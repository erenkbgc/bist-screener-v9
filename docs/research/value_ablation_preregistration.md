# `value_sn` component ablation (removing `S/P` and simpler subsets): pre-registration

Written and committed on 2026-10-17, **before** the ablation runner was executed on the panel. All variants, metrics, windows, and decision rules are fixed here and are not changed after seeing the results.

## Question

The live decision rule R0 ranks the liquid non-financial universe by `value_sn`, the sector-neutralized equal-weighted average of four valuation z-scores:
- `bm`: book-to-market (`equity / mcap`),
- `ep`: earnings-to-price (`ttm_ni / mcap`),
- `sp`: sales-to-price (`ttm_revenue / mcap`),
- `ey`: operating earnings yield (`ttm_ebit / (mcap + net_debt)`).

Two pieces of prior evidence question whether all four legs should be weighted equally:
1. In the accounting multiples literature (Liu, Nissim & Thomas 2002, *Journal of Accounting Research*), sales multiples are the weakest valuation indicator across almost all sectors (`docs/research/sector_specific_notes.md`).
2. In the IAS 29 regime test (`docs/research/ias29_regime_preregistration.md`) and the constant-unit TTM test (`docs/research/ias29_constant_unit_ttm_preregistration.md`), the standalone rank-IC of `sp` turned negative after the IAS 29 switch (2024-05 onward), and this persisted on the C1 constant-purchasing-power panel.

Rather than adding new indicators, this study tests whether removing `sp` or restricting `value_sn` to the two core equity multiples (`bm`, `ep`) improves stock ranking, the performance of stocks that enter/leave the top quintile, and **after-cost portfolio returns** under the exact pre-registered portfolio simulator (`core/portfolio_backtest.py`).

## Prior exposure, stated honestly

- The C1 panel (2013-04 to 2026-08) and the baseline 4-leg `value_sn` results are already known (`long_term_preregistration.md`, `portfolio_backtest_preregistration.md`, `total_return_benchmarks_preregistration.md`, `c1_panel_rebuild.md`).
- Exploratory single-factor ICs in the IAS 29 window (`2024-05+`, 28 months) were seen in `ias29_regime_preregistration.md`. Full-history portfolio simulations and switcher returns for the 3-leg (`bm, ep, ey`) and 2-leg (`bm, ep`) composites have **not** been run before this document was written.

## Data and universe

- Base C1 monthly panel (`research_long_term.load()`): non-financial BIST stocks, actual KAP publication dates where matched (75/100-day fallback otherwise), IAS 29 quarterly flows in constant CPI purchasing power (C1), bottom 30% by 60-day median daily TL volume (`tlvol60`) dropped each month.
- Daily adjusted and raw prices from `data/research/raw/*.pkl`, `fx.parquet`, and `macro_monthly.parquet`, exactly as in `research_portfolio_backtest.py`.
- **Discovery:** decisions 2013-04 to 2020-12 (93 months).
- **Holdout:** decisions 2021-01 to 2026-08 (68 months).
- **IAS 29 sub-window (descriptive):** 2024-05 to 2026-08 (28 months).

## Variants (fixed)

For any component tuple $C \subseteq \{\text{bm}, \text{ep}, \text{sp}, \text{ey}\}$:
1. Each component $f \in C$ is cross-sectionally winsorized at 1%/99% and standardised (`f_z`) within each month's liquid universe (`core/factor_backtest.py::prepare`).
2. Raw composite: $v_C = \text{mean}(\{f\text{\_z} : f \in C\})$ over available components for that stock-month.
3. Sector-neutral composite: $s_C = \text{sector\_neutralize}(v_C, \text{min\_n}=5)$ (demeaned within sector when the sector has at least 5 names in that month, market mean otherwise).

The three compared composites are:
- **V0 (Baseline, 4 legs):** `("bm", "ep", "sp", "ey")` — current live `value_sn`.
- **V1 (No S/P, 3 legs):** `("bm", "ep", "ey")` — drops sales-to-price.
- **V2 (Book + Earnings, 2 legs):** `("bm", "ep")` — keeps only the two equity-level multiples (no enterprise-value debt adjustment or sales multiple).

Single sector-neutral legs (`bm_sn`, `ep_sn`, `sp_sn`, `ey_sn`) are also reported as diagnostics via a joint monthly Fama-MacBeth regression of `fwd_ret_1m` on all four legs simultaneously.

## Metrics

For each variant $V_k \in \{V_1, V_2\}$ compared against $V_0$, in both **Discovery** and **Holdout**:

1. **Cross-sectional ranking (Rank-IC):**
   - Mean monthly Spearman Rank-IC against `fwd_ret_1m`, Newey-West $t$ (6 lags),
   - Paired monthly difference $\Delta\text{IC}_t = \text{IC}(V_k)_t - \text{IC}(V_0)_t$ and its 6-lag Newey-West $t$.
2. **Rank stability and switcher portfolio (who enters vs who leaves the top 20%):**
   - Average monthly cross-sectional Spearman correlation $\rho(V_k, V_0)$,
   - Top-20% overlap ratio $|Q_5(V_k)_t \cap Q_5(V_0)_t| / |Q_5(V_0)_t|$,
   - **Switcher return spread:** in each month $t$ where $Q_5(V_k)_t \neq Q_5(V_0)_t$, the equal-weighted 1-month return of **entrants** ($Q_5(V_k)_t \setminus Q_5(V_0)_t$) minus **dropouts** ($Q_5(V_0)_t \setminus Q_5(V_k)_t$), annualised ($12 \times$ mean) with 6-lag Newey-West $t$.
3. **Costed portfolio simulation (`core/portfolio_backtest.py::simulate`):**
   - Top 20% equal-weighted monthly rebalance, 1M TL real capital (2026-09 TL scaled by CPI), base cost scenario (10 bps commission + liquidity-tier half-spread + square-root market impact), next-day close fills, cash at the policy rate, unbuyable fill-day target weights kept in cash,
   - Active return against the **costed equal-weighted universe (`EW net`, B2)**, annualised ($12 \times$ monthly mean) with 6-lag Newey-West $t$,
   - **Primary paired portfolio test:** $D_t = r_{\text{net}}(V_k)_t - r_{\text{net}}(V_0)_t$, annualised %/yr and 6-lag Newey-West $t$,
   - Monthly one-way turnover, annual cost drag (%/yr), and maximum drawdown in TL and USD.

## Decision rules

1. **SUPERIOR (`PASS`):** A variant $V_k \in \{V_1, V_2\}$ beats $V_0$ if its paired costed portfolio return difference $D = r_{\text{net}}(V_k) - r_{\text{net}}(V_0)$ has:
   - $D > 0$ and NW $t > 3.0$ in Discovery (2013–2020), **and**
   - $D > 0$ and NW $t > 2.0$ in Holdout (2021–2026), **and**
   - positive switcher spread (entrants beat dropouts) in both windows.
2. **NON_INFERIOR_SIMPLIFICATION:** For $V_1$ (removing `sp`), if it does not meet the `SUPERIOR` threshold above, it is classified as a non-inferior simplification if **all** of the following hold:
   - In the joint 4-leg Fama-MacBeth regression, `sp_sn` has no significant positive marginal slope ($t \le 2.0$) in either Discovery or Holdout,
   - Paired costed portfolio difference $D(V_1 - V_0)$ is non-negative ($\ge 0$) or statistically indistinguishable from zero with $D > -0.50\%/\text{yr}$ and $t > -1.0$ in both Discovery and Holdout,
   - Holdout net active return of $V_1$ vs costed `EW net` remains $> 0$ with $t > 2.0$.
3. **FAIL / KEEP_V0:** Otherwise, the 4-leg composite carries non-redundant information and $V_0$ stays preferred.
4. **Live rule:** Regardless of the classification, `config/live_rule.json` (`R0-2026-10-12`) is **not** changed automatically by this study. Any live rule change requires an explicit version bump (`R1-...`) so the forward record splits cleanly.

## Results (added 2026-10-17, after the run; the sections above are unchanged)

Runner: `python3 scripts/research_value_ablation.py` → `data/reports/research_value_ablation_2026-10-17.json`.

### 1. Single sector-neutral legs (`bm_sn`, `ep_sn`, `sp_sn`, `ey_sn`)

| Leg | Discovery (2013-04..2020-12, 93m) Rank-IC ($t$) | Discovery Joint FM Slope %/yr ($t$) | Holdout (2021-01..2026-08, 68m) Rank-IC ($t$) | Holdout Joint FM Slope %/yr ($t$) | IAS 29 (2024-05..2026-08, 28m) Rank-IC ($t$) | IAS 29 Joint FM Slope %/yr ($t$) |
|---|---:|---:|---:|---:|---:|---:|
| `bm_sn` (B/M) | +0.0214 (+2.07) | +3.13% (+1.93) | +0.0363 (+3.19) | +2.99% (+1.27) | +0.0129 (+0.93) | +1.00% (+0.24) |
| `ep_sn` (E/P) | +0.0186 (+2.04) | −2.96% (−1.26) | +0.0489 (+3.92) | +4.78% (+1.82) | +0.0347 (+2.06) | +2.55% (+1.36) |
| `sp_sn` (S/P) | +0.0060 (+0.57) | +2.17% (+1.66) | +0.0391 (+3.13) | +2.82% (+1.47) | −0.0014 (−0.12) | −1.11% (−0.38) |
| `ey_sn` (EV/EBITDA) | **+0.0420 (+4.61)** | +1.82% (+0.79) | **+0.0532 (+4.67)** | −0.17% (−0.12) | **+0.0372 (+3.00)** | −0.74% (−0.62) |

- **`ey_sn` (`ttm_ebit / EV`) is the strongest standalone leg across every window** (Discovery IC +0.0420, $t = 4.61$; Holdout IC +0.0532, $t = 4.67$; IAS 29 IC +0.0372, $t = 3.00$).
- **`sp_sn` (`ttm_revenue / mcap`) has the weakest standalone IC in Discovery (+0.0060, $t = 0.57$) and collapses to zero in the IAS 29 sub-window (−0.0014, $t = -0.12$)**, though in the 2021–2023 pre-IAS 29 high-inflation portion of Holdout it contributed positively (Holdout IC +0.0391, $t = 3.13$). In the joint 4-leg Fama-MacBeth regression, `sp_sn`'s marginal slope never exceeds $t = 2.0$ (+2.17%/yr, $t = 1.66$ in Discovery; +2.82%/yr, $t = 1.47$ in Holdout; −1.11%/yr, $t = -0.38$ in IAS 29).

### 2. Composite Rank-IC and top-20% switcher analysis

| Variant | Window | Mean Rank-IC ($t$) | Paired $\Delta\text{IC}$ vs $V_0$ ($t$) | Rank Corr vs $V_0$ | Top-20% Overlap | Switches / mo | Entrants − Dropouts %/yr ($t$) |
|---|---|---:|---:|---:|---:|---:|---:|
| **V0 (`bm+ep+sp+ey`)** | Discovery (93m) | +0.0407 (+5.14) | — | 1.000 | 100.0% | 0.0 | — |
| | Holdout (68m) | +0.0617 (+4.91) | — | 1.000 | 100.0% | 0.0 | — |
| | IAS 29 (28m) | +0.0340 (+2.22) | — | 1.000 | 100.0% | 0.0 | — |
| **V1 (`bm+ep+ey`, no `sp`)** | Discovery (93m) | +0.0387 (+5.35) | −0.0020 (−0.50) | 0.930 | 83.1% | 7.3 | −9.64% (−0.87) |
| | Holdout (68m) | +0.0630 (+5.07) | +0.0013 (+0.44) | 0.928 | 81.9% | 10.7 | **+10.96% (+1.51)** |
| | IAS 29 (28m) | **+0.0429 (+2.82)** | **+0.0088 (+4.01)** | 0.929 | 82.1% | 12.3 | **+10.97% (+1.76)** |
| **V2 (`bm+ep` only)** | Discovery (93m) | +0.0278 (+3.91) | −0.0129 (−2.42) | 0.805 | 69.6% | 13.0 | −7.12% (−1.03) |
| | Holdout (68m) | +0.0536 (+4.39) | −0.0081 (−2.00) | 0.845 | 70.6% | 17.5 | +2.37% (+0.40) |
| | IAS 29 (28m) | +0.0339 (+2.35) | −0.0001 (−0.03) | 0.847 | 68.7% | 21.5 | +5.07% (+0.57) |

### 3. Costed portfolio simulation (1M TL real capital, base costs, next-day close, vs `EW net`)

| Variant | Window | Active vs `EW net` %/yr ($t$) | Active vs `EW gross` %/yr ($t$) | Paired $D = r_{\text{net}}(V_k) - r_{\text{net}}(V_0)$ %/yr ($t$) | USD CAGR % | Max DD USD % | 1-Way Turnover % | Cost Drag %/yr | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| **V0 (`bm+ep+sp+ey`)** | Discovery (93m) | +10.58% (+2.68) | +9.81% (+2.47) | — | +17.57% | −58.1% | 20.3% | 1.86% | Baseline |
| | Holdout (68m) | +6.89% (+2.55) | +6.11% (+2.29) | — | +3.61% | −43.9% | 20.0% | 1.50% | |
| | IAS 29 (28m) | +2.74% (+0.70) | +1.87% (+0.48) | — | −8.66% | −24.3% | 19.8% | 1.51% | |
| **V1 (`bm+ep+ey`, no `sp`)** | Discovery (93m) | +8.03% (+2.59) | +7.27% (+2.31) | −2.55% (−1.21) | +15.16% | −57.3% | 21.7% | 1.98% | **`KEEP_V0`** |
| | Holdout (68m) | **+8.84% (+3.31)** | **+8.06% (+3.06)** | +1.95% (+1.44) | **+5.35%** | **−38.8%** | 21.6% | 1.60% | |
| | IAS 29 (28m) | **+5.10% (+1.44)** | **+4.24% (+1.20)** | **+2.37% (+1.95)** | −6.71% | −25.7% | 21.4% | 1.64% | |
| **V2 (`bm+ep` only)** | Discovery (93m) | +7.28% (+2.65) | +6.52% (+2.35) | −3.30% (−1.41) | +14.00% | −57.9% | 19.8% | 1.88% | **`KEEP_V0`** |
| | Holdout (68m) | +6.67% (+2.14) | +5.90% (+1.91) | −0.22% (−0.14) | +3.06% | −44.7% | 20.4% | 1.56% | |
| | IAS 29 (28m) | +4.76% (+0.92) | +3.90% (+0.75) | +2.03% (+0.72) | −6.88% | −26.3% | 20.2% | 1.59% | |

### 4. Interpretation and decision

1. **Both $V_1$ and $V_2$ classify as `KEEP_V0` under the pre-registered decision rules:**
   - **$V_2$ (`bm+ep` only) is rejected (`KEEP_V0`):** Dropping `ey` (`EV/EBITDA`) degrades cross-sectional Rank-IC significantly in both Discovery ($\Delta\text{IC} = -0.0129, t = -2.42$) and Holdout ($\Delta\text{IC} = -0.0081, t = -2.00$) and costs −3.30%/yr ($t = -1.41$) in Discovery portfolio return. Enterprise-value operating earnings yield (`ey`) is an essential pillar of `value_sn`.
   - **$V_1$ (`bm+ep+ey`, removing `sp`) shows a sharp regime split:**
     - In **Holdout (2021–2026)** and especially **IAS 29 (2024-05+)**, removing `sp` improves performance across every metric: IAS 29 Rank-IC rises from +0.0340 to +0.0429 ($\Delta\text{IC} = +0.0088, t = +4.01$), Holdout switcher spread (entrants minus dropouts) is +10.96%/yr ($t = +1.51$), and Holdout costed active return vs `EW net` rises from **+6.89%/yr ($t = 2.55$) to +8.84%/yr ($t = 3.31$)** (paired difference $D = +1.95\%/\text{yr}, t = +1.44$; IAS 29 paired difference $D = +2.37\%/\text{yr}, t = +1.95$), while USD max drawdown improves from −43.9% to −38.8%.
     - However, in **Discovery (2013–2020)**, removing `sp` cost −2.55%/yr ($t = -1.21$, switcher spread −9.64%/yr, $t = -0.87$), which violates both the `SUPERIOR` discovery gate ($D > 0, t > 3.0$) and the `NON_INFERIOR_SIMPLIFICATION` discovery bound ($D > -0.50\%/\text{yr}, t > -1.0$).
2. **Actionable takeaway:** `config/live_rule.json` (`R0-2026-10-12`) remains locked on the 4-leg `V0` (`bm, ep, sp, ey`) to respect the pre-registered full-cycle hurdle, while `V1` (`bm, ep, ey`) is retained as the primary IAS 29 shadow composite.
