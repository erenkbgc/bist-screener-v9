import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# KRITIK: run.py import edildiginde (bircok test modulunun tepesinde
# `import run as run_mod` var) `load_dotenv()`'i kosulsuz cagirir. Gelistirme
# makinesindeki .env dosyasi CANLI kosular icin BIST_DATA_MODE=live tutuyor
# olabilir -- python-dotenv zaten os.environ'da olan bir degiskeni EZMEZ, bu
# yuzden burada .env YUKLENMEDEN ONCE (conftest.py test toplama surecinin en
# basinda, herhangi bir test modulu import edilmeden calisir) mock'u acikca
# sabitliyoruz. Bu yapilmazsa testler SESSIZCE canli moda gecip run.py'nin
# TUM (~800 ticker'lik) evrenine gercek ag istekleri atar -- kanitlandi:
# tests/test_idempotency.py::test_second_run_skipped_when_already_email_sent
# bu yuzden dakikalarca "askida" kaliyordu (faulthandler stack dump'i
# core/live_data.py::live_universe icinde gercek Is Yatirim/TradingView
# websocket cagrilarinda oldugunu gosterdi) -- onceki oturumlarda "full test
# suite 120sn'de timeout oluyor" olarak not dusulen gizemin kok nedeni buydu.
os.environ["BIST_DATA_MODE"] = "mock"

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
