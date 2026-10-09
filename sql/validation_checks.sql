-- Data-integrity and reconciliation checks. Each query returns the number of violating rows (must be 0).

-- name: order_value_equals_sum_of_lines
SELECT COUNT(*) FROM orders o JOIN (SELECT order_id, SUM(net_sales_cad) s FROM sales_transactions GROUP BY 1) l USING (order_id)
WHERE ABS(o.net_order_value_cad - l.s) > 0.05;

-- name: line_gross_equals_units_x_price
SELECT COUNT(*) FROM sales_transactions WHERE ABS(gross_sales_cad - units * unit_price_cad) > 0.02;

-- name: line_net_equals_gross_less_discount
SELECT COUNT(*) FROM sales_transactions WHERE ABS(net_sales_cad - ROUND(gross_sales_cad * (1 - discount_pct), 2)) > 0.02;

-- name: line_gross_profit_identity
SELECT COUNT(*) FROM sales_transactions WHERE ABS(gross_profit_cad - (net_sales_cad - cogs_cad)) > 0.02 OR ABS(cogs_cad - units * unit_cost_cad) > 0.02;

-- name: every_order_has_lines
SELECT COUNT(*) FROM orders o WHERE NOT EXISTS (SELECT 1 FROM sales_transactions s WHERE s.order_id = o.order_id);

-- name: fulfilled_orders_fully_paid
SELECT COUNT(*) FROM orders o
LEFT JOIN (SELECT order_id, SUM(amount_incl_gst) paid FROM payments GROUP BY 1) p USING (order_id)
LEFT JOIN (SELECT order_id, SUM(refund_incl_gst_cad) r FROM returns GROUP BY 1) r USING (order_id)
WHERE o.status = 'Fulfilled' AND NOT (o.trade_account = 1 AND date(o.fulfilled_date, '+30 day') > '2026-09-30')
  AND ABS(COALESCE(p.paid, 0) - (o.order_total_incl_gst_cad + o.protection_plan_cad + o.agent_delivery_fee_cad - COALESCE(r.r, 0))) > 0.05;

-- name: cancelled_orders_refund_or_retained_fee
SELECT COUNT(*) FROM orders o LEFT JOIN (SELECT order_id, SUM(amount_incl_gst) paid FROM payments GROUP BY 1) p USING (order_id)
WHERE o.status = 'Cancelled' AND ABS(COALESCE(p.paid, 0) - ROUND(o.retained_cancellation_fee_cad * 1.05, 2)) > 0.05;

-- name: open_orders_deposit_received
SELECT COUNT(*) FROM orders WHERE status IN ('Awaiting supplier', 'Ready - awaiting pickup/delivery') AND deposit_paid_cad + 0.05 < deposit_required_cad;

-- name: balance_paid_before_handoff
SELECT COUNT(*) FROM orders o WHERE o.status = 'Fulfilled' AND o.trade_account = 0
  AND (SELECT COALESCE(SUM(amount_incl_gst), 0) FROM payments p WHERE p.order_id = o.order_id AND p.payment_date <= o.fulfilled_date AND p.amount_incl_gst > 0)
      + 0.05 < o.order_total_incl_gst_cad;

-- name: fulfilment_date_sequence
SELECT COUNT(*) FROM orders WHERE (fulfilled_date IS NOT NULL AND (fulfilled_date < ready_date OR ready_date < order_date))
   OR (cancel_date IS NOT NULL AND cancel_date < order_date);

-- name: pickup_slots_per_day_within_capacity
SELECT COUNT(*) FROM (SELECT fulfilled_date, COUNT(*) n FROM orders WHERE fulfillment_method = 'Customer pickup' AND status = 'Fulfilled'
                      AND date(fulfilled_date) <> date(order_date) GROUP BY 1 HAVING n > 9);

-- name: inventory_movements_reconcile_to_product_balances
SELECT COUNT(*) FROM products p
LEFT JOIN (SELECT product_id, SUM(CASE WHEN inventory_state = 'stock' THEN quantity END) s, SUM(CASE WHEN inventory_state = 'allocated' THEN quantity END) a
           FROM inventory_movements GROUP BY 1) m USING (product_id)
WHERE COALESCE(m.s, 0) <> p.on_hand_stock_units OR COALESCE(m.a, 0) <> p.allocated_to_customers_units;

-- name: no_negative_running_inventory
SELECT COUNT(*) FROM (SELECT SUM(quantity) OVER (PARTITION BY product_id, inventory_state ORDER BY movement_id) bal FROM inventory_movements) WHERE bal < 0;

-- name: allocated_units_match_open_order_lines
SELECT COUNT(*) FROM (
  SELECT p.product_id, COALESCE(m.a, 0) a, COALESCE(l.u, 0) u FROM products p
  LEFT JOIN (SELECT product_id, SUM(quantity) a FROM inventory_movements WHERE inventory_state = 'allocated' GROUP BY 1) m USING (product_id)
  LEFT JOIN (SELECT product_id, SUM(units) u FROM sales_transactions WHERE line_status = 'Allocated - awaiting pickup/delivery' GROUP BY 1) l USING (product_id))
WHERE a <> u;

-- name: stock_receipts_match_purchase_orders
SELECT COUNT(*) FROM (
  SELECT po_id, qty_received FROM purchase_orders WHERE po_type = 'Stock replenishment' AND status = 'Received' AND received_date >= '2024-01-01' AND qty_received > 0) po
LEFT JOIN (SELECT reference_id, SUM(quantity) q FROM inventory_movements WHERE movement_type = 'PO_RECEIPT' GROUP BY 1) m ON m.reference_id = po.po_id
WHERE COALESCE(m.q, 0) <> po.qty_received;

-- name: fulfilled_units_match_movements
SELECT COUNT(*) FROM (SELECT line_id, units FROM sales_transactions WHERE line_status IN ('Fulfilled', 'Returned') AND fulfilled_date >= '2024-01-01') l
LEFT JOIN (SELECT reference_id, -SUM(quantity) q FROM inventory_movements WHERE movement_type = 'FULFILL' GROUP BY 1) m ON m.reference_id = l.line_id
WHERE COALESCE(m.q, 0) <> l.units;

-- name: returns_only_eligible_lines
SELECT COUNT(*) FROM returns r JOIN sales_transactions s USING (line_id) JOIN products p ON p.product_id = s.product_id
WHERE s.discount_pct > 0 OR s.supply_source <> 'From stock' OR p.category = 'Mattresses & Bases' OR julianday(r.return_date) - julianday(s.fulfilled_date) > 3;

-- name: restocking_fee_is_15_percent
SELECT COUNT(*) FROM returns WHERE ABS(restocking_fee_cad - ROUND(0.15 * net_sales_returned_cad, 2)) > 0.02
   OR ABS(refund_incl_gst_cad - ROUND(0.85 * net_sales_returned_cad * 1.05, 2)) > 0.02;

-- name: converted_consultations_link_to_orders
SELECT COUNT(*) FROM consultations c LEFT JOIN orders o ON o.order_id = c.order_id
WHERE (c.converted = 1 AND (o.order_id IS NULL OR o.consultation_id <> c.consultation_id OR o.sales_channel <> 'Design consultation')) OR (c.converted = 0 AND c.order_id IS NOT NULL);

-- name: consultation_orders_reference_consultation
SELECT COUNT(*) FROM orders WHERE sales_channel = 'Design consultation' AND order_date >= '2024-01-01' AND consultation_id IS NULL;

-- name: converted_leads_have_customers
SELECT COUNT(*) FROM leads WHERE (converted = 1 AND customer_id IS NULL) OR (converted = 0 AND customer_id IS NOT NULL);

-- name: fulfilment_record_per_active_order
SELECT (SELECT COUNT(*) FROM orders WHERE status <> 'Cancelled') - (SELECT COUNT(*) FROM fulfillment);

-- name: delivery_fees_not_retailer_revenue
SELECT COUNT(*) FROM fulfillment WHERE (fulfillment_method = 'Third-party delivery (customer-paid)' AND agent_delivery_fee_cad <> 0)
   OR (fulfillment_method = 'Retailer-arranged flat-rate delivery' AND agent_delivery_fee_cad <> 199) OR (fulfillment_method = 'Customer pickup' AND carrier_fee_customer_paid_cad <> 0);

-- name: purchase_order_dates_and_delay
SELECT COUNT(*) FROM purchase_orders WHERE (received_date IS NOT NULL AND received_date < order_date)
   OR (status = 'Received' AND delay_days <> CAST(julianday(received_date) - julianday(promised_date) AS INTEGER));

-- name: custom_lines_sourced_by_custom_po
SELECT COUNT(*) FROM sales_transactions s WHERE s.supply_source = 'Custom PO'
  AND NOT EXISTS (SELECT 1 FROM purchase_orders p WHERE p.order_line_id = s.line_id AND p.po_type = 'Custom');

-- name: opex_total_equals_components
SELECT COUNT(*) FROM operating_expenses WHERE ABS(total_opex_cad - (sales_wages_cad + sales_commission_cad + designer_compensation_cad + warehouse_wages_cad
  + management_admin_salaries_cad + rent_cad + cam_property_tax_cad + utilities_cad + marketing_cad + insurance_cad + admin_professional_cad + it_ecommerce_cad
  + warehouse_operations_cad + design_consult_materials_travel_cad + card_processing_fees_cad)) > 0.05;

-- name: marketing_detail_equals_opex_marketing
SELECT COUNT(*) FROM operating_expenses o JOIN (SELECT month, SUM(spend_cad) s FROM marketing_spend GROUP BY 1) m USING (month) WHERE ABS(o.marketing_cad - m.s) > 0.10;

-- name: customer_lifetime_sales_match_lines
SELECT COUNT(*) FROM customers c LEFT JOIN (SELECT customer_id, SUM(net_sales_cad) s FROM sales_transactions WHERE line_status <> 'Cancelled' GROUP BY 1) l USING (customer_id)
WHERE ABS(COALESCE(c.lifetime_net_sales_cad, 0) - COALESCE(l.s, 0)) > 0.05;

-- name: pre_period_records_only_for_opening_backlog
SELECT COUNT(*) FROM orders WHERE order_date < '2024-01-01' AND opening_backlog = 0;

-- name: transactions_within_period_or_backlog
SELECT COUNT(*) FROM sales_transactions WHERE transaction_date > '2026-09-30' OR (transaction_date < '2024-01-01' AND opening_backlog = 0);
