"""Faz 2 on-kayitli uzun vade testleri icin sinyal ve portfoy yardimcilari.

Tanimlar docs/research/long_term_preregistration.md ile birebir aynidir; orada
degisiklik yeni bir on-kayit gerektirir. Fonksiyonlar saf (I/O yok); kosucu
scripts/research_long_term.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core import factor_backtest as fb

PHI = 2 ** (-1 / 3)  # CHS geometrik agirlik
CHS_COEF = {"nimta": -20.12, "tlmta": 1.60, "exret": -7.88, "sigma": 1.55,
            "rsize": -0.005, "cashmta": -2.27, "mb": 0.070}
ALTMAN_DISTRESS = 1.1
COST_BPS = 20.0


def _weighted_avg(values: list[float]) -> float:
    """values[0] en yeni. CHS agirliklari phi^j, toplam 1'e olceklenir; eksik varsa NaN."""
    if any(v is None or not np.isfinite(v) for v in values):
        return np.nan
    w = np.array([PHI ** j for j in range(len(values))])
    return float(np.dot(w / w.sum(), values))


def statement_features(q: pd.DataFrame) -> pd.DataFrame:
    """(ticker, period) basina F7 ve Altman girdileri; yil onceki ayni ceyrekle karsilastirma."""
    q = q.sort_values(["ticker", "period_end"]).copy()
    ni = q["ttm_ni_parent"].where(q["ttm_ni_parent"].notna(), q.get("ttm_net_income"))
    ta = q["total_assets"].where(q["total_assets"] > 0)
    q["roa"] = ni / ta
    q["lev"] = q["fin_debt"].fillna(0.0) / ta
    q["cur_ratio"] = q["current_assets"] / q["current_liab"].where(q["current_liab"] > 0)
    q["gm"] = q["ttm_gross_profit"] / q["ttm_revenue"].where(q["ttm_revenue"] > 0)
    q["ato"] = q["ttm_revenue"] / ta
    prev = q[["ticker", "year", "q", "roa", "lev", "cur_ratio", "gm", "ato"]].copy()
    prev["year"] = prev["year"] + 1
    q = q.merge(prev, on=["ticker", "year", "q"], how="left", suffixes=("", "_ya"))

    def pt(cond: pd.Series, *inputs: pd.Series) -> pd.Series:
        known = pd.concat(inputs, axis=1).notna().all(axis=1)
        return cond.astype(float).where(known)

    parts = [
        pt(q["roa"] > 0, q["roa"]),
        pt(q["roa"] > q["roa_ya"], q["roa"], q["roa_ya"]),
        pt(q["lev"] < q["lev_ya"], q["lev"], q["lev_ya"]),
        pt(q["cur_ratio"] > q["cur_ratio_ya"], q["cur_ratio"], q["cur_ratio_ya"]),
        pt(q["gm"] > q["gm_ya"], q["gm"], q["gm_ya"]),
        pt(q["ato"] > q["ato_ya"], q["ato"], q["ato_ya"]),
    ]
    p = pd.concat(parts, axis=1)
    # 6 bilanco/gelir maddesinin hepsi bilinmeli; 7. madde (bedelli) aylik panelden eklenir.
    q["f6"] = p.sum(axis=1).where(p.notna().all(axis=1))

    tl = q["current_liab"] + q["noncurrent_liab"]
    ebit = q["ttm_ebit"].where(q["ttm_ebit"].notna(), q["ttm_op_profit"])
    eq = q["equity"]
    q["altman_em"] = (6.56 * (q["current_assets"] - q["current_liab"]) / ta
                      + 3.26 * q["retained"] / ta
                      + 6.72 * ebit / ta
                      + 1.05 * eq / tl.where(tl > 0))
    q["total_liab"] = tl
    qni = q["q_ni_parent"].where(q["q_ni_parent"].notna(), q.get("q_net_income"))
    q["_qni"] = qni
    lags = [q.groupby("ticker")["_qni"].shift(j) for j in range(4)]
    lag_end = [q.groupby("ticker")["period_end"].shift(j) for j in range(4)]
    consec = ((lag_end[0] - lag_end[3]).dt.days.between(260, 290))
    q["ni_q0"], q["ni_q1"], q["ni_q2"], q["ni_q3"] = [x.where(consec) for x in lags]
    return q[["ticker", "period", "f6", "altman_em", "total_liab", "cash",
              "ni_q0", "ni_q1", "ni_q2", "ni_q3"]].rename(columns={"period": "stmt_period", "cash": "cash_q"})


def monthly_exret(prices: pd.DataFrame, market_m: pd.DataFrame) -> pd.DataFrame:
    """Ay sonu CHS EXRETAVG: son 12 ayin log fazla getirisi, phi agirlikli."""
    p = prices.sort_values(["ticker", "date"]).copy()
    p["r"] = np.log(p.groupby("ticker")["adj"].pct_change() + 1)
    xu = np.log(market_m["xu100"].pct_change() + 1)
    p["ex"] = p["r"] - p["date"].map(xu)
    w = np.array([PHI ** j for j in range(12)])
    w = w / w.sum()

    def roll(s: pd.Series) -> pd.Series:
        return s.rolling(12, min_periods=12).apply(lambda x: float(np.dot(w, x[::-1])), raw=True)

    p["exretavg"] = p.groupby("ticker")["ex"].transform(roll)
    hi = p.groupby("ticker")["adj"].transform(lambda s: s.rolling(12, min_periods=12).max())
    p["hi52"] = p["adj"] / hi
    return p[["date", "ticker", "exretavg", "hi52"]]


def add_signals(df: pd.DataFrame, stmt: pd.DataFrame, monthly: pd.DataFrame, mcap_total: pd.Series) -> pd.DataFrame:
    out = df.merge(stmt, on=["ticker", "stmt_period"], how="left")
    out = out.merge(monthly, on=["date", "ticker"], how="left")
    mta = out["mcap"] + out["total_liab"]
    mta = mta.where(mta > 0)
    nimta = pd.Series([_weighted_avg([r.ni_q0, r.ni_q1, r.ni_q2, r.ni_q3])
                       for r in out[["ni_q0", "ni_q1", "ni_q2", "ni_q3"]].itertuples()], index=out.index) / mta
    be = out["mcap"] * out["bm"]
    adj_be = (be + 0.1 * (out["mcap"] - be)).clip(lower=1.0)
    terms = {
        "nimta": nimta,
        "tlmta": out["total_liab"] / mta,
        "exret": out["exretavg"],
        "sigma": out["vol60"] * np.sqrt(252),
        "rsize": np.log(out["mcap"] / out["date"].map(mcap_total)),
        "cashmta": out["cash_q"] / mta,
        "mb": out["mcap"] / adj_be,
    }
    out["chs"] = sum(CHS_COEF[k] * v for k, v in terms.items())
    out["f7"] = out["f6"] + (out["nsi_rights_12m"] == 0).astype(float)
    return out


def flags(df: pd.DataFrame) -> dict[str, pd.Series]:
    """On-kayitli dislama bayraklari (True = cikar). Eksik veri dislanmaz."""
    g = df.groupby("date")
    chs_cut = g["chs"].transform(lambda s: s.quantile(0.9))
    mom_cut = g["mom_12_1"].transform(lambda s: s.quantile(0.2))
    hi_cut = g["hi52"].transform(lambda s: s.quantile(0.2))
    vol_cut = g["vol60"].transform(lambda s: s.quantile(0.8))
    crashed = df["dd_5y_pct"] <= -70.0
    return {
        "H1a": df["chs"] > chs_cut,
        "H1b": df["altman_em"] < ALTMAN_DISTRESS,
        "H2a": crashed,
        "H2b": crashed & (df["f7"] <= 3),
        "H3a": df["mom_12_1"] < mom_cut,
        "H3b": df["hi52"] < hi_cut,
        "H4b": df["f7"] <= 2,
        "H8": df["vol60"] > vol_cut,
    }


def composite(df: pd.DataFrame, other: str) -> pd.Series:
    s = 0.5 * df["value_sn_z"] + 0.5 * df[other].fillna(0.0)
    return s.where(df["value_sn_z"].notna())


def portfolio(df: pd.DataFrame, rank_col: str, exclude: pd.Series | None = None,
              ret_cols: tuple[str, ...] = ("fwd_ret_1m", "fwd_ret_1m_usd")) -> pd.DataFrame:
    """Aylik ust dilim (kalan adaylar icinde %20), evren ortalamasi TUM evrenden.

    Doner: date, n, turnover, top_<ret>, uni_<ret>, active_<ret> (net), trap_rate.
    """
    rows, prev = [], set()
    excl = exclude if exclude is not None else pd.Series(False, index=df.index)
    for dt, g in df.groupby("date"):
        g = g[g["fwd_ret_1m"].notna()]
        if len(g) < 30:
            continue
        elig = g[g[rank_col].notna() & ~excl.loc[g.index].fillna(False).astype(bool)]
        if len(elig) < 5:
            continue
        n_top = max(1, int(round(len(elig) * 0.2)))
        top = elig.nlargest(n_top, rank_col)
        names = set(top["ticker"])
        turnover = 1 - len(names & prev) / len(names) if prev else 1.0
        prev = names
        row = {"date": dt, "n": len(top), "turnover": turnover}
        cost = 2 * turnover * COST_BPS / 1e4
        for c in ret_cols:
            row[f"top_{c}"] = top[c].mean()
            row[f"uni_{c}"] = g[c].mean()
            row[f"active_{c}"] = row[f"top_{c}"] - row[f"uni_{c}"] - cost
        xs6 = top["xs_6m"].dropna()
        row["trap_rate"] = float((xs6 < -0.30).mean()) if len(xs6) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(p: pd.DataFrame, col: str = "active_fwd_ret_1m") -> dict:
    s = p[col].dropna()
    if s.empty:
        return {"months": 0}
    m, t, n = fb.newey_west_t(s, 6)
    cum = (1 + s).cumprod()
    mdd = float((cum / cum.cummax() - 1).min())
    return {"months": n, "active_ann_pct": round(100 * 12 * m, 2), "t": round(t, 2),
            "max_dd_pct": round(100 * mdd, 1), "avg_names": round(float(p["n"].mean()), 1),
            "turnover_pct": round(100 * float(p["turnover"].mean()), 1),
            "trap_rate_pct": round(100 * float(p["trap_rate"].mean()), 1)}


def diff_stats(base: pd.DataFrame, alt: pd.DataFrame, col: str = "active_fwd_ret_1m") -> dict:
    d = alt.set_index("date")[col] - base.set_index("date")[col]
    d = d.dropna()
    if d.empty:
        return {"months": 0}
    m, t, n = fb.newey_west_t(d, 6)
    return {"months": n, "diff_ann_pct": round(100 * 12 * m, 2), "t": round(t, 2)}
