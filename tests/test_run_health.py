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


def test_catalyst_missing_share_degrades(temp_db):
    _seed()
    avail = {f"T{i:03d}": i < 30 for i in range(100)}
    h = run_health.assess(D, catalyst_available=avail)
    assert h["metrics"]["catalyst_missing_share"] == 0.7
    assert h["status"] == "DEGRADED" and "catalyst_redistributed" in h["issues"]


def test_outcomes_stalled_degrades(temp_db):
    _seed()
    conn = db.get_connection()
    conn.execute("""INSERT INTO predictions (as_of_date, ticker, bucket, entry_price, horizon_days)
                    VALUES ('2026-09-01', 'T001', 'short_term', 10, 20)""")
    conn.commit(); conn.close()
    h = run_health.assess(D)
    assert h["metrics"]["matured_without_outcome"] == 1
    assert "outcomes_stalled" in h["issues"] and h["status"] == "DEGRADED"
