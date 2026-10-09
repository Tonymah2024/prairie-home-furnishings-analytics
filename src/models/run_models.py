"""Run Models A-D, save evaluation tables, forecasts and scored pipelines (all on SYNTHETIC data)."""
import json

import numpy as np
import pandas as pd

from src.config import TABLES
from src.models import classifiers as C
from src.models import forecasting as F


def _save(df, name, status="SYNTHETIC"):
    d = df.copy()
    d["data_status"] = status
    d.to_csv(TABLES / f"{name}.csv", index=False)


def run():
    R = {}
    d = F.daily_frame()
    targets = ["net_sales"] + F.CATS
    res, preds, summ = F.backtest(d, targets)
    fc, chosen = F.final_forecast(d, targets, summ)
    _save(res, "forecast_backtest_detail")
    _save(preds, "forecast_backtest_predictions")
    _save(summ, "forecast_model_comparison")
    _save(fc, "forecast_next_12_months_all_models", "FORECAST (SYNTHETIC)")
    _save(fc[fc.selected], "forecast_next_12_months", "FORECAST (SYNTHETIC)")
    R["model_a"] = {"chosen": chosen["net_sales"], "comparison": summ[summ.target == "net_sales"].to_dict("records")}
    cat = summ[summ.target != "net_sales"]
    R["model_b"] = {"chosen": {k: v for k, v in chosen.items() if k != "net_sales"},
                    "mean_wape_by_model": cat.groupby("model").WAPE_mean_all_origins.mean().to_dict()}
    rc, reg, best_c, openp, imp, test_c = C.model_c()
    _save(rc, "delay_model_evaluation")
    _save(pd.DataFrame([reg]), "delay_model_regression")
    _save(openp[["po_id", "po_type", "supplier_id", "supplier_class", "product_id", "category", "order_line_id", "order_date", "promised_date", "already_past_promise", "p_late"]]
          .sort_values("p_late", ascending=False), "open_po_delay_risk")
    _save(imp.rename("importance").reset_index().rename(columns={"index": "feature"}), "delay_model_feature_importance")
    R["model_c"] = {"best": best_c, "evaluation": rc.to_dict("records"), "regression": reg}
    rd, best_d, calib, op, realisation, coefs = C.model_d()
    _save(rd, "conversion_model_evaluation")
    _save(calib, "conversion_model_calibration")
    _save(op[["consultation_id", "consultation_date", "customer_id", "designer_id", "consultation_type", "quotation_amount_cad", "p_convert", "expected_revenue_cad"]]
          .sort_values("p_convert", ascending=False), "open_consultation_pipeline", "FORECAST (SYNTHETIC)")
    if coefs is not None:
        _save(coefs.rename("coefficient").reset_index().rename(columns={"index": "feature"}), "conversion_model_coefficients")
    R["model_d"] = {"best": best_d, "evaluation": rd.to_dict("records"), "pipeline_open": int(len(op)), "pipeline_expected_conversions": float(op.p_convert.sum()),
                    "pipeline_expected_revenue": float(op.expected_revenue_cad.sum()), "quote_realisation_ratio": float(realisation)}
    (TABLES / "model_results.json").write_text(json.dumps(R, indent=1, default=lambda x: float(x) if isinstance(x, (np.floating, np.integer)) else str(x)))
    return R


if __name__ == "__main__":
    R = run()
    pd.set_option("display.width", 200)
    print(pd.read_csv(TABLES / "forecast_model_comparison.csv").round(3).to_string())
    print(pd.read_csv(TABLES / "delay_model_evaluation.csv").round(3).to_string(), R["model_c"]["regression"])
    print(pd.read_csv(TABLES / "conversion_model_evaluation.csv").round(3).to_string())
    print({k: v for k, v in R["model_d"].items() if k != "evaluation"})
