# First-published statement panel for the IAS 29 window (P3-1): method and comparison plan

Written and committed on 2026-10-25, **before** the first-published data was complete and before any return was computed on it. This is a data correction, not a new signal. It adds no trial to the ledger: the same rule (R0, `value_sn` top 20%) is re-measured on corrected inputs.

## Why

`vendor_vs_kap_audit.md`: İş Yatırım replaces each IAS 29-era period with its next-year comparative, one year of CPI later. The research panel, fetched on 2026-09-27, therefore used at each decision month of the IAS 29 window figures that were published about a year later, and its discrete quarters mixed units. Before IAS 29, about 1 in 6 to 1 in 5 income figures were restated values.

## Data

`scripts/build_first_published.py`:
- Universe: every stock that was in the liquid non-financial universe (top 70% by `tlvol60`) in any month from 2023-06.
- All "Finansal Rapor" disclosures of those stocks published from 2023-01-01 (`kap_archive.parquet`), fetched from KAP (`data/research/kap_reports/` cache, 3 s pause, back-off on HTTP 429).
- Period from the page ("Cari Dönem" date), not from the publication month, because IAS 29 deadline extensions moved filings into other months.
- Per (stock, period): the first **consolidated** report if one exists, otherwise the first report.
- Items (current-period column): total assets, parent equity, total equity, paid-in capital, cash, revenue (Hasılat), gross profit, operating profit (ESAS FAALİYET KARI), parent net income, net income, financial debt (short-term borrowings + current portion of long-term borrowings + long-term borrowings).

`scripts/rebuild_panels_first_published.py`:
- For periods from 2022Q4, the vendor's items are replaced by the first-published values. Items KAP did not give stay vendor.
- Unit: KAP total assets scaled to the vendor's by a power of ten. When the scaled ratio is outside [0.6, 1.8] (another currency), the period stays vendor. The IAS 29 re-expression (×1.3–1.5) is inside the band.
- Then the unchanged pipeline: C1 `quarterly_table` (correct for first-published YTDs, each in its own period-end units), lag-75 and KAP-date availability, `build_monthly_factors`, with the share-count fix (`share_count_fix.md`). Output in `data/research/fp/`; the current panel files are not changed.

Known limits, stated before the run:
- Periods before 2022Q4 stay vendor, so TTMs that reach back past 2022Q4 (decision months up to about 2023-09) mix sources at the boundary.
- KAP's "ESAS FAALİYET KARI" may differ by definition from the vendor's "FAALİYET KARI" (pre-IAS 29 audit: 9 of 51 matched neither).

## Comparison (fixed)

Same rule and code as `share_count_fix.md`: `long_term_research.portfolio` top 20% by `value_sn_z`, active return against the universe, and `value_sn` rank IC, on the current panel (vendor, share-count fixed) against the first-published panel:
1. **IAS 29 window, decision months 2024-05 to the last month**: active %/yr (NW t), rank IC (NW t), paired difference (NW t), top-20% overlap.
2. **Holdout 2021-01 onward**: the same figures.
3. Costed backtest (`research_portfolio_backtest.py`, P0, 1M TL, base costs) on the first-published panel, holdout active vs EW.

What will be done with the result:
- The first-published panel becomes the research baseline for 2022Q4 onward, whatever the result, because it is what was known at the time.
- The README headline figures are updated to it.
- The live rule does not change (the live score already uses first-published latest quarters, with the vendor-consistent TTM of `vendor_vs_kap_audit.md`).

## Results

(Appended after the run; the sections above stay unchanged.)
