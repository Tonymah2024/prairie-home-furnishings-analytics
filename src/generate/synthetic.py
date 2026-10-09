"""Day-by-day synthetic operations of the FICTIONAL retailer "Prairie Home Furnishings" (Calgary).

EVERYTHING produced here is SYNTHETIC DEMONSTRATION DATA. Real inputs are limited to the product catalogue
(titles, manufacturers, CAD list prices from a public Calgary retailer feed), publicly described policies used as
behavioural rules (9 pickup slots/day, balance due before pickup, 3-day in-stock returns with a 15% restocking
fee, custom orders non-refundable, free design consultations, 0% financing, customer-paid third-party delivery),
Alberta holidays and Bank of Canada rates. Every quantity, cost, customer, order, payment and expense is simulated.

The simulation starts with a warm-up (Sep-Dec 2023) so 1 Jan 2024 opens with realistic stock, open orders and
customer deposits; only the open backlog from the warm-up is kept (flagged opening_backlog). Inventory reconciles
exactly per SKU and per state (stock / allocated-to-customer):  opening + receipts - fulfilments +/- reclasses = closing.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque

import numpy as np
import pandas as pd

from src.config import END, EXTERNAL, SEED, START, SYNTH
from src.research.build_catalogue import LEAD

WARMUP = "2023-09-01"
GST = 0.05
# ---------------------------------------------------------------------------------------------- ASSUMPTIONS (synthetic)
MONTH_SEASON = {1: 1.12, 2: 0.86, 3: 0.98, 4: 1.04, 5: 1.06, 6: 0.90, 7: 0.84, 8: 0.98, 9: 1.08, 10: 1.10, 11: 1.24, 12: 0.80}
DOW = {0: 0.80, 1: 0.78, 2: 0.86, 3: 0.95, 4: 1.12, 5: 1.62, 6: 0.0}           # store closed Sundays
BASE_ORDERS = 7.0                    # walk-in/online/phone/trade orders per open day at index 1.0 (2024)
BASE_CONSULTS = 2.1                  # design consultations per open day at index 1.0
PICKUP_SLOTS = 9                     # published: 9 pickup slots per day
DEPOSIT = 0.50                       # deposit on custom, special-order and scheduled in-stock orders (ASSUMPTION)
TRADE_DEPOSIT = 0.30
FIN_FEE = 0.06                       # financing partner merchant discount (ASSUMPTION)
PLAN_RATE, PLAN_MIN, PLAN_COMMISSION = 0.08, 99.0, 0.40   # protection plan price, minimum, retailer commission (agent)
FLAT_DELIVERY = 199.0                # published flat-rate Calgary delivery for online orders over $999 (collected as agent)
CUSTOMER_TYPES = (["Homeowner", "Condo / apartment", "New-home buyer", "Interior designer (trade)", "Business / hospitality", "Real-estate stager", "Student / first apartment"],
                  [.53, .17, .12, .05, .03, .03, .07])
TRADE = {"Interior designer (trade)", "Business / hospitality", "Real-estate stager"}
ACQ = (["Google search", "Social media & contests", "Showroom walk-in", "Referral / word of mouth", "Online store", "Review sites", "Real-estate partner"],
       [.24, .21, .18, .14, .12, .07, .04])
LEAD_CONV = {"Google search": .22, "Social media & contests": .07, "Showroom walk-in": .38, "Referral / word of mouth": .40, "Online store": .18,
             "Review sites": .20, "Real-estate partner": .30}
PROMOS = [  # name, start (MM-DD), end, extra discount, demand multiplier, scope
    ("New Year Blowout", "01-02", "01-20", 0.10, 1.25, "All"), ("Spring Refresh Event", "04-10", "04-30", 0.08, 1.15, "All"),
    ("Canada Day Sale", "06-27", "07-03", 0.10, 1.20, "All"), ("Summer Clearance (aged stock)", "07-15", "08-10", 0.22, 1.10, "Aged"),
    ("Labour Day Sale", "08-28", "09-07", 0.10, 1.18, "All"), ("Black Friday Event", "11-20", "12-01", 0.15, 1.45, "All"),
    ("Holiday Sale", "12-05", "12-23", 0.08, 1.08, "All"), ("Boxing Week", "12-26", "12-31", 0.15, 1.30, "All"),
]
ROOMS = [("Living room", .36), ("Bedroom", .21), ("Mattress only", .09), ("Dining", .16), ("Décor & lighting only", .12), ("Home office", .02), ("Single occasional piece", .04)]
FABRIC = [("Grade A fabric", 0.0, .45), ("Grade B fabric", .08, .30), ("Grade C performance fabric", .15, .15), ("Top-grain leather", .28, .10)]
CONFIG = {"Sectionals": [("Left-arm chaise", 0.0), ("Right-arm chaise", 0.0), ("U-shape (3 pc)", .18), ("Modular 4 pc", .26)],
          "Sofas": [("Standard 3-seat", 0.0), ("Apartment size", -.06), ("Extra-long 4-seat", .10)]}
DESIGNERS = {"DSN-01": 1.15, "DSN-02": 1.0, "DSN-03": .90, "DSN-04": 1.05}
CONSULT_TYPES = [("In-store design consult", .58, 0.0, 1.8), ("In-home measure & design", .22, .45, 3.5), ("Virtual design consult", .20, -.25, 1.2)]
DELAY_REASONS = ["Supplier production backlog", "Fabric / material shortage", "Freight & transit delay", "Supplier capacity (peak season)"]
CARRIERS = ["Carrier A (fictional)", "Carrier B (fictional)", "Carrier C (fictional)"]


# ---------------------------------------------------------------------------------------------- helpers
class IDs:
    def __init__(self):
        self.c = defaultdict(int)

    def __call__(self, prefix, width=6):
        self.c[prefix] += 1
        return f"{prefix}-{self.c[prefix]:0{width}d}"


def promo_on(d: pd.Timestamp, name_filter=None):
    md = d.strftime("%m-%d")
    for name, s, e, disc, mult, scope in PROMOS:
        if s <= md <= e and (name_filter is None or scope == name_filter):
            return {"promotion_id": f"PRM-{d.year}-{name.split()[0][:4].upper()}{s[:2]}", "name": name, "disc": disc, "mult": mult, "scope": scope}
    return None


def add_business_days(d, n, open_set):
    k = 0
    while k < n:
        d = d + pd.Timedelta(days=1)
        if d in open_set:
            k += 1
    return d


def next_open(d, open_set):
    while d not in open_set:
        d = d + pd.Timedelta(days=1)
    return d


# ---------------------------------------------------------------------------------------------- simulation
def simulate():
    rng = np.random.default_rng(SEED)
    ids = IDs()
    cat = pd.read_csv(EXTERNAL / "catalogue_curated.csv")
    hol = set(pd.to_datetime(pd.read_csv(EXTERNAL / "alberta_holidays.csv").date))
    econ = pd.read_csv(EXTERNAL / "economic_indicators_monthly.csv", parse_dates=["month"]).set_index("month").policy_rate_pct
    days = pd.date_range(WARMUP, END, freq="D")
    xmas = {d for d in days if d.strftime("%m-%d") in ("12-25", "12-26")}
    open_set = {d for d in days if d.dayofweek != 6 and d not in hol and d not in xmas}
    open_set |= {d for d in pd.date_range(pd.Timestamp(END) + pd.Timedelta(days=1), periods=400) if d.dayofweek != 6 and d not in hol}

    # ---- products & suppliers
    P = cat.set_index("product_id")
    sup_of = {m: f"SUP-{i + 1:02d}" for i, m in enumerate(sorted(cat.manufacturer.unique()))}
    suppliers = pd.DataFrame([{"supplier_id": s, "supplier_name": m, "supplier_class": cat[cat.manufacturer == m].supplier_class.mode()[0],
                               "quoted_lead_days": int(LEAD[cat[cat.manufacturer == m].supplier_class.mode()[0]][0]),
                               "payment_terms": "Net 30", "region": "Canada" if m in ("Decor-Rest", "Elite", "Mercana", "LH Imports", "Sahara Furniture", "Aurora", "Kalora")
                               else "North America / import"} for m, s in sup_of.items()])
    sup_quality = {s: float(np.exp(rng.normal(0, 0.35))) for s in sup_of.values()}       # supplier-specific delay multiplier
    stocked = P[P.fulfillment_type.str.startswith("Stocked")].index.tolist()
    by_sub = {sub: g.index.tolist() for sub, g in P.groupby("subcategory")}
    pop = P.popularity_prior.to_dict()

    def pick(sub, custom=None):
        pool = [p for p in by_sub.get(sub, []) if custom is None or bool(P.at[p, "custom"]) == custom]
        if not pool:
            pool = by_sub.get(sub, [])
        if not pool:
            return None
        w = np.array([pop[p] for p in pool])
        return pool[rng.choice(len(pool), p=w / w.sum())]

    def basket(room, rich=1.0):
        L = []
        if room == "Living room":
            sub = rng.choice(["Sectionals", "Sofas", "Loveseats", "Recliners", "Sofa beds"], p=[.42, .33, .10, .12, .03])
            L.append((pick(sub, custom=rng.random() < 0.52), 1))
            for s, pr in [("Coffee tables", .36), ("Side & accent tables", .26), ("Accent chairs", .20), ("Rugs", .22), ("Media cabinets", .07), ("Lighting", .14)]:
                if rng.random() < pr * rich:
                    L.append((pick(s), 2 if s == "Side & accent tables" and rng.random() < .3 else 1))
            for _ in range(rng.poisson(0.55 * rich)):
                L.append((pick(rng.choice(["Wall art", "Textiles & poufs", "Decorative accessories", "Mirrors"])), 1))
        elif room == "Bedroom":
            if rng.random() < .86:
                L.append((pick(rng.choice(["Beds", "Kids beds", "Murphy beds"], p=[.82, .12, .06])), 1))
            if rng.random() < .62:
                L.append((pick("Mattresses"), 1))
            if rng.random() < .50 * rich:
                L.append((pick("Nightstands"), int(rng.choice([1, 2], p=[.4, .6]))))
            if rng.random() < .34 * rich:
                L.append((pick("Dressers & chests"), 1))
            if rng.random() < .18:
                L.append((pick("Textiles & poufs"), 1))
            if rng.random() < .07:
                L.append((pick("Adjustable bases"), 1))
        elif room == "Mattress only":
            L.append((pick("Mattresses"), 1))
            if rng.random() < .15:
                L.append((pick("Adjustable bases"), 1))
        elif room == "Dining":
            if rng.random() < .86:
                L.append((pick(rng.choice(["Dining tables", "Kitchen islands"], p=[.95, .05])), 1))
            if rng.random() < .85:
                L.append((pick("Dining chairs"), int(rng.choice([2, 4, 6, 8], p=[.12, .50, .30, .08]))))
            if rng.random() < .16:
                L.append((pick("Bar & counter stools"), int(rng.choice([2, 3, 4], p=[.5, .25, .25]))))
            if rng.random() < .24 * rich:
                L.append((pick("Sideboards & buffets"), 1))
            if rng.random() < .14:
                L.append((pick("Lighting"), 1))
        elif room == "Décor & lighting only":
            for _ in range(1 + rng.poisson(0.8)):
                L.append((pick(rng.choice(["Wall art", "Lighting", "Mirrors", "Rugs", "Textiles & poufs", "Decorative accessories"], p=[.22, .24, .12, .16, .14, .12])), 1))
        elif room == "Home office":
            L.append((pick("Desks"), 1))
            if rng.random() < .5:
                L.append((pick("Cabinets & storage"), 1))
            if rng.random() < .3:
                L.append((pick("Accent chairs"), 1))
        else:
            L.append((pick(rng.choice(["Accent chairs", "Coffee tables", "Console tables", "Ottomans & benches", "Cabinets & storage"])), 1))
        return [(p, q) for p, q in L if p is not None]

    # ---- expected daily stocked demand (Monte Carlo of baskets) -> initial stocking policy
    mc = defaultdict(float)
    rp = np.array([r[1] for r in ROOMS])
    for _ in range(6000):
        for p, q in basket(ROOMS[rng.choice(len(ROOMS), p=rp / rp.sum())][0]):
            mc[p] += q
    exp_orders = BASE_ORDERS * 1.0 + BASE_CONSULTS * 0.45 * 1.6
    rate = {p: mc[p] / 6000 * exp_orders * 312 / 365 for p in P.index}              # units per calendar day
    lt = {p: LEAD[P.at[p, "supplier_class"]][0] for p in P.index}
    on_hand = {}
    rop, upto = {}, {}
    slow = set(rng.choice(stocked, size=int(len(stocked) * 0.12), replace=False))  # over-bought / slow lines (current practice)
    for p in stocked:
        d = max(rate[p], 0.004)
        rop[p] = max(1, int(math.ceil(d * lt[p] * 1.15)))
        upto[p] = rop[p] + max(2, int(math.ceil(d * 42)))
        on_hand[p] = upto[p] * (4 if p in slow else 1)
        if p in slow:
            pop[p] *= 0.35
    for p in P.index:
        on_hand.setdefault(p, 0)
    allocated = defaultdict(int)          # product -> units held for customers
    on_order = defaultdict(int)
    stock_cost = P.unit_cost_cad.to_dict()

    rec = defaultdict(list)               # table name -> list of dicts
    moves = []

    def move(d, p, mtype, state, qty, ref, unit_cost):
        moves.append((d, p, mtype, state, int(qty), round(float(unit_cost), 2), ref))

    for p in P.index:
        if on_hand[p]:
            move(pd.Timestamp(WARMUP), p, "WARMUP_OPENING", "stock", on_hand[p], "WARMUP", stock_cost[p])

    customers = {}
    past_customers = []
    staff_sales = [("EMP-S01", "2019-03-01", None, 1.10), ("EMP-S02", "2020-06-01", None, 1.0), ("EMP-S03", "2021-02-01", None, .95), ("EMP-S04", "2022-04-15", "2025-05-31", .90),
                   ("EMP-S05", "2022-09-01", None, 1.05), ("EMP-S06", "2023-05-01", None, .85), ("EMP-S07", "2024-03-01", None, 1.0), ("EMP-S08", "2025-04-01", None, .92),
                   ("EMP-S09", "2025-08-15", None, .88)]

    def reps_on(d):
        return [s for s in staff_sales if pd.Timestamp(s[1]) <= d and (s[2] is None or pd.Timestamp(s[2]) >= d)]

    orders, lines, pos, payments, fulfil, consults, returns, stockouts, leads = {}, [], {}, [], {}, [], [], [], []
    pending_conv = defaultdict(list)       # date -> consultation dicts converting that day
    receipts_due = defaultdict(list)       # date -> po_id
    sched = defaultdict(list)              # date -> order_id fulfilment
    returns_due = defaultdict(list)
    open_orders = {}                      # insertion-ordered (a set would make iteration order, and hence draws, run-dependent)
    clearance_age = {}                     # product -> first date it became aged stock

    def new_customer(d, ctype=None, channel=None):
        cid = ids("CUST", 6)
        ctype = ctype or rng.choice(CUSTOMER_TYPES[0], p=CUSTOMER_TYPES[1])
        channel = channel or rng.choice(ACQ[0], p=ACQ[1])
        customers[cid] = {"customer_id": cid, "customer_type": ctype, "acquisition_channel": channel, "created_date": d,
                          "postal_area": rng.choice(["NW Calgary", "SW Calgary", "NE Calgary", "SE Calgary", "Inner city", "Airdrie / Cochrane / Okotoks", "Elsewhere in Alberta"],
                                                    p=[.24, .21, .12, .16, .12, .11, .04])}
        return cid

    def pay(d, oid, kind, amount, tender):
        if abs(amount) < 0.005:
            return
        payments.append({"payment_id": ids("PAY", 7), "order_id": oid, "payment_date": d, "payment_type": kind, "tender": tender, "amount_incl_gst": round(amount, 2)})

    def place_po(d, kind, p, qty, line_id=None, unit_cost=None, lead_extra=0):
        s = sup_of[P.at[p, "manufacturer"]]
        cls = P.at[p, "supplier_class"]
        q_lead, mu, sd, ontime = LEAD[cls]
        order_d = add_business_days(d, int(rng.integers(0, 3)), open_set) if kind != "Stock replenishment" else d
        promised = order_d + pd.Timedelta(days=int(q_lead + lead_extra))
        season = 6 if order_d.month in (10, 11, 12) else (3 if order_d.month in (1, 2) else 0)
        yr = 3 if order_d.year == 2024 else (0 if order_d.year == 2025 else -1)
        if rng.random() < ontime * (0.93 if season else 1.0):
            delay = int(rng.integers(-3, 3))
        else:
            delay = int(max(1, rng.gamma(2.0, (mu + season + yr) * sup_quality[s] / 2 + 3)))
        arrive = next_open(promised + pd.Timedelta(days=delay), open_set)
        po_id = ids("PO", 6)
        pos[po_id] = {"po_id": po_id, "po_type": kind, "supplier_id": s, "product_id": p, "order_line_id": line_id, "order_date": order_d,
                      "promised_date": promised, "received_date": arrive, "qty_ordered": int(qty), "qty_received": 0, "qty_damaged": 0,
                      "unit_cost_cad": round(unit_cost if unit_cost is not None else stock_cost[p], 2), "status": "Open",
                      "delay_days": (arrive - promised).days, "delay_reason": None if delay <= 2 else rng.choice(DELAY_REASONS, p=[.38, .24, .22, .16]),
                      "replacement_of": None}
        receipts_due[arrive].append(po_id)
        if line_id:
            po_by_line[line_id].append(po_id)
        if kind == "Stock replenishment":
            on_order[p] += qty
        return po_id

    # ---------------------------------------------------------------- create an order
    def create_order(d, channel, cid, rep, consult=None, room=None, target_value=None):
        ctype = customers[cid]["customer_type"]
        rich = 1.35 if consult else (1.15 if ctype in TRADE else 1.0)
        room = room or ROOMS[rng.choice(len(ROOMS), p=rp / rp.sum())][0]
        items = basket(room, rich)
        if consult:                                   # whole-room design projects: keep adding rooms until near the quote
            while sum(P.at[p, "list_price_cad"] * q for p, q in items) < target_value * 0.8 and len(items) < 14:
                items += basket(rng.choice(["Living room", "Bedroom", "Dining", "Décor & lighting only"], p=[.45, .25, .2, .1]), rich)
        promo = promo_on(d)
        oid = ids("ORD", 6)
        o_lines = []
        any_custom = any_special = False
        merged = defaultdict(int)
        for p, qty in items:
            merged[p] += qty
        reserved = defaultdict(int)
        for p, qty in merged.items():
            prod = P.loc[p]
            custom = bool(prod.custom)
            uplift, material, config = 0.0, "Standard", "Standard"
            if custom:
                f = FABRIC[rng.choice(len(FABRIC), p=[x[2] for x in FABRIC])]
                material, uplift = f[0], f[1]
                if prod.subcategory in CONFIG:
                    c = CONFIG[prod.subcategory][rng.integers(len(CONFIG[prod.subcategory]))]
                    config, uplift = c[0], uplift + c[1]
                if rng.random() < .35:
                    config += " + high-density foam"
                    uplift += .06
            price = round(prod.list_price_cad * (1 + uplift), 2)
            aged = p in clearance_age and (d - clearance_age[p]).days > 180
            disc, reason = 0.0, None
            if promo and (promo["scope"] == "All" or (promo["scope"] == "Aged" and aged)) and not (prod.category == "Mattresses & Bases" and rng.random() < .5):
                disc, reason = promo["disc"], "Promotion"
            elif aged and rng.random() < .55:
                disc, reason = float(rng.choice([.25, .30, .40])), "Clearance (aged stock)"
            elif ctype in TRADE:
                disc, reason = float(rng.choice([.10, .12, .15])), "Trade discount"
            elif rng.random() < .025:
                disc, reason = float(rng.choice([.05, .08, .10])), "Price match"
            elif rng.random() < .09 * (1.2 if consult else 1.0):
                disc, reason = float(rng.choice([.03, .05, .07, .10])), "Manager discretionary"
            line_id = ids("LN", 7)
            gross = round(price * qty, 2)
            net = round(gross * (1 - disc), 2)
            unit_cost = round(stock_cost[p] * (1 + uplift * 0.9), 2)
            ln = {"line_id": line_id, "order_id": oid, "transaction_date": d, "customer_id": cid, "product_id": p, "units": int(qty), "list_unit_price_cad": prod.list_price_cad,
                  "unit_price_cad": price, "discount_pct": disc, "discount_reason": reason, "gross_sales_cad": gross, "net_sales_cad": net, "unit_cost_cad": unit_cost,
                  "material_variant": material, "configuration": config, "fulfillment_type": "Custom (made to order)" if custom else "Stocked (ready-made)",
                  "supply": None, "sales_channel": channel, "employee_id": rep, "promotion_id": promo["promotion_id"] if reason == "Promotion" else None,
                  "consultation_id": consult["consultation_id"] if consult else None, "status": "Open", "ready": False, "returned_units": 0}
            if custom and on_hand[p] - reserved[p] >= qty and rng.random() < 0.6:          # floor model / cancelled custom piece in stock
                ln["supply"] = "From stock"
                ln["discount_pct"], ln["discount_reason"] = 0.30, "Floor model / clearance"
                ln["net_sales_cad"] = round(gross * 0.70, 2)
                ln["unit_cost_cad"] = stock_cost[p]
                ln["unit_price_cad"], ln["material_variant"], ln["configuration"] = prod.list_price_cad, "Floor model", "As displayed"
                ln["gross_sales_cad"] = gross = round(prod.list_price_cad * qty, 2)
                ln["net_sales_cad"] = round(gross * 0.70, 2)
            elif custom:
                ln["supply"] = "Custom PO"
                any_custom = True
            elif on_hand[p] - reserved[p] >= qty:
                ln["supply"] = "From stock"
            elif rng.random() < 0.72:
                ln["supply"] = "Special order (backorder)"
                any_special = True
            else:
                stockouts.append({"stockout_id": ids("SO", 6), "event_date": d, "product_id": p, "lost_units": int(qty), "lost_revenue_est_cad": net})
                continue
            if ln["supply"] == "From stock":
                reserved[p] += qty
            o_lines.append(ln)
        if not o_lines:
            return None
        net_total = round(sum(l["net_sales_cad"] for l in o_lines), 2)
        small = net_total < 900 and not any_custom and not any_special
        same_day = small and channel != "Online store" and rng.random() < 0.55
        trade = ctype in TRADE and ctype != "Real-estate stager" and rng.random() < .7
        financed = (not trade) and net_total > 1500 and rng.random() < 0.20
        tender = "Financing partner" if financed else ("Trade account" if trade else rng.choice(["Credit card", "Debit", "E-transfer", "Cash"], p=[.56, .27, .13, .04]))
        dep_rate = 1.0 if same_day else (TRADE_DEPOSIT if trade else DEPOSIT)
        gross_incl = round(net_total * (1 + GST), 2)
        # promise = date the order will be READY for pickup/delivery (customer then books the hand-off)
        promise_days = (max([lt[l["product_id"]] for l in o_lines if l["supply"] != "From stock"], default=0) + 5) if (any_custom or any_special) else (0 if same_day else 3)
        method = "Customer pickup" if same_day else rng.choice(["Customer pickup", "Third-party delivery (customer-paid)", "Retailer-arranged flat-rate delivery"],
                                                              p=[.44, .44, .12] if channel == "Online store" and net_total > 999 else [.50, .50, 0.0])
        plan = round(max(PLAN_MIN, PLAN_RATE * net_total), 2) if (net_total > 1000 and rng.random() < 0.17 and room != "Décor & lighting only") else 0.0
        orders[oid] = {"order_id": oid, "customer_id": cid, "order_date": d, "sales_channel": channel, "employee_id": rep, "room_type": room,
                       "consultation_id": consult["consultation_id"] if consult else None, "order_type": "Custom" if any_custom else ("Special order" if any_special else "In stock"),
                       "net_order_value_cad": net_total, "gst_cad": round(gross_incl - net_total, 2), "deposit_rate": dep_rate, "tender": tender, "financed": financed, "trade_account": trade,
                       "promised_fulfillment_date": d + pd.Timedelta(days=promise_days), "fulfillment_method": method, "protection_plan_cad": plan,
                       "agent_delivery_fee_cad": FLAT_DELIVERY if method == "Retailer-arranged flat-rate delivery" else 0.0, "promotion_id": promo["promotion_id"] if promo else None,
                       "status": "Open", "ready_date": None, "scheduled_date": None, "fulfilled_date": None, "cancel_date": None, "cancel_reason": None,
                       "paid_incl_gst": 0.0, "refund_incl_gst": 0.0, "retained_fee_cad": 0.0, "lines": [l["line_id"] for l in o_lines], "same_day": same_day}
        lines.extend(o_lines)
        line_ix.update({l["line_id"]: l for l in o_lines})
        open_orders[oid] = True
        # deposit
        dep = round(gross_incl * dep_rate, 2)
        if not trade or dep_rate < 1:
            pay(d, oid, "Deposit" if dep_rate < 1 else "Payment in full", dep, tender)
            orders[oid]["paid_incl_gst"] += dep
        # supply actions
        for l in o_lines:
            p, q = l["product_id"], l["units"]
            if l["supply"] == "From stock":
                on_hand[p] -= q
                allocated[p] += q
                move(d, p, "ALLOCATE", "stock", -q, l["line_id"], stock_cost[p])
                move(d, p, "ALLOCATE", "allocated", q, l["line_id"], stock_cost[p])
                l["ready"] = True
            else:
                place_po(d, "Custom" if l["supply"] == "Custom PO" else "Special order", p, q, l["line_id"], unit_cost=l["unit_cost_cad"] if l["supply"] == "Custom PO" else None)
        if same_day:
            fulfil_order(oid, d)
        else:
            check_ready(oid, d)
        past_customers.append(cid)
        return oid

    line_ix = {}

    def check_ready(oid, d):
        o = orders[oid]
        if o["ready_date"] is not None or o["status"] != "Open":
            return
        if all(line_ix[l]["ready"] for l in o["lines"]):
            ready = add_business_days(d, int(rng.integers(1, 3)), open_set) if not o["same_day"] else d
            o["ready_date"] = ready
            hold = rng.random() < 0.07
            lag = int(rng.integers(14, 46)) if hold else int(rng.choice([1, 2, 3, 4, 5, 7, 10], p=[.16, .2, .2, .14, .12, .1, .08]))
            want = next_open(ready + pd.Timedelta(days=lag), open_set)
            if o["fulfillment_method"] == "Customer pickup" and rng.random() < .35:
                while want.dayofweek != 5:
                    want = next_open(want + pd.Timedelta(days=1), open_set)            # Saturday preference
            o["requested_date"] = want
            o["storage_hold"] = hold
            date = want
            if o["fulfillment_method"] == "Customer pickup":
                while len([x for x in sched[date] if orders[x]["fulfillment_method"] == "Customer pickup"]) >= PICKUP_SLOTS:
                    date = next_open(date + pd.Timedelta(days=1), open_set)
            else:
                date = next_open(date + pd.Timedelta(days=int(rng.choice([0, 1, 2, 3, 5], p=[.35, .25, .2, .12, .08]))), open_set)
            o["scheduled_date"] = date
            o["carrier"] = None if o["fulfillment_method"] == "Customer pickup" else rng.choice(CARRIERS, p=[.5, .3, .2])
            sched[date].append(oid)

    def fulfil_order(oid, d):
        o = orders[oid]
        if o["status"] != "Open":
            return
        o["status"] = "Fulfilled"
        o["fulfilled_date"] = d
        if o["ready_date"] is None:
            o["ready_date"] = d
            o["requested_date"] = d
            o["scheduled_date"] = d
            o["storage_hold"] = False
            o["carrier"] = None
        open_orders.pop(oid, None)
        for l in o["lines"]:
            ln = line_ix[l]
            ln["status"] = "Fulfilled"
            p, q = ln["product_id"], ln["units"]
            allocated[p] -= q
            move(d, p, "FULFILL", "allocated", -q, l, ln["unit_cost_cad"] if ln["supply"] == "Custom PO" else stock_cost[p])
        gross_incl = round(o["net_order_value_cad"] * (1 + GST), 2)
        bal = round(gross_incl - o["paid_incl_gst"], 2)
        extras = o["protection_plan_cad"] + o["agent_delivery_fee_cad"]
        if o["trade_account"]:
            pay(d + pd.Timedelta(days=30), oid, "Trade account settlement (Net 30)", bal + extras, "Trade account")
        else:
            pay(d, oid, "Balance before pickup", bal + extras, o["tender"])
        o["paid_incl_gst"] += bal
        dmg = rng.random() < (0.025 if o["fulfillment_method"] != "Customer pickup" else 0.012)
        cost = 0.0
        if dmg:
            cost += float(rng.choice([65, 120, 180, 260]))
        if o.get("storage_hold") and (d - o["ready_date"]).days > 14:
            cost += 15.0 * ((d - o["ready_date"]).days - 14) / 7
        o["damage_flag"], o["retailer_fulfillment_cost_cad"] = dmg, round(cost, 2)
        o["carrier_fee_customer_paid_cad"] = round(float(rng.choice([129, 159, 189, 229, 289, 349])) * (1.5 if o["net_order_value_cad"] > 5000 else 1.0), 2) \
            if o["fulfillment_method"] == "Third-party delivery (customer-paid)" else 0.0
        # in-stock regular-priced returns within 3 days (15% restocking fee), not mattresses / bedding / discounted / custom
        for l in o["lines"]:
            ln = line_ix[l]
            prod = P.loc[ln["product_id"]]
            if ln["supply"] == "From stock" and ln["discount_pct"] == 0 and prod.category != "Mattresses & Bases" and prod.subcategory != "Textiles & poufs" and rng.random() < 0.035:
                returns_due[d + pd.Timedelta(days=int(rng.integers(1, 4)))].append(l)

    def cancel_order(oid, d, reason):
        o = orders[oid]
        o["status"] = "Cancelled"
        o["cancel_date"], o["cancel_reason"] = d, reason
        open_orders.pop(oid, None)
        custom_started = o["order_type"] == "Custom" and (d - o["order_date"]).days > 3
        fee = round(0.25 * o["net_order_value_cad"], 2) if custom_started and reason != "Supplier delay - goodwill full refund" else 0.0
        fee = min(fee, round(o["paid_incl_gst"] / (1 + GST), 2))
        refund = round(o["paid_incl_gst"] - fee * (1 + GST), 2)
        o["retained_fee_cad"] = fee
        o["refund_incl_gst"] = refund
        if refund > 0:
            pay(d, oid, "Refund on cancellation", -refund, o["tender"])
        for l in o["lines"]:
            ln = line_ix[l]
            ln["status"] = "Cancelled"
            p, q = ln["product_id"], ln["units"]
            if ln["ready"]:
                allocated[p] -= q
                uc = ln["unit_cost_cad"] if ln["supply"] == "Custom PO" else stock_cost[p]
                move(d, p, "CANCEL_RELEASE", "allocated", -q, l, uc)
                on_hand[p] += q
                move(d, p, "CANCEL_RELEASE", "stock", q, l, stock_cost[p])
                # stock is carried at standard cost; a cancelled custom piece re-enters stock at standard cost as a floor model
                # (the cost difference is posted to inventory variances by the ledger) and is flagged for clearance
                if ln["supply"] == "Custom PO":
                    clearance_age.setdefault(p, d - pd.Timedelta(days=170))
            else:
                for po in (pos[x] for x in po_by_line.get(l, [])):
                    if po["status"] == "Open":
                        po["status"] = "Cancelled"
                        po["cancel_date"] = d
                        po["supplier_cancellation_fee_cad"] = round(0.20 * po["qty_ordered"] * po["unit_cost_cad"], 2) if (d - po["order_date"]).days > 5 else 0.0

    po_by_line = defaultdict(list)

    # ---------------------------------------------------------------- day loop
    t0 = pd.Timestamp(WARMUP)
    for d in days:
        is_open = d in open_set
        # 1. receipts
        for po_id in receipts_due.pop(d, []):
            po = pos[po_id]
            if po["status"] != "Open":
                continue
            p, q = po["product_id"], po["qty_ordered"]
            if po["po_type"] == "Stock replenishment":
                dmg = int(rng.binomial(q, 0.012))
                po["qty_received"], po["qty_damaged"], po["status"] = q - dmg, dmg, "Received"
                on_order[p] -= q
                if q - dmg:
                    on_hand[p] += q - dmg
                    move(d, p, "PO_RECEIPT", "stock", q - dmg, po_id, po["unit_cost_cad"])
            else:
                ln = line_ix[po["order_line_id"]]
                if rng.random() < 0.03 and po["replacement_of"] is None:          # damaged on arrival -> supplier replacement
                    po["qty_received"], po["qty_damaged"], po["status"] = 0, q, "Damaged - replaced"
                    new = place_po(d, po["po_type"], p, q, ln["line_id"], unit_cost=po["unit_cost_cad"], lead_extra=-int(LEAD[P.at[p, "supplier_class"]][0] * 0.5))
                    pos[new]["replacement_of"] = po_id
                    pos[new]["delay_reason"] = "Damaged on arrival - replacement"
                    continue
                po["qty_received"], po["status"] = q, "Received"
                allocated[p] += q
                move(d, p, "CUSTOMER_GOODS_RECEIPT", "allocated", q, po_id, po["unit_cost_cad"])
                ln["ready"] = True
                ln["received_date"] = d
                check_ready(ln["order_id"], d)
        if d > pd.Timestamp(END):
            break
        # 2. fulfilments scheduled today
        for oid in sched.pop(d, []):
            if orders[oid]["status"] == "Open":
                fulfil_order(oid, d)
        # 3. returns
        for l in returns_due.pop(d, []):
            ln = line_ix[l]
            if ln["status"] != "Fulfilled":
                continue
            p, q = ln["product_id"], ln["units"]
            ln["status"], ln["returned_units"] = "Returned", q
            restock = rng.random() < 0.88
            returns.append({"return_id": ids("RET", 5), "line_id": l, "order_id": ln["order_id"], "return_date": d, "units": q, "net_sales_returned_cad": ln["net_sales_cad"],
                            "restocking_fee_cad": round(0.15 * ln["net_sales_cad"], 2), "refund_incl_gst_cad": round(0.85 * ln["net_sales_cad"] * (1 + GST), 2),
                            "restocked": restock, "reason": rng.choice(["Changed mind", "Did not fit space", "Colour / finish not as expected", "Comfort"], p=[.35, .3, .2, .15])})
            pay(d, ln["order_id"], "Refund on return", -round(0.85 * ln["net_sales_cad"] * (1 + GST), 2), orders[ln["order_id"]]["tender"])
            on_hand[p] += q
            move(d, p, "CUSTOMER_RETURN", "stock", q, returns[-1]["return_id"], stock_cost[p])
            if not restock:
                on_hand[p] -= q
                move(d, p, "WRITE_OFF_DAMAGED", "stock", -q, returns[-1]["return_id"], stock_cost[p])
        # 4. cancellations (hazard rises with supplier delay)
        for oid in list(open_orders):
            o = orders[oid]
            if o["order_date"] == d:
                continue
            late = (d - o["promised_fulfillment_date"]).days
            if o["order_type"] == "Custom":
                hz = 0.00025 + (0.0035 * min(late, 60) / 30 if late > 0 else 0)
            elif o["order_type"] == "Special order":
                hz = 0.0006 + (0.004 * min(late, 60) / 30 if late > 0 else 0)
            else:
                hz = 0.0012
            if rng.random() < hz:
                reason = ("Supplier delay - goodwill full refund" if late > 28 and rng.random() < .5 else "Supplier delay - customer cancelled") if late > 0 \
                    else rng.choice(["Changed mind", "Found alternative", "Moving plans changed"])
                cancel_order(oid, d, reason)
        if not is_open:
            continue
        season = MONTH_SEASON[d.month]
        trend = {2023: 0.96, 2024: 1.0, 2025: 1.06, 2026: 1.09}[d.year] * float(np.exp(-0.035 * (econ.get(d.to_period("M").to_timestamp(), 3.0) - 3.5)))
        promo = promo_on(d)
        pm = promo["mult"] if promo else 1.0
        reps = reps_on(d)
        rep_w = np.array([r[3] for r in reps])
        # 5. design consultations today + conversions
        for _ in range(rng.poisson(BASE_CONSULTS * season ** 0.6 * DOW[d.dayofweek] * trend)):
            ctype_name, _, type_eff, hours = CONSULT_TYPES[rng.choice(3, p=[c[1] for c in CONSULT_TYPES])]
            designer = rng.choice(list(DESIGNERS))
            repeat = rng.random() < .10 and len(past_customers) > 200
            cid = past_customers[int(rng.integers(len(past_customers)))] if repeat else new_customer(d, channel=rng.choice(ACQ[0], p=ACQ[1]))
            ctype = customers[cid]["customer_type"]
            quote = round(float(np.exp(rng.normal(np.log(6200 if ctype not in TRADE else 9800), 0.55))), -1)
            follow = int(rng.choice([0, 1, 2, 3, 4], p=[.12, .30, .30, .18, .10]))
            first_fu = int(rng.integers(1, 8)) if follow else None
            z = (-0.62 + type_eff + 0.55 * math.log(DESIGNERS[designer]) * 3 + (0.5 if ctype in TRADE else 0) + 0.35 * repeat - 0.45 * (math.log(quote) - math.log(6200))
                 + 0.38 * follow - (0.25 if follow == 0 else 0) + 0.15 * (d.month in (1, 9, 10, 11)) - 0.004 * (first_fu or 10) * 10)
            conv = rng.random() < 1 / (1 + math.exp(-z))
            cons = {"consultation_id": ids("DC", 6), "consultation_date": d, "customer_id": cid, "designer_id": designer, "consultation_type": ctype_name,
                    "rooms_in_scope": int(rng.choice([1, 2, 3, 4], p=[.42, .33, .17, .08])), "quotation_amount_cad": quote, "follow_up_count": follow,
                    "first_follow_up_days": first_fu, "designer_hours": round(hours * float(rng.uniform(.8, 1.3)), 2), "converted": conv, "repeat_customer": repeat}
            cons["estimated_conversion_cost_cad"] = round(cons["designer_hours"] * 46 + 25 + (75 if "In-home" in ctype_name else 0) + 18 * follow, 2)
            cons["recommended_categories"] = ", ".join(sorted(set(rng.choice(["Sofas & Sectionals", "Bedroom", "Dining", "Living & Occasional", "Décor & Lighting", "Mattresses & Bases"],
                                                                              size=cons["rooms_in_scope"] + 1, p=[.3, .17, .17, .18, .14, .04]))))
            consults.append(cons)
            if conv:
                cdate = next_open(d + pd.Timedelta(days=int(rng.gamma(2.0, 7.0)) + (first_fu or 0)), open_set)
                pending_conv[cdate].append(cons)
        for cons in pending_conv.pop(d, []):
            rep = cons["designer_id"]
            oid = create_order(d, "Design consultation", cons["customer_id"], rep, consult=cons, target_value=cons["quotation_amount_cad"] * float(rng.uniform(.75, 1.1)))
            cons["order_id"] = oid
            cons["conversion_date"] = d if oid else None
        # 6. regular orders
        for _ in range(rng.poisson(BASE_ORDERS * season * DOW[d.dayofweek] * trend * pm)):
            ch = rng.choice(["In-store showroom", "Online store", "Phone / email", "Trade account"], p=[.64, .22, .08, .06])
            repeat = rng.random() < (.09 if ch != "Trade account" else .45) and len(past_customers) > 200
            if repeat:
                k = int(len(past_customers) * (1 - rng.random() ** 1.8))
                cid = past_customers[min(k, len(past_customers) - 1)]
            else:
                ctype = rng.choice(["Interior designer (trade)", "Business / hospitality", "Real-estate stager"]) if ch == "Trade account" else None
                cid = new_customer(d, ctype, "Online store" if ch == "Online store" and rng.random() < .5 else None)
                if rng.random() < 0.85:
                    leads.append({"lead_date": d - pd.Timedelta(days=int(rng.gamma(1.5, 6))), "lead_channel": customers[cid]["acquisition_channel"], "customer_id": cid,
                                  "converted": True, "conversion_date": d})
            rep = None if ch == "Online store" else reps[rng.choice(len(reps), p=rep_w / rep_w.sum())][0]
            create_order(d, ch, cid, rep)
        # 7. weekly replenishment (Mondays) + pre-season buys (late Feb, early Aug)
        if d.dayofweek == 0:
            for p in stocked:
                pos_ = on_hand[p] + on_order[p]
                if pos_ <= rop[p]:
                    place_po(d, "Stock replenishment", p, max(1, upto[p] - pos_))
            if (d.month == 2 and 18 <= d.day <= 24) or (d.month == 8 and 1 <= d.day <= 7):
                for p in stocked:
                    if p not in slow and rng.random() < .5:
                        place_po(d, "Stock replenishment", p, max(1, int(rate[p] * 30)))
        # 8. quarterly policy refresh from trailing sales (current practice: flat, non-seasonal)
        if d.day == 1 and d.month in (1, 4, 7, 10) and d > t0 + pd.Timedelta(days=90):
            recent = defaultdict(int)
            for ln in lines[-4000:]:
                if ln["transaction_date"] >= d - pd.Timedelta(days=90) and ln["supply"] == "From stock":
                    recent[ln["product_id"]] += ln["units"]
            for p in stocked:
                dr = max(recent[p] / 90, 0.003)
                rop[p] = max(1, int(math.ceil(dr * lt[p] * 1.15)))
                upto[p] = rop[p] + max(2, int(math.ceil(dr * 42)))
        # 9. month end: cycle counts + aged-stock flags
        if (d + pd.Timedelta(days=1)).day == 1:
            for p in stocked:
                if on_hand[p] > 0 and rng.random() < 0.03:
                    on_hand[p] -= 1
                    move(d, p, "CYCLE_COUNT_ADJ", "stock", -1, f"CC-{d:%Y%m}", stock_cost[p])
                if on_hand[p] > upto[p] * 1.5:
                    clearance_age.setdefault(p, d)
                elif on_hand[p] <= upto[p]:
                    clearance_age.pop(p, None)
    return dict(P=P, suppliers=suppliers, customers=customers, orders=orders, lines=lines, pos=pos, payments=payments, consults=consults, returns=returns,
                stockouts=stockouts, leads=leads, moves=moves, staff_sales=staff_sales, rop=rop, upto=upto, rng=rng, open_set=open_set, slow=slow)


# ---------------------------------------------------------------------------------------------- assemble & write
def opex_and_marketing(sim, orders_df, lines_df, pay_df, cons_df, days_open, rng):
    months = pd.period_range(START, END, freq="M")
    rows, mrows = [], []
    lm = lines_df.assign(m=lines_df.transaction_date.dt.to_period("M"))
    written = lm[lm.line_status != "Cancelled"].groupby("m").net_sales_cad.sum().reindex(months, fill_value=0.0)
    by_rep = lm[lm.line_status != "Cancelled"].groupby(["m", "employee_id"]).net_sales_cad.sum()
    fo = orders_df.dropna(subset=["fulfilled_date"]).assign(m=lambda x: x.fulfilled_date.dt.to_period("M"))
    ful_cost = fo.groupby("m").retailer_fulfillment_cost_cad.sum().reindex(months, fill_value=0.0)
    cons_m = cons_df.assign(m=cons_df.consultation_date.dt.to_period("M"))
    cons_direct = cons_m.groupby("m").apply(lambda g: (25 * len(g) + 75 * g.consultation_type.str.contains("In-home").sum()), include_groups=False).reindex(months, fill_value=0.0)
    pm = pay_df.assign(m=pay_df.payment_date.dt.to_period("M"))
    card = pm[pm.tender.isin(["Credit card", "Debit"]) & (pm.amount_incl_gst > 0)].groupby("m").amount_incl_gst.sum().reindex(months, fill_value=0.0)
    for m in months:
        yr = m.year - 2024
        n_open = days_open.get(m, 26)
        hrs = n_open * 8.0
        reps = [s for s in sim["staff_sales"] if pd.Timestamp(s[1]) <= m.end_time and (s[2] is None or pd.Timestamp(s[2]) >= m.start_time)]
        sales_wages = sum(20.0 * hrs * (0.8 if i > 5 else 1.0) for i, _ in enumerate(reps)) * (1.03 ** yr)
        commission = 0.03 * sum(by_rep.get((m, r[0]), 0.0) for r in reps)
        designer = 4 * 4850 * (1.03 ** yr) + 0.02 * float(lm[(lm.m == m) & lm.consultation_id.notna() & (lm.line_status != "Cancelled")].net_sales_cad.sum())
        warehouse = 4 * 21.0 * hrs * (1.03 ** yr)
        mgmt_admin = (2 * 7400 + 1.5 * 4800 + 8500) * (1.03 ** yr)
        burden = 1.13
        season = MONTH_SEASON[m.month]
        mk_total = round(0.052 * float(written[m - 1] if m > months[0] else written[m]) * (0.85 + 0.3 * (season > 1)) * float(rng.uniform(0.93, 1.07)), 2)
        split = {"Google search ads": .33, "Meta / Instagram ads": .25, "Contests & community giveaways": .12, "Flyers, radio & print": .12,
                 "Website, SEO & e-commerce": .09, "Review & marketplace listings": .09}
        for ch, sh in split.items():
            mrows.append({"month": m.start_time, "marketing_channel": ch, "spend_cad": round(mk_total * sh, 2), "data_status": "SYNTHETIC"})
        rows.append({
            "month": m.start_time,
            "sales_wages_cad": round(sales_wages * burden, 2), "sales_commission_cad": round(commission, 2), "designer_compensation_cad": round(designer * burden, 2),
            "warehouse_wages_cad": round(warehouse * burden, 2), "management_admin_salaries_cad": round(mgmt_admin * burden, 2),
            "rent_cad": round(44000 * (1.03 ** yr), 2), "cam_property_tax_cad": round(9800 * (1.025 ** yr), 2),
            "utilities_cad": round(5400 + 5800 * max(0.0, (6 - abs(m.month - 1 if m.month <= 6 else 13 - m.month)) / 6) + rng.normal(0, 250), 2),
            "marketing_cad": mk_total, "insurance_cad": round(5200 * (1.04 ** yr), 2), "admin_professional_cad": round(7800 + rng.normal(0, 400), 2),
            "it_ecommerce_cad": round(3400 * (1.03 ** yr) + rng.normal(0, 150), 2), "warehouse_operations_cad": round(3200 + float(ful_cost[m]) + rng.normal(0, 200), 2),
            "design_consult_materials_travel_cad": round(float(cons_direct[m]), 2), "card_processing_fees_cad": round(0.0175 * float(card[m]), 2),
        })
    o = pd.DataFrame(rows)
    o["total_opex_cad"] = o.drop(columns="month").sum(axis=1).round(2)
    o["data_status"] = "SYNTHETIC (assumption-driven)"
    return o, pd.DataFrame(mrows)


def assemble(sim):
    rng = sim["rng"]
    s0, s1 = pd.Timestamp(START), pd.Timestamp(END)
    orders = pd.DataFrame([{k: v for k, v in o.items() if k != "lines"} for o in sim["orders"].values()])
    keep = (orders.order_date >= s0) | ((orders.fulfilled_date.isna() | (orders.fulfilled_date >= s0)) & (orders.cancel_date.isna() | (orders.cancel_date >= s0)))
    orders = orders[keep].copy()
    orders["opening_backlog"] = orders.order_date < s0
    kept = set(orders.order_id)
    L = pd.DataFrame(sim["lines"])
    L = L[L.order_id.isin(kept)].copy()
    pay = pd.DataFrame(sim["payments"])
    pay = pay[pay.order_id.isin(kept) & (pay.payment_date <= s1)].copy()
    pay["pre_period"] = pay.payment_date < s0
    po = pd.DataFrame(sim["pos"].values())
    po_keep = po.order_line_id.isin(set(L.line_id)) | (po.received_date >= s0 - pd.Timedelta(days=45)) | (po.status == "Open")   # Dec-2023 receipts support opening AP
    po = po[po_keep & ~((po.status == "Cancelled") & (po.get("cancel_date", pd.NaT) < s0))].copy()
    po = po[po.order_line_id.isna() | po.order_line_id.isin(set(L.line_id))].copy()
    po.loc[~po.replacement_of.isin(set(po.po_id)), "replacement_of"] = None
    po.loc[po.received_date > s1, ["received_date"]] = pd.NaT
    po.loc[(po.status == "Received") & po.received_date.isna(), "status"] = "Open"
    po["pre_period"] = po.order_date < s0
    # inventory: opening snapshot at START + movements from START
    mv = pd.DataFrame(sim["moves"], columns=["movement_date", "product_id", "movement_type", "inventory_state", "quantity", "unit_cost_cad", "reference_id"])
    mv["value_cad"] = (mv.quantity * mv.unit_cost_cad).round(2)
    pre = mv[mv.movement_date < s0].groupby(["product_id", "inventory_state"]).agg(quantity=("quantity", "sum"), value_cad=("value_cad", "sum")).reset_index()
    pre = pre[(pre.quantity != 0) | (pre.value_cad.abs() > 0.005)]
    pre["unit_cost_cad"] = (pre.value_cad / pre.quantity.replace(0, np.nan)).round(4)
    pre["movement_date"], pre["movement_type"], pre["reference_id"] = s0, "OPENING_BALANCE", "OPENING-2024-01-01"
    mv = pd.concat([pre, mv[(mv.movement_date >= s0) & (mv.movement_date <= s1)]], ignore_index=True)
    mv.insert(0, "movement_id", [f"MV-{i + 1:07d}" for i in range(len(mv))])
    # orders: status at END
    orders.loc[orders.status == "Open", "status"] = np.where(orders.loc[orders.status == "Open", "ready_date"].notna() & (orders.loc[orders.status == "Open", "ready_date"] <= s1),
                                                             "Ready - awaiting pickup/delivery", "Awaiting supplier")
    for c in ["ready_date", "requested_date", "scheduled_date"]:
        orders.loc[orders[c] > s1, c] = pd.NaT
    lines_status = L.set_index("line_id").status
    L.loc[(L.status == "Open") & L.ready, "status"] = "Allocated - awaiting pickup/delivery"
    L.loc[L.status == "Open", "status"] = "Awaiting supplier"
    P = sim["P"]
    L["category"] = L.product_id.map(P.category)
    L["subcategory"] = L.product_id.map(P.subcategory)
    L["manufacturer"] = L.product_id.map(P.manufacturer)
    L["cogs_cad"] = (L.unit_cost_cad * L.units).round(2)
    L["gross_profit_cad"] = (L.net_sales_cad - L.cogs_cad).round(2)
    L["gross_margin_pct"] = (L.gross_profit_cad / L.net_sales_cad * 100).round(2)
    L["opening_backlog"] = L.order_id.map(orders.set_index("order_id").opening_backlog)
    L = L.drop(columns=["ready"]).rename(columns={"supply": "supply_source", "status": "line_status"})
    L["fulfilled_date"] = L.order_id.map(orders.set_index("order_id").fulfilled_date)
    L.loc[L.line_status.isin(["Cancelled", "Awaiting supplier", "Allocated - awaiting pickup/delivery"]), "fulfilled_date"] = pd.NaT
    # payments summary on orders
    ps = pay.groupby("order_id").amount_incl_gst.sum()
    orders["total_paid_incl_gst_cad"] = orders.order_id.map(ps).fillna(0).round(2)
    orders["order_total_incl_gst_cad"] = (orders.net_order_value_cad + orders.gst_cad).round(2)
    orders["deposit_required_cad"] = (orders.order_total_incl_gst_cad * orders.deposit_rate).round(2)
    dep = pay[pay.payment_type.isin(["Deposit", "Payment in full"])].groupby("order_id").amount_incl_gst.sum()
    orders["deposit_paid_cad"] = orders.order_id.map(dep).fillna(0).round(2)
    extras = orders.protection_plan_cad + orders.agent_delivery_fee_cad
    orders["balance_outstanding_cad"] = np.where(orders.status.isin(["Fulfilled", "Cancelled"]), 0.0, (orders.order_total_incl_gst_cad - orders.total_paid_incl_gst_cad).round(2))
    orders.loc[orders.status == "Fulfilled", "balance_outstanding_cad"] = (orders.order_total_incl_gst_cad + extras - orders.total_paid_incl_gst_cad).clip(lower=0).round(2)[orders.status == "Fulfilled"]
    orders = orders.rename(columns={"promised_fulfillment_date": "promised_ready_date"})
    orders["fulfillment_days"] = (orders.fulfilled_date - orders.order_date).dt.days
    orders["ready_delay_days"] = (orders.ready_date - orders.promised_ready_date).dt.days
    orders["handoff_wait_days"] = (orders.fulfilled_date - orders.ready_date).dt.days
    # fulfilment records (G)
    f = orders[orders.status != "Cancelled"].copy()
    f["fulfillment_id"] = ["FUL-" + x[4:] for x in f.order_id]
    supplier_late = po[po.order_line_id.notna()].assign(oid=lambda x: x.order_line_id.map(L.set_index("line_id").order_id)).groupby("oid").delay_days.max()
    dmg_repl = po[po.status == "Damaged - replaced"].assign(oid=lambda x: x.order_line_id.map(L.set_index("line_id").order_id)).oid.unique()
    f["supplier_delay_days"] = f.order_id.map(supplier_late).fillna(0).clip(lower=0)
    f["pickup_capacity_wait_days"] = np.where(f.fulfillment_method == "Customer pickup", (f.scheduled_date - f.requested_date).dt.days.fillna(0), 0)
    f["warehouse_prep_days"] = np.where(f.same_day, 0, (f.ready_date - f.order_date).dt.days)
    def ready_cat(r):
        if pd.isna(r.ready_date):
            return "Open - awaiting supplier"
        if r.ready_delay_days <= 0:
            return "Ready on time"
        if r.order_id in dmg_repl:
            return "Damaged on arrival - supplier replacement"
        if r.supplier_delay_days > 2:
            return "Supplier delay"
        return "Warehouse preparation"

    def wait_cat(r):
        if pd.isna(r.fulfilled_date):
            return "Not yet handed off"
        if r.handoff_wait_days <= 0:
            return "Same day"
        if r.storage_hold:
            return "Customer requested storage"
        if r.pickup_capacity_wait_days > 0:
            return "Pickup slot capacity"
        if r.fulfillment_method != "Customer pickup":
            return "Carrier scheduling"
        return "Customer scheduling"
    f["delay_category"] = [ready_cat(r) for r in f.itertuples()]
    f["handoff_wait_reason"] = [wait_cat(r) for r in f.itertuples()]
    f["return_flag"] = f.order_id.isin({x["order_id"] for x in sim["returns"]})
    fulfil = f[["fulfillment_id", "order_id", "order_type", "fulfillment_method", "carrier", "promised_ready_date", "ready_date", "requested_date", "scheduled_date",
                "fulfilled_date", "status", "warehouse_prep_days", "supplier_delay_days", "ready_delay_days", "delay_category", "pickup_capacity_wait_days",
                "handoff_wait_days", "handoff_wait_reason", "fulfillment_days", "storage_hold", "damage_flag", "return_flag", "retailer_fulfillment_cost_cad", "carrier_fee_customer_paid_cad", "agent_delivery_fee_cad"]].copy()
    fulfil["carrier_fee_note"] = np.where(fulfil.fulfillment_method == "Third-party delivery (customer-paid)", "Paid by customer directly to carrier - not retailer revenue",
                                          np.where(fulfil.fulfillment_method == "Retailer-arranged flat-rate delivery", "Collected as agent and remitted to carrier - not retailer revenue", ""))
    # consultations, leads, customers
    C = pd.DataFrame(sim["consults"])
    C["order_id"] = C.get("order_id")
    C = C[((C.consultation_date >= s0) & (C.consultation_date <= s1)) | C.order_id.isin(kept)].copy()
    C["pre_period"] = C.consultation_date < s0
    C["conversion_status"] = np.where(C.order_id.notna(), "Converted", np.where(C.converted & C.order_id.isna(), "Open - follow-up in progress",
                                      np.where((s1 - C.consultation_date).dt.days < 45, "Open - follow-up in progress", "Not converted")))
    C["converted"] = C.order_id.notna()
    kept_c = set(C.consultation_id)                       # backlog orders from warm-up consultations lose the (out-of-period) link
    orders.loc[~orders.consultation_id.isin(kept_c), "consultation_id"] = None
    L.loc[~L.consultation_id.isin(kept_c), "consultation_id"] = None
    rev = L[L.line_status != "Cancelled"].groupby("order_id").net_sales_cad.sum()
    C["final_sales_revenue_cad"] = C.order_id.map(rev).fillna(0).round(2)
    C["conversion_date"] = C.order_id.map(orders.set_index("order_id").order_date)
    C["days_to_convert"] = (C.conversion_date - C.consultation_date).dt.days
    leads = pd.DataFrame(sim["leads"])
    leads = leads[(leads.conversion_date >= s0) & leads.customer_id.isin(set(orders.customer_id))]
    non = []
    for ch, g in leads.groupby("lead_channel"):
        r = LEAD_CONV[ch]
        n = int(rng.poisson(len(g) * (1 - r) / r))
        for dd in g.lead_date.sample(n, replace=True, random_state=int(rng.integers(1e9))).values:
            dd = pd.Timestamp(dd) + pd.Timedelta(days=int(rng.integers(-20, 21)))
            non.append({"lead_date": min(max(dd, s0), s1), "lead_channel": ch, "customer_id": None, "converted": False, "conversion_date": pd.NaT})
    leads = pd.concat([leads, pd.DataFrame(non)], ignore_index=True).sort_values("lead_date").reset_index(drop=True)
    leads["lead_date"] = leads.lead_date.clip(lower=s0)
    leads.insert(0, "lead_id", [f"LEAD-{i + 1:06d}" for i in range(len(leads))])
    age = (s1 - leads.lead_date).dt.days
    leads["lead_status"] = np.where(leads.converted, "Won", np.where(age < 30, "Open", "Lost"))
    leads["lead_source_detail"] = leads.lead_channel.map({"Google search": "Search ad / organic", "Social media & contests": "Contest entry / social DM", "Showroom walk-in": "Showroom visit",
                                                          "Referral / word of mouth": "Referral", "Online store": "Cart / chat inquiry", "Review sites": "Review profile",
                                                          "Real-estate partner": "Partner referral"})
    used = set(orders.customer_id) | set(C.customer_id) | set(leads.customer_id.dropna())
    cust = pd.DataFrame(sim["customers"].values())
    cust = cust[cust.customer_id.isin(used)].copy()
    valid = L[~L.line_status.isin(["Cancelled"])]
    agg = valid.groupby("customer_id").agg(first_order_date=("transaction_date", "min"), last_order_date=("transaction_date", "max"), orders=("order_id", "nunique"),
                                           lifetime_net_sales_cad=("net_sales_cad", "sum"), lifetime_gross_profit_cad=("gross_profit_cad", "sum"))
    cust = cust.set_index("customer_id").join(agg)
    cust["orders"] = cust.orders.fillna(0).astype(int)
    cust["repeat_customer"] = cust.orders >= 2
    cust["consultations"] = C.groupby("customer_id").size().reindex(cust.index).fillna(0).astype(int)
    camp = {"Google search": "CMP-SEARCH", "Social media & contests": "CMP-SOCIAL", "Online store": "CMP-SEARCH", "Review sites": "CMP-REVIEW", "Real-estate partner": "CMP-PARTNER"}
    cust["campaign_id"] = cust.acquisition_channel.map(camp)
    cust["lead_conversion_status"] = np.where(cust.orders > 0, "Converted", "Not converted")
    cust = cust.reset_index()
    cust["data_status"] = "SYNTHETIC (fictional, privacy-safe)"
    returns = pd.DataFrame(sim["returns"])
    returns = returns[returns.order_id.isin(kept) & (returns.return_date >= s0)]
    so = pd.DataFrame(sim["stockouts"])
    so = so[(so.event_date >= s0) & (so.event_date <= s1)]
    days_all = pd.date_range(START, END)
    cal = pd.DataFrame({"date": days_all, "store_open": [d in sim["open_set"] for d in days_all]})
    days_open = cal.assign(m=cal.date.dt.to_period("M")).groupby("m").store_open.sum()
    opex, mkt = opex_and_marketing(sim, orders, L, pay, C, days_open, rng)
    staff = pd.DataFrame([{"employee_id": e, "role": "Sales associate", "start_date": s, "end_date": t, "data_status": "SYNTHETIC"} for e, s, t, _ in sim["staff_sales"]]
                         + [{"employee_id": k, "role": "Interior designer", "start_date": "2021-01-01", "end_date": None, "data_status": "SYNTHETIC"} for k in DESIGNERS])
    promos = []
    for y in (2023, 2024, 2025, 2026):
        for name, s, e, disc, mult, scope in PROMOS:
            pid = f"PRM-{y}-{name.split()[0][:4].upper()}{s[:2]}"
            promos.append({"promotion_id": pid, "promotion_name": name, "start_date": f"{y}-{s}", "end_date": f"{y}-{e}", "extra_discount_pct": disc, "scope": scope,
                           "data_status": "SYNTHETIC"})
    promos = pd.DataFrame(promos)
    campaigns = pd.DataFrame([("CMP-SEARCH", "Always-on search & shopping ads", "Google search ads"), ("CMP-SOCIAL", "Social ads & weekly furniture giveaways", "Meta / Instagram ads"),
                              ("CMP-REVIEW", "Review & marketplace profile", "Review & marketplace listings"), ("CMP-PARTNER", "Real-estate & stager partnership", "Contests & community giveaways")],
                             columns=["campaign_id", "campaign_name", "spend_channel"]).assign(data_status="SYNTHETIC")
    prod = P.reset_index().copy()
    prod["supplier_id"] = prod.manufacturer.map(dict(zip(sim["suppliers"].supplier_name, sim["suppliers"].supplier_id)))
    prod["reorder_point_current_policy"] = prod.product_id.map(sim["rop"])
    prod["order_up_to_current_policy"] = prod.product_id.map(sim["upto"])
    end_q = mv.groupby(["product_id", "inventory_state"]).quantity.sum().unstack(fill_value=0)
    prod["on_hand_stock_units"] = prod.product_id.map(end_q.get("stock", pd.Series(dtype=float))).fillna(0).astype(int)
    prod["allocated_to_customers_units"] = prod.product_id.map(end_q.get("allocated", pd.Series(dtype=float))).fillna(0).astype(int)
    prod["holding_cost_rate_annual"] = 0.22
    prod["data_status"] = prod.price_status
    prod = prod.drop(columns=["price_status", "popularity_prior"])
    orders = orders.drop(columns=["same_day", "paid_incl_gst", "refund_incl_gst"]).rename(columns={"retained_fee_cad": "retained_cancellation_fee_cad"})
    orders["data_status"] = "SYNTHETIC"
    for df in (L, pay, po, mv, fulfil, C, leads, returns, so):
        df["data_status"] = "SYNTHETIC"
    return dict(products=prod, suppliers=sim["suppliers"].assign(data_status="SYNTHETIC (lead times & terms simulated)"), customers=cust, leads=leads, staff=staff,
                promotions=promos, campaigns=campaigns, consultations=C, orders=orders, sales_transactions=L, payments=pay, purchase_orders=po,
                inventory_movements=mv, fulfillment=fulfil, returns=returns, stockout_events=so, operating_expenses=opex, marketing_spend=mkt, store_calendar=cal)


def main():
    sim = simulate()
    T = assemble(sim)
    SYNTH.mkdir(parents=True, exist_ok=True)
    for k, v in T.items():
        v.to_csv(SYNTH / f"{k}.csv", index=False)
    return T


if __name__ == "__main__":
    import time
    t = time.time()
    T = main()
    for k, v in T.items():
        print(f"{k:22s} {len(v):>8,d}")
    s = T["sales_transactions"]
    print(s.groupby(s.transaction_date.dt.year).net_sales_cad.sum().round(0))
    print(f"{time.time() - t:.1f}s")
