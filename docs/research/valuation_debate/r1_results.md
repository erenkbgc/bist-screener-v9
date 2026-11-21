# Valuation Round 1 — Confirmatory Backtest Results (`S1`, `M2`, `FV1`)

**Date:** 2026-11-22  
**Branch:** `agent/valuation`  
**Role:** Backtest Engineer  
**Pre-registration:** [`docs/research/valuation_round1_preregistration.md`](../docs/research/valuation_round1_preregistration.md)  
**Runner script:** [`scripts/research_valuation_round1.py`](../scripts/research_valuation_round1.py)  
**Unit tests:** [`tests/test_valuation_round1.py`](../tests/test_valuation_round1.py)  
**Report JSON:** [`data/reports/research_valuation_round1_2026-11-22.json`](../data/reports/research_valuation_round1_2026-11-22.json)  
**Updated Trial Ledger (`data/research/trial_ledger.json`):** `N_sel = 89` (`86 + 3` stock-selection trials; cross-variant monthly Sharpe variance $V[\widehat{\text{SR}}] = 0.02335$, expected maximum null monthly Sharpe $\text{SR}_0 = 0.3804$).

---

## 1. Executive Summary & Verbatim Fixed Pass Rule Verdict

> **FIXED PASS RULE:** candidate monthly top-20% portfolio vs R0 `value_sn` top-20%, same universe, liquidity cut, 1M TL costs and next-close fills as `scripts/research_portfolio_backtest.py`. Paired $D = \text{net active}(\text{candidate}) - \text{net active}(R0)$. PASS iff $D > 0$ in discovery 2013–2020 with $\text{NW } t(D) \ge 1.0$ AND $D > 0$ in holdout 2021+ with $\text{NW } t(D) \ge 2.0$ AND holdout USD max drawdown not worse than R0 by more than 2 pp. Also report DSR at the updated `N_sel`. Every method tested adds `+1` to `N_sel` in the trial ledger, PASS or FAIL.

**Overall Outcome:** **0 of 3 methods PASS (`S1: FAIL`, `M2: FAIL`, `FV1: FAIL`).** Because no method passed, `debate/PASS` was **not** created, and `config/live_rule.json` (`R0-2026-10-12`) remains the live rule.

| Method ID | Track | Discovery $D$ %/yr ($t$) [req: $>0, t \ge 1.0$] | Holdout $D$ %/yr ($t$) [req: $>0, t \ge 2.0$] | Holdout USD Max DD % ($\Delta$ vs `R0` `-35.4%`) [req: $\ge -37.4\%$] | Full-Sample Monthly $\widehat{\text{SR}}$ vs `EW net` | DSR (`N_sel = 89`, $\text{SR}_0 = 0.3804$) | Final Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| **`R0` (`value_sn`)** | Baseline (`R0-2026-10-12`) | — *(vs `EW net`: +5.14%, t 1.97)* | — *(vs `EW net`: +10.14%, t 2.97)* | **−35.4%** *(0.0 pp)* | **0.2830** | **0.0986** | **Baseline** |
| **`S1` (`S1_value_eb_ns`)** | Statistical / Cross-Sectional | **−2.13%** (**−1.39**) ❌ | **−0.78%** (**−0.52**) ❌ | **−35.2%** (**+0.2 pp**) ✅ | 0.2081 | **0.0099** | **`FAIL`** |
| **`M2` (`M2_value_real_spread_sn`)** | EM / Turkey Macro-Adjusted | **+0.45%** (**+0.25**) ❌ *($t < 1.0$)* | **−2.52%** (**−1.69**) ❌ | **−36.4%** (**−1.0 pp**) ✅ | 0.2529 | **0.0540** | **`FAIL`** |
| **`FV1` (`FV1_reoi_ev_sn`)** | Fundamental Valuation | **−1.30%** (**−0.74**) ❌ | **−1.59%** (**−0.82**) ❌ | **−37.8%** (**−2.4 pp**) ❌ | 0.2252 | **0.0241** | **`FAIL`** |

---

## 2. Detailed Primary Results (`factors_monthly.parquet`, `lag75`, 2013-04 to 2026-09)

### 2.1 Costed Portfolio Performance Across All Windows (1M TL Real Capital, Base Costs, Next-Close Fills)

| Method | Window | Months | Active vs `EW net` %/yr ($t$) | Active vs `EW gross` %/yr ($t$) | Paired $D$ vs `R0` %/yr ($t$) | CAGR TL % | CAGR USD % | CAGR Real % | Max DD TL % | Max DD USD % | 1-Way Turnover % | Cost Drag %/yr | Avg Names (Coverage %) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **`R0`** | Discovery | 93 | +5.14 (+1.97) | +4.37 (+1.67) | — | 34.60% | 12.26% | 20.65% | −26.0% | −56.6% | 21.4% | 1.92% | 42.7 (100.0%) |
| | Holdout | 68 | +10.14 (+2.97) | +9.36 (+2.74) | — | 49.69% | 7.02% | 2.59% | −25.3% | −35.4% | 19.3% | 1.42% | 59.2 (100.0%) |
| | IAS 29 (`2024-05+`) | 28 | +2.19 (+0.56) | +1.33 (+0.34) | — | 8.75% | −9.15% | −17.66% | −18.6% | −25.1% | 18.4% | 1.43% | 68.7 (100.0%) |
| | Full | 161 | +7.25 (+3.38) | +6.48 (+3.01) | — | 40.78% | 10.02% | 12.66% | −26.0% | −56.6% | 20.5% | 1.71% | 49.7 (100.0%) |
| **`S1_value_eb_ns`** | Discovery | 93 | +3.00 (+0.94) | +2.24 (+0.70) | **−2.13 (−1.39)** | 32.03% | 10.12% | 18.34% | −26.9% | −54.9% | 20.7% | 1.79% | 42.7 (100.0%) |
| | Holdout | 68 | +9.35 (+2.34) | +8.58 (+2.15) | **−0.78 (−0.52)** | 48.83% | 6.40% | 2.00% | −24.7% | −35.2% | 19.5% | 1.43% | 59.2 (100.0%) |
| | IAS 29 (`2024-05+`) | 28 | +1.94 (+0.40) | +1.08 (+0.22) | −0.25 (−0.12) | 8.59% | −9.28% | −17.78% | −15.6% | −23.4% | 18.7% | 1.41% | 68.7 (100.0%) |
| | Full | 161 | +5.69 (+2.20) | +4.92 (+1.90) | −1.56 (−1.45) | 38.88% | 8.53% | 11.14% | −26.9% | −54.9% | 20.2% | 1.63% | 49.7 (100.0%) |
| **`M2_value_real_spread_sn`** | Discovery | 93 | **+5.58 (+1.70)** | **+4.82 (+1.46)** | **+0.45 (+0.25)** | 35.31% | 12.85% | 21.28% | −25.8% | −55.8% | 20.3% | 1.84% | 42.7 (100.0%) |
| | Holdout | 68 | +7.62 (+2.19) | +6.84 (+1.97) | **−2.52 (−1.69)** | 45.96% | 4.35% | 0.03% | −24.6% | −36.4% | 19.0% | 1.41% | 59.2 (100.0%) |
| | IAS 29 (`2024-05+`) | 28 | −0.17 (−0.04) | −1.03 (−0.25) | −2.36 (−0.92) | 6.31% | −11.19% | −19.51% | −18.0% | −24.7% | 18.3% | 1.46% | 68.7 (100.0%) |
| | Full | 161 | +6.44 (+2.66) | +5.68 (+2.34) | −0.80 (−0.62) | 39.71% | 9.18% | 11.80% | −25.8% | −55.8% | 19.8% | 1.66% | 49.7 (100.0%) |
| **`FV1_reoi_ev_sn`** | Discovery | 93 | +3.83 (+1.21) | +3.07 (+0.97) | **−1.30 (−0.74)** | 33.12% | 11.03% | 19.32% | −26.5% | −53.2% | 20.9% | 1.93% | 41.7 (97.61%) |
| | Holdout | 68 | +8.55 (**+3.13**) | +7.77 (+2.83) | **−1.59 (−0.82)** | 47.25% | 5.27% | 0.92% | −23.8% | −37.8% | 20.2% | 1.55% | 58.8 (99.19%) |
| | IAS 29 (`2024-05+`) | 28 | **+3.73 (+0.89)** | **+2.87 (+0.67)** | **+1.55 (+0.51)** | 10.26% | −7.89% | −16.52% | −19.8% | −26.1% | 19.8% | 1.62% | 68.1 (99.00%) |
| | Full | 161 | +5.83 (+2.63) | +5.06 (+2.27) | −1.42 (−1.09) | 38.92% | 8.56% | 11.17% | −26.5% | −53.2% | 20.6% | 1.77% | 48.9 (98.41%) |

### 2.2 Cross-Sectional Rank-IC and Switcher Analysis (`lag75`)

| Method | Window | Spearman Rank-IC ($t$) | Paired $\Delta\text{IC}$ vs `R0` ($t$) | Mean Rank Corr vs `R0` | Top-20% Overlap % | Switches / mo | Switcher Spread: Entrants − Dropouts %/yr ($t$) |
|---|---|---:|---:|---:|---:|---:|---:|
| **`R0`** | Discovery / Holdout / IAS 29 | +0.0558 (5.52) / +0.0734 (4.85) / +0.0344 (2.30) | — | 1.0000 | 100.00% | 0.00 | — |
| **`S1_value_eb_ns`** | Discovery (93m) | **+0.0566 (+5.39)** | +0.0008 (+0.32) | 0.9143 | 78.15% | 9.32 | −12.77% (−1.62) |
| | Holdout (68m) | **+0.0793 (+4.90)** | **+0.0058 (+1.88)** | 0.9078 | 79.11% | 12.51 | 0.00% (0.00) |
| | IAS 29 (28m) | **+0.0363 (+2.19)** | +0.0019 (+0.40) | 0.9063 | 77.65% | 15.32 | +5.24% (+0.53) |
| **`M2_value_real_spread_sn`** | Discovery (93m) | +0.0555 (**+5.77**) | −0.0003 (−0.09) | 0.9273 | 82.47% | 7.48 | −3.33% (−0.29) |
| | Holdout (68m) | +0.0676 (+4.58) | −0.0058 (−1.54) | 0.9108 | 80.04% | 11.94 | −14.19% (−1.94) |
| | IAS 29 (28m) | +0.0332 (+2.42) | −0.0012 (−0.23) | 0.9001 | 78.66% | 14.57 | −5.96% (−0.63) |
| **`FV1_reoi_ev_sn`** | Discovery (93m) | +0.0544 (**+6.47**) | −0.0014 (−0.46) | 0.8509 | 72.68% | 11.40 | −0.72% (−0.14) |
| | Holdout (68m) | +0.0666 (+4.43) | −0.0068 (−1.65) | 0.8588 | 72.29% | 16.49 | −4.32% (−0.71) |
| | IAS 29 (28m) | +0.0298 (+2.30) | −0.0046 (−0.56) | 0.8553 | 70.95% | 19.75 | +3.76% (+0.41) |

---

## 3. Sensitivity Results (`factors_monthly_kapdates.parquet`, Actual KAP Publication Dates)

| Method | Discovery vs `EW net` %/yr ($t$) | Discovery $D$ vs `R0` %/yr ($t$) | Holdout vs `EW net` %/yr ($t$) | Holdout $D$ vs `R0` %/yr ($t$) | Holdout USD Max DD ($\Delta$ vs `R0`) | Rank-IC Discovery / Holdout ($t$) | DSR (`N_sel = 89`) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **`R0` (`value_sn`)** | +7.25 (+2.68) | — | +8.38 (+2.79) | — | −35.5% (0.0 pp) | +0.0571 (5.96) / +0.0748 (4.64) | 0.1464 | Baseline |
| **`S1` (`S1_value_eb_ns`)** | +4.49 (+1.44) | −2.76 (−1.68) | **+9.44 (+2.31)** | **+1.06 (+0.67)** | **−33.6% (+1.9 pp)** | **+0.0592 (5.73) / +0.0815 (4.77)** | 0.0306 | **`FAIL`** |
| **`M2` (`M2_value_real_spread_sn`)** | +7.04 (+2.18) | −0.21 (−0.11) | +6.08 (+1.95) | −2.30 (−1.84) | −37.4% (−1.9 pp) | +0.0573 (6.20) / +0.0660 (4.33) | 0.0568 | **`FAIL`** |
| **`FV1` (`FV1_reoi_ev_sn`)** | +4.64 (+1.79) | −2.60 (−1.40) | +6.85 (+2.60) | −1.53 (−0.96) | −38.1% (−2.6 pp) | +0.0568 (7.28) / +0.0649 (4.13) | 0.0179 | **`FAIL`** |

---

## 4. Diagnostic Post-Mortem: Why Each Pre-Registered Failure Mode Materialized

1. **`S1` (`S1_value_eb_ns` — Statistical Track):**
   - **What worked:** Per-leg Blom normal scores + 2-stage Empirical-Bayes sector location & scale shrinkage improved full-cross-section Spearman Rank-IC in **every window on both panels** (`+0.0793` vs `+0.0734` in `lag75` Holdout, $\Delta\text{IC}\ t = +1.88$; `+0.0815` vs `+0.0748` in `kapdates` Holdout, $\Delta\text{IC}\ t = +1.98$), and beat `R0` in `kapdates` Holdout portfolio return ($D = +1.06\%/\text{yr}, t = +0.67$, switcher spread $+12.24\%/\text{yr}, t = +1.74$) while reducing Holdout USD max drawdown on both panels (`-35.2%` on `lag75`, `-33.6%` on `kapdates`).
   - **Why it failed the top-20% portfolio rule:** In Discovery (2013–2020), `S1`'s entrants underperformed `R0`'s dropouts by $-12.77\%/\text{yr}$ ($t = -1.62$), producing $D = -2.13\%/\text{yr}$ ($t = -1.39$). Confirming Failure Mode #1 in [`debate/r1_proposal_statistical.md`](r1_proposal_statistical.md) and the Referee's §3.1.5 critique, BIST's 2013–2020 top-quintile value premium relied heavily on cardinal right-tail deep-value convexity (`B/M` and `S/P` outliers) and wider dispersion in Holdings/REITs; rank-normalizing the tails improved rank accuracy across the middle of the distribution (`Rank-IC`) but pruned high-upside deep-value rebounds from the top 20%.
2. **`M2` (`M2_value_real_spread_sn` — EM / Turkey Macro Track):**
   - **What worked:** In Discovery (`lag75`), `M2` was the **only candidate to post a positive costed active return edge over `R0`** ($D = +0.45\%/\text{yr}, t = +0.25$; $+5.58\%/\text{yr}$ vs $+5.14\%/\text{yr}$ vs `EW net`), reduced turnover (`20.3%` vs `21.4%` in Discovery; `19.0%` vs `19.3%` in Holdout), improved Discovery USD max drawdown (`-55.8%` vs `-56.6%`), and increased Discovery Rank-IC $t$-statistic (`5.77` vs `5.52`).
   - **Why it failed:** Discovery $t(D) = +0.25$ fell below the $1.0$ threshold, and in Holdout `M2` lagged `R0` by $D = -2.52\%/\text{yr}$ ($t = -1.69$, switcher spread $-14.19\%/\text{yr}, t = -1.94$). Confirming Failure Modes #1, #3, and #4 in [`debate/r1_proposal_macro.md`](r1_proposal_macro.md), during Turkey's 2021–2023 negative-real-rate inflation boom, domestic TL borrowers benefited massively from negative real TL interest rates (`-40%` to `-60%`), whereas `M2` charged their net debt at the `~9–10%` USD Eurobond yield, delevered `S/P` into `S/EV`, and discarded below-EBIT `ttm_ni_parent` (associate income and cheap-credit gains).
3. **`FV1` (`FV1_reoi_ev_sn` — Fundamental Valuation Track):**
   - **What worked:** `FV1` achieved the highest Discovery Rank-IC $t$-statistic ($t = 6.47$ on `lag75`, $t = 7.28$ on `kapdates`), the highest Holdout active return $t$-statistic against `EW net` ($t = 3.13$, $+8.55\%/\text{yr}$), the lowest Discovery USD max drawdown (`-53.2%`, $+3.4\text{ pp}$ better than `R0`), and **outperformed `R0` in the `2024-05+` IAS 29 sub-window by $D = +1.55\%/\text{yr}$ ($t = +0.51$)** ($+3.73\%/\text{yr}$ vs $+2.19\%/\text{yr}$ vs `EW net`).
   - **Why it failed:** Confirming Failure Mode #1 in [`debate/r1_proposal_fundamental.md`](r1_proposal_fundamental.md) and the Referee's §3.3.4 critique, dropping the `S/P` revenue anchor in a 2-pillar (`NOA/EV`, `ey`) operating valuation lost $-1.30\%/\text{yr}$ ($t = -0.74$) in Discovery and $-1.59\%/\text{yr}$ ($t = -0.82$) across full Holdout, and worsened Holdout USD max drawdown to $-37.8\%$ ($-2.4\text{ pp}$ vs `R0`'s $-35.4\%$, failing the $\le 2.0\text{ pp}$ drawdown guardrail).
