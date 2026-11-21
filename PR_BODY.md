## Summary

Fixes three live-operations reliability and runtime issues identified in the November 2026 daily run audit without touching `config/live_rule.json`, `core/rotation.py`, or scoring logic:

1. **Cron midnight date drift (`core/run_date.py`, `run.py`, `scripts/kap_sentiment_today.py`, `.github/workflows/daily-screener.yml`, `core/forward_record.py`)**
   - Resolves the intended `Europe/Istanbul` trading date from explicit input (`--as-of-date` / `INPUT_AS_OF_DATE`), the scheduled UTC cron expression (`GITHUB_EVENT_SCHEDULE`, e.g. `"30 15 * * *"`), or a `06:00 Europe/Istanbul` rollover cutoff when started past midnight.
   - Applies the resolved trading date consistently across `runs`, `run_health`, `data/reports/`, `rotation_holdings`, and `forward_record`.
   - Guards `forward_record.append_decision()` against writing more than one `"ok"` decision per `YYYY-MM` calendar month so delayed month-boundary runs cannot skip or double a monthly rebalance.

2. **`bp.companies()` retry, cached fallback & `run_health` flag (`core/live_data.py`, `core/run_health.py`, `report/templates/_run_health.html.j2`)**
   - Wraps `bp.companies()` in `_fetch_companies_with_fallback()` with 3 attempts and exponential backoff (`2s`, `4s`), persisting the latest company list to `data/companies_cache.json`.
   - Falls back to the freshest cached company list (from `data/companies_cache.json` or SQLite `universe_snapshot`) within a 14-day staleness limit (`COMPANIES_CACHE_MAX_STALE_DAYS = 14`) when KAP's `/tr/api/company/generic/excel/IGS/A` endpoint returns HTTP 500.
   - Flags fallback runs in `run_health` (`status="DEGRADED"`, issue `"companies_cache_fallback"`, metrics `companies_cache_fallback` and `companies_cache_age_days`) and renders the warning banner in `_run_health.html.j2`.

3. **`universe` stage parallelization & redundant-call elimination (`core/universe.py`, `core/live_data.py`, `bist_mcp/server.py`)**
   - Parallelizes per-ticker `get_listing_and_size()` and `get_tedbir_level()` calls in `core/universe.py::build_universe()` with a bounded thread pool (`UNIVERSE_MAX_WORKERS = 4`, matching `PREFETCH_MAX_WORKERS = 4`).
   - Skips `_info_cached()` in `live_universe()` for the 636/804 tickers whose sector is already defined in `config/fintables_ticker_sektor.json`.
   - Cuts 20-ticker live `universe` stage runtime from `198.50s` (`9.92s/ticker`) to `80.67s` (`4.03s/ticker`, **2.46x speedup**) with identical output.

## Testing

- `.venv/bin/pytest tests/ -q`
- Added unit tests for cron date resolution and Nov 30 / Dec 1 month-boundary rebalance behavior (`tests/test_run_date.py`), `bp.companies()` retry/backoff/fallback/staleness and `run_health` degradation (`tests/test_live_data.py`, `tests/test_run_health.py`), and serial vs. parallel `build_universe()` / `live_universe()` output parity (`tests/test_universe.py`, `tests/test_live_data.py`).
