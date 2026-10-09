"""Client-facing deliverables (HTML -> PDF via headless Chrome): executive management report, financial performance analysis,
demonstration guide, pilot proposal and 90-day pilot plan. All figures come from computed outputs of the SYNTHETIC demo."""
from __future__ import annotations

import html
import json

import numpy as np
import pandas as pd

from src.analysis.style import cad, fig, save
from src.config import APP_NAME, ATTRIBUTION, BRAND, FIN_OUT, REPORTS, RETRIEVAL_DATE, SYNTHETIC_LABEL, TABLES
from src.finance import ratios as R
from src.finance import statements as S
from src.reporting.pdf import CSS, img, money, page, render_pdf, tbl

FIN = [BRAND["brand"], BRAND["teal"], BRAND["accent"], BRAND["warn"]]
UP, DOWN, TOT = BRAND["teal"], BRAND["bad"], BRAND["navy"]
DEMO_URL = "https://prairie-home-furnishings-bi.streamlit.app"


def t(name, **kw):
    return pd.read_csv(TABLES / f"{name}.csv", **kw)


def stmt(name):
    d = t(f"fin_{name}", index_col=0)
    return d.drop(columns=[c for c in ("label", "data_status") if c in d.columns])


def acct(v, d=0):
    if pd.isna(v):
        return ""
    if abs(v) < 0.5 * 10 ** -d:
        return "-"
    return f"({abs(v):,.{d}f})" if v < 0 else f"{v:,.{d}f}"


def esc(s):
    return html.escape(str(s))


# ----------------------------------------------------------------------------------------------- charts
def charts():
    is_m, bs_m, cf_m = stmt("income_statement_monthly"), stmt("balance_sheet_monthly"), stmt("cash_flow_monthly")
    mo = pd.PeriodIndex(is_m.columns, freq="M").to_timestamp()
    sm = t("sales_monthly", parse_dates=["month"])
    f, ax = fig(11, 4.4)
    ax.bar(sm.month - pd.Timedelta(days=6), sm.net_sales, width=12, color=FIN[0], label="Written sales (order date)")
    ax.bar(mo + pd.Timedelta(days=6), is_m.loc["net_sales"], width=12, color=FIN[1], label="Net sales recognised (hand-off)")
    ax.set_title("Bookings vs recognised revenue: customer deposits bridge the timing gap")
    ax.legend(loc="upper left")
    cad(ax, k=True)
    save(f, "R01_bookings_vs_revenue", "Fictional retailer; synthetic data.")
    cat = t("sales_by_category").sort_values("net_sales")
    f, (a1, a2) = fig(11, 4.2, 1, 2, sharey=True)
    a1.barh(cat.category, cat.net_sales, color=FIN[0])
    a1.set_title("Net sales by category, Jan 2024 - Sep 2026")
    cad(a1, axis="x", k=True)
    a2.barh(cat.category, cat.gm_pct, color=FIN[1])
    for i, v in enumerate(cat.gm_pct):
        a2.text(v + 0.5, i, f"{v:.0f}%", va="center", fontsize=8)
    a2.set_title("Line gross margin %")
    save(f, "R02_category_sales_margin")
    inv = t("inventory_aging_by_category", index_col=0).drop(columns="data_status")
    f, ax = fig(10, 4.2)
    left = np.zeros(len(inv))
    shades = ["#cfe0f5", "#9cc0ec", "#5f97de", "#2a78d6", "#184f95"]
    for i, c in enumerate(inv.columns):
        ax.barh(inv.index, inv[c], left=left, color=shades[i], label=c, edgecolor="white", linewidth=1.5)
        left += inv[c].values
    ax.set_title("Stocked inventory by age (FIFO, cost) - aged stock concentrates in a few categories")
    ax.legend(ncol=5, fontsize=7.5, loc="lower right")
    cad(ax, axis="x", k=True)
    save(f, "R03_inventory_aging")
    sp = t("supplier_lead_time_performance")
    sp = sp[sp.pos >= 30].sort_values("on_time_pct")
    f, ax = fig(10, 4.6)
    ax.barh(sp.supplier_name, sp.on_time_pct, color=[DOWN if v < 65 else FIN[0] for v in sp.on_time_pct])
    for i, (v, d) in enumerate(zip(sp.on_time_pct, sp.p90_delay_days)):
        ax.text(v + 0.8, i, f"{v:.0f}%  (p90 delay {d:.0f} d)", va="center", fontsize=7.5)
    ax.set_xlim(0, 115)
    ax.set_title("Supplier on-time delivery (purchase orders >= 30); red = below 65%")
    save(f, "R04_supplier_on_time")
    bl = t("open_order_backlog_monthly", parse_dates=["month"])
    f, ax = fig(10, 4.2)
    ax.plot(bl.month, bl.open_order_value_incl_gst, color=FIN[0], lw=2.2, label="Open order value (incl. GST)")
    ax.plot(bl.month, bl.deposits_held, color=FIN[1], lw=2.2, label="Deposits held")
    ax.plot(bl.month, bl.balances_still_to_collect, color=FIN[3], lw=2.2, label="Balances to collect at pickup")
    ax.legend(loc="upper left")
    ax.set_title("Unfulfilled orders: deposits held and balances still to collect (month end)")
    cad(ax, k=True)
    save(f, "R05_open_order_backlog")
    fu = t("consultations_by_follow_up_count")
    f, (a1, a2) = fig(11, 3.9, 1, 2)
    a1.bar(fu.follow_up_count.astype(str), fu.conversion_pct, color=FIN[1])
    for i, (v, n) in enumerate(zip(fu.conversion_pct, fu.consults)):
        a1.text(i, v + 1, f"{v:.0f}%\nn={n}", ha="center", fontsize=8)
    a1.set_title("Consultation conversion by follow-ups")
    a1.set_xlabel("follow-ups")
    dz = t("consultations_by_designer_id")
    a2.bar(dz.designer_id, dz.revenue_per_consult, color=FIN[0])
    a2.set_title("Sales per consultation by designer")
    cad(a2, k=True)
    save(f, "R06_consultations")
    f, ax = fig(10, 4.4)
    ax.plot(mo, is_m.loc["ebitda"].rolling(12).sum(), color=FIN[0], lw=2.4, label="EBITDA (TTM)")
    ax.plot(mo, is_m.loc["net_income"].rolling(12).sum(), color=FIN[1], lw=2.4, label="Net income (TTM)")
    ax.plot(mo, cf_m.loc["cfo"].rolling(12).sum(), color=FIN[2], lw=2.4, label="Operating cash flow (TTM)")
    ax.legend(loc="upper left")
    ax.set_title("Profit and cash, trailing twelve months")
    cad(ax, k=True)
    save(f, "R07_profit_cash_ttm")
    f, ax = fig(10, 4.2)
    ax.stackplot(mo, bs_m.loc["inv_stock"], bs_m.loc["inv_alloc"], colors=[FIN[0], FIN[1]], labels=["Stocked inventory", "Allocated to customer orders"], alpha=.9)
    ax.plot(mo, bs_m.loc["deposits"], color=TOT, lw=2.4, label="Customer deposits")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, fontsize=8)
    ax.set_title("Inventory investment vs customer deposits funding it")
    cad(ax, k=True)
    save(f, "R08_inventory_vs_deposits")
    fc = t("forecast_next_12_months_all_models", parse_dates=["month"])
    fc = fc[(fc.target == "net_sales") & fc.selected]
    f, ax = fig(10, 4.2)
    ax.plot(sm.month, sm.net_sales, color=TOT, lw=2, label="Written sales (actual, synthetic)")
    ax.plot(fc.month, fc.forecast, color=FIN[0], lw=2.4, label=f"Forecast ({fc.model.iloc[0]})")
    ax.fill_between(fc.month, fc.lo80, fc.hi80, color=FIN[0], alpha=.15, label="80% interval")
    ax.legend(loc="upper left")
    ax.set_title("Monthly sales: history and 12-month forecast (FORECAST)")
    cad(ax, k=True)
    save(f, "R09_sales_forecast")
    sens = t("fin_forecast_sensitivity").sort_values("delta_net_income")
    f, ax = fig(10, 4.6)
    ax.barh(sens.scenario, sens.delta_net_income, color=[UP if v >= 0 else DOWN for v in sens.delta_net_income])
    for i, (v, c) in enumerate(zip(sens.delta_net_income, sens.delta_closing_cash)):
        ax.text(v + (3000 if v >= 0 else -3000), i, f"NI {v / 1000:+,.0f}K | cash {c / 1000:+,.0f}K", va="center", ha="left" if v >= 0 else "right", fontsize=7.5)
    ax.axvline(0, color="#999", lw=.8)
    ax.set_title("Scenario impact on 12-month net income vs Base (label adds closing-cash impact)")
    cad(ax, axis="x", k=True)
    ax.set_xlim(sens.delta_net_income.min() * 1.9, sens.delta_net_income.max() * 1.9)
    save(f, "R10_scenarios")


# ----------------------------------------------------------------------------------------------- shared content
def ctx():
    E = json.loads((TABLES / "findings.json").read_text())
    MR = json.loads((TABLES / "model_results.json").read_text())
    return dict(K=E["metrics"], F=E["findings"], MR=MR, rec=t("recommendations"), ann=t("fin_ratios_annual", index_col=0), is_y=stmt("income_statement_annual"),
                bs_y=stmt("balance_sheet_annual"), cf_y=stmt("cash_flow_annual"), cs_y=stmt("common_size_annual"), sm=t("fin_forecast_scenario_summary", index_col=0),
                checks=t("fin_validation_checks"), dq=t("data_validation_checks"), src=pd.read_csv(TABLES.parents[1] / "data/external/processed/sources_register.csv"),
                fmc=t("forecast_model_comparison"), dme=t("delay_model_evaluation"), cme=t("conversion_model_evaluation"),
                xl=json.loads((TABLES / "fin_excel_verification.json").read_text()))


def cover(title, sub, kind="Demonstration"):
    return f"""<section class='cover'><div class='brandmark'>VISIVAULT ANALYTICS</div>
<h1 style='margin-top:38mm'>{esc(title)}</h1><div class='sub'>{esc(sub)}</div>
<div class='badge'>⚠ {esc(SYNTHETIC_LABEL)}</div>
<div class='meta'>{esc(ATTRIBUTION)} · October 2026 · {esc(kind)}<br>Prairie Home Furnishings is a FICTIONAL Calgary furniture retailer. Product categories, manufacturers and
CAD list prices reflect a public Calgary furniture catalogue (retrieved {RETRIEVAL_DATE}); every order, cost, customer and financial figure is synthetic.
No relationship with or endorsement by any real company is implied.</div></section>"""


def statement_html(df, labels, keys, cols, names):
    x = df.loc[keys, cols].copy()
    x.columns = names
    x.index = [labels[k] for k in keys]
    x = x.reset_index().rename(columns={"index": "CAD"})
    return tbl(x, fmt={c: acct for c in names})


def model_rows(c):
    f = c["fmc"][c["fmc"].target == "net_sales"][["model", "WAPE_holdout", "WAPE_mean_all_origins", "bias_pct_holdout", "PI80_coverage_mean"]]
    return tbl(f, fmt={"WAPE_holdout": lambda v: f"{v:.1%}", "WAPE_mean_all_origins": lambda v: f"{v:.1%}", "bias_pct_holdout": lambda v: f"{v:+.1f}%", "PI80_coverage_mean": lambda v: f"{v:.0%}"})


def exec_report(c):
    K, F, rec, ann, is_y, sm = c["K"], c["F"], c["rec"], c["ann"], c["is_y"], c["sm"]
    ttm = stmt("income_statement_monthly")
    tcols = [x for x in ttm.columns if x >= "2025-10"]
    T = ttm[tcols].sum(axis=1)
    rec_rows = "".join(f"<tr><td><b>{r.rank}</b></td><td><b>{esc(r.area)}</b><br>{esc(r.title)}</td><td style='text-align:right'>{money(r.pretax_profit_impact_12m)}</td>"
                       f"<td style='text-align:right'>{money(r.cash_impact_12m)}</td><td>{esc(r.effort)} / {esc(r.timeframe)}</td></tr>" for r in rec.itertuples())
    rec_det = "".join(f"<h3>{r.rank}. {esc(r.title)}</h3><p><b>Estimate:</b> pre-tax {money(r.pretax_profit_impact_12m)}, cash {money(r.cash_impact_12m)} (12 months). "
                      f"<b>How calculated:</b> {esc(r.methodology)} <b>Assumptions:</b> {esc(r.assumptions)} <b>KPIs:</b> {esc(r.kpis)}</p>" for r in rec.itertuples())
    caps = [("Sales & product profitability", "Bookings vs revenue, category/manufacturer margins, promotion lift, associate performance, cross-sell pairs"),
            ("Inventory intelligence", "ABC, FIFO aging, overstock, stockouts, service-level reorder points and safety stock, supplier lead-time monitoring"),
            ("Custom orders & fulfilment", "Open-order tracker with supplier ETA, deposits, balances, aging and model-scored delay risk; pickup-slot and carrier analytics"),
            ("Customers & design consultations", "Low-frequency RFM segments, cohort retention, 5-year value, consult conversion by designer/follow-up, pipeline forecast"),
            ("Financial intelligence", "Double-entry ledger, monthly/annual statements, common-size and ratios, integrated 12-month forecast, Excel model with scenarios")]
    cap_html = tbl(pd.DataFrame(caps, columns=["Module", "What management sees"]))
    body = cover("Prairie Home Furnishings: Retail, Inventory & Financial Intelligence", "Executive management report - what a furniture retailer can learn from its own data", "Executive report") + f"""
<h2>Important notice</h2><div class='warn'>This report analyses a <b>fictional</b> retailer built on synthetic data to demonstrate VisiVault Analytics' capabilities.
None of the figures describe any real company. The analyses are designed to complement - not replace - a retailer's existing POS, ERP,
accounting, CRM and e-commerce systems.</div>
<h2>1. Executive summary</h2>
<div class='kpis'>
<div class='kpi'><div class='l'>Written sales (TTM)</div><div class='v'>{money(K['ttm_net_sales'])}</div><div class='s'>{K['ttm_growth']:+.1%} vs prior 12 months</div></div>
<div class='kpi'><div class='l'>EBITDA (TTM)</div><div class='v'>{money(T['ebitda'])}</div><div class='s'>{T['ebitda'] / T['net_rev']:.1%} of net revenue</div></div>
<div class='kpi'><div class='l'>Open orders</div><div class='v'>{K['open_orders']:.0f}</div><div class='s'>{money(K['deposits_held'])} deposits held</div></div>
<div class='kpi'><div class='l'>Custom ready on time</div><div class='v'>{K['custom_on_time']:.0%}</div><div class='s'>vs promised date</div></div>
<div class='kpi'><div class='l'>Consult conversion</div><div class='v'>{K['consult_conv']:.0%}</div><div class='s'>AOV {money(K['aov_consult'])} vs {money(K['aov_other'])}</div></div>
<div class='kpi'><div class='l'>Aged stock &gt;180 d</div><div class='v'>{money(K['aged_180'])}</div><div class='s'>{K['overstock_n']:.0f} overstocked SKUs</div></div>
<div class='kpi'><div class='l'>Stockout sales lost</div><div class='v'>{money(K['lost_sales_ttm'])}</div><div class='s'>trailing 12 months, estimated</div></div>
<div class='kpi'><div class='l'>Base forecast net income</div><div class='v'>{money(sm.at['Base', 'net_income'])}</div><div class='s'>Oct-26 to Sep-27 (FORECAST)</div></div></div>
<ul><li>{esc(F['sales'])}</li><li>{esc(F['custom'])}</li><li>{esc(F['orders'])}</li><li>{esc(F['fulfilment'])}</li><li>{esc(F['consults'])}</li><li>{esc(F['inventory'])}</li></ul>
<h2>2. What the platform covers</h2>{cap_html}
<h2 class='pb'>3. Sales and product profitability</h2>{img('R01_bookings_vs_revenue')}{img('R02_category_sales_margin')}
<p>{esc(F['promotions'])} {esc(F['cross_sell'])} {esc(F['reps'])}</p>
<h2 class='pb'>4. Inventory intelligence</h2>{img('R03_inventory_aging')}<p>{esc(F['inventory'])} {esc(F['stockouts'])}</p>
<h2>5. Custom orders, suppliers and fulfilment</h2>{img('R04_supplier_on_time')}{img('R05_open_order_backlog')}<p>{esc(F['suppliers'])} {esc(F['fulfilment'])}</p>
<h2 class='pb'>6. Customers and design consultations</h2>{img('R06_consultations')}<p>{esc(F['customers'])} {esc(F['consults'])}</p>
<h2>7. Financial performance</h2>
{statement_html(is_y, S.IS_LABEL, ['gross_sales', 'discounts', 'returns', 'net_sales', 'net_rev', 'cogs', 'gross_profit', 'opex', 'ebitda', 'da', 'interest', 'tax', 'net_income'],
                list(is_y.columns), ['FY2024', 'FY2025', 'YTD Sep-2026'])}
{img('R07_profit_cash_ttm')}{img('R08_inventory_vs_deposits')}
<p>Customer deposits fund roughly {ann.at['deposit_funding', 'TTM Sep-2026']:.0%} of inventory, so the effective cash conversion cycle falls from {ann.at['ccc', 'TTM Sep-2026']:.0f} days to
{ann.at['ccc_after_deposits', 'TTM Sep-2026']:.0f} days after deposits. The business holds more cash than it needs - an opportunity to repay debt or invest.</p>
<h2 class='pb'>8. Forecasts and scenarios (FORECAST)</h2>{img('R09_sales_forecast')}{model_rows(c)}
<p class='small'>Accuracy is measured on synthetic data with time-based backtests (holdout Jan-Sep 2026 plus rolling origins); it is not evidence of accuracy on any real retailer's data.</p>
{img('R10_scenarios')}
<h2 class='pb'>9. Recommendations</h2>
<table><thead><tr><th>#</th><th>Area / action</th><th>Pre-tax, 12m</th><th>Cash, 12m</th><th>Effort / timing</th></tr></thead><tbody>{rec_rows}</tbody></table>{rec_det}
<h2>10. Data limitations</h2><ul><li>All operational and financial records are synthetic; behaviour (seasonality, delays, conversion, margins) follows documented assumptions, so findings
illustrate methods, not facts about any real retailer.</li><li>Only product names, manufacturers, list prices and published policies (pickup slots, deposits-before-pickup, returns,
custom-order terms, delivery paid to carriers, free design consults, financing) come from public sources.</li><li>Models were trained on 33 months of synthetic history; monthly sales
models have ~21 training months before the holdout.</li></ul>
<p class='small'>{esc(ATTRIBUTION)} · {esc(CONTACT)} · {esc(SYNTHETIC_LABEL)}</p>"""
    return page("Prairie Home Furnishings - Executive Management Report", body)


def financial_report(c):
    is_y, bs_y, cf_y, cs_y, ann, sm, ch, xl = c["is_y"], c["bs_y"], c["cf_y"], c["cs_y"], c["ann"], c["sm"], c["checks"], c["xl"]
    yrs = list(is_y.columns)
    names = ["FY2024", "FY2025", "YTD Sep-2026"]
    ratio_t = ann[["ratio", "FY2024", "FY2025", "TTM Sep-2026", "direction", "management_action"]].copy()
    ratio_html = tbl(ratio_t, fmt={k: (lambda v: f"{v:,.2f}" if abs(v) < 1e4 else f"{v:,.0f}") for k in ["FY2024", "FY2025", "TTM Sep-2026"]})
    cs = cs_y.loc[["net_sales", "cogs", "gross_profit", "emp_comp", "occupancy", "marketing", "g_and_a", "warehouse", "fees", "ebitda", "net_income"]]
    cs.index = [S.IS_LABEL[k] for k in cs.index]
    cs_html = tbl(cs.reset_index().rename(columns={"index": "% of net revenue"}), fmt={k: (lambda v: f"{v:.1f}%") for k in cs.columns})
    sc = sm.loc[["Conservative", "Base", "Optimistic"], ["net_revenue", "gross_profit", "ebitda", "net_income", "cfo", "closing_cash", "closing_working_capital", "closing_deposits"]].T
    sc_html = tbl(sc.reset_index().rename(columns={"index": "12 months to Sep-2027 (FORECAST)"}), fmt={k: acct for k in sc.columns})
    chk = tbl(ch[["check_no", "check", "result", "detail"]].rename(columns={"check_no": "#"}))
    policies = [("Revenue", "Recognised at hand-off (store pickup or loading to the customer's carrier); orders and deposits before that are contract liabilities."),
                ("Customer deposits", "50% on custom, special and scheduled in-stock orders (30% for trade); balance due before pickup; held gross of GST until applied."),
                ("Delivery", "Third-party delivery is booked and paid by the customer directly - not revenue. Flat-rate delivery collected for a partner carrier is an agent liability."),
                ("Protection plans", "Sold as agent; only the retailer's 40% commission is revenue, the remainder is remitted to the insurer."),
                ("Cancellations & returns", "Custom orders in production retain a 25% cancellation fee; in-stock returns within 3 days carry a 15% restocking fee."),
                ("Inventory", "Perpetual at purchase cost; stocked goods (1200) and goods allocated to customer orders (1210) shown separately."),
                ("Tax", "GST 5%, quarterly; income tax 11% small-business rate on the first $500K, 23% above, YTD true-up; prior year paid 31 March."),
                ("Opening position", "Explicit 31-Dec-2023 balances (cash, assets, inventory, deposits, payables, debt, share capital); opening retained earnings is the documented residual.")]
    body = cover("Prairie Home Furnishings: Financial Performance Analysis", "Integrated three-statement model, ratio analysis, forecast and validation", "Financial analysis") + f"""
<h2>Basis of preparation</h2><div class='warn'>Simulated accounts of a fictional retailer, generated by double-entry accounting from synthetic operational data.</div>
{tbl(pd.DataFrame(policies, columns=['Policy', 'Treatment']))}
<h2 class='pb'>Income statement (CAD)</h2>{statement_html(is_y, S.IS_LABEL, [k for k, *_ in S.IS_LINES], yrs, names)}
<h3>Common-size (% of total net revenue)</h3>{cs_html}
<h2 class='pb'>Balance sheet (CAD)</h2>{statement_html(bs_y, S.BS_LABEL, [k for k, *_ in S.BS_LINES if k != 'check'], yrs, ['31-Dec-2024', '31-Dec-2025', '30-Sep-2026'])}
<h2 class='pb'>Cash flow statement - indirect (CAD)</h2>{statement_html(cf_y, S.CF_LABEL, [k for k, *_ in S.CF_LINES if k not in ('bs_cash', 'check')], yrs, names)}
{img('R08_inventory_vs_deposits')}
<h2 class='pb'>Ratio analysis</h2>{ratio_html}
<h2 class='pb'>12-month forecast and scenarios (FORECAST)</h2>{sc_html}{img('R10_scenarios')}
<p>The integrated Excel model (<i>Prairie_Home_Integrated_Financial_Model.xlsx</i>) recalculates all three statements when assumptions change. Excel's own recalculation of
{esc(xl.get('cases', ''))} matched the Python engine to within ${xl.get('max_diff', 0):.6f}.</p>
<h2 class='pb'>Validation</h2>{chk}
<p class='small'>{esc(ATTRIBUTION)} · {esc(SYNTHETIC_LABEL)}</p>"""
    return page("Prairie Home Furnishings - Financial Performance Analysis", body)


def demo_guide(c):
    K = c["K"]
    steps = [("Executive Overview", "Start here: bookings vs recognised revenue, open orders and deposits, headline findings and ranked actions."),
             ("Sales Performance / Product Profitability", "Filter by date, category and channel; show promotion lift and the custom vs ready-made margin trade-off; open the cross-sell table."),
             ("Inventory Intelligence", "Filter to ABC class A and action 'Reorder now'; then show aged stock and the clearance list."),
             ("Custom Order Tracking", "Tick 'Only past promised date' - the tracker lists each late order with deposit, balance, supplier ETA and model delay risk."),
             ("Supplier & Fulfillment", "Show the weakest suppliers' on-time %, the Saturday pickup-slot crunch and why third-party delivery is not revenue."),
             ("Customer Intelligence / Design Consultations", f"Explain low repeat rates in furniture; show the follow-up effect on conversion ({K['fu0']:.0f}% vs {K['fu2']:.0f}%) and the open-quote pipeline."),
             ("Income Statement / Balance Sheet / Cash Flow / Ratios", "Show revenue recognised at hand-off, deposits as a liability, the cash bridge and the cash conversion cycle after deposits."),
             ("Forecasting / Scenario Simulator", "Move the sliders (volume, margin, supplier delays, payment terms) and watch revenue, profit, cash and working capital update together."),
             ("Excel model", "Open Prairie_Home_Integrated_Financial_Model.xlsx, change Assumptions!C4 to Optimistic and show the Checks sheet staying TRUE.")]
    body = f"""<h1>{esc(APP_NAME)} - Demonstration guide</h1><p class='small'>{esc(ATTRIBUTION)} · 20-minute walkthrough for a furniture retailer's management team</p>
<div class='warn'>{esc(SYNTHETIC_LABEL)} Prairie Home Furnishings is fictional; say so at the start of every demo.</div>
<h2>Before the meeting</h2><ul><li>Open the dashboard ({esc(DEMO_URL)} or locally: <code>.venv/bin/streamlit run dashboard/app.py</code>).</li>
<li>Have the Excel model and the executive report PDF ready to share.</li><li>Ask which systems they already use (POS/ERP, accounting, e-commerce, CRM) - the pilot reads from them; it replaces nothing.</li></ul>
<h2>Walkthrough</h2>{tbl(pd.DataFrame(steps, columns=['Page', 'What to show']))}
<h2>Questions to ask</h2><ul><li>How are deposits, balances and supplier ETAs tracked today, and who chases late orders?</li><li>Which reports does management review monthly, and how long do they take to produce?</li>
<li>Where is stock aging or clearance decided?</li><li>How are design consultations followed up and measured?</li></ul>
<h2>Close</h2><p>Propose the 90-day pilot (sales & product profitability, inventory aging & reorder intelligence, cash flow & financial reporting) with read-only data access.</p>"""
    return page("Prairie Home Furnishings - Demonstration guide", body)


CONTACT = "Antoine Matemane Mahirwe, PhD - Founder & Chief Data Strategist, VisiVault Analytics Ltd. - visivault@visivaultanalytics.com - www.visivaultanalytics.com"
INVEST = [("1. Diagnostic (2 weeks)", "Data-access review, policy confirmation, data-quality report, opportunity sizing on your data", "2,500 fixed"),
          ("2. Pilot (90 days)", "Three phase-1 modules on your data, monthly management pack, reorder/clearance lists, 13-week cash forecast", "14,500 fixed, in 3 milestones"),
          ("3. Ongoing support (optional)", "Monthly refresh, management pack and analyst support; phase-2 modules quoted separately", "1,250 - 2,500 per month")]
PHASE1 = [("Sales & product profitability", "Monthly/category/manufacturer sales and margin, discount and promotion effectiveness, associate performance, custom vs ready-made margin",
           "POS / order-system sales lines (12-24 months), product master with costs, promotion calendar"),
          ("Inventory aging & reorder intelligence", "ABC, FIFO aging, overstock and clearance list, service-level reorder points and safety stock, supplier lead-time scorecard",
           "Inventory movement or month-end on-hand history, purchase orders with order/expected/received dates, supplier list"),
          ("Cash flow & financial reporting", "Monthly income statement, balance sheet and cash flow from the existing trial balance; deposits, backlog and 13-week cash forecast; ratio pack",
           "Monthly trial balance / GL export, open-order & deposit register, AP/AR ageing")]
PHASE2 = [("Customer conversion", "Design-consultation conversion, follow-up cadence, RFM segments, marketing attribution, lead pipeline forecast", "Consult/quote log, CRM or lead data, marketing spend"),
          ("Order fulfilment", "Open-order tracker with delay-risk scoring, pickup-slot and carrier analytics, cancellation drivers", "Order status history, pickup bookings, carrier hand-offs")]


def proposal(c):
    body = cover("Pilot proposal: retail and financial intelligence for a furniture retailer", "A limited-scope pilot that works alongside your existing systems", "Proposal") + f"""
<h2>Purpose</h2><p>VisiVault Analytics proposes a limited-scope pilot that connects to the systems the retailer already uses (point of sale / order management, accounting,
e-commerce) to deliver three management views: sales and product profitability, inventory aging and reorder intelligence, and cash flow and financial reporting.
We do not assume any gap in your current technology; the pilot adds analysis on top of it. The accompanying demonstration uses a fictional retailer and synthetic data;
no figure in it describes the retailer.</p>
<h2>Phase 1 - pilot (90 days)</h2>{tbl(pd.DataFrame(PHASE1, columns=['Module', 'Deliverables', 'Information required']))}
<h2>Phase 2 - optional, after the pilot</h2>{tbl(pd.DataFrame(PHASE2, columns=['Module', 'Deliverables', 'Information required']))}
<h2>Minimum information from management</h2><ul><li>Read-only exports (CSV/Excel or API) of the items above; we can work from scheduled exports if direct access is not preferred.</li>
<li>A named contact for data questions (2-3 hours per week) and a monthly 60-minute review with the owners/management.</li><li>Confirmation of costing method, deposit policy and
how custom orders are recorded, so revenue and deposits are treated exactly as in your books.</li></ul>
<h2>Assumptions</h2><ul><li>Data stays in Canada and is handled under PIPEDA / Alberta PIPA; customer personal information is excluded or pseudonymised.</li>
<li>The pilot is read-only - no changes to your POS, ERP or accounting system.</li><li>Amounts are in CAD and exclude GST; final scope is confirmed in the diagnostic.</li></ul>
<h2>Investment</h2>{tbl(pd.DataFrame(INVEST, columns=['Stage', 'Scope', 'Investment (CAD, excl. GST)']))}
<h2>Success measures (agreed at kickoff)</h2><ul><li>Monthly management pack produced from your data within 5 business days of month end.</li>
<li>Reorder and clearance lists accepted by the buyer for at least two cycles; aged (&gt;180 day) stock value tracked down month over month.</li>
<li>Cash and deposit position reconciled to the trial balance every month (zero unexplained differences).</li><li>Management rates the pack useful for decisions (survey at day 90).</li></ul>
<p style='margin-top:10px'><b>Contact:</b> {esc(CONTACT)}</p>"""
    return page("VisiVault - Pilot proposal", body)


def pilot_plan(c):
    weeks = [("Weeks 1-2", "Kickoff & data access", "Confirm systems, exports and policies (revenue, deposits, costing); data-sharing agreement; success measures signed off"),
             ("Weeks 3-4", "Data model & validation", "Load sales, product, inventory, PO and trial-balance exports; automated reconciliation checks; data-quality report"),
             ("Weeks 5-7", "Module 1 - sales & product profitability", "Dashboard pages, margin and promotion analysis, first management review"),
             ("Weeks 6-9", "Module 2 - inventory intelligence", "ABC, aging, reorder points and safety stock, supplier scorecard; buyer workshop; first reorder/clearance lists"),
             ("Weeks 8-11", "Module 3 - cash flow & financial reporting", "Monthly statements from the trial balance, deposits & backlog view, 13-week cash forecast, ratio pack"),
             ("Week 12", "Month-end pack & handover", "Produce a full month-end pack, review results against success measures, training, recommendation for phase 2"),
             ("Week 13", "Pilot close-out", "Pilot report: value delivered, data gaps, options and costs for ongoing support and phase 2 modules")]
    raci = [("Data exports", "Retailer IT / admin", "VisiVault"), ("Policy confirmation (revenue, deposits, costing)", "Retailer finance", "VisiVault"),
            ("Dashboards, models, reconciliations", "VisiVault", "Retailer management"), ("Buyer workshop & reorder acceptance", "Retailer purchasing", "VisiVault"),
            ("Monthly review", "Owners / management", "VisiVault")]
    body = f"""<h1>90-day pilot implementation plan</h1><p class='small'>{esc(ATTRIBUTION)} · Retail and financial intelligence pilot · October 2026</p>
<div class='warn'>Plan for a pilot using the retailer's own data. The demonstration that accompanies it uses a fictional retailer and synthetic data.</div>
<h2>Timeline</h2>{tbl(pd.DataFrame(weeks, columns=['When', 'Workstream', 'Activities & outputs']))}
<h2>Responsibilities</h2>{tbl(pd.DataFrame(raci, columns=['Activity', 'Owner', 'Support']))}
<h2>Deliverables at day 90</h2><ul><li>Live dashboard on the retailer's data (sales, product profitability, inventory, financial statements, cash).</li><li>Month-end management pack and
13-week cash forecast template.</li><li>Reorder-point, safety-stock and clearance lists with a supplier lead-time scorecard.</li><li>Data dictionary, reconciliation log and runbook.</li></ul>
<h2>Risks & mitigations</h2><ul><li>Data export gaps - start from monthly exports; automate later.</li><li>Policy differences (e.g., deposit or revenue timing) - confirm in week 1 and mirror
the books exactly.</li><li>Staff time - limit to 2-3 hours per week from one contact.</li></ul>
<h2>Phase 2 options</h2><p>Customer conversion (design consultations, follow-up, attribution) and order fulfilment (delay-risk scoring, pickup and carrier analytics).</p>"""
    return page("VisiVault - 90-day pilot plan", body)


def _label_check():
    from src.config import OUT
    from src.finance.validation import label_audit
    ok, detail = label_audit(OUT)
    ch = t("fin_validation_checks")
    ch.loc[ch.check_no == 11, ["result", "detail"]] = ["PASS" if ok else "FAIL", detail]
    ch.to_csv(TABLES / "fin_validation_checks.csv", index=False)
    return ok


def run():
    charts()
    _label_check()
    c = ctx()
    docs = {"Prairie_Home_Executive_Management_Report": exec_report(c), "Prairie_Home_Financial_Performance_Analysis": financial_report(c),
            "Prairie_Home_Demonstration_Guide": demo_guide(c), "VisiVault_Pilot_Proposal": proposal(c), "VisiVault_90_Day_Pilot_Plan": pilot_plan(c)}
    out = {}
    for name, h in docs.items():
        hp = REPORTS / f"{name}.html"
        hp.write_text(h, encoding="utf-8")
        out[name] = render_pdf(hp, REPORTS / f"{name}.pdf")
    out["labels_ok"] = _label_check()                    # re-audit including the reports just written
    return out


if __name__ == "__main__":
    print(run())
