# Data vendor (İş Yatırım) against KAP filings: value inputs (data audit, not a test)

Date: 2026-10-25. Runner: `python scripts/audit_vendor_vs_kap.py` → `data/reports/audit_vendor_vs_kap_2026-10-25.json`. No trial is added to the ledger.

## Design

`scripts/audit_restatements.py` (P2-5) compared total assets and net income with the first KAP report only. This audit widens it:
- **Items:** revenue, operating profit, parent net income, total assets, parent equity, cash, paid-in capital, financial debt (KAP short-term borrowings + current portion of long-term borrowings + long-term borrowings, against the sum of İş Yatırım's two "Finansal Borçlar" rows).
- **Two KAP figures per (stock, period):** the **first** report for the period, and the **restated** figure, which is the prior-period column of the same quarter's report one year later. For income items the restated figure exists for every quarter. For balance-sheet items it exists only for Q4, because the balance sheet's comparative column is the previous year-end.
- **Classes:** `match_first` (equals the first report), `restated` (differs from the first report but equals the restated one), `vendor_only` (equals neither), `missing`.
- **Sample:** 80 random (stock, period) pairs from 2014Q1–2025Q2 with a next-year report, seed 20261025. Unit scale (TL, thousand, million) is taken from total assets as a power of ten. A pair whose total assets differ by more than 10% after scaling is "unmatched".

The first run hit KAP's rate limit: HTTP 429 with an empty body, which `kap_text` cached as a page with no numbers (145 empty files). `kap_text` now retries with back-off and never caches an empty page. The figures below are from the clean second run.

## Results (62 comparable pairs, 18 unmatched)

| Item | Era | match_first | restated | vendor_only | missing |
|---|---|---:|---:|---:|---:|
| Revenue | 2014–2022 | 29 | 8 | 6 | 8 |
| | IAS 29 (2023Q4+) | 4 | **7** | 0 | 0 |
| Operating profit | 2014–2022 | 26 | 8 | 9 | 8 |
| | IAS 29 | 3 | **8** | 0 | 0 |
| Parent net income | 2014–2022 | 32 | 5 | 6 | 8 |
| | IAS 29 | 4 | **7** | 0 | 0 |
| Total assets | 2014–2022 / IAS 29 | 50 / 10 | | | |
| Parent equity | 2014–2022 / IAS 29 | 42 / 10 | | | 8 / 0 |
| Cash | 2014–2022 / IAS 29 | 50 / 10 | | | |
| Paid-in capital | 2014–2022 / IAS 29 | 49 / 11 | | | |
| Financial debt | 2014–2022 / IAS 29 | 44 / 9 | | | 3 / 1 |

Nine of the 18 unmatched pairs are IAS 29 year-ends (2023Q4, 2024Q4). The other nine are pre-2016 pages without XBRL data, plus a few currency mismatches. On the year-ends the vendor's total assets are the first figure × the year's inflation: AKYHO, THYAO and DOAS 2024Q4 give 1.309 against the first report, and CPI 2024-12 → 2025-12 is 1.309.

## Findings

1. **In the IAS 29 era the vendor shows each period re-expressed one year later.** Once a period's next-year report is out, İş Yatırım replaces the period's figures with that report's comparative column, which is in purchasing power one year later. This applies to every income quarter and to year-end balance sheets. Mid-year balance sheets have no later comparative, so they keep the first figures. Companies with a foreign functional currency (THYAO, TAVHL, EREGL) are not re-expressed.
2. **Before IAS 29, income figures are not reliably first-published.** About 1 in 6 to 1 in 5 income figures equals the restated figure, and about 1 in 8 equals neither KAP figure. For operating profit part of that may be definitional (İş Yatırım "FAALİYET KARI" against KAP "ESAS FAALİYET KARI"). Balance-sheet items match the first report in 84–98% of pairs.

## Consequence 1: the live TTM was wrong (fixed)

The live score built TTM flows as the sum of four discrete quarters, each the difference of consecutive YTD figures (`pit_panel.quarterly_table`, C1). Under finding 1 the two YTDs of one subtraction can be in different units. With 2026Q2 as the latest quarter, YTD 2025Q2 was already re-expressed ×1.32 (by the 2026Q2 report) while YTD 2025Q3 was not. The discrete 2025Q3 revenue of TL reporters came out at 0.42–0.61× 2024Q3 (sample of 20 large stocks).

Against the vendor-consistent formula below (all 530 stocks with a 2026Q2 report), the old live TTM was:
- revenue: 0.87× (interquartile range 0.86–0.89), 1 sign flip;
- operating profit: 0.89× (0.82–0.96), 141 stocks off by more than 20%, 9 sign flips;
- parent net income: 0.92× (0.82–1.02), 176 stocks off by more than 20%, 15 sign flips.

**Fix (`pit_panel.vendor_consistent_ttm`, used by `latest_value_ratios`, i.e. the live score only), for latest periods from 2023Q4:**

TTM = YTD(P) + YTD(FY y−1) × CPI(P) / CPI(Dec y−1) − YTD(P − 4 quarters); at Q4, TTM = YTD(FY).

YTD(P) is first-published, since its next-year report does not exist yet. YTD(P−4) has already been re-expressed into P's units by P's own report. The annual YTD is carried to P with CPI, as in C1. In C0, with no CPI, the formula equals the old sum of four quarters, so the old parity tests still hold. Test: `tests/test_valuation_parity.py::test_live_ttm_handles_vendor_reexpressed_prior_year`.

Effect on the live ranking at 2026-09-30 (565 non-financial stocks, today's market value): rank correlation of value_sn old vs new 0.965; 8 of the 112 top-20% names change. The forward record starts on 2026-11-01, so the record starts with the fixed definition.

## Consequence 2: the backtest's IAS 29 window used later numbers (open)

The research panel was fetched on 2026-09-27. Every period up to 2025Q2 was therefore in re-expressed form. At a decision month in that window the panel used figures that were published about a year later, in later purchasing power, and the C1 TTM mixed units in the same way as the live score did. Cross-sectional ranks are partly protected, because stocks reporting the same period share one CPI factor. Mixed periods and foreign-currency reporters are not.

The correct fix is the first-published panel (P3-1, `docs/plan_2026-10-21.md`). The live parity with the panel is broken for 2023Q4+ by design until then: the panel's numbers in that window are not what was known at the time.
