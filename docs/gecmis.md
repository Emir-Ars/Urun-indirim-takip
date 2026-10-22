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

## Proje yapısının sadeleştirilmesi (20 Ekim'den itibaren)

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
| 22.10 | (bekliyor) | Adım 4.3: Cimri kodunun kullanılmayan eski yolları (`cimri_page_data`, sıfırı ret eden TL modu) ve 3 eski test kaldırıldı; 151 kayıtlı/bozuk örneğin dönüşümü birebir aynı | — |

## Eylül 2026 ayrıntıları

Kabul kontrolü ve katalog kurulumu sırasında bulunup düzeltilen sorunlar
(eski teknik rehberden aynen alınmıştır).

### Kabul kontrolü (24–25 Eylül 2026)

Veritabanına geçmeden önce scraper ve discovery 6 adımda, canlı veri ve tarayıcı
karşılaştırmasıyla denetlendi. Sonuç: o günkü katalogdaki 44 sayfanın tamamı hatasız
sınıflandı (16 Stokta Var, 5 Kritik Stok, 23 Tükendi); satıcı listeleri, fiyatlar
ve üstü çizili fiyatlar tarayıcıda görülenle eşleşti. Bulunup düzeltilenler:

| Sorun | Çözüm |
|---|---|
| Keşfin sessiz eleme kararları görünmüyordu | `--trace` tanılama izi |
| Keşif ve scraper modeli farklı kurallarla kontrol ediyordu; başlığında "GB" yazmayan Hepsiburada sayfaları hiç okunamıyordu | Tek ortak kimlik kuralı (`identify`) |
| Hepsiburada `-pm-` grup kartları görülmüyordu (bir iPhone 15 ailesi eksikti) | Grup sayfaları gerçek SKU'ya çözülüyor; eksik sayfa kataloğa eklendi |
| Stoksuz Hepsiburada sayfaları "Tükendi" yerine hata veriyordu | Satıcı listesi boşsa doğrudan `Tükendi` |
| Çelişkili Hepsiburada yanıtı "Tükendi" sayılıyordu | `api_error` |
| "Yenilenmiş Cep Telefonu" telefon kategorisi sayılabiliyordu | Hariç tutuluyor |
| Boş SKU'lu bir varyant kaydı bütün keşfi raporsuz durduruyordu | Kayıt atlanıyor, hata raporlanıyor |
| Xiaomi'de marka filtresi bulunamıyor, arama 71.450 ürünle (çoğu kılıf) doluyordu | Marka filtre listesinden de okunuyor (129 ürün, tam tarama) |
| Redmi Note 14 ile Note 14 5G aynı ürün sanılıyordu | `exclude_terms` |
| Trendyol'da satıcının koşulsuz indirimi atlanıyordu | Sayfadaki indirimli fiyat kaydediliyor |
| Tek bir tutarsız aday bütün keşif çalışmasını raporsuz durduruyordu | Yalnızca o aday atlanıyor (`catalog_conflict`) |
| Arama aşamasındaki bozuk yanıt bütün keşfi çökertebiliyordu | Ortak kurtarılabilir hata listesi; uyarı olarak raporlanıyor |
| Hepsiburada'nın bildirdiği sayfa adresi alan adı kontrolsüz kullanılıyordu | Yalnızca `https://www.hepsiburada.com/` kabul ediliyor |
| Keşif, hiç kullanmadığı API paketine (`slowapi`/`limits`) bağımlıydı; ölü kod ve gelecek aşama tanımları vardı | Temizlendi; bağımlılıklar yalnızca biten aşamanınkiler |

Trendyol model filtresinin (ör. "Cep Telefonu Modeli: iPhone 16") kullanılması
değerlendirildi ve **reddedildi**: satıcıların girdiği bu özellik güvenilir
değil (iPhone 16e sayfaları "iPhone 16" olarak etiketli) ve hiçbir marka 20
sayfa sınırına yaklaşmadı (Apple 3–4, Samsung 6, Xiaomi 4 sayfa).

### Katalog kurulumu (25–27 Eylül 2026)

Kabul kontrolünden sonra katalog **sıfırdan** kuruldu: eski 6 ürün / 45
bağlantılık katalog boşaltıldı (elle verilmiş 3 Trendyol bağlantısı ve
stoksuz sayfalar bilinçli olarak bırakıldı; testler artık kataloğun sabit
kopyasını okur) ve kullanıcının seçtiği 25 hedef marka marka eklendi. Her
markada aynı döngü uygulandı: keşif → rapor incelemesi → canlı fiyat kontrolü →
kullanıcının tarayıcı karşılaştırması. Bütün keşif ve kontrol komutlarını
kullanıcı kendi terminalinden çalıştırdı.

| Marka | Ürün | Sayfa (HB / TY) | Kullanıcının tarayıcıda kontrol ettiği |
|---|---|---|---|
| Apple (9 model) | 29 | 118 / 46 | 5 sayfada fiyat, satıcı, çizili fiyat, Tükendi; 2 sayfada renk seçicisi |
| Samsung (8 model) | 17 | 56 / 41 | 4 sayfada fiyat, satıcı, stok; S25 256 GB'ın Ultra olmadığı |
| Xiaomi (6 model) + POCO (1) | 11 | 25 / 20 | 2 sayfada "Mobil Bağlantı Hızı" alanı; satıştaki POCO X6 Pro sayfası |

Kurulum sonunda 57 ürün ve 306 bağlantı; bunlardan biri (yurt dışı sürüm) pasif.
28 Eylül'deki kapanış taraması (sıfır çakışma, sıfır ağ hatası) 21 bağlantı ve
2 ürün daha ekledi: güncel katalog **59 ürün, 327 bağlantı** (Apple 29 ürün
118/50, Samsung 18 ürün 62/41, Xiaomi 11 ürün 30/22, POCO 1 ürün 3/1;
Hepsiburada/Trendyol). 5 Ekim'de ilk haftalık keşif raporu 7 sayfa ekledi (Apple
121/50, Samsung 62/42, Xiaomi 31/24, POCO 3/1; Hepsiburada/Trendyol): katalog
**59 ürün, 334 bağlantı**. Kurulumdaki son
toplu fiyat kontrolünde (27 Eylül) 306 bağlantının 304'ü okundu: 163 Stokta Var,
70 Kritik Stok, 71 Tükendi. Kalan 2 Galaxy S25 128 GB sayfası "12 GB Ram"
başlığı yüzünden doğrulanamadı; kural düzeltildi (aşağıda).

Kurulum sırasında bulunup düzeltilenler (her biri canlı örneğe dayanan testle):

| Sorun | Çözüm |
|---|---|
| Trendyol HTML arama sayfası (`/sr`) HTTP 403 ile engelleniyordu; 9 modelin 6'sı taranamadı | Sayfa açılmıyor, API'ye yalnız `Referer` gönderiliyor; aynı komut beklemesiz 9/9 geçti |
| Engel raporunda yalnız "blocked" yazıyordu; 429 (hız) ile 403 (erişim) ayırt edilemiyordu | Rapora HTTP kodu ve engellenen adres yazılıyor |
| "Galaxy S25 Edge" S25, "iPhone 17 Air" iPhone 17 sayılıyordu | `edge` ve `air` ayrı model eki |
| "Galaxy S25 Ultra_12GB_256GB" adı hem S25 hem Ultra sayıldı (`catalog_conflict`) | `_` boşluk gibi okunuyor |
| Trendyol renkleri satıcı özelliğinden geliyordu: "Çok Renkli", genel "Mavi" | Renk, sayfanın renk seçicisindeki ad (varyant listesi) |
| POCO `brand: "Xiaomi"` ile bulunamıyordu | Marka sitedeki etiket: `POCO` |
| Redmi Note 14/13 Pro 4G başlıkta "4G" yazmadığı için hiç bulunamıyordu | `network` alanı: yapısal "Mobil Bağlantı Hızı" ile doğrulama |
| `exclude_terms: ["5G"]`, 4G telefonların "4.5G" başlığını da dışlıyordu | Ondalık sayının parçası olan ifade eşleşmiyor |
| "Galaxy S25 128 GB 12 GB Ram" başlığında hafıza belirlenemiyordu | "RAM" etiketli değer hafıza sayılmıyor |
| Bir iPhone 16 yurt dışı sürümü ("International Version") karşılaştırmaya giriyordu; satıcı garanti alanına "Apple Türkiye Garantili" yazmıştı | Yurt dışı sürümler kapsam dışı; o bağlantı pasife alındı |

Son denetimde (kodu baştan okuyan inceleme) bulunup düzeltilenler:

| Sorun | Çözüm |
|---|---|
| Hepsiburada'da satıcı listesinde stok alanı olmayan sayfa "Tükendi" sayılıyordu | Alan yoksa `parse` hatası; Tükendi yalnız açık sinyalle |
| 3 sn bekleme her bağlantıda yeni istemci açıldığı için uygulanmıyordu | Son istek zamanı alan adı başına, bütün istemciler arasında ortak |
| `curl_cffi` çerez çakışması hatası bütün çalışmayı durdurabilirdi | Çerez yokmuş gibi devam ediliyor |
| "5G+", "5G NR" ağ değerleri tanınmıyordu; 4G hedefine girebilirdi | 5G desteği söyleyen her değer 5G |
| Katalog Windows'ta CRLF satır sonuyla yazılabiliyordu | Her zaman LF |

Kararlar: RAM ve garanti türü ürün kimliğine katılmadı (gerekçe: [proje_plani.md](../proje_plani.md),
Bölüm 5); yurt dışı sürümler kapsam dışı; POCO X5 Pro satılmadığı
için kapatıldı.
