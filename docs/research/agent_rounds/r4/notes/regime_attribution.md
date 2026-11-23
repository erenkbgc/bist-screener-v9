# Round 4 Regime & Attribution Analysis of `R0` (`value_sn`)

**Author**: `r4-regime` (Regime & Attribution Lab)  
**Date**: 2026-11-24  
**Mode**: Diagnostics only — **zero** candidate return trials, `trial_ledger.json` untouched (`N_sel` unchanged), live code untouched.  
**Data**: Read-only PIT panel `/home/eren/bist_project/data/research/fp/` (`factors_monthly.parquet`, `factors_monthly_kapdates.parquet`, `quarterly.parquet`, `STATS.json`), simulated with exact `R0` engine (`core/portfolio_backtest.py::simulate`, 1M TL real capital, base costs, next-close fills, `ew_net` benchmark).  
**Reproducibility**: `scripts/diagnose_r4_regime_attribution.py` -> `data/reports/r4_regime_attribution_2026-11-24.json`.

---

## Executive Summary

1. **`R0` (`value_sn_z` top-20% equal weight) earns `+7.25%/yr (NW t = +3.38)` full-period net active vs `EW net` on `lag75` (`+7.73%/yr, t = +3.86` on `kapdates`), and is positive in all 4 gauntlet blocks — but its return engine rotates dramatically across regimes:**
   - **B1 (`2013–16`, moderate inflation, near-zero real policy rate `-0.7%`):** Broad within-sector selection (`+6.90%/yr, t = +3.39`), anchored by `ey` (`EBIT/EV`, FM `+5.33%, t = +2.72`) and `sp`.
   - **B2 (`2017–20`, 2018 FX crisis + 2020 COVID momentum surge):** **R0's weakest block** (`+3.48%/yr, t = +0.76`; USD MaxDD `-56.6%`; `2020` active `-7.5%`). Earnings legs collapsed (`ep` FM `-5.98%, t = -2.82`; `ep_sn_z` `D = -9.27%`; `ey_sn_z` `D = -6.78%`); almost all survival alpha came from `bm` (`+6.84%, t = +2.33`), `sp` (`+3.80%, t = +3.27`), extreme top-5% deep value (`+20.73%/yr`), and small-cap value (`+30.63%/yr`).
   - **B3 (`2021–23`, hyperinflation `48.3%` CPI vs `17.0%` policy -> `-31.3%` real rate):** **R0's super-block** (`+14.21%/yr, t = +3.83`). All 4 legs worked simultaneously, large-cap value surged (`+17.34%/yr`), leveraged value re-rated (`nd_to_eq` Hi-Lo inside R0 `+18.4%/yr, t = +2.5`), and avoiding the expensive bottom quintile (`Q5 = -15.58%/yr`) paid heavily.
   - **B4 (`2024+`, CBRT tightening `43.7%` policy vs `43.6%` CPI + IAS 29 adoption):** Net active slowed to `+5.56%/yr (t = +1.15)` and collapsed in the **IAS 29 sub-window (`2024-05+`) to `+2.19%/yr (t = +0.56)`** (`2025: +2.8%`, `2026 YTD: -1.9%`). Leg leadership inverted: **`ep` became the only positive joint-FM leg (`+4.51%, t = +2.06`)**, while `sp` (`D = -6.57%, t = -2.34`; IAS 29 IC `-0.0011`) and `ey` (`D = -4.40%, t = -2.28`) dragged, leveraged R0 names flipped to **`-13.2%/yr (t = -2.1)`**, and `ep < 0` R0 picks (`13.7%` share) lost **`-9.99%/yr`** vs `+9.84%/yr` for `ep > 0`.

2. **Why `R0` survived 106 trials (and why naive linear tilts / rank compressions fail):**
   - **Regime hedging across the 4 legs:** No single leg or 3-leg leave-one-out composite beats `R0` across all 4 blocks (`no_ep` wins B1/B2 by `+3.25%/+3.89%` then loses B3/B4 by `-0.97%/-2.45%`; `no_sp` loses all 4 blocks).
   - **Extreme top-tail convexity:** `T1_top5` (top 5% of universe) earns **`+13.94%/yr`** full (`+20.73%` B2, `+14.96%` B4, `+9.80%` IAS 29) vs `T3_10_20` (half of R0's weight) at `+6.22%/yr` (`-2.69%` B2, `+0.10%` IAS 29). Compressing right-tail skew via rank/log/normal-score transforms (`v_rk_sn`, `v_slog_sn`, `v_wsec_rk_mean`, Round 1 `S1`) raises whole-cross-section Rank-IC (`+0.0632 -> +0.0662`) while **destroying top-20% return** (`+8.6% -> +6.4..7.8%`).

3. **Six Concrete Construction & Data Defects of `value_sn` Quantified Below:**
   1. **`S/P` (`ttm_revenue / mcap`) capital-structure mismatch & leverage contamination:** Enterprise numerator over equity denominator creates `+0.373` rank correlation with `net_debt/mcap` (`+0.384` in B4) and `+2.72` skewness (`+3.01` in B4), driving `40%` of single-leg outlier picks and crashing `-6.57%/yr` in B4 tightening.
   2. **`E/P` left-tail skewness (`skew = -0.52` full, `-1.30` B2; `p01 = -3.77σ` vs `p95 = +1.42σ`):** Deep one-off loss outliers inflate `std(ep)`, compressing positive `ep_z` right-tail weights and causing `ep`'s B2 collapse (`-9.27%/yr`), while unscreened `ep < 0` picks (`13.7%` of R0 in B4) lose `-9.99%/yr` under tight rates.
   3. **Current-price denominator chasing falling knives:** Updating `mcap` monthly while fundamentals update quarterly gives R0 persistent negative momentum (`mom_12_1_z = -0.17` full, `-0.26` B4) and short-term loser exposure (`str_1m_z = +0.12` full, `+0.15` B4). Inside R0, higher `str_1m` (non-crashing) and higher `mom_12_1` beat lower in **all 4 blocks** (`+6.1%/yr` and `+4.4%/yr` full), and **filing-driven entrants (`+26.15%/yr` L75, `+9.72%/yr` KAP)** vastly outperform **price-driven entrants (`+11.81%` L75, `-0.76%` KAP)** and **newly-liquid universe entrants (`-10.23%` L75)**.
   4. **IAS 29 `2023Q3 -> 2023Q4` accounting cliff & `fp/` mixed-basis seam:** `undo_reexpression` leaves `2023Q3` in 2024 restated units while dividing `2023Q4+`, causing `ttm_revenue` to drop **`0.630x`** and `equity` to jump **`1.778x`** across `2023Q3 -> 2023Q4`; `2024Q4` `ttm_ni` drops `0.664x` with a **`24.7%` positive-to-negative flip rate**; `32` `unknown`-class tickers (left undivided) get selected at **`38.4%`** (`12.9%` of R0 in B4), while `not_reexpressed` USD-functional reporters inside R0 lose **`-17.24%/yr`** under real TL appreciation.
   5. **`lag75` staleness vs 2024 IAS 29 lookahead inversion:** Normally `lag75` is ~32 days staler than `kapdates` (`130d` vs `98d`), costing R0 `-2.29%/yr (t = -2.15)` in B1 and `-1.94%/yr` in B2. Conversely, during 2024 SPK IAS 29 filing extensions, `lag75` was **ahead of actual KAP publication** for **`45.0%`** of the universe on `2024-04-30` (`overlap = 73.8%`) and `18.6%` on `2024-09-30`. On `kapdates`, cross-sectional statement-age dispersion creates 10–17% CPI-unit mismatch in B3/B4.
   6. **Unscaled sector dispersion overweight (`corr(sector_std, R0_rate) = +0.643`):** Subtracting sector mean without scaling overweights wide-dispersion sectors (`GSYO 34.5%`, `Gayrimenkul 31.3%`, `Holding 26.6%` -> `33.8%` of R0 vs `23.3%` EW). While `Gayrimenkul` and `Holding` dispersion reflects genuine value alpha (`+1.28%` and `+1.41%/yr` full), `GSYO` is the #1 full-sample sector detractor (`-0.15%/yr`, `-0.69%` B3, `-0.24%` B4).

---

## 1. Headline `R0` Performance & Macro Regimes Across the 4 Gauntlet Blocks

| Window | Mo | L75 vs EW net %/yr (NW t) | L75 Gross vs EW | L75 USD CAGR | L75 USD MaxDD | L75 TO / Cost | KAP vs EW net %/yr (NW t) | Mean CPI YoY | Policy / Real Rate | XU100 USD CAGR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **B1 (`2013-04..2016-12`)** | 45 | **+6.90 (+3.39)** | +6.27 | -6.6% | -34.2% | 22.0% / 2.08% | **+9.19 (+3.94)** | 8.0% | 7.3% / -0.7% | -15.6% |
| **B2 (`2017-01..2020-12`)** | 48 | **+3.48 (+0.76)** | +2.60 | +33.4% | -56.6% | 20.8% / 1.78% | **+5.42 (+1.17)** | 13.8% | 13.6% / -0.2% | -2.4% |
| **B3 (`2021-01..2023-12`)** | 36 | **+14.21 (+3.83)** | +13.51 | +16.2% | -35.4% | 19.6% / 1.37% | **+12.21 (+3.44)** | 48.3% | 17.0% / -31.3% | +7.3% |
| **B4 (`2024-01..2026-08`)** | 32 | **+5.56 (+1.15)** | +4.69 | -2.5% | -25.1% | 19.0% / 1.48% | **+4.08 (+1.08)** | 43.6% | 43.7% / +0.0% | -1.4% |
| **Full (`2013-04..2026-08`)** | 161 | **+7.25 (+3.38)** | +6.48 | +10.0% | -56.6% | 20.5% / 1.71% | **+7.73 (+3.86)** | 25.8% | 18.6% / -7.2% | -3.6% |
| Holdout (`2021+`) | 68 | +10.14 (+2.97) | +9.36 | +7.0% | -35.4% | 19.3% / 1.42% | +8.38 (+2.79) | 46.1% | 29.5% / -16.6% | +3.1% |
| IAS 29 (`2024-05+`) | 28 | +2.19 (+0.56) | +1.33 | -9.2% | -25.1% | 18.4% / 1.43% | +2.85 (+0.72) | 40.2% | 43.1% / +2.9% | -6.5% |

*(Note: `L75 vs EW net` exceeds `L75 Gross vs EW` by ~0.7–0.9 pp/yr because the EW universe benchmark also incurs rebalancing costs in `ew_net`.)*

### Annual Calendar & Drawdown Profile (`lag75`)
- **Positive active years (10/14):** `2014 (+10.2%)`, `2015 (+11.0%)`, `2016 (+5.8%)`, `2017 (+10.1%)`, `2018 (+0.9%)`, `2019 (+10.5%)`, `2021 (+20.5%)`, `2022 (+17.5%)`, `2023 (+4.6%)`, `2024 (+13.3%)`, `2025 (+2.8%)` (11 positive, 3 negative: `2013 -1.6%`, **`2020 -7.5%`**, **`2026 YTD -1.9%`**).
- **Major USD drawdowns:**
  - Full: **`-56.65%`** (`2017-12-31` -> `2018-07-31`, Brunson/TRY crisis).
  - `2021+`: **`-35.38%`** (`2022-11-30` -> `2023-05-31`, pre-election uncertainty).
  - `2024+`: **`-25.10%`** (`2025-12-31` -> `2026-08-31`, prolonged high real rates & earnings recession).
- **Worst active months vs `EW net`:** Clustered in two exact regimes — **2020 retail/growth mania** (`2020-08 -4.74%`, `2020-04 -4.28%`, `2020-06 -3.41%`, `2020-09 -2.47%`) and **2024–2026 IAS 29 / disinflation** (`2026-02 -3.87%`, `2024-01 -3.27%`, `2025-11 -2.99%`, `2025-02 -2.95%`, `2025-08 -2.40%`).

---

## 2. Component Ablation (`bm`, `ep`, `sp`, `ey`) Across All 4 Blocks

### 2A. Costed Portfolio Paired `D = net_active(variant) - net_active(R0)` (`lag75`, %/yr & NW t)

| Variant | B1 (`13–16`) | B2 (`17–20`) | B3 (`21–23`) | B4 (`24+`) | Full (`161m`) | KAP Full `D` (t) |
|---|---:|---:|---:|---:|---:|---:|
| `value_z` (no sector neut.) | -2.29 (-2.03) | +1.08 (+0.70) | -2.17 (-1.00) | -0.67 (-0.63) | -0.94 (-1.12) | — |
| `diag_within_sec_z` (mean+std) | +1.29 (+0.84) | -0.23 (-0.17) | -3.47 (-1.80) | -0.88 (-0.51) | -0.66 (-0.76) | — |
| **Single leg: `bm_sn_z`** | -8.18 (-2.98) | **+7.22 (+1.81)** | -7.88 (-2.41) | -1.64 (-0.48) | -2.22 (-0.98) | -2.90 (-1.22) |
| **Single leg: `ep_sn_z`** | -3.07 (-1.55) | **-9.27 (-2.67)** | -3.64 (-1.27) | **+0.34 (+0.18)** | -4.37 (-2.91) | -5.69 (-3.09) |
| **Single leg: `sp_sn_z`** | -1.49 (-0.87) | +2.67 (+0.87) | -4.62 (-1.01) | **-6.57 (-2.34)** | -1.96 (-1.13) | -2.42 (-1.40) |
| **Single leg: `ey_sn_z`** | -1.17 (-0.59) | **-6.78 (-2.78)** | -6.18 (-1.35) | **-4.40 (-2.28)** | -4.61 (-3.06) | -2.71 (-1.93) |
| **LOO: `no_bm`** (`ep+sp+ey`) | +0.92 (+0.47) | -2.90 (-1.52) | -3.67 (-1.65) | -0.45 (-0.21) | -1.52 (-1.38) | -0.86 (-0.75) |
| **LOO: `no_ep`** (`bm+sp+ey`) | **+3.25 (+1.55)** | **+3.89 (+2.60)** | -0.97 (-0.42) | **-2.45 (-1.70)** | +1.36 (+1.26) | +1.78 (+1.61) |
| **LOO: `no_sp`** (`bm+ep+ey`) | -2.29 (-1.22) | **-4.73 (-2.20)** | -0.62 (-0.24) | -2.03 (-0.89) | -2.59 (-2.34) | -1.74 (-1.44) |
| **LOO: `no_ey`** (`bm+ep+sp`) | -0.96 (-0.50) | +2.49 (+0.79) | **-3.50 (-2.04)** | -1.19 (-1.27) | -0.54 (-0.43) | -0.30 (-0.22) |

### 2B. Joint 4-Leg Fama-MacBeth Slopes (ann %/yr, NW t) & Single-Leg Rank-IC

| Block | `bm_sn_z` FM (IC) | `ep_sn_z` FM (IC) | `sp_sn_z` FM (IC) | `ey_sn_z` FM (IC) | `value_sn_z` IC (t) |
|---|---:|---:|---:|---:|---:|
| **B1 (`13–16`)** | +1.53 (+1.28) / `+0.0306` | -1.32 (-0.55) / `+0.0487` | +2.28 (+1.71) / `+0.0222` | **+5.33 (+2.72)** / `+0.0644` | +0.0606 (+4.91) |
| **B2 (`17–20`)** | **+6.84 (+2.33)** / `+0.0535` | **-5.98 (-2.82)** / `+0.0099` | **+3.80 (+3.27)** / `+0.0327` | -2.96 (-0.67) / `+0.0336` | +0.0513 (+3.41) |
| **B3 (`21–23`)** | +4.31 (+1.99) / `+0.0700` | +3.98 (+1.26) / `+0.0631` | **+6.08 (+2.81)** / `+0.0738` | +2.11 (+0.83) / `+0.0757` | +0.0943 (+5.12) |
| **B4 (`24+`)** | +1.61 (+0.36) / `+0.0233` | **+4.51 (+2.06)** / `+0.0430` | +0.21 (+0.08) / `+0.0151` | -1.17 (-1.15) / `+0.0430` | +0.0499 (+2.77) |
| **IAS 29 (`24-05+`)** | +0.07 (+0.02) / `+0.0148` | **+2.45 (+1.29)** / `+0.0333` | -1.12 (-0.38) / `-0.0011` | -1.05 (-0.88) / `+0.0371` | +0.0344 (+2.30) |
| **Full (`161m`)** | **+3.75 (+2.53)** / `+0.0448` | -0.36 (-0.24) / `+0.0392` | **+3.17 (+3.13)** / `+0.0354` | +0.85 (+0.49) / `+0.0535` | +0.0632 (+7.02) |

**Key Ablation Insights:**
- **Sector neutralization pays in 3 of 4 blocks** (`value_z` vs `value_sn_z` loses `-2.29%` B1, `-2.17%` B3, `-0.67%` B4; switcher spread `-9.5%/yr` full).
- **Every leg is regime-specialized:** Asset/top-line legs (`bm`, `sp`) carry R0 when earnings break (B2), whereas earnings legs (`ey` in B1, `ep` in B4) carry R0 under positive real rates / IAS 29. Dropping `ep` wins B1/B2 (`+3.25%/+3.89%`) but loses B3/B4 (`-0.97%/-2.45%`); dropping `sp` loses all 4 blocks (`-2.59%/yr, t = -2.34`).
- **Capital-structure-consistent replacements beat `sp` and `ep` cleanly on IC:**
  - `sp` (`ttm_revenue / mcap`) has **`+0.373` rank correlation with `net_debt/mcap`** (`+0.384` in B4). Replacing it with `rev_ev` (`ttm_revenue / EV`, corr `+0.127`) lifts Full IC `+0.0354 -> +0.0392` and IAS 29 `-0.0011 -> +0.0023`. Replacing it with `gp_ev` (`ttm_gross_profit / EV`) beats `sp` in **every block**: B1 `+0.0527`, B2 `+0.0368`, B3 `+0.0807`, B4 `+0.0298`, IAS 29 `+0.0151`, Full `+0.0497 (+5.7)`.
  - `op_mcap` (`ttm_op_profit / mcap`) beats `ep` in B1 (`+0.0521` vs `+0.0487`), B2 (**`+0.0366` vs `+0.0099`**), B3 (`+0.0752` vs `+0.0631`), IAS 29 (`+0.0337` vs `+0.0333`), and Full (`+0.0504 (+6.2)` vs `+0.0392 (+4.0)`), avoiding below-the-line FX & deferred-tax/NPPKK distortion.

---

## 3. Quintile & Extreme Top-Tail Profile (Why Convexity Matters)

Gross monthly excess return vs EW universe (`%/yr`):

| Block | `T1` (Top 5%) | `T2` (5–10%) | `T3` (10–20%) | `Q2` (20–40%) | `Q5` (Bot 20%) | `T1 − T23` |
|---|---:|---:|---:|---:|---:|---:|
| B1 (`13–16`) | +6.00 | +9.54 | +9.33 | +4.29 | -4.92 | -3.41 |
| B2 (`17–20`) | **+20.73** | +2.65 | **-2.69** | -0.92 | **+5.44** | **+21.64** |
| B3 (`21–23`) | +13.89 | +13.19 | +17.70 | +1.66 | **-15.58** | -2.30 |
| B4 (`24+`) | **+14.96** | +8.33 | **+2.31** | +2.02 | +2.20 | **+10.65** |
| IAS 29 (`24-05+`) | **+9.80** | +4.02 | **+0.10** | +0.41 | **+7.91** | **+8.39** |
| **Full (`161m`)** | **+13.94** | **+8.06** | **+6.22** | +1.70 | -2.80 | **+7.10** |

- **Two distinct tail regimes:** In B1 and B3, value is broad across the full top 20% (`T3 >= T1`). In B2 and B4/IAS 29 — when growth/momentum (`Q5`) rallies (`+5.44%` B2, `+7.91%` IAS 29) — **the 10–20% border half of R0 goes flat/negative (`-2.69%` B2, `+0.10%` IAS 29)** while the deepest 5% still delivers `+14.96%` to `+20.73%/yr`.
- **Diagnostic warning on tail compression:** Replacing linear z-scores with rank (`v_rk_sn`), signed-log (`v_slog_sn`), median (`v_med_sn`), or within-sector percentile rank (`v_wsec_rk_mean`) raises full-sample IC (`+0.0632 -> +0.0662`) but **cuts gross top-20% active return from `+8.6%/yr` down to `+6.4%..+8.1%/yr`**. Even the `4.0%` of R0 picks driven by a single `>= +2σ` leg outperform balanced picks (`+14.52%/yr, t = +1.77` vs `+8.15%/yr`).

---

## 4. Sector Attribution & Concentration

| Block | Gross Active | Brinson Allocation (t) | Brinson Selection (t) | Eff. N Sectors (R0 vs EW) | Small-Sec (`n<5`) wP / wB | Small-Sec R0 ex |
|---|---:|---:|---:|---:|---:|---:|
| B1 (`13–16`) | +8.53 | +1.12 (+1.24) | **+7.41 (+4.37)** | 11.9 vs 16.2 | 23.3% / 23.6% | +15.70 |
| B2 (`17–20`) | +4.49 | **+2.81 (+2.26)** | +1.68 (+0.40) | 11.1 vs 16.1 | 15.5% / 19.9% | +12.26 |
| B3 (`21–23`) | +15.65 | +0.58 (+0.46) | **+15.07 (+3.44)** | 10.8 vs 16.6 | 10.9% / 16.5% | -4.21 |
| B4 (`24+`) | +6.96 | +1.22 (+0.83) | +5.74 (+1.18) | 12.7 vs 16.7 | 7.3% / 9.9% | +1.58 |
| **Full** | **+8.61** | **+1.52 (+2.45)** | **+7.08 (+3.18)** | **11.6 vs 16.3** | **15.0% / 18.2%** | **+7.42** |

- **82% of R0's alpha is within-sector stock selection (`+7.08%`), plus `+1.52% (t = +2.45)` positive sector allocation.**
- **Unscaled sector dispersion skew (`corr(sec_std, R0_rate) = +0.643`):** Because `sector_neutralize` subtracts sector mean without dividing by sector std, high-dispersion sectors are structurally overweight in R0:
  - `Gayrimenkul`: `16.6%` R0 vs `10.6%` EW (`+6.0 pp`, `std = 0.84`, `31.3%` pick rate) -> **#2 full contributor (`+1.28%/yr`; `+3.56%` B3, `+2.83%` B4; `-0.91%` B2)**.
  - `Holding`: `14.6%` R0 vs `11.0%` EW (`+3.6 pp`, `std = 0.80`, `26.6%` pick rate) -> **#1 full contributor (`+1.41%/yr`; positive in all 4 blocks)**.
  - `Girişim Sermayesi Yat. Ort.` (GSYO): `2.5%` R0 vs `1.2%` EW (`std = 1.06`, **`34.5%` pick rate**) -> **#1 full-sample detractor (`-0.15%/yr`; `-0.69%` B3, `-0.24%` B4)**.
  - Meanwhile, low-dispersion industrial sectors (`İmalat 15.4%`, `Kimya 14.2%`, `Çimento 14.2%`, `Perakende 10.7%`) are structurally underweight.
- **Takeaway:** Equalizing sector std (`diag_within_sec_z`: `-0.66%/yr`, B3 `-3.47%`) or equal-weighting sectors (`r4-risk` `risk_sector_ew`: `-1.46%/yr`, B4 `-4.46%`) **hurts**, because `Gayrimenkul` and `Holding` wide valuation spreads carry real selection alpha. Only `GSYO` (venture capital investment trusts whose NAV/book accounting behaves like non-operating financials) is a consistent structural drag.

---

## 5. Size, Liquidity & Style-Factor Loadings

| Block | Size Alloc / Sel | R0 Weight S / M / L | R0 ex vs Own Size Tercile (S / M / L) | `mcap` Hi-Lo in R0 | `vol60_z` (LowVol) | `mom_12_1_z` | `str_1m_z` (1m Loser) | `nd_to_eq` Hi-Lo in R0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B1 (`13–16`) | +1.07 / +7.46 | 43.6 / 38.0 / 18.4% | +10.84 / +2.15 / +14.94 | -8.6 (-1.4) | +0.09 | -0.07 | +0.10 | -4.6 (-0.6) |
| B2 (`17–20`) | -2.60 / +7.09 | 26.6 / 38.6 / 34.8% | **+30.63** / +6.69 / +0.68 | **-39.2 (-3.0)** | +0.30 | -0.21 | +0.13 | +1.5 (+0.2) |
| B3 (`21–23`) | +2.82 / +12.83 | 26.6 / 33.0 / 40.4% | +11.81 / +4.73 / **+17.34** | -0.6 (-0.1) | +0.33 | -0.18 | +0.09 | **+18.4 (+2.5)** |
| B4 (`24+`) | +0.34 / +6.62 | 32.7 / 33.0 / 34.3% | +9.36 / +7.76 / +1.35 | -6.9 (-0.4) | **+0.42** | **-0.26** | **+0.15** | **-13.2 (-2.1)** |
| **Full** | +0.22 / **+8.38** | 32.6 / 36.1 / 31.4% | **+16.66 / +5.19 / +8.52** | **-15.6 (-2.5)** | **+0.27** | **-0.17** | **+0.12** | +0.6 (+0.2) |

- **Size:** R0 is nearly size-neutral overall (`32.6 / 36.1 / 31.4%`), with `97%` of active return from within-size selection (`+8.38%`), NOT small-cap allocation (`+0.22%`). However, within R0, the **smaller half outperforms the larger half in all 4 blocks (`-15.6%/yr, t = -2.5` full; `-39.2%` B2)** — explaining why cap-weighting or size filters (`F1/F2`) destroy R0's B2 performance.
- **Growing unintended style tilts:** R0's **low-vol loading (`vol60_z`)** quadrupled from `+0.09` (B1) to `+0.42` (B4), while its **anti-momentum (`mom_12_1_z`)** deepened to `-0.26` and **1m-loser chasing (`str_1m_z`)** rose to `+0.15`.
- **Two uniform within-R0 spreads across ALL 4 blocks:** Inside R0 top-20%, stocks with **higher trailing 1m return (`str_1m`, NOT crashing)** beat lower by **`+6.1%/yr (t = +1.7)`** (`B1 +10.2%`, `B2 +6.5%`, `B3 +5.1%`, `B4 +0.8%`), and **higher `mom_12_1`** beat lower in all 4 blocks (`+4.4%/yr` full; `+13.0%` B2).
- **Macro leverage flip:** High `net_debt/equity` inside R0 swung from **`+18.4%/yr (t = +2.5)`** in B3 (`-31.3%` real policy rate) to **`-13.2%/yr (t = -2.1)`** in B4 (`0%..+3%` real rate).

---

## 6. IAS 29 Seam Quarters (`2023Q4–2024Q4`) & Accounting Basis Defects

### 6A. Statement-Level Jumps Across `fp/quarterly.parquet`

| Transition | `equity` med [p25, p75] | `total_assets` med | `ttm_revenue` med | `ttm_op_profit` med | `ttm_ni` med (`pos->neg`, `NaN%`) |
|---|---:|---:|---:|---:|---:|
| `2023Q2 -> 2023Q3` (pre-IAS 29) | 1.093 [1.02, 1.19] | 1.089 | 1.171 | 1.136 | 1.048 (10.7%, 8.2%) |
| **`2023Q3 -> 2023Q4` (IAS 29 cliff)** | **1.778** [1.47, 2.31] | **1.498** | **0.630** [0.56, 0.74] | **0.664** [0.49, 0.97] | 0.864 (8.5%, 0.0%) |
| `2023Q4 -> 2024Q1` (bridge TTM) | 1.137 [1.08, 1.18] | 1.135 | 1.145 | 1.181 | 1.174 (6.2%, 3.2%) |
| `2024Q1 -> 2024Q2` | 1.082 | 1.077 | 1.087 | 1.032 | 1.045 (9.4%, 4.1%) |
| `2024Q2 -> 2024Q3` | 1.086 | 1.085 | 1.092 | 1.022 | 1.084 (8.5%, 3.5%) |
| **`2024Q3 -> 2024Q4` (full-yr IAS 29)** | 1.083 | 1.092 | 1.037 | 0.933 (9.9% flip) | **0.664** (**24.7% flip**, **9.6% NaN**) |
| `2024Q4 -> 2025Q1` | 1.079 | 1.087 | 1.071 | 1.038 | 1.054 (12.4%, 7.2%) |

**Three concrete IAS 29 defects proven:**
1. **`2023Q3 -> 2023Q4` asymmetric unit break in `fp/`:** `undo_reexpression` operates only on `period >= 2023Q4`, leaving `2023Q3` vendor rows in next-year restated units (~1.5× inflated) for TL-reexpressed firms (e.g., `TUPRS` `ttm_revenue` drops `1232.8B -> 686.6B`, `ARCLK` `426.5B -> 257.1B`, `BIMAS` `507.5B -> 328.5B`) while USD-functional firms (`EREGL`, `THYAO`) rise smoothly `+13..15%`. Simultaneously, `equity` jumps `1.778×` (`med_bm` jumps `0.26 -> 0.46` in April 2024 on `lag75`). On `kapdates`, `32.9%` of firms switch to `2023Q4` in March 2024 and `55%` in April 2024, mixing two incompatible accounting bases in the same cross-section.
2. **Phase breakdown (`2023–2026`, `lag75`):**
   - `Pre-IAS 29 (2023-01..2024-03)`: R0 gross active `+8.64% (t = +2.23)`, IC `+0.0649`, all 4 legs `+0.039..+0.053`.
   - `Seam (2024-04..2025-04)`: R0 gross active `+6.71% (t = +1.08)`, IC drops to `+0.0341`; `ep` IC slumps to `+0.0113`.
   - `Post-Seam (2025-05..2026-08)`: R0 gross active `+4.91% (t = +0.76)`, IC recovers to `+0.0497` (`ep` surges to `+0.0625`, `ey` `+0.0424`), while **`sp` turns negative (`-0.0040`)** and `bm` weakens (`+0.0134`).
3. **Mixed `reexpression_class` distortion in `2024+`:**

| `reexpression_class` | Tickers | Univ Share | R0 Share | R0 Selection Rate | Mean `value_sn_z` | Univ ex vs EW | R0 ex vs EW |
|---|---:|---:|---:|---:|---:|---:|---:|
| `reexpressed` (TL IAS 29, undone) | 416 | 84.6% | 77.4% | 18.2% | -0.041 | +0.73%/yr | **+8.51%/yr** |
| `unknown` (**left undivided!**) | 32 | 6.7% | **12.9%** | **38.4%** | **+0.293** | +3.88%/yr | +13.81%/yr |
| `not_reexpressed` (FX-functional) | 34 | 7.0% | 7.9% | 22.5% | +0.092 | -6.59%/yr | **-17.24%/yr** |
| `unclassified` | 6 | 1.7% | 1.8% | 20.3% | -0.546 | -23.49%/yr | -14.73%/yr |

Leaving `unknown` tickers undivided systematically inflates their multiples (`bm +0.34, ep +0.41, ey +0.32`), nearly **doubling** their R0 inclusion rate (`38.4%`). Meanwhile, `not_reexpressed` USD/EUR-functional exporters inside R0 lost `-17.24%/yr` under 2024–2026 real TL appreciation.

---

## 7. Staleness Attribution (`lag75` vs `kapdates`)

| Block | `KAP − L75` net %/yr (NW t) | Top-20% Overlap | `KAP` Fresher Rows | `L75` Ahead of `KAP` | Mean Stmt Age (L75 / KAP) | `KAP` New vs Old Stmt R0 ex |
|---|---:|---:|---:|---:|---:|---:|
| B1 (`13–16`) | **+2.29 (+2.15)** | 91.4% | 39.8% | 2.4% | 128.6d / 94.9d | +2.41 / +3.38 |
| B2 (`17–20`) | **+1.94 (+1.32)** | 91.6% | 39.4% | 2.4% | 130.4d / 96.8d | +9.04 / +3.46 |
| B3 (`21–23`) | **-2.00 (-1.78)** | 89.8% | 39.3% | 2.4% | 129.6d / 96.5d | +23.75 / +17.99 |
| B4 (`24+`) | -1.48 (-0.69) | 92.7% | 31.0% | **4.1%** | 131.8d / 107.8d | -4.20 / +4.98 |
| IAS 29 (`24-05+`) | +0.67 (+0.84) | 93.0% | 34.0% | 2.9% | 130.0d / 102.2d | +1.94 / +3.71 |
| **Full (`161m`)** | **+0.48 (+0.57)** | **91.4%** | **37.8%** | **2.7%** | **130.0d / 98.4d** | **+7.62 / +6.87** |

- **Two-sided lag defect:**
  1. In B1–B2 (`2013–2020`), `lag75` is ~33 days staler than actual KAP filings (`39.5%` of rows stale), costing `R0` **`~2.1%/yr`**.
  2. In B4 (`2024-04-30`), SPK's IAS 29 deadline extensions flipped the sign: **`45.0%`** of the liquid universe had **`lag75` ahead of actual KAP publication** (`overlap = 73.8%`, `age L75 = 121d` vs `KAP = 162d`), and `18.6%` on `2024-09-30`! Notably, `2024-04-30` was a massive `+5.66%` R0 active month on `lag75`, explaining why `lag75` beat `kapdates` in B4 (`+5.56%` vs `+4.08%`) while trailing in `IAS 29 2024-05+` (`+2.19%` vs `+2.85%`).
  3. **CPI-unit drift from statement age:** Mean `CPI(date)/CPI(stmt_period_end) - 1` jumped from `3.0%` (B1) and `5.0%` (B2) to **`17.1%` (B3)** and **`12.8%` (B4)**. On `kapdates`, mixed early/late filers in reporting months face 10–15% purely nominal multiple distortion relative to peers.

---

## 8. Entrants vs Holdings vs Exits Decomposition

Monthly gross excess return vs EW (`%/yr`):

| Block | Entrants Wt (`Px / Fil / NewU`, Flicker%) | L75 Entrants (`Px / Fil / NewU`) | L75 Holdings (`7m+`) | L75 Exits | KAP Entrants (`Px / Fil / NewU`) | KAP Holdings |
|---|---:|---:|---:|---:|---:|---:|
| B1 (`13–16`) | 17.3% (`6.8 / 6.2 / 4.3`, 21.2%) | +13.16 (`+7.65 / +29.26 / -14.58`) | +8.86 (+11.89) | +2.25 | +14.61 (`+6.14 / +26.91 / -6.78`) | +10.44 |
| B2 (`17–20`) | 17.1% (`7.8 / 6.6 / 2.7`, 27.1%) | +1.24 (`+5.35 / +35.44 / -29.51`) | +4.36 (+5.15) | -8.16 | -7.57 (`-15.03 / -2.26 / +4.50`) | +7.94 |
| B3 (`21–23`) | 16.0% (`7.1 / 7.0 / 1.9`, 26.8%) | +22.52 (`+35.03 / +1.93 / +8.20`) | +14.97 (+17.43) | -1.32 | +13.19 (`+16.30 / +13.57 / -9.14`) | +12.37 |
| B4 (`24+`) | 16.0% (`6.4 / 6.8 / 2.8`, 23.2%) | +14.88 (`+1.82 / +35.68 / +4.00`) | +4.20 (+6.48) | -12.28 | -0.31 (`-3.65 / +2.44 / +2.24`) | +7.04 |
| **Full** | **16.7%** (`7.1 / 6.6 / 3.0`, **24.6%**) | **+12.03** (`+11.81 / +26.15 / -10.23`) | **+7.95** (+9.97) | **-4.58** | **+4.65** (`-0.76 / +9.72 / -1.91`) | **+9.44** |

- **Long-tenured holdings are NOT value traps:** Stocks held `7+` months earn **`+9.97%/yr`** full (beating overall holdings `+7.95%` in every single block!).
- **Exits are genuinely bad (`-4.58%/yr` full, `-12.28%` B4):** Confirming why holding-period smoothing (`risk_smooth_k3`) and exit buffers lose gross alpha (`-1.02%/yr`).
- **Three distinct entrant classes with wildly different alpha:**
  1. **Filing-driven entrants (`Fil`):** Strongest alpha source (`+26.15%/yr` L75, `+9.72%/yr` KAP).
  2. **Price-driven entrants (`Px`, falling knives on stale fundamentals):** Weak/negative in B2 & B4 (`+1.82%` B4 L75; `-15.03%` B2 and `-3.65%` B4 on KAP; **`-0.76%/yr` full KAP**).
  3. **New-to-liquid-universe entrants (`NewU`, ~1.4 names/mo):** Chronically toxic (`-10.23%/yr` full L75; `-14.58%` B1, `-29.51%` B2; `-1.91%` full KAP), entering right after temporary volume spikes.
- **Boundary churn:** **`24.6%`** of entrants are 1-month "flicker" re-entrants (dropped at `t-1`, re-entered at `t`), contributing to R0's `20.5%/mo` turnover (`1.71%/yr` cost drag).

---

## 9. Summary of Concrete `value_sn` Defects & Guardrails for Round 4 Teams

| Defect | Evidence | Actionable Owner |
|---|---|---|
| 1. `sp` (`Rev/MCap`) leverage & pass-through bias | `+0.373` corr w/ `ND/MCap`, `+2.72` skew, B4 `-6.57%`; `rev_ev` & `gp_ev` beat `sp` on IC | **`vlab`** (H1) |
| 2. `ep` negative left-tail skew & below-the-line noise | `skew -1.30` in B2 (`D = -9.27%`), `p95 = +1.42σ`, `24.7%` 2024Q4 flip; `op_mcap` IC `+0.0504` | **`vlab`** (H2) |
| 3. Current-price falling-knife chasing | `str_1m` & `mom_12_1` Hi-Lo inside R0 positive in all 4 blocks; `Fil` beats `Px` by `+10..14 pp` | **`vlab` / `ml`** (H3) |
| 4. IAS 29 basis mixing, `unknown` 38.4% bias, CPI-age drift | `2023Q3->Q4` `eq 1.78x / rev 0.63x`, `45%` L75 lookahead `2024-04`, `13-17%` CPI drift | **`vlab`** (H4, hygiene) |
| 5. Toxic `NewU` entrants (`-10.2%/yr`) & `GSYO` (`-0.15%/yr`) | `NewU` enters on volume spikes; `GSYO` has `std = 1.06` (`34.5%` rate), worst sector | **`ml` / `vlab`** (H5) |
| **ANTI-DEFECTS (DO NOT BREAK)** | Equal-weight `R0` already beat 8/8 `risk` weighting/smoothing variants; rank/log compression kills top-5% convexity (`+13.94%`); small-cap & `Gayrimenkul/Holding` dispersion are real alpha engines. | All teams |
