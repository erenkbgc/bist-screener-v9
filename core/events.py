"""core/events.py: Kurumsal Aksiyon Takvimi ve Olay Yonetimi Modulu.

v13 Roadmap P1-8:
1. event_calendar tablosu: tarih, tur, aciklama, beklenen etki, oran/tutar.
2. Otomatik kurumsal aksiyon ve fiyat duzeltme baglantisi.
3. Entry / Exit sinyallerinde yakin takvim uyarisi (check_signal_corporate_action_warnings).
4. KAP ve borsapy veri baglantilari.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from core import db
from kap_web_mcp import server as kap_web_mcp

logger = logging.getLogger(__name__)


# =====================================================================
# 1. EVENT CALENDAR DB OPERASYONLARI
# =====================================================================

def save_calendar_events(events: list[dict]) -> None:
    """Olaylari event_calendar tablosuna kaydeder."""
    if not events:
        return
    conn = db.get_connection()
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        conn.executemany(
            """INSERT INTO event_calendar
               (ticker, event_date, event_type, description, expected_impact, ratio_or_amount, source, created_at)
               VALUES (:ticker, :event_date, :event_type, :description, :expected_impact, :ratio_or_amount, :source, :created_at)
               ON CONFLICT(ticker, event_date, event_type) DO UPDATE SET
                 description=excluded.description,
                 expected_impact=excluded.expected_impact,
                 ratio_or_amount=excluded.ratio_or_amount,
                 source=excluded.source,
                 created_at=excluded.created_at""",
            [{**e, "created_at": e.get("created_at") or now_iso} for e in events],
        )
        conn.commit()
    finally:
        conn.close()


def get_calendar_events(
    ticker: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Takvimdeki olaylari sorgular."""
    sql = "SELECT * FROM event_calendar WHERE 1=1"
    params: list[Any] = []

    if ticker:
        sql += " AND ticker = ?"
        params.append(ticker.upper())
    if start_date:
        sql += " AND event_date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND event_date <= ?"
        params.append(end_date)

    sql += " ORDER BY event_date ASC"
    rows = db.query(sql, tuple(params))
    return [dict(r) for r in rows]


# =====================================================================
# 2. KURUMSAL AKSIYONLARDAN TAKVIM OLUSTURMA
# =====================================================================

def populate_calendar_from_corporate_actions(ticker: str, actions: list[dict]) -> list[dict]:
    """Kurumsal aksiyonlari (temettu, bedelsiz, bedelli) standart takvim olaylarina donusturur ve kaydeder."""
    events = []
    ticker = ticker.upper()

    for a in actions:
        a_type = a.get("action_type")
        a_date = a.get("action_date")
        amount = float(a.get("ratio_or_amount", 0.0) or 0.0)
        split_factor = float(a.get("split_factor", 1.0) or 1.0)
        div_amount = float(a.get("dividend_amount", 0.0) or 0.0)

        if a_type == "dividend":
            desc = f"Nakit Temettü: Pay başına net/brüt {div_amount:.4f} TL"
            impact = f"Fiyat açılışta {div_amount:.2f} TL düşer; brüt getiri endeksi süreklidir."
            events.append({
                "ticker": ticker,
                "event_date": a_date,
                "event_type": "dividend",
                "description": desc,
                "expected_impact": impact,
                "ratio_or_amount": div_amount,
                "source": a.get("source", "corporate_actions"),
            })
        elif a_type == "bonus_issue":
            desc = f"Bedelsiz Sermaye Artırımı: %{amount:.1f}"
            impact = f"Fiyat {split_factor:.2f} katına bölünür; yatırımcının pay sayısı aynı oranda artar."
            events.append({
                "ticker": ticker,
                "event_date": a_date,
                "event_type": "bonus_issue",
                "description": desc,
                "expected_impact": impact,
                "ratio_or_amount": amount,
                "source": a.get("source", "corporate_actions"),
            })
        elif a_type == "rights_issue":
            desc = f"Bedelli Sermaye Artırımı: %{amount:.1f}"
            impact = f"Rüçhan hakkı kullanımı ve sermaye artırımı; yeni pay alma hakkı fiyattan ayrışır."
            events.append({
                "ticker": ticker,
                "event_date": a_date,
                "event_type": "rights_issue",
                "description": desc,
                "expected_impact": impact,
                "ratio_or_amount": amount,
                "source": a.get("source", "corporate_actions"),
            })

    if events:
        save_calendar_events(events)

    return events


# =====================================================================
# 3. ENTRY / EXIT SINYAL UYARILARI (SIGNALS WARNING CHECK)
# =====================================================================

def check_signal_corporate_action_warnings(
    ticker: str,
    as_of_date: str,
    horizon_days: int = 20,
) -> list[dict]:
    """Yatirim sinyalinin vadesi icinde (orn. onumuzdeki 20 gun) kurumsal aksiyon var mi kontrol eder.
    
    Yatirimciyi temettu veya bedelsiz gibi fiyati etkileyecek olaylara karsi uyarir.
    """
    ticker = ticker.upper()
    try:
        d_start = datetime.strptime(as_of_date, "%Y-%m-%d").date()
    except Exception:
        d_start = datetime.now(timezone.utc).date()

    d_end = d_start + timedelta(days=horizon_days)
    events = get_calendar_events(ticker=ticker, start_date=d_start.isoformat(), end_date=d_end.isoformat())

    warnings = []
    for e in events:
        e_type = e["event_type"]
        e_date = e["event_date"]
        impact = e["expected_impact"]
        desc = e["description"]

        if e_type in ("dividend", "bonus_issue", "rights_issue"):
            severity = "HIGH"
            msg = f"DİKKAT: {ticker} için {e_date} tarihinde {desc} bulunmaktadır. {impact}"
        else:
            severity = "MEDIUM"
            msg = f"BİLGİ: {ticker} için {e_date} tarihinde {desc} planlanmaktadır."

        warnings.append({
            "ticker": ticker,
            "event_date": e_date,
            "event_type": e_type,
            "severity": severity,
            "message": msg,
            "expected_impact": impact,
        })

    return warnings


# =====================================================================
# 4. MEVCUT KAP UPCOMING EVENTS ENTEGRASYONU (GERIYE UYUMLULUK)
# =====================================================================

def fetch_upcoming_events(as_of_date: str, tickers: list[str]) -> dict[str, list[dict]]:
    """Orijinal kap_web_mcp entegrasyonu (geriye uyumluluk icin korunur)."""
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
