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
    yield db_path
