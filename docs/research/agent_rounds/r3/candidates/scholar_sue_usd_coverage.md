# Coverage Report: `scholar_sue_usd (primary leg: sue_ni_usd)`

- **Window**: `2013-04-30 .. 2020-12-31` (discovery-only; holdout 2021+ untouched)
- **Lag75 overall coverage**: 84.50% (16942 / 20049 rows, 93 months, 314 tickers)
- **Lag75 coverage within R0 (`value_sn_z`) universe**: 84.50%
- **Lag75 Spearman corr with R0 (discovery)**: +0.0545
- **Lag75 monthly coverage (min / med / max)**: 0.00% / 96.71% / 99.57%
- **KAP-dates overall coverage**: 85.69% (within R0: 85.69%)
- **Distribution (lag75)**: p01=-2.3181, p25=-0.5984, p50=0.0186, p75=0.6466, p99=2.5398

## Coverage by Year (Discovery 2013-2020)

| Year | Lag75 % | KAP-dates % |
| --- | ---: | ---: |
| 2013 | 0.00% | 0.00% |
| 2014 | 56.87% | 65.80% |
| 2015 | 95.95% | 96.24% |
| 2016 | 97.71% | 97.91% |
| 2017 | 98.65% | 98.65% |
| 2018 | 96.55% | 96.63% |
| 2019 | 95.80% | 95.91% |
| 2020 | 98.88% | 99.07% |

## Notes

- **Composite score (`scholar_sue_usd`) coverage within R0 universe**: lag75 = 100.00%, kapdates = 100.00% (missing tilt legs fall back to 0.0 per spec).
- **Composite Spearman corr with R0 (`value_sn_z`)**: lag75 = +0.9088, kapdates = +0.9076.
- **Primary leg (`sue_ni_usd`) Spearman corr with R0**: lag75 = +0.0545, kapdates = +0.0667.
- **PIT & unit checks**: `tests/test_round3_features.py` (17/17 passed: zero lookahead, KAP lag respected, TL scale invariance, no infinities).
