"""Deneysel LLM etiketi: sabit sema dogrulamasi, hata toleransi, panelde ayri gosterim."""
import json
import json as _json
from datetime import date

from core import db, kap_api, kap_llm, kap_red_flag_panel as panel

AS_OF = "2026-10-10"
ODA = "Özel Durum Açıklaması (Genel)"


def test_parse_drops_unknown_ids_and_categories():
    content = json.dumps({"items": [
        {"id": 1, "category": "insolvency"},
        {"id": 2, "category": "bankruptcy_risk"},   # listede yok
        {"id": 99, "category": "none"},             # sorulmayan id
        {"id": "3", "category": "none"},
        {"category": "insolvency"},
    ]})
    assert kap_llm.parse(content, {1, 2, 3}) == {1: "insolvency", 3: "none"}
    assert kap_llm.parse("OK", {1}) == {}
    assert kap_llm.parse('{"items": "x"}', {1}) == {}
    # Bazi modeller JSON'u kod blogu icinde dondurur.
    assert kap_llm.parse('```json\n{"items": [{"id": 1, "category": "none"}]}\n```', {1}) == {1: "none"}


def test_prompt_lists_only_fixed_categories():
    for c in kap_llm.CATEGORIES:
        assert f"- {c}:" in kap_llm.SYSTEM_PROMPT
    assert len(kap_llm.PROMPT_HASH) == 12


class _Resp:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    text = "rate limit"

    def json(self):
        return self.payload


class _FakeHttp:
    """Her bildirimi 'lawsuit_or_seizure' etiketler; fail_after istekten sonra 429."""
    def __init__(self, fail_after=None):
        self.calls, self.fail_after = 0, fail_after

    def post(self, url, headers=None, timeout=None, json=None):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            return _Resp({}, 429)
        items = [{"id": d["id"], "category": "lawsuit_or_seizure"} for d in _json.loads(json["messages"][1]["content"])]
        return _Resp({"choices": [{"message": {"content": _json.dumps({"items": items})}}]})

    def close(self):
        pass


def _seed(monkeypatch, n):
    d = date(2026, 9, 1)
    rows = [{"disclosureIndex": 100 + i, "publishDate": f"{d:%d.%m.%Y} 10:00:00", "stockCodes": "AAA",
             "subject": ODA, "summary": f"Tedarikci ile yasanan anlasmazlik {i}"} for i in range(n)]
    monkeypatch.setattr(kap_api, "fetch_range", lambda http, fr, to, **kw: [r for r in rows if fr <= d <= to])
    panel.refresh(AS_OF, http=object(), sleep_s=0)


def test_no_token_skips(temp_db, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert kap_llm.label_pending(["AAA"], "2026-04-01")["error"] == "GROQ_API_KEY yok"


def test_labels_stored_and_shown_separately(temp_db, monkeypatch):
    from report.render import render_mobile_newsletter
    from report.validate import find_orphan_numbers
    monkeypatch.setenv("GROQ_API_KEY", "x")
    _seed(monkeypatch, 3)
    out = kap_llm.label_pending(["AAA"], "2026-04-01", http=_FakeHttp())
    assert out["labeled"] == 3 and out["error"] is None
    # Ikinci kosuda bekleyen yok.
    assert kap_llm.pending(["AAA"], "2026-04-01", 100) == []

    kap = panel.build_panel(AS_OF, ["AAA"], llm=out)
    h = kap["holdings"][0]
    assert h["categories"] == [] and h["llm_categories"][0]["category"] == "lawsuit_or_seizure"
    assert h["llm_categories"][0]["count"] == 3

    rotation = {"rebalance_date": "2026-10-01", "buy": [{"ticker": "AAA"}], "hold": [], "sell": [],
                "n_holdings": 23, "top_pct": 20.0}
    ctx = {"as_of_date": AS_OF, "long_term_candidates": [], "short_term_candidates": [],
           "long_term_display_count": 0, "short_term_display_count": 0, "sector_rotation": [],
           "no_action_today": True, "rotation": rotation, "portfolio_correlation": {}, "kap_red_flags": kap}
    html = render_mobile_newsletter(ctx)
    assert "Deneysel LLM etiketi" in html
    assert find_orphan_numbers(html, {"rotation": rotation, "kap_red_flags": kap}) == []


def test_rate_limit_keeps_partial_labels(temp_db, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    _seed(monkeypatch, 45)  # 3 istek (20 + 20 + 5)
    out = kap_llm.label_pending(["AAA"], "2026-04-01", http=_FakeHttp(fail_after=1))
    assert out["labeled"] == 20 and "429" in out["error"]
    assert len(db.query("SELECT * FROM kap_llm_labels")) == 20


def test_label_rows_carry_model_and_prompt(temp_db, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    _seed(monkeypatch, 1)
    kap_llm.label_pending(["AAA"], "2026-04-01", http=_FakeHttp())
    r = db.query("SELECT model, prompt_hash FROM kap_llm_labels")[0]
    assert r["model"] == kap_llm.MODEL and r["prompt_hash"] == kap_llm.PROMPT_HASH


def test_retry_wait_parsed_from_header_or_body():
    assert kap_llm.retry_wait_s({"retry-after": "7"}, "") == 7.0
    assert kap_llm.retry_wait_s({}, "Please try again in 12.4575s. Need more") == 12.4575
    assert kap_llm.retry_wait_s(None, "Please try again in 7m12.5s.") == 432.5
    assert kap_llm.retry_wait_s({}, "rate limit") is None


class _TpmHttp(_FakeHttp):
    """Her 2 istekten sonra bir kez 429 + kisa bekleme (dakikalik token limiti)."""
    def __init__(self, wait_text="Please try again in 12.4s."):
        super().__init__()
        self.wait_text, self.ok_since_429 = wait_text, 0

    def post(self, url, headers=None, timeout=None, json=None):
        if self.ok_since_429 == 2:
            self.ok_since_429 = 0
            r = _Resp({}, 429)
            r.text = self.wait_text
            return r
        self.ok_since_429 += 1
        return super().post(url, headers=headers, timeout=timeout, json=json)


def test_short_rate_limit_waits_and_labels_all(temp_db, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    _seed(monkeypatch, 85)  # 5 istek
    waits = []
    out = kap_llm.label_pending(["AAA"], "2026-04-01", http=_TpmHttp(), sleep=waits.append)
    assert out["labeled"] == 85 and out["error"] is None
    assert waits == [13.4, 13.4]


def test_long_rate_limit_stops_without_waiting(temp_db, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    _seed(monkeypatch, 85)
    waits = []
    out = kap_llm.label_pending(["AAA"], "2026-04-01", http=_TpmHttp("Please try again in 7m12.5s."),
                                sleep=waits.append)
    assert out["labeled"] == 40 and "429" in out["error"] and waits == []
