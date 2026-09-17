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


# =====================================================================
# 4. ANA OPTIMIZASYON AKISI & DB ENTEGRASYONU
# =====================================================================

def optimize_portfolio(
    candidates: list[dict],
    price_series_by_ticker: dict[str, list[dict]],
    method: str = "risk_parity",  # 'risk_parity' | 'min_variance' | 'max_sharpe'
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
            "active_candidates_count": 1,
            "dropped_correlated_pairs": dropped_info,
            "sector_cap_applied": False,
        }

    # Yeniden filtrelenmis evren icin kovaryans ve getiri matrisi
    _, cov_matrix, vols = calculate_returns_and_covariance(active_tickers, price_series_by_ticker, window_days=60)

    n = len(active_tickers)
    sectors = [next(c.get("sector", "BILINMIYOR") for c in filtered_candidates if c["ticker"] == t) for t in active_tickers]

    # Beklenen getiri vektoru (adaylarin expected_roi_pct degeri veya yoksa tarihsel getiri proxy'si)
    rf_dec = risk_free_rate_pct / 100.0
    exp_returns = []
    for t in active_tickers:
        c_item = next(c for c in filtered_candidates if c["ticker"] == t)
        roi = c_item.get("expected_roi_pct")
        if roi is not None and roi > 0:
            exp_returns.append(float(roi) / 100.0)
        else:
            # Gecmis ortalama getiri proxy
            r_arr = returns_dict.get(t, np.array([0.0]))
            annualized_ret = float(np.mean(r_arr)) * ANNUAL_TRADING_DAYS
            exp_returns.append(max(0.10, annualized_ret))
    exp_ret_arr = np.array(exp_returns, dtype=float)

    # 3. Secilen metod ile optimizasyon
    if method == "min_variance":
        weights, cap_applied = optimize_min_variance(cov_matrix, sectors, max_sector_weight=max_sector_weight)
    elif method == "max_sharpe":
        weights, cap_applied = optimize_max_sharpe(
            exp_ret_arr, cov_matrix, sectors, risk_free_rate=rf_dec, max_sector_weight=max_sector_weight
        )
    else:  # risk_parity (varsayilan)
        weights, cap_applied = optimize_risk_parity(cov_matrix, sectors, max_sector_weight=max_sector_weight)

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

    result = {
        "as_of_date": as_of_date,
        "method": method,
        "recommended_portfolio_weights": weights_pct,
        "sector_allocations_pct": sector_allocs,
        "portfolio_expected_return_pct": port_exp_ret_pct,
        "portfolio_volatility_pct": port_vol_pct,
        "sharpe_ratio": sharpe,
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
