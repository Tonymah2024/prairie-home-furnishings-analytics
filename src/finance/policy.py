"""Chart of accounts and documented accounting policies for the SIMULATED accounts of the fictional retailer
Prairie Home Furnishings Ltd. (a stand-alone Alberta corporation). Every figure is synthetic.

Revenue recognition (IFRS 15 / ASPE 3400 principles, simplified):
  * Furniture revenue is recognised when control passes to the customer: at in-store pickup, or when the goods are
    handed to the customer's own delivery carrier at the loading dock. Order date is NOT the revenue date.
  * Deposits and balances received before hand-off are CONTRACT LIABILITIES (customer deposits), held gross of GST;
    GST is accounted for when the deposit is applied at completion (Excise Tax Act treatment of deposits).
  * Third-party delivery is contracted and paid by the customer directly -> never retailer revenue.
    Flat-rate delivery collected for a partner carrier, and Guardsman-style protection plans, are collected as AGENT:
    only the retailer's plan commission is revenue; the rest is a liability remitted to the carrier / insurer.
  * Retained cancellation fees (custom orders already in production) and 15% restocking fees are other revenue.
Inventory: perpetual, at purchase cost (standard cost for stocked SKUs; actual PO cost for custom pieces).
  Stocked goods = 1200; goods reserved for / received for specific customers = 1210 (reclassified when allocated).
"""
from __future__ import annotations

FIN_LABEL = "SIMULATED FINANCIAL INFORMATION - synthetic demonstration accounts of a fictional retailer, not actual company records"

COA = [  # code, name, type, normal, statement line, cash-flow class
    ("1000", "Cash - operating account", "asset", "D", "Cash", "cash"),
    ("1100", "Card & debit processor receivable", "asset", "D", "Receivables", "op_wc"),
    ("1110", "Financing-partner receivable", "asset", "D", "Receivables", "op_wc"),
    ("1120", "Trade receivables - designer & business accounts", "asset", "D", "Receivables", "op_wc"),
    ("1200", "Inventory - stocked merchandise", "asset", "D", "Inventory", "op_wc"),
    ("1210", "Inventory - allocated to customer orders (custom & reserved)", "asset", "D", "Inventory", "op_wc"),
    ("1300", "Prepaid expenses", "asset", "D", "Prepaid expenses", "op_wc"),
    ("1400", "GST input tax credits", "asset", "D", "Sales tax", "op_wc"),
    ("1500", "Leasehold improvements", "asset", "D", "Fixed assets", "ppe"),
    ("1510", "Warehouse equipment & forklifts", "asset", "D", "Fixed assets", "ppe"),
    ("1520", "Showroom fixtures, POS & IT", "asset", "D", "Fixed assets", "ppe"),
    ("1590", "Accumulated depreciation", "contra_asset", "C", "Accumulated depreciation", "accdep"),
    ("2000", "Accounts payable - suppliers", "liability", "C", "Accounts payable", "op_wc"),
    ("2010", "Accounts payable - operating vendors", "liability", "C", "Accounts payable", "op_wc"),
    ("2100", "Accrued payroll & commissions", "liability", "C", "Accrued liabilities", "op_wc"),
    ("2300", "GST collected", "liability", "C", "Sales tax", "op_wc"),
    ("2350", "Customer deposits (contract liabilities)", "liability", "C", "Customer deposits", "op_wc"),
    ("2360", "Delivery fees collected for partner carrier (agent)", "liability", "C", "Agent liabilities", "op_wc"),
    ("2370", "Protection-plan premiums payable to insurer (agent)", "liability", "C", "Agent liabilities", "op_wc"),
    ("2400", "Income tax payable", "liability", "C", "Income tax payable", "op_wc"),
    ("2600", "Revolving operating line of credit", "liability", "C", "Revolver", "fin_rev"),
    ("2700", "Term loan", "liability", "C", "Term loan", "fin_term"),
    ("3000", "Share capital", "equity", "C", "Share capital", "equity"),
    ("3200", "Retained earnings", "equity", "C", "Retained earnings", "re"),
    ("3300", "Dividends declared", "equity", "D", "Retained earnings", "equity"),
    ("4000", "Sales - sofas & sectionals", "revenue", "C", "Gross furniture sales", "pnl"),
    ("4010", "Sales - bedroom", "revenue", "C", "Gross furniture sales", "pnl"),
    ("4020", "Sales - mattresses & bases", "revenue", "C", "Gross furniture sales", "pnl"),
    ("4030", "Sales - dining", "revenue", "C", "Gross furniture sales", "pnl"),
    ("4040", "Sales - living & occasional", "revenue", "C", "Gross furniture sales", "pnl"),
    ("4050", "Sales - home office", "revenue", "C", "Gross furniture sales", "pnl"),
    ("4060", "Sales - décor & lighting", "revenue", "C", "Gross furniture sales", "pnl"),
    ("4100", "Protection-plan commissions (net, agent)", "revenue", "C", "Other revenue", "pnl"),
    ("4200", "Restocking fees", "revenue", "C", "Other revenue", "pnl"),
    ("4300", "Retained cancellation fees", "revenue", "C", "Other revenue", "pnl"),
    ("4900", "Discounts & promotional allowances", "contra_revenue", "D", "Discounts", "pnl"),
    ("4910", "Sales returns", "contra_revenue", "D", "Returns", "pnl"),
    ("5000", "Cost of goods sold - merchandise", "cogs", "D", "Cost of goods sold", "pnl"),
    ("5100", "Inventory variances, shrinkage & write-offs", "cogs", "D", "Cost of goods sold", "pnl"),
    ("5200", "Freight-in & supplier charges", "cogs", "D", "Cost of goods sold", "pnl"),
    ("6000", "Wages - sales associates", "opex", "D", "Employee compensation", "pnl"),
    ("6010", "Sales commissions", "opex", "D", "Employee compensation", "pnl"),
    ("6020", "Interior designer compensation", "opex", "D", "Employee compensation", "pnl"),
    ("6030", "Wages - warehouse", "opex", "D", "Employee compensation", "pnl"),
    ("6040", "Salaries - management & administration", "opex", "D", "Employee compensation", "pnl"),
    ("6100", "Rent", "opex", "D", "Occupancy", "pnl"),
    ("6105", "Common-area & property tax charges", "opex", "D", "Occupancy", "pnl"),
    ("6110", "Utilities", "opex", "D", "Occupancy", "pnl"),
    ("6200", "Marketing & advertising", "opex", "D", "Marketing", "pnl"),
    ("6300", "Insurance", "opex", "D", "General & administrative", "pnl"),
    ("6310", "Administrative & professional fees", "opex", "D", "General & administrative", "pnl"),
    ("6320", "IT & e-commerce platform", "opex", "D", "General & administrative", "pnl"),
    ("6400", "Warehouse & fulfilment operations", "opex", "D", "Warehouse & fulfilment", "pnl"),
    ("6410", "Design consultation materials & travel", "opex", "D", "Warehouse & fulfilment", "pnl"),
    ("6420", "Card processing fees", "opex", "D", "Merchant & financing fees", "pnl"),
    ("6430", "Financing-partner merchant fees", "opex", "D", "Merchant & financing fees", "pnl"),
    ("6900", "Depreciation", "opex", "D", "Depreciation", "pnl"),
    ("7000", "Interest - term loan", "other_exp", "D", "Interest", "pnl"),
    ("7010", "Interest - revolving line", "other_exp", "D", "Interest", "pnl"),
    ("8000", "Income tax expense", "tax", "D", "Income taxes", "pnl"),
]
ACCOUNTS = {c[0]: dict(zip(["code", "name", "type", "normal", "line", "cf"], c)) for c in COA}
PNL_TYPES = {"revenue", "contra_revenue", "cogs", "opex", "other_exp", "tax"}
REV_ACCT = {"Sofas & Sectionals": "4000", "Bedroom": "4010", "Mattresses & Bases": "4020", "Dining": "4030", "Living & Occasional": "4040",
            "Home Office": "4050", "Décor & Lighting": "4060"}

GST_RATE = 0.05
SETTLEMENT = {"Credit card": ("1100", 2), "Debit": ("1100", 1), "Financing partner": ("1110", 3), "E-transfer": ("1000", 0), "Cash": ("1000", 0),
              "Trade account": ("1000", 0)}        # trade deposits are paid by e-transfer; trade balances are invoiced (1120)
FIN_PARTNER_FEE = 0.06
PLAN_COMMISSION = 0.40
SUPPLIER_TERMS_DAYS = 30
FREIGHT_IN_RATE = 0.04
OPEX_PAY_DAY = 20
PAYROLL_FIRST_HALF = 0.50
TAX_SMALL_RATE, TAX_GENERAL_RATE, SMALL_BUSINESS_LIMIT = 0.11, 0.23, 500000.0   # Alberta CCPC: 9% + 2% on first $500K, 15% + 8% above
TAX_PAYMENT = "Prior-year balance paid on 31 March (no instalments modelled)"
GST_TAXABLE_OPEX = {"6100", "6105", "6110", "6200", "6310", "6320", "6400", "6410"}
OPEX_MAP = [  # operating_expenses column, account, vendor, kind (payroll | rent | prepaid | vendor)
    ("sales_wages_cad", "6000", None, "payroll"), ("sales_commission_cad", "6010", None, "payroll"), ("designer_compensation_cad", "6020", None, "payroll"),
    ("warehouse_wages_cad", "6030", None, "payroll"), ("management_admin_salaries_cad", "6040", None, "payroll"),
    ("rent_cad", "6100", "Landlord", "rent"), ("cam_property_tax_cad", "6105", "Landlord", "rent"),
    ("utilities_cad", "6110", "VEN-UTIL Utility provider", "vendor"), ("marketing_cad", "6200", "VEN-MKTG Media & advertising vendors", "vendor"),
    ("insurance_cad", "6300", "Insurer", "prepaid"), ("admin_professional_cad", "6310", "VEN-ADM Professional & office vendors", "vendor"),
    ("it_ecommerce_cad", "6320", "VEN-IT IT & e-commerce vendors", "vendor"), ("warehouse_operations_cad", "6400", "VEN-WHS Warehouse & handling vendors", "vendor"),
    ("design_consult_materials_travel_cad", "6410", "VEN-DSN Design materials & travel", "vendor"), ("card_processing_fees_cad", "6420", "VEN-PAY Payment processors", "vendor"),
]
FIXED_ASSETS = [  # asset_id, description, account, acquired, cost, life (months), accumulated depreciation at 31 Dec 2023
    ("FA-001", "Showroom leasehold improvements (60,000 sq ft)", "1500", "2019-01-15", 420000.0, 120, 207000.0),
    ("FA-002", "Warehouse racking, forklifts & loading dock", "1510", "2019-06-01", 145000.0, 84, 93000.0),
    ("FA-003", "Showroom fixtures, POS & IT", "1520", "2021-03-01", 160000.0, 60, 90000.0),
    ("FA-004", "Showroom refresh & vignette rooms", "1500", "2024-05-06", 85000.0, 120, 0.0),
    ("FA-005", "Second forklift & pallet racking", "1510", "2025-03-03", 48000.0, 84, 0.0),
    ("FA-006", "POS, e-commerce & order-management upgrade", "1520", "2025-09-02", 36000.0, 36, 0.0),
    ("FA-007", "Loading-dock pickup bay improvements", "1500", "2026-04-06", 28000.0, 120, 0.0),
]
TERM_LOAN = dict(balance_open=500000.0, months_remaining=48, spread=0.0200)
PRIME_SPREAD_OVER_POLICY = 0.0220
REVOLVER = dict(limit=750000.0, spread=0.0100, min_cash=150000.0, target_cash=250000.0, repay_above=400000.0, step=5000.0,
                intramonth_floor=40000.0, intramonth_target=120000.0)
DIVIDEND = dict(payout=0.50, cash_floor=500000.0)   # year-end dividend: 50% of FY net income, only if cash stays above the floor and the revolver is nil
OPENING = dict(date="2023-12-31", cash=650000.0, share_capital=250000.0)
