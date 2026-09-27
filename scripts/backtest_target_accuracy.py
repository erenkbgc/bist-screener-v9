#!/usr/bin/env python3
"""Hedef fiyat isabeti: emsal adil degeri 6 aylik getiriyi tahmin ediyor mu,
fiyat adil deger acigini ne hizla kapatiyor (alpha)?

    python scripts/backtest_target_accuracy.py

Canli uzun vade hedefi (core/targets.py::compute_long_term_target):
    beklenen = (P + alpha * (FV - P)) * (1 + k_e)^(180/365) - temettu
yani goreli beklenti  r_i - r_piyasa ~= alpha * (FV/P - 1). Burada:
  - FV: emsal bacagi (canlida 0.50 agirlik) nokta-zamanli yeniden kurulur
    (core/factor_backtest.py::peer_fair_value_ratio).
  - Test edilen alpha: her ay kesitsel OLS  (r6_i - ort) ~ b * (gap_i - ort),
    b'nin ortalamasi = gercek 6 aylik yakinsama orani. Newey-West lag 6
    (ust uste binen 6 aylik pencereler). Canli varsayim alpha = 0.32.
  - Kalibrasyon tablosu: acik dilimlerine gore tahmin (alpha*acik) vs gerceklesen.
Test EDILEMEYENLER:
  - DCF bacagi: panelde nakit akis tablosu yok.
  - Kalite bacagi: gerekceli PD/DD = ROE/k_e -> FV/P ~= (E/P)/k_e; siralamasi E/P
    ile ayni (faktor backtest'inde test edildi), seviyesi tarihsel k_e ister.
  - Holding NAV bacagi ve ML senaryo agirliklandirmasi (prob_up gecmisi yok).
Sinirlar: hayatta kalma yanliligi (bugunku liste), nominal TL, EV/FAVOK yerine
EV/EBIT. Gecmis getiri gelecegi garanti etmez.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import factor_backtest as fb  # noqa: E402

RESEARCH = ROOT / "data" / "research"
LIVE_ALPHA = 0.32
HOLDING_SECTORS = {"Holding"}  # canlida NAV bacagi; panelde yeniden kurulamaz


def load_panel(liq_drop: float) -> pd.DataFrame:
    f = pd.read_parquet(RESEARCH / "factors_monthly.parquet")
    q = pd.read_parquet(RESEARCH / "quarterly.parquet")[["ticker", "period", "fin_debt", "cash"]]
    f = f.merge(q.rename(columns={"period": "stmt_period"}), on=["ticker", "stmt_period"], how="left")
    f["net_debt"] = f["fin_debt"].fillna(0.0) - f["cash"].fillna(0.0)
    f = f[~f["sector"].isin(HOLDING_SECTORS)]
    out = []
    for dt, g in f.groupby("date"):
        g = g[g["tlvol60"].notna() & (g["tlvol60"] > 0)]
        g = g[g["tlvol60"] >= g["tlvol60"].quantile(liq_drop)]
        if len(g) < 30:
            continue
        g = g.join(fb.peer_fair_value_ratio(g))
        out.append(g)
    df = pd.concat(out, ignore_index=True)
    df["gap"] = df["fv_ratio"] - 1.0
    return df


def convergence(df: pd.DataFrame, ret: str, lags: int) -> dict:
    """Aylik kesitsel egim: (r - ort) ~ b (gap - ort). b = kapanan acik orani."""
    slopes, ics, n_names = {}, {}, []
    for dt, g in df[["date", "gap", ret]].dropna().groupby("date"):
        if len(g) < 30:
            continue
        x = g["gap"].clip(g["gap"].quantile(0.01), g["gap"].quantile(0.99))
        y = g[ret].clip(g[ret].quantile(0.01), g[ret].quantile(0.99))
        x, y = x - x.mean(), y - y.mean()
        if (x ** 2).sum() > 0:
            slopes[dt] = (x * y).sum() / (x ** 2).sum()
            ics[dt] = g["gap"].rank().corr(g[ret].rank())
            n_names.append(len(g))
    b, b_t, n = fb.newey_west_t(pd.Series(slopes), lags)
    ic, ic_t, _ = fb.newey_west_t(pd.Series(ics), lags)
    return {"alpha": round(b, 3), "alpha_t": round(b_t, 2), "ic": round(ic, 4), "ic_t": round(ic_t, 2),
            "months": n, "median_names": int(np.median(n_names)) if n_names else 0}


def calibration(df: pd.DataFrame, alpha: float) -> pd.DataFrame:
    d = df[["date", "gap", "fwd_ret_6m"]].dropna().copy()
    d["excess"] = d["fwd_ret_6m"] - d.groupby("date")["fwd_ret_6m"].transform("mean")
    # getiri dagilimi saga carpik: ortalamayi gecen hisse orani ~%37; %50 tabani icin medyan
    d["beat_median"] = d["fwd_ret_6m"] > d.groupby("date")["fwd_ret_6m"].transform("median")
    d["pred"] = alpha * (d["gap"] - d.groupby("date")["gap"].transform("mean"))
    d["q"] = d.groupby("date")["gap"].transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False))
    t = d.groupby("q").agg(gap_pct=("gap", "mean"), predicted_excess_pct=("pred", "mean"),
                           realized_excess_pct=("excess", "mean"),
                           beat_median_pct=("beat_median", "mean"), n=("gap", "size"))
    for c in ("gap_pct", "predicted_excess_pct", "realized_excess_pct", "beat_median_pct"):
        t[c] = (100 * t[c]).round(1)
    t.index = [f"Q{i + 1}" for i in t.index]
    return t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liq-drop", type=float, default=0.3)
    ap.add_argument("--split", default="2021-01-01")
    args = ap.parse_args()

    df = load_panel(args.liq_drop)
    cov = df["fv_ratio"].notna().mean()
    split = pd.Timestamp(args.split)
    print(f"Panel: {df['ticker'].nunique()} hisse (holding haric), {df['date'].min().date()} .. "
          f"{df['date'].max().date()}; emsal adil degeri hesaplanabilen satir %{100 * cov:.0f}; "
          f"medyan acik (FV/P-1) %{100 * df['gap'].median():.1f}\n")

    rows = []
    for label, m in (("tam", df["date"] >= "2013"),
                     ("2016-2020", (df["date"] >= "2016") & (df["date"] < split)),
                     ("2021-2026", df["date"] >= split)):
        sub = df[m]
        r6 = convergence(sub, "fwd_ret_6m", lags=6)
        r1 = convergence(sub, "fwd_ret_1m", lags=1)
        rows.append({"donem": label, "alpha_6m": r6["alpha"], "alpha_6m_t": r6["alpha_t"],
                     "ic_6m": r6["ic"], "ic_6m_t": r6["ic_t"], "ic_1m": r1["ic"], "ic_1m_t": r1["ic_t"],
                     "ay": r6["months"], "medyan_hisse": r6["median_names"]})
    res = pd.DataFrame(rows)
    full_alpha = res.iloc[0]["alpha_6m"]
    cal_live = calibration(df, LIVE_ALPHA)
    cal_emp = calibration(df, full_alpha)

    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print("Adil deger acigi -> gerceklesen getiri (piyasa ortalamasina gore):")
        print(res.to_string(index=False))
        print(f"\nKalibrasyon, canli alpha={LIVE_ALPHA} (acik beslileri, 6 ay):")
        print(cal_live.to_string())
        print(f"\nKalibrasyon, gozlenen alpha={full_alpha}:")
        print(cal_emp[["predicted_excess_pct", "realized_excess_pct"]].to_string())

    out = ROOT / "data" / "reports" / f"backtest_target_accuracy_{date.today().isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "live_alpha": LIVE_ALPHA, "liq_drop": args.liq_drop, "split": args.split,
        "coverage": round(float(cov), 3), "convergence": rows,
        "calibration_live_alpha": cal_live.reset_index(names="quintile").to_dict("records"),
    }, ensure_ascii=False, indent=2, default=lambda x: None if isinstance(x, float) and math.isnan(x) else str(x)),
        encoding="utf-8")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
