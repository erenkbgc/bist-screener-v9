# Round 1 Rebuttal — Fundamental Valuation Quant

**Author role:** Author of `debate/r1_proposal_fundamental.md` (Fundamental Valuation Quant)  
**Date:** 2026-11-22  
**Branch:** `agent/valuation`  
**Responding to:** `debate/r1_critique.md` (and reviewed against `debate/r1_proposal_macro.md`, `debate/r1_proposal_statistical.md`, `debate/r1_rebuttal_statistical.md`)  
**Discipline check:** Every new diagnostic reported in this rebuttal was computed strictly on **Discovery (`2013-04` to `2020-12`, 93 months)** after the standard `liq_drop_pct = 0.30` / `min_names = 30` cut (`lag75`: $N = 20{,}049$; `kapdates`: $N = 20{,}088$). **Zero return columns (`fwd_ret_1m`, `fwd_ret_6m`, `mom_12_1`, `str_1m`, `vol60`) and zero Holdout (`2021+`) rows were loaded or inspected.**

---

## Executive Disposition Summary

| Method | Referee Verdict | Author Rebuttal Action | Trial-Budget Impact (`N_sel`) | Core Reason |
|---|---|---|---|---|
| **`FV1` (`reoi_ev_sn`: `V_ReOI / EV`)** | **RECOMMEND (#3)** | **DEFEND + EX-ANTE TRANSITION-SEAM FIX** (0 new parameters; bit-for-bit identical in all 93 Discovery months & all single-regime months; fixes the `2024Q1–Q2` mixed-regime scaling jump) | **`+1`** | Closed-form Feltham-Ohlson enterprise valuation (`97.6%` coverage, `16.94%` turnover vs `17.21%` `R0` and `17.53%` `V1`). Discovery switcher audit proves `FV1` is **not** a clone of failed `V1` (`24.2%` portfolio divergence): `FV1` ejects heavily indebted `R0` picks (`med NetDebt/MCap = +78.2%`, `43.1%` with `NetDebt > MCap`) and replaces them with low-debt/net-cash firms (`med NetDebt/MCap = +7.8%`, `31.9%` net cash) trading at `1.49x` median `B/M`. Convex PV-weight normalization + regime-cohort standardization (`min_n = 5`) eliminates the referee's `2024Q1–Q2` transition seam without altering a single Discovery score. |
| **`FV2` (`ccv_sn`: `ccey + noa_ev + rev_ev`)** | **REJECT (#5)** | **WITHDRAW** (do not test in Round 2) | **`+0`** *(saves 1 trial)* | Concede four decisive flaws: (1) our anticipated working-capital liquidation trap dominates in Discovery, more than doubling top-20% loss-makers (`ep <= 0`: `21.2%` vs `9.9%` `R0`; `ey <= 0`: `12.3%` vs `4.6%` `R0`); (2) highest monthly turnover in the pool (`18.5%`); (3) `raw/*.pkl` IAS 29 `2022Q4–2023Q3` comparative restatement and `2025Q2` `reexpression_class.parquet` look-ahead vulnerabilities; (4) patching the loss-maker tail would require a prohibited quality/distress filter (`QV1–QV3` / `H4a`). |

---

## 1. Method `FV1` (`reoi_ev_sn`): Ex-Ante Transition-Seam Fix & Defense Against the `V1` Analogy

The referee recommended `FV1` for **Round 2 Slot #3**, confirming zero look-ahead risk in Discovery, `97.6%` liquid coverage, lower monthly turnover than `R0` (`16.9%` vs `17.2%`), and complete neutrality to size (`-0.019`), while raising two sharp technical critiques:
1. **The `2024Q1–Q2` IAS 29 mixed-regime transition seam** (§3.3.1, also highlighted in `r1_rebuttal_statistical.md` §3.2); and
2. **Within-month algebraic reduction to a 2-leg (`NOA/EV`, `ey`) linear combination without `S/P` (`sp`) or `E/P` (`ep`)** (§3.3.4).

We address both points rigorously below.

### 1.1 Ex-Ante Fix for Referee Catch #1: Eliminating the `2023Q4` Mixed-Regime Transition Discontinuity

In our Round 1 specification, a stock's discount hurdle switches from $r_{w,t}^{\text{nom}} = \text{policy}_t/100 + 0.05$ when $\texttt{stmt\_period}_{i,t} < \texttt{"2023Q4"}$ to $r_{w,t}^{\text{real}} = \max\!\big(0.05,\, (1+r_{w,t}^{\text{nom}})/(1+\pi_{t-1}) - 1\big)$ when $\texttt{stmt\_period}_{i,t} \ge \texttt{"2023Q4"}$, and:
$$\frac{V^{\text{ReOI}}_{i,t}}{\text{EV}_{i,t}} = c_1(r_{w,i,t})\,\frac{\text{NOA}_{i,t}}{\text{EV}_{i,t}} + c_2(r_{w,i,t})\,\text{ey}_{i,t}, \qquad c_1(r_w) = (1 + r_w)^{-5}, \quad c_2(r_w) = (1 - \tau)\,A(r_w, 5)$$

**Why the referee's catch is mathematically exact:**  
In any single-regime month (100% of Discovery `2013-04..2020-12`, 100% of `2021-01..2023-12`, and steady-state IAS 29 after `2024-05`), all stocks share the same hurdle $r_{w,t}$, so the total multiplier scale $S(r_{w,t}) = c_1(r_{w,t}) + c_2(r_{w,t})$ cancels out identically inside `fb.winsorize_z`. However, during the early-2024 filing transition when early `2023Q4` IAS 29 filers ($r_w^{\text{real}} \approx 7.8\% \implies c_1 = 0.69,\; c_2 = 3.01,\; c_1+c_2 = 3.70$) coexist in the same month and sector with late `2023Q3` nominal filers ($r_w^{\text{nom}} \approx 50\% \implies c_1 = 0.13,\; c_2 = 1.30,\; c_1+c_2 = 1.43$):
1. A finite-horizon nominal annuity at $r_w^{\text{nom}} = 50\%$ implicitly assumes zero nominal inflation growth in future `NOPAT` and terminal `NOA`, whereas the IAS 29 real annuity at $r_w^{\text{real}} = 7.8\%$ assumes CPI-indexed real preservation — inflating the raw multiplier sum $c_1 + c_2$ by **$2.58\times$** (`3.70` vs `1.43`) for early `2023Q4` filers; and
2. Simultaneously, an early `2023Q4` filer's balance-sheet `NOA` has just undergone first-time IAS 29 PPE/equity inflation restatement, whereas a late `2023Q3` peer's `NOA` is still at pre-IAS 29 historical cost. Pooling both raw ratios into a single cross-sectional `winsorize_z` systematically ranks early `2023Q4` filers above late `2023Q3` filers in the same sector purely because of their filing date.

**Two-Step Zero-Parameter Ex-Ante Fix (strictly scale-invariant in every single-regime month):**

1. **Convex Present-Value Weight Normalization ($c_1 + c_2 \equiv 1$):**  
   Normalize $V^{\text{ReOI}}_{i,t} / \text{EV}_{i,t}$ by its total present-value multiplier $c_1(r_{w,i,t}) + c_2(r_{w,i,t}) = (1 + r_{w,i,t})^{-5} + (1 - \tau)\,A(r_{w,i,t}, 5)$ so that the weights on `NOA/EV` and `ey` form a proper convex combination in every regime:
   $$\widetilde{\text{reoi\_ev}}_{i,t} = \frac{V^{\text{ReOI}}_{i,t} / \text{EV}_{i,t}}{(1 + r_{w,i,t})^{-5} + (1 - \tau)\,A(r_{w,i,t}, 5)} = w_{\text{NOA}}(r_{w,i,t})\,\frac{\text{NOA}_{i,t}}{\text{EV}_{i,t}} + \big(1 - w_{\text{NOA}}(r_{w,i,t})\big)\,\text{ey}_{i,t}$$
   where:
   $$w_{\text{NOA}}(r_w) = \frac{(1 + r_w)^{-5}}{(1 + r_w)^{-5} + (1 - \tau)\,A(r_w, 5)} \in (0, 1)$$
   - Notice how clean the economic interpretation is: the relative capital-backing share $w_{\text{NOA}}(r_w)$ adapts smoothly across macro regimes (`17.1%` at Discovery median $r_w = 13.0\%$, shrinking to `9.2%` at $r_w^{\text{nom}} = 50\%$ when nominal historical-cost book values are stale, and restoring to `18.6%` at $r_w^{\text{real}} = 7.8\%$ under IAS 29 restated book values), while the total weight $w_{\text{NOA}} + (1 - w_{\text{NOA}}) \equiv 1.000$ never jumps across regimes.
2. **Within-Regime Cross-Sectional Standardization (`min_n = 5`, matching `sector_neutralize`):**  
   Let $g_{i,t} = \mathbb{I}(\texttt{stmt\_period}_{i,t} \ge \texttt{"2023Q4"}) \in \{0, 1\}$ denote the stock's active accounting regime (`0` = nominal GAAP, `1` = IAS 29 constant purchasing power). Within each month $t$:
   - If **both** regime cohorts $g \in \{0, 1\}$ contain at least `min_n = 5` valid stocks in month $t$, compute `reoi_ev_z = fb.winsorize_z(reoi_ev_tilde, 0.01, 0.99)` **separately within each regime cohort $(t, g_{i,t})$** — ensuring that IAS 29 early filers (with restated `NOA`) and nominal late filers (with historical-cost `NOA`) are each standardized to $\mathcal{N}(0,1)$ against peers in the *same accounting unit* before `fb.sector_neutralize(..., min_n=5)`.
   - Otherwise (whenever only one regime is active or a straggler cohort has $< 5$ stocks), compute `reoi_ev_z = fb.winsorize_z(reoi_ev_tilde, 0.01, 0.99)` across the full month-$t$ cross-section (where Step 1's convex normalization already eliminates the $2.58\times$ discount-multiplier jump).

**Proof of zero Discovery drift:** In every single month of Discovery (`2013-04` to `2020-12`, 93 months, on both `lag75` and `kapdates`), $g_{i,t} \equiv 0$ for 100% of stocks and $c_1(r_{w,t}) + c_2(r_{w,t}) > 0$ is a cross-sectional scalar constant. Direct verification on `factors_monthly.parquet` and `factors_monthly_kapdates.parquet` confirms:
$$\max_{i,\, t \in \text{Discovery}} \big|\texttt{FV1}^{\text{fixed}}_{i,t} - \texttt{FV1}^{\text{orig}}_{i,t}\big| = 1.78 \times 10^{-15} \quad (\text{machine epsilon, } \mathbf{100.00\%} \text{ identical holdings}).$$

---

### 1.2 Defense Against Referee Catch #2: Why `FV1` Is Fundamentally Distinct From Failed `V1` (`bm+ep+ey`) and `R0`

The referee rightly notes (§3.3.4) that within any single-regime month $t$, `FV1` ranks stocks on a linear combination of `NOA/EV` and `ey` (`EBIT/EV`) without `S/P` (`sp`) or levered `E/P` (`ep`), and asks whether `FV1` is an algebraic cousin of failed `V1` (`bm_z + ep_z + ey_z`).

A strictly Discovery-only (`2013-04` to `2020-12`, 93 months, zero return columns) audit across both `lag75` and `kapdates` demonstrates why combining `NOA` and `NOPAT` **additively in raw TL on a unified `EV` denominator before z-scoring** produces a fundamentally different portfolio from both `R0` and `V1`:

#### Table 1.2A — Discovery-Only (`2013-04`–`2020-12`, 93m) Summary: `FV1` vs. `R0` and `V1`

| Metric (Discovery `2013-04`–`2020-12`, 93m) | `R0` (`lag75`) | `V1` (no `S/P`, `lag75`) | **`FV1` (`lag75`)** | `R0` (`kapdates`) | `V1` (no `S/P`, `kapdates`) | **`FV1` (`kapdates`)** |
|---|---:|---:|---:|---:|---:|---:|
| Liquid stock-months $N$ / Coverage | `20,049` / `100.0%` | `20,049` / `100.0%` | **`19,569` / `97.61%`** | `20,088` / `100.0%` | `20,088` / `100.0%` | **`19,598` / `97.56%`** |
| Monthly Spearman corr vs `R0` (mean / med) | `1.000` / `1.000` | `0.946` / `0.947` | **`0.851` / `0.849`** | `1.000` / `1.000` | `0.947` / `0.948` | **`0.851` / `0.853`** |
| Monthly Spearman corr vs `V1` (mean / med) | `0.946` / `0.947` | `1.000` / `1.000` | **`0.864` / `0.862`** | `0.947` / `0.948` | `1.000` / `1.000` | **`0.866` / `0.864`** |
| Monthly Top-20% overlap vs `R0` (mean) | `100.0%` | `84.8%` | **`70.7%`** | `100.0%` | `85.0%` | **`71.3%`** |
| Monthly Top-20% overlap vs `V1` (mean) | `84.8%` | `100.0%` | **`75.8%`** | `85.0%` | `100.0%` | **`75.8%`** |
| Monthly Top-20% turnover (`1 - stay`) | `17.21%` | `17.53%` *(higher)* | **`16.94%`** *(`-0.27 pp`)* | `16.43%` | `17.34%` *(higher)* | **`16.75%`** *(`-0.59 pp` vs `V1`)* |
| Top-20% median `NetDebt / MCap` | `+48.1%` | `+28.6%` | **`+27.6%`** | `+48.4%` | `+28.5%` | **`+27.5%`** |
| Top-20% share `NetDebt / MCap > 100%` | `30.6%` | `23.8%` | **`20.9%`** | `30.8%` | `23.8%` | **`20.8%`** |
| Top-20% share Net Cash (`NetDebt < 0`) | `23.6%` | `29.0%` | **`26.9%`** | `23.5%` | `28.9%` | **`27.0%`** |
| Top-20% median `ey` (`EBIT / EV`) | `15.2%` | `16.0%` | **`15.8%`** | `15.3%` | `16.2%` | **`16.0%`** |
| Top-20% median `bm` / `NOA / EV` | `1.32` / `1.19` | `1.36` / `1.21` | **`1.46` / `1.31`** | `1.33` / `1.19` | `1.37` / `1.22` | **`1.46` / `1.30`** |

#### Table 1.2B — Discovery Switcher Anatomy (`FV1` vs. `R0`, `lag75`, 93 months)

| Discovery (`lag75`, 93m) Bucket | $N$ | `NetDebt/MCap > 100%` | Med `NetDebt/MCap` | Net Cash (`ND < 0`) | Med `sp` (`Sales/MCap`) | Med `bm` | Med `NOA/EV` | Med `ey` (`EBIT/EV`) | `ey <= 0` | `ep <= 0` | `ey > 0` & `ep <= 0` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Liquid Universe | `20,049` | `18.4%` | `+24.2%` | `25.3%` | `0.95` | `0.71` | `0.78` | `6.7%` | `16.3%` | `26.8%` | `14.0%` |
| Overlap (`R0 ∩ FV1`) | `2,810` | `25.4%` | `+41.5%` | `24.9%` | `1.81` | `1.44` | `1.28` | `17.8%` | `2.9%` | `7.5%` | `7.1%` |
| **Dropped (`R0 \ FV1`)** | **`1,165`** | **`43.1%`** | **`+78.2%`** | **`20.4%`** | **`3.35`** | **`0.95`** | **`0.95`** | **`9.9%`** | `8.4%` | `15.3%` | `10.3%` |
| **Added (`FV1 \ R0`)** | **`1,066`** | **`8.8%`** | **`+7.8%`** | **`31.9%`** | **`0.86`** | **`1.49`** | **`1.38`** | **`9.8%`** | `14.2%` | `28.2%` | **`17.2%`** |

*(On `kapdates` Discovery, the switcher contrast is even sharper: `Dropped R0 \ FV1` [$N = 1,144$] has `med NetDebt/MCap = +82.5%` and `43.6%` with `NetDebt > MCap`; `Added FV1 \ R0` [$N = 1,041$] has `med NetDebt/MCap = +6.4%`, `32.4%` net cash, and only `8.5%` with `NetDebt > MCap`.)*

**Three structural insights from Tables 1.2A and 1.2B:**

1. **`FV1` is NOT `V1` (`24.2%` portfolio divergence and opposite turnover behavior):**  
   `V1` (`bm_z + ep_z + ey_z`) retains `84.8%` overlap with `R0` (`0.946` rank correlation) and **increases** monthly turnover from `17.21%` to `17.53%`. By contrast, `FV1` diverges from `V1` on **nearly a quarter of the top quintile (`75.8%` overlap, `954` swapped stock-months)** and **reduces** monthly turnover to **`16.94%`** (`-0.59 pp/mo` below `V1`).
2. **The core economic mechanism of `FV1`: a `10×` reduction in financial leverage across swapped holdings (`+78.2% -> +7.8%` median `NetDebt / MCap`):**  
   Why does `R0` select the `1,165` `Dropped (R0 \ FV1)` stock-months? Look at their profile: **`43.1%` carry Net Debt exceeding `100%` of Market Cap** (`med NetDebt/MCap = +78.2%`). Because three of `R0`'s four legs (`bm`, `ep`, `sp`) divide by levered equity `MCap`, a thin equity sliver on top of heavy debt inflates `sp = Sales / MCap` to a median of **`3.35`** ($3.5\times$ the universe median!) even though these firms have mediocre book backing (`med bm = 0.95`, `med NOA/EV = 0.95`) and mediocre operating yield (`med ey = 9.9%`).
   In `FV1`, scaling **both** `NOA = Equity + NetDebt` and `NOPAT` by unified `EV = MCap + NetDebt` exerts a strict nonlinear leverage penalty on any cheap stock ($\text{bm} = \text{Equity}/\text{MCap} > 1$):
   $$\frac{\text{NOA}}{\text{EV}} = \frac{\text{bm} + L}{1 + L}, \qquad L = \frac{\text{NetDebt}}{\text{MCap}}$$
   Whenever $\text{bm} > 1$, higher leverage $L > 0$ pulls $\text{NOA}/\text{EV}$ **down toward `1.0`**, increases the capital charge $r_{w,t}(\text{Equity} + \text{NetDebt})$, and expands the denominator of $\text{ey} = \text{EBIT}/(\text{MCap} + \text{NetDebt})$. Conversely, net cash ($L < 0$) boosts both $\text{NOA}/\text{EV}$ and $\text{ey}$. As a result, `FV1` replaces `R0`'s debt-laden picks (`med NetDebt/MCap = +78.2%`) with nearly unlevered / net-cash operators (`med NetDebt/MCap = +7.8%`, `31.9%` net cash, only `8.8%` with `NetDebt > MCap`) that have **identical median operating yield (`9.8%` vs `9.9%`) and `57%` higher book backing (`med bm = 1.49` vs `0.95`)**.
3. **Why `FV1`'s slightly higher `ep <= 0` share (`13.2%` vs `9.8%` in `R0`) reflects below-the-line noise rather than operating distress:**  
   As shown in the last column of Table 1.2B, **`17.2%` of `Added (FV1 \ R0)` (and `9.9%` of `FV1`'s entire top quintile, i.e., three-quarters of its `13.2%` `ep <= 0` picks) have POSITIVE operating profit (`ey > 0`) alongside negative bottom-line net income (`ep <= 0`)**. These are low-debt, asset-backed firms (`med bm = 1.49`, `med NetDebt/MCap = +7.8%`) whose bottom-line net income was temporarily pushed negative by below-the-line items (`(Esas Faaliyet Dışı) Finansal Giderler (-)`). We fully accept the remaining `6.0%` operating loss-makers (`ey <= 0`, vs `4.5%` in `R0`) and the omission of `S/P` as `FV1`'s genuine, pre-registered economic risk: if `R0`'s Discovery returns depend on levered high-`S/P` turnarounds, Round 2 will cleanly falsify `FV1`.

---

### 1.3 Exact Deterministic Specification of `FV1` Locked for Round 2

To ensure zero ambiguity in Round 2 execution:
- **Universe:** Exact `R0` liquid non-financial cross-section (`tlvol60 > 0`, `tlvol60 >= quantile(0.30)`, `min_names = 30`).
- **Inputs (100% from promoted PIT parquets):** Join `quarterly.parquet` on `(ticker, stmt_period)` (`equity_parent` with fallback to `equity`, `fin_debt`, `cash`, `ttm_op_profit`) and `macro_monthly.parquet` on calendar month (`policy` at month $t$; `cpi_yoy` strictly lagged 1 month to $t-1$).
- **Enterprise accounting items:**
  $$\text{NOA}_{i,t} = \text{Eq}_{i,t} + \text{fin\_debt}_{i,t} - \text{cash}_{i,t}, \qquad \text{EV}_{i,t} = \text{mcap}_{i,t} + \text{fin\_debt}_{i,t} - \text{cash}_{i,t}, \qquad \text{NOPAT}_{i,t} = (1 - \tau)\,\text{ttm\_op\_profit}_{i,t} \;\; (\tau = 0.25)$$
- **Inflation-consistent PIT hurdle rate $r_{w,i,t}$:**
  $$r_{w,t}^{\text{nom}} = \frac{\text{policy}_t}{100} + 0.05, \qquad r_{w,t}^{\text{real}} = \max\!\left(0.05,\; \frac{1 + r_{w,t}^{\text{nom}}}{1 + \text{cpi\_yoy}_{t-1}/100} - 1\right)$$
  $$r_{w,i,t} = \begin{cases} r_{w,t}^{\text{nom}}, & \text{if } \texttt{stmt\_period}_{i,t} < \texttt{"2023Q4"}, \\ r_{w,t}^{\text{real}}, & \text{if } \texttt{stmt\_period}_{i,t} \ge \texttt{"2023Q4"}. \end{cases}$$
- **Normalized Feltham-Ohlson Residual Operating Income yield ($T = 5$):**
  $$A(r_{w,i,t}, 5) = \frac{1 - (1 + r_{w,i,t})^{-5}}{r_{w,i,t}}, \qquad V^{\text{ReOI}}_{i,t} = \text{NOA}_{i,t} + A(r_{w,i,t}, 5)\cdot\big(\text{NOPAT}_{i,t} - r_{w,i,t}\,\text{NOA}_{i,t}\big)$$
  $$\widetilde{\text{reoi\_ev}}_{i,t} = \begin{cases} \dfrac{V^{\text{ReOI}}_{i,t} / \text{EV}_{i,t}}{(1 + r_{w,i,t})^{-5} + (1 - \tau)\,A(r_{w,i,t}, 5)}, & \text{if } \text{EV}_{i,t} > 0 \text{ and all inputs finite,} \\[8pt] \text{NaN}, & \text{otherwise.} \end{cases}$$
- **Regime-consistent cross-sectional standardization & sector neutralization:**  
  Let $g_{i,t} = \mathbb{I}(\texttt{stmt\_period}_{i,t} \ge \texttt{"2023Q4"})$. Within each month $t$, if both regime cohorts $g \in \{0, 1\}$ have $\ge 5$ finite $\widetilde{\text{reoi\_ev}}$ observations, compute `reoi_ev_z = fb.winsorize_z(reoi_ev_tilde, 0.01, 0.99)` within each $(t, g_{i,t})$ cohort; else compute `fb.winsorize_z(reoi_ev_tilde, 0.01, 0.99)` across month $t$. Then apply `FV1 = fb.sector_neutralize(df, "reoi_ev_z", min_n=5)`.
- **Portfolio:** Hold the monthly top 20% (`rank(ascending=False, pct=True) <= 0.20`), equal-weighted, evaluated in `scripts/research_portfolio_backtest.py` (1M TL real capital, base costs, next-close fills), primary on `factors_monthly.parquet` (`lag75`) and sensitivity on `factors_monthly_kapdates.parquet`.

---

## 2. Method `FV2` (`ccv_sn`): Formal Withdrawal & Fundamental Post-Mortem

**Decision: We unconditionally WITHDRAW `FV2` (`ccv_sn`) from Round 2 testing (`+0` to `N_sel`).**

In our Round 1 proposal (§2.4 Failure Mode #1 & #2), we explicitly warned of two potential failure modes for `FV2`:
1. *"Distressed working-capital liquidation traps: A shrinking business liquidating inventories and collecting old receivables without replacing them generates $\Delta^{\text{real}}\text{WC} < 0$, which boosts `ccey` temporarily"*; and
2. *"Higher turnover from quarterly working-capital swings."*

The referee's independent Discovery audit (`2013-04` to `2020-12`, 93 months) proved that **both failure modes materialize severely in the data**, alongside a legitimate `raw/*.pkl` IAS 29 transition vulnerability. We concede all four points in full:

1. **Severe distressed-liquidation contamination in Discovery (`21.2%` `ep <= 0`, `12.3%` `ey <= 0`, `8.4%` median ROE):**  
   In Discovery, `FV2` more than **doubles** top-20% net-income loss-makers relative to `R0` (`21.2%` vs `9.9%`) and nearly **triples** operating loss-makers (`12.3%` vs `4.6%`), while cutting median ROE from `12.8%` to `8.4%`. When a distressed BIST firm liquidates inventory, writes down receivables, or stretches unpaid trade payables (`Ticari Borçlar`) during a liquidity crunch, $\Delta^{\text{real}}\text{WC}_{i,t} < 0$ creates phantom operating cash flow ($\text{Core\_OCF} = \text{ttm\_core\_op} - \Delta^{\text{real}}\text{WC} \gg \text{ttm\_core\_op}$). The `noa_ev` and `rev_ev` legs were insufficient to prevent these distressed working-capital liquidators from entering the top quintile.
2. **Highest monthly turnover of all 6 proposals (`18.5%` vs `17.2%` in `R0` and `15.0%–16.9%` in the 4 recommended methods):**  
   Because quarterly trade working capital (`Ticari Alacaklar + Stoklar - Ticari Borçlar`) fluctuates sharply with seasonality, shipment timing, and inflation-driven restocking cycles, `FV2` adds `+1.3 pp/mo` of extra turnover (`+15.6 pp/yr` two-way), creating a direct transaction-cost drag at 1M TL.
3. **Coverage discrepancy (`97.6%` under strict $\ge 2$-leg rule) and `raw/*.pkl` IAS 29 pipeline risks (conceded):**  
   We confirm the referee's coverage audit: enforcing the strict $\ge 2$-leg requirement with `EV > 0` yields `97.6%` Discovery coverage (our Round 1 table's `99.1%` reflected $\ge 1$ valid leg). More importantly, we concede that extracting 4-quarter working-capital changes $\Delta^{\text{real}}\text{WC}$ from `raw/*.pkl` is exposed to (a) `2022Q4–2023Q3` vendor IAS 29 first-application restated comparatives (`1.65x–2.0x` nominal) when differenced against `2021Q4–2022Q3` or `2023Q4–2024Q3`, and (b) classification look-ahead from `reexpression_class.parquet` (built from 2025Q2 KAP filings, with 33 companies left `unknown`).
4. **Why we refuse to patch `FV2`:**  
   Eliminating `FV2`'s `21.2%` loss-maker tail would require either gating on positive profitability (`ep > 0` or `core_op > 0`) or down-weighting $-\Delta^{\text{real}}\text{WC}$ when revenue or earnings shrink. Any such gate is an ad-hoc post-audit patch that re-introduces failed `quality x value` / distress exclusions (`long_term_preregistration.md`, `quality_value_lowvol_preregistration.md`), and `FV2`'s `+0.457` active rank-deviation correlation with withdrawn `S2` confirms that testing it would waste a trial ledger slot.

---

## 3. Alignment with Round 2 Slate & Trial-Ledger Discipline

With `N_sel = 86` and full-sample `R0` `DSR = 0.103`, withdrawing `FV2` (alongside the Statistical Quant's withdrawal of `S2` in `debate/r1_rebuttal_statistical.md`) keeps the Round 2 test budget strictly capped at the referee's **4 orthogonal recommended methods (`N_sel: 86 -> 90`, monthly $\text{SR}_0 = 0.3810$ at $V[\widehat{\text{SR}}] = 0.02335$):**
1. **`S1` (`S1_value_eb_ns`)** — Empirical-Bayes Sector-Standardized Normal-Score Value (`100%` coverage, estimator & sector-scale repair on `R0`'s 4 ratios).
2. **`M2` (`value_real_spread_sn`)** — Sovereign-Spread-Conditioned Real Economic Value (`100%` coverage, universal CPI constant-unit TTM + Eurobond debt charge + `S/EV`).
3. **`FV1` (`reoi_ev_sn`)** — Inflation-Consistent Residual Operating Income Valuation (`97.6%` coverage, closed-form Feltham-Ohlson `V_ReOI / EV` with convex PV-weight normalization & transition-cohort guard, cutting switcher `NetDebt/MCap` from `+78.2%` to `+7.8%`).
4. **`M1` (`value_usd_3y_sn`)** — Hard-Currency (USD) 3Y Normalized Value (`100%` coverage, lowest turnover `15.0%`, orthogonal multi-year USD-CAPE).

---

## Final Fundamental Track Submission for Round 2

- **Advance (1 method, `+1` to `N_sel`):** **`FV1` (`reoi_ev_sn`)** — locked per Section 1.3 (with the zero-parameter ex-ante `2024Q1–Q2` transition-seam fix; 100.00% identical in Discovery).
- **Withdrawn (`+0` to `N_sel`):** **`FV2` (`ccv_sn`)** — withdrawn permanently.
