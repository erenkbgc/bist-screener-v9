# Round 1 Valuation Proposal — EM / Turkey Macro-Adjusted Quant

**Author role:** EM / Turkey-specific quant  
**Date:** 2026-11-22  
**Baseline:** Live rule `R0-2026-10-12` — monthly top-20% equal-weighted non-financial portfolio by `value_sn` (`bm`, `ep`, `sp`, `ey`, 1%/99% winsorized cross-sectional z-scores, averaged and sector-neutralized with `min_n = 5`) on the promoted point-in-time panel `data/research/factors_monthly.parquet` (lag75; `factors_monthly_kapdates.parquet` for KAP-date sensitivity).  
**Trial budget:** Current `N_sel = 86` (`data/research/trial_ledger.json`). Testing both methods below adds `+2` to `N_sel` (`N_sel = 88`), and DSR must be reported at the updated `N_sel`.  
**Discipline check:** No backtests were run and no return columns (`fwd_ret_*`) were inspected in drafting this proposal. Existing `debate/` directory was checked and contained no prior files at draft time.

---

## 0. Screening Out Degenerate, Unimplementable, and Previously Failed EM Ideas

Before specifying the two candidate methods, four tempting Turkey/EM ideas are explicitly ruled out on mathematical, PIT-data, or prior-evidence grounds:

1. **Single-date USD conversion of `value_sn`:** Dividing both numerator and denominator of `bm`, `ep`, `sp` by month-$t$ `USDTRY` cancels identically ($X_i/\text{FX}_t \div P_i/\text{FX}_t = X_i/P_i$), and multiplying every stock's ratio by the same $\text{FX}_t/\text{FX}_p$ scalar leaves cross-sectional z-scores invariant whenever companies share the same `stmt_period` $p$. Any valid inflation/USD adjustment must operate through **cross-sectionally heterogeneous channels**: multi-quarter/multi-year flow timing, balance-sheet vs. market-cap staleness inside `EV`, real vs. nominal debt-service charges, or reporting-date differences.
2. **Footnote export share / net FX position:** Neither export revenue share (`Yurtdışı Satışlar`) nor footnote net FX position (`Yabancı Para Pozisyonu`) is present in `data/research/raw/*.pkl` (only `Yabancı Para Çevrim Farkları` exists on the balance sheet, which captures foreign subsidiaries rather than domestic exporters). Using `reexpression_class.parquet` (`not_reexpressed`) as a foreign-functional-currency signal would introduce look-ahead bias because it was classified from 2025Q2 KAP reports.
3. **Price-based FX beta sorting or sovereign-spread market timing:** `fx_asymmetry_preregistration.md` showed stock-level price FX beta does not persist (`X1`/`X2` both FAIL), and `sovereign_spread_preregistration.md` showed Turkey's Eurobond spread explains contemporaneous USD returns ($t = -8.24$) but fails out-of-sample return prediction (`C2a`/`C2b` FAIL). Any use of sovereign spreads must stay **100% invested** and act **cross-sectionally** through valuation fundamentals, not market timing.
4. **IAS-29-only patches or previously failed filters/ablations:** Under the fixed pass rule, a candidate must achieve paired $D > 0$ in **both** discovery (2013–2020, NW $t \ge 1.0$) and holdout (2021+, NW $t \ge 2.0$) without worsening holdout USD max drawdown by $> 2$ pp. An IAS-29-only fix (2024+) yields $D \equiv 0$ in discovery and cannot pass. We also avoid all failed ideas in `README.md` / `trial_ledger.json` (dividend yield, quality/profitability overlays, low-vol/size/liquidity/free-float filters, EV variant `E1` adding ST investments & minority interest, ST debt coverage filter `D1`, learned IC weights, timing/exit overlays, and dropping `S/P` as in `V1` or `V2`).

---

## Method M1: Hard-Currency (USD) Through-the-Cycle Normalized Value (`value_usd_3y_sn`)

### 1.1 Exact Formula

Let $t$ be a month-end rebalance date and $p = p(i,t)$ be the latest statement period of stock $i$ satisfying $\text{available\_at}_{i,p} \le t$. Let $\text{FX}(d)$ denote the daily `usdtry` series from `data/research/fx.parquet`, with:
- $\text{FX}_t$: last observed daily `usdtry` on or before month-end $t$;
- $\text{FX}_{\text{end},s}$: last observed daily `usdtry` on or before quarter-end date $\text{period\_end}(s)$;
- $\overline{\text{FX}}_k$: arithmetic mean of daily `usdtry` over all trading days inside calendar quarter $k$.

**Step 1 — Annual hard-currency (USD) flows for each statement period $s$:**  
For any flow item $X \in \{\text{rev}, \text{op}, \text{ni}\}$ (corresponding to `revenue`, `op_profit`, and `ni_parent` with fallback to `net_income` exactly as in `core/pit_panel.py::_ttm_net_income`):
- **Nominal GAAP periods ($s < \text{2023Q4}$):** Require 4 consecutive discrete quarters $s-3, s-2, s-1, s$ (each consecutive `period_end` gap in $[80, 100]$ days, matching `pit_panel.quarterly_table`):
  $$F^{\text{USD}}_{X,i,s} = \sum_{j=0}^{3} \frac{q_{X,i,s-j}}{\overline{\text{FX}}_{s-j}}$$
- **IAS 29 periods ($s \ge \text{2023Q4}$):** In `quarterly.parquet`, `ttm_*` is already expressed in constant period-$s$-end TL purchasing power (via `C1` + `bridge_ttm` for `2023Q4`–`2024Q3`, with vendor re-expression undone):
  $$F^{\text{USD}}_{X,i,s} = \frac{\text{ttm}_{X,i,s}}{\text{FX}_{\text{end},s}}$$
If the required 4-quarter sequence or `ttm_*` is missing/`NaN`, $F^{\text{USD}}_{X,i,s} = \text{NaN}$.

**Step 2 — Non-overlapping multi-year (up to 3-year) normalized USD annual flow:**  
At decision date $t$ with latest available period $p$, consider the trailing non-overlapping annual blocks $s \in \{p,\, p-4,\, p-8\}$ (each 4 quarters apart, ending in the same calendar quarter to eliminate seasonality). To prevent mixing pre-IAS 29 nominal accounting with IAS 29 inflation accounting across the regime boundary, restrict lagged blocks to the **same accounting regime** as $p$:
- if $p < \text{2023Q4}$, require $s < \text{2023Q4}$;
- if $p \ge \text{2023Q4}$, require $s \ge \text{2023Q4}$.

Require $F^{\text{USD}}_{X,i,p}$ to be finite (else output is `NaN`, matching R0's eligibility). Define the valid contiguous annual-block set:
$$S_{X,i,p} = \begin{cases}
\{p, p-4, p-8\} & \text{if } p-4 \text{ and } p-8 \text{ are valid and in same regime,} \\
\{p, p-4\} & \text{else if } p-4 \text{ is valid and in same regime,} \\
\{p\} & \text{otherwise.}
\end{cases}$$
Compute the equal-weighted hard-currency normalized annual flow:
$$\overline{F}^{\text{USD,3Y}}_{X,i,p} = \frac{1}{|S_{X,i,p}|} \sum_{s \in S_{X,i,p}} F^{\text{USD}}_{X,i,s}$$

**Step 3 — Hard-currency Market Cap, FX-matched Enterprise Value, and 4 Valuation Ratios:**  
Let $\text{Eq}_{i,p}$ be `equity_parent` (fallback `equity`, as in `pit_panel._equity`), $\text{FD}_{i,p}$ be `fin_debt`, and $\text{Cash}_{i,p}$ be `cash`.
$$\text{MCap}^{\text{USD}}_{i,t} = \frac{\text{mcap}_{i,t}}{\text{FX}_t}$$
$$\text{EV}^{\text{USD}}_{i,t} = \begin{cases}
\dfrac{\text{mcap}_{i,t}}{\text{FX}_t} + \dfrac{\text{FD}_{i,p} - \text{Cash}_{i,p}}{\text{FX}_{\text{end},p}} & \text{if } \text{FD}_{i,p}, \text{Cash}_{i,p} \text{ are finite,} \\
\text{NaN} & \text{otherwise.}
\end{cases}$$
The four USD-normalized valuation yields are:
1. $\text{bm}^{\text{USD}}_{i,t} = \dfrac{\text{Eq}_{i,p} / \text{FX}_{\text{end},p}}{\text{MCap}^{\text{USD}}_{i,t}}$ if $\text{Eq}_{i,p} > 0$, else `NaN`
2. $\text{ep}^{\text{USD,3Y}}_{i,t} = \dfrac{\overline{F}^{\text{USD,3Y}}_{\text{ni},i,p}}{\text{MCap}^{\text{USD}}_{i,t}}$
3. $\text{sp}^{\text{USD,3Y}}_{i,t} = \dfrac{\overline{F}^{\text{USD,3Y}}_{\text{rev},i,p}}{\text{MCap}^{\text{USD}}_{i,t}}$
4. $\text{ey}^{\text{USD,3Y}}_{i,t} = \dfrac{\overline{F}^{\text{USD,3Y}}_{\text{op},i,p}}{\text{EV}^{\text{USD}}_{i,t}}$ if $\text{EV}^{\text{USD}}_{i,t} > 0$, else `NaN`

**Step 4 — Cross-sectional standardization, sector neutralization, and portfolio rule (identical to R0):**  
On the exact same monthly non-financial liquid universe (`tlvol60` bottom 30% dropped, `min_names = 30`):
1. For each ratio $r \in \{\text{bm}^{\text{USD}}, \text{ep}^{\text{USD,3Y}}, \text{sp}^{\text{USD,3Y}}, \text{ey}^{\text{USD,3Y}}\}$, compute `fb.winsorize_z(r, lo=0.01, hi=0.99)` cross-sectionally within month $t$.
2. Compute `value_usd_3y_z` as the row mean of non-null ratio z-scores (identical to `add_composites` in `scripts/backtest_factor_model.py`).
3. Sector-neutralize via `value_usd_3y_sn_z = fb.sector_neutralize(df, "value_usd_3y_z", min_n=5)` (demean within sector if sector count $\ge 5$, else within full cross-section).
4. Select the top 20% (`rank(ascending=False, pct=True) <= 0.20`), equal-weighted, evaluated with the exact `scripts/research_portfolio_backtest.py` simulator (1M TL real capital, base costs, next-close fills).

### 1.2 Point-in-Time (PIT) Inputs

- `data/research/factors_monthly.parquet` (primary) and `factors_monthly_kapdates.parquet` (sensitivity): `date`, `ticker`, `sector`, `mcap` (İş Yatırım HisseTekil `PD` with `shares_at` fallback), `tlvol60`, `stmt_period`.
- `data/research/quarterly.parquet`: `ticker`, `period`, `period_end`, `available_at` (75/100d lag; or KAP first-publication date via `pit_panel.apply_report_dates` for `kapdates`), `equity_parent`, `equity`, `fin_debt`, `cash`, `q_revenue`, `q_op_profit`, `q_ni_parent`, `q_net_income`, `ttm_revenue`, `ttm_op_profit`, `ttm_ni_parent`, `ttm_net_income`. Strictly filtered by `available_at <= t`.
- `data/research/fx.parquet`: daily `usdtry` (complete 2011-01 to 2026-10, 0 missing months). Market price observed at close on day $t$ with zero publication lag.
- **Zero free fitted parameters.** Window cap of 3 years ($M \le 3$) is fixed a priori to match Turkish macro/FX cycles while fitting inside the `quarterly.parquet` history starting 2011Q3.

### 1.3 Rationale (EM / Turkey Mechanism)

1. **Eliminates pre-IAS 29 nominal unit mixing across 2013–2023Q3:** In `R0`, `C1` constant-unit restatement only activates from `2023Q4` onward. Over all of Discovery (2013–2020) and 2021–2023Q3 of Holdout—when USDTRY rose from 1.8 to 29+—`R0` sums 4 unadjusted nominal TL quarters whose purchasing power shifted dramatically inside the same 12-month window. Translating each nominal quarter at its contemporaneous average `USDTRY` puts every flow into an unmanipulated, daily market-priced hard currency (avoiding 2021–2023 TÜİK CPI measurement debates).
2. **Fixes FX-staleness distortion in Enterprise Value during lira crises:** In `R0`, `EV = MCap_t + NetDebt_p` mixes month-$t$ market cap with 2-to-5-month-old balance-sheet net debt. Because Turkish corporate debt and corporate deposits are heavily FX-denominated, a 20–50% lira depreciation between period-end $p$ and rebalance date $t$ (2018Q3 Brunson shock, 2020Q1, 2021Q4, 2023Q2) causes `R0` to **understate** leveraged firms' true EV right at the height of FX stress, pulling FX-indebted distressed firms into the top quintile. Marking `NetDebt_p` to USD at $\text{FX}_{\text{end},p}$ puts debt and equity on the exact same hard-currency footing at date $t$.
3. **Hard-currency cyclically-adjusted earnings power (USD-CAPE):** Turkey experiences violent credit and FX cycles (2017 KGF boom, 2018 FX crisis, 2020 credit surge, 2022–2023 negative-real-rate boom, 2024–2025 50% rate squeeze). Single-year `ep`/`ey` over-ranks cyclical firms at temporary earnings peaks (classic EM value traps) and drops sound franchises after one-off FX revaluation losses. Multi-year averaging is impossible in nominal TL (where 3-year cumulative inflation exceeds 400% in holdout, crushing early years to zero weight), so hard-currency USD translation is the prerequisite that makes multi-year normalized valuation well-defined in Turkey.
4. **Lower turnover and implicit dilution penalty:** Multi-year normalized USD flows evolve more smoothly than 1-year trailing flows (expected lower monthly turnover and cost drag), and dividing aggregate 3-year USD flows by current post-dilution `MCap_USD` naturally penalizes firms that recently expanded share count via dilutive rights issues without adding a separate `nsi` filter.

### 1.4 Failure Modes

1. **Secular-decline value traps (Discovery & delisted risk):** A structurally deteriorating business had *higher* USD earnings 2–3 years ago than today. Equal-weighted 3-year USD averaging makes decaying firms look cheaper than 1-year TTM does—directly opposite to what avoids the delisted value traps (`-1.39%/mo` while listed) that weakened Discovery in `survivorship_delisted_preregistration.md`.
2. **Real exchange rate (RER) overshooting:** Turkey's real exchange rate swings by $\pm 40\%$ (real depreciation in 2018–2022, sharp real TL appreciation in 2024–2026 under 50% rates). For domestic-TL-revenue businesses, USD-translated profits jump during real TL appreciation even when real TL margins are flat, and collapse during RER overshoots—potentially introducing RER-driven cross-sectional noise between domestic and export-oriented sub-industries inside broad sectors.
3. **2022Q4–2023Q3 panel restatement seam:** As documented in `first_published_panel.md`, `quarterly.parquet` holds vendor IAS 29 first-application restated comparatives for `2022Q4`–`2023Q3` (approx. 1.65–1.9× original nominal TL). While the same-regime rule prevents `2022Q4`–`2023Q3` from leaking into `2024Q4+` averages, during decision months `2023-04` to `2024-03` dividing restated `2022Q4`–`2023Q3` quarters by `2022`–`2023` USDTRY overstates year-0 relative to year-1/year-2 (`2020`–`2021`). This affects `R0` too, but interacts asymmetrically with M1's 3-year average in 2023.
4. **Slow reactivity to genuine turnarounds / capacity expansions:** High-growth capex or M&A stories whose current USD earnings doubled look artificially expensive on a 3-year average; conversely, 1-year earnings momentum (`SUE`) is partially damped out.

---

## Method M2: Sovereign-Spread-Conditioned Real Economic Value (`value_real_spread_sn`)

### 2.1 Exact Formula

Let $t$ be a month-end rebalance date and $p = p(i,t)$ be stock $i$'s latest statement period with $\text{available\_at}_{i,p} \le t$.

**Step 1 — Strictly PIT CPI index and universal constant-purchasing-power flows (2013–2026):**  
Build the monthly TÜİK CPI index $I(m) = \prod_{\tau \le m}(1 + \text{cpi\_mom}_\tau / 100)$ from `data/research/macro_monthly.parquet` (matching `core/pit_panel.py::cpi_index`).  
Respecting TÜİK's publication calendar (month-$m$ CPI is released on the 3rd business day of month $m+1$, so $I(t)$ is **not** known on month-end $t$), define the latest CPI month strictly known at month-end $t$ as $m^*(t) = t - 1\text{ month}$. For any statement period $p$ with month $m_p = \text{period\_end}(p)\text{'s month}$, define the strictly PIT staleness inflation factor:
$$\Pi_{p \to t} = \frac{I(\max(m_p,\, m^*(t)))}{I(m_p)}$$
(Note: for lag75, $m^*(t) > m_p$ always; for fast `kapdates` filers releasing within 30 days of quarter-end, $\max(m_p, m^*(t)) = m_p$ gives $\Pi_{p \to t} = 1.0$, guaranteeing zero look-ahead.)

For flow items $X \in \{\text{rev}, \text{op}\}$ (`revenue`, `op_profit`), construct constant period-$p$-end purchasing-power TTM across **all** regimes:
- **Nominal GAAP periods ($p < \text{2023Q4}$):** Require 4 consecutive discrete quarters $p-3, \dots, p$ (80–100 day gaps). Let $\overline{I}_k$ be the arithmetic mean of the 3 monthly CPI index levels inside calendar quarter $k$ (matching the average purchasing power of a nominal quarterly flow):
  $$\text{TTM}^{\text{real}}_{X,i,p} = \sum_{j=0}^{3} q_{X,i,p-j} \cdot \frac{I(m_p)}{\overline{I}_{p-j}}$$
- **IAS 29 periods ($p \ge \text{2023Q4}$):** Use `ttm_revenue` and `ttm_op_profit` directly from `quarterly.parquet`, which are already in constant period-$p$-end purchasing power (`C1` + `bridge_ttm`).

**Step 2 — Strictly PIT Turkey USD Sovereign Yield (country-risk real financing hurdle):**  
From `data/research/eurobond_monthly.parquet`, take all Turkey USD Eurobonds observed on or before month-end $t$ (the month-$t$ snapshot) with remaining maturity $3 \le (\text{maturity} - \text{date})/365.25 \le 30$ years (the exact same bond universe as `core/sovereign_spread.py::median_spread` and `sovereign_spread_preregistration.md`). Define:
$$y^{\text{USD}}_{\text{TR},t} = \frac{1}{100} \cdot \operatorname{median}_{b \in \mathcal{B}_t}\!\big(\text{yield}_{b,t}\big)$$
(Observed across 165/165 months from 2013-01 to 2026-09 with zero missing months; range 4.74%–10.97%, median 6.92%.) Because $y^{\text{USD}}_{\text{TR},t} \approx y^{\text{UST}}_t + \text{sp}_t$, it is Turkey's live hard-currency cost of capital—embedding the sovereign spread directly with **zero free parameters**.

**Step 3 — Inflation-consistent EV, Sovereign-Spread-Conditioned Real Economic Earnings, and 4 Valuation Ratios:**  
Let $\text{NetDebt}_{i,p} = \text{FD}_{i,p} - \text{Cash}_{i,p}$ (strictly `NaN` if either `fin_debt` or `cash` is missing, identical to `pit_panel.value_ratios`). Define inflation-consistent Enterprise Value in month-$t$ purchasing power:
$$\text{EV}^{\text{real}}_{i,t} = \text{mcap}_{i,t} + \Pi_{p \to t} \cdot \text{NetDebt}_{i,p}$$
Define the four valuation ratios (preserving `R0`'s four economic pillars—Book, Equity Earnings, Sales, Operating Profit—while eliminating nominal/IAS 29 distortions and conditioning debt valuation on Turkey's sovereign spread):

1. **Inflation-consistent Book-to-Market (`bm_real`):**
   $$\text{bm}^{\text{real}}_{i,t} = \frac{\Pi_{p \to t} \cdot \text{Eq}_{i,p}}{\text{mcap}_{i,t}} \quad (\text{if } \text{Eq}_{i,p} > 0,\text{ else NaN})$$
2. **Sovereign-Spread-Conditioned Real Economic Earnings Yield (`real_ep_sp`):**
   $$\text{real\_ep}^{\text{sp}}_{i,t} = \frac{\Pi_{p \to t} \cdot \Big(\text{TTM}^{\text{real}}_{\text{op},i,p} - y^{\text{USD}}_{\text{TR},t} \cdot \text{NetDebt}_{i,p}\Big)}{\text{mcap}_{i,t}}$$
   (Requires both $\text{TTM}^{\text{real}}_{\text{op},i,p}$ and $\text{NetDebt}_{i,p}$ to be finite; note that a statutory tax multiplier $(1-\tau)$ is a cross-sectional constant and cancels identically in z-scores.)
3. **Inflation-consistent Unlevered Sales Yield (`sev_real`):**
   $$\text{sev}^{\text{real}}_{i,t} = \frac{\Pi_{p \to t} \cdot \text{TTM}^{\text{real}}_{\text{rev},i,p}}{\text{EV}^{\text{real}}_{i,t}} \quad (\text{if } \text{EV}^{\text{real}}_{i,t} > 0,\text{ else NaN})$$
4. **Inflation-consistent Operating Earnings Yield (`ey_real`):**
   $$\text{ey}^{\text{real}}_{i,t} = \frac{\Pi_{p \to t} \cdot \text{TTM}^{\text{real}}_{\text{op},i,p}}{\text{EV}^{\text{real}}_{i,t}} \quad (\text{if } \text{EV}^{\text{real}}_{i,t} > 0,\text{ else NaN})$$

**Step 4 — Cross-sectional standardization, sector neutralization, and portfolio rule (identical to R0):**  
On the exact same monthly non-financial liquid universe (`tlvol60` bottom 30% dropped, `min_names = 30`):
1. Compute `fb.winsorize_z(r, lo=0.01, hi=0.99)` per month for each of the four ratios.
2. Row mean of available ratio z-scores $\to$ `value_real_spread_z`.
3. `value_real_spread_sn_z = fb.sector_neutralize(df, "value_real_spread_z", min_n=5)`.
4. Top 20% equal-weighted monthly portfolio, evaluated identically to `R0` in `scripts/research_portfolio_backtest.py`.

### 2.2 Point-in-Time (PIT) Inputs

- `data/research/factors_monthly.parquet` (primary) and `factors_monthly_kapdates.parquet` (sensitivity): `date`, `ticker`, `sector`, `mcap`, `tlvol60`, `stmt_period`.
- `data/research/quarterly.parquet`: `equity_parent`, `equity`, `fin_debt`, `cash`, `q_revenue`, `q_op_profit`, `ttm_revenue`, `ttm_op_profit`, `period`, `period_end`, `available_at`. Strictly filtered by `available_at <= t`.
- `data/research/macro_monthly.parquet`: `cpi_mom` (complete 2011-01 to 2026-09, 0 missing months), strictly lagged to $m^*(t) = t - 1\text{ month}$ to respect TÜİK's 3-business-day release schedule.
- `data/research/eurobond_monthly.parquet`: Turkey USD Eurobond `maturity`, `date`, `yield` (complete 165/165 months across 2013-01 to 2026-09, observed on month-end $t$ with zero publication lag; live pipeline equivalent is the daily Ziraat Eurobond feed already noted in `sovereign_spread_preregistration.md`).
- **Zero free fitted parameters.** Every coefficient ($1.0$ equal ratio weights, live market yield $y^{\text{USD}}_{\text{TR},t}$) is fixed by accounting identity and market prices.

### 2.3 Rationale (EM / Turkey Mechanism)

1. **Unifies real vs. nominal earnings across EVERY Turkish macro/accounting regime (2013–2026):** In `R0`, accounting net income (`ep = ttm_ni_parent / mcap`) is systematically corrupted below the operating line in every regime, for opposite reasons:
   - *2013–2020 Discovery (FX debt boom & 2018 shock):* Companies borrowing in low-coupon EUR/USD booked tiny nominal interest expense before devaluations (inflating `ep`), then took massive lump-sum FX revaluation losses during shocks.
   - *2021–2023 Holdout (nominal GAAP, 60–85% CPI, negative real rates):* Cash-rich firms booked 20–45% nominal TL deposit interest as profit without deducting 60–85% purchasing-power erosion of cash, while TL-indebted firms expensed the inflation component of nominal interest as real loss (Modigliani-Cohn distortion, inverted by FX debt).
   - *2024–2026 Holdout (IAS 29 + 50% policy rate):* İş Yatırım maps IAS 29 **Net Monetary Position Gain/Loss** into financial items (`(Esas Faaliyet Dışı) Finansal Giderler (-)`). Heavily indebted or negative-working-capital firms book large **non-cash paper monetary gains** that inflate `ep`, while cash-rich conservative firms book paper monetary losses that depress `ep` (`docs/research/sector_specific_notes.md` §3).
   Replacing accounting financing/monetary lines with a real hard-currency debt charge $y^{\text{USD}}_{\text{TR},t} \cdot \text{NetDebt}$ removes all three distortions simultaneously.
2. **Continuous, zero-parameter sovereign-spread regime conditioning of value:** Letting $L^{\text{real}}_{i,t} = \Pi_{p\to t}\text{NetDebt}_{i,p} / \text{mcap}_{i,t}$, simple algebra yields the exact identity:
   $$\text{real\_ep}^{\text{sp}}_{i,t} = \text{ey}^{\text{real}}_{i,t} + L^{\text{real}}_{i,t}\cdot\Big(\text{ey}^{\text{real}}_{i,t} - y^{\text{USD}}_{\text{TR},t}\Big)$$
   - When Turkey's sovereign spread widens ($y^{\text{USD}}_{\text{TR},t}$ climbs from ~4.7% in calm years to ~10–11% during the 2018, 2020, and 2022–2023 stress regimes), the operating-yield hurdle $\text{ey}^{\text{real}} > y^{\text{USD}}_{\text{TR},t}$ tightens automatically across the entire cross-section.
   - Leveraged low-return value traps ($\text{ey}^{\text{real}} < y^{\text{USD}}_{\text{TR},t},\, L^{\text{real}} > 0$) suffer sharply negative `real_ep_sp` precisely when country risk is elevated, while net-cash firms ($L^{\text{real}} < 0$) receive an automatic cushion—targeting both Discovery value-trap drag and Holdout USD drawdown without trying to time the market.
3. **Fixes the leverage mismatch in `S/P` without dropping the sales pillar:** On the PIT baseline (`point_in_time_baseline_2026-11-22.md`), dropping `S/P` (`V1`) underperformed `V0` in every window (Discovery $D = -3.55\%/\text{yr}$, Holdout $-1.28\%/\text{yr}$, IAS 29 $-2.48\%/\text{yr}$), proving revenue carries value signal. Yet raw `S/P = Sales/MCap` equals $(\text{Sales}/\text{EV})\cdot(1 + L)$, mechanically multiplying a firm's sales yield by its leverage—a fatal flaw during high-rate tightening (when `S/P` IC flipped negative under IAS 29). Switching `S/P` to enterprise-consistent `S/EV` (`sev_real`) retains the sales valuation pillar while removing its distortionary leverage multiplier.
4. **Universal CPI constant-unit alignment:** Extending `C1` constant-purchasing-power TTM back to 2013–2023Q3 and carrying `NetDebt_p` forward by $\Pi_{p\to t}$ fixes both intra-year nominal TTM unit distortion (especially severe in 2018 and 2021–2023) and balance-sheet staleness in `EV` without waiting for `2023Q4`.

### 2.4 Failure Modes

1. **Redundancy between `real_ep_sp` and `ey_real` (loss of genuine below-EBIT information):** Because both `real_ep_sp` and `ey_real` start from `ttm_op_profit`, M2 places effectively ~50% weight on operating profit (differentiated only by leverage × $(\text{ey} - y^{\text{USD}}_{\text{TR}})$) and **completely discards** non-operating items in `ni_parent`: equity-method associate income (`Özkaynak Yöntemiyle Değerlenen Yatırımlar`, critical for Turkish holdings like KCHOL/SAHOL/AGHOL and industrial JVs!), effective corporate tax differences (export/R&D/investment-incentive tax shields!), and genuine subsidized TL credit windfalls (e.g., negative-real-rate KGF / 2022–2023 TL commercial loans, where borrowers truly earned a real transfer that `y_TR_USD` ignores!).
2. **Symmetric leverage amplification when $\text{ey}^{\text{real}} > y^{\text{USD}}_{\text{TR},t}$:** By the identity $\text{real\_ep}^{\text{sp}} = \text{ey}^{\text{real}} + L^{\text{real}}(\text{ey}^{\text{real}} - y^{\text{USD}}_{\text{TR},t})$, a distressed, deeply leveraged firm ($L^{\text{real}} = 5$) whose trailing operating yield temporarily exceeds $y^{\text{USD}}_{\text{TR},t}$ (say 14% vs. 8%) gets boosted to `real_ep_sp = 44%` because the formula charges the *sovereign* yield rather than a leverage-adjusted distressed corporate spread. Although `1%/99%` winsorization limits extreme outliers, M2 could still load onto high-leverage cyclical peak earners when spreads are compressed (2013–2017 or 2025–2026).
3. **Sovereign-spread vs. domestic TL real-rate divergence:** During 2022–2023, Turkey's USD Eurobond yield was ~9–10% while domestic TL real borrowing rates were deeply negative ($-40\%$ to $-60\%$); during 2024–2025, Turkey's USD Eurobond yield fell to ~6.5–7% while domestic TL real borrowing rates surged above $+10\%$ to $+15\%$ (50% TCMB policy rate vs. falling forward inflation). Charging $y^{\text{USD}}_{\text{TR},t}$ to a TL-indebted firm in 2024–2025 may *understate* its real TL debt burden relative to firms with USD funding.
4. **Replacing `S/P` with `S/EV` may give up genuine financial-distress / leverage risk premium:** If part of `S/P`'s strong PIT-baseline contribution (`sp_sn` Discovery FM slope $+3.07\%/\text{yr}$, $t = 3.11$) actually reflects compensation for bearing equity leverage risk on high-turnover firms rather than pure enterprise cheapness, delevering `S/P` into `S/EV` could weaken Discovery active returns below the $t(D) \ge 1.0$ threshold.

---

## Summary Comparison of Proposals

| Dimension | Baseline `R0` (`value_sn`) | **M1 (`value_usd_3y_sn`)** | **M2 (`value_real_spread_sn`)** |
|---|---|---|---|
| **Numeraire / unit** | Nominal TL (`<2023Q4`), C1 CPI (`>=2023Q4`); stale `NetDebt_p` | Hard-currency **USD** across 2013–2026; FX-matched `EV_USD` | Universal **CPI constant purchasing power** (lagged `t-1`) + `EV_real` |
| **Flow horizon** | 1-year TTM | Up to **3-year** non-overlapping annual USD blocks (regime-consistent) | 1-year constant-unit TTM |
| **Earnings leg** | Accounting `ttm_ni_parent / mcap` | 3Y normalized USD `NI / MCap_USD` | **Sovereign-spread-conditioned Real E/P** `(Op_real - y_TR_USD * NetDebt) / MCap` |
| **Sales leg** | Levered `ttm_rev / mcap` | 3Y normalized USD `Rev / MCap_USD` | Unlevered **Enterprise Sales Yield** `Rev_real / EV_real` |
| **Macro conditioning** | None | Implicit via quarterly FX & FX-matched EV | Explicit cross-sectional debt hurdle via PIT Turkey USD Eurobond yield $y^{\text{USD}}_{\text{TR},t}$ |
| **Free fitted params** | 0 | 0 | 0 |
| **Primary risk** | Nominal/FX/IAS 29 distortion + value traps | Secular-decline traps (stale 3Y average) + RER swings | Drops associate income/tax shields; sovereign yield $\ne$ TL real rate |
