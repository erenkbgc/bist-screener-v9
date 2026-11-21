#!/usr/bin/env python3
"""Valuation round 2 (docs/research/valuation_round2_preregistration.md).

Candidates replace one leg of value_sn and keep everything else:
  V2B_ep_xdt  -- E/P with deferred tax removed
  V2A_bm_tan  -- tangible B/M (equity - intangibles - goodwill)

Steps:
  1. Rebuild the quarterly table from the raw vendor cache with three extra items
     (deferred_tax, intangibles, goodwill) through the same pipeline as the baseline
     (C1 TTM, IAS 29 undo, TTM bridge). Item maps are extended only inside this script.
  2. Parity: the existing quarterly columns and the panel's ep/bm re-derived from the
     rebuilt table must match the baseline panel, else stop.
  3. Build each candidate's value_sn_z with the unchanged composite code and evaluate it
     with the round 1 machinery under the fixed pass rule.

    .venv/bin/python scripts/research_valuation_round2.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import research_valuation_round1 as r1  # noqa: E402
from backtest_factor_model import FACTORS, add_composites  # noqa: E402
from core import factor_backtest as fb  # noqa: E402
from core import pit_panel  # noqa: E402
from diagnose_crashed_picks import month_end  # noqa: E402
from research_portfolio_backtest import RESEARCH  # noqa: E402
from research_quant_review import LEDGER_PATH, variant_matrix  # noqa: E402

AS_OF = "2026-11-22"
EXTRA_INC = {"deferred_tax": ("Ertelenmiş Vergi Geliri (Gideri)",)}
EXTRA_BS = {"intangibles": ("Maddi Olmayan Duran Varlıklar",), "goodwill": ("Şerefiye",)}
CANDIDATES = ("V2B_ep_xdt", "V2A_bm_tan")
ITEMS_DIR = RESEARCH / "r2_items"


# ---------------------------------------------------------------------------
# 1. Quarterly table with extra items
# ---------------------------------------------------------------------------
def rebuild_quarterly_with_items() -> pd.DataFrame:
    path = ITEMS_DIR / "quarterly.parquet"
    if path.exists():
        return pd.read_parquet(path)
    import build_pit_panel as bpp

    pit_panel.INC_ITEMS.update(EXTRA_INC)
    pit_panel.BS_ITEMS.update(EXTRA_BS)
    try:
        sector_rows = json.loads((ROOT / "config" / "fintables_ticker_sektor.json").read_text(encoding="utf-8"))
        sectors = {r["ticker"]: r["sektor"] for r in sector_rows}
        tickers = sorted(f.stem for f in bpp.RAW.glob("*.pkl")
                         if f.stem in sectors and sectors[f.stem] not in pit_panel.FINANCIAL_SECTORS)
        raw = {tk: r for tk in tickers if (r := bpp.load_cached_raw(tk)) is not None}
        bpp.build_panel_from_raw(raw, sectors, research_dir=RESEARCH, out_dir=ITEMS_DIR,
                                 write_prices_and_events=False)
    finally:
        for k in EXTRA_INC:
            pit_panel.INC_ITEMS.pop(k, None)
        for k in EXTRA_BS:
            pit_panel.BS_ITEMS.pop(k, None)
    return pd.read_parquet(path)


def parity_quarterly(q_new: pd.DataFrame, q_base: pd.DataFrame) -> dict:
    cols = [c for c in q_base.columns if c in q_new.columns and c not in ("ticker", "period")
            and pd.api.types.is_numeric_dtype(q_base[c])]
    m = q_base.merge(q_new, on=["ticker", "period"], suffixes=("_b", "_n"), how="outer", indicator=True)
    out = {"rows_base": len(q_base), "rows_new": len(q_new),
           "only_base": int((m["_merge"] == "left_only").sum()), "only_new": int((m["_merge"] == "right_only").sum())}
    both = m[m["_merge"] == "both"]
    worst = 0.0
    for c in cols:
        a, b = both[f"{c}_b"].astype(float), both[f"{c}_n"].astype(float)
        diff = ((a - b).abs() / b.abs().clip(lower=1.0)).where(a.notna() & b.notna(), 0.0)
        mismatch_nan = int((a.isna() != b.isna()).sum())
        worst = max(worst, float(diff.max()) if len(diff) else 0.0)
        if mismatch_nan:
            out[f"nan_mismatch_{c}"] = mismatch_nan
    out["max_rel_diff"] = worst
    out["ok"] = out["only_base"] == 0 and out["only_new"] == 0 and worst < 1e-9 and not any(
        k.startswith("nan_mismatch") for k in out)
    return out


# ---------------------------------------------------------------------------
# 2. Candidate legs
# ---------------------------------------------------------------------------
def candidate_legs(panel: pd.DataFrame, q: pd.DataFrame) -> pd.DataFrame:
    """Adds ep_base/bm_base (re-derived R0 legs, for parity) and ep_xdt/bm_tan."""
    cols = ["ticker", "period", "ttm_ni_parent", "ttm_net_income", "ttm_deferred_tax",
            "equity_parent", "equity", "intangibles", "goodwill"]
    qq = q[[c for c in cols if c in q.columns]].rename(columns={"period": "stmt_period"})
    p = panel.merge(qq, on=["ticker", "stmt_period"], how="left")
    mcap = p["mcap"].astype(float)

    ni_p, ni_t = p["ttm_ni_parent"], p["ttm_net_income"]
    use_parent = ni_p.notna() & np.isfinite(ni_p)
    ni = ni_p.where(use_parent, ni_t)
    share = (ni_p / ni_t).where(use_parent & ni_t.notna() & (ni_t != 0), 1.0).clip(0.0, 1.0)
    share = share.where(use_parent, 1.0)
    dt = p["ttm_deferred_tax"].fillna(0.0)
    p["ep_base"] = ni / mcap
    p["ep_xdt"] = (ni - share * dt) / mcap

    eq = p["equity_parent"].where(p["equity_parent"].notna() & np.isfinite(p["equity_parent"]), p["equity"])
    p["bm_base"] = (eq / mcap).where(eq > 0)
    tan = eq - p["intangibles"].fillna(0.0) - p["goodwill"].fillna(0.0)
    p["bm_tan"] = (tan / mcap).where(tan > 0)
    return p


def leg_parity(p: pd.DataFrame) -> dict:
    out = {}
    for leg in ("ep", "bm"):
        a, b = p[leg], p[f"{leg}_base"]
        both = a.notna() & b.notna()
        rel = ((a - b).abs() / a.abs().clip(lower=1e-12))[both]
        out[leg] = {"rows": int(len(p)), "both": int(both.sum()),
                    "nan_mismatch": int((a.isna() != b.isna()).sum()),
                    "share_rel_diff_gt_1e6": round(float((rel > 1e-6).mean()), 6) if both.any() else None}
    out["ok"] = all(v["nan_mismatch"] == 0 and (v["share_rel_diff_gt_1e6"] or 0) == 0 for v in out.values()
                    if isinstance(v, dict))
    return out


def prepared_scores(raw_panel: pd.DataFrame, market_m: pd.DataFrame) -> pd.Series:
    """value_sn_z exactly as r1.load_prepared_panel builds R0, keyed by (date, ticker)."""
    raw = raw_panel.copy()
    raw["date"] = month_end(raw["date"])
    raw = pit_panel.add_usd_returns(raw, market_m)
    df = add_composites(fb.prepare(raw, FACTORS, liq_drop_pct=0.3))
    df = df[df["value_sn_z"].notna()]
    return df.set_index(["date", "ticker"])["value_sn_z"]


def descriptive(p: pd.DataFrame) -> dict:
    out = {}
    for name, a, b in (("deferred_tax", "ep_xdt", "ep"), ("tangible_book", "bm_tan", "bm")):
        chg = (p[a] - p[b]).abs() > 1e-12
        out[name] = {"leg_changed_share": round(float(chg.mean()), 4),
                     "leg_nan_share_candidate": round(float(p[a].isna().mean()), 4),
                     "leg_nan_share_r0": round(float(p[b].isna().mean()), 4)}
    yr = pd.to_datetime(p["date"]).dt.year
    out["deferred_tax_abs_share_of_ni_by_year"] = (
        (p["ttm_deferred_tax"].abs() / p["ttm_ni_parent"].abs()).replace(np.inf, np.nan)
        .groupby(yr).median().round(3).dropna().to_dict())
    return out


# ---------------------------------------------------------------------------
# 3. Evaluation
# ---------------------------------------------------------------------------
def evaluate(panel_name: str, q: pd.DataFrame, macro, eurobond, fx, frames_cache, n_sel, var_sr) -> dict:
    base = pd.read_parquet(RESEARCH / panel_name)
    p = candidate_legs(base, q)
    parity = leg_parity(p)
    if not parity["ok"]:
        return {"parity": parity, "stopped": "re-derived ep/bm do not match the panel"}

    market_m = pit_panel.monthly_market(pd.read_parquet(RESEARCH / "fx.parquet"))
    df = r1.load_prepared_panel(RESEARCH / panel_name)
    scores = {}
    for cand, leg, new in (("V2B_ep_xdt", "ep", "ep_xdt"), ("V2A_bm_tan", "bm", "bm_tan")):
        alt = base.copy()
        alt[leg] = p[new].to_numpy()
        scores[cand] = prepared_scores(alt, market_m)

    key = pd.MultiIndex.from_arrays([df["date"], df["ticker"]])
    for cand, s in scores.items():
        df[cand] = s.reindex(key).to_numpy()

    def signals(d, *_args, **_kw):
        out = d.copy()
        out["R0"] = out["value_sn_z"]
        return out

    r1.build_all_signals = signals
    r1.CANDIDATES = CANDIDATES
    r1.ALL_METHODS = ("R0", *CANDIDATES)
    res = r1.run_panel_evaluation(df, q, macro, eurobond, fx, frames_cache, n_sel=n_sel, var_sr=var_sr)
    res[f"dsr_at_N_sel_{n_sel}"] = res.pop("dsr_at_N_sel_89")
    res["parity"] = parity
    res["coverage_vs_R0"] = {c: round(float(df[c].notna().mean()), 4) for c in CANDIDATES}
    res["descriptive"] = descriptive(p)
    return res


def main() -> None:
    ledger = json.loads(LEDGER_PATH.read_text())
    n_sel = sum(s["trials"] for s in ledger["studies"] if s["family"] == "stock_selection")

    q_base = pd.read_parquet(RESEARCH / "quarterly.parquet")
    print("Rebuilding quarterly table with extra items...", flush=True)
    q = rebuild_quarterly_with_items()
    qpar = parity_quarterly(q, q_base)
    print(f"Quarterly parity: {qpar}", flush=True)
    if not qpar["ok"]:
        out = {"as_of": AS_OF, "stopped": "quarterly parity failed", "quarterly_parity": qpar}
        (ROOT / "data" / "reports" / f"research_valuation_round2_{AS_OF}.json").write_text(json.dumps(out, indent=2))
        raise SystemExit("quarterly parity failed; see report")
    coverage = {c: round(float(q[c].notna().mean()), 4) for c in ("ttm_deferred_tax", "intangibles", "goodwill")}

    macro = pd.read_parquet(RESEARCH / "macro_monthly.parquet")
    eurobond = pd.read_parquet(RESEARCH / "eurobond_monthly.parquet")
    fx = pd.read_parquet(RESEARCH / "fx.parquet")
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()

    df0 = r1.load_prepared_panel(RESEARCH / "factors_monthly.parquet")
    vm = variant_matrix(df0).dropna()
    sr_vm = vm.mean() / vm.std(ddof=1)
    var_sr = float(sr_vm.var(ddof=1))

    frames_cache: dict[str, pd.DataFrame] = {}
    print(f"Evaluating primary lag75 (N_sel={n_sel})...", flush=True)
    primary = evaluate("factors_monthly.parquet", q, macro, eurobond, fx, frames_cache, n_sel, var_sr)
    print("Evaluating KAP-date panel...", flush=True)
    kap = evaluate("factors_monthly_kapdates.parquet", q, macro, eurobond, fx, frames_cache, n_sel, var_sr)

    result = {"as_of": AS_OF, "trial_ledger_N_sel": n_sel, "var_sr_monthly": round(var_sr, 5),
              "quarterly_parity": qpar, "item_coverage_quarterly": coverage,
              "primary_lag75": primary, "sensitivity_kapdates": kap}
    out_path = ROOT / "data" / "reports" / f"research_valuation_round2_{AS_OF}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    for name, res in (("PRIMARY lag75", primary), ("KAP dates", kap)):
        print(f"\n=== {name} ===")
        if "stopped" in res:
            print("STOPPED:", res["stopped"], res["parity"])
            continue
        for m in CANDIDATES:
            v = res["verdicts"][m]
            print(f"{m}: D_disc {v['disc_D_ann_pct']:+.2f}% (t {v['disc_t']:+.2f}) | "
                  f"D_hold {v['hold_D_ann_pct']:+.2f}% (t {v['hold_t']:+.2f}) | "
                  f"DD diff {v['hold_dd_usd_diff_vs_R0_pp']:+.1f} pp | {v['verdict']}")
    print(f"\nJSON: {out_path}")


if __name__ == "__main__":
    main()
