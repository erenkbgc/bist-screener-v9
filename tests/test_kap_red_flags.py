"""KAP kirmizi bayrak siniflandiricisi: ornekler KAP arsivindeki gercek
konu/ozet metinleri (data/research/kap_archive.parquet)."""
import pytest

from core.kap_red_flags import RED_FLAG_LABELS, classify

ODA = "Özel Durum Açıklaması (Genel)"


@pytest.mark.parametrize("subject,summary,expected", [
    (ODA, "Konkordato 41. Taksit Ödemesi", "insolvency"),
    (ODA, "Finansal Yeniden Yapılandırma Başvurusu Hakkında", "insolvency"),
    (ODA, "Finansal sektöre olan borçların yeniden yapılandırılması hakkında,", "insolvency"),
    ("TTK'nın 376. Maddesi Kapsamında Yapılan İşlemler", None, "insolvency"),
    ("İflas - İflas Ertelemeye İlişkin Bildirim", "", "insolvency"),
    (ODA, "Bağımsız Denetim Raporu Görüş Sayfasındaki Sürekliliğe İlişkin İfade", "going_concern"),
    ("Bağımsız Denetim Raporunun Olumsuz Görüş İçermesi veya Görüş Bildirmekten Kaçınılması",
     "Bağımsız Denetçi Görüşü Hakkında,", "auditor_adverse"),
    (ODA, "30.06.2011 Tarihli Bağımsız Denetim Raporu Şartlı Görüş Bildirimi", "auditor_adverse"),
    (ODA, "Rekabet Kurulu tarafından verilen idari para cezası hakkında", "regulatory_sanction"),
    (ODA, "Rekabet Kurumu Soruşturması Hakkında", "regulatory_sanction"),
    (ODA, "Şirketimiz Yönetim Kurulu Üyelerinin Gözaltına Alınmaları hk.", "regulatory_sanction"),
    (ODA, "Şirket paylarımıza getirilen brüt takas uygulamasına ilişkin açıklamamız", "market_sanction"),
    ("Ortaklık Aleyhine Dava Açılması veya Davaya İlişkin Gelişmeler", "Gulf Sigorta Dava Süreci Hk.",
     "lawsuit_or_seizure"),
    (ODA, "Şirketimiz Hakkında Başlatılan Takip ve Haciz İşlemleri Hakkında", "lawsuit_or_seizure"),
    (ODA, "Yönetim Kurulu Üyesinin İstifası ve Yerine Yeni Üye Ataması", "board_resignation"),
    (ODA, "Genel Müdürün istifası ve yerine vekaleten atama hakkında", "board_resignation"),
])
def test_red_flag_examples(subject, summary, expected):
    assert classify(subject, summary) == expected


@pytest.mark.parametrize("subject,summary", [
    # Rutin rapor, sureklilik suphesi degil.
    ("İlişkili Taraf İşlemleri", "Yaygın ve Süreklilik Arz Eden İlişkili Taraf İşlemleri Raporu"),
    # Vergi affi ve turev islemi, borc yapilandirmasi degil.
    (ODA, "6736 Sayılı Bazı Alacakların Yeniden Yapılandırılmasına İlişkin Kanundan yararlanılması hakkında"),
    (ODA, "Swap işlemleri yeniden yapılandırma"),
    # Sirketin magdur oldugu suc duyurusu, lehe sonuclar.
    (ODA, "Şirketimiz Tarafından Suç Duyurusunda Bulunulması Hakkında"),
    (ODA, "Vergi Cezalarının Kaldırılması Hk."),
    (ODA, "TMSF'nin Haciz Kaldırılması konulu tebligatı"),
    (ODA, "UZEL OTOMOTİV SİSTEMLERİ A.Ş.'den haciz ile alınan TBL Hattı Makinalarının satışı hakkında"),
    (ODA, "Şirketimizin hisse senetlerinin işlem gördüğü Gözaltı Pazarından bir üst pazara alınmasına ilişkin başvuru"),
    # Komite / bagli ortaklik / GM yardimcisi istifasi rutin.
    (ODA, "Kurumsal Yönetim Komitesi üyeliğinden istifa"),
    (ODA, "Bağlı ortaklık yönetim kurulu üyesinin istifası"),
    (ODA, "Genel Müdür Yardımcısı- Hazır Beton ve Agrega  istifası hakkında."),
    # Denetci gorusu olmayan "olumsuz gorus" ve duzeltme.
    (ODA, "Bağımsız Yönetim Kurulu Üyesi Ataması Hakkında Olumsuz Görüş Bildirilmemesi."),
    ("Finansal Tablo ve-veya Dipnot Değişikliği",
     "Bağımsız Denetim Şirketince Sehven Şartlı Görüş Bildirmesinin , OLUMLU GÖRÜŞ olarak düzeltilmesi."),
    # COVID tedbirleri, rutin bildirimler.
    (ODA, "COVID-19 ile ilgili alınan tedbirler hk."),
    ("Finansal Rapor", None),
    ("Yeni İş İlişkisi", ""),
])
def test_not_red_flag(subject, summary):
    assert classify(subject, summary) is None


def test_missing_text_is_tolerated():
    # Arsivde bos ozet NaN (float) olarak gelir.
    assert classify(None, float("nan")) is None


def test_priority_insolvency_over_lawsuit():
    # Konkordato davasi: dava kelimesi var ama sikinti kategorisi oncelikli.
    assert classify(ODA, "Görülmekte olan konkordato davası hk.") == "insolvency"


def test_every_category_has_label():
    assert set(RED_FLAG_LABELS) == {
        "insolvency", "going_concern", "auditor_adverse", "regulatory_sanction",
        "market_sanction", "lawsuit_or_seizure", "board_resignation",
    }
