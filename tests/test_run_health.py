"""run_health: sessiz kapsam cokusleri (2026-09-20..27 KAP olayi) gorunur olmali."""
from jinja2 import Environment, FileSystemLoader

from core import db, run_health
from report import render, validate

D = "2026-10-02"


def _seed(n=100, effective_at=D, pit_source="kap_financial_report", filtered_by=None,
          fresh=True, macro=True, fund_n=None):
    conn = db.get_connection()
    try:
        for i in range(n):
            t = f"T{i:03d}"
            conn.execute("INSERT INTO universe_snapshot (as_of_date, ticker) VALUES (?, ?)", (D, t))
            # uygun evren disi hisse paydaya girmemeli
            conn.execute("INSERT INTO universe_snapshot (as_of_date, ticker, exclusion_reason) VALUES (?, ?, ?)",
                         (D, "X" + t, "low_volume"))
            if fund_n is None or i < fund_n:
                conn.execute("INSERT INTO fundamentals (as_of_date, ticker, effective_at, pit_source) VALUES (?,?,?,?)",
                             (D, t, effective_at, pit_source))
            if fresh:
                conn.execute("INSERT INTO prices (date, ticker, close) VALUES (?,?,?)", (D, t, 10.0))
            conn.execute("INSERT INTO scores (as_of_date, ticker, bucket, filtered_by) VALUES (?,?,?,?)",
                         (D, t, "long_term", filtered_by))
        if macro:
            conn.execute("INSERT INTO regime_log (as_of_date, xu100_level, bond_2y_pct) VALUES (?,?,?)",
                         (D, 13000.0, 40.0))
        conn.commit()
    finally:
        conn.close()


def test_ok_when_all_sources_present(temp_db):
    _seed()
    h = run_health.assess(D)
    assert h["status"] == "OK" and h["issues"] == []
    assert len(h["config_hash"]) == 12


def test_kap_outage_pit_filter_is_failed(temp_db):
    # 2026-09-20 durumu: tarih yok -> point_in_time ile tum evren elendi
    _seed(effective_at=None, pit_source=None, filtered_by="point_in_time")
    h = run_health.assess(D)
    assert h["status"] == "FAILED"
    assert "data_filter_share" in h["issues"] and "kap_unavailable" in h["issues"]


def test_kap_outage_with_observed_fallback_is_degraded(temp_db):
    # PR #15 sonrasi: gozlem tarihi yedegi -> sinyal var ama katalizor kor
    _seed(pit_source="observed_at_ingest")
    h = run_health.assess(D)
    assert h["status"] == "DEGRADED" and h["issues"] == ["kap_unavailable"]


def test_low_coverage_and_missing_macro_fail(temp_db):
    _seed(fund_n=50, fresh=False, macro=False)
    h = run_health.assess(D)
    assert h["status"] == "FAILED"
    assert {"fundamentals_coverage", "price_fresh_coverage", "macro_missing"} <= set(h["issues"])


def test_persist_upserts(temp_db):
    _seed()
    h = run_health.assess(D)
    run_health.persist(h)
    run_health.persist({**h, "status": "DEGRADED"})
    rows = db.query("SELECT status FROM run_health WHERE as_of_date=?", (D,))
    assert [r["status"] for r in rows] == ["DEGRADED"]


def test_banner_numbers_pass_validation_gate(temp_db):
    _seed(fund_n=50, effective_at=None, pit_source=None, filtered_by="point_in_time", fresh=False)
    h = run_health.assess(D)
    env = Environment(loader=FileSystemLoader(str(render._TEMPLATE_DIR)))
    env.filters["fmt"] = render._fmt
    html = env.get_template("_run_health.html.j2").render(run_health=h)
    assert "YETERSİZ" in html
    assert validate.find_orphan_numbers(html, {"run_health": h}) == []


def test_price_stats_from_memory_and_empty_index(temp_db):
    _seed(fresh=False)
    rows = {f"T{i:03d}": [{"date": D, "close": 1.0}] for i in range(90)}
    rows.update({f"S{i}": [{"date": "2026-09-01", "close": 1.0}] for i in range(10)})
    ps = run_health.price_stats(D, rows, index_rows=[])
    assert ps == {"n_tickers": 100, "n_fresh": 90, "index_rows": 0}
    h = run_health.assess(D, prices=ps)
    assert h["metrics"]["price_fresh_coverage"] == 0.9
    assert "index_series_empty" in h["issues"] and h["status"] == "FAILED"


def test_catalyst_missing_share_degrades(temp_db, monkeypatch):
    import core.scoring as scoring
    real = scoring.load_weights()
    weighted = {**real, "scoring_weights": {**real["scoring_weights"], "catalyst_score": 0.25}}
    monkeypatch.setattr(scoring, "load_weights", lambda: weighted)
    _seed()
    avail = {f"T{i:03d}": i < 30 for i in range(100)}
    h = run_health.assess(D, catalyst_available=avail)
    assert h["metrics"]["catalyst_missing_share"] == 0.7
    assert h["status"] == "DEGRADED" and "catalyst_redistributed" in h["issues"]


def test_catalyst_missing_ignored_when_weight_zero(temp_db):
    """Faz 2: katalizor agirligi 0 -> eksik KAP verisi skoru etkilemez, uyari yok."""
    _seed()
    avail = {f"T{i:03d}": i < 30 for i in range(100)}
    h = run_health.assess(D, catalyst_available=avail)
    assert "catalyst_redistributed" not in h["issues"]


def test_outcomes_stalled_degrades(temp_db):
    _seed()
    conn = db.get_connection()
    conn.execute("""INSERT INTO predictions (as_of_date, ticker, bucket, entry_price, horizon_days)
                    VALUES ('2026-09-01', 'T001', 'short_term', 10, 20)""")
    conn.commit(); conn.close()
    h = run_health.assess(D)
    assert h["metrics"]["matured_without_outcome"] == 1
    assert "outcomes_stalled" in h["issues"] and h["status"] == "DEGRADED"


def _make_cpi():
    import pandas as pd
    # ~30%/yil sabit enflasyon (aylik ~2.21%)
    dates = pd.date_range("2024-01-31", "2026-09-30", freq="ME")
    return pd.Series([1.0221 ** i for i in range(len(dates))], index=pd.PeriodIndex(dates, freq="M"))


def _make_inc(ytd_by_period: dict[str, float]):
    import pandas as pd
    return pd.DataFrame([ytd_by_period], index=["Satış Gelirleri"])


def _healthy_ias29_inc(scale: float = 1.0, real_growth: float = 1.03):
    """Mevcut Is Yatirim sozlesmesi: P ve P-4 ayni satin alma gucunde (2026Q2)."""
    cpi = _make_cpi()
    c = lambda ym: float(cpi[ym])  # noqa: E731
    # 2025Q1..2025Q2 2026-03/06 PP'sinde yeniden ifade edilmis; 2026Q1..Q2 gercek
    q25_1 = 100.0 * scale
    q25_2 = 105.0 * scale
    ytd_25q1 = q25_1
    ytd_25q2 = q25_1 * (c("2025-06") / c("2025-03")) + q25_2
    q26_1 = q25_1 * real_growth
    q26_2 = q25_2 * real_growth
    ytd_26q1 = q26_1
    ytd_26q2 = q26_1 * (c("2026-06") / c("2026-03")) + q26_2
    return _make_inc({"2026Q2": ytd_26q2, "2026Q1": ytd_26q1, "2025Q2": ytd_25q2, "2025Q1": ytd_25q1})


def test_vendor_consistency_ok_under_current_convention(temp_db):
    _seed()
    cpi = _make_cpi()
    stmts = {f"S{i}": _healthy_ias29_inc(scale=10 + i, real_growth=0.95 + 0.03 * i) for i in range(6)}
    vc = run_health.vendor_consistency_check(stmts, cpi=cpi)
    assert vc["n_checked"] == 6
    assert 0.95 <= vc["median_ratio"] <= 1.15
    assert vc["ok"] is True
    h = run_health.assess(D, vendor_check=vc)
    assert h["status"] == "OK"
    assert "vendor_inconsistent" not in h["issues"]
    assert h["metrics"]["vendor_checked_n"] == 6
    assert h["metrics"]["vendor_q_yoy_median"] == vc["median_ratio"]


def test_vendor_consistency_mixed_units_0_5x_degrades(temp_db):
    """0.4-0.6x birim karismasi (docs/research/vendor_vs_kap_audit.md) DEGRADED uretmeli."""
    _seed()
    cpi = _make_cpi()
    c = lambda ym: float(cpi[ym])  # noqa: E731
    # 2025Q2 yeniden ifade edilmis (x1.32), 2025Q3 edilmemis -> ayrik 2025Q3 ~0.5x 2024Q3
    stmts = {}
    for i in range(6):
        s = 100.0 + 10 * i
        # 2024Q2/Q3 tutarli (ikisi de 2025 PP'sinde); 2025Q2 2026-06 PP'sinde, 2025Q3 2025-09 PP'sinde
        ytd_24q2 = 200.0 * s
        ytd_24q3 = ytd_24q2 * (c("2024-09") / c("2024-06")) + 100.0 * s
        ytd_25q2 = 200.0 * s * 1.32
        ytd_25q3 = ytd_24q3 * 1.02  # henuz yeniden ifade edilmemis!
        stmts[f"S{i}"] = _make_inc({"2025Q3": ytd_25q3, "2025Q2": ytd_25q2, "2024Q3": ytd_24q3, "2024Q2": ytd_24q2})
    vc = run_health.vendor_consistency_check(stmts, cpi=cpi)
    assert vc["n_checked"] == 6
    assert vc["median_ratio"] < 0.75
    assert vc["ok"] is False
    h = run_health.assess(D, vendor_check=vc)
    assert h["status"] == "DEGRADED"
    assert "vendor_inconsistent" in h["issues"]


def test_vendor_consistency_stopped_reexpression_above_max_degrades(temp_db):
    """Saglayici P-4'u yeniden ifade etmeyi birakirsa oran enflasyon kadar (~1.35x) firlar -> DEGRADED."""
    _seed()
    cpi = _make_cpi()
    stmts = {f"S{i}": _healthy_ias29_inc(scale=10 + i, real_growth=1.36) for i in range(6)}
    vc = run_health.vendor_consistency_check(stmts, cpi=cpi)
    assert vc["median_ratio"] > run_health.VENDOR_RATIO_MAX
    assert vc["ok"] is False
    h = run_health.assess(D, vendor_check=vc)
    assert h["status"] == "DEGRADED" and "vendor_inconsistent" in h["issues"]


def test_vendor_consistency_ytd_to_discrete_switch_negative_degrades(temp_db):
    """Saglayici YTD yerine ayrik ceyrek vermeye baslarsa q_revenue <= 0 olur -> DEGRADED."""
    _seed()
    cpi = _make_cpi()
    # Ayrik ceyrekler (YTD degil): Q2 ~= Q1 oldugundan YTD farki <= 0 cikar
    stmts = {f"S{i}": _make_inc({"2026Q2": 100.0, "2026Q1": 105.0, "2025Q2": 220.0, "2025Q1": 100.0})
             for i in range(6)}
    vc = run_health.vendor_consistency_check(stmts, cpi=cpi)
    assert vc["n_checked"] == 6 and vc["median_ratio"] < 0
    assert vc["ok"] is False
    h = run_health.assess(D, vendor_check=vc)
    assert h["status"] == "DEGRADED" and "vendor_inconsistent" in h["issues"]


def test_vendor_consistency_insufficient_sample_and_pre_ias29_ignored(temp_db):
    _seed()
    cpi = _make_cpi()
    # Sadece 3 hisse (< VENDOR_SAMPLE_MIN_N=5) -> ok=None, yanlis alarm yok
    small = {f"S{i}": _healthy_ias29_inc(real_growth=0.4) for i in range(3)}
    vc_small = run_health.vendor_consistency_check(small, cpi=cpi)
    assert vc_small["n_checked"] == 3 and vc_small["ok"] is None
    assert run_health.assess(D, vendor_check=vc_small)["status"] == "OK"
    # Pre-IAS 29 donemler atlanir
    pre = {f"P{i}": _make_inc({"2022Q2": 300.0, "2022Q1": 140.0, "2021Q2": 150.0, "2021Q1": 70.0})
           for i in range(6)}
    assert run_health.vendor_consistency_check(pre, cpi=cpi)["n_checked"] == 0


def test_market_cap_cross_check_ok_and_flagged(temp_db):
    _seed()
    tv = {"AAA": 100e9, "BBB": 52e9, "CCC": 10e9, "NONE_MC": None, "ONLY_TV": 5e9}
    isy = {"AAA": 100e9, "BBB": 50e9, "CCC": 10.5e9, "ONLY_ISY": 20e9}
    ok_chk = run_health.market_cap_cross_check(tv, isy)
    assert ok_chk["n_checked"] == 3 and ok_chk["n_flagged"] == 0
    assert ok_chk["max_diff_pct"] == 4.8
    h_ok = run_health.assess(D, mcap_check=ok_chk)
    assert h_ok["status"] == "OK" and "mcap_mismatch" not in h_ok["issues"]

    tv_bad = {**tv, "AAA": 115e9, "CCC": 7.5e9}  # +15% ve -28.6%
    bad_chk = run_health.market_cap_cross_check(tv_bad, isy)
    assert bad_chk["n_checked"] == 3 and bad_chk["n_flagged"] == 2
    assert [f["ticker"] for f in bad_chk["flagged"]] == ["CCC", "AAA"]  # sapmaya gore azalan
    assert bad_chk["flagged"][0]["diff_pct"] == 28.6
    h_bad = run_health.assess(D, mcap_check=bad_chk)
    assert h_bad["status"] == "DEGRADED" and "mcap_mismatch" in h_bad["issues"]
    assert h_bad["metrics"]["mcap_flagged_tickers"] == ["CCC", "AAA"]
    assert len(h_bad["mcap_flagged"]) == 2


def test_new_safeguard_banners_pass_validation_gate(temp_db):
    _seed()
    cpi = _make_cpi()
    vc = run_health.vendor_consistency_check(
        {f"S{i}": _healthy_ias29_inc(real_growth=1.42) for i in range(6)}, cpi=cpi)
    mc = run_health.market_cap_cross_check({"AAA": 125e9, "BBB": 50e9}, {"AAA": 100e9, "BBB": 50e9})
    h = run_health.assess(D, vendor_check=vc, mcap_check=mc)
    assert set(h["issues"]) == {"vendor_inconsistent", "mcap_mismatch"}
    env = Environment(loader=FileSystemLoader(str(render._TEMPLATE_DIR)))
    env.filters["fmt"] = render._fmt
    html = env.get_template("_run_health.html.j2").render(run_health=h)
    assert "TMS 29" in html and "Piyasa değeri" in html
    assert validate.find_orphan_numbers(html, {"run_health": h}) == []


def test_live_isyatirim_market_caps_scales_millions_and_handles_error(monkeypatch):
    import pandas as pd
    from core import live_data

    class FakeScreener:
        _provider = type("P", (), {"CRITERIA_MAP": {"market_cap": "8"}})()
        def add_filter(self, *a, **kw): return self
        def run(self):
            return pd.DataFrame([
                {"symbol": "THYAO", "name": "THY", "criteria_8": 454020.0},
                {"symbol": "INDES", "name": "Indeks", "criteria_8": 6330.5},
                {"symbol": "BAD", "name": "Bad", "criteria_8": None},
            ])

    monkeypatch.setattr(live_data.bp, "Screener", FakeScreener)
    out = live_data.live_isyatirim_market_caps()
    assert out == {"THYAO": 454_020_000_000.0, "INDES": 6_330_500_000.0}

    class BrokenScreener:
        def add_filter(self, *a, **kw): return self
        def run(self): raise RuntimeError("timeout")

    monkeypatch.setattr(live_data.bp, "Screener", BrokenScreener)
    assert live_data.live_isyatirim_market_caps() == {}
