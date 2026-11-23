# Round 4 Portfolio & Risk Engineering Lessons (`r4-risk`)

**Author**: `r4-risk` (`agent/r4-risk`)  
**Date**: 2026-11-24  
**Scope**: 8 pre-registered portfolio-construction & risk-engineering variants on unchanged `R0` (`value_sn_z` top-20%) across Batch 1 (`N_sel: 98 -> 103`) and Batch 2 (`N_sel: 103 -> 106`).

---

## 1. Gauntlet Summary (0/8 PASS)

| Batch | Variant | Full `D` %/yr (NW t) | Blocks (`13-16` / `17-20` / `21-23` / `24+`) | USD MaxDD Full / `21+` vs R0 | `kapdates` `D` (`t`) | Holm `p` | Turnover (`xR0`) | Sharpe / Sortino | Verdict |
|---|---|---:|---|---:|---:|---:|---:|---:|:---:|
| B1 | `risk_score_rank` | +1.60 (+1.49) | -0.68 / +5.79 / -1.34 / +1.82 | +0.40 / -0.40 pp | +1.39 (+1.32) | 0.4203 | 21.6% (1.05x) | 0.76 / 1.42 | **FAIL** |
| B1 | `risk_score_exp_cap` | +1.45 (+1.32) | +0.47 / +5.26 / -1.62 / +0.58 | -0.30 / -2.20 pp | +1.55 (+1.29) | 0.4203 | 21.3% (1.04x) | 0.76 / 1.41 | **FAIL** |
| B1 | `risk_invvol` | -1.27 (-1.63) | +0.16 / -5.37 / +0.97 / +0.37 | +0.20 / +0.70 pp | -1.07 (-1.38) | 0.4203 | 21.3% (1.04x) | 0.70 / 1.30 | **FAIL** |
| B1 | `risk_smooth_k3` | -0.30 (-0.54) | +0.10 / +0.33 / -1.34 / -0.63 | +0.60 / +0.00 pp | +0.12 (+0.19) | 0.5899 | 13.2% (0.64x) | 0.72 / 1.31 | **FAIL** |
| B1 | `risk_invvol_smooth_k3` | -1.69 (-1.92) | -0.24 / -5.06 / -0.20 / -0.35 | +0.50 / +0.60 pp | -1.24 (-1.11) | 0.2832 | 13.4% (0.65x) | 0.69 / 1.26 | **FAIL** |
| B2 | `risk_sector_ew` | -1.46 (-1.16) | -2.02 / -0.40 / +0.48 / -4.46 | +1.20 / +0.40 pp | -0.87 (-0.69) | 0.7433 | 25.7% (1.25x) | 0.69 / 1.26 | **FAIL** |
| B2 | `risk_sn_invvol` | -0.39 (-0.86) | +0.23 / -2.30 / +0.09 / +1.06 | +0.10 / +0.40 pp | -0.21 (-0.46) | 0.7433 | 21.3% (1.04x) | 0.72 / 1.34 | **FAIL** |
| B2 | `risk_max_div` | -2.00 (-0.99) | -1.76 / -2.62 / -3.13 / -0.15 | -1.60 / -0.50 pp | -1.56 (-0.73) | 0.7433 | 35.2% (1.72x) | 0.66 / 1.24 | **FAIL** |

(`R0` baseline: full `vs_ew_net = +7.25%/yr, t = +3.38`, Sharpe `0.73`, Sortino `1.34`, USD MaxDD `-56.6%` full / `-35.4%` `2021+`, turnover `20.5%`, `DSR(106) = 0.0787`.)

---

## 2. Key Structural Takeaways

1. **`R0` (`value_sn_z` top-20% equal weight) is already well-diversified by construction.**
   - Because `value_sn_z` is sector-neutralized, equal-weighting its `34..73` monthly picks (median `46`) naturally caps every sector at `<= 23.9%` (median max sector `16.8%`) and every single stock at `<= 2.94%`. Naive `30%` sector or `5%` name caps are 100% non-binding on `R0`.
   - Re-weighting sectors to equal sector share (`risk_sector_ew`) increases turnover (`20.5% -> 25.7%`) and loses `-1.46%/yr` (`-4.46%/yr` in `2024+`), showing that `R0`'s natural sector representation reflects legitimate cross-sectional valuation breadth rather than harmful concentration.

2. **Score-weighting (`risk_score_rank`, `risk_score_exp_cap`) adds modest full-period return (`+1.45%` to `+1.60%/yr`) but is regime-episodic.**
   - Nearly all gains come from `2017-20` (`+5.26%` to `+5.79%/yr`, `t = +2.39..+2.77`), while `2021-23` turns negative (`-1.34%` to `-1.62%/yr`). `risk_score_rank` raises full-period Sharpe (`0.73 -> 0.76`) and Sortino (`1.34 -> 1.42`) without hurting drawdown, yet falls well short of `NW t >= 2.0` (`t = +1.49`), 4-block consistency, and Holm `p < 0.05`.

3. **Inverse-volatility (`risk_invvol`, `risk_sn_invvol`) dampens 2021+ drawdowns slightly (`+0.40` to `+0.70 pp`) at the cost of `2017-20` cyclical underperformance.**
   - Even after removing cross-sector defensive tilts (`risk_sn_invvol`), within-sector `1/vol_6m` still loses `-2.30%/yr` (`t = -2.16`) in `2017-20` because the most volatile deep-value cyclicals led the recovery.

4. **Holding-period smoothing (`risk_smooth_k3`) saves `0.72%/yr` in transaction costs, but `value_sn` alpha decays faster (`-1.02%/yr` gross).**
   - Cutting turnover from `20.5%` to `13.2%` (`0.64x`) is not enough to overcome stale-rank dilution in `2021-23` (`-1.34%/yr`).

5. **Trailing 6m covariance optimization (`risk_max_div`) overfits noisy daily correlations.**
   - Turnover surges to `35.2%` (`1.72x R0`, breaching the `1.5x` ceiling), pushing annual trading costs from `1.71%` to `3.19%/yr` and dragging `D` to `-2.00%/yr`.

**Conclusion**: Across 8 pre-registered weighting, capping, risk-parity, covariance, and smoothing variants, **equal weighting over the `R0` (`value_sn_z` top-20%) sleeve remains undefeated** on the Round 4 Full-Period Robustness Gauntlet (`0/8 PASS`).
