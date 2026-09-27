# Short-term rule search: pre-registration

Written and committed on 2026-09-28, **before** any of the signals below were run. The candidate list, the thresholds and the pass rule are fixed here. They are not changed after the results are seen. If a rule is changed later, it counts as a new test and gets a new pre-registration.

## Background

`scripts/backtest_short_term.py` showed that the live short-term rule (20-day volume ratio ≥ 1.5, ranked by the value-weighted score) has no edge.
- Volume spikes underperform the liquid universe by 0.76% over 20 days (t = −7.9).
- Down-day spikes underperform by 2.0% (t = −12.4).
- Adding the value ranking brings this to +0.10% (t = 0.6).

## Data and universe

- Daily adjusted OHLCV from `data/research/raw/*.pkl`: 543 non-financial tickers, 2013 to today.
- Each day, the least liquid 30% by 60-day median TL volume is dropped. Days with fewer than 30 names are dropped.
- Selection happens every 5th trading day (weekly) to limit overlap.

## Candidate signals (6)

Higher value means buy. Every signal uses only data up to and including day t.

| ID | Signal | Definition | Source |
|---|---|---|---|
| S1 | 1-week reversal | −(C_t / C_{t−5} − 1) | Lehmann (1990) |
| S2 | 1-month reversal | −(C_t / C_{t−20} − 1) | Jegadeesh (1990) |
| S3 | 52-week-high proximity | C_t / max(High over 252 days) | George & Hwang (2004) |
| S4 | Low volatility | −stdev(daily returns, 60 days) | Ang et al. (2006) |
| S5 | Sector-neutral value | monthly point-in-time value composite, demeaned within sector, last month-end ≤ t (max 62 days old) | #19 |
| S6 | Value + low volatility | 5:1 mix of cross-sectional z-scores of S5 and S4 (the live long-term weights) | live score proxy |

## Portfolio and metrics

- On each selection day, the portfolio is the top quintile of the signal, equal-weighted.
- **Primary metric:** 20-day return minus the equal-weighted liquid-universe mean. Its t-statistic is Newey-West with 4 lags (20-day windows, weekly sampling).
- **Trade simulation:** the live bracket, with the same assumptions as `backtest_short_term.py`:
  - entry at the close
  - target +2.5 ATR20, stop −2 ATR20, 20-day horizon
  - if target and stop are hit on the same day, the stop is assumed first
  - 0.5% round-trip cost
  - compared with the same bracket on the whole liquid universe on the same days
- **Split:** discovery is 2013-01-01 to 2020-12-31; holdout is 2021-01-01 to the end of the data.

## Pass rule (all must hold)

1. Discovery: t > 3.0 (Harvey-Liu-Zhu). This is also above the Bonferroni threshold of ≈ 2.64 for 6 tests at α = 0.05, two-sided.
2. Holdout: mean excess has the same sign as in discovery, and t > 2.0.
3. Holdout: the trade-simulation mean net return is above the universe baseline.

If no signal passes, the conclusion is "no short-term rule found". The short-term bucket should then stop being presented as opportunities.

If several signals pass, the one with the highest holdout t is chosen. A different threshold or holding period is **not** searched afterwards.

## Known limits

- Survivorship bias: the universe is today's listing.
- Returns are nominal TL.
- The entry is the signal-day close; live, it is next day within a band.
- There is no structural cap (swing high, Bollinger band) on the target.

---

## Results (added 2026-09-28, after the run; the sections above are unchanged)

`python scripts/research_short_term_signals.py`: 685 weekly selection dates, 543 tickers. Excess is the 20-day return minus the liquid-universe mean; t is Newey-West with 4 lags. The trade column is the mean net return of the bracket trade; the universe baseline is 0.87% in discovery and 0.96% in holdout.

| Signal | Discovery excess | t | Holdout excess | t | Holdout trade | Pass |
|---|---|---|---|---|---|---|
| S1 1-week reversal | −0.67% | −3.87 | −0.69% | −5.02 | 0.71% | no |
| S2 1-month reversal | −0.60% | −2.39 | −1.01% | −4.84 | 0.76% | no |
| S3 52-week-high proximity | +0.27% | 1.02 | +1.83% | 6.03 | 1.59% | no (discovery) |
| S4 Low volatility | −0.69% | −2.39 | +0.58% | 2.05 | 1.17% | no (discovery) |
| S5 Sector-neutral value | +0.86% | 4.77 | +0.42% | 1.61 | 1.19% | no (holdout t < 2) |
| S6 Value + low volatility | +0.82% | 4.58 | +0.33% | 1.24 | 1.09% | no (holdout t < 2) |

**Conclusion: no short-term rule was found.** As pre-registered, the short-term bucket is no longer presented as opportunities. `config/weights.yaml` now has `short_term_opportunities_enabled: false`.

**Post-hoc observation (not a result).** The reversal signals are significantly negative in both periods, which suggests short-term *continuation* in BIST (1-week momentum). This hypothesis was formed after seeing the holdout, so this data cannot test it cleanly. A new pre-registration with forward (out-of-sample, live paper) tracking is needed before it can be used.
