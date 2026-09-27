"""evaluate_past_predictions: canli takip (ex-post tracking), BACKTEST DEGIL.

evaluate_past_predictions_clarification kurallarina tabidir:
- independence_caveat: ufuklar ortusur, N gunluk takip N bagimsiz gozlem degildir.
- banned_claims: bu modulun urettigi hicbir metin/rapor "kanitlanmis edge",
  "istatistiksel olarak anlamli", "backtest edilmis" gibi ifadeler icermez.
point_in_time_rule: yalnizca effective_at <= degerlendirme tarihi olan satirlar kullanilir.

Not (execution_order): payload asamasi bu modulun HESAPLADIGI degil, DAHA
ONCE hesaplanip outcomes tablosuna yazilmis sonuclari okur (summarize_outcomes).
evaluate_past_predictions'in kendisi -- yeni matured tahminleri hesaplayip
outcomes tablosuna yazan taraf -- execution_order'da dispatch'ten SONRA
calisir, boylece bir sonraki kosunun payload'u guncel veriyi bulur.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median

from core import db
from macro_mcp import server as macro_mcp
from bist_mcp import server as bist_mcp

# prediction_horizon_evaluation_mismatch (v12 T0-1): core/targets.py::compute_long_term_target
# ve run.py, uzun vadeli tezleri horizon_days=180 ile predictions tablosuna yaziyordu, ama
# 180 bu listede YOKTU -- 180 gunluk HICBIR tahmin (evrenin tum uzun-vadeli tezleri) asla
# degerlendirilemiyordu. Kanit (2026-09-17, data/bist_history.db): 108 predictions satirinin
# 74'u (%69) horizon_days=180, outcomes tablosu 0 satir. 180 gun kisa vade (20) ile ayni
# kesitte oldugu icin ORTUSME artiyor -- bkz. asagidaki independence_caveat guncellemesi.
HORIZONS_DAYS = [5, 20, 60, 180]

ALLOWED_CLAIMS = [
    "tanimlayici izleme metrigi (hit_rate, ortalama fazla getiri) belirtilen donem icin",
    "bu bir canli takip ozetidir, gecmis performans garantisi degildir",
]
BANNED_CLAIMS = ["kanitlanmis edge", "istatistiksel olarak anlamli", "backtest edilmis",
                  "dogrulanmis strateji", "sharpe orani"]


def _usdtry_on_or_before(date_str: str) -> float | None:
    rows = db.query("SELECT usdtry_spot FROM regime_log WHERE as_of_date<=? AND usdtry_spot IS NOT NULL "
                    "ORDER BY as_of_date DESC LIMIT 1", (date_str,))
    return rows[0]["usdtry_spot"] if rows else None


def matured_without_outcome(as_of_date: str, grace_days: int = 3) -> int:
    """Ufku grace_days'ten once dolmus ama outcomes'a yazilmamis tahmin sayisi
    (core/run_health.py: sessiz degerlendirme cokusunu yakalar)."""
    rows = db.query(
        """SELECT COUNT(*) AS n FROM predictions p
           WHERE date(p.as_of_date, '+' || p.horizon_days || ' days', '+' || ? || ' days') <= date(?)
             AND NOT EXISTS (SELECT 1 FROM outcomes o WHERE o.as_of_date=p.as_of_date
                             AND o.ticker=p.ticker AND o.horizon_days=p.horizon_days)""",
        (grace_days, as_of_date))
    return rows[0]["n"] if rows else 0


def _already_evaluated(pred_as_of_date: str, ticker: str, horizon_days: int) -> bool:
    rows = db.query(
        "SELECT 1 FROM outcomes WHERE as_of_date=? AND ticker=? AND horizon_days=? LIMIT 1",
        (pred_as_of_date, ticker, horizon_days),
    )
    return bool(rows)


def evaluate_past_predictions(as_of_date: str, lookback_months: int = 6) -> dict:
    """Ufku dolmus (matured) tahminler icin outcomes hesaplar ve tabloya yazar.
    Zaten degerlendirilmis (as_of_date, ticker, horizon_days) uclulerini tekrar islemez.
    """
    cutoff = (datetime.strptime(as_of_date, "%Y-%m-%d") - timedelta(days=lookback_months * 30)).date().isoformat()
    predictions = db.query(
        "SELECT * FROM predictions WHERE as_of_date >= ? AND as_of_date <= ?",
        (cutoff, as_of_date),
    )

    macro_now = macro_mcp.get_macro_snapshot(as_of_date)
    outcomes_rows = []
    skipped: dict[str, int] = {}

    def _skip(reason: str) -> None:
        skipped[reason] = skipped.get(reason, 0) + 1

    for p in predictions:
        horizon = p["horizon_days"]
        if horizon not in HORIZONS_DAYS:
            continue
        pred_date = datetime.strptime(p["as_of_date"], "%Y-%m-%d").date()
        eval_date = pred_date + timedelta(days=horizon)
        if eval_date.isoformat() > as_of_date:
            continue  # ufuk henuz dolmadi
        if _already_evaluated(p["as_of_date"], p["ticker"], horizon):
            continue  # bu tahmin bu ufuk icin daha once degerlendirildi

        # Giris ve cikis AYNI (duzeltilmis) seriden, kapanistan kapanisa: aradaki
        # bedelsiz/temettu duzeltmesi ham giris fiyatiyla karistirilirsa sahte
        # kayip/kazanc olusur. Seri bulunamazsa satir atlanir, sonraki kosuda denenir.
        prices = bist_mcp.get_prices(p["ticker"], eval_date.isoformat(), days=horizon + 15)
        if not prices:
            _skip("no_prices")
            continue
        entry_rows = [r for r in prices if str(r["date"])[:10] <= p["as_of_date"]]
        entry = entry_rows[-1]["close"] if entry_rows else p["entry_price"]
        exit_price = prices[-1]["close"]
        if not entry or not exit_price:
            _skip("bad_price")
            continue
        return_pct = (exit_price - entry) / entry * 100

        # v10 roadmap: xu100_benchmark_integration -- gercek XU100 serisiyle
        # kiyaslar. Cekilemezse UYDURMA 0.0 YAZMAZ -- satir atlanir ve
        # _already_evaluated onu isaretlemedigi icin bir sonraki kosuda tekrar denenir.
        xu100_return_pct = macro_mcp.get_index_return_pct("XU100", p["as_of_date"], eval_date.isoformat())
        if xu100_return_pct is None:
            _skip("no_xu100")
            continue
        # Mevduat/risksiz kiyas: tahmin aninda kaydedilen hurdle (2Y tahvil, ufka
        # bilesik). Onceden bugunun politika faizi kullaniliyordu; canli kaynak
        # (borsapy.policy_rate) makul aralik disi deger dondugu icin HER satir
        # atlaniyor ve outcomes hic yazilmiyordu (2026-09-27 teshisi).
        deposit_return_pct = p["hurdle_rate_pct"] if "hurdle_rate_pct" in p.keys() else None
        if deposit_return_pct is None and macro_now.get("bond_2y_pct") is not None:
            deposit_return_pct = ((1 + macro_now["bond_2y_pct"] / 100) ** (horizon / 365) - 1) * 100
        if deposit_return_pct is None:
            _skip("no_risk_free")
            continue
        # USD getirisi: giris kuru tahmin gunu, cikis kuru degerlendirme gunu
        # (onceden ikisi de bugunun kuruydu -> USD getirisi = TL getirisi).
        fx_entry = _usdtry_on_or_before(p["as_of_date"])
        fx_exit = _usdtry_on_or_before(eval_date.isoformat()) or macro_now.get("usdtry_spot")
        usd_return_pct = ((exit_price / fx_exit) / (entry / fx_entry) - 1) * 100 if fx_entry and fx_exit else None

        outcomes_rows.append({
            "as_of_date": p["as_of_date"], "ticker": p["ticker"], "horizon_days": horizon,
            "return_pct": return_pct, "xu100_return_pct": xu100_return_pct,
            "deposit_return_pct": deposit_return_pct, "usd_return_pct": usd_return_pct,
            "excess_vs_index_pct": return_pct - xu100_return_pct,
            "excess_vs_deposit_pct": return_pct - deposit_return_pct,
            "evaluated_at": as_of_date,
        })

    if outcomes_rows or skipped:
        print(f"[evaluate] {len(outcomes_rows)} sonuc yazildi; atlanan: {skipped or 'yok'}", flush=True)

    if outcomes_rows:
        conn = db.get_connection()
        try:
            conn.executemany(
                """INSERT INTO outcomes (as_of_date, ticker, horizon_days, return_pct, xu100_return_pct,
                   deposit_return_pct, usd_return_pct, excess_vs_index_pct, excess_vs_deposit_pct, evaluated_at)
                   VALUES (:as_of_date, :ticker, :horizon_days, :return_pct, :xu100_return_pct,
                           :deposit_return_pct, :usd_return_pct, :excess_vs_index_pct, :excess_vs_deposit_pct, :evaluated_at)""",
                outcomes_rows,
            )
            conn.commit()
        finally:
            conn.close()

    return summarize_outcomes(as_of_date, lookback_months)


def summarize_outcomes(as_of_date: str, lookback_months: int = 6) -> dict:
    """outcomes tablosunda ONCEDEN hesaplanmis satirlari okuyup tanimlayici
    metrikler uretir. Yeni bir hesap YAPMAZ (bkz. modul dosya-basi notu)."""
    cutoff = (datetime.strptime(as_of_date, "%Y-%m-%d") - timedelta(days=lookback_months * 30)).date().isoformat()
    rows = db.query(
        "SELECT * FROM outcomes WHERE evaluated_at >= ? AND evaluated_at <= ?",
        (cutoff, as_of_date),
    )
    per_horizon: dict[int, list] = {h: [] for h in HORIZONS_DAYS}
    for r in rows:
        if r["horizon_days"] in per_horizon:
            per_horizon[r["horizon_days"]].append(r)

    summary = {}
    for horizon, hrows in per_horizon.items():
        if not hrows:
            summary[horizon] = None
            continue
        hits = sum(1 for r in hrows if r["excess_vs_index_pct"] > 0)
        hit_rate = hits / len(hrows)
        summary[horizon] = {
            "n_observations": len(hrows),
            "hit_rate": hit_rate,
            "hit_rate_pct": hit_rate * 100,  # sablonda dogrudan gosterilen, payload'da da bulunan olceklenmis deger
            "median_excess_vs_index": median(r["excess_vs_index_pct"] for r in hrows),
            "median_excess_vs_deposit": median(r["excess_vs_deposit_pct"] for r in hrows),
        }

    return {
        "is_not_a_backtest": True,
        "independence_caveat": "T+5/T+20/T+60/T+180 ufuklari gunluk secilen adaylarda ortusur "
                                "(180 gunluk uzun vadeli tezler 20 gunluk kisa vadeli adaylarla "
                                "ayni donemde secilebilir); N gunluk takip N bagimsiz gozlem "
                                "anlamina gelmez. Her ufuk asagida AYRI gosterilir, tek bir "
                                "birlesik basari orani verilmez.",
        "by_horizon": summary,
        "allowed_claims": ALLOWED_CLAIMS,
        "banned_claims": BANNED_CLAIMS,
    }
