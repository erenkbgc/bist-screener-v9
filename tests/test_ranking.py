"""min_peer_n geri dusus testi, ratio_profile testi."""
from core.ranking import build_peer_group, compute_valuation_z, RATIO_PROFILES, MIN_PEER_N


def _make_candidate(ticker, sector, supersector, ratio_profile="industrial",
                     reporting_basis="adjusted", pe=10, pb=1, ev_ebitda=5, ev_sales=1, roe=15,
                     net_debt_ebitda=1, fcf_yield=0.05):
    return {"ticker": ticker, "sector": sector, "supersector": supersector, "ratio_profile": ratio_profile,
            "reporting_basis": reporting_basis, "pe": pe, "pb": pb, "ev_ebitda": ev_ebitda,
            "ev_sales": ev_sales, "roe": roe, "net_debt_ebitda": net_debt_ebitda, "fcf_yield": fcf_yield}


def test_min_peer_n_fallback_to_supersector():
    """Sektorde min_peer_n'den az sirket varsa supersector'e, sonra market'e geri duser."""
    candidate = _make_candidate("A", "XGIDA", "XUSIN")
    # sektorde yalnizca 3 sirket (min_peer_n=8'den az), supersector'de 10
    same_sector = [_make_candidate(f"S{i}", "XGIDA", "XUSIN") for i in range(2)]
    same_supersector = [_make_candidate(f"P{i}", "XTEKS", "XUSIN") for i in range(10)]
    pool = [candidate] + same_sector + same_supersector

    peers, level, confidence = build_peer_group(candidate, pool)
    assert level == "supersector"
    assert confidence == "degraded"
    assert len(peers) >= MIN_PEER_N


def test_min_peer_n_fallback_to_market_when_insufficient():
    candidate = _make_candidate("A", "XGIDA", "XUSIN")
    pool = [candidate] + [_make_candidate(f"S{i}", "XGIDA", "XUSIN") for i in range(2)]
    peers, level, confidence = build_peer_group(candidate, pool)
    assert level == "none"
    assert confidence == "insufficient_peers"


def test_sector_level_used_when_enough_peers():
    candidate = _make_candidate("A", "XGIDA", "XUSIN")
    pool = [candidate] + [_make_candidate(f"S{i}", "XGIDA", "XUSIN") for i in range(10)]
    peers, level, confidence = build_peer_group(candidate, pool)
    assert level == "sector"
    assert confidence == "high"


def test_ratio_profile_bank_excludes_ev_metrics():
    assert "ev_ebitda" not in RATIO_PROFILES["bank"]["metrics"]
    assert "ev_ebitda" in RATIO_PROFILES["bank"].get("forbidden_metrics", [])


def test_ratio_profile_only_compares_within_same_profile():
    bank = {"ticker": "BANK1", "sector": "XBANK", "supersector": "XUMAL", "ratio_profile": "bank",
            "reporting_basis": "nominal", "pe": 5, "pb": 0.8, "roe": 20, "roa": 2, "nim": 5,
            "npl_ratio": 3, "car": 15}
    industrials = [_make_candidate(f"I{i}", "XGIDA", "XUSIN") for i in range(10)]
    result = compute_valuation_z(bank, [bank] + industrials)
    # bank'in esler grubu yalnizca kendisi -> insufficient_peers
    assert result["confidence"] == "insufficient_peers"
