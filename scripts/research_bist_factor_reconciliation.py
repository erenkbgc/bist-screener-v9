#!/usr/bin/env python3
"""2026 BIST faktor calismasi uzlastirma testi
(docs/research/bist_factor_reconciliation_preregistration.md).

Gokcen (2026, Borsa Istanbul Review) bulgulari ile kendi C1 panelimiz arasindaki
metodolojik farklari (likidite kesimi, esit vs piyasa degeri agirliklandirmasi,
alternatif karlilik ve momentum tanimlari, dusuk volatilite kuyruk ayrisimi) olcer:
  - R1 (Buyukluk / Size): liq_drop = 0.0, 0.30, 0.50; EW vs VW; ilikidite kontrolu.
  - R2 (Karlilik / Profitability): GP/A, ROE, ROA, OP/A (EBIT/Assets); tek basina ve
    value_sn kontrolu altinda Fama-MacBeth egimleri.
  - R3 (Momentum): 12-1 vs 6-1; liq_drop = 0.0 vs 0.30; EW vs VW; kesif vs holdout.
  - R4 (Dusuk Volatilite / vol60): Q5 (en dusuk vol) vs Q1 (en yuksek vol) kuyruk
    ayrisimi ve value_sn icinden en volatil %20'yi eleme etkisi.

    python scripts/research_bist_factor_reconciliation.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backtest_factor_model import FACTORS, add_composites  # noqa: E402
from core import factor_backtest as fb  # noqa: E402
from core import pit_panel  # noqa: E402
from diagnose_crashed_picks import month_end  # noqa: E402
from research_long_term import extended_quarterly  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SPLIT = pd.Timestamp("2021-01-01")


def nw(s: pd.Series, lags: int = 6, scale: float = 1200.0) -> dict:
    m, t, n = fb.newey_west_t(s, lags)
    return {
        "ann_pct": round(scale * m, 2) if np.isfinite(m) else None,
        "t": round(float(t), 2) if np.isfinite(t) else None,
        "months": int(n),
    }


def add_extra_factors(raw: pd.DataFrame, q: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """ROA (TTM net kar / toplam aktif), OP/A (TTM EBIT / toplam aktif) ve 6-1 momentum ekler."""
    q = q.sort_values(["ticker", "period_end"]).copy()
    ni = q["ttm_ni_parent"].where(q["ttm_ni_parent"].notna(), q.get("ttm_net_income"))
    ebit = q["ttm_ebit"].where(q["ttm_ebit"].notna(), q.get("ttm_op_profit"))
    ta = q["total_assets"].where(q["total_assets"] > 0)
    q["roa"] = ni / ta
    q["opa"] = ebit / ta
    stmt_cols = q[["ticker", "period", "roa", "opa"]].rename(columns={"period": "stmt_period"})

    p = prices.sort_values(["ticker", "date"]).copy()
    g = p.groupby("ticker")["adj"]
    p["mom_6_1"] = g.shift(1) / g.shift(6) - 1.0
    mom_cols = p[["date", "ticker", "mom_6_1"]]

    out = raw.merge(stmt_cols, on=["ticker", "stmt_period"], how="left")
    out = out.merge(mom_cols, on=["date", "ticker"], how="left")
    return out


def quintile_ew_vw(df: pd.DataFrame, col: str, ret: str = "fwd_ret_1m",
                   n_q: int = 5, min_names: int = 30) -> pd.DataFrame:
    """Her ay 5 dilim: EW ve VW (mcap agirlikli) Q5 - Q1 yayilimi ve Q5 - Evren aktif getirisi."""
    rows = []
    for dt, g in df[["date", "ticker", col, ret, "mcap"]].dropna().groupby("date"):
        if len(g) < min_names:
            continue
        q = pd.qcut(g[col].rank(method="first"), n_q, labels=False)
        top = g[q == n_q - 1]
        bot = g[q == 0]

        def vw(sub: pd.DataFrame) -> float:
            w = sub["mcap"].clip(lower=0.0).to_numpy(dtype=float)
            return float(np.average(sub[ret].to_numpy(dtype=float), weights=w)) if w.sum() > 0 else float(sub[ret].mean())

        ew_univ = float(g[ret].mean())
        vw_univ = vw(g)
        ew_top, ew_bot = float(top[ret].mean()), float(bot[ret].mean())
        vw_top, vw_bot = vw(top), vw(bot)
        rows.append({
            "date": dt,
            "ew_q5_minus_q1": ew_top - ew_bot,
            "ew_q5_minus_univ": ew_top - ew_univ,
            "ew_q1_minus_univ": ew_bot - ew_univ,
            "vw_q5_minus_q1": vw_top - vw_bot,
            "vw_q5_minus_univ": vw_top - vw_univ,
        })
    return pd.DataFrame(rows).set_index("date").sort_index() if rows else pd.DataFrame()


def summarize_factor(df: pd.DataFrame, col: str, ret: str = "fwd_ret_1m") -> dict:
    ic = fb.rank_ic(df, col, ret)
    q = quintile_ew_vw(df, col, ret)
    out = {}
    for wname, wfn in (("full", lambda idx: idx == idx),
                       ("discovery", lambda idx: idx < SPLIT),
                       ("holdout", lambda idx: idx >= SPLIT)):
        sub_ic = ic[wfn(ic.index)]
        sub_q = q[wfn(q.index)]
        ic_m, ic_t, ic_n = fb.newey_west_t(sub_ic, 6)
        out[wname] = {
            "rank_ic": round(float(ic_m), 4) if np.isfinite(ic_m) else None,
            "rank_ic_t": round(float(ic_t), 2) if np.isfinite(ic_t) else None,
            "months": int(ic_n),
            "ew_q5_q1": nw(sub_q["ew_q5_minus_q1"]),
            "ew_q5_univ": nw(sub_q["ew_q5_minus_univ"]),
            "vw_q5_q1": nw(sub_q["vw_q5_minus_q1"]),
            "vw_q5_univ": nw(sub_q["vw_q5_minus_univ"]),
        }
    return out


def low_vol_decomposition(df: pd.DataFrame, ret: str = "fwd_ret_1m") -> dict:
    """vol60_z (yuksek = dusuk volatilite): Q5 (en dusuk vol), Q1 (en yuksek vol),
    Q1 haric evren ve Q1 haric value_sn ust %20 analizi."""
    rows = []
    for dt, g in df.dropna(subset=["vol60_z", "value_sn_z", ret]).groupby("date"):
        if len(g) < 30:
            continue
        q_vol = pd.qcut(g["vol60_z"].rank(method="first"), 5, labels=False)
        univ = float(g[ret].mean())
        q5_low_vol = float(g.loc[q_vol == 4, ret].mean())
        q1_high_vol = float(g.loc[q_vol == 0, ret].mean())
        ex_q1 = g[q_vol > 0]
        univ_ex_q1 = float(ex_q1[ret].mean())

        r_val_all = g["value_sn_z"].rank(ascending=False, pct=True)
        val_top = float(g.loc[r_val_all <= 0.20, ret].mean())

        r_val_ex = ex_q1["value_sn_z"].rank(ascending=False, pct=True)
        val_ex_highvol_top = float(ex_q1.loc[r_val_ex <= 0.20, ret].mean())

        rows.append({
            "date": dt,
            "q5_lowvol_minus_univ": q5_low_vol - univ,
            "q1_highvol_minus_univ": q1_high_vol - univ,
            "q5_minus_q1": q5_low_vol - q1_high_vol,
            "univ_ex_highvol_minus_univ": univ_ex_q1 - univ,
            "value_top20_minus_univ": val_top - univ,
            "value_ex_highvol_top20_minus_univ": val_ex_highvol_top - univ,
            "value_ex_highvol_minus_value": val_ex_highvol_top - val_top,
        })
    res_df = pd.DataFrame(rows).set_index("date").sort_index()
    out = {}
    for wname, wfn in (("full", lambda idx: idx == idx),
                       ("discovery", lambda idx: idx < SPLIT),
                       ("holdout", lambda idx: idx >= SPLIT)):
        sub = res_df[wfn(res_df.index)]
        out[wname] = {col: nw(sub[col]) for col in res_df.columns}
    return out


def main() -> None:
    raw = pd.read_parquet(RESEARCH / "factors_monthly.parquet")
    raw["date"] = month_end(raw["date"])
    market_m = pit_panel.monthly_market(pd.read_parquet(RESEARCH / "fx.parquet"))
    raw = pit_panel.add_usd_returns(raw, market_m)
    prices = pd.read_parquet(RESEARCH / "monthly_prices.parquet")
    prices["date"] = month_end(prices["date"])
    raw = add_extra_factors(raw, extended_quarterly(), prices)

    all_factors = list(dict.fromkeys([*FACTORS, "roa", "opa", "mom_6_1"]))
    fb.SIGNS.update({"roa": 1, "opa": 1, "mom_6_1": 1})

    cuts = {
        "liq_drop_0_0_all": add_composites(fb.prepare(raw, all_factors, liq_drop_pct=0.0)),
        "liq_drop_0_3_live": add_composites(fb.prepare(raw, all_factors, liq_drop_pct=0.3)),
        "liq_drop_0_5_large_liq": add_composites(fb.prepare(raw, all_factors, liq_drop_pct=0.5)),
    }

    # R1: Size across liquidity cuts & controlling for liquidity / value
    r1_size = {cname: summarize_factor(cdf, "size_z") for cname, cdf in cuts.items()}
    df_live = cuts["liq_drop_0_3_live"].copy()
    df_live["log_tlvol_z"] = df_live.groupby("date")["tlvol60"].transform(lambda s: fb.winsorize_z(np.log(s.clip(lower=1.0))))
    fm_size = fb.fama_macbeth(df_live, ["size_z", "log_tlvol_z", "value_sn_z"], "fwd_ret_1m")
    r1_size["fama_macbeth_size_controlling_liq_and_value"] = {
        w: {c: nw(fm_size.loc[(fm_size.index < SPLIT) if w == "discovery" else (fm_size.index >= SPLIT), c])
            for c in ("size_z", "log_tlvol_z", "value_sn_z")}
        for w in ("discovery", "holdout")
    }

    # R2: Profitability definitions (gpa, roe, roa, opa) on live liquid universe
    r2_prof = {}
    for pf in ("gpa", "roe", "roa", "opa"):
        zcol = f"{pf}_z"
        sncol = f"{pf}_sn_z"
        df_live[sncol] = fb.sector_neutralize(df_live, zcol, min_n=5)
        fm_bi = fb.fama_macbeth(df_live, ["value_sn_z", sncol], "fwd_ret_1m")
        r2_prof[pf] = {
            "raw": summarize_factor(df_live, zcol),
            "sector_neutral": summarize_factor(df_live, sncol),
            "fm_controlling_for_value_sn": {
                w: {
                    "prof_slope": nw(fm_bi.loc[(fm_bi.index < SPLIT) if w == "discovery" else (fm_bi.index >= SPLIT), sncol]),
                    "value_slope": nw(fm_bi.loc[(fm_bi.index < SPLIT) if w == "discovery" else (fm_bi.index >= SPLIT), "value_sn_z"]),
                }
                for w in ("discovery", "holdout")
            },
        }

    # R3: Momentum (12-1 vs 6-1, all vs liquid 0.3, EW vs VW)
    r3_mom = {
        "mom_12_1_all": summarize_factor(cuts["liq_drop_0_0_all"], "mom_12_1_z"),
        "mom_12_1_live_liq": summarize_factor(df_live, "mom_12_1_z"),
        "mom_6_1_all": summarize_factor(cuts["liq_drop_0_0_all"], "mom_6_1_z"),
        "mom_6_1_live_liq": summarize_factor(df_live, "mom_6_1_z"),
    }

    # R4: Low volatility decomposition (long leg vs high-vol loser avoidance)
    r4_lowvol = low_vol_decomposition(df_live)

    result = {
        "as_of": date.today().isoformat(),
        "R1_size": r1_size,
        "R2_profitability": r2_prof,
        "R3_momentum": r3_mom,
        "R4_low_volatility": r4_lowvol,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    out = ROOT / "data" / "reports" / f"research_bist_factor_reconciliation_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
