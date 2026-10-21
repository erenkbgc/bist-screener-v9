# Trend-following timing overlays (Donchian + ATR, Supertrend, EMA pullback): pre-registration

Written and committed on 2026-10-21, **before** any rule below was run on the panel. The rules, parameters, metrics and pass rule are fixed here. They are not changed after the results are seen. A changed rule or parameter counts as a new test and needs a new pre-registration.

## Question

An external suggestion (2026-10-21): keep the stock selection, and let a rule-based indicator decide when to hold each selected stock and when to step aside. Three standard systems were proposed:

| ID | System | Long when | Flat when |
|---|---|---|---|
| T1 | Donchian 20/10 + ATR | close breaks above the prior 20-day high | close breaks below the prior 10-day low, or below the ATR trailing stop |
| T2 | Supertrend | Supertrend direction turns up | direction turns down |
| T3 | EMA pullback | pullback to EMA20 in an uptrend, then confirmation | ATR trailing stop |

Do any of these, applied to the R0 picks, beat simply holding the picks for the whole month?

## Theory and prior evidence

- `entry_timing_preregistration.md`, `exit_rules_preregistration.md` and `smc_timing_preregistration.md`: 15 entry and exit timing rules on the value picks, none passed. Stops cut return without cutting drawdown.
- Time-series momentum exists in some asset classes, but the factor study found no 12-1 momentum effect in the BIST cross-section, and the macro study found no predictability of market direction.
- Value picks are cheap stocks, often after a decline. A trend filter keeps them out until they rise, which can miss the value rebound. The prior is that the overlays fail.

## Data

- Daily adjusted OHLC from `data/research/raw/*.pkl` (`px_adj`), XU100 and USD/TRY from `fx.parquet`, policy rate from `macro_monthly.parquet`.
- Selection and benchmark exactly as in `exit_rules_preregistration.md` (`scripts/research_exit_rules.build_inputs`): monthly value_sn ranking on the base panel, R0 = top 20%, equal weight; benchmark = the EW universe return of the month.
- Discovery: decisions 2013 to 2020-12. Holdout: 2021-01 to the end.

## System states (computed on each stock's full daily history, point-in-time)

ATR is Wilder's average true range. All rolling windows end on the previous day where stated, so a signal on day t uses only data up to t.

- **T1 Donchian 20/10 + ATR(14).** Go long at the close of day t if close_t > max(High over t−20..t−1). While long, track H = the highest close since entry. Go flat at the close of day t if close_t < min(Low over t−10..t−1), or close_t < H − 2 × ATR14_{t−1}.
- **T2 Supertrend (ATR 10, multiplier 3).** Standard definition: basic bands hl2 ± 3 × ATR10; final upper band = basic upper if basic upper < previous final upper or previous close > previous final upper, else previous final upper; final lower band mirrored. Direction turns up when close > previous final upper, down when close < previous final lower. Long while the direction is up.
- **T3 EMA pullback + ATR.** Uptrend: EMA20 > EMA50. Go long at the close of day t if the trend is up on t, Low_{t−1} ≤ EMA20_{t−1}, and close_t > High_{t−1}. While long, track H = the highest close since entry. Go flat at the close of day t if close_t < H − 3 × ATR14_{t−1}.

## Execution

- A state change at the close of day t is executed at the close of day t+1 (no same-close execution).
- **Limit rule:** if on day t+1 the close moved ≥ 9.5% from the previous close (BIST daily limit ±10%), the trade waits for the next day without such a move.
- A selected stock is held on a day only if its executed position is long; otherwise its slot earns the policy rate (cash). Secondary, information only: the slot sits in XU100.
- The state is computed on the whole history regardless of the selection, so a stock entering the list can already be long.

## Portfolio and costs

- Monthly rebalance at d0 to the R0 list, equal slots per name. The month's slot return compounds daily: the stock's return on days when the executed position is long, the daily policy rate otherwise.
- Costs: the monthly rebalance cost of the exit study (2 × turnover × 20 bps), plus 20 bps of the slot for each executed state change within the month.
- **Base B0:** the same simulator with the position always long. It must reproduce R0 of the exit study (discovery net active 10.64%/yr) up to the cost and fill conventions; any difference is reported.

## Metrics

Per month: net active return vs the EW universe, in TL and USD. Reported per window: annualised active return with Newey-West t (6 lags), USD max drawdown, USD volatility, share of slot-days in the market, state changes per name per year.

D = overlay − B0 monthly net active return.

## Pass rule (all must hold; same as the exit study)

1. Discovery: D > 0 and t > 3.0.
2. Holdout: D > 0 and t > 2.0.
3. Holdout USD max drawdown no worse than B0's by more than 2 percentage points.

`RISK_REDUCTION_NO_RETURN_GAIN` if D > −1%/yr in both windows, USD max drawdown at least 5 pp smaller in both and USD volatility lower in both. `HARMFUL` if D < 0 with t < −2 in both windows.

## Multiple testing

3 confirmatory tests (T1–T3, cash parking). Added to `trial_ledger.json` after this study (N_sel 81 → 84).

## What can go live

A passing overlay would be shown as a hold/step-aside indicator next to the rotation, after a new costed portfolio pre-registration. Nothing passes: the systems are not added.

## Known limits

- Survivorship and fill assumptions as in the exit study. Close-to-close fills ignore the intraday spread.
- The limit rule uses a ±9.5% close move as a proxy for a locked limit.
- ATR and EMAs need history: before the windows fill, a stock's state is flat.

## Files

- `core/trend_timing.py`: the three state machines, execution lag and limit rule, overlay simulator.
- `scripts/research_trend_timing.py`: runs the test and writes `data/reports/research_trend_timing_<date>.json`.
