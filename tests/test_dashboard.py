"""Dashboard functionality: every page renders and is labelled, filters work, downloads exist, simulator responds."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")
PAGES = ["1. Executive Overview", "2. Sales Performance", "3. Product Profitability", "4. Inventory Intelligence", "5. Custom Order Tracking",
         "6. Supplier & Fulfillment Analytics", "7. Customer Intelligence", "8. Design Consultation Analytics", "9. Income Statement", "10. Balance Sheet",
         "11. Cash Flow Statement", "12. Financial Ratios", "13. Sales & Cash Flow Forecasting", "14. Business Scenario Simulator"]


def app(page=None):
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    if page:
        at.sidebar.radio[0].set_value(page).run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_labelled_with_content(page):
    at = app(page)
    assert not at.exception, at.exception[0].value
    assert len(at.get("plotly_chart")) + len(at.dataframe) > 0
    text = " ".join(m.value for m in at.markdown)
    assert "Synthetic demonstration data" in text and "VisiVault Analytics" in text


def test_filters_change_sales_page():
    at = app(PAGES[1])
    before = [m.value for m in at.markdown if "class='kpi'" in m.value][0]
    at.sidebar.multiselect[0].set_value(["Dining"]).run()
    after = [m.value for m in at.markdown if "class='kpi'" in m.value][0]
    assert not at.exception and before != after


@pytest.mark.parametrize("page", [PAGES[1], PAGES[3], PAGES[4], PAGES[8]])
def test_csv_downloads_present(page):
    at = app(page)
    assert len(at.get("download_button")) >= 1


def test_simulator_responds():
    at = app(PAGES[13])
    v0 = [m.value for m in at.markdown if "Net income" in m.value][0]
    at.slider[0].set_value(10.0).run()
    v1 = [m.value for m in at.markdown if "Net income" in m.value][0]
    assert not at.exception and v0 != v1
