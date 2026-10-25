# Short-term debt coverage (rollover risk) filter on `value_sn`: pre-registration

Written and committed on 2026-10-25, **before** the runner was written or executed on the panel. The rule, metrics, windows and decision rule are fixed here and are not changed after seeing the results.

## Question

`value_sn` uses total financial debt in `ey`'s enterprise value. For valuation that is right: maturity does not change what a company owes. Maturity matters for risk. A company whose short-term financial debt is larger than its liquid assets must roll the debt over, and in Turkey that happens at policy rates of 40–50% and with frequent credit tightening. None of the tested filters looks at debt maturity:
- CHS (H1a) uses total liabilities and cash over market assets.
- Altman EM (H1b) uses working capital and equity over total liabilities.

Both failed (`long_term_preregistration.md`). This study asks whether removing the stocks with the weakest short-term debt coverage improves the value portfolio.

## Prior exposure, stated honestly

- H1a and H1b failed. The post-hoc observation in `long_term_preregistration.md` says low CHS predicts returns on its own (rank IC t 4.27), but its information overlaps with value. The value top quintile already avoids most distressed names.
- On 2026-10-25 a check of the latest quarter (2026Q2) of 40 large stocks from live data, **without returns**: in 23 of 40, cash plus short-term financial investments was less than short-term financial debt; median short-term share of financial debt 42%.
- The EV definition study (`ev_definition_preregistration.md`, same day) used short-term financial investments inside EV. It found that netting them made the portfolio slightly worse (post-hoc decomposition, E1a). That is a valuation definition, not this filter; its results were seen before this document.
- A structure check of the 576 raw research statements (no returns): the first "Finansal Borçlar" row never exceeds "Kısa Vadeli Yükümlülükler", and the first "Finansal Yatırımlar" row never exceeds "Dönen Varlıklar", in any of about 23,200 quarters. The first occurrence is the short-term line (`pit_panel.merge_statement_batches` keeps occurrence order).
- No return, IC or portfolio result of the coverage measure has been computed before this document.

## Data and universe

Identical to the H1a test: `research_long_term.load()` (C1 panel, lag-75/100 availability, non-financial stocks, bottom 30% by `tlvol60` dropped each month), portfolio construction `core/long_term_research.py::portfolio` (top 20% of the remaining candidates by `value_sn_z`, equal weight, monthly, 2 × turnover × cost; universe average from the whole universe), comparison `diff_stats` (paired monthly difference vs the unfiltered base, NW t with 6 lags).
- **Discovery:** 2013-04 to 2020-12. **Holdout:** 2021-01 to the last panel month.

New items from `data/research/raw/*.pkl` with `pit_panel._pick` (first occurrence, no summing), joined to each stock-month on (`ticker`, `stmt_period`):
- `st_fin_debt`: first "Finansal Borçlar" (short-term financial debt).
- `st_fin_inv`: first "Finansal Yatırımlar" (short-term financial investments).
- `cash` from the panel's quarterly table ("Nakit ve Nakit Benzerleri").

## Measure and rule (one confirmatory trial)

$$\text{cov} = \frac{\text{cash} + \text{st\_fin\_inv}}{\text{st\_fin\_debt}}$$

- `st_fin_debt` equal to 0: no short-term financial debt, never flagged.
- `cash` missing or `st_fin_debt` missing: never flagged (missing data is not excluded, as in `flags()`). A missing `st_fin_inv` counts as 0.
- **D1 (confirmatory):** exclude a stock in month *t* when its `cov` is below the 10th percentile of `cov` among that month's universe stocks with `st_fin_debt > 0`. Same decile as H1a.

Descriptive only (cannot change the verdict): share of stock-months flagged; share of the base top-20% portfolio flagged; month-by-month rank IC of `log(cov)` (stocks with `st_fin_debt > 0`) against `fwd_ret_1m`, NW t.

## Decision rule

The H1a rule, `research_long_term.verdict` with a one-sided "improves" direction:
- **PASS:** discovery paired difference t > 3.0 and positive, **and** holdout difference positive with t > 2.0, **and** holdout USD active return of the filtered portfolio at least the base portfolio's.
- **SUPPORTED_NOT_CONFIRMED:** both differences positive with t > 2 (reported, no live change).
- **FAIL:** otherwise.

The trial ledger counts **1** new stock-selection trial (D1).

## Live rule

No automatic change. On PASS, the filter would go to the live rule in a separate PR with a new `config/live_rule.json` version. On any other verdict, short-term debt coverage may at most appear as information in the single-stock sheet.

## Results

(Appended after the run; the sections above stay unchanged.)
