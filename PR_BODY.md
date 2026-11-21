## Summary

This PR fixes two live-pipeline parity gaps identified after the `2026-11-01` rebalance, without changing any rule parameters in `config/live_rule.json`:

1. **Fetch the latest calendar-ended quarter (`2026Q3` in October/November) instead of relying on `borsapy._get_periods()`:**
   - `borsapy._providers.isyatirim.IsYatirimProvider._get_periods()` hardcodes a two-month lag after each quarter end (`current_month <= 11 -> start_period = 6`), so `core/pit_panel.fetch_statement()` never requested `2026Q3` during October or November even after 538 non-financial companies had filed `2026Q3`.
   - `core/pit_panel.py` now computes the latest calendar-ended quarter via `last_ended_quarter(as_of)` and generates the 4-quarter request batches via `quarter_periods(count, as_of)`.
   - Point-in-time KAP availability is unchanged: a fetched quarter is only used by `latest_value_ratios()` / `live_value_inputs()` if its `available_at` (first KAP financial report publication date, or next day if published at/after `18:00`; `period_end + 75/100` days when no KAP match exists) is `<= as_of_date`. Tickers that have not filed `2026Q3` fall back to `2026Q2`.

2. **Do not drop `Holding` (and other `target_price is None`) candidates before `valuation_z` scoring and R0 monthly rotation:**
   - The research panel (`data/research/factors_monthly.parquet`) includes `Holding` (52 tickers) and `Girişim Sermayesi Yat. Ort.`, and pre-registered study `S2` (`docs/research/financials_holdings_reits_preregistration.md`) confirmed that `Holding` stays on `value_sn`. Only `pit_panel.FINANCIAL_SECTORS` (banks, insurance, pension, leasing, factoring, brokers, MKYO, asset management, savings finance) are excluded.
   - In live runs, `core/valuation_triangle.py` prices `ratio_profile == "holding"` on the peer-group median NAV discount (`FV = P / (1 - nav_disc_med)`) and nulls out `target_price` when `FV > 2.5 * P`, which triggers for the entire peer group whenever `nav_disc_med > 0.60`. On `2026-10-30..2026-11-01` (`nav_disc_med = 0.6156`) and `2026-11-17` (`nav_disc_med = 0.6028`), `target_price` became `None` for every `Holding` stock, and `if lt["target_price"] is None: continue` in `run.py` dropped all 42 eligible `Holding`/`GSYO` stocks (plus ~52 deep-value industrial/REIT stocks whose peer-multiple fair value exceeded the `2.5x`/`3.5x` cap) before `scoring.score_candidates()` and `rotation.monthly_rotation()`.
   - `run.py` now keeps candidates when informational `target_price` is `None` (setting `expected_roi_pct = None` and `excess_over_hurdle_pct = None`, with `core/beta_hurdle.py` handling `expected_roi_pct = None`). They are scored with cross-sectional `valuation_z` in `scores` and included in the R0 monthly rotation pool at parity with the backtested panel, while `hard_filters_passed()` still filters them out of target-price thesis cards (`NO_ACTION`, `filtered_by = "hurdle"`).

## Evidence

- **Live `2026Q3` check (`2026-11-22`):**
  - `THYAO` (`kap_published_at = 2026-11-04T08:00` -> `kap_available_at = 2026-11-04`), `ARCLK` (`2026-10-26T18:18` -> `2026-10-27`), and `KCHOL` (`2026-11-09T18:16` -> `2026-11-10`) now return `stmt_period = "2026Q3"` with `vendor_consistent_ytd` TTM ratios.
  - `KONTR` (no `2026Q3` filing yet) returns `2026Q2..2024Q4` from İş Yatırım and falls back cleanly to `stmt_period = "2026Q2"`.
- **Historical DB audit (`data/bist_history.db`):**
  - On `2026-10-29` (`Holding` median `nav_discount = 0.5942`), 36 `Holding` stocks were scored; on `2026-10-30..2026-11-01` (`median = 0.6156`), 0 `Holding` stocks were scored; on `2026-11-04` (`median = 0.5964`), 36 were scored again. Removing the early `continue` eliminates this cliff.

## Testing

- `tests/test_pit_panel.py`: unit tests for `last_ended_quarter`, `quarter_periods`, and mocked `fetch_statement` in November (`2026Q3` requested and returned when present, fallback to `2026Q2` when absent).
- `tests/test_valuation_parity.py`: unit test for `live_value_inputs` in November verifying the 18:00 KAP session-close rule, the 75-day assumed-lag fallback (`2026-12-14`) when KAP is unavailable, and `2026Q2` fallback when `2026Q3` is not filed.
- `tests/test_holding_live_parity.py`: end-to-end `run.py` test verifying that when Holding median `nav_discount > 0.60` (`target_price = None`), all Holding and low-P/B industrial candidates are written to `scores` with `valuation_z` matching `core.factor_backtest` (`value_sn_z`) and ranked in `rotation_holdings`, while banks remain excluded.
- Full test suite: `.venv/bin/pytest tests/ -q` (`522 passed`).
