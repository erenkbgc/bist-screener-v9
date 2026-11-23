# Quality × Value Interaction and Low-Volatility Risk Filter: Pre-Registration

Written and committed on 2026-10-17 **before** running `scripts/research_quality_value_lowvol.py`. The conditional sort definitions, missing-data (`strict NaN`) rules, costed portfolio rules, risk metrics, and decision rules separating **alpha enhancement** from **risk control** are fixed below and are not modified after seeing results.

---

## 1. Motivation & Prior Evidence

1. **Why unconditional additive composites failed (`long_term_preregistration.md`, `bist_factor_reconciliation_preregistration.md`):**
   - Adding `gpa_z` (`H4a`) or `sue_z` (`H5`) at 50/50 weight to `value_sn_z` across the entire universe degraded `value_sn` top-quintile performance (`-3.19%/yr` and `-2.52%/yr` in Holdout) because `value_sn` already contains two earnings-flow yields (`ep` and `ey`), so unconditional profitability weighting double-counts earnings and dilutes deep book-to-market discounts.
   - Adding `low_vol_z` as a positive additive bonus also failed because the lowest-volatility quintile (`Q5` of `vol60_z`) does not generate standalone alpha (`Q5 − Univ` `-0.98%/yr`, $t = -0.27$ in Holdout); instead, the low-volatility effect in BIST is driven by **left-tail crash avoidance** (`Q1`, the most volatile 20%, trails the liquid universe by `-6.89%/yr`, $t = -2.26$ full sample and `-8.64%/yr`, $t = -2.51$ in Holdout).
2. **Untested P2 hypotheses:**
   - **Question A (Quality × Value Conditional Interaction):** Within cheap stocks (`value_sn` top quintile `V_Q5` and top 30%), do stocks with sustainable profitability (`ROE`, `ROA`, operating profitability `OP/A`, `GP/A`) and stronger balance sheets (`F7`) outperform unprofitable / weak-balance-sheet cheap stocks? Does `ROE` outperform `GP/A` or `OP/A` as a conditional filter inside the cheap value sleeve?
   - **Question B (Low-Volatility as a Risk Filter vs Alpha Generator):** When we remove extreme-volatility stocks (`vol60_z` bottom quintile) from the cheap `value_sn` pool and evaluate under the full costed portfolio simulator (`core/portfolio_backtest.py::simulate`, next-day close fill, base costs, cash at TCMB policy rate, benchmarked against costed `EW net`), does it increase net active return (**alpha enhancement**) or does it primarily compress volatility, drawdown, and value-trap incidence at comparable return (**risk control**)?

---

## 2. Data, Universe, Missing-Data Policy, and Windows

- **Panel:** C1 point-in-time non-financial monthly factor panel (`data/research/factors_monthly.parquet`, extended with `quarterly_ext.parquet` statement features via `research_long_term.load()`, 162 months, 2013-04 to 2026-09).
- **Universe:** Liquid non-financial stocks (`liq_drop_pct = 0.30` by 60-day median TL volume, minimum 30 stocks per month).
- **Strict `NaN` Policy:** Missing accounting items (`roe`, `roa`, `opa`, `gpa`, `f7`) or volatility (`vol60`) are **never** filled with `0.0`. Every factor and composite reports its overall and monthly coverage rate (`obs_pct`, `monthly_mean_pct`, `monthly_min_pct`). Multi-leg quality composites require all constituent legs to be non-`NaN` (`skipna=False`), with a `skipna=True` sensitivity column reported separately.
- **Windows:**
  - **Full sample:** 2013-04 to 2026-09 (162 months)
  - **Discovery:** 2013-04 to 2020-12 (93 months)
  - **Holdout:** 2021-01 to 2026-09 (69 months)

---

## 3. Family A — Conditional Double-Sorts Within Value Quintiles

Each month $t$, stocks are first sorted into 5 `value_sn_z` quintiles (`V_Q1` most expensive to `V_Q5` cheapest top-20%). Within the cheapest value quintile `V_Q5` (and also reported across `V_Q4 + V_Q5`, the cheapest 40%), stocks are conditionally split into 3 terciles (`Low` bottom 30%, `Mid` middle 40%, `High` top 30%) on each quality or risk metric:

| Metric ID | Definition | Economic Role |
|---|---|---|
| `Q_roe` | Sector-neutralized `roe_sn_z` (`TTM parent net income / book equity`) | Return on equity (2025 BIST profitability hypothesis) |
| `Q_roa` | Sector-neutralized `roa_sn_z` (`TTM parent net income / total assets`) | Asset profitability |
| `Q_opa` | Sector-neutralized `opa_sn_z` (`TTM EBIT / total assets`) | Operating profitability |
| `Q_gpa` | Sector-neutralized `gpa_sn_z` (`gross profit / total assets`) | Novy-Marx gross profitability |
| `Q_f7` | Piotroski 7-point accounting & balance-sheet score (`F7`, 0..7) | Leverage, liquidity, margin & profitability change |
| `Q_qual` | Strict equal-weighted composite `qual_sn_z = mean(roe_sn_z, roa_sn_z, f7_z)` (`skipna=False`) | Combined profitability + balance-sheet quality |
| `R_lowvol` | `vol60_z` (negated 60-day realized volatility; `High` = lowest vol, `Low` = highest vol) | Realized return volatility |

For each metric inside `V_Q5`, we report:
1. `High − Low` equal-weighted 1-month forward return spread (%/yr, Newey-West $t$ with 6 lags).
2. `High − All V_Q5` spread (%/yr, Newey-West $t$).
3. `Non-Low (Mid + High) − All V_Q5` spread (effect of dropping only the worst 30% tail inside `V_Q5`).
4. **Value-trap rate (`trap_6m_pct`):** Share of picks with 6-month market-excess return `< -30%` in `Low` vs `High` inside `V_Q5`.

---

## 4. Family B — Costed Portfolio Variants (`core/portfolio_backtest.py::simulate`)

All portfolio variants are simulated with `1,000,000 TL` reference capital, next-trading-day close fill, base transaction costs (commission + half-spread + market impact), cash earning the monthly TCMB policy rate (`data/research/macro_monthly.parquet`), and benchmarked against the identically costed equal-weighted universe (`EW net`):

| Variant ID | Selection Rule at Month $t$ | Target Breadth |
|---|---|---|
| **`P0_value_top20`** | Baseline: top 20% of `value_sn_z` | 20% of liquid universe |
| **`QV1_roe_filter`** | Top 20% of `value_sn_z`, excluding stocks in the bottom 20% of `roe_sn_z` (or missing `roe_sn_z`) | ~16%–18% of universe |
| **`QV2_f7_filter`** | Top 20% of `value_sn_z`, excluding weak balance-sheet / accounting stocks (`F7 <= 3` or missing `F7`) | ~14%–17% of universe |
| **`QV3_qual_in_top30`** | Two-stage breadth-preserving sort: take top 30% of `value_sn_z`, keep top 2/3 by strict `qual_sn_z` | 20% of liquid universe |
| **`LV1_lowvol_filter`** | Top 20% of `value_sn_z`, excluding the highest-volatility quintile of the universe (`vol60_z` bottom 20%) | ~16% of universe |
| **`LV2_lowvol_in_top25`** | Two-stage breadth-preserving sort: take top 25% of `value_sn_z`, drop the most volatile 20% within that cheap pool | 20% of liquid universe |
| **`QLV_combined_filter`** | Top 20% of `value_sn_z`, excluding extreme volatility (`vol60_z` bottom 20%) OR joint profitability/balance-sheet distress (`roe_sn_z` bottom 20% AND `F7 <= 3`) | ~15% of universe |

### Metrics Reported for Every Costed Portfolio Variant
- Net annualized return, active return vs `EW net` (%/yr, Newey-West $t$ with 6 lags), active return vs BIST 100 Total Return (`XU100_CFNNTLTL`), and USD real CAGR.
- Paired monthly net return difference $D_t = r_{\text{net}}(P_k) - r_{\text{net}}(P_0)$ in Full, Discovery, and Holdout (%/yr, Newey-West $t$).
- **Risk & Execution Profile:** Annualized portfolio volatility ($\sigma_{\text{port}}$), annualized active volatility ($\sigma_{\text{active}}$), Sharpe ratio (excess over daily policy rate), maximum drawdown in USD ($\text{MDD}_{\text{USD}}$), active maximum drawdown vs `EW net` ($\text{MDD}_{\text{active}}$), monthly one-way turnover, annualized cost drag (%/yr), and 6-month value-trap rate (`fwd_ret_6m_xs < -30%`).

---

## 5. Pre-Registered Decision Rules: Alpha Enhancement vs Risk Control

To prevent relabeling drawdown reduction as alpha after seeing the numbers, every variant $P_k$ is classified into exactly one of three pre-registered outcomes:

1. **`ALPHA_ENHANCEMENT` (Eligible to replace `P0` in live scoring):**
   - Discovery paired net return difference $D_{\text{disc}} > 0$ with $t_{\text{disc}} \ge 2.0$, **AND**
   - Holdout paired net return difference $D_{\text{hold}} \ge +1.5\%/\text{yr}$ with $t_{\text{hold}} \ge 1.96$, **AND**
   - Holdout USD CAGR $\ge P_0$ USD CAGR.
2. **`RISK_CONTROL_ONLY` (Reported as a risk-management overlay / warning flag; does NOT replace `P0` as an alpha signal):**
   - Fails `ALPHA_ENHANCEMENT`, **AND** in **both** Discovery and Holdout:
     - Reduces annualized portfolio volatility ($\sigma_{\text{port}}(P_k) < \sigma_{\text{port}}(P_0)$) or reduces active maximum drawdown ($|\text{MDD}_{\text{active}}(P_k)| < |\text{MDD}_{\text{active}}(P_0)|$), **AND**
     - Improves or maintains active risk-adjusted efficiency ($t_{\text{active vs EW net}}(P_k) \ge t_{\text{active vs EW net}}(P_0)$), **AND**
     - Does not sacrifice more than $-1.0\%/\text{yr}$ of net return in either window ($D_{\text{disc}} > -1.0\%/\text{yr}$ and $D_{\text{hold}} > -1.0\%/\text{yr}$).
3. **`REJECTED`:**
   - Fails both `ALPHA_ENHANCEMENT` and `RISK_CONTROL_ONLY`.

---

## Results (added 2026-10-17, after the run; the sections above are unchanged)

Script: [`scripts/research_quality_value_lowvol.py`](../../scripts/research_quality_value_lowvol.py) · Output: `data/reports/research_quality_value_lowvol_2026-10-17.json` · Panel: C1 point-in-time non-financial monthly factor panel (`162` months, `2013-04` to `2026-09`, `liq_drop_pct = 0.30`).

### 1. Strict `NaN` Coverage Diagnostics

| Feature | Overall `obs_pct` | Monthly Mean % | Monthly Min % | Post-2013 Warm-Up Min % | Avg Valid Names / Mo |
|---|---|---|---|---|---|
| `value_sn_z` | `100.00%` | `100.00%` | `100.00%` | `100.00%` | `251.19` |
| `roe_sn_z` | `96.79%` | `96.62%` | `92.51%` | `92.51%` | `243.12` |
| `roa_sn_z` | `98.83%` | `98.82%` | `96.04%` | `96.04%` | `248.26` |
| `opa_sn_z` | `98.83%` | `98.82%` | `96.04%` | `96.04%` | `248.26` |
| `gpa_sn_z` | `98.83%` | `98.82%` | `96.04%` | `96.04%` | `248.26` |
| `f7` | `91.87%` | `90.51%` | `0.00%` | `91.90%` | `230.77` |
| `qual_sn_z` (`strict NaN`, `skipna=False`) | `89.91%` | `88.43%` | `0.00%` | `88.55%` | `225.84` |
| `qual_sn_z_skipna` (`skipna=True`) | `98.83%` | `98.82%` | `96.04%` | `96.04%` | `248.26` |
| `vol60_z` | `100.00%` | `100.00%` | `100.00%` | `100.00%` | `251.19` |

*(Note: `f7` requires 4-quarter YoY changes in ROA, leverage, current ratio, gross margin, and asset turnover, so its first 8 panel months `2013-04`..`2013-11` are warm-up `NaN`s; from `2013-12` onward its minimum monthly coverage is `91.90%`.)*

---

### 2. Family A — Conditional Double-Sorts Inside the Cheapest Value Quintile (`V_Q5`, Top 20%)

*(All spreads in `%/yr`, Newey-West $t$ with 6 lags; `Non-Low` = `Mid + High` terciles, i.e., dropping only the worst 30% inside `V_Q5`; `trap_6m_pct` = share of picks with `fwd_ret_6m_xs < -30%`.)*

| Metric inside `V_Q5` | Full `High−Low` ($t$) | Disc `High−Low` ($t$) | Hold `High−Low` ($t$) | Full `Non-Low − All V_Q5` ($t$) | Disc `Non-Low − All V_Q5` ($t$) | Hold `Non-Low − All V_Q5` ($t$) | Holdout 6m Trap Rate (`Low` $\to$ `High` / `Non-Low` vs `All V_Q5` `18.77%`) |
|---|---|---|---|---|---|---|---|
| **`Q_roe`** (`roe_sn_z`) | `-9.35%` (`-1.99`) | `-14.99%` (`-2.98`) | `-1.63%` (`-0.20`) | `-1.16%` (`-0.89`) | `-2.91%` (`-1.75`) | **`+1.23%`** (`0.67`) | `20.31%` $\to$ `20.48%` / `17.95%` |
| **`Q_roa`** (`roa_sn_z`) | `-7.21%` (`-1.54`) | `-9.16%` (`-1.37`) | `-4.53%` (`-0.69`) | `-1.40%` (`-1.21`) | `-2.02%` (`-1.16`) | `-0.56%` (`-0.39`) | `18.35%` $\to$ `20.69%` / `18.83%` |
| **`Q_opa`** (`opa_sn_z`) | `+0.85%` (`0.18`) | `-2.66%` (`-0.38`) | **`+5.65%`** (`1.10`) | `+0.89%` (`0.73`) | `+0.06%` (`0.03`) | **`+2.02%`** (`1.75`) | `16.86%` $\to$ `21.49%` / `19.44%` |
| **`Q_gpa`** (`gpa_sn_z`) | `-3.56%` (`-0.67`) | `-5.47%` (`-0.78`) | `-0.95%` (`-0.11`) | `-0.20%` (`-0.16`) | `-1.33%` (`-0.77`) | **`+1.34%`** (`0.71`) | `23.02%` $\to$ `17.94%` / `16.93%` |
| **`Q_f7`** (`f7`) | `+2.51%` (`0.44`) | `+3.91%` (`0.65`) | `+0.75%` (`0.08`) | `+0.05%` (`0.03`) | `-2.01%` (`-0.77`) | **`+2.62%`** (`1.38`) | `15.48%` $\to$ `18.33%` / `18.27%` |
| **`Q_qual`** (`qual_sn_z` strict) | `-5.22%` (`-0.87`) | `-7.95%` (`-0.98`) | `-1.82%` (`-0.21`) | `-1.21%` (`-0.57`) | `-3.78%` (`-1.10`) | **`+2.01%`** (`1.15`) | `17.53%` $\to$ `18.61%` / `17.31%` |
| **`R_lowvol`** (`vol60_z`) | `-7.12%` (`-0.78`) | `-24.22%` (`-1.94`) | **`+16.28%`** (`1.74`) | `-2.19%` (`-0.97`) | `-5.53%` (`-1.69`) | **`+2.38%`** (`0.99`) | **`28.54%` $\to$ `10.63%` / `14.74%`** |

*(Across the broader cheap pool `V_Q4 + V_Q5` [top 40%], `Q_f7` `Non-Low − All` in Holdout is `+3.11%/yr`, $t = 1.97$, and `R_lowvol` `High − Low` in Holdout is `+9.63%/yr`, $t = 1.44$, reducing 6m value-trap incidence from `28.62%` in `Low` to `12.84%` in `High`.)*

**Structural insight from Family A:**
1. **Why `High − Low` quality spreads inside `V_Q5` are negative in Discovery (2013–2020):** Within `V_Q5`, the stocks with the highest trailing `ROE` or `ROA` are already profitable companies whose cheapness comes from `ep`/`ey`, whereas the stocks with depressed trailing `ROE` inside `V_Q5` are deep book-to-market (`B/M`) cyclical turnarounds. In 2013–2020, those deep `B/M` cyclical turnarounds rebounded strongly (`High − Low` `-14.99%/yr`, $t = -2.98$ for `Q_roe`).
2. **Asymmetry between top-tercile selection (`High`) and left-tail distress removal (`Non-Low`) in Holdout (2021–2026):** In the 2021–2026 high-inflation/IAS 29 regime, dropping the worst 30% tail (`Non-Low − All V_Q5`) improved returns across almost every metric (`Q_f7` `+2.62%/yr`, $t = 1.38$; `R_lowvol` `+2.38%/yr`, $t = 0.99$, and `High − All V_Q5` **`+10.46%/yr`, $t = 2.49$**; `Q_opa` `+2.02%/yr`, $t = 1.75$; `Q_qual` `+2.01%/yr`, $t = 1.15$; `Q_gpa` `+1.34%/yr`, $t = 0.71$; `Q_roe` `+1.23%/yr`, $t = 0.67$), but none achieved a stationary `High − Low` $t \ge 2.0$ across both sample halves.
3. **Low-volatility (`R_lowvol`) strongly separates value traps from steady compounders inside `V_Q5`:** Across the full sample, the highest-volatility tercile (`Low` of `vol60_z`) inside `V_Q5` had a **6-month value-trap rate of `15.94%`** (`28.54%` in Holdout, `7.40%` in Discovery), compared to **`5.73%`** (`10.63%` in Holdout, `2.40%` in Discovery) in the lowest-volatility tercile (`High` of `vol60_z`) — cutting severe 6-month crashes (`< -30%` excess) bynearly two-thirds in both sub-periods.

---

### 3. Family B — Costed Portfolio Variants (`1,000,000 TL`, Next-Day Close, Base Costs, vs Costed `EW net`)

| Variant | Full Active vs `EW net` ($t$) | Disc Active vs `EW net` ($t$) | Hold Active vs `EW net` ($t$) | Disc Paired $D$ vs `P0` ($t$) | Hold Paired $D$ vs `P0` ($t$) | Hold vs BIST 100 TR ($t$) | Hold USD CAGR | Hold $\sigma_{\text{port}}$ / Sharpe | Hold $\text{MDD}_{\text{USD}}$ / $\text{MDD}_{\text{active}}$ | Full Turn / Cost | Hold 6m Trap Rate | Pre-Registered Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **`P0_value_top20`** | `+9.02%` (`3.53`) | `+10.58%` (`2.68`) | `+6.89%` (`2.55`) | — | — | `-1.71%` (`-0.28`) | `+3.61%` | `34.33%` / `0.51` | `-43.9%` / `-8.55%` | `20.2%` / `1.71%` | `18.64%` | `BASELINE` |
| **`QV1_roe_filter`** | **`+9.57%`** (`3.51`) | **`+10.87%`** (`2.63`) | **`+7.80%`** (`2.55`) | **`+0.29%`** (`0.25`) | **`+0.91%`** (`0.75`) | `-0.80%` (`-0.14`) | `+4.70%` | `33.76%` / `0.55` | `-41.2%` / `-9.03%` | `21.5%` / `1.82%` | `18.02%` | `REJECTED` |
| **`QV2_f7_filter`** | `+7.97%` (`2.61`) | `+6.91%` (`1.53`) | **`+9.42%` (`2.79`)** | `-3.67%` (`-1.49`) | **`+2.53%` (`1.86`)** | **`+0.82%`** (`0.13`) | **`+6.02%`** | `34.86%` / `0.58` | `-42.1%` / `-8.42%` | `24.3%` / `2.09%` | `17.95%` | `REJECTED` |
| **`QV3_qual_in_top30`** | `+5.05%` (`1.96`) | `+3.18%` (`0.90`) | `+7.62%` (`2.18`) | `-7.40%` (`-1.85`) | `+0.73%` (`0.26`) | `-0.98%` (`-0.22`) | `+4.44%` | `34.08%` / `0.54` | **`-37.6%`** / **`-8.18%`** | `22.7%` / `1.86%` | `17.34%` | `REJECTED` |
| **`LV1_lowvol_filter`** | `+6.70%` (`2.90`) | `+6.63%` (`2.11`) | `+6.79%` (`2.02`) | `-3.95%` (`-2.55`) | `-0.09%` (`-0.07`) | `-1.80%` (`-0.31`) | `+3.59%` | `34.06%` / `0.51` | `-42.0%` / `-11.58%` | `24.1%` / `2.06%` | `16.49%` | `REJECTED` |
| **`LV2_lowvol_in_top25`** | `+6.07%` (`2.74`) | `+4.04%` (`1.48`) | **`+8.85%` (`2.55`)** | `-6.54%` (`-1.65`) | **`+1.96%` (`0.99`)** | **`+0.25%`** (`0.05`) | **`+5.91%`** | **`33.46%` / `0.58`** | **`-38.5%`** / `-9.16%` | `24.2%` / `2.02%` | **`15.35%`** | `REJECTED` |
| **`QLV_combined_filter`** | `+7.76%` (`3.20`) | `+7.59%` (`2.35`) | `+8.00%` (`2.23`) | `-2.99%` (`-1.54`) | `+1.11%` (`0.77`) | `-0.60%` (`-0.10`) | `+4.85%` | `33.92%` / `0.55` | `-41.7%` / `-10.51%` | `25.0%` / `2.14%` | `16.32%` | `REJECTED` |

---

### 4. Evaluation Against Pre-Registered Decision Rules (Alpha Enhancement vs Risk Control)

1. **No variant passes `ALPHA_ENHANCEMENT`:**
   - **`QV1_roe_filter`** (dropping the bottom-20% `roe_sn_z` tail from `V_Q5`) is the **only** filter with positive paired net return differences in both Discovery (`+0.29%/yr`, $t = 0.25$) and Holdout (`+0.91%/yr`, $t = 0.75$), lifting Full active return vs `EW net` from `+9.02%` to `+9.57%/yr` ($t = 3.51$), Holdout active return from `+6.89%` to `+7.80%/yr` ($t = 2.55$), and Holdout USD CAGR from `+3.61%` to `+4.70%` while lowering portfolio volatility (`34.33%` $\to$ `33.76%`) and USD max drawdown (`-43.9%` $\to$ `-41.2%`). However, its paired $t$-statistics (`0.25` and `0.75`) are well below the pre-registered `ALPHA_ENHANCEMENT` thresholds ($t_{\text{disc}} \ge 2.0$, $t_{\text{hold}} \ge 1.96$).
   - **`QV2_f7_filter`** (`F7 >= 4` inside `V_Q5`) delivers the strongest Holdout improvement: active return vs `EW net` rises from `+6.89%` ($t = 2.55$) to **`+9.42%/yr` ($t = 2.79$)**, paired $D_{\text{hold}} = +2.53\%/\text{yr}$ ($t = 1.86$), USD CAGR rises from `+3.61%` to **`+6.02%`**, and it beats BIST 100 Total Return (`+0.82%/yr`). However, in Discovery (2013–2020) it cost `-3.67%/yr` ($t = -1.49$) because `F7` was `NaN` during the 2013 warm-up and excluded deep cyclical turnarounds, and its Holdout paired $t = 1.86$ is just shy of $1.96$.
2. **Low-Volatility Filters (`LV1`, `LV2`) Act as Holdout Risk & Value-Trap Compressors, Not Stationary Alpha Generators:**
   - In Holdout (2021–2026), the breadth-preserving **`LV2_lowvol_in_top25`** (cheapest 25% by `value_sn_z`, dropping the most volatile 20% within that cheap pool) reduces annualized volatility from `34.33%` to **`33.46%`** (`31.27%` $\to$ `27.83%` in Discovery), cuts USD max drawdown from `-43.9%` to **`-38.5%`**, reduces the 6-month value-trap rate from `18.64%` to **`15.35%`** (`4.29%` $\to$ `3.54%` in Discovery), and raises Holdout active return vs `EW net` to **`+8.85%/yr` ($t = 2.55$, paired $D = +1.96\%/\text{yr}, t = 0.99$, vs BIST 100 TR `+0.25%/yr`, USD CAGR `+5.91%`)**.
   - However, in Discovery (2013–2020), high-volatility deep-value stocks rebounded sharply and extra monthly turnover (`20.2%` $\to$ `24.2%`, cost drag `1.71%` $\to$ `2.02%/yr`) penalized both `LV1` ($D_{\text{disc}} = -3.95\%/\text{yr}, t = -2.55$) and `LV2` ($D_{\text{disc}} = -6.54\%/\text{yr}, t = -1.65$), violating the pre-registered `RISK_CONTROL_ONLY` non-degradation bound ($D_{\text{disc}} > -1.0\%/\text{yr}$ and $t_{\text{active}}(P_k) \ge t_{\text{active}}(P_0)$).
   - Even `QV1_roe_filter`, which meets the return non-degradation bound in both periods ($D_{\text{disc}} = +0.29\%$, $D_{\text{hold}} = +0.91\%$) and lowers $\sigma_{\text{port}}$ in both periods (`31.27%` $\to$ `31.19%` Discovery, `34.33%` $\to$ `33.76%` Holdout), has $t_{\text{active}} = 2.63 < 2.68$ in Discovery (`2.55 = 2.55` in Holdout), so under the strict pre-registered rule it is also classified as `REJECTED`.
3. **Live Rule Decision:**
   - Keep `config/live_rule.json` (`R0-2026-10-12`, plain `value_sn` top 20%) unchanged. Neither conditional quality filtering nor low-volatility filtering is promoted into the live selection rule.
