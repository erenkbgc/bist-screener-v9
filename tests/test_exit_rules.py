import numpy as np
import pandas as pd

from core import exit_rules as xr


def _setup(path_a, path_b, ranks):
    days = pd.bdate_range("2020-01-31", periods=len(path_a))
    close = pd.DataFrame({"A": path_a, "B": path_b}, index=days)
    atr = pd.DataFrame({"A": 1.0, "B": 1.0}, index=days)
    xu = pd.Series(np.linspace(100, 110, len(days)), index=days)
    months = [days[0], days[10], days[20]]
    universe = {}
    for t, rk in zip(months, ranks):
        g = pd.DataFrame({"rank_pct": rk, "ep": 0.1, "f7": 5.0}, index=["A", "B"])
        g["bench"], g["bench_usd"], g["fx_ret"] = 0.0, 0.0, 0.0
        universe[t] = g
    d0_of = {t: t for t in months}
    return months, universe, close, atr, xu, d0_of


def test_buffer_keeps_name_and_r0_sells():
    path = [100.0] * 21
    m, u, c, a, xu, d0 = _setup(path, path, [(0.1, 0.9), (0.3, 0.1), (0.1, 0.1)])
    r0, _ = xr.simulate(xr.RULES["R0"], m, u, c, a, xu, d0)
    r1, _ = xr.simulate(xr.RULES["R1"], m, u, c, a, xu, d0)
    assert list(r0["n"]) == [1, 1]           # ay 2: yalniz B (A 0.3 > 0.2 -> satilir)
    assert list(r1["n"]) == [1, 2]           # ay 2: A tamponda kalir + B alinir
    assert r0["turnover"].iloc[1] == 1.0 and r1["turnover"].iloc[1] == 0.5


def test_trailing_stop_moves_proceeds_to_index():
    a_path = [100.0, 120.0, 85.0] + [80.0] * 18   # zirve 120 -> 90 alti tetik (85)
    m, u, c, a, xu, d0 = _setup(a_path, [100.0] * 21, [(0.1, 0.9), (0.1, 0.9), (0.1, 0.9)])
    p, stops = xr.simulate(xr.RULES["X1"], m, u, c, a, xu, d0)
    assert stops[0]["ticker"] == "A" and stops[0]["pos"] == 2
    expected = 85.0 / 100.0 * (xu.iloc[10] / xu.iloc[2]) - 1
    assert abs(p["port"].iloc[0] - expected) < 1e-12
    assert p["n_stops"].iloc[0] == 1
    # stop sonrasi bir sonraki dengelemede yeniden yeni alim olarak girer (zirve sifirlanir)
    assert p["turnover"].iloc[1] == 1.0


def test_fixed_and_atr_levels():
    assert xr.stop_level(xr.RULES["X2"], 100.0, 150.0, 5.0) == 80.0
    assert xr.stop_level(xr.RULES["X3"], 100.0, 150.0, 5.0) == 90.0
    assert xr.stop_level(xr.RULES["R1"], 100.0, 150.0, 5.0) == -np.inf


def test_thesis_break_sells_inside_buffer():
    path = [100.0] * 21
    m, u, c, a, xu, d0 = _setup(path, path, [(0.1, 0.9), (0.3, 0.9), (0.3, 0.9)])
    u[m[1]].loc["A", "f7"] = 2.0
    r1, _ = xr.simulate(xr.RULES["R1"], m, u, c, a, xu, d0)
    x4, _ = xr.simulate(xr.RULES["X4"], m, u, c, a, xu, d0)
    assert r1["n"].iloc[1] == 1 and len(x4) == 1  # X4: A satildi, ust dilimde kimse yok -> ay atlanir
