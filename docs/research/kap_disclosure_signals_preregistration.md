# KAP disclosure timing and buybacks: pre-registration

Written and committed on 2026-10-12, **before** any return was computed for the signals below. The signal definitions, portfolios, tests and pass rules are fixed here. A changed definition counts as a new test and needs a new pre-registration.

## Question

Do disclosure behaviours carry information that prices miss? Four signals, each with a published prior:

| ID | Signal | Expected sign | Prior |
|---|---|---|---|
| S1 | KAP marks the financial report as late (`isLate`) | − | Late filers underperform (Begley & Fischer 1998; Alford, Jones & Zmijewski 1994) |
| S2 | The report is published later than the company's own habit | − | Delay signals bad news (Bagnoli, Kross & Watts 2002) |
| S3 | The report is published on a Friday after the session close, or at the weekend | − | Bad news is released when attention is low (DellaVigna & Pollet 2009) |
| S4 | The company starts buying back its own shares | + | Buybacks are followed by positive drift (Ikenberry, Lakonishok & Vermaelen 1995) |

**Insider trading** (`Pay Alım Satım Bildirimi`) is **not** tested here. The archive summaries do not state the direction of the trade reliably; many of them read just "Alım Satım İşlemleri". Testing it needs the disclosure bodies (about 18,600 documents), which is a separate data project.

## Data

- `data/research/kap_archive.parquet`: all KAP disclosures from 2010-01 to 2026-10, with `published_at`, `subject`, `ruleType` and `isLate`.
- `data/research/factors_monthly.parquet`: month-end universe, `tlvol60` and `fwd_ret_1m`, non-financial stocks.
- First publication per (ticker, period) from `pit_panel.kap_report_dates` (`kap_report_dates_preregistration.md`).

## Signal definitions

A financial report is a filing with `disclosureClass == "FR"` and subject "Finansal Rapor" or "Finansal Rapor Bildirimi". Only the **first** filing of each (ticker, period) counts.

- **S1:** the first filing has `isLate == True`.
- **S2:** actual lag (publication date − period end, in days) minus the median lag of the same company's previous 4 filings of the same quarter type is **≥ 14 days**. At least 2 previous filings are needed.
- **S3:** the first filing's `published_at` is on a Friday at or after 18:00, or on a Saturday or Sunday.
- **S4:** a "Payların Geri Alınmasına İlişkin Bildirim" filing for a ticker with no such filing in the previous 180 days. This marks the start of a buyback episode.

**Event month:** the calendar month of `published_at`.

## Portfolios (calendar-time)

At each month-end t:
- **Universe:** the month-t liquid universe as in `factor_backtest.prepare`. The bottom 30% by `tlvol60` is dropped; financials are already excluded from the panel.
- **Signal portfolio:** equal-weighted, holding the universe stocks with a signal event in months t, t−1 and t−2, so each event is held for 3 months.
  - Return: `fwd_ret_1m` over month t+1. Entry is therefore at a month-end after the event: a delay, never a look-ahead.
  - **S1–S3 control:** the EW portfolio of universe stocks that published a financial report in the same window **without** the signal. Timing, not reporting, is what is being tested.
  - **S4 control:** the EW universe.
- **Monthly statistic:** D_t = signal portfolio return − control return. Months with fewer than 5 stocks in the signal portfolio are skipped.
- **Statistic:** annualised mean of D with Newey-West t (3 lags).

**Periods:**
- S1–S3: discovery to 2020-12, holdout 2021-01 onward.
- S4: the buyback subject exists only from 2018. Discovery is 2018-01 to 2021-12, holdout 2022-01 onward.

## Pass rule (each signal)

There are 4 tests. All of the following must hold:
1. Discovery: D has the expected sign and |t| > 3.0. Harvey-Liu-Zhu; above the Bonferroni level of about 2.50 for 4 tests.
2. Holdout: the same sign, |t| > 2.0.
3. At least 24 months with a portfolio in each period.

A signal that meets rules 1 and 3 but not rule 2 is labelled "discovery only".

## What goes live

- A passing negative signal (S1–S3) becomes an information flag in the bulletin for held names ("bilanço geç / alışılmıştan geç / cuma akşamı açıklandı"). It does not change the rotation unless a later pre-registration tests it as an exclusion filter.
- A passing S4 becomes an information flag ("geri alım başladı").
- A failing signal is not shown.

## Known limits

- Calendar-time portfolios are concentrated in reporting seasons, so some months have few names.
- `isLate` is KAP's own flag, and its definition may have changed over time.
- **Survivorship:** delisted companies are missing from the panel. They are likely to be over-represented among late filers, so S1 and S2 are biased **against** finding the effect.
