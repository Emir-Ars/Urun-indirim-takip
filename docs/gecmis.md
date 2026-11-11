# Geliştirme geçmişi

Her plan adımı tek commit'tir. Bu dosya her adım için **tek satır** tutar:
tarih, commit, ne yapıldı ve aynı commit'in CI sonucu. Ayrıntılı oturum
kayıtları 20 Ekim 2026'ya kadar [arşivdedir](arsiv/proje_plani_2026-10-20.md);
kod farkları için `git show <commit>` kullanılır. CI sütunu boşsa sonuç o
tarihte belgeye ayrı kimlikle yazılmamıştır; GitHub Actions geçmişinde görülür.

Yeni satır, adımın commit/push'u yapılıp CI sonucu görüldükten sonra eklenir.
Bu dosyanın kendi güncellemesi bir sonraki adımın commit'ine girer.

## Aşama 1–4: fiyat okuma, keşif ve kabul kontrolü

| Tarih (2026) | Commit | Ne yapıldı | CI |
|---|---|---|---|
| 23.09 | `a36b5b6` | Complete Trendyol and Hepsiburada scraper milestone | — |
| 23.09 | `b0f466c` | Document and expose scraper offer diagnostics in live checks | — |
| 23.09 | `a716c9a` | Add readable TRY values to live scraper diagnostics | — |
| 24.09 | `e00a435` | Add model-based phone discovery and coverage reporting | — |
| 24.09 | `e6664a3` | Report verified sold-out Trendyol pages | — |
| 24.09 | `4d5613d` | Scraper ve discovery kabul kontrolünü tamamla | — |

## Aşama 5: katalog kurulumu

| Tarih (2026) | Commit | Ne yapıldı | CI |
|---|---|---|---|
| 28.09 | `9528f63` | Kataloğu 25 hedefle sıfırdan kur ve kod denetimini tamamla | — |

## Aşama 6: veritabanı, zamanlanmış toplama ve Cimri aktarımı

| Tarih (2026) | Commit | Ne yapıldı | CI |
|---|---|---|---|
| 28.09 | `6d7f6e8` | Veritabanı aşamasının kararlarını plana işle ve eski taslakları ayır | — |
| 28.09 | `5f1f149` | Veritabanı şemasını ve migration koşucusunu ekle | — |
| 28.09 | `72650f1` | Katalogu veritabanına eşitleme komutunu ekle | — |
| 28.09 | `72faae0` | Fiyat toplama turunu ve ortak tarama kilidini ekle | — |
| 28.09 | `792049a` | İlk tam fiyat turunu belgele ve boş tur notunu düzelt | — |
| 29.09 | `9f15525` | Görev Zamanlayıcı turunu ekle ve projenin tamamını gözden geçir | — |
| 29.09 | `881329f` | Cimri piyasa geçmişi araştırmasını tamamla | — |
| 01.10 | `76d4399` | Zamanlayıcı gözlemini kapat; Cimri, keşif ve ikinci geçiş kararlarını plana işle | — |
| 01.10 | `59fe190` | Haftalık keşif zamanlayıcısını ve rapor uygulama komutunu ekle | — |
| 05.10 | `b03faa3` | İlk haftalık keşif raporunu uygula ve Adım 10'u kapat | — |
| 05.10 | `ddf5548` | Adım 4: Koruyucu kurallar ve karşılaştırılabilirlik görünümü (002 migration) | — |
| 06.10 | `4e9c36c` | Bulut deneyi: GitHub Actions'tan canlı okuma iş tanımı (elle tetiklenir) | — |
| 06.10 | `685e53c` | Genel denetim: eskimiş belge ve yorumlar, küçük düzeltmeler, S25+ sayfası pasif | — |
| 06.10 | `55c4085` | Adım 11: Tur sonunda network hatalı sayfaları bir kez yeniden oku | — |
| 06.10 | `572061c` | Hepsiburada bozuk satıcı yanıtını Tükendi yerine hata olarak bildir | — |
| 06.10 | `9f31305` | Kapanmış turlara sonuç yazımını ve turların yeniden açılmasını engelle | — |
| 06.10 | `3388c6b` | HTTP yanıtını indirme sırasında 8 MB ile sınırla | — |
| 06.10 | `feee4bd` | Adres kimliği kontrolü için ham keşif yanıtlarını kaydet | — |
| 06.10 | `4f132fe` | Ham keşif testini dosya listeleme sırasından bağımsız yap | — |
| 06.10 | `57595f9` | Türkçe ekli aksesuarları kimlik ve kategori kontrollerinde reddet | — |
| 07.10 | `afe03e4` | Hepsiburada varyant kapasite ve renk tutarlılığını doğrula | [37603817085](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37603817085) |
| 07.10 | `8598e3c` | 2. bakım düzeltmesi: keşifte ürün adresi kimliğini ve canonical SKU eşitliğini doğrula | [37609748487](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37609748487) |
| 07.10 | `ac9c6b6` | 5. bakım düzeltmesi: ürün adresi kimliği kurallarını ortaklaştır ve doğrula | [37616987979](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37616987979) |
| 07.10 | `ea4248e` | 6. bakım düzeltmesi: tur sonu hata durumlarını doğrula ve kesinti mesajını düzelt | [37625155724](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37625155724) |
| 07.10 | `9cdde52` | 7. bakım kontrolü: eklenti yükleyicilerinin sözleşmelerini ve hata akışını doğrula | — |
| 08.10 | `79a3f77` | Adım 9.1: Cimri geçmişinin doğrulanmış yerel alımını ve güncel fiyat dönüşümünü hazırla | [37767276279](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37767276279) |
| 08.10 | `c64d14f` | Adım 9.2: Cimri geçmişi için güvenli veritabanı aktarımı ve önizleme ekle | [37777433986](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37777433986) |
| 08.10 | `2c78af2` | Adım 9.3: Cimri geçmişinin gerçek aktarımını ve katalog kapsamını doğrula | [37795271692](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37795271692) |
| 08.10 | `3c4d030` | Adım 7: veritabanı ve zamanlanmış toplama aşamasının kapanışını belgele | [37813840435](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37813840435) |
| 08.10 | `b4d1e98` | README’yi proje tanıtımına odakla ve teknik rehberle görev paylaşımını düzenle | — |

## Aşama 7: FastAPI ve Streamlit

| Tarih (2026) | Commit | Ne yapıldı | CI |
|---|---|---|---|
| 09.10 | `bcbad7c` | Aşama 7.1: API ve arayüz için bağımlılıkları, okuma rolünü ve test ortamını hazırla | [37915304432](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37915304432) |
| 09.10 | `04d765f` | Aşama 7.2: ürün, teklif ve fiyat geçmişi için salt okunur veritabanı sorgularını ekle | [37922348048](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37922348048) |
| 09.10 | `a964c23` | Aşama 7.3: kapsam dönemine göre fiyat istatistiklerini ve veri yeterliliğini hesapla | [37925934164](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37925934164) |
| 09.10 | `d8ba475` | Aşama 7.4: salt okunur FastAPI adreslerini ve bağlantı havuzunu ekle | [37930206610](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37930206610) |
| 09.10 | `ec42361` | Aşama 7.5: yerel API istemcisini ve ortak cevap doğrulamasını ekle | [37933861856](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37933861856) |
| 10.10 | `7ec1d0a` | Aşama 7.6: Streamlit telefon ekranını, fiyat grafiklerini ve yenilemeyi ekle | [38035484461](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/38035484461) |
| 10.10 | `c8d864b` | Aşama 7.7: gerçek SQL, API ve Streamlit akışını doğrula ve aşamayı kapat | [38045257013](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/38045257013) |

## ML öncesi bakım dizisi (Bakım 1–6)

| Tarih (2026) | Commit | Ne yapıldı | CI |
|---|---|---|---|
| 14.10 | `d251291` | Yenilio ürünlerini kapsam dışına al ve ML öncesi keşif incelemesini kaydet | [38564530086](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/38564530086) |
| 14.10 | `4eaf35e` | Trendyol'da 5G model ile 4G özellik çelişkisini reddet | [38569095383](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/38569095383) |
| 14.10 | `c814f64` | Redmi Note 13 Pro 512 GB ağ kanıtı incelemesini tamamla | [38578897388](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/38578897388) |
| 14.10 | `59fab0d` | Redmi Note 13 Pro 5G 256 GB renk kanıtı incelemesini tamamla | [38585120704](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/38585120704) |
| 15.10 | `9c3e4b6` | ML öncesi bakım planına otomatik güvenli kabul adımını ekle | — |
| 16.10 | `96d42a6` | Doğrulanan 15 keşif bağlantısını kataloğa ekle | [38873185491](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/38873185491) |
| 19.10 | `7a2d4ec` | Grafik başlangıcındaki sonsuz eksen uyarısını düzelt | [39209741592](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39209741592) |
| 19.10 | `b4d223f` | S25 bağlantısının katalog bakımını ve veritabanı doğrulamasını tamamla | [39211825501](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39211825501) |
| 19.10 | `14d70b2` | Cimri kullanım kapsamı değerlendirmesini belgele | [39216850461](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39216850461) |
| 19.10 | `0bc26a6` | İki eksik Cimri eşleştirmesinin incelemesini tamamla | [39223564598](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39223564598) |
| 19.10 | `978faa6` | Cimri incelemesini koşullu alım sonucu ile kapat | [39225290241](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39225290241) |
| 19.10 | `f600bc8` | ML veri yeterliliği denetimini ve kaynak değerlendirmesini ekle | [39237984848](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39237984848) |
| 20.10 | `7c0988b` | Haftalık keşfe kanıta dayalı otomatik katalog kabulünü ekle | [39393708497](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39393708497) |

## Proje yapısının sadeleştirilmesi (20–26 Ekim)

| Tarih (2026) | Commit | Ne yapıldı | CI |
|---|---|---|---|
| 20.10 | `6ad6fcd` | Adım 1: belgeleri sadeleştir; planı ve teknik rehberi yeniden düzenle, eski hâllerini arşivle | [39410273669](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39410273669) |
| 20.10 | `093dafc` | Adım 2: Git dışı inceleme kanıtları (12.038 dosya, ~330 MB) `Desktop\Staj_arsiv\2026-10-20\` klasörüne taşındı; belge notları | [39417566957](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39417566957) |
| 20.10 | `df35c7d` | Adım 3.1: canlı kontrol ve denetim araçları `tools/` klasörüne taşındı; eski piyasa geçmişi araştırma aracı kaldırıldı | [39462078926](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39462078926) |
| 22.10 | `3b9e2e0` | Adım 3.2: ortak test yardımcıları `tests/support/` altında toplandı; `tests.test_…` biçimindeki testler arası içe aktarmalar ve `insert`/`migrated` kopyaları kaldırıldı (kısa `from test_…` biçimindekiler kaldı) | [39733231717](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39733231717) |
| 22.10 | `18c77e5` | Adım 3.3: `test_discovery.py` (3.176 satır) konularına göre beş dosyaya bölündü; ortak keşif örnekleri `tests/support/discovery.py`'de | [39735381454](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39735381454) |
| 22.10 | `50c1721` | Adım 3.4: AppTest süre sınırı 30 sn; iki zaman aşımı testi 5 sn beklemeden; Cimri testleri canlı katalog yerine sabit ürün kopyasıyla | [39740220867](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39740220867) |
| 22.10 | `158eade` | Adım 3.5: kalan kısa biçimli testler arası içe aktarmalar (5 dosya) kaldırıldı; `world`/`client`/`stub` fixture'ları `tests/support/` altında `pytest_plugins` ile; koruma testi eklendi | [39743212204](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39743212204) |
| 22.10 | `1b9e937` | Adım 4.1: keşfin iki katalog/rapor yazıcısı tek yazıcıda birleşti (çıktı bayt bayt aynı) | [39750026839](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39750026839) |
| 22.10 | `764b5f3` | Adım 4.2: tur ve keşfin zamanlanmış çalışma kopyası `app/console.py` `run_logged` yardımcısında toplandı; komutlar ve log içeriği aynı | [39760818472](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39760818472) |
| 22.10 | `7a5ff8f` | Adım 4.3: Cimri kodunun kullanılmayan eski yolları (`cimri_page_data`, sıfırı ret eden TL modu) ve 3 eski test kaldırıldı; 151 kayıtlı/bozuk örneğin dönüşümü birebir aynı | [39762305991](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39762305991) |
| 22.10 | `cc3ec2d` | Adım 3.4 düzeltmesi: zaman aşımı testi havuzun ilk bağlantısını bekliyor (havuz büyüyüp bağlantıları sırayla verince test aralıklı düşüyordu) | [39768770708](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39768770708) |
| 22.10 | `7ca9be1` | Adım 5.1: otomatik kabulde Trendyol rengi renk seçicisindeki ad; 19 Ekim raporundaki 44 yanlış `color_mismatch` kalktı, diğer 451 karar değişmedi; 7 gerçek örnekle regresyon testi | [39769099983](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39769099983) |
| 26.10 | `75d4732` | Adım 5.2: atıl aday üretimini kaldır; kabul, ret ve HB seçenek taramasını koru; sadeleştirmeyi tamamla | [40291234833](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/40291234833) |

## Sürekli işletim, keşif ve kaynak bakımı (22 Ekim'den itibaren)

| Tarih (2026) | Commit | Ne yapıldı | CI |
|---|---|---|---|
| 22.10 | `b5bbb99` | Sürekli işletim: bulut denemesine Trendyol sayfa teşhisi; sonuç Trendyol'dan HTTP 403 ve Cloudflare çerezleri (GitHub yolu kapandı); karar: dizüstü sürekli açık, prizde kapak kapanınca uyumaz | [39779121760](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39779121760) |
| 22.10 | `1d82c9c` | Sürekli işletim kararını belgeledi: dizüstü sürekli açık, toplama evdeki bilgisayarda; buluta taşıma yolu kapandı | [39784217016](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/39784217016) |
| 26.10 | `6dcef3b` | Sürekli işletim, Cimri/ML hazırlığı ve iş sırası belgelerini güncelle | [40282132834](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/40282132834) |
| 26.10 | `8b933c2` | Haftalık keşif eklemelerini kaydet; kapasitesi doğrulanamayan S25 bağlantısını pasife al ve kapsam belgelerini güncelle | [40282854404](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/40282854404) |
| 02.11 | `63b2c30` | 1 Kasım keşfinin 7 bağlantısını (Trendyol 4, Hepsiburada 3) kaydet; 4.4 kapanış belgeleri ve 2 Kasım sıra kararı; 2206 test, 0 atlanan, Black ve Flake8 temiz | [41446593601](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41446593601) |
| 02.11 | `253c831` | Hepsiburada arama API'si: iPhone kategorisi tanım alanıyla tanınır, hedefe uyan yeni sonuç bitince uyarısız durulur; canlı yanıttan regresyon testi; canlı iPhone 15 kontrolünde 7 API varyantı, `repeated_page` yok, adaylar ve istek sayısı aynı; 2207 test, 0 atlanan, Black ve Flake8 temiz | [41451043542](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41451043542) |
| 09.11 | `7cf023a` | Haftalık ara kayıt: 8 Kasım otomatik keşfinin katalog eklemeleri ve güncel kapsam, 6.5/9.1 işletim denetimi ve erken değerlendirme sonuçları, önceki 7.4 kapanışı ve kabul edilen yerel web uygulaması/Docker teslim hedefi belgelendi. Docker uygulaması, görev veya model ayarı değişmedi; kullanıcı onayıyla gönderildi, aynı SHA için CI test paketi, Black ve Flake8 başarılı | [42587778055](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42587778055) |

## Ekran iyileştirmeleri (26–28 Ekim)

| Tarih (2026) | Commit | Ne yapıldı | CI |
|---|---|---|---|
| 26.10 | `dd2e262` | Ekran 1–2 kodu ve yerel geçiş: sıfır fiyat farkı gri/oksuz, seçilen satıcının offer_url akışı ve 005 migration; gerçek düğme kontrolü ilk yeni tur sonrası | [40310082371](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/40310082371) |
| 28.10 | `94045bd` | Trendyol ana satıcı adresi kaydındaki satıcı kimliğinden (`?merchantId=`); tur 58'de Trendyol 107/107, Hepsiburada 144/144 adres; tarayıcı örneklemesi ve iki pazaryerinin ekran düğmeleri doğrulandı; ekran 1–2 kapandı | [40643349065](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/40643349065) |

## Aşama 8: ML, gölge mod ve tahmin gösterimi

| Tarih (2026) | Commit | Ne yapıldı | CI |
|---|---|---|---|
| 28.10 | `ddca8ae` | Kalan sıra 2: GPT ve Claude ML araştırma raporları eklendi; kaynakları ve gerçek veriyle uyumu denetlendi; K1–K8 ML kararları plana yazıldı; son Cimri alımı için aktarım çakışması ve 57/60 eşleştirme açık karar oldu | [40653290005](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/40653290005) |
| 28.10 | `a2e124f` | Kalan sıra 3.1: Cimri aktarımında alım günü yarım gün sayılır; yarım gün farkı çelişki değil, ilk satır korunur ve fark raporlanır; 9 regresyon testi; arşivdeki 13:51 alımının önizlemesi eski kodla çıkış 2, yeni kodla 1 yarım gün farkı ve çıkış 0 | [40659279633](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/40659279633) |
| 28.10 | `d292db1` | Kalan sıra 3.2: Galaxy S24 FE 128 GB Cimri ana sayfasıyla eşleştirildi (58/60; kimliği son alımda doğrulanacak); S25 512 GB ve Redmi Note 14 Pro 5G 256 GB eşleştirmesiz kaldı | [40662966101](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/40662966101) |
| 28.10 | `fbdd42a` | Kalan sıra 4.0: ML hazırlığının yapısı ve 4.0–4.6 adımları, ara dönem sırası ve E8DHJL kararı plana yazıldı; teknik rehberde eşleştirme satırı düzeltildi | [40665199435](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/40665199435) |
| 30.10 | `bf0e80f` | Kalan sıra 4.1: `ml` bağımlılık grubu, CI ve salt okunur veri görüntüsü; gerçek görüntü (60 ürün, 370 sayfa/366 etkin; Cimri 20.805 satır/57 ürün, 553 eksik fiyat) doğrulandı; 2032 test, 0 atlanan, Black ve Flake8 temiz | [41046830071](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41046830071) |
| 02.11 | `179215a` | Kalan sıra 4.2: günlük seriler, simetrik 6/7 etiketi, sabit/izlenen kapsam, parmak izli rapor ve eski hesaplayıcıyla sıkı çapraz kontrol; gerçek görüntü ve yerel test/biçim denetimleri doğrulandı | [41413845126](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41413845126) |
| 02.11 | `c6ecea7` | Kalan sıra 4.3: geçmişe dayalı tipli model girdileri, aile/segment, girdi şeması ve raporu; gelecek veriye karşı değişmezlik testleri, gerçek görüntüde 4.2 başlangıç eşleşmesi ve dosya bütünlüğü doğrulandı | [41429382111](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41429382111) |
| 02.11 | `ad01bcb` | Kalan sıra 4.4: ortak tarih bölmesi, purge, ayrı kalibrasyonlu ileri yürüyen katlar, ölçütler ve tarih bloklu güven aralığı; gerçek bölme/kat, dosya bütünlüğü ve saklı test koruması doğrulandı | [41440395101](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41440395101) |
| 02.11 | `e144bf9` | Kalan sıra 3: son Cimri alımı ve aktarımı (kullanıcı terminali); 58 ürün, 1.790 yeni gün, çelişki yok; salt okunur doğrulama 22.595 kayıt/58 ürün/699 eksik fiyat, 9 Ekim 2025–2 Kasım 2026 | [41462109583](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41462109583) |
| 02.11 | `e46ca61` | Kalan sıra 4: 4.1–4.4 komutları son alımı içeren 2 Kasım görüntüsüyle yeniden çalıştırıldı (kod değişmedi); Cimri 19.561 kullanılabilir pencere, 23.115 girdi başlangıcı 4.2 ile birebir, bölme yeterli, dört kat Nisan–Temmuz 2026, saklı test açılmadı; sabah turu ölçümü plana yazıldı; 2207 test, 0 atlanan, Black ve Flake8 temiz | [41493302145](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41493302145) |
| 03.11 | `49b937e` | ML 4.5: R0–R2, LightGBM, ayrı dilimde Platt kalibrasyonu ve ağsız deney komutu; yeniden üretilen bölmeyle kanıt zinciri, yalnız kat doğrulama tahminleri, üç durumlu seçim önerisi ve raporlar; sızıntı testleri, tam test paketi, Black ve Flake8 başarılı; gerçek deney 4.6'da, saklı test açılmadı | [41620388192](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41620388192) |
| 03.11 | `24cdb55` | ML 4.6: son alımı içeren kanıtlarla ilk gerçek Cimri deneyi kullanıcı terminalinde çalıştırıldı; dosya/üyelik ve kayıtlı tahminlerden kat/birleşik puan doğrulaması, sonuç yorumu ve belgeler; LightGBM seçim koşulu karşılanmadı, kesin model seçilmedi, saklı test açılmadı; tam test paketi, Black ve Flake8 CI'da başarılı | [41625038457](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41625038457) |
| 03.11 | `4eed21b` | ML 5.1: `freeze` ve `final-test` komutları, saklı test için ayrı puanlama girişleri, pickle'ı SHA-256/parmak izi/sürüm/kalibrasyon yeniden üretimi denetimlerinden sonra açan model yükleme; gerçek kanıtlarla deney çıktıları 3 Kasım'la bayt bayt aynı, `freeze` provası geçici klasörde; 2348 test, 0 atlanan, Black ve Flake8 temiz; dondurma ve saklı test çalıştırılmadı | [41643112753](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41643112753) |
| 04.11 | `834326b` | ML 5.2: kullanıcı R2 + Platt modelini dondurdu; model manifest SHA-256'sı ve dosya parmak izleri, girdi/deney zinciri, dilim üyeliği ve yeniden yüklemede kalibrasyon olasılıklarının birebir üretimi doğrulandı; ön kayıt belgelendi ve gönderildi; 2348 test, 0 atlanan, Black ve Flake8 temiz; saklı test açılmadı | [41795838319](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41795838319) |
| 04.11 | `f238d92` | ML 5.3: kullanıcı ön kayıtlı R2 + Platt ile saklı testi bir kez açtı; dosya/üyelik/etiket denetimi, kayıtlı tahminlerden bağımsız puan, kalibrasyon, kırılım ve tarih bloklu AP farkı aralığı doğrulaması; okuma koşulları karşılandı, model değişmedi, kendi kaynak puanlanmadı; sonuçlar ve sınırlar belgelendi, gönderildi; CI tam test paketi ve biçim kontrolleri başarılı | [41801324595](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41801324595) |
| 04.11 | `376208e` | Gölge mod 6.0: plan (6.0–6.5) ve ön kayıtlı değerlendirme kuralları belgelendi (dondurulan model değişmez, kayıt `data/ml/golge/` dosyaları, günlük çalışma 11:00, kesin kapı değerlendirmesi 5 Ocak 2027); aynı commit 4 Kasım veri kapsam ve Cimri kimlik denetimi notlarını içerir; kod değişmedi, CI testler ve biçim kontrolleri başarılı | [41832785030](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41832785030) |
| 04.11 | `a4f0318` | Gölge mod 6.1: kullanıcı terminalinde 4 Kasım görüntüsü (`snapshot`, `labels`, `features`, üçü de çıkış 0) ve ağsız ölçüm; 47 kendi etiketi tek güne (27 Ekim) ait, 11 ürün hiç başlangıç üretmiyor, gösterilebilir ürün 44–48, 30 olay hedefi kaba öngörüyle sınırda (29–39), kendi satırlarında `missing_ratio_30d` eğitimden ~5 sapma uzakta; plan riskleri ve Cimri uç değer sınırı belgelendi, 6.4'e bilgi amaçlı kırılım eklendi; kod değişmedi, CI testler ve biçim kontrolleri başarılı | [41835197577](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41835197577) |
| 04.11 | `6421610` | Gölge mod 6.2: `shadow-predict` komutu ve `config/shadow.json` (ön kayıtlı model SHA-256'sı doğrulanıp dondurulan modelle kendi serimiz için değişmez, kayıtlı günü yeniden tahmin etmeyen tahmin kaydı; resmi kayıt 6.3'te); 2374 test, 0 atlanan, Black ve Flake8 temiz; kuralları bozan 6 değişiklik testlerce yakalandı; kullanıcı terminalinde 4 Kasım görüntüsüyle deneme (398 kayıt, 389 olasılık, 368 gösterilebilir) bağımsız denetlendi: girdiler `features` ile birebir, olasılıklar `model.json` katsayılarından pickle açılmadan aynı; resmi kayıt oluşmadı | [41838861593](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/41838861593) |
| 05.11 | `091a954` | Gölge mod 6.3: günlük salt okunur görüntü + tahmin akışı, sınırlı tur bekleme, ortak kayıt kilidi, kalıcı model kanıtları ve penceresiz Windows görev betiği; ilk resmi kayıt bağımsız denetlendi, ikinci çalışmada dosyalar değişmedi ve yeni tahmin oluşmadı; kullanıcı 11:00 görevini kurup ayarlarını okudu; model değişmedi, gönderildi, aynı SHA için CI tam test paketi ve biçim kontrolleri başarılı | [42027035890](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42027035890) |
| 05.11 | `fe46382` | Gölge mod 6.4: kayıtlı olasılıkları yeni görüntüdeki gerçek etiketlerle eşleştiren değerlendirme komutu, girdi eşleşmesi denetimi, own_evaluation güven aralığı, ön kayıtlı kapı ve sağlık raporu; ilk gerçek raporun girdileri, ham turlardan etiketleri ve standart Python ile puanları bağımsız doğrulandı, tahmin dosyaları/model değişmedi; erken veri desteği yetersiz, kesin karar verilmedi; gönderildi, aynı SHA için CI tam test paketi ve biçim kontrolleri başarılı | [42040569861](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42040569861) |
| 06.11 | `e936b68` | ML 7.1 (yalnız belge): tek kart, günlük güncellik, ayrı tahmin API sözleşmesi, kaynak doğrulama ve kesin rapora bağlı gösterim onayı planı belgelendi; 6.5 ilk otomatik çalışma kanıtı ve kalan iş sırası güncellendi, Docker/sunum korundu. Model değişmedi; API/CLI/ekran henüz uygulanmadı. Gönderildi, aynı SHA için CI test paketi ve biçim kontrolleri başarılı | [42218229190](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42218229190) |
| 06.11 | `0f3ebdd` | ML 7.2: ortak kayıt okuyucu, kesin rapor/model SHA’sına bağlı gösterim onayı ve kapatma komutu, ayrı tahmin API ucu ve yerel istemci sözleşmesi; günlük güncellik, kaynak görüntü ve yeterlilik denetimi, güvenli hata cevapları; model/resmi kayıtlar değişmedi, gösterim kapalı. Kullanıcı onayıyla gönderildi; aynı SHA için CI tam test paketi, Black ve Flake8 başarılı | [42223187541](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42223187541) |
| 06.11 | `c2dd26e` | ML 7.3: tek tahmin kartı, tarih/fiyat/kapsam açıklamaları, kapalı/eksik/yetersiz veri durumları; tahmin hatası fiyat ekranından ayrıldı, telefon ve durum değişiminde eski oran kaldırılır. Gerçek gösterim kapalı; otomatik ekran/API testleri ve aynı SHA'nın CI tam test/biçim kontrolleri başarılı. Görsel tarayıcı denetimi 7.4'te açık | [42228410084](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42228410084) |
| 09.11 | `07ec7cf` | ML 7.4: kayıt ve kaynak görüntü → API → istemci → ekran zinciri, gün değişimi/yeni kayıt, yeterlilik, kanıt hatası ve CLI kapatma testleri; kullanım rehberi tamamlandı. Yapay önizlemenin geniş/dar görünümü ve senaryo kartları kullanıcı görüntüleriyle, yenileme/seçim/fiyat-grafik korunması kullanıcı teyidiyle doğrulandı. Gerçek gösterim kapalı, model değişmedi; onaylı dosyalar gönderildi, aynı SHA için CI tam test paketi, Black ve Flake8 başarılı | [42578742631](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42578742631) |

## Aşama 9: Docker teslim yazılımı ve yerel kabul

| Tarih (2026) | Commit | Ne yapıldı | CI |
|---|---|---|---|
| 09.11 | `3ef75a4` | Docker 9.2: ayrı gerçek veri kopyasıyla yerel web uygulaması teslimi, ağ/sürüm/kalıcılık ve paket/geri dönüş sözleşmesi, Docker parola istisnası ve 9.3–9.7 geliştirme sırası belgelendi; README yol haritası güncellendi. Docker uygulaması, canlı görevler ve model değişmedi; kullanıcı onayıyla gönderildi, aynı SHA için CI pytest, Black ve Flake8 adımları başarılı | [42601311403](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42601311403) |
| 09.11 | `5368c39` | Docker 9.3: SHA ile sabit tabanlar, hash'li Linux bağımlılık kilidi, ayrı kullanıcı ve salt okunur uygulama, veri/sır dışlaması, DB/API/UI Compose ağı, gizli dosya girişi ve kilit yardımcıları/testleri eklendi; belgeler güncellendi. İmaj, sürüm/izin, ağ ve bağlam kontrolleri yerelde doğrulandı. Gerçek veri, model ve Windows görevleri değişmedi; kullanıcı onayıyla gönderildi, aynı SHA için CI pytest, Black ve Flake8 adımları başarılı | [42617392260](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42617392260) |
| 09.11 | `d3fc0fd` | Docker 9.4: tutarlı salt okunur yedek, SHA/kod/model/şema doğrulamalı paket ve ayrı Docker kopyasına hazırlama eklendi; NOLOGIN sahiplik, SELECT API hesabı ve tekrar hazırlama yapay ve ilk gerçek paketle doğrulandı. Native kaynak, model ve gösterim kapısı korundu; belgeler tamamlandı, kullanıcı onayıyla gönderildi, aynı SHA için CI pytest, Black ve Flake8 başarılı | [42632732129](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42632732129) |
| 10.11 | `f2a4e57` | Docker 9.5: API/UI bağlantısı, yerel aktarım bildirimi, türlenmiş hazırlık kaydı ve kopyaya özel gösterim bakımı eklendi; aynı tarih/kapı, kontrol dosyaları, RO/yetki sınırları ve fiyat/grafik akışı yapay ve gerçek kopyada doğrulandı. Native kaynak, model ve kapalı gösterim korundu; kullanıcı onayıyla gönderildi, aynı SHA için CI pytest, Black ve Flake8 başarılı | [42785773532](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42785773532) |
| 10.11 | `4a06202` | Docker 9.6: tek PowerShell girişi, paket başına sabit imaj/Compose, seçim ve işlem kilidi, sağlık kontrolleri, durum/log ve geri dönüş eklendi; tekrar hazırlama/açılış, paket geçişi, bozuk paket reddi ve başarısız API açılışından kurtarma yapay kopyalarda doğrulandı. Gerçek teslim kopyası yeniden sağlıklı açıldı; native kaynak, görevler ve ML kapısı korundu. Kullanıcı onayıyla tek commit/push yapıldı, aynı SHA için CI pytest, Black ve Flake8 başarılı | [42800500575](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42800500575) |
| 10.11 | `952b454` | Docker 9.7 kodu ve yerel kabul: tekrarlanabilir yapay _test paket/aktarım, gerçek HTTP/grafikler, yetki/kesinti/kalıcılık, Linux gösterim kapısı ve ağsız akış aracı; ayrı Docker CI işi ve teslim rehberi eklendi. Temiz Windows klasöründe kurulum/geçiş/kurtarma ve sınırlar doğrulandı; kullanıcı onayıyla tek commit/push yapıldı. Aynı SHA için pytest, Black, Flake8 ve yeni Docker kabul/rapor işi başarılı; ikinci fiziksel Windows PC kabulü açık | [42815832301](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42815832301) |

## Belge düzeni (10 Kasım'dan itibaren)

| Tarih (2026) | Commit | Ne yapıldı | CI |
|---|---|---|---|
| 10.11 | `7d95864` | Belge denetimi: README'de kaynak/teslim kullanımı ve kalan işler ayrıldı; plan, teknik rehber, ortak AI kuralları ve araştırma notlarının konumu güncellendi, eski durum/bağlantı bilgileri düzeltildi. Kod, model, görevler ve ölçümler değişmedi. Kullanıcı onayıyla tek commit/push yapıldı; aynı SHA için CI pytest, Black, Flake8 ve yapay Docker kabul/rapor işi başarılı | [42823077732](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42823077732) |
| 11.11 | `7de68d7` | Belge düzeni Adım 2: tamamlanan uygulama, 6.5/9.1 düzenli takibi, bekleyen kabul/teslim ve ikincil ML kapsamı ayrıldı; tek güncel takip tablosu, README özeti ve rehber bağlantıları düzenlendi. Ölçümler, eski kararlar, model ve kabul koşulları korundu. Kullanıcı onayıyla beş belge tek commit/push ile gönderildi; aynı SHA için CI pytest, Black, Flake8 ve yapay Docker kabul/rapor işi başarılı | [42986337605](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42986337605) |
| 11.11 | `0e84166` | Belge düzeni Adım 3: planın bitmiş teknik ayrıntıları asıl rehbere bağlandı; kontrol/risk/kabul metinleri korunarak taşındı, eski kurulum/Cimri/kapsam açıklamaları düzeltildi. Geçmiş aşamalara ayrıldı, Eylül tekrarları doğrulanmış arşive bağlandı; önceki 111 commit/CI kaydı, kararlar, ölçümler ve model korundu. Kullanıcı onayıyla üç belge tek commit/push ile gönderildi; aynı SHA için CI pytest, Black, Flake8 ve ayrı yapay Docker kabul/rapor işi başarılı | [42990800690](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/42990800690) |

## Eylül 2026 ayrıntıları

Eylül'deki kabul kontrolü ve katalog kurulumu anlatıları dondurulmuş
teknik rehberle karşılaştırıldı; ayrı kopyaları burada tutulmaz:

- [24–25 Eylül kabul kontrolü](arsiv/teknik_2026-10-20.md#kabul-kontrolü-eylül-2026).
- [25–27 Eylül katalog kurulumu ve kapanış denetimi](arsiv/teknik_2026-10-20.md#katalog-kurulumu-2527-eylül-2026).

Arşivdeki dönem sayıları bugünkü kapsam değildir. Kararların güncel yeri
[planın kararlar tablosudur](../proje_plani.md#5-kararlar); teknik davranış
güncel rehberden okunur. Arşivin eski bölüm numaraları değiştirilmemiştir.
