"""Model E + Phase 9: integrated, driver-based 12-month financial forecast (Oct-2026 to Sep-2027) and scenario engine.

Single source of truth: each line is ONE formula template (ROWS) that is evaluated in Python AND written into the
Excel model as a live formula. Tokens: {key} this month | {key[-k]} k months earlier (t=0 = actual 30-Sep-2026
opening; before that = 0) | {key[+k]} k months later (wraps to the start of the horizon as a seasonal proxy) |
{$name} active scenario assumption.

Furniture-specific mechanics (explicit drivers, no growth plugs):
  bookings (written sales, Model A forecast) -> revenue recognised at hand-off via a historical lag profile;
  the opening order backlog releases on its own schedule (expected ready dates of open orders);
  customer deposits = deposit ratio x open backlog; customer-allocated inventory moves with deposits;
  stocked inventory = cover policy x forward COGS; supplier credit (DPO), GST and income-tax timing; debt terms;
  revolver cash-band rule; year-end dividend at 50% of net income.
All values are SIMULATED.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from src.config import END, TABLES
from src.finance import policy as P
from src.finance.ledger import fixed_asset_schedule, prime_rate
from src.finance.statements import MONTHS

H = 12
FC_MONTHS = pd.period_range("2026-10", periods=H, freq="M")
TTM = pd.period_range("2025-10", END, freq="M")


@dataclass
class Scenario:
    volume_change: float = 0.0          # sales volume vs Model A base forecast (+0.05 = +5%)
    margin_pts: float = 0.0             # gross-margin improvement, fraction of net sales (+0.02 = +2 pts)
    slow_reduction: float = 0.0         # share of slow-moving (overstock) inventory cleared (+0.10 = 10%)
    delay_reduction: float = 0.0        # reduction in supplier delays (+0.15 = 15% fewer late weeks)
    consult_conv_change: float = 0.0    # relative change in design-consultation conversion (+0.10 = +10%)
    dpo_change_days: float = 0.0        # change in supplier payment days
    opex_change: float = 0.0            # change in controllable operating expenses (+0.05 = +5%)
    discount_change: float = 0.0        # change in promotional discount rate (fraction of gross sales)
    rate_change: float = 0.0            # change in prime rate


SCENARIOS = {
    "Conservative": Scenario(volume_change=-0.07, margin_pts=-0.01, delay_reduction=-0.15, dpo_change_days=-5, opex_change=0.02, discount_change=0.01, rate_change=0.005),
    "Base": Scenario(),
    "Optimistic": Scenario(volume_change=0.05, margin_pts=0.02, slow_reduction=0.10, delay_reduction=0.15, consult_conv_change=0.10, dpo_change_days=5),
}
SCENARIO_NOTES = {
    "Conservative": "Bookings -7%, gross margin -1 pt, supplier delays 15% worse, suppliers shorten terms by 5 days, opex +2%, +1 pt promotional discounting, prime +50 bps.",
    "Base": "Model A booking forecast, TTM margins, recognition lags, deposit and working-capital ratios, current staffing and lease, prime flat.",
    "Optimistic": "Bookings +5%, gross margin +2 pts, 10% of slow-moving stock cleared, supplier delays -15%, consultation conversion +10%, +5 supplier days.",
}
SCENARIO_FIELDS = [("volume_change", "Sales volume change", "%"), ("margin_pts", "Gross-margin improvement", "pts"), ("slow_reduction", "Slow-moving inventory reduction", "%"),
                   ("delay_reduction", "Supplier-delay reduction", "%"), ("consult_conv_change", "Design-consultation conversion change", "%"),
                   ("dpo_change_days", "Change in supplier payment days", "days"), ("opex_change", "Change in controllable operating expenses", "%"),
                   ("discount_change", "Change in promotional discount rate", "pts"), ("rate_change", "Change in prime rate", "%")]
SENSITIVITIES = [  # spec scenarios: label, field, value
    ("5% sales volume increase", "volume_change", 0.05), ("2-pt gross-margin improvement", "margin_pts", 0.02),
    ("10% reduction in slow-moving inventory", "slow_reduction", 0.10), ("15% reduction in supplier delays", "delay_reduction", 0.15),
    ("10% increase in design-consultation conversion", "consult_conv_change", 0.10), ("Supplier terms +10 days", "dpo_change_days", 10.0),
    ("Supplier terms -10 days", "dpo_change_days", -10.0), ("Operating expenses -5%", "opex_change", -0.05), ("Operating expenses +5%", "opex_change", 0.05),
    ("Promotional discounts +2 pts", "discount_change", 0.02), ("Promotional discounts -2 pts", "discount_change", -0.02), ("Prime rate +100 bps", "rate_change", 0.01),
]
FIXED_LABELS = {
    "w0": "Share of bookings handed off in the booking month", "w1": "... 1 month later", "w2": "... 2 months later", "w3": "... 3 months later", "w4": "... 4+ months later",
    "cancel_rate": "Bookings cancelled before hand-off (TTM)", "consult_share": "Share of bookings from design consultations", "disc_rate": "Discount rate (share of gross sales)",
    "return_rate": "Returns (share of net sales)", "other_rev_rate": "Plan commissions, restocking & cancellation fees (share of net sales)",
    "cogs_ratio": "Merchandise COGS / net furniture sales (TTM)", "freight_ratio": "Freight-in / merchandise COGS", "var_ratio": "Inventory variances / merchandise COGS",
    "stock_share": "Share of COGS from stocked goods", "commission_rate": "Commission on bookings", "marketing_rate": "Marketing / prior-month bookings",
    "fee_rate": "Card & financing fees / net revenue", "dep_ratio": "Customer deposits / open backlog incl. GST", "alloc_ratio": "Allocated inventory / customer deposits",
    "ar_ratio": "Receivables, months of net revenue", "dpo_base": "Supplier payment days (TTM)", "vendor_ap_ratio": "Vendor payables, months of vendor opex",
    "agent_ratio": "Agent liabilities / net furniture sales", "accrued_ratio": "Accrued payroll, months of payroll", "gst": "GST rate", "prime": "Prime rate",
    "term_spread": "Term-loan spread", "rev_spread": "Revolver spread", "rev_limit": "Revolver limit", "min_cash": "Minimum month-end cash", "target_cash": "Target cash after draw",
    "repay_above": "Repay revolver above", "step": "Draw/repay increment", "term_pmt": "Term-loan principal / month", "payout": "Dividend payout ratio",
    "cash_floor": "Cash floor after dividend", "slow_value": "Slow-moving (>180 days cover) stock at 30-Sep-2026", "markdown_rate": "Markdown loss on cleared stock",
    "new_capex_life": "Useful life of new capex (months)", "tax_small": "Small-business tax rate", "tax_general": "General tax rate", "sbd_limit": "Small-business limit",
}

ROWS = [  # key, label, section, template, phase (s = static row-by-row, d = dynamic month-by-month)
    ("bookings", "Bookings - written net sales (Model A x scenario)", "Revenue build",
     "{bookings_base}*(1+{$volume_change})*(1+{$consult_share}*{$consult_conv_change})*(1-{$discount_change}/(1-{$disc_rate}))", "s"),
    ("w1e", "Lag weight 1 month (delay-adjusted)", "Revenue build", "{$w1}+{$delay_reduction}*{$w2}", "s"),
    ("w2e", "Lag weight 2 months (delay-adjusted)", "Revenue build", "{$w2}*(1-{$delay_reduction})+{$delay_reduction}*{$w3}", "s"),
    ("w3e", "Lag weight 3 months (delay-adjusted)", "Revenue build", "{$w3}*(1-{$delay_reduction})+{$delay_reduction}*{$w4}", "s"),
    ("w4e", "Lag weight 4+ months (delay-adjusted)", "Revenue build", "{$w4}*(1-{$delay_reduction})", "s"),
    ("cancel_eff", "Cancellation rate (falls with fewer delays)", "Revenue build", "{$cancel_rate}*(1-0.6*{$delay_reduction})", "s"),
    ("net_sales", "Net furniture sales (recognised at hand-off)", "Income statement",
     "({backlog_release}+{$w0}*{bookings}+{w1e}*{bookings[-1]}+{w2e}*{bookings[-2]}+{w3e}*{bookings[-3]}+{w4e}*{bookings[-4]})*(1-{cancel_eff})", "s"),
    ("gross_sales", "Gross furniture sales", "Income statement", "{net_sales}/(1-{$disc_rate}-{$discount_change})/(1-{$return_rate})", "s"),
    ("discounts", "Less: discounts & promotional allowances", "Income statement", "-{gross_sales}*({$disc_rate}+{$discount_change})", "s"),
    ("returns", "Less: sales returns", "Income statement", "{net_sales}-{gross_sales}-{discounts}", "s"),
    ("other_rev", "Plan commissions, restocking & cancellation fees", "Income statement", "{$other_rev_rate}*{net_sales}", "s"),
    ("net_rev", "Total net revenue", "Income statement", "{net_sales}+{other_rev}", "s"),
    ("cogs_merch", "Cost of goods sold - merchandise", "Income statement", "-{net_sales}*({$cogs_ratio}-{$margin_pts})", "s"),
    ("freight_in", "Freight-in & supplier charges", "Income statement", "{cogs_merch}*{$freight_ratio}", "s"),
    ("inv_var", "Inventory variances & markdowns", "Income statement", "{cogs_merch}*{$var_ratio}-{is_m1}*{$slow_reduction}*{$slow_value}*{$markdown_rate}", "s"),
    ("cogs", "Cost of goods sold", "Income statement", "{cogs_merch}+{freight_in}+{inv_var}", "s"),
    ("gross_profit", "Gross profit", "Income statement", "{net_rev}+{cogs}", "s"),
    ("payroll", "Payroll (staffing plan + commissions)", "Opex build", "{payroll_base}*(1+{$opex_change})+{$commission_rate}*{bookings}", "s"),
    ("emp_comp", "Employee compensation", "Income statement", "-{payroll}", "s"),
    ("occupancy", "Occupancy (lease schedule, utilities)", "Income statement", "-{occupancy_d}", "s"),
    ("marketing", "Marketing & advertising", "Income statement", "-{$marketing_rate}*IF({is_m1},{bookings_hist_last},{bookings[-1]})*(1+{$opex_change})", "s"),
    ("g_and_a", "General & administrative", "Income statement", "-{ga_d}*(1+{$opex_change})", "s"),
    ("warehouse", "Warehouse, fulfilment & design-consult costs", "Income statement", "-{warehouse_d}*(1+{$opex_change})", "s"),
    ("fees", "Card & financing-partner fees", "Income statement", "-{$fee_rate}*{net_rev}", "s"),
    ("opex", "Operating expenses (before depreciation)", "Income statement", "{emp_comp}+{occupancy}+{marketing}+{g_and_a}+{warehouse}+{fees}", "s"),
    ("ebitda", "EBITDA", "Income statement", "{gross_profit}+{opex}", "s"),
    ("capex_cum", "Cumulative new capex (memo)", "Fixed assets", "{capex_cum[-1]}+{capex_d}", "s"),
    ("da", "Depreciation", "Income statement", "-({da_existing}+{capex_cum[-1]}/{$new_capex_life})", "s"),
    ("ebit", "Operating income (EBIT)", "Income statement", "{ebitda}+{da}", "s"),
    ("stock_target", "Stocked-inventory target (cover x forward COGS, less cleared slow stock)", "Inventory",
     "-{cover_k}*{$stock_share}*({cogs_merch[+1]}+{cogs_merch[+2]})/2-{$slow_reduction}*{$slow_value}", "s"),
    # ---- dynamic
    ("backlog", "Open order backlog (net, memo)", "Working capital", "{backlog[-1]}+{bookings}-{net_sales}/(1-{cancel_eff})", "d"),
    ("deposits", "Customer deposits (contract liabilities)", "Balance sheet", "{$dep_ratio}*{backlog}*(1+{$gst})", "d"),
    ("inv_alloc", "Inventory - allocated to customer orders", "Balance sheet", "{$alloc_ratio}*{deposits}", "d"),
    ("purchases", "Inventory purchases at cost", "Inventory",
     "MAX(0,{stock_target}-{inv_stock[-1]}+{inv_alloc}-{inv_alloc[-1]}-{cogs_merch}-{inv_var})", "d"),
    ("inv_stock", "Inventory - stocked merchandise", "Balance sheet",
     "{inv_stock[-1]}+{purchases}-({inv_alloc}-{inv_alloc[-1]})+{cogs_merch}+{inv_var}", "d"),
    ("interest", "Interest expense", "Income statement", "-({term_loan[-1]}*({$prime}+{$rate_change}+{$term_spread})+{revolver[-1]}*({$prime}+{$rate_change}+{$rev_spread}))/12", "d"),
    ("pbt", "Income before tax", "Income statement", "{ebit}+{interest}", "d"),
    ("ytd_pbt", "Fiscal YTD income before tax (memo)", "Tax", "IF({is_jan},0,{ytd_pbt[-1]})+{pbt}", "d"),
    ("lcf", "Loss carry-forward at 1 January (memo)", "Tax", "IF({is_jan},MAX(0,{lcf[-1]}-{ytd_pbt[-1]}),{lcf[-1]})", "d"),
    ("tax_ytd", "Fiscal YTD income tax (memo)", "Tax",
     "{$tax_small}*MIN(MAX(0,{ytd_pbt}-{lcf}),{$sbd_limit})+{$tax_general}*MAX(0,{ytd_pbt}-{lcf}-{$sbd_limit})", "d"),
    ("tax", "Income taxes", "Income statement", "-({tax_ytd}-IF({is_jan},0,{tax_ytd[-1]}))", "d"),
    ("net_income", "Net income", "Income statement", "{pbt}+{tax}", "d"),
    ("ytd_ni", "Fiscal YTD net income (memo)", "Tax", "IF({is_jan},0,{ytd_ni[-1]})+{net_income}", "d"),
    ("ar", "Receivables", "Balance sheet", "{$ar_ratio}*{net_rev}*(1+{$gst})", "d"),
    ("prepaid", "Prepaid expenses", "Balance sheet", "{prepaid[-1]}+{insurance_premium}-{insurance_exp}", "d"),
    ("gst_remit", "GST remitted for prior quarter (memo)", "Working capital", "IF({q_start},{gst_net[-1]},0)", "d"),
    ("gst_net", "Net GST payable / (recoverable) (memo)", "Working capital",
     "{gst_net[-1]}+{$gst}*({net_sales}-{purchases}*(1+{$freight_ratio})-{taxable_opex}-{capex_d})-{gst_remit}", "d"),
    ("ap", "Accounts payable", "Balance sheet", "({$dpo_base}+{$dpo_change_days})/30.4*{purchases}*(1+{$freight_ratio})*(1+{$gst})+{$vendor_ap_ratio}*{taxable_opex}*(1+{$gst})", "d"),
    ("accrued", "Accrued payroll & commissions", "Balance sheet", "{$accrued_ratio}*{payroll}", "d"),
    ("agent", "Amounts collected as agent", "Balance sheet", "{$agent_ratio}*{net_sales}", "d"),
    ("prior_tax", "Prior-year tax awaiting payment (memo)", "Tax", "IF({is_jan},{tax_ytd[-1]},IF({is_mar},0,{prior_tax[-1]}))", "d"),
    ("tax_paid", "Income tax paid (memo)", "Tax", "IF({is_mar},{prior_tax[-1]},0)", "d"),
    ("tax_payable", "Income taxes payable", "Balance sheet", "{tax_payable[-1]}-{tax}-{tax_paid}", "d"),
    ("ppe_gross", "Fixed assets at cost", "Balance sheet", "{ppe_gross[-1]}+{capex_d}", "d"),
    ("acc_dep", "Accumulated depreciation", "Balance sheet", "{acc_dep[-1]}+{da}", "d"),
    ("cf_ni", "Net income", "Cash flow", "{net_income}", "d"),
    ("cf_da", "Depreciation", "Cash flow", "-{da}", "d"),
    ("d_ar", "(Increase) decrease in receivables", "Cash flow", "{ar[-1]}-{ar}", "d"),
    ("d_inv", "Inventory investment: (increase) decrease in inventory", "Cash flow", "{inv_stock[-1]}+{inv_alloc[-1]}-{inv_stock}-{inv_alloc}", "d"),
    ("d_ap", "Increase (decrease) in accounts payable", "Cash flow", "{ap}-{ap[-1]}", "d"),
    ("d_deposits", "Increase (decrease) in customer deposits", "Cash flow", "{deposits}-{deposits[-1]}", "d"),
    ("d_other", "Other working capital (prepaid, accrued, agent, GST, tax)", "Cash flow",
     "{prepaid[-1]}-{prepaid}+{accrued}-{accrued[-1]}+{agent}-{agent[-1]}+{gst_net}-{gst_net[-1]}+{tax_payable}-{tax_payable[-1]}", "d"),
    ("cfo", "Net cash from operating activities", "Cash flow", "{cf_ni}+{cf_da}+{d_ar}+{d_inv}+{d_ap}+{d_deposits}+{d_other}", "d"),
    ("cfi", "Capital expenditures", "Cash flow", "-{capex_d}", "d"),
    ("term_repay", "Term-loan repayments", "Cash flow", "-MIN({$term_pmt},{term_loan[-1]})", "d"),
    ("pre_cash", "Cash before revolver (memo)", "Cash flow", "{cash[-1]}+{cfo}+{cfi}+{term_repay}", "d"),
    ("rev_draw", "Revolver draws", "Cash flow", "IF({pre_cash}<{$min_cash},MIN({$rev_limit}-{revolver[-1]},CEIL(MAX(0,{$target_cash}-{pre_cash}),{$step})),0)", "d"),
    ("rev_repay", "Revolver repayments", "Cash flow",
     "IF(({pre_cash}>{$repay_above})*({revolver[-1]}>0),-MIN({revolver[-1]},FLOOR(MAX(0,{pre_cash}-{$target_cash}),{$step})),0)", "d"),
    ("revolver", "Revolving line of credit", "Balance sheet", "{revolver[-1]}+{rev_draw}+{rev_repay}", "d"),
    ("dividends", "Dividends paid", "Cash flow",
     "IF({is_dec}*({revolver}<0.005),-FLOOR(MIN({$payout}*MAX(0,{ytd_ni}),MAX(0,{pre_cash}+{rev_draw}+{rev_repay}-{$cash_floor})),1000),0)", "d"),
    ("cff", "Net cash from (used in) financing activities", "Cash flow", "{term_repay}+{rev_draw}+{rev_repay}+{dividends}", "d"),
    ("net_change", "Net change in cash", "Cash flow", "{cfo}+{cfi}+{cff}", "d"),
    ("cash", "Cash", "Balance sheet", "{cash[-1]}+{net_change}", "d"),
    ("term_loan", "Term-loan balance (memo)", "Balance sheet", "{term_loan[-1]}+{term_repay}", "d"),
    ("share_capital", "Share capital", "Balance sheet", "{share_capital[-1]}", "d"),
    ("cpe", "Current-year earnings", "Balance sheet", "IF({is_dec},0,{cpe[-1]}+{net_income})", "d"),
    ("retained", "Retained earnings", "Balance sheet", "{retained[-1]}+IF({is_dec},{cpe[-1]}+{net_income},0)+{dividends}", "d"),
    ("gst_rec", "GST recoverable", "Balance sheet", "MAX(0,-{gst_net})", "d"),
    ("current_assets", "Total current assets", "Balance sheet", "{cash}+{ar}+{inv_stock}+{inv_alloc}+{prepaid}+{gst_rec}", "d"),
    ("ppe_net", "Net fixed assets", "Balance sheet", "{ppe_gross}+{acc_dep}", "d"),
    ("total_assets", "TOTAL ASSETS", "Balance sheet", "{current_assets}+{ppe_net}", "d"),
    ("gst_pay", "GST payable", "Balance sheet", "MAX(0,{gst_net})", "d"),
    ("term_current", "Current portion of term loan", "Balance sheet", "MIN({term_loan},12*{$term_pmt})", "d"),
    ("current_liabilities", "Total current liabilities", "Balance sheet", "{ap}+{accrued}+{deposits}+{agent}+{gst_pay}+{tax_payable}+{revolver}+{term_current}", "d"),
    ("term_lt", "Term loan (non-current)", "Balance sheet", "{term_loan}-{term_current}", "d"),
    ("total_liabilities", "TOTAL LIABILITIES", "Balance sheet", "{current_liabilities}+{term_lt}", "d"),
    ("total_equity", "TOTAL EQUITY", "Balance sheet", "{share_capital}+{retained}+{cpe}", "d"),
    ("total_le", "TOTAL LIABILITIES AND EQUITY", "Balance sheet", "{total_liabilities}+{total_equity}", "d"),
    ("working_capital", "Working capital (memo)", "Working capital", "{current_assets}-{current_liabilities}", "d"),
    ("check_bs", "Check: assets - liabilities - equity (must be 0)", "Checks", "{total_assets}-{total_le}", "d"),
    ("check_cash", "Check: ending cash - (opening cash + net change) (must be 0)", "Checks", "{cash}-{cash[-1]}-{net_change}", "d"),
]
ROW = {r[0]: r for r in ROWS}
DRIVER_ROWS = [("bookings_base", "Bookings - Model A forecast of written net sales"), ("backlog_release", "Opening backlog released (expected hand-off of open orders)"),
               ("payroll_base", "Payroll staffing plan (TTM same month +3%, excl. commission)"), ("occupancy_d", "Occupancy: lease schedule (+3% Jan) + utilities seasonal"),
               ("ga_d", "General & administrative (insurance, professional, IT)"), ("warehouse_d", "Warehouse, fulfilment & design-consult costs"),
               ("taxable_opex", "GST-taxable operating expenses (for ITCs and vendor payables)"), ("insurance_exp", "Insurance expense"),
               ("insurance_premium", "Insurance premium paid (January)"), ("capex_d", "Capital expenditure plan"), ("da_existing", "Depreciation - existing asset register"),
               ("cover_k", "Stocked inventory: months of forward cover (seasonal, from history)"), ("bookings_hist_last", "Bookings of the last actual month (Sep-2026)"),
               ("is_m1", "Flag: first forecast month"), ("is_jan", "Flag: January"), ("is_mar", "Flag: March"), ("is_dec", "Flag: December"), ("q_start", "Flag: first month of quarter")]
OPENING = {"backlog", "deposits", "inv_alloc", "inv_stock", "term_loan", "revolver", "ar", "prepaid", "gst_net", "ap", "accrued", "agent", "tax_payable", "ppe_gross", "acc_dep",
           "cash", "share_capital", "retained", "cpe", "ytd_pbt", "lcf", "tax_ytd", "prior_tax", "capex_cum", "ytd_ni"}
TOK = re.compile(r"\{(\$?)([a-z_0-9]+)(\[[+-]\d\]|@\d+)?\}")
ZERO = H + 1                    # index of a permanent zero (references before the opening month)


def _py(template):
    def sub(m):
        dollar, key, suf = m.groups()
        if dollar:
            return f"A['{key}']"
        if not suf:
            return f"V['{key}'][t]"
        if suf.startswith("@"):
            return f"V['{key}'][{int(suf[1:])}]"
        return f"V['{key}'][W(t{int(suf[1:-1]):+d})]"
    return TOK.sub(sub, template)


FUN = dict(IF=lambda c, a, b: a if c else b, MAX=max, MIN=min, CEIL=lambda x, s: math.ceil(round(x / s, 9)) * s,
           FLOOR=lambda x, s: math.floor(round(x / s, 9)) * s, W=lambda i: ZERO if i < 0 else (i if i <= H else i - H))
COMPILED = {k: compile(_py(tpl), k, "eval") for k, _, _, tpl, _ in ROWS}


def run(sc: Scenario, base: dict) -> pd.DataFrame:
    A = dict(base["A"])
    A.update({k: float(getattr(sc, k)) for k in sc.__dataclass_fields__})
    V = {k: [0.0] * (H + 2) for k, *_ in ROWS}
    for k in base["drivers"].index:
        V[k] = [0.0] + list(map(float, base["drivers"].loc[k].values)) + [0.0]
    for k, v in base["opening"].items():
        V[k][0] = float(v)
    ns = dict(FUN, A=A, V=V)
    for k, _, _, _, ph in ROWS:
        if ph == "s":
            for t in range(1, H + 1):
                ns["t"] = t
                V[k][t] = eval(COMPILED[k], ns)
    for t in range(1, H + 1):
        ns["t"] = t
        for k, _, _, _, ph in ROWS:
            if ph == "d":
                V[k][t] = eval(COMPILED[k], ns)
    out = pd.DataFrame({k: V[k][:H + 1] for k, *_ in ROWS}).T
    out.columns = ["2026-09 (actual)"] + [str(m) for m in FC_MONTHS]
    return out


def summary(f):
    x = f.iloc[:, 1:]
    return {"bookings": x.loc["bookings"].sum(), "net_revenue": x.loc["net_rev"].sum(), "gross_profit": x.loc["gross_profit"].sum(),
            "gross_margin_pct": x.loc["gross_profit"].sum() / x.loc["net_rev"].sum() * 100, "ebitda": x.loc["ebitda"].sum(), "net_income": x.loc["net_income"].sum(),
            "net_margin_pct": x.loc["net_income"].sum() / x.loc["net_rev"].sum() * 100, "cfo": x.loc["cfo"].sum(), "closing_cash": x.loc["cash"].iloc[-1],
            "min_cash": x.loc["cash"].min(), "peak_revolver": max(0.0, x.loc["revolver"].max()), "closing_deposits": x.loc["deposits"].iloc[-1],
            "closing_inventory": x.loc["inv_stock"].iloc[-1] + x.loc["inv_alloc"].iloc[-1], "closing_working_capital": x.loc["working_capital"].iloc[-1],
            "avg_working_capital": x.loc["working_capital"].mean(), "dividends": -x.loc["dividends"].sum(),
            "max_abs_bs_check": x.loc["check_bs"].abs().max(), "max_abs_cash_check": x.loc["check_cash"].abs().max()}


# ----------------------------------------------------------------------------------------------- calibration
def calibrate(L, St, K):
    T = L["T"]
    is_m, bal = St["is_m"], St["bal"]
    ttm = [str(m) for m in TTM]
    s, o = T["lines"], T["orders"]
    li = s[s.line_status != "Cancelled"].merge(o[["order_id", "order_date", "fulfilled_date", "status"]], on="order_id", suffixes=("", "_o"))
    coh = li[(li.order_date >= "2024-10-01") & (li.order_date <= "2025-09-30")]
    lag = ((coh.fulfilled_date_o.dt.to_period("M") - coh.order_date.dt.to_period("M")).apply(lambda x: x.n if pd.notna(x) else np.nan)).clip(upper=4)
    w = coh.groupby(lag).net_sales_cad.sum() / coh.net_sales_cad.sum()
    oo = o[(o.order_date >= "2024-10-01") & (o.order_date <= "2025-09-30")]
    A = {f"w{k}": float(w.get(float(k), 0.0)) for k in range(5)}
    tot = sum(A.values())
    A = {k: v / tot for k, v in A.items()}
    A["cancel_rate"] = float(oo[oo.status == "Cancelled"].net_order_value_cad.sum() / oo.net_order_value_cad.sum())
    st = s[(s.transaction_date >= "2025-10-01") & (s.line_status != "Cancelled")]
    A["consult_share"] = float(st[st.sales_channel == "Design consultation"].net_sales_cad.sum() / st.net_sales_cad.sum())
    t = is_m[ttm].sum(axis=1)
    A["disc_rate"] = float(-t["discounts"] / t["gross_sales"])
    A["return_rate"] = float(-t["returns"] / (t["gross_sales"] + t["discounts"]))
    A["other_rev_rate"] = float((t["plan_comm"] + t["restock_fees"] + t["cancel_fees"]) / t["net_sales"])
    A["cogs_ratio"] = float(-t["cogs_merch"] / t["net_sales"])
    A["freight_ratio"] = float(t["freight_in"] / t["cogs_merch"])
    A["var_ratio"] = float(t["inv_var"] / t["cogs_merch"])
    lines_cogs = st.assign(stocked=st.supply_source != "Custom PO").groupby("stocked").cogs_cad.sum()
    A["stock_share"] = float(lines_cogs.get(True, 0) / lines_cogs.sum())
    opx = T["opex"].assign(m=T["opex"].month.dt.to_period("M").astype(str)).set_index("m").loc[ttm]
    book = s.groupby(s.transaction_date.dt.to_period("M").astype(str)).net_sales_cad.sum()
    A["commission_rate"] = float(opx.sales_commission_cad.sum() / book.reindex(ttm).sum())        # effective rate (online & consult orders earn none)
    A["marketing_rate"] = float(opx.marketing_cad.sum() / book.reindex([str(m - 1) for m in TTM]).sum())
    A["fee_rate"] = float(-t["fees"] / t["net_rev"])
    b = bal.loc[TTM]
    bh = pd.read_csv(TABLES / "open_order_backlog_monthly.csv", parse_dates=["month"])
    backlog_hist = bh.assign(m=bh.month.dt.to_period("M")).set_index("m").loc[TTM]
    A["dep_ratio"] = float((-b["2350"]).sum() / (backlog_hist.open_order_value_incl_gst.sum()))
    A["alloc_ratio"] = float(b["1210"].sum() / (-b["2350"]).sum())
    A["ar_ratio"] = float(np.mean(b[["1100", "1110", "1120"]].sum(axis=1).values / (is_m.loc["net_rev", ttm].values * (1 + P.GST_RATE))))
    rec = T["pos"][T["pos"].received_date.dt.to_period("M").isin(TTM) & (T["pos"].qty_received > 0)]
    purch = (rec.qty_received * rec.unit_cost_cad).groupby(rec.received_date.dt.to_period("M")).sum().reindex(TTM).values
    A["dpo_base"] = float(np.mean(-b["2000"].values / (purch * (1 + P.FREIGHT_IN_RATE) * (1 + P.GST_RATE))) * 30.4)
    vend = opx[[c for c, a, v, k in P.OPEX_MAP if a in P.GST_TAXABLE_OPEX and k == "vendor"]].sum(axis=1).values
    A["vendor_ap_ratio"] = float(np.mean(-b["2010"].values / (vend * (1 + P.GST_RATE))))
    A["agent_ratio"] = float(np.mean(-(b["2360"] + b["2370"]).values / is_m.loc["net_sales", ttm].values))
    A["accrued_ratio"] = 1 - P.PAYROLL_FIRST_HALF
    A["gst"] = P.GST_RATE
    A["prime"] = float(prime_rate(T["econ"]).loc[pd.Period(END, "M")])
    A["term_spread"], A["rev_spread"] = P.TERM_LOAN["spread"], P.REVOLVER["spread"]
    for k in ["limit", "min_cash", "target_cash", "repay_above", "step"]:
        A[{"limit": "rev_limit"}.get(k, k)] = P.REVOLVER[k]
    A["term_pmt"] = round(P.TERM_LOAN["balance_open"] / P.TERM_LOAN["months_remaining"], 2)
    A["payout"], A["cash_floor"] = P.DIVIDEND["payout"], P.DIVIDEND["cash_floor"]
    A["slow_value"] = float(K.get("overstock_value", 0.0))
    A["markdown_rate"] = 0.20
    A["new_capex_life"] = 84.0
    A["tax_small"], A["tax_general"], A["sbd_limit"] = P.TAX_SMALL_RATE, P.TAX_GENERAL_RATE, P.SMALL_BUSINESS_LIMIT
    return {k: float(v) for k, v in A.items()}


def drivers(L, St, A):
    T = L["T"]
    fc = pd.read_csv(TABLES / "forecast_next_12_months.csv", parse_dates=["month"])
    book = fc[fc.target == "net_sales"].sort_values("month").forecast.values[:H]
    o = T["orders"]
    openo = o[o.status.isin(["Awaiting supplier", "Ready - awaiting pickup/delivery"])].copy()
    po = T["pos"]
    s = T["lines"]
    eta = po[po.status == "Open"].assign(oid=lambda x: x.order_line_id.map(s.set_index("line_id").order_id)).groupby("oid").promised_date.max()
    eta = pd.to_datetime(eta)
    end = pd.Timestamp(END)
    exp = pd.to_datetime(openo.order_id.map(eta).fillna(openo.promised_ready_date))
    exp = exp.where(exp > end + pd.Timedelta(days=10), end + pd.Timedelta(days=10)) + pd.Timedelta(days=10)       # ready + typical hand-off wait
    exp = exp.where(~openo.status.str.startswith("Ready").values, end + pd.Timedelta(days=7))
    openo["exp_month"] = pd.DatetimeIndex(exp).to_period("M")
    rel = openo.groupby("exp_month").net_order_value_cad.sum()
    release = np.array([rel.get(m, 0.0) for m in FC_MONTHS])
    release[-1] += rel[rel.index > FC_MONTHS[-1]].sum()
    same = [str(m - 12) for m in FC_MONTHS]
    opx = T["opex"].assign(m=T["opex"].month.dt.to_period("M").astype(str)).set_index("m")
    payroll_cols = [c for c, a, v, k in P.OPEX_MAP if k == "payroll" and c != "sales_commission_cad"]
    payroll = np.array([opx.loc[m, payroll_cols].sum() * 1.03 for m in same])
    rent_sep = opx.loc[END[:7], ["rent_cad", "cam_property_tax_cad"]].sum()
    occ = np.array([rent_sep * (1.03 if m.year == 2027 else 1.0) + opx.loc[sm, "utilities_cad"] * 1.025 for m, sm in zip(FC_MONTHS, same)])
    ga = np.array([opx.loc[m, ["insurance_cad", "admin_professional_cad", "it_ecommerce_cad"]].sum() * 1.025 for m in same])
    wh = np.array([opx.loc[m, ["warehouse_operations_cad", "design_consult_materials_travel_cad"]].sum() * 1.025 for m in same])
    ins26 = opx.loc[END[:7], "insurance_cad"]
    ins = np.array([ins26 * (1.04 if m.year == 2027 else 1.0) for m in FC_MONTHS])
    prem = np.array([ins26 * 1.04 * 12 if m.month == 1 else 0.0 for m in FC_MONTHS])
    taxable = occ + np.array([opx.loc[m, ["admin_professional_cad", "it_ecommerce_cad", "warehouse_operations_cad", "design_consult_materials_travel_cad", "marketing_cad"]].sum() * 1.025 for m in same])
    capex = np.array([40000.0 if str(m) == "2027-03" else 0.0 for m in FC_MONTHS])
    dep = fixed_asset_schedule(until="2027-09")
    da = dep.groupby("month").depreciation.sum().reindex(FC_MONTHS, fill_value=0.0).values
    inv = St["bal"]["1200"].loc[MONTHS]
    merch = -St["is_m"].loc["cogs_merch"].values
    ratios = {}
    for i, m in enumerate(MONTHS[:-2]):
        ratios.setdefault(m.month, []).append(inv.iloc[i] / (A["stock_share"] * (merch[i + 1] + merch[i + 2]) / 2))
    cover = np.array([np.mean(ratios[m.month]) for m in FC_MONTHS])
    last_book = s[s.transaction_date.dt.to_period("M") == pd.Period(END, "M")].net_sales_cad.sum()
    return pd.DataFrame({"bookings_base": book, "backlog_release": release, "payroll_base": payroll, "occupancy_d": occ, "ga_d": ga, "warehouse_d": wh, "taxable_opex": taxable,
                         "insurance_exp": ins, "insurance_premium": prem, "capex_d": capex, "da_existing": da, "cover_k": cover, "bookings_hist_last": np.full(H, last_book),
                         "is_m1": [int(i == 0) for i in range(H)], "is_jan": [int(m.month == 1) for m in FC_MONTHS], "is_mar": [int(m.month == 3) for m in FC_MONTHS],
                         "is_dec": [int(m.month == 12) for m in FC_MONTHS], "q_start": [int(m.month in (1, 4, 7, 10)) for m in FC_MONTHS]}, index=range(1, H + 1)).T


def opening_values(L, St):
    b = St["bal"].loc[pd.Period(END, "M")]
    tr = L["treasury"].set_index("month")
    is26 = St["is_m"][[c for c in St["is_m"].columns if c.startswith("2026")]]
    o = L["T"]["orders"]
    openo = o[o.status.isin(["Awaiting supplier", "Ready - awaiting pickup/delivery"])]
    return {"backlog": openo.net_order_value_cad.sum(), "deposits": -b["2350"], "inv_alloc": b["1210"], "inv_stock": b["1200"], "term_loan": -b["2700"], "revolver": -b["2600"],
            "ar": b[["1100", "1110", "1120"]].sum(), "prepaid": b["1300"], "gst_net": -(b["1400"] + b["2300"]), "ap": -b[["2000", "2010"]].sum(), "accrued": -b["2100"],
            "agent": -(b["2360"] + b["2370"]), "tax_payable": -b["2400"], "ppe_gross": b[["1500", "1510", "1520"]].sum(), "acc_dep": b["1590"], "cash": b["1000"],
            "share_capital": -b["3000"], "retained": -(b["3200"] + b["3300"]), "cpe": St["bs_m"].at["cpe", END[:7]], "ytd_pbt": is26.loc["pbt"].sum(),
            "lcf": float(tr.at[END[:7], "loss_carryforward"]), "tax_ytd": -is26.loc["tax"].sum(), "prior_tax": 0.0, "capex_cum": 0.0, "ytd_ni": is26.loc["net_income"].sum()}


def sensitivity(base):
    b = summary(run(SCENARIOS["Base"], base))
    rows = []
    for lab, fld, val in SENSITIVITIES:
        r = summary(run(replace(SCENARIOS["Base"], **{fld: val}), base))
        rows.append({"scenario": lab, "driver": fld, "value": val, "delta_net_revenue": r["net_revenue"] - b["net_revenue"], "delta_gross_profit": r["gross_profit"] - b["gross_profit"],
                     "delta_net_income": r["net_income"] - b["net_income"], "delta_cfo": r["cfo"] - b["cfo"], "delta_closing_cash": r["closing_cash"] - b["closing_cash"],
                     "delta_working_capital": r["closing_working_capital"] - b["closing_working_capital"], "net_income": r["net_income"], "closing_cash": r["closing_cash"]})
    return pd.DataFrame(rows)


def build(L, St, K):
    A = calibrate(L, St, K)
    base = {"A": A, "opening": opening_values(L, St)}
    base["drivers"] = drivers(L, St, A)
    res = {n: run(sc, base) for n, sc in SCENARIOS.items()}
    summ = pd.DataFrame({k: summary(v) for k, v in res.items()}).T
    summ["assumptions"] = pd.Series(SCENARIO_NOTES)
    return dict(base=base, results=res, summary=summ, sensitivity=sensitivity(base))
