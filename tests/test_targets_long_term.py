"""compute_long_term_target testi: hicbir zaman test edilmemisti (bkz.
long_term_target_price_outlier_cap). RATIO_PROFILES'in forbidden_metrics
kuralinin (ev_ebitda finansal kurulus/GYO icin anlamsiz) target_price
hesabinda da uygulandigini dogrular -- kok neden: 2026-09-15 kosusunda GLRYH/
A1CAP/IHLGM sector='BILINMIYOR' -> 'industrial'e dusup EV/EBITDA ile
alakasiz sanayi emsallerine karsi degerlenmisti (fintables entegrasyonu artik
dogru profili veriyor); reit ise profili dogru olsa bile targets.py ayri ele
almadigi icin ayni hataya devam ederdi -- bu dosya o bosluk icin eklendi."""
from core.targets import compute_long_term_target


def _peer(ticker, ratio_profile, pe=10.0, ev_ebitda=8.0, eps_ttm=5.0,
          ebitda_ttm=1000.0, net_debt=0.0, shares_outstanding=100.0,
          reporting_basis="adjusted", sector="S1", supersector="XUSIN"):
    return {"ticker": ticker, "ratio_profile": ratio_profile, "pe": pe, "ev_ebitda": ev_ebitda,
            "eps_ttm": eps_ttm, "ebitda_ttm": ebitda_ttm, "net_debt": net_debt,
            "shares_outstanding": shares_outstanding, "reporting_basis": reporting_basis,
            "sector": sector, "supersector": supersector, "market_cap": 1000.0,
            "entry_price": 100.0, "nav_discount": None}


def _peers(n, ratio_profile, **kw):
    return [_peer(f"P{i}", ratio_profile, **kw) for i in range(n)]


def test_reit_target_ignores_ev_ebitda_peer_multiple():
    """Bir peer'in ev_ebitda'si asiri (ornegin GYO'da amortisman/yeniden degerleme
    carpitmasi) olsa bile REIT hedef fiyati bunu KULLANMAMALI -- yalnizca PE bacagi."""
    peers = _peers(9, "reit", ev_ebitda=500.0)  # asiri EV/EBITDA -- kullanilirsa hedefi sisirir
    candidate = _peer("IHLGM", "reit", eps_ttm=5.0, ebitda_ttm=1_000_000.0, net_debt=0.0,
                       shares_outstanding=10.0)
    result = compute_long_term_target(candidate, peers + [candidate])
    # legs_used==1 -> yalnizca PE bacagi kullanildi, EV/EBITDA bacagi (leg2) YOK
    assert result["legs_used"] == 1
    assert result["target_price"] == 10.0 * 5.0  # peer PE medyani (10.0) * eps_ttm


def test_bank_and_insurance_target_ignores_ev_ebitda_peer_multiple():
    for profile in ("bank", "insurance"):
        peers = _peers(9, profile, ev_ebitda=500.0)
        candidate = _peer("BANK1", profile, eps_ttm=3.0)
        result = compute_long_term_target(candidate, peers + [candidate])
        assert result["legs_used"] == 1
        assert result["target_price"] == 10.0 * 3.0


def test_industrial_target_uses_both_pe_and_ev_ebitda_legs():
    peers = _peers(9, "industrial")
    candidate = _peer("IND1", "industrial", eps_ttm=4.0, ebitda_ttm=200.0,
                       net_debt=50.0, shares_outstanding=20.0)
    result = compute_long_term_target(candidate, peers + [candidate])
    assert result["legs_used"] == 2
    leg1 = 10.0 * 4.0
    leg2 = (8.0 * 200.0 - 50.0) / 20.0
    assert abs(result["target_price"] - (leg1 + leg2) / 2) < 1e-9


def test_holding_without_nav_discount_data_produces_no_target():
    peers = _peers(9, "holding")
    for p in peers:
        p["nav_discount"] = None
    candidate = _peer("HOLD1", "holding")
    candidate["nav_discount"] = None
    result = compute_long_term_target(candidate, peers + [candidate])
    assert result["legs_used"] == 0
    assert result["target_price"] is None
