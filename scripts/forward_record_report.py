#!/usr/bin/env python3
"""Ileriye donuk kaydin degerlendirmesi (config/live_rule.json -> forward_record).

Kayitli kararlar YENIDEN SECILMEZ; yalnizca gerceklesen fiyatlarla, on-kayitli
portfoy backtest'iyle ayni simulatorle (ertesi gun kapanis, 1M TL, base maliyet,
nakit politika faizi kazanir) fiyatlanir. Yalnizca tamamlanmis donemler (ardisik
iki karar arasi) sayilir. Kural surumu degisince yeni seri baslar.

Ana sonuc on-kayitla ayni delist varsayimini (h = 0) kullanir; on-kayitli
duyarlilik h = 0.5 (islemden kalkan pozisyonun yarisi kaybedilir) yaninda
raporlanir. Karar uretilemeyen kayitlar (status "no_decision") fiyatlanmaz;
sayilari ve hic basarili karari olmayan aylar raporda gorunur.

    python scripts/research_macro_drivers.py  # data/research/macro_monthly.parquet (politika faizi)

    python scripts/build_fx_panel.py          # XU100/USDTRY gunluk
    python scripts/build_pit_panel.py         # data/research/raw/*.pkl gunluk fiyat onbellegi
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


def evaluate(series: list[dict], frames: dict[str, pd.DataFrame], xu: pd.Series,
             rf_daily: pd.Series | None = None, costs: pb.Costs = pb.Costs(),
             haircut: float = 0.0) -> pd.DataFrame:
    """frames[ticker]: gunluk Close, Open, adv, sigma (duzeltilmis); xu: XU100 kapanisi (takvim);
    rf_daily: nakdin gunluk getirisi (pb.policy_rf_daily). Yoksa 0."""
    days = xu.index
    months = [pd.Timestamp(d["rebalance_date"]) for d in series]
    d0_of = {t: days[days.searchsorted(t, side="right") - 1] for t in months}
    targets = {t: d["holdings"] for t, d in zip(months, series)}
    tickers = sorted({tk for d in series for tk in d["holdings"] + d["universe"]} & set(frames))
    mat = {k: pd.DataFrame({tk: frames[tk][c].reindex(days) for tk in tickers}, index=days, dtype=float)
           for k, c in (("close", "Close"), ("open", "Open"), ("adv", "adv"), ("sigma", "sigma"))}
    mat["adv"], mat["sigma"] = mat["adv"].ffill(), mat["sigma"].ffill()
    universe_liq = {t: np.sort(mat["adv"].loc[d0_of[t], [tk for tk in d["universe"] if tk in tickers]]
                               .dropna().to_numpy()) for t, d in zip(months, series)}
    mkt = pb.Market(close=mat["close"], open=mat["open"], adv=mat["adv"], sigma=mat["sigma"],
                    rf_daily=pd.Series(0.0, index=days) if rf_daily is None else rf_daily.reindex(days))
    p = pb.simulate(targets, months, d0_of, mkt, universe_liq, {t: CAPITAL_TL for t in months},
                    costs=costs, haircut=haircut)
    if p.empty:
        return p
    close = mat["close"].ffill()
    nxt = {months[k]: months[k + 1] for k in range(len(months) - 1)}
    bench, xu_ret = [], []
    for t in p["date"]:
        rec = series[months.index(t)]
        a, b = d0_of[t], d0_of[nxt[t]]
        u = [tk for tk in rec["universe"] if tk in tickers]
        r = (close.loc[b, u] / close.loc[a, u] - 1).dropna()
        bench.append(float(r.mean()) if len(r) else np.nan)
        xu_ret.append(float(xu.loc[b] / xu.loc[a] - 1))
    p["bench"], p["xu"] = bench, xu_ret
    p["active"], p["active_xu"] = p["port"] - p["bench"], p["port"] - p["xu"]
    return p


def summarize(p: pd.DataFrame) -> dict:
    if p.empty:
        return {"periods": 0}
    out = {"periods": len(p), "first": str(p["date"].iloc[0].date()), "last": str(p["date"].iloc[-1].date()),
           "cum_return_pct": round(100 * float((1 + p["port"]).prod() - 1), 2),
           "cum_ew_universe_pct": round(100 * float((1 + p["bench"]).prod() - 1), 2),
           "cum_xu100_pct": round(100 * float((1 + p["xu"]).prod() - 1), 2),
           "cost_total_pct": round(100 * float(p["cost"].sum()), 2),
           "delist_events": int(p.attrs.get("delist_events", 0))}
    if len(p) >= 12:  # anlamli t icin en az bir yil
        for key, col in (("active_univ", "active"), ("active_xu100", "active_xu")):
            m, t, _ = fb.newey_west_t(p[col], 6)
            out[f"{key}_ann_pct"], out[f"{key}_t"] = round(1200 * m, 2), round(t, 2)
    return out


def main() -> None:
    from research_portfolio_backtest import load_daily  # arastirma onbellegi (data/research/raw)

    decisions = fr.load_decisions()
    fx = pd.read_parquet(ROOT / "data" / "research" / "fx.parquet")
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    xu = fx.set_index("date").sort_index()["xu100"]
    macro = pd.read_parquet(ROOT / "data" / "research" / "macro_monthly.parquet")
    macro.index = pd.to_datetime(macro.index).to_period("M")
    rf_daily = pb.policy_rf_daily(macro["policy"], xu.index)
    result = {"as_of": date.today().isoformat(), "rule": fr.live_rule()["version"],
              "policy_rate_last_month": str(macro["policy"].dropna().index[-1]),
              "no_decision_records": sum(not fr.is_ok(d) for d in decisions),
              "months_without_decision": missed_months(decisions), "series": []}
    for s in series_by_version(decisions):
        tickers = sorted({tk for d in s for tk in d["holdings"] + d["universe"]})
        frames = {tk: f for tk in tickers if (f := load_daily(tk)) is not None}
        main_p = evaluate(s, frames, xu, rf_daily)
        sens = summarize(evaluate(s, frames, xu, rf_daily, haircut=DELIST_HAIRCUT_SENSITIVITY))
        result["series"].append({"rule_version": s[0]["rule_version"], "decisions": len(s), **summarize(main_p),
                                 "haircut_0_5": {k: v for k, v in sens.items() if k not in ("first", "last")}})
    out = ROOT / "data" / "reports" / f"forward_record_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not decisions:
        print("Henuz kayitli karar yok (ilk kayit 2026-11 dengelemesinde).")


if __name__ == "__main__":
    main()
