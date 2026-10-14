"""min_peer_n geri dusus testi, ratio_profile testi."""
from core import ranking
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


def test_compute_valuation_z_never_uses_forbidden_metrics(monkeypatch):
    """dead_hard_filters_repair (v12 T0-2): forbidden_metrics eskiden dekoratifti --
    hicbir kod bakmiyordu, yalnizca RATIO_PROFILES['bank']['metrics'] zaten
    'ev_ebitda' ICERMEDIGI icin zararsizdi. Bu, savunma hattinin gercekten
    calistigini dogrulamiyor -- bu test, 'metrics' listesine YANLISLIKLA
    yasakli bir metrik eklendigi (gelecekte ev_ebitda_net_debt_recovery
    sonrasi olabilecek bir hata) senaryosunu simule edip valuation_z'nin
    yine de o metrigi KULLANMADIGINI dogruluyor."""
    monkeypatch.setitem(ranking.RATIO_PROFILES, "bank", {
        "metrics": ["ev_ebitda"],  # yanlislikla forbidden bir metrik eklenmis
        "direction": {"ev_ebitda": "lower_better"},
        "forbidden_metrics": ["ev_ebitda", "ev_sales", "net_debt_ebitda"],
    })
    banks = [{"ticker": f"BANK{i}", "sector": "XBANK", "supersector": "XUMAL",
              "ratio_profile": "bank", "reporting_basis": "nominal",
              "ev_ebitda": 5.0 + i} for i in range(10)]
    result = compute_valuation_z(banks[0], banks)
    assert result["valuation_z"] is None  # forbidden metrik filtrelendigi icin skorlanamaz


def test_ratio_profile_only_compares_within_same_profile():
    bank = {"ticker": "BANK1", "sector": "XBANK", "supersector": "XUMAL", "ratio_profile": "bank",
            "reporting_basis": "nominal", "pe": 5, "pb": 0.8, "roe": 20, "roa": 2, "nim": 5,
            "npl_ratio": 3, "car": 15}
    industrials = [_make_candidate(f"I{i}", "XGIDA", "XUSIN") for i in range(10)]
    result = compute_valuation_z(bank, [bank] + industrials)
    # bank'in esler grubu yalnizca kendisi -> insufficient_peers
    assert result["confidence"] == "insufficient_peers"
    assert result["valuation_z"] is None


def test_loss_maker_is_penalized_not_skipped():
    """Zarar eden sirkette F/K None ('A/D') -- eskiden metrik atlaniyor, skor kalan
    metriklerden geliyordu. E/P zarari negatif deger olarak siralamaya sokar."""
    peers = [_make_candidate(f"S{i}", "XGIDA", "XUSIN", pe=8 + i) for i in range(8)]
    for p in peers:
        p["current_price"] = 10.0
    profitable = _make_candidate("WIN", "XGIDA", "XUSIN", pe=10)
    loser = _make_candidate("LOS", "XGIDA", "XUSIN", pe=None)
    profitable["current_price"] = loser["current_price"] = 10.0
    loser["eps_ttm"] = -2.0
    pool = peers + [profitable, loser]
    assert ranking.earnings_yield(loser) == -20.0
    z_win = compute_valuation_z(profitable, pool)["valuation_z"]
    z_los = compute_valuation_z(loser, pool)["valuation_z"]
    assert z_los < z_win


def test_extreme_candidate_not_clipped_to_peer_range_and_nan_ignored():
    """Aday emsal min-max'ina kirpilmaz: daha ucuz hisse daha yuksek z alir."""
    peers = [_make_candidate(f"S{i}", "XGIDA", "XUSIN", pe=8 + i, pb=1 + 0.1 * i) for i in range(10)]
    cheap = _make_candidate("CHP", "XGIDA", "XUSIN", pb=0.5)
    cheaper = _make_candidate("CRS", "XGIDA", "XUSIN", pb=0.25)
    nan_peer = _make_candidate("NAN", "XGIDA", "XUSIN", pb=float("nan"))
    pool = peers + [cheap, cheaper, nan_peer]
    z = ranking.compute_valuation_scores(pool)
    assert z[-2]["valuation_z"] > z[-3]["valuation_z"]
    assert all(r["valuation_z"] == r["valuation_z"] for r in z if r["valuation_z"] is not None)
    assert z[-1]["metrics_used"] == ["ep"]  # pb NaN -> yalnizca E/P


def test_metric_coverage_is_reported():
    pool = [_make_candidate(f"S{i}", "XGIDA", "XUSIN", pe=8 + i, pb=1 + 0.1 * i) for i in range(8)]
    pool[0]["pb"] = None
    res = ranking.compute_valuation_scores(pool)
    assert res[0]["valid_metric_count"] == 1 and res[0]["metrics_used"] == ["ep"]
    assert res[1]["valid_metric_count"] == 2 and res[1]["metrics_used"] == ["ep", "bm"]
    assert "valuation_z_sector_neutral" not in res[1]


def test_value_sn_metrics_match_research_definition():
    """Faz 2: sanayi/holding/GYO canli skoru panel value_sn ile ayni dort oran."""
    from core.ranking import VALUE_SN_METRICS, book_to_market, ebit_yield, sales_yield

    assert VALUE_SN_METRICS == ["ep", "bm", "sp", "ey"]
    for prof in ("industrial", "holding", "reit"):
        assert RATIO_PROFILES[prof]["metrics"] == VALUE_SN_METRICS
        assert set(RATIO_PROFILES[prof]["direction"].values()) == {"higher_better"}
    c = {"pb": 2.0, "revenue_ttm": 500.0, "op_profit_ttm": 60.0, "market_cap": 1000.0, "net_debt": 200.0}
    assert book_to_market(c) == 0.5
    assert sales_yield(c) == 0.5
    assert ebit_yield(c) == 60.0 / 1200.0
    assert book_to_market({"pb": -1.0}) is None
    assert ebit_yield({**c, "net_debt": -1500.0}) is None  # EV <= 0
    assert ebit_yield({**c, "net_debt": None}) is None  # bilinmeyen borc 0 sayilmaz
    assert ebit_yield({**c, "net_debt": 0.0}) == 60.0 / 1000.0
    assert sales_yield({"revenue_ttm": 1.0, "market_cap": None}) is None
