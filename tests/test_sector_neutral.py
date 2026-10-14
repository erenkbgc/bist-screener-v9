"""tests/test_sector_neutral.py: sektor-notr valuation_z (sector_neutralize ile ayni kurallar)."""
from __future__ import annotations

from statistics import mean

import pytest

from core.ranking import compute_valuation_scores, compute_valuation_z


def _make_candidate(ticker, sector, pe=15.0, pb=2.0, sector_super="XUSIN", **kw):
    return {"ticker": ticker, "sector": sector, "supersector": sector_super,
            "ratio_profile": "industrial", "reporting_basis": "nominal", "pe": pe, "pb": pb, **kw}


def test_sector_level_when_sector_has_5_names():
    pool = [_make_candidate(f"T{i}", "XUTEK", pe=12.0 + i, pb=1.0 + 0.2 * i) for i in range(5)]
    pool += [_make_candidate(f"G{i}", "XGIDA", pe=6.0 + i, pb=0.8 + 0.1 * i) for i in range(5)]
    res = compute_valuation_scores(pool)
    assert all(r["peer_group_used"] == "sector" and r["confidence"] == "high" for r in res)
    assert all(r["peer_n"] == 5 for r in res)
    # sektor ortalamasi cikarildigi icin her sektorde ortalama 0
    assert mean(r["valuation_z"] for r in res[:5]) == pytest.approx(0, abs=1e-12)
    assert mean(r["valuation_z"] for r in res[5:]) == pytest.approx(0, abs=1e-12)


def test_small_sector_falls_back_to_market_not_supersector():
    pool = [_make_candidate(f"T{i}", "XUTEK", pe=12.0 + i) for i in range(6)]
    small = [_make_candidate(f"B{i}", "XBLSM", pe=9.0 + i, sector_super="XUTEK") for i in range(3)]
    res = compute_valuation_scores(pool + small)
    for r in res[6:]:
        assert r["peer_group_used"] == "market"
        assert r["confidence"] == "degraded"
        assert r["peer_n"] == 9


def test_insufficient_when_cross_section_under_5():
    cand = _make_candidate("MAIN", "RARE_SEC")
    res = compute_valuation_z(cand, [cand, _make_candidate("OTHER", "RARE_SEC", pe=10.0)])
    assert res["peer_group_used"] == "none"
    assert res["confidence"] == "insufficient_peers"
    assert res["valuation_z"] is None


def test_holding_and_industrial_share_value_sn_pool():
    """Panelde sanayi/holding/GYO tek finansal-disi kesit; canlida da ayni havuz."""
    pool = [_make_candidate(f"T{i}", "XUTEK", pe=12.0 + i) for i in range(4)]
    hold = _make_candidate("HOLD", "XHOLD", pe=7.0)
    hold["ratio_profile"] = "holding"
    res = compute_valuation_z(hold, pool + [hold])
    assert res["peer_group_used"] == "market" and res["peer_n"] == 5


def test_financial_and_illiquid_names_excluded_from_reference():
    liquid = [_make_candidate(f"T{i}", "XUTEK", pe=10.0 + i, tl_vol_med60=1e8 + i) for i in range(10)]

    def run(pe):
        others = [_make_candidate("ILQ", "XUTEK", pe=pe, tl_vol_med60=1.0),
                  _make_candidate("FCT", "Faktoring", pe=pe, tl_vol_med60=1e9)]
        return compute_valuation_scores(liquid + others)

    a, b = run(3.0), run(300.0)
    # likit olmayan ve finansal hissenin degeri istatistige girmez
    assert [r["valuation_z"] for r in a[:10]] == pytest.approx([r["valuation_z"] for r in b[:10]])
    assert a[10]["valuation_z"] > b[10]["valuation_z"]  # yine de skorlanir
