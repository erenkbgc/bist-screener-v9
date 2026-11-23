"""Turkiye ulke riski: USD Eurobond getirisi - vade eslesmis ABD Hazine getirisi (medyan).

docs/research/sovereign_spread_preregistration.md: aylik spread degisimi BIST'in ayni
ayki USD getirisini EEM'in otesinde aciklar (C1 PASS, t -8.24), ama sonraki ayi veya
yili TAHMIN ETMEZ (C2 FAIL). Bultende yalnizca risk gostergesi olarak gosterilir;
hicbir karari etkilemez.

Veri: borsapy Ziraat Eurobond arsivi (gun basina tek istek) ve yfinance ^FVX/^TNX/^TYX.
Herhangi bir kaynak cevap vermezse panel 'unavailable' doner; tarama durmaz.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MIN_YEARS, MAX_YEARS = 3.0, 30.0
UST_TENORS = (("^FVX", 5.0), ("^TNX", 10.0), ("^TYX", 30.0))
LOOKBACK_DAYS = 30
MAX_BACK_DAYS = 6
# On-kayitli C1 sonucu: spread 1 puan (100 bp) acilinca BIST USD ayni ay ~-%12.4
SENSITIVITY_PCT_PER_100BP = 12.4


def ust_curve(ust_row: pd.Series, years: float) -> float:
    xs = [t for _, t in UST_TENORS]
    ys = [float(ust_row[c]) for c, _ in UST_TENORS]
    return float(np.interp(years, xs, ys))


def median_spread(bonds: list[dict], ust_row: pd.Series, on: pd.Timestamp) -> float | None:
    """bonds: {'maturity', 'yield'} (USD). 3-30 yil vadeli tahvillerin medyan spread'i (puan)."""
    sp = []
    for b in bonds:
        yrs = (pd.Timestamp(b["maturity"]) - on).days / 365.25
        if MIN_YEARS <= yrs <= MAX_YEARS and b.get("yield") is not None:
            sp.append(float(b["yield"]) - ust_curve(ust_row, yrs))
    return float(np.median(sp)) if sp else None


def _usd_bonds(provider, day: date) -> list[dict]:
    rows = provider._fetch_bonds_for_date_cached(day.strftime("%Y-%m-%d"))
    return [{"maturity": b["maturity"], "yield": b["bid_yield"]} for b in rows
            if b.get("currency") == "USD" and b.get("bid_yield")]


def _spread_near(provider, ust: pd.DataFrame, target: date) -> tuple[date, float] | None:
    for k in range(MAX_BACK_DAYS):
        d = target - timedelta(days=k)
        if d.weekday() >= 5:
            continue
        bonds = _usd_bonds(provider, d)
        u = ust.loc[: pd.Timestamp(d)]
        if not bonds or u.empty:
            continue
        sp = median_spread(bonds, u.iloc[-1], pd.Timestamp(d))
        if sp is not None:
            return d, sp
    return None


def build_panel(as_of_date: str) -> dict:
    """Bugunku spread ve ~1 ay onceye gore degisimi. Hata -> {'status': 'unavailable'}."""
    try:
        import yfinance as yf
        from borsapy._providers.ziraat_eurobond import get_eurobond_provider

        today = datetime.strptime(as_of_date, "%Y-%m-%d").date()
        start = today - timedelta(days=LOOKBACK_DAYS + 20)
        ust = yf.download([c for c, _ in UST_TENORS], start=start.isoformat(),
                          end=(today + timedelta(days=1)).isoformat(), auto_adjust=False, progress=False)["Close"]
        ust.index = pd.to_datetime(ust.index).tz_localize(None).normalize()
        ust = ust.sort_index().ffill().dropna()
        if ust.empty:
            return {"status": "unavailable", "reason": "ust_yields_empty"}
        provider = get_eurobond_provider()
        now = _spread_near(provider, ust, today)
        prev = _spread_near(provider, ust, today - timedelta(days=LOOKBACK_DAYS))
        if now is None or prev is None:
            # 2026-10-21..24 CI kosularinda hep unavailable, lokalde ok: hangi
            # kaynagin bos dondugu log'da gorunsun (Ziraat GitHub IP'lerini engelliyor olabilir).
            days = [today - timedelta(days=k) for k in range(MAX_BACK_DAYS)]
            n_bonds = sum(len(_usd_bonds(provider, d)) for d in days if d.weekday() < 5)
            return {"status": "unavailable",
                    "reason": "eurobond_empty" if n_bonds == 0 else "no_spread_in_window"}
        return {"status": "ok", "date": now[0].isoformat(), "spread_pp": round(now[1], 2),
                "prev_date": prev[0].isoformat(), "change_bp": int(round(100 * (now[1] - prev[1]))),
                "sensitivity_pct": SENSITIVITY_PCT_PER_100BP, "per_bp": 100}
    except Exception as exc:  # noqa: BLE001 - bilgi paneli taramayi durdurmaz
        logger.warning("ulke riski spread'i alinamadi: %s", exc)
        return {"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}"[:200]}
