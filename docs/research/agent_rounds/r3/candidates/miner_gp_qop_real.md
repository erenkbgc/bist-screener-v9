# Candidate: `miner_gp_qop_real` — Gross Profit Yield + Real Operating Profit Surprise Yield Tilt on `value_sn`

**Proposer:** `r3-miner`  
**Date:** 2026-11-24  
**Free return-fitted parameters:** 0 (fixed 70/15/15 canonical 3-pillar tilt; no in-sample optimization)  
**Discovery-only discipline:** Strictly developed and verified on `2013-04` .. `2020-12` (`<= 2020-12-31`); holdout `2021+` untouched.

---

## 1. Economic Rationale & Non-Duplication Audit

- **Mechanism (Two Orthogonal Horizons Complementing `value_sn`):**
  1. **Gross Profit Yield (`gp_mcap = ttm_gross_profit / mcap`, 15% weight):** Equals `Gross Margin × Sales Yield`. Across all 674 `(feature, transform)` series scanned on Discovery 2013–2020, `gp_mcap` produced the **single strongest 12-month orthogonal IC after controlling for `value_sn_z`** (`resid_v IC_12m = +0.0861, NW t = +8.80`; standalone `IC_12m = +0.1287, t = +8.56`). Unlike `S/P` (which rewards low-margin high-volume businesses equally with high-margin businesses) and `E/P` (which is noisy due to FX/interest/tax below the operating line), `GP/Mcap` captures pricing power scaled by equity price, with **lower turnover than R0** (`20.2%` vs `21.4%`).
  2. **Real Operating Profit Surprise Yield (`qop_surp_real_mcap = (q_op_profit_p - q_op_profit_{p-4q} * CPI_p/CPI_{p-4q}) / mcap`, 15% weight):** Captures fast `1m–3m` post-earnings operating drift (PEAD) scaled by market value (price-scaled earnings surprise, Livnat & Mendenhall 2006), using **operating profit** rather than FX/tax-distorted net income and restating prior-year operating profit by `CPI(p) / CPI(p-4q)` so nominal inflation is never mistaken for real operational acceleration. Requires no 8-quarter rolling std window → **98.5% coverage** (vs `78.0%` for `sue`), is automatically seasonally adjusted (same fiscal quarter YoY), and strengthens sharply on actual KAP filing dates (`kapdates IC_1m = +0.0526, t = +6.72`; `IC_3m = +0.0774, t = +8.12`; `IC_6m = +0.0799, t = +5.22`).
  - **Why the pair works together:** The two pillars have **almost zero pairwise correlation (`corr = +0.07`)**! `gp_mcap` anchors slow 12-month quality-value re-rating and dampens turnover, while `qop_surp_real_mcap` injects fast 1m–3m operating momentum that prevents buying structurally deteriorating value traps. Combined turnover rises by only `+1.4 pp` over R0 (`22.8%` vs `21.4%`).
- **Non-duplication vs. 92 prior trials & `r3-scholar`:**
  - `H4a` tested `gpa = gross_profit / total_assets` (asset-scaled profitability, weak `Q5-U = +2.8%/yr`), never `gross_profit / mcap` (price-scaled gross profit yield, `Q5-U = +8.0%/yr, t = +3.66` even after removing `value_sn_z`!).
  - `H5` tested 50/50 nominal bottom-line `sue` (78% coverage, decays to zero by 12m), never CPI-real operating profit surprise yield (`98.5%` coverage, persists through 12m).
  - Completely distinct from `scholar_cbop_real` (`corr = +0.07` for `gp_mcap`, `+0.03` for `qop_surp_real_mcap`) and distinct from `scholar_sue_usd` (`corr = -0.02` for `gp_mcap`, `+0.54` for `qop_surp_real_mcap`).

---

## 2. Exact Formula from PIT Panel Columns

**Inputs:** `fp/factors_monthly.parquet` (or `factors_monthly_kapdates.parquet`), `fp/quarterly.parquet`, `data/research/macro_monthly.parquet` (`cpi_mom`).

1. **Purchasing-Power Index (`cpi_idx`):**
   - From `macro_monthly.parquet`, index by `Period("M")`, compute `cpi_idx = (1.0 + cpi_mom.fillna(0.0) / 100.0).cumprod()`.
   - Map `cpi_q = cpi_idx[Period(period_end, "M")]` onto `quarterly.parquet`. (*PIT guarantee:* `period_end` precedes `available_at` by 30–100+ days.)

2. **Quarterly Numerators in `quarterly.parquet`:**
   - Deduplicate on `(ticker, year, q)` and self-join on `(ticker, year - 1, q)` to obtain `q_op_profit_ya` and `cpi_q_ya`:
     $$\texttt{qop\_surp\_real}_{i,p} = \texttt{q\_op\_profit}_{i,p} - \texttt{q\_op\_profit}_{i,p-4q} \cdot \frac{\texttt{cpi\_q}_{i,p}}{\texttt{cpi\_q}_{i,p-4q}}$$
   - Retain `ttm_gross_profit` and `qop_surp_real`.

3. **PIT Merge & Market-Cap Scaling:**
   - Merge `ttm_gross_profit` and `qop_surp_real` onto the prepared liquid monthly panel (`fb.prepare(raw, FACTORS, liq_drop_pct=0.3)`, restricted to `value_sn_z.notna()`) on `(ticker, stmt_period == period)`.
   - For `mcap > 0`:
     $$\texttt{gp\_mcap}_{i,t} = \frac{\texttt{ttm\_gross\_profit}_{i,p}}{\texttt{mcap}_{i,t}}, \qquad \texttt{qop\_surp\_real\_mcap}_{i,t} = \frac{\texttt{qop\_surp\_real}_{i,p}}{\texttt{mcap}_{i,t}}$$

4. **Cross-Sectional Standardization & Composite:**
   - Within each month `date`, for each leg `x in {gp_mcap, qop_surp_real_mcap}`:
     - `x_z = fb.winsorize_z(x, 0.01, 0.99)`
     - `x_z_sn = fb.sector_neutralize(df, "x_z", min_n=5)`
   - Composite score:
     $$\texttt{score}_{i,t} = 0.70 \cdot \texttt{value\_sn\_z}_{i,t} + 0.15 \cdot \text{fillna}(\texttt{gp\_mcap\_z\_sn}_{i,t},\, 0.0) + 0.15 \cdot \text{fillna}(\texttt{qop\_surp\_real\_mcap\_z\_sn}_{i,t},\, 0.0)$$
   - Select monthly top 20% (`rank(ascending=False, pct=True) <= 0.20`).

---

## 3. Discovery-Only Diagnostics (`2013-04` .. `2020-12`, Holdout Untouched)

- **Coverage:** `98.5%` on `gp_mcap` and `98.5%` on `qop_surp_real_mcap`.
- **Standalone Discovery Rank-IC (`lag75`, zero-leakage truncated `<= 2020-12-31`):**
  - `gp_mcap`: `IC_1m = +0.0424 (t=+4.21)`, `IC_3m = +0.0576 (t=+3.42)`, `IC_6m = +0.0836 (t=+4.01)`, **`IC_12m = +0.1287 (t=+8.56)`**; `resid_v IC_12m = +0.0861 (t=+8.80)`; `7/8` years positive (`2013: -0.003, 2014: +0.083, 2015: +0.038, 2016: +0.055, 2017: +0.061, 2018: +0.036, 2019: +0.048, 2020: +0.007`); `corr vs R0 = +0.51`.
  - `qop_surp_real_mcap`: `IC_1m = +0.0395 (t=+4.81)`, **`IC_3m = +0.0603 (t=+5.91)`**, `IC_6m = +0.0480 (t=+3.14)`, `IC_12m = +0.0402 (t=+2.64)`; **`8/8` years positive** (`2013: +0.034, 2014: +0.060, 2015: +0.049, 2016: +0.036, 2017: +0.061, 2018: +0.005, 2019: +0.051, 2020: +0.017`); `corr vs R0 = +0.09`, `corr vs gp_mcap = +0.07`.
- **Discovery `pb.simulate` (base costs, next-close fills, `2013-04`..`2020-11`, 92m):**
  - **Primary `factors_monthly.parquet` (`lag75`):** paired net **`D = +2.98%/yr` (`NW t = +2.21`)**; `2013–16` = `+2.28%/yr` (`t = +2.11`), `2017–20` = `+3.66%/yr` (`t = +1.53`); **`7/8` years positive**; Discovery USD MaxDD = `-56.0%` (**`+0.7 pp` better** than R0 `-56.7%`); 1-way turnover = `22.8%` (vs R0 `21.4%`); top-20% overlap with R0 = `82.8%`.
  - **Sensitivity `factors_monthly_kapdates.parquet`:** paired net **`D = +2.16%/yr` (`NW t = +1.96`)**; `2013–16` = `+2.67%/yr` (`t = +1.92`), `2017–20` = `+1.68%/yr` (`t = +0.97`); `6/8` years positive; Discovery USD MaxDD = `-55.9%` (**`+0.1 pp` better** than R0 `-56.0%`); 1-way turnover = `22.7%`; overlap with R0 = `82.5%`.
