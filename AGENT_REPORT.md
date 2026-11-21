# Agent Report — Data Quality Auditor (P2-1, P2-2, P2-5)

- **Date:** 2026-11-22
- **Branch:** `agent/completeness` (worktree `/home/eren/bist_wt/completeness`)
- **Scope:** Plan items **P2-1**, **P2-2**, and **P2-5** from `docs/plan_2026-10-26.md`.
- **Guardrails verified:** `config/live_rule.json`, `core/` (live scoring), `master`, and `data/research/trial_ledger.json` (`N_sel = 86`) are untouched. No new research test was run. Never pushed. All KAP fetches respected the 3 s pause + HTTP 429 backoff (~18 new KAP pages fetched total).
- **Test suite:** `520 passed` (`pytest -q`), including new unit tests for sub-section footnote parsing, Q4-only / shifted-FY re-expression undo, share-class & multi-item classification, and HisseTekil `PD` preference for financials.
- **Full per-ticker tables:** `docs/research/completeness_audit_2026-11-22.md`.

---

## 1. What Was Done & Key Numbers

### P2-1 — 33 `unknown` companies in `reexpression_class.parquet` (+ 6 previously misclassified caught on full re-audit)

- **Outcome:** **33 / 33 `unknown` companies resolved (`unknown`: 33 → 0).** Re-auditing all 455 previously classified tickers also caught **6 misclassified** companies (`ARENA`, `BTCIM`, `KONTR`, `MEGAP`, `OZGYO`, `TRILC`).
- **Root causes fixed:**
  1. **Sub-section footnote parsing bug (`scripts/audit_restatements.py`, `scripts/audit_vendor_vs_kap.py`) — 19 of 33:** KAP footnotes like `23.1`, `22.01`, `3,11`, `5,28` before `Hasılat` were parsed as revenue (`231`, `2201`, `3.11`, `5.28`). Tightened `_NUM` so `.` only matches 3-digit Turkish thousands groups, and skipped leading footnote numbers `< 100` followed by monetary amounts `>= 1000`.
  2. **Consolidated vs. solo GYO mismatch — 6 of 33 (`AGYO`, `ALGYO`, `AVGYO`, `HLGYO`, `RYGYO`, `TRGYO`) + `OZGYO`:** İş Yatırım stores solo statements (`consolidated=False`) for these GYOs. Matching candidate pages by `TOPLAM VARLIKLAR` proximity (`v_ta / (k_ta * scale) ≈ 1.0`) picks the exact vendor basis.
  3. **Share-class pro-rata allocation — 3 of 33 (`KRDMA` 21.08%, `KRDMB` 10.48%, `KRDMD` 68.44%):** Normalizing mid-year income ratios by `v_ta / k_ta` recovers exact CPI factors (`1.3505` on 2024Q2, `1.3211` on 2025Q2) across all 3 income items.
  4. **Special fiscal year-ends — 5 of 33 + `ARENA`:**
     - `BORSK` (Mar 31, `fy_shift_q=1`), `BALSU` (Jun 30, `fy_shift_q=2`), `MERKO` (Jun 30, `fy_shift_q=2`) → `reexpressed`.
     - `MARTI`, `MRGYO`, `ARENA` (Mar 31, `fy_shift_q=1`) → **`reexpressed_q4_only`**: verified across 2023Q4–2026Q1 that Q1–Q3 equal `1.00000` while Q4 (`2024Q4` × `1.30865`, `2025Q4` × `1.07014`) is re-expressed by shifted CPI. Updated `undo_reexpression()` in `scripts/rebuild_panels_first_published.py` to handle `fy_shift_q` and `reexpressed_q4_only`.
  5. **Restated Q2 (`TGSAS`) — 1 of 33:** Multi-item consensus (`>= 2` agreeing items) rejects coincidental single-item `1.0000` on `2024Q2` (`r_rev=0.6326, r_op=0.6326, r_ni=1.0000`) and resolves `TGSAS` as `reexpressed` on `2024Q1` (`1.3810`, corroborated by `2024Q4` `1.3089` and `2025Q4` `1.1776`).
  6. **Missing `2026Q2` in `raw/*.pkl` — 4 previously misclassified (`BTCIM`, `KONTR`, `MEGAP`, `TRILC`):** Previously compared `2025Q2` even though `2026Q2` had not been published when `raw/*.pkl` was fetched, yielding spurious `1.0000` (`not_reexpressed`). Requiring `nxt_v in inc_cols` resolves all four as `reexpressed` on `2024Q2`/`2024Q1`/`2025Q1`.
- **Final `reexpression_class.parquet` (488 tickers):**
  - `reexpressed`: **453** (was 421)
  - `not_reexpressed`: **32** (was 34)
  - `reexpressed_q4_only`: **3** (was 0: `ARENA`, `MARTI`, `MRGYO`)
  - `unknown`: **0** (was 33)
- **Effect on `data/research/fp/`:** `values_divided` increased `36,185 → 38,986` (+2,801).

### P2-2 — 9 stocks without HisseTekil history (`CITAS`, `DAGHL`, `INTEK`, `LRSHO`, `LYDHO`, `MARKA`, `METUR`, `PEHOL`, `SELGD`)

- **Outcome:** **9 / 9 resolved.**
  - **5 stale renamed old codes** (0 rows in `factors_monthly.parquet`; new codes already exist in `raw/` and `isy_daily/` with full 2012–2026 history):
    - `DAGHL` → `TRHOL` (2025-09-01, 3,733 days)
    - `MARKA` → `USHOL` (2026-09-01, 3,720 days)
    - `METUR` → `BLUME` (2025-10-01, 3,735 days)
    - `PEHOL` → `TEHOL` (2025-08-01, 3,734 days)
    - `SELGD` → `DUNYH` (2025-10-01, 3,724 days)
  - **4 active tickers recovered via recursive date-range bisection** (`scripts/fetch_isyatirim_market_cap.py`): İş Yatırım's `HisseTekil` returns `{"value": []}` for an entire 2012–2026 query whenever a single corrupt day falls inside the window. Bisecting empty ranges recovered:
    - `CITAS` (Aug 2026 IPO): **65 days** (2026-08-21 → 2026-11-20; poisoned on IPO opening days 2026-08-18..20; 0 panel rows due to <13m history).
    - `INTEK` (formerly `UZERB`): **3,591 days** (2012-07-23 → 2026-11-20; 1 poison day skipped: `2018-07-20`); **154 / 154 panel months recovered** (5.8% had mcap off >10%).
    - `LRSHO` (formerly `ITTFH`): **3,733 days** (2012-01-02 → 2026-11-20; 2 poison days skipped: `2018-07-18`, `2023-03-15`); **162 / 162 panel months recovered** (**79.6%** had old mcap off >10%, median old/new = **0.362×**, min 0.195×).
    - `LYDHO` (formerly `MIPAZ`): **3,733 days** (2012-01-02 → 2026-11-20; 2 poison days skipped: `2018-07-19`, `2023-03-15`); **158 / 158 panel months recovered** (5.7% had mcap off >10%).
- **Effect on `data/research/fp/`:**
  - `isyatirim_pd` coverage rose from `57,636 / 58,223` (98.99%) → **`58,110 / 58,223` (99.81%)** (`lag75`) and `57,721 → 58,195 / 58,308` (99.81%, `kapdates`).
  - `price_x_shares` fallback dropped **587 → 113** stock-months, leaving only genuinely unavailable `ERBOS` (105 rows, pre-2022-01-12) and `UMPAS` (8 rows during BIST trading suspension, 2022-12..2023-07).
  - Re-running `scripts/compare_panels.py` (`data/reports/compare_panels_2026-11-22.json`, same fixed comparison as `first_published_panel.md`, uncosted top-20% active vs EW universe):
    - Discovery 2013–2020: `+5.28% (t 2.14)` → **`+4.43% (t 1.67)`**, IC `0.0558 (t 5.47)` (correcting `LRSHO` removes another pre-rights look-ahead outlier).
    - Holdout 2021+: `+10.75% (t 3.21)` → **`+10.00% (t 2.91)`**, IC `0.0733 (t 4.78)`.
    - IAS 29 window 2024-05+: `+2.93% (t 0.76)` → **`+2.08% (t 0.55)`**, IC `0.0340 (t 2.28)`, paired diff vs vendor baseline `−2.44%/yr (t −2.39)`.

### P2-5 — Rebuild `financials_factors_monthly.parquet` with HisseTekil `PD`

- Extended `scripts/fetch_isyatirim_market_cap.py` to scan `raw_fin/*.pkl` alongside `raw/` and `raw_delisted/` (**52 / 53** financial tickers fetched; only `QNBFL` is empty because it was renamed to `QNBFK`, which is in the 52). Total `market_cap_monthly.parquet`: **79,219 rows across 678 tickers** (0 failures; only 6 renamed old tickers empty across all 684).
- Updated `build_financials_panel()` in `scripts/research_financials_holdings_reits.py` to pass `market_caps` from `market_cap_monthly.parquet` to `pit_panel.build_monthly_factors()` and rebuilt `data/research/financials_factors_monthly.parquet`:
  - **Coverage:** **`6,582 / 6,582` rows (100.0% `isyatirim_pd`, 0 fallbacks)** across 49 financial tickers (`2013-02-28` → `2026-10-31`).
  - **Old `price × shares` distortion quantified (109 rights issues across 26 financial stocks):**
    - `|old/new − 1| > 10%`: **1,692 / 6,582 (25.7%)**
    - `|old/new − 1| > 25%`: **1,414 / 6,582 (21.5%)**
    - Off by `> 1.5×`: **1,149 / 6,582 (17.5%)**; `> 2×` too low (`ratio < 0.5`): **383 (5.8%)**
    - Spearman rank correlation old vs. new: `bm` = **0.9214**, `ep` = **0.9179**.
    - Worst distorted: `KLNMA` (89.0% >1.5×, median 0.113×, min 0.022×), `SEKFK` (98.2%, med 0.551×), `QNBFK` (85.9%, med 0.406×), `AKGRT` (72.4%, med 0.510×), `INFO` (60.1%, med 0.394×), `VAKFN` (55.2%, min 0.001×), `SKBNK` (54.0%, med 0.667×).

---

## 2. Commits on `agent/completeness`

- `6e26799` — `fix(research): resolve 33 unknown + 6 misclassified reexpression companies (P2-1)`
- `a6e5a65` — `fix(research): bisect HisseTekil gaps (P2-2) and rebuild financials panel with PD (P2-5)`
- *(Next commit)* — `docs: add AGENT_REPORT.md for P2-1/P2-2/P2-5 data completeness audit`

Note: `data/research/` is gitignored, so the rebuilt parquet files (`reexpression_class.parquet`, `isy_daily/*.parquet`, `market_cap_monthly.parquet`, `financials_factors_monthly.parquet`, `fp/*.parquet`) live in this worktree's `data/research/`. Running the committed scripts (`classify_reexpression.py`, `fetch_isyatirim_market_cap.py --retry-empty`, `rebuild_panels_first_published.py`, and `build_financials_panel(..., rebuild_panel=True)`) reproduces them deterministically in any other checkout.

---

## 3. Open Problems / Remaining Limitations

1. **95 illiquid/recent non-financial tickers outside `targets()`:** `classify_reexpression.py` only classifies the 488 tickers that appeared in the liquid top-70% non-financial universe from 2023-06 onward (matching `build_first_published.py`). The remaining 95 tickers in `raw/*.pkl` (illiquid / post-2026-06 IPOs / stale renamed duplicates like `DAGHL`, `MARKA`, `METUR`, `PEHOL`, `SELGD`) are never selected by the liquid-universe rule, so they are intentionally absent from `reexpression_class.parquet`, but if a future study drops the liquidity filter they would need classification.
2. **Stale renamed tickers still present in `data/research/raw/` and `raw_fin/`:** `DAGHL`, `MARKA`, `METUR`, `PEHOL`, `SELGD`, and `QNBFL` still have `.pkl` files alongside their active successors (`TRHOL`, `USHOL`, `BLUME`, `TEHOL`, `DUNYH`, `QNBFK`). They currently contribute 0 rows to `factors_monthly.parquet` and `financials_factors_monthly.parquet`, so they cause no double-counting today, but `config/fintables_ticker_sektor.json` / `build_pit_panel.py` should eventually prune superseded codes.
3. **113 remaining `price_x_shares` rows in `fp/factors_monthly.parquet`:** `ERBOS` (105 rows, 2013-04..2021-12) has no pre-2022 HisseTekil history on İş Yatırım, and `UMPAS` (8 rows, 2022-12..2023-07) was suspended from trading on BIST. Neither can be recovered from HisseTekil.
4. **Special fiscal year-end non-quarterly shifts:** Football clubs (`BJKAS`, `FENER`, `GSRAY`, `TSPOR`, May 31 FY-end), `MAVI` (Jan 31 FY-end), and `KAYSE` (Apr 30 FY-end) have month-level (not exact 3-month-quarter) fiscal shifts. Their `reexpression_class` matched cleanly within `±1%`, so they are classified as `reexpressed` with `fy_shift_q=0`; their CPI ratio approximation is within ~1% of the true non-quarter-end CPI month.
5. **Financial-sector IAS 29 re-expression & re-evaluation:** P2-5 rebuilt `financials_factors_monthly.parquet` with HisseTekil `PD` (100% coverage), fixing the rights-adjustment market-cap distortion (25.7% of rows off >10%). Note that Turkish banks and insurers were exempt from IAS 29 (BDDK/SEDDK deferral), while some non-bank financials (brokers, factoring, leasing) applied IAS 29; re-running `research_financials_holdings_reits.py` on the rebuilt panel (reporting only, or under a new pre-registration if changing rules) is left for a follow-up after P1 baseline promotion.
6. **P2-3 and P2-4 remain open** (not in this role's scope): validating the re-expression undo model against more KAP first-published pages (P2-3) and deciding on pre-IAS-29 (2014–2022) income restatements (P2-4).
