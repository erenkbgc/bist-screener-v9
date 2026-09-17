"""tests/test_backtest.py: Backtesting Altyapisi ve Walk-forward analiz testleri (P0-2)."""
import pytest
from core.backtest import WalkForwardEngine, run_backtest, save_backtest_results
from core import db


def _generate_synthetic_prices(n=40, trend="up"):
    """Sentetik deterministik fiyat serisi uretir."""
    prices = []
    base_p = 100.0
    for i in range(n):
        d_str = f"2026-01-{i+1:02d}"
        if trend == "up":
            close_p = base_p + i * 1.5
        elif trend == "down":
            close_p = max(10.0, base_p - i * 1.5)
        else:
            close_p = base_p + (2.0 if i % 2 == 0 else -2.0)

        prices.append({
            "date": d_str,
            "ticker": "TEST",
            "open": close_p - 0.5,
            "high": close_p + 1.0,
            "low": close_p - 1.0,
            "close": close_p,
            "volume": 1000000.0,
            "sma20": close_p - 1.0,
            "atr20": 2.0,
            "volume_ratio_20d": 1.2,
        })
    return prices


def test_walk_forward_engine_runs_and_calculates_metrics():
    prices = _generate_synthetic_prices(n=50, trend="up")
    engine = WalkForwardEngine(
        price_rows=prices,
        initial_capital=100_000.0,
        commission_pct=0.15,
        slippage_pct=0.10,
    )
    res = engine.run("test_up_trend")

    assert res["initial_capital"] == 100_000.0
    assert "cagr_pct" in res
    assert "sharpe_ratio" in res
    assert "sortino_ratio" in res
    assert "max_drawdown_pct" in res
    assert "hit_rate_pct" in res
    assert "profit_factor" in res
    assert "total_trades" in res
    assert len(res["equity_curve"]) > 0


def test_walk_forward_insufficient_data():
    prices = _generate_synthetic_prices(n=10)
    engine = WalkForwardEngine(price_rows=prices)
    res = engine.run()
    assert res["total_trades"] == 0
    assert res["final_capital"] == 100_000.0


def test_trade_record_and_db_persistence(temp_db):
    prices = _generate_synthetic_prices(n=45, trend="up")
    engine = WalkForwardEngine(price_rows=prices)
    res = engine.run("persistence_test")

    run_id = save_backtest_results(res)
    assert run_id == res["run_id"]

    conn = db.get_connection()
    row = conn.execute("SELECT * FROM backtest_results WHERE run_id=?", (run_id,)).fetchone()
    assert row is not None
    assert row["strategy_name"] == "persistence_test"
    assert row["ticker"] == "TEST"

    # Trades tablosunu da kontrol et
    trades = conn.execute("SELECT * FROM backtest_trades WHERE run_id=?", (run_id,)).fetchall()
    assert len(trades) == res["total_trades"]
    conn.close()


def test_run_backtest_on_forte():
    # Canli veya mock FORTE verisiyle uctan uca test
    res = run_backtest("FORTE", as_of_date="2026-09-17", days=60, save_to_db=False)
    assert res["ticker"] == "FORTE"
    assert "total_return_pct" in res
    assert "cagr_pct" in res
    assert "sharpe_ratio" in res
    assert "max_drawdown_pct" in res
    assert "hit_rate_pct" in res
