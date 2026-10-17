"""valuation_engine: kesitsel (cross-sectional) esler grubu ici degerleme skoru.

Spec: valuation_engine, ratio_profiles, sector_taxonomy, known_pitfalls P3/P4/P5.
no_fixed_thresholds ve no_historical_ratio_comparison kurallari: burada HICBIR
sabit F/K, PD/DD, FD/FAVOK esigi veya bir sirketin kendi gecmisiyle karsilastirmasi
YOKTUR. valuation_z, ayni reporting_basis ve oran seti icindeki kesitsel z-skorun
sektor ortalamasindan farkidir (test edilen value_sn; bkz. compute_valuation_scores).
"""
from __future__ import annotations

import math
from statistics import mean, stdev

from core.pit_panel import FINANCIAL_SECTORS

MIN_PEER_N = 5  # v13 P1-7: peer_n < 5 ise supersector'e dusulur; kucuk sektorler (sigorta vb.) gereksiz elenmez
# build_peer_group (core/targets.py hedef fiyat emsalleri) icin; valuation_z artik
# bu zinciri kullanmaz (bkz. compute_valuation_scores).
FALLBACK_CHAIN = ["sector", "supersector", "market"]
CONFIDENCE_MAPPING = {"sector": "high", "supersector": "degraded", "market": "low", "none": "insufficient_peers"}

# Sanayi/holding/GYO: test edilen value_sn ile ayni dort oran (Faz 2 on-kaydi,
# docs/research/long_term_preregistration.md; panel 2013-2026, deger ust dilimi
# net aktif +10.65%/yil kesif, +6.96%/yil holdout). Onceki karisim (PD/DD,
# FD/FAVOK, FD/Satis, ROE, net borc/FAVOK, FCF verimi, NAV iskontosu) hic test
# edilmemisti. Hepsi "verim" yonunde: buyuk = ucuz.
VALUE_SN_METRICS = ["ep", "bm", "sp", "ey"]
_VALUE_SN_PROFILE = {
    "metrics": VALUE_SN_METRICS,
    "direction": {m: "higher_better" for m in VALUE_SN_METRICS},
}

RATIO_PROFILES = {
    "industrial": dict(_VALUE_SN_PROFILE),
    # Banka/sigorta: panel finansallari kapsamadi; bu profiller TEST EDILMEDI.
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
    # Holding ve GYO panelde finansal-disi evrendeydi (pit_panel.FINANCIAL_SECTORS
    # yalnizca banka/sigorta/araci kurum/MKYO vb.); ayni value_sn tanimi gecerli.
    "holding": dict(_VALUE_SN_PROFILE),
    "reit": dict(_VALUE_SN_PROFILE),
}


def earnings_yield(c: dict) -> float | None:
    """E/P (%). F/K yerine kullanilir: zarar eden sirkette F/K anlamsizdir ("A/D",
    None) ve eskiden metrik SESSIZCE atlaniyordu -- zarar cezalandirilmiyor, skor
    kalan (cogu zaman PD/DD, FD/Satis) metriklerden geliyordu. E/P zarari negatif
    deger olarak siralamaya sokar (Fama-French ve literatur standardi).

    F/K saglayicidan gelmezse (karli sirkette de bos donebiliyor) EPS / fiyat
    kullanilir; panel E/P'yi her hisse icin net kar / piyasa degeri olarak hesaplar.
    Eskiden geri donus yalniz zararda vardi: 2026-10-16 kosusunda karli 52 hissede
    E/P eksikti (docs/research/ratio_coverage_diagnostics.md)."""
    pe = c.get("pe")
    if pe is not None and _finite(pe) and pe > 0:
        return 100.0 / pe
    eps = c.get("eps_ttm")
    price = c.get("current_price")
    if price is None and c.get("market_cap") and c.get("shares_outstanding"):
        price = c["market_cap"] / c["shares_outstanding"]
    if eps is not None and _finite(eps) and price and price > 0:
        return eps / price * 100.0
    return None


def _finite(x) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def book_to_market(c: dict) -> float | None:
    """B/M = 1 / (PD/DD). Negatif ozsermaye panelde NaN'dir (pit_panel: eq > 0 sarti)."""
    pb = c.get("pb")
    return 1.0 / pb if pb is not None and _finite(pb) and pb > 0 else None


def sales_yield(c: dict) -> float | None:
    """S/P = satislar / piyasa degeri (pit_panel 'sp')."""
    rev, mcap = c.get("revenue_ttm"), c.get("market_cap")
    if rev is None or not _finite(rev) or not mcap or mcap <= 0:
        return None
    return rev / mcap


def ebit_yield(c: dict) -> float | None:
    """EBIT/EV = faaliyet kari / (piyasa degeri + net borc) (pit_panel 'ey'). EV <= 0 ise None.

    Net borc bilinmiyorsa None: eksik veri 0 borc sayilirsa EV piyasa degerine
    esitlenir ve borclu sirketin EBIT/EV'si sisar. Gercekten borcsuz sirket
    net_debt'i 0 (veya negatif, net nakit) olarak tasir."""
    op, mcap, nd = c.get("op_profit_ttm"), c.get("market_cap"), c.get("net_debt")
    if op is None or not _finite(op) or not mcap or mcap <= 0 or nd is None or not _finite(nd):
        return None
    ev = mcap + nd
    return op / ev if ev > 0 else None


_DERIVED = {"ep": earnings_yield, "bm": book_to_market, "sp": sales_yield, "ey": ebit_yield}


def _metric_value(c: dict, metric: str) -> float | None:
    fn = _DERIVED.get(metric)
    v = fn(c) if fn else c.get(metric)
    return v if v is not None and _finite(v) else None


def value_sn_ratios(c: dict) -> dict[str, float | None]:
    """value_sn'in dort ham orani (E/P, B/M, S/P, EBIT/EV); hesaplanamayan None."""
    return {m: _metric_value(c, m) for m in VALUE_SN_METRICS}


def _quantile(sorted_vals: list[float], q: float) -> float:
    """pandas Series.quantile (lineer interpolasyon) ile ayni."""
    k = (len(sorted_vals) - 1) * q
    f, c = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


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




# --- valuation_z: test edilen value_sn ile ayni hesap -------------------------
# Referans: scripts/backtest_factor_model.py::add_composites + core/factor_backtest
# (prepare, winsorize_z, sector_neutralize). Canli skor eskiden farkli bir formuldu
# (emsal grubu ici z, adayin emsal min-max'ina kirpilmasi, +-3 siniri, supersector
# kademesi); Faz 2 sonucu (docs/research/long_term_preregistration.md) o formule ait
# degildi. tests/test_valuation_parity.py iki hesabin ayni sonucu verdigini dogrular.
WINSOR_LO, WINSOR_HI = 0.01, 0.99   # factor_backtest.winsorize_z
MIN_METRIC_N = 3                     # winsorize_z: < 3 gecerli deger -> NaN
MIN_SECTOR_N = 5                     # factor_backtest.sector_neutralize(min_n=5)
LIQ_DROP_PCT = 0.30                  # factor_backtest.prepare(liq_drop_pct=0.3)
NEUTRAL_CONFIDENCE = {"sector": "high", "market": "degraded", "none": "insufficient_peers"}


def _active_metrics(profile: dict) -> list[str]:
    # dead_hard_filters_repair (v12 T0-2): metrics listesine yanlislikla yasakli bir
    # metrik eklenirse (orn. bank'a ev_ebitda) burada acikca filtrelenir.
    forbidden = set(profile.get("forbidden_metrics", []))
    return [m for m in profile["metrics"] if m not in forbidden]


def _reference_set(members: list[dict], is_value_sn: bool) -> list[dict]:
    """z istatistiklerinin hesaplandigi kesit: panelin aylik evreni.

    Panel finansallari icermez (pit_panel.FINANCIAL_SECTORS) ve 60g medyan TL hacmine
    gore en az likit %30'u z'den once atar. Likidite verisi hic yoksa (testler, skill
    CLI) kesim uygulanmaz. Referans disinda kalan adaylar ayni istatistiklerle skorlanir.
    """
    ref = [c for c in members if not (is_value_sn and c.get("sector") in FINANCIAL_SECTORS)]
    liq = [c.get("tl_vol_med60") for c in ref]
    vals = sorted(v for v in liq if v is not None and _finite(v) and v > 0)
    if not vals:
        return ref
    cut = _quantile(vals, LIQ_DROP_PCT)
    return [c for c in ref if c.get("tl_vol_med60") is not None and _finite(c["tl_vol_med60"])
            and c["tl_vol_med60"] > 0 and c["tl_vol_med60"] >= cut]


def _metric_stats(ref: list[dict], metric: str, sign: int) -> tuple[float, float, float, float] | None:
    """winsorize_z istatistikleri: (alt sinir, ust sinir, ortalama, orneklem std)."""
    vals = [sign * v for v in (_metric_value(c, metric) for c in ref) if v is not None]
    if len(vals) < MIN_METRIC_N:
        return None
    s = sorted(vals)
    lo, hi = _quantile(s, WINSOR_LO), _quantile(s, WINSOR_HI)
    clipped = [min(max(v, lo), hi) for v in vals]
    sd = stdev(clipped)
    return (lo, hi, mean(clipped), sd) if sd > 0 else None


def _score_pool(members: list[dict], profile: dict, is_value_sn: bool) -> list[dict]:
    metrics = _active_metrics(profile)
    ref = _reference_set(members, is_value_sn)
    ref_ids = {id(c) for c in ref}
    stats = {}
    for m in metrics:
        sign = 1 if profile["direction"][m] == "higher_better" else -1
        st = _metric_stats(ref, m, sign)
        if st is not None:
            stats[m] = (sign, *st)

    raw: list[tuple[float | None, list[str]]] = []
    for c in members:
        zs, used = [], []
        for m, (sign, lo, hi, mu, sd) in stats.items():
            v = _metric_value(c, m)
            if v is None:
                continue
            # Winsorize siniri referans kesitin %1/%99'u; aday kendi emsal araligina kirpilmaz.
            zs.append((min(max(sign * v, lo), hi) - mu) / sd)
            used.append(m)
        raw.append((mean(zs) if zs else None, used))

    # sector_neutralize: referans kesitte sektor >= MIN_SECTOR_N ise sektor ortalamasi,
    # degilse tum kesit ortalamasi cikarilir.
    by_sector: dict[str, list[float]] = {}
    market: list[float] = []
    for c, (v, _) in zip(members, raw):
        if v is not None and id(c) in ref_ids:
            by_sector.setdefault(c.get("sector"), []).append(v)
            market.append(v)

    out = []
    for c, (v, used) in zip(members, raw):
        res = {"valuation_z": None, "peer_group_used": "none", "peer_n": len(market),
               "confidence": NEUTRAL_CONFIDENCE["none"],
               "valid_metric_count": len(used), "metrics_used": used}
        if v is not None and len(market) >= MIN_PEER_N:
            sec = by_sector.get(c.get("sector"), [])
            level, group = ("sector", sec) if len(sec) >= MIN_SECTOR_N else ("market", market)
            res.update(valuation_z=v - mean(group), peer_group_used=level, peer_n=len(group),
                       confidence=NEUTRAL_CONFIDENCE[level])
        out.append(res)
    return out


def compute_valuation_scores(candidates: list[dict]) -> list[dict]:
    """Tum adaylar icin sektor-notr valuation_z (girdiyle ayni sirada).

    Havuz: ayni reporting_basis ve ayni oran seti (sanayi/holding/GYO ortak value_sn
    havuzu, panelde oldugu gibi; banka ve sigorta kendi profilleri). Her sonuc
    valid_metric_count ve metrics_used tasir: skor kac/hangi orandan olustu.
    """
    pools: dict[tuple, list[int]] = {}
    for i, c in enumerate(candidates):
        profile = c["ratio_profile"]
        family = "value_sn" if RATIO_PROFILES[profile]["metrics"] == VALUE_SN_METRICS else profile
        pools.setdefault((c["reporting_basis"], family), []).append(i)
    out: list[dict | None] = [None] * len(candidates)
    for (_, family), idx in pools.items():
        members = [candidates[i] for i in idx]
        profile = _VALUE_SN_PROFILE if family == "value_sn" else RATIO_PROFILES[family]
        for i, res in zip(idx, _score_pool(members, profile, family == "value_sn")):
            out[i] = res
    return out


def compute_valuation_z(candidate: dict, all_candidates: list[dict]) -> dict:
    """Tek aday icin sarmalayici; havuz all_candidates (aday icinde degilse eklenir)."""
    pool = list(all_candidates)
    pos = next((i for i, c in enumerate(pool) if c is candidate), None)
    if pos is None:
        pool.append(candidate)
        pos = len(pool) - 1
    return compute_valuation_scores(pool)[pos]
