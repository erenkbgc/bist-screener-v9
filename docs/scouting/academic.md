# Academic Scouting Report: Emerging-Market Value, IAS 29 & Backtest Inference (2023–2026)

**Date:** 2026-11-22 · **Scope:** Primary sources (2023–2026) ranked by expected value for the live BIST `value_sn` rule (`R0-2026-10-12`, `docs/plan_2026-10-26.md`, trial ledger `N_sel = 86–87`).  
**Prioritization principle:** Zero-trial statistical/benchmarking infrastructure that directly fixes known weaknesses in `P1–P3` and the live forward record (`data/forward_record/decisions.jsonl`) ranks ahead of `+1 N_sel` signal hypotheses, given `DSR = 0.10–0.12` at current `N_sel`.

---

## Summary Table (Ranked by Expected Value)

| Rank | Finding | Date | Type | Effort | Target Plan / File |
|---:|---|---|---|---|---|
| 1 | López de Prado, Lipton & Zoonekynd — *How to Use the Sharpe Ratio* | 2026-03-25 | Infrastructure (0 `N_sel`) | S | `P1-2`, `P1-3` · `core/research_stats.py` |
| 2 | López de Prado & Porcu — *The Deflated Sharpe Ratio: Unified Framework* | 2026-08-30 | Infrastructure (0 `N_sel`) | S | `P1-2` · `core/research_stats.py` |
| 3 | Benhamou et al. — *Anytime-Valid Promotion Tests (`Promote`)* | 2026-11-02 | Infrastructure (0 `N_sel`) | M | `P0-3`, `P1-3`, `P4-2` · `scripts/forward_record_report.py` |
| 4 | Uzunlar, Atıcı & Çevik — *BIST Investor Reactions to IAS 29 NMPGL* | 2025-06-16 | New testable idea (+1 `N_sel`) | M | Post-`P1` · `core/pit_panel.py`, `scripts/build_pit_panel.py` |
| 5 | Gençay — *In-Loop Deflation & Variance-Dilution Exploits* | 2026-10-14 | Infrastructure (0 `N_sel`) | S | `P1-2`, `P4` · `core/research_stats.py`, `trial_ledger.json` |
| 6 | Dursun — *Multi-Factor Investing in Borsa Istanbul* | 2026-10-23 | Infrastructure (0 `N_sel`) | S | `P1-2`, `P4-2` · `scripts/research_total_return_benchmarks.py` |
| 7 | Harvey, Sancetta & Zhao — *Thresholds for Tests of Factor Models* | 2026-02-01 | Infrastructure (0 `N_sel`) | S | `P1-2`, `P4` · `core/research_stats.py` |
| 8 | Binz, Graham & Kubic — *Does Inflation Affect Earnings Relevance?* | 2024-04-18 | Infrastructure / Diagnostic (0 `N_sel`) | S | `P1-2` · `scripts/research_value_ablation.py` |
| 9 | Arian, Norouzi Mobarekeh & Seco — *CPCV vs. CSCV Backtest Overfitting* | 2024-12-03 | Infrastructure (0 `N_sel`) | S | `P1-2` · `core/research_stats.py::pbo_cscv` |
| 10 | Guimaraes & Kimura — *The Factor Zoo Revisited in Emerging Markets* | 2026-04-24 | Infrastructure (0 `N_sel`) | M | `P1-2`, `P2-5` · `scripts/research_quant_review.py` |
| 11 | Jensen, Kelly & Pedersen — *Is There a Replication Crisis in Finance?* | 2023-05-26 | Infrastructure (0 `N_sel`) | M | `P1-1`, `P1-3` · `config/live_rule.json`, `data/research/fp/` |
| 12 | Zuluaga-Rendón & Agudelo — *Nonparametric LatAm Cross-Section (`CFO/P`)* | 2025-02-02 | New testable idea (+1 `N_sel`) | M | Post-`P1` · `core/pit_panel.py`, `scripts/build_pit_panel.py` |
| 13 | FACPCE / IFRS EEG — *Hyperinflation in Argentina (IAS 29 Review)* | 2023-10 | Infrastructure / Governance (0 `N_sel`) | S | `P2-1`, `P2-3`, `P4-2` · `ias29_regime_preregistration.md` |
| 14 | Vincenz — *Intangible Value: An International Perspective* | 2024-04 | New testable idea (+1 `N_sel`) | L | Post-`P2` · `core/pit_panel.py::value_ratios` |

---

## Ranked Findings

### 1. How to Use the Sharpe Ratio
- **Link:** [SSRN 5520741](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5520741) · Official replication code: [github.com/zoonek/2025-sharpe-ratio](https://github.com/zoonek/2025-sharpe-ratio)
- **Date:** 2025-09-23 (last revised 2026-03-25)
- **Summary:** López de Prado, Lipton & Zoonekynd derive a closed-form sampling distribution for the Sharpe ratio under jointly non-Normal and serially correlated returns, paired with effective independent trial count ($N_{\text{eff}}$ via correlation clustering / ONC), Minimum Track Record Length (MinTRL), and observed False Discovery Rate (oFDR). Monte Carlo tests show this framework corrects severe over-penalization from raw correlated trial counts and false confidence from IID Normal assumptions.
- **Concrete use for THIS project:** Upgrade `core/research_stats.py::deflated_sharpe` before running **P1-2** (`scripts/research_quant_review.py` on `data/research/fp/`): add AR(1) serial-correlation correction to Sharpe variance, estimate $N_{\text{eff}}$ on the `B3` 48-variant return matrix alongside raw `N_sel = 86`, and compute MinTRL to set a realistic horizon for `config/live_rule.json` (**P1-3**).
- **Type:** Infrastructure (0 `N_sel`; reporting upgrade, no live rule change)
- **Effort:** S
- **README failed-idea check:** Clear. Not a trading rule; directly strengthens the already-adopted `B2` DSR diagnostic in `docs/research/quant_review_followups_preregistration.md`.

### 2. The Deflated Sharpe Ratio: A Unified Framework for Search-Adjusted Performance Inference
- **Link:** [SSRN 7198158](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7198158)
- **Date:** 2026-07-31 (last revised 2026-08-30)
- **Summary:** López de Prado & Porcu unify location-only DSR (`DSR-L`), location-and-scale DSR (`DSR-LS`, incorporating dispersion of the selected maximum), and exact order-statistic DSR (`DSR-EO`). They prove that non-Gaussian fat tails (Student-$t$ vs. Gaussian) shift both the magnitude and sign of calibration error, making `DSR-LS` with matched GEV shape necessary for calibrated p-values and power.
- **Concrete use for THIS project:** `core/research_stats.py::deflated_sharpe` currently implements only `DSR-L`, while BIST monthly active returns are fat-tailed (kurtosis 4.20 in `quant_review_followups_preregistration.md`). Add `DSR-LS` next to `DSR-L` in `core/research_stats.py` and report both in **P1-2** (`scripts/research_quant_review.py`).
- **Type:** Infrastructure (0 `N_sel`)
- **Effort:** S
- **README failed-idea check:** Clear. Refines the existing `B2` DSR formula rather than testing any rejected factor or overlay.

### 3. Can We Stop the Backtest Yet? Anytime-Valid Promotion Tests for Adaptive Financial Research Agents
- **Link:** [arXiv:2611.03384](https://arxiv.org/abs/2611.03384) (accepted ICAIF 2026)
- **Date:** 2026-11-02
- **Summary:** Benhamou et al. introduce *Promote*, an e-process / Ville-inequality protocol that allocates predictable testing wealth across dependent strategies and updates only on subsequent net-of-cost returns. Unlike fixed-sample tests—which suffered 94.5% false family crossings under repeated monitoring—*Promote* yields 0.0% null crossings while remaining valid under indefinite monthly peeking and adaptive candidate additions.
- **Concrete use for THIS project:** Implement a parallel cost-aware e-process tracker in `scripts/forward_record_report.py` (**P0-3**, **P1-3**, **P4-2**) to evaluate `data/forward_record/decisions.jsonl` (R0) and shadow composites (`V1` no-S/P, `P2` financials sleeve) month by month without optional-stopping bias that invalidates fixed-horizon Newey-West $t$-tests.
- **Type:** Infrastructure (0 `N_sel`)
- **Effort:** M
- **README failed-idea check:** Clear. Addresses sequential forward-record evaluation, which is not yet built in `scripts/forward_record_report.py`.

### 4. Reactions of Borsa Istanbul Investors to Inflation Accounting Practices
- **Link:** [TISEJ Vol. 60, Art. 1518](https://tisej.com/index.php/pub/en/article/view/1518) (DOI: `10.63556/tisej.2025.1518`)
- **Date:** 2025-06-16
- **Summary:** Uzunlar, Atıcı & Çevik analyze BIST-100 firms under Turkey's mandatory TMS 29 / IAS 29 inflation accounting and show that the Net Monetary Position Gain/Loss (NMPGL) line significantly drives announcement cumulative abnormal returns (positive-NMPGL firms outperform negative-NMPGL firms). Because NMPGL reflects balance-sheet monetary liability structure rather than recurring operating cash flow, unadjusted headline net income conflates debt inflation gains with core earnings power.
- **Concrete use for THIS project:** First run a zero-trial data audit in `scripts/build_pit_panel.py` / `data/research/fp/` to verify whether İş Yatırım and KAP first-published filings expose `Net Parasal Pozisyon Kazançları (Kayıpları)` cleanly from 2023Q4+; if coverage is high, pre-register **one** post-**P1** test comparing `ep` stripped of NMPGL (`ep_ex_nmpgl`) inside `core/pit_panel.py::value_ratios` against `V0` during the IAS 29 regime.
- **Type:** New testable idea (+1 `N_sel`; requires pre-registration after data audit)
- **Effort:** M
- **README failed-idea check:** Clear. `ias29_regime_preregistration.md` and `ias29_constant_unit_ttm_preregistration.md` tested regime consistency and constant-unit YTD alignment only; stripping NMPGL from `ep` is explicitly flagged as an **untested** open item in `docs/research/sector_specific_notes.md` §3 and `README.md` Known Limitations.

### 5. Can a Search Hold Its Own Bar? In-Loop Deflation and Its Exploits in Autonomous Strategy Discovery
- **Link:** [arXiv:2611.14539](https://arxiv.org/abs/2611.14539)
- **Date:** 2026-10-14
- **Summary:** Gençay proves that indexing a DSR acceptance bar to the running trial count and cross-sectional Sharpe variance `V[SR]` suffers a *variance-dilution exploit*: adding mediocre or near-duplicate candidates shrinks `√V` faster than the trial-count multiplier grows, lowering the bar `SR₀`. He shows 100 nominal trials typically collapse to 6–8 independent streams and recommends a pre-registered variance floor `V_min` plus a monotone high-water-mark `SR₀`.
- **Concrete use for THIS project:** Add a frozen variance floor `V_min` and monotone `SR₀` guard to `core/research_stats.py::deflated_sharpe` and `data/research/trial_ledger.json` before running **P1-2** and any **P4** trials (`P4-1` free float, `P4-3` minority interest), ensuring failed future trials cannot inadvertently dilute `V[SR]` and weaken the DSR gate.
- **Type:** Infrastructure (0 `N_sel`)
- **Effort:** S
- **README failed-idea check:** Clear. Hardens the existing `data/research/trial_ledger.json` and `B2` DSR mechanism from `quant_review_followups_preregistration.md`.

### 6. Multi-Factor Investing in Borsa Istanbul
- **Link:** [SSRN 7662821](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7662821)
- **Date:** 2026-10-23
- **Summary:** Using 17 years of hand-collected point-in-time BIST financials, Dursun tests a walk-forward multi-factor portfolio (low vol, value, 52-week high, reversal, quality + trend gate) and finds +4.4%/yr CAPM alpha vs. XU100 (t 2.08) that completely vanishes against a volatility-matched equal-weighted eligible universe (−0.4%/yr, 95% CI [−6.3%, +5.5%]; 25.1% TL CAGR = 2.6% USD). Characteristics deliver drawdown containment (−22% vs. −34%) rather than excess return over EW, and reporting confidence-interval upper bounds is more informative than binary null tests.
- **Concrete use for THIS project:** Independent external validation of our own BIST findings (`long_term_preregistration.md`, `trend_timing_preregistration.md`, **P4-2**). In **P1-2** (`scripts/research_total_return_benchmarks.py` and `scripts/research_quant_review.py`), add volatility-matched EW-universe benchmarking and explicit 95% CI upper-bound alpha reporting alongside point $t$-stats, reinforcing why we should not spend `N_sel` on complex multi-factor/timing overlays.
- **Type:** Infrastructure / Benchmarking (0 `N_sel`)
- **Effort:** S
- **README failed-idea check:** Clear. Does not propose adopting its 5-factor or trend-gate rules (which already failed in README); adopts only its volatility-matched EW benchmark and upper-bound reporting protocol.

### 7. What Threshold Should be Applied to Tests of Factor Models?
- **Link:** [NBER Working Paper w34898](https://doi.org/10.3386/w34898)
- **Date:** 2026-02-01
- **Summary:** Harvey, Sancetta & Zhao revisit the Harvey-Liu-Zhu $t > 3$ rule, deriving a dependence-robust lower bound on valid significance cutoffs without assuming the unobserved total number of tests ($t \ge 3.0$ minimum; $3.7$–$5.0$ for purely data-mined accounting ratios). They advocate reporting the **local False Discovery Rate (lFDR)**—the posterior probability the null is true given observed $t$—instead of relying solely on conventional p-values.
- **Concrete use for THIS project:** Add `local_fdr` computation to `core/research_stats.py` and print it in `scripts/research_quant_review.py` (**P1-2**) and future **P4** pre-registration scorecards (`P4-1`, `P4-3`), modernizing the legacy HLZ $t > 3$ gate documented in `README.md`.
- **Type:** Infrastructure (0 `N_sel`)
- **Effort:** S
- **README failed-idea check:** Clear. Updates the statistical pass-rule methodology already used across `docs/research/`.

### 8. Does Inflation Affect Earnings Relevance? A Century-Long Analysis
- **Link:** [NBER Working Paper w32364](https://www.nber.org/papers/w32364)
- **Date:** 2024-04-18
- **Summary:** Across nearly a century of financial statements, Binz, Graham & Kubic find a strong *positive* relationship between inflation and the market relevance of accounting earnings—dominating historical-cost distortion effects. Higher inflation raises nominal discount rates, shortening equity duration and shifting investor valuation weight toward near-term earnings/operating flows over distant balance-sheet assets or top-line sales.
- **Concrete use for THIS project:** Directly explains our empirical split in `ias29_regime_preregistration.md` and `value_ablation_preregistration.md` (where `ey` and `ep` remained strongly predictive in 2021–2026 while `bm` weakened and `sp` collapsed). Use this to frame the **P1-2** re-run of `scripts/research_value_ablation.py` on `data/research/fp/` and justify continued forward-record tracking of shadow composite `V1` (`bm+ep+ey`, no `sp`) without prematurely altering `R0`.
- **Type:** Infrastructure / Diagnostic Interpretation (0 `N_sel`)
- **Effort:** S
- **README failed-idea check:** Clear. Does not re-test `V1` as a new trial (`V1` already recorded `KEEP_V0` in `value_ablation_preregistration.md`); provides macro-accounting grounding for `P1-2` reporting and forward shadow monitoring.

### 9. Backtest Overfitting in the Machine Learning Era: A Comparison of Out-of-Sample Testing Methods in a Synthetic Controlled Environment
- **Link:** [Knowledge-Based Systems, Vol. 305 (112477)](https://dl.acm.org/doi/10.1016/j.knosys.2024.112477)
- **Date:** 2024-12-03
- **Summary:** Arian, Norouzi Mobarekeh & Seco benchmark walk-forward, K-fold, CSCV, and Combinatorial Purged Cross-Validation (CPCV) under autocorrelation, non-stationarity, and regime shifts. CPCV materially outperforms unpurged CSCV and single walk-forward splits by preventing boundary leakage across adjacent blocks, yielding lower false-discovery rates and more stable PBO/DSR estimates.
- **Concrete use for THIS project:** `core/research_stats.py::pbo_cscv` (`B3`) currently splits 128 months into 16 contiguous blocks with zero purge/embargo between adjacent train and test blocks. Add an optional `embargo_months=1` purge at train/test boundaries in `core/research_stats.py::pbo_cscv` and report purged PBO alongside unpurged PBO in **P1-2** (`scripts/research_quant_review.py`).
- **Type:** Infrastructure (0 `N_sel`)
- **Effort:** S
- **README failed-idea check:** Clear. Fixes a boundary-leakage limitation in the existing `B3` CSCV implementation.

### 10. The Factor Zoo Revisited: Multiple Testing, Hierarchical Modeling, and Out-of-Sample Evidence from Emerging Markets
- **Link:** [SSRN 6628840](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6628840)
- **Date:** 2025-12-15 (posted 2026-04-24)
- **Summary:** Guimaraes & Kimura (Universidade de Brasília) test frequentist FWER/FDR vs. Bayesian hierarchical partial-pooling models on a broad emerging-market equity panel in expanding-window walk-forward backtests. Only a small core of economic themes survives disciplined inference, and while overly strict no-pooling FWER (e.g., Bonferroni) degrades OOS portfolio efficiency, hierarchical theme-level partial pooling and FDR deliver superior risk-adjusted OOS robustness.
- **Concrete use for THIS project:** Inform **P1-2** (`scripts/research_quant_review.py`) and **P2-5** (rebuilding `financials_factors_monthly.parquet` with HisseTekil `PD`): apply hierarchical Bayesian shrinkage across related valuation sleeves (`V0`, `V1`, `F1_bm_roe_sn`) when reporting expected out-of-sample alpha in small-sample EM subsets (e.g., 12–49 financial stocks where unpooled $t$-tests lack power).
- **Type:** Infrastructure (0 `N_sel`)
- **Effort:** M
- **README failed-idea check:** Clear. Distinct from `learned_weights_preregistration.md` (which failed on dynamic month-by-month IC weighting); hierarchical pooling is an inference/shrinkage diagnostic, not a live weight optimizer.

### 11. Is There a Replication Crisis in Finance?
- **Link:** [The Journal of Finance, 78(5)](https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.13249) · Open data & code: [jkpfactors.com](https://jkpfactors.com/), [github.com/bkelly-lab/ReplicationCrisis](https://github.com/bkelly-lab/ReplicationCrisis)
- **Date:** 2023-05-26
- **Summary:** Jensen, Kelly & Pedersen evaluate 153 factors across 93 countries (including Turkey, Brazil, and Argentina) using a hierarchical Bayesian model, finding an 82.4% global replication rate grouped into 13 economic themes. Importantly, post-publication / out-of-sample factor alphas shrink toward theme-level priors rather than zero, and single-country factor estimates benefit heavily from cross-country shrinkage.
- **Concrete use for THIS project:** Cross-validate our newly promoted `data/research/fp/` baseline (**P1-1**) against JKP's open-source Turkey & EM `value` theme monthly returns (`jkpfactors.com`) to spot residual corporate-action or restatement discrepancies, and calibrate a realistic shrunk OOS alpha band for `config/live_rule.json` (**P1-3**) rather than extrapolating raw holdout `+9.36%/yr`.
- **Type:** Infrastructure (0 `N_sel`)
- **Effort:** M
- **README failed-idea check:** Clear. External data-audit and Bayesian OOS expectation benchmark; introduces no new trading factor.

### 12. Nonparametric Identification of Factors for the Cross-Section of Latin American Stock Returns
- **Link:** [Global Finance Journal, Vol. 68 (RePEc)](https://ideas.repec.org/a/eee/glofin/v68y2025ics1044028325000997.html)
- **Date:** 2025-02-02
- **Summary:** Zuluaga-Rendón & Agudelo apply Group Adaptive Elastic Net to 34 classic factors across Latin American equities (including high-inflation Brazil and Argentina) and find that only six signals drive most cross-sectional return variance—prominently **Cash Flow to Price (`CFO/P`)**, `E/P`, and `Assets/Market`. Out-of-sample factor portfolios built on this sparse set outperform regional benchmarks cleanly.
- **Concrete use for THIS project:** Our `value_sn` uses `bm`, `ep`, `sp`, `ey` and has **never** tested operating cash-flow yield (`CFO/P` or `CFO/EV`), which is immune to non-cash IAS 29 NMPGL and depreciation revaluations. After **P1** completes, extract PIT operating cash flow (`İşletme Faaliyetlerinden Nakit Akışları`) in `scripts/build_pit_panel.py` / `core/pit_panel.py` and pre-register **one** trial (`+1 N_sel`) testing `cfo_p` replacing `sp` (or as a 5th leg) in `value_sn`.
- **Type:** New testable idea (+1 `N_sel`; requires pre-registration)
- **Effort:** M
- **README failed-idea check:** Clear. README tested `bm`, `ep`, `sp`, `ey`, `gpa`, `roe`, `roa`, `opa`, `sue`, `dividend_yield`, and `st_debt_coverage`; `CFO/P` was never tested in `long_term_preregistration.md` or `value_ablation_preregistration.md` (Sloan accrual in `core/sloan.py` is information-only and untested).

### 13. Hyperinflation in Argentina (IAS 29 Five-Year Post-Implementation Review)
- **Link:** [IFRS Emerging Economies Group / FACPCE Report](https://www.ifrs.org/content/dam/ifrs/meetings/2023/october/eeg/5-hyperinflation-in-argentina-facpce-october-2023-eeg.pdf)
- **Date:** 2023-10
- **Summary:** Reviewing five years of mandatory IAS 29 adoption in Argentina (since 2018), FACPCE documents to the IFRS Foundation that CPI-restated statements suffer persistent cross-standard mismatches (IFRIC 7, IAS 21, deferred taxes) and fail to improve KPI predictability. Investors routinely encounter counterintuitive accounting signals when the local currency stops functioning as a stable unit of account and rely heavily on cash-flow and constant-FX cross-checks.
- **Concrete use for THIS project:** Directly informs **P2-1** (resolving the 33 `unknown` re-expression companies), **P2-3** (per-item first-published validation hit rates in `scripts/build_first_published.py`), and **P4-2** / `ias29_regime_preregistration.md`: treat Turkey's noisy 28-month IAS 29 IC drop (+0.077 → +0.034) as an expected structural property of hyperinflationary restatement rather than a trigger to re-tune `R0` on short IAS 29 history.
- **Type:** Infrastructure / Governance (0 `N_sel`)
- **Effort:** S
- **README failed-idea check:** Clear. Primary standard-setter evidence reinforcing our existing `CONSISTENT` / do-not-retune decision in `docs/research/ias29_regime_preregistration.md`.

### 14. Intangible Value: An International Perspective
- **Link:** [Lancaster University / FoFI 2024 Working Paper 002](http://wp.lancs.ac.uk/fofi2024/files/2024/04/FoFI-2024-002-Stefan-Vincenz.pdf)
- **Date:** 2023-09-15 (FoFI release 2024-04)
- **Summary:** Vincenz extends Eisfeldt, Kim & Papanikolaou's perpetual-inventory SG&A capitalization (`INT_t = (1 − δ)INT_{t−1} + SG&A_t`) to international equity markets and finds that intangible-adjusted book-to-market (`iB/M`) consistently outperforms standard `B/M`, with the gap widening in recent decades. The improvement reflects reduced book-equity mismeasurement across asset-light vs. tangible-asset-heavy firms.
- **Concrete use for THIS project:** Lower priority on BIST than in US tech-heavy markets—hence ranked #14—because BIST is industrial/asset-heavy; however, IAS 29 restates tangible PP&E upward while leaving SG&A-built organizational capital uncapitalized, widening distortion in `bm`. After **P2** data completeness, audit PIT SG&A (`Genel Yönetim + Pazarlama Giderleri`) coverage in `core/pit_panel.py`; only if ≥80% clean 5-year history exists, consider one pre-registered trial (`+1 N_sel`) testing `iB/M` in place of `bm`.
- **Type:** New testable idea (+1 `N_sel`; requires pre-registration)
- **Effort:** L
- **README failed-idea check:** Clear. `financials_holdings_reits_preregistration.md` tested *subtracting* balance-sheet intangibles (`tangible_bm`) for financials only; capitalizing off-balance-sheet SG&A for non-financials has never been tested in README.

---

## Explicitly Reviewed & Excluded (Conflicts with README / Plan)
- **Factor value-spread / macro timing** (e.g., Zhang 2024, [SSRN 4588171](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4588171); FTSE Russell 2023 inflation-regime timing): excluded as actionable ideas because timing overlays are explicitly **Not planned** in `docs/plan_2026-10-26.md` (22 entry/exit/timing rules and all macro-timing tests failed).
- **Dropping sector neutrality in long-only value** (Ehsani, Harvey & Li 2023, *FAJ*, [DOI 10.1080/0015198X.2023.2196931](https://doi.org/10.1080/0015198X.2023.2196931)): excluded as a new trial because raw `value_z` was already evaluated against `value_sn_z` in `quant_review_followups_preregistration.md` (`B3` 48-variant CSCV menu, where `value_sn` ranked 1st) and Brinson attribution (`A3`) confirmed R0's holdout edge is within-sector selection (`+8.50%/yr`, $t = 2.91$).
- **Rights/bonus capital-increase short-term avoidance** (Aydınlı 2026, *JECF*, [Art. 10](https://cf.org.tr/journal/economic-change-future/article/10)): excluded because `nsi_rights_12m = 0` was already tested inside `docs/research/long_term_preregistration.md` and failed to improve `value_sn`.
