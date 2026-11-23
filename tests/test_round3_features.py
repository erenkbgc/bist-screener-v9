"""Unit tests for scripts/research_round3_features.py.

Covers:
  1. Strict point-in-time / zero-lookahead tests (future quarterly filings,
     future prices, future share events, KAP availability lag).
  2. Units, scale invariance, split invariance, and edge cases (non-positive
     denominators, missing quarters, no infinities).
  3. Coverage calculation and discovery-only guard (2013-2020).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import pit_panel  # noqa: E402
import research_round3_features as r3f  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic PIT fixtures
# ---------------------------------------------------------------------------
def _make_synthetic_quarterly(
    tickers: tuple[str, ...] = ("AAA", "BBB"),
    years: range = range(2016, 2021),
    scale: float = 1.0,
) -> pd.DataFrame:
    rows = []
    for t_idx, tk in enumerate(tickers):
        base = (1000.0 + 300.0 * t_idx) * scale
        for y in years:
            for q in (1, 2, 3, 4):
                per = f"{y}Q{q}"
                pe = pit_panel.period_end(per)
                avail = pit_panel.available_at(per)
                step = (y - years.start) * 4 + (q - 1)
                ta = base * (1.0 + 0.03 * step)
                cash = 0.10 * ta
                ca = 0.45 * ta
                cl = 0.25 * ta
                ncl = 0.20 * ta
                fd = 0.15 * ta
                eq = ta - cl - ncl
                q_gp = (0.08 + 0.002 * step + 0.01 * (q == 4)) * ta
                q_op = 0.50 * q_gp
                # Mild nonlinear earnings path so YoY changes have positive std for SUE
                q_ni = (0.03 + 0.0015 * step + 0.004 * math.sin(step + t_idx)) * ta
                rows.append(
                    {
                        "ticker": tk,
                        "period": per,
                        "period_end": pe,
                        "available_at": avail,
                        "year": y,
                        "q": q,
                        "total_assets": ta,
                        "cash": cash,
                        "current_assets": ca,
                        "current_liab": cl,
                        "noncurrent_liab": ncl,
                        "fin_debt": fd,
                        "equity": eq,
                        "equity_parent": eq,
                        "paid_in": 100.0 * scale,
                        "q_gross_profit": q_gp,
                        "ttm_gross_profit": 4.0 * q_gp,
                        "q_op_profit": q_op,
                        "ttm_op_profit": 4.0 * q_op,
                        "q_ni_parent": q_ni,
                        "ttm_ni_parent": 4.0 * q_ni,
                        "q_net_income": q_ni,
                        "ttm_net_income": 4.0 * q_ni,
                    }
                )
    return pd.DataFrame(rows)


def _make_synthetic_prices(
    tickers: tuple[str, ...] = ("AAA", "BBB"),
    start: str = "2017-01-31",
    end: str = "2020-12-31",
) -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="ME")
    rows = []
    for t_idx, tk in enumerate(tickers):
        px = 10.0 * (1 + t_idx)
        for i, dt in enumerate(dates):
            r = 0.015 + 0.02 * math.sin(i * 0.7 + t_idx)
            px = px * (1.0 + r)
            rows.append({"date": dt, "ticker": tk, "raw": px, "adj": px, "tlvol60": 1e7})
    return pd.DataFrame(rows)


def _make_synthetic_panel(
    tickers: tuple[str, ...] = ("AAA", "BBB"),
    dates: list[str] = ("2019-06-30", "2019-12-31", "2020-06-30", "2020-12-31"),
    scale: float = 1.0,
) -> pd.DataFrame:
    rows = []
    for dt in dates:
        for t_idx, tk in enumerate(tickers):
            rows.append(
                {
                    "date": pd.Timestamp(dt),
                    "ticker": tk,
                    "sector": f"SEC{t_idx % 2}",
                    "mcap": (2000.0 + 500.0 * t_idx) * scale,
                    "value_sn_z": 0.5 - float(t_idx),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 1. Exact value & units tests
# ---------------------------------------------------------------------------
def test_gross_profit_to_assets_exact_and_nonpositive_guard():
    panel = pd.DataFrame(
        {
            "date": [pd.Timestamp("2020-06-30"), pd.Timestamp("2020-06-30")],
            "ticker": ["AAA", "NEG"],
        }
    )
    q = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "period": "2020Q1",
                "period_end": pd.Timestamp("2020-03-31"),
                "available_at": pd.Timestamp("2020-06-14"),
                "ttm_gross_profit": 250.0,
                "total_assets": 1000.0,
            },
            {
                "ticker": "NEG",
                "period": "2020Q1",
                "period_end": pd.Timestamp("2020-03-31"),
                "available_at": pd.Timestamp("2020-06-14"),
                "ttm_gross_profit": 100.0,
                "total_assets": 0.0,
            },
        ]
    )
    gpa = r3f.gross_profit_to_assets(panel, q)
    assert gpa.iloc[0] == pytest.approx(0.25)
    assert np.isnan(gpa.iloc[1])


def test_accruals_noa_wc_and_cpi_adjustment():
    panel = pd.DataFrame({"date": [pd.Timestamp("2020-06-30")], "ticker": ["AAA"]})
    q = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "period": "2019Q1",
                "period_end": pd.Timestamp("2019-03-31"),
                "available_at": pd.Timestamp("2019-06-14"),
                "year": 2019,
                "q": 1,
                "total_assets": 1000.0,
                "cash": 100.0,
                "current_assets": 400.0,
                "current_liab": 200.0,
                "noncurrent_liab": 300.0,
                "fin_debt": 200.0,
            },
            {
                "ticker": "AAA",
                "period": "2020Q1",
                "period_end": pd.Timestamp("2020-03-31"),
                "available_at": pd.Timestamp("2020-06-14"),
                "year": 2020,
                "q": 1,
                "total_assets": 1200.0,
                "cash": 100.0,
                "current_assets": 550.0,
                "current_liab": 250.0,
                "noncurrent_liab": 300.0,
                "fin_debt": 250.0,
            },
        ]
    )
    # 2019Q1: NOA = (1000-100) - (200+300-200) = 600; NWC = (400-100) - 200 = 100
    # 2020Q1: NOA = (1200-100) - (250+300-250) = 800; NWC = (550-100) - 250 = 200
    # avg_ta = 1100
    assert r3f.accruals(panel, q, method="noa").iloc[0] == pytest.approx(200.0 / 1100.0)
    assert r3f.accruals(panel, q, method="wc").iloc[0] == pytest.approx(100.0 / 1100.0)
    assert r3f.accruals(panel, q, method="noa_level").iloc[0] == pytest.approx(800.0 / 1200.0)

    # With 20% inflation (CPI doubles from 100 to 120): real NOA_ya = 720, TA_ya = 1200 -> (800-720)/1200
    cpi = pd.Series([100.0, 120.0], index=pd.PeriodIndex(["2019-03", "2020-03"], freq="M"))
    assert r3f.accruals(panel, q, method="noa", cpi=cpi).iloc[0] == pytest.approx(80.0 / 1200.0)


def test_net_issuance_bonus_split_vs_rights_issue():
    panel = pd.DataFrame(
        {
            "date": [pd.Timestamp("2020-06-30"), pd.Timestamp("2020-06-30")],
            "ticker": ["BONUS", "RIGHTS"],
        }
    )
    q = pd.DataFrame(
        [
            {"ticker": "BONUS", "period": "2019Q1", "period_end": pd.Timestamp("2019-03-31"),
             "available_at": pd.Timestamp("2019-06-14"), "paid_in": 100.0},
            {"ticker": "BONUS", "period": "2020Q1", "period_end": pd.Timestamp("2020-03-31"),
             "available_at": pd.Timestamp("2020-06-14"), "paid_in": 200.0},
            {"ticker": "RIGHTS", "period": "2019Q1", "period_end": pd.Timestamp("2019-03-31"),
             "available_at": pd.Timestamp("2019-06-14"), "paid_in": 100.0},
            {"ticker": "RIGHTS", "period": "2020Q1", "period_end": pd.Timestamp("2020-03-31"),
             "available_at": pd.Timestamp("2020-06-14"), "paid_in": 200.0},
        ]
    )
    events = pd.DataFrame(
        [
            {"ticker": "BONUS", "date": pd.Timestamp("2019-10-15"), "rights_pct": 0.0, "bonus_pct": 100.0},
            {"ticker": "RIGHTS", "date": pd.Timestamp("2019-10-15"), "rights_pct": 100.0, "bonus_pct": 0.0},
        ]
    )
    nsi = r3f.net_issuance(panel, quarterly=q, share_events=events, method="shares")
    assert nsi.iloc[0] == pytest.approx(0.0, abs=1e-12)
    assert nsi.iloc[1] == pytest.approx(math.log(2.0), rel=1e-9)

    nsi_r = r3f.net_issuance(panel, share_events=events, method="rights")
    assert nsi_r.iloc[0] == pytest.approx(0.0)
    assert nsi_r.iloc[1] == pytest.approx(math.log(2.0))


def test_net_issuance_composite_exact():
    dates = pd.date_range("2019-06-30", "2020-06-30", freq="ME")
    panel = pd.DataFrame(
        {
            "date": [dates[0], dates[-1]],
            "ticker": ["AAA", "AAA"],
            "mcap": [1000.0, 2200.0],
        }
    )
    prices = pd.DataFrame({"date": [dates[0], dates[-1]], "ticker": ["AAA", "AAA"], "adj": [10.0, 11.0]})
    csi = r3f.net_issuance(panel, prices=prices, method="composite")
    assert np.isnan(csi.iloc[0])
    # log(2200/1000) - log(11/10) = log(2.2 / 1.1) = log(2.0)
    assert csi.iloc[1] == pytest.approx(math.log(2.0))


def test_momentum_12_1_exact_and_gap_handling():
    dates = pd.date_range("2019-01-31", "2020-06-30", freq="ME")
    # Constant 10% monthly growth: adj[t-1]/adj[t-12] - 1 = 1.1^11 - 1
    adj = [10.0 * (1.1 ** i) for i in range(len(dates))]
    prices = pd.DataFrame({"date": dates, "ticker": "AAA", "adj": adj})
    panel = pd.DataFrame({"date": [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-06-30")], "ticker": ["AAA", "AAA"]})
    mom = r3f.momentum_12_1(panel, prices)
    expected = (1.1 ** 11) - 1.0
    assert mom.iloc[0] == pytest.approx(expected, rel=1e-9)
    assert mom.iloc[1] == pytest.approx(expected, rel=1e-9)


def test_sue_and_realized_volatility_exact():
    q = _make_synthetic_quarterly(tickers=("AAA",), years=range(2016, 2021))
    panel = _make_synthetic_panel(tickers=("AAA",), dates=("2020-06-30", "2020-12-31"))
    sue = r3f.sue_earnings_surprise(panel, q)
    assert sue.notna().all()
    assert np.isfinite(sue).all()

    # Daily volatility test
    d_idx = pd.bdate_range("2020-01-01", "2020-06-30")
    rng = np.random.default_rng(42)
    rets = rng.normal(0.0, 0.02, size=len(d_idx))
    close = 100.0 * np.cumprod(1.0 + rets)
    daily_frames = {"AAA": pd.DataFrame({"Close": close}, index=d_idx)}
    vol_d = r3f.realized_volatility(panel.iloc[[0]], daily_frames=daily_frames, window_days=60, min_days=40)
    expected_vol = pd.Series(close, index=d_idx).pct_change().iloc[-60:].std()
    assert vol_d.iloc[0] == pytest.approx(expected_vol, rel=1e-12)

    # Monthly volatility test
    prices = _make_synthetic_prices(tickers=("AAA",), start="2018-01-31", end="2020-12-31")
    vol_m = r3f.realized_volatility(panel, prices=prices, window_months=12, min_months=10, annualize=True)
    assert vol_m.notna().all()
    assert (vol_m > 0).all()


def test_units_scale_invariance():
    """Multiplying all monetary units by 1e-3 (TL -> thousand TL) must not change any ratio."""
    q1 = _make_synthetic_quarterly(scale=1.0)
    q2 = _make_synthetic_quarterly(scale=1e-3)
    p1 = _make_synthetic_panel(scale=1.0)
    p2 = _make_synthetic_panel(scale=1e-3)
    prices = _make_synthetic_prices()

    for fn_name, fn in (
        ("gpa", lambda p, q: r3f.gross_profit_to_assets(p, q)),
        ("accruals_noa", lambda p, q: r3f.accruals(p, q, method="noa")),
        ("accruals_wc", lambda p, q: r3f.accruals(p, q, method="wc")),
        ("nsi_shares", lambda p, q: r3f.net_issuance(p, quarterly=q, method="shares")),
        ("nsi_composite", lambda p, q: r3f.net_issuance(p, prices=prices, method="composite")),
        ("sue", lambda p, q: r3f.sue_earnings_surprise(p, q)),
        ("asset_growth", lambda p, q: r3f.asset_growth(p, q)),
        ("op_prof", lambda p, q: r3f.operating_profitability(p, q)),
    ):
        s1 = fn(p1, q1)
        s2 = fn(p2, q2)
        np.testing.assert_allclose(s1.to_numpy(), s2.to_numpy(), rtol=1e-10, atol=1e-12, err_msg=fn_name)


# ---------------------------------------------------------------------------
# 2. Strict Lookahead & KAP Availability Lag Tests
# ---------------------------------------------------------------------------
def test_zero_lookahead_when_future_data_corrupted():
    """Corrupting all statements, prices, and events after cutoff date T MUST NOT
    change any feature value at dates <= T."""
    cutoff = pd.Timestamp("2019-12-31")
    q_base = _make_synthetic_quarterly(years=range(2016, 2021))
    px_base = _make_synthetic_prices(start="2017-01-31", end="2020-12-31")
    panel = _make_synthetic_panel(dates=("2019-06-30", "2019-12-31", "2020-06-30", "2020-12-31"))
    ev_base = pd.DataFrame(
        [{"ticker": "AAA", "date": pd.Timestamp("2019-04-15"), "rights_pct": 50.0, "bonus_pct": 0.0}]
    )

    q_fut = q_base.copy()
    fut_q_mask = q_fut["available_at"] > cutoff
    assert fut_q_mask.any()
    for c in ("total_assets", "ttm_gross_profit", "q_ni_parent", "paid_in", "cash", "ttm_op_profit"):
        q_fut.loc[fut_q_mask, c] = q_fut.loc[fut_q_mask, c] * 999.0

    px_fut = px_base.copy()
    fut_px_mask = px_fut["date"] > cutoff
    assert fut_px_mask.any()
    px_fut.loc[fut_px_mask, "adj"] = px_fut.loc[fut_px_mask, "adj"] * 50.0

    ev_fut = pd.concat(
        [
            ev_base,
            pd.DataFrame([{"ticker": "AAA", "date": pd.Timestamp("2020-02-01"), "rights_pct": 300.0, "bonus_pct": 0.0}]),
        ],
        ignore_index=True,
    )

    pre = panel["date"] <= cutoff
    assert pre.any()

    checks = [
        ("gpa", r3f.gross_profit_to_assets(panel, q_base), r3f.gross_profit_to_assets(panel, q_fut)),
        ("acc_noa", r3f.accruals(panel, q_base, method="noa"), r3f.accruals(panel, q_fut, method="noa")),
        ("acc_wc", r3f.accruals(panel, q_base, method="wc"), r3f.accruals(panel, q_fut, method="wc")),
        ("nsi_sh", r3f.net_issuance(panel, q_base, ev_base, method="shares"),
         r3f.net_issuance(panel, q_fut, ev_fut, method="shares")),
        ("nsi_ri", r3f.net_issuance(panel, share_events=ev_base, method="rights"),
         r3f.net_issuance(panel, share_events=ev_fut, method="rights")),
        ("nsi_co", r3f.net_issuance(panel, prices=px_base, method="composite"),
         r3f.net_issuance(panel, prices=px_fut, method="composite")),
        ("mom", r3f.momentum_12_1(panel, px_base), r3f.momentum_12_1(panel, px_fut)),
        ("sue", r3f.sue_earnings_surprise(panel, q_base), r3f.sue_earnings_surprise(panel, q_fut)),
        ("vol", r3f.realized_volatility(panel, prices=px_base), r3f.realized_volatility(panel, prices=px_fut)),
        ("ag", r3f.asset_growth(panel, q_base), r3f.asset_growth(panel, q_fut)),
        ("op", r3f.operating_profitability(panel, q_base), r3f.operating_profitability(panel, q_fut)),
    ]
    for name, s_base, s_fut in checks:
        np.testing.assert_allclose(
            s_base[pre].to_numpy(), s_fut[pre].to_numpy(), rtol=0.0, atol=0.0, equal_nan=True, err_msg=name
        )


def test_kap_availability_lag_respected():
    """2020Q1 filed on KAP at 2020-05-15 (available 2020-05-15) must NOT appear at
    2020-04-30, MUST appear at 2020-05-31 under KAP dates, and MUST NOT appear at
    2020-05-31 under 75-day assumed lag (available 2020-06-14)."""
    q = pd.DataFrame(
        [
            {"ticker": "AAA", "period": "2019Q4", "period_end": pd.Timestamp("2019-12-31"),
             "available_at": pd.Timestamp("2020-04-09"), "ttm_gross_profit": 100.0, "total_assets": 1000.0},
            {"ticker": "AAA", "period": "2020Q1", "period_end": pd.Timestamp("2020-03-31"),
             "available_at": pd.Timestamp("2020-06-14"), "ttm_gross_profit": 400.0, "total_assets": 1000.0},
        ]
    )
    kap = pd.DataFrame(
        [
            {"ticker": "AAA", "period": "2019Q4", "kap_available_at": pd.Timestamp("2020-03-05")},
            {"ticker": "AAA", "period": "2020Q1", "kap_available_at": pd.Timestamp("2020-05-15")},
        ]
    )
    panel = pd.DataFrame(
        {
            "date": [pd.Timestamp("2020-04-30"), pd.Timestamp("2020-05-31"), pd.Timestamp("2020-06-30")],
            "ticker": ["AAA", "AAA", "AAA"],
        }
    )
    gpa_lag75 = r3f.gross_profit_to_assets(panel, q, kap_dates=None)
    gpa_kap = r3f.gross_profit_to_assets(panel, q, kap_dates=kap)

    assert gpa_lag75.tolist() == pytest.approx([0.10, 0.10, 0.40])
    assert gpa_kap.tolist() == pytest.approx([0.10, 0.40, 0.40])


def test_cross_sectional_z_no_temporal_leakage():
    panel = pd.DataFrame(
        {
            "date": [pd.Timestamp("2020-01-31")] * 6 + [pd.Timestamp("2020-02-29")] * 6,
            "ticker": [f"T{i}" for i in range(6)] * 2,
            "sector": ["S1"] * 6 + ["S1"] * 6,
        }
    )
    vals_a = pd.Series([1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6], dtype=float)
    vals_b = pd.Series([1, 2, 3, 4, 5, 6, 100, 200, 300, 400, 500, 9999], dtype=float)
    za = r3f.cross_sectional_z(panel, vals_a, sector_neutral=True)
    zb = r3f.cross_sectional_z(panel, vals_b, sector_neutral=True)
    np.testing.assert_allclose(za.iloc[:6].to_numpy(), zb.iloc[:6].to_numpy(), atol=0.0, rtol=0.0)


# ---------------------------------------------------------------------------
# 3. Coverage & Discovery-Only Guard Tests
# ---------------------------------------------------------------------------
def test_coverage_stats_discovery_only_excludes_holdout():
    df = pd.DataFrame(
        {
            "date": [
                pd.Timestamp("2019-12-31"),
                pd.Timestamp("2020-12-31"),
                pd.Timestamp("2021-01-31"),
                pd.Timestamp("2022-01-31"),
            ],
            "ticker": ["AAA", "AAA", "AAA", "AAA"],
            "value_sn_z": [0.5, 0.5, 0.5, 0.5],
            "sig": [1.0, np.nan, 2.0, 3.0],
        }
    )
    st = r3f.compute_coverage_stats(df, "sig", discovery_only=True)
    assert st["rows"] == 2
    assert st["non_null_rows"] == 1
    assert st["coverage_pct"] == pytest.approx(50.0)
    assert 2021 not in st["by_year_coverage_pct"]
    md = r3f.format_coverage_markdown("demo_sig", st)
    assert "discovery-only" in md
    assert "| 2019 |" in md
    assert "| 2021 |" not in md


def test_real_pit_discovery_primitives_coverage_and_gpa_parity():
    """Discovery-only (2013-2020) sanity check on the read-only FP PIT panel if present."""
    fp = Path("/home/eren/bist_project/data/research/fp")
    res_dir = Path("/home/eren/bist_project/data/research")
    if not (fp / "factors_monthly.parquet").exists():
        pytest.skip("Read-only FP PIT panel not present")

    f75 = pd.read_parquet(fp / "factors_monthly.parquet")
    f75 = f75[(f75["date"] >= r3f.DISCOVERY_START) & (f75["date"] <= r3f.DISCOVERY_END)].copy()
    q = pd.read_parquet(fp / "quarterly.parquet")
    px = pd.read_parquet(res_dir / "monthly_prices.parquet")
    px = px[px["date"] <= r3f.DISCOVERY_END].copy()
    ev = pd.read_parquet(res_dir / "share_events.parquet")
    ev = ev[ev["date"] <= r3f.DISCOVERY_END].copy()

    # Exact parity on GPA against the PIT panel
    gpa_calc = r3f.gross_profit_to_assets(f75, q)
    both = f75["gpa"].notna() & gpa_calc.notna()
    assert both.mean() > 0.90
    rel = (f75.loc[both, "gpa"] - gpa_calc.loc[both]).abs() / f75.loc[both, "gpa"].abs().clip(lower=1e-9)
    assert float((rel > 1e-6).mean()) < 1e-4

    # Coverage checks across primitives on discovery (2013-2020)
    acc = r3f.accruals(f75, q, method="noa")
    nsi = r3f.net_issuance(f75, quarterly=q, share_events=ev, method="shares")
    mom = r3f.momentum_12_1(f75, px)
    sue = r3f.sue_earnings_surprise(f75, q)
    vol = r3f.realized_volatility(f75, prices=px, window_months=12, min_months=10)

    assert acc.notna().mean() > 0.70
    assert nsi.notna().mean() > 0.80
    assert mom.notna().mean() > 0.95
    assert sue.notna().mean() > 0.65
    assert vol.notna().mean() > 0.95
    for s in (gpa_calc, acc, nsi, mom, sue, vol):
        assert not np.isinf(s.dropna().to_numpy()).any()


# ---------------------------------------------------------------------------
# 4. Scholar Candidate Tests (scholar_cbop, scholar_sue_usd, scholar_real_cbop_sue)
# ---------------------------------------------------------------------------
def _make_scholar_universe(
    n_tickers: int = 12,
    years: range = range(2016, 2021),
    scale: float = 1.0,
):
    tickers = tuple(f"TK{i:02d}" for i in range(n_tickers))
    q = _make_synthetic_quarterly(tickers=tickers, years=years, scale=scale)
    # Vary operating profit & NOA growth across tickers so cross-sectional z-scores are non-degenerate
    for idx, tk in enumerate(tickers):
        m = q["ticker"] == tk
        q.loc[m, "ttm_op_profit"] = q.loc[m, "ttm_op_profit"] * (0.7 + 0.08 * idx)
        q.loc[m, "cash"] = q.loc[m, "cash"] * (0.5 + 0.1 * (idx % 5))

    dates = ("2019-06-30", "2019-12-31", "2020-06-30", "2020-12-31")
    panel = _make_synthetic_panel(tickers=tickers, dates=dates, scale=scale)
    # Attach PIT stmt_period matching lag75 available_at <= date
    q_sorted = q.sort_values(["ticker", "available_at", "period_end"])
    stmt_periods = []
    for _, row in panel.iterrows():
        avail = q_sorted[(q_sorted["ticker"] == row["ticker"]) & (q_sorted["available_at"] <= row["date"])]
        stmt_periods.append(avail.iloc[-1]["period"])
    panel["stmt_period"] = stmt_periods
    panel["value_sn_z"] = [((i % n_tickers) - n_tickers / 2.0) / 3.0 for i in range(len(panel))]

    fx_dates = pd.bdate_range("2015-12-01", "2020-12-31")
    fx = pd.DataFrame(
        {"usdtry": np.linspace(3.0, 7.5, len(fx_dates)), "xu100": np.linspace(700.0, 1400.0, len(fx_dates))},
        index=fx_dates,
    )
    m_dates = pd.date_range("2015-01-31", "2020-12-31", freq="ME")
    macro = pd.DataFrame({"cpi_mom": 1.2 + 0.2 * np.sin(np.arange(len(m_dates)))}, index=m_dates)
    return panel, q, macro, fx


def test_cbop_and_cbop_real_exact_values():
    panel = pd.DataFrame({"date": [pd.Timestamp("2020-06-30")], "ticker": ["AAA"], "stmt_period": ["2020Q1"]})
    q = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "period": "2019Q1",
                "period_end": pd.Timestamp("2019-03-31"),
                "available_at": pd.Timestamp("2019-06-14"),
                "year": 2019,
                "q": 1,
                "total_assets": 1000.0,
                "cash": 100.0,
                "current_liab": 200.0,
                "noncurrent_liab": 300.0,
                "fin_debt": 200.0,
                "ttm_op_profit": 150.0,
            },
            {
                "ticker": "AAA",
                "period": "2020Q1",
                "period_end": pd.Timestamp("2020-03-31"),
                "available_at": pd.Timestamp("2020-06-14"),
                "year": 2020,
                "q": 1,
                "total_assets": 1200.0,
                "cash": 100.0,
                "current_liab": 250.0,
                "noncurrent_liab": 300.0,
                "fin_debt": 250.0,
                "ttm_op_profit": 260.0,
            },
        ]
    )
    # NOA_2019Q1 = 600, NOA_2020Q1 = 800, delta_NOA = 200 -> cbop = (260 - 200) / 1200 = 0.05
    assert r3f.cbop_feature(panel, q).iloc[0] == pytest.approx(60.0 / 1200.0)
    # With 20% YoY CPI: NOA_ya_real = 600 * 1.2 = 720 -> delta_real = 80 -> cbop_real = (260 - 80) / 1200 = 0.15
    cpi = pd.Series([100.0, 120.0], index=pd.PeriodIndex(["2019-03", "2020-03"], freq="M"))
    assert r3f.cbop_feature(panel, q, cpi=cpi).iloc[0] == pytest.approx(180.0 / 1200.0)


def test_scholar_candidates_units_invariance_and_missing_value_mask():
    p1, q1, macro, fx = _make_scholar_universe(scale=1.0)
    p2, q2, _, _ = _make_scholar_universe(scale=1e-3)

    # Raw features and final candidate scores are scale-invariant to monetary unit rescaling
    for name, fn in (
        ("scholar_cbop", lambda p, q: r3f.signal_scholar_cbop(p, q)),
        ("scholar_sue_usd", lambda p, q: r3f.signal_scholar_sue_usd(p, q, fx)),
        ("scholar_real_cbop_sue", lambda p, q: r3f.signal_scholar_real_cbop_sue(p, q, macro, fx)),
    ):
        s1 = fn(p1, q1)
        s2 = fn(p2, q2)
        assert s1.notna().all(), name
        np.testing.assert_allclose(s1.to_numpy(), s2.to_numpy(), rtol=1e-9, atol=1e-11, err_msg=name)

    # Masking value_sn_z to NaN must mask candidate score to NaN
    p_nan = p1.copy()
    p_nan.loc[0, "value_sn_z"] = np.nan
    assert np.isnan(r3f.signal_scholar_cbop(p_nan, q1).iloc[0])
    assert np.isnan(r3f.signal_scholar_sue_usd(p_nan, q1, fx).iloc[0])
    assert np.isnan(r3f.signal_scholar_real_cbop_sue(p_nan, q1, macro, fx).iloc[0])


def test_scholar_candidates_zero_lookahead_and_kap_lag():
    panel, q_base, macro_base, fx_base = _make_scholar_universe()
    cutoff = pd.Timestamp("2019-12-31")
    pre = panel["date"] <= cutoff

    # Corrupt all quarterly rows available after cutoff, FX after cutoff, and macro CPI after cutoff
    q_fut = q_base.copy()
    m_q = q_fut["available_at"] > cutoff
    assert m_q.any()
    for c in ("total_assets", "cash", "ttm_op_profit", "q_ni_parent", "q_net_income"):
        q_fut.loc[m_q, c] = q_fut.loc[m_q, c] * 500.0

    fx_fut = fx_base.copy()
    fx_fut.loc[fx_fut.index > cutoff, "usdtry"] = 999.0

    macro_fut = macro_base.copy()
    macro_fut.loc[macro_fut.index > cutoff, "cpi_mom"] = 85.0

    # Also corrupt future cross-section value_sn_z
    p_fut = panel.copy()
    p_fut.loc[~pre, "value_sn_z"] = 100.0

    for name, s_base, s_fut in (
        ("scholar_cbop", r3f.signal_scholar_cbop(panel, q_base), r3f.signal_scholar_cbop(p_fut, q_fut)),
        (
            "scholar_sue_usd",
            r3f.signal_scholar_sue_usd(panel, q_base, fx_base),
            r3f.signal_scholar_sue_usd(p_fut, q_fut, fx_fut),
        ),
        (
            "scholar_real_cbop_sue",
            r3f.signal_scholar_real_cbop_sue(panel, q_base, macro_base, fx_base),
            r3f.signal_scholar_real_cbop_sue(p_fut, q_fut, macro_fut, fx_fut),
        ),
    ):
        np.testing.assert_allclose(
            s_base[pre].to_numpy(), s_fut[pre].to_numpy(), rtol=0.0, atol=0.0, equal_nan=True, err_msg=name
        )

    # KAP availability lag test: 2020Q1 filed 2020-05-15 must not appear on 2020-04-30, must appear on 2020-05-31
    p_kap = pd.DataFrame(
        {
            "date": [pd.Timestamp("2020-04-30"), pd.Timestamp("2020-05-31"), pd.Timestamp("2020-06-30")],
            "ticker": ["TK00", "TK00", "TK00"],
        }
    )
    kap_dates = pd.DataFrame(
        [
            {"ticker": "TK00", "period": "2019Q4", "kap_available_at": pd.Timestamp("2020-03-05")},
            {"ticker": "TK00", "period": "2020Q1", "kap_available_at": pd.Timestamp("2020-05-15")},
        ]
    )
    c_lag75 = r3f.cbop_feature(p_kap, q_base, kap_dates=None)
    c_kap = r3f.cbop_feature(p_kap, q_base, kap_dates=kap_dates)
    # Under lag75: 2020-04-30 and 2020-05-31 both use 2019Q4; 2020-06-30 switches to 2020Q1
    assert c_lag75.iloc[0] == pytest.approx(c_lag75.iloc[1])
    assert c_lag75.iloc[2] != pytest.approx(c_lag75.iloc[1])
    # Under KAP: 2020-04-30 uses 2019Q4; 2020-05-31 already switches to 2020Q1 (matching 2020-06-30)
    assert c_kap.iloc[0] == pytest.approx(c_lag75.iloc[0])
    assert c_kap.iloc[1] == pytest.approx(c_lag75.iloc[2])
    assert c_kap.iloc[2] == pytest.approx(c_lag75.iloc[2])


def test_scholar_registry_harness_interface():
    panel, q, macro, fx = _make_scholar_universe()
    ctx = {"quarterly": q, "macro": macro, "fx": fx, "panel_tag": "lag75"}
    for name in ("scholar_cbop", "scholar_sue_usd", "scholar_real_cbop_sue"):
        assert name in r3f.CANDIDATE_BUILDERS
        assert name in r3f.CANDIDATE_META
        s = r3f.CANDIDATE_BUILDERS[name](panel, panel, ctx)
        assert isinstance(s, pd.Series)
        assert s.index.equals(panel.index)
        assert s.notna().all()


def test_real_pit_discovery_scholar_candidates_coverage():
    """Discovery-only (2013-2020) coverage verification for all 3 Scholar candidates on FP PIT panel."""
    fp = Path("/home/eren/bist_project/data/research/fp")
    res_dir = Path("/home/eren/bist_project/data/research")
    if not (fp / "factors_monthly.parquet").exists():
        pytest.skip("Read-only FP PIT panel not present")

    from backtest_factor_model import FACTORS, add_composites
    from core import factor_backtest as fb

    raw = pd.read_parquet(fp / "factors_monthly.parquet")
    raw["date"] = r3f.normalize_month_end(raw["date"])
    raw = raw[(raw["date"] >= r3f.DISCOVERY_START) & (raw["date"] <= r3f.DISCOVERY_END)].copy()
    prep = add_composites(fb.prepare(raw, FACTORS, liq_drop_pct=0.3))
    prep = prep[prep["value_sn_z"].notna()].copy()

    q = pd.read_parquet(fp / "quarterly.parquet")
    macro = pd.read_parquet(res_dir / "macro_monthly.parquet")
    fx = pd.read_parquet(res_dir / "fx.parquet")
    ctx = {"quarterly": q, "macro": macro, "fx": fx, "panel_tag": "lag75"}

    # Raw leg coverage matches scholar specs (~98% for cbop/cbop_real, ~84% for sue_ni_usd)
    cbop_raw = r3f.cbop_feature(prep, q)
    cbop_real_raw = r3f.cbop_feature(prep, q, cpi=r3f.cpi_index_from_macro(macro))
    sue_usd_raw = r3f.sue_usd_feature(prep, q, fx)
    assert cbop_raw.notna().mean() > 0.95
    assert cbop_real_raw.notna().mean() > 0.95
    assert sue_usd_raw.notna().mean() > 0.80

    for name in ("scholar_cbop", "scholar_sue_usd", "scholar_real_cbop_sue"):
        s = r3f.CANDIDATE_BUILDERS[name](raw, prep, ctx)
        assert s.notna().mean() == pytest.approx(1.0)
        assert not np.isinf(s.to_numpy()).any()
