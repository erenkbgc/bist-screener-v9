# Pre-registration: Round 4 vlab batch1 (value_sn construction repairs)

Date: 2026-11-24. Run by the manager (Claude) because the vlab agent hit its quota before testing.
Code: scripts/research_round4_vlab_variants.py on branch agent/r4-vlab. Harness: scripts/research_round4_vlab.py.

Source of ideas: r4-board/notes/hypotheses.md (Rank 1, 2, 3a). Those hypotheses were written after block-level diagnostics that included 2021+ data, so this batch is holdout-informed. A PASS only qualifies for a shadow forward record from 2026-12; it does not change the live rule.

## Variants (5, all frozen, no return-fitted parameters)
Each rebuilds R0 exactly (per-month winsorize_z of each leg on the liquidity-filtered universe, equal-weight mean of available legs, sector_neutralize) and changes one thing. Rebuild parity with value_sn_z checked: max abs diff 0.0 on both panels.

1. vlab_rev_ev: S/P replaced by TTM revenue / EV, EV = mcap + fin_debt - cash > 0 (same EV as the ey leg).
2. vlab_gp_ev: S/P replaced by TTM gross profit / EV.
3. vlab_op_mcap: E/P replaced by TTM operating profit / mcap.
4. vlab_ep_floor0: E/P floored at 0 before winsorize_z.
5. vlab_val_mom15: 0.85 * value_sn_z + 0.15 * sector-neutral mom_12_1_z (missing momentum -> 0).

Monthly top 20%, same universe, liquidity cut, 1M TL costs, next-close fills as R0.

## Fixed gauntlet (copied from the Round 4 rule)
PASS iff ALL: (1) full 2013-04..latest paired D vs R0 > 0 with NW t >= 2.0; (2) D > 0 in EACH of 4 blocks 2013-16, 2017-20, 2021-23, 2024+; (3) USD maxDD not worse than R0 by > 2pp in full and 2021+; (4) also holds on kapdates panel (D>0, t>=1.0); (5) Holm-adjusted p < 0.05 within this batch (m = 5); (6) one-way turnover <= 1.5x R0. Report DSR at updated N_sel.

Trial ledger: +5 (N_sel 108 -> 113).
Note: this branch's ledger reads 103 because risk (+8) and ml (+2) trials live on their own branches; the cross-branch N_sel after this batch is 113.
