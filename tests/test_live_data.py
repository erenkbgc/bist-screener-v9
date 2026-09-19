"""financial_institution_data_source: banka/sigorta (UFRS) sablonlarinin
gercek satir etiketleriyle (canli test: 2026-09-17, AKBNK/ANHYT) Piotroski/
fundamentals cikarimlarinin dogru calistigini, ag cagrisi yapmadan dogrular."""
import pandas as pd

from core import live_data as ld


def test_row_is_whitespace_tolerant():
    """UFRS sablonlari ayni satiri bazen bastaki/sondaki fazladan boslukla donduruyor
    (orn. ' AKTİF TOPLAMI') -- _row bunu normalize etmeli."""
    df = pd.DataFrame({"2025": [100.0]}, index=[" AKTİF TOPLAMI"])
    assert ld._val(ld._row(df, "AKTİF TOPLAMI")) == 100.0


def test_statements_cached_partial_fetch_survives_missing_cashflow(monkeypatch):
    """Banka/sigorta: bilanco/gelir tablosu cekilebilir ama nakit akis tablosu Is
    Yatirim'de HIC yok (DataNotAvailableError) -- tek bir tablonun basarisiz olmasi
    digerlerinin de atilmasina yol acmamali (eskiden tek try/except icindeydi)."""
    class FakeTicker:
        def get_balance_sheet(self, financial_group=None, **kw):
            return pd.DataFrame({"2025": [1.0]}, index=["AKTİF TOPLAMI"])

        def get_income_stmt(self, financial_group=None, **kw):
            return pd.DataFrame({"2025": [2.0]}, index=["23.1 Grubun Karı/Zararı"])

        def get_cashflow(self, financial_group=None, **kw):
            raise Exception("No financial data available for FAKEBANK")

    monkeypatch.setattr(ld, "_ticker_obj", lambda ticker: FakeTicker())
    bs, inc, cf = ld._statements_cached("FAKEBANK_TEST_1", "UFRS")
    assert bs is not None and inc is not None
    assert cf is None


def _bank_statements():
    bs = pd.DataFrame({"2025": [1_000_000.0, 100_000.0], "2024": [900_000.0, 80_000.0]},
                       index=["AKTİF TOPLAMI", "XVI. ÖZKAYNAKLAR"])
    inc = pd.DataFrame({"2025": [50_000.0], "2024": [30_000.0]},
                        index=["23.1 Grubun Karı/Zararı"])
    return bs, inc, None  # UFRS bankalar icin cashflow hic mevcut degil


def test_live_piotroski_raw_criteria_bank_partial_computability(monkeypatch):
    """Bankalarda 'Dönen Varlıklar'/'BRÜT KAR'/nakit akis kavramlari yok --
    yalnizca ROA seviyesi/degisimi (kriter 1, 3) hesaplanabilmeli, geri kalani
    (cfo/current ratio/margin/turnover/capital raise -- 2,4,5,6,7,8,9) None kalmali.
    financial_institution_data_source acceptance_test: criteria_computable > 0."""
    monkeypatch.setattr(ld, "_statements_cached", lambda ticker, fg=None: _bank_statements())
    raw = ld.live_piotroski_raw_criteria("AKBNK_TEST", "2026-09-17", ratio_profile="bank")

    computable = {k: v for k, v in raw.items() if v is not None}
    assert len(computable) > 0
    # ROA seviyesi pozitif (50000/1000000 > 0) ve ROA arttı (50000/1e6 > 30000/9e5)
    assert raw["criterion_1"] == 1
    assert raw["criterion_3"] == 1
    # nakit akis tablosu yok -> cfo tabanli kriterler hesaplanamaz
    assert raw["criterion_2"] is None
    assert raw["criterion_4"] is None
    assert raw["criterion_7"] is None
    # banka sablonunda 'Dönen Varlıklar'/'BRÜT KAR' kavramlari yok
    assert raw["criterion_6"] is None
    assert raw["criterion_8"] is None
    assert raw["criterion_9"] is None


def test_live_piotroski_raw_criteria_all_none_when_statements_unavailable(monkeypatch):
    monkeypatch.setattr(ld, "_statements_cached", lambda ticker, fg=None: (None, None, None))
    raw = ld.live_piotroski_raw_criteria("NODATA_TEST", "2026-09-17", ratio_profile="bank")
    assert all(v is None for v in raw.values())


def test_live_cashflow_for_sloan_returns_none_cfo_for_bank(monkeypatch):
    monkeypatch.setattr(ld, "_statements_cached", lambda ticker, fg=None: _bank_statements())
    result = ld.live_cashflow_for_sloan("AKBNK_TEST", "2026-09-17", 50_000.0, ratio_profile="bank")
    assert result["operating_cashflow_ttm"] is None
    assert result["average_total_assets"] == 950_000.0  # (1_000_000 + 900_000) / 2


def test_live_fundamentals_bank_computes_roa_roe_from_ufrs_labels(monkeypatch):
    monkeypatch.setattr(ld, "_statements_cached", lambda ticker, fg=None: _bank_statements())
    monkeypatch.setattr(ld, "_fast_info_cached", lambda ticker: {"pe_ratio": 5.0, "pb_ratio": 1.0,
                                                                   "market_cap": 1e9, "shares": 1e8})
    monkeypatch.setattr(ld, "_info_cached", lambda ticker: {})
    monkeypatch.setattr(ld, "_dividend_ttm", lambda ticker: 0.0)

    f = ld.live_fundamentals("AKBNK_TEST", "2026-09-17", "BDDK", "bank")
    assert f["roa"] == 5.0  # 50_000/1_000_000 * 100
    assert f["roe"] == 50.0  # 50_000/100_000 * 100
    # revenue/gross-profit kavrami bankalar icin yok -- uydurulmaz
    assert f["ev_sales"] is None


def test_live_fundamentals_reports_unknown_basis_when_statements_totally_unfetchable(monkeypatch):
    """dead_hard_filters_repair (v12 T0-2): bs VE inc ikisi de None ise (financial_group
    fallback'i dahil hicbir sablonda veri yok -- ornegin faktoring/leasing/tasarruf
    finansman/varlik yonetimi, bkz. non_bank_bddk_data_source_gap), live_fundamentals
    reporting_basis='unknown' SINYALI vermeli ki basis_guard/hard filter bunu
    yakalayabilsin. Eskiden bu sinyal hic uretilmiyordu."""
    monkeypatch.setattr(ld, "_statements_cached", lambda ticker, fg=None: (None, None, None))
    monkeypatch.setattr(ld, "_fast_info_cached", lambda ticker: {"pe_ratio": 5.0, "pb_ratio": 1.0,
                                                                   "market_cap": 1e9, "shares": 1e8})
    monkeypatch.setattr(ld, "_info_cached", lambda ticker: {})
    monkeypatch.setattr(ld, "_dividend_ttm", lambda ticker: 0.0)

    f = ld.live_fundamentals("ISFIN_TEST", "2026-09-17", "BDDK", "bank")
    assert f["reporting_basis"] == "unknown"


def test_live_fundamentals_stays_unresolved_when_at_least_one_statement_available(monkeypatch):
    """Yalnizca bilanco VEYA yalnizca gelir tablosu mevcut olsa bile (bankalarda
    nakit akis hic yok ama bu ikisi degil), reporting_basis unknown OLMAMALI --
    fundamentals.py'nin basis_guard'e gore regulator-bazli karar vermesine izin
    verilmeli (None doner)."""
    bs, inc, _ = _bank_statements()
    monkeypatch.setattr(ld, "_statements_cached", lambda ticker, fg=None: (bs, None, None))
    monkeypatch.setattr(ld, "_fast_info_cached", lambda ticker: {"pe_ratio": 5.0, "pb_ratio": 1.0,
                                                                   "market_cap": 1e9, "shares": 1e8})
    monkeypatch.setattr(ld, "_info_cached", lambda ticker: {})
    monkeypatch.setattr(ld, "_dividend_ttm", lambda ticker: 0.0)

    f = ld.live_fundamentals("PARTIAL_TEST", "2026-09-17", "BDDK", "bank")
    assert f["reporting_basis"] is None


def _fake_kap_disclosures(*rows):
    return pd.DataFrame(rows, columns=["Date", "Title", "URL"])


def test_live_financial_report_published_at_finds_real_lagged_disclosure(monkeypatch):
    """point_in_time_publication_lag: canli olcum (2026-09-19, FORTE) -- gercek
    'Finansal Rapor' bildirimi donem sonundan (2026-06-30) 37 gun sonra
    (2026-08-06) geldi. period_end doner DEGIL."""
    df = _fake_kap_disclosures(
        ("16.09.2026 10:32:56", "Pay Bazında Devre Kesici Bildirimi", "u1"),
        ("06.08.2026 18:19:25", "Finansal Rapor", "u2"),
        ("11.05.2026 18:11:29", "Finansal Rapor", "u3"),  # onceki donem, daha uzak
    )
    monkeypatch.setattr(ld, "_financial_report_disclosures_cached", lambda ticker: df)
    result = ld.live_financial_report_published_at("FORTE", "2026-06-30")
    assert result == "2026-08-06"


def test_live_financial_report_published_at_returns_none_when_no_disclosures(monkeypatch):
    monkeypatch.setattr(ld, "_financial_report_disclosures_cached", lambda ticker: None)
    assert ld.live_financial_report_published_at("ZZZZ", "2026-06-30") is None


def test_live_financial_report_published_at_ignores_out_of_window_matches(monkeypatch):
    """Donem sonundan 150 gunden fazla sonra (baska bir doneme ait olasi) veya
    ONCESINDE gelen 'Finansal Rapor' bildirimleri eslesmemeli."""
    df = _fake_kap_disclosures(
        ("01.01.2026 10:00:00", "Finansal Rapor", "u1"),  # period_end'den ONCE
        ("01.03.2027 10:00:00", "Finansal Rapor", "u2"),  # 150 gunden fazla sonra
    )
    monkeypatch.setattr(ld, "_financial_report_disclosures_cached", lambda ticker: df)
    assert ld.live_financial_report_published_at("FORTE", "2026-06-30") is None
