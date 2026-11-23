#!/usr/bin/env python3
"""Alpha atfi, coklu test duzeltmesi ve maliyet/limit stresi
(docs/research/quant_review_followups_preregistration.md).

A: CAPM (BIST 100 TR), panel faktor modeli, Brinson, banka egilimi, bootstrap.
B: deneme defteri (data/research/trial_ledger.json), Deflated Sharpe, PBO (CSCV).
C: maliyet carpani x sermaye x limit kurali izgarasi, basabas maliyet carpani.
Canli kural degismez.

    python scripts/research_quant_review.py
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
from core import research_stats as rs  # noqa: E402
from research_long_term import load  # noqa: E402
from research_portfolio_backtest import RESEARCH, SPLIT, attach_benchmarks, build  # noqa: E402
from research_total_return_benchmarks import tr_indices, window_returns  # noqa: E402

XBANK_PATH = RESEARCH / "xbank_tr.parquet"
LEDGER_PATH = RESEARCH / "trial_ledger.json"
LIMIT_PCT = 0.095
LEG = 0.30
MIN_NAMES = 20
SIGNALS = {
    "value_sn": ["value_sn_z"], "value_raw": ["value_z"], "bm": ["bm_z"], "ep": ["ep_z"], "sp": ["sp_z"],
    "ey": ["ey_z"], "bm_ep_ey": ["bm_z", "ep_z", "ey_z"], "bm_ep": ["bm_z", "ep_z"], "gpa": ["gpa_z"],
    "roe": ["roe_z"], "mom": ["mom_12_1_z"], "lowvol": ["-vol60_z"], "sue": ["sue_z"], "small": ["-size_z"],
    "value_sn_gpa": ["value_sn_z", "gpa_z"], "value_sn_lowvol": ["value_sn_z", "-vol60_z"],
}
TOPS = (0.1, 0.2, 0.3)


def xbank_tr(refresh: bool = False) -> pd.Series:
    """BIST Bankalar getiri endeksi (XBANK_CFNNTLTL), gunluk; onbellek xbank_tr.parquet."""
    if XBANK_PATH.exists() and not refresh:
        return pd.read_parquet(XBANK_PATH)["xbank_tr"]
    import borsapy as bp
    h = bp.Index("XBANK_CFNNTLTL").history(period="max")
    idx = pd.to_datetime(h.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    s = pd.Series(h["Close"].astype(float).to_numpy(), index=idx.normalize(), name="xbank_tr")
    s.to_frame().to_parquet(XBANK_PATH)
    return s


def nw(x: pd.Series) -> dict:
    m, t, n = fb.newey_west_t(x, 6)
    return {"months": n, "ann_pct": round(1200 * m, 2), "t": round(t, 2)}


def reg(y: pd.Series, X: pd.DataFrame) -> dict:
    out = rs.ols_nw(y, X)
    if "coef" not in out:
        return out
    return {"n": out["n"], "alpha_ann_pct": round(1200 * out["coef"]["alpha"], 2),
            "t_alpha": round(out["t"]["alpha"], 2), "r2": round(out["r2"], 3),
            "betas": {k: round(v, 3) for k, v in out["coef"].items() if k != "alpha"},
            "t_betas": {k: round(v, 2) for k, v in out["t"].items() if k != "alpha"}}


def windows(s: pd.Series | pd.DataFrame) -> dict:
    return {"full": s, "discovery": s[s.index < SPLIT], "holdout": s[s.index >= SPLIT]}


# ------------------------------------------------------------------ A
def panel_factors(df: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for t, g in df.groupby("date"):
        g = g.dropna(subset=["fwd_ret_1m"])

        def ls(col: str, high_long: bool) -> float:
            h = g.dropna(subset=[col])
            if len(h) < MIN_NAMES:
                return np.nan
            lo, hi = h[col].quantile(LEG), h[col].quantile(1 - LEG)
            top, bot = h.loc[h[col] >= hi, "fwd_ret_1m"].mean(), h.loc[h[col] <= lo, "fwd_ret_1m"].mean()
            return top - bot if high_long else bot - top

        rows[t] = {"ew": g["fwd_ret_1m"].mean(), "SMB": ls("mcap", False), "WML": ls("mom_12_1", True),
                   "LV": ls("vol60", False), "HML_sn": ls("value_sn_z", True)}
    return pd.DataFrame.from_dict(rows, orient="index").sort_index()


def part_a(p: pd.DataFrame, df: pd.DataFrame, held: dict) -> dict:
    out = {}
    h = p[p.index >= SPLIT]
    a1 = reg(h["port"] - h["dep"], pd.DataFrame({"mkt": h["xu100_tr"] - h["dep"]}))
    out["A1_capm_xu100_tr"] = {**a1, "label": ("POSITIVE_ALPHA" if a1["alpha_ann_pct"] > 0 and a1["t_alpha"] > 2
                                               else "POSITIVE_NOT_SIGNIFICANT" if a1["alpha_ann_pct"] > 0
                                               else "NO_ALPHA")}

    f = panel_factors(df).reindex(p.index)
    X = pd.DataFrame({"MKT": f["ew"] - p["dep"], "SMB": f["SMB"], "WML": f["WML"], "LV": f["LV"]})
    y = p["port"] - p["dep"]
    a2 = {"A2a": {w: reg(y.loc[s.index], s) for w, s in windows(X).items()},
          "A2b": {w: reg(y.loc[s.index], s) for w, s in windows(X.assign(HML_sn=f["HML_sn"])).items()}}
    hh = a2["A2a"]["holdout"]
    a2["label_A2a_holdout"] = ("EDGE_NOT_EXPLAINED_BY_SIZE_MOM_LOWVOL" if hh["alpha_ann_pct"] > 0 and hh["t_alpha"] > 2
                               else "EDGE_WEAK_AFTER_CONTROLS" if hh["alpha_ann_pct"] > 0
                               else "EDGE_EXPLAINED_BY_CONTROLS")
    out["A2_factor_model"] = a2

    br = {}
    for t, g in df.groupby("date"):
        if t in held and held[t]:
            br[t] = rs.brinson(g.rename(columns={"fwd_ret_1m": "ret"})[["ticker", "sector", "ret"]], set(held[t]))
    br = pd.DataFrame.from_dict(br, orient="index", columns=["allocation", "selection"]).sort_index()
    a3 = {}
    for w, s in windows(br).items():
        al, se = nw(s["allocation"]), nw(s["selection"])
        a3[w] = {"allocation": al, "selection": se, "total_ann_pct": round(al["ann_pct"] + se["ann_pct"], 2)}
    hb = a3["holdout"]
    tot = hb["total_ann_pct"]
    a3["label_holdout"] = ("NO_EDGE" if tot <= 0
                           else "SELECTION_DRIVEN" if hb["selection"]["ann_pct"] > 0 and hb["selection"]["ann_pct"] > 0.5 * tot
                           else "ALLOCATION_DRIVEN" if hb["allocation"]["ann_pct"] > 0.5 * tot
                           else "MIXED")
    out["A3_brinson_vs_ew"] = a3

    gap = h["port"] - h["xu100_tr"]
    a4 = reg(gap, pd.DataFrame({"bank_minus_xu100": h["xbank_tr"] - h["xu100_tr"]}))
    raw = nw(gap)
    a4 = {"raw_gap": raw, **a4}
    a4["label"] = ("NO_GAP" if raw["ann_pct"] >= 0 else "BANK_TILT_EXPLAINS_GAP" if a4["alpha_ann_pct"] > 0
                   else "GAP_PERSISTS")
    out["A4_bank_gap"] = a4

    out["A5_bootstrap_holdout_95"] = {
        "vs_ew_net": {**nw(h["port"] - h["ew_net"]), "ci_ann_pct": rs.stationary_bootstrap_ci(h["port"] - h["ew_net"])},
        "vs_xu100_tr": {**nw(gap), "ci_ann_pct": rs.stationary_bootstrap_ci(gap)},
    }
    return out


# ------------------------------------------------------------------ B
def signal_value(g: pd.DataFrame, cols: list[str]) -> pd.Series:
    parts = [(-g[c[1:]] if c.startswith("-") else g[c]) for c in cols]
    return pd.concat(parts, axis=1).mean(axis=1, skipna=True)


def variant_matrix(df: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for t, g in df.groupby("date"):
        g = g.dropna(subset=["fwd_ret_1m"])
        univ = g["fwd_ret_1m"].mean()
        row = {}
        for name, cols in SIGNALS.items():
            s = signal_value(g, cols)
            ok = s.notna()
            for q in TOPS:
                if ok.sum() < MIN_NAMES:
                    row[f"{name}|{q}"] = np.nan
                    continue
                r = s[ok].rank(ascending=False, pct=True)
                row[f"{name}|{q}"] = g.loc[r[r <= q].index, "fwd_ret_1m"].mean() - univ
        rows[t] = row
    return pd.DataFrame.from_dict(rows, orient="index").sort_index()


def part_b(active_net: pd.Series, df: pd.DataFrame) -> dict:
    ledger = json.loads(LEDGER_PATH.read_text())
    fam: dict[str, int] = {}
    for s in ledger["studies"]:
        fam[s["family"]] = fam.get(s["family"], 0) + s["trials"]
    n_sel = fam["stock_selection"]

    vm = variant_matrix(df)
    full = vm.dropna()
    sr = full.mean() / full.std(ddof=1)
    var_sr = float(sr.var(ddof=1))
    dsr = {n: rs.deflated_sharpe(active_net, n, var_sr) for n in sorted({n_sel, 10, 26, 50, 100, 200})}
    main = dsr[n_sel]
    pbo = rs.pbo_cscv(full, n_blocks=16)
    own = "value_sn|0.2"
    return {
        "ledger": {"families": fam, "n_studies": len(ledger["studies"]), "N_sel": n_sel},
        "variants": {"n": vm.shape[1], "months_total": len(vm), "months_complete": len(full),
                     "var_sr_monthly": round(var_sr, 5),
                     "r0_variant_rank_full": int((sr > sr[own]).sum() + 1),
                     "top5_sr_full": {k: round(v, 3) for k, v in sr.sort_values(ascending=False).head(5).items()}},
        "B2_dsr": {str(n): {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()} for n, d in dsr.items()},
        "B2_label": "SIGNIFICANT_AFTER_TRIALS" if main["dsr"] >= 0.95 else "NOT_SIGNIFICANT_AFTER_TRIALS",
        "B3_pbo": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in pbo.items()},
        "B3_label": ("LOW_OVERFIT_RISK" if pbo["pbo"] <= 0.2 else "MODERATE" if pbo["pbo"] <= 0.5
                     else "HIGH_OVERFIT_RISK"),
    }


# ------------------------------------------------------------------ C
def part_c(sel: dict, mkt: pb.Market, ctx: dict) -> dict:
    months = ctx["months"]

    def sim(variant: str, capital: float, mult: float, limit: bool) -> pd.Series:
        cap = {t: capital * ctx["cpi_rel"][t] for t in months}
        p = pb.simulate(sel[variant], months, ctx["d0_of"], mkt, ctx["universe_liq"], cap,
                        costs=pb.Costs(mult=mult), limit_pct=LIMIT_PCT if limit else None)
        return p.set_index("date")

    def active(capital: float, mult: float, limit: bool) -> dict:
        r, e = sim("P0", capital, mult, limit), sim("EW", capital, mult, limit)
        a = (r["port"] - e["port"]).dropna()
        return {"discovery": nw(a[a.index < SPLIT]), "holdout": nw(a[a.index >= SPLIT]),
                "r0_cost_ann_pct": round(1200 * float(r.loc[r.index >= SPLIT, "cost"].mean()), 2),
                "ew_cost_ann_pct": round(1200 * float(e.loc[e.index >= SPLIT, "cost"].mean()), 2)}

    grid = {}
    for mult in (1, 2, 3):
        for cname, capital in (("1M", 1e6), ("10M", 1e7), ("50M", 5e7)):
            for limit in (False, True):
                grid[f"x{mult}|{cname}|{'limit' if limit else 'nolimit'}"] = active(capital, mult, limit)
                print(f"  C x{mult} {cname} limit={limit}", flush=True)
    prim = grid["x3|10M|limit"]
    d, h = prim["discovery"]["ann_pct"], prim["holdout"]
    label = ("COST_ROBUST" if d > 0 and h["ann_pct"] > 0 and h["t"] > 2
             else "COST_ROBUST_NOT_SIGNIFICANT" if d > 0 and h["ann_pct"] > 0 else "COST_FRAGILE")
    breakeven = "> 8"
    for mult in range(1, 9):
        key = f"x{mult}|1M|limit"
        res = grid.get(key) or active(1e6, mult, True)
        if res["holdout"]["ann_pct"] <= 0:
            breakeven = mult
            break
    return {"grid": grid, "primary": "x3|10M|limit", "label": label, "breakeven_mult_1M_limit": breakeven}


def main() -> None:
    sel, mkt, ctx = build(include_universe=True)
    months = ctx["months"]
    df = load()
    df = df[df["value_sn_z"].notna()].copy()

    cap = {t: 1e6 * ctx["cpi_rel"][t] for t in months}
    strat = attach_benchmarks(pb.simulate(sel["P0"], months, ctx["d0_of"], mkt, ctx["universe_liq"], cap), ctx)
    ew = pb.simulate(sel["EW"], months, ctx["d0_of"], mkt, ctx["universe_liq"], cap).set_index("date")
    tr = tr_indices()
    strat["xu100_tr"] = window_returns(tr["xu100_tr"], strat, ctx)
    strat["xbank_tr"] = window_returns(xbank_tr(), strat, ctx)
    p = strat.set_index("date")
    p["ew_net"] = ew["port"].reindex(p.index)

    baseline = {"holdout_vs_ew_net": nw((p["port"] - p["ew_net"])[p.index >= SPLIT]),
                "holdout_vs_xu100_tr": nw((p["port"] - p["xu100_tr"])[p.index >= SPLIT])}
    print("Baseline:", baseline, flush=True)

    result = {"as_of": date.today().isoformat(), "months": [str(months[0].date()), str(months[-1].date())],
              "baseline": baseline}
    result["A"] = part_a(p, df, sel["P0"])
    print("A done", flush=True)
    result["B"] = part_b((p["port"] - p["ew_net"]).dropna(), df)
    print("B done", flush=True)
    result["C"] = part_c(sel, mkt, ctx)

    labels = {"A1": result["A"]["A1_capm_xu100_tr"]["label"], "A2a": result["A"]["A2_factor_model"]["label_A2a_holdout"],
              "A3": result["A"]["A3_brinson_vs_ew"]["label_holdout"], "A4": result["A"]["A4_bank_gap"]["label"],
              "B2": result["B"]["B2_label"], "B3": result["B"]["B3_label"], "C": result["C"]["label"]}
    result["labels"] = labels
    out = ROOT / "data" / "reports" / f"research_quant_review_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(json.dumps(labels, indent=1))
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
