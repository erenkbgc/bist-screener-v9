#!/usr/bin/env python3
"""Ileriye donuk kaydin degerlendirmesi (config/live_rule.json -> forward_record).

Kayitli kararlar YENIDEN SECILMEZ; yalnizca gerceklesen fiyatlarla, on-kayitli
portfoy backtest'iyle ayni simulatorle (ertesi gun kapanis, 1M TL, base maliyet,
nakit politika faizi kazanir) fiyatlanir. Kural surumu degisince yeni seri baslar.

Takvim ayi bazinda: her ay bir donem. Basarili karari olmayan ayda (status
"no_decision" veya hic kayit yok) islem yapilmaz, pozisyonlar tasinir ve o ay
ayri bir donem olarak yazilir; boylece 12 x aylik ortalama yilliklastirmasi ve
NW t her zaman aylik gozlemlere dayanir. Yalnizca tamamlanmis donemler sayilir.

Ana sonuc on-kayitla ayni delist varsayimini (h = 0) kullanir; on-kayitli
duyarlilik h = 0.5 (islemden kalkan pozisyonun yarisi kaybedilir) yaninda
raporlanir. Benchmark'lar: EW evren (maliyetsiz), XU100 fiyat ve BIST 100
toplam getiri (XU100_CFNNTLTL; total_return_benchmarks_preregistration.md).

Fiyatlar ve endeksler kosu aninda borsapy'den cekilir (arastirma onbellegi
data/research/raw guncellenmez); politika faizi macro_monthly.parquet'ten:

    python scripts/research_macro_drivers.py  # data/research/macro_monthly.parquet (politika faizi)
    python scripts/forward_record_report.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import factor_backtest as fb  # noqa: E402
from core import forward_record as fr  # noqa: E402
from core import portfolio_backtest as pb  # noqa: E402

CAPITAL_TL = 1e6


DELIST_HAIRCUT_SENSITIVITY = 0.5  # portfolio_backtest_preregistration.md


def series_by_version(decisions: list[dict]) -> list[list[dict]]:
    """Ardisik ayni surumlu basarili kararlar bir seri; surum degisince yeni seri."""
    out: list[list[dict]] = []
    for d in sorted(filter(fr.is_ok, decisions), key=lambda d: d["rebalance_date"]):
        if out and out[-1][-1]["rule_version"] == d["rule_version"]:
            out[-1].append(d)
        else:
            out.append([d])
    return out


def missed_months(decisions: list[dict]) -> list[str]:
    """Kaydin ilk ve son ayi arasinda basarili karari olmayan aylar."""
    if not decisions:
        return []
    months = sorted({d["rebalance_date"][:7] for d in decisions})
    ok = {d["rebalance_date"][:7] for d in decisions if fr.is_ok(d)}
    span = pd.period_range(months[0], months[-1], freq="M").strftime("%Y-%m")
    return [m for m in span if m not in ok]


def schedule(series: list[dict], end: pd.Timestamp,
             stop: pd.Timestamp | None = None) -> list[tuple[pd.Timestamp, dict | None]]:
    """Takvim ayi basina bir capa: ayin basarili karari varsa onun tarihi, yoksa ayin
    ilk gunu ve None (tasima). stop: sonraki surumun ilk karari (bu seriyi kapatir)."""
    by_month = {d["rebalance_date"][:7]: d for d in series}
    last = (stop - pd.Timedelta(days=1)) if stop is not None else end
    out = []
    for m in pd.period_range(series[0]["rebalance_date"][:7], last.strftime("%Y-%m"), freq="M"):
        rec = by_month.get(m.strftime("%Y-%m"))
        out.append((pd.Timestamp(rec["rebalance_date"]), rec) if rec else (m.start_time, None))
    if stop is not None:
        out.append((stop, None))
    return [(t, r) for t, r in out if t <= end]


def evaluate(series: list[dict], frames: dict[str, pd.DataFrame], xu: pd.Series,
             rf_daily: pd.Series | None = None, costs: pb.Costs = pb.Costs(),
             haircut: float = 0.0, tr: pd.Series | None = None,
             stop: pd.Timestamp | None = None) -> pd.DataFrame:
    """frames[ticker]: gunluk Close, Open, adv, sigma (duzeltilmis); xu: XU100 kapanisi (takvim);
    rf_daily: nakdin gunluk getirisi (pb.policy_rf_daily), yoksa 0; tr: BIST 100 toplam getiri."""
    days = xu.index
    sched, seen = [], set()
    for t, rec in schedule(series, days[-1], stop):
        d0 = days[days.searchsorted(t, side="right") - 1]
        if d0 in seen:  # ayni kapanisa dusen tasima capasi bos donem uretir
            continue
        seen.add(d0)
        sched.append((t, rec))
    months = [t for t, _ in sched]
    d0_of = {t: days[days.searchsorted(t, side="right") - 1] for t in months}
    held, cur = {}, None
    for t, rec in sched:
        cur = rec or cur
        held[t] = cur
    targets = {t: (rec["holdings"] if rec else None) for t, rec in sched}
    tickers = sorted({tk for d in series for tk in d["holdings"] + d["universe"]} & set(frames))
    mat = {k: pd.DataFrame({tk: frames[tk][c].reindex(days) for tk in tickers}, index=days, dtype=float)
           for k, c in (("close", "Close"), ("open", "Open"), ("adv", "adv"), ("sigma", "sigma"))}
    mat["adv"], mat["sigma"] = mat["adv"].ffill(), mat["sigma"].ffill()
    universe_liq = {t: np.sort(mat["adv"].loc[d0_of[t], [tk for tk in held[t]["universe"] if tk in tickers]]
                               .dropna().to_numpy()) for t in months}
    mkt = pb.Market(close=mat["close"], open=mat["open"], adv=mat["adv"], sigma=mat["sigma"],
                    rf_daily=pd.Series(0.0, index=days) if rf_daily is None else rf_daily.reindex(days))
    p = pb.simulate(targets, months, d0_of, mkt, universe_liq, {t: CAPITAL_TL for t in months},
                    costs=costs, haircut=haircut)
    if p.empty:
        return p
    close = mat["close"].ffill()
    trs = tr.reindex(days).ffill() if tr is not None else None
    nxt = {months[k]: months[k + 1] for k in range(len(months) - 1)}
    bench, xu_ret, tr_ret = [], [], []
    for t in p["date"]:
        a, b = d0_of[t], d0_of[nxt[t]]
        u = [tk for tk in held[t]["universe"] if tk in tickers]
        r = (close.loc[b, u] / close.loc[a, u] - 1).dropna()
        bench.append(float(r.mean()) if len(r) else np.nan)
        xu_ret.append(float(xu.loc[b] / xu.loc[a] - 1))
        tr_ret.append(float(trs.loc[b] / trs.loc[a] - 1) if trs is not None else np.nan)
    p["decision"] = p["date"].map(lambda t: targets[t] is not None)
    p["bench"], p["xu"], p["xu_tr"] = bench, xu_ret, tr_ret
    p["active"], p["active_xu"], p["active_xu_tr"] = p["port"] - p["bench"], p["port"] - p["xu"], p["port"] - p["xu_tr"]
    return p


def summarize(p: pd.DataFrame) -> dict:
    """Her satir bir takvim ayi; yilliklastirma 12 x aylik ortalama."""
    if p.empty:
        return {"periods": 0}
    out = {"periods": len(p), "periods_carried_without_decision": int((~p["decision"]).sum()),
           "first": str(p["date"].iloc[0].date()), "last": str(p["date"].iloc[-1].date()),
           "cum_return_pct": round(100 * float((1 + p["port"]).prod() - 1), 2),
           "cum_ew_universe_pct": round(100 * float((1 + p["bench"]).prod() - 1), 2),
           "cum_xu100_pct": round(100 * float((1 + p["xu"]).prod() - 1), 2),
           "cum_xu100_tr_pct": round(100 * float((1 + p["xu_tr"]).prod() - 1), 2) if p["xu_tr"].notna().all() else None,
           "cost_total_pct": round(100 * float(p["cost"].sum()), 2),
           "delist_events": int(p.attrs.get("delist_events", 0))}
    if len(p) >= 12:  # anlamli t icin en az bir yil
        for key, col in (("active_univ", "active"), ("active_xu100", "active_xu"), ("active_xu100_tr", "active_xu_tr")):
            if p[col].notna().all():
                m, t, _ = fb.newey_west_t(p[col], 6)
                out[f"{key}_ann_pct"], out[f"{key}_t"] = round(1200 * m, 2), round(t, 2)
    return out


def _index_close(code: str) -> pd.Series:
    import borsapy as bp
    h = bp.Index(code).history(period="5y")
    idx = pd.to_datetime(h.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return pd.Series(h["Close"].astype(float).to_numpy(), index=idx.normalize()).sort_index()


def _daily_live(ticker: str) -> pd.DataFrame | None:
    """Guncel gunluk fiyat (borsapy), arastirma onbellegiyle ayni bicimde."""
    import borsapy as bp
    from research_portfolio_backtest import daily_frame
    try:
        t = bp.Ticker(ticker)
        return daily_frame(t.history(period="2y", adjust=True), t.history(period="2y", adjust=False))
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    decisions = fr.load_decisions()
    xu = _index_close("XU100")
    tr = _index_close("XU100_CFNNTLTL")
    macro = pd.read_parquet(ROOT / "data" / "research" / "macro_monthly.parquet")
    macro.index = pd.to_datetime(macro.index).to_period("M")
    rf_daily = pb.policy_rf_daily(macro["policy"], xu.index)
    result = {"as_of": date.today().isoformat(), "rule": fr.live_rule()["version"],
              "last_price_day": str(xu.index[-1].date()),
              "policy_rate_last_month": str(macro["policy"].dropna().index[-1]),
              "no_decision_records": sum(not fr.is_ok(d) for d in decisions),
              "months_without_decision": missed_months(decisions), "series": []}
    all_series = series_by_version(decisions)
    for k, s in enumerate(all_series):
        stop = pd.Timestamp(all_series[k + 1][0]["rebalance_date"]) if k + 1 < len(all_series) else None
        tickers = sorted({tk for d in s for tk in d["holdings"] + d["universe"]})
        frames = {tk: f for tk in tickers if (f := _daily_live(tk)) is not None}
        main_p = evaluate(s, frames, xu, rf_daily, tr=tr, stop=stop)
        sens = summarize(evaluate(s, frames, xu, rf_daily, haircut=DELIST_HAIRCUT_SENSITIVITY, tr=tr, stop=stop))
        result["series"].append({"rule_version": s[0]["rule_version"], "decisions": len(s),
                                 "tickers_without_prices": sorted(set(tickers) - set(frames)), **summarize(main_p),
                                 "haircut_0_5": {k2: v for k2, v in sens.items() if k2 not in ("first", "last")}})
    out = ROOT / "data" / "reports" / f"forward_record_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not decisions:
        print("Henuz kayitli karar yok (ilk kayit 2026-11 dengelemesinde).")


if __name__ == "__main__":
    main()
