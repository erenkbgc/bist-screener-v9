# Long-term model research: pre-registration

Written and committed on 2026-10-10, **before** any test below was run. The hypotheses, definitions, base portfolio, metrics and pass rule are fixed here. They are not changed after the results are seen. A changed definition counts as a new test and needs a new pre-registration.

## Background

- Factor evidence on the point-in-time panel (`backtest_factor_model.py`, 2013–2026):
  - Value (IC1 t 7.15), sector-neutral value (t 6.59), low volatility (t 7.25) and SUE (t 5.63) rank stocks.
  - 12-1 momentum does not (t 0.71).
  - The evidence is the same in TL, USD and XU100-excess terms (`phase1_diagnostics.md`).
- The live model shows stocks that fell 70%+ in five years as STRONG_OPPORTUNITY: 4 of 26 tickers in September 2026.
- The value premium's significance is fragile to survivorship bias (`phase1_diagnostics.md`, section 3).
- About 40% of live weight (catalyst, ownership) has no historical data and has never been tested. Regime weights have never been tested either.

**Prior exposure, stated honestly.** Phase 1 diagnostics already looked at the full sample:
- crashed stocks in the value-proxy top quintile did not underperform (descriptive);
- low-vol had a negative top-quintile active return.

H2a and H8 below are therefore not clean tests. H2a stays in the main set because the user question requires an answer, but the prior exposure is noted. H8 is reported as exploratory and cannot pass.

## Data and universe

- `data/research/factors_monthly.parquet`: point-in-time monthly factors, non-financial stocks, 2013-04 to 2026-09.
- Statements:
  - `quarterly.parquet`, extended with the balance-sheet and income items listed below from the same raw Is Yatirim cache (`data/research/raw/*.pkl`);
  - publication lag of 75 days for interim statements and 100 days for annual statements (unchanged).
- `monthly_prices.parquet` and `fx.parquet` (USDTRY, XU100).
- Each month, the least liquid 30% by 60-day median TL volume is dropped. Months with fewer than 30 names are dropped. Both rules are as in `factor_backtest.prepare`.
- **Discovery:** 2013-01-01 to 2020-12-31. **Holdout:** 2021-01-01 to the end of the data.

## Base portfolio

**B = top quintile of `value_sn`**, equal-weighted and rebalanced monthly:
- `value_sn` is the mean of the bm, ep, sp and ey z-scores, demeaned within sector;
- it is the same as in `backtest_factor_model.add_composites`;
- it is the tested core of the live valuation score.

Each hypothesis changes B in one of two ways:
- an **exclusion filter**: flagged names are removed before the quintile is formed;
- a **composite**: the ranking variable changes.

## Definitions

Statement items are added to `core/pit_panel.py`. Labels are exact Is Yatirim rows.

| Item | Label |
|---|---|
| current_assets | Dönen Varlıklar |
| current_liab | Kısa Vadeli Yükümlülükler |
| noncurrent_liab | Uzun Vadeli Yükümlülükler |
| retained | Geçmiş Yıllar Kar/Zararları |
| ebit | Finansman Gideri Öncesi Faaliyet Karı/Zararı (fallback: op_profit) |
| fin_expense | (Esas Faaliyet Dışı) Finansal Giderler (-) |

- Total liabilities: TL = current_liab + noncurrent_liab.
- Market value of total assets: MTA = mcap + TL.

**CHS distress probability** (Campbell, Hilscher & Szilagyi 2008, 12-month model):
- Coefficients are fixed from the paper. Nothing is re-estimated on BIST.
- The PRICE term is dropped, because the nominal TL price level is not comparable across stocks.
- Formula: `0.0 − 20.12·NIMTAAVG + 1.60·TLMTA − 7.88·EXRETAVG + 1.55·SIGMA − 0.005·RSIZE − 2.27·CASHMTA + 0.070·MB`.
- Inputs:
  - NIMTAAVG: the last four quarterly net incomes over MTA, with CHS geometric weights φ = 2^(−1/3) per quarter, scaled to sum to 1.
  - EXRETAVG: monthly log(1+r_i) − log(1+r_XU100) over 12 months, with weights φ per month, scaled to sum to 1.
  - SIGMA: vol60 (daily) × √252.
  - RSIZE: log(mcap / sum of panel mcap that month).
  - CASHMTA: cash / MTA.
  - MB: mcap / adjusted book equity, where adjusted book equity is BE + 0.1·(mcap − BE), floored at 1 TL.
- Higher score means more distress.

**Altman EM score** (Altman 2005):
- Formula: Z = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4.
- Inputs: X1 = (current_assets − current_liab)/TA; X2 = retained/TA; X3 = TTM ebit/TA; X4 = equity/TL.
- Distress zone: Z < 1.1.

**F7: Piotroski score without cash-flow items.** The panel has no cash-flow statement, so CFO and accruals are dropped. Each item scores 1 point, for a range of 0 to 7:
1. ROA > 0
2. ΔROA > 0 vs the same quarter a year earlier
3. Δ(fin_debt/TA) < 0
4. Δ(current ratio) > 0
5. no paid-in capital increase from rights issues in 12 months (nsi_rights_12m = 0)
6. Δ gross margin > 0
7. Δ asset turnover > 0

ROA uses TTM net income over TA.

**dd5y**: month-end adjusted close over its trailing 60-month maximum, minus 1. At least 36 months of history are required (`diagnose_crashed_picks.drawdown_from_peak`).

**hi52**: month-end adjusted close over the maximum of the last 12 month-end adjusted closes.

## Hypotheses (10 confirmatory tests)

| ID | Change to B | Prediction | Source |
|---|---|---|---|
| H1a | Exclude the worst CHS decile of the month's universe | improves | Campbell-Hilscher-Szilagyi 2008 |
| H1b | Exclude Altman EM Z < 1.1 | improves | Altman 2005 |
| H2a | Exclude dd5y ≤ −70% | two-sided (prior exposure noted) | De Bondt-Thaler 1985 vs distress literature |
| H2b | Exclude dd5y ≤ −70% only when F7 ≤ 3 | improves | Piotroski 2000 conditional on losers |
| H3a | Exclude the bottom quintile of mom_12_1 | improves | Asness-Moskowitz-Pedersen 2013 |
| H3b | Exclude the bottom quintile of hi52 | improves | George-Hwang 2004 |
| H4a | Rank on 0.5·value_sn_z + 0.5·gpa_z | improves | Novy-Marx 2013 |
| H4b | Exclude F7 ≤ 2 | improves | Piotroski 2000 |
| H5 | Rank on 0.5·value_sn_z + 0.5·sue_z | improves | Bernard-Thomas 1989 |
| H6 | Regime weights vs fixed weights | **not tested; see below** | — |
| H7 | Catalyst and ownership weights | **not tested; see below** | — |
| H8 (exploratory) | Exclude the top quintile of vol60 | improves | Ang et al. 2006 |

The weights in H4a and H5 are fixed at 50/50 and are not searched.

- **H6 (regime weights).** The live regime engine cannot be rebuilt point-in-time without refitting its model, and the macro study (`macro_drivers_preregistration.md`) found no predictability of market direction. Decision without a test: fixed weights, and the regime weight table is removed from live scoring.
- **H7 (catalyst and ownership).** There is no historical KAP or ownership data, so these cannot be tested. Decision without a test: weight 0 in the score. Both stay as display-only information.

## Metric

- **Primary:** the monthly difference D_t = active(B') − active(B).
  - active = top-quintile 1-month forward return − equal-weighted universe mean − 2 × turnover × 20 bps.
  - B' is the modified portfolio and B the base.
  - The t-statistic is Newey-West with 6 lags.
- Also reported for B and every B':
  - annualised net active return and its t-statistic;
  - USD and XU100-excess versions (`fwd_ret_1m_usd`, `_xs`);
  - value-trap rate: the share of picks with 6-month excess return below −30%;
  - maximum drawdown of the cumulative active return;
  - average number of names and turnover;
  - survivorship break-even universe delisting rate for t < 3, with R = −100% and k = 3 (method of `survivorship_sensitivity.py`).

## Pass rule (all must hold)

1. Discovery: D has the predicted sign and |t| > 3.0 (Harvey-Liu-Zhu). This is above the Bonferroni threshold of ≈ 2.81 for 10 tests at α = 0.05, two-sided. For H2a, either sign can pass.
2. Holdout: D has the same sign as in discovery and |t| > 2.0.
3. Holdout: B' net active return is ≥ B net active return in USD terms as well.

**Fallback rule.** A filter that fails rule 1 but has D > 0 in both periods with t > 2 in each is labelled "supported, not confirmed". It may be shown as a display flag. It may not change scoring.

## What goes live

- **New live score:** value_sn, plus every passing composite component, with weights fixed at equal shares.
  - The 50/50 weights of H4a and H5 extend to 1/n when both pass.
  - No IC-IR fitting. With at most three components, equal weights avoid an extra searched parameter.
- **Exclusions:** every passing exclusion filter becomes a hard filter, applied before ranking.
- **Low volatility:** keeps its current weight only as tested in the existing evidence. H8's result is reported but cannot change it.
- **Alignment:** the live score is changed to match the tested definition exactly. This means peer-free sector-neutral value z-scores, with the same four ratios. The live and tested models must not differ again; see `phase1_diagnostics.md` section 1.
- **If nothing passes:** the live score becomes plain value_sn, with weight 0 on catalyst and ownership, and this is stated in the report.

## Known limits

- Survivorship bias: the universe is today's listing, and delisted prices are unavailable. Break-even rates are reported, but they are not a correction.
- Financial companies are excluded, so the results do not cover banks or insurers.
- Statements are nominal; IAS 29 restatements are not modelled.
- The CHS and Altman coefficients come from US and emerging-market samples and are not re-estimated for BIST. This is deliberate, to avoid in-sample fitting.
- Signals and trades use the same month-end close.

---

## Results (added 2026-10-10, after the run; the sections above are unchanged)

`python scripts/research_long_term.py`. The panel runs from 2013-04 to 2026-09: 93 discovery months and 68 holdout months.

Implementation notes. These were fixed in unit tests (`tests/test_long_term_research.py`) before the run:
- Missing data never triggers an exclusion.
- In H4a and H5, a missing second component counts as 0 (as in `add_composites`).
- The CHS intercept is omitted. Only the ranking is used, so the intercept has no effect.

Coverage of the new signals:

| Signal | Rows with a value |
|---|---|
| CHS | 96.8% |
| Altman | 98.8% |
| F7 | 91.9% |
| dd5y | 79.9% |
| hi52 | 100% |

**Base B** (value_sn top quintile; net active return per year, NW t with 6 lags):

| Period | Net active / yr (TL) | Net active / yr (USD) | Value-trap rate | Max DD of active | Names | Turnover |
|---|---|---|---|---|---|---|
| Discovery | +10.65% (t 2.71) | +10.60% | 4.3% | −7.2% | 43 | 16.7% |
| Holdout | +6.96% (t 2.60) | +6.82% | 18.7% | −9.1% | 60 | 17.6% |

The holdout value-trap rate is higher because the whole universe changed: 22.6% of all holdout rows had a 6-month excess below −30%, against 7.0% in discovery. B stays below the universe rate in both periods.

**Hypotheses.** D is the annual difference in net active return versus B, with NW t at 6 lags.

| ID | Discovery D (t) | Holdout D (t) | Holdout B′ active TL / USD | Holdout trap rate | Result |
|---|---|---|---|---|---|
| H1a CHS worst decile | −0.14% (−0.18) | +0.05% (0.05) | 7.01% / 6.83% | 18.2% | FAIL |
| H1b Altman EM < 1.1 | +0.40% (0.26) | −0.11% (−0.10) | 6.86% / 6.79% | 18.8% | FAIL |
| H2a dd5y ≤ −70% | −1.50% (−2.04) | +0.32% (0.90) | 7.28% / 7.12% | 18.6% | FAIL |
| H2b dd5y ≤ −70% and F7 ≤ 3 | −0.44% (−0.97) | +0.34% (2.00) | 7.30% / 7.14% | 18.7% | FAIL |
| H3a bottom mom_12_1 quintile | −0.41% (−0.42) | +1.52% (0.80) | 8.48% / 8.12% | 18.7% | FAIL |
| H3b bottom hi52 quintile | +2.24% (1.53) | +2.18% (1.33) | 9.14% / 8.87% | 17.8% | FAIL |
| H4a value + GP/A | −2.64% (−0.73) | −8.36% (−2.55) | −1.40% / −1.43% | 24.2% | FAIL |
| H4b F7 ≤ 2 | +0.42% (0.50) | −0.21% (−0.25) | 6.75% / 6.62% | 19.2% | FAIL |
| H5 value + SUE | −4.49% (−1.23) | +0.21% (0.07) | 7.17% / 6.69% | 20.8% | FAIL |
| H8 top vol60 quintile (exploratory) | −3.84% (−2.05) | +0.47% (0.31) | 7.43% / 7.31% | 16.5% | — |

**No hypothesis passed, and none reached "supported, not confirmed".**

What the results show:
- **H2a** answers the user's question directly. Removing stocks that fell 70%+ in five years from the value portfolio did not help. In discovery it cost 1.5% per year (t −2.04). In surviving stocks, a crash is not a reason to exclude a cheap stock. The survivorship caveat applies most strongly here (`phase1_diagnostics.md`).
- **H4a** made things worse. Mixing GP/A into value halves its tilt towards cheap stocks.
- **H3b** is the only filter that was positive in both periods, but its t is below 2 in each.

As pre-registered, the live score becomes plain value_sn:
- no exclusion filters;
- catalyst and ownership weight 0;
- no regime weights.

Survivorship. The holdout B′ series falls below t = 3 at h = 0 by construction, so the break-even is not informative here; the JSON has the values. For H1a, the mean active return turns negative at a 3.5% annual universe delisting rate (full loss, 3× concentration). The break-even uses NW t with 1 lag (the method of `survivorship_sensitivity.py`), so its t at h = 0 differs from the table above.

**Post-hoc observation (not a result).** As standalone signals over the full sample, low CHS (rank IC t 4.27) and F7 (t 3.95) do predict returns. Altman EM does not (t 0.93). Their information overlaps with value: the value top quintile already avoids most distressed names. This was seen after the run, so it cannot support a new rule without a new pre-registration.
