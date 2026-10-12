"""Ulke riski paneli: medyan spread, hata durumu ve bulten dogrulama kapisi."""
from __future__ import annotations

import pandas as pd

from core import sovereign_spread as ss


def test_median_spread_maturity_window():
    on = pd.Timestamp("2026-10-12")
    ust = pd.Series({"^FVX": 4.0, "^TNX": 4.4, "^TYX": 4.8})
    bonds = [{"maturity": "2027-06-01", "yield": 6.0},   # <3 yil: disarida
             {"maturity": "2031-10-12", "yield": 7.0},   # 5y: 7-4.0 = 3.0
             {"maturity": "2036-10-12", "yield": 7.6},   # 10y: 7.6-4.4 = 3.2
             {"maturity": "2046-10-12", "yield": 8.0}]   # 20y: 8-4.6 = 3.4
    assert abs(ss.median_spread(bonds, ust, on) - 3.2) < 0.01


def test_build_panel_unavailable_on_error(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fail(name, *a, **k):
        if name == "yfinance":
            raise ImportError("no network")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fail)
    assert ss.build_panel("2026-10-12") == {"status": "unavailable"}


def test_panel_renders_and_passes_validation(temp_db):
    from report.render import render_mobile_newsletter
    from report.validate import find_orphan_numbers, find_banned_claims
    panel = {"status": "ok", "date": "2026-10-12", "spread_pp": 2.66, "prev_date": "2026-09-11",
             "change_bp": -14, "sensitivity_pct": 12.4, "per_bp": 100}
    ctx = {"as_of_date": "2026-10-12", "long_term_candidates": [], "short_term_candidates": [],
           "long_term_display_count": 0, "short_term_display_count": 0, "sector_rotation": [],
           "no_action_today": True, "rotation": {}, "portfolio_correlation": {}, "sovereign_spread": panel}
    html = render_mobile_newsletter(ctx)
    assert "Ülke riski" in html and "2.66" in html.replace(",", ".")
    assert find_orphan_numbers(html, {"sovereign_spread": panel}) == []
    assert find_banned_claims(html) == []
    detail = open("report/templates/newsletter.html.j2", encoding="utf-8").read()
    assert "sovereign_spread.spread_pp" in detail
