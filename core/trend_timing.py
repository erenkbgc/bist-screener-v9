"""Trend takip zamanlama katmanlari (docs/research/trend_timing_preregistration.md).

Her hissenin tum gunluk gecmisi uzerinde uzun/duz durum makineleri (T1 Donchian 20/10 +
ATR, T2 Supertrend 10/3, T3 EMA geri cekilme + ATR), bir gun gecikmeli uygulama ve
limit kurali; R0 secimi uzerinde aylik dengelemeli katman simulasyonu.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.smc import atr_wilder

COST_BPS = 20.0
LIMIT_PCT = 0.095


def _ema(x: np.ndarray, span: int) -> np.ndarray:
    return pd.Series(x).ewm(span=span, adjust=False, min_periods=span).mean().to_numpy()


def donchian_state(h: np.ndarray, lo: np.ndarray, c: np.ndarray, entry_n: int = 20, exit_n: int = 10,
                   atr_n: int = 14, atr_mult: float = 2.0) -> np.ndarray:
    atr = atr_wilder(h, lo, c, atr_n)
    hi_prev = pd.Series(h).rolling(entry_n).max().shift(1).to_numpy()
    lo_prev = pd.Series(lo).rolling(exit_n).min().shift(1).to_numpy()
    st = np.zeros(len(c), dtype=np.int8)
    long, peak = False, np.nan
    for t in range(1, len(c)):
        if not long:
            if np.isfinite(hi_prev[t]) and c[t] > hi_prev[t]:
                long, peak = True, c[t]
        else:
            peak = max(peak, c[t])
            trail = peak - atr_mult * atr[t - 1] if np.isfinite(atr[t - 1]) else -np.inf
            if (np.isfinite(lo_prev[t]) and c[t] < lo_prev[t]) or c[t] < trail:
                long = False
        st[t] = long
    return st


def supertrend_state(h: np.ndarray, lo: np.ndarray, c: np.ndarray, atr_n: int = 10,
                     mult: float = 3.0) -> np.ndarray:
    atr = atr_wilder(h, lo, c, atr_n)
    hl2 = (h + lo) / 2
    st = np.zeros(len(c), dtype=np.int8)
    fu = fl = np.nan
    up = False
    for t in range(len(c)):
        if not np.isfinite(atr[t]):
            continue
        bu, bl = hl2[t] + mult * atr[t], hl2[t] - mult * atr[t]
        if not np.isfinite(fu):
            fu, fl = bu, bl
            up = c[t] > hl2[t]
            st[t] = up
            continue
        prev_fu, prev_fl = fu, fl
        fu = bu if (bu < prev_fu or c[t - 1] > prev_fu) else prev_fu
        fl = bl if (bl > prev_fl or c[t - 1] < prev_fl) else prev_fl
        if not up and c[t] > prev_fu:
            up = True
        elif up and c[t] < prev_fl:
            up = False
        st[t] = up
    return st


def ema_pullback_state(h: np.ndarray, lo: np.ndarray, c: np.ndarray, atr_n: int = 14,
                       atr_mult: float = 3.0) -> np.ndarray:
    atr = atr_wilder(h, lo, c, atr_n)
    e20, e50 = _ema(c, 20), _ema(c, 50)
    st = np.zeros(len(c), dtype=np.int8)
    long, peak = False, np.nan
    for t in range(1, len(c)):
        if not long:
            trend = np.isfinite(e20[t]) and np.isfinite(e50[t]) and e20[t] > e50[t]
            if trend and np.isfinite(e20[t - 1]) and lo[t - 1] <= e20[t - 1] and c[t] > h[t - 1]:
                long, peak = True, c[t]
        else:
            peak = max(peak, c[t])
            if np.isfinite(atr[t - 1]) and c[t] < peak - atr_mult * atr[t - 1]:
                long = False
        st[t] = long
    return st


SYSTEMS = {"T1": donchian_state, "T2": supertrend_state, "T3": ema_pullback_state}


def execute(state: np.ndarray, c: np.ndarray, limit_pct: float = LIMIT_PCT) -> np.ndarray:
    """Uygulanan pozisyon: t kapanisindaki durum t+1 kapanisinda islenir; t+1'de kapanis
    onceki kapanisa gore >= limit_pct oynadiysa islem ertelenir."""
    pos = np.zeros(len(state), dtype=np.int8)
    for t in range(1, len(state)):
        want = state[t - 1]
        locked = c[t - 1] > 0 and np.isfinite(c[t]) and abs(c[t] / c[t - 1] - 1) >= limit_pct
        pos[t] = pos[t - 1] if (want != pos[t - 1] and locked) else want
    return pos


def simulate_overlay(months: list[pd.Timestamp], universe: dict[pd.Timestamp, pd.DataFrame],
                     close: pd.DataFrame, pos: pd.DataFrame | None, rf_daily: pd.Series, xu: pd.Series,
                     d0_of: dict[pd.Timestamp, pd.Timestamp], park: str = "cash") -> pd.DataFrame:
    """R0 (rank_pct <= 0.2) aylik esit agirlik; pos None ise hep uzun (B0). Duz gunlerde
    slot politika faizi (park='cash') veya XU100 (park='xu100') kazanir."""
    rows, prev = [], set()
    for k, t in enumerate(months[:-1]):
        g = universe[t]
        d0, d1 = d0_of[t], d0_of[months[k + 1]]
        window = close.loc[d0:d1]
        names = [tk for tk in g.index[g["rank_pct"] <= 0.2]
                 if tk in window.columns and np.isfinite(window[tk].iloc[0])]
        if not names:
            prev = set()
            continue
        turnover = len([tk for tk in names if tk not in prev]) / len(names) if prev else 1.0
        rf = rf_daily.reindex(window.index).fillna(0.0).to_numpy()[1:]
        xr = (xu.reindex(window.index).ffill().pct_change().fillna(0.0)).to_numpy()[1:]
        alt = rf if park == "cash" else xr
        rets, switches, invested = [], 0, []
        for tk in names:
            path = window[tk].ffill().to_numpy()
            r = path[1:] / path[:-1] - 1
            if pos is None:
                p = np.ones(len(path), dtype=np.int8)
            else:
                p = pos[tk].reindex(window.index).ffill().fillna(0).to_numpy().astype(np.int8)
            held = p[:-1]
            growth = np.prod(1 + np.where(held == 1, r, alt))
            n_sw = int((p[1:] != p[:-1]).sum())
            rets.append(growth - 1 - n_sw * COST_BPS / 1e4)
            switches += n_sw
            invested.append(held.mean() if len(held) else 1.0)
        port = float(np.mean(rets))
        cost = 2 * turnover * COST_BPS / 1e4
        fx = g["fx_ret"].iloc[0]
        port_usd = (1 + port - cost) / (1 + fx) - 1
        rows.append({"date": t, "n": len(names), "turnover": turnover, "n_stops": switches / len(names),
                     "invested": float(np.mean(invested)), "port": port, "cost": cost,
                     "active": port - cost - g["bench"].iloc[0],
                     "active_usd": port_usd - g["bench_usd"].iloc[0], "total_usd": port_usd})
        prev = set(names)
    return pd.DataFrame(rows)
