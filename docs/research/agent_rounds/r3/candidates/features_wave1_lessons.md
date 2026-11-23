# Wave 1 Postmortem (`r3-features`): Why Profitability / Accruals / SUE Tilts Fail Post-2021

**Author:** `r3-features`  
**Date:** 2026-11-24  
**Scope:** Engineering & data-structure diagnosis based strictly on `core/pit_panel.py`, `fp/STATS.json`, and the 6 published Wave 1 `results/*.md` reports (no new holdout queries or candidates).

---

## Summary Table (Published Wave 1 `results/*.md`, Primary `lag75` vs `kapdates`)

| Candidate | Disc `D` (`lag75`) | Hold `D` (`lag75`) | IAS 29 `D` (`2024-05+`) | Hold `dIC` (`lag75`) | Hold `D` (`kapdates`) | `kap - lag75` (Hold) |
|---|---:|---:|---:|---:|---:|---:|
| `scholar_cbop` | +2.71% (+2.67) | -2.29% (-1.67) | -3.69% (-3.03) | -0.0028 | -1.41% (-1.00) | +0.88 pp |
| `scholar_sue_usd` | +1.43% (+1.32) | -1.49% (-1.02) | -0.87% (-0.61) | +0.0004 | +2.55% (+1.46) | +4.04 pp |
| `scholar_real_cbop_sue` | +3.86% (+4.56) | -2.41% (-1.38) | -3.04% (-2.20) | +0.0007 | +2.40% (+1.28) | +4.81 pp |
| `miner_ocf_ev_real` | +3.38% (+2.35) | -2.12% (-1.67) | -3.84% (-1.78) | -0.0009 | -1.18% (-0.60) | +0.94 pp |
| `miner_qgp_surp_real` | +1.79% (+1.30) | -2.13% (-1.45) | -5.01% (-2.15) | +0.0077 (+2.88) | -0.48% (-0.26) | +1.65 pp |
| `miner_gp_qop_real` | +2.31% (+1.46) | -2.21% (-1.23) | -6.16% (-3.95) | +0.0030 (+1.07) | -0.94% (-0.76) | +1.27 pp |

---

## Five Feature-Engineering Root Causes

### 1. IAS 29 Adoption Cliff Breaks Every YoY Balance-Sheet & Discrete-Quarter Feature (`2023Q4–2024Q4`)
- **Balance-sheet stock cliff (`cbop`, `cbop_real`, `ocf_ev_real`):** `fp/quarterly.parquet` switches from historical cost (`<= 2023Q3`) to IAS 29 constant purchasing power (`>= 2023Q4`). On adoption, multi-year historical-cost non-monetary assets (PP&E, inventories, intangibles) step up by **several years of cumulative inflation**, not 1-year CPI. Scaling `NOA_{p-4q}` by 1-year `CPI(p)/CPI(p-4q)` does not bridge this multi-year step-up, creating large artificial `ΔNOA > 0` (fake accruals) for capital-intensive value firms. All three NOA-based candidates suffered their worst losses in IAS 29 (`-3.04%` to `-3.84%/yr`, `Entrants - Dropouts` = `-18.4%` to `-19.6%/yr`).
- **Unbridged discrete-quarter flows (`q_gross_profit`, `q_op_profit`, `q_ni_parent`):** In `core/pit_panel.py::bridge_ttm`, the `2023Q4–2024Q3` IAS 29 bridge repairs **`ttm_*` columns only — never `q_*` columns**. Moreover, comparing `q_*` in `2024` (IAS 29 inflation-adjusted COGS) against `q_*_{p-4q}` in `2023` (historical-cost FIFO-inflated margins) produces systematic negative accounting surprises for inventory-heavy firms even after 1-year CPI scaling. Both discrete-quarter surprise tilts collapsed in IAS 29 (`miner_qgp_surp_real`: `-5.01%/yr, t=-2.15`; `miner_gp_qop_real`: `-6.16%/yr, t=-3.95`, `Entrants - Dropouts = -39.94%/yr`).
- **Mixed re-expression classes (`fp/STATS.json`):** `undo_reexpression` covers 421 `reexpressed` tickers while 34 `not_reexpressed` and 33 `unknown` tickers remain in the same cross-section; any YoY level difference mixes accounting bases across peers in the same month.

### 2. Right-Tail Outlier Selection vs. Full-Cross-Section `dIC`
- `miner_qgp_surp_real` achieved **significantly positive** holdout Rank-IC gain (`dIC = +0.0077, t = +2.88`) and `miner_gp_qop_real` was also positive (`dIC = +0.0030`), yet **both lost badly in top-20% portfolio switching** (`Entrants - Dropouts = -9.3%` and `-17.6%/yr` in holdout; `-22.9%` and `-39.9%/yr` in IAS 29).
- Symmetric linear z-score tilting (`0.75 * value_sn_z + 0.25 * tilt_z`) promotes stocks with extreme positive right-tail `tilt_z` into the top 20% at the expense of deep-value boundary names. Under IAS 29 / high inflation, the extreme right tail of YoY flow/accrual ratios is disproportionately populated by **restatement and regime-transition artifacts**, whereas cross-sectional `dIC` gains come primarily from ordering the middle/bottom of the distribution.

### 3. `lag75` Staleness Severely Penalizes Fast-Horizon Quarterly Surprise Signals in 2021+
- Every single candidate performed better on `factors_monthly_kapdates.parquet` than on primary `lag75` in Holdout, with the fastest earnings-surprise signals swinging by **`+4.0 to +4.8 pp/yr`** (`scholar_sue_usd`: `-1.49% -> +2.55%`; `scholar_real_cbop_sue`: `-2.41% -> +2.40%`).
- Under primary `lag75`, reports published on KAP at 30–50 days sit unused for 1–2 extra months; in post-2021 BIST, PEAD is largely priced in before day 75, turning a fast earnings-surprise tilt into a stale chase signal. (Conversely, during 2024 IAS 29 filing extensions, actual KAP dates exceeded 100 days for many Q4 reports, creating lag mismatch in the opposite direction.)

### 4. Steep `R0` Dilution Hurdle in 2021+
- `R0` (`value_sn`) net active return nearly doubled from Discovery (`+5.14%/yr, t=+1.97`) to Holdout (`+10.14%/yr, t=+2.97`).
- Cutting `value_sn_z` weight from `1.00` to `0.70–0.80` immediately surrenders `~2–3%/yr` of value exposure in 2021+ (`top-20% overlap = 78–85%`), which any noisy or regime-shifted secondary leg fails to earn back after turnover costs.

### 5. Feature-Engineering Takeaways for Any Future Work
1. **Treat `2023Q3 -> 2023Q4` as a hard accounting basis break for YoY features:** do not compute YoY differences on `NOA` or unbridged `q_*` flows across the IAS 29 transition without explicit basis-consistent restatement or masking.
2. **Audit `lag75` vs `kapdates` sensitivity on Discovery before promoting fast fundamental signals:** if a signal's edge requires KAP-day speed, it is structurally disadvantaged under a `lag75` primary pass rule.
3. **Inspect top-20% entrant profiles (not just full-sample `dIC`) on Discovery:** linear z-tilts reward extreme positive tilt outliers, which are the most fragile rows during regime transitions.
