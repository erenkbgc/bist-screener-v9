"""KAP metin cikarimi ve toplu-duyuru gurultu filtresi (model gerektirmez)."""
from core.kap_sentiment import extract_disclosure_text
from core.live_data import _categorize_kap_title


def test_bulk_mkk_trading_ban_notice_is_noise_not_company_ban():
    # KAP 1666319: yasakli YATIRIMCILARIN paylari -- ~100 sirkete eklenir.
    cat, sign = _categorize_kap_title("SPK İşlem Yasağı Nedeniyle Pay Duyurusu")
    assert cat == "market_notice_noise" and sign == "neutral"
    assert _categorize_kap_title("Temerrüt İşlemi")[0] == "market_notice_noise"


def test_unclassified_title_keeps_neutral_sign():
    assert _categorize_kap_title("Özel Durum Açıklaması (Genel)") == ("material_event_other", "neutral")


def test_extract_disclosure_text_strips_form_fields():
    html = ("<html><body><div>Özet Bilgi Uçak Siparişleri Yapılan Açıklama Güncelleme mi? Evet "
            "oda_ExplanationTextBlock| Yapılan Açıklama Düzeltme mi? Hayır (No) "
            "150 adet B737MAX uçağının satın alınmasına karar verilmiştir. "
            "Kamuya duyurulur. oda_Other| x</div><script>var a=1</script></body></html>")
    out = extract_disclosure_text(html)
    assert out["summary"] == "Uçak Siparişleri"
    assert "B737MAX" in out["body"]
    assert "Düzeltme mi" not in out["body"]
    assert "Kamuya" not in out["body"]
