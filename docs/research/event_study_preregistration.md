# Elections, domestic shocks and regional conflicts: pre-registration

Written and committed on 2026-10-12, **before** any event window below was computed. The event list, event days, windows, tests and pass rules are fixed here. They are not changed after the results are seen. Adding or removing an event, or changing a window, counts as a new test and needs a new pre-registration.

## Question

How did BIST react to scheduled elections, unscheduled domestic shocks and regional conflicts? Two questions can be acted on:
1. **Elections (scheduled).** Their dates are known in advance. Was it better to hold cash around them than to stay invested?
2. **Shocks (unscheduled).** They cannot be traded in advance. After the shock day, did the market recover (buy the dip) or keep falling?

Everything else is descriptive.

## Prior exposure, stated honestly

These events are well known. The broad outcome of several of them is known before this test, for example the August 2018 lira crash and the 2016 coup attempt. Event selection is therefore not blind. To limit the damage:
- the list covers every national election in the sample, not a chosen subset;
- shocks are included by a fixed definition (below), not by their market reaction;
- the pass rule uses only the sign and size across all events of a group.

Power is low: 11 elections and 16 shocks. A FAIL means no evidence, not evidence of no effect.

The earlier macro study (`macro_drivers_preregistration.md`, PR #23) found that EM beta is the only reliable driver of BIST in USD and that the direction is not predictable. That is the prior.

## Data

- XU100 daily close and USDTRY daily from `fx.parquet` (2011-01 to 2026-10).
- EEM daily adjusted close from yfinance (`EEM`), the global EM factor.
- Policy rate from `macro_monthly.parquet`, used as the TL deposit proxy.
- Value portfolio: the top quintile of value_sn at the last month-end before the event day, from base B in `long_term_preregistration.md`. Daily adjusted closes come from `data/research/raw/*.pkl`; the EW liquid universe of the same month is the comparison.

## Events

**Event day t0** = the first BIST trading day on or after the listed date. Each listed date is a day on which the news was public before or during that day's session. A weekend or after-close event is listed on the next calendar day, so t0 is the next session.

**Inclusion rule for shocks:**
- a domestic political or economic event that made front-page international news; or
- a military event involving Turkey or a country bordering Turkey or Israel–Iran–US, with direct state action (an invasion, an air strike between states, an aircraft downing, a cross-border operation).

Terror attacks are excluded: they are too frequent to list without choosing.

| ID | Date listed | Event | Group |
|---|---|---|---|
| E1 | 2014-03-31 | Local elections (Sunday 30.03) | election |
| E2 | 2014-08-11 | Presidential election (Sunday 10.08) | election |
| E3 | 2015-06-08 | General election (Sunday 07.06) | election |
| E4 | 2015-11-02 | Snap general election (Sunday 01.11) | election |
| E5 | 2017-04-17 | Constitutional referendum (Sunday 16.04) | election |
| E6 | 2018-06-25 | General and presidential election (Sunday 24.06) | election |
| E7 | 2019-04-01 | Local elections (Sunday 31.03) | election |
| E8 | 2019-06-24 | Istanbul re-run (Sunday 23.06) | election |
| E9 | 2023-05-15 | General election, first round (Sunday 14.05) | election |
| E10 | 2023-05-29 | Presidential run-off (Sunday 28.05) | election |
| E11 | 2024-04-01 | Local elections (Sunday 31.03) | election |
| D1 | 2013-06-03 | Gezi protests escalate (from Friday 31.05) | domestic |
| D2 | 2013-12-17 | 17 December corruption operation | domestic |
| D3 | 2016-07-18 | Coup attempt (Friday night 15.07) | domestic |
| D4 | 2018-08-10 | Lira crisis, US tariff doubling | domestic |
| D5 | 2021-03-22 | Central bank governor Ağbal dismissed (Saturday 20.03) | domestic |
| D6 | 2021-11-23 | Lira crash after the rate-cut speech (evening 22.11) | domestic |
| D7 | 2023-02-06 | Kahramanmaraş earthquakes | domestic |
| D8 | 2025-03-19 | İmamoğlu detained | domestic |
| G1 | 2015-11-24 | Turkey downs a Russian jet | geopolitical |
| G2 | 2019-10-09 | Operation Peace Spring (Syria) | geopolitical |
| G3 | 2020-01-03 | US kills Soleimani | geopolitical |
| G4 | 2022-02-24 | Russia invades Ukraine | geopolitical |
| G5 | 2023-10-09 | Hamas attack on Israel (Saturday 07.10) | geopolitical |
| G6 | 2024-04-15 | Iran's attack on Israel (Saturday night 13.04) | geopolitical |
| G7 | 2025-06-13 | Israel strikes Iran | geopolitical |
| G8 | 2025-06-23 | US strikes Iranian nuclear sites (Sunday 22.06) | geopolitical |

Shocks are D1–D8 and G1–G8 (16 events). E1–E11 are the 11 elections. Events after June 2025 are not listed, because the list was written from knowledge that ends there. Later events need a new pre-registration.

Overlapping windows: G7 and G8 are 6 trading days apart. Each is kept as listed; their overlap is reported.

## Measures

Days are BIST trading days relative to t0. "Window [a, b]" is the return from the close of day a−1 to the close of day b.

- **TL and USD returns** of XU100 (USD = XU100 / USDTRY).
- **Abnormal return (AR)** in USD against a market model on EEM, with Dimson (1979) correction for non-synchronous trading:
  - r_bist,usd = α + β0 · r_eem(t) + β1 · r_eem(t−1) + ε;
  - estimated on [−250, −31];
  - AR = r − α − (β0 + β1) · r_eem applied term by term;
  - CAR = sum of AR over the window.
- **Descriptive windows:** [−20, −1], [−5, −1], [0, 0], [0, +5], [0, +20], [0, +60].
- **Volatility ratio:** std of the daily USD return on [+1, +20] / std on [−60, −1].
- **Recovery:** trading days until the USD level first closes at or above its day −1 close. Censored at 250.
- **Value portfolio:** EW top-quintile value_sn return minus the EW liquid universe return, window [0, +20], in TL.

## Confirmatory tests

There are 3 tests. Each uses a one-sample t-test across events (df = N − 1). The Bonferroni threshold is two-sided p < 0.05 / 3 = 0.0167.

**H1, cash around elections (E1–E11).**
- Per event: X = XU100 TL return over [−5, +5] − TL deposit return over the same days. This is the gain from staying invested instead of holding cash.
- PASS "cash around elections" if mean X < 0, p < 0.0167 and X < 0 in at least 8 of 11 events.
- PASS "stay invested" if mean X > 0, p < 0.0167 and X > 0 in at least 8 of 11 events.

**H2a and H2b, buying after a shock (D1–D8, G1–G8).**
- Per event: Y = CAR in USD over [+2, +20] (H2a) and [+2, +60] (H2b). The position is bought at the close of day +1, the first close after the shock day is known.
- PASS "buy after shock" if mean Y > 0, p < 0.0167 and Y > 0 in at least 11 of 16 events.
- Labelled "continuation" if mean Y < 0, p < 0.0167 and Y < 0 in at least 11 of 16.

## What goes live

- If H1 passes either way, the bulletin shows an election-calendar note with the measured effect. No automatic trading is added: the live rule is a monthly rotation and stays unchanged.
- If H2a or H2b passes, the bulletin may show a "post-shock" note after a large one-day fall. The fall threshold must come from a separate pre-registration, because this test does not define one.
- If nothing passes, the event table is published in `docs/research/` as information. The bulletin says nothing about elections or conflicts.

## Known limits

- **Few events:** the t-test across 11 or 16 events has little power.
- **Non-synchronous trading:** BIST closes at 18:00 Istanbul time, before the US close. The Dimson term only partly corrects for this.
- **Global shocks:** a global shock moves EEM too, so the abnormal return can understate the total effect for G3–G8. TL and USD raw returns are reported next to the AR.
- **XU100 is a price index:** dividends are missing, which is small over 20–60 days.
- **Survivorship:** the value-portfolio measure has the same survivorship bias as the other studies.
