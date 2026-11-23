# Pre-registration: value_sn metric-count sensitivity (vlab_metric_count)

Date: 2026-11-24. Source: external code review, item P1 ("score reliability differs when a stock is scored on 4 legs vs 2").

## Question
R0 (`value_sn`) averages the z-scores of the available legs among bm, ep, sp and ey, then sector-neutralizes. Does requiring a minimum number of valid legs improve the portfolio?

## Variants (3; the score is unchanged, only eligibility changes)
- V0 = R0 (control, not a trial).
- mc_v1_min2: only stocks with >= 2 valid legs.
- mc_v2_min3: only stocks with >= 3 valid legs.
- mc_v3_all4: only stocks with all 4 valid legs.

Diagnostic before any return was computed (lag75 panel, liquid universe): legs per stock-month are 4 legs 94.6%, 3 legs 4.3%, 2 legs 0.02%, 1 leg 1.1%. Inside the R0 top 20%: 4 legs 95.8%, 3 legs 3.2%, 1 leg 0.9%. So mc_v1_min2 and mc_v2_min3 differ by only ~0.02% of rows, and all effects are expected to be small. Sectors with most missing legs: Spor 85%, mining 28%, metal goods/machinery 22%, holdings 12%. These are reported, not used to choose variants.

## Fixed gauntlet (Round 4 rule, unchanged)
PASS iff ALL: (1) full 2013-04..latest paired D vs R0 > 0 with NW t >= 2.0; (2) D > 0 in EACH of 4 blocks 2013-16, 2017-20, 2021-23, 2024+; (3) USD maxDD not worse than R0 by > 2pp in full and 2021+; (4) also holds on kapdates panel (D>0, t>=1.0); (5) Holm-adjusted p < 0.05 within this batch (m = 3); (6) one-way turnover <= 1.5x R0. Same universe, liquidity cut, 1M TL costs, next-close fills as R0. Report DSR at updated N_sel.

The 2021+ period has been seen many times, so a PASS only qualifies for the shadow forward record; it does not change the live rule.

Trial ledger: +3 (N_sel 113 -> 116).
