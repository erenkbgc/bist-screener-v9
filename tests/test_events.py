"""event calendar testi: bilanco_aciklama_tarihi yalnizca KAP'ta acikca ilan
edildiginde dolu olmali, aksi halde bos donmeli, tahmin uretilmemeli."""
from core.events import fetch_upcoming_events
from kap_web_mcp import server as kap_web_mcp


def test_no_dates_are_fabricated_when_source_has_none(temp_db, monkeypatch):
    monkeypatch.setattr(kap_web_mcp, "get_upcoming_events", lambda tickers, as_of_date: [])
    result = fetch_upcoming_events("2026-09-10", ["AAA"])
    assert result["AAA"] == []


def test_earnings_date_only_present_when_officially_announced(temp_db, monkeypatch):
    monkeypatch.setattr(kap_web_mcp, "get_upcoming_events", lambda tickers, as_of_date: [
        {"ticker": "AAA", "event_type": "bilanco_aciklama_tarihi", "event_date": "2026-10-01",
         "source": "KAP (sirket tarafindan resmen ilan edildi)", "coverage_note": "dusuk"},
    ])
    result = fetch_upcoming_events("2026-09-10", ["AAA"])
    assert len(result["AAA"]) == 1
    assert result["AAA"][0]["event_type"] == "bilanco_aciklama_tarihi"
    assert "KAP" in result["AAA"][0]["source"]


def test_events_only_from_official_sources(temp_db, monkeypatch):
    events = [
        {"ticker": "AAA", "event_type": "bist_index_rebalance", "event_date": "2026-10-01",
         "source": "Borsa Istanbul endeks revizyon takvimi", "coverage_note": "yuksek"},
    ]
    monkeypatch.setattr(kap_web_mcp, "get_upcoming_events", lambda tickers, as_of_date: events)
    result = fetch_upcoming_events("2026-09-10", ["AAA"])
    assert result["AAA"][0]["source"] == "Borsa Istanbul endeks revizyon takvimi"
