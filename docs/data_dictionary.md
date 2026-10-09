# Data dictionary

> Synthetic demonstration data — not actual company financial or operational records. Prairie Home Furnishings is fictional.

## `campaigns` (4 rows)

Marketing campaigns used for attribution.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| campaign_id | TEXT | PK |  | CMP-PARTNER |
| campaign_name | TEXT |  |  | Always-on search & shopping ads |
| spend_channel | TEXT |  |  | Google search ads |
| data_status | TEXT |  |  | SYNTHETIC |

## `consultations` (1,919 rows)

Free design consultations: designer, type, quotation, follow-ups, conversion, resulting order and revenue, estimated cost.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| consultation_id | TEXT | PK |  | DC-000006 |
| consultation_date | TEXT |  |  | 2023-09-02 |
| customer_id | TEXT |  | customers(customer_id) | CUST-000015 |
| designer_id | TEXT |  | staff(employee_id) | DSN-04 |
| consultation_type | TEXT |  |  | In-store design consult |
| rooms_in_scope | INTEGER |  |  | 1 |
| quotation_amount_cad | REAL |  |  | 11400.0 |
| follow_up_count | INTEGER |  |  | 2 |
| first_follow_up_days | REAL |  |  | 4.0 |
| designer_hours | REAL |  |  | 1.81 |
| converted | INTEGER |  |  | 1 |
| repeat_customer | INTEGER |  |  | 0 |
| estimated_conversion_cost_cad | REAL |  |  | 144.26 |
| recommended_categories | TEXT |  |  | Bedroom, Sofas & Sectionals |
| order_id | TEXT |  | orders(order_id) | ORD-000158 |
| conversion_date | TEXT |  |  | 2023-09-23 |
| pre_period | INTEGER |  |  | 1 |
| conversion_status | TEXT |  |  | Converted |
| final_sales_revenue_cad | REAL |  |  | 9061.5 |
| days_to_convert | REAL |  |  | 21.0 |
| data_status | TEXT |  |  | SYNTHETIC |

## `customers` (7,885 rows)

Fictional customers with type, acquisition channel, campaign and lifetime metrics derived from transactions.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| customer_id | TEXT | PK |  | CUST-000001 |
| customer_type | TEXT |  |  | Condo / apartment |
| acquisition_channel | TEXT |  |  | Social media & contests |
| created_date | TEXT |  |  | 2023-09-01 |
| postal_area | TEXT |  |  | Elsewhere in Alberta |
| first_order_date | TEXT |  |  | 2024-08-10 |
| last_order_date | TEXT |  |  | 2024-08-10 |
| orders | INTEGER |  |  | 1 |
| lifetime_net_sales_cad | REAL |  |  | 899.0 |
| lifetime_gross_profit_cad | REAL |  |  | 462.98 |
| repeat_customer | INTEGER |  |  | 0 |
| consultations | INTEGER |  |  | 0 |
| campaign_id | TEXT |  | campaigns(campaign_id) | CMP-SOCIAL |
| lead_conversion_status | TEXT |  |  | Converted |
| data_status | TEXT |  |  | SYNTHETIC (fictional, privacy-safe) |

## `fin_ap_subledger` (9,308 rows)

Payable open items.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| item_id | TEXT |  |  | OB-PO-000061 |
| account | TEXT |  |  | 2000 |
| counterparty | TEXT |  |  | SUP-07 |
| doc_date | TEXT |  |  | 2023-12-09 |
| due_date | TEXT |  |  | 2024-01-08 |
| amount | REAL |  |  | 3768.61 |
| data_status | TEXT |  |  | SIMULATED |

## `fin_ar_subledger` (12,058 rows)

Receivable open items.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| item_id | TEXT |  |  | OB-PAY-0001446 |
| account | TEXT |  |  | 1110 |
| counterparty | TEXT |  |  | Financing partner |
| doc_date | TEXT |  |  | 2023-12-29 |
| due_date | TEXT |  |  | 2024-01-01 |
| amount | REAL |  |  | 2248.39 |
| data_status | TEXT |  |  | SIMULATED |

## `fin_chart_of_accounts` (60 rows)

Chart of accounts.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| code | TEXT |  |  | 1000 |
| name | TEXT |  |  | Cash - operating account |
| type | TEXT |  |  | asset |
| normal_balance | TEXT |  |  | D |
| statement_line | TEXT |  |  | Cash |
| cash_flow_class | TEXT |  |  | cash |
| data_status | TEXT |  |  | SIMULATED |

## `fin_debt_treasury` (33 rows)

Debt, revolver, interest, tax and treasury schedule.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| month | TEXT |  |  | 2024-01 |
| prime_rate | REAL |  |  | 0.07200000000000001 |
| term_rate | REAL |  |  | 0.09200000000000001 |
| revolver_rate | REAL |  |  | 0.082 |
| term_interest | REAL |  |  | 3833.33 |
| revolver_interest | REAL |  |  | 0.0 |
| term_principal | REAL |  |  | 10416.67 |
| term_balance | REAL |  |  | 489583.33 |
| revolver_intramonth_draws | REAL |  |  | 0.0 |
| revolver_draw | REAL |  |  | 0.0 |
| revolver_repay | REAL |  |  | 0.0 |
| revolver_balance | REAL |  |  | 0.0 |
| dividend | REAL |  |  | 0.0 |
| month_end_cash | REAL |  |  | 721261.96 |
| min_daily_cash | REAL |  |  | 508122.71 |
| pbt_ytd | REAL |  |  | 83180.0 |
| tax_ytd | REAL |  |  | 9149.8 |
| loss_carryforward | REAL |  |  | 0.0 |
| data_status | TEXT |  |  | SIMULATED |

## `fin_fixed_assets` (7 rows)

Fixed-asset register.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| asset_id | TEXT |  |  | FA-001 |
| description | TEXT |  |  | Showroom leasehold improvements (60,000  |
| account | TEXT |  |  | 1500 |
| acquired | TEXT |  |  | 2019-01-15 |
| cost | REAL |  |  | 420000.0 |
| useful_life_months | INTEGER |  |  | 120 |
| accumulated_depreciation_31dec2023 | REAL |  |  | 207000.0 |
| accumulated_depreciation_30sep2026 | REAL |  |  | 322500.0 |
| net_book_value_30sep2026 | REAL |  |  | 97500.0 |
| data_status | TEXT |  |  | SIMULATED |

## `fin_general_ledger` (136,189 rows)

Double-entry general ledger lines (SIMULATED).

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| line_no | INTEGER |  |  | 1 |
| je_id | TEXT |  |  | OB-0000001 |
| date | TEXT |  |  | 2023-12-31 |
| account | TEXT |  |  | 1000 |
| debit | REAL |  |  | 650000.0 |
| credit | REAL |  |  | 0.0 |
| source | TEXT |  |  | Opening balance |
| reference | TEXT |  |  | OB-2023 |
| counterparty | TEXT |  |  | Lender |
| description | TEXT |  |  | Opening statement of financial position  |
| is_closing | INTEGER |  |  | 0 |
| amount | REAL |  |  | 650000.0 |
| month | TEXT |  |  | 2023-12 |
| account_name | TEXT |  |  | Cash - operating account |
| data_status | TEXT |  |  | SIMULATED |

## `fin_journal_entries` (40,842 rows)

Journal entry headers.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| je_id | TEXT |  |  | ADJ-0032602 |
| date | TEXT |  |  | 2024-01-25 |
| source | TEXT |  |  | Inventory |
| reference | TEXT |  |  | RET-00021 |
| description | TEXT |  |  | WRITE_OFF_DAMAGED |
| lines | INTEGER |  |  | 2 |
| total_debits | REAL |  |  | 865.76 |
| total_credits | REAL |  |  | 865.76 |
| data_status | TEXT |  |  | SIMULATED |

## `fin_trial_balance` (1,896 rows)

Monthly pre-closing trial balances.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| month | TEXT |  |  | 2023-12 |
| account | TEXT |  |  | 1000 |
| account_name | TEXT |  |  | Cash - operating account |
| type | TEXT |  |  | asset |
| debit | REAL |  |  | 650000.0 |
| credit | REAL |  |  | 0.0 |
| data_status | TEXT |  |  | SIMULATED |

## `fulfillment` (7,572 rows)

Fulfilment record per active order: readiness vs promise, delay category, hand-off wait reason, pickup / carrier, costs; carrier fees paid by customers are memo only.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| fulfillment_id | TEXT | PK |  | FUL-000158 |
| order_id | TEXT |  | orders(order_id) | ORD-000158 |
| order_type | TEXT |  |  | Custom |
| fulfillment_method | TEXT |  |  | Customer pickup |
| carrier | TEXT |  |  | Carrier A (fictional) |
| promised_ready_date | TEXT |  |  | 2023-11-16 |
| ready_date | TEXT |  |  | 2023-12-11 |
| requested_date | TEXT |  |  | 2024-01-13 |
| scheduled_date | TEXT |  |  | 2024-01-13 |
| fulfilled_date | TEXT |  |  | 2024-01-13 |
| status | TEXT |  |  | Fulfilled |
| warehouse_prep_days | REAL |  |  | 79.0 |
| supplier_delay_days | REAL |  |  | 26.0 |
| ready_delay_days | REAL |  |  | 25.0 |
| delay_category | TEXT |  |  | Supplier delay |
| pickup_capacity_wait_days | REAL |  |  | 0.0 |
| handoff_wait_days | REAL |  |  | 33.0 |
| handoff_wait_reason | TEXT |  |  | Customer requested storage |
| fulfillment_days | REAL |  |  | 112.0 |
| storage_hold | REAL |  |  | 1.0 |
| damage_flag | REAL |  |  | 0.0 |
| return_flag | INTEGER |  |  | 0 |
| retailer_fulfillment_cost_cad | REAL |  |  | 40.71 |
| carrier_fee_customer_paid_cad | REAL |  |  | 0.0 |
| agent_delivery_fee_cad | REAL |  |  | 0.0 |
| carrier_fee_note | TEXT |  |  | Paid by customer directly to carrier - n |
| data_status | TEXT |  |  | SYNTHETIC |

## `inventory_movements` (61,256 rows)

Perpetual inventory movements by state (stock / allocated to customer) with quantity and value; reconciles to product balances.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| movement_id | TEXT | PK |  | MV-0000001 |
| product_id | TEXT |  | products(product_id) | PRD-0001 |
| inventory_state | TEXT |  |  | allocated |
| quantity | INTEGER |  |  | 1 |
| value_cad | REAL |  |  | 1346.53 |
| unit_cost_cad | REAL |  |  | 1346.53 |
| movement_date | TEXT |  |  | 2024-01-01 |
| movement_type | TEXT |  |  | OPENING_BALANCE |
| reference_id | TEXT |  |  | OPENING-2024-01-01 |
| data_status | TEXT |  |  | SYNTHETIC |

## `leads` (29,642 rows)

Inquiries (search, social & contests, showroom, referral, online) with conversion status.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| lead_id | TEXT | PK |  | LEAD-000001 |
| lead_date | TEXT |  |  | 2024-01-01 |
| lead_channel | TEXT |  |  | Real-estate partner |
| customer_id | TEXT |  | customers(customer_id) | CUST-000929 |
| converted | INTEGER |  |  | 1 |
| conversion_date | TEXT |  |  | 2024-01-03 |
| lead_status | TEXT |  |  | Won |
| lead_source_detail | TEXT |  |  | Partner referral |
| data_status | TEXT |  |  | SYNTHETIC |

## `marketing_spend` (198 rows)

Monthly marketing spend by channel.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| month | TEXT |  |  | 2024-01-01 |
| marketing_channel | TEXT |  |  | Google search ads |
| spend_cad | REAL |  |  | 16082.22 |
| data_status | TEXT |  |  | SYNTHETIC |

## `operating_expenses` (33 rows)

Monthly operating expenses by category (simulated, assumption-driven).

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| month | TEXT | PK |  | 2024-01-01 |
| sales_wages_cad | REAL |  |  | 28204.8 |
| sales_commission_cad | REAL |  |  | 16096.0 |
| designer_compensation_cad | REAL |  |  | 25238.73 |
| warehouse_wages_cad | REAL |  |  | 19743.36 |
| management_admin_salaries_cad | REAL |  |  | 34465.0 |
| rent_cad | REAL |  |  | 44000.0 |
| cam_property_tax_cad | REAL |  |  | 9800.0 |
| utilities_cad | REAL |  |  | 11473.57 |
| marketing_cad | REAL |  |  | 48733.99 |
| insurance_cad | REAL |  |  | 5200.0 |
| admin_professional_cad | REAL |  |  | 7462.75 |
| it_ecommerce_cad | REAL |  |  | 3630.53 |
| warehouse_operations_cad | REAL |  |  | 3864.04 |
| design_consult_materials_travel_cad | REAL |  |  | 2625.0 |
| card_processing_fees_cad | REAL |  |  | 9652.03 |
| total_opex_cad | REAL |  |  | 270189.8 |
| data_status | TEXT |  |  | SYNTHETIC (assumption-driven) |

## `orders` (7,760 rows)

Order headers: channel, order type (Custom / Special order / In stock), deposits, balances, promised ready date, fulfilment method, status, cancellations.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| order_id | TEXT | PK |  | ORD-000158 |
| customer_id | TEXT |  | customers(customer_id) | CUST-000015 |
| order_date | TEXT |  |  | 2023-09-23 |
| sales_channel | TEXT |  |  | Design consultation |
| employee_id | TEXT |  | staff(employee_id) | DSN-04 |
| room_type | TEXT |  |  | Décor & lighting only |
| consultation_id | TEXT |  | consultations(consultation_id) | DC-000006 |
| order_type | TEXT |  |  | Custom |
| net_order_value_cad | REAL |  |  | 9061.5 |
| gst_cad | REAL |  |  | 453.08 |
| deposit_rate | REAL |  |  | 0.5 |
| tender | TEXT |  |  | Credit card |
| financed | INTEGER |  |  | 0 |
| trade_account | INTEGER |  |  | 0 |
| promised_ready_date | TEXT |  |  | 2023-11-16 |
| fulfillment_method | TEXT |  |  | Customer pickup |
| protection_plan_cad | REAL |  |  | 0.0 |
| agent_delivery_fee_cad | REAL |  |  | 0.0 |
| promotion_id | TEXT |  | promotions(promotion_id) | PRM-2023-BLAC11 |
| status | TEXT |  |  | Fulfilled |
| ready_date | TEXT |  |  | 2023-12-11 |
| scheduled_date | TEXT |  |  | 2024-01-13 |
| fulfilled_date | TEXT |  |  | 2024-01-13 |
| cancel_date | TEXT |  |  | 2024-01-06 |
| cancel_reason | TEXT |  |  | Supplier delay - customer cancelled |
| retained_cancellation_fee_cad | REAL |  |  | 0.0 |
| requested_date | TEXT |  |  | 2024-01-13 |
| storage_hold | REAL |  |  | 1.0 |
| carrier | TEXT |  |  | Carrier A (fictional) |
| damage_flag | REAL |  |  | 0.0 |
| retailer_fulfillment_cost_cad | REAL |  |  | 40.71 |
| carrier_fee_customer_paid_cad | REAL |  |  | 0.0 |
| opening_backlog | INTEGER |  |  | 1 |
| total_paid_incl_gst_cad | REAL |  |  | 9514.58 |
| order_total_incl_gst_cad | REAL |  |  | 9514.58 |
| deposit_required_cad | REAL |  |  | 4757.29 |
| deposit_paid_cad | REAL |  |  | 4757.29 |
| balance_outstanding_cad | REAL |  |  | 0.0 |
| fulfillment_days | REAL |  |  | 112.0 |
| ready_delay_days | REAL |  |  | 25.0 |
| handoff_wait_days | REAL |  |  | 33.0 |
| data_status | TEXT |  |  | SYNTHETIC |

## `payments` (15,090 rows)

Customer payments and refunds (deposits, balances before pickup, trade settlements); pre_period = received before 1-Jan-2024 for opening backlog orders.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| payment_id | TEXT | PK |  | PAY-0000232 |
| order_id | TEXT |  | orders(order_id) | ORD-000158 |
| payment_date | TEXT |  |  | 2023-09-23 |
| payment_type | TEXT |  |  | Deposit |
| tender | TEXT |  |  | Credit card |
| amount_incl_gst | REAL |  |  | 4757.29 |
| pre_period | INTEGER |  |  | 1 |
| data_status | TEXT |  |  | SYNTHETIC |

## `products` (350 rows)

Curated product catalogue (350 SKUs). Names, manufacturers and list prices from a public Calgary furniture catalogue; costs, margins, lead times SIMULATED.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| product_id | TEXT | PK |  | PRD-0001 |
| sku | TEXT |  |  | PHF-BED-0001 |
| product_name | TEXT |  |  | 2382-61 Queen Bed |
| manufacturer | TEXT |  |  | House collection (various makers) |
| category | TEXT |  |  | Bedroom |
| subcategory | TEXT |  |  | Beds |
| fulfillment_type | TEXT |  |  | Custom (made to order) |
| custom | INTEGER |  |  | 1 |
| made_in_canada | INTEGER |  |  | 0 |
| options | TEXT |  |  | Title |
| list_price_cad | REAL |  |  | 2199.0 |
| compare_at_cad | REAL |  |  | 2939.0 |
| unit_cost_cad | REAL |  |  | 1132.49 |
| assumed_margin | REAL |  |  | 0.485 |
| supplier_class | TEXT |  |  | Specialty importer |
| quoted_lead_days | INTEGER |  |  | 42 |
| handle | TEXT |  |  | 2382-61-queen-bed |
| supplier_id | TEXT |  | suppliers(supplier_id) | SUP-11 |
| reorder_point_current_policy | REAL |  |  | 2.0 |
| order_up_to_current_policy | REAL |  |  | 4.0 |
| on_hand_stock_units | INTEGER |  |  | 0 |
| allocated_to_customers_units | INTEGER |  |  | 1 |
| holding_cost_rate_annual | REAL |  |  | 0.22 |
| data_status | TEXT |  |  | List price VERIFIED from public catalogu |

## `promotions` (32 rows)

Promotional calendar (event name, dates, extra discount, scope).

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| promotion_id | TEXT | PK |  | PRM-2023-BLAC11 |
| promotion_name | TEXT |  |  | New Year Blowout |
| start_date | TEXT |  |  | 2023-01-02 |
| end_date | TEXT |  |  | 2023-01-20 |
| extra_discount_pct | REAL |  |  | 0.1 |
| scope | TEXT |  |  | All |
| data_status | TEXT |  |  | SYNTHETIC |

## `purchase_orders` (9,573 rows)

Supplier POs: stock replenishment, custom (made to order) and special orders with promised/received dates, delays and damage replacements.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| po_id | TEXT | PK |  | PO-000061 |
| po_type | TEXT |  |  | Custom |
| supplier_id | TEXT |  | suppliers(supplier_id) | SUP-07 |
| product_id | TEXT |  | products(product_id) | PRD-0333 |
| order_line_id | TEXT |  | sales_transactions(line_id) | LN-0000393 |
| order_date | TEXT |  |  | 2023-09-25 |
| promised_date | TEXT |  |  | 2023-11-13 |
| received_date | TEXT |  |  | 2023-12-09 |
| qty_ordered | INTEGER |  |  | 1 |
| qty_received | INTEGER |  |  | 1 |
| qty_damaged | INTEGER |  |  | 0 |
| unit_cost_cad | REAL |  |  | 3451.11 |
| status | TEXT |  |  | Received |
| delay_days | INTEGER |  |  | 26 |
| delay_reason | TEXT |  |  | Supplier production backlog |
| replacement_of | TEXT |  | purchase_orders(po_id) | PO-000677 |
| cancel_date | TEXT |  |  | 2024-02-11 |
| supplier_cancellation_fee_cad | REAL |  |  | 180.09 |
| pre_period | INTEGER |  |  | 1 |
| data_status | TEXT |  |  | SYNTHETIC |

## `returns` (219 rows)

In-stock returns within 3 days with 15% restocking fee.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| return_id | TEXT | PK |  | RET-00019 |
| line_id | TEXT |  | sales_transactions(line_id) | LN-0001366 |
| order_id | TEXT |  | orders(order_id) | ORD-000530 |
| return_date | TEXT |  |  | 2024-01-15 |
| units | INTEGER |  |  | 1 |
| net_sales_returned_cad | REAL |  |  | 259.0 |
| restocking_fee_cad | REAL |  |  | 38.85 |
| refund_incl_gst_cad | REAL |  |  | 231.16 |
| restocked | INTEGER |  |  | 1 |
| reason | TEXT |  |  | Comfort |
| data_status | TEXT |  |  | SYNTHETIC |

## `sales_transactions` (20,899 rows)

Order lines (written sales by order date): units, prices, configuration, discounts, net sales, COGS, gross profit, supply source, status.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| line_id | TEXT | PK |  | LN-0000390 |
| order_id | TEXT |  | orders(order_id) | ORD-000158 |
| transaction_date | TEXT |  |  | 2023-09-23 |
| customer_id | TEXT |  | customers(customer_id) | CUST-000015 |
| product_id | TEXT |  | products(product_id) | PRD-0001 |
| units | INTEGER |  |  | 1 |
| list_unit_price_cad | REAL |  |  | 269.0 |
| unit_price_cad | REAL |  |  | 269.0 |
| discount_pct | REAL |  |  | 0.1 |
| discount_reason | TEXT |  |  | Trade discount |
| gross_sales_cad | REAL |  |  | 269.0 |
| net_sales_cad | REAL |  |  | 242.1 |
| unit_cost_cad | REAL |  |  | 134.77 |
| material_variant | TEXT |  |  | Standard |
| configuration | TEXT |  |  | Standard |
| fulfillment_type | TEXT |  |  | Stocked (ready-made) |
| supply_source | TEXT |  |  | From stock |
| sales_channel | TEXT |  |  | Design consultation |
| employee_id | TEXT |  | staff(employee_id) | DSN-04 |
| promotion_id | TEXT |  | promotions(promotion_id) | PRM-2023-BLAC11 |
| consultation_id | TEXT |  | consultations(consultation_id) | DC-000006 |
| line_status | TEXT |  |  | Fulfilled |
| returned_units | INTEGER |  |  | 0 |
| received_date | TEXT |  |  | 2023-12-09 |
| category | TEXT |  |  | Décor & Lighting |
| subcategory | TEXT |  |  | Lighting |
| manufacturer | TEXT |  |  | Mercana |
| cogs_cad | REAL |  |  | 134.77 |
| gross_profit_cad | REAL |  |  | 107.33 |
| gross_margin_pct | REAL |  |  | 44.33 |
| opening_backlog | INTEGER |  |  | 1 |
| fulfilled_date | TEXT |  |  | 2024-01-13 |
| data_status | TEXT |  |  | SYNTHETIC |

## `staff` (13 rows)

Sales associates and interior designers (fictional IDs).

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| employee_id | TEXT | PK |  | DSN-01 |
| role | TEXT |  |  | Sales associate |
| start_date | TEXT |  |  | 2019-03-01 |
| end_date | TEXT |  |  | 2025-05-31 |
| data_status | TEXT |  |  | SYNTHETIC |

## `stockout_events` (886 rows)

Demand for ready-made SKUs lost because stock was unavailable and the customer declined a backorder.

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| stockout_id | TEXT | PK |  | SO-000085 |
| event_date | TEXT |  |  | 2024-01-02 |
| product_id | TEXT |  | products(product_id) | PRD-0321 |
| lost_units | INTEGER |  |  | 1 |
| lost_revenue_est_cad | REAL |  |  | 827.1 |
| data_status | TEXT |  |  | SYNTHETIC |

## `store_calendar` (1,004 rows)

Daily store-open calendar (closed Sundays, Alberta statutory holidays, Dec 25-26).

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| date | TEXT | PK |  | 2024-01-01 |
| store_open | INTEGER |  |  | 0 |

## `suppliers` (25 rows)

Manufacturers / distributors with supplier class, quoted lead time and payment terms (simulated).

| Column | Type | Key | References | Example |
|---|---|---|---|---|
| supplier_id | TEXT | PK |  | SUP-01 |
| supplier_name | TEXT |  |  | Amax |
| supplier_class | TEXT |  |  | North American case goods & upholstery |
| quoted_lead_days | INTEGER |  |  | 28 |
| payment_terms | TEXT |  |  | Net 30 |
| region | TEXT |  |  | North America / import |
| data_status | TEXT |  |  | SYNTHETIC (lead times & terms simulated) |
