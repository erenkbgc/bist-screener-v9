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

Added 2026-10-25, after the run. Runner: `python scripts/research_ev_definition.py` → `data/reports/research_ev_definition_2026-10-25.json`.

**Sanity gate: passed.** E0 recomputed from the joined quarterly table equals the stored panel `ey`, `ey_z` and `value_sn_z` exactly (0 NaN mismatches, max relative difference 0.0). Coverage over 24,089 quarters: short-term financial investments non-zero in 35.7%, minority interest non-zero in 39.3%, either item missing in 0.06%. The panel's last decision month is 2026-09 (one month later than the window written above; same panel the other studies use).

### Rank-IC (sector-neutral, `fwd_ret_1m`; NW t, 6 lags)

| Variant | Window | `ey_k` IC (t) | ΔIC vs E0 (t) | `value_sn_k` IC (t) | ΔIC vs E0 (t) |
|---|---|---:|---:|---:|---:|
| E0 | Discovery | +0.0420 (4.61) | | +0.0407 (5.14) | |
| | Holdout | +0.0532 (4.67) | | +0.0617 (4.91) | |
| | IAS 29 | +0.0372 (3.00) | | +0.0340 (2.22) | |
| **E1** | Discovery | +0.0398 (4.31) | −0.0022 (−0.85) | +0.0386 (5.05) | −0.0021 (−1.25) |
| | Holdout | +0.0542 (4.57) | +0.0010 (0.72) | +0.0625 (4.96) | +0.0007 (1.39) |
| | IAS 29 | +0.0373 (2.85) | +0.0001 (0.10) | +0.0340 (2.23) | +0.0000 (0.02) |
| E1a (diag.) | Discovery | +0.0399 (4.10) | −0.0022 (−1.41) | +0.0389 (4.93) | −0.0018 (−1.98) |
| | Holdout | +0.0511 (4.33) | −0.0022 (−1.82) | +0.0609 (4.84) | −0.0009 (−1.70) |
| E1b (diag.) | Discovery | +0.0418 (4.77) | −0.0002 (−0.14) | +0.0407 (5.10) | +0.0000 (0.03) |
| | Holdout | +0.0548 (4.68) | +0.0016 (1.45) | +0.0626 (4.95) | +0.0009 (1.85) |

### Top-20% changes vs E0

| Variant | Window | Overlap | Switches / month | Entrants − dropouts %/yr (t) |
|---|---|---:|---:|---:|
| **E1** | Discovery | 93.0% | 3.0 | −8.38 (−0.50) |
| | Holdout | 96.0% | 2.3 | −24.62 (−1.67) |
| | IAS 29 | 97.3% | 1.9 | −50.82 (−2.72) |
| E1a (diag.) | Discovery / Holdout | 94.8% / 96.4% | 2.3 / 2.1 | +10.22 (0.97) / −21.02 (−1.11) |
| E1b (diag.) | Discovery / Holdout | 95.5% / 96.8% | 1.9 / 1.8 | −24.92 (−0.79) / +0.22 (0.01) |

### Costed portfolio (1M TL real, base costs, next-day close)

| Variant | Window | Active vs EW net %/yr (t) | Paired D vs E0 %/yr (t) | USD CAGR | Max DD USD |
|---|---|---:|---:|---:|---:|
| E0 | Discovery | +10.58 (2.68) | | +17.57% | −58.1% |
| | Holdout | +6.89 (2.55) | | +3.61% | −43.9% |
| | IAS 29 | +2.74 (0.70) | | −8.66% | −24.3% |
| **E1** | Discovery | +9.55 (2.60) | **−1.03 (−0.69)** | +16.64% | −58.2% |
| | Holdout | +6.26 (2.37) | **−0.63 (−1.00)** | +3.09% | −42.9% |
| | IAS 29 | +1.61 (0.41) | −1.12 (−2.29) | −9.71% | −25.4% |
| E1a (diag.) | Discovery / Holdout | +10.79 (2.83) / +6.05 (2.17) | +0.21 (0.25) / −0.84 (−1.27) | | |
| E1b (diag.) | Discovery / Holdout | +9.84 (2.54) / +7.33 (2.72) | −0.73 (−0.47) / +0.44 (0.65) | | |

### Verdict: `KEEP_E0`

- E1 is not SUPERIOR (D is negative in both windows).
- E1 fails ADOPT_CORRECTION: D is −1.03%/yr in discovery (bound −0.50) and −0.63%/yr with t −1.00 in holdout (bound t > −1.0). The other two conditions hold (holdout ΔIC t 1.39; holdout active vs EW net +6.26%/yr).
- The correction changes only 2–3 of about 60 holdings a month (93–97% overlap). The stocks it removes did better than the ones it adds, most clearly in the IAS 29 window (−50.8%/yr, t −2.72, on about 2 names a month).
- The live `ey` keeps the current definition. `config/live_rule.json` is unchanged.

**Post-hoc observation (not a result).** Minority interest alone (E1b) is the only variant with a non-negative holdout difference (+0.44%/yr, t 0.65; ΔIC t 1.85), and short-term investments alone (E1a) are the part that hurts in holdout. E1b was a diagnostic, chosen before the run only to explain E1, so it cannot be adopted from this run. A test of E1b alone would need a new pre-registration and would count as another trial.
