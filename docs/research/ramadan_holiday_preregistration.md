# Ramadan and pre-holiday effects: pre-registration

Written and committed on 2026-10-12, **before** any return was computed by calendar period. The calendars, tests and pass rules are fixed here.

## Question

1. **R1, Ramadan.** Are BIST returns higher during Ramadan than in the rest of the year? Białkowski, Etebari & Wisniewski (2012) found higher and less volatile returns during Ramadan in 14 Muslim-majority markets, Turkey included, over 1989–2007. The proposed mechanism is better investor mood.
2. **R2, pre-holiday.** Are returns higher on the last trading day before a market holiday? This is documented for the US (Ariel 1990; Lakonishok & Smidt 1988) and other markets. On BIST, the day before a bayram (arife) is often a half session.

The working hypothesis is that mood and cultural calendars move prices.

## Prior exposure

The 2005–2007 part of the sample overlaps the Białkowski et al. sample. No BIST-specific Ramadan or pre-holiday result was looked at in this project before this note.

## Data

- **XU100** daily close, yfinance `XU100.IS`, 2005-01-03 to 2026-10-09. Checked against borsapy: the ratio is 1.0000 with standard deviation 0.00001 on the 3,951 overlapping days. Holidays have no row.
- **USDTRY** daily from yfinance `USDTRY=X`, forward-filled to BIST days.
- **Returns:** daily log returns of XU100 in USD (primary) and TL (secondary). The USD return removes most of the inflation trend.

## Calendars

- **Ramadan** (1 to 29/30 Ramadan) comes from the Umm al-Qura calendar (`hijridate` 2.5.0). Spot checks against Diyanet: Ramadan began 2024-03-11 and 2025-03-01; Ramazan Bayramı fell on 2023-04-21 and 2024-04-10. All match. A one-day difference with Diyanet in some years changes about 5% of Ramadan days and is ignored.
  - A trading day is a Ramadan day if its date is in [1 Ramadan, last day of Ramadan].
  - There are 22 Ramadans (AH 1426–1447).
- **Pre-holiday day:** a trading day t whose next weekday is not a trading day, so the market is closed on a weekday. This uses the XU100 calendar itself, so it covers bayrams and national holidays. Weekends alone do not count.

## Tests

The regression is daily_return_t = a + b · D_t + e_t, with Newey-West standard errors (5 lags). b is the daily return difference, and is reported annualised (× 252) for readability.

| Test | D_t |
|---|---|
| R1 | 1 on Ramadan days |
| R2 | 1 on pre-holiday days |

**Periods:**
- discovery 2005-01 to 2015-12 (11 Ramadans);
- holdout 2016-01 to 2026-10 (11 Ramadans).

**Pass rule (each test), all must hold, on USD returns:**
1. Discovery: b > 0 and t > 3.0. Harvey-Liu-Zhu; above the Bonferroni threshold of about 2.24 for 2 tests.
2. Holdout: b > 0 and t > 2.0.
3. b > 0 in TL returns in both periods (sign only).

R1 also reports, descriptively:
- the volatility ratio (Ramadan / rest);
- per-Ramadan mean returns (how many of the 22 were above their year's non-Ramadan mean).

## What goes live

- A passing effect becomes a calendar note in the bulletin, for example "Ramazan dönemi: geçmişte ortalamanın üstünde getiri". The monthly rotation is not changed: a calendar tilt on the market as a whole is not part of a stock-selection rule.
- A failing effect is not shown.

## Known limits

- **Few Ramadans:** about 20 trading days per Ramadan, so the test has more power than the event study, but not much.
- **Pre-holiday days:** about 8–10 a year (roughly 180 in all). One large day can dominate the mean, so the median difference is also reported.
- **Partial overlap:** 2005–2007 overlaps the published sample.
