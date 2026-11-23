# Round 3 Pre-registration: `scholar_sue_usd`

- **Date**: 2026-11-24
- **Source branch**: `agent/r3-features`
- **Trial type**: Combination candidate (separate +1 N_sel trial)
- **Trial ledger `N_sel` after registration**: 94

## Motivation & Hypothesis

Atilgan (2026, Sabanci CEF), Ahlatcioglu & Okay (2021, BIR), Novy-Marx (2015), and Konchitchki (2011): translating discrete quarterly net income to USD at quarter-end USD/TRY removes nominal TL inflation/FX drift from YoY earnings surprises while retaining PEAD alpha orthogonal to static value. Zero return-fitted parameters (fixed 80/20 canonical tilt). Discovery (2013-2020) net D = +1.72%/yr (NW t = +1.64), coverage 84.5%.

## Formula

```text
q_ni_{i,p} = coalesce(q_ni_parent_{i,p}, q_net_income_{i,p})
q_ni_usd_{i,p} = q_ni_{i,p} / usdtry_month_end[month_end(period_end_{i,p})]
d_q_ni_usd_{i,p} = q_ni_usd_{i,p} - q_ni_usd_{i,p-4q}
sue_ni_usd_{i,p} = d_q_ni_usd_{i,p} / rolling(window=8, min_periods=6).std(d_q_ni_usd)   (strictly causal: available_at <= current)
Merge strictly PIT on (ticker, stmt_period == period) onto liquid panel (fb.prepare, liq_drop_pct=0.3, value_sn_z.notna()).
sue_ni_usd_z_sn = fb.sector_neutralize(fb.winsorize_z(sue_ni_usd, 0.01, 0.99), min_n=5)
score_{i,t} = 0.80 * value_sn_z_{i,t} + 0.20 * fillna(sue_ni_usd_z_sn_{i,t}, 0.0)
Portfolio: monthly top-20% (rank(ascending=False, pct=True) <= 0.20).
```

## Frozen Parameters

```json
{
  "min_obs": 6,
  "min_sector_n": 5,
  "std_window": 8,
  "w_sue_usd_sn": 0.2,
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
