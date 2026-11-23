import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fetch_old_tr as f  # noqa: E402


class FakeResp:
    def __init__(self, v): self.v = v
    def raise_for_status(self): pass
    def json(self): return {"value": self.v}


class FakeSession:
    def __init__(self): self.calls = []
    def get(self, url, params, headers, timeout):
        self.calls.append((url.rsplit("/", 1)[-1], params))
        if url.endswith("HisseTekil"):
            return FakeResp([{"HGDG_TARIH": "02-01-2001", "SERMAYE": 1.0, "PD": 2.0}])
        return FakeResp([{"itemCode": "2N", "value1": "5", "value2": None, "value3": "", "value4": 0}])


def test_params_four_quarters():
    p = f.malitablo_params("THYAO", 2009, "XI_29")
    assert [p[f"period{i}"] for i in range(1, 5)] == [3, 6, 9, 12]
    assert {p[f"year{i}"] for i in range(1, 5)} == {2009}


def test_filled_quarters():
    assert f.filled_quarters([{"value1": "1", "value2": None, "value3": "", "value4": 0}]) == [1]
    assert f.filled_quarters([]) == []


def test_fetch_one_skips_pre2008_and_bank_group(monkeypatch):
    monkeypatch.setattr(f, "SLEEP", 0)
    s = FakeSession()
    d = f.fetch_one(s, "AKBNK", 2001, 2009)
    years = [p["year1"] for e, p in s.calls if e == "MaliTablo"]
    assert years == [2008, 2009]
    assert all(p["financialGroup"] == "UFRS" for e, p in s.calls if e == "MaliTablo")
    assert d["px"][0]["SERMAYE"] == 1.0
