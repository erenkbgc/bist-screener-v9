# Agent Report — Data Engineer Refresh (2026-11-22)

**Branch:** `agent/data` (local only; never pushed, `master`, `config/live_rule.json`, live scoring, and `data/research/trial_ledger.json` untouched).
**As-of date:** `2026-11-22` (latest BIST/global trading session: Friday `2026-11-20`; latest KAP archive day: Saturday `2026-11-21`).
**Test suite:** `.venv/bin/pytest -q` → **521 passed, 0 failed** (including 4 new unit tests in `tests/test_pit_panel_refresh.py`).
**Research trials added:** `0` (pure data refresh & panel extension; `N_sel` unchanged).

---

## 1. What Was Done

### Script & Pipeline Improvements (committed on `agent/data`)
1. **[scripts/build_pit_panel.py](scripts/build_pit_panel.py)**
   - Added `last_ended_quarter()`, `quarter_periods()`, and `fetch_statement_upto_latest()` so the research panel queries İş Yatırım starting from the **latest calendar-ended quarter** (`2026Q3 = (2026, 9)` in November) in 4-period batches, bypassing `borsapy._providers.isyatirim._get_periods()` which stops at `(2026, 6)` throughout November.
   - Added `--update` incremental mode: refreshes `px_raw`, `px_adj`, and `splits` (`period="max"`) plus the latest 8 quarters (`2026Q3..2024Q4`, capturing both `2026Q3` and newly IAS 29 re-expressed `2025Q3`/`2025Q4` vendor columns) and merges them onto preserved older columns (`<= 2024Q3`) via `merge_updated_statement()` without duplicate-label Cartesian blowup.
2. **[scripts/fetch_isyatirim_market_cap.py](scripts/fetch_isyatirim_market_cap.py)**
   - Added `--update`, `--end`, `--workers`, and `--sleep` flags for fast incremental tail updates of `data/research/isy_daily/*.parquet` (`HG_KAPANIS`, `SERMAYE`, `PD`, `HAO_PD`) and regeneration of `data/research/market_cap_monthly.parquet`.
3. **[scripts/fetch_eurobond_monthly.py](scripts/fetch_eurobond_monthly.py)**
   - Made default run incremental (appending only new completed month-ends to `eurobond_monthly.parquet`; `--refresh` preserves full 2008+ rebuild) while refreshing `ust_daily.parquet` through the latest trading day.
4. **[scripts/build_first_published.py](scripts/build_first_published.py)**
   - Added `--since` and `--limit` options, incremental merge with existing `first_published.parquet`, and preference for `data/research/fp/factors_monthly.parquet` when building the liquid target universe.
5. **[scripts/refresh_macro_data.py](scripts/refresh_macro_data.py)** *(new)*
   - Single reproducible command refreshing all macro and benchmark files (`macro_monthly.parquet`, EVDS3 `ipi_tsanay2021.parquet`, `eurobond_monthly.parquet`, `ust_daily.parquet`, `eem_daily.parquet`, `xu100_usdtry_yf_daily.parquet`, `fx.parquet`, `tr_indices.parquet`).
6. **[tests/test_pit_panel_refresh.py](tests/test_pit_panel_refresh.py)** *(new)*
   - Unit tests for calendar quarter boundary logic (`last_ended_quarter`, `quarter_periods`) and statement merge preservation (`merge_updated_statement`, including duplicate `"Finansal Borçlar"` labels).

### Data Refresh Executed (gitignored `data/research/`)
1. Refreshed all macro/market/benchmark series via `scripts/refresh_macro_data.py`.
2. Extended `kap_archive.parquet` through `2026-11-21` via `scripts/build_kap_archive.py --end 2026-11-22` (complete `2026-10.json` + `2026-11.partial.json`; removed stale `2026-10.partial.json`).
3. Updated HisseTekil daily market cap & free float (`PD`, `HAO_PD`) through `2026-11-20` for all 631 tickers (`622` updated, `0` failures, `9` known empty) via `scripts/fetch_isyatirim_market_cap.py --update --end 2026-11-21 --workers 4`.
4. Updated daily prices, splits, and Q3 2026 (plus `2025Q3`/`2025Q4` re-expressed comparatives) for all 583 non-financial tickers (`0` failures) via `scripts/build_pit_panel.py --update --workers 8`.
5. Rebuilt the point-in-time panel in `data/research/fp/` (`factors_monthly.parquet`, `factors_monthly_kapdates.parquet`, `quarterly.parquet`, `STATS.json`) via `scripts/rebuild_panels_first_published.py` (`undo_reexpression` + `bridge_ttm` + İş Yatırım `PD`, C1 constant-unit TTM with CPI through `2026-10`).
6. Built `data/research/first_published.parquet` from all cached KAP reports (`--parse-only`: `816` stock-periods) and sample-fetched 10 fresh `2026Q3` KAP filings (`--since 2026-10-20 --limit 10` → `821` stock-periods, `0` failures) to verify vendor-vs-KAP agreement on `2026Q3`.

---

## 2. Dataset Inventory & Numbers

### Refreshed Files in `data/research/`

| File | Rows | Date / Period Range | Notes |
|---|---:|---|---|
| `macro_monthly.parquet` | 1,188 | `1927-12-31 .. 2026-11-30` | TÜİK CPI through `2026-10` (YoY `29.77%`, MoM `2.58%`); TCMB policy `36.0%` (decision `2026-10-23`) |
| `ipi_tsanay2021.parquet` | 273 | `2004-01-01 .. 2026-09-01` | EVDS3 `TP.TSANAY2021.BCD`; latest `2026-09 = 116.66` (`2026-08 = 107.84`, `2026-07 = 113.91`) |
| `eurobond_monthly.parquet` | 2,706 | `2010-04-30 .. 2026-10-31` | 199 months (+33 USD bonds for `2026-10-31`); spread `2026-10-31 = 2.80%` (live `2026-11-20 = 3.16%`) |
| `ust_daily.parquet` | 4,771 | `2007-12-03 .. 2026-11-20` | `^FVX`, `^TNX`, `^TYX` |
| `eem_daily.parquet` | 5,759 | `2004-01-02 .. 2026-11-20` | EEM adjusted close (`2026-10-31 = 61.04`, `2026-11-20 = 53.84`) |
| `fx.parquet` | 3,988 | `2011-01-03 .. 2026-11-20` | Daily `usdtry` and `xu100` (`borsapy`) |
| `tr_indices.parquet` | 2,088 | `2018-07-16 .. 2026-11-20` | `XU100_CFNNTLTL` and `XUTUM_CFNNTLTL` |
| `xu100_usdtry_yf_daily.parquet` | 5,706 | `2005-01-03 .. 2026-11-20` | yfinance `USDTRY=X`, `XU100.IS` |
| `kap_archive.parquet` | 781,905 | `2010-01-04 .. 2026-11-21` | 989 tickers (`2026-10`: 8,600 rows; `2026-11`: 5,974 rows) |
| `market_cap_monthly.parquet` | 71,864 | `2012-01-31 .. 2026-11-30` | HisseTekil `PD` & `HAO_PD` (`622` tickers updated through `2026-11-20`, `9` empty) |
| `monthly_prices.parquet` | 68,163 | `2011-09-30 .. 2026-11-30` | 582/583 tickers through `2026-11-20` (`UMPAS` last traded `2024-09-30`) |
| `fp/quarterly.parquet` | 24,663 | `2011Q3 .. 2026Q3` | `538` rows of `2026Q3`; `undo_reexpression` divided `39,069` vendor values (`421` TL IAS 29 tickers) |
| `fp/factors_monthly_kapdates.parquet` | 59,691 | `2012-10-31 .. 2026-11-30` | `isyatirim_pd`: `59,104`, `price_x_shares`: `587` |
| `fp/factors_monthly.parquet` | 59,607 | `2012-10-31 .. 2026-11-30` | Lag-75 variant (`isyatirim_pd`: `59,020`, `price_x_shares`: `587`) |
| `first_published.parquet` | 821 | `2023-01-23 .. 2026-10-22` | Parsed from cached KAP pages + 10 newly fetched `2026Q3` filings |

### Key Latest Macro Snapshot
- **XU100:** `11,947.2` (`2026-09-30`) → `10,759.6` (`2026-10-31`) → `11,131.3` (`2026-11-20`)
- **USD/TRY:** `49.01` (`2026-09-30`) → `49.94` (`2026-10-31`) → `50.56` (`2026-11-20`)
- **EEM:** `66.79` (`2026-09-30`) → `61.04` (`2026-10-31`) → `53.84` (`2026-11-20`)
- **Turkey USD Eurobond Spread (10Y interpol., Ziraat vs UST):** `2.66%` (`2026-09-30`) → `2.80%` (`2026-10-31`) → `3.16%` (live `2026-11-20`)
- **TÜİK CPI:** `2026-09`: YoY `29.73%`, MoM `1.84%`; `2026-10`: YoY `29.77%`, MoM `2.58%`
- **TCMB Policy Rate:** cut `37.0%` → `36.0%` on `2026-10-23`
- **EVDS Industrial Production (`TP.TSANAY2021.BCD`):** `2026-09 = 116.66`

---

## 3. Q3 2026 (`2026Q3`) Coverage & Verification

### Coverage Summary (Non-Financial Universe: 583 stocks)
- **Vendor (`raw/*.pkl` `bs` & `inc`):** **538 / 583 (92.3%)** have complete `2026Q3` balance sheet and income statement.
- **KAP (`kap_archive.parquet`, `FR` `9 Aylık`):** **538 / 583 (92.3%)** — **exact 1-to-1 match** (`0` in vendor without KAP, `0` in KAP without vendor).
- **KAP availability timing (respecting 18:00 session-close cutoff):**
  - Publication timestamps: `2026-10-21 18:15:36` through `2026-11-19 22:53:07`.
  - Available `<= 2026-10-31`: **184** stocks (`165` in `fp/factors_monthly_kapdates` on `2026-10-31`, remainder `<14m` IPOs).
  - Available `2026-11-01 .. 2026-11-20`: **354** stocks.
  - Available `> 2026-11-20`: **0** stocks (zero look-ahead mismatch against `2026-11-20` prices).
- **TTM completeness in `fp/quarterly.parquet`:** `538/538` have equity; `537/538` have C1 constant-unit TTM revenue, operating profit, and net income (`1` missing TTM: `NETGL`, insufficient consecutive quarterly history).
- **In `fp/factors_monthly_kapdates.parquet` on `2026-11-30` (`536` stocks total):**
  - `2026Q3`: **500** (`38` of the 538 are recent IPOs with `< 14` monthly price bars required by `i >= 13` for `mom_12_1`: `AAGYO, AKHAN, ALBTN, ARFYE, ATATR, BESTE, BETAE, BKRGY, CITAS, ECOGR, EKDMR, EKIM, EMPAE, FRMPL, GENKM, GOLDA, INTET, ISVEA, KARCL, KPEKS, LXGYO, MASFN, MCARD, METEN, MEYSU, NETCD, NETGL, ORZAX, PAHOL, SARAE, SOHOE, SSAAT, SVGYO, TKNKA, UCAYM, VEYAS, ZERGY, ZGYO`).
  - `2026Q2`: **28**
  - `2026Q1`: **8**
- **In `fp/factors_monthly.parquet` (lag-75) on `2026-11-30`:** `0` stocks use `2026Q3` (`2026-09-30 + 75d = 2026-12-14 > 2026-11-30`), confirming lag rules are strictly enforced.

### Empirical IAS 29 Re-Expression & First-Published Check
- Confirmed empirically on TL IAS 29 reporters (`ARCLK, AKCNS, BIMAS, FROTO`) that uploading `2026Q3` caused İş Yatırım to re-express `2025Q4` by `1.0557` (`CPI(2026Q3)/CPI(2026Q2) = 1.0556`) and `2025Q3` revenue by `1.2973` (`CPI(2026Q3)/CPI(2025Q3) = 1.2972`); `undo_reexpression` correctly undid both (`39,069` values divided vs `36,185` previously).
- Cross-checked 9 freshly fetched `2026Q3` KAP filings (`AFYON, AKFGY, DZGYO, EBEBK, EREGL, ISDMR, KLGYO, METRO, TAVHL`) against İş Yatırım `2026Q3`: **ratio = `1.0000` on all 5 items** (`total_assets`, `equity_parent`, `revenue`, `op_profit`, `net_income`) for **9 / 9** companies.

### Missing `2026Q3` List (45 / 583 Non-Financial Stocks)

1. **Special (non-calendar) fiscal year — 14 stocks** (filed `3 Aylık` or `6 Aylık` in Sep–Nov 2026, not `9 Aylık`):
   - Sports clubs (Jun–May FY, `3 Aylık` on `2026-10-12`): `BJKAS`, `FENER`, `GSRAY`, `TSPOR`
   - Apr–Mar FY (`6 Aylık` in Nov 2026): `ARENA` (Nov 18), `BORSK` (Nov 9), `DOCO` (Nov 12), `MARTI` (Nov 19), `MRGYO` (Nov 9)
   - Other off-cycle FYs: `BALSU` (`3 Aylık` Nov 10), `MERKO` (`3 Aylık` Oct 30), `KAYSE` (`3 Aylık` Sep 9), `MAVI` (`6 Aylık` Sep 16, Feb–Jan FY), `MEGAP` (`3 Aylık` Jun 5)
2. **No current KAP FR / delisted / suspended / renamed — 8 stocks:**
   - `DAGHL`, `MARKA`, `METUR`, `PEHOL`, `ROYAL`, `SELGD`, `YGYO` (no KAP FR disclosures), `UMPAS` (last price `2024-09-30`, filed `Yıllık` on Nov 4)
3. **Calendar-year companies without `2026Q3` KAP filing as of `2026-11-21` — 23 stocks:**
   - Semi-annual-only (also lacked `2025Q3`, 1): `ALVES`
   - Had `2025Q3` previously, no `2026Q3` yet (22, includes PÖİP / watch-list / late filers): `ATSYH`, `AYES`, `BALAT`, `BASCM`, `BTCIM`, `EMKEL`, `GUNDG`, `INTEK`, `ISBIR`, `KONTR`, `KSTUR`, `KUYAS`, `ORMA`, `PAPIL`, `PEKGY`, `RALYH`, `SODSN`, `SUMAS`, `TEHOL`, `TRHOL`, `YBTAS`, `YONGA`

---

## 4. Latest Month's Top-20% `value_sn` Picks vs Live Picks (`data/forward_record`)

Live reference: `data/forward_record/decisions.jsonl` (`rebalance_date = 2026-11-01`, `rule_version = R0-2026-10-12`, prices as of `2026-10-30`, statements `2026Q2: 227, 2026Q1: 6`): **233** ranked liquid stocks, **47** holdings.

### Head-to-Head Summary

| Panel Snapshot | Liquid Univ. | Top-20% Picks | Overlap w/ 47 Live Holdings | Common Univ. (of 233) | Spearman Rank Corr | Common-Univ Top-20% (43) Overlap |
|---|---:|---:|---:|---:|---:|---:|
| **`fp_kapdates 2026-11-30`** *(as of 2026-11-20, 358/375 on `2026Q3`)* | **375** | **75** | **32 / 47 (68.1%)** *(Jaccard 35.6%)* | 217 | **0.891** | **31 / 43 (72.1%)** |
| `fp_kapdates 2026-10-31` *(Oct month-end, 104/375 on `2026Q3`)* | 375 | 75 | 33 / 47 (70.2%) *(Jaccard 37.1%)* | 217 | 0.935 | 36 / 43 (83.7%) |
| `fp_lag75 2026-10-31` *(Oct month-end, 368/375 on `2026Q2`)* | 375 | 75 | 34 / 47 (72.3%) *(Jaccard 38.6%)* | 217 | 0.962 | 36 / 43 (83.7%) |

### Why the Full Universe Differs (375 Panel vs 233 Live)
1. **Liquidity cutoff:** Live applies a 10M TL floor + universe gates before the bottom-30% cut, yielding a `tl_vol_med60` floor of **`32.28M TL`** (`233` stocks). The research panel drops the bottom 30% of all `536` stocks directly, yielding a floor of **`14.07M TL`** (`375` stocks — including names like `DGATE`, `YATAS`, `SRVGY`, `PLTUR`, `BESLR`, `ARASE` that were scored in live DB with high `valuation_z` but cut by the `32.28M TL` liquidity threshold).
2. **Holdings absent from live `forward_record` universe:** `0` `Holding`-sector tickers appeared in `2026-11-01` live `scores` / `forward_record` universe, whereas the research panel includes liquid holdings (`AGHOL, BERA, DOHOL, GLRYH, GSDHO, HDFGS, ISGSY, KCHOL, METRO, NTHOL, PRDGS, SAHOL` are in the `2026-11-30` panel top-20%).
3. **Recent IPOs (`< 14` months):** `16` stocks in the live `2026-11-01` universe (including live holdings `FRMPL` and `GENKM`) have fewer than 14 monthly price bars and are excluded from the research panel by `i >= 13` (`mom_12_1` requirement).
4. **Q3 2026 statement shift:** On `2026-10-31`, using `2026Q2` (lag-75) yields Spearman `0.962` with live; turning on KAP-dated `2026Q3` lowers Spearman to `0.935` on `2026-10-31` (104 early filers) and to `0.891` on `2026-11-30` (358 Q3 filers + 3 weeks of November price moves).

### Detailed `2026-11-30` (`fp_kapdates`, as of `2026-11-20`) Breakdown vs `2026-11-01` Live Holdings
- **Kept in both (`32` of `47` live holdings):**
  `AKFGY, AKFYE, ARCLK, AYDEM, DAPGM, DOAS, EUREN, GLRMK, GOKNR, GSDDE, HLGYO, INDES, IZMDC, KARSN, KATMR, KZBGY, MEGMT, MOPAS, MRGYO, NTGAZ, PCILT, RUBNS, SARKY, SNGYO, SOKM, THYAO, TRENJ, TUREX, ULKER, ULUUN, YIGIT, YYLGD`
- **Live holdings outside `2026-11-30` panel top-20% (`15`):**
  - Dropped by rank (all on `2026Q3`, 13): `TTKOM` (#80, 21.3%, `z=+0.293`), `FROTO` (#86, 22.9%, `+0.273`), `LMKDC` (#88, 23.5%, `+0.260`), `ADESE` (#91, 24.3%, `+0.254`), `LILAK` (#95, 25.3%, `+0.237`), `MERCN` (#96, 25.6%, `+0.228`), `GWIND` (#104, 27.7%, `+0.200`), `EGEGY` (#106, 28.3%, `+0.196`), `PSGYO` (#116, 30.9%, `+0.135`), `SELEC` (#123, 32.8%, `+0.122`), `CATES` (#141, 37.6%, `+0.067`), `IZENR` (#171, 45.6%, `-0.036`), `FORTE` (#176, 46.9%, `-0.048`)
  - Not in panel (`< 14m` price history, 2): `FRMPL`, `GENKM`
- **New entrants from the `2026-11-01` live universe (`5`):** `KORDS`, `KRDMA`, `KRDMD`, `SISE`, `TUPRS`
- **Panel top-20% picks outside the `2026-11-01` live universe (`38`):** `A1YEN, AGHOL, AHSGY, ARASE, ASGYO, BERA, BESLR, BIENY, BUCIM, DERHL, DGATE, DOHOL, EDIP, EPLAS, ESCOM, GLRYH, GOLTS, GSDHO, HDFGS, ISGSY, KCHOL, KRSTL, LKMNH, LRSHO, MERIT, METRO, MNDRS, NETAS, NTHOL, PLTUR, PNSUT, PRDGS, SAHOL, SRVGY, TATGD, VESBE, VKGYO, YATAS`

### Top 25 of `fp_kapdates 2026-11-30` (`value_sn_z`, 75 picks total)

| Rank | Ticker | `value_sn_z` | Stmt | B/M | E/P | S/P | EBIT/EV | MCap (B TL) | Live `2026-11-01` |
|---:|---|---:|---|---:|---:|---:|---:|---:|---|
| 1 | `ULUUN` | +2.297 | 2026Q3 | 4.15 | 0.03 | 21.69 | — | 4.18 | LIVE |
| 2 | `INDES` | +2.272 | 2026Q3 | 1.42 | 0.17 | 22.72 | 0.96 | 6.33 | LIVE |
| 3 | `DGATE` | +1.908 | 2026Q3 | 0.39 | 0.13 | 16.87 | 0.91 | 1.25 | outside live univ (`tlvol60` < 32.3M) |
| 4 | `GLRYH` | +1.760 | 2026Q3 | 7.45 | -0.10 | 1.51 | 2.78 | 0.75 | outside live univ (Holding) |
| 5 | `HDFGS` | +1.647 | 2026Q3 | 3.44 | 0.19 | 0.89 | 0.84 | 1.29 | outside live univ (Holding) |
| 6 | `MRGYO` | +1.631 | 2026Q2 | 6.14 | 1.17 | 0.10 | 1.00 | 2.54 | LIVE |
| 7 | `HLGYO` | +1.593 | 2026Q3 | 5.44 | 1.33 | 1.33 | 0.93 | 13.09 | LIVE |
| 8 | `SRVGY` | +1.584 | 2026Q3 | 5.92 | 0.63 | 0.83 | 1.15 | 5.56 | outside live univ (`tlvol60` < 32.3M) |
| 9 | `ISGSY` | +1.393 | 2026Q3 | 2.68 | 0.58 | 0.97 | 0.46 | 5.04 | outside live univ (Holding) |
| 10 | `AGHOL` | +1.390 | 2026Q3 | 2.39 | 0.05 | 14.82 | 0.12 | 60.88 | outside live univ (Holding) |
| 11 | `YATAS` | +1.354 | 2026Q3 | 4.60 | 0.18 | 9.85 | 0.13 | 2.94 | outside live univ (`tlvol60` < 32.3M) |
| 12 | `ESCOM` | +1.266 | 2026Q3 | 1.97 | 0.81 | 1.44 | 1.44 | 2.33 | outside live univ |
| 13 | `BERA` | +1.207 | 2026Q3 | 5.53 | -0.03 | 3.65 | 0.45 | 6.70 | outside live univ (Holding) |
| 14 | `PLTUR` | +1.205 | 2026Q3 | 3.09 | 0.21 | 3.35 | 0.43 | 3.39 | outside live univ (`tlvol60` < 32.3M) |
| 15 | `KZBGY` | +1.172 | 2026Q3 | 6.43 | 0.40 | 0.91 | 0.61 | 4.52 | LIVE |
| 16 | `DOAS` | +1.050 | 2026Q3 | 3.19 | -0.02 | 10.83 | 0.09 | 24.46 | LIVE |
| 17 | `BESLR` | +0.982 | 2026Q3 | 3.60 | 0.25 | 7.09 | 0.29 | 5.98 | outside live univ (`tlvol60` < 32.3M) |
| 18 | `ARASE` | +0.961 | 2026Q3 | 1.93 | 0.18 | 3.21 | 0.63 | 13.52 | outside live univ (`tlvol60` < 32.3M) |
| 19 | `ARCLK` | +0.935 | 2026Q3 | 1.68 | -0.15 | 13.80 | 0.03 | 43.08 | LIVE |
| 20 | `RUBNS` | +0.799 | 2026Q3 | 5.89 | 0.15 | 3.03 | 0.31 | 1.02 | LIVE |
| 21 | `EDIP` | +0.799 | 2026Q3 | 6.14 | 0.33 | 0.65 | 0.35 | 1.42 | outside live univ |
| 22 | `METRO` | +0.755 | 2026Q3 | 1.67 | 0.49 | 0.06 | 0.59 | 4.91 | outside live univ (Holding) |
| 23 | `AHSGY` | +0.749 | 2026Q3 | 1.92 | 0.50 | 0.06 | 0.90 | 5.95 | outside live univ |
| 24 | `GSDHO` | +0.747 | 2026Q3 | 3.88 | 0.13 | 0.56 | 0.41 | 3.94 | outside live univ (Holding) |
| 25 | `KATMR` | +0.740 | 2026Q3 | 4.66 | 0.18 | 1.02 | 0.17 | 2.37 | LIVE |

---

## 5. Commits on `agent/data`

1. `937b6d5` — `data: incremental PIT panel, Q3 2026 statements, HisseTekil and macro refresh scripts` (`scripts/build_pit_panel.py`, `scripts/build_first_published.py`, `scripts/fetch_isyatirim_market_cap.py`, `scripts/fetch_eurobond_monthly.py`, `scripts/refresh_macro_data.py`, `tests/test_pit_panel_refresh.py`).
2. *(Next commit)* — `docs: add AGENT_REPORT.md for 2026-11-22 data refresh`.

---

## 6. Open Problems & Honest Caveats

1. **Live scoring blind spot on `2026Q3` in November (CRITICAL — untouched per role rules):** `borsapy._providers.isyatirim._get_periods()` hardcodes `current_month <= 11 -> start_period = 6 (Q2)`, so `core/pit_panel.fetch_statement()` (used by `core/live_data.py`) never requests `2026Q3` until December 1, even though 538 non-financial `2026Q3` statements are already live on İş Yatırım. In addition, CI's ~98% `kap_missing_share` falls back to the 75-day lag (`2026-12-14`), blocking `2026Q3` even if fetched. Fixing `core/pit_panel.fetch_statement` + pushing KAP dates outside CI (plan P3-3) is needed for the `2026-12-01` rebalance.
2. **Rolling `period="max"` price history start shifted by 1 month:** Refreshing TradingView `px_raw`/`px_adj` via `period="max"` shifted the earliest bar from `2011-08-31` to `2011-09-30`, so `factors_monthly*` now starts at `2012-10-31` instead of `2012-09-30`. The discovery (`2013-01..2020-12`, 28,664 rows) and holdout (`2021-01+`) windows are **unaffected**. To prevent future pre-2013 erosion, `--update` should append new bars onto stored history (rescaling adjusted closes on corporate actions, like `core/forward_prices.py`) rather than overwriting with TradingView's rolling window.
3. **`2026-11-30` is a partial month-to-date snapshot:** Prices reflect Friday `2026-11-20` (labelled `2026-11-30` by `resample("ME").last()`, consistent with the `2026-09-27` build). `2026-10-31`'s `fwd_ret_1m` is month-to-date through `2026-11-20`, and `2026-11-30`'s `fwd_ret_1m` is `NaN`; re-run `build_pit_panel.py --update` + `rebuild_panels_first_published.py` after `2026-11-30` close to finalize November returns.
4. **`reexpression_class.parquet` coverage & foreign-currency Q4 check:** `33` stocks remain `unknown` (plan P2-1), and `14` newly liquid stocks (`BIOEN, BJKAS, BSOKE, BURCE, CANTE, DOFRB, FENER, GSRAY, KAYSE, KUVVA, MARMR, MAVI, TKNSA, TSPOR`) are not yet classified in `reexpression_class.parquet` (`CANTE` and `KAYSE` appear near top valuation ranks). Also, `THYAO` (classified `not_reexpressed`) showed a `1.0557` (`CPI(2026Q3)/CPI(2026Q2)`) jump in vendor `2025Q4` when `2026Q3` arrived, suggesting İş Yatırım may CPI-index `Q4` comparatives even for some foreign-functional-currency reporters — worth auditing in `classify_reexpression.py`.
5. **9 stocks without HisseTekil history (plan P2-2):** `CITAS, DAGHL, INTEK, LRSHO, LYDHO, MARKA, METUR, PEHOL, SELGD` still return empty from HisseTekil (`587` historical stock-months, `3` stocks in `2026-11-30` fall back to `price_x_shares`).
6. **Full `first_published.parquet` backfill (plan P2-3):** `821` stock-periods are parsed (cached + 10 sampled `2026Q3` pages); downloading the remaining ~7,200 KAP pages remains rate-limited (~15s/page under HTTP 429) and requires an overnight resume run.
7. **Live Holding-sector discrepancy:** `0` `Holding`-sector stocks appeared in `2026-11-01` live `scores` / `forward_record` universe despite being present in `universe` and `fundamentals` (`KCHOL, SAHOL, AGHOL, DOHOL` etc.), creating a systematic gap between research-panel top-20% picks and live `forward_record` picks.
