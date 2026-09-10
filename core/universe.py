"""universe: taranabilir BIST evrenini olusturur ve universe_filters'i uygular.

Spec: universe_filters (min_volume_tl_default, min_listing_days,
min_reported_quarters, max_tedbir_level), sector_taxonomy.
P10_ipo_wave: 90 gunden yeni sirketler elenir.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core import db
from bist_mcp import server as bist_mcp

MIN_VOLUME_TL_DEFAULT = 10_000_000
MIN_LISTING_DAYS = 90
MIN_REPORTED_QUARTERS = 2
MAX_TEDBIR_LEVEL = 1


def build_universe(as_of_date: str, min_volume_tl: float = MIN_VOLUME_TL_DEFAULT) -> list[dict]:
    seed = bist_mcp.get_universe()
    rows: list[dict] = []
    ingested_at = datetime.now(timezone.utc).isoformat()

    for entry in seed:
        ticker = entry["ticker"]
        size = bist_mcp.get_listing_and_size(ticker, as_of_date)
        tedbir = bist_mcp.get_tedbir_level(ticker, as_of_date)["tedbir_level"]
        listing_days = size["listing_days"]
        reported_quarters = max(0, listing_days // 90)

        exclusion_reason = None
        if listing_days < MIN_LISTING_DAYS:
            exclusion_reason = "min_listing_days"
        elif reported_quarters < MIN_REPORTED_QUARTERS:
            exclusion_reason = "min_reported_quarters"
        elif tedbir > MAX_TEDBIR_LEVEL:
            exclusion_reason = "max_tedbir_level"
        elif size["avg_volume_tl_20d"] is None:
            # canli modda fiyat gecmisi cekilemediyse (agsal hata, yeni/askida
            # sembol vb.) hacim dogrulanamaz -> guvenlik icin elenir.
            exclusion_reason = "min_volume_tl"
        elif size["avg_volume_tl_20d"] < min_volume_tl:
            exclusion_reason = "min_volume_tl"

        supersector_map = {"XBANK": "XUMAL", "XFINK": "XUMAL", "XSGRT": "XUMAL", "XHOLD": "XUMAL",
                            "XYORT": "XUMAL", "XGMYO": "XUMAL", "XILTM": "XUTEK", "XBLSM": "XUTEK"}
        supersector = supersector_map.get(entry["sector"], "XUSIN" if entry["ratio_profile"] == "industrial" else "XUHIZ")

        row = {
            "as_of_date": as_of_date, "ticker": ticker, "name": entry["name"],
            "sector": entry["sector"], "supersector": supersector,
            "ratio_profile": entry["ratio_profile"], "regulator": entry["regulator"],
            "market_cap": size["market_cap"], "avg_volume_tl_20d": size["avg_volume_tl_20d"],
            "tedbir_level": tedbir, "tedbir_end_date": None, "listing_days": listing_days,
            "exclusion_reason": exclusion_reason, "ingested_at": ingested_at,
        }
        rows.append(row)

    conn = db.get_connection()
    try:
        conn.executemany(
            """INSERT INTO universe_snapshot
               (as_of_date, ticker, name, sector, supersector, ratio_profile, regulator,
                market_cap, avg_volume_tl_20d, tedbir_level, tedbir_end_date, listing_days,
                exclusion_reason, ingested_at)
               VALUES (:as_of_date, :ticker, :name, :sector, :supersector, :ratio_profile, :regulator,
                       :market_cap, :avg_volume_tl_20d, :tedbir_level, :tedbir_end_date, :listing_days,
                       :exclusion_reason, :ingested_at)
               ON CONFLICT(as_of_date, ticker) DO UPDATE SET
                 exclusion_reason=excluded.exclusion_reason,
                 market_cap=excluded.market_cap,
                 avg_volume_tl_20d=excluded.avg_volume_tl_20d,
                 tedbir_level=excluded.tedbir_level,
                 listing_days=excluded.listing_days""",
            rows,
        )
        conn.commit()
    finally:
        conn.close()

    return rows


def eligible_tickers(as_of_date: str) -> list[dict]:
    rows = db.query(
        "SELECT * FROM universe_snapshot WHERE as_of_date=? AND exclusion_reason IS NULL",
        (as_of_date,),
    )
    return [dict(r) for r in rows]
