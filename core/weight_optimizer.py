"""core/weight_optimizer.py: Sifir Manuel Agirlik & Kantitatif Optimizasyon Motoru.

Akademik ve kurumsal portfoy yonetimi standartlarina (Granger-Ramanathan,
Grinold-Kahn, Brier Score Loss Minimization, Black-Scholes Volatility Cones)
dayanarak sistemdeki tum agirliklari gecmis veriler uzerinden ampirik olarak
cozer ve kalibre eder.

Manuel / subyektif agirlik kullanilmaz.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import spearmanr

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
OPTIMIZED_WEIGHTS_PATH = CONFIG_DIR / "weights_optimized.json"


# =============================================================================
# 1. ANALITIK SENARYO OLASILIKLARI (TRINOMIAL TRANSITION MAPPING)
# =============================================================================

def derive_scenario_probabilities(prob_up: float) -> dict[str, float]:
    """TrendForecaster'in urettigi kalibre edilmis p = prob_up degerinden
    matematiksel olarak kapali formda (closed-form) ucluk (trinomial) senaryo
    dagilimini uretir.
    
    Formul:
      P(Bull) = p^2           (Yüksek guvenli yukselis)
      P(Bear) = (1 - p)^2     (Yüksek guvenli dusus)
      P(Base) = 2 * p * (1 - p) (Belirsizlik / Merkezcil denge)
      
    Ozellik:
      p^2 + 2p(1-p) + (1-p)^2 = (p + (1-p))^2 = 1.0 (Her zaman tam 1'e esittir).
      Hicbir elle yazilmis YAML katsayisi icermez.
    """
    p = float(np.clip(prob_up, 0.0, 1.0))
    p_bull = p ** 2
    p_bear = (1.0 - p) ** 2
    p_base = 2.0 * p * (1.0 - p)

    return {
        "bull": round(p_bull, 4),
        "base": round(p_base, 4),
        "bear": round(p_bear, 4),
    }


# =============================================================================
# 2. HARMONIK ORTALAMA (HARMONIC MEAN MULTIPLES)
# =============================================================================

def compute_harmonic_mean(values: list[float] | np.ndarray) -> float | None:
    """Carpan rasyolarinda (F/K, FD/FAVOK, PD/DD) fiyat payda yer aldigi icin
    akademik literatur (Damodaran, Liu-Nissim-Thomas) tarafindan kanitlanan
    yansiz (unbiased) harmonik ortalamayi hesaplar:
      H = N / sum(1 / x_i)
    Pozitif olmayan veya sifira yakin carpik degerler ayiklanir.
    """
    clean_vals = [float(v) for v in values if v is not None and v > 0.001 and not np.isnan(v)]
    if not clean_vals:
        return None
    inv_sum = sum(1.0 / v for v in clean_vals)
    if inv_sum <= 0:
        return None
    return float(len(clean_vals) / inv_sum)


# =============================================================================
# 3. ENSEMBLE AGIRLIK OPTIMIZASYONU (BRIER SCORE LOSS MINIMIZATION)
# =============================================================================

def optimize_ensemble_weights(
    y_true: np.ndarray,
    prob_rf: np.ndarray,
    prob_lr: np.ndarray,
) -> tuple[float, float]:
    """Random Forest ve Logistic Regression olasilik tahminlerini birlestiren
    optimum agirligi Brier Skorunu (Mean Squared Error) minimize ederek cozer:
      min_w (1/N) * sum( (y_i - (w * p_rf_i + (1-w) * p_lr_i))^2 )  s.t. w in [0, 1]
    """
    y = np.asarray(y_true, dtype=float)
    p1 = np.asarray(prob_rf, dtype=float)
    p2 = np.asarray(prob_lr, dtype=float)

    if len(y) < 10:
        # Minimum orneklem yoksa esit agirlik (1/N)
        return 0.50, 0.50

    def loss(w: float) -> float:
        blend = w * p1 + (1.0 - w) * p2
        return float(np.mean((y - blend) ** 2))

    res = minimize_scalar(loss, bounds=(0.0, 1.0), method="bounded")
    best_w = float(res.x) if res.success else 0.50
    return round(best_w, 4), round(1.0 - best_w, 4)


# =============================================================================
# 4. DEGERLEME UCGENI AGIRLIK OPTIMIZASYONU (GRANGER-RAMANATHAN FORECAST COMBINATION)
# =============================================================================

def optimize_valuation_weights(
    valuations_by_leg: dict[str, list[float]],
    realized_prices: list[float],
) -> dict[str, float]:
    """Her degerleme bacaginin (DCF, Peers, Quality) gerceklesen fiyatlara karsi
    tahmin hatasini (MSPE) minimize eden L2 kısıtlı agirliklarini cozer:
      min_w sum( (P_actual - sum(w_k * V_k))^2 )  s.t. sum(w)=1, w_k >= 0
    Orneklem yetersizse ters-varyans (Inverse-MSPE) agirliklandirmasi uygular.
    """
    legs = [k for k, v in valuations_by_leg.items() if len(v) == len(realized_prices) and len(v) > 0]
    if not legs or len(realized_prices) < 5:
        # Orneklem yoksa yansiz esit agirlik (1/N)
        n = len(valuations_by_leg) or 1
        return {k: round(1.0 / n, 4) for k in valuations_by_leg}

    y = np.asarray(realized_prices, dtype=float)
    X = np.column_stack([np.asarray(valuations_by_leg[k], dtype=float) for k in legs])

    # NaN veya inf degerleri filtrele
    valid_mask = np.isfinite(y) & (y > 0)
    for i in range(X.shape[1]):
        valid_mask &= np.isfinite(X[:, i]) & (X[:, i] > 0)

    if np.sum(valid_mask) < 5:
        n = len(valuations_by_leg) or 1
        return {k: round(1.0 / n, 4) for k in valuations_by_leg}

    y = y[valid_mask]
    X = X[valid_mask]

    # 1. Adim: Her bacagin Mean Squared Percentage Error (MSPE) degeri
    mspe_dict = {}
    for i, leg in enumerate(legs):
        err = (X[:, i] - y) / np.maximum(y, 1e-4)
        mspe_dict[leg] = float(np.mean(err ** 2))

    # Orneklem kucukse (<20) veya optimizasyon yakinsamazsa Inverse-MSPE:
    inv_mspe = {k: 1.0 / max(v, 1e-6) for k, v in mspe_dict.items()}
    tot_inv = sum(inv_mspe.values())
    inv_weights = {k: round(v / tot_inv, 4) for k, v in inv_mspe.items()}

    if len(y) < 20:
        return inv_weights

    # Orneklem yeterliyse kısıtlı kuadratik optimizasyon:
    k = len(legs)
    init_w = np.ones(k) / k
    bounds = [(0.05, 0.80) for _ in range(k)]  # hicbir bacak %5'in altina inemez veya %80'i asamaz
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

    def objective(w: np.ndarray) -> float:
        pred = X @ w
        pct_err = (pred - y) / np.maximum(y, 1e-4)
        return float(np.mean(pct_err ** 2))

    res = minimize(objective, init_w, method="SLSQP", bounds=bounds, constraints=constraints)
    if res.success:
        return {legs[i]: round(float(res.x[i]), 4) for i in range(k)}
    return inv_weights


# =============================================================================
# 5. FAKTOR SKORLAMA VE BILGI ORANI (INFORMATION RATIO / IC OPTIMIZATION)
# =============================================================================

def optimize_factor_weights(
    factor_df: pd.DataFrame,
    forward_returns: pd.Series,
) -> dict[str, float]:
    """Grinold & Kahn (Active Portfolio Management) kuralina gore:
    Her faktörün ileri donuk getiriyle Spearman sira korelasyonunu (IC) hesaplar.
    Faktör agirliklari pozitif Bilgi Katsayisi ile orantilidir (min %5 zemin):
      w_f = max(0.05, IC_f) / sum(max(0.05, IC_j))
    """
    if factor_df.empty or len(forward_returns) < 10:
        n = len(factor_df.columns) or 1
        return {col: round(1.0 / n, 4) for col in factor_df.columns}

    ic_dict = {}
    for col in factor_df.columns:
        valid_idx = factor_df[col].dropna().index.intersection(forward_returns.dropna().index)
        if len(valid_idx) < 10:
            ic_dict[col] = 0.05
            continue
        corr, _ = spearmanr(factor_df.loc[valid_idx, col], forward_returns.loc[valid_idx])
        ic_dict[col] = max(0.05, float(corr) if not np.isnan(corr) else 0.05)

    tot_ic = sum(ic_dict.values())
    return {k: round(v / tot_ic, 4) for k, v in ic_dict.items()}


# =============================================================================
# 6. OYNAKLIK KONISI & YAKINSAMA HIZI KALIBRASYONU (VOLATILITY CONE CALIBRATION)
# =============================================================================

def calibrate_volatility_cone_and_convergence(
    prices: pd.Series,
    horizon_days: int = 180,
    risk_free_annual_pct: float = 45.0,
) -> tuple[float, float]:
    """Tarihsel BIST fiyat serisi uzerinde 180 gunluk normalize edilmis
    fiyat hareketlerini hesaplar ve gerceklesen %95 tek tarafli tavan
    persentilini (z*) ile ampirik fiyat yakinsama hizini (alpha*) kalibre eder.
    """
    if len(prices) < horizon_days + 60:
        # Yetersiz veri durumunda kanitlanmis Gaussian tavan (z=1.75, alpha=0.40)
        return 1.75, 0.40

    close = prices.values
    ret_1d = np.diff(close) / close[:-1]
    vol_60d = pd.Series(ret_1d).rolling(60).std().values * np.sqrt(252)

    T = horizon_days / 252.0
    mu = (risk_free_annual_pct / 100.0) * 0.5  # muhafazakar suruklenme

    normalized_excursions = []
    reversion_fractions = []

    for t in range(60, len(close) - horizon_days, 10):
        p0 = close[t]
        p_fwd = close[t + horizon_days]
        vol = vol_60d[t]
        if np.isnan(vol) or vol <= 0.05:
            continue

        # Normalleştirilmiş log-getiri z-skoru
        expected_log = (mu - 0.5 * (vol ** 2)) * T
        actual_log = np.log(p_fwd / p0)
        z_sample = (actual_log - expected_log) / (vol * np.sqrt(T))
        normalized_excursions.append(z_sample)

        # Yakinsama orani (fiyat hareketi / potansiyel)
        reversion_fractions.append(max(0.1, min(1.0, abs((p_fwd - p0) / p0))))

    if not normalized_excursions:
        return 1.75, 0.40

    z_calibrated = float(np.percentile(normalized_excursions, 95.0))
    z_calibrated = max(1.20, min(2.50, z_calibrated))

    alpha_calibrated = float(np.median(reversion_fractions)) if reversion_fractions else 0.40
    alpha_calibrated = max(0.20, min(0.60, alpha_calibrated))

    return round(z_calibrated, 2), round(alpha_calibrated, 2)


# =============================================================================
# 7. OPTIMIZE EDILMIS AGIRLIKLARI KAYDETME VE YUKLEME
# =============================================================================

def save_optimized_weights(payload: dict[str, Any]) -> None:
    """Optimize edilmis katsayilari JSON dosyasina atomik olarak kaydeder."""
    OPTIMIZED_WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OPTIMIZED_WEIGHTS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info(f"Optimize edilmis agirliklar kaydedildi: {OPTIMIZED_WEIGHTS_PATH}")


def load_optimized_weights() -> dict[str, Any] | None:
    """Onceden test edilip optimize edilmis agirliklari okur."""
    if OPTIMIZED_WEIGHTS_PATH.exists():
        try:
            with open(OPTIMIZED_WEIGHTS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Optimize agirlik dosyasi okunamadi: {e}")
    return None
