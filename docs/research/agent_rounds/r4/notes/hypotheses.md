# Round 4 Ranked Mechanism-First Hypotheses (`vlab` / `ml` / `risk`)

**Author**: `r4-regime` (Regime & Attribution Lab)  
**Date**: 2026-11-24  
**Basis**: Grounded strictly in diagnostic attribution (`notes/regime_attribution.md`, `data/reports/r4_regime_attribution_2026-11-24.json`). Zero candidate backtests were optimized or pre-screened on gauntlet returns.  
**Team status note**: `r4-risk` has already completed 2 batches (`0/8 PASS`, see `notes/risk_lessons.md`), confirming that pure re-weighting/smoothing/inv-vol/sector-EW on unchanged `R0` picks does not clear the 4-block gauntlet. Therefore, all 5 hypotheses below target **signal & valuation construction (`vlab`)** and **tail-preserving non-linear modeling (`ml` Batch 2)**, strictly avoiding all banned repeats (`profitability/quality/accruals/SUE tilts`, `learned IC weights`, `dividend yield`, `foreign ownership`, `KAP flags`, `size/liquidity filters`, `stops/exit buffers`, `entry timing`, `macro/calendar timing`, plus Round 1–2 `S1/M2/FV1/V2A/V2B/V1/V2`).

---

## Gauntlet Target Reality Check (Why Passing Requires a *Structural* Repair)

To pass the Round 4 Gauntlet, a candidate must beat `R0` (`+7.25%/yr`) with `NW t >= 2.0` full, `D > 0` in **each of 4 wildly different blocks** (`B1 2013–16`, `B2 2017–20`, `B3 2021–23`, `B4 2024+`), hold on `kapdates` (`D > 0, t >= 1.0`), preserve USD MaxDD (`<= +2pp` worse), keep turnover `<= 1.5x R0`, and clear Holm `p < 0.05`.

Diagnostic attribution showed **three non-negotiable rules** for any candidate to survive all 4 blocks:
1. **Preserve top-5% deep-value convexity** (`T1_top5 = +13.94%/yr` vs `T3_10_20 = +6.22%/yr`). Never compress the right tail with rank-averaging, Blom normal scores, or equal-std sector scaling — all raise full-sample IC while cutting top-20% returns.
2. **Preserve multi-leg regime hedging.** Never drop a leg outright (`no_ep` fails B3/B4; `no_sp` fails B1–B4; `no_bm` fails B2–B4; `no_ey` fails B1/B3/B4). **Repair broken legs in place** rather than diluting `value_sn` with an unrelated secondary tilt.
3. **Avoid sign-flipping macro factors** (e.g., leverage/accruals flipped from `+18.4%` in B3 to `-13.2%` in B4; volatility flipped from `+28.0%` in B2 to `-17.5%` in B3).

---

## Ranked Hypotheses (Max 5)

### Rank 1 (`vlab`): Capital-Structure-Consistent Top-Line Valuation — Replace `S/P` (`Rev/MCap`) with `Rev/EV` or `GP/EV`
- **Target Owner**: `vlab` (Batch 1 priority — 2 clean variants).
- **Concrete Defect Repaired**: `sp = ttm_revenue / mcap` is the only leg in `value_sn` with a **numerator–denominator capital-structure mismatch** (`S/P = (Rev/EV) × (1 + NetDebt/MCap)`). This induces `+0.373` rank correlation with `net_debt/mcap` (`+0.384` in B4), extreme right-tail skewness (`+2.72` full, `+3.01` B4), and pass-through distributor bias. When real rates turned positive in B4, `sp_sn_z` cratered (`D = -6.57%/yr, t = -2.34`; IAS 29 IC `-0.0011`), yet dropping `sp` (`no_sp`) fails in B1 (`-2.29%`) and B2 (`-4.73%`).
- **Mechanism-First Formulation (Frozen, Zero Free Params)**:
  - **H1a (`val_rev_ev`)**: Exact `R0` 4-leg formula (`bm`, `ep`, `rev_ev`, `ey`), replacing `sp = ttm_revenue / mcap` with `rev_ev = ttm_revenue / EV` (`EV = mcap + fin_debt - cash > 0`, same EV definition as `ey`). Pure valuation denominator repair; zero profitability content.
  - **H1b (`val_gp_ev`)**: Exact `R0` 4-leg formula (`bm`, `ep`, `gp_ev`, `ey`), replacing `sp` with `gp_ev = ttm_gross_profit / EV` (enterprise value-added yield — a valuation multiple removing both leverage inflation and zero-margin pass-through sales, *not* a profitability `GP/Assets` tilt). Diagnostic single-leg SN Rank-IC beats `sp` in **all 4 blocks + IAS 29** (`+0.0527/+0.0368/+0.0807/+0.0298`, IAS 29 `+0.0151`, Full `+0.0497` vs `sp` `+0.0354`).
- **Gauntlet Blocks Helped & Why**:
  - **B1 (`13–16`) & B4 (`24+`):** Strongest expected lift — positive/tight real rates punish the indebted, low-margin pass-through firms that `sp` over-selects.
  - **B2 (`17–20`):** Preserves the top-line anchor needed when `ep` breaks in 2018 while trimming leveraged distress.
  - **B3 (`21–23`):** Highest-risk block (leveraged firms rallied in B3), *but* both `rev_ev` (`+0.0758`) and `gp_ev` (`+0.0807`) beat `sp` (`+0.0738`) on Rank-IC even in B3. Turnover remains `~1.0x R0`.

---

### Rank 2 (`vlab`): Repair `E/P` Left-Tail Skewness & Below-the-Line Noise (`op_mcap` or Positive-Floor `ep`)
- **Target Owner**: `vlab` (Batch 1 — 2 clean variants, optionally combined with H1 in Batch 2).
- **Concrete Defect Repaired**: `ep` is the only leg with heavy negative skewness (`skew = -0.52` full, `-1.30` B2; `p01 = -3.77σ` vs `p95 = +1.42σ`). Deep one-off accounting/FX translation losses stretch `std(ep)`, compressing positive `ep_z` scores and causing `ep_sn_z` to lose `-9.27%/yr (t = -2.67)` in B2 (`FM = -5.98%, t = -2.82`). Meanwhile in B4 (`2024Q4`), `ttm_ni` suffered a `24.7%` positive-to-negative flip rate under IAS 29 NPPKK/deferred-tax noise (vs `9.9%` for `ttm_op_profit`), and unscreened `ep < 0` picks (`13.7%` of R0 in B4) lost `-9.99%/yr` vs `+9.84%/yr` for `ep > 0`.
- **Mechanism-First Formulation (Frozen, Zero Free Params)**:
  - **H2a (`val_op_mcap`)**: Replace `ep` (`ttm_ni / mcap`) in the 4-leg composite with `op_mcap = ttm_op_profit / mcap` (pre-FX, pre-NPPKK, pre-deferred-tax operating earnings yield to equity). Diagnostic single-leg SN Rank-IC beats `ep` in B1 (`+0.0521` vs `+0.0487`), **B2 (`+0.0366` vs `+0.0099`)**, B3 (`+0.0752` vs `+0.0631`), IAS 29 (`+0.0337` vs `+0.0333`), and Full (`+0.0504, t=+6.2` vs `+0.0392, t=+4.0`). *(Check correlation with `ey = op_profit / EV`: `op_mcap` is equity-level while `ey` is enterprise-level; consider pairing with H1b `gp_ev` so the 4 legs are `bm`, `op_mcap`, `gp_ev`, `ey` or keeping `bm`, `op_mcap`, `rev_ev`, `ey`.)*
  - **H2b (`val_ep_floor0`)**: Keep `ep` in all 4 legs, but floor negative `ep` at `0.0` (i.e., `max(ep, 0)` before winsorize+z) so extreme negative loss-makers do not distort `std(ep)` and compress the profitable right tail, while still ranking loss-makers below every profitable firm.
- **Gauntlet Blocks Helped & Why**:
  - **B2 (`17–20`):** Directly repairs R0's single biggest leg failure (`ep` `-9.27%/yr` in 2018 FX crisis).
  - **B1 (`13–16`) & B3 (`21–23`):** `op_mcap` improves Rank-IC in both blocks (`+0.0034` and `+0.0121`), and `ep_floor0` restores `ep`'s upside weight in `value_z`.
  - **B4 (`24+`):** Avoids IAS 29 `2024Q4` net-income NPPKK/deferred-tax noise while still separating operating profit makers from cash-burners.

---

### Rank 3 (`vlab` / `ml`): Value–Momentum Synergy & Falling-Knife Disentanglement (Separating Fundamental Value from Price Crashes)
- **Target Owner**: `vlab` (Batch 1/2) and `ml` (Batch 2 feature/interaction design).
- **Concrete Defect Repaired**: Updating `mcap` monthly on static quarterly statements makes `R0` systematically anti-momentum (`mom_12_1_z = -0.17` full, `-0.26` B4) and a 1-month loser chaser (`str_1m_z = +0.12` full, `+0.15` B4). Two independent diagnostics confirm this drags across **all 4 blocks**:
  1. Inside R0 top-20%, stocks with **higher `str_1m`** (not crashing) beat lower in **every block** (`B1 +10.2%`, `B2 +6.5%`, `B3 +5.1%`, `B4 +0.8%`, Full `+6.1%/yr, t = +1.7`), and **higher `mom_12_1`** also beats lower in **every block** (`B1 +1.2%`, `B2 +13.0%`, `B3 +0.6%`, `B4 +0.5%`, Full `+4.4%/yr`).
  2. **Filing-driven entrants** (`+26.15%/yr` L75, `+9.72%/yr` KAP) vastly beat **price-driven entrants** (`+11.81%` L75, `-0.76%` KAP; `-15.03%` B2 and `-3.65%` B4 on KAP).
  - *(Why NOT banned? This is cross-sectional Value+Momentum portfolio construction / fundamental-vs-price value decomposition — NOT intra-month entry timing or stops. Note standalone `mom_12_1` is weak in BIST precisely because it is negatively correlated with `value_sn`, classic Asness-Moskowitz-Pedersen 2013 synergy!)*
- **Mechanism-First Formulation**:
  - **H3a (`vlab`, `val_mom_sn`)**: Small, fixed sector-neutral `mom_12_1` synergy leg added *without* diluting `value_sn`'s right tail — e.g., `0.85 * value_sn_z + 0.15 * mom_12_1_sn_z` (frozen weight; `mom_12_1` has far lower turnover than `str_1m`, keeping turnover `<= 1.2x R0`).
  - **H3b (`vlab`, `val_anti_crash`)**: Asymmetric crash-penalty ONLY on extreme price-crash / falling-knife entrants (e.g., penalize `min(0, mom_12_1_sn_z)` or `min(0, str_1m_sn_z)` with frozen weight `0.15`, leaving non-crashing deep-value convexity 100% untouched!). This avoids the Round 3 mistake where symmetric linear tilts rewarded right-tail momentum outliers at the expense of deep-value incumbents.
- **Gauntlet Blocks Helped & Why**:
  - **B2 (`17–20`):** Directly addresses R0's worst year (`2020 -7.5%` growth/momentum surge; `mom_12_1` Hi-Lo inside R0 `+13.0%/yr`).
  - **B1 (`13–16`), B3 (`21–23`), B4 (`24+`):** Positive spread inside R0 in all 3 remaining blocks; cushions B4's `-0.26` negative momentum loading and helps USD MaxDD during protracted selloffs.

---

### Rank 4 (`vlab` Data Hygiene Layer + Structural Test): Enterprise-Consistent Value + IAS 29 Cross-Sectional Hygiene (`CPI-Age Alignment` & `Basis Stratification`)
- **Target Owner**: `vlab` (as a clean composite in Batch 2, or paired with H1/H2).
- **Concrete Defect Repaired**:
  1. **Cross-sectional IAS 29 basis mixing (`2024-03..2024-04` on `kapdates`)**: `equity` jumped `1.778×` while `ttm_revenue` dropped `0.630×` at `2023Q3 -> 2023Q4`; standardizing across mixed nominal + IAS 29 filers distorts ranks during transition months.
  2. **Cross-sectional CPI-age drift (`17.1%` B3, `12.8%` B4)**: On `kapdates` (and for special-FY tickers on `lag75`), firms in the same month carry statements aged 35 to 190+ days; under 40–70% annual inflation, staler statements suffer 10–15% purely nominal multiple compression.
  3. **Accumulated earnings & balance-sheet hygiene**: `ret_mcap` (`retained / mcap`, 100% coverage, Full IC `+0.0420, t=+4.2`, B3 `+0.0782`, IAS 29 `+0.0267`) and `eq_ev` (`equity / EV`, Full IC `+0.0388, t=+6.4`, positive in all 4 blocks & IAS 29 `+0.0209`) offer cleaner capital-structure scaling than raw `bm` during debt-heavy cycles.
- **Mechanism-First Formulation**:
  - **Hygiene operator**: Scale nominal ratios by published `CPI(t - 1m) / CPI(stmt_period_end)` (strictly PIT: TÜİK publishes `t-1m` CPI on the 3rd of month `t`) and stratify standardization by accounting basis (`stmt_period >= 2023Q4` vs `< 2023Q4` when both have `>= 20` stocks).
  - **Important Gauntlet Warning**: Because `lag75` has near-zero cross-sectional statement-age dispersion in B1–B3 (`p90 - p10 = 0.0%`), CPI-age alignment + IAS 29 stratification alone will move **`kapdates` (Check 4)** and **B4** more than `lag75` B1–B3. Pair it with H1/H2 (e.g., **Enterprise-Consistent 4-Leg Value: `eq_ev` or `bm` + `op_mcap` + `gp_ev` + `ey` + CPI-age alignment**) rather than burning a standalone trial expecting `t >= 2.0` on `lag75` 2013–2020.
- **Gauntlet Blocks Helped & Why**:
  - **B4 (`24+`) & `kapdates` (all blocks):** Eliminates mixed-regime transition distortion and filing-timing CPI bias; `eq_ev` / `gp_ev` / `op_mcap` stabilize B4 and `kapdates` simultaneously.

---

### Rank 5 (`ml` Batch 2): Top-Tail Residual ML Anchored to `value_sn_z` with Basis-Invariant Valuation & Price-Structure Features
- **Target Owner**: `ml` (Batch 2 — after seeing `ml_batch1` results).
- **Concrete Defect Repaired**:
  1. Standard cross-sectional ML trained on all ~250 stocks optimizes mid-distribution Rank-IC, which Round 3 (`miner_qgp_surp_real`: `dIC = +0.0077, t = +2.88` yet `D = -2.13%`) and our diagnostic rank-compression tests (`v_rk_sn`: IC `+0.0662` yet top-20% `-1.1%/yr`) proved **does not translate to top-20% portfolio alpha** when deep-value convexity lives in the top 5%.
  2. Including YoY balance-sheet/quarter-flow deltas (`ΔNOA`, `q_*` surprises) creates guaranteed IAS 29 `2023Q4–2024Q4` seam blowups.
  3. Small, surgical toxic pockets inside R0 — specifically **newly-liquid-universe entrants (`NewU`, `-10.23%/yr` full L75)**, **`ep < 0` + high-leverage in tight-rate regimes**, and **price-crash vs filing-jump entrants** — are inherently **non-linear interactions** that linear tilts cannot isolate without diluting R0's top-5% core.
- **Mechanism-First Formulation (`ml` Batch 2)**:
  - **Target & Loss**: Train walk-forward (strictly expanding causal window, `>= 36m` warmup, purged 1m gap) to predict **within-top-40% (or top-weighted) excess return**, OR output a **bounded residual adjustment `score = value_sn_z + λ * clip(ml_pred_z, -1, +1)`** (e.g. `λ = 0.25`, frozen) so `value_sn_z`'s top-5% convexity and turnover (`<= 1.3x R0`) are structurally protected.
  - **Safe Feature Set (strictly basis-invariant & free of IAS 29 YoY cliffs)**:
    - Capital-structure-consistent valuation legs: `bm_sn_z`, `ep_sn_z`, `op_mcap_sn_z`, `rev_ev_sn_z`, `gp_ev_sn_z`, `ey_sn_z`, `ret_mcap_sn_z`, `eq_ev_sn_z`, `value_sn_z`.
    - Price-vs-fundamental structure: `mom_12_1_z`, `str_1m_z`, `vol60_z`, `is_new_stmt` (statement updated this month), `in_prev_univ` (flags toxic `NewU` entrants!), `log_mcap_z` (interaction only — do NOT filter out small caps!).
    - **Explicitly EXCLUDE**: all YoY `ΔNOA` / accruals, all unbridged `q_*` YoY surprises, raw nominal TL levels, and `sue` (all break at `2023Q4`).
- **Gauntlet Blocks Helped & Why**:
  - **B2 (`17–20`) & B4 (`24+`):** Learns non-linear interactions between `ep < 0` / `sp` leverage / falling knives (`mom_12_1`, `str_1m`) / `NewU` entrants without over-correcting B1 & B3.
  - **B1 (`13–16`) & B3 (`21–23`):** Anchoring to `value_sn_z` with bounded residual prevents the tree from abandoning deep-value convexity during B3's broad value rally.

---

## Quick Reference Matrix for `vlab` & `ml`

| Rank | Owner | Mechanism | Primary Blocks Helped | Main Watchout |
|---:|---|---|---|---|
| **1** | `vlab` | Replace `sp` (`Rev/MCap`) with `rev_ev` (`Rev/EV`) or `gp_ev` (`GP/EV`) | B1, B4 (IAS 29), B2 | B3 leverage rally (IC still higher!) |
| **2** | `vlab` | Repair `ep`: `op_mcap` (`OpProfit/MCap`) or `ep_floor0` (`max(ep,0)`) | B2 (`ep` `-9.27%`), B1, B4 | Overlap w/ `ey` (`op_mcap` vs `op/EV`) |
| **3** | `vlab` / `ml` | Asymmetric falling-knife penalty / `0.85*value_sn + 0.15*mom_12_1_sn` | All 4 blocks (esp. B2, B1) | Turnover & B3 dilution if weight > 0.20 |
| **4** | `vlab` | CPI-age alignment + IAS 29 basis stratification (paired w/ H1/H2) | B4, `kapdates` Check 4 | Small `lag75` effect in B1–B3 alone |
| **5** | `ml` (B2) | Top-tail residual ML on basis-invariant valuation + `in_prev_univ`/`is_new_stmt` | B2, B4, Full | Avoid YoY `ΔNOA`/`q_*` & mid-IC dilution |
