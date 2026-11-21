# Engineering & Quant Tooling Scouting Report

**Date:** 2026-11-22 | **Scope:** Open-source Python quant engineering tooling & practices (2023–2026 primary sources)  
**Baseline:** Live rule R0 (`core/rotation.py`, monthly EW top-20% `value_sn`, non-financials, locked in `config/live_rule.json`; ledger `N_sel ≈ 86–87`). All rankings are ordered by expected value (EV) for **this** codebase (`docs/plan_2026-10-26.md` P0–P4 & README Roadmap Step 5).

---

## 1. Healthchecks (`healthchecks/healthchecks` v5.0) — Dead-Man's-Switch Monitoring for GitHub Actions

- **Link:** https://github.com/healthchecks/healthchecks
- **Date:** 2026 (v5.0.x; BSD-3-Clause)
- **Summary:** Open-source cron dead-man's-switch service that alerts when an expected HTTP heartbeat fails to arrive within a configured period plus grace window. Catches silent failures that native CI error notifications never fire on: dropped GitHub Actions schedules, 350-minute job timeouts, and GitHub's silent 60-day public-repo schedule disable.
- **Concrete use for THIS project:** Add a final `if: success()` heartbeat `curl` step (plus optional `/start` and `/fail` pings) in `.github/workflows/daily-screener.yml` with a 26-hour window to absorb cron drift; ensures a missed monthly rebalance on `data/forward_record/decisions.jsonl` (**P0-3**) or silent run crash is alerted immediately rather than discovered days later.
- **Type:** Infrastructure
- **Effort:** S
- **Failed-idea check:** Passed — pure pipeline observability; touches no alpha signal, timing overlay, or factor weight in README scorecard.

## 2. Pandera (`unionai-oss/pandera` v0.36) — Declarative DataFrame Schema & Statistical Drift Contracts

- **Link:** https://github.com/unionai-oss/pandera
- **Date:** 2026 (v0.36.0; MIT)
- **Summary:** Pythonic, lightweight `DataFrameModel` schema and statistical contract validator supporting Pandas, Polars, and PyArrow natively with `@pa.check_types` / `@pa.check_output` decorators. Supports cross-column checks, null-rate bounds, and built-in hypothesis checks directly inside pytest and live pipelines without external metadata servers.
- **Concrete use for THIS project:** Enforce hard contracts on `core/pit_panel.py` outputs (`quarterly.parquet`, `factors_monthly.parquet` for **P1-1**, asserting `available_at > period_end`, finite bounds, and no duplicate `(ticker, date)` keys) and implement **P3-1** (vendor IAS 29 YoY discrete-quarter ratio convention alarm) and **P3-2** (>10% TradingView vs. İş Yatırım market-value divergence check) cleanly inside `core/run_health.py` and `tests/`.
- **Type:** Infrastructure
- **Effort:** S
- **Failed-idea check:** Passed — data-integrity and vendor-drift guard only; does not alter `value_sn` or add any failed filter (Piotroski, debt maturity, KAP red-flag exclusions).

## 3. Hishel (`karpetrosyan/hishel` v2.0) — RFC 9111 Persistent HTTP Caching for `httpx`

- **Link:** https://github.com/karpetrosyan/hishel
- **Date:** 2026 (v2.0.0; BSD-3-Clause)
- **Summary:** Modern RFC 9111-compliant HTTP caching transport built natively for `httpx`/`httpcore` (sync and async) with file/SQLite/Redis storage backends and custom cache-key/TTL controllers. Transparently intercepts repeated GET/POST responses at the transport layer without rewriting downstream parsing logic.
- **Concrete use for THIS project:** Both `core/kap_api.py` and `borsapy`'s underlying HTTP clients use `httpx` (`core/live_data.py` currently relies on process-only `@lru_cache`, re-fetching 5y history and 8 quarters for ~800 tickers every CI run, taking 2.5–4.5h against a 350m cap — **P0-2**). Wrapping immutable historical statement/KAP requests in `hishel` persisted via `actions/cache` cuts daily CI runtime dramatically and makes **P2-3** / **P2-4** resumable at HTTP level.
- **Type:** Infrastructure
- **Effort:** M
- **Failed-idea check:** Passed — network caching layer only; deterministic outputs unchanged and no trading rule touched.

## 4. PyrateLimiter (`vutran1710/PyrateLimiter` v4.x) + Tenacity (`jd/tenacity` v9.2) — Monotonic Rate Limiting & Jittered Retries

- **Link:** https://github.com/vutran1710/PyrateLimiter (companion: https://github.com/jd/tenacity)
- **Date:** 2026 (PyrateLimiter v4.x; Tenacity v9.2.x; MIT / Apache-2.0)
- **Summary:** PyrateLimiter v4 provides thread-safe and async leaky-bucket throttling using monotonic clocks and per-key lock release during waits (so one throttled provider never blocks others). Paired with Tenacity's composable exponential backoff + full jitter, it replaces ad-hoc `time.sleep` loops and coarse thread caps.
- **Concrete use for THIS project:** Replace fixed `PREFETCH_MAX_WORKERS = 4` blind throttling in `core/live_data.py` (**P0-2**) with per-provider buckets (separate rates for TradingView `fast_info`, İş Yatırım statements, and KAP) and replace the unjittered `base_wait * 2**attempt` loop in `core/kap_api.py::fetch_range` so **P2-4** (~20,000 KAP pages under KAP's ~90-request IP-ban ceiling) runs safely without triggering lockouts.
- **Type:** Infrastructure
- **Effort:** S
- **Failed-idea check:** Passed — I/O resilience and runtime reduction; no change to factor definitions or selection rules.

## 5. Cloudflare Workers Cron Triggers → GitHub Actions `workflow_dispatch` — Eliminating Cron Drift & Silent Skips

- **Link:** https://developers.cloudflare.com/workers/configuration/cron-triggers/ (GitHub spec: https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule)
- **Date:** 2025–2026 (Official Docs)
- **Summary:** GitHub Actions `on: schedule` runs on best-effort shared queues (documented delays of 30–60+ min at `:00`/`:30` boundaries, silent drops under peak load, and 60-day inactivity auto-disable on public repos). Triggering `.github/workflows/daily-screener.yml` via a tiny Cloudflare Worker Cron calling GitHub's `workflow_dispatch` REST API (or shifting off `:30` as an interim fix) executes deterministically on the minute and logs dispatch failures.
- **Concrete use for THIS project:** `.github/workflows/daily-screener.yml` currently fires at `cron: "30 15 * * *"` (peak half-hour slot) and carries a 350m timeout; a 60m start delay pushes a 4.5h run past midnight Istanbul time, risking a wrong `as_of_date` or missed monthly `decisions.jsonl` lock (**P0-3**). Also pairs cleanly with **P3-3** (external trigger/job for KAP report dates outside blocked GitHub runner IPs).
- **Type:** Infrastructure
- **Effort:** S
- **Failed-idea check:** Passed — scheduling reliability only; no signal or model change.

## 6. DuckDB 2.0 LTS `ASOF JOIN` & DuckLake 1.1 (`duckdb/duckdb`) — Bitemporal Point-in-Time Parquet Store

- **Link:** https://duckdb.org/docs/stable/sql/query_syntax/from#asof-joins (Lakehouse spec: https://ducklake.select/)
- **Date:** October 2026 (DuckDB 2.0.0 LTS & DuckLake 1.1; MIT)
- **Summary:** Embedded, zero-server analytical SQL engine with native, out-of-core `ASOF JOIN` directly over Parquet files plus DuckLake (open lakehouse storing snapshot metadata in SQL and immutable data in Parquet). Expresses bitemporal queries (`period_end` valid time × `available_at`/`published_at` knowledge time × restatement vintage) in declarative SQL without look-ahead bugs or loading full panels into RAM.
- **Concrete use for THIS project:** Power **P1-1** (`core/pit_panel.py`, `scripts/build_pit_panel.py`) and **P2-3 / P2-4 / P2-5** by joining monthly price dates (`d0`) `ASOF` against first-published vs. restated financial vintages and İş Yatırım `PD` / `HAO_PD` directly on Parquet (`data/research/fp/*.parquet`). Also offers a clean append-only Parquet alternative to committing binary `data/bist_history.db` via fragile `git rebase -X theirs` in `daily-screener.yml`.
- **Type:** Infrastructure
- **Effort:** M
- **Failed-idea check:** Passed — directly supports the data-correctness audit (`first_published_panel.md`, `vendor_vs_kap_audit.md`); introduces zero new return hypotheses.

## 7. Pydantic v2 (`pydantic/pydantic`) — Strict Boundary Validation for `decisions.jsonl` & `payload.json`

- **Link:** https://github.com/pydantic/pydantic
- **Date:** 2024–2026 (v2.x Rust-backed `pydantic-core`; MIT)
- **Summary:** High-speed, Rust-core schema validation and serialization for JSON/JSONL records with discriminated unions, strict typing, and frozen immutable models. Catches missing fields, `NaN`/string-coercion bugs, and schema-version mismatches at write time before corrupt lines enter append-only audit trails.
- **Concrete use for THIS project:** Validate every `ok` and `no_decision` line in `core/forward_record.py` (`data/forward_record/decisions.jsonl`, schema 2, **P0-3**) before appending and on read in `scripts/forward_record_report.py`, and formalize `core/payload.py` contracts upstream of `report/validate.py` so malformed `value_inputs.ttm_method` (**P0-2**) or missing KAP provenance fails loudly.
- **Type:** Infrastructure
- **Effort:** S
- **Failed-idea check:** Passed — forward-record audit integrity only; no trading rule modification.

## 8. DiskCache (`grantjenks/python-diskcache`) — Atomic SQLite-Backed Disk Cache Replacing Raw `.pkl` Files

- **Link:** https://github.com/grantjenks/python-diskcache
- **Date:** 2023–2026 (Actively maintained on PyPI/conda-forge; Apache-2.0)
- **Summary:** Pure-Python, SQLite-backed persistent key-value cache with thread/process safety, atomic transactions, TTL expiration, and eviction policies. Eliminates partial-write file corruption and directory-inode bloat common with hand-rolled per-ticker `.pkl` files under `ThreadPoolExecutor`.
- **Concrete use for THIS project:** Replace raw `path.write_bytes(pickle.dumps(raw))` in `scripts/build_pit_panel.py` (`data/research/raw/<T>.pkl`, **P1-1**, **P2-3**) and back `core/live_data.py`'s historical statement/metadata cache so interrupted local builds or parallel worker writes never leave truncated cache files.
- **Type:** Infrastructure
- **Effort:** S
- **Failed-idea check:** Passed — pure storage/caching hygiene; zero impact on factor signals or live rule.

## 9. skfolio (`skfolio/skfolio` v1.13, arXiv:2507.04176) — Scikit-Learn-Native Portfolio Construction & Denoised HRP

- **Link:** https://arxiv.org/abs/2507.04176 (Repo: https://github.com/skfolio/skfolio)
- **Date:** July 2025 (paper); Oct–Nov 2026 (v1.12.5–v1.13.0; BSD-3-Clause)
- **Summary:** Scikit-learn-compatible portfolio optimization library offering `LedoitWolf`, `OAS`, Marchenko-Pastur `DenoiseCovariance`, `DetoneCovariance`, HRP/HERC/NCO, sector group constraints, and `CombinatorialPurgedCV`. Actively maintained with clean `fit`/`predict` APIs and minimal dependency friction compared to older toolkits.
- **Concrete use for THIS project:** Directly upgrades `core/portfolio.py` (currently using unshrunk 60-day `np.cov` for ~60–110 stocks where $p \ge n$) to satisfy **Roadmap Step 5** (Ledoit-Wolf / denoised covariance + HRP with existing 30% sector caps).
- **Type:** Infrastructure (if kept information-only in `core/portfolio.py` reports); **New testable idea (+1 `N_sel`; requires pre-registration)** if tested as a live replacement for equal-weight R0 in `core/rotation.py`.
- **Effort:** M
- **Failed-idea check:** Passed — `learned_weights_preregistration.md` tested IC-learned *factor* weights (FAIL), and `long_term_preregistration.md` tested *low-vol factor* additions (FAIL), whereas covariance-shrunk portfolio weighting (HRP/min-var on the fixed R0 basket) has not been pre-registered or failed. Keep strictly info-only unless pre-registered.

## 10. Ledoit–Wolf Quadratic-Inverse Shrinkage (`oledoit/covShrinkage` v1.1 / `matzhaugen/analytic_shrinkage`)

- **Link:** https://github.com/oledoit/covShrinkage (Python PyPI port: https://github.com/matzhaugen/analytic_shrinkage)
- **Date:** 2022–2026 (v1.1.0 reference implementation; BSD/MIT)
- **Summary:** Implements Ledoit & Wolf's analytical nonlinear shrinkage and Quadratic-Inverse Shrinkage (QIS), correcting each sample eigenvalue individually in closed form rather than applying one global linear shrinkage intensity. Dramatically reduces covariance condition-number blowup when asset count $p$ approaches or exceeds return window length $n$.
- **Concrete use for THIS project:** Drop-in ~50-line pure-NumPy replacement for `np.cov(mat.to_numpy(), rowvar=False)` in `core/portfolio.py::calculate_returns_and_covariance` (`window_days=60`, `MIN_COMMON_OBS=15` vs. 50–110 held tickers — **Roadmap Step 5**) with zero heavy solver dependencies.
- **Type:** Infrastructure (when upgrading info-only risk diagnostics / HRP display in `core/portfolio.py`); **New testable idea (+1 `N_sel`; requires pre-registration)** if used to change live portfolio weights.
- **Effort:** S
- **Failed-idea check:** Passed — statistical covariance estimator for Roadmap Step 5; distinct from all failed alpha/timing/weighting studies in README.

## 11. Cvxportfolio (`cvxgrp/cvxportfolio` v1.5) — Convex Square-Root Impact Model & Cost-Model Cross-Check

- **Link:** https://github.com/cvxgrp/cvxportfolio (Docs: https://www.cvxportfolio.com/)
- **Date:** July 2025 (v1.5.1; active 2026 CI; Apache-2.0)
- **Summary:** Stanford/BlackRock open-source framework for single- and multi-period convex portfolio optimization and backtesting with explicit bid-ask spread, $3/2$-power (square-root price) market impact, holding costs, and ADV participation caps (`MaxTrade`/`ParticipationRate`). Separates cost model definitions cleanly from `StockMarketSimulator` execution.
- **Concrete use for THIS project:** Directly maps to **Roadmap Step 5** (ADV-based position limits + square-root market impact) and serves as an independent verification benchmark against our custom `core/portfolio_backtest.py` (`Costs.impact`, `PARTICIPATION_FLAG = 0.10`) and capacity stress tests (`quant_review_followups_preregistration.md` 10M TL / 3× cost scenario).
- **Type:** Infrastructure (independent cost/capacity cross-check for `core/portfolio_backtest.py`); **New testable idea (+1 `N_sel`; requires pre-registration)** if testing turnover-penalized / impact-aware rebalancing against EW R0.
- **Effort:** M
- **Failed-idea check:** Passed — `exit_rules_preregistration.md` tested heuristic rank-buffer exits (FAIL), not convex ADV-capped / impact-aware sizing; still must be pre-registered before touching live weights.

## 12. Polars 2.0 (`pola-rs/polars`) — Lazy `join_asof` + Parquet for Deterministic PIT Panel Rebuilds

- **Link:** https://github.com/pola-rs/polars (Docs: https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.join_asof.html)
- **Date:** 2026 (Polars v1.43–v2.0.0; MIT)
- **Summary:** Rust-powered DataFrame engine with lazy Parquet scanning (`scan_parquet`), streaming `sink_parquet`, and grouped `join_asof(..., strategy="backward", tolerance=...)` that enforces explicit staleness ceilings. Integrates directly with Pandera (`Finding #2`) and cuts multi-year panel build time and RAM by an order of magnitude vs. Pandas.
- **Concrete use for THIS project:** Optional engine upgrade for `core/pit_panel.py` (`build_monthly_factors`) and `scripts/build_pit_panel.py` (**P1-1**, **P2-5** financials rebuild) if DuckDB SQL (`Finding #6`) is not desired; native `tolerance` parameter prevents stale fundamentals from silently carrying forward across missing quarters.
- **Type:** Infrastructure
- **Effort:** M
- **Failed-idea check:** Passed — pure execution engine for existing PIT rules; zero model/rule changes.

## 13. Microsoft Qlib PIT Storage Pattern (`microsoft/qlib` v0.9.8) — Append-Only Financial Vintage Indexing

- **Link:** https://github.com/microsoft/qlib (PIT docs: https://qlib.readthedocs.io/en/latest/component/data.html)
- **Date:** 2026 (v0.9.8; MIT)
- **Summary:** Qlib includes a dedicated Point-in-Time (PIT) fundamental storage layout indexing `(date, period, value, _next)` linked records so queries resolve the exact first-published vs. restated figure known on any historical date. Recent v0.9.8 also hardened expression/artifact deserialization (`trusted=True`).
- **Concrete use for THIS project:** Do **not** migrate the whole codebase to Qlib's heavy ML/workflow stack; instead borrow Qlib's compact vintage-chain schema for **P2-3 / P2-4** (`scripts/build_first_published.py`, restatements 2014–2022) inside Parquet/DuckDB so first-published and restated values coexist queryably without rebuilding separate panel directories (`data/research/fp/` vs `pre_point_in_time/`).
- **Type:** Infrastructure
- **Effort:** S (pattern adoption) / L (full framework migration — **not recommended**)
- **Failed-idea check:** Passed — bitemporal storage pattern only; avoids Qlib's ML alpha-mining features (which would inflate `N_sel` and contradict this repo's pre-registration discipline).

## 14. Riskfolio-Lib (`dcajasn/Riskfolio-Lib` v7.4) — Mature CVXPY Hierarchical & Constraint Portfolio Library

- **Link:** https://github.com/dcajasn/Riskfolio-Lib
- **Date:** November 4, 2026 (v7.4.1; BSD-3-Clause)
- **Summary:** Actively maintained CVXPY-backed portfolio optimization library supporting HRP, HERC, NCO, custom/shrunk covariance matrices, Kelly sizing, and linear turnover/asset-class/sector caps. Stronger active maintenance cadence in 2025–2026 than `PyPortfolioOpt`, though slightly heavier API than `skfolio`.
- **Concrete use for THIS project:** Alternative to `skfolio` (`Finding #9`) for **Roadmap Step 5** in `core/portfolio.py` if linear turnover constraints, CVaR/CDaR risk measures, or custom hierarchical clustering matrices are needed alongside the existing 30% sector cap (`apply_sector_caps`).
- **Type:** Infrastructure (info-only diagnostics in `core/portfolio.py`); **New testable idea (+1 `N_sel`; requires pre-registration)** if applied to live rule R0 weights.
- **Effort:** M
- **Failed-idea check:** Passed — portfolio construction tooling only; no overlap with failed factor, timing, or macro rules.

---

## Evaluated & Rejected / Lower-EV Tools (Do Not Adopt Now)

| Tool (Primary Link & 2025–2026 Status) | Category | Verdict for THIS Project |
|---|---|---|
| **NautilusTrader** ([nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader), v2.0.0rc9, 2026) | Backtest (Event-driven) | **Overkill.** Rust L1/L2/L3 order-book & tick execution parity is irrelevant for monthly-rebalanced EOD BIST equities; our audited 216-line `core/portfolio_backtest.py` already models next-close fills, half-spread, sqrt impact, limit-day locks, and delisting haircuts transparently. |
| **Zipline-Reloaded** ([stefan-jansen/zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded), Py 3.11–3.14, 2025–2026) | Backtest (Event-driven) | **Wrong fit.** Heavy US-equity bundle/calendar machinery (`exchange_calendars`, `pandas < 3.0` constraint) adds maintenance tax for BIST custom rules (IAS 29, ±10% daily limit locks, TCMB policy-rate cash). |
| **VectorBT** ([polakowo/vectorbt](https://github.com/polakowo/vectorbt), OSS vs. PRO, 2025–2026) | Backtest (Vectorized) | **Do not adopt.** OSS edition has sparse maintenance (active features/callbacks gated in paid PRO); flat vectorized fees cannot natively express path-dependent stuck-on-limit positions, and fast parameter sweeping actively invites `N_sel` data-mining inflation. |
| **bt** ([pmorissette/bt](https://github.com/pmorissette/bt), Py ≥ 3.9, 2024–2026) | Backtest (Portfolio tree) | **Redundant.** Clean for simple fixed-commission allocation trees, but lacks native sqrt market impact, ADV participation caps, and BIST limit-day lock rules already working in `core/portfolio_backtest.py`. |
| **PyPortfolioOpt** ([PyPortfolio/PyPortfolioOpt](https://github.com/PyPortfolio/PyPortfolioOpt), v1.6.0, Feb 2026) | Portfolio construction | **Superseded.** Slower feature cadence; `skfolio` (`Finding #9`) and `Riskfolio-Lib` (`Finding #14`) offer richer covariance denoising, hierarchical models, and active 2026 maintenance. |
| **Great Expectations** ([great-expectations/great_expectations](https://github.com/great-expectations/great_expectations), v1.25.0, 2026) | Data validation | **Too heavy.** Enterprise Data Docs + checkpoint/SQLAlchemy scaffolding is unnecessary overhead for a single-maintainer Python CI pipeline; **Pandera** (`Finding #2`) + **Pydantic v2** (`Finding #7`) deliver 95% of the value at 10% of the footprint. |
| **ArcticDB** ([man-group/ArcticDB](https://github.com/man-group/ArcticDB), v5.x, 2025–2026) | PIT data store | **License & git friction.** Business Source License 1.1 restricts commercial/production use until 2-year Apache 2.0 conversion (v5.0–5.1 convert Oct–Nov 2026; newer releases stay BSL until 2027+), and binary LMDB stores fit poorly with git/CI compared to **DuckDB + Parquet** (`Finding #6`). |
| **Pointblank** ([posit-dev/pointblank](https://github.com/posit-dev/pointblank), v1.2.0, 2026) | Data validation | **Secondary option.** Clean threshold-based validation and HTML reports, but Pandera (`Finding #2`) integrates tighter with typed Python functions and pytest contracts in `core/`. |
