# Coverage Report: `scholar_real_cbop_sue (primary leg: cbop_real)`

- **Window**: `2013-04-30 .. 2020-12-31` (discovery-only; holdout 2021+ untouched)
- **Lag75 overall coverage**: 98.40% (19729 / 20049 rows, 93 months, 314 tickers)
- **Lag75 coverage within R0 (`value_sn_z`) universe**: 98.40%
- **Lag75 Spearman corr with R0 (discovery)**: +0.0795
- **Lag75 monthly coverage (min / med / max)**: 96.04% / 98.63% / 100.00%
- **KAP-dates overall coverage**: 98.38% (within R0: 98.38%)
- **Distribution (lag75)**: p01=-0.5131, p25=-0.0308, p50=0.0526, p75=0.1306, p99=0.5209

## Coverage by Year (Discovery 2013-2020)

| Year | Lag75 % | KAP-dates % |
| --- | ---: | ---: |
| 2013 | 99.27% | 99.09% |
| 2014 | 98.57% | 98.62% |
| 2015 | 98.33% | 98.34% |
| 2016 | 98.74% | 98.67% |
| 2017 | 98.57% | 98.53% |
| 2018 | 97.33% | 97.37% |
| 2019 | 96.96% | 96.89% |
| 2020 | 99.82% | 99.82% |

## Notes

- **Composite score (`scholar_real_cbop_sue`) coverage within R0 universe**: lag75 = 100.00%, kapdates = 100.00% (missing tilt legs fall back to 0.0 per spec).
- **Composite Spearman corr with R0 (`value_sn_z`)**: lag75 = +0.9109, kapdates = +0.9107.
- **Primary leg (`cbop_real`) Spearman corr with R0**: lag75 = +0.0795, kapdates = +0.0783.
- **Second leg (`sue_ni_usd`) coverage**: lag75 = 84.50%, kapdates = 85.69%.
- **Joint coverage (`cbop_real` AND `sue_ni_usd` both non-null)**: lag75 = 84.39%, kapdates = 85.58%.
- **PIT & unit checks**: `tests/test_round3_features.py` (17/17 passed: zero lookahead, KAP lag respected, TL scale invariance, no infinities).
