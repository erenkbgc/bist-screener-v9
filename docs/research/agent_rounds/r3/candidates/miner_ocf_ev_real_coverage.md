# Coverage Report: `miner_ocf_ev_real (primary leg: ocf_ev_real)`

- **Window**: `2013-04-30 .. 2020-12-31` (discovery-only; holdout 2021+ untouched)
- **Lag75 overall coverage**: 97.54% (19555 / 20049 rows, 93 months, 314 tickers)
- **Lag75 coverage within R0 (`value_sn_z`) universe**: 97.54%
- **Lag75 Spearman corr with R0 (discovery)**: +0.1846
- **Lag75 monthly coverage (min / med / max)**: 94.81% / 97.57% / 99.56%
- **KAP-dates overall coverage**: 97.48% (within R0: 97.48%)
- **Distribution (lag75)**: p01=-0.8235, p25=-0.037, p50=0.0532, p75=0.1485, p99=0.9319

## Coverage by Year (Discovery 2013-2020)

| Year | Lag75 % | KAP-dates % |
| --- | ---: | ---: |
| 2013 | 98.42% | 98.29% |
| 2014 | 97.23% | 97.32% |
| 2015 | 97.38% | 97.39% |
| 2016 | 97.64% | 97.49% |
| 2017 | 97.78% | 97.75% |
| 2018 | 96.81% | 96.78% |
| 2019 | 96.16% | 96.02% |
| 2020 | 99.17% | 99.10% |

## Notes

- **Composite score (`miner_ocf_ev_real`) coverage within R0 universe**: lag75 = 100.00%, kapdates = 100.00% (missing tilt legs fall back to 0.0 per spec).
- **Composite Spearman corr with R0 (`value_sn_z`)**: lag75 = +0.9199, kapdates = +0.9194.
- **Primary leg (`ocf_ev_real`) Spearman corr with R0**: lag75 = +0.1846, kapdates = +0.1829.
- **PIT & unit checks**: `tests/test_round3_features.py` (20/20 passed: zero lookahead, KAP lag respected, TL scale invariance, non-positive EV/mcap guarded, no infinities).
