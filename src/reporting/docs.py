"""Documentation deliverables: business understanding & research, data dictionary, model evaluation, accounting policies."""
from __future__ import annotations

import json
import sqlite3

import pandas as pd

from src.config import DB_PATH, DOCS, EXTERNAL, RETRIEVAL_DATE, SYNTHETIC_LABEL, TABLES
from src.finance import policy as P

TABLE_DESC = {
    "products": "Curated product catalogue (350 SKUs). Names, manufacturers and list prices from a public Calgary furniture catalogue; costs, margins, lead times SIMULATED.",
    "suppliers": "Manufacturers / distributors with supplier class, quoted lead time and payment terms (simulated).",
    "customers": "Fictional customers with type, acquisition channel, campaign and lifetime metrics derived from transactions.",
    "leads": "Inquiries (search, social & contests, showroom, referral, online) with conversion status.",
    "staff": "Sales associates and interior designers (fictional IDs).",
    "promotions": "Promotional calendar (event name, dates, extra discount, scope).",
    "campaigns": "Marketing campaigns used for attribution.",
    "consultations": "Free design consultations: designer, type, quotation, follow-ups, conversion, resulting order and revenue, estimated cost.",
    "orders": "Order headers: channel, order type (Custom / Special order / In stock), deposits, balances, promised ready date, fulfilment method, status, cancellations.",
    "sales_transactions": "Order lines (written sales by order date): units, prices, configuration, discounts, net sales, COGS, gross profit, supply source, status.",
    "payments": "Customer payments and refunds (deposits, balances before pickup, trade settlements); pre_period = received before 1-Jan-2024 for opening backlog orders.",
    "purchase_orders": "Supplier POs: stock replenishment, custom (made to order) and special orders with promised/received dates, delays and damage replacements.",
    "inventory_movements": "Perpetual inventory movements by state (stock / allocated to customer) with quantity and value; reconciles to product balances.",
    "fulfillment": "Fulfilment record per active order: readiness vs promise, delay category, hand-off wait reason, pickup / carrier, costs; carrier fees paid by customers are memo only.",
    "returns": "In-stock returns within 3 days with 15% restocking fee.",
    "stockout_events": "Demand for ready-made SKUs lost because stock was unavailable and the customer declined a backorder.",
    "operating_expenses": "Monthly operating expenses by category (simulated, assumption-driven).",
    "marketing_spend": "Monthly marketing spend by channel.",
    "store_calendar": "Daily store-open calendar (closed Sundays, Alberta statutory holidays, Dec 25-26).",
    "fin_general_ledger": "Double-entry general ledger lines (SIMULATED).", "fin_journal_entries": "Journal entry headers.", "fin_trial_balance": "Monthly pre-closing trial balances.",
    "fin_chart_of_accounts": "Chart of accounts.", "fin_ar_subledger": "Receivable open items.", "fin_ap_subledger": "Payable open items.",
    "fin_fixed_assets": "Fixed-asset register.", "fin_debt_treasury": "Debt, revolver, interest, tax and treasury schedule.",
}


def data_dictionary():
    con = sqlite3.connect(DB_PATH)
    rows = []
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        cols = con.execute(f"PRAGMA table_info({t})").fetchall()
        fks = {r[3]: f"{r[2]}({r[4]})" for r in con.execute(f"PRAGMA foreign_key_list({t})")}
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for c in cols:
            ex = con.execute(f'SELECT "{c[1]}" FROM {t} WHERE "{c[1]}" IS NOT NULL LIMIT 1').fetchone()
            rows.append({"table": t, "table_rows": n, "column": c[1], "type": c[2] or "TEXT", "primary_key": bool(c[5]), "references": fks.get(c[1], ""),
                         "example": "" if ex is None else str(ex[0])[:40], "table_description": TABLE_DESC.get(t, "")})
    con.close()
    dd = pd.DataFrame(rows)
    dd.to_csv(DOCS / "data_dictionary.csv", index=False)
    md = ["# Data dictionary", "", f"> {SYNTHETIC_LABEL} Prairie Home Furnishings is fictional.", ""]
    for t, g in dd.groupby("table", sort=False):
        md += [f"## `{t}` ({g.table_rows.iloc[0]:,} rows)", "", g.table_description.iloc[0], "", "| Column | Type | Key | References | Example |", "|---|---|---|---|---|"]
        md += [f"| {r.column} | {r.type} | {'PK' if r.primary_key else ''} | {r.references} | {str(r.example).replace('|', '/')} |" for r in g.itertuples()]
        md.append("")
    (DOCS / "data_dictionary.md").write_text("\n".join(md))
    return dd


def business_understanding():
    src = pd.read_csv(EXTERNAL / "sources_register.csv")
    cat = pd.read_csv(EXTERNAL / "catalogue_curated.csv")
    feed = pd.read_csv(EXTERNAL / "public_catalogue_snapshot.csv")
    pt = feed.groupby("product_type").size().sort_values(ascending=False).head(15)
    md = ["# Business understanding and research", "", f"Research retrieved {RETRIEVAL_DATE} from the public website of the retailer Furniture (Calgary) to make the demonstration realistic. "
          "The demonstration retailer, **Prairie Home Furnishings, is fictional**; only the public facts below were used, and none of the demo's operational or financial figures "
          "describe the retailer Furniture.", "",
          "## Verified public information", "",
          "| Topic | What the public sources say |", "|---|---|",
          "| Positioning | Calgary family-owned furniture store; specialises in custom Canadian-made furniture; states over 1/3 of products are hand-made in Canada; buys factory-direct; 70,000 sq ft showroom at a Calgary shopping centre |",
          f"| Catalogue | {len(feed):,} products in the public feed across sofas & sectionals, beds, mattresses, dining, occasional, lighting, rugs and décor; manufacturers include Mercana, Ashley, LH Imports, Decor-Rest, Elite and others |",
          "| Custom Canadian furniture | Custom sofas/sectionals and beds: customers choose fabric, foam density and configuration; custom pieces are non-refundable |",
          "| Design services | Free design consultation (mood boards, layouts, product options); the store places the order and schedules delivery |",
          "| Pickup & delivery | In-store pickup 10:30-5:30 with 9 slots per day and 24 h notice; outstanding balance paid before pickup; storage beyond a week by request; delivery by third-party movers booked and paid directly by the customer; flat-rate $199 Calgary delivery for online orders over $999 (one item) |",
          "| Returns | In-stock regular-priced items refundable within 3 days with a 15% restocking fee; discounted, clearance, custom, mattresses and bedding are final sale |",
          "| Financing & warranty | 0% financing for 12 months; one-year manufacturer warranty; optional third-party (Guardsman) 5-year protection plan |",
          "| Promotions & community | Seasonal and blowout sales, price-match guarantee (14 days), weekly social-media giveaways, community give-back |", "",
          "Note: the sources state different histories (\"family run since 1987\", \"18 years ago\", \"over 15 years ago\"); this is recorded as stated and not used in the demo.", "",
          "## How the research shaped the demonstration", "",
          "* Categories, manufacturers, custom vs ready-made split and list prices drive the synthetic catalogue (350 SKUs; " + f"{int(cat.custom.sum())} custom made-to-order).",
          "* Published policies became simulation rules: 9 pickup slots/day, balance before pickup, 3-day returns with 15% restocking fee, custom orders non-refundable, deposits on custom orders, "
          "customer-paid third-party delivery (never retailer revenue), flat-rate delivery collected as agent, free consultations, 0% financing via a partner, protection plans sold as agent.",
          "* Not published (and therefore SIMULATED assumptions): costs and margins, supplier lead times and reliability, deposit percentage, staffing, rent, marketing spend, demand and conversion rates.", "",
          "## Complementing existing systems", "",
          "We do not assume the retailer lacks an ERP, POS, accounting, CRM or e-commerce platform. The analytics in this demo are designed to read exports from those systems "
          "(sales lines, product master, inventory/PO history, trial balance, order and deposit register, consult/quote log) and add: margin and promotion analytics, inventory aging and "
          "service-level reorder points, an order-fulfilment tracker with delay-risk scoring, consultation conversion analytics, and integrated financial statements with a forecast.", "",
          "## Public catalogue by product type (top 15)", "", "| Product type | Products |", "|---|---|"] + [f"| {k or '(blank)'} | {v} |" for k, v in pt.items()] + [
          "", "## Source register", "", "| Source | URL | Information used | Retrieved |", "|---|---|---|---|"] + [
          f"| {r.source} | {r.url} | {r.information_used} | {r.retrieved} |" for r in src.itertuples()]
    (DOCS / "business_understanding.md").write_text("\n".join(md) + "\n")


def model_evaluation():
    MR = json.loads((TABLES / "model_results.json").read_text())
    fmc = pd.read_csv(TABLES / "forecast_model_comparison.csv")
    dme = pd.read_csv(TABLES / "delay_model_evaluation.csv")
    cme = pd.read_csv(TABLES / "conversion_model_evaluation.csv")
    reg = pd.read_csv(TABLES / "delay_model_regression.csv")
    fm = lambda df: df.drop(columns="data_status").round(3).to_markdown(index=False)
    md = ["# Model evaluation", "", f"> {SYNTHETIC_LABEL} Accuracy below is measured on synthetic data and does not demonstrate accuracy on any real retailer's transactions.", "",
          "## Validation design", "* **Time-based only**: models are trained on data up to an origin and evaluated after it (holdout Jan-Sep 2026 from origin 31-Dec-2025, plus rolling origins Jun-2025 and Sep-2025).",
          "* **No leakage**: target values after the origin are masked before features are built; year-ago lag features only use pre-origin values; supplier-history features use receipts strictly before each order date;"
          " consultation features are those known at consultation time (follow-ups, which happen later, are excluded).",
          "* **Right-censoring** (delays): open POs already more than 7 days past promise are labelled late; open POs not yet due are excluded.", "",
          "## Model A - monthly written sales (bookings)", f"Selected: **{MR['model_a']['chosen']}** (lowest average of holdout WAPE and mean WAPE across all origins).", "", fm(fmc[fmc.target == "net_sales"]), "",
          "## Model B - demand by category (units)", "Selected model per category: " + ", ".join(f"{k}: {v}" for k, v in MR["model_b"]["chosen"].items()), "",
          fm(fmc[fmc.target != "net_sales"]), "", "Home Office has very few units per month, so percentage errors are large and should not drive decisions.", "",
          "## Model C - custom / special-order delay (> 7 days late)", f"Best: **{MR['model_c']['best']}**. Test = orders placed Jul-2025 to May-2026.", "", fm(dme), "",
          f"Delay-days regression: MAE baseline {reg.MAE_days_baseline[0]:.1f} days vs XGBoost {reg.MAE_days_xgboost[0]:.1f} days.", "",
          "Interpretation: lift over the supplier-history baseline is modest because simulated delays are largely random within supplier class and season; on real data, carrier, "
          "fabric availability and factory capacity signals would be added.", "",
          "## Model D - design-consultation conversion propensity", f"Best: **{MR['model_d']['best']}**. Test = consultations Oct-2025 to mid-Aug-2026.", "", fm(cme), "",
          f"Pipeline forecast: {MR['model_d']['pipeline_open']} open consultations, ~{MR['model_d']['pipeline_expected_conversions']:.0f} expected conversions and "
          f"${MR['model_d']['pipeline_expected_revenue']:,.0f} expected sales (quote realisation ratio {MR['model_d']['quote_realisation_ratio']:.2f}).", "",
          "## Model E - cash flow and working capital", "Integrated driver-based forecast (src/finance/forecast.py): bookings from Model A, recognition lags, deposits, inventory policy, supplier terms, "
          "GST/tax timing and debt; validated by balance-sheet and cash checks under 50 random assumption sets and by Excel recalculation."]
    (DOCS / "model_evaluation.md").write_text("\n".join(md) + "\n")


def accounting_policies():
    ch = pd.read_csv(TABLES / "fin_validation_checks.csv")
    md = ["# Accounting policies and financial validation", "", f"> {P.FIN_LABEL}.", "", "## Policies", P.__doc__.strip(), "",
          "## Key parameters", f"* GST {P.GST_RATE:.0%}; income tax {P.TAX_SMALL_RATE:.0%} on the first ${P.SMALL_BUSINESS_LIMIT:,.0f}, {P.TAX_GENERAL_RATE:.0%} above; {P.TAX_PAYMENT}.",
          f"* Financing-partner fee {P.FIN_PARTNER_FEE:.0%}; protection-plan commission {P.PLAN_COMMISSION:.0%}; freight-in {P.FREIGHT_IN_RATE:.0%} of receipts; supplier terms Net {P.SUPPLIER_TERMS_DAYS}.",
          f"* Term loan ${P.TERM_LOAN['balance_open']:,.0f} at 31-Dec-2023, {P.TERM_LOAN['months_remaining']} monthly instalments, prime + {P.TERM_LOAN['spread']:.2%}; revolver ${P.REVOLVER['limit']:,.0f}.",
          f"* Opening position: cash ${P.OPENING['cash']:,.0f}, share capital ${P.OPENING['share_capital']:,.0f}; opening retained earnings = residual of the explicit opening balances.",
          f"* Dividend: {P.DIVIDEND['payout']:.0%} of fiscal-year net income if cash stays above ${P.DIVIDEND['cash_floor']:,.0f}.", "",
          "## Validation results", "| # | Check | Result | Evidence |", "|---|---|---|---|"] + [f"| {r.check_no} | {r.check} | {r.result} | {r.detail} |" for r in ch.itertuples()]
    (DOCS / "accounting_policies_and_validation.md").write_text("\n".join(md) + "\n")


def run():
    business_understanding()
    data_dictionary()
    model_evaluation()
    accounting_policies()


if __name__ == "__main__":
    run()
