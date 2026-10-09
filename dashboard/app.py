"""Prairie Home Furnishings Analytics - retail BI, inventory, order-fulfilment and financial-intelligence dashboard.

Run:  streamlit run dashboard/app.py
Demonstration developed by VisiVault Analytics Ltd. Synthetic demonstration data - not actual company financial or
operational records. Prairie Home Furnishings is a fictional retailer.
"""
import json
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import APP_NAME, ATTRIBUTION, BRAND, DB_PATH, FIN_OUT, REPORTS, SYNTHETIC_LABEL, TABLES  # noqa: E402
from src.finance import forecast as F  # noqa: E402
from src.finance import ratios as R  # noqa: E402

st.set_page_config(page_title=APP_NAME, page_icon="🛋️", layout="wide")
FIN = [BRAND["brand"], BRAND["teal"], BRAND["accent"], BRAND["warn"]]          # validated categorical order (4 slots)
UP, DOWN, TOT = BRAND["teal"], BRAND["bad"], BRAND["navy"]
PLOT = dict(template="plotly_white", colorway=FIN, font=dict(family="Inter, Helvetica, Arial", size=12), margin=dict(l=10, r=10, t=50, b=10),
            legend=dict(orientation="h", y=-0.2))
st.markdown(f"""<style>
 .block-container {{padding-top: 1.1rem; max-width: 1400px;}}
 .vv-banner {{background: linear-gradient(90deg, {BRAND['navy']} 0%, {BRAND['brand_dark']} 100%); color:#fff; padding:14px 20px; border-radius:12px;
             display:flex; flex-wrap:wrap; gap:10px; justify-content:space-between; align-items:center; margin-bottom:10px;}}
 .vv-banner h1 {{font-size:1.3rem; margin:0; color:#fff;}} .vv-banner span {{font-size:.8rem; opacity:.85}}
 .vv-synth {{background:#fff4e5; border:1px solid #f5c37a; color:#7a4a00; padding:6px 12px; border-radius:8px; font-size:.8rem; font-weight:600;}}
 .kpi {{background:#fff; border:1px solid rgba(11,15,25,.08); border-radius:12px; padding:11px 13px; box-shadow:0 1px 2px rgba(0,0,0,.04); margin-bottom:8px;}}
 .kpi .l {{font-size:.72rem; color:{BRAND['muted']}; text-transform:uppercase; letter-spacing:.04em;}}
 .kpi .v {{font-size:1.35rem; font-weight:700; color:{BRAND['navy']}; margin-top:2px;}} .kpi .d {{font-size:.76rem; margin-top:2px;}}
 .note {{background:{BRAND['brand_light']}; border-left:4px solid {BRAND['brand']}; padding:9px 13px; border-radius:6px; margin:6px 0; font-size:.9rem;}}
 @media (max-width: 640px) {{ .kpi .v {{font-size:1.1rem;}} .vv-banner h1 {{font-size:1.05rem;}} }}
</style>""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------------------------- data
@st.cache_data
def sql(q, params=None):
    con = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(q, con, params=params or [])
    finally:
        con.close()


@st.cache_data
def table(name, **kw):
    p = TABLES / f"{name}.csv"
    return pd.read_csv(p, **kw) if p.exists() else pd.DataFrame()


@st.cache_data
def findings():
    p = TABLES / "findings.json"
    return json.loads(p.read_text()) if p.exists() else {"metrics": {}, "findings": {}}


@st.cache_data
def lines():
    s = sql("SELECT * FROM sales_transactions WHERE transaction_date >= '2024-01-01'")
    s["transaction_date"] = pd.to_datetime(s.transaction_date)
    s["month"] = s.transaction_date.dt.to_period("M").dt.to_timestamp()
    return s


@st.cache_data
def fbase():
    js = json.loads((TABLES / "fin_forecast_base.json").read_text())
    dv = pd.DataFrame(js["drivers"]).T
    dv.columns = range(1, F.H + 1)
    return {"A": js["A"], "drivers": dv, "opening": js["opening"]}


def stmt(name):
    d = table(f"fin_{name}", index_col=0)
    lab = d["label"].to_dict() if "label" in d else {}
    return d.drop(columns=[c for c in ("label", "data_status") if c in d.columns]), lab


def money(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    s = "-" if v < 0 else ""
    v = abs(v)
    return f"{s}${v / 1e6:,.2f}M" if v >= 1e6 else f"{s}${v:,.0f}"


def acct(v):
    if pd.isna(v):
        return ""
    return "-" if abs(v) < 0.5 else (f"({abs(v):,.0f})" if v < 0 else f"{v:,.0f}")


def fmt_table(df, labels=None):
    x = df.copy()
    if labels:
        x.index = [labels.get(k, k) for k in x.index]
    return pd.DataFrame({c: [acct(v) for v in x[c]] for c in x.columns}, index=x.index)


def esc(t):
    return str(t).replace("$", "\\$")


def kpis(items, per_row=6):
    for i in range(0, len(items), per_row):
        cols = st.columns(min(per_row, len(items) - i))
        for c, (label, value, delta, good) in zip(cols, items[i:i + per_row]):
            color = BRAND["good"] if good is True else (BRAND["bad"] if good is False else BRAND["muted"])
            c.markdown(f"<div class='kpi'><div class='l'>{label}</div><div class='v'>{value}</div><div class='d' style='color:{color}'>{delta or '&nbsp;'}</div></div>",
                       unsafe_allow_html=True)


def show(fig, h=380):
    fig.update_layout(height=h, **PLOT)
    st.plotly_chart(fig, use_container_width=True)


def note(text):
    if text:
        st.markdown(f"<div class='note'>{text}</div>", unsafe_allow_html=True)


def download(df, name, label="Download CSV", index=False):
    st.download_button(label, df.to_csv(index=index).encode(), file_name=f"{name}.csv", mime="text/csv", key=f"dl_{name}")


def download_file(path, label):
    p = Path(path)
    if p.exists():
        st.download_button(label, p.read_bytes(), file_name=p.name, key=f"f_{p.name}")


def waterfall(labels, values, measures, title):
    fig = go.Figure(go.Waterfall(x=labels, y=values, measure=measures, text=[f"{v / 1000:,.0f}K" for v in values], textposition="outside",
                                 increasing=dict(marker_color=UP), decreasing=dict(marker_color=DOWN), totals=dict(marker_color=TOT)))
    fig.update_layout(title=title, yaxis_tickprefix="$", showlegend=False)
    return fig


# ----------------------------------------------------------------------------------------------- layout
st.markdown(f"""<div class='vv-banner'><div><h1>{APP_NAME}</h1><span>{ATTRIBUTION} | Fictional Calgary furniture retailer | Data Jan 2024 - Sep 2026</span></div>
<div class='vv-synth'>⚠ {SYNTHETIC_LABEL}</div></div>""", unsafe_allow_html=True)
PAGES = ["1. Executive Overview", "2. Sales Performance", "3. Product Profitability", "4. Inventory Intelligence", "5. Custom Order Tracking",
         "6. Supplier & Fulfillment Analytics", "7. Customer Intelligence", "8. Design Consultation Analytics", "9. Income Statement", "10. Balance Sheet",
         "11. Cash Flow Statement", "12. Financial Ratios", "13. Sales & Cash Flow Forecasting", "14. Business Scenario Simulator"]
S_ALL = lines()
with st.sidebar:
    st.markdown(f"<div style='font-weight:800;font-size:1.05rem;color:{BRAND['brand_dark']}'>VisiVault Analytics</div>", unsafe_allow_html=True)
    page = st.radio("Navigate", PAGES, label_visibility="collapsed")
    st.divider()
    st.caption("FILTERS (pages 1-3)")
    dmin, dmax = S_ALL.transaction_date.min().date(), S_ALL.transaction_date.max().date()
    dr = st.date_input("Order date range", (dmin, dmax), min_value=dmin, max_value=dmax)
    cats = st.multiselect("Category", sorted(S_ALL.category.unique()), default=[])
    chans = st.multiselect("Sales channel", sorted(S_ALL.sales_channel.unique()), default=[])
    ftype = st.multiselect("Fulfilment type", sorted(S_ALL.fulfillment_type.unique()), default=[])
    st.divider()
    st.caption("Prairie Home Furnishings is fictional. Product categories, manufacturers and list prices reflect a public Calgary furniture catalogue (Oct 2026); "
               "every order, cost, customer and financial figure is synthetic.")
d0, d1 = (pd.Timestamp(dr[0]), pd.Timestamp(dr[1])) if isinstance(dr, tuple) and len(dr) == 2 else (pd.Timestamp(dmin), pd.Timestamp(dmax))
S = S_ALL[(S_ALL.transaction_date >= d0) & (S_ALL.transaction_date <= d1) & (S_ALL.line_status != "Cancelled")]
for col, sel in (("category", cats), ("sales_channel", chans), ("fulfillment_type", ftype)):
    if sel:
        S = S[S[col].isin(sel)]
M, FD = findings()["metrics"], findings()["findings"]


# ----------------------------------------------------------------------------------------------- pages
def p_exec():
    is_m, _ = stmt("income_statement_monthly")
    bs_m, _ = stmt("balance_sheet_monthly")
    ttm = [c for c in is_m.columns if c >= "2025-10"]
    t = is_m[ttm].sum(axis=1)
    kpis([("Written sales (TTM)", money(M.get("ttm_net_sales")), f"{M.get('ttm_growth', 0):+.1%} vs prior 12m", M.get("ttm_growth", 0) >= 0),
          ("Net revenue recognised (TTM)", money(t.net_rev), "at hand-off", None), ("Gross margin (TTM)", f"{t.gross_profit / t.net_rev:.1%}", "after freight & variances", None),
          ("EBITDA (TTM)", money(t.ebitda), f"{t.ebitda / t.net_rev:.1%} margin", t.ebitda > 0), ("Net income (TTM)", money(t.net_income), f"{t.net_income / t.net_rev:.1%}", t.net_income > 0),
          ("Cash 30-Sep-2026", money(bs_m.at["cash", "2026-09"]), "no revolver drawn", True),
          ("Open orders", f"{M.get('open_orders', 0):,.0f}", f"{M.get('open_custom', 0):,.0f} custom", None), ("Customer deposits held", money(bs_m.at["deposits", "2026-09"]), "contract liabilities", None),
          ("Custom ready on time", f"{M.get('custom_on_time', 0):.0%}", "vs promised date", M.get("custom_on_time", 0) > 0.7),
          ("Consult conversion", f"{M.get('consult_conv', 0):.0%}", f"AOV {money(M.get('aov_consult'))}", None),
          ("Stockout sales lost (TTM)", money(M.get("lost_sales_ttm")), "estimated", False), ("Aged stock >180 d", money(M.get("aged_180")), "at cost", False)])
    m = S.groupby("month").agg(written=("net_sales_cad", "sum")).reset_index()
    rec = is_m.loc["net_sales"].rename("recognised").reset_index().rename(columns={"index": "month"})
    rec["month"] = pd.to_datetime(rec.month)
    mm = m.merge(rec, on="month", how="left")
    fig = go.Figure([go.Bar(x=mm.month, y=mm.written, name="Written sales (order date)", marker_color=FIN[0]),
                     go.Bar(x=mm.month, y=mm.recognised, name="Net sales recognised (hand-off date)", marker_color=FIN[1])])
    fig.update_layout(barmode="group", title="Bookings vs recognised revenue - deposits bridge the gap", yaxis_tickprefix="$")
    show(fig, 400)
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Headline findings")
        for k in ["sales", "custom", "orders", "fulfilment", "inventory", "consults"]:
            if k in FD:
                st.markdown(f"- {esc(FD[k])}")
    with c2:
        st.subheader("Priority actions")
        rc = table("recommendations")
        for r in rc.head(6).itertuples():
            note(f"<b>{r.rank}. {r.title}</b><br>{r.area} · pre-tax impact {money(r.pretax_profit_impact_12m)} · cash {money(r.cash_impact_12m)} · {r.effort} effort")
        if len(rc):
            download(rc, "recommendations", "Download all recommendations")
    st.caption("Impacts are illustrative estimates from the synthetic model, not guaranteed results.")


def p_sales():
    st.subheader("Sales performance (written sales by order date)")
    tx = S.groupby("order_id").net_sales_cad.sum()
    kpis([("Net sales", money(S.net_sales_cad.sum()), f"{S.transaction_date.min():%b %Y} - {S.transaction_date.max():%b %Y}", None),
          ("Gross profit", money(S.gross_profit_cad.sum()), f"GM {S.gross_profit_cad.sum() / max(S.net_sales_cad.sum(), 1):.1%}", None),
          ("Orders", f"{S.order_id.nunique():,}", f"ATV {money(tx.mean() if len(tx) else 0)}", None), ("Units", f"{int(S.units.sum()):,}", f"{len(S):,} lines", None),
          ("Average discount", f"{(1 - S.net_sales_cad.sum() / max(S.gross_sales_cad.sum(), 1)):.1%}", "of gross", None)], per_row=5)
    gran = st.radio("Period", ["Monthly", "Quarterly", "Yearly"], horizontal=True)
    key = {"Monthly": S.month, "Quarterly": S.transaction_date.dt.to_period("Q").astype(str), "Yearly": S.transaction_date.dt.year.astype(str)}[gran]
    g = S.groupby([key, "category"]).net_sales_cad.sum().reset_index()
    g.columns = ["period", "category", "net_sales"]
    show(px.bar(g, x="period", y="net_sales", color="category", title=f"{gran} net sales by category", labels={"net_sales": "Net sales (CAD)", "period": ""},
                color_discrete_sequence=px.colors.qualitative.Safe), 420)
    c1, c2 = st.columns(2)
    with c1:
        ch = S.groupby("sales_channel").agg(net_sales=("net_sales_cad", "sum"), orders=("order_id", "nunique"), gp=("gross_profit_cad", "sum")).reset_index()
        ch["ATV"], ch["GM %"] = ch.net_sales / ch.orders, ch.gp / ch.net_sales * 100
        show(px.bar(ch.sort_values("net_sales"), x="net_sales", y="sales_channel", orientation="h", text=ch.sort_values("net_sales")["ATV"].map(lambda v: f"ATV ${v:,.0f}"),
                    title="Net sales by channel (label = average transaction value)", color_discrete_sequence=[FIN[0]]), 360)
    with c2:
        atv = S.groupby(["month", "order_id"]).net_sales_cad.sum().groupby("month").mean().reset_index()
        show(px.line(atv, x="month", y="net_sales_cad", markers=True, title="Average transaction value by month", labels={"net_sales_cad": "ATV (CAD)", "month": ""},
                     color_discrete_sequence=[FIN[2]]), 360)
    st.markdown("**Promotion effectiveness** (incremental vs a same-weekday baseline from the five weeks before each event)")
    pe = table("promotion_effectiveness")
    if len(pe):
        show(px.bar(pe, x="promotion", y=["incremental_gross_profit", "discount_cost"], barmode="group", title="Incremental gross profit vs discount cost by event",
                    labels={"value": "CAD", "promotion": "", "variable": ""}), 400)
        st.dataframe(pe[["promotion", "days", "net_sales", "baseline_net_sales", "lift_pct", "incremental_gross_profit", "discount_cost"]].round(1), use_container_width=True, hide_index=True)
        download(pe, "promotion_effectiveness")
    rp = table("sales_rep_performance")
    st.markdown("**Sales associate performance**")
    st.dataframe(rp.drop(columns="data_status").round(2), use_container_width=True, hide_index=True)
    download(S.drop(columns=["month"]), "sales_lines_filtered", "Download filtered sales lines")
    note(esc(FD.get("promotions", "")))
    note(esc(FD.get("reps", "")))


def p_product():
    st.subheader("Product profitability")
    c1, c2 = st.columns(2)
    cat = S.groupby("category").agg(net_sales=("net_sales_cad", "sum"), gp=("gross_profit_cad", "sum")).reset_index()
    cat["GM %"] = cat.gp / cat.net_sales * 100
    with c1:
        show(px.scatter(cat, x="net_sales", y="GM %", size="gp", text="category", title="Category sales vs gross margin (bubble = gross profit)",
                        color_discrete_sequence=[FIN[0]]).update_traces(textposition="top center"), 420)
    with c2:
        mf = S.groupby("manufacturer").agg(net_sales=("net_sales_cad", "sum"), gp=("gross_profit_cad", "sum")).reset_index().sort_values("net_sales").tail(15)
        mf["GM %"] = mf.gp / mf.net_sales * 100
        show(px.bar(mf, x="net_sales", y="manufacturer", orientation="h", color="GM %", color_continuous_scale="Blues", title="Top manufacturers (colour = GM %)"), 420)
    cu = S.groupby("fulfillment_type").agg(net_sales=("net_sales_cad", "sum"), gp=("gross_profit_cad", "sum"), lines=("line_id", "count")).reset_index()
    cu["GM %"] = cu.gp / cu.net_sales * 100
    ot = table("order_type_performance")
    st.markdown("**Custom (made to order) vs ready-made**")
    c1, c2 = st.columns(2)
    c1.dataframe(cu.round(1), use_container_width=True, hide_index=True)
    c2.dataframe(ot.drop(columns="data_status").round(1), use_container_width=True, hide_index=True)
    note(esc(FD.get("custom", "")))
    sku = table("product_profitability")
    view = st.radio("Show", ["Best sellers", "Lowest margin", "Slow movers (lowest units)"], horizontal=True)
    s2 = sku[sku.units > 0]
    s2 = {"Best sellers": s2.sort_values("net_sales", ascending=False), "Lowest margin": s2.sort_values("gm_pct"), "Slow movers (lowest units)": s2.sort_values("units")}[view]
    st.dataframe(s2[["product_name", "manufacturer", "category", "subcategory", "fulfillment_type", "list_price_cad", "units", "net_sales", "gross_profit", "gm_pct", "avg_discount"]]
                 .head(40).round(2), use_container_width=True, hide_index=True, height=380)
    download(sku, "product_profitability")
    st.markdown("**Cross-selling and bundling opportunities** (subcategory pairs bought in the same order)")
    mb = table("cross_sell_pairs")
    mb = mb[mb.orders_together >= 40].sort_values("lift", ascending=False)
    st.dataframe(mb[["antecedent", "consequent", "orders_together", "confidence_pct", "lift"]].head(20).round(2), use_container_width=True, hide_index=True)
    note(esc(FD.get("cross_sell", "")))


def p_inventory():
    st.subheader("Inventory intelligence (stocked ready-made goods vs goods allocated to customer orders)")
    inv = table("inventory_intelligence")
    kpis([("Stocked inventory", money(M.get("stock_value")), "at cost, 30-Sep-2026", None), ("Allocated to customers", money(M.get("alloc_value")), "custom & reserved - already sold", None),
          ("Inventory turnover", f"{M.get('turnover', 0):.1f}x", "stocked, TTM", None), ("Overstocked SKUs", f"{M.get('overstock_n', 0):.0f}", f"{money(M.get('overstock_value'))} >180 d cover", False),
          ("Aged >180 days", money(M.get("aged_180")), "FIFO age", False), ("Carrying cost", money(M.get("carrying_cost")), "22% p.a. assumption", None)])
    vs = table("inventory_value_by_state_monthly", parse_dates=["month"])
    if len(vs):
        show(px.area(vs, x="month", y=["stocked_value", "allocated_to_customers_value"], title="Inventory at cost by state", labels={"value": "CAD", "variable": ""}), 340)
    c1, c2 = st.columns(2)
    with c1:
        ag = table("inventory_aging_by_category", index_col=0).drop(columns="data_status")
        agl = ag.reset_index().melt(id_vars="category", var_name="age", value_name="value")
        show(px.bar(agl, x="value", y="category", color="age", orientation="h", title="Stock aging by category (cost)", color_discrete_sequence=px.colors.sequential.Blues[2:]), 380)
    with c2:
        ic = table("inventory_by_category")
        show(px.bar(ic, x="category", y="dio_days", title="Days inventory outstanding by category", color_discrete_sequence=[FIN[2]]), 380)
    abc = st.multiselect("ABC class", ["A", "B", "C"], default=["A", "B", "C"])
    act = st.multiselect("Action", sorted(inv.action.unique()), default=sorted(inv.action.unique()))
    v = inv[inv.abc_class.isin(abc) & inv.action.isin(act)]
    st.dataframe(v[["product_name", "manufacturer", "category", "abc_class", "on_hand_stock_units", "stock_value", "units_ttm", "turnover", "days_of_cover", "weighted_age_days",
                    "lead_time_mean_days", "safety_stock", "reorder_point_recommended", "reorder_point_current_policy", "recommended_order_now_units", "action"]].round(1),
                 use_container_width=True, hide_index=True, height=380)
    download(v, "inventory_recommendations", "Download reorder & clearance recommendations")
    note(esc(FD.get("inventory", "")))
    note(esc(FD.get("stockouts", "")))


def p_orders():
    st.subheader("Custom order tracking - Order Fulfilment Tracker")
    tr = table("open_orders_tracker", parse_dates=["order_date", "promised_ready_date", "supplier_eta", "ready_date"])
    risk = table("open_po_delay_risk")
    if len(risk):
        ln = sql("SELECT line_id, order_id FROM sales_transactions").set_index("line_id").order_id
        rk = risk.assign(order_id=risk.order_line_id.map(ln)).groupby("order_id").p_late.max()
        tr["delay_risk"] = tr.order_id.map(rk)
    kpis([("Open orders", f"{len(tr):,}", f"{(tr.order_type == 'Custom').sum()} custom", None), ("Open order value", money(tr.order_total_incl_gst_cad.sum()), "incl. GST", None),
          ("Deposits received", money(tr.deposit_paid_cad.sum()), "held as liability", None), ("Balances to collect", money(tr.balance_outstanding_cad.sum()), "due before pickup", None),
          ("Past promised date", f"{(tr.days_past_promise > 0).sum()}", "open orders", False), ("High delay risk", f"{(tr.delay_risk > 0.5).sum() if 'delay_risk' in tr else 0}", "model C p>50%", False)])
    c1, c2, c3 = st.columns(3)
    typ = c1.multiselect("Order type", sorted(tr.order_type.unique()), default=sorted(tr.order_type.unique()))
    stt = c2.multiselect("Status", sorted(tr.status.unique()), default=sorted(tr.status.unique()))
    late_only = c3.checkbox("Only past promised date")
    v = tr[tr.order_type.isin(typ) & tr.status.isin(stt)]
    if late_only:
        v = v[v.days_past_promise > 0]
    vd = v.sort_values("days_open", ascending=False).copy()
    for c in ["order_date", "promised_ready_date", "supplier_eta", "ready_date"]:
        vd[c] = vd[c].dt.date
    st.dataframe(vd.drop(columns="data_status").round(2), use_container_width=True, hide_index=True, height=380)
    download(v, "open_order_tracker", "Download order tracker")
    c1, c2 = st.columns(2)
    with c1:
        ab = tr.groupby(["aging_band", "order_type"]).size().reset_index(name="orders")
        show(px.bar(ab, x="aging_band", y="orders", color="order_type", title="Open-order aging (days since order)", category_orders={"aging_band": ["0-30", "31-60", "61-90", "91-120", ">120"]}), 360)
    with c2:
        bl = table("open_order_backlog_monthly", parse_dates=["month"])
        show(px.line(bl, x="month", y=["open_order_value_incl_gst", "deposits_held", "balances_still_to_collect"], title="Cash tied up in unfulfilled orders",
                     labels={"value": "CAD", "variable": ""}), 360)
    note(esc(FD.get("orders", "")))


def p_fulfil():
    st.subheader("Supplier & fulfilment analytics")
    sp = table("supplier_lead_time_performance")
    c1, c2 = st.columns(2)
    with c1:
        s2 = sp[sp.pos >= 20].sort_values("on_time_pct")
        show(px.bar(s2, x="on_time_pct", y="supplier_name", orientation="h", hover_data=["supplier_class", "pos"], title="Supplier on-time delivery % (POs >= 20)",
                    color_discrete_sequence=[FIN[0]]), 460)
    with c2:
        show(px.scatter(sp[sp.pos >= 20], x="avg_delay_days", y="p90_delay_days", size="pos", text="supplier_name", hover_data=["supplier_class"],
                        title="Supplier delay: average vs 90th percentile (days; bubble = POs)", color_discrete_sequence=[FIN[2]]).update_traces(textposition="top center", textfont_size=9), 460)
    st.dataframe(sp.drop(columns="data_status").round(1), use_container_width=True, hide_index=True)
    download(sp, "supplier_performance")
    c1, c2, c3 = st.columns(3)
    with c1:
        rd = table("readiness_delay_categories")
        show(px.pie(rd, names="delay_category", values="orders", hole=.5, title="Ready vs promise"), 340)
    with c2:
        hw = table("handoff_wait_reasons")
        show(px.pie(hw, names="handoff_wait_reason", values="orders", hole=.5, title="Wait from ready to hand-off"), 340)
    with c3:
        pu = table("pickup_slot_utilisation")
        order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        show(px.bar(pu, x="dow", y="avg_util", category_orders={"dow": order}, title="Pickup-slot utilisation by weekday (9 slots)", labels={"avg_util": "%"},
                    color_discrete_sequence=[FIN[3]]), 340)
    fp = table("fulfilment_performance")
    st.markdown("**Fulfilment performance by order type and method** - third-party delivery fees are paid by customers directly to carriers and are not retailer revenue")
    st.dataframe(fp.drop(columns="data_status").round(1), use_container_width=True, hide_index=True)
    cx = table("cancellations")
    st.markdown("**Cancellations**")
    st.dataframe(cx.drop(columns="data_status").round(0), use_container_width=True, hide_index=True)
    note(esc(FD.get("suppliers", "")))
    note(esc(FD.get("fulfilment", "")))


def p_customers():
    st.subheader("Customer intelligence (furniture is a low-frequency purchase)")
    seg = table("customer_segments")
    kpis([("Buying customers", f"{M.get('customers', 0):,.0f}", "since Jan 2024", None), ("Repeat within 12 months", f"{M.get('repeat_12m', 0):.0%}", f"{M.get('repeat_24m', 0):.0%} within 24", None),
          ("Avg 5-yr customer value", money(M.get("clv_avg")), "gross profit, estimated", None)], per_row=3)
    c1, c2 = st.columns(2)
    with c1:
        show(px.bar(seg.sort_values("sales_share_pct"), x="sales_share_pct", y="segment", orientation="h", text="customers", title="Segments: share of sales (label = customers)",
                    color_discrete_sequence=[FIN[0]]), 400)
    with c2:
        coh = table("retention_cohorts")
        show(px.bar(coh, x="cohort", y=["repeat_6m_pct", "repeat_12m_pct", "repeat_to_date_pct"], barmode="group", title="Repeat purchase by first-order cohort (%)",
                    labels={"value": "%", "variable": ""}), 400)
    st.dataframe(seg.drop(columns="data_status").round(1), use_container_width=True, hide_index=True)
    att = table("marketing_attribution")
    st.markdown("**Marketing attribution** (new customers by acquisition channel; spend mapping is an assumption)")
    st.dataframe(att.drop(columns="data_status").round(2), use_container_width=True, hide_index=True)
    rfm = table("customer_rfm")
    download(rfm, "customer_rfm", "Download RFM scores (fictional IDs)")
    note(esc(FD.get("customers", "")))


def p_consult():
    st.subheader("Design consultation analytics")
    kpis([("Consult conversion", f"{M.get('consult_conv', 0):.0%}", "closed consultations", None), ("AOV after consult", money(M.get("aov_consult")), f"vs {money(M.get('aov_other'))} other", True),
          ("Consult-driven sales", money(M.get("consult_revenue")), "since Jan 2024", None), ("Consult cost", money(M.get("consult_cost")), "designer time & materials", None),
          ("Open consultations", f"{M.get('open_quotes', 0):,.0f}", f"quotes {money(M.get('open_quote_value'))}", None)], per_row=5)
    c1, c2 = st.columns(2)
    with c1:
        fu = table("consultations_by_follow_up_count")
        show(px.bar(fu, x="follow_up_count", y="conversion_pct", text="consults", title="Conversion by number of follow-ups (label = consults)", color_discrete_sequence=[FIN[1]]), 360)
    with c2:
        dz = table("consultations_by_designer_id")
        show(px.bar(dz, x="designer_id", y="conversion_pct", text=dz.revenue_per_consult.map(lambda v: f"${v:,.0f}/consult"), title="Conversion by designer",
                    color_discrete_sequence=[FIN[0]]), 360)
    c1, c2 = st.columns(2)
    with c1:
        ty = table("consultations_by_consultation_type")
        st.markdown("**By consultation type**")
        st.dataframe(ty.drop(columns="data_status").round(1), use_container_width=True, hide_index=True)
    with c2:
        qb = table("consultations_by_quote_band")
        st.markdown("**By quotation size**")
        st.dataframe(qb.drop(columns="data_status").round(1), use_container_width=True, hide_index=True)
    cm = table("consultations_monthly", parse_dates=["month"])
    show(px.bar(cm, x="month", y=["consults", "converted"], barmode="group", title="Consultations and conversions by month"), 320)
    pipe = table("open_consultation_pipeline")
    st.markdown(f"**Lead-conversion forecast for open consultations** (model D): {len(pipe)} open, ~{pipe.p_convert.sum():.0f} expected to convert, "
                f"{money(pipe.expected_revenue_cad.sum())} expected sales")
    st.dataframe(pipe.drop(columns="data_status").round(3), use_container_width=True, hide_index=True, height=260)
    download(pipe, "consultation_pipeline")
    note(esc(FD.get("consults", "")))


def p_is():
    st.subheader("Income statement")
    st.caption("Revenue is recognised at hand-off (store pickup or loading to the customer's carrier); deposits are liabilities until then. " + SYNTHETIC_LABEL)
    gran = st.radio("Granularity", ["Annual", "Quarterly", "Monthly"], horizontal=True)
    df, lab = stmt({"Annual": "income_statement_annual", "Quarterly": "income_statement_quarterly", "Monthly": "income_statement_monthly"}[gran])
    df = df.rename(columns={"2026": "2026 YTD (Jan-Sep)"})
    cols = list(df.columns)
    c1, c2 = st.columns(2)
    a = c1.selectbox("Period", cols, index=len(cols) - (2 if gran == "Annual" else 1))
    b = c2.selectbox("Compare with", cols, index=max(0, len(cols) - (3 if gran == "Annual" else 2)))
    comp = pd.DataFrame({a: df[a], b: df[b], "Variance": df[a] - df[b]})
    c1, c2 = st.columns([3, 2])
    with c1:
        st.dataframe(fmt_table(comp, lab), use_container_width=True, height=620)
    with c2:
        x = df[a]
        show(waterfall(["Net revenue", "COGS", "Gross profit", "Opex", "EBITDA", "Depreciation", "Interest", "Tax", "Net income"],
                       [x.net_rev, x.cogs, 0, x.opex, 0, x.da, x.interest, x.tax, 0],
                       ["absolute", "relative", "total", "relative", "total", "relative", "relative", "relative", "total"], f"{a}: revenue to net income"), 420)
        cs, _ = stmt("common_size_annual")
        st.markdown("**Common-size (% of net revenue), annual**")
        st.dataframe(cs.loc[["net_sales", "cogs", "gross_profit", "emp_comp", "occupancy", "marketing", "opex", "ebitda", "net_income"]].round(1), use_container_width=True)
    download(df, f"income_statement_{gran.lower()}", index=True)
    download_file(FIN_OUT / "Prairie_Home_Financial_Statements.xlsx", "Download statements workbook (Excel)")


def p_bs():
    st.subheader("Balance sheet")
    df, lab = stmt("balance_sheet_monthly")
    cols = list(df.columns)
    a = st.select_slider("Month end", cols, value=cols[-1])
    i = cols.index(a)
    b = cols[i - 12] if i >= 12 else cols[0]
    x = df[a]
    kpis([("Total assets", money(x.total_assets), f"vs {money(df.at['total_assets', b])} {b}", None), ("Inventory (stock + allocated)", money(x.inv_stock + x.inv_alloc), "at cost", None),
          ("Customer deposits", money(x.deposits), "contract liabilities", None), ("Working capital", money(x.current_assets - x.current_liabilities), f"current ratio {x.current_assets / x.current_liabilities:.2f}", True),
          ("Equity", money(x.total_equity), "share capital + retained", None), ("A = L + E", "✔ balanced" if abs(x.check) < 0.01 else "✖", f"diff ${x.check:,.2f}", abs(x.check) < 0.01)])
    c1, c2 = st.columns([3, 2])
    with c1:
        st.dataframe(fmt_table(pd.DataFrame({a: x, b: df[b], "Change": x - df[b]}).drop(index="check"), lab), use_container_width=True, height=640)
    with c2:
        mm = pd.to_datetime(df.columns)
        fig = go.Figure([go.Bar(x=mm, y=df.loc[k], name=n, marker_color=FIN[j]) for j, (k, n) in enumerate([("cash", "Cash"), ("inv_stock", "Stocked inventory"),
                                                                                                            ("inv_alloc", "Allocated inventory"), ("ar", "Receivables")])])
        fig.update_layout(barmode="stack", title="Asset composition", yaxis_tickprefix="$")
        show(fig, 310)
        fig = go.Figure([go.Bar(x=mm, y=df.loc[k], name=n, marker_color=FIN[j]) for j, (k, n) in enumerate([("deposits", "Customer deposits"), ("ap", "Payables"),
                                                                                                            ("term_lt", "Term loan (LT)"), ("total_equity", "Equity")])])
        fig.update_layout(barmode="stack", title="Funding composition", yaxis_tickprefix="$")
        show(fig, 310)
    download(df, "balance_sheet_monthly", index=True)


def p_cf():
    st.subheader("Cash flow statement (indirect method)")
    gran = st.radio("Granularity", ["Annual", "Quarterly", "Monthly"], horizontal=True, key="cfg")
    df, lab = stmt({"Annual": "cash_flow_annual", "Quarterly": "cash_flow_quarterly", "Monthly": "cash_flow_monthly"}[gran])
    a = st.selectbox("Period", list(df.columns), index=len(df.columns) - 1, key="cfa")
    x = df[a]
    kpis([("Net income", money(x.net_income), "accounting profit", None), ("Operating cash flow", money(x.cfo), "cash from operations", x.cfo > 0),
          ("Customer deposits change", money(x.d_deposits), "cash collected ahead of revenue", None), ("Inventory investment", money(x.d_inv), "(-) = cash used", None),
          ("Ending cash", money(x.close_cash), "ties to balance sheet ✔" if abs(x.check) < 0.01 else "✖", abs(x.check) < 0.01)], per_row=5)
    c1, c2 = st.columns([2, 3])
    with c1:
        st.dataframe(fmt_table(df[[a]], lab), use_container_width=True, height=560)
    with c2:
        show(waterfall(["Opening cash", "Net income", "Depreciation", "Receivables", "Inventory", "Payables", "Deposits", "Other WC", "Capex", "Financing", "Ending cash"],
                       [x.open_cash, x.net_income, x.da, x.d_ar, x.d_inv, x.d_ap, x.d_deposits, x.d_other, x.cfi, x.cff, 0],
                       ["absolute"] + ["relative"] * 9 + ["total"], f"Cash bridge {a}"), 430)
        dm, _ = stmt("cash_flow_direct_method")
        st.markdown("**Direct-method view (receipts and payments)**")
        st.dataframe(fmt_table(dm.T.groupby(lambda c: c[:4]).sum().T), use_container_width=True)
    download(df, f"cash_flow_{gran.lower()}", index=True)


def p_ratios():
    st.subheader("Financial ratios (TTM)")
    ann = table("fin_ratios_annual", index_col=0)
    r = table("fin_ratios_monthly_ttm", index_col=0).drop(columns="data_status")
    grp = st.radio("Group", ["Profitability", "Liquidity", "Efficiency", "Solvency"], horizontal=True)
    keys = [d[0] for d in R.DEFINITIONS if d[2] == grp]
    items = []
    for k in keys:
        d = R.DEF[k]
        v = ann.at[k, "TTM Sep-2026"]
        items.append((d[1], money(v) if d[5] == "$" else f"{v:,.2f}{'%' if d[5] == '%' else (' d' if d[5] == 'days' else 'x')}", f"{ann.at[k, 'change_vs_FY2025']:+,.2f} vs FY2025",
                      ann.at[k, "direction"] == "improved"))
    kpis(items)
    sel = st.multiselect("Plot", keys, default=keys[:3], format_func=lambda k: R.DEF[k][1])
    fig = go.Figure([go.Scatter(x=pd.to_datetime(r.columns), y=r.loc[k], name=R.DEF[k][1], line=dict(width=2.5, color=FIN[i % 4])) for i, k in enumerate(sel)])
    fig.update_layout(title=f"{grp} ratios - monthly TTM")
    show(fig, 360)
    st.dataframe(ann.loc[keys, ["ratio", "formula", "FY2024", "FY2025", "TTM Sep-2026", "direction", "meaning", "management_action"]].round(2), use_container_width=True, hide_index=True)
    download(ann, "ratio_analysis", index=True)


def p_forecast():
    st.subheader("Sales & cash flow forecasting (Oct 2026 - Sep 2027) - FORECAST")
    st.caption("Accuracy is measured on synthetic data with time-based backtests; it does not demonstrate accuracy on any real retailer's transactions.")
    comp = table("forecast_model_comparison")
    fc = table("forecast_next_12_months_all_models", parse_dates=["month"])
    targets = ["net_sales"] + [t for t in fc.target.unique() if t != "net_sales"]
    tgt = st.selectbox("Series", targets, format_func=lambda t: "Total written sales (CAD)" if t == "net_sales" else f"{t} (units)")
    from src.models import forecasting as fm
    d = fm.daily_frame()
    h = fm.monthly(d[d.date <= "2026-09-30"], tgt)
    fig = go.Figure([go.Scatter(x=h.index, y=h.values, name="History", line=dict(color=TOT, width=3))])
    for i, m in enumerate(["Seasonal naive", "SARIMAX", "XGBoost"]):
        g = fc[(fc.target == tgt) & (fc.model == m)]
        fig.add_scatter(x=g.month, y=g.forecast, name=m + (" (selected)" if g.selected.any() else ""), line=dict(width=2.5 if g.selected.any() else 1.5, dash="solid" if g.selected.any() else "dash", color=FIN[i]))
        if g.selected.any():
            fig.add_scatter(x=list(g.month) + list(g.month[::-1]), y=list(g.hi80) + list(g.lo80[::-1]), fill="toself", fillcolor="rgba(42,120,214,0.14)", line=dict(width=0), name="80% interval")
    fig.update_layout(title="History and 12-month forecast")
    show(fig, 420)
    st.markdown("**Backtest accuracy** (holdout Jan-Sep 2026 + rolling origins; lower WAPE is better)")
    st.dataframe(comp[comp.target == tgt].drop(columns="data_status").round(3), use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Model C - custom/special-order delay prediction (test set)**")
        st.dataframe(table("delay_model_evaluation").drop(columns="data_status").round(3), use_container_width=True, hide_index=True)
    with c2:
        st.markdown("**Model D - consultation conversion propensity (test set)**")
        st.dataframe(table("conversion_model_evaluation").drop(columns="data_status").round(3), use_container_width=True, hide_index=True)
    st.markdown("**Cash flow & working-capital forecast by scenario (integrated three-statement model)**")
    rows = []
    for n in ["Conservative", "Base", "Optimistic"]:
        f = table(f"fin_forecast_{n.lower()}_monthly", index_col=0).drop(columns=["label", "data_status"]).iloc[:, 1:]
        rows.append(pd.DataFrame({"month": pd.to_datetime(f.columns), "cash": f.loc["cash"].values, "working_capital": f.loc["working_capital"].values, "scenario": n}))
    cf = pd.concat(rows)
    c1, c2 = st.columns(2)
    with c1:
        show(px.line(cf, x="month", y="cash", color="scenario", title="Month-end cash by scenario"), 340)
    with c2:
        show(px.line(cf, x="month", y="working_capital", color="scenario", title="Working capital by scenario"), 340)
    download(fc, "forecast_next_12_months_all_models")
    download_file(FIN_OUT / "Prairie_Home_Integrated_Financial_Model.xlsx", "Download integrated three-statement model (Excel, live formulas)")


def p_sim():
    st.subheader("Business scenario simulator (12-month integrated forecast)")
    st.caption("Every slider feeds the same formula engine as the Excel model; revenue, profit, cash and working capital stay reconciled. Illustrative only.")
    b = fbase()
    preset = st.selectbox("Start from", ["Base", "Conservative", "Optimistic"])
    p0 = F.SCENARIOS[preset]
    c1, c2, c3 = st.columns(3)
    with c1:
        vol = st.slider("Sales volume change %", -20.0, 20.0, p0.volume_change * 100, 1.0) / 100
        gm = st.slider("Gross-margin improvement (pts)", -5.0, 5.0, p0.margin_pts * 100, 0.25) / 100
        slow = st.slider("Slow-moving inventory reduction %", 0.0, 50.0, p0.slow_reduction * 100, 5.0) / 100
    with c2:
        dly = st.slider("Supplier-delay reduction %", -50.0, 50.0, p0.delay_reduction * 100, 5.0) / 100
        conv = st.slider("Design-consultation conversion change %", -30.0, 30.0, p0.consult_conv_change * 100, 1.0) / 100
        dpo = st.slider("Supplier payment terms change (days)", -20, 30, int(p0.dpo_change_days), 1)
    with c3:
        opx = st.slider("Operating expense change %", -15.0, 15.0, p0.opex_change * 100, 0.5) / 100
        disc = st.slider("Promotional discount change (pts)", -3.0, 5.0, p0.discount_change * 100, 0.25) / 100
        rate = st.slider("Prime-rate change (bps)", -200, 300, int(p0.rate_change * 10000), 25) / 10000
    sc = replace(F.SCENARIOS["Base"], volume_change=vol, margin_pts=gm, slow_reduction=slow, delay_reduction=dly, consult_conv_change=conv, dpo_change_days=dpo,
                 opex_change=opx, discount_change=disc, rate_change=rate)
    res, base = F.run(sc, b), F.run(F.SCENARIOS["Base"], b)
    r, r0 = F.summary(res), F.summary(base)
    kpis([("Net revenue", money(r["net_revenue"]), f"{r['net_revenue'] - r0['net_revenue']:+,.0f} vs Base", r["net_revenue"] >= r0["net_revenue"]),
          ("Gross profit", money(r["gross_profit"]), f"GM {r['gross_margin_pct']:.1f}%", r["gross_profit"] >= r0["gross_profit"]),
          ("Net income", money(r["net_income"]), f"{r['net_income'] - r0['net_income']:+,.0f}", r["net_income"] >= r0["net_income"]),
          ("Operating cash flow", money(r["cfo"]), f"{r['cfo'] - r0['cfo']:+,.0f}", r["cfo"] >= r0["cfo"]),
          ("Closing cash", money(r["closing_cash"]), f"{r['closing_cash'] - r0['closing_cash']:+,.0f}", None),
          ("Working capital", money(r["closing_working_capital"]), f"{r['closing_working_capital'] - r0['closing_working_capital']:+,.0f}", None)])
    fm = pd.to_datetime(res.columns[1:])
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure([go.Bar(x=fm, y=base.loc["net_income"].iloc[1:], name="Base", marker_color=FIN[0]), go.Bar(x=fm, y=res.loc["net_income"].iloc[1:], name="Scenario", marker_color=FIN[1])])
        fig.update_layout(barmode="group", title="Monthly net income", yaxis_tickprefix="$")
        show(fig, 360)
    with c2:
        fig = go.Figure([go.Scatter(x=fm, y=base.loc["cash"].iloc[1:], name="Base", line=dict(color=FIN[0], width=3)),
                         go.Scatter(x=fm, y=res.loc["cash"].iloc[1:], name="Scenario", line=dict(color=FIN[1], width=3))])
        fig.update_layout(title="Month-end cash", yaxis_tickprefix="$")
        show(fig, 360)
    st.markdown("**Required scenarios (each lever alone vs Base)**")
    sens = table("fin_forecast_sensitivity")
    st.dataframe(sens[["scenario", "delta_net_revenue", "delta_gross_profit", "delta_net_income", "delta_cfo", "delta_working_capital", "delta_closing_cash"]].round(0),
                 use_container_width=True, hide_index=True)
    download(sens, "scenario_sensitivity")
    with st.expander("Formulas and assumptions"):
        st.markdown("Each forecast line is one formula template, e.g. net sales = (opening-backlog release + lag-weighted bookings) x (1 - cancellation rate); "
                    "deposits = deposit ratio x open backlog x 1.05; inventory purchases = stock target - opening stock + change in allocated stock + COGS.")
        st.dataframe(pd.DataFrame([(k, lab, tpl) for k, lab, _, tpl, _ in F.ROWS], columns=["key", "line", "formula template"]), use_container_width=True, hide_index=True, height=300)
        st.json({k: round(v, 4) for k, v in b["A"].items()})
    st.warning("Scenario results are illustrative estimates for a fictional retailer on synthetic data, not forecasts of any real company's results.")


{PAGES[0]: p_exec, PAGES[1]: p_sales, PAGES[2]: p_product, PAGES[3]: p_inventory, PAGES[4]: p_orders, PAGES[5]: p_fulfil, PAGES[6]: p_customers,
 PAGES[7]: p_consult, PAGES[8]: p_is, PAGES[9]: p_bs, PAGES[10]: p_cf, PAGES[11]: p_ratios, PAGES[12]: p_forecast, PAGES[13]: p_sim}[page]()

st.markdown(f"<div style='text-align:center;color:{BRAND['subtle']};font-size:.75rem;margin-top:30px'>{ATTRIBUTION} | {SYNTHETIC_LABEL} | "
            "Prairie Home Furnishings is a fictional retailer; no endorsement by or relationship with any real company is implied.</div>", unsafe_allow_html=True)
