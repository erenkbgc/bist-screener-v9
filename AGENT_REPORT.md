# Live-Ops Reliability Report (November 2026 Follow-Up)

- **Date:** 2026-11-22
- **Worktree / Branch:** `/home/eren/bist_wt/liveops` (`fix/live-ops-reliability`)
- **Scope & Constraints:** `config/live_rule.json`, `core/rotation.py`, `core/scoring.py`, `core/live_data.py` statement-fetching and Holding-sector valuation logic, and `master` were left untouched. No remote push or PR operations were performed.

---

## 0. Inspection of Previous Partial Work & `core/rotation.py` Decision

Upon inspecting `git status` and `git diff`:
1. **`core/run_date.py` (kept):** Implemented `resolve_run_date()` supporting explicit date overrides (`--as-of-date` / `INPUT_AS_OF_DATE`), scheduled UTC cron derivation (`GITHUB_EVENT_SCHEDULE`, e.g. `"30 15 * * *"`), and a `06:00 Europe/Istanbul` rollover cutoff fallback.
2. **`.github/workflows/daily-screener.yml` (completed):** Added the `as_of_date` workflow dispatch input and wired the `today` step to call `python -m core.run_date` with `INPUT_AS_OF_DATE` and `GITHUB_EVENT_SCHEDULE` instead of `TZ=Europe/Istanbul date +%F`.
3. **`core/forward_record.py` (kept):** Updated `append_decision()` to guard against duplicate `"ok"` records within the same `YYYY-MM` calendar month (`d["rebalance_date"][:7] == rebalance_date[:7]`), matching the existing monthly guard in `append_no_decision()`.
4. **`core/rotation.py` (reverted):** The previous work replaced the `rebalance_date <= ? ORDER BY rebalance_date DESC LIMIT 2` query in `monthly_rotation()` with `substr(rebalance_date, 1, 7) = ?`. Although that edit was date-lookup plumbing rather than a scoring/selection change, our operating rules explicitly forbid modifying `core/rotation.py` or rotation logic. Moreover, once `as_of_date` is resolved to the intended trading date before `run.py` executes and `core/forward_record.py::append_decision` enforces one `"ok"` decision per `YYYY-MM`, the existing `core/rotation.py` already handles month boundaries deterministically without skipping or doubling a monthly rebalance. We therefore reverted `core/rotation.py` (`git checkout -- core/rotation.py`) so it has zero diff against `master`.

---

## 1. Task 1 — Cron Midnight Date Drift & Month-Boundary Rebalance Integrity

### Root Cause
The scheduled workflow (`cron: "30 15 * * *"`, 18:30 `Europe/Istanbul`) frequently starts 4–8 hours late on GitHub Actions runners, crossing `21:00 UTC` (`00:00 Europe/Istanbul`). Computing `TZ=Europe/Istanbul date +%F` at job startup labeled delayed runs as `D+1`, leaving `2026-11-03`, `2026-11-09`, and `2026-11-16` missing from `runs`/`run_health` and causing the next day's on-time run (`2026-11-06`, `2026-11-14`, `2026-11-21`) to exit with `skipped_idempotent`.

### Fix
- **`core/run_date.py`:** Resolves the intended `Europe/Istanbul` trading date in priority order:
  1. Explicit date (`--as-of-date` or `INPUT_AS_OF_DATE`).
  2. Scheduled cron expression (`GITHUB_EVENT_SCHEDULE`, e.g. `"30 15 * * *"`): finds the most recent scheduled UTC trigger `<= now` (with a 5-minute early-trigger grace) and converts that timestamp to its `Europe/Istanbul` calendar date.
  3. Fallback for manual/local runs without an explicit date: uses `Europe/Istanbul` date, rolling back 1 day if started before `06:00 Europe/Istanbul` (after the prior 18:00 BIST close and before the next session open).
- **`run.py`, `scripts/kap_sentiment_today.py`, `.github/workflows/daily-screener.yml`:** Consistently resolve `as_of_date` via `core.run_date.resolve_run_date()`, propagating the intended trading date into `runs`, `run_health`, `data/reports/<as_of_date>*`, `rotation_holdings`, and `forward_record`.
- **`core/forward_record.py`:** `append_decision()` rejects any second `"ok"` decision in the same `YYYY-MM` month.

### Verification (`tests/test_run_date.py`)
- Tested on-time (`18:35+03:00`), late past Istanbul midnight (`00:30+03:00`), and late past both Istanbul and UTC midnights (`04:30+03:00`).
- Tested month boundary cases:
  - **Run for Nov 30 starting Dec 1 `01:00 Europe/Istanbul` (`2026-11-30T22:00:00Z`):** Resolves to `2026-11-30`, reuses the existing `2026-11-01` holdings, and does not trigger an early December rebalance.
  - **Run for Dec 1 starting Dec 2 `02:00 Europe/Istanbul` (`2026-12-01T23:00:00Z`):** Resolves to `2026-12-01`, triggers the `2026-12-01` monthly rebalance under rule `R0-2026-10-12`, and records `rebalance_date="2026-12-01"` in `rotation_holdings` and `decisions.jsonl`.
  - **Subsequent Dec 2 run starting Dec 3 `01:30 Europe/Istanbul`:** Resolves to `2026-12-02`, reuses the `2026-12-01` rebalance, and cannot double-record in `forward_record`.

---

## 2. Task 2 — `bp.companies()` Retry, Cached Company-List Fallback & `run_health` Flag

### Root Cause
On `2026-11-02` (run `41543110775`), `bp.companies()` failed after 1.3 minutes with `borsapy.exceptions.APIError: Failed to fetch company list: Server error '500 Internal Server Error' for url 'https://www.kap.org.tr/tr/api/company/generic/excel/IGS/A'`. Because `live_universe()` called `bp.companies()` with no retry or fallback, a transient KAP 500 aborted the entire daily run.

### Fix
- **Retry with exponential backoff (`core/live_data.py::_fetch_companies_with_fallback`):**
  - Retries `bp.companies()` up to `COMPANIES_MAX_ATTEMPTS = 3` times with exponential backoff (`COMPANIES_RETRY_BACKOFF_S = 2.0`, delays `2.0s`, `4.0s`).
  - On every successful live fetch, persists `{as_of_date, updated_at, companies}` to `data/companies_cache.json` (`COMPANIES_CACHE_PATH`).
- **Cached fallback with staleness limit (`COMPANIES_CACHE_MAX_STALE_DAYS = 14`):**
  - If all retry attempts fail, `_load_cached_companies()` checks both `data/companies_cache.json` and the latest `universe_snapshot` date (`<= as_of_date`) in SQLite (`data/bist_history.db`), selecting the freshest snapshot.
  - If the snapshot is within `COMPANIES_CACHE_MAX_STALE_DAYS` (`0 <= age_days <= 14`), the run continues with the cached company list and sets `_COMPANIES_STATUS` (`source="cache_fallback"`, `fallback_used=True`, `cached_date`, `age_days`, `attempts`, `error`).
  - If no cache exists or `age_days > 14`, the error is re-raised rather than running on stale universe membership.
- **`run_health` flag & report banner (`core/run_health.py`, `report/templates/_run_health.html.j2`):**
  - `run_health.assess()` records `metrics["companies_cache_fallback"]` and `metrics["companies_cache_age_days"]` and appends `"companies_cache_fallback"` to `degraded` issues (`status="DEGRADED"`).
  - `_run_health.html.j2` renders a warning line using `run_health.metrics.companies_cache_age_days | fmt` (compliant with `report/validate.py` orphan-number checks).

### Verification (`tests/test_live_data.py`, `tests/test_run_health.py`)
- Tested retry recovery on transient HTTP 500 (verifying attempt count, `[2.0, 4.0]` backoff delays, and cache write).
- Tested fallback to `companies_cache.json` on persistent HTTP 500 and fallback to SQLite `universe_snapshot` when the JSON cache file is absent.
- Tested staleness limit rejection when the cached company list is older than 14 days.
- Tested `run_health.assess()` degradation and HTML banner validation (`find_orphan_numbers == []`).

---

## 3. Task 3 — `universe` Stage Profiling, Bounded Thread-Pool Parallelization & Benchmark

### Profiling Findings
In the November 2026 audit (17 full runs), the `universe` stage took `6,140s`–`15,542s` (median **`7,285s`**, **89.4%** of median total runtime `8,152s`), whereas `prefetch` took a median of only `624s`.

Profiling the per-ticker calls inside `universe_mod.build_universe()` (`run.py` stage 3) identified two bottlenecks:
1. **Unnecessary `_info_cached(ticker)` calls in `core/live_data.py::live_universe()`:**
   - `live_universe()` ran `pool.map(_info_cached, tickers)` across all **804** companies solely to evaluate `sector = _fintables_sector_map().get(ticker) or info.get("sector") or info.get("industry")`.
   - Inside `borsapy`, `dict(Ticker(t).info)` triggers `EnrichedInfo.__iter__()`, which executes 5 provider calls per ticker (`TradingView.get_quote`, `IsYatirim.get_company_metrics`, `TradingView.get_history("1y")`, `KAP.get_company_details`, and `IsYatirim.get_dividends`), taking **~4.4s–4.9s per ticker**.
   - However, `config/fintables_ticker_sektor.json` (`_fintables_sector_map()`) already covers **636 of 804** tickers (79.1%), for which `info` was never read by `live_universe()`. (Eligible tickers still have `_info_cached` prefetched later in `prefetch_all(eligible)`, while ~340 ineligible tickers never need `_info_cached` at all.)
2. **Sequential per-ticker I/O in `core/universe.py::build_universe()`:**
   - `build_universe()` looped serially (`for entry in seed:`) over all **804** tickers, calling `bist_mcp.get_listing_and_size(ticker, as_of_date)` and `bist_mcp.get_tedbir_level(ticker, as_of_date)` in a single thread before `bist_mcp.prefetch(eligible)` ran.
   - Each `live_listing_and_size(ticker, as_of_date)` call invokes `_fast_info_cached(ticker)` (~2.0s) and `_history_cached(ticker, "5y")` (~2.8s), totaling **~4.8s–5.0s per ticker** (`1,608` sequential network requests across 804 tickers).

### Optimization
1. **`core/live_data.py::live_universe()`:** Only invokes `_info_cached(ticker)` for tickers not already mapped in `_fintables_sector_map()` (`need_info = [t for t in tickers_list if not sector_map.get(t)]`), using `ThreadPoolExecutor(max_workers=PREFETCH_MAX_WORKERS)` (`4` workers).
2. **`core/universe.py::build_universe()`:** Parallelizes per-ticker evaluation (`get_listing_and_size` + `get_tedbir_level` + filter classification) across `seed` using a bounded `ThreadPoolExecutor(max_workers=UNIVERSE_MAX_WORKERS)` (`UNIVERSE_MAX_WORKERS = 4`, matching `PREFETCH_MAX_WORKERS = 4` to respect TradingView/İş Yatırım rate limits). `pool.map` preserves deterministic `seed` ordering, and all SQLite writes remain batched in a single `conn.executemany()` on the main thread.
3. **Cache reuse in `prefetch`:** Because `_fast_info_cached` and `_history_cached(ticker, HISTORY_PERIOD)` are `@lru_cache(maxsize=2048)`, warming them in parallel during `build_universe()` also makes them 100% cache hits when `prefetch_all(eligible)` runs immediately afterwards.

### Real Local Benchmark (`universe` Stage Only, 20-Ticker Live Sample, `as_of_date="2026-11-21"`)

| Configuration | 20-Ticker Sample Wall Time | Per-Ticker Average | Extrapolated Full Universe (804 Tickers) | Output / Eligible Parity |
|---|---:|---:|---:|---|
| **Before** (all-ticker `_info_cached` + serial `build_universe`) | `198.50s` | `9.92s` | `~7,980s` (`2.22h`, matches CI median `7,285s`) | Baseline (`13/20` eligible) |
| **After** (unmapped-only `_info_cached` + 4-worker `build_universe`) | `80.67s` | `4.03s` | `~3,243s` (`0.90h`, **2.46× faster**, ~1.3h saved/run) | **100% identical** (`rows_identical=True`, `eligible_identical=True`, `13/20` eligible) |

---

## 4. Test Suite Summary

Ran `.venv/bin/pytest tests/ -q`:
- **528 passed, 0 failed** (`46.98s`), including all new tests in `tests/test_run_date.py`, `tests/test_live_data.py`, `tests/test_run_health.py`, `tests/test_universe.py`, `tests/test_rotation.py`, and `tests/test_forward_record.py`.
