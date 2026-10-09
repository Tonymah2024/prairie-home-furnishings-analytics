"""Central configuration for the Prairie Home Furnishings analytics demonstration (VisiVault Analytics Ltd.).

Prairie Home Furnishings is a FICTIONAL Calgary furniture retailer. Product categories, manufacturers and CAD
list prices are anchored to a public Calgary furniture retailer's online catalogue (retrieved RETRIEVAL_DATE);
every operational and financial record is SYNTHETIC and generated with a fixed SEED.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_EXTERNAL = DATA / "external" / "raw"
EXTERNAL = DATA / "external" / "processed"
SYNTH = DATA / "synthetic"
DB_PATH = DATA / "prairie_home_synthetic.db"
SQL_DIR = ROOT / "sql"
DOCS = ROOT / "docs"
OUT = ROOT / "outputs"
CHARTS = OUT / "charts"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
MODELS = OUT / "models"
FIN_OUT = OUT / "finance"

SEED = 20240102
START = "2024-01-01"
END = "2026-09-30"
FORECAST_START = "2026-10-01"
FORECAST_MONTHS = 12
RETRIEVAL_DATE = "2026-10-09"

APP_NAME = "Prairie Home Furnishings Analytics"
STORE_NAME = "Prairie Home Furnishings (fictional Calgary retailer)"
ATTRIBUTION = "Demonstration developed by VisiVault Analytics Ltd."
SYNTHETIC_LABEL = "Synthetic demonstration data — not actual company financial or operational records."
FIN_LABEL = "SIMULATED FINANCIAL INFORMATION — synthetic demonstration accounts of a fictional retailer"

# VisiVault brand palette (from the VisiVault website CSS variables); FIN = validated 4-slot categorical order
BRAND = {
    "brand": "#2a78d6", "brand_dark": "#184f95", "brand_light": "#eaf2fc",
    "accent": "#4a3aa7", "accent_light": "#efeaf9", "teal": "#0d9488",
    "navy": "#0b1120", "navy2": "#10192e", "bg": "#f9f9f7", "muted": "#52514e",
    "subtle": "#898781", "good": "#0ca30c", "warn": "#d97706", "bad": "#c2410c",
}
SERIES = ["#2a78d6", "#0d9488", "#4a3aa7", "#d97706"]

for p in (EXTERNAL, SYNTH, DOCS, CHARTS, TABLES, REPORTS, MODELS, FIN_OUT):
    p.mkdir(parents=True, exist_ok=True)
