#!/usr/bin/env python3
"""Kalite x Degerleme etkilesimi ve Dusuk Volatilite risk filtresi arastirmasi
(docs/research/quality_value_lowvol_preregistration.md).

Bolumler:
  - Aile A (Kosullu Cift Siralama / Double-Sort):
      value_sn_z dilimleri (ozellikle V_Q5 en ucuz %20 ve V_Q4+V_Q5 en ucuz %40)
      icinde Q_roe (roe_sn_z), Q_roa (roa_sn_z), Q_opa (opa_sn_z), Q_gpa (gpa_sn_z),
      Q_f7 (Piotroski F7), Q_qual (roe_sn_z + roa_sn_z + f7_z, strict NaN) ve
      R_lowvol (vol60_z) alt/orta/ust uclulerinin getiri yayilimi ve 6 aylik deger
      tuzagi (fwd_ret_6m_xs < -30%) oranlari.
  - Aile B (Maliyetli Portfoy Simulasyonu, 1M TL, baz maliyet, ertesi gun kapanisi):
      P0_value_top20, QV1_roe_filter, QV2_f7_filter, QV3_qual_in_top30,
      LV1_lowvol_filter, LV2_lowvol_in_top25, QLV_combined_filter.
      Her varyant icin ALPHA_ENHANCEMENT vs RISK_CONTROL_ONLY vs REJECTED karari.

    python scripts/research_quality_value_lowvol.py
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

from core import factor_backtest as fb  # noqa: E402
from core import portfolio_backtest as pb  # noqa: E402
from research_long_term import extended_quarterly, load  # noqa: E402
from research_portfolio_backtest import (  # noqa: E402
    CAPITAL_REF,
    RESEARCH,
    SPLIT,
    TOP,
    attach_benchmarks,
    load_daily,
    stats,
)


def nw(s: pd.Series, lags: int = 6, scale: float = 1200.0) -> dict:
    m, t, n = fb.newey_west_t(s, lags)
    return {
        "ann_pct": round(scale * m, 2) if np.isfinite(m) else None,
        "raw_mean": round(float(m), 4) if np.isfinite(m) else None,
        "t": round(float(t), 2) if np.isfinite(t) else None,
        "months": int(n),
    }


def coverage_summary(df: pd.DataFrame, cols: list[str]) -> dict[str, dict]:
    """Her sutun icin toplam ve aylik kapsama oranini (obs_pct, monthly_mean_pct, monthly_min_pct) raporlar."""
    out: dict[str, dict] = {}
    post_warmup = pd.Timestamp("2013-12-01")
    for c in cols:
        if c not in df.columns:
            continue
        valid = df[c].notna()
        by_m = df.assign(_v=valid).groupby("date")["_v"].agg(["mean", "sum"])
        by_m_pw = by_m[by_m.index >= post_warmup]
        out[c] = {
            "obs_pct": round(100.0 * float(valid.mean()), 2),
            "monthly_mean_pct": round(100.0 * float(by_m["mean"].mean()), 2) if not by_m.empty else 0.0,
            "monthly_min_pct": round(100.0 * float(by_m["mean"].min()), 2) if not by_m.empty else 0.0,
            "post_2013_warmup_min_pct": round(100.0 * float(by_m_pw["mean"].min()), 2) if not by_m_pw.empty else 0.0,
            "avg_valid_names_per_month": round(float(by_m["sum"].mean()), 2) if not by_m.empty else 0.0,
        }
    return out


def enrich_quality_and_risk_factors(
    df: pd.DataFrame, q_ext: pd.DataFrame | None = None, min_peers: int = 5
) -> pd.DataFrame:
    """Strict NaN politikasiyla roa, opa, sektor-notr kalite z-skorlari ve qual_sn_z uretir."""
    out = df.copy()
    if q_ext is not None and ("roa" not in out.columns or "opa" not in out.columns):
        q = q_ext.sort_values(["ticker", "period_end"]).copy()
        ni = q["ttm_ni_parent"].where(q["ttm_ni_parent"].notna(), q.get("ttm_net_income"))
        ebit = q["ttm_ebit"].where(q["ttm_ebit"].notna(), q.get("ttm_op_profit"))
        ta = q["total_assets"].where(q["total_assets"] > 0)
        q["roa"] = ni / ta
        q["opa"] = ebit / ta
        stmt_cols = q[["ticker", "period", "roa", "opa"]].rename(columns={"period": "stmt_period"})
        out = out.merge(stmt_cols, on=["ticker", "stmt_period"], how="left")

    for raw_col in ("roe", "roa", "opa", "gpa"):
        zcol = f"{raw_col}_z"
        if zcol not in out.columns and raw_col in out.columns:
            out[zcol] = out.groupby("date")[raw_col].transform(fb.winsorize_z)
        if zcol in out.columns:
            out[f"{raw_col}_sn_z"] = fb.sector_neutralize(out, zcol, min_n=min_peers)

    if "f7" in out.columns:
        out["f7_z"] = out.groupby("date")["f7"].transform(fb.winsorize_z)

    qual_legs = [c for c in ("roe_sn_z", "roa_sn_z", "f7_z") if c in out.columns]
    if len(qual_legs) == 3:
        out["qual_sn_z"] = out[qual_legs].mean(axis=1, skipna=False)
        out["qual_sn_z_skipna"] = out[qual_legs].mean(axis=1, skipna=True)
    return out


def conditional_double_sort(
    df: pd.DataFrame,
    cond_col: str,
    val_col: str = "value_sn_z",
    ret_col: str = "fwd_ret_1m",
    top_val_quintiles: tuple[int, ...] = (4,),
    min_names: int = 25,
) -> dict:
    """Her ay val_col uzerinden 5 dilime ayirir; secilen deger dilimi (or. V_Q5 = 4) icinde
    cond_col uzerinden alt %30 (Low), orta %40 (Mid) ve ust %30 (High) alt gruplarini karsilastirir."""
    rows = []
    has_trap = "fwd_ret_6m_xs" in df.columns
    for dt, g in df.dropna(subset=[val_col, ret_col]).groupby("date"):
        if len(g) < min_names:
            continue
        vq = pd.qcut(g[val_col].rank(method="first"), 5, labels=False)
        v_slice = g[vq.isin(top_val_quintiles)].copy()
        all_vq_ret = float(v_slice[ret_col].mean())

        sub = v_slice.dropna(subset=[cond_col])
        if len(sub) < 6:
            continue
        rk = sub[cond_col].rank(method="first", pct=True)
        low = sub[rk <= 0.30]
        high = sub[rk > 0.70]
        nonlow = sub[rk > 0.30]
        if low.empty or high.empty:
            continue

        row = {
            "date": dt,
            "low_ret": float(low[ret_col].mean()),
            "high_ret": float(high[ret_col].mean()),
            "nonlow_ret": float(nonlow[ret_col].mean()),
            "all_vq_ret": all_vq_ret,
            "high_minus_low": float(high[ret_col].mean() - low[ret_col].mean()),
            "high_minus_all_vq": float(high[ret_col].mean() - all_vq_ret),
            "nonlow_minus_all_vq": float(nonlow[ret_col].mean() - all_vq_ret),
        }
        if has_trap:
            l6 = low["fwd_ret_6m_xs"].dropna()
            h6 = high["fwd_ret_6m_xs"].dropna()
            nl6 = nonlow["fwd_ret_6m_xs"].dropna()
            a6 = v_slice["fwd_ret_6m_xs"].dropna()
            row["trap_low"] = float((l6 < -0.30).mean()) if len(l6) else np.nan
            row["trap_high"] = float((h6 < -0.30).mean()) if len(h6) else np.nan
            row["trap_nonlow"] = float((nl6 < -0.30).mean()) if len(nl6) else np.nan
            row["trap_all_vq"] = float((a6 < -0.30).mean()) if len(a6) else np.nan
        rows.append(row)

    panel = pd.DataFrame(rows).set_index("date").sort_index() if rows else pd.DataFrame()
    out: dict[str, dict] = {}
    for wname, wfn in (("full", lambda idx: idx == idx),
                       ("discovery", lambda idx: idx < SPLIT),
                       ("holdout", lambda idx: idx >= SPLIT)):
        sub_p = panel[wfn(panel.index)] if not panel.empty else pd.DataFrame()
        if sub_p.empty:
            out[wname] = {}
            continue
        entry = {
            "high_minus_low": nw(sub_p["high_minus_low"]),
            "high_minus_all_vq": nw(sub_p["high_minus_all_vq"]),
            "nonlow_minus_all_vq": nw(sub_p["nonlow_minus_all_vq"]),
        }
        if "trap_low" in sub_p.columns:
            entry["trap_6m_pct"] = {
                "low": round(100.0 * float(sub_p["trap_low"].mean()), 2),
                "high": round(100.0 * float(sub_p["trap_high"].mean()), 2),
                "nonlow": round(100.0 * float(sub_p["trap_nonlow"].mean()), 2),
                "all_vq": round(100.0 * float(sub_p["trap_all_vq"].mean()), 2),
            }
        out[wname] = entry
    return out


def build_portfolio_selections(
    df: pd.DataFrame,
) -> tuple[dict[str, dict[pd.Timestamp, list[str]]], dict[str, pd.Series]]:
    """Aile B portfoy varyantlarinin aylik hisse listelerini ve 6-aylik deger tuzagi serilerini uretir."""
    variants = (
        "P0_value_top20",
        "QV1_roe_filter",
        "QV2_f7_filter",
        "QV3_qual_in_top30",
        "LV1_lowvol_filter",
        "LV2_lowvol_in_top25",
        "QLV_combined_filter",
        "EW_universe",
    )
    sel: dict[str, dict[pd.Timestamp, list[str]]] = {k: {} for k in variants}
    traps: dict[str, dict[pd.Timestamp, float]] = {k: {} for k in variants if k != "EW_universe"}
    has_trap = "fwd_ret_6m_xs" in df.columns

    for t, g in df[df["value_sn_z"].notna()].groupby("date"):
        if len(g) < 30:
            continue
        sel["EW_universe"][t] = sorted(g["ticker"])

        r_val = g["value_sn_z"].rank(ascending=False, pct=True)
        top20 = g[r_val <= TOP]
        top25 = g[r_val <= 0.25]
        top30 = g[r_val <= 0.30]

        # Evren bazli kuyruk esikleri (strict NaN korunarak)
        roe_valid = g["roe_sn_z"].dropna()
        roe_q20 = float(roe_valid.quantile(0.20)) if len(roe_valid) >= 10 else -np.inf
        vol_valid = g["vol60_z"].dropna()
        vol_q20 = float(vol_valid.quantile(0.20)) if len(vol_valid) >= 10 else -np.inf

        picks_map: dict[str, pd.DataFrame] = {}
        # 1. P0: kosulsuz value_sn ust %20
        picks_map["P0_value_top20"] = top20

        # 2. QV1: value_sn ust %20 icinden roe_sn_z alt %20 (veya NaN) elenir
        picks_map["QV1_roe_filter"] = top20[top20["roe_sn_z"].notna() & (top20["roe_sn_z"] > roe_q20)]

        # 3. QV2: value_sn ust %20 icinden F7 <= 3 (veya NaN) elenir (2013 YoY isinma aylari haric)
        has_f7 = g["f7"].notna().sum() >= 10
        picks_map["QV2_f7_filter"] = (
            top20[top20["f7"].notna() & (top20["f7"] > 3)] if has_f7 else top20
        )

        # 4. QV3: value_sn ust %30 icinden qual_sn_z en yuksek 2/3 (~%20 evren genisligi)
        t30_q = top30.dropna(subset=["qual_sn_z"])
        k_qv3 = max(2, int(round(len(g) * TOP)))
        picks_map["QV3_qual_in_top30"] = t30_q.nlargest(k_qv3, "qual_sn_z") if len(t30_q) >= 2 else top20

        # 5. LV1: value_sn ust %20 icinden en volatil %20 (vol60_z <= vol_q20 veya NaN) elenir
        picks_map["LV1_lowvol_filter"] = top20[top20["vol60_z"].notna() & (top20["vol60_z"] > vol_q20)]

        # 6. LV2: value_sn ust %25 icinden en volatil %20 elenir (~%20 evren genisligi)
        t25_v = top25.dropna(subset=["vol60_z"])
        k_lv2 = max(2, int(round(len(g) * TOP)))
        picks_map["LV2_lowvol_in_top25"] = t25_v.nlargest(k_lv2, "vol60_z") if len(t25_v) >= 2 else top20

        # 7. QLV: asiri volatil (%20) VEYA (dusuk ROE %20 VE zayif bilanco F7 <= 3) elenir
        bad_vol = top20["vol60_z"].isna() | (top20["vol60_z"] <= vol_q20)
        if has_f7:
            bad_qual = (top20["roe_sn_z"].isna() | (top20["roe_sn_z"] <= roe_q20)) & (
                top20["f7"].isna() | (top20["f7"] <= 3)
            )
        else:
            bad_qual = pd.Series(False, index=top20.index)
        picks_map["QLV_combined_filter"] = top20[~(bad_vol | bad_qual)]

        for k, sub_df in picks_map.items():
            sel[k][t] = sorted(sub_df["ticker"])
            if has_trap:
                xs6 = sub_df["fwd_ret_6m_xs"].dropna()
                if len(xs6):
                    traps[k][t] = float((xs6 < -0.30).mean())

    trap_series = {k: pd.Series(v).sort_index() for k, v in traps.items()}
    return sel, trap_series


def classify_outcome(
    disc_d: dict,
    hold_d: dict,
    disc_st: dict,
    hold_st: dict,
    p0_disc_st: dict,
    p0_hold_st: dict,
) -> str:
    """On-kayitli 3-yonlu karar kurali: ALPHA_ENHANCEMENT vs RISK_CONTROL_ONLY vs REJECTED."""
    d_disc = disc_d.get("ann_pct") or 0.0
    t_disc = disc_d.get("t") or 0.0
    d_hold = hold_d.get("ann_pct") or 0.0
    t_hold = hold_d.get("t") or 0.0
    usd_ok = (hold_st.get("cagr_usd_pct") or -999.0) >= (p0_hold_st.get("cagr_usd_pct") or 0.0)

    if d_disc > 0 and t_disc >= 2.0 and d_hold >= 1.5 and t_hold >= 1.96 and usd_ok:
        return "ALPHA_ENHANCEMENT"

    def risk_improves(st: dict, p0_st: dict) -> bool:
        vol_ok = (st.get("vol_ann_pct") or 999.0) < (p0_st.get("vol_ann_pct") or 0.0)
        mdd_ok = abs(st.get("active_ew_max_dd_pct") or 999.0) < abs(p0_st.get("active_ew_max_dd_pct") or 0.0)
        t_act = (st.get("vs_ew_net", {}).get("t") or -999.0) >= (p0_st.get("vs_ew_net", {}).get("t") or 0.0)
        return (vol_ok or mdd_ok) and t_act

    if (
        risk_improves(disc_st, p0_disc_st)
        and risk_improves(hold_st, p0_hold_st)
        and d_disc > -1.0
        and d_hold > -1.0
    ):
        return "RISK_CONTROL_ONLY"

    return "REJECTED"


def main() -> None:
    base_df = load()
    q_ext = extended_quarterly()
    df = enrich_quality_and_risk_factors(base_df, q_ext=q_ext)

    cov = coverage_summary(
        df,
        ["value_sn_z", "roe_sn_z", "roa_sn_z", "opa_sn_z", "gpa_sn_z", "f7", "qual_sn_z", "qual_sn_z_skipna", "vol60_z"],
    )

    # 1. Aile A: Kosullu Cift Siralama (V_Q5 en ucuz %20 ve V_Q4+V_Q5 en ucuz %40 icinde)
    cond_metrics = {
        "Q_roe": "roe_sn_z",
        "Q_roa": "roa_sn_z",
        "Q_opa": "opa_sn_z",
        "Q_gpa": "gpa_sn_z",
        "Q_f7": "f7",
        "Q_qual": "qual_sn_z",
        "R_lowvol": "vol60_z",
    }
    family_a_vq5 = {
        k: conditional_double_sort(df, col, top_val_quintiles=(4,)) for k, col in cond_metrics.items()
    }
    family_a_top40 = {
        k: conditional_double_sort(df, col, top_val_quintiles=(3, 4)) for k, col in cond_metrics.items()
    }

    # 2. Aile B: Maliyetli Portfoy Simulasyonu (core/portfolio_backtest.py::simulate)
    sel, trap_series = build_portfolio_selections(df)

    fx = pd.read_parquet(RESEARCH / "fx.parquet")
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()
    days = fx.index
    months = sorted(sel["P0_value_top20"].keys())
    d0_of = {t: days[days.searchsorted(t, side="right") - 1] for t in months}

    tickers = sorted({tk for m in sel.values() for lst in m.values() for tk in lst})
    frames = {tk: load_daily(tk) for tk in tickers}
    frames = {tk: f for tk, f in frames.items() if f is not None}
    mat = {k: pd.DataFrame({tk: f[c] for tk, f in frames.items()}).reindex(days)
           for k, c in (("close", "Close"), ("open", "Open"), ("adv", "adv"), ("sigma", "sigma"))}
    mat["adv"], mat["sigma"] = mat["adv"].ffill(), mat["sigma"].ffill()

    macro = pd.read_parquet(RESEARCH / "macro_monthly.parquet")
    macro.index = pd.to_datetime(macro.index).to_period("M")
    rf_daily = pb.policy_rf_daily(macro["policy"], days)
    cpi_idx = (1 + macro["cpi_mom"].fillna(0) / 100).cumprod()
    ref = cpi_idx[CAPITAL_REF.to_period("M")]
    cpi_rel = {t: float(cpi_idx[t.to_period("M")] / ref) for t in months}
    cap = {t: 1e6 * cpi_rel[t] for t in months}
    nonfin_p = df[df["value_sn_z"].notna()]
    universe_liq = {t: np.sort(g["tlvol60"].to_numpy()) for t, g in nonfin_p.groupby("date")}
    bench = nonfin_p.groupby("date")[["fwd_ret_1m", "fwd_ret_1m_usd"]].mean()
    mkt = pb.Market(close=mat["close"], open=mat["open"], adv=mat["adv"], sigma=mat["sigma"], rf_daily=rf_daily)
    ctx = {"months": months, "d0_of": d0_of, "fx": fx, "rf_daily": rf_daily, "cpi_idx": cpi_idx,
           "bench": bench, "cpi_rel": cpi_rel, "universe_liq": universe_liq}

    tr_idx = pd.read_parquet(RESEARCH / "tr_indices.parquet")
    if "date" in tr_idx.columns:
        tr_idx["date"] = pd.to_datetime(tr_idx["date"]).dt.normalize()
        tr_idx = tr_idx.set_index("date")
    else:
        tr_idx.index = pd.to_datetime(tr_idx.index).normalize()
    tr_idx = tr_idx.sort_index()
    xu100_tr_m = {}
    for i, t in enumerate(months[:-1]):
        d_a, d_b = d0_of[t], d0_of[months[i + 1]]
        sub_tr = tr_idx["xu100_tr"].loc[:d_b].dropna()
        sub_a = tr_idx["xu100_tr"].loc[:d_a].dropna()
        if not sub_tr.empty and not sub_a.empty and (d_a - sub_a.index[-1]).days <= 10:
            xu100_tr_m[t] = float(sub_tr.iloc[-1] / sub_a.iloc[-1] - 1.0)
    xu100_tr_s = pd.Series(xu100_tr_m)

    costs = pb.Costs()
    ew_sim = pb.simulate(sel["EW_universe"], months, d0_of, mkt, universe_liq, cap, costs=costs).set_index("date")
    port_names = [k for k in sel.keys() if k != "EW_universe"]
    sims: dict[str, pd.DataFrame] = {}
    for pname in port_names:
        p = attach_benchmarks(pb.simulate(sel[pname], months, d0_of, mkt, universe_liq, cap, costs=costs), ctx)
        p = p.set_index("date")
        p["ew_net"] = ew_sim["port"].reindex(p.index)
        p["active_ew_net"] = p["port"] - p["ew_net"]
        p["xu100_tr"] = xu100_tr_s.reindex(p.index)
        p["active_xu100_tr"] = p["port"] - p["xu100_tr"]
        sims[pname] = p

    family_b: dict[str, dict] = {}
    p0 = sims["P0_value_top20"]
    for pname, p in sims.items():
        family_b[pname] = {}
        for wname, wfn in (("full", lambda idx: idx == idx),
                           ("discovery", lambda idx: idx < SPLIT),
                           ("holdout", lambda idx: idx >= SPLIT)):
            mask = wfn(p.index)
            sub = p[mask].reset_index()
            st = stats(sub)
            port_s = p.loc[mask, "port"]
            act_ew_s = p.loc[mask, "active_ew_net"]
            rf_s = p.loc[mask, "dep"]
            vol_ann = float(port_s.std(ddof=1) * np.sqrt(12) * 100.0)
            act_vol_ann = float(act_ew_s.std(ddof=1) * np.sqrt(12) * 100.0)
            ex_rf = port_s - rf_s
            sharpe = float((ex_rf.mean() / port_s.std(ddof=1)) * np.sqrt(12)) if port_s.std(ddof=1) > 0 else 0.0
            act_nav = (1.0 + act_ew_s.dropna()).cumprod()
            act_ew_mdd = float((act_nav / act_nav.cummax() - 1.0).min() * 100.0) if len(act_nav) else 0.0
            tr_s = trap_series[pname]
            tr_sub = tr_s[wfn(tr_s.index)]

            entry = {
                "vs_ew_net": nw(act_ew_s),
                "vs_xu100_tr": nw(p.loc[mask, "active_xu100_tr"].dropna()),
                "cagr_tl_pct": st.get("cagr_tl_pct"),
                "cagr_usd_pct": st.get("cagr_usd_pct"),
                "vol_ann_pct": round(vol_ann, 2),
                "active_vol_ann_pct": round(act_vol_ann, 2),
                "sharpe": round(sharpe, 2),
                "max_dd_usd_pct": st.get("max_dd_usd_pct"),
                "active_ew_max_dd_pct": round(act_ew_mdd, 2),
                "turnover_pct": st.get("turnover_pct"),
                "cost_ann_pct": st.get("cost_ann_pct"),
                "avg_names": st.get("avg_names"),
                "trap_6m_pct": round(100.0 * float(tr_sub.mean()), 2) if len(tr_sub) else None,
            }
            if pname != "P0_value_top20":
                d_s = (p["port"] - p0["port"]).loc[mask]
                entry["diff_vs_P0"] = nw(d_s)
            family_b[pname][wname] = entry

    p0_disc = family_b["P0_value_top20"]["discovery"]
    p0_hold = family_b["P0_value_top20"]["holdout"]
    for pname in port_names:
        if pname == "P0_value_top20":
            family_b[pname]["verdict"] = "BASELINE"
            continue
        disc_e = family_b[pname]["discovery"]
        hold_e = family_b[pname]["holdout"]
        family_b[pname]["verdict"] = classify_outcome(
            disc_e["diff_vs_P0"], hold_e["diff_vs_P0"], disc_e, hold_e, p0_disc, p0_hold
        )

    result = {
        "as_of": date.today().isoformat(),
        "split": str(SPLIT.date()),
        "coverage_diagnostics": cov,
        "family_A_double_sorts_within_VQ5_top20": family_a_vq5,
        "family_A_double_sorts_within_VQ4_VQ5_top40": family_a_top40,
        "family_B_costed_portfolios": family_b,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    out = ROOT / "data" / "reports" / f"research_quality_value_lowvol_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
