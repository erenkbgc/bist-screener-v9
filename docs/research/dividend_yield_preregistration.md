# Dividend yield factor: pre-registration

Written and committed on 2026-10-12, **before** any dividend data was joined to returns. The definition, portfolios, tests and pass rules are fixed here.

## Question

Do high-dividend BIST stocks earn more than the universe? Does dividend yield add to the live value rule?

**Prior:**
- In US data, dividend yield is a weak value proxy once other valuation ratios are included (Fama & French 1993, 2015).
- Payers and non-payers differ in risk and quality.
- In this project, value_sn (E/P, B/M, S/P, EBIT/EV) already ranks stocks (`long_term_preregistration.md`). Dividend yield may add little.

## Data

- **Dividends:** `borsapy.Ticker(t).dividends` (İş Yatırım). One row per ex-date with `TotalDividend`, the total cash paid in TL. These are cash dividends only.
- **Panel:** `factors_monthly.parquet`, which supplies the universe, `mcap`, `fwd_ret_1m` and `value_sn` via `research_long_term.load()`. The universe is non-financial, with the bottom 30% by liquidity dropped (base B).
- **Periods:** discovery to 2020-12, holdout 2021-01 onward.

## Definition

At month-end t:
- **dy** = sum of `TotalDividend` over ex-dates in (t − 365 days, t], divided by `mcap` at t.
- A stock with no ex-date in that window has dy = 0.
- A stock whose ticker returns no dividend data at all (fetch error) is dropped. It is not counted as dy = 0.

Using totals over market value avoids per-share adjustments for bonus issues.

## Tests

Each is a monthly series with Newey-West t (1 lag), net of 20 bps per unit of turnover as in `backtest_factor_model.spread_stats`.

| ID | Test | Expected |
|---|---|---|
| Y1 | Top quintile of dy among payers (dy > 0) minus the EW universe | + |
| Y2 | All payers minus all non-payers, EW | + |
| Y3 | Composite (value_sn_z + dy_z) / 2, top quintile, minus value_sn top quintile. dy_z is the winsorised cross-sectional z of dy, with non-payers set to the minimum. | + |

Y3 is the decision-relevant test: should the live rule add dividend yield?

## Pass rule (each test)

There are 3 tests:
1. Discovery: expected sign, t > 3.0 (Harvey-Liu-Zhu; above Bonferroni ≈ 2.39 for 3).
2. Holdout: same sign, t > 2.0.

## What goes live

- **Y3 passes:** a new pre-registration is needed to change the live rule. The composite would replace value_sn only after a portfolio backtest with costs (as in `portfolio_backtest_preregistration.md`).
- **Only Y1 or Y2 passes:** the dividend yield of each held name is shown as information.
- **Nothing passes:** nothing is shown.

## Known limits

- **Taxes:** dividends are taxed differently from capital gains; returns here are gross.
- **Data source:** dividend records come from one source and are not cross-checked.
- **Survivorship**, as in the other studies.

---

## Results (added 2026-10-12, after the run; the sections above are unchanged)

**Data:**
- `python scripts/fetch_dividends.py`: 528 tickers, 0 failures, 3,178 cash-dividend rows, 362 tickers that ever paid.
- `python scripts/research_dividend_yield.py`. JSON: `data/reports/research_dividend_yield_2026-10-12.json`.
- In an average month, 36–37% of the universe paid in the last 12 months.
- The correlation between dy_z and value_sn_z is 0.17.

D is per year, net of 20 bps turnover cost, with Newey-West t.

| Test | Discovery D (t) | Holdout D (t) | Result |
|---|---|---|---|
| Y1 top dy among payers − universe | −9.71% (−2.52) | +4.82% (0.70) | FAIL |
| Y2 payers − non-payers | −8.46% (−1.93) | +2.72% (0.59) | FAIL |
| Y3 (value_sn + dy) top quintile − value_sn top quintile | −11.76% (−2.78) | −4.17% (−1.17) | FAIL |

**Nothing passes**, so nothing is shown in the bulletin.

How to read it:
- **High-dividend stocks did not beat the universe.** In 2013–2020 they lagged it by about 10% a year. In 2021–2026 they were slightly ahead, not significantly.
- **Adding dividend yield to the live value rule makes it worse in both periods.** The cost was 11.8% a year in discovery and 4.2% in holdout. Dividend payers on BIST are larger, steadier companies, and the value premium found here sits in smaller, cheaper names (`portfolio_backtest_preregistration.md`, F1). Mixing the two dilutes it.
- The common belief that high and regular dividend payers attract steady demand and outperform is not supported on BIST in 2013–2026.
