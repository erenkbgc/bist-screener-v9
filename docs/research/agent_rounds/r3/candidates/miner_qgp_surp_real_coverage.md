# Coverage Report: `miner_qgp_surp_real (primary leg: qgp_surp_real_mcap)`

- **Window**: `2013-04-30 .. 2020-12-31` (discovery-only; holdout 2021+ untouched)
- **Lag75 overall coverage**: 98.45% (19739 / 20049 rows, 93 months, 314 tickers)
- **Lag75 coverage within R0 (`value_sn_z`) universe**: 98.45%
- **Lag75 Spearman corr with R0 (discovery)**: +0.0746
- **Lag75 monthly coverage (min / med / max)**: 96.04% / 98.64% / 100.00%
- **KAP-dates overall coverage**: 98.32% (within R0: 98.32%)
- **Distribution (lag75)**: p01=-0.1767, p25=-0.0101, p50=0.0016, p75=0.0158, p99=0.1784

## Coverage by Year (Discovery 2013-2020)

| Year | Lag75 % | KAP-dates % |
| --- | ---: | ---: |
| 2013 | 99.27% | 97.93% |
| 2014 | 98.49% | 98.49% |
| 2015 | 98.49% | 98.42% |
| 2016 | 98.90% | 98.71% |
| 2017 | 98.76% | 98.72% |
| 2018 | 97.37% | 97.48% |
| 2019 | 96.96% | 96.89% |
| 2020 | 99.75% | 99.78% |

## Notes

- **Composite score (`miner_qgp_surp_real`) coverage within R0 universe**: lag75 = 100.00%, kapdates = 100.00% (missing tilt legs fall back to 0.0 per spec).
- **Composite Spearman corr with R0 (`value_sn_z`)**: lag75 = +0.8835, kapdates = +0.8836.
- **Primary leg (`qgp_surp_real_mcap`) Spearman corr with R0**: lag75 = +0.0746, kapdates = +0.0806.
- **PIT & unit checks**: `tests/test_round3_features.py` (20/20 passed: zero lookahead, KAP lag respected, TL scale invariance, non-positive EV/mcap guarded, no infinities).
