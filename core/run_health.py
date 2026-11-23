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
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

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

# P3-1: Is Yatirim TMS 29 sozlesmesi izleme (docs/plan_2026-10-26.md).
# Dogrulanmis TL raporlayan (reexpression_class.parquet: cls == 'reexpressed')
# buyuk/likit sanayi-perakende-telekom sirketleri orneklemi (yabanci para
# fonksiyonel para birimli THYAO/TAVHL/EREGL/ENKAI/PGSUS haric).
# Mevcut sozlesmede P ve P-4 ayni satin alma gucunde oldugundan ayrik son
# ceyrek / gecen yil ayni ceyrek medyan orani ~1.0 (reel buyume) cikar.
# Birim karismasi (0.4-0.6x) veya yeniden ifade degisikligi (>1.25x) DEGRADED uretir.
VENDOR_SAMPLE_TICKERS = (
    "BIMAS", "MGROS", "ARCLK", "ASELS", "FROTO", "TOASO", "TUPRS", "KCHOL",
    "SAHOL", "SISE", "TCELL", "TTKOM", "DOAS", "CCOLA", "AEFES", "ULKER",
    "SOKM", "AKSA", "PETKM", "OTKAR",
)
VENDOR_RATIO_MIN = 0.75
VENDOR_RATIO_MAX = 1.25
VENDOR_SAMPLE_MIN_N = 5

# P3-2: Piyasa degeri capraz kontrolu (TradingView fast_info vs Is Yatirim Screener).
# %10 ustu fark veren adaylar bayraklanir ve kosu DEGRADED isaretlenir (skoru degistirmez).
MCAP_MAX_DIFF_SHARE = 0.10


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


def vendor_consistency_check(
    income_stmts: dict[str, object],
    cpi=None,
    min_ratio: float = VENDOR_RATIO_MIN,
    max_ratio: float = VENDOR_RATIO_MAX,
    min_sample: int = VENDOR_SAMPLE_MIN_N,
) -> dict:
    """P3-1: Is Yatirim TMS 29 sozlesmesinin bozulmadigini izler.

    TL raporlayan orneklem icin son ceyregin ayrik hasilatini (`q_revenue`) bir
    yil onceki ayni ceyregin ayrik hasilatina boler (`pit_panel.quarterly_table`).
    Mevcut sozlesmede P ve P-4 ayni satin alma gucundedir (medyan ~1.0).
    Birim karismasi (0.4-0.6x) veya yeniden ifade degisikligi (>1.25x) medyani
    [min_ratio, max_ratio] disina tasir ve ok=False doner.
    """
    from core import pit_panel

    ratios: list[tuple[str, str, float]] = []
    for ticker, inc in income_stmts.items():
        if inc is None or getattr(inc, "empty", True):
            continue
        long = pit_panel.statements_long(ticker, None, inc)
        if long.empty:
            continue
        qt = pit_panel.quarterly_table(long, cpi=cpi)
        if qt.empty or "q_revenue" not in qt.columns:
            continue
        qt = qt.sort_values("period_end")
        last = qt.iloc[-1]
        period = str(last["period"])
        if period < pit_panel.IAS29_FIRST_PERIOD:
            continue
        try:
            y, q = int(period[:4]), int(period[-1])
        except (TypeError, ValueError):
            continue
        prev = qt[qt["period"] == f"{y - 1}Q{q}"]
        if prev.empty:
            continue
        now_v = float(last["q_revenue"])
        prev_v = float(prev.iloc[0]["q_revenue"])
        if math.isfinite(now_v) and math.isfinite(prev_v) and prev_v > 0:
            ratios.append((ticker, period, now_v / prev_v))

    n_checked = len(ratios)
    if not n_checked:
        return {
            "n_checked": 0, "median_ratio": None, "min_ratio": None, "max_ratio": None,
            "n_out_of_range": 0, "ok": None, "ratios": {},
        }
    vals = [r for _, _, r in ratios]
    med = round(float(median(vals)), 3)
    out_of_range = sum(1 for v in vals if v < min_ratio or v > max_ratio)
    ok = None if n_checked < min_sample else (min_ratio <= med <= max_ratio)
    return {
        "n_checked": n_checked,
        "median_ratio": med,
        "min_ratio": round(float(min(vals)), 3),
        "max_ratio": round(float(max(vals)), 3),
        "n_out_of_range": out_of_range,
        "ok": ok,
        "ratios": {tk: round(r, 3) for tk, _, r in ratios},
    }


def market_cap_cross_check(
    tv_mcaps: dict[str, float | None],
    isy_mcaps: dict[str, float | None],
    max_diff: float = MCAP_MAX_DIFF_SHARE,
) -> dict:
    """P3-2: TradingView (fast_info) piyasa degerini Is Yatirim Screener ile karsilastirir.

    Ikisinde de pozitif/sonlu degeri olan hisselerde |TV - ISY| / ISY > max_diff
    (%10) olanlari bayraklar. Yalnizca izleme, skoru degistirmez.
    """
    n_checked = 0
    max_rel = 0.0
    flagged: list[dict] = []
    for ticker, tv_raw in tv_mcaps.items():
        isy_raw = isy_mcaps.get(ticker)
        if tv_raw is None or isy_raw is None:
            continue
        try:
            tv, isy = float(tv_raw), float(isy_raw)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(tv) and math.isfinite(isy) and tv > 0 and isy > 0):
            continue
        n_checked += 1
        rel = abs(tv - isy) / isy
        if rel > max_rel:
            max_rel = rel
        if rel > max_diff:
            flagged.append({
                "ticker": ticker,
                "tv_mcap": round(tv),
                "isy_mcap": round(isy),
                "diff_pct": round(100.0 * rel, 1),
            })
    flagged.sort(key=lambda r: (-r["diff_pct"], r["ticker"]))
    return {
        "n_checked": n_checked,
        "n_flagged": len(flagged),
        "flagged_share": _share(len(flagged), n_checked),
        "max_diff_share": round(max_rel, 4) if n_checked else None,
        "max_diff_pct": round(100.0 * max_rel, 1) if n_checked else None,
        "flagged": flagged,
    }


def assess(as_of_date: str, prices: dict | None = None,
           catalyst_available: dict[str, bool] | None = None,
           vendor_check: dict | None = None,
           mcap_check: dict | None = None,
           companies_status: dict | None = None) -> dict:
    """prices: price_stats() ciktisi; verilmezse prices tablosundan okunur.
    catalyst_available: ticker -> KAP bildirim listesi cekilebildi mi.
    vendor_check: vendor_consistency_check() ciktisi (P3-1).
    mcap_check: market_cap_cross_check() ciktisi (P3-2).
    companies_status: live_data.get_companies_status() ciktisi (bp.companies() cache fallback bilgisi)."""
    if companies_status is None:
        try:
            from core import live_data as _ld
            companies_status = _ld.get_companies_status()
        except Exception:  # noqa: BLE001
            companies_status = None
    companies_fallback = bool(companies_status and companies_status.get("fallback_used"))
    companies_cache_age = (
        companies_status.get("age_days") if (companies_status and companies_fallback) else None
    )
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
        "vendor_checked_n": vendor_check["n_checked"] if vendor_check is not None else None,
        "vendor_q_yoy_median": vendor_check["median_ratio"] if vendor_check is not None else None,
        "vendor_out_of_range_n": vendor_check["n_out_of_range"] if vendor_check is not None else None,
        "mcap_checked_n": mcap_check["n_checked"] if mcap_check is not None else None,
        "mcap_flagged_n": mcap_check["n_flagged"] if mcap_check is not None else None,
        "mcap_flagged_share": mcap_check["flagged_share"] if mcap_check is not None else None,
        "mcap_max_diff_share": mcap_check["max_diff_share"] if mcap_check is not None else None,
        "mcap_flagged_tickers": ([f["ticker"] for f in mcap_check["flagged"]]
                                 if mcap_check is not None else None),
        "companies_cache_fallback": companies_fallback,
        "companies_cache_age_days": companies_cache_age,
    }
    thresholds = {
        "min_fundamentals_coverage": MIN_FUNDAMENTALS_COVERAGE,
        "min_price_fresh_coverage": MIN_PRICE_FRESH_COVERAGE,
        "max_data_filter_share": MAX_DATA_FILTER_SHARE,
        "max_kap_missing_share": MAX_KAP_MISSING_SHARE,
        "vendor_ratio_min": VENDOR_RATIO_MIN,
        "vendor_ratio_max": VENDOR_RATIO_MAX,
        "mcap_max_diff": MCAP_MAX_DIFF_SHARE,
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
    if vendor_check is not None and vendor_check.get("ok") is False:
        degraded.append("vendor_inconsistent")
    if mcap_check is not None and mcap_check.get("n_flagged", 0) > 0:
        degraded.append("mcap_mismatch")
    if companies_fallback:
        degraded.append("companies_cache_fallback")

    status = "FAILED" if failed else ("DEGRADED" if degraded else "OK")
    # Bultende gosterilen yuzdeler payload'dan gelmeli (report/validate.py orphan kontrolu).
    pct = {k: round(100 * v, 1) for k, v in {**metrics, **thresholds}.items()
           if isinstance(v, float) and not isinstance(v, bool)}
    return {"as_of_date": as_of_date, "status": status, "issues": failed + degraded,
            "metrics": metrics, "thresholds": thresholds, "pct": pct,
            "mcap_flagged": list(mcap_check["flagged"]) if mcap_check is not None else [],
            "config_hash": config_hash()}


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
             json.dumps({"metrics": health["metrics"], "thresholds": health["thresholds"],
                         "mcap_flagged": health.get("mcap_flagged", [])}),
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
