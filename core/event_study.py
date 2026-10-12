"""Olay calismasi yardimcilari (docs/research/event_study_preregistration.md).

Gunler BIST islem gunu; t0 listelenen tarihte veya sonrasindaki ilk islem gunu.
Pencere [a, b]: a-1 kapanisindan b kapanisina getiri.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

EST_START, EST_END = -250, -31
RECOVERY_CAP = 250


def event_pos(days: pd.DatetimeIndex, listed: str) -> int:
    return int(days.searchsorted(pd.Timestamp(listed), side="left"))


def window_return(level: np.ndarray, i0: int, a: int, b: int) -> float:
    lo, hi = i0 + a - 1, i0 + b
    if lo < 0 or hi >= len(level):
        return np.nan
    return float(level[hi] / level[lo] - 1)


def market_model(r: np.ndarray, rm: np.ndarray, i0: int) -> tuple[float, float, float]:
    """Dimson: r_t = a + b0 rm_t + b1 rm_{t-1}; tahmin penceresi [-250, -31]."""
    idx = np.arange(i0 + EST_START, i0 + EST_END + 1)
    idx = idx[(idx >= 1) & (idx < len(r))]
    y = r[idx]
    x = np.column_stack([np.ones(len(idx)), rm[idx], rm[idx - 1]])
    ok = np.isfinite(y) & np.isfinite(x).all(axis=1)
    coef, *_ = np.linalg.lstsq(x[ok], y[ok], rcond=None)
    return float(coef[0]), float(coef[1]), float(coef[2])


def car(r: np.ndarray, rm: np.ndarray, params: tuple[float, float, float], i0: int, a: int, b: int) -> float:
    lo, hi = i0 + a, i0 + b
    if lo < 1 or hi >= len(r):
        return np.nan
    k = np.arange(lo, hi + 1)
    al, b0, b1 = params
    return float(np.sum(r[k] - al - b0 * rm[k] - b1 * rm[k - 1]))


def recovery_days(level: np.ndarray, i0: int) -> int:
    """Seviyenin ilk kez gun -1 kapanisina veya ustune kapandigi gun sayisi (0 = t0'da)."""
    ref = level[i0 - 1]
    for k in range(0, RECOVERY_CAP + 1):
        if i0 + k >= len(level):
            break
        if level[i0 + k] >= ref:
            return k
    return RECOVERY_CAP


def vol_ratio(r: np.ndarray, i0: int) -> float:
    post = r[i0 + 1:i0 + 21]
    pre = r[max(0, i0 - 60):i0]
    if len(post) < 20 or len(pre) < 60:
        return np.nan
    return float(np.std(post, ddof=1) / np.std(pre, ddof=1))


def cross_event_test(x: list[float]) -> dict:
    """Olaylar arasi tek orneklem t-testi (df = N-1)."""
    a = np.array([v for v in x if np.isfinite(v)])
    if len(a) < 3:
        return {"n": int(len(a))}
    t, p = stats.ttest_1samp(a, 0.0)
    return {"n": int(len(a)), "mean_pct": round(100 * float(a.mean()), 2), "t": round(float(t), 2),
            "p": round(float(p), 4), "n_pos": int((a > 0).sum()), "n_neg": int((a < 0).sum())}


def verdict(test: dict, need: int, alpha: float, pos_label: str, neg_label: str) -> str:
    if test.get("n", 0) < 3:
        return "INSUFFICIENT"
    if test["p"] < alpha and test["mean_pct"] > 0 and test["n_pos"] >= need:
        return pos_label
    if test["p"] < alpha and test["mean_pct"] < 0 and test["n_neg"] >= need:
        return neg_label
    return "FAIL"
