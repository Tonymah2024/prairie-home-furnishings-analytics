"""Phases 3-6: sales, product, inventory, custom-order / fulfilment, customer and design-consultation analytics.
Writes result tables to outputs/tables and a findings dictionary (metrics + plain-language interpretations) used
by the dashboard and the executive report. All results describe SYNTHETIC data of a fictional retailer."""
from __future__ import annotations

import itertools
import json
import math
from collections import Counter

import numpy as np
import pandas as pd
from scipy.stats import norm

from src.config import END, TABLES
from src.engineering.sqlutil import connect

END_TS = pd.Timestamp(END)
TTM0 = pd.Timestamp("2025-10-01")
CARRY = 0.22             # annual inventory carrying-cost rate (capital 7% + storage/handling 9% + damage/obsolescence 6%) - ASSUMPTION


def money(v):
    s = "-" if v < 0 else ""
    v = abs(v)
    return f"{s}${v / 1e6:,.2f}M" if v >= 1e6 else f"{s}${v:,.0f}"


def load():
    con = connect()
    q = lambda s: pd.read_sql_query(s, con)
    D = {t: q(f"SELECT * FROM {t}") for t in ["products", "suppliers", "customers", "leads", "consultations", "orders", "sales_transactions", "payments",
                                                "purchase_orders", "inventory_movements", "fulfillment", "returns", "stockout_events", "marketing_spend", "operating_expenses"]}
    con.close()
    for t, cols in dict(orders=["order_date", "ready_date", "fulfilled_date", "cancel_date", "promised_ready_date"], sales_transactions=["transaction_date", "fulfilled_date"],
                        consultations=["consultation_date", "conversion_date"], purchase_orders=["order_date", "promised_date", "received_date"],
                        inventory_movements=["movement_date"], customers=["created_date", "first_order_date", "last_order_date"], leads=["lead_date", "conversion_date"],
                        fulfillment=["promised_ready_date", "ready_date", "requested_date", "scheduled_date", "fulfilled_date"], stockout_events=["event_date"],
                        marketing_spend=["month"], payments=["payment_date"]).items():
        for c in cols:
            D[t][c] = pd.to_datetime(D[t][c])
    s = D["sales_transactions"]
    D["valid"] = s[(s.line_status != "Cancelled") & (s.transaction_date >= "2024-01-01")].copy()
    return D


def save(df, name, index=False):
    d = df.copy()
    d["data_status"] = "SYNTHETIC"
    d.to_csv(TABLES / f"{name}.csv", index=index)
    return df


# ----------------------------------------------------------------------------------------------- sales
def sales(D, F, K):
    v = D["valid"]
    o = D["orders"][(D["orders"].status != "Cancelled") & (D["orders"].order_date >= "2024-01-01")]
    v["month"] = v.transaction_date.dt.to_period("M").dt.to_timestamp()
    m = v.groupby("month").agg(net_sales=("net_sales_cad", "sum"), gross_profit=("gross_profit_cad", "sum"), units=("units", "sum"), orders=("order_id", "nunique")).reset_index()
    m["gm_pct"] = m.gross_profit / m.net_sales * 100
    m["yoy_pct"] = m.net_sales.pct_change(12) * 100
    save(m, "sales_monthly")
    q = v.assign(q=v.transaction_date.dt.to_period("Q").astype(str)).groupby("q").agg(net_sales=("net_sales_cad", "sum"), gross_profit=("gross_profit_cad", "sum")).reset_index()
    q["qoq_pct"], q["yoy_pct"] = q.net_sales.pct_change() * 100, q.net_sales.pct_change(4) * 100
    save(q, "sales_quarterly")
    cat = v.groupby("category").agg(net_sales=("net_sales_cad", "sum"), gross_profit=("gross_profit_cad", "sum"), units=("units", "sum"), lines=("line_id", "count")).reset_index()
    cat["gm_pct"] = cat.gross_profit / cat.net_sales * 100
    cat["share_pct"] = cat.net_sales / cat.net_sales.sum() * 100
    ttm = v[v.transaction_date >= TTM0].groupby("category").net_sales_cad.sum()
    prior = v[(v.transaction_date >= TTM0 - pd.DateOffset(years=1)) & (v.transaction_date < TTM0)].groupby("category").net_sales_cad.sum()
    cat["ttm_growth_pct"] = cat.category.map((ttm / prior - 1) * 100)
    save(cat.sort_values("net_sales", ascending=False), "sales_by_category")
    sku = v.groupby(["product_id"]).agg(units=("units", "sum"), net_sales=("net_sales_cad", "sum"), gross_profit=("gross_profit_cad", "sum"),
                                        avg_discount=("discount_pct", "mean"), lines=("line_id", "count")).reset_index()
    sku = D["products"][["product_id", "product_name", "manufacturer", "category", "subcategory", "fulfillment_type", "list_price_cad"]].merge(sku, on="product_id", how="left").fillna({"units": 0, "net_sales": 0, "gross_profit": 0})
    sku["gm_pct"] = np.where(sku.net_sales > 0, sku.gross_profit / sku.net_sales * 100, np.nan)
    sku["rank_net_sales"] = sku.net_sales.rank(ascending=False)
    save(sku.sort_values("net_sales", ascending=False), "product_profitability")
    mfr = v.groupby("manufacturer").agg(net_sales=("net_sales_cad", "sum"), gross_profit=("gross_profit_cad", "sum"), units=("units", "sum"), skus=("product_id", "nunique")).reset_index()
    mfr["gm_pct"] = mfr.gross_profit / mfr.net_sales * 100
    save(mfr.sort_values("net_sales", ascending=False), "manufacturer_profitability")
    # custom vs ready-made
    o2 = o.copy()
    cu = v.groupby("fulfillment_type").agg(net_sales=("net_sales_cad", "sum"), gross_profit=("gross_profit_cad", "sum"), units=("units", "sum"), lines=("line_id", "count")).reset_index()
    cu["gm_pct"] = cu.gross_profit / cu.net_sales * 100
    ot = D["orders"][D["orders"].order_date >= "2024-01-01"].groupby("order_type").agg(orders=("order_id", "count"), aov=("net_order_value_cad", "mean"),
                                                                                         cancel_rate=("status", lambda x: (x == "Cancelled").mean() * 100),
                                                                                         median_days_to_handoff=("fulfillment_days", "median"),
                                                                                         ready_late_pct=("ready_delay_days", lambda x: (x > 0).mean() * 100)).reset_index()
    save(cu, "custom_vs_ready_made_lines")
    save(ot, "order_type_performance")
    # channel & ATV
    ch = o.groupby("sales_channel").agg(orders=("order_id", "count"), net_sales=("net_order_value_cad", "sum"), aov=("net_order_value_cad", "mean")).reset_index()
    chgp = v.groupby("sales_channel").gross_profit_cad.sum()
    ch["gross_profit"] = ch.sales_channel.map(chgp)
    ch["gm_pct"] = ch.gross_profit / ch.net_sales * 100
    save(ch.sort_values("net_sales", ascending=False), "sales_by_channel")
    # sales reps
    rp = v[v.employee_id.str.startswith("EMP-S", na=False)].groupby("employee_id").agg(net_sales=("net_sales_cad", "sum"), gross_profit=("gross_profit_cad", "sum"),
                                                                                        orders=("order_id", "nunique"), lines=("line_id", "count"), avg_discount=("discount_pct", "mean")).reset_index()
    rp["aov"] = rp.net_sales / rp.orders
    rp["items_per_order"] = rp.lines / rp.orders
    rp["gm_pct"] = rp.gross_profit / rp.net_sales * 100
    rp["discretionary_discount_lines_pct"] = rp.employee_id.map(v[v.discount_reason == "Manager discretionary"].groupby("employee_id").size() / v.groupby("employee_id").size() * 100)
    save(rp.sort_values("net_sales", ascending=False), "sales_rep_performance")
    # discounts & promotions
    v["disc_band"] = pd.cut(v.discount_pct, [-0.001, 0, 0.05, 0.10, 0.15, 1], labels=["0%", "1-5%", "6-10%", "11-15%", ">15%"])
    db = v.groupby(["disc_band", "discount_reason"], observed=True, dropna=False).agg(lines=("line_id", "count"), net_sales=("net_sales_cad", "sum"),
                                                                                     gm_pct=("gross_margin_pct", "mean")).reset_index()
    save(db, "discount_bands")
    daily = v.groupby("transaction_date").agg(net=("net_sales_cad", "sum"), gp=("gross_profit_cad", "sum")).reset_index()
    pr = D["orders"][["order_id", "promotion_id"]]
    promo_days = v.merge(pr, on="order_id", suffixes=("", "_order")).groupby("transaction_date").promotion_id_order.first()
    daily["promotion_id"] = daily.transaction_date.map(promo_days)
    daily["dow"] = daily.transaction_date.dt.dayofweek
    rows = []
    for pid, g in daily[daily.promotion_id.notna()].groupby("promotion_id"):
        s0, s1 = g.transaction_date.min(), g.transaction_date.max()
        base = daily[(daily.transaction_date >= s0 - pd.Timedelta(days=35)) & (daily.transaction_date < s0 - pd.Timedelta(days=7)) & daily.promotion_id.isna()]
        bd = base.groupby("dow")[["net", "gp"]].mean()
        exp_net = g.dow.map(bd.net).sum()
        exp_gp = g.dow.map(bd.gp).sum()
        disc = v[(v.promotion_id == pid)]
        rows.append({"promotion_id": pid, "start": s0.date(), "end": s1.date(), "days": len(g), "net_sales": g.net.sum(), "baseline_net_sales": exp_net,
                     "incremental_net_sales": g.net.sum() - exp_net, "gross_profit": g.gp.sum(), "baseline_gross_profit": exp_gp, "incremental_gross_profit": g.gp.sum() - exp_gp,
                     "discount_cost": (disc.gross_sales_cad - disc.net_sales_cad).sum()})
    pe = pd.DataFrame(rows)
    pe["lift_pct"] = (pe.net_sales / pe.baseline_net_sales - 1) * 100
    names = pd.read_sql_query("SELECT promotion_id, promotion_name FROM promotions", connect()).set_index("promotion_id").promotion_name
    pe["promotion"] = pe.promotion_id.map(names) + " " + pe.promotion_id.str[4:8]
    save(pe, "promotion_effectiveness")
    # market basket (subcategory pairs within orders)
    baskets = v.groupby("order_id").subcategory.apply(lambda x: sorted(set(x)))
    n = len(baskets)
    single = Counter(itertools.chain.from_iterable(baskets))
    pairs = Counter(itertools.chain.from_iterable(itertools.combinations(b, 2) for b in baskets if len(b) > 1))
    mb = pd.DataFrame([{"antecedent": a, "consequent": b, "orders_together": c, "support_pct": c / n * 100, "confidence_pct": c / single[a] * 100,
                        "lift": (c / n) / ((single[a] / n) * (single[b] / n))} for (a, b), c in pairs.items() if c >= 25])
    mb2 = mb.rename(columns={"antecedent": "consequent", "consequent": "antecedent"})
    mb2["confidence_pct"] = mb2.orders_together / mb2.antecedent.map(single) * 100
    mb = pd.concat([mb, mb2]).sort_values("lift", ascending=False)
    save(mb, "cross_sell_pairs")
    # metrics + findings
    t = v[v.transaction_date >= TTM0]
    p = v[(v.transaction_date >= TTM0 - pd.DateOffset(years=1)) & (v.transaction_date < TTM0)]
    K.update(ttm_net_sales=t.net_sales_cad.sum(), ttm_growth=t.net_sales_cad.sum() / p.net_sales_cad.sum() - 1, ttm_gm=t.gross_profit_cad.sum() / t.net_sales_cad.sum(),
             aov=o[o.order_date >= TTM0].net_order_value_cad.mean(), custom_share=v[v.fulfillment_type.str.startswith("Custom")].net_sales_cad.sum() / v.net_sales_cad.sum(),
             custom_gm=cu.set_index("fulfillment_type").gm_pct.get("Custom (made to order)", np.nan), stock_gm=cu.set_index("fulfillment_type").gm_pct.get("Stocked (ready-made)", np.nan),
             promo_incr_gp=pe.incremental_gross_profit.sum(), promo_disc_cost=pe.discount_cost.sum())
    top = cat.sort_values("net_sales", ascending=False).iloc[0]
    best_pair = mb[(mb.orders_together >= 200)].sort_values("lift", ascending=False).iloc[0]          # material volume only
    worst_promo = pe.sort_values("incremental_gross_profit").iloc[0]
    best_promo = pe.sort_values("incremental_gross_profit").iloc[-1]
    F["sales"] = (f"Trailing-twelve-month written sales are {money(K['ttm_net_sales'])} ({K['ttm_growth']:+.1%} vs the prior twelve months) at a {K['ttm_gm']:.1%} gross margin. "
                  f"{top.category} is the largest category ({top.share_pct:.0f}% of sales, {top.gm_pct:.0f}% GM).")
    F["custom"] = (f"Custom Canadian-made pieces are {K['custom_share']:.0%} of sales at a {K['custom_gm']:.1f}% line margin vs {K['stock_gm']:.1f}% for ready-made stock, "
                   f"but they tie up customers' money and the store's attention for ~{ot.set_index('order_type').median_days_to_handoff.get('Custom', 0):.0f} days per order.")
    F["promotions"] = (f"Promotions generated {money(K['promo_incr_gp'])} of incremental gross profit against {money(K['promo_disc_cost'])} of discounts. Best: {best_promo.promotion} "
                       f"({money(best_promo.incremental_gross_profit)} incremental GP); weakest: {worst_promo.promotion} ({money(worst_promo.incremental_gross_profit)}).")
    F["cross_sell"] = (f"Strongest attachment: {best_pair.antecedent} -> {best_pair.consequent} (confidence {best_pair.confidence_pct:.0f}%, lift {best_pair.lift:.1f}x) - "
                       "a candidate for bundles and room packages.")
    rp_hi, rp_lo = rp.sort_values("gm_pct").iloc[-1], rp.sort_values("gm_pct").iloc[0]
    d_hi, d_lo = rp.sort_values("discretionary_discount_lines_pct").iloc[-1], rp.sort_values("discretionary_discount_lines_pct").iloc[0]
    F["reps"] = (f"Gross margin by sales associate ranges from {rp_lo.gm_pct:.1f}% ({rp_lo.employee_id}) to {rp_hi.gm_pct:.1f}% ({rp_hi.employee_id}); the share of lines carrying a "
                 f"discretionary discount ranges from {d_lo.discretionary_discount_lines_pct:.1f}% ({d_lo.employee_id}) to {d_hi.discretionary_discount_lines_pct:.1f}% ({d_hi.employee_id}).")


# ----------------------------------------------------------------------------------------------- inventory
def fifo_age(mv, prod_ids):
    """Age of on-hand STOCK units at END using FIFO layers from receipts (opening balance aged as of 1-Jan-2024 minus 120 days)."""
    out = []
    st = mv[mv.inventory_state == "stock"].sort_values(["movement_date", "movement_id"])
    for p, g in st.groupby("product_id"):
        layers = []
        for r in g.itertuples():
            if r.quantity > 0:
                d = r.movement_date - pd.Timedelta(days=120) if r.movement_type == "OPENING_BALANCE" else r.movement_date
                layers.append([d, r.quantity, r.unit_cost_cad])
            else:
                q = -r.quantity
                while q > 0 and layers:
                    take = min(q, layers[0][1])
                    layers[0][1] -= take
                    q -= take
                    if layers[0][1] == 0:
                        layers.pop(0)
        for d, q, c in layers:
            if q > 0:
                out.append({"product_id": p, "receipt_date": d, "units": q, "value_cad": q * c, "age_days": (END_TS - d).days})
    return pd.DataFrame(out)


def inventory(D, F, K):
    p = D["products"].copy()
    mv = D["inventory_movements"]
    v = D["valid"]
    stocked = p[p.fulfillment_type.str.startswith("Stocked")].copy()
    # demand from stock (units sold from stock) TTM + seasonal profile
    from_stock = v[v.supply_source == "From stock"]
    d12 = from_stock[from_stock.transaction_date >= TTM0].groupby("product_id").units.sum()
    all_d = v[v.fulfillment_type.str.startswith("Stocked")]
    d12_all = all_d[all_d.transaction_date >= TTM0].groupby("product_id").units.sum()      # incl. special orders = true demand
    cogs12 = all_d[all_d.transaction_date >= TTM0].groupby("product_id").cogs_cad.sum()
    stocked["units_ttm"] = stocked.product_id.map(d12_all).fillna(0)
    stocked["cogs_ttm"] = stocked.product_id.map(cogs12).fillna(0)
    stocked["stock_value"] = stocked.on_hand_stock_units * stocked.unit_cost_cad
    stocked = stocked.sort_values("cogs_ttm", ascending=False)
    cum = stocked.cogs_ttm.cumsum() / stocked.cogs_ttm.sum()
    stocked["abc_class"] = np.where(cum <= 0.70, "A", np.where(cum <= 0.90, "B", "C"))
    # average stock (monthly snapshots, TTM)
    mv2 = mv[mv.inventory_state == "stock"].assign(m=mv.movement_date.dt.to_period("M"))
    snap = mv2.pivot_table(index="m", columns="product_id", values="value_cad", aggfunc="sum", fill_value=0).cumsum()
    avg_val = snap.loc[pd.Period("2025-09", "M"):].mean()
    stocked["avg_stock_value_ttm"] = stocked.product_id.map(avg_val).fillna(0)
    stocked["turnover"] = np.where(stocked.avg_stock_value_ttm > 0, stocked.cogs_ttm / stocked.avg_stock_value_ttm, np.nan)
    stocked["days_of_cover"] = np.where(stocked.units_ttm > 0, stocked.on_hand_stock_units / (stocked.units_ttm / 365), np.inf)
    ages = fifo_age(mv, stocked.product_id)
    wa = ages.groupby("product_id").apply(lambda g: np.average(g.age_days, weights=g.units), include_groups=False)
    stocked["weighted_age_days"] = stocked.product_id.map(wa)
    stocked["aged_180_value"] = stocked.product_id.map(ages[ages.age_days > 180].groupby("product_id").value_cad.sum()).fillna(0)
    stocked["overstock"] = stocked.days_of_cover > 180
    stocked["carrying_cost_annual"] = stocked.avg_stock_value_ttm * CARRY
    # reorder point & safety stock (95% / 90% / 85% service by ABC; weekly demand variability; supplier lead-time variability)
    po = D["purchase_orders"]
    rec = po[(po.status == "Received") & po.received_date.notna()]
    lt = rec.assign(lt=(rec.received_date - rec.order_date).dt.days).groupby("product_id").lt.agg(["mean", "std", "count"])
    sup_lt = rec.assign(lt=(rec.received_date - rec.order_date).dt.days).merge(p[["product_id", "supplier_class"]], on="product_id").groupby("supplier_class").lt.agg(["mean", "std"])
    wk = all_d[all_d.transaction_date >= "2025-01-01"].assign(w=lambda x: x.transaction_date.dt.to_period("W")).groupby(["product_id", "w"]).units.sum().unstack(fill_value=0)
    z = {"A": norm.ppf(0.95), "B": norm.ppf(0.90), "C": norm.ppf(0.85)}
    recs = []
    for r in stocked.itertuples():
        weekly = wk.loc[r.product_id] if r.product_id in wk.index else pd.Series([0.0])
        mu_d, sd_d = weekly.mean() / 7, weekly.std(ddof=0) / math.sqrt(7)
        Lm = lt.at[r.product_id, "mean"] if r.product_id in lt.index else sup_lt.at[r.supplier_class, "mean"]
        Ls = lt.at[r.product_id, "std"] if r.product_id in lt.index and lt.at[r.product_id, "count"] > 2 else sup_lt.at[r.supplier_class, "std"]
        Ls = 0.0 if pd.isna(Ls) else Ls
        ss = z[r.abc_class] * math.sqrt(Lm * sd_d ** 2 + (mu_d * Ls) ** 2)
        rop = mu_d * Lm + ss
        eoq = math.sqrt(2 * mu_d * 365 * 85 / max(r.unit_cost_cad * CARRY, 1)) if mu_d > 0 else 0          # $85 per purchase order (ASSUMPTION)
        recs.append({"product_id": r.product_id, "safety_stock": ss, "reorder_point_recommended": rop, "eoq_units": eoq, "lead_time_mean_days": Lm, "lead_time_sd_days": Ls,
                     "daily_demand": mu_d, "service_level": {"A": .95, "B": .90, "C": .85}[r.abc_class]})
    rc = pd.DataFrame(recs)
    stocked = stocked.merge(rc, on="product_id")
    stocked["recommended_order_now_units"] = np.where(stocked.on_hand_stock_units <= stocked.reorder_point_recommended,
                                                      np.ceil(np.maximum(stocked.eoq_units, stocked.reorder_point_recommended + stocked.daily_demand * 30 - stocked.on_hand_stock_units)), 0)
    stocked["action"] = np.select([stocked.overstock & (stocked.aged_180_value > 0), stocked.on_hand_stock_units <= stocked.reorder_point_recommended, stocked.overstock],
                                  ["Clear aged stock (markdown / bundle)", "Reorder now", "Pause replenishment"], "Hold")
    cols = ["product_id", "product_name", "manufacturer", "category", "subcategory", "abc_class", "on_hand_stock_units", "allocated_to_customers_units", "stock_value", "units_ttm",
            "cogs_ttm", "avg_stock_value_ttm", "turnover", "days_of_cover", "weighted_age_days", "aged_180_value", "overstock", "carrying_cost_annual", "service_level",
            "lead_time_mean_days", "lead_time_sd_days", "daily_demand", "safety_stock", "reorder_point_recommended", "reorder_point_current_policy", "eoq_units",
            "recommended_order_now_units", "action"]
    save(stocked[cols].round(2).replace([np.inf], 9999), "inventory_intelligence")
    ab = ages.merge(p[["product_id", "category"]], on="product_id")
    ab["age_band"] = pd.cut(ab.age_days, [-1, 60, 120, 180, 365, 10000], labels=["0-60 d", "61-120 d", "121-180 d", "181-365 d", ">365 d"])
    save(ab.groupby(["category", "age_band"], observed=False).value_cad.sum().unstack(fill_value=0).round(0), "inventory_aging_by_category", index=True)
    catinv = stocked.groupby("category").agg(stock_value=("stock_value", "sum"), cogs_ttm=("cogs_ttm", "sum"), avg_stock=("avg_stock_value_ttm", "sum"), aged_180=("aged_180_value", "sum")).reset_index()
    catinv["turnover"] = catinv.cogs_ttm / catinv.avg_stock
    catinv["dio_days"] = 365 / catinv.turnover
    save(catinv, "inventory_by_category")
    # allocated (custom & reserved) vs stocked
    snap_all = mv.assign(m=mv.movement_date.dt.to_period("M")).pivot_table(index="m", columns="inventory_state", values="value_cad", aggfunc="sum", fill_value=0).cumsum()
    snap_all.index = snap_all.index.to_timestamp()
    save(snap_all.reset_index().rename(columns={"m": "month", "stock": "stocked_value", "allocated": "allocated_to_customers_value"}), "inventory_value_by_state_monthly")
    # suppliers
    rec2 = rec.merge(D["suppliers"][["supplier_id", "supplier_name", "supplier_class"]], on="supplier_id")
    rec2 = rec2[rec2.received_date >= "2024-01-01"]
    sl = rec2.groupby(["supplier_name", "supplier_class"]).agg(pos=("po_id", "count"), on_time_pct=("delay_days", lambda x: (x <= 2).mean() * 100), avg_delay_days=("delay_days", "mean"),
                                                                 p90_delay_days=("delay_days", lambda x: x.quantile(.9)), custom_pos=("po_type", lambda x: (x == "Custom").sum())).reset_index()
    dmg = po[po.status == "Damaged - replaced"].merge(D["suppliers"][["supplier_id", "supplier_name"]], on="supplier_id").groupby("supplier_name").size()
    sl["damaged_on_arrival"] = sl.supplier_name.map(dmg).fillna(0).astype(int)
    save(sl.sort_values("pos", ascending=False), "supplier_lead_time_performance")
    so = D["stockout_events"]
    K.update(stock_value=stocked.stock_value.sum(), alloc_value=(p.allocated_to_customers_units * p.unit_cost_cad).sum(), aged_180=stocked.aged_180_value.sum(),
             overstock_value=stocked[stocked.overstock].stock_value.sum(), overstock_n=int(stocked.overstock.sum()), turnover=stocked.cogs_ttm.sum() / stocked.avg_stock_value_ttm.sum(),
             lost_sales_ttm=so[so.event_date >= TTM0].lost_revenue_est_cad.sum(), reorder_now=int((stocked.action == "Reorder now").sum()),
             carrying_cost=stocked.carrying_cost_annual.sum(), supplier_on_time=(rec2.delay_days <= 2).mean())
    worst = sl[sl.pos >= 30].sort_values("on_time_pct").iloc[0]
    F["inventory"] = (f"Stocked inventory is {money(K['stock_value'])} at cost ({K['turnover']:.1f} turns a year); {K['overstock_n']} SKUs carry more than 180 days of cover "
                      f"({money(K['overstock_value'])}) and {money(K['aged_180'])} has been on the floor more than six months. Carrying cost at {CARRY:.0%} a year is "
                      f"~{money(K['carrying_cost'])}. A further {money(K['alloc_value'])} is customer-allocated (custom and reserved) and already sold.")
    F["stockouts"] = (f"Stockouts on ready-made lines cost an estimated {money(K['lost_sales_ttm'])} of sales in the last twelve months, while slow lines sit overstocked - "
                      f"{K['reorder_now']} SKUs should be reordered now under service-level reorder points.")
    F["suppliers"] = (f"Suppliers delivered {K['supplier_on_time']:.0%} of purchase orders on time; {worst.supplier_name} ({worst.supplier_class}) is weakest at "
                      f"{worst.on_time_pct:.0f}% on time with a 90th-percentile delay of {worst.p90_delay_days:.0f} days.")


# ----------------------------------------------------------------------------------------------- custom orders & fulfilment
def orders_fulfilment(D, F, K):
    o = D["orders"]
    f = D["fulfillment"]
    pay = D["payments"]
    s = D["sales_transactions"]
    po = D["purchase_orders"]
    openo = o[o.status.isin(["Awaiting supplier", "Ready - awaiting pickup/delivery"])].copy()
    openo["days_open"] = (END_TS - openo.order_date).dt.days
    openo["days_past_promise"] = (END_TS - openo.promised_ready_date).dt.days.clip(lower=0)
    openo["aging_band"] = pd.cut(openo.days_open, [-1, 30, 60, 90, 120, 10000], labels=["0-30", "31-60", "61-90", "91-120", ">120"])
    eta = po[po.status == "Open"].assign(oid=lambda x: x.order_line_id.map(s.set_index("line_id").order_id)).groupby("oid").promised_date.max()
    openo["supplier_eta"] = openo.order_id.map(eta)
    cost_alloc = s[s.line_status == "Allocated - awaiting pickup/delivery"].groupby("order_id").cogs_cad.sum()
    openo["allocated_inventory_cost"] = openo.order_id.map(cost_alloc).fillna(0)
    save(openo[["order_id", "customer_id", "order_date", "order_type", "sales_channel", "status", "promised_ready_date", "supplier_eta", "ready_date", "days_open", "days_past_promise",
                "aging_band", "net_order_value_cad", "order_total_incl_gst_cad", "deposit_paid_cad", "balance_outstanding_cad", "fulfillment_method", "allocated_inventory_cost"]],
         "open_orders_tracker")
    ful = f[f.status == "Fulfilled"]
    pick = o[(o.fulfillment_method == "Customer pickup") & (o.status == "Fulfilled") & (o.fulfilled_date != o.order_date)].groupby("fulfilled_date").size()
    util = pick.reindex(pd.date_range("2024-01-01", END), fill_value=0)
    util = util[util.index.dayofweek != 6]
    pu = pd.DataFrame({"date": util.index, "pickups": util.values})
    pu["utilisation_pct"] = pu.pickups / 9 * 100
    pu["dow"] = pu.date.dt.day_name()
    save(pu.groupby("dow").agg(avg_pickups=("pickups", "mean"), avg_util=("utilisation_pct", "mean"), days_full=("pickups", lambda x: (x >= 9).sum())).reset_index(), "pickup_slot_utilisation")
    fm = ful.groupby(["order_type", "fulfillment_method"]).agg(orders=("order_id", "count"), ready_on_time_pct=("ready_delay_days", lambda x: (x <= 0).mean() * 100),
                                                               median_ready_delay=("ready_delay_days", "median"), median_handoff_wait=("handoff_wait_days", "median"),
                                                               damage_pct=("damage_flag", "mean"), retailer_cost=("retailer_fulfillment_cost_cad", "sum"),
                                                               carrier_fees_paid_by_customers=("carrier_fee_customer_paid_cad", "sum")).reset_index()
    fm["damage_pct"] *= 100
    save(fm, "fulfilment_performance")
    save(f.groupby(["delay_category"]).size().rename("orders").reset_index(), "readiness_delay_categories")
    save(f.groupby(["handoff_wait_reason"]).size().rename("orders").reset_index(), "handoff_wait_reasons")
    can = o[(o.status == "Cancelled") & (o.order_date >= "2024-01-01")]
    cr = can.groupby(["order_type", "cancel_reason"]).agg(orders=("order_id", "count"), value=("net_order_value_cad", "sum"), retained_fees=("retained_cancellation_fee_cad", "sum")).reset_index()
    save(cr, "cancellations")
    # cash tied up: monthly deposits held vs inventory allocated
    months = pd.period_range("2024-01", END[:7], freq="M")
    pos_pay = pay[(pay.amount_incl_gst > 0) & ~pay.payment_type.str.startswith("Trade account settlement")]
    rows = []
    for m in months:
        at = m.end_time.normalize()
        op = o[(o.order_date <= at) & ~((o.fulfilled_date <= at) | (o.cancel_date <= at))]
        dep = pos_pay[pos_pay.order_id.isin(op.order_id) & (pos_pay.payment_date <= at)].amount_incl_gst.sum()
        rows.append({"month": m.start_time, "open_orders": len(op), "open_order_value_incl_gst": op.order_total_incl_gst_cad.sum(), "deposits_held": dep,
                     "balances_still_to_collect": op.order_total_incl_gst_cad.sum() - dep, "open_custom_orders": int((op.order_type == "Custom").sum())})
    ct = pd.DataFrame(rows)
    save(ct, "open_order_backlog_monthly")
    late = ful[ful.order_type == "Custom"]
    K.update(open_orders=len(openo), open_custom=int((openo.order_type == "Custom").sum()), open_value=openo.order_total_incl_gst_cad.sum(), deposits_held=openo.deposit_paid_cad.sum(),
             balances_to_collect=openo.balance_outstanding_cad.sum(), overdue_open=int((openo.days_past_promise > 0).sum()), custom_on_time=(late.ready_delay_days <= 0).mean(),
             cancel_rate_custom=(o[o.order_type == "Custom"].status == "Cancelled").mean(), pickup_full_days=int((pu.pickups >= 9).sum()),
             sat_util=pu[pu.dow == "Saturday"].utilisation_pct.mean(), retained_fees=can.retained_cancellation_fee_cad.sum())
    F["orders"] = (f"{K['open_orders']} orders are open ({K['open_custom']} custom) worth {money(K['open_value'])} incl. GST; customers have paid {money(K['deposits_held'])} in deposits "
                   f"and {money(K['balances_to_collect'])} is still to collect at pickup. {K['overdue_open']} open orders are past their promised ready date.")
    F["fulfilment"] = (f"Only {K['custom_on_time']:.0%} of custom orders were ready by the promised date; {K['cancel_rate_custom']:.1%} of custom orders cancel, mostly after supplier delays. "
                       f"Saturday pickup slots run at {K['sat_util']:.0f}% utilisation and all 9 slots were full on {K['pickup_full_days']} days.")


# ----------------------------------------------------------------------------------------------- customers & consultations
def customers_consults(D, F, K):
    c = D["customers"]
    v = D["valid"]
    o = D["orders"][(D["orders"].status != "Cancelled")]
    buyers = c[c.orders > 0].copy()
    buyers["recency_months"] = ((END_TS - buyers.last_order_date).dt.days / 30.4).round(1)
    buyers["R"] = pd.cut(buyers.recency_months, [-1, 6, 12, 24, 100], labels=[4, 3, 2, 1]).astype(int)
    buyers["F"] = np.clip(buyers.orders, 1, 3) + (buyers.orders >= 4)
    buyers["M"] = pd.qcut(buyers.lifetime_net_sales_cad.rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    trade = buyers.customer_type.isin(["Interior designer (trade)", "Business / hospitality", "Real-estate stager"])

    def seg(r, t):
        if t:
            return "Trade & business accounts"
        if r.F >= 2 and r.R >= 3:
            return "Repeat loyalists"
        if r.F >= 2:
            return "Repeat - lapsing"
        if r.R >= 3 and r.M >= 3:
            return "Recent big-ticket buyers"
        if r.R >= 3:
            return "Recent first-time buyers"
        if r.M >= 3:
            return "One-time big-ticket (12m+)"
        return "One-time small-basket (12m+)"
    buyers["segment"] = [seg(r, t) for r, t in zip(buyers.itertuples(), trade)]
    # repeat behaviour for CLV: share of first-time buyers who purchase again within 12 / 24 months (cohorts with full observation)
    first = buyers.first_order_date
    nxt = v.sort_values("transaction_date").groupby("customer_id").transaction_date.apply(lambda x: x.drop_duplicates().iloc[1] if x.nunique() > 1 else pd.NaT)
    buyers["second_order_date"] = buyers.customer_id.map(nxt)
    gap = (buyers.second_order_date - first).dt.days
    obs12 = buyers[first <= END_TS - pd.Timedelta(days=365)]
    obs24 = buyers[first <= END_TS - pd.Timedelta(days=730)]
    p12 = (gap[obs12.index] <= 365).mean()
    p24 = (gap[obs24.index] <= 730).mean()
    gp_order = (v.groupby("order_id").gross_profit_cad.sum()).mean()
    annual_repeat = 1 - (1 - p24) ** 0.5
    buyers["clv_5y_gp"] = buyers.lifetime_gross_profit_cad + sum(annual_repeat * gp_order * (0.9 ** y) for y in range(1, 6)) * np.where(buyers.R >= 2, 1.0, 0.5)
    sp = buyers.groupby("segment").agg(customers=("customer_id", "count"), avg_recency_months=("recency_months", "mean"), avg_orders=("orders", "mean"),
                                       avg_lifetime_sales=("lifetime_net_sales_cad", "mean"), total_sales=("lifetime_net_sales_cad", "sum"), avg_clv_5y_gp=("clv_5y_gp", "mean")).reset_index()
    sp["sales_share_pct"] = sp.total_sales / sp.total_sales.sum() * 100
    strat = {"Trade & business accounts": "Dedicated trade rep, net-30 terms, early access to floor models and quantity pricing.",
             "Repeat loyalists": "Room-completion offers (the next room), protection-plan renewals, VIP previews of new collections.",
             "Repeat - lapsing": "Win-back with design-refresh consult invitations and accessory bundles.",
             "Recent big-ticket buyers": "Post-delivery check-in, care kits, complementary pieces at 60-90 days (rug, lighting, side tables).",
             "Recent first-time buyers": "Review request + referral credit; invite to free design consult for the next room.",
             "One-time big-ticket (12m+)": "Seasonal refresh campaigns (spring, fall moving season) and mattress/bedroom cross-sell.",
             "One-time small-basket (12m+)": "Low-cost email/social nurture; promote contests and clearance events."}
    sp["strategy"] = sp.segment.map(strat)
    save(buyers[["customer_id", "customer_type", "acquisition_channel", "first_order_date", "last_order_date", "orders", "lifetime_net_sales_cad", "lifetime_gross_profit_cad",
                 "recency_months", "R", "F", "M", "segment", "clv_5y_gp"]].round(2), "customer_rfm")
    save(sp.sort_values("total_sales", ascending=False).round(2), "customer_segments")
    # retention cohorts
    buyers["cohort"] = first.dt.to_period("Q").astype(str)
    coh = buyers.groupby("cohort").apply(lambda g: pd.Series({"new_customers": len(g), "repeat_6m_pct": ((g.second_order_date - g.first_order_date).dt.days <= 182).mean() * 100,
                                                               "repeat_12m_pct": ((g.second_order_date - g.first_order_date).dt.days <= 365).mean() * 100,
                                                               "repeat_to_date_pct": g.second_order_date.notna().mean() * 100}), include_groups=False).reset_index()
    save(coh, "retention_cohorts")
    # marketing attribution (new customers by acquisition channel vs channel spend)
    newc = buyers[buyers.first_order_date >= "2024-01-01"]
    att = newc.groupby("acquisition_channel").agg(new_customers=("customer_id", "count"), first_year_sales=("lifetime_net_sales_cad", "sum")).reset_index()
    ms = D["marketing_spend"].groupby("marketing_channel").spend_cad.sum()
    mapping = {"Google search": ["Google search ads"], "Social media & contests": ["Meta / Instagram ads", "Contests & community giveaways"], "Review sites": ["Review & marketplace listings"],
               "Online store": ["Website, SEO & e-commerce"], "Showroom walk-in": ["Flyers, radio & print"]}
    att["attributed_spend"] = att.acquisition_channel.map(lambda ch: sum(ms.get(x, 0) for x in mapping.get(ch, [])))
    att["cac"] = np.where(att.attributed_spend > 0, att.attributed_spend / att.new_customers, np.nan)
    att["sales_per_spend_dollar"] = np.where(att.attributed_spend > 0, att.first_year_sales / att.attributed_spend, np.nan)
    leads = D["leads"]
    lc = leads.groupby("lead_channel").agg(leads=("lead_id", "count"), won=("converted", "sum")).reset_index()
    lc["conversion_pct"] = lc.won / lc.leads * 100
    att = att.merge(lc, left_on="acquisition_channel", right_on="lead_channel", how="left").drop(columns="lead_channel")
    save(att.sort_values("first_year_sales", ascending=False), "marketing_attribution")
    # consultations
    cs = D["consultations"]
    cs = cs[cs.consultation_date >= "2024-01-01"]
    closed = cs[cs.conversion_status != "Open - follow-up in progress"]
    by = lambda col: closed.groupby(col).agg(consults=("consultation_id", "count"), conversion_pct=("converted", lambda x: x.mean() * 100),
                                            revenue=("final_sales_revenue_cad", "sum"), avg_quote=("quotation_amount_cad", "mean"),
                                            cost=("estimated_conversion_cost_cad", "sum")).reset_index()
    tabs = {}
    for col in ["designer_id", "consultation_type", "follow_up_count"]:
        t = by(col)
        t["revenue_per_consult"] = t.revenue / t.consults
        t["cost_per_conversion"] = t.cost / (t.consults * t.conversion_pct / 100)
        tabs[col] = t
        save(t, f"consultations_by_{col}")
    closed = closed.assign(quote_band=pd.cut(closed.quotation_amount_cad, [0, 3000, 6000, 10000, 20000, 1e9], labels=["<$3K", "$3-6K", "$6-10K", "$10-20K", ">$20K"]))
    qb = closed.groupby("quote_band", observed=True).agg(consults=("consultation_id", "count"), conversion_pct=("converted", lambda x: x.mean() * 100),
                                                          avg_order=("final_sales_revenue_cad", lambda x: x[x > 0].mean())).reset_index()
    save(qb, "consultations_by_quote_band")
    cm = cs.assign(m=cs.consultation_date.dt.to_period("M").dt.to_timestamp()).groupby("m").agg(consults=("consultation_id", "count"), converted=("converted", "sum"),
                                                                                                 revenue=("final_sales_revenue_cad", "sum")).reset_index().rename(columns={"m": "month"})
    save(cm, "consultations_monthly")
    aov_c = o[(o.sales_channel == "Design consultation") & (o.order_date >= "2024-01-01")].net_order_value_cad.mean()
    aov_n = o[(o.sales_channel != "Design consultation") & (o.order_date >= "2024-01-01")].net_order_value_cad.mean()
    K.update(customers=len(buyers), repeat_12m=p12, repeat_24m=p24, consult_conv=closed.converted.mean(), aov_consult=aov_c, aov_other=aov_n,
             consult_revenue=cs.final_sales_revenue_cad.sum(), consult_cost=cs.estimated_conversion_cost_cad.sum(),
             fu0=tabs["follow_up_count"].set_index("follow_up_count").conversion_pct.get(0, np.nan), fu2=tabs["follow_up_count"].set_index("follow_up_count").conversion_pct.get(2, np.nan),
             clv_avg=buyers.clv_5y_gp.mean(), open_quotes=int((cs.conversion_status == "Open - follow-up in progress").sum()),
             open_quote_value=cs[cs.conversion_status == "Open - follow-up in progress"].quotation_amount_cad.sum())
    best_d = tabs["designer_id"].sort_values("conversion_pct").iloc[-1]
    worst_d = tabs["designer_id"].sort_values("conversion_pct").iloc[0]
    F["customers"] = (f"Furniture is bought rarely: only {K['repeat_12m']:.0%} of first-time buyers return within 12 months ({K['repeat_24m']:.0%} within 24). "
                      f"Value therefore comes from basket size and referrals; estimated 5-year customer value averages {money(K['clv_avg'])} of gross profit.")
    F["consults"] = (f"Free design consultations convert {K['consult_conv']:.0%} of the time and the resulting orders average {money(K['aov_consult'])} vs {money(K['aov_other'])} for other orders. "
                     f"Follow-up matters: {K['fu0']:.0f}% conversion with no follow-up vs {K['fu2']:.0f}% with two. Designer conversion ranges from {worst_d.conversion_pct:.0f}% "
                     f"({worst_d.designer_id}) to {best_d.conversion_pct:.0f}% ({best_d.designer_id}).")


def run():
    D = load()
    F, K = {}, {}
    sales(D, F, K)
    inventory(D, F, K)
    orders_fulfilment(D, F, K)
    customers_consults(D, F, K)
    K = {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v) for k, v in K.items()}
    (TABLES / "findings.json").write_text(json.dumps({"metrics": K, "findings": F, "data_status": "SYNTHETIC"}, indent=1, default=str))
    return K, F


if __name__ == "__main__":
    K, F = run()
    for k, v in F.items():
        print(f"[{k}] {v}\n")
