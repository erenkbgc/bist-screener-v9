# Round 4 Value Construction Lab (`vlab`) — Batch `metric_count` Results

- **Date**: 2026-11-24
- **Batch**: `metric_count` (3 variants; **0/3 PASS**)
- **Pre-registration**: `/home/eren/bist_wt/mc/docs/research/metric_count/vlab_metric_count.md`
- **JSON report**: `/home/eren/bist_wt/mc/data/reports/research_round4_vlab_metric_count_2026-11-24.json`
- **Trial ledger `N_sel`**: 116 (`V[SR]` monthly = 0.02335, `SR0` = 0.3946)
- **Primary panel**: `fp/factors_monthly.parquet` (`lag75`, 161 months: 2013-04-30 .. 2026-08-31)
- **Robustness panel**: `fp/factors_monthly_kapdates.parquet` (161 months: 2013-04-30 .. 2026-08-31)
- **Baseline `R0` (`value_sn` top-20% monthly)**: full active vs EW net = +7.25%/yr (NW t=+3.38), full MaxDD USD = -56.6%, 2021+ MaxDD USD = -35.4%, 1-way turnover = 20.5%, DSR = 0.0698

> **Gauntlet rule**: GAUNTLET PASS iff ALL: (1) full 2013-04..latest paired D vs R0 > 0 with NW t >= 2.0; (2) D > 0 in EACH of 4 blocks 2013-16, 2017-20, 2021-23, 2024+; (3) USD maxDD not worse than R0 by > 2pp in full and 2021+; (4) also holds on kapdates panel (D>0, t>=1.0); (5) Holm-adjusted p < 0.05 within your prereg batch; (6) one-way turnover <= 1.5x R0. Report DSR at updated N_sel. Same universe, liquidity cut, 1M TL costs, next-close fills as R0.

## 1. Gauntlet Pass/Fail Table

| Variant | (1) Full D %/yr (NW t) | (2) 4-Block D %/yr (13-16 / 17-20 / 21-23 / 24+) | (3) MaxDD USD Δpp (Full / 21+) | (4) kapdates D %/yr (t) | (5) Holm p | (6) Turn Ratio | DSR | Verdict |
|---|---:|---|---:|---:|---:|---:|---:|:---:|
| `mc_v1_min2` | -0.22 (-0.55) [FAIL] | -0.08 / -0.51 / -1.07 / +0.95 [FAIL] | +0.00 / -0.80 [PASS] | -0.24 (-0.62) [FAIL] | 1.0000 [FAIL] | 0.99x [PASS] | 0.0513 | **FAIL** |
| `mc_v2_min3` | -0.15 (-0.38) [FAIL] | +0.18 / -0.51 / -1.07 / +0.95 [FAIL] | +0.00 / -0.80 [PASS] | -0.26 (-0.68) [FAIL] | 1.0000 [FAIL] | 0.99x [PASS] | 0.0556 | **FAIL** |
| `mc_v3_all4` | -0.68 (-0.82) [FAIL] | -0.91 / -2.00 / +0.69 / +0.05 [FAIL] | -0.60 / +0.00 [PASS] | -0.53 (-0.65) [FAIL] | 1.0000 [FAIL] | 0.99x [PASS] | 0.0290 | **FAIL** |

## 2. Detailed Performance by Variant & Block (Primary `lag75`)

| Strategy | Window | Months | vs EW net %/yr (t) | Paired D %/yr (NW t) | CAGR USD % | MaxDD USD % | Turn % | Cost %/yr | Avg Names |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `R0` | Full (2013-04+) | 161 | +7.25 (+3.38) | — | +10.02% | -56.6% | 20.5% | 1.71% | 49.7 |
| `R0` | 2013-16 | 45 | +6.90 (+3.39) | — | -6.64% | -34.2% | 22.0% | 2.08% | 40.3 |
| `R0` | 2017-20 | 48 | +3.48 (+0.76) | — | +33.44% | -56.6% | 20.8% | 1.78% | 45.0 |
| `R0` | 2021-23 | 36 | +14.21 (+3.83) | — | +16.23% | -35.4% | 19.6% | 1.37% | 51.7 |
| `R0` | 2024+ | 32 | +5.56 (+1.15) | — | -2.47% | -25.1% | 19.0% | 1.48% | 67.7 |
| `R0` | 2021+ | 68 | +10.14 (+2.97) | — | +7.02% | -35.4% | 19.3% | 1.42% | 59.2 |
| `R0` | IAS29 (24-05+) | 28 | +2.19 (+0.56) | — | -9.15% | -25.1% | 18.4% | 1.43% | 68.7 |
| `mc_v1_min2` | Full (2013-04+) | 161 | +7.03 (+3.13) | -0.22 (-0.55) | +9.79% | -56.6% | 20.3% | 1.69% | 49.1 |
| `mc_v1_min2` | 2013-16 | 45 | +6.82 (+3.44) | -0.08 (-0.22) | -6.73% | -34.5% | 21.7% | 2.05% | 39.8 |
| `mc_v1_min2` | 2017-20 | 48 | +2.98 (+0.56) | -0.51 (-0.50) | +32.83% | -56.6% | 20.4% | 1.74% | 44.1 |
| `mc_v1_min2` | 2021-23 | 36 | +13.14 (+3.96) | -1.07 (-1.22) | +14.98% | -36.2% | 19.4% | 1.36% | 51.5 |
| `mc_v1_min2` | 2024+ | 32 | +6.50 (+1.32) | +0.95 (+2.09) | -1.48% | -23.8% | 19.1% | 1.48% | 67.2 |
| `mc_v1_min2` | 2021+ | 68 | +10.02 (+3.13) | -0.12 (-0.20) | +6.92% | -36.2% | 19.3% | 1.42% | 58.9 |
| `mc_v1_min2` | IAS29 (24-05+) | 28 | +3.17 (+0.76) | +0.99 (+1.93) | -8.18% | -23.8% | 18.4% | 1.43% | 68.1 |
| `mc_v2_min3` | Full (2013-04+) | 161 | +7.10 (+3.17) | -0.15 (-0.38) | +9.89% | -56.6% | 20.4% | 1.69% | 49.1 |
| `mc_v2_min3` | 2013-16 | 45 | +7.08 (+3.72) | +0.18 (+0.51) | -6.44% | -33.6% | 21.9% | 2.06% | 39.8 |
| `mc_v2_min3` | 2017-20 | 48 | +2.98 (+0.56) | -0.51 (-0.50) | +32.83% | -56.6% | 20.4% | 1.74% | 44.1 |
| `mc_v2_min3` | 2021-23 | 36 | +13.14 (+3.96) | -1.07 (-1.22) | +14.98% | -36.2% | 19.4% | 1.36% | 51.5 |
| `mc_v2_min3` | 2024+ | 32 | +6.50 (+1.32) | +0.95 (+2.09) | -1.48% | -23.8% | 19.1% | 1.48% | 67.2 |
| `mc_v2_min3` | 2021+ | 68 | +10.02 (+3.13) | -0.12 (-0.20) | +6.92% | -36.2% | 19.3% | 1.42% | 58.9 |
| `mc_v2_min3` | IAS29 (24-05+) | 28 | +3.17 (+0.76) | +0.99 (+1.93) | -8.18% | -23.8% | 18.4% | 1.43% | 68.1 |
| `mc_v3_all4` | Full (2013-04+) | 161 | +6.57 (+2.65) | -0.68 (-0.82) | +9.24% | -57.2% | 20.3% | 1.70% | 46.9 |
| `mc_v3_all4` | 2013-16 | 45 | +5.99 (+2.59) | -0.91 (-0.52) | -7.42% | -33.8% | 21.7% | 2.06% | 37.6 |
| `mc_v3_all4` | 2017-20 | 48 | +1.49 (+0.27) | -2.00 (-1.12) | +30.84% | -57.2% | 20.5% | 1.74% | 41.5 |
| `mc_v3_all4` | 2021-23 | 36 | +14.90 (+3.78) | +0.69 (+0.53) | +16.76% | -35.4% | 19.7% | 1.37% | 49.0 |
| `mc_v3_all4` | 2024+ | 32 | +5.61 (+1.10) | +0.05 (+0.08) | -2.41% | -24.7% | 19.0% | 1.48% | 65.8 |
| `mc_v3_all4` | 2021+ | 68 | +10.53 (+2.90) | +0.39 (+0.51) | +7.31% | -35.4% | 19.4% | 1.42% | 56.9 |
| `mc_v3_all4` | IAS29 (24-05+) | 28 | +2.26 (+0.51) | +0.07 (+0.10) | -9.08% | -24.7% | 18.4% | 1.43% | 66.8 |

## 3. Cross-Sectional Rank-IC, Switcher & DSR Diagnostics (`lag75` Full)

| Strategy | Rank-IC (NW t) | dIC vs R0 (NW t) | Rank Corr vs R0 | Portfolio Overlap | Switches/mo | Entrants - Dropouts %/yr (t) | Monthly SR | DSR (`N_sel`) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `R0` | +0.0632 (+7.02) | — | 1.0000 | 100.0% | 0.00 | — | 0.2830 | 0.0698 |
| `mc_v1_min2` | +0.0619 (+6.63) | -0.0013 (-1.09) | 1.0000 | 99.3% | 0.19 | +0.00 (n/a) | 0.2708 | 0.0513 |
| `mc_v2_min3` | +0.0621 (+6.64) | -0.0011 (-0.94) | 1.0000 | 99.3% | 0.23 | +0.00 (n/a) | 0.2740 | 0.0556 |
| `mc_v3_all4` | +0.0601 (+6.18) | -0.0031 (-1.43) | 1.0000 | 98.1% | 0.20 | +0.00 (n/a) | 0.2468 | 0.0290 |

## 4. KAP-Date Panel Summary (`factors_monthly_kapdates.parquet`)

- **`R0` (`kapdates` full)**: active vs EW net = +7.73%/yr (NW t=+3.86), MaxDD USD = -56.0%, turnover = 20.3%

| Variant | Full D %/yr (NW t) | 2013-16 D | 2017-20 D | 2021-23 D | 2024+ D | MaxDD USD Full / 21+ | Turn % |
|---|---:|---:|---:|---:|---:|---:|---:|
| `mc_v1_min2` | -0.24 (-0.62) | -0.29 | -0.65 | -0.78 | +1.06 | -55.9% / -37.3% | 20.3% |
| `mc_v2_min3` | -0.26 (-0.68) | -0.37 | -0.65 | -0.78 | +1.06 | -55.9% / -37.3% | 20.3% |
| `mc_v3_all4` | -0.53 (-0.65) | +0.08 | -2.95 | +0.74 | +0.79 | -56.6% / -36.8% | 20.2% |

## 5. Frozen Variant Specifications

- **`mc_v1_min2`**: R0 score, only stocks with >= 2 valid value legs | `top_pct=0.2`, `rebalance_months=None`, `frozen_params={"min_legs": 2}`
- **`mc_v2_min3`**: R0 score, only stocks with >= 3 valid value legs | `top_pct=0.2`, `rebalance_months=None`, `frozen_params={"min_legs": 3}`
- **`mc_v3_all4`**: R0 score, only stocks with all 4 valid value legs | `top_pct=0.2`, `rebalance_months=None`, `frozen_params={"min_legs": 4}`

## 6. Descriptive, post-hoc (not part of the verdict)

Inside the R0 top 20% (lag75, 2013-04+), monthly gross return minus the equal-weight universe, times 12:

| Valid legs | Stock-months | Excess %/yr |
|---|---:|---:|
| 1 | 71 | +30.6 |
| 2 | 8 | -28.1 |
| 3 | 260 | +35.7 |
| 4 | 7663 | +7.4 |

Picks with missing legs (4.2% of picks) did better than full-data picks on average, which is why dropping them costs a little. The sample is small and noisy. By sector, Holdings (112 stock-months, +31.9%/yr) and mining (60, +36.2%/yr) carry most of it; tourism is the main loser (17, -51.7%/yr). No rule is drawn from this.

## Conclusion
All 3 variants FAIL; D is within about +/-1%/yr of R0 in every block. Score reliability by leg count does not need a filter: keep R0 as is. `valid_metric_count` stays an information field. N_sel 113 -> 116.
