#!/usr/bin/env python3
"""On-kayitli KAP bildirim zamanlamasi ve geri alim sinyalleri
(docs/research/kap_disclosure_signals_preregistration.md).

S1 KAP gec bayragi, S2 sirketin kendi aliskanligindan gec, S3 cuma aksami/hafta sonu
yayini, S4 geri alim baslangici. Takvim-zamanli portfoy: olaydan sonraki ay
sonundan itibaren 3 ay tutulur; S1-S3 ayni pencerede bilanco aciklayip sinyali
olmayanlara, S4 EW evrene karsi.

    python scripts/research_kap_disclosure_signals.py
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
from core import pit_panel  # noqa: E402
from diagnose_crashed_picks import month_end  # noqa: E402

RESEARCH = ROOT / "data" / "research"
HOLD_MONTHS = 3
MIN_NAMES = 5
NW_LAGS = 3
OWN_DELAY_DAYS = 14
BUYBACK_GAP_DAYS = 180
BUYBACK_SUBJECT = "Payların Geri Alınmasına İlişkin Bildirim"
SIGNS = {"S1": -1, "S2": -1, "S3": -1, "S4": 1}
SPLITS = {"S1": "2021-01-01", "S2": "2021-01-01", "S3": "2021-01-01", "S4": "2022-01-01"}
S4_START = pd.Timestamp("2018-01-01")
HLZ_T, HOLDOUT_T, MIN_MONTHS = 3.0, 2.0, 24


def first_filings(archive: pd.DataFrame) -> pd.DataFrame:
    """Her (ticker, period) icin ilk finansal rapor: published_at, isLate, lag, quarter."""
    fr = archive[(archive["disclosureClass"] == "FR") & archive["subject"].isin(pit_panel.REPORT_SUBJECTS)
                 & archive["ruleType"].isin(pit_panel.RULE_QUARTER)].copy()
    pub = pd.to_datetime(fr["published_at"])
    qn = fr["ruleType"].map(pit_panel.RULE_QUARTER).astype(int)
    pe_same = pd.to_datetime(dict(year=pub.dt.year, month=3 * qn, day=1)) + pd.offsets.MonthEnd(0)
    year = np.where(pe_same < pub.dt.normalize(), pub.dt.year, pub.dt.year - 1)
    pe = pd.to_datetime(dict(year=year, month=3 * qn, day=1)) + pd.offsets.MonthEnd(0)
    fr = fr.assign(ticker=fr["stock_code"].str.strip(), published_at=pub, quarter=qn, period_end=pe,
                   lag=(pub.dt.normalize() - pe).dt.days)
    fr = fr[fr["lag"].between(1, pit_panel.MAX_MATCH_DAYS)]
    first = fr.sort_values("published_at").groupby(["ticker", "period_end"], as_index=False).first()
    return first[["ticker", "period_end", "quarter", "published_at", "isLate", "lag"]]


def report_signals(first: pd.DataFrame) -> pd.DataFrame:
    f = first.sort_values(["ticker", "quarter", "period_end"]).copy()
    prior = (f.groupby(["ticker", "quarter"])["lag"]
             .transform(lambda s: s.shift(1).rolling(4, min_periods=2).median()))
    f["S1"] = f["isLate"].astype(bool)
    f["S2"] = (f["lag"] - prior) >= OWN_DELAY_DAYS
    wd, hr = f["published_at"].dt.weekday, f["published_at"].dt.hour
    f["S3"] = ((wd == 4) & (hr >= pit_panel.SESSION_CLOSE_HOUR)) | (wd >= 5)
    f["month"] = month_end(f["published_at"].dt.normalize())
    return f


def buyback_starts(archive: pd.DataFrame) -> pd.DataFrame:
    b = archive[archive["subject"] == BUYBACK_SUBJECT].copy()
    b["ticker"] = b["stock_code"].str.strip()
    b["published_at"] = pd.to_datetime(b["published_at"])
    b = b.sort_values(["ticker", "published_at"])
    gap = b.groupby("ticker")["published_at"].diff().dt.days
    b = b[gap.isna() | (gap > BUYBACK_GAP_DAYS)]
    b["month"] = month_end(b["published_at"].dt.normalize())
    return b[["ticker", "published_at", "month"]]


def calendar_portfolio(events: pd.DataFrame, control_events: pd.DataFrame | None,
                       panel: pd.DataFrame) -> pd.DataFrame:
    """events/control_events: (ticker, month). Ay t portfoyu: t, t-1, t-2 olaylari (evren icinde)."""
    rows = []
    months = sorted(panel["date"].unique())
    ev_by = events.groupby("month")["ticker"].apply(set).to_dict()
    ct_by = control_events.groupby("month")["ticker"].apply(set).to_dict() if control_events is not None else None
    for k, t in enumerate(months):
        win = months[max(0, k - HOLD_MONTHS + 1):k + 1]
        g = panel[panel["date"] == t].set_index("ticker")["fwd_ret_1m"].dropna()
        sig = set().union(*(ev_by.get(m, set()) for m in win)) & set(g.index)
        if len(sig) < MIN_NAMES:
            continue
        if ct_by is not None:
            ctl = set().union(*(ct_by.get(m, set()) for m in win)) & set(g.index)
            ctl -= sig
            if len(ctl) < MIN_NAMES:
                continue
            base = g[list(ctl)].mean()
        else:
            base = g.mean()
        rows.append({"date": t, "n": len(sig), "d": g[list(sig)].mean() - base})
    return pd.DataFrame(rows)


def stats(p: pd.DataFrame) -> dict:
    if len(p) < 3:
        return {"months": len(p)}
    m, t, n = fb.newey_west_t(p["d"], NW_LAGS)
    return {"months": n, "d_ann_pct": round(1200 * m, 2), "t": round(t, 2), "avg_names": round(p["n"].mean(), 1)}


def verdict(sign: int, disc: dict, hold: dict) -> str:
    def ok(s, thr):
        return s.get("months", 0) >= MIN_MONTHS and np.sign(s.get("d_ann_pct", 0)) == sign and abs(s.get("t", 0)) > thr
    if ok(disc, HLZ_T) and ok(hold, HOLDOUT_T):
        return "PASS"
    if ok(disc, HLZ_T):
        return "DISCOVERY_ONLY"
    return "FAIL"


def main() -> None:
    archive = pd.read_parquet(RESEARCH / "kap_archive.parquet")
    panel = pd.read_parquet(RESEARCH / "factors_monthly.parquet")
    panel["date"] = month_end(panel["date"])
    panel = fb.prepare(panel, [], liq_drop_pct=0.3)

    sig = report_signals(first_filings(archive))
    reporters = sig[["ticker", "month"]]
    bb = buyback_starts(archive)
    result = {"as_of": date.today().isoformat(), "event_counts": {}, "tests": {}}
    for s in ("S1", "S2", "S3", "S4"):
        if s == "S4":
            ev = bb[["ticker", "month"]]
            p = calendar_portfolio(ev, None, panel[panel["date"] >= S4_START])
        else:
            ev = sig.loc[sig[s], ["ticker", "month"]]
            ctl = sig.loc[~sig[s], ["ticker", "month"]]
            p = calendar_portfolio(ev, ctl, panel)
        split = pd.Timestamp(SPLITS[s])
        disc, hold = stats(p[p["date"] < split]), stats(p[p["date"] >= split])
        result["event_counts"][s] = int(len(ev))
        result["tests"][s] = {"expected_sign": SIGNS[s], "discovery": disc, "holdout": hold,
                              "verdict": verdict(SIGNS[s], disc, hold)}
    result["event_counts"]["reports_total"] = int(len(reporters))
    out = ROOT / "data" / "reports" / f"research_kap_disclosure_signals_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
