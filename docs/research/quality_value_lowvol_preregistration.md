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
