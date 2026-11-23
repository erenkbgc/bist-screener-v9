# emdata: other high-inflation markets, data feasibility (round 5)

Role: emdata. Branch `agent/r5-emdata`. Prototype `scripts/fetch_cvm_brazil.py` with tests in `tests/test_fetch_cvm_brazil.py`. No return backtests were run.

## Verdict

**Brazil is the only market where a free, point-in-time, survivorship-free panel of the four value_sn legs is practical.** The official regulator (CVM) and exchange (B3) data cover everything value_sn needs, and the prototype now builds the legs from it. Argentina, Nigeria, Egypt and Pakistan have no free bulk structured filings. For those markets, only prices (and sometimes vendor snapshots without filing dates) can be had cheaply. They are not worth building now.

Brazil caveat for the research question: it had high but not hyper inflation (IPCA peaked at about 10-12% in 2015/2016 and 2021/2022) and it does not apply IAS 29. It tests "does value_sn survive in another volatile EM with a weak currency". It does not test "does it survive in an IAS 29 regime". Argentina (IAS 29 since 2018) would be the real IAS 29 analogue, but its data are not available programmatically (see rank 4).

## Ranked sources

| Rank | Source | Market | What it gives | Point in time | Survivorship | ToS/access | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | **CVM dados abertos** DFP (annual, 2010+) and ITR (quarterly, 2011+) zips: `dados.cvm.gov.br/dados/CIA_ABERTA/DOC/{DFP,ITR}/DADOS/` | Brazil | BPA, BPP, DRE, DFC, DMPL, consolidated and individual statements on a standardized chart of accounts (3.01 revenue, 3.05 EBIT, 3.11.01 parent net income, 2.03 equity, 2.03.09 non-controlling interests, 2.01.04 and 2.02.01 loans, 1.01.01 and 1.01.02 cash). `composicao_capital` has ON/PN shares and treasury shares per filing | **Yes.** The index file has `DT_RECEB` (CVM receipt date), `VERSAO` and `ID_DOC`. Current-period columns (`ÚLTIMO`) avoid later restated comparatives | Good. All registrants, including companies later cancelled. `cad_cia_aberta.csv` has `SIT` and `DT_CANCEL` | Open-data licence (gov.br open data, free reuse). **Cloudflare returns 403 to this host (WSL/residential IP, curl and WebFetch both blocked).** The prototype falls back to the identical files on web.archive.org (`id_` raw copies, verified as valid zips). | **Build** |
| 2 | **B3 COTAHIST** annual files: `bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{YYYY}.ZIP` | Brazil | Daily OHLC, volume and trade count for every listed instrument, 1986+ (use 1995+ after the Plano Real) | Yes (raw end-of-day) | Includes every ticker that traded that year, so delisted names are present | Free public download. Reachable directly from here (200 OK) | **Build.** Raw, unadjusted: dividends and splits must be adjusted (ISIN plus CVM/B3 corporate events). Volume supports the 30% liquidity cut |
| 3 | yfinance `.SA` tickers | Brazil | Adjusted prices; vendor fundamentals for about 4 years only | No filing dates | Delisted tickers missing | Unofficial; Yahoo ToS | Prices only, as a cross-check |
| 4 | CNV AIF (`aif2.cnv.gov.ar`) / BYMA | Argentina | Statements as PDFs per filing. No open-data bulk export or API found. BYMA open data has prices only | Filing dates are visible per document but would need scraping | Unknown | No bulk API. Scraping PDFs means parsing (XBRL is not mandatory) | Not feasible cheaply. Prices are possible via yfinance `.BA` or BYMA; fundamentals would need hand or LLM PDF extraction for about 60 names |
| 5 | stockanalysis.com / Macrotrends | AR, BR, NG, EG, PK | Vendor fundamentals (stockanalysis covers about 10-20 years for some exchanges) | No filing dates, survivors only | Survivor-biased | ToS forbids scraping; paid export | Do not use for point-in-time research |
| 6 | NGX (Nigeria), EGX (Egypt), PSX (Pakistan) | NG, EG, PK | Exchange PDFs and announcements; PSX has daily price files | Filing dates appear only in announcements | Weak | No structured fundamentals | Not feasible. Egypt (2016-2017 and 2022-2024) and Nigeria (2023+) would be good high-inflation episodes, but would need a paid vendor (LSEG, Bloomberg, S&P Capital IQ) |
| 7 | Kaggle / academic datasets (Economatica, Compustat Global, LSEG Worldscope) | All | Clean panels | Worldscope has partial point-in-time | Good (paid) | Licensed; university access only | Best option if a university licence is available. Not free |

## Prototype status (Brazil)

`scripts/fetch_cvm_brazil.py`:
- Downloads DFP for y-2 and y-1, ITR for y-1 and y, and COTAHIST for y. Results are cached in `scratch/cvm/` (gitignored scratch). There is a 2 s sleep per request and a direct-then-archive fallback.
- For each (company, period), it uses the first receipt date (`DT_RECEB`) as the availability date, YTD current-period DRE rows, and parent equity = 2.03 - 2.03.09.
- TTM = YTD_P + FY(y-1) - YTD(P-4), the same formula as the BIST panel. Values are nominal BRL, with no IAS 29 handling.
- Market cap = (ON - treasury) x ON close + (PN - treasury) x PN close. Units are taken from the "lot market" (TPMERC 010).
- `value_legs` mirrors `core/pit_panel.py::value_ratios`: bm only if equity > 0; ey only if EV > 0 and debt and cash are both known.
- Sample: PETR, VALE, WEGE, ABEV, LREN, SUZB, GGBR, EMBR, RADL, CMIG, at 2024 month-ends.
- Tests: 4 offline unit tests (TTM, leg definitions, filing-date gating, COTAHIST parsing), all passing.

**Run result (`--year 2024`)**: 120 rows, all 10 tickers at all 12 month-ends, and every leg populated. Output in `scratch/cvm/panel_sample.csv`. Snapshot at 2024-12-31 (statement 2024Q3, filed 2024-10-24 to 11-13):

| ticker | mcap (BRL bn) | bm | ep | sp | ey |
|---|---|---|---|---|---|
| PETR | 490 | 0.80 | 0.17 | 1.03 | 0.22 |
| VALE | 233 | 0.90 | 0.21 | 0.91 | 0.25 |
| WEGE | 221 | 0.09 | 0.03 | 0.16 | 0.03 |
| ABEV | 185 | 0.53 | 0.08 | 0.45 | 0.12 |
| LREN | 11.6 | 0.90 | 0.11 | 1.22 | 0.13 |
| SUZB | 77 | 0.54 | 0.05 | 0.57 | 0.10 |
| GGBR | 37 | 1.50 | 0.13 | 1.76 | 0.18 |
| EMBR | 41 | 0.41 | 0.06 | 0.76 | 0.07 |
| RADL | 38 | 0.17 | 0.03 | 1.00 | 0.06 |
| CMIG | 35 | 0.80 | 0.23 | 1.10 | 0.24 |

Market caps match public figures to the right order of magnitude (PETR about 490bn, VALE about 230bn).

**Data issue found:** `composicao_capital` has no unit column. VALE, ABEV, LREN, EMBR and CMIG report shares in thousands, which made their mcap 1000x too small. The prototype now detects this (equity/mcap > 50 means multiply shares by 1000) and flags it in `shares_x1000`. A full build should replace this heuristic with B3 or FCA share counts.

## Known gaps before a full Brazil panel

1. **Ticker map.** The prototype hardcodes CD_CVM to ticker root. A full build needs the FCA `valor_mobiliario` file (also on CVM open data), which gives ticker codes per CNPJ, or ISIN matching against COTAHIST.
2. **Versions.** The yearly DADOS zip holds the latest version of each document. `DT_RECEB` is the receipt date of that version, so a restated (re-filed) ITR moves to a later date, which is conservative. Getting the true first-published values needs old archive snapshots or the per-document RAD download.
3. **Financials.** Banks and insurers use a different chart (3.01 = intermediation revenue). Exclude them or treat them separately, as the BIST panel does.
4. **Prices.** COTAHIST is unadjusted. Dividend and split adjustment for total-return labels needs B3 corporate-action data (the `rb3` / `b3quant` libraries implement it) or yfinance adjusted closes as an approximation (survivors only).
5. **Inflation.** Brazil has no IAS 29. A constant-unit variant is possible with IPCA (BCB SGS series 433, free API) if needed.
6. **Access.** Ask the user whether CVM can be fetched from another network. Otherwise the archive mirror works, but it depends on snapshot recency: the newest year may lag.

Estimated effort for a full 2011-2026 Brazil panel (about 300-400 non-financial firms, delisted included): 1-2 agent sessions. Data volume is about 0.5 GB of zips, plus COTAHIST at about 30-90 MB per year.

## Sources
- CVM open data, ITR: https://dados.cvm.gov.br/dataset/cia_aberta-doc-itr ; DFP: https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp
- B3 historical quotes and layout: https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/cotacoes-historicas/ ; https://www.b3.com.br/data/files/65/50/AD/26/29C8B51095EE46B5790D8AA8/HistoricalQuotations_B3.pdf
- rb3 (COTAHIST tooling): https://docs.ropensci.org/rb3/articles/Fetching-historical-equity-data.html
- cvm-sqlite: https://pypi.org/project/cvm-sqlite
- CNV AIF regime (no bulk API found): https://www.argentina.gob.ar/preguntas-frecuentes-cnv
