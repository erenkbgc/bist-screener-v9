"""Alis zamanlamasi kurallari (docs/research/entry_timing_preregistration.md).

Saf fonksiyonlar: gunluk duzeltilmis OHLC + d0 indeksi -> giris bacaklari
[(gun_indeksi, fiyat, agirlik)]. Her kural son tarihe kadar girer; kosul hic
olusmazsa son tarih kapanisindan alir.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

Leg = tuple[int, float, float]  # (gun indeksi, giris fiyati, sermaye payi)
EXIT_DAY = 126


def indicators(px: pd.DataFrame) -> pd.DataFrame:
    """px: Open/High/Low/Close (duzeltilmis), tarih indeksli. Wilder ATR20/RSI14, SMA20/50."""
    c = px["Close"]
    prev = c.shift(1)
    tr = pd.concat([px["High"] - px["Low"], (px["High"] - prev).abs(), (px["Low"] - prev).abs()], axis=1).max(axis=1)
    out = px.copy()
    out["atr20"] = tr.ewm(alpha=1 / 20, adjust=False, min_periods=20).mean()
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = up / dn.replace(0, np.nan)
    out["rsi14"] = (100 - 100 / (1 + rs)).where(dn > 0, 100.0)
    out["sma20"] = c.rolling(20, min_periods=20).mean()
    out["sma50"] = c.rolling(50, min_periods=50).mean()
    return out


def _close(a: dict, i: int) -> Leg:
    return (i, float(a["Close"][i]), 1.0)


def e0(a: dict, d0: int, ctx: dict) -> list[Leg]:
    return [_close(a, d0 + 1)]


def e1(a: dict, d0: int, ctx: dict) -> list[Leg]:
    return [_close(a, d0 + 22)] if ctx.get("ret_quintile") == 4 else e0(a, d0, ctx)


def _limit(a: dict, d0: int, k: float) -> list[Leg]:
    atr = a["atr20"][d0]
    if not np.isfinite(atr) or atr <= 0:
        return [_close(a, d0 + 21)]
    lim = a["Close"][d0] - k * atr
    for i in range(d0 + 1, d0 + 22):
        if a["Low"][i] <= lim:
            return [(i, float(min(a["Open"][i], lim)), 1.0)]
    return [_close(a, d0 + 21)]


def e2a(a: dict, d0: int, ctx: dict) -> list[Leg]:
    return _limit(a, d0, 1.0)


def e2b(a: dict, d0: int, ctx: dict) -> list[Leg]:
    return _limit(a, d0, 2.0)


def _first(a: dict, start: int, end: int, cond) -> list[Leg]:
    for i in range(start, end + 1):
        if cond(i):
            return [_close(a, i)]
    return [_close(a, end)]


def e3(a: dict, d0: int, ctx: dict) -> list[Leg]:
    return _first(a, d0 + 1, d0 + 21, lambda i: a["rsi14"][i] < 30)


def e4(a: dict, d0: int, ctx: dict) -> list[Leg]:
    return _first(a, d0 + 1, d0 + 63, lambda i: a["Close"][i] > a["sma50"][i])


def e5(a: dict, d0: int, ctx: dict) -> list[Leg]:
    return [(i, float(a["Close"][i]), 1 / 3) for i in (d0 + 1, d0 + 11, d0 + 21)]


def e6(a: dict, d0: int, ctx: dict) -> list[Leg]:
    if ctx.get("ret_quintile") != 0:
        return e0(a, d0, ctx)
    return _first(a, d0 + 1, d0 + 21, lambda i: a["Close"][i] > a["sma20"][i])


RULES = {"E1": e1, "E2a": e2a, "E2b": e2b, "E3": e3, "E4": e4, "E5": e5, "E6": e6}


def improvement(a: dict, xu: np.ndarray, d0: int, legs: list[Leg], policy_pct: float) -> dict:
    """I_mkt ve I_cash (log), bacaklarin agirlikli ortalamasi. xu: hisse gunlerine hizali XU100."""
    p1, x1 = a["Close"][d0 + 1], xu[d0 + 1]
    i_mkt = i_cash = wait = 0.0
    for i, price, w in legs:
        base = np.log(p1 / price)
        i_mkt += w * (base - np.log(x1 / xu[i]))
        days = i - (d0 + 1)
        i_cash += w * (base + np.log1p(policy_pct / 100) * days / 252)
        wait += w * days
    first = min(i for i, _, _ in legs)
    return {"i_mkt": i_mkt, "i_cash": i_cash, "wait_days": wait, "first_idx": first}
