# Survivorship correction with delisted stocks: pre-registration

Written and committed on 2026-10-17, **before** the corrected panel was built or any return was computed on it. The data rules, the delisting-return assumptions, the metrics and the decision rule are fixed here. They are not changed after the results are seen. A changed rule counts as a new test and needs a new pre-registration.

## Background

- The research panel (`build_pit_panel.py`) holds only stocks listed today. borsapy (TradingView) returns "invalid symbol" for delisted tickers.
- Until now survivorship bias was handled only with break-even rates (`survivorship_sensitivity.py`; `phase1_diagnostics.md` section 3). That method assumes delisting rates; it is not a correction.
- The value evidence behind the live score (value_sn top quintile, `long_term_preregistration.md`) is the result that must be checked.

## What was looked at before this file was written

This is stated so the reader can judge how blind the test is.

1. **Prices.** İş Yatırım `Common/Data.aspx/HisseTekil` was queried for 478 codes: every code in `data/research/delisted_candidates.txt` plus every KAP archive `stock_code` that is not in `config/fintables_ticker_sektor.json`. 57 codes returned prices. For each, only the first date, the last date with volume > 0, the last row date and the last market cap were looked at. No return was computed.
2. **Consistency check on six listed stocks** (THYAO, ASELS, KONYA, BRSAN, ALARK, SISE). İş Yatırım month-end returns against the panel's borsapy returns: correlation 0.995–0.9998. Raw closes are equal. İş Yatırım `PD` (market cap) over panel `mcap`: median 1.000.
3. **Statements.** The İş Yatırım industrial statement table returned data for ARTI and ADANA. AKFEN returned nothing for 2015Q3–2016Q2.
4. **KAP subjects.** For each delisted stock, KAP disclosure subjects from 18 months before to 6 months after the last trade were listed (classification below).

## Data

**Sample of delisted stocks.**
- A code from step 1 is in the sample when all of the following hold:
  - its last trade date (last day with `HGDG_HACIM` > 0) is between 2013-05-01 and 2026-09-30;
  - it is not financial (see below);
  - the industrial-format statement table returns at least one quarter.
- Codes still trading today (ISATR, ISBTR, ISKUR: İş Bankası share classes) are not delisted and are excluded.

**Financial exclusion.**
- The panel excludes financials (`pit_panel.FINANCIAL_SECTORS`). For delisted stocks this is done in two ways:
  - known banks, insurers and securities investment trusts are excluded by code: TEBNK, DENIZ, HALKS, YKBYO, TSKYO, YKFIN, ISATR, ISBTR, ISKUR;
  - a stock without an industrial-format statement is excluded (banks and insurers use other formats).

**Prices.** Each stock's daily series is converted to the panel's input format, and then passes through the unchanged `pit_panel.monthly_prices`:
- raw Close = `HG_KAPANIS`;
- adjusted Close = `HGDG_KAPANIS`;
- Volume = `HGDG_HACIM / HG_KAPANIS`, so that TL volume equals `HGDG_HACIM`.

The series is cut at the last trade date. Zero-volume rows after the last trade are suspension rows; nobody could trade at those prices.

**Shares and market cap.**
- borsapy split events do not exist for delisted codes.
- Changes in İş Yatırım `SERMAYE` (paid-in capital, daily) are converted to share events. Each change is entered as `bonus_pct` = 100 × (new / old − 1).
- With these events, `pit_panel.shares_at` reproduces the share count. Rights issues and bonus issues cannot be told apart. As a result, `nsi_rights_12m` is 0 for delisted stocks. That field is not part of value_sn.

**Statements.**
- The same fetch as the panel: `build_pit_panel.fetch_statement`, 60 quarters.
- Publication dates use the same `apply_report_dates` step: the actual KAP date where the archive has it, otherwise 75 days for interim and 100 days for annual statements.

**Sector.**
- `fintables_ticker_sektor.json` has no delisted codes. The sector is set by hand from the company name, only where the activity is clear. The table is fixed below.
- Every other delisted stock gets a unique label, `BILINMIYOR_<code>`. Its group is then smaller than 5, so `sector_neutralize` demeans it against the whole month.

| Sector | Codes |
|---|---|
| Taş, Toprak, Çimento | ADANA, ADBGR, ADNAC, ASLAN, BOLUC, UNYEC |
| Cam, Seramik, Porselen | ANACM, TRKCM, DENCM, ECYAP |
| Kimya ve Plastik | SODA, PIMAS |
| Holding | AKFEN, DYHOL, KPHOL, EGCYH, TRNSK, ARTI |
| Turizm | NTTUR |
| Gıda Perakendeciliği | KIPA, KILER |
| Giyim, Tekstil ve Deri Ürünleri Perakendeciliği | BOYP |
| Tekstil, Giyim ve Deri | MEMSA, ESEMS |
| Gayrimenkul | SAFGY |
| Ambalaj | OLMK |
| İnşaat | ANELT |
| Enerji Üretim ve Dağıtım | EGCEY |

**Panel.** Corrected panel = current panel rows + delisted stock rows. All rows go through the same `build_monthly_factors`, `prepare` (bottom 30% liquidity cut, ≥ 30 names) and `add_composites`. The baseline is the current panel, run through the same code in the same script.

## Delisting return

Panel rows stop at the last month-end before or on the last trade date. For that row, the forward one-month return is:

(1 + r_partial) × (1 + D) − 1

- r_partial is the adjusted return from that month-end to the last trade date. It is 0 when the last trade is on the month-end itself.
- D is the delisting return.
- `fwd_ret_6m` is set the same way for rows in the last six months, so the value-trap rate includes the exit.
- USD and XU100-excess versions use the unchanged `add_usd_returns`, with the market month of the row.

**Exit class**, decided by rule:
- A stock is a **corporate exit** when any KAP disclosure from 18 months before to 6 months after its last trade has one of these words in its subject or summary: "Devrolma", "Birleşme", "Satma Hakkı", "Ortaklıktan Çıkarma", "Pay Alım Teklifi", "Borsa Kotundan Çıkma".
- Every other stock is an **other exit** (failure, expulsion or unknown).

By the rule, on the KAP listing in step 4:
- corporate: ADANA, ADBGR, ADNAC, ANACM, ANELT, ASCEL, ASLAN, BOLUC, DENCM, DYHOL, ECYAP, KILER, KIPA, NTTUR, OLMK, PIMAS, SAFGY, SODA, TRKCM, UNYEC, USAS;
- other: all remaining sample stocks.

**Specifications.** S1 is primary; S2–S5 are sensitivity checks.

| ID | D for corporate exit | D for other exit |
|---|---|---|
| S1 (primary) | 0 | −30% (Shumway 1997, performance delistings) |
| S2 | 0 | 0 |
| S3 | 0 | −100% |
| S4: rule plus known corrections | 0 | −30% |
| S5: worst case, every exit treated as failure | −100% | −100% |

In S4, AKFEN, BOYP, DGZTE and IZOCM are corporate exits. Outside knowledge says these were going-private deals or mergers, but the KAP archive has no matching disclosure for them.

## Metrics

For the baseline panel and for each specification:

1. **B net active return.** B is the value_sn top quintile; the computation is `long_term_research.portfolio` and `summarize`, unchanged:
   - annualised TL net active return and NW t (6 lags);
   - USD version;
   - value-trap rate;
   - average names.
   - Reported for discovery (2013-01-01 to 2020-12-31) and holdout (2021-01-01 to the end of the data).
2. **value_sn rank IC.** 1-month forward return, mean IC and NW t (6 lags), per period.
3. **Coverage.**
   - number of delisted stocks in the sample;
   - delisted stock-months;
   - the share of B picks that are delisted stocks;
   - the number of B picks whose next month is an exit, by class.

## Decision rule

**Primary (S1).** value_sn **survives the correction** when all three hold:
1. discovery B net active TL > 0 with t > 2.0;
2. holdout B net active TL > 0 with t > 2.0;
3. holdout B net active USD > 0.

Otherwise value_sn is **survivorship-fragile**.

Consequences:
- **Survives:** the live score is unchanged. The report states that the value evidence holds on a panel with delisted stocks.
  - When S5 also meets rules 1–3, the evidence is labelled **robust to the worst case**.
- **Survivorship-fragile:** the live score is not changed automatically, because no other tested model passed and there is nothing better to switch to.
  - The report and README must then state that the value evidence does not survive the correction.
  - The live list is labelled as unconfirmed.
  - The next step is a user decision, not part of this test.

The baseline is run with the same code. It is reported for comparison and is not part of the rule. If the baseline itself does not meet rules 1–2, this is stated. A correction cannot make a baseline that already fails pass.

## Known limits

- **Coverage is partial.**
  - Only delisted codes that İş Yatırım still serves are in the sample: 57 of the 478 probed codes.
  - Most of the other probed codes are not stocks: brokers, funds and bond-issuing leasing and factoring companies. However, some real delisted stocks may be missing, and their count is unknown.
  - Renamed tickers (e.g. KOZAL to TRALT) are not missing: İş Yatırım serves their full history under the new code, which the panel already has.
- The KAP archive has few disclosures for some delisted stocks. The exit rule therefore puts some corporate exits in "other". S4 shows the effect for the four known cases.
- Sector labels for delisted stocks are hand-set and partial.
- The −30% for other exits comes from US data (Shumway 1997). It is not estimated for BIST. S2, S3 and S5 bracket it.
