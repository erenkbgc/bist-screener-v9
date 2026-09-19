"""core/portfolio.py: BIST Screener Portfoy Optimizasyonu ve Agirliklandirma Modulu.

v13 Roadmap P1-5:
1. Risk Parity (Esit Risk Katkisi / Ters Volatilite).
2. Minimum Variance (Kovaryans bazli min risk).
3. Maximum Sharpe (Maksimum getiri/risk orani).
4. Korelasyon Filtresi: Korelasyon > 0.80 olan hisselerden yalnizca daha yuksek skorluyu secme.
5. Sektor Limiti: Hicbir sektor portfoyun %30'unu asamaz (max %30 tavan kisiti).
Cikti: recommended_portfolio_weights, sector_allocations, portfoy metrikleri.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as sch
import scipy.spatial.distance as scd

from core import db

logger = logging.getLogger(__name__)

DEFAULT_CORRELATION_THRESHOLD = 0.80
DEFAULT_MAX_SECTOR_WEIGHT = 0.30
ANNUAL_TRADING_DAYS = 252


# =====================================================================
# 1. KORELASYON HESAPLAMA VE FILTRELEME
# =====================================================================

def calculate_returns_and_covariance(
    tickers: list[str],
    price_series_by_ticker: dict[str, list[dict]],
    window_days: int = 60,
) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    """Kapanis fiyatlarindan gunluk log/yuzde getirileri ve yilliklandirilmis kovaryans matrisini hesaplar."""
    returns_dict: dict[str, np.ndarray] = {}
    valid_tickers: list[str] = []

    for t in tickers:
        bars = price_series_by_ticker.get(t, [])
        if len(bars) < 15:
            continue
        closes = [float(b["close"]) for b in bars[-window_days:] if b.get("close")]
        if len(closes) < 15:
            continue
        arr = np.array(closes, dtype=float)
        # Gunluk getiri
        rets = np.diff(arr) / arr[:-1]
        returns_dict[t] = rets
        valid_tickers.append(t)

    if len(valid_tickers) < 2:
        return returns_dict, np.array([]), np.array([])

    # Ortak uzunluga kirp
    min_len = min(len(returns_dict[t]) for t in valid_tickers)
    mat = np.column_stack([returns_dict[t][-min_len:] for t in valid_tickers])

    # Yilliklandirilmis kovaryans matrisi
    cov_matrix = np.cov(mat, rowvar=False) * ANNUAL_TRADING_DAYS
    # Volatiliteler (yillik %)
    vols = np.sqrt(np.diag(cov_matrix)) * 100.0

    return returns_dict, cov_matrix, vols


def filter_correlated_candidates(
    candidates: list[dict],
    returns_dict: dict[str, np.ndarray],
    threshold: float = DEFAULT_CORRELATION_THRESHOLD,
) -> tuple[list[dict], list[dict]]:
    """Korelasyonu threshold'u (>0.80) asan ciftlerden skoru dusuk olani eler."""
    tickers = [c["ticker"] for c in candidates if c["ticker"] in returns_dict]
    if len(tickers) < 2:
        return candidates, []

    # Ortak boyutta matris
    min_len = min(len(returns_dict[t]) for t in tickers)
    data = np.column_stack([returns_dict[t][-min_len:] for t in tickers])
    corr_mat = np.corrcoef(data, rowvar=False)

    candidate_map = {c["ticker"]: c for c in candidates}
    dropped_info: list[dict] = []
    excluded_tickers: set[str] = set()

    for i in range(len(tickers)):
        ti = tickers[i]
        if ti in excluded_tickers:
            continue
        for j in range(i + 1, len(tickers)):
            tj = tickers[j]
            if tj in excluded_tickers:
                continue
            corr = float(corr_mat[i, j])
            if corr > threshold:
                score_i = float(candidate_map[ti].get("final_score", 0.0) or 0.0)
                score_j = float(candidate_map[tj].get("final_score", 0.0) or 0.0)

                # Skoru yuksek olani tut, digerini ele
                if score_i >= score_j:
                    kept, dropped = ti, tj
                    s_kept, s_dropped = score_i, score_j
                else:
                    kept, dropped = tj, ti
                    s_kept, s_dropped = score_j, score_i

                excluded_tickers.add(dropped)
                dropped_info.append({
                    "dropped": dropped,
                    "kept": kept,
                    "correlation": round(corr, 3),
                    "reason": (
                        f"Korelasyon {corr:.2f} > {threshold:.2f} esigini asti; "
                        f"{kept} (skor: {s_kept:.2f}), {dropped}'e (skor: {s_dropped:.2f}) tercih edildi."
                    ),
                })

    kept_candidates = [c for c in candidates if c["ticker"] not in excluded_tickers]
    return kept_candidates, dropped_info


# =====================================================================
# 2. SEKTOR LIMITI VE KISIT PROJEKSIYONU
# =====================================================================

def apply_sector_caps(
    weights: np.ndarray,
    sectors: list[str],
    max_sector_weight: float = DEFAULT_MAX_SECTOR_WEIGHT,
    max_iter: int = 50,
) -> tuple[np.ndarray, bool]:
    """Hicbir sektorun toplam portfoy agirligi max_sector_weight (%30) degerini asamaz.
    
    Sinirli simpleks projeksiyonu (bounded simplex projection) kullanilarak sektor toplamlari
    tam [0, max_sector_weight] kutusu icine projelendirilir ve toplam 1.0 korunur.
    """
    w = np.copy(weights)
    if len(w) == 0:
        return w, False

    s = np.sum(w)
    if s > 0:
        w /= s
    else:
        w = np.ones_like(w) / len(w)

    unique_sectors = sorted(list(set(sectors)))
    K = len(unique_sectors)
    
    # Teorik alt sinir kontrolu (orn. 2 sektor varsa her biri en az 0.50 olmak zorundadir)
    if K * max_sector_weight < 1.0:
        C = 1.0 / K
    else:
        C = max_sector_weight

    # Mevcut sektor agirliklari
    raw_s = np.array([float(np.sum(w[[i for i, s_name in enumerate(sectors) if s_name == sec]])) for sec in unique_sectors])
    
    if np.all(raw_s <= C + 1e-5):
        return w, False

    # Bounded simplex projection via bisection on lambda: sum(clip(s - lambda, 0, C)) = 1.0
    low = np.min(raw_s) - 1.0
    high = np.max(raw_s) + 1.0
    for _ in range(60):
        mid = (low + high) / 2.0
        val = np.sum(np.clip(raw_s - mid, 0.0, C))
        if val > 1.0:
            low = mid
        else:
            high = mid
    target_s = np.clip(raw_s - (low + high) / 2.0, 0.0, C)
    # Kucuk sayisal yuvarlama duzeltmesi
    target_s /= np.sum(target_s)

    # Sektor ici hisselere dagit
    w_new = np.zeros_like(w)
    for k, sec in enumerate(unique_sectors):
        sec_idx = [i for i, s_name in enumerate(sectors) if s_name == sec]
        cur_sec_w = float(np.sum(w[sec_idx]))
        if cur_sec_w > 1e-6:
            w_new[sec_idx] = target_s[k] * (w[sec_idx] / cur_sec_w)
        else:
            w_new[sec_idx] = target_s[k] / len(sec_idx)

    total = np.sum(w_new)
    if total > 0:
        w_new /= total

    return w_new, True


# =====================================================================
# 3. PORTFOY OPTIMIZASYON MOTORLARI
# =====================================================================

def optimize_risk_parity(
    cov_matrix: np.ndarray,
    sectors: list[str],
    max_sector_weight: float = DEFAULT_MAX_SECTOR_WEIGHT,
) -> tuple[np.ndarray, bool]:
    """Risk Parity / Inverse Volatility Agirliklandirma.
    
    w_i = (1 / sigma_i) / sum(1 / sigma_j), ardindan %30 sektor tavan kisiti.
    """
    n = cov_matrix.shape[0]
    vols = np.sqrt(np.maximum(1e-8, np.diag(cov_matrix)))
    inv_vols = 1.0 / vols
    raw_weights = inv_vols / np.sum(inv_vols)

    w_capped, cap_applied = apply_sector_caps(raw_weights, sectors, max_sector_weight=max_sector_weight)
    return w_capped, cap_applied


def optimize_min_variance(
    cov_matrix: np.ndarray,
    sectors: list[str],
    max_sector_weight: float = DEFAULT_MAX_SECTOR_WEIGHT,
    max_iter: int = 200,
    lr: float = 0.05,
) -> tuple[np.ndarray, bool]:
    """Minimum Variance Portfoyu (Projektif Gradyan Inisi).
    
    Minimize 0.5 * w^T Sigma w  subject to: w >= 0, sum(w) = 1, sector <= 30%
    """
    n = cov_matrix.shape[0]
    # Baslangic: esit agirlik
    w = np.ones(n, dtype=float) / n

    # Sayisal stabilite icin kucuk duzenleme (ridge)
    cov_reg = cov_matrix + np.eye(n) * 1e-5

    for _ in range(max_iter):
        # Gradyan: grad = Sigma * w
        grad = cov_reg @ w
        # Gradient descent step
        w_new = w - lr * grad
        # Long-only kisiti: non-negatif
        w_new = np.maximum(0.0, w_new)
        # Normalizasyon
        s = np.sum(w_new)
        if s > 0:
            w_new /= s
        else:
            w_new = np.ones(n) / n
        w = w_new

    # Sektor tavan kisitini uygula
    w_capped, cap_applied = apply_sector_caps(w, sectors, max_sector_weight=max_sector_weight)
    return w_capped, cap_applied


def optimize_max_sharpe(
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    sectors: list[str],
    risk_free_rate: float = 0.40,  # yillik %40 politika faizi
    max_sector_weight: float = DEFAULT_MAX_SECTOR_WEIGHT,
    max_iter: int = 200,
    lr: float = 0.02,
) -> tuple[np.ndarray, bool]:
    """Maksimum Sharpe Portfoyu (Projektif Gradyan Inisi / Tangency Portfolio).
    
    Maximize (w^T mu - rf) / sqrt(w^T Sigma w) subject to w >= 0, sum(w)=1, sector <= 30%
    """
    n = len(expected_returns)
    w = np.ones(n, dtype=float) / n
    cov_reg = cov_matrix + np.eye(n) * 1e-5

    excess_ret = expected_returns - risk_free_rate
    # Eger tum excess_ret negatifse (ornek piyasa cok kotuyse), Min Variance'a fallback yap
    if np.all(excess_ret <= 0):
        return optimize_min_variance(cov_matrix, sectors, max_sector_weight=max_sector_weight)

    # Pozitif katsayilarla basla
    excess_pos = np.maximum(0.01, excess_ret)
    w = excess_pos / np.sum(excess_pos)

    for _ in range(max_iter):
        port_ret = float(w @ expected_returns)
        port_var = float(w @ cov_reg @ w)
        port_sd = np.sqrt(max(1e-8, port_var))

        # Sharpe gradyani: d/dw [(w^T mu - rf) / sd] = (mu * sd - (port_ret - rf) * (Sigma * w / sd)) / var
        num = port_ret - risk_free_rate
        grad = (expected_returns * port_sd - num * (cov_reg @ w / port_sd)) / max(1e-8, port_var)

        # Gradient ascent
        w_new = w + lr * grad
        w_new = np.maximum(0.0, w_new)
        s = np.sum(w_new)
        if s > 0:
            w_new /= s
        else:
            w_new = np.ones(n) / n
        w = w_new

    w_capped, cap_applied = apply_sector_caps(w, sectors, max_sector_weight=max_sector_weight)
    return w_capped, cap_applied


def get_quasi_diag(link: np.ndarray) -> list[int]:
    """Hierarchical tree linkage matrisinden sirali yaprak indekslerini (quasi-diagonal) dondurur."""
    link = link.astype(int)
    sort_ix = [int(link[-1, 0]), int(link[-1, 1])]
    num_items = int(link[-1, 3])
    while any(i >= num_items for i in sort_ix):
        new_sort_ix = []
        for item in sort_ix:
            if item >= num_items:
                idx = item - num_items
                new_sort_ix.extend([int(link[idx, 0]), int(link[idx, 1])])
            else:
                new_sort_ix.append(item)
        sort_ix = new_sort_ix
    return sort_ix


def get_cluster_var(cov: np.ndarray, c_items: list[int]) -> float:
    """Bir kume icindeki hisselerin ters varyans agirlikli portfoy varyansini hesaplar."""
    sub_cov = cov[np.ix_(c_items, c_items)]
    inv_diag = 1.0 / np.maximum(1e-8, np.diag(sub_cov))
    w = inv_diag / np.sum(inv_diag)
    c_var = float(w @ sub_cov @ w)
    return max(1e-8, c_var)


def get_rec_bisection(cov: np.ndarray, sort_ix: list[int]) -> np.ndarray:
    """Siralanmis yapraklar uzerinde ozyinelemeli ikili bolme ile HRP agirliklarini hesaplar."""
    weights = pd.Series(1.0, index=sort_ix)
    c_items = [sort_ix]
    while len(c_items) > 0:
        c_items = [i[j:k] for i in c_items for j, k in ((0, len(i) // 2), (len(i) // 2, len(i))) if len(i) > 1]
        for i in range(0, len(c_items), 2):
            c1 = c_items[i]
            c2 = c_items[i + 1]
            v1 = get_cluster_var(cov, c1)
            v2 = get_cluster_var(cov, c2)
            denom = v1 + v2
            alpha = 1.0 - (v1 / denom) if denom > 0 else 0.5
            weights[c1] *= alpha
            weights[c2] *= (1.0 - alpha)
    return weights.sort_index().values


def optimize_hrp(
    cov_matrix: np.ndarray,
    sectors: list[str],
    max_sector_weight: float = DEFAULT_MAX_SECTOR_WEIGHT,
) -> tuple[np.ndarray, bool]:
    """Hierarchical Risk Parity (HRP) Portfoyu (Marcos López de Prado 2016, Quant Level-Up Faz 4).
    
    1. Agac Tabanli Kumeleme (Tree Clustering): Korelasyon uzakligi d = sqrt(0.5 * (1 - rho))
    2. Yari-Kosegenlestirme (Quasi-Diagonalization): Dendrogram yaprak siralamasi
    3. Ozyinelemeli Ikili Bolme (Recursive Bisection): Kumeler arasi risk paylasimi
    4. Sektor Tavan Kisiti (%30)
    """
    n = cov_matrix.shape[0]
    if n <= 1:
        return np.ones(n, dtype=float), False

    # 1. Korelasyon ve Mesafe Matrisi
    vols = np.sqrt(np.maximum(1e-8, np.diag(cov_matrix)))
    outer_vols = np.outer(vols, vols)
    corr = np.clip(cov_matrix / np.maximum(1e-8, outer_vols), -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)

    # Mesafe: d_{i,j} = sqrt(0.5 * (1 - rho_{i,j}))
    dist = np.sqrt(np.clip(0.5 * (1.0 - corr), 0.0, 1.0))
    np.fill_diagonal(dist, 0.0)

    try:
        condensed_dist = scd.squareform(dist, checks=False)
        link = sch.linkage(condensed_dist, method="single")
        sort_ix = get_quasi_diag(link)
        w_raw = get_rec_bisection(cov_matrix, sort_ix)
    except Exception as e:
        logger.warning("HRP kumeleme hatasi, risk parity'e fallback yapiliyor: %s", e)
        return optimize_risk_parity(cov_matrix, sectors, max_sector_weight=max_sector_weight)

    w_capped, cap_applied = apply_sector_caps(w_raw, sectors, max_sector_weight=max_sector_weight)
    return w_capped, cap_applied


def compute_portfolio_cvar(
    weights: np.ndarray,
    returns_matrix: np.ndarray,
    confidence: float = 0.95,
) -> float:
    """Portfoy icin %95 Kosullu Riske Maruz Deger (CVaR / Expected Shortfall) hesaplar.
    
    returns_matrix: (T, N) boyutlu gunluk getiri matrisi.
    weights: (N,) boyutlu portfoy agirlik vektoru.
    
    Donus: Gunluk yuzde bazinda ortalama kuyruk kaybi (pozitif risk degeri, or. %2.35).
    """
    if len(weights) == 0 or returns_matrix.size == 0:
        return 0.0

    port_returns = returns_matrix @ weights
    if len(port_returns) < 5:
        return 0.0

    alpha = 1.0 - confidence
    var_threshold = float(np.percentile(port_returns, alpha * 100))

    tail_returns = port_returns[port_returns <= var_threshold]
    if len(tail_returns) == 0:
        cvar = -var_threshold
    else:
        cvar = -float(np.mean(tail_returns))

    return round(max(0.0, cvar * 100.0), 2)


# =====================================================================
# 4. ANA OPTIMIZASYON AKISI & DB ENTEGRASYONU
# =====================================================================

def optimize_portfolio(
    candidates: list[dict],
    price_series_by_ticker: dict[str, list[dict]],
    method: str = "hrp",  # 'hrp' (varsayilan) | 'risk_parity' | 'min_variance' | 'max_sharpe'
    as_of_date: str = "2026-09-17",
    risk_free_rate_pct: float = 40.0,
    max_sector_weight: float = DEFAULT_MAX_SECTOR_WEIGHT,
    correlation_threshold: float = DEFAULT_CORRELATION_THRESHOLD,
    save_to_db: bool = True,
) -> dict[str, Any]:
    """Aday listesi uzerinde korelasyon filtresi, sektor kisiti ve portfoy optimizasyonu calistirir."""
    if not candidates:
        return {
            "as_of_date": as_of_date,
            "method": method,
            "recommended_portfolio_weights": {},
            "sector_allocations_pct": {},
            "portfolio_expected_return_pct": 0.0,
            "portfolio_volatility_pct": 0.0,
            "sharpe_ratio": 0.0,
            "cvar_95_pct": 0.0,
            "active_candidates_count": 0,
            "dropped_correlated_pairs": [],
            "sector_cap_applied": False,
        }

    # 1. Kapanis fiyat serilerinden getiriler ve kovaryans matrisi
    all_tickers = [c["ticker"] for c in candidates]
    returns_dict, _, _ = calculate_returns_and_covariance(all_tickers, price_series_by_ticker, window_days=60)

    # 2. Korelasyon Filtresi (> 0.80 olan ciftlerden skoru dusuk olani ele)
    filtered_candidates, dropped_info = filter_correlated_candidates(
        candidates, returns_dict, threshold=correlation_threshold
    )

    active_tickers = [c["ticker"] for c in filtered_candidates if c["ticker"] in returns_dict]
    if len(active_tickers) == 0:
        active_tickers = [c["ticker"] for c in filtered_candidates]

    # Tek hisse durumu
    if len(active_tickers) == 1:
        single = active_tickers[0]
        c_item = next(c for c in filtered_candidates if c["ticker"] == single)
        sec = c_item.get("sector", "BILINMIYOR")
        exp_roi = float(c_item.get("expected_roi_pct", 0.0) or 0.0)
        return {
            "as_of_date": as_of_date,
            "method": method,
            "recommended_portfolio_weights": {single: 100.0},
            "sector_allocations_pct": {sec: 100.0},
            "portfolio_expected_return_pct": exp_roi,
            "portfolio_volatility_pct": 25.0,
            "sharpe_ratio": round((exp_roi - risk_free_rate_pct) / 25.0, 2),
            "cvar_95_pct": 0.0,
            "active_candidates_count": 1,
            "dropped_correlated_pairs": dropped_info,
            "sector_cap_applied": False,
        }

    # Yeniden filtrelenmis evren icin kovaryans ve getiri matrisi
    _, cov_matrix, vols = calculate_returns_and_covariance(active_tickers, price_series_by_ticker, window_days=60)

    n = len(active_tickers)

    if cov_matrix.size == 0:
        # Hicbir adayin yeterli (>=15 bar) fiyat gecmisi yok: kovaryans hesaplanamaz.
        # Optimizasyona (bos matrisle index hatasi verir) girmek yerine esit
        # agirlikli portfoyle guvenli sekilde devam et.
        equal_w = 100.0 / n
        sector_allocs_fallback: dict[str, float] = {}
        for t in active_tickers:
            c_item = next(c for c in filtered_candidates if c["ticker"] == t)
            sec = c_item.get("sector", "BILINMIYOR")
            sector_allocs_fallback[sec] = round(sector_allocs_fallback.get(sec, 0.0) + equal_w, 2)
        avg_exp_roi = float(np.mean([
            float(next(c for c in filtered_candidates if c["ticker"] == t).get("expected_roi_pct", 0.0) or 0.0)
            for t in active_tickers
        ]))
        return {
            "as_of_date": as_of_date,
            "method": method,
            "recommended_portfolio_weights": {t: round(equal_w, 2) for t in active_tickers},
            "sector_allocations_pct": sector_allocs_fallback,
            "portfolio_expected_return_pct": round(avg_exp_roi, 2),
            "portfolio_volatility_pct": 25.0,
            "sharpe_ratio": round((avg_exp_roi - risk_free_rate_pct) / 25.0, 2),
            "cvar_95_pct": 0.0,
            "active_candidates_count": n,
            "dropped_correlated_pairs": dropped_info,
            "sector_cap_applied": False,
            "data_quality_note": "insufficient_price_history_equal_weight_fallback",
        }

    sectors = [next(c.get("sector", "BILINMIYOR") for c in filtered_candidates if c["ticker"] == t) for t in active_tickers]

    # Beklenen getiri vektoru (adaylarin expected_roi_pct degeri veya yoksa tarihsel getiri proxy'si)
    rf_dec = risk_free_rate_pct / 100.0
    exp_returns = []
    for t in active_tickers:
        c_item = next(c for c in filtered_candidates if c["ticker"] == t)
        roi = c_item.get("expected_roi_pct")
        if roi is not None and roi > 0:
            exp_returns.append(float(roi) / 100.0)
        elif t in returns_dict:
            # Gecmis ortalama getiri proxy -- gercek (negatif dahil) trend korunur, yapay taban uygulanmaz.
            annualized_ret = float(np.mean(returns_dict[t])) * ANNUAL_TRADING_DAYS
            exp_returns.append(annualized_ret)
        else:
            # Fiyat gecmisi hic yok: notr bir varsayilan kullan.
            exp_returns.append(0.10)
    exp_ret_arr = np.array(exp_returns, dtype=float)

    # 3. Secilen metod ile optimizasyon
    if method == "min_variance":
        weights, cap_applied = optimize_min_variance(cov_matrix, sectors, max_sector_weight=max_sector_weight)
    elif method == "max_sharpe":
        weights, cap_applied = optimize_max_sharpe(
            exp_ret_arr, cov_matrix, sectors, risk_free_rate=rf_dec, max_sector_weight=max_sector_weight
        )
    elif method == "risk_parity":
        weights, cap_applied = optimize_risk_parity(cov_matrix, sectors, max_sector_weight=max_sector_weight)
    else:  # hrp (varsayilan ve birincil motor)
        weights, cap_applied = optimize_hrp(cov_matrix, sectors, max_sector_weight=max_sector_weight)

    # 4. Sonuclari formatla
    weights_pct = {active_tickers[i]: round(float(weights[i]) * 100.0, 2) for i in range(n)}
    
    # Sektor dagilimi
    sector_allocs: dict[str, float] = {}
    for i in range(n):
        sec = sectors[i]
        sector_allocs[sec] = round(sector_allocs.get(sec, 0.0) + float(weights[i]) * 100.0, 2)

    # Portfoy metrikleri
    port_exp_ret_pct = round(float(weights @ exp_ret_arr) * 100.0, 2)
    port_var = float(weights @ cov_matrix @ weights)
    port_vol_pct = round(np.sqrt(max(1e-8, port_var)) * 100.0, 2)
    sharpe = round((port_exp_ret_pct - risk_free_rate_pct) / max(1.0, port_vol_pct), 2)

    # %95 CVaR (Expected Shortfall) hesabi
    min_len = min(len(returns_dict[t]) for t in active_tickers) if active_tickers else 0
    if min_len >= 5:
        returns_mat = np.column_stack([returns_dict[t][-min_len:] for t in active_tickers])
        cvar_95 = compute_portfolio_cvar(weights, returns_mat, confidence=0.95)
    else:
        cvar_95 = 0.0

    result = {
        "as_of_date": as_of_date,
        "method": method,
        "recommended_portfolio_weights": weights_pct,
        "sector_allocations_pct": sector_allocs,
        "portfolio_expected_return_pct": port_exp_ret_pct,
        "portfolio_volatility_pct": port_vol_pct,
        "sharpe_ratio": sharpe,
        "cvar_95_pct": cvar_95,
        "active_candidates_count": n,
        "dropped_correlated_pairs": dropped_info,
        "sector_cap_applied": cap_applied,
    }

    # 5. DB Kaydi
    if save_to_db:
        save_portfolio_allocations(as_of_date, method, weights_pct, sectors, active_tickers, exp_returns, vols)

    return result


def save_portfolio_allocations(
    as_of_date: str,
    method: str,
    weights_pct: dict[str, float],
    sectors: list[str],
    tickers: list[str],
    exp_returns: list[float],
    vols: np.ndarray,
) -> None:
    """Hesaplanan portfoy agirliklarini portfolio_allocations tablosuna kaydeder."""
    rows = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for i, t in enumerate(tickers):
        w = weights_pct.get(t, 0.0)
        sec = sectors[i] if i < len(sectors) else "UNKNOWN"
        ret_pct = round(exp_returns[i] * 100.0, 2) if i < len(exp_returns) else 0.0
        vol_pct = round(float(vols[i]), 2) if i < len(vols) else 0.0
        rows.append((as_of_date, t, method, w, sec, ret_pct, vol_pct, now_iso))

    conn = db.get_connection()
    try:
        conn.executemany(
            """INSERT INTO portfolio_allocations
               (as_of_date, ticker, method, weight_pct, sector, expected_return_pct, volatility_pct, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(as_of_date, ticker, method) DO UPDATE SET
                 weight_pct=excluded.weight_pct,
                 sector=excluded.sector,
                 expected_return_pct=excluded.expected_return_pct,
                 volatility_pct=excluded.volatility_pct,
                 created_at=excluded.created_at""",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def get_portfolio_allocations(as_of_date: str, method: str = "risk_parity") -> list[dict]:
    """Kayitli portfoy agirliklarini getirir."""
    rows = db.query(
        "SELECT * FROM portfolio_allocations WHERE as_of_date = ? AND method = ? ORDER BY weight_pct DESC",
        (as_of_date, method),
    )
    return [dict(r) for r in rows]
