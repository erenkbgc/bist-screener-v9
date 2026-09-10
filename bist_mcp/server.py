"""bist-data MCP server.

Fiyat, hacim, rasyo, tedbir, sahiplik, temettu gecmisi saglar.

BIST_DATA_MODE ortam degiskeni "live" ise core/live_data.py (borsapy / Is
Yatirim kaynakli GERCEK veri) kullanilir; aksi halde (varsayilan, testlerde
de budur) core/mock_data.py'daki deterministik mock veri katmani kullanilir.
Canli modda tek bir ticker icin veri cekilemezse (agsal hata, sablon
uyumsuzlugu vb.) o ticker icin sessizce mock'a DUSMEZ -- bunun yerine ilgili
alanlar None doner, boylece basis_guard/null_reason mekanizmalari devreye
girer (sahte sayi uretilmez).

Gercek veri kaynagi ilk defa baglanirken bu dosyadaki fonksiyon govdeleri
degisti (mock_data -> live_data yonlendirmesi); imzalar ve donus semalari
sabit kaldi, core/ katmaninin geri kalani DEGISMEDI.
"""
from __future__ import annotations

import os

from core import mock_data as md

try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("bist-data")
    HAS_MCP = True
except ImportError:  # pip install mcp yapilmadiysa da fonksiyonlar dogrudan kullanilabilsin
    mcp = None
    HAS_MCP = False


def _live_enabled() -> bool:
    return os.environ.get("BIST_DATA_MODE", "mock").strip().lower() == "live"


def get_universe() -> list[dict]:
    """Taranabilir BIST evrenini (ticker, sektor, ratio_profile, regulator) dondurur.

    Canli modda bp.companies() ile TUM BIST evrenini (~800 sirket) dondurur --
    hardcoded ticker listesi degildir. Mock modda kucuk, sabit bir gelistirme
    evreni doner (core/mock_data.py -> _UNIVERSE, yalnizca test/gelistirme icin)."""
    if _live_enabled():
        from core import live_data as ld
        limit = os.environ.get("BIST_LIVE_UNIVERSE_LIMIT")
        # YALNIZCA gelistirme/hizli-test icin: gercek, dinamik olarak cekilen
        # evrenin ilk N kaydiyla sinirlar (siniflandirma dongusune girmeden
        # once, performans icin). Hicbir ticker hardcoded SECILMEZ; production'da
        # bu degisken tanimlanmamalidir (tum evren taranir).
        return ld.live_universe(limit=int(limit) if limit else None)
    return md.universe_seed()


def get_listing_and_size(ticker: str, as_of_date: str) -> dict:
    if _live_enabled():
        from core import live_data as ld
        return ld.live_listing_and_size(ticker, as_of_date)
    listing_days = md.mock_listing_days(ticker, as_of_date)
    market_cap, avg_volume_tl = md.mock_market_cap_and_volume(ticker, as_of_date)
    return {"listing_days": listing_days, "market_cap": market_cap, "avg_volume_tl_20d": avg_volume_tl}


def get_tedbir_level(ticker: str, as_of_date: str) -> dict:
    if _live_enabled():
        from core import live_data as ld
        return ld.live_tedbir_level(ticker, as_of_date)
    return {"ticker": ticker, "tedbir_level": md.mock_tedbir_level(ticker, as_of_date)}


def get_prices(ticker: str, as_of_date: str, days: int = 140) -> list[dict]:
    if _live_enabled():
        from core import live_data as ld
        return ld.live_prices(ticker, as_of_date, days=days)
    return md.mock_prices(ticker, as_of_date, days=days)


def get_fundamentals(ticker: str, as_of_date: str, regulator: str, ratio_profile: str) -> dict:
    if _live_enabled():
        from core import live_data as ld
        return ld.live_fundamentals(ticker, as_of_date, regulator, ratio_profile)
    return md.mock_fundamentals(ticker, as_of_date, regulator, ratio_profile)


def get_piotroski_raw_criteria(ticker: str, as_of_date: str) -> dict:
    if _live_enabled():
        from core import live_data as ld
        return ld.live_piotroski_raw_criteria(ticker, as_of_date)
    return md.mock_piotroski_inputs(ticker, as_of_date)


def get_cashflow_for_sloan(ticker: str, as_of_date: str, net_income_hint: float) -> dict:
    if _live_enabled():
        from core import live_data as ld
        return ld.live_cashflow_for_sloan(ticker, as_of_date, net_income_hint)
    return md.mock_cashflow_for_sloan(ticker, as_of_date, net_income_hint)


def get_dividend_history(ticker: str, as_of_date: str) -> dict:
    if _live_enabled():
        from core import live_data as ld
        return ld.live_dividend_history(ticker, as_of_date)
    return md.mock_dividend_history(ticker, as_of_date)


def get_ownership(ticker: str, as_of_date: str) -> dict:
    if _live_enabled():
        from core import live_data as ld
        return ld.live_ownership(ticker, as_of_date)
    return md.mock_ownership(ticker, as_of_date)


def prefetch(tickers: list[str]) -> None:
    """Canli modda, evrenin ihtiyac duyacagi tum ag cagrilarini PARALEL olarak
    onceden cache'ler (bkz. core/live_data.py::prefetch_all) -- boylece
    run.py'deki sirali per-ticker dongulerinin her biri artik cache'ten okur.
    Mock modda no-op'tur (mock veri zaten anlik/CPU-bound)."""
    if _live_enabled():
        from core import live_data as ld
        ld.prefetch_all(tickers)


if HAS_MCP:
    mcp.tool()(get_universe)
    mcp.tool()(get_listing_and_size)
    mcp.tool()(get_tedbir_level)
    mcp.tool()(get_prices)
    mcp.tool()(get_fundamentals)
    mcp.tool()(get_piotroski_raw_criteria)
    mcp.tool()(get_cashflow_for_sloan)
    mcp.tool()(get_dividend_history)
    mcp.tool()(get_ownership)


if __name__ == "__main__":
    if not HAS_MCP:
        raise SystemExit("mcp paketi kurulu degil. `pip install mcp` calistirin.")
    mcp.run()
