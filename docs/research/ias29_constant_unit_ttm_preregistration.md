# IAS 29: TTM flows in a common purchasing-power unit: pre-registration

Written and committed on 2026-10-17, **before** the new definition was coded or run. The definition, metrics and decision rule are fixed here. They are not changed after the results are seen.

## Problem

`pit_panel.quarterly_table` turns year-to-date (YTD) income items into quarters by subtraction, then sums four quarters into TTM:

- quarter_k = YTD_k − YTD_{k−1};
- TTM = sum of the last four quarters.

Under IAS 29 (periods ending on or after 2023-12-31), each report states its YTD figures in the purchasing power at **that report's** period end. YTD_k and YTD_{k−1} are therefore in different units, and the four quarters in a TTM sum are in four different units. With 2–4% monthly inflation, one quarter's unit gap is about 6–12%. This distorts TTM sales, operating profit and net income, and through them S/P, E/P and EBIT/EV. The IAS 29 regime test (`ias29_regime_preregistration.md`) found the S/P rank IC turning negative after the switch. That was an exploratory observation.

## What has been seen, stated honestly

- The IAS 29 regime results under the **current** definition (C0) are known: ADJ value_sn IC +0.034 (t 2.18), net active +2.98%/yr (t 0.70), S/P IC −0.019.
- So the ADJ window is not unseen data for this question. A rule like "adopt the new definition if it improves ADJ" would select on seen data. The decision rule below avoids that. The new definition is adopted on accounting grounds, **unless** it is clearly worse. Improvement is reported but is not the criterion.

## New definition C1 (fixed)

CPI: the TÜİK monthly CPI index (`bp.Inflation().tufe()`, monthly change chained into an index; `macro_monthly.parquet` `cpi_mom` for research). CPI(p) is the index value in the month of period end p.

For rows with `period` ≥ 2023Q4 (restated reports):
- **Discrete quarter**, restating the previous YTD into the current report's unit:
  - Q1: quarter_k = YTD_k.
  - Q2–Q4: quarter_k = YTD_k − YTD_{k−1} × CPI(end_k) / CPI(end_{k−1}).
  - The previous quarter must exist, as in C0.
- **TTM in the unit of the row's own period end:** TTM_i = Σ_{j = i−3..i} quarter_j × CPI(end_i) / CPI(end_j). The four-consecutive-quarters rule of C0 still applies.
- Quarters before 2023Q4 inside such a sum (nominal reports) are restated the same way. Their quarters are computed as in C0.

For rows with `period` ≤ 2023Q3: C1 = C0, by construction.

Balance-sheet items (equity, financial debt, cash) are not changed. They are already in the unit of their own period end, and all stocks in a month mostly share that period end.

The same change applies to every flow item (`revenue`, `gross_profit`, `op_profit`, `ni_parent`, `net_income`, `ebit`, `fin_expense`). The value ratios use sales, operating profit and net income.

## Test

- Panels: kapdates (primary) and lag75. Both are rebuilt from the raw cache with C0 and with C1, using otherwise identical code.
- Windows as in `ias29_regime_preregistration.md`: discovery, NOM (2021+ nominal months), ADJ (T + I months), I-only.
- Metrics per window and definition:
  - value_sn rank IC (NW t, 6 lags);
  - top-quintile net active return (NW t);
  - per-ratio rank IC of E/P, S/P and EBIT/EV.
- **Paired difference C1 − C0 over the same ADJ months:** monthly value_sn IC and monthly top-quintile net active, NW t with 6 lags.

## Decision rule (fixed)

1. **Check:** in discovery and NOM, C1 must equal C0 row for row (the definition only touches rows from 2023Q4). If not, the run is invalid and the code is fixed, not the rule.
2. **ADOPT C1** unless it is clearly worse in ADJ (kapdates). Clearly worse means:
   - the paired monthly value_sn IC difference C1 − C0 has a mean below −0.01 **and** NW t < −2; **or**
   - the paired net active difference has NW t < −2.
3. Otherwise **KEEP C0**, and the README records that the correction made the score worse.

If adopted, a separate PR moves both the research panel and the live value inputs (`live_value_inputs`) to C1, with a parity test. The rule version `R0-2026-10-12` keeps its parameters. The definition change is noted in the forward record by the code SHA and in the README with its date.

The S/P sign question is reported (S/P IC under C1 in ADJ), but no ratio is dropped or reweighted on it. That would need its own pre-registration on unseen data.

## Known limits

- The CPI restatement uses the month of period end. Companies restate with the same TÜİK index, but their exact method (and any sector-specific indices) may differ.
- 2023Q4 is a first-application report. How the provider shows the 2023 Q1–Q3 YTD figures (nominal as published, or restated) is not known. C1 treats them as nominal.
- The ADJ window is short (about 28 months) and has been seen. This test can only catch a clear deterioration.

## Results (added 2026-10-17, after the run; the sections above are unchanged)

Run: `python scripts/research_ias29_constant_unit.py`. Output: `data/reports/research_ias29_constant_unit_2026-10-17.json`.

**Check (rule 1): valid.** Rows using statements before 2023Q4 are identical under C0 and C1:
- kapdates: 43,610 rows, 0 mismatches in E/P, S/P, EBIT/EV, B/M and `fwd_ret_1m`;
- lag75: 43,427 rows, 0 mismatches.

Of the IAS 29 rows, about 12,100 (kapdates) change E/P and EBIT/EV, and about 11,900 change S/P. Q4 rows do not change: their TTM is the annual YTD figure, already in one unit. The NOM window has a few rows (about 5% in 2024-02) already on 2023Q4 statements. That explains the 5.32 → 5.33 change in the NOM S/P t.

**ADJ window, C0 → C1**:

| Panel | Net active %/yr (t) | value_sn IC (t) | E/P IC | S/P IC | EBIT/EV IC |
|---|---|---|---|---|---|
| kapdates C0 | +2.98 (0.70) | +0.034 (2.18) | +0.053 | −0.019 | +0.041 |
| kapdates C1 | +4.14 (1.06) | +0.034 (2.21) | +0.054 | −0.019 | +0.042 |
| lag75 C0 | +5.34 (1.18) | +0.043 (2.54) | +0.062 | −0.015 | +0.047 |
| lag75 C1 | +6.29 (1.39) | +0.043 (2.56) | +0.066 | −0.014 | +0.048 |

Paired C1 − C0 over the ADJ months:
- kapdates: IC −0.0001 (t −0.21); net active +1.16%/yr (t 1.43).
- lag75: IC −0.0000 (t −0.08); net active +0.94%/yr (t 2.39).

**Decision by the rule: ADOPT_C1** (kapdates). C1 is not worse on either criterion. The improvement is reported but was not the criterion.

### Reading

- The unit fix leaves the rank IC unchanged. It slightly raises the top quintile's net active return in both panels.
- **The S/P sign flip is not explained by the unit mismatch.** Under C1, S/P IC in ADJ is still −0.019 (kapdates). The cause lies elsewhere: for example sales restatement itself, or sector mix in 2024–2026. Per the pre-registration, no ratio is dropped on this.

### Next step (as fixed above)

A separate PR moves the research panel build and the live value inputs to C1, with a parity test and a dated README note.
