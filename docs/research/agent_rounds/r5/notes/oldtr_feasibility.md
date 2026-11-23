# Old Turkey (2001-2012) point-in-time panel: feasibility

**Verdict: PARTIAL.** With the free sources already used in the repo, you can build a full panel for **2008Q1-2012**: prices, shares, market cap and all six value inputs. That is about 4.5 fresh years that the current 2013+ panel never covers. You **cannot** build one for **2001-2007**. Prices and share capital exist for those years, but no free endpoint returns financial statements before 2008, so the 2001-04 high-inflation era and the 2005 IFRS switch are out of reach unless someone buys or hand-parses the data.

## Probe (2026-11-24, Is Yatirim, 2 s between requests)
| ticker | price start (HisseTekil) | first statement (MaliTablo) | statement items/quarter | KAP dates |
|---|---|---|---|---|
| THYAO | 1996-12-26 | 2008Q1 | ~65-72 | from 2009-12-31 |
| EREGL | 1996-12-26 | 2008Q1 | ~73-77 | same |
| ARCLK | 1996-12-26 | 2008Q1 | ~71-102 | same |
| AKBNK (UFRS) | 1996-12-26 | 2008Q1 | ~95-118 | same |
| ASYAB (bank, delisted 2015) | 2006-05-12 | 2008Q1 | ~82-95 | same |
| DISBA (delisted 2006), FINBN (delisted ~2010) | **no rows** | none | - | - |

For every ticker, MaliTablo returns the item list but with all values empty for 1998-2007. I also tried other financialGroup codes for 2002-2007 (XI_29K, UFRS_K, SPK, TMS, ...); all came back empty.
Each HisseTekil row has: close (raw HG_* and adjusted HGDG_*), volume, `SERMAYE` (paid-in capital = share count at 1 TL nominal), `PD` (market cap), `PD_USD`, USD price and XU100 level.

## Coverage by year (free sources)
| years | daily prices / mcap / shares | statements (equity, NI, revenue, EBIT, debt, cash) | announcement dates | sectors |
|---|---|---|---|---|
| 1997-2000 | yes (survivors) | no | no | current map only |
| 2001-2004 (inflation) | yes (survivors) | **no** | no | current map only |
| 2005-2007 (IFRS/IAS29 exit) | yes (survivors) | **no** | no | current map only |
| 2008-2009 | yes | yes (quarterly YTD, from 2008Q1) | 75-day lag rule only (KAP API starts 2009-12-31) | current map |
| 2010-2012 | yes | yes | KAP actual dates (repo kap_archive starts 2010-01-04) | current map |

Panel usable from about mid-2008, once 2008Q1 statements clear the 75-day lag and TTM can be built: TTM needs 4 quarters, so full TTM starts with 2008Q4 (~Mar 2009). Before that, annualise YTD or use only B/M.

## Survivorship risks
- HisseTekil has no rows for companies that delisted before about 2010 (DISBA, FINBN). Delisted names in 2008-2012 have to be found from the KAP archive or the repo's delisted_candidates.txt. Before 2010, no free delisting list was found. Expect a survivor bias that is **worse than in the 2013+ panel**.
- Sectors exist only in today's map, so sectors are missing for exited names.
- 2008-2012 statements use the current Is Yatirim template, which re-maps the pre-2013 SPK formats. Check item consistency (e.g. 2012 ARCLK jumps to 97-102 items) before building the value legs.
- The 2008 crisis falls inside the sample, so the period is short and has a single regime. Its power is low: roughly 4 years, t ~1 expected at the current effect size.

## Possible routes for 2001-2007 (not verified)
- Borsa Istanbul "Financial Statements Archive (2009 and before)": https://www.borsaistanbul.com/en/sayfa/2795/financial-statements-archive. The host refused connections during the probe (socket hang up), so I could not read it. Even if it is reachable, it most likely holds per-company PDF/XLS filings, which would need large-scale parsing.
- Borsa Istanbul DataStore (https://datastore.borsaistanbul.com, a paid, JS-rendered site): pricing for historical financial data is unknown.
- Commercial/academic sources: Finnet, Matriks, Refinitiv Worldscope/Datastream, Compustat Global. All need a licence (university access).

## Endpoints
- Prices: `GET https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseTekil?hisse=THYAO&startdate=01-01-1996&enddate=31-12-2012`
- Statements: `GET .../Data.aspx/MaliTablo?companyCode=THYAO&exchange=TRY&financialGroup=XI_29|UFRS&year1..4=Y&period1..4=3,6,9,12`. A call takes at most 4 periods; values are YTD.
- KAP dates: `POST https://www.kap.org.tr/tr/api/disclosure/members/byCriteria` (core/kap_api.py). It returns 0 rows before 2009-12-20.

## Code
`scripts/fetch_old_tr.py` (prices from 1996, statements from 2008, polite 2 s pacing) and `tests/test_fetch_old_tr.py` (3 tests, offline). Estimated full run: ~300 tickers × (1 + 5 years) calls × 2 s ≈ 1 h. Not run yet, as the brief requires for anything over 30 min. Raw probe output: `/home/eren/bist_wt/r5-oldtr/scratch/probe.json`.
