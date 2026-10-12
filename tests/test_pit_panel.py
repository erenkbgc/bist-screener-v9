"""pit_panel.merge_statement_batches: tekrarlanan satir adlari batch sayisiyla
katlanmamali (borsapy 0.11 join hatasi, 15 batch'te 2^15 kopya)."""
import pandas as pd

from core import pit_panel


def _batch(cols, rows):
    idx = pd.Index([r[0] for r in rows], name="Item")
    return pd.DataFrame([r[1] for r in rows], index=idx, columns=cols)


def test_duplicate_labels_not_multiplied():
    batches = [
        _batch([f"{y}Q2"], [("  Finansal Borçlar", [10.0 + y]), ("Toplam", [1.0]), ("  Finansal Borçlar", [20.0 + y])])
        for y in range(2010, 2025)
    ]
    merged = pit_panel.merge_statement_batches(batches)
    assert len(merged) == 3
    assert merged.shape[1] == 15
    fd = pit_panel._pick(merged, ("Finansal Borçlar",), sum_dupes=True)
    assert fd["2024Q2"] == 10.0 + 2024 + 20.0 + 2024


def test_first_occurrence_kept_in_order():
    a = _batch(["2026Q2"], [("  Diğer Alacaklar", [1.0]), ("  Diğer Alacaklar", [2.0])])
    b = _batch(["2025Q2"], [("  Diğer Alacaklar", [3.0]), ("  Diğer Alacaklar", [4.0])])
    s = pit_panel._pick(pit_panel.merge_statement_batches([a, b]), ("Diğer Alacaklar",), sum_dupes=False)
    assert s["2026Q2"] == 1.0 and s["2025Q2"] == 3.0


def test_item_missing_in_old_template():
    new = _batch(["2026Q2"], [("A", [1.0]), ("  Kullanım Hakkı Varlıkları", [5.0])])
    old = _batch(["2014Q2"], [("A", [2.0])])
    merged = pit_panel.merge_statement_batches([new, old, pd.DataFrame()])
    assert len(merged) == 2
    assert pd.isna(merged.loc["  Kullanım Hakkı Varlıkları", "2014Q2"])


def test_empty():
    assert pit_panel.merge_statement_batches([]).empty


def test_add_usd_returns_converts_and_excess():
    import pandas as pd
    from core import pit_panel

    daily = pd.DataFrame({
        "date": pd.to_datetime(["2020-01-31", "2020-02-28", "2020-07-31"]),
        "usdtry": [6.0, 6.6, 6.0],
        "xu100": [1000.0, 1100.0, 1000.0],
    })
    m = pit_panel.monthly_market(daily)
    f = pd.DataFrame({"date": pd.to_datetime(["2020-01-31"]), "ticker": ["X"],
                      "fwd_ret_1m": [0.21], "fwd_ret_6m": [0.0]})
    out = pit_panel.add_usd_returns(f, m)
    # TL +21%, kur +10% -> USD +10%; XU100 +10% -> fazla getiri 11 puan
    assert abs(out.loc[0, "fwd_ret_1m_usd"] - 0.10) < 1e-9
    assert abs(out.loc[0, "fwd_ret_1m_xs"] - 0.11) < 1e-9
    assert abs(out.loc[0, "fwd_ret_6m_usd"]) < 1e-9


def test_add_usd_returns_missing_month_is_nan():
    import pandas as pd
    from core import pit_panel

    daily = pd.DataFrame({"date": pd.to_datetime(["2020-01-31"]), "usdtry": [6.0], "xu100": [1000.0]})
    f = pd.DataFrame({"date": pd.to_datetime(["2020-01-31"]), "ticker": ["X"],
                      "fwd_ret_1m": [0.2], "fwd_ret_6m": [0.3]})
    out = pit_panel.add_usd_returns(f, pit_panel.monthly_market(daily))
    assert out["fwd_ret_1m_usd"].isna().all()


def test_kap_report_dates_maps_period_and_session_close():
    import pandas as pd
    from core import pit_panel
    arc = pd.DataFrame([
        # Q1 2023, seans icinde -> ayni gun
        {"disclosureClass": "FR", "subject": "Finansal Rapor", "ruleType": "3 Aylık",
         "published_at": pd.Timestamp("2023-05-02 15:00"), "stock_code": "AAA"},
        # ayni donem daha gec duzeltme: ilk yayin sayilir
        {"disclosureClass": "FR", "subject": "Finansal Rapor", "ruleType": "3 Aylık",
         "published_at": pd.Timestamp("2023-06-20 10:00"), "stock_code": "AAA"},
        # Yillik 2024, kapanistan sonra -> ertesi gun
        {"disclosureClass": "FR", "subject": "Finansal Rapor", "ruleType": "Yıllık",
         "published_at": pd.Timestamp("2025-03-11 20:29"), "stock_code": "AAA"},
        # faaliyet raporu sayilmaz
        {"disclosureClass": "FR", "subject": "Faaliyet Raporu (Konsolide)", "ruleType": "Yıllık",
         "published_at": pd.Timestamp("2025-02-01 10:00"), "stock_code": "AAA"},
    ])
    d = pit_panel.kap_report_dates(arc).set_index("period")
    assert d.loc["2023Q1", "kap_available_at"] == pd.Timestamp("2023-05-02")
    assert d.loc["2024Q4", "kap_available_at"] == pd.Timestamp("2025-03-12")
    assert len(d) == 2

    q = pd.DataFrame({"ticker": ["AAA", "AAA"], "period": ["2023Q1", "2023Q2"],
                      "available_at": [pd.Timestamp("2023-06-14"), pd.Timestamp("2023-09-13")]})
    b = pit_panel.apply_report_dates(q, d.reset_index())
    assert list(b["available_at"]) == [pd.Timestamp("2023-05-02"), pd.Timestamp("2023-09-13")]
    assert list(b["available_source"]) == ["kap", "assumed"]
    c = pit_panel.apply_report_dates(q, d.reset_index(), strict=True)
    assert list(c["period"]) == ["2023Q1"]
