# Agent Report — Plan P4-1 (Free-Float Filter) & P4-2 (Discovery Weakness Note)

- **Date:** 2026-11-22
- **Branch / Worktree:** `agent/freefloat` (`/home/eren/bist_wt/freefloat`)
- **Base commit:** `5617fbc` (`origin/master`)
- **Live rule / scoring:** untouched (`config/live_rule.json` remains `R0-2026-10-12`, zero changes in `config/` or `core/`)

---

## 1. What Was Done

1. **Pre-registered P4-1 before writing or running any backtest code** (commit `4a1a67d`):
   - Created `docs/research/free_float_preregistration.md` with one confirmatory rule (`FF1`: exclude stocks whose positive observed point-in-time free-float market value `ff_mcap` / İş Yatırım `HAO_PD` is below the 10th percentile of the monthly liquid universe; missing `ff_mcap` is never excluded), evaluated on the point-in-time baseline `data/research/fp/factors_monthly.parquet` with next-close fills and liquidity-dependent transaction costs at 1M TL (base costs).
   - Locked the decision rule identical to **D3** in `docs/research/portfolio_backtest_preregistration.md` (`d3_verdict`): `PASS` iff paired `D = net active(FF1) − net active(P0) > −1.0%/yr` and `NW t(D) > −2.0` in both discovery (2013–2020) and holdout (2021+), and holdout USD max drawdown of `FF1` is within 2.0 pp of `P0`.
   - Updated `data/research/trial_ledger.json`: added `free_float_preregistration` (+1 stock-selection trial), bringing `N_sel` from **86 → 87** (107 total trials across 33 studies).
2. **Implemented, tested, and ran the P4-1 study** (commit `3008b7d`):
   - Built `scripts/research_free_float.py` reusing `core/portfolio_backtest.py` and `scripts/research_portfolio_backtest.py` (`d3_verdict`, `attach_benchmarks`, `stats`, `diff`).
   - Added unit tests in `tests/test_free_float_filter.py` (4 tests covering bottom-decile exclusion, missing/non-positive preservation, per-month re-ranking, and D3 decision boundaries).
   - Ran `.venv/bin/python scripts/research_free_float.py` → `data/reports/research_free_float_2026-11-22.json`.
   - Appended the full results strictly below `## Results` in `docs/research/free_float_preregistration.md` (pre-registered sections unchanged).
   - Verified full test suite: `.venv/bin/pytest tests/ -q` → **521 passed** (0 failed, 0 skipped).
3. **Documented P4-1 and P4-2 in `README.md`** (commit `3008b7d`):
   - Added the `free_float_preregistration.md` (`FF1` `FAIL`, `N_sel = 87`) row to the Pre-registered Research scorecard.
   - Added the **P4-2** discovery-weakness note in both the top Status callout and the "Two layers of evidence" section: on the corrected `data/research/fp/` baseline, 2013–2020 costed discovery edge is **+4.37%/yr (t 1.67)** (+2.40%/yr, t 0.93 at 2× costs); `R0` is intentionally **not** re-tuned on this weakness, and it is recorded as the primary reason the live forward record (`data/forward_record/decisions.jsonl`) is the decisive out-of-sample test.

---

## 2. Key Numbers

### Baseline Regression Check (`P0`, `data/research/fp/factors_monthly.parquet`, 1M TL, base costs)

Exact match to `docs/research/first_published_panel.md`:
- **Discovery (2013-04 → 2020-12, 93 mo):** active vs EW universe **+4.37%/yr (t 1.67)**, USD CAGR **12.26%**, USD max DD **−56.6%**, cost **1.92%/yr**.
- **Holdout (2021-01 → 2026-08, 68 mo):** active vs EW universe **+9.36%/yr (t 2.74)**, USD CAGR **7.02%**, USD max DD **−35.4%**, cost **1.42%/yr**.

### Primary Result (`FF1` vs `P0`, 1M TL, base costs, next-close fills)

| Window | P0 active %/yr (t) | FF1 active %/yr (t) | Paired D %/yr (t) | USD paired D %/yr (t) | USD CAGR P0 / FF1 | USD max DD P0 / FF1 | Cost %/yr P0 / FF1 | Avg names P0 / FF1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Discovery (93 mo) | +4.37 (1.67) | +4.87 (1.75) | **+0.50 (0.69)** | +0.52 (0.73) | 12.26% / 12.88% | −56.6% / −56.4% | 1.92% / 1.73% | 42.7 / 38.8 |
| Holdout (68 mo) | +9.36 (2.74) | +8.07 (2.20) | **−1.29 (−1.73)** | −1.31 (−1.85) | 7.02% / 5.68% | −35.4% / −35.2% | 1.42% / 1.34% | 59.2 / 53.4 |

Against costed EW universe (`B2`): `P0` +5.14% (t 1.97) / +10.14% (t 2.97); `FF1` +5.64% (t 2.03) / +8.84% (t 2.41).

### Pre-registered Verdict: **`FAIL`**

| D3 Criterion | Bound | Observed | Result |
|---|---|---:|---|
| Discovery paired `D` | > −1.00%/yr | +0.50%/yr | PASS |
| Discovery NW `t(D)` | > −2.00 | +0.69 | PASS |
| Holdout paired `D` | > −1.00%/yr | **−1.29%/yr** | **FAIL** (−0.29 pp below bound) |
| Holdout NW `t(D)` | > −2.00 | −1.73 | PASS |
| Holdout USD max DD vs P0 | ≥ −37.4% | −35.2% (+0.2 pp) | PASS |

### Descriptive Diagnostics & Sensitivities

- **Coverage & overlap:** `ff_mcap` known for **93.1%** of liquid stock-months (89.2% discovery, 97.0% holdout; 40,693 rows). `FF1` excludes **9.5%** of the liquid universe and **7.3%** of `P0`'s top-20% holdings (monthly overlap `|P0 ∩ FF1| / |P0|` = **89.9%**, Jaccard **89.3%**).
- **Standalone Spearman rank IC vs `fwd_ret_1m` (NW 6 lags):**
  - `log(ff_mcap)`: discovery −0.0077 (t −0.38), holdout +0.0481 (t +2.53).
  - Free-float ratio (`ff_mcap / mcap`): discovery −0.0099 (t −1.21), holdout −0.0344 (t −2.28).
- **Capital / cost / fill sensitivities (all `FAIL` on lag-75/100 panel):**
  - 100k base: disc D +0.45% (0.63), hold D −1.30% (−1.74).
  - 1M stress 2×: disc D +0.70% (0.96), hold D −1.20% (−1.60).
  - 1M stress 3×: disc D +0.90% (1.23), hold D −1.10% (−1.47).
  - 1M next-open: disc D +0.55% (0.71), hold D −1.44% (−1.74).
  - 10M base: disc D +0.64% (0.88), hold D −1.27% (−1.70).
  - 100M base: disc D +1.09% (1.45), hold D −1.20% (−1.61); discovery >10%-ADV fills drop 16.0% → 14.0%.
  - 100M stress 2×: disc D +1.87% (2.36), hold D −1.00% (−1.34).
- **Actual KAP publication dates sensitivity (`data/research/fp/factors_monthly_kapdates.parquet`, 1M TL base):**
  - `P0` discovery +6.47% (t 2.37), holdout +7.61% (t 2.53).
  - `FF1` discovery +6.72% (t 2.46), holdout +8.30% (t 2.34).
  - Paired `D`: discovery **+0.25%/yr (t 0.37)**, holdout **+0.70%/yr (t 0.77)**, holdout USD max DD −35.5% → −33.6% (+1.9 pp). Would pass D3 on KAP dates, but does **not** override the pre-registered lag-75/100 primary verdict.

---

## 3. Commits on `agent/freefloat`

1. `4a1a67d` — `research: pre-register free-float market value filter FF1 (P4-1; N_sel 86->87)`
   - `docs/research/free_float_preregistration.md`, `data/research/trial_ledger.json`
2. `3008b7d` — `research: run free-float filter FF1 on fp baseline (FAIL) and add P4-2 note`
   - `scripts/research_free_float.py`, `tests/test_free_float_filter.py`, `data/reports/research_free_float_2026-11-22.json`, `docs/research/free_float_preregistration.md`, `README.md`
3. *(final commit)* — `docs: add AGENT_REPORT.md for P4-1 and P4-2`
   - `AGENT_REPORT.md`

No `git push`, no PRs, `master` untouched, `config/live_rule.json` and live scoring untouched.

---

## 4. Open Problems & Notes

1. **Publication-date sensitivity of `FF1`:** The sign flip in holdout `D` between lag-75/100 (−1.29%/yr, `FAIL`) and KAP publication dates (+0.70%/yr, would `PASS`) shows that the bottom-decile free-float filter sits right on the knife-edge of the −1.00%/yr D3 bound. Unlike `F1` (−8.83%/yr) and `F2` (−3.75%/yr), `FF1` is nearly return-neutral across specifications, but the evidence is too noisy to justify changing `R0-2026-10-12`.
2. **Missing `HAO_PD` history (6.9% of liquid stock-months):** 2,797 rows across 51 tickers (mostly renamed symbols like `TRALT`, `TRENJ`, `TRMET`, `OYAKC`, and the 9 stocks missing from HisseTekil tracked under P2-2) have `NaN` for `ff_mcap` (10.8% in discovery, 3.0% in holdout). They were kept rather than excluded per project rules; resolving P2-2 and ticker-rename history would close that gap.
3. **Minor labeling discrepancy discovered in `docs/research/first_published_panel.md`:** Line 79 of `first_published_panel.md` labels the last column `3× costs vs EW` with values `+2.40 (0.93)` (discovery) and `+7.88 (2.30)` (holdout). Our exact reproduction shows those values are **2× costs** (`mult=2.0`, `1M_stress2x`); true **3× costs** (`mult=3.0`, `1M_stress3x`) are `+0.42% (t 0.16)` discovery and `+6.39% (t 1.86)` holdout. We kept `first_published_panel.md` untouched (out of scope for this branch) and used the accurate `2× costs` label in our P4-2 `README.md` note.
4. **Delisted stocks & unpriced manipulation risk:** `data/research/fp/` does not yet include the 39 delisted stocks (tracked under P1-2), and the ADV-based square-root impact model cannot price real-world stock manipulation or cornering risk in ultra-thin floats. Free-float market value should remain visible as an information field for manual review.
5. **Merge coordination note:** `data/research/trial_ledger.json` was updated from `N_sel = 86` to `87` (`as_of: 2026-11-22`). If another parallel worktree also adds a trial to `trial_ledger.json`, keep both rows on merge (just as PR #98/#99 did).
