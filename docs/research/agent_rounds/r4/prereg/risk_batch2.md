# Round 4 Pre-Registration: Portfolio & Risk Engineer (`risk`) — Batch 2

- **Date**: 2026-11-24
- **Role**: Portfolio & Risk Engineer (`r4-risk`, branch `agent/r4-risk`)
- **Batch**: 2 of 2 (3 variants; `N_sel`: 103 -> 106)
- **Signal**: Unchanged `R0` (`value_sn_z`, top 20% monthly cross-section, same universe, 30% liquidity drop, 1M TL real capital, base costs, next-close fills).

## Motivation & Hypotheses (Orthogonal Constructions Beyond Batch 1)

Batch 1 established that:
- Pure cross-sectional `1/vol_6m` (`risk_invvol`) improved 2021+ USD MaxDD (`+0.70pp`) and 3/4 blocks, but lost `-5.37%/yr` (`t=-3.81`) in `2017-20` due to cross-sector defensive tilts.
- `R0` top-20% spans `14..28` sectors per month (median `20`, with median `10` single-stock sectors) and concentrates heavily in `Gayrimenkul` and `Holding` (`157/162` months top sector).

Batch 2 tests 3 orthogonal, non-tuned portfolio constructions addressing sector balance, intra-sector risk parity, and pairwise return correlation:

1. **`risk_sector_ew`** — Sector-Equalized Weighting (with 5% Name / 20% Sector Caps)
   - Assign equal target weight `1 / S_t` to each of the `S_t` sectors represented in the monthly top-20% `value_sn_z` set, divided equally among the names in that sector (`w_i^(0) = 1 / (S_t * n_{s(i),t})`), then project onto `{w >= 0, sum(w) = 1, w_i <= 0.05, sum_{i in s} w_i <= 0.20}` via `cap_weights`.
   - *Frozen params*: `{"weighting": "sector_equal_capped", "top_pct": 0.2, "max_name_weight": 0.05, "max_sector_weight": 0.20}`
   - *Hypothesis*: Eliminates `R0`'s structural overweight in `Gayrimenkul` / `Holding` while capping single-stock sectors at `5%` to prevent idiosyncratic spikes.

2. **`risk_sn_invvol`** — Sector-Neutral Inverse-Volatility Weighting
   - Preserve `R0`'s exact monthly sector weights (`W_s = n_{s,t} / N_t`), and allocate within each sector `s` proportionally to `1 / vol_6m_i` (trailing `126`-day daily return std strictly `<= d0(t)`, `min_periods=60`, fallback to sector/cross-section median).
   - *Frozen params*: `{"weighting": "sector_neutral_invvol", "top_pct": 0.2, "vol_window_days": 126, "vol_min_periods": 60}`
   - *Hypothesis*: Captures intra-sector risk-parity / lower volatility & lower impact without introducing the cross-sector defensive bias that hurt `risk_invvol` in `2017-20`.

3. **`risk_max_div`** — PIT Maximum Diversification Portfolio (Ledoit-Wolf Shrinkage Covariance)
   - At decision day `d0(t)`, compute the `126`-trading-day trailing daily return matrix strictly `<= d0(t)` for the monthly top-20% tickers (filling isolated non-trading days with `0.0` return after requiring `>= 60` valid days; fallback to median diagonal variance if `< 60` days), estimate the shrinkage covariance matrix `Sigma_t` via `LedoitWolf`, and solve `max_w (w^T sigma_t) / sqrt(w^T Sigma_t w)` subject to `w >= 0, sum(w) = 1, w_i <= 0.05, sum_{i in s} w_i <= 0.20`.
   - *Frozen params*: `{"weighting": "max_diversification", "top_pct": 0.2, "cov_window_days": 126, "cov_min_periods": 60, "shrinkage": "LedoitWolf", "max_name_weight": 0.05, "max_sector_weight": 0.20}`
   - *Hypothesis*: Exploits pairwise correlation structure to downweight redundant co-moving picks in crowded sectors while preserving volatility balance and diversification.

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
> Report DSR at updated `N_sel` (`106`), plus Sharpe, Sortino, maxDD, turnover besides `D`.
