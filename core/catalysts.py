"""catalyst_engine: KAP bildirimlerini (once deterministik kategoriye indirgenmis olarak)
agirliklandirir ve zamanla sonumlenen bir katalizor skoru uretir.

no_free_text_interpretation_of_kap: burada hicbir yerde bildirim ozet/baslik metni
LLM'e verilmez; yalnizca category/impact_sign/weight sayisal olarak islenir.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core import db, decay
from kap_web_mcp import server as kap_web_mcp

_CONFIG = decay.load_config()


def fetch_kap_catalysts(as_of_date: str, tickers: list[str], lookback_days: int = 14) -> dict[str, dict]:
    disclosures = kap_web_mcp.get_disclosures(tickers, as_of_date, lookback_days=lookback_days)
    ingested_at = datetime.now(timezone.utc).isoformat()
    as_of = datetime.strptime(as_of_date, "%Y-%m-%d").date()

    rows_to_store = []
    per_ticker_scores: dict[str, dict] = {t: {"catalyst_score": 0.0, "volatility_event": False, "events": []} for t in tickers}

    for d in disclosures:
        category = d["category"]
        cat_cfg = _CONFIG["categories"].get(category)
        if cat_cfg is None:
            continue
        half_life = _CONFIG["half_life_days"][category]
        published = datetime.strptime(d["published_at"], "%Y-%m-%d").date()
        days_since = max(0, (as_of - published).days)
        eff_w = decay.effective_weight(cat_cfg["weight"], days_since, half_life)

        sign_mode = cat_cfg["sign"]
        if sign_mode == "positive":
            sign = 1
        elif sign_mode == "negative":
            sign = -1
        elif sign_mode == "by_surprise":
            sign = 1 if d["impact_sign"] == "positive" else -1
        else:  # neutral / volatility_event
            sign = 0

        contribution = sign * eff_w
        ticker = d.get("ticker") or _ticker_from_disclosure_id(d["disclosure_id"])
        if ticker not in per_ticker_scores:
            per_ticker_scores[ticker] = {"catalyst_score": 0.0, "volatility_event": False, "events": []}
        per_ticker_scores[ticker]["catalyst_score"] += contribution
        if sign_mode == "volatility_event":
            per_ticker_scores[ticker]["volatility_event"] = True
        per_ticker_scores[ticker]["events"].append({"category": category, "sign": sign_mode,
                                                      "published_at": d["published_at"]})

        rows_to_store.append({
            "ticker": ticker, "disclosure_id": d["disclosure_id"], "category": category,
            "title": d["title"], "summary": d["summary"], "impact_sign": d["impact_sign"],
            "weight": cat_cfg["weight"], "url": d["url"], "published_at": d["published_at"],
            "available_at": d["available_at"], "effective_at": d["effective_at"],
        })

    # -1..+1 arasina normalize et (mumkun maksimum toplam agirlikla)
    max_possible = sum(c["weight"] for c in _CONFIG["categories"].values()) or 1
    for t, s in per_ticker_scores.items():
        s["catalyst_score"] = max(-1.0, min(1.0, s["catalyst_score"] / max_possible))

    if rows_to_store:
        conn = db.get_connection()
        try:
            conn.executemany(
                """INSERT INTO kap_disclosures (ticker, disclosure_id, category, title, summary,
                   impact_sign, weight, url, published_at, available_at, effective_at)
                   VALUES (:ticker, :disclosure_id, :category, :title, :summary, :impact_sign,
                           :weight, :url, :published_at, :available_at, :effective_at)""",
                rows_to_store,
            )
            conn.commit()
        finally:
            conn.close()

    return per_ticker_scores


def _ticker_from_disclosure_id(disclosure_id: str) -> str:
    return disclosure_id.split("-")[0]
