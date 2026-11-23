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


def test_amihud_illiquidity_calculation():
    # 1. Likit hisse (buyuk hacim, kucuk getiri -> cok kucuk ILLIQ)
    liquid_bars = [
        {"close": 100.0 + i * 0.1, "volume": 1_000_000} for i in range(25)
    ]
    illiq_liquid = universe_mod.calculate_amihud_illiquidity(liquid_bars)
    assert illiq_liquid is not None
    assert illiq_liquid < 0.05  # Cok dusuk fiyat etkisi

    # 2. Sig hisse (kucuk hacim, sert getiri -> yuksek ILLIQ)
    illiquid_bars = [
        {"close": 50.0 + (5.0 if i % 2 == 0 else -5.0), "volume": 2_000} for i in range(25)
    ]
    illiq_illiquid = universe_mod.calculate_amihud_illiquidity(illiquid_bars)
    assert illiq_illiquid is not None
    assert illiq_illiquid > illiq_liquid * 100


def test_build_universe_serial_vs_parallel_identical(temp_db, monkeypatch):
    """Task 3: Seri (max_workers=1) ve paralel (max_workers=4) build_universe ciktisi birebir ayni olmali."""
    import time
    from core import db

    entries = [
        {
            "ticker": f"TK{i:03d}",
            "name": f"Sirket {i}",
            "sector": ["XGIDA", "XBANK", "XHOLD", "XBLSM", "XGMYO"][i % 5],
            "ratio_profile": ["industrial", "bank", "holding", "industrial", "reit"][i % 5],
            "regulator": "BDDK" if i % 5 == 1 else "SPK_TFRS",
        }
        for i in range(25)
    ]
    _patch_universe(monkeypatch, entries)

    def fake_size(ticker, as_of_date):
        idx = int(ticker[2:])
        time.sleep(0.002 * ((idx % 3) + 1))
        if idx == 3:
            return {"listing_days": 30, "market_cap": 5e9, "avg_volume_tl_20d": 5e7}
        if idx == 7:
            return {"listing_days": 120, "market_cap": 5e9, "avg_volume_tl_20d": 5e7}  # reported_quarters=1 < 2
        if idx == 11:
            return {"listing_days": 500, "market_cap": 2e9, "avg_volume_tl_20d": None}
        if idx == 15:
            return {"listing_days": 500, "market_cap": 2e9, "avg_volume_tl_20d": 1_000_000.0}
        return {"listing_days": 400 + idx * 10, "market_cap": 1e9 * (idx + 1), "avg_volume_tl_20d": 2e7 + idx * 1e6}

    def fake_tedbir(ticker, as_of_date):
        idx = int(ticker[2:])
        return {"ticker": ticker, "tedbir_level": 2 if idx == 19 else (1 if idx % 4 == 0 else 0)}

    monkeypatch.setattr(bist_mcp, "get_listing_and_size", fake_size)
    monkeypatch.setattr(bist_mcp, "get_tedbir_level", fake_tedbir)

    serial_rows = universe_mod.build_universe("2026-11-21", max_workers=1)
    serial_eligible = universe_mod.eligible_tickers("2026-11-21")

    conn = db.get_connection()
    conn.execute("DELETE FROM universe_snapshot")
    conn.commit()
    conn.close()

    parallel_rows = universe_mod.build_universe("2026-11-21", max_workers=4)
    parallel_eligible = universe_mod.eligible_tickers("2026-11-21")

    strip_ts = lambda rows: [{k: v for k, v in r.items() if k != "ingested_at"} for r in rows]  # noqa: E731
    assert strip_ts(serial_rows) == strip_ts(parallel_rows)
    assert strip_ts(serial_eligible) == strip_ts(parallel_eligible)
    assert [r["ticker"] for r in serial_rows] == [e["ticker"] for e in entries]

