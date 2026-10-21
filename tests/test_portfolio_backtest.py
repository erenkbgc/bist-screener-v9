"""core/portfolio_backtest: gunluk defter, ertesi gun islem, maliyet ve delist mekanigi."""
from __future__ import annotations

import numpy as np
import pandas as pd

from core import portfolio_backtest as pb

ZERO = pb.Costs(commission_bps=0, spread_bps=(0, 0, 0), impact_k=0, impact_cap=0)


def _market(prices: dict[str, list[float]], days: pd.DatetimeIndex, adv: float = 1e9, rf: float = 0.0):
    close = pd.DataFrame(prices, index=days, dtype=float)
    return pb.Market(close=close, open=close.copy(), adv=pd.DataFrame(adv, index=days, columns=close.columns),
                     sigma=pd.DataFrame(0.02, index=days, columns=close.columns),
                     rf_daily=pd.Series(rf, index=days))


def _setup(n_days=60):
    days = pd.bdate_range("2020-01-01", periods=n_days)
    months = [days[9], days[29], days[49]]
    d0_of = {t: t for t in months}
    return days, months, d0_of


def test_next_day_fill_misses_jump_on_fill_day():
    days, months, d0_of = _setup()
    px = [100.0] * 10 + [150.0] * 50  # d0'dan sonraki ilk gun (islem gunu) %50 sicrama
    mkt = _market({"A": px}, days)
    out = pb.simulate({t: ["A"] for t in months}, months, d0_of, mkt, {}, {t: 1e6 for t in months}, costs=ZERO)
    # Kapanista alindigi icin sicrama kacirilir; ilk ay getirisi 0
    assert abs(out.iloc[0]["port"]) < 1e-12
    out_open = pb.simulate({t: ["A"] for t in months}, months, d0_of, mkt, {}, {t: 1e6 for t in months},
                           costs=ZERO, fill="open")
    assert abs(out_open.iloc[0]["port"]) < 1e-12  # acilis = kapanis bu testte


def test_costs_charged_on_first_buy():
    days, months, d0_of = _setup()
    mkt = _market({"A": [100.0] * 60, "B": [100.0] * 60}, days)
    liq = {t: np.array([1.0, 2.0, 3.0]) for t in months}  # adv=1e9 -> ust ucte bir -> 5 bps
    c = pb.Costs(commission_bps=10, spread_bps=(5, 15, 30), impact_k=0.0)
    out = pb.simulate({t: ["A", "B"] for t in months}, months, d0_of, mkt, liq, {t: 1e6 for t in months}, costs=c)
    first = out.iloc[0]
    assert np.isclose(first["cost"], 15e-4)
    assert np.isclose(first["port"], -15e-4, atol=1e-6)
    assert np.isclose(first["turnover"], 1.0)
    # ikinci ay liste ayni, fiyat sabit: islem yok, maliyet yok
    assert out.iloc[1]["cost"] == 0


def test_impact_grows_with_capital():
    days, months, d0_of = _setup()
    mkt = _market({"A": [100.0] * 60}, days, adv=1e6)
    small = pb.simulate({t: ["A"] for t in months}, months, d0_of, mkt, {}, {t: 1e4 for t in months})
    big = pb.simulate({t: ["A"] for t in months}, months, d0_of, mkt, {}, {t: 1e7 for t in months})
    assert big.iloc[0]["impact"] > small.iloc[0]["impact"]
    assert big.iloc[0]["fills_over_10pct_adv"] == 1 and small.iloc[0]["fills_over_10pct_adv"] == 0


def test_delisted_name_closed_with_haircut():
    days, months, d0_of = _setup()
    px_a = [100.0] * 15 + [np.nan] * 45  # 15. gunden sonra islem yok
    mkt = _market({"A": px_a, "B": [100.0] * 60}, days)
    out = pb.simulate({months[0]: ["A", "B"]}, months, d0_of, mkt, {}, {t: 1e6 for t in months},
                      costs=ZERO, haircut=0.5)
    assert out.attrs["delist_events"] == 1
    # 1. ay: A son fiyatindan tasinir (getiri 0). 2. ay: liste bos; A islem gormedigi icin
    # satilamaz (takili), B satilir; A 20 gun fiyatsiz kalinca yarisi kaybedilerek kapanir.
    assert np.isclose(out.iloc[0]["port"], 0.0)
    assert np.isclose(out.iloc[1]["port"], -0.25)


def test_cash_earns_deposit_rate_when_no_targets():
    days, months, d0_of = _setup()
    mkt = _market({"A": [100.0] * 60}, days, rf=0.001)
    out = pb.simulate({t: [] for t in months}, months, d0_of, mkt, {}, {t: 1e6 for t in months}, costs=ZERO)
    assert np.isclose(out.iloc[0]["port"], 1.001 ** 20 - 1)


def test_unbuyable_target_weight_stays_in_cash_and_stuck_held_separate():
    """Islem gununde fiyati olmayan hedef hissenin agirligi diger hisselere dagitilmaz,
    nakitte kalir; satilamayan mevcut pozisyon (stuck) da ayri tasinir."""
    days, months, d0_of = _setup()
    # Ilk dengeleme islem gunu: days[10]. Donem sonu: days[29].
    uni = [f"T{k}" for k in range(100)]
    prices = {}
    for k, tk in enumerate(uni):
        px = [100.0] * 11 + [110.0] * 49  # islem gunu (days[10]) 100'den alinir, donem sonunda 110 (+%10)
        if k == 99:
            px[10] = np.nan  # T99 yalnizca islem gununde fiyatsiz, donem sonunda tekrar 110.0
        prices[tk] = px
    mkt = _market(prices, days, rf=0.0)
    out = pb.simulate({months[0]: uni, months[1]: uni}, months, d0_of, mkt, {},
                      {t: 1e6 for t in months}, costs=ZERO)
    # 99 hisse %1'er agirlikla +%10 kazanir, T99'un %1 payi nakitte (%0) kalir -> port = %9.9 (%10 degil)
    assert out.iloc[0]["n"] == 99
    assert np.isclose(out.iloc[0]["turnover"], 0.99)
    assert np.isclose(out.iloc[0]["port"], 0.99 * 0.10, atol=1e-12)

    # Mevcut pozisyonu satilamayan (stuck) hisse: S 1. ayda alinir, 2. ay islem gunu (days[30]) fiyatsizdir;
    # yeni hedef listedeki B alinabilir, C ise islem gunu fiyatsizdir -> tradable sermayenin yarisi B'ye, yarisi nakde.
    px_s = [100.0] * 30 + [np.nan] * 5 + [100.0] * 25
    px_b = [100.0] * 31 + [120.0] * 29  # 2. ayda +%20
    px_c = [100.0] * 30 + [np.nan] + [120.0] * 29  # yalnizca days[30] islem gununde fiyatsiz
    mkt2 = _market({"S": px_s, "B": px_b, "C": px_c}, days, rf=0.0)
    out2 = pb.simulate({months[0]: ["S", "B"], months[1]: ["B", "C"]}, months, d0_of, mkt2, {},
                       {t: 1e6 for t in months}, costs=ZERO)
    # 2. ay basinda S (%50) stuck; kalan %50 tradable sermaye ["B", "C"] (2 slot) arasinda bolunur:
    # B %25 alir (+%20 kazanir -> +%5), C'nin %25 payi nakitte kalir (0 kazanir), S %50 sabit -> toplam +%5
    assert np.isclose(out2.iloc[1]["port"], 0.25 * 0.20, atol=1e-12)



def test_limit_rule_blocks_new_buy_and_freezes_held_position():
    """limit_pct: islem gunu %10 tavan olan yeni hedef alinmaz (nakitte); taban olan eldeki hisse satilamaz."""
    days, months, d0_of = _setup()
    # A: ilk islem gunu (gun 10) tavan, sonra +%10 daha; B: duz
    a = [100.0] * 10 + [110.0] * 20 + [121.0] * 30
    b = [100.0] * 60
    mkt = _market({"A": a, "B": b}, days)
    cap = {t: 1e6 for t in months}
    on = pb.simulate({t: ["A", "B"] for t in months}, months, d0_of, mkt, {}, cap, costs=ZERO, limit_pct=0.095)
    off = pb.simulate({t: ["A", "B"] for t in months}, months, d0_of, mkt, {}, cap, costs=ZERO)
    # kapali: A ilk ayda alinir, ikinci ay +%10 -> ay 2 getirisi %5
    assert np.isclose(off.iloc[1]["port"], 0.05)
    # acik: ilk ay A alinamaz (n_held 1), ikinci dengelemede (gun 30) A yine %10 sicradi -> yine alinmaz
    assert on.iloc[0]["n"] == 1
    assert on.iloc[1]["n"] == 1 and np.isclose(on.iloc[1]["port"], 0.0)

    # eldeki hisse taban: C ilk ayda alinir, gun 30'da %10 duser ve hedeften cikar ama satilamaz;
    # sonra %10 daha duser. Kural kapaliyken gun 30 kapanisinda satilir (-%10).
    c = [100.0] * 30 + [90.0] * 10 + [81.0] * 20
    mkt2 = _market({"C": c, "B": b}, days)
    targets = {months[0]: ["C"], months[1]: ["B"], months[2]: ["B"]}
    on2 = pb.simulate(targets, months, d0_of, mkt2, {}, cap, costs=ZERO, limit_pct=0.095)
    off2 = pb.simulate(targets, months, d0_of, mkt2, {}, cap, costs=ZERO)
    assert np.isclose(off2.iloc[1]["port"], -0.10)
    assert np.isclose(on2.iloc[1]["port"], -0.19)
