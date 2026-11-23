# Round 3 Pre-registration: `miner_qgp_surp_real`

- **Date**: 2026-11-24
- **Source branch**: `agent/r3-features`
- **Trial type**: Combination candidate (separate +1 N_sel trial)
- **Trial ledger `N_sel` after registration**: 97

## Motivation & Hypothesis

Top-of-income-statement CPI-adjusted quarterly gross profit surprise scaled by market cap captures real demand and pricing-power acceleration above FX/interest/deferred-tax noise, with 98.5% coverage and near-zero correlation (+0.07) to value_sn_z. Zero return-fitted parameters (fixed 75/25 tilt). Discovery (2013-2020) net D = +2.08%/yr (NW t = +1.60), 8/8 years positive standalone IC.

## Formula

```text
cpi_idx = cumprod(1 + cpi_mom.fillna(0) / 100) indexed by Period('M')
qgp_surp_real_{i,p} = q_gross_profit_{i,p} - q_gross_profit_{i,p-4q} * (cpi_idx[period_end_p] / cpi_idx[period_end_{p-4q}])
Merge strictly PIT on (ticker, stmt_period == period) onto liquid panel (fb.prepare, liq_drop_pct=0.3, value_sn_z.notna()).
qgp_surp_real_mcap_{i,t} = qgp_surp_real_{i,p} / mcap_{i,t}   (if mcap > 0 else NaN)
qgp_surp_real_z_sn = fb.sector_neutralize(fb.winsorize_z(qgp_surp_real_mcap, 0.01, 0.99), min_n=5)
score_{i,t} = 0.75 * value_sn_z_{i,t} + 0.25 * fillna(qgp_surp_real_z_sn_{i,t}, 0.0)
Portfolio: monthly top-20% (rank(ascending=False, pct=True) <= 0.20).
```

## Frozen Parameters

```json
{
  "min_sector_n": 5,
  "w_qgp_surp_real_sn": 0.25,
  "w_value_sn": 0.75,
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
