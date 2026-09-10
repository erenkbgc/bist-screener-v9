"""dashboard.py: salt-okunur goruntuleme katmani.

execution_rules.deterministic_math: "Dashboard hicbir hesaplama yapmaz."
acceptance_criteria: "dashboard.py veritabanina yalnizca salt-okunur erisiyor
ve rapordakiyle birebir ayni sayilari gosteriyor."

Bu dosya core/db.get_connection(read_only=True) DISINDA hicbir baglanti
acmaz ve HICBIR INSERT/UPDATE/DELETE ifadesi icermez (tests/test_dashboard_read_only.py
bunu kaynak taramasiyla dogrular). Bu yuzden core.payload.build_report_payload
(yazma izinli baglanti kullanan core.db.query'ye dayanir) burada BILEREK
kullanilmaz; ayni SELECT sorgulari salt-okunur baglanti ile burada tekrarlanir
-- tablo/kolon adlari core/db.py SCHEMA'siyla birebir aynidir, bu yuzden
rapordakiyle birebir ayni sayilari gosterir.
"""
from __future__ import annotations

import streamlit as st

from core import db


def _q(sql: str, params: tuple = ()):
    conn = db.get_connection(read_only=True)
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def main() -> None:
    st.set_page_config(page_title="BIST AI Screener - Dashboard", layout="wide")
    st.title("BIST AI Investment Screener - Dashboard (salt-okunur)")

    dates = _q("SELECT DISTINCT as_of_date FROM runs ORDER BY as_of_date DESC")
    if not dates:
        st.info("Henuz hicbir kosu calistirilmadi. `python run.py` ile bir kosu baslatin.")
        return

    as_of_date = st.selectbox("Tarih", [d["as_of_date"] for d in dates])

    regime_rows = _q("SELECT * FROM regime_log WHERE as_of_date=?", (as_of_date,))
    scores = _q("SELECT * FROM scores WHERE as_of_date=?", (as_of_date,))
    predictions = _q("SELECT * FROM predictions WHERE as_of_date=?", (as_of_date,))
    gordon = _q("SELECT * FROM gordon_reference WHERE as_of_date=?", (as_of_date,))
    beta = _q("SELECT * FROM beta_metrics WHERE as_of_date=?", (as_of_date,))
    sloan = _q("SELECT * FROM earnings_quality WHERE as_of_date=?", (as_of_date,))
    events = _q("SELECT * FROM upcoming_events")
    invalidation_triggered = _q(
        "SELECT * FROM invalidation_checks WHERE triggered_at IS NOT NULL AND resolved=0"
    )
    correlation_flags = _q("SELECT * FROM correlation_flags WHERE as_of_date=?", (as_of_date,))

    if regime_rows:
        st.subheader("Rejim Ozeti")
        r = regime_rows[0]
        cols = st.columns(5)
        cols[0].metric("Politika Faizi (%)", r["policy_rate_pct"])
        cols[1].metric("2Y Tahvil (%)", r["bond_2y_pct"])
        cols[2].metric("TUFE yillik (%)", r["cpi_yoy_pct"])
        cols[3].metric("USD/TRY", r["usdtry_spot"])
        cols[4].metric("XU100", r["xu100_level"])
        if r.get("real_rate_regime"):
            st.caption(f"regime_taxonomy: {r['real_rate_regime']}_real_rate + "
                       f"{r['inflation_trend']}_inflation + {r['fx_regime']}")

    st.subheader("Skorlanan Adaylar")
    st.dataframe(scores, use_container_width=True) if scores else st.write("Bu tarih icin skor kaydi yok.")

    no_action_today = not any(s["candidate_state"] in ("STRONG_OPPORTUNITY", "OPPORTUNITY") for s in scores)
    if no_action_today:
        st.warning("NO_ACTION_TODAY: Bu kosuda hard_filters'i gecen hicbir aday yok.")

    st.subheader("Tahminler (predictions)")
    st.dataframe(predictions, use_container_width=True)

    st.subheader("Gordon Buyume Referansi (deneysel, bilgi amacli)")
    st.dataframe(gordon, use_container_width=True)

    st.subheader("Beta-duzeltmeli Hurdle (bilgi amacli)")
    st.dataframe(beta, use_container_width=True)

    st.subheader("Sloan Tahakkuk Bayragi (bilgi amacli)")
    st.dataframe(sloan, use_container_width=True)

    st.subheader("Yaklasan Olaylar")
    st.dataframe(events, use_container_width=True)

    st.subheader("Bozulan Tez Uyarilari")
    st.dataframe(invalidation_triggered, use_container_width=True) if invalidation_triggered else \
        st.write("Tetiklenen bir bozulma kosulu yok.")

    st.subheader("Korelasyon Uyarilari (>0.85, otomatik eleme yapilmaz)")
    st.dataframe(correlation_flags, use_container_width=True)

    st.caption(
        "Skorlama agirliklari (0.55/0.30/0.15), Piotroski esigi ve equity risk premium "
        "denenmemis baslangic varsayimlaridir. Bu dashboard yatirim tavsiyesi degildir."
    )


if __name__ == "__main__":
    main()
