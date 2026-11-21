# BIST Quant Scouting Synthesis & Skeptical Audit (`SUMMARY.md`)

**Date:** 2026-11-22 · **Role:** Synthesizer & Skeptic · **Baseline:** Live rule `R0-2026-10-12` (`core/rotation.py`, monthly equal-weight top-20% non-financials by point-in-time `value_sn`; `docs/plan_2026-10-26.md` `P0`–`P4`; trial ledger `N_sel = 86` in `data/research/trial_ledger.json`, `~87` including `P4-1`; `DSR = 0.10–0.12`).

---

## 1. Web-Fetch Verification of the Most Promising Primary Sources

Ten primary URLs across `docs/scouting/academic.md`, `data.md`, and `engineering.md` were live-fetched and verified against their claimed contents:

| # | Source & Fetched URL | Status | Verification & Skeptical Audit Result |
|---:|---|---|---|
| 1 | **Benhamou et al. (2026-11-02)** — [arXiv:2611.03384](https://arxiv.org/abs/2611.03384) | **VERIFIED** | Exists (accepted ICAIF 2026). Confirms *Promote* e-process (weighted Ville inequality) yields 0.0% false family crossings vs. 94.5% under repeated fixed-sample peeking. Ideal for `scripts/forward_record_report.py` (**P0-3 / P4-2**). |
| 2 | **Dursun (2026-10-23)** — [SSRN 7662821](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7662821) | **VERIFIED** | Exists (*Multi-Factor Investing in Borsa Istanbul*, 24 pp.). Confirms 17-year PIT BIST 5-factor strategy's `+4.4%/yr` CAPM alpha vs. XU100 ($t=2.08$) vanishes against a volatility-matched equal-weighted universe (`−0.4%/yr`, 95% CI `[−6.3%, +5.5%]`). |
| 3 | **Gençay (2026-10-14)** — [arXiv:2611.14539](https://arxiv.org/abs/2611.14539) | **VERIFIED** | Exists (*Can a Search Hold Its Own Bar?*). Proves the *variance-dilution exploit* (mediocre trials shrink $\sqrt{V[\text{SR}]}$ faster than the trial multiplier grows, lowering $\text{SR}_0$; 100 nominal trials $\approx 6\text{–}8$ independent streams) and validates a frozen variance floor $V_{\min}$ + monotone $\text{SR}_0$. |
| 4 | **López de Prado et al. (2026-03-25 / 2026-08-30)** — [github.com/zoonek/2025-sharpe-ratio](https://github.com/zoonek/2025-sharpe-ratio) & [SSRN 7198158](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7198158) | **VERIFIED** | Both exist. Repo contains full Python replication (`functions.py`) for non-Normal AR(1) Sharpe inference, $N_{\text{eff}}$, and MinTRL; SSRN 7198158 (60 pp.) formalizes location-scale `DSR-LS` for fat-tailed returns. |
| 5 | **Uzunlar, Atıcı & Çevik (2025-06-16)** — [tisej.com/index.php/pub/en/article/view/1518](https://tisej.com/index.php/pub/en/article/view/1518) | **VERIFIED** | Exists (DOI `10.63556/tisej.2025.1518`). Confirms BIST-100 positive-NMPGL (*Net Monetary Position Gain/Loss*) stocks significantly outperform negative-NMPGL stocks around TMS 29 announcements. |
| 6 | **borsapy v0.10.0 (2026-05-04)** — [github.com/saidsurucu/borsapy/releases/tag/v0.10.0](https://github.com/saidsurucu/borsapy/releases/tag/v0.10.0) | **VERIFIED** | Exists. Confirms `evds2.tcmb.gov.tr` was shut down at end-2025 and `borsapy` natively wraps `evds3.tcmb.gov.tr` (`bp.evds_series()`, 1,000-row auto-chunking, `EVDS_API_KEY`). |
| 7 | **TrailingEdge & Avci (2024–2026)** — [github.com/caganco/trailingedge](https://github.com/caganco/trailingedge) & [RePEc:taf:eurjfi:v:30:y:2024:i:6:p:549-574](https://ideas.repec.org/a/taf/eurjfi/v30y2024i6p549-574.html) | **VERIFIED** | Both exist. `trailingedge` (MIT, May 2026) unpacks KAP's Java-serialized `byte[]` PDF wrapper for SPK II-15.1 `DKB` insider tables; Avci (*EJF* 2024) documents `+6.58%` 1-yr abnormal returns across ~65,000 BIST insider trades. |
| 8 | **kap-mcp v0.1.0 (2026-04-25)** — [pypi.org/project/kap-mcp/](https://pypi.org/project/kap-mcp/) vs. `github.com/atayalcinb/KAP-MCP-TR` | **PARTIAL (PyPI LIVE / GitHub 404)** | PyPI package `kap-mcp==0.1.0` exists and verifies 100% parser coverage (572 IFRS, 27 BDDK, 6 Insurance templates in Python 3.12), but its linked GitHub repo `atayalcinb/KAP-MCP-TR` returns `404 / CRAWL_NOT_FOUND`. Must inspect the PyPI sdist tarball directly. |
| 9 | **Zuluaga-Rendón & Agudelo (2025-02-02)** — [RePEc:eee:glofin:v:68:y2025:i:c:s1044028325000997](https://ideas.repec.org/a/eee/glofin/v68y2025ics1044028325000997.html) | **VERIFIED** | Exists (*Global Finance Journal* Vol. 68, DOI `10.1016/j.gfj.2025.101172`). Confirms Cash Flow to Price (`CFO/P`) and `E/P` are primary cross-sectional return drivers in high-inflation LatAm markets. |
| 10 | **Hishel / Pandera / skfolio** — [github.com/karpetrosyan/hishel](https://github.com/karpetrosyan/hishel), [github.com/unionai-oss/pandera](https://github.com/unionai-oss/pandera), [arXiv:2507.04176](https://arxiv.org/abs/2507.04176) | **VERIFIED** | All 3 exist and match claims (RFC 9111 `httpx` caching, DataFrame statistical contracts, and scikit-learn-native shrunk covariance/HRP). |

---

## 2. Skeptical Pruning Log (Removed Duplicates, Failed Ideas & Non-PIT Items)

Out of 41 raw items across `academic.md` (14), `data.md` (13), and `engineering.md` (14), **31 were merged or rejected**:

1. **Rejected — Already Failed in README Scorecard:**
   - *MKK VAP Foreign Custody Share (`data.md` #5 partial):* 3-month foreign ownership change (`dfor3`) and level (`for_t`) already failed in `foreign_ownership_preregistration.md` (sign flip between discovery and holdout). Only PIT free-float validation (`HAO_PD` for **P2-2 / P4-1**) is retained.
   - *TCMB EVDS3 Sectoral Inflation Expectations & Weekly Foreign Flows as Predictive Signals (`data.md` #12):* Macro and industrial-production predictors of BIST direction all failed (`macro_drivers_preregistration.md`, `industrial_production_preregistration.md`, OOS $R^2 < 0$). Retained strictly as a zero-trial data pipe for CPI (`C1`) and `policy_rate`.
   - *Multi-Factor Blends & Trend/Timing Gates (`academic.md` #6 Dursun 5-factor + trend gate; excluded timing papers):* 52-week high, reversal, quality/Piotroski, low-vol blends, and 22 entry/exit/trend/SMC timing rules already failed (`long_term_preregistration.md`, `trend_timing_preregistration.md`, `smc_timing_preregistration.md`).
2. **Rejected — Not Point-in-Time (PIT) Feasible or Regime-Broken:**
   - *BIST Analyst Consensus Targets & Ratings (`hedeffiyat.com.tr` / `Yatırımcı.AI`, `data.md` #9):* No free historical PIT archive exists for 2013–2026 backtesting (only live snapshots of ~98 large caps, missing the small/mid-cap segment where `value_sn` earns its edge).
   - *Takasbank ÖPP Securities Lending & BIST 50 Short-Selling (`data.md` #8):* Short-selling was banned across BIST from Feb 2023 to Jan 2, 2025 and remained restricted to BIST 50 thereafter, leaving a 2-year hole in our 2021–2026 holdout and near-zero overlap with non-BIST-50 `value_sn` holdings.
   - *KAP Monthly Mutual Fund Holdings (`Portföy Dağılım Raporu` / Fonoloji, `data.md` #7):* `fonoloji.com/v1` provides current/forward API access rather than a clean 2013–2026 PIT stock-level panel; backfilling 13 years of unstandardized fund PDFs carries severe fund-survivorship bias and Effort L.
   - *Intangible-Adjusted Book-to-Market `iB/M` (`academic.md` #14, Vincenz 2024):* Perpetual-inventory SG&A capitalization (`INT_t = (1−δ)INT_{t−1} + SG&A_t`) requires 5+ years of uninterrupted pre-sample SG&A per stock and mixes pre-2023 nominal SG&A with post-2023Q4 IAS 29 restated tangible equity.
   - *Commercial / Unverified Feeds (`data.md` #3 paid BIST DataStore archives, `data.md` #11 paid BilancoVeri with unverified IAS 29 restatement vintage, `data.md` #13 Matriks/Foreks terminals, `engineering.md` #13 Qlib framework):* Unjustified cost or restatement-leakage risk for a 1M TL monthly portfolio.
3. **Deduplicated & Consolidated:**
   - Merged 5 overlapping multiple-testing/DSR/PBO papers (`academic.md` #1, #2, #5, #7, #9) into **Action 3** (`core/research_stats.py`).
   - Merged sequential forward-record testing (`academic.md` #3 *Promote*) and volatility-matched EW confidence bounds (`academic.md` #6 Dursun) into **Action 4** (`scripts/forward_record_report.py` & `scripts/research_total_return_benchmarks.py`).
   - Merged CI KAP bypass (`data.md` #1), dead-man's-switch alerting (`engineering.md` #1), and off-peak cron dispatch (`engineering.md` #5) into **Action 1** (`.github/workflows/daily-screener.yml`).
   - Merged HTTP/disk caching (`engineering.md` #3 `hishel`, #8 `diskcache`), per-provider rate limiting (`engineering.md` #4 `PyrateLimiter` + `tenacity`), direct KAP statement parsing (`data.md` #2 `kap-mcp`), and bitemporal `ASOF JOIN` (`engineering.md` #6 DuckDB) into **Action 6** (`core/live_data.py`, `scripts/build_first_published.py`, `core/pit_panel.py`).
   - Consolidated 4 portfolio-optimization libraries (`engineering.md` #9 `skfolio`, #10 `covShrinkage` QIS, #11 `cvxportfolio`, #14 `Riskfolio-Lib`) into an information-only note under **Action 5 / Roadmap Step 5** (changing live R0 equal weights to HRP/min-var would cost `+1 N_sel` and is not recommended at `N_sel = 86`).

---

## 3. Top 10 Ranked Actions by Expected Value

### Part (a) — Infrastructure & Data Actions (`0 N_sel` Cost · No Pre-Registration Needed)

#### 1. Sanctioned KAP Feed Outside Blocked CI + Off-Peak Cron & Dead-Man's-Switch (`kap_feed` + `Healthchecks`)
- **Link:** [KAP REST API Integration Spec (PDF)](https://kap.org.tr/tr/api/about/content-file/8a019492945fbe080194b26d8bed4873) · [github.com/oguzhanozfe/kap-watcher](https://github.com/oguzhanozfe/kap-watcher) · [github.com/healthchecks/healthchecks](https://github.com/healthchecks/healthchecks) · [Cloudflare Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
- **Date:** 2024-11-27 (KAP REST spec); 2026-11-17 (`kap-watcher` WAF check & Healthchecks v5.0)
- **Summary (2 lines):** `www.kap.org.tr` sits behind a perimeter WAF that drops GitHub Actions datacenter IPs (`kap_missing_share = 0.98` in CI, burning retry time), while GitHub `on: schedule` at peak `30 15 * * *` suffers 30–60+ minute start delays and silent drops. Running a daily 18:15 Istanbul local/TR cron to push `data/kap_feed/latest.parquet` and adding a Healthchecks dead-man's-switch heartbeat in `.github/workflows/daily-screener.yml` eliminates CI KAP timeouts and guarantees immediate alerting if a monthly `decisions.jsonl` rebalance fails to lock.
- **Concrete use for THIS project:** Directly closes **Plan P3-3** (`kap_missing_share = 0.98`), **Plan P0-2** (`[timing]` / `_KapBreaker` delays in `core/kap_api.py`), and protects **Plan P0-3** (`data/forward_record/decisions.jsonl` in `.github/workflows/daily-screener.yml`).
- **Type & `N_sel` cost:** Infrastructure (`0 N_sel` cost; no trading rule change).
- **Effort:** S
- **README failed-idea & PIT check:** Clear — `kap_report_dates_preregistration.md` showed `value_sn` is *lag-sensitive* (`+6.87%` $\to$ `+5.26%/yr`), making real KAP publication dates essential PIT infrastructure rather than a failed signal.

#### 2. Native `borsapy` v0.10–0.11 TCMB EVDS3 & `Eurobond.history()` Migration for CPI (`C1`), Policy Rate & Sovereign Spread
- **Link:** [github.com/saidsurucu/borsapy/releases/tag/v0.10.0](https://github.com/saidsurucu/borsapy/releases/tag/v0.10.0) · [github.com/saidsurucu/borsapy/releases/tag/v0.8.7](https://github.com/saidsurucu/borsapy/releases/tag/v0.8.7) · [evds3.tcmb.gov.tr](https://evds3.tcmb.gov.tr/)
- **Date:** 2026-04-17 (`v0.8.7`) · 2026-05-04 (`v0.10.0`) · 2026-08-07 (`v0.11.0`)
- **Summary (2 lines):** TCMB retired legacy `evds2.tcmb.gov.tr` at end-2025, and `borsapy>=0.11.0` (already pinned in `requirements.txt`) natively wraps EVDS3 (`bp.evds_series()`) and cached Ziraat-sourced `Eurobond.history()`. Replacing fragile web scrapers in `core/live_data.py` eliminates bogus `policy_rate() == 7.0` fallbacks, prevents CPI fetch failures from dropping live runs from `C1` to `C0`, and stabilizes the sovereign-spread risk gauge.
- **Concrete use for THIS project:** Upgrade `core/live_data.py::live_macro_snapshot()`, `core/pit_panel.py::_cpi_index_cached()` (IAS 29 `C1` constant-purchasing-power TTM deflator), and `core/sovereign_spread.py` (**Plan P0-2** `[sovereign_spread]`).
- **Type & `N_sel` cost:** Infrastructure (`0 N_sel` cost; data reliability upgrade).
- **Effort:** S
- **README failed-idea & PIT check:** Clear — hardens data pipes for `ADOPT_C1` (`ias29_constant_unit_ttm_preregistration.md`) and the **only confirmatory PASS** in README (`sovereign_spread_preregistration.md`, contemporaneous risk gauge); does not test macro market timing (`macro_drivers_preregistration.md`).

#### 3. Search-Adjusted Sharpe Inference, Variance-Dilution Guard & Purged CSCV (`DSR-LS`, $N_{\text{eff}}$, `V_min`, `embargo_months=1`)
- **Link:** [github.com/zoonek/2025-sharpe-ratio](https://github.com/zoonek/2025-sharpe-ratio) ([SSRN 5520741](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5520741)) · [SSRN 7198158](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7198158) · [arXiv:2611.14539](https://arxiv.org/abs/2611.14539) · [DOI 10.1016/j.knosys.2024.112477](https://dl.acm.org/doi/10.1016/j.knosys.2024.112477)
- **Date:** 2026-03-25 (López de Prado et al.) · 2026-08-30 (López de Prado & Porcu) · 2026-10-14 (Gençay) · 2024-12-03 (Arian et al.)
- **Summary (2 lines):** Location-only `DSR-L` evaluated at raw correlated trial count `N_sel = 86` on fat-tailed BIST active returns (kurtosis 4.20) miscalibrates tail p-values and is vulnerable to Gençay's *variance-dilution exploit*, where adding mediocre trials shrinks $\sqrt{V[\text{SR}]}$ faster than the trial multiplier grows. Upgrading `core/research_stats.py` with location-scale `DSR-LS`, cluster-estimated effective trials $N_{\text{eff}}$, a frozen variance floor $V_{\min}$ (monotone $\text{SR}_0$), and a 1-month purge embargo in `pbo_cscv` hardens multiple-testing inference.
- **Concrete use for THIS project:** Update `core/research_stats.py` (`deflated_sharpe`, `pbo_cscv`) and `data/research/trial_ledger.json` before re-running **Plan P1-2** (`scripts/research_quant_review.py` on `data/research/fp/`) and setting the MinTRL / expectation horizon in **Plan P1-3** (`config/live_rule.json`).
- **Type & `N_sel` cost:** Infrastructure (`0 N_sel` cost; statistical reporting on locked rule R0).
- **Effort:** S
- **README failed-idea & PIT check:** Clear — directly refines `B2` (DSR) and `B3` (CSCV PBO) in `quant_review_followups_preregistration.md` without altering `core/rotation.py`.

#### 4. Anytime-Valid Forward-Record Sequential Test (`Promote` e-Process) & Volatility-Matched EW Alpha Bounds
- **Link:** [arXiv:2611.03384](https://arxiv.org/abs/2611.03384) (Benhamou et al., ICAIF 2026) · [SSRN 7662821](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7662821) (Dursun 2026)
- **Date:** 2026-11-02 (`Promote`) · 2026-10-23 (Dursun BIST study)
- **Summary (2 lines):** Monitoring `data/forward_record/decisions.jsonl` month by month with fixed-horizon Newey-West $t$-tests suffers severe optional-stopping inflation (94.5% false crossings in Benhamou et al.), whereas a cost-aware *Promote* e-process remains statistically valid under indefinite monthly peeking. In parallel, Dursun (2026) shows on 17 years of PIT BIST statements that apparent CAPM alpha vs. XU100 disappears against a volatility-matched equal-weighted universe (`−0.4%/yr`, 95% CI `[−6.3%, +5.5%]`), motivating explicit vol-matched EW upper-bound reporting.
- **Concrete use for THIS project:** Add an e-process sequential wealth tracker to `scripts/forward_record_report.py` (**Plan P0-3, P1-3, P4-2**) for live `R0` and shadow sleeves (`V1` no-S/P, `P2` financials), and report volatility-matched `EW net` 95% confidence bounds in `scripts/research_total_return_benchmarks.py` (**Plan P1-2**).
- **Type & `N_sel` cost:** Infrastructure (`0 N_sel` cost; forward-record & benchmark evaluation).
- **Effort:** S
- **README failed-idea & PIT check:** Clear — Dursun's 5-factor + trend-gate trading strategy is explicitly *rejected* (already failed in README); only its vol-matched EW benchmark protocol and Benhamou et al.'s sequential e-process are adopted to support **Plan P4-2**.

#### 5. Boundary Data Contracts (`Pandera` + `Pydantic v2`) for Vendor IAS 29 Drift (`P3-1`), Market-Cap Cross-Check (`P3-2`) & `decisions.jsonl` (`P0-3`)
- **Link:** [github.com/unionai-oss/pandera](https://github.com/unionai-oss/pandera) · [github.com/pydantic/pydantic](https://github.com/pydantic/pydantic) · *(Info-only Step 5 companion: [arXiv:2507.04176](https://arxiv.org/abs/2507.04176) `skfolio` / `covShrinkage` QIS)*
- **Date:** 2026 (Pandera v0.36.0; Pydantic v2.x; `skfolio` v1.13)
- **Summary (2 lines):** Pandera provides declarative DataFrame contracts for Pandas/Parquet tables (`available_at > period_end`, YoY discrete-quarter ratio bounds), while Pydantic v2 enforces strict Rust-backed schema validation on append-only JSONL records. Adding them catches silent İş Yatırım IAS 29 re-expression convention changes, >10% TradingView vs. İş Yatırım market-cap divergences, and malformed `decisions.jsonl` lines before they enter git history.
- **Concrete use for THIS project:** Implement **Plan P3-1** (vendor consistency alarm) and **Plan P3-2** (`bp.Screener()` vs. TradingView market-cap check) in `core/run_health.py`, enforce PIT panel schemas in `core/pit_panel.py` (**Plan P1-1**), and validate Schema 2 records in `core/forward_record.py` (**Plan P0-3**). *(Optionally replace unshrunk 60-day `np.cov` in `core/portfolio.py` with analytical QIS / `skfolio` `LedoitWolf` for **Roadmap Step 5** strictly as an information-only diagnostic.)*
- **Type & `N_sel` cost:** Infrastructure (`0 N_sel` cost; monitoring and validation contracts only).
- **Effort:** S
- **README failed-idea & PIT check:** Clear — enforces PIT data hygiene and `vendor_vs_kap_audit.md` safeguards without touching `value_sn` selection or equal weighting.

#### 6. Persistent HTTP/Vintage Caching (`Hishel` + `DiskCache`), Per-Provider Rate Limiting (`PyrateLimiter`) & Direct KAP Excel/XBRL Parsing (`kap-mcp` + DuckDB `ASOF JOIN`)
- **Link:** [github.com/karpetrosyan/hishel](https://github.com/karpetrosyan/hishel) · [github.com/vutran1710/PyrateLimiter](https://github.com/vutran1710/PyrateLimiter) · [pypi.org/project/kap-mcp/](https://pypi.org/project/kap-mcp/) · [duckdb.org/docs/stable/sql/query_syntax/from#asof-joins](https://duckdb.org/docs/stable/sql/query_syntax/from#asof-joins)
- **Date:** 2026-04-25 (`kap-mcp` v0.1.0 on PyPI) · 2026-10 (DuckDB 2.0 LTS, Hishel v2.0, PyrateLimiter v4)
- **Summary (2 lines):** `core/live_data.py` currently relies on process-only `@lru_cache` and a coarse 4-worker cap (taking 2.5–4.5h per CI run), while `scripts/build_first_published.py` scrapes KAP HTML at 3.6–15 s/page and lacks BDDK/Insurance statement templates. Persisting immutable historical `httpx` responses with `hishel`/`diskcache`, pacing providers independently via `PyrateLimiter` + jittered `tenacity`, and adopting `kap-mcp`'s standalone `openpyxl`/`lxml` parsers (from the verified PyPI sdist) with DuckDB bitemporal `ASOF JOIN` accelerates both daily runs and historical first-published panel builds.
- **Concrete use for THIS project:** Cut daily CI runtime in `core/live_data.py` (**Plan P0-2**), promote and automate `data/research/fp/` in `scripts/build_pit_panel.py` (**Plan P1-1**), resolve the 33 `unknown` IAS 29 firms (**P2-1**), validate `undo_reexpression` hit rates (**P2-3**), batch pre-2023 restatements (**P2-4**), and rebuild `financials_factors_monthly.parquet` (**P2-5**).
- **Type & `N_sel` cost:** Infrastructure (`0 N_sel` cost).
- **Effort:** M
- **README failed-idea & PIT check:** Clear — directly resolves the first-published vs. vendor-restated data limitation documented in `vendor_vs_kap_audit.md` and `first_published_panel.md`.

---

### Part (b) — New Research Ideas (Each Requires Pre-Registration & Costs `+1 N_sel`; Run Only After `P1`)

> **Discipline gate:** Current stock-selection trial count is `N_sel = 86` (`DSR = 0.10–0.12`). Each idea below costs **`+1 N_sel`**, must be pre-registered before computing returns, and must be tested on the promoted `data/research/fp/` baseline (**Plan P1-1**) using the fixed discovery ($t > 3$) / holdout ($t > 2$) / paired non-inferiority protocol.

#### 7. Point-in-Time Free-Float Market-Cap Filter (`HAO_PD` + MKK VAP Validation — Plan `P4-1`)
- **Link:** [MKK VAP Free Float in Shares Data](https://www.vap.org.tr/en/free-float-shares-data) · [MKK VAP Portal Release](https://www.mkk.com.tr/en/news/data-analysis-platform-vap-opens-turkiyes-capital-markets-data-to-the-world-with-english-language-option) · Internal basis: [`docs/research/market_cap_source.md`](docs/research/market_cap_source.md)
- **Date:** 2026-06-22 (MKK VAP English portal; İş Yatırım HisseTekil `HAO_PD` daily series available from 2012)
- **Summary (2 lines):** Ultra-low free-float BIST stocks are prone to cornering and limit-lock manipulation, an execution hazard `portfolio_backtest_preregistration.md` could not test before historical free-float market value existed. Using daily point-in-time free-float market cap (`HAO_PD` from İş Yatırım HisseTekil, cross-checked against MKK VAP SPK 5/157 custody ratios and gap-filled for **P2-2**), we can test a single pre-registered rule excluding the bottom decile of free-float market value within the liquid universe.
- **Concrete use for THIS project:** Execute **Plan P4-1** (`docs/plan_2026-10-26.md`) via a pre-registered study (`docs/research/free_float_filter_preregistration.md`) on `data/research/fp/` (`market_cap_monthly.parquet` `HAO_PD` column), comparing costed net active return and limit-day lock incidence against `R0`.
- **Type & `N_sel` cost:** **New testable idea — costs `+1 N_sel` (`N_sel: 86 → 87`), requires pre-registration.**
- **Effort:** S (`HAO_PD` is already fetched in `scripts/fetch_isyatirim_market_cap.py`)
- **README failed-idea & PIT check:** Not failed in README (`portfolio_backtest_preregistration.md` tested total-market-cap floor `F1` and 50% volume floor `F2`, never free-float market cap `HAO_PD`; strictly exclude MKK foreign-share `dfor3` which failed in `foreign_ownership_preregistration.md`). 100% PIT feasible from 2012.

#### 8. Operating Cash-Flow Yield (`CFO/P`) Replacing `S/P` in `value_sn`
- **Link:** [RePEc:eee:glofin:v:68:y:2025:i:c:s1044028325000997](https://ideas.repec.org/a/eee/glofin/v68y2025ics1044028325000997.html) (Zuluaga-Rendón & Agudelo, *Global Finance Journal* 2025) · [NBER Working Paper w32364](https://www.nber.org/papers/w32364) (Binz, Graham & Kubic 2024)
- **Date:** 2025-02-02 (Zuluaga-Rendón & Agudelo) · 2024-04-18 (Binz, Graham & Kubic)
- **Summary (2 lines):** Zuluaga-Rendón & Agudelo (2025) identify Cash Flow to Price (`CFO/P`) and `E/P` as top cross-sectional predictors across high-inflation emerging markets, while Binz et al. (2024) show inflation shifts valuation weight toward near-term cash/earnings flows over top-line sales. In our own panels, `S/P` (`sp`) is the weakest leg of `value_sn` and its Rank-IC flipped negative under IAS 29 (`value_ablation_preregistration.md`), whereas operating cash flow (`İşletme Faaliyetlerinden Nakit Akışları`) is available PIT across 2013–2026 and is immune to non-cash IAS 29 monetary gains and depreciation restatements.
- **Concrete use for THIS project:** After **Plan P1-1**, extract PIT YTD operating cash flow (`İşletme Faaliyetlerinden Nakit Akışları`) in `scripts/build_pit_panel.py` / `core/pit_panel.py::value_ratios` (`C1` constant-unit TTM `cfo / mcap`) and pre-register **one** trial comparing `bm + ep + cfo_p + ey` against `V0` (`bm + ep + sp + ey`) across both discovery (2013–2020) and holdout (2021–2026).
- **Type & `N_sel` cost:** **New testable idea — costs `+1 N_sel` (`N_sel: 87 → 88`), requires pre-registration.**
- **Effort:** M
- **README failed-idea & PIT check:** Not failed in README (`bm`, `ep`, `sp`, `ey`, `gpa`, `roe`, `op_a`, `sue`, `dividend_yield`, and `st_debt_coverage` were tested; `CFO/P` was never tested, and `core/sloan.py` accrual is information-only and untested). 100% PIT feasible across the full 2013–2026 panel.

#### 9. IAS 29 Net Monetary Position Gain/Loss (NMPGL) Stripping from `E/P` (`ep_ex_nmpgl`)
- **Link:** [tisej.com/index.php/pub/en/article/view/1518](https://tisej.com/index.php/pub/en/article/view/1518) (Uzunlar, Atıcı & Çevik 2025, DOI `10.63556/tisej.2025.1518`) · [IFRS EEG / FACPCE IAS 29 Review (PDF)](https://www.ifrs.org/content/dam/ifrs/meetings/2023/october/eeg/5-hyperinflation-in-argentina-facpce-october-2023-eeg.pdf)
- **Date:** 2025-06-16 (Uzunlar et al.) · 2023-10 (FACPCE IAS 29 review)
- **Summary (2 lines):** Uzunlar, Atıcı & Çevik (2025) show on BIST-100 equities that TMS 29 / IAS 29 *Net Monetary Position Gain/Loss* (`Net Parasal Pozisyon Kazançları (Kayıpları)`) significantly drives announcement returns, because inflation gains on net monetary debt boost headline net income without creating cash flow. Stripping NMPGL from TTM net income in `ep` directly tests whether debt-driven monetary gains explain why `value_sn` weakened in the 2024-05+ IAS 29 window (`+2.93%/yr`, $t = 0.76$ on `data/research/fp/`).
- **Concrete use for THIS project:** First run a zero-trial line-item coverage audit in `scripts/build_first_published.py` (**Plan P2-3**) for `Net Parasal Pozisyon Kazançları (Kayıpları)` on 2023Q4+ KAP filings; if coverage is $\ge 85\%$, pre-register **one** IAS 29-window study testing `ep_ex_nmpgl` inside `core/pit_panel.py::value_ratios` (closing `README.md` Known Limitations line 764 and `docs/research/sector_specific_notes.md` §3).
- **Type & `N_sel` cost:** **New testable idea — costs `+1 N_sel` (`N_sel: 88 → 89`), requires pre-registration.** *(Caveat: only ~30 IAS 29 months exist, so power is limited to Rank-IC / paired-difference diagnostics.)*
- **Effort:** M
- **README failed-idea & PIT check:** Not failed in README (`ias29_regime_preregistration.md` and `ias29_constant_unit_ttm_preregistration.md` tested regime stability and C1 CPI-unit alignment only; NMPGL stripping is explicitly marked "check planned" in `README.md` line 764). Strictly PIT on first-published 2023Q4+ KAP filings.

#### 10. SPK II-15.1 Insider Net Buying (`Pay Alım Satım Bildirimi`, `DKB` PDF Parser on `kap_archive.parquet`)
- **Link:** [github.com/caganco/trailingedge](https://github.com/caganco/trailingedge) · [KAP Endpoint Notes](https://github.com/caganco/bist-flow-intel/blob/master/docs/KAP_ENDPOINT_NOTES.md) · [RePEc:taf:eurjfi:v:30:y:2024:i:6:p:549-574](https://ideas.repec.org/a/taf/eurjfi/v30y2024i6p549-574.html) (Avci, *European Journal of Finance* 2024)
- **Date:** 2024-04 (Avci, *EJF* 30(6):549–574) · 2026-05-31 (`trailingedge`)
- **Summary (2 lines):** Resolves the exact blocker listed in `README.md` line 522 (*"Insider trades: the direction is not in the KAP summaries; it needs the disclosure texts"*): `trailingedge` demonstrates how to unpack KAP's Java-serialized `byte[]` PDF wrapper for `disclosureClass == "DKB"` (*Pay Alım Satım Bildirimi*) to extract exact buy/sell direction, share count, and price. Avci (2024) documents `+6.58%` 1-year abnormal profits across ~65,000 BIST insider transactions (2008–2019), with outside investors outperforming when mimicking officer/director net purchases.
- **Concrete use for THIS project:** Filter our existing 2010–2026 `data/research/kap_archive.parquet` (637,454 disclosures) for `Pay Alım Satım Bildirimi` (`DKB`), parse transaction tables via a standalone `scripts/fetch_insider_trades.py` utility using publication timestamps (`published_at`) for strict PIT availability, and pre-register **one** trial testing trailing 90-day net insider buying as a standalone signal or `value_sn` filter (after **Plan P4-1** and **P4-3**).
- **Type & `N_sel` cost:** **New testable idea — costs `+1 N_sel` (`N_sel: 89 → 90`), requires pre-registration.**
- **Effort:** M
- **README failed-idea & PIT check:** Not failed in README (explicitly listed as *"Not tested, and why: Insider trades"* in `README.md` line 522; distinct from `kap_disclosure_signals_preregistration.md` which tested late filings, Friday releases, and corporate buybacks). Strictly PIT because every KAP `DKB` filing in `kap_archive.parquet` carries its exact publication date/time.

---

## 4. Summary Execution Table

| Rank | Action | Category | `N_sel` Cost | Effort | Target Plan / Files |
|---:|---|---|---:|---|---|
| **1** | Sanctioned KAP Feed Outside CI + Off-Peak Cron + `Healthchecks` | **(a) Infra / Data** | `0` | S | `P0-2`, `P0-3`, `P3-3` · `core/kap_api.py`, `.github/workflows/daily-screener.yml` |
| **2** | Native `borsapy` v0.10–0.11 EVDS3 (`C1` CPI, Policy Rate) & `Eurobond.history()` | **(a) Infra / Data** | `0` | S | `P0-2` · `core/live_data.py`, `core/pit_panel.py`, `core/sovereign_spread.py` |
| **3** | Search-Adjusted Sharpe (`DSR-LS`, $N_{\text{eff}}$), Variance Floor `V_min` & Purged PBO | **(a) Infra / Data** | `0` | S | `P1-2`, `P1-3` · `core/research_stats.py`, `data/research/trial_ledger.json` |
| **4** | Anytime-Valid Forward-Record Test (`Promote` e-Process) & Vol-Matched EW Bounds | **(a) Infra / Data** | `0` | S | `P0-3`, `P1-2`, `P1-3`, `P4-2` · `scripts/forward_record_report.py`, `scripts/research_total_return_benchmarks.py` |
| **5** | Boundary Data Contracts (`Pandera` + `Pydantic v2`) & Info-Only QIS Covariance | **(a) Infra / Data** | `0` | S | `P0-3`, `P1-1`, `P3-1`, `P3-2`, Step 5 · `core/run_health.py`, `core/forward_record.py`, `core/portfolio.py` |
| **6** | Persistent HTTP/Disk Cache (`Hishel`), `PyrateLimiter` & `kap-mcp` + DuckDB `ASOF JOIN` | **(a) Infra / Data** | `0` | M | `P0-2`, `P1-1`, `P2-1..P2-5` · `core/live_data.py`, `scripts/build_first_published.py`, `core/pit_panel.py` |
| **7** | PIT Free-Float Market-Cap Filter (`HAO_PD` + MKK VAP Cross-Check) | **(b) New Research** | `+1` (`86→87`) | S | `P4-1`, `P2-2` · `market_cap_monthly.parquet`, `docs/research/free_float_filter_preregistration.md` |
| **8** | Operating Cash-Flow Yield (`CFO/P`) Replacing `S/P` in `value_sn` | **(b) New Research** | `+1` (`87→88`) | M | Post-`P1` · `scripts/build_pit_panel.py`, `core/pit_panel.py::value_ratios` |
| **9** | IAS 29 Net Monetary Position Gain/Loss Stripping (`ep_ex_nmpgl`) | **(b) New Research** | `+1` (`88→89`) | M | Post-`P2-3` · `scripts/build_first_published.py`, `core/pit_panel.py::value_ratios` |
| **10** | SPK II-15.1 Insider Net Buying (`DKB` PDF Parser on `kap_archive.parquet`) | **(b) New Research** | `+1` (`89→90`) | M | Post-`P4` · `data/research/kap_archive.parquet`, `scripts/fetch_insider_trades.py` |
