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
