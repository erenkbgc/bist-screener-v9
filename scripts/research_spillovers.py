#!/usr/bin/env python3
"""On-kayitli sektor yayilimi testleri (docs/research/spillovers_preregistration.md).

L1  sektor ici buyukten kucuge haftalik gecikmeli yayilim (Fama-MacBeth).
L2a ilk bilanco aciklayan sirketin gun [0,+1] tepkisi -> henuz aciklamamis
    sektor kardeslerinin ayni pencere tepkisi.
L2b ayni tepki -> kardeslerin [+2,+10] kaymasi (eksik tepki).

    python scripts/research_spillovers.py
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
from core import pit_panel  # noqa: E402
from diagnose_crashed_picks import month_end  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SPLIT = pd.Timestamp("2021-01-01")
MIN_SECTOR_NAMES, MIN_SECTORS, MIN_PEERS = 4, 5, 2
PEER_GAP = 10
NW_LAGS = 4
HLZ_T, HOLDOUT_T = 3.0, 2.0


def load_closes(tickers: list[str], days: pd.DatetimeIndex) -> pd.DataFrame:
    cols = {}
    for tk in tickers:
        f = RESEARCH / "raw" / f"{tk}.pkl"
        if not f.exists():
            continue
        px = pickle.loads(f.read_bytes()).get("px_adj")
        if px is None or px.empty:
            continue
        idx = pd.to_datetime(px.index)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        s = pd.Series(px["Close"].astype(float).to_numpy(), index=idx.normalize())
        s = s[~s.index.duplicated(keep="last")]
        cols[tk] = s[s > 0]
    return pd.DataFrame(cols).reindex(days)


def ols_b(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    X = np.column_stack([np.ones(len(y)), x])
    return np.linalg.lstsq(X, y, rcond=None)[0]


def cluster_ols(y: np.ndarray, x: np.ndarray, groups: np.ndarray) -> tuple[float, float, int]:
    """y = a + b x; b ve kume-dayanikli t (kume = takvim ceyregi)."""
    X = np.column_stack([np.ones(len(y)), x])
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    e = y - X @ beta
    meat = np.zeros((2, 2))
    gs = pd.unique(groups)
    for g in gs:
        m = groups == g
        s = X[m].T @ e[m]
        meat += np.outer(s, s)
    G = len(gs)
    V = xtx_inv @ meat @ xtx_inv * (G / (G - 1) if G > 1 else 1.0)
    return float(beta[1]), float(beta[1] / np.sqrt(V[1, 1])), G


# ---------------------------------------------------------------- L1
def lead_lag(close: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    """Hafta basina b (Fama-MacBeth) ve tanimlayici portfoy farki."""
    c = close.ffill(limit=5)
    weekly = c.resample("W-FRI").last()
    first_day = close.notna().any(axis=1)
    wk_mon = close.index[first_day].to_series().groupby(close.index[first_day].to_period("W-FRI")).first()
    r_w = weekly.pct_change(fill_method=None)
    months = sorted(universe["date"].unique())
    uni_by = {t: g for t, g in universe.groupby("date")}
    rows = []
    wk = r_w.index
    for k in range(1, len(wk) - 1):
        w, w1 = wk[k], wk[k + 1]
        start = w + pd.Timedelta(days=1)  # w+1 haftasinin baslangici
        prior = [t for t in months if t < start]
        if not prior:
            continue
        g = uni_by[prior[-1]]
        mon = wk_mon.get(w1.to_period("W-FRI"))
        xs, ys, ys_skip, lag_small, port_rows = [], [], [], [], []
        for sec, h in g.groupby("sector"):
            h = h[h["ticker"].isin(r_w.columns)]
            if len(h) < MIN_SECTOR_NAMES:
                continue
            med = h["mcap"].median()
            big, small = list(h.loc[h["mcap"] > med, "ticker"]), list(h.loc[h["mcap"] <= med, "ticker"])
            rb, rs, rs1 = r_w.loc[w, big].mean(), r_w.loc[w, small].mean(), r_w.loc[w1, small].mean()
            if not all(np.isfinite([rb, rs, rs1])):
                continue
            rs1_skip = np.nan
            if mon is not None and mon in c.index:
                rs1_skip = (weekly.loc[w1, small] / c.loc[mon, small] - 1).mean()
            xs.append(rb); lag_small.append(rs); ys.append(rs1); ys_skip.append(rs1_skip)
            port_rows.append((rb, small))
        if len(xs) < MIN_SECTORS:
            continue
        b = ols_b(np.array(ys), np.column_stack([xs, lag_small]))[1]
        yk = np.array(ys_skip)
        ok = np.isfinite(yk)
        b_skip = ols_b(yk[ok], np.column_stack([np.array(xs)[ok], np.array(lag_small)[ok]]))[1] \
            if ok.sum() >= MIN_SECTORS else np.nan
        cut = np.quantile(xs, 2 / 3)
        top = [tk for rb, sm in port_rows if rb >= cut for tk in sm]
        alls = [tk for _, sm in port_rows for tk in sm]
        port = r_w.loc[w1, top].mean() - r_w.loc[w1, alls].mean()
        rows.append({"week": w1, "b": b, "b_skip": b_skip, "port": port, "sectors": len(xs)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- L2
def transfer_events(close: pd.DataFrame, universe: pd.DataFrame, dates: pd.DataFrame) -> pd.DataFrame:
    days = close.index
    r = close.pct_change(fill_method=None)
    months = sorted(universe["date"].unique())
    uni_by = {t: g for t, g in universe.groupby("date")}
    mkt_cache: dict[pd.Timestamp, pd.Series] = {}
    rows = []
    dates = dates.copy()
    dates["pos"] = days.searchsorted(dates["kap_available_at"], side="left")
    for period, dp in dates.groupby("period"):
        first_day = dp["kap_available_at"].min()
        prior = [t for t in months if t < first_day]
        if not prior:
            continue
        m = prior[-1]
        g = uni_by[m]
        if m not in mkt_cache:
            members = [t for t in g["ticker"] if t in r.columns]
            mkt_cache[m] = r[members].mean(axis=1)
        mkt = mkt_cache[m]
        dp = dp[dp["ticker"].isin(g["ticker"])].merge(g[["ticker", "sector"]], on="ticker")
        for sec, h in dp.groupby("sector"):
            t0 = int(h["pos"].min())
            if t0 + PEER_GAP >= len(days):
                continue
            ann = list(h.loc[h["pos"] == t0, "ticker"])
            peers = list(h.loc[h["pos"] > t0 + PEER_GAP, "ticker"])
            ann = [t for t in ann if t in r.columns]
            peers = [t for t in peers if t in r.columns]
            if not ann or len(peers) < MIN_PEERS:
                continue

            def car(names, a, b):
                win = r.iloc[t0 + a:t0 + b + 1][names].mean(axis=1) - mkt.iloc[t0 + a:t0 + b + 1]
                return float(win.sum()) if win.notna().all() else np.nan

            rows.append({"period": period, "sector": sec, "t0": days[t0], "n_ann": len(ann), "n_peers": len(peers),
                         "ar_ann": car(ann, 0, 1), "ar_peer0": car(peers, 0, 1),
                         "ar_peer_drift": car(peers, 2, PEER_GAP)})
    return pd.DataFrame(rows).dropna(subset=["ar_ann", "ar_peer0", "ar_peer_drift"])


def verdict(disc_b: float, disc_t: float, hold_b: float, hold_t: float) -> str:
    if disc_b > 0 and disc_t > HLZ_T and hold_b > 0 and hold_t > HOLDOUT_T:
        return "PASS"
    if disc_b > 0 and disc_t > HLZ_T:
        return "DISCOVERY_ONLY"
    return "FAIL"


def main() -> None:
    panel = pd.read_parquet(RESEARCH / "factors_monthly.parquet")
    panel["date"] = month_end(panel["date"])
    universe = fb.prepare(panel, [], liq_drop_pct=0.3)[["date", "ticker", "sector", "mcap"]]
    fx = pd.read_parquet(RESEARCH / "fx.parquet")
    days = pd.DatetimeIndex(pd.to_datetime(fx["date"]).dt.normalize()).sort_values()
    close = load_closes(sorted(universe["ticker"].unique()), days)
    print(f"fiyat: {close.shape[1]} hisse, {len(days)} gun", flush=True)

    result = {"as_of": date.today().isoformat(), "tests": {}}
    ll = lead_lag(close, universe)
    l1 = {}
    for w, sub in (("discovery", ll[ll["week"] < SPLIT]), ("holdout", ll[ll["week"] >= SPLIT])):
        m, t, n = fb.newey_west_t(sub["b"], NW_LAGS)
        ms, ts, _ = fb.newey_west_t(sub["b_skip"].dropna(), NW_LAGS)
        mp, tp, _ = fb.newey_west_t(sub["port"].dropna(), NW_LAGS)
        l1[w] = {"weeks": n, "b": round(m, 4), "t": round(t, 2), "b_skip_day": round(ms, 4), "t_skip_day": round(ts, 2),
                 "port_weekly_bps": round(1e4 * mp, 1), "port_t": round(tp, 2),
                 "avg_sectors": round(sub["sectors"].mean(), 1)}
    l1["verdict"] = verdict(l1["discovery"]["b"], l1["discovery"]["t"], l1["holdout"]["b"], l1["holdout"]["t"])
    result["tests"]["L1_big_to_small_lead_lag"] = l1
    print("L1 bitti", flush=True)

    dates = pit_panel.kap_report_dates(pd.read_parquet(RESEARCH / "kap_archive.parquet"))
    ev = transfer_events(close, universe, dates)
    for name, col in (("L2a_same_day_transfer", "ar_peer0"), ("L2b_peer_drift", "ar_peer_drift")):
        res = {}
        for w, sub in (("discovery", ev[ev["t0"] < SPLIT]), ("holdout", ev[ev["t0"] >= SPLIT])):
            b, t, G = cluster_ols(sub[col].to_numpy(), sub["ar_ann"].to_numpy(), sub["period"].to_numpy())
            res[w] = {"events": len(sub), "clusters": G, "b": round(b, 4), "t": round(t, 2),
                      "avg_peers": round(sub["n_peers"].mean(), 1)}
        res["verdict"] = verdict(res["discovery"]["b"], res["discovery"]["t"], res["holdout"]["b"], res["holdout"]["t"])
        result["tests"][name] = res
    out = ROOT / "data" / "reports" / f"research_spillovers_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=float))
    print(json.dumps(result, indent=1, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
