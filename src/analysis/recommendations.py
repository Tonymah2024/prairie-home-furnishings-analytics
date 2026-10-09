"""Management recommendations, each quantified by re-running the integrated forecast engine against Base or by stated
arithmetic on the synthetic results. ILLUSTRATIVE ONLY - estimates for a fictional retailer, not guaranteed benefits."""
from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pandas as pd

from src.config import TABLES
from src.finance import forecast as F


def _base():
    js = json.loads((TABLES / "fin_forecast_base.json").read_text())
    dv = pd.DataFrame(js["drivers"]).T
    dv.columns = range(1, F.H + 1)
    return {"A": js["A"], "drivers": dv, "opening": js["opening"]}


def delta(base, **kw):
    b0 = F.summary(F.run(F.SCENARIOS["Base"], base))
    r = F.summary(F.run(replace(F.SCENARIOS["Base"], **kw), base))
    return {"profit": r["net_income"] - b0["net_income"], "pretax": (r["ebitda"] - b0["ebitda"]), "cash": r["closing_cash"] - b0["closing_cash"],
            "wc": r["closing_working_capital"] - b0["closing_working_capital"]}


def build():
    base = _base()
    K = json.loads((TABLES / "findings.json").read_text())["metrics"]
    fu = pd.read_csv(TABLES / "consultations_by_follow_up_count.csv")
    cons = pd.read_csv(TABLES / "consultations_monthly.csv")
    sup = pd.read_csv(TABLES / "supplier_lead_time_performance.csv")
    inv = pd.read_csv(TABLES / "inventory_intelligence.csv")
    pairs = pd.read_csv(TABLES / "cross_sell_pairs.csv")
    db = pd.read_csv(TABLES / "discount_bands.csv")
    A = base["A"]
    gm = 1 - A["cogs_ratio"] * (1 + A["freight_ratio"])
    recs = []

    def add(**k):
        recs.append(k)

    # 1 consultation follow-up cadence
    low = fu[fu.follow_up_count < 2]
    share_low = low.consults.sum() / fu.consults.sum()
    conv_now = (fu.consults * fu.conversion_pct).sum() / fu.consults.sum()
    target = fu[fu.follow_up_count == 2].conversion_pct.iloc[0]
    uplift_rel = share_low * (target - (low.consults * low.conversion_pct).sum() / low.consults.sum()) / conv_now * 0.5      # assume half the gap is closed
    d1 = delta(base, consult_conv_change=uplift_rel)
    add(area="Design consultations", title="Standardise a two-touch follow-up within 7 days of every design consultation",
        impact=d1["pretax"], cash=d1["cash"],
        method=f"{share_low:.0%} of consultations get fewer than two follow-ups and convert well below the {target:.0f}% achieved with two. Closing half of that gap lifts overall "
               f"conversion {uplift_rel:+.1%} relative; the forecast engine re-run with consultation conversion {uplift_rel:+.1%}.",
        assumptions="Follow-up is a driver of conversion, not only a marker of keen customers (to be tested with an A/B rota); designer capacity is sufficient.",
        kpis="Consult-to-order conversion, days to first follow-up, revenue per consultation", effort="Low", timeframe="0-3 months")
    # 2 supplier delays
    d2 = delta(base, delay_reduction=0.15)
    worst = sup[sup.pos >= 30].sort_values("on_time_pct").head(3)
    add(area="Supplier & fulfilment", title="Supplier scorecards and lead-time buffers for the three least reliable suppliers",
        impact=d2["pretax"], cash=d2["cash"],
        method=f"Weakest on-time performance: {', '.join(f'{r.supplier_name} ({r.on_time_pct:.0f}%)' for r in worst.itertuples())}. Engine re-run with supplier delays -15% "
               "(revenue recognised earlier, fewer delay-driven cancellations).",
        assumptions="Monthly scorecard reviews, realistic quoted lead times and alternate makers for persistently late lines reduce late weeks by 15%.",
        kpis="Supplier on-time %, custom orders ready by promise date, delay-driven cancellations", effort="Medium", timeframe="3-6 months")
    # 3 discount discipline
    disc_share = db[db.discount_reason == "Manager discretionary"].net_sales.sum() / db.net_sales.sum()
    d3 = delta(base, discount_change=-0.005)
    add(area="Gross margin", title="Approval bands for discretionary discounts and price-match tracking",
        impact=d3["pretax"], cash=d3["cash"],
        method=f"Discretionary discounts touch {disc_share:.0%} of sales. Engine re-run with the overall discount rate 0.5 pt lower.",
        assumptions="No volume loss: discretionary discounts close sales that would mostly have closed anyway; promotions unchanged.",
        kpis="Average discount %, share of lines with discretionary discount by associate, gross margin %", effort="Low", timeframe="0-3 months")
    # 4 inventory
    d4 = delta(base, slow_reduction=0.30)
    recover = K["lost_sales_ttm"] * 0.30 * gm
    add(area="Inventory", title="Clear 30% of slow-moving stock and move A-items to service-level reorder points",
        impact=d4["pretax"] + recover, cash=d4["cash"],
        method=f"Engine re-run clearing 30% of the ${A['slow_value']:,.0f} of >180-day-cover stock (20% markdown). Plus 30% of the ${K['lost_sales_ttm']:,.0f} TTM stockout "
               f"sales recovered by the recommended reorder points at the {gm:.0%} gross margin (${recover:,.0f}).",
        assumptions="Reorder points from inventory_intelligence.csv (95/90/85% service by ABC class); clearance through events and bundles.",
        kpis="Inventory turnover, aged (>180 d) stock $, stockout events, fill rate", effort="Medium", timeframe="0-6 months")
    # 5 supplier terms
    d5 = delta(base, dpo_change_days=10)
    add(area="Working capital", title="Negotiate Net 45 with the largest importers and distributors",
        impact=d5["pretax"], cash=d5["cash"], method="Engine re-run with supplier payment days +10.",
        assumptions="Volume commitments in exchange for terms; no price increase.", kpis="DPO, cash conversion cycle", effort="Medium", timeframe="3-9 months")
    # 6 bundles / cross-sell
    top = pairs[pairs.orders_together >= 200].sort_values("lift", ascending=False).iloc[0]
    n_ante = top.orders_together / (top.confidence_pct / 100)
    extra = n_ante * 0.05 * (12 / 33)
    avg_line = pd.read_csv(TABLES / "product_profitability.csv").query("subcategory == @top.consequent and units > 0")
    val = (avg_line.net_sales.sum() / avg_line.units.sum()) if len(avg_line) else 500
    imp6 = extra * val * gm
    add(area="Sales", title=f"Room packages: {top.antecedent} + {top.consequent} bundle with designer styling",
        impact=imp6, cash=imp6 * 0.9,
        method=f"{top.antecedent} buyers already add {top.consequent} {top.confidence_pct:.0f}% of the time (lift {top.lift:.1f}x). Raising attachment by 5 pts adds "
               f"~{extra:.0f} items a year at ~${val:,.0f} and a {gm:.0%} margin.",
        assumptions="Bundle priced at 5% off the second item; attachment lift of 5 pts is a target, not an estimate.", kpis="Attachment rate, items per order, AOV",
        effort="Low", timeframe="0-3 months")
    # 7 pickup capacity
    add(area="Fulfilment", title="Add four Saturday pickup slots and offer weekday-pickup incentives",
        impact=0.0, cash=0.0,
        method=f"Saturday slots run at {K['sat_util']:.0f}% utilisation and all 9 slots were full on {K['pickup_full_days']} days; customers waiting for a slot delay hand-off "
               "(and therefore revenue recognition and balance collection).",
        assumptions="Warehouse staff rota shift; benefit is customer experience and faster cash collection, not modelled as profit.",
        kpis="Pickup wait days, slot utilisation by weekday, customer satisfaction", effort="Low", timeframe="0-3 months")
    # 8 cash deployment
    fc = F.summary(F.run(F.SCENARIOS["Base"], base))
    excess = max(0.0, fc["min_cash"] - 600000)
    add(area="Treasury", title="Deploy surplus cash: repay the term loan early and hold a treasury reserve",
        impact=excess * 0.03, cash=0.0,
        method=f"Base forecast minimum month-end cash ${fc['min_cash']:,.0f} vs a ${600000:,.0f} operating reserve; ${excess:,.0f} could earn ~3% or retire the remaining term loan.",
        assumptions="Customer deposits must stay covered by liquid assets; reserve sized to two months of supplier payments.",
        kpis="Cash vs reserve, net interest, deposit coverage", effort="Low", timeframe="0-3 months")
    df = pd.DataFrame(recs)
    df["value_score"] = (df.impact + df.cash.clip(lower=0) * 0.05) / df.effort.map({"Low": 1, "Medium": 2, "High": 3})
    df = df.sort_values("value_score", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", np.arange(1, len(df) + 1))
    df = df.rename(columns={"impact": "pretax_profit_impact_12m", "cash": "cash_impact_12m", "method": "methodology"})
    df["data_status"] = "SYNTHETIC - illustrative estimate for a fictional retailer"
    df.to_csv(TABLES / "recommendations.csv", index=False)
    return df


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    print(build()[["rank", "area", "title", "pretax_profit_impact_12m", "cash_impact_12m"]].round(0).to_string())
