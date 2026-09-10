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

HORIZONS_DAYS = [5, 20, 60]

ALLOWED_CLAIMS = [
    "tanimlayici izleme metrigi (hit_rate, ortalama fazla getiri) belirtilen donem icin",
    "bu bir canli takip ozetidir, gecmis performans garantisi degildir",
]
BANNED_CLAIMS = ["kanitlanmis edge", "istatistiksel olarak anlamli", "backtest edilmis",
                  "dogrulanmis strateji", "sharpe orani"]


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

        prices = bist_mcp.get_prices(p["ticker"], eval_date.isoformat(), days=horizon + 5)
        if not prices:
            continue
        entry, exit_price = p["entry_price"], prices[-1]["close"]
        return_pct = (exit_price - entry) / entry * 100

        xu100_return_pct = 0.0  # mock XU100 icin yer tutucu, gercek entegrasyonda indeks serisi kullanilir
        deposit_return_pct = macro_now["policy_rate_pct"] * (horizon / 365)
        usd_return_pct = ((exit_price / macro_now["usdtry_spot"]) / (entry / macro_now["usdtry_spot"]) - 1) * 100

        outcomes_rows.append({
            "as_of_date": p["as_of_date"], "ticker": p["ticker"], "horizon_days": horizon,
            "return_pct": return_pct, "xu100_return_pct": xu100_return_pct,
            "deposit_return_pct": deposit_return_pct, "usd_return_pct": usd_return_pct,
            "excess_vs_index_pct": return_pct - xu100_return_pct,
            "excess_vs_deposit_pct": return_pct - deposit_return_pct,
            "evaluated_at": as_of_date,
        })

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
        "independence_caveat": "T+5/T+20/T+60 ufuklari gunluk secilen adaylarda ortusur; "
                                "N gunluk takip N bagimsiz gozlem anlamina gelmez.",
        "by_horizon": summary,
        "allowed_claims": ALLOWED_CLAIMS,
        "banned_claims": BANNED_CLAIMS,
    }
