# Point-in-time baseline promotion and headline re-runs (2026-11-22)

Reporting update for plan items **P1-1**, **P1-2**, and **P1-3** (`docs/plan_2026-10-26.md`). **No new trials are added to `data/research/trial_ledger.json` (`N_sel = 86` unchanged), and `config/live_rule.json` (`R0-2026-10-12`) and live scoring are unchanged.**

## P1-1: Panel promotion and default rebuild pipeline

The point-in-time panel built in `data/research/fp/` (`first_published_panel.md`, `market_cap_source.md`) is now the default research baseline in `data/research/`:

- **Backup:** previous default files (`factors_monthly.parquet`, `factors_monthly_kapdates.parquet`, `quarterly.parquet`, `quarterly_ext.parquet`) were copied to `data/research/pre_point_in_time/`.
- **Promoted files:** `data/research/fp/factors_monthly.parquet` (58,223 rows, lag75), `factors_monthly_kapdates.parquet` (58,308 rows, actual KAP dates), and `quarterly.parquet` (24,089 rows, 576 non-financial tickers; also synced to `quarterly_ext.parquet`).
- **`data/research/PANEL_DEFINITION.txt`** updated to record the point-in-time definition (C1 + `shares_at` fix + IAS 29 `undo_reexpression` + `bridge_ttm` + İş Yatırım HisseTekil `PD` market value; backups in `c0/`, `pre_share_fix/`, `pre_point_in_time/`).
- **`core/pit_panel.py` & `scripts/build_pit_panel.py`:** `undo_reexpression` and `bridge_ttm` moved to `core/pit_panel.py` (re-exported by `scripts/rebuild_panels_first_published.py` for compatibility). `scripts/build_pit_panel.py` now applies C1, `shares_at`, `undo_reexpression`, `bridge_ttm`, and İş Yatırım `PD` by default, writes both `factors_monthly.parquet` (lag75) and `factors_monthly_kapdates.parquet`, and supports `--rebuild` for offline rebuilds from `data/research/raw/*.pkl`.
- **Parity check:** `scripts/build_pit_panel.py --rebuild --out _verify_pit_rebuild` reproduced `data/research/fp/` identically (`exact_equals=True` across `factors_monthly.parquet`, `factors_monthly_kapdates.parquet`, and `quarterly.parquet`).

---

## P1-2: Headline studies re-run on the point-in-time baseline

All four scripts were re-run on the promoted baseline (reporting only; original pre-registered verdicts stay on record).

### 1. Total-return and costed benchmarks (`scripts/research_total_return_benchmarks.py`)

Output: `data/reports/research_total_return_benchmarks_2026-11-22.json` (1M TL real capital, base costs, next-close fills, 2013-04 → 2026-09).

**Holdout (2021-01 → 2026-08, 68 months):**

| Benchmark | Old C1 panel %/yr (t) | PIT baseline %/yr (t) | TE / IR | CAGR strat vs bench | Label (PIT) |
|---|---:|---:|---:|---:|---|
| B1 EW universe, zero cost | +6.11 (2.29) | **+9.36 (2.74)** | 8.3% / 1.12 | 49.7% vs 36.9% | `BEATS` |
| **B2 EW universe, same costs** | +6.89 (2.55) | **+10.14 (2.97)** | 8.4% / 1.21 | 49.7% vs 35.9% | **`BEATS`** |
| **B3 BIST 100 total return** | −1.71 (−0.28) | **+1.54 (0.30)** | 12.7% / 0.12 | 49.7% vs 48.6% | **`AHEAD_NOT_SIGNIFICANT`** |
| B4 BIST All Shares total return | −2.11 (−0.44) | **+1.14 (0.28)** | 10.0% / 0.11 | 49.7% vs 49.2% | `AHEAD_NOT_SIGNIFICANT` |
| *XU100 price (no dividends)* | *+1.04 (0.17)* | *+4.29 (0.86)* | *12.7% / 0.34* | *49.7% vs 44.7%* | *`AHEAD_NOT_SIGNIFICANT`* |

**Discovery (2013-04 → 2020-12, 93 months):**

| Benchmark | Old C1 panel %/yr (t) | PIT baseline %/yr (t) | CAGR strat vs bench |
|---|---:|---:|---:|
| B1 EW universe, zero cost | +9.81 (2.47) | **+4.37 (1.67)** | 34.6% vs 29.2% |
| B2 EW universe, same costs | +10.58 (2.68) | **+5.14 (1.97)** | 34.6% vs 28.3% |

Reading: against BIST 100 TR the holdout point estimate flips from −1.71%/yr to +1.54%/yr (t 0.30), which is still statistically indistinguishable from zero (12.7% tracking error). Against its own costed EW universe, holdout strengthens (+6.89% → +10.14%/yr, t 2.97), while discovery falls below t = 2 (+5.14%/yr, t 1.97; +4.37%, t 1.67 vs gross EW).

### 2. Quant review follow-ups: attribution, multiple testing, cost stress (`scripts/research_quant_review.py`)

Output: `data/reports/research_quant_review_2026-11-22.json`.

**Labels (old C1 → PIT):**
- `A1`: `NO_ALPHA` → **`POSITIVE_NOT_SIGNIFICANT`**
- `A2a`: `EDGE_WEAK_AFTER_CONTROLS` → **`EDGE_WEAK_AFTER_CONTROLS`**
- `A3`: `SELECTION_DRIVEN` → **`SELECTION_DRIVEN`**
- `A4`: `GAP_PERSISTS` → **`NO_GAP`**
- `B2`: `NOT_SIGNIFICANT_AFTER_TRIALS` → **`NOT_SIGNIFICANT_AFTER_TRIALS`**
- `B3`: `LOW_OVERFIT_RISK` → **`LOW_OVERFIT_RISK`**
- `C`: `COST_ROBUST_NOT_SIGNIFICANT` → **`COST_ROBUST_NOT_SIGNIFICANT`**

| Metric | Old C1 (N_sel = 75 / 81) | PIT baseline (N_sel = 86) |
|---|---|---|
| A1 CAPM vs BIST 100 TR (holdout) | α −1.65%/yr (t −0.29), β 1.00, R² 0.85 | α **+1.47%/yr (t 0.31)**, β 1.004 (t 14.55), R² 0.869 |
| A2a Factor model (full, 161m) | α +5.05%/yr (t 2.24), SMB 0.16 (2.7), LV 0.24 (3.1) | α **+5.07%/yr (t 3.14)**, SMB 0.004 (0.07), LV 0.245 (4.63) |
| A2a Factor model (discovery, 93m) | α +5.95%/yr (t 2.18), SMB 0.16 (1.5), LV 0.07 (0.8) | α **+4.81%/yr (t 2.66)**, SMB −0.019 (−0.24), LV 0.116 (1.87) |
| A2a Factor model (holdout, 68m) | α +0.89%/yr (t 0.37), SMB 0.08 (1.5), LV 0.37 (7.8) | α **+4.12%/yr (t 1.51)**, SMB 0.005 (0.10), LV **0.350 (8.06)** |
| A2b + HML_sn (holdout) | α −0.48%/yr (t −0.29), HML_sn 0.39 (9.7) | α **+1.48%/yr (t 0.79)**, HML_sn 0.359 (7.41), LV 0.140 (3.49) |
| A3 Brinson vs EW (holdout, gross) | selection +8.50% (2.91), alloc −0.29% (−0.29) | selection **+10.68% (2.89)**, alloc +0.88% (0.92) |
| A4 Bank gap (holdout) | raw −1.71%, γ −0.85% (−0.13), δ −0.08 (−1.92) | raw **+1.54% (0.30)**, γ +2.36% (0.43), δ −0.080 (−1.97) |
| A5 Bootstrap 95% CI (holdout) | vs EW net [+1.7, +11.9]%; vs BIST 100 TR [−13.8, +10.0]% | vs EW net **[+3.4, +16.8]%**; vs BIST 100 TR **[−8.1, +11.2]%** |
| B2 DSR (T = 161, full vs EW net) | SR 0.327, V[SR] 0.029; DSR 0.12 (N=75) / 0.10 (N=81) | SR **0.283**, V[SR] 0.02335, SR₀ 0.3785; **DSR 0.103** (N=86) |
| B3 PBO (CSCV, 48 variants, 16 blocks) | PBO 0.056 (logit 1.24), R0 rank 1/48 | PBO **0.0556** (logit 1.79), R0 (`value_sn\|0.2`) rank **2/48** (SR 0.341; behind `sue\|0.3` 0.363) |
| C Stress `×3 \| 10M \| limit` | disc +5.42% (1.45), hold +3.68% (1.29), R0 cost 5.38% | disc **+0.39% (0.15)**, hold **+6.55% (1.80)**, R0 cost 5.07% |
| C Stress `×3 \| 50M \| limit` | disc +1.00% (0.26), hold +2.18% (0.77) | disc **−4.02% (−1.59)**, hold **+5.19% (1.42)** |
| C Break-even cost mult (1M, limit) | > 8 | **> 8** |

Reading:
- Removing the rights-adjustment bias eliminated the apparent small-cap (`SMB`) tilt completely (SMB loading 0.16 → 0.004).
- Holdout factor-adjusted alpha improves from +0.89% to +4.12%/yr (t 1.51), but remains non-significant because the low-volatility loading (`LV` = 0.35, t 8.06) still explains a large share of holdout returns.
- Full-sample monthly active Sharpe drops (0.327 → 0.283) because discovery weakened; at `N_sel = 86`, DSR is **0.103** (`NOT_SIGNIFICANT_AFTER_TRIALS`). PBO stays low at **0.056** (`LOW_OVERFIT_RISK`).
- Under cost stress (`×3`, 10M TL, limit rule), holdout is stronger (+6.55%/yr, t 1.80) but discovery nearly vanishes (+0.39%/yr, t 0.15) and turns negative at 50M TL (−4.02%/yr).

### 3. Survivorship with 39 delisted stocks (`scripts/research_survivorship.py`)

Output: `data/reports/research_survivorship_2026-11-22.json`. All 3,275 of 3,275 delisted stock-months (39 delisted stocks with statements, 32 entering the prepared liquid panel) now use İş Yatırım HisseTekil `PD` (`core/delisted.py::monthly_market_caps`; `isyatirim_pd`: 3,275, `price_x_shares`: 0).

| Variant / Spec | Discovery TL %/yr (t) | Holdout TL %/yr (t) | Holdout USD %/yr | Rank IC t (disc / hold) | Delisted pick share | Verdict |
|---|---:|---:|---:|---:|---:|---|
| **kapdates** baseline | +7.14 (2.71) | +8.62 (2.99) | +8.23 | 5.96 / 4.64 | 0.00% | baseline passes rules 1–3 |
| **kapdates S1** (primary) | **+4.80 (1.84)** | **+8.62 (2.99)** | +8.21 | 6.30 / 4.66 | 3.19% (2 corp, 0 other) | **`SURVIVORSHIP_FRAGILE`** |
| kapdates S5 (all −100%) | +4.98 (1.82) | +8.70 (3.00) | +8.29 | 6.28 / 4.66 | 3.19% | |
| **lag75** baseline | +5.28 (2.14) | +10.75 (3.21) | +10.29 | 5.52 / 4.85 | 0.00% | baseline passes rules 1–3 |
| **lag75 S1** | **+3.51 (1.40)** | **+10.78 (3.20)** | +10.31 | 5.84 / 4.87 | 3.32% (1 corp, 0 other) | **`SURVIVORSHIP_FRAGILE`** |
| lag75 S5 (all −100%) | +3.96 (1.58) | +10.86 (3.21) | +10.39 | 5.85 / 4.87 | 3.32% | |

Reading:
- Both `kapdates` and `lag75` now classify as **`SURVIVORSHIP_FRAGILE`**, for a **different reason than before**: on the old C0/C1 panels, `kapdates` hovered near t = 2 in *holdout* (1.94 on C0, 2.26 on C1). On the point-in-time baseline, **holdout is strong in both variants** (+8.62% t 2.99 kapdates; +10.78% t 3.20 lag75), and **discovery** fails t > 2 once the 39 delisted stocks are added (+7.14% → +4.80%, t 1.84 in kapdates; +5.28% → +3.51%, t 1.40 in lag75).
- As before, exit-return assumptions (S1–S5) barely matter (0 failure exits held in the top quintile; 1–2 corporate merger exits `SODA`/`TRKCM`), and Rank IC t actually *rises* when delisted stocks are added (5.96 → 6.30 in kapdates discovery). The −1.8 to −2.3%/yr discovery drag comes from delisted value traps while still listed.

### 4. Value component ablation (`scripts/research_value_ablation.py`)

Output: `data/reports/research_value_ablation_2026-11-22.json` (1M TL, base costs, next-close fills, vs `EW net`).

| Variant | Window | Rank-IC (t) | ΔIC vs V0 (t) | Active vs EW net %/yr (t) | Paired D vs V0 %/yr (t) | Switcher spread %/yr (t) | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| **V0 (`bm+ep+sp+ey`)** | Discovery | +0.0558 (5.52) | — | **+5.14 (1.97)** | — | — | Baseline |
| | Holdout | +0.0734 (4.85) | — | **+10.14 (2.97)** | — | — | |
| | IAS 29 (28m) | +0.0344 (2.30) | — | **+2.19 (0.56)** | — | — | |
| **V1 (`bm+ep+ey`, no S/P)** | Discovery | +0.0507 (5.15) | −0.0051 (−1.48) | +1.59 (0.55) | **−3.55 (−2.41)** | −19.46 (−2.34) | **`KEEP_V0`** |
| | Holdout | +0.0707 (4.91) | −0.0027 (−0.79) | +8.85 (2.15) | **−1.28 (−0.73)** | −5.16 (−0.52) | |
| | IAS 29 (28m) | +0.0409 (2.71) | +0.0065 (+2.11) | −0.29 (−0.08) | **−2.48 (−0.98)** | −8.23 (−0.68) | |
| **V2 (`bm+ep`)** | Discovery | +0.0429 (4.99) | −0.0129 (−2.85) | +2.42 (0.76) | −2.71 (−1.20) | −11.69 (−1.70) | **`KEEP_V0`** |
| | Holdout | +0.0625 (4.53) | −0.0109 (−2.32) | +8.72 (2.33) | −1.42 (−1.08) | −4.17 (−0.80) | |
| | IAS 29 (28m) | +0.0329 (2.43) | −0.0015 (−0.33) | +1.51 (0.30) | −0.68 (−0.33) | −2.88 (−0.44) | |

Reading:
- On true market values, `sp_sn` is no longer weak in discovery: standalone discovery Rank-IC rose from +0.0060 (t 0.57) to **+0.0276 (t 3.41)** and its joint 4-leg FM slope is **+3.07%/yr (t 3.11)**.
- **`V1` (dropping `S/P`) no longer outperforms `V0` in costed portfolio returns in ANY window** — not even in holdout (D −1.28%/yr, t −0.73; previously +1.95%/yr) or IAS 29 (D −2.48%/yr, t −0.98; previously +2.37%/yr, t 1.95). Although `V1` still posts a slightly higher cross-sectional Rank-IC in IAS 29 (+0.0065, t 2.11), its top-quintile entrants underperform its dropouts in every window.
- Both `V1` and `V2` remain **`KEEP_V0`**, and the previous motivation to treat `V1` as an outperforming IAS 29 shadow composite disappears on the corrected panel.

---

## P1-3: Forward-record expectation comparison (report only; `config/live_rule.json` unchanged)

Current `config/live_rule.json` → `expectation`:
- `metric`: `"active_univ_gross"` (evaluated by `scripts/forward_record_report.py::expectation_check` on `p["active_gross"]`)
- `ann_pct`: **9.36**, `nw_t`: **2.74**, `months`: **68**, `band_z`: **2.0**

Comparison with P1-2 (`research_total_return_benchmarks_2026-11-22.json`, holdout 2021-01..2026-08, 68m):

| Series | Annualised %/yr | NW t | Months | Monthly μ | σ_eff (%/mo / %/yr) | 12m alert (< −2σ) | 24m alert (< −2σ) | 36m alert (< −2σ) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **`config/live_rule.json` (`active_univ_gross`)** | **9.36** | **2.74** | **68** | 0.780% | 2.348% / 8.13% | −6.90% | −4.28% | −0.09% |
| P1-2 `B1_ew_universe_zero_cost` (`active_univ_gross`) | **9.36** | **2.74** | **68** | 0.780% | 2.348% / 8.13% | −6.90% | −4.28% | −0.09% |
| P1-2 `B2_ew_universe_costed` (`active_univ_net`) | **10.14** | **2.97** | **68** | 0.845% | 2.346% / 8.13% | −6.11% | −2.71% | +2.27% |

Findings:
1. **Exact numerical match on the configured metric:** `config/live_rule.json`'s `expectation` (`9.36%/yr`, `nw_t = 2.74`, `months = 68`) reproduces P1-2's `B1_ew_universe_zero_cost` (`active_univ_gross`) to the last decimal place. No update is needed for consistency with `active_univ_gross`.
2. **Gross vs. net benchmark note:** `scripts/forward_record_report.py` reports `EW net` (`active_univ_net`) as the primary summary benchmark, whereas `expectation_check` tests `active_gross` against `B1` (9.36%/yr, t 2.74). Because `B2` (`EW net`) has an annualised cost drag of 0.75%/yr and nearly identical effective monthly volatility (2.346% vs 2.348%/mo), switching the expectation metric to `active_univ_net` (10.14%/yr, t 2.97) would simply shift the expected sum and −2σ alert boundary up by ~0.78 pp/yr. Either way, comparing `active_gross` against `B1` is internally consistent (apples to apples).
3. **Calibration caveat (discovery & IAS 29 weakness):** Anchoring the band to the 2021–2026 holdout (+9.36%/yr) sets a relatively high bar compared to discovery (+4.37%/yr gross, t 1.67; +3.51% lag75 / +4.80% kapdates with delisted stocks) and the IAS 29 sub-window (+1.33%/yr gross, t 0.34). A live rule delivering the discovery-era edge (~4.4%/yr) would still stay inside the −2σ band for roughly 3 years, so the band is reasonably wide in the short run.
4. **Current forward-record state (2026-11-22):** `data/forward_record/decisions.jsonl` holds 1 decision (`2026-11-01`, rule `R0-2026-10-12`, 47 holdings, 233 universe names) and 0 completed calendar months; `expectation_check` stays `null` until the 2026-12 rebalance closes November.
5. **Action taken:** report only; `config/live_rule.json` was not modified.
