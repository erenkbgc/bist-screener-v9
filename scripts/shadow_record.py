#!/usr/bin/env python3
"""Shadow forward record (paper only): R0 control vs three pre-registered variants.

Pre-registration: docs/research/shadow_record_preregistration.md. Nothing here
trades or changes the live score; it only reads what the daily run already
writes:

  * data/forward_record/decisions.jsonl  ("ranking": the liquidity-filtered,
    non-financial pool with bm/ep/sp/ey, market_cap and inputs.ttm_op_profit)
  * data/forward_record/prices/<TICKER>.csv  (adj_close store)
  * data/bist_history.db universe_snapshot  (sector, latest snapshot <= date)

Variants are built with the SAME functions as the research harness:
fb.winsorize_z per leg (via research_round4_vlab_variants._leg_z), equal-weight
mean + fb.sector_neutralize (_composite), score_ep_floor0 unchanged.

  R0_top20       value_sn top 20%            (control)
  R0_top10       value_sn top 10%            (deep-value concentration)
  vlab_ep_floor0 E/P floored at 0, top 20%
  vlab_op_mcap   E/P -> TTM op profit / mcap, top 20%

Output (append-only): data/forward/shadow_record.csv, one row per
(rebalance_date, variant, ticker). Picks are written once and never rewritten;
only the empty return fields of a row are filled once the next decision's
entry close exists. Report: data/forward/shadow_report.json.

    python scripts/shadow_record.py            # update csv + report
    python scripts/shadow_record.py --report   # report only
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import factor_backtest as fb  # noqa: E402
from core import forward_record as fr  # noqa: E402
from core.pit_panel import FINANCIAL_SECTORS  # noqa: E402
import research_round4_vlab_variants as vv  # noqa: E402

SHADOW_START = "2026-12-01"   # first counted decision month (pre-registered)
CONTROL = "R0_top20"
VARIANTS = {  # name -> top fraction
    "R0_top20": 0.20, "R0_top10": 0.10, "vlab_ep_floor0": 0.20, "vlab_op_mcap": 0.20,
}
EVAL_MONTHS = 24
EVAL_T = 2.0
NW_LAGS = 1

OUT_DIR = ROOT / "data" / "forward"
CSV_PATH = OUT_DIR / "shadow_record.csv"
REPORT_PATH = OUT_DIR / "shadow_report.json"
PRICES_DIR = ROOT / "data" / "forward_record" / "prices"
DB_PATH = ROOT / "data" / "bist_history.db"
COLUMNS = ["rebalance_date", "variant", "ticker", "score", "rank", "n_pool", "n_top",
           "counted", "entry_date", "entry_px", "exit_date", "exit_px", "ret", "recorded_rule"]


# ---------------------------------------------------------------- inputs
def sectors_from_db(as_of: str, db_path: Path = DB_PATH) -> dict[str, str]:
    """Sector per ticker from the latest universe_snapshot on or before as_of."""
    if not Path(db_path).exists():
        return {}
    con = sqlite3.connect(db_path)
    try:
        row = con.execute("SELECT MAX(as_of_date) FROM universe_snapshot WHERE as_of_date <= ?",
                          (as_of,)).fetchone()
        if not row or row[0] is None:
            return {}
        return dict(con.execute("SELECT ticker, sector FROM universe_snapshot WHERE as_of_date = ?",
                                (row[0],)).fetchall())
    finally:
        con.close()


def build_prep(decision: dict, sectors: dict[str, str]) -> pd.DataFrame:
    """The decision's ranking pool as an R0 'prep' frame (one date).

    The pool is already the live liquidity-filtered non-financial universe; any
    financial sector found via the snapshot is dropped again defensively."""
    rows = []
    for r in decision.get("ranking") or []:
        inp = r.get("inputs") or {}
        rows.append({"date": pd.Timestamp(decision["rebalance_date"]), "ticker": r["ticker"],
                     "sector": r.get("sector") or sectors.get(r["ticker"]) or "UNKNOWN",
                     "mcap": r.get("market_cap"),
                     **{k: r.get(k) for k in ("bm", "ep", "sp", "ey")},
                     "ttm_op_profit": inp.get("ttm_op_profit")})
    prep = pd.DataFrame(rows, columns=["date", "ticker", "sector", "mcap", "bm", "ep", "sp", "ey",
                                       "ttm_op_profit"])
    prep = prep[~prep["sector"].isin(FINANCIAL_SECTORS)].reset_index(drop=True)
    for c in ("mcap", "bm", "ep", "sp", "ey", "ttm_op_profit"):
        prep[c] = pd.to_numeric(prep[c], errors="coerce").astype(float)
    for k in ("bm", "ep", "sp", "ey"):  # fb.prepare: per-month winsorize_z, all legs +1-signed
        prep[f"{k}_z"] = vv._leg_z(prep, prep[k])
    return prep


def variant_scores(prep: pd.DataFrame) -> dict[str, pd.Series]:
    r0 = vv._composite(prep, vv._r0_legs(prep))
    legs = vv._r0_legs(prep)
    legs["ep"] = vv._leg_z(prep, prep["ttm_op_profit"] / prep["mcap"])
    return {"R0_top20": r0, "R0_top10": r0,
            "vlab_ep_floor0": vv.score_ep_floor0(None, prep, {}),
            "vlab_op_mcap": vv._composite(prep, legs)}


def picks(prep: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Top fraction per variant: n_top = max(1, round(n_scored x pct)) (core/rotation)."""
    out = {}
    for name, s in variant_scores(prep).items():
        df = pd.DataFrame({"ticker": prep["ticker"], "score": s}).dropna(subset=["score"])
        df = df.sort_values(["score", "ticker"], ascending=[False, True]).reset_index(drop=True)
        n_top = max(1, int(round(len(df) * VARIANTS[name]))) if len(df) else 0
        top = df.head(n_top).copy()
        top["rank"] = np.arange(1, len(top) + 1)
        top["n_pool"], top["n_top"] = len(df), n_top
        out[name] = top
    return out


# ---------------------------------------------------------------- prices
def next_close(ticker: str, after: str, prices_dir: Path = PRICES_DIR) -> tuple[str | None, float | None]:
    """First adj_close strictly after `after` (next-close fill)."""
    p = Path(prices_dir) / f"{ticker}.csv"
    if not p.exists():
        return None, None
    df = pd.read_csv(p, parse_dates=["date"])
    df = df[(df["date"] > pd.Timestamp(after)) & df["adj_close"].notna()].sort_values("date")
    if df.empty:
        return None, None
    return df["date"].iloc[0].date().isoformat(), float(df["adj_close"].iloc[0])


# ---------------------------------------------------------------- record
def load_record(path: Path = CSV_PATH) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(path, dtype={"rebalance_date": str, "entry_date": str, "exit_date": str})


def update_record(decisions: list[dict], path: Path = CSV_PATH, prices_dir: Path = PRICES_DIR,
                  sector_fn=sectors_from_db) -> pd.DataFrame:
    ok = sorted((d for d in decisions if fr.is_ok(d) and d.get("ranking")),
                key=lambda d: d["rebalance_date"])
    rec = load_record(path)
    have = set(zip(rec["rebalance_date"], rec["variant"]))
    new_rows = []
    for d in ok:
        dt = d["rebalance_date"]
        todo = [v for v in VARIANTS if (dt, v) not in have]
        if not todo:
            continue
        prep = build_prep(d, sector_fn(dt))
        for name, top in picks(prep).items():
            if name not in todo:
                continue
            for r in top.itertuples():
                new_rows.append({"rebalance_date": dt, "variant": name, "ticker": r.ticker,
                                 "score": round(float(r.score), 6), "rank": int(r.rank),
                                 "n_pool": int(r.n_pool), "n_top": int(r.n_top),
                                 "counted": dt >= SHADOW_START,
                                 "recorded_rule": d.get("rule_version")})
    if new_rows:
        rec = pd.concat([rec, pd.DataFrame(new_rows)], ignore_index=True)
    rec = rec.reindex(columns=COLUMNS)

    # Fill returns: hold from next close after d_t to next close after d_{t+1}.
    dates = [d["rebalance_date"] for d in ok]
    nxt = dict(zip(dates, dates[1:]))
    for i in rec.index[rec["ret"].isna()]:
        dt = rec.at[i, "rebalance_date"]
        if dt not in nxt:
            continue
        tk = rec.at[i, "ticker"]
        if pd.isna(rec.at[i, "entry_px"]):
            ed, ep = next_close(tk, dt, prices_dir)
            rec.at[i, "entry_date"], rec.at[i, "entry_px"] = ed, ep
        xd, xp = next_close(tk, nxt[dt], prices_dir)
        if xp is None or pd.isna(rec.at[i, "entry_px"]):
            continue  # no exit price yet / missing: stays empty, counted as missing in report
        rec.at[i, "exit_date"], rec.at[i, "exit_px"] = xd, xp
        rec.at[i, "ret"] = xp / float(rec.at[i, "entry_px"]) - 1.0
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    rec.to_csv(path, index=False)
    return rec


# ---------------------------------------------------------------- report
def monthly_returns(rec: pd.DataFrame, counted_only: bool = True) -> pd.DataFrame:
    """Equal-weight portfolio return per (rebalance_date, variant) over picks with a
    realized return; months where any variant still lacks returns are left out."""
    r = rec.copy()
    if counted_only:
        r = r[r["counted"].astype(str).str.lower() == "true"]
    r = r[r["exit_date"].notna() & (r["exit_date"].astype(str) != "nan")]
    if r.empty:
        return pd.DataFrame(columns=list(VARIANTS))
    m = r.groupby(["rebalance_date", "variant"])["ret"].mean().unstack("variant")
    return m.reindex(columns=list(VARIANTS)).dropna()


def evaluate(monthly: pd.DataFrame) -> dict:
    out = {"control": CONTROL, "months": int(len(monthly)), "eval_months": EVAL_MONTHS,
           "rule": f"after {EVAL_MONTHS} counted months: mean D>0, NW t(lag {NW_LAGS})>={EVAL_T}, "
                   "D>0 in both 12-month halves", "variants": {}}
    for v in VARIANTS:
        if v == CONTROL:
            continue
        d = (monthly[v] - monthly[CONTROL]) if len(monthly) else pd.Series(dtype=float)
        m, t, n = fb.newey_west_t(d.to_numpy(), NW_LAGS) if len(d) >= 3 else (
            float(d.mean()) if len(d) else float("nan"), float("nan"), len(d))
        res = {"n": int(n), "mean_d_pct": round(100 * m, 3) if np.isfinite(m) else None,
               "cum_d_pct": round(100 * float(d.sum()), 3), "nw_t": round(t, 2) if np.isfinite(t) else None,
               "status": "pending"}
        if len(d) >= EVAL_MONTHS:
            w = d.iloc[:EVAL_MONTHS]
            mw, tw, _ = fb.newey_west_t(w.to_numpy(), NW_LAGS)
            half = EVAL_MONTHS // 2
            ok = mw > 0 and tw >= EVAL_T and w.iloc[:half].mean() > 0 and w.iloc[half:].mean() > 0
            res.update(status="PASS" if ok else "FAIL", eval_mean_d_pct=round(100 * mw, 3),
                       eval_nw_t=round(tw, 2))
        out["variants"][v] = res
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", action="store_true", help="report only, do not update the csv")
    a = ap.parse_args(argv)
    rec = load_record() if a.report else update_record(fr.load_decisions())
    rep = evaluate(monthly_returns(rec))
    rep["rows"] = int(len(rec))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
