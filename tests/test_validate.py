"""validation_gate testi, banned_claims testi."""
from report.validate import validate_report, find_orphan_numbers, find_banned_claims


def _minimal_payload():
    return {"scores": [{"final_score": 1.23, "peer_n": 10}], "as_of_date": "2026-09-10"}


def test_orphan_number_detected():
    html = "<div>Hedef fiyat: 999.99</div>"
    orphans = find_orphan_numbers(html, _minimal_payload())
    assert "999.99" in orphans


def test_number_present_in_payload_is_not_orphan():
    html = "<div>final_score: 1.23, peer_n: 10</div>"
    orphans = find_orphan_numbers(html, _minimal_payload())
    assert orphans == []


def test_iso_dates_are_not_treated_as_orphan_numbers():
    html = "<div>2026-09-10</div>"
    orphans = find_orphan_numbers(html, _minimal_payload())
    assert orphans == []


def test_negative_number_inside_word_not_false_positive():
    html = '<meta charset="utf-8">'
    orphans = find_orphan_numbers(html, _minimal_payload())
    assert orphans == []


def test_banned_claims_detected():
    html = "<p>Bu strateji kanitlanmis edge saglar.</p>"
    found = find_banned_claims(html)
    assert "kanitlanmis edge" in found


def test_clean_report_is_valid():
    html = "<div>final_score: 1.23</div>"
    result = validate_report(html, _minimal_payload())
    assert result["is_valid"] is True


def test_report_with_orphan_and_banned_claim_invalid():
    html = "<div>999.99 kanitlanmis edge</div>"
    result = validate_report(html, _minimal_payload())
    assert result["is_valid"] is False
    assert result["orphan_numbers"]
    assert result["banned_claims_found"]
