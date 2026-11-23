# Skeptic Audit Review: `risk_batch1`

- **Audit Date**: 2026-11-24
- **Role / Branch**: `r4-risk` (`agent/r4-risk`), Batch 1 (`N_sel`: `98 -> 103`, `m = 5` variants)
- **Preregistration**: `/home/eren/bist_wt/r4-board/prereg/risk_batch1.md`
- **Results**: `/home/eren/bist_wt/r4-board/results/risk_batch1.md`
- **Code / Report**: `scripts/research_round4_risk.py`, `tests/test_research_round4_risk.py`, `data/reports/research_round4_risk_batch1_2026-11-24.json`
- **Overall Audit Verdict**: **AUDIT CLEAN — REJECT ALL 5 VARIANTS (`0/5 PASS`)**

---

## 1. Procedural & Timestamp Audit

| Check | Evidence | Status |
|---|---|---|
| Prereg committed before result | `r4-board/prereg/risk_batch1.md` (`01:01:05.67 +03:00`) and git commit `871ef8bb` (`01:01:21 +03:00`, updating `trial_ledger.json` `98 -> 103` and freezing harness) strictly precede `r4-board/results/risk_batch1.md` (`01:01:48.49 +03:00`) and JSON report (`01:01:48.49 +03:00`). | **PASS** |
| Variants run vs. preregistered | Exactly 5 variants preregistered (`risk_score_rank`, `risk_score_exp_cap`, `risk_invvol`, `risk_smooth_k3`, `risk_invvol_smooth_k3`); 5 variants run and reported. No `scratch/` tuning scripts. | **PASS** |
| Banned repeats check | Unchanged `R0` (`value_sn_z` top-20%) selection; uses score-weighting, name/sector caps, PIT 6m inverse-vol, and staggered `K=3` cohort smoothing (no banned exit/rank buffers). | **PASS** |
| AI attribution check | Zero AI attribution tokens in `agent/r4-risk` commits (`871ef8bb`). | **PASS** |
| Git artifact hygiene | Note: `data/reports/research_round4_risk_batch1_2026-11-24.json` is not yet committed (working tree has Batch 2 edits in progress); must be committed before PR. | **NOTE** |

---

## 2. Technical, Lookahead & Gauntlet Verification

- **Simulator parity & unit tests**: Ran `pytest tests/test_research_round4_risk.py` independently -> **5/5 passed**. `simulate_weighted` matches `core/portfolio_backtest.py::simulate` to `1e-12` under equal weights.
- **No lookahead**: `build_pit_vol6m` uses strictly trailing 126-day std up to `d0(t)`. `smooth_cohorts` checks finite close on `d0(t)` before carrying prior-cohort weights.
- **Gauntlet & Holm-Bonferroni check**:
  - `R0` baseline matches our independent run to exact precision (`161` months `2013-04-30..2026-08-31`, `vs_ew_net = +7.25%/yr`, `NW t = +3.38`, USD maxDD `-56.6%` full / `-35.4%` `2021+`, turnover `20.5%`, `DSR(103) = 0.0817`).
  - Independent recomputation of two-sided Student-t p-values (`df = 160`) and Holm-Bonferroni step-down adjusted p-values (`m = 5`) matches the reported values to 6 decimal places.

| Variant | Full `D` (`NW t`) | Blocks (`13-16` / `17-20` / `21-23` / `24+`) | USD DD Diff (Full / `21+`) | `kapdates` `D` (`t`) | Raw `p` / Holm `p` | Turnover (`xR0`) | Failed Rules | Decision |
|---|---:|---|---:|---:|---:|---:|---|---|
| `risk_score_rank` | +1.60% (+1.49) | -0.68 / +5.79 / -1.34 / +1.82 | +0.40 / -0.40 pp | +1.39% (+1.32) | 0.1382 / 0.4203 | 21.6% (1.05x) | C1, C2, C5 | **REJECT** |
| `risk_score_exp_cap` | +1.45% (+1.32) | +0.47 / +5.26 / -1.62 / +0.58 | -0.30 / **-2.20 pp** | +1.55% (+1.29) | 0.1887 / 0.4203 | 21.3% (1.04x) | C1, C2, C3, C5 | **REJECT** |
| `risk_invvol` | -1.27% (-1.63) | +0.16 / -5.37 / +0.97 / +0.37 | +0.20 / +0.70 pp | -1.07% (-1.38) | 0.1051 / 0.4203 | 21.3% (1.04x) | C1, C2, C4, C5 | **REJECT** |
| `risk_smooth_k3` | -0.30% (-0.54) | +0.10 / +0.33 / -1.34 / -0.63 | +0.60 / +0.00 pp | +0.12% (+0.19) | 0.5899 / 0.5899 | 13.2% (0.64x) | C1, C2, C4, C5 | **REJECT** |
| `risk_invvol_smooth_k3` | -1.69% (-1.92) | -0.24 / -5.06 / -0.20 / -0.35 | +0.50 / +0.60 pp | -1.24% (-1.11) | 0.0566 / 0.2832 | 13.4% (0.65x) | C1, C2, C4, C5 | **REJECT** |

---

## 3. Skeptic Assessment

- Weighting toward deeper `value_sn_z` (`risk_score_rank`, `risk_score_exp_cap`) boosted `2017-20` (`+5.79%` / `+5.26%/yr`) and slightly raised full-period Sharpe (`0.73 -> 0.76`), **but** lost in `2021-23` (`-1.34%` / `-1.62%`) and worsened `2021+` USD maxDD for `exp_cap` (`-2.20pp`, breaching the `2.00pp` limit).
- Inverse-volatility (`risk_invvol`) severely hurt `2017-20` (`-5.37%/yr, t=-3.81`) by under-weighting volatile deep-value cyclicals during the value recovery.
- Staggered `K=3` cohort smoothing (`risk_smooth_k3`) cut turnover by `36%` (`20.5% -> 13.2%`) and costs (`1.71% -> 0.99%/yr`), **but** still trailed `R0` net (`-0.30%/yr`) due to stale-rank drag in `2021-23` (`-1.34%`) and `2024+` (`-0.63%`).
- **Recommendation**: **REJECT** all 5 Batch 1 variants; `R0` remains undefeated.
