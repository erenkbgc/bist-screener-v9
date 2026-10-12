#!/usr/bin/env python3
"""On-kayitli futbol duygusu testi (docs/research/football_sentiment_preregistration.md).

F1 kulup hisseleri (lig galibiyeti vs yenilgisi, ertesi seans piyasa-duzeltilmis getiri),
F2 milli takim resmi mac yenilgisi (ertesi seans XU100 USD anormal getiri, EEM Dimson).

Veri: data/research/football/T1_*.csv (football-data.co.uk), intl_results.csv
(martj42/international_results). T1 dosyalari yoksa F1 atlanir.

    python scripts/research_football_sentiment.py
"""
from __future__ import annotations

import json
import pickle
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import event_study as es  # noqa: E402

RESEARCH = ROOT / "data" / "research"
FOOTBALL = RESEARCH / "football"
CLUBS = {"Galatasaray": "GSRAY", "Fenerbahce": "FENER", "Besiktas": "BJKAS", "Trabzonspor": "TSPOR"}
COMPETITIVE = {"FIFA World Cup qualification", "UEFA Euro qualification", "UEFA Nations League",
               "UEFA Euro", "FIFA World Cup"}
F1_SPLIT, F2_SPLIT = pd.Timestamp("2016-07-01"), pd.Timestamp("2016-01-01")
HLZ_T, HOLDOUT_T = 3.0, 2.0


def market() -> pd.DataFrame:
    """BIST takvimi: 2011+ borsapy (fx.parquet), oncesi yfinance XU100.IS; EEM gunluk."""
    fx = pd.read_parquet(RESEARCH / "fx.parquet")
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()[["xu100", "usdtry"]]
    yf_path = RESEARCH / "xu100_usdtry_yf_daily.parquet"
    if yf_path.exists():
        y = pd.read_parquet(yf_path)
        early = pd.DataFrame({"xu100": y["XU100.IS"], "usdtry": y["USDTRY=X"].ffill()}).dropna(subset=["xu100"])
        early = early[early.index < fx.index.min()]
        fx = pd.concat([early, fx])
    eem = pd.read_parquet(RESEARCH / "eem_daily.parquet")["eem"]
    fx["eem"] = eem.reindex(fx.index.union(eem.index)).ffill().reindex(fx.index)
    return fx.dropna()


def event_day(days: pd.DatetimeIndex, match_date: pd.Timestamp) -> int:
    return int(days.searchsorted(match_date, side="right"))


def national_matches() -> pd.DataFrame:
    d = pd.read_csv(FOOTBALL / "intl_results.csv", parse_dates=["date"])
    d = d[((d["home_team"] == "Turkey") | (d["away_team"] == "Turkey")) & (d["date"] >= "2005-01-01")
          & d["tournament"].isin(COMPETITIVE)].copy()
    tr_home = d["home_team"] == "Turkey"
    gf = np.where(tr_home, d["home_score"], d["away_score"])
    ga = np.where(tr_home, d["away_score"], d["home_score"])
    d["result"] = np.select([gf > ga, gf < ga], ["W", "L"], "D")
    return d[["date", "home_team", "away_team", "tournament", "result"]]


def club_matches() -> pd.DataFrame | None:
    files = sorted(FOOTBALL.glob("T1_*.csv"))
    if not files:
        return None
    rows = []
    for f in files:
        m = pd.read_csv(f, encoding="latin-1", usecols=lambda c: c in {"Date", "HomeTeam", "AwayTeam", "FTR"})
        m["Date"] = pd.to_datetime(m["Date"], dayfirst=True, errors="coerce")
        for team, tk in CLUBS.items():
            for side, win in (("HomeTeam", "H"), ("AwayTeam", "A")):
                g = m[m[side] == team]
                res = np.where(g["FTR"] == win, "W", np.where(g["FTR"] == "D", "D", "L"))
                rows.append(pd.DataFrame({"date": g["Date"], "ticker": tk, "result": res}))
    out = pd.concat(rows).dropna(subset=["date"])
    return out[out["date"] >= "2005-07-01"]


def club_close(ticker: str, days: pd.DatetimeIndex) -> pd.Series | None:
    f = RESEARCH / "raw" / f"{ticker}.pkl"
    if not f.exists():
        return None
    px = pickle.loads(f.read_bytes()).get("px_adj")
    idx = pd.to_datetime(px.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    s = pd.Series(px["Close"].astype(float).to_numpy(), index=idx.normalize())
    return s[~s.index.duplicated(keep="last")].reindex(days)


def run_f1(m: pd.DataFrame) -> dict:
    matches = club_matches()
    if matches is None:
        return {"status": "NOT_RUN_NO_DATA"}
    days = m.index
    r_xu = np.log(m["xu100"]).diff()
    rows = []
    for tk, g in matches.groupby("ticker"):
        close = club_close(tk, days)
        if close is None:
            continue
        r = np.log(close).diff()
        g = g.assign(pos=[event_day(days, d) for d in g["date"]])
        g = g[~g.duplicated("pos", keep=False) & (g["pos"] < len(days))]
        for _, x in g.iterrows():
            ar = r.iloc[x["pos"]] - r_xu.iloc[x["pos"]]
            if np.isfinite(ar):
                rows.append({"ticker": tk, "date": x["date"], "result": x["result"], "ar": ar})
    ev = pd.DataFrame(rows)

    def diff(sub: pd.DataFrame) -> dict:
        w, lo = sub.loc[sub["result"] == "W", "ar"], sub.loc[sub["result"] == "L", "ar"]
        t, p = stats.ttest_ind(w, lo, equal_var=False)
        return {"n_win": len(w), "n_loss": len(lo), "n_draw": int((sub["result"] == "D").sum()),
                "mean_win_bps": round(1e4 * w.mean(), 1), "mean_draw_bps": round(1e4 * sub.loc[sub["result"] == "D", "ar"].mean(), 1),
                "mean_loss_bps": round(1e4 * lo.mean(), 1), "d_bps": round(1e4 * (w.mean() - lo.mean()), 1),
                "t": round(float(t), 2), "p": round(float(p), 4)}

    disc, hold = diff(ev[ev["date"] < F1_SPLIT]), diff(ev[ev["date"] >= F1_SPLIT])
    ok = disc["d_bps"] > 0 and disc["t"] > HLZ_T and hold["d_bps"] > 0 and hold["t"] > HOLDOUT_T
    return {"discovery": disc, "holdout": hold, "verdict": "PASS" if ok else "FAIL",
            "by_club": {tk: diff(g) for tk, g in ev.groupby("ticker")}}


def run_f2(m: pd.DataFrame) -> dict:
    days = m.index
    usd = (m["xu100"] / m["usdtry"]).to_numpy()
    r_usd = np.r_[np.nan, np.diff(np.log(usd))]
    r_eem = np.r_[np.nan, np.diff(np.log(m["eem"].to_numpy()))]
    rows = []
    for _, x in national_matches().iterrows():
        i0 = event_day(days, x["date"])
        if i0 + es.EST_START < 1 or i0 >= len(days):
            continue
        params = es.market_model(r_usd, r_eem, i0)
        rows.append({"date": x["date"], "result": x["result"], "tournament": x["tournament"],
                     "ar": es.car(r_usd, r_eem, params, i0, 0, 0)})
    ev = pd.DataFrame(rows)

    def one(sub: pd.DataFrame, res: str) -> dict:
        return es.cross_event_test(list(sub.loc[sub["result"] == res, "ar"]))

    out = {}
    for w, sub in (("discovery", ev[ev["date"] < F2_SPLIT]), ("holdout", ev[ev["date"] >= F2_SPLIT])):
        out[w] = {"loss": one(sub, "L"), "win": one(sub, "W"), "draw": one(sub, "D")}
    d, h = out["discovery"]["loss"], out["holdout"]["loss"]
    ok = d.get("mean_pct", 0) < 0 and d.get("t", 0) < -HLZ_T and h.get("mean_pct", 0) < 0 and h.get("t", 0) < -HOLDOUT_T
    out["verdict"] = "PASS" if ok else "FAIL"
    return out


def main() -> None:
    m = market()
    result = {"as_of": date.today().isoformat(), "F1_club_win_minus_loss": run_f1(m), "F2_national_loss": run_f2(m)}
    out = ROOT / "data" / "reports" / f"research_football_sentiment_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=float))
    print(json.dumps(result, indent=1, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
