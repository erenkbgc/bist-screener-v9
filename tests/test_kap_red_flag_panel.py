"""KAP kirmizi bayrak paneli: eksik gun takibi, KAP hatasi, sablon/validate kapisi."""
from datetime import date, timedelta
from pathlib import Path

from core import kap_api, kap_red_flag_panel as panel

AS_OF = "2026-10-10"


def _row(idx, day, codes, subject, summary):
    return {"disclosureIndex": idx, "publishDate": f"{day:%d.%m.%Y} 10:00:00", "stockCodes": codes,
            "subject": subject, "summary": summary}


def _fake_fetch(rows_by_day, calls):
    def fetch(http, fr, to, **kw):
        calls.append((fr, to))
        return [r for d, rs in rows_by_day.items() if fr <= d <= to for r in rs]
    return fetch


def test_refresh_fetches_window_and_builds_panel(temp_db, monkeypatch):
    d = date(2026, 9, 1)
    rows = {d: [_row(1, d, "AAA", "Özel Durum Açıklaması (Genel)", "Konkordato Süreci Hakkında Bilgilendirme"),
                _row(2, d, "AAA, BBB", "Özel Durum Açıklaması (Genel)", "Yeni fabrika yatırımı"),
                _row(3, d, "CCC", "Finansal Rapor", None)]}
    calls = []
    monkeypatch.setattr(kap_api, "fetch_range", _fake_fetch(rows, calls))
    out = panel.refresh(AS_OF, http=object(), sleep_s=0)
    assert out["error"] is None
    # 181 gun, en fazla 7 gunluk pencereler.
    assert len(calls) == 26 and all((to - fr).days < 7 for fr, to in calls)

    p = panel.build_panel(AS_OF, ["AAA", "BBB"])
    assert p["status"] == "ok" and p["missing_days"] == 0
    assert p["n_flagged_holdings"] == 1
    assert p["holdings"][0]["ticker"] == "AAA"
    assert p["holdings"][0]["categories"] == [{
        "category": "insolvency", "label": p["holdings"][0]["categories"][0]["label"], "count": 1,
        "last_date": "2026-09-01", "disclosure_index": 1, "url": "https://www.kap.org.tr/tr/Bildirim/1"}]

    # Ikinci kosu: yalnizca kosu gunu (bitmemis) yeniden cekilir.
    calls.clear()
    panel.refresh(AS_OF, http=object(), sleep_s=0)
    assert calls == [(date(2026, 10, 10), date(2026, 10, 10))]


def test_kap_error_marks_panel_partial_not_clean(temp_db, monkeypatch):
    calls = []
    good = _fake_fetch({}, calls)

    def flaky(http, fr, to, **kw):
        if len(calls) >= 3:
            raise RuntimeError("Server disconnected")
        return good(http, fr, to)
    monkeypatch.setattr(kap_api, "fetch_range", flaky)
    out = panel.refresh(AS_OF, http=object(), sleep_s=0)
    assert "Server disconnected" in out["error"]
    p = panel.build_panel(AS_OF, ["AAA"], out["error"])
    assert p["status"] == "partial" and p["missing_days"] > 0


def test_no_fetch_means_unavailable(temp_db):
    p = panel.build_panel(AS_OF, ["AAA"])
    assert p["status"] == "unavailable" and p["holdings"] == []


def test_windows_split_on_gaps_and_week():
    d = date(2026, 1, 1)
    days = [d + timedelta(days=i) for i in range(10)] + [d + timedelta(days=20)]
    assert panel._windows(days) == [(d, d + timedelta(days=6)), (d + timedelta(days=7), d + timedelta(days=9)),
                                    (d + timedelta(days=20), d + timedelta(days=20))]


def _ctx(kap):
    rotation = {"rebalance_date": "2026-10-01", "buy": [{"ticker": "AAA"}], "hold": [], "sell": [],
                "n_holdings": 23, "top_pct": 20.0}
    return {"as_of_date": AS_OF, "long_term_candidates": [], "short_term_candidates": [],
            "long_term_display_count": 0, "short_term_display_count": 0, "sector_rotation": [],
            "no_action_today": True, "rotation": rotation, "portfolio_correlation": {},
            "kap_red_flags": kap}, {"rotation": rotation, "kap_red_flags": kap}


def test_panel_passes_validation_gate(temp_db, monkeypatch):
    from report.render import render_mobile_newsletter
    from report.validate import find_orphan_numbers
    d = date(2026, 9, 1)
    rows = {d: [_row(1666590 + i, d, "AAA", "Özel Durum Açıklaması (Genel)", "Konkordato 41. Taksit Ödemesi")
                for i in range(5)]}
    monkeypatch.setattr(kap_api, "fetch_range", _fake_fetch(rows, []))
    panel.refresh(AS_OF, http=object(), sleep_s=0)
    kap = panel.build_panel(AS_OF, ["AAA"])
    assert kap["holdings"][0]["categories"][0]["count"] == 5
    ctx, payload = _ctx(kap)
    html = render_mobile_newsletter(ctx)
    assert "KAP kırmızı bayrak" in html and "Konkordato" in html and "5 bildirim, son 2026-09-01" in html
    assert find_orphan_numbers(html, payload) == []
    # Detay sablonu tam kosu baglami ister; mock run.py testleri onu render eder.
    detail = (Path(__file__).resolve().parent.parent / "report/templates/newsletter.html.j2").read_text(encoding="utf-8")
    assert "KAP Kirmizi Bayraklar" in detail and 'kap_red_flags.status == "unavailable"' in detail


def test_unavailable_panel_never_says_no_flags(temp_db):
    from report.render import render_mobile_newsletter
    ctx, _ = _ctx(panel.build_panel(AS_OF, ["AAA"]))
    html = render_mobile_newsletter(ctx)
    assert "KAP verisi alınamadı" in html and "bayrak yok" not in html
