"""Forecast evaluation and leakage controls."""
import numpy as np
import pandas as pd

from src.config import TABLES
from src.models import classifiers as C
from src.models import forecasting as F

ORIGIN = pd.Timestamp("2025-12-31")
HM = pd.date_range("2026-01-01", periods=9, freq="MS")


def _perturb(d):
    x = d.copy()
    x.loc[x.date > ORIGIN, "net_sales"] = x.loc[x.date > ORIGIN, "net_sales"] * 5 + 1e5
    return x


def test_forecasts_ignore_post_origin_data():
    d = F.daily_frame()
    p = _perturb(d)
    ex = F.month_exog(d)
    for fn in (lambda dd: F.seasonal_naive(F.monthly(dd[dd.date <= ORIGIN], "net_sales"), ORIGIN, HM)[0],
               lambda dd: F.sarimax(F.monthly(dd[dd.date <= "2026-09-30"], "net_sales"), ex, ORIGIN, HM)[0],
               lambda dd: F.xgb_model(dd, "net_sales", ORIGIN, HM)[0]):
        assert np.allclose(fn(d), fn(p), rtol=1e-9)


def test_xgb_features_mask_target_after_origin():
    f = F._features(F.daily_frame(), "net_sales", ORIGIN)
    assert f.loc[f.date > ORIGIN, "net_sales"].isna().all()


def test_supplier_history_uses_only_past_receipts():
    po = C.delay_dataset()
    r = po.iloc[len(po) // 2]
    past = po[(po.supplier_id == r.supplier_id) & po.received_date.notna() & (po.received_date < r.order_date) & (po.received_date >= r.order_date - pd.Timedelta(days=270))]
    assert r.supplier_hist_n == len(past)


def test_model_evaluation_tables_complete():
    fmc = pd.read_csv(TABLES / "forecast_model_comparison.csv")
    assert set(fmc.model) == {"Seasonal naive", "SARIMAX", "XGBoost"}
    sel = fmc[fmc.target == "net_sales"].assign(s=lambda x: (x.WAPE_holdout + x.WAPE_mean_all_origins) / 2).sort_values("s").model.iloc[0]
    fc = pd.read_csv(TABLES / "forecast_next_12_months.csv")
    assert fc[fc.target == "net_sales"].model.iloc[0] == sel and len(fc[fc.target == "net_sales"]) == 12
    for t in ["delay_model_evaluation", "conversion_model_evaluation"]:
        e = pd.read_csv(TABLES / f"{t}.csv")
        assert e.AUC.between(0.5, 1).all() and len(e) == 3
