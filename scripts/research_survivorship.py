#!/usr/bin/env python3
"""Cikmis hisselerle hayatta kalma duzeltmesi
(docs/research/survivorship_delisted_preregistration.md).

    python scripts/fetch_delisted.py        # once (raw_delisted/, delisted_meta.json)
    python scripts/research_survivorship.py

Taban: bugunku panel. S1..S5: panel + cikmis hisse satirlari, cikis getirisi
spesifikasyona gore. Her biri ayni prepare/add_composites/portfolio kodundan gecer.
Karar kurali on-kayitta; burada yalnizca uygulanir.
"""
from __future__ import annotations

import json
import pickle
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import delisted  # noqa: E402
from core import factor_backtest as fb  # noqa: E402
from core import long_term_research as ltr  # noqa: E402
from core import pit_panel  # noqa: E402
from backtest_factor_model import FACTORS, add_composites  # noqa: E402
from diagnose_crashed_picks import month_end  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SPLIT = pd.Timestamp("2021-01-01")
T_MIN = 2.0


# Taban panel dosyalari (ikisi de net borc duzeltmesinden once kuruldu: eksik borc/nakit = 0).
BASELINES = {
    "kapdates": ("factors_monthly_kapdates.parquet", True),  # gercek KAP yayin tarihleri
    "lag75": ("factors_monthly.parquet", False),              # 75/100 gun gecikmesi (long_term)
}


def delisted_panel(kap: pd.DataFrame, report_dates: bool) -> tuple[pd.DataFrame, dict]:
    """Cikmis hisseler icin faktor satirlari (cikis getirisi eklenmemis) ve kod bilgisi.

    Taban dosyayla ayni kurallar: report_dates=True ise KAP yayin tarihleri;
    eksik borc/nakit 0 sayilir (taban dosyalar pit_panel'deki NaN kuralindan once kuruldu).
    """
    longs, pxs, evs, info = [], [], [], {}
    for f in sorted((RESEARCH / "raw_delisted").glob("*.pkl")):
        raw = pickle.loads(f.read_bytes())
        if raw.get("bs") is None or raw.get("inc") is None:
            continue
        code = f.stem
        daily = delisted.daily_frame(raw["px"])
        r, a = delisted.price_frames(daily)
        px = pit_panel.monthly_prices(code, r, a)
        last = delisted.last_trade(daily)
        info[code] = {
            "last_trade": last,
            "adj_last": float(daily["HGDG_KAPANIS"].iloc[-1]),
            "adj_at": px.set_index("date")["adj"],
            "exit_class": delisted.classify_exit(kap, code, last),
            "sector": delisted.sector_of(code),
        }
        longs.append(pit_panel.statements_long(code, raw["bs"], raw["inc"]))
        pxs.append(px)
        evs.append(delisted.share_events(code, daily))
    q = pit_panel.quarterly_table(pd.concat([x for x in longs if not x.empty], ignore_index=True))
    if report_dates:
        q = pit_panel.apply_report_dates(q, pit_panel.kap_report_dates(pd.read_parquet(RESEARCH / "kap_archive.parquet")))
    q[["fin_debt", "cash"]] = q[["fin_debt", "cash"]].fillna(0.0)
    px = pd.concat(pxs, ignore_index=True)
    ev = pd.concat(evs, ignore_index=True)
    factors = pit_panel.build_monthly_factors(q, px, ev, {c: i["sector"] for c, i in info.items()})
    return factors, info


def prepared(raw: pd.DataFrame, market_m: pd.DataFrame) -> pd.DataFrame:
    raw = raw.copy()
    raw["date"] = month_end(raw["date"])
    raw = pit_panel.add_usd_returns(raw, market_m)
    df = add_composites(fb.prepare(raw, FACTORS, liq_drop_pct=0.3))
    df["xs_6m"] = df["fwd_ret_6m_xs"]
    return df


def top_picks(df: pd.DataFrame) -> pd.DataFrame:
    """ltr.portfolio ile ayni secim (dislama yok): ay basina value_sn ust %20."""
    out = []
    for _, g in df.groupby("date"):
        g = g[g["fwd_ret_1m"].notna()]
        if len(g) < 30:
            continue
        elig = g[g["value_sn_z"].notna()]
        if len(elig) < 5:
            continue
        out.append(elig.nlargest(max(1, int(round(len(elig) * 0.2))), "value_sn_z"))
    return pd.concat(out, ignore_index=True)


def evaluate(df: pd.DataFrame, info: dict) -> dict:
    res = {}
    for w, m in (("discovery", df["date"] < SPLIT), ("holdout", df["date"] >= SPLIT)):
        sub = df[m]
        p = ltr.portfolio(sub, "value_sn_z")
        ic = fb.rank_ic(sub, "value_sn_z", "fwd_ret_1m")
        ic_m, ic_t, ic_n = fb.newey_west_t(ic, 6)
        res[w] = {"tl": ltr.summarize(p), "usd": ltr.summarize(p, "active_fwd_ret_1m_usd"),
                  "ic": {"mean": round(float(ic_m), 4), "t": round(float(ic_t), 2), "months": ic_n}}
    codes = set(info)
    picks = top_picks(df)
    is_del = picks["ticker"].isin(codes)
    exits = picks[is_del & picks.apply(
        lambda r: r["date"] + pd.offsets.MonthEnd(1) > info[r["ticker"]]["last_trade"] if r["ticker"] in codes else False,
        axis=1)] if is_del.any() else picks.iloc[:0]
    res["coverage"] = {
        "delisted_stocks_in_panel": int(df.loc[df["ticker"].isin(codes), "ticker"].nunique()),
        "delisted_stock_months": int(df["ticker"].isin(codes).sum()),
        "pick_share_delisted_pct": round(100 * float(is_del.mean()), 2),
        "picks_exiting_next_month": {c: int((exits["ticker"].map(lambda t: info[t]["exit_class"]) == c).sum())
                                     for c in ("corporate", "other")},
        "exiting_pick_tickers": sorted(exits["ticker"].unique().tolist()),
    }
    return res


def survives(r: dict) -> bool:
    d, h = r["discovery"]["tl"], r["holdout"]["tl"]
    return (d.get("active_ann_pct", 0) > 0 and d.get("t", 0) > T_MIN
            and h.get("active_ann_pct", 0) > 0 and h.get("t", 0) > T_MIN
            and r["holdout"]["usd"].get("active_ann_pct", 0) > 0)


def main() -> None:
    kap = pd.read_parquet(RESEARCH / "kap_archive.parquet", columns=["stock_code", "published_at", "subject", "summary"])
    kap = kap.dropna(subset=["stock_code"])
    codes = kap["stock_code"].str.split(",").explode().str.strip()
    kap = kap.loc[codes.index].assign(stock_code=codes.values)

    market_m = pit_panel.monthly_market(pd.read_parquet(RESEARCH / "fx.parquet"))
    result = {"as_of": date.today().isoformat(), "split": str(SPLIT.date()), "primary": "kapdates", "variants": {}}
    for variant, (fname, report_dates) in BASELINES.items():
        base_raw = pd.read_parquet(RESEARCH / fname)
        del_raw, info = delisted_panel(kap, report_dates)
        overlap = set(base_raw["ticker"]) & set(info)
        if overlap:
            raise SystemExit(f"Cikmis kod bugunku panelde de var: {sorted(overlap)}")
        v = {"baseline_file": fname,
             "delisted": {c: {"last_trade": str(i["last_trade"].date()), "exit_class": i["exit_class"],
                              "sector": i["sector"]} for c, i in sorted(info.items())},
             "baseline": evaluate(prepared(base_raw, market_m), {}), "specs": {}}
        for spec in delisted.SPECS:
            d_by = {c: delisted.exit_return(spec, i["exit_class"], c) for c, i in info.items()}
            adj_last = {c: (i["last_trade"], i["adj_last"]) for c, i in info.items()}
            adj_at = {c: i["adj_at"] for c, i in info.items()}
            dr = delisted.apply_exits(del_raw, adj_last, adj_at, d_by)
            r = evaluate(prepared(pd.concat([base_raw, dr], ignore_index=True), market_m), info)
            r["survives"] = survives(r)
            v["specs"][spec] = r
        s1 = v["specs"]["S1"]["survives"]
        v["verdict"] = ("SURVIVES_ROBUST_TO_WORST_CASE" if s1 and v["specs"]["S5"]["survives"]
                        else "SURVIVES" if s1 else "SURVIVORSHIP_FRAGILE")
        v["baseline"]["meets_rules_1_3"] = survives(v["baseline"])
        result["variants"][variant] = v

        cls = pd.Series({c: i["exit_class"] for c, i in info.items()}).value_counts().to_dict()
        print(f"\n== {variant} ({fname}) | cikmis hisse (tablolu): {len(info)} {cls}")
        print("Spec   kesif aktif TL (t)   holdout aktif TL (t)   holdout USD   IC t kesif/holdout   B'de cikmis %   cikan secim")
        for name, r in [("base", v["baseline"])] + list(v["specs"].items()):
            d, h = r["discovery"], r["holdout"]
            cov = r["coverage"]
            print(f"{name:5s}  {d['tl']['active_ann_pct']:6.2f} ({d['tl']['t']:5.2f})      {h['tl']['active_ann_pct']:6.2f} ({h['tl']['t']:5.2f})"
                  f"      {h['usd']['active_ann_pct']:6.2f}      {d['ic']['t']:5.2f} / {h['ic']['t']:5.2f}"
                  f"        {cov['pick_share_delisted_pct']:5.2f}      {cov['picks_exiting_next_month']}")
        print(f"Karar: {v['verdict']}  (taban kural 1-3: {v['baseline']['meets_rules_1_3']})")
    result["verdict"] = result["variants"]["kapdates"]["verdict"]

    out = ROOT / "data" / "reports" / f"research_survivorship_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
