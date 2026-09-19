"""catalyst_engine testi: KAP bildirimlerinden kural-tabanli, zamanla sonumlenen
katalizor (sentiment) skoru. no_free_text_interpretation_of_kap: yalnizca
category/impact_sign/weight sayisal olarak islenir.

kap_earnings_surprise_data_source_gap (2026-09-19): financial_report kategorisi
'neutral' olmali -- gercek EPS beklenti/gerceklesen verisi olmadan kar
acikla/kacir yonu UYDURULAMAZ (bkz. TODO.md, config/catalyst_decay.yaml)."""
from core import catalysts
from kap_web_mcp import server as kap_web_mcp


def _disclosure(ticker, category, published_at, impact_sign="positive", disclosure_id=None):
    return {
        "ticker": ticker,
        "disclosure_id": disclosure_id or f"{ticker}-{published_at}-0",
        "category": category,
        "title": category,
        "summary": "test",
        "impact_sign": impact_sign,
        "url": "",
        "published_at": published_at,
        "available_at": published_at,
        "effective_at": published_at,
    }


def test_financial_report_contributes_neutral_not_fabricated_positive(temp_db, monkeypatch):
    """Kok neden testi: eskiden HER 'financial_report' bildirimi (sabit
    impact_sign='positive' + sign_mode='by_surprise') kosulsuz pozitif
    katalizor sayiliyordu -- gercek kar acikla/kacir bilgisi olmadan.
    Artik sign_mode='neutral' oldugu icin katkisi 0 olmali."""
    monkeypatch.setattr(kap_web_mcp, "get_disclosures",
                         lambda tickers, as_of_date, lookback_days=14: [
                             _disclosure("AAA", "financial_report", as_of_date, impact_sign="positive"),
                         ])
    scores = catalysts.fetch_kap_catalysts("2026-09-17", ["AAA"])
    assert scores["AAA"]["catalyst_score"] == 0.0


def test_share_buyback_contributes_positive(temp_db, monkeypatch):
    monkeypatch.setattr(kap_web_mcp, "get_disclosures",
                         lambda tickers, as_of_date, lookback_days=14: [
                             _disclosure("BBB", "share_buyback", as_of_date),
                         ])
    scores = catalysts.fetch_kap_catalysts("2026-09-17", ["BBB"])
    assert scores["BBB"]["catalyst_score"] > 0.0


def test_vbts_measure_applied_contributes_negative(temp_db, monkeypatch):
    monkeypatch.setattr(kap_web_mcp, "get_disclosures",
                         lambda tickers, as_of_date, lookback_days=14: [
                             _disclosure("CCC", "vbts_measure_applied", as_of_date),
                         ])
    scores = catalysts.fetch_kap_catalysts("2026-09-17", ["CCC"])
    assert scores["CCC"]["catalyst_score"] < 0.0


def test_score_normalized_to_unit_range(temp_db, monkeypatch):
    """Ayni gun icinde birden fazla yuksek agirlikli olumlu olay gelse bile
    catalyst_score [-1, 1] disina cikmamali."""
    monkeypatch.setattr(kap_web_mcp, "get_disclosures",
                         lambda tickers, as_of_date, lookback_days=14: [
                             _disclosure("DDD", "share_buyback", as_of_date, disclosure_id="d1"),
                             _disclosure("DDD", "new_business_or_tender", as_of_date, disclosure_id="d2"),
                             _disclosure("DDD", "insider_buy", as_of_date, disclosure_id="d3"),
                         ])
    scores = catalysts.fetch_kap_catalysts("2026-09-17", ["DDD"])
    assert -1.0 <= scores["DDD"]["catalyst_score"] <= 1.0


def test_ticker_with_no_disclosures_scores_zero(temp_db, monkeypatch):
    monkeypatch.setattr(kap_web_mcp, "get_disclosures",
                         lambda tickers, as_of_date, lookback_days=14: [])
    scores = catalysts.fetch_kap_catalysts("2026-09-17", ["EEE"])
    assert scores["EEE"]["catalyst_score"] == 0.0
    assert scores["EEE"]["volatility_event"] is False


def test_older_disclosure_decays_toward_zero(temp_db, monkeypatch):
    """Ayni kategori, daha eski yayin tarihi -> half-life sonumu nedeniyle
    daha kucuk mutlak katki."""
    monkeypatch.setattr(kap_web_mcp, "get_disclosures",
                         lambda tickers, as_of_date, lookback_days=14: [
                             _disclosure("FFF", "share_buyback", "2026-09-10", disclosure_id="old"),
                         ])
    old_scores = catalysts.fetch_kap_catalysts("2026-09-17", ["FFF"])

    monkeypatch.setattr(kap_web_mcp, "get_disclosures",
                         lambda tickers, as_of_date, lookback_days=14: [
                             _disclosure("FFF", "share_buyback", "2026-09-17", disclosure_id="fresh"),
                         ])
    fresh_scores = catalysts.fetch_kap_catalysts("2026-09-17", ["FFF"])

    assert 0.0 < old_scores["FFF"]["catalyst_score"] < fresh_scores["FFF"]["catalyst_score"]
