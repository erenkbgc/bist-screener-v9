# Round 1 Referee Critique & Risk Audit of Valuation Proposals

**Author role:** Skeptical Risk Quant / Referee  
**Date:** 2026-11-22  
**Branch:** `agent/valuation`  
**Baseline:** Live rule `R0-2026-10-12` — monthly top-20% equal-weighted non-financial portfolio by `value_sn` (`bm`, `ep`, `sp`, `ey`, 1%/99% winsorized cross-sectional z-scores, averaged and demeaned within sector with `min_n = 5`) on the promoted point-in-time panel `data/research/factors_monthly.parquet` (`lag75`; `factors_monthly_kapdates.parquet` for KAP-date sensitivity).  
**Proposals reviewed:**
- `debate/r1_proposal_fundamental.md` (`FV1: reoi_ev_sn`, `FV2: ccv_sn`)
- `debate/r1_proposal_macro.md` (`M1: value_usd_3y_sn`, `M2: value_real_spread_sn`)
- `debate/r1_proposal_statistical.md` (`S1: value_eb_ns`, `S2: fund_mispricing_hr`)

**Referee discipline check:** All independent diagnostics in this critique were computed strictly on **Discovery (2013-04 to 2020-12, 93 months, $N = 20{,}049$ liquid non-financial stock-months)** after dropping the bottom 30% by `tlvol60` (`min_names = 30`). **Zero return columns (`fwd_ret_1m`, `fwd_ret_6m`, `mom_12_1`, `str_1m`) and zero Holdout (2021+) rows were loaded or inspected.**

---

## 1. Executive Summary & Referee Ranking (Recommend 4, Reject 2)

Every method tested under the fixed pass rule permanently increments `N_sel` in `data/research/trial_ledger.json` by `+1` (currently `N_sel = 86`, where full-sample `R0` monthly Sharpe is `0.283`, $V[\widehat{\text{SR}}] = 0.02335$, $\text{SR}_0 = 0.3785$, and $\text{DSR} = 0.103$ — already `NOT_SIGNIFICANT_AFTER_TRIALS`). Spending trial budget on disguised variations of failed studies, distress-contaminated signals, or collinear duplicates destroys statistical power without adding independent shots on goal.

| Rank | Method ID | Short Description | Look-Ahead Risk | Disc. Cov. | Disc. Rank Corr vs `R0` (Mean / Med) | Disc. Top-20% Overlap vs `R0` | Disc. Turnover (`R0`: `17.2%`) | Disc. Top-20% `ep <= 0` (`R0`: `9.9%`) | Disguised Failed Idea? | Referee Decision |
|---:|---|---|---|---:|---:|---:|---:|---:|---|---|
| **1** | **`S1`** | Empirical-Bayes Sector-Standardized Normal-Score Value (`value_eb_ns`) | **None** (100% same PIT inputs as `R0`) | **100.0%** | `0.914` / `0.915` | `78.2%` | **`16.5%`** | **`3.7%`** | **No** (pure estimator & sector-scale fix) | **RECOMMEND (#1)** |
| **2** | **`M2`** | Sovereign-Spread-Conditioned Real Economic Value (`value_real_spread_sn`) | **Low** (CPI lagged $t-1$; month-end Eurobond yield) | **100.0%** | `0.930` / `0.936` | `83.0%` | **`15.6%`** | `11.8%` (`ey<=0`: **`1.6%`**) | **No** (cross-sectional debt charge + `S/EV`) | **RECOMMEND (#2)** |
| **3** | **`FV1`** | Inflation-Consistent Residual Operating Income (`V_ReOI / EV`) | **Low–Mod** (2024Q1–Q2 IAS 29 mixed-hurdle transition seam) | `97.6%` | `0.851` / `0.849` | `70.7%` | **`16.9%`** | `13.3%` | **Borderline** (drops `S/P` like failed `V1`, but unifies `NOA` & `NOPAT` in TL) | **RECOMMEND (#3)** |
| **4** | **`M1`** | Hard-Currency (USD) 3Y Normalized Value (`value_usd_3y_sn`) | **Mod–High in 2023** (`2022Q4–2023Q3` vendor IAS 29 comparative seam) | **100.0%** | `0.873` / `0.861` | `76.9%` | **`15.0%`** | `16.3%` | **No** (3Y USD-CAPE + FX-matched `EV_USD`) | **RECOMMEND (#4, final slot)** |
| **5** | **`FV2`** | Enterprise Cash-Conversion Valuation (`ccv_sn`: `ccey + noa_ev + rev_ev`) | **Mod–High** (`raw/*.pkl` unverified IAS 29 WC jump + 2025Q2 `reexpression_class`) | `97.6%` | `0.694` / `0.694` | `59.7%` | `18.5%` *(highest)* | **`21.2%`** (`ey<=0`: `12.3%`) | **Partial** (Sloan working-capital accrual variant; distress liquidation trap) | **REJECT (Do Not Test)** |
| **6** | **`S2`** | Huber-Ridge Cross-Sectional Fundamental Mispricing (`fund_mispricing_hr`) | **Moderate** ($\lambda=5$ & specification tuned on full 162m incl. 2021–2026 Holdout `mcap`) | `93.6%` *(lowest)* | `0.719` / `0.718` | `60.3%` | `16.8%` | **`26.7%`** (`ey<=0`: `14.3%`) | **Yes** (hybrid of failed `B2_pb_roe_resid`, `QV1–QV3`/`GP/A`, and `learned_weights`) | **REJECT (Do Not Test)** |

---

## 2. Independent Discovery (2013–2020) Non-Return Empirical Audit

To verify every author's claims without touching returns or Holdout data, all six signals were reconstructed from scratch on the **Discovery (2013-04 to 2020-12, 93 months, $N = 20{,}049$ liquid stock-months)** slice of `data/research/factors_monthly.parquet` (`liq_drop_pct = 0.30`, `min_names = 30`).

### 2.1 Discovery (2013–2020) Signal Summary vs. `R0` (`value_sn`)

| Method | Liquid Coverage (2013–2020) | Monthly Spearman Corr vs `R0` (Mean / Med / Min–Max) | Monthly Top-20% Overlap vs `R0` (Mean / Med) | Monthly Top-20% Turnover | Top-20% Share `ep <= 0` | Top-20% Share `ey <= 0` | Top-20% Median `ROE` | Rank Corr with `size = log(mcap)` |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| **`R0` (`value_sn`)** | `100.0%` | `1.000` / `1.000` (`1.000–1.000`) | `100.0%` / `100.0%` | `17.2%` | `9.9%` | `4.6%` | `12.8%` | `+0.062` |
| **`S1` (`value_eb_ns`)** | **`100.0%`** | `0.914` / `0.915` (`0.832–0.941`) | `78.2%` / `78.3%` | **`16.5%`** | **`3.7%`** | **`1.2%`** | **`13.9%`** | `+0.049` |
| **`M2` (`value_real_spread_sn`)** | **`100.0%`** | `0.930` / `0.936` (`0.837–0.966`) | `83.0%` / `83.7%` | **`15.6%`** | `11.8%` | **`1.6%`** | `12.4%` | `+0.076` |
| **`FV1` (`reoi_ev_sn`)** | `97.6%` | `0.851` / `0.849` (`0.739–0.909`) | `70.7%` / `70.7%` | **`16.9%`** | `13.3%` | `6.1%` | `10.5%` | `-0.019` |
| **`M1` (`value_usd_3y_sn`)** | **`100.0%`** | `0.873` / `0.861` (`0.770–0.997`) | `76.9%` / `76.9%` | **`15.0%`** | `16.3%` | `7.6%` | `9.7%` | `+0.059` |
| **`FV2` (`ccv_sn`, $\ge 2$ legs)** | `97.6%` | `0.694` / `0.694` (`0.588–0.775`) | `59.7%` / `60.5%` | `18.5%` | **`21.2%`** | **`12.3%`** | `8.4%` | `-0.060` |
| **`S2` (`fund_mispricing_hr`)** | `93.6%` | `0.719` / `0.718` (`0.660–0.797`) | `60.3%` / `60.0%` | `16.8%` | **`26.7%`** | **`14.3%`** | `7.0%` | **`-0.156`** |

### 2.2 Pairwise Spearman Rank Correlation Matrix (Discovery 2013–2020 Mean Across 93 Months)

| | `R0` | `FV1` | `FV2` | `M1` | `M2` | `S1` | `S2` |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`R0`** | `1.000` | `0.851` | `0.693` | `0.873` | `0.930` | `0.914` | `0.717` |
| **`FV1`** | `0.851` | `1.000` | `0.676` | `0.769` | `0.866` | `0.816` | `0.725` |
| **`FV2`** | `0.693` | `0.676` | `1.000` | `0.713` | `0.701` | `0.667` | `0.680` |
| **`M1`** | `0.873` | `0.769` | `0.713` | `1.000` | `0.832` | `0.812` | `0.711` |
| **`M2`** | `0.930` | `0.866` | `0.701` | `0.832` | `1.000` | `0.886` | `0.682` |
| **`S1`** | `0.914` | `0.816` | `0.667` | `0.812` | `0.886` | `1.000` | `0.759` |
| **`S2`** | `0.717` | `0.725` | `0.680` | `0.711` | `0.682` | `0.759` | `1.000` |

### 2.3 Pairwise Top-20% Portfolio Overlap (`%`) and Active Rank-Deviation Correlation ($\text{Rank}(M) - \text{Rank}(R_0)$) in Discovery (2013–2020)

| Top-20% Overlap `%` \ Active Rank-Diff Corr | `FV1` | `FV2` | `M1` | `M2` | `S1` | `S2` |
|---|---:|---:|---:|---:|---:|---:|
| **`FV1`** | — | `+0.309` | `+0.151` | **`+0.409`** | `+0.206` | `+0.382` |
| **`FV2`** | `59.3%` | — | `+0.341` | `+0.263` | `+0.170` | **`+0.457`** |
| **`M1`** | `64.0%` | `60.1%` | — | `+0.148` | **`+0.121`** | `+0.295` |
| **`M2`** | **`72.1%`** | `60.0%` | `72.3%` | — | `+0.258` | `+0.119` |
| **`S1`** | `67.0%` | `55.4%` | `66.3%` | **`75.2%`** | — | `+0.396` |
| **`S2`** | `59.7%` | `54.0%` | `61.8%` | `59.7%` | `60.6%` | — |

*(Lower triangle: mean monthly Top-20% portfolio overlap `%` in Discovery; Upper triangle: mean monthly Pearson correlation of active rank deviations $\text{pct\_rank}(M) - \text{pct\_rank}(R_0)$ in Discovery.)*

**Key structural finding from Table 2.3:**  
- The two rejected methods (`FV2` and `S2`) have the **highest pairwise active-deviation correlation in the entire pool (`+0.457`)**, and both achieve their low overlap with `R0` (`~60%`) by loading heavily onto **loss-making (`ep <= 0`: `21.2%` and `26.7%`) and operating-loss (`ey <= 0`: `12.3%` and `14.3%`) companies**.
- Conversely, the four recommended methods (`S1`, `M2`, `FV1`, `M1`) span **four distinct economic and statistical mechanisms** with low-to-moderate active-deviation correlations (`0.121` to `0.258` across `S1`, `M1`, `M2`; `0.409` between `FV1` and `M2` is the only moderately coupled pair), all four **reduce monthly turnover** relative to `R0` (`15.0%–16.9%` vs `17.2%`), and none introduces a small-cap tilt.

---

## 3. Method-by-Method Forensic Critique

### 3.1 Rank #1 (RECOMMEND): `S1` — Empirical-Bayes Sector-Standardized Normal-Score Value (`S1_value_eb_ns`)

1. **Look-ahead risk (`NONE`):**  
   `S1` is a pure cross-sectional operator on month $t$'s already-promoted PIT columns (`bm`, `ep`, `sp`, `ey`, `sector`) in `data/research/factors_monthly.parquet`. It uses zero time-series history, zero external macro series, and zero raw `.pkl` items. It is 100% immune to publication-lag leakage, CPI release timing, or vendor restatement seams beyond `R0` itself.
2. **Overlap / correlation with `value_sn` (`R0`) (Discovery 2013–2020):**  
   Mean Spearman rank correlation with `R0` is **`0.914`** (median `0.915`, range `0.832–0.941`), with **`78.2%`** mean top-20% overlap (`21.8%` active switcher share, swapping ~9–10 holdings per month in Discovery). Monthly turnover drops from `17.2%` (`R0`) to **`16.5%`**, reducing transaction-cost drag at 1M TL.
3. **Data coverage & portfolio hygiene:**  
   **`100.0%` coverage** in Discovery (`20,049 / 20,049` rows). Even though `S1` uses zero profitability or quality inputs, replacing asymmetric 1%/99% linear winsorization with per-leg Blom normal scores + two-stage Empirical-Bayes (EB) sector location/scale standardization cuts top-20% net-income loss-makers (`ep <= 0`) from **`9.9%` (`R0`) to `3.7%`** and operating loss-makers (`ey <= 0`) from **`4.6%` to `1.2%`**. In `R0`, an extreme right-tail `sp_z` (`+4.6`) or `bm_z` (`+3.6`) overpowers negative `ep_z` and `ey_z`; under `S1`'s symmetric Gaussian marginals, single-leg distressed outliers cannot enter the top quintile unless other legs concur. Simultaneously, EB within-sector variance shrinkage (`nu_0 = 5`) removes `R0`'s structural over-allocation to high-dispersion sectors (REITs `31.3% -> 24.3%`, Holdings `26.7% -> 21.4%`) and under-allocation to tight industrial sectors (`İmalat` `15.4% -> 21.4%`), directly targeting the within-sector selection engine where Brinson attribution proved 100% of `R0`'s alpha lives (`+10.68%/yr, t = 2.89`).
4. **Disguised failed idea check (`CLEAN`):**  
   Not a disguised failed idea. It does not add failed quality/low-vol/size factors, does not learn return weights, and keeps all four `V0` ratios.
5. **Multiple-testing cost & failure risk:**  
   Adds `+1` to `N_sel` with `0` return-fitted parameters. The main risk is that `78.2%` overlap leaves a `21.8%` switcher portfolio to generate $t(D) \ge 1.0$ in Discovery and $t(D) \ge 2.0$ in Holdout, and rank-normalizing compresses extreme deep-value tail convexity if a handful of distressed high-`B/M` cyclicals rally sharply. Because tracking error $\sigma(D)$ against `R0` is tight and turnover is lower, `S1` has the highest probability of clearing the paired $t(D)$ hurdles cleanly.

---

### 3.2 Rank #2 (RECOMMEND): `M2` — Sovereign-Spread-Conditioned Real Economic Value (`value_real_spread_sn`)

1. **Look-ahead risk (`LOW / CLEAN`):**  
   - **CPI release lag properly enforced:** TÜİK releases month-$t$ CPI on the 3rd business day of month $t+1$. `M2` explicitly lags the target CPI month to $m^*(t) = t - 1\text{ month}$ and defines $\Pi_{p \to t} = I(\max(m_p, m^*(t))) / I(m_p)$, which equals `1.0` whenever a fast KAP filer reports within 30 days of quarter-end. Zero CPI look-ahead.
   - **Eurobond yield PIT integrity:** `eurobond_monthly.parquet` uses market close yields on or before month-end $t$ across the `3–30y` maturity bucket (identical to `core/sovereign_spread.py::median_spread`), known in real time with zero lag.
2. **Overlap / correlation with `value_sn` (`R0`) (Discovery 2013–2020):**  
   Mean Spearman rank correlation with `R0` is **`0.930`** (median `0.936`, range `0.837–0.966`), with **`83.0%`** mean top-20% overlap (`17.0%` active switcher share). Discovery monthly turnover falls by `-1.6 pp/mo` from `17.2%` (`R0`) to **`15.6%`**.
3. **Data coverage & referee mathematical audit:**  
   **`100.0%` coverage** in Discovery (`20,049 / 20,049` rows). Operating loss-makers (`ey <= 0`) in the top quintile fall from `4.6%` (`R0`) to **`1.6%`**. However, the referee notes three structural subtleties that explain why `M2` correlates at `0.930` with `R0`:
   - *Partial cross-sectional cancellation of $\Pi_{p \to t}$:* In any `lag75` month $t$ where >90% of firms share the same active `stmt_period` $p$, $\Pi_{p \to t}$ is a cross-sectional scalar constant on `m2_bm = \Pi_{p \to t} \cdot \text{Eq}_{i,p} / \text{mcap}_{i,t}$ that cancels out inside `winsorize_z`, leaving `m2_bm_z` nearly identical to `bm_z`. ($\Pi_{p \to t}$ does have genuine cross-sectional bite inside $\text{EV}^{\text{real}}_{i,t} = \text{mcap}_{i,t} + \Pi_{p \to t}\text{NetDebt}_{i,p}$ and across mixed-period `kapdates` months.)
   - *Double-weighting operating profit & loss of below-EBIT information:* Both `real_ep_sp` and `ey_real` use $\text{TTM}^{\text{real}}_{\text{op},i,p}$ in the numerator, discarding `ttm_ni_parent`. While this successfully strips IAS 29 non-cash net monetary position gains (which İş Yatırım books inside `(Esas Faaliyet Dışı) Finansal Giderler (-)`, causing a 24.4% sign flip between `ni_parent` and `op_profit` in IAS 29), it also discards equity-method associate income (`Özkaynak Yöntemiyle Değerlenen Yatırımlar` for Holdings) and slightly raises top-20% bottom-line loss-makers (`ep <= 0`: `11.8%` vs `9.9%` in `R0`).
   - *Symmetric leverage amplification when $\text{ey}^{\text{real}} > y^{\text{USD}}_{\text{TR},t}$:* Because $\text{real\_ep}^{\text{sp}} = \text{ey}^{\text{real}} + L^{\text{real}}(\text{ey}^{\text{real}} - y^{\text{USD}}_{\text{TR},t})$, an indebted firm whose trailing operating yield exceeds the sovereign yield (~7%) gets boosted by leverage $L^{\text{real}}$.
4. **Disguised failed idea check (`CLEAN`):**  
   The sovereign spread passed its pre-registered contemporaneous study (`sovereign_spread_preregistration.md`, $t = -8.24$) and failed only as an out-of-sample market-timing predictor. `M2` stays 100% invested and uses $y^{\text{USD}}_{\text{TR},t}$ strictly as a cross-sectional debt-service hurdle, while fixing `S/P`'s leverage distortion via `S/EV` (`sev_real`) rather than dropping sales like failed `V1`.
5. **Multiple-testing cost:**  
   Adds `+1` to `N_sel` with `0` free parameters. Directly addresses Turkey's macro/rate regime shifts and IAS 29 monetary-gain distortion with lower turnover (`15.6%`) and full coverage.

---

### 3.3 Rank #3 (RECOMMEND): `FV1` — Inflation-Consistent Residual Operating Income Valuation (`V_ReOI / EV`)

1. **Look-ahead risk (`LOW in Discovery; MODERATE transition-seam risk in 2024Q1–Q2 Holdout`):**  
   - In Discovery (2013–2020), `policy` (TCMB policy rate at month-end $t$) and `cpi_yoy` (lagged 1 month to $t-1$) from `macro_monthly.parquet` are strictly PIT.
   - **Referee Catch — Cross-sectional hurdle discontinuity during the `2024-01` to `2024-05` IAS 29 transition:** `FV1` sets $r_{w,t} = r_{w,t}^{\text{nom}}$ ($\approx 50\%$) if `stmt_period < "2023Q4"` and $r_{w,t} = r_{w,t}^{\text{real}}$ ($\approx 7.8\%$) if `stmt_period >= "2023Q4"`. Because $V^{\text{ReOI}} / \text{EV} = c_{1,t}(\text{NOA}/\text{EV}) + c_{2,t}\,\text{ey}$ with $c_{1,t} = (1+r_{w,t})^{-5}$ and $c_{2,t} = A(r_{w,t},5)(1-\tau)$, during the 4–5 transition months in early 2024 when early filers have reported `2023Q4` (`c_1 = 0.69`, `c_2 = 3.03`) while late filers in the *same month and sector* are still on `2023Q3` (`c_1 = 0.13`, `c_2 = 1.30`), `FV1` scores early filers with **$2.3\times$ higher earnings weight and $5.3\times$ higher book weight** than late filers! While `lag75` switches most firms together in `2024-04` (`100d` lag for Q4), `kapdates` spreads `2023Q4` filings across February–May 2024.
2. **Overlap / correlation with `value_sn` (`R0`) (Discovery 2013–2020):**  
   Mean Spearman rank correlation with `R0` is **`0.851`** (median `0.849`, range `0.739–0.909`), with **`70.7%`** mean top-20% overlap (`29.3%` active switcher share). Monthly turnover is **`16.9%`** (`-0.3 pp/mo` below `R0`).
3. **Data coverage:**  
   **`97.6%`** in Discovery (`19,561 / 20,049` rows; drops `2.4%` where `EV <= 0` or `ttm_op_profit` is missing). Top-20% `ep <= 0` is `13.3%` (`ey <= 0` is `6.1%`), and size correlation is near zero (`-0.019`).
4. **Disguised failed idea check (`BORDERLINE — Algebraic cousin of V1 no-S/P ablation`):**  
   - **Referee Catch:** Within any month $t$ where all firms share the same accounting regime (100% of Discovery 2013–2020 and 100% of Holdout outside early 2024), $r_{w,t}$ is a **cross-sectional constant**. Consequently, within each month $t$:
     $$\frac{V^{\text{ReOI}}_{i,t}}{\text{EV}_{i,t}} = c_{1}(r_{w,t})\,\frac{\text{NOA}_{i,t}}{\text{EV}_{i,t}} + c_{2}(r_{w,t})\,\text{ey}_{i,t}$$
     is a **two-metric linear combination of `NOA/EV` and `EBIT/EV` (`ey`) that completely drops `S/P` (`sp`) and `E/P` (`ep`)**!
   - On the promoted PIT baseline (`point_in_time_baseline_2026-11-22.md` §4), `sp_sn` has standalone Discovery Rank-IC `+0.0276 (t = 3.41)` and Fama-MacBeth slope `+3.07%/yr (t = 3.11)`, and dropping `S/P` (`V1: bm+ep+ey`) lost **`-3.55%/yr (t = -2.41)` in Discovery** and **`-1.28%/yr` in Holdout**.
   - *Why `FV1` still earns the #3 slot despite dropping `S/P`:* Unlike `V1` (which averaged separate cross-sectional z-scores `bm_z + ep_z + ey_z` with static equal weights), `FV1` combines book capital (`NOA`) and operating profit (`NOPAT`) **additively in raw TL via an explicit cost-of-capital charge ($r_{w,t}\cdot\text{NOA}$) before dividing by `EV` and before z-scoring**, and dynamically adapts the relative weight of book capital vs. earnings as Turkish rates move from 10% to 50% to 8% real.
5. **Multiple-testing cost & redundancy warning:**  
   Adds `+1` to `N_sel` (`0` fitted parameters; $\tau=0.25, \text{ERP}=0.05, T=5$ are pre-existing repo priors). Note that `FV1` and `M2` share a `0.866` rank correlation (`72.1%` top-20% overlap) and `+0.409` active rank-deviation correlation in Discovery; testing both compares a pure Feltham-Ohlson operating model without `S/P` (`FV1`) against a 4-pillar model that retains `S/EV` and conditions debt on the sovereign spread (`M2`).

---

### 3.4 Rank #4 (RECOMMEND — Final 4th Slot): `M1` — Hard-Currency (USD) Through-the-Cycle Normalized Value (`value_usd_3y_sn`)

1. **Look-ahead risk (`CLEAN in Discovery; HIGH VENDOR RESTATEMENT SEAM in 2023–2024 Holdout`):**  
   - In Discovery (2013–2020), all inputs (`quarterly.parquet` with `available_at <= t` and daily `usdtry` from `fx.parquet`) are strictly PIT.
   - **Referee Catch — The `2022Q4–2023Q3` vendor IAS 29 first-application restatement seam:** As documented in `docs/research/first_published_panel.md` (§"Method change", line 47), `undo_reexpression` only undoes vendor CPI re-expression for `period >= 2023Q4`. In `quarterly.parquet`, the periods `2022Q4–2023Q3` are **not** first-published nominal figures — they are the vendor's **IAS 29 first-application restated comparatives** published in 2024 (inflated by `1.65x–2.0x` over original nominal TL). While `M1`'s same-regime rule (`s < 2023Q4` vs `s >= 2023Q4`) prevents `2022Q4–2023Q3` from mixing into `2023Q4+` averages, during Holdout decision months **`2023-03` to `2024-04`** (when latest period $p \in \{\text{2022Q4}, \text{2023Q1}, \text{2023Q2}, \text{2023Q3}\}$), `M1` divides 2024-restated TL flows in block $p$ by contemporaneous 2022–2023 `USDTRY` ($\overline{\text{FX}}_{s-j}$) and averages them with un-restated 2020–2022 nominal USD blocks ($p-4, p-8$)! This over-weights block $p$ by ~`1.7x` in USD terms during 2023 and injects subtle cross-sectional look-ahead variation across companies with different 2023 intrayear inflation profiles.
2. **Overlap / correlation with `value_sn` (`R0`) (Discovery 2013–2020):**  
   Mean Spearman rank correlation with `R0` is **`0.873`** (median `0.861`, range `0.770–0.997`; note `0.997` in 2013-04 when `quarterly.parquet` has only 1 annual block), with **`76.9%`** mean top-20% overlap (`23.1%` active switcher share).
   - **Lowest turnover of all 6 proposals:** Discovery monthly turnover drops to **`15.0%`** (`-2.2 pp/mo` below `R0`'s `17.2%`), because 3-year averaged USD flows smooth out transitory quarterly earnings noise.
   - **Highest orthogonality to other recommended candidates:** In Table 2.3, `M1`'s active rank deviations from `R0` have only **`+0.121`** correlation with `S1`, **`+0.148`** with `M2`, and **`+0.151`** with `FV1`.
3. **Data coverage & Discovery value-trap warning:**  
   **`100.0%` coverage** in Discovery (`20,049 / 20,049` rows). However, our Discovery audit confirms a major fundamental vulnerability: `M1` **increases the top-20% share of current TTM loss-makers (`ep <= 0`) from `9.9%` (`R0`) to `16.3%`** (`+65%` relative jump!) and drops median ROE from `12.8%` to **`9.7%`**. A secularly deteriorating firm that earned positive USD profits 2–3 years ago but is losing money today looks artificially cheap on a 3-year backward average — the exact "value trap while listed (`-1.39%/mo`)" mechanism that hurt Discovery in `survivorship_delisted_preregistration.md`. (Also note that $\text{bm}^{\text{USD}}_{i,t} = \text{bm}_{i,t} \cdot (\text{FX}_t / \text{FX}_{\text{end},p})$ cancels the FX ratio cross-sectionally whenever firms share the same `stmt_period` $p$.)
4. **Disguised failed idea check (`CLEAN`):**  
   Not a disguised failed idea. Multi-year hard-currency cyclically adjusted valuation (USD-CAPE) and FX-matched `EV_USD` are genuinely new to the trial ledger.
5. **Multiple-testing cost:**  
   Adds `+1` to `N_sel` (`0` fitted parameters). Despite its secular-decline trap risk in Discovery and the 2023 restatement seam, `M1`'s low turnover (`15.0%`) and near-orthogonality (`corr ~ 0.12–0.15`) to `S1`, `M2`, and `FV1` justify allocating the 4th and final test slot to it.

---

### 3.5 Rank #5 (REJECT — Do Not Test): `FV2` — Enterprise Cash-Conversion Valuation (`ccv_sn`)

1. **Look-ahead & data-pipeline risk (`MODERATE–HIGH`):**  
   - Unlike the top 4 methods (which run 100% on the audited PIT parquets), `FV2` parses 4 raw lines (`Net Faaliyet Kar/Zararı`, `Ticari Alacaklar`, `Stoklar`, `Ticari Borçlar`) directly from `data/research/raw/*.pkl`.
   - For IAS 29 periods (`>= 2023Q4`), `FV2` relies on `reexpression_class.parquet` to undo vendor Q4 balance-sheet re-expression on working capital. However, `reexpression_class.parquet` was classified from **2025Q2 KAP filings** (introducing classification look-ahead across 2023Q4–2025Q1 and leaving 33 companies as `unknown` vendor-restated). Furthermore, across the `2022Q4–2023Q3` to `2023Q4–2024Q3` boundary, `raw/*.pkl` stores vendor IAS 29 first-application restated comparatives for `2022Q4–2023Q3`, corrupting the 4-quarter real working-capital delta $\Delta^{\text{real}}\text{WC}_{i,t} = \text{WC}_{i,t} - \text{WC}_{i,t-4}\cdot\text{CPI}(p_t)/\text{CPI}(p_{t-4})$.
2. **Overlap / correlation with `value_sn` (`R0`) (Discovery 2013–2020):**  
   Mean Spearman rank correlation with `R0` is **`0.694`** (median `0.694`, range `0.588–0.775`), with **`59.7%`** mean top-20% overlap.
   - **Highest turnover of all 6 proposals:** Discovery monthly turnover jumps to **`18.5%`** (`+1.3 pp/mo` higher than `R0` and `+3.5 pp/mo` higher than `M1`), because quarterly working-capital changes ($\Delta\text{WC}$) are much noisier than book equity or TTM revenue.
3. **Data coverage discrepancy & catastrophic distress contamination in Discovery:**  
   - **Coverage audit:** Under `FV2`'s stated specification requiring $\ge 2$ valid legs (with `EV > 0`, `NOA > 0`, `ttm_revenue > 0`, and 4-quarter lagged `WC`), Discovery coverage is **`97.6%`** (the `99.1%` reported in `r1_proposal_fundamental.md` only holds if the $\ge 2$-leg requirement is relaxed to allow single-leg ranking).
   - **Distressed liquidation trap confirmed on Discovery data:** In Discovery (2013–2020), **`21.2%` of `FV2`'s top-20% picks are bottom-line loss-makers (`ep <= 0`)** (more than **double** `R0`'s `9.9%` and **$5.7\times$** `S1`'s `3.7%`!), **`12.3%` are operating loss-makers (`ey <= 0`)** (nearly **$3\times$** `R0`'s `4.6%` and **$10.3\times$** `S1`'s `1.2%`!), and median ROE plunges from `12.8%` (`R0`) to **`8.4%`**. Why? When a distressed firm shrinks, liquidates inventory without restocking, writes off receivables, or stretches trade payables because it is illiquid, $\Delta^{\text{real}}\text{WC}$ becomes strongly negative, inflating $\text{Core\_OCF} = \text{ttm\_core\_op} - \Delta^{\text{real}}\text{WC}$ and pushing shrinking value traps straight into the top quintile.
4. **Disguised failed idea check (`PARTIAL OVERLAP`):**  
   Sloan working-capital accruals (`core/sloan.py`) and cash-flow/quality overlays (`long_term_preregistration.md`) were already built and relegated to information-only after failing pre-registered tests. Moreover, `FV2`'s active rank deviations from `R0` correlate at **`+0.457`** with `S2` (the highest pair in Table 2.3).
5. **Multiple-testing cost (`REJECT`):**  
   Spending `+1` trial on a high-turnover (`18.5%`), distress-heavy (`21.2%` loss-makers) working-capital accrual signal with `raw/*.pkl` restatement risks is unjustified.

---

### 3.6 Rank #6 (REJECT — Do Not Test): `S2` — Scale-Invariant Huber-Ridge Cross-Sectional Fundamental Mispricing (`S2_fund_mispricing_hr`)

1. **Look-ahead & specification-snooping risk (`MODERATE`):**  
   While each monthly Huber-Ridge regression uses contemporaneous PIT accounting figures (`available_at <= t`), `r1_proposal_statistical.md` (§2.1 lines 110–113, 148 and §2.2 lines 161–169) explicitly discloses that the choice of dependent variable ($\ln(M/A)$ after rejecting $\ln(P/B)$ due to negative slope percentages across 162 months), the 6-regressor functional form, and the Ridge hyperparameter $\lambda_f = \lambda_s = 5.0$ were selected after inspecting **all 162 months (2013–2026, including the 68 Holdout months 2021–2026!)** for LOO-CV $R^2$ (`0.386` at $\lambda=1$, `0.392` at $\lambda=3$, `0.391` at $\lambda=5$, `0.385` at $\lambda=10$) and slope-sign consistency. Because month-$t$ market cap $M_{i,t}$ is the cumulative product of realized stock prices up to month $t$, using 2021–2026 Holdout cross-sections to diagnose and tune the valuation model violates strict Discovery-only design discipline.
2. **Overlap / correlation with `value_sn` (`R0`) (Discovery 2013–2020):**  
   Mean Spearman rank correlation with `R0` is **`0.719`** (median `0.718`, range `0.660–0.797`), with **`60.3%`** mean top-20% overlap (`64.5%` of `S2`'s smaller covered pool) and `16.8%` monthly turnover.
3. **Data coverage, extreme distress contamination, and small-cap tilt in Discovery:**  
   - **Lowest coverage of all 6 proposals:** **`93.6%`** in Discovery (`18,763 / 20,049` rows), dropping **`6.4%`** of the liquid universe (negative equity, zero revenue, or any missing regressor).
   - **Worst loss-maker contamination in the entire pool:** Because the regression residual $m_{i,t} = \widehat{\ln(M/A)}_{i,t} - \ln(M_{i,t}/A_{i,t})$ is forced by IRLS orthogonality to have zero linear covariance with $\text{NI}/A$, $\text{OP}/A$, and $\text{GP}/A$, `S2` strips out the protective earnings floor that `ep` and `ey` provide in `R0`. In Discovery (2013–2020), **`26.7%` of `S2`'s top-20% picks are net-income loss-makers (`ep <= 0`)** (nearly **$3\times$** `R0`'s `9.9%` and **$7.2\times$** `S1`'s `3.7%`!), **`14.3%` are operating loss-makers (`ey <= 0`)** (over **$3\times$** `R0`'s `4.6%` and **$11.9\times$** `S1`'s `1.2%`!), and median ROE collapses from `12.8%` (`R0`) to **`7.0%`**. Any deeply distressed company whose market cap falls faster than a linear function of $\text{NI}/A$ is flagged as a "top-quintile buy".
   - **Toxic small-cap tilt:** `S2` has a **`-0.156` rank correlation with `size` (`log(mcap)`)** in Discovery (versus `+0.062` for `R0` and `+0.049` for `S1`). Per `bist_factor_reconciliation_preregistration.md`, size has a significantly *negative* IC (`-0.057, t = -2.45`) inside the liquid (`liq_drop = 0.30`) Holdout universe.
4. **Disguised failed idea check (`FAIL — Hybrid of THREE previously failed studies`):**  
   - **Failed Idea #1 (`B2_pb_roe_resid` in `financials_holdings_reits_preregistration.md`):** Cross-sectional residual of log valuation multiple on profitability was already tested and failed to beat baseline selection.
   - **Failed Idea #2 (`GP/A`, `OP/A`, `ROE` + value in `long_term_preregistration.md`, `quality_value_lowvol_preregistration.md`, `bist_factor_reconciliation_preregistration.md`):** 19 prior trials in `trial_ledger.json` tested combining gross profitability (`GP/A`), operating profitability (`OP/A`), and `ROE` with value; all failed, with `OP/A` and `ROE` posting negative Fama-MacBeth slopes alongside `value_sn` in Discovery.
   - **Failed Idea #3 (`learned_weights_preregistration.md`):** As shown by `S2`'s own algebraic identity:
     $$m_{i,t} = \hat{\alpha}_t + \hat{\gamma}_{s(i),t} + \hat{\beta}_{1,t} \ln(B/M) + \hat{\beta}_{2,t} \ln(S/M) + (1 - \hat{\beta}_{1,t} - \hat{\beta}_{2,t})\ln(A/M) + \hat{\beta}_{3,t}\frac{\text{OP}}{A} + \hat{\beta}_{4,t}\frac{\text{NI}}{A} + \hat{\beta}_{5,t}\frac{\text{GP}}{A} + \hat{\beta}_{6,t}\frac{\text{ND}}{A}$$
     `S2` is a 40-parameter monthly linear combination of `B/M`, `S/P`, `A/M`, `OP/A`, `NI/A`, `GP/A`, and `NetDebt/A` with time-varying weights learned each month from cross-sectional market caps.
5. **Multiple-testing cost (`REJECT`):**  
   Estimating ~40 parameters every month across ~215 stocks while admitting `26.7%` loss-makers and re-packaging `GP/A` + `OP/A` + `NI/A` + learned weights wastes a ledger trial.

---

## 4. Multiple-Testing Cost & Trial Ledger Budget Analysis

Under the Bailey & López de Prado (2014) Deflated Sharpe Ratio (`core/research_stats.py::deflated_sharpe`) evaluated on the promoted PIT baseline (`T = 161` months, cross-variant monthly Sharpe variance $V[\widehat{\text{SR}}] = 0.02335$ from `point_in_time_baseline_2026-11-22.md`), the expected maximum monthly Sharpe under the null ($\text{SR}_0$) increases monotonically with every trial added to `N_sel`:

| Trial Count `N_sel` | Scenario | Monthly Hurdle $\text{SR}_0$ | Annualized Equivalent $\sqrt{12}\,\text{SR}_0$ | Active Monthly $\widehat{\text{SR}}$ Required for $\text{DSR} \ge 0.95$ (approx.) |
|---:|---|---:|---:|---:|
| `86` | Current ledger (`data/research/trial_ledger.json`) | `0.3785` | `1.3112` | `~0.510` (`R0` is `0.283`, $\text{DSR} = 0.103$) |
| **`87`** | +1 trial (`S1` only) | `0.3791` | `1.3134` | `~0.511` |
| **`88`** | +2 trials (`S1, M2`) | `0.3798` | `1.3156` | `~0.511` |
| **`89`** | +3 trials (`S1, M2, FV1`) | `0.3804` | `1.3177` | `~0.512` |
| **`90`** | **+4 trials (Recommended cap: `S1, M2, FV1, M1`)** | **`0.3810`** | **`1.3198`** | **`~0.513`** |
| `92` | +6 trials (if `FV2` and `S2` were also run) | `0.3822` | `1.3239` | `~0.514` |

**Why capping at 4 trials (`N_sel: 86 -> 90`) and rejecting `FV2` and `S2` is essential:**
1. **The bottleneck is the paired active-return pass rule, not just $\text{SR}_0$:** Each candidate must beat `R0` net of 1M TL liquidity-tier transaction costs with **paired $D > 0$ and NW $t(D) \ge 1.0$ in Discovery (2013–2020, 93m)** AND **paired $D > 0$ and NW $t(D) \ge 2.0$ in Holdout (2021+, 68m)** AND **Holdout USD Max Drawdown not worse than `R0` (`-35.4%`) by more than `2.0 pp` (`>= -37.4%`)**.
2. **Pruning `FV2` and `S2` eliminates the two highest drawdown-and-trap hazards:** Because `R0` already struggles in Discovery when delisted value traps are present (`+5.14%/yr, t = 1.97` baseline; `+3.51%–4.80%` with delisted stocks), any candidate that *doubles or triples* top-20% loss-maker exposure in Discovery (`FV2`: `21.2%`, `S2`: `26.7%` vs `R0`: `9.9%`) or increases turnover (`FV2`: `18.5%`) is structurally set up to fail Discovery $t(D) \ge 1.0$ or breach the Holdout USD drawdown cap while burning `+2` ledger trials.
3. **Orthogonal diversification across the 4 recommended trials:**
   - **`S1` (Statistical / Cross-Sectional Estimator):** Same 4 PIT multiples as `R0`, `100%` coverage, cuts top-20% loss-makers from `9.9%` to `3.7%`, fixes within-sector dispersion balance and the `min_n = 5` cliff, lowers turnover to `16.5%`.
   - **`M2` (Macro-Conditioned Real Economic Value):** `100%` coverage, universal CPI constant-unit TTM (lagged $t-1$), replaces below-the-line FX/IAS 29 monetary noise with Turkey's live USD Eurobond yield hurdle $y^{\text{USD}}_{\text{TR},t} \cdot \text{NetDebt}$, fixes `S/P` leverage via `S/EV`, lowers turnover to `15.6%`.
   - **`FV1` (Fundamental Residual Operating Income):** `97.6%` coverage, closed-form Feltham-Ohlson `V_ReOI / EV` pricing abnormal operating profit above a Fisher-consistent nominal/real hurdle $r_{w,t}$, lowers turnover to `16.9%`.
   - **`M1` (Hard-Currency Multi-Year USD-CAPE):** `100%` coverage, 3-year cyclically adjusted USD flows + FX-matched `EV_USD`, lowest turnover (`15.0%`), and lowest active-deviation correlation (`0.121–0.151`) with `S1`, `M2`, and `FV1`.

---

## 5. Final Referee Recommendation & Mandatory Guardrails for Round 2 Testing

**Advance exactly 4 methods to backtesting (in priority order):**
1. **`S1` (`S1_value_eb_ns`)** — Empirical-Bayes Sector-Standardized Normal-Score Value
2. **`M2` (`value_real_spread_sn`)** — Sovereign-Spread-Conditioned Real Economic Value
3. **`FV1` (`reoi_ev_sn`)** — Inflation-Consistent Residual Operating Income Valuation (`V_ReOI / EV`)
4. **`M1` (`value_usd_3y_sn`)** — Hard-Currency (USD) Through-the-Cycle 3Y Normalized Value

**Reject and exclude from backtesting:**
- **`FV2` (`ccv_sn`)** — Rejected (`21.2%` Discovery loss-makers, highest turnover `18.5%`, `raw/*.pkl` IAS 29 working-capital transition risk, Sloan accrual overlap).
- **`S2` (`fund_mispricing_hr`)** — Rejected (`93.6%` coverage, `26.7%` Discovery loss-makers, `-0.156` small-cap tilt, full-sample specification snooping, hybrid of failed `B2_pb_roe_resid` + `GP/A`/`OP/A` + `learned_weights`).

**Mandatory Execution Protocol for Round 2:**
- All 4 approved methods must be evaluated using the exact portfolio simulator and cost model in `scripts/research_portfolio_backtest.py` (1M TL real capital, base costs, next-close fills, same liquid non-financial universe `liq_drop_pct = 0.30`) against `R0` (`value_sn` top 20%), with primary evaluation on `data/research/factors_monthly.parquet` (`lag75`) and sensitivity reported on `data/research/factors_monthly_kapdates.parquet`.
- No formula, parameter, or threshold in `S1`, `M2`, `FV1`, or `M1` may be modified after viewing returns.
- Increment `N_sel` by `+4` (`86 -> 90`) in `data/research/trial_ledger.json` and report DSR at `N_sel = 90` ($\text{SR}_0 = 0.3810$ monthly at $V[\widehat{\text{SR}}] = 0.02335$).
