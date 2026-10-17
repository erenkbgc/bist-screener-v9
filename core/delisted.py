"""Borsadan cikmis hisseleri arastirma paneline ekleme
(docs/research/survivorship_delisted_preregistration.md).

Kaynak: Is Yatirim ``Common/Data.aspx/HisseTekil`` gunluk satirlari. borsapy
cikmis kodlar icin "invalid symbol" verir; Is Yatirim fiyat, duzeltilmis fiyat,
TL hacim ve odenmis sermayeyi (SERMAYE) cikis tarihine kadar saklar.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

TRADE_START = pd.Timestamp("2013-05-01")
TRADE_END = pd.Timestamp("2026-09-30")

# Banka / sigorta / menkul kiymet yatirim ortakligi; ISATR/ISBTR/ISKUR hala islem goruyor.
FINANCIAL_CODES = {"TEBNK", "DENIZ", "HALKS", "YKBYO", "TSKYO", "YKFIN", "ISATR", "ISBTR", "ISKUR"}

# On-kayittaki elle sektor tablosu; listede olmayan kod BILINMIYOR_<kod> alir.
SECTORS: dict[str, str] = {
    **dict.fromkeys(["ADANA", "ADBGR", "ADNAC", "ASLAN", "BOLUC", "UNYEC"], "Taş, Toprak, Çimento"),
    **dict.fromkeys(["ANACM", "TRKCM", "DENCM", "ECYAP"], "Cam, Seramik, Porselen"),
    **dict.fromkeys(["SODA", "PIMAS"], "Kimya ve Plastik"),
    **dict.fromkeys(["AKFEN", "DYHOL", "KPHOL", "EGCYH", "TRNSK", "ARTI"], "Holding"),
    "NTTUR": "Turizm",
    **dict.fromkeys(["KIPA", "KILER"], "Gıda Perakendeciliği"),
    "BOYP": "Giyim, Tekstil ve Deri Ürünleri Perakendeciliği",
    **dict.fromkeys(["MEMSA", "ESEMS"], "Tekstil, Giyim ve Deri"),
    "SAFGY": "Gayrimenkul",
    "OLMK": "Ambalaj",
    "ANELT": "İnşaat",
    "EGCEY": "Enerji Üretim ve Dağıtım",
}

CORPORATE_PATTERN = re.compile(
    r"Devrolma|Birleşme|Satma Hakkı|Ortaklıktan Çıkarma|Pay Alım Teklifi|Borsa Kotundan Çıkma",
    re.IGNORECASE,
)
KNOWN_CORPORATE = {"AKFEN", "BOYP", "DGZTE", "IZOCM"}  # S4

# (kurumsal cikis D, diger cikis D, bilinen duzeltmeler uygulanir mi)
SPECS: dict[str, tuple[float, float, bool]] = {
    "S1": (0.0, -0.30, False),
    "S2": (0.0, 0.0, False),
    "S3": (0.0, -1.00, False),
    "S4": (0.0, -0.30, True),
    "S5": (-1.00, -1.00, False),
}


def sector_of(code: str) -> str:
    return SECTORS.get(code, f"BILINMIYOR_{code}")


def daily_frame(rows: list[dict]) -> pd.DataFrame:
    """HisseTekil satirlari -> tarih indeksli gunluk tablo (son islem gunune kadar)."""
    if not rows:
        return pd.DataFrame()
    d = pd.DataFrame(rows)
    d.index = pd.to_datetime(d["HGDG_TARIH"], format="%d-%m-%Y")
    d = d.sort_index()
    traded = d[d["HGDG_HACIM"].fillna(0) > 0]
    if traded.empty:
        return pd.DataFrame()
    return d.loc[: traded.index.max()]


def last_trade(daily: pd.DataFrame) -> pd.Timestamp | None:
    return None if daily.empty else daily.index.max()


def price_frames(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """borsapy history bicimi: (ham, duzeltilmis); Volume * ham kapanis = TL hacim."""
    raw_close = daily["HG_KAPANIS"].astype(float)
    vol = daily["HGDG_HACIM"].astype(float) / raw_close.where(raw_close > 0)
    raw = pd.DataFrame({"Close": raw_close, "Volume": vol.fillna(0.0)})
    adj = pd.DataFrame({"Close": daily["HGDG_KAPANIS"].astype(float), "Volume": vol.fillna(0.0)})
    return raw, adj


def share_events(code: str, daily: pd.DataFrame) -> pd.DataFrame:
    """SERMAYE degisimleri -> pit_panel.split_events bicimi (hepsi bonus_pct)."""
    cap = daily["SERMAYE"].astype(float).replace(0, np.nan).dropna()
    chg = cap / cap.shift(1)
    chg = chg[(chg.notna()) & ((chg - 1).abs() > 1e-6)]
    return pd.DataFrame({"ticker": code, "date": chg.index, "rights_pct": 0.0,
                         "bonus_pct": 100.0 * (chg.values - 1.0)})


def classify_exit(kap: pd.DataFrame, code: str, last: pd.Timestamp) -> str:
    """kap: stock_code (tek kod), published_at, subject, summary."""
    w = kap[(kap["stock_code"] == code)
            & (kap["published_at"] >= last - pd.DateOffset(months=18))
            & (kap["published_at"] <= last + pd.DateOffset(months=6))]
    text = w["subject"].fillna("") + " " + w["summary"].fillna("")
    return "corporate" if text.str.contains(CORPORATE_PATTERN).any() else "other"


def exit_return(spec: str, exit_class: str, code: str) -> float:
    d_corp, d_other, known = SPECS[spec]
    if known and code in KNOWN_CORPORATE:
        exit_class = "corporate"
    return d_corp if exit_class == "corporate" else d_other


def apply_exits(factors: pd.DataFrame, adj_last: dict[str, tuple[pd.Timestamp, float]],
                adj_at: dict[str, pd.Series], d_by_code: dict[str, float]) -> pd.DataFrame:
    """Cikmis hisse satirlarini son islem gunune kadar kes, cikis getirisini ekle.

    adj_last: kod -> (son islem gunu, o gunku duzeltilmis kapanis)
    adj_at:   kod -> ay sonu (factors.date) indeksli duzeltilmis kapanis
    Satirin 1 (6) aylik penceresi cikisi iceriyorsa ileri getiri
    (adj_son / adj_satir) * (1 + D) - 1 olur.
    """
    out = factors.copy()
    drop = pd.Series(False, index=out.index)
    for code, (last, a_last) in adj_last.items():
        m = out["ticker"] == code
        if not m.any():
            continue
        drop |= m & (out["date"] > last)
        keep = m & (out["date"] <= last)
        d = d_by_code[code]
        a_row = out.loc[keep, "date"].map(adj_at[code])
        to_exit = (a_last / a_row) * (1.0 + d) - 1.0
        for h, col in ((1, "fwd_ret_1m"), (6, "fwd_ret_6m")):
            hit = keep & (out["date"] + pd.DateOffset(months=h) + pd.offsets.MonthEnd(0) > last)
            out.loc[hit, col] = to_exit.reindex(out.index[hit]).values
    return out[~drop].reset_index(drop=True)
