"""fintables sektor eslemesinin _classify_sector ile dogru (ratio_profile, regulator)
ciftine dustugunu dogrular. Ag cagrisi yapmaz (config/fintables_ticker_sektor.json
salt-okunur bir sabit dosyadir)."""
from core.live_data import _classify_sector, _fintables_sector_map


def test_fintables_map_loads_known_tickers():
    m = _fintables_sector_map()
    assert m["GARAN"] == "Bankacılık"
    assert m["EREGL"] == "Ana Metal"
    assert len(m) > 500


def test_bank_like_categories_map_to_bddk():
    for sektor in ["Bankacılık", "Faktoring", "Finansal Kiralama", "Sigorta",
                   "Emeklilik", "Varlık Yönetimi", "Tasarruf Finansman", "Aracı Kurum"]:
        assert _classify_sector(sektor) == ("bank", "BDDK")


def test_gayrimenkul_maps_to_reit():
    assert _classify_sector("Gayrimenkul") == ("reit", "SPK_TFRS")


def test_holding_and_investment_trusts_map_to_holding():
    for sektor in ["Holding", "Girişim Sermayesi Yat. Ort.", "Menkul Kıymet Yat. Ort."]:
        assert _classify_sector(sektor) == ("holding", "SPK_TFRS")


def test_default_falls_back_to_industrial():
    assert _classify_sector("İmalat") == ("industrial", "SPK_TFRS")
    assert _classify_sector(None) == ("industrial", "SPK_TFRS")
