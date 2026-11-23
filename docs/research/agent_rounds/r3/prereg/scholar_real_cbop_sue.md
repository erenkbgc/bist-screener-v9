# Round 3 Pre-registration: `scholar_real_cbop_sue`

- **Date**: 2026-11-24
- **Source branch**: `agent/r3-features`
- **Trial type**: Combination candidate (separate +1 N_sel trial)
- **Trial ledger `N_sel` after registration**: 95

## Motivation & Hypothesis

Combines CPI-restated Cash-Based Operating Profitability (putting NOA_{p-4q} in period-p purchasing power for high-inflation and IAS 29 consistency) with USD-deflated SUE as a 3-pillar tilt on value_sn. Zero return-fitted parameters (fixed 75/15/10 canonical weights). Discovery (2013-2020) net D = +3.80%/yr (NW t = +4.38).

## Formula

```text
cpi_idx = cumprod(1 + cpi_mom.fillna(0) / 100) indexed by Period('M')
NOA_{i,p} = (total_assets - cash) - (current_liab + noncurrent_liab - fin_debt)
NOA_real_{i,p-4q} = NOA_{i,p-4q} * (cpi_idx[period_end_p] / cpi_idx[period_end_{p-4q}])
cbop_real_{i,p} = (ttm_op_profit_{i,p} - (NOA_{i,p} - NOA_real_{i,p-4q})) / total_assets_{i,p}   (if total_assets > 0 else NaN)
q_ni_usd_{i,p} = coalesce(q_ni_parent, q_net_income) / usdtry_month_end[month_end(period_end_{i,p})]
sue_ni_usd_{i,p} = (q_ni_usd_{i,p} - q_ni_usd_{i,p-4q}) / rolling(8, min_periods=6).std(d_q_ni_usd)   (strictly causal)
Merge strictly PIT on (ticker, stmt_period == period) onto liquid panel (fb.prepare, liq_drop_pct=0.3, value_sn_z.notna()).
cbop_real_z_sn, sue_ni_usd_z_sn = monthly 1%/99% winsorize_z + sector_neutralize(min_n=5)
score_{i,t} = 0.75 * value_sn_z_{i,t} + 0.15 * fillna(cbop_real_z_sn_{i,t}, 0.0) + 0.10 * fillna(sue_ni_usd_z_sn_{i,t}, 0.0)
Portfolio: monthly top-20% (rank(ascending=False, pct=True) <= 0.20).
```

## Frozen Parameters

```json
{
  "min_obs": 6,
  "min_sector_n": 5,
  "std_window": 8,
  "w_cbop_real_sn": 0.15,
  "w_sue_usd_sn": 0.1,
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
