# What moves BIST: pre-registration

Written and committed on 2026-10-10, **before** any of the regressions below were run. The variables, horizons, thresholds and pass rules are fixed here and not changed after the results are seen. A change after that point counts as a new test and gets a new pre-registration.

## Question

The question "what makes BIST go up or down" covers two different things, and they are tested separately:

- **A. Explanation (same month).** Which variables move together with BIST in the same month, and how much of the variance do they explain? This says what BIST is *exposed to*. It does not give a trading signal, because the explanatory variables are only known at the end of the same month.
- **B. Prediction (next month / next 12 months).** Does any variable known at month-end *t* predict BIST returns after *t*, out of sample? Only this can be used for timing.

A statistical test can't "prove" a cause. A pass here means the relationship is large, stable across sub-periods and survives a multiple-testing correction. A fail means no evidence; it does not prove the variable has no effect.

## Data (monthly, month-end)

| Series | Source | Start |
|---|---|---|
| XU100 price index (TL) | yfinance `XU100.IS`; checked against borsapy `Index("XU100")` (2020 redenomination already rescaled in both) | 1997 |
| USDTRY | yfinance `USDTRY=X` | 2005 |
| MSCI EM (USD) | yfinance `EEM` (ETF, total return) | 2003 |
| S&P 500, VIX, US 10y yield, DXY | yfinance `^GSPC`, `^VIX`, `^TNX`, `DX-Y.NYB` | 1990 |
| Brent, gold | yfinance `BZ=F`, `GC=F` | 2007 / 2000 |
| CPI yoy, CPI mom | borsapy `Inflation().tufe()` (TÜİK) | 2005 |
| CBRT policy rate | borsapy `TCMB().history` | 2010 |

The sample is 2005-01 to 2026-09 for everything that does not need the policy rate, and 2010-06 onwards for the policy-rate variables.

**Dependent variable:** `r_usd` = monthly log return of XU100 / USDTRY, i.e. BIST measured in USD. The identity `r_tl = r_usd + Δln USDTRY` is reported to show how much of the nominal TL rise is just the currency.

## Part A: explanation (contemporaneous)

Regressors, all in month *t*:

| ID | Variable | Expected sign | Source of the hypothesis |
|---|---|---|---|
| A1 | EEM log return | + | global EM risk appetite (Bekaert & Harvey 1997) |
| A2 | Δ ln VIX | − | global risk aversion |
| A3 | Δ US 10y yield | − | global discount rate / dollar funding |
| A4 | DXY log return | − | dollar strength drains EM flows |
| A5 | Brent log return | − | Turkey is a net oil importer (current account) |
| A6 | Gold log return (USD) | ? | safe-haven substitute for local savers |
| A7 | Δ CPI yoy (pp) | − | inflation shock |
| A8 | Δ real policy rate (policy − CPI yoy, pp) | ? | tighter real rates: TL support vs higher discount rate |

**Method**
- Multivariate OLS with Newey-West standard errors (3 lags) for the full sample. A7–A8 regressions use the shorter sample.
- Relative importance: Shapley (LMG) decomposition of R² over the regressors.
- Stability: rolling 36-month betas, and the full regression in two halves: 2005–2015 and 2016–2026.

**A "driver" passes when all of these hold:**
1. Full sample: |t| > 3.0 (Harvey-Liu-Zhu). This is also above the Bonferroni level for 8 tests (≈ 2.73).
2. The coefficient has the same sign in both halves.

## Part B: prediction (out of sample)

Predictors, all known at the end of month *t*:

| ID | Predictor | Source of the hypothesis |
|---|---|---|
| P1 | Real policy rate level (policy − CPI yoy) | rate-differential / carry |
| P2 | 3-month change in real policy rate | monetary-policy shock |
| P3 | 12-month USDTRY log change | currency momentum / crisis |
| P4 | Trend: ln(XU100_usd / 10-month SMA) | Faber (2007); Moskowitz-Ooi-Pedersen (2012) |
| P5 | 12-month XU100 USD log return | time-series momentum |
| P6 | Market earnings yield: median E/P of the research panel minus CPI yoy | Campbell & Shiller (1988), Fed-model analogue |
| P7 | VIX level (log) | Bollerslev, Tauchen & Zhou (2009) |
| P8 | 12-month EEM log return | global momentum |
| P9 | 12-month change in CPI yoy | inflation trend |

Targets: `r_usd` for month *t+1* (h = 1) and the sum over *t+1..t+12* (h = 12).

**Method**
- Univariate predictive regressions.
- In-sample: Newey-West t with h + 2 lags.
- Out of sample: expanding window. The first forecast uses at least 84 months of data (forecasting begins about 2012 for 2005-start series and about 2017 for 2010-start series). The benchmark is the historical mean.
  - Statistic: OOS R² (Campbell & Thompson 2008), tested with Clark & West (2007) MSFE-adjusted *t*.
  - For h = 12, the Clark-West *t* uses Newey-West with 12 lags.

**A predictor passes when all of these hold:**
1. OOS R² > 0.
2. Clark-West one-sided p < 0.05 / 18 (Bonferroni over 9 predictors × 2 horizons ≈ 0.0028).
3. In-sample Newey-West |t| > 3.0.

**Information only (not part of the pass rule):** the P4 trend rule as a strategy. Hold XU100 in USD when P4 > 0, otherwise hold USD cash. Costs are 0.2% per switch. Reported: Sharpe ratio, maximum drawdown, and the same for buy and hold.

## What follows from the result

- **Part A passes** are reported as BIST's main exposures, with their share of R². This goes into the docs and the regime monitor as an explanation only, not as a signal.
- **A Part B pass** makes that predictor a candidate input for Phase 3, the market trend filter / risk reduction. It still needs its own portfolio test there.
- **If no Part B predictor passes,** the conclusion is "BIST's direction is not predictable with these variables". The live regime forecast (`core/trend_forecaster.py`) should then not be used to change scoring weights.

## Known limits

- **XU100 is a price index without dividends,** so returns are understated by roughly the dividend yield. This does not change betas or prediction tests much.
- **About 260 monthly observations.** Power is limited, and regime changes (2018 currency crisis, 2021–23 unorthodox policy) can dominate.
- **Missing variables.** Turkey 5y CDS, foreign ownership flows and the CBRT reserve series are not in free data, so they are not tested. CDS is probably one of the strongest contemporaneous variables. Its absence means part of the unexplained variance belongs to it.
- **The policy rate in 2021–23 did not reflect the effective funding rate,** because of unorthodox tools. P1/P2/A8 are measured with this noise.
- **Monthly CPI is published in the first days of the next month.** To avoid look-ahead, every Part B predictor that uses CPI (P1, P2, P6, P9) uses CPI lagged by one month, i.e. the last print available at the end of month *t*.

---

## Results (added 2026-10-10, after the run; the sections above are unchanged)

`python scripts/research_macro_drivers.py --refresh`. The full output is in `data/reports/research_macro_drivers_2026-10-10.json`.

**Sample**
- Months run to 2026-09-30. The incomplete October 2026 month was excluded (data hygiene, decided before the results were read).
- The global regression starts in 2007-09 because Brent only exists from then: n = 230.
- The policy-rate regressions start in 2010: n = 196.
- The last policy-rate decision in the borsapy feed is 2026-01-23. Any later decisions are missing and the value is forward-filled.

### 1. Where the nominal TL rise comes from (2005-02 → 2026-09)

| | Annualised |
|---|---|
| XU100 in TL | +19.0% |
| USDTRY | +18.1% |
| XU100 in USD | **+0.8%** |

- Over 21 years almost all of the nominal TL rise of BIST is the currency. In USD, the price index has been roughly flat; dividends are not included.
- The monthly USD part and the currency part are negatively correlated (−0.67): when the lira falls, BIST in USD also falls.
- As a result, the TL index is *less* volatile than its USD part: TL-variance / USD-variance ≈ 1 / 1.68. In TL terms, BIST works as a partial currency hedge.

### 2. Part A: what moves BIST in the same month (USD returns)

| ID | Variable | β | NW t | Shapley R² | t in halves | Pass |
|---|---|---|---|---|---|---|
| A1 | MSCI EM (EEM) | +0.98 | +6.66 | 0.215 | +6.79 / +3.90 | **yes** |
| A2 | Δ ln VIX | −0.00 | −0.16 | 0.038 | +0.21 / −0.24 | no |
| A3 | Δ US 10y | +0.04 | +1.24 | 0.014 | −0.23 / +1.85 | no |
| A4 | DXY | +0.20 | +0.57 | 0.039 | +0.92 / −0.31 | no |
| A5 | Brent | +0.02 | +0.37 | 0.023 | −0.88 / +1.03 | no |
| A6 | Gold | −0.01 | −0.10 | 0.007 | −0.77 / +1.26 | no |

- The 2007–2026 regression has R² = 0.34 (first half 0.53, second half 0.20).
- The 2010+ regression adds A7 Δ CPI yoy (t = +0.38) and A8 Δ real policy rate (t = −0.36); neither passes. EEM still passes there (β = +0.75, t = +4.35), and R² = 0.23.

**Reading**
- **The only robust same-month driver is global EM risk appetite:** BIST moves roughly 1:1 with MSCI EM in USD.
- VIX, the dollar index, oil and US yields add nothing once EM is included; their effect runs through EM.
- **About two thirds of the monthly variance is not explained by any tested variable,** and that share grew after 2016 (R² fell from 0.53 to 0.20). This is the Turkey-specific part: politics, policy surprises, sovereign risk. Turkey CDS, which was not available, is the obvious candidate. The CPI and policy-rate variables do not capture it month by month.

### 3. Part B: can BIST's direction be predicted? (USD, out of sample)

Bonferroni α = 0.0028 (18 tests). To pass, a predictor needs all three: OOS R² > 0, Clark-West p < α, and in-sample |t| > 3.

| ID | Predictor | h | In-sample t | OOS R² | CW p | Pass |
|---|---|---|---|---|---|---|
| P1 | real policy rate | 12 | −3.45 | −29.7% | 0.091 | no |
| P3 | 12m USDTRY change | 1 | +2.51 | +2.3% | 0.048 | no |
| P3 | 12m USDTRY change | 12 | +3.74 | −58.2% | 0.186 | no |
| P4 | 10-month trend | 12 | −3.57 | +1.9% | 0.015 | no |
| P7 | VIX level | 12 | +1.85 | +14.8% | **0.0021** | no (in-sample t) |
| P8 | 12m EEM return | 12 | −3.19 | +13.4% | 0.041 | no |
| all other predictor / horizon pairs | | | | ≤ +0.7% | > 0.12 | no |

**Conclusion: no predictor passes.** With these variables, BIST's direction in USD is not predictable out of sample. As pre-registered:
- The live regime forecast (`core/trend_forecaster.py`) should not change scoring weights.
- Phase 3 should not add a market-timing filter on the basis of these variables.

**Near misses (not results; would need a new pre-registration and forward tracking)**
- High VIX predicted higher 12-month BIST returns out of sample: OOS R² +14.8%, CW p = 0.0021. This fits the variance-risk-premium literature. The in-sample t was only 1.85, and the overlapping 12-month windows mean there are only about 12 independent observations.
- Several 12-month predictors (real rate, 10-month trend, momentum, EEM momentum) have negative in-sample slopes. That points to multi-year *mean reversion* in BIST USD prices, not momentum. They fail out of sample.

### 4. 10-month trend rule (information only)

From 2005-10 to 2026-09, the rule was invested 50% of the time with 47 switches.

| | Annual return (USD) | Volatility | Sharpe | Max drawdown |
|---|---|---|---|---|
| Trend rule | −0.5% | 23.5% | −0.02 | −72% |
| Buy and hold | +0.1% | 35.9% | 0.00 | −73% |

The trend rule halves the time in the market and cuts volatility. It does **not** reduce the maximum drawdown and does not add return. The Faber (2007) result is not reproduced on BIST in USD.
