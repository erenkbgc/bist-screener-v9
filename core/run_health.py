"""run_health: kosu seviyesinde veri saglik kapisi (roadmap Adim 6).

Neden: 2026-09-20..27 arasinda KAP baglantisi CI'da koptugu icin 4 kosuda
527/527 hisse point_in_time filtresinden sessizce elendi; bulten "bugun
sinyal yok" dedi ve kimse fark etmedi. Bu modul kosu sonunda DB'den kapsam
olcer, sonucu bultene uyari bandi olarak koyar ve run_health tablosuna yazar.

Durumlar:
  OK        -- esiklerin hepsi saglandi.
  DEGRADED  -- sinyaller uretildi ama bir veri kaynagi eksik/zayif
               (orn. KAP erisilemedi -> katalizor skoru kor).
  FAILED    -- sinyaller guvenilmez: temel veri/fiyat kapsami dusuk, makro
               eksik veya veri kaynakli eleme orani yuksek.
Esikler bilincli olarak kaba tutuldu; amac ince ayar degil, sessiz
kapsam cokuslerini gorunur kilmak.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core import db

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

# Kapsam esikleri (oran, 0-1). Asagisi FAILED.
MIN_FUNDAMENTALS_COVERAGE = 0.80
MIN_PRICE_FRESH_COVERAGE = 0.80
# Veri kaynakli eleme nedenleri (model karari degil): bu nedenlerle elenen
# aday orani bu esigi asarsa FAILED.
DATA_FILTER_REASONS = ("point_in_time", "reporting_basis")
MAX_DATA_FILTER_SHARE = 0.20
# KAP'tan finansal rapor tarihi alinamayan hisse orani bunu asarsa DEGRADED
# (KAP disinda kalan: katalizor bildirimleri de muhtemelen eksik).
MAX_KAP_MISSING_SHARE = 0.50
PRICE_FRESH_DAYS = 5


def _matured_without_outcome(as_of_date: str) -> int:
    from core.evaluate import matured_without_outcome
    return matured_without_outcome(as_of_date)


def config_hash() -> str:
    """Skoru etkileyen config dosyalarinin kisa SHA-256 ozeti (rapor-config eslesmesi)."""
    h = hashlib.sha256()
    for p in sorted(CONFIG_DIR.glob("*.yaml")) + sorted(CONFIG_DIR.glob("*.json")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def _share(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def price_stats(as_of_date: str, prices_by_ticker: dict[str, list[dict]], index_rows: list[dict] | None) -> dict:
    """run.py bellekteki fiyat serilerinden tazelik ozeti (prices tablosu canlida yazilmiyor)."""
    fresh_from = (datetime.strptime(as_of_date, "%Y-%m-%d") - timedelta(days=PRICE_FRESH_DAYS)).date().isoformat()
    fresh = sum(1 for rows in prices_by_ticker.values()
                if rows and fresh_from <= str(rows[-1].get("date", ""))[:10] <= as_of_date)
    return {"n_tickers": len(prices_by_ticker), "n_fresh": fresh, "index_rows": len(index_rows or [])}


def assess(as_of_date: str, prices: dict | None = None,
           catalyst_available: dict[str, bool] | None = None) -> dict:
    """prices: price_stats() ciktisi; verilmezse prices tablosundan okunur.
    catalyst_available: ticker -> KAP bildirim listesi cekilebildi mi."""
    # Uygun evren: universe.py exclusion_reason'i NULL birakan hisseler (hacim/tedbir vb. disi)
    universe_n = db.query("SELECT COUNT(*) AS n FROM universe_snapshot WHERE as_of_date=? AND exclusion_reason IS NULL",
                          (as_of_date,))[0]["n"]
    fund = db.query("SELECT effective_at, pit_source, reporting_basis FROM fundamentals WHERE as_of_date=?",
                    (as_of_date,))
    fund_n = len(fund)
    pit_missing = sum(1 for r in fund if r["effective_at"] is None)
    # pit_source NULL = kolon oncesi satir; tarih varsa KAP'tan gelmistir
    kap_missing = sum(1 for r in fund if r["pit_source"] != "kap_financial_report"
                      and not (r["pit_source"] is None and r["effective_at"] is not None))
    if prices is None:
        fresh_from = (datetime.strptime(as_of_date, "%Y-%m-%d") - timedelta(days=PRICE_FRESH_DAYS)).date().isoformat()
        fresh_n = db.query("SELECT COUNT(DISTINCT ticker) AS n FROM prices WHERE date>=? AND date<=?",
                           (fresh_from, as_of_date))[0]["n"]
        index_ok = True
    else:
        fresh_n, index_ok = prices["n_fresh"], prices["index_rows"] > 0
    regime = db.query("SELECT xu100_level, bond_2y_pct FROM regime_log WHERE as_of_date=?", (as_of_date,))
    scores = db.query("SELECT bucket, filtered_by FROM scores WHERE as_of_date=?", (as_of_date,))
    scored_n = len(scores)
    data_filtered = sum(1 for r in scores if r["filtered_by"] in DATA_FILTER_REASONS)

    metrics = {
        "universe_n": universe_n,
        "fundamentals_n": fund_n,
        "fundamentals_coverage": _share(fund_n, universe_n),
        "pit_missing_share": _share(pit_missing, fund_n),
        "kap_missing_share": _share(kap_missing, fund_n),
        "price_fresh_n": fresh_n,
        "price_fresh_coverage": _share(fresh_n, universe_n),
        "scored_n": scored_n,
        "data_filter_share": _share(data_filtered, scored_n),
        "xu100_present": bool(regime and regime[0]["xu100_level"]),
        "bond_2y_present": bool(regime and regime[0]["bond_2y_pct"] is not None),
        "index_series_present": index_ok,
        "matured_without_outcome": _matured_without_outcome(as_of_date),
        "catalyst_missing_share": (_share(sum(1 for v in catalyst_available.values() if not v),
                                          len(catalyst_available)) if catalyst_available else None),
    }
    thresholds = {
        "min_fundamentals_coverage": MIN_FUNDAMENTALS_COVERAGE,
        "min_price_fresh_coverage": MIN_PRICE_FRESH_COVERAGE,
        "max_data_filter_share": MAX_DATA_FILTER_SHARE,
        "max_kap_missing_share": MAX_KAP_MISSING_SHARE,
    }

    failed, degraded = [], []

    def below(key: str, limit: float) -> bool:
        v = metrics[key]
        return v is None or v < limit

    if below("fundamentals_coverage", MIN_FUNDAMENTALS_COVERAGE):
        failed.append("fundamentals_coverage")
    if below("price_fresh_coverage", MIN_PRICE_FRESH_COVERAGE):
        failed.append("price_fresh_coverage")
    if not (metrics["xu100_present"] and metrics["bond_2y_present"]):
        failed.append("macro_missing")
    if not index_ok:
        failed.append("index_series_empty")
    if metrics["data_filter_share"] is not None and metrics["data_filter_share"] > MAX_DATA_FILTER_SHARE:
        failed.append("data_filter_share")
    if metrics["kap_missing_share"] is not None and metrics["kap_missing_share"] > MAX_KAP_MISSING_SHARE:
        degraded.append("kap_unavailable")
    # Katalizor agirligi 0 iken (Faz 2: test edilemez) eksik KAP verisi skoru etkilemez.
    from core.scoring import load_weights
    catalyst_weighted = float(load_weights()["scoring_weights"].get("catalyst_score", 0.0)) > 0
    if catalyst_weighted and metrics["catalyst_missing_share"] is not None \
            and metrics["catalyst_missing_share"] > MAX_KAP_MISSING_SHARE:
        degraded.append("catalyst_redistributed")
    if metrics["matured_without_outcome"]:
        degraded.append("outcomes_stalled")

    status = "FAILED" if failed else ("DEGRADED" if degraded else "OK")
    # Bultende gosterilen yuzdeler payload'dan gelmeli (report/validate.py orphan kontrolu).
    pct = {k: round(100 * v, 1) for k, v in {**metrics, **thresholds}.items()
           if isinstance(v, float) and not isinstance(v, bool)}
    return {"as_of_date": as_of_date, "status": status, "issues": failed + degraded,
            "metrics": metrics, "thresholds": thresholds, "pct": pct, "config_hash": config_hash()}


def persist(health: dict) -> None:
    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO run_health (as_of_date, status, config_hash, issues_json, metrics_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(as_of_date) DO UPDATE SET status=excluded.status, config_hash=excluded.config_hash,
                 issues_json=excluded.issues_json, metrics_json=excluded.metrics_json,
                 created_at=excluded.created_at""",
            (health["as_of_date"], health["status"], health["config_hash"], json.dumps(health["issues"]),
             json.dumps({"metrics": health["metrics"], "thresholds": health["thresholds"]}),
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
