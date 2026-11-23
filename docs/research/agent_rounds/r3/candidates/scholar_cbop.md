# Candidate: `scholar_cbop` — Cash-Based Operating Profitability Tilt on `value_sn`

**Proposer:** `r3-scholar`  
**Date:** 2026-11-24  
**Free return-fitted parameters:** 0 (fixed 80/20 canonical tilt; no in-sample optimization)  

---

## 1. Literature Grounding

- **Primary Citation:** Ball, R., Gerakos, J., Linnainmaa, J. T., & Nikolaev, V. V. (2016). *Accruals, Cash Flows, and Operating Profitability in the Cross Section of Stock Returns*. Journal of Financial Economics (SSRN 2587199). [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2587199)
- **Supporting Balance-Sheet Bloat / EM Evidence:**
  - Hirshleifer, D., Hou, K., Teoh, S. H., & Zhang, Y. (2004). *Do investors overvalue firms with bloated balance sheets?* J. Accounting & Economics, 38, 297–331. [PDF](https://www.ivey.uwo.ca/media/3775500/do_investors_overvalue_firms_with_bloated_balance_sheets.pdf)
  - Richardson, S. A., Sloan, R. G., Soliman, M. T., & Tuna, İ. (2005). *Accrual reliability, earnings persistence and stock prices*. J. Accounting & Economics, 39(3), 437–485. [DOI](https://doi.org/10.1016/j.jacceco.2005.04.005)
  - Özkan, N. & Kayalı, M. M. (2015). *The accrual anomaly: Evidence from Borsa Istanbul*. Borsa Istanbul Review, 15(2), 115–125. [DOI](https://doi.org/10.1016/j.bir.2015.01.002) (18.58% accrual abnormal return among profitable BIST firms).
  - Azimli, A. (2019). *Pricing the accrual effect in an emerging market*. Economic Research, 32(1), 2180–2194. [DOI](https://doi.org/10.1080/1331677X.2019.1645715) (12.73%/yr accrual premium in BIST among positive-profitability firms).

**Economic Mechanism:** Plain `value_sn` treats accounting earnings (`ep`, `ey`) at face value, leaving portfolios vulnerable to value traps whose operating profits are tied up in non-cash working-capital or operating-asset expansion (`ΔNOA > 0`). Ball et al. (2016) show that subtracting balance-sheet accruals (`ΔNOA`) from operating profit produces cash-based operating profitability (`CbOP`), which strictly outperforms accrual-contaminated profitability and subsumes standalone accruals.

---

## 2. Exact Formula from PIT Panel Columns

**Inputs:** `factors_monthly.parquet` (or `factors_monthly_kapdates.parquet`) and `quarterly.parquet` ONLY (zero external macro/FX series required).

1. **Net Operating Assets (`noa`) in `quarterly.parquet`:**
   For each `(ticker, period)` row in `quarterly.parquet`:
   $$\text{NOA}_{i,p} = (\texttt{total\_assets}_{i,p} - \texttt{cash}_{i,p}) - (\texttt{current\_liab}_{i,p} + \texttt{noncurrent\_liab}_{i,p} - \texttt{fin\_debt}_{i,p})$$
   (Leave `NaN` if any of the five balance-sheet columns is missing.)

2. **4-Quarter Lagged NOA (`noa_ya`):**
   Self-join `quarterly.parquet` on `(ticker, year - 1, q)` (same fiscal quarter one year prior, deduplicated on `(ticker, year, q)`).

3. **Cash-Based Operating Profitability (`cbop`):**
   $$\texttt{cbop}_{i,p} = \frac{\texttt{ttm\_op\_profit}_{i,p} - (\text{NOA}_{i,p} - \text{NOA}_{i,p-4q})}{\texttt{total\_assets}_{i,p}}, \qquad \text{if } \texttt{total\_assets}_{i,p} > 0 \text{ else } \texttt{NaN}$$

4. **Point-in-Time Merge & Standardization:**
   - Merge `cbop` onto the prepared liquid monthly panel (`fb.prepare(raw, FACTORS, liq_drop_pct=0.3)`, restricted to `value_sn_z.notna()`) on `(ticker, stmt_period == period)`. Since `stmt_period` already satisfies `available_at <= date`, `(ticker, year - 1, q)` is strictly point-in-time.
   - Within each month `date`, winsorize at 1%/99% and z-score:
     $$\texttt{cbop\_z} = \texttt{fb.winsorize\_z}(\texttt{cbop}, 0.01, 0.99)$$
   - Sector-neutralize within month using `min_n = 5`:
     $$\texttt{cbop\_z\_sn} = \texttt{fb.sector\_neutralize}(\text{df}, \texttt{"cbop\_z"}, \text{min\_n}=5)$$

5. **Composite Ranking Score:**
   $$\texttt{score}_{i,t} = 0.80 \cdot \texttt{value\_sn\_z}_{i,t} + 0.20 \cdot \text{fillna}(\texttt{cbop\_z\_sn}_{i,t},\, 0.0)$$
   Select monthly top 20% (`rank(ascending=False, pct=True) <= 0.20`).

---

## 3. Discovery-Only Diagnostics (`2013-04` .. `2020-12`, Holdout Untouched)

- **Coverage in Discovery liquid universe:** `98.4%` (`value_sn_z` rows with valid `cbop_z_sn`).
- **Standalone Discovery Rank-IC (`fwd_ret_1m`):** `+0.0304` (`NW t = +4.17`); sector-neutral IC = `+0.0241` (`NW t = +2.75`); cross-sectional correlation with `value_sn_z` = `+0.092`.
- **Discovery `pb.simulate` (1M TL real capital, base costs, next-close fills, `2013-04`..`2020-11`, 91m):**
  - Primary `factors_monthly.parquet` (`lag75`): **net `D` = `+2.53%/yr` (`NW t = +2.44`)**; `2013–16` = `+2.90%/yr` (`t = +1.76`), `2017–20` = `+2.17%/yr` (`t = +1.70`); Discovery USD MaxDD = `-55.7%` (vs R0 `-56.7%`); 1-way turnover = `21.7%` (vs R0 `21.4%`).
  - Sensitivity `factors_monthly_kapdates.parquet`: **net `D` = `+2.13%/yr` (`NW t = +1.99`)**; USD MaxDD = `-54.0%`.
