# Live decision vs. tested panel: audit (2026-10-17)

This is an audit, not a test. Question: does the live monthly rotation make the same decision as the rule tested on the research panel? Run: `python scripts/audit_live_vs_panel.py`. Output: `data/reports/audit_live_vs_panel_2026-10-17.json`.

## 1. Decision timing

| | Backtest | Live |
|---|---|---|
| Signal | value_sn at the month-end close (last trading day of month *t*−1) | value_sn at the first successful run of month *t* (daily cron 15:30 UTC, after the close) |
| Statements usable | `available_at` ≤ month-end (actual KAP date + 1 day if after 18:00) | whatever the provider returns on the run day |
| Fill | next trading day close | `forward_record_report.py`: next trading day close after the last close ≤ `rebalance_date` |

Measured gap, signal day vs. the last close the live run saw:

| Month | Backtest signal | Live first run | Trading days late |
|---|---|---|---|
| 2026-10 | 2026-09-30 | 2026-10-01 | 1 |
| 2026-11 (expected) | 2026-10-31 | 2026-11-01 (Saturday; last close 10-31) | 0 if the run succeeds |

(2026-09 is not counted: the live system started on 2026-09-13.)

- The cron runs every day, including weekends. When the month starts on a weekend, the live signal uses the same close as the backtest.
- When the first run fails, the decision moves to the next successful run. Since PR #67 such days are recorded as `no_decision`, so the delay is visible in the forward record.
- A one- or two-day delay is small against a monthly holding period. **Timing is not the main gap.**

## 2. Statement data: the main gap

| Input | Panel (tested) | Live |
|---|---|---|
| Income: E (net income), S (sales), EBIT | TTM from **quarterly** statements, latest quarter with `available_at` ≤ month-end | **Annual** statements (`get_income_stmt()` default `quarterly=False`), latest fiscal year |
| E/P | net income / market cap | 100 / provider P/E (`fast_info`); else EPS / price |
| B/M | equity / market cap (equity > 0) | 1 / provider P/B (`fast_info`) |
| Net debt | financial debt − cash, same quarter | provider `netDebt` (`info`); else annual balance sheet |

On 2026-09-30 the panel uses 2026Q2 for 510 of 527 stocks. In October 2026, live income items come from FY2025, which is up to 9 months older. Under IAS 29 (from FY2023) the annual and quarterly figures are also stated in different purchasing power.

## 3. Ranking agreement

Panel 2026-09-30 `value_sn_z` (liquidity cut applied) against live `valuation_z` (value_sn profiles), on the stocks in both:

| Live day | Common names | Rank corr. | Top-20% overlap |
|---|---|---|---|
| 2026-10-14 | 333 | 0.870 | 53 / 67 (79.1%) |
| 2026-10-15 | 333 | 0.878 | 54 / 67 (80.6%) |
| 2026-10-16 | 329 | 0.880 | 52 / 66 (78.8%) |
| Reference: panel 2026-08-31 vs. 2026-09-30 | 357 | 0.945 | 80.3% |

- About one in five live top-20% names would not be in the tested top 20% on the same stocks.
- The rank correlation (0.87–0.88) is lower than one month of natural change inside the panel (0.945), and that month already includes the Q2 statement updates. The two-week price gap alone does not explain it.
- Known causes, not separated here:
  - annual vs. quarterly TTM statements;
  - provider P/E and P/B vs. the panel's own ratios;
  - the E/P fallback bug (fixed in PR #70; 52 live stocks had no E/P).

## Conclusion

- **Timing: acceptable.** The gap is 0–1 trading days. Failed months are now recorded.
- **Data: not the tested strategy yet.** The live list uses older, annual statements and provider ratios. The tested rule uses quarterly TTM with KAP dates. The overlap is about 80%.
- **Recommended fix (not done here):** build the live value_sn inputs with the same `pit_panel` functions as the panel: quarterly statements → TTM, `available_at` ≤ run day, E/P and B/M from the panel's own definitions. That is one canonical selection path. It restores the tested definition, so it is a parity fix, not a new rule. It does change the live list, so it should land before the forward series starts, or the series should note the change date.
- Re-run this script after PR #70 and after the next rebalance to see how much of the gap remains.
