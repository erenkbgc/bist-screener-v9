"""core/backtest.py: BIST Screener Walk-Forward Backtesting Engine & Backtrader Integration.

v12/v13 Roadmap P0-2:
- Walk-forward analiz (look-ahead bias kontrolu: available_at/effective_at).
- Islem maliyeti (commission) + slippage simülasyonu.
- Dinamik entry bandi, stop-loss ve sabit kesirli pozisyon buyuklugu kurallari.
- Metrikler: CAGR, Sharpe, Sortino, Max Drawdown, Hit Rate, Profit Factor.
- Sonuclarin backtest_results ve backtest_trades tablolarina kaydi.
"""
from __future__ import annotations

import argparse
import math
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Proje kok dizinini sys.path'e ekle
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import backtrader as bt
import numpy as np
import pandas as pd

from bist_mcp import server as bist_mcp
from core import db
from core.targets import compute_dynamic_risk_levels


@dataclass
class TradeRecord:
    ticker: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    target_price: float
    stop_loss: float
    position_size_pct: float
    shares: float
    pnl_tl: float
    return_pct: float
    exit_reason: str
    holding_days: int


class WalkForwardEngine:
    """Look-ahead bias icermeyen, adim adim yuruyen (walk-forward) simülasyon motoru."""

    def __init__(
        self,
        price_rows: list[dict],
        initial_capital: float = 100_000.0,
        commission_pct: float = 0.15,
        slippage_pct: float = 0.10,
        account_risk_pct: float = 1.5,
        max_position_size_pct: float = 25.0,
        horizon_days: int = 20,
    ) -> None:
        self.price_rows = sorted(price_rows, key=lambda x: x["date"])
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.account_risk_pct = account_risk_pct
        self.max_position_size_pct = max_position_size_pct
        self.horizon_days = horizon_days

    def run(self, strategy_name: str = "dynamic_risk_walkforward") -> dict[str, Any]:
        if len(self.price_rows) < 25:
            return self._empty_result(strategy_name)

        capital = self.initial_capital
        equity_curve: list[dict[str, Any]] = []
        trades: list[TradeRecord] = []

        # Pozisyon durumu
        in_position = False
        pos_entry_price = 0.0
        pos_entry_date = ""
        pos_shares = 0.0
        pos_target_price = 0.0
        pos_stop_loss = 0.0
        pos_size_pct = 0.0
        days_in_trade = 0

        # Bekleyen emir (bir onceki gun olusan sinyal)
        pending_order: dict[str, Any] | None = None

        ticker = self.price_rows[0].get("ticker", "UNKNOWN")
        from core.data_quality import get_delist_info
        delist_info = get_delist_info(ticker)

        for i in range(20, len(self.price_rows)):
            bar = self.price_rows[i]
            date_str = bar["date"]
            open_p = bar.get("adj_open", bar["open"])
            high_p = bar.get("adj_high", bar["high"])
            low_p = bar.get("adj_low", bar["low"])
            close_p = bar.get("adj_close", bar["close"])

            # Delist / İflas kontrolü (Survivorship bias önleme)
            if delist_info and date_str >= delist_info["delist_date"]:
                if in_position:
                    recovery_pct = float(delist_info.get("terminal_recovery_pct", 0.0))
                    last_price = float(delist_info.get("last_price") or pos_entry_price)
                    exit_price = last_price * (recovery_pct / 100.0)
                    exit_reason = f"delisted_{delist_info.get('delist_reason', 'bankruptcy')}"
                    gross_proceeds = pos_shares * exit_price
                    exit_comm = gross_proceeds * (self.commission_pct / 100.0)
                    net_proceeds = gross_proceeds - exit_comm
                    capital += net_proceeds
                    trade_cost = pos_shares * pos_entry_price
                    trade_pnl = net_proceeds - trade_cost
                    ret_pct = ((exit_price - pos_entry_price) / pos_entry_price) * 100.0
                    trades.append(
                        TradeRecord(
                            ticker=ticker,
                            entry_date=pos_entry_date,
                            exit_date=date_str,
                            entry_price=round(pos_entry_price, 2),
                            exit_price=round(exit_price, 2),
                            target_price=round(pos_target_price, 2),
                            stop_loss=round(pos_stop_loss, 2),
                            position_size_pct=round(pos_size_pct, 2),
                            shares=round(pos_shares, 2),
                            pnl_tl=round(trade_pnl, 2),
                            return_pct=round(ret_pct, 2),
                            exit_reason=exit_reason,
                            holding_days=days_in_trade,
                        )
                    )
                    in_position = False
                    pos_shares = 0.0
                    days_in_trade = 0
                equity_curve.append({
                    "date": date_str,
                    "equity": round(capital, 2),
                    "cash": round(capital, 2),
                    "in_position": False,
                })
                continue

            # 1. Mevcut pozisyonu kontrol et (Exit kontrolu)
            if in_position:
                days_in_trade += 1
                exit_triggered = False
                exit_price = 0.0
                exit_reason = ""

                # Stop loss kontrolu
                if low_p <= pos_stop_loss:
                    exit_triggered = True
                    fill_base = min(open_p, pos_stop_loss)
                    exit_price = fill_base * (1.0 - self.slippage_pct / 100.0)
                    exit_reason = "stop_hit"
                # Target price kontrolu
                elif high_p >= pos_target_price:
                    exit_triggered = True
                    fill_base = max(open_p, pos_target_price) if open_p >= pos_target_price else pos_target_price
                    exit_price = fill_base * (1.0 - self.slippage_pct / 100.0)
                    exit_reason = "target_hit"
                # Vade dolumu kontrolu
                elif days_in_trade >= self.horizon_days:
                    exit_triggered = True
                    exit_price = close_p * (1.0 - self.slippage_pct / 100.0)
                    exit_reason = "horizon_expired"

                if exit_triggered:
                    gross_proceeds = pos_shares * exit_price
                    exit_comm = gross_proceeds * (self.commission_pct / 100.0)
                    net_proceeds = gross_proceeds - exit_comm
                    capital += net_proceeds

                    trade_cost = pos_shares * pos_entry_price
                    trade_pnl = net_proceeds - trade_cost
                    ret_pct = ((exit_price - pos_entry_price) / pos_entry_price) * 100.0

                    trades.append(
                        TradeRecord(
                            ticker=ticker,
                            entry_date=pos_entry_date,
                            exit_date=date_str,
                            entry_price=round(pos_entry_price, 2),
                            exit_price=round(exit_price, 2),
                            target_price=round(pos_target_price, 2),
                            stop_loss=round(pos_stop_loss, 2),
                            position_size_pct=round(pos_size_pct, 2),
                            shares=round(pos_shares, 2),
                            pnl_tl=round(trade_pnl, 2),
                            return_pct=round(ret_pct, 2),
                            exit_reason=exit_reason,
                            holding_days=days_in_trade,
                        )
                    )

                    in_position = False
                    pos_shares = 0.0
                    days_in_trade = 0

            # 2. Bekleyen alim emri varsa ve pozisyonda degilsek doldur (Entry kontrolu)
            if not in_position and pending_order is not None:
                entry_low = pending_order["entry_low"]
                entry_high = pending_order["entry_high"]

                if low_p <= entry_high and high_p >= entry_low:
                    ideal_entry = min(open_p, (entry_low + entry_high) / 2.0) if open_p <= entry_high else (entry_low + entry_high) / 2.0
                    exec_entry = ideal_entry * (1.0 + self.slippage_pct / 100.0)

                    allocated_capital = capital * (pending_order["position_size_pct"] / 100.0)
                    entry_comm = allocated_capital * (self.commission_pct / 100.0)
                    net_investable = allocated_capital - entry_comm

                    if net_investable > 0 and exec_entry > 0:
                        pos_shares = net_investable / exec_entry
                        capital -= allocated_capital
                        in_position = True
                        pos_entry_price = exec_entry
                        pos_entry_date = date_str
                        pos_target_price = pending_order["target_price"]
                        pos_stop_loss = pending_order["stop_loss"]
                        pos_size_pct = pending_order["position_size_pct"]
                        days_in_trade = 0

                pending_order = None

            # 3. Pozisyonda degilsek yeni sinyal taramasi (Look-ahead bias onleyici)
            if not in_position:
                sma20 = bar.get("sma20", close_p)
                atr20 = bar.get("atr20", close_p * 0.02)
                vol_ratio = bar.get("volume_ratio_20d", 1.0) or 1.0

                is_setup = (close_p >= sma20 * 0.98) and (vol_ratio >= 0.8)
                if is_setup and atr20 > 0:
                    past_window = self.price_rows[max(0, i - 19) : i + 1]
                    recent_lows = [p.get("adj_low", p.get("low")) for p in past_window if p.get("adj_low", p.get("low")) is not None]
                    recent_swing = min(recent_lows) if recent_lows else None

                    risk = compute_dynamic_risk_levels(
                        current_price=close_p,
                        atr20=atr20,
                        recent_swing_low=recent_swing,
                        account_risk_pct=self.account_risk_pct,
                        max_position_size_pct=self.max_position_size_pct,
                    )

                    target_price = close_p + 2.5 * atr20
                    pending_order = {
                        "entry_low": risk["entry_low"],
                        "entry_high": risk["entry_high"],
                        "stop_loss": risk["stop_loss"],
                        "target_price": target_price,
                        "position_size_pct": risk["position_size_pct"],
                    }

            current_pos_val = (pos_shares * close_p) if in_position else 0.0
            total_equity = capital + current_pos_val
            equity_curve.append({
                "date": date_str,
                "equity": round(total_equity, 2),
                "cash": round(capital, 2),
                "in_position": in_position,
            })

        if in_position:
            last_bar = self.price_rows[-1]
            exit_price = last_bar.get("adj_close", last_bar["close"]) * (1.0 - self.slippage_pct / 100.0)
            gross = pos_shares * exit_price
            comm = gross * (self.commission_pct / 100.0)
            capital += (gross - comm)
            trades.append(
                TradeRecord(
                    ticker=ticker,
                    entry_date=pos_entry_date,
                    exit_date=last_bar["date"],
                    entry_price=round(pos_entry_price, 2),
                    exit_price=round(exit_price, 2),
                    target_price=round(pos_target_price, 2),
                    stop_loss=round(pos_stop_loss, 2),
                    position_size_pct=round(pos_size_pct, 2),
                    shares=round(pos_shares, 2),
                    pnl_tl=round((gross - comm) - (pos_shares * pos_entry_price), 2),
                    return_pct=round(((exit_price - pos_entry_price) / pos_entry_price) * 100.0, 2),
                    exit_reason="end_of_period",
                    holding_days=days_in_trade,
                )
            )

        return self._calculate_metrics(strategy_name, ticker, capital, equity_curve, trades)

    def _calculate_metrics(
        self,
        strategy_name: str,
        ticker: str,
        final_capital: float,
        equity_curve: list[dict],
        trades: list[TradeRecord],
    ) -> dict[str, Any]:
        start_date = self.price_rows[20]["date"]
        end_date = self.price_rows[-1]["date"]

        total_return_pct = round(((final_capital - self.initial_capital) / self.initial_capital) * 100.0, 2)

        try:
            d_start = datetime.strptime(start_date, "%Y-%m-%d")
            d_end = datetime.strptime(end_date, "%Y-%m-%d")
            days_span = max(1, (d_end - d_start).days)
            years_span = days_span / 365.25
            cagr_pct = round(((final_capital / self.initial_capital) ** (1.0 / years_span) - 1.0) * 100.0, 2)
        except Exception:
            cagr_pct = total_return_pct

        equities = [pt["equity"] for pt in equity_curve]
        if len(equities) > 1:
            returns = np.diff(equities) / equities[:-1]
            mean_ret = float(np.mean(returns))
            std_ret = float(np.std(returns)) if len(returns) > 1 else 0.0

            rf_daily = (1.0 + 0.40) ** (1.0 / 252.0) - 1.0
            excess_ret = mean_ret - rf_daily

            sharpe = round((excess_ret / std_ret) * math.sqrt(252.0), 2) if std_ret > 1e-9 else 0.0

            downside_returns = returns[returns < 0]
            downside_std = float(np.std(downside_returns)) if len(downside_returns) > 1 else std_ret
            sortino = round((excess_ret / downside_std) * math.sqrt(252.0), 2) if downside_std > 1e-9 else 0.0

            peaks = np.maximum.accumulate(equities)
            drawdowns = (peaks - equities) / peaks
            max_drawdown_pct = round(float(np.max(drawdowns)) * 100.0, 2)
        else:
            sharpe = 0.0
            sortino = 0.0
            max_drawdown_pct = 0.0

        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.pnl_tl > 0)
        losing_trades = sum(1 for t in trades if t.pnl_tl <= 0)
        hit_rate_pct = round((winning_trades / total_trades * 100.0), 2) if total_trades > 0 else 0.0

        gross_gains = sum(t.pnl_tl for t in trades if t.pnl_tl > 0)
        gross_losses = abs(sum(t.pnl_tl for t in trades if t.pnl_tl < 0))
        profit_factor = round(gross_gains / gross_losses, 2) if gross_losses > 0 else (99.0 if gross_gains > 0 else 0.0)

        run_id = f"bt_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        return {
            "run_id": run_id,
            "strategy_name": strategy_name,
            "ticker": ticker,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": self.initial_capital,
            "final_capital": round(final_capital, 2),
            "total_return_pct": total_return_pct,
            "cagr_pct": cagr_pct,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown_pct": max_drawdown_pct,
            "hit_rate_pct": hit_rate_pct,
            "profit_factor": profit_factor,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "commission_pct": self.commission_pct,
            "slippage_pct": self.slippage_pct,
            "created_at": now_iso,
            "trades": [asdict(t) for t in trades],
            "equity_curve": equity_curve,
        }

    def _empty_result(self, strategy_name: str) -> dict[str, Any]:
        return {
            "run_id": f"bt_{uuid.uuid4().hex[:12]}",
            "strategy_name": strategy_name,
            "ticker": "N/A",
            "start_date": "",
            "end_date": "",
            "initial_capital": self.initial_capital,
            "final_capital": self.initial_capital,
            "total_return_pct": 0.0,
            "cagr_pct": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "hit_rate_pct": 0.0,
            "profit_factor": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "commission_pct": self.commission_pct,
            "slippage_pct": self.slippage_pct,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trades": [],
            "equity_curve": [],
        }


class BacktraderDynamicRiskStrategy(bt.Strategy):
    """Backtrader Cerebro framework ile entegre dinamik risk stratejisi."""

    params = (
        ("account_risk_pct", 1.5),
        ("horizon_days", 20),
    )

    def __init__(self):
        self.atr = bt.indicators.ATR(self.data, period=20)
        self.sma20 = bt.indicators.SMA(self.data.close, period=20)
        self.order = None
        self.entry_bar = 0
        self.stop_price = 0.0
        self.target_price = 0.0

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.data.close[0] >= self.sma20[0] * 0.98 and self.atr[0] > 0:
                current_price = self.data.close[0]
                entry_low = current_price - 0.5 * self.atr[0]
                stop_loss = entry_low - 1.5 * self.atr[0]
                target_price = current_price + 2.5 * self.atr[0]

                risk_per_share = max(0.01, current_price - stop_loss)
                portfolio_val = self.broker.getvalue()
                risk_tl = portfolio_val * (self.params.account_risk_pct / 100.0)
                shares = int(risk_tl / risk_per_share)

                if shares > 0 and current_price * shares <= portfolio_val * 0.25:
                    self.order = self.buy(size=shares)
                    self.entry_bar = len(self)
                    self.stop_price = stop_loss
                    self.target_price = target_price
        else:
            bars_held = len(self) - self.entry_bar
            if self.data.low[0] <= self.stop_price:
                self.order = self.close()
            elif self.data.high[0] >= self.target_price:
                self.order = self.close()
            elif bars_held >= self.params.horizon_days:
                self.order = self.close()


def run_backtrader_backtest(
    ticker: str,
    as_of_date: str = "2026-09-17",
    days: int = 250,
    initial_capital: float = 100_000.0,
    commission_pct: float = 0.15,
) -> dict[str, Any]:
    """Backtrader Cerebro framework ile tam backtest calistirir."""
    prices = bist_mcp.get_prices(ticker, as_of_date, days=days)
    if len(prices) < 25:
        return {"ticker": ticker, "status": "insufficient_data"}

    df = pd.DataFrame(prices)
    df["datetime"] = pd.to_datetime(df["date"])
    df.set_index("datetime", inplace=True)
    data = bt.feeds.PandasData(dataname=df, openinterest=-1)

    cerebro = bt.Cerebro()
    cerebro.addstrategy(BacktraderDynamicRiskStrategy)
    cerebro.adddata(data)
    cerebro.broker.setcash(initial_capital)
    cerebro.broker.setcommission(commission=commission_pct / 100.0)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

    results = cerebro.run()
    strat = results[0]
    dd = strat.analyzers.drawdown.get_analysis()
    ta = strat.analyzers.trades.get_analysis()

    final_val = cerebro.broker.getvalue()
    tot_ret = ((final_val - initial_capital) / initial_capital) * 100.0
    closed_trades = ta.get("total", {}).get("closed", 0)
    won = ta.get("won", {}).get("total", 0)
    hit_rate = (won / closed_trades * 100.0) if closed_trades > 0 else 0.0

    return {
        "engine": "backtrader_cerebro",
        "ticker": ticker,
        "initial_capital": initial_capital,
        "final_capital": round(final_val, 2),
        "total_return_pct": round(tot_ret, 2),
        "max_drawdown_pct": round(dd.max.drawdown, 2) if hasattr(dd, "max") else 0.0,
        "total_trades": closed_trades,
        "winning_trades": won,
        "hit_rate_pct": round(hit_rate, 2),
    }


def save_backtest_results(result: dict[str, Any]) -> str:
    """Backtest sonucunu ve islemlerini SQLite veritabanina yazar."""
    run_id = result["run_id"]
    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO backtest_results (
                run_id, strategy_name, ticker, start_date, end_date,
                initial_capital, final_capital, total_return_pct, cagr_pct,
                sharpe_ratio, sortino_ratio, max_drawdown_pct, hit_rate_pct,
                profit_factor, total_trades, winning_trades, losing_trades,
                commission_pct, slippage_pct, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                result["strategy_name"],
                result["ticker"],
                result["start_date"],
                result["end_date"],
                result["initial_capital"],
                result["final_capital"],
                result["total_return_pct"],
                result["cagr_pct"],
                result["sharpe_ratio"],
                result["sortino_ratio"],
                result["max_drawdown_pct"],
                result["hit_rate_pct"],
                result["profit_factor"],
                result["total_trades"],
                result["winning_trades"],
                result["losing_trades"],
                result["commission_pct"],
                result["slippage_pct"],
                result["created_at"],
            ),
        )

        trade_rows = [
            (
                run_id,
                t["ticker"],
                t["entry_date"],
                t["exit_date"],
                t["entry_price"],
                t["exit_price"],
                t["target_price"],
                t["stop_loss"],
                t["position_size_pct"],
                t["shares"],
                t["pnl_tl"],
                t["return_pct"],
                t["exit_reason"],
            )
            for t in result.get("trades", [])
        ]

        if trade_rows:
            conn.executemany(
                """INSERT INTO backtest_trades (
                    run_id, ticker, entry_date, exit_date, entry_price, exit_price,
                    target_price, stop_loss, position_size_pct, shares, pnl_tl,
                    return_pct, exit_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                trade_rows,
            )
        conn.commit()
    finally:
        conn.close()

    return run_id


def format_backtest_report(result: dict[str, Any]) -> str:
    """Kullanici dostu terminal / markdown backtest raporu uretir."""
    lines = [
        "==================================================================",
        f"        BIST SCREENER BACKTEST RAPORU — {result['ticker']}",
        "==================================================================",
        f"Strateji      : {result['strategy_name']}",
        f"Tarih Araligi : {result['start_date']} -> {result['end_date']}",
        f"Baslangic     : {result['initial_capital']:,.2f} TL",
        f"Bitis         : {result['final_capital']:,.2f} TL",
        f"Toplam Getiri : %{result['total_return_pct']:.2f}",
        f"CAGR          : %{result['cagr_pct']:.2f}",
        "------------------------------------------------------------------",
        f"Sharpe Orani  : {result['sharpe_ratio']:.2f}",
        f"Sortino Orani : {result['sortino_ratio']:.2f}",
        f"Max Drawdown  : %{result['max_drawdown_pct']:.2f}",
        f"Isabet (Hit)  : %{result['hit_rate_pct']:.2f} ({result['winning_trades']}/{result['total_trades']})",
        f"Profit Factor : {result['profit_factor']:.2f}",
        f"Komisyon/Kayma: %{result['commission_pct']} / %{result['slippage_pct']}",
        "==================================================================",
    ]

    trades = result.get("trades", [])
    if trades:
        lines.append("\nGerceklesen Islemler:")
        lines.append(f"{'Giris':<11} {'Cikis':<11} {'Alis':<8} {'Satis':<8} {'Getiri %':<9} {'PnL (TL)':<11} {'Neden'}")
        lines.append("-" * 72)
        for t in trades:
            lines.append(
                f"{t['entry_date']:<11} {t['exit_date']:<11} {t['entry_price']:<8.2f} "
                f"{t['exit_price']:<8.2f} {t['return_pct']:<9.2f} {t['pnl_tl']:<11.2f} {t['exit_reason']}"
            )
        lines.append("-" * 72)
    else:
        lines.append("\nBu donemde filtreleri karsilayan islem gerceklesmedi.")

    return "\n".join(lines)


def run_backtest(
    ticker: str,
    as_of_date: str = "2026-09-17",
    days: int = 250,
    initial_capital: float = 100_000.0,
    commission_pct: float = 0.15,
    slippage_pct: float = 0.10,
    save_to_db: bool = True,
    adjust_prices: bool = True,
    audit_quality: bool = True,
) -> dict[str, Any]:
    """Tekil bir hisse veya liste icin walk-forward backtest calistirir."""
    from core.data_quality import adjust_price_series, audit_ticker_data_quality, fetch_corporate_actions

    prices = bist_mcp.get_prices(ticker, as_of_date, days=days)
    actions = []
    if adjust_prices or audit_quality:
        actions = fetch_corporate_actions(ticker, as_of_date)

    if audit_quality and prices:
        audit_ticker_data_quality(ticker, prices, as_of_date=as_of_date, corporate_actions=actions)

    if adjust_prices and prices:
        prices = adjust_price_series(prices, actions)

    engine = WalkForwardEngine(
        price_rows=prices,
        initial_capital=initial_capital,
        commission_pct=commission_pct,
        slippage_pct=slippage_pct,
    )
    result = engine.run(strategy_name="dynamic_risk_walkforward")
    if save_to_db and result.get("run_id"):
        save_backtest_results(result)
    return result


def main():
    parser = argparse.ArgumentParser(description="BIST Screener Walk-Forward Backtester")
    parser.add_argument("--ticker", type=str, default="FORTE", help="Test edilecek hisse kodu (orn. FORTE)")
    parser.add_argument("--date", type=str, default="2026-09-17", help="Degerlendirme tarihi (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=250, help="Geriye donuk incelenecek gun sayisi")
    parser.add_argument("--capital", type=float, default=100000.0, help="Baslangic sermayesi TL")
    parser.add_argument("--backtrader", action="store_true", help="Backtrader Cerebro motoruyla da calistir")

    args = parser.parse_args()

    print(f"\n[Backtest] {args.ticker} icin walk-forward simülasyonu baslatiliyor...\n")
    res = run_backtest(args.ticker, as_of_date=args.date, days=args.days, initial_capital=args.capital)
    print(format_backtest_report(res))

    if args.backtrader:
        print("\n[Backtrader] Cerebro framework ile dogrulaniyor...")
        bt_res = run_backtrader_backtest(args.ticker, as_of_date=args.date, days=args.days, initial_capital=args.capital)
        print(f"Cerebro Bitis Sermayesi : {bt_res['final_capital']} TL")
        print(f"Cerebro Toplam Getiri   : %{bt_res['total_return_pct']}")
        print(f"Cerebro Max Drawdown    : %{bt_res['max_drawdown_pct']}")
        print(f"Cerebro Kapanan Islem   : {bt_res['total_trades']}")


if __name__ == "__main__":
    main()
