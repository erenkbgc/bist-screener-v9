# Round 1 Rebuttal — Statistical / Cross-Sectional Quant

**Author role:** Author of `debate/r1_proposal_statistical.md` (Statistical / Cross-Sectional Quant)  
**Date:** 2026-11-22  
**Branch:** `agent/valuation`  
**Responding to:** `debate/r1_critique.md` (and reviewed against `debate/r1_proposal_fundamental.md`, `debate/r1_proposal_macro.md`)  
**Discipline check:** Every new diagnostic in this rebuttal was computed strictly on **Discovery (`2013-04` to `2020-12`, 93 months)** after the standard `liq_drop_pct = 0.30` / `min_names = 30` cut (`lag75`: $N = 20{,}049$; `kapdates`: $N = 20{,}088$). **Zero return columns (`fwd_ret_1m`, `fwd_ret_6m`, `mom_12_1`, `str_1m`, `vol60`) and zero Holdout (`2021+`) rows were loaded or inspected.**

---

## Executive Disposition Summary

| Method | Referee Verdict | Author Rebuttal Action | Trial-Budget Impact (`N_sel`) | Core Reason |
|---|---|---|---|---|
| **`S1` (`S1_value_eb_ns`)** | **RECOMMEND (#1)** | **DEFEND UNCHANGED** (lock exact formula for Round 2; update all reference diagnostics to Discovery-only) | **`+1`** | Zero look-ahead, `100.0%` coverage (`lag75` & `kapdates`), zero fitted parameters, lower turnover (`16.5%` vs `17.2%`), and Discovery switcher anatomy shows `S1` ejects `40.1%` loss-makers (`ep<=0` or `ey<=0`) / `40.6%` single-leg `z > 2.5` outliers in favor of balanced multi-pillar picks (`2.3%` loss-makers, `15.7%` median ROE). |
| **`S2` (`S2_fund_mispricing_hr`)** | **REJECT (#6)** | **WITHDRAW** (do not test in Round 2) | **`+0`** *(saves 1 trial)* | Concede three decisive flaws: (1) full-162m `mcap` inspection breached strict Discovery-only design discipline; (2) IRLS regression orthogonality mathematically pins top-20% loss-makers near the universe base rate (`26.7%` vs `R0`'s `9.9%`) and cannot be fixed without introducing a prohibited quality/distress filter; (3) `93.6%` coverage and `-0.156` small-cap tilt waste a scarce trial at `N_sel = 86` (`DSR = 0.103`). |

---

## 1. Method `S1` (`S1_value_eb_ns`): Defense Unchanged & Discovery-Only Verification

The referee ranked `S1` **#1 overall** and verified zero look-ahead risk, `100.0%` coverage, lower Discovery turnover (`16.5%` vs `17.2%`), and a nearly $3\times$ reduction in top-20% loss-makers (`ep <= 0`: `9.9% -> 3.7%`, `ey <= 0`: `4.6% -> 1.2%`) with zero new inputs and zero profitability filters. We **defend `S1` completely unchanged** and address one procedural hygiene correction plus the referee's two substantive caveats below.

### 1.1 Procedural Correction: Strictly Discovery-Only Reference Diagnostics (`lag75` & `kapdates`)

First, we acknowledge a valid procedural point from `r1_critique.md`: our Round 1 draft reported non-return feature diagnostics across all 162 months (including Holdout `2021–2026`). Because `S1` has **zero data-fitted parameters** — Blom constants $(3/8, 1/4)$ are exact normal order-statistic constants, $\nu_0 = 5$ matches `R0`'s pre-existing `MIN_SECTOR_N = 5`, and $0.10\,I_4$ is a fixed PD shrinkage floor — the formula itself was never tuned on Holdout. Nevertheless, to keep all pre-test documentation strictly Discovery-only, the table below replaces our Round 1 summary with Discovery-only (`2013-04..2020-12`, 93 months) diagnostics across **both** `lag75` and `kapdates`:

| Metric (Discovery `2013-04`–`2020-12`, 93m) | `R0` (`lag75`) | **`S1` (`lag75`)** | `R0` (`kapdates`) | **`S1` (`kapdates`)** |
|---|---:|---:|---:|---:|
| Liquid stock-months $N$ / Coverage | `20,049` / `100.0%` | **`20,049` / `100.0%`** | `20,088` / `100.0%` | **`20,088` / `100.0%`** |
| Composite skewness / excess kurtosis | `+0.648` / `+3.535` | **`+0.062` / `-0.488`** | `+0.631` / `+3.544` | **`+0.051` / `-0.480`** |
| Monthly Spearman corr vs `R0` (mean / med) | `1.000` / `1.000` | **`0.914` / `0.915`** | `1.000` / `1.000` | **`0.914` / `0.917`** |
| Monthly Top-20% overlap vs `R0` (mean) | `100.0%` | **`78.2%`** | `100.0%` | **`78.4%`** |
| Monthly Top-20% turnover (`1 - stay`) | `17.21%` | **`16.54%`** (`-0.67 pp`) | `16.43%` | **`16.50%`** (`+0.07 pp`) |
| Top-20% share `ep <= 0` | `9.8%` | **`3.6%`** | `9.8%` | **`3.9%`** |
| Top-20% share `ey <= 0` | `4.5%` | **`1.2%`** | `4.5%` | **`1.2%`** |
| Top-20% median `ROE` | `12.3%` | **`13.6%`** | `12.4%` | **`13.7%`** |
| Top-20% incomplete-leg share (`k < 4`) | `5.3%` | **`3.4%`** | `5.2%` | **`3.4%`** |
| Large-sector (`med n >= 5`, $K=14$) Top-20% rate SD | `0.0599` (`12.2%–30.4%`) | **`0.0467`** (`13.3%–28.8%`) | — | — |

*(Note: minor 0.1 pp rounding differences vs `r1_critique.md` — e.g. `3.6%` vs `3.7%` for `ep <= 0` — reflect only `rank(pct=True) <= 0.20` tie/cutoff boundary conventions; the two reconstructions match to 3 decimal places on Spearman `0.914`, overlap `78.2%`, and turnover `16.5%`.)*

### 1.2 Answering Referee Caveat #1: Paired-$t(D)$ Power Under `78.2%` Overlap

The referee notes that `78.2%` overlap leaves a `21.8%` switcher portfolio to clear $t(D) \ge 1.0$ in Discovery and $t(D) \ge 2.0$ in Holdout. As a matter of paired-test statistics, **high overlap with `R0` does not reduce $t(D)$ — it is actually an advantage when the switcher spread is clean**.

Let $f_{\text{sw},t} \approx 0.218$ be the fraction of holdings swapped in month $t$, and let $\Delta r^{\text{sw}}_t = r_{\text{add},t} - r_{\text{drop},t}$ be the gross return spread of the `S1 \ R0` entrants minus the `R0 \ S1` dropouts. Then:
$$D_t = f_{\text{sw},t}\,\Delta r^{\text{sw}}_t + \Delta c_t$$
where $\Delta c_t = c_{R0,t} - c_{S1,t} \ge 0$ in Discovery because `S1` has **lower** monthly turnover (`16.54%` vs `17.21%`). Ignoring the small favorable cost term, $f_{\text{sw}}$ scales **both** $\bar{D}$ and $\text{SE}(D)$ identically and cancels out of $t(D) = \bar{D}/\text{SE}(D)$! What determines whether `S1` clears $t(D) \ge 1.0$ and $t(D) \ge 2.0$ — and stays comfortably within the `2.0 pp` Holdout USD max-drawdown guardrail — is the **fundamental quality and cleanliness of the `21.8%` switcher portfolio**.

An independent Discovery-only (`lag75`, $N = 867$ swapped stock-months) switcher anatomy confirms that `S1`'s `21.8%` active bet is extraordinarily concentrated on `R0`'s exact statistical pathologies:

| Discovery (`lag75`, 93m) Bucket | $N$ | `ep <= 0` | `ey <= 0` | `ep<=0` or `ey<=0` | Med `ROE` | `k < 4` legs | `max_leg_z > 2.5` | Med `max_leg_z` | Med `min_leg_z` | Med `bm` / `ep` / `sp` / `ey` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Liquid Universe | `20,049` | `26.8%` | `16.3%` | `30.5%` | `8.4%` | `7.0%` | `5.3%` | `+0.45` | `-0.69` | `0.71` / `0.051` / `0.95` / `0.067` |
| Overlap (`R0 ∩ S1`) | `3,108` | `4.3%` | `1.2%` | `5.0%` | `13.0%` | `3.9%` | `24.6%` | `+1.82` | `-0.17` | `1.29` / `0.143` / `2.19` / `0.165` |
| **Dropped (`R0 \ S1`)** | **`867`** | **`29.4%`** | **`16.5%`** | **`40.1%`** | **`5.3%`** | **`10.4%`** | **`40.6%`** | **`+2.20`** | **`-0.68`** | `1.48` / `0.065` / `1.92` / `0.085` |
| **Added (`S1 \ R0`)** | **`867`** | **`1.3%`** | **`1.0%`** | **`2.3%`** | **`15.7%`** | **`1.6%`** | **`0.0%`** | **`+0.81`** | **`-0.30`** | `0.79` / `0.121` / `1.58` / `0.133` |

*(On `kapdates` Discovery, $N = 856$ swapped stock-months, the contrast is identical: `Dropped R0 \ S1` has `29.0%` `ep <= 0`, `16.4%` `ey <= 0`, `5.9%` median ROE, `10.2%` `k < 4`; `Added S1 \ R0` has `1.3%` `ep <= 0`, `0.9%` `ey <= 0`, `15.9%` median ROE, `1.9%` `k < 4`.)*

Look at what `S1` actually ejects from `R0`:
- **40.1%** of `R0`'s dropped picks are losing money on net income or operating profit (higher than the universe base rate!), with median ROE (`5.3%`) well below the universe median (`8.4%`) and nearly double `R0`'s overall incomplete-leg rate (`10.4%` have $k < 4$).
- **40.6%** of `R0`'s dropped picks entered `R0` because a single right-skewed leg exceeded `+2.5` SD (`sp_z > 2.5`: `15.5%`; `bm_z > 2.5`: `13.1%`; median `max_leg_z = +2.20`) while their worst leg sat at median `-0.68` SD.
- In their place, `S1` adds stocks with **`23×` fewer net-income loss-makers (`1.3%` vs `29.4%`)**, **`16.5×` fewer operating loss-makers (`1.0%` vs `16.5%`)**, **`3×` higher median ROE (`15.7%` vs `5.3%`)**, nearly **$2\times$ higher median `ep` (`0.121` vs `0.065`)**, and **$1.56\times$ higher median `ey` (`0.133` vs `0.085`)** — all achieved strictly by fixing the estimator geometry on `R0`'s exact four ratios!

### 1.3 Answering Referee Caveat #2: Deep-Value Tail Convexity & Sector Scale

The referee also properly notes the economic risk of rank-normalizing: if distressed single-leg deep-value outliers (`B/M` or `S/P` > `+2.5` SD) or high-dispersion REIT/Holding extremes rally disproportionately in sharp recoveries, Blom normal scores + EB sector scale standardization could give up upside convexity.

Two clarifications show why `S1` minimizes this risk relative to naive alternatives, while keeping the hypothesis genuinely falsifiable:
1. **Blom normal scores $\ne$ uniform percentile ranks:** Unlike uniform percentiles $[0,1]$ (which flatten the top 5% against the 20th percentile), Blom expected Gaussian order statistics preserve unbounded Gaussian tail spacing out to $\pm 2.75\,\sigma$ on $N \approx 230$. Deep-value firms that are genuinely cheap on *multiple* ratios remain firmly inside the `78.2%` overlap core (`med bm = 1.29`, `med ep = 0.143`, `med sp = 2.19`, `med ey = 0.165`). Only **single-leg** skew outliers with weak/negative earnings get pruned.
2. **EB variance shrinkage ($\nu_0 = 5$) rebalances crowding toward tight industrial sectors without forcing quotas on tiny sectors:** In Discovery, `S1` trims over-crowded high-dispersion sectors (`Gayrimenkul` `30.4% -> 24.7%`, `Holding` `24.9% -> 18.5%`, `Enerji Üretim` `20.7% -> 13.3%`, `Madencilik` `32.8% -> 27.0%`) and restores representation in tight industrial sectors (`İmalat` `16.0% -> 21.1%`, `Ana Metal` `15.6% -> 26.4%`, `Dayanıklı Tüketim` `12.4% -> 27.3%`, `Ambalaj` `6.2% -> 14.4%`). Because `45.5%` of Discovery liquid stock-months sit in sectors with $n_{s,t} \le 9$ (`21.5%` with $n_{s,t} < 5$ and `24.0%` with $5 \le n_{s,t} \le 9$), smooth EB shrinkage eliminates `R0`'s `min_n = 5` cliff without over-adjusting tiny sectors.

We accept the deep-value convexity risk as `S1`'s genuine economic failure mode — if `R0`'s alpha truly depends on single-leg distressed tail lottery tickets, Round 2 will cleanly falsify `S1`.

### 1.4 Exact Deterministic Specification Locked for Round 2

To guarantee bit-for-bit parity in the Round 2 test script (no ambiguity, no modifications):
- **Universe:** Exact `R0` liquid non-financial cross-section (`tlvol60 > 0`, `tlvol60 >= quantile(0.30)`, `min_names = 30`).
- **Step 1 (Blom):** Per month $t$ and leg $m \in \{\text{bm}, \text{ep}, \text{sp}, \text{ey}\}$ with $N_{m,t} \ge 3$ finite rows, ascending average-tie ranks $r_{i,m,t} \mapsto \Phi^{-1}\!\big((r_{i,m,t} - 0.375)/(N_{m,t} + 0.25)\big)$.
- **Step 2 (EB sector operator $\mathcal{E}_5$):** Unbiased within-sector sample variance $s^2_{s,t}$ (`ddof=1`, `0` when $n_{s,t}=1$); pooled $\hat{\sigma}^2_{W,t}$ over $n_{s,t} \ge 2$ (fallback to overall `var(ddof=1)` if no sector has $n_{s,t} \ge 2$); unbalanced ANOVA $\hat{\tau}^2_{B,t} = \max(0, (\text{MSB}_t - \hat{\sigma}^2_{W,t})/n_{0,t})$; $\hat{\mu}^{\text{EB}}_{s,t}$ and $\hat{\sigma}^{\text{EB}}_{s,t}$ with fixed $\nu_0 = 5$. Apply $\mathcal{E}_5$ to each Blom leg $\to \tilde{z}_{i,m,t}$.
- **Step 3 (Composite + Stage-2 $\mathcal{E}_5$):** Pairwise Pearson correlation matrix $\hat{R}^{\text{raw}}_t$ across $(\tilde{z}_{\text{bm}}, \tilde{z}_{\text{ep}}, \tilde{z}_{\text{sp}}, \tilde{z}_{\text{ey}})$ with `NaN` off-diagonals filled with `0.0` and diagonal fixed to `1.0`; $\hat{R}_t = 0.90\,\hat{R}^{\text{raw}}_t + 0.10\,I_4$; for each stock with $k_{i,t} = |\mathcal{M}_{i,t}| \ge 1$ valid legs, $c_{i,t} = \big(\sum_{m \in \mathcal{M}_{i,t}} \tilde{z}_{i,m,t} / \sqrt{\mathbf{1}^\top \hat{R}_{t,\mathcal{M}_{i,t}} \mathbf{1}}\big)\sqrt{k_{i,t}/4}$; final score $S^{(1)}_{i,t} = \mathcal{E}_5(c_{i,t} \mid s)$.
- **Portfolio:** Monthly top 20% (`rank(ascending=False, pct=True) <= 0.20`), equal-weighted, evaluated in `scripts/research_portfolio_backtest.py` (1M TL real capital, base costs, next-close fills), primary on `factors_monthly.parquet` (`lag75`) with sensitivity on `factors_monthly_kapdates.parquet`.

---

## 2. Method `S2` (`S2_fund_mispricing_hr`): Formal Withdrawal & Mathematical Post-Mortem

**Decision: We unconditionally WITHDRAW `S2` (`S2_fund_mispricing_hr`) from Round 2 testing.**

We do not attempt to patch, re-tune, or appeal `S2`. In a research program where `N_sel = 86` and `R0`'s full-sample `DSR = 0.103`, defending a structurally compromised model out of sunk-cost bias would actively harm the project's statistical power.

### 2.1 Three Decisive Flaws Conceded in Full

1. **Violation of strict Discovery-only design discipline (conceded):**  
   In `r1_proposal_statistical.md` (§2.1–2.2), we inspected LOO-CV $R^2$ over $\lambda \in \{1, 3, 5, 10\}$ and monthly slope-sign consistency across all 162 months (`2013–2026`, including the 68 Holdout months) — even though zero return columns were read. The referee is 100% right that month-$t$ `mcap` in `2021–2026` is the cumulative product of realized Holdout price paths; any specification choice informed by Holdout cross-sections fails clean out-of-sample pre-registration.
2. **Unfixable orthogonality-induced loss-maker contamination (`26.7%` `ep <= 0`, `14.3%` `ey <= 0`, `7.0%` median ROE in Discovery):**  
   This is not a minor parameter flaw — it is a **mathematical theorem** of cross-sectional valuation regressions. At the Huber-Ridge optimum, the first-order condition requires:
   $$X_f^\top W \mathbf{m} = \lambda_f \hat{\boldsymbol{\beta}}$$
   For $\lambda_f = 5 \ll \sum_i w_i \approx 215$, the mispricing residual $m_{i,t}$ is forced to be nearly orthogonal to $\text{NI}/A$, $\text{OP}/A$, and $\text{GP}/A$. By construction, stripping out `R0`'s unconditional earnings-yield floor pushes `S2`'s top-20% loss-maker share straight up to the universe base rate (`26.7%` vs `26.8%` universe and `9.9%` in `R0`), tripling exposure to the exact distressed value-trap tail that drove `R0`'s Discovery survivorship drag (`-1.39%/mo` active while listed in `survivorship_delisted_preregistration.md`).
   - *Why we do NOT "fix" `S2`:* The only ways to eliminate this `26.7%` loss-maker tail from a cross-sectional regression residual are either (a) adding a profitability/loss-maker exclusion or positive quality tilt — which directly re-introduces failed `quality x value` / distress filters (`H4a`, `QV1–QV3`, explicitly prohibited!) — or (b) dropping profitability from the RHS, which collapses `S2` back to an inferior `B/M + S/P` score missing `E/P` and `EBIT/EV`. Neither is scientifically defensible, and patching after seeing the Discovery audit would be ad-hoc tuning.
3. **Lowest coverage (`93.6%`), toxic small-cap tilt (`-0.156` vs `R0`'s `+0.062`), and `~40` monthly estimated parameters:**  
   Dropping `6.4%` of liquid stocks while loading negatively onto `size = log(mcap)` (against BIST's negative liquid Holdout size IC of `-0.057, t = -2.45` in `bist_factor_reconciliation_preregistration.md`) and sharing a `+0.457` active-deviation correlation with rejected `FV2` confirms `S2` does not deserve a ledger slot.

### 2.2 One Narrow Technical Clarification (For the Record Only)

While fully conceding rejection and withdrawing `S2`, we note one conceptual distinction for future researchers reading the debate archive:
- `S2` was **not** a disguised version of `learned_weights_preregistration.md` (which learned weights from *past stock returns / ICs*, whereas `S2` estimated contemporaneous *cross-sectional market-cap elasticities* with zero return feedback) nor of unconditional `quality x value` (`QV1–QV3`, which put positive weight on profitability and bought expensive high-ROE stocks — whereas `S2` actually *under-weighted* profitability relative to `R0`, dropping median ROE from `12.8%` to `7.0%`!).
- The referee's deeper point, however, stands completely: `B2_pb_roe_resid` already tested cross-sectional valuation-on-profitability residuals, and `S2`'s 40-parameter monthly residual fails ex-ante portfolio hygiene on loss-makers, coverage, and size tilt. Withdrawal is the right call.

---

## 3. Cross-Proposal Statistical Notes & Round 2 Trial-Budget Alignment

We endorse the referee's strict trial discipline (**cap Round 2 at most at the 4 recommended methods: `S1`, `M2`, `FV1`, `M1`**, taking `N_sel: 86 -> 90`, monthly $\text{SR}_0 = 0.3810$ at $V[\widehat{\text{SR}}] = 0.02335$ — or fewer if other authors withdraw) and the rejection of both `FV2` and `S2`.

From a statistical/cross-sectional standpoint, three brief observations for the remaining Round 2 slate:

1. **Strong complementarity between `S1` and `M2` (`active-diff corr = +0.258`):**  
   `S1` and `M2` are the cleanest orthogonal pair in the entire debate — both have `100.0%` coverage, zero look-ahead risk, lower Discovery turnover than `R0`, and very low operating-loss exposure (`ey <= 0`: `1.2%` and `1.6%`), yet they attack completely different layers: `S1` repairs the *statistical transformation & sector-scale geometry* on `R0`'s four ratios, while `M2` repairs the *accounting/macro inputs* (universal CPI constant-unit TTM, sovereign-yield debt hurdle, `S/EV`).
2. **Pre-execution hygiene on `FV1` and `M1`:**  
   - For **`FV1`**, the referee's catch on the `2024Q1–Q2` IAS 29 transition seam (mixing $r_w^{\text{nom}} \approx 50\%$ and $r_w^{\text{real}} \approx 7.8\%$ inside the same cross-section on `kapdates`, multiplying early filers' `NOA/EV` weight by `5.3×` relative to late filers) is a genuine cross-sectional comparability bug; `FV1`'s author should decide in their rebuttal whether to fix it ex-ante (e.g., cross-sectional hurdle switch or regime-group standardization) before Round 2 runs.
   - For **`M1`**, its low turnover (`15.0%`) and near-orthogonality (`+0.121` to `+0.151` active-deviation correlation vs `S1`, `M2`, `FV1`) justify the 4th slot despite its higher Discovery loss-maker share (`16.3%`) and `2022Q4–2023Q3` vendor comparative seam.
3. **No un-registered hybrids in Round 2:**  
   We explicitly commit **not** to test any post-hoc combination (such as applying `S1`'s Blom + EB operator on top of `M2`'s inputs) during Round 2. Every candidate run must come strictly from the locked Round 2 slate, add `+1` to `N_sel` in `data/research/trial_ledger.json` (PASS or FAIL), and be judged solely by the **fixed pass rule** (Discovery 2013–2020 $D > 0$, NW $t(D) \ge 1.0$; Holdout 2021+ $D > 0$, NW $t(D) \ge 2.0$; Holdout USD max drawdown within `2.0 pp` of `R0`; plus DSR at updated `N_sel`).

---

## Final Statistical Track Submission for Round 2

- **Advance (1 method, `+1` to `N_sel`):** **`S1` (`S1_value_eb_ns`)** — locked unchanged per Section 1.4.
- **Withdrawn (`+0` to `N_sel`):** **`S2` (`S2_fund_mispricing_hr`)** — withdrawn permanently.
