# Exit and rotation rules: pre-registration

Written and committed on 2026-10-10, **before** any rule below was run. The rules, parameters, metrics and pass rule are fixed here. They are not changed after the results are seen. A changed rule or parameter counts as a new test and needs a new pre-registration.

## Question

When should a value_sn pick be sold? Two separate questions:
1. **Rotation:** sell as soon as a stock leaves the top quintile, or hold it through a buffer?
2. **Risk exits:** do price stops or fundamental "thesis break" exits add value over plain rotation?

## Theory and prior evidence

- **Buffers lower turnover cost** with little loss of signal when the signal is persistent (Novy-Marx & Velikov 2016). In this repository, value_sn top-quintile turnover is about 17% per month.
- **Stops help only if returns show momentum after losses.** Kaminski & Lo (2014) show that stops add value under momentum and cost value under mean reversion or a random walk.
- **Evidence against stops in BIST:**
  - 12-1 momentum has no effect (t 0.71);
  - 1-month reversal is strong (top net −12%/yr, t −5.05);
  - entry timing found no exploitable post-selection drift (`entry_timing_preregistration.md`).

  The expected sign for price stops is therefore negative.

## Data

- Daily adjusted OHLC from `data/research/raw/*.pkl`.
- XU100 daily close from `fx.parquet`.
- Monthly factors from `factors_monthly.parquet`.
- Quarterly statements, plus F7 and EP from `long_term_research` (`quarterly_ext.parquet`).
- Selection and liquidity universe: as base B in `long_term_preregistration.md` (value_sn rank within the monthly liquid universe).
- **Discovery:** months 2013-01 to 2020-12. **Holdout:** 2021-01 onward.

## Portfolio simulation

- **Rebalance:** at each month-end t (d0 = last trading day ≤ t). Holdings are equal-weighted at the d0 close.
- **Between rebalances:**
  - the daily adjusted close drives the value of each position;
  - a stopped position is sold at the close of the trigger day;
  - its proceeds are held in XU100 until the next rebalance.
- **Cost:** 20 bps one way on traded weight, counted at rebalance from the set changes, plus 20 bps on each stop sale.
- **Benchmark:** the equal-weighted mean of `fwd_ret_1m` over the full liquid universe for month t (as in `factor_backtest.quintile_spread`).
- **Net active return** = portfolio month return − benchmark − costs.
- **Stops:**
  - The price peak and the entry price are tracked from the day a name enters the portfolio.
  - A stopped name cannot be re-bought until a later rebalance, and only as a new buy (top quintile). Its peak and entry then reset.

Rotation rules:

| ID | Rule |
|---|---|
| R0 (baseline) | Hold exactly the top 20% each month. |
| R1 | Buffer 20/40: buy names in the top 20%, keep a holding while its rank stays in the top 40%. |
| R2 | Buffer 20/60: same, keep while in the top 60%. |

Risk exits, each applied on top of R1 and compared with R1:

| ID | Rule | Source |
|---|---|---|
| X1 | Trailing stop: sell when the close is ≤ 75% of the peak close since entry (−25%) | Han, Zhou & Zhu 2016 |
| X2 | Fixed stop: sell when the close is ≤ 80% of the entry close (−20%) | common practice |
| X3 | Live ATR stop: sell when the close is ≤ entry close − 2·ATR20 at entry (the live rule `entry_low − 1.5·ATR`, with entry_low = price − 0.5·ATR) | `core/targets.py` |
| X4 | Thesis break at rebalance: sell a holding (even if still inside the buffer) when TTM net income turns negative (ep < 0) or F7 ≤ 2 | Piotroski 2000 |

There are 6 confirmatory tests: R1 and R2 versus R0, and X1–X4 versus R1.

## Metrics

- **Primary:** the monthly difference D = net active(rule) − net active(base). The t-statistic is Newey-West with 6 lags.
- Also reported, per period:
  - annualised net active return and its t;
  - USD version;
  - turnover;
  - number of stop exits per year;
  - maximum drawdown of the cumulative total return in USD;
  - annualised volatility of the total return in USD;
  - the share of stopped names whose next 3-month return was above the universe ("stopped out then recovered").

## Pass rule (all must hold)

1. Discovery: D > 0 and t > 3.0 (Harvey-Liu-Zhu). This is above the Bonferroni threshold of ≈ 2.64 for 6 tests at α = 0.05, two-sided.
2. Holdout: D > 0 and t > 2.0.
3. Holdout: the rule's USD maximum drawdown is no worse than the base's by more than 2 percentage points.

**Risk-only label.** A stop that fails rule 1 but meets all three conditions below is labelled "risk reduction, no return gain". It may be shown as an optional setting and is not the default:
- D > −1%/yr in both periods;
- USD max drawdown at least 5 pp smaller in both periods;
- USD volatility lower in both periods.

A rule with D < 0 and t < −2 in both periods is labelled "harmful".

## What goes live

- **Rotation:** R1 or R2 goes live only if it passes; otherwise it is R0. The live report gets a BUY / HOLD / SELL list from that rule (`core/decision_diff.py`).
- **Stops:** if no stop passes, the live `stop_loss` is labelled information only, and position size is no longer described as stop-derived.
- **Thesis break:** if X4 passes, it becomes a SELL reason in the report.

## Known limits

- Survivorship bias: delisted stocks are missing, and they are exactly the ones a stop would have sold. The bias works **against** stops. This is reported with the result, not corrected.
- Fills are at the close with no slippage. Gaps through a stop are filled at the trigger-day close, which is realistic for daily monitoring.
- Proceeds held in XU100 keep market exposure. The alternative, cash, mixes in a market-timing effect that is not tested here.

---

## Results (added 2026-10-10, after the run; the sections above are unchanged)

`python scripts/research_exit_rules.py`. 160 monthly rebalances, 2013-04 to 2026-08. Discovery is 93 months and holdout 67.

R0 here is +10.64%/yr in discovery, the same as base B. Its holdout value (+5.67%) is lower than B's +6.96%, for two reasons:
- month returns come from daily closes between rebalance days, not from the month-end panel;
- names without daily data are skipped.

**Portfolio statistics.** Active return is net of cost, NW t with 6 lags. Drawdown and volatility are for the total return in USD, so they include market exposure.

| Rule | Period | Net active / yr (t) | USD active / yr | Turnover / month | Stop exits / yr | USD max DD | USD vol |
|---|---|---|---|---|---|---|---|
| R0 top 20% | discovery | 10.64% (2.66) | 10.60% | 16.7% | — | −57.9% | 38.5% |
| | holdout | 5.67% (2.03) | 5.56% | 16.4% | — | −43.5% | 35.1% |
| R1 buffer 20/40 | discovery | 9.62% (3.43) | 9.68% | 9.0% | — | −58.8% | 38.0% |
| | holdout | 5.36% (2.09) | 5.12% | 7.3% | — | −39.8% | 34.6% |
| R2 buffer 20/60 | discovery | 7.53% (3.10) | 7.67% | 7.1% | — | −58.4% | 37.4% |
| | holdout | 5.27% (2.15) | 5.00% | 5.5% | — | −39.9% | 34.4% |
| X1 trailing −25% | discovery | 6.34% (2.10) | 6.36% | 18.8% | 67 | −58.3% | 37.6% |
| | holdout | 4.86% (1.95) | 4.69% | 19.3% | 113 | −40.2% | 34.5% |
| X2 fixed −20% | discovery | 8.39% (2.88) | 8.40% | 12.5% | 25 | −58.8% | 37.7% |
| | holdout | 5.55% (2.19) | 5.30% | 9.2% | 22 | −39.6% | 34.5% |
| X3 live ATR stop | discovery | 8.48% (2.70) | 8.49% | 18.4% | 64 | −59.1% | 37.7% |
| | holdout | 4.85% (1.91) | 4.64% | 13.4% | 67 | −40.4% | 34.5% |
| X4 thesis break | discovery | 8.15% (2.67) | 8.21% | 26.4% | — | −58.7% | 37.9% |
| | holdout | 5.59% (2.05) | 5.38% | 18.4% | — | −40.6% | 34.8% |

**Tests.** D is the annual difference versus the base, NW t with 6 lags.

| Test | Base | Discovery D (t) | Holdout D (t) | Stopped names beating XU100 over the next 3 months | Result |
|---|---|---|---|---|---|
| R1 buffer 20/40 | R0 | −1.02% (−0.44) | −0.30% (−0.19) | — | FAIL |
| R2 buffer 20/60 | R0 | −3.11% (−1.01) | −0.40% (−0.24) | — | FAIL |
| X1 trailing −25% | R1 | −3.29% (−1.81) | −0.50% (−0.56) | 46.6% | FAIL |
| X2 fixed −20% | R1 | −1.23% (−1.25) | +0.19% (0.85) | 54.2% | FAIL |
| X3 live ATR stop | R1 | −1.14% (−1.00) | −0.51% (−1.24) | 48.4% | FAIL |
| X4 thesis break | R1 | −1.47% (−1.36) | +0.23% (0.28) | — | FAIL |

**No rotation or exit rule passed.** None met "risk reduction" either: max drawdown and volatility moved by less than 1 pp. None met "harmful": no t < −2 in both periods.

As pre-registered:
- **Rotation stays R0:** hold the top 20% and sell when a name leaves it.
- **The live `stop_loss` is information only.**
- **Thesis break is not a sell reason.**

How to read it:
- **Buffers** halve turnover (16.7% to 7–9% per month). The cost saving is only about 0.4%/yr at 20 bps (2 × 20 bps × 7.7 pp × 12), and it is more than offset by holding weaker-ranked names. The net effect is small and not significant. At higher real costs (wide spreads in small caps), R1 would look relatively better. This was not tested.
- **Price stops** cut drawdown by less than 1 pp, because the portfolio's drawdown is market-wide (USD max DD around −40% to −59% for every rule). A stock-level stop does not protect against a market fall, and the proceeds stayed in XU100.
- After a stop, roughly half the stopped names beat XU100 over the next 3 months (46.6–54.2%). A stop sells at a random point, not before further losses. This matches the reversal and no-momentum evidence.
- **Survivorship works against stops**, because delisted names are missing. So these results understate stop value somewhat, but not by enough to reverse a −1% to −3%/yr discovery cost without evidence.
