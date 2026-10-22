# Teknik rehber

Bu belge, [README](../README.md)'de tanıtılan sistemin başvuru rehberidir:
dosyaların görevleri, komutlar, keşif ve fiyat okuma kuralları, veritabanı,
API ve ekran sözleşmeleri, hata kodları ve bilinen sınırlar. Yalnız sistemin
**bugünkü davranışını** anlatır; tarihli oturum kaydı tutmaz.

- Kararlar, aşama durumu ve açık kararlar: [proje_plani.md](../proje_plani.md)
- Adım adım geçmiş (tarih, commit, CI): [gecmis.md](gecmis.md)
- 20 Ekim 2026'ya kadarki ayrıntılı oturum kayıtları: [arsiv/](arsiv/)

## İçindekiler

- [Dosyalar ve sorumlulukları](#dosyalar-ve-sorumlulukları)
- [Komutlar](#komutlar)
- [Yeni telefon ekleme: bütün kurallar](#yeni-telefon-ekleme-bütün-kurallar)
- [Eklenti yükleyicilerinin sözleşmesi](#eklenti-yükleyicilerinin-sözleşmesi)
- [Keşif nasıl çalışır](#keşif-nasıl-çalışır)
- [Fiyat okuma nasıl çalışır](#fiyat-okuma-nasıl-çalışır)
- [Kimlik kuralları](#kimlik-kuralları)
- [Veritabanı (PostgreSQL)](#veritabanı-postgresql)
- [Cimri geçmişi (bir defalık alım ve aktarım)](#cimri-geçmişi-bir-defalık-alım-ve-aktarım)
- [Yerel API: kurulum ve okuma hesabı](#yerel-api-kurulum-ve-okuma-hesabı)
- [Salt okunur veritabanı okumaları](#salt-okunur-veritabanı-okumaları)
- [Fiyat istatistikleri](#fiyat-istatistikleri)
- [Salt okunur FastAPI](#salt-okunur-fastapi)
- [Yerel API istemcisi](#yerel-api-istemcisi)
- [Streamlit ekranı](#streamlit-ekranı)
- [SQL–API–Streamlit bağımsız denetimi](#sqlapistreamlit-bağımsız-denetimi)
- [ML veri denetimi](#ml-veri-denetimi)
- [Testler ne kanıtlar, ne kanıtlamaz](#testler-ne-kanıtlar-ne-kanıtlamaz)
- [Bilinen sınırlar](#bilinen-sınırlar)

## Dosyalar ve sorumlulukları

### Proje kökü ve belgeler

| Dosya | Görevi |
|---|---|
| `README.md` | Projenin tanıtımı: amaç, özellikler, akış, teknolojiler, güncel kapsam, yol haritası. |
| `proje_plani.md` | Kararların, aşama durumunun, açık kararların ve sıradaki işin tek kaynağı. |
| `AGENTS.md` | Projede çalışan yapay zekâ araçlarının (Claude Code, Codex) ortak çalışma kuralları. |
| `docs/teknik.md` | Bu rehber: bugünkü davranışın başvuru belgesi. |
| `docs/gecmis.md` | Her plan adımı için kısa geçmiş satırı (tarih, ne yapıldı, commit, CI). |
| `docs/arsiv/` | 20 Ekim 2026'da dondurulmuş eski plan ve rehber, Aşama 7 araştırma raporları. Değiştirilmez. |
| `pyproject.toml` | Bağımlılıklar, Python sürümü, paketleme ve test/biçim araçlarının ayarları. |

Eski veritabanı, API, ML, arayüz ve Docker taslakları yerel
`_eski_taslaklar/` klasöründedir. Git’e gönderilmez, güncel uygulamanın
parçası değildir ve bugünkü kodla çalışmazlar; yalnız örnek olarak korunur.

### Ayarlar: `config/` (kod değil, veri)

| Dosya | Ne işe yarar | Kim yazar |
|---|---|---|
| `discovery.json` | Takip edilecek telefonlar ve tarama sınırları | Kullanıcı |
| `catalog.json` | Keşfin doğruladığı ürünler ve sayfalar | Keşif (elle yazılmaz) |
| `runtime.json` | Zaman aşımı, tekrar deneme, istekler arası bekleme (3 sn) | Kullanıcı, nadiren |
| `market_history.json` | Bir defalık Cimri alımı: `product_key`, URL ve beklenen Cimri kimliği. 57 ürünün ana adresi doğrulandı; Galaxy S25 512 GB ve Redmi Note 14 Pro 5G 256 GB eşleştirmesiz, yeni eklenen Galaxy S24 FE 128 GB için eşleştirme yapılmadı. | Araştırma ve gerçek çıktı kontrolüyle |

### Ortak parçalar: `app/`

| Dosya | Ne işe yarar |
|---|---|
| `contracts.py` | Verinin şekilleri ve doğrulaması (Pydantic V2 strict): `Product`, `Listing`, `Catalog`, `PriceObservation`, keşif hedefleri ve raporu. Hatalı veri içeri giremez (ör. fiyat alanına "Tükendi"). Yalnızca biten aşamanın kullandığı tanımları içerir. |
| `settings.py` | Ayar dosyalarını okur. `CATALOG_PATH`, `DISCOVERY_PATH`, `RUNTIME_PATH`, `SCRAPE_LOCK_PATH`, `LOG_DIR`, `DISCOVERY_REPORT_DIR` ortam değişkenleriyle başka dosya veya klasör gösterilebilir. |
| `scrape_lock.py` | Siteye giden bütün girişlerin paylaştığı kilit (`data/scrape.lock`). Fiyat turu, keşif, Cimri yerel alımı/ağsız aktarımı ve iki canlı kontrol aracı (`live_scraper_check`, `live_discovery_check`) alır; biri sürerken diğeri beklemeden "sürüyor" deyip çıkar. Süreç çökse bile işletim sistemi kilidi bırakır. |
| `console.py` | Komut satırı araçlarının ortak çıktı yardımcıları: UTF-8 çıktı (`utf8_output`; fiyat turu, keşif, `app.database` ve canlı kontrol araçları kullanır), `<ön ek>_<tarih-saat>.log` dosyası açma ve stdout/stderr'i log dosyasına da yazan `tee_output` (yalnız zamanlanmış tur ve keşif). pythonw.exe altında ekran akışları yoktur (`None`); hepsi buna dayanır. |
| `price_statistics.py` | `ProductSnapshot.all_history` verisinden mevcut tam kapsam dönemini, 30 günlük gözlenen dibi, dönem zirvesini ve değişkenliği hesaplar; eksiklik gerekçeleri ve gözlem sayıları döndürür. Bağlantı/HTTP/dosya işlemi yapmaz; Cimri verisini kullanmaz. |

### Cimri geçmişi: `app/market_history/`

| Dosya | Ne işe yarar |
|---|---|
| `cimri.py` | Gömülü ürün ve grafik yanıtını ağsız okur; marka/model/kapasite, kategori ve kimlik doğrulaması yapar. Alım ayrıca fiyatı mevcut `money` ile kuruşa doğrular. |
| `capture.py` | Eşleştirmeleri doğrular; seçilen ürünlerin HTML ve API JSON yanıtlarını yeni klasöre, parmak izlerini ve sonucu rapora yazar. Veritabanına bağlanmaz. |
| `importer.py` | Sonlandırılmış alım raporunu ve kaynak parmak izlerini doğrular; aynı baytlardan kimlik/geçmişi yeniden hesaplar. Katalog kimliği ve rapor eşitliği zorunludur. Dosya/veritabanı yazmaz, ağa çıkmaz. |
| `__main__.py` | `capture` ve ağsız `import`/`--dry-run` girişidir; ortak kilidi alır, Türkçe sonucu basar, çıkış kodlarını yönetir. `capture` veritabanına bağlanmaz; `import` HTTP çalışma ayarlarını okumaz. |

### Fiyat okuma: `app/scraper/`

| Dosya | Ne işe yarar |
|---|---|
| `http.py` | İnternete açılan tek kapı. `curl_cffi` + `impersonate="chrome120"`; yalnızca izinli alan adları, zaman aşımı, sınırlı tekrar, istek aralığı (alan adı başına, bütün istemciler arasında ortak), yönlendirme kontrolü, indirme sırasında 8 MB gövde sınırı, istek bütçesi. 401/403/418/429 yanıtları `blocked` olarak sınıflanır. Playwright, Selenium veya `requests` kullanılmaz. |
| `parsing.py` | Ortak yardımcılar: fiyatı kuruşa çevirme (`money`), metin normalleştirme, sayfaya gömülü JSON okuma ve **kimlik kuralları** (`identify`, `verify_identity`, `matches_model`, `network_type`, `verify_model_network`). Trendyol'un açık 5G model/4G özellik reddi de iki tüketicide aynı ortak kontroldür. |
| `base.py` | Bütün sitelerin sözleşmesi: `fetch(listing) -> PriceObservation`. Ayrıştırma hatalarını ortak `FetchError`'a çevirir. |
| `factory.py` | Platform adından (`trendyol`, `hepsiburada`) doğru scraper sınıfını yükler. |
| `trendyol_scraper.py` | Trendyol sayfasını okur, satıcıları karşılaştırır. |
| `hepsiburada_scraper.py` | Hepsiburada sayfası + satıcı listesi API'si + fiyat API'siyle satıcıları karşılaştırır. |

### Keşif: `app/discovery/`

| Dosya | Ne işe yarar |
|---|---|
| `trendyol.py` | Trendyol arama API'si, filtreler, varyant (renk/kapasite) listeleri ve ürün sayfası doğrulaması. |
| `hepsiburada.py` | Hepsiburada arama/model sayfası kartları, grup sayfaları ve ürün sayfasındaki seçenek listesi. |
| `matching.py` | "Yeni telefon kategorisi mi?" kuralı (aksesuar ve yenilenmiş kategoriler hariç). |
| `base.py` | Ortak iskelet: istek bütçesi, uyarı listesi (`issues`), tanılama izi (`trace`) ve ağ türü kontrolü (`verify_network`). |
| `service.py` | Platformları çalıştırır, sonuçları katalogla birleştirir, raporu yazar (`run`); incelenmiş önizleme raporunu siteye gitmeden kataloğa uygular (`apply_report`); raporun tek satırlık özetini üretir (`summarize_report`). Tarama bittikten sonra katalog ya da rapor yazılamazsa `DiscoveryWriteError` verir (`run`). |
| `__main__.py` | Komut satırı: `python -m app.discovery [--dry-run] [--target KEY]`, `--scheduled --dry-run` veya `--scheduled --auto-accept` (Görev Zamanlayıcı) ve `--apply-report RAPOR`. |

### Veritabanı: `app/database/`

| Dosya | Ne işe yarar |
|---|---|
| `connection.py` | PostgreSQL bağlantısı. Adres `DATABASE_URL` ortam değişkeninden okunur (şifresiz); şifre PostgreSQL'in `pgpass.conf` dosyasındadır. Oturum saati UTC; bağlanma 10 sn, tablo kilidi bekleme 30 sn ile sınırlı (yarım bırakılmış bir işlem turu sonsuza kadar bekletmez, hata verir). |
| `migrate.py` | Migration koşucusu: `migrations/` altındaki numaralı SQL dosyalarını sırayla, her birini tek transaction'da ve yalnızca bir kez uygular; `schema_migrations` tablosuna parmak iziyle yazar. |
| `migrations/001_initial.sql` | Katalog kopyası, toplama turları ve sayfa sonuçları tabloları; bütün kurallar (`CHECK`, `UNIQUE`, yabancı anahtarlar). |
| `migrations/002_guards_and_comparability.sql` | İki yeni `CHECK` (Tükendi satırı fiyat taşımaz, çizili fiyat güncel fiyattan büyüktür), beş tabloda 15 tetikleyici (silmeyi ve `TRUNCATE`'i reddeder, kimlik alanlarını korur, yazılmış sayfa sonucunu dondurur), `product_run_prices` görünümü. |
| `migrations/003_closed_run_guards.sql` | İki tetikleyici işlevini yeniler: kapanmış turun sonuçsuz satırına yazımı ve kapanmış turun durum/bitiş zamanı değişimini reddeder; ilk sonuç ve `network` yeniden yazımını tur kapanışıyla sıraya alır. Veri satırlarını ve görünümü değiştirmez. |
| `migrations/004_market_history.sql` | Ayrı Cimri geçmişi tablosu; ürün/kaynak/gün tekilliği, pozitif kuruş/NULL ve ilk kaydın güncelleme/silme korumaları. |
| `market_history.py` | Ağsız aktarımın SQL işlemleri: kimlik ön kontrolü, salt okunur önizleme, ürün başına transaction, tekrar/çelişki koruması ve tur kilidi. |
| `catalog_sync.py` | `catalog.json`'u veritabanındaki kopyaya eşitler: `plan_sync` farkı veritabanına dokunmadan hesaplar, `sync_catalog` tek transaction'da yazar. |
| `runs.py` | Tur SQL'leri: veritabanı tur kilidi, yarım kalan turu kapatma, turu ve planlanan sayfaları açma, sayfa sonucunu (bir kez, yalnızca süren tura) yazma, süren turdaki `network` hatası satırını ikinci okumanın sonucuyla değiştirme (`rewrite_network_result`, tek istisna), turu kapatma, özet. |
| `read.py` | API'nin kullanacağı salt okunur veri katmanı: etkin ürünler, global tur durumu, ürüne özel son tamamlanmış tur, teklifler ve ayrı kendi/Cimri geçmişi. Hazır bağlantıda tek REPEATABLE READ, READ ONLY işlem; bağlantı/havuz açmaz, kilit almaz, veri yazmaz. |
| `__main__.py` | Komut satırı: `python -m app.database migrate` / `status` / `sync-catalog [--dry-run]`. Çıkış kodları: `0` başarılı; `1` komut başarısız (şema, katalog çakışması, bağlantı, ayar; mesaj stderr'e `Veritabanı komutu başarısız: …` diye yazılır); `2` argüman hatası. |

### Fiyat toplama turu: `app/collection/`

| Dosya | Ne işe yarar |
|---|---|
| `service.py` | Bir tur: şema kontrolü, yarım kalan turu kapatma, katalog eşitleme, planlama, her sayfayı mevcut scraper'la okuyup sonucunu hemen yazma, `network` hatası alan sayfaları tur sonunda bir kez yeniden okuma, turu kapatma. Scraper ile veritabanını bağlayan tek yer. |
| `__main__.py` | Komut satırı: `python -m app.collection [--prefix ÖN_EK] [--scheduled]`; ortak kilidi alır. `--scheduled` ile çıktı `data/logs/` altındaki log dosyasına da yazılır. |

### Yerel API: `app/api/`

| Dosya | Ne işe yarar |
|---|---|
| `main.py` | `create_app()` fabrikası, lifespan ile havuz açma/kapatma, dört GET adresi, cevap doğrulaması ve Türkçe güvenli hata cevapları. İçe aktarmada bağlantı açmaz. |
| `database.py` | Yalnız `API_DATABASE_URL` ile 1–4 bağlantılık Psycopg havuzu; her istekte rol, SELECT/yazma izinleri, nesneler ve migration durumunun salt okunur denetimi. |
| `schemas.py` | API ve istemcinin ortak, ağsız cevap modelleri. DB/havuz/hesaplama/FastAPI yüklemez; JSON alanları ve OpenAPI aynı kalır. |
| `models.py` | Tek `ProductSnapshot` içinden istatistik ve fiyat yaşıyla ortak cevaba dönüşüm. İç `all_history`, ham sayfa hata metni ve tur notu dışarı verilmez. |

### Yerel istemci ve ekran: `app/ui/`

| Dosya | Ne işe yarar |
|---|---|
| `api_client.py` | `ApiClient`: dört sabit yerel GET, katı girdi/JSON/hedef doğrulaması; proxy/yönlendirme/tekrar/önbellek yok, açık zaman aşımı ve güvenli Türkçe hatalar. UI veritabanı/sunucu uygulamasını yüklemez. |
| `main.py` | Kartlı Streamlit ekranı: telefon/aralık seçimi, güncel sonuç, API istatistikleri, iki grafik ve 30 sn/elle yenileme. Hata halinde eski veri kaldırılır; yalnız seçim tercihleri korunur. |
| `presentation.py` | Tamsayı kuruş ve İstanbul saati biçimleme, Türkçe gerekçeler, açık boşluk/kapsam sınırlarına sahip Altair çizgi/nokta verisi. İstatistik hesaplamaz veya veri kaynağına bağlanmaz. |

### Kurulum ve zamanlayıcı: `scripts/`

| Dosya | Ne işe yarar |
|---|---|
| `zamanlayici_kur.ps1` | Fiyat toplama turunu Windows Görev Zamanlayıcı'ya kurar (her gün 10:00 ve 22:00, penceresiz); `-Kaldir` ile siler. Ayarları [Zamanlanmış tur](#zamanlanmış-tur-görev-zamanlayıcı) bölümündedir. |
| `kesif_zamanlayici_kur.ps1` | Haftalık keşfi Görev Zamanlayıcı'ya kurar (her Pazar 14:00, penceresiz, kaçan çalışmayı telafi etmez). Seçeneksiz kurulum önizleme (`--dry-run`), `-OtomatikKabul` otomatik kabul (`--auto-accept`) modunu kurar; `-Kaldir` siler. Ayarları [Zamanlanmış keşif](#zamanlanmış-keşif-görev-zamanlayıcı) bölümündedir. |
| `api_okuma_rolu.sql` | Yönetici hesabıyla çalıştırılan, tek işlemde rol/SELECT izinlerini hazırlayan ortam kurulumu. Yeni tablo veya migration oluşturmaz; fiyat/katalog satırlarını değiştirmez. Üretimde `fiyat_takip_api`, `_test` DB'de `fiyat_takip_api_test`; mevcut ayrıcalıklı/üye/sahip veya yazma yetkili rolü reddeder. |

### Testler ve CI

Test sayıları burada tutulmaz; güncel sayı `pytest -q` çıktısındadır.

| Yer | Ne sınar |
|---|---|
| `tests/conftest.py` | Her testte gerçek curl_cffi ve HTTPX ağ transport'ları kesilir; ASGI/TestClient/MockTransport süreç içinde çalışır. Kalıcı `DATABASE_URL` ve `API_DATABASE_URL` silinir. `db` yalnız `TEST_DATABASE_URL`'deki `_test` DB'yi her testte boşaltır; ortak test kilidi en çok 30 sn bekler. `api_db` ayrıca `TEST_API_DATABASE_URL` ve `fiyat_takip_api_test` ister; iki bağlantının aynı `_test` DB olduğunu denetleyip test şemasında SELECT izinlerini yeniden kurar. `migrated`, `db`'ye bütün migration'ları uygular. Eksik test adresleri yerelde atlama, CI'da hata üretir. |
| `tests/support/` | Test değildir; birden fazla test dosyasının ortak yardımcılarıdır: sahte HTTP oturumu ve yanıtı (`fake_http.py`), `_test` DB'ye satır yazan `insert` (`database.py`), toplama turunun küçük sahte kataloğu ve sahte scraper'ları (`collection.py`), Cimri kayıtlı örnekleri ve sahte istemcisi (`market_history.py`), Streamlit ekranının yapay örnekleri (`ui_samples.py`). Test dosyaları birbirinden içe aktarma yapmaz; yalnız tek dosyada kullanılan yardımcı o dosyada kalır. Buradaki `assert`'ler de pytest'in ayrıntılı hata mesajını verir (`conftest.py`'deki kayıt). |
| `tests/test_http.py` | HTTP katmanı: hata kodları (`invalid_host` mesajı hedef alan adını yazar, sorgu metnini yazmaz), indirme sırasında 8 MB sınırı, büyük hata/yönlendirme yanıtları, yönlendirme kuralları, 5xx tekrarı ve bekleme süreleri, istekler arası bekleme, scraper factory. Mimari sınır da burada: pazaryeri HTTP'si yalnız `app/scraper/http.py` ve curl_cffi ile; HTTPX yalnız `app/ui/api_client.py` için; UI veritabanı/havuz/sunucu katmanını yüklemez. |
| `tests/test_contracts.py` | Pydantic sözleşmeleri: satılabilir teklif fiyat ve satıcı taşır, puan ölçeği aşamaz, üstü çizili fiyat güncel fiyattan büyüktür, katalog kimlik/referans/alan adı kuralları, `money()` kuruş çevirimi. |
| `tests/test_url_identity.py` | Ortak ürün adresi kimliği: ürün yolu, sorgu, son eğik çizgi, küçük harfli SKU, eksik/bozuk kimlik ve bütün tüketicilerin aynı kimliği okuması. |
| `tests/test_trendyol_scraper.py`, `tests/test_hepsiburada_scraper.py` | Fiyat okuma: seçilen teklif, eşit fiyatta satıcı adı, çizili fiyat, Kritik Stok, Tükendi'nin yalnız açık sinyalle verilmesi, bozuk satıcı kayıtlarının reddi, ret nedenleri, `parse` dönüşümü. Sahte sayfa ve istemci; internete çıkmaz. |
| `tests/test_discovery.py` | Keşif: kimlik kuralları, sayfalama ve uyarı türleri, katalog birleştirme, dry-run'ın kataloğa yazmaması, LF satır sonu, BOM'lu ayar dosyaları, UTF-8 çıktı, çıkış kodları, zamanlanmış keşif, `--apply-report` ve gerçek `config/*.json` dosyalarının sözleşmeye uyması. |
| `tests/test_discovery_acceptance.py` | Otomatik güvenli kabul: gerçek kaynak örnekleriyle doğrulandı/uyuşmazlık/kanıt yetersiz kararı, rapor ve katalog yazma koruması, kesinti sonrası uzlaştırma. |
| `tests/test_collection.py` | Toplama turu: sahte scraper'larla her sonuç türü, Ctrl+C, tur ortasında veritabanı hatası, yarım kalan tur, kilitlerin bırakılması, pasif sayfa/ürün/platform, ön ek, çıkış kodları, zamanlanmış turun logu, kapanış sonrası hatalar ve tur sonu ikinci okuma. |
| `tests/test_catalog_sync.py` | Katalog eşitleme: kararlar veritabanısız; yazma, deneme, çakışma ve komut satırı veritabanında. |
| `tests/test_database.py` | Migration koşucusu, şemanın bütün `CHECK`/`UNIQUE`/yabancı anahtar kuralları, 002 ve 003 tetikleyicileri, kodun gerçek güncellemelerinin geçmesi, "bilerek silme" yolu ve testlerin emniyet kemerleri. |
| `tests/test_comparability.py` | `product_run_prices` görünümü: aynı sayfa kümesi, hataya giriş/çıkış, yeni sayfa, Tükendi, `--prefix` turu, süren/yarıda kalan turlar, uzun boşluk. |
| `tests/test_database_read.py` | Salt okunur sorgular ve istatistiklerle bütünleşme: ürüne özel tamamlanmış tur, kısmi kapsam, ayrı Cimri/NULL, iki bağlantıyla tutarlı görüntü, sorgu hatası/zaman aşımı sonrası yeniden okuma. |
| `tests/test_price_statistics.py` | İstatistik hesabı: tam kapsam dönemi, 30 gün/14 geçiş/7 gün/18 saat eşikleri, İstanbul günü, NULL üzerinden geçmeme, değişkenlik, grafik aralığından bağımsızlık. Veritabanısız. |
| `tests/test_api_foundation.py` | API okuma rolünün izinleri (yazamaması, kalıcı nesne kuramaması) ve test ortamının ağ/adres korumaları. |
| `tests/test_api.py` | FastAPI: dört adres ve OpenAPI, kuruş/UTC/NULL, fiyat yaşı, rol/şema hataları, dört bağlantı sınırı, kesinti ve yeniden bağlantı, 5 sn sorgu zaman aşımı, tutarlı cevap. |
| `tests/test_api_client.py` | Yerel API istemcisi: katı girdi/JSON ve alan tamlığı, sabit hedef/proxy/yönlendirme sınırı, güvenli hatalar, tekrar/önbellek olmaması, kaynak bırakma. |
| `tests/test_ui.py` | Streamlit ekranı (AppTest) ve grafik verisi. Yapay örnekler `tests/support/ui_samples.py`'dedir; AppTest ve önizleme ortak kullanır, gerçek fiyat değildir. |
| `tests/test_api_ui_integration.py` | Gerçek test okuma hesabı → FastAPI → istemci → Streamlit zinciri; SQL ve hesaplama sahte değildir. |
| `tests/test_api_ui_check.py`, `tests/test_ml_data_check.py`, `tests/test_live_discovery_check.py` | Aşağıdaki denetim/kontrol araçlarının kendileri. |
| `tests/test_market_history.py`, `tests/test_market_history_import.py` | Cimri alımı ve aktarımı: kimlik, tarih/fiyat/eksik veri, ham kanıt ve parmak izi, istek bütçesi, kilit, ilk/tekrar aktarım, çelişki, READ ONLY önizleme, kesinti. |
| `tests/fixtures/` | Gerçek kaynaklardan küçültülmüş örnekler (kaynak yolu ve SHA-256 ile) ve kataloğun sabit kopyası (`discovery/catalog.json`). Testler `data/` veya ağa bağlı değildir. |
| `.github/workflows/ci.yml` | Her push/pull request'te geçici PostgreSQL 17 (`C.UTF-8`) açar, `dev,web` bağımlılıklarını kurar; yalnız `_test` DB'de API rolünü hazırlar ve Black/Flake8/tam testleri çalıştırır. `ci_only` şifresi yalnız o işte açılıp silinen sunucunundur. |
| `.github/workflows/bulut-deneme.yml` | Elle tetiklenen bulut erişim denemesi (zamanlama, veritabanı ve gizli anahtar yok): `tools/live_scraper_check.py samsung_galaxy_a55_128gb` ile 4 sayfayı GitHub'ın makinesinden okur. Sonuç "Bilinen sınırlar"dadır. Tur saatlerinde (10:00–10:40, 22:00–22:40) tetiklenmez: `data/scrape.lock` bu makineye özgüdür. |

### Canlı kontrol ve denetim araçları: `tools/`

Otomatik test değildir; `pytest` bu klasörü toplamaz. Araçlar proje kökünden
`.venv\Scripts\python.exe tools\<araç>.py` biçiminde çalıştırılır; siteye veya gerçek veritabanına giden araçları
kullanıcı kendi terminalinden, tur ve keşif saatleri dışında çalıştırır.

| Araç | Ne işe yarar |
|---|---|
| `tools/live_scraper_check.py` | Katalogdaki sayfaları canlı okur; bütün satıcıları gösterir. İsteğe bağlı `product_key` ön eki (ör. `samsung_`) ile yalnız o ürünler; sayfa seçimi toplama turuyla aynı fonksiyondur. Başka bir tarama sürüyorsa (ortak kilit) çıkış kodu 3'tür. |
| `tools/live_discovery_check.py` | Keşfi kataloğa yazmadan canlı çalıştırır; `--trace` ile her kararın nedenini gösterir. Normalde raporu `data/discovery_report.json` dosyasının üzerine yazar. `--save-responses KLASOR`, tek hedefin ham HTML/JSON yanıtlarını ve raporunu yeni klasöre kaydeder; karar izini de basar. |
| `tools/ui_preview.py` | Aynı Streamlit ekranını ağsız test istemcisiyle gösterir; kalıcı test verisi uyarısı vardır. API/DB veya canlı site gerekmez; kullanıcı görünüm/yenileme kontrolünü burada yapar. |
| `tools/ml_data_check.py` | Yalnız okuma hesabıyla günlük 30+7 ML pencereleri, %5 hedefi, eksik/kapsam nedenleri ve zaman bölümlerini hesaplar. Kendi/Cimri ayrı; `--snapshot` ile ağsız tekrar. Model eğitmez, API/site çağırmaz. |
| `tools/api_ui_check.py` | Yerel API'nin gerçek veritabanını doğru sunduğunu, üretim kodunu kullanmadan bağımsız SQL hesabıyla karşılaştırır ([bağımsız denetim](#sqlapistreamlit-bağımsız-denetimi)). |

## Komutlar

Windows ve PowerShell, Python sanal ortamı `.venv`:

```powershell
# Kurulum: mevcut kod + test araçları + API/arayüz hazırlığı
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev,web]"

# Otomatik testler (internete çıkmaz; veritabanı testleri TEST_DATABASE_URL ister)
.venv\Scripts\python.exe -m pytest -q

# Veritabanı şeması: bekleyen migration'ları uygula / durumu göster
.venv\Scripts\python.exe -m app.database migrate
.venv\Scripts\python.exe -m app.database status

# Katalogu veritabanına eşitle (önce deneme; keşif kataloğu değiştirdikten sonra)
.venv\Scripts\python.exe -m app.database sync-catalog --dry-run
.venv\Scripts\python.exe -m app.database sync-catalog

# Fiyat toplama turu: sitelere istek atar ve sonuçları veritabanına yazar
.venv\Scripts\python.exe -m app.collection --prefix poco_   # yalnız POCO (4 sayfa)
.venv\Scripts\python.exe -m app.collection                  # bütün etkin sayfalar (~31 dk)

# Zamanlanmış tur: görevi kur (tekrar çalıştırmak yeniden kurar), hemen bir kez
# başlat, son/sonraki çalışmayı göster, kaldır. Loglar: data\logs\tur_*.log
powershell -ExecutionPolicy Bypass -File scripts\zamanlayici_kur.ps1
Start-ScheduledTask -TaskPath '\FiyatTakip\' -TaskName 'FiyatToplamaTuru'
Get-ScheduledTaskInfo -TaskPath '\FiyatTakip\' -TaskName 'FiyatToplamaTuru'
powershell -ExecutionPolicy Bypass -File scripts\zamanlayici_kur.ps1 -Kaldir

# Biçim ve kalite kontrolü (CI'daki gibi)
.venv\Scripts\python.exe -m black --check app tests tools
.venv\Scripts\python.exe -m flake8 app tests tools

# Keşif: önce kataloğu değiştirmeden rapor
.venv\Scripts\python.exe -m app.discovery --dry-run --target apple_iphone_15

# Keşif: doğrulanan yeni sayfaları kataloğa ekle
.venv\Scripts\python.exe -m app.discovery --target apple_iphone_15

# Zamanlanmış keşfin komutu (elle de çalışır): katalog yazılmaz; log data\logs\kesif_*.log,
# rapor data\discovery\kesif_*.json (aynı tarih-saat damgası)
.venv\Scripts\python.exe -m app.discovery --scheduled --dry-run --target apple_iphone_15

# İncelenen önizleme raporunu siteye gitmeden kataloğa ekle
.venv\Scripts\python.exe -m app.discovery --apply-report data\discovery\kesif_<tarih-saat>.json

# Zamanlanmış keşfin otomatik kabul modu (kurulu haftalık görev bunu çalıştırır)
.venv\Scripts\python.exe -m app.discovery --scheduled --auto-accept

# Haftalık keşfi Görev Zamanlayıcı'ya kur (her Pazar 14:00): seçeneksiz önizleme
# modu, -OtomatikKabul ile otomatik kabul modu (bugün kurulu olan); -Kaldir siler
powershell -ExecutionPolicy Bypass -File scripts\kesif_zamanlayici_kur.ps1
powershell -ExecutionPolicy Bypass -File scripts\kesif_zamanlayici_kur.ps1 -OtomatikKabul

# Keşif tanılaması: rapor + her kararın izi (katalog değişmez)
.venv\Scripts\python.exe tools\live_discovery_check.py apple_iphone_15 --trace

# Adres kimliği incelemesi için tek hedefin ham yanıtları (yeni klasör gerekir)
.venv\Scripts\python.exe tools\live_discovery_check.py apple_iphone_15 --save-responses data\kimlik_iphone15_20261006

# Canlı fiyat kontrolü: katalogdaki bütün sayfalar (veya yalnız bir ön ek)
.venv\Scripts\python.exe tools\live_scraper_check.py
.venv\Scripts\python.exe tools\live_scraper_check.py apple_iphone_15_128
.venv\Scripts\python.exe tools\live_scraper_check.py samsung_ | Out-File -Encoding utf8 data\scraper_samsung.json
```

Ham keşif kaydında her platform/hedef alt klasörüne HTML/JSON dosyaları ve
`index.json` yazılır. Index, ilk istenen adresi, zamanı, dosya adını veya okuma
hatasını ve o ana kadarki gerçek istek sayısını tutar; yönlendirme son adresini
tutmaz. Başarılı yanıt ayrıştırmadan önce kaydedilir, böylece bozuk JSON da
incelenebilir. HTTP hata gövdeleri kaydedilmez. `report.json` seçilen klasörde
olur; mevcut standart rapor korunur. `--save-responses` karar izini de basar,
ek HTTP isteği göndermez, bütçeyi veya kilidi değiştirmez. Hedef verilmezse ya
da klasör zaten varsa tarama başlamaz (kod 2); kilit meşgulse kod 3. Disk hatası
çalışmayı keser. Canlı kontrolü kullanıcı tur saatleri dışında çalıştırır;
kanıt dosyaları `data/` altında tutulur ve Git'e gönderilmez.

Türkçe karakterlerin terminalde doğru görünmesi için oturum başında bir kez
`[Console]::OutputEncoding = [Text.Encoding]::UTF8` çalıştırın. Keşif hedef
başına yaklaşık 1,5 dakika sürer (istekler arası 3 sn bekleme); 24 etkin hedefin
tamamı yaklaşık 35 dakikadır (5 Ekim 2026 ölçümü: 34 dk). Elle çalıştırılan keşif raporu her çalışmada
(dry-run dahil) `data/discovery_report.json` dosyasının üzerine yazılır; saklamak
istediğiniz raporu kopyalayın. `--scheduled` ise her çalışmada tarihli yeni bir
dosya yazar (`data/discovery/kesif_<tarih-saat>.json`) ve hiçbirinin üzerine
yazmaz. Her iki modda da komutun sonunda stderr'e tek satırlık özet ile rapor
yolu yazılır; stdout elle çalıştırmada yalnız rapor JSON'u kalır.

`--target` verilmezse bütün etkin hedefler taranır. Eski taslaklar
`_eski_taslaklar/` klasörüne taşındığı için Black/Flake8 CI'daki gibi bütün
klasörde çalıştırılabilir (yukarıdaki biçim komutları).

Gerçek dosyalara dokunmadan denemek için ortam değişkeni kullanılabilir:

```powershell
$env:CATALOG_PATH = "data/deneme_katalog.json"   # kataloğun kopyası
$env:DISCOVERY_PATH = "data/deneme_hedef.json"   # geçici hedefler
# deneme bitince (ya da yeni bir terminal açın):
Remove-Item Env:CATALOG_PATH, Env:DISCOVERY_PATH
```

**Dikkat:** Bu değişkenler o terminal kapanana kadar geçerlidir. Toplama turu
(`python -m app.collection`) ile `sync-catalog` `CATALOG_PATH`'i de okur
(`DISCOVERY_PATH` yalnız keşfi etkiler). Deneme
kataloğu tanımlıyken tur veya eşitleme çalıştırılırsa deneme kayıtları gerçek
veritabanına yazılır ve silinmez (kayıt silinmez kuralı); sonra gerçek katalog
aynı kimliği başka bir telefona verirse eşitleme çakışmayla durur. Zamanlanmış
tur kendi ortamında çalıştığı için etkilenmez.

## Yeni telefon ekleme: bütün kurallar

`config/discovery.json` içine marka ve **tam** model yazılır; adres girilmez:

```json
{
  "targets": [
    {"key": "apple_iphone_17_pro", "brand": "Apple", "model": "iPhone 17 Pro"},
    {"key": "samsung_galaxy_s25", "brand": "Samsung", "model": "Galaxy S25"},
    {"key": "poco_x6_pro", "brand": "POCO", "model": "X6 Pro"},
    {
      "key": "xiaomi_redmi_note_14_pro_4g",
      "brand": "Xiaomi",
      "model": "Redmi Note 14 Pro",
      "network": "4G",
      "exclude_terms": ["5G"]
    },
    {"key": "xiaomi_redmi_note_14_pro_5g", "brand": "Xiaomi", "model": "Redmi Note 14 Pro 5G"}
  ],
  "max_search_pages": 20,
  "max_product_pages": 100,
  "max_requests": 200
}
```

- `model` alanına marka yazılmaz; ürün adı `marka + model + kapasite` olarak
  oluşur ("Xiaomi 14T Pro 512 GB"). `key` biçimi `marka_model`dir.
- `model: "iPhone 16"` → iPhone 16 Pro, Plus, 16e **kapsanmaz**; bunlar ayrı
  hedeftir. Aynı şekilde Galaxy S25 hedefi S25 Edge, S25+, S25 FE ve S25
  Ultra'yı kapsamaz.
- **Marka, sitedeki marka etiketidir.** POCO iki sitede de "POCO" markasıyla
  listelenir; `brand: "Xiaomi"` ile hiçbir POCO sayfası bulunmaz. Galaxy A55 /
  A54 gibi yalnız 5G'si olan modellerde adına "5G" yazılmaz; yazılırsa
  başlığında 5G geçmeyen doğru sayfalar kaçar.
- **`exclude_terms`** (isteğe bağlı): Aynı adı taşıyan farklı telefonları
  başlıktan ayırır. Terim bütün sözcük olarak aranır: "5G" ifadesi "Note 14
  Pro 5G" içinde bulunur; "5 GB RAM" ve 4G telefonların "4.5G" yazımı içinde
  bulunmaz. Genel bir "5G ayrı model" kuralı bilinçli olarak yoktur.
- **`network`** (isteğe bağlı, `"4G"` veya `"5G"`): Başlığı ağ türünü
  söylemeyen modeller için. Sayfanın yapısal "Mobil Bağlantı Hızı" değeri
  hedefle çelişirse (ör. 4G hedefine 5G sayfa) sayfa reddedilir; değer "4.5G"
  ise 4G sayılır; alan boşsa sayfa **geçer**, çünkü satıcılar bu alanı çoğu
  zaman doldurmaz. 4G hedefi bu yüzden `exclude_terms: ["5G"]` ile birlikte
  kullanılır: başlıkta veya özellikte 5G yazan sayfa dışlanır, gerisi 4G
  sayılır. Karar 27 Eylül 2026'da kullanıcıyla verildi; bilinen sınırı
  aşağıdadır.
- Bugün gerçek dosyada 25 hedef vardır: Apple 9 (iPhone 15/16/17, her birinin
  Pro ve Pro Max'i), Samsung 8 (S25, S25 Ultra, S24, S24 Ultra, S24 FE, S23 FE,
  A55, A54), Xiaomi 6 (14T Pro, 13T Pro, Redmi Note 14 Pro 4G/5G, Redmi Note
  13 Pro 4G/5G) ve POCO 2 (X6 Pro; X5 Pro iki sitede de satılmadığı için
  `active: false`).

## Eklenti yükleyicilerinin sözleşmesi

Eklenti, bir pazaryerini okuyan platform sınıfıdır. İki yükleyici aynı anahtar
biçimini (`[a-z][a-z0-9_]*`) ve soyut olmayan taban sınıfı şartını denetler;
geçersiz anahtar için modül içe aktarılmaz. Görevleri farklıdır:

| Yükleyici | Sonuç ve hata davranışı |
|---|---|
| `create_scraper` | `BaseScraper` nesnesini verilen hosts/runtime ile kurar. Yükleme veya kurulum hatası `FetchError("plugin", ...)` olur; asıl hata `__cause__` içinde korunur. Toplama ilgili sayfaya `error/plugin` yazar, diğer sayfalarla devam eder. |
| `_adapter` | `BaseDiscovery` sınıfını döndürür; nesneyi keşfin `run` akışı target/config/runtime ile kurar. Modül yoksa `ImportError`, sınıf eksik/yanlış/soyutsa `ValueError` yükselir; hatalı adaptör keşfi durdurur. |

Keşifte `OSError`, `ValueError` ve `ImportError` komutta açıklamalı hata ve
çıkış 1 üretir. Yükleme/kurma sırasındaki beklenmeyen `RuntimeError` veya
`TypeError` elle çalıştırmada yukarı iletilir (komut satırında ayrıntılı hata
çıktısı); zamanlanmış giriş ayrıntıyı loga yazar ve çıkış 1 döndürür. İlk
adaptör daha önce tamamlandıysa kapanmıştır; sonuçlandırma yapılmadığı için
katalog ve önceki rapor korunur, yeni sonuç raporu yazılmaz. Ortak kilit
bırakılır; sonraki keşif başlayabilir.

Ctrl+C (`KeyboardInterrupt`) olağan eklenti hatasına çevrilmez. Keşfin elle
ve zamanlanmış girişlerinde yukarı iletilir; kilit yine bırakılır.
Zamanlanmış keşif logunda başlangıç kalır, normal `Çıkış kodu:` satırı
yazılmaz. Scraper factory de Ctrl+C'yi `plugin` olarak sarmaz.

## Keşif nasıl çalışır

### Örnek: iPhone 15 128 GB baştan sona

1. `discovery.json` içinde `Apple / iPhone 15` hedefi var.
2. Keşif Trendyol aramasında yaklaşık 120 iPhone kartı görür. 5'i gerçekten
   iPhone 15'tir, gerisi (iPhone 16, 15 Pro, 17…) başka model diye elenir.
   Hepsiburada'da tek bir ürün sayfasındaki seçenek listesinden 16 renk/kapasite
   sayfasına ulaşır.
3. Doğrulanan sayfalar kataloğa yazılır: iPhone 15 128 GB için Trendyol'da 3,
   Hepsiburada'da 6 sayfa.
4. Scraper bu 9 sayfanın her birindeki satıcıları karşılaştırır (ör. Hepsiburada
   Mavi sayfasında 11 satıcı).
5. Ürünün takip edilen en ucuz teklifi: 56.999 TL (tarayıcıda doğrulandı).

### Trendyol

1. Ana sayfa açılarak oturum hazırlanır. HTML arama sayfası (`/sr`) **açılmaz**:
   içeriği kullanılmıyordu ve canlıda HTTP 403 ile engelleniyordu (25 Eylül
   2026'da 9 modelin 6'sı bu yüzden taranamadı); API'ye yalnız `Referer` olarak
   gönderilir.
2. Arama API'sine "marka + model" sorulur.
3. Yanıttaki filtre listesinden marka ve **telefon kategorisi** filtresi bulunur;
   kılıf ve aksesuarlar böylece elenir. Marka önce `canonicalFilters`, yoksa
   `aggregation/WebBrand` içinden okunur. "Yenilenmiş Cep Telefonu" telefon
   kategorisi sayılmaz. Birden çok geçerli telefon kategorisi varsa yalnızca ilki
   taranır ve rapora `category_partial` yazılır.
4. Sayfalar kaynaktaki "sonraki" bağlantısıyla gezilir (en fazla 20 sayfa).
   Toplam ürün sayısı tutmazsa `count_mismatch` raporlanır.
5. Her arama kartı için karar verilir: kabul, `excluded_word` (kılıf, yenilenmiş…),
   `other_model` (Pro, 16e, başka model), `excluded_term`, `brand`, `category`.
6. Kabul edilen kartların ürün grubu için Trendyol'un "renk/kapasite seçenekleri"
   listesi (`slicing-attributes`) okunur; kardeş sayfalar eklenir. Bağlantının
   rengi bu listedeki addır (sayfanın renk seçicisinde görünen ad, ör. "Abis");
   ürün listede yoksa satıcının "Renk" özelliği kullanılır.
7. Aday adresinin ürün yolundaki `-p-<id>` kimliği, arama/varyant kaynağındaki
   ürün kimliğiyle eşleştirilir. Eksik veya farklı kimlikte istek gönderilmeden
   `identity` hatası verilir; raporda `candidate_rejected` olur, diğer adaylarla
   devam edilir. Sorgu parametresindeki kimlik eşleşme için kullanılmaz.
   Reddedilen adres ürün sayfası deneme sınırından bir hak tüketir; HTTP istek
   bütçesini tüketmez. Geçerli sayfa açılınca sayfanın kendi ürün kimliği, marka,
   telefon kategorisi, model, kapasite ve (hedefte `network` varsa) "Mobil Bağlantı
   Hızı" ayrıca doğrulanır; başka ürüne yönlendirme kimlik denetimini aşamaz.

### Hepsiburada

1. Arama sayfası (`ara?q=…`) okunur. Varsa model filtresi sayfasına
   (`…-xc-…`) geçilir; bulunamazsa `model_filter_missing` raporlanır.
2. Ürün kartları toplanır. Kart iki biçimde olabilir:
   `-p-HBCV…` (ürün sayfası) veya `-pm-HBC…` (grup sayfası). Grup sayfası
   **aday olmaz**; yalnızca gerçek ürün SKU'larına çözülür.
3. Arama API'si denenir; bugün engellenir (`search_api: blocked`). Engel olsa da
   HTML'den bulunanlar korunur.
4. Her ürün sayfası açılır, kimlik doğrulanır (hedefte `network` varsa ürün
   özelliklerindeki "Mobil Bağlantı Hızı" kaydı da) ve sayfadaki
   `allVariantCombinations` (bütün renk/kapasite seçenekleri) kuyruğa eklenir.
   Stoksuz olduğu için aramada görünmeyen kapasiteler de böyle bulunur.

Canonical adresi aynı ürünün adresi olmayabilir. Keşif yalnız
`https://www.hepsiburada.com/` adresinde, ürün yolundan çıkarılan SKU beklenen
SKU'ya **tam eşitse** canonical adresini kullanır; küçük harfli SKU eşdeğerdir.
Farklı SKU, grup/kategori adresi, başka alan adı veya yalnız sorguda geçen SKU
canonical olarak kullanılmaz; doğrulanmış istenen ürün adresi korunur, geçerli
aday sırf canonical farklı diye reddedilmez.

### Otomatik güvenli kabul

`app/discovery/acceptance.py`, aynı sayfanın ürün koduna bağlı kimlik
kanıtlarını toplar ve `verified` (doğrulandı), `mismatch` (uyuşmazlık),
`insufficient` (kanıt yetersiz) kararı verir. Model, marka, kapasite, renk,
yeni telefon kategorisi ve kendi JSON-LD Product/ProductGroup teklifindeki
NewCondition birlikte aranır. Garanti yazısı yeni ürün kanıtı değildir;
yenilenmiş/aksesuar/ikinci el/teşhir kanıtı NewCondition etiketinden önce gelir.
Fiyat/satıcı/stok, kimlik kararı yerine kullanılmaz; kimliği tam stoksuz aday
kabul edilebilir. Yanlış başka SKU'nun fiyatı veya özelliği ödünç alınmaz.

Ağ ayrımı hedefin kimliğine dahilse olumlu kanıt gerekir: kendi başlığında
açık 5G veya aynı kodun ağ özelliği. 5G yazmaması 4G kanıtı değildir; 4.5G
4G sayılır. Açık ağ, kapasite, renk veya RAM çelişkisi ret nedenidir; RAM'ın
bulunmaması tek başına ret değildir. Hepsiburada özellikleri yalnız ürünün
ana `productState.product`/ürün kökü içinde okunur; önerilen ürüne girilmez.
Renk kendi varyantı/ürün alanından alınır; kayıtlı satışa kapalı örneklerde
yalnız tam başlığın açık renk son eki de kullanılır. Sınırlı renk sözlüğü,
tanınmayan renkleri görselden tahmin etmez (bilinen sınırı: "Bilinen sınırlar"). Blue/Mavi eşitliği kayıtlı 6 Ekim
örneğine dayanır; genel WebColor “Çok Renkli” özgül renk sayılmaz.

Etkin, tanımlı hedeflerin doğrulanan yeni kapasiteleri yeni ürün oluşturabilir;
tanımlanmayan marka/model oluşturulmaz. Mevcut ürün/listing kimlikleri, pasif
kayıtlar ve görülmeyen bağlantılar korunur. Aynı platform kodu aynı taramada
çelişkili kimlikler gösterirse grubun tamamı dışarıda tutulur. Bir arama
yolunun engellenmesi, kendi sayfasında yeterli kanıt bulunan adayı topluca
engellemez; `complete=false` ve kısmi çıkış kodu yine korunur.

`config/discovery.json` içindeki `retired_listing_bindings`, kaldırılan
bağlantının platform kodunu, eski listing_id, product_id ve product_key bağını
saklar. İlk kayıt HBCV00008BCY51 → ürün 58 / Galaxy S25 512 GB'dır. Keşif DB'ye bağlanmaz.
Kaldırılmış bağlantı yalnız tam yeni kanıtla aynı ürüne eski kimliğiyle
dönebilir; başka ürüne taşınamaz. Katalogda hâlen bulunan pasif bağlantı
kendiliğinden açılmaz. Gelecekte hedefli kalıcı kaldırmada bu kayıt güncellenir.

Komut seçenekleri:

```powershell
# Tek seferlik toplu önizleme; katalog yazmaz.
.venv\Scripts\python.exe -m app.discovery --scheduled --dry-run
# Yalnız ayrıca kabul edilip devreye alındıktan sonra otomatik ekleme.
.venv\Scripts\python.exe -m app.discovery --scheduled --auto-accept
```

`--auto-accept` ile `--dry-run` birlikte kullanılamaz. `--scheduled` açıkça bu
iki moddan birini ister. Eski seçeneksiz normal yazma yolu da aynı kanıt
katmanını kullanır. Yeni günlük görev, 24 saat bekleme veya süre dolunca
kabul yoktur; belirsiz aday sonraki normal haftalık keşifte tekrar görülebilir.

**Rapor ve kesinti:** `results[].decisions` kendi ürün kodunu, URL'yi,
gözlem zamanını, UTF-8 HTML içerik parmak izini, alan/değer/kaynak/owner_id
kanıtlarını ve gerekçeleri içerir. HTML alınamayan sayfada boş içerik izi ve
eksik kanıt kararı kalır; tam HTML elde edilmiş gibi gösterilmez. Katalog
yazmadan önce kararlar ve önceki/beklenen sonraki katalog parmak izleri
atomik rapora, ardından Git dışı `data/discovery/pending_<katalog>.json`
kaydına yazılır. Sonra katalog atomik değiştirilir, sonuç raporu tamamlanır.
İki dosyanın tek atomik işlem olduğu varsayılmaz. Sonuç durumları:

| `application.state` | Anlamı |
|---|---|
| `preview` | Yazmadan hesaplanan eklemeler; katalog değişmedi. |
| `prepared` | Yazma niyeti kalıcı kaydedildi; son durum henüz kesinleşmedi. |
| `applied` / `unchanged` | Beklenen katalog yazıldı / katalog baytları değişmedi. |
| `not_applied` | Kesinti sonrası mevcut parmak izi önceki katalogla aynı; eski adaylar kendiliğinden yeniden uygulanmadı. |

Sonraki başlangıç, yarım işlemin iki parmak izini kontrol eder. Katalog
beklenen son durumdaysa uygulandı, önceki durumdaysa uygulanmadı olarak kaydı
tamamlar. İkisinden farklıysa yeni tarama/yazma durur; otomatik geri alma
yoktur. Rapor hazırlanamıyorsa katalog değişmez. Son rapor yazılamadığında
katalog değişmiş olabilir; çıkış1 “hiçbir şey yazılmadı” garantisi değildir.
Yerel rapor, katalog ve hedef ayarı parmak izleri yeniden denetlenir; raporun
kendi kabul iddiası yerine kanıttan karar tekrar hesaplanır.

### Katalogla birleştirme (`service.py`)

- Ürün kimliği: marka + model + kapasite. Bağlantı kimliği: platform + sitedeki
  ürün kimliği/SKU. Yeni bağlantı adı `platform_urunkimligi` biçimindedir.
- Mevcut kimlikler değişmez; kimlik başka ürün için tekrar kullanılmaz; bu
  taramada görülmeyen eski kayıtlar **silinmez**.
- Aynı keşfi tekrar çalıştırmak çift kayıt üretmez (canlıda doğrulandı: ikinci
  çalışmada sıfır ekleme, dosya bayt düzeyinde aynı).
- Katalogdaki bir sayfa bu kez başka ürün (ör. başka kapasite) olarak görülürse
  o aday yazılmaz, mevcut kayıt korunur ve rapora `catalog_conflict` yazılır;
  diğer geçerli adaylar yine eklenir.
- Dosya kilit altında yeniden okunur ve atomik olarak (geçici dosya + yer
  değiştirme) yazılır. `--dry-run` kataloğa hiç yazmaz.

### İncelenen raporu uygulama (`--apply-report`)

Yazmanın tek yolu keşfi `--dry-run` olmadan yeniden çalıştırmak olsaydı, ikinci
tarama incelenenden farklı sayfalar bulabilirdi: Hepsiburada'nın genel
aramasında yalnız ilk 36 kart görünür ve bu kartlar her seferinde değişebilir.
`python -m app.discovery --apply-report RAPOR` bu yüzden siteye gitmeden **raporun
kendi adaylarını** kataloğa birleştirir:

- Rapor bir önizleme (`dry_run: true`) olmalıdır; kataloğu zaten yazmış bir
  çalışmanın raporu reddedilir. `--trace` çıktısı gibi sarmalanmış ya da bozuk
  dosya da rapor sayılmaz (sözleşme katıdır). Dosyanın başında BOM olabilir.
- Kanıtlı raporlarda (otomatik kabul sonrası biçim) kanıt kararı, katalog/ayar/rapor
  parmak izleri ve beklenen son katalog denetlenir. Eski raporlar okunabilir; fakat kanıtsız rapordan
  yeni ekleme yapılmaz. Aynı raporun zaten uygulanmış kayıtları çoğaltılmaz.
- Birleştirme canlı yazmayla aynı koddur (`service.py`): kilit altında
  yeniden okuma, aynı `merge_catalog`, yalnız içerik değiştiyse yazma. Önizleme
  ve uygulama, aynı başlangıç kataloğundan canlı yazmayla bayt bayt aynı dosyayı verir.
- **Önizlemeyi aşmama kuralı:** hesaplanan eklemeler, raporun `added_products` ve
  `added_listings` listesinin alt kümesi olmalıdır. Katalog önizlemeden sonra
  elle değiştiyse (ör. bir sayfa silindi) önizlemede görünmeyen bir ekleme
  çıkabilir; o durumda hiçbir şey yazılmaz ve yeni bir önizleme istenir. Önizlemede
  görünen ama artık katalogda olan kayıtlar sorun değildir: aynı rapor ikinci kez
  uygulanırsa eklenecek bir şey kalmaz ve dosya yazılmaz.
- Siteye gitmez; adaptör hiç çalışmaz. Yalnız katalog kilidini alır, `data/scrape.lock`'u
  almaz: fiyat turu sürerken de çalışır (tur kataloğu yalnız başlarken okur, yazma
  atomiktir).
- Eklenen her ürün ve sayfa `+` ile listelenir; katalogla çelişen aday
  (`catalog_conflict`) yazılmaz ve ayrıca gösterilir.
- Tek bir sayfa istenmiyorsa ayrı seçenek yoktur: rapor uygulanır, sonra ilk fiyat
  turundan önce `catalog.json`'da o sayfanın `"active": false` yapılır. Bu kalıcıdır;
  sonraki raporlar o sayfayı yeniden önermez.
- Kataloğa giren sayfa en geç bir sonraki fiyat turunda veritabanına eşitlenir;
  `config/catalog.json` değişikliği Git'e commit edilmelidir (geri alınırsa
  `product_id` yeniden kullanılabilir ve eşitleme `CatalogConflict` verir).

### Rapor: `data/discovery_report.json` (zamanlanmışta `data/discovery/kesif_<tarih-saat>.json`)

| Alan | Anlamı |
|---|---|
| `generated_at` | Raporun üretildiği an (UTC); `--apply-report` hangi önizlemeyi uyguladığını bununla gösterir. Alan eklenmeden önce yazılmış raporlarda yoktur (`null`). |
| `dry_run` | Çalışma katalog yazmadan mı yapıldı. |
| `complete` | Kullanılan kaynakların tamamı tarandı mı. Bütün pazaryerinin bulunduğunu **kanıtlamaz**. |
| `results` | Hedef × platform başına ayrıntı: kanıtı yeterli adaylar, sayfa kararları (`decisions`), uyarılar, taranan arama/ürün sayfası sayısı. RAM yalnız kanıt varsa doldurulur; garanti kimlik yerine geçmez. |
| `application` | Yazma işleminin durumu, katalog yolu, önceki/sonraki katalog ve ayar/rapor parmak izleri. Eski raporda `null`; yeni ekleme yetkisi vermez. |
| `added_products`, `added_listings` | Önizleme/hazırlıkta planlanan, `applied` sonucunda eklenen ürünler/sayfalar; `not_applied` durumda eklenmemiştir. |
| `existing_listings` | Yeniden görülen, zaten katalogda olan sayfalar. |
| `retained_unobserved_listings` | Etkin olduğu hâlde bu taramada görülmeyen, katalogda korunan sayfalar; güncel teklif sayılmaz. Pasif sayfalar listelenmez. |
| `pending` | Taramayı kısmi yapan nedenler (aşağıdaki tablo). |
| `rejected` | Reddedilen sayfalar ve nedenleri (gözlenen ürün adıyla) ve `catalog_conflict` kayıtları. |
| `observed_colors` | Kapasite ve platform bazında bulunan renkler; pazaryerinin eksiksiz renk listesi değildir. |
| `coverage_changes` | Platform başına bu çalışmada eklenen bağlantı sayısı. |

`pending` içindeki uyarılar (taramayı kısmi yapar):

| Uyarı | Anlamı |
|---|---|
| `search_fetch` | Arama aşaması hiç tamamlanamadı; ayrıntıda hata kodu, mesaj ve adres var (ör. `network: …` bağlantı kesildi, `blocked: Kaynak HTTP 403 …`). |
| `search_api` | Hepsiburada arama API'si engellendi. |
| `model_filter_missing` | Hepsiburada model filtresi sayfası bulunamadı; genel arama sayfası kullanıldı. |
| `html_partial` | Sayfadaki kart sayısı sitenin bildirdiği toplamdan az. |
| `filter_unavailable` | Trendyol telefon kategorisi filtresi alınamadı ya da bulunamadı. Filtre isteği hata verdiyse ayrıntıda hata kodu ve mesajı bulunur; aynı arama için uyarı bir kez yazılır. |
| `category_partial` | Birden çok telefon kategorisi var, yalnızca ilki tarandı. |
| `count_mismatch` | Trendyol'un bildirdiği toplamla gelen ürün sayısı farklı. Bugünkü nedeni reklam kartları: sonuçların arasına giren reklamlar 2–3 ürünü hiçbir sayfaya düşürmez (bkz. bilinen sınırlar). |
| `search_limit`, `product_limit` | Sayfa veya ürün sınırı doldu. |
| `repeated_page` | Site aynı sonuç sayfasını tekrar döndürdü; sayfalama durduruldu. |
| `variant_fetch`, `missing_variants` | Varyant listesi alınamadı veya boş geldi. |
| `group_url_pending` | Hepsiburada arama API'sinin varyant kaydındaki adres ne ürün (`-p-`) ne grup (`-pm-`) biçiminde; aday çözülemedi. API bugün engelli olduğundan (`search_api`) fiilen görülmez. HTML arama sayfasında bu iki kalıba uymayan bağlantılar (menü, kategori…) kart sayılmaz ve uyarısız atlanır. |
| `evidence_missing` | Kendi ürün koduna bağlı kritik kimlik/yeni ürün kanıtı eksik. Aday eklenmez. |

`rejected` içindeki kayıtlar (tek bir aday atlanır, tarama sürer):

| Kayıt | Anlamı |
|---|---|
| `candidate_rejected` | Aday sayfa doğrulanamadı; ayrıntıda neden ve ürün adı var (başka model, kapasite, ağ türü, yurt dışı sürüm, aksesuar…). Taramayı da kısmi sayar. |
| `catalog_conflict` | Sayfa katalogda başka bir ürüne bağlı; aday yazılmadı, mevcut kayıt korundu. |
| `identity_mismatch` | Kendi ürün koduna bağlı alanlarda açık model/kapasite/ağ/renk/RAM/kapsam çelişkisi. |

Komutun çıkış kodu: `0` tam tarama, `2` kısmi tarama (doğrulanmış kayıtlar yine
eklenir; Hepsiburada arama API'si engelli olduğu için bugün her zaman 2; katalogla
çelişen aday, `catalog_conflict`, de taramayı kısmi sayar; hiç etkin hedef
yoksa sonuç listesi boştur ve çıkış yine 2'dir), `1` keşif başlatılamadı
(`--target` ile verilen anahtar `discovery.json`'da yok, ayar dosyası bozuk,
platform adaptörü yüklenemedi…) **ya da** tarama bitti ama sonuç kataloğa veya
rapora yazılamadı (disk, kilit zaman aşımı; mesaj "Tarama bitti ama sonuç
yazılamadı" der; kalıcı hazırlık kaydı varsa uzlaştırma gerekir), `3` kilit meşgul (tur, başka bir keşif veya canlı kontrol
sürüyor). `--apply-report` için: `0` katalog güncellendi ya da eklenecek bir şey
kalmadı, `2` güncellendi ama katalogla çelişen aday atlandı, `1` rapor/ayar/
yazma hatası (geçersiz önizleme veya yazma öncesi uyuşmazlıkta katalog yazılmaz;
son rapor hatasında katalog değişmiş olabilir). `--scheduled` kodları tarama kodlarıyla aynıdır;
ek olarak log dosyası açılamazsa `1` döner ve keşif hiç başlamaz. Argüman hatası
(`--scheduled` için mod seçmeden, iki modu birlikte veya `--apply-report` başka seçenekle) çıkış `2`
verir ve hiçbir şey yazmaz.

Her taramanın sonunda stderr'e tek satırlık özet yazılır, ör. `Özet: yeni ürün 1 ·
yeni sayfa 5 (hepsiburada 2, trendyol 3) · zaten kayıtlı 310 · görülmeyen 4 ·
çakışma 0 · reddedilen 7 · tam sonuç 24/48 · uyarı search_api 24`. Çıkış kodu
Hepsiburada arama API'si engelli olduğu için bugün hep `2` olduğundan tek başına
bir şey söylemez; uyarılar `pending` nedenlerine göre sayıldığı için beklenen
`search_api` ile gerçek sorunlar (ör. `search_fetch`, `variant_fetch`) bu satırdan
ayırt edilir. "Zaten kayıtlı", bu taramada yeniden görülen katalog sayfalarıdır;
raporda katalogun toplam sayfa sayısı yoktur.

Çıktı UTF-8'dir; dosyaya yönlendirildiğinde de Türkçe karakterler
bozulmaz. `catalog.json`, `discovery.json` ve `runtime.json` başında BOM olsa
da okunur (PowerShell'in `Out-File -Encoding utf8` ile yazdığı kopya gibi);
katalog her zaman BOM'suz ve LF satır sonuyla yazılır. Trendyol'da arama sayfası
sınırı (`max_search_pages`) dolunca sonraki sayfa istenmez, `search_limit`
yazılır.

## Fiyat okuma nasıl çalışır

Ortak HTTP katmanı, HTML ve JSON gövdesini `curl_cffi`'nin `content_callback`
işleviyle parça parça biriktirir. Sınır 8 × 1024 × 1024 bayttır: tam eşik
kabul edilir, aşan parça tamponda tutulmadan aktarım durdurulur. Başarılı HTTP
yanıtındaki taşma `too_large` verir ve yeniden denenmez. Gövde büyük olsa da
HTTP durumu biliniyorsa önceliği korunur: engel `blocked`, diğer 4xx
`http_error`, 5xx normal `network` tekrarlarıdır; yönlendirme hedefi yine
denetlenir. Her istek/yönlendirme/tekrarda boş tampon açılır. `Content-Length`
başlığına güvenilmez; alınan gövde baytları sayılır. Bu, bütün programın bellek
kullanımı için 8 MB garantisi değildir; metin/JSON ayrıştırması ayrıca bellek kullanır.

### Trendyol (sayfa başına 1 istek)

1. Ürün sayfası indirilir; `window['__envoy__SHARED_PROPS']` içindeki ürün verisi okunur.
2. Kimlik doğrulanır: URL'deki ürün kimliği, model ve kapasite (başlık +
   `Dahili Hafıza`/`slicingAttributes`).
3. Ana satıcı (buybox) ve `otherMerchants` teklifleri okunur.
4. Elenenler: stok dışı, yenilenmiş/ikinci el/teşhir, fiyatı veya satıcısı eksik,
   başka ürün sayfasına (başka renk) ait teklifler.
5. Kalanlardan en ucuzu seçilir; eşitlikte satıcı adına göre karar verilir.

### Hepsiburada (sayfa başına 3 istek; Tükendi ise 2)

1. Ürün sayfası indirilir; kimlik doğrulanır (JSON-LD adları, sayfa başlığı ve
   aynı SKU'nun bütün seçenek listelerindeki kapasite/renk tutarlılığı).
   Çelişki `identity` hatasıdır; satıcı/fiyat API'sine geçilmez.
2. `/api/v1/product/listings/{sku}` ile bütün satıcılar alınır.
3. Satıcı yoksa veya her satıcı açıkça satılamaz (`isSalable: false`) ise sonuç
   `Tükendi` olur. Bir satıcıda stok alanı hiç yoksa sonuç Tükendi **değil**,
   `parse` hatasıdır; site alanı değiştirirse sayfalar sessizce Tükendi olmaz.
   Listede sözlük olmayan bir satıcı kaydı varsa (ör. `[null]`) yanıt `parse`
   hatasıdır; kayıt atılıp boş liste veya daha dar satıcı kapsamı üretilmez.
   Bu denetim 6 Ekim ikinci denetiminde bulunan yanlış Tükendi ihtimalini kapatır.
4. Aynı oturumla `otherMerchants` fiyat isteği gönderilir; yenilenmiş/teşhir
   teklifleri elenir, en ucuz geçerli teklif seçilir.

### Fiyat ve stok kuralları

- **Güncel fiyat:** Sayfada gösterilen, koşulsuz indirimli fiyat.
  Trendyol'da `discountedPrice` ile `sellingPrice`'ın küçüğü (ör. "Net 400 TL
  İndirim" → 59.599 TL); Hepsiburada'da `discountedPrice`, yoksa `price`.
  "2 adet ve üzeri", sepet veya kupon koşullu indirimler dahil edilmez.
- **Üstü çizili fiyat:** Sayfada çizili görünen fiyat (Trendyol'da `originalPrice`
  ile `sellingPrice`'ın büyüğü); güncel fiyattan büyük değilse `null`. Üstü çizili
  fiyat ileride indirim tahmininin referansı **değildir**.
- Para kuruş cinsinden tam sayıdır: `5724900` = 57.249,00 TL.
- **Tükendi** yalnızca açık stok sinyaliyle verilir: Trendyol'da sayfadaki uygun
  teklifler açıkça stok dışıysa, Hepsiburada'da satıcı listesinde satılabilir
  teklif yoksa. Ağ/ayrıştırma hatası, engellenme veya çelişkili yanıt (satıcı
  listesi "satılabilir" deyip fiyat API'sinin boş dönmesi) **Tükendi değildir**,
  hata olarak raporlanır.
- **Kritik Stok** yalnızca Trendyol'un açık sinyaliyle (`isRunningOut`) verilir;
  Hepsiburada bu sinyali sağlamadığı için orada hiç üretilmez.

### Dönen alanlar: `PriceObservation`

| Alan | Anlamı |
|---|---|
| `listing_id` | Katalogdaki kalıcı bağlantı kimliği |
| `product_id` | Model ve kapasite düzeyindeki ürün kimliği |
| `platform` | Teklifin geldiği platform |
| `product_name`, `product_url` | Katalogdaki ürün adı ve kontrol edilen sayfa |
| `current_price` | Güncel fiyat (kuruş) |
| `original_price` | Üstü çizili fiyat (kuruş) veya `null` |
| `seller_name`, `seller_rating`, `seller_rating_scale` | Seçilen teklifin satıcısı ve puanı (puan yoksa `null`) |
| `stock_status` | `Stokta Var`, `Kritik Stok` veya `Tükendi` |
| `timestamp`, `currency` | UTC gözlem zamanı, `TRY` |

`null` hata anlamına gelmez; kaynakta o bilginin güvenilir olarak bulunmadığını
gösterir. Satıcıların bütün teklifleri tek tek kaydedilmez; yalnızca seçilen
teklif döner. Bütün teklifler canlı kontrol aracında (`all_offers`) görülebilir.

### Hata kodları

Sayfa okunamazsa `FetchError(code, mesaj)` verilir (`app/scraper/http.py`).
Kod, toplama turunda `listing_checks.error_code` sütununa, keşifte rapora aynen
yazılır; hiçbiri fiyat veya Tükendi yerine geçmez.

| Kod | Nerede | Anlamı |
|---|---|---|
| `invalid_url` | HTTP | Adres düz bir HTTPS adresi değil (kullanıcı adı, port, `#` parçası ya da başka şema). |
| `invalid_host` | HTTP | Adres veya yönlendirme hedefi platformun izinli alan adı dışında. Mesaj hedefin alan adını ve yolunu yazar, ör. `(evil.example/yol)`; sorgu metni yazılmaz. |
| `limit` | HTTP | İstek bütçesi doldu (bütçeyi yalnız keşif verir). |
| `redirect` | HTTP | Yönlendirmenin hedefi yok ya da 3'ten fazla yönlendirme. |
| `blocked` | HTTP | Kaynak 401/403/418/429 döndürdü (engellendi); tekrar denenmez. |
| `http_error` | HTTP | Diğer 4xx (ör. 404); kalıcı sayılır, tekrar denenmez. |
| `network` | HTTP | Bağlantı hatası, zaman aşımı veya 5xx; tekrarlardan sonra da sürdü. 5xx bilerek ayrı bir kod almaz (karar, 6 Ekim): geçicidir ve [tur sonu ikinci okuma](#tur-sonu-ikinci-okuma) yalnız `network`'ü yeniden okuduğu için 5xx'i de kapsar. |
| `too_large` | HTTP | Başarılı yanıtın gövdesi indirme sırasında 8 MB sınırını aştı; aktarım durduruldu, tekrar denenmez. |
| `parse` | HTTP, scraper | Yanıt UTF-8 metin/JSON değil ya da sayfa verisi beklenen yapıda değil; teklif sözleşme doğrulamasından geçmedi. |
| `identity` | scraper, keşif | Sayfa hedef ürün değil: model, kapasite, dışlanan ifade, ağ türü ya da yenilenmiş/aksesuar/yurt dışı sürüm. |
| `no_eligible_offer` | scraper | Uygun satılabilir teklif yok, ama Tükendi için açık stok sinyali de yok. |
| `api_error` | Hepsiburada | Satıcı listesi veya fiyat API'si başarısız ya da satılabilir satıcı için boş yanıt verdi. |
| `plugin` | factory | Platform adaptörü yüklenemedi. |
| `validation`, `unexpected`, `storage` | toplama turu | Gözlem doğrulanamadı veya başka sayfaya ait; beklenmeyen istisna (ayrıntı loga yazılır); veritabanı değeri reddetti. Tur üçünde de sürer. |

## Kimlik kuralları

Keşif ve scraper aynı fonksiyonu (`app/scraper/parsing.py → identify`) kullanır;
böylece keşfin kabul ettiği sayfayı scraper aynı girdilerle reddetmez.

- Ürün adresi kimliği de `app/scraper/parsing.py` içindeki
  `trendyol_product_id(url)` ve `hepsiburada_sku(url)` ile ortak okunur. İki
  scraper, iki keşif modülü ve katalog eşleştirme bu yardımcıları kullanır.
  Kimlik yalnız ürün yolundan çıkarılır; sorgu veya alan adındaki metin kimlik
  sayılmaz. Geçerli sorgu parametreleri, son eğik çizgi ve göreli ürün yolları
  kabul edilir; yardımcılar adresi yeniden yazmaz.
- Trendyol kimliği küçük harfli `-p-` ardından rakamlardır; rakama yapışık harf
  reddedilir. Kimlik metin olarak kalır, baştaki sıfırlar korunur. Hepsiburada
  ürün kodu `-p-HBCV…` içindeki harf/rakam SKU'sudur ve büyük harfe çevrilir.
  Kimlik bulunamazsa ortak yardımcılar `None` döndürür. Mevcut scraper
  doğrulaması geçersiz ürün adresinde `identity` verir; Trendyol'da sorunlu
  satıcı teklifi fiyat seçiminden `different_product_page` gerekçesiyle elenir.
  Hepsiburada SKU reddi ürün isteğinden önce, Trendyol scraper doğrulaması
  mevcut ürün isteğinden sonra çalışır; istek sırası korunur.
- Hepsiburada grup (`-pm-HBC…`) kimliği keşfe özgü ayrı kuraldır; ürün SKU'su
  sayılmaz. Katalog eşleştirmede bilinmeyen platform `None` döndürür. Keşfin
  kaynak/adres/sayfa karşılaştırması ve canonical tam SKU koruması bu kimliği kullanır.
- Başlık tam modeli içermeli: "iPhone 16" hedefi "iPhone 16e", "16 Plus",
  "16 Pro" başlıklarını; "Galaxy S24" hedefi "S24+", "S24 FE", "S24 Ultra"
  başlıklarını; "iPhone 13" hedefi "13 mini" başlığını kabul etmez.
- Yenilenmiş, ikinci el, teşhir, **yurt dışı sürüm** ("International Version",
  "Global Version", "Yurt Dışı") ve aksesuar (kılıf, şarj, koruyucu…) reddedilir.
  Kayıtlı "Kılıfı", "Adaptörü", "Kapağı" yazımları da başlıklarda bütün sözcük
  olarak reddedilir (`kilifi`, `adaptoru`, `kapagi`). Başlık veya yapısal veri
  doğru kapasiteyi taşısa da ret `identity` olur. Genel Türkçe ek tahmini yoktur.
- Yenilio + isteğe bağlı Outlet + A/B/C + Kalite birleşimi de başlıkta
  kapsam dışıdır (13 Ekim gerçek kaynak bakımı). Örnekler: "Yenilio A Kalite",
  "Yenilio B Kalite", "Yenilio Outlet C Kalite". Normalleştirilmiş sözcük
  sınırları ve boşluk/tire/alt çizgi korunur; tek outlet/kalite veya satıcı
  adı yeterli ret sinyali değildir. Keşif kartı/ürün ve scraper aynı ortak
  kurala bağlıdır; fiyat okumasından önce identity reddi vardır.
- Keşfin kategori süzgeci "Kapağı" ve "Adaptörü" yazımlarını da reddeder;
  "Kılıfı" mevcut `kilif` kuralıyla zaten reddediliyordu. "Cep Telefonu Kapağı"
  ve "Cep Telefonu Adaptörü" kategori örnekleri yapay sınamadır; bu adlarla
  gerçek bir kaynak kategorisi görüldüğü iddia edilmez.
- Kapasite, sayfanın yapısal verisinden ve başlıktan okunur; iki kaynak
  çelişirse sayfa reddedilir, hiçbirinde yoksa da reddedilir. TB desteklenir
  (1 TB = 1024 GB). Ardından "RAM" yazan değer hafıza sayılmaz ("128 GB 12 GB
  Ram" → 128). Etiketsiz iki değer varsa ("12GB+512GB") başlık kullanılmaz,
  yapısal veri kullanılır.
- Hepsiburada'da `variant_identity(soup, sku)` aynı SKU'nun bütün
  `allVariantCombinations` kayıtlarını karşılaştırır. Keşif kapasite ve rengi
  buradan alır; scraper'ın `variant_capacity` yardımcısı da aynı doğrulamaya
  bağlıdır. Farklı geçerli kapasite veya normalize edilmiş renkler `identity`
  üretir; başka SKU'nun çelişkisi açılan ürünü etkilemez. Eksik/ayrıştırılamayan
  kapasite ve boş renk çelişki değildir. Tek geçerli kapasite kullanılır;
  kapasite bulunamazsa başlık doğrulaması sürer. `1 TB`/`1024 GB` ve mevcut
  normalizasyonla eşdeğer renk tekrarları kabul edilir; rengin ilk dolu kaynak
  metni korunur. Renk çevirisi veya eş anlamlı eşleştirmesi yapılmaz.
  Keşifte SKU herhangi bir listede bulunabilir; hiçbirinde yoksa reddedilir.
  Scraper'da seçenek bulunmadığında başlıktan kapasite doğrulaması korunur.
  Grup sayfalarının ve bağlantı kuyruğunun son dolu listeden ilerlemesi değişmedi.
- Ayrı model sayılan ekler: Pro, Plus, Max, Ultra, FE, Lite, mini, **Edge, Air**.
  "Galaxy S25 Edge" S25 hedefine, "iPhone 17 Air" yazan bir sayfa iPhone 17
  hedefine girmez.
- Satıcıların `_` ile ayırdığı adlar ("Galaxy S25 Ultra_12GB_256GB") boşlukla
  ayrılmış gibi okunur; aksi halde "Ultra" görülmüyor ve sayfa hem S25 hem S25
  Ultra sayılıyordu (canlıda `catalog_conflict` olarak yakalandı).
- Hedefin `exclude_terms` ifadelerini içeren başlıklar reddedilir; hedefte
  `network` varsa sayfanın yapısal ağ türü hedefle çelişemez.
- Trendyol'da model adında açık 5G varsa yapısal Mobil Bağlantı Hızı değeri
  açık 4G olduğunda verify_model_network iki tüketicide de identity verir.
  4.5G/4,5G/LTE/4G LTE mevcut network_type ile 4G sayılır. Değer eksik/
  tanınmıyorsa bu koruma yeni çıkarım yapmaz; 5G+, 5G NR ve 4G/5G mevcut
  5G tanımında kabul edilir. Kontrol fiyat/adaydan önce uygulanır; modelde
  5G yazmaması 4G kabul kuralı değildir. Kaynak 797850359, 14 Ekim.

## Veritabanı (PostgreSQL)

Fiyat toplama turlarının sonuçları PostgreSQL 17'de saklanır. Günde 2 turu
Görev Zamanlayıcı başlatır ([Zamanlanmış tur](#zamanlanmış-tur-görev-zamanlayıcı)).

### Bir kerelik kurulum (Windows)

1. EDB'nin PostgreSQL 17 kurulum programı; bileşenler: Server ve Command Line
   Tools. **"Locale" adımında `C` seçilmelidir.** Türkçe Windows'un varsayılan
   locale adı `Turkish_Türkiye.1254` ASCII dışı karakter içerdiği için `initdb`
   başarısız olur; kurulum programı yine de "tamamlandı" der ama servis ve veri
   klasörü oluşmaz (28 Eylül 2026'da yaşandı).
2. Yönetici olarak (`psql -U postgres -h localhost`) proje kullanıcısı ve iki
   veritabanı:

   ```sql
   CREATE ROLE fiyat_takip LOGIN;
   \password fiyat_takip
   CREATE DATABASE fiyat_takip OWNER fiyat_takip TEMPLATE template0 ENCODING 'UTF8' LOCALE_PROVIDER builtin BUILTIN_LOCALE 'C.UTF-8';
   CREATE DATABASE fiyat_takip_test OWNER fiyat_takip TEMPLATE template0 ENCODING 'UTF8' LOCALE_PROVIDER builtin BUILTIN_LOCALE 'C.UTF-8';
   ```

   `fiyat_takip` yönetici değildir; yalnızca bu iki veritabanının sahibidir.
   Şifrede Türkçe karakter kullanılmamalıdır (psql konsolu ile `pgpass.conf`
   farklı kodlama kullanır). Yerel kurulum yalnızca bu bilgisayardan gelen
   bağlantılara izin verir (`pg_hba.conf`).
3. Şifre `%APPDATA%\postgresql\pgpass.conf` dosyasına:
   `localhost:5432:*:fiyat_takip:ŞİFRE`. Repoda ve ortam değişkeninde şifre
   bulunmaz.
4. Şifresiz adresler kullanıcı ortam değişkeni olarak (sonra VS Code/terminal
   yeniden açılır):

   ```powershell
   setx DATABASE_URL "postgresql://fiyat_takip@localhost:5432/fiyat_takip"
   setx TEST_DATABASE_URL "postgresql://fiyat_takip@localhost:5432/fiyat_takip_test"
   ```

5. `python -m app.database migrate` tabloları kurar.

### Tablolar

| Tablo | İçerik |
|---|---|
| `platforms`, `products`, `listings` | `catalog.json`'un kopyası (asıl kaynak dosyadır). Kayıt silinmez; yabancı anahtarlar bu kopyaya dayanır. |
| `collection_runs` | Her fiyat toplama turu: başlama şekli (`scheduled`/`manual`), durum (`running`/`completed`/`interrupted`), zamanlar, turun başındaki `catalog.json` parmak izi, planlanan sayfa sayısı. |
| `listing_checks` | Her tur × planlanan sayfa bir satır. Tur başında sonuçsuz açılır (`outcome` boş = planlandı, bakılmadı); sayfa okununca `offer` (fiyat), `sold_out` (Tükendi) veya `error` (hata kodu) olur. Fiyat alanları `PriceObservation` ile aynıdır, para kuruş. |
| `schema_migrations` | Uygulanan migration dosyaları ve parmak izleri. |
| `market_history` | 004 ile ayrı Cimri geçmişi: ürün/kaynak/gün tekil, fiyat kuruş veya NULL; Cimri kimliği/adresi, alım zamanı ve üç kaynak parmak izi. Kendi turlarımızın görünümüne katılmaz. |
| `product_run_prices` (görünüm) | Her biten tur × ürün için bir satır: en ucuz fiyat ve önceki turla karşılaştırılabilir mi ([Karşılaştırılabilirlik](#karşılaştırılabilirlik-product_run_prices)). |

### Veritabanının zorladığı kurallar

Kurallar kodda değil tabloda tanımlıdır; koddaki bir hata bile aykırı satır
yazamaz (`tests/test_database.py` aşağıdakilerin her birini dener):

- Aynı turda aynı sayfa bir kez yazılır (`PRIMARY KEY (run_id, listing_id)`).
- Hata sonucu fiyat, satıcı veya stok taşımaz; fiyat sonucu satıcısız ve
  Tükendi stoklu olamaz; Tükendi sonucu yalnız `Tükendi` stokla yazılır;
  planlanmış ama bakılmamış satır hiçbir sonuç alanı taşımaz.
- Bir sayfanın sonucu başka bir ürünün altına yazılamaz
  (`(listing_id, product_id)` yabancı anahtarı).
- Aynı anda yalnızca bir tur `running` olabilir (kısmi benzersiz indeks).
  Süren turun bitiş zamanı yoktur, biten turun vardır.
- Satıcı puanı ölçeği aşamaz; fiyatlar sıfırdan büyüktür; marka + model +
  kapasite büyük/küçük harften bağımsız tekildir.
- `CHECK` ifadesi NULL sonuç verirse satır kabul edilir. Bu yüzden sonuç
  kuralları `CASE` ile ve her koşul `IS NOT NULL` ile korunarak yazıldı
  (korumasız yazımda satıcısı boş bir fiyat satırı kabul ediliyordu).
- **002 ile gelenler:** Tükendi satırı fiyat, çizili fiyat, satıcı, puan veya puan
  ölçeği taşıyamaz (`listing_checks_sold_out_has_no_offer`). Üstü çizili fiyat yalnız
  güncel fiyattan büyükse saklanır (`listing_checks_original_above_current`); aynı
  kural `PriceObservation` sözleşmesinde de vardır, scraper bozulup eşit ya da
  küçük çizili fiyat verirse sayfa hata olur. Scraper'lar bugün bu durumda zaten
  `null` verir.
- **002 ile gelen tetikleyiciler** (aşağıdaki tablo): hiçbir tabloda satır
  silinemez, `TRUNCATE` reddedilir, kimlik alanları değişmez ve yazılmış sonuç
  donar.

#### Tetikleyiciler: neyin değişip neyin değişmediği

Tetikleyici (trigger), bir değişiklik yapılmadan önce veritabanının araya girip
reddedebildiği kuraldır. Hata `integrity_constraint_violation` (SQLSTATE `23000`)
koduyla döner; kodun gerçek güncellemeleri (katalog eşitleme, `record_result`,
`finish_run`, `close_stale_runs`) bu kurallara takılmaz ve bu `tests/test_database.py`
ile bütün tur ve eşitleme testlerinde sınanır.

| Tablo | Değişmez | Değişebilir |
|---|---|---|
| `platforms` | `key` | `name`, `active` |
| `products` | `product_id`, `product_key`, `brand`, `model`, `storage_gb` | `active` |
| `listings` | `listing_id`, `product_id`, `platform` | `url`, `color`, `active` |
| `collection_runs` | `trigger`, `started_at`, `catalog_sha256`, `planned_count` (`run_id`'yi PostgreSQL kendisi korur: `GENERATED ALWAYS`); 003 ile kapanmış turun `status` ve `finished_at` alanları | Çalışan turun `status`, `finished_at` alanları; her turun `note` alanı |
| `listing_checks` | `run_id`, `listing_id`, `product_id` | Sonuç alanları **bir kez**, yalnız çalışan turda yazılır: sonuçsuz (planlı) satır ilk sonucunu alır, sonra satır donar |

- **Tek istisna:** çalışan turdaki `network` hatası, aynı tur içinde yeniden
  okunup yerine sonuç yazılabilir ([tur sonu ikinci okuma](#tur-sonu-ikinci-okuma),
  `runs.rewrite_network_result`). Başka hata kodları ve biten turun satırları
  değiştirilemez. `003_closed_run_guards.sql` ilk sonuç yazımını da çalışan
  turla sınırlar; sonuç yazarken tur satırını işlem sonuna kadar `FOR SHARE`
  ile kilitler, eşzamanlı kapanışı sıraya alır. Kapanmış turun durumu ve bitiş
  zamanı değişmez, notu güncellenebilir.
- **Bilerek silme:** gerçekten gerekirse (örneğin yanlış eklenmiş bir sayfanın
  geçmişi) tablonun sahibi (`fiyat_takip`) ilgili tetikleyiciyi kapatıp işini
  yapar ve hemen açar. Önce `SELECT` ile neyin silineceğine bakılır, tur
  saatleri dışında yapılır:

  ```sql
  ALTER TABLE listing_checks DISABLE TRIGGER listing_checks_no_delete;
  DELETE FROM listing_checks WHERE listing_id = 'hepsiburada_ornek';
  ALTER TABLE listing_checks ENABLE TRIGGER listing_checks_no_delete;
  ```

  Tetikleyici adları `<tablo>_no_delete`, `<tablo>_no_truncate` ve
  `<tablo>_guard_update`'tir. Kapatıp açma yolu `tests/test_database.py`'de
  denenir.

### Karşılaştırılabilirlik (`product_run_prices`)

Bir sayfa hata alınca ürünün "en ucuz fiyatı" yukarı sıçrar, sonraki turda geri
düşer; bu sahte bir indirim gibi görünürdü. Kural: **iki tur ancak ürünün cevap
veren sayfa kümesi aynıysa karşılaştırılır.** Cevap `offer` (fiyat) veya `sold_out`
(Tükendi) demektir; hata cevap değildir, Tükendi gerçek cevaptır. Bir hata iki
karşılaştırmayı bozar (hataya girerken ve hatadan çıkarken); kapsam değişince de
(yeni eklenen ya da pasife alınan sayfa) bir kez bozulur.

`product_run_prices`, biten (`completed`) her tur × ürün için bir satırdır;
süren ve yarıda kalan turlar girmez.

| Sütun | Anlam |
|---|---|
| `run_id`, `product_id`, `run_started_at` | Tur, ürün ve turun başlama zamanı |
| `planned_pages`, `answered_pages`, `offer_pages`, `sold_out_pages`, `error_pages` | Ürünün o turdaki sayfaları: planlanan, cevap veren, fiyatlı, Tükendi, hatalı |
| `best_price`, `best_listing_id` | Fiyatı olan sayfalar arasındaki en ucuz fiyat (kuruş) ve sayfası; eşitlikte kimliği küçük olan. Bütün cevaplar Tükendi ise boş: bu bir düşüş değildir |
| `previous_run_id`, `previous_best_price` | O ürünün satırı bulunan bir önceki biten tur (`--prefix` turu başka ürünleri atladığı için ürüne göre) ve onun en ucuz fiyatı |
| `hours_since_previous` | İki tur arası saat. **Karşılaştırmayı engellemez:** bilgisayar uyurken kaçan turlar (2–4 Ekim: yaklaşık 40 saat) yalnız bilgi olarak gösterilir, yorumu tüketen taraf (API, ML) yapar |
| `comparable_with_previous` | Doğru ise `best_price` ile `previous_best_price` karşılaştırılabilir. İlk tur, cevapsız ürün ve küme değişen satırlarda yanlış |

Karşılaştırma yalnız `comparable_with_previous = true` olan satırlarda yapılır.

```sql
SELECT run_id, run_started_at, best_price / 100.0 AS en_ucuz_tl,
       previous_best_price / 100.0 AS onceki_tl,
       comparable_with_previous, hours_since_previous
FROM product_run_prices
WHERE product_id = 1
ORDER BY run_id;
```

### Toplama turu (`python -m app.collection`)

1. Ortak kilidi alır (`data/scrape.lock`); başka bir tur, keşif veya canlı
   kontrol sürüyorsa beklemeden çıkar (kod 3).
2. Şema güncel değilse durur. Veritabanının kendi tur kilidini (advisory lock)
   alır; aynı veritabanını kullanan başka bir süreç (ör. farklı kilit dosyasıyla
   çalışan bir kopya) tur yürütüyorsa çıkar (kod 3) ve onun turuna dokunmaz. İki
   kilit de bizdeyse `running` kalmış eski turlar yarıda kalmıştır;
   `interrupted` yapılır.
3. Katalogu eşitler (aşağıdaki kurallar); çakışma varsa tur açılmaz.
4. Etkin sayfa + etkin ürün + etkin platform (isteğe bağlı `--prefix`) planlanır;
   tur satırı ve planlanan sayfalar (sonuçsuz) tek transaction'da yazılır.
5. Her sayfa mevcut scraper'la (`fetch`) okunur ve sonucu **hemen** yazılır;
   tur ortasında bilgisayar kapanırsa okunanlar kaybolmaz. Ekrana
   `[12/326] listing_id  fiyat 57.249,00 TL · satıcı (Stokta Var)` biçiminde
   ilerleme yazılır.
6. Tur sonunda yalnız `network` hatası alan sayfalar **bir kez** yeniden okunur
   (aşağıda [Tur sonu ikinci okuma](#tur-sonu-ikinci-okuma)).
7. Tur `completed` yapılır ve özet basılır.

| `fetch()` sonucu | `listing_checks` |
|---|---|
| Stokta Var / Kritik Stok | `offer` + fiyat, satıcı, puan, stok |
| Tükendi | `sold_out`; fiyat ve satıcı **yazılmaz** (satın alınamayan fiyat "en ucuz" hesabına karışmasın) |
| `FetchError` (`blocked`, `network`, `parse`, `identity`, `no_eligible_offer`…) | `error` + aynı kod ve mesaj (`network` tur sonunda bir kez yeniden okunur) |
| Gözlem başka bir sayfaya ait ya da scraper doğrulanmamış veri döndürdü (`ValueError`) | `error`, `validation`. Gerçek scraper'larda sayfa içindeki doğrulama hatası zaten `parse` koduyla gelir |
| Beklenmeyen hata | `error`, `unexpected`; ayrıntı ekrana yazılır, **tur sürer** |
| Veritabanı değeri reddetti (ör. sütuna sığmayan fiyat) | `error`, `storage`; **tur sürer**. Metinlerdeki NUL (`\x00`) karakteri yazmadan önce silinir |
| Ctrl+C veya veritabanı hatası | Tur `interrupted`; bakılmayan sayfalar sonuçsuz kalır. Veritabanı bağlantısı tamamen koptuysa tur kapatılamaz ve `running` kalır; bir sonraki tur onu `interrupted` yapar |

Çıkış kodları: `0` tamamlandı ve hata yok; `2` tamamlandı ama bazı sayfalarda
hata var; `1` başlayamadı (şema, çakışma, `DATABASE_URL`, `runtime.json`,
planlanacak etkin sayfa yok: ör. hiçbir ürünle eşleşmeyen `--prefix`)
**ya da** tur ortasında veritabanı hatasıyla kesildi (tur `interrupted`, o ana
kadar yazılanlar kalır) **ya da** tur tamamlandıktan sonra özeti okuyan sorgu
düştü (tur `completed` kalır, yalnız çıkış kodu 1 olur); `3` kilit meşgul; `130`
Ctrl+C (tur kapandıktan sonra gelirse `completed` kalır). `--scheduled` turu
`scheduled` olarak kaydeder (Görev
Zamanlayıcı için); verilmezse `manual`. `--prefix` kullanıldıysa turun
notuna yazılır. Sonuç yalnızca süren tura yazılabilir; kapanmış bir tur
yeniden kapatılmaya çalışılırsa hata verir (sessiz geçmez).

#### Kapanış sonrası hatalar

Turun kapanışı özet sorgusundan önce, autocommit bağlantıda kalıcıdır.
Özet SQL hatası veya özet okunurken kullanılan bağlantının kapanması, yazılmış
sonuçları ve `completed` durumunu değiştirmez; komut çıkış kodu 1 olur.
Kapanış sonrası Ctrl+C'de de tur `completed` kalır, çıkış kodu 130 olur.
Tur ortasında kesilme ve bağlantı kopması kuralları yukarıdaki gibi sürer.

Ctrl+C mesajı kapanmış ve yarım kalmış turu ayırır:

> Komut durduruldu. Tamamlanmış tur 'completed' kalır; yarım kalan tur 'interrupted' olarak kapatılır. Kapatılamadıysa bir sonraki tur kapatır.

#### Tur sonu ikinci okuma

Bağlantı tur ortasında koptuysa ve tur bitmeden döndüyse (28 Eylül: 47 sayfa,
4 Ekim: ilk 109 sayfa) `network` hatası alan sayfalar bu sırada okunabilir
durumdadır. Tur, sayfa döngüsü bittikten sonra ve kapatılmadan önce bunları bir
kez daha okur:

- **Kapsam:** yalnız o turda `error` / `network` sonuçlu sayfalar (5xx dahil).
  `blocked`, `parse`, `identity`, `invalid_host`, `http_error` ve diğer bütün hatalar
  yeniden denenmez: engel aşılmaz, kalıcı hatalar tekrar denenmez. Her sayfa aynı
  `check_listing` ile ve yeni bir scraper nesnesiyle okunur; 3 sn istek aralığı aynen
  geçerlidir.
- **Yazma:** yeni sonuç hata satırının **üzerine yazılır**
  (`runs.rewrite_network_result`: yalnız süren turun `error`/`network` satırı;
  002 tetikleyicisi aynı istisnayı tanır). Sayfa başına tek satır kuralı korunur ve
  bir sayfa bir turda en çok bir kez yeniden okunur. Düzelen sayfanın `checked_at`
  değeri ikinci okuma anıdır (ilk denemeden en çok tur süresi, ~30 dk sonra).
- **İkinci okuma da `network` verirse** yeni bilgi yoktur: satır (mesaj ve zaman
  damgası dahil) olduğu gibi kalır. Başka bir sonuç gelirse (fiyat, Tükendi ya da
  `network` dışında bir hata) o yazılır.
- **Veritabanı yeni sonucu reddederse** (ör. sütuna sığmayan fiyat) ilk `network`
  satırı kalır, log'a yazılır ve tur sürer.
- **Erken durdurma:** ardışık 5 sayfa yine `network` verirse bağlantı hâlâ yok
  demektir ve geçiş durur; kalan sayfalar `network` olarak kalır (internet tur
  boyunca yoksa 333 sayfayı bir de denemek 3 sn aralıkla ~17 dk boşa giderdi).
  Birinci geçişte erken durdurma yoktur.
- **Log ve tur notu:** `Tur sonu: network hatası alan N sayfa yeniden okunuyor`,
  her sayfa için `[tekrar i/N] listing_id  …` ve özet satırı. Tur notuna yalnız
  sayılar yazılır, sayfa kimlikleri logdadır: `network hatası alan 109 sayfa,
  ikinci okuma: 104 düzeldi, 5 hâlâ hatalı` (durursa sonuna `, 2 denenmedi
  (ardışık 5 network hatasında durdu)` eklenir; `--prefix` notunun ardından `; `
  ile gelir). Hiç `network` hatası yoksa ikinci okuma yapılmaz ve not eklenmez.
- **Çıkış kodu ve özet** ikinci okumadan sonraki duruma göre hesaplanır; tamamen
  kurtarılan bir kesinti çıkış 0 verir. Kurtarılan sayfa cevap sayıldığı için
  ürünün cevap veren sayfa kümesi değişmez ve [karşılaştırılabilirlik
  görünümünde](#karşılaştırılabilirlik-product_run_prices) sahte bir
  "karşılaştırılamaz" satırı oluşmaz.
- **Sınırı:** bilgisayar uyursa ya da kesinti tur bitene kadar sürerse sayfalar
  hatalı kalır; bu kalıcı çözüm değildir (sürekli işletim, Aşama 9). Gerçek
  turlarda çalıştığı görüldü: 17 Ekim tur 37'de 55/55, 19 Ekim tur 42'de 3/3
  sayfa düzeldi.

### Zamanlanmış tur (Görev Zamanlayıcı)

`scripts/zamanlayici_kur.ps1`, Windows Görev Zamanlayıcı'ya
`\FiyatTakip\FiyatToplamaTuru` görevini kurar. Yönetici izni gerekmez; tekrar
çalıştırmak görevi aynı ayarlarla yeniden kurar, `-Kaldir` siler. Windows
varsayılan olarak `.ps1` çalıştırmadığı için komut
`powershell -ExecutionPolicy Bypass -File …` biçimindedir (izin yalnız o komut
içindir, sistem ayarı değişmez). Betik, `.venv\Scripts\pythonw.exe` yoksa ya da
`DATABASE_URL` kullanıcı ortam değişkeni tanımlı değilse görevi kurmadan hata
verip durur (görev bu değişkeni Windows kullanıcı ortamından alır).

| Ayar | Değer | Neden |
|---|---|---|
| Tetikleyiciler | Her gün yerel saatle 10:00 ve 22:00 | Karar ([proje_plani.md](../proje_plani.md)). Görev Zamanlayıcı saati varsayılan olarak UTC'ye çevirir; script yerel saat yazar. |
| Eylem | `.venv\Scripts\pythonw.exe -m app.collection --scheduled`; çalışma klasörü proje klasörü | `pythonw` pencere açmaz: 31 dakika açık kalan ve kapatılınca turu kesen bir pencere olmaz. `config\` ve `data\` yolları çalışma klasörüne göredir. |
| Kaçan tur | "Kaçırılırsa en kısa sürede çalıştır" | Bilgisayar kapalıyken kaçan tur, açılınca **bir kez** yapılır (iki tur kaçtıysa da bir kez). |
| Pil | Pildeyken de başlar, pile geçince durmaz | Windows'un varsayılanı yalnız şarjdayken çalıştırmaktır; dizüstünde pilde tur hiç başlamazdı. |
| Uyandırma | Yok | Uykudaki bilgisayar uyandırılmaz; kaçan tur açılınca telafi edilir. |
| Aynı anda | Görev çalışıyorsa yeni kopya başlatılmaz (`IgnoreNew`) | Atılan tetikleme log, veritabanı satırı ve çıkış kodu bırakmaz ve sonradan telafi edilmez (aşağıdaki sınırlara bakın). Elle başlatılan keşif ve canlı kontrol araçlarını ortak kilit engeller. |
| Süre sınırı | 2 saat | Normal tur ~31 dk (kesintili turlar 36–38 dk sürdü: uyku ya da bağlantı kopması). Görev Zamanlayıcı süreci zorla kapatırsa tur `running` kalır; bir sonraki tur onu `interrupted` yapar. |
| Kullanıcı | Kurulumu yapan kullanıcı, yalnız oturum açıkken | Windows şifresi saklanmaz; `DATABASE_URL` ve `pgpass.conf` bu kullanıcınındır. Kilitli ekran "oturum açık" sayılır. |

`--scheduled` ile bütün çıktı `data/logs/tur_<yerel tarih-saat>.log` dosyasına
da yazılır: başlangıç satırı, her sayfanın ilerleme satırı, beklenmeyen
hataların ayrıntısı (traceback), özet ve **çıkış kodu**. Başlayamayan (kod 1)
ve kilit meşgul olduğu için atlanan (kod 3) turlar da log bırakır. Tek istisna:
log dosyasının kendisi açılamazsa (ör. `data\logs` yazılamıyor) `pythonw`
altında hiçbir yere yazı düşmez; yalnız Görev Zamanlayıcı sonucu `0x1` görünür.
Dosya satır satır yazılır; tur ortasında bilgisayar kapanırsa o ana kadarki
satırlar kalır. `pythonw` altında ekran akışları yoktur; tek yazılı kayıt bu
dosyadır. Loglar silinmez (tur başına ~30 KB).

Görev Zamanlayıcı "Son çalıştırma sonucu"nu onaltılık gösterir: `0x0`
hatasız, `0x2` bazı sayfalar hatalı, `0x3` kilit meşgul (tur atlandı, yeniden
denenmez), `0x1` başlayamadı ya da veritabanı hatasıyla kesildi. Görev
çalışırken `0x41301` (267009) görünür; bu hata değil, "çalışıyor" kodudur.
Ayrıntı log dosyasında, sonuçlar veritabanındadır
(`collection_runs.trigger = 'scheduled'`).

Sınırlar:

- 10:00 veya 22:00'de elle keşif ya da canlı kontrol sürüyorsa zamanlanmış tur
  başlamaz (kod 3) ve o tur telafi edilmez.
- Bilgisayar açılışında başlayan telafi turu ağ bağlantısı kurulmadan
  başlayabilir; ilk sayfalar `network` hatası alabilir.
- Tur bilgisayarın o anki internet bağlantısına bağlıdır. Bağlantı tur
  ortasında koparsa o sıradaki sayfalar `network` hatası alır, bağlantı dönünce
  tur kaldığı yerden sürer ve tamamlanır; tur sonunda bu sayfalar bir kez yeniden
  okunur ([Tur sonu ikinci okuma](#tur-sonu-ikinci-okuma)). Kesinti tur
  bitene kadar sürerse ya da bilgisayar uyursa sayfalar hatalı kalır (28 Eylül,
  ilk zamanlanmış tur: 326 sayfanın 47'si `network`, 279'u okundu, çıkış 2; ikinci
  okuma o tarihte yoktu). İnternet hiç yoksa tur bütün sayfalara hata yazarak biter
  (birinci geçişte erken durdurma yok; ikinci okuma ardışık 5 hatada durur). Hata
  "cevap" sayılmadığı için sahte fiyat veya sahte düşüş oluşmaz.
- Tur yarıda kesilirse (bilgisayar kapandı, süre sınırı) Görev Zamanlayıcı onu
  "çalıştı" saydığı için telafi edilmez.
- Görev bilgisayarı uyandırmaz. Bilgisayar uyurken gelen tur kaçar ve
  açılışta bir kez telafi edilir. 30 Eylül'de bilgisayar 17:57'den 1 Ekim
  09:20'ye kadar uykudaydı; 22:00 turu çalışmadı ve telafi turu 1 Ekim 09:26'da
  başladı (tur 7). Kaçan turun verisi geriye dönük toplanamaz; yalnız o saatin
  gözlemi kaybolur.
- Telafi turu bir sonraki tur saatine sarkarsa o tetikleme `IgnoreNew` ile
  atılır: ayrı log, `collection_runs` satırı ve çıkış kodu oluşmaz ve sonradan
  telafi edilmez (1 Ekim 10:00: tur 7 hâlâ sürüyordu). `LastRunTime` tetikleme
  saatini, `LastTaskResult` ise çalışmakta olan turun sonucunu gösterir. Atılma
  olayını Görev Zamanlayıcı geçmişi kayıt eder; geçmiş kapalıysa doğrulanamaz.
- Tur ortasında bilgisayar uyursa (1 Ekim 09:29, kritik pil, yaklaşık 6,5 dk)
  uyanma anındaki sayfalar `network` hatası alabilir (tur 7: 1 sayfa, DNS
  çözülemedi); tur tamamlanır. Tur sonu ikinci okuma bu sayfaları yeniden dener;
  düzelmezlerse çıkış kodu 2 olur.

### Zamanlanmış keşif (Görev Zamanlayıcı)

`scripts/kesif_zamanlayici_kur.ps1`, `\FiyatTakip\HaftalikKesif` görevini kurar
(yönetici izni gerekmez; tekrar çalıştırmak yeniden kurar, `-Kaldir` siler;
fiyat görevine dokunmaz). Kurulu görev **otomatik kabul** modundadır
(`-OtomatikKabul`, 19 Ekim 2026); seçeneksiz yeniden kurulum önizleme moduna
(`--dry-run`) döner. İki biçimde de keşif veritabanına bağlanmaz.

| Ayar | Değer | Neden |
|---|---|---|
| Tetikleyici | Her Pazar yerel saatle 14:00 | Fiyat turları 10:00 ve 22:00'de başlayıp ~31 dk sürer; keşif (~35 dk) onlardan uzak bir saate konur. Saat yerel yazılır (UTC'ye çevrilmez). |
| Eylem | Önizleme kurulumunda `.venv\Scripts\pythonw.exe -m app.discovery --scheduled --dry-run`; çalışma klasörü proje klasörü | Penceresiz. `config\` ve `data\` yolları çalışma klasörüne göredir. `--dry-run` görevin kataloğa hiç yazmamasını sağlar. |
| Otomatik mod seçimi | Betik `-OtomatikKabul` ile çalıştırılırsa eylem `--scheduled --auto-accept` olur | Yalnız yeterli kimlik kanıtı olan adaylar eklenir. Seçeneksiz yeniden kurulum önizlemeye dönüş sağlar; Git işlemi yapmaz. |
| Kaçan çalışma | **Telafi edilmez** | Geç açılan bir bilgisayarda telafi keşfi ortak kilidi ~35 dk tutar ve o sırada gelen 22:00 fiyat turu "kilit meşgul" (kod 3) deyip atlanırdı. Kaçan fiyat turu geriye dönük toplanamaz; keşif raporu ise elle her zaman alınabilir. |
| Pil | Pildeyken de başlar, pile geçince durmaz | Windows'un varsayılanı yalnız şarjdayken çalıştırmaktır. |
| Uyandırma | Yok | Uykudaki bilgisayar uyandırılmaz; o hafta keşif kaçar. |
| Aynı anda | Görev çalışıyorsa yeni kopya başlatılmaz | Ortak kilit de engeller. |
| Süre sınırı | 2 saat | Normal çalışma ~35 dk (5 Ekim: 34 dk). Zorla kapatılırsa normal çıkış satırı olmayabilir; hazırlık kaydı yazılmışsa sonraki başlangıç uzlaştırır. |
| Kullanıcı | Kurulumu yapan kullanıcı, yalnız oturum açıkken | Windows şifresi saklanmaz. Keşif veritabanı kullanmadığı için `DATABASE_URL` gerekmez. |

`--scheduled` ile bütün çıktı `data/logs/kesif_<yerel tarih-saat>.log` dosyasına da
yazılır (başlık, özet satırı (uyarılar nedene göre sayılarak orada görünür),
beklenmeyen hataların ayrıntısı, rapor yolu ve **çıkış kodu**); tam rapor aynı damgayla
`data/discovery/kesif_<yerel tarih-saat>.json` dosyasına kaydedilir. Kilit meşgulken
(kod 3), program hatasında ve tarama sonrası yazma hatasında (kod 1) de log bırakılır. Tek istisna: log dosyası
açılamazsa keşif hiç başlamaz ve `pythonw` altında hiçbir yere yazı düşmez; yalnız
Görev Zamanlayıcı sonucu `0x1` görünür. Rapor klasörü taramadan önce oluşturulur;
yazılamıyorsa keşif hiç başlamaz (kod 1, loga yazılır), ~35 dakikalık tarama boşa gitmez.
Keşif ilerleme satırı yazmaz: 4 ve 5 Ekim'deki iki zamanlanmış biçimli çalışmanın
logu yalnız başlık, özet, rapor yolu ve çıkış kodundan oluşuyordu (4 satır); tarama
sürerken ekran ve log sessiz kalır.

Otomatik kabul modunda haftalık akış:

1. Pazar 14:00'te görev başlar; yaklaşık 35 dk sonra log ve tarihli rapor oluşur.
2. Yeterli kimlik kanıtı olan adaylar kataloğa eklenir; eksik veya çelişkili
   olanlar raporda (`decisions`, `rejected`) nedenleriyle dışarıda kalır.
   Süre dolması kabul nedeni değildir.
3. Sonraki normal fiyat turu yeni katalogu veritabanına eşitler.
4. `config/catalog.json` değişikliği yerelde birikir; kullanıcı ayrıca
   onayladığında commit edilir. Otomatik Git işlemi yoktur.
5. Katalog değiştiyse sonraki normal turdan sonra
   [bağımsız SQL–API denetimi](#sqlapistreamlit-bağımsız-denetimi) çalıştırılabilir.

Önizleme modunda (seçeneksiz kurulum) 2. adımda katalog yazılmaz: log'un
sonundaki özet satırına ve rapora bakılır (yeni ürün/sayfalar, `rejected`
nedenleri, `pending` içinde beklenen `search_api` dışında bir uyarı), uygunsa
`python -m app.discovery --apply-report data\discovery\kesif_<tarih-saat>.json`
ile uygulanır.

Otomatik ekleme, kaynakların eksiksiz tarandığı veya ML verisinin hazır olduğu
anlamına gelmez. Yeni sayfa ilgili ürünün kapsamını değiştirebilir ve 30+7
günlük karşılaştırılabilir dönem başlangıcını etkileyebilir; eski fiyatlar silinmez.

Görev Zamanlayıcı "Son çalıştırma sonucu"
(`Get-ScheduledTaskInfo -TaskPath '\FiyatTakip\' -TaskName 'HaftalikKesif'`):
`0x0` tarama tam, `0x2` tarama kısmi (Hepsiburada arama API'si engelli olduğu için
beklenen sonuç), `0x3` kilit meşgul (keşif atlandı, telafi edilmez), `0x1` başlayamadı
ya da program hatası. Ayrıntı log dosyasındadır.

Sınırlar:

- Pazar 14:00'te bilgisayar kapalı ya da uykudaysa o hafta keşif kaçar (log oluşmaz);
  elle çalıştırılır. Görev Zamanlayıcı geçmişi kapalıysa kaçan ya da atılan çalışma
  Windows tarafında görünmez; kanıt, o günün log dosyasının varlığıdır.
- Fiyat turunun telafisi 14:00'e sarkarsa ya da o sırada elle canlı komut
  çalışıyorsa keşif kod 3 ile atlanır (loga yazılır) ve telafi edilmez.
- Tarama sürerken (~35 dk) elle canlı komut çalıştırılmaz: ortak kilit tutulur.
- Raporlar silinmez; klasör zamanla büyür (tam tarama raporu birkaç yüz KB,
  haftada bir dosya). İnternet kesilince rapor küçük kalır.
- Testler komut akışını kayıtlı sonuçlarla sınar; görevin gerçek sitelerle
  çalıştığını ve raporun doğruluğunu yalnız canlı çalışma gösterir.

### Katalog eşitleme (`sync-catalog`)

`listing_checks` yalnızca veritabanında var olan sayfayı kabul eder; bu yüzden
`catalog.json` önce veritabanındaki kopyaya (`platforms`, `products`,
`listings`) yazılır. Asıl kaynak dosyadır. Toplama turu da kendi başında aynı
eşitlemeyi çalıştırır; komut, keşiften sonra farkı gözle görmek içindir.

- Tek transaction: ya bütün değişiklikler yazılır ya hiçbiri. `--dry-run`
  aynı işi yapıp sonunda geri alır.
- Yeni kayıt eklenir. Değişebilen alanlar güncellenir: platform adı ve
  aktifliği, ürün aktifliği, sayfanın adresi, rengi ve aktifliği.
- **Kimlik alanları değişemez:** ürünün `product_key`, marka, model ve
  kapasitesi; sayfanın `product_id`'si ve platformu. Değişmişse (ya da yeni bir
  kayıt başka kaydın `product_key`'ini veya adresini kullanıyorsa) eşitleme
  hiçbir şey yazmadan durur ve bütün çakışmaları listeler. Gerekçe: o sayfanın
  geçmiş fiyatları yanlış ürüne bağlanırdı.
- Katalogdan düşen kayıt silinmez (geçmiş fiyatlar ona bağlıdır), pasife
  alınır ve raporlanır.
- Her tabloda önce güncellemeler, sonra eklemeler yazılır: bir sayfanın adresi
  değişip eski adres yeni bir sayfaya verildiyse sorun çıkmaz. İki sayfanın
  adresi yer değiştirmişse tek adımda yazılamaz; hiçbir şey yazılmadan açık bir
  çakışma mesajı verilir.
- Katalog dosyası başında BOM olsa da okunur.
- İkinci çalıştırma değişiklik yapmaz. Şema güncel değilse (bekleyen migration)
  eşitleme başlamaz.
- Çıktıdaki parmak izi, `catalog.json`'un sha256'sıdır (satır sonundan
  bağımsız); toplama turları hangi katalogla yapıldığını
  `collection_runs.catalog_sha256` alanında bununla kaydeder.

### Migration kuralları

- Dosya adı `NNN_ad.sql`; numaralar 001'den boşluksuz artar. Uzantı büyük harfle
  yazılmış (`.SQL`) ya da kurala uymayan ad hata verir; hiç dosya bulunamazsa da
  hata verilir. Dosyalar pakete dahildir (`pyproject.toml`, `package-data`).
- Her dosya tek transaction'da uygulanır; hata verirse o dosyadan hiçbir iz
  kalmaz (PostgreSQL'de tablo oluşturma da geri alınır). Aynı anda iki
  `migrate` çalışırsa ikincisi bekler (en çok 30 sn, bağlantının
  `lock_timeout` ayarı; sonra hata verir).
- **Uygulanmış dosya değiştirilmez;** değişiklik yeni numaralı dosyayla yapılır.
  Değiştirilirse parmak izi tutmaz ve `migrate`/`status` hata verir. Parmak izi
  satır sonundan bağımsızdır (Windows CRLF ile CI'daki LF aynı sayılır).
- Uygulanmış dosya **yeniden adlandırılamaz** da: `schema_migrations` dosyanın
  numarasız adını (ör. `initial`) tutar; ad değişirse `migrate` ve `status` eski
  ve yeni adı gösteren bir hatayla durur. Numaralar boşluksuz artmazsa (atlanmış
  ya da aynı numaralı iki dosya) hata mesajı bulunan numaraları listeler (ör.
  `bulunan: [1, 1]`).
- Veritabanında kodda olmayan bir sürüm varsa ("veritabanı koddan yeni") komut
  hata verir.
- **Yeni migration'ı koymak ile `migrate` arasında tur başlamamalı.** Dosya
  klasördeyken veritabanı güncel değilse tur "şema güncel değil" deyip başlamaz ve
  o tur kaçar (telafisi tek turdur). Bu yüzden yeni migration projenin kopyasında
  geliştirilir ve gerçek klasöre yalnız bitince konur; `migrate` hemen ardından,
  10:00–10:40 ve 22:00–22:40 tur saatleri dışında çalıştırılır.

## Cimri geçmişi (bir defalık alım ve aktarım)

Katalogdaki telefonların Cimri'de görünen bir yıllık fiyat geçmişi, 8 Ekim
2026'da bir defa alınıp ayrı `market_history` tablosuna aktarıldı (57 ürün,
20.805 tarihli kayıt, 553'ü eksik fiyat). Düzenli Cimri toplaması yapılmaz;
Cimri serisi kendi toplama serimizle birleştirilmez ve aynı ölçüm sayılmaz.
Kod (`app/market_history/`) olası tek bir son alım için korunur; yeni alım
ayrı karar ister ([kullanım değerlendirmesi](#kullanım-değerlendirmesi)).

### Eşleştirme dosyası

Eşleştirme dosyası `version: 1`, `source: "cimri"`, `entries` taşır. Her girdi
`product_key`, `url`, `cimri_product_id` içerir; anahtar, URL ve Cimri kimliği
tekrar edemez. URL yalnız Cimri'nin HTTPS telefon sayfası olabilir; ürün etkin
katalogda bulunmalıdır. 8 Ekim web araştırmasıyla 59 ürünün 57'sinin ana
sayfa adresi ve görünen ürün başlığı eşleştirildi. İlk üç eşleştirme aynı
kaldı. Araştırmada 57 başlık mevcut model/kapasite kuralıyla ağsız doğrulandı;
bu kontrol tek başına API erişimini veya gömülü kimliği kanıtlamaz.
Alım sırasında 57 sayfa/API kimliği ayrıca doğrulandı.

Araştırma izi yerelde
`data/market_history/mapping_research_20261008_073732.json` içindedir:
araştırma zamanı, görülen başlıklar, kaynak adres/kimlikleri ve açık anahtarlar.
URL/kimlik tahmin edilmedi; ana sayfalar kullanıldı, renk sayfaları birleştirilmedi.
Galaxy S25 512 GB (`samsung_galaxy_s25_512gb`) ve Redmi Note 14 Pro 5G
256 GB (`xiaomi_redmi_note_14_pro_5g_256gb`) için doğru ana adres araştırmada
doğrulanamadı. Başka kapasite, Ultra/Plus veya 4G sayfası bunların yerine
konmadı; eşleştirmesi olmayan ürünün Cimri'de bulunmadığı varsayılmaz.

Redmi Note 14 Pro'nun [256 GB](https://www.cimri.com/cep-telefonlari/en-ucuz-xiaomi-redmi-note-14-pro-fiyatlari,a2372365369)
ve [512 GB](https://www.cimri.com/cep-telefonlari/en-ucuz-xiaomi-redmi-note-14-pro-512gb-12gb-ram-fiyatlari,a2430184601)
başlıkları 4G yazmıyor; her iki sayfanın teknik özelliklerinde
`Veri Aktarım Hızı: 4G` doğrulandı. [5G 512 GB](https://www.cimri.com/cep-telefonlari/en-ucuz-xiaomi-redmi-note-14-pro-5g-fiyatlari,a2428710429)
ayrı ana sayfadır. [Poco X6 Pro](https://www.cimri.com/cep-telefonlari/en-ucuz-xiaomi-poco-x6-pro-5g-512gb-12gb-ram-fiyatlari,a2308370397)
sayfasında marka Poco'dur; URL'deki Xiaomi metni marka yerine kullanılmadı.
Galaxy A55 256 GB ve Redmi Note 13 Pro 5G 256 GB için 8 GB RAM ana sayfaları
seçildi; RAM/renk eş anlamlıları veya yeni kimlik istisnası eklenmedi.

### Yerel alım (`capture`)

Zamanlanmış tur bittikten sonra katalog alımı:

```powershell
$cimriKlasor = "data\market_history\katalog_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
.venv\Scripts\python.exe -m app.market_history capture `
  --mapping config\market_history.json --output-dir $cimriKlasor
$LASTEXITCODE
```

`--product-key` tekrarlanabilir; verilmezse etkin katalogdaki bütün ürünler
raporlanır. `--mapping` ve `--output-dir` zorunludur. Var olan klasöre yazılmaz;
eskisini silmek yerine tarih-saatli yeni klasör kullanılır. Kilit meşgulse
klasör oluşturulmaz. Canlı komutu kullanıcı tur saatleri dışında çalıştırır.
İki eşleştirme açık olduğundan bütün 57 alım başarılı olsa bile katalog
komutunun çıkışı 2 olur. `captured`/`error`/`not_attempted` kayıtları ayrıca
incelenir; yalnız çıkış 2'den ağ veya kimlik hatası olduğu sonucu çıkarılmaz.

Her ürün için aynı `PageClient` ile sayfa ve grafik okunur (grafik, sayfadaki
ürün kimliğiyle `POST https://www.cimri.com/api/cimri` üzerinden
`priceHistoryV2Query` sorgusuyla alınır); yönlendirme/tekrar
dahil dört istek bütçesi, ortak bekleme, alan adı ve 8 MB sınırı korunur.
`__OCTOPUS_DATA__` içindeki ürün kimliği eşleştirmeyle aynı olmalıdır; marka
katalogla, başlık ve H1'lerin her biri model/kapasiteyle doğrulanır. Kategori
`cep-telefonlari` olmalıdır. Bunlar doğrulanmadan grafik isteği yapılmaz.
Grafik API'si kimliği de aynı olmalıdır. HTTP `blocked` alınırsa kalan eşleşmiş
ürünlere istek yapılmaz; diğer ürün hatalarında sıradaki ürüne devam edilir.

Grafik, `lastDay`'den geriye sıralanmış en çok 366 nokta verir. Mevcut
araştırmada doğrulanan bu biçim kullanılır; bilinmeyen biçim için tahmin
yapılmaz. Geçersiz tarih, fiyat veya ortak tarihte tablo uyuşmazlığı hata olur.
Fiyatlar pozitif ve en çok iki ondalıklı olmalı; mevcut `money` ile kuruşa
çevrilir. Sayısal grafik sıfırı, aynı tarihte tablo fiyatı yoksa eksik sayılır;
tablo fiyatıyla çelişirse reddedilir. Eksik değer `null` kalır, kısa geçmiş
tamamlanmaz. Ham API dosyasında sıfır değeri korunur. Tabloyla ortak
tarih yoksa `table_comparison: "unavailable"` yazılır. Tekrarlanan fiyatlar
bağımsız günlük ölçümleri veya sabit satıcı kapsamını kanıtlamaz.

Yeni klasörde `responses/<product_key>.html`, `responses/<product_key>.json`
ve `report.json` bulunur. HTML alınmış metindir; API JSON'u, ortak HTTP
katmanının ayrıştırdığı nesnenin UTF-8 dosyasıdır, özgün JSON baytlarının
aynısı olduğu iddia edilmez. Her kaynak dosyasının SHA-256 parmak izi saklanır.
HTTP/JSON ayrıştırma hatasında alınamamış gövde uydurulmaz; sayfa alınmışsa
korunur. Kimlik/grafik doğrulaması başarısızsa kabul edilmiş geçmiş yazılmaz.

Rapor sürümü 1'dir. Kaynak, başlangıç/bitiş zamanı (UTC), sonuç, katalogdaki
ürün sayısı, eşleştirmesi henüz olmayan katalog anahtarları ve `products`
listesi taşır. Ürün kaydı katalog kimliğini, eşleştirmeyi, istek sayısını,
varsa sayfa/API dosyalarının yolunu ve parmak izini, doğrulanmış kimliği,
API alınma zamanını ve `history`yi içerir. `history.points` eski tarihten yeniye
`day` ve `price_kurus` taşır; özet tarih aralığını, nokta/eksik fiyat sayısını
ve tablo karşılaştırmasını gösterir. Ürün durumları `captured`, `error`,
`unmapped`, `not_attempted`, `interrupted`; genel sonuç `running`, `completed`,
`partial`, `interrupted` veya `failed` olabilir. Hata ve durma nedeni raporda
kalır. Yalnız seçilen üç ürünün başarılı olması bütün kataloğun alındığı
anlamına gelmez; seçilmeyen ürünler için ağ isteği yapılmaz.

Rapor her işlenen ürünün ardından geçici dosyadan atomik olarak yenilenir.
Ctrl+C önceki kayıtları korur; disk hatasında yeni istekler durur. İstemci ve
ortak kilit kapanır. Çıkış: 0 seçilen ürünler kaydedildi, 2 kısmi sonuç,
1 ayar/seçim/klasör/dosya hatası, 3 ortak kilit meşgul, 130 Ctrl+C.

**Bugünkü fiyatın ilk teklif dönüşümü.** Cimri'nin ekrandaki grafiği, ürün
sayfasında teklif varsa API'nin son günündeki fiyatı sayfadaki ilk teklifin
fiyatıyla değiştirir; kalan günler API'den gelir (8 Ekim'de grafik kaynak
kodunda doğrulandı). Alım aynı kuralı uygular:

`verified_page` doğrulanmış ürünün ilk teklif fiyatını da okur. İlk teklif
yoksa mevcut API fiyatları korunur; bozuk teklif geçerli fiyat sayılmaz.
`history_in_kurus`, bütün ham API fiyatlarını önce doğrular; ardından yalnız
son noktada geçerli ilk teklif fiyatını kullanır ve bütün ortak tablo günlerini
yeniden birebir karşılaştırır. Diğer günler, sıfır/eksik değer ve eski TL
araştırma sözleşmesi korunur. Bugünün ham API fiyatı sıfır/null ise ilk
teklifle doldurulmaz; doğrulanmamış bu birleşim `parse` olarak kalır.

Alım, HTML isteğinden önce `page_started_at_utc`, API yanıtından sonra
`captured_at_utc` kaydeder. İlk teklif kullanılacaksa iki zaman UTC, sıralı ve
İstanbul'da aynı gün olmalı; API `lastDay` bu güne eşit olmalıdır. Gün sınırı
veya eski API günü `parse` üretir; tarih dizisi yine `lastDay` üzerinden
kurulur. Ağsız yeniden doğrulama bilgisayarın o gününü kullanmaz.
İstanbul tarihi `ZoneInfo` ile hesaplanır; Windows'ta da saat dilimi verisinin
bulunması için zaten ortamda kurulu `tzdata` açık bağımlılık yapıldı
([Python belgeleri](https://docs.python.org/3/library/zoneinfo.html#data-sources)).

`history.summary.latest_price` alanında `day`, `rule` (`page_first_offer`
veya `api`), `api_price_kurus`, `first_offer_price_kurus`,
`effective_price_kurus`, `changed`, `table_comparison` kaydedilir.
Son günün tablo satırı yoksa `unavailable` olur ve komut bunu ayrıca söyler;
bu sınır diğer ortak günlerin eşleşmesini geçersiz kılmaz. İstek sırası,
bütçe, kilit, çıkış kodu ve ham dosyaları koruma davranışı bu kuraldan etkilenmez.

### Ağsız aktarım (`import`)

Komutlar:

```powershell
.venv\Scripts\python.exe -m app.market_history import <alım_klasörü> --dry-run
.venv\Scripts\python.exe -m app.market_history import <alım_klasörü>
```

Girdi `report.json` ve onun gösterdiği HTML/API dosyalarıdır. Raporun
`version: 1`, `source: cimri`, sonlandırılmış sonuç ve UTC zamanları gerekir;
`running`, bozuk zarf ve tekrarlanan kimlikler bütün girdiyi reddettirir.
`completed`, `partial`, `interrupted`, `failed` raporlarından yalnız `captured`
kayıtlar doğrulanır; hatalı kayıtlar başarıya çevrilmez. Güncel ürün başlangıç
zamanı ve `latest_price` alanları zorunludur; eski raporlara uyumluluk yoktur.

Okuyucu rapor/katalogdaki ürün ID'si, anahtar, marka, model ve kapasiteyi
karşılaştırır. Kaydedilmiş eşleştirme kullanılır; güncel eşleştirme dosyasından
adres değiştirilmez. Kaynak yolları çözülünce alım klasörü içinde kalmalıdır.
HTML/API'nin doğrulanan baytları bir kez okunup ayrıştırılır; SHA-256 değişimi,
eksik kaynak, zaman aralığı, kaynak kimliği veya yeniden hesaplanan
kimlik/geçmiş/özet uyuşmazlığı ilgili ürünü reddettirir. Fiyatlar bigint'e
sığmalıdır. Tabloyla karşılaştırılamayan günler tarih aralıklarıyla yazılır.

`app/database/market_history.py` yazma başlamadan bütün rapor ürünlerinin
kimliğini veritabanıyla karşılaştırır; uyuşmazlıkta hiçbir ürün yazılmaz.
Katalog eşitlemez, ürün oluşturmaz, tur açmaz veya eski turu kapatmaz.
Ortak dosya kilidi ve mevcut veritabanı tur kilidi kullanılır; kilit meşgulse
beklenmez. Normal aktarımda ürün başına READ COMMITTED transaction açılır.
Önce mevcut günler karşılaştırılır; `ON CONFLICT DO NOTHING` ile eklenir;
aynı transaction içinde tekrar okunup karşılaştırılmadan commit edilmez.
Böylece ilk kontrolden sonra eşzamanlı eklenen farklı fiyat da bütün ürünün
geri alınmasına yol açar. [PostgreSQL eşzamanlılık belgeleri](https://www.postgresql.org/docs/17/transaction-iso.html)

Anahtar `(product_id, source, day)`; `source` yalnız `cimri`, Cimri kimliği
pozitif rakam dizisi, adres HTTPS Cimri telefon yolu, fiyat pozitif bigint
veya NULL'dır. Tarih ve alım zamanı sonlu olmalıdır. Üç SHA-256 alanı HTML,
API ve alım raporunun **yerel dosya baytlarına** aittir. Bunlar kaynak
imzası değildir; raporun kendisi güvenilir bir dijital imzayla doğrulanmaz.
004, yalnız yeni tablo ve onun korumalarını ekler: UPDATE reddedilir;
DELETE/TRUNCATE mevcut `reject_delete` işleviyle engellenir. 001–003 değişmez.

Aynı günün fiyatı ve Cimri kimliği aynıysa ilk satır bütün alanlarıyla
korunur; adres/zaman/parmak izi değişimi tek başına çelişki değildir.
NULL–NULL aynı, NULL–fiyat farklıdır. Bir gündeki fiyat veya Cimri kimliği
farklıysa o üründe hiç yeni gün yazılmaz; diğer doğrulanmış ürünler devam
eder. SQL/bağlantı hatasında komut durur, tamamlanan ürünler kalır. COMMIT
yanıtı kaybolduğunda son ürünün sonucu belirsiz olarak bildirilir; yeniden
çalıştırma aynı kaydı çoğaltmadan sonucu netleştirir.

`--dry-run` tek REPEATABLE READ, READ ONLY transaction'da çalışır; INSERT
deneyip geri almaz. Önizleme yazma yetkisi veya sonuç rezervasyonu değildir;
normal komut bütün kontrolleri yeniden yapar. Çıktı her ürünü, eklenecek/aynı
kayıtları, çelişkili tarihleri ve eski/yeni kuruş fiyatı ile Cimri kimliğini
gösterir. Kaynak dosyalarına veya giriş raporuna yazılmaz; çıktı terminaldedir.
[PostgreSQL READ ONLY belgeleri](https://www.postgresql.org/docs/17/sql-set-transaction.html)

Çıkışlar: **0** girdideki ürünler aktarıldı/zaten aynı; **2** atlanan veya
çelişkili ürün var; **1** yapı/kimlik/şema/veritabanı hatası; **3** kilit
meşgul; **130** Ctrl+C. Kesintide son ürün ya tamamen yazılır ya hiç yazılmaz;
önceki ürünler korunur. Global katalogdaki eşleştirmesiz ürünler seçili
girdide yoksa komutun başarısını değiştirmez; katalog kapsamı ayrıca raporlanır.

### Gerçek aktarımın akışı

Her alım ayrı klasörde saklanır. Raporlar birleştirilmez/değiştirilmez; ek
alım yalnız başarısız/denenmemiş ürünleri tamamlar. Her kabul edilen ürünün
kaynak klasörü ve rapor hash’i belirlenir. Önce ana alım, sonra eksikleri
karşılayan ek alımlar önizlenir ve kullanıcı tarafından ayrı ayrı aktarılır.
Önizleme ve rapor değerlendirmesinden önce gerçek aktarım başlatılmaz.

Bağımsız doğrulama READ ONLY sorgularla bütün geçmiş satırlarını kaynakla
karşılaştırır: ürün/kaynak/kimlik/adres/gün/kuruş/zaman ve üç hash.
Ürün başına sayı, tarih aralığı ve NULL sayısı ayrıca raporlanır. Kullanıcının
aynı girdiyi tekrar aktarımında 0 yeni kayıt ve ilk kaynak bilgilerinin
korunması beklenir; atlanan ürünler nedeniyle çıkış 2 sürebilir.

### Kullanım değerlendirmesi

Cimri'nin [kullanım koşulları](https://www.cimri.com/kullanim-kosullari)
(2.2, 3.1, 4.12) kullanım amacını, kopyalamayı/işlemeyi ve başka mecrada
kullanımı sınırlıyor; [kullanıcı sözleşmesi](https://www.cimri.com/kullanici-sozlesmesi)
üyelik sözleşmesidir. 19 Ekim 2026 incelemesinin sonucu:

| Projedeki amaç | Teknik inceleme sonucu | Uygun kullanım doğrulandı mı? |
|---|---|---|
| Yeni geçmişi indirme ve saklama | Kısıtlı | Hayır |
| Mevcut geçmişi yerel uygulamada gösterme | Belirsiz | Hayır |
| ML eğitiminde kullanma | Belirsiz | Hayır |

Bu, kesin hukuki izin kararı değildir; eğitim/staj amacı tek başına izin
kanıtı sayılmadı. Bu yüzden yeni alım/aktarım yapılmadı; mevcut veri ve
gösterim korunuyor. [Akakçe kullanım sözleşmesi](https://www.akakce.com/kullanim-sozlesmesi/)
de benzer kısıtlar içerir.

Galaxy S25 512 GB ve Redmi Note 14 Pro 5G 256 GB için doğru Cimri ana
sayfası bulunamadı (incelenen adaylar Plus 512 GB, normal S25 256 GB,
Redmi 5G 512 GB ve 4G 256 GB idi). Bu, ürünlerin Cimri'de olmadığı
anlamına gelmez; başka kapasite/model bunların yerine konmaz.

## Yerel API: kurulum ve okuma hesabı

### Bağımlılıklar ve HTTP sınırı

`web` grubu FastAPI 0.142.4, Uvicorn 0.54.0, Streamlit 1.65.0,
Psycopg Pool 3.3.3, HTTPX 0.28.1 ve Altair 6.3.0 içerir. Python 3.13'te
`pip install -e ".[dev,web]"` ile kurulur; `pip check` bağımlılık uyumunu
denetler. Temel toplama bağımlılıkları ve yazıcı bağlantı kodu değişmedi.
Sürümler sabittir; yükseltme ayrı karar ve tam test ister. [FastAPI](https://pypi.org/project/fastapi/),
[Streamlit](https://pypi.org/project/streamlit/).

AGENTS/mimari testine işlenen tek HTTPX istisnası
`app/ui/api_client.py` içindir: yalnız yerel API, yönlendirme izlemeden,
ortam proxy'si kullanmadan ve zaman aşımıyla. İstemci sabit
`http://127.0.0.1:8000` adresine gider; hedef/yönlendirme/zaman aşımı
`tests/test_api_client.py` içinde sınanır; diğer `app/` modüllerinin HTTPX izni yok.
Pazaryeri erişimi yalnız `app/scraper/http.py` ve curl_cffi üzerinden sürer.

### Okuma hesabının bir kerelik kurulumu

Önce 001–004 uygulanmış olmalıdır. `scripts/api_okuma_rolu.sql` yönetici
hesabıyla çalışır; yeni tablo/migration yoktur. `fiyat_takip` DB'sinde
`fiyat_takip_api`, `_test` DB'sinde `fiyat_takip_api_test` seçilir. Diğer DB
adları reddedilir. Script tekrar çalışabilir; mevcut rolün yönetici/üye/sahip
veya yazma yetkili olması hata üretir, kurulumun bütün izinleri geri alınır.

Verilen izinler CONNECT, public şemasına USAGE ve şu sekiz nesneye SELECT:
`schema_migrations`, `platforms`, `products`, `listings`, `collection_runs`,
`listing_checks`, `product_run_prices`, `market_history`. Yeni nesnelere
otomatik izin verilmez. Rolün varsayılan işlemi READ ONLY'dir; bu varsayılan
kapatılsa da proje tablolarına yazma ve kalıcı nesne oluşturma izni yoktur.

PostgreSQL'in `psql.exe` yolu bu bilgisayarda doğrulanmıştır. Tam yollarla
herhangi bir PowerShell klasöründen, kullanıcı yönetici şifresini terminale
girerek çalıştırır:

```powershell
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PGCLIENTENCODING = "UTF8"
$apiPsql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
& $apiPsql -X -h localhost -U postgres -d fiyat_takip_test -v ON_ERROR_STOP=1 -c "SET client_encoding TO 'UTF8';" -f "C:\Users\Emir\Desktop\Staj\scripts\api_okuma_rolu.sql"
& $apiPsql -X -h localhost -U postgres -d fiyat_takip_test
```

SQL dosyası UTF-8'dir. Kodlama ayarı verilmezse psql Türkçe Windows'ta
WIN1254 kullanır ve kurulum hata verir; COMMIT'e ulaşılmaz. Yukarıdaki komut dosyadan önce bağlantının kodlamasını açıkça
UTF8 yapar; `-X` kişisel psql başlangıç dosyasını devre dışı bırakır.
Kurulum ancak rol hazır bildirimi, DO ve COMMIT görüldüğünde başarılı sayılır.

Açılan psql oturumunda `\password fiyat_takip_api_test` ile şifre belirlenir,
`\q` ile çıkılır. Şifre mesaja veya repoya yazılmaz; mevcut
`%APPDATA%\postgresql\pgpass.conf` dosyasına kullanıcı tarafından eklenir:

```text
localhost:5432:fiyat_takip_test:fiyat_takip_api_test:SEÇİLEN_ŞİFRE
```

Üretim rolü gerektiğinde aynı dosya `-d fiyat_takip` ile kullanıcı tarafından
çalıştırılır; oturumda `\password fiyat_takip_api`, pgpass'ta
`localhost:5432:fiyat_takip:fiyat_takip_api:SEÇİLEN_ŞİFRE` kullanılır. Asistan
gerçek DB'ye rol/izin/fiyat yazmaz. Bu işlem mevcut `fiyat_takip` yazıcı rolünü,
tur kilitlerini, tabloları ve zamanlayıcıları değiştirmez.

Şifresiz adresler; `setx` yeni terminal/süreç için, `$env:` mevcut terminal için:

```powershell
setx TEST_API_DATABASE_URL "postgresql://fiyat_takip_api_test@localhost:5432/fiyat_takip_test"
$env:TEST_API_DATABASE_URL = "postgresql://fiyat_takip_api_test@localhost:5432/fiyat_takip_test"
```

Gerçek API ayrı `API_DATABASE_URL` değeriyle çalışır:
`postgresql://fiyat_takip_api@localhost:5432/fiyat_takip`. `DATABASE_URL`'e
dönüş yoktur.

### Test ortamı ve sınırı

Tam testler `dev,web` kurulumu, `TEST_DATABASE_URL` ve rol testleri için
`TEST_API_DATABASE_URL` ister. Her iki bağlantı aynı `_test` DB olmalı;
okuma bağlantısının kullanıcısı `fiyat_takip_api_test` olmalı. `db` test başında
şemayı boşalttığı için `api_db`, mevcut test rolüne yeni şemanın SELECT
izinlerini yeniden verir; yönetici rolü veya şifre oluşturmaz. Üretim adresleri
her testte ortamdan silinir. API adresi yoksa rol testleri yerelde atlanır;
CI'da başarısız olur. CI kendi geçici sunucusunda test hesabını kurar.

Gerçek HTTPX ağ transport'ları otomatik testlerde kapalıdır;
MockTransport/ASGI/TestClient süreç içinde çalışır. Yerel API'ye gerçek ağ
isteği de otomatik testte engellenir. Bu, uygulamanın dış adrese gitmeme
kuralıyla aynı kontrol değildir; istemcinin sabit hedef sınırı
ayrıca sınanır.

Starlette 1.6.0 TestClient, mevcut HTTPX uyumu ve AnyIO takma adı için iki
kullanım sonlandırma uyarısı veriyor; testler başarılı, uyarılar gizlenmedi.

## Salt okunur veritabanı okumaları

`app/database/read.py` yalnız hazır Psycopg bağlantısıyla çalışır; ortam
adresi seçmez, bağlantı açmaz/kapatmaz. Ürün için mevcut değiştirilemez
`Product` sözleşmesi kullanılır; tur, sayfa sonucu ve geçmişler aynı modüldeki
`frozen` veri sınıfları ve tuple'larla döner; HTTP/JSON cevabına API katmanı çevirir.

| İşlev | Sonuç |
|---|---|
| `list_products(conn)` | Etkin ürünler, artan ürün kimliğiyle `tuple[Product, ...]` |
| `read_run_status(conn)` | Kayıtlı running ve en yüksek kimlikli global completed tur; olmayan alan `None` |
| `read_product(conn, product_key, history_days=30, cimri_days=366)` | `ProductSnapshot`: ürün, güncel tur, sayfa sonuçları, en ucuz/son başarılı teklif, kendi ve ayrı Cimri geçmişi; bilinmeyen ürün `None` |

Pasif ürün doğrudan anahtarıyla okunabilir; etkinlik bilgisi korunur ve ürün
listesine eklenmez. Sorgular parametrelidir.

### İşlem ve hata sözleşmesi

Her giriş bağlantının işlemsiz olmasını ister. Açık işlem `ValueError` ile
reddedilir; çağıranın işlemi sonlandırılmaz. Kapalı bağlantı
`psycopg.InterfaceError` üretir. Kendi işleminde REPEATABLE READ, READ ONLY,
5 saniyelik `statement_timeout` ve UTC kurulur; işlem bitince bağlantının
önceki ayarları geri gelir. Sorgu hatası yükselir ve okuma işlemi geri alınır;
boş veri gibi gösterilmez. Başarılı veya SQL hatalı okumadan sonra açık
bağlantı yeniden kullanılabilir.

Tek işlem bütün ürün cevabını aynı veritabanı görüntüsünden kurar;
eşzamanlı tamamlanan tur veya katalog değişikliği cevabın ortasında görünmez.
Toplama kilidi alınmaz, migration/katalog eşitleme/tur kapatma çağrılmaz.
İşlem yönetiminin dayanağı
[PostgreSQL yalıtımı](https://www.postgresql.org/docs/17/transaction-iso.html)
ve [Psycopg işlemleridir](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).

### Güncel sonuç ve geçmişlerin anlamı

- Güncel tur, ürünün kendisini içeren en yüksek `run_id` değerli completed
  turdur. Başka ürünün daha yeni sınırlı turu sonucu gizlemez;
  running/interrupted turlar elenir.
- O turdaki bütün planlanan sayfalar okunur. Mevcut katalogdaki pasif
  sayfa/platform geçmiş sonucu elemez. En ucuz teklif ve eşit fiyatta küçük
  sayfa kimliği seçimi `product_run_prices` görünümünden gelir.
- `state`: fiyat varsa `offer`; bütün sayfalar sold_out ise `sold_out`;
  fiyat yokken hata/sonuçsuz sayfa varsa `unverified`; ürünün tamamlanmış turu
  yoksa `no_history`. `partial`, cevaplanan sayfalar planlananlardan azsa
  doğrudur. Hata ve henüz cevaplanmamış sayılar ayrı tutulur.
- `last_successful_offer` ayrı bilgidir; güncel fiyatın yerine geçirilmez.
  `best_checked_at` seçilen teklif zamanı, `last_checked_at` turun ürüne ait
  son kontrol zamanıdır.
- Fiyat/satıcı/stok kayıtlı sonuçtan; URL/renk/etkinlik mevcut katalogdan
  gelir. Geçmiş URL veya renk varmış gibi sunulmaz.
- Kendi `history` aralığı, son completed ürün turunun başlangıcı eksi
  `history_days` ile bu başlangıç arasındadır; iki sınır dahildir.
  Cimri aralığı ürünün son kayıtlı günü dahil `cimri_days` takvim günüdür.
  Bugünün tarihi esas alınmaz. Parametreler 1–366 tam sayı olmalıdır;
  bool, metin ve kesirli sayılar kabul edilmez.
- Fiyatsız turlar/günler `None` kalır; boş gün eklenmez ve seriler birleşmez.
  Kuruşlar tam sayı, zamanlar UTC, Cimri günü `date`'tir. Görünen aralığın
  dışındaki önceki tur karşılaştırması korunur. `all_history` bütün
  tamamlanmış ürün turu özetlerini ve planlanan sayfa kimliklerini istatistik
  hesabı için tutar; okuma katmanı dip/zirve/değişkenlik hesaplamaz.

## Fiyat istatistikleri

`app/price_statistics.py → calculate_statistics(snapshot)`, `read_product`
okumasının `ProductSnapshot` sonucunu alır ve değiştirilemez `ProductStatistics` döndürür.
Veritabanı, ağ, dosya veya bugünün saati kullanılmaz; giriş değiştirilmez.

### Kapsam dönemi ve sonuç alanları

`all_history` içindeki son completed ürün turundan geriye gidilir.
`answered_pages == planned_pages` olan ve planlanan sayfa kümesi aynı kalan
turlar alınır; ilk eksik cevap veya farklı küme döneme katılmadan yürüyüşü
keser. Kümenin sırası önemli değildir. Son tur eksikse eski döneme dönüş yok;
bütün göstergeler `None` döner. Tükendi geçerli cevaptır; bütün sayfaları
Tükendi olan tur dönemde kalır. Zaman boşluğu dönemi tek başına kesmez.

Bu şart, görünümün cevap veren sayfa kümesi karşılaştırmasından daha
sıkıdır. Örneğin aynı sayfalar iki turda hata alsa da görünüm karşılaştırmayı
kabul edebilir; istatistikler eksik cevaplı turu kabul etmez.
`comparable_with_previous` ve mevcut tur karşılaştırma davranışı değişmez.

`ProductStatistics` kaynak tur kimliği, kapsam başlangıç/bitişi, tur sayısı,
planlanan sayfa kimlikleri ve üç gösterge taşır:

| Gösterge | Hesap |
|---|---|
| `low_30d` | Kapsam süresi en az 30 günse son 30 gündeki geçerli fiyat minimumu, tam sayı kuruş |
| `high_in_scope` | Bütün mevcut kapsam döneminin geçerli fiyat maksimumu, tam sayı kuruş; 30 gün şartı yok |
| `volatility_30d` | Son 30 gündeki geçerli ardışık fiyat değişimlerinin örnek standart sapması × 100, ondalıklı sayı |

Her göstergede `value`, `reasons`, `period_started_at`, `period_ended_at` ve
`observations` vardır. Dip/zirvede gözlem sayısı dönemindeki fiyatlı tur
sayısıdır; değişkenlikte kabul edilen geçişlerin uçlarındaki farklı tur
sayısıdır. Değişkenlik ayrıca `transitions` ve `days` taşır.
Son tur eksik veya geçmiş yoksa kullanılan dönem yoktur; dönem alanları
`None`, kullanılan tur/gözlem sayıları sıfırdır.

30 günlük pencere son ürün turunun başlangıcından geriye açılır; tur
başlangıçlarına göre iki sınır dahil olur. Göstergenin dönem başlangıcı,
kapsam başlangıcı ile pencere başlangıcından daha yeni olanıdır.
Grafik için `history_days` veya Cimri için `cimri_days` seçimi hesabı
değiştirmez; hesap `all_history` kullanır. Cimri serisi katılmaz.

### Değişkenlik ve yeterlilik

Getiri `log(yeni/eski)`'dir. Yalnız kapsam içindeki ardışık iki turun da
30 günlük pencerede olması, fiyatlarının ve gerçek `best_checked_at`
zamanlarının bulunması yeterli geçiş adayıdır. Kontrol zamanları arasındaki
fark pozitif ve en çok 18 saat olmalıdır; **tam 18 saat kabul edilir**,
yuvarlanmış `hours_since_previous` kullanılmaz.
Fiyatsız/uzun boşluklu tur üzerinden fiyatlar birleştirilmez.

En az 14 geçerli geçiş ve 7 farklı İstanbul takvim günü gerekir.
Günler yalnız kabul edilen geçişlerin iki ucunun gerçek kontrol zamanından,
`ZoneInfo("Europe/Istanbul")` ile sayılır. Bu iki zaman/gün kuralı 9 Ekim
2026'da kullanıcıyla kararlaştırıldı. Bu eşikler proje kararıdır; evrensel istatistiksel yeterlilik iddiası değildir.

Hesap [`statistics.stdev`](https://docs.python.org/3.13/library/statistics.html#statistics.stdev)
ile örnek standart sapmasını kullanır (varyansta bölen `n−1`).
[`ZoneInfo`](https://docs.python.org/3.13/library/zoneinfo.html)
mevcut `tzdata` bağımlılığıyla Windows'ta da çalışır.
Sonuç yuvarlanmaz, yıllıklaştırılmaz. Yeterli veriyle `0.0` gerçek sonuçtur;
bu, bütün fiyatların aynı olması kadar bütün oransal değişimlerin aynı olması
durumunda da görülebilir. Bir indirim olasılığı veya fiyat değişim yüzdesi değildir.

| Gerekçe | Anlamı |
|---|---|
| `no_history` | Kendi tamamlanmış ürün turu yok |
| `incomplete_scope` | Son ürün turunda bütün planlanan sayfalar cevaplanmadı |
| `insufficient_period` | Dibe uygun mevcut kapsam dönemi 30 güne ulaşmadı |
| `no_prices` | İlgili dönemde kayıtlı geçerli fiyat yok |
| `insufficient_transitions` | Değişkenlik için 14 geçerli geçiş yok |
| `insufficient_days` | Geçerli geçişlerin uçları 7 İstanbul gününü kapsamıyor |

Geçmiş yokluğu/eksik son turda ilgili tek kapsam gerekçesi döner. Kullanılabilir
dönemde birden fazla yeterlilik şartı eksikse ilgili gerekçeler birlikte
`tuple` içinde döner; başarılı göstergede bu liste boştur.
Yetersiz değer `None` kalır; fiyatlar doldurulmaz.

## Salt okunur FastAPI

`create_app()` salt okunur okumaları ve fiyat istatistiklerini yerel HTTP
adreslerinden sunar. Modül içe aktarılırken veya fabrika çağrılırken bağlantı
açılmaz; havuz FastAPI lifespan başlangıcında açılır, kapanışta bırakılır.
Sorgulu adresler normal `def` işlevleriyle çalışır.
[FastAPI yaşam döngüsü](https://fastapi.tiangolo.com/advanced/events/)
ve [eşzamanlı işlevler](https://fastapi.tiangolo.com/async/#path-operation-functions).

### Ayar, havuz ve hazır olma

Yalnız `API_DATABASE_URL` okunur; `DATABASE_URL`'e dönüş yoktur. Kullanıcı ve
veritabanı açıkça belirtilmelidir. Eksik/ayrıştırılamayan ayar bağlantı
adresini göstermeyen Türkçe başlangıç hatası verir. Şifre pgpass'ta kalır.

Havuz min 1/max 4 bağlantı; edinme sınırı 3 sn, yeni bağlantı zaman aşımı
3 sn'dir. Bağlantılar autocommit ve varsayılan READ ONLY çalışır; oturum
UTC, sorgu sınırı 5 sn, search_path `pg_catalog,public` olur.
Bozuk boşta bağlantı ödünç verilmeden denetlenir ve elenir.

Kullanıcının kararıyla başlangıç veritabanını beklemez: geçici kesintide API
açık kalır ve 503 verir. Psycopg havuzunun tekrar denemeleri ve sonraki
isteklerin bağlantı edinmesiyle düzelme sonrası aynı uygulama yeniden
okuyabilir. Bağlantı bilgisi/hazırlık hatası veriyi boş başarılı cevap gibi
göstermez. [Psycopg havuzu](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)

Her veri isteğinde ayrı kısa REPEATABLE READ, READ ONLY işlemle:

- Gerçek veritabanı ve current/session kullanıcıları denetlenir. `fiyat_takip`
  için `fiyat_takip_api`, `_test` için `fiyat_takip_api_test` kabul edilir.
- Ayrıcalıklı rol, üyelik, nesne sahipliği, kalıcı nesne oluşturma veya
  public nesnelerinde tablo/sütun yazma izni reddedilir. Sekiz gerekli
  tablo/görünümün varlığı ve SELECT izinleri denetlenir.
- Mevcut `pending` migration denetimi kullanılır: eksik, bilinmeyen veya
  ad/parmak izi uyuşmazlıklı migration şemayı hazır olmaktan çıkarır.

Hazırlık işlemi kapanınca okuma işlevi (`read_product`) kendi tutarlı salt okunur
işlemini açar; dış işlemle sarılmaz. Başarı veya hata sonrası bağlantı
havuza geri verilir. API migration/rol kurulumu, katalog eşitleme veya
toplama/keşif başlatmaz; tarama/tur kilidi almaz.

### Adresler ve cevaplar

| GET adresi | Cevap |
|---|---|
| `/health` | Hazırsa `{"ready": true}`; DB/yetki/şema hazır değilse 503 |
| `/api/v1/status` | `running` ve son global `completed`; olmayan alan `null` |
| `/api/v1/products` | Kimlik sırasıyla etkin ürün dizisi |
| `/api/v1/products/{product_key}` | Ürün cevabı; pasif ürün doğrudan okunabilir, bilinmeyen ürün 404 |

Ürün parametreleri `history_days=30` ve `cimri_days=366`; ikisi de 1–366.
Okuma katmanının son kayıtlı veriden açtığı, sınırları dahil aralıklar korunur.
Adresler/cevap modelleri `/docs` ve `/openapi.json` üzerinden belgelenir.
Önbellek yoktur; cevaplar `Cache-Control: no-store` taşır.

Ürün cevabı `product`, `state`, `current`, `checks`, `best_offer`,
`last_successful_offer`, `history`, `cimri_history`, `statistics`,
`generated_at`, `currency`, `price_age_seconds` ve `is_stale` alanlarıdır.
Tek `read_product` çağrısının görüntüsünden hazırlanır; istatistikler aynı
görüntünün bütün iç geçmişini kullanır. `all_history` JSON'a gönderilmez.

- Para alanları tam sayı TRY kuruşudur; float'a çevrilmez. Zamanlar UTC
  RFC 3339 metni, Cimri günü `YYYY-MM-DD`, tuple'lar JSON dizisidir.
  Eksikler `null`, olmayan seriler `[]` kalır; seriler birleştirilmez.
- Satıcı puanı/ölçeği ve saat aralığı JSON'da sonlu sayı olarak döner.
  Kapsam sayıları, `partial`, `unchecked_pages` ve önceki tur
  karşılaştırılabilirliği korunur; önceki teklif güncel fiyatın yerine geçmez.
- `generated_at` cevap hazırlanma zamanıdır. Güncel teklifin gerçek kontrol
  zamanıyla yaş saniye olarak hesaplanır; tam 18 saatte `is_stale=true`.
  Gelecekteki kontrol zamanı negatif yaş yerine 0 üretir; eski sayılmaz.
  Güncel teklif yoksa yaş/eski işareti `null`; son kontrol zamanı
  `current.last_checked_at` alanında kalır.
- İstatistik değer/gerekçe/dönem/gözlem/geçiş/gün sayıları istatistik hesabından aynen gelir.
  Ham `error_message` ve tur `note` dışarı verilmez; sayfanın `error_code`
  bilgisi korunur. URL/renk/etkinlik mevcut katalog kopyasıdır.

Pydantic cevap modelleri geçersiz alanı başarılı cevap olarak kabul etmez.
[FastAPI cevap modelleri](https://fastapi.tiangolo.com/tutorial/response-model/)

### Hatalar

Hata biçimi: `{"detail": {"code": "...", "message": "Türkçe açıklama"}}`.
Bağlantı adresi/şifre/SQL/ham istisna cevaba eklenmez.

| HTTP | Kod | Anlam |
|---|---|---|
| 404 | `product_not_found` / `not_found` | Ürün veya adres bulunamadı |
| 405 | `method_not_allowed` | Yazma isteği kabul edilmez |
| 422 | `invalid_request` | Gün parametreleri geçersiz |
| 503 | `pool_unavailable` | Havuzdan bağlantı edinilemedi |
| 503 | `database_unavailable` | DB bağlantısı/sorgusu veya zaman aşımı |
| 503 | `read_access_denied` | Okuma hesabı/izinleri uygun değil |
| 503 | `schema_not_ready` | Şema eksik/tutarsız |
| 500 | `internal_error` | Beklenmeyen kod/cevap doğrulama hatası |

### Yerel başlatma

Ayrı bir API terminalinde:

```powershell
$env:API_DATABASE_URL = "postgresql://fiyat_takip_api@localhost:5432/fiyat_takip"
.venv\Scripts\python.exe -m uvicorn app.api.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

Tek çalışan süreç ve yalnız yerel adres kullanılır; API için zamanlayıcı
görevi yoktur.

## Yerel API istemcisi

`app/ui/api_client.py` içindeki `ApiClient`, Streamlit'in kullanacağı
eşzamanlı okuma istemcisidir. Ekran, veritabanı bağlantısı veya hesaplama
içermez. Dört GET yalnız `http://127.0.0.1:8000` adresine gider;
adres/port ortam ayarı veya genel URL isteyen işlev yoktur.

### Ortak sözleşme ve işlevler

`app/api/schemas.py` mevcut cevap modellerini bağımsız tutar.
İstatistiklerin `Reason` tipi temel sözleşmededir; hesaplar değişmedi.
API'nin `models.py` modülü kaynak görüntüsünü ortak cevaba dönüştürür.
İstemci yalnız ortak sözleşmeleri yükler; DB/havuz/istatistik/uygulama
modüllerini içe aktarmaz. API JSON alanları ve OpenAPI bütünü öncekiyle aynıdır.

| İşlev | Doğrulanmış sonuç |
|---|---|
| `get_health()` | `HealthResponse` |
| `get_status()` | `StatusResponse`; bulunmayan turlar `None` |
| `list_products()` | Değiştirilemez `tuple[Product, ...]` |
| `get_product(product_key, history_days=30, cimri_days=366)` | `ProductResponse`; teklifler, iki ayrı geçmiş ve mevcut istatistikler |

Anahtar mevcut `Key` kuralını, günler katı 1–366 tam sayı koşulunu sağlamalı;
`bool`/ondalıklı sayı/metin gün sayılmaz. Geçersiz girdide HTTP yoktur.

JSON doğrudan baytlardan `validate_json(..., strict=True)` ile okunur.
Tarihler/tuple'lar JSON karşılıklarından uygun Python türüne dönüşür;
para tam sayı kuruş, zamanlar UTC, Cimri günleri `date` kalır.
Eksikler `None`; sıfırla doldurma, eski tekliften güncel fiyat üretme veya
istatistikleri yeniden hesaplama yoktur.
[Pydantic JSON doğrulaması](https://docs.pydantic.dev/latest/concepts/json/)

API'nin varsayılanlı alanları dahil gönderdiği bütün alanlar JSON'da
bulunmalıdır. İstemci alan tamlığını da denetler: eksik `ready`,
`currency` veya ürün `active` alanı varsayılanla doldurulup başarılı
gösterilmez. Bu kontrol API'nin nesne kurma varsayılanlarını değiştirmez.

### Hedef, zaman aşımı ve yaşam döngüsü

İstek gönderilmeden GET yöntemi, şema/host/port, dört izinli yol ve
ürün isteğinin yalnız iki gün parametresi denetlenir. Anahtar bir URL veya
başka yol oluşturamaz. Kullanıcı bilgisi/fragment, dış hedef ve tekrarlanan
sorgu parametresi reddedilir.

HTTPX `trust_env=False` ve `follow_redirects=False` kullanır; ortam
proxy'leri yok sayılır. Herhangi bir 3xx yönlendirme hata olur,
`Location` adresine ikinci istek yapılmaz.
[HTTPX ortam ayarları](https://www.python-httpx.org/environment_variables/)

Bağlanma, yazma ve HTTP bağlantı havuzu beklemesi 3 sn; okuma beklemesi
15 sn'dir. HTTPX bunları işlem aşamalarında uygular; 15 sn toplam istek
süresi garantisi değildir.
[HTTPX zaman aşımı davranışı](https://www.python-httpx.org/advanced/timeouts/)

Otomatik tekrar ve veri önbelleği yoktur. Her çağrı yeni GET yapar; hata
sonrası sonraki çağrı aynı istemciyle yeniden okuyabilir. İçe aktarmada veya
nesne kurmada ağ bağlantısı açılmaz. Cevap başarı/hatada kapatılır;
istemci `with` veya idempotent `close()` ile bırakılır. Ctrl+C aynen yükselir.
[HTTPX istemci yaşam döngüsü](https://www.python-httpx.org/advanced/clients/)

Kullanım örneği (API açıkken):

```python
from app.ui.api_client import ApiClient

with ApiClient() as client:
    products = client.list_products()
    detail = client.get_product(products[0].product_key) if products else None
```

### Hatalar

`ApiClientError`, `code`, güvenli Türkçe `message` ve varsa `status_code`
taşır. Ham gövde, sunucunun mesajı, SQL veya HTTPX istisna metni gösterilmez.
Bilinen API kodu ancak beklenen HTTP durumuyla eşleşiyorsa korunur.

| Kod | Anlam |
|---|---|
| `invalid_request` | Geçersiz anahtar/gün; yerelde reddedildiyse HTTP durumu yok |
| `invalid_target` | İzinli sabit yerel hedef/yol/sorgu koşulu sağlanmadı |
| `client_closed` | Kapatılmış istemci tekrar kullanıldı |
| `timeout` | HTTPX bağlantı/okuma/yazma/havuz beklemesi doldu |
| `connection_error` | Bağlantı/aktarım/protokol hatası |
| `redirect_rejected` | 3xx cevap; yönlendirme izlenmedi |
| `invalid_response` | 200 cevabı bozuk/eksik veya beklenmeyen başarılı HTTP durumu |
| Mevcut API kodu | Bilinen 404/405/422/500/503; güvenli yerel Türkçe karşılık |
| `http_error` | Bilinmeyen, bozuk veya durum/kodu uyuşmayan HTTP hatası |

Hata boş liste veya önceki veriye çevrilmez. Beklenmeyen programlama hatası
da bağlantı hatası gibi gizlenmez.

## Streamlit ekranı

`app/ui/main.py` aynı bilgisayardaki API'nin doğrulanmış sonuçlarını gösterir.
`presentation.py` yalnız biçimlendirme ve grafik verisini hazırlar;
veritabanına veya pazaryerine erişmez. API/JSON sözleşmeleri aynı kaldı.

### Ekran ve veri anlamı

- Ürün seçimi etkin API listesinden, ürün anahtarıyla korunur. Seçilen ürün
  etkin listeden çıkarsa bilgi verilerek ilk etkin ürün seçilir. Liste boşsa
  açıklama gösterilir; veri hatası boş listeye çevrilmez.
- Güncel teklif, bütün sayfaların stoksuz olması, doğrulanamayan fiyat ve
  tamamlanmış ürün turunun yokluğu ayrı gösterilir. Önceki başarılı teklif
  ayrı açılır bölümdedir; güncel teklifin aynısı ikinci kez gösterilmez.
- Platform/satıcı/puan/ölçek/renk/stok ve gerçek kontrol zamanı gösterilir.
  Kritik stok kayıtlı durumdan, eski fiyat uyarısı API'nin `is_stale`
  değerinden gelir. Güncel fiyat farkı yalnız API karşılaştırılabilir diyorsa
  önceki fiyatla hesaplanır. Satıcının eski fiyatı ayrıca etiketlenir.
- Fiyat/stok cevabı sayısı, hata ve kontrol edilmeyen sayfa sayısı ayrı
  gösterilir. Kısmi kapsam uyarısı vardır. Sayfa tablosu bugün pasif olan
  sayfa/platformu elemez; adres/renk/etkinlik mevcut katalog bilgisidir.
- Dip, kapsam zirvesi ve değişkenlik API'den aynen alınır. Eksik göstergeler
  sıfırla doldurulmaz; Türkçe gerekçe, dönem ve gözlem/geçiş/gün sayıları
  gösterilir. Değişkenlik yalnız gösterimde iki ondalıkla biçimlenir;
  kaynak değeri ve hesap değişmez. Sıfır değişkenlik `0,00` olarak görünür.
- Fiyat metni tamsayı kuruştan üretilir; saatler Europe/Istanbul'dur.
  Global tur ve ürün turu ayrı etiketlenir; iki API okumasının aynı
  veritabanı görüntüsü olduğu iddia edilmez.

### Grafikler ve yenileme

İki grafikte bağımsız 7/30/90/366 gün seçimi vardır. Varsayılan kendi
geçmişi 30, Cimri 366 gündür; API'nin son kayıtlı veriden geriye açtığı
aralık kullanılır. Grafik aralığı istatistikleri değiştirmez.

Kendi grafiğinde tur başlangıcı eksendedir; tooltip fiyatın gerçek kontrol
zamanını ve kapsamı taşır. Çizgi yalnız ardışık fiyatlı, tam cevaplanmış,
aynı planlanan sayfa kümesine sahip turlar arasında kurulur. Gerçek teklif
kontrol zamanlarının farkı pozitif/en çok 18 saat olmalıdır; tam 18 saat
kabul edilir. Eksik fiyat, kısmi kapsam, küme değişimi ve uzun boşluk çizgiyi
keser. Kısmi fiyat noktası elmasla görünür. Tek nokta çizgi olmasa da görünür.

Cimri ayrı grafiktedir. NULL ve ardışık olmayan tarihler çizgiyi keser;
eksik gün oluşturulmaz. Hiç kayıt yoksa “Cimri geçmişi bulunmuyor” denir;
neden tahmin edilmez. Kayıt var/fiyatların hepsi eksik durumu ayrıca açıklanır.
Tekrarlanan fiyatlar bağımsız günlük ölçüm kanıtı olarak sunulmaz.

Altair'da bölüm kimliği ve `invalid="break-paths-show-domains"` açıkça
kullanılır. NULL satırları grafik hazırlığında korunur; sıfıra dönüştürülmez.
Grafik çizim sayıları TL, tooltip fiyat metni doğrudan tamsayı kuruştandır.
Kendi zaman ekseni tarayıcı saatinden etkilenmesin diye yalnız çizimde
İstanbul duvar saati UTC ölçeğine kodlanır; gerçek API zamanları UTC kalır.
[Vega-Lite eksik veri davranışı](https://vega.github.io/vega-lite/docs/invalid-data.html)

Streamlit satırları Altair tanımından ayırıp ayrı yükler; ön yüz grafiği
satırlar gelmeden boş başlatır. Boş başlangıçta Vega'nın `Infinite extent`
uyarısı vermemesi için `presentation.py::price_chart` eksen sınırlarını mevcut
satırlardan hazırlar: tarih sınırı UTC milisaniye sabit ifadesi, fiyat sınırı
yalnız dolu fiyatlardan (`nice=True` ile). Satırlar, eksik fiyatlar ve
boşluklar değişmez; konsol uyarısı susturulmaz.

Tek `st.fragment(run_every=30)` veri/seçim bölümünü oturum açıkken yeniler.
Elle Yenile düğmesi aynı bölümü çalıştırır. Her yenilemede ürün listesi,
global durum ve seçilen ürün yeniden okunur; istemci `with` ile bırakılır.
Yalnız seçim/aralık tercihleri oturumda tutulur; veri/istemci önbelleği yoktur.
API hatasında eski teklif/grafik/göstergeler kaldırılır, güvenli Türkçe hata
gösterilir; sonraki yenileme yeniden okuyabilir. Beklenmeyen kod hatası
olağan API hatası gibi gizlenmez.
[Streamlit fragment](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment)

### Başlatma ve test önizlemesi

Normal ekran (API açıkken):

```powershell
.venv\Scripts\python.exe -m streamlit run app\ui\main.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

API sunucusu ve veritabanı gerektirmeyen test önizlemesi:

```powershell
.venv\Scripts\python.exe -m streamlit run tools\ui_preview.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

Proje klasöründen çalıştırılır; tarayıcıda `http://127.0.0.1:8501` açılır.
İki ekran aynı portta birlikte başlatılmaz. Önizleme aynı `render_app`
işlevine testteki MockTransport istemcisini verir; üretim demo modu yoktur.
“Test verisi — gerçek fiyatlar değildir” uyarısı sürekli görünür.
`tests/support/ui_samples.py` örnekleri AppTest ve önizleme için ortaktır; gerçek
fiyat kanıtı değildir. Sidebar'dan teklif/boşluk, eski/kısmi fiyat, stoksuzluk,
doğrulanamama, yalnız Cimri, eksik geçmiş, API hatası ve boş liste denenir.

Telefon/aralık seçimi, dar ekran görünümü, grafik boşlukları ve hata sonrası
dönüş kontrol edilir. API cevabı saatinin açık oturumda yaklaşık 30 saniyede
değişmesi, elle Yenile'nin hemen yenilemesi ve tercihlerin korunması gözlenir.
Terminalde Ctrl+C önizlemeyi kapatır.

## SQL–API–Streamlit bağımsız denetimi

Yerel API'nin gerçek veritabanını doğru sunduğunu, üretim okuma/hesaplama
kodunu kullanmadan bağımsız SQL hesabıyla karşılaştırır. Katalog veya veri
değişikliğinden sonraki normal turun ardından, API açıkken üçüncü bir proje
terminalinde:

```powershell
$env:API_DATABASE_URL = "postgresql://fiyat_takip_api@localhost:5432/fiyat_takip"
$kontrolKlasoru = "artifacts\ui_7_7_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
.venv\Scripts\python.exe tools\api_ui_check.py --output-dir $kontrolKlasoru
$LASTEXITCODE
```

Araç yalnız okur; kilit almaz, tur başlatmaz. Rol/SELECT, nesne sahipliği,
fazladan yazma/CREATE yetkileri ve migration parmak izlerini denetler.
Temel tablolar tek REPEATABLE READ READ ONLY işleminde okunur. Üretim okuma,
cevap dönüştürme ve istatistik işlevleri beklenen sonuç için kullanılmaz.
Sağlık, global tur ve etkin ürün listesi; her ürünün 30/366 gün cevabındaki
kimlik, completed tur, bütün sonuçlar/teklifler/kapsam, önceki başarı,
karşılaştırılabilirlik, iki geçmiş ve istatistikler karşılaştırılır. Fiyatlar
birebir; yalnız değişkenlik değeri rel_tol=1e-9/abs_tol=1e-12 toleransıyla.
Fiyat yaşı cevabın generated_at zamanından hesaplanır.

Sekiz tablo/görünümün tüm kayıtları önce/sonra parmak iziyle karşılaştırılır.
Değişimde sonuç kararsızdır. Çıkış 0 doğrulandı, 1 uyuşmazlık/durduran hata,
2 kaynak değişti (sakin zamanda yeniden kontrol), 130 Ctrl+C. Yeni çıktı
klasörü gerekir; UTC zaman, commit/worktree_dirty, araç SHA-256'sı, kapsam,
ürün sonuçları/farklı alan yolları ve parmak izleri raporlanır. Şifre, SQL,
ham hata veya özel tur notları çıktıya konmaz; raporlar Git'e gönderilmez.

## ML veri denetimi

Araç, mevcut tools/api_ui_check.py içindeki configured_url/read_dataset
hesap/şema denetimlerini kullanır. Yalnız API_DATABASE_URL ve SELECT hesabı;
her görüntü REPEATABLE READ / READ ONLY, 5 saniye sorgu sınırı ve UTC ile alınır.
Analiz önceki tek görüntüde yapılır; sonunda sekiz nesne yeniden okunup parmak
izleri karşılaştırılır. Devam eden tur varsa başlanmaz; kaynak değişirse
hesaplanan sayılar kesin kabul edilmez. API, internete HTTP, migration,
katalog eşitlemesi veya gerçek DB yazması yoktur.

Toplama ve keşif çalışmıyorken proje kökünde kullanıcı terminalinden:

```powershell
$env:API_DATABASE_URL = "postgresql://fiyat_takip_api@localhost:5432/fiyat_takip"
$mlAuditOut = "artifacts\ml_denetim_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
.venv\Scripts\python.exe tools/ml_data_check.py --output-dir $mlAuditOut
$LASTEXITCODE
```

Şifre pgpass'ten okunur, komuta yazılmaz. API sunucusunu açmak veya yeni tur
başlatmak gerekmez. Araç otomatik zamanlanmaz; eski çıktı klasörü kabul edilmez.

| Çıkış | Anlamı |
|---|---|
| 0 | Denetim doğrulandı; kullanılabilir örnek sayısı sıfır olabilir. ML hazır veya kullanım izni var anlamına gelmez. |
| 1 | Hesap/şema/girdi/DB/çıktı hatası; denetim tamamlanmadı. Ham hata ve bağlantı adresi yazdırılmaz. |
| 2 | Kaynak değişti; sonuç kesin kabul edilmedi. Bu görüntünün ağsız tekrarı da 2 kalır. |
| 130 | Kullanıcı durdurdu; tamamlanmış sonuç değildir. |

Başarılı veya kaynak değişen denetim; snapshot.json, rules.json, report.json,
source_check.json, windows.jsonl, daily.jsonl, report.md ve dosya parmak
izlerini içeren manifest.json üretir. snapshot.json yalnız gereken alanları
taşır; DSN/parola/tur notu/satıcı/ham hata metni içermez. Çıktı yazımı kesilirse
failure.json varsa önceki kısmi dosyalar kesin sonuç sayılmaz. Yerel hash
bütünlük kontrolüdür, kaynağın dijital imzası değildir. Görüntüdeki ilk
hesaplayıcı SHA'sı ve source_check.json içindeki analysis_verifier_sha256
ayrıdır; başka kod sürümüyle tekrar alınırsa hangi hesaplayıcının kullanıldığı bellidir.

Kaydedilmiş görüntünün ağsız tekrarı da kullanıcı terminalinden:

```powershell
.venv\Scripts\python.exe tools/ml_data_check.py --snapshot "$mlAuditOut\snapshot.json" --output-dir "${mlAuditOut}_tekrar"
$LASTEXITCODE
```

Tekrar DB adresini okumaz/bağlanmaz ve görüntünün sabit tarihiyle hesaplar;
aynı hesaplayıcı sürümü ve kurallarıyla
report.json/windows.jsonl/daily.jsonl aynı olmalıdır. source_check.json içindeki
çalışma biçimi farklıdır. Dışarıdan eklenen alanlar, tekrarlı/bozuk kimlikler,
plan–kontrol veya sonuç–fiyat çelişkisi ve bozuk hash reddedilir.

**Günlük kurallar:** kendi verimizde başlangıç fiyatı akşam turunun ürün
minimumu, gelecek sonucu günün iki turunda gözlenen minimumdur. Akşam fiyatı
yoksa sabah fiyatı başlangıca taşınmaz. Her scheduled tur, başlangıcından
önceki en yakın İstanbul 10.00/22.00 dilimine aittir; örneğin ertesi gün
09.00 başlangıcı önceki 22.00 dilimidir. Eksik/tekrarlı dilim, kesilen tur,
günü aşan tamamlanma, ürünün planlanmaması ve eksik/hatalı sayfa cevabı kalite
kusurudur. İki turun ürün sayfa kimlikleri aynı olmalı; başka ürünün değişen
kataloğu etkilemez. Manuel turlar envanterde kalır, örneklere katılmaz.
Cimri günlük fiyatları ayrı kalır; ürün kimliği değişimi pencereyi eler,
tarihsel satıcı kapsamının aynı olduğu varsayılmaz.

Geçmiş d−29…d, gelecek d+1…d+7'dir; d başlangıç günüdür. İlk 30 günde her gün
başlangıç fiyatı ve sonraki yedi günde her gün minimum fiyat gerekir. Kendi
37 günlük kapsamı sabit ve cevapları tam olmalı. Tükendi geçerli kaynak
sonucudur; bütün gün fiyatsızsa doldurulmaz. Sabah fiyatı olan, akşam stoksuz
bir gün gelecek minimumu sağlayabilir; geçmiş başlangıç fiyatını sağlayamaz.
Eksik gelecekte gözlenen düşüş olsa dahi sıkı temel sayımda pencere dışarıda
kalır; olumsuz etiket üretilmez. Tam sayı kuruşla
100×gelecek_minimum ≤ 95×başlangıç ise 1, değilse 0; kullanılamayan etiket NULL.
İçinde bulunduğumuz İstanbul günü elenir. API'nin 18 saat/14 geçiş/7 gün gibi
gösterge eşikleri ML denetimine aktarılmaz.

Rapor ürün/kaynak bazında tur/sonuç sayıları, süre, eksik gün/fiyat aralıkları,
kapsam dönemleri, azami tur boşluğu, aday/elenen/kullanılabilir pencere ve
sınıfları verir. calendar_days takvim uzunluğu, observed_days en az bir
kontrol sonucu/kaydı bulunan nominal gün sayısıdır; boş hazırlanan satır
gözlem sayılmaz. Cimri'de NULL fiyatlı tarih kaydı gözlemdir, fiyat değildir.
Elenme nedenleri birden fazla olabilir; neden sayıları
toplamı elenen pencere sayısına eşit olmak zorunda değildir. Güncel etkin
sayfalar değişmişse bekleme hesabı eski kapsamı sürüyormuş gibi saymaz.
Koşullu ilk pencere sonu ve ertesi gün yapılabilecek denetim tarihi verilir;
bu vaat değildir. Takip sayfası yoksa veya ürün pasifse tarih hesaplanmaz.

Kaynak başına kullanılabilir ortak referans tarihlerinde ilk floor(%70),
sonraki floor(%85)'e kadar doğrulama, kalanı testtir. Bütün ürünler aynı
tarih bölümünü paylaşır. Önceki bölümün hedef sonu sonraki dolu bölümün ilk
referansına eşit/sonraysa purged olarak ayrılır. first_anchor/last_anchor,
ayırmadan önceki bölüm sınırlarıdır; distinct_anchor_days kalan günleri sayar.
Ürün/sınıf/gün sayıları ve
boş/tek sınıflı bölümler belirtilir; model eğitilmez, puan üretilmez.
Çakışmayan 37 günlük pencereler en erken olandan açgözlü seçilir; bunlar da
ürünler arası istatistiksel bağımsızlık kanıtı değildir. numerical_candidate
yalnız bu sayımlarda engel bulunmadığıdır; yayın yeterliliği değildir.
Mevcut Cimri serisinin eski kalması ve ML kullanım belirsizliği ayrıca gösterilir.

## Testler ne kanıtlar, ne kanıtlamaz

- **Otomatik testler:** Kuralların doğru çalıştığını kayıtlı ve sahte
  yanıtlarla kanıtlar. Kimlik değişiklikleri gerçek kaynak örneği ve regresyon
  ister; bazı korumalar (Hepsiburada varyant tutarlılığı, adres kimliği)
  kullanıcının ayrı istisnasıyla, gerçek uyuşmazlık görülmeden önleyici eklendi.
  Sitelerin bugün hâlâ aynı yapıda olduğunu kanıtlamaz. Veritabanı testleri
  şema kurallarının, migration koşucusunun, katalog eşitlemenin ve toplama
  turunun gerçek PostgreSQL'de doğru çalıştığını kanıtlar; tur testleri sahte
  scraper kullanır, turun gerçek sitelerle çalıştığını yalnızca canlı tur
  gösterir.
- **Kasıtlı bozma (mutasyon) denetimi:** Testlerin gerçekten hata
  yakalayabildiğini sınamak için kodun kritik satırları projenin bir kopyasında
  ya da yalnız bellekte (ağ kapalıyken) tek tek bozuldu ve testlerin bozmayı
  yakalayıp yakalamadığına bakıldı (sonuçlar: [arşivdeki plan](arsiv/proje_plani_2026-10-20.md),
  Bölüm 9, Adım 3 ve Adım 6). Yakalanmayanlar bilinçli olarak testsiz bırakılan eşzamanlılık
  korumaları ya da davranışı değiştirmeyen (eşdeğer) bozmalardır.
- **Linux/Windows farkı:** CI Linux'ta çalışır; `pythonw`, Windows kod sayfası
  ve Görev Zamanlayıcı yalnız bu bilgisayarda, canlı turla sınanır. Kataloğun
  LF yazılması testi yalnız Windows'ta anlamlıdır (Linux zaten LF yazar).
- **Canlı kontrol araçları:** Bugünkü site uyumunu aynı üretim koduyla sınar.
  Pazaryerindeki her sayfanın katalogda olduğunu kanıtlamaz.
- "Testler geçti" ile "bütün pazaryeri eksiksiz tarandı" aynı şey değildir.

## Bilinen sınırlar

- **Hepsiburada arama API'si** bizi engelliyor (HTTP 403, kalıcı); Hepsiburada
  taraması her zaman "kısmi" raporlanır. Kapsamı arama/model sayfasının ilk
  sayfası ve ürün sayfalarındaki seçenek listesi taşır; ayrı bir ürün ailesi
  yalnızca kartı görünürse bulunur.
- **iPhone dışındaki markalarda** Hepsiburada model filtresi sayfası bulunamadı;
  genel arama sayfası kullanılır ve yalnız ilk 36 kart görünür. Kalabalık
  aramalarda kapsam eksik kalabilir: Galaxy S25'te 140 sonucun 36'sı
  (`html_partial`), Redmi aramalarında ilk sayfa kılıf ilanlarıyla doluydu.
- **Trendyol reklam kartları** arama sonuçlarının arasına giriyor ve sayfa
  kaydırıyor; sitenin bildirdiği toplamdan 2–3 ürün hiçbir sayfaya düşmüyor
  (`count_mismatch`, ör. iPhone 15'te 116/119). Ölçüldü: bu ürünlere sayfalama
  ile ulaşılamıyor. Aranan modelin kartları ilk sayfada çıktığı ve kardeş
  sayfalar varyant listesinden geldiği için pratik etkisi düşük; kod düzeltmesi
  yapılmadı.
- **Trendyol araması ve varyant listesi** yalnızca satıştaki sayfaları gösterir.
  Stoktan çıkan bir sayfa yeniden keşfedilemez; önceden kataloğa girmişse korunur.
- **Trendyol renk adları** sayfanın renk seçicisinden gelir ve satıcı girdisi
  olduğu için dili karışıktır ("Abis", "Deniz Mavisi" yanında "Silver", "Cosmic
  Orange", "Sage"). Bir sayfada (`trendyol_762254869`) varyant listesi
  olmadığından "Çok Renkli" kaldı. Renk adları platformlar arasında
  birleştirilmez; renk yalnız gösterim bilgisidir, ürün kimliğini etkilemez.
- **4G/5G ayrımı**: `network: "4G"` hedefi, ağ alanı boş sayfaları 4G sayar.
  Başlığında "5G" yazmayan ve özelliği boş bırakılmış bir 5G sayfası 4G
  ürününe girebilir; bugüne kadar görülen bütün 5G sayfalarında başlıkta "5G"
  vardı. 4G ürünün adında "4G" yazmaz ("Xiaomi Redmi Note 14 Pro 256 GB").
- **Garanti ve RAM** ürün kimliğine katılmaz (karar). Satıcıların garanti alanı
  güvenilir değil: yurt dışı sürüm olan `trendyol_991304922` sayfasında bile
  "Apple Türkiye Garantili" yazıyordu. Bu yüzden yurt dışı sürüm, garanti
  alanından değil ürün adından ("International Version", "Global Version",
  "Yurt Dışı") ayırt edilir ve kapsam dışıdır; adında bunu söylemeyen bir yurt
  dışı sürümü ayırt edilemez. Garanti yazısı ve RAM yalnız Trendyol'da keşif
  raporunda bilgi olarak tutulur.
- Keşif, katalogda var olan bağlantının rengini veya ürününü **güncellemez**;
  renk kaynağı gibi bir kural değişirse katalog yeniden kurulur.
- `exclude_terms` ve `network` keşif anında uygulanır; hedefe sonradan
  eklenirse daha önce kataloğa girmiş sayfalar kendiliğinden çıkarılmaz.
- **Bulutta çalıştırma:** GitHub'ın bulut makinelerinden Hepsiburada bilgisayardakiyle
  aynı okundu, ama Trendyol HTTP 403 verdi (6 Ekim, tek örnek). Bilgisayardaki
  turlarda Trendyol hiç engellenmedi. 403 `blocked` sayılır ve engel aşılmaz (vekil
  sunucu, adres döndürme, tarayıcı taklidi yok); bu yüzden toplamanın GitHub'ın
  makinelerine taşınması şimdilik uygun görünmüyor. Karar:
  [proje_plani.md](../proje_plani.md).
- Arka arkaya çok tarama Trendyol'da geçici engele yol açabilir (25 Eylül'de
  yarım saatte 7 tarama sonrası 10 dakika engel). Günlük fiyat toplama bu
  yoğunlukta değildir; keşif seyrek çalışır.
- Fiyat ve stok iki tur arasında değişip geri dönebilir; veritabanındaki geçmiş
  turların anlık görüntüleridir. 28 Eylül'de bir Trendyol sayfası 2 saatte
  Tükendi'den Kritik Stok'a ("Son 1 ürün"), bir Hepsiburada sayfası 71.059
  TL'den 75.524 TL'ye geçti.
- Siteler sayfa yapısını değiştirebilir; bu durumda bakım gerekebilir. Kod,
  değişiklikte sessizce yanlış sonuç üretmek yerine hatayı raporlamaya çalışır.

- **Hepsiburada sayfası başka modele dönebilir:** aynı adres başka bir modelin
  içeriğini gösterebilir (Galaxy S25 sayfalarının S25+ içeriğine dönmesi iki kez
  görüldü). Kimlik kuralı `identity` verir, yanlış fiyat geçmişe girmez; bağlantı
  hedefli kararla pasife alınır veya katalogdan çıkarılır. Kalıcı çıkarılan
  bağlantının ürün bağı `retired_listing_bindings` içinde korunur.
- **`invalid_host` (www3.hepsiburada.com):** bazı Hepsiburada sayfaları ara sıra
  izinli alan adı dışına (`www3.hepsiburada.com/`) gidiyor. Olaylar tek turluk ve
  kendiliğinden geçiyor; yönlendirmenin nedeni doğrulanmadı, izin listesi
  genişletilmedi.
- **Otomatik kabulün renk kuralı:** kabul katmanı sayfadaki bütün renk
  kaynaklarının normalleştirilmiş hâliyle aynı olmasını ister; eş anlam yalnız
  `blue`→`mavi`. "Black" ile "Siyah", "Siyah Titanyum" ile "Siyah" ya da JSON-LD
  renk alanına kapasite yazılması `color_mismatch` üretir. 19 Ekim raporunda
  44 Trendyol sayfası yalnız bu nedenle reddedildi; 41'i katalogda etkin, doğru
  sayfalardır. Mevcut bağlantılar korunur, ama yeni Trendyol renk sayfaları
  otomatik kabul edilemez. Hepsiburada başlık renkleri sınırlı bir listeyle
  (`TITLE_COLORS`) tanınır. Düzeltmesi planlandı ([proje_plani.md](../proje_plani.md)).
- **Kaynak içi çelişkiler:** bazı satıcı sayfalarında başlık ile özellik alanları
  çelişir: Trendyol 797850359 başlıkta 5G/12 GB RAM, özellikte 4G/8 GB RAM;
  Hepsiburada HBCV0000E8DHJL başlık/varyantta 256 GB, ana üründe 512 GB.
  Bunlar yeni aday olarak kabul edilmez; hangi alanın yanlış olduğu bilinmez.
  E8DHJL eski kaydıyla katalogdadır; ona müdahale ayrı hedefli karar ister.
- **Stoksuz Hepsiburada JSON-LD'si:** satılamayan sayfa JSON-LD'de 0,00 TL ve
  `InStock` gösterebilir; bu alanlar fiyat veya stok kanıtı sayılmaz. Tükendi
  kararı satıcı listesinden verilir.
- **Cimri:** kullanım uygunluğu doğrulanmadı ([değerlendirme](#kullanım-değerlendirmesi));
  iki ürünün eşleştirmesi yok. Seri kendi ölçümümüzle aynı kapsamda değildir;
  tarihsel satıcı kapsamı ve günlerin bağımsız ölçülüp ölçülmediği bilinmez.
  Akakçe'nin ilk örneği HTTP 403 verdi; engel aşılmaz.
