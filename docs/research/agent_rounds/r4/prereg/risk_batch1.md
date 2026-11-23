# Round 4 Pre-Registration: Portfolio & Risk Engineer (`risk`) — Batch 1

- **Date**: 2026-11-24
- **Role**: Portfolio & Risk Engineer (`r4-risk`, branch `agent/r4-risk`)
- **Batch**: 1 of 2 (5 variants; `N_sel`: 98 -> 103)
- **Signal**: Unchanged `R0` (`value_sn_z`, top 20% monthly cross-section, same universe, 30% liquidity drop, 1M TL real capital, base costs, next-close fills).

## Motivation & Hypotheses (Pre-Return Diagnostics Only)

Pre-return structural diagnostics on the `R0` top-20% portfolio (`162` months `2013-04 .. 2026-09`) established:
1. `R0` holds `34..73` stocks (median `46`). Because `value_sn_z` is already sector-neutralized, equal-weighted `R0` never exceeds `23.9%` in any single sector (median max sector `16.8%`) and never exceeds `2.94%` in any single name. Consequently, applying a `30%` sector cap or `5%` single-name cap on equal-weight `R0` would be a 100% no-op.
2. Under conviction score-weighting (`exp(value_sn_z)`), single-name weights reach `34.3%` (`95th pct = 21.9%`, `>5%` in `157/162` months) and sector weights reach `46.6%` (after `5%` name cap, `>20%` sector weight occurs in `84/162` months). Thus concentration caps genuinely bind on conviction-weighted portfolios.
3. Trailing 6-month (`126` trading days, `min_periods=60`, strictly `<= d0(t)`) daily return volatility is available with `0` missing values across all `8,075` `R0` picks (`p1 = 0.0126`, `median = 0.0268`, `p99 = 0.0528`).
4. Staggered `K=3` monthly cohort smoothing reduces target one-way turnover from `16.7%` (EW) to `9.6%` (`-42%`), lowering transaction costs without using banned exit/rank buffers.

## Frozen Variants (Batch 1, Max 5)

All 5 variants keep the exact `R0` selection universe (`value_sn_z` non-null after `liq_drop_pct=0.3`), top-20% cutoff (`rank(ascending=False, pct=True) <= 0.2`), and `core/portfolio_backtest.py` cost/fill model (`1M TL` real capital, next-close fills):

1. **`risk_score_rank`** — Rank-Linear Score Weighting
   - Within the monthly top-20% `value_sn_z` set of $N_t$ stocks, assign weight $w_{i,t} \propto r_{i,t}$, where $r_{i,t} \in [1, N_t]$ is the ascending rank (`method="average"`) of `value_sn_z`, normalized to $\sum_i w_{i,t} = 1$.
   - *Frozen params*: `{"weighting": "score_rank", "top_pct": 0.2}`
   - *Hypothesis*: Tilts toward deepest-value convexity without right-tail outlier blowups (`max_w <= 5.7%`).

2. **`risk_score_exp_cap`** — Conviction Exponential Score Weighting with Single-Name & Sector Caps
   - Raw weight $w_{i,t}^{(0)} \propto \exp(\text{value\_sn\_z}_{i,t})$ over the monthly top-20% set, iteratively projected onto $\{w \ge 0,\; \sum_i w_i = 1,\; w_i \le 0.05,\; \sum_{i \in s} w_i \le 0.20\}$.
   - *Frozen params*: `{"weighting": "score_exp_capped", "top_pct": 0.2, "max_name_weight": 0.05, "max_sector_weight": 0.20}`
   - *Hypothesis*: Captures non-linear deep-value tail alpha while strictly bounding idiosyncratic and sector concentration risk.

3. **`risk_invvol`** — PIT 6-Month Inverse-Volatility Weighting
   - At decision day $d_0(t)$ (last trading day $\le t$), compute trailing `126`-trading-day (`min_periods=60`) daily adjusted-close return standard deviation $\sigma_{i,t}^{(6m)}$ strictly up to $d_0(t)$ (fallback to cross-sectional median of top-20% picks if missing or $\le 0$). Weight $w_{i,t} \propto 1 / \sigma_{i,t}^{(6m)}$, normalized to $\sum_i w_{i,t} = 1$.
   - *Frozen params*: `{"weighting": "inverse_vol_6m", "top_pct": 0.2, "vol_window_days": 126, "vol_min_periods": 60}`
   - *Hypothesis*: Reduces portfolio volatility, USD max drawdown, and sqrt market-impact costs without diluting `value_sn` selection.

4. **`risk_smooth_k3`** — 3-Month Staggered Cohort Holding-Period Smoothing (Equal-Weight)
   - Let $w_t^{\text{EW}}$ be the month-$t$ `R0` equal-weight vector. Target weight at month $t$ averages the last $K=3$ monthly cohorts ($t, t-1, t-2$, or $\min(3, t+1)$ at sample start), retaining only tickers with a finite close price on $d_0(t)$ (to avoid allocating to delisted names) and renormalizing to $\sum_i w_{i,t} = 1$. No rank/exit buffer is used.
   - *Frozen params*: `{"weighting": "equal_smooth_k3", "top_pct": 0.2, "cohort_months": 3}`
   - *Hypothesis*: Cuts one-way turnover and 1M TL transaction costs by ~40–50% while retaining multi-month value alpha.

5. **`risk_invvol_smooth_k3`** — Combined PIT Inverse-Volatility + 3-Month Cohort Smoothing
   - Apply the same $K=3$ staggered cohort averaging (filtered for finite close on $d_0(t)$ and renormalized) to the PIT inverse-volatility weights $w_t^{\text{IV}}$ from variant 3.
   - *Frozen params*: `{"weighting": "invvol_smooth_k3", "top_pct": 0.2, "vol_window_days": 126, "vol_min_periods": 60, "cohort_months": 3}`
   - *Hypothesis*: Combines drawdown/volatility reduction from inverse-vol risk budgeting with turnover/cost reduction from 3-month cohort smoothing.

## Evaluation Panels & Fixed Gauntlet Rule (Verbatim)

- **Primary panel**: `/home/eren/bist_project/data/research/fp/factors_monthly.parquet` (`lag75` PIT).
- **Sensitivity panel**: `/home/eren/bist_project/data/research/fp/factors_monthly_kapdates.parquet` (`kapdates` PIT).
- **Execution**: Same universe, liquidity cut (`liq_drop_pct=0.3`), `1M TL` CPI-indexed real capital, base costs, next-close fills as `R0`.

> **FULL-PERIOD ROBUSTNESS GAUNTLET (PASS iff ALL)**:
> (1) full `2013-04..latest` paired `D` vs `R0` > 0 with NW `t >= 2.0`;
> (2) `D > 0` in EACH of 4 blocks `2013-16`, `2017-20`, `2021-23`, `2024+`;
> (3) USD `maxDD` not worse than `R0` by `> 2pp` in `full` and `2021+`;
> (4) also holds on `kapdates` panel (`D > 0`, `t >= 1.0`);
> (5) Holm-adjusted `p < 0.05` within your prereg batch;
> (6) one-way turnover `<= 1.5x R0`.
> Report DSR at updated `N_sel` (`103`), plus Sharpe, Sortino, maxDD, turnover besides `D`.
