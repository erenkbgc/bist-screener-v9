"""Holding sektoru canli-panel esitligi (Task 2 regresyon ve parity testi).

Arastirma paneli (data/research/factors_monthly.parquet) Holding ve Girisim
Sermayesi Yat. Ort. hisselerini ICERIR (pit_panel.FINANCIAL_SECTORS yalnizca
banka/sigorta/faktoring/leasing/araci kurum/MKYO vb. dislar). Canli run.py
eskiden bilgi amacli target_price None dondugunde `continue` ile adayi tamamen
atliyordu; Holding sektor medyan NAV iskontosu > %60 oldugunda (2026-11-01:
medyan 0.6156 -> 1/(1-0.6156) = 2.60x > 2.5x siniri) tum Holding sektoru ve
tum GSYO'lar (ve 2.5x/3.5x sinirina takilan cok ucuz sanayi hisseleri) scores
ve aylik rotasyon evreninden sessizce dusuyordu.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import run as runner
from core import db, factor_backtest as fb, pit_panel, rotation


def _price_series(start_price: float, days: int = 273, vol: float = 5_000_000.0) -> list[dict]:
    dates = pd.bdate_range(end="2026-11-01", periods=days)
    rows = []
    for i, dt in enumerate(dates):
        p = start_price * (1.0 + 0.0005 * (i % 7 - 3))
        rows.append({
            "date": dt.date().isoformat(),
            "open": p, "high": p * 1.02, "low": p * 0.98,
            "close": p, "adj_close": p,
            "volume": vol / p,
            "sma20": p, "sma50": p, "atr20": p * 0.02,
            "volume_ratio_20d": 1.0, "volatility_60d": 0.02,
        })
    return rows


def test_run_scores_and_rotates_holdings_when_target_price_is_none(temp_db, monkeypatch):
    """Holding medyan nav_discount > 0.60 -> target_price None olsa bile Holding
    hisseleri scores tablosuna valuation_z ile yazilir, R0 rotasyon evrenine
    paneldekiyle birebir ayni valuation_z ile girer; finansallar haric kalir."""
    from bist_mcp import server as bist_mcp
    from kap_web_mcp import server as kap_web_mcp
    from macro_mcp import server as macro_mcp

    # 10 Holding (medyan nav_discount = 0.65 -> 1/(1-0.65) = 2.86 > 2.5 -> target_price None),
    # 35 Sanayi (VESBE cok ucuz pb=0.1 -> target_price None; toplam 45 finansal-disi -> %30 likidite
    # kesiminden sonra 32 hisse >= fb.prepare varsayilan min_names=30),
    # 5 Banka (FINANCIAL_SECTORS -> rotasyondan haric, untested_financials'ta).
    holdings = [
        ("KCHOL", "Holding", "holding", "SPK_TFRS", 500e9, 0.62, {"bm": 2.6, "ep": 0.14, "sp": 8.0, "ey": 0.18}),
        ("SAHOL", "Holding", "holding", "SPK_TFRS", 170e9, 0.76, {"bm": 4.1, "ep": 0.18, "sp": 9.5, "ey": 0.25}),
        ("AGHOL", "Holding", "holding", "SPK_TFRS", 60e9, 0.84, {"bm": 2.4, "ep": 0.08, "sp": 14.0, "ey": 0.15}),
        ("DOHOL", "Holding", "holding", "SPK_TFRS", 41e9, 0.64, {"bm": 2.8, "ep": 0.12, "sp": 6.0, "ey": 0.20}),
        ("BERA",  "Holding", "holding", "SPK_TFRS", 7e9,  0.66, {"bm": 5.2, "ep": 0.05, "sp": 3.5, "ey": 0.42}),
        ("BRYAT", "Holding", "holding", "SPK_TFRS", 33e9, 0.19, {"bm": 1.0, "ep": 0.15, "sp": 1.2, "ey": 0.10}),
        ("GSDHO", "Holding", "holding", "SPK_TFRS", 4e9,  0.71, {"bm": 3.9, "ep": 0.13, "sp": 0.6, "ey": 0.41}),
        ("NTHOL", "Holding", "holding", "SPK_TFRS", 17e9, 0.82, {"bm": 4.8, "ep": 0.09, "sp": 1.1, "ey": 0.22}),
        ("ECILC", "Holding", "holding", "SPK_TFRS", 29e9, 0.61, {"bm": 2.5, "ep": 0.06, "sp": 1.4, "ey": 0.11}),
        ("KLRHO", "Holding", "holding", "SPK_TFRS", 25e9, 0.55, {"bm": 1.4, "ep": 0.07, "sp": 1.8, "ey": 0.08}),
    ]
    ind_sectors = ["İmalat", "Gıda ve İçecek", "Ana Metal", "Kimya ve Plastik"]
    industrials = [
        ("VESBE", "İmalat", "industrial", "SPK_TFRS", 30e9, None, {"bm": 9.0, "ep": 0.10, "sp": 5.0, "ey": 0.22}),
        *[
            (f"IND{i:02d}", ind_sectors[i % len(ind_sectors)], "industrial", "SPK_TFRS",
             (40 - i) * 1e9, None,
             {"bm": 0.4 + 0.08 * i, "ep": 0.03 + 0.005 * i, "sp": 0.7 + 0.15 * i, "ey": 0.04 + 0.008 * i})
            for i in range(1, 35)
        ],
    ]
    banks = [
        (f"BNK{i}", "Bankacılık", "bank", "BDDK", 100e9 + i * 1e9, None, None)
        for i in range(5)
    ]
    specs = {t: (sec, prof, reg, mcap, nav_d, vi) for t, sec, prof, reg, mcap, nav_d, vi in holdings + industrials + banks}

    seed = [{"ticker": t, "name": t, "sector": sec, "ratio_profile": prof, "regulator": reg}
            for t, (sec, prof, reg, _, _, _) in specs.items()]
    prices_map = {t: _price_series(50.0 + idx, vol=100_000_000.0 + ((idx * 19) % 50) * 10_000_000.0)
                  for idx, t in enumerate(specs)}
    xu100 = _price_series(10_000.0, vol=1e11)

    monkeypatch.setattr(bist_mcp, "_live_enabled", lambda: False)
    monkeypatch.setattr(kap_web_mcp, "_live_enabled", lambda: False)
    monkeypatch.setattr(bist_mcp, "get_universe", lambda: seed)
    monkeypatch.setattr(bist_mcp, "prefetch", lambda rows: None)
    monkeypatch.setattr(bist_mcp, "get_listing_and_size", lambda t, d: {
        "listing_days": 1000, "market_cap": specs[t][3], "avg_volume_tl_20d": 100_000_000.0,
    })
    monkeypatch.setattr(bist_mcp, "get_tedbir_level", lambda t, d: {"ticker": t, "tedbir_level": 0})
    monkeypatch.setattr(bist_mcp, "get_prices", lambda t, d, days=140: (xu100 if t == "XU100_INDEX" else prices_map[t])[-days:])
    monkeypatch.setattr(bist_mcp, "get_current_price", lambda t, rows: {"price": rows[-1]["close"], "source": "live"})
    monkeypatch.setattr(bist_mcp, "get_bid_ask", lambda t: {"bid": None, "ask": None})
    monkeypatch.setattr(bist_mcp, "get_financial_report_published_at", lambda t, pe: "2026-10-25")

    def fake_fundamentals(t, d, reg, prof):
        _, _, _, mcap, nav_d, vi = specs[t]
        pb = 0.1 if t == "VESBE" else (1.0 / vi["bm"] if vi else 0.9)
        pe = None if t == "VESBE" else 10.0
        return {
            "reporting_basis": None, "pe": pe, "pb": pb, "ev_ebitda": 6.0 if prof == "industrial" else None,
            "ev_sales": 1.0 if prof == "industrial" else None, "roe": 15.0,
            "eps_ttm": -2.0 if t == "VESBE" else 5.0, "ebitda_ttm": 1e9 if prof == "industrial" else None,
            "net_debt": 0.0 if prof != "bank" else None, "nav_discount": nav_d,
            "dividend_per_share_ttm": 0.0, "payout_ratio": 0.0, "fcf_ttm": 1e8,
            "roa": 5.0, "nim": None, "npl_ratio": None, "car": None, "combined_ratio": None, "ffo_yield": None,
            "_shares_outstanding": mcap / prices_map[t][-1]["close"],
            "_value_inputs": ({**vi, "stmt_period": "2026Q3", "stmt_period_end": "2026-09-30",
                               "available_at": "2026-10-25", "available_source": "kap",
                               "kap_published_at": "2026-10-25T10:00", "kap_available_at": "2026-10-25",
                               "source": "isyatirim_quarterly_ytd", "ttm_unit": "C1_constant_unit",
                               "observed_at": "2026-11-01T15:00:00+00:00", "inputs": {"market_cap": mcap}}
                              if vi else None),
        }

    monkeypatch.setattr(bist_mcp, "get_fundamentals", fake_fundamentals)
    monkeypatch.setattr(bist_mcp, "get_piotroski_raw_criteria",
                        lambda t, d, ratio_profile=None: {f"criterion_{i}": 1 for i in range(1, 9)} | {"criterion_9": None})
    monkeypatch.setattr(bist_mcp, "get_cashflow_for_sloan",
                        lambda t, d, ni, ratio_profile=None: {"operating_cashflow_ttm": 1e8, "average_total_assets": 1e10})
    monkeypatch.setattr(bist_mcp, "get_dividend_history",
                        lambda t, d: {"dividend_streak_years": 0, "payout_ratio_trend_3p": "stabil"})
    monkeypatch.setattr(bist_mcp, "get_ownership", lambda t, d: {
        "investor_count": None, "investor_count_change_1m": None,
        "retail_pct": None, "institutional_pct": None, "free_float_pct": 35.0, "foreign_pct": 20.0,
    })
    monkeypatch.setattr(kap_web_mcp, "get_disclosures", lambda tks, d, lookback_days=14: [])
    monkeypatch.setattr(kap_web_mcp, "disclosures_available", lambda tks: {t: True for t in tks})
    monkeypatch.setattr(kap_web_mcp, "get_upcoming_events", lambda tks, d: [])
    monkeypatch.setattr(macro_mcp, "get_macro_snapshot", lambda d: {
        "policy_rate_pct": 36.0, "bond_2y_pct": 38.0, "bond_10y_pct": 34.0,
        "cpi_yoy_pct": 30.0, "cpi_yearend_expectation_pct": None,
        "usdtry_spot": 50.0, "usdtry_12m_expectation": None,
        "xu100_level": 10000.0, "xu100_pe": None, "foreign_ownership_pct": None,
        "short_selling_ban_active": False, "individual_investor_count_millions": None,
        "ytd_ipo_count": None, "vbts_stock_count": None,
    })
    monkeypatch.setattr(runner.sector_rotation_mod, "compute_sector_rotation", lambda d: {})
    monkeypatch.setattr(runner, "_dispatch", lambda *a, **k: False)

    res = runner.run("2026-11-01", force=True)
    assert res["status"] == "completed"
    assert res["validation"]["is_valid"] is True

    # 1. Tum Holding hisseleri ve cok ucuz VESBE scores tablosunda mevcut ve valuation_z dolu olmali
    score_rows = {r["ticker"]: dict(r) for r in db.query(
        "SELECT * FROM scores WHERE as_of_date='2026-11-01' AND bucket='long_term'"
    )}
    holding_tickers = {t for t, *_ in holdings}
    assert holding_tickers.issubset(score_rows.keys())
    for t in holding_tickers | {"VESBE"}:
        assert score_rows[t]["valuation_z"] is not None, f"{t} valuation_z bos"
        # target_price None oldugu icin bilgi kartlarina (passing) girmez, NO_ACTION/hurdle kalir
        assert score_rows[t]["candidate_state"] == "NO_ACTION"
        assert score_rows[t]["filtered_by"] == "hurdle"

    # 2. Canli valuation_z == arastirma panelinin (factor_backtest) Holding dahil value_sn_z hesabi
    panel_rows = []
    for t, (sec, prof, _, _, _, vi) in specs.items():
        if sec in pit_panel.FINANCIAL_SECTORS:
            continue
        panel_rows.append({
            "date": pd.Timestamp("2026-10-31"), "ticker": t, "sector": sec,
            "tlvol60": rotation.tl_volume_median_60(prices_map[t]), **vi,
        })
    df = fb.prepare(pd.DataFrame(panel_rows), ["bm", "ep", "sp", "ey"])
    df["value_z"] = df[[f"{m}_z" for m in ("bm", "ep", "sp", "ey")]].mean(axis=1)
    panel_z = fb.sector_neutralize(df, "value_z").set_axis(df["ticker"])
    assert any(t in panel_z.index for t in holding_tickers)
    for tk, expected_z in panel_z.items():
        assert score_rows[tk]["valuation_z"] == pytest.approx(expected_z, abs=1e-9), tk

    # 3. Aylik rotasyon (R0) Holding hisselerini icermeli, bankalari dislamali
    rot_rows = [dict(r) for r in db.query("SELECT * FROM rotation_holdings WHERE rebalance_date='2026-11-01'")]
    rot_tickers = {r["ticker"] for r in rot_rows}
    assert rot_tickers, "rotation_holdings bos"
    assert not any(t.startswith("BNK") for t in rot_tickers)
    # Panelin en yuksek value_sn_z ust %20'si ile birebir eslesmeli
    n_top = max(1, round(len(panel_z) * rotation.TOP_PCT))
    expected_top = set(panel_z.sort_values(ascending=False).head(n_top).index)
    assert rot_tickers == expected_top
    assert rot_tickers & holding_tickers, f"Holding secilmedi: {rot_tickers}"
