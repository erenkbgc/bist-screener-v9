"""regime testi."""
import pytest

from core import regime as regime_mod
from core.regime_taxonomy import real_rate_regime
from macro_mcp import server as macro_mcp


def test_regime_halts_when_macro_fetch_fails(temp_db, monkeypatch):
    def boom(as_of_date):
        raise RuntimeError("network down")
    monkeypatch.setattr(macro_mcp, "get_macro_snapshot", boom)
    with pytest.raises(regime_mod.RegimeHaltError):
        regime_mod.check_market_regime("2026-09-10")


def test_regime_halts_when_snapshot_empty(temp_db, monkeypatch):
    monkeypatch.setattr(macro_mcp, "get_macro_snapshot", lambda d: {})
    with pytest.raises(regime_mod.RegimeHaltError):
        regime_mod.check_market_regime("2026-09-10")


def test_regime_detects_short_selling_ban_change(temp_db, monkeypatch):
    snapshots = iter([
        {"short_selling_ban_active": True, "vbts_stock_count": 5, "policy_rate_pct": 37,
         "bond_2y_pct": 39.6, "cpi_yoy_pct": 31.5, "usdtry_spot": 48.4, "xu100_level": 14000},
        {"short_selling_ban_active": False, "vbts_stock_count": 5, "policy_rate_pct": 37,
         "bond_2y_pct": 39.6, "cpi_yoy_pct": 31.5, "usdtry_spot": 48.4, "xu100_level": 14000},
    ])
    monkeypatch.setattr(macro_mcp, "get_macro_snapshot", lambda d: next(snapshots))
    regime_mod.check_market_regime("2026-09-10")
    result = regime_mod.check_market_regime("2026-09-11")
    assert result["short_term_bucket_suspended"] is True
    assert result["regime_change_flag"] is True


def test_regime_detects_bond_shock(temp_db, monkeypatch):
    snapshots = iter([
        {"short_selling_ban_active": True, "vbts_stock_count": 5, "policy_rate_pct": 37,
         "bond_2y_pct": 39.6, "cpi_yoy_pct": 31.5, "usdtry_spot": 48.4, "xu100_level": 14000},
        {"short_selling_ban_active": True, "vbts_stock_count": 5, "policy_rate_pct": 37,
         "bond_2y_pct": 44.0, "cpi_yoy_pct": 31.5, "usdtry_spot": 48.4, "xu100_level": 14000},
    ])
    monkeypatch.setattr(macro_mcp, "get_macro_snapshot", lambda d: next(snapshots))
    regime_mod.check_market_regime("2026-09-10")
    result = regime_mod.check_market_regime("2026-09-11")
    assert result["hurdle_recalc_required"] is True


def test_real_rate_regime_labels():
    assert real_rate_regime(30, 35) == "negative"
    assert real_rate_regime(35, 33) == "low_positive"
    assert real_rate_regime(40, 20) == "high_positive"
