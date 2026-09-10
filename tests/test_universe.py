"""tedbir_level testi, ipo testi (min_listing_days)."""
from core import universe as universe_mod
from bist_mcp import server as bist_mcp


def _patch_universe(monkeypatch, entries):
    monkeypatch.setattr(bist_mcp, "get_universe", lambda: entries)


def test_tedbir_level_above_max_excludes(temp_db, monkeypatch):
    _patch_universe(monkeypatch, [
        {"ticker": "AAA", "name": "A", "sector": "XGIDA", "ratio_profile": "industrial", "regulator": "SPK_TFRS"},
    ])
    monkeypatch.setattr(bist_mcp, "get_listing_and_size",
                         lambda t, d: {"listing_days": 1000, "market_cap": 1e10, "avg_volume_tl_20d": 5e7})
    monkeypatch.setattr(bist_mcp, "get_tedbir_level", lambda t, d: {"ticker": t, "tedbir_level": 2})

    rows = universe_mod.build_universe("2026-09-10")
    assert rows[0]["exclusion_reason"] == "max_tedbir_level"


def test_tedbir_level_within_max_included(temp_db, monkeypatch):
    _patch_universe(monkeypatch, [
        {"ticker": "BBB", "name": "B", "sector": "XGIDA", "ratio_profile": "industrial", "regulator": "SPK_TFRS"},
    ])
    monkeypatch.setattr(bist_mcp, "get_listing_and_size",
                         lambda t, d: {"listing_days": 1000, "market_cap": 1e10, "avg_volume_tl_20d": 5e7})
    monkeypatch.setattr(bist_mcp, "get_tedbir_level", lambda t, d: {"ticker": t, "tedbir_level": 1})

    rows = universe_mod.build_universe("2026-09-10")
    assert rows[0]["exclusion_reason"] is None


def test_ipo_wave_excludes_new_listings(temp_db, monkeypatch):
    """P10_ipo_wave: 90 gunden yeni sirketler elenir."""
    _patch_universe(monkeypatch, [
        {"ticker": "NEWCO", "name": "N", "sector": "XGIDA", "ratio_profile": "industrial", "regulator": "SPK_TFRS"},
    ])
    monkeypatch.setattr(bist_mcp, "get_listing_and_size",
                         lambda t, d: {"listing_days": 45, "market_cap": 1e10, "avg_volume_tl_20d": 5e7})
    monkeypatch.setattr(bist_mcp, "get_tedbir_level", lambda t, d: {"ticker": t, "tedbir_level": 0})

    rows = universe_mod.build_universe("2026-09-10")
    assert rows[0]["exclusion_reason"] == "min_listing_days"


def test_low_volume_excludes(temp_db, monkeypatch):
    _patch_universe(monkeypatch, [
        {"ticker": "THIN", "name": "T", "sector": "XGIDA", "ratio_profile": "industrial", "regulator": "SPK_TFRS"},
    ])
    monkeypatch.setattr(bist_mcp, "get_listing_and_size",
                         lambda t, d: {"listing_days": 1000, "market_cap": 1e10, "avg_volume_tl_20d": 1000})
    monkeypatch.setattr(bist_mcp, "get_tedbir_level", lambda t, d: {"ticker": t, "tedbir_level": 0})

    rows = universe_mod.build_universe("2026-09-10")
    assert rows[0]["exclusion_reason"] == "min_volume_tl"
