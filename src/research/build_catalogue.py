"""Public research inputs -> processed, source-labelled tables.

* Parses the public Shopify product feed of a Calgary furniture retailer (retrieved RETRIEVAL_DATE) into a full
  snapshot and a curated catalogue for the FICTIONAL demonstration retailer "Prairie Home Furnishings".
  Verified fields: product title, manufacturer (vendor), product type, CAD list price, compare-at price.
  Simulated fields (clearly labelled): acquisition cost, margin, supplier lead time, stocking policy.
* Builds the Alberta holiday calendar and Bank of Canada series (public data).
* Writes the source register used in docs/business_understanding.md.
"""
from __future__ import annotations

import json
import re

import holidays
import numpy as np
import pandas as pd

from src.config import EXTERNAL, RAW_EXTERNAL, RETRIEVAL_DATE, SEED

SITE = "a public Calgary furniture retailer's website"

TYPE_MAP = [  # (regex on product_type or title, category group, subcategory)
    (r"sectional", "Sofas & Sectionals", "Sectionals"), (r"sofa ?bed|sleeper", "Sofas & Sectionals", "Sofa beds"),
    (r"recliner|reclining", "Sofas & Sectionals", "Recliners"), (r"loveseat", "Sofas & Sectionals", "Loveseats"),
    (r"sofa", "Sofas & Sectionals", "Sofas"),
    (r"adjustable base", "Mattresses & Bases", "Adjustable bases"), (r"mattress", "Mattresses & Bases", "Mattresses"),
    (r"murphy", "Bedroom", "Murphy beds"), (r"kids bed", "Bedroom", "Kids beds"), (r"\bbed\b|beds", "Bedroom", "Beds"),
    (r"dresser|chest", "Bedroom", "Dressers & chests"), (r"nightstand", "Bedroom", "Nightstands"),
    (r"dining table|bistro table", "Dining", "Dining tables"), (r"dining chair", "Dining", "Dining chairs"),
    (r"counter stool|bar stool|stool", "Dining", "Bar & counter stools"), (r"sideboard|buffet|hutch", "Dining", "Sideboards & buffets"),
    (r"kitchen island", "Dining", "Kitchen islands"),
    (r"coffee table|cocktail table", "Living & Occasional", "Coffee tables"), (r"side table|end table|accent table", "Living & Occasional", "Side & accent tables"),
    (r"console", "Living & Occasional", "Console tables"), (r"accent chair|arm chair|nest chair|swivel|chair", "Living & Occasional", "Accent chairs"),
    (r"ottoman|bench", "Living & Occasional", "Ottomans & benches"), (r"media|tv", "Living & Occasional", "Media cabinets"),
    (r"cabinet|bookcase|shelv|shelf", "Living & Occasional", "Cabinets & storage"),
    (r"desk", "Home Office", "Desks"),
    (r"rug", "Décor & Lighting", "Rugs"), (r"chandelier|lighting|lamp|pendant|sconce", "Décor & Lighting", "Lighting"),
    (r"mirror", "Décor & Lighting", "Mirrors"), (r"wall art|canvas|art|wall box", "Décor & Lighting", "Wall art"),
    (r"pouf|pillow|duvet|bedding|throw", "Décor & Lighting", "Textiles & poufs"),
    (r"vase|planter|clock|decor|sculpture|tray|bowl", "Décor & Lighting", "Decorative accessories"),
]
VENDOR_NORM = {"lh imports": "LH Imports", "lh": "LH Imports", "lh home": "LH Imports", "ashley": "Ashley Furniture",
               "signature design by ashley": "Ashley Furniture", "mercana studio": "Mercana", "amax leather": "Amax",
               "aurora furniture manufacturing": "Aurora", "tempur-pro": "Tempur-Pedic"}
HOUSE = re.compile(r"the retailer", re.I)
CANADIAN_CUSTOM_MAKERS = {"Decor-Rest", "Elite", "Sahara Furniture", "Aurora"}

# ASSUMPTIONS (not published by any retailer): gross-margin targets by category and lead times by supplier class
MARGIN = {"Sofas & Sectionals": 0.48, "Mattresses & Bases": 0.51, "Bedroom": 0.48, "Dining": 0.49, "Living & Occasional": 0.51,
          "Home Office": 0.49, "Décor & Lighting": 0.57}
CUSTOM_MARGIN = 0.44
LEAD = {  # supplier class: (quoted lead days, mean delay days, delay sd, on-time probability) - SIMULATED
    "Canadian custom upholstery": (49, 9, 12, 0.62), "North American case goods & upholstery": (28, 5, 9, 0.72),
    "Canadian décor & furniture distributor": (14, 2, 5, 0.85), "Canadian furniture importer": (21, 6, 10, 0.70),
    "Mattress manufacturer": (10, 1, 3, 0.90), "Specialty importer": (42, 10, 14, 0.58),
}


def supplier_class(vendor, custom):
    if vendor in CANADIAN_CUSTOM_MAKERS or (custom and vendor in {"Amax"}):
        return "Canadian custom upholstery"
    if vendor in {"Ashley Furniture", "Magnussen", "Amax"}:
        return "North American case goods & upholstery"
    if vendor in {"Mercana", "Kalora", "Fab Habitat", "Emerald Home"}:
        return "Canadian décor & furniture distributor"
    if vendor in {"LH Imports", "Mobital", "Style in Form"}:
        return "Canadian furniture importer"
    if vendor in {"King Koil", "Sleep Chest", "Tempur-Pedic", "Restonic", "Blu Sleep"}:
        return "Mattress manufacturer"
    return "Specialty importer"


def classify(ptype, title):
    s = f"{ptype} {title}".lower()
    for pat, grp, sub in TYPE_MAP:
        if re.search(pat, ptype.lower() if ptype else "") or (not ptype and re.search(pat, title.lower())):
            return grp, sub
    for pat, grp, sub in TYPE_MAP:
        if re.search(pat, s):
            return grp, sub
    return None, None


def clean_title(t):
    t = re.sub(r"[^\w\s\-&'\"/.,()+]", "", t)          # strip emoji and symbols
    t = HOUSE.sub("", t)
    t = re.sub(r"\s*[-|]\s*(sale|clearance|final sale|low price.*|limited stock.*|in stock.*|floor model.*)\s*$", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" -")
    if t.isupper():
        t = t.title()
    return t


def feed_snapshot() -> pd.DataFrame:
    rows = []
    for f in sorted(RAW_EXTERNAL.glob("products_p*.json"), key=lambda p: int(re.findall(r"\d+", p.stem)[0])):
        for p in json.load(open(f))["products"]:
            prices = [float(v["price"]) for v in p["variants"] if v.get("price")]
            comps = [float(v["compare_at_price"]) for v in p["variants"] if v.get("compare_at_price")]
            tags = ",".join(p["tags"]) if isinstance(p["tags"], list) else (p["tags"] or "")
            rows.append({"feed_id": p["id"], "handle": p["handle"], "title": p["title"], "vendor": p["vendor"], "product_type": p["product_type"] or "",
                         "tags": tags, "n_variants": len(p["variants"]), "options": "|".join(o["name"] for o in p.get("options", [])),
                         "price_min_cad": min(prices) if prices else np.nan, "price_max_cad": max(prices) if prices else np.nan,
                         "compare_at_max_cad": max(comps) if comps else np.nan, "available": any(v.get("available") for v in p["variants"]),
                         "created_at": p["created_at"][:10], "retrieved": RETRIEVAL_DATE, "source": f"{SITE}/products.json"})
    return pd.DataFrame(rows)


def curate(feed: pd.DataFrame, rng) -> pd.DataFrame:
    d = feed[(feed.price_min_cad >= 25) & feed.available].copy()
    d[["category", "subcategory"]] = [classify(p, t) for p, t in zip(d.product_type, d.title)]
    d = d.dropna(subset=["category"])
    d["manufacturer"] = d.vendor.str.strip().map(lambda v: VENDOR_NORM.get(v.lower(), v))
    d.loc[d.manufacturer.str.contains(HOUSE), "manufacturer"] = "House collection (various makers)"
    d["made_in_canada"] = (d.title.str.contains("made in canada|🇨🇦", case=False) | d.tags.str.contains("made in canada", case=False)
                           | d.manufacturer.isin(CANADIAN_CUSTOM_MAKERS))
    custom_kw = d.title.str.contains("custom", case=False) | d.tags.str.contains("custom canadian|canadian custom", case=False)
    d["custom"] = (((custom_kw | d.manufacturer.isin(CANADIAN_CUSTOM_MAKERS)) & d.category.isin(["Sofas & Sectionals", "Bedroom", "Living & Occasional"])
                    & d.subcategory.isin(["Sectionals", "Sofas", "Loveseats", "Sofa beds", "Recliners", "Beds", "Accent chairs", "Ottomans & benches"])))
    d["title_clean"] = d.title.map(clean_title)
    d = d.drop_duplicates("title_clean")
    # stratified selection: keep the assortment shape (more SKUs where the public catalogue is deep), cap per subcategory
    quota = {"Sofas & Sectionals": 70, "Mattresses & Bases": 22, "Bedroom": 45, "Dining": 60, "Living & Occasional": 75, "Home Office": 8, "Décor & Lighting": 70}
    picks = []
    for grp, g in d.groupby("category"):
        n = min(len(g), quota[grp])
        w = g.groupby("subcategory").title.transform("count") ** -0.35        # flatten deep subcategories a little
        if grp == "Sofas & Sectionals":
            w = w * np.where(g.custom, 1.6, 1.0)
        picks.append(g.sample(n, weights=w, random_state=int(rng.integers(1e9))))
    c = pd.concat(picks).sort_values(["category", "subcategory", "title_clean"]).reset_index(drop=True)
    c["product_id"] = [f"PRD-{i + 1:04d}" for i in range(len(c))]
    code = c.category.map({"Sofas & Sectionals": "SOF", "Mattresses & Bases": "MAT", "Bedroom": "BED", "Dining": "DIN", "Living & Occasional": "LIV",
                           "Home Office": "OFF", "Décor & Lighting": "DEC"})
    c["sku"] = [f"PHF-{k}-{i + 1:04d}" for i, k in enumerate(code)]
    c["fulfillment_type"] = np.where(c.custom, "Custom (made to order)", "Stocked (ready-made)")
    c["supplier_class"] = [supplier_class(v, cu) for v, cu in zip(c.manufacturer, c.custom)]
    m = np.where(c.custom, CUSTOM_MARGIN, c.category.map(MARGIN)) + rng.normal(0, 0.035, len(c))
    c["assumed_margin"] = np.clip(m, 0.28, 0.66).round(3)
    c["list_price_cad"] = c.price_min_cad.round(2)
    c["unit_cost_cad"] = (c.list_price_cad * (1 - c.assumed_margin)).round(2)
    c["quoted_lead_days"] = c.supplier_class.map(lambda s: LEAD[s][0])
    big = c.list_price_cad > 1500
    c["popularity_prior"] = np.exp(rng.normal(0, 0.8, len(c))) * np.where(c.category == "Décor & Lighting", 1.3, 1.0) * np.where(big, 0.75, 1.0)
    c["price_status"] = "List price VERIFIED from public catalogue (" + RETRIEVAL_DATE + "); cost, margin, lead time SIMULATED"
    return c[["product_id", "sku", "title_clean", "manufacturer", "category", "subcategory", "fulfillment_type", "custom", "made_in_canada",
              "options", "list_price_cad", "compare_at_max_cad", "unit_cost_cad", "assumed_margin", "supplier_class", "quoted_lead_days",
              "popularity_prior", "handle", "price_status"]].rename(columns={"title_clean": "product_name", "compare_at_max_cad": "compare_at_cad"})


def boc() -> pd.DataFrame:
    obs = json.load(open(RAW_EXTERNAL / "boc_valet.json"))["observations"]
    rows = [{"date": o["d"], "policy_rate_pct": float(o["V39079"]["v"]) if "V39079" in o else np.nan,
             "cpi_total": float(o["V41690973"]["v"]) if "V41690973" in o else np.nan} for o in obs]
    d = pd.DataFrame(rows)
    d["month"] = pd.to_datetime(d.date).dt.to_period("M").dt.to_timestamp()
    m = d.groupby("month").agg(policy_rate_pct=("policy_rate_pct", "last"), cpi_total=("cpi_total", "last")).ffill()
    m["source"] = "Bank of Canada Valet API (V39079 policy rate; V41690973 total CPI)"
    return m.reset_index()


def holiday_calendar() -> pd.DataFrame:
    ab = holidays.Canada(subdiv="AB", years=range(2023, 2029))
    h = pd.DataFrame(sorted(ab.items()), columns=["date", "holiday"])
    h["source"] = "python-holidays (Canada, Alberta)"
    return h


SOURCES = [
    ("Public product feed", f"{SITE}/products.json", "1,752 products: titles, manufacturers, product types, CAD list and compare-at prices, availability"),
    ("Contact page", f"{SITE}/pages/contact-us", "Location (Calgary), hours Mon-Sat 10-6 / Sunday closed, third-party delivery company paid directly, Guardsman protection plan claims"),
    ("Free design consult page", f"{SITE}/pages/free-design-consult", "Free design consultation: schedule, mood boards/layouts, store places order, third-party delivery paid directly by client"),
    ("Pickup & delivery page", f"{SITE}/pages/shipping-delivery", "In-store pickup 10:30-5:30, 9 pickup slots/day, 24h notice, balance paid before pickup, storage beyond 1 week by request; white-glove partner booked and paid directly"),
    ("Returns & exchanges page / refund policy", f"{SITE}/pages/returns-exchanges", "In-stock regular-priced items refundable within 3 days with 15% restocking fee; discounted, custom, mattresses, bedding and clearance final sale"),
    ("0% financing page", f"{SITE}/pages/interest-free-financing-calgary", "0% interest financing, no admin cost for 12 months"),
    ("FAQs", f"{SITE}/pages/the retailer-faqs", "Family business; custom Canadian sofas/sectionals (fabric, foam, configuration); 70,000 sq ft showroom; price-match guarantee within 14 days; $199 flat-rate Calgary delivery for online orders over $999 (one item); free design consult Mon-Sat; 5,000+ reviews; contests/giveaways"),
    ("Our story", f"{SITE}/pages/the retailer-furniture-story", "Specialises in custom Canadian furniture; over 1/3 of products hand-made in Canada; buys factory-direct"),
    ("Warranty page", f"{SITE}/pages/the retailers-warranty", "One-year manufacturer warranty; optional third-party Guardsman 5-year protection plan sold through the store"),
    ("Terms of service", f"{SITE}/policies/terms-of-service", "Warehouse pickup Mon-Sat; local third-party delivery companies paid directly by the customer"),
    ("Bank of Canada Valet API", "https://www.bankofcanada.ca/valet/", "Policy rate and CPI (monthly) used as macro context / forecast regressors"),
    ("Alberta statutory holidays", "python-holidays package (CA, subdiv=AB)", "Store-closure calendar"),
]


def build():
    if not any(RAW_EXTERNAL.glob("products_p*.json")):              # public copy ships only the processed, source-labelled tables
        print("No raw public snapshots found - using the processed catalogue in data/external/processed.")
        return None, pd.read_csv(EXTERNAL / "catalogue_curated.csv")
    rng = np.random.default_rng(SEED)
    feed = feed_snapshot()
    feed.to_csv(EXTERNAL / "public_catalogue_snapshot.csv", index=False)
    cat = curate(feed, rng)
    cat.to_csv(EXTERNAL / "catalogue_curated.csv", index=False)
    boc().to_csv(EXTERNAL / "economic_indicators_monthly.csv", index=False)
    holiday_calendar().to_csv(EXTERNAL / "alberta_holidays.csv", index=False)
    src = pd.DataFrame(SOURCES, columns=["source", "url", "information_used"])
    src["retrieved"] = RETRIEVAL_DATE
    src.to_csv(EXTERNAL / "sources_register.csv", index=False)
    return feed, cat


if __name__ == "__main__":
    f, c = build()
    print(len(f), "feed products ->", len(c), "curated SKUs")
    print(c.groupby(["category", "fulfillment_type"]).size())
    print(c.groupby("supplier_class").size())
    print(c.list_price_cad.describe())
