# Phase 1 diagnostics: crashed stocks, currency, survivorship

Date: 2026-10-10. Data: point-in-time panel `data/research/factors_monthly.parquet`, 2013-04 .. 2026-09, 514 non-financial tickers, bottom 30% by liquidity dropped each month. These are descriptive diagnostics, not pre-registered tests. They do not change live scoring. Formal tests are in the Phase 2 pre-registration.

## 1. Do crashed stocks reach the top of the list?

Script: `scripts/diagnose_crashed_picks.py`. "Crashed" means the month-end adjusted close is at least 70% below its trailing 60-month peak. At least 36 months of history are required. The score proxy is the same as in `backtest_factor_model.py` (valuation, momentum and low-vol weights from `weights.yaml`).

| Group | Crashed share |
|---|---|
| Universe, all months | 4.6% |
| Proxy top quintile | 3.2% |
| Proxy top 4, all months | 2.0% |
| Proxy top 4, since 2023 | 1.7% (3 picks: MEGAP twice, KZBGY) |

The historical proxy does not over-select crashed stocks. The live model does. Live DB long-term predictions from 2026-09-11 to 2026-09-27 were classified by drawdown at the last panel month:
- 4 of 26 STRONG_OPPORTUNITY tickers were crashed: VRGYO, TEKTU, ADESE, DUNYH.
- 11 of 92 WATCHLIST tickers were crashed.

So the user's observation is real for the live model, which differs from the proxy. The live model uses a 273-day price window, sector-peer valuation and target and hurdle gates.

Next 6 months after selection, measured as the mean of monthly group means, with Newey-West t at 6 lags:

| Group | n | USD return mean / median | Excess over XU100 mean / median (NW t) | Excess below −30% |
|---|---|---|---|---|
| Top quintile, crashed | 200 | +26.7% / +11.8% | +23.6% / +9.9% (t 2.11) | 7.5% |
| Top quintile, not crashed | 6414 | +13.5% / −1.0% | +12.8% / −1.6% (t 2.79) | 10.6% |
| Universe, crashed | 1324 | +5.8% / −0.3% | +3.5% / −2.4% (t 0.66) | 14.4% |
| Universe, not crashed | 29344 | +8.2% / −4.1% | +7.4% / −4.3% (t 1.91) | 16.3% |

In surviving stocks, a crash alone is not a bad sign once the value score is high. This is also the group most inflated by survivorship (section 3). The result does not justify either a hard exclusion or a bonus. It goes to Phase 2 as hypothesis H2 (drawdown × quality).

## 2. Currency

Script: `scripts/backtest_factor_model.py --currency tl|usd|xs`. Daily USDTRY and XU100 come from `scripts/build_fx_panel.py`.

Rank IC and Fama-MacBeth t-stats are identical in TL, USD and XU100-excess terms:
- value IC1 t 7.15;
- vol60 t 7.25;
- sue t 5.63.

Top-quintile net active return changes by less than 0.1 pp per year. This is expected, because each month all stocks share the same FX and index move. The cross-sectional factor evidence is not a nominal-TL artifact. Absolute return levels still are: XU100 returned +0.8% per year in USD over 2005–2026 (`macro_drivers_preregistration.md`).

## 3. Survivorship

Delisted price history is not available. borsapy and TradingView return "invalid symbol" for MUTLU, TEB and ASYAB. The 14-row list in `core/data_quality.py` is hand-entered and unverified, so it is not used.

Script: `scripts/survivorship_sensitivity.py`, which follows Shumway (1997). It adds phantom delistings:
- Universe annual hazard is h, and the top quintile has hazard k·h.
- A delisting returns R: −30% for a typical performance delisting, −100% for a full loss.

The table shows the smallest annual universe h at which the top-quintile net active return (20 bps cost) falls below each threshold:

| Signal | No-bias active / t | R=−30%, k=2: t<3 / mean<0 | R=−100%, k=2: t<3 / mean<0 | R=−100%, k=3: t<3 / mean<0 |
|---|---|---|---|---|
| value | +8.76%/yr, t 3.81 | 5.75% / 25.75% | 2.0% / 8.5% | 1.0% / 4.25% |
| value_sn | +9.10%/yr, t 4.05 | 7.25% / 26.5% | 2.5% / 8.75% | 1.25% / 4.5% |
| model_proxy | +6.15%/yr, t 2.66 | (already <3) / 18.25% | (already <3) / 6.0% | (already <3) / 3.0% |
| sue | +5.10%/yr, t 2.07 | (already <3) / 15.0% | (already <3) / 5.0% | (already <3) / 2.5% |
| vol60 | −2.54%/yr, t −0.86 | negative before any adjustment | | |

The crashed top-quintile subgroup averages about 2.4 names per month and has mean active +9.7%/yr (value) with t 0.96. Under full loss, its mean turns negative at h = 2.5% with k=5, and at h = 1.25% with k=10.

Reading:
- The value premium's sign is robust. Its significance against the HLZ threshold is fragile: with full-loss delistings concentrated 3× in value stocks, a 1% universe rate removes it.
- The crashed subgroup is the most exposed. No verified BIST delisting count is available; a web search found only individual cases. The break-even rates should be checked against an official Borsa Istanbul or KAP delisting count before any live rule relies on the crashed-stock result.
- Low-vol has strong IC but no top-quintile edge after cost. Its signal sits in the bottom quintile (high-vol losers), which matches its role as an exclusion filter rather than a buy signal.

## Consequences for Phase 2

- H1 distress and H2 drawdown × quality must be tested with the survivorship sensitivity above. Report h break-even next to each result.
- The live model selects crashed names more often than the proxy. Phase 2 should first make the live score match the tested proxy, so the evidence applies to what is shown.
- Low-vol: test as an exclusion of the top-volatility quintile, not as a positive weight.
