"""Trial balances and the integrated three statements, derived ONLY from general-ledger balances (SIMULATED).

Presentation: income-statement and cash-flow lines are signed (+ income / inflow, - cost / outflow); balance-sheet lines
are positive balances, with accumulated depreciation shown negative.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import END
from src.finance import policy as P
from src.finance.ledger import MONTHS, fixed_asset_schedule

ALL_M = pd.period_range("2023-12", END, freq="M")


def activity(gl, include_closing=True):
    g = gl if include_closing else gl[~gl.is_closing]
    a = g.groupby(["month", "account"]).amount.sum().unstack(fill_value=0.0)
    return a.reindex(index=ALL_M, columns=list(P.ACCOUNTS), fill_value=0.0)


def balances(gl):
    return activity(gl).cumsum().round(2)


def trial_balances(gl):
    act = activity(gl, include_closing=False)
    pre = act.cumsum()
    yrs = [m.year for m in act.index]
    for a, v in P.ACCOUNTS.items():
        if v["type"] in P.PNL_TYPES or a == "3300":
            pre[a] = act[a].groupby(yrs).cumsum()
    pre["3200"] = activity(gl)["3200"].cumsum() - activity(gl[gl.is_closing])["3200"].groupby(yrs).cumsum()
    pre = pre.round(2)
    rows = [{"month": str(m), "account": a, "account_name": P.ACCOUNTS[a]["name"], "type": P.ACCOUNTS[a]["type"],
             "debit": round(v, 2) if v > 0 else 0.0, "credit": round(-v, 2) if v < 0 else 0.0}
            for m in pre.index for a in P.ACCOUNTS if abs(v := pre.at[m, a]) >= 0.005]
    return pd.DataFrame(rows).assign(data_status="SIMULATED")


IS_LINES = [  # key, label, accounts, kind
    ("sales_sofas", "Sofas & sectionals", ["4000"], "rev"), ("sales_bedroom", "Bedroom", ["4010"], "rev"), ("sales_mattress", "Mattresses & bases", ["4020"], "rev"),
    ("sales_dining", "Dining", ["4030"], "rev"), ("sales_living", "Living & occasional", ["4040"], "rev"), ("sales_office", "Home office", ["4050"], "rev"),
    ("sales_decor", "Décor & lighting", ["4060"], "rev"),
    ("gross_sales", "Gross furniture sales", None, "sub"),
    ("discounts", "Less: discounts & promotional allowances", ["4900"], "cost"), ("returns", "Less: sales returns", ["4910"], "cost"),
    ("net_sales", "Net furniture sales", None, "sub"),
    ("plan_comm", "Protection-plan commissions (agent, net)", ["4100"], "rev"), ("restock_fees", "Restocking fees", ["4200"], "rev"),
    ("cancel_fees", "Retained cancellation fees", ["4300"], "rev"),
    ("net_rev", "Total net revenue", None, "sub"),
    ("cogs_merch", "Cost of goods sold - merchandise", ["5000"], "cost"), ("freight_in", "Freight-in & supplier charges", ["5200"], "cost"),
    ("inv_var", "Inventory variances, shrinkage & write-offs", ["5100"], "cost"),
    ("cogs", "Cost of goods sold", None, "sub"),
    ("gross_profit", "Gross profit", None, "sub"),
    ("emp_comp", "Employee compensation (incl. commissions & designers)", ["6000", "6010", "6020", "6030", "6040"], "cost"),
    ("occupancy", "Occupancy (rent, CAM & property tax, utilities)", ["6100", "6105", "6110"], "cost"),
    ("marketing", "Marketing & advertising", ["6200"], "cost"),
    ("g_and_a", "General & administrative (insurance, professional, IT)", ["6300", "6310", "6320"], "cost"),
    ("warehouse", "Warehouse, fulfilment & design-consult costs", ["6400", "6410"], "cost"),
    ("fees", "Card & financing-partner fees", ["6420", "6430"], "cost"),
    ("opex", "Operating expenses (before depreciation)", None, "sub"),
    ("ebitda", "EBITDA", None, "sub"),
    ("da", "Depreciation", ["6900"], "cost"),
    ("ebit", "Operating income (EBIT)", None, "sub"),
    ("interest", "Interest expense", ["7000", "7010"], "cost"),
    ("pbt", "Income before tax", None, "sub"),
    ("tax", "Income taxes", ["8000"], "cost"),
    ("net_income", "Net income", None, "sub"),
]
IS_LABEL = {k: l for k, l, *_ in IS_LINES}
IS_SUB = {"gross_sales": ["sales_sofas", "sales_bedroom", "sales_mattress", "sales_dining", "sales_living", "sales_office", "sales_decor"],
          "net_sales": ["gross_sales", "discounts", "returns"], "net_rev": ["net_sales", "plan_comm", "restock_fees", "cancel_fees"],
          "cogs": ["cogs_merch", "freight_in", "inv_var"], "gross_profit": ["net_rev", "cogs"],
          "opex": ["emp_comp", "occupancy", "marketing", "g_and_a", "warehouse", "fees"], "ebitda": ["gross_profit", "opex"],
          "ebit": ["ebitda", "da"], "pbt": ["ebit", "interest"], "net_income": ["pbt", "tax"]}


def income_statement(gl):
    a = activity(gl, include_closing=False).loc[MONTHS[0]:]
    out = {k: -a[accts].sum(axis=1) for k, _, accts, _ in IS_LINES if accts}
    for k, parts in IS_SUB.items():
        out[k] = sum(out[p] for p in parts)
    df = pd.DataFrame(out).T.loc[[k for k, *_ in IS_LINES]].round(2)
    df.columns = [str(c) for c in df.columns]
    return df


def common_size(is_df):
    nr = is_df.loc["net_rev"].replace(0, np.nan)
    return (is_df / nr * 100).round(2)


BS_LINES = [
    ("cash", "Cash", "Current assets"), ("ar", "Receivables (card, financing partner, trade)", "Current assets"),
    ("inv_stock", "Inventory - stocked merchandise", "Current assets"), ("inv_alloc", "Inventory - allocated to customer orders", "Current assets"),
    ("prepaid", "Prepaid expenses", "Current assets"), ("gst_rec", "GST recoverable", "Current assets"),
    ("current_assets", "Total current assets", "sub"),
    ("ppe_gross", "Fixed assets at cost", "Non-current"), ("acc_dep", "Accumulated depreciation", "Non-current"), ("ppe_net", "Net fixed assets", "sub"),
    ("total_assets", "TOTAL ASSETS", "sub"),
    ("ap", "Accounts payable", "Current liabilities"), ("accrued", "Accrued payroll & commissions", "Current liabilities"),
    ("deposits", "Customer deposits (contract liabilities)", "Current liabilities"), ("agent", "Amounts collected as agent (carrier, insurer)", "Current liabilities"),
    ("gst_pay", "GST payable", "Current liabilities"), ("tax_payable", "Income taxes payable", "Current liabilities"),
    ("revolver", "Revolving line of credit", "Current liabilities"), ("term_current", "Current portion of term loan", "Current liabilities"),
    ("current_liabilities", "Total current liabilities", "sub"),
    ("term_lt", "Term loan (non-current)", "Non-current"), ("total_liabilities", "TOTAL LIABILITIES", "sub"),
    ("share_capital", "Share capital", "Equity"), ("retained", "Retained earnings", "Equity"), ("cpe", "Current-year earnings", "Equity"),
    ("total_equity", "TOTAL EQUITY", "sub"), ("total_le", "TOTAL LIABILITIES AND EQUITY", "sub"), ("check", "Check: assets - liabilities - equity", "check"),
]
BS_LABEL = {k: l for k, l, _ in BS_LINES}
BS_SUB = {"current_assets": ["cash", "ar", "inv_stock", "inv_alloc", "prepaid", "gst_rec"], "ppe_net": ["ppe_gross", "acc_dep"], "total_assets": ["current_assets", "ppe_net"],
          "current_liabilities": ["ap", "accrued", "deposits", "agent", "gst_pay", "tax_payable", "revolver", "term_current"],
          "total_liabilities": ["current_liabilities", "term_lt"], "total_equity": ["share_capital", "retained", "cpe"], "total_le": ["total_liabilities", "total_equity"]}
TERM_PMT = round(P.TERM_LOAN["balance_open"] / P.TERM_LOAN["months_remaining"], 2)


def balance_sheet(gl):
    b = balances(gl)
    pnl = [a for a, v in P.ACCOUNTS.items() if v["type"] in P.PNL_TYPES]
    o = {"cash": b["1000"], "ar": b[["1100", "1110", "1120"]].sum(axis=1), "inv_stock": b["1200"], "inv_alloc": b["1210"], "prepaid": b["1300"]}
    gst = b["1400"] + b["2300"]
    o["gst_rec"] = gst.clip(lower=0)
    o["ppe_gross"] = b[["1500", "1510", "1520"]].sum(axis=1)
    o["acc_dep"] = b["1590"]
    o["ap"] = -b[["2000", "2010"]].sum(axis=1)
    o["accrued"] = -b["2100"]
    o["deposits"] = -b["2350"]
    o["agent"] = -b[["2360", "2370"]].sum(axis=1)
    o["gst_pay"] = (-gst).clip(lower=0)
    o["tax_payable"] = -b["2400"]
    o["revolver"] = -b["2600"]
    term = -b["2700"]
    o["term_current"] = term.clip(upper=12 * TERM_PMT)
    o["term_lt"] = term - o["term_current"]
    o["share_capital"] = -b["3000"]
    o["retained"] = -(b["3200"] + b["3300"])
    o["cpe"] = -b[pnl].sum(axis=1)
    for k, parts in BS_SUB.items():
        o[k] = sum(o[p] for p in parts)
    o["check"] = o["total_assets"] - o["total_le"]
    df = pd.DataFrame(o).T.loc[[k for k, *_ in BS_LINES]].round(2)
    df.columns = [str(c) for c in df.columns]
    return df


CF_LINES = [
    ("net_income", "Net income", "Operating"), ("da", "Depreciation", "Operating"),
    ("d_ar", "(Increase) decrease in receivables", "Operating"), ("d_inv", "Inventory investment: (increase) decrease in inventory", "Operating"),
    ("d_ap", "Increase (decrease) in accounts payable (supplier & vendor credit)", "Operating"),
    ("d_deposits", "Increase (decrease) in customer deposits", "Operating"),
    ("d_other", "Other working capital (prepaid, accrued, agent, GST, tax)", "Operating"),
    ("cfo", "Net cash from operating activities", "sub"),
    ("capex", "Capital expenditures", "Investing"), ("cfi", "Net cash used in investing activities", "sub"),
    ("rev_draw", "Revolver draws", "Financing"), ("rev_repay", "Revolver repayments", "Financing"), ("term_repay", "Term-loan repayments", "Financing"),
    ("dividends", "Dividends paid", "Financing"), ("cff", "Net cash from (used in) financing activities", "sub"),
    ("net_change", "Net change in cash", "sub"), ("open_cash", "Opening cash", "sub"), ("close_cash", "Ending cash balance", "sub"),
    ("bs_cash", "Cash per balance sheet", "check"), ("check", "Check: ending cash - balance-sheet cash", "check"),
]
CF_LABEL = {k: l for k, l, _ in CF_LINES}
CF_SUB = {"cfo": ["net_income", "da", "d_ar", "d_inv", "d_ap", "d_deposits", "d_other"], "cfi": ["capex"], "cff": ["rev_draw", "rev_repay", "term_repay", "dividends"],
          "net_change": ["cfo", "cfi", "cff"]}


def cash_flow(gl, is_df):
    act = activity(gl).loc[MONTHS[0]:]
    nc = gl[~gl.is_closing]

    def flow(acct, side):
        return nc[nc.account == acct].groupby("month")[side].sum().reindex(MONTHS, fill_value=0.0).values

    o = {"net_income": is_df.loc["net_income"].values, "da": -is_df.loc["da"].values,
         "d_ar": -act[["1100", "1110", "1120"]].sum(axis=1).values, "d_inv": -act[["1200", "1210"]].sum(axis=1).values,
         "d_ap": -act[["2000", "2010"]].sum(axis=1).values, "d_deposits": -act["2350"].values,
         "d_other": -act[["1300", "1400", "2100", "2300", "2360", "2370", "2400"]].sum(axis=1).values,
         "capex": -act[["1500", "1510", "1520"]].sum(axis=1).values,
         "rev_draw": flow("2600", "credit"), "rev_repay": -flow("2600", "debit"), "term_repay": -(flow("2700", "debit") - flow("2700", "credit")),
         "dividends": -flow("3300", "debit")}
    for k, parts in CF_SUB.items():
        o[k] = sum(o[p] for p in parts)
    bs_cash = balances(gl)["1000"]
    o["open_cash"] = bs_cash.shift(1).loc[MONTHS[0]:].values
    o["close_cash"] = o["open_cash"] + o["net_change"]
    o["bs_cash"] = bs_cash.loc[MONTHS[0]:].values
    o["check"] = o["close_cash"] - o["bs_cash"]
    return pd.DataFrame(o, index=[str(m) for m in MONTHS]).T.loc[[k for k, *_ in CF_LINES]].round(2)


DIRECT = {"Customer payments": "Receipts: customer deposits & balances (cash tenders)", "Collections": "Receipts: card, financing-partner & trade settlements",
          "Cancellations": "Refunds on cancelled orders", "Returns": "Refunds on returns", "Supplier payments": "Payments to suppliers & vendors",
          "Operating expenses": "Rent & occupancy paid", "Payroll": "Payroll paid", "Prepaid expenses": "Insurance premiums paid",
          "Agent remittances": "Remitted to carrier / insurer (agent)", "GST remittance": "GST remitted", "Income tax": "Income tax paid",
          "Financing": "Interest, loan principal & revolver", "Capital expenditure": "Capital expenditures", "Equity": "Dividends"}


def direct_cash_flow(gl):
    c = gl[(gl.account == "1000") & (gl.date > pd.Timestamp(P.OPENING["date"]))]
    d = c.assign(category=c.source.map(DIRECT)).pivot_table(index="category", columns="month", values="amount", aggfunc="sum", fill_value=0.0)
    d.columns = [str(x) for x in d.columns]
    return d.reindex(columns=[str(m) for m in MONTHS], fill_value=0.0).round(2)


def aggregate(is_df, bs_df, cf_df, freq):
    per = pd.PeriodIndex(is_df.columns, freq="M")
    key = per.asfreq("Q").astype(str) if freq == "Q" else per.year.astype(str)
    agg_is = is_df.T.groupby(key.values).sum().T
    agg_cf = cf_df.T.groupby(key.values).sum().T
    last = pd.Series(is_df.columns, index=key.values).groupby(level=0).last()
    first = pd.Series(is_df.columns, index=key.values).groupby(level=0).first()
    agg_cf.loc["open_cash"] = [cf_df.at["open_cash", first[k]] for k in agg_cf.columns]
    for r in ["close_cash", "bs_cash", "check"]:
        agg_cf.loc[r] = [cf_df.at[r, last[k]] for k in agg_cf.columns]
    agg_bs = bs_df[[last[k] for k in agg_is.columns]]
    agg_bs.columns = agg_is.columns
    return agg_is.round(2), agg_bs.round(2), agg_cf.round(2)


def open_items(items, at):
    return items[(items.doc_date <= at) & (items.due_date > at)]


def subledger_reconciliation(gl, ar_items, ap_items, T):
    """AR/AP open items vs control accounts; customer-deposit liability vs the open-order deposit register."""
    b = balances(gl)
    pay, orders = T["payments"], T["orders"]
    pos = pay[(pay.amount_incl_gst > 0) & ~pay.payment_type.str.startswith("Trade account settlement")]
    rows = []
    for m in MONTHS:
        at = m.end_time.normalize()
        for acct in ["1100", "1110", "1120"]:
            items = ar_items[ar_items.account == acct]
            if acct == "1120":                                                        # trade invoices close when the settlement payment arrives
                settled = set(pay[pay.payment_type.str.startswith("Trade account settlement") & (pay.payment_date <= at)].order_id)
                sub = items[(items.doc_date <= at) & ~items.counterparty.isin(settled)].amount.sum()
            else:
                sub = open_items(items, at).amount.sum()
            rows.append({"month": str(m), "ledger": "AR", "control_account": acct, "gl_balance": round(b.at[m, acct], 2), "subledger": round(sub, 2)})
        for acct in ["2000", "2010"]:
            rows.append({"month": str(m), "ledger": "AP", "control_account": acct, "gl_balance": round(-b.at[m, acct], 2),
                         "subledger": round(open_items(ap_items[ap_items.account == acct], at).amount.sum(), 2)})
        o = orders[(orders.order_date <= at) & ~((orders.fulfilled_date <= at) | (orders.cancel_date <= at))]
        dep = pos[pos.order_id.isin(o.order_id) & (pos.payment_date <= at)].amount_incl_gst.sum()
        rows.append({"month": str(m), "ledger": "Customer deposits", "control_account": "2350", "gl_balance": round(-b.at[m, "2350"], 2), "subledger": round(dep, 2)})
    r = pd.DataFrame(rows)
    r["difference"] = (r.gl_balance - r.subledger).round(2)
    return r


def aging(items, at=pd.Timestamp(END)):
    o = open_items(items, at).copy()
    o["days_outstanding"] = (at - o.doc_date).dt.days
    o["bucket"] = pd.cut(o.days_outstanding, [-1, 30, 60, 90, 10_000], labels=["0-30", "31-60", "61-90", "90+"])
    return o


def inventory_valuation(T):
    """Independent month-end inventory value by state from the operational movement records."""
    mv = T["moves"].assign(month=lambda x: x.movement_date.dt.to_period("M"))
    v = mv.pivot_table(index="month", columns="inventory_state", values="value_cad", aggfunc="sum", fill_value=0.0).reindex(MONTHS, fill_value=0.0).cumsum()
    q = mv.pivot_table(index="month", columns="inventory_state", values="quantity", aggfunc="sum", fill_value=0.0).reindex(MONTHS, fill_value=0.0).cumsum()
    out = pd.DataFrame({"stock_units": q.get("stock", 0), "allocated_units": q.get("allocated", 0),
                        "stock_value_from_movements": v.get("stock", 0).round(2), "allocated_value_from_movements": v.get("allocated", 0).round(2)})
    out.index = out.index.astype(str)
    return out


def fixed_asset_register():
    dep = fixed_asset_schedule()
    acc = dep.groupby("asset_id").depreciation.sum()
    return pd.DataFrame([{"asset_id": a, "description": d, "account": ac, "acquired": q, "cost": c, "useful_life_months": l, "accumulated_depreciation_31dec2023": a0,
                          "accumulated_depreciation_30sep2026": round(a0 + acc.get(a, 0.0), 2), "net_book_value_30sep2026": round(c - a0 - acc.get(a, 0.0), 2),
                          "data_status": "SIMULATED"} for a, d, ac, q, c, l, a0 in P.FIXED_ASSETS])


def build(L):
    gl = L["gl"]
    is_m = income_statement(gl)
    bs_m = balance_sheet(gl)
    cf_m = cash_flow(gl, is_m)
    bs_open = bs_m["2023-12"]
    bs_m = bs_m.drop(columns="2023-12")
    is_q, bs_q, cf_q = aggregate(is_m, bs_m, cf_m, "Q")
    is_y, bs_y, cf_y = aggregate(is_m, bs_m, cf_m, "Y")
    return dict(is_m=is_m, bs_m=bs_m, cf_m=cf_m, bs_open=bs_open, is_q=is_q, bs_q=bs_q, cf_q=cf_q, is_y=is_y, bs_y=bs_y, cf_y=cf_y,
                cs_m=common_size(is_m), cs_y=common_size(is_y), tb=trial_balances(gl), direct=direct_cash_flow(gl),
                subledger=subledger_reconciliation(gl, L["ar_items"], L["ap_items"], L["T"]), inv_val=inventory_valuation(L["T"]),
                far=fixed_asset_register(), bal=balances(gl))
