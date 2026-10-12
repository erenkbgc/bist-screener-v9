# Currency exposure across BIST stocks: pre-registration

Written and committed on 2026-10-12, **before** any return was computed for the portfolios below. The beta definition, portfolios, tests and pass rules are fixed here.

## Question

A common claim is that a weaker lira hurts importers and helps exporters, so stocks react to USDTRY in opposite directions. Two questions:

1. **X1, does the exposure persist?** Do stocks whose past returns moved most with USDTRY (high FX beta) still outperform low-FX-beta stocks in the months when the lira falls? If yes, the asymmetry is real and measurable in advance. It cannot be traded on its own, because the lira's direction would have to be predicted (`macro_drivers_preregistration.md`: not predictable).
2. **X2, does the market react late?** After a month in which the lira fell, do high-FX-beta stocks outperform in the **next** month? If yes, the market underreacts to what a currency move means for each company, and this can be traded: the FX move is known at month-end.

## Data

- **Monthly adjusted prices:** `monthly_prices.parquet`, from 2011-08.
- **Universe, fwd_ret_1m and sectors:** `factors_monthly.parquet` via `factor_backtest.prepare`. Non-financial stocks; the bottom 30% by liquidity is dropped.
- **USDTRY and XU100:** month-end values from `fx.parquet`.
- **Periods:** discovery before 2021-01-01, holdout after. The month is that of the portfolio's holding month t+1.

## FX beta (point-in-time)

At each month-end t, for each universe stock, using months t−35 … t:
- r_i = a + b_m · r_XU100 + b_fx · Δln USDTRY + e (OLS, TL log returns);
- at least 24 months are needed;
- b_fx is the stock's FX exposure beyond the market's own FX exposure.

**Portfolios:** each month t, universe stocks are sorted by b_fx into quintiles. S_{t+1} = EW `fwd_ret_1m` of the top quintile (Q5, high FX beta) − EW of the bottom quintile (Q1). This is gross, with no costs; it is a test of the relationship, not of a trading rule.

## Tests

Δfx_t is the log change of USDTRY in month t. The t-statistic is Newey-West (1 lag).

| ID | Regression | Expected |
|---|---|---|
| X1 | S_{t+1} = a + c · Δfx_{t+1} | c > 0 |
| X2 | S_{t+1} = a + d · Δfx_t | d > 0 |

**Pass rule (each test):**
- discovery: expected sign, t > 3.0;
- holdout: same sign, t > 2.0.

**Descriptive:**
- the unconditional mean of S;
- the mean b_fx by sector over the full sample (which sectors behave like "exporters");
- for X2, the mean S_{t+1} after the top-quartile Δfx months against the rest.

## What goes live

- **X2 passes:** a follow-up pre-registration tests a trading rule with costs: after a large lira fall, tilt toward high-FX-beta names. No live change from this test alone.
- **Only X1 passes:** each held name's FX beta is shown in the bulletin as information ("kur hassasiyeti").
- **Nothing passes:** nothing is shown.

## Known limits

- **Price-based exposure:** FX beta is estimated from prices, not from reported export shares or FX positions. Those are not available point-in-time.
- **Lira trend:** the lira fell in most months of the sample, so Δfx is mostly positive. X1 is identified mainly by the size of the fall, not by its direction.
- **Survivorship**, as in the other studies.
