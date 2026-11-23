# Round 3 Backtest Result: `miner_ocf_ev_real`

- **Date**: 2026-11-24
- **Description**: Real Enterprise Cash-Based Operating Yield tilt on value_sn (80/20 fixed)
- **Combination trial**: No
- **Frozen params**: `{"min_sector_n": 5, "w_ocf_ev_real_sn": 0.2, "w_value_sn": 0.8, "winsor_hi": 0.99, "winsor_lo": 0.01}`
- **Pre-registration**: `/home/eren/bist_wt/r3-board/prereg/miner_ocf_ev_real.md`
- **JSON report**: `/home/eren/bist_wt/r3-backtest/data/reports/research_round3_miner_ocf_ev_real_2026-11-24.json`
- **Trial ledger `N_sel`**: 96 (`V[SR]` monthly = 0.02335)
- **Primary panel**: `fp/factors_monthly.parquet` (lag-75 PIT, 93 disc / 68 holdout months)
- **Robustness panel**: `fp/factors_monthly_kapdates.parquet` (93 disc / 68 holdout months)

## Verdict (Primary lag-75): **FAIL**

> **Fixed pass rule**: candidate monthly top-20% vs R0 value_sn top-20%, same universe, liquidity cut, 1M TL costs, next-close fills. D = net active(cand) - net active(R0). PASS iff D>0 discovery 2013-2020 NW t>=1.0 AND D>0 holdout 2021+ NW t>=2.0 AND holdout USD maxDD not worse than R0 by >2pp. Report DSR at updated N_sel. Every tested candidate +1 N_sel.

| Check | Value | Threshold | Result |
|---|---:|---:|:---:|
| Discovery D (2013-2020) | +3.38%/yr | > 0 | PASS |
| Discovery NW t(D) | +2.35 | >= 1.00 | PASS |
| Holdout D (2021+) | -2.12%/yr | > 0 | FAIL |
| Holdout NW t(D) | -1.67 | >= 2.00 | FAIL |
| Holdout USD MaxDD vs R0 | -36.2% vs -35.4% (-0.80 pp) | >= -2.00 pp | PASS |

## Primary (lag-75) Performance by Window

| Window | Months | Cand vs EW net %/yr (t) | R0 vs EW net %/yr (t) | Paired D %/yr (NW t) | Cand MaxDD USD | R0 MaxDD USD | Cand Turnover | R0 Turnover | Cand Cost %/yr | Cov % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Discovery (2013-2020) | 93 | +8.52 (+3.01) | +5.14 (+1.97) | +3.38 (+2.35) | -56.5% | -56.6% | 22.1% | 21.4% | 1.97% | 100.0% |
| Holdout (2021+) | 68 | +8.02 (+2.05) | +10.14 (+2.97) | -2.12 (-1.67) | -36.2% | -35.4% | 19.7% | 19.3% | 1.45% | 100.0% |
| IAS 29 (2024-05+) | 28 | -1.65 (-0.40) | +2.19 (+0.56) | -3.84 (-1.78) | -26.6% | -25.1% | 19.1% | 18.4% | 1.51% | 100.0% |
| Full | 161 | +8.30 (+3.59) | +7.25 (+3.38) | +1.06 (+0.93) | -56.5% | -56.6% | 21.1% | 20.5% | 1.75% | 100.0% |

## Deflated Sharpe Ratio (DSR at `N_sel = 96`)

| Strategy | T | Monthly SR | SR0 | Skew | Kurtosis | DSR |
|---|---:|---:|---:|---:|---:|---:|
| `miner_ocf_ev_real` | 161 | 0.3089 | 0.3845 | 0.468 | 4.108 | 0.1607 |
| `R0` (`value_sn`) | 161 | 0.2830 | 0.3845 | 0.509 | 3.911 | 0.0895 |

## Diagnostics (Primary lag-75)

| Window | Rank-IC (NW t) | dIC vs R0 (NW t) | Rank Corr vs R0 | Top-20% Overlap | Switches/mo | Entrants - Dropouts %/yr (t) |
|---|---:|---:|---:|---:|---:|---:|
| Discovery | +0.0615 (+6.47) | +0.0057 (+2.03) | 0.9175 | 82.9% | 7.30 | +16.67 (+2.49) |
| Holdout | +0.0725 (+4.50) | -0.0009 (-0.34) | 0.9230 | 84.0% | 9.51 | -7.16 (-0.87) |
| IAS 29 | +0.0317 (+2.20) | -0.0027 (-0.84) | 0.9118 | 83.9% | 11.07 | -18.38 (-1.44) |
| Full | +0.0661 (+7.37) | +0.0029 (+1.40) | 0.9198 | 83.3% | 8.24 | +6.60 (+1.15) |

## KAP-date Panel Sensitivity (Robustness Only)

- **Discovery D**: +2.30%/yr (NW t = +1.68)
- **Holdout D**: -1.18%/yr (NW t = -0.60)
- **Holdout USD MaxDD**: -35.7% vs R0 -35.5% (-0.20 pp)
- **KAP-date Verdict**: FAIL (cannot overturn primary lag-75 verdict)
