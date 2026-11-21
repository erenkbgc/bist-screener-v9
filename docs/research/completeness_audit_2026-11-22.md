# Data Completeness Audit (P2-1, P2-2, P2-5)

Date: 2026-11-22. Data-quality audit and panel completeness rebuilds (no new research signal or trial; `N_sel` unchanged, `config/live_rule.json` and live scoring untouched).

---

## P2-1: 33 `unknown` companies in `reexpression_class.parquet` (+ 6 misclassified found on full re-audit)

### Root causes found

1. **Sub-section footnote parsing bug (`scripts/audit_restatements.py`, `scripts/audit_vendor_vs_kap.py`) — 19 of 33 unknowns:**
   KAP XBRL tables place sub-section footnote references (e.g. `23.1`, `22.01`, `24.1`, `25.1`, `26.1`, `27.1`, `3,11`, `3,17`, `5,28`, `5,31`) in the Dipnot column directly before `Hasılat`. Previously:
   - `parse_number()` accepted `.` anywhere, turning `23.1` into `231.0` and `22.01` into `2201.0`;
   - `values()` only skipped integer footnotes `< 100`, so `3,11` (`3.11`) and `231.0` were treated as revenue, producing ratios of `3.6e4`–`6.9e9`.
   - Fix: restrict `.` in `_NUM` to valid 3-digit Turkish thousands groups (`\d{1,3}(?:\.\d{3})+|\d+`), and skip leading small numbers `< 100` when followed by monetary amounts (`abs(nums[1]) >= 1000`).

2. **Consolidated vs. solo mismatch on GYOs — 6 of 33 unknowns (+ `OZGYO`):**
   `AGYO`, `ALGYO`, `AVGYO`, `HLGYO`, `RYGYO`, `TRGYO` (and `OZGYO`) publish both consolidated and solo statements on KAP, while İş Yatırım stores the **solo** (`consolidated=False`) statement. Ranking candidate pages by mid-year `TOPLAM VARLIKLAR` proximity (`v_ta / (k_ta * scale) ≈ 1.0000`) immediately selects the matching basis.

3. **Pro-rata share-class allocation (`KRDMA`, `KRDMB`, `KRDMD`) — 3 of 33 unknowns:**
   İş Yatırım allocates Kardemir's consolidated statement pro-rata across A (21.08%), B (10.48%), and D (68.44%) share classes. Because mid-year balance-sheet total assets are not re-expressed, normalizing income ratios by `v_ta / k_ta` recovers exact CPI factors (`1.3505` on 2024Q2, `1.3211` on 2025Q2) across all 3 income items.

4. **Special fiscal year-ends — 5 of 33 unknowns (+ `ARENA`):**
   - `BORSK` (March 31 FY-end, `fy_shift_q=1`), `BALSU` (June 30 FY-end, `fy_shift_q=2`), `MERKO` (June 30 FY-end, `fy_shift_q=2`, also had footnote `25.1`): fully `reexpressed` once KAP calendar periods are mapped to vendor fiscal columns and shifted CPI months.
   - `MARTI`, `MRGYO` (March 31 FY-end, `fy_shift_q=1`), and `ARENA` (switched to March 31 FY-end in 2025): verified across all 2023Q4–2026Q1 filings that interim quarters (Q1–Q3) are **not re-expressed (`1.00000`)**, while Q4 (`2024Q4` × `1.30865` = `CPI(2026-03)/CPI(2025-03)`, `2025Q4` × `1.07014` = `CPI(2026-06)/CPI(2026-03)`) **is** re-expressed. Classified as `reexpressed_q4_only`; `undo_reexpression()` now supports both `reexpressed_q4_only` and `fy_shift_q`.

5. **Single-period restatement (`TGSAS`) — 1 of 33 unknowns:**
   `TGSAS` restated `2024Q2` and `2025Q2` income items in later comparatives (`r_rev=0.6326`, `r_ni=1.0000` on 2024Q2). Requiring multi-item consensus (`>= 2` agreeing items when `>= 2` are present) rejects the coincidental single-item `1.0000` on 2024Q2 and resolves `TGSAS` on `2024Q1` (`r_rev=1.3810, r_op=1.3810`, factor `1.3810`), corroborated by `2024Q4` (`1.3089` across all 4 items) and `2025Q4` (`1.1776` across all 4 items).

6. **Bonus catch on the 455 previously classified companies — 6 corrections:**
   - `BTCIM`, `KONTR`, `MEGAP`, `TRILC` lacked `2026Q2` in `raw/*.pkl` when fetched on 2026-09-27, so `2025Q2` had not yet been overwritten by `2026Q2` comparatives (`ratio = 1.0000`) and was falsely labelled `not_reexpressed`. Checking `nxt_v in inc_cols` and falling back to `2024Q2`/`2024Q1`/`2025Q1` proved all four are `reexpressed` (multi-item exact CPI match).
   - `OZGYO` (`not_reexpressed` → `reexpressed`): solo statement matches `1.3211` across all 3 items.
   - `ARENA` (`not_reexpressed` → `reexpressed_q4_only`, `fy_shift_q=1`): switched to March 31 FY-end in 2025; `2025Q4` re-expressed × `1.07014`.

### Overall counts (`data/research/reexpression_class.parquet`, 488 companies)

| Class | Before (2026-10-25) | After (2026-11-22) | Change |
|---|---:|---:|---:|
| `reexpressed` | 421 | 453 | +32 (+27 from unknown, +5 misclassified) |
| `not_reexpressed` | 34 | 32 | −2 (+4 from unknown, −5 to `reexpressed`, −1 to `reexpressed_q4_only`) |
| `reexpressed_q4_only` | 0 | 3 | +3 (`MARTI`, `MRGYO`, `ARENA`) |
| `unknown` | 33 | **0** | −33 (100% resolved) |

### Per-ticker outcome for all 33 previously `unknown` companies

| Ticker | KAP period | Vendor period | Ratio | CPI factor | New class | Cons. | FY shift (Q) | Root cause / method |
|---|---|---|---:|---:|---|---|---:|---|
| `AGYO` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | False | 0 | Solo/cons GYO mismatch |
| `AHSGY` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | False | 0 | Footnote `23.1` on Hasılat |
| `ALCTL` | 2025Q2 | 2025Q2 | 1.0000 | 1.3211 | `not_reexpressed` | False | 0 | Footnote `3,11` on Hasılat |
| `ALGYO` | 2024Q2 | 2024Q2 | 1.3505 | 1.3504 | `reexpressed` | False | 0 | Solo/cons GYO mismatch |
| `ANELE` | 2024Q2 | 2024Q2 | 1.3505 | 1.3504 | `reexpressed` | True | 0 | Footnote `3,17` on Hasılat |
| `AVGYO` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | False | 0 | Solo/cons GYO mismatch |
| `BALSU` | 2025Q2 | 2024Q4 | 1.3211 | 1.3211 | `reexpressed` | True | 2 | Jun 30 special FY (`q4_match`) |
| `BMSTL` | 2025Q2 | 2025Q2 | 1.0000 | 1.3211 | `not_reexpressed` | True | 0 | Footnote `23.1` on Hasılat |
| `BORSK` | 2025Q2 | 2025Q1 | 1.3211 | 1.3211 | `reexpressed` | False | 1 | Mar 31 special FY |
| `CGCAM` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | False | 0 | Footnote `21.1` on Hasılat |
| `CVKMD` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | True | 0 | Footnote `23.1`/`24.1` on Hasılat |
| `DUNYH` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | False | 0 | Footnote `20.1` on Hasılat |
| `HLGYO` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | False | 0 | Solo/cons GYO mismatch |
| `HUNER` | 2025Q2 | 2025Q2 | 1.0000 | 1.3211 | `not_reexpressed` | True | 0 | Footnote `22.1` on Hasılat |
| `KOPOL` | 2025Q2 | 2025Q2 | 1.0000 | 1.3211 | `not_reexpressed` | False | 0 | Footnote `21.1` on Hasılat |
| `KRDMA` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | True | 0 | Share-class allocation (21.08%) |
| `KRDMB` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | True | 0 | Share-class allocation (10.48%) |
| `KRDMD` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | True | 0 | Share-class allocation (68.44%) |
| `KUTPO` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | True | 0 | Footnote `23.1` on Hasılat |
| `MACKO` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | True | 0 | Footnote `23.1` on Hasılat |
| `MARTI` | 2025Q1 | 2024Q4 | 1.3087 | 1.3088 | `reexpressed_q4_only` | True | 1 | Mar 31 FY; Q1–Q3 = 1.0, Q4 re-expressed |
| `MERIT` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | True | 0 | Footnote `17.1` on Hasılat |
| `MERKO` | 2025Q2 | 2024Q4 | 1.3211 | 1.3211 | `reexpressed` | False | 2 | Jun 30 FY + footnote `25.1` |
| `MRGYO` | 2025Q1 | 2024Q4 | 1.3087 | 1.3088 | `reexpressed_q4_only` | False | 1 | Mar 31 FY; Q1–Q3 = 1.0, Q4 re-expressed |
| `NTHOL` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | True | 0 | Footnote `27.1` on Hasılat |
| `OZYSR` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | True | 0 | Footnote `26.1`/`27.1` on Hasılat |
| `POLTK` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | False | 0 | Footnote `22.01`/`20.1` on Hasılat |
| `RYGYO` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | False | 0 | Solo/cons GYO mismatch |
| `SANKO` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | False | 0 | Footnote `5,31` on Hasılat |
| `SARKY` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | True | 0 | Footnote `5,28` on Hasılat |
| `SDTTR` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | True | 0 | Footnote `24.1` on Hasılat |
| `TGSAS` | 2024Q1 | 2024Q1 | 1.3810 | 1.3810 | `reexpressed` | True | 0 | 2024Q2/2025Q2 restated; confirmed on Q1 & Q4 |
| `TRGYO` | 2025Q2 | 2025Q2 | 1.3211 | 1.3211 | `reexpressed` | False | 0 | Solo/cons GYO mismatch |

---

## P2-2: 9 stocks without HisseTekil history

### Root causes found

- **5 tickers are old (renamed) codes** whose new tickers are **already** present in `raw/` and `isy_daily/` with full 2012–2026 history, and the old codes have 0 rows in `factors_monthly.parquet`.
- **4 tickers are active on İş Yatırım under their exact current codes**, but a single corrupt trading day (or IPO opening days) in İş Yatırım's `HisseTekil` backend causes any wide date-range query (`01-01-2012..today`) spanning that day to return `{"value": []}` silently. Adding recursive date-range bisection (year → month → binary split to day) in `scripts/fetch_isyatirim_market_cap.py` recovered 100% of all remaining trading days and 100% of monthly rows (`474 / 474` panel stock-months for `INTEK`, `LRSHO`, `LYDHO`).

### Per-ticker outcome (all 9 stocks)

| Ticker | Status | Alternate / new code | HisseTekil outcome | Panel rows recovered | Notes |
|---|---|---|---|---:|---|
| `CITAS` | Active IPO (Aug 2026, Çitlekçi Gıda) | — (no prior code) | **Recovered: 65 days** (2026-08-21 → 2026-11-20) | 0 (<13m history) | Poisoned on IPO opening days (2026-08-18..20); 0 missing days from 2026-08-21 |
| `DAGHL` | Renamed (2025-09-01) | `TRHOL` (already in `isy_daily`: 3,733 days) | Stale old code (empty) | 0 (0 rows in panel) | Tera Finansal Yatırımlar Holding |
| `INTEK` | Active (formerly `UZERB`) | Same code `INTEK` works with bisection | **Recovered: 3,591 days** (2012-07-23 → 2026-11-20) | **154 / 154** | Single poison day skipped: `2018-07-20`; 5.8% of months had `mcap` off >10% |
| `LRSHO` | Active (formerly `ITTFH`) | Same code `LRSHO` works with bisection | **Recovered: 3,733 days** (2012-01-02 → 2026-11-20) | **162 / 162** | Two poison days skipped: `2018-07-18`, `2023-03-15`; **79.6%** of months off >10% (median old/new = **0.362×**, min 0.195×) |
| `LYDHO` | Active (formerly `MIPAZ`) | Same code `LYDHO` works with bisection | **Recovered: 3,733 days** (2012-01-02 → 2026-11-20) | **158 / 158** | Two poison days skipped: `2018-07-19`, `2023-03-15`; 5.7% of months had `mcap` off >10% |
| `MARKA` | Renamed (2026-09-01) | `USHOL` (already in `isy_daily`: 3,720 days) | Stale old code (empty) | 0 (0 rows in panel) | US Yatırım Holding |
| `METUR` | Renamed (2025-10-01) | `BLUME` (already in `isy_daily`: 3,735 days) | Stale old code (empty) | 0 (0 rows in panel) | Blume Metal Kimya |
| `PEHOL` | Renamed (2025-08-01) | `TEHOL` (already in `isy_daily`: 3,734 days) | Stale old code (empty) | 0 (0 rows in panel) | Tera Yatırım Teknoloji Holding |
| `SELGD` | Renamed (2025-10-01) | `DUNYH` (already in `isy_daily`: 3,724 days) | Stale old code (empty) | 0 (0 rows in panel) | Dünya Holding |

### Impact on `data/research/fp/` (P2-1 + P2-2 combined)

- `values_divided`: `36,185` → **`38,986`** (+2,801).
- `isyatirim_pd` coverage:
  - `lag75`: `57,636 / 58,223` (98.99%) → **`58,110 / 58,223` (99.81%)**.
  - `kapdates`: `57,721 / 58,308` (98.99%) → **`58,195 / 58,308` (99.81%)**.
- Remaining `price_x_shares` fallback dropped from **587 → 113** stock-months, consisting solely of:
  - `ERBOS` (105 rows, 2013-04 → 2021-12): İş Yatırım HisseTekil genuinely has no records prior to `2022-01-12`.
  - `UMPAS` (8 rows, 2022-12 → 2023-07): trading suspension on BIST (no daily bars).
- Uncosted `compare_panels.py` (`data/reports/compare_panels_2026-11-22.json`, same fixed comparison as `first_published_panel.md`):
  - Discovery 2013–2020: active `+5.28% (t 2.14)` → **`+4.43% (t 1.67)`**, IC `0.0558 (t 5.47)` (correcting `LRSHO`'s 3–5× under-priced market cap removes another pre-rights look-ahead outlier).
  - Holdout 2021+: active `+10.75% (t 3.21)` → **`+10.00% (t 2.91)`**, IC `0.0733 (t 4.78)`.
  - IAS 29 window 2024-05+: active `+2.93% (t 0.76)` → **`+2.08% (t 0.55)`**, IC `0.0340 (t 2.28)`, paired diff vs vendor baseline `−2.44%/yr (t −2.39)`.

---

## P2-5: Rebuild `financials_factors_monthly.parquet` with HisseTekil `PD`

- Extended `scripts/fetch_isyatirim_market_cap.py` to include `data/research/raw_fin/*.pkl` (53 financial tickers). **52 of 53** returned full HisseTekil history; the sole empty ticker is `QNBFL` (renamed to `QNBFK`, which is in the 52).
- Updated `build_financials_panel()` in `scripts/research_financials_holdings_reits.py` to load `market_cap_monthly.parquet` and pass `market_caps=...` into `pit_panel.build_monthly_factors()`, with an offline `rebuild_panel=True` flag.
- Rebuilt `data/research/financials_factors_monthly.parquet`:
  - **Coverage:** `6,582 / 6,582` rows (**100.0% `isyatirim_pd`**, 0 `price_x_shares` fallbacks), 49 financial tickers, `2013-02-28` → `2026-10-31`.
  - **Severity of prior `price × shares` distortion (109 rights issues across 26 financial tickers):**
    - `|old/new − 1| > 10%`: **1,692 / 6,582 (25.7%)**
    - `|old/new − 1| > 25%`: **1,414 / 6,582 (21.5%)**
    - Off by `> 1.5×` (`ratio < 0.67` or `> 1.5`): **1,149 / 6,582 (17.5%)**
    - `old` more than `2×` too low (`ratio < 0.5`): **383 / 6,582 (5.8%)**
    - Cross-sectional Spearman rank correlation (old vs. new): `bm` = **0.9214**, `ep` = **0.9179**.
  - **Most affected tickers (old `price × shares` / new HisseTekil `PD`):**
    - `SEKFK`: 98.2% of 163 months off >1.5× (median 0.551×)
    - `KLNMA`: 89.0% off >1.5× (median **0.113×**, min **0.022×** — 13 rights issues)
    - `QNBFK`: 85.9% off >1.5× (median 0.406×)
    - `AKGRT`: 72.4% off >1.5× (median 0.510×)
    - `INFO`: 60.1% off >1.5× (median 0.394×)
    - `VAKFN`: 55.2% off >1.5× (min **0.001×** — unit glitch in old paid-in capital)
    - `SKBNK`: 54.0% off >1.5× (median 0.667× — 13 rights issues)
    - `MTRYO`: 52.1% off >1.5× (median 0.657×)
    - `YKBNK`: 38.0% off >1.5× (min 0.645×)
    - `ATLAS`: 35.0% off >1.5× (min 0.328×)
    - `ICBCT`: 29.4% off >1.5× (min 0.650×)
