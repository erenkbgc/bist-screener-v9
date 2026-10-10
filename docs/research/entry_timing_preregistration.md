# Entry timing: pre-registration

Written and committed on 2026-10-10, **before** any rule below was run. The rules, parameters, metrics and pass rule are fixed here. They are not changed after the results are seen. A changed rule or parameter counts as a new test and needs a new pre-registration.

## Question

The stock is already chosen: the value_sn top quintile, monthly (`long_term_preregistration.md`). Is there a better moment to buy it than right away?

## Theory and expected result

The theory gives a clear default, and every rule below is tested against it:
- **No timing gain without predictability.** If prices are a martingale relative to the market, every entry-timing rule has zero expected gain (optional stopping theorem).
- **Waiting has a cost.** If the chosen stock has positive expected excess return (here, the value premium), every day spent waiting gives some of it up.
- **So a rule can help only if** short-horizon price moves after selection are predictable.

Earlier evidence in this repository:
- the 1-month reversal factor (top net −12%/yr, t −5.05 in `backtest_factor_model.py`);
- the short-term pre-registration, where 1-week and 1-month reversal signals had the wrong sign in both periods.

## Data

- Daily adjusted OHLC from `data/research/raw/*.pkl` (`px_adj`).
- XU100 daily close from `data/research/fx.parquet`.
- Policy rate, monthly, from `data/research/macro_monthly.parquet`.
- Selection: on each month-end t, the value_sn top quintile, built exactly as base B in `long_term_preregistration.md` (liquidity filter, sector demeaning).
- **Primary sample:** new entrants, meaning names in the top quintile at t but not at t−1. This is the actual buy decision in a rotation.
- **Secondary sample:** all top-quintile members.
- **Discovery:** selection months 2013-01 to 2020-12. **Holdout:** 2021-01 to the last month with a full 126-day exit window.

## Day indexing

- d0 is the last trading day on or before month-end t. d_k is the k-th trading day after d0.
- **Immediate entry (baseline E0):** close of d1. The signal uses the d0 close, so this avoids same-close execution.
- **Exit:** close of d126 (about 6 months), the same for every rule.
- ATR20 is the Wilder 20-day average true range on adjusted OHLC at d0.
- RSI14 is Wilder's RSI on adjusted closes.
- SMA20 and SMA50 are simple averages of adjusted closes, each including the current day.

## Rules (7 confirmatory tests)

Each rule must enter by its deadline. If its condition never triggers, it buys at the deadline close, so every selected stock is bought.

| ID | Rule | Deadline | Source |
|---|---|---|---|
| E1 | If the stock's month-t return is in the top quintile of that month's universe, wait and buy at the d22 close; otherwise buy at the d1 close | d22 | Jegadeesh 1990 (reversal) |
| E2a | Limit order at P0 − 1·ATR20, where P0 is the d0 close. Fill on the first day in d1..d21 with Low ≤ limit, at min(Open, limit) | d21 close | pullback entry |
| E2b | Same as E2a with P0 − 2·ATR20 | d21 close | pullback entry |
| E3 | Buy at the close of the first day in d1..d21 with RSI14 < 30 | d21 close | oversold entry |
| E4 | Buy at the close of the first day in d1..d63 with close > SMA50. If d1 already qualifies, this is the d1 close | d63 close | trend confirmation (Faber 2007) |
| E5 | One third at each of the d1, d11 and d21 closes | — | staggered entry (cost averaging) |
| E6 | If the stock's month-t return is in the bottom quintile ("falling knife"), buy at the close of the first day in d1..d21 with close > SMA20. Otherwise buy at the d1 close | d21 close | knife filter |

Prior exposure: E1 and E6 use the month return. Its cross-sectional effect was seen in the factor backtest, but not as an entry rule and not on this selection.

## Metrics

All metrics are per (stock, month). The entry price P_e comes from the rule and P_1 is the d1 close.

- **Primary, I_mkt = ln(P_1 / P_e) − ln(XU_1 / XU_e).** This is the price improvement versus immediate entry when the capital waits in XU100. XU_e is XU100 on the entry day.
- **Secondary, I_cash = ln(P_1 / P_e) + ln(1 + r_policy) × (waiting trading days / 252).** The capital waits in cash at the policy rate of month t.
- For E5, I is the mean of the three legs.

The exit is common to all rules, so these numbers equal the difference in log return to the exit.

Each month's value is the mean over names. The t-statistic is Newey-West with 6 lags. Also reported:
- mean and median waiting days;
- the share of names entered before the deadline;
- the share of names whose return to the exit is better than immediate entry.

## Pass rule (all must hold, primary sample)

1. Discovery: mean I_mkt > 0 and t > 3.0 (Harvey-Liu-Zhu). This is also above the Bonferroni threshold of ≈ 2.69 for 7 tests at α = 0.05, two-sided.
2. Holdout: mean I_mkt > 0 and t > 2.0.
3. Holdout: mean I_cash > 0.

If no rule passes, the conclusion is "buy right away": the live report shows no timing advice, and entry bands become information only.

A rule significantly **negative** in both periods (t < −2 in each) is reported as "waiting is costly" and is never used as a buy rule.

If several rules pass, the one with the highest holdout t is chosen. No other parameter is searched afterwards.

## Known limits

- Survivorship bias: the universe is today's listing. Its effect on timing differences is smaller than on levels, but not zero.
- Limit fills assume full execution at the limit with no queue or spread.
- There are no transaction-cost differences, except E5, which pays three commissions; this is ignored as small.
- Daily data include BIST circuit-breaker days with no special handling.
- The policy rate is a proxy for a deposit rate.

---

## Results (added 2026-10-10, after the run; the sections above are unchanged)

`python scripts/research_entry_timing.py`. Selection months run from 2013-04 to 2026-02; the last 126-day exit window ends in 2026-09.

| Sample | Discovery | Holdout |
|---|---|---|
| New entrants | 665 obs, 93 months (about 7 per month) | 589 obs, 62 months |
| All members | 4010 obs | 3615 obs |

All values are mean monthly improvements versus buying at the d1 close, in log %. The t-statistics are Newey-West with 6 lags.

**Primary sample (new entrants):**

| Rule | Discovery I_mkt (t) | Holdout I_mkt (t) | Holdout I_cash | Holdout mean wait (days) | Holdout share better than immediate | Result |
|---|---|---|---|---|---|---|
| E1 wait after a top-quintile month | −0.21% (−0.89) | +0.04% (0.20) | −0.02% | 1.9 | 5.3% | FAIL |
| E2a limit −1 ATR | −0.38% (−0.74) | +0.39% (0.65) | −0.34% | 11.5 | 64.7% | FAIL |
| E2b limit −2 ATR | −0.56% (−1.05) | +0.56% (0.75) | −0.30% | 16.1 | 63.2% | FAIL |
| E3 RSI14 < 30 | −0.97% (−1.54) | +0.40% (0.53) | −0.53% | 17.0 | 55.7% | FAIL |
| E4 close > SMA50 | +0.06% (0.14) | −0.15% (−0.28) | −0.45% | 12.1 | 21.1% | FAIL |
| E5 staggered thirds | −0.29% (−0.84) | +0.27% (0.56) | −0.64% | 10.0 | 56.4% | FAIL |
| E6 knife filter | +0.20% (1.22) | +0.04% (0.28) | −0.06% | 2.7 | 11.5% | FAIL |

**Secondary sample (all top-quintile members), discovery I_mkt:**

| Rule | I_mkt (t) |
|---|---|
| E2a | −1.33% (−3.42) |
| E2b | −1.23% (−2.57) |
| E3 | −1.48% (−2.43) |
| E4 | −0.45% (−2.69) |
| E5 | −0.62% (−2.04) |

Holdout values for all members are small and positive (t ≤ 1.74).

**Conclusion: no entry-timing rule beats buying right away.** As pre-registered:
- the live report gives no timing advice;
- the ATR entry band is information only.

No rule met "waiting is costly" (t < −2 in both periods), so that label is not claimed.

How to read it:
- **Limit and pullback rules (E2a, E2b, E3)** get a better price in most cases: 56–65% of names. They still lose on average. When the stock rises immediately the limit never fills, and the rule buys later at a higher price. Many small savings are outweighed by a few missed rallies.
- **Waiting in cash (I_cash)** is negative for every rule in the holdout, even at policy rates of 8.5–50%.
- **The discovery losses in the all-members sample** match the theory: a stock with a positive expected premium costs money to wait for.

The theoretical default holds: the chosen value stocks show no exploitable short-term price predictability after selection, so the best mathematical entry time is the earliest one.
