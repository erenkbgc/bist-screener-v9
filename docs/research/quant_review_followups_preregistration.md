# Quant review follow-ups (alpha attribution, multiple testing, cost stress): pre-registration

Written and committed on 2026-10-21, **before** any of the series below were computed. The models, inputs, windows and labels are fixed here. They are not changed after the results are seen.

Source: `docs/plan_2026-10-21.md`, items P1-1, P1-2 and P1-3. Two external reviews (2026-10-21) asked three questions the earlier studies did not answer:

1. Where does the rule's edge come from, and why does it trail BIST 100 total return?
2. After 26 pre-registered studies on the same panel, is the edge still distinguishable from the best of many tries?
3. Does the edge survive higher costs, larger capital and days when a stock cannot be traded at the limit?

These are reporting tests. **The live rule R0 does not change whatever the result.** The results decide only how the README and the reports describe the rule.

## What was looked at before this file was written

- `scripts/research_total_return_benchmarks.py` was re-run on the current (C1) panel to check that the baseline reproduces: holdout R0 vs costed EW universe +6.89%/yr (t 2.55), vs BIST 100 TR −1.71%/yr (t −0.28). Same as the README.
- borsapy returns `XBANK_CFNNTLTL` (BIST Banks total return) daily from 2018-07-16. Only the first and last dates were looked at. No return was computed.
- No factor return, attribution, DSR, PBO or stressed simulation was computed.

## Common setup

- **Strategy R0:** the main specification of `portfolio_backtest_preregistration.md`: `value_sn` top 20%, equal weight, monthly, panel `research_long_term.load()` (C1), next-close fills, 1M TL in 2026-09 money scaled by CPI, base costs, cash at the policy rate, delisting haircut 0.
- **EW net:** the same simulator and settings with every name in the month's ranking universe as target (B2 of `total_return_benchmarks_preregistration.md`).
- **Windows:** discovery = decisions 2013-04 to 2020-12; holdout = 2021-01 to the end. The labels use the holdout unless stated.
- **Risk-free:** the policy-rate deposit return over the same window (`dep` column of `attach_benchmarks`).
- **t-statistics:** Newey-West, 6 lags, as in all earlier studies.

## A. Alpha attribution (P1-1)

### A1. CAPM against BIST 100 total return

Monthly regression, holdout:
R0 − rf = α + β (XU100_TR − rf) + ε.

Label: `POSITIVE_ALPHA` if α > 0 and t(α) > 2; `POSITIVE_NOT_SIGNIFICANT` if α > 0 and t ≤ 2; `NO_ALPHA` otherwise.

### A2. Factor model on the panel

Monthly long-short factor returns from the panel, gross, equal weight within each leg, each month's ranking universe:
- **MKT:** EW universe gross return (`fwd_ret_1m` mean) − rf;
- **SMB:** bottom 30% by `mcap` − top 30%;
- **WML:** top 30% by `mom_12_1` − bottom 30%;
- **LV:** bottom 30% by `vol60` − top 30%;
- **HML_sn:** top 30% by `value_sn_z` − bottom 30%.

Two regressions of R0 − rf, full sample and each window:
- **A2a:** MKT, SMB, WML, LV (no value factor). Does size, momentum or low volatility explain the edge?
- **A2b:** A2a + HML_sn. How much of R0 is the value factor?

Label (A2a, holdout): `EDGE_NOT_EXPLAINED_BY_SIZE_MOM_LOWVOL` if α > 0 and t(α) > 2; `EDGE_WEAK_AFTER_CONTROLS` if α > 0 and t ≤ 2; `EDGE_EXPLAINED_BY_CONTROLS` otherwise. A2b is reported without a label (its α is expected near 0, since HML_sn contains R0's own signal).

### A3. Sector attribution (Brinson, against the EW universe)

Gross monthly returns (`fwd_ret_1m`), sectors as in the panel. Benchmark weights = sector shares of the universe; portfolio weights = sector shares of R0's names.
- allocation = Σ_s (w_p,s − w_b,s)(R_b,s − R_b);
- selection = Σ_s w_p,s (R_p,s − R_b,s).

Both per year with Newey-West t, each window. Label (holdout): `SELECTION_DRIVEN` if selection > 0 and selection > 50% of allocation + selection; `ALLOCATION_DRIVEN` if allocation > 50% and the total is > 0; `NO_EDGE` if the total ≤ 0.

### A4. The gap to BIST 100 total return

The EW universe excludes banks and other financials; BIST 100 holds them at a large weight. Holdout regression:
R0 − XU100_TR = γ + δ (XBANK_TR − XU100_TR) + ε.

γ is the gap after removing the bank tilt. Label: `BANK_TILT_EXPLAINS_GAP` if the raw mean gap < 0 and γ > 0; `GAP_PERSISTS` if γ ≤ 0; `NO_GAP` if the raw mean gap ≥ 0.

### A5. Block-bootstrap intervals

Stationary bootstrap (Politis-Romano), mean block length 6 months, 5,000 draws, seed 20261021. 95% intervals for the holdout mean active return per year against EW net and against BIST 100 TR. No label; reported next to the Newey-West t.

## B. Multiple testing (P1-2)

### B1. Trial ledger

`data/research/trial_ledger.json` lists every pre-registered study, its family (stock selection, market timing, events/calendar) and the number of candidate rules it tested, counted from the study files. `N_sel` = the number of stock-selection trials evaluated on this panel; it is the N used for the label. The ledger is committed with the results.

### B2. Deflated Sharpe Ratio (Bailey & López de Prado 2014)

Series: R0 monthly net active return against EW net, full sample 2013–2026 (T months). SR = mean / std (monthly, not annualised), skewness γ3 and kurtosis γ4 from the same series.

SR₀ = √V · [(1 − γ_E) Φ⁻¹(1 − 1/N) + γ_E Φ⁻¹(1 − 1/(N e))], γ_E = 0.5772.

DSR = Φ((SR − SR₀) √(T − 1) / √(1 − γ3 SR + (γ4 − 1)/4 SR²)).

V = the cross-sectional variance of monthly active SR over the B3 variant set (below). DSR is reported for N = `N_sel` and, as information, for N ∈ {10, 26, 50, 100, 200}.

Label (N = `N_sel`): `SIGNIFICANT_AFTER_TRIALS` if DSR ≥ 0.95; `NOT_SIGNIFICANT_AFTER_TRIALS` otherwise.

### B3. Probability of Backtest Overfitting (CSCV)

A variant set that stands for the choices a researcher had on this panel. Signals (higher = buy; negative signs flip a column):
`value_sn_z`, `value_z`, `bm_z`, `ep_z`, `sp_z`, `ey_z`, mean of (`bm_z`, `ep_z`, `ey_z`), mean of (`bm_z`, `ep_z`), `gpa_z`, `roe_z`, `mom_12_1_z`, −`vol60_z`, `sue_z`, −`size_z`, mean of (`value_sn_z`, `gpa_z`), mean of (`value_sn_z`, −`vol60_z`).
Each with top 10%, 20% and 30%: 48 variants. Monthly gross active return = EW mean `fwd_ret_1m` of the top names − universe mean. A month where a signal has fewer than 20 names is NaN for that variant; months where any variant is NaN are dropped.

CSCV: the months are cut into S = 16 contiguous blocks of equal size (the last months that do not fill a block are dropped). For each of the C(16, 8) = 12,870 splits, the variant with the highest in-sample Sharpe is taken; ω = its out-of-sample Sharpe rank among all variants / (N + 1); λ = ln(ω / (1 − ω)). PBO = share of splits with λ ≤ 0.

Labels: `LOW_OVERFIT_RISK` if PBO ≤ 0.2; `MODERATE` if 0.2 < PBO ≤ 0.5; `HIGH_OVERFIT_RISK` if PBO > 0.5. Also reported: the in-sample rank of R0's own variant (`value_sn_z`, top 20%) over the full sample.

## C. Cost, capacity and limit stress (P1-3)

### Grid

R0 and EW net are simulated with **identical** settings on every point:
- cost multiplier `Costs(mult=m)`, m ∈ {1, 2, 3};
- capital ∈ {1M, 10M, 50M} TL in 2026-09 money, scaled by CPI;
- limit rule off / on.

**Limit rule.** On a fill day, a stock whose fill-price close is ≥ 9.5% above or below the previous trading day's close is not traded (BIST daily price limit ±10%). A held position stays as it is (not resized, not sold) until the next rebalance. A new target is not bought; its slot stays in cash. This is a simplification: on a limit-up day a sale would still be possible. It is stated, not modelled.

### Label (primary point: m = 3, capital 10M, limit rule on)

R0 − EW net per year and Newey-West t, each window:
- `COST_ROBUST` if active > 0 in discovery and holdout and the holdout t > 2;
- `COST_ROBUST_NOT_SIGNIFICANT` if active > 0 in both windows and the holdout t ≤ 2;
- `COST_FRAGILE` otherwise.

Also reported: the break-even cost multiplier, the smallest m in {1, …, 8} at 1M with the limit rule on where the holdout active return ≤ 0 (or "> 8").

## What the results can change

- README headline and the "Backtests & Evidence" section: attribution, DSR/PBO and stress numbers next to the existing ones.
- Nothing in `config/live_rule.json`, `core/rotation.py` or the scoring.

## Files

- `core/research_stats.py`: DSR, PBO (CSCV), stationary bootstrap, Brinson, OLS with Newey-West.
- `core/portfolio_backtest.py`: optional `limit_pct` argument in `simulate` (default off; existing results unchanged).
- `scripts/research_quant_review.py`: runs A, B and C and writes `data/reports/research_quant_review_<date>.json`.
- `data/research/trial_ledger.json`.

---

## Results (2026-10-21)

Run: `python scripts/research_quant_review.py` → `data/reports/research_quant_review_2026-10-21.json`. Months 2013-04 → 2026-09. The baseline reproduces: holdout R0 vs EW net +6.89%/yr (t 2.55), vs BIST 100 TR −1.71%/yr (t −0.28).

**Labels:** A1 `NO_ALPHA` · A2a `EDGE_WEAK_AFTER_CONTROLS` · A3 `SELECTION_DRIVEN` · A4 `GAP_PERSISTS` · B2 `NOT_SIGNIFICANT_AFTER_TRIALS` · B3 `LOW_OVERFIT_RISK` · C `COST_ROBUST_NOT_SIGNIFICANT`.

### A. Attribution

| Test | Window | α %/yr (t) | Loadings (t) | R² |
|---|---|---|---|---|
| A1 CAPM vs BIST 100 TR | holdout | −1.65 (−0.29) | β 1.00 | 0.85 |
| A2a MKT, SMB, WML, LV | full | +5.05 (2.24) | SMB 0.16 (2.7), WML 0.04 (0.6), LV 0.24 (3.1) | 0.95 |
| A2a | discovery | +5.95 (2.18) | SMB 0.16 (1.5), LV 0.07 (0.8) | 0.95 |
| A2a | holdout | +0.89 (0.37) | SMB 0.08 (1.5), LV 0.37 (7.8) | 0.98 |
| A2b + HML_sn | holdout | −0.48 (−0.29) | HML_sn 0.39 (9.7), LV 0.13 (3.3) | 0.99 |

- **A1:** R0 is a market-beta-1 portfolio against BIST 100 TR with no alpha in the holdout.
- **A2a:** in discovery the edge is not explained by size, momentum or low volatility (α +5.95%/yr, t 2.18). In the holdout it is: the low-volatility loading is 0.37 (t 7.8), and α drops to +0.89%/yr (t 0.37). Since 2021, cheap stocks have also been low-volatility stocks, and that exposure carries the edge.
- **A2b:** the value factor HML_sn absorbs the rest (α ≈ 0 in every window), as expected.
- **A3 (Brinson against the EW universe, gross):** holdout selection +8.50%/yr (t 2.91), allocation −0.29%/yr (t −0.29). The edge comes from picking within sectors, not from sector bets. In discovery allocation added +2.85%/yr (t 2.19).
- **A4:** the gap to BIST 100 TR is **not** the missing bank weight. Raw gap −1.71%/yr; after the bank-minus-index term γ = −0.85%/yr (t −0.13), bank loading −0.08 (t −1.92), R² 0.03. The gap is noise around a beta-1 portfolio (A1).
- **A5 (stationary bootstrap, 95%):** holdout vs EW net [+1.7, +11.9]%/yr; vs BIST 100 TR [−13.8, +10.0]%/yr.

### B. Multiple testing

- **Ledger:** 28 studies; 75 stock-selection trials (`N_sel`), 14 market-timing, 6 events/calendar.
- **B2 Deflated Sharpe** (R0 net active vs EW net, T = 161, monthly SR 0.327, skew 0.71, kurtosis 4.20; V[SR] = 0.029 from the 48 variants):

| N | 10 | 26 | 50 | **75** | 100 | 200 |
|---|---|---|---|---|---|---|
| SR₀ | 0.269 | 0.344 | 0.388 | **0.414** | 0.432 | 0.472 |
| DSR | 0.79 | 0.41 | 0.20 | **0.12** | 0.08 | 0.02 |

  After 75 trials, R0's Sharpe is below the best Sharpe expected from chance alone. It would need N ≤ about 5 to reach DSR 0.95.
- **B3 PBO (CSCV, 48 variants, 128 months in 16 blocks, 12,870 splits):** PBO 0.056, median logit 1.24. R0's own variant (`value_sn`, top 20%) has the highest full-sample Sharpe of the 48. The in-sample winner usually stays in the top half out of sample: choosing value_sn from this menu is not an overfit choice.

B2 and B3 answer different questions. B3: among the choices on this panel, value_sn is robustly the best. B2: its absolute Sharpe is not large enough to rule out that the best of 75 tries looks this good by luck. Both stand.

### C. Cost, capacity and limit stress (R0 − EW net, identical settings)

| Cost | Capital | Limit rule | Discovery %/yr (t) | Holdout %/yr (t) | R0 cost %/yr |
|---|---|---|---|---|---|
| ×1 | 1M | off | +10.58 (2.68) | +6.89 (2.55) | 1.50 |
| ×1 | 1M | on | +10.21 (2.73) | +6.03 (2.11) | 1.45 |
| ×2 | 10M | on | +7.41 (1.98) | +4.72 (1.65) | 3.59 |
| **×3** | **10M** | **on** | **+5.42 (1.45)** | **+3.68 (1.29)** | **5.38** |
| ×3 | 50M | on | +1.00 (0.26) | +2.18 (0.77) | 7.27 |

Full grid in the JSON. The edge stays positive at every grid point, but the holdout t falls below 2 with the limit rule from ×2 costs, and at 50M with ×3 costs little is left. The limit rule alone costs about 0.7–0.9%/yr in the holdout. Break-even cost multiplier at 1M with the limit rule: > 8.

### Deviations and interpretation notes

- The ledger is at `data/research/trial_ledger.json`. That folder is git-ignored, so the file is force-added.
- B3 "fewer than 20 names" was read as fewer than 20 stocks with a non-missing signal value. Composite signals use the mean of the available legs.

### What changes

- **Live rule: nothing** (as pre-registered).
- README: R0 is described as a beta-1 portfolio with no alpha against BIST 100 TR, an edge against its own universe that comes from within-sector selection and, since 2021, from a low-volatility tilt, and a Sharpe that does not survive the deflation for 75 trials.

### Ledger update (2026-10-21, after `smc_timing_preregistration.md`)

The SMC timing study added 6 stock-selection trials (S1–S4, X5, X6), all failed. `N_sel` is now 81. With the same series and V[SR], DSR at N = 81 is 0.10 (SR₀ 0.419), against 0.12 at N = 75. The label stays `NOT_SIGNIFICANT_AFTER_TRIALS`. Every future pre-registered stock-selection test adds to `N_sel` the same way.
