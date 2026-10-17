# Sector-specific valuation models (Banks/Financials, Holdings, and REITs): pre-registration

Written and committed on 2026-10-17, **before** the sector-specific panel builder and evaluation script were executed. All factor definitions, templates, windows, and decision rules are fixed here and are not modified after seeing the results.

## Question

The live monthly rotation rule (`R0-2026-10-12`) ranks non-financial BIST stocks by `value_sn` (`bm, ep, sp, ey`) and excludes all 53 tickers in `core/pit_panel.py::FINANCIAL_SECTORS` (`Bankacılık`, `Sigorta`, `Emeklilik`, `Faktoring`, `Finansal Kiralama`, `Aracı Kurum`, `Menkul Kıymet Yat. Ort.`, `Varlık Yönetimi`, `Tasarruf Finansman`). While `R0` beats its own costed equal-weighted non-financial universe in the 2021–2026 holdout (+6.89%/yr, $t = 2.55$), it trails the bank-heavy BIST 100 Total Return index (`XU100_CFNNTLTL`) by −1.71%/yr ($t = -0.28$, `total_return_benchmarks_preregistration.md`).

Furthermore, two non-financial sectors already inside the C1 panel have distinct balance-sheet structures where standard industrial multiples (`sp` and `ey`) may be noisy (`docs/research/sector_specific_notes.md`):
1. **Banks (`Bankacılık`, 13 tickers) and broader Financials (52 active tickers with İş Yatırım templates):** Banks have no industrial sales (`sp`) or enterprise-value `EBIT/EV` (`ey`); standard valuation theory (BIS 2018) prices banks on **Book-to-Market (`B/M`, inverse `PD/DD`) conditioned on `ROE`**.
2. **Holdings (`Holding`, 52 tickers in C1 panel):** Consolidated holding statements frequently combine industrial subsidiaries with banking/financial subsidiaries (e.g., `KCHOL`, `SAHOL`), distorting consolidated `sp` and `ey` (`fin_debt` vs banking deposits/loans), whereas equity-level multiples (`bm`, `ep`, `roe`) and balance-sheet asset backing (tangible equity, financial investments, equity-method associates net of holding debt) avoid consolidation perimeter noise.
3. **REITs (`Gayrimenkul`, 62 tickers in C1 panel):** Turkish REITs revalue investment properties (`Yatırım Amaçlı Gayrimenkuller`) to fair value (mostly in Q4), which inflates bottom-line net income (`ep`) with non-cash revaluation gains, whereas recurring operating cash flow / EBIT yield (`op_ep = ttm_ebit / mcap`), direct property + inventory NAV backing (`(inv_property + inventories + cash - fin_debt) / mcap`), or Letdin & Sirmans (2020) fundamental-adjusted `B/M` residuals isolate recurring cash yield and sentiment discounts.

This study builds the first point-in-time historical panel for BIST financial institutions across all five İş Yatırım reporting templates (`UFRS`, `UFRS_K`, `UFRS_B`, `XI_29`, `XI_29K`) and tests four pre-registered questions (`S1`–`S4`).

## Statistical power and scope disclosure

- **Banks (`Bankacılık`) have only 13 listed tickers** (10–13 active per month). A top-20% basket holds only 2–3 banks per month. Even a large true return spread has low statistical power over 68 holdout months. Therefore, **within-bank results (`S1a`) are explicitly classified as descriptive / low-power**, and the confirmatory cross-sectional test (`S1b`) is evaluated both across the pooled **All-Financials universe (52 tickers, sector-neutralized)** and via the **full-market costed portfolio simulation (`S4`)**.
- **Holdings (`S2`, 52 tickers) and REITs (`S3`, 62 tickers)** each have 25–45 liquid names per month in recent years (fewer in 2013–2016). Their sector-internal comparisons and their impact on the full non-financial top-20% portfolio are evaluated with paired Newey-West $t$-statistics (6 lags).

## Data and point-in-time construction

1. **Financials point-in-time panel (`data/research/raw_fin/<TICKER>.pkl`):**
   - For the 53 tickers in `FINANCIAL_SECTORS` (`config/fintables_ticker_sektor.json`), quarterly financial statements (`last_n = 60`, 2011–2026) are fetched from İş Yatırım using each sub-sector's native template without Cartesian row duplication (`core/pit_panel.py::merge_statement_batches`):
     - `Bankacılık` (13) and `Sigorta` / `Emeklilik` (7): `UFRS` (with `UFRS_K` fallback for `QUICK`),
     - `Varlık Yönetimi` (3): `UFRS_B`,
     - `Faktoring` (6), `Finansal Kiralama` (5), `Tasarruf Finansman` (1): `XI_29K`,
     - `Aracı Kurum` (9) and `Menkul Kıymet Yat. Ort.` (9): `XI_29`.
   - Extracted items:
     - `total_assets`: `"TOPLAM VARLIKLAR"` or `"AKTİF TOPLAMI"`,
     - `equity`: `"Ana Ortaklığa Ait Özkaynaklar"`, `"Özkaynaklar"`, `"XVI. ÖZKAYNAKLAR"`, `"ÖZKAYNAK"`, or `"Özsermaye Toplamı"`,
     - `paid_in`: `"Ödenmiş Sermaye"`, `"16.1 Ödenmiş Sermaye"`, `"14.1 Ödenmiş Sermaye"`, `"13.1 Ödenmiş Sermaye"`, `"A- Ödenmiş Sermaye"`, or `"1- (Nominal) Sermaye"`,
     - `net_income` (YTD flow): `"Ana Ortaklık Payları"`, `"DÖNEM KARI (ZARARI)"`, `"23.1 Grubun Karı/Zararı"`, `"XXIII. NET DÖNEM KARI/ZARARI (XVII+XXII)"`, `"XVIII. NET DÖNEM KARI/ZARARI (XVII+XXII)"`, `"NET DÖNEM KARI (ZARARI)"`, `"N- Dönem Net Karı veya Zararı"`, or `"3- Dönem Net Kar veya Zararı"`,
     - `op_profit` (YTD flow): `"FAALİYET KARI (ZARARI)"`, `"Net Faaliyet Kar/Zararı"`, or `"XI. NET FAALİYET KARI/ZARARI (VIII-IX-X)"`.
   - Quarterly flows and 4-quarter consecutive TTMs are formed with C1 constant purchasing power (`core/pit_panel.py::quarterly_table`, CPI adjustment for `>= 2023Q4`) and matched to actual KAP first publication dates (`data/research/kap_archive.parquet`, 75/100-day fallback when unmatched).
2. **Holdings and REITs extended balance-sheet panel:**
   - From the existing `data/research/raw/*.pkl` caches for all `Holding` (52) and `Gayrimenkul` (62) tickers, we extract additional point-in-time balance-sheet items:
     - `inv_property`: `"Yatırım Amaçlı Gayrimenkuller"`,
     - `inventories`: `"Stoklar"` (summed across short- and long-term occurrences),
     - `fin_investments`: `"Finansal Yatırımlar"` (summed across short- and long-term occurrences),
     - `eq_investments`: `"Özkaynak Yöntemiyle Değerlenen Yatırımlar"`,
     - `intangibles`: `"Maddi Olmayan Duran Varlıklar"`,
     - `goodwill`: `"Şerefiye"`,
     - `fin_sector_liab`: `"Finans Sektörü Faaliyetlerinden Borçlar"` (summed across occurrences).
3. **Sample windows:**
   - **Discovery:** 2013-04 to 2020-12 (93 months).
   - **Holdout:** 2021-01 to 2026-08 (68 months).

## Hypotheses and models (fixed)

### S1. Banks (`Bankacılık`, 13 tickers) and All Financials (52 tickers)
Within each month (dropping the bottom 30% by `tlvol60` in the pooled financial test; no liquidity drop in the 13-bank descriptive test so all listed banks are observed):
- **`B0_bm` (Inverse P/B):** cross-sectionally standardized `bm = equity / mcap`.
- **`B1_bm_roe` (Valuation + Profitability composite):** equal-weighted average of `bm_z` and `roe_z` (`roe = ttm_net_income / equity`), plus `ep_z` (`ttm_net_income / mcap`).
- **`B2_pb_roe_resid` (ROE-conditioned P/B residual):** cross-sectional OLS residual $e_i = \text{bm\_z}_i - (\hat{\alpha} + \hat{\beta}\,\text{roe\_z}_i)$ within each month (positive residual = cheaper than warranted by `ROE`).
- **Metrics:** monthly Spearman Rank-IC (NW $t$, 6 lags), top-3 vs bottom-3 bank spread (`S1a`, descriptive), and top-20% vs sector-EW spread across all liquid financials (`S1b`, sector-neutralized with `min_n = 3`).

### S2. Holdings (`Holding`, 52 tickers)
Within the liquid `Holding` cross-section each month:
- **`H0_value_sn` (Baseline 4-leg):** `mean(bm_z, ep_z, sp_z, ey_z)` demeaned within `Holding`.
- **`H1_bm_ep_roe` (Equity-only valuation + ROE):** `mean(bm_z, ep_z, roe_z)` demeaned within `Holding` — removes consolidated `sp` and `ey` (which mix bank/industrial subsidiaries).
- **`H2_backing_nav` (Balance-sheet asset-backing composite):** `mean(tangible_bm_z, fin_backing_z, ep_z)` demeaned within `Holding`, where:
  - $\text{tangible\_bm} = (\text{equity} - \text{intangibles} - \text{goodwill}) / \text{mcap}$,
  - $\text{fin\_backing} = (\text{cash} + \text{fin\_investments} + \text{eq\_investments} - \text{fin\_debt}) / \text{mcap}$.
- **Metrics:** within-Holding Rank-IC (NW $t$), top-20% minus Holding EW return spread, and paired portfolio return difference when `H1` or `H2` replaces `H0` for Holding stocks inside the full non-financial top-20% screener.

### S3. REITs (`Gayrimenkul`, 62 tickers)
Within the liquid `Gayrimenkul` cross-section each month:
- **`G0_value_sn` (Baseline 4-leg):** `mean(bm_z, ep_z, sp_z, ey_z)` demeaned within `Gayrimenkul`.
- **`G1_nav_ffo` (Property NAV backing + Operating Cash-Flow/EBIT yield):** `mean(bm_z, prop_nav_z, op_ep_z)` demeaned within `Gayrimenkul`, where:
  - $\text{prop\_nav} = (\text{inv\_property} + \text{inventories} + \text{cash} - \text{fin\_debt}) / \text{mcap}$,
  - $\text{op\_ep} = \text{ttm\_op\_profit} / \text{mcap}$ (recurring operating profit yield over market cap, excluding Q4 fair-value revaluation spikes in net income).
- **`G2_letdin_sirmans_resid` (Fundamental-adjusted B/M residual):** cross-sectional OLS residual of `bm_z` regressed on `roe_z`, leverage (`fin_debt / total_assets`), and `size_z` (`log(mcap)`) within `Gayrimenkul` each month.
- **Metrics:** within-REIT Rank-IC (NW $t$), top-20% minus REIT EW return spread, and paired portfolio return difference when `G1` or `G2` replaces `G0` for REIT stocks inside the full non-financial top-20% screener.

### S4. Costed Full-Market Portfolio Simulation (`Non-Financials + Financials`, 1M TL, base costs)
Using `core/portfolio_backtest.py::simulate` (1M TL real capital, base costs, next-day close fills, cash at policy rate):
- **`P0_nonfin_baseline`:** Current live rule (`R0`: non-financial liquid top 20% by `value_sn`).
- **`P1_nonfin_sector_specialized`:** Non-financial liquid top 20% where `Holding` uses `H1_bm_ep_roe` and `Gayrimenkul` uses `G1_nav_ffo`, while all other non-financial sectors use `value_sn`.
- **`P2_all_bist_with_financials`:** Combined liquid universe (Non-Financials + Financials, dropping bottom 30% by `tlvol60` overall), holding the top 20% of non-financials by `value_sn` and the top 20% of financials by sector-neutral `B1_bm_roe` (`mean(bm_z, ep_z, roe_z)`).
- **Benchmarks compared:**
  1. Costed equal-weighted non-financial universe (`EW net`),
  2. BIST 100 Total Return (`XU100_CFNNTLTL`, from 2016-01 onward as in `total_return_benchmarks_preregistration.md`),
  3. Paired net return difference $D = r_{\text{net}}(P_k) - r_{\text{net}}(P_0)$ in Discovery and Holdout.

## Decision rules

1. **Within-sector replacement (`S2` Holdings, `S3` REITs, `P1`):** A specialized sector model replaces `value_sn` in that sector only if the paired portfolio difference $D = r_{\text{net}}(P_1) - r_{\text{net}}(P_0)$ (or the within-sector top-20% spread difference) is positive with NW $t > 3.0$ in Discovery and $t > 2.0$ in Holdout.
2. **Financial sleeve inclusion (`S1` / `P2`):** Including financials in the main rotation (`P2`) passes as a confirmatory upgrade over `P0` if $D = r_{\text{net}}(P_2) - r_{\text{net}}(P_0) > 0$ with $t > 2.0$ in Holdout **and** does not degrade Discovery return by more than −1.0%/yr ($t > -1.0$), while improving Holdout active return against BIST 100 Total Return (`XU100_CFNNTLTL`).
3. **Descriptive bank scorecard (`S1a`):** Because $N \le 13$ banks cannot support an HLZ $t > 3.0$ portfolio gate on its own, `B1_bm_roe` and `B2_pb_roe_resid` are evaluated descriptively for the bulletin's separate financial watchlist ("test edildi — düşük örneklem gücü" vs "test edilmedi").
4. **Live rule:** `config/live_rule.json` (`R0-2026-10-12`) is not modified automatically by this script.

## Results (added 2026-10-17, after the run; the sections above are unchanged)

Runner: `python3 scripts/research_financials_holdings_reits.py` → `data/reports/research_financials_holdings_reits_2026-10-17.json`.

### 0. Financials point-in-time panel coverage, sub-sector row matching, and template audit

1. **Universe accounting (53 configured tickers $\to$ 52 with statements $\to$ 49 in the monthly factor panel):**
   - Across the 53 tickers in `FINANCIAL_SECTORS`, **52** have quarterly financial statements in İş Yatırım (`QNBFL` has 0 statement/price rows because it is the legacy ticker code of `QNBFK` — QNB Finansal Kiralama — which is already present in the panel).
   - **3 recent IPOs** have complete statement rows but fewer than 13 months of trading history (required for 12-month trailing metrics plus 1-month forward return) and are therefore excluded from `financials_factors_monthly.parquet`:
     - `ENPRA` (`Bankacılık`, 10 statement quarters, 132 trading days — leaving **12** banks in the `S1a` panel: `AKBNK`, `ALBRK`, `GARAN`, `HALKB`, `ICBCT`, `ISCTR`, `KLNMA`, `QNBTR`, `SKBNK`, `TSKB`, `VAKBN`, `YKBNK`),
     - `QUICK` (`Sigorta`, 1 statement quarter, 52 trading days),
     - `VAKFA` (`Faktoring`, 17 statement quarters, 228 trading days).
   - The remaining **49 tickers** yield **6,582 stock-month observations** across 162 months (2013-04 to 2026-09): `Bankacılık` (12), `Aracı Kurum` (9), `Menkul Kıymet Yat. Ort.` (9), `Faktoring` (5), `Finansal Kiralama` (4), `Sigorta` (4), `Varlık Yönetimi` (3), `Emeklilik` (2), `Tasarruf Finansman` (1).
2. **Sub-sector line-item mapping completeness (`100%` across all 52 non-empty tickers):**
   - With the BDDK (`UFRS`, `XI_29K`, `UFRS_B`), SEDDK (`UFRS`), and SPK (`XI_29`) row aliases mapped in `FIN_BS_ITEMS` and `FIN_INC_ITEMS`, all 9 required balance-sheet and income-statement items (`total_assets`, `equity`, `paid_in`, `cash`, `fin_debt`, `revenue`, `gross_profit`, `op_profit`, `net_income`) achieve **100.0% ticker match rate** across all 9 financial sub-sectors.
3. **Cross-template consistency & restatement limitation:**
   - For `Bankacılık`, `Sigorta`, and `Emeklilik`, İş Yatırım exposes both `UFRS` (unconsolidated regulatory statements) and `UFRS_K` (consolidated group statements). In banks with large industrial/non-bank holdings (e.g., `ISCTR`, which consolidates `SISE`), `UFRS_K` reports ~17% higher equity and ~40% higher net income than solo `UFRS`, and in insurance (`AKGRT`), `UFRS_K` is missing recent quarters that are present in `UFRS`. Our pipeline strictly locks `Bankacılık`, `Sigorta`, and `Emeklilik` to unconsolidated regulatory **`UFRS`** (`SECTOR_TEMPLATE_ORDER` stops at the first non-empty template per ticker) and never mixes `UFRS` and `UFRS_K`. For `Faktoring`/`Finansal Kiralama`/`Tasarruf Finansman` (`XI_29K`), `Aracı Kurum`/`MKYO` (`XI_29`), and `Varlık Yönetimi` (`UFRS_B`), only one template is populated per company.
   - **Data source restatement limitation:** While `apply_report_dates()` anchors each quarter's availability to the actual KAP filing timestamp (`kap_archive.parquet`), İş Yatırım's `MaliTablo` API returns the latest comparative/restated column for a given `year/quarter` rather than an immutable archival snapshot of the initial KAP filing.

### S1. Banks (`S1a`, 12 tickers) and All Liquid Financials (`S1b`, 49 tickers, `liq_drop = 0.30`)

| Universe & Model | Coverage (Obs / Min Month) | Window | Mean Rank-IC ($t$) | Top Basket − Sector EW %/yr ($t$) | Paired Diff vs Base %/yr ($t$) |
|---|---:|---|---:|---:|---:|
| **S1a: Banks (`B0_bm` = B/M)** | 100.0% / 100.0% | Full (162m) | +0.0654 (+2.42) | +8.30% (+0.90) | — |
| | | Discovery (93m) | −0.0152 (−0.63) | +7.74% (+0.54) | — |
| | | Holdout (69m) | **+0.1739 (+5.15)** | +9.05% (+0.92) | — |
| **S1a: Banks (`B1_bm_roe` = B/M + E/P + ROE)** | 100.0% / 100.0% | Full (162m) | **+0.0774 (+2.46)** | +2.88% (+0.53) | −5.42% (−0.69) |
| | | Discovery (93m) | −0.0028 (−0.08) | −4.25% (−0.68) | −11.98% (−1.08) |
| | | Holdout (69m) | **+0.1855 (+4.56)** | +12.48% (+1.42) | +3.43% (+0.34) |
| **S1a: Banks (`B2_pb_roe_resid` = B/M \| ROE)** | 97.3% / 83.3% | Full (162m) | +0.0606 (+2.07) | +7.94% (+0.91) | −0.35% (−0.09) |
| | | Discovery (93m) | −0.0293 (−1.12) | +3.29% (+0.24) | −4.44% (−0.96) |
| | | Holdout (69m) | **+0.1818 (+5.58)** | **+14.21% (+1.75)** | +5.15% (+0.81) |
| **S1b: All Financials (`F0_bm_sn`)** | 100.0% / 100.0% | Full (162m) | +0.0346 (+2.36) | +3.41% (+0.56) | — |
| | | Discovery (93m) | +0.0275 (+1.50) | +6.01% (+0.65) | — |
| | | Holdout (69m) | +0.0442 (+1.83) | −0.10% (−0.02) | — |
| **S1b: All Financials (`F1_bm_roe_sn`)** | 100.0% / 100.0% | Full (162m) | **+0.0591 (+3.32)** | +7.01% (+1.56) | +3.61% (+0.55) |
| | | Discovery (93m) | +0.0237 (+1.03) | −2.13% (−0.48) | −8.14% (−1.00) |
| | | Holdout (69m) | **+0.1067 (+5.62)** | **+19.34% (+3.03)** | **+19.44% (+2.34)** |
| **S1b: All Financials (`F2_pb_roe_resid`)** | 97.9% / 88.9% | Full (162m) | +0.0385 (+2.54) | +8.67% (+1.32) | +5.26% (+1.39) |
| | | Discovery (93m) | +0.0331 (+1.69) | +5.97% (+0.63) | −0.04% (−0.02) |
| | | Holdout (69m) | +0.0457 (+1.94) | +12.31% (+1.52) | +12.41% (+1.61) |

### S2. Holdings (`Holding`, 52 tickers) and S3. REITs (`Gayrimenkul`, 62 tickers) — Strict `NaN` vs Positive-Backing vs Zero-Fill Sensitivity

To ensure missing or unpopulated balance-sheet items are not conflated with genuine zeros, `H2_backing_nav` and `G1_nav_ffo` are evaluated under three explicit missing-data treatments:
1. **Primary (`strict NaN`, `skipna=False`):** No `.fillna(0.0)` is applied to any balance-sheet or income-statement column, and all 3 legs of the composite must be non-null (`H2_backing_nav` coverage `97.19%`, `G1_nav_ffo` coverage `98.83%`).
2. **Positive-backing filter (`_pos`, `skipna=False`):** Because İş Yatırım's `XI_29` JSON table encodes unpopulated optional lines (`Finansal Yatırımlar`, `Özkaynak Yöntemiyle Değerlenen Yatırımlar`, `Yatırım Amaçlı Gayrimenkuller`) as `0.0`, `H2_backing_nav_pos` requires `fin_investments + eq_investments > 0` (`93.27%` coverage; excludes `5.5%` of Holding rows where subsidiaries are only consolidated), and `G1_nav_ffo_pos` requires `inv_property > 0` (`93.95%` coverage; excludes `4.9%` of REIT rows where properties are held in `Stoklar` or not yet booked as investment property).
3. **Zero-fill sensitivity (`_zerofill`, `skipna=True`):** Missing sub-items filled with `0.0` and remaining legs averaged (`100.0%` coverage).

| Sector & Model | Coverage (Obs / Min Month) | Window | Mean Rank-IC ($t$) | Top 20% − Sector EW %/yr ($t$) | Paired Diff vs `value_sn` %/yr ($t$) |
|---|---:|---|---:|---:|---:|
| **S2: Holdings `H0_value_sn` (`bm+ep+sp+ey`)** | 100.0% / 100.0% | Full (161m) | **+0.0437 (+2.32)** | +3.11% (+0.44) | — |
| | | Discovery (93m) | +0.0529 (+2.55) | +6.98% (+0.66) | — |
| | | Holdout (68m) | +0.0310 (+0.88) | −2.17% (−0.20) | — |
| **S2: Holdings `H1_bm_ep_roe` (no `sp`/`ey`)** | 100.0% / 100.0% | Full (161m) | +0.0361 (+1.89) | +2.11% (+0.30) | −1.00% (−0.20) |
| | | Discovery (93m) | +0.0291 (+1.27) | +3.30% (+0.33) | −3.68% (−0.54) |
| | | Holdout (68m) | **+0.0457 (+1.45)** | +0.48% (+0.04) | +2.65% (+0.37) |
| **S2: Holdings `H2_backing_nav` (strict `NaN`)** | 97.2% / 86.2% | Full (161m) | +0.0128 (+0.84) | +2.55% (+0.39) | −0.57% (−0.10) |
| | | Discovery (93m) | +0.0274 (+1.55) | +8.96% (+0.94) | +1.99% (+0.23) |
| | | Holdout (68m) | −0.0072 (−0.29) | −6.23% (−0.71) | −4.07% (−0.66) |
| **S2: Holdings `H2_backing_nav_pos` (`fin+eq > 0`)** | 93.3% / 79.3% | Full (161m) | +0.0131 (+0.91) | +1.52% (+0.24) | −1.60% (−0.30) |
| | | Discovery (93m) | +0.0263 (+1.58) | +7.40% (+0.84) | +0.43% (+0.05) |
| | | Holdout (68m) | −0.0049 (−0.21) | −6.53% (−0.69) | −4.36% (−0.71) |
| **S2: Holdings `H2_backing_nav_zerofill`** | 100.0% / 100.0% | Full (161m) | +0.0228 (+1.61) | +2.49% (+0.44) | −0.62% (−0.12) |
| | | Discovery (93m) | +0.0447 (+3.31) | +8.87% (+1.13) | +1.89% (+0.26) |
| | | Holdout (68m) | −0.0072 (−0.29) | −6.23% (−0.71) | −4.07% (−0.66) |
| **S3: REITs `G0_value_sn` (`bm+ep+sp+ey`)** | 100.0% / 100.0% | Full (161m) | +0.0399 (+2.47) | **+10.85% (+1.91)** | — |
| | | Discovery (93m) | +0.0232 (+1.08) | +5.76% (+0.67) | — |
| | | Holdout (68m) | +0.0627 (+2.75) | **+17.81% (+3.01)** | — |
| **S3: REITs `G1_nav_ffo` (strict `NaN`)** | 98.8% / 93.1% | Full (161m) | **+0.0518 (+2.79)** | +9.58% (+1.87) | −1.27% (−0.24) |
| | | Discovery (93m) | **+0.0426 (+1.64)** | +3.19% (+0.49) | −2.57% (−0.33) |
| | | Holdout (68m) | **+0.0644 (+2.54)** | **+18.32% (+2.45)** | +0.51% (+0.08) |
| **S3: REITs `G1_nav_ffo_pos` (`inv_property > 0`)** | 94.0% / 86.2% | Full (161m) | +0.0511 (+2.74) | +6.75% (+1.20) | −4.10% (−0.70) |
| | | Discovery (93m) | +0.0430 (+1.60) | +1.56% (+0.24) | −4.20% (−0.53) |
| | | Holdout (68m) | +0.0622 (+2.57) | +13.86% (+1.44) | −3.95% (−0.46) |
| **S3: REITs `G1_nav_ffo_zerofill`** | 100.0% / 100.0% | Full (161m) | +0.0519 (+2.77) | +11.36% (+2.13) | +0.51% (+0.09) |
| | | Discovery (93m) | +0.0411 (+1.61) | +3.38% (+0.53) | −2.38% (−0.30) |
| | | Holdout (68m) | +0.0667 (+2.50) | +22.29% (+2.83) | +4.47% (+0.58) |
| **S3: REITs `G2_letdin_sirmans_resid`** | 98.8% / 93.1% | Full (161m) | +0.0362 (+2.11) | +5.66% (+1.09) | −5.19% (−0.85) |
| | | Discovery (93m) | +0.0202 (+1.01) | +0.77% (+0.14) | −4.99% (−0.58) |
| | | Holdout (68m) | +0.0581 (+2.01) | +12.35% (+1.31) | −5.47% (−0.65) |

- **Interpretation (`S2` & `S3`):**
  1. **Holdings (`S2`):** Across all three missing-data treatments (`strict NaN`, `fin+eq > 0`, and `zerofill`), neither `H1_bm_ep_roe` (−1.00%/yr vs `H0`, $t = -0.20$) nor `H2_backing_nav` (`strict NaN` −0.57%/yr, $t = -0.10$; `pos` −1.60%/yr, $t = -0.30$) beats `value_sn`. Book carrying values of financial/equity-method investments do not substitute for live market values of listed subsidiaries.
  2. **REITs (`S3`):** Requiring complete non-`NaN` legs (`G1_nav_ffo` strict `NaN`, 98.8% coverage) reduces the apparent Holdout top-20% spread from +22.29%/yr (`zerofill`) to **+18.32%/yr ($t = 2.45$)**, which is virtually indistinguishable from `G0_value_sn` (+17.81%/yr, paired diff **+0.51%/yr, $t = 0.08$**, Full diff −1.27%/yr, $t = -0.24$). Further restricting to REITs with `inv_property > 0` (`G1_nav_ffo_pos`, 94.0% coverage) lowers the Holdout spread to +13.86%/yr (−3.95%/yr vs `G0`, $t = -0.46$) because developers carrying properties in `Stoklar` (`EKGYO`, `DAPGM`, etc.) are dropped in those quarters. Neither `H2` nor `G1` clears the replacement hurdle.

### S4. Costed full-market portfolio simulation (`1M TL`, base costs, next-day close)

Both `P1_nonfin_sector_specialized` (`Holding = H1_bm_ep_roe`, `Gayrimenkul = G1_nav_ffo` strict `NaN`) and `P1b_nonfin_backing_nav` (`Holding = H2_backing_nav` strict `NaN`, `Gayrimenkul = G1_nav_ffo` strict `NaN`) are reported alongside `P0` and `P2`:

| Portfolio Variant | Window | Avg Names | Active vs `EW net` %/yr ($t$) | Active vs `BIST 100 TR` %/yr ($t$) | Paired $D$ vs `P0` %/yr ($t$) | USD CAGR % | Max DD USD % | Turnover % |
|---|---|:---:|---:|---:|---:|---:|---:|---:|
| **`P0_nonfin_baseline` (live `R0`)** | Discovery (93m) | 42.7 | +10.58% (+2.68) | +58.83% (+2.31)* | — | +17.57% | −58.1% | 20.3% |
| | Holdout (68m) | 59.2 | +6.89% (+2.55) | **−1.71% (−0.28)** | — | +3.61% | −43.9% | 20.0% |
| **`P1_nonfin_sector_specialized` (`H1`+`G1` strict)** | Discovery (93m) | 42.7 | +8.13% (+2.20) | +52.17% (+2.19)* | −2.45% (−1.56) | +15.17% | −57.2% | 20.4% |
| | Holdout (68m) | 59.1 | +5.85% (+2.38) | −2.75% (−0.47) | −1.04% (−1.31) | +2.83% | −43.4% | 21.1% |
| **`P1b_nonfin_backing_nav` (`H2`+`G1` strict)** | Discovery (93m) | 42.4 | +8.97% (+2.39) | +54.63% (+2.28)* | −1.61% (−1.09) | +15.88% | −58.1% | 19.7% |
| | Holdout (68m) | 59.1 | +5.91% (+2.60) | −2.69% (−0.46) | −0.98% (−0.81) | +2.81% | −42.9% | 21.0% |
| **`P2_all_bist_with_financials` (`P0` + `F1_bm_roe_sn`)** | Discovery (93m) | 47.7 | +8.60% (+2.41) | +58.07% (+2.46)* | −1.98% (−2.13) | +15.57% | −58.1% | 21.2% |
| | Holdout (68m) | 64.7 | **+8.86% (+3.11)** | **+0.26% (+0.04)** | **+1.97% (+1.85)** | **+5.43%** | −44.3% | 20.8% |

*\*Note: `XU100_CFNNTLTL` begins in 2018-07 in the provider feed (30 discovery months).*

### Summary of decisions

1. **Why `P0` lagged BIST 100 Total Return in Holdout is explained structurally, but `P2` is a shadow benchmark rather than a confirmed live upgrade:** Adding the top-20% liquid financials ranked by `F1_bm_roe_sn` (`B/M + E/P + ROE`, ~5.5 financial stocks per month alongside 59.2 non-financials in `P2`) closes the −1.71%/yr Holdout lag against BIST 100 Total Return (`−1.71%/yr` $\to$ `+0.26%/yr`) and lifts Holdout active return vs `EW net` from +6.89%/yr ($t = 2.55$) to +8.86%/yr ($t = 3.11$). However, closing the benchmark gap is distinct from passing the pre-registered superiority test over `P0`: `P2`'s paired Holdout improvement ($D = +1.97\%/\text{yr}, t = 1.85$) is below $t > 2.0$, and its Discovery paired difference ($D = -1.98\%/\text{yr}, t = -2.13$) breaches the pre-registered non-degradation bound ($D > -1.0\%/\text{yr}, t > -1.0$). Therefore `R0-2026-10-12` (`P0`) remains unchanged, and `P2` may only be tracked as a shadow model.
2. **Holdings (`S2`) and REITs (`S3`) remain on `value_sn`:** Both `P1` (`H1`+`G1`, Holdout diff −1.04%/yr, $t = -1.31$) and `P1b` (`H2`+`G1`, Holdout diff −0.98%/yr, $t = -0.81$) trail `P0`, and under strict `NaN` handling `G1_nav_ffo` (+18.32%/yr in Holdout vs +17.81%/yr for `G0`, diff +0.51%/yr, $t = 0.08$) provides no statistically significant advantage over `value_sn`.
