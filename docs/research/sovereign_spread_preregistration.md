# Turkey sovereign spread and BIST: pre-registration

Written and committed on 2026-10-13, **before** the spread was joined to any return. The spread definition, tests and pass rules are fixed here.

## Question

The macro study (`macro_drivers_preregistration.md`) explained about a third of BIST's monthly USD variance, almost all of it through EM equities (EEM). It named Turkey's credit risk as the obvious candidate for the unexplained, Turkey-specific part. Turkey CDS is not available here: EVDS has no CDS series, and there is no free CDS history. The closest free measure is the **sovereign spread**, the yield on Turkey's USD Eurobonds minus the US Treasury yield of the same remaining maturity.

1. **C1, explanation.** Does the monthly spread change explain BIST's USD return in the same month, beyond EEM? Expected: a wider spread goes with a lower BIST.
2. **C2, prediction.** Does the spread level at month-end predict BIST's USD return over the next month (C2a) or the next 12 months (C2b)? Expected: a high spread goes with higher future returns, the risk premium paid for bearing country risk.

## Data

- **Eurobonds:** month-end bid yields of all Turkey USD Eurobonds from borsapy's Ziraat archive (`scripts/fetch_eurobond_monthly.py`). On a non-trading month-end, the last business day with data is used.
- **US Treasury:** yfinance `^FVX` (5y), `^TNX` (10y) and `^TYX` (30y) on the same date.
- **BIST and EEM:** monthly r_usd and EEM returns from `research_macro_drivers` (`load()`, `build()`).

## Spread definition

For each month-end and each USD bond with 3 to 30 years to maturity:
- bond spread = yield − UST yield interpolated linearly in maturity between 5, 10 and 30 years (flat outside).

**sp_t** = the median bond spread that month, in percentage points. This is a robust level for Turkey's USD credit risk at a roughly 10–20-year tenor.

## Tests

| ID | Regression (monthly, Newey-West) | Expected |
|---|---|---|
| C1 | r_usd,t = a + b · Δsp_t + c · r_eem,t | b < 0 |
| C2a | r_usd,t+1 = a + b · sp_t | b > 0 |
| C2b | Σ r_usd,t+1..t+12 = a + b · sp_t (12 lags) | b > 0 |

**Pass rules:**
- **C1,** as in macro part A: NW t of b below −3.0 over the full sample, and b < 0 in both halves of the sample.
  - Also reported: the increase in R² over EEM alone.
- **C2a and C2b,** as in macro part B, all three needed:
  - in-sample NW t > 3.0;
  - out-of-sample R² > 0 against the historical mean (expanding window, 84 months of training, `oos_test`);
  - Clark-West p < 0.05 / 3.

## What goes live

- **C1 passes:** the README's "what moves BIST" section names the sovereign spread as the Turkey-specific driver. The bulletin may show the current spread and its monthly change as information.
- **C2a or C2b passes:** a market-level note ("ülke riski primi yüksek/düşük") with its measured effect. No change to stock selection.
- **Nothing passes:** nothing is shown.

## Known limits

- **Not CDS:** the spread includes bond liquidity and the USD term premium. It moves closely with CDS but is not the same.
- **Changing basket:** the bond basket changes as bonds are issued and mature. The median spread limits the effect, but the tenor drifts.
- **Unknown archive start:** the Ziraat archive's start date was checked back to 2012-12. The usable sample starts where month-end data begins.

---

## Results (added 2026-10-13, after the run; the sections above are unchanged)

**Data:**
- `python scripts/fetch_eurobond_monthly.py`: 2,673 bond-month yields over 198 month-ends, 2010-04 to 2026-09.
- `python scripts/research_sovereign_spread.py`. JSON: `data/reports/research_sovereign_spread_2026-10-13.json`.
- The median spread averaged 3.82 pp (range 1.72 to 8.03). It was 2.66 pp at 2026-09.

**C1, same month: PASS.**

| | Value |
|---|---|
| Months | 197 |
| b on Δsp (per 1 pp) | −0.124, NW t −8.24 |
| b in each half | −0.122 / −0.126 |
| R², EEM only | 0.215 |
| R², EEM + Δsp | 0.490 |

A 100 bp widening of Turkey's USD spread goes with about a 12% lower BIST in USD in the same month, beyond what EM equities explain. Adding the spread **more than doubles** the explained share of monthly variance, from 22% to 49%. The coefficient is the same in both halves.

**C2, prediction: FAIL.**

| Test | In-sample b (t) | OOS R² | Clark-West p | Result |
|---|---|---|---|---|
| C2a next month | +0.011 (2.17) | −3.2% | 0.48 | FAIL |
| C2b next 12 months | +0.098 (3.70) | −31.4% | 0.018 | FAIL |

**Decisions, as pre-registered:**
- The README names the sovereign spread as the Turkey-specific driver of BIST.
- The bulletin may show the current spread and its monthly change as information. This is not implemented yet: it needs a daily Ziraat Eurobond request in the live run.
- No timing note: C2 failed.

How to read it:
- This answers the macro study's open question: the Turkey-specific half of BIST's monthly move is largely country credit risk.
- It is **explanation, not prediction**. The spread moves together with BIST in the same month. A high spread at month-end did not reliably predict a better next month or year out of sample. The 12-month in-sample fit (t 3.70) did not survive out of sample (R² −31%), the same pattern as the macro study's near misses.
- For an investor, the spread is a risk gauge: when it widens, BIST in USD falls. It does not give a timing signal.
