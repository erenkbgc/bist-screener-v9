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


def test_populate_calendar_from_corporate_actions(temp_db):
    from core.events import get_calendar_events, populate_calendar_from_corporate_actions
    actions = [
        {"action_type": "dividend", "action_date": "2026-10-15", "dividend_amount": 3.25},
        {"action_type": "bonus_issue", "action_date": "2026-11-01", "ratio_or_amount": 100.0, "split_factor": 2.0},
    ]
    events = populate_calendar_from_corporate_actions("XYZ", actions)
    assert len(events) == 2
    assert events[0]["event_type"] == "dividend"
    assert events[1]["event_type"] == "bonus_issue"

    db_events = get_calendar_events("XYZ")
    assert len(db_events) == 2
    assert db_events[0]["ratio_or_amount"] == 3.25


def test_check_signal_corporate_action_warnings(temp_db):
    from core.events import check_signal_corporate_action_warnings, save_calendar_events
    save_calendar_events([
        {
            "ticker": "WARNTICKER",
            "event_date": "2026-09-22",
            "event_type": "dividend",
            "description": "Nakit Temettu 2.0 TL",
            "expected_impact": "Fiyat duzeltmesi",
            "ratio_or_amount": 2.0,
            "source": "test",
        },
        {
            "ticker": "WARNTICKER",
            "event_date": "2026-12-01",  # outside 20-day horizon
            "event_type": "general_assembly",
            "description": "Genel Kurul",
            "expected_impact": "Bilgilendirme",
            "ratio_or_amount": 0.0,
            "source": "test",
        },
    ])

    warnings = check_signal_corporate_action_warnings("WARNTICKER", as_of_date="2026-09-17", horizon_days=20)
    assert len(warnings) == 1
    assert warnings[0]["severity"] == "HIGH"
    assert "Nakit Temettu" in warnings[0]["message"]

