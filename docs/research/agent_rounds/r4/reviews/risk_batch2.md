# Skeptic Audit Review: `risk_batch2`

- **Audit Date**: 2026-11-24
- **Role / Branch**: `r4-risk` (`agent/r4-risk`), Batch 2 (`N_sel`: `103 -> 106`, `m = 3` variants)
- **Preregistration**: `/home/eren/bist_wt/r4-board/prereg/risk_batch2.md`
- **Results**: `/home/eren/bist_wt/r4-board/results/risk_batch2.md`
- **Code / Report**: `scripts/research_round4_risk.py`, `data/reports/research_round4_risk_batch2_2026-11-24.json`
- **Overall Audit Verdict**: **AUDIT CLEAN — REJECT ALL 3 VARIANTS (`0/3 PASS`)**

---

## 1. Procedural & Timestamp Audit

| Check | Evidence | Status |
|---|---|---|
| Prereg committed before result | `r4-board/prereg/risk_batch2.md` (`01:02:56.03 +03:00`) and git commit `649fa671` (`01:03:29 +03:00`, updating `trial_ledger.json` `103 -> 106` and freezing Batch 2 builders) strictly precede `r4-board/results/risk_batch2.md` (`01:05:45.78 +03:00`) and JSON report (`01:05:45.78 +03:00`). | **PASS** |
| Variants run vs. preregistered | Exactly 3 variants preregistered (`risk_sector_ew`, `risk_sn_invvol`, `risk_max_div`); 3 variants run and reported. No `scratch/` tuning scripts. | **PASS** |
| Banned repeats check | Unchanged `R0` (`value_sn_z` top-20%) selection; uses sector-equalization, intra-sector inverse-vol, and PIT 126d Ledoit-Wolf Maximum Diversification. | **PASS** |
| AI attribution check | Zero AI attribution tokens in `agent/r4-risk` commits (`871ef8bb`, `649fa671`). | **PASS** |
| Git artifact hygiene | `research_round4_risk_batch1_2026-11-24.json` and `research_round4_risk_batch2_2026-11-24.json` remain untracked; verify committed before final PR. | **NOTE** |

---

## 2. Technical, Lookahead & Gauntlet Verification

- **No lookahead**: `build_batch2_targets` slices daily returns strictly up to `d0(t)` (`ret_d.iloc[max(0, i_d0 - 125) : i_d0 + 1]`) before fitting `LedoitWolf` covariance, and uses trailing 126-day `vol6m` at `d0(t)` for `risk_sn_invvol`.
- **Gauntlet & Holm-Bonferroni check**: Independent recomputation of two-sided Student-t p-values (`df = 160`) and Holm-Bonferroni step-down adjusted p-values (`m = 3`) matches reported values (`0.743330`) to 6 decimal places. (`R0` DSR updated cleanly at `N_sel = 106` -> `0.0787`.)

| Variant | Full `D` (`NW t`) | Blocks (`13-16` / `17-20` / `21-23` / `24+`) | USD DD Diff (Full / `21+`) | `kapdates` `D` (`t`) | Raw `p` / Holm `p` | Turnover (`xR0`) | Failed Rules | Decision |
|---|---:|---|---:|---:|---:|---:|---|---|
| `risk_sector_ew` | -1.46% (-1.16) | -2.02 / -0.40 / +0.48 / -4.46 | +1.20 / +0.40 pp | -0.87% (-0.69) | 0.2478 / 0.7433 | 25.7% (1.25x) | C1, C2, C4, C5 | **REJECT** |
| `risk_sn_invvol` | -0.39% (-0.86) | +0.23 / -2.30 / +0.09 / +1.06 | +0.10 / +0.40 pp | -0.21% (-0.46) | 0.3911 / 0.7433 | 21.3% (1.04x) | C1, C2, C4, C5 | **REJECT** |
| `risk_max_div` | -2.00% (-0.99) | -1.76 / -2.62 / -3.13 / -0.15 | -1.60 / -0.50 pp | -1.56% (-0.73) | 0.3237 / 0.7433 | **35.2% (1.72x)** | C1, C2, C4, C5, C6 | **REJECT** |

---

## 3. Skeptic Assessment

- Equalizing across sectors (`risk_sector_ew`) forced heavy allocation into small single-stock/thinly populated sectors, losing `-4.46%/yr` in `2024+` and `-2.02%/yr` in `2013-16` while raising turnover to `1.25x R0`.
- Sector-neutral inverse-vol (`risk_sn_invvol`) cut the `2017-20` drawdown of cross-sector inverse-vol by more than half (`-5.37%` -> `-2.30%`), **but** still lagged `R0` in `2017-20` (`t = -2.16`) and full period (`-0.39%/yr`).
- Ledoit-Wolf Maximum Diversification (`risk_max_div`) chased noisy 126-day covariance inversions, spiking turnover to `35.2%` (`1.72x R0`, failing C6) and costs to `3.19%/yr` (vs `R0` `1.71%/yr`), losing in every single block.
- **Conclusion across all 8 `r4-risk` trials (`N_sel = 98 -> 106`)**: **0/8 PASS**. Equal-weighting across `R0` (`value_sn_z` top-20%) remains superior to all tested weighting, capping, inverse-vol, smoothing, and covariance-optimization schemes.
