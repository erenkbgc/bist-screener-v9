# Learned factor weights: pre-registration

Written and committed on 2026-10-14, **before** any test below was run. The hypothesis, weight rule, factor set, metric and pass rule are fixed here and do not change after the results are seen.

## Question

Can a factor composite whose weights are learned month by month from **past data only** beat plain value_sn?

Phase 2 (`long_term_preregistration.md`) tested fixed 50/50 composites:
- H4a, value + GP/A: holdout −8.36%/yr (t −2.55);
- H5, value + SUE: discovery −4.49%/yr (t −1.23).

Both failed. A fixed 50/50 split may be a bad weight even if a factor carries information. This test lets the past decide the weights, so the weights themselves are out of sample.

## Prior exposure, stated honestly

- The full-sample factor ICs are known (`backtest_factor_model.py`):
  - value t 7.15;
  - low volatility t 7.25;
  - SUE t 5.63;
  - 12-1 momentum t 0.71.
- The Phase 2 composite results are known.
- The factor list below was chosen with this knowledge. The learned weights use only past months. The choice of which factors may enter does not use only past months, and this test cannot remove that bias.

## Data and universe

Identical to Phase 2, via `research_long_term.load()`:
- Panel: point-in-time `factors_monthly.parquet`, non-financial companies.
- Liquidity: each month, the least liquid 30% by 60-day median TL volume is dropped.
- Z-scores: 1/99 winsorized cross-sectional z-scores.
- Value: value_sn_z, the sector-neutral mean of E/P, B/M, S/P and EBIT/EV. It is identical to live `valuation_z` since PR #59.

## Candidate factors (fixed; nothing is added or removed after the run)

| Factor | Column | Sign |
|---|---|---|
| Value | `value_sn_z` | + |
| Gross profitability | `gpa_z` | + |
| Earnings surprise | `sue_z` | + |
| Momentum 12-1 | `mom_12_1_z` | + |
| Low volatility | `vol60_z` | − (already flipped in `prepare`) |

## Weight rule (H-LW, confirmatory)

For each month t:

1. **Monthly ICs.** For every earlier month m < t, compute the Spearman rank IC between each factor and the 1-month forward return. Use the month's universe and require ≥ 30 names. The forward return of month m is known at m+1 ≤ t, so no future data enters.
2. **Window.** Expanding window. At least 36 IC months are required. Months before that have no composite and are not compared.
3. **Weights.** For each factor k, ĝ_k = mean IC over the window. Set w_k = max(ĝ_k, 0) / Σ_j max(ĝ_j, 0). Negative-IC factors get weight 0, so the composite never bets against a factor. If every ĝ_k ≤ 0, use value only (w_value = 1).
4. **Composite.** composite_t = Σ_k w_k · z_k. A missing z counts as 0, as in `add_composites` and H4a/H5.

There are no other parameters, no shrinkage and no tuning.

## Exploratory composites (reported, cannot pass)

These were asked for, but they repeat or extend tests whose result is already known:
- **E1:** value_sn_z + mom_12_1_z, 50/50.
- **E2:** value_sn_z + gpa_z + mom_12_1_z, 1/3 each.

The value + GP/A 50/50 composite is not rerun. It is Phase 2 H4a.

## Metric

Same as Phase 2 (`core/long_term_research.portfolio`):
- top quintile, monthly, equal weight;
- net active return = top − universe mean − 2 × turnover × 20 bps;
- D_t = active(H-LW) − active(value_sn) on the months where both exist;
- Newey-West t with 6 lags.

Periods:
- Discovery: before 2021-01. The learning window starts only once 36 IC months exist, so discovery is shorter than Phase 2.
- Holdout: 2021-01 onward.

Also reported:
- USD active return;
- turnover;
- value-trap rate;
- the weight path (the weights each December and their range over time).

## Pass rule (all must hold)

1. Discovery: D > 0 and t > 3.0 (Harvey-Liu-Zhu).
2. Holdout: D > 0 and t > 2.0.
3. Holdout: USD net active return of H-LW ≥ that of value_sn.

Fallback: D > 0 in both periods with t > 2 in each is labelled "supported, not confirmed". It does not change live scoring.

## What goes live

- **If H-LW passes:**
  - Live scoring computes the same expanding-window IC weights from the research panel each month.
  - The weekly optimizer is replaced by this monthly rule.
  - The live score becomes the composite.
  - A parity test against the panel is added, as for value_sn.
- **If it fails:**
  - The live score stays plain value_sn.
  - The weekly weight-optimization job (`weekly-optimize.yml`), whose output nothing reads, is disabled.
  - Its code stays in the repository.

## Known limits

- The same limits as Phase 2 apply:
  - survivorship: the universe is today's listing;
  - no financial companies;
  - nominal statements;
  - signal and trade at the same month-end close.
- With a 36-month burn-in, discovery has about 57 months, which gives the test less power.
- The prior exposure described above.

---

## Results (added 2026-10-14, after the run; the sections above are unchanged)

`python scripts/research_learned_weights.py`. The composite exists from 2016-04 (after 36 IC months) to 2026-09: 57 discovery months and 68 holdout months. value_sn over the same months is +12.81%/yr (t 2.24) in discovery and +6.96%/yr (t 2.60) in holdout.

Full-sample mean rank IC (descriptive): value 0.050, GP/A 0.020, SUE 0.040, momentum 0.007, low volatility 0.075.

Learned weight ranges over time:

| Factor | Weight range |
|---|---|
| Value | 0.15–0.27 |
| GP/A | 0.10–0.21 |
| SUE | 0.16–0.25 |
| Momentum | 0.00–0.10 |
| Low volatility | 0.31–0.40 |

| Test | Discovery D (t) | Holdout D (t) | Holdout active TL / USD | Holdout turnover | Result |
|---|---|---|---|---|---|
| H-LW learned IC weights | −20.08% (−2.43) | −0.71% (−0.27) | 6.25% / 5.92% | 30.5% | **FAIL** |
| E1 value + momentum 50/50 | −14.58% (−2.72) | −8.05% (−1.63) | −1.09% / −1.30% | 25.7% | exploratory |
| E2 value + GP/A + momentum 1/3 | −8.59% (−2.00) | −9.17% (−1.77) | −2.21% / −2.30% | 19.7% | exploratory |

**H-LW fails**, and in discovery it is significantly worse than plain value.

Reading:
- The IC rule gives low volatility the largest weight, because its rank IC is the highest. Phase 1, however, found a negative top-quintile active return for low volatility. A factor can rank the whole cross-section well and still not improve a concentrated top quintile. The IC weighting does not see this.
- Mixing in other factors also dilutes the value tilt. This is the same pattern as H4a.
- These readings are post-hoc explanations, not results.

As pre-registered:
- The live score stays plain value_sn.
- The weekly weight-optimization job no longer runs on a schedule. Its schedule is removed from `.github/workflows/weekly-optimize.yml`, and manual dispatch stays available.
