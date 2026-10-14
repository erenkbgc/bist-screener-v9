# Foreign ownership change: pre-registration

Written and committed on 2026-10-15, **before** the foreign-ownership history was downloaded and before any test below was run. The hypotheses, definitions, metric and pass rule are fixed here and do not change after the results are seen.

## Question

Do stocks whose foreign ownership share rose over the last three months earn higher returns next month? Does this signal improve the live value rule?

Literature:
- Foreign and institutional investors are often better informed or faster to act (Grinblatt-Keloharju 2000; Froot-O'Connell-Seasholes 2001).
- Their buying can therefore lead prices.
- The opposite view is that foreign flows are momentum-like and herd, and then reverse.

The confirmatory prediction is the informed-investor direction: **positive**.

## Prior exposure, stated honestly

- No per-stock foreign-ownership history has been examined in this project before. borsapy has none (`dividend_yield_preregistration.md`).
- Live collection began 2026-09-11. Those five weeks were only checked for coverage, never against returns.
- 12-1 momentum does not rank BIST stocks (t 0.71), and value + momentum composites failed (H3a, #62 E1). This is relevant if foreign flows mostly follow past returns.

## Data

- **Source:** İş Yatırım `GetYabanciOranlarXHR`, the endpoint behind the company card page.
  - The share of the stock held by foreign investors, from MKK settlement records.
  - Per stock and per date, available from about 2013-06.
- **Fetch:** `scripts/fetch_foreign_ownership.py`. One call per consecutive month-end pair. Each month-end is the last trading day of the month; when the call returns empty, the previous weekday is tried, up to 5 days back.
- **Cache:** `data/research/foreign_monthly.parquet`.
- **Timing:** settlement data lags trades by two business days (T+2). The value at month-end t therefore reflects trades up to t−2, and no future information enters.
- **Survivorship:** only currently listed stocks are returned. This is the same limit as the panel.
- **Universe:** the Phase 2 panel (`research_long_term.load()`), non-financial companies with the least liquid 30% dropped each month. Foreign data is merged on ticker and calendar month-end.

## Signals

- `for_t`: foreign share (%) at month-end t.
- `dfor3`: for_t − for_{t−3 months}, in percentage points. It is missing if either value is missing.
- `dfor3_z`: the panel's cross-sectional 1/99 winsorized z-score of `dfor3` (`factor_backtest.winsorize_z`), computed on the same monthly universe.

## Hypotheses

| ID | Test | Prediction |
|---|---|---|
| F1 | Top quintile of `dfor3` versus the universe (standalone signal) | positive net active return |
| F2 | Rank on 0.5·value_sn_z + 0.5·dfor3_z versus plain value_sn (as H4a/H5; a missing `dfor3_z` counts as 0) | D > 0 |
| F3 (exploratory) | Top quintile of the foreign share level `for_t` versus the universe | reported, cannot pass |

The weights in F2 are fixed at 50/50 and are not searched.

## Metric

Same as Phase 2 (`core/long_term_research.portfolio`):
- top quintile, monthly, equal weight;
- net active return = top − equal-weighted universe mean − 2 × turnover × 20 bps;
- Newey-West t with 6 lags.

What is compared:
- F1 and F3: the portfolio's net active return itself.
- F2: D_t = active(F2) − active(value_sn).

Periods:
- Discovery: before 2021-01, starting from the first month with `dfor3`, which is about 2013-09.
- Holdout: 2021-01 onward.

Also reported:
- USD active return;
- turnover;
- coverage (the share of panel rows with `dfor3`);
- the monthly rank IC of `dfor3` with the 1-month forward return;
- the correlation of `dfor3` with `mom_12_1` and with 3-month past return. This shows whether the signal is momentum in disguise.

## Pass rule (all must hold, for F1 and for F2)

1. Discovery: positive, and t > 3.0 (Harvey-Liu-Zhu).
2. Holdout: positive, and t > 2.0.
3. Holdout USD:
   - F1: net active return > 0.
   - F2: net active return ≥ that of value_sn.

Fallback: positive in both periods with t > 2 in each is labelled "supported, not confirmed". It may be shown as information. It does not change scoring.

## What goes live

- **F2 passes:**
  - The live score becomes 0.5·valuation_z + 0.5·dfor3_z.
  - `dfor3` is computed from the same endpoint (current value minus the value three months earlier).
  - A parity test is added.
- **Only F1 passes:**
  - `dfor3` is shown in the bulletin as information.
  - The ranking does not change: the live rule is a value rule, and F1 alone does not show that the signal adds to value.
- **Neither passes:** nothing changes. Live collection of `foreign_pct` continues.

## Known limits

- **Survivorship:** delisted stocks are missing.
- **Data source:** this is an undocumented website endpoint. It can change, and its values cannot be checked against MKK for free. Live `foreign_pct` (same source via borsapy) matched within about 0.4 pp on 2026-10-13.
- **Discovery length:** discovery starts in 2013-09, so it has about 88 months.
- **Same-close trading:** signal and trade use the same month-end close (panel convention).

---

## Results (added 2026-10-15, after the run; the sections above are unchanged)

`python scripts/fetch_foreign_ownership.py` downloaded 160 consecutive months (2013-06 .. 2026-09), 83,564 rows and 347–785 stocks per month. Eight month-ends fell on holidays, and the previous trading day was used for them. `python scripts/research_foreign_ownership.py` ran the tests from 2013-09 (first month with `dfor3`) to 2026-09: 88 discovery months and 68 holdout months. `dfor3` covers 93.9% of panel rows.

Diagnostics:
- **Rank IC of `dfor3`:** −0.016 in discovery (t −1.51); 0.000 in holdout (t 0.01).
- **Spearman correlation of `dfor3`:** 0.056 with 12-1 momentum, 0.255 with 3-month past return. Foreign buying partly follows recent price rises.
- **value_sn over the same months:** +11.82%/yr (t 2.98) in discovery, +6.96%/yr (t 2.60) in holdout.

| Test | Discovery | Holdout | Holdout USD | Result |
|---|---|---|---|---|
| F1 top `dfor3` quintile vs universe | −3.07%/yr (t −0.93) | +5.46%/yr (t 2.38) | +5.30% | **FAIL** |
| F2 0.5 value + 0.5 `dfor3` vs value_sn (D) | −5.93%/yr (t −1.47) | −1.90%/yr (t −0.55) | — | **FAIL** |
| F3 top foreign-level quintile (exploratory) | −13.23%/yr (t −3.40) | +7.83%/yr (t 1.64) | +7.44% | — |

**Both confirmatory tests fail.** Rising foreign ownership does not predict next-month returns, and adding it to value lowers returns in both periods.

Reading (post-hoc, not a result):
- F1 is positive only in 2021+. The sign flips between periods, so it is not a stable signal.
- The foreign-ownership level (F3) also flips sign: strongly negative in 2013–2020, positive in 2021+. High-foreign stocks are the large, liquid names, and how they fare against the rest depends on the period. This is not a stock-selection signal.

As pre-registered, nothing changes in live scoring. Live collection of `foreign_pct` continues.
