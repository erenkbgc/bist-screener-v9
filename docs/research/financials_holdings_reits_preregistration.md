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
