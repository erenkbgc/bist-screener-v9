# Round 3 Backtest Result: `miner_gp_qop_real`

- **Date**: 2026-11-24
- **Description**: Gross Profit Yield + Real Operating Profit Surprise Yield tilt on value_sn (70/15/15 fixed)
- **Combination trial**: Yes
- **Frozen params**: `{"min_sector_n": 5, "w_gp_mcap_sn": 0.15, "w_qop_surp_real_sn": 0.15, "w_value_sn": 0.7, "winsor_hi": 0.99, "winsor_lo": 0.01}`
- **Pre-registration**: `/home/eren/bist_wt/r3-board/prereg/miner_gp_qop_real.md`
- **JSON report**: `/home/eren/bist_wt/r3-backtest/data/reports/research_round3_miner_gp_qop_real_2026-11-24.json`
- **Trial ledger `N_sel`**: 98 (`V[SR]` monthly = 0.02335)
- **Primary panel**: `fp/factors_monthly.parquet` (lag-75 PIT, 93 disc / 68 holdout months)
- **Robustness panel**: `fp/factors_monthly_kapdates.parquet` (93 disc / 68 holdout months)

## Verdict (Primary lag-75): **FAIL**

> **Fixed pass rule**: candidate monthly top-20% vs R0 value_sn top-20%, same universe, liquidity cut, 1M TL costs, next-close fills. D = net active(cand) - net active(R0). PASS iff D>0 discovery 2013-2020 NW t>=1.0 AND D>0 holdout 2021+ NW t>=2.0 AND holdout USD maxDD not worse than R0 by >2pp. Report DSR at updated N_sel. Every tested candidate +1 N_sel.

| Check | Value | Threshold | Result |
|---|---:|---:|:---:|
| Discovery D (2013-2020) | +2.31%/yr | > 0 | PASS |
| Discovery NW t(D) | +1.46 | >= 1.00 | PASS |
| Holdout D (2021+) | -2.21%/yr | > 0 | FAIL |
| Holdout NW t(D) | -1.23 | >= 2.00 | FAIL |
| Holdout USD MaxDD vs R0 | -35.9% vs -35.4% (-0.50 pp) | >= -2.00 pp | PASS |

## Primary (lag-75) Performance by Window

| Window | Months | Cand vs EW net %/yr (t) | R0 vs EW net %/yr (t) | Paired D %/yr (NW t) | Cand MaxDD USD | R0 MaxDD USD | Cand Turnover | R0 Turnover | Cand Cost %/yr | Cov % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Discovery (2013-2020) | 93 | +7.45 (+2.82) | +5.14 (+1.97) | +2.31 (+1.46) | -56.0% | -56.6% | 22.8% | 21.4% | 2.02% | 100.0% |
| Holdout (2021+) | 68 | +7.93 (+2.01) | +10.14 (+2.97) | -2.21 (-1.23) | -35.9% | -35.4% | 20.6% | 19.3% | 1.51% | 100.0% |
| IAS 29 (2024-05+) | 28 | -3.97 (-0.98) | +2.19 (+0.56) | -6.16 (-3.95) | -29.9% | -25.1% | 21.3% | 18.4% | 1.65% | 100.0% |
| Full | 161 | +7.65 (+3.37) | +7.25 (+3.38) | +0.40 (+0.31) | -56.0% | -56.6% | 21.9% | 20.5% | 1.80% | 100.0% |

## Deflated Sharpe Ratio (DSR at `N_sel = 98`)

| Strategy | T | Monthly SR | SR0 | Skew | Kurtosis | DSR |
|---|---:|---:|---:|---:|---:|---:|
| `miner_gp_qop_real` | 161 | 0.2917 | 0.3856 | 0.460 | 3.950 | 0.1088 |
| `R0` (`value_sn`) | 161 | 0.2830 | 0.3856 | 0.509 | 3.911 | 0.0872 |

## Diagnostics (Primary lag-75)

| Window | Rank-IC (NW t) | dIC vs R0 (NW t) | Rank Corr vs R0 | Top-20% Overlap | Switches/mo | Entrants - Dropouts %/yr (t) |
|---|---:|---:|---:|---:|---:|---:|
| Discovery | +0.0621 (+6.82) | +0.0063 (+2.18) | 0.9295 | 82.8% | 7.41 | +11.44 (+1.15) |
| Holdout | +0.0764 (+4.83) | +0.0030 (+1.07) | 0.9485 | 85.2% | 8.76 | -17.60 (-1.36) |
| IAS 29 | +0.0338 (+2.29) | -0.0006 (-0.11) | 0.9448 | 84.8% | 10.39 | -39.94 (-3.29) |
| Full | +0.0682 (+7.77) | +0.0049 (+2.35) | 0.9375 | 83.8% | 7.98 | -0.83 (-0.10) |

## KAP-date Panel Sensitivity (Robustness Only)

- **Discovery D**: +1.60%/yr (NW t = +1.18)
- **Holdout D**: -0.94%/yr (NW t = -0.76)
- **Holdout USD MaxDD**: -36.7% vs R0 -35.5% (-1.20 pp)
- **KAP-date Verdict**: FAIL (cannot overturn primary lag-75 verdict)
