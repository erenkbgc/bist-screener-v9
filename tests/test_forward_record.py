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


def test_evaluate_prices_recorded_decisions():
    days = pd.bdate_range("2026-11-02", periods=50)
    up = pd.Series(100 * 1.01 ** np.arange(50), index=days)  # A her gun +%1
    flat = pd.Series(100.0, index=days)

    def frame(px):
        return pd.DataFrame({"Close": px, "Open": px, "adv": 1e12, "sigma": 0.0})

    series = [{"rebalance_date": str(days[0].date()), "rule_version": "v", "holdings": ["A"], "universe": ["A", "B"]},
              {"rebalance_date": str(days[20].date()), "rule_version": "v", "holdings": ["A"], "universe": ["A", "B"]}]
    zero = rep.pb.Costs(commission_bps=0, spread_bps=(0, 0, 0), impact_k=0, impact_cap=0)
    p = rep.evaluate(series, {"A": frame(up), "B": frame(flat)}, flat * 1.0, costs=zero)
    assert len(p) == 1
    # ertesi gun kapanisinda alinir: 20 gunluk pencerede 19 gun getiri
    assert np.isclose(p.iloc[0]["port"], 1.01 ** 19 - 1)
    assert np.isclose(p.iloc[0]["bench"], (1.01 ** 20 - 1) / 2)
    assert p.iloc[0]["xu"] == 0.0
    assert rep.summarize(p)["periods"] == 1


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
              "_raw_fundamentals": {"published_at": "2026-08-10", "pit_source": "kap_financial_report",
                                    "_raw": {"_statement_period": "2026/6"}}} for i in range(10)]
    d = rotation.decision_details(cands, {"status": "OK", "issues": [], "config_hash": "h", "metrics": {}})
    assert d["counts"] == {"long_term_nonfinancial": 10, "eligible": 10, "pool": 7}  # alt %30 likidite
    top = d["ranking"][0]
    assert top["rank"] == 1 and top["ticker"] == "T9" and top["valid_metric_count"] == 2
    assert set(top) >= {"ep", "bm", "sp", "ey"} and top["statement_period"] == "2026/6"
    assert d["price_date_max"] == "2026-11-02" and d["health"]["status"] == "OK"


def test_cash_earns_policy_rate_and_delist_haircut():
    days = pd.bdate_range("2026-11-02", periods=60)
    rf = rep.pb.policy_rf_daily(pd.Series([36.0], index=pd.PeriodIndex(["2026-11"], freq="M")), days)
    assert np.isclose((1 + rf).prod() ** (252 / 60), 1.36)  # seri bitince son faiz surer
    gone = pd.Series(100.0, index=days).where(np.arange(60) < 10)  # A 10. gunden sonra islem gormez

    def frame(px):
        return pd.DataFrame({"Close": px, "Open": px, "adv": 1e12, "sigma": 0.0})

    series = [{"rebalance_date": str(days[0].date()), "rule_version": "v", "holdings": ["A"], "universe": ["A", "B"]},
              {"rebalance_date": str(days[50].date()), "rule_version": "v", "holdings": ["B"], "universe": ["A", "B"]}]
    zero = rep.pb.Costs(commission_bps=0, spread_bps=(0, 0, 0), impact_k=0, impact_cap=0)
    frames = {"A": frame(gone), "B": frame(pd.Series(100.0, index=days))}
    base = rep.evaluate(series, frames, pd.Series(100.0, index=days), rf, costs=zero)
    cut = rep.evaluate(series, frames, pd.Series(100.0, index=days), rf, costs=zero, haircut=0.5)
    assert base.attrs["delist_events"] == 1 and rep.summarize(base)["delist_events"] == 1
    assert base.iloc[0]["port"] > 0  # delist sonrasi nakit faiz kazanir
    assert np.isclose(1 + cut.iloc[0]["port"], (1 + base.iloc[0]["port"]) / 2, rtol=0.05)
