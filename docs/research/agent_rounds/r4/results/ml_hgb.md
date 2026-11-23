# Round 4 Gauntlet Result: `ml_hgb`

- **Date**: 2026-11-24
- **Role / Batch**: `ml` / `ml_batch1` (`m = 2` variants: `ml_hgb`, `ml_hgb_blend50`)
- **Description**: Expanding-window walk-forward HistGradientBoostingRegressor predicting next-month cross-sectional rank return (PIT value/size/liquidity/momentum/volatility/sector features, 2016-01+)
- **Pre-registration**: `/home/eren/bist_wt/r4-board/prereg/ml_batch1.md` (`docs/research/round4_ml_batch1_preregistration.md`)
- **JSON report**: `/home/eren/bist_wt/r4-ml/data/reports/research_round4_ml_2026-11-24.json`
- **Trial ledger `N_sel`**: 100 (`V[SR]` monthly = 0.02335)
- **Evaluation window**: `2016-01-31` .. `2026-08-31` (128 realized return months; first train window `2013-04..2015-12`)
- **Leakage audit**: 129 walk-forward folds verified (`max_train_date < rebalance_date` on 100% of folds; `tests/test_research_round4_ml_leakage.py` PASS)

## Gauntlet Verdict: **FAIL**

| # | Gauntlet Criterion (Blocks Start 2016) | Value | Threshold | Result |
|---:|---|---:|---:|:---:|
| 1 | Full (2016-01+) paired `D` & NW `t` (6 lags) | -2.46%/yr (t = -0.61) | D > 0 & t >= 2.00 | FAIL |
| 2 | All 4 blocks `D > 0` (`2016`, `2017-20`, `2021-23`, `2024+`) | 2016: -10.33%, 2017-20: -1.39%, 2021-23: -8.91%, 2024+: +6.16% | All 4 > 0 | FAIL |
| 3 | USD MaxDD vs R0 (Full / 2021+) | -59.1% vs -56.6% (-2.50 pp) / -39.9% vs -35.4% (-4.50 pp) | Both >= -2.00 pp | FAIL |
| 4 | KAP-dates panel Full paired `D` & NW `t` | -1.23%/yr (t = -0.26) | D > 0 & t >= 1.00 | FAIL |
| 5 | Holm-adjusted p-value (`m = 2`, two-sided / one-sided) | 1.0000 (raw 0.5430) / 1-sided 1.0000 | D > 0 & Holm p < 0.05 | FAIL |
| 6 | One-way monthly turnover vs R0 (steady-state ratio) | 42.77% vs 20.71% (2.06x; SS 2.11x) | <= 1.50x R0 | FAIL |

## Primary Panel (`lag75`) Performance by Block & Window

| Window | Months | Cand vs EW net %/yr (t) | R0 vs EW net %/yr (t) | Paired D %/yr (NW t) | Cand MaxDD USD | R0 MaxDD USD | Cand Turn | R0 Turn | Cost %/yr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Block 1: 2016 | 12 | -4.16 (-0.95) | +6.18 (+3.69) | -10.33 (-2.08) | -25.3% | -23.6% | 46.3% | 28.2% | 3.61% |
| Block 2: 2017-20 | 48 | +2.09 (+0.36) | +3.48 (+0.76) | -1.39 (-0.16) | -59.1% | -56.6% | 44.6% | 20.8% | 3.83% |
| Block 3: 2021-23 | 36 | +5.30 (+1.45) | +14.21 (+3.83) | -8.91 (-2.36) | -39.9% | -35.4% | 41.5% | 19.6% | 3.30% |
| Block 4: 2024+ | 32 | +11.72 (+1.64) | +5.56 (+1.15) | +6.16 (+1.24) | -27.6% | -25.1% | 40.1% | 19.0% | 3.42% |
| 2021+ Combined | 68 | +8.32 (+2.18) | +10.14 (+2.97) | -1.82 (-0.48) | -39.9% | -35.4% | 40.8% | 19.3% | 3.36% |
| IAS 29 (2024-05+) | 28 | +5.55 (+0.98) | +2.19 (+0.56) | +3.36 (+0.69) | -27.6% | -25.1% | 39.7% | 18.4% | 3.39% |
| Full (2016-01+) | 128 | +4.81 (+1.46) | +7.27 (+2.78) | -2.46 (-0.61) | -59.1% | -56.6% | 42.8% | 20.7% | 3.56% |

## Deflated Sharpe Ratio (DSR at `N_sel = 100`)

| Strategy | T | Monthly SR | SR0 | Skew | Kurtosis | DSR |
|---|---:|---:|---:|---:|---:|---:|
| `ml_hgb` | 128 | 0.1581 | 0.3867 | 0.898 | 4.563 | 0.0030 |
| `R0` (`value_sn`) | 128 | 0.2664 | 0.3867 | 0.544 | 3.728 | 0.0769 |

## Cross-Sectional Rank-IC & Switcher Diagnostics (Primary `lag75`)

| Window | Rank-IC (NW t) | dIC vs R0 (NW t) | Rank Corr vs R0 | Top-20% Overlap | Switches/mo | Entrants - Dropouts %/yr (t) |
|---|---:|---:|---:|---:|---:|---:|
| 2016 | +0.0490 (+1.90) | -0.0124 (-0.86) | 0.3651 | 41.1% | 25.58 | -14.59 (-1.96) |
| 2017-20 | +0.0659 (+3.90) | +0.0146 (+0.63) | 0.4035 | 35.7% | 28.96 | +1.05 (+0.08) |
| 2021-23 | +0.0986 (+7.15) | +0.0043 (+0.28) | 0.4899 | 40.6% | 30.39 | -10.37 (-1.52) |
| 2024+ | +0.0921 (+4.12) | +0.0422 (+2.92) | 0.5461 | 46.7% | 36.16 | +14.17 (+1.75) |
| Full (2016-01+) | +0.0801 (+7.46) | +0.0161 (+1.45) | 0.4598 | 40.3% | 30.84 | -0.35 (-0.06) |

## KAP-date Panel Performance (`factors_monthly_kapdates.parquet`)

| Window | Months | Cand vs EW net %/yr (t) | R0 vs EW net %/yr (t) | Paired D %/yr (NW t) | Cand MaxDD USD | R0 MaxDD USD |
|---|---:|---:|---:|---:|---:|---:|
| 2016 | 12 | -0.38 (-0.09) | +9.28 (+3.12) | -9.66 (-1.67) | -22.8% | -21.6% |
| 2017-20 | 48 | +6.98 (+0.94) | +5.42 (+1.17) | +1.55 (+0.15) | -56.8% | -56.0% |
| 2021-23 | 36 | +6.93 (+1.68) | +12.21 (+3.44) | -5.28 (-1.27) | -39.5% | -35.5% |
| 2024+ | 32 | +6.41 (+0.95) | +4.08 (+1.08) | +2.33 (+0.39) | -25.5% | -24.3% |
| Full (2016-01+) | 128 | +6.13 (+1.63) | +7.36 (+3.08) | -1.23 (-0.26) | -56.8% | -56.0% |
