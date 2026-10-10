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
