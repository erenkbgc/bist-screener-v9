"""macro MCP server.

TCMB politika faizi, tahvil getirileri, TUFE, USD/TRY, enflasyon hedefi.

BIST_DATA_MODE=live oldugunda core/live_data.py::live_macro_snapshot GERCEK
degerler dondurur: bond_2y_pct/bond_10y_pct (doviz.com gosterge tahvil),
usdtry_spot (doviz.com), xu100_level (Is Yatirim). TCMB EVDS anket bazli
serilerle dogrulanamayan alanlar (cpi_yearend_expectation_pct,
usdtry_12m_expectation, short_selling_ban_active, vbts_stock_count,
individual_investor_count_millions, ytd_ipo_count) UYDURULMAZ; None/varsayilan
birakilir (bkz. core/hurdle.py ve core/regime.py'deki None-guard'lar). Aksi
halde core/mock_data.mock_macro_snapshot ile deterministik bir gunluk seri
kullanilir.
"""
from __future__ import annotations

import os

from core import mock_data as md

try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("macro")
    HAS_MCP = True
except ImportError:
    mcp = None
    HAS_MCP = False


def _live_enabled() -> bool:
    return os.environ.get("BIST_DATA_MODE", "mock").strip().lower() == "live"


def get_macro_snapshot(as_of_date: str) -> dict:
    if _live_enabled():
        from core import live_data as ld
        return ld.live_macro_snapshot(as_of_date)
    return md.mock_macro_snapshot(as_of_date)


def get_index_return_pct(index_name: str, start_date: str, end_date: str) -> float | None:
    """v10 roadmap: xu100_benchmark_integration. start_date -> end_date arasi
    endeks (ör. 'XU100') getirisi (%); core/evaluate.py'nin excess_vs_index_pct
    hesabinda kullanilir. Canli modda gercek veri cekilemezse None doner
    (durustluk kurali -- sahte 0.0 UYDURULMAZ, bkz. core/live_data.py)."""
    if _live_enabled():
        from core import live_data as ld
        return ld.live_index_return_pct(index_name, start_date, end_date)
    return md.mock_index_return_pct(index_name, start_date, end_date)


if HAS_MCP:
    mcp.tool()(get_macro_snapshot)
    mcp.tool()(get_index_return_pct)


if __name__ == "__main__":
    if not HAS_MCP:
        raise SystemExit("mcp paketi kurulu degil. `pip install mcp` calistirin.")
    mcp.run()
