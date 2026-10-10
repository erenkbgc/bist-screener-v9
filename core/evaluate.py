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

# Kisa vade kurali (core/targets.py, scripts/backtest_short_term.py) "20" ile
# 20 ISLEM GUNU (bar) kastediyor; uzun vade 180 TAKVIM gunu (k_e * 180/365).
# Kisa vadeyi takvim gunuyle olcmek ~14 islem gunune denk gelip kurali
# backtestinden farkli bir ufukta degerlendiriyordu.
TRADING_DAY_BUCKETS = {"short_term"}
_CAL_PER_TRADING_DAY = 7 / 5

# Ozet gruplari: rapordaki "firsat" iddiasi yalnizca aksiyon etiketli satirlarla
# olculur; izleme listesi ve deneysel kisa vade ayri gosterilir.
ACTIONABLE_STATES = {"STRONG_OPPORTUNITY", "OPPORTUNITY"}

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


def _calendar_horizon(bucket: str | None, horizon: int) -> int:
    """Olgunlasma kontrolu icin takvim gunu karsiligi (islem gunu ufku ~7/5 ile)."""
    if bucket in TRADING_DAY_BUCKETS:
        return int(round(horizon * _CAL_PER_TRADING_DAY))
    return horizon


def _adj(bar: dict, key: str = "close") -> float | None:
    """Bedelsiz/bolunme duzeltilmis deger: ham * (adj_close / close)."""
    raw = bar.get(key)
    close = bar.get("close")
    if raw is None or not close:
        return None
    adj_close = bar.get("adj_close") or close
    return raw * adj_close / close


def matured_without_outcome(as_of_date: str, grace_days: int = 3) -> int:
    """Ufku grace_days'ten once dolmus ama outcomes'a yazilmamis tahmin sayisi
    (core/run_health.py: sessiz degerlendirme cokusunu yakalar)."""
    rows = db.query(
        """SELECT p.as_of_date, p.bucket, p.horizon_days FROM predictions p
           WHERE NOT EXISTS (SELECT 1 FROM outcomes o WHERE o.as_of_date=p.as_of_date
                             AND o.ticker=p.ticker AND o.horizon_days=p.horizon_days)""")
    today = datetime.strptime(as_of_date, "%Y-%m-%d").date()
    n = 0
    for r in rows:
        pred = datetime.strptime(r["as_of_date"], "%Y-%m-%d").date()
        if pred + timedelta(days=_calendar_horizon(r["bucket"], r["horizon_days"]) + grace_days) <= today:
            n += 1
    return n


def _path_stats(window: list[dict], entry_adj: float, entry_raw: float,
                target: float | None, stop: float | None) -> dict:
    """Giris ile cikis arasindaki fiyat yolu: hedef/stop hangisine once degdi,
    en yuksek/en dusuk (duzeltilmis) getiri. Hedef/stop ham giris fiyatina gore
    getiri esigine cevrilir; boylece arada bedelsiz olsa da karsilastirma tutarli kalir."""
    target_ret = target / entry_raw - 1 if target and entry_raw else None
    stop_ret = stop / entry_raw - 1 if stop and entry_raw else None
    first_touch = "none"
    max_up = max_down = 0.0
    for bar in window:
        hi = _adj(bar, "high") or _adj(bar)
        lo = _adj(bar, "low") or _adj(bar)
        up, down = hi / entry_adj - 1, lo / entry_adj - 1
        max_up, max_down = max(max_up, up), min(max_down, down)
        if first_touch != "none":
            continue
        if stop_ret is not None and down <= stop_ret:  # ayni bar: muhafazakar varsayim, once stop
            first_touch = "stop"
        elif target_ret is not None and up >= target_ret:
            first_touch = "target"
    return {"first_touch": first_touch, "max_runup_pct": max_up * 100, "max_drawdown_pct": max_down * 100}


def evaluate_past_predictions(as_of_date: str, lookback_months: int = 6) -> dict:
    """Ufku dolmus (matured) ve henuz outcomes'a yazilmamis TUM tahminleri isler.

    Onceki surum yalnizca son lookback_months*30 gunde verilmis tahminlere
    bakiyordu: 180 gunluk bir tahmin yalnizca tam d+180 gunu kosu olursa
    degerlendirilebiliyordu; o gun atlanirsa (hafta sonu, basarisiz kosu)
    sonsuza kadar degerlendirilmeden kaliyordu. lookback_months artik yalnizca
    ozet penceresidir.
    """
    today = datetime.strptime(as_of_date, "%Y-%m-%d").date()
    predictions = db.query(
        """SELECT p.* FROM predictions p
           WHERE p.as_of_date <= ?
             AND NOT EXISTS (SELECT 1 FROM outcomes o WHERE o.as_of_date=p.as_of_date
                             AND o.ticker=p.ticker AND o.horizon_days=p.horizon_days)""",
        (as_of_date,),
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
        bucket = p["bucket"]
        pred_date = datetime.strptime(p["as_of_date"], "%Y-%m-%d").date()
        if pred_date + timedelta(days=_calendar_horizon(bucket, horizon)) > today:
            continue  # ufuk henuz dolmadi

        # Giris ve cikis AYNI duzeltilmis (adj_close) seriden, kapanistan kapanisa:
        # ham kapanis kullanilirsa ufuk icindeki bedelsiz/bolunme sahte kayip yaratir.
        prices = bist_mcp.get_prices(p["ticker"], as_of_date, days=(today - pred_date).days + 15)
        if not prices:
            _skip("no_prices")
            continue
        entry_idx = max((i for i, r in enumerate(prices) if str(r["date"])[:10] <= p["as_of_date"]),
                        default=None)
        if entry_idx is None:
            _skip("no_entry_bar")
            continue
        if bucket in TRADING_DAY_BUCKETS:
            exit_idx = entry_idx + horizon
            if exit_idx >= len(prices):
                continue  # yeterli islem gunu henuz yok
        else:
            eval_iso = (pred_date + timedelta(days=horizon)).isoformat()
            exit_idx = max(i for i, r in enumerate(prices) if str(r["date"])[:10] <= eval_iso)
        entry_bar, exit_bar = prices[entry_idx], prices[exit_idx]
        entry, exit_price = _adj(entry_bar), _adj(exit_bar)
        if not entry or not exit_price:
            _skip("bad_price")
            continue
        return_pct = (exit_price - entry) / entry * 100
        exit_date = str(exit_bar["date"])[:10]
        path = _path_stats(prices[entry_idx + 1:exit_idx + 1], entry, entry_bar["close"],
                           p["target_price"], p["stop_loss"])

        # v10 roadmap: xu100_benchmark_integration -- gercek XU100 serisiyle
        # kiyaslar. Cekilemezse UYDURMA 0.0 YAZMAZ -- satir atlanir ve
        # outcomes'a yazilmadigi icin bir sonraki kosuda tekrar denenir.
        xu100_return_pct = macro_mcp.get_index_return_pct("XU100", p["as_of_date"], exit_date)
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
        # USD getirisi: giris kuru tahmin gunu, cikis kuru cikis bari gunu.
        fx_entry = _usdtry_on_or_before(p["as_of_date"])
        fx_exit = _usdtry_on_or_before(exit_date) or macro_now.get("usdtry_spot")
        usd_return_pct = ((exit_price / fx_exit) / (entry / fx_entry) - 1) * 100 if fx_entry and fx_exit else None

        outcomes_rows.append({
            "as_of_date": p["as_of_date"], "ticker": p["ticker"], "horizon_days": horizon,
            "return_pct": return_pct, "xu100_return_pct": xu100_return_pct,
            "deposit_return_pct": deposit_return_pct, "usd_return_pct": usd_return_pct,
            "excess_vs_index_pct": return_pct - xu100_return_pct,
            "excess_vs_deposit_pct": return_pct - deposit_return_pct,
            "evaluated_at": as_of_date,
            "bucket": bucket,
            "candidate_state": p["candidate_state"] if "candidate_state" in p.keys() else None,
            "exit_date": exit_date, **path,
        })

    if outcomes_rows or skipped:
        print(f"[evaluate] {len(outcomes_rows)} sonuc yazildi; atlanan: {skipped or 'yok'}", flush=True)

    if outcomes_rows:
        conn = db.get_connection()
        try:
            conn.executemany(
                """INSERT INTO outcomes (as_of_date, ticker, horizon_days, return_pct, xu100_return_pct,
                   deposit_return_pct, usd_return_pct, excess_vs_index_pct, excess_vs_deposit_pct, evaluated_at,
                   bucket, candidate_state, exit_date, first_touch, max_runup_pct, max_drawdown_pct)
                   VALUES (:as_of_date, :ticker, :horizon_days, :return_pct, :xu100_return_pct,
                           :deposit_return_pct, :usd_return_pct, :excess_vs_index_pct, :excess_vs_deposit_pct,
                           :evaluated_at, :bucket, :candidate_state, :exit_date, :first_touch,
                           :max_runup_pct, :max_drawdown_pct)""",
                outcomes_rows,
            )
            conn.commit()
        finally:
            conn.close()

    return summarize_outcomes(as_of_date, lookback_months)


def _group_of(row) -> str:
    state = row["candidate_state"] if "candidate_state" in row.keys() else None
    bucket = row["bucket"] if "bucket" in row.keys() else None
    if bucket == "short_term":
        return "experimental"
    if state in ACTIONABLE_STATES:
        return "actionable"
    if state is None:
        return "legacy_unlabeled"
    return "watchlist"


def _describe(hrows: list) -> dict:
    hits = sum(1 for r in hrows if r["excess_vs_index_pct"] > 0)
    hit_rate = hits / len(hrows)
    touched = [r["first_touch"] for r in hrows if "first_touch" in r.keys() and r["first_touch"]]
    usd = [r["usd_return_pct"] for r in hrows if r["usd_return_pct"] is not None]
    return {
        "n_observations": len(hrows),
        "hit_rate": hit_rate,
        "hit_rate_pct": hit_rate * 100,  # sablonda dogrudan gosterilen, payload'da da bulunan olceklenmis deger
        "median_excess_vs_index": median(r["excess_vs_index_pct"] for r in hrows),
        "median_excess_vs_deposit": median(r["excess_vs_deposit_pct"] for r in hrows),
        "median_usd_return": median(usd) if usd else None,
        "target_first_pct": (sum(t == "target" for t in touched) / len(touched) * 100) if touched else None,
        "stop_first_pct": (sum(t == "stop" for t in touched) / len(touched) * 100) if touched else None,
    }


def summarize_outcomes(as_of_date: str, lookback_months: int = 6) -> dict:
    """outcomes tablosunda ONCEDEN hesaplanmis satirlari okuyup tanimlayici
    metrikler uretir. Yeni bir hesap YAPMAZ (bkz. modul dosya-basi notu)."""
    cutoff = (datetime.strptime(as_of_date, "%Y-%m-%d") - timedelta(days=lookback_months * 30)).date().isoformat()
    rows = db.query(
        "SELECT * FROM outcomes WHERE evaluated_at >= ? AND evaluated_at <= ?",
        (cutoff, as_of_date),
    )
    per_horizon: dict[int, list] = {h: [] for h in HORIZONS_DAYS}
    per_group: dict[str, dict[int, list]] = {}
    for r in rows:
        if r["horizon_days"] in per_horizon:
            per_horizon[r["horizon_days"]].append(r)
            per_group.setdefault(_group_of(r), {}).setdefault(r["horizon_days"], []).append(r)

    summary = {h: (_describe(hrows) if hrows else None) for h, hrows in per_horizon.items()}
    by_group = {g: {h: _describe(hrows) for h, hrows in hz.items()} for g, hz in per_group.items()}

    return {
        "is_not_a_backtest": True,
        "independence_caveat": "T+5/T+20/T+60/T+180 ufuklari gunluk secilen adaylarda ortusur "
                                "(180 gunluk uzun vadeli tezler 20 gunluk kisa vadeli adaylarla "
                                "ayni donemde secilebilir); N gunluk takip N bagimsiz gozlem "
                                "anlamina gelmez. Her ufuk asagida AYRI gosterilir, tek bir "
                                "birlesik basari orani verilmez.",
        "by_horizon": summary,
        # actionable: STRONG/OPPORTUNITY; watchlist: izleme listesi; experimental:
        # kanitsiz kisa vade kovasi; legacy_unlabeled: etiket kaydedilmeden once yazilan tahminler.
        "by_group": by_group,
        "allowed_claims": ALLOWED_CLAIMS,
        "banned_claims": BANNED_CLAIMS,
    }
