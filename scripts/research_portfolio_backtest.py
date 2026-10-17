#!/usr/bin/env python3
"""On-kayitli canli kural portfoy backtest'i (docs/research/portfolio_backtest_preregistration.md).

    python scripts/build_fx_panel.py
    python scripts/research_long_term.py     # quarterly_ext.parquet onbellegi
    python scripts/research_portfolio_backtest.py
"""
from __future__ import annotations

import json
import pickle
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import factor_backtest as fb  # noqa: E402
from core import portfolio_backtest as pb  # noqa: E402
from diagnose_crashed_picks import month_end  # noqa: E402
from research_long_term import load  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SPLIT = pd.Timestamp("2021-01-01")
CAPITALS = {"100k": 1e5, "1M": 1e6, "10M": 1e7, "100M": 1e8}
CAPITAL_REF = pd.Timestamp("2026-09-30")
TOP = 0.2


def _norm_index(idx) -> pd.DatetimeIndex:
    idx = pd.to_datetime(idx)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return idx.normalize()


def load_daily(ticker: str) -> pd.DataFrame | None:
    f = RESEARCH / "raw" / f"{ticker}.pkl"
    if not f.exists():
        return None
    d = pickle.loads(f.read_bytes())
    adj, raw = d.get("px_adj"), d.get("px_raw")
    if adj is None or adj.empty or raw is None or raw.empty:
        return None
    adj = adj[["Open", "Close"]].astype(float).copy()
    raw = raw[["Close", "Volume"]].astype(float).copy()
    adj.index, raw.index = _norm_index(adj.index), _norm_index(raw.index)
    adj = adj[~adj.index.duplicated(keep="last")]
    raw = raw[~raw.index.duplicated(keep="last")]
    adj = adj[(adj["Close"] > 0) & (adj["Open"] > 0)]
    out = adj.join((raw["Close"] * raw["Volume"]).rename("tl_vol"), how="left")
    out["adv"] = out["tl_vol"].rolling(60, min_periods=40).median()  # pit_panel tlvol60 tanimi
    out["sigma"] = out["Close"].pct_change().rolling(60, min_periods=40).std()
    return out


def selections(df: pd.DataFrame, raw_panel: pd.DataFrame) -> dict[str, dict[pd.Timestamp, list[str]]]:
    """P0, F1, F2 hedef listeleri (ay -> ticker listesi)."""
    thr50 = raw_panel[raw_panel["tlvol60"] > 0].groupby("date")["tlvol60"].quantile(0.5)
    out = {"P0": {}, "F1": {}, "F2": {}}
    for t, g in df.groupby("date"):
        variants = {
            "P0": g,
            "F1": g[g["mcap"] >= g["mcap"].quantile(0.3)],
            "F2": g[g["tlvol60"] >= thr50.get(t, np.inf)],
        }
        for name, h in variants.items():
            r = h["value_sn_z"].rank(ascending=False, pct=True)
            out[name][t] = sorted(h.loc[r <= TOP, "ticker"])
    return out


def build():
    df = load()
    df = df[df["value_sn_z"].notna()].copy()
    raw_panel = pd.read_parquet(RESEARCH / "factors_monthly.parquet")
    raw_panel["date"] = month_end(raw_panel["date"])
    sel = selections(df, raw_panel)

    fx = pd.read_parquet(RESEARCH / "fx.parquet")
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()
    days = fx.index
    months = sorted(df["date"].unique())
    d0_of = {t: days[days.searchsorted(t, side="right") - 1] for t in months}

    tickers = sorted({tk for v in sel.values() for lst in v.values() for tk in lst})
    frames = {tk: load_daily(tk) for tk in tickers}
    frames = {tk: f for tk, f in frames.items() if f is not None}
    mat = {k: pd.DataFrame({tk: f[c] for tk, f in frames.items()}).reindex(days)
           for k, c in (("close", "Close"), ("open", "Open"), ("adv", "adv"), ("sigma", "sigma"))}
    # ADV/sigma islem olmayan gunlerde son bilinen deger
    mat["adv"], mat["sigma"] = mat["adv"].ffill(), mat["sigma"].ffill()

    macro = pd.read_parquet(RESEARCH / "macro_monthly.parquet")
    macro.index = pd.to_datetime(macro.index).to_period("M")
    rf_daily = pb.policy_rf_daily(macro["policy"], days)
    cpi_idx = (1 + macro["cpi_mom"].fillna(0) / 100).cumprod()
    ref = cpi_idx[CAPITAL_REF.to_period("M")]
    cpi_rel = {t: float(cpi_idx[t.to_period("M")] / ref) for t in months}

    universe_liq = {t: np.sort(g["tlvol60"].to_numpy()) for t, g in df.groupby("date")}
    bench = df.groupby("date")[["fwd_ret_1m", "fwd_ret_1m_usd"]].mean()

    mkt = pb.Market(close=mat["close"], open=mat["open"], adv=mat["adv"], sigma=mat["sigma"], rf_daily=rf_daily)
    ctx = {"months": months, "d0_of": d0_of, "fx": fx, "rf_daily": rf_daily, "cpi_idx": cpi_idx,
           "bench": bench, "cpi_rel": cpi_rel, "universe_liq": universe_liq}
    return sel, mkt, ctx


def attach_benchmarks(p: pd.DataFrame, ctx: dict) -> pd.DataFrame:
    months, d0_of, fx = ctx["months"], ctx["d0_of"], ctx["fx"]
    nxt = {months[k]: months[k + 1] for k in range(len(months) - 1)}
    p = p.copy()
    d0 = p["date"].map(d0_of)
    d1 = p["date"].map(lambda t: d0_of[nxt[t]])
    p["xu"] = fx["xu100"].reindex(d1).to_numpy() / fx["xu100"].reindex(d0).to_numpy() - 1
    p["fx_ret"] = fx["usdtry"].reindex(d1).to_numpy() / fx["usdtry"].reindex(d0).to_numpy() - 1
    growth = (1 + ctx["rf_daily"]).cumprod()
    p["dep"] = growth.reindex(d1).to_numpy() / growth.reindex(d0).to_numpy() - 1
    cpi = ctx["cpi_idx"]
    p["infl"] = [float(cpi[nxt[t].to_period("M")] / cpi[t.to_period("M")] - 1) for t in p["date"]]
    p["bench"] = p["date"].map(ctx["bench"]["fwd_ret_1m"])
    p["bench_usd"] = p["date"].map(ctx["bench"]["fwd_ret_1m_usd"])
    p["port_usd"] = (1 + p["port"]) / (1 + p["fx_ret"]) - 1
    p["port_real"] = (1 + p["port"]) / (1 + p["infl"]) - 1
    p["active"] = p["port"] - p["bench"]
    p["active_usd"] = p["port_usd"] - p["bench_usd"]
    p["active_xu"] = p["port"] - p["xu"]
    p["excess_dep"] = p["port"] - p["dep"]
    return p.dropna(subset=["bench", "xu", "fx_ret", "infl"])


def _cagr(r: pd.Series) -> float:
    return float((1 + r).prod() ** (12 / len(r)) - 1) if len(r) else np.nan


def _dd(r: pd.Series) -> tuple[float, int]:
    nav = (1 + r).cumprod()
    peak = nav.cummax()
    dd = float((nav / peak - 1).min())
    longest, run = 0, 0
    for under in (nav < peak - 1e-12):
        run = run + 1 if under else 0
        longest = max(longest, run)
    return dd, longest


def stats(p: pd.DataFrame) -> dict:
    if p.empty:
        return {"months": 0}
    out = {"months": len(p)}
    for key, col in (("active_univ", "active"), ("active_usd", "active_usd"),
                     ("active_xu100", "active_xu"), ("excess_deposit", "excess_dep")):
        m, t, _ = fb.newey_west_t(p[col], 6)
        out[f"{key}_ann_pct"], out[f"{key}_t"] = round(1200 * m, 2), round(t, 2)
    a = p["active_xu"]
    out["ir_xu100"] = round(float(a.mean() / a.std() * np.sqrt(12)), 2)
    ex = p["excess_dep"]
    down = np.sqrt(np.mean(np.minimum(ex, 0) ** 2))
    out["sharpe"] = round(float(ex.mean() / ex.std() * np.sqrt(12)), 2)
    out["sortino"] = round(float(ex.mean() / down * np.sqrt(12)), 2) if down > 0 else None
    out["cagr_tl_pct"] = round(100 * _cagr(p["port"]), 2)
    out["cagr_usd_pct"] = round(100 * _cagr(p["port_usd"]), 2)
    out["cagr_real_pct"] = round(100 * _cagr(p["port_real"]), 2)
    out["cagr_xu100_pct"] = round(100 * _cagr(p["xu"]), 2)
    out["cagr_deposit_pct"] = round(100 * _cagr(p["dep"]), 2)
    for cur, col in (("tl", "port"), ("usd", "port_usd")):
        dd, rec = _dd(p[col])
        out[f"max_dd_{cur}_pct"], out[f"longest_underwater_{cur}_months"] = round(100 * dd, 1), rec
    out["turnover_pct"] = round(100 * p["turnover"].mean(), 1)
    for c in ("cost", "commission", "spread", "impact"):
        out[f"{c}_ann_pct"] = round(1200 * p[c].mean(), 2)
    out["fills_over_10pct_adv_pct"] = round(100 * p["fills_over_10pct_adv"].sum() / max(1, p["fills"].sum()), 1)
    out["avg_names"] = round(p["n"].mean(), 1)
    return out


def diff(base: pd.DataFrame, alt: pd.DataFrame) -> dict:
    d = (alt.set_index("date")["active"] - base.set_index("date")["active"]).dropna()
    m, t, n = fb.newey_west_t(d, 6)
    return {"months": n, "diff_ann_pct": round(1200 * m, 2), "t": round(t, 2)}


def split(p: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {"discovery": p[p["date"] < SPLIT], "holdout": p[p["date"] >= SPLIT]}


def d1_verdict(s: dict) -> str:
    d, h = s["discovery"], s["holdout"]
    if h["active_univ_ann_pct"] <= 0:
        return "EDGE_NOT_ESTABLISHED_AFTER_COSTS"
    if d["active_univ_ann_pct"] > 0 and d["active_univ_t"] > 2 and h["active_univ_t"] > 2:
        return "SURVIVES_REALISTIC_COSTS"
    return "NET_FIGURES_NO_CLAIM"


def d3_verdict(dd: dict, alt_s: dict, base_s: dict) -> str:
    ok = all(dd[w]["diff_ann_pct"] > -1.0 and dd[w]["t"] > -2.0 for w in ("discovery", "holdout"))
    ok = ok and alt_s["holdout"]["max_dd_usd_pct"] >= base_s["holdout"]["max_dd_usd_pct"] - 2.0
    return "PASS" if ok else "FAIL"


def main() -> None:
    sel, mkt, ctx = build()
    months = ctx["months"]

    def run(variant: str, capital: float, costs: pb.Costs, fill: str = "close", haircut: float = 0.0):
        cap = {t: capital * ctx["cpi_rel"][t] for t in months}
        p = pb.simulate(sel[variant], months, ctx["d0_of"], mkt, ctx["universe_liq"], cap,
                        costs=costs, fill=fill, haircut=haircut)
        out = attach_benchmarks(p, ctx)
        out.attrs["delist_events"] = p.attrs["delist_events"]
        return out

    scenarios = {"base": pb.Costs(), "stress": pb.Costs(mult=2.0)}
    sims = {}
    for v in ("P0", "F1", "F2"):
        for cname, cap in CAPITALS.items():
            for sname, c in scenarios.items():
                sims[(v, cname, sname, "close", 0.0)] = run(v, cap, c)
                print(f"  {v} {cname} {sname}", flush=True)
    sims[("P0", "1M", "base", "open", 0.0)] = run("P0", 1e6, scenarios["base"], fill="open")
    sims[("P0", "1M", "base", "close", 0.5)] = run("P0", 1e6, scenarios["base"], haircut=0.5)

    def key_s(k):
        return "|".join(str(x) for x in k)

    summary = {key_s(k): {**{w: stats(s) for w, s in split(p).items()}, "delist_events": p.attrs["delist_events"]}
               for k, p in sims.items()}
    main_k = ("P0", "1M", "base", "close", 0.0)
    main_s = summary[key_s(main_k)]

    # D2 kapasite
    base100 = summary[key_s(("P0", "100k", "base", "close", 0.0))]["holdout"]["active_univ_ann_pct"]
    capacity = None
    for cname in CAPITALS:
        if summary[key_s(("P0", cname, "base", "close", 0.0))]["holdout"]["active_univ_ann_pct"] >= base100 / 2:
            capacity = cname

    # D3 filtreler
    filt = {}
    for v in ("F1", "F2"):
        a, b = split(sims[(v, "1M", "base", "close", 0.0)]), split(sims[main_k])
        dd = {w: diff(b[w], a[w]) for w in ("discovery", "holdout")}
        filt[v] = {**dd, "verdict": d3_verdict(dd, summary[key_s((v, "1M", "base", "close", 0.0))], main_s)}
    passing = [v for v in filt if filt[v]["verdict"] == "PASS"]
    live_filter = max(passing, key=lambda v: filt[v]["holdout"]["diff_ann_pct"]) if passing else None

    # D4 survivorship
    h05 = summary[key_s(("P0", "1M", "base", "close", 0.5))]
    sign_flip = any(np.sign(h05[w]["active_univ_ann_pct"]) != np.sign(main_s[w]["active_univ_ann_pct"])
                    for w in ("discovery", "holdout"))

    result = {"as_of": date.today().isoformat(),
              "months": [str(months[0].date()), str(months[-1].date())],
              "decisions": {"D1_execution": d1_verdict(main_s), "D2_capacity": capacity,
                            "D3_filters": filt, "D3_live_filter": live_filter,
                            "D4_survivorship_sensitive": bool(sign_flip)},
              "summary": summary}
    out = ROOT / "data" / "reports" / f"research_portfolio_backtest_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"\nAylar {result['months'][0]} .. {result['months'][1]}")
    print("variant cap  cost   fill  h    period     univ%/yr (t)   xu100%/yr  CAGR TL/USD/real   maxDD USD  cost%/yr  >10%ADV")
    for k, s in summary.items():
        for w in ("discovery", "holdout"):
            x = s[w]
            print(f"{k:28s} {w:9s}  {x['active_univ_ann_pct']:6.2f} ({x['active_univ_t']:5.2f})  "
                  f"{x['active_xu100_ann_pct']:6.2f}   {x['cagr_tl_pct']:6.1f}/{x['cagr_usd_pct']:5.1f}/{x['cagr_real_pct']:5.1f}  "
                  f"{x['max_dd_usd_pct']:6.1f}   {x['cost_ann_pct']:5.2f}   {x['fills_over_10pct_adv_pct']:5.1f}")
    print("\nKararlar:", json.dumps(result["decisions"], indent=1, ensure_ascii=False))
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
