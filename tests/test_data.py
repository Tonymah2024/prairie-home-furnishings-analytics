"""Data consistency and database relationships."""
import hashlib

import pandas as pd
import pytest

from src.config import SYNTH
from src.engineering.load_db import validate
from src.engineering.sqlutil import connect


def test_all_sql_validation_checks_pass():
    c = validate()
    assert (c.violations == 0).all(), c[c.violations > 0].to_string()
    assert len(c) >= 30


def test_foreign_keys_enforced():
    con = connect()
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(Exception):
        con.execute("INSERT INTO sales_transactions (line_id, order_id, product_id, units, unit_price_cad, gross_sales_cad, net_sales_cad, discount_pct) "
                    "VALUES ('X', 'ORD-NOPE', 'PRD-0001', 1, 1, 1, 1, 0)")
        con.commit()
    con.rollback()
    con.close()


def test_volume_and_period():
    s = pd.read_csv(SYNTH / "sales_transactions.csv")
    assert 15000 <= len(s) <= 25000
    inp = s[~s.opening_backlog]
    assert inp.transaction_date.min() >= "2024-01-01" and s.transaction_date.max() <= "2026-09-30"


def test_inventory_reconciles_per_sku_and_state():
    mv = pd.read_csv(SYNTH / "inventory_movements.csv")
    p = pd.read_csv(SYNTH / "products.csv").set_index("product_id")
    q = mv.groupby(["product_id", "inventory_state"]).quantity.sum().unstack(fill_value=0)
    assert (q.reindex(p.index).fillna(0)["stock"] == p.on_hand_stock_units).all()
    assert (q.reindex(p.index).fillna(0)["allocated"] == p.allocated_to_customers_units).all()


def test_third_party_delivery_never_revenue():
    f = pd.read_csv(SYNTH / "fulfillment.csv")
    tp = f[f.fulfillment_method == "Third-party delivery (customer-paid)"]
    assert (tp.agent_delivery_fee_cad == 0).all() and tp.carrier_fee_note.str.contains("not retailer revenue").all()


@pytest.mark.slow
def test_generator_is_reproducible():
    from src.generate import synthetic
    before = hashlib.md5((SYNTH / "sales_transactions.csv").read_bytes()).hexdigest()
    synthetic.main()
    assert hashlib.md5((SYNTH / "sales_transactions.csv").read_bytes()).hexdigest() == before
