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


def test_live_value_inputs_apply_kap_availability_rule(monkeypatch):
    """Skor yalnizca karar gunu KULLANILABILIR ceyregi kullanir: KAP ilk yayini (18:00 sonrasi
    ertesi gun); KAP eslesmezse panelin 75/100 gun varsayimi; yayin tarihi uydurulmaz."""
    from datetime import datetime

    from core import live_data as ld
    bs, inc, _ = _ytd_statements(5)
    monkeypatch.setattr(ld, "_quarterly_statements_cached", lambda tk: (bs, inc))
    monkeypatch.setattr(ld, "_cpi_index_cached", lambda: None)
    pubs = {"2026-06-30": datetime(2026, 8, 10, 18, 45), "2026-03-31": datetime(2026, 5, 8, 10, 0)}
    monkeypatch.setattr(ld, "live_financial_report_published_dt",
                        lambda tk, pe: pubs.get(pe) if tk == "HAS" else None)
    before = ld.live_value_inputs("HAS", 400.0, "2026-08-10")  # Q2 18:45'te yayinlandi -> 08-11
    assert before["stmt_period"] == "2026Q1" and before["kap_published_at"] == "2026-05-08T10:00"
    assert before["available_source"] == "kap" and before["as_of"] == "2026-08-10"
    after = ld.live_value_inputs("HAS", 400.0, "2026-08-11")
    assert after["stmt_period"] == "2026Q2" and after["kap_available_at"] == "2026-08-11"
    assert after["ep"] != pytest.approx(before["ep"])
    # KAP eslesmesi yok: varsayilan gecikme (Q2 -> 09-13), tarih uydurulmaz
    none = ld.live_value_inputs("NONE", 400.0, "2026-09-01")
    assert none["stmt_period"] == "2026Q1" and none["available_source"] == "assumed"
    assert none["available_at"] == "2026-06-14" and none["kap_published_at"] is None
    assert ld.live_value_inputs("NONE", 400.0, "2026-09-13")["stmt_period"] == "2026Q2"


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


def test_live_value_inputs_use_constant_unit_ttm(monkeypatch):
    """Canli value_inputs, panelle ayni C1 tanimini (TUFE ile sabit birim TTM) kullanir;
    TUFE yoksa C0'a duser ve bunu ttm_unit ile kaydeder."""
    from core import live_data as ld
    from core import pit_panel
    bs, inc, _ = _ytd_statements(9)
    months = pd.period_range("2024-01", "2026-12", freq="M")
    cpi = pd.Series(1.02 ** np.arange(len(months)), index=months)
    monkeypatch.setattr(ld, "_quarterly_statements_cached", lambda tk: (bs, inc))
    monkeypatch.setattr(ld, "live_financial_report_published_dt", lambda tk, pe: None)
    monkeypatch.setattr(ld, "_cpi_index_cached", lambda: cpi)
    vi = ld.live_value_inputs("X", 400.0)
    ref = pit_panel.latest_value_ratios("X", bs, inc, 400.0, cpi=cpi)
    c0 = pit_panel.latest_value_ratios("X", bs, inc, 400.0)
    assert vi["ttm_unit"] == "C1_constant_unit"
    assert vi["sp"] == pytest.approx(ref["sp"]) and vi["sp"] != pytest.approx(c0["sp"])
    monkeypatch.setattr(ld, "_cpi_index_cached", lambda: None)
    fb_ = ld.live_value_inputs("X", 400.0)
    assert fb_["ttm_unit"] == "C0_fallback_no_cpi" and fb_["sp"] == pytest.approx(c0["sp"])


def test_live_ttm_handles_vendor_reexpressed_prior_year():
    """Is Yatirim, ertesi yil raporu gelen donemi bir yil sonraki birimle yeniden ifade ediyor.
    Reel ceyrek akisi sabit R: dogru TTM = 4 R x CPI(P). Ardisik YTD farki (quarterly_table)
    bunu bozuyor; vendor_consistent_ttm bozmuyor (docs/research/vendor_vs_kap_audit.md)."""
    from core import pit_panel
    months = pd.period_range("2023-01", "2026-12", freq="M")
    cpi = pd.Series(1.03 ** np.arange(len(months)), index=months)
    c = lambda p: cpi[pit_panel.period_end(p).to_period("M")]  # noqa: E731
    R, latest = 10.0, "2026Q2"
    periods = ["2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2"]
    inc_vals = {}
    for p in periods:
        v = int(p[-1]) * R * c(p)  # ilk yayin: kendi donem sonu biriminde
        nxt = f"{int(p[:4]) + 1}{p[4:]}"
        if nxt in periods:  # ertesi yil raporu var: saglayici o kolonla degistirir
            v *= c(nxt) / c(p)
        inc_vals[p] = v
    inc = pd.DataFrame({p: [v, v / 2, v / 4] for p, v in inc_vals.items()},
                       index=["Satış Gelirleri", "FAALİYET KARI (ZARARI)", "Ana Ortaklık Payları"])
    bs = pd.DataFrame({p: [1000.0, 500.0, 100.0, 50.0, 80.0] for p in periods},
                      index=["TOPLAM VARLIKLAR", "Ana Ortaklığa Ait Özkaynaklar", "Ödenmiş Sermaye",
                             "Nakit ve Nakit Benzerleri", "Finansal Borçlar"])
    vi = pit_panel.latest_value_ratios("X", bs, inc, 400.0, cpi=cpi)
    assert vi["stmt_period"] == latest and vi["ttm_method"] == "vendor_consistent_ytd"
    assert vi["inputs"]["ttm_revenue"] == pytest.approx(4 * R * c(latest))
    q = pit_panel.quarterly_table(pit_panel.statements_long("X", bs, inc), cpi=cpi).set_index("period")
    assert q.loc[latest, "ttm_revenue"] < 0.8 * 4 * R * c(latest)  # eski yol: birim karisimi
