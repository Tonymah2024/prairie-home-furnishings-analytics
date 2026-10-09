"""Model C (custom / special-order fulfilment delay) and Model D (design-consultation conversion propensity).

Both use only information available at decision time, and a strict time split (train on earlier records, test on
later ones). Supplier history features are computed from receipts that happened BEFORE each order date.
Results describe SYNTHETIC data only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.config import END, SEED
from src.engineering.sqlutil import connect

END_TS = pd.Timestamp(END)
LATE_DAYS = 7


def _q(sql):
    con = connect()
    try:
        return pd.read_sql_query(sql, con)
    finally:
        con.close()


# ----------------------------------------------------------------------------------------------- Model C
def delay_dataset():
    po = _q("""SELECT p.*, s.supplier_class, pr.category, pr.subcategory, pr.list_price_cad FROM purchase_orders p JOIN suppliers s USING (supplier_id)
               JOIN products pr USING (product_id) WHERE p.po_type IN ('Custom', 'Special order') AND p.replacement_of IS NULL AND p.status <> 'Cancelled'""")
    for c in ["order_date", "promised_date", "received_date"]:
        po[c] = pd.to_datetime(po[c])
    po = po[po.order_date >= "2024-01-01"].sort_values("order_date").reset_index(drop=True)
    # outcome (right-censoring handled: open POs already >7 days past promise are late; open POs not yet due are excluded)
    recv = po.status.isin(["Received", "Damaged - replaced"]) & po.received_date.notna()
    po["delay"] = np.where(recv, (po.received_date - po.promised_date).dt.days, np.where((END_TS - po.promised_date).dt.days > LATE_DAYS, (END_TS - po.promised_date).dt.days, np.nan))
    po["late"] = (po.delay > LATE_DAYS).astype(float)
    po.loc[po.delay.isna(), "late"] = np.nan
    po["quoted_lead_days"] = (po.promised_date - po.order_date).dt.days
    po["order_month"] = po.order_date.dt.month
    po["peak_season"] = po.order_month.isin([10, 11, 12, 1]).astype(int)
    po["log_value"] = np.log1p(po.qty_ordered * po.unit_cost_cad)
    # leakage-safe supplier history: receipts strictly before the order date
    hist = po[recv][["supplier_id", "received_date", "delay"]].rename(columns={"received_date": "known_date"}).sort_values("known_date")
    feats = []
    for r in po[["supplier_id", "order_date"]].itertuples():
        h = hist[(hist.supplier_id == r.supplier_id) & (hist.known_date < r.order_date) & (hist.known_date >= r.order_date - pd.Timedelta(days=270))]
        feats.append((len(h), (h.delay > LATE_DAYS).mean() if len(h) else np.nan, h.delay.mean() if len(h) else np.nan))
    po[["supplier_hist_n", "supplier_hist_late_rate", "supplier_hist_mean_delay"]] = feats
    load = po.groupby("supplier_id").apply(lambda g: g.order_date.apply(lambda d: ((g.order_date < d) & ((g.received_date.isna()) | (g.received_date > d))).sum()), include_groups=False)
    po["supplier_open_pos"] = load.reset_index(level=0, drop=True).reindex(po.index).values
    return po


C_NUM = ["quoted_lead_days", "order_month", "peak_season", "log_value", "supplier_hist_n", "supplier_hist_late_rate", "supplier_hist_mean_delay", "supplier_open_pos"]
C_CAT = ["supplier_class", "category", "po_type"]


def _pipe_logit(num, cat):
    pre = ColumnTransformer([("n", Pipeline([("imp", SimpleImputer(strategy="median")), ("s", StandardScaler())]), num),
                             ("c", OneHotEncoder(handle_unknown="ignore"), cat)])
    return Pipeline([("pre", pre), ("m", LogisticRegression(max_iter=2000, C=0.5))])


def _xgb_frame(df, num, cat, cols=None):
    X = pd.get_dummies(df[num + cat], columns=cat, dtype=float)
    return X.reindex(columns=cols, fill_value=0.0) if cols is not None else X


def lift_at(y, p, frac=0.2):
    k = max(1, int(len(p) * frac))
    top = np.argsort(-p)[:k]
    return y[top].mean() / y.mean()


def eval_binary(y, p):
    return {"AUC": roc_auc_score(y, p), "Brier": brier_score_loss(y, p), "LogLoss": log_loss(y, np.clip(p, 1e-4, 1 - 1e-4)), "lift_top20pct": lift_at(np.asarray(y), np.asarray(p)),
            "base_rate": float(np.mean(y)), "n_test": int(len(y))}


def model_c():
    po = delay_dataset()
    lab = po[po.late.notna()]
    train = lab[lab.order_date <= "2025-06-30"]
    test = lab[(lab.order_date > "2025-06-30") & (lab.order_date <= "2026-05-31")]
    y_tr, y_te = train.late.values, test.late.values
    # baseline: supplier's historical late rate (falls back to the overall training rate)
    base = test.supplier_hist_late_rate.fillna(y_tr.mean()).values
    lg = _pipe_logit(C_NUM, C_CAT).fit(train, y_tr)
    p_lg = lg.predict_proba(test)[:, 1]
    Xtr = _xgb_frame(train, C_NUM, C_CAT)
    xm = xgb.XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9, random_state=SEED, eval_metric="logloss")
    xm.fit(Xtr, y_tr)
    p_x = xm.predict_proba(_xgb_frame(test, C_NUM, C_CAT, Xtr.columns))[:, 1]
    res = pd.DataFrame([{"model": "Baseline: supplier historical late rate", **eval_binary(y_te, base)},
                        {"model": "Logistic regression", **eval_binary(y_te, p_lg)}, {"model": "XGBoost", **eval_binary(y_te, p_x)}])
    # delay-days regression (late magnitude) baseline vs XGBoost
    xr = xgb.XGBRegressor(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.9, random_state=SEED).fit(Xtr, train.delay.clip(-5, 90))
    d_x = xr.predict(_xgb_frame(test, C_NUM, C_CAT, Xtr.columns))
    d_b = test.supplier_hist_mean_delay.fillna(train.delay.mean()).values
    reg = {"MAE_days_baseline": mean_absolute_error(test.delay.clip(-5, 90), d_b), "MAE_days_xgboost": mean_absolute_error(test.delay.clip(-5, 90), d_x)}
    best = res.iloc[1:].sort_values("AUC").iloc[-1].model
    # score currently open POs (decision support for the order tracker): refit on all labelled data
    xm_all = xgb.XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9, random_state=SEED, eval_metric="logloss")
    Xall = _xgb_frame(lab, C_NUM, C_CAT)
    xm_all.fit(Xall, lab.late.values)
    lg_all = _pipe_logit(C_NUM, C_CAT).fit(lab, lab.late.values)
    openp = po[po.status == "Open"].copy()
    openp["p_late"] = lg_all.predict_proba(openp)[:, 1] if best == "Logistic regression" else xm_all.predict_proba(_xgb_frame(openp, C_NUM, C_CAT, Xall.columns))[:, 1]
    openp["already_past_promise"] = (END_TS - openp.promised_date).dt.days > 0
    imp = pd.Series(xm.feature_importances_, index=Xtr.columns).sort_values(ascending=False).head(12)
    return res, reg, best, openp, imp, test.assign(p_xgb=p_x, p_logit=p_lg, p_base=base)


# ----------------------------------------------------------------------------------------------- Model D
D_NUM = ["log_quote", "rooms_in_scope", "repeat_customer", "consult_month", "peak_month", "dow"]
D_CAT = ["consultation_type", "designer_id", "customer_type", "acquisition_channel"]


def conversion_dataset():
    c = _q("""SELECT c.*, cu.customer_type, cu.acquisition_channel FROM consultations c JOIN customers cu USING (customer_id)""")
    c["consultation_date"] = pd.to_datetime(c.consultation_date)
    c = c[c.consultation_date >= "2024-01-01"]
    c["log_quote"] = np.log(c.quotation_amount_cad)
    c["consult_month"] = c.consultation_date.dt.month
    c["peak_month"] = c.consult_month.isin([1, 9, 10, 11]).astype(int)
    c["dow"] = c.consultation_date.dt.dayofweek
    c["y"] = c.converted.astype(float)
    return c.sort_values("consultation_date").reset_index(drop=True)


def model_d():
    c = conversion_dataset()
    closed = c[c.conversion_status != "Open - follow-up in progress"]
    train = closed[closed.consultation_date <= "2025-09-30"]
    test = closed[(closed.consultation_date > "2025-09-30") & (closed.consultation_date <= END_TS - pd.Timedelta(days=45))]
    y_tr, y_te = train.y.values, test.y.values
    rate = train.groupby(["designer_id", "consultation_type"]).y.mean()
    base = np.array([rate.get((a, b), y_tr.mean()) for a, b in zip(test.designer_id, test.consultation_type)])
    lg = _pipe_logit(D_NUM, D_CAT).fit(train, y_tr)
    p_lg = lg.predict_proba(test)[:, 1]
    Xtr = _xgb_frame(train, D_NUM, D_CAT)
    xm = xgb.XGBClassifier(n_estimators=250, max_depth=3, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9, random_state=SEED, eval_metric="logloss").fit(Xtr, y_tr)
    p_x = xm.predict_proba(_xgb_frame(test, D_NUM, D_CAT, Xtr.columns))[:, 1]
    res = pd.DataFrame([{"model": "Baseline: designer x consult-type rate", **eval_binary(y_te, base)},
                        {"model": "Logistic regression", **eval_binary(y_te, p_lg)}, {"model": "XGBoost", **eval_binary(y_te, p_x)}])
    best = res.iloc[1:].sort_values("AUC").iloc[-1].model
    t = test.assign(p=p_lg if best == "Logistic regression" else p_x)
    t["decile"] = pd.qcut(t.p.rank(method="first"), 10, labels=False) + 1
    calib = t.groupby("decile").agg(consults=("y", "size"), predicted=("p", "mean"), actual=("y", "mean")).reset_index()
    # pipeline forecast for open consultations
    lg_all = _pipe_logit(D_NUM, D_CAT).fit(closed, closed.y.values)
    xm_all = xgb.XGBClassifier(n_estimators=250, max_depth=3, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9, random_state=SEED, eval_metric="logloss")
    Xall = _xgb_frame(closed, D_NUM, D_CAT)
    xm_all.fit(Xall, closed.y.values)
    op = c[c.conversion_status == "Open - follow-up in progress"].copy()
    op["p_convert"] = lg_all.predict_proba(op)[:, 1] if best == "Logistic regression" else xm_all.predict_proba(_xgb_frame(op, D_NUM, D_CAT, Xall.columns))[:, 1]
    conv = closed[closed.converted == 1]
    realisation = (conv.final_sales_revenue_cad / conv.quotation_amount_cad).median()
    op["expected_revenue_cad"] = op.p_convert * op.quotation_amount_cad * realisation
    coefs = None
    if best == "Logistic regression":
        names = lg.named_steps["pre"].get_feature_names_out()
        coefs = pd.Series(lg.named_steps["m"].coef_[0], index=names).sort_values()
    return res, best, calib, op, realisation, coefs
