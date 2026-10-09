"""Double-entry general ledger of the FICTIONAL retailer, generated from the synthetic operational database.

Journal sources -> entries (every entry balances to the cent when posted; nothing is a balancing plug):
    Opening balance      31-Dec-2023 statement of financial position (explicit balances; opening retained earnings = residual)
    Customer payments    deposits / balances -> customer deposits (contract liability), tender receivables
    Collections          card / financing-partner settlements (partner fee expensed), trade-account settlements
    Order completion     hand-off: deposits released, revenue by category, discounts, GST, plan commission (agent), COGS
    Cancellations        refunds and retained cancellation fees; supplier cancellation fees
    Returns              refunds less 15% restocking fee, GST reversal, restock / write-off
    Purchasing           supplier receipts (stock or customer-allocated) with GST ITCs, freight-in, supplier payments
    Inventory            allocation reclasses, cancel releases (standard-cost variances), returns, write-offs, cycle counts
    Operating expenses   payroll, rent, prepaid insurance, vendor bills and payments, agent remittances
    Fixed assets         capex, straight-line depreciation
    Treasury & tax       daily revolver sweep, month-end cash band, interest, term-loan principal, GST, income tax, dividends
    Year-end close       P&L and dividends closed to retained earnings
All amounts are SIMULATED.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import END, EXTERNAL, START
from src.engineering.sqlutil import connect
from src.finance import policy as P

END_TS, START_TS = pd.Timestamp(END), pd.Timestamp(START)
MONTHS = pd.period_range(START, END, freq="M")
OB_DATE = pd.Timestamp(P.OPENING["date"])


def r2(x):
    return float(np.round(x + 1e-12, 2))


@dataclass
class Book:
    rows: list = field(default_factory=list)
    ar_items: list = field(default_factory=list)
    ap_items: list = field(default_factory=list)
    n: int = 0

    def je(self, prefix, date, source, ref, desc, lines, closing=False):
        cents = [int(round(a * 100)) for _, a, _ in lines]
        if sum(cents) != 0:
            raise ValueError(f"Unbalanced JE {prefix} {ref}: {sum(cents) / 100}")
        self.n += 1
        jid = f"{prefix}-{self.n:07d}"
        d = pd.Timestamp(date)
        for (acct, _, cp), c in zip(lines, cents):
            if c == 0:
                continue
            if acct not in P.ACCOUNTS:
                raise KeyError(acct)
            self.rows.append((jid, d, acct, c / 100 if c > 0 else 0.0, -c / 100 if c < 0 else 0.0, source, ref, cp, desc, closing))
        return jid

    def ar(self, item, acct, cp, doc, due, amount):
        self.ar_items.append(dict(item_id=item, account=acct, counterparty=cp, doc_date=pd.Timestamp(doc), due_date=pd.Timestamp(due), amount=r2(amount)))

    def ap(self, item, acct, cp, doc, due, amount):
        self.ap_items.append(dict(item_id=item, account=acct, counterparty=cp, doc_date=pd.Timestamp(doc), due_date=pd.Timestamp(due), amount=r2(amount)))


def load_operational():
    con = connect()
    q = lambda s: pd.read_sql_query(s, con)
    T = dict(orders=q("SELECT * FROM orders"), lines=q("SELECT * FROM sales_transactions"), payments=q("SELECT * FROM payments"),
             pos=q("SELECT * FROM purchase_orders"), moves=q("SELECT * FROM inventory_movements"), returns=q("SELECT * FROM returns"),
             opex=q("SELECT * FROM operating_expenses"), products=q("SELECT * FROM products"), suppliers=q("SELECT * FROM suppliers"))
    con.close()
    T["econ"] = pd.read_csv(EXTERNAL / "economic_indicators_monthly.csv", parse_dates=["month"])
    dates = dict(orders=["order_date", "ready_date", "fulfilled_date", "cancel_date"], lines=["transaction_date", "fulfilled_date"], payments=["payment_date"],
                 pos=["order_date", "received_date", "cancel_date"], moves=["movement_date"], returns=["return_date"], opex=["month"])
    for k, cols in dates.items():
        for c in cols:
            T[k][c] = pd.to_datetime(T[k][c])
    return T


def prime_rate(econ):
    r = econ.set_index(econ.month.dt.to_period("M")).policy_rate_pct.reindex(pd.period_range("2023-12", "2027-12", freq="M")).ffill().bfill()
    return r / 100 + P.PRIME_SPREAD_OVER_POLICY


def fixed_asset_schedule(until=END):
    """Monthly straight-line depreciation; assets owned at 31-Dec-2023 continue from their accumulated depreciation."""
    rows = []
    months = pd.period_range("2024-01", until, freq="M")
    for aid, desc, acct, acq, cost, life, acc0 in P.FIXED_ASSETS:
        monthly = r2(cost / life)
        start = max(pd.Period(acq, "M") + 1, months[0])
        acc = acc0
        m = start
        while m <= months[-1] and acc < cost - 0.005:
            amt = min(monthly, r2(cost - acc))
            acc = r2(acc + amt)
            rows.append({"asset_id": aid, "month": m, "account": acct, "depreciation": amt})
            m += 1
    return pd.DataFrame(rows, columns=["asset_id", "month", "account", "depreciation"])


def opex_frame(T):
    o = T["opex"].copy()
    o["m"] = o.month.dt.to_period("M")
    return o.set_index("m")


# ----------------------------------------------------------------------------------------------- opening position
def post_opening(B: Book, T):
    d = OB_DATE
    lines = [("1000", P.OPENING["cash"], None), ("3000", -P.OPENING["share_capital"], None), ("2700", -P.TERM_LOAN["balance_open"], "Lender")]
    for aid, desc, acct, acq, cost, life, acc0 in P.FIXED_ASSETS:
        if pd.Timestamp(acq) <= d:
            lines += [(acct, cost, aid), ("1590", -acc0, aid)]
    mv = T["moves"]
    ob = mv[mv.movement_type == "OPENING_BALANCE"]
    lines += [("1200", r2(ob[ob.inventory_state == "stock"].value_cad.sum()), None), ("1210", r2(ob[ob.inventory_state == "allocated"].value_cad.sum()), None)]
    pre = T["payments"][T["payments"].pre_period == 1]
    lines.append(("2350", -r2(pre.amount_incl_gst.sum()), None))                    # deposits held for the opening order backlog
    for r in pre.itertuples():                                                    # tender receivables not yet settled at 31-Dec-2023
        acct, lag = P.SETTLEMENT[r.tender]
        due = r.payment_date + pd.Timedelta(days=lag)
        if acct != "1000" and due > d:
            lines.append((acct, r2(r.amount_incl_gst), r.tender))
            B.ar(f"OB-{r.payment_id}", acct, r.tender, r.payment_date, due, r.amount_incl_gst)
    po = T["pos"]
    rec = po[(po.received_date <= d) & (po.qty_received > 0)]
    for r in rec.itertuples():                                                    # supplier invoices received in Dec-2023, unpaid at year end
        due = r.received_date + pd.Timedelta(days=P.SUPPLIER_TERMS_DAYS)
        if due > d:
            v = r2(r.qty_received * r.unit_cost_cad)
            frt = r2(v * P.FREIGHT_IN_RATE)
            amt = r2(v + frt + r2((v + frt) * P.GST_RATE))
            lines.append(("2000", -amt, r.supplier_id))
            B.ap(f"OB-{r.po_id}", "2000", r.supplier_id, r.received_date, due, amt)
    o = opex_frame(T).loc[MONTHS[0]]
    payroll = r2(sum(o[c] for c, a, v, k in P.OPEX_MAP if k == "payroll"))
    acc_pay = r2(payroll * (1 - P.PAYROLL_FIRST_HALF))
    lines.append(("2100", -acc_pay, None))                                        # proxy: second half of December payroll ~ January run rate
    for c, a, v, k in P.OPEX_MAP:
        if k == "vendor":
            amt = r2(o[c] * (1 + (P.GST_RATE if a in P.GST_TAXABLE_OPEX else 0)))
            lines.append(("2010", -amt, v))
            B.ap(f"OB-{a}", "2010", v, d, pd.Timestamp("2024-01-20"), amt)
    lines.append(("2400", -38000.0, "Canada Revenue Agency"))                      # 2023 income tax, paid 31-Mar-2024
    resid = -r2(sum(a for _, a, _ in lines))
    lines.append(("3200", resid, None))                                           # opening retained earnings = derived residual (documented)
    B.je("OB", d, "Opening balance", "OB-2023", "Opening statement of financial position at 31-Dec-2023", lines)
    return acc_pay


# ----------------------------------------------------------------------------------------------- customer cash, completion, cancellation, returns
def post_customer_flows(B: Book, T):
    O = T["orders"].set_index("order_id")
    L = T["lines"]
    pay = T["payments"]
    lp = pay[(pay.pre_period == 0)]
    for r in lp[lp.amount_incl_gst > 0].itertuples():
        if r.payment_type.startswith("Trade account settlement"):
            B.je("COL", r.payment_date, "Collections", r.payment_id, f"Trade account settlement {r.order_id}", [("1000", r.amount_incl_gst, r.order_id), ("1120", -r.amount_incl_gst, r.order_id)])
            continue
        acct, lag = P.SETTLEMENT[r.tender]
        cp = None if acct == "1000" else r.tender
        B.je("CUS", r.payment_date, "Customer payments", r.payment_id, f"{r.payment_type} {r.order_id}", [(acct, r.amount_incl_gst, cp), ("2350", -r.amount_incl_gst, r.order_id)])
        if acct != "1000":
            B.ar(r.payment_id, acct, cp, r.payment_date, r.payment_date + pd.Timedelta(days=lag), r.amount_incl_gst)
    # order completion (hand-off) -> revenue
    ful = O[(O.status == "Fulfilled") & (O.fulfilled_date >= START_TS)]
    pos_pay = pay[pay.amount_incl_gst > 0]
    paid_by_order = pos_pay[~pos_pay.payment_type.str.startswith("Trade account settlement")].groupby("order_id").amount_incl_gst.sum()
    lg = L.groupby("order_id")
    for oid, o in ful.iterrows():
        g = lg.get_group(oid)
        net = r2(g.net_sales_cad.sum())
        gst = r2(o.gst_cad)
        plan, agent = r2(o.protection_plan_cad), r2(o.agent_delivery_fee_cad)
        total = r2(net + gst + plan + agent)
        paid = r2(paid_by_order.get(oid, 0.0))
        lines = [("2350", paid, oid)]
        if total - paid > 0.004:
            lines.append(("1120", r2(total - paid), oid))
            B.ar(f"INV-{oid}", "1120", oid, o.fulfilled_date, o.fulfilled_date + pd.Timedelta(days=30), total - paid)
        for cat, gg in g.groupby("category"):
            lines.append((P.REV_ACCT[cat], -r2(gg.gross_sales_cad.sum()), None))
        disc = r2(g.gross_sales_cad.sum() - g.net_sales_cad.sum())
        lines += [("4900", disc, None), ("2300", -gst, None)]
        if plan:
            com = r2(plan * P.PLAN_COMMISSION)
            lines += [("4100", -com, None), ("2370", -r2(plan - com), "Protection-plan insurer")]
        if agent:
            lines.append(("2360", -agent, "Partner carrier"))
        cogs = r2(g.cogs_cad.sum())
        lines += [("5000", cogs, None), ("1210", -cogs, None)]
        B.je("SAL", o.fulfilled_date, "Order completion", oid, f"Hand-off {o.order_type} order {oid} ({o.fulfillment_method})", lines)
    # cancellations
    can = O[(O.status == "Cancelled") & (O.cancel_date >= START_TS)]
    for oid, o in can.iterrows():
        paid = r2(pos_pay[(pos_pay.order_id == oid) & (pos_pay.payment_date <= o.cancel_date)].amount_incl_gst.sum())
        ref = r2(-pay[(pay.order_id == oid) & (pay.payment_type == "Refund on cancellation")].amount_incl_gst.sum())
        fee = r2(o.retained_cancellation_fee_cad)
        if paid == 0 and ref == 0:
            continue
        lines = [("2350", paid, oid), ("1000", -ref, oid)]
        if fee:
            lines += [("4300", -fee, None), ("2300", -r2(paid - ref - fee), None)]
        B.je("CAN", o.cancel_date, "Cancellations", oid, f"Order cancelled: {o.cancel_reason}", lines)
    # returns (refund less 15% restocking fee)
    for r in T["returns"].itertuples():
        n = r2(r.net_sales_returned_cad)
        fee = r2(r.restocking_fee_cad)
        refund = r2(r.refund_incl_gst_cad)
        B.je("RET", r.return_date, "Returns", r.return_id, f"Return {r.line_id} (15% restocking fee)",
             [("4910", n, None), ("2300", r2(refund + fee - n), None), ("1000", -refund, r.order_id), ("4200", -fee, None)])


def post_purchasing_and_inventory(B: Book, T):
    po = T["pos"]
    rec = po[(po.received_date >= START_TS) & (po.received_date <= END_TS) & (po.qty_received > 0)]
    for r in rec.itertuples():
        v = r2(r.qty_received * r.unit_cost_cad)
        inv = "1210" if r.po_type in ("Custom", "Special order") else "1200"
        frt = r2(v * P.FREIGHT_IN_RATE)
        gst = r2((v + frt) * P.GST_RATE)
        tot = r2(v + frt + gst)
        B.je("RCV", r.received_date, "Purchasing", r.po_id, f"{r.po_type} receipt {r.product_id}",
             [(inv, v, r.supplier_id), ("5200", frt, "Inbound freight"), ("1400", gst, r.supplier_id), ("2000", -tot, r.supplier_id)])
        B.ap(r.po_id, "2000", r.supplier_id, r.received_date, r.received_date + pd.Timedelta(days=P.SUPPLIER_TERMS_DAYS), tot)
    fee = po[(po.status == "Cancelled") & (po.supplier_cancellation_fee_cad.fillna(0) > 0) & (po.cancel_date >= START_TS)]
    for r in fee.itertuples():
        f = r2(r.supplier_cancellation_fee_cad)
        g = r2(f * P.GST_RATE)
        B.je("SCF", r.cancel_date, "Purchasing", r.po_id, "Supplier cancellation fee (custom order cancelled)",
             [("5200", f, r.supplier_id), ("1400", g, r.supplier_id), ("2000", -r2(f + g), r.supplier_id)])
        B.ap(f"SCF-{r.po_id}", "2000", r.supplier_id, r.cancel_date, r.cancel_date + pd.Timedelta(days=P.SUPPLIER_TERMS_DAYS), f + g)
    mv = T["moves"]
    mv = mv[(mv.movement_date >= START_TS) & (mv.movement_type != "OPENING_BALANCE")]
    for d, g in mv[mv.movement_type == "ALLOCATE"].groupby("movement_date"):
        v = r2(g[g.inventory_state == "allocated"].value_cad.sum())
        B.je("ALC", d, "Inventory", f"ALC-{d:%Y%m%d}", "Stock reserved for customer orders", [("1210", v, None), ("1200", -v, None)])
    for ref, g in mv[mv.movement_type == "CANCEL_RELEASE"].groupby("reference_id"):
        st, al = r2(g[g.inventory_state == "stock"].value_cad.sum()), r2(g[g.inventory_state == "allocated"].value_cad.sum())
        B.je("REL", g.movement_date.iloc[0], "Inventory", ref, "Cancelled order goods returned to stock (standard-cost variance)",
             [("1200", st, None), ("1210", al, None), ("5100", -r2(st + al), None)])
    for r in mv[mv.movement_type == "CUSTOMER_RETURN"].itertuples():
        B.je("RTS", r.movement_date, "Inventory", r.reference_id, "Returned goods back to stock", [("1200", r2(r.value_cad), None), ("5000", -r2(r.value_cad), None)])
    for r in mv[mv.movement_type.isin(["WRITE_OFF_DAMAGED", "CYCLE_COUNT_ADJ"])].itertuples():
        B.je("ADJ", r.movement_date, "Inventory", r.reference_id, r.movement_type, [("5100", -r2(r.value_cad), None), ("1200", r2(r.value_cad), None)])


def post_opex(B: Book, T, acc_pay_open):
    o = opex_frame(T)
    for m, r in o.iterrows():
        me = m.end_time.normalize()
        payroll = r2(sum(r[c] for c, a, v, k in P.OPEX_MAP if k == "payroll"))
        B.je("PRL", me, "Payroll", f"PRL-{m}", "Payroll & commission accrual", [(a, r2(r[c]), None) for c, a, v, k in P.OPEX_MAP if k == "payroll"] + [("2100", -payroll, None)])
        first = r2(payroll * P.PAYROLL_FIRST_HALF)
        B.je("PRL", m.start_time + pd.Timedelta(days=14), "Payroll", f"PAY1-{m}", "Payroll run 1", [("2100", first, None), ("1000", -first, None)])
        prev = acc_pay_open if m == MONTHS[0] else r2(o.loc[m - 1, [c for c, a, v, k in P.OPEX_MAP if k == "payroll"]].sum() - r2(o.loc[m - 1, [c for c, a, v, k in P.OPEX_MAP if k == "payroll"]].sum() * P.PAYROLL_FIRST_HALF))
        B.je("PRL", m.start_time + pd.Timedelta(days=4), "Payroll", f"PAY2-{m - 1}", "Payroll run 2 (prior month)", [("2100", prev, None), ("1000", -prev, None)])
        for c, a, v, k in P.OPEX_MAP:
            amt = r2(r[c])
            g = r2(amt * P.GST_RATE) if a in P.GST_TAXABLE_OPEX else 0.0
            if k == "rent":
                B.je("OPX", m.start_time, "Operating expenses", f"{a}-{m}", P.ACCOUNTS[a]["name"], [(a, amt, v), ("1400", g, v), ("1000", -r2(amt + g), v)])
            elif k == "prepaid":
                if m.month == 1:
                    prem = r2(amt * 12)
                    B.je("INS", m.start_time + pd.Timedelta(days=1), "Prepaid expenses", f"INSP-{m.year}", "Annual insurance premium", [("1300", prem, v), ("1000", -prem, v)])
                B.je("INS", me, "Prepaid expenses", f"INSA-{m}", "Insurance amortisation", [(a, amt, v), ("1300", -amt, v)])
            elif k == "vendor":
                B.je("OPX", me, "Operating expenses", f"{a}-{m}", P.ACCOUNTS[a]["name"], [(a, amt, v), ("1400", g, v), ("2010", -r2(amt + g), v)])
                B.ap(f"{a}-{m}", "2010", v, me, (m + 1).start_time + pd.Timedelta(days=P.OPEX_PAY_DAY - 1), amt + g)


def post_capex_dep(B: Book):
    for aid, desc, acct, acq, cost, life, acc0 in P.FIXED_ASSETS:
        if pd.Timestamp(acq) > OB_DATE:
            B.je("CAP", acq, "Capital expenditure", aid, desc, [(acct, cost, None), ("1400", r2(cost * P.GST_RATE), None), ("1000", -r2(cost * (1 + P.GST_RATE)), None)])
    dep = fixed_asset_schedule()
    for m, g in dep.groupby("month"):
        amt = r2(g.depreciation.sum())
        B.je("DPR", m.end_time.normalize(), "Depreciation", f"DPR-{m}", "Monthly straight-line depreciation", [("6900", amt, None), ("1590", -amt, None)])


def post_settlements_and_agent_remittances(B: Book, T):
    ar = pd.DataFrame(B.ar_items)
    ar = ar[(ar.due_date <= END_TS) & (ar.account != "1120")]                    # trade accounts settle through their payment records
    for (acct, d, cp), g in ar.groupby(["account", "due_date", "counterparty"]):
        amt = r2(g.amount.sum())
        if acct == "1110":
            fee = r2(amt * P.FIN_PARTNER_FEE)
            B.je("SET", d, "Collections", f"SET-{acct}-{d:%Y%m%d}", "Financing-partner settlement (net of merchant fee)",
                 [("1000", r2(amt - fee), cp), ("6430", fee, cp), (acct, -amt, cp)])
        else:
            B.je("SET", d, "Collections", f"SET-{acct}-{d:%Y%m%d}", f"Card settlement ({len(g)} items)", [("1000", amt, cp), (acct, -amt, cp)])
    ap = pd.DataFrame(B.ap_items)
    for (acct, d, cp), g in ap[ap.due_date <= END_TS].groupby(["account", "due_date", "counterparty"]):
        amt = r2(g.amount.sum())
        B.je("PAY", d, "Supplier payments", f"PAY-{cp}-{d:%Y%m%d}", f"Payment to {cp} ({len(g)} invoices)", [(acct, amt, cp), ("1000", -amt, cp)])


def _frame(B: Book) -> pd.DataFrame:
    gl = pd.DataFrame(B.rows, columns=["je_id", "date", "account", "debit", "credit", "source", "reference", "counterparty", "description", "is_closing"])
    gl["amount"] = gl.debit - gl.credit
    gl["month"] = gl.date.dt.to_period("M")
    return gl


def income_tax(x):
    x = max(0.0, x)
    return P.TAX_SMALL_RATE * min(x, P.SMALL_BUSINESS_LIMIT) + P.TAX_GENERAL_RATE * max(0.0, x - P.SMALL_BUSINESS_LIMIT)


def post_treasury_tax_and_close(B: Book, T):
    """Agent remittances, GST, interest, principal, tax, daily revolver sweep, month-end cash band, dividends, close."""
    prime = prime_rate(T["econ"])
    pmt = r2(P.TERM_LOAN["balance_open"] / P.TERM_LOAN["months_remaining"])
    pnl_accts = sorted(k for k, v in P.ACCOUNTS.items() if v["type"] in P.PNL_TYPES)
    # agent liabilities remitted on the 10th (carrier) / 15th (insurer) of the following month
    base = _frame(B)
    for acct, day, cp in (("2360", 10, "Partner carrier"), ("2370", 15, "Protection-plan insurer")):
        mm = base[base.account == acct].groupby("month").amount.sum()
        for m, v in mm.items():
            due = (m + 1).start_time + pd.Timedelta(days=day - 1)
            if due <= END_TS and v:
                B.je("AGT", due, "Agent remittances", f"{acct}-{m}", f"Remit amounts collected as agent ({cp})", [(acct, -r2(v), cp), ("1000", r2(v), cp)])
    base = _frame(B)
    by_m = base.groupby(["month", "account"]).amount.sum().unstack(fill_value=0.0).reindex(columns=list(P.ACCOUNTS), fill_value=0.0)
    by_m = by_m.reindex(pd.period_range("2023-12", END, freq="M"), fill_value=0.0)
    cash_day = base[base.account == "1000"].groupby("date").amount.sum()
    n0 = len(B.rows)
    R = P.REVOLVER

    def tre(f):
        out = defaultdict(float)
        for r in B.rows[n0:]:
            if not r[9] and f(r[1].to_period("M")):
                out[r[2]] += r[3] - r[4]
        return out

    step = lambda x: float(np.ceil(round(x / R["step"], 9)) * R["step"])
    cash = r2(cash_day[cash_day.index <= OB_DATE].sum())
    term_bal, rev_bal = P.TERM_LOAN["balance_open"], 0.0
    ytd_tax, tax_prior = 0.0, 38000.0
    lcf = 0.0                                                    # non-capital loss carry-forward available at 1 January
    log = []
    for m in MONTHS:
        me = m.end_time.normalize()
        rate_t, rate_r = prime[m] + P.TERM_LOAN["spread"], prime[m] + R["spread"]
        rev_days, min_day, intra = 0.0, np.inf, 0.0
        for d in pd.date_range(m.start_time, me):
            cash = r2(cash + cash_day.get(d, 0.0))
            if d < me and cash < R["intramonth_floor"] and rev_bal < R["limit"]:
                draw = min(r2(R["limit"] - rev_bal), step(R["intramonth_target"] - cash))
                B.je("REV", d, "Financing", f"REVD-{d:%Y%m%d}", "Revolver draw (intra-month sweep)", [("1000", draw, "Lender"), ("2600", -draw, "Lender")])
                cash, rev_bal, intra = r2(cash + draw), r2(rev_bal + draw), intra + draw
            min_day = min(min_day, cash)
            if d < me:
                rev_days += rev_bal
        if m.month in (1, 4, 7, 10) and m > MONTHS[0]:
            q = (m - 1).asfreq("Q")
            qm = by_m[[pm.asfreq("Q") == q for pm in by_m.index]]
            col, itc = -r2(qm["2300"].sum()), r2(qm["1400"].sum())
            B.je("GST", me, "GST remittance", f"GST-{q}", f"GST return {q}", [("2300", col, "Canada Revenue Agency"), ("1400", -itc, "Canada Revenue Agency"),
                                                                              ("1000", -r2(col - itc), "Canada Revenue Agency")])
            cash = r2(cash - (col - itc))
        i_t = r2(term_bal * rate_t / 12)
        p_amt = min(pmt, r2(term_bal))
        B.je("INT", me, "Financing", f"INT-TL-{m}", f"Term loan interest @ {rate_t:.2%}", [("7000", i_t, "Lender"), ("1000", -i_t, "Lender")])
        if p_amt:
            B.je("TLP", me, "Financing", f"TLP-{m}", "Term loan principal", [("2700", p_amt, "Lender"), ("1000", -p_amt, "Lender")])
            term_bal = r2(term_bal - p_amt)
        i_r = r2((rev_days + rev_bal) / m.days_in_month * rate_r / 12)
        if i_r:
            B.je("INT", me, "Financing", f"INT-RV-{m}", f"Revolver interest @ {rate_r:.2%} (average daily balance)", [("7010", i_r, "Lender"), ("1000", -i_r, "Lender")])
        cash = r2(cash - i_t - p_amt - i_r)
        if m.month == 3 and tax_prior > 0:
            B.je("TAX", me, "Income tax", f"TAXPAY-{m.year - 1}", f"Income tax paid for {m.year - 1}", [("2400", tax_prior, "Canada Revenue Agency"), ("1000", -tax_prior, "Canada Revenue Agency")])
            cash = r2(cash - tax_prior)
            tax_prior = 0.0
        in_ytd = lambda pm: pm.year == m.year and pm <= m
        t = tre(in_ytd)
        yb = by_m.loc[[pm for pm in by_m.index if in_ytd(pm)]]
        pbt = -r2(sum(yb[a].sum() + t.get(a, 0.0) for a in pnl_accts if a != "8000"))
        need = r2(income_tax(pbt - lcf))
        if r2(need - ytd_tax):
            B.je("TAX", me, "Income tax", f"TAXPROV-{m}", "Income tax provision (YTD true-up; small-business rate on first $500K)",
                 [("8000", r2(need - ytd_tax), None), ("2400", -r2(need - ytd_tax), None)])
            ytd_tax = need
        draw = repay = div = 0.0
        if cash < R["min_cash"]:
            draw = min(r2(R["limit"] - rev_bal), step(R["target_cash"] - cash))
        elif cash > R["repay_above"] and rev_bal > 0:
            repay = min(rev_bal, float(np.floor(round((cash - R["target_cash"]) / R["step"], 9)) * R["step"]))
        if draw:
            B.je("REV", me, "Financing", f"REVD-{m}", "Revolver draw (month-end cash band)", [("1000", draw, "Lender"), ("2600", -draw, "Lender")])
        if repay:
            B.je("REV", me, "Financing", f"REVR-{m}", "Revolver repayment", [("2600", repay, "Lender"), ("1000", -repay, "Lender")])
        rev_bal = r2(rev_bal + draw - repay)
        cash = r2(cash + draw - repay)
        if m.month == 12:
            ni_year = pbt - need
            if rev_bal == 0 and ni_year > 0:
                div = float(np.floor(min(P.DIVIDEND["payout"] * ni_year, max(0.0, cash - P.DIVIDEND["cash_floor"])) / 1000) * 1000)
            if div > 0:
                B.je("DIV", me, "Equity", f"DIV-{m.year}", "Dividend to shareholders", [("3300", div, "Shareholders"), ("1000", -div, "Shareholders")])
                cash = r2(cash - div)
            t = tre(lambda pm: pm.year == m.year)
            yb = by_m.loc[[pm for pm in by_m.index if pm.year == m.year]]
            bal = {a: r2(yb[a].sum() + t.get(a, 0.0)) for a in pnl_accts + ["3300"]}
            bal = {a: v for a, v in bal.items() if v}
            B.je("CLS", me, "Year-end close", f"CLOSE-{m.year}", f"Close FY{m.year}", [(a, -v, None) for a, v in bal.items()] + [("3200", r2(sum(bal.values())), None)], closing=True)
            lcf = max(0.0, lcf - pbt) if pbt > 0 else lcf - pbt
            tax_prior, ytd_tax = ytd_tax, 0.0
        log.append(dict(month=str(m), prime_rate=prime[m], term_rate=rate_t, revolver_rate=rate_r, term_interest=i_t, revolver_interest=i_r, term_principal=p_amt,
                        term_balance=term_bal, revolver_intramonth_draws=intra, revolver_draw=draw, revolver_repay=repay, revolver_balance=rev_bal, dividend=div,
                        month_end_cash=cash, min_daily_cash=min_day, pbt_ytd=pbt, tax_ytd=need, loss_carryforward=lcf, data_status="SIMULATED"))
    return pd.DataFrame(log)


def build():
    T = load_operational()
    B = Book()
    acc_pay = post_opening(B, T)
    post_customer_flows(B, T)
    post_purchasing_and_inventory(B, T)
    post_opex(B, T, acc_pay)
    post_capex_dep(B)
    post_settlements_and_agent_remittances(B, T)
    treasury = post_treasury_tax_and_close(B, T)
    gl = _frame(B).sort_values(["date", "je_id"], kind="stable").reset_index(drop=True)
    gl.insert(0, "line_no", np.arange(1, len(gl) + 1))
    gl["account_name"] = gl.account.map(lambda a: P.ACCOUNTS[a]["name"])
    gl["data_status"] = "SIMULATED"
    return dict(gl=gl, ar_items=pd.DataFrame(B.ar_items), ap_items=pd.DataFrame(B.ap_items), treasury=treasury, T=T)
