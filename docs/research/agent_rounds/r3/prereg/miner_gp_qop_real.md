# Round 3 Pre-registration: `miner_gp_qop_real`

- **Date**: 2026-11-24
- **Source branch**: `agent/r3-features`
- **Trial type**: Combination candidate (separate +1 N_sel trial)
- **Trial ledger `N_sel` after registration**: 98

## Motivation & Hypothesis

Combines two nearly orthogonal pillars (pairwise corr = +0.07): slow 12m Gross Profit Yield (ttm_gross_profit/mcap = Gross Margin x Sales Yield, capturing pricing power scaled by equity price) and fast 1m-3m CPI-adjusted quarterly operating profit surprise yield (qop_surp_real/mcap, capturing real operating PEAD above FX/tax noise). Zero return-fitted parameters (fixed 70/15/15 canonical tilt). Discovery (2013-2020) net D = +2.98%/yr (NW t = +2.21), 7/8 years positive.

## Formula

```text
cpi_idx = cumprod(1 + cpi_mom.fillna(0) / 100) indexed by Period('M')
qop_surp_real_{i,p} = q_op_profit_{i,p} - q_op_profit_{i,p-4q} * (cpi_idx[period_end_p] / cpi_idx[period_end_{p-4q}])
Merge ttm_gross_profit and qop_surp_real strictly PIT on (ticker, stmt_period == period) onto liquid panel (fb.prepare, liq_drop_pct=0.3, value_sn_z.notna()).
For mcap > 0: gp_mcap_{i,t} = ttm_gross_profit_{i,p} / mcap_{i,t};  qop_surp_real_mcap_{i,t} = qop_surp_real_{i,p} / mcap_{i,t}
gp_mcap_z_sn, qop_surp_real_mcap_z_sn = monthly 1%/99% winsorize_z + sector_neutralize(min_n=5)
score_{i,t} = 0.70 * value_sn_z_{i,t} + 0.15 * fillna(gp_mcap_z_sn_{i,t}, 0.0) + 0.15 * fillna(qop_surp_real_mcap_z_sn_{i,t}, 0.0)
Portfolio: monthly top-20% (rank(ascending=False, pct=True) <= 0.20).
```

## Frozen Parameters

```json
{
  "min_sector_n": 5,
  "w_gp_mcap_sn": 0.15,
  "w_qop_surp_real_sn": 0.15,
  "w_value_sn": 0.7,
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
