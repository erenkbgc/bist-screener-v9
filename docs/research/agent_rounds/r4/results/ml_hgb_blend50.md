# Round 4 Gauntlet Result: `ml_hgb_blend50`

- **Date**: 2026-11-24
- **Role / Batch**: `ml` / `ml_batch1` (`m = 2` variants: `ml_hgb`, `ml_hgb_blend50`)
- **Description**: 50/50 cross-sectional percentile-rank average of walk-forward ml_hgb and R0 value_sn_z (2016-01+)
- **Pre-registration**: `/home/eren/bist_wt/r4-board/prereg/ml_batch1.md` (`docs/research/round4_ml_batch1_preregistration.md`)
- **JSON report**: `/home/eren/bist_wt/r4-ml/data/reports/research_round4_ml_2026-11-24.json`
- **Trial ledger `N_sel`**: 100 (`V[SR]` monthly = 0.02335)
- **Evaluation window**: `2016-01-31` .. `2026-08-31` (128 realized return months; first train window `2013-04..2015-12`)
- **Leakage audit**: 129 walk-forward folds verified (`max_train_date < rebalance_date` on 100% of folds; `tests/test_research_round4_ml_leakage.py` PASS)

## Gauntlet Verdict: **FAIL**

| # | Gauntlet Criterion (Blocks Start 2016) | Value | Threshold | Result |
|---:|---|---:|---:|:---:|
| 1 | Full (2016-01+) paired `D` & NW `t` (6 lags) | +0.01%/yr (t = +0.00) | D > 0 & t >= 2.00 | FAIL |
| 2 | All 4 blocks `D > 0` (`2016`, `2017-20`, `2021-23`, `2024+`) | 2016: -0.86%, 2017-20: +0.50%, 2021-23: -1.74%, 2024+: +1.56% | All 4 > 0 | FAIL |
| 3 | USD MaxDD vs R0 (Full / 2021+) | -57.0% vs -56.6% (-0.40 pp) / -35.4% vs -35.4% (+0.00 pp) | Both >= -2.00 pp | PASS |
| 4 | KAP-dates panel Full paired `D` & NW `t` | +0.38%/yr (t = +0.16) | D > 0 & t >= 1.00 | FAIL |
| 5 | Holm-adjusted p-value (`m = 2`, two-sided / one-sided) | 1.0000 (raw 1.0000) / 1-sided 1.0000 | D > 0 & Holm p < 0.05 | FAIL |
| 6 | One-way monthly turnover vs R0 (steady-state ratio) | 32.07% vs 20.71% (1.55x; SS 1.57x) | <= 1.50x R0 | FAIL |

## Primary Panel (`lag75`) Performance by Block & Window

| Window | Months | Cand vs EW net %/yr (t) | R0 vs EW net %/yr (t) | Paired D %/yr (NW t) | Cand MaxDD USD | R0 MaxDD USD | Cand Turn | R0 Turn | Cost %/yr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Block 1: 2016 | 12 | +5.32 (+0.88) | +6.18 (+3.69) | -0.86 (-0.13) | -24.1% | -23.6% | 38.4% | 28.2% | 3.20% |
| Block 2: 2017-20 | 48 | +3.98 (+1.15) | +3.48 (+0.76) | +0.50 (+0.11) | -57.0% | -56.6% | 33.4% | 20.8% | 2.81% |
| Block 3: 2021-23 | 36 | +12.47 (+2.60) | +14.21 (+3.83) | -1.74 (-0.45) | -35.4% | -35.4% | 31.2% | 19.6% | 2.29% |
| Block 4: 2024+ | 32 | +7.12 (+1.38) | +5.56 (+1.15) | +1.56 (+0.91) | -23.0% | -25.1% | 28.6% | 19.0% | 2.33% |
| 2021+ Combined | 68 | +9.95 (+2.70) | +10.14 (+2.97) | -0.18 (-0.08) | -35.4% | -35.4% | 30.0% | 19.3% | 2.31% |
| IAS 29 (2024-05+) | 28 | +3.20 (+0.76) | +2.19 (+0.56) | +1.01 (+0.53) | -23.0% | -25.1% | 28.6% | 18.4% | 2.33% |
| Full (2016-01+) | 128 | +7.28 (+2.64) | +7.27 (+2.78) | +0.01 (+0.00) | -57.0% | -56.6% | 32.1% | 20.7% | 2.58% |

## Deflated Sharpe Ratio (DSR at `N_sel = 100`)

| Strategy | T | Monthly SR | SR0 | Skew | Kurtosis | DSR |
|---|---:|---:|---:|---:|---:|---:|
| `ml_hgb_blend50` | 128 | 0.2561 | 0.3867 | 1.096 | 4.636 | 0.0476 |
| `R0` (`value_sn`) | 128 | 0.2664 | 0.3867 | 0.544 | 3.728 | 0.0769 |

## Cross-Sectional Rank-IC & Switcher Diagnostics (Primary `lag75`)

| Window | Rank-IC (NW t) | dIC vs R0 (NW t) | Rank Corr vs R0 | Top-20% Overlap | Switches/mo | Entrants - Dropouts %/yr (t) |
|---|---:|---:|---:|---:|---:|---:|
| 2016 | +0.0646 (+2.09) | +0.0032 (+0.45) | 0.8214 | 64.0% | 15.33 | -5.48 (-0.29) |
| 2017-20 | +0.0706 (+5.21) | +0.0193 (+1.58) | 0.8333 | 63.1% | 16.73 | +5.47 (+0.47) |
| 2021-23 | +0.1104 (+6.54) | +0.0161 (+2.76) | 0.8604 | 68.0% | 16.14 | -6.88 (-0.63) |
| 2024+ | +0.0799 (+3.67) | +0.0300 (+3.49) | 0.8777 | 72.7% | 18.34 | +9.55 (+1.62) |
| Full (2016-01+) | +0.0836 (+7.76) | +0.0196 (+3.48) | 0.8509 | 67.0% | 16.84 | +1.99 (+0.31) |

## KAP-date Panel Performance (`factors_monthly_kapdates.parquet`)

| Window | Months | Cand vs EW net %/yr (t) | R0 vs EW net %/yr (t) | Paired D %/yr (NW t) | Cand MaxDD USD | R0 MaxDD USD |
|---|---:|---:|---:|---:|---:|---:|
| 2016 | 12 | +5.61 (+1.69) | +9.28 (+3.12) | -3.66 (-0.62) | -23.8% | -21.6% |
| 2017-20 | 48 | +5.56 (+1.70) | +5.42 (+1.17) | +0.14 (+0.03) | -56.4% | -56.0% |
| 2021-23 | 36 | +12.86 (+3.01) | +12.21 (+3.44) | +0.65 (+0.17) | -36.3% | -35.5% |
| 2024+ | 32 | +6.04 (+1.22) | +4.08 (+1.08) | +1.96 (+0.83) | -21.3% | -24.3% |
| Full (2016-01+) | 128 | +7.74 (+3.16) | +7.36 (+3.08) | +0.38 (+0.16) | -56.4% | -56.0% |
