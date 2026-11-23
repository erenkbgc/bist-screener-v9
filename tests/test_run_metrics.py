import json
import time

import pandas as pd

import run as run_mod
from core import live_data as ld


def test_tracked_counts_provider_calls_and_empty():
    calls = []

    @ld._tracked("unit_probe")
    def probe(x):
        calls.append(x)
        return None if x == "bad" else pd.DataFrame({"a": [1]})

    probe("ok"); probe("bad"); probe("ok2")
    st = ld._PROVIDER_STATS["unit_probe"]
    assert st["calls"] == 3 and st["empty"] == 1
    assert len(calls) == 3


def test_is_empty_result_shapes():
    assert ld._is_empty_result(None)
    assert ld._is_empty_result((None, None))
    assert ld._is_empty_result(pd.DataFrame())
    assert ld._is_empty_result({})
    assert not ld._is_empty_result((None, pd.DataFrame({"a": [1]})))
    assert not ld._is_empty_result({"k": 1})


def test_provider_stats_lists_tracked_fetchers():
    stats = ld.provider_stats()
    assert "quarterly_statements" in stats and "fast_info" in stats
    assert set(stats["fast_info"]) >= {"provider_calls", "empty_share", "mean_s", "cache_hit_share"}


def test_stage_seconds_are_deltas(monkeypatch):
    run_mod._STAGE_SECONDS.clear()
    t0 = time.monotonic() - 10
    run_mod._timing(t0, "a")
    run_mod._timing(t0 - 5, "b")
    assert run_mod._STAGE_SECONDS["a"] >= 10
    assert 4 <= run_mod._STAGE_SECONDS["b"] <= 6


def test_write_run_metrics_never_raises_and_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "Path", lambda *_a, **_k: tmp_path / "x" / "run.py")
    monkeypatch.setattr(run_mod.bist_mcp, "_live_enabled", lambda: False)
    run_mod._STAGE_SECONDS.clear()
    scored = [{"valid_metric_count": 4}, {"valid_metric_count": 2}, {"valid_metric_count": None}]
    run_mod._write_run_metrics("2026-11-24", time.monotonic() - 60, [{"ticker": "A"}] * 3, scored)
    m = json.loads((tmp_path / "x" / "data" / "reports" / "run_metrics_2026-11-24.json").read_text())
    assert m["value_coverage"]["all_4_share"] == round(1 / 3, 4)
    assert m["value_coverage"]["ge_2_share"] == round(2 / 3, 4)
    assert m["n_eligible"] == 3 and m["limit_used_share"] > 0
