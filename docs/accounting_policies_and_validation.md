# Accounting policies and financial validation

> SIMULATED FINANCIAL INFORMATION - synthetic demonstration accounts of a fictional retailer, not actual company records.

## Policies
Chart of accounts and documented accounting policies for the SIMULATED accounts of the fictional retailer
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

## Key parameters
* GST 5%; income tax 11% on the first $500,000, 23% above; Prior-year balance paid on 31 March (no instalments modelled).
* Financing-partner fee 6%; protection-plan commission 40%; freight-in 4% of receipts; supplier terms Net 30.
* Term loan $500,000 at 31-Dec-2023, 48 monthly instalments, prime + 2.00%; revolver $750,000.
* Opening position: cash $650,000, share capital $250,000; opening retained earnings = residual of the explicit opening balances.
* Dividend: 50% of fiscal-year net income if cash stays above $500,000.

## Validation results
| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | General ledger balances: total debits = total credits (every journal entry) | PASS | 40,842 journal entries / 136,189 lines; debits $177,224,863.54 = credits $177,224,863.54; unbalanced entries: 0 |
| 2 | Trial balances balance; AR, AP and customer-deposit sub-ledgers equal their control accounts | PASS | 34 monthly trial balances; max sub-ledger difference: AP $0.00, AR $0.00, Customer deposits $0.00 |
| 3 | Accounting equation: assets = liabilities + equity (every month-end, opening and forecast) | PASS | Historical max |A-L-E| $0.00; opening $0.00; forecast (3 scenarios) $0.000000 |
| 4 | Retained-earnings movements: opening + net income - dividends = closing; current-year earnings = YTD net income | PASS | FY2024: 138,578 + 451,095 -225,000 = 364,674; FY2025: + 585,437 -292,000 = 658,111; YTD-2026 earnings 569,840 |
| 5 | Cash-flow reconciliation: ending cash = balance-sheet cash (monthly, quarterly, annual, forecast); direct = indirect | PASS | Indirect-method ending cash ties every period; direct-method net change matches every month |
| 6 | Inventory: GL stocked (1200) and customer-allocated (1210) balances equal the movement records | PASS | Month-end values reconcile for both states (max difference $0.00); stocked $505,080, allocated $279,846 at 30-Sep-2026 |
| 7 | Revenue, discounts, returns, fees and COGS reconcile to order, return, cancellation and movement records; bookings-to-revenue bridge has no residual | PASS | 14 lines x 33 months; residual of written-sales-to-revenue bridge $0.00 |
| 8 | Customer deposits (contract liabilities) equal deposits held on open orders; delivery fees paid to carriers never recorded as revenue | PASS | Deposits $495,984 at 30-Sep-2026 tie to the open-order register every month; agent collections held in 2360/2370 only |
| 9 | No balancing plugs | PASS | No suspense/plug accounts; every line comes from a documented journal source; every balance-sheet account maps to one cash-flow line; opening retained earnings is the documented residual of the explicit opening position; forecast has no circular references |
| 10 | Forecasts remain integrated when assumptions change (Python and Excel) | PASS | 50 random assumption sets: max |A-L-E| or |cash difference| $0.000000; Excel recalculation (Base; Conservative; Custom): max |Excel - Python| $0.000000, Excel checks TRUE = True |
| 11 | All synthetic financial information is labelled | PASS | 31 financial CSV tables carry data_status; 43 workbook sheets carry the SIMULATED banner; 5 HTML/PDF reports labelled |
