# Round 3 Pre-registration: `scholar_cbop`

- **Date**: 2026-11-24
- **Source branch**: `agent/r3-features`
- **Trial type**: Combination candidate (separate +1 N_sel trial)
- **Trial ledger `N_sel` after registration**: 93

## Motivation & Hypothesis

Ball, Gerakos, Linnainmaa & Nikolaev (2016, JFE) Cash-Based Operating Profitability (CbOP) strips balance-sheet operating accruals (Delta NOA) from operating profit to avoid accrual-inflated value traps. Zero return-fitted parameters (fixed 80/20 canonical tilt). Discovery (2013-2020) net D = +2.53%/yr (NW t = +2.44), coverage 98.4%.

## Formula

```text
NOA_{i,p} = (total_assets - cash) - (current_liab + noncurrent_liab - fin_debt)
cbop_{i,p} = (ttm_op_profit_{i,p} - (NOA_{i,p} - NOA_{i,p-4q})) / total_assets_{i,p}   (if total_assets > 0 else NaN)
Merge strictly PIT on (ticker, stmt_period == period) onto liquid panel (fb.prepare, liq_drop_pct=0.3, value_sn_z.notna()).
cbop_z_sn = fb.sector_neutralize(fb.winsorize_z(cbop, 0.01, 0.99), min_n=5)
score_{i,t} = 0.80 * value_sn_z_{i,t} + 0.20 * fillna(cbop_z_sn_{i,t}, 0.0)
Portfolio: monthly top-20% (rank(ascending=False, pct=True) <= 0.20).
```

## Frozen Parameters

```json
{
  "min_sector_n": 5,
  "w_cbop_sn": 0.2,
  "w_value_sn": 0.8,
  "winsor_hi": 0.99,
  "winsor_lo": 0.01
}
```

## Evaluation Panel & Execution

- Primary panel: `/home/eren/bist_project/data/research/fp/factors_monthly.parquet` (lag-75 PIT).
- Robustness panel: `/home/eren/bist_project/data/research/fp/factors_monthly_kapdates.parquet` (cannot flip FAIL to PASS).
- Holdout 2021+ has NOT been inspected prior to this pre-registration.

## FIXED PASS RULE (verbatim)

candidate monthly top-20% vs R0 value_sn top-20%, same universe, liquidity cut, 1M TL costs, next-close fills. D = net active(cand) - net active(R0). PASS iff D>0 discovery 2013-2020 NW t>=1.0 AND D>0 holdout 2021+ NW t>=2.0 AND holdout USD maxDD not worse than R0 by >2pp. Report DSR at updated N_sel. Every tested candidate +1 N_sel.
