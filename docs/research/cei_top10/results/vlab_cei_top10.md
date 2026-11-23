# Round 4 Value Construction Lab (`vlab`) — Batch `cei_top10` Results

- **Date**: 2026-11-24
- **Batch**: `cei_top10` (3 variants; **0/3 PASS**)
- **Pre-registration**: `/home/eren/bist_wt/cei/docs/research/cei_top10/vlab_cei_top10.md`
- **JSON report**: `/home/eren/bist_wt/cei/data/reports/research_round4_vlab_cei_top10_2026-11-24.json`
- **Trial ledger `N_sel`**: 119 (`V[SR]` monthly = 0.02335, `SR0` = 0.3960)
- **Primary panel**: `fp/factors_monthly.parquet` (`lag75`, 161 months: 2013-04-30 .. 2026-08-31)
- **Robustness panel**: `fp/factors_monthly_kapdates.parquet` (161 months: 2013-04-30 .. 2026-08-31)
- **Baseline `R0` (`value_sn` top-20% monthly)**: full active vs EW net = +7.25%/yr (NW t=+3.38), full MaxDD USD = -56.6%, 2021+ MaxDD USD = -35.4%, 1-way turnover = 20.5%, DSR = 0.0674

> **Gauntlet rule**: GAUNTLET PASS iff ALL: (1) full 2013-04..latest paired D vs R0 > 0 with NW t >= 2.0; (2) D > 0 in EACH of 4 blocks 2013-16, 2017-20, 2021-23, 2024+; (3) USD maxDD not worse than R0 by > 2pp in full and 2021+; (4) also holds on kapdates panel (D>0, t>=1.0); (5) Holm-adjusted p < 0.05 within your prereg batch; (6) one-way turnover <= 1.5x R0. Report DSR at updated N_sel. Same universe, liquidity cut, 1M TL costs, next-close fills as R0.

## 1. Gauntlet Pass/Fail Table

| Variant | (1) Full D %/yr (NW t) | (2) 4-Block D %/yr (13-16 / 17-20 / 21-23 / 24+) | (3) MaxDD USD Δpp (Full / 21+) | (4) kapdates D %/yr (t) | (5) Holm p | (6) Turn Ratio | DSR | Verdict |
|---|---:|---|---:|---:|---:|---:|---:|:---:|
| `r0_no_issuers` | -1.06 (-0.68) [FAIL] | -0.92 / -1.21 / +0.60 / -2.89 [FAIL] | +1.10 / -1.30 [PASS] | -1.24 (-0.78) [FAIL] | 0.6288 [FAIL] | 0.98x [PASS] | 0.0131 | **FAIL** |
| `value_cei_20` | -1.16 (-1.45) [FAIL] | -0.40 / -1.87 / -1.16 / -1.18 [FAIL] | +0.60 / +1.30 [PASS] | -0.71 (-0.70) [FAIL] | 0.4438 [FAIL] | 0.98x [PASS] | 0.0144 | **FAIL** |
| `r0_top10` | +1.85 (+1.01) [FAIL] | -1.46 / +6.50 / -1.97 / +3.82 [FAIL] | -0.10 / -1.20 [PASS] | +1.04 (+0.54) [FAIL] | 0.6288 [FAIL] | 1.13x [PASS] | 0.0279 | **FAIL** |

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
| `r0_no_issuers` | Full (2013-04+) | 161 | +6.19 (+2.35) | -1.06 (-0.68) | +9.10% | -55.5% | 20.2% | 1.69% | 40.1 |
| `r0_no_issuers` | 2013-16 | 45 | +5.98 (+2.03) | -0.92 (-0.36) | -7.45% | -34.2% | 22.0% | 2.16% | 32.9 |
| `r0_no_issuers` | 2017-20 | 48 | +2.28 (+0.43) | -1.21 (-0.81) | +31.99% | -55.5% | 20.7% | 1.76% | 38.3 |
| `r0_no_issuers` | 2021-23 | 36 | +14.81 (+3.10) | +0.60 (+0.17) | +17.33% | -36.7% | 18.8% | 1.25% | 38.0 |
| `r0_no_issuers` | 2024+ | 32 | +2.67 (+0.43) | -2.89 (-0.60) | -4.81% | -26.6% | 18.3% | 1.42% | 55.2 |
| `r0_no_issuers` | 2021+ | 68 | +9.10 (+2.03) | -1.04 (-0.34) | +6.34% | -36.7% | 18.6% | 1.33% | 46.1 |
| `r0_no_issuers` | IAS29 (24-05+) | 28 | +0.44 (+0.07) | -1.75 (-0.32) | -10.31% | -26.3% | 18.5% | 1.44% | 56.3 |
| `value_cei_20` | Full (2013-04+) | 161 | +6.09 (+2.58) | -1.16 (-1.45) | +8.88% | -56.0% | 20.2% | 1.68% | 49.7 |
| `value_cei_20` | 2013-16 | 45 | +6.50 (+2.87) | -0.40 (-0.24) | -7.00% | -34.5% | 22.9% | 2.12% | 40.3 |
| `value_cei_20` | 2017-20 | 48 | +1.62 (+0.35) | -1.87 (-1.61) | +31.21% | -56.0% | 19.6% | 1.68% | 45.0 |
| `value_cei_20` | 2021-23 | 36 | +13.05 (+2.62) | -1.16 (-0.62) | +15.24% | -34.1% | 17.8% | 1.24% | 51.7 |
| `value_cei_20` | 2024+ | 32 | +4.37 (+0.83) | -1.18 (-0.65) | -3.63% | -23.5% | 19.9% | 1.56% | 67.7 |
| `value_cei_20` | 2021+ | 68 | +8.97 (+2.24) | -1.17 (-0.90) | +5.94% | -34.1% | 18.8% | 1.39% | 59.2 |
| `value_cei_20` | IAS29 (24-05+) | 28 | +0.99 (+0.23) | -1.20 (-0.58) | -10.20% | -23.5% | 19.6% | 1.54% | 68.7 |
| `r0_top10` | Full (2013-04+) | 161 | +9.10 (+3.36) | +1.85 (+1.01) | +11.68% | -56.7% | 23.2% | 2.09% | 24.6 |
| `r0_top10` | 2013-16 | 45 | +5.44 (+1.59) | -1.46 (-0.66) | -8.17% | -34.6% | 25.5% | 2.74% | 20.0 |
| `r0_top10` | 2017-20 | 48 | +9.98 (+2.20) | +6.50 (+1.95) | +41.78% | -56.7% | 23.4% | 2.18% | 22.3 |
| `r0_top10` | 2021-23 | 36 | +12.24 (+1.88) | -1.97 (-0.54) | +13.80% | -36.6% | 22.1% | 1.52% | 25.6 |
| `r0_top10` | 2024+ | 32 | +9.37 (+1.24) | +3.82 (+1.04) | +0.66% | -28.2% | 20.9% | 1.70% | 33.6 |
| `r0_top10` | 2021+ | 68 | +10.89 (+2.19) | +0.75 (+0.28) | +7.41% | -36.6% | 21.6% | 1.61% | 29.3 |
| `r0_top10` | IAS29 (24-05+) | 28 | +4.88 (+0.71) | +2.69 (+0.68) | -7.13% | -28.2% | 20.4% | 1.67% | 34.1 |

## 3. Cross-Sectional Rank-IC, Switcher & DSR Diagnostics (`lag75` Full)

| Strategy | Rank-IC (NW t) | dIC vs R0 (NW t) | Rank Corr vs R0 | Portfolio Overlap | Switches/mo | Entrants - Dropouts %/yr (t) | Monthly SR | DSR (`N_sel`) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `R0` | +0.0632 (+7.02) | — | 1.0000 | 100.0% | 0.00 | — | 0.2830 | 0.0674 |
| `r0_no_issuers` | +0.0609 (+5.96) | -0.0023 (-0.56) | 1.0000 | 94.8% | 0.98 | +0.00 (n/a) | 0.2242 | 0.0131 |
| `value_cei_20` | +0.0627 (+6.47) | -0.0006 (-0.25) | 0.9299 | 89.4% | 5.31 | -15.34 (-1.75) | 0.2309 | 0.0144 |
| `r0_top10` | +0.0632 (+7.02) | +0.0000 (n/a) | 1.0000 | 49.5% | 0.00 | +0.00 (n/a) | 0.2553 | 0.0279 |

## 4. KAP-Date Panel Summary (`factors_monthly_kapdates.parquet`)

- **`R0` (`kapdates` full)**: active vs EW net = +7.73%/yr (NW t=+3.86), MaxDD USD = -56.0%, turnover = 20.3%

| Variant | Full D %/yr (NW t) | 2013-16 D | 2017-20 D | 2021-23 D | 2024+ D | MaxDD USD Full / 21+ | Turn % |
|---|---:|---:|---:|---:|---:|---:|---:|
| `r0_no_issuers` | -1.24 (-0.78) | -1.29 | -3.96 | +2.45 | -1.26 | -54.3% / -34.0% | 20.4% |
| `value_cei_20` | -0.71 (-0.70) | +0.58 | -3.96 | +2.52 | -1.27 | -55.1% / -34.7% | 20.6% |
| `r0_top10` | +1.04 (+0.54) | -4.19 | +2.91 | +2.01 | +4.52 | -56.9% / -36.7% | 22.9% |

## 5. Frozen Variant Specifications

- **`r0_no_issuers`**: R0 top 20% among stocks with CEI_5y = 0 (no net rights issue in 5y) | `top_pct=0.2`, `rebalance_months=None`, `frozen_params={"window_months": 60}`
- **`value_cei_20`**: 0.8*value_sn_z + 0.2*(-CEI_5y sn z, NaN->0), top 20% | `top_pct=0.2`, `rebalance_months=None`, `frozen_params={"w_cei": 0.2, "window_months": 60}`
- **`r0_top10`**: R0 value_sn_z, top 10% instead of 20% | `top_pct=0.1`, `rebalance_months=None`, `frozen_params={"top_pct": 0.1}`

## Conclusion
All 3 FAIL. Excluding 5-year rights issuers (D -1.06%/yr) and tilting away from them (D -1.16%/yr) both cost a little in most blocks: inside cheap stocks, issuers did not underperform. R0 top 10% is +1.85%/yr (t 1.01) with 2017-20 +6.50 and 2024+ +3.82, but 2013-16 -1.46 and 2021-23 -1.97, so it fails the all-blocks rule; it stays in the shadow forward record. N_sel 116 -> 119. Live rule unchanged.
