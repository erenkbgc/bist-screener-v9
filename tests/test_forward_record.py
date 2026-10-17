"""Ileriye donuk kayit: kural kilidi, yalnizca-ekleme kaydi ve degerlendirme."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from core import forward_record as fr
from core import rotation

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import forward_record_report as rep  # noqa: E402


def test_rotation_constants_match_locked_rule():
    # Kural parametresi degisirse config/live_rule.json ve surum da degismeli.
    p = fr.live_rule()["params"]
    assert p["top_pct"] == rotation.TOP_PCT
    assert p["liq_drop_pct"] == rotation.LIQ_DROP_PCT
    assert (p["liq_window_days"], p["liq_min_bars"]) == (rotation.LIQ_WINDOW, rotation.LIQ_MIN_BARS)


def test_append_only_after_start_and_once_per_date(tmp_path):
    path = tmp_path / "decisions.jsonl"
    assert not fr.append_decision("2026-10-01", ["A"], ["A", "B"], path=path, force=True)  # baslangic oncesi
    assert fr.append_decision("2026-11-02", ["B", "A"], ["C", "A", "B"], path=path, force=True)
    assert not fr.append_decision("2026-11-02", ["X"], ["X"], path=path, force=True)  # ayni tarih degismez
    recs = fr.load_decisions(path)
    assert len(recs) == 1 and recs[0]["holdings"] == ["A", "B"] and recs[0]["universe"] == ["A", "B", "C"]
    assert recs[0]["rule_version"] == fr.live_rule()["version"] and recs[0]["recorded_at"]


def test_no_write_outside_production_live(tmp_path, monkeypatch):
    monkeypatch.setenv("BIST_DATA_MODE", "live")
    path = tmp_path / "decisions.jsonl"
    # temp DB != uretim DB -> yazmaz
    from core import db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "x.db")
    assert not fr.append_decision("2026-11-02", ["A"], ["A"], path=path)
    assert not path.exists()


def test_monthly_rotation_does_not_touch_real_record(temp_db):
    before = fr.RECORD_PATH.read_text(encoding="utf-8") if fr.RECORD_PATH.exists() else None
    cands = [{"ticker": f"T{i}", "bucket": "long_term", "candidate_state": "WATCHLIST", "confidence": "high",
              "valuation_z": float(i), "tl_vol_med60": 1e9} for i in range(10)]
    rotation.monthly_rotation("2026-11-02", cands)
    after = fr.RECORD_PATH.read_text(encoding="utf-8") if fr.RECORD_PATH.exists() else None
    assert before == after


def test_series_split_on_version_change():
    ds = [{"rebalance_date": "2026-11-02", "rule_version": "v1"},
          {"rebalance_date": "2026-12-01", "rule_version": "v1"},
          {"rebalance_date": "2027-01-04", "rule_version": "v2"}]
    assert [len(s) for s in rep.series_by_version(ds)] == [2, 1]


DAYS = pd.bdate_range("2026-11-02", "2027-02-26")
ZERO = rep.pb.Costs(commission_bps=0, spread_bps=(0, 0, 0), impact_k=0, impact_cap=0)


def _frame(px):
    return pd.DataFrame({"Close": px, "Open": px, "adv": 1e12, "sigma": 0.0})


def _dec(day, holdings, version="v"):
    return {"rebalance_date": str(pd.Timestamp(day).date()), "rule_version": version,
            "holdings": holdings, "universe": ["A", "B"]}


def _pos(day):
    return DAYS.get_loc(pd.Timestamp(day))


def test_evaluate_prices_recorded_decisions():
    up = pd.Series(1.01 ** np.arange(len(DAYS)), index=DAYS)  # A her gun +%1
    flat = pd.Series(1.0, index=DAYS)
    series = [_dec("2026-11-02", ["A"]), _dec("2026-12-01", ["A"]), _dec("2027-01-04", ["A"])]
    p = rep.evaluate(series, {"A": _frame(up), "B": _frame(flat)}, flat, costs=ZERO)
    # Kasim, Aralik, Ocak tamamlandi (Subat capasi 2027-02-01 son donemi kapatir)
    assert list(p["date"].dt.strftime("%Y-%m")) == ["2026-11", "2026-12", "2027-01"]
    # ertesi gun kapanisinda alinir: ilk donemde bir gun eksik getiri
    n1 = _pos("2026-12-01") - _pos("2026-11-02")
    assert np.isclose(p.iloc[0]["port"], 1.01 ** (n1 - 1) - 1)
    assert np.isclose(p.iloc[0]["bench"], (1.01 ** n1 - 1) / 2)
    assert p.iloc[0]["xu"] == 0.0
    assert rep.summarize(p)["periods"] == 3


def test_missing_month_is_carried_as_its_own_period():
    """Aralikta karar yok: pozisyon islemsiz tasinir, Aralik ayri bir aylik donemdir
    (iki aylik getiri tek gozlem olarak yilliklastirilmaz)."""
    up = pd.Series(1.01 ** np.arange(len(DAYS)), index=DAYS)
    flat = pd.Series(1.0, index=DAYS)
    series = [_dec("2026-11-02", ["A"]), _dec("2027-01-04", ["B"])]
    p = rep.evaluate(series, {"A": _frame(up), "B": _frame(flat)}, flat, costs=ZERO)
    assert list(p["date"].dt.strftime("%Y-%m-%d")) == ["2026-11-02", "2026-12-01", "2027-01-04"]
    dec = p.set_index(p["date"].dt.strftime("%Y-%m"))
    assert list(dec["decision"]) == [True, False, True]
    assert dec.loc["2026-12", "turnover"] == 0 and dec.loc["2026-12", "cost"] == 0
    n_dec = _pos("2027-01-04") - _pos("2026-12-01")  # Aralik capasi: 2026-12-01 kapanisi
    assert np.isclose(dec.loc["2026-12", "port"], 1.01 ** n_dec - 1)  # A tasindi
    s = rep.summarize(p)
    assert s["periods"] == 3 and s["periods_carried_without_decision"] == 1


def test_schedule_closes_series_at_next_version():
    series = [_dec("2026-11-02", ["A"]), _dec("2026-12-01", ["A"])]
    sched = rep.schedule(series, pd.Timestamp("2027-03-31"), stop=pd.Timestamp("2027-02-01"))
    assert [t.strftime("%Y-%m-%d") for t, _ in sched] == ["2026-11-02", "2026-12-01", "2027-01-01", "2027-02-01"]
    assert [r is None for _, r in sched] == [False, False, True, True]


def test_no_decision_recorded_until_month_decided(tmp_path):
    path = tmp_path / "decisions.jsonl"
    assert fr.append_no_decision("2026-11-02", "run_error: X", path=path, force=True)
    assert not fr.append_no_decision("2026-11-02", "again", path=path, force=True)  # gunde tek kayit
    # ayni gunun basarili kosusu yine yazilir
    assert fr.append_decision("2026-11-02", ["A"], ["A", "B"], path=path, force=True)
    assert not fr.append_no_decision("2026-11-03", "empty_pool", path=path, force=True)  # ay karara baglandi
    recs = fr.load_decisions(path)
    assert [r["status"] for r in recs] == ["no_decision", "ok"]
    assert recs[0]["reason"] == "run_error: X" and recs[1]["schema"] == fr.SCHEMA
    assert fr.is_ok({"rebalance_date": "2026-11-02"})  # sema 1 kaydi


def test_failed_months_not_priced_but_counted():
    ds = [{"rebalance_date": "2026-11-02", "rule_version": "v1", "status": "ok"},
          {"rebalance_date": "2026-12-01", "rule_version": "v1", "status": "no_decision"},
          {"rebalance_date": "2027-01-04", "rule_version": "v1"}]
    assert [len(s) for s in rep.series_by_version(ds)] == [2]
    assert rep.missed_months(ds) == ["2026-12"]


def test_decision_details_records_ratios_and_dates():
    cands = [{"ticker": f"T{i}", "bucket": "long_term", "candidate_state": "WATCHLIST", "confidence": "high",
              "valuation_z": float(i), "tl_vol_med60": 1e9 + i, "market_cap": 1e9, "eps_ttm": 1.0,
              "shares_outstanding": 1e8, "valid_metric_count": 2, "current_price": 10.0,
              "price_date": f"2026-11-0{1 + i % 2}",
              "_raw_fundamentals": {"period_end": "2026-09-30", "pit_source": "observed_at_ingest"},
              "value_inputs": {"bm": 0.5, "ep": 0.1, "sp": 1.0, "ey": None, "stmt_period": "2026Q2",
                               "stmt_period_end": "2026-06-30", "kap_published_at": "2026-08-10T18:30",
                               "kap_available_at": "2026-08-11", "source": "isyatirim_quarterly_ytd",
                               "observed_at": "2026-11-01T15:31:00+00:00",
                               "inputs": {"market_cap": 1e9, "equity": 5e8}}} for i in range(10)]
    d = rotation.decision_details(cands, {"status": "OK", "issues": [], "config_hash": "h", "metrics": {}})
    assert d["counts"] == {"long_term_nonfinancial": 10, "eligible": 10, "pool": 7}  # alt %30 likidite
    top = d["ranking"][0]
    assert top["rank"] == 1 and top["ticker"] == "T9" and top["valid_metric_count"] == 2
    assert set(top) >= {"ep", "bm", "sp", "ey"} and top["statement_period"] == "2026Q2"
    # yayin tarihi KULLANILAN ceyregin (2026Q2), temel veri katmaninin sorguladigi donemin degil
    assert top["kap_published_at"] == "2026-08-10T18:30" and top["kap_available_at"] == "2026-08-11"
    assert top["fundamentals_period_end"] == "2026-09-30" and top["inputs"]["equity"] == 5e8
    assert d["price_date_max"] == "2026-11-02" and d["health"]["status"] == "OK"


def test_cash_earns_policy_rate_and_delist_haircut():
    rf = rep.pb.policy_rf_daily(pd.Series([36.0], index=pd.PeriodIndex(["2026-11"], freq="M")), DAYS)
    assert np.isclose((1 + rf.iloc[:60]).prod() ** (252 / 60), 1.36)  # seri bitince son faiz surer
    gone = pd.Series(100.0, index=DAYS).where(np.arange(len(DAYS)) < 5)  # A 5. gunden sonra islem gormez
    frames = {"A": _frame(gone), "B": _frame(pd.Series(100.0, index=DAYS))}
    series = [_dec("2026-11-02", ["A"]), _dec("2027-01-04", ["B"])]
    flat = pd.Series(100.0, index=DAYS)
    base = rep.evaluate(series, frames, flat, rf, costs=ZERO)
    cut = rep.evaluate(series, frames, flat, rf, costs=ZERO, haircut=0.5)
    assert base.attrs["delist_events"] == 1 and rep.summarize(base)["delist_events"] == 1
    # Kasim+Aralik (tasima) boyunca: once A, delist sonrasi nakit faiz kazanir
    two = (1 + base.iloc[0]["port"]) * (1 + base.iloc[1]["port"])
    two_cut = (1 + cut.iloc[0]["port"]) * (1 + cut.iloc[1]["port"])
    assert two > 1
    assert np.isclose(two_cut, two / 2, rtol=0.05)


def test_ew_net_and_gross_benchmarks_and_calendar_hac():
    """EW net ayni maliyet modeli ve simulatorle calisir (birincil); EW gross maliyetsizdir
    (tamamlayici). Gecersiz aylar cikarildiginda HAC takvim araligini korur ve eksik ay /
    gozlem araligi raporlanir."""
    days = pd.bdate_range("2026-10-01", "2028-04-28")
    up = pd.Series(1.002 ** np.arange(len(days)), index=days)
    flat = pd.Series(1.0, index=days)
    uni = [f"U{i}" for i in range(20)]
    # U19 yalnizca 2027-04 doneminde islem gormuyor -> o ay kapsama %95'in altina (19/20 değil, U18+U19 = 18/20 = %90) duser
    gapped = flat.copy()
    gapped.loc[(days >= "2027-04-05") & (days <= "2027-05-05")] = np.nan
    frames = {tk: _frame(up if tk == "U0" else flat) for tk in uni}
    frames["U18"] = _frame(gapped)
    frames["U19"] = _frame(gapped)
    months = pd.date_range("2026-11-01", "2028-02-01", freq="MS")
    series = [{"rebalance_date": str(days[days.searchsorted(m)].date()),
               "rule_version": "v", "holdings": ["U0"], "universe": uni} for m in months]
    costs = rep.pb.Costs(commission_bps=10.0, spread_bps=(5.0, 15.0, 30.0), impact_k=0.0, impact_cap=0.10)
    p = rep.evaluate(series, frames, flat, costs=costs)
    # Ilk donem islem maliyeti nedeniyle EW net < EW gross
    assert p.iloc[0]["bench_net_cost"] > 0
    assert p.iloc[0]["bench_net"] < p.iloc[0]["bench_gross"]
    s = rep.summarize(p)
    # 2027-05-03 sinirinda fiyat NaN oldugu icin hem 2027-04 (bitis) hem 2027-05 (baslangic) donemi gecersiz
    assert s["ew_universe_invalid_periods"] == 2
    assert s["ew_universe_net_cost_total_pct"] > 0
    # 17 donemin 2'si gecersiz -> 15 gecerli ay, 2 eksik ay, aralik 2026-11..2028-03
    assert s["active_univ_net_periods"] == 15 and s["active_univ_net_missing_periods"] == 2
    assert s["active_univ_net_span"] == ["2026-11", "2028-03"]
    assert s["active_univ_ann_pct"] == s["active_univ_net_ann_pct"]
    assert "active_univ_gross_ann_pct" in s and "active_univ_gross_t" in s

