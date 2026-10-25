# Share count in the research panel: capital increases applied twice or not at all (data audit, not a test)

Date: 2026-10-25. This is a correctness fix to the research panel, not a new signal. It does not add a trial to the ledger.

## How the panel computes market value

`core/pit_panel.py::build_monthly_factors` sets market value = raw close × shares. Shares come from `shares_at`: paid-in capital ("Ödenmiş Sermaye", 1 TL nominal per share) on the latest available balance sheet. Bonus and rights issues dated after that balance sheet's period end are then applied (`share_events.parquet`, from borsapy splits).

The live score does not use this. It takes market value from the data provider (`fast_info`), so this audit concerns the backtests only.

## Audit

Consistency check over all 57,695 consecutive stock-month pairs. A change in panel shares should match the split factor implied by raw and adjusted prices: shares × k when the raw price is divided by k. 615 pairs (220 stocks) differed by more than 25%. 593 of them were share jumps with no price event.

Two causes, both seen in the raw statements:

1. **Registration lag.** The event date falls before a balance sheet's period end, but that balance sheet (and sometimes the next) still shows the old paid-in capital. The old rule applies only events after the period end, so the event is skipped and market value is too low by the event factor. The stock looks cheap.
   - AZTEK: 900% bonus on 2025-12-01; the 2025Q4 balance sheet still shows 100M → market value 10× too low in 2026-04 and 2026-05 (in the value top 20% in 2026-05).
   - DERIM: 400% rights issue on 2019-09-24; 2019Q3 still shows 5.4M → 5× too low in 2019-12 to 2020-03 (in the top 20% in 2020-01 to 2020-03).
   - KATMR: 100% rights issue on 2025-04-14; 2025Q2 still shows the old capital → 2× too low in 2025-09 to 2025-11.
2. **Early registration.** The balance sheet's period end is before the event date, but paid-in capital already includes the increase. The old rule applies the event again, and market value is too high. LINK: 4000% bonus in 2026-03; the 2025Q4 balance sheet already shows the new capital → market value 41× too high in 2026-04 and 2026-05.
3. **Events that never reach capital.** The event list has a rights issue, but paid-in capital never rises (cancelled or not completed). TSPOR: 581.82% on 2025-06-19, capital stays 7.5 billion; BJKAS: 400% on 2025-04-16, capital stays 4.36 billion. Market value 5–7× too high. A live cross-check confirmed it: the data provider's share count today equals the unchanged paid-in capital.
4. **Partly subscribed rights issues.** BJKAS 2024: 400% (×5), capital went 1.2 → 4.36 billion (×3.64).

In the value top 20%, 64 of 8,002 stock-month picks (0.8%) had market value off by more than 1.5×. They returned +0.84% a month against +3.59% for all picks. Falsely cheap names were picked and then did badly.

## Fix

`shares_at(..., history)` looks at the available balance sheets (`history`). For each event dated on or before t and within one year before the current period end:
- *before* = the lowest paid-in capital among available balance sheets in the year before the event.
- **Reflected** when current paid-in ≥ before × (1 + 0.5 × (factor − 1)), i.e. at least half of the increase shows in capital. Then the event is not applied, whatever its date.
- **Not completed** when the current period end is more than 180 days after the event and capital still has not risen. Then the event is not applied.
- Otherwise the event is applied, even when it is dated before the period end (registration lag).
- With no balance sheet in the year before the event, the old rule is used (apply only events after the period end).

Only balance sheets available at t are used, so the rule stays point-in-time. Tests in `tests/test_pit_panel.py`: AZTEK (lag), LINK (early), TSPOR (not completed), BJKAS (partial), old events.

Not fixed:
- 13 balance sheets whose paid-in capital is a one-quarter spike that reverts the next quarter (OYAKC's Q4 values of 785M against 110M in the other quarters of 2018–2019; INTEM 2022Q4). Removing such spikes point-in-time would also delay real capital increases that have no event record (directed issues, mergers: 759 persistent changes without a matching event, median factor 1.36).
- Capital changes the provider does not report: at the panel's last month (2026-09) 4 of 518 stocks still differ from the live share count by more than 10% (AYES, KLRHO, KLYPV, SASA), none with an event record. Before the fix: 9 (also BMSTL, FENER, MERKO, TRILC, VSNMD).

## Effect

Rebuilt with `python scripts/rebuild_panels_share_fix.py` (old files kept in `data/research/pre_share_fix/`). Only market value and the ratios built on it change. Returns, liquidity, GP/A and SUE are identical (checked by the script).
- Stock-months whose market value is off by more than 1.5× from a price-consistent share path (shares changed only when raw and adjusted prices imply it, anchored on the last month): 540 → 108.
- Live share count at the last month (İş Yatırım screener market value ÷ close, 2026-10-25), differences above 10%: 9 → 4 of 518.

Value portfolio (`long_term_research.portfolio`, top 20% by `value_sn_z`, active vs universe, same costs):

| Window | Old panel %/yr (t) | Fixed panel %/yr (t) | Paired difference %/yr (t) | value_sn rank IC old → fixed |
|---|---:|---:|---:|---:|
| Discovery 2013–2020 | +10.65 (2.71) | +10.54 (2.73) | −0.11 (−0.27) | 0.0407 → 0.0410 |
| Holdout 2021+ | +7.36 (2.80) | +7.91 (2.83) | +0.55 (1.18) | 0.0617 → 0.0618 |

270 of about 8,075 top-20% memberships change. The errors did not flatter the backtest. The result moves little, and the ranking IC is unchanged. Earlier studies were computed on the old panel. Their conclusions do not depend on differences of this size, but their exact figures would shift slightly if re-run.

Costed portfolio backtest (`scripts/research_portfolio_backtest.py`, P0, 1M TL, base costs, next-day close; active return vs the gross EW universe), run of 2026-10-17 (old panel) against 2026-10-25 (fixed panel):

| Window | Old %/yr (t) | Fixed %/yr (t) | USD CAGR old → fixed | Max drawdown USD old → fixed |
|---|---:|---:|---:|---:|
| Discovery | +9.81 (2.47) | +9.92 (2.49) | 17.57% → 17.82% | −58.1% → −57.7% |
| Holdout | +6.11 (2.29) | +6.65 (2.48) | 3.61% → 4.20% | −43.9% → −44.0% |
