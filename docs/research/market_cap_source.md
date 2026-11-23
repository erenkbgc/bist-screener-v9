# Market value source for the research panel: borsapy's "raw" close is rights-adjusted (data audit)

Date: 2026-10-25. Not a test; no trial is added.

## Finding

The panel computed market value as borsapy's unadjusted close (`history(adjust=False)`) × shares. In 159 of 187 rights issues with an expected price drop of more than 5%, that "unadjusted" series shows no drop on the ex-date: it is back-adjusted for rights issues (it is not adjusted for bonus issues). So before every rights issue the panel price is the true price × the issue's adjustment factor.

Example, AKYHO: borsapy close = true close × 0.274 until 2019 and × 0.589 until 2024. The panel market value was 2.5–3.6× too low for about ten years, so the stock looked 2.5–3.6× cheaper on B/M, E/P and S/P. Because the adjustment comes from a **later** rights issue, this is look-ahead: future rights issuers looked cheap in the backtest. On the first 47 stocks fetched, 14% of stock-months had panel market value off by more than 1.5×.

Returns are not affected (the adjusted series handles rights issues correctly). TL volume is not affected either: borsapy's volume is adjusted inversely, so close × volume matches İş Yatırım's TL volume (KATMR 2025-03-03: 74.9M vs 75.7M TL).

## Source

İş Yatırım HisseTekil (`scripts/fetch_isyatirim_market_cap.py`), one call per stock for the full daily history from 2012:
- `HG_KAPANIS`: true unadjusted close; `SERMAYE`: paid-in capital, changing on the ex-date;
- `PD`: market value = HG_KAPANIS × SERMAYE;
- `HAO_PD`: free-float market value. This is the first point-in-time free-float history in the project. `portfolio_backtest_preregistration.md` said free float could not be tested.

622 of 631 stocks have history (no data: CITAS, DAGHL, INTEK, LRSHO, LYDHO, MARKA, METUR, PEHOL, SELGD). `market_cap_monthly.parquet` holds the last trading day of each month. `pit_panel.build_monthly_factors(market_caps=...)` uses `PD` when present and falls back to price × shares otherwise; the row set is unchanged.

The live score already used provider market value (TradingView). It agrees with İş Yatırım within 10% for all 617 stocks on 2026-10-24.

Effect on the value rule: `first_published_panel.md`.
