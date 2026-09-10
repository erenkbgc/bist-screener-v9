#!/usr/bin/env python3
"""Autonomous BIST AI Investment Screener - gunluk kosu orkestratoru.

execution_order (spec): regime_monitor -> regime_taxonomy -> universe ->
basis_guard -> ranking -> earnings_quality_sloan -> catalysts ->
event_calendar_engine -> ownership_quality -> target_price_engine ->
hurdle_engine -> beta_adjusted_hurdle -> dividend_sustainability_engine ->
optional_valuation_addon -> concentration_check -> correlation_diagnostic ->
decision_diff_engine -> payload -> thesis_card -> validate -> dispatch ->
evaluate_past_predictions -> thesis_invalidation_monitor

deterministic_math: butun sayisal hesap burada ve core/ altinda; agentic bir
LLM adimi bu dosyada YOKTUR (agentic_workflow=true, ama bu script'in kendisi
"skill'lerin tasidigi yontemi" deterministik olarak calistirir; sentez/metin
uretimi gerektiginde core/thesis.py sablon tabanli calisir, serbest LLM
yorumu icermez).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import uuid
from datetime import date, datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()  # .env dosyasindaki SMTP_*/MAIL_*/BIST_DATA_MODE degiskenlerini yukler
except ImportError:
    pass  # python-dotenv kurulu degilse ortam degiskenleri zaten disaridan export edilmis olmali

from core import db
from core import regime as regime_mod
from core import regime_taxonomy
from core import universe as universe_mod
from core import basis_guard
from core import piotroski as piotroski_mod
from core import sloan as sloan_mod
from core import catalysts as catalysts_mod
from core import events as events_mod
from core import ownership as ownership_mod
from core import targets as targets_mod
from core import hurdle as hurdle_mod
from core import beta_hurdle as beta_hurdle_mod
from core import dividend_sustainability as div_sustain_mod
from core import gordon as gordon_mod
from core import concentration as concentration_mod
from core import correlation as correlation_mod
from core import scoring as scoring_mod
from core import payload as payload_mod
from core import thesis as thesis_mod
from core import invalidation as invalidation_mod
from core import evaluate as evaluate_mod
from bist_mcp import server as bist_mcp
from report import render as report_render
from report import validate as report_validate


def _net_debt_ebitda(net_debt, ebitda_ttm):
    return (net_debt / ebitda_ttm) if (ebitda_ttm and net_debt is not None) else None


def _fcf_yield(fcf_ttm, market_cap):
    return (fcf_ttm / market_cap) if (market_cap and fcf_ttm is not None) else None


def _shares_outstanding(market_cap, pe, eps_ttm):
    if market_cap and pe and eps_ttm:
        return market_cap / (pe * eps_ttm)
    return None


def _build_base_candidate(u: dict, fnd: dict, piotroski_by_ticker: dict, sloan_by_ticker: dict,
                            catalyst_by_ticker: dict, ownership_by_ticker: dict) -> dict:
    ticker = u["ticker"]
    raw = fnd.get("_raw", {})
    pio = piotroski_by_ticker.get(ticker, {})
    sl = sloan_by_ticker.get(ticker, {})
    cat = catalyst_by_ticker.get(ticker, {"catalyst_score": 0.0})
    own = ownership_by_ticker.get(ticker, {})

    net_debt_ebitda = _net_debt_ebitda(fnd.get("net_debt"), fnd.get("ebitda_ttm"))
    fcf_yield = _fcf_yield(fnd.get("fcf_ttm"), u.get("market_cap"))
    shares_outstanding = _shares_outstanding(u.get("market_cap"), raw.get("pe"), fnd.get("eps_ttm"))

    return {
        "ticker": ticker, "sector": u["sector"], "supersector": u["supersector"],
        "ratio_profile": u["ratio_profile"], "regulator": u["regulator"],
        "reporting_basis": fnd["reporting_basis"], "tedbir_level": u["tedbir_level"],
        "listing_days": u["listing_days"], "market_cap": u["market_cap"],
        "effective_at": fnd["effective_at"],
        "pe": raw.get("pe"), "pb": raw.get("pb"), "ev_ebitda": raw.get("ev_ebitda"),
        "ev_sales": raw.get("ev_sales"), "roe": raw.get("roe"), "roa": raw.get("roa"),
        "nim": raw.get("nim"), "npl_ratio": raw.get("npl_ratio"), "car": raw.get("car"),
        "combined_ratio": raw.get("combined_ratio"), "ffo_yield": raw.get("ffo_yield"),
        "nav_discount": raw.get("nav_discount"), "net_debt_ebitda": net_debt_ebitda,
        "fcf_yield": fcf_yield, "fcf_yield_usd": fnd.get("fcf_yield_usd"),
        "eps_ttm": fnd.get("eps_ttm"), "ebitda_ttm": fnd.get("ebitda_ttm"),
        "net_debt": fnd.get("net_debt"), "shares_outstanding": shares_outstanding,
        "dividend_per_share_ttm": fnd.get("dividend_per_share_ttm"),
        "payout_ratio": fnd.get("payout_ratio"), "fcf_ttm": fnd.get("fcf_ttm"),
        "piotroski_normalized_score": pio.get("normalized_score"),
        "sloan_flag": bool(sl.get("elevated_risk_flag")), "sloan_peer_percentile": sl.get("peer_percentile"),
        "catalyst_score": cat.get("catalyst_score", 0.0),
        "retail_pct": own.get("retail_pct"), "free_float_pct": own.get("free_float_pct"),
        "institutional_pct": own.get("institutional_pct"), "foreign_pct": own.get("foreign_pct"),
        "investor_count_change_1m": own.get("investor_count_change_1m"),
        "_penalize": own.get("_penalize", False), "_short_term_rejected": own.get("_short_term_rejected", False),
        "_raw_fundamentals": fnd,
    }


def run(as_of_date: str, min_volume_tl: float = 10_000_000) -> dict:
    db.init_db()
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    existing = db.query("SELECT * FROM runs WHERE as_of_date=?", (as_of_date,))
    if existing and existing[0]["email_sent"]:
        return {"status": "skipped_idempotent", "as_of_date": as_of_date}

    # --- 1. regime_monitor ---
    try:
        regime_result = regime_mod.check_market_regime(as_of_date)
    except regime_mod.RegimeHaltError as exc:
        _persist_run(run_id, as_of_date, "halted", "HALTED", started_at, str(exc))
        return {"status": "halted", "reason": str(exc)}

    # --- 2. regime_taxonomy ---
    taxonomy = regime_taxonomy.compute_taxonomy(
        as_of_date, regime_result["snapshot"]["policy_rate_pct"], regime_result["snapshot"]["cpi_yoy_pct"]
    )

    # --- 3. universe ---
    universe_mod.build_universe(as_of_date, min_volume_tl=min_volume_tl)
    eligible = universe_mod.eligible_tickers(as_of_date)
    if not eligible:
        _persist_run(run_id, as_of_date, "completed", "NO_ACTION_TODAY", started_at, None)
        return {"status": "no_eligible_universe", "as_of_date": as_of_date}

    # --- 4. basis_guard uygulanmis fundamentals ---
    from core import fundamentals as fundamentals_mod
    fundamentals_rows = fundamentals_mod.fetch_and_store_fundamentals(as_of_date, eligible)
    fundamentals_by_ticker = {r["ticker"]: r for r in fundamentals_rows}

    ur = basis_guard.unknown_ratio(fundamentals_rows)
    if ur > basis_guard.UNKNOWN_RATIO_HALT_THRESHOLD:
        _persist_run(run_id, as_of_date, "halted", "HALTED", started_at,
                     f"basis_guard: unknown oran %{ur*100:.1f} > %30")
        return {"status": "halted", "reason": "basis_guard_unknown_ratio"}

    # --- 5. quality_filter_piotroski + earnings_quality_sloan ---
    piotroski_rows = piotroski_mod.calculate_piotroski_scores(as_of_date, eligible)
    piotroski_by_ticker = {r["ticker"]: r for r in piotroski_rows}
    sloan_rows = sloan_mod.calculate_earnings_quality(as_of_date, eligible, fundamentals_by_ticker)
    sloan_by_ticker = {r["ticker"]: r for r in sloan_rows}

    # --- 6. catalysts + event_calendar_engine ---
    tickers = [u["ticker"] for u in eligible]
    catalyst_by_ticker = catalysts_mod.fetch_kap_catalysts(as_of_date, tickers, lookback_days=14)
    events_by_ticker = events_mod.fetch_upcoming_events(as_of_date, tickers)

    # --- prices (hurdle/beta/target/correlation icin ortak girdi) ---
    prices_by_ticker = {t: bist_mcp.get_prices(t, as_of_date, days=140) for t in tickers}

    # --- 7. ownership_quality ---
    ownership_rows = [ownership_mod.fetch_ownership(as_of_date, t, prices_by_ticker[t]) for t in tickers]
    ownership_by_ticker = {r["ticker"]: r for r in ownership_rows}

    # --- adaylari kur ---
    base_candidates = {
        u["ticker"]: _build_base_candidate(u, fundamentals_by_ticker[u["ticker"]], piotroski_by_ticker,
                                            sloan_by_ticker, catalyst_by_ticker, ownership_by_ticker)
        for u in eligible
    }

    macro = regime_result["snapshot"]

    long_term_candidates = []
    short_term_candidates = []

    all_lt_for_peers = [dict(c) for c in base_candidates.values()]
    for t, base in base_candidates.items():
        price_rows = prices_by_ticker[t]
        if not price_rows:
            continue
        last = price_rows[-1]
        current_price = last["close"]

        # --- uzun vade: target_price_engine ---
        lt = dict(base)
        lt["entry_price"] = current_price
        lt_target = targets_mod.compute_long_term_target(lt, all_lt_for_peers)
        lt["target_price"] = lt_target["target_price"]
        if lt["target_price"] is None:
            continue
        hurdle_lt = hurdle_mod.compute_all(current_price, lt["target_price"], 180, macro)
        lt.update(hurdle_lt)
        lt["horizon_days"] = 180
        lt["stop_loss"] = None
        beta_lt = beta_hurdle_mod.calculate_beta_adjusted_hurdle(
            as_of_date, t, price_rows, macro["bond_2y_pct"], hurdle_lt["expected_roi_pct"]
        )
        lt["excess_over_beta_hurdle_pct"] = beta_lt["excess_over_beta_hurdle_pct"]
        lt["beta_60_120d"] = beta_lt["beta_60_120d"]

        div_sustain = div_sustain_mod.check_dividend_sustainability(as_of_date, t, base)
        gordon_row = gordon_mod.calculate_gordon_reference(
            as_of_date, t, base.get("dividend_per_share_ttm"), macro["bond_2y_pct"],
            div_sustain["dividend_streak_years"], bool(div_sustain["passes_sustainability"]),
        )
        lt["gordon"] = gordon_row
        lt["dividend_sustainability"] = div_sustain
        lt["bucket"] = "long_term"
        lt["events"] = events_by_ticker.get(t, [])
        long_term_candidates.append(lt)

        # --- kisa vade: yalnizca ownership.short_term_rejected degilse ---
        atr20, sma20 = last.get("atr20"), last.get("sma20")
        if base.get("_short_term_rejected") or not atr20 or not sma20:
            continue
        st = dict(base)
        short_target = targets_mod.compute_short_term_target(current_price, atr20, sma20)
        st.update(short_target)
        st["volume_ratio_20d"] = last.get("volume_ratio_20d")
        hurdle_st = hurdle_mod.compute_all(short_target["entry_price"], short_target["target_price"], 20, macro)
        st.update(hurdle_st)
        # beta_metrics tablosunda (as_of_date, ticker) TEK bir satir vardir (spec:
        # database_schema.constraints); hurdle_rate_beta_adjusted_pct zaten ufuktan
        # bagimsiz (yillik) bir degerdir. Bu yuzden excess_over_beta_hurdle_pct de
        # gunluk TEK bir referans (uzun vade beklenen getirisi) uzerinden hesaplanir
        # ve kisa vade bolumunde AYNI deger bilgi amacli tekrar gosterilir.
        st["excess_over_beta_hurdle_pct"] = lt["excess_over_beta_hurdle_pct"]
        st["bucket"] = "short_term"
        short_term_candidates.append(st)

    all_candidates = long_term_candidates + short_term_candidates

    # --- ownership_z (kesitsel, bucket ici) ---
    for bucket_list in (long_term_candidates, short_term_candidates):
        for c in bucket_list:
            c["ownership_z"] = ownership_mod.compute_ownership_z(c, bucket_list)

    # --- scoring (hard_filters + final_score + candidate_state) ---
    as_of_date_cutoff = as_of_date
    scored = scoring_mod.score_candidates(as_of_date, all_candidates, as_of_date_cutoff)

    # --- concentration_check + correlation_diagnostic (yalnizca gecen adaylar uzerinde) ---
    passing = [c for c in scored if c["candidate_state"] not in ("NO_ACTION", "QUARANTINE")]
    concentration_warnings = concentration_mod.check_concentration(passing)
    correlation_mod.compute_correlation_flags(as_of_date, {c["ticker"]: prices_by_ticker[c["ticker"]] for c in passing})

    # --- predictions kaydi + thesis_invalidation kosullari ---
    _persist_predictions_and_invalidation(as_of_date, passing)

    # --- payload (decision_diff_engine dahil, bkz. core/payload.py) ---
    payload = payload_mod.build_report_payload(as_of_date)
    decision_diff = payload["decision_diff"]

    # --- thesis_card ---
    lt_display = []
    for c in long_term_candidates:
        if c["candidate_state"] in ("NO_ACTION", "QUARANTINE"):
            continue
        card = thesis_mod.build_thesis_card(c)
        lt_display.append({**c, **card, "upcoming_events": c.get("events", [])})

    filtered_candidates = [c for c in scored if c["candidate_state"] == "NO_ACTION"]
    evaluation_summary = payload["evaluation_summary"]

    context = {
        "as_of_date": as_of_date,
        "regime": regime_result["snapshot"] | {"as_of_date": as_of_date},
        "regime_taxonomy_tag": taxonomy["display_tag"],
        "decision_diff": decision_diff,
        "concentration_warnings": concentration_warnings,
        "long_term_candidates": lt_display,
        "short_term_candidates": [c for c in short_term_candidates if c["candidate_state"] not in ("NO_ACTION", "QUARANTINE")],
        "filtered_candidates": filtered_candidates,
        "unscored_count": payload["unscored_count"],
        "no_action_today": payload["no_action_today"],
        "invalidation_triggered": payload["invalidation_triggered"],
        "evaluation_summary": evaluation_summary,
        "weights": payload["weights"],
    }

    html_content = report_render.render_newsletter(context)
    validation = report_validate.validate_report(html_content, payload)

    email_sent = False
    error_message = None
    if validation["is_valid"]:
        email_sent = _dispatch(as_of_date, html_content, payload)
    else:
        error_message = f"validation_gate basarisiz: orphan={validation['orphan_numbers'][:10]} banned={validation['banned_claims_found']}"

    # --- evaluate_past_predictions + thesis_invalidation_monitor (kosunun sonunda) ---
    # Bu, BIR SONRAKI kosunun payload'unun okuyacagi outcomes/invalidation_checks
    # tablolarini gunceller (bkz. core/evaluate.py dosya-basi notu).
    post_run_evaluation = evaluate_mod.evaluate_past_predictions(as_of_date)
    triggered = invalidation_mod.check_thesis_invalidation(as_of_date)

    run_level_state = scoring_mod.run_level_state(scored)
    _persist_run(run_id, as_of_date, "completed" if validation["is_valid"] else "validation_failed",
                 run_level_state, started_at, error_message, email_sent=email_sent)

    return {
        "status": "completed", "as_of_date": as_of_date, "run_level_state": run_level_state,
        "validation": validation, "email_sent": email_sent, "n_candidates_scored": len(scored),
        "invalidation_triggered": triggered, "post_run_evaluation": post_run_evaluation,
    }


def _persist_predictions_and_invalidation(as_of_date: str, passing_candidates: list[dict]) -> None:
    rows = []
    for c in passing_candidates:
        rationale_hash = hashlib.sha256(
            f"{c['ticker']}|{c['bucket']}|{c.get('final_score')}|{as_of_date}".encode()
        ).hexdigest()[:16]
        rows.append({
            "as_of_date": as_of_date, "ticker": c["ticker"], "bucket": c["bucket"],
            "entry_price": c["entry_price"], "target_price": c["target_price"],
            "stop_loss": c.get("stop_loss"), "horizon_days": c["horizon_days"],
            "expected_roi_pct": c["expected_roi_pct"], "hurdle_rate_pct": c["hurdle_rate_pct"],
            "excess_over_hurdle_pct": c["excess_over_hurdle_pct"], "real_return_pct": c["real_return_pct"],
            "usd_return_pct": c["usd_return_pct"], "rationale_hash": rationale_hash,
        })
        invalidation_mod.create_invalidation_condition(as_of_date, c["ticker"], "excess_over_hurdle_pct", "<", 0)
        if c.get("piotroski_normalized_score") is not None:
            invalidation_mod.create_invalidation_condition(
                as_of_date, c["ticker"], "piotroski_normalized_score", "<", 0.3
            )

    if rows:
        conn = db.get_connection()
        try:
            conn.executemany(
                """INSERT INTO predictions (as_of_date, ticker, bucket, entry_price, target_price,
                   stop_loss, horizon_days, expected_roi_pct, hurdle_rate_pct, excess_over_hurdle_pct,
                   real_return_pct, usd_return_pct, rationale_hash)
                   VALUES (:as_of_date, :ticker, :bucket, :entry_price, :target_price, :stop_loss,
                           :horizon_days, :expected_roi_pct, :hurdle_rate_pct, :excess_over_hurdle_pct,
                           :real_return_pct, :usd_return_pct, :rationale_hash)""",
                rows,
            )
            conn.commit()
        finally:
            conn.close()


def _dispatch(as_of_date: str, html_content: str, payload: dict) -> bool:
    """delivery kanali: SMTP, ek olarak payload.json (spec: delivery.attachments)."""
    import json
    import os
    import re
    from pathlib import Path

    reports_dir = Path(__file__).resolve().parent / "data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    html_path = reports_dir / f"{as_of_date}.html"
    payload_path = reports_dir / f"{as_of_date}_payload.json"
    html_path.write_text(html_content, encoding="utf-8")
    payload_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    smtp_vars = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "MAIL_TO", "MAIL_FROM"]
    if not all(os.environ.get(v) for v in smtp_vars):
        print(f"[dispatch] SMTP env degiskenleri eksik, e-posta gonderilmedi. "
              f"HTML kaydedildi: {html_path}, payload: {payload_path}")
        return False

    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    # MAIL_TO ';' veya ',' ile ayrilmis birden fazla adres icerebilir; e-posta
    # basliklari virgul bekler ve send_message alicilari "To" basligindan
    # cikarir, bu yuzden hem basligi normalize ediyor hem de alicilari acikca
    # to_addrs olarak veriyoruz (basliktaki bicim ne olursa olsun teslimat
    # garanti altina alinsin diye).
    recipients = [addr.strip() for addr in re.split(r"[;,]", os.environ["MAIL_TO"]) if addr.strip()]

    msg = MIMEMultipart()
    msg["Subject"] = f"BIST Tarama Bulteni - {as_of_date}"
    msg["From"] = os.environ["MAIL_FROM"]
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    attachment = MIMEApplication(payload_path.read_bytes(), Name="payload.json")
    attachment["Content-Disposition"] = 'attachment; filename="payload.json"'
    msg.attach(attachment)

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"])) as server:
        server.starttls()
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        server.send_message(msg, to_addrs=recipients)
    return True


def _persist_run(run_id: str, as_of_date: str, status: str, run_level_state: str, started_at: str,
                  error_message: str | None, email_sent: bool = False) -> None:
    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO runs (run_id, as_of_date, status, run_level_state, started_at, finished_at,
               email_sent, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(as_of_date) DO UPDATE SET
                 status=excluded.status, run_level_state=excluded.run_level_state,
                 finished_at=excluded.finished_at, email_sent=excluded.email_sent,
                 error_message=excluded.error_message""",
            (run_id, as_of_date, status, run_level_state, started_at, datetime.now(timezone.utc).isoformat(),
             int(email_sent), error_message),
        )
        conn.commit()
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="BIST AI Investment Screener - gunluk kosu")
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    parser.add_argument("--min-volume-tl", type=float, default=10_000_000)
    args = parser.parse_args()

    result = run(args.as_of_date, min_volume_tl=args.min_volume_tl)
    print(result)
    if result.get("status") == "halted":
        sys.exit(1)


if __name__ == "__main__":
    main()
