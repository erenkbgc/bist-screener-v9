# Round 1 Valuation Proposal — Statistical / Cross-Sectional Quant

**Author role:** Statistical / Cross-Sectional Quant  
**Date:** 2026-11-22  
**Branch:** `agent/valuation`  
**Baseline to beat:** Live rule `R0-2026-10-12` — monthly top-20% equal-weighted non-financial portfolio by `value_sn` (`bm`, `ep`, `sp`, `ey`, 1%/99% winsorized cross-sectional z-scores, averaged and demeaned within sector with hard cliff `min_n = 5`) on the promoted point-in-time panel `data/research/factors_monthly.parquet` (lag75; `factors_monthly_kapdates.parquet` for KAP-date sensitivity).  
**Trial budget:** Current `N_sel = 86` (`data/research/trial_ledger.json`). Testing both proposals below adds **+2** to `N_sel` (`86 -> 88`), and DSR must be reported at the updated `N_sel` (PASS or FAIL).  
**Discipline check:** No backtests were run and no return columns (`fwd_ret_*`, `mom_12_1`, `str_1m`, `vol60`) were inspected. Existing `debate/` files (`r1_proposal_macro.md`, `r1_proposal_fundamental.md`) were read before drafting; our two proposals are strictly orthogonal to both the macro/numeraire methods (`M1`, `M2`) and accounting-formula methods (`FV1`, `FV2`).

---

## 0. Cross-Sectional Statistical Audit of `R0` (`value_sn`) — Non-Return Diagnostics

All prior failed stock-selection studies in `README.md` / `trial_ledger.json` are excluded a priori: no dividend yield, no learned IC weights, no additive/multiplicative `quality x value` blends, no low-vol/size/liquidity/free-float filters, no EV redefinition `E1`, no ST debt coverage filter `D1`, no timing/SMC overlays, no KAP red flags, no foreign ownership, and no leg-dropping (`V1`/`V2`).

Auditing purely the **non-return feature matrix** of the promoted PIT panel (`data/research/factors_monthly.parquet` after `liq_drop_pct = 0.30`, $N = 40{,}693$ stock-months across 162 months, median 230 stocks/month across 34 non-financial sectors) reveals **four structural statistical defects** in how `R0` transforms, neutralizes, and aggregates valuation information:

1. **Severe post-winsorization asymmetry and single-leg tail dominance:**  
   Raw valuation ratios in BIST are violently non-Gaussian (`bm` skew $+3.23$, kurt $20.1$; `sp` skew $+5.36$, kurt $46.5$; `ep` skew $-1.75$, kurt $64.5$; `ey` skew $+186.8$, kurt $36{,}447$). Because `bm` and `sp` are strictly positive while `ep` and `ey` are two-sided (27.1% and 17.5% negative, respectively), `fb.winsorize_z(0.01, 0.99)` leaves extreme asymmetric tails:
   - `sp_z`: p01 $= -0.90$, p99 $= +4.60$ (skew $+2.72$, kurt $9.17$);
   - `bm_z`: p01 $= -1.13$, p99 $= +3.56$ (skew $+1.69$, kurt $3.13$);
   - `ep_z`: p01 $= -3.77$, p99 $= +3.15$ (skew $-0.52$, kurt $6.17$).  
   In `value_z = mean(bm_z, ep_z, sp_z, ey_z)`, a single extreme right-tail `sp_z` ($+4.6$) or `bm_z` ($+3.6$) outlier overpowers negative earnings/operating-profit legs. Consequently, `value_sn_z` retains strong positive skew ($+0.774$, kurt $+3.338$), and **10.0%** of `R0`'s top-20% picks are loss-makers (`ep <= 0`; **5.6%** have `ey <= 0`).
2. **Global-before-sector standardization + unscaled sector demeaning:**  
   `R0` standardizes each leg across the *entire market* first, averages them, and then *only subtracts* the sector mean (`within = col - mean_s`). Because cross-sector level dispersion dominates `sp` and `bm`, global standardization compresses within-sector variance for tight industrial sectors while leaving massive within-sector dispersion in financial-adjacent/asset-heavy sectors. Across sectors with $n_{s,t} \ge 5$, within-sector $\text{Std}(\texttt{value\_sn\_z})$ varies by **nearly $5\times$**: from `0.22–0.32` in `Madencilik`, `Ambalaj`, `Taş, Toprak, Çimento`, and `İmalat` (`0.37`) up to `0.79` in `Holding`, `0.84` in `Gayrimenkul` (REITs), and `1.02` in `Girişim Sermayesi`. As a result, `R0` is **not genuinely sector-neutral in portfolio selection**: its top-20% selection rate is **31.3%** for REITs and **26.7%** for Holdings, versus only **15.4%** for `İmalat`, **14.6%** for `Kimya ve Plastik`, and **14.1%** for `Taş, Toprak, Çimento` (cross-sector SD of top-20% rate across the 16 large sectors $= 0.0510$). Yet Brinson attribution (`point_in_time_baseline_2026-11-22.md`) proved 100% of `R0`'s edge comes from **within-sector selection** ($+10.68\%/\text{yr}, t = 2.89$), not sector tilts ($+0.88\%/\text{yr}, t = 0.92$).
3. **Hard discontinuity at `min_n = 5` and unshrunk small-sector estimation noise:**  
   **17.1%** of all liquid stock-months sit in sectors with $n_{s,t} < 5$ and receive *zero* sector neutralization (falling back abruptly to market mean, causing small structural-value sectors like `Cam, Seramik, Porselen` to hit a **38.0%** top-20% rate). Another **22.1%** sit in sectors with $5 \le n_{s,t} \le 9$ (together **39.2%** of the panel), where subtracting an unshrunk 5-to-9-stock sample mean of a skewed composite injects high $\sigma_s^2 / n_s$ estimation error and lets one extreme peer distort every other peer in that sector.
4. **Unconditioned raw multiples vs. market-implied cross-sectional pricing:**  
   `R0` treats raw cheapness identically whether a low multiple reflects genuine mispricing or weak fundamentals (low profitability, weak margins, high net debt) — and `R0`'s survivorship drag ($-1.8$ to $-2.3\%/\text{yr}$ in discovery) came from delisted value traps while still listed (`-1.39%/mo` active). Conversely, naive `quality x value` overlays failed because adding standalone quality buys *expensive* high-profitability stocks. A **cross-sectional fundamental pricing regression** solves this without touching returns: it prices each firm's contemporaneous fundamental profile against peers and ranks purely on the **mispricing residual** (orthogonal to fundamentals by construction).

The two proposals below isolate these two distinct statistical paradigms cleanly: **S1** fixes defects (1)–(3) on the exact four `R0` multiples; **S2** directly implements paradigm (4) via scale-invariant robust regularized cross-sectional valuation regression.

---

## Method S1: Empirical-Bayes Sector-Standardized Normal-Score Value (`S1_value_eb_ns`)

### 1.1 Exact Formula

On each month-end rebalance date $t$, take the exact same liquid non-financial cross-section as `R0` (`tlvol60 > 0`, drop bottom 30% of `tlvol60`, `min_names = 30`), with the four PIT ratios $m \in \mathcal{L} = \{\text{bm}, \text{ep}, \text{sp}, \text{ey}\}$ and sector label $s(i)$.

**Step 1 — Blom rank-based inverse normal transformation (per leg, month $t$):**  
For each leg $m \in \mathcal{L}$ with $N_{m,t} \ge 3$ finite observations, compute tie-averaged ascending mid-ranks $r_{i,m,t} \in [1, N_{m,t}]$ (higher ratio $\Rightarrow$ higher rank) and map to Blom (1958) expected standard-normal order statistics:
$$u_{i,m,t} = \Phi^{-1}\!\left(\frac{r_{i,m,t} - \tfrac{3}{8}}{N_{m,t} + \tfrac{1}{4}}\right)$$
Missing values remain `NaN`.

**Step 2 — Empirical-Bayes (Hierarchical Random-Effects) sector location & scale operator $\mathcal{E}_{\nu_0}(\cdot \mid s)$:**  
For any cross-sectional score vector $v_{i,t}$ with $N_t \ge 5$ finite values distributed across $K_t$ sectors (sector counts $n_{s,t}$, sample means $\bar{v}_{s,t}$, unbiased sample variances $s^2_{s,t}$ for $n_{s,t} \ge 2$, grand mean $\bar{v}_{\cdot,t}$):
1. **Pooled within-sector variance (ANOVA MSW):**
   $$\hat{\sigma}^2_{W,t} = \frac{\sum_{s:\, n_{s,t} \ge 2} (n_{s,t} - 1)\, s^2_{s,t}}{\sum_{s:\, n_{s,t} \ge 2} (n_{s,t} - 1)}$$
2. **Between-sector variance component (unbalanced ANOVA Method-of-Moments / DerSimonian-Laird):**
   $$\text{MSB}_t = \frac{1}{K_t - 1}\sum_{s=1}^{K_t} n_{s,t}\,(\bar{v}_{s,t} - \bar{v}_{\cdot,t})^2, \qquad n_{0,t} = \frac{1}{K_t - 1}\!\left(N_t - \frac{\sum_s n_{s,t}^2}{N_t}\right)$$
   $$\hat{\tau}^2_{B,t} = \max\!\left(0,\; \frac{\text{MSB}_t - \hat{\sigma}^2_{W,t}}{n_{0,t}}\right)$$
   (If $K_t \le 1$ or $n_{0,t} \le 0$, set $\hat{\tau}^2_{B,t} = 0$.)
3. **EB shrunk sector mean (exact James-Stein / BLUP posterior mean):**
   $$w_{s,t} = \frac{n_{s,t}\,\hat{\tau}^2_{B,t}}{n_{s,t}\,\hat{\tau}^2_{B,t} + \hat{\sigma}^2_{W,t}} \in [0, 1), \qquad \hat{\mu}^{\text{EB}}_{s,t} = \bar{v}_{\cdot,t} + w_{s,t}\,(\bar{v}_{s,t} - \bar{v}_{\cdot,t})$$
4. **EB shrunk within-sector standard deviation (Inverse-Gamma conjugate shrinkage with fixed prior df $\nu_0 = 5$):**
   $$\hat{\sigma}^{\text{EB}}_{s,t} = \sqrt{\frac{\max(n_{s,t} - 1, 0)\, s^2_{s,t} + \nu_0\,\hat{\sigma}^2_{W,t}}{\max(n_{s,t} - 1, 0) + \nu_0}}, \qquad \nu_0 = 5$$
   (with convention $0 \cdot s^2_{s,t} := 0$ when $n_{s,t} = 1$, giving $\hat{\sigma}^{\text{EB}}_{s,t} = \hat{\sigma}_{W,t}$).
5. **Operator output:**
   $$\mathcal{E}_{\nu_0}(v_{i,t} \mid s) = \frac{v_{i,t} - \hat{\mu}^{\text{EB}}_{s(i),t}}{\hat{\sigma}^{\text{EB}}_{s(i),t}}$$

Apply $\mathcal{E}_5$ to each Blom-transformed leg **before** aggregation:
$$\tilde{z}_{i,m,t} = \mathcal{E}_5(u_{i,m,t} \mid s), \qquad m \in \{\text{bm}, \text{ep}, \text{sp}, \text{ey}\}$$

**Step 3 — Correlation-aware, variance-preserving, reliability-shrunk composite + second-stage EB sector standardization:**  
1. Estimate the $4 \times 4$ month-$t$ pairwise cross-sectional correlation matrix $\hat{R}^{\text{raw}}_t$ of $(\tilde{z}_{\cdot,\text{bm},t}, \tilde{z}_{\cdot,\text{ep},t}, \tilde{z}_{\cdot,\text{sp},t}, \tilde{z}_{\cdot,\text{ey},t})$ (fill any missing off-diagonal with $0$, diagonal $= 1$) and apply minimal positive-definite shrinkage $\hat{R}_t = 0.90\,\hat{R}^{\text{raw}}_t + 0.10\,I_4$.
2. For each stock $i$ with observed leg subset $\mathcal{M}_{i,t} \subseteq \mathcal{L}$ of size $k_{i,t} = |\mathcal{M}_{i,t}| \ge 1$ (`NaN` if $k_{i,t} = 0$):
   $$c_{i,t} = \frac{\sum_{m \in \mathcal{M}_{i,t}} \tilde{z}_{i,m,t}}{\sqrt{\mathbf{1}_{\mathcal{M}_{i,t}}^\top \hat{R}_{t,\mathcal{M}_{i,t}} \mathbf{1}_{\mathcal{M}_{i,t}}}} \cdot \sqrt{\frac{k_{i,t}}{4}}$$
3. Apply a second pass of $\mathcal{E}_5$ to the composite $c_{i,t}$ to neutralize cross-sector differences in within-sector leg correlations:
   $$S^{(1)}_{i,t} = \mathcal{E}_5(c_{i,t} \mid s)$$
4. **Portfolio rule (identical to `R0`):** Hold the monthly top 20% (`rank(ascending=False, pct=True) <= 0.20`), equal-weighted, evaluated in `scripts/research_portfolio_backtest.py` (1M TL real capital, base costs, next-close fills).

*Fixed structural priors (zero return-fitted parameters):* Blom constants $(3/8, 1/4)$ are exact normal order-statistic constants; $\nu_0 = 5$ matches `R0`'s existing `MIN_SECTOR_N = 5` peer scale without a discontinuity; equal nominal weights across all 4 legs preserve `R0`'s economic balance; $0.10\,I_4$ guarantees positive-definiteness of $\hat{R}_t$.

### 1.2 Verified PIT Inputs

- **100% identical to `R0`** — zero new data feeds, zero new raw-file parsing, trivial live drop-in replacement for `core/ranking.py::_score_pool` (after testing):
  - `data/research/factors_monthly.parquet` (primary) and `factors_monthly_kapdates.parquet` (KAP-date sensitivity): `date`, `ticker`, `sector`, `tlvol60`, `bm`, `ep`, `sp`, `ey`.
- **Non-return cross-sectional diagnostics on the promoted PIT panel ($N = 40{,}693$ liquid stock-months):**
  - Coverage: **100.0%** (identical to `R0`).
  - Distribution: skewness drops from $+0.774$ (`R0`) to **$+0.023$** (`S1`); excess kurtosis drops from $+3.338$ to **$-0.540$**.
  - Sector neutrality (16 large sectors with median $n_{s,t} \ge 5$, covering 78.5% of stock-months): cross-sector SD of top-20% selection rate falls **31%** from `0.0510` (`R0`, range `11.1%–31.3%`) to **`0.0352`** (`S1`, range `12.0%–24.3%`; `Holding` `26.7% -> 21.4%`, `Gayrimenkul` `31.3% -> 24.3%`, `İmalat` `15.4% -> 21.4%`, `Taş, Toprak, Çimento` `14.1% -> 19.1%`).
  - Differentiation & turnover: Spearman rank correlation vs `R0` $= 0.9115$; top-20% overlap vs `R0` $= \mathbf{78.6\%}$ (~21% monthly switcher differential); monthly top-20% turnover **falls** from `16.68%` (`R0`) to **`16.39%`** (`S1`).
  - Automatic value-trap reduction (with *zero* quality/profitability factor added): top-20% loss-maker share (`ep <= 0`) falls nearly $3\times$ from **10.0%** (`R0`) to **3.8%** (`S1`), `ey <= 0` falls $4\times$ from **5.6%** to **1.3%**, and median ROE of picks rises from `13.64%` to `15.44%`.
  - Size neutrality: rank correlation with `size = log(mcap)` is $+0.0827$ (virtually identical to `R0`'s $+0.0838$).

### 1.3 Rationale (Statistical / Cross-Sectional Mechanism)

1. **Symmetrizing legs eliminates single-leg outlier traps automatically:** Because `ep` and `ey` are symmetric/left-skewed while `bm` and `sp` are right-skewed, `R0` lets one extreme `sp` or `bm` outlier (+4 SD) override deep losses (`ep < 0`, `ey < 0`). Blom normal scores put all four legs on identical $\mathcal{N}(0,1)$ marginals while preserving Gaussian tail resolution (unlike uniform percentile ranks $[0,1]$, which squash the top 5% against the 20th percentile). A stock must now be genuinely cheap across *multiple* valuation pillars rather than riding a single skewed ratio — cutting loss-makers in the top quintile by two-thirds without adding a single quality filter.
2. **Per-leg + two-stage EB sector standardization unlocks within-sector selection:** Brinson attribution showed `R0`'s entire return comes from within-sector selection, yet `R0` over-samples high-dispersion sectors (REITs, Holdings, Venture Capital) and starves tight-dispersion industrial sectors (`İmalat`, `Kimya`, `Çimento`). Standardizing *both location and scale* per leg via Empirical-Bayes shrinkage aligns every sector's effective dispersion and eliminates the `min_n = 5` discontinuity affecting 17.1% of rows, while *refusing* to over-adjust tiny pathological sectors (e.g., 3–4 bankrupt football clubs in `Spor`, where EB smoothly shrinks toward the market mean instead of forcing a quota).
3. **Reliability-shrunk missing-leg aggregation fixes incomplete-data tail bias:** Under naive `mean(axis=1)`, observing $k < 4$ legs (e.g., negative equity $\Rightarrow$ `bm = NaN`) inflates composite variance and pushes incomplete/distressed names into the extreme tails. Normalizing by $\sqrt{\mathbf{1}_{\mathcal{M}}^\top \hat{R}_{\mathcal{M}} \mathbf{1}_{\mathcal{M}}}$ stabilizes variance at 1 across every missingness pattern, and multiplying by $\sqrt{k/4}$ shrinks partial-data scores toward zero in proportion to missing information.
4. **IAS 29 & inflation-regime robustness:** Because Blom scores are strictly monotone-invariant, non-linear shifts in multiple dispersion across nominal-inflation vs. IAS 29 regimes cannot warp tail weights.

### 1.4 Failure Modes

1. **Loss of cardinal extremity signal ("deep value convexity"):** If BIST's value premium is disproportionately concentrated in extreme deep-value outliers (e.g., $B/M > 2.5$ or $S/P > 5.0$, which linear z-scores reward with $+3.5$ to $+4.6$ SDs whereas Blom normal scores compress to $+2.3$ to $+2.7$ SDs), rank-normalizing could dilute top-quintile upside in sharp value-rebound regimes (particularly in Discovery 2013–2020 or post-shock rallies).
2. **Under-weighting genuinely high-dispersion value sectors:** Scaling down the within-sector dispersion of `Gayrimenkul` (REITs, where `G0_value_sn` posted $+17.8\%/\text{yr}$ holdout spread in `financials_holdings_reits_preregistration.md`) and `Holding` increases allocation to tighter sectors (`İmalat`, `Çimento`, `Ambalaj`). If wide valuation dispersion inside REITs/Holdings reflects *genuinely wider mispricing* rather than mere noise, equalizing sector scales could sacrifice holdout alpha.
3. **High correlation with `R0` (`78.6%` overlap) limits paired-difference power:** Because `S1` keeps the exact same four underlying PIT ratios, the paired active-return tracking error $\sigma(D)$ against `R0` will be relatively small. While low tracking error can *help* $t(D)$ if the switcher spread is consistently positive, it also means small regime-specific drags (e.g., a few high-`bm` distressed cyclicals rebounding) could prevent `S1` from clearing $t(D) \ge 2.0$ in the 68-month holdout.
4. **Reliability shrinkage $\sqrt{k/4}$ penalizes legitimate 3-leg stocks:** Firms temporarily missing `fin_debt` or `sp` (4.3% of rows have $k = 3$) receive a $\sqrt{3/4} \approx 0.866$ multiplier; if missingness in a specific vendor line item is unrelated to distress, this shrinkage mildly under-ranks those names.

---

## Method S2: Scale-Invariant Huber-Ridge Cross-Sectional Fundamental Mispricing (`S2_fund_mispricing_hr`)

### 2.1 Exact Formula

Grounded in cross-sectional fundamental valuation theory — Wilcox (1984, *FAJ*), Rhodes-Kropf, Robinson & Viswanathan (2005, *JFE*), and Bartram & Grinblatt (2018, *JFE*, "Agnostic Fundamental Analysis Works") — `S2` estimates each month's **market-implied cross-sectional pricing law** using strictly contemporaneous PIT accounting fundamentals (zero historical returns!) and ranks stocks by their **fundamentals-adjusted mispricing residual**.

**Why asset-normalized $\ln(M/A)$ rather than raw $\ln(P/B)$ on $\text{ROE}$:**  
A non-return pre-audit of naive $\ln(P/B)$ regressed on `ROE`, `log(S/B)`, and `log(TA)` on the BIST panel revealed two severe econometric pathologies:
1. *Denominator coupling & loss-maker U-shape:* When book equity $B \to 0^+$ under losses, $M/B$ stays elevated via equity option value while $\text{ROE} = \text{NI}/B \to -\infty$ and $S/B \to +\infty$, causing OLS/Huber to fit a **negative** slope on negative `ROE` (positive in only 3.1% of months!) — predicting *higher* fair `P/B` for deeply unprofitable firms and turning the residual into a distressed value-trap magnet.
2. *Size-elasticity distortion:* Including $\ln(\text{TA})$ on the RHS of $\ln(P/B)$ yields a negative slope (positive in only 3.1% of months) because small speculative BIST stocks trade at higher multiples, mechanically tilting residuals toward small caps (rank corr with `size` $= -0.36$), which is dangerous given BIST's negative liquid-universe size IC in holdout (`-0.057, t = -2.45`).

Normalizing both market value and every fundamental driver by **Total Assets $A_{i,t}$** (`total_assets > 0` for **100.0%** of rows) cures both pathologies simultaneously: it guarantees exact **homogeneity of degree 1** in TL/CPI scale (removing currency/size bias without putting $\ln A$ on the RHS) and decouples profitability ratios from vanishing book equity.

**Step 1 — Strictly PIT asset-scaled target and 6 fundamental regressors (month $t$):**  
On the exact same monthly liquid non-financial universe (`tlvol60 >= 30th pct`, `min_names = 30`), join `quarterly.parquet` on `(ticker, stmt_period)` (`available_at <= t`). Let $A_{i,t} = \texttt{total\_assets}$, $B_{i,t} = \texttt{equity\_parent}$ (fallback `equity`, matching `pit_panel._equity`), $\text{NI}_{i,t} = \texttt{ttm\_ni\_parent}$ (fallback `ttm_net_income`, matching `pit_panel._ttm_net_income`), $S_{i,t} = \texttt{ttm\_revenue}$, $\text{GP}_{i,t} = \texttt{ttm\_gross\_profit}$, $\text{OP}_{i,t} = \texttt{ttm\_op\_profit}$, $\text{FD}_{i,t} = \texttt{fin\_debt}$, $\text{Cash}_{i,t} = \texttt{cash}$, and $M_{i,t} = \texttt{mcap}$.

Define the dependent variable (log market-cap-to-assets):
$$y_{i,t} = \ln\!\left(\frac{M_{i,t}}{A_{i,t}}\right)$$
and the 6 scale-invariant fundamental drivers $\mathbf{f}_{i,t} \in \mathbb{R}^6$:
1. **Equity capital cushion:** $f_{1,i,t} = \ln(B_{i,t} / A_{i,t})$ (requires $B_{i,t} > 0$)
2. **Asset turnover (sales intensity):** $f_{2,i,t} = \ln(S_{i,t} / A_{i,t})$ (requires $S_{i,t} > 0$)
3. **Operating return on assets:** $f_{3,i,t} = \text{OP}_{i,t} / A_{i,t}$
4. **Bottom-line return on assets:** $f_{4,i,t} = \text{NI}_{i,t} / A_{i,t}$
5. **Gross profitability on assets (Novy-Marx):** $f_{5,i,t} = \text{GP}_{i,t} / A_{i,t}$
6. **Net financial leverage:** $f_{6,i,t} = (\text{FD}_{i,t} - \text{Cash}_{i,t}) / A_{i,t}$

*(Strict `NaN` rule: any stock missing $y_{i,t}$ or any of $f_{1..6,i,t}$ — e.g. negative equity or missing TTM — is excluded from month-$t$'s regression and scored `NaN`; no silent zero-filling.)*

Within month $t$ (on the $N_t^{\text{reg}} \ge 30$ complete rows), winsorize each $f_{j,i,t}$ at the cross-sectional 1%/99% quantiles and standardize to zero mean and unit sample SD: $\tilde{f}_{j,i,t}$. Let $\mathbf{D}_{i,t} \in \{0,1\}^{K_t}$ be the one-hot sector indicator vector across the $K_t$ sectors present in month $t$, and form the design row $\mathbf{x}_{i,t} = [1,\; \tilde{\mathbf{f}}_{i,t}^\top,\; \mathbf{D}_{i,t}^\top]^\top \in \mathbb{R}^{1 + 6 + K_t}$.

**Step 2 — Robust Huber-Ridge cross-sectional pricing regression (month $t$):**  
Estimate the month-$t$ pricing parameter vector $\boldsymbol{\theta}_t = [\alpha_t,\; \boldsymbol{\beta}_t^\top,\; \boldsymbol{\gamma}_t^\top]^\top$ by minimizing the penalized Huber loss (zero penalty on intercept $\alpha_t$, isotropic $L_2$ Ridge shrinkage $\lambda_f = 5.0$ on the 6 standardized fundamental elasticities and $\lambda_s = 5.0$ on the $K_t$ sector fixed effects):
$$\hat{\boldsymbol{\theta}}_t = \arg\min_{\boldsymbol{\theta}} \left\{ \sum_{i=1}^{N_t^{\text{reg}}} \rho_{\delta_t}\!\big(y_{i,t} - \mathbf{x}_{i,t}^\top \boldsymbol{\theta}\big) + \frac{\lambda_f}{2}\|\boldsymbol{\beta}\|_2^2 + \frac{\lambda_s}{2}\|\boldsymbol{\gamma}\|_2^2 \right\}, \qquad \lambda_f = \lambda_s = 5.0$$
solved deterministically via 10 iterations of Iteratively Reweighted Least Squares (IRLS), initialized at $w_i^{(0)} = 1$:
1. $\boldsymbol{\theta}^{(r+1)} = \big(X^\top W^{(r)} X + \Lambda\big)^{-1} X^\top W^{(r)} \mathbf{y}$, where $\Lambda = \text{diag}(0, \underbrace{\lambda_f, \dots, \lambda_f}_{6}, \underbrace{\lambda_s, \dots, \lambda_s}_{K_t})$ and $W^{(r)} = \text{diag}(w_i^{(r)})$.
2. $e_i^{(r+1)} = y_{i,t} - \mathbf{x}_{i,t}^\top \boldsymbol{\theta}^{(r+1)}$, $\hat{\sigma}_{\text{MAD}}^{(r+1)} = 1.4826 \cdot \operatorname{median}_i \big|e_i^{(r+1)} - \operatorname{median}_j e_j^{(r+1)}\big|$, $\delta^{(r+1)} = 1.345 \cdot \max(\hat{\sigma}_{\text{MAD}}^{(r+1)},\, 0.05)$.
3. $w_i^{(r+1)} = \min\!\left(1,\; \dfrac{\delta^{(r+1)}}{|e_i^{(r+1)}|}\right)$.

**Step 3 — Mispricing residual and EB heteroskedasticity standardization:**  
Define raw log fundamental mispricing (positive = market cap is *below* peer-implied fundamental value $\widehat{M}_{i,t}$):
$$m_{i,t} = \widehat{\ln(M/A)}_{i,t} - \ln\!\left(\frac{M_{i,t}}{A_{i,t}}\right) = \ln\!\left(\frac{\widehat{M}_{i,t}}{M_{i,t}}\right) = -\hat{e}_{i,t}$$
Because Ridge-shrunk sector fixed effects equalize cross-sector *means* but not cross-sector residual *heteroskedasticity* (e.g., wider log valuation residuals in Holdings/REITs than in Cement/Manufacturing), apply the Empirical-Bayes sector standardization operator $\mathcal{E}_5$ from Method S1 to $m_{i,t}$:
$$S^{(2)}_{i,t} = \mathcal{E}_5(m_{i,t} \mid s)$$
**Portfolio rule (identical to `R0`):** Monthly top 20% (`rank(ascending=False, pct=True) <= 0.20`), equal-weighted, evaluated in `scripts/research_portfolio_backtest.py` (1M TL real capital, base costs, next-close fills).

*Fixed structural priors (zero return-fitted parameters):* Huber efficiency constant $1.345$ is canonical (95% Gaussian efficiency); $\lambda_f = \lambda_s = 5.0$ corresponds to a Gaussian prior equivalent to 5 pseudo-observations (matching `MIN_SECTOR_N = 5`, and sitting right at the flat optimum of contemporaneous cross-sectional LOO-CV $R^2$: `0.386` at $\lambda=1$, `0.392` at $\lambda=3$, `0.391` at $\lambda=5$, `0.385` at $\lambda=10$).

### 2.2 Verified PIT Inputs

**Zero external fetches and zero new raw-file parsing required.** Every input already exists in the promoted PIT files:

| Input | File & Column | PIT / Audit Notes | Liquid Coverage |
|---|---|---|---|
| `mcap`, `sector`, `tlvol60`, `stmt_period` | `data/research/factors_monthly.parquet` (or `_kapdates`) | İş Yatırım `PD` market cap; `available_at <= t` | 100.0% |
| `total_assets`, `equity_parent`/`equity`, `fin_debt`, `cash` | `data/research/quarterly.parquet` (joined on `ticker, stmt_period`) | `undo_reexpression` applied; `total_assets > 0`: 100.0%, `equity > 0`: 98.1%, `fin_debt`/`cash`: 100.0%/99.9% | 98.0% |
| `ttm_revenue`, `ttm_gross_profit`, `ttm_op_profit`, `ttm_ni_parent`/`ttm_net_income` | `data/research/quarterly.parquet` (joined on `ticker, stmt_period`) | C1 constant-purchasing-power TTM + `bridge_ttm` (`2023Q4–2024Q3`); `ttm_revenue > 0`: 96.9% | 96.9% |
| **Resulting `S2` (`fund_mispricing_hr`)** | — | Strictly excludes negative-equity / zero-revenue / missing-TTM rows (no imputation) | **94.8%** |

- **Non-return cross-sectional diagnostics on the promoted PIT panel (162 months, 2013–2026):**
  - **Contemporaneous valuation fit:** Mean monthly cross-sectional $R^2 = \mathbf{0.475}$ (median `0.47+`), mean leave-one-out CV $R^2 = \mathbf{0.391}$ — confirming the 6 fundamentals + shrunk sector FE explain nearly half of BIST cross-sectional log valuation variance without touching returns.
  - **100% economically coherent monthly pricing slopes** (mean standardized $\hat{\beta}_j$ and fraction of 162 months with $\hat{\beta}_j > 0$):
    - $\ln(B/A)$: $+0.338$ (**100.0%** positive);
    - $\text{GP}/A$: $+0.229$ (**100.0%** positive);
    - $\ln(S/A)$: $+0.088$ (**94.4%** positive);
    - $\text{NI}/A$: $+0.079$ (**85.2%** positive);
    - $\text{OP}/A$: $+0.010$ (55.6% positive — collinear between `GP/A` and `NI/A`, stabilized by Ridge);
    - $\text{NetDebt}/A$: $-0.098$ (**95.1%** negative — higher net debt lowers equity value).
  - **Size & sector neutrality:** Rank correlation with `size = log(mcap)` is only `−0.1006` (no small-cap blowup); large-sector top-20% selection-rate SD $= 0.0529$ (`Holding = 20.7%`, `Gayrimenkul = 23.6%`, `İmalat = 17.2%`).
  - **Differentiation & turnover:** Spearman rank correlation vs `R0` $= 0.7340$ (vs `S1` $= 0.7710$); top-20% overlap vs `R0` $= \mathbf{64.4\%}$ (~36% new selections/month, vs `S1` $= 60.2\%$); average monthly turnover $= \mathbf{17.24\%}$ (only $+0.56$ pp above `R0`'s `16.68%`).

### 2.3 Rationale (Statistical / Cross-Sectional Mechanism)

1. **Market-implied, regime-adaptive multiple weighting without return peeking (unlike failed learned IC weights):**  
   Notice the algebraic unification inside `S2`:
   $$m_{i,t} = \hat{\alpha}_t + \hat{\gamma}_{s(i),t} + \hat{\beta}_1 \ln(B/A) + \hat{\beta}_2 \ln(S/A) + \dots - \ln(M/A)$$
   $$= \hat{\alpha}_t + \hat{\gamma}_{s(i),t} + \hat{\beta}_1 \ln(B/M) + \hat{\beta}_2 \ln(S/M) + (1 - \hat{\beta}_1 - \hat{\beta}_2)\ln(A/M) + \hat{\beta}_3 \tfrac{\text{OP}}{A} + \hat{\beta}_4 \tfrac{\text{NI}}{A} + \hat{\beta}_5 \tfrac{\text{GP}}{A} + \hat{\beta}_6 \tfrac{\text{ND}}{A}$$
   `S2` automatically nests $\ln(B/M)$, $\ln(S/P)$, $\ln(A/M)$, profitability, and net leverage using the **exact cross-sectional elasticities implied by BIST market prices in month $t$**! When Turkey shifts from low-rate nominal GAAP (2013–2017) to hyperinflation (2021–2023) to IAS 29 + 50% rates (2024–2026), the market's relative pricing of book equity, gross profit, net income, and net debt shifts automatically month by month — with **zero historical return fitting** (`N_params_fitted_to_returns = 0`).
2. **Fundamentally distinct from failed `quality x value` overlays:**  
   Additive/multiplicative `quality x value` (`QV1–QV3`, `H4a`) puts a fixed unconditional positive weight on profitability, forcing the portfolio to overpay for glamorous high-ROE stocks. In `S2`, profitability enters strictly as a **conditioning benchmark** on the RHS: by regression orthogonality, $\text{Cov}(m_{i,t}, \text{GP}/A) \approx 0$ and $\text{Cov}(m_{i,t}, \text{NI}/A) \approx 0$. A high-profitability stock only enters `S2`'s top 20% if its market price lags *far behind* what peers with identical profitability trade at; conversely, a low-`P/B` firm with weak profitability and high net debt gets a *lower* predicted $\widehat{\ln(M/A)}$, curbing classic unconditioned `B/M` value traps.
3. **Huber IRLS + Ridge prevents outlier leverage and small-sector overfitting:**  
   In BIST, speculative micro/mid-cap bubbles trade at $10\times$–$30\times$ peer multiples (`log(M/A)` outliers). Ordinary least squares (OLS) gets pulled toward these speculative bubbles, distorting fair-value estimates for every normal peer in the same sector. Huber IRLS smoothly downweights extreme valuation outliers without discarding them from the final mispricing ranking, while Ridge ($\lambda_s = 5$) shrinks small-sector fixed effects smoothly toward the market intercept (avoiding the `min_n = 5` cliff).
4. **Exact scale & inflation invariance:**  
   Scaling every stock's numerator and denominator by `total_assets` makes both $y_{i,t}$ and $\mathbf{f}_{i,t}$ dimensionless ratios; any common CPI drift between balance-sheet date and month-$t$ market cap is absorbed identically by the monthly intercept $\hat{\alpha}_t$.

### 2.4 Failure Modes

1. **Orthogonality to profitability re-admits deep loss-makers if their discount exceeds model prediction:**  
   Because the regression residual $m_{i,t}$ is orthogonal to $\text{NI}/A$ and $\text{OP}/A$, `S2`'s top 20% matches the universe's base rate of loss-makers (`ep <= 0`: **26.1%** vs `26.8%` universe and `10.0%` in `R0`; median ROE `7.59%` vs `13.64%` in `R0`). If a linear slope on $\text{NI}/A$ under-penalizes severe financial distress (where bankruptcy risk is nonlinear in negative earnings), `S2` could hold deeply distressed firms whose market cap trades below the linear prediction — hurting Discovery returns and survivorship/drawdown resilience.
2. **Omitted fundamental variables appear as fake "mispricing":**  
   Any real value driver absent from the 6 regressors — such as expected future growth, corporate governance / controlling-shareholder discount (crucial in BIST family conglomerates), regulatory tariff caps (utilities/telecom), or FX-debt mismatch — gets dumped into the residual $m_{i,t}$. Persistent governance discounts look perpetually "undervalued" in cross-sectional regressions and may never mean-revert.
3. **Functional-form misspecification across heterogeneous capital structures (Holdings / REITs / Asset-Light Tech):**  
   A single cross-sectional elasticity vector $\boldsymbol{\beta}_t$ is shared across all non-financial sectors (only intercepts $\gamma_{s,t}$ vary by sector). Asset-light software/tech firms (high `GP/A`, low `B/A`) and asset-heavy REITs (high `B/A`, low `S/A`) may obey different slope elasticities; pooling them can introduce systematic cross-business-model residuals inside broad sectors like `İmalat` or `Bilişim ve Yazılım`.
4. **Slightly narrower coverage (`94.8%`) and slightly higher turnover (`17.24%`):**  
   Requiring all 6 fundamental inputs drops 5.2% of liquid stock-months (negative equity, zero-revenue shells, or incomplete 4-quarter TTM), and month-to-month variation in estimated $\hat{\boldsymbol{\theta}}_t$ adds $+0.56$ pp of monthly turnover vs `R0` (modest, but non-zero under 1M TL liquidity-tier costs).

---

## Summary Comparison vs. `R0` (`value_sn`)

| Dimension | Baseline `R0` (`value_sn`) | **S1 (`value_eb_ns`)** | **S2 (`fund_mispricing_hr`)** |
|---|---|---|---|
| **Statistical paradigm** | 1%/99% winsorized z-scores, equal mean, unscaled sector demean (`min_n = 5`) | **Blom normal scores + 2-stage Empirical-Bayes sector location/scale + correlation-aware reliability composite** | **Scale-invariant Huber-Ridge cross-sectional regression $\ln(M/A) \sim \mathbf{f} + \gamma_s$ + EB residual scale** |
| **PIT inputs** | `bm, ep, sp, ey, sector` | Identical to `R0` (0 new items) | `mcap, total_assets, equity, fin_debt, cash, ttm_{rev,gp,op,ni}, sector` (100% in `quarterly.parquet`) |
| **Return-fitted parameters** | 0 | **0** (Blom exact; $\nu_0 = 5$) | **0** (Huber $1.345$; $\lambda_f = \lambda_s = 5.0$) |
| **Coverage (liquid univ.)** | 100.0% | **100.0%** | **94.8%** |
| **Score skew / excess kurt.** | $+0.774$ / $+3.338$ | **$+0.023$ / $-0.540$** | $-0.582$ / $+0.710$ |
| **Large-sector top-20% SD** | `0.0510` (`11.1%–31.3%`) | **`0.0352`** (`12.0%–24.3%`) | `0.0529` (`8.8%–29.1%`) |
| **Avg monthly turnover** | `16.68%` | **`16.39%`** | `17.24%` |
| **Top-20% overlap vs `R0`** | `100.0%` | **`78.6%`** | **`64.4%`** (`60.2%` vs `S1`) |
| **Rank corr vs `size`** | $+0.0838$ | $+0.0827$ | $-0.1006$ |
| **Top-20% `ep <= 0` / med ROE** | `10.0%` / `13.64%` | **`3.8%`** / **`15.44%`** | `26.1%` / `7.59%` |
| **Primary statistical risk** | Tail-skew dominance + sector dispersion imbalance + `min_n=5` cliff | Compressing extreme deep-value convexity; smaller tracking error vs `R0` | Linear profitability slope may under-penalize extreme distress; persistent governance discounts in residuals |

Both `S1` and `S2` are ready for Round 2 peer critique and, if selected, strict out-of-sample testing under the **fixed pass rule** (paired $D > 0$ in Discovery 2013–2020 with NW $t(D) \ge 1.0$, $D > 0$ in Holdout 2021+ with NW $t(D) \ge 2.0$, Holdout USD max drawdown within 2 pp of `R0`, plus DSR at the updated `N_sel`).
