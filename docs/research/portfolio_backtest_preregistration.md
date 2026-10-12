# Live rule portfolio backtest: pre-registration

Written on 2026-10-12, **before** the simulation below was built or run. The rules, cost model, scenarios, metrics and decision rules are fixed here. They are not changed after the results are seen. A changed rule or parameter counts as a new test and needs a new pre-registration.

## Question

The factor tests (`backtest_factor_model.py`) and the rotation test (`exit_rules_preregistration.md`) show that the value_sn top quintile ranked stocks. They do not show what an investor would have earned. Those tests:
- traded at the decision-day close;
- charged a flat 20 bps on traded weight, whatever the stock's liquidity or the trade size;
- compared only with the equal-weighted liquid universe.

This test answers three questions:
1. **Execution:** does the live rule R0 keep a positive net active return when it trades at the next close and pays costs that depend on liquidity and trade size?
2. **Capacity:** how fast does the result decay as capital grows?
3. **Size and liquidity filters:** does a stricter size or liquidity floor cost return? The motivation is manipulation risk in small, thin stocks (for example SANEL: about 474M TL free-float market value, 14M TL a day). A backtest cannot measure manipulation risk. It can only measure what the filter costs.

## Prior exposure, stated honestly

- The 2021+ holdout has been looked at in every earlier pre-registration. It is **not** a clean holdout. It is reported, but the decisive evidence for the live rule is the forward record that starts with the 2026-11 rebalance (section "Forward record").
- R0's gross result is known: discovery +10.64%/yr, holdout +5.67%/yr at 20 bps (`exit_rules_preregistration.md`).

## Data

- Monthly panel, universe and ranking: exactly base B in `long_term_preregistration.md` (`research_long_term.load()`, value_sn rank within the monthly liquid universe; bottom 30% by 60-day median TL volume dropped; financials excluded).
- Daily adjusted Open/High/Low/Close and raw Close × Volume from `data/research/raw/*.pkl`.
- XU100 and USDTRY daily from `fx.parquet`. XU100 is a **price** index; it has no dividends, so the active return against it is biased in the strategy's favour by the index dividend yield. This is reported, not corrected.
- Policy rate and monthly CPI from `macro_monthly.parquet`. The policy rate is the deposit proxy. Before 2018 the effective funding rate often differed from the policy rate. This is reported, not corrected.
- **Discovery:** decisions 2013-01 to 2020-12. **Holdout:** 2021-01 to the end of the data.

Free-float history is not available, so free-float market value cannot be tested point-in-time. Using today's free float on past months would add look-ahead bias. Total market value and 60-day median TL volume are the point-in-time proxies.

## Simulation

**Decision.** At each month-end t, the target list is the top 20% of value_sn in the month-t universe (rule R0), equal-weighted.

**Execution.** Trades fill at the close of the first trading day after d0, where d0 is the last trading day ≤ t. Sensitivity: the open of that day.

**Daily book.**
- Positions drift with the daily adjusted close. Cash earns the daily policy rate.
- At a rebalance, the book trades to equal weights of the new list. Sells and buys of names that stay in the list are included (they restore equal weight).
- A name with no price on the fill day is not bought; its weight stays in cash until the next rebalance.
- A held name with no price is carried at its last close.
- **Delisting:** a held name with no price for 20 consecutive trading days while XU100 trades is closed at its last close × (1 − h). Main case h = 0. Sensitivity h = 0.5. The delisting date is the last day with a price.

**Costs** (one way, on the TL value traded):
- Commission: 10 bps.
- Half-spread, by the name's 60-day median TL volume percentile within that month's liquid universe: top third 5 bps, middle third 15 bps, bottom third 30 bps.
- Market impact, square-root model: impact = 1.0 × σ_d × √(Q / ADV). σ_d is the 60-day daily return volatility. ADV is the 60-day median TL volume. Q is the TL value traded in the name on the fill day. The impact is capped at 10%.
- Cost scenarios: base (as above) and stress (2 × each component).

**Capital.** Starting capital in 2026-09 TL: 100k, 1M, 10M and 100M TL. Earlier capital is the same real amount, deflated by monthly CPI. Each level is a separate simulation. Main case: 1M TL.

**Participation.** The share of fills with Q > 10% of ADV is reported for each capital level. Fills are not split across days.

## Variants

| ID | Rule |
|---|---|
| P0 (live rule) | R0 as above. |
| F1 | P0, plus names in the bottom 30% of month-t market value within the liquid universe are removed before the quintile is formed. |
| F2 | P0, but the liquidity cut is the bottom 50% instead of 30%. |

F1 and F2 change the universe and then re-rank. They are compared with P0 at the same capital level and cost scenario.

## Metrics

For each variant, capital level, cost scenario and period:
- net CAGR in TL, USD and real TL (CPI-deflated);
- net active return per year against (a) the equal-weighted liquid universe, (b) XU100 and (c) the deposit proxy, with Newey-West t (6 lags);
- information ratio against XU100;
- Sharpe and Sortino of the excess over the deposit proxy;
- maximum drawdown and the longest time to recover a previous peak, in TL and USD;
- monthly turnover and annual cost drag, split into commission, spread and impact;
- share of fills above 10% of ADV;
- number of delisting events.

## Decision rules

**D1. Execution (P0, 1M TL, base costs, next-close fills).**
- If the net active return against the equal-weighted universe is ≤ 0 in the holdout, the bulletin states: "the edge is not established after realistic costs". The live rule stays as the most tested rule, but the bulletin's realised-return reference uses this simulation's net figures instead of the 20 bps figures.
- If it is > 0 with t > 2.0 in both periods, the bulletin may say "survives realistic costs in the backtest".
- Anything in between: the bulletin shows the net figures with no claim.

**D2. Capacity.** The largest capital level whose holdout net active return against the universe is at least half of the 100k TL level is reported as the indicative capacity. No live change follows from it.

**D3. Filters F1 and F2.** These are risk-control filters, not alpha signals. A filter goes live if **all** of the following hold at 1M TL with base costs:
- the difference D = net active(filter) − net active(P0) is > −1.0%/yr in both periods;
- the Newey-West t of D is > −2.0 in both periods;
- the holdout USD maximum drawdown is no worse than P0's by more than 2 percentage points.

If both pass, the one with the higher holdout D goes live. If neither passes, the live universe stays as tested and each live pick's market value and liquidity percentile are shown as information.

**D4. Survivorship.** If the main result changes sign under h = 0.5, the bulletin's net figures carry a "survivorship-sensitive" note.

## Forward record

From the 2026-11 rebalance onward, each live decision (date, list, fill-day prices) is stored with a timestamp and is never re-simulated under a new rule. Results from that series are the clean out-of-sample test. A rule change starts a new series.

## Known limits

- Survivorship: delisted stocks are mostly missing from the data, so delisting events are under-counted.
- The cost model is a fixed formula, not a fit to BIST trade data. Its constants are standard textbook values.
- The equal-weighted universe benchmark pays no costs.
- XU100 is a price index (see Data).
