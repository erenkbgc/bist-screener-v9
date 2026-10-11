# Sektöre özel analiz: araştırma notları (2026-10-11)

Taslak not. Henüz ön kayıt değil, hiçbir test koşulmadı. Amaç: yarın hangi sektörde hangi ölçütü test edeceğimize karar vermek.

## 0. Önce düzeltilmesi gereken tutarsızlık

- Test edilen model (`long_term_preregistration.md`) finansal şirketleri **içermiyor**. `core/pit_panel.py::FINANCIAL_SECTORS` banka, sigorta, emeklilik, faktoring, finansal kiralama ve aracı kurumları dışarıda bırakıyor.
- Canlı sistem ise bunları da puanlıyor. 2026-10-10 koşusunda GARAN valuation_z 0.58, ANSGR 0.44, SAHOL STRONG_OPPORTUNITY çıktı.
- Sonuç: finansal şirketler canlı AL listesine test edilmemiş bir kuralla girebiliyor.
- Öneri: bu şirketleri canlı rotasyondan çıkar ya da "test edilmedi" etiketiyle göster. Ön kayıt gerekmez; amaç canlıyı test edilen tanıma uydurmak.

## 1. Genel bulgu: tek tip çarpan çoğu sektörde yeterli

- Liu, Nissim & Thomas (2002, *Journal of Accounting Research*) büyük bir çarpan setini karşılaştırdı. Sıralama şöyle: ileriye dönük kâr en iyi, sonra geçmiş kâr; nakit akışı ve defter değeri üçüncü; satış en kötü.
- Bu sıralama neredeyse **tüm sektörlerde aynı** çıktı. "Her sektörün kendi en iyi çarpanı var" görüşünü desteklemiyor.
- Bizim için anlamı:
  - value_sn zaten sektör içinde normalize ediliyor (bm, ep, sp ve ey z-skorları, sektör ortalaması çıkarılarak).
  - Sanayi sektörleri için ayrı bir çarpan eklemek büyük ihtimalle az şey katar.
  - value_sn içindeki satış/fiyat (sp) bileşeni literatürde en zayıf ölçüt.
- Gerçek fark, bilanço yapısı farklı sektörlerde: finansallar, holdingler ve GYO'lar.
- Kaynak: [Equity Valuation Using Multiples](https://business.columbia.edu/sites/default/files-efs/pubfiles/318/Equity_Valuation_Using_Multiples.pdf), [RePEc](https://ideas.repec.org/a/bla/joares/v40y2002i1p135-172.html)

## 2. Sektör bazında bakılacak ölçütler

### Bankalar (yaklaşık 13 hisse, şu an panelde yok)
- **Teori:** PD/DD, ROE'ye göre değerlendirilmeli; yüksek ROE yüksek PD/DD'yi haklı çıkarır. BIS çalışmaları global bankalarda PD/DD'nin analistlerin ROE tahminleriyle çok yakın hareket ettiğini buluyor. Takipteki krediler (NPL), defter değerinin ötesinde PD/DD'yi düşürüyor.
- **Gelişen piyasalar:** ZEB çalışmasında ROE ve kişi başı reel GSYH daha belirleyici çıkıyor. Net faiz marjının (NIM) etkisi zayıf veya istikrarsız.
- **Türkiye'ye özel:**
  - Swap maliyetine göre düzeltilmiş net faiz marjı ile swap hariç marj çok farklı. Hangi tanımın kullanıldığına dikkat et.
  - TÜFE'ye endeksli menkul kıymet getirileri, enflasyon tahminine çok duyarlı.
  - Kamu bankalarının marjı özel bankalardan belirgin düşük.
  - Düzenleyici esnekliklerin kalkması sermaye oranlarını düşürecek.
- **Aday test:** ROE'ye göre PD/DD artığı. PD/DD, ROE'ye kesitsel regresyonla açıklanır; artığı negatif olan banka ucuz sayılır.
- **Engel:** Banka bilançoları farklı formatta. borsapy'de ayrı bir finansal grup gerekiyor ve panel bunu hiç çekmedi.
- **Güç:** Ayda 13 bankanın üst %20'si 2–3 hisse ediyor. İstatistiksel test neredeyse imkânsız. Bu sektörde ancak betimsel analiz yapılabilir.
- Kaynaklar: [BIS – What drives bank PBRs](https://www.bis.org/publ/qtrpdf/r_qt1803h.htm), [BIS WP 1144](https://www.bis.org/publ/work1144.pdf), [ZEB – bank valuation](https://zeb-consulting.com/en-DE/topics/confronting-the-puzzle-of-bank-valuation), [Fitch: Türk bankalarında NIM](https://www.ekoturk.com/haberler/fitch-turk-bankalarinda-swap-maliyetleri-haric-ortalama-net-faiz-marji-68e-yukseldi/), [İş Yatırım Bankacılık Raporu Haziran 2026](https://arastirma.isyatirim.com.tr/2026/08/03/bankacilik-sektor-raporu-haziran-2026/)

### Sigorta / emeklilik (ANSGR, AGESA, TURSG gibi; panelde yok)
- Bankalara benzer şekilde PD/DD ile ROE ilişkisine bakılır. Teknik kâr ile yatırım geliri ayrımı da önemli.
- Sektöre özel akademik kanıt bulamadım; ayrı bir arama gerekiyor.

### Holdingler (47 hisse, panelde var)
- **Teori:** Net aktif değer (NAV) iskontosu. Holdingin piyasa değeri, iştiraklerinin piyasa değeri + net nakit – holding borcu toplamıyla karşılaştırılır.
- **Neden iskonto var:** Ekstra yönetim katmanı, likidite ve vergi. Bu açıklamalar akademik değil, pratisyen görüşleri.
- **Türkiye örneği:** Garanti BBVA Yatırım bir holding için iskontoyu %36 olarak hesaplamış, 2 yıllık ortalama %32. İskontonun kendi ortalamasına dönmesi bir alım gerekçesi olarak kullanılıyor.
- **Dikkat:** Projenin `no_historical_ratio_comparison` kuralı bir metriği kendi tarihsel ortalamasıyla karşılaştırmayı yasaklıyor. Test **kesitsel** olmalı: aynı ay içinde iskontosu yüksek holding ile düşük holding karşılaştırılır.
- **BIST'e özel çalışma:** NAV iskontosunun getiriyi öngörüp öngörmediğini BIST'te test eden akademik çalışma bulamadım. En yakın kanıt: BIST'te defter/piyasa oranı en güçlü getiri tahmincisi (Emerging Markets Finance and Trade, 2013).
- **Veri:** İştirak payları KAP'taki "Şirket Genel Bilgi Formu"nda var; formdan şirket sayısı 46.576. İştiraklerin fiyatları da panelde var. Ama tarihsel iştirak yapısını zaman noktasına uygun (PIT) kurmak zahmetli.
- Kaynaklar: [Garanti BBVA Yatırım – AVPGY raporu](https://www.garantibbvayatirim.com.tr/medium/ResearchReports-Constant-58092.vsf), [Return Predictability of Turkish Stocks](https://www.tandfonline.com/doi/abs/10.2753/REE1540-496X490506)

### GYO (54 hisse, panelde var)
- **Teori:** Net aktif değer (NAD) iskontosu. GYO'larda bilanço genelde gerçeğe uygun değerle tutulduğu için PD/DD bu iskontoya kabaca yakın. Yani value_sn içindeki bm bileşeni bunu kısmen zaten yakalıyor olabilir.
- **ABD REIT kanıtı:**
  - Letdin & Sirmans (JREFE): NAV priminin yarısından fazlası şirket özellikleriyle açıklanıyor (büyüklük, mülk tipi, kaldıraç, kârlılık). **Duygu kaynaklı artık** ise gelecek getiriyle güçlü negatif ilişkili. Özelliklerden gelen kısım ise çok zayıf bir tahminci.
  - Gentry, Jones & Mayer: iskontolu REIT'i alıp primli olanı satan strateji yüksek fazla getiri vermiş. Bunu ikincil kaynaktan aktarıyorum.
- **Türkiye:**
  - Sektörde NAD iskontosu %42–50 aralığında; aracı kurumlara göre değişiyor.
  - Uçlarda %80'in üzerinde iskonto (OZGYO, ALGYO) ve %700'ün üzerinde prim (PEKGY) var.
  - Aracı kurum yorumlarına göre performansı belirleyen başlıca etkenler borçluluk ve portföy yapısı.
  - Türkiye'de NAD iskontosunun getiriyi öngörüp öngörmediğine dair hakemli çalışma bulamadım.
- **Aday test:** Kesitsel NAD iskontosu. Daha iyisi Letdin & Sirmans tarzı: iskontoyu kaldıraç, büyüklük ve kârlılıkla açıkla, artığı sinyal olarak kullan.
- **Veri:** KAP arşivinde 8.596 "Değerleme Raporu" bildirimi var; ekspertiz değerleri bunlarda. Ama değerler PDF ekinde, kısa özette yok.
- Kaynaklar: [Betting Against the Sentiment in REIT NAV Premiums](https://link.springer.com/article/10.1007/s11146-020-09803-3), [RERI WP 106](https://www.reri.org/research/article_pdf/wp106.pdf), [Nareit – NAV premium/discount](https://www.reit.com/news/blog/market-commentary/valuing-reits-in-2017-stock-price-premiumdiscount-to-net-asset-value), [Fintables – NAD nedir](https://fintables.com/arastirma/yazilar/sektor-analiz/nad-nedir), [GYO'larda net varlık iskontosu](https://yenercoskun.com/gyolarda-net-varlik-iskontosu/), [GYO iskonto/prim tablosu](https://paraajansi.com.tr/piyasalar/gyo-hisselerinde-iskonto-ve-prim-tablosu-hangi-sirket-one-cikiyor-22230256h)

### Sanayi, enerji, ulaştırma, perakende
- **Teori:** EV/FAVÖK varsayılan ölçüt. Kiralama yükü ağır şirketlerde (havayolu, perakende) EV/FAVÖKK (kira öncesi) kullanılıyor. Enerjide alt sektör farkı büyük: üretim, dağıtım, yenilenebilir.
- **Türkiye'ye özel konular:**
  - **Net döviz pozisyonu ve ihracat payı:** Kur şokunda ayrışmanın ana kaynağı. Bunu destekleyen bir kaynak bulamadım, genel bilgi.
  - **TMS 29 enflasyon muhasebesi** (aşağıda ayrı başlık).
- Liu-Nissim-Thomas bulgusuna göre bu sektörlerde ayrı bir çarpan büyük fark yaratmayabilir. Öncelik düşük.
- Kaynaklar: [Damodaran EV multiples](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/vebitda.html), [EV/EBITDA by industry](https://www.basisreport.com/resources/ev-ebitda-by-industry-sector-benchmarks)

## 3. Tüm sektörleri etkileyen konu: TMS 29 enflasyon muhasebesi

- 2023 yıl sonundan beri bilançolar enflasyona göre düzeltiliyor. Net parasal pozisyon kazancı/kaybı ayrı bir kalem olarak gösteriliyor.
- Yüksek TL borçlu şirket, parasal kazanç sayesinde kârlı görünebilir. Nakit zengini şirket ise faaliyetleri kârlı olsa bile zarar gösterebilir. Parasal kazanç nakit yaratmaz.
- **Bizim için risk:** ep ve ey bileşenleri parasal kazanç/kayıptan etkileniyor. Kâr bu kalemden arındırılmazsa value_sn, borçlu şirketleri olduğundan ucuz gösterebilir.
- **Aday düzeltme:** Kâr ölçütünden parasal kazanç/kaybı çıkarmak. Bunun için önce panelde bu kalemin var olup olmadığını kontrol et.
- Kaynaklar: [Finkap – TMS 29](https://finkap.com.tr/blog/enflasyon-muhasebesi-tms-29), [KGK – TMS 29 metni](https://www.kgk.gov.tr/Portalv2Uploads/files/DynamicContentFiles/T%C3%BCrkiye%20Muhasebe%20Standartlar%C4%B1/TMSTFRS2018Seti/TMS/TMS_29_2018.pdf), [İstanbul Bağımsız Denetim – TMS 29](https://www.istanbulbagimsizdenetim.com.tr/2026/01/09/enflasyon-muhasebesi-tms-29-ve-denetim-gercek-rakamlara-donus/)

## 4. Yarın için önerilen sıra

1. **Finansal şirket tutarsızlığını düzelt** (bölüm 0). Hızlı iş, araştırma değil.
2. **TMS 29 kontrolü:** Panelde parasal kazanç/kayıp kalemi var mı? Varsa kâr bazlı bileşenler (ep, ey) bundan arındırılınca value_sn sıralaması ne kadar değişiyor? Önce betimsel bak, getiri testi ön kayıtla yapılır.
3. **GYO:** Önce bm'nin zaten NAD iskontosuna yakın olup olmadığını kontrol et. Yakınsa ek iş gerekmez. Değilse Letdin-Sirmans tarzı artık testi için ön kayıt yaz.
4. **Holding NAV iskontosu:** Ön kayıt yaz, kesitsel test. İştirak yapısı verisinin maliyetini önce değerlendir.
5. **Bankalar ve sigorta:** Güç çok düşük. Ancak betimsel bir "PD/DD ile ROE" paneli yapılabilir, getiri testi yapılamaz.

## 5. Uyarılar

- **Çoklu test riski:** Sektör × ölçüt kombinasyonu çoğaldıkça tesadüfen anlamlı sonuç bulma ihtimali artar. Hipotez sayısı az tutulmalı ve hepsi önceden yazılmalı.
- **Sektör büyüklükleri küçük:** Holding 47, GYO 54, banka yaklaşık 13 hisse. Sektör içi üst dilim 2–10 hisse ediyor.
- **Kaynakların niteliği:** Yukarıdaki Türkiye kaynaklarının çoğu aracı kurum veya haber yazısı, hakemli çalışma değil. Rakamlar tarih ve hisse kapsamına göre değişiyor.
