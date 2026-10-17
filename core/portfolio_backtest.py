"""Canli kural portfoy backtest'i (docs/research/portfolio_backtest_preregistration.md).

Gunluk defter: pozisyonlar duzeltilmis kapanisla kayar, nakit politika faizinden
gunluk faiz alir. Aylik karar d0 (ay sonu <= t son islem gunu) kapanisinda, islem
d0'dan sonraki ilk gunun kapanisinda (duyarlilik: acilisinda). Maliyet: komisyon +
likidite dilimine gore yarim spread + karekok piyasa etkisi.

Sermaye seviyesi reel olarak sabit tutulur: islem buyuklugu Q = |agirlik degisimi| x
capital_tl[t]. Getiriler NAV orani uzerinden hesaplanir.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

DELIST_DAYS = 20
PARTICIPATION_FLAG = 0.10


@dataclass(frozen=True)
class Costs:
    commission_bps: float = 10.0
    spread_bps: tuple[float, float, float] = (5.0, 15.0, 30.0)  # likidite ust/orta/alt ucte bir
    impact_k: float = 1.0
    impact_cap: float = 0.10
    mult: float = 1.0  # stres senaryosu: 2.0

    def half_spread(self, liq_pct: float) -> float:
        if not np.isfinite(liq_pct):
            return self.spread_bps[2] / 1e4
        if liq_pct >= 2 / 3:
            return self.spread_bps[0] / 1e4
        if liq_pct >= 1 / 3:
            return self.spread_bps[1] / 1e4
        return self.spread_bps[2] / 1e4

    def impact(self, sigma_d: float, q_tl: float, adv_tl: float) -> float:
        if not (np.isfinite(sigma_d) and np.isfinite(adv_tl)) or adv_tl <= 0:
            return self.impact_cap
        return min(self.impact_cap, self.impact_k * sigma_d * np.sqrt(q_tl / adv_tl))


@dataclass
class Market:
    """Islem gunu x ticker matrisleri; NaN = o gun islem yok."""
    close: pd.DataFrame
    open: pd.DataFrame
    adv: pd.DataFrame     # 60g medyan TL hacmi (ham kapanis x adet)
    sigma: pd.DataFrame   # 60g gunluk getiri std'si
    rf_daily: pd.Series   # islem gunu indeksli


def policy_rf_daily(policy_pct: pd.Series, days: pd.DatetimeIndex) -> pd.Series:
    """Aylik politika faizinden (% yillik, PeriodIndex 'M') gunluk nakit getirisi.
    Serinin bittigi aylarda son bilinen faiz kullanilir."""
    rate = policy_pct.ffill().reindex(days.to_period("M")).ffill().to_numpy()
    return pd.Series((1 + rate / 100) ** (1 / 252) - 1, index=days)


def liq_percentile(adv: float, universe_liq: np.ndarray) -> float:
    """adv'nin o ayki likit evren tlvol60 dagilimindaki yuzdeligi (0..1)."""
    if not np.isfinite(adv) or len(universe_liq) == 0:
        return np.nan
    return float(np.searchsorted(universe_liq, adv, side="right") / len(universe_liq))


def simulate(targets: dict[pd.Timestamp, list[str] | None], months: list[pd.Timestamp],
             d0_of: dict[pd.Timestamp, pd.Timestamp], mkt: Market,
             universe_liq: dict[pd.Timestamp, np.ndarray], capital_tl: dict[pd.Timestamp, float],
             costs: Costs = Costs(), fill: str = "close", haircut: float = 0.0) -> pd.DataFrame:
    """Doner: ay t satirlari (d0_t -> d0_{t+1} NAV getirisi ve t dengelemesinin maliyeti).

    targets[t] None ise t'de islem yapilmaz (karar uretilemeyen ay, ileriye donuk
    kayit): pozisyonlar tasinir, satir maliyetsiz ve devir 0 olarak yazilir."""
    days = mkt.close.index
    pos_of = {d: i for i, d in enumerate(days)}
    close = mkt.close.to_numpy(dtype=float)
    opn = mkt.open.to_numpy(dtype=float)
    adv = mkt.adv.to_numpy(dtype=float)
    sig = mkt.sigma.to_numpy(dtype=float)
    rf = mkt.rf_daily.reindex(days).fillna(0.0).to_numpy(dtype=float)
    col = {tk: j for j, tk in enumerate(mkt.close.columns)}

    fill_day = {}
    for t in months[:-1]:
        i0 = pos_of[d0_of[t]]
        if i0 + 1 < len(days):
            fill_day[i0 + 1] = t

    values: dict[str, float] = {}
    last_px: dict[str, float] = {}
    miss: dict[str, int] = {}
    cash = 1.0
    month_log: dict[pd.Timestamp, dict] = {}
    delist_events = 0

    def mark(i: int, px: np.ndarray, count_missing: bool) -> None:
        nonlocal cash, delist_events
        for tk in list(values):
            p = px[i, col[tk]]
            if np.isfinite(p):
                values[tk] *= p / last_px[tk]
                last_px[tk] = p
                if count_missing:
                    miss[tk] = 0
            elif count_missing:
                miss[tk] += 1
                if miss[tk] >= DELIST_DAYS:
                    cash += values.pop(tk) * (1 - haircut)
                    last_px.pop(tk)
                    miss.pop(tk)
                    delist_events += 1

    def rebalance(i: int, t: pd.Timestamp, px: np.ndarray) -> None:
        nonlocal cash
        if t in targets and targets[t] is None:
            month_log[t] = {"commission": 0.0, "spread": 0.0, "impact": 0.0, "buy": 0.0, "fills": 0,
                            "fills_over_10pct_adv": 0, "n_held": len(values)}
            return
        nav = cash + sum(values.values())
        cap = capital_tl[t]
        ref = i - 1  # d0: islem oncesi bilinen ADV/sigma
        wanted = [tk for tk in targets.get(t, []) if tk in col and np.isfinite(px[i, col[tk]])]
        stuck = {tk for tk in values if not np.isfinite(px[i, col[tk]])}
        tradable = nav - sum(values[tk] for tk in stuck)
        tgt = {tk: tradable / len(wanted) for tk in wanted} if wanted else {}
        log = {"commission": 0.0, "spread": 0.0, "impact": 0.0, "buy": 0.0, "fills": 0, "fills_over_10pct_adv": 0}
        for tk in set(values) - stuck | set(tgt):
            dv = tgt.get(tk, 0.0) - values.get(tk, 0.0)
            if abs(dv) < 1e-12:
                continue
            j = col[tk]
            q = abs(dv) / nav * cap
            a = adv[ref, j]
            lp = liq_percentile(a, universe_liq.get(t, np.array([])))
            c_comm = costs.mult * costs.commission_bps / 1e4
            c_spr = costs.mult * costs.half_spread(lp)
            c_imp = costs.mult * costs.impact(sig[ref, j], q, a)
            log["commission"] += abs(dv) * c_comm / nav
            log["spread"] += abs(dv) * c_spr / nav
            log["impact"] += abs(dv) * c_imp / nav
            log["buy"] += max(dv, 0.0) / nav
            log["fills"] += 1
            if not np.isfinite(a) or q > PARTICIPATION_FLAG * a:
                log["fills_over_10pct_adv"] += 1
        total_cost = (log["commission"] + log["spread"] + log["impact"]) * nav
        scale = (tradable - total_cost) / tradable if tradable > 0 else 1.0
        new_values = {tk: values[tk] for tk in stuck}
        for tk, v in tgt.items():
            new_values[tk] = v * scale
            last_px[tk] = px[i, col[tk]]
            miss[tk] = 0
        for tk in set(values) - set(new_values):
            last_px.pop(tk, None)
            miss.pop(tk, None)
        values.clear()
        values.update(new_values)
        cash = (tradable - sum(tgt.values())) * scale if tgt else tradable - total_cost
        log["n_held"] = len(wanted)
        month_log[t] = log

    start = pos_of[d0_of[months[0]]]
    nav_at: dict[pd.Timestamp, float] = {}
    d0_idx = {pos_of[d0_of[t]]: t for t in months}
    for i in range(start, len(days)):
        if i > start:
            cash *= 1 + rf[i]
            t = fill_day.get(i)
            if t is not None and fill == "open":
                mark(i, opn, count_missing=False)
                rebalance(i, t, opn)
                mark(i, close, count_missing=True)
            else:
                mark(i, close, count_missing=True)
                if t is not None:
                    rebalance(i, t, close)
        if i in d0_idx:
            nav_at[d0_idx[i]] = cash + sum(values.values())

    rows = []
    for k, t in enumerate(months[:-1]):
        t1 = months[k + 1]
        if t not in nav_at or t1 not in nav_at or t not in month_log:
            continue
        lg = month_log[t]
        rows.append({"date": t, "port": nav_at[t1] / nav_at[t] - 1,
                     "cost": lg["commission"] + lg["spread"] + lg["impact"],
                     "commission": lg["commission"], "spread": lg["spread"], "impact": lg["impact"],
                     "turnover": lg["buy"], "fills": lg["fills"],
                     "fills_over_10pct_adv": lg["fills_over_10pct_adv"], "n": lg["n_held"]})
    out = pd.DataFrame(rows)
    out.attrs["delist_events"] = delist_events
    return out
