#!/usr/bin/env python3
"""Ayni kural (value_sn ust %20), farkli panel dosyalari: aktif getiri, IC, eslestirilmis fark.

docs/research/first_published_panel.md karsilastirmasi. Her panel, data/research'in
symlink kopyasinda factors_monthly.parquet degistirilerek research_long_term.load ile okunur.

    python scripts/compare_panels.py base=data/research isy=data/research/isy fp=data/research/fp
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import research_long_term as rlt  # noqa: E402
from core import factor_backtest as fb  # noqa: E402
from core import long_term_research as ltr  # noqa: E402

WINDOWS = {"discovery": (None, "2021-01-01"), "holdout": ("2021-01-01", None), "ias29": ("2024-05-01", None)}


def research_view(factors_dir: Path) -> Path:
    """data/research'in symlink kopyasi; factors_monthly.parquet verilen klasorden."""
    tmp = Path(tempfile.mkdtemp(prefix="panel_"))
    for f in (ROOT / "data" / "research").iterdir():
        if f.name != "factors_monthly.parquet":
            (tmp / f.name).symlink_to(f)
    (tmp / "factors_monthly.parquet").symlink_to((factors_dir / "factors_monthly.parquet").resolve())
    return tmp


def window(df: pd.DataFrame, lo: str | None, hi: str | None) -> pd.Series:
    m = pd.Series(True, index=df.index)
    if lo:
        m &= df["date"] >= lo
    if hi:
        m &= df["date"] < hi
    return m


def main() -> None:
    panels = dict(a.split("=", 1) for a in sys.argv[1:])
    res, ports, tops = {}, {}, {}
    for name, d in panels.items():
        rlt.RESEARCH = research_view(ROOT / d)
        df = rlt.load()
        ic = fb.rank_ic(df, "value_sn_z", "fwd_ret_1m")
        df["top"] = df.groupby("date")["value_sn_z"].rank(ascending=False, pct=True) <= 0.2
        tops[name] = df.loc[df["top"], ["date", "ticker"]]
        res[name] = {}
        for w, (lo, hi) in WINDOWS.items():
            sub = df[window(df, lo, hi)]
            p = ltr.portfolio(sub, "value_sn_z")
            ports[(name, w)] = p
            s = ltr.summarize(p)
            icw = ic[(ic.index >= (lo or "1900")) & (ic.index < (hi or "2100"))]
            m, t, n = fb.newey_west_t(icw, 6)
            res[name][w] = {"active_ann_pct": s.get("active_ann_pct"), "t": s.get("t"), "months": s.get("months"),
                            "ic": round(float(m), 4), "ic_t": round(float(t), 2)}
    base = next(iter(panels))
    for name in panels:
        if name == base:
            continue
        for w in WINDOWS:
            res[name][w]["diff_vs_" + base] = ltr.diff_stats(ports[(base, w)], ports[(name, w)])
        a, b = tops[base].assign(k=1), tops[name].assign(k=1)
        j = a.merge(b, on=["date", "ticker"], how="outer", indicator=True)
        res[name]["top20_rows_base"] = len(a)
        res[name]["top20_changed_rows"] = int((j["_merge"] != "both").sum() // 2)
    out = ROOT / "data" / "reports" / f"compare_panels_{date.today().isoformat()}.json"
    out.write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()
