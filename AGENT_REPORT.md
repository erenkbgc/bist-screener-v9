# Agent Report — Live Pipeline Fixes: Q3 Blind Spot & Holding Sector Parity (2026-11-22)

**Branch:** `fix/live-q3-and-holdings` (local worktree `/home/eren/bist_wt/livefix` only; never pushed, `master` and `config/live_rule.json` untouched).
**As-of date:** `2026-11-22`
**Test suite:** `.venv/bin/pytest tests/ -q` → **522 passed, 0 failed**

---

## 1. Summary of Changes

### Task 1: Fix `borsapy._get_periods()` Quarterly Fetch Blind Spot (`2026Q3` in November)
- **Root cause:** `borsapy._providers.isyatirim.IsYatirimProvider._get_periods()` hardcodes a 2-month post-quarter delay into the periods it requests from İş Yatırım:
  - `current_month <= 2` → starts at `(current_year - 1, 9)` (misses `Q4` in Jan–Feb)
  - `current_month <= 5` → starts at `(current_year - 1, 12)` (misses `Q1` in Apr–May)
  - `current_month <= 8` → starts at `(current_year, 3)` (misses `Q2` in Jul–Aug)
  - `current_month <= 11` → starts at `(current_year, 6)` (misses `Q3` in Oct–Nov)
  Because `core/pit_panel.py::fetch_statement()` called `prov._get_periods(datetime.now().year, True, count=last_n)`, `core/live_data.py::live_value_inputs()` never requested `(2026, 9)` (`2026Q3`) throughout October and November 2026—even though 538 / 583 (92.3%) non-financial companies had already filed `2026Q3` on KAP and İş Yatırım by `2026-11-21`.
- **Fix in our code (no site-packages patch):**
  1. Added `last_ended_quarter(as_of: date | None = None) -> tuple[int, int]` and `quarter_periods(count: int, as_of: date | None = None) -> list[tuple[int, int]]` to `core/pit_panel.py`.
  2. Updated `core/pit_panel.py::fetch_statement(ticker, statement_type, last_n, as_of=None)` to request 4-period batches starting from `last_ended_quarter(as_of)` (`(2026, 9)` on `2026-11-22`) and merge them via `merge_statement_batches()`.
  3. **KAP availability rule preserved:** Fetching `2026Q3` from İş Yatırım does not make it usable unconditionally. `core/pit_panel.py::latest_value_ratios()` and `core/live_data.py::live_value_inputs()` still require `available_at <= as_of`, where `available_at` is the first KAP financial-report publication date (+1 day if published at or after `18:00` Istanbul session close), or `period_end + 75` days (`2026-12-14` for `2026Q3`) when no KAP filing matches.
  4. Minor tie-break refinement in `core/live_data.py::live_financial_report_published_dt()`: compare `pub_dt < best[1]` (`datetime`) rather than `lag_days < best[0]` (`int`) so multiple disclosures on the same day deterministically pick the earliest timestamp.

### Task 2: Holding Sector Absence on `2026-11-01` — Investigation, Evidence, and Live Fix
- **Question 1 — Was the exclusion of `Holding` stocks intentional?**
  - **No.** It was an accidental drop in `run.py`.
  - **Evidence from git history, research docs, README, config, and research panel:**
    1. **PR #38 (`d11af24`, `fix/exclude-financials-live`, 2026-10-11):** Explicitly excluded only `core/pit_panel.py::FINANCIAL_SECTORS` (`Bankacılık`, `Sigorta`, `Emeklilik`, `Faktoring`, `Finansal Kiralama`, `Tasarruf Finansman`, `Aracı Kurum`, `Menkul Kıymet Yat. Ort.`, `Varlık Yönetimi`). The commit message states verbatim: *"Ayni sektor listesi canliya uygulanir; holdingler panelde oldugu gibi kalir"* (*"The same sector list is applied to live; holdings remain as in the panel"*).
    2. **Pre-registered study (`docs/research/financials_holdings_reits_preregistration.md`, PR #84/#85, 2026-10-17):** Evaluated 52 `Holding` tickers (`S2`) inside the C1 panel and concluded (Section "Summary of decisions", item 2): *"Holdings (`S2`) and REITs (`S3`) remain on `value_sn`"*.
    3. **`README.md` (line 220) & `core/ranking.py` (lines 49–53):** Define `RATIO_PROFILES["holding"] = dict(_VALUE_SN_PROFILE)` (`ep, bm, sp, ey`) and state that `valuation_z` is computed across industrial, holding, and REIT profiles together.
    4. **Research panel (`data/research/factors_monthly.parquet` and `data/research/fp/factors_monthly*.parquet`):** Contains **7,020 stock-month rows** for `Holding` (52 tickers, including `KCHOL`, `SAHOL`, `AGHOL`, `DOHOL` with 162 months each through `2026-11-30`) plus **938 stock-month rows** for `Girişim Sermayesi Yat. Ort.`.
- **Question 2 — Why did live drop all `Holding` stocks on `2026-11-01`?**
  - In `core/live_data.py`, `_classify_sector()` maps `"Holding"` and `"Girişim Sermayesi Yat. Ort."` to `ratio_profile = "holding"`, where `nav_discount = (equity - market_cap) / equity`.
  - Since commit `945e9fc` (`fix/p2-info-layers`, 2026-10-21), `config/weights.yaml` sets `valuation_triangle_weights` to `dcf: 0.0, peer_multiples: 0.50, quality_premium: 0.0` (only `peers_leg` is active).
  - In `core/valuation_triangle.py::compute_peers_leg()`, `ratio_profile == "holding"` computes a single leg:
    $$\text{holding\_nav} = \frac{\text{entry\_price}}{1 - \text{nav\_disc\_med}}$$
  - Next, `compute_valuation_triangle()` (line 438) applies an outlier guard: if `target_price > entry_price * 2.5`, it returns `target_price = None`.
  - Algebraically, $\frac{1}{1 - \text{nav\_disc\_med}} > 2.5 \iff \text{nav\_disc\_med} > 0.60$.
  -Whenever the Holding peer-group median `nav_discount` crosses **`0.60`**, `compute_valuation_triangle()` returns `target_price = None` for **every** stock in that peer group.
  - In `run.py` (line 343 before fix), `if lt["target_price"] is None: continue` dropped any candidate with `target_price is None` **before** appending to `long_term_candidates`, before `scoring.score_candidates()`, and before `rotation.monthly_rotation()`.
  - This violated the documented live rule (`README.md` line 142, `core/rotation.py` line 11) that target-price and hurdle gates are information-only and must never filter the `valuation_z` ranking or monthly rotation pool. It also dropped all 6 eligible `Girişim Sermayesi Yat. Ort.` tickers (`HDFGS`, `ISGSY`, `PRDGS`, `GOZDE`, `BULGS`, `ICUGS`, whose sector median `nav_discount` is ~`0.73 > 0.60`) on every run, as well as ultra-cheap industrial/REIT stocks (`VESBE`, `PNSUT`, `ESCOM`, `NETAS`, `EPLAS`, etc.) whose peer-multiple fair value exceeded `2.5x`/`3.5x` of price.
- **Fix:**
  1. In `run.py`, removed `if lt["target_price"] is None: continue`. When `lt["target_price"] is None`, `hurdle_lt` sets `expected_roi_pct = None`, `excess_over_hurdle_pct = None`, and `passes_gate = False`, and the candidate still proceeds to `long_term_candidates`, `scoring.score_candidates()`, and `rotation.monthly_rotation()`.
  2. In `core/beta_hurdle.py::calculate_beta_adjusted_hurdle()`, guarded `expected_roi_pct - hurdle_beta_adj` when `expected_roi_pct is None` so `beta_60_120d` and `hurdle_rate_beta_adjusted_pct` are still persisted with `excess_over_beta_hurdle_pct = None`.
  3. Downstream behavior: in `core/scoring.py`, candidates with `target_price is None` receive their exact cross-sectional `valuation_z` in `scores` and enter `rotation.monthly_rotation()`, while `hard_filters_passed()` marks them `candidate_state = "NO_ACTION"` (`filtered_by = "hurdle"`) so they are excluded from target-price prediction cards (`predictions`), which require a non-null `target_price`.

---

## 2. Empirical Evidence

### 2.1 Live Verification of `2026Q3` Fetch & Fallback (Task 1)
Executed live against İş Yatırım and KAP on `2026-11-22` (`core/pit_panel.fetch_statement` + `core/live_data.live_value_inputs(..., as_of_date="2026-11-22")`):

| Ticker | Sector | Filing Status | Fetched Columns (top 4) | `stmt_period` | `kap_published_at` | `kap_available_at` | `available_source` | `ttm_method` | `bm` | `ep` | `sp` | `ey` |
|---|---|---|---|---|---|---|---|---|---:|---:|---:|---:|
| `THYAO` | Hava Yolu | Filed `2026Q3` | `2026Q3, 2026Q2, 2026Q1, 2025Q4` | **`2026Q3`** | `2026-11-04T08:00` | `2026-11-04` | `kap` | `vendor_consistent_ytd` | `2.500` | `0.401` | `3.891` | `0.080` |
| `ARCLK` | Dayanıklı Tüketim | Filed `2026Q3` | `2026Q3, 2026Q2, 2026Q1, 2025Q4` | **`2026Q3`** | `2026-10-26T18:18` | `2026-10-27` | `kap` | `vendor_consistent_ytd` | `1.684` | `-0.213` | `17.478` | `0.044` |
| `KCHOL` | Holding | Filed `2026Q3` | `2026Q3, 2026Q2, 2026Q1, 2025Q4` | **`2026Q3`** | `2026-11-09T18:16` | `2026-11-10` | `kap` | `vendor_consistent_ytd` | `1.794` | `0.151` | `6.644` | `0.148` |
| `SAHOL` | Holding | Filed `2026Q3` | `2026Q3, 2026Q2, 2026Q1, 2025Q4` | **`2026Q3`** | `2026-11-04T19:21` | `2026-11-05` | `kap` | `vendor_consistent_ytd` | `2.683` | `0.160` | `1.815` | `0.205` |
| `AGHOL` | Holding | Filed `2026Q3` | `2026Q3, 2026Q2, 2026Q1, 2025Q4` | **`2026Q3`** | `2026-11-06T18:55` | `2026-11-07` | `kap` | `vendor_consistent_ytd` | `2.393` | `0.061` | `18.328` | `0.156` |
| `DOHOL` | Holding | Filed `2026Q3` | `2026Q3, 2026Q2, 2026Q1, 2025Q4` | **`2026Q3`** | `2026-11-05T18:18` | `2026-11-06` | `kap` | `vendor_consistent_ytd` | `2.460` | `0.218` | `2.011` | `0.264` |
| `KONTR` | İmalat | No `2026Q3` yet | `2026Q2, 2026Q1, 2025Q4, 2025Q3` | **`2026Q2`** | `2026-08-19T18:48` | `2026-08-20` | `kap` | `vendor_consistent_ytd` | `1.606` | `-0.953` | `5.979` | `-0.053` |

- Notice `ARCLK` (`18:18`), `KCHOL` (`18:16`), `SAHOL` (`19:21`), `AGHOL` (`18:55`), `DOHOL` (`18:18`), and `KONTR` (`18:48`) all published after `18:00`, so `kap_available_at` is strictly the next calendar day.
- `KONTR` has not filed `2026Q3` as of `2026-11-22`; `fetch_statement` requests `2026Q3..2024Q4`, İş Yatırım returns `2026Q2..2024Q4`, and `live_value_inputs` cleanly falls back to `2026Q2`.

### 2.2 Production SQLite Evidence for the `Holding` Cliff at `median(nav_discount) > 0.60` (Task 2)
From `data/bist_history.db` across October–November 2026 live runs:

| Run Date | Eligible `ratio_profile='holding'` | `Holding` Sector Median `nav_discount` | Implied `FV / P = 1 / (1 - med)` | `scored_holding` (`scores` table) | Total Eligible Universe | Total Scored (`long_term`) | Dropped Before Scoring (`target_price is None`) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `2026-10-28` | 42 | `0.5942` | `2.464x` ($\le 2.5\text{x}$) | **36** | 463 | 403 | 60 |
| `2026-10-29` | 42 | `0.5942` | `2.464x` ($\le 2.5\text{x}$) | **36** | 463 | 406 | 57 |
| **`2026-10-30`** | **42** | **`0.6156`** | **`2.601x` ($> 2.5\text{x}$)** | **0** | **460** | **366** | **94** |
| **`2026-10-31`** | **42** | **`0.6156`** | **`2.601x` ($> 2.5\text{x}$)** | **0** | **460** | **366** | **94** |
| **`2026-11-01`** | **42** | **`0.6156`** | **`2.601x` ($> 2.5\text{x}$)** | **0** | **460** | **366** | **94** |
| `2026-11-04` | 42 | `0.5964` | `2.478x` ($\le 2.5\text{x}$) | **36** | 460 | 403 | 57 |
| `2026-11-15` | 44 | `0.5749` | `2.352x` ($\le 2.5\text{x}$) | **38** | 466 | 411 | 55 |
| **`2026-11-17`** | **43** | **`0.6028`** | **`2.518x` ($> 2.5\text{x}$)** | **0** | **463** | **371** | **92** |
| `2026-11-18` | 44 | `0.5693` | `2.322x` ($\le 2.5\text{x}$) | **38** | 468 | 411 | 57 |
| `2026-11-21` | 45 | `0.5696` | `2.323x` ($\le 2.5\text{x}$) | **39** | 464 | 411 | 53 |

- On every single day where `Holding` median `nav_discount` exceeded `0.60` (`2026-10-30..2026-11-01` at `0.6156`, and `2026-11-17` at `0.6028`), all 36–37 `Holding` stocks collapsed to `scored_holding = 0`.
- Even on days where `Holding` median `nav_discount` was `< 0.60`, all 6 `Girişim Sermayesi Yat. Ort.` tickers (`BULGS, GOZDE, HDFGS, ICUGS, ISGSY, PRDGS`) plus ~47–54 non-holding stocks (`VESBE, PNSUT, ESCOM, NETAS, EPLAS`, etc.) were dropped before scoring because `target_price` was `None`.

---

## 3. Risks for the `2026-12-01` Rebalance

1. **CI KAP connectivity outage blocks `2026Q3` until `2026-12-14` unless KAP dates are reachable or cached (CRITICAL):**
   - For `2026Q3` (`period_end = 2026-09-30`), the fallback 75-day publication lag is **`2026-12-14`** (`2026-09-30 + 75 days`).
   - On **`2026-12-01`**, `2026Q3` is usable (`available_at <= 2026-12-01`) **if and only if** `live_financial_report_published_dt()` matches the stock's KAP `Finansal Rapor` disclosure (`available_source == "kap"`).
   - In GitHub Actions CI, KAP frequently blocks or times out requests from runner IPs, tripping `_KapBreaker` after 10 consecutive failures (on `2026-11-01`, `decisions.jsonl` recorded `health.issues = ["kap_unavailable"]` and `0 / 233` stocks had `kap_available_at`).
   - **Impact on `2026-12-01`:** With Task 1 fixed, `fetch_statement()` will fetch `2026Q3` for all 538 filers, and local runs (where KAP is reachable) will use `2026Q3`. However, if the `2026-12-01` run executes on a GitHub Actions runner where KAP is unreachable and there is no committed/cached KAP report-date table fallback, `latest_value_ratios()` will assign the assumed lag `2026-12-14 > 2026-12-01` to `2026Q3` and fall back to **`2026Q2`** across the board. Providing a committed KAP report-date fallback or running the `2026-12-01` rebalance from an environment with working KAP connectivity is strongly recommended.
2. **Portfolio turnover at the `2026-12-01` rebalance from restoring `Holding` / `GSYO` / low-P/B stocks and shifting `2026Q2 -> 2026Q3`:**
   - The `2026-11-01` recorded basket (`47` holdings out of `233` ranked liquid stocks) excluded all `Holding`, `GSYO`, and `target_price=None` stocks and used `2026Q2` statements.
   - Restoring the ~94 previously dropped eligible candidates expands the live non-financial pool before the 30% liquidity cut from ~334 to ~425 stocks (yielding ~298 liquid ranked stocks vs 233 on `2026-11-01`, and ~60 top-20% holdings vs 47).
   - High-`value_sn` Holding and GSYO names (`GLRYH, HDFGS, ISGSY, AGHOL, BERA, METRO, GSDHO, KCHOL, SAHOL, DOHOL, NTHOL, PRDGS`) and deep-value industrials (`VESBE, ESCOM, NETAS, EPLAS, PNSUT`) now enter the live ranking pool at parity with the tested panel, which will produce higher-than-usual one-off turnover (`SAT` / `AL`) on `2026-12-01`.
   - Per `config/live_rule.json`, the `2026-11-01` forward record entry is never retroactively altered; the parity fix takes effect forward from the next decision (`2026-12-01`).

---

## 4. Commits on `fix/live-q3-and-holdings`

1. `bac70af` — `fix(live): fetch latest ended quarter in November and score candidates when target_price is None`
   - `core/pit_panel.py`: `last_ended_quarter()`, `quarter_periods()`, `fetch_statement(..., as_of=None)`
   - `core/live_data.py`: deterministic timestamp tie-break in `live_financial_report_published_dt()`
   - `run.py`: keep candidates in `long_term_candidates` when informational `target_price` is `None`
   - `core/beta_hurdle.py`: handle `expected_roi_pct=None` in `calculate_beta_adjusted_hurdle()`
   - `tests/test_pit_panel.py`: unit tests for `last_ended_quarter`, `quarter_periods`, and mocked `fetch_statement` in November (`HASQ3` vs `NOQ3`)
   - `tests/test_valuation_parity.py`: unit test for `live_value_inputs` with `2026Q3` in November verifying KAP 18:00 cutoff, 75-day fallback when KAP is missing, and `2026Q2` fallback when `2026Q3` is unfiled
   - `tests/test_holding_live_parity.py`: end-to-end `run.py` parity test verifying that when Holding median `nav_discount > 0.60` (and industrial `pb = 0.1` causes `target_price = None`), all Holding and deep-value industrial stocks are scored in `scores` with `valuation_z` identical to `factor_backtest` (`value_sn_z`) and included in `rotation_holdings` while banks remain excluded
2. `docs: add AGENT_REPORT.md and PR_BODY.md for live Q3 and Holding parity fixes`
