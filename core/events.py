"""event_calendar_engine: onceden bilinen, tahmin gerektirmeyen takvim olaylari.

rule: Hicbir tarih tahmin edilmez. Yalnizca resmi kaynaktan (Borsa Istanbul
takvimi, KAP ilani, izahname) dogrudan cekilen tarihler gosterilir.
output_field: upcoming_events, skora girmez.
"""
from __future__ import annotations

from core import db
from kap_web_mcp import server as kap_web_mcp


def fetch_upcoming_events(as_of_date: str, tickers: list[str]) -> dict[str, list[dict]]:
    events = kap_web_mcp.get_upcoming_events(tickers, as_of_date)

    if events:
        conn = db.get_connection()
        try:
            conn.executemany(
                """INSERT INTO upcoming_events (ticker, event_type, event_date, source, coverage_note)
                   VALUES (:ticker, :event_type, :event_date, :source, :coverage_note)""",
                events,
            )
            conn.commit()
        finally:
            conn.close()

    by_ticker: dict[str, list[dict]] = {t: [] for t in tickers}
    for e in events:
        by_ticker.setdefault(e["ticker"], []).append(e)
    return by_ticker
