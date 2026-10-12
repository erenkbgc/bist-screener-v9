# Football sentiment and BIST: pre-registration

Written and committed on 2026-10-12, **before** any return was computed around a match. The data, event days, tests and pass rules are fixed here.

## Question

Does football mood move prices?

1. **F1, club stocks.** Galatasaray (GSRAY), Fenerbahçe (FENER), Beşiktaş (BJKAS) and Trabzonspor (TSPOR) are listed. Does each stock do better on the session after a league win than after a league loss? The literature finds this for listed clubs:
   - Palomino, Renneboog & Zhang (2009);
   - for Turkey, Berument, Ceylan & Gözpınar (2006).

   Part of the effect is cash-flow news (prize money, European places), and part is mood.
2. **F2, national team.** Does the whole market fall on the session after a competitive national-team loss? Edmans, García & Norli (2007) find this across 39 countries, with no matching effect after wins. That points to mood, not news.

## Data

- **Club league results:** football-data.co.uk, Turkish Süper Lig (`T1.csv`), seasons 2005/06 to 2026/27, columns Date, HomeTeam, AwayTeam, FTR. Team names: Galatasaray, Fenerbahce, Besiktas, Trabzonspor.
  - Turkish Cup and European matches are **not** included (no free consolidated source); this limit is reported.
  - This file must be downloaded outside the sandbox. If it is not available, F1 is not run and stays registered.
- **National team:** `martj42/international_results` (`results.csv`), Turkey's matches from 2005-01-01. Competitive only: World Cup and Euro qualifiers, World Cup, Euro and Nations League. Friendlies are excluded.
- **Prices:**
  - club stocks: daily adjusted closes from `data/research/raw/*.pkl`;
  - XU100 and USDTRY: from `fx.parquet` (borsapy calendar, 2011 onward), extended to 2005 with yfinance `XU100.IS` where needed;
  - EEM daily: `eem_daily.parquet`.

## Event day

The first BIST trading day **strictly after** the match date. Almost all matches end after the 18:00 close or fall on a weekend.

- F1: if a club has two matches mapped to the same event day, both are dropped.
- F2: matches are counted with their result after 90 or 120 minutes. A penalty shoot-out counts as a draw.

## Measures

- **F1:** the market-adjusted return of the club stock on the event day, AR = r_stock − r_XU100 (daily log returns, TL).
- **F2:** the USD abnormal return of XU100 on the event day, from the EEM market model with the Dimson correction (`core/event_study.py`, estimated on [−250, −31]).

## Tests

**F1.** D = mean AR after wins − mean AR after losses, pooled over the four clubs. The t is from Welch's two-sample test. Draws are reported, not tested.
- Discovery: matches before 2016-07-01. Holdout: after.
- PASS if D > 0 with t > 3.0 in discovery, and D > 0 with t > 2.0 in holdout.
- Each club is also reported on its own, descriptively.

**F2.** The mean AR after losses, with a one-sample t-test.
- Discovery: before 2016-01-01. Holdout: after.
- PASS if mean < 0 with t < −3.0 in discovery, and mean < 0 with t < −2.0 in holdout.
- Wins and draws are reported, not tested.

There are 2 tests, so the Harvey-Liu-Zhu threshold of 3.0 is above Bonferroni (about 2.24).

## What goes live

Nothing trades on this:
- the four club stocks are not part of a selection rule;
- a market-wide one-day effect cannot be acted on by a monthly rotation.

A pass is documented and shown in the bulletin as information only, for example "Milli maç yenilgisi: geçmişte ertesi gün piyasa ortalama X düştü".

## Known limits

- **F2 power:** about 40–50 competitive losses, so power is low.
- **Missing competitions:** European and cup matches are not included, although for the clubs they can matter more than league matches.
- **Overlapping news:** club stocks also react to transfers, debt and capital-increase news, which adds noise but no bias by result.
