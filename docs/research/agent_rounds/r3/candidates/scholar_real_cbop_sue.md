# Candidate: `scholar_real_cbop_sue` — Inflation-Consistent Cash Profitability + USD SUE Tilt on `value_sn`

**Proposer:** `r3-scholar`  
**Date:** 2026-11-24  
**Free return-fitted parameters:** 0 (fixed 75/15/10 canonical 3-pillar composite; no in-sample optimization)  

---

## 1. Literature Grounding

Synthesizes the three empirical mechanisms shown to survive in emerging markets, high-inflation accounting regimes, and Borsa Istanbul specifically:
1. **Value Anchor (`value_sn`):** Gökçen (2026, *Borsa Istanbul Review*, [DOI](https://doi.org/10.1016/j.bir.2026.100884)) — value is the strongest standalone BIST factor.
2. **Inflation-Consistent Cash-Based Operating Profitability (`cbop_real`):** Ball, Gerakos, Linnainmaa & Nikolaev (2016, *JFE*, [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2587199)) + Grecco et al. (2023, *REDECA*, [PDF](https://revistas.pucsp.br/redeca/article/download/62532/42676?inline=1)) + Archambault & Archambault (2009, *JIAAT*, [DOI](https://www.sciencedirect.com/science/article/abs/pii/S0020706309000740)).
   - *Why CPI-restating `NOA_{P-4}` matters for IAS 29 and high inflation:* In `quarterly.parquet`, `ttm_op_profit` (C1 constant purchasing power) and `total_assets` at period $P$ are measured in **period-$P$-end purchasing power**, whereas `NOA_{P-4}` is measured in **period-$(P-4)$-end purchasing power**. Under 50%+ inflation (or IAS 29 with vendor re-expression undone), taking a nominal difference `NOA_P - NOA_{P-4}` mistakes general price-level inflation on existing working capital for real accrual bloat. Multiplying `NOA_{P-4}` by `CPI(P) / CPI(P-4)` puts both balance sheets in the exact same purchasing-power unit as `ttm_op_profit` and `total_assets`.
3. **USD-Deflated Earnings Momentum (`sue_ni_usd`):** Atılgan (2026, *Sabancı CEF*, [PDF](https://cef.sabanciuniv.edu/uploads/studies/the-cross-section-of-equity-returns-in-borsa-istanbul.pdf)) + Ahlatcıoğlu & Okay (2021, *BIR*, [DOI](https://doi.org/10.1016/j.bir.2020.09.001)) + Novy-Marx (2015, [PDF](https://mysimon.rochester.edu/novy-marx/research/FMFM.pdf)). Adds a low-turnover fundamental momentum leg (`corr = +0.070` with `value_sn_z`) that captures underreaction to real earnings surprises without price-momentum crash risk.

---

## 2. Exact Formula from PIT Panel Columns

**Inputs:** `factors_monthly.parquet` (or `factors_monthly_kapdates.parquet`), `quarterly.parquet`, `data/research/macro_monthly.parquet` (`cpi_mom`), and `data/research/fx.parquet` (`usdtry`).

1. **Purchasing-Power Index (`cpi_idx`) & Quarter-End FX (`usdtry_m`):**
   - `cpi_idx`: cumulative product of `(1 + cpi_mom.fillna(0) / 100)` indexed by `Period("M")`.
   - `usdtry_m`: month-end `usdtry` from `fx.parquet`.
   - Map `cpi_q = cpi_idx[Period(period_end, "M")]` and `fx_q = usdtry_m[month_end(period_end)]` onto `quarterly.parquet`.
   - *PIT guarantee:* For any statement period $P$, `available_at >= period_end + ~30..100 days`, whereas TÜİK CPI for `period_end` is published on the 3rd business day of the next month and `usdtry` is observed on `period_end` itself. Both `cpi_q` and `fx_q` are strictly known before `available_at`.

2. **Real Cash-Based Operating Profitability (`cbop_real`):**
   $$\text{NOA}_{i,p} = (\texttt{total\_assets}_{i,p} - \texttt{cash}_{i,p}) - (\texttt{current\_liab}_{i,p} + \texttt{noncurrent\_liab}_{i,p} - \texttt{fin\_debt}_{i,p})$$
   Self-join `quarterly.parquet` on `(ticker, year - 1, q)` to get `noa_ya`, `cpi_q_ya`, `q_ni_usd_ya`:
   $$\text{NOA}^{\text{real}}_{i,p-4q} = \text{NOA}_{i,p-4q} \cdot \frac{\texttt{cpi\_q}_{i,p}}{\texttt{cpi\_q}_{i,p-4q}}$$
   $$\texttt{cbop\_real}_{i,p} = \frac{\texttt{ttm\_op\_profit}_{i,p} - (\text{NOA}_{i,p} - \text{NOA}^{\text{real}}_{i,p-4q})}{\texttt{total\_assets}_{i,p}}, \qquad \text{if } \texttt{total\_assets}_{i,p} > 0 \text{ else } \texttt{NaN}$$

3. **USD-Deflated SUE (`sue_ni_usd`):**
   $$\texttt{q\_ni\_usd}_{i,p} = \frac{\text{coalesce}(\texttt{q\_ni\_parent}_{i,p},\, \texttt{q\_net\_income}_{i,p})}{\texttt{fx\_q}_{i,p}}, \qquad \Delta\texttt{q\_ni\_usd}_{i,p} = \texttt{q\_ni\_usd}_{i,p} - \texttt{q\_ni\_usd}_{i,p-4q}$$
   $$\texttt{sue\_ni\_usd}_{i,p} = \frac{\Delta\texttt{q\_ni\_usd}_{i,p}}{\text{rolling}(8, \text{min\_periods}=6).\text{std}(\Delta\texttt{q\_ni\_usd})}$$

4. **Point-in-Time Merge, Standardization & Composite:**
   - Merge `cbop_real` and `sue_ni_usd` onto the prepared liquid monthly panel on `(ticker, stmt_period == period)`.
   - Within each month `date`, winsorize at 1%/99%, z-score, and sector-neutralize (`min_n = 5`) both legs to obtain `cbop_real_z_sn` and `sue_ni_usd_z_sn`.
   - Composite score:
     $$\texttt{score}_{i,t} = 0.75 \cdot \texttt{value\_sn\_z}_{i,t} + 0.15 \cdot \text{fillna}(\texttt{cbop\_real\_z\_sn}_{i,t},\, 0.0) + 0.10 \cdot \text{fillna}(\texttt{sue\_ni\_usd\_z\_sn}_{i,t},\, 0.0)$$
   - Select monthly top 20% (`rank(ascending=False, pct=True) <= 0.20`).

---

## 3. Discovery-Only Diagnostics (`2013-04` .. `2020-12`, Holdout Untouched)

- **Coverage in Discovery liquid universe:** `cbop_real_z_sn` = `98.4%`, `sue_ni_usd_z_sn` = `84.5%`.
- **Discovery `pb.simulate` (1M TL real capital, base costs, next-close fills, `2013-04`..`2020-11`, 91m):**
  - Primary `factors_monthly.parquet` (`lag75`): **net `D` = `+3.80%/yr` (`NW t = +4.38`)**; `2013–16` = `+4.17%/yr` (`t = +3.22`), `2017–20` = `+3.43%/yr` (`t = +3.01`); Discovery USD MaxDD = `-55.8%` (vs R0 `-56.7%`); 1-way turnover = `23.1%` (vs R0 `21.4%`).
  - Sensitivity `factors_monthly_kapdates.parquet`: **net `D` = `+3.32%/yr` (`NW t = +2.93`)**; USD MaxDD = `-54.1%`.
