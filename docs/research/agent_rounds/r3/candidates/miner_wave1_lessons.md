# Wave 1 Post-Mortem (`r3-miner`): Why Linear Fundamental Tilts Beat `value_sn` in 2013–2020 and Fail in 2021+

**Author:** `r3-miner`  
**Date:** 2026-11-24  
**Scope:** Synthesis strictly from published Wave 1 board reports (`results/*.md`, `N_sel = 93..98`); zero new holdout queries, zero new candidates proposed.

---

## 1. The Uniform Wave 1 Failure Signature (0/6 PASS)

Every Wave 1 candidate — across **both** literature-driven (`r3-scholar`) and data-mined (`r3-miner`) pipelines, covering cash-based operating profitability (`CbOP`), EV cash yield, gross-profit yield, and net/operating/gross profit surprises (nominal, CPI-real, and USD-deflated) — produced the **exact same sign flip** on the primary `lag75` panel:

| Candidate (`N_sel`) | Disc `D` (t) | Hold `D` (t) | IAS 29 `D` (t) | Implied `2021–24.04` `D` | Hold `dIC` (t) | Hold `Ent-Drop` | `kapdates` Hold `D` (t) |
|:---|---:|---:|---:|---:|---:|---:|---:|
| `scholar_cbop` (93) | +2.71% (+2.67) | -2.29% (-1.67) | -3.69% (-3.03) | -1.31% | -0.0028 (-0.96) | -10.5%/yr | -1.41% (-1.00) |
| `scholar_sue_usd` (94) | +1.43% (+1.32) | -1.49% (-1.02) | -0.87% (-0.61) | -1.92% | +0.0004 (+0.15) | -7.3%/yr | +2.55% (+1.46) |
| `scholar_real_cbop_sue` (95) | +3.86% (+4.56) | -2.41% (-1.38) | -3.04% (-2.20) | -1.97% | +0.0007 (+0.25) | -10.3%/yr | +2.40% (+1.28) |
| `miner_ocf_ev_real` (96) | +3.38% (+2.35) | -2.12% (-1.67) | -3.84% (-1.78) | -0.92% | -0.0009 (-0.34) | -7.2%/yr | -1.18% (-0.60) |
| `miner_qgp_surp_real` (97) | +1.79% (+1.30) | -2.13% (-1.45) | -5.01% (-2.15) | -0.11% | **+0.0077 (+2.88)** | -9.3%/yr | -0.48% (-0.26) |
| `miner_gp_qop_real` (98) | +2.31% (+1.46) | -2.21% (-1.23) | -6.16% (-3.95) | **+0.56%** | +0.0030 (+1.07) | -17.6%/yr | -0.94% (-0.76) |

*(Implied pre-IAS 29 holdout `D` = `(68 * D_hold - 28 * D_ias29) / 40`.)*

---

## 2. Five Structural Causes of Post-2021 Failure

1. **IAS 29 Regime Seam Breaks All 4-Quarter Statement Differences (`2024-05+`):**
   - For the miner surprise/yield tilts, **virtually 100% of the holdout deficit occurred inside the 28-month IAS 29 window** (`miner_gp_qop_real`: `-6.16%/yr, t = -3.95` vs `+0.56%/yr` in `2021–2024-04`; `miner_qgp_surp_real`: `-5.01%/yr, t = -2.15` vs `-0.11%/yr` in `2021–2024-04`; `miner_ocf_ev_real`: `-3.84%/yr, t = -1.78`).
   - Every Wave 1 tilt relies on a **4-quarter difference** (`NOA_p - NOA_{p-4}`, `q_profit_p - q_profit_{p-4}`). Across the IAS 29 transition (`2023Q4` onward), balance sheets and flows shifted abruptly from historical-cost nominal accounting to cumulatively indexed IAS 29 purchasing power. Multiplying a historical-cost `p-4` balance sheet or quarter by 1-year `CPI(p)/CPI(p-4)` does **not** remove multi-year cumulative revaluation jumps (fixed assets, inventories, equity carried at old historical cost), turning `Δ_real NOA` and `Δ_real q_profit` into noisy accounting-seam artifacts precisely when IAS 29 begins.
   - Economically, during the 2024–2026 CBRT disinflation tightening cycle (high real rates, real TL appreciation), trailing operating/gross profit winners suffered sharp margin compression, so tilting away from plain deep value toward trailing profit momentum/cash quality lost `-3%` to `-6%/yr`.

2. **Top-Quintile Deep-Value Convexity Dilution (IC Improves, Yet Portfolio Loses):**
   - `miner_qgp_surp_real` **significantly raised cross-sectional Rank-IC in Holdout (`dIC = +0.0077, NW t = +2.88`, Rank-IC `+0.0811`)** and even in IAS 29 (`dIC = +0.0073, t = +1.52`), yet its **top-20% entrants trailed its dropouts by `-9.3%/yr` in holdout and `-22.9%/yr (t = -2.06)` in IAS 29**.
   - Every linear tilt `0.75 * value_sn_z + 0.25 * X_z` swaps out 15–22% of the deepest value names (`R0` holdout active `+10.14%/yr, t = +2.97`) for moderately cheap high-`X` names. Just like Round 1 `S1`, lifting Rank-IC across the middle/bottom of the cross-section does **not** pay inside a long-only top-20% portfolio when `R0`'s edge is concentrated in the extreme right tail of cheapness.

3. **Lag-75 Staleness Penalizes Quarterly Earnings/Surprise Signals in 2021+:**
   - All 6 candidates performed **`+0.88` to `+4.81 pp/yr` better on `kapdates` than on `lag75` in Holdout** (e.g., `scholar_sue_usd`: `-1.49%` → `+2.55%`; `scholar_real_cbop_sue`: `-2.41%` → `+2.40%`; `miner_qgp_surp_real`: `-2.13%` → `-0.48%`).
   - Waiting an assumed 75/100 days in 2021+ — when BIST market participation and earnings-reaction speed accelerated — means acting on stale quarterly surprises *after* PEAD has already realized. Even on `kapdates`, however, zero candidates reached `t >= 2.0`, proving staleness is a compounding drag rather than the sole cause.

4. **Asymmetric Discovery-to-Holdout Regime Shift & Selection Regression:**
   - On the corrected PIT baseline, `R0` was relatively weak in 2013–2020 (`+5.14%/yr, t = 1.97`) and very strong in 2021+ (`+10.14%/yr, t = 2.97`, boosted by negative-real-rate deep-value re-rating and a `0.35` low-vol loading).
   - Any factor mined to repair `R0`'s 2013–2020 discovery weakness naturally selects signals that thrived in the low-inflation 2013–2020 regime (accrual quality, operating PEAD) and systematically regresses toward zero or negative `D` when `R0` dominates in 2021+.

5. **Multiple-Testing Reality (`N_sel = 98`):**
   - After 98 stock-selection trials, the full-sample Deflated Sharpe Ratio hurdle (`SR0 = 0.386` monthly) exceeds every tested variant (`DSR <= 0.227`). Continuing to test linear fundamental/profitability/accrual/SUE tilts on this same panel burns `N_sel` with negative expected value.

---

## 3. Conclusion (`r3-miner` Standing Down)

- **Do not** propose or test further profitability, accrual/cash-flow, gross-profit, or quarterly SUE/surprise tilts on `value_sn`.
- `R0` (`value_sn` top-20% monthly) remains undefeated across 98 trials; the **live forward record** (started 2026-11) is the proper out-of-sample arbiter.
- `r3-miner` is now idle per manager directive.
