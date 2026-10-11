# KAP red flags: pre-registration

Written and committed on 2026-10-11, **before** any test below was run. The hypotheses, definitions, base portfolio, metrics and pass rule are fixed here. They are not changed after the results are seen. A changed definition counts as a new test and needs a new pre-registration.

## Question

A stock can look cheap after a large fall while the real cause is a deteriorating company: insolvency, auditor doubts, regulatory sanctions, lawsuits, management leaving. This information is in KAP disclosures, not in the statements. Does removing value_sn picks with recent KAP red flags improve the live rule?

## Prior evidence and exposure

- Phase 2 (`long_term_preregistration.md`) tested numeric distress proxies (CHS, Altman EM, dd5y ≤ −70%, F7) as exclusion filters on the same base. None passed. Excluding crashed stocks cost about 1.5%/yr in discovery.
- KAP text has never been tested in this repository. Catalyst weight is 0 in the live score (PR #25).
- **Exposure, stated honestly.** Before this document was written:
  - the classifier (`core/kap_red_flags.py`, PR #32) was tuned on the subject/summary frequency table of the archive and on hand-read samples. No return data was looked at.
  - the number of flagged top-quintile stock-months was counted for the power check below. These are counts of events only, not outcomes.

## Data

- KAP archive: `data/research/kap_archive.parquet` built by `scripts/build_kap_archive.py` (kap.org.tr `disclosure/members/byCriteria`, memberType IGS). 637,454 disclosures, 987 tickers, 2010-01-04 to 2026-10-11. Delisted companies are included. All 514 panel tickers appear in the archive.
- Panel, liquidity filter, value_sn and returns: as in `long_term_preregistration.md` (`scripts/research_long_term.load()`), 2013-04 to 2026-09.
- **Discovery:** 2013-01-01 to 2020-12-31. **Holdout:** 2021-01-01 to the end of the data.

## Definitions

- **Red flag:** a disclosure for which `core/kap_red_flags.classify(subject, summary)` returns a category. The classifier is used exactly as committed in PR #32 (commit 3d38149). A disclosure tagged with several stock codes counts for each of them.
- **Severe red flag:** categories insolvency, going_concern, auditor_adverse, regulatory_sanction, market_sanction. That is, all categories except lawsuit_or_seizure and board_resignation, which are frequent and often routine.
- **Flagged at month-end t:** at least one red flag with publication date in [t − 90 days, t). Disclosures published on day t itself are not used, because many are published after the close.

## Base portfolio

**B = top quintile of `value_sn`**, equal-weighted, monthly rebalance, 20 bps one-way cost on turnover. This is the same B as in `long_term_preregistration.md`, computed by `core/long_term_research.portfolio`.

## Hypotheses

Each hypothesis is an **exclusion filter**: flagged names are removed before the quintile is formed (`portfolio(..., exclude=flag)`), as in Phase 2.

| ID | Filter | Expected sign | Type |
|---|---|---|---|
| K1 | Exclude names with any red flag in the last 90 days | D > 0 | confirmatory |
| K2 | Exclude names with a severe red flag in the last 90 days | D > 0 | confirmatory |
| K3 | Within top-quintile names with dd5y ≤ −70%: next 6-month return vs XU100 of flagged minus unflagged names | negative | exploratory |

**Power.** Flagged stock-months inside the B top quintile (counts only):

| Filter | Discovery | Holdout |
|---|---|---|
| Any flag (K1) | 388 (9.7%) | 320 (7.9%) |
| Severe flag (K2) | 81 (2.0%) | 63 (1.6%) |
| Any flag and dd5y ≤ −70% (K3) | 15 | 9 |

The minimum for a confirmatory test is 60 flagged stock-months per period. K1 and K2 meet it. K3 does not, so it is exploratory: it is reported descriptively and cannot pass.

## Metrics

- **Primary:** monthly D = net active(filter) − net active(B), annualised. The t-statistic is Newey-West with 6 lags (`long_term_research.diff_stats`).
- Also reported, per period: active return of the filtered portfolio in TL and USD, trap rate (share of names with 6-month excess return < −30%), turnover, average number of names.
- **Descriptive only, no decision:** monthly cross-sectional Spearman correlation of value_sn with the any-flag indicator, CHS, F7 and dd5y, averaged over months. Question: are cheap stocks systematically the distressed ones?
- **Sensitivity, no decision:** K1 and K2 with a 180-day window, which is the window of the planned bulletin panel.

## Pass rule (all must hold)

Same as Phase 2 (`scripts/research_long_term.verdict`):
1. Discovery: D > 0 and t > 3.0 (Harvey-Liu-Zhu).
2. Holdout: D > 0 and t > 2.0.
3. Holdout: the filtered portfolio's USD active return is not below B's.

A filter with D > 0 and t > 2 in both periods, but failing rule 1, is labelled "supported, not confirmed". It does not go live.

## What goes live

- If K1 or K2 passes: a separate PR proposes the exclusion rule for the live AL list.
- If neither passes: red flags stay **information only**. The bulletin panel shows them for AL/TUT holdings as "check this", and the score and AL/TUT/SAT decisions do not change.

## Known limits

- **Survivorship bias against the filter.** The price panel is missing delisted stocks, and companies in insolvency are the most likely to be delisted. The filter can only be credited for names that survived. This is reported with the result, not corrected.
- **Classifier recall.** Auditor opinions inside financial reports, auditor changes and Borsa VBTS/brüt takas notices are not captured (see module docstring). The test covers what the classifier sees, not all red flags.
- **Repeated disclosures.** Some companies file the same event every month (for example konkordato instalment payments). They stay flagged for the whole period. This is intended: the condition is still present.

---

## Results (added 2026-10-11, after the run; the sections above are unchanged)

`python scripts/research_kap_red_flags.py`. Panel 2013-04 to 2026-09: discovery is 93 months and holdout 68. Base B: discovery +10.65%/yr (t 2.71), holdout +6.96%/yr (t 2.60).

Flagged stock-months in the top quintile matched the power table: K1 388 / 320, K2 81 / 63.

| Filter | Discovery D %/yr (t) | Holdout D %/yr (t) | Holdout active TL / USD | Verdict |
|---|---|---|---|---|
| K1 any flag, 90 days | −0.13 (−0.13) | +1.39 (1.18) | 8.36 / 8.21 | FAIL |
| K2 severe flag, 90 days | −1.35 (−1.61) | −0.33 (−0.91) | 6.63 / 6.51 | FAIL |

Sensitivity, 180-day window (no decision): K1 −0.79 (−0.81) / −0.96 (−0.64); K2 −1.99 (−1.81) / −0.68 (−1.07). Every sign is negative: excluding flagged names lowers the return.

**K3 (exploratory, cannot pass).** Crashed top-quintile names (dd5y ≤ −70%) with a 6-month outcome, mean 6-month return vs XU100:
- discovery: flagged 15 names +26.6%, unflagged 152 names +30.2%;
- holdout: flagged 5 names −2.3%, unflagged 62 names +22.0%.

The holdout gap points in the expected direction, but 5 observations cannot support a conclusion.

**Descriptive: are cheap stocks the distressed ones?** Mean monthly Spearman correlation with value_sn:
- any flag (90 days): −0.075 (162 months)
- CHS distress: −0.083
- F7 quality: +0.182
- dd5y: +0.015

Cheaper stocks have slightly fewer KAP red flags, lower CHS distress and higher F7 quality. value_sn does not systematically select distressed companies.

## Conclusion

Neither filter passes. The severe-flag filter is negative in both periods, and K1 is near zero.

As registered, red flags stay **information only**. The planned bulletin panel shows them for AL/TUT holdings as a "check this" note, without changing the score or the AL/TUT/SAT decision. This agrees with Phase 2: excluding distressed names did not help the value portfolio, through numeric proxies or through KAP disclosures.

Survivorship bias works against the filter (see Known limits). The result therefore does not prove that red flags are harmless, only that the surviving panel shows no gain from excluding them.
