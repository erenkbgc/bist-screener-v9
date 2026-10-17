# 2026 BIST factor study reconciliation: pre-registration

Written and committed on 2026-10-17, **before** the reconciliation script was run on the panel. The factor definitions, universe cuts, weighting schemes, windows, and interpretation rules are fixed here.

## Question

Gökçen (2026, *Borsa Istanbul Review*, "Factor Investing in the Turkish Equity Market") reports that in BIST:
- valuation is the strongest and most consistent factor,
- size, profitability, and momentum are significant in specific sample cuts or weighting schemes, and
- low-risk stocks outperform high-risk stocks.

In our earlier pre-registered tests on the liquid non-financial PIT panel (`backtest_factor_model.py`, `long_term_preregistration.md`), `value_sn` was strong, but:
- 12-1 momentum (`mom_12_1`) had near-zero cross-sectional Rank-IC (+0.007, $t = 0.7$) and negative top-quintile active return,
- gross profitability (`gpa`) did not improve `value_sn`, and
- low volatility (`vol60`) had a strong positive Rank-IC (+0.075, $t = 7.3$) because high-volatility stocks crashed, yet its long-only top quintile lagged the equal-weighted universe (−2.5%/yr) and adding `low_vol_z` as a positive linear weight diluted `value_sn`.

Before proposing any new composite or filter, this diagnostic/reconciliation study tests **why** those differences arise by systematically varying the four methodological choices that differ between academic BIST factor papers and an investable screener universe:
1. **Universe liquidity cut:** all non-financials (`liq_drop = 0.0`) vs our live liquid cut (`liq_drop = 0.30`) vs large/liquid half (`liq_drop = 0.50`).
2. **Portfolio weighting:** equal-weighted (`EW`) vs market-cap value-weighted (`VW`) quintiles, and long-short (`Q5 - Q1`) vs long-only active (`Q5 - Universe`).
3. **Alternative definitions within each factor family:**
   - **Size:** `-log(mcap)` across liquidity cuts (testing whether the size premium in BIST is confined to the illiquid bottom 30% microcap tier that an institutional/1M TL investor cannot trade cheaply).
   - **Profitability:** `GP/A` (`gpa`), `ROE` (`roe`), `ROA` (`ttm_ni / total_assets`), and operating profitability (`OP/A = ttm_ebit / total_assets`), tested both standalone and sector-neutralized, and controlling for `value_sn` in bivariate Fama-MacBeth regressions.
   - **Momentum:** `12-1` (`mom_12_1`) vs `6-1` (`mom_6_1`, 6-month return skipping the last month), evaluated across liquidity tiers and across Discovery (2013–2020) vs Holdout (2021–2026).
   - **Low risk (`vol60`):** asymmetry decomposition between the **long leg** (`Q5 - Universe`, buying the lowest-volatility 20%) and the **avoidance leg** (`Universe - Q1`, avoiding the highest-volatility 20%, and `Universe_ex_Q1 - Universe`), plus drawdown and volatility reduction.

## Data and windows

- C1 monthly panel (`data/research/factors_monthly.parquet`, `monthly_prices.parquet`, `quarterly_ext.parquet`, `fx.parquet`), 2013-04 to 2026-08 (161 months, 528 non-financial tickers).
- **Full sample:** 2013-04 to 2026-08.
- **Discovery:** 2013-04 to 2020-12 (93 months).
- **Holdout:** 2021-01 to 2026-08 (68 months).

## Hypotheses and diagnostic tests (fixed)

### R1. Size (`size = -mcap`): microcap illiquidity vs investable size effect
- Compute Rank-IC, EW `Q5 - Q1` spread, EW `Q5 - Universe` active return, and VW `Q5 - Q1` spread under three liquidity cuts: `liq_drop = 0.0` (all stocks), `0.30` (live universe), and `0.50` (liquid half), plus bivariate Fama-MacBeth slope of `size_z` controlling for `tlvol60` (log illiquidity/volume) and `value_sn_z`.
- **Question answered:** Does the BIST size premium survive once the least liquid 30% microcaps are excluded or when portfolios are value-weighted?

### R2. Profitability (`gpa`, `roe`, `roa`, `opa`): definition comparison
- Definitions (all point-in-time from the usable quarterly statement at month-end):
  - `gpa`: TTM gross profit / total assets (`factors_monthly.parquet`),
  - `roe`: TTM net income / book equity (`factors_monthly.parquet`),
  - `roa`: TTM net income / total assets (`statement_features`),
  - `opa`: TTM operating profit (EBIT) / total assets (`ttm_ebit / total_assets`).
- For each metric on the liquid universe (`liq_drop = 0.30`):
  - Standalone Rank-IC (1m), EW `Q5 - Q1` spread, EW `Q5 - Universe` active return, and VW `Q5 - Q1` spread in Discovery and Holdout,
  - Bivariate Fama-MacBeth slope alongside `value_sn_z` (`ret ~ 1 + value_sn_z + prof_z`).
- **Question answered:** Does `ROE`, `ROA`, or `OP/A` carry stronger cross-sectional predictive power in BIST than `GP/A`, either standalone or after controlling for `value_sn`?

### R3. Momentum (`mom_12_1` vs `mom_6_1`): horizon, weighting, and regime
- Definitions:
  - `mom_12_1`: $P_{t-1} / P_{t-12} - 1$ (`factors_monthly.parquet`),
  - `mom_6_1`: $P_{t-1} / P_{t-6} - 1$ built from monthly adjusted closes (`monthly_prices.parquet`).
- Compare Rank-IC, EW `Q5 - Q1`, EW `Q5 - Universe`, and VW `Q5 - Q1` across `liq_drop = 0.0` vs `0.30` and Discovery vs Holdout.
- **Question answered:** Is momentum significant in long-short (`Q5 - Q1`), value-weighted, or 6-1 form even when long-only EW `Q5 - Universe` fails?

### R4. Low volatility (`vol60`): long-leg bonus vs high-volatility tail avoidance
- On the liquid universe (`liq_drop = 0.30`), decompose the monthly return of `vol60` quintiles (`Q1` = highest volatility, `Q5` = lowest volatility):
  - Long-short `Q5 - Q1` (academic anomaly definition),
  - Long-only top quintile `Q5 - Universe` (buying low-vol stocks),
  - High-vol loser drag `Q1 - Universe` (what the riskiest 20% returns relative to the universe),
  - Exclusion portfolio `Universe_ex_Q1 - Universe` (dropping the highest-volatility 20% from the universe),
  - Within-value exclusion: top 20% by `value_sn_z` after dropping the highest-volatility 20% of the universe vs plain `value_sn_z` top 20% (gross and 20 bps turnover-adjusted active return, volatility, and max drawdown).

## Role of this study

This is a **reconciliation and hypothesis-qualification study**. It does not alter `config/live_rule.json`. Its output determines which candidate hypotheses (e.g., `ROE` or `OP/A` quality interaction with value, or high-volatility tail exclusion) warrant a dedicated costed portfolio pre-registration in P2.
