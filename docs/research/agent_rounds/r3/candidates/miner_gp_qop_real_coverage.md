# Coverage Report: `miner_gp_qop_real (primary leg: gp_mcap)`

- **Window**: `2013-04-30 .. 2020-12-31` (discovery-only; holdout 2021+ untouched)
- **Lag75 overall coverage**: 98.48% (19744 / 20049 rows, 93 months, 314 tickers)
- **Lag75 coverage within R0 (`value_sn_z`) universe**: 98.48%
- **Lag75 Spearman corr with R0 (discovery)**: +0.5008
- **Lag75 monthly coverage (min / med / max)**: 96.04% / 98.65% / 100.00%
- **KAP-dates overall coverage**: 98.45% (within R0: 98.45%)
- **Distribution (lag75)**: p01=-0.0809, p25=0.0882, p50=0.1834, p75=0.3368, p99=1.5032

## Coverage by Year (Discovery 2013-2020)

| Year | Lag75 % | KAP-dates % |
| --- | ---: | ---: |
| 2013 | 99.27% | 99.09% |
| 2014 | 98.66% | 98.70% |
| 2015 | 98.49% | 98.46% |
| 2016 | 98.74% | 98.67% |
| 2017 | 98.61% | 98.65% |
| 2018 | 97.63% | 97.63% |
| 2019 | 96.96% | 96.89% |
| 2020 | 99.82% | 99.82% |

## Notes

- **Composite score (`miner_gp_qop_real`) coverage within R0 universe**: lag75 = 100.00%, kapdates = 100.00% (missing tilt legs fall back to 0.0 per spec).
- **Composite Spearman corr with R0 (`value_sn_z`)**: lag75 = +0.9307, kapdates = +0.9301.
- **Primary leg (`gp_mcap`) Spearman corr with R0**: lag75 = +0.5008, kapdates = +0.4954.
- **Second leg (`qop_surp_real_mcap`) coverage**: lag75 = 98.45%, kapdates = 98.32%.
- **Second leg (`qop_surp_real_mcap`) Spearman corr with R0**: lag75 = +0.0882, kapdates = +0.0939.
- **Joint coverage (`gp_mcap` AND `qop_surp_real_mcap` both non-null)**: lag75 = 98.40%, kapdates = 98.27%.
- **PIT & unit checks**: `tests/test_round3_features.py` (20/20 passed: zero lookahead, KAP lag respected, TL scale invariance, non-positive EV/mcap guarded, no infinities).
