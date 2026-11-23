#!/usr/bin/env python3
"""Round 3 point-in-time feature primitives and candidate signal builders.

All feature functions in this module are pure functions over DataFrames:
  - No disk I/O inside signal functions.
  - Strict point-in-time (PIT) discipline: at rebalance date ``t``, only
    fundamental rows with ``available_at <= t`` (after applying KAP report
    dates when provided), prices with ``date <= t``, and share events with
    ``date <= t`` are ever accessed.
  - Discovery-only exploration guard: coverage diagnostics default to
    ``2013-01-01 .. 2020-12-31`` so holdout (``2021+``) is never inspected
    outside the backtest harness after pre-registration.

Reusable primitives:
  - gross_profit_to_assets  (Novy-Marx 2013 GP/A)
  - accruals                (Balance-sheet NOA / WC operating accruals)
  - net_issuance            (PIT share-count NSI ex bonus splits, composite CSI, rights)
  - momentum_12_1           (12-1 price momentum from adjusted prices)
  - sue_earnings_surprise   (Foster-Olsen-Shevlin seasonal random walk SUE)
  - realized_volatility     (Daily 60d or monthly rolling realized volatility)
  - asset_growth            (YoY total asset growth)
  - operating_profitability (TTM operating profit / book equity)
  - cross_sectional_z       (Monthly winsorized z-score, optional sector neutralization)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import factor_backtest as fb  # noqa: E402
from core import pit_panel  # noqa: E402

DISCOVERY_START = pd.Timestamp("2013-01-01")
DISCOVERY_END = pd.Timestamp("2020-12-31")
HOLD_SPLIT = pd.Timestamp("2021-01-01")


# ---------------------------------------------------------------------------
# Strict PIT alignment helpers
# ---------------------------------------------------------------------------
def normalize_month_end(s: pd.Series) -> pd.Series:
    """Normalize timestamps to calendar month-end (tz-naive)."""
    dt = pd.to_datetime(s)
    if getattr(dt.dt, "tz", None) is not None:
        dt = dt.dt.tz_localize(None)
    return dt.dt.to_period("M").dt.to_timestamp("M")


def prepare_quarterly_pit(
    quarterly: pd.DataFrame,
    kap_dates: pd.DataFrame | None = None,
    strict_kap: bool = False,
) -> pd.DataFrame:
    """Return a clean, sorted copy of ``quarterly`` with PIT ``available_at``.

    If ``kap_dates`` (output of ``pit_panel.kap_report_dates``) is provided,
    replaces assumed 75/100d availability dates with actual KAP publication
    availability (next day if published at or after 18:00).
    """
    if quarterly.empty:
        return quarterly.copy()
    q = quarterly.copy()
    if "period_end" not in q.columns and "period" in q.columns:
        q["period_end"] = q["period"].map(pit_panel.period_end)
    q["period_end"] = pd.to_datetime(q["period_end"])
    if "available_at" not in q.columns and "period" in q.columns:
        q["available_at"] = q["period"].map(pit_panel.available_at)
    q["available_at"] = pd.to_datetime(q["available_at"])
    if "year" not in q.columns and "period" in q.columns:
        q["year"] = q["period"].str[:4].astype(int)
    if "q" not in q.columns and "period" in q.columns:
        q["q"] = q["period"].str[-1].astype(int)
    if kap_dates is not None and not kap_dates.empty:
        q = pit_panel.apply_report_dates(q, kap_dates, strict=strict_kap)
        q["available_at"] = pd.to_datetime(q["available_at"])
    return q.sort_values(["ticker", "available_at", "period_end"], kind="mergesort").reset_index(drop=True)


def attach_latest_pit_quarterly(
    panel: pd.DataFrame,
    q_features: pd.DataFrame,
    value_cols: list[str],
    kap_dates: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Strictly PIT backward as-of join from ``q_features`` onto ``panel``.

    For each ``(date, ticker)`` row in ``panel``, selects the latest row in
    ``q_features`` satisfying ``available_at <= date`` (tie-broken by latest
    ``period_end``). Guarantees zero lookahead and preserves ``panel.index``.
    """
    out = pd.DataFrame(index=panel.index)
    for col in value_cols:
        out[col] = np.nan
    if panel.empty or q_features.empty:
        return out

    q_pit = prepare_quarterly_pit(q_features, kap_dates=kap_dates)
    keep = ["ticker", "available_at", "period_end", *[c for c in value_cols if c in q_pit.columns]]
    q_dedup = (
        q_pit[keep]
        .sort_values(["ticker", "available_at", "period_end"], kind="mergesort")
        .drop_duplicates(subset=["ticker", "available_at"], keep="last")
        .sort_values(["available_at", "ticker"], kind="mergesort")
        .reset_index(drop=True)
    )

    left = pd.DataFrame(
        {
            "_orig_pos": np.arange(len(panel), dtype=np.int64),
            "ticker": panel["ticker"].astype(str).to_numpy(),
            "date": pd.to_datetime(panel["date"]).to_numpy(),
        }
    ).sort_values(["date", "ticker"], kind="mergesort")

    q_dedup["ticker"] = q_dedup["ticker"].astype(str)
    # Match timestamp resolution before merge_asof (pandas >=2 enforces matching units)
    left["date"] = left["date"].astype("datetime64[ns]")
    q_dedup["available_at"] = q_dedup["available_at"].astype("datetime64[ns]")

    merged = pd.merge_asof(
        left,
        q_dedup,
        left_on="date",
        right_on="available_at",
        by="ticker",
        direction="backward",
        allow_exact_matches=True,
    )
    merged = merged.sort_values("_orig_pos", kind="mergesort")
    for col in value_cols:
        if col in merged.columns:
            out[col] = merged[col].to_numpy()
    return out


def _attach_yoy_lag(
    q_pit: pd.DataFrame,
    cols: list[str],
    min_days: int = 350,
    max_days: int = 380,
) -> pd.DataFrame:
    """Attach exact 4-quarter (year - 1, same q) causal lag columns ``<col>_ya``.

    Enforces both calendar spacing (``350 <= period_end diff <= 380`` days) and
    strict PIT causality (``available_at_ya <= available_at``) so a late-filed
    prior-year report never leaks into an earlier availability date.
    """
    base = q_pit.copy()
    prev = base[["ticker", "year", "q", "period_end", "available_at", *cols]].copy()
    prev["year"] = prev["year"] + 1
    rename = {"period_end": "_period_end_ya", "available_at": "_available_at_ya", **{c: f"{c}_ya" for c in cols}}
    prev = prev.rename(columns=rename).drop_duplicates(subset=["ticker", "year", "q"], keep="last")
    merged = base.merge(prev, on=["ticker", "year", "q"], how="left")
    days = (merged["period_end"] - merged["_period_end_ya"]).dt.days
    valid_lag = days.between(min_days, max_days) & (merged["_available_at_ya"] <= merged["available_at"])
    for c in cols:
        merged[f"{c}_ya"] = merged[f"{c}_ya"].where(valid_lag)
    return merged


def _cpi_ratio_yoy(q_with_ya: pd.DataFrame, cpi: pd.Series | None) -> np.ndarray:
    """Return CPI(period_end) / CPI(period_end_ya) if ``cpi`` is provided, else 1.0."""
    if cpi is None:
        return np.ones(len(q_with_ya), dtype=float)
    m_now = q_with_ya["period_end"].dt.to_period("M")
    m_ya = q_with_ya["_period_end_ya"].dt.to_period("M")
    c_now = m_now.map(cpi).to_numpy(dtype=float)
    c_ya = m_ya.map(cpi).to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.isfinite(c_now) & np.isfinite(c_ya) & (c_ya > 0.0), c_now / c_ya, np.nan)


# ---------------------------------------------------------------------------
# Reusable PIT Feature Primitives
# ---------------------------------------------------------------------------
def gross_profit_to_assets(
    panel: pd.DataFrame,
    quarterly: pd.DataFrame,
    kap_dates: pd.DataFrame | None = None,
) -> pd.Series:
    """Novy-Marx (2013) Gross Profitability: ``ttm_gross_profit / total_assets``.

    Units: dimensionless ratio (TL / TL).
    Requires strictly positive ``total_assets`` and finite ``ttm_gross_profit``
    from the latest quarterly filing with ``available_at <= date``.
    """
    q = prepare_quarterly_pit(quarterly, kap_dates=kap_dates)
    if q.empty or "ttm_gross_profit" not in q.columns or "total_assets" not in q.columns:
        return pd.Series(np.nan, index=panel.index, dtype=float, name="gpa")
    gp = q["ttm_gross_profit"].to_numpy(dtype=float)
    ta = q["total_assets"].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        q["_gpa"] = np.where(np.isfinite(gp) & np.isfinite(ta) & (ta > 0.0), gp / ta, np.nan)
    res = attach_latest_pit_quarterly(panel, q, ["_gpa"])
    return pd.Series(res["_gpa"].to_numpy(dtype=float), index=panel.index, name="gpa")


def accruals(
    panel: pd.DataFrame,
    quarterly: pd.DataFrame,
    method: str = "noa",
    cpi: pd.Series | None = None,
    kap_dates: pd.DataFrame | None = None,
) -> pd.Series:
    """Point-in-time balance-sheet operating accruals.

    Methods:
      - ``"noa"`` (default; Richardson et al. 2005 change in Net Operating Assets):
          ``NOA = (total_assets - cash) - (current_liab + noncurrent_liab - fin_debt)``
          ``accruals = (NOA_t - k * NOA_{t-4q}) / (0.5 * (TA_t + k * TA_{t-4q}))``
      - ``"wc"`` (Sloan 1996 working-capital operating accruals approximation):
          ``NWC = (current_assets - cash) - current_liab``
          ``accruals = (NWC_t - k * NWC_{t-4q}) / (0.5 * (TA_t + k * TA_{t-4q}))``
      - ``"noa_level"`` (Hirshleifer et al. 2004 scaled NOA level):
          ``NOA_t / total_assets_t``

    Where ``k = CPI(period_end_t) / CPI(period_end_{t-4q})`` if ``cpi`` is given,
    else ``1.0``. Units: dimensionless ratio (TL / TL). Higher values denote
    higher accruals (lower earnings quality; sign = -1 in return prediction).
    """
    if method not in ("noa", "wc", "noa_level"):
        raise ValueError(f"Unsupported accruals method: {method!r}")
    q = prepare_quarterly_pit(quarterly, kap_dates=kap_dates)
    if q.empty:
        return pd.Series(np.nan, index=panel.index, dtype=float, name=f"accruals_{method}")

    if method in ("noa", "noa_level"):
        req = ("total_assets", "cash", "current_liab", "noncurrent_liab", "fin_debt")
        if any(c not in q.columns for c in req):
            return pd.Series(np.nan, index=panel.index, dtype=float, name=f"accruals_{method}")
        q["_stock"] = (
            q["total_assets"].astype(float)
            - q["cash"].astype(float)
            - (q["current_liab"].astype(float) + q["noncurrent_liab"].astype(float) - q["fin_debt"].astype(float))
        )
    else:
        req = ("total_assets", "current_assets", "cash", "current_liab")
        if any(c not in q.columns for c in req):
            return pd.Series(np.nan, index=panel.index, dtype=float, name=f"accruals_{method}")
        q["_stock"] = (
            q["current_assets"].astype(float) - q["cash"].astype(float) - q["current_liab"].astype(float)
        )

    if method == "noa_level":
        ta = q["total_assets"].to_numpy(dtype=float)
        st = q["_stock"].to_numpy(dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            q["_acc"] = np.where(np.isfinite(st) & np.isfinite(ta) & (ta > 0.0), st / ta, np.nan)
    else:
        qw = _attach_yoy_lag(q, ["_stock", "total_assets"])
        k = _cpi_ratio_yoy(qw, cpi)
        st_now = qw["_stock"].to_numpy(dtype=float)
        st_ya = qw["_stock_ya"].to_numpy(dtype=float)
        ta_now = qw["total_assets"].to_numpy(dtype=float)
        ta_ya = qw["total_assets_ya"].to_numpy(dtype=float)
        valid = (
            np.isfinite(st_now)
            & np.isfinite(st_ya)
            & np.isfinite(ta_now)
            & np.isfinite(ta_ya)
            & np.isfinite(k)
            & (ta_now > 0.0)
            & (ta_ya > 0.0)
            & (k > 0.0)
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            avg_ta = 0.5 * (ta_now + k * ta_ya)
            qw["_acc"] = np.where(valid & (avg_ta > 0.0), (st_now - k * st_ya) / avg_ta, np.nan)
        q = qw

    res = attach_latest_pit_quarterly(panel, q, ["_acc"])
    return pd.Series(res["_acc"].to_numpy(dtype=float), index=panel.index, name=f"accruals_{method}")


def _pit_shares_for_ticker(
    dates: np.ndarray,
    qt: pd.DataFrame,
    ev: pd.DataFrame,
) -> np.ndarray:
    """Compute PIT share counts at each timestamp in ``dates`` using ``pit_panel.shares_at``."""
    out = np.full(len(dates), np.nan, dtype=float)
    if qt.empty or "paid_in" not in qt.columns:
        return out
    avail_arr = qt["available_at"].to_numpy(dtype="datetime64[ns]")
    paid_arr = pd.to_numeric(qt["paid_in"], errors="coerce").to_numpy(dtype=float)
    pend_arr = qt["period_end"].to_numpy(dtype="datetime64[ns]")
    dates_ns = dates.astype("datetime64[ns]")
    idx_arr = np.searchsorted(avail_arr, dates_ns, side="right") - 1
    has_ev = not ev.empty
    ev_dates = ev["date"].to_numpy(dtype="datetime64[ns]") if has_ev else None
    lookback_ns = np.timedelta64(pit_panel.SHARE_EVENT_LOOKBACK_DAYS, "D")
    hist_df = qt[["period_end", "paid_in"]] if has_ev else None

    for i, last_idx in enumerate(idx_arr):
        if last_idx < 0:
            continue
        paid_in = paid_arr[last_idx]
        if not np.isfinite(paid_in) or paid_in <= 0.0:
            continue
        if not has_ev:
            out[i] = float(paid_in)
            continue
        t_ns = dates_ns[i]
        pe_ns = pend_arr[last_idx]
        # Fast path when no event falls in (stmt_end - 365d, t]
        if not np.any((ev_dates <= t_ns) & (ev_dates > pe_ns - lookback_ns)):
            out[i] = float(paid_in)
            continue
        out[i] = float(
            pit_panel.shares_at(
                pd.Timestamp(t_ns),
                float(paid_in),
                pd.Timestamp(pe_ns),
                ev,
                hist_df.iloc[: last_idx + 1],
            )
        )
    return out


def net_issuance(
    panel: pd.DataFrame,
    quarterly: pd.DataFrame | None = None,
    share_events: pd.DataFrame | None = None,
    prices: pd.DataFrame | None = None,
    method: str = "shares",
    lookback_months: int = 12,
    kap_dates: pd.DataFrame | None = None,
) -> pd.Series:
    """Point-in-time net equity issuance over trailing ``lookback_months``.

    Methods:
      - ``"shares"`` (default): log growth in PIT split-adjusted share counts from
        ``paid_in`` (nominal 1 TL par on BIST) + ``share_events`` via
        ``pit_panel.shares_at``, dividing out pure bonus splits (``bonus_pct``)
        in ``(t - lookback, t]`` so pure stock splits yield ``0.0`` while rights
        issues, private placements, and conversions yield positive log issuance.
      - ``"composite"`` (Daniel & Titman 2006):
        ``log(mcap_t / mcap_{t-L}) - log(adj_t / adj_{t-L})``.
      - ``"rights"``: log cumulative rights-issue dilution
        ``sum(log(1 + rights_pct / 100))`` over ``(t - L, t]``.

    Units: log share growth (dimensionless). Higher = more dilution (sign = -1).
    """
    if method not in ("shares", "composite", "rights"):
        raise ValueError(f"Unsupported net_issuance method: {method!r}")
    if lookback_months <= 0:
        raise ValueError("lookback_months must be positive")
    if panel.empty:
        return pd.Series(dtype=float, name=f"nsi_{method}")

    p_dates = pd.to_datetime(panel["date"])
    tickers = panel["ticker"].astype(str)

    ev_clean = pd.DataFrame(columns=["ticker", "date", "rights_pct", "bonus_pct"])
    if share_events is not None and not share_events.empty:
        ev_clean = share_events.copy()
        ev_clean["ticker"] = ev_clean["ticker"].astype(str)
        ev_clean["date"] = pd.to_datetime(ev_clean["date"])
        if getattr(ev_clean["date"].dt, "tz", None) is not None:
            ev_clean["date"] = ev_clean["date"].dt.tz_localize(None)
        ev_clean["rights_pct"] = pd.to_numeric(ev_clean.get("rights_pct", 0.0), errors="coerce").fillna(0.0)
        ev_clean["bonus_pct"] = pd.to_numeric(ev_clean.get("bonus_pct", 0.0), errors="coerce").fillna(0.0)

    if method == "rights":
        ev_by = {tk: g for tk, g in ev_clean.groupby("ticker")}
        out = np.zeros(len(panel), dtype=float)
        for idx_pos, (tk, dt) in enumerate(zip(tickers.to_numpy(), p_dates.to_numpy())):
            ev = ev_by.get(tk)
            if ev is None or ev.empty:
                continue
            ts = pd.Timestamp(dt)
            start = ts - pd.DateOffset(months=lookback_months)
            e = ev[(ev["date"] > start) & (ev["date"] <= ts)]
            if not e.empty:
                r_fac = 1.0 + e["rights_pct"].to_numpy(dtype=float) / 100.0
                r_fac = r_fac[r_fac > 0.0]
                if len(r_fac):
                    out[idx_pos] = float(np.sum(np.log(r_fac)))
        return pd.Series(out, index=panel.index, name="nsi_rights")

    if method == "composite":
        if prices is None or prices.empty or "mcap" not in panel.columns:
            return pd.Series(np.nan, index=panel.index, dtype=float, name="nsi_composite")
        px = prices[["date", "ticker", "adj"]].copy()
        px["ticker"] = px["ticker"].astype(str)
        px["date"] = normalize_month_end(px["date"])
        px["adj"] = pd.to_numeric(px["adj"], errors="coerce")
        px = px.drop_duplicates(subset=["ticker", "date"], keep="last")
        px_wide = px.pivot(index="date", columns="ticker", values="adj")

        mc = pd.DataFrame(
            {
                "date": normalize_month_end(p_dates),
                "ticker": tickers,
                "mcap": pd.to_numeric(panel["mcap"], errors="coerce"),
            }
        ).drop_duplicates(subset=["ticker", "date"], keep="last")
        mc_wide = mc.pivot(index="date", columns="ticker", values="mcap")

        all_months = pd.date_range(
            min(px_wide.index.min(), mc_wide.index.min()),
            max(px_wide.index.max(), mc_wide.index.max()),
            freq="ME",
        )
        px_wide = px_wide.reindex(all_months)
        mc_wide = mc_wide.reindex(all_months)

        with np.errstate(divide="ignore", invalid="ignore"):
            mcap_ratio = mc_wide / mc_wide.shift(lookback_months)
            px_ratio = px_wide / px_wide.shift(lookback_months)
            valid = (mc_wide > 0) & (mc_wide.shift(lookback_months) > 0) & (px_wide > 0) & (px_wide.shift(lookback_months) > 0)
            csi_wide = (np.log(mcap_ratio) - np.log(px_ratio)).where(valid)

        csi_long = csi_wide.stack().rename("_csi")
        key = pd.MultiIndex.from_arrays([normalize_month_end(p_dates), tickers])
        return pd.Series(csi_long.reindex(key).to_numpy(dtype=float), index=panel.index, name="nsi_composite")

    # method == "shares"
    if quarterly is None or quarterly.empty:
        return pd.Series(np.nan, index=panel.index, dtype=float, name="nsi_shares")
    q_pit = prepare_quarterly_pit(quarterly, kap_dates=kap_dates)
    q_pit["ticker"] = q_pit["ticker"].astype(str)
    q_by = {tk: g.reset_index(drop=True) for tk, g in q_pit.groupby("ticker")}
    ev_by = {tk: g.reset_index(drop=True) for tk, g in ev_clean.groupby("ticker")}

    out = np.full(len(panel), np.nan, dtype=float)
    work = pd.DataFrame(
        {"pos": np.arange(len(panel), dtype=np.int64), "ticker": tickers.to_numpy(), "date": p_dates.to_numpy()}
    )
    for tk, g in work.groupby("ticker", sort=False):
        qt = q_by.get(tk)
        if qt is None or qt.empty:
            continue
        ev = ev_by.get(tk, pd.DataFrame(columns=["date", "rights_pct", "bonus_pct"]))
        dates_now = g["date"].to_numpy()
        dates_prev = np.array(
            [(pd.Timestamp(d) - pd.DateOffset(months=lookback_months)).to_datetime64() for d in dates_now]
        )
        sh_now = _pit_shares_for_ticker(dates_now, qt, ev)
        sh_prev = _pit_shares_for_ticker(dates_prev, qt, ev)
        pos_arr = g["pos"].to_numpy()
        for k_i in range(len(pos_arr)):
            s1, s0 = sh_now[k_i], sh_prev[k_i]
            if not (np.isfinite(s1) and np.isfinite(s0) and s1 > 0.0 and s0 > 0.0):
                continue
            t1 = pd.Timestamp(dates_now[k_i])
            t0 = pd.Timestamp(dates_prev[k_i])
            bonus_fac = 1.0
            if not ev.empty:
                eb = ev[(ev["date"] > t0) & (ev["date"] <= t1)]
                if not eb.empty:
                    # Only divide out bonus splits that are actually reflected or not expired in s1
                    # (matching pit_panel.shares_at reflection semantics).
                    for _, erow in eb.iterrows():
                        bp = float(erow["bonus_pct"])
                        if bp <= 0.0:
                            continue
                        bf = 1.0 + bp / 100.0
                        # Check if event expired unreflected in latest balance sheet at t1
                        avail_t1 = qt[qt["available_at"] <= t1]
                        last_t1 = avail_t1.iloc[-1]
                        stmt_end = pd.Timestamp(last_t1["period_end"])
                        ev_dt = pd.Timestamp(erow["date"])
                        expired = stmt_end > ev_dt + pd.Timedelta(days=pit_panel.SHARE_EVENT_EXPIRY_DAYS)
                        if expired:
                            h = avail_t1[
                                (avail_t1["period_end"] < ev_dt)
                                & (avail_t1["period_end"] >= ev_dt - pd.Timedelta(days=pit_panel.SHARE_EVENT_LOOKBACK_DAYS))
                                & (avail_t1["period_end"] <= stmt_end)
                            ]["paid_in"]
                            h = h[h > 0]
                            if len(h):
                                before = float(h.min())
                                full_fac = 1.0 + (float(erow["rights_pct"]) + bp) / 100.0
                                reflected = float(last_t1["paid_in"]) >= before * (
                                    1.0 + pit_panel.SHARE_EVENT_REFLECTED_SHARE * (full_fac - 1.0)
                                )
                                if not reflected:
                                    continue
                        bonus_fac *= bf
            out[pos_arr[k_i]] = math.log(s1 / (s0 * bonus_fac))
    return pd.Series(out, index=panel.index, name="nsi_shares")


def momentum_12_1(
    panel: pd.DataFrame,
    prices: pd.DataFrame,
    lookback_months: int = 12,
    skip_months: int = 1,
) -> pd.Series:
    """Point-in-time price momentum ``adj[t - skip] / adj[t - lookback] - 1``.

    Uses exact calendar month-end grid from ``prices`` (``date, ticker, adj``),
    strictly ``<= t``. Default ``lookback_months=12, skip_months=1`` matches
    Jegadeesh & Titman (1993) 12-1 momentum and ``pit_panel.build_monthly_factors``.
    Units: fractional return (dimensionless).
    """
    if skip_months < 0 or lookback_months <= skip_months:
        raise ValueError("Require lookback_months > skip_months >= 0")
    if panel.empty or prices.empty:
        return pd.Series(np.nan, index=panel.index, dtype=float, name=f"mom_{lookback_months}_{skip_months}")

    px = prices[["date", "ticker", "adj"]].copy()
    px["ticker"] = px["ticker"].astype(str)
    px["date"] = normalize_month_end(px["date"])
    px["adj"] = pd.to_numeric(px["adj"], errors="coerce")
    px = px.drop_duplicates(subset=["ticker", "date"], keep="last")

    wide = px.pivot(index="date", columns="ticker", values="adj")
    full_idx = pd.date_range(wide.index.min(), wide.index.max(), freq="ME")
    wide = wide.reindex(full_idx)

    p_end = wide.shift(skip_months)
    p_start = wide.shift(lookback_months)
    with np.errstate(divide="ignore", invalid="ignore"):
        mom_wide = (p_end / p_start - 1.0).where((p_end > 0.0) & (p_start > 0.0))

    mom_long = mom_wide.stack()
    key = pd.MultiIndex.from_arrays([normalize_month_end(panel["date"]), panel["ticker"].astype(str)])
    return pd.Series(
        mom_long.reindex(key).to_numpy(dtype=float),
        index=panel.index,
        name=f"mom_{lookback_months}_{skip_months}",
    )


def sue_earnings_surprise(
    panel: pd.DataFrame,
    quarterly: pd.DataFrame,
    col: str = "q_ni_parent",
    fallback_col: str | None = "q_net_income",
    std_window: int = 8,
    min_obs: int = 8,
    kap_dates: pd.DataFrame | None = None,
) -> pd.Series:
    """Foster-Olsen-Shevlin seasonal random-walk Standardized Unexpected Earnings (SUE).

    For each quarterly report ``i`` available at rebalance date ``t``:
      ``chg_i = q_val_i - q_val_{i-4q}`` (exact same fiscal quarter 1 year prior,
      requiring ``available_at_{i-4q} <= available_at_i``)
      ``SUE_i = chg_i / std(chg_{trailing std_window}, ddof=1)``

    Requires at least ``min_obs`` valid seasonal differences within the trailing
    window (all strictly available on or before ``available_at_i``) and ``std > 0``.
    Units: standardized z-score (dimensionless).
    """
    if std_window < 2 or min_obs < 2 or min_obs > std_window:
        raise ValueError("Require 2 <= min_obs <= std_window")
    q = prepare_quarterly_pit(quarterly, kap_dates=kap_dates)
    if q.empty or col not in q.columns:
        return pd.Series(np.nan, index=panel.index, dtype=float, name="sue")

    val = pd.to_numeric(q[col], errors="coerce")
    if fallback_col and fallback_col in q.columns:
        fb_val = pd.to_numeric(q[fallback_col], errors="coerce")
        val = val.where(val.notna() & np.isfinite(val), fb_val)
    q["_qval"] = val
    q = _attach_yoy_lag(q, ["_qval"])
    q["_chg"] = q["_qval"] - q["_qval_ya"]

    # Compute strictly causal trailing std per ticker in (available_at, period_end) order.
    sue_vals = np.full(len(q), np.nan, dtype=float)
    for _, grp in q.groupby("ticker", sort=False):
        idxs = grp.index.to_numpy()
        chgs = grp["_chg"].to_numpy(dtype=float)
        pends = grp["period_end"].to_numpy()
        # Keep only non-null chg observations whose period_end <= current period_end
        # (and since grp is sorted by available_at, all earlier rows satisfy available_at <= current).
        for pos in range(len(idxs)):
            c_cur = chgs[pos]
            if not np.isfinite(c_cur):
                continue
            cur_pe = pends[pos]
            # Past + current rows already available at or before current available_at
            prior_mask = (pends[: pos + 1] <= cur_pe) & np.isfinite(chgs[: pos + 1])
            hist = chgs[: pos + 1][prior_mask]
            # Sort eligible history by period_end so window is the last `std_window` fiscal quarters
            order = np.argsort(pends[: pos + 1][prior_mask], kind="mergesort")
            hist = hist[order]
            if len(hist) < min_obs:
                continue
            win = hist[-std_window:]
            sd = float(np.std(win, ddof=1))
            if np.isfinite(sd) and sd > 0.0:
                sue_vals[idxs[pos]] = c_cur / sd

    q["_sue"] = sue_vals
    res = attach_latest_pit_quarterly(panel, q, ["_sue"])
    return pd.Series(res["_sue"].to_numpy(dtype=float), index=panel.index, name="sue")


def realized_volatility(
    panel: pd.DataFrame,
    prices: pd.DataFrame | None = None,
    daily_frames: dict[str, pd.DataFrame] | None = None,
    window_days: int = 60,
    min_days: int = 40,
    window_months: int = 12,
    min_months: int = 10,
    annualize: bool = False,
) -> pd.Series:
    """Point-in-time realized return volatility strictly using prices ``<= t``.

    Modes:
      - If ``daily_frames`` (``dict[ticker, DataFrame]`` with ``Close`` column
        indexed by trading dates) is provided: computes rolling ``window_days``
        daily return std (``min_periods=min_days``) as of the last trading day
        ``<= t``. Multiply by ``sqrt(252)`` if ``annualize=True``.
      - Else uses monthly ``prices`` (``date, ticker, adj``): computes rolling
        ``window_months`` monthly simple return std (``min_periods=min_months``)
        strictly ``<= t``. Multiply by ``sqrt(12)`` if ``annualize=True``.

    Units: return standard deviation (dimensionless fraction per period or annualized).
    """
    if panel.empty:
        return pd.Series(dtype=float, name="volatility")

    if daily_frames is not None:
        out = np.full(len(panel), np.nan, dtype=float)
        scale = math.sqrt(252.0) if annualize else 1.0
        work = pd.DataFrame(
            {
                "pos": np.arange(len(panel), dtype=np.int64),
                "ticker": panel["ticker"].astype(str).to_numpy(),
                "date": pd.to_datetime(panel["date"]).to_numpy(),
            }
        )
        for tk, g in work.groupby("ticker", sort=False):
            df_d = daily_frames.get(tk)
            if df_d is None or df_d.empty or "Close" not in df_d.columns:
                continue
            s = pd.to_numeric(df_d["Close"], errors="coerce").dropna()
            idx = pd.to_datetime(s.index)
            if getattr(idx, "tz", None) is not None:
                idx = idx.tz_localize(None)
            s = pd.Series(s.to_numpy(dtype=float), index=idx.normalize())
            s = s[~s.index.duplicated(keep="last")].sort_index()
            s = s[s > 0.0]
            if len(s) < min_days + 1:
                continue
            vol = s.pct_change().rolling(window_days, min_periods=min_days).std() * scale
            vol_idx = vol.index.to_numpy()
            vol_vals = vol.to_numpy(dtype=float)
            for pos, dt in zip(g["pos"].to_numpy(), g["date"].to_numpy()):
                j = int(np.searchsorted(vol_idx, dt, side="right")) - 1
                if j >= 0:
                    out[pos] = vol_vals[j]
        return pd.Series(out, index=panel.index, name=f"vol_{window_days}d")

    if prices is None or prices.empty:
        return pd.Series(np.nan, index=panel.index, dtype=float, name=f"vol_{window_months}m")

    px = prices[["date", "ticker", "adj"]].copy()
    px["ticker"] = px["ticker"].astype(str)
    px["date"] = normalize_month_end(px["date"])
    px["adj"] = pd.to_numeric(px["adj"], errors="coerce")
    px = px.drop_duplicates(subset=["ticker", "date"], keep="last")

    wide = px.pivot(index="date", columns="ticker", values="adj")
    full_idx = pd.date_range(wide.index.min(), wide.index.max(), freq="ME")
    wide = wide.reindex(full_idx)
    rets = wide.pct_change(fill_method=None)
    scale = math.sqrt(12.0) if annualize else 1.0
    vol_wide = rets.rolling(window_months, min_periods=min_months).std() * scale
    vol_long = vol_wide.stack()
    key = pd.MultiIndex.from_arrays([normalize_month_end(panel["date"]), panel["ticker"].astype(str)])
    return pd.Series(
        vol_long.reindex(key).to_numpy(dtype=float),
        index=panel.index,
        name=f"vol_{window_months}m",
    )


def asset_growth(
    panel: pd.DataFrame,
    quarterly: pd.DataFrame,
    cpi: pd.Series | None = None,
    kap_dates: pd.DataFrame | None = None,
) -> pd.Series:
    """Cooper-Gulen-Schill (2008) YoY total asset growth: ``TA_t / (k * TA_{t-4q}) - 1``.

    Units: dimensionless fractional growth. Higher = more investment (sign = -1).
    """
    q = prepare_quarterly_pit(quarterly, kap_dates=kap_dates)
    if q.empty or "total_assets" not in q.columns:
        return pd.Series(np.nan, index=panel.index, dtype=float, name="asset_growth")
    qw = _attach_yoy_lag(q, ["total_assets"])
    k = _cpi_ratio_yoy(qw, cpi)
    ta_now = qw["total_assets"].to_numpy(dtype=float)
    ta_ya = qw["total_assets_ya"].to_numpy(dtype=float)
    valid = np.isfinite(ta_now) & np.isfinite(ta_ya) & np.isfinite(k) & (ta_now > 0.0) & (ta_ya > 0.0) & (k > 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        qw["_ag"] = np.where(valid, ta_now / (k * ta_ya) - 1.0, np.nan)
    res = attach_latest_pit_quarterly(panel, qw, ["_ag"])
    return pd.Series(res["_ag"].to_numpy(dtype=float), index=panel.index, name="asset_growth")


def operating_profitability(
    panel: pd.DataFrame,
    quarterly: pd.DataFrame,
    kap_dates: pd.DataFrame | None = None,
) -> pd.Series:
    """Fama-French (2015) operating profitability: ``ttm_op_profit / equity``.

    Uses ``equity_parent`` with fallback to ``equity`` (matching ``pit_panel._equity``).
    Requires strictly positive book equity. Units: dimensionless ratio (TL / TL).
    """
    q = prepare_quarterly_pit(quarterly, kap_dates=kap_dates)
    if q.empty or "ttm_op_profit" not in q.columns:
        return pd.Series(np.nan, index=panel.index, dtype=float, name="op_prof")
    eq_p = pd.to_numeric(q["equity_parent"], errors="coerce") if "equity_parent" in q.columns else pd.Series(np.nan, index=q.index)
    eq_t = pd.to_numeric(q["equity"], errors="coerce") if "equity" in q.columns else pd.Series(np.nan, index=q.index)
    eq = eq_p.where(eq_p.notna() & np.isfinite(eq_p), eq_t).to_numpy(dtype=float)
    op = pd.to_numeric(q["ttm_op_profit"], errors="coerce").to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        q["_op"] = np.where(np.isfinite(op) & np.isfinite(eq) & (eq > 0.0), op / eq, np.nan)
    res = attach_latest_pit_quarterly(panel, q, ["_op"])
    return pd.Series(res["_op"].to_numpy(dtype=float), index=panel.index, name="op_prof")


# ---------------------------------------------------------------------------
# Cross-sectional standardization (strictly within each month)
# ---------------------------------------------------------------------------
def cross_sectional_z(
    panel: pd.DataFrame,
    values: pd.Series,
    sign: int = 1,
    lo: float = 0.01,
    hi: float = 0.99,
    sector_neutral: bool = False,
    min_sector_n: int = 5,
) -> pd.Series:
    """Monthly cross-sectional winsorized z-score (+ optional sector neutralization).

    Strictly operates within each ``date`` cross-section (zero temporal lookahead).
    """
    if panel.empty:
        return pd.Series(dtype=float)
    tmp = pd.DataFrame({"date": panel["date"], "_val": float(sign) * pd.to_numeric(values, errors="coerce")}, index=panel.index)
    if "sector" in panel.columns:
        tmp["sector"] = panel["sector"]
    z = tmp.groupby("date", group_keys=False)["_val"].apply(lambda s: fb.winsorize_z(s, lo=lo, hi=hi))
    z = z.reindex(panel.index)
    if sector_neutral:
        if "sector" not in tmp.columns:
            raise ValueError("sector column required for sector_neutral=True")
        tmp["_z"] = z
        z = fb.sector_neutralize(tmp, "_z", min_n=min_sector_n)
    return z.rename(f"{values.name or 'signal'}_z")


# ---------------------------------------------------------------------------
# Candidate Registry & Discovery-Only Coverage Diagnostics
# ---------------------------------------------------------------------------
CANDIDATE_BUILDERS: dict[str, Callable[..., pd.Series]] = {}


def register_candidate(name: str):
    """Decorator registering a candidate signal builder in ``CANDIDATE_BUILDERS``."""
    def _wrap(fn: Callable[..., pd.Series]) -> Callable[..., pd.Series]:
        CANDIDATE_BUILDERS[name] = fn
        return fn
    return _wrap


def compute_coverage_stats(
    df: pd.DataFrame,
    signal_col: str,
    r0_col: str = "value_sn_z",
    discovery_only: bool = True,
) -> dict:
    """Compute PIT coverage and distribution diagnostics for ``signal_col``.

    By default restricted strictly to discovery (``2013-01-01 .. 2020-12-31``)
    to uphold holdout discipline.
    """
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    if discovery_only:
        d = d[(d["date"] >= DISCOVERY_START) & (d["date"] <= DISCOVERY_END)]
    if d.empty:
        return {"rows": 0, "months": 0, "coverage_pct": 0.0}

    s = pd.to_numeric(d[signal_col], errors="coerce")
    finite = np.isfinite(s.to_numpy(dtype=float))
    s_clean = s[finite]

    out: dict = {
        "window": f"{d['date'].min().date()} .. {d['date'].max().date()}",
        "discovery_only": bool(discovery_only),
        "rows": int(len(d)),
        "months": int(d["date"].nunique()),
        "tickers": int(d["ticker"].nunique()),
        "non_null_rows": int(finite.sum()),
        "coverage_pct": round(100.0 * float(finite.mean()), 2),
        "inf_count": int(np.isinf(s.to_numpy(dtype=float)).sum()),
    }
    if r0_col in d.columns:
        r0_mask = d[r0_col].notna()
        if r0_mask.any():
            out["coverage_within_R0_pct"] = round(100.0 * float(finite[r0_mask.to_numpy()].mean()), 2)
            both = r0_mask & pd.Series(finite, index=d.index)
            if both.sum() >= 30:
                corr = d.loc[both, signal_col].corr(d.loc[both, r0_col], method="spearman")
                out["spearman_corr_with_R0"] = round(float(corr), 4) if np.isfinite(corr) else None

    per_month = pd.Series(finite, index=d.index).groupby(d["date"]).mean() * 100.0
    out["monthly_coverage_min_pct"] = round(float(per_month.min()), 2)
    out["monthly_coverage_median_pct"] = round(float(per_month.median()), 2)
    out["monthly_coverage_max_pct"] = round(float(per_month.max()), 2)

    by_year = (pd.Series(finite, index=d.index).groupby(d["date"].dt.year).mean() * 100.0).round(2).to_dict()
    out["by_year_coverage_pct"] = {int(k): float(v) for k, v in by_year.items()}

    if len(s_clean):
        q = s_clean.quantile([0.01, 0.25, 0.50, 0.75, 0.99])
        out["quantiles"] = {
            "p01": round(float(q.loc[0.01]), 4),
            "p25": round(float(q.loc[0.25]), 4),
            "p50": round(float(q.loc[0.50]), 4),
            "p75": round(float(q.loc[0.75]), 4),
            "p99": round(float(q.loc[0.99]), 4),
        }
    return out


def format_coverage_markdown(
    name: str,
    stats_lag75: dict,
    stats_kap: dict | None = None,
    notes: str = "",
) -> str:
    """Render discovery-only coverage statistics as a markdown report."""
    lines = [
        f"# Coverage Report: `{name}`",
        "",
        f"- **Window**: `{stats_lag75.get('window', 'N/A')}` (discovery-only; holdout 2021+ untouched)",
        f"- **Lag75 overall coverage**: {stats_lag75.get('coverage_pct', 0.0):.2f}% "
        f"({stats_lag75.get('non_null_rows', 0)} / {stats_lag75.get('rows', 0)} rows, "
        f"{stats_lag75.get('months', 0)} months, {stats_lag75.get('tickers', 0)} tickers)",
    ]
    if "coverage_within_R0_pct" in stats_lag75:
        lines.append(f"- **Lag75 coverage within R0 (`value_sn_z`) universe**: {stats_lag75['coverage_within_R0_pct']:.2f}%")
    if stats_lag75.get("spearman_corr_with_R0") is not None:
        lines.append(f"- **Lag75 Spearman corr with R0 (discovery)**: {stats_lag75['spearman_corr_with_R0']:+.4f}")
    lines.append(
        f"- **Lag75 monthly coverage (min / med / max)**: "
        f"{stats_lag75.get('monthly_coverage_min_pct', 0.0):.2f}% / "
        f"{stats_lag75.get('monthly_coverage_median_pct', 0.0):.2f}% / "
        f"{stats_lag75.get('monthly_coverage_max_pct', 0.0):.2f}%"
    )
    if stats_kap is not None:
        lines.append(
            f"- **KAP-dates overall coverage**: {stats_kap.get('coverage_pct', 0.0):.2f}% "
            f"(within R0: {stats_kap.get('coverage_within_R0_pct', 0.0):.2f}%)"
        )
    if "quantiles" in stats_lag75:
        q = stats_lag75["quantiles"]
        lines.append(
            f"- **Distribution (lag75)**: p01={q['p01']}, p25={q['p25']}, p50={q['p50']}, p75={q['p75']}, p99={q['p99']}"
        )
    lines.extend(["", "## Coverage by Year (Discovery 2013-2020)", "", "| Year | Lag75 % | KAP-dates % |", "| --- | ---: | ---: |"])
    by_y75 = stats_lag75.get("by_year_coverage_pct", {})
    by_ykap = stats_kap.get("by_year_coverage_pct", {}) if stats_kap else {}
    for yr in sorted(set(by_y75) | set(by_ykap)):
        v75 = f"{by_y75[yr]:.2f}%" if yr in by_y75 else "-"
        vkap = f"{by_ykap[yr]:.2f}%" if yr in by_ykap else "-"
        lines.append(f"| {yr} | {v75} | {vkap} |")
    if notes:
        lines.extend(["", "## Notes", "", notes])
    lines.append("")
    return "\n".join(lines)
