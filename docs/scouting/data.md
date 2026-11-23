# Data Source Scouting — Turkish Equities (BIST)

**Date:** 2026-11-22 | **Scope:** Infrastructure upgrades & untested data sources for the monthly `value_sn` pipeline (`docs/plan_2026-10-26.md`, trial ledger `N_sel ≈ 86–87`). Ranked strictly by expected value (EV) for this project.

## Summary Matrix

| Rank | Finding | Type | Effort | Target Files / Plan Items | Failed in README? |
|---:|---|---|---|---|---|
| 1 | KAP Blocked-CI Architecture & Official KAP REST API | Infrastructure | S / L | `core/kap_api.py`, `.github/workflows/daily-screener.yml`, **P3-3** | No |
| 2 | KAP Bulk `.rar` Financials & `kap-mcp` IFRS/BDDK/Insurance Parser | Infrastructure | M | `scripts/build_first_published.py`, `core/live_data.py`, **P2-1/P2-3/P2-4/P2-5** | No |
| 3 | Borsa İstanbul DataStore (`SERMAYE_ARTIRIMI`, Delisted, VBTS) | Infrastructure | M | `core/pit_panel.py`, `scripts/fetch_delisted.py`, `core/live_data.py`, **P1-2/P2-2** | No |
| 4 | `borsapy` v0.10–v0.11 Native EVDS3 & `Eurobond.history()` | Infrastructure | S | `core/live_data.py`, `core/pit_panel.py`, `core/sovereign_spread.py`, **P0-2** | No |
| 5 | MKK VAP Daily Free-Float Custody & Investor Demographics | Infrastructure (+opt. trial) | S / M | `scripts/fetch_isyatirim_market_cap.py`, `core/live_data.py`, **P2-2/P4-1** | **Foreign share YES (avoid)**; free-float/retail NO |
| 6 | SPK II-15.1 Insider Trades (`DKB` Parser + Avci 2024 Evidence) | **New testable idea (+1 N_sel)** | M | `data/research/kap_archive.parquet` → new `scripts/fetch_insider_trades.py` | No (explicitly *Not tested* in README) |
| 7 | KAP Monthly Fund Holdings (`Portföy Dağılım Raporu`) + TEFAS v2 / Fonoloji | **New testable idea (+1 N_sel)** | M / L | `kap_archive.parquet`, `borsapy` v0.11 TEFAS JSON, `fonoloji.com/v1` | No (distinct from failed foreign share) |
| 8 | Takasbank ÖPP Securities Lending & Post-2025 BIST 50 Short-Selling | **New testable idea (+1 N_sel)** / Infra | M | `kap_archive.parquet` (`DKB`), `core/live_data.py` | No |
| 9 | BIST Analyst Consensus (`borsapy` `hedeffiyat` + `Yatırımcı.AI`) | Infra (forward log) → **+1 N_sel** later | S / L | `core/live_data.py`, `data/bist_history.db`, `decisions.jsonl` | No (seasonal-RW SUE failed; consensus untested) |
| 10 | BIST Sept 2026 Index Methodology, Rebalancing Calendar & MSCI Turkey | Infrastructure (+opt. **+1 N_sel**) | S / M | `config/fintables_ticker_sektor.json`, `core/events.py` | No |
| 11 | BilancoVeri Keyed JSON API (`bilancoveri.com/api/`) | Infrastructure | S | `core/run_health.py`, **P3-1/P3-2/P3-3** | No |
| 12 | TCMB EVDS3 New 2024–2026 Series (Sectoral Inflation, Weekly Flows) | Infrastructure (info-only) | S | `core/live_data.py::live_macro_snapshot()`, `core/hurdle.py` | **Timing YES (avoid)**; info-only NO |
| 13 | Matriks (`XML Feeder` / `DB Matriks`) & Foreks Institutional Feeds | Infrastructure (scale gate) | L | Future replacement for `core/live_data.py` if capital > 10M TL | No |

---

## Ranked Findings

### 1. Sanctioned KAP Access Outside Blocked CI + Official KAP Data Dissemination REST API
- **Link:** [KAP Veri Yayın Servisi REST API Entegrasyonu (Official PDF)](https://kap.org.tr/tr/api/about/content-file/8a019492945fbe080194b26d8bed4873) · [oguzhanozfe/kap-watcher WAF check](https://github.com/oguzhanozfe/kap-watcher) · [semudu/kap-client](https://github.com/semudu/kap-client)
- **Date:** 2024-11-27 (official KAP REST API announcement); 2026-11-17 (`kap-watcher` WAF verification)
- **Summary:** `www.kap.org.tr` sits behind a perimeter WAF (`robots.txt` returns HTTP 404/666) that drops datacenter/GitHub Actions IPs, while officially routing automated subscribers to the IP-whitelisted KAP Data Dissemination REST API (`disclosures`, `disclosureDetail`, `downloadAttachment`, `caEventStatus`) via a BIST data-distribution contract (`kapdestek@mkk.com.tr`). For non-commercial research, a single daily fetch from a residential/local machine or self-hosted GitHub Actions runner in Turkey avoids cloud-ASN blocks cleanly without WAF circumvention; `byCriteria` also expects `Referer: https://www.kap.org.tr/tr/bildirim-sorgu`.
- **Concrete use for THIS project:** Directly closes **Plan P3-3** (`kap_missing_share = 0.98` in CI) and **P0-2** (`[timing]` / `_KapBreaker` delays). Run a lightweight daily local cron (or self-hosted runner) that executes `core/kap_api.py::fetch_range` once at 18:15 Istanbul time and commits a compact `data/kap_feed/latest.parquet` (report dates + red-flag subjects), which `.github/workflows/daily-screener.yml` and `core/live_data.py::live_financial_report_published_dt()` read instead of hitting `kap.org.tr` from GitHub runners; escalate to the official MKK API key only if commercialized.
- **Type:** Infrastructure
- **Effort:** S (local cron / self-hosted runner for P3-3) · L (official BIST/MKK contract)
- **Failed-idea check:** Clear. `kap_report_dates_preregistration.md` confirmed `value_sn` is *lag-sensitive* (making real KAP dates critical infrastructure, not a failed signal); `kap_red_flags` stays information-only as already established.

---

### 2. KAP Bulk Financial Statements (`.rar`) & `kap-mcp` Direct IFRS / BDDK / Insurance Excel Parser
- **Link:** [KAP Site Guide — Bulk Financial Tables & Report Dates (Official PDF)](https://www.kap.org.tr/tr/api/about/content-file/402832a195b3017d0195bd17e2e07e9a) · [kap-mcp v0.1.0 (PyPI)](https://pypi.org/project/kap-mcp/) · [atayalcinb/KAP-MCP-TR (GitHub)](https://github.com/atayalcinb/KAP-MCP-TR) · [KAP XBRL Guide](https://goruntuleyici.com/rehber/kap-xbrl-finansal-tablo-okuma)
- **Date:** 2026-04-25 (`kap-mcp` v0.1.0 release); 2026-09-17 (KGK TFRS XBRL guide)
- **Summary:** KAP's *Finansal Tablolar* tab supports bulk `.rar` downloads of every company's financial statements for a chosen year and period (plus the official *Finansal Rapor Tarihleri* Excel of filing deadlines and publication dates), avoiding per-ticker scraping. `kap-mcp` (MIT, Python 3.12, `httpx`/`openpyxl`/`lxml`) parses KAP Excel filings directly into flat TL dicts with 100% coverage across 572 IFRS, 27 BDDK (banks/leasing/factoring), and 6 Insurance templates—eliminating İş Yatırım's IAS 29 re-expression bug and BDDK template gaps.
- **Concrete use for THIS project:** Accelerates **Plan P2-1** (33 `unknown` IAS 29 firms), **P2-3** (first-published validation), and **P2-4** (20,000 pre-2023 KAP pages currently taking days at 3.6 s/page in `scripts/build_first_published.py`) by parsing bulk quarterly archives directly from KAP Excel/XBRL. Also provides a clean reference parser for **Plan P2-5** (rebuilding `financials_factors_monthly.parquet`) and removes `core/live_data.py`'s İş Yatırım BDDK limitation.
- **Type:** Infrastructure
- **Effort:** M
- **Failed-idea check:** Clear. Pure point-in-time data integrity upgrade addressing `vendor_vs_kap_audit.md` and `first_published_panel.md`; financials shadow sleeve (`F1_bm_roe_sn`) showed strong holdout IC (+0.107, t 5.62) and is tracked as a shadow model.

---

### 3. Borsa İstanbul DataStore — Official Corporate Actions (`SERMAYE_ARTIRIMI`), Delisted Registry & VBTS
- **Link:** [BIST DataStore Format Spec (PDF)](https://datastore.borsaistanbul.com/assets/files/DataStore_Data_Reporting_and_Acceptance_Formats.pdf) · [BIST File Sharing Guidelines — Sec. 2.4 Corporate Actions (PDF)](https://www.borsaistanbul.com/files/file-sharing-guidelines1AB68DFE8245.pdf) · [BIST Market Data Products](https://borsaistanbul.com/en/sayfa/2727/market-data-products)
- **Date:** Active 2024–2026 catalog (updated BISTECH format specs)
- **Summary:** Borsa İstanbul's official DataStore (`datastore.borsaistanbul.com`) distributes exchange-grade EOD files: `SERMAYE_ARTIRIMI_[YYYYMMDD].csv` (effective date, prior capital, rights/bonus amounts, rights issue price, cash dividends), `NakitSerTem.[YYYY].zip`, the permanent delisted equity list (*Kottan Sürekli Olarak Çıkarılan Pay Senetleri*), and daily equity bulletins containing VBTS/tedbir flags and unadjusted prices. Unlike `borsapy`/TradingView, DataStore separates unadjusted prices from corporate-action adjustments cleanly.
- **Concrete use for THIS project:** Directly resolves **Plan P2-2** (9 tickers missing HisseTekil history: `CITAS`, `DAGHL`, `INTEK`, `LRSHO`, `LYDHO`, `MARKA`, `METUR`, `PEHOL`, `SELGD`), expands delisted survivorship testing well beyond 39 exits (**Plan P1-2**, `scripts/fetch_delisted.py`), hardens `core/pit_panel.py::shares_at()` against registration-lag errors (`share_count_fix.md`), and fills the missing free-source gap for `core/live_data.py::live_tedbir_level()` (README Known Limitations). *Cost caveat:* historical DataStore packages are paid (academic pricing available).
- **Type:** Infrastructure
- **Effort:** M (budget/licensing + CSV loader)
- **Failed-idea check:** Clear. Data correctness and survivorship infrastructure (`survivorship_delisted_preregistration.md` showed the panel is sensitive to delisted stocks; `market_cap_source.md` showed rights-adjusted closes created look-ahead bias).

---

### 4. `borsapy` v0.10.0–v0.11.0 Native TCMB EVDS3 Wrapper & Cached `Eurobond.history()`
- **Link:** [borsapy v0.10.0 EVDS3 Release](https://github.com/saidsurucu/borsapy/releases/tag/v0.10.0) · [borsapy v0.8.7 Eurobond History Release](https://github.com/saidsurucu/borsapy/releases/tag/v0.8.7) · [TCMB EVDS3 Portal](https://evds3.tcmb.gov.tr/)
- **Date:** 2026-04-17 (`v0.8.7`); 2026-05-04 (`v0.10.0`); 2026-08-07 (`v0.11.0`)
- **Summary:** TCMB retired the legacy `evds2.tcmb.gov.tr` REST API at end-2025 (breaking older `evds` PyPI clients) and migrated to `evds3.tcmb.gov.tr` (`/igmevdsms-dis/`, HTTP `key` header auth). `borsapy>=0.11.0`—already pinned in `requirements.txt`—natively wraps EVDS3 (145+ categories via `bp.evds_series()`) and adds cached daily Ziraat-sourced `Eurobond.history()`, yet this repo currently calls `bp.evds_series()` only inside `scripts/research_industrial_production.py`.
- **Concrete use for THIS project:** Replace fragile scrapers in `core/live_data.py::live_macro_snapshot()` (`policy_rate()` occasionally returning bogus `7.0` and `doviz.com` HTML bond parsing) and `_cpi_index_cached()` (critical for IAS 29 C1 unit conversion in `core/pit_panel.py`) with official EVDS3 series using a free `EVDS_API_KEY` CI secret; harden `core/sovereign_spread.py` (**Plan P0-2** `[sovereign_spread]`) with `Eurobond.history()`.
- **Type:** Infrastructure
- **Effort:** S
- **Failed-idea check:** Clear. Strictly replaces flaky live data pipes for CPI, policy rate, and the **one passing confirmatory study** (`sovereign_spread_preregistration.md`, contemporaneous risk gauge).

---

### 5. MKK Veri Analiz Platformu (VAP) Daily Free-Float Custody & Investor Counts + MKK API Portal
- **Link:** [MKK VAP Free Float in Shares Data](https://www.vap.org.tr/en/free-float-shares-data) · [MKK VAP English Launch Announcement](https://www.mkk.com.tr/en/news/data-analysis-platform-vap-opens-turkiyes-capital-markets-data-to-the-world-with-english-language-option) · [MKK API Portal Launch](https://www.mkk.com.tr/haberler/mkk-api-portal-yayinda)
- **Date:** 2025-01-13 (MKK API Portal); 2026-06-22 (VAP English portal); live daily through 2026-11
- **Summary:** MKK's Data Analysis Platform (`vap.org.tr/en`) publishes daily official per-stock free-float ratios from custody balances (SPK 5/157 methodology, previous-day settlement), index-level investor counts/portfolio values, and domestic/foreign custody splits (10-business-day lag), with bulk research extracts available via `vaptalep@mkk.com.tr`. MKK also launched an API Portal in Jan 2025 for structured developer integration.
- **Concrete use for THIS project:** Cross-validates İş Yatırım's `HAO_PD` and fills missing free-float history for the 9 HisseTekil gap stocks (**Plan P2-2**) directly ahead of **Plan P4-1** (pre-registered free-float filter for manipulation risk). Also provides official investor-count / retail-vs-institutional demographics currently left `None` in `core/live_data.py::live_ownership()`.
- **Type:** Infrastructure (for P4-1 & P2-2) · Optional **New testable idea (+1 N_sel, needs pre-registration)** only if domestic retail-count / ownership concentration is tested as a signal
- **Effort:** S (manual/academic bulk request via `vaptalep@mkk.com.tr`) · M (API Portal)
- **Failed-idea check:** **WARNING — Partial overlap with README failure:** per-stock foreign ownership change (`dfor3`) and level (`for_t`) **ALREADY FAILED** (`foreign_ownership_preregistration.md`, sign flips across periods). Do NOT re-test MKK foreign share; restrict MKK VAP strictly to official free-float validation (**P4-1**) and untested domestic investor-count diagnostics.

---

### 6. SPK II-15.1 Insider Transactions (`Pay Alım Satım Bildirimi`, `DKB`) — Open Parser + 2024 EJF Evidence
- **Link:** [caganco/trailingedge (GitHub)](https://github.com/caganco/trailingedge) · [KAP Insider Endpoint Reconnaissance Notes](https://github.com/caganco/bist-flow-intel/blob/master/docs/KAP_ENDPOINT_NOTES.md) · [Avci (2024), *European Journal of Finance*](https://ideas.repec.org/a/taf/eurjfi/v30y2024i6p549-574.html)
- **Date:** 2024 (Avci, *EJF* 30(6):549–574); 2026-05-28 (`KAP_ENDPOINT_NOTES.md` & `trailingedge`)
- **Summary:** Solves the exact blocker cited in README ("direction is not in KAP summaries"): `trailingedge` documents that KAP "Pay Alım Satım Bildirimi" filings split into `DKB` (SPK II-15.1 individual insider PDF tables inside a Java-serialized `byte[]` wrapper) vs. `ODA` (fund threshold crossings), enabling full extraction of buy/sell direction, share volume, and price. Avci (2024) analyzed ~65,000 BIST insider trades (2008–2019), documenting +6.58% 1-year abnormal profits and replicable outperformance when mimicking officers/directors (caveat: smaller earlier Turkish studies such as Ünal 2022 found weaker post-disclosure CARs).
- **Concrete use for THIS project:** Filter existing `data/research/kap_archive.parquet` for `subject == "Pay Alım Satım Bildirimi"` & `disclosureClass == "DKB"`, write a `scripts/fetch_insider_trades.py` parser modeled on `trailingedge`, and pre-register a test of trailing 3m/6m net insider buying (standalone or as a tie-breaker/filter on `value_sn`).
- **Type:** **New testable idea (+1 N_sel, needs pre-registration)**
- **Effort:** M
- **Failed-idea check:** Clear. Explicitly listed under README *"Not tested, and why: Insider trades"* (line 522); completely distinct from `kap_disclosure_signals_preregistration.md` (which tested late filings, Friday-evening releases, and corporate buybacks).

---

### 7. KAP Monthly Mutual Fund Holdings (`Portföy Dağılım Raporu`) + TEFAS v2 JSON API (`borsapy` v0.11 / Fonoloji)
- **Link:** [borsapy v0.11.0 Browserless TEFAS JSON Release](https://github.com/saidsurucu/borsapy/releases/tag/v0.11.0) · [Fonoloji REST API Docs](https://fonoloji.com/api-docs) · [Mutual Fund Herding in Industries: The Turkish Case (2024)](https://openalex.org/works/W4394600211)
- **Date:** 2024 (Turkish mutual fund herding paper); 2026-08-07 (`borsapy` v0.11.0); 2026-10-19 (SPK II-14.2 guide)
- **Summary:** Under SPK Communiqué II-14.2, every Turkish mutual fund discloses itemized stock holdings (ticker, share count, weight) monthly on KAP within 6 business days of month-end (weekly for *serbest fonlar*), while TEFAS's April 2026 Next.js migration still exposes browserless JSON asset-class histories via `/api/funds/dagilimSiraliGetirT` (`borsapy` v0.11.0). `Fonoloji` (`https://fonoloji.com/v1`, free tier 15,000 req/mo, `X-API-Key`) serves parsed KAP fund holdings (ticker + weight) alongside TEFAS metrics with <50 ms latency.
- **Concrete use for THIS project:** Construct a stock-level **domestic institutional fund flow & crowding** panel (month-over-month share-count delta summed across Turkish equity funds) either historically from `kap_archive.parquet` (`Portföy Dağılım Raporu`) or forward via `fonoloji.com/v1`, to test whether domestic mutual-fund accumulation (or avoiding fund-crowded stocks) adds orthogonal alpha to `value_sn`.
- **Type:** **New testable idea (+1 N_sel, needs pre-registration)**
- **Effort:** M (forward via Fonoloji + `borsapy` v0.11) · L (historical KAP attachment backfill)
- **Failed-idea check:** Clear. Distinct from `foreign_ownership_preregistration.md` (which tested foreign MKK custody share `dfor3`); domestic equity mutual funds (~5.9M investors per MKK VAP Nov 2026) have never been tested in this repo.

---

### 8. Takasbank Securities Lending Market (*Ödünç Pay Piyasası*) Daily Bulletins & BIST 50 Short-Selling
- **Link:** [Takasbank ÖPP Daily Bulletin](https://www.takasbank.com.tr/en/statistics/securities-lending-market/securities-lending-market-daily-bulletin) · [Takasbank ÖPP Annual Statistics](https://www.takasbank.com.tr/en/statistics/securities-lending-market/securities-lending-market-statistics-by-years) · [Borak (2026), *Maliye ve Finans Yazıları*](https://dergipark.org.tr/tr/download/article-file/6063244)
- **Date:** 2025-01-02 (BIST 50 short-selling ban lifted); 2026-08-22 (Borak accepted); live 2026 Takasbank stats
- **Summary:** Following SPK's partial lifting of the 2023 short-selling ban for BIST 50 (effective Jan 2, 2025, with brief temporary suspensions in Spring 2025/2026), Takasbank ÖPP volume surged from 224.6B TL ($5.7B, 54 stocks) in 2025 to 413.1B TL ($9.0B, 60 stocks) YTD in 2026. Per-ticker daily open lending positions (shares, TL value, rates, maturities) are published free daily via Takasbank and KAP `DKB` bulletins (*Takasbank Ödünç Pay Piyasası Günlük Bülten*).
- **Concrete use for THIS project:** Parse Takasbank's daily `DKB` PDFs from `kap_archive.parquet` (pre-2023 and 2025+ non-ban windows) to compute `lent_shares / free_float_shares` as either an info-only short-pressure field in `core/live_data.py` (currently `None` per line 18) or a pre-registered value-trap exclusion filter on large-cap holdings. *Scope caveat:* only ~50–60 liquid large caps trade on ÖPP, limiting overlap with small-cap `value_sn` picks.
- **Type:** Infrastructure (info-only lending/ban field) · **New testable idea (+1 N_sel, needs pre-registration)** if tested as a filter
- **Effort:** M
- **Failed-idea check:** Clear. Short-selling and securities-lending utilization have never been tested in the README scorecard.

---

### 9. BIST Analyst Consensus Target Prices & Ratings (`borsapy` `hedeffiyat.com.tr` + `Yatırımcı.AI`)
- **Link:** [borsapy Analyst Data Docs](https://github.com/saidsurucu/borsapy/blob/master/README.md) · [Yatırımcı.AI BIST Consensus Targets](https://yatirimci.ai/en/analyst-price-targets) · [Tiniç, Tanyeri & Bodur (2021), Bilkent/Elsevier](https://repository.bilkent.edu.tr/server/api/core/bitstreams/fdc8cf2b-e048-4f8d-9847-930c4988b0a8/content)
- **Date:** 2026-08-07 (`borsapy` v0.11.0); live 2026 (`yatirimci.ai`: 98 BIST stocks, 1,067 ratings)
- **Summary:** `borsapy` already ships `Ticker.analyst_price_targets`, `recommendations_summary`, and `recommendations` (sourced from `hedeffiyat.com.tr`), and free aggregators like `yatirimci.ai` compile ~1,000+ broker ratings across ~98 liquid BIST stocks—yet `core/live_data.py` never pulls consensus data. Point-in-time historical analyst EPS/target revisions are not freely available (requiring LSEG I/B/E/S, Bloomberg, or daily forward capture).
- **Concrete use for THIS project:** Immediately log daily `analyst_price_targets` and `recommendations_summary` snapshots via `core/live_data.py` into `data/bist_history.db` (zero extra dependencies) as an information-only cross-check in the newsletter and to build a clean, look-ahead-free panel for a future pre-registered consensus-revision test.
- **Type:** Infrastructure (forward snapshot logging now) · **New testable idea (+1 N_sel, needs pre-registration)** once history accumulates or I/B/E/S is licensed
- **Effort:** S (forward logging) · L (commercial historical consensus backfill)
- **Failed-idea check:** Clear. Seasonal random-walk `SUE` failed (`long_term_preregistration.md`) and internal model targets failed (`backtest_target_accuracy.py`), but **external broker consensus EPS surprises and target revisions** have never been tested.

---

### 10. BIST Quarterly Index Rebalancing Rules (Updated Sept 2026) & MSCI Turkey Reconstitution Calendar
- **Link:** [BIST Market Cap Weighted Stock Indices Methodology (Sept 2026 PDF)](https://borsaistanbul.com/files/bist-mcw-equity-indices-m-eng-202609-clean.pdf) · [BIST Rule Changes Announcement (Aug 2025 PDF)](https://www.borsaistanbul.com/files/duyuru-38729-EN.pdf) · [Çıtak (2026), Participation Index Exclusions (DergiPark)](https://dergipark.org.tr/en/pub/jie/article/1867161) · [Avcı et al. (2023), MSCI Turkey Reconstitution](https://dergipark.org.tr/tr/pub/jyasar/article/1151230)
- **Date:** 2025-08-25 (12-month lookback rule change); 2026-07-15 (Çıtak 2024–2026 study); 2026-09 (clean methodology)
- **Summary:** Borsa İstanbul extended BIST 30/50/100/500 review lookbacks from 6 to 12 months in late 2025 (curbing ~10% quarterly churn) and standardized quarterly review cutoffs on the last business day of Nov/Feb/May/Aug, announced on KAP ~10 days prior to Jan 1 / Apr 1 / Jul 1 / Oct 1 effective dates. Recent event studies document short-window price pressure around BIST Participation Index (2024–2026) and MSCI Turkey Small Cap reconstitutions—events that coincide directly with R0's first-of-month rebalance dates.
- **Concrete use for THIS project:** Parse official BIST index & sector constituent announcements from KAP into `core/events.py` to replace the static, manually maintained `config/fintables_ticker_sektor.json` and flag quarterly index-rebalance execution risk on Jan/Apr/Jul/Oct `decisions.jsonl` fills; optionally pre-register a test of forced index-exclusion mean reversion.
- **Type:** Infrastructure (dynamic sector map & calendar) · Optional **New testable idea (+1 N_sel, needs pre-registration)** for exclusion/inclusion alpha
- **Effort:** S (KAP calendar & constituent parser) · M (historical constituent backfill)
- **Failed-idea check:** Clear. Index reconstitution and Participation/MSCI exclusion effects have never been tested (`event_study_preregistration.md` tested elections/shocks; `ramadan_holiday_preregistration.md` tested religious/holiday calendars).

---

### 11. BilancoVeri Keyed JSON API (`bilancoveri.com/api/`) — Low-Cost CI-Safe KAP Backup
- **Link:** [BilancoVeri API Documentation & Pricing](https://bilancoveri.com/api/)
- **Date:** Verified 2026-11 (active commercial v1 API)
- **Summary:** Turkish keyed JSON API (`X-API-Key`) serving KAP financial statements (`/api/v1/hisse/{kod}.json`), market caps/multiples (`/api/v1/sirketler.json`), sector medians, and the last 90 days of KAP financial-report filing timestamps (`/api/v1/takvim.json`) for ₺249/month personal/academic (1,000 req/day, 7-day free trial). Unlike `kap.org.tr`, it is built for server-side CI requests without datacenter IP blocking.
- **Concrete use for THIS project:** Pragmatic low-cost fallback for **Plan P3-3** (live KAP report timestamps via `/api/v1/takvim.json` when no local runner is online), **Plan P3-1** (`core/run_health.py` vendor-consistency cross-check vs İş Yatırım), and **Plan P3-2** (market-cap cross-check). *Audit requirement:* verify whether historical quarters are first-published or IAS 29 re-expressed before ever feeding it into research panels.
- **Type:** Infrastructure
- **Effort:** S
- **Failed-idea check:** Clear. Redundancy and monitoring infrastructure only.

---

### 12. TCMB EVDS3 New 2024–2026 Series (`Sektörel Enflasyon Beklentileri`, `Sektör Bilançoları`, Weekly Foreign Flows)
- **Link:** [TCMB Sectoral Inflation Expectations Metadata (PDF)](https://www.tcmb.gov.tr/wps/wcm/connect/00323178-4c8e-44b5-9733-dab9dac15a1e/SEB-Metaveri.pdf?MOD=AJPERES) · [TCMB Oct 2026 SEB Report (PDF)](https://www.tcmb.gov.tr/wps/wcm/connect/6325af8e-24a6-446d-abc8-49bb8e9f3b6b/SEB-Rapor.pdf?MOD=AJPERES) · [EVDS3 Portal](https://evds3.tcmb.gov.tr/)
- **Date:** 2024 launch; updated monthly through 2026-10 / 2026-11
- **Summary:** TCMB's EVDS3 publishes *Sektörel Enflasyon Beklentileri* (unifying 12-month CPI expectations from Market Participants PKA, Real Sector İYA, and Households HBA), weekly *Menkul Kıymet İstatistikleri* (aggregate non-resident equity/GDDS net flows), and *Sektör Bilançoları* (2009–2024). All are programmatically accessible with a free EVDS3 API key via `borsapy.evds_series()`.
- **Concrete use for THIS project:** Populate the forward-looking TCMB survey CPI and USD/TRY expectation fields currently explicitly left `None` in `core/live_data.py` (lines 16–18) for `core/hurdle.py` / `core/regime.py` diagnostics and real-return context in reports—strictly as **information only**.
- **Type:** Infrastructure (information-only reporting)
- **Effort:** S
- **Failed-idea check:** **WARNING:** `macro_drivers_preregistration.md` and `industrial_production_preregistration.md` ALREADY FAILED to predict next-month BIST direction. Do NOT spend `+1 N_sel` testing EVDS3 macro series as market-timing overlays.

---

### 13. Matriks (`XML Feeder` / `DB Matriks`) & Foreks / ForInvest Commercial Institutional Feeds (Scale Gate)
- **Link:** [Matriks XML Feeder](https://www.matriksdata.com/website/urunlerimiz/kurumsal-hizmet-ve-servisler/veri-ve-icerik-saglayici-servisler/xml-feeder) · [DB Matriks](https://www.matriksdata.com/website/urunlerimiz/kurumsal-hizmet-ve-servisler/veri-ve-icerik-saglayici-servisler/db-matriks) · [pykapfinance v0.1.1 (PyPI)](https://pypi.org/project/pykapfinance/)
- **Date:** Active 2025–2026 institutional offerings; 2026-01-22 (`pykapfinance` v0.1.1)
- **Summary:** Matriks (`XML Feeder`, `DB Matriks`) and Foreks/ForInvest are the primary local institutional feeds combining licensed BIST EOD/real-time prices, corporate actions, VBTS status, KAP feeds, and multi-broker consensus estimates under a single SLA. However, Borsa İstanbul data-licensing and terminal fees make them uneconomical relative to a 1M TL monthly-rebalance research book.
- **Concrete use for THIS project:** Keep as a documented **scale-up trigger** rather than an immediate build: only migrate `core/live_data.py` to Matriks/Foreks (or official MKK VYK API via `pykapfinance`) if live forward-record results (`data/forward_record/decisions.jsonl`, **Plan P0-3**) confirm positive net alpha and deployed capital crosses the 10M TL liquidity/cost threshold (`quant_review_followups_preregistration.md`).
- **Type:** Infrastructure
- **Effort:** L (commercial contract + integration)
- **Failed-idea check:** Clear. Cost-discipline gate preventing premature vendor spend while DSR remains non-significant (`N_sel ≈ 86–87`).
