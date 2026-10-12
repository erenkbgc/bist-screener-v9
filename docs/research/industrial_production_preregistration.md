# Industrial production and BIST: pre-registration

Written and committed on 2026-10-12, **before** industrial production data was joined to any return. The series, timing, tests and pass rules are fixed here.

## Question

Several Turkish studies, typically variance decompositions and cointegration on index levels, report that industrial production is a leading real-economy driver of BIST. Two questions:

1. **I1, reaction.** Does BIST move in the month an industrial production surprise is published? If not, the "driver" claim has no news content for investors.
2. **I2 and I3, prediction.** Does the latest published industrial production figure predict next month's BIST return, out of sample? This is the only form a monthly investor could use.

## Data

- **Industrial production:** TÜİK industrial production index, total industry, 2021=100, monthly from 2005-01. EVDS series `TP.TSANAY2021.BCD`, via `borsapy.evds_series` (key in `.env`, `EVDS_API_KEY`).
  - The unadjusted index is used with year-on-year growth. Seasonally adjusted series are re-estimated over the whole history at every release, which would leak future information.
  - EVDS gives only the latest vintage. Revisions to unadjusted data are usually small, and this limit is reported.
- **BIST:** monthly XU100 in USD, r_usd = Δln(XU100 / USDTRY), from `macro_drivers` (`research_macro_drivers.load()`), 2005 onward.

## Timing

- TÜİK publishes month m's index around the 10th of month m + 2. Month m's figure is treated as known at the end of month m + 2, and as **news in month m + 2**.
- g_m = ln(IPI_m / IPI_{m−12}), year-on-year growth.
- surprise_m = g_m − mean(g_{m−12} … g_{m−1}), the deviation from the previous 12 months' average growth. A crude proxy for the unexpected part, because no consensus forecasts are available.

## Tests

| ID | Regression (monthly) | Expected | Type |
|---|---|---|---|
| I1 | r_usd(month m + 2) = a + b · surprise_m | b > 0 | reaction |
| I2 | r_usd(month m + 3) = a + b · surprise_m | b > 0 | prediction |
| I3 | r_usd(month m + 3) = a + b · g_m | b > 0 | prediction |

**Pass rules:**
- **I1:** b > 0 with Newey-West t > 3.0 in discovery (release months before 2016-01) and t > 2.0 in holdout (2016-01 onward).
- **I2 and I3,** as in `macro_drivers_preregistration.md` part B, all three needed:
  - in-sample NW t > 3.0 with the expected sign;
  - out-of-sample R² > 0 against the historical mean (expanding window, first 84 months for training, `oos_test`);
  - Clark-West p < 0.05 / 3.

## What goes live

- **I2 or I3 passes:** the bulletin may show a "sanayi üretimi sinyali" note with its measured effect. No change to the stock-selection rule: this is a market-level signal.
- **Only I1 passes:** this is documented as information. A market that reacts at publication has nothing left to trade a month later.
- **Nothing passes:** nothing is shown.

## Known limits

- **Surprise proxy:** the surprise is not a consensus surprise and is noisier than one.
- **Vintage:** the latest vintage is used, not the first-release figure.
- **Release dates:** an approximate rule (m + 2) is used, not the exact release dates.

---

## Results (added 2026-10-13, after the run; the sections above are unchanged)

`python scripts/research_industrial_production.py`. EVDS `TP.TSANAY2021.BCD`, 2005-01 to 2026-08; mean year-on-year growth 4.8%. JSON: `data/reports/research_industrial_production_2026-10-13.json`.

| Test | Result detail | Verdict |
|---|---|---|
| I1 reaction in the release month | discovery b −0.011 (t −0.08, 118 months); holdout b +0.043 (t 0.57, 129 months) | FAIL |
| I2 surprise → next month | in-sample b −0.023 (t −0.30); OOS R² −0.6%, Clark-West p 0.94 | FAIL |
| I3 growth level → next month | in-sample b −0.050 (t −0.66); OOS R² −0.8%, Clark-West p 0.69 | FAIL |

The correlation of yoy growth with the release-month USD return is −0.02.

**Nothing passes**, so nothing is shown.

How to read it:
- BIST does not react to the monthly industrial production figure in the month it is published, and the figure does not predict the next month.
- The literature's "industrial production is the strongest real driver" comes from level relationships and variance decompositions, not from news or prediction. On a monthly, out-of-sample basis, with publication lags respected, there is nothing to use.
