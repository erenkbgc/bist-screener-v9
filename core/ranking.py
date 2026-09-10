"""valuation_engine: kesitsel (cross-sectional) esler grubu ici degerleme skoru.

Spec: valuation_engine, ratio_profiles, sector_taxonomy, known_pitfalls P3/P4/P5.
no_fixed_thresholds ve no_historical_ratio_comparison kurallari: burada HICBIR
sabit F/K, PD/DD, FD/FAVOK esigi veya bir sirketin kendi gecmisiyle karsilastirmasi
YOKTUR. Yalnizca ayni (peer_level, reporting_basis, ratio_profile) grubu icindeki
persentil/z-skor kullanilir.
"""
from __future__ import annotations

from statistics import mean, pstdev

MIN_PEER_N = 8
FALLBACK_CHAIN = ["sector", "supersector", "market"]
CONFIDENCE_MAPPING = {"sector": "high", "supersector": "degraded", "market": "low", "none": "insufficient_peers"}

RATIO_PROFILES = {
    "industrial": {
        "metrics": ["pe", "pb", "ev_ebitda", "ev_sales", "roe", "net_debt_ebitda", "fcf_yield"],
        "direction": {"pe": "lower_better", "pb": "lower_better", "ev_ebitda": "lower_better",
                      "ev_sales": "lower_better", "roe": "higher_better",
                      "net_debt_ebitda": "lower_better", "fcf_yield": "higher_better"},
    },
    "bank": {
        "metrics": ["pe", "pb", "roe", "roa", "nim", "npl_ratio", "car"],
        "direction": {"pe": "lower_better", "pb": "lower_better", "roe": "higher_better",
                      "roa": "higher_better", "nim": "higher_better", "npl_ratio": "lower_better",
                      "car": "higher_better"},
        "forbidden_metrics": ["ev_ebitda", "ev_sales", "net_debt_ebitda"],
    },
    "insurance": {
        "metrics": ["pe", "pb", "roe", "combined_ratio"],
        "direction": {"pe": "lower_better", "pb": "lower_better", "roe": "higher_better",
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


def build_peer_group(candidate: dict, all_candidates: list[dict]) -> tuple[list[dict], str, str]:
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
        if len(peers) >= MIN_PEER_N:
            return peers, level, CONFIDENCE_MAPPING[level]
    # hicbir seviye min_peer_n'e ulasamadi -> en genis seviyeyi (market) dondur ama confidence=insufficient_peers
    return same_basis_profile, "none", CONFIDENCE_MAPPING["none"]


def score_metric_z(candidate_value: float, peer_values: list[float], direction: str) -> float:
    pool = winsorize([v for v in peer_values if v is not None])
    if len(pool) < 2 or candidate_value is None:
        return 0.0
    mu, sigma = mean(pool), pstdev(pool)
    if sigma == 0:
        return 0.0
    z = (candidate_value - mu) / sigma
    return z if direction == "higher_better" else -z


def compute_valuation_z(candidate: dict, all_candidates: list[dict]) -> dict:
    profile = RATIO_PROFILES[candidate["ratio_profile"]]
    peers, peer_level, confidence = build_peer_group(candidate, all_candidates)
    metrics = profile["metrics"]
    z_scores = []
    for metric in metrics:
        peer_values = [p.get(metric) for p in peers if p.get(metric) is not None]
        cand_value = candidate.get(metric)
        if cand_value is None or len(peer_values) < 2:
            continue
        direction = profile["direction"][metric]
        z_scores.append(score_metric_z(cand_value, peer_values, direction))
    valuation_z = mean(z_scores) if z_scores else None
    return {
        "valuation_z": valuation_z,
        "peer_group_used": peer_level,
        "peer_n": len(peers),
        "confidence": confidence,
    }
