# Candidate: `scholar_sue_usd` — USD-Deflated Standardized Unexpected Earnings Tilt on `value_sn`

**Proposer:** `r3-scholar`  
**Date:** 2026-11-24  
**Free return-fitted parameters:** 0 (fixed 80/20 canonical tilt; no in-sample optimization)  

---

## 1. Literature Grounding

- **Primary Citations:**
  - Atılgan, Y. (2026). *Borsa İstanbul'da Pay Getirilerinin Kesiti*. Sabancı Univ. CEF Research Report. [PDF](https://cef.sabanciuniv.edu/uploads/studies/the-cross-section-of-equity-returns-in-borsa-istanbul.pdf) (Tests 153 JKP anomalies on BIST; **SUE** is the single strongest anomaly surviving multiple-testing adjustment `|t| > 2.78` in both full and ex-microcap universes).
  - Ahlatcıoğlu, A. & Okay, N. (2021). *Post-earnings announcement drift: Evidence from Turkey*. Borsa Istanbul Review, 21(1), 92–103. [DOI](https://doi.org/10.1016/j.bir.2020.09.001) (2.9% 60-day post-announcement CAR spread for SUE in BIST, unexplained by multifactor models).
  - Novy-Marx, R. (2015). *Fundamentally, momentum is fundamental momentum*. Working Paper. [PDF](https://mysimon.rochester.edu/novy-marx/research/FMFM.pdf) (Earnings momentum / SUE subsumes price momentum `t > 7` without momentum crashes).
  - Konchitchki, Y. (2011). *Inflation and Nominal Financial Reporting*. The Accounting Review, 86(3), 1045–1085. [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1349929) & Grecco et al. (2023) [PDF](https://revistas.pucsp.br/redeca/article/download/62532/42676?inline=1) (Nominal financial flows under high inflation distort YoY comparisons unless converted to constant purchasing power / hard currency).

**Economic Mechanism:** Prior trial `H5` (`0.5 * value_sn_z + 0.5 * sue_z`) failed because (i) a 50% weight halved value exposure and spiked turnover, and (ii) nominal TL `sue` in `factors_monthly.parquet` computes `q_ni_t - q_ni_{t-4}` in depreciating nominal TL, conflating currency/inflation drift with genuine operational earnings surprises. Translating each discrete quarter's net income to USD at its quarter-end `usdtry` before computing seasonal YoY surprises strips out inflation/FX drift while preserving PEAD's orthogonality to static value (`corr = +0.070`).

---

## 2. Exact Formula from PIT Panel Columns

**Inputs:** `factors_monthly.parquet` (or `factors_monthly_kapdates.parquet`), `quarterly.parquet`, and `data/research/fx.parquet` (`usdtry`).

1. **USD-Translated Discrete Quarterly Earnings (`q_ni_usd`) in `quarterly.parquet`:**
   - Month-end USD/TRY series: `usdtry_m = fx.set_index("date")["usdtry"].resample("ME").last()`.
   - For each `(ticker, period)` row in `quarterly.parquet`:
     $$\texttt{q\_ni}_{i,p} = \text{coalesce}(\texttt{q\_ni\_parent}_{i,p},\, \texttt{q\_net\_income}_{i,p})$$
     $$\texttt{fx\_q}_{i,p} = \texttt{usdtry\_m}[\text{month\_end}(\texttt{period\_end}_{i,p})]$$
     $$\texttt{q\_ni\_usd}_{i,p} = \frac{\texttt{q\_ni}_{i,p}}{\texttt{fx\_q}_{i,p}}$$
   - *PIT guarantee:* `period_end` always precedes `available_at` (by 30–100+ days), so `fx_q` is strictly known before `available_at`.

2. **Seasonal Random-Walk USD SUE (`sue_ni_usd`):**
   - Self-join `quarterly.parquet` on `(ticker, year - 1, q)` to get `q_ni_usd_ya` and compute YoY change:
     $$\Delta \texttt{q\_ni\_usd}_{i,p} = \texttt{q\_ni\_usd}_{i,p} - \texttt{q\_ni\_usd}_{i,p-4q}$$
   - Sort each ticker by `period_end` and compute trailing 8-quarter rolling standard deviation (minimum 6 non-null YoY changes):
     $$\sigma_{i,p} = \text{rolling}(\text{window}=8, \text{min\_periods}=6).\text{std}(\Delta \texttt{q\_ni\_usd})$$
     $$\texttt{sue\_ni\_usd}_{i,p} = \frac{\Delta \texttt{q\_ni\_usd}_{i,p}}{\sigma_{i,p}}, \qquad \text{if } \sigma_{i,p} > 0 \text{ else } \texttt{NaN}$$

3. **Point-in-Time Merge & Standardization:**
   - Merge `sue_ni_usd` onto the prepared liquid monthly panel on `(ticker, stmt_period == period)`.
   - Within each month `date`, winsorize at 1%/99%, z-score, and sector-neutralize (`min_n = 5`):
     $$\texttt{sue\_ni\_usd\_z\_sn} = \texttt{fb.sector\_neutralize}(\text{df}, \texttt{"sue\_ni\_usd\_z"}, \text{min\_n}=5)$$

4. **Composite Ranking Score:**
   $$\texttt{score}_{i,t} = 0.80 \cdot \texttt{value\_sn\_z}_{i,t} + 0.20 \cdot \text{fillna}(\texttt{sue\_ni\_usd\_z\_sn}_{i,t},\, 0.0)$$
   Select monthly top 20% (`rank(ascending=False, pct=True) <= 0.20`).

---

## 3. Discovery-Only Diagnostics (`2013-04` .. `2020-12`, Holdout Untouched)

- **Coverage in Discovery liquid universe:** `84.5%` (vs `78.0%` for existing `sue` in `factors_monthly.parquet`, due to `q_net_income` fallback when `q_ni_parent` is missing).
- **Standalone Discovery Rank-IC (`fwd_ret_1m`):** `+0.0401` (`NW t = +6.34`); sector-neutral IC = `+0.0362` (`NW t = +5.32`); cross-sectional correlation with `value_sn_z` = `+0.070`.
- **Discovery `pb.simulate` (1M TL real capital, base costs, next-close fills, `2013-04`..`2020-11`, 91m):**
  - Primary `factors_monthly.parquet` (`lag75`): **net `D` = `+1.72%/yr` (`NW t = +1.64`)**; `2013–16` = `+1.76%/yr` (`t = +2.16`), `2017–20` = `+1.68%/yr` (`t = +0.91`); Discovery USD MaxDD = `-56.7%` (identical to R0 `-56.7%`); 1-way turnover = `25.7%` (vs R0 `21.4%`).
  - Sensitivity `factors_monthly_kapdates.parquet`: **net `D` = `+2.00%/yr` (`NW t = +1.57`)**; USD MaxDD = `-56.7%`.
