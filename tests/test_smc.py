"""core/smc: yapi kirilimi (BOS/CHoCH), order block, FVG, bolgeler ve repaint olmamasi."""
import numpy as np
import pandas as pd

from core import smc


def _frame(closes, spread=0.5):
    c = np.asarray(closes, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    idx = pd.bdate_range("2024-01-01", periods=len(c))
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + spread, "low": np.minimum(o, c) - spread,
                         "close": c}, index=idx)


def _zigzag():
    # yukari dalgalar (yuksek tepe/dip), sonra sert dusus
    seg = []
    level = 100.0
    for up, down in ((15, 8), (15, 8), (15, 8)):
        seg += list(np.linspace(level, level + up, 12))[1:]
        level += up
        seg += list(np.linspace(level, level - down, 8))[1:]
        level -= down
    seg += list(np.linspace(level, level - 40, 25))[1:]
    return [100.0] + seg


def test_bullish_bos_then_bearish_choch():
    res = smc.analyze(_frame(_zigzag()), swing_size=5, internal_size=3, atr_length=14)
    st = res.events[res.events["kind"].isin([smc.BOS, smc.CHOCH]) & (res.events["scope"] == "swing")]
    assert len(st) >= 2
    ups = st[st["direction"] == smc.BULLISH]
    assert (ups["kind"] == smc.BOS).any()
    first_down = st[st["direction"] == smc.BEARISH].iloc[0]
    assert first_down["kind"] == smc.CHOCH  # yukari trendden sonraki ilk asagi kirilim
    assert res.swing_bias == smc.BEARISH


def test_no_repaint_prefix_events_are_stable():
    df = _frame(_zigzag())
    full = smc.analyze(df, swing_size=5, internal_size=3, atr_length=14).events
    for k in (30, 50, 70):
        part = smc.analyze(df.iloc[:k], swing_size=5, internal_size=3, atr_length=14).events
        expect = full[full["bar"] < k].reset_index(drop=True)
        pd.testing.assert_frame_equal(part.reset_index(drop=True), expect)


def test_pivot_known_only_after_size_bars():
    # tepe: bar 11 (bar 10 ile esit yuksek; kesin buyukluk gerekir); size=5 -> bar 16'da bilinir
    closes = [100 + i for i in range(11)] + [110 - i for i in range(1, 20)]
    df = _frame(closes, spread=0.1)
    legs = smc._legs(df["high"].to_numpy(), df["low"].to_numpy(), 5)
    # yukselis boyunca bacak yukari (1); tepe ancak bar 16'da dogrulanir
    assert legs[15] == 1 and legs[16] == 0
    before = smc.analyze(df.iloc[:16], swing_size=5, internal_size=5, atr_length=5)
    after = smc.analyze(df.iloc[:17], swing_size=5, internal_size=5, atr_length=5)
    assert before.trailing_top == after.trailing_top == df["high"].iloc[11]


def test_bullish_fvg_detected_and_mitigated():
    rows = [(100, 101, 99, 100)] * 5 + [(100, 101, 99.5, 100.8), (101, 106, 100.9, 105.5), (106, 108, 104, 107)]
    rows += [(107, 107.5, 106, 107)] * 3
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=pd.bdate_range("2024-01-01", periods=len(rows)))
    res = smc.analyze(df, swing_size=3, internal_size=2, atr_length=3, fvg_auto_threshold=False)
    fvg = res.events[res.events["kind"] == "FVG"]
    assert len(fvg) == 1 and fvg.iloc[0]["direction"] == smc.BULLISH
    assert len(res.fvgs) == 1 and res.fvgs[0].bottom == 101 and res.fvgs[0].top == 104
    # fiyat boslugun altina inerse kapanir
    df2 = pd.concat([df, pd.DataFrame([(106, 106, 100, 100.5)], columns=df.columns,
                                      index=[df.index[-1] + pd.offsets.BDay()])])
    assert smc.analyze(df2, swing_size=3, internal_size=2, atr_length=3, fvg_auto_threshold=False).fvgs == []


def test_order_block_created_and_mitigated():
    df = _frame(_zigzag())
    res = smc.analyze(df, swing_size=5, internal_size=3, atr_length=14)
    # son sert dusus tum yukari order blocklari kirar
    assert all(b.bias == smc.BEARISH for b in res.order_blocks)


def test_zone_bands():
    assert smc.zone(99, 100, 0) == "premium"
    assert smc.zone(2, 100, 0) == "discount"
    assert smc.zone(50, 100, 0) == "equilibrium"
    assert smc.zone(70, 100, 0) == "premium_half"
    assert smc.zone(30, 100, 0) == "discount_half"
    assert smc.zone(50, np.nan, 0) is None


def test_atr_wilder_matches_definition():
    h = np.array([2, 3, 4, 5.0]); lo = np.array([1, 1, 2, 3.0]); c = np.array([1.5, 2, 3, 4.0])
    a = smc.atr_wilder(h, lo, c, 2)
    tr = [1, 2, 2, 2]
    assert np.isnan(a[0]) and a[1] == 1.5 and a[2] == (1.5 + tr[2]) / 2


def test_snapshot_needs_history_and_returns_fields():
    assert smc.snapshot([]) == {}
    df = _frame(_zigzag() * 3)
    rows = [{"date": str(d.date()), **r} for d, r in df.to_dict("index").items()]
    snap = smc.snapshot(rows, swing_size=5, internal_size=3)
    assert snap["smc_swing_trend"] in ("yukari", "asagi")
    assert set(snap) >= {"smc_zone", "smc_last_structure", "smc_bull_ob", "smc_bear_ob", "smc_open_fvg"}
