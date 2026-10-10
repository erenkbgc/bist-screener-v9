"""Rotasyon ve cikis kurallari simulasyonu (docs/research/exit_rules_preregistration.md).

Aylik dengeleme, esit agirlik; ay icinde gunluk duzeltilmis kapanisla stop
kontrolu. Stop satisi tetik gunu kapanisindan; gelir ay sonuna kadar XU100'de.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

COST_BPS = 20.0


@dataclass(frozen=True)
class Rule:
    name: str
    keep_pct: float = 0.2          # elde tutma esigi (siralama yuzdeligi, 0 = en iyi)
    trailing: float | None = None  # zirveden dusus orani (0.25 = -%25)
    fixed: float | None = None     # giristen dusus orani
    atr_mult: float | None = None  # giris - k*ATR20
    thesis: bool = False           # ep < 0 veya f7 <= 2 ise sat


RULES = {
    "R0": Rule("R0", keep_pct=0.2),
    "R1": Rule("R1", keep_pct=0.4),
    "R2": Rule("R2", keep_pct=0.6),
    "X1": Rule("X1", keep_pct=0.4, trailing=0.25),
    "X2": Rule("X2", keep_pct=0.4, fixed=0.20),
    "X3": Rule("X3", keep_pct=0.4, atr_mult=2.0),
    "X4": Rule("X4", keep_pct=0.4, thesis=True),
}
BASE_OF = {"R1": "R0", "R2": "R0", "X1": "R1", "X2": "R1", "X3": "R1", "X4": "R1"}


def stop_level(rule: Rule, entry: float, peak: float, atr: float) -> float:
    lv = -np.inf
    if rule.trailing is not None:
        lv = max(lv, peak * (1 - rule.trailing))
    if rule.fixed is not None:
        lv = max(lv, entry * (1 - rule.fixed))
    if rule.atr_mult is not None and np.isfinite(atr) and atr > 0:
        lv = max(lv, entry - rule.atr_mult * atr)
    return lv


def simulate(rule: Rule, months: list[pd.Timestamp], universe: dict[pd.Timestamp, pd.DataFrame],
             close: pd.DataFrame, atr: pd.DataFrame, xu: pd.Series, d0_of: dict[pd.Timestamp, pd.Timestamp]
             ) -> tuple[pd.DataFrame, list[dict]]:
    """universe[t]: ticker indeksli; rank_pct, ep, f7, bench, bench_usd, fx_ret kolonlari.
    close/atr: islem gunu x ticker (duzeltilmis). Doner: aylik satirlar ve stop olaylari."""
    holdings: dict[str, dict] = {}
    rows, stops = [], []
    for k, t in enumerate(months[:-1]):
        g = universe[t]
        d0, d1 = d0_of[t], d0_of[months[k + 1]]
        top = set(g.index[g["rank_pct"] <= 0.2])
        keep = set()
        for tk in holdings:
            if tk not in g.index or g.at[tk, "rank_pct"] > rule.keep_pct:
                continue
            if rule.thesis and ((g.at[tk, "ep"] < 0) or (g.at[tk, "f7"] <= 2)):
                continue
            keep.add(tk)
        new_set = keep | top
        window = close.loc[d0:d1]
        valid = [tk for tk in new_set if tk in window.columns and np.isfinite(window[tk].iloc[0])]
        if not valid:
            holdings = {}
            continue
        bought = [tk for tk in valid if tk not in holdings or tk not in keep]
        turnover = len(bought) / len(valid) if holdings else 1.0
        new_holdings = {}
        for tk in valid:
            if tk in keep and tk in holdings:
                new_holdings[tk] = holdings[tk]
            else:
                p = float(window[tk].iloc[0])
                a = float(atr.at[d0, tk]) if tk in atr.columns else np.nan
                new_holdings[tk] = {"entry": p, "peak": p, "atr": a}
        xu_w = xu.loc[d0:d1]
        rets, stop_cost = [], 0.0
        survivors = {}
        for tk, st in new_holdings.items():
            path = window[tk].ffill().to_numpy()
            p0 = path[0]
            r, stopped = path[-1] / p0 - 1, False
            if has_stop(rule):
                peak = st["peak"]
                for j in range(1, len(path)):
                    peak = max(peak, path[j])
                    if path[j] <= stop_level(rule, st["entry"], peak, st["atr"]):
                        r = path[j] / p0 * (xu_w.iloc[-1] / xu_w.iloc[j]) - 1
                        stopped = True
                        stop_cost += COST_BPS / 1e4  # stop satisi, tek yon
                        stops.append({"date": window.index[j], "ticker": tk, "pos": j})
                        break
                st = {**st, "peak": peak}
            rets.append(r)
            if not stopped:
                survivors[tk] = st
        holdings = survivors
        port = float(np.mean(rets))
        cost = 2 * turnover * COST_BPS / 1e4 + stop_cost / len(rets)
        fx = g["fx_ret"].iloc[0]
        port_usd = (1 + port - cost) / (1 + fx) - 1
        rows.append({"date": t, "n": len(rets), "turnover": turnover,
                     "n_stops": len(rets) - len(survivors),
                     "port": port, "cost": cost,
                     "active": port - cost - g["bench"].iloc[0],
                     "active_usd": port_usd - g["bench_usd"].iloc[0],
                     "total_usd": port_usd})
    return pd.DataFrame(rows), stops


def has_stop(rule: Rule) -> bool:
    return bool(rule.trailing or rule.fixed or rule.atr_mult)
