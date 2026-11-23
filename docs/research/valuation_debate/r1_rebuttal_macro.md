# Round 1 Rebuttal — EM / Turkey Macro-Adjusted Quant

**Author role:** Author of `debate/r1_proposal_macro.md` (EM / Turkey-specific Quant)  
**Date:** 2026-11-22  
**Branch:** `agent/valuation`  
**Responding to:** `debate/r1_critique.md` (and reviewed against `debate/r1_proposal_fundamental.md`, `debate/r1_proposal_statistical.md`, `debate/r1_rebuttal_fundamental.md`, `debate/r1_rebuttal_statistical.md`)  
**Discipline check:** Every new diagnostic reported in this rebuttal was computed strictly on **Discovery (`2013-04` to `2020-12`, 93 months)** after the standard `liq_drop_pct = 0.30` / `min_names = 30` cut (`lag75`: $N = 20{,}049$; `kapdates`: $N = 20{,}088$). **Zero return columns (`fwd_ret_1m`, `fwd_ret_6m`, `mom_12_1`, `str_1m`, `vol60`) and zero Holdout (`2021+`) rows were loaded or inspected.**

---

## Executive Disposition Summary

| Method | Referee Verdict | Author Rebuttal Action | Trial-Budget Impact (`N_sel`) | Core Reason |
|---|---|---|---|---|
| **`M2` (`value_real_spread_sn`)** | **RECOMMEND (#2)** | **DEFEND UNCHANGED** (lock exact formula for Round 2; provide Discovery-only switcher & spread-regime audit) | **`+1`** | Zero look-ahead (CPI strictly lagged to $m^*(t) = t-1$; month-end `3–30y` USD Eurobond yield), `100.0%` coverage (`lag75` & `kapdates`), zero fitted parameters, lower turnover (`15.6%–16.1%` vs `17.2%` `R0`), and cuts top-20% operating loss-makers (`ey <= 0`) from `4.5%` to **`1.0%–1.6%`**. Discovery switcher anatomy proves `M2` ejects heavily indebted `R0` traps (`med NetDebt/MCap = +85.2%`, `22.0%` `ey <= 0`, `med ey = 6.9%`) and replaces them with net-cash / low-debt operating earners (`med NetDebt/MCap = +5.6%`, `43.2%` net cash, `1.6%` `ey <= 0`, `med ey = 14.0%`), with `90.1%` of `M2`'s `ep <= 0` entrants being operating-profitable (`ey > 0`). |
| **`M1` (`value_usd_3y_sn`)** | **RECOMMEND (#4, final slot)** | **WITHDRAW** (do not test in Round 2; save 1 trial) | **`+0`** *(saves 1 trial)* | Concede the referee's two catches (`2022Q4–2023Q3` vendor IAS 29 comparative restatement seam and `+65%` jump in Discovery top-20% `ep <= 0` from `9.9%` to `16.4%`), and report a deeper Discovery switcher proof: because 1-year USD TTM (`u1_sn`) has **`96.91%` top-20% overlap (`0.9952` rank corr) with `R0`**, 100% of `M1`'s active divergence comes from 3-year backward averaging, which is algebraically identical to selecting on **negative 2-year USD earnings growth** ($-\Delta F^{\text{USD}}/\text{MCap}^{\text{USD}}$). In Discovery, `Added (M1 \ R0)` consists of **`83.4%` falling-earnings firms**, **`36.8%` current bottom-line loss-makers (`ep <= 0`)**, **`20.8%` operating loss-makers (`ey <= 0`)**, and **`3.5%` median ROE** (while dropping `81.3%` growing-earnings firms with `15.6%` median ROE). |

---

## 1. Method `M2` (`value_real_spread_sn`): Defense Unchanged & Discovery Switcher Audit

The referee ranked `M2` **#2 overall**, confirming its clean point-in-time construction (TÜİK CPI lagged to $m^*(t) = t - 1\text{ month}$, month-end `3–30y` Turkey USD Eurobond median yield $y^{\text{USD}}_{\text{TR},t}$), `100.0%` liquid coverage, lower Discovery turnover than `R0`, and sharp reduction in operating loss-makers (`ey <= 0`), while noting three structural subtleties (§3.2.3):
1. Partial cross-sectional cancellation of $\Pi_{p \to t}$ on `bm_real` in single-period `lag75` months;
2. Double-weighting operating profit ($\text{TTM}^{\text{real}}_{\text{op},i,p}$) across `real_ep_sp` and `ey_real` (discarding below-the-line `ttm_ni_parent` and slightly raising top-20% `ep <= 0` from `9.8%` to `11.7%`); and
3. Potential leverage amplification when $\text{ey}^{\text{real}}_{i,t} > y^{\text{USD}}_{\text{TR},t}$.

We address all three points below using strictly Discovery-only (`2013-04` to `2020-12`, 93 months, zero return columns) empirical diagnostics on both `lag75` and `kapdates`.

### 1.1 Discovery-Only (`2013-04`–`2020-12`, 93m) Summary & Switcher Anatomy (`lag75` & `kapdates`)

| Discovery (`2013-04`–`2020-12`, 93m) Bucket | Panel | $N$ | `NetDebt/MCap > 100%` | Med `NetDebt/MCap` | Net Cash (`ND < 0`) | Med `bm` | Med `sp` | Med `ey` (`EBIT/EV`) | Med `ep` | `ey <= 0` | `ep <= 0` | `ey > 0` & `ep <= 0` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Full Top-20% `R0` (`value_sn`)** | `lag75` | `3,975` | `30.6%` | `+48.1%` | `23.6%` | `1.32` | `2.15` | `15.2%` | `13.3%` | `4.5%` | `9.8%` | `8.1%` |
| **Full Top-20% `M2` (`value_real_spread_sn`)** | `lag75` | `3,975` | **`26.5%`** | **`+33.8%`** | **`29.3%`** | `1.20` | `2.04` | **`16.5%`** | `12.0%` | **`1.0%`** | `11.7%` | `10.8%` |
| Liquid Universe | `lag75` | `20,049` | `18.4%` | `+24.2%` | `25.3%` | `0.71` | `0.95` | `6.7%` | `5.1%` | `16.3%` | `26.8%` | `14.0%` |
| Overlap (`R0 ∩ M2`, `82.5%`) | `lag75` | `3,279` | `27.7%` | `+41.4%` | `26.3%` | `1.30` | `2.17` | `17.0%` | `13.1%` | `0.8%` | `8.4%` | `7.8%` |
| **Dropped (`R0 \ M2`)** | `lag75` | **`696`** | **`44.3%`** | **`+85.2%`** | **`10.8%`** | `1.45` | `2.01` | **`6.9%`** | `14.3%` | **`22.0%`** | `16.4%` | `9.2%` |
| **Added (`M2 \ R0`)** | `lag75` | **`696`** | **`20.8%`** | **`+5.6%`** | **`43.2%`** | `0.84` | `1.53` | **`14.0%`** | `7.3%` | **`1.6%`** | `27.4%` | **`24.7%`** |
| **Dropped (`R0 \ M2`)** | `kapdates` | **`687`** | **`42.1%`** | **`+82.9%`** | **`11.4%`** | `1.42` | `2.06` | **`6.8%`** | `15.1%` | **`22.4%`** | `17.3%` | `9.9%` |
| **Added (`M2 \ R0`)** | `kapdates` | **`687`** | **`19.7%`** | **`+4.7%`** | **`44.4%`** | `0.83` | `1.53` | **`14.3%`** | `7.3%` | **`2.6%`** | `27.7%` | **`24.3%`** |

*(Note: minor 0.3–0.5 pp differences vs `r1_critique.md` Table 2.1 — e.g., `82.5%` vs `83.0%` overlap and `1.0%` vs `1.6%` `ey <= 0` — come solely from whether the 3 monthly CPI values inside quarter $k$ are averaged before or after month-end alignment; under either convention, Discovery coverage is `100.0%`, Spearman correlation with `R0` is `0.927–0.930`, and monthly turnover drops by `-1.1` to `-1.6 pp/mo` below `R0`.)*

### 1.2 Direct Answers to the Referee's Three Structural Notes on `M2`

1. **Where $\Pi_{p \to t}$ and intra-year CPI restatement exert genuine cross-sectional bite:**  
   The referee rightly observes that in any `lag75` month where most firms share the same active `stmt_period` $p$, the staleness factor $\Pi_{p \to t} = I(\max(m_p, m^*(t)))/I(m_p)$ is a common multiplier on $\text{bm}^{\text{real}}_{i,t} = \Pi_{p \to t}\text{Eq}_{i,p}/\text{mcap}_{i,t}$ that cancels inside `winsorize_z`. Keeping $\Pi_{p \to t}$ across all four ratios and $\text{EV}^{\text{real}}_{i,t}$ is nevertheless essential for three reasons:
   - **Inside $\text{EV}^{\text{real}}_{i,t} = \text{mcap}_{i,t} + \Pi_{p \to t}\text{NetDebt}_{i,p}$:** $\Pi_{p \to t}$ scales `NetDebt_p` relative to current `mcap_t`, which **never** cancels cross-sectionally because leverage $\text{NetDebt}_{i,p}/\text{mcap}_{i,t}$ varies across stocks. During high-inflation windows (2018Q3, 2021Q4–2026), carrying `NetDebt_p` forward by $\Pi_{p \to t}$ prevents stale historical-cost net debt from understating enterprise value on highly leveraged firms.
   - **Across mixed-filing months (`kapdates` & Q4/Q1 transitions):** On `factors_monthly_kapdates.parquet`, **100.0% of Discovery months** contain multiple active `stmt_period` cohorts (`12.0%` of the liquid cross-section is on a non-modal quarter in an average month; `53.8%` of `lag75` months also have $>1$ active quarter). $\Pi_{p \to t}$ puts early filers (with fresh $p$) and late filers (still on $p-1$) into the exact same month-$t$ purchasing power.
   - **Intra-year quarterly CPI restatement ($\text{TTM}^{\text{real}}_{X,i,p} = \sum_{j=0}^3 q_{X,i,p-j}\,I(m_p)/\overline{I}_{p-j}$):** Even when two firms share the same `stmt_period` $p$, weighting Q1–Q4 nominal flows by $I(m_p)/\overline{I}_{p-j}$ re-weights early vs. late quarters inside the TTM according to inflation, differentiating firms with front-loaded vs. back-loaded seasonal earnings/revenue across 2013–2023Q3.

2. **Why `M2`'s slightly higher `ep <= 0` (`11.7%` vs `9.8%` in `R0`) is a feature, not operating distress:**  
   Look at the last three columns of Table 1.1 for the active switcher portfolio (`M2 \ R0` vs `R0 \ M2`):
   - In **`Dropped (R0 \ M2)`** ($N = 696$), **`22.0%` are losing money at the operating line (`ey <= 0`)** (`22.4%` on `kapdates`) — well above the random universe base rate (`16.3%`) — and median operating yield is just **`6.9%`**.
   - In **`Added (M2 \ R0)`** ($N = 696$), operating loss-makers plunge **$13.8\times$ to just `1.6%`** (`2.6%` on `kapdates`), and median operating yield **doubles to `14.0%`** (`14.3%` on `kapdates`)!
   - Why do `27.4%` of `Added (M2 \ R0)` have negative GAAP net income (`ep <= 0`) when only `1.6%` have negative operating profit (`ey <= 0`)? Because **`24.7%` out of `27.4%` (`90.1%` of all `ep <= 0` entrants!) sit in the `ey > 0 & ep <= 0` bucket**: they are **strongly profitable operating businesses (`med ey = 14.0%`) with near-zero or net-cash balance sheets (`43.2%` net cash, `med NetDebt/MCap = +5.6%`)** whose bottom-line GAAP net income (`ep`) was temporarily pushed below zero by non-operating/financing items (and in 2024+ by IAS 29 non-cash net monetary position losses on net-cash firms). We explicitly accept the omission of equity-method associate income (`Özkaynak Yöntemiyle Değerlenen Yatırımlar`) as `M2`'s clean, pre-registered fundamental trade-off.

3. **Why leverage amplification when $\text{ey}^{\text{real}} > y^{\text{USD}}_{\text{TR},t}$ does NOT tilt `M2` toward high-debt firms in practice:**  
   The referee noted that in $\text{real\_ep}^{\text{sp}} = \text{ey}^{\text{real}} + L^{\text{real}}(\text{ey}^{\text{real}} - y^{\text{USD}}_{\text{TR},t})$, a leveraged firm with $\text{ey}^{\text{real}} > y^{\text{USD}}_{\text{TR},t}$ receives a positive leverage term on the `real_ep_sp` leg. However, across the 4-leg composite (`bm_real`, `real_ep_sp`, `sev_real`, `ey_real`), `M2` simultaneously (a) strips the $(1 + L)$ leverage multiplier out of `S/P` by replacing `Sales / MCap` with unlevered `Sales / EV_real` (`sev_real`), (b) inflates `NetDebt` by $\Pi_{p \to t}$ inside the `EV_real` denominator of both `sev_real` and `ey_real`, and (c) charges $y^{\text{USD}}_{\text{TR},t} \cdot \text{NetDebt}$ on `real_ep_sp`.  
   Empirically in Discovery (Table 1.1):
   - Full top-20% median `NetDebt / MCap` **falls** from `+48.1%` (`R0`) to **`+33.8%` (`M2`)**, and net-cash holdings rise from `23.6%` to **`29.3%`**.
   - Across the `696` swapped stock-months (`Dropped R0 \ M2` vs `Added M2 \ R0`), median `NetDebt / MCap` drops **$15\times$ from `+85.2%` to `+5.6%`** (`+82.9% -> +4.7%` on `kapdates`), `NetDebt > MCap` falls more than in half (`44.3% -> 20.8%`), and net-cash share quadruples (`10.8% -> 43.2%`).
   - Splitting Discovery into **Calm spreads (`2013–2017`, median $y^{\text{USD}}_{\text{TR},t} = 5.83\%$)** and **FX/Sovereign-Stress spreads (`2018–2020`, median $y^{\text{USD}}_{\text{TR},t} = 7.25\%$)** confirms the exact regime-conditioning mechanism: when sovereign spreads widen in `2018–2020`, the median `NetDebt / MCap` of the `R0` picks ejected by `M2` (`Dropped R0 \ M2`) rises from `+77.4%` (`2013–2017`) to **`+109.0%`** (`2018–2020`, vs `+29.2%` for `Added M2 \ R0` with `39.1%` net cash and `1.5%` `ey <= 0`).
   - Finally, unlike `FV1` (which needed a transition fix because its hurdle rate jumped from $50\%$ nominal to $7.8\%$ real at `2023Q4`), `M2` expresses **every** period from 2013 to 2026 in real constant purchasing power and always applies the real USD sovereign yield $y^{\text{USD}}_{\text{TR},t}$ (`~5%–11%`), so `M2` has **zero discount-rate discontinuity** at the `2023Q4` IAS 29 boundary.

### 1.3 Exact Deterministic Specification of `M2` Locked for Round 2

To guarantee zero ambiguity in Round 2 execution:
- **Universe:** Exact `R0` liquid non-financial cross-section (`tlvol60 > 0`, `tlvol60 >= quantile(0.30)`, `min_names = 30`).
- **Strictly PIT CPI index & staleness factor $\Pi_{p \to t}$:** From `data/research/macro_monthly.parquet`, $I(m) = \prod_{\tau \le m}(1 + \text{cpi\_mom}_\tau/100)$. For rebalance date $t$, let $m^*(t) = t - 1\text{ month}$ (calendar month strictly prior to $t$) and $m_p = \text{period\_end}(p)$'s calendar month. Set $\Pi_{p \to t} = I(\max(m_p, m^*(t))) / I(m_p)$.
- **Constant period-$p$-end purchasing-power TTM flows ($\text{TTM}^{\text{real}}_{X,i,p}$, $X \in \{\text{rev}, \text{op}\}$):**
  - If `stmt_period < "2023Q4"`: require 4 consecutive discrete quarters $p-3, p-2, p-1, p$ (`period_end` gaps in $[80, 100]$ days); let $\overline{I}_k$ be the arithmetic mean of the 3 monthly CPI index levels $I(m)$ in calendar quarter $k$; compute $\text{TTM}^{\text{real}}_{X,i,p} = \sum_{j=0}^3 q_{X,i,p-j} \cdot \big(I(m_p)/\overline{I}_{p-j}\big)$.
  - If `stmt_period >= "2023Q4"`: use `ttm_revenue` and `ttm_op_profit` directly from `data/research/quarterly.parquet` (`C1` + `bridge_ttm`).
- **Strictly PIT Turkey USD Sovereign Yield $y^{\text{USD}}_{\text{TR},t}$:** From `data/research/eurobond_monthly.parquet`, take the month-$t$ snapshot (`date <= t`) of all bonds with remaining maturity $3.0 \le (\text{maturity} - \text{date})/365.25 \le 30.0$ years; $y^{\text{USD}}_{\text{TR},t} = \operatorname{median}_{b \in \mathcal{B}_t}(\text{yield}_{b,t}) / 100$.
- **Four Valuation Ratios (`Eq` = `equity_parent` with fallback to `equity`; `NetDebt` = `fin_debt - cash`, `NaN` if either missing):**
  $$\text{EV}^{\text{real}}_{i,t} = \text{mcap}_{i,t} + \Pi_{p \to t}\cdot\text{NetDebt}_{i,p}$$
  $$\text{bm}^{\text{real}}_{i,t} = \frac{\Pi_{p \to t}\cdot\text{Eq}_{i,p}}{\text{mcap}_{i,t}} \;\; (\text{if } \text{Eq}_{i,p} > 0), \qquad \text{real\_ep}^{\text{sp}}_{i,t} = \frac{\Pi_{p \to t}\cdot\big(\text{TTM}^{\text{real}}_{\text{op},i,p} - y^{\text{USD}}_{\text{TR},t}\cdot\text{NetDebt}_{i,p}\big)}{\text{mcap}_{i,t}}$$
  $$\text{sev}^{\text{real}}_{i,t} = \frac{\Pi_{p \to t}\cdot\text{TTM}^{\text{real}}_{\text{rev},i,p}}{\text{EV}^{\text{real}}_{i,t}} \;\; (\text{if } \text{EV}^{\text{real}}_{i,t} > 0), \qquad \text{ey}^{\text{real}}_{i,t} = \frac{\Pi_{p \to t}\cdot\text{TTM}^{\text{real}}_{\text{op},i,p}}{\text{EV}^{\text{real}}_{i,t}} \;\; (\text{if } \text{EV}^{\text{real}}_{i,t} > 0)$$
- **Composite & Portfolio (identical to `R0`):** Per month $t$, winsorize each of the 4 ratios at 1%/99% and z-score (`fb.winsorize_z(..., 0.01, 0.99)`), average available leg z-scores (`mean(axis=1)`), apply `fb.sector_neutralize(..., min_n=5)`, and hold the monthly top 20% (`rank(ascending=False, pct=True) <= 0.20`), equal-weighted, evaluated in `scripts/research_portfolio_backtest.py` (1M TL real capital, base costs, next-close fills), primary on `factors_monthly.parquet` (`lag75`) and sensitivity on `factors_monthly_kapdates.parquet`.

---

## 2. Method `M1` (`value_usd_3y_sn`): Formal Withdrawal & Mathematical Post-Mortem

**Decision: We formally WITHDRAW `M1` (`value_usd_3y_sn`) from Round 2 testing (`+0` to `N_sel`).**

Although the referee generously allocated the 4th and final recommendation slot (`#4`) to `M1` on the strength of its low monthly turnover (`15.0%`) and low active-deviation correlation (`0.121–0.151`) with `S1`, `M2`, and `FV1`, the referee also flagged **two severe vulnerabilities** (§3.4.1 & §3.4.3):
1. **The `2022Q4–2023Q3` vendor IAS 29 first-application comparative restatement seam** (`Mod–High` look-ahead/restatement risk in 2023 Holdout); and
2. **A `+65%` surge in Discovery top-20% loss-makers (`ep <= 0`: `9.9% -> 16.3%`, `ey <= 0`: `4.6% -> 7.6%`, median ROE `12.8% -> 9.7%`)** caused by 3-year backward USD averaging making secularly decaying firms look artificially cheap.

When we subjected `M1` to the exact same Discovery-only (`2013-04` to `2020-12`, 93 months, zero return columns) switcher audit as `S1`, `FV1`, and `M2`, we uncovered an algebraic identity and an empirical switcher pathology that make testing `M1` scientifically indefensible at `N_sel = 86` (`DSR = 0.103`).

### 2.1 Discovery Switcher Proof: Why `M1`'s Active Bet Is a Pure Negative-Earnings-Growth / Value-Trap Selector

First, we tested how much of `M1`'s divergence from `R0` in Discovery comes from **1-year hard-currency USD translation + FX-matched `EV_USD`** (`u1_sn`: using 1-year $F^{\text{USD}}_{X,i,p}$ instead of 3-year $\overline{F}^{\text{USD,3Y}}_{X,i,p}$) versus how much comes from **3-year backward averaging (`{p, p-4, p-8}`)**.  
On Discovery (`2013-04` to `2020-12`, 93 months, `lag75`):
- **1-year USD TTM + FX-matched `EV_USD` (`u1_sn`) has a `0.9952` mean Spearman rank correlation and `96.91%` top-20% overlap with `R0`!**  
  Why? Because within any single 4-quarter TTM window shared across the cross-section, translating quarterly flows by $\overline{\text{FX}}_{p-j}$ and dividing by $\text{MCap}_{i,t}/\text{FX}_t$ multiplies every stock's flow yield by virtually the same macro FX ratio $\text{FX}_t/\overline{\text{FX}}_p$, which cancels out inside `fb.winsorize_z` (just as $\text{bm}^{\text{USD}}_{i,t} = \text{bm}_{i,t}\cdot(\text{FX}_t/\text{FX}_{\text{end},p})$ cancels whenever firms share `stmt_period` $p$).
- Consequently, **nearly 100% of `M1`'s active divergence from `R0` (`76.9%` overlap vs `96.9%` for 1-year USD) comes from averaging year-0 ($p$) with year-1 ($p-4$) and year-2 ($p-8$)**.

Now look at the exact algebraic difference between a 3-year equal-weighted USD flow yield and a 1-year USD flow yield:
$$\frac{\overline{F}^{\text{USD,3Y}}_{X,i,p}}{\text{MCap}^{\text{USD}}_{i,t}} - \frac{F^{\text{USD}}_{X,i,p}}{\text{MCap}^{\text{USD}}_{i,t}} = -\frac{2}{3}\,\frac{F^{\text{USD}}_{X,i,p} - \tfrac{1}{2}\big(F^{\text{USD}}_{X,i,p-4} + F^{\text{USD}}_{X,i,p-8}\big)}{\text{MCap}^{\text{USD}}_{i,t}}$$
**By an exact mathematical identity, `M1`'s active rank deviation from 1-year value (`R0`) is strictly proportional to MINUS the firm's recent 1-to-2-year USD earnings/sales change!**
- A stock enters **`Added (M1 \ R0)`** if and only if its USD profits 1–2 years ago ($p-4, p-8$) were much *higher* than its current TTM USD profits ($p$) — i.e., **collapsing earnings**!
- A stock falls into **`Dropped (R0 \ M1)`** if and only if its current TTM USD profits ($p$) are much *higher* than 1–2 years ago — i.e., **growing earnings**!

#### Table 2.1 — Discovery Switcher Anatomy of `M1` vs. `R0` (`2013-04`–`2020-12`, 93m, `lag75` & `kapdates`)

| Discovery Bucket | Panel | $N$ | Current `ep <= 0` | Current `ey <= 0` | Med `ROE` | Med 1Y USD `ep` (`y0`) | Med 3Y USD `ep` | Med 1Y USD `ey` (`y0`) | Med 3Y USD `ey` | Share `NI_USD(p) < NI_USD(p-4)` | Share `OP_USD(p) < OP_USD(p-4)` | Share `Rev_USD(p) < Rev_USD(p-4)` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Liquid Universe | `lag75` | `20,049` | `26.8%` | `16.3%` | `8.4%` | `5.1%` | `6.1%` | `6.7%` | `7.9%` | `53.2%` | `52.4%` | `53.8%` |
| Overlap (`R0 ∩ M1`, `76.9%`) | `lag75` | `3,043` | `10.1%` | `3.6%` | `11.3%` | `12.8%` | `14.1%` | `15.4%` | `16.4%` | `46.5%` | `46.3%` | `52.1%` |
| **Dropped (`R0 \ M1`)** | `lag75` | **`932`** | **`8.7%`** | **`7.6%`** | **`15.6%`** | **`16.2%`** | `7.7%` | **`15.3%`** | `9.9%` | **`18.7%`** *(`81.3%` growing)* | **`21.2%`** *(`78.8%` growing)* | `39.4%` |
| **Added (`M1 \ R0`)** | `lag75` | **`932`** | **`36.8%`** | **`20.8%`** | **`3.5%`** | **`4.3%`** | `17.0%` | **`7.3%`** | `16.1%` | **`83.4%` falling** | **`79.6%` falling** | **`76.9%` falling** |
| **Dropped (`R0 \ M1`)** | `kapdates` | **`956`** | **`8.6%`** | **`7.6%`** | **`15.7%`** | **`16.3%`** | `7.8%` | **`15.4%`** | `9.9%` | **`18.5%`** *(`81.5%` growing)* | **`21.0%`** *(`79.0%` growing)* | `39.1%` |
| **Added (`M1 \ R0`)** | `kapdates` | **`956`** | **`36.6%`** | **`20.7%`** | **`3.4%`** | **`4.3%`** | `16.9%` | **`7.3%`** | `16.0%` | **`83.1%` falling** | **`79.5%` falling** | **`76.6%` falling** |

Look at what Table 2.1 reveals about `M1`'s `23.1%` active switcher bet (`Added M1 \ R0` vs `Dropped R0 \ M1`):
1. **Even worse active loss-maker contamination than rejected `FV2` (`21.2%`) and `S2` (`26.7%`):**  
   In `M1`'s active entrants (`Added M1 \ R0`, $N = 932$), **`36.8%` are bottom-line loss-makers (`ep <= 0`)** and **`20.8%` are operating loss-makers (`ey <= 0`)** (`56.5%` of the `ep <= 0` entrants are losing money at the operating line too, unlike `M2` where `90.1%` of `ep <= 0` entrants had positive operating profit!), while median `ROE` collapses **$4.5\times$ from `15.6%` (`Dropped R0 \ M1`) to `3.5%` (`Added M1 \ R0`)**. This toxic `36.8%` entrant loss-maker rate was partially masked in the full top-20% average (`16.4%`) only because `M1` shares `76.9%` overlap with `R0`.
2. **Directly bets against BIST's documented positive SUE / earnings-growth effect (`+0.040 IC, t = 5.6`):**  
   In `Added (M1 \ R0)`, **`83.4%` of entrants have falling year-over-year USD net income**, **`79.6%` have falling USD operating profit**, and **`76.9%` have falling USD revenue** (current 1-year USD `ep` is only `4.3%` vs a stale 3-year average of `17.0%`). Conversely, in `Dropped (R0 \ M1)`, `M1` sells profitable `R0` holdings where **`81.3%` have growing USD net income** and **`78.8%` have growing USD operating profit** (`med ROE = 15.6%`, current 1-year USD `ep = 16.2%`). In an economy with high survivorship drag from decaying value traps (`-1.39%/mo` while listed in `survivorship_delisted_preregistration.md`) and strongly positive SUE (`README.md` line 550), selling growing-earnings value stocks to buy shrinking-earnings loss-makers is a direct structural defect.

### 2.2 Why the `2022Q4–2023Q3` Vendor IAS 29 Restatement Seam Cannot Be Patched Without Degeneracy

The referee also caught (§3.4.1) that in `data/research/quarterly.parquet`, `undo_reexpression` only applies to `period >= 2023Q4` (`first_published_panel.md` line 47): the periods `2022Q4–2023Q3` are vendor **IAS 29 first-application restated comparatives** published in 2024 (inflated by `1.65x–2.0x` over original nominal TL).
- Under `M1`'s original two-regime split (`< 2023Q4` vs `>= 2023Q4`), decision months `2023-03` to `2024-04` divide 2024-restated `2022Q4–2023Q3` TL flows by 2022–2023 `USDTRY` and average them with un-restated 2020–2022 nominal USD blocks ($p-4, p-8$), injecting `1.65x–2.0x` restatement look-ahead into year-0.
- What if one attempted an ex-ante fix by partitioning statement periods into **three** disjoint accounting regimes — $g(s) = 0$ (`s < 2022Q4`, pure nominal), $g(s) = 1$ (`2022Q4 <= s <= 2023Q3`, vendor IAS 29 comparative), and $g(s) = 2$ (`s >= 2023Q4`, `C1` + `undo_reexpression`) — and restricting lagged blocks $s \in \{p, p-4, p-8\}$ to share the exact same regime $g(s) = g(p)$?
  - Because regime $g = 1$ (`2022Q4–2023Q3`) is only **4 quarters long**, $p-4$ is *never* in $g = 1$ when $p \in g = 1$, and when $p \in \{\text{2023Q4}, \text{2024Q1}, \text{2024Q2}, \text{2024Q3}\}$ ($g = 2$), $p-4 \in g = 1$ is excluded too!
  - Thus, fixing the `2022Q4–2023Q3` seam forces $|S_{X,i,p}| \equiv 1$ (collapsing `M1` to a 1-year USD TTM that is **`96.9%` identical to `R0`**) across **8 consecutive quarters (`24+` decision months from `2023-03` to `2025-04`)** — over one-third of the 68-month Holdout!
- Similarly, any attempt to fix `M1`'s `36.8%` entrant loss-maker rate in Discovery by filtering out `ep <= 0` or down-weighting lagged blocks when $F^{\text{USD}}_p < F^{\text{USD}}_{p-4}$ either (a) introduces a prohibited quality/distress/SUE filter (`long_term_preregistration.md`, `quality_value_lowvol_preregistration.md`) or (b) collapses `M1` back to the `96.9%`-overlapping 1-year USD TTM clone of `R0`.

Therefore, **withdrawing `M1` is the only scientifically rigorous decision**.

---

## 3. Updated Round 2 Trial-Ledger Budget: 3 Orthogonal Finalists (`N_sel: 86 -> 89`)

With `S2` withdrawn in `debate/r1_rebuttal_statistical.md`, `FV2` withdrawn in `debate/r1_rebuttal_fundamental.md`, and `M1` withdrawn here, **each of the three research tracks advances its single highest-conviction, zero-parameter method to Round 2 (`+3` trials total, `N_sel: 86 -> 89`, saving 3 full trials relative to the 6 Round 1 proposals and 1 extra trial relative to the referee's 4-method cap)**:

| Priority | Track | Method ID | Coverage (Disc) | Disc Turnover (`R0`: `17.2%`) | Disc Top-20% `ey <= 0` (`R0`: `4.5%`) | Active Rank-Diff Corr vs `M2` | Core Orthogonal Mechanism |
|---:|---|---|---:|---:|---:|---:|---|
| **1** | Statistical | **`S1` (`S1_value_eb_ns`)** | `100.0%` | `16.5%` | `1.2%` | `+0.258` | Blom normal scores + 2-stage Empirical-Bayes sector location & scale shrinkage + correlation-aware reliability composite on `R0`'s 4 ratios |
| **2** | EM / Macro | **`M2` (`value_real_spread_sn`)** | `100.0%` | `15.6%–16.1%` | `1.0%–1.6%` | `1.000` | Universal CPI constant-purchasing-power TTM (lagged $t-1$) + Turkey USD Eurobond sovereign yield debt hurdle ($y^{\text{USD}}_{\text{TR},t}\cdot\text{NetDebt}$) + unlevered `S/EV` (`sev_real`) |
| **3** | Fundamental | **`FV1` (`reoi_ev_sn`)** | `97.6%` | `16.9%` | `6.0%` | `+0.409` | Closed-form Feltham-Ohlson `V_ReOI / EV` pricing 5-year abnormal operating profit above a Fisher-consistent nominal/real hurdle $r_{w,t}$ (with convex PV-weight normalization & transition-cohort guard) |

At **`N_sel = 89`** ($T = 161$ months, $V[\widehat{\text{SR}}] = 0.02335$), the Bailey–López de Prado (2014) expected maximum monthly Sharpe under the null is **$\text{SR}_0 = 0.3804$** (`1.3177` annualized), compared to `0.3810` at `N_sel = 90` and `0.3822` at `N_sel = 92`.

---

## Final EM / Macro Track Submission for Round 2

- **Advance (1 method, `+1` to `N_sel`):** **`M2` (`value_real_spread_sn`)** — locked unchanged per Section 1.3.
- **Withdrawn (`+0` to `N_sel`):** **`M1` (`value_usd_3y_sn`)** — withdrawn permanently.
