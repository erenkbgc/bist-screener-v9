# Round 1 Chair Decision — Valuation Method Selection & Trial-Ledger Allocation

**Author role:** Head of Research (Chair)  
**Date:** 2026-11-22  
**Branch:** `agent/valuation`  
**Pre-registration file:** [`docs/research/valuation_round1_preregistration.md`](../docs/research/valuation_round1_preregistration.md)  
**Trial ledger updated:** [`data/research/trial_ledger.json`](../data/research/trial_ledger.json) (`N_sel: 86 -> 89`, `+3` stock-selection trials committed prior to any backtest code)

---

## 1. Executive Summary of Chair Decision

After reviewing all six Round 1 proposals ([`r1_proposal_fundamental.md`](r1_proposal_fundamental.md), [`r1_proposal_macro.md`](r1_proposal_macro.md), [`r1_proposal_statistical.md`](r1_proposal_statistical.md)), the referee's Discovery-only empirical risk audit ([`r1_critique.md`](r1_critique.md)), and all three track rebuttals ([`r1_rebuttal_fundamental.md`](r1_rebuttal_fundamental.md), [`r1_rebuttal_macro.md`](r1_rebuttal_macro.md), [`r1_rebuttal_statistical.md`](r1_rebuttal_statistical.md)), the Chair approves **3 methods** (within the $\le 4$ cap) for confirmatory backtesting and drops **3 methods**:

| Method ID | Track | Method Name | Chair Verdict | Ledger Impact (`N_sel`) | Primary Reason for Selection or Rejection |
|---|---|---|---|---:|---|
| **`S1`** (`S1_value_eb_ns`) | Statistical / Cross-Sectional | Empirical-Bayes Sector-Standardized Normal-Score Value | **CHOSEN (#1)** | **`+1`** | Zero new inputs, `100.0%` coverage, `0` return-fitted parameters, lower Discovery turnover (`16.5%` vs `17.2%` `R0`), cuts top-20% loss-makers from `9.8%` to `3.6%` (`40.1% -> 2.3%` in swapped picks), and fixes `R0`'s `min_n = 5` cliff and 5× cross-sector dispersion imbalance. |
| **`M2`** (`M2_value_real_spread_sn`) | EM / Turkey Macro-Adjusted | Sovereign-Spread-Conditioned Real Economic Value | **CHOSEN (#2)** | **`+1`** | Strictly PIT universal CPI constant-unit TTM (lagged $t-1$) + live Turkey USD Eurobond sovereign yield debt charge ($y^{\text{USD}}_{\text{TR},t}\cdot\text{NetDebt}$) + unlevered `S/EV` (`sev_real`). `100.0%` coverage, `0` fitted parameters, lower turnover (`15.6%–16.1%`), cuts top-20% operating loss-makers (`ey <= 0`) from `4.5%` to `1.0%–1.6%` (`22.0% -> 1.6%` in swapped picks) and slashes switcher median `NetDebt/MCap` from `+85.2%` to `+5.6%`. |
| **`FV1`** (`FV1_reoi_ev_sn`) | Fundamental Valuation | Inflation-Consistent Residual Operating Income (`V_ReOI / EV`) | **CHOSEN (#3)** | **`+1`** | Closed-form Feltham-Ohlson 5-year residual operating income (`97.6%` coverage, `0` fitted parameters, lower turnover `16.9%` vs `17.2%` `R0` and `17.5%` `V1`). Unifies `NOA` and `NOPAT` in raw TL on an unlevered `EV` denominator against a Fisher nominal/real policy+ERP hurdle $r_{w,t}$, cutting switcher median `NetDebt/MCap` from `+78.2%` to `+7.8%`, with a zero-parameter ex-ante convex PV-weight + regime-cohort normalization that eliminates the early-2024 IAS 29 transition seam. |
| **`M1`** (`value_usd_3y_sn`) | EM / Turkey Macro-Adjusted | Hard-Currency (USD) 3Y Normalized Value | **DROPPED (Withdrawn)** | **`+0`** | Withdrawn by author after Discovery switcher proof showed 1-year USD TTM is `96.91%` identical to `R0` (`0.9952` rank corr), so 100% of `M1`'s active divergence comes from 3-year backward averaging — algebraically identical to selecting on **negative 2-year USD earnings growth** (`83.4%` falling USD net income, **`36.8%` `ep <= 0`**, **`20.8%` `ey <= 0`**, `3.5%` median ROE in entrants) — plus an unfixable `2022Q4–2023Q3` vendor IAS 29 comparative restatement seam in Holdout. |
| **`FV2`** (`ccv_sn`) | Fundamental Valuation | Enterprise Cash-Conversion Valuation (`ccey + noa_ev + rev_ev`) | **DROPPED (Rejected & Withdrawn)** | **`+0`** | Rejected by referee and withdrawn by author: severe distressed working-capital liquidation trap in Discovery (**`21.2%` `ep <= 0`**, **`12.3%` `ey <= 0`**, `8.4%` median ROE when shrinking firms liquidate inventory/stretch payables $\implies \Delta^{\text{real}}\text{WC} < 0$), highest turnover (`18.5%`), Sloan accrual overlap, and `raw/*.pkl` IAS 29 comparative restatement / `2025Q2` `reexpression_class` look-ahead risk. |
| **`S2`** (`fund_mispricing_hr`) | Statistical / Cross-Sectional | Scale-Invariant Huber-Ridge Cross-Sectional Fundamental Mispricing | **DROPPED (Rejected & Withdrawn)** | **`+0`** | Rejected by referee and withdrawn by author: specification & $\lambda = 5$ were selected after inspecting all 162 months of `mcap` (including 2021–2026 Holdout); IRLS orthogonality mathematically forces top-20% loss-makers to the universe base rate (**`26.7%` `ep <= 0`**, **`14.3%` `ey <= 0`**, `7.0%` median ROE); lowest coverage (`93.6%`); toxic small-cap tilt (`-0.156`); and structural overlap with failed `B2_pb_roe_resid`, `GP/A`/`OP/A`, and `40`-parameter monthly learned weights. |

**Trial-budget discipline:** Stopping at **3 methods** (`N_sel: 86 -> 89` rather than `90` or `92`) saves 3 full stock-selection trials relative to the 6 initial proposals and 1 trial relative to the 4-method ceiling. At `N_sel = 89` ($T = 161$ months, cross-variant monthly Sharpe variance $V[\widehat{\text{SR}}] = 0.02335$), the expected maximum monthly Sharpe ratio under the null is $\text{SR}_0 = 0.3804$ (`1.3177` annualised).

---

## 2. Why Each Chosen Method Was Selected

### 2.1 Method 1: `S1` (`S1_value_eb_ns`) — Statistical / Cross-Sectional Track

- **Exact statistical defect in `R0` addressed:**
  1. `R0` applies 1%/99% linear winsorization (`fb.winsorize_z`) to two strictly positive, heavily right-skewed ratios (`sp_z` p99 $= +4.60$, `bm_z` p99 $= +3.56$) alongside two two-sided ratios (`ep_z`, `ey_z`). A single extreme right-tail `S/P` or `B/M` outlier overpowers deeply negative earnings, leaving `9.8%` bottom-line loss-makers (`ep <= 0`) in `R0`'s Discovery top quintile.
  2. `R0` standardizes globally across the market first and then only subtracts the unshrunk sector mean (`min_n = 5`). Because within-sector dispersion varies by nearly $5\times$ (`0.22–0.37` in `Madencilik`, `Ambalaj`, `Taş, Toprak, Çimento`, `İmalat` vs. `0.79–1.02` in `Holding`, `Gayrimenkul`, `Girişim Sermayesi`), `R0` over-allocates to REITs (`30.4%`) and Holdings (`24.9%`) while starving tight industrial sectors (`İmalat` `16.0%`), and leaves `21.5%` of Discovery stock-months in sectors with $n_{s,t} < 5$ completely un-neutralized.
- **Discovery-only empirical evidence (`2013-04..2020-12`, 93 months, zero return columns inspected):**
  - `100.0%` coverage (`20,049 / 20,049` on `lag75`, `20,088 / 20,088` on `kapdates`), zero new data dependencies, and lower monthly turnover (`16.54%` vs `17.21%` in `R0`).
  - In the `21.8%` active switcher portfolio (`867` swapped stock-months in Discovery), `R0 \ S1` dropouts consist of **`40.1%` loss-makers (`ep <= 0` or `ey <= 0`)** and **`40.6%` single-leg `z > 2.5` skew outliers** (`med ROE = 5.3%`), whereas `S1 \ R0` entrants contain only **`2.3%` loss-makers (`1.3%` `ep <= 0`, `1.0%` `ey <= 0`)**, `0.0%` single-leg `z > 2.5` outliers, and **`15.7%` median ROE** — achieved purely by fixing the estimator geometry on `R0`'s exact four ratios without adding any quality or profitability factor.

### 2.2 Method 2: `M2` (`M2_value_real_spread_sn`) — EM / Turkey Macro-Adjusted Track

- **Exact Turkish macro & accounting defects in `R0` addressed:**
  1. Below-the-line accounting net income (`ep`) is distorted across every Turkish macro regime: FX debt translation swings in 2013–2020, nominal interest vs. cash purchasing-power erosion in 2021–2023, and **non-cash IAS 29 net monetary position gains/losses** folded into `(Esas Faaliyet Dışı) Finansal Gelirler / Giderler (-)` in 2023Q4+ (where `sign(ttm_ni_parent) != sign(ttm_op_profit)` in `24.4%` of IAS 29 stock-months).
  2. Before `2023Q4`, `R0` sums four nominal quarterly flows of unequal purchasing power and compares month-$t$ `mcap` against stale period-$p$ balance-sheet `NetDebt_p` in `EV`.
  3. `R0`'s `S/P = Sales / MCap` multiplies unlevered sales yield `Sales / EV` by $(1 + \text{NetDebt}/\text{MCap})$, rewarding heavily indebted low-margin companies right when sovereign borrowing costs spike.
- **Discovery-only empirical evidence (`2013-04..2020-12`, 93 months):**
  - `100.0%` coverage, zero look-ahead (TÜİK CPI strictly lagged to $m^*(t) = t - 1\text{ month}$; month-end `3–30y` Turkey USD Eurobond median yield $y^{\text{USD}}_{\text{TR},t}$), zero free parameters, and lower monthly turnover (`15.6%–16.1%` vs `17.2%` `R0`).
  - Across the `696` swapped Discovery stock-months (`82.5%–83.0%` overlap with `R0`), `M2` ejects heavily indebted `R0` value traps (`med NetDebt/MCap = +85.2%`, `44.3%` with `NetDebt > MCap`, **`22.0%` operating loss-makers `ey <= 0`**, `med ey = 6.9%`) and replaces them with net-cash / low-debt operating earners (`med NetDebt/MCap = +5.6%`, `43.2%` net cash, **`1.6%` `ey <= 0`**, `med ey = 14.0%`). Moreover, `90.1%` (`24.7% / 27.4%`) of `M2`'s `ep <= 0` entrants have strongly positive operating profit (`ey > 0`).
  - Because `M2` expresses every period from 2013 to 2026 in real constant purchasing power and always applies the real USD sovereign yield $y^{\text{USD}}_{\text{TR},t}$ (`~4.7%–11.0%`), it has **zero discount-rate discontinuity** across the `2023Q4` IAS 29 boundary.

### 2.3 Method 3: `FV1` (`FV1_reoi_ev_sn`) — Fundamental Valuation Track

- **Exact fundamental valuation defect in `R0` addressed:**
  - `R0` averages separately standardized z-scores (`bm_z`, `ep_z`, `sp_z`, `ey_z`) with static equal weights and no cost-of-capital charge, treating a capital-destroying high-`B/M` firm (`ROIC << WACC`) on the `bm` leg identically to a value-creating operator, and keeping book-vs-earnings weights fixed whether Turkish policy rates are `10%` nominal, `50%` nominal, or `~8%` real under IAS 29.
  - `FV1` values the operating enterprise directly in raw TL via Feltham & Ohlson (1995) 5-year Residual Operating Income ($V^{\text{ReOI}}_{i,t} = \text{NOA}_{i,t} + A(r_{w,i,t}, 5)(\text{NOPAT}_{i,t} - r_{w,i,t}\text{NOA}_{i,t})$) scaled by unified `EV`, using existing repository priors ($\tau = 0.25$, $\text{ERP} = 0.05$, $T = 5$).
- **Resolution of the Referee's two technical critiques (`r1_rebuttal_fundamental.md`):**
  1. *Distinction from failed `V1` (`bm+ep+ey` without `S/P`):* On Discovery (`2013-04..2020-12`), `FV1` diverges from `V1` on **24.2% of top-20% holdings** (`75.8%` overlap) and **lowers** monthly turnover (`16.94%` vs `17.21%` `R0` and `17.53%` `V1`). Because $\text{NOA}/\text{EV} = (\text{bm} + L)/(1 + L)$ pulls high-leverage cheap stocks ($\text{bm} > 1, L = \text{NetDebt}/\text{MCap} > 0$) down toward `1.0` while charging $r_{w,t}\text{NetDebt}$ and expanding `EV`, `FV1` cuts median `NetDebt/MCap` across swapped Discovery holdings by **`10×` from `+78.2%` (`R0 \ FV1`, `43.1%` with `NetDebt > MCap`, `med sp = 3.35`) to `+7.8%` (`FV1 \ R0`, `31.9%` net cash, `med bm = 1.49`)**.
  2. *Ex-ante fix for the early-2024 IAS 29 mixed-regime transition seam:* Dividing $V^{\text{ReOI}}/\text{EV}$ by the total present-value multiplier $(1+r_{w,i,t})^{-5} + (1-\tau)A(r_{w,i,t}, 5)$ puts $\text{NOA}/\text{EV}$ and $\text{ey}$ on a unit-sum convex weight scale $w_{\text{NOA}}(r_w) \in (0,1)$ in every regime, and standardizing (`winsorize_z`) within active regime cohorts $g_{i,t} = \mathbb{I}(\texttt{stmt\_period}_{i,t} \ge \texttt{"2023Q4"})$ whenever both cohorts have $\ge 5$ stocks eliminates the $2.58\times$ annuity jump between early `2023Q4` IAS 29 filers and late `2023Q3` nominal filers. This fix adds zero parameters and is **bit-for-bit identical ($\max|\Delta| = 1.78 \times 10^{-15}$, `100.00%` identical holdings)** across all 93 Discovery months and all single-regime months.

---

## 3. Why Each Dropped Method Was Excluded

### 3.1 `M1` (`value_usd_3y_sn`) — Dropped (Withdrawn by Author)

Although the referee initially ranked `M1` #4 based on its low turnover (`15.0%`) and low active-deviation correlation (`0.121–0.151`) with `S1`, `M2`, and `FV1`, the referee also flagged its `+65%` surge in Discovery top-20% loss-makers (`ep <= 0`: `9.9% -> 16.3%`) and the `2022Q4–2023Q3` vendor IAS 29 comparative restatement seam. In [`debate/r1_rebuttal_macro.md`](r1_rebuttal_macro.md), the EM/Macro Quant conducted a Discovery-only decomposition that decisively falsified `M1`'s mechanism before any return check:
1. **1-year USD TTM (`u1_sn`) is a `96.91%`-overlapping clone of `R0` (`0.9952` Spearman rank correlation):** Within any single TTM window shared across the cross-section, translating flows by quarterly `USDTRY` and dividing by $\text{MCap}_t / \text{FX}_t$ multiplies every stock by nearly the same macro FX ratio, which cancels out in cross-sectional z-scores.
2. **100% of `M1`'s active divergence comes from 3-year backward averaging, which is an algebraic negative-earnings-growth selector:** By the exact identity $\overline{F}^{\text{USD,3Y}}/\text{MCap}^{\text{USD}} - F^{\text{USD}}_p/\text{MCap}^{\text{USD}} = -\frac{2}{3}\big(F^{\text{USD}}_p - \frac{1}{2}(F^{\text{USD}}_{p-4} + F^{\text{USD}}_{p-8})\big)/\text{MCap}^{\text{USD}}$, `M1` promotes a stock over `R0` if and only if its USD earnings/sales collapsed relative to 1–2 years ago. In Discovery (`lag75`, $N = 932$ swapped stock-months), `Added (M1 \ R0)` entrants have **`83.4%` falling USD net income**, **`79.6%` falling USD operating profit**, **`36.8%` current bottom-line loss-makers (`ep <= 0`)**, **`20.8%` current operating loss-makers (`ey <= 0`)**, and **`3.5%` median ROE**, while `Dropped (R0 \ M1)` ejects growing value stocks (`81.3%` growing USD net income, `15.6%` median ROE).
3. **Unfixable `2022Q4–2023Q3` vendor IAS 29 restatement seam:** In `quarterly.parquet`, `2022Q4–2023Q3` rows are 2024-published IAS 29 first-application comparatives (`1.65x–2.0x` nominal TL). Averaging them with 2020–2022 nominal USD blocks during `2023-03..2024-04` Holdout injects direct restatement look-ahead, while isolating `2022Q4–2023Q3` as a separate 4-quarter regime forces `M1` to collapse to a 1-year USD TTM (`96.9%` identical to `R0`) across 24+ Holdout decision months.

### 3.2 `FV2` (`ccv_sn`) — Dropped (Rejected by Referee & Withdrawn by Author)

1. **Severe distressed working-capital liquidation trap in Discovery:** When a financially distressed firm shrinks, liquidates inventory without restocking, writes down receivables, or stretches unpaid trade payables (`Ticari Borçlar`), $\Delta^{\text{real}}\text{WC}_{i,t} < 0$ inflates $\text{Core\_OCF} = \text{ttm\_core\_op} - \Delta^{\text{real}}\text{WC}$. In Discovery (`2013-04..2020-12`), `FV2` more than **doubled** top-20% net-income loss-makers (`ep <= 0`: **`21.2%`** vs `9.9%` in `R0` and `3.6%` in `S1`), nearly **tripled** operating loss-makers (`ey <= 0`: **`12.3%`** vs `4.6%` in `R0`), and cut median ROE to `8.4%`.
2. **Highest monthly turnover (`18.5%` vs `17.2%` `R0`):** Quarterly working-capital changes are noisy and seasonal, adding `+1.3 pp/mo` of turnover drag under 1M TL liquidity-tier costs.
3. **Unverified `raw/*.pkl` IAS 29 transition & `2025Q2` `reexpression_class` look-ahead risks:** Differencing 4-quarter balance-sheet working capital in `raw/*.pkl` crosses the `2022Q4–2023Q3` vendor comparative restatement boundary and relies on `reexpression_class.parquet` (built from 2025Q2 KAP reports, with 33 companies `unknown`).
4. **Overlap with prior failed Sloan accrual / quality-filter studies (`+0.457` active rank-deviation correlation with rejected `S2`).**

### 3.3 `S2` (`fund_mispricing_hr`) — Dropped (Rejected by Referee & Withdrawn by Author)

1. **Breach of strict Discovery-only specification discipline:** The dependent variable $\ln(M/A)$ (chosen after rejecting $\ln(P/B)$ based on 162-month slope signs), the 6-regressor structure, and the Ridge penalty $\lambda_f = \lambda_s = 5.0$ were selected after inspecting cross-sectional LOO-CV $R^2$ across all 162 months (`2013–2026`), including 2021–2026 Holdout market caps.
2. **Mathematical orthogonality forces universe-level loss-maker contamination (`26.7%` `ep <= 0`, `14.3%` `ey <= 0`, `7.0%` median ROE in Discovery):** Because the Huber-Ridge first-order condition forces the mispricing residual $m_{i,t}$ to be nearly orthogonal to $\text{NI}/A$, $\text{OP}/A$, and $\text{GP}/A$, `S2` strips out `R0`'s earnings-yield protection and admits deeply unprofitable firms whenever their market cap falls faster than a linear function of $\text{NI}/A$. Fixing this would require re-introducing failed `quality x value` or distress filters (`QV1–QV3`, `H4a`).
3. **Lowest coverage (`93.6%`), negative size tilt (`-0.156` rank corr with `log(mcap)` against BIST's `-0.057, t = -2.45` liquid Holdout size IC), and overlap with failed `B2_pb_roe_resid` and `GP/A`/`OP/A` studies.**

---

## 4. Next Steps (Round 2 Execution Protocol)

1. Commit [`docs/research/valuation_round1_preregistration.md`](../docs/research/valuation_round1_preregistration.md), [`data/research/trial_ledger.json`](../data/research/trial_ledger.json) (`N_sel = 89`), and [`debate/r1_decision.md`](r1_decision.md) **before** any backtest runner script is written or executed.
2. In Round 2, implement `scripts/research_valuation_round1.py` following the locked equations in [`docs/research/valuation_round1_preregistration.md`](../docs/research/valuation_round1_preregistration.md) and write the output to `data/reports/research_valuation_round1_2026-11-22.json`.
3. Judge every method strictly by the verbatim **FIXED PASS RULE** with zero post-hoc adjustments.
