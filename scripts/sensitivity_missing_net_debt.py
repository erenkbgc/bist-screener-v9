#!/usr/bin/env python3
"""Eksik net borcu 0 saymamanin value_sn sonucuna etkisi (duyarlilik, hipotez degil).

Degisiklik: Finansal Borclar veya Nakit kalemi eksik olan ceyrekte EBIT/EV NaN
(eskiden eksik kalem 0 sayiliyor, EV piyasa degerine yaklasiyordu). Panel yeniden
kurulmaz: mevcut factors_monthly.parquet satirlarinda, o ay kullanilan ceyregin
(available_at <= ay sonu, en son) borc/nakit kalemi eksikse ey NaN yapilir.

Kural (kosudan once yazildi): degisiklik kabul edilir, eger value_sn ust %20
holdout aktif getirisi isaretini korur ve NW t > 2 kalir (Faz 2 holdout kurali).

    python scripts/sensitivity_missing_net_debt.py
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

from core import factor_backtest as fb  # noqa: E402
from core import long_term_research as ltr  # noqa: E402
from core import pit_panel  # noqa: E402
from backtest_factor_model import FACTORS, add_composites  # noqa: E402
from diagnose_crashed_picks import drawdown_from_peak, month_end  # noqa: E402
from research_long_term import RESEARCH, SPLIT, extended_quarterly  # noqa: E402

HOLDOUT_T = 2.0


def missing_debt_rows(raw: pd.DataFrame, q: pd.DataFrame) -> pd.Series:
    """raw satirinin kullandigi ceyrekte fin_debt veya cash eksik mi."""
    qq = q[["ticker", "available_at", "fin_debt", "cash"]].dropna(subset=["available_at"])
    qq = qq.assign(available_at=pd.to_datetime(qq["available_at"]).astype("datetime64[ns]")).sort_values("available_at")
    left = raw[["ticker", "date"]].reset_index()
    left = left.assign(date=pd.to_datetime(left["date"]).astype("datetime64[ns]")).sort_values("date")
    m = pd.merge_asof(left, qq, left_on="date", right_on="available_at", by="ticker",
                      direction="backward", allow_exact_matches=True)
    miss = m["fin_debt"].isna() | m["cash"].isna()
    return miss.set_axis(m["index"]).reindex(raw.index).fillna(False).astype(bool)


def run(raw: pd.DataFrame, market_m, prices, stmt, mcap_total) -> dict:
    df = add_composites(fb.prepare(raw, FACTORS, liq_drop_pct=0.3))
    monthly = ltr.monthly_exret(prices, market_m).merge(drawdown_from_peak(prices), on=["date", "ticker"], how="left")
    df = ltr.add_signals(df, stmt, monthly, mcap_total)
    df["xs_6m"] = df["fwd_ret_6m_xs"]
    out = {}
    for w, mask in (("discovery", df["date"] < SPLIT), ("holdout", df["date"] >= SPLIT)):
        p = ltr.portfolio(df[mask], "value_sn_z")
        out[w] = {"tl": ltr.summarize(p), "usd": ltr.summarize(p, "active_fwd_ret_1m_usd")}
    return out


def main() -> None:
    raw = pd.read_parquet(RESEARCH / "factors_monthly.parquet")
    q = pd.read_parquet(RESEARCH / "quarterly.parquet")
    miss = missing_debt_rows(raw, q)
    affected = miss & raw["ey"].notna()

    raw["date"] = month_end(raw["date"])
    market_m = pit_panel.monthly_market(pd.read_parquet(RESEARCH / "fx.parquet"))
    raw = pit_panel.add_usd_returns(raw, market_m)
    mcap_total = raw.groupby("date")["mcap"].sum()
    prices = pd.read_parquet(RESEARCH / "monthly_prices.parquet")
    prices["date"] = month_end(prices["date"])
    stmt = ltr.statement_features(extended_quarterly())

    base = run(raw, market_m, prices, stmt, mcap_total)
    fixed_raw = raw.copy()
    fixed_raw.loc[affected, "ey"] = float("nan")
    fixed = run(fixed_raw, market_m, prices, stmt, mcap_total)

    h = fixed["holdout"]["tl"]
    b = base["holdout"]["tl"]
    accepted = (h.get("t", 0) > HOLDOUT_T) and ((h.get("active_ann_pct", 0) > 0) == (b.get("active_ann_pct", 0) > 0))
    result = {
        "as_of": date.today().isoformat(),
        "rule": "holdout value_sn top-20% active return keeps sign and NW t > 2",
        "rows_total": int(len(raw)),
        "rows_ey_set_nan": int(affected.sum()),
        "rows_ey_set_nan_pct": round(100 * float(affected.mean()), 3),
        "tickers_affected": int(raw.loc[affected, "ticker"].nunique()),
        "baseline": base, "missing_debt_nan": fixed,
        "verdict": "ACCEPT" if accepted else "REJECT",
    }
    out = ROOT / "data" / "reports" / f"sensitivity_missing_net_debt_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("rows_ey_set_nan", "rows_ey_set_nan_pct", "tickers_affected", "verdict")}))
    for w in ("discovery", "holdout"):
        print(w, "base", base[w]["tl"], "\n", w, "fix ", fixed[w]["tl"])
    print(out)


if __name__ == "__main__":
    main()
