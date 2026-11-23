# Round 3 Audit Summary (`r3-skeptic` / Chief Risk & Skeptic)

- **Audit Date**: 2026-11-24
- **Scope**: All 6 Wave-1 candidates (`scholar_cbop`, `scholar_sue_usd`, `scholar_real_cbop_sue`, `miner_ocf_ev_real`, `miner_qgp_surp_real`, `miner_gp_qop_real`), `N_sel: 92 -> 98`.
- **Overall Audit Verdict**: **CLEAN EXECUTION, 0/6 PASS (ALL REJECTED)**. Pre-registration discipline, zero-lookahead PIT enforcement, and TL/dimensionless unit consistency all passed independent verification. Every Wave-1 tilt failed out-of-sample holdout (`2021+`) on the primary `lag75` panel, leaving `R0` (`value_sn`) undefeated at `N_sel = 98`.

---

## 1. Pre-Registration vs. Result Timestamp Audit

Because `/home/eren/bist_wt/r3-board/` is a shared board directory rather than a git repo, preregistration timestamps were cross-checked across **both** board filesystem mtimes (`r3-board/prereg/*.md` vs `r3-board/results/*.md`) **and** git commits on `agent/r3-backtest` (`data/research/trial_ledger.json` registration commits vs `data/reports/research_round3_*_2026-11-24.json` result commits).

| `N_sel` | Candidate | Feature Code Commit (`agent/r3-features`) | Board Prereg (`mtime`, +03) | Git Ledger Prereg Commit (`agent/r3-backtest`) | Board Result (`mtime`, +03) | Git Result Commit (`agent/r3-backtest`) | Order Valid? |
|---:|:---|:---|:---|:---|:---|:---|:---:|
| 93 | `scholar_cbop` | `cafd910` (00:43:25) | `00:46:30.83` | `8e356a8` (00:46:37) | `00:46:58.87` | `350ee61` (00:47:18) | **PASS** (+28s / +41s) |
| 94 | `scholar_sue_usd` | `cafd910` (00:43:25) | `00:47:18.83` | `fbc5a21` (00:47:18) | `00:47:40.45` | `eaa82d0` (00:47:57) | **PASS** (+22s / +39s) |
| 95 | `scholar_real_cbop_sue` | `cafd910` (00:43:25) | `00:47:58.26` | `e87c62f` (00:47:58) | `00:48:20.08` | `6f9a6a5` (00:48:32) | **PASS** (+22s / +34s) |
| 96 | `miner_ocf_ev_real` | `9d6b963` (00:50:01) | `00:51:17.51` | `5f142ad` (00:51:17) | `00:51:37.19` | `d082b0f` (00:51:57) | **PASS** (+20s / +40s) |
| 97 | `miner_qgp_surp_real` | `9d6b963` (00:50:01) | `00:51:57.96` | `3dc4aaa` (00:51:58) | `00:52:17.10` | `dd384cc` (00:52:31) | **PASS** (+19s / +33s) |
| 98 | `miner_gp_qop_real` | `9d6b963` (00:50:01) | `00:52:32.45` | `f86c305` (00:52:32) | `00:52:51.88` | `7fe95c2` (00:53:05) | **PASS** (+19s / +33s) |

- **Git hygiene / attribution**: Zero AI attribution tokens found across `b66c0e4..HEAD` on `r3-scholar`, `r3-miner`, `r3-features`, `r3-backtest`, and `r3-skeptic`. All 28 tests in `tests/test_round3.py` and `tests/test_round3_features.py` pass (`28 passed`).
- **Process note**: `scripts/research_round3.py` enforces `verify_prereg()` (checks file presence and pass-rule tokens) and `verify_ledger_registered()` before running any backtest, and `r3-features` enforced discovery-only (`2013-01-01 .. 2020-12-31`) coverage diagnostics prior to preregistration.

---

## 2. Lookahead & PIT Integrity Audit

Independent checks performed on `scripts/research_round3.py` and `scripts/research_round3_features.py`:

1. **Forward-target stripping**: `strip_forward_columns()` removes all `fwd_ret*` columns from both `raw_panel` and `prepared_df` before invoking any `CANDIDATE_BUILDERS[name]` function.
2. **Future-truncation invariance test** (`audit_kit.check_lookahead_truncation`): Re-ran all 6 candidate builders after truncating `raw_panel`, `prepared_df`, `quarterly` (`available_at <= cutoff`), `macro`, `fx`, and `eurobond` at both `2019-12-31` and `2020-12-31`:
   - `scholar_cbop`: `2019-12-31` `max_abs_diff = 0.0`, `nan_mismatch = 0`; `2020-12-31` `max_abs_diff = 0.0`, `nan_mismatch = 0` (**PASS**)
   - `scholar_sue_usd`: `2019-12-31` `0.0` / `0`; `2020-12-31` `0.0` / `0` (**PASS**)
   - `scholar_real_cbop_sue`: `2019-12-31` `0.0` / `0`; `2020-12-31` `0.0` / `0` (**PASS**)
   - `miner_ocf_ev_real`: `2019-12-31` `0.0` / `0`; `2020-12-31` `0.0` / `0` (**PASS**)
   - `miner_qgp_surp_real`: `2019-12-31` `0.0` / `0`; `2020-12-31` `0.0` / `0` (**PASS**)
   - `miner_gp_qop_real`: `2019-12-31` `0.0` / `0`; `2020-12-31` `0.0` / `0` (**PASS**)
3. **Causal lag & FX alignment**:
   - `_attach_yoy_lag` requires `350 <= (period_end - period_end_ya) <= 380` days AND `_available_at_ya <= available_at`.
   - `sue_usd_feature` deflates `q_ni` by `usdtry_month_end[month_end(period_end)]` (quarter-end precedes `available_at`) and computes trailing `std` strictly over causal rows (`available_at <= current available_at`).
   - `_attach_pit_quarterly_values` joins on `(ticker, stmt_period == period)` when `stmt_period` is present on the PIT panel (`lag75` or `kapdates`), preserving exact panel filing-lag semantics.
   - `cross_sectional_z` (`1%/99%` winsorize + `sector_neutralize(min_n=5)`) operates strictly within each monthly `date` slice.
   - Simulation (`core/portfolio_backtest.py::simulate`) uses `d0` ADV/sigma and executes at next-trading-day (`d0 + 1`) close.

---

## 3. Units & Scaling Audit (All 6 Wave-1 Candidates)

Direct inspection of `fp/quarterly.parquet` vs `fp/factors_monthly.parquet` (verified on `THYAO 2023Q4` and `EREGL 2023Q4`) confirms **all monetary statement items (`total_assets`, `cash`, `fin_debt`, `ttm_gross_profit`, `ttm_op_profit`, `q_*`) and `mcap` are in exact 1 TL units** (no 1,000x TL vs thousand-TL mismatch).

| Candidate | Underlying Feature(s) | Exact Formula Units | Verified Empirical Medians (Disc / Pre-IAS29 / IAS29) | Unit / Accounting Verdict |
|---|---|---|---|---|
| `scholar_cbop` | `cbop_nom` | `(TL - ΔTL) / TL` (dimensionless) | `-0.008` / `-0.070` / `-0.187` | **Dimensionless OK**; nominal `ΔNOA` drifts strongly negative under high inflation |
| `scholar_sue_usd` | `sue_ni_usd` | `(USD - USD) / std(USD)` (sigma) | `+0.019` / `+0.184` / `-0.028` | **Dimensionless OK**; clean quarter-end FX deflation |
| `scholar_real_cbop_sue` | `cbop_real` + `sue_ni_usd` | `TL/TL` (`k=CPI_p/CPI_{p-4q}`) + sigma | `cbop_real`: `+0.053` / `+0.083` / `-0.008` | **Dimensionless OK**; 1y CPI fixes pre-IAS29, breaks at IAS29 multi-year step-up |
| `miner_ocf_ev_real` | `ocf_ev_real` | `(TL - k*TL) / (mcap + fin_debt - cash)` (`TL/TL`, `EV>0`) | `+0.053` / `+0.046` / `-0.004` | **Dimensionless OK**; `mcap` and `net_debt` both in 1 TL |
| `miner_qgp_surp_real` | `qgp_surp_real_mcap` | `(q_gp_p - k*q_gp_{p-4q}) / mcap` (`TL/TL`) | `+0.002` / `+0.007` / `-0.003` | **Dimensionless OK**; `q_gross_profit` not bridged by `bridge_ttm` across 2023Q4–2024Q3 |
| `miner_gp_qop_real` | `gp_mcap` + `qop_surp_real` | `TL/TL` + `TL/TL` | `gp_mcap`: `+0.183` / `+0.127` / `+0.114`; `qop`: `+0.002` / `+0.005` / `-0.002` | **Dimensionless OK**; discrete `q_op_profit` unbridged across IAS29 seam |

**Reporting units check**:
- `D`, `vs_ew_net`, `Entrants - Dropouts`: annualized arithmetic means (`1200 * mean_monthly`, `%/yr`) with 6-lag Newey-West `t`.
- `MaxDD USD`, `Turnover` (one-way buy turnover), `Cov %`: `%`.
- `DSR`: monthly Sharpe ratio (`mean / std(ddof=1)`) evaluated against `expected_max_sharpe(N_sel, var_sr=0.02335)`.
- **Key caveat (accounting basis break, not a unit-scale error)**: All 5 YoY-difference tilts fail sharpest in the 28-month IAS 29 regime (`2024-05+`) because 1-year `CPI(p)/CPI(p-4q)` scaling does not bridge the multi-year historical-cost-to-IAS-29 balance-sheet revaluation cliff (`2023Q4+`) or unbridged `q_*` discrete flows.

---

## 4. Consolidated Wave-1 Results & Final Verdict (`N_sel = 98`)

Primary `lag75` panel (`93` discovery months `2013-04..2020-12`, `68` holdout months `2021-01..2026-08`; `R0` net vs EW = `+5.14%/yr (t=+1.97)` disc, `+10.14%/yr (t=+2.97)` holdout, `+2.19%/yr` IAS29, `+7.25%/yr (t=+3.38)` full, `DSR(N=98)=0.0872`):

| `N_sel` | Candidate | Disc `D` (`t`) | Hold Pre-IAS29 (40m) `D` (`t`) | Hold IAS29 (28m) `D` (`t`) | Hold All `D` (`t`) | Hold DD diff (pp) | `kapdates` Hold `D` (`t`) | DSR (`N_sel`) | Final Verdict |
|---:|:---|---:|---:|---:|---:|---:|---:|---:|:---|
| 93 | `scholar_cbop` | +2.71% (+2.67) | -1.31% (-0.65) | -3.69% (-3.03) | -2.29% (-1.67) | -0.80 | -1.41% (-1.00) | 0.1208 | **REJECT (FAIL)** |
| 94 | `scholar_sue_usd` | +1.43% (+1.32) | -1.93% (-0.85) | -0.87% (-0.61) | -1.49% (-1.02) | -1.40 | +2.55% (+1.46) | 0.1296 | **REJECT (FAIL)** |
| 95 | `scholar_real_cbop_sue` | +3.86% (+4.56) | -1.97% (-0.70) | -3.04% (-2.20) | -2.41% (-1.38) | -1.40 | +2.40% (+1.28) | 0.2273 | **REJECT (FAIL)** |
| 96 | `miner_ocf_ev_real` | +3.38% (+2.35) | -0.91% (-0.79) | -3.84% (-1.78) | -2.12% (-1.67) | -0.80 | -1.18% (-0.60) | 0.1607 | **REJECT (FAIL)** |
| 97 | `miner_qgp_surp_real` | +1.79% (+1.30) | -0.11% (-0.09) | -5.01% (-2.15) | -2.13% (-1.45) | +0.60 | -0.48% (-0.26) | 0.0925 | **REJECT (FAIL)** |
| 98 | `miner_gp_qop_real` | +2.31% (+1.46) | +0.55% (+0.25) | -6.16% (-3.95) | -2.21% (-1.23) | -0.50 | -0.94% (-0.76) | 0.1088 | **REJECT (FAIL)** |

**Conclusion**: Round 3 Wave 1 is closed (`0/6 PASS`). All 6 candidates pass every technical audit (timestamps, zero lookahead, unit consistency) and fail purely on out-of-sample economic merit. `R0` (`value_sn`) remains the undefeated baseline entering Round 4 at `N_sel = 98` (48-variant CSCV `PBO = 0.056`, `V[SR] = 0.02335`, `SR0(98) = 0.3856`).
