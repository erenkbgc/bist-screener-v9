#!/usr/bin/env python3
"""Tanisal (on-kayitli test DEGIL): value_sn ust %20 ile ayni ayin evreni karsilastirmasi.

Soru: canli kural likiditesi dusuk veya finansal olarak sorunlu hisselerde mi
yogunlasiyor? Panel: research_long_term.load() (finansal disi, likidite alt %30
atilmis). Her ay ust dilim ve evren icin oranlar; aylarin ortalamasi raporlanir.
Canli skoru DEGISTIRMEZ.

    python scripts/diagnose_pick_profile.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from research_long_term import SPLIT, load  # noqa: E402


def profile(g: pd.DataFrame) -> dict:
    chs_cut = g.attrs["chs_p90"]
    return {
        "median_tlvol60_mn": g["tlvol60"].median() / 1e6,
        "net_loss_pct": 100 * (g["ep"] < 0).mean(),
        "op_loss_pct": 100 * (g["ey"] < 0).mean(),
        "no_positive_equity_pct": 100 * g["bm"].isna().mean(),
        "chs_worst_decile_pct": 100 * (g["chs"] >= chs_cut).mean(),
        "altman_distress_pct": 100 * (g["altman_em"] < 1.1).mean(),
        "f7_le2_pct": 100 * (g["f7"] <= 2).mean(),
        "dd5y_le_-70_pct": 100 * (g["dd_5y_pct"] <= -70).mean(),
        "fwd_6m_xs_mean_pct": 100 * g["xs_6m"].mean(),
        "trap_rate_pct": 100 * (g["xs_6m"] < -0.30).mean(),
    }


def main() -> None:
    df = load()
    df = df[df["fwd_ret_1m"].notna()]
    rows = []
    for dt, g in df.groupby("date"):
        elig = g[g["value_sn_z"].notna()]
        if len(elig) < 30:
            continue
        top = elig.nlargest(max(1, round(0.2 * len(elig))), "value_sn_z")
        for name, part in (("top20", top), ("universe", g)):
            part = part.copy()
            part.attrs["chs_p90"] = g["chs"].quantile(0.9)
            rows.append({"date": dt, "group": name, **profile(part)})
    p = pd.DataFrame(rows)
    p["period"] = (p["date"] >= SPLIT).map({False: "discovery", True: "holdout"})
    table = p.groupby(["period", "group"]).mean(numeric_only=True).round(2)
    out = ROOT / "data" / "reports" / f"diagnose_pick_profile_{date.today().isoformat()}.json"
    out.write_text(json.dumps({"as_of": date.today().isoformat(), "months": int(p["date"].nunique()),
                               "table": {f"{a}/{b}": r.to_dict() for (a, b), r in table.iterrows()}},
                              indent=2), encoding="utf-8")
    pd.set_option("display.width", 200)
    print(table.T.to_string())
    print(out)


if __name__ == "__main__":
    main()
