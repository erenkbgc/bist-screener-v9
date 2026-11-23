# Candidate: `miner_qgp_surp_real` — Real Gross Profit Surprise Yield Tilt on `value_sn`

**Proposer:** `r3-miner`  
**Date:** 2026-11-24  
**Free return-fitted parameters:** 0 (fixed 75/25 canonical tilt; no in-sample optimization)  
**Discovery-only discipline:** Strictly developed and verified on `2013-04` .. `2020-12` (`<= 2020-12-31`); holdout `2021+` untouched.

---

## 1. Economic Rationale & Non-Duplication Audit

- **Mechanism:** Gross profit sits at the very top of the income statement (`Revenue - COGS`), cleanly above SG&A timing shifts, FX debt-revaluation swings, interest-rate shocks, deferred tax adjustments, and one-off non-operating items — all of which heavily pollute Turkish bottom-line net income (`ni_parent`). Measuring the **inflation-adjusted YoY change in latest-quarter gross profit scaled by market capitalization** (`(q_gross_profit_p - q_gross_profit_{p-4q} * CPI_p/CPI_{p-4q}) / mcap`) directly captures **real demand and pricing-power acceleration relative to equity market value**.
  - Economically, this combines Novy-Marx's (2013) insight that gross profit is the cleanest measure of true economic profitability with Jegadeesh & Livnat's (2006) / Livnat & Mendenhall's (2006) price-scaled fundamental surprise (post-announcement underreaction).
  - Restating `q_gross_profit_{p-4q}` to period-`p` purchasing power via `CPI(p) / CPI(p-4q)` guarantees regime consistency under high Turkish inflation (2022–2023) and IAS 29 constant-unit accounting (2024+).
  - Comparing the same fiscal quarter YoY automatically eliminates seasonal revenue/margin effects (tourism, agriculture, energy, retail), while requiring **zero** rolling multi-year variance window → **98.5% coverage** (vs `78.0%` for `sue` and `84.5%` for `scholar_sue_usd`).
- **Non-duplication vs. 92 prior trials & `r3-scholar`:**
  - Never tested in any of the 92 prior trials (`H4a` used static `GP/TA`; `H5` used 8q std-scaled nominal bottom-line `sue`).
  - Virtually **uncorrelated with `value_sn_z` (`corr = +0.07`)**, **zero correlation with `scholar_cbop_real` (`corr = -0.01`)**, and **low-moderate correlation with `scholar_sue_usd` (`corr = +0.42`)** because gross profit surprise captures top-line/margin expansion rather than bottom-line net income volatility.
  - Note: On `lag75` discovery, standalone `m_qgp_surp_mcap` produced the single highest long-side quintile spread across all 674 mined signals (`Q5 - Univ = +14.90%/yr, NW t = +5.30`; `resid_v Q5 - Univ = +14.03%/yr, t = +4.62`).

---

## 2. Exact Formula from PIT Panel Columns

**Inputs:** `fp/factors_monthly.parquet` (or `factors_monthly_kapdates.parquet`), `fp/quarterly.parquet`, `data/research/macro_monthly.parquet` (`cpi_mom`).

1. **Purchasing-Power Index (`cpi_idx`):**
   - From `macro_monthly.parquet`, index by `Period("M")`, compute `cpi_idx = (1.0 + cpi_mom.fillna(0.0) / 100.0).cumprod()`.
   - Map `cpi_q = cpi_idx[Period(period_end, "M")]` onto `quarterly.parquet`. (*PIT guarantee:* `period_end` precedes `available_at` by 30–100+ days.)

2. **Real Quarterly Gross Profit Surprise (`qgp_surp_real`) in `quarterly.parquet`:**
   - Deduplicate `quarterly.parquet` on `(ticker, year, q)` and self-join on `(ticker, year - 1, q)` to obtain `q_gross_profit_ya` and `cpi_q_ya`:
     $$\texttt{qgp\_surp\_real}_{i,p} = \texttt{q\_gross\_profit}_{i,p} - \texttt{q\_gross\_profit}_{i,p-4q} \cdot \frac{\texttt{cpi\_q}_{i,p}}{\texttt{cpi\_q}_{i,p-4q}}$$

3. **PIT Merge & Market-Cap Scaling:**
   - Merge `qgp_surp_real` onto the prepared liquid monthly panel (`fb.prepare(raw, FACTORS, liq_drop_pct=0.3)`, restricted to `value_sn_z.notna()`) on `(ticker, stmt_period == period)`.
   - For `mcap > 0`:
     $$\texttt{qgp\_surp\_real\_mcap}_{i,t} = \frac{\texttt{qgp\_surp\_real}_{i,p}}{\texttt{mcap}_{i,t}}$$

4. **Cross-Sectional Standardization & Composite:**
   - Within each month `date`, winsorize at 1%/99% and z-score: `qgp_surp_real_z = fb.winsorize_z(qgp_surp_real_mcap, 0.01, 0.99)`.
   - Sector-neutralize within month (`min_n = 5`): `qgp_surp_real_z_sn = fb.sector_neutralize(df, "qgp_surp_real_z", min_n=5)`.
   - Composite score:
     $$\texttt{score}_{i,t} = 0.75 \cdot \texttt{value\_sn\_z}_{i,t} + 0.25 \cdot \text{fillna}(\texttt{qgp\_surp\_real\_z\_sn}_{i,t},\, 0.0)$$
   - Select monthly top 20% (`rank(ascending=False, pct=True) <= 0.20`).

---

## 3. Discovery-Only Diagnostics (`2013-04` .. `2020-12`, Holdout Untouched)

- **Coverage:** `98.5%` of R0 liquid stock-months.
- **Cross-sectional Spearman correlation:** `corr vs value_sn_z = +0.07`; `corr vs scholar_cbop_real = -0.01`; `corr vs scholar_sue_usd = +0.42`.
- **Standalone Discovery Rank-IC (`lag75`, zero-leakage truncated `<= 2020-12-31`):**
  - `1m`: **`+0.0363`** (`NW t = +4.15`; `kapdates`: **`+0.0542, t = +5.91`**)
  - `3m`: **`+0.0459`** (`NW t = +3.70`; `kapdates`: **`+0.0692, t = +5.00`**)
  - `6m`: **`+0.0316`** (`NW t = +1.99`; `kapdates`: **`+0.0586, t = +3.21`**)
  - `12m`: **`+0.0233`** (`NW t = +1.69`; `kapdates`: `+0.0376, t = +2.69`)
  - **Yearly sign stability (`2013`–`2020`):** **`8/8` years positive** (`2013: +0.019, 2014: +0.056, 2015: +0.038, 2016: +0.039, 2017: +0.075, 2018: +0.015, 2019: +0.038, 2020: +0.003`).
- **Discovery `pb.simulate` (base costs, next-close fills, `2013-04`..`2020-11`, 92m):**
  - **Primary `factors_monthly.parquet` (`lag75`):** paired net **`D = +2.08%/yr` (`NW t = +1.60`)**; `2013–16` = `+2.30%/yr` (`t = +1.44`), `2017–20` = `+1.87%/yr` (`t = +0.96`); `5/8` years positive; Discovery USD MaxDD = `-56.2%` (**`+0.5 pp` better** than R0 `-56.7%`); 1-way turnover = `24.7%` (vs R0 `21.4%`); top-20% overlap with R0 = `77.3%`.
  - **Sensitivity `factors_monthly_kapdates.parquet`:** paired net **`D = +1.99%/yr` (`NW t = +1.65`)**; `2013–16` = `+3.33%/yr` (`t = +2.38`), `2017–20` = `+0.70%/yr` (`t = +0.37`); **`7/8` years positive**; Discovery USD MaxDD = `-56.2%` (`-0.2 pp` vs R0 `-56.0%`); 1-way turnover = `24.6%`; overlap with R0 = `76.8%`.
  - *(Reference note on zero-external-data nominal variant `(q_gp_p - q_gp_{p-4q}) / mcap`: discovery `D_lag75 = +1.73%/yr, t = +1.42, 7/8 yrs` and `D_kap = +3.36%/yr, t = +2.51, 7/8 yrs`; CPI-real is proposed here for structural inflation/IAS 29 consistency.)*
