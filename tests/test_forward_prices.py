"""Ileriye donuk kayit fiyat deposu ve eksik fiyatli hisselerin degerlendirmesi."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from core import forward_prices as fp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import forward_record_report as rep  # noqa: E402


def _bars(dates, adj, close=10.0):
    return [{"date": d, "open": close, "close": close, "adj_close": a, "volume": 100.0} for d, a in zip(dates, adj)]


def test_store_keeps_history_and_rescales_after_adjustment(tmp_path):
    d1 = ["2026-11-02", "2026-11-03", "2026-11-04"]
    assert fp.write({"A": _bars(d1, [10, 11, 12])}, {"A"}, "2026-07-01", root=tmp_path, force=True) == 1
    # bedelsiz sonrasi saglayici duzeltilmis seriyi yarilar; yalniz son iki gunu dondurur
    d2 = ["2026-11-04", "2026-11-05"]
    fp.write({"A": _bars(d2, [6, 6.5])}, {"A"}, "2026-07-01", root=tmp_path, force=True)
    df = fp.load("A", tmp_path)
    assert list(df["date"].dt.strftime("%Y-%m-%d")) == d1 + ["2026-11-05"]
    assert np.allclose(df["adj_close"], [5, 5.5, 6, 6.5])  # eski satirlar yeni baza olceklendi
    # saglayici artik dondurmuyor (delist): dosya son haliyle kalir
    assert fp.write({}, {"A"}, "2026-07-01", root=tmp_path, force=True) == 0
    assert len(fp.load("A", tmp_path)) == 4


def test_store_writes_only_in_production_live(tmp_path, monkeypatch):
    monkeypatch.setenv("BIST_DATA_MODE", "mock")
    assert fp.write({"A": _bars(["2026-11-02"], [10])}, {"A"}, "2026-07-01", root=tmp_path) == 0
    assert not (tmp_path / "A.csv").exists()


DAYS = pd.bdate_range("2026-08-03", "2027-01-29")


def _frame(px):
    return pd.DataFrame({"Open": px, "Close": px, "adv": 1e12, "sigma": 0.0})


def test_missing_history_never_silently_dropped():
    """Saglayici yok -> depo; ikisi de yok -> tutulan hisse muhafazakar -%100, evren hissesi raporlanir."""
    flat = _frame(pd.Series(1.0, index=DAYS))
    series = [{"rebalance_date": "2026-11-02", "rule_version": "v", "holdings": ["P", "S", "GONE"],
               "universe": ["P", "S", "GONE", "U"]},
              {"rebalance_date": "2026-12-01", "rule_version": "v", "holdings": ["P", "S", "GONE"],
               "universe": ["P", "S", "GONE", "U"]}]
    frames, src = rep.price_frames(series, DAYS,
                                   live=lambda tk, start: flat if tk == "P" else None,
                                   stored=lambda tk: flat if tk == "S" else None)
    assert src == {"provider": ["P"], "store": ["S"], "conservative_loss": ["GONE"], "universe_missing": ["U"]}
    zero = rep.pb.Costs(commission_bps=0, spread_bps=(0, 0, 0), impact_k=0, impact_cap=0)
    p = rep.evaluate(series, frames, pd.Series(1.0, index=DAYS), costs=zero)
    # GONE (1/3) kayboldu, P ve S duz: Kasim donemi ~ -1/3
    assert np.isclose(p.iloc[0]["port"], -1 / 3, atol=1e-6)


def test_provider_must_cover_first_decision():
    late = _frame(pd.Series(1.0, index=DAYS[DAYS >= "2026-12-15"]))
    full = _frame(pd.Series(1.0, index=DAYS))
    series = [{"rebalance_date": "2026-11-02", "rule_version": "v", "holdings": ["A"], "universe": ["A"]}]
    _, src = rep.price_frames(series, DAYS, live=lambda tk, start: late, stored=lambda tk: full)
    assert src["store"] == ["A"]  # saglayici gecmisi kesik: depo kullanilir


def test_ew_benchmark_invalid_when_universe_coverage_low():
    """Evrenin %95'inden azinin getirisi olculebiliyorsa EW karsilastirmasi o donem gecersiz (NaN)."""
    flat = _frame(pd.Series(1.0, index=DAYS))
    uni = [f"U{i}" for i in range(10)]
    series = [{"rebalance_date": "2026-11-02", "rule_version": "v", "holdings": ["U0"], "universe": uni},
              {"rebalance_date": "2026-12-01", "rule_version": "v", "holdings": ["U0"], "universe": uni}]
    full = {tk: flat for tk in uni}
    p = rep.evaluate(series, full, pd.Series(1.0, index=DAYS))
    assert p["bench"].notna().all() and p["bench_coverage"].min() == 1.0
    part = {tk: flat for tk in uni[:9]}  # %90 kapsama
    q = rep.evaluate(series, part, pd.Series(1.0, index=DAYS))
    assert q["bench"].isna().all() and q["active"].isna().all()
    s = rep.summarize(q)
    assert s["ew_universe_invalid_periods"] == len(q) and s["ew_universe_min_coverage_pct"] == 90.0
    assert s["cum_ew_universe_pct"] is None


def test_ew_benchmark_rejects_stale_ffill_gap_and_measures_price_age():
    """Onceki ayda fiyati bulunan fakat sonraki ay boyunca fiyati eksik kalan hisse,
    ffill() ile sifir getirili gozlem gibi kapsama hesabina girmemeli; fiyat yasi olculmeli."""
    flat = _frame(pd.Series(1.0, index=DAYS))
    uni = [f"U{i}" for i in range(10)]
    # U9 Kasim'da islem goruyor, Aralik boyunca fiyati NaN (bosluk)
    stale_px = pd.Series(1.0, index=DAYS).where(DAYS <= "2026-12-01")
    frames = {tk: flat for tk in uni[:9]}
    frames["U9"] = _frame(stale_px)
    series = [{"rebalance_date": "2026-11-02", "rule_version": "v", "holdings": ["U0"], "universe": uni},
              {"rebalance_date": "2026-12-01", "rule_version": "v", "holdings": ["U0"], "universe": uni},
              {"rebalance_date": "2027-01-04", "rule_version": "v", "holdings": ["U0"], "universe": uni}]
    p = rep.evaluate(series, frames, pd.Series(1.0, index=DAYS))
    # 1. donem (Kasim): U9'un baslangic ve bitis fiyati gozlemlenebilir -> %100 kapsama
    assert p.iloc[0]["bench_coverage"] == 1.0 and np.isfinite(p.iloc[0]["bench_net"])
    assert p.iloc[0]["bench_max_price_age"] == 0
    # 2. donem (Aralik): U9'un donem sonu fiyati eksik -> kapsama %90 (< %95), EW gecersiz
    assert np.isclose(p.iloc[1]["bench_coverage"], 0.9)
    assert np.isnan(p.iloc[1]["bench_net"]) and np.isnan(p.iloc[1]["bench_gross"])
    assert p.iloc[1]["bench_max_price_age"] >= 20  # 1 ay boyunca islem gormedi
    s = rep.summarize(p)
    assert s["ew_universe_invalid_periods"] == 1
    assert s["ew_universe_min_coverage_pct"] == 90.0
    assert s["ew_universe_max_price_age_days"] == int(p.iloc[1]["bench_max_price_age"])
    assert s["cum_ew_universe_net_pct"] is None and s["cum_ew_universe_gross_pct"] is None


def test_100_stock_missing_only_on_fill_day_not_redistributed_and_coverage_checked():
    """100 hisselik hedef portfoyde 1 hissenin yalnizca islem gununde fiyati eksik, donem basi ve
    sonunda fiyati mevcut: agirligi diger 99 hisseye dagitilmaz (nakitte kalir) ve kapsama %99
    olarak olculur; >%5 hisse islem gununde eksikse donem gecersiz sayilir."""
    uni = [f"U{i}" for i in range(100)]
    d0 = pd.Timestamp("2026-11-02")
    fill_d = DAYS[DAYS.get_loc(d0) + 1]  # 2026-11-03 (islem gunu)
    base_px = pd.Series(np.where(DAYS <= fill_d, 100.0, 110.0), index=DAYS)  # islem gunu sonrasi +%10
    missing_fill_px = base_px.copy()
    missing_fill_px.loc[fill_d] = np.nan  # yalnizca islem gununde NaN, donem sonunda 110.0
    frames = {tk: _frame(base_px) for tk in uni[:99]}
    frames["U99"] = _frame(missing_fill_px)
    series = [{"rebalance_date": "2026-11-02", "rule_version": "v", "holdings": uni, "universe": uni},
              {"rebalance_date": "2026-12-01", "rule_version": "v", "holdings": uni, "universe": uni}]
    zero = rep.pb.Costs(commission_bps=0, spread_bps=(0, 0, 0), impact_k=0, impact_cap=0)
    p = rep.evaluate(series, frames, pd.Series(100.0, index=DAYS), costs=zero)
    # U99'un %1 agirligi 99 hisseye dagitilmadi (nakitte %0 aldi): port ve bench_net = 0.99 * 0.10 = 0.099
    assert np.isclose(p.iloc[0]["port"], 0.99 * 0.10, atol=1e-12)
    assert np.isclose(p.iloc[0]["bench_net"], 0.99 * 0.10, atol=1e-12)
    # Kapsama: islem gununde 1 hisse eksik oldugu icin 99/100 = 0.99 (>= 0.95 -> donem gecerli)
    assert np.isclose(p.iloc[0]["bench_coverage"], 0.99)
    assert np.isfinite(p.iloc[0]["bench_net"]) and np.isfinite(p.iloc[0]["bench_gross"])

    # 6 hissenin yalnizca islem gununde fiyati eksikse (uc noktalar mevcut olsa bile) kapsama 94/100 < 0.95 -> gecersiz
    for tk in uni[94:]:
        frames[tk] = _frame(missing_fill_px)
    q = rep.evaluate(series, frames, pd.Series(100.0, index=DAYS), costs=zero)
    assert np.isclose(q.iloc[0]["bench_coverage"], 0.94)
    assert np.isnan(q.iloc[0]["bench_net"]) and np.isnan(q.iloc[0]["bench_gross"])


