# Enterprise value definition in `ey` (short-term investments and minority interest): pre-registration

Written and committed on 2026-10-25, **before** the runner was written or executed on the panel. Variants, metrics, windows and decision rules are fixed here and are not changed after seeing the results.

## Question

`ey` is one of the four legs of `value_sn`, and the strongest one in every window (`value_ablation_preregistration.md`). Today it is

$$ey = \frac{\text{TTM operating profit}}{\text{mcap} + \text{fin\_debt} - \text{cash}}$$

(`core/pit_panel.py::value_ratios`, the same function in the research panel and the live score). `fin_debt` is short-term plus long-term "Finansal Borçlar". Two parts of this enterprise value do not match standard practice:

1. **Short-term financial investments are not netted.** `cash` is only "Nakit ve Nakit Benzerleri". The current-asset line "Finansal Yatırımlar" (time deposits over 3 months, government bonds, FX-protected deposits) is left out, so EV is too high and `ey` too low for cash-rich companies.
2. **Minority interest is not added.** TTM operating profit is consolidated and includes the part that belongs to minority shareholders of subsidiaries, but `mcap` covers only the parent. EV is too low and `ey` too high for groups and holdings.

This is a definition correction motivated by accounting consistency (for example Koller, Goedhart & Wessels, *Valuation*, ch. on enterprise value: non-operating financial assets are subtracted, non-controlling interests are added). It is not a new signal.

## Prior exposure, stated honestly

- The C1 panel (2013-04 to 2026-08), the baseline `value_sn` results and the single-leg ICs of `ey` are known (`value_ablation_preregistration.md`, `portfolio_backtest_preregistration.md`).
- On 2026-10-25 a one-off check of the latest quarter (2026Q2) of 40 large stocks was made from live data, **without any returns**: median absolute EV change from both corrections 3.8%, 7 of 40 above 10% (largest: AEFES +78%, ISMEN −54%, ENKAI −31%, KCHOL +24%).
- A label check of the 576 raw research statements (no values, no returns): every file has "Finansal Yatırımlar" (first occurrence inside current assets) and "Azınlık Payları".
- No rank-IC, return or portfolio result of the corrected `ey` has been computed before this document.

## Data and universe

Identical to `value_ablation_preregistration.md`:
- C1 monthly panel from `research_long_term.load()` (lag-75/100 report availability, IAS 29 flows in constant purchasing power, bottom 30% by `tlvol60` dropped each month, non-financial stocks).
- **Discovery:** decisions 2013-04 to 2020-12. **Holdout:** 2021-01 to 2026-08. **IAS 29 sub-window (descriptive):** 2024-05 to 2026-08.

New balance-sheet items, read from `data/research/raw/*.pkl` with `pit_panel._pick` (first occurrence, no summing):
- `st_fin_inv`: "Finansal Yatırımlar" (first occurrence = current assets).
- `minority`: "Azınlık Payları", as reported (a negative value is kept).

They are joined to each stock-month on (`ticker`, `stmt_period`), so they come from the same quarter as `fin_debt`, `cash` and TTM operating profit. A missing or NaN value of either new item counts as 0 (the line exists in every template; a blank means nothing reported). The share of stock-months where each item is non-zero is reported.

**Sanity gate (run first):** `ey` recomputed from the joined quarterly table with the old formula must equal the stored panel `ey` (relative difference below 1e-9 on all non-NaN rows, same NaN pattern). If the gate fails, the study stops and nothing is concluded.

## Variants (fixed)

$$EV_k = \text{mcap} + \text{fin\_debt} - \text{cash} - a_k \cdot \text{st\_fin\_inv} + b_k \cdot \text{minority}$$

$ey_k = \text{TTM op profit} / EV_k$ when $EV_k > 0$, NaN otherwise (same rule as today).

| ID | $a_k$ | $b_k$ | Role |
|---|---|---|---|
| E0 | 0 | 0 | Baseline, current live definition |
| **E1** | 1 | 1 | **Primary: both corrections** |
| E1a | 1 | 0 | Diagnostic only (short-term investments alone) |
| E1b | 0 | 1 | Diagnostic only (minority alone) |

For each variant, `value_sn_k` is built exactly like the live `value_sn` (V0 of the ablation study): each of `bm`, `ep`, `sp`, `ey_k` winsorized 1%/99% and z-scored within the month's liquid universe (`factor_backtest.prepare` settings), equal-weighted mean, sector-neutralized with `min_n = 5`.

Only E1 is a decision candidate. E1a and E1b are reported to show which correction drives any difference; they cannot change the verdict. The trial ledger counts **1** new stock-selection trial (E1).

## Metrics

Same code paths as `scripts/research_value_ablation.py`, comparing E1 (and descriptively E1a, E1b) with E0, in Discovery, Holdout and the IAS 29 window:
1. Standalone rank-IC of `ey_k` (sector-neutral) and of `value_sn_k` against `fwd_ret_1m`, Newey-West $t$ (6 lags); paired $\Delta\text{IC}$ vs E0.
2. Top-20% overlap with E0, rank correlation, and switcher spread (entrants minus dropouts, annualised, NW $t$).
3. Costed portfolio simulation (`core/portfolio_backtest.py::simulate`, 1M TL real capital, base costs, next-day close, cash at the policy rate): active return vs costed EW universe, and the **paired difference** $D = r_\text{net}(E1) - r_\text{net}(E0)$, annualised, NW $t$ (6 lags). Turnover, cost drag, max drawdown TL/USD.

## Decision rules

1. **SUPERIOR:** $D > 0$ with $t > 3.0$ in Discovery **and** $D > 0$ with $t > 2.0$ in Holdout **and** positive switcher spread in both windows.
2. **ADOPT_CORRECTION** (non-inferior definition fix): not SUPERIOR, but all of:
   - $D > -0.50\%$/yr and $t > -1.0$ in **both** Discovery and Holdout,
   - holdout paired $\Delta\text{IC}$ of `value_sn` (E1 − E0) has $t > -1.0$,
   - holdout costed active return of E1 vs EW net $> 0$.
3. **KEEP_E0:** otherwise.

Why a non-inferiority rule: the correction is chosen on accounting grounds before any test; the test only guards against the correction making the tested signal worse. A definition fix that is not worse is preferred, because the live `ey` should measure what its name says.

## Live rule

No live change is made by this study automatically. If E1 is SUPERIOR or ADOPT_CORRECTION, `core/pit_panel.py::value_ratios` changes in a separate PR for the panel and the live score together (the parity test `tests/test_valuation_parity.py` must keep passing), and `config/live_rule.json` gets a new version so the forward record splits cleanly.

## Results

(Appended after the run; the sections above stay unchanged.)
