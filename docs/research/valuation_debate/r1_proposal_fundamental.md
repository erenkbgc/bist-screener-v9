# Round 1 Proposal — Fundamental Valuation Quant

**Author role:** Fundamental Valuation Quant  
**Date:** 2026-11-22  
**Branch:** `agent/valuation`  
**Baseline to beat:** `R0-2026-10-12` (monthly top-20% equal-weighted by `value_sn`, non-financials, bottom 30% `tlvol60` dropped, 1M TL real capital, base costs, next-close fills on the promoted PIT panel `data/research/factors_monthly.parquet`).  
**Trial budget:** 2 candidate methods (`FV1`, `FV2`), adding **+2** to `N_sel` (`86 -> 88`) once tested under the fixed pass rule (PASS or FAIL). No returns were inspected and no backtests were run in preparing this proposal.

---

## 0. Diagnosis of `R0` (`value_sn`) Accounting Blind Spots on the PIT Panel

`R0` averages four equally weighted cross-sectional z-scores (`bm`, `ep`, `sp`, `ey`), demeaned within sector (`min_n = 5`). Prior pre-registered studies on this repository establish tight guardrails on what **not** to re-propose:
- Linear quality/profitability overlays (`GP/A`, `ROE`, `ROA`, `OP/A`, `F7`), dividend yield, low-volatility/size/liquidity filters, learned IC weights, timing/SMC overlays, KAP red flags, foreign ownership, and short-term debt coverage (`D1`) all failed.
- Dropping `S/P` (`V1: bm+ep+ey`) now trails `V0` in every window on the promoted PIT baseline, and minor EV tweaks (`E1`: netting short-term financial investments + adding minority interest, 93–97% portfolio overlap) failed.
- Sector-specialized Holdings (`H1/H2`) and REIT (`G1/G2`) overrides failed.

Yet an audit of the promoted PIT panel's accounting inputs (strictly non-return diagnostics on the `liq_drop = 0.30` universe, $N = 40{,}693$ stock-months) reveals **two major fundamental valuation flaws** in `R0` that have never been tested:

1. **No cost-of-capital discipline across Turkey's extreme rate & IAS 29 regimes:** `R0` treats a firm with high `B/M` and `ROIC << WACC` (a capital-destroying value trap) identically to a profitable operator on the `bm` leg, and weights book value vs. earnings identically whether Turkey's nominal rate is 10% (2013–2017), 50% (2024 nominal), or ~8% real (IAS 29). It does not price **abnormal economic profit** above the hurdle rate.
2. **Below-the-line monetary/FX distortion, non-core operating noise, and zero cash-conversion check:**
   - Checking `PBT - (EBIT + Finansal Gelirler + Finansal Giderler)` across `data/research/raw/*.pkl` confirms **0.0% non-zero residual** in both 2023Q3 and 2024Q4: İş Yatırım's industrial template folds **IAS 29 net monetary position gains/losses** into `(Esas Faaliyet Dışı) Finansal Gelirler / Giderler (-)` below operating profit. As a result, `ep` (`ttm_ni_parent / mcap`) is directly polluted by non-cash monetary gains on indebted firms and non-cash monetary losses on net-cash firms (and pre-IAS 29 by FX debt revaluation swings): `sign(ttm_ni_parent) != sign(ttm_op_profit)` in **19.3%** of all liquid stock-months and **24.4%** of IAS 29 stock-months.
   - Even above the financing line, `pit_panel.py`'s `op_profit` (`FAALİYET KARI (ZARARI)`) includes `Diğer Faaliyet Gelirleri / Giderleri (-)` (dominated in BIST by trade FX revaluation gains/losses, provisions, and non-recurring items), differing from core operating profit (`Net Faaliyet Kar/Zararı = Gross Profit - Marketing - G&A - R&D`) by a **median 20.4%**.
   - Neither `ep` nor `ey` checks whether reported accrual profits actually convert into cash rather than getting trapped in expanding receivables and inventories.
   - Finally, `sp = ttm_revenue / mcap` mismatches an unlevered numerator (`Sales`) with a levered equity denominator (`mcap`), making highly indebted firms appear artificially cheap.

The two proposals below target these two blind spots via **closed-form, parameter-light accounting valuation models** with strict PIT alignment, zero free parameters fitted to BIST, and high universe coverage.

---

## Method 1 (`FV1`): Inflation-Consistent Residual Operating Income Valuation (`V_ReOI / EV`)

### 1.1 Exact Formula

Grounded in Feltham & Ohlson (1995, *Contemporary Accounting Research*) and Penman (2013), `FV1` values the operating enterprise directly in TL as **current Net Operating Assets (`NOA`) plus the present value of a $T$-year competitive-advantage annuity of abnormal operating profit (`ReOI`)**, scaled by Market Enterprise Value (`EV`):

$$\text{NOA}_{i,t} = \text{equity}_{i,t} + \text{fin\_debt}_{i,t} - \text{cash}_{i,t}$$

$$\text{EV}_{i,t} = \text{mcap}_{i,t} + \text{fin\_debt}_{i,t} - \text{cash}_{i,t}$$

$$\text{NOPAT}_{i,t} = (1 - \tau)\cdot \text{ttm\_op\_profit}_{i,t}, \qquad \tau = 0.25$$

$$\text{ReOI}_{i,t} = \text{NOPAT}_{i,t} - r_{w,t}\cdot \text{NOA}_{i,t}$$

$$A(r_{w,t}, T) = \frac{1 - (1 + r_{w,t})^{-T}}{r_{w,t}}, \qquad T = 5$$

$$V^{\text{ReOI}}_{i,t} = \text{NOA}_{i,t} + A(r_{w,t}, 5)\cdot \text{ReOI}_{i,t} = (1 + r_{w,t})^{-5}\,\text{NOA}_{i,t} + A(r_{w,t}, 5)\,\text{NOPAT}_{i,t}$$

$$\text{reoi\_ev}_{i,t} = \begin{cases} \dfrac{V^{\text{ReOI}}_{i,t}}{\text{EV}_{i,t}}, & \text{if } \text{EV}_{i,t} > 0 \text{ and all inputs finite,} \\[8pt] \text{NaN}, & \text{otherwise.} \end{cases}$$

**Inflation-consistent PIT operating hurdle rate $r_{w,t}$:**  
Matched strictly to the purchasing-power unit of the stock's active statement (`stmt_period`), using fixed prior $\text{ERP} = 0.05$ (`config/equity_risk_premium.yaml`):

$$r_{w,t}^{\text{nom}} = \frac{\text{policy}_{t}}{100} + 0.05$$

$$r_{w,t}^{\text{real}} = \max\!\left(0.05,\ \frac{1 + r_{w,t}^{\text{nom}}}{1 + \pi_{t-1}} - 1\right), \qquad \pi_{t-1} = \frac{\text{cpi\_yoy}_{t-1}}{100}$$

$$r_{w,t} = \begin{cases} r_{w,t}^{\text{nom}}, & \text{if } \texttt{stmt\_period}_{i,t} < \texttt{"2023Q4"} \text{ (nominal accounting)}, \\ r_{w,t}^{\text{real}}, & \text{if } \texttt{stmt\_period}_{i,t} \ge \texttt{"2023Q4"} \text{ (IAS 29 constant-purchasing-power accounting)}. \end{cases}$$

**Cross-sectional ranking signal (exact `core/factor_backtest.py` convention):**
1. Apply the same liquid non-financial universe cut (`tlvol60 >= 30th percentile`, `min_names = 30`).
2. Within each month $t$, winsorize `reoi_ev` at 1%/99% and standardize (`fb.winsorize_z`).
3. Demean within sector (`fb.sector_neutralize(..., min_n=5)`, falling back to market mean when sector count $< 5$):
   $$\texttt{FV1}_{i,t} = \text{sector\_neutralize}\!\big(\text{winsorize\_z}_t(\text{reoi\_ev}_{i,t}),\ \text{min\_n}=5\big)$$
4. Hold the monthly top 20% equal-weighted (`rank(ascending=False, pct=True) <= 0.20`).

*Fixed priors (zero optimization):* $\tau = 0.25$ (statutory Turkish corporate tax rate already in `config/equity_risk_premium.yaml`), $\text{ERP} = 0.05$ (already in `config/equity_risk_premium.yaml`), $T = 5$ years (standard competitive advantage / ROIC mean-reversion horizon in Penman 2013 & Koller et al.). `EV` uses baseline `E0` (`mcap + fin_debt - cash`) — deliberately not touching failed `E1`.

### 1.2 Verified PIT Inputs Available in the Promoted Panel

**Zero new raw-file parsing or external fetches required.** Every input already exists in the promoted PIT files:

| Input | File & Column | PIT / Accounting Audit | Liquid-Universe Coverage (Disc / Hold) |
|---|---|---|---|
| `mcap`, `sector`, `tlvol60`, `stmt_period` | `data/research/factors_monthly.parquet` | İş Yatırım `PD` market cap; `available_at <= t` | 100.0% / 100.0% |
| `equity`, `fin_debt`, `cash` | `data/research/quarterly.parquet` (joined on `ticker, stmt_period`) | `undo_reexpression` applied; exact BS identity `\|(TA - TL - equity)/TA\|` median `0.000000`, `\|NOA - (equity+fin_debt-cash)\|/TA` median `0.000000` | 100.0% / 100.0% (`NOA > 0`: 99.4%, `EV > 0`: 99.5%) |
| `ttm_op_profit` | `data/research/quarterly.parquet` (joined on `ticker, stmt_period`) | C1 constant-purchasing-power TTM + `bridge_ttm` (`2023Q4–2024Q3`); sits above financing & IAS 29 monetary gain/loss | 98.5% / 99.3% |
| `policy` | `data/research/macro_monthly.parquet` | TCMB policy rate at month-end $t$ (known in real time on decision day) | 100.0% (range 4.5%–50.0%) |
| `cpi_yoy` (lagged 1m) | `data/research/macro_monthly.parquet` | Strictly lagged to $t-1$ (TÜİK publishes month-$t$ CPI on the 3rd business day of $t+1$) | 99.4% (100% over 2023–2026 IAS 29) |
| **Resulting `FV1` (`reoi_sn`)** | — | Same-period `NOA` avoids the `2023Q4–2024Q3` IAS 29 transition jump (`NOA / NOA_lag4` jumped to 1.26× real) | **97.6% / 99.2%** |

*Non-return feature diagnostics:* Median monthly Spearman correlation with `R0` (`value_sn_z`) is **0.849** with **72.3% median top-20% overlap** (~16 stock swaps/month out of ~58 names). Across regimes, $r_{w,t}$ behaves cleanly: median 13.0% in Discovery (2013–2020), 20.0% in Holdout nominal (up to 55.0%), and 7.8% real in Holdout IAS 29 (`c1` weight on `NOA/EV` shifts automatically from 0.54 in Discovery to 0.40 in high-rate nominal Holdout to 0.69 under IAS 29).

### 1.3 Economic Rationale for Turkey

1. **Unifies book capital and operating earnings in TL before scaling by EV:** Unlike `value_sn` (which averages separately standardized `bm_z`, `ep_z`, `sp_z`, `ey_z` with fixed 1-sigma weights) and unlike failed linear `value + ROE/GPA` composites (which double-counted earnings without a hurdle rate), `V_ReOI / EV` directly prices **economic profit above the cost of capital**. A firm with huge `NOA` but negative or sub-hurdle `NOPAT` suffers a direct TL haircut to intrinsic value rather than coasting into the top quintile on `bm_z` alone.
2. **Automatic Fisher regime adaptation (Nominal $\to$ IAS 29):** During Turkey's 2021–2023 nominal inflation surge, historical-cost book values became stale and nominal discount rates rose sharply; `(1 + r_w)^{-5}` automatically shrinks the weight on stale historical-cost `NOA` (down to 0.11 at $r_w = 55\%$) and shifts valuation onto current-TL `NOPAT`. Once IAS 29 restates `NOA` into current purchasing power (`>= 2023Q4`), `r_w` switches to the Fisher real hurdle (~8%), restoring full economic weight to restated capital backing (`c1 ~ 0.69`).
3. **Complete immunity to IAS 29 net monetary gain/loss and FX borrowing noise:** By operating at the `NOPAT` / `NOA` / `EV` level rather than levered net income, `FV1` excludes `(Esas Faaliyet Dışı) Finansal Gelirler / Giderler (-)` where İş Yatırım books both FX debt translation swings and IAS 29 net monetary gains/losses. Unproductive financial debt is penalized twice: it increases `NOA` (raising the capital charge $r_w \cdot \text{NOA}$) and increases `EV` in the denominator.
4. **Live-system parity:** Every input is already produced by `core/pit_panel.py::latest_value_ratios` + live macro data, so promotion would require zero new data feeds.

### 1.4 Expected Failure Modes

1. **Drop of the `S/P` scale anchor for temporary turnarounds:** On the promoted PIT baseline, `V1` (dropping `S/P`) underperformed `V0` because low-margin / temporarily depressed-EBIT cyclicals recovered sharply. Because `FV1` places zero direct weight on revenue, it will miss deep-cyclical turnarounds whose trailing TTM `NOPAT` is near zero or negative at the trough.
2. **Uniform hurdle rate $r_{w,t}$ across heterogeneous risk/FX exposures:** Using a single market-wide unlevered hurdle ignores firm-level systematic risk differences (export-USD cash flows vs. domestic-TL regulated utilities) — though sector neutralization removes between-sector WACC differences, within-sector exporter vs. domestic differences remain.
3. **Capital-light vs. asset-heavy outliers within broad sectors:** In heterogeneous sectors (e.g., `İmalat`, `Bilişim ve Yazılım`, `Holding`), firms with near-zero or negative `NOA` (negative working capital / customer prepayments) receive a zero or negative capital charge, inflating `V_ReOI / EV`; 1%/99% winsorization mitigates extreme tails but does not eliminate structural business-model dispersion.
4. **Static tax rate ($\tau = 0.25$) and horizon ($T = 5$):** Turkish exporters, technoparks, and investment-incentive recipients face effective tax rates well below 25%, while `ttm_op_profit` still includes `Diğer Faaliyet Gelirleri / Giderleri (-)` (which Method 2 explicitly addresses).

---

## Method 2 (`FV2`): Enterprise Cash-Conversion Valuation (`CCV_sn`)

### 2.1 Exact Formula

Grounded in Ball, Gerakos, Linnainmaa & Nikolaev (2016, *Journal of Financial Economics*, "Accruals, cash flows, and operating profitability in the cross section of stock returns") and Sloan (1996, *The Accounting Review*), `FV2` replaces `R0`'s mixed equity/enterprise accrual multiples (`bm`, `ep`, `sp`, `ey`) with a **strictly unlevered, enterprise-consistent, accruals-adjusted, monetary-clean valuation composite** built on three pillars sharing the exact same `EV` denominator:

1. **Cash-Based Core Operating Earnings Yield (`ccey`):**  
   Start from **Core Operating Profit** (`Net Faaliyet Kar/Zararı` = Gross Profit $-$ Marketing $-$ G&A $-$ R&D, stripping both below-the-line financing/IAS 29 monetary gains and non-core `Diğer Faaliyet Gelirleri/Giderleri`), and subtract **inflation-adjusted 4-quarter trade working capital accruals**:
   $$\text{WC}_{i,t} = \text{Ticari Alacaklar}_{i,t} + \text{Stoklar}_{i,t} - \text{Ticari Borçlar}_{i,t}$$
   $$\Delta^{\text{real}}\text{WC}_{i,t} = \text{WC}_{i,t} - \text{WC}_{i,t-4}\cdot \frac{\text{CPI}(p_t)}{\text{CPI}(p_{t-4})}$$
   where $p_t$ is the period-end month of `stmt_period` and $p_{t-4}$ is the exact 4-quarter lagged statement (gap 350–380 days), ensuring both terms are measured in period-$p_t$ TL purchasing power.
   $$\text{Core\_OCF}_{i,t} = \text{ttm\_core\_op}_{i,t} - \Delta^{\text{real}}\text{WC}_{i,t}$$
   $$\text{ccey}_{i,t} = \frac{\text{Core\_OCF}_{i,t}}{\text{EV}_{i,t}}, \qquad \text{EV}_{i,t} = \text{mcap}_{i,t} + \text{fin\_debt}_{i,t} - \text{cash}_{i,t} > 0$$

2. **Enterprise Net Operating Asset Yield (`noa_ev`):**  
   Unlevered book operating capital backing on the same `EV` denominator:
   $$\text{noa\_ev}_{i,t} = \frac{\text{NOA}_{i,t}}{\text{EV}_{i,t}} = \frac{\text{equity}_{i,t} + \text{fin\_debt}_{i,t} - \text{cash}_{i,t}}{\text{EV}_{i,t}}, \qquad \text{EV}_{i,t} > 0,\ \text{NOA}_{i,t} > 0$$

3. **Enterprise Sales Yield (`rev_ev`):**  
   Unlevered revenue anchor on the same `EV` denominator (correcting `sp = Revenue / mcap`'s leverage mismatch while retaining the top-line anchor that `V1` ablation proved essential on the PIT baseline):
   $$\text{rev\_ev}_{i,t} = \frac{\text{ttm\_revenue}_{i,t}}{\text{EV}_{i,t}}, \qquad \text{EV}_{i,t} > 0,\ \text{ttm\_revenue}_{i,t} > 0$$

**Cross-sectional ranking signal (exact `core/factor_backtest.py` convention):**
1. Apply the same liquid non-financial universe cut (`tlvol60 >= 30th percentile`, `min_names = 30`).
2. Within each month $t$, winsorize each pillar (`ccey`, `noa_ev`, `rev_ev`) at 1%/99% and standardize (`fb.winsorize_z`). Missing legs remain `NaN` (never zero-filled).
3. Form the equal-weighted composite over available legs (same `mean(axis=1)` convention as `value_z` in `backtest_factor_model.add_composites`, requiring at least 2 valid legs so no stock is ranked on a single leg alone):
   $$\text{ccv}_{i,t} = \text{mean}\!\big(\text{ccey\_z}_{i,t},\ \text{noa\_ev\_z}_{i,t},\ \text{rev\_ev\_z}_{i,t}\big)$$
4. Demean within sector (`fb.sector_neutralize(..., min_n=5)`):
   $$\texttt{FV2}_{i,t} = \text{sector\_neutralize}(\text{ccv}_{i,t},\ \text{min\_n}=5)$$
5. Hold the monthly top 20% equal-weighted (`rank(ascending=False, pct=True) <= 0.20`).

*Fixed priors (zero optimization):* Equal weights across the 3 unlevered enterprise pillars; `EV` keeps baseline `E0` (`mcap + fin_debt - cash`).

### 2.2 Verified PIT Inputs Available in the Promoted Panel & Raw Cache

All inputs are available locally with **zero network calls** and pass through the exact same PIT pipeline as `build_pit_panel.py` (`undo_reexpression` via `reexpression_class.parquet` + TÜİK CPI, C1 constant-purchasing-power `quarterly_table`, and `bridge_ttm` for `2023Q4–2024Q3`, then joined on `(ticker, stmt_period)` from `factors_monthly.parquet`):

| Input | Source & Exact İş Yatırım Row Label | PIT / IAS 29 Transition Audit | Liquid-Universe Coverage (Disc / Hold) |
|---|---|---|---|
| `mcap`, `sector`, `tlvol60`, `stmt_period` | `data/research/factors_monthly.parquet` | İş Yatırım `PD`; `available_at <= t` | 100.0% / 100.0% |
| `equity`, `fin_debt`, `cash`, `ttm_revenue` | `data/research/quarterly.parquet` | Promoted PIT baseline | `noa_ev`: **98.3% / 99.4%**, `rev_ev`: **95.4% / 97.4%** |
| `core_op` (`ttm_core_op`) | `data/research/raw/*.pkl` → `inc["Net Faaliyet Kar/Zararı"]` | Present in 100% of audited raw files; passed through `undo_reexpression` + C1 TTM + `bridge_ttm` | 98.5% / 99.3% |
| `ar`, `inv`, `ap` (`WC`, `Δ_real WC`) | `data/research/raw/*.pkl` → `bs["Ticari Alacaklar"]`, `bs["Stoklar"]`, `bs["Ticari Borçlar"]` (summed across ST/LT occurrences) | Present in 100% of audited raw files; `undo_reexpression` on Q4 BS; **zero IAS 29 step-up jump** (median `WC / (WC_4 × infl)` = **1.007** pre-IAS 29, **0.932** in `2023Q4–2024Q3` transition, **0.947** steady IAS 29) | `ccey`: **97.5% / 99.0%** |
| `cpi_mom` | `data/research/macro_monthly.parquet` | Used only at `stmt_period`'s `period_end` ($p_t$) and $p_{t-4}$, both strictly prior to `available_at <= t` | 100.0% |
| **Resulting `FV2` (`ccv_sn`)** | — | — | **99.1% / 99.9%** |

*Non-return feature diagnostics:* Median monthly Spearman correlation with `R0` (`value_sn_z`) is **0.733** with **65.7% median top-20% overlap** (~20 stock swaps/month out of ~58 names). Correlation between `FV1` and `FV2` is **0.722** (and standalone `ccey_sn` vs `FV1` is only **0.176**), confirming that `FV1` and `FV2` test distinct accounting mechanisms (cost-of-capital capitalization vs. cash-conversion & core operating accruals).

### 2.3 Economic Rationale for Turkey

1. **Penalizes Turkey's chronic inflation working-capital trap:** Under high Turkish inflation, nominal FIFO/weighted-average inventory accounting creates **phantom operating profits** (`COGS` lags current replacement cost) that never turn into distributable cash because every lira of reported EBIT is absorbed into restocking inventories and funding extended TL receivables. Subtracting $\Delta^{\text{real}}\text{WC}$ directly separates genuine cash-generating operators from working-capital sinks — and CPI-adjusting $\text{WC}_{t-4}$ prevents penalizing a company merely for nominal price-level growth.
2. **Double-clean against IAS 29 & FX accounting noise without a transition discontinuity:**
   - Using `Net Faaliyet Kar/Zararı` (`core_op`) removes **both** below-the-line IAS 29 net monetary position gains/losses (which distort `ep`) **and** non-core `Diğer Faaliyet Gelirleri / Giderleri (-)` (trade FX gains/losses and one-off revaluations that distort `ey` by a median 20.4%).
   - Using **trade working capital** (`Receivables + Inventories - Payables`) instead of total $\Delta\text{NOA}$ avoids the massive one-time historical-cost PPE restatement jump in `2023Q4–2024Q3` (real `NOA/NOA_4` jumped to 1.26× while real `WC/WC_4` stayed at 0.93×) because trade working capital is short-duration and already near current purchasing power.
3. **Eliminates `S/P`'s leverage distortion while preserving top-line resilience:** Swapping `Sales / mcap` (`sp`) to `Sales / EV` (`rev_ev`) stops `R0` from rewarding heavily leveraged low-margin firms merely for having a thin equity sliver, while retaining the revenue anchor that `V1` ablation showed is vital in discovery and turnarounds — and simultaneously guarding `ccey` against distressed liquidation traps (where shrinking inventories create positive $-\Delta\text{WC}$ but shrinking revenue lowers `rev_ev`).
4. **Live-system parity:** `core/pit_panel.py::fetch_statement` already fetches the full İş Yatırım balance sheet and income statement DataFrames containing all four exact Turkish labels (`Net Faaliyet Kar/Zararı`, `Ticari Alacaklar`, `Stoklar`, `Ticari Borçlar`).

### 2.4 Expected Failure Modes

1. **Distressed working-capital liquidation traps:** A shrinking business liquidating inventories and collecting old receivables without replacing them generates $\Delta^{\text{real}}\text{WC} < 0$, which boosts `ccey` temporarily. While `rev_ev` and `noa_ev` dampen this effect in `FV2`, it remains a key risk among deep-distress names (and may interact negatively with survivorship/delisted names if not monitored).
2. **Higher turnover from quarterly working-capital swings:** Working capital is lumpier quarter-to-quarter than book equity or revenue (especially in defense, construction, agriculture, and seasonal retail/tourism). Even smoothed by `noa_ev` and `rev_ev`, `ccey` may increase monthly turnover relative to `R0`, eating into net active returns under 1M TL liquidity-tier costs.
3. **CapEx-intensive sectors (energy, telecom, airlines, manufacturing):** Trade working-capital accruals capture *operating working capital* cash absorption, not *fixed-asset CapEx* (which is deliberately omitted because `raw/*.pkl` lacks cash flow statements and $\Delta\text{PPE}$ suffers a 2–4× IAS 29 step-up jump in 2023Q4). Capital-intensive firms burning cash on heavy CapEx while holding lean working capital are not penalized by `ccey`.
4. **Holdings & REITs (`Holding`, `Gayrimenkul`):** For REITs carrying development projects in `Stoklar`, an inventory build during construction reduces `ccey` right before unit deliveries recognize revenue, potentially penalizing growing REIT developers at the wrong point in their project cycle; for Holdings, consolidated `Net Faaliyet Kar/Zararı` omits equity-method associate income (`Özkaynak Yöntemiyle Değerlenen Yatırımlar`), which may undervalue pure-play associate holdings.

---

## Summary Comparison vs. `R0` (`value_sn`)

| Dimension | `R0` (`value_sn`, live) | `FV1` (`V_ReOI / EV`) | `FV2` (`CCV_sn`) |
|---|---|---|---|
| **Valuation paradigm** | 4 ad-hoc multiples (`bm, ep, sp, ey`) | Closed-form Feltham-Ohlson abnormal operating earnings | Ball et al. (2016) cash-based core enterprise valuation |
| **Denominator consistency** | Mixed (3 equity `mcap`, 1 `EV`; `sp` mismatched) | Unified `EV` (`E0`) | Unified `EV` (`E0`) |
| **IAS 29 monetary & FX debt noise** | Contaminates `ep` (24.4% sign flip vs OP in IAS 29) | Excluded (operates at `NOPAT / NOA`) | Excluded (operates at `core_op` + trade `WC`) |
| **Non-core operating FX/other noise** | Included in `ey` (median 20.4% gap) | Included in `ttm_op_profit` | Excluded (`Net Faaliyet Kar/Zararı`) |
| **Cost-of-capital hurdle** | None | Explicit PIT nominal / Fisher-real $r_{w,t}$ | None |
| **Cash conversion / accruals** | None | None | Explicit CPI-adjusted $\Delta^{\text{real}}\text{WC}$ |
| **Extra raw-file items needed** | None | **None** (100% in `quarterly.parquet` + `macro_monthly.parquet`) | 4 existing İş Yatırım rows in `raw/*.pkl` |
| **Coverage (Disc / Hold)** | 100% / 100% | **97.6% / 99.2%** | **99.1% / 99.9%** |
| **Median Top-20% overlap vs `R0`** | 100% | **72.3%** | **65.7%** |
| **Free parameters fitted to BIST** | 0 | **0** ($\tau=0.25, \text{ERP}=0.05, T=5$ fixed priors) | **0** (equal-weighted 3 pillars) |

Both `FV1` and `FV2` are ready for Round 2 critique and, if selected, strict out-of-sample evaluation under the **fixed pass rule** (paired $D > 0$ with discovery NW $t \ge 1.0$, holdout NW $t \ge 2.0$, holdout USD max drawdown within 2 pp of `R0`, and DSR at updated $N_{\text{sel}}$).
