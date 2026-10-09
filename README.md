# Prairie Home Furnishings Analytics — Retail BI, Inventory, Order-Fulfilment & Financial Intelligence

**Demonstration developed by VisiVault Analytics Ltd.** · October 2026

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://prairie-home-furnishings-bi.streamlit.app)

**▶ Live dashboard: <https://prairie-home-furnishings-bi.streamlit.app>**

> ⚠ **Synthetic demonstration data — not actual company financial or operational records.**
> *Prairie Home Furnishings* is a **fictional** Calgary furniture retailer. Product categories, manufacturers and CAD list prices reflect the public online
> catalogue of a Calgary furniture retailer (retrieved 2026-10-09), and the simulation follows that retailer's publicly described policies.
> Every order, cost, customer, consultation, supplier delivery and financial figure is synthetic (seed `20240102`). No relationship with or endorsement by any real company is implied.

## What's inside

| Path | Contents |
|---|---|
| `run_pipeline.py` | One-command reproducible pipeline: research → synthetic data → database → analytics → models → finance → recommendations → reports → docs (~2 min) |
| `src/research/` | Public catalogue parser (Shopify feed), policy research, Bank of Canada and Alberta holidays, source register |
| `src/generate/synthetic.py` | Day-by-day simulation (with a Sep–Dec 2023 warm-up backlog): orders, custom vs in-stock lines, deposits, POs, supplier delays, pickup slots, carriers, cancellations, returns, consultations, leads, expenses |
| `src/engineering/load_db.py` | SQLite database with enforced keys and checks; 30 SQL validation checks (`sql/validation_checks.sql`); generated `sql/schema.sql` |
| `src/analysis/` | Sales, product, inventory (ABC, FIFO aging, reorder points & safety stock), order/fulfilment, customer (RFM, CLV, cohorts), consultation and attribution analytics; costed recommendations |
| `src/models/` | Model A sales forecasting · Model B category demand · Model C delay prediction · Model D conversion propensity (time-based validation, leakage controls) |
| `src/finance/` | Double-entry ledger, three statements (monthly/quarterly/annual, common-size), ratios, integrated 12-month forecast & scenario engine, Excel model builder, validation |
| `dashboard/app.py` | Streamlit + Plotly dashboard, 14 pages |
| `outputs/finance/` | Integrated Excel model (live formulas, scenario selector) + statements, ratios, working-capital and forecast workbooks; general ledger & journal entries (CSV.gz) |
| `outputs/reports/` | Executive management report · Financial performance analysis · Demonstration guide · Pilot proposal · 90-day pilot plan (PDF + HTML) |
| `outputs/tables/` | All result tables (CSV/JSON) used by the dashboard |
| `data/synthetic/` · `data/prairie_home_synthetic.db` | Synthetic CSV datasets and the relational database |
| `docs/` | Business understanding & sources, data dictionary (MD + CSV), model evaluation, accounting policies & validation, Streamlit Cloud deployment |
| `tests/` | 46 automated tests (data consistency, relationships, reconciliation, forecast leakage, dashboard pages/filters/downloads, reproducibility) |

## Headline demonstration results (synthetic)

* 20,899 order lines and 7,760 orders (Jan 2024 – Sep 2026), 350 SKUs, 1,919 design consultations; all 30 database checks pass with zero foreign-key violations.
* Trailing-twelve-month written sales $10.21M at a 45.3% line gross margin; custom Canadian-made pieces are 26% of sales.
* FY2025 net revenue $9.63M, EBITDA $816K, net income $585K; 40,842 balanced journal entries; all 11 financial checks pass.
* Only 54% of custom orders are ready by the promised date; 219 open orders hold $496K of customer deposits.
* Design consultations convert 52% (orders $7,246 vs $3,026); two follow-ups lift conversion from 32% to 53%.
* Sales forecast (SARIMAX): holdout WAPE 3.8% vs 5.8% seasonal-naive; Base 12-month forecast net income $611K.

## Run locally

```bash
cd "the retailer Furniture - Furniture Store in Calgary"
uv venv -p 3.11 .venv            # or: python3.11 -m venv .venv
uv pip install -p .venv/bin/python -r requirements.txt
.venv/bin/python run_pipeline.py                 # rebuild everything (~2 min)
.venv/bin/python -m pytest                       # 46 tests
.venv/bin/streamlit run dashboard/app.py         # http://localhost:8501
```
PDFs are rendered with a locally installed Google Chrome / Edge / Chromium (headless). If Microsoft Excel is installed (macOS), the pipeline also
recalculates the Excel model in Excel and checks it against the Python engine. Live demo: <https://prairie-home-furnishings-bi.streamlit.app> · deployment notes: `docs/deployment_streamlit_cloud.md`.

## Accounting policy in one paragraph

Revenue is recognised when the customer collects the order or it is loaded onto the customer's own carrier — not on the order date. Deposits and balances
received before that are customer deposits (contract liabilities). Third-party delivery is booked and paid by the customer directly and is never retailer revenue;
flat-rate delivery collected for a partner carrier and protection plans are handled as agent (only the plan commission is revenue). Inventory is carried at purchase
cost, split between stocked goods and goods allocated to customer orders. See `docs/accounting_policies_and_validation.md`.
