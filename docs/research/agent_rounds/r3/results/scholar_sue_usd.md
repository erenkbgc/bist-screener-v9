# Round 3 Backtest Result: `scholar_sue_usd`

- **Date**: 2026-11-24
- **Description**: USD-deflated Standardized Unexpected Earnings tilt on value_sn (80/20 fixed)
- **Combination trial**: No
- **Frozen params**: `{"min_obs": 6, "min_sector_n": 5, "std_window": 8, "w_sue_usd_sn": 0.2, "w_value_sn": 0.8, "winsor_hi": 0.99, "winsor_lo": 0.01}`
- **Pre-registration**: `/home/eren/bist_wt/r3-board/prereg/scholar_sue_usd.md`
- **JSON report**: `/home/eren/bist_wt/r3-backtest/data/reports/research_round3_scholar_sue_usd_2026-11-24.json`
- **Trial ledger `N_sel`**: 94 (`V[SR]` monthly = 0.02335)
- **Primary panel**: `fp/factors_monthly.parquet` (lag-75 PIT, 93 disc / 68 holdout months)
- **Robustness panel**: `fp/factors_monthly_kapdates.parquet` (93 disc / 68 holdout months)

## Verdict (Primary lag-75): **FAIL**

> **Fixed pass rule**: candidate monthly top-20% vs R0 value_sn top-20%, same universe, liquidity cut, 1M TL costs, next-close fills. D = net active(cand) - net active(R0). PASS iff D>0 discovery 2013-2020 NW t>=1.0 AND D>0 holdout 2021+ NW t>=2.0 AND holdout USD maxDD not worse than R0 by >2pp. Report DSR at updated N_sel. Every tested candidate +1 N_sel.

| Check | Value | Threshold | Result |
|---|---:|---:|:---:|
| Discovery D (2013-2020) | +1.43%/yr | > 0 | PASS |
| Discovery NW t(D) | +1.32 | >= 1.00 | PASS |
| Holdout D (2021+) | -1.49%/yr | > 0 | FAIL |
| Holdout NW t(D) | -1.02 | >= 2.00 | FAIL |
| Holdout USD MaxDD vs R0 | -36.8% vs -35.4% (-1.40 pp) | >= -2.00 pp | PASS |

## Primary (lag-75) Performance by Window

| Window | Months | Cand vs EW net %/yr (t) | R0 vs EW net %/yr (t) | Paired D %/yr (NW t) | Cand MaxDD USD | R0 MaxDD USD | Cand Turnover | R0 Turnover | Cand Cost %/yr | Cov % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Discovery (2013-2020) | 93 | +6.57 (+2.80) | +5.14 (+1.97) | +1.43 (+1.32) | -56.7% | -56.6% | 25.7% | 21.4% | 2.27% | 100.0% |
| Holdout (2021+) | 68 | +8.64 (+2.24) | +10.14 (+2.97) | -1.49 (-1.02) | -36.8% | -35.4% | 23.8% | 19.3% | 1.71% | 100.0% |
| IAS 29 (2024-05+) | 28 | +1.32 (+0.31) | +2.19 (+0.56) | -0.87 (-0.61) | -25.0% | -25.1% | 23.1% | 18.4% | 1.75% | 100.0% |
| Full | 161 | +7.44 (+3.48) | +7.25 (+3.38) | +0.19 (+0.21) | -56.7% | -56.6% | 24.9% | 20.5% | 2.04% | 100.0% |

## Deflated Sharpe Ratio (DSR at `N_sel = 94`)

| Strategy | T | Monthly SR | SR0 | Skew | Kurtosis | DSR |
|---|---:|---:|---:|---:|---:|---:|
| `scholar_sue_usd` | 161 | 0.2993 | 0.3834 | 0.595 | 4.016 | 0.1296 |
| `R0` (`value_sn`) | 161 | 0.2830 | 0.3834 | 0.509 | 3.911 | 0.0920 |

## Diagnostics (Primary lag-75)

| Window | Rank-IC (NW t) | dIC vs R0 (NW t) | Rank Corr vs R0 | Top-20% Overlap | Switches/mo | Entrants - Dropouts %/yr (t) |
|---|---:|---:|---:|---:|---:|---:|
| Discovery | +0.0624 (+7.36) | +0.0066 (+2.01) | 0.9085 | 81.6% | 8.08 | +7.53 (+1.33) |
| Holdout | +0.0738 (+4.99) | +0.0004 (+0.15) | 0.8978 | 80.9% | 11.35 | -7.27 (-0.89) |
| IAS 29 | +0.0375 (+2.51) | +0.0031 (+0.70) | 0.8965 | 80.6% | 13.32 | -4.59 (-0.69) |
| Full | +0.0672 (+8.29) | +0.0040 (+1.65) | 0.9039 | 81.3% | 9.46 | +1.28 (+0.26) |

## KAP-date Panel Sensitivity (Robustness Only)

- **Discovery D**: +1.79%/yr (NW t = +1.37)
- **Holdout D**: +2.55%/yr (NW t = +1.46)
- **Holdout USD MaxDD**: -37.4% vs R0 -35.5% (-1.90 pp)
- **KAP-date Verdict**: FAIL (cannot overturn primary lag-75 verdict)
