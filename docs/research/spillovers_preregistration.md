# Sector spillovers: pre-registration

Written and committed on 2026-10-12, **before** any return below was computed. The groups, regressions and pass rules are fixed here.

## Question

Stocks in the same sector share news. Two testable forms of the "spider web":

1. **L1, big-to-small lead-lag.** Does last week's return of a sector's big stocks predict this week's return of the same sector's small stocks, beyond the small stocks' own last week? Hou (2007) finds this within US industries: information reaches big firms first.
2. **L2, intra-industry information transfer.** When the first company in a sector publishes its quarterly report, do its sector peers that have not yet reported move with it?
   - **L2a, same day:** is there a transfer on the announcement day itself (Foster 1981)?
   - **L2b, underreaction:** do the peers keep drifting in the same direction over the following days (Thomas & Zhang 2008)?

L1 and L2b could be traded. L2a only shows whether the transfer exists.

## Data

- **Prices:** daily adjusted closes from `data/research/raw/*.pkl` (non-financial stocks).
- **Universe:** each month, the liquid universe of the PIT panel (`factors_monthly.parquet`, bottom 30% by `tlvol60` dropped). Market value is `mcap` at the previous month-end.
- **Sectors:** `config/fintables_ticker_sektor.json`.
- **Report dates:** the first KAP publication per (ticker, period), from `pit_panel.kap_report_dates` (`kap_report_dates_preregistration.md`).
- **Periods:** discovery before 2021-01-01, holdout after.

## L1: lead-lag

- **Weeks:** Friday close to Friday close, on the BIST calendar. A week's universe and size groups come from the last month-end before the week starts.
- **Groups:** within each sector with at least 4 universe names, stocks above the sector's median `mcap` are "big", the rest "small". Group returns are equal-weighted.
- **Regression:** each week w+1, across sectors:
  - r_small(s, w+1) = a + b · r_big(s, w) + c · r_small(s, w) + e
  - weeks with fewer than 5 sectors are skipped.
- **Statistic:** the time-series mean of b (Fama-MacBeth), with Newey-West t (4 lags).
- **Expected sign:** b > 0.
- **Descriptive:** a long-only portfolio of small stocks in the top third of sectors by r_big(w), minus all small stocks, held during w+1. Weekly mean and t.

## L2: information transfer

- **Event:** for each sector and fiscal period, the first universe company to publish (the "announcer").
  - Event day t0 = the first trading day on or after its `kap_available_at`.
  - Several companies may publish on the same first day. Then the announcer return is their EW return, and all of them count as announcers.
- **Peers:** universe companies in the same sector whose own publication for that period comes after t0 + 10 trading days. At least 2 are needed.
- **Returns,** as market-adjusted returns against the EW return of the whole liquid universe that day:
  - AR_ann = the announcers' return over [0, +1];
  - AR_peer,0 = the peers' EW return over [0, +1];
  - AR_peer,drift = the peers' EW return over [+2, +10].
- **Regressions across events,** with standard errors clustered by calendar quarter:
  - L2a: AR_peer,0 = a + b · AR_ann. Expected b > 0.
  - L2b: AR_peer,drift = a + b · AR_ann. Expected b > 0.

## Pass rule (each of L1, L2a, L2b)

There are 3 tests:
1. Discovery: expected sign, t > 3.0 (Harvey-Liu-Zhu; above Bonferroni ≈ 2.39 for 3 tests).
2. Holdout: same sign, t > 2.0.

## What goes live

- **L1 or L2b passes:** it is documented, and a follow-up pre-registration tests a concrete trading rule with costs (the weekly rule turns over a lot). Nothing changes live from this test alone.
- **L2a passes:** this is information only. It describes how news travels within a sector, and nothing goes live.

## Known limits

- **Non-synchronous trading:** stale prices in small stocks can create spurious lead-lag at daily frequency. Weekly returns reduce this but do not remove it. A pass in L1 that disappears after a further one-day skip would point to stale prices. This is reported as a sensitivity.
- **Sector labels** are one current classification and are applied to the whole history.
- **Survivorship**, as in all studies here.
