"""CEI (composite equity issuance, bonus-neutral) and R0 top-10% (pre-registered).

CEI_5y(i, t) = sum over capital events e of i with t-60m < date_e <= t of
    log((1 + R_e + B_e + BD_e) / (1 + B_e + BD_e))
where R = rights issue %, B = bonus from capital %, BD = bonus from dividend %
(borsapy splits table, effective dates). Bonus issues do not change firm value,
so they are removed; rights issues (new money) remain. Stocks with no recorded
event in the window get 0. Signal = -CEI (issuers expected to underperform,
Daniel and Titman 2006; Hanauer and Lauterbach for emerging markets).

    python scripts/research_cei_top10.py
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

import research_round4_vlab as h  # noqa: E402
from core import factor_backtest as fb  # noqa: E402

BATCH = "cei_top10"
WINDOW_MONTHS = 60
DOC_DIR = ROOT / "docs" / "research" / "cei_top10"


def event_issuance(splits: pd.DataFrame | None) -> pd.DataFrame:
    """One row per capital event: date, log bonus-neutral issuance."""
    if splits is None or len(splits) == 0:
        return pd.DataFrame(columns=["date", "iss"])
    s = splits.copy()
    idx = pd.to_datetime(s.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    num = lambda c: pd.to_numeric(s.get(c, 0), errors="coerce").fillna(0.0).to_numpy() / 100.0  # noqa: E731
    r, b, bd = num("RightsIssue"), num("BonusFromCapital"), num("BonusFromDividend")
    iss = np.log((1.0 + r + b + bd) / (1.0 + b + bd))
    return pd.DataFrame({"date": idx.normalize(), "iss": iss}).sort_values("date").reset_index(drop=True)


def cei_for_dates(events: pd.DataFrame, dates: pd.Series, window_months: int = WINDOW_MONTHS) -> np.ndarray:
    out = np.zeros(len(dates), dtype=float)
    if events.empty:
        return out
    ed = events["date"].to_numpy(dtype="datetime64[ns]")
    ev = events["iss"].to_numpy(dtype=float)
    for i, t in enumerate(pd.to_datetime(dates)):
        lo = (t - pd.DateOffset(months=window_months)).to_datetime64()
        m = (ed > lo) & (ed <= t.to_datetime64())
        out[i] = float(ev[m].sum())
    return out


def load_events(raw_dirs: list[Path]) -> dict[str, pd.DataFrame]:
    ev: dict[str, pd.DataFrame] = {}
    for d in raw_dirs:
        for f in sorted(d.glob("*.pkl")):
            if f.stem in ev:
                continue
            try:
                ev[f.stem] = event_issuance(pickle.loads(f.read_bytes()).get("splits"))
            except Exception:  # noqa: BLE001
                ev[f.stem] = event_issuance(None)
    return ev


_EVENTS: dict[str, pd.DataFrame] | None = None


def _events(ctx) -> dict[str, pd.DataFrame]:
    global _EVENTS
    if _EVENTS is None:
        rd = Path(ctx["raw_dir"])
        _EVENTS = load_events([rd, rd.parent / "raw_delisted"])
    return _EVENTS


def cei_column(prep: pd.DataFrame, ctx) -> pd.Series:
    ev = _events(ctx)
    out = pd.Series(np.nan, index=prep.index)
    for tk, g in prep.groupby("ticker"):
        e = ev.get(str(tk), event_issuance(None))
        out.loc[g.index] = cei_for_dates(e, g["date"])
    return out


def neg_cei_sn_z(prep: pd.DataFrame, ctx) -> pd.Series:
    tmp = prep[["date", "sector"]].copy()
    tmp["x"] = (-cei_column(prep, ctx)).groupby(prep["date"]).transform(fb.winsorize_z)
    return fb.sector_neutralize(tmp, "x")


def score_r0_no_issuers(raw, prep, ctx):
    """81% of stock-months have CEI_5y = 0 (no rights issue), so a pure -CEI rank is
    mostly ties; the testable standalone form is R0 restricted to non-issuers."""
    return prep["value_sn_z"].where(cei_column(prep, ctx) <= 0.0)


def score_value_cei(raw, prep, ctx):
    return 0.8 * prep["value_sn_z"] + 0.2 * neg_cei_sn_z(prep, ctx).fillna(0.0)


def score_r0(raw, prep, ctx):
    return prep["value_sn_z"]


SPECS = [
    h.VariantSpec("r0_no_issuers", BATCH, "R0 top 20% among stocks with CEI_5y = 0 (no net rights issue in 5y)", score_r0_no_issuers,
                  frozen_params={"window_months": 60}),
    h.VariantSpec("value_cei_20", BATCH, "0.8*value_sn_z + 0.2*(-CEI_5y sn z, NaN->0), top 20%", score_value_cei,
                  frozen_params={"w_cei": 0.2, "window_months": 60}),
    h.VariantSpec("r0_top10", BATCH, "R0 value_sn_z, top 10% instead of 20%", score_r0, top_pct=0.10,
                  frozen_params={"top_pct": 0.10}),
]
for _s in SPECS:
    h.register_variant(_s)


if __name__ == "__main__":
    out = h.run_batch(BATCH, [s.name for s in SPECS], prereg_dir=DOC_DIR, results_dir=DOC_DIR / "results")
    print(out["md_path"])
    for n, v in out["payload"]["verdicts"].items():
        b = v["blocks_D_ann_pct"]
        print(f"{n:15s} D={v['full_D_ann_pct']:+.2f} t={v['full_t']:+.2f} "
              f"blk={[round(x, 2) for x in b.values()]} dd={v['dd_full_diff_pp']:+.1f}/{v['dd_2021p_diff_pp']:+.1f} "
              f"kap={v['kap_full_D_ann_pct']:+.2f}({v['kap_full_t']:+.2f}) holm={v['p_holm_tdist']:.3f} "
              f"turn={v['turnover_ratio']:.2f} {v['verdict']}")
