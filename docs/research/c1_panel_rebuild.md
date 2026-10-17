# Research panel rebuilt with C1 (2026-10-17)

`ias29_constant_unit_ttm_preregistration.md` adopted C1: under IAS 29, YTD flows are put into one purchasing-power unit before quarters and TTM are formed. The live score uses C1 (PR #77). This note brings the **stored** research panels to the same definition and re-runs the studies behind the live rule, so that historical figures are not shown for a different definition than the one live.

Run:
```
python scripts/rebuild_panels_c1.py   # no network; raw cache + macro_monthly CPI
python scripts/research_long_term.py
python scripts/research_portfolio_backtest.py
python scripts/research_total_return_benchmarks.py
python scripts/research_survivorship.py
python scripts/research_ias29_regime.py
```

## What changed in the files

`rebuild_panels_c1.py` keeps each file's meaning:
- `factors_monthly.parquet`: lag75;
- `factors_monthly_kapdates.parquet`: actual KAP dates;
- `quarterly.parquet`: 75/100-day `available_at`;
- `quarterly_ext.parquet`: all stocks.

It refuses to write if any row built on pre-IAS 29 statements changes. Result:
- 0 mismatches over 12 columns, including every factor and both forward returns;
- the same row counts (58,223 lag75; 58,308 kapdates);
- E/P changed in 12,344 (lag75) and 12,119 (kapdates) IAS 29 rows.

The C0 files are kept in `data/research/c0/`. `PANEL_DEFINITION.txt` records the definition.

## Results, C0 → C1

Discovery (2013–2020) is identical in every study, as it must be. Changes are in the holdout only (net active %/yr, NW t):

| Study | Measure | C0 | C1 |
|---|---|---|---|
| `long_term` (lag75 base) | value_sn top quintile, holdout | +6.96 (2.60) | **+7.36 (2.80)** |
| | same, USD | +6.82 | +7.21 |
| | Phase 2 hypotheses H1–H5 | all FAIL | all FAIL (unchanged) |
| `portfolio_backtest` (P0, 1M, base) | vs EW universe, holdout | +5.83 (2.11) | **+6.11 (2.29)** |
| | vs XU100 price, holdout | +0.75 (0.13) | +1.04 (0.17) |
| | stress costs ×2, holdout t | 1.56 | 1.71 |
| | real TL CAGR, holdout | −0.96% | −0.67% |
| | D1–D4 decisions | SURVIVES / 100M / F1, F2 FAIL / not sensitive | unchanged |
| `total_return_benchmarks` | B2 costed EW universe | +6.60 (2.37) BEATS | **+6.89 (2.55) BEATS** |
| | B3 BIST 100 total return | −2.00 (−0.33) BEHIND | **−1.71 (−0.28) BEHIND** |
| | B4 BIST All Shares total return | −2.40 (−0.50) BEHIND | −2.11 (−0.44) BEHIND |
| `survivorship` kapdates | baseline holdout | +5.14 (1.99) | +5.65 (2.32) |
| | S1 holdout | +5.06 (1.94) | **+5.56 (2.26)** |
| | **verdict** | **SURVIVORSHIP_FRAGILE** | **SURVIVES_ROBUST_TO_WORST_CASE** |
| `survivorship` lag75 | S1 holdout; verdict | +6.94 (2.57); ROBUST | +7.34 (2.76); ROBUST |
| `ias29_regime` kapdates | ADJ net active | +2.98 (0.70) | +4.14 (1.06) |
| | ADJ − NOM | −2.51 (−0.49) | −1.35 (−0.28) |
| | verdict; ADJ IC; ADJ S/P IC | CONSISTENT; 0.034; −0.019 | CONSISTENT; 0.034; −0.019 |

## How to read the survivorship change

- The **pre-registered** survivorship result was run on C0 before C1 existed. It stays on record: SURVIVORSHIP_FRAGILE.
- The same rule on the adopted C1 panel gives SURVIVES_ROBUST_TO_WORST_CASE.
- The difference is a holdout t moving from 1.94 to 2.26 around a threshold of 2.0. It comes from 2024–2026 rows only. **The value edge is close to the threshold under either definition.** The verdict should not be read as a new, independent confirmation.
- C1 was adopted on accounting grounds (non-inferiority) before this effect was seen. Even so, this is the same holdout seen many times. The forward record remains the decisive test.

## Not re-run

Older studies whose conclusions do not depend on the value composite's IAS 29 months (short-term signals, events, KAP signals, macro, FX, football, spillovers, foreign ownership) were not re-run. Their recorded figures are C0. The exit-rule and entry-timing studies use the same panel and were not re-run either; their decisions (no rule passed) rest mostly on discovery, which C1 does not change.
