"""Aday teshis katmani: "neden listede, ne riskli?" -- YALNIZCA BILGI.

Level-up plani Faz 1: 5 yilda %80 dusmus hisseler "firsat" olarak listeye
dusuyordu. Degerleme carpanlari fiyat cokunce kuculur ve valuation_z buyur;
skor bunu odul olarak okur. Bu modul her aday icin cokusu ve sikinti
belirtilerini gorunur kilar. Karar mantigini DEGISTIRMEZ: esikler henuz test
edilmedi (Faz 2 on-kaydi H1/H2 bu bayraklari test edecek). Test gecmeyen katman
yalnizca bilgi olarak gosterilir (README "kanit" ilkesi).

Alanlar (hepsi yuzde puan, ham degil duzeltilmis kapanis):
  drawdown_from_5y_peak_pct : son kapanis / 5 yillik zirve - 1 (<= 0)
  max_drawdown_5y_pct       : 5 yil icindeki en derin tepe-dip dususu (<= 0)
  dist_52w_high_pct         : son kapanis / 52 haftalik zirve - 1 (<= 0)
  price_history_years       : teshisin dayandigi gecmis uzunlugu (yil)
  loss_flag                 : TTM hisse basi kar < 0
  distress_flag             : sanayi profilinde negatif ozsermaye, negatif
                              FAVOK + net borc ya da asiri kaldirac / zayif faiz
                              karsilama. Banka/sigorta icin None (bilanco yapisi
                              farkli; bu kurallar anlamsiz).
  risk_flags                : sablonda gosterilen kisa Turkce etiketler. SAYI
                              ICERMEZ: report/validate.py orphan kontrolu metin
                              icindeki sayilari payload'da bulamaz.
"""
from __future__ import annotations

import math

TRADING_DAYS_PER_YEAR = 252
LOOKBACK_DAYS = 5 * TRADING_DAYS_PER_YEAR

# Gosterim esikleri (test edilmemis; Faz 2'de on-kayitla sinanacak).
CRASH_FROM_PEAK_PCT = -70.0
FAR_FROM_52W_HIGH_PCT = -40.0
NET_DEBT_EBITDA_MAX = 4.0
INTEREST_COVERAGE_MIN = 1.5

FLAG_LABELS = {
    "crash_5y": "beş yıllık zirvenin çok altında",
    "far_52w": "son bir yılın zirvesinden uzak",
    "loss": "zarar ediyor",
    "distress": "borç / sıkıntı belirtisi",
    "short_history": "fiyat geçmişi kısa",
}


def _num(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _adj_closes(price_rows: list[dict]) -> list[float]:
    out = []
    for r in price_rows:
        v = _num(r.get("adj_close"))
        if v is None:
            v = _num(r.get("close"))
        if v is not None and v > 0:
            out.append(v)
    return out


def price_diagnostics(price_rows: list[dict]) -> dict:
    closes = _adj_closes(price_rows[-LOOKBACK_DAYS:])
    if len(closes) < 2:
        return {"drawdown_from_5y_peak_pct": None, "max_drawdown_5y_pct": None,
                "dist_52w_high_pct": None, "price_history_years": None}
    last = closes[-1]
    running = closes[0]
    max_dd = 0.0
    for c in closes:
        running = max(running, c)
        max_dd = min(max_dd, c / running - 1)
    peak = max(closes)
    high_52w = max(closes[-TRADING_DAYS_PER_YEAR:])
    return {
        "drawdown_from_5y_peak_pct": round((last / peak - 1) * 100, 2),
        "max_drawdown_5y_pct": round(max_dd * 100, 2),
        "dist_52w_high_pct": round((last / high_52w - 1) * 100, 2),
        "price_history_years": round(len(closes) / TRADING_DAYS_PER_YEAR, 2),
    }


def distress_flag(c: dict) -> bool | None:
    if c.get("ratio_profile") in ("bank", "insurance"):
        return None
    pb = _num(c.get("pb"))
    ebitda = _num(c.get("ebitda_ttm"))
    net_debt = _num(c.get("net_debt"))
    nd_ebitda = _num(c.get("net_debt_ebitda"))
    fin_exp = _num(c.get("financial_expenses_ttm"))
    if pb is not None and pb < 0:
        return True
    if ebitda is not None and ebitda <= 0 and net_debt is not None and net_debt > 0:
        return True
    if nd_ebitda is None and ebitda and net_debt is not None and ebitda > 0:
        nd_ebitda = net_debt / ebitda
    if nd_ebitda is not None and nd_ebitda > NET_DEBT_EBITDA_MAX:
        return True
    if ebitda is not None and fin_exp and abs(fin_exp) > 0:
        if ebitda / abs(fin_exp) < INTEREST_COVERAGE_MIN:
            return True
    known = [v for v in (pb, ebitda, net_debt, nd_ebitda) if v is not None]
    return False if known else None


def diagnose(c: dict, price_rows: list[dict]) -> dict:
    out = price_diagnostics(price_rows)
    eps = _num(c.get("eps_ttm"))
    out["loss_flag"] = (eps < 0) if eps is not None else None
    out["distress_flag"] = distress_flag(c)

    flags = []
    dd = out["drawdown_from_5y_peak_pct"]
    if dd is not None and dd <= CRASH_FROM_PEAK_PCT:
        flags.append("crash_5y")
    d52 = out["dist_52w_high_pct"]
    if d52 is not None and d52 <= FAR_FROM_52W_HIGH_PCT:
        flags.append("far_52w")
    if out["loss_flag"]:
        flags.append("loss")
    if out["distress_flag"]:
        flags.append("distress")
    years = out["price_history_years"]
    if years is not None and years < 4.5:
        flags.append("short_history")
    out["risk_flag_codes"] = flags
    out["risk_flags"] = [FLAG_LABELS[f] for f in flags]
    return out
