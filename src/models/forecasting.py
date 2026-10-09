"""Model A (monthly sales) and Model B (category demand) forecasting with leakage-safe time-based validation.

Candidates: seasonal naive (same month last year x trailing level ratio), SARIMAX on log sales with promotion-day
and open-day regressors, and XGBoost on daily features (calendar, promotions, lags >= 365 days masked at origin).
Validation: holdout Jan-Sep 2026 from origin 31-Dec-2025 plus rolling origins (Jun-2025, Sep-2025) - training
data never extends past the origin and lag features are built only from pre-origin values.
Accuracy describes SYNTHETIC data only; it is not evidence of accuracy on any real retailer's transactions.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import xgboost as xgb
from statsmodels.tsa.statespace.sarimax import SARIMAX

from src.config import END, EXTERNAL, SEED
from src.engineering.sqlutil import connect
from src.generate.synthetic import PROMOS

warnings.filterwarnings("ignore")
FUT_END = "2027-09-30"
CATS = ["Sofas & Sectionals", "Dining", "Bedroom", "Mattresses & Bases", "Living & Occasional", "Décor & Lighting", "Home Office"]


def calendar():
    d = pd.DataFrame({"date": pd.date_range("2024-01-01", FUT_END)})
    hol = set(pd.to_datetime(pd.read_csv(EXTERNAL / "alberta_holidays.csv").date))
    md = d.date.dt.strftime("%m-%d")
    d["open"] = ((d.date.dt.dayofweek != 6) & ~d.date.isin(hol) & ~md.isin(["12-25", "12-26"])).astype(int)
    d["promo"] = 0.0
    d["promo_disc"] = 0.0
    for name, s, e, disc, mult, scope in PROMOS:
        on = (md >= s) & (md <= e)
        d.loc[on, "promo"] = 1.0 if scope == "All" else 0.5
        d.loc[on, "promo_disc"] = disc
    return d


def daily_frame():
    con = connect()
    # target = WRITTEN bookings (all lines as ordered, incl. orders later cancelled): cancellations are unknown when forecasting
    s = pd.read_sql_query("""SELECT transaction_date date, SUM(net_sales_cad) net_sales, SUM(units) units FROM sales_transactions
                             WHERE transaction_date >= '2024-01-01' GROUP BY 1""", con, parse_dates=["date"])
    c = pd.read_sql_query("""SELECT transaction_date date, category, SUM(units) units FROM sales_transactions
                             WHERE line_status <> 'Cancelled' AND transaction_date >= '2024-01-01' GROUP BY 1, 2""", con, parse_dates=["date"])
    con.close()
    d = calendar().merge(s, on="date", how="left")
    hist = d.date <= pd.Timestamp(END)
    d.loc[hist, ["net_sales", "units"]] = d.loc[hist, ["net_sales", "units"]].fillna(0)
    cu = c.pivot_table(index="date", columns="category", values="units", aggfunc="sum")
    d = d.merge(cu, left_on="date", right_index=True, how="left")
    for k in CATS:
        if k not in d:
            d[k] = 0.0
        d.loc[hist, k] = d.loc[hist, k].fillna(0)
    return d


def monthly(d, col):
    m = d.set_index("date")[col].resample("MS").sum(min_count=1)
    return m


def month_exog(d):
    m = d.set_index("date").resample("MS").agg({"open": "sum", "promo": "sum"})
    return m


# ----------------------------------------------------------------------------------------------- models (each returns forecast, lo80, hi80)
def seasonal_naive(y: pd.Series, origin, horizon):
    tr = y[y.index <= origin]
    lvl = tr.iloc[-6:].sum() / tr.iloc[-18:-12].sum() if len(tr) >= 18 else 1.0
    f = np.array([tr.get(h - pd.DateOffset(years=1), tr.iloc[-12:].mean()) * lvl for h in horizon])
    resid = (tr.iloc[12:].values - tr.shift(12).iloc[12:].values * lvl)
    sd = np.nanstd(resid) if len(resid) > 3 else f.std()
    return f, f - 1.2816 * sd, f + 1.2816 * sd


def sarimax(y: pd.Series, ex: pd.DataFrame, origin, horizon):
    tr = y[y.index <= origin]
    X = ex[["open", "promo"]]
    m = SARIMAX(np.log(tr.clip(lower=1)), exog=X.loc[tr.index], order=(1, 0, 0), seasonal_order=(0, 1, 0, 12), trend="n").fit(disp=False)
    fc = m.get_forecast(len(horizon), exog=X.loc[horizon])
    ci = fc.conf_int(alpha=0.2)
    return np.exp(fc.predicted_mean.values), np.exp(ci.iloc[:, 0].values), np.exp(ci.iloc[:, 1].values)


def _features(d, col, origin):
    x = d[["date", "open", "promo", "promo_disc", col]].copy()
    x.loc[x.date > origin, col] = np.nan                                   # mask the target after the origin (no leakage)
    x["dow"], x["month"], x["doy"] = x.date.dt.dayofweek, x.date.dt.month, x.date.dt.dayofyear
    x["t"] = (x.date - pd.Timestamp("2024-01-01")).dt.days
    s = x.set_index("date")[col]
    lag = s.shift(364)
    x["lag364_7d"] = lag.rolling(7, min_periods=1).mean().values            # value one year ago: only pre-origin data for horizons <= 364 days
    x["lag364_28d"] = lag.rolling(28, min_periods=1).mean().values
    return x


FEATS = ["open", "promo", "promo_disc", "dow", "month", "doy", "t", "lag364_7d", "lag364_28d"]


def xgb_model(d, col, origin, horizon, resid_sd=None):
    x = _features(d, col, origin)
    tr = x[(x.date <= origin) & x[col].notna()]                              # lags may be missing in year 1 (XGBoost handles NaN)
    m = xgb.XGBRegressor(n_estimators=350, max_depth=3, learning_rate=0.04, subsample=0.9, colsample_bytree=0.9, random_state=SEED, objective="reg:squarederror")
    m.fit(tr[FEATS], tr[col])
    fut = x[(x.date > origin) & (x.date <= horizon[-1] + pd.offsets.MonthEnd(0))].copy()
    fut["pred"] = np.clip(m.predict(fut[FEATS]), 0, None) * fut.open
    mf = fut.set_index("date").pred.resample("MS").sum().reindex(horizon).values
    ins = tr.assign(p=m.predict(tr[FEATS]) * tr.open).set_index("date")[[col, "p"]].resample("MS").sum()
    sd = resid_sd if resid_sd is not None else np.std(ins[col] - ins.p) * 1.6          # in-sample error widened for out-of-sample use
    return mf, mf - 1.2816 * sd, mf + 1.2816 * sd, m


MODELS = ["Seasonal naive", "SARIMAX", "XGBoost"]


def run_one(name, d, col, y, ex, origin, horizon):
    if name == "Seasonal naive":
        return seasonal_naive(y, origin, horizon)
    if name == "SARIMAX":
        return sarimax(y, ex, origin, horizon)
    f, lo, hi, _ = xgb_model(d, col, origin, horizon)
    return f, lo, hi


def metrics(a, f, lo, hi):
    a, f = np.asarray(a, float), np.asarray(f, float)
    return {"WAPE": np.abs(a - f).sum() / np.abs(a).sum(), "MAE": np.abs(a - f).mean(), "RMSE": float(np.sqrt(((a - f) ** 2).mean())),
            "bias_pct": (f.sum() - a.sum()) / a.sum() * 100, "PI80_coverage": float(np.mean((a >= lo) & (a <= hi)))}


ORIGINS = [("Holdout Jan-Sep 2026", "2025-12-31", 9), ("Rolling origin Jun-2025 (+6m)", "2025-06-30", 6), ("Rolling origin Sep-2025 (+6m)", "2025-09-30", 6)]


def backtest(d, targets):
    ex = month_exog(d)
    rows, preds = [], []
    for col in targets:
        y = monthly(d[d.date <= END], col)
        for design, o, h in ORIGINS:
            origin = pd.Timestamp(o)
            horizon = pd.date_range(origin + pd.Timedelta(days=1), periods=h, freq="MS")
            for name in MODELS:
                f, lo, hi = run_one(name, d, col, y, ex, origin, horizon)
                a = y.reindex(horizon).values
                rows.append({"target": col, "design": design, "model": name, **metrics(a, f, lo, hi)})
                preds += [{"target": col, "design": design, "model": name, "month": m, "actual": av, "forecast": fv, "lo80": l, "hi80": u}
                          for m, av, fv, l, u in zip(horizon, a, f, lo, hi)]
    res = pd.DataFrame(rows)
    summ = res.groupby(["target", "model"]).agg(WAPE_holdout=("WAPE", lambda x: x.iloc[0]), WAPE_mean_all_origins=("WAPE", "mean"), MAE_holdout=("MAE", lambda x: x.iloc[0]),
                                                RMSE_holdout=("RMSE", lambda x: x.iloc[0]), bias_pct_holdout=("bias_pct", lambda x: x.iloc[0]),
                                                PI80_coverage_mean=("PI80_coverage", "mean")).reset_index()
    return res, pd.DataFrame(preds), summ


def final_forecast(d, targets, summ):
    ex = month_exog(d)
    origin = pd.Timestamp(END)
    horizon = pd.date_range(origin + pd.Timedelta(days=1), periods=12, freq="MS")
    out, chosen = [], {}
    for col in targets:
        y = monthly(d[d.date <= END], col)
        s = summ[summ.target == col].assign(score=lambda x: (x.WAPE_holdout + x.WAPE_mean_all_origins) / 2).sort_values("score")   # holdout and rolling origins weighted equally
        chosen[col] = s.model.iloc[0]
        for name in MODELS:
            if name == "XGBoost":                          # intervals sized from out-of-sample backtest error, not in-sample fit
                rmse = float(s.set_index("model").RMSE_holdout.get("XGBoost"))
                f, lo, hi, _ = xgb_model(d, col, origin, horizon, resid_sd=rmse)
            else:
                f, lo, hi = run_one(name, d, col, y, ex, origin, horizon)
            out += [{"target": col, "model": name, "month": m, "forecast": fv, "lo80": max(l, 0), "hi80": u, "selected": name == chosen[col]}
                    for m, fv, l, u in zip(horizon, f, lo, hi)]
    return pd.DataFrame(out), chosen
