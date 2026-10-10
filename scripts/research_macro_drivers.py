"""BIST neye gore artiyor/dusuyor: on-kayitli makro surucu ve ongoru calismasi.

On-kayit: docs/research/macro_drivers_preregistration.md (2026-10-10, sonuclar
gorulmeden once commit edildi). Esikler ve degisken listesi orada sabittir;
bu script onlari degistirmez.

A. Aciklama (ayni ay): r_usd ~ global/yerel makro degiskenler, Newey-West,
   Shapley R^2 payi, iki alt donemde isaret kararliligi.
B. Ongoru (t sonunda bilinen -> t+1 / t+1..t+12): tek degiskenli ongoru
   regresyonlari, genisleyen pencere OOS R^2 (Campbell-Thompson 2008),
   Clark-West (2007) testi, Bonferroni.

Kullanim:
    python scripts/research_macro_drivers.py            # onbellekten (yoksa indirir)
    python scripts/research_macro_drivers.py --refresh  # verileri yeniden indir
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.factor_backtest import newey_west_t  # noqa: E402

RAW_PATH = ROOT / "data" / "research" / "macro_monthly.parquet"
PANEL_PATH = ROOT / "data" / "research" / "factors_monthly.parquet"
REPORTS = ROOT / "data" / "reports"

YF = {"xu100": "XU100.IS", "usdtry": "USDTRY=X", "eem": "EEM", "spx": "^GSPC", "vix": "^VIX",
      "us10y": "^TNX", "dxy": "DX-Y.NYB", "brent": "BZ=F", "gold": "GC=F"}

START = "2005-01-31"
T_HURDLE = 3.0
SPLIT = "2015-12-31"
MIN_TRAIN = 84
SWITCH_COST = 0.002

A_VARS = {"A1": "eem_ret", "A2": "dlog_vix", "A3": "d_us10y", "A4": "dxy_ret",
          "A5": "brent_ret", "A6": "gold_ret", "A7": "d_cpi_yoy", "A8": "d_real_rate"}
A_POLICY_VARS = {"A7", "A8"}
B_VARS = {"P1": "real_rate_lag", "P2": "d3_real_rate_lag", "P3": "usdtry_12m", "P4": "trend_10m",
          "P5": "mom_12m", "P6": "mkt_ep_real_lag", "P7": "log_vix", "P8": "eem_12m", "P9": "d12_cpi_lag"}
HORIZONS = [1, 12]


# ---------------------------------------------------------------------------
# veri
# ---------------------------------------------------------------------------

def _month_end(s: pd.Series) -> pd.Series:
    s = s.copy()
    s.index = pd.to_datetime(s.index).tz_localize(None) if getattr(s.index, "tz", None) else pd.to_datetime(s.index)
    return s.resample("ME").last()


def download() -> pd.DataFrame:
    import borsapy as bp
    import yfinance as yf

    cols = {}
    for name, tk in YF.items():
        h = yf.Ticker(tk).history(period="max", interval="1d", auto_adjust=True)
        if h.empty:
            raise RuntimeError(f"{tk} bos dondu")
        cols[name] = _month_end(h["Close"])
    df = pd.DataFrame(cols)

    infl = bp.Inflation().tufe()
    infl.index = pd.to_datetime(infl.index)
    df["cpi_yoy"] = _month_end(infl["YearlyInflation"].astype(float).sort_index())
    df["cpi_mom"] = _month_end(infl["MonthlyInflation"].astype(float).sort_index())

    pol = bp.TCMB().history("policy")
    pol.index = pd.to_datetime(pol.index)
    pol = pol["lending"].astype(float).sort_index()
    # karar tarihli seri: ay sonuna ileri tasinir (karar gununden itibaren gecerli)
    daily = pol.reindex(pd.date_range(pol.index.min(), df.index.max(), freq="D")).ffill()
    df["policy"] = daily.resample("ME").last()
    df["policy_last_decision"] = pol.index.max().date().isoformat()
    return df


def load(refresh: bool) -> pd.DataFrame:
    if refresh or not RAW_PATH.exists():
        df = download()
        RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(RAW_PATH)
    return pd.read_parquet(RAW_PATH)


def market_ep() -> pd.Series | None:
    """Arastirma panelinden (PIT) aylik medyan E/P (TL, nominal)."""
    if not PANEL_PATH.exists():
        return None
    f = pd.read_parquet(PANEL_PATH, columns=["date", "ep"])
    s = f.groupby("date")["ep"].median()
    s.index = pd.to_datetime(s.index)
    return s.resample("ME").last()


def build(raw: pd.DataFrame) -> pd.DataFrame:
    d = raw.copy()
    # tamamlanmamis son ay (ay sonu bugunden sonra) dislanir
    d = d[(d.index >= START) & (d.index <= pd.Timestamp(date.today()))]
    xu_usd = d["xu100"] / d["usdtry"]
    out = pd.DataFrame(index=d.index)
    out["r_usd"] = np.log(xu_usd).diff()
    out["r_tl"] = np.log(d["xu100"]).diff()
    out["dlog_usdtry"] = np.log(d["usdtry"]).diff()
    # A: ayni ay
    out["eem_ret"] = np.log(d["eem"]).diff()
    out["dlog_vix"] = np.log(d["vix"]).diff()
    out["d_us10y"] = d["us10y"].diff()
    out["dxy_ret"] = np.log(d["dxy"]).diff()
    out["brent_ret"] = np.log(d["brent"]).diff()
    out["gold_ret"] = np.log(d["gold"]).diff()
    out["d_cpi_yoy"] = d["cpi_yoy"].diff()
    real = d["policy"] - d["cpi_yoy"]
    out["d_real_rate"] = real.diff()
    # B: t sonunda bilinen; TUFE bir ay gecikmeli (yayin gecikmesi)
    real_lag = d["policy"] - d["cpi_yoy"].shift(1)
    out["real_rate_lag"] = real_lag
    out["d3_real_rate_lag"] = real_lag.diff(3)
    out["usdtry_12m"] = np.log(d["usdtry"]).diff(12)
    out["trend_10m"] = np.log(xu_usd / xu_usd.rolling(10).mean())
    out["mom_12m"] = np.log(xu_usd).diff(12)
    ep = market_ep()
    if ep is not None:
        out["mkt_ep_real_lag"] = ep.reindex(out.index) * 100 - d["cpi_yoy"].shift(1)
    else:
        out["mkt_ep_real_lag"] = np.nan
    out["log_vix"] = np.log(d["vix"])
    out["eem_12m"] = np.log(d["eem"]).diff(12)
    out["d12_cpi_lag"] = d["cpi_yoy"].shift(1).diff(12)
    # hedefler
    out["y_h1"] = out["r_usd"].shift(-1)
    out["y_h12"] = out["r_usd"].rolling(12).sum().shift(-12)
    return out


# ---------------------------------------------------------------------------
# A: aciklama
# ---------------------------------------------------------------------------

def ols_hac(y: pd.Series, X: pd.DataFrame, lags: int):
    Xc = sm.add_constant(X)
    return sm.OLS(y, Xc).fit(cov_type="HAC", cov_kwds={"maxlags": lags})


def shapley_r2(y: pd.Series, X: pd.DataFrame) -> dict[str, float]:
    cols = list(X.columns)
    cache: dict[frozenset, float] = {frozenset(): 0.0}

    def r2(sub: frozenset) -> float:
        if sub not in cache:
            cache[sub] = sm.OLS(y, sm.add_constant(X[list(sub)])).fit().rsquared
        return cache[sub]

    k = len(cols)
    out = {}
    for c in cols:
        others = [o for o in cols if o != c]
        tot = 0.0
        for m in range(k):
            w = math.factorial(m) * math.factorial(k - m - 1) / math.factorial(k)
            for sub in itertools.combinations(others, m):
                s = frozenset(sub)
                tot += w * (r2(s | {c}) - r2(s))
        out[c] = tot
    return out


def part_a(df: pd.DataFrame) -> dict:
    results = {}
    for label, ids in (("global_2005", [i for i in A_VARS if i not in A_POLICY_VARS]),
                       ("all_2010", list(A_VARS))):
        cols = [A_VARS[i] for i in ids]
        sub = df[["r_usd"] + cols].dropna()
        y, X = sub["r_usd"], sub[cols]
        full = ols_hac(y, X, 3)
        halves = {}
        for name, mask in (("first", sub.index <= SPLIT), ("second", sub.index > SPLIT)):
            halves[name] = ols_hac(y[mask], X[mask], 3)
        shap = shapley_r2(y, X)
        # standartlastirilmis beta: 1 std degisken degisimi -> r_usd std cinsinden
        rows = {}
        for i, c in zip(ids, cols):
            same_sign = np.sign(halves["first"].params[c]) == np.sign(halves["second"].params[c])
            rows[i] = {
                "variable": c,
                "beta": float(full.params[c]),
                "t_nw": float(full.tvalues[c]),
                "std_beta": float(full.params[c] * X[c].std() / y.std()),
                "shapley_r2": float(shap[c]),
                "beta_first_half": float(halves["first"].params[c]),
                "t_first_half": float(halves["first"].tvalues[c]),
                "beta_second_half": float(halves["second"].params[c]),
                "t_second_half": float(halves["second"].tvalues[c]),
                "passes": bool(abs(full.tvalues[c]) > T_HURDLE and same_sign),
            }
        # kayan 36 aylik betalar (bilgi): yalnizca ozet istatistik
        roll = {}
        for c in cols:
            b = []
            for end in range(36, len(sub) + 1):
                w = sub.iloc[end - 36:end]
                b.append(sm.OLS(w["r_usd"], sm.add_constant(w[cols])).fit().params[c])
            roll[c] = {"min": float(np.min(b)), "median": float(np.median(b)), "max": float(np.max(b)),
                       "share_positive": float(np.mean(np.array(b) > 0))}
        results[label] = {
            "n_months": int(len(sub)), "start": str(sub.index.min().date()), "end": str(sub.index.max().date()),
            "r2": float(full.rsquared), "adj_r2": float(full.rsquared_adj),
            "r2_first_half": float(halves["first"].rsquared), "r2_second_half": float(halves["second"].rsquared),
            "variables": rows, "rolling_36m_beta": roll,
        }
    return results


def currency_decomposition(df: pd.DataFrame) -> dict:
    """r_tl = r_usd + dlog_usdtry (ozdeslik): nominal TL getirisinin ne kadari kur."""
    sub = df[["r_tl", "r_usd", "dlog_usdtry"]].dropna()
    cum = sub.sum()
    var_tl = sub["r_tl"].var()
    return {
        "start": str(sub.index.min().date()), "end": str(sub.index.max().date()),
        "cum_log_return_tl": float(cum["r_tl"]), "cum_log_return_usd": float(cum["r_usd"]),
        "cum_log_usdtry": float(cum["dlog_usdtry"]),
        "annualized_tl_pct": float((math.exp(cum["r_tl"] * 12 / len(sub)) - 1) * 100),
        "annualized_usd_pct": float((math.exp(cum["r_usd"] * 12 / len(sub)) - 1) * 100),
        "annualized_usdtry_pct": float((math.exp(cum["dlog_usdtry"] * 12 / len(sub)) - 1) * 100),
        "share_of_tl_variance_usd_part": float(sub["r_usd"].var() / var_tl),
        "share_of_tl_variance_fx_part": float(sub["dlog_usdtry"].var() / var_tl),
        "corr_usd_part_fx_part": float(sub["r_usd"].corr(sub["dlog_usdtry"])),
    }


# ---------------------------------------------------------------------------
# B: ongoru
# ---------------------------------------------------------------------------

def oos_test(x: pd.Series, y: pd.Series, h: int) -> dict:
    """Genisleyen pencere. t aninda tahmin icin yalnizca hedefi t'den once
    tamamen gerceklesmis gozlemler kullanilir (h>1'de son h-1 ay dislanir)."""
    sub = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    n = len(sub)
    fc_m, fc_b, actual, dates = [], [], [], []
    for i in range(MIN_TRAIN + h - 1, n):
        train = sub.iloc[: i - h + 1]
        if len(train) < MIN_TRAIN:
            continue
        b = np.polyfit(train["x"], train["y"], 1)
        fc_m.append(b[0] * sub["x"].iloc[i] + b[1])
        fc_b.append(train["y"].mean())
        actual.append(sub["y"].iloc[i])
        dates.append(sub.index[i])
    if len(actual) < 24:
        return {"n_oos": len(actual), "oos_r2": None, "cw_t": None, "cw_p": None}
    fc_m, fc_b, actual = map(np.array, (fc_m, fc_b, actual))
    e_m, e_b = actual - fc_m, actual - fc_b
    oos_r2 = 1 - (e_m @ e_m) / (e_b @ e_b)
    f = e_b ** 2 - (e_m ** 2 - (fc_b - fc_m) ** 2)
    _, cw_t, _ = newey_west_t(f, max(h, 1) if h > 1 else 0)
    cw_p = float(1 - stats.norm.cdf(cw_t)) if cw_t == cw_t else None
    return {"n_oos": int(len(actual)), "oos_start": str(dates[0].date()), "oos_r2": float(oos_r2),
            "cw_t": float(cw_t), "cw_p": cw_p}


def part_b(df: pd.DataFrame) -> dict:
    alpha = 0.05 / (len(B_VARS) * len(HORIZONS))
    out = {}
    for pid, col in B_VARS.items():
        out[pid] = {"variable": col}
        for h in HORIZONS:
            y = df[f"y_h{h}"]
            sub = df[[col, f"y_h{h}"]].dropna()
            if len(sub) < MIN_TRAIN + 24:
                out[pid][f"h{h}"] = {"n": int(len(sub)), "note": "yetersiz veri"}
                continue
            fit = ols_hac(sub[f"y_h{h}"], sub[[col]], h + 2)
            oos = oos_test(df[col], y, h)
            passes = bool(oos["oos_r2"] is not None and oos["oos_r2"] > 0
                          and oos["cw_p"] is not None and oos["cw_p"] < alpha
                          and abs(fit.tvalues[col]) > T_HURDLE)
            out[pid][f"h{h}"] = {
                "n": int(len(sub)), "start": str(sub.index.min().date()),
                "beta": float(fit.params[col]), "t_nw_insample": float(fit.tvalues[col]),
                "r2_insample": float(fit.rsquared), **oos, "passes": passes,
            }
    return {"bonferroni_alpha": alpha, "predictors": out}


def trend_rule(df: pd.DataFrame) -> dict:
    """Bilgi: P4 > 0 iken XU100 (USD), degilse USD nakit; gecis basi %0.2 maliyet."""
    sub = df[["trend_10m", "y_h1"]].dropna()
    pos = (sub["trend_10m"] > 0).astype(float)
    switches = pos.diff().abs().fillna(0)
    strat = pos * sub["y_h1"] - switches * SWITCH_COST
    bh = sub["y_h1"]

    def summary(r: pd.Series) -> dict:
        eq = r.cumsum()
        dd = eq - eq.cummax()
        return {"ann_return_pct": float((math.exp(r.mean() * 12) - 1) * 100),
                "ann_vol_pct": float(r.std() * math.sqrt(12) * 100),
                "sharpe": float(r.mean() / r.std() * math.sqrt(12)) if r.std() > 0 else None,
                "max_drawdown_pct": float((math.exp(dd.min()) - 1) * 100)}

    return {"start": str(sub.index.min().date()), "end": str(sub.index.max().date()),
            "time_in_market_pct": float(pos.mean() * 100), "n_switches": int(switches.sum()),
            "trend_rule": summary(strat), "buy_and_hold": summary(bh)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    raw = load(args.refresh)
    df = build(raw)
    report = {
        "preregistration": "docs/research/macro_drivers_preregistration.md",
        "generated": date.today().isoformat(),
        "data_end": str(df["r_usd"].dropna().index.max().date()),
        "policy_rate_last_decision": str(raw["policy_last_decision"].iloc[-1]),
        "currency_decomposition": currency_decomposition(df),
        "part_a_explanation": part_a(df),
        "part_b_prediction": part_b(df),
        "trend_rule_info_only": trend_rule(df),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"research_macro_drivers_{date.today().isoformat()}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"yazildi: {path}")

    a = report["part_a_explanation"]
    for label, res in a.items():
        print(f"\n[A:{label}] n={res['n_months']} R2={res['r2']:.3f} (1.yari {res['r2_first_half']:.3f}, "
              f"2.yari {res['r2_second_half']:.3f})")
        for i, v in res["variables"].items():
            print(f"  {i} {v['variable']:<12} beta={v['beta']:+.3f} t={v['t_nw']:+.2f} "
                  f"stdB={v['std_beta']:+.2f} shapR2={v['shapley_r2']:.3f} "
                  f"halves t=({v['t_first_half']:+.2f},{v['t_second_half']:+.2f}) "
                  f"{'GECTI' if v['passes'] else '-'}")
    b = report["part_b_prediction"]
    print(f"\n[B] bonferroni alpha={b['bonferroni_alpha']:.4f}")
    for pid, v in b["predictors"].items():
        for h in HORIZONS:
            r = v.get(f"h{h}", {})
            if "oos_r2" not in r or r["oos_r2"] is None:
                print(f"  {pid} {v['variable']:<16} h={h:<2} {r.get('note', 'yetersiz')}")
                continue
            print(f"  {pid} {v['variable']:<16} h={h:<2} t_is={r['t_nw_insample']:+.2f} "
                  f"OOS_R2={r['oos_r2']*100:+.2f}% CW_t={r['cw_t']:+.2f} p={r['cw_p']:.4f} "
                  f"{'GECTI' if r['passes'] else '-'}")
    print("\n[kur ayristirmasi]", json.dumps(report["currency_decomposition"], indent=1))
    print("\n[trend kurali, bilgi]", json.dumps(report["trend_rule_info_only"], indent=1))


if __name__ == "__main__":
    main()
