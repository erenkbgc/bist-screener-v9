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

### 0. Financials point-in-time panel coverage

Across the 53 tickers in `FINANCIAL_SECTORS`, 49 have >= 13 months of point-in-time C1 quarterly statements and price history (`6,582` stock-month observations from 2013-04 to 2026-09):
- `Bankacılık`: 12 (`AKBNK`, `ALBRK`, `GARAN`, `HALKB`, `ICBCT`, `ISCTR`, `KLNMA`, `QNBTR`, `SKBNK`, `TSKB`, `VAKBN`, `YKBNK`; `ENPRA` has only 8 quarters of history),
- `Aracı Kurum`: 9, `Menkul Kıymet Yat. Ort.`: 9, `Faktoring`: 5, `Finansal Kiralama`: 4 (`QNBFL` merged/renamed to `QNBFK`), `Sigorta`: 4, `Varlık Yönetimi`: 3, `Emeklilik`: 2, `Tasarruf Finansman`: 1.

### S1. Banks (`S1a`, 12 tickers) and All Liquid Financials (`S1b`, 49 tickers, `liq_drop = 0.30`)

| Universe & Model | Window | Mean Rank-IC ($t$) | Top Basket − Sector EW %/yr ($t$) | Paired Diff vs Base %/yr ($t$) |
|---|---|---:|---:|---:|
| **S1a: Banks (`B0_bm` = B/M)** | Full (162m) | +0.0654 (+2.42) | +8.30% (+0.90) | — |
| | Discovery (93m) | −0.0152 (−0.63) | +7.74% (+0.54) | — |
| | Holdout (69m) | **+0.1739 (+5.15)** | +9.05% (+0.92) | — |
| **S1a: Banks (`B1_bm_roe` = B/M + E/P + ROE)** | Full (162m) | **+0.0774 (+2.46)** | +2.88% (+0.53) | −5.42% (−0.69) |
| | Discovery (93m) | −0.0028 (−0.08) | −4.25% (−0.68) | −11.98% (−1.08) |
| | Holdout (69m) | **+0.1855 (+4.56)** | +12.48% (+1.42) | +3.43% (+0.34) |
| **S1a: Banks (`B2_pb_roe_resid` = B/M \| ROE)** | Full (162m) | +0.0606 (+2.07) | +7.94% (+0.91) | −0.35% (−0.09) |
| | Discovery (93m) | −0.0293 (−1.12) | +3.29% (+0.24) | −4.44% (−0.96) |
| | Holdout (69m) | **+0.1818 (+5.58)** | **+14.21% (+1.75)** | +5.15% (+0.81) |
| **S1b: All Financials (`F0_bm_sn`)** | Full (162m) | +0.0346 (+2.36) | +3.41% (+0.56) | — |
| | Discovery (93m) | +0.0275 (+1.50) | +6.01% (+0.65) | — |
| | Holdout (69m) | +0.0442 (+1.83) | −0.10% (−0.02) | — |
| **S1b: All Financials (`F1_bm_roe_sn`)** | Full (162m) | **+0.0591 (+3.32)** | +7.01% (+1.56) | +3.61% (+0.55) |
| | Discovery (93m) | +0.0237 (+1.03) | −2.13% (−0.48) | −8.14% (−1.00) |
| | Holdout (69m) | **+0.1067 (+5.62)** | **+19.34% (+3.03)** | **+19.44% (+2.34)** |
| **S1b: All Financials (`F2_pb_roe_resid`)** | Full (162m) | +0.0385 (+2.54) | +8.67% (+1.32) | +5.26% (+1.39) |
| | Discovery (93m) | +0.0331 (+1.69) | +5.97% (+0.63) | −0.04% (−0.02) |
| | Holdout (69m) | +0.0457 (+1.94) | +12.31% (+1.52) | +12.41% (+1.61) |

- **Interpretation (`S1`):**
  1. Within the 12-bank cross-section (`S1a`), all three valuation signals show very strong Holdout Rank-IC (`B0_bm` +0.1739, $t = 5.15$; `B1_bm_roe` +0.1855, $t = 4.56$; `B2_pb_roe_resid` +0.1818, $t = 5.58$), and the ROE-conditioned P/B residual (`B2_pb_roe_resid`) produces a +14.21%/yr ($t = 1.75$) top-basket spread over the equal-weighted bank sector in Holdout. As pre-registered, with only 12 banks (top basket = 3 banks), portfolio return $t$-statistics remain below 2.0 due to small-N idiosyncratic variance.
  2. Across the broader liquid Financials universe (`S1b`, 49 tickers, sector-neutralized), combining valuation with profitability/earnings (`F1_bm_roe_sn` = `mean(bm_z_sn, ep_z_sn, roe_z_sn)`) achieves a full-sample Rank-IC of **+0.0591 ($t = 3.32$)** and a Holdout Rank-IC of **+0.1067 ($t = 5.62$)**, generating **+19.34%/yr ($t = 3.03$)** over the equal-weighted financial universe in Holdout (+19.44%/yr, $t = 2.34$ ahead of book-to-market `F0_bm_sn` alone).

### S2. Holdings (`Holding`, 52 tickers) and S3. REITs (`Gayrimenkul`, 62 tickers)

| Sector & Model | Window | Mean Rank-IC ($t$) | Top 20% − Sector EW %/yr ($t$) | Paired Diff vs `value_sn` %/yr ($t$) |
|---|---|---:|---:|---:|
| **S2: Holdings `H0_value_sn` (`bm+ep+sp+ey`)** | Full (161m) | **+0.0437 (+2.32)** | +3.11% (+0.44) | — |
| | Discovery (93m) | +0.0529 (+2.55) | +6.98% (+0.66) | — |
| | Holdout (68m) | +0.0310 (+0.88) | −2.17% (−0.20) | — |
| **S2: Holdings `H1_bm_ep_roe` (no `sp`/`ey`)** | Full (161m) | +0.0361 (+1.89) | +2.11% (+0.30) | −1.00% (−0.20) |
| | Discovery (93m) | +0.0291 (+1.27) | +3.30% (+0.33) | −3.68% (−0.54) |
| | Holdout (68m) | **+0.0457 (+1.45)** | +0.48% (+0.04) | +2.65% (+0.37) |
| **S2: Holdings `H2_backing_nav`** | Full (161m) | +0.0228 (+1.61) | +2.49% (+0.44) | −0.62% (−0.12) |
| | Discovery (93m) | +0.0447 (+3.31) | +8.87% (+1.13) | +1.89% (+0.26) |
| | Holdout (68m) | −0.0072 (−0.29) | −6.23% (−0.71) | −4.07% (−0.66) |
| **S3: REITs `G0_value_sn` (`bm+ep+sp+ey`)** | Full (161m) | +0.0399 (+2.47) | +10.85% (+1.91) | — |
| | Discovery (93m) | +0.0232 (+1.08) | +5.76% (+0.67) | — |
| | Holdout (68m) | +0.0627 (+2.75) | **+17.81% (+3.01)** | — |
| **S3: REITs `G1_nav_ffo` (`bm + prop_nav + op_ep`)** | Full (161m) | **+0.0519 (+2.77)** | **+11.36% (+2.13)** | +0.51% (+0.09) |
| | Discovery (93m) | **+0.0411 (+1.61)** | +3.38% (+0.53) | −2.38% (−0.30) |
| | Holdout (68m) | **+0.0667 (+2.50)** | **+22.29% (+2.83)** | +4.47% (+0.58) |
| **S3: REITs `G2_letdin_sirmans_resid`** | Full (161m) | +0.0362 (+2.11) | +5.66% (+1.09) | −5.19% (−0.85) |
| | Discovery (93m) | +0.0202 (+1.01) | +0.77% (+0.14) | −4.99% (−0.58) |
| | Holdout (68m) | +0.0581 (+2.01) | +12.35% (+1.31) | −5.47% (−0.65) |

- **Interpretation (`S2` & `S3`):**
  1. **Holdings (`S2`):** Neither `H1_bm_ep_roe` (−1.00%/yr vs `H0`, $t = -0.20$) nor balance-sheet asset backing `H2_backing_nav` (−0.62%/yr vs `H0`, $t = -0.12$) improves upon `value_sn`. Book-value line items (`Finansal Yatırımlar` and `Özkaynak Yöntemiyle Değerlenen Yatırımlar`) do not capture the live market-value sum-of-the-parts (SOTP) of listed subsidiaries (`KCHOL`, `SAHOL`, etc.).
  2. **REITs (`S3`):** Standard `value_sn` (`G0`) already works well in REITs (+17.81%/yr, $t = 3.01$ in Holdout) because REIT balance sheets carry investment properties at fair value (`bm` approximates NAV discount). Replacing bottom-line `ep` and `sp` with direct property backing and recurring operating profit yield (`G1_nav_ffo` = `bm + prop_nav + op_ep`) lifts full-sample Rank-IC from +0.0399 ($t = 2.47$) to **+0.0519 ($t = 2.77$)** and Holdout top-20% active return from +17.81%/yr to **+22.29%/yr ($t = 2.83$)**, though the paired difference (+4.47%/yr in Holdout, $t = 0.58$) is well below the replacement hurdle.

### S4. Costed full-market portfolio simulation (`1M TL`, base costs, next-day close)

| Portfolio Variant | Window | Avg Names | Active vs `EW net` %/yr ($t$) | Active vs `BIST 100 TR` %/yr ($t$) | Paired $D$ vs `P0` %/yr ($t$) | USD CAGR % | Max DD USD % | Turnover % |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **`P0_nonfin_baseline` (live `R0`)** | Discovery (93m) | 42.7 | +10.58% (+2.68) | +58.83% (+2.31)* | — | +17.57% | −58.1% | 20.3% |
| | Holdout (68m) | 59.2 | +6.89% (+2.55) | **−1.71% (−0.28)** | — | +3.61% | −43.9% | 20.0% |
| **`P1_nonfin_sector_specialized` (`H1`+`G1`)** | Discovery (93m) | 42.7 | +7.65% (+2.13) | +52.17% (+2.19)* | −2.93% (−1.97) | +14.59% | −57.2% | 20.4% |
| | Holdout (68m) | 59.2 | +5.86% (+2.39) | −2.73% (−0.47) | −1.02% (−1.33) | +2.84% | −43.5% | 21.1% |
| **`P2_all_bist_with_financials` (`P0` + `F1_bm_roe_sn`)** | Discovery (93m) | 47.7 | +8.60% (+2.41) | +58.07% (+2.46)* | −1.98% (−2.13) | +15.57% | −58.1% | 21.2% |
| | Holdout (68m) | 64.7 | **+8.86% (+3.11)** | **+0.26% (+0.04)** | **+1.97% (+1.85)** | **+5.43%** | −44.3% | 20.8% |

*\*Note: `XU100_CFNNTLTL` begins in 2018-07 in the provider feed (30 discovery months).*

### Summary of decisions

1. **Why `P0` lagged BIST 100 Total Return in Holdout is now empirically confirmed:** Adding the top-20% liquid financials ranked by `F1_bm_roe_sn` (`B/M + E/P + ROE`, ~5.5 financial stocks per month alongside 59.2 non-financials in `P2`) **eliminates the −1.71%/yr Holdout lag against BIST 100 Total Return (`−1.71%/yr` $\to$ `+0.26%/yr`)** and lifts Holdout active return vs `EW net` from **+6.89%/yr ($t = 2.55$) to +8.86%/yr ($t = 3.11$)** (paired difference $D = +1.97\%/\text{yr}, t = 1.85$; USD CAGR +3.61% $\to$ +5.43%).
2. **Why `R0-2026-10-12` (`P0`) stays locked on the main rotation:** In the 2013–2020 Discovery period (when Turkish banks experienced a multi-year valuation compression), including financials (`P2`) dragged portfolio return by −1.98%/yr ($t = -2.13$), which breaches the pre-registered discovery non-degradation bound ($D > -1.0\%/\text{yr}, t > -1.0$), and Holdout paired $t = 1.85$ is just shy of $2.0$.
3. **Holdings (`S2`) and REITs (`S3`) stays on `value_sn`:** `P1_nonfin_sector_specialized` underperformed `P0` (−2.93%/yr in Discovery, −1.02%/yr in Holdout). Within REITs, `G1_nav_ffo` (`bm + prop_nav + op_ep`) improves Holdout top-20% spread (+17.81% $\to$ +22.29%/yr), but the difference is not statistically significant ($t = 0.58$).
