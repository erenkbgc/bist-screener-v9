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
