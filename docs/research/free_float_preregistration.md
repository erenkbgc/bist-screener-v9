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

Added 2026-11-22, after the run (the pre-registered sections above are unchanged). Runner: `.venv/bin/python scripts/research_free_float.py` → `data/reports/research_free_float_2026-11-22.json`. Panel: `data/research/fp/factors_monthly.parquet` (2013-04 to 2026-09; 93 discovery months, 68 holdout months with full next-month returns, 40,693 liquid stock-months).

### Descriptive

- `ff_mcap` (`HAO_PD`) coverage in the liquid `value_sn` universe: **93.1%** overall (89.2% discovery, 97.0% holdout). Median free-float market cap: 125.2M TL (p10 19.8M TL) in discovery; 1,813.0M TL (p10 371.6M TL) in holdout.
- `FF1` excludes **9.5%** of liquid stock-months (9.1% discovery, 9.8% holdout), and **7.3%** of `P0`'s top-20% holdings (7.8% discovery, 6.6% holdout). Average held names drop from 42.7 → 38.8 in discovery and 59.2 → 53.4 in holdout; monthly overlap `|P0 ∩ FF1| / |P0|` is **89.9%** (Jaccard 89.3%).
- Standalone monthly Spearman rank IC vs `fwd_ret_1m` (Newey-West t, 6 lags):
  - `log(ff_mcap)`: discovery **−0.0077** (t −0.38, 93 mo), holdout **+0.0481** (t +2.53, 68 mo).
  - Free-float ratio (`ff_mcap / mcap`): discovery **−0.0099** (t −1.21, 93 mo), holdout **−0.0344** (t −2.28, 68 mo).

### Primary test (`data/research/fp/factors_monthly.parquet`, 1M TL, base costs, next-close fills)

Baseline `P0` matches `first_published_panel.md` exactly (+4.37%/yr t 1.67 discovery; +9.36%/yr t 2.74 holdout; USD max DD −56.6% / −35.4%).

| Window | P0 active %/yr (t) | FF1 active %/yr (t) | Paired D %/yr (t) | USD paired D %/yr (t) | USD CAGR P0 / FF1 | USD max DD P0 / FF1 | Cost %/yr P0 / FF1 | Turnover P0 / FF1 | Avg names P0 / FF1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Discovery (93 mo) | +4.37 (1.67) | +4.87 (1.75) | **+0.50 (0.69)** | +0.52 (0.73) | 12.26% / 12.88% | −56.6% / −56.4% | 1.92% / 1.73% | 21.4% / 20.5% | 42.7 / 38.8 |
| Holdout (68 mo) | +9.36 (2.74) | +8.07 (2.20) | **−1.29 (−1.73)** | −1.31 (−1.85) | 7.02% / 5.68% | −35.4% / −35.2% | 1.42% / 1.34% | 19.3% / 18.8% | 59.2 / 53.4 |

Against the costed equal-weighted universe (`B2`, 1M TL base costs): `P0` +5.14%/yr (t 1.97) discovery, +10.14%/yr (t 2.97) holdout; `FF1` +5.64%/yr (t 2.03) discovery, +8.84%/yr (t 2.41) holdout.

### Pre-registered decision check (D3)

| Criterion | Threshold | Observed | Status |
|---|---|---:|---|
| Discovery paired `D` | > −1.00%/yr | +0.50%/yr | PASS |
| Discovery NW `t(D)` | > −2.00 | +0.69 | PASS |
| Holdout paired `D` | > −1.00%/yr | **−1.29%/yr** | **FAIL** |
| Holdout NW `t(D)` | > −2.00 | −1.73 | PASS |
| Holdout USD max DD vs P0 | ≥ P0 − 2.0 pp (−37.4%) | −35.2% (+0.2 pp) | PASS |

### Verdict: `FAIL`

`FF1` fails the pre-registered holdout return bound (`D = −1.29%/yr` vs `> −1.00%/yr` required, missing by 0.29 pp), while passing the discovery bound (+0.50%/yr), both t-statistic bounds, and the holdout USD drawdown bound (+0.2 pp better). Live rule `R0-2026-10-12` stays unchanged (`config/live_rule.json` untouched). Free-float market value remains information-only.

### Descriptive sensitivities (do not change the verdict)

**Capital, cost multiplier, and fill timing (`data/research/fp/factors_monthly.parquet`):**

| Scenario | Discovery D %/yr (t) | Holdout D %/yr (t) | Holdout USD max DD P0 / FF1 | Cost/yr holdout P0 / FF1 | D3 check |
|---|---:|---:|---:|---:|---|
| 100k TL, base | +0.45 (0.63) | −1.30 (−1.74) | −35.3% / −35.2% | 1.32% / 1.24% | FAIL |
| 1M TL, base (primary) | +0.50 (0.69) | −1.29 (−1.73) | −35.4% / −35.2% | 1.42% / 1.34% | **FAIL** |
| 1M TL, stress 2× | +0.70 (0.96) | −1.20 (−1.60) | −35.9% / −35.6% | 2.85% / 2.67% | FAIL |
| 1M TL, stress 3× | +0.90 (1.23) | −1.10 (−1.47) | −36.4% / −36.1% | 4.27% / 4.01% | FAIL |
| 1M TL, next-open | +0.55 (0.71) | −1.44 (−1.74) | −35.3% / −35.4% | 1.42% / 1.34% | FAIL |
| 10M TL, base | +0.64 (0.88) | −1.27 (−1.70) | −35.5% / −35.3% | 1.76% / 1.65% | FAIL |
| 10M TL, stress 2× | +0.98 (1.33) | −1.15 (−1.54) | −36.1% / −35.9% | 3.52% / 3.30% | FAIL |
| 100M TL, base | +1.09 (1.45) | −1.20 (−1.61) | −35.9% / −35.7% | 2.82% / 2.65% | FAIL |
| 100M TL, stress 2× | +1.87 (2.36) | −1.00 (−1.34) | −36.9% / −36.6% | 5.65% / 5.29% | FAIL |

Across every capital and cost cell on the lag-75/100 panel, `FF1` slightly improves discovery returns (+0.45% to +1.87%/yr) and reduces annual trading costs (by 0.08–0.19%/yr at 1M TL and up to 1.55%/yr at 100M TL 2×; >10%-ADV fills in discovery drop from 16.0% to 14.0% at 100M TL), yet consistently costs 1.00–1.44%/yr in holdout.

**Actual KAP publication dates (`data/research/fp/factors_monthly_kapdates.parquet`, 1M TL, base costs, next-close fills):**

| Window | P0 active %/yr (t) | FF1 active %/yr (t) | Paired D %/yr (t) | USD max DD P0 / FF1 | D3 check |
|---|---:|---:|---:|---:|---|
| Discovery (93 mo) | +6.47 (2.37) | +6.72 (2.46) | +0.25 (0.37) | −56.0% / −55.6% | — |
| Holdout (68 mo) | +7.61 (2.53) | +8.30 (2.34) | +0.70 (0.77) | −35.5% / −33.6% | PASS (sensitivity only) |

### How to read it

1. **Much cheaper than size or liquidity floors, but still fails its pre-registered bound.** Unlike `F1` (bottom 30% market cap, −8.83%/yr discovery) and `F2` (50% liquidity cut, −3.75%/yr holdout), dropping the bottom decile of free-float market value is nearly neutral overall (+0.50%/yr discovery, −1.29%/yr holdout) and trims trading costs by ~0.1–0.2%/yr at 1M TL. However, it misses the pre-registered −1.00%/yr holdout floor on the primary lag-75/100 baseline.
2. **Publication-date sensitivity:** On the KAP-date version of the same `data/research/fp/` panel, `FF1` turns slightly positive in holdout (+0.70%/yr, t 0.77, USD max DD improved by 1.9 pp). Because lag-75/100 was locked as the primary baseline before running, the official verdict stays **`FAIL`** — switching panels post-hoc is not allowed.
3. **Practical takeaway:** `value_sn` already underweights the bottom free-float decile slightly (7.3% of `P0` holdings vs 9.5% of the liquid universe). Live rule `R0-2026-10-12` stays unchanged; free-float market value remains an information field so users can judge manipulation risk themselves.

