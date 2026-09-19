"""BIST 100 Trend Tahmin ve Walk-Forward Geriye Test Scripti."""
import borsapy as bp
import pandas as pd
from core.trend_forecaster import (
    compute_indicators,
    TrendForecastingEngine,
    walk_forward_backtest,
)


def main():
    print("=" * 80)
    print("       BIST 100 TREND & YÖN TAHMİNİ (MAKİNE ÖĞRENMESİ & QUANT MODELİ)")
    print("=" * 80)
    print("[*] XU100 tarihsel verisi cekiliyor (5 yillik derinlik)...")
    idx = bp.Index("XU100").history(period="5y")
    if idx is None or idx.empty:
        print("[-] XU100 verisi alinamadi!")
        return

    print(f"[+] Toplam {len(idx)} gunluk bar alindi ({idx.index[0].strftime('%Y-%m-%d')} -> {idx.index[-1].strftime('%Y-%m-%d')}).")

    # 1. Gostergeleri hesapla
    df_feat = compute_indicators(idx)

    # 2. Canli / En Guncel Durum Tahmini
    print("\n" + "-" * 80)
    print("1. ANLIK BIST 100 TREND & REJİM TAHMİNİ (EN GÜNCEL BAR)")
    print("-" * 80)
    engine = TrendForecastingEngine(horizon=10)
    engine.fit(df_feat)
    current_forecast = engine.predict_current(df_feat)

    print(f"Tarih             : {current_forecast['as_of_date']}")
    print(f"XU100 Kapanis     : {current_forecast['close']:.2f}")
    print(f"Tahmin Ufku       : {current_forecast['horizon_days']} Islem Gunu (~2 Hafta)")
    print(f"Yukari Olasiligi  : %{current_forecast['prob_up'] * 100:.1f}")
    print(f"Trend Skoru       : {current_forecast['trend_score']} / 100")
    print(f"Tespit Edilen Rejim: {current_forecast['regime']}")
    print(f"Onerilen Aksiyon  : {current_forecast['recommended_stance']}")
    print("\nKritik Gostergeler:")
    for k, v in current_forecast["indicators"].items():
        print(f"  - {k:28s}: {v}")
    print("\nModele En Cok Yon Veren Onculer (Feature Importance):")
    for k, v in current_forecast["top_drivers"].items():
        print(f"  - {k:28s}: %{v * 100:.1f}")

    # 3. Walk-Forward Backtest
    print("\n" + "-" * 80)
    print("2. WALK-FORWARD OUT-OF-SAMPLE GERİYE DÖNÜK DOĞRULAMA (BACKTEST)")
    print("-" * 80)
    print("[*] Egitim penceresi: 500 bar (~2 yil), test adimi: 40 bar... (Sifir Bilgi Sizintisi)")
    bt_results = walk_forward_backtest(idx, horizon=10, train_window=500, step=40)

    print(f"Test Edilen Donem Sayisi       : {bt_results['samples_count']} islem gunu (Out-of-sample)")
    print(f"Yon Tahmin Dogrulugu (Accuracy) : %{bt_results['accuracy_pct']}")
    print(f"Yukselis Tahmin Guveni (Prec.)  : %{bt_results['bullish_precision_pct']}")
    print(f"Strateji Toplam Getirisi (Model): %{bt_results['strategy_cumulative_ret_pct']}")
    print(f"Endeks Al-Tut Getirisi (B&H)    : %{bt_results['market_cumulative_ret_pct']}")
    print(f"Strateji Yillik Bilesik (CAGR)  : %{bt_results['strategy_cagr_pct']}")
    print(f"Endeks Yillik Bilesik (CAGR)    : %{bt_results['market_cagr_pct']}")
    print(f"Strateji Maks. Dusus (MaxDD)    : %{bt_results['strategy_max_drawdown_pct']}")
    print(f"Endeks Maks. Dusus (MaxDD)      : %{bt_results['market_max_drawdown_pct']}")
    print(f"Strateji Yillik Volatilitesi    : %{bt_results['strategy_annual_vol_pct']}")
    print(f"Endeks Yillik Volatilitesi      : %{bt_results['market_annual_vol_pct']}")
    print(f"Strateji Sharpe Orani           : {bt_results['strategy_sharpe']}")
    print(f"Endeks Sharpe Orani             : {bt_results['market_sharpe']}")
    print(f"Modelin Alfa / Fazla Getirisi   : %{bt_results['outperformance_pct']:+.2f}")
    print("=" * 80)



if __name__ == "__main__":
    main()
