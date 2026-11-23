# R0 with a market hedge (measurement, not a trial)

Date: 2026-11-24. Script: `scripts/report_hedged_r0.py`. Output: `data/reports/report_hedged_r0_2026-11-24.json`. Not in the trial ledger: nothing is selected or tuned on returns, and the live rule is not compared against it.

## Setup
- R0: the exact costed top-20% simulation (lag75 panel, 1M TL, next-close fills).
- Hedge: short BIST 100 total-return futures, synthetic. borsapy lists only live VIOP contracts, so there is no futures history. Futures excess return = XU100 TR - deposit rate. TR data start 2018-07; earlier months use price return + the mean dividend yield implied by 2018-07+.
- Basis risk is ignored. Roll and trading cost is 0.05%/month (assumption).
- Betas: fixed 1.0, and a 36-month rolling OLS beta using only past months. All windows start 2016-05 after the warm-up.
- Full-sample beta of R0 to the market: 0.99.

## Results (excess over TL deposit, mean %/yr, 2016-05+)

| Series | Full (t) | 2013-16* | 2017-20 | 2021-23 | 2024+ | Sharpe | Vol | Max DD (TL) |
|---|---|---|---|---|---|---|---|---|
| R0 unhedged | +26.9 (2.22) | +9.9 | +38.8 | +55.0 | -17.7 | 0.81 | 32.9% | -26.0% |
| R0 hedged, beta 1 | +13.6 (2.14) | +10.8 | +32.1 | +2.2 | -0.5 | 0.87 | 15.5% | -12.0% |
| R0 hedged, rolling beta | +13.2 (2.01) | +12.8 | +31.4 | +1.0 | -0.4 | 0.82 | 15.9% | -11.8% |
| BIST 100 TR | +12.7 (1.28) | -1.6 | +6.1 | +52.3 | -17.8 | 0.44 | 28.6% | -24.5% |

*2013-16 block holds only 2016-05..2016-12 after the warm-up.

## Reading
- The hedge halves volatility and drawdown. The Sharpe ratio barely changes (0.81 -> 0.87), so the hedge reshapes risk rather than adding return.
- What remains after the hedge is R0's return over the market. It sits almost entirely in 2016-2020. In 2021-23 and 2024+ it is about zero, matching the earlier finding of no alpha against BIST 100 TR in the holdout.
- A hedged R0 since 2021 would have earned roughly the TL deposit rate. The hedge is only worth adding if stock selection beats the index again, which the forward record has to show first.
- Not tested: real VIOP basis, margin and roll timing, and XU030 versus XU100 tracking. A trading decision needs real futures data.
