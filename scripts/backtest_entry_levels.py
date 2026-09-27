#!/usr/bin/env python3
"""Giris/stop/hedef kurali backtest'i: ATR bandi (eski) vs destek/direnc (yeni).

    python scripts/backtest_entry_levels.py                  # varsayilan ~40 likit hisse
    python scripts/backtest_entry_levels.py --tickers THYAO,ASELS --days 500

Tasarim (ileriye bakis yok):
  - Ayni sinyal kumesi iki kurala da verilir: kapanis >= 0.98*SMA20 ve
    volume_ratio_20d >= 0.8 (core/backtest.py ile ayni setup), hisse basina
    tek acik pozisyon, sinyaller en az 5 bar arayla.
  - Seviyeler i gunune kadarki verilerle hesaplanir; pivotlar iki yanda k bar
    ister, son k bar kullanilmaz.
  - Tum fiyatlar duzeltilmis olcekte (bedelsiz/bolunme sahte kirilim uretmez).
  - Kademeli alim: %50 entry_low, %50 entry_high limit emir, 3 bar gecerli.
    Acilista emrin altinda acarsa acilistan dolar.
  - Cikis: stop / hedef / 20 bar. Ayni barda ikisi de dokunursa STOP varsayilir
    (kotumser). Gidis-donus maliyet --cost-pct (varsayilan %0.5).
Sinirlar:
  - Canli kaynak ~2 yil gecmis verir; tek rejim donemi.
  - Ayni hissedeki islemler zamansal olarak bagimli: islem bazli t-istatistigi
    iyimserdir. Hisse bazli ortalama farklarin t-istatistigi de raporlanir.
  - Evren bugunku likit hisselerdir (hayatta kalanlar yanliligi).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import levels, live_data  # noqa: E402
from core.targets import compute_dynamic_risk_levels, compute_short_term_target  # noqa: E402

DEFAULT_TICKERS = (
    "THYAO,ASELS,BIMAS,AKBNK,GARAN,YKBNK,ISCTR,KCHOL,SAHOL,EREGL,FROTO,TOASO,TUPRS,"
    "SISE,PGSUS,TCELL,TTKOM,ARCLK,PETKM,KRDMD,ENKAI,EKGYO,MGROS,SASA,HEKTS,ALARK,"
    "TAVHL,DOAS,OTKAR,VESTL,ULKER,AEFES,CCOLA,KOZAL,GUBRF,ODAS,TKFEN,SOKM,AKSEN,ASTOR"
).split(",")
HORIZON = 20
ORDER_VALID = 3
MIN_BARS = 150
SIGNAL_GAP = 5


def _adjust(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        k = (r.get("adj_close") or r["close"]) / r["close"] if r["close"] else 1.0
        out.append({
            **r,
            "open": r["open"] * k, "high": r["high"] * k, "low": r["low"] * k,
            "close": r["close"] * k, "adj_close": r["close"] * k,
            "atr20": (r.get("atr20") or 0.0) * k, "sma20": (r.get("sma20") or 0.0) * k,
        })
    return out


def _plans(hist: list[dict]) -> dict[str, dict]:
    last = hist[-1]
    p, atr, sma = last["close"], last["atr20"], last["sma20"]
    swing = min(r["low"] for r in hist[-20:])
    old_risk = compute_dynamic_risk_levels(p, atr, swing)
    old = {"entry_low": old_risk["entry_low"], "entry_high": old_risk["entry_high"],
           "stop": old_risk["stop_loss"], "target": p + 2.5 * atr, "method": "atr_band"}
    lv = levels.find_levels(hist, atr)
    plan = levels.plan_entry(p, atr, lv, breakout_zone=levels.recent_breakout(hist, lv, atr))
    st = compute_short_term_target(p, atr, sma, recent_swing_low=swing, level_plan=plan)
    new = {"entry_low": st["entry_low"], "entry_high": st["entry_high"],
           "stop": st["dynamic_stop_loss"], "target": st["target_price"], "method": st["entry_method"]}
    # bilesen ayristirmasi: hangi parca fark yaratiyor
    new_entry_old_target = {**new, "target": old["target"]}
    old_entry_new_target = {**old, "target": new["target"]}
    return {"old": old, "new": new, "new_entry_old_target": new_entry_old_target,
            "old_entry_new_target": old_entry_new_target}


def _simulate(bars: list[dict], i: int, plan: dict, cost_pct: float) -> dict | None:
    """i gunu kapanisindaki plani i+1..i+ORDER_VALID arasinda doldurur."""
    legs = [plan["entry_low"], plan["entry_high"]]
    fills: list[float] = []
    fill_bar = None
    for j in range(i + 1, min(len(bars), i + 1 + ORDER_VALID)):
        b = bars[j]
        for leg in list(legs):
            if b["low"] <= leg:
                fills.append(min(b["open"], leg))
                legs.remove(leg)
                fill_bar = j if fill_bar is None else fill_bar
        if not legs:
            break
    if not fills:
        return None
    entry = sum(fills) / len(fills)
    stop, target = plan["stop"], plan["target"]
    exit_price, reason, exit_bar = None, "horizon", None
    last_j = min(len(bars) - 1, fill_bar + HORIZON)
    for j in range(fill_bar, last_j + 1):
        b = bars[j]
        # doldugu barda stopa dokunus mumkun; hedef ancak ertesi bardan
        if b["low"] <= stop:
            exit_price, reason = min(b["open"], stop) if j > fill_bar else stop, "stop"
        elif j > fill_bar and target and b["high"] >= target:
            exit_price, reason = max(b["open"], target), "target"
        if exit_price is not None:
            exit_bar = j
            break
    if exit_price is None:
        exit_bar = last_j
        exit_price = bars[last_j]["close"]
    if exit_bar - fill_bar < 1 and reason == "horizon":
        return None  # veri sonu: islem kapanmadi
    ret = (exit_price / entry - 1.0) * 100.0 - cost_pct
    risk = (entry - stop) / entry * 100.0 if entry > stop else float("nan")
    return {"ret": ret, "reason": reason, "r_mult": ret / risk if risk and risk > 0 else float("nan"),
            "legs_filled": len(fills), "risk_pct": risk}


def _summary(trades: list[dict], n_signals: int) -> dict:
    rets = [t["ret"] for t in trades]
    if not rets:
        return {"signals": n_signals, "trades": 0}
    sd = statistics.pstdev(rets) if len(rets) > 1 else 0.0
    rm = [t["r_mult"] for t in trades if t["r_mult"] == t["r_mult"]]
    return {
        "signals": n_signals,
        "trades": len(rets),
        "fill_rate_pct": round(100 * len(rets) / n_signals, 1),
        "mean_ret_pct": round(statistics.mean(rets), 3),
        "median_ret_pct": round(statistics.median(rets), 3),
        "hit_rate_pct": round(100 * sum(r > 0 for r in rets) / len(rets), 1),
        "stop_rate_pct": round(100 * sum(t["reason"] == "stop" for t in trades) / len(rets), 1),
        "target_rate_pct": round(100 * sum(t["reason"] == "target" for t in trades) / len(rets), 1),
        "mean_risk_pct": round(statistics.mean(t["risk_pct"] for t in trades if t["risk_pct"] == t["risk_pct"]), 2),
        "mean_R": round(statistics.mean(rm), 3) if rm else None,
        "per_signal_ret_pct": round(sum(rets) / n_signals, 3),
        "t_stat_trade": round(statistics.mean(rets) / (sd / math.sqrt(len(rets))), 2) if sd else None,
    }


def run(tickers: list[str], as_of: str, days: int, cost_pct: float) -> dict:
    variants = ("old", "new", "new_entry_old_target", "old_entry_new_target")
    per_variant: dict[str, list[dict]] = {v: [] for v in variants}
    per_ticker_diff: dict[str, list[float]] = {v: [] for v in variants[1:]}
    method_counts: dict[str, int] = {}
    n_signals = 0
    failed = []
    for t in tickers:
        try:
            raw = live_data.live_prices(t, as_of, days=days)
        except Exception as exc:  # veri hatasi tum kosuyu durdurmaz
            failed.append(f"{t}: {str(exc)[:60]}")
            continue
        bars = _adjust([r for r in raw if r.get("atr20") and r.get("sma20")])
        if len(bars) < MIN_BARS + HORIZON:
            failed.append(f"{t}: {len(bars)} bar")
            continue
        t_rets: dict[str, list[float]] = {v: [] for v in variants}
        i = MIN_BARS
        while i < len(bars) - 2:
            b = bars[i]
            if b["close"] >= 0.98 * b["sma20"] and (b.get("volume_ratio_20d") or 0) >= 0.8:
                plans = _plans(bars[:i + 1])
                m = plans["new"]["method"]
                method_counts[m] = method_counts.get(m, 0) + 1
                n_signals += 1
                for v in variants:
                    tr = _simulate(bars, i, plans[v], cost_pct)
                    if tr:
                        per_variant[v].append(tr)
                        t_rets[v].append(tr["ret"])
                i += SIGNAL_GAP
            else:
                i += 1
        for v in variants[1:]:
            if t_rets["old"] and t_rets[v]:
                per_ticker_diff[v].append(statistics.mean(t_rets[v]) - statistics.mean(t_rets["old"]))

    def _diff_stats(d: list[float]) -> dict:
        if len(d) < 3:
            return {}
        sd = statistics.stdev(d)
        return {"mean_diff_pct": round(statistics.mean(d), 3),
                "t": round(statistics.mean(d) / (sd / math.sqrt(len(d))), 2) if sd else None,
                "tickers_better_pct": round(100 * sum(x > 0 for x in d) / len(d), 1)}

    return {
        "as_of": as_of,
        "tickers": len(tickers) - len(failed),
        "failed": failed,
        "cost_pct_round_trip": cost_pct,
        "new_method_counts": method_counts,
        "variants": {v: _summary(per_variant[v], n_signals) for v in variants},
        "per_ticker_vs_old": {v: _diff_stats(per_ticker_diff[v]) for v in variants[1:]},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tickers", default=",".join(DEFAULT_TICKERS))
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--days", type=int, default=500)
    ap.add_argument("--cost-pct", type=float, default=0.5)
    args = ap.parse_args()
    res = run(args.tickers.split(","), args.date, args.days, args.cost_pct)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    out = ROOT / "data" / "reports" / f"backtest_entry_levels_{args.date}.json"
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"-> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
