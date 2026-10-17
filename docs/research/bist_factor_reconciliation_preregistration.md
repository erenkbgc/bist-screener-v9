# 2026 BIST factor study reconciliation: pre-registration

Written and committed on 2026-10-17, **before** the reconciliation script was run on the panel. The factor definitions, universe cuts, weighting schemes, windows, and interpretation rules are fixed here.

## Question

Gökçen (2026, *Borsa Istanbul Review*, "Factor Investing in the Turkish Equity Market") reports that in BIST:
- valuation is the strongest and most consistent factor,
- size, profitability, and momentum are significant in specific sample cuts or weighting schemes, and
- low-risk stocks outperform high-risk stocks.

In our earlier pre-registered tests on the liquid non-financial PIT panel (`backtest_factor_model.py`, `long_term_preregistration.md`), `value_sn` was strong, but:
- 12-1 momentum (`mom_12_1`) had near-zero cross-sectional Rank-IC (+0.007, $t = 0.7$) and negative top-quintile active return,
- gross profitability (`gpa`) did not improve `value_sn`, and
- low volatility (`vol60`) had a strong positive Rank-IC (+0.075, $t = 7.3$) because high-volatility stocks crashed, yet its long-only top quintile lagged the equal-weighted universe (−2.5%/yr) and adding `low_vol_z` as a positive linear weight diluted `value_sn`.

Before proposing any new composite or filter, this diagnostic/reconciliation study tests **why** those differences arise by systematically varying the four methodological choices that differ between academic BIST factor papers and an investable screener universe:
1. **Universe liquidity cut:** all non-financials (`liq_drop = 0.0`) vs our live liquid cut (`liq_drop = 0.30`) vs large/liquid half (`liq_drop = 0.50`).
2. **Portfolio weighting:** equal-weighted (`EW`) vs market-cap value-weighted (`VW`) quintiles, and long-short (`Q5 - Q1`) vs long-only active (`Q5 - Universe`).
3. **Alternative definitions within each factor family:**
   - **Size:** `-log(mcap)` across liquidity cuts (testing whether the size premium in BIST is confined to the illiquid bottom 30% microcap tier that an institutional/1M TL investor cannot trade cheaply).
   - **Profitability:** `GP/A` (`gpa`), `ROE` (`roe`), `ROA` (`ttm_ni / total_assets`), and operating profitability (`OP/A = ttm_ebit / total_assets`), tested both standalone and sector-neutralized, and controlling for `value_sn` in bivariate Fama-MacBeth regressions.
   - **Momentum:** `12-1` (`mom_12_1`) vs `6-1` (`mom_6_1`, 6-month return skipping the last month), evaluated across liquidity tiers and across Discovery (2013–2020) vs Holdout (2021–2026).
   - **Low risk (`vol60`):** asymmetry decomposition between the **long leg** (`Q5 - Universe`, buying the lowest-volatility 20%) and the **avoidance leg** (`Universe - Q1`, avoiding the highest-volatility 20%, and `Universe_ex_Q1 - Universe`), plus drawdown and volatility reduction.

## Data and windows

- C1 monthly panel (`data/research/factors_monthly.parquet`, `monthly_prices.parquet`, `quarterly_ext.parquet`, `fx.parquet`), 2013-04 to 2026-08 (161 months, 528 non-financial tickers).
- **Full sample:** 2013-04 to 2026-08.
- **Discovery:** 2013-04 to 2020-12 (93 months).
- **Holdout:** 2021-01 to 2026-08 (68 months).

## Hypotheses and diagnostic tests (fixed)

### R1. Size (`size = -mcap`): microcap illiquidity vs investable size effect
- Compute Rank-IC, EW `Q5 - Q1` spread, EW `Q5 - Universe` active return, and VW `Q5 - Q1` spread under three liquidity cuts: `liq_drop = 0.0` (all stocks), `0.30` (live universe), and `0.50` (liquid half), plus bivariate Fama-MacBeth slope of `size_z` controlling for `tlvol60` (log illiquidity/volume) and `value_sn_z`.
- **Question answered:** Does the BIST size premium survive once the least liquid 30% microcaps are excluded or when portfolios are value-weighted?

### R2. Profitability (`gpa`, `roe`, `roa`, `opa`): definition comparison
- Definitions (all point-in-time from the usable quarterly statement at month-end):
  - `gpa`: TTM gross profit / total assets (`factors_monthly.parquet`),
  - `roe`: TTM net income / book equity (`factors_monthly.parquet`),
  - `roa`: TTM net income / total assets (`statement_features`),
  - `opa`: TTM operating profit (EBIT) / total assets (`ttm_ebit / total_assets`).
- For each metric on the liquid universe (`liq_drop = 0.30`):
  - Standalone Rank-IC (1m), EW `Q5 - Q1` spread, EW `Q5 - Universe` active return, and VW `Q5 - Q1` spread in Discovery and Holdout,
  - Bivariate Fama-MacBeth slope alongside `value_sn_z` (`ret ~ 1 + value_sn_z + prof_z`).
- **Question answered:** Does `ROE`, `ROA`, or `OP/A` carry stronger cross-sectional predictive power in BIST than `GP/A`, either standalone or after controlling for `value_sn`?

### R3. Momentum (`mom_12_1` vs `mom_6_1`): horizon, weighting, and regime
- Definitions:
  - `mom_12_1`: $P_{t-1} / P_{t-12} - 1$ (`factors_monthly.parquet`),
  - `mom_6_1`: $P_{t-1} / P_{t-6} - 1$ built from monthly adjusted closes (`monthly_prices.parquet`).
- Compare Rank-IC, EW `Q5 - Q1`, EW `Q5 - Universe`, and VW `Q5 - Q1` across `liq_drop = 0.0` vs `0.30` and Discovery vs Holdout.
- **Question answered:** Is momentum significant in long-short (`Q5 - Q1`), value-weighted, or 6-1 form even when long-only EW `Q5 - Universe` fails?

### R4. Low volatility (`vol60`): long-leg bonus vs high-volatility tail avoidance
- On the liquid universe (`liq_drop = 0.30`), decompose the monthly return of `vol60` quintiles (`Q1` = highest volatility, `Q5` = lowest volatility):
  - Long-short `Q5 - Q1` (academic anomaly definition),
  - Long-only top quintile `Q5 - Universe` (buying low-vol stocks),
  - High-vol loser drag `Q1 - Universe` (what the riskiest 20% returns relative to the universe),
  - Exclusion portfolio `Universe_ex_Q1 - Universe` (dropping the highest-volatility 20% from the universe),
  - Within-value exclusion: top 20% by `value_sn_z` after dropping the highest-volatility 20% of the universe vs plain `value_sn_z` top 20% (gross and 20 bps turnover-adjusted active return, volatility, and max drawdown).

## Role of this study

This is a **reconciliation and hypothesis-qualification study**. It does not alter `config/live_rule.json`. Its output determines which candidate hypotheses (e.g., `ROE` or `OP/A` quality interaction with value, or high-volatility tail exclusion) warrant a dedicated costed portfolio pre-registration in P2.

## Results (added 2026-10-17, after the run; the sections above are unchanged)

Runner: `python3 scripts/research_bist_factor_reconciliation.py` → `data/reports/research_bist_factor_reconciliation_2026-10-17.json`.

### R1. Size (`size = -log(mcap)`): microcap illiquidity vs investable universe

| Universe Liquidity Cut | Window | Rank-IC ($t$) | EW `Q5 - Q1` %/yr ($t$) | EW `Q5 - Univ` %/yr ($t$) | VW `Q5 - Q1` %/yr ($t$) |
|---|---|---:|---:|---:|---:|
| **All non-financials (`liq_drop = 0.0`)** | Full (161m) | −0.0000 (−0.00) | **+33.72% (+3.12)** | **+21.05% (+3.43)** | **+31.10% (+2.94)** |
| | Discovery (93m) | +0.0145 (+0.83) | +41.97% (+2.55) | +22.83% (+2.38) | +40.52% (+2.64) |
| | Holdout (68m) | −0.0199 (−0.90) | +22.43% (+1.95) | +18.62% (+2.98) | +18.22% (+1.40) |
| **Live liquid cut (`liq_drop = 0.30`)** | Full (161m) | −0.0296 (−1.92) | +12.60% (+1.50) | +8.25% (+1.77) | +14.39% (+1.49) |
| | Discovery (93m) | −0.0096 (−0.51) | +25.08% (+2.28) | +13.96% (+2.29) | +29.56% (+2.30) |
| | Holdout (68m) | **−0.0570 (−2.45)** | **−4.47% (−0.40)** | **+0.42% (+0.06)** | **−6.35% (−0.50)** |
| **Large/liquid half (`liq_drop = 0.50`)** | Full (161m) | −0.0462 (−2.63) | +9.53% (+1.01) | +4.54% (+0.87) | +7.30% (+0.76) |
| | Discovery (93m) | −0.0170 (−0.82) | +25.70% (+2.19) | +12.70% (+1.96) | +23.31% (+1.96) |
| | Holdout (68m) | **−0.0860 (−3.36)** | **−12.59% (−0.97)** | **−6.62% (−0.89)** | **−14.60% (−1.06)** |

- **Joint Fama-MacBeth (`fwd_ret_1m ~ size_z + log_tlvol_z + value_sn_z`) on `liq_drop = 0.30`:**
  - Discovery (93m): `size_z` +4.21%/yr ($t = 1.52$), `log_tlvol_z` −5.80%/yr ($t = -1.73$), `value_sn_z` **+8.57%/yr ($t = 2.91$)**.
  - Holdout (68m): `size_z` **−6.36%/yr ($t = -1.35$)**, `log_tlvol_z` −6.12%/yr ($t = -2.02$), `value_sn_z` **+7.01%/yr ($t = 1.95$)**.
- **Reconciliation conclusion (R1):** The academic BIST size premium (+33.72%/yr, $t = 3.12$ unfiltered) is driven almost entirely by the **bottom 30% illiquid microcap tail** and pre-2021 months. Inside the investable liquid universe (`liq_drop = 0.30`), `size` has a significantly negative Rank-IC in Holdout (−0.0570, $t = -2.45$), negative `Q5 - Q1` spread (−4.47%/yr), and negative Fama-MacBeth slope after controlling for liquidity and `value_sn`.

### R2. Profitability (`gpa`, `roe`, `roa`, `opa`) on `liq_drop = 0.30`

| Metric (Sector-Neutral) | Full (161m) Rank-IC ($t$) | Discovery (93m) Rank-IC ($t$) | Holdout (68m) Rank-IC ($t$) | Holdout EW `Q5 - Q1` %/yr ($t$) | Discovery FM Slope w/ `value_sn` %/yr ($t$) | Holdout FM Slope w/ `value_sn` %/yr ($t$) |
|---|---:|---:|---:|---:|---:|---:|
| `gpa_sn` (`GP/A`) | +0.0182 (+2.86) | +0.0143 (+1.74) | +0.0236 (+2.41) | +6.00% (+1.30) | −0.64% (−0.47) | +0.51% (+0.24) |
| `roe_sn` (`NI/Equity`) | +0.0243 (+2.93) | +0.0151 (+1.27) | **+0.0368 (+3.78)** | **+10.65% (+2.32)** | −3.54% (−1.75) | **+3.38% (+2.00)** |
| `roa_sn` (`NI/Assets`) | +0.0243 (+2.88) | +0.0214 (+1.70) | +0.0282 (+2.93) | +3.74% (+0.77) | −3.39% (−1.66) | +0.48% (+0.26) |
| `opa_sn` (`EBIT/Assets`) | **+0.0301 (+4.23)** | **+0.0296 (+2.81)** | **+0.0307 (+3.66)** | +7.34% (+1.55) | −2.75% (−1.24) | +2.04% (+1.09) |

- **Reconciliation conclusion (R2):**
  1. Across all four definitions, **`GP/A` has the weakest Rank-IC (+0.0182, $t = 2.86$)**, whereas **`OP/A` (`ttm_ebit / total_assets`, IC +0.0301, $t = 4.23$) and `ROE` (Holdout IC +0.0368, $t = 3.78$; Holdout EW `Q5 - Q1` +10.65%/yr, $t = 2.32$) are substantially stronger** in BIST.
  2. However, when entered alongside `value_sn_z` in a bivariate Fama-MacBeth regression (`ret ~ value_sn_z + prof_sn_z`), **all four profitability metrics have negative marginal slopes in Discovery (2013–2020)** because `value_sn` already embeds `ep` (`NI/mcap`) and `ey` (`EBIT/EV`). Only `roe_sn` achieves a borderline positive marginal slope in Holdout (+3.38%/yr, $t = 2.00$). Adding linear profitability weights to `value_sn` is therefore not justified on the non-financial panel; `ROE`'s primary value-add remains in the dedicated financial/banking model where `ey` and `sp` are structurally absent.

### R3. Momentum (`mom_12_1` vs `mom_6_1`) across liquidity cuts and weighting

| Signal & Universe | Window | Rank-IC ($t$) | EW `Q5 - Q1` %/yr ($t$) | EW `Q5 - Univ` %/yr ($t$) | VW `Q5 - Q1` %/yr ($t$) |
|---|---|---:|---:|---:|---:|
| `mom_12_1` (`liq_drop = 0.0`) | Full (161m) | +0.0016 (+0.18) | +3.89% (+0.78) | −1.16% (−0.39) | +7.10% (+0.93) |
| `mom_12_1` (`liq_drop = 0.30`) | Full (161m) | +0.0070 (+0.77) | +6.21% (+1.40) | **−2.33% (−0.85)** | +8.49% (+1.19) |
| | Discovery (93m) | +0.0052 (+0.58) | +4.30% (+0.75) | −3.79% (−1.13) | +6.64% (+0.69) |
| | Holdout (68m) | +0.0096 (+0.55) | +8.81% (+1.27) | −0.33% (−0.07) | +11.01% (+1.02) |
| `mom_6_1` (`liq_drop = 0.0`) | Full (161m) | +0.0027 (+0.37) | +8.81% (+1.74) | +2.47% (+0.89) | +6.17% (+0.78) |
| `mom_6_1` (`liq_drop = 0.30`) | Full (161m) | +0.0110 (+1.35) | **+10.58% (+2.30)** | +2.64% (+0.91) | +6.74% (+0.83) |
| | Discovery (93m) | +0.0067 (+0.66) | +7.08% (+1.17) | +0.08% (+0.02) | +1.61% (+0.17) |
| | Holdout (68m) | +0.0170 (+1.27) | **+15.38% (+2.28)** | +6.14% (+1.26) | +13.76% (+0.97) |

- **Reconciliation conclusion (R3):**
  1. Standard `12-1` momentum has positive long-short `Q5 - Q1` spreads (+6.21%/yr EW, +8.49%/yr VW on `liq_drop = 0.30`), but **its long leg (`Q5`) underperforms the equal-weighted universe (−2.33%/yr, $t = -0.85$)** — the spread comes from `Q1` losers rather than `Q5` winners.
  2. Shorter `6-1` momentum (`mom_6_1`) on the liquid universe produces a statistically significant **long-short EW `Q5 - Q1` spread of +10.58%/yr ($t = 2.30$)** over the full sample (+15.38%/yr, $t = 2.28$ in Holdout), reconciling the academic finding that medium-term momentum exists in BIST, yet its long-only active return (`EW Q5 - Univ` +2.64%/yr, $t = 0.91$) is still too weak and high-turnover to pass our long-only screener hurdle.

### R4. Low volatility (`vol60_z`, high = low vol): long-leg vs high-volatility tail avoidance

| Portfolio Spread (`liq_drop = 0.30`) | Full Sample (161m) %/yr ($t$) | Discovery (93m) %/yr ($t$) | Holdout (68m) %/yr ($t$) |
|---|---:|---:|---:|
| Long leg: `Q5 (lowest vol) - Universe` | −0.97% (−0.27) | −8.21% (−1.71) | +8.92% (+2.34) |
| Short leg: `Q1 (highest vol) - Universe` | **−8.63% (−2.51)** | **−7.00% (−1.87)** | **−10.86% (−1.76)** |
| Long-short anomaly: `Q5 - Q1` | +7.66% (+1.29) | −1.21% (−0.19) | **+19.78% (+2.08)** |
| Universe tail filter: `Universe_ex_Q1 - Universe` | **+2.17% (+2.51)** | +1.75% (+1.86) | +2.75% (+1.77) |
| Baseline value: `value_sn Top 20% - Universe` | **+10.11% (+3.96)** | **+11.50% (+2.88)** | **+8.21% (+3.13)** |
| Filtered value: `value_sn Top 20% (ex Q1 high-vol) - Universe` | +8.27% (+3.72) | +7.86% (+2.63) | +8.83% (+2.58) |
| **Paired difference: `value_ex_highvol - value_sn`** | **−1.84% (−1.33)** | **−3.63% (−1.83)** | **+0.62% (+0.41)** |

- **Reconciliation conclusion (R4):**
  1. Across the full 161-month sample, the low-volatility effect in BIST is **100% a high-volatility tail-avoidance effect**: the lowest-volatility quintile (`Q5`) does not beat the universe (−0.97%/yr, $t = -0.27$), whereas the highest-volatility quintile (`Q1`) trails the universe by **−8.63%/yr ($t = -2.51$)**. Dropping `Q1` from the broad universe lifts the equal-weighted universe return by +2.17%/yr ($t = 2.51$).
  2. However, **applying a hard `Q1` high-volatility exclusion before selecting the top 20% `value_sn` portfolio reduces full-sample return by −1.84%/yr ($t = -1.33$; Discovery −3.63%/yr, $t = -1.83$; Holdout +0.62%/yr, $t = +0.41$)**. Because `value_sn` already requires strong fundamental multiples (`B/M`, `E/P`, `EV/EBITDA`, `S/P`), it naturally excludes speculative unprofitable `Q1` story-stocks, while a hard volatility cap prematurely filters out deeply discounted cyclical value winners during recovery months.
