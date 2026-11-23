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
raporlanir. Benchmark'lar: EW net (birincil: ayni simulator, sermaye, islem
maliyetleri, islem zamanlari ve nakit faiziyle isletilen esit agirlikli evren),
EW gross (tamamlayici: maliyetsiz evren ortalamasi), XU100 fiyat ve BIST 100
toplam getiri (XU100_CFNNTLTL; total_return_benchmarks_preregistration.md).

Fiyatlar kosu aninda borsapy'den, ilk karardan bugune cekilir (arastirma onbellegi
data/research/raw guncellenmez). Saglayici bir hisseyi artik dondurmezse (delist,
kod degisikligi) canli kosularin biriktirdigi kalici depo (core/forward_prices,
data/forward_record/prices/) kullanilir; ikisi de yoksa tutulan hisse muhafazakar
-%100 sayilir ve raporda price_sources altinda listelenir. Politika faizi
macro_monthly.parquet'ten:

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
from core import forward_prices  # noqa: E402
from core import portfolio_backtest as pb  # noqa: E402

CAPITAL_TL = 1e6
MIN_BENCH_COVERAGE = 0.95  # EW evren karsilastirmasi icin gozlemlenebilir getiri payi alt siniri
MAX_BENCH_PRICE_AGE = 0    # Donem basi/sonu fiyati icin izin verilen azami fiyat yasi (islem gunu)


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
             stop: pd.Timestamp | None = None,
             max_price_age: int = MAX_BENCH_PRICE_AGE) -> pd.DataFrame:
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
    ew_targets = {t: (rec["universe"] if rec else None) for t, rec in sched}
    tickers = sorted({tk for d in series for tk in d["holdings"] + d["universe"]} & set(frames))
    mat = {k: pd.DataFrame({tk: frames[tk][c].reindex(days) for tk in tickers}, index=days, dtype=float)
           for k, c in (("close", "Close"), ("open", "Open"), ("adv", "adv"), ("sigma", "sigma"))}
    mat["adv"], mat["sigma"] = mat["adv"].ffill(), mat["sigma"].ffill()
    universe_liq = {t: np.sort(mat["adv"].loc[d0_of[t], [tk for tk in held[t]["universe"] if tk in tickers]]
                               .dropna().to_numpy()) for t in months}
    mkt = pb.Market(close=mat["close"], open=mat["open"], adv=mat["adv"], sigma=mat["sigma"],
                    rf_daily=pd.Series(0.0, index=days) if rf_daily is None else rf_daily.reindex(days))
    cap = {t: CAPITAL_TL for t in months}
    p = pb.simulate(targets, months, d0_of, mkt, universe_liq, cap, costs=costs, haircut=haircut)
    if p.empty:
        return p
    ew = pb.simulate(ew_targets, months, d0_of, mkt, universe_liq, cap,
                     costs=costs, haircut=haircut).set_index("date")
    raw_close = mat["close"]
    close_ffill = raw_close.ffill()
    idx_grid = np.arange(len(days), dtype=float)[:, None]
    last_obs = pd.DataFrame(np.where(raw_close.notna(), idx_grid, np.nan),
                            index=days, columns=raw_close.columns).ffill()
    price_age = pd.DataFrame(idx_grid - last_obs.to_numpy(), index=days, columns=raw_close.columns)
    trs = tr.reindex(days).ffill() if tr is not None else None
    nxt = {months[k]: months[k + 1] for k in range(len(months) - 1)}
    bench_net, bench_gross, bench_net_cost, xu_ret, tr_ret, coverage, max_ages = [], [], [], [], [], [], []
    for t in p["date"]:
        a, b = d0_of[t], d0_of[nxt[t]]
        fill_d = days[min(days.get_loc(a) + 1, len(days) - 1)]
        u = [tk for tk in held[t]["universe"] if tk in tickers]
        # Kapsama: doldurulmus seriden degil, donem basi/sonu ve (karar aylarinda) islem gunu
        # fiyatlarinin gercekten gozlemlenebilir olmasindan (fiyat yasi <= max_price_age) hesaplanir
        if u:
            ok_u = ((price_age.loc[a, u] <= max_price_age)
                    & (price_age.loc[b, u] <= max_price_age)
                    & (last_obs.loc[b, u] > last_obs.loc[a, u]))
            if targets[t] is not None:
                ok_u = ok_u & (price_age.loc[fill_d, u] <= max_price_age)
            r = (close_ffill.loc[b, u] / close_ffill.loc[a, u] - 1)[ok_u].dropna()
            age_pts = [a, fill_d, b] if targets[t] is not None else [a, b]
            ages = price_age.loc[age_pts, u].to_numpy(dtype=float)
            max_age = int(np.nanmax(ages)) if np.isfinite(ages).any() else 0
        else:
            r = pd.Series(dtype=float)
            max_age = 0
        cov = len(r) / max(1, len(held[t]["universe"]))
        coverage.append(cov)
        max_ages.append(max_age)
        valid_bench = bool(len(r) and cov >= MIN_BENCH_COVERAGE)
        bench_gross.append(float(r.mean()) if valid_bench else np.nan)
        bench_net.append(float(ew.loc[t, "port"]) if valid_bench and t in ew.index else np.nan)
        bench_net_cost.append(float(ew.loc[t, "cost"]) if t in ew.index else 0.0)
        xu_ret.append(float(xu.loc[b] / xu.loc[a] - 1))
        tr_ret.append(float(trs.loc[b] / trs.loc[a] - 1) if trs is not None else np.nan)
    p["decision"] = p["date"].map(lambda t: targets[t] is not None)
    p["bench_net"], p["bench_gross"], p["bench"] = bench_net, bench_gross, bench_gross
    p["bench_net_cost"] = bench_net_cost
    p["xu"], p["xu_tr"], p["bench_coverage"], p["bench_max_price_age"] = xu_ret, tr_ret, coverage, max_ages
    p["active_net"] = p["port"] - p["bench_net"]
    p["active_gross"] = p["port"] - p["bench_gross"]
    p["active"] = p["active_net"]
    p["active_xu"], p["active_xu_tr"] = p["port"] - p["xu"], p["port"] - p["xu_tr"]
    return p


def expectation_check(active: pd.Series, exp: dict | None) -> dict | None:
    """Gerceklesen aylik aktif getirilerin toplami, backtest beklentisinin bandinda mi?

    exp (config/live_rule.json -> expectation): yillik ortalama, NW t ve ay sayisi.
    sigma_eff = ortalama x sqrt(ay) / t, NW standart hatasindan geri cozulen aylik
    etkin oynaklik. z < -band_z: kayit backtest ile tutarsiz."""
    a = active.dropna()
    if exp is None or a.empty:
        return None
    mu = exp["ann_pct"] / 1200.0
    sigma = mu * np.sqrt(exp["months"]) / exp["nw_t"]
    n = len(a)
    z = (float(a.sum()) - n * mu) / (sigma * np.sqrt(n))
    return {"metric": exp["metric"], "months": n, "realized_sum_pct": round(100 * float(a.sum()), 2),
            "expected_sum_pct": round(100 * n * mu, 2), "band_pct": round(100 * exp["band_z"] * sigma * np.sqrt(n), 2),
            "z": round(z, 2), "inconsistent_with_backtest": bool(z < -exp["band_z"])}


def summarize(p: pd.DataFrame) -> dict:
    """Her satir bir takvim ayi; yilliklastirma 12 x aylik ortalama.
    EW net (ayni simulator ve maliyet modeli) birincil, EW gross (maliyetsiz) tamamlayici."""
    if p.empty:
        return {"periods": 0}
    out = {"periods": len(p), "periods_carried_without_decision": int((~p["decision"]).sum()),
           "first": str(p["date"].iloc[0].date()), "last": str(p["date"].iloc[-1].date()),
           "cum_return_pct": round(100 * float((1 + p["port"]).prod() - 1), 2),
           "cum_ew_universe_net_pct": round(100 * float((1 + p["bench_net"]).prod() - 1), 2) if p["bench_net"].notna().all() else None,
           "cum_ew_universe_gross_pct": round(100 * float((1 + p["bench_gross"]).prod() - 1), 2) if p["bench_gross"].notna().all() else None,
           "cum_ew_universe_pct": round(100 * float((1 + p["bench_net"]).prod() - 1), 2) if p["bench_net"].notna().all() else None,
           "ew_universe_net_cost_total_pct": round(100 * float(p["bench_net_cost"].sum()), 2),
           "ew_universe_min_coverage_pct": round(100 * float(p["bench_coverage"].min()), 1),
           "ew_universe_max_price_age_days": int(p["bench_max_price_age"].max()),
           "ew_universe_invalid_periods": int(p["bench_net"].isna().sum()),
           "cum_xu100_pct": round(100 * float((1 + p["xu"]).prod() - 1), 2),
           "cum_xu100_tr_pct": round(100 * float((1 + p["xu_tr"]).prod() - 1), 2) if p["xu_tr"].notna().all() else None,
           "cost_total_pct": round(100 * float(p["cost"].sum()), 2),
           "delist_events": int(p.attrs.get("delist_events", 0)),
           "expectation_check": expectation_check(p["active_gross"], fr.live_rule().get("expectation"))}
    if len(p) >= 12:  # anlamli t icin en az bir yil
        months_idx = p["date"].dt.to_period("M")
        for key, col in (("active_univ", "active_net"), ("active_univ_net", "active_net"),
                         ("active_univ_gross", "active_gross"),
                         ("active_xu100", "active_xu"), ("active_xu100_tr", "active_xu_tr")):
            s = pd.Series(p[col].to_numpy(dtype=float), index=months_idx)
            valid = s.dropna()
            if len(valid) >= 12:
                first_m, last_m = valid.index[0], valid.index[-1]
                span_s = s.loc[first_m:last_m].reindex(pd.period_range(first_m, last_m, freq="M"))
                m, t, n = fb.newey_west_t(span_s, 6)
                out[f"{key}_ann_pct"] = round(1200 * m, 2)
                out[f"{key}_t"] = round(t, 2)
                out[f"{key}_periods"] = n
                out[f"{key}_missing_periods"] = int(span_s.isna().sum())
                out[f"{key}_span"] = [str(first_m), str(last_m)]
    return out


def _index_close(code: str, start: pd.Timestamp) -> pd.Series:
    """Endeks kapanisi start'tan bugune (kayit buyudukce pencere de buyur)."""
    import borsapy as bp
    h = bp.Index(code).history(start=start.strftime("%Y-%m-%d"))
    idx = pd.to_datetime(h.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return pd.Series(h["Close"].astype(float).to_numpy(), index=idx.normalize()).sort_index()


LOSS_PRICE = 1e-9  # fiyat gecmisi hic bulunamayan tutulan hisse: muhafazakar -%100


def _daily_live(ticker: str, start: pd.Timestamp) -> pd.DataFrame | None:
    """Saglayicidan start'tan bugune gunluk fiyat (borsapy), simulator bicimde."""
    import borsapy as bp
    from research_portfolio_backtest import daily_frame
    try:
        t = bp.Ticker(ticker)
        s = start.strftime("%Y-%m-%d")
        return daily_frame(t.history(start=s, adjust=True), t.history(start=s, adjust=False))
    except Exception:  # noqa: BLE001
        return None


def _daily_stored(ticker: str) -> pd.DataFrame | None:
    """Kalici depodan (core/forward_prices) simulator bicimi."""
    from research_portfolio_backtest import daily_frame
    df = forward_prices.load(ticker)
    if df is None:
        return None
    d = df.dropna(subset=["close", "adj_close"]).set_index("date").sort_index()
    k = d["adj_close"] / d["close"]
    return daily_frame(pd.DataFrame({"Open": d["open"] * k, "Close": d["adj_close"]}),
                       pd.DataFrame({"Close": d["close"], "Volume": d["volume"]}))


def price_frames(series: list[dict], days: pd.DatetimeIndex,
                 live=_daily_live, stored=_daily_stored) -> tuple[dict[str, pd.DataFrame], dict]:
    """Saglayici (kararin baslangicindan bugune) once; ilk karar gununu kapsamiyorsa kalici depo.
    Ikisi de yoksa: tutulan hisse ilk tutuldugu kararin dolum gunu sonrasinda muhafazakar
    -%100 (LOSS_PRICE); yalnizca evrende olan hisse disarida kalir. Hepsi raporlanir."""
    first = pd.Timestamp(series[0]["rebalance_date"])
    start = first - pd.Timedelta(days=120)  # 60 islem gunluk ADV penceresi
    tickers = sorted({tk for d in series for tk in d["holdings"] + d["universe"]})
    frames, src = {}, {"provider": [], "store": [], "conservative_loss": [], "universe_missing": []}
    for tk in tickers:
        f = live(tk, start)
        if f is not None and not f.empty and f.index.min() <= first:
            frames[tk] = f
            src["provider"].append(tk)
            continue
        f = stored(tk)
        if f is not None and not f.empty:
            frames[tk] = f
            src["store"].append(tk)
            continue
        held = [pd.Timestamp(d["rebalance_date"]) for d in series if tk in d["holdings"]]
        if not held:
            src["universe_missing"].append(tk)
            continue
        d0 = days[days.searchsorted(held[0], side="right") - 1]
        fill = days[min(days.get_loc(d0) + 1, len(days) - 1)]
        px = pd.Series(1.0, index=days).where(days <= fill, LOSS_PRICE)
        frames[tk] = pd.DataFrame({"Open": px, "Close": px, "adv": 1e15, "sigma": 0.0})
        src["conservative_loss"].append(tk)
    return frames, src


def main() -> None:
    decisions = fr.load_decisions()
    ok = sorted(d["rebalance_date"] for d in decisions if fr.is_ok(d))
    first = pd.Timestamp(ok[0]) if ok else pd.Timestamp(date.today())
    start = first - pd.Timedelta(days=120)
    xu = _index_close("XU100", start)
    tr = _index_close("XU100_CFNNTLTL", start)
    # Kapsama: takvim (XU100) ilk karari kapsamali; toplam getiri endeksi kapsamiyorsa kullanilmaz
    if xu.index.min() > first:
        raise SystemExit(f"XU100 gecmisi {xu.index.min().date()} basliyor, ilk karar {first.date()}: takvim eksik")
    tr_ok = not tr.empty and tr.index.min() <= first
    tr = tr if tr_ok else None
    macro = pd.read_parquet(ROOT / "data" / "research" / "macro_monthly.parquet")
    macro.index = pd.to_datetime(macro.index).to_period("M")
    rf_daily = pb.policy_rf_daily(macro["policy"], xu.index)
    result = {"as_of": date.today().isoformat(), "rule": fr.live_rule()["version"],
              "last_price_day": str(xu.index[-1].date()),
              "index_coverage": {"xu100_from": str(xu.index.min().date()),
                                 "xu100_tr_covers_first_decision": tr_ok},
              "policy_rate_last_month": str(macro["policy"].dropna().index[-1]),
              "no_decision_records": sum(not fr.is_ok(d) for d in decisions),
              "months_without_decision": missed_months(decisions), "series": []}
    all_series = series_by_version(decisions)
    for k, s in enumerate(all_series):
        stop = pd.Timestamp(all_series[k + 1][0]["rebalance_date"]) if k + 1 < len(all_series) else None
        frames, src = price_frames(s, xu.index)
        main_p = evaluate(s, frames, xu, rf_daily, tr=tr, stop=stop)
        sens = summarize(evaluate(s, frames, xu, rf_daily, haircut=DELIST_HAIRCUT_SENSITIVITY, tr=tr, stop=stop))
        result["series"].append({"rule_version": s[0]["rule_version"], "decisions": len(s),
                                 "price_sources": src, **summarize(main_p),
                                 "haircut_0_5": {k2: v for k2, v in sens.items() if k2 not in ("first", "last")}})
    out = ROOT / "data" / "reports" / f"forward_record_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not decisions:
        print("Henuz kayitli karar yok (ilk kayit 2026-11 dengelemesinde).")


if __name__ == "__main__":
    main()
