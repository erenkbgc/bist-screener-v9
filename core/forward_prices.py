"""Ileriye donuk kayit icin kalici gunluk fiyat deposu (data/forward_record/prices/<TICKER>.csv).

Neden: degerlendirme fiyatlari saglayicidan ceker; ancak sonradan islemden kalkan
(delist, birlesme, kod degisikligi) bir hissenin gecmisi saglayicidan kaybolabilir
ve secilmis hisse sessizce portfoyden duserdi. Her canli kosu, kayittaki hisselerin
gunluk barlarini buraya yazar; saglayici artik dondurmezse dosya son haliyle kalir.

Duzeltilmis fiyat geriye donuk degisir (bedelsiz/bolunme). Her yazimda yeni seri
esas alinir; yalnizca yeni seride olmayan eski satirlar tutulur ve ortak ilk gundeki
oranla yeni baza olceklenir. Ham kapanis ve hacim olceklenmez.

Yalnizca canli veri modunda ve uretim veritabaniyla, kayit baslangicindan sonra yazar
(core/forward_record ile ayni kosul).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from core import forward_record

PRICES_DIR = forward_record.RECORD_PATH.parent / "prices"
COLUMNS = ["date", "open", "close", "adj_close", "volume"]


def path_of(ticker: str, root: Path | None = None) -> Path:
    return (root or PRICES_DIR) / f"{ticker}.csv"


def load(ticker: str, root: Path | None = None) -> pd.DataFrame | None:
    p = path_of(ticker, root)
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["date"])
    return df if not df.empty else None


def merge(old: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """Yeni seri esas; eski satirlardan yalnizca yeni seride olmayan tarihler, ortak ilk
    gundeki adj_close oraniyla yeni baza olceklenerek eklenir. Ortak gun yoksa eski
    satirlar olceklenmeden eklenmez (baz bilinmez)."""
    new = new[COLUMNS].copy()
    new["date"] = pd.to_datetime(new["date"])
    new = new.drop_duplicates("date", keep="last").sort_values("date")
    if old is None or old.empty:
        return new.reset_index(drop=True)
    common = old.merge(new, on="date", suffixes=("_o", "_n"))
    common = common[(common["adj_close_o"] > 0) & (common["adj_close_n"] > 0)]
    if common.empty:
        return new.reset_index(drop=True)
    first = common.sort_values("date").iloc[0]
    k = first["adj_close_n"] / first["adj_close_o"]
    older = old[~old["date"].isin(new["date"])].copy()
    older["adj_close"] = older["adj_close"] * k
    return pd.concat([older[COLUMNS], new], ignore_index=True).sort_values("date").reset_index(drop=True)


def write(bars_by_ticker: dict[str, list[dict]], tickers: set[str], since: str,
          root: Path | None = None, force: bool = False) -> int:
    """tickers icin gunluk barlari (bist_mcp.get_prices satirlari) depoya yazar; yazilan dosya sayisi."""
    if not force and not forward_record._production_live():
        return 0
    root = root or PRICES_DIR
    n = 0
    for tk in sorted(tickers):
        bars = [b for b in bars_by_ticker.get(tk) or [] if b.get("date") and b["date"] >= since]
        if not bars:
            continue  # saglayici dondurmedi: dosya son haliyle kalir
        new = pd.DataFrame([{"date": b["date"], "open": b.get("open"), "close": b.get("close"),
                             "adj_close": b.get("adj_close") or b.get("close"),
                             "volume": b.get("volume")} for b in bars])
        root.mkdir(parents=True, exist_ok=True)
        merged = merge(load(tk, root), new)
        merged.assign(date=merged["date"].dt.strftime("%Y-%m-%d")).to_csv(path_of(tk, root), index=False)
        n += 1
    return n


def recorded_tickers(decisions: list[dict]) -> set[str]:
    """Kayittaki tum basarili kararlarin tutulan ve evren hisseleri."""
    return {tk for d in decisions if forward_record.is_ok(d) for tk in d.get("holdings", []) + d.get("universe", [])}
