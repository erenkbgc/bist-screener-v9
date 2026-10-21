"""Arastirma istatistikleri (docs/research/quant_review_followups_preregistration.md).

- ols_nw: OLS katsayilari ve Newey-West (Bartlett) t-istatistikleri.
- deflated_sharpe: Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio.
- pbo_cscv: Combinatorially Symmetric Cross-Validation ile backtest asiri uyum olasiligi.
- stationary_bootstrap_ci: Politis-Romano duragan blok bootstrap guven araligi.
- brinson: sektor dagilim (allocation) ve secim (selection) etkisi.
"""
from __future__ import annotations

import math
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

EULER_GAMMA = 0.5772156649


def ols_nw(y: pd.Series, X: pd.DataFrame, lags: int = 6) -> dict:
    """y = a + X b + e; sabit eklenir. NaN iceren satirlar atilir.
    Doner: {"n", "coef": {ad: deger}, "t": {ad: deger}, "r2"}; sabitin adi "alpha"."""
    d = pd.concat([y.rename("_y"), X], axis=1).dropna()
    n = len(d)
    if n <= X.shape[1] + 2:
        return {"n": n}
    Y = d["_y"].to_numpy(dtype=float)
    Z = np.column_stack([np.ones(n), d[X.columns].to_numpy(dtype=float)])
    ZtZ_inv = np.linalg.inv(Z.T @ Z)
    b = ZtZ_inv @ Z.T @ Y
    e = Y - Z @ b
    u = Z * e[:, None]
    S = u.T @ u
    for k in range(1, min(lags, n - 1) + 1):
        w = 1 - k / (lags + 1)
        G = u[k:].T @ u[:-k]
        S += w * (G + G.T)
    cov = ZtZ_inv @ S @ ZtZ_inv
    se = np.sqrt(np.diag(cov))
    names = ["alpha", *X.columns]
    tss = float(((Y - Y.mean()) ** 2).sum())
    return {"n": n, "coef": dict(zip(names, map(float, b))),
            "t": dict(zip(names, map(float, b / se))),
            "r2": 1 - float(e @ e) / tss if tss > 0 else float("nan")}


def expected_max_sharpe(n_trials: int, var_sr: float) -> float:
    """N bagimsiz denemenin en buyuk Sharpe'inin beklenen degeri (SR0)."""
    if n_trials <= 1:
        return 0.0
    return math.sqrt(var_sr) * ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / n_trials)
                                + EULER_GAMMA * norm.ppf(1 - 1 / (n_trials * math.e)))


def deflated_sharpe(returns: pd.Series | np.ndarray, n_trials: int, var_sr: float) -> dict:
    """Aylik (yilliklastirilmamis) Sharpe icin DSR. returns: aktif getiri serisi."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    T = len(r)
    sr = float(r.mean() / r.std(ddof=1))
    g3 = float(skew(r))
    g4 = float(kurtosis(r, fisher=False))
    sr0 = expected_max_sharpe(n_trials, var_sr)
    denom = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))
    dsr = float(norm.cdf((sr - sr0) * math.sqrt(T - 1) / denom))
    return {"T": T, "sr_monthly": sr, "skew": g3, "kurtosis": g4, "sr0": sr0, "n_trials": n_trials, "dsr": dsr}


def _sharpe_cols(m: np.ndarray) -> np.ndarray:
    sd = m.std(axis=0, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(sd > 0, m.mean(axis=0) / sd, 0.0)


def pbo_cscv(perf: pd.DataFrame, n_blocks: int = 16) -> dict:
    """perf: ay x varyant getiri matrisi (NaN yok). Doner PBO, logit dagilimi ozeti."""
    m = perf.to_numpy(dtype=float)
    T, N = m.shape
    size = T // n_blocks
    m = m[: size * n_blocks]
    blocks = [np.arange(k * size, (k + 1) * size) for k in range(n_blocks)]
    logits = []
    for ins in combinations(range(n_blocks), n_blocks // 2):
        oos = [k for k in range(n_blocks) if k not in ins]
        i_rows = np.concatenate([blocks[k] for k in ins])
        o_rows = np.concatenate([blocks[k] for k in oos])
        sr_in = _sharpe_cols(m[i_rows])
        sr_out = _sharpe_cols(m[o_rows])
        best = int(np.argmax(sr_in))
        rank = float((sr_out < sr_out[best]).sum() + 1 + 0.5 * ((sr_out == sr_out[best]).sum() - 1))
        w = rank / (N + 1)
        logits.append(math.log(w / (1 - w)))
    lg = np.array(logits)
    return {"pbo": float((lg <= 0).mean()), "n_splits": len(lg), "n_variants": N, "months_used": size * n_blocks,
            "logit_median": float(np.median(lg))}


def stationary_bootstrap_ci(x: pd.Series | np.ndarray, mean_block: float = 6.0, reps: int = 5000,
                            seed: int = 20261021, level: float = 0.95, scale: float = 1200.0) -> tuple[float, float]:
    """Ortalamanin duragan bootstrap araligi (scale ile carpilmis, ornegin %/yil)."""
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    n = len(a)
    rng = np.random.default_rng(seed)
    p = 1 / mean_block
    means = np.empty(reps)
    for r in range(reps):
        idx = np.empty(n, dtype=int)
        idx[0] = rng.integers(n)
        jumps = rng.random(n) < p
        starts = rng.integers(n, size=n)
        for i in range(1, n):
            idx[i] = starts[i] if jumps[i] else (idx[i - 1] + 1) % n
        means[r] = a[idx].mean()
    lo, hi = np.quantile(means, [(1 - level) / 2, (1 + level) / 2])
    return float(scale * lo), float(scale * hi)


def brinson(month: pd.DataFrame, held: set[str]) -> tuple[float, float]:
    """Tek ay icin (allocation, selection). month: ticker, sector, ret sutunlari (evren)."""
    g = month.dropna(subset=["ret"])
    p = g[g["ticker"].isin(held)]
    if g.empty or p.empty:
        return float("nan"), float("nan")
    rb = g["ret"].mean()
    wb = g.groupby("sector").size() / len(g)
    rbs = g.groupby("sector")["ret"].mean()
    wp = p.groupby("sector").size() / len(p)
    rps = p.groupby("sector")["ret"].mean()
    wp = wp.reindex(wb.index, fill_value=0.0)
    alloc = float(((wp - wb) * (rbs - rb)).sum())
    sel = float((wp * (rps.reindex(wb.index) - rbs).fillna(0.0)).sum())
    return alloc, sel
