# Actual KAP publication dates in the research panel: pre-registration

Written and committed on 2026-10-12, **before** the panel was rebuilt with actual dates or any factor result was computed with them. The mapping, variants, metrics and decision rules are fixed here.

## Question

`core/pit_panel.py` assumes that a quarterly statement becomes public 75 days after an interim period end and 100 days after a year end. An external review (2026-10-12) pointed out that this is an assumption, not the real publication date. Two things can go wrong:
- **Look-ahead:** a statement published later than assumed is used before it was public.
- **Staleness:** a statement published earlier than assumed is used later than necessary. This only weakens the signal and does not bias it upward.

Is the value_sn result robust to using the actual dates?

## Data

`data/research/kap_archive.parquet` contains every KAP disclosure from 2010-01 to 2026-10, with its `published_at` timestamp. Financial reports are `disclosureClass == "FR"` with subject "Finansal Rapor" or "Finansal Rapor Bildirimi". The period type is in `ruleType`: 3 Aylık = Q1, 6 Aylık = Q2, 9 Aylık = Q3, Yıllık = Q4.

## Mapping

- **Period:** the most recent quarter end of that type strictly before `published_at`. A filing more than 400 days after that quarter end is dropped as unmatched.
- **Publication:** the earliest matching filing for (ticker, period). Later re-filings and corrections are ignored. The statement values themselves are the provider's latest version. Earlier versions are not available, and this limit is reported.
- **Available at:** the publication date if `published_at` is before 18:00 Istanbul time (the session close). Otherwise, the next calendar day. A month-end decision at t uses a statement only if available_at ≤ t.

## Variants

| ID | available_at |
|---|---|
| A (current) | period end + 75 / 100 days |
| B (main) | the actual KAP date where matched; A where not matched |
| C (strict) | the actual KAP date only; statements without a match are dropped |

Everything else is unchanged:
- the same quarterly table, prices and share events from the cache;
- the same `build_monthly_factors`;
- the same universe (bottom 30% by liquidity dropped);
- the same value_sn.

## Metrics

**Descriptive:**
- the share of (ticker, period) rows with a matched KAP date;
- the distribution of the actual lag in days, by quarter type;
- the share of rows where the actual date was **later** than the assumed date (look-ahead in A), and by how many days.

**value_sn under A, B and C,** in discovery (to 2020-12) and holdout (2021-01 onward):
- top-quintile net active return against the EW universe at 20 bps (`spread_stats` in `backtest_factor_model.py`), with its Newey-West t;
- rank IC at one month, with its t.

## Decision rules

1. **The panel switches to B** as the default, whatever the result. B is strictly more accurate than A. All later research uses B. Past results stay as recorded; they are not re-labelled.
2. **Robust:** value_sn under B has top-quintile net active > 0 with t > 2.0 in both periods. The README states that the value result survives actual publication dates.
3. **Lag-sensitive:** if rule 2 fails, the README and the bulletin's realised-return note state that the value result depended on the assumed publication lag. The live rule stays as it is until a new pre-registration decides otherwise.
4. **C is a sensitivity check only.** If C changes the sign of the holdout net active, this is reported.

## Known limits

- **Restatements:** statement values are the provider's final versions. A restated figure may differ from what was first published.
- **Matching by period type and date:** a company that files very late (more than 400 days) is unmatched and falls back to A in variant B.
- **Consolidated and solo filings** are not told apart. The first filing of either kind counts.
