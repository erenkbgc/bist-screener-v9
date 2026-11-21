# Agent Report — Live Reliability Audit (Nov 2026) & P3-1 / P3-2 Safeguards

- **Date:** 2026-11-22
- **Worktree / Branch:** `/home/eren/bist_wt/safeguards` (`agent/safeguards`, base `5617fbc`)
- **Scope & Rules:** Read-only GitHub Actions & forward-record audit; monitoring-only safeguards in `core/run_health.py`. No `git push`, no PRs, `master` untouched, `config/live_rule.json` untouched, live scoring/rotation untouched, no new research trials (`N_sel` unchanged).

---

## 1. November Daily Run Audit (`2026-11-01` .. `2026-11-21`)

Inspected all **21** scheduled runs of `BIST gunluk tarama` via `gh run list`/`gh run view --log`, `data/bist_history.db` (`runs`, `run_health`, `kap_llm_labels`, `rotation_holdings`), all **17** November `data/reports/2026-11-*_payload.json` files, and `data/forward_record/decisions.jsonl`.

### Run Outcomes Summary
- **17 full completed runs:** `status=completed`, `email_sent=True`, `validation.is_valid=True` (0 orphan numbers, 0 banned claims). All 17 had `run_health.status == "DEGRADED"` (`kap_unavailable` on 17/17; `outcomes_stalled` additionally on 6/17).
- **3 idempotent skips (`skipped_idempotent`):** `2026-11-06` (id `42292679481`, 8.8 min), `2026-11-14` (id `43634995189`, 5.1 min), `2026-11-21` (id `44948988288`, 5.8 min). Cause: GitHub Actions cron rollover past `21:00 UTC` (`00:00 Europe/Istanbul`) shifted the prior day's run onto the next calendar date (see Open Problems).
- **1 hard failure:** `2026-11-02` (id `41543110775`, 1.3 min) — `borsapy.exceptions.APIError: Failed to fetch company list: Server error '500 Internal Server Error' for url 'https://www.kap.org.tr/tr/api/company/generic/excel/IGS/A'` during `bp.companies()`.
- **4 calendar dates absent from `runs`/`run_health`:** `2026-11-02` (failed), plus `2026-11-03`, `2026-11-09`, `2026-11-16` (rolled past midnight UTC+3).

### P0-2 Item-by-Item Audit (17 Full Runs)

| Item | Result | Verified Numbers |
|---|---|---|
| `[timing]` total (`run.py`) | Bottleneck is `universe`, NOT KAP | Min `6,915s` (1.92h), median `8,152s` (2.26h), max `19,129s` (5.31h on Nov 8; Nov 7 was `17,776s` / 4.94h). |
| `[timing]` stage deltas | `universe` is **89.4%** of median runtime | `universe`: `6,140` / **`7,285`** / `15,542s`; `prefetch`: `458` / **`624`** / `9,580s` (Nov 7 retry); `fundamentals`: `25` / **`35`** / `47s`; `piotroski_sloan`: `0` / **`0`** / `1s`; `catalysts_prices_regime_sector`: `61` / **`76`** / `101s`; `candidates`: `73` / **`106`** / `141s`; `scoring_rotation`: `2` / **`3`** / `4s`; `kap_panels`: `5` / **`10`** / `287s`; `report_dispatch`: `7` / **`11`** / `17s`. |
| `[prefetch] KAP istemcisi` (#96) | Breaker working as intended | `open=True` on **17/17** runs. `calls`: 211–214 (496 on Nov 8); `failures`: 10–12; `skipped`: `1,741`–`1,919` (median `1,895`); `seconds`: `63`–`122s` (median **`94s`**, max `316s` on Nov 8). `kap_missing_share = 1.0` on all 17 runs. |
| `[prefetch] mali tablo yeniden deneme` (#94) | **Saved Nov 7 from `basis_guard` halt** | Logged on 17/17 runs. On 16 runs: `failed_before=13..15`, `recovered=0`, `still_failed=13..15` (structural missing statements). On **`2026-11-07`** (id `42406507748`): **`failed_before=154`, `recovered=141`, `still_failed=13`** (`154/459 = 33.6% > 30%` halt threshold reduced to `13/459 = 2.8%`). |
| `[kap_llm]` (#95) | Healthy; 0 errors, well above 80/day | **2,188** labeled across Nov (`error=None` on **17/17** runs). Hit the `400/400` cap on Nov 1, 3, 4, 5; cleared backlog on Nov 7 (`263/263`); labeled 100% of daily pending (`1–61/day`) thereafter. Total rows in DB `kap_llm_labels`: `5,248` (`408` non-`none` flags). |
| `[sovereign_spread]` (#97) | Mostly OK; failures are yfinance, not Ziraat | `status="ok"` on **14/17** runs (spread `2.62`–`3.16 pp`). `status="unavailable"` on **3/17** runs (`2026-11-05`, `2026-11-12`, `2026-11-17`), all 3 with `reason="ust_yields_empty"` (`^FVX/^TNX/^TYX` empty from `yfinance`). |
| `value_inputs.ttm_method` (#101) | 100% `vendor_consistent_ytd` on non-financials | Across all 17 November payloads: **4,270 / 4,270 (100.0%)** non-bank/insurance `passing_candidates` have `value_inputs.ttm_method == "vendor_consistent_ytd"` (`196/196` on `2026-11-01`; `222/222` on `2026-11-21`). Bank/insurance candidates have `value_inputs=None` by design. Note: `decisions.jsonl` records `ttm_unit="C1_constant_unit"` (233/233) and `value_source="isyatirim_quarterly_ytd"` (233/233), while `ttm_method` lives in `*_payload.json`. |

### P0-3 Forward Record & `scripts/forward_record_report.py`
- **`data/forward_record/decisions.jsonl`:** 1 record (`schema=2`, `rebalance_date="2026-11-01"`, `status="ok"`, `rule_version="R0-2026-10-12"`, `recorded_at="2026-11-01T22:20:35+00:00"`, `code_sha="f32a31a1c5516ba1d79dbd89ff53c3ce0d3592f2"`).
  - **47 holdings** (matches `rotation_holdings` DB table), **233 ranked universe** (from 334 long-term non-financial, 333 eligible, `liq_cut_tl=32,258,702.96 TL`).
  - `price_date_min = price_date_max = "2026-10-30"`; `statement_period`: `2026Q2` (227), `2026Q1` (6); `valid_metric_count`: 4 (232), 3 (1); `kap_published_at`: `0/233`; `health`: `DEGRADED ["kap_unavailable"]` (`config_hash="ee609095c6c6"`).
  - `data/forward_record/prices/`: 233 CSV files populated.
- **Ran `.venv/bin/python scripts/forward_record_report.py`** → wrote `data/reports/forward_record_2026-11-22.json`:
  - `as_of="2026-11-22"`, `rule="R0-2026-10-12"`, `last_price_day="2026-11-20"`, `index_coverage={"xu100_from": "2026-07-06", "xu100_tr_covers_first_decision": true}`, `policy_rate_last_month="2026-10"`, `no_decision_records=0`, `months_without_decision=[]`.
  - `series[0]`: `decisions=1`, `periods=0`, `haircut_0_5={"periods": 0}` (first full calendar month completes at 2026-12 rebalance).
  - `price_sources`: `provider=226`, `store=7` (`MOPAS`, `OZKGY`, `OZSUB`, `PEKGY`, `TSPOR`, `TTKOM`, `TUKAS`), `conservative_loss=[]`, `universe_missing=[]` — the persistent price store (`core/forward_prices`) already covered 7 tickers where live provider fetches failed.
  - Note: when `periods == 0`, `summarize()` returns `{"periods": 0}` early, so `"expectation_check"` is omitted (not `null`) until `periods >= 1`.

---

## 2. P3-1 & P3-2 Safeguards Implementation (Monitoring Only)

### P3-1: Vendor Consistency Alarm (`core/run_health.py`)
- Added `VENDOR_SAMPLE_TICKERS` (20 confirmed TL-reporting, `reexpression_class.parquet: cls == "reexpressed"` large/liquid non-financial stocks, excluding USD/EUR reporters `THYAO`, `TAVHL`, `EREGL`, `ENKAI`, `PGSUS`), `VENDOR_RATIO_MIN = 0.75`, `VENDOR_RATIO_MAX = 1.25`, `VENDOR_SAMPLE_MIN_N = 5`.
- Implemented `vendor_consistency_check(income_stmts, cpi=None, ...)` using `pit_panel.statements_long` + `pit_panel.quarterly_table` to compute the discrete latest-quarter YoY revenue ratio `q_revenue(P) / q_revenue(P-4)` for IAS 29 periods (`>= 2023Q4`). Retains `<= 0` numerator values when `prev_v > 0` so a YTD-to-discrete vendor switch is also caught.
- In `run.py` (live mode only, after `score_candidates`), reuses already-cached `live_data._quarterly_statements_cached(t)[1]` for sampled tickers present in `eligible` (0 extra network calls), logs `[vendor_consistency]`, and passes result to `run_health.assess(...)`. Out-of-range median (`n >= 5`) appends `"vendor_inconsistent"` → `status="DEGRADED"`.
- **Live check (2026-11-22):** `n_checked=20/20`, `median_ratio=1.035` (`min=0.722`, `max=1.583`, `n_out_of_range=4`), `ok=True`.

### P3-2: Market Value Cross-Check (`core/live_data.py`, `core/run_health.py`, `run.py`)
- Added `live_data.live_isyatirim_market_caps()`: single `bp.Screener()` call (`add_filter("market_cap", min=0)`, ~2s, resolves `market_cap` or `criteria_8` via `CRITERIA_MAP`, converts TL millions → TL, returns `{}` on error so monitoring never breaks a live run).
- Implemented `run_health.market_cap_cross_check(tv_mcaps, isy_mcaps, max_diff=0.10)`: compares TradingView `market_cap` against İş Yatırım across all matched stocks with finite positive values, flags `|TV - ISY| / ISY > 10%` sorted by `diff_pct` descending.
- In `run.py` (live mode only, after `score_candidates`), flags matching `scored` candidates with informational fields (`mcap_mismatch_flag`, `mcap_isy_diff_pct` — never enters scoring/rotation), logs `[mcap_cross_check]`, stores `mcap_flagged` in `run_health` (and DB `run_health.metrics_json`), and appends `"mcap_mismatch"` → `status="DEGRADED"` when `n_flagged > 0`.
- **Live check (2026-11-22 vs `2026-11-21_payload.json`):** Screener returned 628 positive stocks; `n_checked=463/464` eligible (`DMLKT` has no market cap), `n_flagged=0`, `max_diff_share=0.0001` (`0.01%`).

### Report Banner & Tests
- Updated `report/templates/_run_health.html.j2` with `vendor_inconsistent` and `mcap_mismatch` messages using only payload values via `| fmt` (verified `validate.find_orphan_numbers == []`).
- Added 8 unit tests in `tests/test_run_health.py` covering healthy IAS 29 ratios, 0.4–0.6× mixed-unit break, stopped re-expression (`>1.25×`), YTD→discrete switch (`<0`), insufficient sample & pre-IAS 29 skip, market-cap match vs >10% mismatch, Screener scaling & error handling, and validation-gate orphan-number compliance.
- **Full test suite (`.venv/bin/pytest -q`):** **525 passed, 0 failed** (`45.89s`).

---

## 3. Commits on `agent/safeguards`

- `203c8da` — `feat(health): P3-1 vendor consistency alarm and P3-2 market cap cross-check` (`core/run_health.py`, `core/live_data.py`, `run.py`, `report/templates/_run_health.html.j2`, `tests/test_run_health.py`)
- Plus the subsequent report/artifact commit adding `data/reports/forward_record_2026-11-22.json` and `AGENT_REPORT.md`.

---

## 4. Open Problems & Operational Findings

1. **Sequential `universe` bottleneck (`~2h`, 89% of total runtime):** `core/universe.py::build_universe()` calls `get_listing_and_size()` sequentially over ~800 tickers (`_fast_info_cached` + `_history_cached`) before `prefetch_all()` runs. Parallelizing (with the existing 4-worker cap) or prefetching `fast_info` + `history` inside `live_universe()` would likely cut daily run time from ~2.3h to ~30–40 min.
2. **GitHub Actions cron midnight-crossing date shift:** `cron: "30 15 * * *"` routinely queues 4–8 hours late, starting past `21:00 UTC` (`00:00 Europe/Istanbul`). Computing `TZ=Europe/Istanbul date +%F` at job start assigns the run to `D+1`, causing 3 skipped days (`11-06`, `11-14`, `11-21` via `skipped_idempotent`) and 3 missing calendar dates (`11-03`, `11-09`, `11-16`), which in turn trigger transient `outcomes_stalled` `DEGRADED` alerts on the following run (since `run_health.assess()` runs before `evaluate_past_predictions()`). Fixing the date derivation (e.g., last trading day / shifting cron earlier, or subtracting 4h when determining market date) would eliminate this drift.
3. **Unprotected `bp.companies()` SPOF:** On `2026-11-02`, a single HTTP 500 from KAP's company-list Excel endpoint (`kap.org.tr/tr/api/company/generic/excel/IGS/A`) crashed the entire run in 1.3 min with no retry or cached fallback.
4. **KAP unavailable in CI (`kap_missing_share = 1.0`, P3-3):** Every November run had 0% KAP report-date coverage in CI, forcing `observed_at_ingest` and keeping `run_health` permanently `DEGRADED`.
5. **Intermittent `yfinance` UST empty downloads:** 3/17 November runs (`11-05`, `11-12`, `11-17`) hit `sovereign_spread: ust_yields_empty`; a retry or fallback source (e.g., FRED / Treasury XML) would make the risk gauge reliable.
6. **`borsapy 0.11.0` `_get_periods` calendar lag:** As of `2026-11-22`, İş Yatırım already serves `2026Q3` statements for large TL reporters (verified on 16/16 sample tickers), but `borsapy`'s `_get_periods` fixes `current_month <= 11 -> start_period = 6`, keeping live `fetch_statement` on `2026Q2` until Dec 1. (`vendor_consistent_ttm(2026Q2)` remains mathematically unit-consistent because it only uses `2026Q2`, `2025Q4`, and `2025Q2`, even after `2025Q3` is re-expressed.)
7. **`scripts/forward_record_report.py` slowness & `expectation_check` omission at `periods=0`:** Took ~16 min fetching 233 tickers sequentially with no `socket.setdefaulttimeout`, and omitted the `expectation_check` key (instead of `null`) when `periods == 0`.
