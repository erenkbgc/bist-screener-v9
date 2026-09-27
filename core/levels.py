"""Destek / direnc seviyeleri: pivot + hacim profili + VWAP.

Neden: onceki giris bandi yalnizca ATR kesirleriydi (fiyat - 0.5*ATR ...).
Fiyat yapisini ve hacmi hic gormuyordu; stop "son 20 gunun en dusugu"ydu.

Literatur:
- Osler (2000, FRBNY EPR): firmalarin yayinladigi destek/direnc seviyelerinde
  fiyat trendi rastgele seviyelere gore anlamli sikca durur (bounce).
- Osler (2003, J. Finance 58(5)): kar-al emirleri yuvarlak rakamlarin hemen
  ONUNDE, stop emirleri hemen ARKASINDA kumelenir; seviye kirilinca stop
  kaskadi hareketi hizlandirir. -> stop seviyenin tam uzerine degil, bir
  tampon kadar otesine konur; hedef direncin hemen altina konur.
- Kavajecz & Odders-White (2004, RFS 17(4)): teknik destek/direnc seviyeleri
  limit emir defterindeki derinlik yogunlasmalariyla ortusur. Gunluk veride
  defter derinliginin vekili hacim profilidir (fiyat bandi basina islem hacmi).
- Brock, Lakonishok & LeBaron (1992, J. Finance 47(5)): trading-range-break
  kurali; Lo, Mamaysky & Wang (2000, J. Finance 55(4)): teknik formasyonlar
  hacim bilgisiyle birlikte ek bilgi tasir. -> kirilim ancak hacim onayiyla
  (volume_ratio >= 1.5) kabul edilir; kirilan direnc destege doner.
- Berkowitz, Logue & Noser (1988, J. Finance 43(1)): VWAP kurumsal icra
  referansi; fiyatin VWAP'tan uzakligi kovalama (chasing) maliyetinin vekili.

UYARI: bu kanitlarin cogu FX/ABD verisindendir. BIST olcumu
(scripts/backtest_entry_levels.py, 40 likit hisse, ~2 yil, 1883 sinyal,
2026-09-25): hedefi dirence tavanlamak islem basi getiriyi dusurdu (hisse
bazli t=-2.95; isabet artti ama kazananlar kesildi); destekten giris ve
yapisal stop ATR bandindan anlamli farkli degil (t=-0.65). Bu yuzden run.py
seviyeleri yalnizca bilgi olarak raporlar, karar kurallarina baglamaz.

Tum hesaplar duzeltilmis (bedelsiz/bolunme) olcekte yapilir ve BUGUNUN ham
fiyat olcegine cevrilir: bedelsiz oncesi pivotlar sahte direnc uretmez.
"""
from __future__ import annotations

PIVOT_K = 5                 # fractal pivot: her iki yanda k bar
CLUSTER_TOL_ATR = 0.5       # ayni bolgeye sayilacak pivotlar arasi max mesafe
RECENCY_HALF_LIFE = 60      # bar; eski dokunuslarin agirligi yarilanir
PROFILE_BINS = 60
BREAKOUT_VOLUME_RATIO = 1.5


def _adjusted_bars(rows: list[dict]) -> list[dict]:
    """Ham OHLC'yi duzeltilmis olcege, oradan bugunun ham olcegine tasir."""
    if not rows:
        return []
    last = rows[-1]
    last_adj = last.get("adj_close") or last["close"]
    to_today = last["close"] / last_adj if last_adj else 1.0
    out = []
    for r in rows:
        close = r.get("close")
        if not close or r.get("high") is None or r.get("low") is None:
            continue
        k = ((r.get("adj_close") or close) / close) * to_today
        out.append({
            "high": r["high"] * k, "low": r["low"] * k, "close": close * k,
            "volume": float(r.get("volume") or 0.0),
        })
    return out


def _pivots(bars: list[dict], k: int) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Onayli fractal pivotlar: sadece iki yaninda k bar olanlar (son k bar
    henuz onaylanmadigi icin dahil edilmez -> ileriye bakma yok)."""
    highs, lows = [], []
    for i in range(k, len(bars) - k):
        window = bars[i - k:i + k + 1]
        h, l = bars[i]["high"], bars[i]["low"]
        if h == max(b["high"] for b in window):
            highs.append((i, h))
        if l == min(b["low"] for b in window):
            lows.append((i, l))
    return highs, lows


def volume_profile(bars: list[dict], bins: int = PROFILE_BINS) -> tuple[list[float], list[float]]:
    """Her barin hacmini [low, high] araligina esit dagitir. Donus: (bin
    merkezleri, hacim). Gun ici tick verisi olmadigi icin standart yaklasim."""
    lo = min(b["low"] for b in bars)
    hi = max(b["high"] for b in bars)
    if hi <= lo:
        return [lo], [sum(b["volume"] for b in bars)]
    width = (hi - lo) / bins
    vol = [0.0] * bins
    for b in bars:
        if b["volume"] <= 0:
            continue
        a = int((b["low"] - lo) / width)
        z = min(bins - 1, int((b["high"] - lo) / width))
        a = min(a, z)
        share = b["volume"] / (z - a + 1)
        for j in range(a, z + 1):
            vol[j] += share
    centers = [lo + (j + 0.5) * width for j in range(bins)]
    return centers, vol


def _high_volume_nodes(centers: list[float], vol: list[float]) -> list[tuple[float, float]]:
    """Yerel maksimum ve ortalamanin ustundeki hacim dugumleri (HVN).
    Donus: (fiyat, toplam hacim payi)."""
    total = sum(vol) or 1.0
    mean = total / len(vol)
    sd = (sum((v - mean) ** 2 for v in vol) / len(vol)) ** 0.5
    nodes = []
    for j in range(len(vol)):
        left = vol[j - 1] if j > 0 else -1.0
        right = vol[j + 1] if j < len(vol) - 1 else -1.0
        # ortalama + 1 stdev: duz profilde her kucuk tumsek dugum sayilmaz
        if vol[j] > mean + sd and vol[j] >= left and vol[j] >= right:
            nodes.append((centers[j], vol[j] / total))
    return nodes


def rolling_vwap(bars: list[dict], window: int = 20) -> float | None:
    w = bars[-window:]
    pv = sum(((b["high"] + b["low"] + b["close"]) / 3.0) * b["volume"] for b in w)
    v = sum(b["volume"] for b in w)
    return pv / v if v > 0 else None


def find_levels(rows: list[dict], atr: float, lookback: int = 250) -> dict:
    """Destek/direnc bolgeleri.

    1. Onayli pivot yuksek/dusukler (fractal, k=5).
    2. Her pivotun agirligi = zaman azalimi * (1 + pivot gunu goreli hacmi).
    3. Hacim profilindeki yuksek hacim dugumleri (HVN) ek aday seviye.
    4. ATR*0.5 tolerans ile kumeleme -> bolge (low, high, mid, score, touches).
    Seviyeler bugunun fiyatina gore destek / direnc olarak ayrilir.
    """
    bars = _adjusted_bars(rows)[-lookback:]
    if len(bars) < 2 * PIVOT_K + 5 or not atr or atr <= 0:
        return {"supports": [], "resistances": [], "vwap20": None, "poc": None, "price": None}

    n = len(bars)
    price = bars[-1]["close"]
    avg_vol = (sum(b["volume"] for b in bars) / n) or 1.0
    highs, lows = _pivots(bars, PIVOT_K)

    candidates: list[tuple[float, float]] = []  # (fiyat, agirlik)
    for i, p in highs + lows:
        age = n - 1 - i
        decay = 0.5 ** (age / RECENCY_HALF_LIFE)
        rel_vol = min(3.0, bars[i]["volume"] / avg_vol)
        candidates.append((p, decay * (1.0 + rel_vol)))

    centers, vol = volume_profile(bars)
    poc = centers[max(range(len(vol)), key=vol.__getitem__)] if vol else None
    for p, share in _high_volume_nodes(centers, vol):
        # hacim payi -> pivot agirligiyla ayni mertebe (tipik pivot ~1-2)
        candidates.append((p, share * 20.0))

    candidates.sort()
    tol = CLUSTER_TOL_ATR * atr
    zones: list[dict] = []
    for p, w in candidates:
        # bolge genisligi en fazla 2*tol (1 ATR): tek baglantili kumeleme
        # yakin seviyeleri zincirleyip tum araligi tek bolgeye cevirmesin
        if zones and p - zones[-1]["high"] <= tol and p - zones[-1]["low"] <= 2 * tol:
            z = zones[-1]
            z["high"] = max(z["high"], p)
            z["_wsum"] += w * p
            z["score"] += w
            z["touches"] += 1
        else:
            zones.append({"low": p, "high": p, "_wsum": w * p, "score": w, "touches": 1})
    for z in zones:
        z["mid"] = z.pop("_wsum") / z["score"] if z["score"] else (z["low"] + z["high"]) / 2
        z["score"] = round(z["score"], 3)

    # Tek dokunuslu, zayif bolgeler gurultudur
    zones = [z for z in zones if z["touches"] >= 2 or z["score"] >= 1.5]

    supports = sorted((z for z in zones if z["mid"] < price), key=lambda z: -z["mid"])
    resistances = sorted((z for z in zones if z["mid"] >= price), key=lambda z: z["mid"])
    return {
        "supports": supports,
        "resistances": resistances,
        "vwap20": rolling_vwap(bars),
        "poc": poc,
        "price": price,
    }


def recent_breakout(rows: list[dict], levels: dict, atr: float, window: int = 5) -> dict | None:
    """Son `window` gunde hacim onayli (volume_ratio >= 1.5) kapanisla kirilan
    destek bolgesi (eski direnc). Rol degisimi: kirilan direnc artik destek."""
    recent = rows[-window:]
    confirmed = any((r.get("volume_ratio_20d") or 0) >= BREAKOUT_VOLUME_RATIO for r in recent)
    if not confirmed or not levels.get("supports"):
        return None
    bars = _adjusted_bars(rows)
    start_close = bars[-window - 1]["close"] if len(bars) > window else None
    if start_close is None:
        return None
    for z in levels["supports"]:
        if start_close < z["low"] and z["high"] < levels["price"]:
            return z
    return None


def plan_entry(price: float, atr: float, levels: dict, max_support_dist_atr: float = 2.0,
               breakout_zone: dict | None = None) -> dict:
    """Seviyeye dayali giris / stop / hedef onerisi (ham fiyat).

    - Giris alt ucu: fiyatin en fazla 2 ATR altindaki en guclu destek bolgesinin
      hemen ustu (+0.1 ATR; emir defterinde seviyedeki kalabaligin onunde).
      Hacim onayli kirilim varsa kirilan direnc (yeniden test) kullanilir.
    - Giris ust ucu: fiyat + 0.2 ATR, ama en yakin direncin 0.5 ATR altini asmaz
      (direncin dibinden alim: odul/risk bozuk).
    - Fiyat 20g VWAP'in 1.5 ATR'den fazla ustundeyse ust uc VWAP+0.5 ATR'e
      cekilir (kovalama).
    - Stop: destek bolgesinin alt ucu - 0.5 ATR (Osler 2003: stoplar seviyenin
      hemen arkasinda kumelenir, kaskada yakalanmamak icin tampon).
    - Hedef: en yakin direncin alt ucu - 0.1 ATR (kar-al emirleri seviyenin onunde).
    Uygun destek yoksa None doner; cagiran ATR bandina duser.
    """
    if not atr or atr <= 0 or price <= 0:
        return {"method": "atr_fallback"}

    support = breakout_zone
    if support is None:
        near = [z for z in levels.get("supports", []) if price - z["mid"] <= max_support_dist_atr * atr]
        support = max(near, key=lambda z: z["score"]) if near else None
    resistance = next((z for z in levels.get("resistances", []) if z["low"] > price + 0.25 * atr), None)

    out: dict = {"method": "atr_fallback", "support_zone": support, "resistance_zone": resistance,
                 "vwap20": levels.get("vwap20"), "poc": levels.get("poc")}
    if support is None:
        return out

    entry_low = min(price, support["high"] + 0.1 * atr)
    entry_high = price + 0.2 * atr
    if resistance is not None:
        entry_high = min(entry_high, resistance["low"] - 0.5 * atr)
    vwap = levels.get("vwap20")
    if vwap and price - vwap > 1.5 * atr:
        entry_high = min(entry_high, vwap + 0.5 * atr)
    if entry_high < entry_low:
        # direnc/VWAP destege cok yakin: tek fiyatli limit emir
        entry_high = entry_low

    out.update({
        "method": "breakout_retest" if breakout_zone is not None else "support",
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop": support["low"] - 0.5 * atr,
        "target": (resistance["low"] - 0.1 * atr) if resistance is not None else None,
    })
    return out


def summarize(levels: dict, n: int = 3) -> dict:
    """Rapor/payload icin kisa ozet (en yakin n destek ve direnc orta noktalari)."""
    def mids(zs):
        return [round(z["mid"], 2) for z in zs[:n]]
    return {
        "supports": mids(levels.get("supports", [])),
        "resistances": mids(levels.get("resistances", [])),
        "vwap20": round(levels["vwap20"], 2) if levels.get("vwap20") else None,
        "poc": round(levels["poc"], 2) if levels.get("poc") else None,
    }


__all__ = ["find_levels", "plan_entry", "recent_breakout", "volume_profile", "rolling_vwap", "summarize"]
