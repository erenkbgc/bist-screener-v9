import pandas as pd
import pytest

from core import live_data as ld
from core.fundamentals import fetch_and_store_fundamentals
from core.dividend_sustainability import check_dividend_sustainability
from run import _net_debt_ebitda


def _make_industrial_statements(fin_debt_short=100.0, fin_debt_long=200.0, cash=50.0,
                                op_income=80.0, depreciation=20.0, revenue=500.0):
    bs_data = {
        "2025": [cash, fin_debt_short, fin_debt_long, 1000.0, 500.0],
        "2024": [cash * 0.9, fin_debt_short * 0.9, fin_debt_long * 0.9, 900.0, 450.0],
    }
    bs_idx = [
        "  Nakit ve Nakit Benzerleri",
        "  Finansal Borçlar",
        "  Finansal Borçlar",
        "TOPLAM VARLIKLAR",
        "Özkaynaklar",
    ]
    bs = pd.DataFrame(bs_data, index=bs_idx)

    inc_data = {
        "2025": [revenue, op_income, 50.0],
        "2024": [revenue * 0.9, op_income * 0.9, 45.0],
    }
    inc_idx = [
        "Satış Gelirleri",
        "Net Faaliyet Kar/Zararı",
        "DÖNEM KARI (ZARARI)",
    ]
    inc = pd.DataFrame(inc_data, index=inc_idx)

    cf_data = {
        "2025": [depreciation, 60.0],
        "2024": [depreciation * 0.9, 55.0],
    }
    cf_idx = [
        "Amortisman Giderleri",
        "Serbest Nakit Akım",
    ]
    cf = pd.DataFrame(cf_data, index=cf_idx)
    return bs, inc, cf


def test_net_debt_and_ebitda_calculation_positive(monkeypatch):
    """Sanayi sirketinde borc > nakit durumunda net borc ve FAVOK dogru hesaplanmali."""
    bs, inc, cf = _make_industrial_statements(fin_debt_short=100.0, fin_debt_long=200.0, cash=50.0,
                                              op_income=80.0, depreciation=20.0, revenue=500.0)
    monkeypatch.setattr(ld, "_statements_cached", lambda ticker, fg=None: (bs, inc, cf))
    monkeypatch.setattr(ld, "_fast_info_cached", lambda ticker: {
        "pe_ratio": 10.0, "pb_ratio": 2.0, "market_cap": 1000.0, "shares": 100.0
    })
    monkeypatch.setattr(ld, "_info_cached", lambda ticker: {})
    monkeypatch.setattr(ld, "_dividend_ttm", lambda ticker: 0.0)

    f = ld.live_fundamentals("IND_TEST", "2026-09-18", "SPK_TFRS", "industrial")

    # Finansal Borclar = 100 + 200 = 300, Nakit = 50 -> Net Borc = 250
    assert f["net_debt"] == 250.0
    # EBIT = 80, Amortisman = 20 -> EBITDA = 100
    assert f["ebitda_ttm"] == 100.0
    # EV = Market Cap (1000) + Net Debt (250) = 1250
    # EV / EBITDA = 1250 / 100 = 12.5
    assert f["ev_ebitda"] == pytest.approx(12.5)
    # EV / Sales = 1250 / 500 = 2.5
    assert f["ev_sales"] == pytest.approx(2.5)


def test_net_debt_negative_net_cash(monkeypatch):
    """Nakit > borc durumunda sirket net nakit pozisyonundadir (net_debt < 0)."""
    bs, inc, cf = _make_industrial_statements(fin_debt_short=20.0, fin_debt_long=30.0, cash=150.0,
                                              op_income=80.0, depreciation=20.0, revenue=500.0)
    monkeypatch.setattr(ld, "_statements_cached", lambda ticker, fg=None: (bs, inc, cf))
    monkeypatch.setattr(ld, "_fast_info_cached", lambda ticker: {
        "pe_ratio": 10.0, "pb_ratio": 2.0, "market_cap": 1000.0, "shares": 100.0
    })
    monkeypatch.setattr(ld, "_info_cached", lambda ticker: {})
    monkeypatch.setattr(ld, "_dividend_ttm", lambda ticker: 0.0)

    f = ld.live_fundamentals("CASH_TEST", "2026-09-18", "SPK_TFRS", "industrial")

    # Borc = 50, Nakit = 150 -> Net Borc = -100 (Net Nakit)
    assert f["net_debt"] == -100.0
    assert f["ebitda_ttm"] == 100.0
    # EV = 1000 - 100 = 900
    # EV / EBITDA = 900 / 100 = 9.0
    assert f["ev_ebitda"] == pytest.approx(9.0)


def test_ev_ebitda_guard_against_negative_ebitda_and_negative_ev(monkeypatch):
    """Faaliyet zarari olan (EBITDA <= 0) veya EV <= 0 olan sirketlerde carpanlar None kalmali."""
    # Zarar eden sirket: EBIT = -50, Depr = 10 -> EBITDA = -40
    bs, inc, cf = _make_industrial_statements(fin_debt_short=10.0, fin_debt_long=10.0, cash=50.0,
                                              op_income=-50.0, depreciation=10.0, revenue=200.0)
    monkeypatch.setattr(ld, "_statements_cached", lambda ticker, fg=None: (bs, inc, cf))
    monkeypatch.setattr(ld, "_fast_info_cached", lambda ticker: {
        "pe_ratio": None, "pb_ratio": 1.0, "market_cap": 100.0, "shares": 10.0
    })
    monkeypatch.setattr(ld, "_info_cached", lambda ticker: {})
    monkeypatch.setattr(ld, "_dividend_ttm", lambda ticker: 0.0)

    f = ld.live_fundamentals("LOSS_TEST", "2026-09-18", "SPK_TFRS", "industrial")

    assert f["ebitda_ttm"] == -40.0
    # Negatif EBITDA durumunda carpan carpikligini onlemek icin ev_ebitda None olmali
    assert f["ev_ebitda"] is None
    # EV = 100 + (20 - 50) = 70 > 0, revenue > 0 -> EV/Sales olusabilir
    assert f["ev_sales"] == pytest.approx(70.0 / 200.0)


def test_bank_and_insurance_keep_net_debt_and_ev_ebitda_none(monkeypatch):
    """Banka ve sigortada ev_ebitda, ev_sales, net_debt ve ebitda_ttm None kalmali."""
    bs, inc, cf = _make_industrial_statements()
    monkeypatch.setattr(ld, "_statements_cached", lambda ticker, fg=None: (bs, inc, cf))
    monkeypatch.setattr(ld, "_fast_info_cached", lambda ticker: {
        "pe_ratio": 5.0, "pb_ratio": 1.0, "market_cap": 1000.0, "shares": 100.0
    })
    monkeypatch.setattr(ld, "_info_cached", lambda ticker: {})
    monkeypatch.setattr(ld, "_dividend_ttm", lambda ticker: 0.0)

    f_bank = ld.live_fundamentals("BANK_TEST", "2026-09-18", "BDDK", "bank")
    assert f_bank["net_debt"] is None
    assert f_bank["ebitda_ttm"] is None
    assert f_bank["ev_ebitda"] is None
    assert f_bank["ev_sales"] is None

    f_ins = ld.live_fundamentals("INS_TEST", "2026-09-18", "SEDDK", "insurance")
    assert f_ins["net_debt"] is None
    assert f_ins["ebitda_ttm"] is None
    assert f_ins["ev_ebitda"] is None
    assert f_ins["ev_sales"] is None


def test_run_net_debt_ebitda_safeguards():
    """run.py'deki _net_debt_ebitda negatif/sifir EBITDA durumunda None donmeli."""
    # Normal durum
    assert _net_debt_ebitda(200.0, 100.0) == 2.0
    # Net nakit durumu (ebitda pozitif, borc negatif)
    assert _net_debt_ebitda(-50.0, 100.0) == -0.5
    # Zarar durumu: ebitda negatif veya sifir -> None (ranking'i yaniltmaz)
    assert _net_debt_ebitda(200.0, -50.0) is None
    assert _net_debt_ebitda(200.0, 0.0) is None
    assert _net_debt_ebitda(None, 100.0) is None
    assert _net_debt_ebitda(200.0, None) is None


def test_dividend_sustainability_with_distressed_debt(temp_db, monkeypatch):
    """Zarar eden (EBITDA <= 0) ve borclu sirket temettu surdurulebilirliginde yuksek risk alir."""
    monkeypatch.setattr("bist_mcp.server.get_dividend_history", lambda t, d: {
        "dividend_streak_years": 3,
        "payout_ratio_trend_3p": "artiyor",
    })
    fnd_row = {
        "net_debt": 500.0,
        "fcf_ttm": 100.0,
        "payout_ratio": 0.5,
        "dividend_per_share_ttm": 5.0,
        "market_cap": 1000.0,
        "_raw": {"pe": 10.0, "ebitda_ttm": -50.0}
    }
    res = check_dividend_sustainability("2026-09-18", "TEST", fnd_row)
    assert res["passes_sustainability"] == 0

def test_fundamentals_db_upsert_stores_recovered_fields(temp_db, monkeypatch):
    """fundamentals tablosuna ekleme ve guncellemede ebitda_ttm, net_debt ve EV carpanlari DB'ye yazilmali."""
    from core import db
    from core.fundamentals import fetch_and_store_fundamentals

    u_rows = [{
        "ticker": "TEST_IND", "regulator": "SPK_TFRS", "ratio_profile": "industrial",
        "market_cap": 1e9, "sector": "Sanayi", "supersector": "Uretim",
        "tedbir_level": 0, "listing_days": 500,
    }]

    rows = fetch_and_store_fundamentals("2026-09-18", u_rows)
    assert len(rows) == 1
    assert rows[0]["ebitda_ttm"] is not None
    assert rows[0]["net_debt"] is not None

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ebitda_ttm, net_debt, ev_ebitda, ev_sales FROM fundamentals WHERE ticker='TEST_IND'")
    res = cur.fetchone()
    conn.close()

    assert res[0] is not None
    assert res[1] is not None

