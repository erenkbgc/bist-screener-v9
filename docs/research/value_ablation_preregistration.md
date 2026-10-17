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
