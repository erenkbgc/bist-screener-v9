# Valuation round 2 pre-registration: deferred-tax-free E/P and tangible B/M

Written 2026-11-22, before any code for this study exists and before any return of either candidate has been computed. Trials: 2 stock-selection trials, ledger N_sel 90 -> 92.

## Motivation

Round 1 (`valuation_round1_preregistration.md`) tested three new composites and all failed. Candidates that stayed close to R0 had no power; candidates that moved far from R0 lost return. This round changes only one input of R0 at a time and keeps the rest of `value_sn` unchanged.

Both inputs target Turkish accounting effects that are not operating value:

- **Deferred tax under IAS 29.** Since 2023Q4 the deferred tax line (`Ertelenmiş Vergi Geliri (Gideri)`) moves net income by large amounts that come from restating non-monetary assets, not from the business. Example from the raw vendor cache: THYAO reports deferred tax income of several billion TL per period. E/P built on net income therefore ranks part of this accounting effect as value.
- **Intangibles and goodwill in book value.** Book equity includes intangible assets and goodwill (`Maddi Olmayan Duran Varlıklar`, `Şerefiye`). These are revalued and re-expressed under IAS 29 and are not tangible collateral. Tangible book value is a standard alternative.

The IAS 29 net monetary position gain cannot be isolated in the vendor template (no separate line; the nearest line, `Vergi Öncesi Diğer Gelir ve Giderler`, is a median 6.5% of net income in 2024+, far below known monetary gains). It is not tested here.

## Data

- Panel: `data/research/factors_monthly.parquet` (point-in-time baseline, lag-75 availability), the same panel used for round 1. Secondary: `factors_monthly_kapdates.parquet`.
- New items are read from the same raw vendor cache (`data/research/raw/*.pkl`) and pass through the same pipeline as existing items (`build_pit_panel.build_panel_from_raw`: C1 constant-unit TTM, IAS 29 re-expression undone, TTM bridge). The new items are added to the item maps inside the study script only; `core/pit_panel.py` and live code are not changed.
  - `deferred_tax` (income statement): label `Ertelenmiş Vergi Geliri (Gideri)`. Sign as reported: positive = income.
  - `intangibles` (balance sheet): label `Maddi Olmayan Duran Varlıklar`.
  - `goodwill` (balance sheet): label `Şerefiye`.
- Each stock-month joins the quarterly row of its own `stmt_period` (the period already used for R0 in that month), so availability is identical to R0.
- Parity check before any return is computed: after the rebuild, the existing columns (`bm`, `ep`, `sp`, `ey`) must equal the baseline panel. If they do not, the study stops and the difference is reported.

## Candidates

All other `value_sn` legs and the composite construction are unchanged (`fb.prepare(raw, FACTORS, liq_drop_pct=0.3)` then `add_composites`; candidate score = resulting `value_sn_z`).

**V2B `ep_xdt`** — replace the `ep` leg:

    ep_xdt = (TTM ni_parent - s * TTM deferred_tax) / mcap
    s = TTM ni_parent / TTM net_income, clipped to [0, 1]; s = 1 if net_income is missing or 0
    missing TTM deferred_tax -> 0 (the vendor leaves the line empty when there is no deferred tax)
    if TTM ni_parent is missing, fall back to TTM net_income with s = 1 (same fallback as R0)

**V2A `bm_tan`** — replace the `bm` leg:

    bm_tan = (equity_parent - intangibles - goodwill) / mcap, NaN if the numerator <= 0
    missing intangibles or goodwill -> 0
    if equity_parent is missing, use equity (same fallback as R0)

No parameter in either definition is fitted to returns.

## Fixed pass rule (identical to round 1, copied verbatim)

Candidate monthly top-20% portfolio vs R0 value_sn top-20%, same universe, liquidity cut, 1M TL costs and next-close fills as scripts/research_portfolio_backtest.py. Paired D = net active(candidate) - net active(R0). PASS iff D > 0 in discovery 2013-2020 with NW t(D) >= 1.0 AND D > 0 in holdout 2021+ with NW t(D) >= 2.0 AND holdout USD max drawdown not worse than R0 by more than 2 pp. Also report DSR at the updated N_sel. Every method tested adds +1 to N_sel in the trial ledger, PASS or FAIL.

The verdict is taken on the primary (lag-75) panel. The KAP-date panel is reported as a robustness check and cannot turn a FAIL into a PASS.

## Outputs

- Script: `scripts/research_valuation_round2.py` (reuses `run_panel_evaluation` machinery from round 1).
- Report: `data/reports/research_valuation_round2_2026-11-22.json`.
- Also reported (descriptive, no decision): coverage of each new item, share of months where the leg changes, rank correlation and top-20% overlap with R0, and the IAS 29 window (2024-05+).
- Results are appended below a `## Results` heading; the sections above are not edited after results exist.

A PASS would only make the candidate eligible for a separate pre-registered forward record. The live rule `R0-2026-10-12` is not changed by this study.
