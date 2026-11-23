# Shadow forward record: pre-registration (2026-11-24)

Paper only. No trades, no change to the live score, rule or workflows. Live stays R0-2026-10-12.

## Why
The 2013+ BIST sample is used up (113+ trials, Rounds 3-4 0/21). The only clean new evidence for the
variants that came closest is out-of-sample time. This record collects it from 2026-12 on.

## What is recorded
`scripts/shadow_record.py` reads only what the daily run already writes:
`data/forward_record/decisions.jsonl` (the monthly `ranking` pool: liquidity-filtered, non-financial,
bm/ep/sp/ey, market_cap, inputs.ttm_op_profit), `data/forward_record/prices/` (adj_close) and the
`universe_snapshot` sector (latest snapshot on or before the decision date).

| variant | construction | top |
|---|---|---|
| R0_top20 (control) | value_sn: per-leg fb.winsorize_z, equal-weight mean, fb.sector_neutralize | 20% |
| R0_top10 | same score | 10% |
| vlab_ep_floor0 | E/P floored at 0 before winsorize_z (Round 4 `score_ep_floor0`) | 20% |
| vlab_op_mcap | E/P leg replaced by TTM operating profit / mcap (Round 4 `score_op_mcap` recipe) | 20% |

Code reuses `scripts/research_round4_vlab_variants.py` (`_leg_z`, `_composite`, `score_ep_floor0`).
n_top = max(1, round(n_scored x pct)), ties broken by ticker. Check: on the 2026-11-01 decision the
recomputed R0_top20 equals the live holdings exactly (47/47).

Returns: equal weight, entry at the first adj_close after decision date t, exit at the first adj_close
after the next successful decision date. Gross of costs (turnover differs; costs are reported as context,
not part of the rule). A pick with no price at entry or exit is left out of that month's mean and counted
in the report. Months missing a successful decision are absorbed into the next holding period.

`data/forward/shadow_record.csv` is append-only: picks for (date, variant) are written once; only empty
return fields are filled later.

## Evaluation rule (fixed now)
- Counted months: decisions with rebalance_date >= 2026-12-01. The 2026-11 decision is recorded but not counted.
- Paired difference D_t = r_variant,t - r_R0_top20,t, per variant.
- Single look after the first **24** counted months with realized returns (about 2028-12). Interim
  reports are descriptive only; no early stopping, no early adoption.
- **PASS** for a variant iff all of: mean D > 0; Newey-West t (lag 1) >= 2.0; mean D > 0 in both
  12-month halves.
- Three variants are tested; a PASS only makes the variant a candidate for a new pre-registered live
  version (with a new forward series). It does not change live by itself. Report results at N_sel + 3.
- No variant, threshold or horizon is added or changed after the first counted month. A bug fix that
  changes picks must be logged here with date and reason; already written rows are never rewritten.
