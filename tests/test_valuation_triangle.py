"""tests/test_valuation_triangle.py: Coklu Degerleme Metodolojisi (Degerleme Ucgeni) testleri.

Spec (v13 roadmap P0-3):
- DCF (%40): WACC, terminal buyume (g) config'den.
- Emsal Carpanlar (%35): F/K, FD/FAVOK, PD/DD, GYO/Holding icin NAV iskontosu.
- Kalite Primi (%25): Piotroski F-Score, ROE vs Sermaye Maliyeti, Dusuk Borc/Net Nakit.
- GYO icin NAV (Net Aktif Degeri): Portfoy degeri - net borc / pay sayisi.
- Cikti: fair_value_low, fair_value_base, fair_value_high, valuation_method.
- Hedef fiyat = agirlikli ortalama fair value.
"""
import pytest
from core.valuation_triangle import (
    compute_dcf_leg,
    compute_peers_leg,
    compute_quality_leg,
    compute_reit_nav,
    compute_valuation_triangle,
)
from core.targets import compute_long_term_target


def test_dcf_leg_positive_fcf_and_wacc():
    candidate = {
        "ticker": "TEST1",
        "fcf_ttm": 100_000_000.0,
        "shares_outstanding": 10_000_000.0,
        "market_cap": 500_000_000.0,
        "beta_60_120d": 1.1,
        "net_debt": 50_000_000.0,
        "financial_expenses_ttm": 10_000_000.0,
    }
    macro = {"bond_2y_pct": 45.0}
    dcf = compute_dcf_leg(candidate, macro)

    assert dcf is not None
    assert dcf["eligible"] is True
    assert dcf["fcf_per_share"] == 10.0
    assert dcf["fair_value_low"] > 0
    assert dcf["fair_value_base"] >= dcf["fair_value_low"]
    assert dcf["fair_value_high"] >= dcf["fair_value_base"]


def test_dcf_leg_negative_or_missing_fcf_returns_none():
    macro = {"bond_2y_pct": 45.0}
    # Negatif FCF
    cand_neg = {"ticker": "NEG", "fcf_ttm": -50_000.0, "shares_outstanding": 1000.0, "market_cap": 10000.0}
    assert compute_dcf_leg(cand_neg, macro) is None

    # Missing shares
    cand_no_sh = {"ticker": "NOSH", "fcf_ttm": 50_000.0, "shares_outstanding": None, "market_cap": 10000.0}
    assert compute_dcf_leg(cand_no_sh, macro) is None


def test_peers_leg_industrial_all_multiples():
    peers = [
        {"ticker": "P1", "pe": 10.0, "pb": 2.0, "ev_ebitda": 8.0, "nav_discount": None},
        {"ticker": "P2", "pe": 12.0, "pb": 2.4, "ev_ebitda": 10.0, "nav_discount": None},
    ]
    candidate = {
        "ticker": "IND1",
        "ratio_profile": "industrial",
        "entry_price": 50.0,
        "current_price": 50.0,
        "eps_ttm": 5.0,
        "ebitda_ttm": 200_000_000.0,
        "net_debt": 100_000_000.0,
        "shares_outstanding": 10_000_000.0,
        "pb": 2.0,
    }
    leg = compute_peers_leg(candidate, peers)
    assert leg is not None
    assert leg["eligible"] is True
    # PE, EV/EBITDA, PB kullanilmali
    assert leg["legs_used"] == 3
    assert "pe" in leg["legs_detail"]
    assert "ev_ebitda" in leg["legs_detail"]
    assert "pb" in leg["legs_detail"]
    assert leg["fair_value_low"] <= leg["fair_value_base"] <= leg["fair_value_high"]


def test_peers_leg_reit_omits_ev_ebitda_and_uses_nav():
    peers = [
        {"ticker": "R1", "pe": 8.0, "pb": 0.5, "ev_ebitda": 500.0, "nav_discount": 0.40},
        {"ticker": "R2", "pe": 10.0, "pb": 0.7, "ev_ebitda": 400.0, "nav_discount": 0.50},
    ]
    candidate = {
        "ticker": "REIT1",
        "ratio_profile": "reit",
        "entry_price": 20.0,
        "current_price": 20.0,
        "eps_ttm": 2.5,
        "pb": 0.6,
        "_nav_per_share": 40.0,
        "shares_outstanding": 1_000_000.0,
    }
    leg = compute_peers_leg(candidate, peers)
    assert leg is not None
    # EV/EBITDA yasakli oldugu icin legs_detail icinde OLMAMALI
    assert "ev_ebitda" not in leg["legs_detail"]
    assert "pe" in leg["legs_detail"]
    assert "reit_nav" in leg["legs_detail"]
    # Peer median nav_discount = 0.45 -> reit_nav = 40.0 * (1 - 0.45) = 22.0
    assert abs(leg["legs_detail"]["reit_nav"] - 22.0) < 1e-6


def test_peers_leg_holding_without_nav_produces_no_leg():
    peers = [
        {"ticker": "H1", "pe": 8.0, "pb": 1.2, "nav_discount": None},
    ]
    candidate = {
        "ticker": "HOLD1",
        "ratio_profile": "holding",
        "entry_price": 100.0,
        "eps_ttm": 15.0,
        "pb": 1.1,
    }
    leg = compute_peers_leg(candidate, peers)
    assert leg is None


def test_quality_leg_economic_rent_and_modifiers():
    # Yuksek ROE (%80 vs %50 sermaye maliyeti), yuksek Piotroski (normalize 0.88), net nakit (-50M)
    cand_high = {
        "ticker": "HIGH_Q",
        "current_price": 100.0,
        "entry_price": 100.0,
        "roe": 80.0,
        "pb": 2.0,
        "piotroski_normalized_score": 0.88,
        "net_debt": -50_000_000.0,
    }
    macro = {"bond_2y_pct": 45.0}
    q_high = compute_quality_leg(cand_high, macro)
    assert q_high is not None
    assert q_high["eligible"] is True
    # Piotroski (+0.10) + Net Nakit (+0.10) + Yuksek ROE (+0.05) -> multiplier = 1.25
    assert abs(q_high["quality_multiplier"] - 1.25) < 1e-6
    assert q_high["fair_value_base"] > 0

    # Eksik ROE -> None
    cand_no_roe = dict(cand_high)
    cand_no_roe["roe"] = None
    assert compute_quality_leg(cand_no_roe, macro) is None


def test_reit_nav_calculation():
    cand = {
        "_portfolio_value": 500_000_000.0,
        "net_debt": 100_000_000.0,
        "shares_outstanding": 10_000_000.0,
        "market_cap": 250_000_000.0,
    }
    nav_res = compute_reit_nav(cand)
    # NAV = 500M - 100M = 400M
    assert nav_res["nav"] == 400_000_000.0
    # nav_per_share = 400M / 10M = 40.0
    assert nav_res["nav_per_share"] == 40.0
    # nav_discount = (400M - 250M) / 400M = 37.5% (0.375)
    assert abs(nav_res["nav_discount"] - 0.375) < 1e-6


def test_valuation_triangle_synthesis_all_three_legs():
    peers = [
        {"ticker": "P1", "pe": 10.0, "pb": 2.0, "ev_ebitda": 8.0, "nav_discount": None},
        {"ticker": "P2", "pe": 12.0, "pb": 2.2, "ev_ebitda": 8.5, "nav_discount": None},
    ]
    candidate = {
        "ticker": "ALL3",
        "ratio_profile": "industrial",
        "current_price": 50.0,
        "entry_price": 50.0,
        "eps_ttm": 5.0,
        "ebitda_ttm": 100_000_000.0,
        "net_debt": -20_000_000.0,  # net cash
        "shares_outstanding": 10_000_000.0,
        "market_cap": 500_000_000.0,
        "fcf_ttm": 80_000_000.0,
        "roe": 50.0,
        "pb": 2.0,
        "piotroski_normalized_score": 0.77,
        "beta_60_120d": 1.0,
    }
    macro = {"bond_2y_pct": 45.0}

    vt = compute_valuation_triangle(candidate, peers, macro)
    assert vt["target_price"] is not None
    assert vt["fair_value_low"] <= vt["fair_value_base"] <= vt["fair_value_high"]
    assert vt["weights_used"]["dcf"] == 0.40
    assert vt["weights_used"]["peers"] == 0.35
    assert vt["weights_used"]["quality"] == 0.25
    assert "Değerleme Üçgeni" in vt["valuation_method"]
    assert "DCF" in vt["valuation_method"]
    assert "Emsal" in vt["valuation_method"]
    assert "Kalite" in vt["valuation_method"]


def test_valuation_triangle_renormalizes_weights_when_dcf_missing():
    peers = [
        {"ticker": "P1", "pe": 10.0, "pb": 2.0, "ev_ebitda": 8.0, "nav_discount": None},
    ]
    candidate = {
        "ticker": "NO_DCF",
        "ratio_profile": "industrial",
        "current_price": 50.0,
        "entry_price": 50.0,
        "eps_ttm": 5.0,
        "shares_outstanding": 10_000_000.0,
        "market_cap": 500_000_000.0,
        "fcf_ttm": -10_000.0,  # Negatif FCF -> DCF None
        "roe": 45.0,
        "pb": 2.0,
    }
    macro = {"bond_2y_pct": 45.0}

    vt = compute_valuation_triangle(candidate, peers, macro)
    assert vt["target_price"] is not None
    assert "dcf" not in vt["weights_used"]
    # 0.35 / (0.35 + 0.25) = 0.5833
    assert abs(vt["weights_used"]["peers"] - 0.5833) < 1e-3
    # 0.25 / (0.35 + 0.25) = 0.4167
    assert abs(vt["weights_used"]["quality"] - 0.4167) < 1e-3


def test_compute_long_term_target_integration():
    peers = [
        {"ticker": "P1", "ratio_profile": "industrial", "sector": "S", "supersector": "X",
         "pe": 10.0, "pb": 2.0, "ev_ebitda": 8.0, "market_cap": 500.0, "reporting_basis": "nominal"},
    ]
    candidate = {
        "ticker": "INTG",
        "ratio_profile": "industrial",
        "sector": "S",
        "supersector": "X",
        "reporting_basis": "nominal",
        "current_price": 50.0,
        "entry_price": 50.0,
        "eps_ttm": 5.0,
        "market_cap": 500.0,
        "shares_outstanding": 10.0,
    }
    res = compute_long_term_target(candidate, peers + [candidate])
    assert res["target_price"] is not None
    assert res["fair_value_low"] is not None
    assert res["fair_value_base"] is not None
    assert res["fair_value_high"] is not None
    assert "valuation_method" in res
    assert res["horizon_days"] == 180


def test_peers_leg_filters_out_extreme_multiple_outlier():
    """Emsal carpanlarda bir carpan (orn. bozuk EBITDA veya net borc nedeniyle)
    mevcut fiyatin 3.5 katindan fazla adil deger uretirse, ortalamayi bozmamasi icin
    bilesen bazinda filtrelenir."""
    peers = [
        {"ticker": "P1", "pe": 10.0, "pb": 2.0, "ev_ebitda": 20.0, "nav_discount": None},
    ]
    candidate = {
        "ticker": "OUTL_PEER",
        "ratio_profile": "industrial",
        "entry_price": 50.0,
        "current_price": 50.0,
        "eps_ttm": 5.0,  # PE leg = 10 * 5 = 50.0 (1.0x price)
        "pb": 2.0,       # PB leg = 50.0 (1.0x price)
        "ebitda_ttm": 1_000_000_000.0,
        "net_debt": 0.0,
        "shares_outstanding": 1_000_000.0,  # EV/EBITDA leg = 20 * 1B / 1M = 20,000 TL (400x price!)
    }
    leg = compute_peers_leg(candidate, peers)
    assert leg is not None
    # 20,000 TL'lik EV/EBITDA elenmeli, yalnizca PE ve PB kalmali
    assert "ev_ebitda" not in leg["legs_detail"]
    assert "pe" in leg["legs_detail"]
    assert "pb" in leg["legs_detail"]
    assert leg["legs_used"] == 2
    assert abs(leg["fair_value_base"] - 50.0) < 1.0


def test_valuation_triangle_rejects_synthesized_extreme_target():
    """Eger sentetik hedef fiyat tum bilesenler sonucunda mevcut fiyatin
    2.5 katini asarsa (+%150 prim), sentetik sonuc None doner."""
    candidate = {
        "ticker": "EXTREME",
        "ratio_profile": "industrial",
        "entry_price": 10.0,
        "current_price": 10.0,
        "eps_ttm": 50.0,  # Peer median PE 10 ile 500 TL uretir (> 2.5x price)
        "roe": 100.0,
        "pb": 0.1,
    }
    peers = [{"ticker": "P1", "pe": 10.0, "pb": 5.0, "ev_ebitda": 10.0}]
    vt = compute_valuation_triangle(candidate, peers)
    assert vt["target_price"] is None
    assert vt["valuation_method"] == "none"
