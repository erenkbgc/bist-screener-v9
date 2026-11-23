# Round 3 Backtest Result: `scholar_cbop`

- **Date**: 2026-11-24
- **Description**: Cash-Based Operating Profitability tilt on value_sn (80/20 fixed)
- **Combination trial**: No
- **Frozen params**: `{"min_sector_n": 5, "w_cbop_sn": 0.2, "w_value_sn": 0.8, "winsor_hi": 0.99, "winsor_lo": 0.01}`
- **Pre-registration**: `/home/eren/bist_wt/r3-board/prereg/scholar_cbop.md`
- **JSON report**: `/home/eren/bist_wt/r3-backtest/data/reports/research_round3_scholar_cbop_2026-11-24.json`
- **Trial ledger `N_sel`**: 93 (`V[SR]` monthly = 0.02335)
- **Primary panel**: `fp/factors_monthly.parquet` (lag-75 PIT, 93 disc / 68 holdout months)
- **Robustness panel**: `fp/factors_monthly_kapdates.parquet` (93 disc / 68 holdout months)

## Verdict (Primary lag-75): **FAIL**

> **Fixed pass rule**: candidate monthly top-20% vs R0 value_sn top-20%, same universe, liquidity cut, 1M TL costs, next-close fills. D = net active(cand) - net active(R0). PASS iff D>0 discovery 2013-2020 NW t>=1.0 AND D>0 holdout 2021+ NW t>=2.0 AND holdout USD maxDD not worse than R0 by >2pp. Report DSR at updated N_sel. Every tested candidate +1 N_sel.

| Check | Value | Threshold | Result |
|---|---:|---:|:---:|
| Discovery D (2013-2020) | +2.71%/yr | > 0 | PASS |
| Discovery NW t(D) | +2.67 | >= 1.00 | PASS |
| Holdout D (2021+) | -2.29%/yr | > 0 | FAIL |
| Holdout NW t(D) | -1.67 | >= 2.00 | FAIL |
| Holdout USD MaxDD vs R0 | -36.2% vs -35.4% (-0.80 pp) | >= -2.00 pp | PASS |

## Primary (lag-75) Performance by Window

| Window | Months | Cand vs EW net %/yr (t) | R0 vs EW net %/yr (t) | Paired D %/yr (NW t) | Cand MaxDD USD | R0 MaxDD USD | Cand Turnover | R0 Turnover | Cand Cost %/yr | Cov % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Discovery (2013-2020) | 93 | +7.85 (+2.68) | +5.14 (+1.97) | +2.71 (+2.67) | -55.7% | -56.6% | 21.7% | 21.4% | 1.91% | 100.0% |
| Holdout (2021+) | 68 | +7.85 (+2.06) | +10.14 (+2.97) | -2.29 (-1.67) | -36.2% | -35.4% | 19.2% | 19.3% | 1.39% | 100.0% |
| IAS 29 (2024-05+) | 28 | -1.50 (-0.42) | +2.19 (+0.56) | -3.69 (-3.03) | -26.6% | -25.1% | 17.8% | 18.4% | 1.38% | 100.0% |
| Full | 161 | +7.85 (+3.34) | +7.25 (+3.38) | +0.60 (+0.61) | -55.7% | -56.6% | 20.6% | 20.5% | 1.69% | 100.0% |

## Deflated Sharpe Ratio (DSR at `N_sel = 93`)

| Strategy | T | Monthly SR | SR0 | Skew | Kurtosis | DSR |
|---|---:|---:|---:|---:|---:|---:|
| `scholar_cbop` | 161 | 0.2897 | 0.3828 | 0.220 | 4.562 | 0.1208 |
| `R0` (`value_sn`) | 161 | 0.2830 | 0.3828 | 0.509 | 3.911 | 0.0932 |

## Diagnostics (Primary lag-75)

| Window | Rank-IC (NW t) | dIC vs R0 (NW t) | Rank Corr vs R0 | Top-20% Overlap | Switches/mo | Entrants - Dropouts %/yr (t) |
|---|---:|---:|---:|---:|---:|---:|
| Discovery | +0.0600 (+5.93) | +0.0042 (+1.24) | 0.9043 | 81.8% | 7.80 | +12.69 (+2.34) |
| Holdout | +0.0706 (+4.56) | -0.0028 (-0.96) | 0.9047 | 82.0% | 10.59 | -10.45 (-1.29) |
| IAS 29 | +0.0314 (+2.03) | -0.0030 (-0.98) | 0.9053 | 83.4% | 11.43 | -19.59 (-2.37) |
| Full | +0.0645 (+7.20) | +0.0012 (+0.52) | 0.9044 | 81.9% | 8.98 | +2.91 (+0.55) |

## KAP-date Panel Sensitivity (Robustness Only)

- **Discovery D**: +1.89%/yr (NW t = +1.76)
- **Holdout D**: -1.41%/yr (NW t = -1.00)
- **Holdout USD MaxDD**: -37.5% vs R0 -35.5% (-2.00 pp)
- **KAP-date Verdict**: FAIL (cannot overturn primary lag-75 verdict)
