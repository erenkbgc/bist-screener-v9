# Free-float market value filter on `value_sn` (P4-1): pre-registration

Written and committed on 2026-11-22, **before** the runner was written or executed on the panel. The rule, simulation settings, windows, and decision rule are fixed here and are not changed after seeing the results. A changed rule or cutoff counts as a new trial and requires a new pre-registration.

## Question

`portfolio_backtest_preregistration.md` (2026-10-12) noted manipulation risk in thin, low-float BIST stocks (such as SANEL) and tested two point-in-time proxies: excluding the bottom 30% of total market value (`F1`) and raising the liquidity cut from 30% to 50% (`F2`). Both failed. At that time, point-in-time free-float history was not available and could not be tested without look-ahead bias.

Point-in-time free-float market value (`HAO_PD` from İş Yatırım HisseTekil, stored as `ff_mcap` in `data/research/market_cap_monthly.parquet`) now exists (`market_cap_source.md`). A small free-float market value can occur even in a mid-cap stock when the controlling shareholder holds 85–95% of shares; conversely, a smaller company with high free float may have a larger tradeable float.

As in `F1` and `F2`, a historical backtest cannot price manipulation risk. It can only measure what a free-float filter costs or adds relative to the live rule `R0` (`P0`) after realistic next-close execution and liquidity-dependent transaction costs.

## Prior exposure, stated honestly

- The 2021+ holdout has been inspected in every earlier study on this panel. It is **not** a clean holdout; the forward record (`data/forward_record/decisions.jsonl`) is the decisive out-of-sample test.
- Baseline `P0` performance on the new point-in-time panel (`data/research/fp/`, `first_published_panel.md`) is already known: at 1M TL with base costs and next-close fills, net active vs the equal-weighted liquid universe is +4.37%/yr (t 1.67) in discovery (2013–2020) and +9.36%/yr (t 2.74) in holdout (2021–2026), with holdout USD max drawdown −35.4%.
- The earlier size (`F1`: −8.83%/yr discovery, −1.10%/yr holdout) and stricter liquidity (`F2`: −3.03%/yr discovery, −3.75%/yr holdout) filters failed on the pre-correction panel (`portfolio_backtest_preregistration.md`).
- A non-return coverage check of `data/research/market_cap_monthly.parquet` joined to the liquid universe (`tlvol60` top 70%, 2013-04 to 2026-09) was performed **without reading any return column**: `ff_mcap` is non-null and strictly positive for 93.1% of liquid stock-months (89.2% in discovery, 97.0% in holdout, 99.5% in 2026), with 0 zero, negative, or `> mcap` values. The missing 6.9% (2,797 stock-months across 51 tickers) come from the 9 tickers absent from HisseTekil and ~48 tickers (including renamed symbols such as `TRALT`, `TRENJ`, `TRMET`, `OYAKC`) where İş Yatırım lacks earlier `HAO_PD` history.
- No return, rank IC, or portfolio result of `ff_mcap` or the free-float filter has been computed before this document was committed.

## Data and universe

- **Panel:** the point-in-time research baseline `data/research/fp/factors_monthly.parquet` (lag-75/100 availability, C1 constant-unit TTM, vendor IAS 29 re-expression undone, İş Yatırım `PD` market value; `first_published_panel.md`).
- **Universe and ranking:** identical to `scripts/research_portfolio_backtest.py` (`research_long_term.load()` reading `data/research/fp/factors_monthly.parquet`): non-financial stocks, bottom 30% by `tlvol60` dropped each month (`factor_backtest.prepare(..., liq_drop_pct=0.3, min_names=30)`), `value_sn_z` demeaned within sector, restricted to rows with `value_sn_z.notna()`.
- **Free-float market value:** `ff_mcap` (`HAO_PD`, in TL) from `data/research/market_cap_monthly.parquet` (last trading day of each calendar month, month-end aligned), left-joined on `(date, ticker)`.
- **Daily execution, FX, and macro inputs:** identical to `scripts/research_portfolio_backtest.py` (`data/research/raw/*.pkl` for adjusted Open/Close and raw Close × Volume, `fx.parquet` for XU100 and USDTRY, `macro_monthly.parquet` for TCMB policy rate and monthly CPI).
- **Windows:**
  - **Discovery:** decision months `2013-04` to `2020-12` (`date < 2021-01-01`).
  - **Holdout:** decision months `2021-01` to the last month with a full next-month return (`date >= 2021-01-01`, ending `2026-08`).

## Simulation and costs

Identical to `portfolio_backtest_preregistration.md` (`core/portfolio_backtest.py::simulate`):

- **Execution:** monthly rebalance at the close of the first trading day after `d0` (the last trading day ≤ month-end `t`).
- **Daily book:** positions drift with adjusted close; cash earns the daily TCMB policy rate; names with no fill-day price are not bought (weight stays in cash); delisting haircut `h = 0`.
- **Costs (one-way, on TL value traded):**
  - Commission: 10 bps.
  - Half-spread: 5 / 15 / 30 bps by the stock's `ADV` percentile within the **unfiltered** month-`t` liquid universe (`universe_liq`).
  - Square-root impact: `1.0 × σ_d × √(Q / ADV)`, capped at 10%.
- **Main specification (used for the decision rule):** 1M TL starting capital (2026-09 TL, deflated by monthly CPI), base costs (`mult = 1.0`), next-close fills, `h = 0`.
- **Benchmark:** the **unfiltered** equal-weighted liquid universe (`bench = df.groupby("date")["fwd_ret_1m"].mean()`, identical to `research_portfolio_backtest.py`), so both `P0` and `FF1` share the exact same benchmark and their paired difference `D_t = active(FF1)_t − active(P0)_t` equals `port(FF1)_t − port(P0)_t`.

## Rule (one confirmatory trial)

| ID | Rule |
|---|---|
| `P0` (baseline) | Live rule R0 on `data/research/fp/`: top 20% (`rank(ascending=False, pct=True) <= 0.2`) of `value_sn_z` in the month-`t` liquid universe, equal-weighted. |
| `FF1` (confirmatory) | In each month `t`, compute `q10_t`, the 10th percentile of positive observed `ff_mcap` within the month-`t` liquid universe (`value_sn_z.notna()`). Exclude stocks with observed `ff_mcap > 0` and `ff_mcap < q10_t`. Stocks with missing `ff_mcap` (`NaN`) are **not** excluded (missing vendor data never triggers an exclusion, consistent with `st_debt_coverage_preregistration.md` and `long_term_research.py::flags`). Form the top 20% of the remaining candidates by `value_sn_z` (`rank(ascending=False, pct=True) <= 0.2`), equal-weighted. |

The re-ranking construction (filter the month-`t` liquid universe, then take the top 20% of remaining candidates by `value_sn_z`) is identical to `F1` in `scripts/research_portfolio_backtest.py`.

**Descriptive diagnostics only (cannot change the verdict):**
- `ff_mcap` coverage in discovery and holdout; share of liquid universe and share of `P0` top-20% holdings excluded by `FF1`; average portfolio overlap between `P0` and `FF1`.
- Standalone monthly Spearman rank IC of `log(ff_mcap)` and of free-float ratio (`ff_mcap / mcap`) against `fwd_ret_1m` (Newey-West t, 6 lags).
- Sensitivities: stress costs (2× and 3×), capital levels (100k, 10M, 100M TL), next-open fills, and KAP-date panel (`data/research/fp/factors_monthly_kapdates.parquet`) at 1M TL base costs.

## Decision rule

Identical to **D3** in `portfolio_backtest_preregistration.md` (`research_portfolio_backtest.py::d3_verdict`). `FF1` is a risk-control filter, not an alpha signal. At **1M TL, base costs, next-close fills** on `data/research/fp/`, `FF1` receives verdict **`PASS`** if and only if **all three** hold:

1. The annualised paired difference `D = net active(FF1) − net active(P0)` is **> −1.0%/yr** in **both** discovery (2013–2020) and holdout (2021+);
2. The Newey-West t-statistic (6 lags) of `D` is **> −2.0** in **both** discovery and holdout;
3. The holdout USD maximum drawdown of `FF1` is no worse than `P0`'s by more than 2.0 percentage points (`max_dd_usd_pct(FF1) >= max_dd_usd_pct(P0) - 2.0`).

Otherwise, the verdict is **`FAIL`**.

The trial ledger (`data/research/trial_ledger.json`) adds **1** new stock-selection trial (`FF1`), bringing `N_sel` from **86 to 87**.

## Live rule

No automatic live change. `config/live_rule.json` (`R0-2026-10-12`) and live scoring are not modified by this study. Even on `PASS`, adopting a free-float filter into the live rule requires a separate explicit version change and starts a new forward-record series. On `FAIL`, the live universe stays as tested and free-float market value remains information-only.

## Known limits

- Missing `ff_mcap` (6.9% of liquid stock-months, concentrated in earlier years and renamed tickers) is kept rather than dropped; if missing rows were disproportionately low-float, the filter's reach in discovery is slightly understated.
- Delisted stocks are absent from `data/research/fp/`, so survivorship bias is unchanged relative to `P0`.
- The cost model is a fixed formula (same as `portfolio_backtest_preregistration.md`), not fitted to BIST order-book fills; if very low-float stocks have higher real-world market impact than `ADV` alone captures, the backtest understates the execution benefit of removing them.

---

## Results

*(To be appended after the run; the sections above stay unchanged.)*
