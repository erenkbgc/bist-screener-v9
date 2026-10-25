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

## Method change (2026-10-25, still before any return was computed)

The full KAP fetch ran at about one page every 15 s under KAP's rate limit (HTTP 429): about 30 hours for 7,691 pages. It was stopped after about 250 new pages. The cached pages showed that the vendor's re-expression follows a simple rule, so the first-published figures can be recovered from the vendor data with one KAP page per company instead.

**Re-expression model** (periods from 2023Q4, whose first report is already in IAS 29 units; checked on the cached pages):
- Q1–Q3: income items equal first × CPI(P+4)/CPI(P) once the next-year report exists (10–11 of 16 per item; 5 first-published, which are foreign-functional-currency reporters). Balance-sheet items equal first (16 of 16).
- Q4: the whole column equals first × CPI(L)/CPI(P), where L is the latest report that shows the year-end as a comparative, at most one year later (19 of 26). The 7 misfits are solo/consolidated report mismatches (YESIL, FMIZP, DUNYH, IDGYO) and KAREL.
- 2022Q4–2023Q3 do **not** follow it. Their first reports were nominal, and the vendor shows the IAS 29 first-application restatement, which is indexed month by month (2022Q4 revenue ×1.8–2.0 against a year-end CPI factor of 1.648).

**Procedure** (`scripts/classify_reexpression.py`, `rebuild_panels_first_published.py`):
1. Per company, the 2025Q2 first report (2024Q2 if missing), consolidated preferred. The vendor's income item divided by first = CPI(Jun 2026)/CPI(Jun 2025) ±1% → `reexpressed`; 1 ±1% → `not_reexpressed`; otherwise `unknown` (left as vendor).
2. `undo_reexpression`: for `reexpressed` companies, divide by the model factor (Q4: all items; Q1–Q3: income items).
3. `bridge_ttm`: for latest periods 2023Q4–2024Q3, TTM comes from the formula the live score uses: YTD(P) + YTD(FY 2023) × CPI(P)/CPI(Dec 2023) − YTD(P−4). The vendor's YTD(P−4) for 2023Q1–Q3 is the restated comparative in P's own report, which is what was known at the time. From 2024Q4 all inputs are first-published, so C1 applies unchanged.
4. Market value from İş Yatırım HisseTekil `PD` (`market_cap_source.md`), because borsapy's "raw" close is back-adjusted for rights issues.

The comparison section above is unchanged. "First-published panel" now means steps 1–4. The KAP-replacement path (`--kap-fp`) is kept for when the full fetch is completed.

## Results

(Appended after the run; the sections above stay unchanged.)
