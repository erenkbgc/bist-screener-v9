"""BIST 100 Trend ve Yon Tahmin Motoru (Quant Machine Learning & Regime Forecasting).

Bu modul, akademik literaturdeki bulgulara (López de Prado, Dogan & Buyukkor,
Akbulut & Adem) dayanarak BIST 100 endeksinin kisa ve orta vadeli trendini
ve yonunu tahmin eder.

Temel ozellikler:
  1. Zengin Oznitelik Muhendisligi (Trend, Momentum, Volatilite, Hacim, Donusumler)
  2. Makine Ogrenmesi Tabanli Olasiliksal Yon Tahmini (Random Forest & Logistic Ensemble)
  3. Rejim Siniflandirmasi (STRONG_BULL, MILD_BULL, NEUTRAL, CORRECTION, OVERSOLD_REVERSAL)
  4. Lookahead-Bias Olmayan Walk-Forward (Zaman Pencereli) Geriye Test (Backtest)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """XU100 gunluk OHLCV verisinden zengin teknik ve makro-duyarli ozellikler uretir."""
    data = df.copy()
    close = data["Close"]
    volume = data["Volume"]

    # 1. Hareketli Ortalama Rasyolari (Trend & Mesafe)
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()

    data["dist_sma20"] = (close / sma20) - 1.0
    data["dist_sma50"] = (close / sma50) - 1.0
    data["dist_sma200"] = (close / sma200) - 1.0
    data["sma20_sma50_ratio"] = (sma20 / sma50) - 1.0
    data["sma50_sma200_ratio"] = (sma50 / sma200) - 1.0

    # 2. Momentum & Getiri Hizi
    data["ret_5d"] = close.pct_change(5)
    data["ret_10d"] = close.pct_change(10)
    data["ret_20d"] = close.pct_change(20)
    data["ret_60d"] = close.pct_change(60)

    # 3. RSI (14)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    data["rsi_14"] = 100 - (100 / (1 + rs))
    data["rsi_norm"] = (data["rsi_14"] - 50.0) / 50.0  # -1 ile +1 arasina normalize

    # 4. MACD & Sinyal
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    data["macd_hist_norm"] = (macd_line - macd_signal) / close

    # 5. Volatilite & Bantlar
    ret_1d = close.pct_change()
    data["realized_vol_20d"] = ret_1d.rolling(20).std() * np.sqrt(252)
    data["realized_vol_60d"] = ret_1d.rolling(60).std() * np.sqrt(252)
    data["vol_ratio"] = data["realized_vol_20d"] / data["realized_vol_60d"].replace(0, np.nan)

    std20 = close.rolling(20).std()
    upper_bb = sma20 + 2 * std20
    lower_bb = sma20 - 2 * std20
    data["bb_pct_b"] = (close - lower_bb) / (upper_bb - lower_bb).replace(0, np.nan)

    # 6. Hacim Dinamikleri
    vol_sma20 = volume.rolling(20).mean()
    data["volume_ratio_20d"] = volume / vol_sma20.replace(0, np.nan)
    data["volume_ret_5d"] = volume.pct_change(5).clip(lower=-2, upper=5)

    # 7. 52 Haftalik (252 Gunluk) Zirveden Geri Cekilme (Drawdown)
    high_252 = close.rolling(252).max()
    low_252 = close.rolling(252).min()
    data["drawdown_from_52w_high"] = (close / high_252) - 1.0
    data["distance_from_52w_low"] = (close / low_252) - 1.0

    return data


FEATURE_COLUMNS = [
    "dist_sma20",
    "dist_sma50",
    "dist_sma200",
    "sma20_sma50_ratio",
    "sma50_sma200_ratio",
    "ret_5d",
    "ret_10d",
    "ret_20d",
    "ret_60d",
    "rsi_norm",
    "macd_hist_norm",
    "realized_vol_20d",
    "vol_ratio",
    "bb_pct_b",
    "volume_ratio_20d",
    "drawdown_from_52w_high",
    "distance_from_52w_low",
]


class TrendForecastingEngine:
    """Makine Ogrenmesi Tabanli BIST Trend ve Yon Siniflandirici."""

    def __init__(self, horizon: int = 10, random_state: int = 42):
        self.horizon = horizon
        self.random_state = random_state
        self.scaler = StandardScaler()
        self.rf = RandomForestClassifier(
            n_estimators=100,
            max_depth=4,
            min_samples_leaf=15,
            random_state=random_state,
        )
        self.lr = LogisticRegression(C=0.1, max_iter=500, random_state=random_state)
        self.is_fitted = False
        self.feature_importances_: dict[str, float] = {}
        self.ensemble_weights_: tuple[float, float] = (0.50, 0.50)

    def fit(self, df_with_features: pd.DataFrame) -> TrendForecastingEngine:
        """Ileriye donuk getiriye (horizon gun sonrasi) gore modeli egitir."""
        from sklearn.model_selection import TimeSeriesSplit
        from core.weight_optimizer import optimize_ensemble_weights

        clean_df = df_with_features.dropna(subset=FEATURE_COLUMNS).copy()
        # Hedef: Gelecek H gunun getirisi pozitif mi?
        clean_df["fwd_ret"] = clean_df["Close"].shift(-self.horizon) / clean_df["Close"] - 1.0
        train_data = clean_df.dropna(subset=["fwd_ret"]).copy()

        if len(train_data) < 100:
            raise ValueError(f"Egitim icin yetersiz veri ({len(train_data)} gozlem). En az 100 bar gerekir.")

        X = train_data[FEATURE_COLUMNS].values
        y = (train_data["fwd_ret"] > 0).astype(int).values

        X_scaled = self.scaler.fit_transform(X)

        # Out-of-fold cross validation ile optimum topluluk agirliklarini cozer (sifir manuel agirlik)
        tscv = TimeSeriesSplit(n_splits=3)
        oof_rf, oof_lr, oof_y = [], [], []
        for tr_idx, val_idx in tscv.split(X_scaled):
            rf_f = RandomForestClassifier(n_estimators=40, max_depth=4, min_samples_leaf=15, random_state=self.random_state)
            lr_f = LogisticRegression(C=0.1, max_iter=500, random_state=self.random_state)
            rf_f.fit(X_scaled[tr_idx], y[tr_idx])
            lr_f.fit(X_scaled[tr_idx], y[tr_idx])
            oof_rf.extend(rf_f.predict_proba(X_scaled[val_idx])[:, 1])
            oof_lr.extend(lr_f.predict_proba(X_scaled[val_idx])[:, 1])
            oof_y.extend(y[val_idx])

        if oof_y:
            self.ensemble_weights_ = optimize_ensemble_weights(np.array(oof_y), np.array(oof_rf), np.array(oof_lr))
        else:
            self.ensemble_weights_ = (0.50, 0.50)

        self.rf.fit(X_scaled, y)
        self.lr.fit(X_scaled, y)
        self.is_fitted = True

        # Oznitelik onemlerini kaydet
        importances = self.rf.feature_importances_
        self.feature_importances_ = {
            col: round(float(imp), 4)
            for col, imp in sorted(zip(FEATURE_COLUMNS, importances), key=lambda x: x[1], reverse=True)
        }
        return self

    def predict_current(self, df_with_features: pd.DataFrame) -> dict:
        """En son guncel bara gore trend tahminini ve rejimini cikarir."""
        if not self.is_fitted:
            raise RuntimeError("Model henuz egitilmedi. Once fit() calistirin.")

        last_row = df_with_features.dropna(subset=FEATURE_COLUMNS).iloc[-1]
        x = last_row[FEATURE_COLUMNS].values.reshape(1, -1)
        x_scaled = self.scaler.transform(x)

        p_rf = self.rf.predict_proba(x_scaled)[0][1]
        p_lr = self.lr.predict_proba(x_scaled)[0][1]
        # Optimize edilmis ensemble agirliklari (sifir manuel katsayi)
        w_rf, w_lr = getattr(self, "ensemble_weights_", (0.50, 0.50))
        prob_up = float(w_rf * p_rf + w_lr * p_lr)

        close = float(last_row["Close"])
        rsi = float(last_row["rsi_14"])
        dist_sma20 = float(last_row["dist_sma20"])
        dist_sma50 = float(last_row["dist_sma50"])
        dist_sma200 = float(last_row["dist_sma200"])

        # Rejim Tespiti
        # 1. Asiri Satim Tepkisi (Oversold Reversal)
        if rsi < 36.0 and dist_sma200 < 0.02 and dist_sma200 > -0.06:
            regime = "OVERSOLD_REVERSAL"
            stance = "SELECTIVE_BUY_DIP"
        elif prob_up >= 0.62 and dist_sma50 > -0.01:
            regime = "STRONG_BULL"
            stance = "AGGRESSIVE_HIGH_BETA"
        elif prob_up >= 0.52:
            regime = "MILD_BULL"
            stance = "MODERATE_LONG"
        elif prob_up < 0.40 and dist_sma50 < -0.03:
            regime = "STRONG_BEAR"
            stance = "DEFENSIVE_OR_CASH"
        else:
            regime = "CORRECTION_CHOPPY"
            stance = "DEFENSIVE_SELECTIVE"

        # -100 ile +100 arasi Trend Skoru
        trend_score = int(round((prob_up - 0.5) * 200))

        return {
            "as_of_date": str(last_row.name.date()) if hasattr(last_row.name, "date") else str(last_row.name),
            "close": close,
            "horizon_days": self.horizon,
            "prob_up": round(prob_up, 3),
            "trend_score": trend_score,
            "regime": regime,
            "recommended_stance": stance,
            "indicators": {
                "rsi_14": round(rsi, 1),
                "dist_sma20_pct": round(dist_sma20 * 100, 2),
                "dist_sma50_pct": round(dist_sma50 * 100, 2),
                "dist_sma200_pct": round(dist_sma200 * 100, 2),
                "realized_vol_20d_pct": round(float(last_row["realized_vol_20d"]) * 100, 1),
                "drawdown_from_52w_high_pct": round(float(last_row["drawdown_from_52w_high"]) * 100, 2),
            },
            "top_drivers": dict(list(self.feature_importances_.items())[:5]),
        }


def walk_forward_backtest(
    df: pd.DataFrame,
    horizon: int = 10,
    train_window: int = 500,
    step: int = 40,
) -> dict:
    """Gercekci Walk-Forward Out-of-Sample Geriye Test (Lookahead-Bias Icerilmez).

    train_window kadar bar uzerinde egitir, sonraki 'step' bar icin ileriye
    donuk tahmin yapar; pencereyi 'step' kadar kaydirip tum gecmis uzerinde
    test eder.
    """
    df_feat = compute_indicators(df).dropna(subset=FEATURE_COLUMNS).copy()
    df_feat["fwd_ret"] = df_feat["Close"].shift(-horizon) / df_feat["Close"] - 1.0
    valid_data = df_feat.dropna(subset=["fwd_ret"]).copy()

    total_len = len(valid_data)
    if total_len < train_window + step:
        raise ValueError("Yetersiz veri. Walk-forward icin en az train_window + step bar gerekir.")

    predictions = []

    for start_idx in range(0, total_len - train_window, step):
        train_slice = valid_data.iloc[start_idx : start_idx + train_window]
        test_slice = valid_data.iloc[start_idx + train_window : start_idx + train_window + step]

        if test_slice.empty:
            break

        model = TrendForecastingEngine(horizon=horizon)
        model.fit(train_slice)

        X_test = test_slice[FEATURE_COLUMNS].values
        X_test_scaled = model.scaler.transform(X_test)
        p_rf = model.rf.predict_proba(X_test_scaled)[:, 1]
        p_lr = model.lr.predict_proba(X_test_scaled)[:, 1]
        w_rf, w_lr = getattr(model, "ensemble_weights_", (0.50, 0.50))
        probs = w_rf * p_rf + w_lr * p_lr

        for i, idx_val in enumerate(test_slice.index):
            p = float(probs[i])
            actual_ret = float(test_slice.iloc[i]["fwd_ret"])
            actual_dir = 1 if actual_ret > 0 else 0
            pred_dir = 1 if p >= 0.50 else 0

            predictions.append({
                "date": idx_val,
                "prob_up": p,
                "pred_dir": pred_dir,
                "actual_dir": actual_dir,
                "actual_ret_horizon": actual_ret,
                "is_correct": int(pred_dir == actual_dir),
            })

    res_df = pd.DataFrame(predictions)
    if res_df.empty:
        return {}

    # Gunluk getiri eslestirmesi (Sinyal gunu t ise, t+1 gunluk piyasa getirisini al)
    daily_rets = df["Close"].pct_change().dropna()
    res_df["daily_mkt_ret"] = res_df["date"].map(daily_rets).fillna(0.0)
    # Strateji: Bir onceki barin tahminine gore bugun piyasada ol veya olma (shift 1)
    res_df["strat_position"] = res_df["pred_dir"].shift(1).fillna(0)
    res_df["daily_strat_ret"] = res_df["strat_position"] * res_df["daily_mkt_ret"]

    accuracy = float(res_df["is_correct"].mean())
    win_cases = res_df[res_df["pred_dir"] == 1]
    precision = float((win_cases["actual_dir"] == 1).mean()) if len(win_cases) > 0 else 0.0

    # Bilesik Toplam Getiriler
    cum_mkt = (1.0 + res_df["daily_mkt_ret"]).cumprod()
    cum_strat = (1.0 + res_df["daily_strat_ret"]).cumprod()
    total_market_ret = float(cum_mkt.iloc[-1] - 1.0)
    total_strat_ret = float(cum_strat.iloc[-1] - 1.0)

    # Maksimum Dusus (Max Drawdown)
    mkt_dd = float(((cum_mkt - cum_mkt.cummax()) / cum_mkt.cummax()).min())
    strat_dd = float(((cum_strat - cum_strat.cummax()) / cum_strat.cummax()).min())

    # Yilliklandirilmis Volatilite ve Sharpe Orani (Risksiz oran varsayimi: %0 baz)
    strat_vol = float(res_df["daily_strat_ret"].std() * np.sqrt(252))
    market_vol = float(res_df["daily_mkt_ret"].std() * np.sqrt(252))
    strat_cagr = float((cum_strat.iloc[-1] ** (252 / len(res_df))) - 1.0) if cum_strat.iloc[-1] > 0 else 0.0
    market_cagr = float((cum_mkt.iloc[-1] ** (252 / len(res_df))) - 1.0) if cum_mkt.iloc[-1] > 0 else 0.0
    strat_sharpe = strat_cagr / strat_vol if strat_vol > 0 else 0.0
    market_sharpe = market_cagr / market_vol if market_vol > 0 else 0.0

    return {
        "samples_count": len(res_df),
        "accuracy_pct": round(accuracy * 100, 2),
        "bullish_precision_pct": round(precision * 100, 2),
        "strategy_cumulative_ret_pct": round(total_strat_ret * 100, 2),
        "market_cumulative_ret_pct": round(total_market_ret * 100, 2),
        "strategy_cagr_pct": round(strat_cagr * 100, 2),
        "market_cagr_pct": round(market_cagr * 100, 2),
        "strategy_max_drawdown_pct": round(strat_dd * 100, 2),
        "market_max_drawdown_pct": round(mkt_dd * 100, 2),
        "strategy_annual_vol_pct": round(strat_vol * 100, 2),
        "market_annual_vol_pct": round(market_vol * 100, 2),
        "strategy_sharpe": round(strat_sharpe, 2),
        "market_sharpe": round(market_sharpe, 2),
        "outperformance_pct": round((total_strat_ret - total_market_ret) * 100, 2),
    }


def predict_market_regime(data: list[dict] | pd.DataFrame) -> dict:
    """XU100 veya endeks fiyat serisinden piyasa rejimini ve 10 gunluk yukselis olasiligini tahmin eder (Quant Level-Up Faz 1)."""
    if isinstance(data, list):
        if not data:
            return {
                "regime": "MILD_BULL",
                "prob_up": 0.50,
                "confidence": "insufficient_data",
                "risk_alert": "Veri yok, varsayilan rejim uygulandi.",
            }
        rows = []
        for r in data:
            c = r.get("close") or r.get("Close") or 100.0
            h = r.get("high") or r.get("High") or c
            l = r.get("low") or r.get("Low") or c
            o = r.get("open") or r.get("Open") or c
            v = r.get("volume") or r.get("Volume") or 1000000.0
            rows.append({"Open": float(o), "High": float(h), "Low": float(l), "Close": float(c), "Volume": float(v)})
        df = pd.DataFrame(rows)
    else:
        df = data.copy()

    if len(df) < 120:
        closes = df["Close"].values
        last_c = closes[-1]
        sma20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else float(last_c)
        regime = "MILD_BULL" if last_c >= sma20 else "CORRECTION_CHOPPY"
        return {
            "regime": regime,
            "prob_up": 0.55 if last_c >= sma20 else 0.45,
            "confidence": "heuristic_short_history",
            "close": float(last_c),
            "indicators": {"dist_sma20_pct": round(float((last_c / sma20 - 1.0) * 100), 2)},
        }

    feat_df = compute_indicators(df)
    clean_df = feat_df.dropna(subset=FEATURE_COLUMNS)
    if len(clean_df) < 100:
        closes = df["Close"].values
        last_c = closes[-1]
        sma20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else float(last_c)
        regime = "MILD_BULL" if last_c >= sma20 else "CORRECTION_CHOPPY"
        return {
            "regime": regime,
            "prob_up": 0.55 if last_c >= sma20 else 0.45,
            "confidence": "heuristic_limited_bars",
            "close": float(last_c),
            "indicators": {"dist_sma20_pct": round(float((last_c / sma20 - 1.0) * 100), 2)},
        }

    engine = TrendForecastingEngine(horizon=10)
    engine.fit(feat_df)
    return engine.predict_current(feat_df)



