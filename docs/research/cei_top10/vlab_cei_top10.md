# Pre-registration: composite equity issuance (CEI) and R0 top 10%

Date: 2026-11-24. Source: external review suggestions 1 and 2. Script: `scripts/research_cei_top10.py`.

## Signal
CEI_5y(i, t) = sum over capital events e with t-60m < date_e <= t of log((1 + R_e + B_e + BD_e) / (1 + B_e + BD_e)), where R = rights issue %, B = bonus from capital %, BD = bonus from dividend % (borsapy splits table, effective dates, 1998+). Bonus issues do not change firm value and are removed; rights issues stay. No recorded event in the window means 0. Expected sign: issuers underperform (Daniel and Titman 2006; Hanauer and Lauterbach on emerging markets).

Why event-based: İş Yatırım daily market value history starts in 2012, so the market-value form log(ME_t / ME_t-5y) - return would only exist from 2017 and could not cover the 2013-16 block.

Known limits: buybacks and cancellations are not in the event table, so CEI is never negative. 192 of the cached tickers have no event table (treated as 0). Rights issues priced at nominal value overstate the cash raised.

Diagnostics before any return was computed (lag75 liquid panel): CEI > 0 in 19.2% of stock-months (11-29% by year), corr with value_sn_z -0.10. A pure -CEI rank would be mostly ties at 0, so the standalone test is written as an exclusion rule.

## Variants (3)
1. r0_no_issuers: R0 top 20% among stocks with CEI_5y = 0.
2. value_cei_20: 0.8 * value_sn_z + 0.2 * (-CEI_5y winsorized z, sector-neutral; missing -> 0), top 20%.
3. r0_top10: R0 value_sn_z, top 10% instead of 20%. Note: this idea comes from Round 4 regime diagnostics that used 2021+ data (top 5% +13.94%/yr vs 10-20% +6.22%/yr), so it is holdout-informed. It is also in the shadow forward record (PR #110), which is the decisive test.

Note on overlap: the Phase 2 long-term study tested a 12-month "no rights issue" filter (nsi_rights_12m = 0) as part of a combined filter set. Variant 1 uses a 5-year, bonus-neutral window and is tested alone.

## Fixed gauntlet (Round 4 rule, unchanged)
PASS iff ALL: (1) full 2013-04..latest paired D vs R0 > 0 with NW t >= 2.0; (2) D > 0 in EACH of 4 blocks 2013-16, 2017-20, 2021-23, 2024+; (3) USD maxDD not worse than R0 by > 2pp in full and 2021+; (4) also holds on kapdates panel (D>0, t>=1.0); (5) Holm-adjusted p < 0.05 within this batch (m = 3); (6) one-way turnover <= 1.5x R0. Same universe, liquidity cut, 1M TL costs, next-close fills as R0. Report DSR at updated N_sel.

A PASS only qualifies for the shadow forward record; it does not change the live rule.

Trial ledger: +3 (N_sel 116 -> 119).
