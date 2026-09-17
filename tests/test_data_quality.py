"""tests/test_data_quality.py: Tests for data quality, survivorship bias, corporate actions, and price adjustment."""
from __future__ import annotations

import pytest

from core import db
from core.backtest import WalkForwardEngine
from core.data_quality import (
    adjust_price_series,
    audit_ticker_data_quality,
    fetch_corporate_actions,
    get_delist_info,
    get_delisted_stocks,
    get_survivorship_free_universe,
    is_delisted,
    save_corporate_actions,
    seed_delisted_stocks,
)


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()


def test_seed_and_get_delisted_stocks():
    seed_delisted_stocks()
    delisted = get_delisted_stocks()
    assert len(delisted) >= 14
    tickers = {d["ticker"] for d in delisted}
    assert "ASYAB" in tickers
    assert "GENYH" in tickers
    assert "ESEM" in tickers
    assert "DENIZ" in tickers


def test_is_delisted_and_delist_info():
    seed_delisted_stocks()
    # ASYAB delisted on 2016-07-22
    assert is_delisted("ASYAB") is True
    assert is_delisted("ASYAB", "2015-01-01") is False
    assert is_delisted("ASYAB", "2016-07-22") is True
    assert is_delisted("ASYAB", "2026-09-17") is True

    # Unknown stock
    assert is_delisted("THYAO") is False

    info = get_delist_info("ASYAB")
    assert info is not None
    assert info["delist_reason"] == "bankruptcy"
    assert info["terminal_recovery_pct"] == 0.0

    deniz_info = get_delist_info("DENIZ")
    assert deniz_info is not None
    assert deniz_info["delist_reason"] == "squeeze_out"
    assert deniz_info["terminal_recovery_pct"] == 100.0


def test_survivorship_free_universe():
    seed_delisted_stocks()
    current_universe = [
        {"ticker": "THYAO", "name": "THY", "sector": "XULAS"},
        {"ticker": "ASELS", "name": "Aselsan", "sector": "XUSIN"},
    ]
    # As of 2015-01-01, ASYAB was still alive (delisted 2016)
    hist_universe = get_survivorship_free_universe("2015-01-01", current_universe)
    hist_tickers = {x["ticker"] for x in hist_universe}
    assert "ASYAB" in hist_tickers
    assert "GENYH" in hist_tickers
    assert "THYAO" in hist_tickers


def test_corporate_actions_db_roundtrip():
    actions = [
        {
            "ticker": "TESTCORP",
            "action_date": "2024-05-10",
            "action_type": "dividend",
            "ratio_or_amount": 2.50,
            "split_factor": 1.0,
            "dividend_amount": 2.50,
            "source": "test",
        },
        {
            "ticker": "TESTCORP",
            "action_date": "2024-08-15",
            "action_type": "bonus_issue",
            "ratio_or_amount": 100.0,
            "split_factor": 2.0,
            "dividend_amount": 0.0,
            "source": "test",
        },
    ]
    save_corporate_actions(actions)
    fetched = fetch_corporate_actions("TESTCORP")
    assert len(fetched) == 2
    assert fetched[0]["action_date"] == "2024-05-10"
    assert fetched[0]["dividend_amount"] == 2.50
    assert fetched[1]["action_date"] == "2024-08-15"
    assert fetched[1]["split_factor"] == 2.0


def test_split_price_adjustment():
    raw_bars = [
        {"date": "2024-01-01", "open": 100.0, "high": 105.0, "low": 98.0, "close": 100.0, "volume": 1000.0},
        {"date": "2024-01-02", "open": 100.0, "high": 104.0, "low": 99.0, "close": 102.0, "volume": 1200.0},
        {"date": "2024-01-03", "open": 51.0, "high": 53.0, "low": 50.0, "close": 52.0, "volume": 2500.0},
        {"date": "2024-01-04", "open": 52.0, "high": 55.0, "low": 51.0, "close": 54.0, "volume": 2000.0},
    ]
    actions = [
        {
            "ticker": "TEST",
            "action_date": "2024-01-03",
            "action_type": "bonus_issue",
            "ratio_or_amount": 100.0,
            "split_factor": 2.0,
            "dividend_amount": 0.0,
        }
    ]
    adj_bars = adjust_price_series(raw_bars, actions)
    assert len(adj_bars) == 4
    # Pre-split bars should have price halved and volume doubled
    assert adj_bars[0]["adj_close"] == 50.0
    assert adj_bars[0]["adj_volume"] == 2000.0
    assert adj_bars[1]["adj_close"] == 51.0
    # Post-split bars should remain unchanged
    assert adj_bars[2]["adj_close"] == 52.0
    assert adj_bars[3]["adj_close"] == 54.0


def test_dividend_price_adjustment():
    raw_bars = [
        {"date": "2024-01-01", "open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0, "volume": 1000.0},
        {"date": "2024-01-02", "open": 92.0, "high": 95.0, "low": 90.0, "close": 94.0, "volume": 1500.0},
    ]
    # Dividend of 10 TL paid on 2024-01-02
    actions = [
        {
            "ticker": "TESTDIV",
            "action_date": "2024-01-02",
            "action_type": "dividend",
            "ratio_or_amount": 10.0,
            "split_factor": 1.0,
            "dividend_amount": 10.0,
        }
    ]
    adj_bars = adjust_price_series(raw_bars, actions)
    # p_cum = 100, div = 10 -> factor = (100 - 10) / 100 = 0.9
    assert adj_bars[0]["adj_close"] == 90.0
    assert adj_bars[1]["adj_close"] == 94.0


def test_audit_unexplained_jump():
    raw_bars = [
        {"date": "2024-01-01", "open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0, "volume": 1000.0},
        {"date": "2024-01-02", "open": 50.0, "high": 52.0, "low": 48.0, "close": 50.0, "volume": 1000.0},
    ]
    report = audit_ticker_data_quality("JUMPTICKER", raw_bars, as_of_date="2024-01-02", corporate_actions=[])
    assert report.is_clean is False
    assert report.suspicious_jumps_count == 1
    assert any("aciklanamayan" in iss for iss in report.issues)
    assert report.quality_score < 100.0


def test_audit_explained_jump():
    raw_bars = [
        {"date": "2024-01-01", "open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0, "volume": 1000.0},
        {"date": "2024-01-02", "open": 50.0, "high": 52.0, "low": 48.0, "close": 50.0, "volume": 1000.0},
    ]
    actions = [
        {
            "ticker": "SPLITTICKER",
            "action_date": "2024-01-02",
            "action_type": "bonus_issue",
            "ratio_or_amount": 100.0,
            "split_factor": 2.0,
            "dividend_amount": 0.0,
        }
    ]
    report = audit_ticker_data_quality("SPLITTICKER", raw_bars, as_of_date="2024-01-02", corporate_actions=actions)
    assert report.is_clean is True
    assert report.quality_score == 100.0


def test_audit_sanity_checks():
    bad_bars = [
        # High < Low
        {"date": "2024-01-01", "open": 100.0, "high": 90.0, "low": 95.0, "close": 92.0, "volume": 1000.0},
        # Close outside [Low, High]
        {"date": "2024-01-02", "open": 90.0, "high": 100.0, "low": 85.0, "close": 110.0, "volume": 1000.0},
    ]
    report = audit_ticker_data_quality("SANITYFAIL", bad_bars, as_of_date="2024-01-02")
    assert report.is_clean is False
    assert any("Low'dan" in iss for iss in report.issues)
    assert any("araligi disinda" in iss for iss in report.issues)


def test_backtest_with_delisted_stock_liquidation():
    seed_delisted_stocks()
    # Create price history for ASYAB crossing its delist date (2016-07-22)
    # Generate 35 bars
    price_rows = []
    from datetime import date, timedelta
    start_d = date(2016, 6, 1)
    for i in range(40):
        d_str = (start_d + timedelta(days=i)).isoformat()
        # Simulated pullback to trigger buy early
        p = 1.0 - (0.01 * (i % 5))
        price_rows.append({
            "ticker": "ASYAB",
            "date": d_str,
            "open": p,
            "high": p + 0.05,
            "low": p - 0.05,
            "close": p,
            "volume": 500_000.0,
            "sma20": p + 0.02,
            "atr20": 0.04,
        })

    engine = WalkForwardEngine(
        price_rows=price_rows,
        initial_capital=100_000.0,
    )
    result = engine.run("delist_test")
    trades = result["trades"]
    # If a trade was open when 2016-07-22 arrived, it should have been exited with delisted reason
    delist_trades = [t for t in trades if "delisted" in t.get("exit_reason", "")]
    if delist_trades:
        assert delist_trades[0]["exit_price"] == 0.0
        assert delist_trades[0]["return_pct"] == -100.0
