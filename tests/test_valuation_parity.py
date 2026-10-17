"""Canli valuation_z == test edilen value_sn_z (scripts/backtest_factor_model.py).

Faz 2 on-kaydi bu paneli test etti; canli skor ayni sayiyi uretmeli. Panel tarafi
factor_backtest.prepare + value ortalamasi + sector_neutralize ile birebir kurulur.
"""
from __future__ import annotations

import random

import numpy as np
import pandas as pd
import pytest

from core import factor_backtest as fb
from core.ranking import compute_valuation_scores


def _universe(seed=7, n=80):
    rng = random.Random(seed)
    sectors = ["Gida", "Tekstil", "Kimya", "Metal", "Enerji", "Insaat", "Teknoloji"]
    out = []
    for i in range(n):
        mcap = 10 ** rng.uniform(8, 11)
        c = {"ticker": f"T{i:02d}", "ratio_profile": rng.choice(["industrial", "industrial", "holding"]),
             "reporting_basis": "nominal",
             # Teknoloji'yi kucuk birak: sector < 5 -> tum kesite gore notrleme
             "sector": "Teknoloji" if i < 3 else rng.choice(sectors[:-1]),
             "supersector": "X", "market_cap": mcap, "current_price": 10.0,
             "pe": rng.lognormvariate(2.3, 0.8), "pb": rng.lognormvariate(0.3, 0.9),
             "revenue_ttm": mcap * rng.lognormvariate(-0.3, 1.0),
             "op_profit_ttm": mcap * rng.gauss(0.08, 0.1),
             "net_debt": mcap * rng.gauss(0.2, 0.5) if rng.random() > 0.1 else None,
             "tl_vol_med60": 10 ** rng.uniform(5, 9)}
        if rng.random() < 0.1:   # zarar eden: F/K yok, negatif EPS
            c["pe"], c["eps_ttm"] = None, -rng.uniform(0.1, 3)
        if rng.random() < 0.1:
            c["pb"] = None
        if rng.random() < 0.05:
            c["revenue_ttm"] = None
        out.append(c)
    out[5]["pe"] = 0.3      # asiri ucuz: eski kod emsal max'ina kirpardi
    return out


def _panel_value_sn(cands):
    from core.ranking import book_to_market, earnings_yield, ebit_yield, sales_yield
    rows = [{"date": pd.Timestamp("2026-09-30"), "ticker": c["ticker"], "sector": c["sector"],
             "tlvol60": c["tl_vol_med60"],
             "ep": (earnings_yield(c) or np.nan) / 100, "bm": book_to_market(c) or np.nan,
             "sp": sales_yield(c) or np.nan, "ey": ebit_yield(c) or np.nan} for c in cands]
    df = fb.prepare(pd.DataFrame(rows), ["bm", "ep", "sp", "ey"])
    df["value_z"] = df[[f + "_z" for f in ["bm", "ep", "sp", "ey"]]].mean(axis=1)
    df["value_sn_z"] = fb.sector_neutralize(df, "value_z")
    return df.set_index("ticker")["value_sn_z"]


@pytest.mark.parametrize("seed", [1, 7, 42])
def test_live_valuation_z_equals_panel_value_sn(seed):
    cands = _universe(seed)
    panel = _panel_value_sn(cands)
    live = {c["ticker"]: r["valuation_z"] for c, r in zip(cands, compute_valuation_scores(cands))}
    assert len(panel) > 40
    for tk, v in panel.items():
        if np.isnan(v):
            assert live[tk] is None
        else:
            assert live[tk] == pytest.approx(v, abs=1e-9), tk


def _ytd_statements(seed: int):
    """8 ceyreklik YTD gelir tablosu + bilanco (Is Yatirim sablonu satir adlariyla)."""
    rng = random.Random(seed)
    periods = ["2026Q2", "2026Q1", "2025Q4", "2025Q3", "2025Q2", "2025Q1", "2024Q4", "2024Q3"]
    q = {p: (rng.uniform(50, 150), rng.uniform(-5, 20), rng.uniform(-10, 15)) for p in periods}
    inc = {}
    for item, k in (("Satış Gelirleri", 0), ("FAALİYET KARI (ZARARI)", 1), ("Ana Ortaklık Payları", 2)):
        inc[item] = {p: sum(q[x][k] for x in periods if x[:4] == p[:4] and x[-1] <= p[-1]) for p in periods}
    bs = {"Ana Ortaklığa Ait Özkaynaklar": {p: rng.uniform(-20, 300) for p in periods},
          "Ödenmiş Sermaye": {p: 10.0 for p in periods},
          "Nakit ve Nakit Benzerleri": {p: rng.uniform(0, 50) for p in periods},
          "Finansal Borçlar": {p: rng.uniform(0, 80) for p in periods}}
    ttm = {k: sum(q[p][k] for p in periods[:4]) for k in range(3)}
    return pd.DataFrame(bs).T[periods], pd.DataFrame(inc).T[periods], ttm


def test_live_value_inputs_use_panel_ttm_definition():
    from core import pit_panel
    bs, inc, ttm = _ytd_statements(3)
    vi = pit_panel.latest_value_ratios("X", bs, inc, 400.0)
    assert vi["stmt_period"] == "2026Q2"
    assert vi["sp"] == pytest.approx(ttm[0] / 400.0)
    assert vi["ep"] == pytest.approx(ttm[2] / 400.0)
    eq, cash, debt = (bs.loc[k, "2026Q2"] for k in
                      ("Ana Ortaklığa Ait Özkaynaklar", "Nakit ve Nakit Benzerleri", "Finansal Borçlar"))
    assert vi["ey"] == pytest.approx(ttm[1] / (400.0 + debt - cash))
    assert (vi["bm"] == pytest.approx(eq / 400.0)) if eq > 0 else np.isnan(vi["bm"])
    assert vi["stmt_period_end"] == "2026-06-30"
    assert vi["inputs"]["ttm_revenue"] == pytest.approx(ttm[0]) and vi["inputs"]["market_cap"] == 400.0
    empty = pit_panel.latest_value_ratios("X", None, None, 400.0)
    assert all(np.isnan(empty[k]) for k in ("bm", "ep", "sp", "ey")) and empty["stmt_period"] is None


def test_live_value_inputs_record_kap_date_of_used_quarter(monkeypatch):
    """KAP tarihi kullanilan ceyregin donem sonuyla sorgulanir; 18:00 sonrasi yayin ertesi gun
    kullanilabilir; eslesme yoksa None (uydurulmaz)."""
    from datetime import datetime

    from core import live_data as ld
    bs, inc, _ = _ytd_statements(5)
    monkeypatch.setattr(ld, "_quarterly_statements_cached", lambda tk: (bs, inc))
    asked = []

    def fake_pub(tk, period_end):
        asked.append(period_end)
        return datetime(2026, 8, 10, 18, 45) if tk == "HAS" else None
    monkeypatch.setattr(ld, "live_financial_report_published_dt", fake_pub)
    vi = ld.live_value_inputs("HAS", 400.0)
    assert asked == ["2026-06-30"]
    assert vi["kap_published_at"] == "2026-08-10T18:45" and vi["kap_available_at"] == "2026-08-11"
    assert vi["source"] == "isyatirim_quarterly_ytd" and vi["observed_at"]
    none = ld.live_value_inputs("NONE", 400.0)
    assert none["kap_published_at"] is None and none["kap_available_at"] is None
    assert none["ep"] == vi["ep"]  # yayin tarihi oranlari degistirmez


@pytest.mark.parametrize("seed", [1, 7, 42])
def test_live_valuation_z_from_value_inputs_equals_panel(seed):
    """Canli value_inputs varsa saglayici F/K, PD/DD ve yillik kalemler YOK sayilir;
    skor panelin ayni oranlardan kurdugu value_sn_z'ye esittir."""
    cands = _universe(seed)
    rng = random.Random(seed + 100)
    rows = []
    for c in cands:
        vi = {"bm": rng.lognormvariate(-0.5, 0.8), "ep": rng.gauss(0.08, 0.1),
              "sp": rng.lognormvariate(-0.3, 1.0), "ey": rng.gauss(0.08, 0.1) if rng.random() > 0.1 else None,
              "stmt_period": "2026Q2"}
        if rng.random() < 0.1:
            vi["bm"] = None
        c["value_inputs"] = vi
        rows.append({"date": pd.Timestamp("2026-09-30"), "ticker": c["ticker"], "sector": c["sector"],
                     "tlvol60": c["tl_vol_med60"], **{k: (np.nan if vi[k] is None else vi[k])
                                                       for k in ("bm", "ep", "sp", "ey")}})
    df = fb.prepare(pd.DataFrame(rows), ["bm", "ep", "sp", "ey"])
    df["value_z"] = df[[f + "_z" for f in ["bm", "ep", "sp", "ey"]]].mean(axis=1)
    panel = fb.sector_neutralize(df, "value_z").set_axis(df["ticker"])
    live = {c["ticker"]: r["valuation_z"] for c, r in zip(cands, compute_valuation_scores(cands))}
    for tk, v in panel.items():
        if np.isnan(v):
            assert live[tk] is None
        else:
            assert live[tk] == pytest.approx(v, abs=1e-9), tk


def test_ias29_constant_unit_ttm():
    """TMS 29: her rapor YTD'yi kendi donem sonu biriminde verir. Reel ceyrek akisi sabit R ise
    C1'de ceyrek = R x CPI(donem sonu), TTM = 4 R x CPI(donem sonu); C0 bunu bozar."""
    from core import pit_panel
    months = pd.period_range("2023-01", "2025-12", freq="M")
    cpi = pd.Series(1.03 ** np.arange(len(months)), index=months)
    periods = [f"{y}Q{q}" for y in (2024, 2025) for q in (1, 2, 3, 4)]
    R, rows = 10.0, []
    for p in periods:
        c = cpi[pit_panel.period_end(p).to_period("M")]
        rows.append({"ticker": "X", "period": p, "item": "revenue", "value": int(p[-1]) * R * c})
    q1 = pit_panel.quarterly_table(pd.DataFrame(rows), cpi=cpi).set_index("period")
    q0 = pit_panel.quarterly_table(pd.DataFrame(rows)).set_index("period")
    for p in periods:
        c = cpi[pit_panel.period_end(p).to_period("M")]
        assert q1.loc[p, "q_revenue"] == pytest.approx(R * c)
    for p in periods[3:]:
        c = cpi[pit_panel.period_end(p).to_period("M")]
        assert q1.loc[p, "ttm_revenue"] == pytest.approx(4 * R * c)
    # C0: Q4 TTM = yillik YTD (dogru); yil asan Q1-Q3 TTM bozulur
    assert q0.loc["2025Q4", "ttm_revenue"] == pytest.approx(4 * R * cpi[pd.Period("2025-12", "M")])
    assert q0.loc["2025Q2", "ttm_revenue"] != pytest.approx(4 * R * cpi[pd.Period("2025-06", "M")])
    # TMS 29 oncesi satirlar degismez
    old = [{"ticker": "Y", "period": p, "item": "revenue", "value": v}
           for p, v in (("2022Q4", 40.0), ("2023Q1", 11.0), ("2023Q2", 23.0), ("2023Q3", 36.0))]
    a = pit_panel.quarterly_table(pd.DataFrame(old), cpi=cpi)
    b = pit_panel.quarterly_table(pd.DataFrame(old))
    pd.testing.assert_frame_equal(a, b)
