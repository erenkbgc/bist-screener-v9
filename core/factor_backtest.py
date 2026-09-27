"""Kesitsel faktor testi (roadmap Adim 3): rank-IC, Fama-MacBeth, quintile yayilimi.

Girdi: core/pit_panel.py::build_monthly_factors ciktisi (ay sonu x hisse satirlari,
yalniz o tarihte yayimlanmis tablolar + ileri getiri etiketi).

Tasarim notlari:
  - Faktorler "yuksek = beklenen daha iyi" yonune cevrilir (SIGNS); boylece tum
    IC/egimlerde pozitif deger literaturdeki yonun teyidi demektir.
  - Her ay kesitsel olarak %1/%99 winsorize + z-skor; aykiri degerler ve
    nominal TL olcek kaymasi (enflasyon) kesitsel siralamayi bozmaz.
  - Ortalama IC / FM egimi t-istatistigi Newey-West HAC ile: 6 aylik ileri
    getiri ust uste binen pencereler kullandigi icin duz t sisirilmis olur.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

# +1: yuksek deger beklenen yuksek getiri; -1: tersi (literatur yonu).
SIGNS: dict[str, int] = {
    "size": -1,            # kucuk hisse primi (Banz 1981)
    "bm": 1, "ep": 1, "sp": 1, "ey": 1,   # deger
    "gpa": 1, "roe": 1,    # karlilik (Novy-Marx 2013)
    "mom_12_1": 1,         # momentum (Jegadeesh-Titman 1993)
    "str_1m": -1,          # kisa vade donus (Jegadeesh 1990)
    "vol60": -1,           # dusuk volatilite anomalisi
    "nsi_rights_12m": -1,  # bedelli sermaye artirimi sonrasi dusuk getiri
    "sue": 1,              # kazanc surprizi sonrasi surukleme (PEAD)
}


def winsorize_z(s: pd.Series, lo: float = 0.01, hi: float = 0.99) -> pd.Series:
    s = s.astype(float)
    if s.notna().sum() < 3:
        return s * np.nan
    s = s.clip(s.quantile(lo), s.quantile(hi))
    sd = s.std()
    return (s - s.mean()) / sd if sd > 0 else s * np.nan


def prepare(panel: pd.DataFrame, factors: list[str], liq_drop_pct: float = 0.3,
            min_names: int = 30) -> pd.DataFrame:
    """Aylik evren filtresi + yon cevirme + kesitsel z-skor.

    liq_drop_pct: her ay 60g medyan TL hacmine gore en likit olmayan dilim atilir
    (uygulanamaz kucuk hisseler yaniltici prim uretir). min_names altindaki aylar atilir.
    """
    out = []
    for dt, g in panel.groupby("date"):
        g = g[g["tlvol60"].notna() & (g["tlvol60"] > 0)]
        if len(g) == 0:
            continue
        g = g[g["tlvol60"] >= g["tlvol60"].quantile(liq_drop_pct)].copy()
        if len(g) < min_names:
            continue
        for f in factors:
            g[f + "_z"] = winsorize_z(SIGNS.get(f, 1) * g[f])
        out.append(g)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def newey_west_t(x: pd.Series | np.ndarray, lags: int) -> tuple[float, float, int]:
    """Ortalama, HAC t-istatistigi (Bartlett cekirdegi), gozlem sayisi."""
    x = np.asarray(pd.Series(x).dropna(), dtype=float)
    n = len(x)
    if n < 3:
        return float("nan"), float("nan"), n
    m = x.mean()
    e = x - m
    var = e @ e / n
    for k in range(1, min(lags, n - 1) + 1):
        w = 1 - k / (lags + 1)
        var += 2 * w * (e[k:] @ e[:-k]) / n
    se = math.sqrt(var / n) if var > 0 else float("nan")
    return m, (m / se if se and se > 0 else float("nan")), n


def rank_ic(df: pd.DataFrame, col: str, ret: str, min_names: int = 30) -> pd.Series:
    """Aylik Spearman korelasyonu (faktor z-skoru vs ileri getiri)."""
    ics = {}
    for dt, g in df[["date", col, ret]].dropna().groupby("date"):
        if len(g) >= min_names:
            ics[dt] = g[col].rank().corr(g[ret].rank())
    return pd.Series(ics, dtype=float).sort_index()


def fama_macbeth(df: pd.DataFrame, cols: list[str], ret: str, min_names: int = 30) -> pd.DataFrame:
    """Her ay OLS: ret ~ 1 + cols. Satir = ay, sutun = egim (aylik getiri / 1 std)."""
    rows = {}
    for dt, g in df[["date", ret, *cols]].dropna().groupby("date"):
        if len(g) < max(min_names, len(cols) + 5):
            continue
        X = np.column_stack([np.ones(len(g)), g[cols].to_numpy(float)])
        y = g[ret].to_numpy(float)
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        rows[dt] = dict(zip(["const", *cols], beta))
    return pd.DataFrame.from_dict(rows, orient="index").sort_index()


def quintile_spread(df: pd.DataFrame, col: str, ret: str, n_q: int = 5,
                    min_names: int = 30) -> pd.DataFrame:
    """Esit agirlikli ust - alt dilim getirisi ve ust dilim devri (tek yon)."""
    rows = []
    prev_top: set = set()
    for dt, g in df[["date", "ticker", col, ret]].dropna().groupby("date"):
        if len(g) < min_names:
            continue
        q = pd.qcut(g[col].rank(method="first"), n_q, labels=False)
        top, bot = g[q == n_q - 1], g[q == 0]
        names = set(top["ticker"])
        turnover = 1 - len(names & prev_top) / len(names) if prev_top else 1.0
        rows.append({"date": dt, "top": top[ret].mean(), "bottom": bot[ret].mean(),
                     "universe": g[ret].mean(), "turnover": turnover})
        prev_top = names
    out = pd.DataFrame(rows)
    if not out.empty:
        out["spread"] = out["top"] - out["bottom"]
    return out
