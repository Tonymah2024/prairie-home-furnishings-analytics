# Model evaluation

> Synthetic demonstration data — not actual company financial or operational records. Accuracy below is measured on synthetic data and does not demonstrate accuracy on any real retailer's transactions.

## Validation design
* **Time-based only**: models are trained on data up to an origin and evaluated after it (holdout Jan-Sep 2026 from origin 31-Dec-2025, plus rolling origins Jun-2025 and Sep-2025).
* **No leakage**: target values after the origin are masked before features are built; year-ago lag features only use pre-origin values; supplier-history features use receipts strictly before each order date; consultation features are those known at consultation time (follow-ups, which happen later, are excluded).
* **Right-censoring** (delays): open POs already more than 7 days past promise are labelled late; open POs not yet due are excluded.

## Model A - monthly written sales (bookings)
Selected: **SARIMAX** (lowest average of holdout WAPE and mean WAPE across all origins).

| target    | model          |   WAPE_holdout |   WAPE_mean_all_origins |   MAE_holdout |   RMSE_holdout |   bias_pct_holdout |   PI80_coverage_mean |
|:----------|:---------------|---------------:|------------------------:|--------------:|---------------:|-------------------:|---------------------:|
| net_sales | SARIMAX        |          0.038 |                   0.061 |       32537.6 |        43640.2 |              0.554 |                0.944 |
| net_sales | Seasonal naive |          0.058 |                   0.054 |       49587.7 |        64182.5 |              3.596 |                0.722 |
| net_sales | XGBoost        |          0.125 |                   0.197 |      108128   |       128729   |              8.333 |                0.333 |

## Model B - demand by category (units)
Selected model per category: Sofas & Sectionals: Seasonal naive, Dining: SARIMAX, Bedroom: XGBoost, Mattresses & Bases: SARIMAX, Living & Occasional: Seasonal naive, Décor & Lighting: Seasonal naive, Home Office: SARIMAX

| target              | model          |   WAPE_holdout |   WAPE_mean_all_origins |   MAE_holdout |   RMSE_holdout |   bias_pct_holdout |   PI80_coverage_mean |
|:--------------------|:---------------|---------------:|------------------------:|--------------:|---------------:|-------------------:|---------------------:|
| Bedroom             | SARIMAX        |          0.182 |                   0.193 |        20.721 |         27.559 |             -8.28  |                0.852 |
| Bedroom             | Seasonal naive |          0.21  |                   0.223 |        23.871 |         30.729 |            -11.713 |                0.759 |
| Bedroom             | XGBoost        |          0.13  |                   0.224 |        14.721 |         17.175 |             -6.392 |                0.296 |
| Dining              | SARIMAX        |          0.119 |                   0.218 |        27.069 |         36.022 |             -2.744 |                0.63  |
| Dining              | Seasonal naive |          0.151 |                   0.204 |        34.453 |         52.295 |             14.477 |                0.574 |
| Dining              | XGBoost        |          0.172 |                   0.332 |        39.066 |         46.546 |            -10.41  |                0.204 |
| Décor & Lighting    | SARIMAX        |          0.157 |                   0.102 |        28.665 |         37.764 |            -11.256 |                0.796 |
| Décor & Lighting    | Seasonal naive |          0.144 |                   0.105 |        26.286 |         32.918 |             -7.627 |                0.796 |
| Décor & Lighting    | XGBoost        |          0.184 |                   0.154 |        33.406 |         40.939 |             13.993 |                0.278 |
| Home Office         | SARIMAX        |          1.051 |                   0.725 |         3.97  |          5.189 |            103.751 |                0.407 |
| Home Office         | Seasonal naive |          1.824 |                   0.947 |         6.889 |          7.468 |            182.353 |                0.407 |
| Home Office         | XGBoost        |          8.102 |                   4.106 |        30.607 |         30.985 |            810.189 |                0     |
| Living & Occasional | SARIMAX        |          0.11  |                   0.17  |        12.696 |         16.144 |             -6.891 |                0.741 |
| Living & Occasional | Seasonal naive |          0.108 |                   0.135 |        12.512 |         16.213 |              2.898 |                0.889 |
| Living & Occasional | XGBoost        |          0.228 |                   0.217 |        26.353 |         30.573 |             18.427 |                0.185 |
| Mattresses & Bases  | SARIMAX        |          0.217 |                   0.165 |        13.097 |         15.586 |              2.602 |                0.889 |
| Mattresses & Bases  | Seasonal naive |          0.26  |                   0.199 |        15.717 |         18.822 |              9.291 |                0.648 |
| Mattresses & Bases  | XGBoost        |          0.377 |                   0.345 |        22.814 |         24.787 |             34.983 |                0.056 |
| Sofas & Sectionals  | SARIMAX        |          0.105 |                   0.138 |        10.675 |         11.941 |             -8.598 |                0.778 |
| Sofas & Sectionals  | Seasonal naive |          0.091 |                   0.113 |         9.252 |          9.609 |             -4.112 |                0.722 |
| Sofas & Sectionals  | XGBoost        |          0.251 |                   0.211 |        25.397 |         29.986 |             25.063 |                0.296 |

Home Office has very few units per month, so percentage errors are large and should not drive decisions.

## Model C - custom / special-order delay (> 7 days late)
Best: **Logistic regression**. Test = orders placed Jul-2025 to May-2026.

| model                                   |   AUC |   Brier |   LogLoss |   lift_top20pct |   base_rate |   n_test |
|:----------------------------------------|------:|--------:|----------:|----------------:|------------:|---------:|
| Baseline: supplier historical late rate | 0.594 |   0.178 |     0.546 |           1.361 |       0.238 |     1654 |
| Logistic regression                     | 0.627 |   0.174 |     0.526 |           1.527 |       0.238 |     1654 |
| XGBoost                                 | 0.609 |   0.178 |     0.536 |           1.387 |       0.238 |     1654 |

Delay-days regression: MAE baseline 7.3 days vs XGBoost 7.6 days.

Interpretation: lift over the supplier-history baseline is modest because simulated delays are largely random within supplier class and season; on real data, carrier, fabric availability and factory capacity signals would be added.

## Model D - design-consultation conversion propensity
Best: **Logistic regression**. Test = consultations Oct-2025 to mid-Aug-2026.

| model                                  |   AUC |   Brier |   LogLoss |   lift_top20pct |   base_rate |   n_test |
|:---------------------------------------|------:|--------:|----------:|----------------:|------------:|---------:|
| Baseline: designer x consult-type rate | 0.57  |   0.247 |     0.687 |           1.155 |       0.514 |      642 |
| Logistic regression                    | 0.591 |   0.243 |     0.68  |           1.383 |       0.514 |      642 |
| XGBoost                                | 0.562 |   0.254 |     0.703 |           1.216 |       0.514 |      642 |

Pipeline forecast: 62 open consultations, ~34 expected conversions and $248,457 expected sales (quote realisation ratio 1.02).

## Model E - cash flow and working capital
Integrated driver-based forecast (src/finance/forecast.py): bookings from Model A, recognition lags, deposits, inventory policy, supplier terms, GST/tax timing and debt; validated by balance-sheet and cash checks under 50 random assumption sets and by Excel recalculation.
