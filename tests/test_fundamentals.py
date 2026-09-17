"""fetch_and_store_fundamentals testi: dead_hard_filters_repair (v12 T0-2).

Kok neden: core/live_data.py::live_fundamentals mali tablo hicbir sablonda
cekilemediginde (bs VE inc None) artik "unknown" sinyali donduruyor, ama bu
sinyalin core/fundamentals.py'de basis_guard'in regulator-bazli kurali
tarafindan SESSIZCE EZILMEMESI gerekiyor -- eskiden ezerdi, bu yuzden
basis_guard.UNKNOWN_RATIO_HALT_THRESHOLD ve reporting_basis!='unknown' hard
filter'i hicbir zaman tetiklenemiyordu (canli kanit: 1606/1606 fundamentals
satiri 'adjusted', 2026-09-17)."""
from core.fundamentals import fetch_and_store_fundamentals
from bist_mcp import server as bist_mcp


def _universe_row(ticker, regulator="SPK_TFRS", ratio_profile="industrial", market_cap=1000.0):
    return {"ticker": ticker, "regulator": regulator, "ratio_profile": ratio_profile,
            "market_cap": market_cap}


def _fake_fundamentals_ok(**overrides):
    base = {"reporting_basis": None, "pe": 10.0, "pb": 1.5, "ev_ebitda": None, "ev_sales": None,
            "roe": 12.0, "eps_ttm": 5.0, "ebitda_ttm": None, "net_debt": None, "nav_discount": None,
            "dividend_per_share_ttm": 1.0, "payout_ratio": 0.2, "fcf_ttm": 100.0}
    base.update(overrides)
    return base


def test_valid_regulator_and_available_statements_use_regulator_basis(temp_db, monkeypatch):
    """Normal yol: mali tablo cekilebiliyor (MCP reporting_basis=None donuyor),
    basis_guard'in regulator eslemesi (SPK_TFRS/BDDK->nominal) GECERLI kalir."""
    monkeypatch.setattr(bist_mcp, "get_fundamentals",
                         lambda *a, **k: _fake_fundamentals_ok(reporting_basis=None))
    rows = fetch_and_store_fundamentals("2026-09-10", [_universe_row("AAA")])
    assert rows[0]["reporting_basis"] == "nominal"
    assert rows[0]["null_reason"] != "unknown_reporting_basis"


def test_unfetchable_statements_force_unknown_basis_even_with_valid_regulator(temp_db, monkeypatch):
    """Kok neden testi: regulator GECERLI (SPK_TFRS/BDDK) olsa bile, MCP mali
    tablonun HICBIR sablonda cekilemedigini bildiriyorsa (reporting_basis=
    'unknown'), bu sinyal basis_guard'in regulator eslemesi tarafindan
    EZILMEMELI -- ticker unknown_reporting_basis ile null_reason almali ve
    is_scorable()=False olmali (hard filter + %30 halt kapisi bunu kullanir)."""
    monkeypatch.setattr(bist_mcp, "get_fundamentals",
                         lambda *a, **k: _fake_fundamentals_ok(reporting_basis="unknown", pe=None,
                                                                pb=None, roe=None, eps_ttm=None,
                                                                fcf_ttm=None))
    rows = fetch_and_store_fundamentals("2026-09-10", [_universe_row("BBB", regulator="BDDK")])
    assert rows[0]["reporting_basis"] == "unknown"
    assert rows[0]["null_reason"] == "unknown_reporting_basis"


def test_unknown_ratio_across_universe_reflects_real_fetch_failures(temp_db, monkeypatch):
    """basis_guard.unknown_ratio (run.py'nin %30 halt kapisi) artik GERCEK
    veri yoklugunu yansitmali, sadece regulator dagilimini degil."""
    from core import basis_guard

    def fake_get_fundamentals(ticker, *a, **k):
        # CCC/DDD icin veri yok, EEE icin var -- 2/3 unknown olmali
        if ticker in ("CCC", "DDD"):
            return _fake_fundamentals_ok(reporting_basis="unknown", pe=None, roe=None,
                                          eps_ttm=None, fcf_ttm=None)
        return _fake_fundamentals_ok(reporting_basis=None)

    monkeypatch.setattr(bist_mcp, "get_fundamentals", fake_get_fundamentals)
    rows = fetch_and_store_fundamentals("2026-09-10", [
        _universe_row("CCC", regulator="BDDK"),
        _universe_row("DDD", regulator="BDDK"),
        _universe_row("EEE", regulator="SPK_TFRS"),
    ])
    assert basis_guard.unknown_ratio(rows) == 2 / 3
