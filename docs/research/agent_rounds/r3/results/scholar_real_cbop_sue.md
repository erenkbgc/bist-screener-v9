# Round 3 Backtest Result: `scholar_real_cbop_sue`

- **Date**: 2026-11-24
- **Description**: Inflation-consistent CbOP + USD SUE 3-pillar tilt on value_sn (75/15/10 fixed)
- **Combination trial**: Yes
- **Frozen params**: `{"min_obs": 6, "min_sector_n": 5, "std_window": 8, "w_cbop_real_sn": 0.15, "w_sue_usd_sn": 0.1, "w_value_sn": 0.75, "winsor_hi": 0.99, "winsor_lo": 0.01}`
- **Pre-registration**: `/home/eren/bist_wt/r3-board/prereg/scholar_real_cbop_sue.md`
- **JSON report**: `/home/eren/bist_wt/r3-backtest/data/reports/research_round3_scholar_real_cbop_sue_2026-11-24.json`
- **Trial ledger `N_sel`**: 95 (`V[SR]` monthly = 0.02335)
- **Primary panel**: `fp/factors_monthly.parquet` (lag-75 PIT, 93 disc / 68 holdout months)
- **Robustness panel**: `fp/factors_monthly_kapdates.parquet` (93 disc / 68 holdout months)

## Verdict (Primary lag-75): **FAIL**

> **Fixed pass rule**: candidate monthly top-20% vs R0 value_sn top-20%, same universe, liquidity cut, 1M TL costs, next-close fills. D = net active(cand) - net active(R0). PASS iff D>0 discovery 2013-2020 NW t>=1.0 AND D>0 holdout 2021+ NW t>=2.0 AND holdout USD maxDD not worse than R0 by >2pp. Report DSR at updated N_sel. Every tested candidate +1 N_sel.

| Check | Value | Threshold | Result |
|---|---:|---:|:---:|
| Discovery D (2013-2020) | +3.86%/yr | > 0 | PASS |
| Discovery NW t(D) | +4.56 | >= 1.00 | PASS |
| Holdout D (2021+) | -2.41%/yr | > 0 | FAIL |
| Holdout NW t(D) | -1.38 | >= 2.00 | FAIL |
| Holdout USD MaxDD vs R0 | -36.8% vs -35.4% (-1.40 pp) | >= -2.00 pp | PASS |

## Primary (lag-75) Performance by Window

| Window | Months | Cand vs EW net %/yr (t) | R0 vs EW net %/yr (t) | Paired D %/yr (NW t) | Cand MaxDD USD | R0 MaxDD USD | Cand Turnover | R0 Turnover | Cand Cost %/yr | Cov % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Discovery (2013-2020) | 93 | +9.00 (+3.48) | +5.14 (+1.97) | +3.86 (+4.56) | -55.8% | -56.6% | 23.0% | 21.4% | 2.03% | 100.0% |
| Holdout (2021+) | 68 | +7.73 (+1.95) | +10.14 (+2.97) | -2.41 (-1.38) | -36.8% | -35.4% | 21.8% | 19.3% | 1.56% | 100.0% |
| IAS 29 (2024-05+) | 28 | -0.85 (-0.21) | +2.19 (+0.56) | -3.04 (-2.20) | -28.3% | -25.1% | 21.2% | 18.4% | 1.62% | 100.0% |
| Full | 161 | +8.46 (+3.74) | +7.25 (+3.38) | +1.21 (+1.10) | -55.8% | -56.6% | 22.5% | 20.5% | 1.83% | 100.0% |

## Deflated Sharpe Ratio (DSR at `N_sel = 95`)

| Strategy | T | Monthly SR | SR0 | Skew | Kurtosis | DSR |
|---|---:|---:|---:|---:|---:|---:|
| `scholar_real_cbop_sue` | 161 | 0.3275 | 0.3840 | 0.498 | 3.786 | 0.2273 |
| `R0` (`value_sn`) | 161 | 0.2830 | 0.3840 | 0.509 | 3.911 | 0.0907 |

## Diagnostics (Primary lag-75)

| Window | Rank-IC (NW t) | dIC vs R0 (NW t) | Rank Corr vs R0 | Top-20% Overlap | Switches/mo | Entrants - Dropouts %/yr (t) |
|---|---:|---:|---:|---:|---:|---:|
| Discovery | +0.0642 (+6.98) | +0.0084 (+2.95) | 0.9080 | 81.1% | 8.13 | +22.52 (+4.31) |
| Holdout | +0.0741 (+4.79) | +0.0007 (+0.25) | 0.9086 | 82.6% | 10.24 | -10.27 (-1.16) |
| IAS 29 | +0.0356 (+2.28) | +0.0012 (+0.44) | 0.9124 | 84.2% | 10.82 | -19.13 (-2.41) |
| Full | +0.0684 (+7.97) | +0.0052 (+2.35) | 0.9083 | 81.7% | 9.02 | +8.67 (+1.47) |

## KAP-date Panel Sensitivity (Robustness Only)

- **Discovery D**: +3.04%/yr (NW t = +2.53)
- **Holdout D**: +2.40%/yr (NW t = +1.28)
- **Holdout USD MaxDD**: -36.6% vs R0 -35.5% (-1.10 pp)
- **KAP-date Verdict**: FAIL (cannot overturn primary lag-75 verdict)
