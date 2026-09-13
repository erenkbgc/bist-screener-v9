import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core import db


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Her teste izole, gecici bir SQLite veritabani verir."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    # run.py::_dispatch DB'den bagimsiz olarak HTML/payload dosyalarini
    # REPORTS_DIR'e yazar -- bunu da tmp_path'e yonlendirmezsek her test
    # kosusu gercek data/reports/ klasorunu mock veriyle kirletir (bkz.
    # run.py::REPORTS_DIR yorumu).
    import run as run_mod
    monkeypatch.setattr(run_mod, "REPORTS_DIR", tmp_path / "reports")

    yield db_path
