#!/usr/bin/env python3
"""On-kayitli secim / sok olay calismasi (docs/research/event_study_preregistration.md).

    python scripts/build_fx_panel.py
    python scripts/research_event_study.py   # EEM gunluk yoksa yfinance'tan indirir
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

from core import event_study as es  # noqa: E402

RESEARCH = ROOT / "data" / "research"
ALPHA = 0.05 / 3

EVENTS = [
    ("E1", "2014-03-31", "Yerel secim", "election"),
    ("E2", "2014-08-11", "Cumhurbaskanligi secimi", "election"),
    ("E3", "2015-06-08", "Genel secim", "election"),
    ("E4", "2015-11-02", "Tekrar genel secim", "election"),
    ("E5", "2017-04-17", "Anayasa referandumu", "election"),
    ("E6", "2018-06-25", "Genel + cumhurbaskanligi secimi", "election"),
    ("E7", "2019-04-01", "Yerel secim", "election"),
    ("E8", "2019-06-24", "Istanbul yenileme secimi", "election"),
    ("E9", "2023-05-15", "Genel secim 1. tur", "election"),
    ("E10", "2023-05-29", "Cumhurbaskanligi 2. tur", "election"),
    ("E11", "2024-04-01", "Yerel secim", "election"),
    ("D1", "2013-06-03", "Gezi", "domestic"),
    ("D2", "2013-12-17", "17 Aralik operasyonu", "domestic"),
    ("D3", "2016-07-18", "Darbe girisimi", "domestic"),
    ("D4", "2018-08-10", "Kur krizi / ABD tarifeleri", "domestic"),
    ("D5", "2021-03-22", "Agbal gorevden alindi", "domestic"),
    ("D6", "2021-11-23", "Kur cokusu (faiz indirimi konusmasi)", "domestic"),
    ("D7", "2023-02-06", "Kahramanmaras depremleri", "domestic"),
    ("D8", "2025-03-19", "Imamoglu gozaltisi", "domestic"),
    ("G1", "2015-11-24", "Rus ucagi dusuruldu", "geopolitical"),
    ("G2", "2019-10-09", "Baris Pinari harekati", "geopolitical"),
    ("G3", "2020-01-03", "Suleymani olduruldu", "geopolitical"),
    ("G4", "2022-02-24", "Rusya Ukrayna'yi isgal etti", "geopolitical"),
    ("G5", "2023-10-09", "Hamas'in Israil saldirisi", "geopolitical"),
    ("G6", "2024-04-15", "Iran'in Israil saldirisi", "geopolitical"),
    ("G7", "2025-06-13", "Israil Iran'i vurdu", "geopolitical"),
    ("G8", "2025-06-23", "ABD Iran nukleer tesislerini vurdu", "geopolitical"),
]
DESC_WINDOWS = [(-20, -1), (-5, -1), (0, 0), (0, 5), (0, 20), (0, 60)]


def load_market() -> pd.DataFrame:
    fx = pd.read_parquet(RESEARCH / "fx.parquet")
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()
    eem_path = RESEARCH / "eem_daily.parquet"
    if not eem_path.exists():
        import yfinance as yf
        d = yf.download("EEM", start="2010-01-01", auto_adjust=True, progress=False)
        s = d["Close"].squeeze().dropna()
        s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
        s.rename("eem").to_frame().to_parquet(eem_path)
    eem = pd.read_parquet(eem_path)["eem"]
    m = fx.copy()
    m["eem"] = eem.reindex(m.index.union(eem.index)).ffill().reindex(m.index)
    macro = pd.read_parquet(RESEARCH / "macro_monthly.parquet")
    macro.index = pd.to_datetime(macro.index).to_period("M")
    pol = macro["policy"].ffill().reindex(m.index.to_period("M")).to_numpy()
    m["rf"] = (1 + pol / 100) ** (1 / 252) - 1
    m["usd_level"] = m["xu100"] / m["usdtry"]
    return m.dropna(subset=["xu100", "usdtry", "eem"])


def value_spread(events: list[tuple], days: pd.DatetimeIndex) -> dict[str, float]:
    """[0, +20] EW ust beslik value_sn - EW likit evren (TL), son ay sonu listesiyle."""
    from research_long_term import load
    from research_entry_timing import load_daily

    df = load()
    df = df[df["value_sn_z"].notna()].copy()
    df["rank_pct"] = df.groupby("date")["value_sn_z"].rank(ascending=False, pct=True)
    cache: dict[str, pd.Series | None] = {}
    out = {}
    for eid, listed, _, _ in events:
        i0 = es.event_pos(days, listed)
        if i0 + 20 >= len(days):
            continue
        prior = [t for t in df["date"].unique() if t < days[i0]]
        if not prior:
            continue
        g = df[df["date"] == max(prior)]
        rets = {}
        for tk in g["ticker"]:
            if tk not in cache:
                f = load_daily(tk)
                cache[tk] = f["Close"].reindex(days).ffill() if f is not None else None
            s = cache[tk]
            if s is not None and np.isfinite(s.iloc[i0 - 1]) and np.isfinite(s.iloc[i0 + 20]):
                rets[tk] = s.iloc[i0 + 20] / s.iloc[i0 - 1] - 1
        top = [rets[t] for t in g.loc[g["rank_pct"] <= 0.2, "ticker"] if t in rets]
        if top and rets:
            out[eid] = float(np.mean(top) - np.mean(list(rets.values())))
    return out


def main() -> None:
    m = load_market()
    days = m.index
    tl, usd = m["xu100"].to_numpy(), m["usd_level"].to_numpy()
    r_usd = np.r_[np.nan, np.diff(np.log(usd))]
    r_eem = np.r_[np.nan, np.diff(np.log(m["eem"].to_numpy()))]
    dep = np.cumprod(1 + m["rf"].to_numpy())

    vs = value_spread(EVENTS, days)
    rows = []
    for eid, listed, name, group in EVENTS:
        i0 = es.event_pos(days, listed)
        params = es.market_model(r_usd, r_eem, i0)
        row = {"id": eid, "listed": listed, "t0": str(days[i0].date()), "event": name, "group": group,
               "beta_eem": round(params[1] + params[2], 2)}
        for a, b in DESC_WINDOWS:
            row[f"tl_{a}_{b}"] = es.window_return(tl, i0, a, b)
            row[f"usd_{a}_{b}"] = es.window_return(usd, i0, a, b)
            row[f"car_{a}_{b}"] = es.car(r_usd, r_eem, params, i0, a, b)
        row["h1_x"] = es.window_return(tl, i0, -5, 5) - es.window_return(dep, i0, -5, 5)
        row["h2a_y"] = es.car(r_usd, r_eem, params, i0, 2, 20)
        row["h2b_y"] = es.car(r_usd, r_eem, params, i0, 2, 60)
        row["vol_ratio"] = es.vol_ratio(r_usd, i0)
        row["recovery_days_usd"] = es.recovery_days(usd, i0)
        row["value_minus_universe_0_20"] = vs.get(eid, np.nan)
        rows.append(row)
    ev = pd.DataFrame(rows)

    elec, shock = ev[ev["group"] == "election"], ev[ev["group"] != "election"]
    h1 = es.cross_event_test(list(elec["h1_x"]))
    h2a = es.cross_event_test(list(shock["h2a_y"]))
    h2b = es.cross_event_test(list(shock["h2b_y"]))
    tests = {
        "H1_cash_around_elections": {**h1, "verdict": es.verdict(h1, 8, ALPHA, "STAY_INVESTED", "CASH_AROUND_ELECTIONS")},
        "H2a_buy_after_shock_2_20": {**h2a, "verdict": es.verdict(h2a, 11, ALPHA, "BUY_AFTER_SHOCK", "CONTINUATION")},
        "H2b_buy_after_shock_2_60": {**h2b, "verdict": es.verdict(h2b, 11, ALPHA, "BUY_AFTER_SHOCK", "CONTINUATION")},
    }
    desc = {}
    for grp, g in ev.groupby("group"):
        desc[grp] = {c: es.cross_event_test(list(g[c])) for c in
                     ["usd_-20_-1", "car_-5_-1", "car_0_0", "car_0_5", "car_0_20", "car_0_60",
                      "usd_0_0", "usd_0_20", "tl_0_20", "value_minus_universe_0_20"]}
        desc[grp]["median_recovery_days_usd"] = float(g["recovery_days_usd"].median())
        desc[grp]["median_vol_ratio"] = round(float(g["vol_ratio"].median()), 2)

    def r(v):
        return None if v is None or (isinstance(v, float) and not np.isfinite(v)) else (round(v, 4) if isinstance(v, float) else v)

    result = {"as_of": date.today().isoformat(), "alpha": round(ALPHA, 4), "tests": tests, "descriptive": desc,
              "events": [{k: r(v) for k, v in row.items()} for row in ev.to_dict("records")]}
    out = ROOT / "data" / "reports" / f"research_event_study_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    pct = lambda v: f"{100 * v:7.1f}" if np.isfinite(v) else "    nan"  # noqa: E731
    print("ID   t0          olay                                   USD[0]  USD[0,20] CAR[0,20] CAR[2,60]  H1 X   toparlanma  deger-evren")
    for _, x in ev.iterrows():
        print(f"{x['id']:4s} {x['t0']}  {x['event'][:36]:36s} {pct(x['usd_0_0'])} {pct(x['usd_0_20'])} {pct(x['car_0_20'])} "
              f"{pct(x['h2b_y'])} {pct(x['h1_x']) if x['group'] == 'election' else '      -'} {x['recovery_days_usd']:6d} "
              f"{pct(x['value_minus_universe_0_20'])}")
    print("\nTestler:", json.dumps(tests, indent=1))
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
