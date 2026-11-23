# Round 4 Pre-registration: ML Researcher Batch 1 (`ml_hgb`, `ml_hgb_blend50`)

- **Date**: 2026-11-24
- **Role**: `ml` (ML Researcher)
- **Batch**: `ml_batch1` (`m = 2` variants; max 5 per batch)
- **Branch**: `agent/r4-ml`
- **Trial ledger `N_sel`**: `98 -> 100` (`round4_ml_hgb` = 99, `round4_ml_hgb_blend50` = 100)
- **Return backtest status**: ZERO return backtests executed prior to this pre-registration and ledger commit.

---

## 1. Motivation & Hypothesis

Round 3 showed that static linear additive tilts on `value_sn` (profitability, accruals, SUE) all failed post-2021 (`0/6 PASS`) due to regime shifts (negative real rates 2021–2023, IAS 29 transition 2024+) and deep-value tail dilution.

Here we test one honest, strictly causal walk-forward nonlinear tree model (`HistGradientBoostingRegressor`) trained on expanding monthly windows using **only existing PIT panel columns** (value components, size, liquidity, 12-1 momentum, volatility, and sector dummies — no banned profitability/quality/accruals/SUE/macro/KAP features) to predict next-month cross-sectional rank returns:

1. **`ml_hgb`** (+1 `N_sel`, trial 99): Standalone expanding-window walk-forward `HistGradientBoostingRegressor` rank predictor. Tests whether nonlinear interactions among value components, size, liquidity, momentum, volatility, and sectors beat `R0` (`value_sn`) net of realistic BIST trading costs.
2. **`ml_hgb_blend50`** (+1 `N_sel`, trial 100): 50/50 cross-sectional percentile-rank average of `ml_hgb` and `value_sn_z`. Tests whether anchoring the ML score to `R0`'s deep-value core reduces turnover and improves cross-regime robustness.

---

## 2. Exact Variants & Formulas

### Variant 1: `ml_hgb`
For each rebalance month-end `t >= 2016-01-31`:
1. **Training window (strictly causal)**: all rows in the prepared PIT panel (`liq_drop_pct=0.3`, `value_sn_z.notna()`) with `date < t` and `fwd_ret_1m.notna()`.
   - First prediction month `t = 2016-01-31` trains on `2013-04-30 .. 2015-12-31` (33 months).
   - For every training row at month-end `s < t`, `s + 1 month <= t`, so its 1-month forward return is realized at or before `d0_of[t]` close (prior to the next-trading-day portfolio fill at `d0_of[t] + 1`).
2. **Target `y(i, s)`**: within-month cross-sectional percentile rank of `fwd_ret_1m` in `(0, 1]` (`groupby("date")["fwd_ret_1m"].rank(ascending=True, pct=True)`), computed strictly inside `train_df`.
3. **Feature matrix `X`** (existing PIT panel columns only; inflation-stationary via single-month cross-sectional standardization; zero cross-date leakage):
   - Value components (4): `bm_z`, `ep_z`, `sp_z`, `ey_z` (from `core/factor_backtest.py::prepare`)
   - Size (1): `size_z` (from `prepare`, `-log(mcap)` z-score)
   - Liquidity (1): `log_tlvol60_z` = within-month `fb.winsorize_z(np.log(tlvol60), lo=0.01, hi=0.99)` computed independently per `date`
   - Momentum 12-1 (1): `mom_12_1_z` (from `prepare`)
   - Volatility (1): `vol60_z` (from `prepare`, `-vol60` z-score)
   - Sector dummies (PIT one-hot): binary indicators `sec__<sector>` for `sorted(train_df["sector"].dropna().unique())` — built strictly from sectors observed in `train_df` (`date < t`), so unseen future sectors map to all-zero dummies.
   - Missing values (`NaN`) are handled natively by `HistGradientBoostingRegressor` (no cross-date imputation).
4. **Prediction**: fit frozen `HistGradientBoostingRegressor` on `(X_train, y_train)`, predict `score(i, t) = model.predict(X_test(t))` on `df[df["date"] == t]` (with all `fwd_ret*` columns stripped beforehand). Months `t < 2016-01-31` receive `NaN`.

### Variant 2: `ml_hgb_blend50`
For each rebalance month-end `t >= 2016-01-31`:
```text
score_blend50(i, t) = 0.50 * pct_rank_t(ml_hgb(i, t)) + 0.50 * pct_rank_t(value_sn_z(i, t))
```
computed via `research_round3.rank_average_combo(df, "ml_hgb", "value_sn_z", weight_a=0.5, require_both=True)` (higher score = higher percentile rank in `(0, 1]`; pre-2016 months remain `NaN`).

---

## 3. Frozen Parameters (No Tuning)

```json
{
  "blend_weight_ml": 0.5,
  "blend_weight_value_sn": 0.5,
  "early_stopping": false,
  "estimator": "sklearn.ensemble.HistGradientBoostingRegressor",
  "features_numeric": [
    "bm_z",
    "ep_z",
    "sp_z",
    "ey_z",
    "size_z",
    "log_tlvol60_z",
    "mom_12_1_z",
    "vol60_z"
  ],
  "features_categorical": [
    "sector (PIT one-hot from train_df date < t)"
  ],
  "first_pred_date": "2016-01-31",
  "l2_regularization": 1.0,
  "learning_rate": 0.05,
  "liq_drop_pct": 0.3,
  "loss": "squared_error",
  "max_bins": 255,
  "max_depth": 4,
  "max_iter": 100,
  "max_leaf_nodes": 15,
  "min_samples_leaf": 50,
  "random_state": 42,
  "target": "within-month pct_rank(fwd_ret_1m)",
  "top_pct": 0.2
}
```

---

## 4. Leakage Prevention & Verification Plan

Before reporting backtest returns, a dedicated unit test suite (`tests/test_research_round4_ml_leakage.py`) verifies:
1. Every training fold satisfies `(train_df["date"] < rebalance_date).all()` and `((train_df["date"].dt.to_period("M") + 1) <= rebalance_date.to_period("M")).all()`.
2. Perturbing/corrupting ALL rows with `date >= t` (features and `fwd_ret_1m` alike) leaves predictions at `date < t` and trained model parameters at `date == t` bit-for-bit identical (causality invariance test).
3. Perturbing `fwd_ret_1m` at `date == t` leaves predictions at `date == t` bit-for-bit identical.
4. Sector dummy columns at month `t` contain zero sectors that only first appear at `date >= t`.
5. No pre-2016 predictions are emitted (`date < 2016-01-01` are strictly `NaN`).

---

## 5. Execution & Round 4 Full-Period Robustness Gauntlet (Starting 2016)

- **Primary panel**: `/home/eren/bist_project/data/research/fp/factors_monthly.parquet` (lag-75 PIT).
- **Robustness panel**: `/home/eren/bist_project/data/research/fp/factors_monthly_kapdates.parquet` (actual KAP dates).
- **Portfolio engine**: exact same universe (`value_sn_z.notna()`, `liq_drop_pct=0.3`), top-20% equal weight, 1M TL real capital (`CAPITAL_REF=2026-09-30`), base `pb.Costs()`, next-close fills (`fill="close"`), cash at CBRT policy rate as `R0`.
- **Symmetric horizon**: `EW`, `R0`, `ml_hgb`, and `ml_hgb_blend50` are all simulated from `2016-01-31` through `2026-09-30` (128 realized monthly returns: `2016-01 .. 2026-08`) so initial entry from cash is symmetric across `R0` and candidates.
- **Paired difference**: `D_t = active_ew_net(cand)_t - active_ew_net(R0)_t = port(cand)_t - port(R0)_t`. Newey-West HAC `t` uses 6 lags (`core/factor_backtest.py::newey_west_t`).

### GAUNTLET PASS Rule (Fixed by Manager; Blocks Start 2016)
PASS iff **ALL 6** hold:
1. **Full (2016-01..latest, 128m)**: paired `D > 0` with `NW t >= 2.0`.
2. **All 4 blocks `D > 0`**: `2016` (12m), `2017-20` (48m), `2021-23` (36m), `2024+` (32m).
3. **USD MaxDD**: not worse than `R0` by `> 2.0 pp` in BOTH full (`2016-01+`) AND `2021+`.
4. **KAP-date panel**: full (`2016-01+`) paired `D > 0` and `NW t >= 1.0`.
5. **Holm-adjusted `p < 0.05`** within this prereg batch (`m = 2`), using two-sided Student-t `p = 2 * t.sf(|t_NW|, df=T-1)` (one-sided Holm `p` also reported as diagnostic).
6. **One-way turnover**: `<= 1.5x R0` on primary `lag75` full (`2016-01+`).

DSR is reported at updated `N_sel = 100`. A PASS is **not** promoted to live; it enters only a shadow forward record (OOS from 2026-12).
