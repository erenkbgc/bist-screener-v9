# value_sn ratio coverage: diagnostics (2026-10-17)

This is a diagnostic, not a hypothesis test. Nothing here changes the live rule. A rule such as "at least three ratios" would need its own pre-registration.

Run: `python scripts/diagnose_ratio_coverage.py`. Output: `data/reports/diagnose_ratio_coverage_2026-10-17.json`. The panel, liquidity cut and selection are the same as in `research_survivorship.py` (`prepare`, bottom 30% dropped, `add_composites`, top 20% by `value_sn_z`). The primary panel is kapdates; lag75 gives the same picture.

`value_sn` is the sector-neutral mean z of E/P, B/M, S/P and EBIT/EV. A missing ratio is left out of the mean, so a stock can be ranked on one to four ratios.

## 1. How many ratios the picks use

| | Universe: 4 / 3 / ≤2 ratios | Top 20%: 4 / 3 / ≤2 ratios |
|---|---|---|
| Discovery 2013–2020 | 92.6% / 5.8% / 1.6% | 93.0% / 4.9% / 2.1% |
| Holdout 2021+ | 95.9% / 3.3% / 0.8% | 96.1% / 3.0% / 1.0% |

- Missing ratios are **not** concentrated in the picks. Per ratio, the picks miss 1.0–4.4%; the universe misses 0.8–3.6%. S/P is missing most often.
- By year, 90.5–97.6% of picks have all four ratios. The lowest year is 2018.

## 2. Sector neutralization

Sectors with fewer than 5 names are demeaned against the whole month instead of their sector. 20.1% of discovery picks and 11.2% of holdout picks are in such small groups. The universe shares are 21.4% and 12.8%, so small groups are not over-picked.

## 3. Dropping one ratio (information only)

| Composite | Picks kept | Rank corr. | Discovery net active (t) | Holdout net active (t) |
|---|---|---|---|---|
| all four (live) | – | – | +9.26% (2.75) | +5.14% (1.99) |
| without B/M | 82.2% | 0.90 | +8.05% (2.08) | +5.98% (2.24) |
| without E/P | 86.9% | 0.91 | +9.59% (2.68) | +3.51% (1.39) |
| without S/P | 82.5% | 0.93 | +8.84% (2.43) | +5.78% (1.87) |
| without EBIT/EV | 82.4% | 0.91 | +8.35% (3.10) | +5.16% (1.82) |

- No single ratio drives the list: dropping any one keeps 82–87% of the picks.
- Holdout returns move by up to 2.5 points/yr between the variants (lag75: up to 2.7). This is within the noise of a 68-month holdout. It is not a reason to pick a variant; doing so would be selection on the holdout.

## 4. Picks by number of ratios (information only)

Monthly mean active return of the picks against the universe, gross, NW t with 6 lags (kapdates).

| Ratios | Discovery picks, %/yr (t) | Holdout picks, %/yr (t) |
|---|---|---|
| 4 | 3,737, +8.07% (2.23) | 3,903, +7.48% (2.73) |
| 3 | 196, +64.4% (2.25) | 120, −24.8% (−1.17) |
| 1 | 69, −19.5% (−0.73) | 40, −21.0% (−1.10) |

- The edge sits in the four-ratio picks, which are 93–96% of the list.
- Picks ranked on one ratio did worse in both windows, but there are only 40–69 of them, and t is below 1.2. Three-ratio picks flip sign between windows. These groups are too small to support a minimum-ratio rule without a pre-registered test.

## 5. Live list

The `valid_metric_count` column has been written since 2026-10-14. On the 2026-10-16 run, for the 81 of 88 holdings from the 2026-10-11 rebalance that have scores:

| | 4 ratios | 3 ratios | E/P missing | B/M missing | S/P, EBIT/EV missing |
|---|---|---|---|---|---|
| Holdings | 87.7% | 12.3% | 11.1% | 1.2% | 0% |
| value_sn universe | 86.5% | 13.5% | 12.5% | 1.0% | 0% |
| Panel picks (2021+) | 96.1% | 3.0% | 1.0% | 1.0% | 3.0%, 1.0% |

**Finding: live E/P is missing far more often than in the panel.** 52 live stocks lack E/P. In every case checked, P/E from the data provider is empty and EPS is positive. `core/ranking.py::earnings_yield` falls back to EPS / price only when EPS is negative. The panel computes E/P = net income / market cap for every stock. This is a live-versus-tested gap, fixed separately.

Holdings ranked on three ratios on 2026-10-16: AFYON, BERA, BEYAZ, DERHL, EKGYO, EUREN, ODAS, PGSUS, SNGYO, TKNSA.

## Conclusion

- In the tested panel, the score rarely rests on fewer than four ratios, and missing data is not concentrated in the picks.
- No minimum-ratio rule is proposed. The small groups do not support one.
- The live list should match the panel's coverage once the E/P fallback is fixed. Re-run this script after the next rebalance to check.
