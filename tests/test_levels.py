"""core/levels.py: destek/direnc, hacim profili ve seviye tabanli giris plani."""
from core.levels import find_levels, plan_entry, recent_breakout, volume_profile
from core.targets import compute_dynamic_risk_levels, compute_short_term_target


def _bar(i, lo, hi, close, vol=1_000_000.0, vr=1.0, adj=None):
    return {"date": f"2026-01-{i:03d}", "high": hi, "low": lo, "close": close,
            "adj_close": adj if adj is not None else close, "volume": vol, "volume_ratio_20d": vr}


def _range_market(n=120, floor=95.0, ceil=110.0):
    """floor-ceil arasinda salinan fiyat: 95 destek, 110 direnc."""
    rows, up = [], True
    p = 100.0
    for i in range(n):
        p += 1.5 if up else -1.5
        if p >= ceil:
            p, up = ceil, False
        elif p <= floor:
            p, up = floor, True
        rows.append(_bar(i, p - 0.5, p + 0.5, p, vol=2_000_000.0 if p in (floor, ceil) else 1_000_000.0))
    return rows


def test_range_market_finds_floor_and_ceiling():
    rows = _range_market()
    rows.append(_bar(999, 97.0, 98.0, 97.5))
    lv = find_levels(rows, atr=1.5)
    assert any(abs(z["mid"] - 94.5) < 1.5 for z in lv["supports"])
    assert any(abs(z["mid"] - 110.5) < 1.5 for z in lv["resistances"])


def test_plan_entry_uses_support_and_caps_under_resistance():
    rows = _range_market()
    rows.append(_bar(999, 95.5, 96.5, 96.0))
    lv = find_levels(rows, atr=1.5)
    plan = plan_entry(96.0, 1.5, lv)
    assert plan["method"] == "support"
    assert plan["stop"] < plan["support_zone"]["low"]
    assert plan["entry_low"] <= 96.0
    assert plan["target"] is not None and plan["target"] < 110.5


def test_bonus_issue_does_not_create_fake_resistance():
    """%100 bedelsiz: ham seri 200'den 100'e duser; duzeltilmis olcekte
    200 civari pivotlar 100'e iner, sahte 200 direnci olusmaz."""
    rows = []
    for i in range(60):
        p = 200.0 + (i % 6)
        rows.append(_bar(i, p - 1, p + 1, p, adj=p / 2))
    for i in range(60, 120):
        p = 100.0 + (i % 6) / 2
        rows.append(_bar(i, p - 0.5, p + 0.5, p))
    lv = find_levels(rows, atr=1.0)
    assert all(z["mid"] < 110.0 for z in lv["resistances"])


def test_volume_profile_conserves_volume():
    bars = [{"high": 10.0 + i % 3, "low": 9.0 + i % 3, "close": 9.5, "volume": 100.0} for i in range(30)]
    _, vol = volume_profile(bars, bins=10)
    assert abs(sum(vol) - 3000.0) < 1e-6


def test_breakout_requires_volume_confirmation():
    rows = _range_market(n=120)
    for i in range(4):
        rows.append(_bar(200 + i, 111.0 + i, 112.5 + i, 112.0 + i, vr=1.0))
    lv = find_levels(rows, atr=1.5)
    assert recent_breakout(rows, lv, 1.5) is None
    rows[-1]["volume_ratio_20d"] = 2.0
    assert recent_breakout(rows, lv, 1.5) is not None


def test_risk_levels_fall_back_when_stop_too_far():
    plan = {"method": "support", "entry_low": 99.0, "entry_high": 100.4, "stop": 80.0}
    res = compute_dynamic_risk_levels(100.0, atr20=2.0, level_plan=plan)
    assert res["entry_method"] == "atr_band"
    assert res["entry_low"] == 99.0


def test_risk_levels_use_support_plan():
    plan = {"method": "support", "entry_low": 97.2, "entry_high": 100.4, "stop": 95.0}
    res = compute_dynamic_risk_levels(100.0, atr20=2.0, level_plan=plan)
    assert res["entry_method"] == "support"
    assert res["entry_low"] == 97.2
    assert res["stop_loss"] == 95.0


def test_short_target_capped_by_resistance():
    plan = {"method": "support", "entry_low": 97.2, "entry_high": 100.4, "stop": 95.0, "target": 103.0}
    res = compute_short_term_target(100.0, atr20=2.0, sma20=99.0, level_plan=plan)
    assert res["target_price"] == 103.0
    assert res["entry_method"] == "support"


def test_mobile_card_shows_levels_without_orphan_numbers():
    from report.render import render_mobile_newsletter
    from report.validate import find_orphan_numbers
    cand = {"ticker": "TEST", "candidate_state": "OPPORTUNITY", "current_price": 100.0,
            "target_price": 112.4, "expected_roi_pct": 12.4, "horizon_days": 180,
            "entry_low": 98.5, "entry_high": 100.4, "stop_loss": 93.2, "position_size_pct": 18.2,
            "nearest_support": 97.3, "nearest_resistance": 106.8, "resistance_before_target": True,
            "sr_levels": {"supports": [97.31], "resistances": [106.77], "vwap20": 99.12, "poc": 96.4}}
    payload = {"passing_candidates": [cand]}
    ctx = {"as_of_date": "2026-09-27", "long_term_candidates": [cand], "short_term_candidates": [],
           "sector_rotation": [], "no_action_today": False}
    html = render_mobile_newsletter(ctx)
    assert "Destek / direnç" in html and "106.80" in html
    assert "Hedef yolunda direnç" in html
    assert find_orphan_numbers(html, payload) == []
