"""Smart Money Concepts (SMC): piyasa yapisi, order block, fair value gap, bolgeler.

Kavram referansi: LuxAlgo "Smart Money Concepts" (TradingView, Pine v5). Bu dosya o
betigin satir satir cevirisi DEGIL; ayni genel ICT/SMC kavramlarinin gunluk barlar
icin nokta-zamanli (point-in-time) bir Python uygulamasidir.

Referansa gore farklar / gelistirmeler:
- Repaint yok: her olay, bilindigi barin tarihiyle kaydedilir. Bir pivot ancak
  `size` bar sonra (bacak degistiginde) bilinir; BOS/CHoCH kapanisla teyit edilir.
  `request.security(..., lookahead_on)` kullanilmaz (yalnizca grafik zaman dilimi).
- FVG esigi: referans govde yuzdesini (open * 100)'e bolerek hesapliyordu; burada
  govde orani (close - open) / open kullanilir, otomatik esik = gecmis mutlak
  oranlarin ortalamasinin 2 kati (yalnizca o ana kadarki barlar).
- Konfluans filtresi: referanstaki `min(close, open - low)` operator onceligi hatasi
  duzeltildi: alt fitil = min(open, close) - low.
- Cikti grafik degil veri: olay listesi + son durum (trend, aktif order block ve
  FVG'ler, premium/discount bolgesi, guclu/zayif tepe-dip). Rapor yalnizca bilgi
  olarak gosterir; alim-satim kurali olarak test edilmedi.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

BULLISH, BEARISH = 1, -1
BOS, CHOCH = "BOS", "CHoCH"


@dataclass
class Pivot:
    level: float = np.nan
    last_level: float = np.nan
    bar: int = -1
    crossed: bool = False


@dataclass
class OrderBlock:
    top: float
    bottom: float
    bar: int
    bias: int
    scope: str
    created_bar: int


@dataclass
class FairValueGap:
    top: float
    bottom: float
    bias: int
    bar: int


@dataclass
class SMCResult:
    events: pd.DataFrame
    order_blocks: list[OrderBlock]
    fvgs: list[FairValueGap]
    swing_bias: int
    internal_bias: int
    trailing_top: float
    trailing_bottom: float
    dates: pd.Index = field(repr=False, default=None)
    # states_at istenen barlarda o barin SONUNDAKI durum (yalnizca o bara kadarki veri)
    states: dict = field(repr=False, default_factory=dict)


def atr_wilder(high: np.ndarray, low: np.ndarray, close: np.ndarray, length: int) -> np.ndarray:
    """Wilder ATR (Pine ta.atr): ilk deger ilk `length` TR'nin ortalamasi, oncesi NaN."""
    prev = np.concatenate([[np.nan], close[:-1]])
    tr = np.nanmax(np.vstack([high - low, np.abs(high - prev), np.abs(low - prev)]), axis=0)
    out = np.full(len(tr), np.nan)
    if len(tr) < length:
        return out
    out[length - 1] = tr[:length].mean()
    for i in range(length, len(tr)):
        out[i] = (out[i - 1] * (length - 1) + tr[i]) / length
    return out


def _legs(high: np.ndarray, low: np.ndarray, size: int) -> np.ndarray:
    """Bar i'deki bacak: 0 = asagi (yeni tepe dogrulandi), 1 = yukari (yeni dip).
    Bar i-size'in tepesi, sonraki `size` barin hepsinden yuksekse tepe dogrulanir."""
    n = len(high)
    leg = np.zeros(n, dtype=int)
    cur = 0
    for i in range(n):
        if i >= size:
            window_h = high[i - size + 1: i + 1]
            window_l = low[i - size + 1: i + 1]
            if high[i - size] > window_h.max():
                cur = 0
            elif low[i - size] < window_l.min():
                cur = 1
        leg[i] = cur
    return leg


def analyze(df: pd.DataFrame, swing_size: int = 50, internal_size: int = 5, equal_size: int = 3,
            equal_threshold: float = 0.1, atr_length: int = 200, confluence_filter: bool = False,
            fvg_auto_threshold: bool = True, max_blocks: int = 100,
            states_at: set[int] | None = None) -> SMCResult:
    """df: open, high, low, close sutunlari (tarih sirali). Doner SMCResult.
    states_at: bu bar indekslerinde durum (order block, FVG, takip araligi, trendler)
    saklanir; analyze(df.iloc[:k + 1]) ile ayni sonucu verir, tek gecis yeterlidir."""
    o, h, lo, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    n = len(c)
    atr = atr_wilder(h, lo, c, atr_length)
    high_vol = np.where(np.isfinite(atr), (h - lo) >= 2 * atr, False)
    # Yuksek oynakli barin fitilleri order block siniri olarak guvenilmez: ters cevrilir
    p_high = np.where(high_vol, lo, h)
    p_low = np.where(high_vol, h, lo)

    legs = {k: _legs(h, lo, s) for k, s in (("swing", swing_size), ("internal", internal_size),
                                            ("equal", equal_size))}
    sizes = {"swing": swing_size, "internal": internal_size, "equal": equal_size}
    highs = {k: Pivot() for k in legs}
    lows = {k: Pivot() for k in legs}
    bias = {"swing": 0, "internal": 0}
    blocks: list[OrderBlock] = []
    fvgs: list[FairValueGap] = []
    events: list[dict] = []
    trail_top, trail_bot = np.nan, np.nan
    delta_sum, delta_n = 0.0, 0
    states: dict[int, dict] = {}

    def store_block(piv: Pivot, scope: str, direction: int, i: int) -> None:
        lo_i = max(piv.bar, 0)
        if lo_i >= i:
            return
        if direction == BEARISH:
            j = lo_i + int(np.argmax(p_high[lo_i:i]))
        else:
            j = lo_i + int(np.argmin(p_low[lo_i:i]))
        blocks.insert(0, OrderBlock(top=float(p_high[j]), bottom=float(p_low[j]), bar=j, bias=direction,
                                    scope=scope, created_bar=i))
        del blocks[max_blocks:]

    for i in range(n):
        # 1) yeni pivotlar (bacak degisimi, `size` bar gecikmeli)
        for k, leg in legs.items():
            if i == 0 or leg[i] == leg[i - 1]:
                continue
            s = sizes[k]
            if leg[i] == 1:  # dip dogrulandi
                piv, level = lows[k], lo[i - s]
                if k == "equal" and np.isfinite(piv.level) and np.isfinite(atr[i]) \
                        and abs(piv.level - level) < equal_threshold * atr[i]:
                    events.append({"bar": i, "kind": "EQL", "scope": "equal", "direction": BULLISH,
                                   "level": float(level), "ref_bar": piv.bar})
                if k == "swing":
                    trail_bot = level
            else:  # tepe dogrulandi
                piv, level = highs[k], h[i - s]
                if k == "equal" and np.isfinite(piv.level) and np.isfinite(atr[i]) \
                        and abs(piv.level - level) < equal_threshold * atr[i]:
                    events.append({"bar": i, "kind": "EQH", "scope": "equal", "direction": BEARISH,
                                   "level": float(level), "ref_bar": piv.bar})
                if k == "swing":
                    trail_top = level
            piv.last_level, piv.level, piv.crossed, piv.bar = piv.level, float(level), False, i - s

        # 2) takip eden tepe/dip (premium/discount ve guclu/zayif seviyeler icin)
        trail_top = h[i] if not np.isfinite(trail_top) else max(trail_top, h[i])
        trail_bot = lo[i] if not np.isfinite(trail_bot) else min(trail_bot, lo[i])

        # 3) yapi kirilimlari: once ic, sonra swing (referanstaki sira)
        upper_wick = h[i] - max(c[i], o[i])
        lower_wick = min(c[i], o[i]) - lo[i]
        bull_bar = upper_wick > lower_wick if confluence_filter else True
        bear_bar = upper_wick < lower_wick if confluence_filter else True
        for scope in ("internal", "swing"):
            ph, pl = highs[scope], lows[scope]
            extra_up = (ph.level != highs["swing"].level and bull_bar) if scope == "internal" else True
            extra_dn = (pl.level != lows["swing"].level and bear_bar) if scope == "internal" else True
            if i > 0 and np.isfinite(ph.level) and not ph.crossed and extra_up \
                    and c[i] > ph.level and c[i - 1] <= ph.level:
                tag = CHOCH if bias[scope] == BEARISH else BOS
                ph.crossed, bias[scope] = True, BULLISH
                events.append({"bar": i, "kind": tag, "scope": scope, "direction": BULLISH,
                               "level": ph.level, "ref_bar": ph.bar})
                store_block(ph, scope, BULLISH, i)
            if i > 0 and np.isfinite(pl.level) and not pl.crossed and extra_dn \
                    and c[i] < pl.level and c[i - 1] >= pl.level:
                tag = CHOCH if bias[scope] == BULLISH else BOS
                pl.crossed, bias[scope] = True, BEARISH
                events.append({"bar": i, "kind": tag, "scope": scope, "direction": BEARISH,
                               "level": pl.level, "ref_bar": pl.bar})
                store_block(pl, scope, BEARISH, i)

        # 4) order block azaltimi (fitil ile: high/low)
        blocks[:] = [b for b in blocks
                     if not ((b.bias == BEARISH and h[i] > b.top) or (b.bias == BULLISH and lo[i] < b.bottom))]

        # 5) fair value gap: azaltim, sonra yeni bosluk (yalnizca gecmis barlar)
        fvgs[:] = [g for g in fvgs
                   if not ((g.bias == BULLISH and lo[i] < g.bottom) or (g.bias == BEARISH and h[i] > g.top))]
        if i >= 2 and o[i - 1] > 0:
            delta = (c[i - 1] - o[i - 1]) / o[i - 1]
            delta_sum += abs(delta)
            delta_n += 1
            thr = 2 * delta_sum / delta_n if fvg_auto_threshold else 0.0
            if lo[i] > h[i - 2] and c[i - 1] > h[i - 2] and delta > thr:
                fvgs.insert(0, FairValueGap(top=float(lo[i]), bottom=float(h[i - 2]), bias=BULLISH, bar=i))
                events.append({"bar": i, "kind": "FVG", "scope": "fvg", "direction": BULLISH,
                               "level": float(h[i - 2]), "ref_bar": i - 1})
            elif h[i] < lo[i - 2] and c[i - 1] < lo[i - 2] and -delta > thr:
                fvgs.insert(0, FairValueGap(top=float(lo[i - 2]), bottom=float(h[i]), bias=BEARISH, bar=i))
                events.append({"bar": i, "kind": "FVG", "scope": "fvg", "direction": BEARISH,
                               "level": float(lo[i - 2]), "ref_bar": i - 1})

        if states_at and i in states_at:
            states[i] = {"order_blocks": list(blocks), "fvgs": list(fvgs), "swing_bias": bias["swing"],
                         "internal_bias": bias["internal"], "trailing_top": float(trail_top),
                         "trailing_bottom": float(trail_bot)}

    ev = pd.DataFrame(events, columns=["bar", "kind", "scope", "direction", "level", "ref_bar"])
    if len(ev) and isinstance(df.index, pd.Index):
        ev["date"] = df.index[ev["bar"].to_numpy()]
    return SMCResult(events=ev, order_blocks=list(blocks), fvgs=list(fvgs), swing_bias=bias["swing"],
                     internal_bias=bias["internal"], trailing_top=float(trail_top),
                     trailing_bottom=float(trail_bot), dates=df.index, states=states)


def zone(price: float, top: float, bottom: float) -> str | None:
    """Referanstaki bolgeler: ust %5 premium, alt %5 discount, orta %5 denge; arasi 'premium_half'
    veya 'discount_half'."""
    if not (np.isfinite(top) and np.isfinite(bottom)) or top <= bottom:
        return None
    pos = (price - bottom) / (top - bottom)
    if pos >= 0.95:
        return "premium"
    if pos <= 0.05:
        return "discount"
    if 0.475 <= pos <= 0.525:
        return "equilibrium"
    return "premium_half" if pos > 0.5 else "discount_half"


def snapshot(rows: list[dict], swing_size: int = 50, internal_size: int = 5) -> dict:
    """Fiyat satirlarindan (date, open, high, low, close) rapor ozeti. Yetersiz veride bos sozluk."""
    if not rows or len(rows) < max(3 * swing_size, 60):
        return {}
    df = pd.DataFrame(rows)[["date", "open", "high", "low", "close"]].dropna().set_index("date")
    if len(df) < max(3 * swing_size, 60):
        return {}
    res = analyze(df, swing_size=swing_size, internal_size=internal_size)
    price = float(df["close"].iloc[-1])
    structure = res.events[res.events["kind"].isin([BOS, CHOCH])] if len(res.events) else res.events
    last = structure.iloc[-1] if len(structure) else None
    bull_ob = [b for b in res.order_blocks if b.bias == BULLISH and b.top <= price]
    bear_ob = [b for b in res.order_blocks if b.bias == BEARISH and b.bottom >= price]
    near_bull = max(bull_ob, key=lambda b: b.top) if bull_ob else None
    near_bear = min(bear_ob, key=lambda b: b.bottom) if bear_ob else None
    trend = {BULLISH: "yukari", BEARISH: "asagi", 0: None}
    return {
        "smc_swing_trend": trend[res.swing_bias],
        "smc_internal_trend": trend[res.internal_bias],
        "smc_last_structure": (f"{last['scope']} {last['kind']} {'yukari' if last['direction'] == BULLISH else 'asagi'}"
                               if last is not None else None),
        "smc_last_structure_date": str(last["date"]) if last is not None and "date" in last else None,
        "smc_zone": zone(price, res.trailing_top, res.trailing_bottom),
        "smc_strong_high": res.swing_bias == BEARISH,
        "smc_bull_ob": [round(near_bull.bottom, 2), round(near_bull.top, 2)] if near_bull else None,
        "smc_bear_ob": [round(near_bear.bottom, 2), round(near_bear.top, 2)] if near_bear else None,
        "smc_open_fvg": len(res.fvgs),
    }
