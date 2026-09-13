"""idempotency testi: ayni as_of_date icin ikinci kosu e-posta atmaz (tekrar islenmez)."""
import run as run_mod


def test_second_run_skipped_when_already_email_sent(temp_db, monkeypatch):
    # ilk kosu: gercek pipeline calisir (mock veri ile), SMTP yok -> email_sent=False
    result1 = run_mod.run("2026-09-10")
    assert result1["status"] == "completed"
    # regression: validation_gate her zaman gecmeli (bkz. volume_ratio_20d'nin
    # hicbir tabloya persist edilmedigi icin orphan-number sayilip e-postayi
    # SESSIZCE dusuren gecmis bug -- canli veriyle bulundu, bkz. core/db.py::
    # predictions.volume_ratio_20d). Bu assert olmadan boyle bir regresyon
    # status=="completed" kalirken email_sent=False'a sessizce duserdi.
    assert result1["validation"]["is_valid"] is True, result1["validation"]

    # e-posta gonderilmis gibi isaretle
    from core import db
    conn = db.get_connection()
    conn.execute("UPDATE runs SET email_sent=1 WHERE as_of_date=?", ("2026-09-10",))
    conn.commit()
    conn.close()

    result2 = run_mod.run("2026-09-10")
    assert result2["status"] == "skipped_idempotent"
