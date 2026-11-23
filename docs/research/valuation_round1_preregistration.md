# Valuation Round 1 — Multi-Track Pre-Registration (`S1`, `M2`, `FV1`)

**Date:** 2026-11-22  
**Branch:** `agent/valuation`  
**Role:** Head of Research (Chair)  
**Baseline live rule:** `R0-2026-10-12` — monthly top-20% equal-weighted non-financial portfolio by `value_sn` (`bm`, `ep`, `sp`, `ey`, 1%/99% winsorized cross-sectional z-scores, averaged and demeaned within sector with `min_n = 5`) on the promoted point-in-time panel `data/research/factors_monthly.parquet` (`lag75`; `data/research/factors_monthly_kapdates.parquet` for KAP-date sensitivity).  
**Debate record:** [`valuation_debate/r1_proposal_fundamental.md`](../../valuation_debate/r1_proposal_fundamental.md), [`valuation_debate/r1_proposal_macro.md`](../../valuation_debate/r1_proposal_macro.md), [`valuation_debate/r1_proposal_statistical.md`](../../valuation_debate/r1_proposal_statistical.md), [`valuation_debate/r1_critique.md`](../../valuation_debate/r1_critique.md), [`valuation_debate/r1_rebuttal_fundamental.md`](../../valuation_debate/r1_rebuttal_fundamental.md), [`valuation_debate/r1_rebuttal_macro.md`](../../valuation_debate/r1_rebuttal_macro.md), [`valuation_debate/r1_rebuttal_statistical.md`](../../valuation_debate/r1_rebuttal_statistical.md), [`valuation_debate/r1_decision.md`](../../valuation_debate/r1_decision.md).  
**Trial ledger update:** Adds **+3** confirmatory `stock_selection` trials (`S1`, `M2`, `FV1`) to `data/research/trial_ledger.json`, updating `N_sel` from **86 to 89** (committed **before** any backtest script or return evaluation exists).  
**Planned runner script:** `scripts/research_valuation_round1.py`  
**Planned output file:** `data/reports/research_valuation_round1_2026-11-22.json`

---

## 1. Fixed Pass Rule (Verbatim)

> FIXED PASS RULE (cannot be changed by any agent): candidate monthly top-20% portfolio vs R0 value_sn top-20%, same universe, liquidity cut, 1M TL costs and next-close fills as scripts/research_portfolio_backtest.py. Paired D = net active(candidate) - net active(R0). PASS iff D > 0 in discovery 2013-2020 with NW t(D) >= 1.0 AND D > 0 in holdout 2021+ with NW t(D) >= 2.0 AND holdout USD max drawdown not worse than R0 by more than 2 pp. Also report DSR at the updated N_sel. Every method tested adds +1 to N_sel in the trial ledger, PASS or FAIL.

### Operationalization in Existing Codebase Primitives

1. **Universe & liquidity cut (`scripts/research_long_term.py::load` / `core/factor_backtest.py::prepare`):**
   - Primary panel: `data/research/factors_monthly.parquet` (`lag75`; 75-day lag for Q1–Q3, 100-day lag for Q4; C1 constant purchasing power for `>= 2023Q4` with vendor re-expression undone and `bridge_ttm`; İş Yatırım HisseTekil `PD` market value with `shares_at` fallback).
   - Sensitivity panel (descriptive): `data/research/factors_monthly_kapdates.parquet` (actual KAP first-publication dates).
   - Non-financial universe, monthly month-end dates $t$ (`2013-04` to `2026-09`), dropping the bottom 30% by 60-day median daily TL volume (`tlvol60 > 0`, `liq_drop_pct = 0.30`, `min_names = 30`), restricted to rows where baseline `R0` (`value_sn_z`) is non-null (`df[df["value_sn_z"].notna()]`), matching `scripts/research_portfolio_backtest.py` and `scripts/research_value_ablation.py`.
2. **Portfolio selection (`TOP = 0.20`):**
   - In each decision month $t$, for baseline `R0` and each candidate method $k \in \{\texttt{S1}, \texttt{M2}, \texttt{FV1}\}$, rank all liquid universe stocks with a non-null score $S^{(k)}_{i,t}$ in descending order (`h[col].rank(ascending=False, pct=True) <= 0.20`) and select the top 20% equal-weighted.
3. **Portfolio simulator, costs, capital, and fills (`core/portfolio_backtest.py::simulate` & `scripts/research_portfolio_backtest.py`):**
   - Real capital: **1M TL** in `CAPITAL_REF = pd.Timestamp("2026-09-30")` purchasing power (`cap[t] = 1e6 * cpi_rel[t]`).
   - Transaction costs: base cost schedule `pb.Costs()` (commission + liquidity-tier half-spread + square-root market impact on daily ADV and volatility $\sigma$).
   - Fill timing: next trading day close after month-end decision date $t$ (`fill = "close"`, `haircut = 0.0`).
   - Cash rate: daily compounded TCMB policy rate (`pb.policy_rf_daily(macro["policy"], days)`).
4. **Windows:**
   - **Discovery:** decision months `date < 2021-01-01` (`2013-04` to `2020-12`, 93 completed monthly return periods).
   - **Holdout:** decision months `date >= 2021-01-01` (`2021-01` to `2026-08`, 68 completed monthly return periods; `2026-09` has no forward month in `attach_benchmarks`).
   - **IAS 29 sub-window (descriptive only):** decision months `date >= 2024-05-01` (`2024-05` to `2026-08`, 28 completed monthly return periods).
5. **Paired difference $D$, Newey-West $t(D)$, USD Max Drawdown, and Deflated Sharpe Ratio (DSR):**
   - Whether active return is measured against the costed equal-weighted universe (`EW net`: `active_ew_net = port - ew_net`) or the zero-cost equal-weighted universe (`EW gross`: `active_univ = port - bench`), the benchmark cancels identically in the paired monthly difference:
     $$D_{k,t} = \text{active\_net}_{k,t} - \text{active\_net}_{R0,t} = r^{\text{net}}_{k,t} - r^{\text{net}}_{R0,t}$$
     Both `vs_ew_net` and `vs_ew_gross` active returns will be reported for `R0` and each candidate.
   - Newey-West HAC $t$-statistic (`core/factor_backtest.py::newey_west_t(D_k, lags=6)`): annualised paired difference $\bar{D}_k^{\text{ann}} = 1200 \cdot \bar{D}_k$ (in %/yr) and $t(D_k)$ with 6 monthly lags.
   - Holdout USD Max Drawdown (`scripts/research_portfolio_backtest.py::_dd` on `port_usd` over `date >= 2021-01-01`): candidate passes the drawdown guardrail iff:
     $$\text{max\_dd\_usd\_pct}(k,\text{holdout}) \ge \text{max\_dd\_usd\_pct}(R0,\text{holdout}) - 2.0$$
     (where `max_dd_usd_pct` is signed negative, e.g. `-35.4%` for `R0`, so `-37.4%` is the worst permissible drawdown).
   - **PASS criterion (all three conditions required simultaneously):**
     1. Discovery (`2013-04..2020-12`): $\bar{D}_k > 0$ **and** $\text{NW } t(D_k) \ge 1.0$;
     2. Holdout (`2021-01..2026-08`): $\bar{D}_k > 0$ **and** $\text{NW } t(D_k) \ge 2.0$;
     3. Holdout USD max drawdown: $\text{max\_dd\_usd\_pct}(k,\text{holdout}) \ge \text{max\_dd\_usd\_pct}(R0,\text{holdout}) - 2.0$.
   - **Deflated Sharpe Ratio (`core/research_stats.py::deflated_sharpe`):** Reported at the updated ledger trial count **`N_sel = 89`** (`86 + 3`) on the full-sample monthly active return series (`port - ew_net`, $T = 161$ months), using the cross-variant monthly Sharpe variance $V[\widehat{\text{SR}}]$ from the 48-variant matrix in `scripts/research_quant_review.py::variant_matrix` ($V[\widehat{\text{SR}}] = 0.02335$ on the PIT baseline, giving expected maximum null monthly Sharpe $\text{SR}_0 = 0.3804$).

---

## 2. Candidate Methods Selected for Testing (3 Confirmatory Trials)

Out of 6 proposals debated in Round 1 (`FV1`, `FV2`, `M1`, `M2`, `S1`, `S2`), **3 orthogonal, zero-parameter methods** (one from each research track) are selected for confirmatory testing, and **3 methods** (`FV2`, `S2`, `M1`) were dropped/withdrawn before any return check (see [`valuation_debate/r1_decision.md`](../../valuation_debate/r1_decision.md) for the full selection and rejection summary).

| Trial # | Method ID | Column Name | Track | Core Mechanism | PIT Data Inputs | Discovery Coverage | Free Return-Fitted Params |
|---:|---|---|---|---|---|---:|---:|
| **1** | **`S1`** | `S1_value_eb_ns` | Statistical / Cross-Sectional | Blom rank-normal transformation + 2-stage Empirical-Bayes sector location & scale shrinkage ($\mathcal{E}_5$) + correlation-aware reliability-shrunk composite on `bm, ep, sp, ey` | `factors_monthly.parquet` (`bm, ep, sp, ey, sector`) | `100.0%` | `0` |
| **2** | **`M2`** | `M2_value_real_spread_sn` | EM / Turkey Macro-Adjusted | Universal CPI constant-purchasing-power TTM (lagged $t-1$) + Turkey USD Eurobond sovereign yield debt charge ($y^{\text{USD}}_{\text{TR},t}\cdot\text{NetDebt}$) + unlevered `S/EV` (`sev_real`) | `factors_monthly.parquet` + `quarterly.parquet` + `macro_monthly.parquet` + `eurobond_monthly.parquet` | `100.0%` | `0` |
| **3** | **`FV1`** | `FV1_reoi_ev_sn` | Fundamental Valuation | Closed-form Feltham-Ohlson 5-year Residual Operating Income (`V_ReOI / EV`) with Fisher nominal/real policy+ERP hurdle $r_{w,t}$, convex PV-weight normalization, and within-regime cohort standardization | `factors_monthly.parquet` + `quarterly.parquet` + `macro_monthly.parquet` | `97.6%` | `0` |

---

## 3. Exact Signal Definitions and Deterministic Construction

### 3.0 Baseline `R0` (`value_sn_z`)
Loaded directly from `research_long_term.load()`: within each month $t$ on the liquid non-financial universe (`tlvol60` bottom 30% dropped, `min_names = 30`), each of `bm`, `ep`, `sp`, `ey` is winsorized at 1%/99% and z-scored (`fb.winsorize_z(..., 0.01, 0.99)`), averaged across available legs (`value_z = mean(bm_z, ep_z, sp_z, ey_z)`), and demeaned within sector for sectors with at least 5 stocks (`value_sn_z = fb.sector_neutralize(df, "value_z", min_n=5)`).

---

### 3.1 Method 1 (`S1`): Empirical-Bayes Sector-Standardized Normal-Score Value (`S1_value_eb_ns`)

Operates strictly within each decision month $t$ on the exact four PIT valuation ratios $\mathcal{L} = \{\texttt{bm}, \texttt{ep}, \texttt{sp}, \texttt{ey}\}$ and sector label $s(i) = \texttt{sector}_{i,t}$ of the prepared liquid universe:

1. **Per-leg Blom rank-based inverse normal transformation:**  
   For each leg $m \in \mathcal{L}$ in month $t$ with $N_{m,t} \ge 3$ finite observations, compute ascending average-tie mid-ranks $r_{i,m,t} \in [1, N_{m,t}]$ (`s.rank( ascending=True, method="average")`) and map to Blom (1958) expected standard normal order statistics:
   $$u_{i,m,t} = \Phi^{-1}\!\left(\frac{r_{i,m,t} - 0.375}{N_{m,t} + 0.25}\right)$$
   where $\Phi^{-1}$ is the standard normal quantile function (`scipy.stats.norm.ppf`). Missing ratios stay `NaN`.

2. **Empirical-Bayes (Hierarchical Random-Effects) sector location & scale operator $\mathcal{E}_{\nu_0}(\cdot \mid s)$ with fixed prior degrees of freedom $\nu_0 = 5.0$:**  
   For any 1D monthly cross-sectional vector $v_{i,t}$ with $N_t \ge 5$ finite observations across $K_t$ present sectors (where sector $s$ has finite count $n_{s,t} \ge 1$, sample mean $\bar{v}_{s,t}$, and unbiased sample variance $s^2_{s,t}$ with `ddof=1` for $n_{s,t} \ge 2$ and $s^2_{s,t} := 0$ for $n_{s,t} = 1$, and grand mean $\bar{v}_{\cdot,t} = \frac{1}{N_t}\sum_i v_{i,t}$):
   - *Pooled within-sector variance (ANOVA MSW):*
     $$\text{df}_{W,t} = \sum_{s:\, n_{s,t} \ge 2} (n_{s,t} - 1), \qquad \hat{\sigma}^2_{W,t} = \begin{cases} \dfrac{\sum_{s:\, n_{s,t} \ge 2} (n_{s,t} - 1)\,s^2_{s,t}}{\text{df}_{W,t}}, & \text{if } \text{df}_{W,t} > 0, \\[8pt] \operatorname{Var}_{i}(v_{i,t}, \text{ddof}=1), & \text{otherwise.} \end{cases}$$
     (Floor $\hat{\sigma}^2_{W,t}$ at $10^{-12}$ for numerical safety.)
   - *Between-sector variance component (DerSimonian-Laird / unbalanced one-way ANOVA method of moments):*
     $$\text{MSB}_t = \frac{1}{K_t - 1}\sum_{s=1}^{K_t} n_{s,t}\,(\bar{v}_{s,t} - \bar{v}_{\cdot,t})^2, \qquad n_{0,t} = \frac{1}{K_t - 1}\!\left(N_t - \frac{\sum_{s=1}^{K_t} n_{s,t}^2}{N_t}\right)$$
     $$\hat{\tau}^2_{B,t} = \begin{cases} \max\!\left(0,\; \dfrac{\text{MSB}_t - \hat{\sigma}^2_{W,t}}{n_{0,t}}\right), & \text{if } K_t > 1 \text{ and } n_{0,t} > 0, \\ 0, & \text{otherwise.} \end{cases}$$
   - *James-Stein / BLUP shrunk sector mean:*
     $$w_{s,t} = \frac{n_{s,t}\,\hat{\tau}^2_{B,t}}{n_{s,t}\,\hat{\tau}^2_{B,t} + \hat{\sigma}^2_{W,t}}, \qquad \hat{\mu}^{\text{EB}}_{s,t} = \bar{v}_{\cdot,t} + w_{s,t}\,(\bar{v}_{s,t} - \bar{v}_{\cdot,t})$$
   - *Inverse-Gamma conjugate shrunk within-sector standard deviation ($\nu_0 = 5.0$):*
     $$\hat{\sigma}^{\text{EB}}_{s,t} = \sqrt{\frac{\max(n_{s,t} - 1, 0)\,s^2_{s,t} + \nu_0\,\hat{\sigma}^2_{W,t}}{\max(n_{s,t} - 1, 0) + \nu_0}}, \qquad \nu_0 = 5.0$$
   - *Operator output:*
     $$\mathcal{E}_5(v_{i,t} \mid s) = \frac{v_{i,t} - \hat{\mu}^{\text{EB}}_{s(i),t}}{\hat{\sigma}^{\text{EB}}_{s(i),t}}$$
   Apply $\mathcal{E}_5$ to each Blom-transformed leg $u_{\cdot,m,t}$:
   $$\tilde{z}_{i,m,t} = \mathcal{E}_5(u_{i,m,t} \mid s), \qquad m \in \{\texttt{bm}, \texttt{ep}, \texttt{sp}, \texttt{ey}\}$$

3. **Correlation-aware, variance-preserving, reliability-shrunk composite & Stage-2 EB standardization:**  
   - Compute the $4 \times 4$ pairwise Pearson correlation matrix $\hat{R}^{\text{raw}}_t$ of $(\tilde{z}_{\cdot,\text{bm},t}, \tilde{z}_{\cdot,\text{ep},t}, \tilde{z}_{\cdot,\text{sp},t}, \tilde{z}_{\cdot,\text{ey},t})$ in month $t$ (replace any `NaN` off-diagonal entry with `0.0`, set diagonal to `1.0`), and apply fixed positive-definite shrinkage:
     $$\hat{R}_t = 0.90\,\hat{R}^{\text{raw}}_t + 0.10\,I_4$$
   - For each stock $i$ with non-null leg subset $\mathcal{M}_{i,t} = \{m \in \mathcal{L} : \tilde{z}_{i,m,t} \text{ is finite}\}$ of cardinality $k_{i,t} = |\mathcal{M}_{i,t}| \ge 1$ (`NaN` if $k_{i,t} = 0$):
     $$c_{i,t} = \frac{\sum_{m \in \mathcal{M}_{i,t}} \tilde{z}_{i,m,t}}{\sqrt{\mathbf{1}_{\mathcal{M}_{i,t}}^\top \hat{R}_{t,\mathcal{M}_{i,t}} \mathbf{1}_{\mathcal{M}_{i,t}}}} \cdot \sqrt{\frac{k_{i,t}}{4}}$$
   - Apply a second pass of $\mathcal{E}_5$ to the composite $c_{i,t}$ to remove cross-sector differences in within-sector leg correlation:
     $$\texttt{S1\_value\_eb\_ns}_{i,t} = \mathcal{E}_5(c_{i,t} \mid s)$$

---

### 3.2 Method 2 (`M2`): Sovereign-Spread-Conditioned Real Economic Value (`M2_value_real_spread_sn`)

Replaces nominal pre-2023Q4 TTM flows, stale historical-cost balance-sheet net debt, levered `S/P`, and below-the-line FX/IAS 29 monetary noise with universal CPI constant-purchasing-power flows, unlevered `S/EV`, and a real debt-service charge priced off Turkey's live USD sovereign Eurobond curve:

1. **Strictly PIT CPI index $I(m)$ and staleness inflation factor $\Pi_{p \to t}$:**  
   From `data/research/macro_monthly.parquet`, construct the monthly CPI index $I(m) = \prod_{\tau \le m}(1 + \texttt{cpi\_mom}_\tau / 100)$ indexed by calendar month `Period("M")`.  
   Because TÜİK publishes month-$t$ CPI on the 3rd business day of month $t+1$, define the latest CPI month strictly known on month-end decision date $t$ as:
   $$m^*(t) = \text{Period}(t, \texttt{"M"}) - 1$$
   For stock $i$'s active statement period $p = \texttt{stmt\_period}_{i,t}$ (joined from `data/research/quarterly.parquet` on `(ticker, period == stmt_period)`, which satisfies `available_at <= t` by panel construction) with period-end calendar month $m_p = \text{Period}(\texttt{period\_end}_{i,p}, \texttt{"M"})$, define:
   $$\Pi_{p \to t} = \frac{I(\max(m_p,\, m^*(t)))}{I(m_p)}$$

2. **Universal constant period-$p$-end purchasing-power TTM flows ($\text{TTM}^{\text{real}}_{\text{rev},i,p}$, $\text{TTM}^{\text{real}}_{\text{op},i,p}$):**  
   In `data/research/quarterly.parquet`, sort each ticker's rows by `period_end`:
   - **Nominal GAAP statements (`period < "2023Q4"`):** Require 4 consecutive quarterly rows $p-3, p-2, p-1, p$ whose consecutive `period_end` differences all lie in $[80, 100]$ days (matching `core/pit_panel.py::quarterly_table`). For each discrete quarter $s \in \{p-3, p-2, p-1, p\}$ with quarter-end month $m_s = \text{Period}(\texttt{period\_end}_s, \texttt{"M"})$, let $\overline{I}_s = \frac{1}{3}\big(I(m_s - 2) + I(m_s - 1) + I(m_s)\big)$ be the arithmetic mean of the 3 monthly CPI index levels inside calendar quarter $s$. Define:
     $$\text{TTM}^{\text{real}}_{\text{rev},i,p} = \sum_{j=0}^{3} \texttt{q\_revenue}_{i,p-j} \cdot \frac{I(m_p)}{\overline{I}_{p-j}}, \qquad \text{TTM}^{\text{real}}_{\text{op},i,p} = \sum_{j=0}^{3} \texttt{q\_op\_profit}_{i,p-j} \cdot \frac{I(m_p)}{\overline{I}_{p-j}}$$
     (If the 4-quarter consecutive gap check fails or any of the 4 quarterly flows is `NaN`, the corresponding $\text{TTM}^{\text{real}}$ is `NaN`.)
   - **IAS 29 statements (`period >= "2023Q4"`):** Use `ttm_revenue` and `ttm_op_profit` directly from `quarterly.parquet` (already in constant period-$p$-end purchasing power via `C1` + `bridge_ttm` with vendor re-expression undone).

3. **Strictly PIT Turkey USD Sovereign Eurobond Yield $y^{\text{USD}}_{\text{TR},t}$:**  
   From `data/research/eurobond_monthly.parquet`, for each decision month-end $t$, take the latest available monthly snapshot on or before $t$, filter to bonds with remaining maturity $3.0 \le (\texttt{maturity} - \texttt{date})/365.25 \le 30.0$ years (matching `core/sovereign_spread.py::median_spread`), and compute:
   $$y^{\text{USD}}_{\text{TR},t} = \frac{1}{100} \cdot \operatorname{median}_{b \in \mathcal{B}_t}\!\big(\texttt{yield}_{b,t}\big)$$

4. **Four inflation-consistent, sovereign-spread-conditioned valuation ratios:**  
   Let $\text{Eq}_{i,p} = \texttt{equity\_parent}_{i,p}$ (falling back to $\texttt{equity}_{i,p}$ when `equity_parent` is null, matching `pit_panel._equity`), and let $\text{NetDebt}_{i,p} = \texttt{fin\_debt}_{i,p} - \texttt{cash}_{i,p}$ (`NaN` if either `fin_debt` or `cash` is `NaN`, matching `pit_panel.value_ratios`). Define inflation-adjusted Enterprise Value:
   $$\text{EV}^{\text{real}}_{i,t} = \texttt{mcap}_{i,t} + \Pi_{p \to t}\cdot \text{NetDebt}_{i,p}$$
   Compute the four ratios:
   1. $\text{bm}^{\text{real}}_{i,t} = \dfrac{\Pi_{p \to t}\cdot \text{Eq}_{i,p}}{\texttt{mcap}_{i,t}}$ if $\text{Eq}_{i,p} > 0$ and $\texttt{mcap}_{i,t} > 0$, else `NaN`;
   2. $\text{real\_ep}^{\text{sp}}_{i,t} = \dfrac{\Pi_{p \to t}\cdot \big(\text{TTM}^{\text{real}}_{\text{op},i,p} - y^{\text{USD}}_{\text{TR},t}\cdot \text{NetDebt}_{i,p}\big)}{\texttt{mcap}_{i,t}}$ if $\text{TTM}^{\text{real}}_{\text{op},i,p}, \text{NetDebt}_{i,p}$ are finite and $\texttt{mcap}_{i,t} > 0$, else `NaN`;
   3. $\text{sev}^{\text{real}}_{i,t} = \dfrac{\Pi_{p \to t}\cdot \text{TTM}^{\text{real}}_{\text{rev},i,p}}{\text{EV}^{\text{real}}_{i,t}}$ if $\text{EV}^{\text{real}}_{i,t} > 0$ and $\text{TTM}^{\text{real}}_{\text{rev},i,p}$ is finite, else `NaN`;
   4. $\text{ey}^{\text{real}}_{i,t} = \dfrac{\Pi_{p \to t}\cdot \text{TTM}^{\text{real}}_{\text{op},i,p}}{\text{EV}^{\text{real}}_{i,t}}$ if $\text{EV}^{\text{real}}_{i,t} > 0$ and $\text{TTM}^{\text{real}}_{\text{op},i,p}$ is finite, else `NaN`.

5. **Cross-sectional standardization & sector neutralization (identical to `R0`):**  
   Within each decision month $t$ on the liquid universe:
   - Winsorize and standardize each of the 4 ratios via `fb.winsorize_z(..., lo=0.01, hi=0.99)`.
   - Take the equal-weighted row mean across available leg z-scores (`mean(axis=1, skipna=True)`).
   - Demean within sector via `M2_value_real_spread_sn = fb.sector_neutralize(df, raw_col, min_n=5)`.

---

### 3.3 Method 3 (`FV1`): Inflation-Consistent Residual Operating Income Valuation (`FV1_reoi_ev_sn`)

Values the operating enterprise via a closed-form 5-year Feltham-Ohlson (1995) / Penman (2013) Residual Operating Income model (`V_ReOI / EV`) with a regime-consistent Fisher operating hurdle rate $r_{w,i,t}$, normalized present-value weights, and within-regime cohort standardization across the 2024 IAS 29 filing transition:

1. **Enterprise accounting inputs (`quarterly.parquet` joined on `(ticker, period == stmt_period)`):**  
   Let $\text{Eq}_{i,t} = \texttt{equity\_parent}_{i,t}$ (fallback $\texttt{equity}_{i,t}$), $\text{FD}_{i,t} = \texttt{fin\_debt}_{i,t}$, $\text{Cash}_{i,t} = \texttt{cash}_{i,t}$, and $\text{OP}_{i,t} = \texttt{ttm\_op\_profit}_{i,t}$:
   $$\text{NOA}_{i,t} = \text{Eq}_{i,t} + \text{FD}_{i,t} - \text{Cash}_{i,t}$$
   $$\text{EV}_{i,t} = \texttt{mcap}_{i,t} + \text{FD}_{i,t} - \text{Cash}_{i,t}$$
   $$\text{NOPAT}_{i,t} = (1 - \tau)\cdot \text{OP}_{i,t}, \qquad \tau = 0.25$$
   (Fixed statutory corporate tax rate $\tau = 0.25$ from `config/equity_risk_premium.yaml`; if any of $\text{Eq}, \text{FD}, \text{Cash}, \text{OP}, \texttt{mcap}$ is `NaN` or $\text{EV}_{i,t} \le 0$, output is `NaN`.)

2. **Strictly PIT inflation-consistent operating hurdle rate $r_{w,i,t}$:**  
   From `data/research/macro_monthly.parquet`, take the month-$t$ TCMB policy rate $\texttt{policy}_t$ (known in real time at month-end $t$) and the 1-month lagged year-over-year CPI inflation rate $\pi_{t-1} = \texttt{cpi\_yoy}_{t-1} / 100$ (at month $m^*(t) = \text{Period}(t, \texttt{"M"}) - 1$, respecting TÜİK's 3-business-day release lag), with fixed $\text{ERP} = 0.05$ (`config/equity_risk_premium.yaml`):
   $$r_{w,t}^{\text{nom}} = \frac{\texttt{policy}_t}{100} + 0.05, \qquad r_{w,t}^{\text{real}} = \max\!\left(0.05,\; \frac{1 + r_{w,t}^{\text{nom}}}{1 + \pi_{t-1}} - 1\right)$$
   Match the hurdle rate to the accounting unit of stock $i$'s active statement $\texttt{stmt\_period}_{i,t}$:
   $$r_{w,i,t} = \begin{cases} r_{w,t}^{\text{nom}}, & \text{if } \texttt{stmt\_period}_{i,t} < \texttt{"2023Q4"} \text{ (nominal GAAP)}, \\ r_{w,t}^{\text{real}}, & \text{if } \texttt{stmt\_period}_{i,t} \ge \texttt{"2023Q4"} \text{ (IAS 29 constant purchasing power)}. \end{cases}$$

3. **Feltham-Ohlson 5-year Residual Operating Income value & convex PV-weight normalization ($T = 5$):**  
   Let $A(r_{w,i,t}, 5) = \dfrac{1 - (1 + r_{w,i,t})^{-5}}{r_{w,i,t}}$ be the 5-year annuity factor and $\text{ReOI}_{i,t} = \text{NOPAT}_{i,t} - r_{w,i,t}\cdot \text{NOA}_{i,t}$:
   $$V^{\text{ReOI}}_{i,t} = \text{NOA}_{i,t} + A(r_{w,i,t}, 5)\cdot \text{ReOI}_{i,t} = (1 + r_{w,i,t})^{-5}\,\text{NOA}_{i,t} + A(r_{w,i,t}, 5)\,\text{NOPAT}_{i,t}$$
   Normalize $V^{\text{ReOI}}_{i,t} / \text{EV}_{i,t}$ by the total present-value multiplier $(1 + r_{w,i,t})^{-5} + (1 - \tau)\,A(r_{w,i,t}, 5)$ so that the weights on $\text{NOA}/\text{EV}$ and $\text{ey} = \text{OP}/\text{EV}$ sum to $1$ in every regime (eliminating the $2.58\times$ annuity scale jump during the early-2024 mixed-filing transition while remaining a positive scalar constant in every single-regime month):
   $$\widetilde{\text{reoi\_ev}}_{i,t} = \begin{cases} \dfrac{V^{\text{ReOI}}_{i,t} / \text{EV}_{i,t}}{(1 + r_{w,i,t})^{-5} + (1 - \tau)\,A(r_{w,i,t}, 5)}, & \text{if } \text{EV}_{i,t} > 0 \text{ and all inputs finite,} \\[8pt] \text{NaN}, & \text{otherwise.} \end{cases}$$

4. **Within-regime cross-sectional standardization & sector neutralization:**  
   Let $g_{i,t} = \mathbb{I}(\texttt{stmt\_period}_{i,t} \ge \texttt{"2023Q4"}) \in \{0, 1\}$ denote the active accounting regime cohort. Within each decision month $t$ on the liquid universe:
   - If **both** cohorts $g = 0$ and $g = 1$ have at least `min_n = 5` finite $\widetilde{\text{reoi\_ev}}_{i,t}$ observations in month $t$, compute `reoi_ev_z = fb.winsorize_z(reoi_ev_tilde, lo=0.01, hi=0.99)` separately within each $(t, g_{i,t})$ cohort.
   - Otherwise (including 100% of Discovery `2013-04..2020-12` and all single-regime Holdout months), compute `reoi_ev_z = fb.winsorize_z(reoi_ev_tilde, lo=0.01, hi=0.99)` across the full month-$t$ cross-section.
   - Apply sector neutralization: `FV1_reoi_ev_sn = fb.sector_neutralize(df, "reoi_ev_z", min_n=5)`.

---

## 4. Planned Output File and Reporting Schema

- **Runner:** `python scripts/research_valuation_round1.py`
- **Primary output file:** `data/reports/research_valuation_round1_2026-11-22.json`
- **Required contents of `data/reports/research_valuation_round1_2026-11-22.json`:**
  1. `as_of`, `months`, `n_discovery` (93), `n_holdout` (68), `n_ias29` (28), `trial_ledger_N_sel` (89).
  2. `primary_lag75`:
     - `portfolio_simulation`: for `R0`, `S1_value_eb_ns`, `M2_value_real_spread_sn`, `FV1_reoi_ev_sn` across `discovery`, `holdout`, `ias29_2024_05_plus`, and `full` — reporting `vs_ew_net` (annualised %/yr, NW $t$), `vs_ew_gross` (annualised %/yr, NW $t$), `paired_diff_vs_R0` ($D$ annualised %/yr, monthly mean, NW $t(D)$ with 6 lags), `cagr_tl_pct`, `cagr_usd_pct`, `cagr_real_pct`, `max_dd_tl_pct`, `max_dd_usd_pct`, `holdout_dd_usd_diff_vs_R0_pp`, `turnover_pct`, `cost_ann_pct`, `avg_names`, and `coverage_pct`.
     - `rank_ic`: monthly Spearman Rank-IC against `fwd_ret_1m` (and paired $\Delta\text{IC}$ vs `R0`, NW $t$ with 6 lags) across `discovery`, `holdout`, `ias29_2024_05_plus`.
     - `switcher_analysis`: mean Spearman rank correlation vs `R0`, mean top-20% overlap %, mean switches/month, and equal-weighted switcher spread (`entrants_minus_dropouts` %/yr, NW $t$).
     - `dsr_at_N_sel_89`: Deflated Sharpe Ratio (`rs.deflated_sharpe`) at `N_sel = 89` ($T = 161$, cross-variant $V[\widehat{\text{SR}}]$) for `R0` and each of the 3 candidates on full-sample net active returns (`port - ew_net`).
     - `verdicts`: per-method boolean checks (`disc_D_pos`, `disc_t_ge_1`, `hold_D_pos`, `hold_t_ge_2`, `hold_dd_usd_ok`) and final `"PASS"` / `"FAIL"` string under the verbatim FIXED PASS RULE.
  3. `sensitivity_kapdates`: descriptive re-run of the exact same metrics on `data/research/factors_monthly_kapdates.parquet`.

---

## Results

(Appended on 2026-11-22 after running the study; all pre-registered sections above are unchanged.)

- **Runner:** `.venv/bin/python scripts/research_valuation_round1.py`
- **Output report:** `data/reports/research_valuation_round1_2026-11-22.json`
- **Panel span:** `2013-04-30` to `2026-09-30` (161 completed monthly return periods: **93 Discovery** `2013-04..2020-12`, **68 Holdout** `2021-01..2026-08`, **28 IAS 29** `2024-05..2026-08`).
- **Updated Trial Ledger:** `N_sel = 89` (`86 + 3` stock-selection trials in `data/research/trial_ledger.json`; cross-variant monthly Sharpe variance $V[\widehat{\text{SR}}] = 0.02335$, expected maximum null monthly Sharpe $\text{SR}_0 = 0.3804$).

### 1. Primary Evaluation (`factors_monthly.parquet`, `lag75`, 1M TL real capital, base costs, next-close fills)

#### 1.1 Costed Portfolio Simulation & Verbatim Fixed Pass Rule Verdicts

| Method | Window | Active vs `EW net` %/yr ($t$) | Active vs `EW gross` %/yr ($t$) | Paired $D$ vs `R0` %/yr ($t$) | CAGR TL / USD / Real % | Max DD TL / USD % | Holdout $\Delta\text{DD}_{\text{USD}}$ vs `R0` | 1-Way Turnover % | Cost %/yr | Avg Names (Cov %) | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **`R0` (`value_sn`)** | Discovery (93m) | +5.14 (+1.97) | +4.37 (+1.67) | — | 34.60 / 12.26 / 20.65 | −26.0 / −56.6 | — | 21.4% | 1.92% | 42.7 (100.0%) | Baseline |
| | Holdout (68m) | +10.14 (+2.97) | +9.36 (+2.74) | — | 49.69 / 7.02 / 2.59 | −25.3 / **−35.4** | 0.0 pp | 19.3% | 1.42% | 59.2 (100.0%) | |
| | IAS 29 (28m) | +2.19 (+0.56) | +1.33 (+0.34) | — | 8.75 / −9.15 / −17.66 | −18.6 / −25.1 | — | 18.4% | 1.43% | 68.7 (100.0%) | |
| | Full (161m) | +7.25 (+3.38) | +6.48 (+3.01) | — | 40.78 / 10.02 / 12.66 | −26.0 / −56.6 | — | 20.5% | 1.71% | 49.7 (100.0%) | |
| **`S1` (`S1_value_eb_ns`)** | Discovery (93m) | +3.00 (+0.94) | +2.24 (+0.70) | **−2.13 (−1.39)** | 32.03 / 10.12 / 18.34 | −26.9 / −54.9 | — | 20.7% | 1.79% | 42.7 (100.0%) | **`FAIL`** |
| | Holdout (68m) | +9.35 (+2.34) | +8.58 (+2.15) | **−0.78 (−0.52)** | 48.83 / 6.40 / 2.00 | −24.7 / **−35.2** | **+0.2 pp** (OK) | 19.5% | 1.43% | 59.2 (100.0%) | |
| | IAS 29 (28m) | +1.94 (+0.40) | +1.08 (+0.22) | −0.25 (−0.12) | 8.59 / −9.28 / −17.78 | −15.6 / −23.4 | — | 18.7% | 1.41% | 68.7 (100.0%) | |
| | Full (161m) | +5.69 (+2.20) | +4.92 (+1.90) | −1.56 (−1.45) | 38.88 / 8.53 / 11.14 | −26.9 / −54.9 | — | 20.2% | 1.63% | 49.7 (100.0%) | |
| **`M2` (`M2_value_real_spread_sn`)** | Discovery (93m) | **+5.58 (+1.70)** | **+4.82 (+1.46)** | **+0.45 (+0.25)** | 35.31 / 12.85 / 21.28 | −25.8 / −55.8 | — | 20.3% | 1.84% | 42.7 (100.0%) | **`FAIL`** |
| | Holdout (68m) | +7.62 (+2.19) | +6.84 (+1.97) | **−2.52 (−1.69)** | 45.96 / 4.35 / 0.03 | −24.6 / **−36.4** | **−1.0 pp** (OK) | 19.0% | 1.41% | 59.2 (100.0%) | |
| | IAS 29 (28m) | −0.17 (−0.04) | −1.03 (−0.25) | −2.36 (−0.92) | 6.31 / −11.19 / −19.51 | −18.0 / −24.7 | — | 18.3% | 1.46% | 68.7 (100.0%) | |
| | Full (161m) | +6.44 (+2.66) | +5.68 (+2.34) | −0.80 (−0.62) | 39.71 / 9.18 / 11.80 | −25.8 / −55.8 | — | 19.8% | 1.66% | 49.7 (100.0%) | |
| **`FV1` (`FV1_reoi_ev_sn`)** | Discovery (93m) | +3.83 (+1.21) | +3.07 (+0.97) | **−1.30 (−0.74)** | 33.12 / 11.03 / 19.32 | −26.5 / −53.2 | — | 20.9% | 1.93% | 41.7 (97.61%) | **`FAIL`** |
| | Holdout (68m) | +8.55 (**+3.13**) | +7.77 (+2.83) | **−1.59 (−0.82)** | 47.25 / 5.27 / 0.92 | −23.8 / **−37.8** | **−2.4 pp** (FAIL) | 20.2% | 1.55% | 58.8 (99.19%) | |
| | IAS 29 (28m) | **+3.73 (+0.89)** | **+2.87 (+0.67)** | **+1.55 (+0.51)** | 10.26 / −7.89 / −16.52 | −19.8 / −26.1 | — | 19.8% | 1.62% | 68.1 (99.00%) | |
| | Full (161m) | +5.83 (+2.63) | +5.06 (+2.27) | −1.42 (−1.09) | 38.92 / 8.56 / 11.17 | −26.5 / −53.2 | — | 20.6% | 1.77% | 48.9 (98.41%) | |

#### 1.2 Cross-Sectional Rank-IC and Top-20% Switcher Analysis (`lag75`)

| Method | Window | Rank-IC ($t$) | Paired $\Delta\text{IC}$ vs `R0` ($t$) | Mean Rank Corr vs `R0` | Mean Top-20% Overlap | Mean Switches / mo | Switcher Spread: Entrants − Dropouts %/yr ($t$) |
|---|---|---:|---:|---:|---:|---:|---:|
| **`R0` (`value_sn`)** | Discovery (93m) | +0.0558 (+5.52) | — | 1.0000 | 100.00% | 0.00 | — |
| | Holdout (68m) | +0.0734 (+4.85) | — | 1.0000 | 100.00% | 0.00 | — |
| | IAS 29 (28m) | +0.0344 (+2.30) | — | 1.0000 | 100.00% | 0.00 | — |
| **`S1` (`S1_value_eb_ns`)** | Discovery (93m) | **+0.0566 (+5.39)** | +0.0008 (+0.32) | 0.9143 | 78.15% | 9.32 | −12.77 (−1.62) |
| | Holdout (68m) | **+0.0793 (+4.90)** | **+0.0058 (+1.88)** | 0.9078 | 79.11% | 12.51 | 0.00 (0.00) |
| | IAS 29 (28m) | **+0.0363 (+2.19)** | +0.0019 (+0.40) | 0.9063 | 77.65% | 15.32 | +5.24 (+0.53) |
| **`M2` (`M2_value_real_spread_sn`)** | Discovery (93m) | +0.0555 (**+5.77**) | −0.0003 (−0.09) | 0.9273 | 82.47% | 7.48 | −3.33 (−0.29) |
| | Holdout (68m) | +0.0676 (+4.58) | −0.0058 (−1.54) | 0.9108 | 80.04% | 11.94 | −14.19 (−1.94) |
| | IAS 29 (28m) | +0.0332 (+2.42) | −0.0012 (−0.23) | 0.9001 | 78.66% | 14.57 | −5.96 (−0.63) |
| **`FV1` (`FV1_reoi_ev_sn`)** | Discovery (93m) | +0.0544 (**+6.47**) | −0.0014 (−0.46) | 0.8509 | 72.68% | 11.40 | −0.72 (−0.14) |
| | Holdout (68m) | +0.0666 (+4.43) | −0.0068 (−1.65) | 0.8588 | 72.29% | 16.49 | −4.32 (−0.71) |
| | IAS 29 (28m) | +0.0298 (+2.30) | −0.0046 (−0.56) | 0.8553 | 70.95% | 19.75 | +3.76 (+0.41) |

#### 1.3 Deflated Sharpe Ratio at `N_sel = 89` ($T = 161$ months, $V[\widehat{\text{SR}}] = 0.02335$, $\text{SR}_0 = 0.3804$)

| Method | Full-Sample Monthly $\widehat{\text{SR}}$ (vs `EW net`) | Annualised $\sqrt{12}\,\widehat{\text{SR}}$ | Skewness | Kurtosis | Null Hurdle $\text{SR}_0$ | DSR (`N_sel = 89`, `lag75`) | DSR (`N_sel = 89`, `kapdates`) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`R0` (`value_sn`)** | **0.2830** | **0.9803** | +0.5091 | 3.9113 | 0.3804 | **0.0986** | **0.1464** ($\widehat{\text{SR}} = 0.2976$) |
| **`S1` (`S1_value_eb_ns`)** | 0.2081 | 0.7209 | +0.8283 | 5.4636 | 0.3804 | **0.0099** | **0.0306** ($\widehat{\text{SR}} = 0.2380$) |
| **`M2` (`M2_value_real_spread_sn`)** | 0.2529 | 0.8761 | +0.1922 | 4.5511 | 0.3804 | **0.0540** | **0.0568** ($\widehat{\text{SR}} = 0.2554$) |
| **`FV1` (`FV1_reoi_ev_sn`)** | 0.2252 | 0.7801 | +0.1769 | 3.1985 | 0.3804 | **0.0241** | **0.0179** ($\widehat{\text{SR}} = 0.2163$) |

---

### 2. Sensitivity Evaluation (`factors_monthly_kapdates.parquet`, Actual KAP Publication Dates)

| Method | Discovery vs `EW net` %/yr ($t$) | Discovery Paired $D$ %/yr ($t$) | Holdout vs `EW net` %/yr ($t$) | Holdout Paired $D$ %/yr ($t$) | Holdout Max DD USD ($\Delta$ vs `R0`) | Rank-IC Disc / Hold ($t$) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| **`R0` (`value_sn`)** | +7.25 (+2.68) | — | +8.38 (+2.79) | — | −35.5% (0.0 pp) | +0.0571 (5.96) / +0.0748 (4.64) | Baseline |
| **`S1` (`S1_value_eb_ns`)** | +4.49 (+1.44) | −2.76 (−1.68) | **+9.44 (+2.31)** | **+1.06 (+0.67)** | **−33.6% (+1.9 pp)** | **+0.0592 (5.73) / +0.0815 (4.77)** | **`FAIL`** |
| **`M2` (`M2_value_real_spread_sn`)** | +7.04 (+2.18) | −0.21 (−0.11) | +6.08 (+1.95) | −2.30 (−1.84) | −37.4% (−1.9 pp) | +0.0573 (6.20) / +0.0660 (4.33) | **`FAIL`** |
| **`FV1` (`FV1_reoi_ev_sn`)** | +4.64 (+1.79) | −2.60 (−1.40) | +6.85 (+2.60) | −1.53 (−0.96) | −38.1% (−2.6 pp) | +0.0568 (7.28) / +0.0649 (4.13) | **`FAIL`** |

---

### 3. Interpretation and Verdict Summary

All **3 confirmatory candidates (`S1`, `M2`, `FV1`) classify as `FAIL`** under the fixed pass rule:
1. **`S1` (`S1_value_eb_ns`) — `FAIL`:** Blom rank-normal transformation + 2-stage Empirical-Bayes sector location/scale standardization improves broad cross-sectional Rank-IC across every window (`+0.0566` vs `+0.0558` in Discovery; `+0.0793` vs `+0.0734`, $\Delta\text{IC}\ t = +1.88$ in Holdout on `lag75`, and `+0.0815` vs `+0.0748`, $\Delta\text{IC}\ t = +1.98$ on `kapdates`, where Holdout net active return also improves by $D = +1.06\%/\text{yr}$ and USD max drawdown improves by $+1.9\text{ pp}$ to $-33.6\%$). However, as anticipated in `r1_proposal_statistical.md` Failure Mode #1, compressing right-tail deep-value convexity (`B/M`, `S/P`) and down-scaling high-dispersion sectors (REITs, Holdings) hurts top-quintile portfolio returns in Discovery ($D = -2.13\%/\text{yr}, t = -1.39$ on `lag75`; $-2.76\%/\text{yr}, t = -1.68$ on `kapdates`) and slightly in `lag75` Holdout ($D = -0.78\%/\text{yr}, t = -0.52$).
2. **`M2` (`M2_value_real_spread_sn`) — `FAIL`:** In Discovery (`lag75`), `M2` is the only method with positive paired active return over `R0` ($D = +0.45\%/\text{yr}, t = +0.25$, active vs `EW net` $+5.58\%/\text{yr}$ vs $+5.14\%/\text{yr}$), but its Discovery $t$-statistic ($0.25 < 1.0$) does not clear the hurdle and its Holdout return lags `R0` by $D = -2.52\%/\text{yr}$ ($t = -1.69$). As noted in `r1_proposal_macro.md` Failure Modes #1, #3, and #4, charging the USD Eurobond sovereign yield (`~9–10%`) to domestic TL debt during 2021–2023 (when domestic real TL borrowing rates were deeply negative) and delevering `S/P` into `S/EV` while dropping `ttm_ni_parent` gave up strong Holdout equity-leverage and below-EBIT gains.
3. **`FV1` (`FV1_reoi_ev_sn`) — `FAIL`:** Feltham-Ohlson 5-year Residual Operating Income achieves the highest Discovery Rank-IC $t$-statistic ($t = 6.47$ on `lag75`, $t = 7.28$ on `kapdates`), the highest Holdout active return $t$-statistic vs `EW net` ($t = 3.13$, $+8.55\%/\text{yr}$), and a positive edge over `R0` in the `2024-05+` IAS 29 sub-window ($D = +1.55\%/\text{yr}, t = +0.51$, active vs `EW net` $+3.73\%/\text{yr}$ vs $+2.19\%/\text{yr}$). However, omitting the top-line `S/P` anchor in a 2-pillar (`NOA/EV`, `ey`) operating valuation loses $D = -1.30\%/\text{yr}$ ($t = -0.74$) in Discovery and $D = -1.59\%/\text{yr}$ ($t = -0.82$) across full Holdout, while worsening Holdout USD max drawdown by $2.4\text{ pp}$ ($-37.8\%$ vs $-35.4\%$, breaching the $2.0\text{ pp}$ guardrail).
4. **Live rule:** `config/live_rule.json` (`R0-2026-10-12`, plain `value_sn` top 20%) remains unchanged.


### Ledger note added at integration (2026-11-22)

This study and `free_float_preregistration.md` (FF1, 1 trial) were pre-registered in parallel on separate branches, each starting from N_sel = 86. After both are merged the ledger holds N_sel = 90. The DSR values above were computed at N_sel = 89; at 90 they are marginally lower and every verdict is unchanged (all three methods FAIL on the fixed pass rule, which does not depend on N_sel).
