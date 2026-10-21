# Smart Money Concepts entry and exit timing: pre-registration

Written and committed on 2026-10-21, **before** any rule below was run on the panel. The rules, parameters, metrics and pass rules are fixed here. They are not changed after the results are seen. A changed rule or parameter counts as a new test and needs a new pre-registration.

## Question

`core/smc.py` (PR #90) computes Smart Money Concepts structure point-in-time: swing (50-bar) and internal (5-bar) pivots, BOS/CHoCH on closes, order blocks, fair value gaps and premium/discount zones. Can this structure time the R0 value picks better than the defaults?

- **Entry:** is there a better moment to buy a new value pick than the next close?
- **Exit:** does selling a holding on a bearish change of character beat holding it until the monthly rebalance?

## Theory and prior evidence

- `entry_timing_preregistration.md`: none of 7 entry rules (pullback limits, RSI, SMA confirmation, staggered, knife filter) beat buying at the next close. Limit rules got a better price for most names but missed the rallies.
- `exit_rules_preregistration.md`: no stop (trailing, fixed, ATR) or thesis-break exit beat the buffer rotation.
- SMC rules are pullback and trend-confirmation rules in another form. The prior is that they fail too. This study tests that prior directly instead of assuming it.

## Data and parameters

- Daily adjusted OHLC from `data/research/raw/*.pkl` (`px_adj`), as in the entry and exit studies.
- `core/smc.analyze` with its defaults: `swing_size=50`, `internal_size=5`, `equal_size=3`, `atr_length=200`, no confluence filter, automatic FVG threshold. No parameter is searched.
- **No look-ahead.** The state at d0 (active order blocks, fair value gaps, trailing range, trends) comes from `analyze` run on bars up to and including d0. Events after d0 come from the full-history run; `tests/test_smc.py` checks that events on any prefix equal the full-run events, so an event dated on day i uses only bars ≤ i.
- **Discovery:** 2013 to 2020-12. **Holdout:** 2021-01 to the end.

## Part A: entry rules (framework of `entry_timing_preregistration.md`)

Selection, day indexing, the baseline E0 (buy at the d1 close), the 126-day exit, the metrics I_mkt and I_cash, the primary sample (new entrants) and the secondary sample (all top-quintile members) are exactly as in that study (`scripts/research_entry_timing.py`). Each rule buys every name by its deadline.

| ID | Rule | Deadline |
|---|---|---|
| S1 | **Order-block pullback.** At d0, take the active bullish order block (any scope) with the highest top below the d0 close. Limit order at that top. Fill on the first day in d1..d21 with Low ≤ limit, at min(Open, limit). No such block at d0: buy at the d1 close | d21 close |
| S2 | **Discount zone.** At d0, if the close is above the midpoint of the trailing swing range (zone `premium` or `premium_half`), buy at the close of the first day in d1..d21 with close ≤ that d0 midpoint. Otherwise buy at the d1 close | d21 close |
| S3 | **Internal CHoCH confirmation.** At d0, if the internal trend is bearish, buy at the close of the first day in d1..d21 with a bullish internal BOS or CHoCH. Otherwise buy at the d1 close | d21 close |
| S4 | **Fair-value-gap fill.** At d0, take the active bullish FVG with the highest top below the d0 close. Limit at its top; fill as in S1. No such gap: buy at the d1 close | d21 close |

### Pass rule (all must hold, primary sample; same as the entry study)

1. Discovery: mean I_mkt > 0 and t > 3.0.
2. Holdout: mean I_mkt > 0 and t > 2.0.
3. Holdout: mean I_cash > 0.

A rule with t < −2 in both periods is labelled `WAITING_IS_COSTLY`.

## Part B: exit rules (framework of `exit_rules_preregistration.md`)

Same simulation as that study (`core/exit_rules.simulate`): monthly equal-weight rebalance; buffer rotation R1 (buy the top 20%, keep while in the top 40%) as the base; daily check within the month on adjusted closes; on a trigger the name is sold at that day's close, and the proceeds sit in XU100 until month end; 20 bps one-way cost for each exit.

| ID | Rule | Base |
|---|---|---|
| X5 | Sell a holding on the close of a day with a **bearish swing CHoCH** (50-bar structure) | R1 |
| X6 | Sell a holding on the close of a day with a **bearish internal CHoCH** (5-bar structure) | R1 |

### Pass rule (all must hold; same as the exit study)

1. Discovery: D = rule − R1 net active return > 0, t > 3.0.
2. Holdout: D > 0, t > 2.0.
3. Holdout USD maximum drawdown no worse than R1's by more than 2 percentage points.

Risk-only label `RISK_REDUCTION_NO_RETURN_GAIN` and `HARMFUL` exactly as in that study.

## Multiple testing

6 confirmatory tests (S1–S4, X5, X6). The t > 3 discovery threshold is above the Bonferroni threshold for 6 tests (≈ 2.64). These 6 trials are added to the trial ledger (`trial_ledger.json`, PR #88) after this study.

## What can go live

- An entry rule that passes: shown as the suggested entry in the report for new rotation buys; R0's selection is unchanged.
- An exit rule that passes: a sell reason in the report, after a new pre-registered portfolio backtest with costs.
- Nothing passes: SMC stays information only, as it is now.

## Known limits

- Survivorship and limit-fill assumptions as in the entry and exit studies.
- Order blocks and fair value gaps use adjusted prices; corporate-action adjustments can move old levels.
- The 200-bar ATR needs history: for names with fewer than 200 bars, no bar counts as high-volatility.

## Files

- `scripts/research_smc_timing.py`: runs A and B and writes `data/reports/research_smc_timing_<date>.json`.
- `core/exit_rules.py`: optional event-based exit (`Rule.event_exit`), default off; X1–X4 results unchanged.
