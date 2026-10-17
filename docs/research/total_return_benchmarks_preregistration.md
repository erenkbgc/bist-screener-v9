# Total-return and investable benchmarks: pre-registration

Written and committed on 2026-10-17, **before** the benchmark series were joined to the strategy or any active return against them was computed. The benchmarks, cost treatment, windows, metrics and labels are fixed here. They are not changed after the results are seen.

## Question

The portfolio backtest (`portfolio_backtest_preregistration.md`, PR #43) compares the live rule R0 with two benchmarks:
- the equal-weighted liquid universe, at **zero** cost, while the strategy pays the full cost model;
- XU100, a **price** index without dividends.

Both comparisons are tilted. The first understates what a real equal-weight investor pays. The second favours the strategy by the index dividend yield. An external review (2026-10-17) asked for three benchmarks, each answering a different question:

| Benchmark | Question |
|---|---|
| Equal-weighted investable universe, same cost model | Does the rule beat its own universe for an investor who pays the same costs? |
| BIST 100 total return | Does it beat the large, liquid market? |
| BIST All Shares total return | Does it add anything beyond tilting towards small and mid caps? |

This is a reporting test. It does not select a rule. **The live rule does not change whatever the result.** The result decides only which numbers the README headline and the bulletin use to describe the rule.

## What was looked at before this file was written

- borsapy (TradingView) returns `XU100_CFNNTLTL` and `XUTUM_CFNNTLTL` daily from 2018-07-16. Only the index levels were compared with the price indices XU100 and XUTUM. `XU100_CFNNTLTL / XU100` grows by 1.4–3.4% a year (2019–2026). That matches a dividend-reinvested total-return index. No strategy return was joined to these series.
- The strategy's results against the zero-cost universe and XU100 price are known from PR #43: holdout +0.75%/yr against XU100 price, t 0.13.

## Strategy

The main specification of `portfolio_backtest_preregistration.md`, unchanged:
- R0 (value_sn top 20%, equal weight, monthly) on the base panel `research_long_term.load()`;
- 1M TL capital in 2026-09 money, scaled by CPI;
- base cost scenario, fills at the next trading day's close, delisting haircut 0;
- cash earns the policy rate.

## Benchmarks

All benchmark returns are measured over the same windows as the strategy: from d0 (last trading day ≤ month-end t) to d0 of the next decision month.

- **B1, EW universe, zero cost.** As in PR #43, the mean `fwd_ret_1m` of the monthly universe. Reported for continuity.
- **B2, EW investable universe.** The same simulator (`portfolio_backtest.simulate`) and settings as the strategy. The target list each month is **every** name in the month's ranking universe, equal-weighted: same capital, same base cost model, same fills, same cash rate. Turnover comes from names entering or leaving the universe and from restoring equal weight.
- **B3, BIST 100 total return** (`XU100_CFNNTLTL`). No cost: an index fund or futures position costs little against the strategy's costs. This favours the benchmark slightly. That is stated, not corrected.
- **B4, BIST All Shares total return** (`XUTUM_CFNNTLTL`). No cost, same reason.
- XU100 price is kept as a column for continuity.

## Windows

- **Holdout:** decisions 2021-01 to the end of the data. This is the decision window for all four benchmarks.
- **Early:** decisions 2018-08 to 2020-12, the part of discovery where B3 and B4 exist. Information only, because of the short length.
- B1 and B2 are also reported for the full discovery window 2013–2020.

## Metrics

For each benchmark and window:
- net active return per year (12 × monthly mean) and Newey-West t with 6 lags;
- tracking error and information ratio;
- CAGR of the strategy and of the benchmark.

B2 also reports its own cost per year and turnover. The B4 − B3 return difference is also reported, as information on the size tilt of the market itself.

## Labels (fixed)

For each benchmark, in the holdout:
- **BEATS:** net active > 0 and NW t > 2.
- **AHEAD_NOT_SIGNIFICANT:** net active > 0 and t ≤ 2.
- **BEHIND:** net active ≤ 0.

What the labels change:
- The README status line and the realistic-return reference cite B2 and B3 holdout numbers with their labels. B1 and XU100 price stay in the tables with a note on their bias.
- If B2 is BEHIND, the README must say that the rule's edge over its universe disappears once the universe is costed the same way.
- No result changes the live rule, its parameters or its version. A rule change would need its own pre-registration.

## Known limits

- The 2021+ holdout has been seen in every earlier study. It is not clean. The forward record from 2026-11 is the clean test.
- The panel lacks most delisted stocks (`survivorship_delisted_preregistration.md`). That biases the strategy and B1/B2 alike. B3 and B4 are free of it.
- The total-return index series come from one source (TradingView via borsapy). They are not checked against Borsa İstanbul's own files.

## Results (added 2026-10-17, after the run; the sections above are unchanged)

Run: `python scripts/research_total_return_benchmarks.py`. Output: `data/reports/research_total_return_benchmarks_2026-10-17.json`. Index cache: `data/research/tr_indices.parquet`.

The strategy reproduces PR #43 exactly: against B1, holdout +5.83%/yr (t 2.11) and discovery +9.81%/yr.

**Holdout 2021-01 → 2026-08, 68 months**, strategy net of costs, NW t with 6 lags:

| Benchmark | Active %/yr (t) | Tracking error | IR | CAGR strategy vs benchmark | Label |
|---|---|---|---|---|---|
| B1 EW universe, zero cost | +5.83 (2.11) | 8.0% | 0.73 | 44.5% vs 36.9% | BEATS |
| **B2 EW universe, same costs** | **+6.60 (2.37)** | 8.0% | 0.82 | 44.5% vs 35.9% | **BEATS** |
| **B3 BIST 100 total return** | **−2.00 (−0.33)** | 13.6% | −0.15 | 44.5% vs 48.6% | **BEHIND** |
| B4 BIST All Shares total return | −2.40 (−0.50) | 10.8% | −0.22 | 44.5% vs 49.2% | BEHIND |
| XU100 price (continuity) | +0.75 (0.13) | 13.5% | 0.06 | 44.5% vs 44.7% | AHEAD_NOT_SIGNIFICANT |

- B2 costs 0.75%/yr at 9.3% monthly turnover (298 names on average). It ends below B1, so the edge over the universe grows slightly once the universe is costed the same way.
- B4 − B3: +0.40%/yr (t 0.20). In the holdout the broad market did not beat the large caps.

**Early window 2018-08 → 2020-12** (29 months, information only): the strategy beat all benchmarks. It was +17.1%/yr against B2 (t 1.86) and +64.1%/yr against B3 (t 2.68), at a CAGR of 120.6%. In this window the equal-weighted small and mid-cap universe itself compounded at about 91–93% a year, against 24% for BIST 100 total return.

### Reading

- The rule picks well **within its universe**. After the same costs, it beats the equal-weighted universe by about 6.6%/yr in the holdout (t 2.37).
- The universe itself trailed the market. In the holdout, the costed equal-weighted universe compounded at 35.9% a year, against 48.6% for BIST 100 total return. The universe is equal-weighted and excludes financials. BIST 100 is cap-weighted and bank-heavy. The universe gap is larger than the rule's edge, so **an investor in the rule would have done about 2%/yr worse than a BIST 100 total-return fund**, with 13.6% tracking error. The difference is not significant.
- Dividends matter. Against XU100 price the rule looked level (+0.75%/yr); against the total-return index it is behind.
- The 2018–2020 window is dominated by the 2020 small-cap boom. It says little about the rule.

### Decision (as fixed above)

- Labels: B2 **BEATS**, B3 **BEHIND**.
- The README status line and the realistic-return section now cite B2 and B3. B1 and XU100 price stay in the tables, with a note on their bias.
- Live rule unchanged. Whether to also hold banks or large caps is a different strategy question. It would need its own pre-registration.
