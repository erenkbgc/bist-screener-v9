# IAS 29 (inflation accounting) regime: pre-registration

Written and committed on 2026-10-17, **before** any return, IC or ratio statistic was split by regime. The regime definition, metrics, windows and labels are fixed here. They are not changed after the results are seen.

## Question

From periods ending on or after 2023-12-31, Turkish listed companies report under IAS 29 (TMS 29), the inflation-accounting standard announced by KGK. Restated balance sheets (equity at current purchasing power) and income statements (monetary gain or loss, restated flows) change what E/P, B/M, S/P and EBIT/EV measure. The value evidence behind the live score comes mostly from nominal statements (2013–2023).

**Does value_sn still rank stocks once the statements are inflation-adjusted?**

## What was looked at before this file was written

- Only the statement period (`stmt_period`) used in each panel month, per stock (kapdates panel, 2022-06 to 2026-09). No return, IC or ratio level.
- Share of universe rows by period type (definitions below):
  - nominal rows ≥ 95% up to 2024-02;
  - mixed 2024-03 and 2024-04;
  - transition rows ≥ 97% from 2024-05 to 2025-01;
  - 2025-02 mixed;
  - IAS 29 rows ≥ 97% from 2025-03 on.
- Results from earlier studies over the whole 2021+ holdout are known (value_sn holdout +5.14%/yr, t 1.99 on the kapdates panel). Their split by regime is not.

## Data

- Primary: the kapdates panel (`factors_monthly_kapdates.parquet`), prepared exactly as in `research_survivorship.py` (`prepare` with the bottom-30% liquidity cut, `add_composites`, `add_usd_returns`). It uses actual KAP dates, so the regime switch lands in the right month.
- Secondary: the lag75 panel (`factors_monthly.parquet`), same steps.
- Statement values are the provider's current version (restated comparatives, if any, are not the originally published numbers). This limit is shared with every panel study.

## Regime definition (fixed)

Each panel row is classified by the statement period it uses:
- **N (nominal):** `stmt_period` ≤ 2023Q3.
- **T (transition):** 2023Q4 to 2024Q3. The balance sheet is IAS 29. TTM flows mix nominal and adjusted quarters.
- **I (IAS 29):** ≥ 2024Q4. Balance sheet and all four TTM quarters are IAS 29.

A decision month gets a regime when at least 80% of its universe rows share it. Other months are **mixed** and are left out of the regime comparison.

Comparison windows:
- **NOM:** N months from 2021-01. This is the same high-inflation holdout era, with nominal statements.
- **ADJ (primary):** T and I months together. These are all months with restated balance sheets (about 2024-05 to the end of the data).
- **I-only (secondary):** I months only (about 2025-03 on). It is short, so it is information only.
- Discovery 2013–2020 (all N) is reported as reference.

## Metrics

For each window:
- **value_sn_z rank IC** with `fwd_ret_1m`: mean, NW t with 6 lags.
- **Top-quintile net active return** (`long_term_research.portfolio` and `summarize`, as in all earlier value tests): per year, NW t.
- **Per-ratio rank IC** of `bm_z`, `ep_z`, `sp_z`, `ey_z`. Information only.
- **Difference ADJ − NOM** in monthly top-quintile net active return, t = (mean_ADJ − mean_NOM) / √(se_ADJ² + se_NOM²), with NW standard errors (6 lags).

## Labels (fixed, primary = kapdates, ADJ vs NOM)

1. **REGIME_BREAK:** ADJ IC mean ≤ 0, **or** the ADJ − NOM difference has t < −2.
2. **CONSISTENT:** not 1, ADJ IC t > 2, and ADJ net active > 0.
3. **WEAKER_NOT_SIGNIFICANT:** neither of the above.

## What the labels change

- **CONSISTENT:** no change. The README notes that value ranking holds under IAS 29.
- **WEAKER_NOT_SIGNIFICANT:** the README value evidence gets the label "weaker under IAS 29, not significant". The forward record decides.
- **REGIME_BREAK:** the README carries a warning on the value evidence. A follow-up pre-registration on ratio or sector adjustments (for example dropping a ratio that flips sign) is written before any change is tested.
- **No label changes the live rule by itself.** Per-ratio results are not used to drop or reweight a ratio in this test; doing so would be selection on the data seen here.

## Known limits

- ADJ has about 28 decision months, I-only about 18. Only a large break can reach t < −2. A null result is weak evidence of no change.
- The ADJ period also has other changes: the 2023–2024 policy turn, foreign inflows and a market fall in 2025. These are not separated from the accounting change.
- Within-year IAS 29 YTD figures are restated to each quarter's purchasing power, so quarterly differences mix units. The live score uses the same numbers, so the test measures what the live rule sees.

## Results (added 2026-10-17, after the run; the sections above are unchanged)

Run: `python scripts/research_ias29_regime.py`. Output: `data/reports/research_ias29_regime_2026-10-17.json`.

Implementation detail: the top-quintile portfolio is built once over the whole panel. Months are then selected by regime, so the first month of each window does not pay a full-turnover cost.

Month regimes (kapdates): 131 N, 10 T, 19 I, 2 mixed (2024-03, 2024-04).

**kapdates (primary)**, rank IC mean (NW t); top-quintile net active %/yr (NW t):

| Window | Months | Net active | value_sn IC | B/M IC | E/P IC | S/P IC | EBIT/EV IC |
|---|---|---|---|---|---|---|---|
| Discovery 2013–2020 | 93 | +9.26 (2.75) | +0.040 (5.46) | +0.019 (1.79) | +0.034 (2.52) | +0.026 (2.66) | +0.053 (5.09) |
| NOM 2021-01 → 2024-02 | 38 | +5.49 (1.86) | +0.077 (4.55) | +0.049 (4.77) | +0.069 (4.64) | +0.060 (5.32) | +0.064 (4.23) |
| **ADJ 2024-05 → 2026-09** | 28 | **+2.98 (0.70)** | **+0.034 (2.18)** | +0.020 (1.01) | +0.053 (3.86) | **−0.019 (−1.29)** | +0.041 (3.07) |
| I-only 2025-03 → | 18 | +7.46 (1.14) | +0.045 (2.23) | +0.017 (0.60) | +0.066 (3.90) | −0.013 (−0.63) | +0.044 (2.18) |
| T-only | 10 | −5.08 (−0.83) | +0.014 (1.13) | +0.025 (1.04) | +0.031 (3.40) | −0.030 (−3.07) | +0.037 (5.92) |

- ADJ − NOM net active: −2.51%/yr (t −0.49). I-only − NOM: +1.97%/yr (t 0.27).
- lag75 gives the same picture. ADJ: +5.34%/yr (t 1.18), IC +0.043 (t 2.54), S/P IC −0.015. ADJ − NOM: −2.92%/yr (t −0.57).

**Verdict by the rule: CONSISTENT.**
- ADJ IC is positive with t 2.18 > 2.
- ADJ net active is positive.
- ADJ − NOM is not significant (t −0.49).

### Reading

- Value still ranks stocks under IAS 29. The IC is about half of the 2021–2024 nominal level (0.034 vs 0.077), but close to the 2013–2020 level (0.040).
- The top quintile's net active return in ADJ is positive but not significant (t 0.70) over only 28 months. The rule could not detect a modest decline. "Consistent" here means "no break detected", not "unchanged".
- **Exploratory, not part of the rule:** S/P is the only ratio whose IC turns negative after the switch, in both panels and in both T and I. E/P and EBIT/EV keep their sign and significance. B/M weakens. The restatement of sales under IAS 29 may make S/P a measure of something else. By the rule this is **not** acted on here. It is a candidate hypothesis for a separate pre-registration, which would need data the present test has not seen (for example the forward record from 2026-11).

### Decision (as fixed above)

- CONSISTENT: no change to the live rule. The README notes that value ranking holds under IAS 29, at a lower IC, and records the S/P observation as an open question.
