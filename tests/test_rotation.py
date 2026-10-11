from core import rotation


def _c(t, z, **kw):
    return {"ticker": t, "bucket": "long_term", "candidate_state": "WATCHLIST", "confidence": "high",
            "valuation_z": z, **kw}


def test_select_top_quintile_and_exclusions():
    cands = [_c(f"T{i}", float(i)) for i in range(10)]
    cands += [_c("Q", 99.0, candidate_state="QUARANTINE"), _c("P", 98.0, confidence="insufficient_peers"),
              _c("N", None), {**_c("S", 97.0), "bucket": "short_term"}]
    top = rotation.select_top(cands)
    assert [h["ticker"] for h in top] == ["T9", "T8"]
    assert top[0]["rank_pct"] == 0.1


def test_monthly_rebalance_reused_within_month_and_diff(temp_db):
    from core import db
    db.init_db()
    m1 = [_c(f"T{i}", float(i)) for i in range(10)]
    r1 = rotation.monthly_rotation("2026-09-01", m1)
    assert [h["ticker"] for h in r1["buy"]] == ["T9", "T8"] and r1["sell"] == []
    # ayni ay: yeni skorlar listeyi DEGISTIRMEZ
    m1b = [_c(f"T{i}", float(-i)) for i in range(10)]
    r1b = rotation.monthly_rotation("2026-09-15", m1b)
    assert r1b["rebalance_date"] == "2026-09-01" and [h["ticker"] for h in r1b["buy"]] == ["T9", "T8"]
    # yeni ay: T9 kalir, T8 cikar, T7 girer
    m2 = [_c(f"T{i}", float(i)) for i in range(10)]
    m2[8]["valuation_z"] = 0.5
    r2 = rotation.monthly_rotation("2026-10-01", m2)
    assert [h["ticker"] for h in r2["hold"]] == ["T9"]
    assert [h["ticker"] for h in r2["buy"]] == ["T7"]
    assert r2["sell"] == ["T8"] and r2["previous_rebalance_date"] == "2026-09-01"


def test_financials_excluded_like_tested_panel():
    # Test edilen panel finansallari icermiyordu (pit_panel.FINANCIAL_SECTORS);
    # 2026-10-10 canli kosusunda GARAN gibi bankalar puanlaniyordu.
    cands = [_c(f"T{i}", float(i), sector="İmalat") for i in range(10)]
    cands += [_c("BANK", 99.0, sector="Bankacılık"), _c("INS", 98.0, sector="Sigorta"),
              _c("HOLD", 97.0, sector="Holding")]
    top = rotation.select_top(cands)
    assert [h["ticker"] for h in top] == ["HOLD", "T9"]
    assert rotation.is_financial({"sector": "Faktoring"}) and not rotation.is_financial({"sector": "Holding"})


def test_untested_financials_listed_separately(temp_db):
    from core import db
    from report.render import render_mobile_newsletter
    from report.validate import find_orphan_numbers
    db.init_db()
    cands = [_c(f"T{i}", float(i), sector="İmalat") for i in range(10)]
    cands += [_c(f"B{i}", float(i), sector="Bankacılık") for i in range(5)]
    r = rotation.monthly_rotation("2026-10-01", cands)
    assert all(not h["ticker"].startswith("B") for h in r["buy"])
    assert r["untested_financials"] == [{"ticker": "B4", "sector": "Bankacılık"}]
    ctx = {"as_of_date": "2026-10-01", "long_term_candidates": [], "short_term_candidates": [],
           "long_term_display_count": 0, "short_term_display_count": 0, "sector_rotation": [],
           "no_action_today": True, "rotation": r, "portfolio_correlation": {}}
    html = render_mobile_newsletter(ctx)
    assert "test edilmedi" in html and "B4" in html
    assert find_orphan_numbers(html, {"rotation": r}) == []
