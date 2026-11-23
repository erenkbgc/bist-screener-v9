# Round 3 Backtest Result: `miner_qgp_surp_real`

- **Date**: 2026-11-24
- **Description**: Real Quarterly Gross Profit Surprise Yield tilt on value_sn (75/25 fixed)
- **Combination trial**: No
- **Frozen params**: `{"min_sector_n": 5, "w_qgp_surp_real_sn": 0.25, "w_value_sn": 0.75, "winsor_hi": 0.99, "winsor_lo": 0.01}`
- **Pre-registration**: `/home/eren/bist_wt/r3-board/prereg/miner_qgp_surp_real.md`
- **JSON report**: `/home/eren/bist_wt/r3-backtest/data/reports/research_round3_miner_qgp_surp_real_2026-11-24.json`
- **Trial ledger `N_sel`**: 97 (`V[SR]` monthly = 0.02335)
- **Primary panel**: `fp/factors_monthly.parquet` (lag-75 PIT, 93 disc / 68 holdout months)
- **Robustness panel**: `fp/factors_monthly_kapdates.parquet` (93 disc / 68 holdout months)

## Verdict (Primary lag-75): **FAIL**

> **Fixed pass rule**: candidate monthly top-20% vs R0 value_sn top-20%, same universe, liquidity cut, 1M TL costs, next-close fills. D = net active(cand) - net active(R0). PASS iff D>0 discovery 2013-2020 NW t>=1.0 AND D>0 holdout 2021+ NW t>=2.0 AND holdout USD maxDD not worse than R0 by >2pp. Report DSR at updated N_sel. Every tested candidate +1 N_sel.

| Check | Value | Threshold | Result |
|---|---:|---:|:---:|
| Discovery D (2013-2020) | +1.79%/yr | > 0 | PASS |
| Discovery NW t(D) | +1.30 | >= 1.00 | PASS |
| Holdout D (2021+) | -2.13%/yr | > 0 | FAIL |
| Holdout NW t(D) | -1.45 | >= 2.00 | FAIL |
| Holdout USD MaxDD vs R0 | -34.8% vs -35.4% (+0.60 pp) | >= -2.00 pp | PASS |

## Primary (lag-75) Performance by Window

| Window | Months | Cand vs EW net %/yr (t) | R0 vs EW net %/yr (t) | Paired D %/yr (NW t) | Cand MaxDD USD | R0 MaxDD USD | Cand Turnover | R0 Turnover | Cand Cost %/yr | Cov % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Discovery (2013-2020) | 93 | +6.92 (+2.60) | +5.14 (+1.97) | +1.79 (+1.30) | -56.2% | -56.6% | 24.8% | 21.4% | 2.15% | 100.0% |
| Holdout (2021+) | 68 | +8.01 (+2.03) | +10.14 (+2.97) | -2.13 (-1.45) | -34.8% | -35.4% | 22.3% | 19.3% | 1.63% | 100.0% |
| IAS 29 (2024-05+) | 28 | -2.82 (-0.65) | +2.19 (+0.56) | -5.01 (-2.15) | -27.4% | -25.1% | 22.5% | 18.4% | 1.72% | 100.0% |
| Full | 161 | +7.38 (+3.25) | +7.25 (+3.38) | +0.13 (+0.12) | -56.2% | -56.6% | 23.7% | 20.5% | 1.93% | 100.0% |

## Deflated Sharpe Ratio (DSR at `N_sel = 97`)

| Strategy | T | Monthly SR | SR0 | Skew | Kurtosis | DSR |
|---|---:|---:|---:|---:|---:|---:|
| `miner_qgp_surp_real` | 161 | 0.2833 | 0.3851 | 0.402 | 3.856 | 0.0925 |
| `R0` (`value_sn`) | 161 | 0.2830 | 0.3851 | 0.509 | 3.911 | 0.0883 |

## Diagnostics (Primary lag-75)

| Window | Rank-IC (NW t) | dIC vs R0 (NW t) | Rank Corr vs R0 | Top-20% Overlap | Switches/mo | Entrants - Dropouts %/yr (t) |
|---|---:|---:|---:|---:|---:|---:|
| Discovery | +0.0598 (+6.93) | +0.0040 (+0.90) | 0.8822 | 77.4% | 9.67 | +10.37 (+1.53) |
| Holdout | +0.0811 (+5.46) | +0.0077 (+2.88) | 0.8913 | 79.1% | 12.43 | -9.26 (-1.25) |
| IAS 29 | +0.0417 (+2.98) | +0.0073 (+1.52) | 0.8619 | 77.8% | 15.21 | -22.86 (-2.06) |
| Full | +0.0688 (+8.24) | +0.0056 (+1.93) | 0.8861 | 78.1% | 10.83 | +2.08 (+0.38) |

## KAP-date Panel Sensitivity (Robustness Only)

- **Discovery D**: +1.76%/yr (NW t = +1.36)
- **Holdout D**: -0.48%/yr (NW t = -0.26)
- **Holdout USD MaxDD**: -38.0% vs R0 -35.5% (-2.50 pp)
- **KAP-date Verdict**: FAIL (cannot overturn primary lag-75 verdict)
