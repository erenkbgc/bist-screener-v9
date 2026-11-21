# Agent Report — Research Baseline Owner (P1-1, P1-2, P1-3)

- **Date:** 2026-11-22
- **Branch:** `agent/baseline` (base `5617fbc`; local commits only, never pushed, `master` untouched)
- **Guardrails verified:** `config/live_rule.json`, live scoring (`core/rotation.py`, `core/scoring.py`, `core/live_data.py`), and `data/research/trial_ledger.json` (`N_sel = 86`, reporting-only re-runs) are unchanged.
- **Test suite:** `.venv/bin/pytest tests/ -q` → **520 passed** (0 failed, 0 skipped).

---

## 1. What Was Done

### P1-1 — Promote `data/research/fp/` to default panel & integrate default PIT rebuild into `scripts/build_pit_panel.py`
1. **Backed up previous default panel** (`factors_monthly.parquet`, `factors_monthly_kapdates.parquet`, `quarterly.parquet`, `quarterly_ext.parquet`) to `data/research/pre_point_in_time/`.
2. **Promoted `data/research/fp/` to `data/research/`**:
   - `factors_monthly.parquet` (58,223 rows, lag75; 57,636 `isyatirim_pd` + 587 `price_x_shares`)
   - `factors_monthly_kapdates.parquet` (58,308 rows, actual KAP dates; 57,721 `isyatirim_pd` + 587 `price_x_shares`)
   - `quarterly.parquet` and `quarterly_ext.parquet` (24,089 rows, 576 non-financial tickers; `quarterly_ext.parquet` was previously identical to `quarterly.parquet` and is kept in sync for `research_long_term.py::load()`).
   - Updated `data/research/PANEL_DEFINITION.txt`.
3. **Moved `undo_reexpression` and `bridge_ttm` into `core/pit_panel.py`** (re-exported by `scripts/rebuild_panels_first_published.py` so existing callers and tests stay compatible).
4. **Updated `scripts/build_pit_panel.py`** so a fresh build (or offline `--rebuild` from `data/research/raw/*.pkl`) applies C1 constant-unit TTM, `pit_panel.shares_at` share-count fix, `pit_panel.undo_reexpression`, `pit_panel.bridge_ttm`, and İş Yatırım HisseTekil `PD` (`market_cap_monthly.parquet`) by default without depending on the one-off rebuild scripts. Writes `quarterly.parquet`, `quarterly_ext.parquet`, `factors_monthly.parquet` (lag75), `factors_monthly_kapdates.parquet` (when `kap_archive.parquet` exists), and `PANEL_DEFINITION.txt`.
5. **Exact parity check:** running `scripts/build_pit_panel.py --rebuild --out _verify_pit_rebuild` reproduced `data/research/fp/` identically (`exact_equals=True` across all three parquet files).
6. Added unit tests in `tests/test_undo_reexpression.py` for `core.pit_panel` exports and `build_pit_panel.build_panel_from_raw`.

### P1-2 — Re-run headline studies on the new baseline (reporting only; 0 new trials)
1. **Added HisseTekil `PD` market value for delisted stocks:** added `core/delisted.py::monthly_market_caps` and wired `scripts/research_survivorship.py::delisted_panel` to pass HisseTekil `PD` (from `raw_delisted/*.pkl`) and `cpi` into `pit_panel.build_monthly_factors` / `quarterly_table`, recording `delisted_mcap_source` in the JSON output (`isyatirim_pd`: 3,275 / 3,275; `price_x_shares`: 0). Added unit test in `tests/test_delisted.py`.
2. **Re-ran all 4 headline scripts** on the promoted baseline:
   - `scripts/research_total_return_benchmarks.py` → `data/reports/research_total_return_benchmarks_2026-11-22.json`
   - `scripts/research_quant_review.py` → `data/reports/research_quant_review_2026-11-22.json`
   - `scripts/research_survivorship.py` → `data/reports/research_survivorship_2026-11-22.json`
   - `scripts/research_value_ablation.py` → `data/reports/research_value_ablation_2026-11-22.json`
3. **Documented results** in `docs/research/point_in_time_baseline_2026-11-22.md` and updated `README.md` (status headline, realistic-return benchmark table, research infrastructure description, and scorecard rows; historical pre-registered verdicts preserved on record).

### P1-3 — Forward-record expectation comparison (report only; `config/live_rule.json` untouched)
Compared `config/live_rule.json` → `expectation` against the P1-2 benchmark results and documented the comparison in `docs/research/point_in_time_baseline_2026-11-22.md`.

---

## 2. Numbers Summary (Old C1 Panel vs. Promoted Point-in-Time Baseline)

### A. Total-Return & Costed Benchmarks (`research_total_return_benchmarks.py`, 1M TL, base costs)
| Window / Benchmark | Old C1 %/yr (t) | PIT Baseline %/yr (t) | TE / IR | CAGR Strat vs Bench | PIT Label |
|---|---:|---:|---:|---:|---|
| Holdout `B1` EW universe (zero cost, 68m) | +6.11 (2.29) | **+9.36 (2.74)** | 8.3% / 1.12 | 49.7% vs 36.9% | `BEATS` |
| Holdout `B2` EW universe (costed, 68m) | +6.89 (2.55) | **+10.14 (2.97)** | 8.4% / 1.21 | 49.7% vs 35.9% | `BEATS` |
| Holdout `B3` BIST 100 TR (68m) | −1.71 (−0.28) | **+1.54 (0.30)** | 12.7% / 0.12 | 49.7% vs 48.6% | `AHEAD_NOT_SIGNIFICANT` |
| Holdout `B4` BIST All Shares TR (68m) | −2.11 (−0.44) | **+1.14 (0.28)** | 10.0% / 0.11 | 49.7% vs 49.2% | `AHEAD_NOT_SIGNIFICANT` |
| Holdout XU100 price (dividend-biased, 68m) | +1.04 (0.17) | +4.29 (0.86) | 12.7% / 0.34 | 49.7% vs 44.7% | `AHEAD_NOT_SIGNIFICANT` |
| Discovery `B1` EW universe (zero cost, 93m) | +9.81 (2.47) | **+4.37 (1.67)** | 6.6% / 0.66 | 34.6% vs 29.2% | — |
| Discovery `B2` EW universe (costed, 93m) | +10.58 (2.68) | **+5.14 (1.97)** | 6.6% / 0.78 | 34.6% vs 28.3% | — |

### B. Quant Review (`research_quant_review.py`, `N_sel = 86`)
| Test | Old C1 | PIT Baseline | Label (PIT) |
|---|---|---|---|
| A1 CAPM vs BIST 100 TR (holdout) | α −1.65% (t −0.29), β 1.00 | α **+1.47% (t 0.31)**, β 1.004, R² 0.869 | `POSITIVE_NOT_SIGNIFICANT` |
| A2a Factor model (full, 161m) | α +5.05% (2.24), SMB 0.16 (2.7), LV 0.24 (3.1) | α **+5.07% (3.14)**, SMB 0.004 (0.07), LV 0.245 (4.63) | — |
| A2a Factor model (discovery, 93m) | α +5.95% (2.18), SMB 0.16 (1.5), LV 0.07 (0.8) | α **+4.81% (2.66)**, SMB −0.019 (−0.24), LV 0.116 (1.87) | — |
| A2a Factor model (holdout, 68m) | α +0.89% (0.37), SMB 0.08 (1.5), LV 0.37 (7.8) | α **+4.12% (1.51)**, SMB 0.005 (0.10), LV **0.350 (8.06)** | `EDGE_WEAK_AFTER_CONTROLS` |
| A3 Brinson vs EW (holdout, gross) | sel +8.50% (2.91), alloc −0.29% (−0.29) | sel **+10.68% (2.89)**, alloc +0.88% (0.92) | `SELECTION_DRIVEN` |
| A4 Bank gap (holdout) | raw −1.71%, γ −0.85% (−0.13) | raw **+1.54% (0.30)**, γ +2.36% (0.43), δ −0.080 (−1.97) | `NO_GAP` |
| A5 Bootstrap 95% CI (holdout) | EW net [+1.7, +11.9]%; XU100 TR [−13.8, +10.0]% | EW net **[+3.4, +16.8]%**; XU100 TR **[−8.1, +11.2]%** | — |
| B2 DSR (T = 161, full vs EW net) | SR 0.327; DSR 0.12 (N=75) / 0.10 (N=81) | SR **0.283**, V[SR] 0.02335, SR₀ 0.3785; **DSR 0.103** (N=86) | `NOT_SIGNIFICANT_AFTER_TRIALS` |
| B3 PBO (CSCV, 48 variants, 16 blocks) | PBO 0.056 (logit 1.24), rank 1/48 | PBO **0.0556** (logit 1.79), R0 rank **2/48** (SR 0.341 vs `sue\|0.3` 0.363) | `LOW_OVERFIT_RISK` |
| C Stress `×3 \| 10M \| limit` | disc +5.42% (1.45), hold +3.68% (1.29) | disc **+0.39% (0.15)**, hold **+6.55% (1.80)**, R0 cost 5.07% | `COST_ROBUST_NOT_SIGNIFICANT` |
| C Stress `×3 \| 50M \| limit` | disc +1.00% (0.26), hold +2.18% (0.77) | disc **−4.02% (−1.59)**, hold **+5.19% (1.42)** | — |
| C Break-even cost mult (1M, limit) | > 8 | **> 8** | — |

### C. Survivorship with 39 Delisted Stocks (`research_survivorship.py`, 3,275/3,275 rows HisseTekil `PD`)
| Variant / Spec | Discovery TL %/yr (t) | Holdout TL %/yr (t) | Holdout USD %/yr | Rank IC t (disc / hold) | Verdict |
|---|---:|---:|---:|---:|---|
| `kapdates` baseline | +7.14 (2.71) | +8.62 (2.99) | +8.23 | 5.96 / 4.64 | baseline passes 1–3 |
| `kapdates` **S1** (primary) | **+4.80 (1.84)** | **+8.62 (2.99)** | +8.21 | 6.30 / 4.66 | **`SURVIVORSHIP_FRAGILE`** |
| `kapdates` S5 (all −100%) | +4.98 (1.82) | +8.70 (3.00) | +8.29 | 6.28 / 4.66 | |
| `lag75` baseline | +5.28 (2.14) | +10.75 (3.21) | +10.29 | 5.52 / 4.85 | baseline passes 1–3 |
| `lag75` **S1** | **+3.51 (1.40)** | **+10.78 (3.20)** | +10.31 | 5.84 / 4.87 | **`SURVIVORSHIP_FRAGILE`** |
| `lag75` S5 (all −100%) | +3.96 (1.58) | +10.86 (3.21) | +10.39 | 5.85 / 4.87 | |

### D. Value Ablation (`research_value_ablation.py`, 1M TL, base costs, vs `EW net`)
| Variant | Discovery vs EW net (D vs V0) | Holdout vs EW net (D vs V0) | IAS 29 vs EW net (D vs V0) | Verdict |
|---|---:|---:|---:|---|
| **V0 (`bm+ep+sp+ey`)** | **+5.14% (t 1.97)** | **+10.14% (t 2.97)** | **+2.19% (t 0.56)** | Baseline |
| **V1 (`bm+ep+ey`, no S/P)** | +1.59% (t 0.55) \| **D −3.55% (t −2.41)** | +8.85% (t 2.15) \| **D −1.28% (t −0.73)** | −0.29% (t −0.08) \| **D −2.48% (t −0.98)** | **`KEEP_V0`** |
| **V2 (`bm+ep`)** | +2.42% (t 0.76) \| D −2.71% (t −1.20) | +8.72% (t 2.33) \| D −1.42% (t −1.08) | +1.51% (t 0.30) \| D −0.68% (t −0.33) | **`KEEP_V0`** |

Key finding: on the PIT baseline, `V1` (dropping `S/P`) **no longer beats `V0` in any window** (including Holdout and IAS 29). `sp_sn` discovery Rank-IC rose from +0.0060 (t 0.57) to +0.0276 (t 3.41) and its joint FM slope in discovery is +3.07%/yr (t 3.11).

### E. P1-3 Forward-Record Expectation Comparison (`config/live_rule.json`, NOT modified)
- `config/live_rule.json` expects `metric = "active_univ_gross"`, `ann_pct = 9.36`, `nw_t = 2.74`, `months = 68` (`sigma_eff = 2.348%/mo = 8.13%/yr`; −2σ alert below −6.90% at 12m, −4.28% at 24m, −0.09% at 36m).
- **Exact match** with P1-2 `B1_ew_universe_zero_cost`: **+9.36%/yr, t 2.74, 68 months**.
- `B2_ew_universe_costed` (`active_univ_net`, the primary summary benchmark in `forward_record_report.py`) is **+10.14%/yr, t 2.97, 68 months** (`sigma_eff = 2.346%/mo`; −2σ alert below −6.11% at 12m, −2.71% at 24m, +2.27% at 36m).
- Forward record currently has 1 decision (`2026-11-01`, 47 holdings, 233 universe names) and 0 completed calendar months.

---

## 3. Commits on `agent/baseline`

1. `b1e98ec` — `chore(panel): promote point-in-time panel to baseline and wire build_pit_panel.py defaults (P1-1)`
2. `e8a9037` — `research(baseline): re-run headline studies on PIT baseline, add delisted PD, update README and P1-3 report`
3. *(next commit)* — `docs: add AGENT_REPORT.md for baseline P1-1..P1-3`

---

## 4. Open Problems and Honest Caveats

1. **Discovery weakness & survivorship fragility:** Once rights-adjusted look-ahead is removed, 2013–2020 costed discovery drops to +4.37%/yr gross (t 1.67) / +5.14%/yr costed (t 1.97), and adding the 39 delisted stocks drops discovery t below 2.0 in **both** `kapdates` (+4.80%, t 1.84) and `lag75` (+3.51%, t 1.40) → `SURVIVORSHIP_FRAGILE`. The rule should **not** be re-tuned on this; the forward record from 2026-11 is the decisive clean test.
2. **Multiple testing & index alpha:** At `N_sel = 86`, full-sample DSR is **0.103** (`NOT_SIGNIFICANT_AFTER_TRIALS`). Against BIST 100 total return, holdout active return is +1.54%/yr (t 0.30, CAPM α +1.47%, t 0.31) — statistically zero.
3. **Capacity & cost stress in discovery:** At 50M TL capital with ×2–×3 costs, discovery turns negative (−0.49% to −4.35%/yr); at 10M TL ×3 costs with limit rule, discovery is only +0.39%/yr (t 0.15).
4. **IAS 29 sub-window remains weak:** 2024-05..2026-08 (28m) costed active vs EW net is +2.19%/yr (t 0.56; +1.33% gross, t 0.34).
5. **Data completeness items (tracked under P2):**
   - 33 `unknown` companies in `reexpression_class.parquet` still keep re-expressed vendor values in the IAS 29 window (P2-1).
   - 9 stocks without HisseTekil history still fall back to `price_x_shares` (587 stock-months, ~1.0% of panel; P2-2).
   - Pre-IAS 29 restatements (~1 in 6 to 1 in 5 income items in 2014–2022) remain uncorrected (P2-4).
   - `financials_factors_monthly.parquet` still uses `price × shares` (P2-5).
6. **Gross vs. net alignment in `expectation_check` (P1-3 note):** `config/live_rule.json` checks `active_univ_gross` against `B1` (+9.36%/yr, t 2.74), which is internally consistent, while `forward_record_report.py`'s headline summary uses `active_univ_net` (`B2`, +10.14%/yr, t 2.97). Worth deciding explicitly (without touching `live_rule.json` mid-series) whether to keep `active_univ_gross` or align both to `active_univ_net` at the next formal review.
7. **Stale `config/realized_returns.json`:** `config/realized_returns.json` (used for the bulletin's 6-month realized return reference table in README) predates the PIT baseline promotion and was not touched because config files were off-limits in this role; consider refreshing it via `scripts/realized_return_reference.py` separately if desired.
