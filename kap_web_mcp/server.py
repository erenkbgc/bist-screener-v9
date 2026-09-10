"""kap-web MCP server.

kap.org.tr kamuya acik bildirim listesini parse eder. Resmi KAP REST API
kurumsal sozlesme gerektirdigi icin sahsi kullanimda erisilebilir degil
(bkz. spec: mcp_servers.kap-web.description).

KRITIK KURAL (no_free_text_interpretation_of_kap): bu sunucu bildirimi asla
serbest metin olarak disari vermez. Her bildirim, sabit bir kategori
listesine (financial_report, new_business_or_tender, share_buyback, ...)
deterministik olarak indirgenmis halde doner. LLM'e yalnizca bu kategori
etiketi + zaten hesaplanmis impact_sign/weight gider, ham metin gitmez.

BIST_DATA_MODE=live oldugunda core/live_data.py, Is Yatirim uzerinden ayna
tuttugu GERCEK KAP bildirim basliklarini (Ticker.news) KURAL TABANLI bir
regex/anahtar-kelime siniflandiriciyla (core/live_data.py::_categorize_kap_title)
kategoriye indirger -- LLM tabanli siniflandirma KULLANILMAZ (spec'te acikca
yasaklanmis). Aksi halde core/mock_data.py'daki deterministik mock katmani
kullanilir.
"""
from __future__ import annotations

import os

from core import mock_data as md

try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("kap-web")
    HAS_MCP = True
except ImportError:
    mcp = None
    HAS_MCP = False


def _live_enabled() -> bool:
    return os.environ.get("BIST_DATA_MODE", "mock").strip().lower() == "live"


def get_disclosures(tickers: list[str], as_of_date: str, lookback_days: int = 14) -> list[dict]:
    """Verilen tickerlar icin ONCEDEN KATEGORIZE EDILMIS KAP bildirimlerini dondurur."""
    if _live_enabled():
        from core import live_data as ld
        return ld.live_kap_disclosures(tickers, as_of_date, lookback_days=lookback_days)
    out: list[dict] = []
    for t in tickers:
        out.extend(md.mock_kap_disclosures(t, as_of_date, lookback_days))
    return out


def get_upcoming_events(tickers: list[str], as_of_date: str) -> list[dict]:
    """BIST rebalans, VIOP vade, lock-up ve resmen ilan edilmis genel kurul/temettu/bilanco tarihlerini ceker.

    Hicbir tarih tahmin edilmez; yalnizca resmi kaynaktan (mock katmaninda
    da bu kisit korunur, canli katmanda Is Yatirim finansal takviminden gelen
    resmi tarihler kullanilir) gelen tarihler dondurulur.
    """
    if _live_enabled():
        from core import live_data as ld
        return ld.live_upcoming_events(tickers, as_of_date)
    out: list[dict] = []
    for t in tickers:
        out.extend(md.mock_upcoming_events(t, as_of_date))
    return out


if HAS_MCP:
    mcp.tool()(get_disclosures)
    mcp.tool()(get_upcoming_events)


if __name__ == "__main__":
    if not HAS_MCP:
        raise SystemExit("mcp paketi kurulu degil. `pip install mcp` calistirin.")
    mcp.run()
