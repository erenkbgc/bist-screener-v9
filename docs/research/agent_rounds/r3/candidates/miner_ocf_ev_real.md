# Candidate: `miner_ocf_ev_real` — Real Enterprise Cash-Based Operating Yield Tilt on `value_sn`

**Proposer:** `r3-miner`  
**Date:** 2026-11-24  
**Free return-fitted parameters:** 0 (fixed 80/20 canonical tilt; no in-sample optimization)  
**Discovery-only discipline:** Strictly developed and verified on `2013-04` .. `2020-12` (`<= 2020-12-31`); holdout `2021+` untouched.

---

## 1. Economic Rationale & Non-Duplication Audit

- **Mechanism:** Standard `value_sn` includes `ey = ttm_op_profit / EV`, which treats accrual-backed operating profit identically to cash-backed operating profit. In emerging markets with working-capital financing pressure and high inflation, firms that report rising accounting operating profit while simultaneously expanding Net Operating Assets (`ΔNOA > 0`, e.g., uncollected receivables, bloated inventory, capitalized operating assets) frequently turn into value traps. Subtracting inflation-consistent balance-sheet accruals (`NOA_p - NOA_{p-4q} * CPI_p / CPI_{p-4q}`) from `ttm_op_profit` and scaling by Enterprise Value (`EV = mcap + fin_debt - cash`) produces **Real Enterprise Cash-Based Operating Yield** — a direct cash-flow valuation yield that penalizes accrual bloat while rewarding true cash-generating cheap firms.
- **Why CPI-restated `NOA_{p-4q}`:** In `fp/quarterly.parquet`, `ttm_op_profit` (C1 constant unit) and `NOA_p` are in period-`p` purchasing power, while `NOA_{p-4q}` is in period-`(p-4q)` purchasing power. Restating `NOA_{p-4q}` by `CPI(p) / CPI(p-4q)` prevents nominal price-level inflation on working capital from being misclassified as real accrual expansion, ensuring regime consistency across low inflation, 2022–2023 high inflation, and IAS 29.
- **Non-duplication vs. 92 prior trials:** Cash-based operating cash flow / NOA accruals were never tested in the 92 prior trials (`long_term_preregistration.md` dropped CFO/accruals because the panel lacks a cash-flow statement; here we reconstruct operating cash flow strictly from balance-sheet `NOA` + `ttm_op_profit`). Not an EV definition tweak (`E1` only added ST investments & minority interest to `EBIT/EV`).
- **Relation to `r3-scholar` candidates (full transparency):** Shares the Ball et al. (2016) `ttm_op_profit - Δ_real NOA` numerator with `scholar_cbop_real` (rank correlation `+0.91` on discovery), but scales by **Enterprise Value (`EV`)** rather than `total_assets` — transforming a profitability ratio into a **valuation cash yield**. On discovery, EV-yield scaling lifts standalone 1m IC (`+0.0388, t = +4.94`), 12m IC (`+0.0891, t = +6.70`), and `lag75` `pb.simulate` paired `D` (`+3.49%/yr, t = +2.38` vs `+2.53%/yr, t = +2.44` for `scholar_cbop`). Manager/Skeptic may treat this as a direct valuation-yield contender alongside or in lieu of `scholar_cbop` to conserve `N_sel`.

---

## 2. Exact Formula from PIT Panel Columns

**Inputs:** `fp/factors_monthly.parquet` (or `factors_monthly_kapdates.parquet`), `fp/quarterly.parquet`, `data/research/macro_monthly.parquet` (`cpi_mom`).

1. **Purchasing-Power Index (`cpi_idx`):**
   - From `macro_monthly.parquet`, index by `Period("M")`, compute `cpi_idx = (1.0 + cpi_mom.fillna(0.0) / 100.0).cumprod()`.
   - Map `cpi_q = cpi_idx[Period(period_end, "M")]` onto `quarterly.parquet`.
   - *PIT guarantee:* `period_end` precedes `available_at` by 30–100+ days; TÜİK CPI for `period_end` is released on business day 3 of the following month, strictly before `available_at`.

2. **Net Operating Assets (`noa`) & Real Operating Cash Flow Numerator (`ocf_real_num`) in `quarterly.parquet`:**
   $$\text{NOA}_{i,p} = (\texttt{total\_assets}_{i,p} - \texttt{cash}_{i,p}) - (\texttt{current\_liab}_{i,p} + \texttt{noncurrent\_liab}_{i,p} - \texttt{fin\_debt}_{i,p})$$
   (Leave `NaN` if any of the 5 inputs is missing.)  
   Self-join `quarterly.parquet` (deduplicated on `(ticker, year, q)`) on `(ticker, year - 1, q)` to obtain `noa_ya` and `cpi_q_ya`:
   $$\text{NOA}^{\text{real}}_{i,p-4q} = \text{NOA}_{i,p-4q} \cdot \frac{\texttt{cpi\_q}_{i,p}}{\texttt{cpi\_q}_{i,p-4q}}$$
   $$\texttt{ocf\_real\_num}_{i,p} = \texttt{ttm\_op\_profit}_{i,p} - \left(\text{NOA}_{i,p} - \text{NOA}^{\text{real}}_{i,p-4q}\right)$$
   Also retain `net_debt = fin_debt - cash` (NaN if either is missing, matching `core/pit_panel.py::value_ratios`).

3. **Enterprise Value Scaling & PIT Merge:**
   - Merge `ocf_real_num` and `net_debt` onto the prepared liquid monthly panel (`fb.prepare(raw, FACTORS, liq_drop_pct=0.3)`, restricted to `value_sn_z.notna()`) on `(ticker, stmt_period == period)`.
   - Compute Enterprise Value identically to `pit_panel.value_ratios`:
     $$\text{EV}_{i,t} = \texttt{mcap}_{i,t} + \texttt{net\_debt}_{i,p}, \qquad \texttt{ocf\_ev\_real}_{i,t} = \frac{\texttt{ocf\_real\_num}_{i,p}}{\text{EV}_{i,t}} \quad \text{if } \text{EV}_{i,t} > 0 \text{ else } \texttt{NaN}$$

4. **Cross-Sectional Standardization & Composite:**
   - Within each month `date`, winsorize at 1%/99% and z-score: `ocf_ev_real_z = fb.winsorize_z(ocf_ev_real, 0.01, 0.99)`.
   - Sector-neutralize within month (`min_n = 5`): `ocf_ev_real_z_sn = fb.sector_neutralize(df, "ocf_ev_real_z", min_n=5)`.
   - Composite score:
     $$\texttt{score}_{i,t} = 0.80 \cdot \texttt{value\_sn\_z}_{i,t} + 0.20 \cdot \text{fillna}(\texttt{ocf\_ev\_real\_z\_sn}_{i,t},\, 0.0)$$
   - Select monthly top 20% (`rank(ascending=False, pct=True) <= 0.20`).

---

## 3. Discovery-Only Diagnostics (`2013-04` .. `2020-12`, Holdout Untouched)

- **Coverage:** `97.5%` of R0 liquid stock-months.
- **Cross-sectional Spearman correlation with `value_sn_z`:** `+0.19` (low; `corr vs scholar_sue_usd = +0.03`).
- **Standalone Discovery Rank-IC (`lag75`, zero-leakage truncated `<= 2020-12-31`):**
  - `1m`: **`+0.0388`** (`NW t = +4.94`)
  - `3m`: **`+0.0537`** (`NW t = +5.31`)
  - `6m`: **`+0.0709`** (`NW t = +4.66`)
  - `12m`: **`+0.0891`** (`NW t = +6.70`) — zero decay; IC grows monotonically across all horizons!
  - **Yearly sign stability (`2013`–`2020`):** **`8/8` years positive** (`2013: +0.037, 2014: +0.042, 2015: +0.012, 2016: +0.064, 2017: +0.040, 2018: +0.035, 2019: +0.035, 2020: +0.045`).
  - **Pure orthogonal `resid_v` (nominal `m_ocf_proxy_ev`):** `IC_1m = +0.0240 (t = +3.05)`, `IC_3m = +0.0340 (t = +3.23)`, `IC_12m = +0.0434 (t = +3.38)`, `8/8` years positive.
- **Discovery `pb.simulate` (base costs, next-close fills, `2013-04`..`2020-11`, 92m):**
  - **Primary `factors_monthly.parquet` (`lag75`):** paired net **`D = +3.49%/yr` (`NW t = +2.38`)**; `2013–16` = `+4.57%/yr` (`t = +2.32`), `2017–20` = `+2.45%/yr` (`t = +1.20`); `6/8` years positive; Discovery USD MaxDD = `-56.5%` (**`+0.2 pp` better** than R0 `-56.7%`); 1-way turnover = `22.1%` (vs R0 `21.4%`); top-20% overlap with R0 = `82.9%`.
  - **Sensitivity `factors_monthly_kapdates.parquet`:** paired net **`D = +2.31%/yr` (`NW t = +1.68`)**; `2013–16` = `+3.98%/yr` (`t = +2.72`), `2017–20` = `+0.72%/yr` (`t = +0.34`); `6/8` years positive; Discovery USD MaxDD = `-55.0%` (**`+1.0 pp` better** than R0 `-56.0%`); 1-way turnover = `21.3%`.
