# Wave 1 Post-Mortem: Why Quality, Cash-Profitability, and SUE Tilts Fail Post-2021 (`r3-scholar`)

**Date:** 2026-11-24  
**Author:** Literature Researcher (`r3-scholar`)  
**Status:** Wave 1 closed `0/6 PASS` (`N_sel`: `92 -> 98`). Per Manager Directive `00:55`, no further candidates will be proposed.

---

## 1. Empirical Pattern Across All 6 Wave-1 Trials (Primary `lag75`)

| Candidate | Discovery `D` (`NW t`) | Holdout `D` (`NW t`) | IAS 29 `2024-05+` `D` (`NW t`) | Holdout `dIC` vs `R0` | Holdout Entrants − Dropouts |
|---|---:|---:|---:|---:|---:|
| `scholar_cbop` | `+2.71%/yr (+2.67)` | `-2.29%/yr (-1.67)` | `-3.69%/yr (-3.03)` | `-0.0028 (-0.96)` | `-10.45%/yr (-1.29)` |
| `scholar_sue_usd` | `+1.43%/yr (+1.32)` | `-1.49%/yr (-1.02)` | `-0.87%/yr (-0.61)` | `+0.0004 (+0.15)` | `-7.27%/yr (-0.89)` |
| `scholar_real_cbop_sue` | `+3.86%/yr (+4.56)` | `-2.41%/yr (-1.38)` | `-3.04%/yr (-2.20)` | `+0.0007 (+0.25)` | `-10.27%/yr (-1.16)` |
| `miner_ocf_ev_real` | `+3.38%/yr (+2.35)` | `-2.12%/yr (-1.67)` | `-3.84%/yr (-1.78)` | `-0.0009 (-0.34)` | `-7.16%/yr (-0.87)` |
| `miner_qgp_surp_real` | `+1.79%/yr (+1.30)` | `-2.13%/yr (-1.45)` | `-5.01%/yr (-2.15)` | `+0.0077 (+2.88)` | `-9.26%/yr (-1.25)` |
| `miner_gp_qop_real` | `+2.31%/yr (+1.46)` | `-2.21%/yr (-1.23)` | `-6.16%/yr (-3.95)` | `+0.0030 (+1.07)` | `-17.60%/yr (-1.36)` |

Every candidate cleared the Discovery bar (`D > 0`, `t >= 1.0`) and failed Holdout (`D < 0`), with the sharpest losses concentrated in the **IAS 29 window (`2024-05+`)**, where `Entrants - Dropouts` ran `-19%` to `-40%/yr` (`t = -2.06` to `-3.29`).

---

## 2. Four Structural Reasons Tilts Fail Post-2021

1. **Negative Real Interest Rates (2021–2023) Inverted the Accrual / NOA Penalty:**
   - In `2013–2020`, Turkey had positive real rates and moderate inflation (6–20%); expanding Net Operating Assets (`ΔNOA > 0`) reflected bloated receivables/inventories and weak cash conversion, so penalizing `ΔNOA` (`CbOP`, `OCF/EV`) added `+2.7%` to `+3.9%/yr`.
   - In `2021–2023`, deeply negative real policy/borrowing rates (~50–85% CPI vs ~10–15% credit) turned working-capital and debt-financed asset accumulation (`ΔNOA > 0`) into a **rational inflation hedge** and generated unrecognized monetary liability gains (Konchitchki 2011; Uzunlar, Atıcı & Çevik 2025). Penalizing `ΔNOA` pushed the portfolio out of net-debt/inventory beneficiaries into cash-heavy firms that suffered monetary purchasing-power erosion.

2. **IAS 29 Accounting Mechanics Distorted Operating Margins, Gross Profits, and Accruals (`2024-05+`):**
   - Under IAS 29, COGS and inventories are restated from historical purchase dates to period-end CPI, which mechanically compresses gross and operating margins for inventory-heavy manufacturers while non-operating **Net Monetary Position Gain/Loss (NPPKK)** (not present in `quarterly.parquet`) drives a large share of bottom-line earnings and equity re-rating (Uzunlar et al. 2025).
   - Consequently, `gp/mcap`, `op_profit` surprises, and `CbOP` penalized capital-intensive `value_sn` incumbents right as IAS 29 restated their book values upward (`miner_gp_qop_real` `IAS 29 D = -6.16%/yr, t = -3.95`; `Entrants - Dropouts = -39.94%/yr, t = -3.29`).

3. **Top-Quintile Dilution vs. Whole-Cross-Section Rank-IC:**
   - Several tilts improved full-cross-section `Rank-IC` in Holdout (`miner_qgp_surp_real` `dIC = +0.0077, t = +2.88`; `scholar_real_cbop_sue` `dIC = +0.0007`), yet lost money in the top 20% portfolio (`Entrants - Dropouts` `-9%` to `-18%/yr`).
   - Reason: in BIST's concentrated value tail, `R0` already earns `+10.14%/yr (t = +2.97)` in Holdout by holding the deepest-value quintile. Any linear additive tilt (`0.70–0.80 * value_sn + 0.20–0.30 * X`) displaces ~15–20% of those extreme value names (`top-20% overlap ~79–85%`) in exchange for mid-value stocks whose `X` spread does not compensate for the lost deep-value convexity during post-2021 inflation re-ratings.

4. **Filing-Lag Mismatch Under IAS 29 (`lag75` vs. `kapdates`):**
   - On `scholar_sue_usd` and `scholar_real_cbop_sue`, Holdout `D` flipped by **+4.0 to +4.8 pp/yr** between primary `lag75` (`-1.49%` / `-2.41%`) and actual KAP publication dates (`+2.55%` / `+2.40%`). Under IAS 29 transitions, SPK extended reporting deadlines beyond 75 days, breaking the fixed 75-day lag assumption for event-sensitive earnings-surprise signals.

---

## 3. Conclusion

Across **98 total stock-selection trials** (`R0` through Round 3 Wave 1), no static quality, cash-flow, accrual, ROIC, or SUE tilt beats `value_sn` top-20% across both the 2013–2020 low-inflation/positive-real-rate regime and the 2021–2026 high-inflation/IAS 29 regime. The cross-regime robustness of `R0` (`+5.14%/yr` Discovery, `+10.14%/yr` Holdout vs EW net) comes precisely from relying on a balanced 4-leg sector-neutral valuation anchor without conditioning on accounting quality signals whose sign flips under negative real rates and hyperinflation restatements.
