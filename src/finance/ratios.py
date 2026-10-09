"""Financial ratio analysis of the SIMULATED accounts (TTM flows; month-end or 13-point average balances)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.finance import policy as P

DEFINITIONS = [  # key, name, group, formula, meaning, unit, higher_is_better
    ("gross_margin", "Gross profit margin", "Profitability", "Gross profit / total net revenue", "Pricing, discount discipline and mix after all cost of goods.", "%", True),
    ("ebitda_margin", "EBITDA margin", "Profitability", "EBITDA / total net revenue", "Operating cash earnings before depreciation, interest and tax.", "%", True),
    ("net_margin", "Net profit margin", "Profitability", "Net income / total net revenue", "Bottom-line profit per dollar of revenue.", "%", True),
    ("roa", "Return on assets", "Profitability", "TTM net income / average total assets", "Profit generated from the assets employed (mostly inventory and cash).", "%", True),
    ("roe", "Return on equity", "Profitability", "TTM net income / average equity", "Return earned on the owners' capital.", "%", True),
    ("current_ratio", "Current ratio", "Liquidity", "Current assets / current liabilities", "Short-term solvency; customer deposits are a large current liability.", "x", True),
    ("quick_ratio", "Quick ratio", "Liquidity", "(Cash + receivables) / current liabilities", "Liquidity without selling inventory.", "x", True),
    ("working_capital", "Working capital", "Liquidity", "Current assets - current liabilities", "Net short-term resources.", "$", True),
    ("deposit_funding", "Inventory funded by customer deposits", "Liquidity", "Customer deposits / total inventory", "Share of inventory investment financed by customers' deposits.", "x", True),
    ("inventory_turnover", "Inventory turnover", "Efficiency", "TTM merchandise COGS / average inventory (stocked + allocated)", "How often stock is sold and replaced each year.", "x", True),
    ("dio", "Days inventory outstanding", "Efficiency", "365 / inventory turnover", "Days of inventory held.", "days", False),
    ("dso", "Days sales outstanding", "Efficiency", "Average receivables / (TTM net revenue x 1.05) x 365", "Days to collect card, financing-partner and trade receivables.", "days", False),
    ("dpo", "Days payables outstanding", "Efficiency", "Average accounts payable / TTM cost of goods sold x 365", "Days of supplier credit used.", "days", True),
    ("ccc", "Cash conversion cycle", "Efficiency", "DIO + DSO - DPO", "Days between paying suppliers and collecting from customers (before deposits).", "days", False),
    ("ccc_after_deposits", "Cash conversion cycle after customer deposits", "Efficiency", "CCC - average customer deposits / TTM COGS x 365",
     "Deposits collected before delivery shorten the effective cycle - a key furniture-retail advantage.", "days", False),
    ("asset_turnover", "Asset turnover", "Efficiency", "TTM net revenue / average total assets", "Revenue per dollar of assets.", "x", True),
    ("debt_to_equity", "Debt-to-equity", "Solvency", "(Revolver + term loan) / equity", "Reliance on borrowed money.", "x", False),
    ("interest_coverage", "Interest coverage", "Solvency", "TTM EBIT / TTM interest", "Headroom to service interest.", "x", True),
]
DEF = {d[0]: d for d in DEFINITIONS}
ACTIONS = {
    "gross_margin": "Tighten discretionary discounts, price custom upholstery to its true lead-time cost, push high-margin décor attachment.",
    "ebitda_margin": "Hold payroll flat as sales grow (designer-led selling), review marketing mix by attributed revenue.",
    "net_margin": "Combine margin and cost actions; keep debt low.",
    "roa": "Release cash tied in aged stock; invest surplus cash or repay debt.",
    "roe": "Profit growth and a disciplined dividend policy.",
    "current_ratio": "Comfortable; monitor as deposits grow with the custom backlog.",
    "quick_ratio": "Strong cash position - consider deploying idle cash.",
    "working_capital": "Size working capital to the custom backlog and seasonal peaks (Nov-Jan, spring).",
    "deposit_funding": "Keep 50% deposits on custom and special orders; consider a deposit on high-value in-stock reservations.",
    "inventory_turnover": "Service-level reorder points for A items, clear >180-day stock, buy deeper only on proven sellers.",
    "dio": "Cut cover on C-class décor and slow case goods.",
    "dso": "Short already; follow up trade accounts at 30 days.",
    "dpo": "Negotiate Net 45-60 with importers in exchange for volume commitments.",
    "ccc": "Lower DIO and lengthen DPO.",
    "ccc_after_deposits": "Protect deposit discipline; shorten custom lead times to release deposits into revenue sooner.",
    "asset_turnover": "Grow revenue per square foot via design consultations and room packages.",
    "debt_to_equity": "Low; the term loan is nearly repaid.",
    "interest_coverage": "Very comfortable.",
}


def compute(is_m, bs_m, bs_open):
    bs = pd.concat([bs_open.rename("2023-12"), bs_m], axis=1)
    cols = list(is_m.columns)
    out = {}
    for i in range(11, len(cols)):
        w = cols[i - 11:i + 1]
        bw = ["2023-12" if i == 11 else cols[i - 12]] + w
        f = is_m[w].sum(axis=1)
        b = bs[cols[i]]
        avg = bs[bw].mean(axis=1)
        nr = f["net_rev"]
        inv_avg = avg["inv_stock"] + avg["inv_alloc"]
        merch = -(f["cogs_merch"] + f["inv_var"])
        turn = merch / inv_avg
        dso = avg["ar"] / (nr * (1 + P.GST_RATE)) * 365
        dpo = avg["ap"] / -f["cogs"] * 365
        ccc = 365 / turn + dso - dpo
        debt = b["revolver"] + b["term_current"] + b["term_lt"]
        out[cols[i]] = {"gross_margin": f["gross_profit"] / nr * 100, "ebitda_margin": f["ebitda"] / nr * 100, "net_margin": f["net_income"] / nr * 100,
                        "roa": f["net_income"] / avg["total_assets"] * 100, "roe": f["net_income"] / avg["total_equity"] * 100,
                        "current_ratio": b["current_assets"] / b["current_liabilities"], "quick_ratio": (b["cash"] + b["ar"]) / b["current_liabilities"],
                        "working_capital": b["current_assets"] - b["current_liabilities"], "deposit_funding": b["deposits"] / (b["inv_stock"] + b["inv_alloc"]),
                        "inventory_turnover": turn, "dio": 365 / turn, "dso": dso, "dpo": dpo, "ccc": ccc, "ccc_after_deposits": ccc - avg["deposits"] / -f["cogs"] * 365,
                        "asset_turnover": nr / avg["total_assets"], "debt_to_equity": debt / b["total_equity"],
                        "interest_coverage": f["ebit"] / -f["interest"] if f["interest"] else np.nan}
    return pd.DataFrame(out).loc[[d[0] for d in DEFINITIONS]]


def annual_table(r):
    t = r[["2024-12", "2025-12", "2026-09"]].copy()
    t.columns = ["FY2024", "FY2025", "TTM Sep-2026"]
    t["change_vs_FY2025"] = t["TTM Sep-2026"] - t["FY2025"]
    meta = pd.DataFrame([d[1:] for d in DEFINITIONS], index=[d[0] for d in DEFINITIONS], columns=["ratio", "group", "formula", "meaning", "unit", "higher_is_better"])
    t = meta.join(t)
    t["direction"] = np.where(t.change_vs_FY2025.abs() < 1e-9, "flat", np.where((t.change_vs_FY2025 > 0) == t.higher_is_better, "improved", "deteriorated"))
    t["management_action"] = t.index.map(ACTIONS)
    return t
