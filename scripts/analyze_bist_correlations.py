"""BIST 100 Korelasyon ve Beta Analiz Motoru.

Bu script, Borsa Istanbul (XU100) ile farkli sektorlerdeki onemli hisselerin
gunluk getiri serilerini karsilastirarak su metrikleri hesaplar:
  1. Pearson Korelasyonu (r): Yon birlikteligi derecesi
  2. Beta (beta): Piyasa duyarliligi / kaldiraci (Cov(Ri, Rm) / Var(Rm))
  3. R-Kare (R^2): Hissenin fiyat hareketinin ne kadarinin endeks tarafindan aciklandigi
  4. Asimetrik Beta (Upside Beta vs. Downside Beta):
     - Downside Beta: Endeks duserken hissenin dusus katsayisi
     - Upside Beta: Endeks yukselirken hissenin artis katsayisi
  5. Sektorel Ortalama Beta ve Korelasyonlar
"""
import time
import argparse
import numpy as np
import pandas as pd
import borsapy as bp

SECTORS = {
    "Bankacilik": ["AKBNK", "GARAN", "ISCTR", "YKBNK", "HALKB", "VAKBN"],
    "Holding": ["KCHOL", "SAHOL", "DOHOL", "ALARK"],
    "Sanayi & Uretim": ["EREGL", "SISE", "FROTO", "TOASO", "ARCLK"],
    "Enerji & Rafineri": ["TUPRS", "AYGAZ", "AKSEN", "ENJSA"],
    "Havacilik & Ulastirma": ["THYAO", "PGSUS", "TAVHL"],
    "Perakende & Tuketime Dayali": ["BIMAS", "MGROS", "SOKM", "CCOLA"],
    "Savunma & Teknoloji": ["ASELS", "LOGO"],
    "Telekomunikasyon": ["TCELL", "TTKOM"],
    "Gayrimenkul (GYO)": ["EKGYO"],
    "Madencilik & Emtia": ["KOZAL"],
    "Yuksek Beta / Buyume": ["ASTOR", "KONTR", "YEOTK"],
}


def fetch_series(symbol: str, is_index: bool = False, period: str = "6mo", retries: int = 3) -> pd.Series | None:
    for attempt in range(retries):
        try:
            if is_index:
                obj = bp.Index(symbol)
                hist = obj.history(period=period)
            else:
                obj = bp.Ticker(symbol)
                hist = obj.history(period=period, adjust=False)
            if hist is not None and not hist.empty and "Close" in hist.columns:
                s = hist["Close"].copy()
                s.index = pd.to_datetime(s.index).date
                return s
        except Exception as e:
            time.sleep(0.5 * (attempt + 1))
    return None


def run_analysis(period: str = "6mo", min_obs: int = 30) -> pd.DataFrame:
    print(f"[*] XU100 endeks verisi cekiliyor (periyot: {period})...")
    idx_close = fetch_series("XU100", is_index=True, period=period)
    if idx_close is None or len(idx_close) < min_obs:
        raise RuntimeError("XU100 endeks verisi alinamadi!")
    idx_ret = idx_close.pct_change().dropna()

    results = []
    print("[*] Sektor hisseleri inceleniyor...")

    for sector, tickers in SECTORS.items():
        for t in tickers:
            time.sleep(0.15)  # Nazik istek araligi
            s_close = fetch_series(t, is_index=False, period=period)
            if s_close is None or len(s_close) < min_obs:
                print(f"  [-] {t} ({sector}): Yetersiz veri veya hata.")
                continue

            s_ret = s_close.pct_change().dropna()
            df = pd.DataFrame({"stock": s_ret, "index": idx_ret}).dropna()
            n = len(df)
            if n < min_obs:
                continue

            r = float(df["stock"].corr(df["index"]))
            cov_mat = np.cov(df["stock"], df["index"])
            var_idx = cov_mat[1][1]
            cov = cov_mat[0][1]
            beta = float(cov / var_idx) if var_idx > 0 else 0.0
            r_squared = (r ** 2)

            # Yilliklandirilmis volatilite (252 is gunu)
            ann_vol_stock = float(df["stock"].std() * np.sqrt(252) * 100)
            ann_vol_idx = float(df["index"].std() * np.sqrt(252) * 100)

            # Downside Beta (Endeks eksi gunlerde)
            down_df = df[df["index"] < 0]
            if len(down_df) >= 10:
                c_down = np.cov(down_df["stock"], down_df["index"])
                var_down = c_down[1][1]
                beta_down = float(c_down[0][1] / var_down) if var_down > 0 else beta
            else:
                beta_down = beta

            # Upside Beta (Endeks arti gunlerde)
            up_df = df[df["index"] > 0]
            if len(up_df) >= 10:
                c_up = np.cov(up_df["stock"], up_df["index"])
                var_up = c_up[1][1]
                beta_up = float(c_up[0][1] / var_up) if var_up > 0 else beta
            else:
                beta_up = beta

            # Asimetri: beta_down - beta_up (>0 ise duserken daha cok dusuyor)
            downside_risk_bias = beta_down - beta_up

            results.append({
                "ticker": t,
                "sector": sector,
                "correlation": round(r, 3),
                "beta": round(beta, 2),
                "r_squared": round(r_squared, 3),
                "beta_down": round(beta_down, 2),
                "beta_up": round(beta_up, 2),
                "downside_bias": round(downside_risk_bias, 2),
                "annual_vol_pct": round(ann_vol_stock, 1),
                "obs_count": n,
            })
            print(f"  [+] {t:6s} ({sector:20s}): r={r:+.2f}, beta={beta:.2f}, down_beta={beta_down:.2f}, up_beta={beta_up:.2f}")

    res_df = pd.DataFrame(results)
    return res_df


def main():
    parser = argparse.ArgumentParser(description="BIST 100 Correlation and Beta Analysis")
    parser.add_argument("--period", default="6mo", help="Data period (3mo, 6mo, 1y)")
    args = parser.parse_args()

    df = run_analysis(period=args.period)
    if df.empty:
        print("Hicbir hisse verisi hesaplanamadi.")
        return

    print("\n" + "=" * 80)
    print("           BIST 100 KORELASYON VE BETA RAPORU (GENEL)")
    print("=" * 80)
    print(df.sort_values(by="correlation", ascending=False).to_string(index=False))

    print("\n" + "=" * 80)
    print("           SEKTÖREL ORTALAMALAR")
    print("=" * 80)
    sec_summary = df.groupby("sector").agg({
        "correlation": "mean",
        "beta": "mean",
        "beta_down": "mean",
        "beta_up": "mean",
        "annual_vol_pct": "mean",
        "ticker": "count"
    }).rename(columns={"ticker": "hisse_sayisi"}).sort_values(by="beta", ascending=False)
    print(sec_summary.round(2).to_string())

    # CSV kaydi
    out_path = "data/bist_correlations_latest.csv"
    df.to_csv(out_path, index=False)
    print(f"\n[OK] Sonuclar '{out_path}' dosyasina kaydedildi.")


if __name__ == "__main__":
    main()
