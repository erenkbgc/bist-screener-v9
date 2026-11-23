# Skeptic Audit Review: `ml_hgb`

- **Audit Date**: 2026-11-24
- **Role / Branch**: `r4-ml` (`agent/r4-ml`), Batch `ml_batch1` (`N_sel`: `98 -> 100`, `m = 2` variants)
- **Preregistration**: `/home/eren/bist_wt/r4-board/prereg/ml_batch1.md` (`docs/research/round4_ml_batch1_preregistration.md`)
- **Result**: `/home/eren/bist_wt/r4-board/results/ml_hgb.md`
- **Code / Report**: `scripts/research_round4_ml.py`, `tests/test_research_round4_ml_leakage.py`, `data/reports/research_round4_ml_2026-11-24.json`
- **Verdict**: **AUDIT CLEAN — REJECT (`FAIL` 0/6 Gauntlet criteria)**

---

## 1. Procedural, Timestamp & Leakage Audit

| Check | Evidence | Status |
|---|---|---|
| Prereg committed before result | `r4-board/prereg/ml_batch1.md` (`01:02:08.81 +03:00`) and git commit `0b90ac5c` (`01:02:28 +03:00`, updating `trial_ledger.json` `98 -> 100`) strictly precede `results/ml_hgb.md` (`01:07:21.33 +03:00`) and JSON report (`01:07:21.33 +03:00`). | **PASS** |
| Variants run vs. preregistered | Exact `m = 2` variants preregistered (`ml_hgb`, `ml_hgb_blend50`) and run with frozen `HistGradientBoostingRegressor` hyperparameters. No `scratch/` tuning scripts. | **PASS** |
| Causality & leakage audit | Independently ran `pytest tests/test_research_round4_ml_leakage.py` (**6/6 passed**): verified `max_train_date < rebalance_date` and `(train_period + 1) <= rebal_period` on all 129 walk-forward folds (`2016-01-31..2026-09-30`), zero future sector dummy leakage, single-month `log_tlvol60_z`, and bit-exact future-perturbation invariance. | **PASS** |
| Symmetric 2016+ simulation | `EW`, `R0`, `ml_hgb`, and `ml_hgb_blend50` all start symmetrically from cash on `2016-01-31` (`128` realized return months `2016-01..2026-08`). | **PASS** |
| AI attribution / Git hygiene | Zero AI attribution in `0b90ac5c`. Note: `scripts/research_round4_ml.py`, `tests/test_research_round4_ml_leakage.py`, and JSON report are still untracked and must be committed before PR. | **NOTE** |

---

## 2. Gauntlet & Holm Verification

Independent recomputation confirms exact match on two-sided Student-t p-values (`df = 127`) and Holm-Bonferroni (`m = 2`):

| Criterion | Reported | Threshold | Audit Check |
|---|---|---|---|
| (1) Full `2016-01+` `D` (`NW t`) | `-2.46%/yr` (`t = -0.61`) | `D > 0` & `t >= 2.00` | **FAIL** |
| (2) 4-Block `D` (`16` / `17-20` / `21-23` / `24+`) | `-10.33%` / `-1.39%` / `-8.91%` / `+6.16%` | All 4 `> 0` | **FAIL** (3/4 negative) |
| (3) USD MaxDD vs `R0` (Full / `21+`) | `-59.1%` vs `-56.6%` (`-2.50pp`) / `-39.9%` vs `-35.4%` (`-4.50pp`) | Both `>= -2.00pp` | **FAIL** (both worse > 2pp) |
| (4) `kapdates` Full `D` (`NW t`) | `-1.23%/yr` (`t = -0.26`) | `D > 0` & `t >= 1.00` | **FAIL** |
| (5) Holm `p` (`m = 2`) | `1.0000` (raw `0.5430`) | `D > 0` & `< 0.05` | **FAIL** |
| (6) One-way turnover (`xR0`) | `42.77%` vs `20.71%` (`2.06x`, SS `2.11x`) | `<= 1.50x` | **FAIL** |
| DSR (`N_sel = 100`) | `0.0030` vs `R0` `0.0769` | Diagnostic | Inferior |

---

## 3. Skeptic Assessment

- Strictly causal expanding-window `HistGradientBoostingRegressor` learned a strong loading on `vol60_z` (`rank corr = +0.47`) and `value_sn_z` (`+0.46`) and achieved high full-sample Rank-IC (`+0.0801, t = +7.46`), **but** suffered massive portfolio turnover (`42.8%/mo = 2.06x R0`, `30.8 switches/mo`), burning `3.56%/yr` in trading costs (vs `R0` `1.71–1.85%/yr`) and underperforming badly in `2016` (`-10.33%/yr`) and `2021-23` (`-8.91%/yr, t = -2.36`).
- **Recommendation**: **REJECT**.
