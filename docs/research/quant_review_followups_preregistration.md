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
