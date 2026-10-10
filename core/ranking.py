"""valuation_engine: kesitsel (cross-sectional) esler grubu ici degerleme skoru.

Spec: valuation_engine, ratio_profiles, sector_taxonomy, known_pitfalls P3/P4/P5.
no_fixed_thresholds ve no_historical_ratio_comparison kurallari: burada HICBIR
sabit F/K, PD/DD, FD/FAVOK esigi veya bir sirketin kendi gecmisiyle karsilastirmasi
YOKTUR. Yalnizca ayni (peer_level, reporting_basis, ratio_profile) grubu icindeki
persentil/z-skor kullanilir.
"""
from __future__ import annotations

import math
from statistics import mean, pstdev

MIN_PEER_N = 5  # v13 P1-7: peer_n < 5 ise supersector'e dusulur; kucuk sektorler (sigorta vb.) gereksiz elenmez
FALLBACK_CHAIN = ["sector", "supersector", "market"]
CONFIDENCE_MAPPING = {"sector": "high", "supersector": "degraded", "market": "low", "none": "insufficient_peers"}

RATIO_PROFILES = {
    "industrial": {
        "metrics": ["ep", "pb", "ev_ebitda", "ev_sales", "roe", "net_debt_ebitda", "fcf_yield"],
        "direction": {"ep": "higher_better", "pb": "lower_better", "ev_ebitda": "lower_better",
                      "ev_sales": "lower_better", "roe": "higher_better",
                      "net_debt_ebitda": "lower_better", "fcf_yield": "higher_better"},
    },
    "bank": {
        "metrics": ["ep", "pb", "roe", "roa", "nim", "npl_ratio", "car"],
        "direction": {"ep": "higher_better", "pb": "lower_better", "roe": "higher_better",
                      "roa": "higher_better", "nim": "higher_better", "npl_ratio": "lower_better",
                      "car": "higher_better"},
        "forbidden_metrics": ["ev_ebitda", "ev_sales", "net_debt_ebitda"],
    },
    "insurance": {
        "metrics": ["ep", "pb", "roe", "combined_ratio"],
        "direction": {"ep": "higher_better", "pb": "lower_better", "roe": "higher_better",
                      "combined_ratio": "lower_better"},
        "forbidden_metrics": ["ev_ebitda", "ev_sales"],
    },
    "holding": {
        "metrics": ["nav_discount", "pb", "roe"],
        "direction": {"nav_discount": "higher_better", "pb": "lower_better", "roe": "higher_better"},
        "note": "NAV hesaplanamiyorsa skorlanmaz.",
    },
    "reit": {
        "metrics": ["pb", "nav_discount", "ffo_yield"],
        "direction": {"pb": "lower_better", "nav_discount": "higher_better", "ffo_yield": "higher_better"},
        "forbidden_metrics": ["ev_ebitda"],
    },
}


def earnings_yield(c: dict) -> float | None:
    """E/P (%). F/K yerine kullanilir: zarar eden sirkette F/K anlamsizdir ("A/D",
    None) ve eskiden metrik SESSIZCE atlaniyordu -- zarar cezalandirilmiyor, skor
    kalan (cogu zaman PD/DD, FD/Satis) metriklerden geliyordu. E/P zarari negatif
    deger olarak siralamaya sokar (Fama-French ve literatur standardi)."""
    pe = c.get("pe")
    if pe is not None and _finite(pe) and pe > 0:
        return 100.0 / pe
    eps = c.get("eps_ttm")
    price = c.get("current_price")
    if price is None and c.get("market_cap") and c.get("shares_outstanding"):
        price = c["market_cap"] / c["shares_outstanding"]
    if eps is not None and _finite(eps) and eps < 0 and price and price > 0:
        return eps / price * 100.0
    return None


def _finite(x) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _metric_value(c: dict, metric: str) -> float | None:
    v = earnings_yield(c) if metric == "ep" else c.get(metric)
    return v if v is not None and _finite(v) else None


def winsorize(values: list[float], low_pct: float = 1, high_pct: float = 99) -> list[float]:
    if len(values) < 3:
        return values[:]
    s = sorted(values)

    def pct(p):
        k = (len(s) - 1) * (p / 100)
        f, c = int(k), min(int(k) + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    lo, hi = pct(low_pct), pct(high_pct)
    return [min(max(v, lo), hi) for v in values]


def percentile_rank(value: float, population: list[float]) -> float:
    """0..1 arasi persentil (value populasyonun kacinci sirasinda)."""
    if not population:
        return 0.5
    below = sum(1 for v in population if v < value)
    equal = sum(1 for v in population if v == value)
    return (below + 0.5 * equal) / len(population)


def _group_candidates(candidates: list[dict], level: str) -> dict[tuple, list[dict]]:
    groups: dict[tuple, list[dict]] = {}
    for c in candidates:
        key_field = "sector" if level == "sector" else ("supersector" if level == "supersector" else None)
        peer_key = c[key_field] if key_field else "MARKET"
        key = (peer_key, c["reporting_basis"], c["ratio_profile"])
        groups.setdefault(key, []).append(c)
    return groups


def build_peer_group(
    candidate: dict,
    all_candidates: list[dict],
    min_peer_n: int = MIN_PEER_N,
) -> tuple[list[dict], str, str]:
    """min_peer_n'e ulasana kadar sector -> supersector -> market'e geri duser.

    Ayni reporting_basis ve ratio_profile icindeki sirketlerle sinirlidir (P1, P5).
    """
    same_basis_profile = [c for c in all_candidates
                           if c["reporting_basis"] == candidate["reporting_basis"]
                           and c["ratio_profile"] == candidate["ratio_profile"]]
    for level in FALLBACK_CHAIN:
        if level == "sector":
            peers = [c for c in same_basis_profile if c["sector"] == candidate["sector"]]
        elif level == "supersector":
            peers = [c for c in same_basis_profile if c["supersector"] == candidate["supersector"]]
        else:
            peers = same_basis_profile
        if len(peers) >= min_peer_n:
            return peers, level, CONFIDENCE_MAPPING[level]
    # hicbir seviye min_peer_n'e ulasamadi -> en genis seviyeyi (market) dondur ama confidence=insufficient_peers
    return same_basis_profile, "none", CONFIDENCE_MAPPING["none"]


Z_CLIP = 3.0


def score_metric_z(candidate_value: float, peer_values: list[float], direction: str) -> float:
    clean = [v for v in peer_values if v is not None and _finite(v)]
    pool = winsorize(clean)
    if len(pool) < 2 or candidate_value is None or not _finite(candidate_value):
        return 0.0
    mu, sigma = mean(pool), pstdev(pool)
    if sigma == 0:
        return 0.0
    # Adayin kendi degeri de esler havuzunun ayni sinirlarina kirpilir; aksi halde
    # tek bir uc deger (cokmus fiyat -> asiri dusuk PD/DD) z'yi sinirsiz buyutup
    # valuation_z ortalamasini domine ediyordu.
    lo, hi = min(pool), max(pool)
    z = (min(max(candidate_value, lo), hi) - mu) / sigma
    z = max(-Z_CLIP, min(Z_CLIP, z))
    return z if direction == "higher_better" else -z


def compute_valuation_z(
    candidate: dict,
    all_candidates: list[dict],
    min_peer_n: int = MIN_PEER_N,
) -> dict:
    profile = RATIO_PROFILES[candidate["ratio_profile"]]
    peers, peer_level, confidence = build_peer_group(candidate, all_candidates, min_peer_n)
    # dead_hard_filters_repair (v12 T0-2): forbidden_metrics su ana kadar
    # yalnizca DEKORATIF bir alandi -- hicbir kod bakmiyordu, zararsizdi cunku
    # ev_ebitda/ev_sales zaten kalici None'di (bkz. ev_ebitda_net_debt_recovery).
    # O madde bu alanlari canlandirdiginda profile['metrics'] listesine yanlislikla
    # bir yasakli metrik eklenirse (orn. bank/insurance/reit'e ev_ebitda sizarsa)
    # SAVUNMA HATTI olarak burada acikca filtreleniyor.
    forbidden = set(profile.get("forbidden_metrics", []))
    metrics = [m for m in profile["metrics"] if m not in forbidden]
    z_scores = []
    for metric in metrics:
        peer_values = [v for v in (_metric_value(p, metric) for p in peers) if v is not None]
        cand_value = _metric_value(candidate, metric)
        if cand_value is None or len(peer_values) < 2:
            continue
        direction = profile["direction"][metric]
        z_scores.append(score_metric_z(cand_value, peer_values, direction))
    valuation_z = mean(z_scores) if z_scores else None
    return {
        "valuation_z": valuation_z,
        "valuation_z_sector_neutral": valuation_z,
        "peer_group_used": peer_level,
        "peer_n": len(peers),
        "confidence": confidence,
    }


def compute_sector_neutral_valuation(
    candidate: dict,
    all_candidates: list[dict],
    min_peer_n: int = MIN_PEER_N,
) -> dict:
    """Sektor ici normalizasyon (sektor-notr degerleme z-skoru).

    v13 Roadmap P1-7:
    - Z-skoru oncelikle sektor ici hesaplanir.
    - Sektordeki peer_n < 5 ise supersector'e (XUMAL, XUSIN, XUHIZ, XUTEK) duser.
    - Supersector de < 5 ise market geneline duser.
    Cikti: valuation_z_sector_neutral.
    """
    return compute_valuation_z(candidate, all_candidates, min_peer_n)

