# Skeptic Audit Review: `ml_hgb_blend50`

- **Audit Date**: 2026-11-24
- **Role / Branch**: `r4-ml` (`agent/r4-ml`), Batch `ml_batch1` (`N_sel`: `98 -> 100`, `m = 2` variants)
- **Preregistration**: `/home/eren/bist_wt/r4-board/prereg/ml_batch1.md` (`docs/research/round4_ml_batch1_preregistration.md`)
- **Result**: `/home/eren/bist_wt/r4-board/results/ml_hgb_blend50.md`
- **Code / Report**: `scripts/research_round4_ml.py`, `tests/test_research_round4_ml_leakage.py`, `data/reports/research_round4_ml_2026-11-24.json`
- **Verdict**: **AUDIT CLEAN — REJECT (`FAIL` 5/6 Gauntlet criteria)**

---

## 1. Procedural, Timestamp & Leakage Audit

- **Timestamps**: Prereg `r4-board/prereg/ml_batch1.md` (`01:02:08.81`) and commit `0b90ac5c` (`01:02:28`, `N_sel 98 -> 100`) strictly precede `results/ml_hgb_blend50.md` (`01:07:21.33`).
- **Leakage**: `compute_blend50_score` uses single-month `rank_average_combo(df, "ml_hgb", "value_sn_z", weight_a=0.5, require_both=True)` on already-verified causal `ml_hgb` predictions (`6/6` leakage unit tests pass; 129 folds strictly `max_train_date < rebalance_date`).
- **No hidden tuning**: Exact 2 preregistered variants run (`ml_hgb`, `ml_hgb_blend50`); zero `scratch/` files; zero banned repeats.

---

## 2. Gauntlet & Holm Verification

| Criterion | Reported | Threshold | Audit Check |
|---|---|---|---|
| (1) Full `2016-01+` `D` (`NW t`) | `+0.01%/yr` (`t = +0.00`) | `D > 0` & `t >= 2.00` | **FAIL** |
| (2) 4-Block `D` (`16` / `17-20` / `21-23` / `24+`) | `-0.86%` / `+0.50%` / `-1.74%` / `+1.56%` | All 4 `> 0` | **FAIL** (2/4 negative) |
| (3) USD MaxDD vs `R0` (Full / `21+`) | `-57.0%` vs `-56.6%` (`-0.40pp`) / `-35.4%` vs `-35.4%` (`+0.00pp`) | Both `>= -2.00pp` | **PASS** |
| (4) `kapdates` Full `D` (`NW t`) | `+0.38%/yr` (`t = +0.16`) | `D > 0` & `t >= 1.00` | **FAIL** |
| (5) Holm `p` (`m = 2`) | `1.0000` (raw `1.0000`) | `D > 0` & `< 0.05` | **FAIL** |
| (6) One-way turnover (`xR0`) | `32.07%` vs `20.71%` (`1.55x`, SS `1.57x`) | `<= 1.50x` | **FAIL** |
| DSR (`N_sel = 100`) | `0.0476` vs `R0` `0.0769` | Diagnostic | Inferior |

---

## 3. Skeptic Assessment

- `ml_hgb_blend50` demonstrates the exact same Rank-IC vs. top-20% portfolio disconnect seen in Round 3: it raised full-sample Rank-IC by `+0.0196` (`NW t = +3.48`) over `R0`, **yet** delivered zero net active gain (`D = +0.01%/yr`, `t = +0.00`), lower DSR (`0.0476` vs `0.0769`), and failed the `1.50x` turnover cap (`32.07% = 1.55x R0`, `2.58%/yr` cost).
- **Recommendation**: **REJECT**.
