"""Bultende bilgi amacli KAP kirmizi bayrak paneli (AL/TUT hisseleri, son 180 gun).

On-kayitli test (docs/research/kap_red_flags_preregistration.md) gecmedi:
bayraklar skoru ve AL/TUT/SAT kararini DEGISTIRMEZ, yalnizca "kontrol et"
notudur.

Veri: core/kap_api.py byCriteria sorgusu (konu + kisa ozet; borsapy news
yalnizca konu basligi veriyor). Eksik gunler kap_fetch_log'a gore haftalik
pencerelerle cekilir; normal gunde tek istek. KAP CI'da sik baglanti kestigi
icin (bkz. run_health) ilk hatada durulur, eksik gunler sonraki kosuda
tamamlanir. Panel eksik gun varsa "bayrak yok" DEMEZ.
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

from core import db, kap_api
from core.kap_red_flags import RED_FLAG_LABELS, classify

WINDOW_DAYS = 180
_WEEK = 7
_SLEEP_S = 1.5
# Ileride LLM etiketlemesi icin saklanan serbest metinli konular.
_FREE_TEXT_SUBJECTS = ("Özel Durum Açıklaması", "Haber ve Söylentilere")
KAP_URL = "https://www.kap.org.tr/tr/Bildirim/"


def _fetched_days() -> set[str]:
    return {r["day"] for r in db.query("SELECT day FROM kap_fetch_log")}


def _windows(days: list[date]) -> list[tuple[date, date]]:
    """Ardisik gunleri en fazla 7 gunluk pencerelere boler."""
    out: list[tuple[date, date]] = []
    for d in days:
        if out and (d - out[-1][1]).days == 1 and (d - out[-1][0]).days < _WEEK:
            out[-1] = (out[-1][0], d)
        else:
            out.append((d, d))
    return out


def _store(rows: list[dict]) -> None:
    out = []
    for r in rows:
        subject, summary = r.get("subject") or "", r.get("summary") or ""
        flag = classify(subject, summary)
        if flag is None and not subject.startswith(_FREE_TEXT_SUBJECTS):
            continue
        published = datetime.strptime(r["publishDate"], "%d.%m.%Y %H:%M:%S").isoformat(sep=" ")
        for code in (r.get("stockCodes") or "").split(","):
            if code.strip():
                out.append((int(r["disclosureIndex"]), code.strip(), published, subject, summary, flag))
    db.executemany(
        "INSERT OR REPLACE INTO kap_feed (disclosure_index, ticker, published_at, subject, summary, red_flag) "
        "VALUES (?,?,?,?,?,?)", out)


def refresh(as_of_date: str, http=None, sleep_s: float = _SLEEP_S) -> dict:
    """[as_of - 180 gun, as_of] icindeki cekilmemis gunleri ceker ve saklar."""
    as_of = date.fromisoformat(as_of_date)
    have = _fetched_days()
    missing = [as_of - timedelta(days=i) for i in range(WINDOW_DAYS, -1, -1)]
    missing = [d for d in missing if d.isoformat() not in have]
    own = http is None
    http = http or kap_api.client()
    fetched, error = 0, None
    try:
        for fr, to in _windows(missing):
            try:
                rows = kap_api.fetch_range(http, fr, to, retries=3, base_wait=20, max_wait=80)
                if len(rows) >= kap_api.PAGE_CAP:
                    rows = []
                    for i in range((to - fr).days + 1):
                        d = fr + timedelta(days=i)
                        rows += kap_api.fetch_range(http, d, d, retries=3, base_wait=20, max_wait=80)
                        time.sleep(sleep_s)
            except RuntimeError as exc:
                error = str(exc)
                break
            _store(rows)
            per_day: dict[str, int] = {}
            for r in rows:
                day = datetime.strptime(r["publishDate"], "%d.%m.%Y %H:%M:%S").date().isoformat()
                per_day[day] = per_day.get(day, 0) + 1
            now = datetime.now().isoformat(timespec="seconds")
            done = [fr + timedelta(days=i) for i in range((to - fr).days + 1)]
            # Kosu gunu bitmedi: sonraki kosuda tekrar cekilir.
            db.executemany("INSERT OR REPLACE INTO kap_fetch_log (day, n_disclosures, fetched_at) VALUES (?,?,?)",
                           [(d.isoformat(), per_day.get(d.isoformat(), 0), now) for d in done if d < as_of])
            fetched += 1
            time.sleep(sleep_s)
    finally:
        if own:
            http.close()
    return {"windows_fetched": fetched, "error": error}


def build_panel(as_of_date: str, tickers: list[str], refresh_error: str | None = None) -> dict:
    """AL/TUT hisseleri icin son 180 gunun kirmizi bayraklari.

    status: ok (pencere tam), partial (bazi gunler cekilemedi), unavailable
    (hic gun yok). Sayilar payload'da hesaplanir (sablonda | length yok)."""
    as_of = date.fromisoformat(as_of_date)
    start = as_of - timedelta(days=WINDOW_DAYS)
    have = _fetched_days()
    window = [(start + timedelta(days=i)).isoformat() for i in range(WINDOW_DAYS)]
    missing_days = sum(1 for d in window if d not in have)
    status = "ok" if missing_days == 0 else ("unavailable" if missing_days == WINDOW_DAYS else "partial")

    holdings = []
    if tickers and status != "unavailable":
        marks = ",".join("?" * len(tickers))
        rows = db.query(
            f"SELECT disclosure_index, ticker, published_at, red_flag FROM kap_feed "
            f"WHERE red_flag IS NOT NULL AND ticker IN ({marks}) AND published_at >= ? AND published_at < ? "
            f"ORDER BY ticker, published_at DESC",
            (*tickers, start.isoformat(), (as_of + timedelta(days=1)).isoformat()))
        # Hisse basina kategori ozeti: adet, en yeni tarih ve en yeni bildirimin linki.
        by_ticker: dict[str, dict[str, dict]] = {}
        for r in rows:  # published_at DESC: ilk gorulen en yeni
            cats = by_ticker.setdefault(r["ticker"], {})
            c = cats.get(r["red_flag"])
            if c is None:
                cats[r["red_flag"]] = {
                    "category": r["red_flag"], "label": RED_FLAG_LABELS.get(r["red_flag"], r["red_flag"]),
                    "count": 1, "last_date": r["published_at"][:10],
                    "disclosure_index": r["disclosure_index"], "url": f"{KAP_URL}{r['disclosure_index']}"}
            else:
                c["count"] += 1
        holdings = [{"ticker": t, "n_flags": sum(c["count"] for c in cats.values()),
                     "categories": sorted(cats.values(), key=lambda c: c["last_date"], reverse=True)}
                    for t, cats in sorted(by_ticker.items())]
    return {"status": status, "window_days": WINDOW_DAYS, "missing_days": missing_days,
            "n_holdings": len(tickers), "n_flagged_holdings": len(holdings),
            "holdings": holdings, "refresh_error": refresh_error}
