# Teknik rehber

Bu belge, [README](../README.md)'de tanıtılan sistemin başvuru rehberidir:
dosyaların görevleri, komutlar, keşif ve fiyat okuma kuralları, veritabanı,
API ve ekran sözleşmeleri, hata kodları ve bilinen sınırlar. Yalnız sistemin
**bugünkü davranışını** anlatır; tarihli oturum kaydı tutmaz.

- Kararlar, aşama durumu ve açık kararlar: [proje_plani.md](../proje_plani.md)
- Teslim kullanıcısı: [teslim.md](teslim.md)
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
- [ML hazırlığı](#ml-hazırlığı)
- [Gölge mod tahmin kaydı](#gölge-mod-tahmin-kaydı-python--m-appml-shadow-predict)
- [Günlük gölge görevi](#günlük-gölge-çalışması-python--m-appml-shadow-daily)
- [Gölge değerlendirmesi](#gölge-değerlendirmesi-python--m-appml-shadow-evaluate)
- [Güvenilirlik grafiği](#güvenilirlik-grafiği-python--m-appml-reliability-chart)
- [Tahmin gösterim onayı](#tahmin-gösterim-onayı-python--m-appml-shadow-display)
- [Gölge işletiminde kontrol komutları](#gölge-işletiminde-kontrol-komutları)
- [Gölge kayıtlarının kontrol sırası](#gölge-kayıtlarının-kontrol-sırası)
- [Tatil dönemi tur kontrolü](#tatil-dönemi-tur-kontrolü)
- [Docker: imaj ve Compose temeli](#docker-imaj-ve-compose-temeli)
- [Docker: paket ve veritabanı aktarımı](#docker-paket-ve-veritabanı-aktarımı)
- [Docker: tek komutla kullanım ve kabul](#docker-tek-komutla-kullanım)
- [Docker kabul senaryoları](#docker-kabul-senaryoları)
- [Docker servis bağlantısı ve gösterim bakımı](#docker-servis-bağlantısı-ve-gösterim-bakımı)
- [Haftalık yedek](#haftalık-yedek)
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
| `docs/teslim.md` | Teslim kullanıcısının ilk kurulum, günlük kullanım, veri yenileme ve geri dönüş rehberi. |
| `DEVAM.md`, `ARAC_GECISI.md`, `CLAUDE.md` | Yerel devir notu, araç geçişi rehberi ve ortak kuralları içe alan Claude sarmalayıcısı; Git dışıdır. |
| `docs/arastirma/` | Karar öncesi araştırma girdileri; güncel uygulama talimatı değildir. |
| `docs/gecmis.md` | Her plan adımı için kısa geçmiş satırı (tarih, ne yapıldı, commit, CI). |
| `docs/arsiv/` | 20 Ekim 2026'da dondurulmuş eski plan ve rehber, Aşama 7 araştırma raporları. Değiştirilmez. |
| `pyproject.toml` | Bağımlılıklar, Python sürümü, paketleme ve test/biçim araçlarının ayarları. |
| `Dockerfile`, `.dockerignore` | Sabit Linux tabanı, hash'li paket kurulumu ve ayrı kullanıcı; imaja yalnız gerekli uygulama kaynaklarının alınması. |
| `compose.yaml` | Ayrı teslim kopyası için DB/API/ekran servisleri, ağ, kalıcı alanlar ve gizli dosya bağlantıları. Veri hazırlamaz. |
| `requirements-linux.lock` | Python 3.13.15 / Linux x86_64 için doğrudan ve dolaylı çalışma bağımlılıklarının sürüm ve wheel hash'leri. Windows'a kurulmaz. |
| `app/delivery/` | Tutarlı salt okunur yedek, kapalı paket envanteri ve Docker kopyasının hazırlık/doğrulama komutları. |
| `scripts/teslim.ps1` | Docker tesliminin Export, Prepare, Start, Status, Logs, Stop ve Rollback girişi. |
| `scripts/teslim_ortak.ps1` | Sabit yerel motor, seçim/kilit, Compose çağrısı, sağlık ve geri dönüş işlemleri. |
| `scripts/teslim_paket.ps1` | Paket/imaj doğrulama, ayrı kopyaya geri yükleme ve hazırlık kaydı. |
| `scripts/teslim_hazirla.ps1` | Eski hazırlama komutunu aynı Prepare girişine yönlendiren uyumluluk dosyası. |

Eski veritabanı, API, ML, arayüz ve Docker taslakları yerel
`_eski_taslaklar/` klasöründedir. Git’e gönderilmez, güncel uygulamanın
parçası değildir ve bugünkü kodla çalışmazlar; yalnız örnek olarak korunur.

### Ayarlar: `config/` (kod değil, veri)

| Dosya | Ne işe yarar | Kim yazar |
|---|---|---|
| `discovery.json` | Takip edilecek telefonlar ve tarama sınırları | Kullanıcı |
| `catalog.json` | Keşfin doğruladığı ürünler ve sayfalar | Keşif (elle yazılmaz) |
| `runtime.json` | Zaman aşımı, tekrar deneme, istekler arası bekleme (3 sn) | Kullanıcı, nadiren |
| `market_history.json` | Bir defalık Cimri alımı: `product_key`, URL ve beklenen Cimri kimliği. Güncel eşleştirme kapsamı README tablosunda; sözleşme [eşleştirme bölümündedir](#eşleştirme-dosyası). | Araştırma ve gerçek çıktı kontrolüyle |
| `shadow.json` | Gölge mod: başlangıç günü (27 Ekim 2026), dondurulan modelin ön kayıtlı manifest SHA-256'sı, model ve 2 Kasım kanıtlarının kalıcı kopya yolları (`data/ml/golge/kanitlar/`, Git dışı) ve resmi kayıt klasörü (`data/ml/golge`). Ayrıntı: [Gölge mod tahmin kaydı](#gölge-mod-tahmin-kaydı-python--m-appml-shadow-predict). | Kullanıcı, nadiren; model değişmez |

### Ortak parçalar: `app/`

| Dosya | Ne işe yarar |
|---|---|
| `contracts.py` | Verinin şekilleri ve doğrulaması (Pydantic V2 strict): `Product`, `Listing`, `Catalog`, `PriceObservation`, keşif hedefleri ve raporu. Hatalı veri içeri giremez (ör. fiyat alanına "Tükendi"). Yalnızca biten aşamanın kullandığı tanımları içerir. |
| `settings.py` | Ayar dosyalarını okur. `CATALOG_PATH`, `DISCOVERY_PATH`, `RUNTIME_PATH`, `SCRAPE_LOCK_PATH`, `LOG_DIR`, `DISCOVERY_REPORT_DIR` ortam değişkenleriyle başka dosya veya klasör gösterilebilir. |
| `scrape_lock.py` | Siteye giden bütün girişlerin paylaştığı kilit (`data/scrape.lock`). Fiyat turu, keşif, Cimri yerel alımı/ağsız aktarımı ve iki canlı kontrol aracı (`live_scraper_check`, `live_discovery_check`) alır; biri sürerken diğeri beklemeden "sürüyor" deyip çıkar. Süreç çökse bile işletim sistemi kilidi bırakır. |
| `console.py` | Komut satırı araçlarının ortak çıktı yardımcıları: UTF-8 çıktı (`utf8_output`; fiyat turu, keşif, `app.database`, `app.ml` ve canlı kontrol araçları kullanır), `<ön ek>_<tarih-saat>.log` dosyası açma, stdout/stderr'i log dosyasına da yazan `tee_output` ve ikisini birleştiren `run_logged` (zamanlanmış tur/keşif ile elle veya zamanlanmış günlük gölge çalışması: log açılamazsa iş başlamaz ve 1 döner; başlık satırı, beklenmeyen hatanın ayrıntısı ve "Çıkış kodu" satırı log'a yazılır). pythonw.exe altında ekran akışları yoktur (`None`); hepsi buna dayanır. |
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
| `connection.py` | PostgreSQL bağlantısı. Adres `DATABASE_URL` ortam değişkeninden okunur (şifresiz); `database_url(API_DATABASE_URL_ENV)` okuma hesabının adresini (`API_DATABASE_URL`) verir. Şifre PostgreSQL'in `pgpass.conf` dosyasındadır. Oturum saati UTC; bağlanma 10 sn, tablo kilidi bekleme 30 sn ile sınırlı (yarım bırakılmış bir işlem turu sonsuza kadar bekletmez, hata verir). |
| `migrate.py` | Migration koşucusu: `migrations/` altındaki numaralı SQL dosyalarını sırayla, her birini tek transaction'da ve yalnızca bir kez uygular; `schema_migrations` tablosuna parmak iziyle yazar. |
| `migrations/001_initial.sql` | Katalog kopyası, toplama turları ve sayfa sonuçları tabloları; bütün kurallar (`CHECK`, `UNIQUE`, yabancı anahtarlar). |
| `migrations/002_guards_and_comparability.sql` | İki yeni `CHECK` (Tükendi satırı fiyat taşımaz, çizili fiyat güncel fiyattan büyüktür), beş tabloda 15 tetikleyici (silmeyi ve `TRUNCATE`'i reddeder, kimlik alanlarını korur, yazılmış sayfa sonucunu dondurur), `product_run_prices` görünümü. |
| `migrations/003_closed_run_guards.sql` | İki tetikleyici işlevini yeniler: kapanmış turun sonuçsuz satırına yazımı ve kapanmış turun durum/bitiş zamanı değişimini reddeder; ilk sonuç ve `network` yeniden yazımını tur kapanışıyla sıraya alır. Veri satırlarını ve görünümü değiştirmez. |
| `migrations/004_market_history.sql` | Ayrı Cimri geçmişi tablosu; ürün/kaynak/gün tekilliği, pozitif kuruş/NULL ve ilk kaydın güncelleme/silme korumaları. |
| `migrations/005_listing_offer_url.sql` | Seçilen teklifin ölçüm anındaki satıcı bağlantısı; yalnız `offer` sonucunda dolabilir, eski kayıtlar `NULL` kalır. |
| `market_history.py` | Ağsız aktarımın SQL işlemleri: kimlik ön kontrolü, salt okunur önizleme, ürün başına transaction, tekrar/çelişki koruması ve tur kilidi. |
| `catalog_sync.py` | `catalog.json`'u veritabanındaki kopyaya eşitler: `plan_sync` farkı veritabanına dokunmadan hesaplar, `sync_catalog` tek transaction'da yazar. |
| `runs.py` | Tur SQL'leri: veritabanı tur kilidi, yarım kalan turu kapatma, turu ve planlanan sayfaları açma, sayfa sonucunu (bir kez, yalnızca süren tura) yazma, süren turdaki `network` hatası satırını ikinci okumanın sonucuyla değiştirme (`rewrite_network_result`, tek istisna), turu kapatma, özet. |
| `read.py` | API'nin kullanacağı salt okunur veri katmanı: etkin ürünler, global tur durumu, ürüne özel son tamamlanmış tur, teklifler ve ayrı kendi/Cimri geçmişi. Hazır bağlantıda tek REPEATABLE READ, READ ONLY işlem; bağlantı/havuz açmaz, kilit almaz, veri yazmaz. |
| `ml_data.py` | ML veri görüntüsünün okuması: ürün, platform, sayfa, tur, sayfa sonucu ve Cimri satırlarının yalnız ML'in kullandığı alanları, `read.py` ile aynı tek REPEATABLE READ, READ ONLY işlemde. Hesabın varsayılanı salt okunur değilse, bekleyen migration varsa veya bir tur sürüyorsa okumaz ([ML hazırlığı](#ml-hazırlığı)). |
| `__main__.py` | Komut satırı: `python -m app.database migrate` / `status` / `sync-catalog [--dry-run]`. Çıkış kodları: `0` başarılı; `1` komut başarısız (şema, katalog çakışması, bağlantı, ayar; mesaj stderr'e `Veritabanı komutu başarısız: …` diye yazılır); `2` argüman hatası. |

### Fiyat toplama turu: `app/collection/`

| Dosya | Ne işe yarar |
|---|---|
| `service.py` | Bir tur: şema kontrolü, yarım kalan turu kapatma, katalog eşitleme, planlama, her sayfayı mevcut scraper'la okuyup sonucunu hemen yazma, `network` hatası alan sayfaları tur sonunda bir kez yeniden okuma, turu kapatma. Scraper ile veritabanını bağlayan tek yer. |
| `__main__.py` | Komut satırı: `python -m app.collection [--prefix ÖN_EK] [--scheduled]`; ortak kilidi alır. `--scheduled` ile çıktı `data/logs/` altındaki log dosyasına da yazılır. |

### Yerel API: `app/api/`

| Dosya | Ne işe yarar |
|---|---|
| `main.py` | `create_app()` fabrikası, lifespan ile havuz açma/kapatma, beş GET adresi, cevap doğrulaması ve Türkçe güvenli hata cevapları. İçe aktarmada bağlantı açmaz. |
| `database.py` | Yalnız `API_DATABASE_URL` ile 1–4 bağlantılık Psycopg havuzu; her istekte rol, SELECT/yazma izinleri, nesneler ve migration durumunun salt okunur denetimi. |
| `schemas.py` | API ve istemcinin ortak, ağsız cevap modelleri. DB/havuz/hesaplama/FastAPI yüklemez; JSON alanları ve OpenAPI aynı kalır. |
| `models.py` | Tek `ProductSnapshot` içinden istatistik ve fiyat yaşıyla ortak cevaba dönüşüm. İç `all_history`, ham sayfa hata metni ve tur notu dışarı verilmez. |

### Yerel istemci ve ekran: `app/ui/`

| Dosya | Ne işe yarar |
|---|---|
| `api_client.py` | `ApiClient`: beş sabit yerel GET, katı girdi/JSON/hedef doğrulaması; proxy/yönlendirme/tekrar/önbellek yok, açık zaman aşımı ve güvenli Türkçe hatalar. UI veritabanı/sunucu uygulamasını yüklemez. |
| `main.py` | Kartlı Streamlit ekranı: telefon/aralık seçimi, güncel sonuç, tek tahmin kartı, API istatistikleri, iki grafik ve 30 sn/elle yenileme. Tahmin hatası yalnız kendi kartında kalır; fiyat hatasında eski veriler kaldırılır. Yalnız seçim tercihleri korunur. |
| `presentation.py` | Tamsayı kuruş, bir ondalıklı olasılık yüzdesi ve İstanbul saati biçimleme, Türkçe gerekçeler, açık boşluk/kapsam sınırlarına sahip Altair çizgi/nokta verisi. İstatistik hesaplamaz veya veri kaynağına bağlanmaz. |

### ML hazırlığı: `app/ml/`

| Dosya | Ne işe yarar |
|---|---|
| `dataset.py` | Veri görüntüsünün sözleşmesi (Pydantic V2 strict) ve dosyası: satırları anahtar sırasına dizer, kayıtlar arası bağları denetler, `snapshot.json`'u SHA-256 parmak iziyle yeni klasöre yazar, okurken parmak izini ve içeriği yeniden denetler. Veritabanı, ağ ve pazaryeri katmanı yüklemez. |
| `series.py` | İstanbul günleri, zamanlanmış tur dilimleri, sağlam akşam başlangıcı, günlük minimum ve Cimri yarım gün maskesi; eski sıkı karşılaştırmanın günlük serisi. |
| `labels.py` | Ayrı kendi/Cimri serilerinden simetrik 6/7 etiketi, sabit/izlenen sayfa kapsamı, sıkı pencere ve etiket özeti. Model eğitmez ve zaman bölmesi yapmaz. |
| `features.py` | Yalnız geçmiş günlük başlangıç fiyatlarından sabit sözleşmeli girdiler, aile/segment kategorileri ve eksiklik raporu. Etiket okumaz; öğrenilen dönüşüm veya model eğitimi yapmaz. |
| `splitting.py` | Parmak izli etiket/girdi eşleşmesi, ortak %70/%15/%15 tarih bölmesi, purge, ayrı kalibrasyonlu dört ileri yürüyen kat; katların etiket/girdi satırlarını ve saklı test dışındaki değerlendirme hedeflerini sınır denetimiyle seçer. Aynı dilim kuralıyla son modelin eğitim/kalibrasyon satırlarını (`final_samples`) verir; saklı test satırları yalnız ayrı `reserved_test_samples` girişindedir. |
| `metrics.py` | Anahtarlı tahminlerde AP/Brier/log loss/Brier skill, güvenilirlik kovaları, olumlu pencere kümeleri, kırılımlar/makro ve eşleştirilmiş tarih bloklu güven aralığı. İstatistik kütüphaneleri yalnız puanlama çağrısında yüklenir. Doğrulama işlevleri saklı testi reddeder; saklı testi yalnız `score_reserved_test` ve `reserved_test_bootstrap` puanlar. |
| `models.py` | R0 sabit oran, R1 dip kuralı, R2 lojistik regresyon ve LightGBM; yalnız eğitimden öğrenilen ön işlemler, ayrı dilimde Platt kalibrasyonu, ham/kalibre tahminler ve öğrenilen değerlerin özeti. Dondurulan model (`FrozenModel`: R0 + seçilen model) ve özeti. |
| `experiment.py` | Etiket/girdiden bölmeyi yeniden üretip kanıt dosyalarıyla karşılaştırır; hazır katlarda eğitim/kalibrasyon/doğrulama akışını, birleşik ölçütleri, güven aralıklarını ve seçim önerisini yürütür. Saklı test ve kendi serimiz puanlanmaz. |
| `final.py` | Deneyin seçim sonucundan modeli türetir, son dilimlerle dondurur, dondurulan modeli yalnız denetimlerden sonra yükler ve saklı testi bir kez puanlar. |
| `shadow_records.py` | Ortak ayar, gerekçe, satır/manifest/parmak izi ve tekillik doğrulamaları. NumPy/scikit-learn yüklemez; eski gölge komutları bu işlevleri aynı adlarla kullanır. |
| `shadow_display.py` | Ayrı gösterim onayını atomik yazar/kapatır; kayıt ve kaynak görüntüden güncel tahmini salt okunur hazırlar. API yolu model/puanlama kütüphanelerini yüklemez. |
| `shadow.py` | Gölge mod: ön kayıtlı SHA-256'sı ve kanıt zinciri doğrulanmış dondurulan modeli açar, veri görüntüsünden kendi serimizin girdilerini bellekte hesaplar, kayıtsız her (ürün, gün) için olasılık ve gerekçe üretir, değişmeyen tahmin klasörünü yazar/yeniden doğrular ve resmi kayıtlardaki anahtarları çıkarır. Veritabanı, ağ ve pazaryeri katmanı yüklemez. |
| `daily.py` | Günlük gölge akışı: kısa ortak tarama kilidi altında salt okunur görüntü, sınırlı tur/DB bekleme ve ardından mevcut gölge tahmin komutu; her çalışmada tarihli log. Kayıtlı ürün-günleri yeniden yazmaz. |
| `shadow_evaluation.py` | Kayıtlı olasılıkları yeni görüntünün gerçek sonuçlarıyla eşleştirir; kayıt girdilerini yeniden hesaplayıp doğrular, puan/kapı/sağlık raporunu yeni klasöre yazar ve yeniden okur. DB/ağ, pickle, eğitim veya yeni tahmin kullanmaz. |
| `reliability.py` | Manifestle doğrulanmış saklı test veya gölge değerlendirme raporunun kalibrasyon kovalarından güvenilirlik diyagramı (SVG) çizer; yazılan dosyayı yeniden okuyup her kovayı raporla karşılaştırır. Yeni ölçüm hesaplamaz; numpy/scikit-learn, DB ve ağ katmanı yüklemez. |
| `reporting.py` | Etiket, girdi, bölme, deney, dondurulan model ve saklı test için belirlenimci JSON/JSONL, Türkçe Markdown ve en son yazılan parmak izli başarı manifesti; çıktıların yeniden doğrulanması. `split_plan_files` bölme yazımıyla deneyin bayt karşılaştırmasına ortak dosya içeriği üretir. |
| `__main__.py` | `snapshot` yalnız `API_DATABASE_URL` okuma hesabıyla görüntü alır; `labels`/`features` görüntüden, `split` etiket/girdiden, `experiment` etiket/girdi/bölme klasörlerinden, `freeze` ve `final-test` ayrıca deney/model klasöründen çalışır. `shadow-predict` görüntü ve model/kanıt klasörlerinden tahmin üretir; `shadow-evaluate` kayıtları yeni görüntüyle değerlendirir; `shadow-display` kesin rapora bağlı ayrı gösterim onayını yönetir; `reliability-chart` saklı test veya gölge değerlendirme raporundan grafik çizer. Dosyadan çalışan bu komutlar DB katmanını yüklemez. `shadow-daily` görüntü + tahmin akışını ve loglamayı yürütür; yalnız görüntü aşaması okuma bağlantısı kullanır. Çıkış kodları ilgili [ML hazırlığı](#ml-hazırlığı) alt bölümündedir. |

### Kurulum ve zamanlayıcı: `scripts/`

| Dosya | Ne işe yarar |
|---|---|
| `zamanlayici_kur.ps1` | Fiyat toplama turunu Windows Görev Zamanlayıcı'ya kurar (her gün 10:00 ve 22:00, penceresiz); `-Kaldir` ile siler. Ayarları [Zamanlanmış tur](#zamanlanmış-tur-görev-zamanlayıcı) bölümündedir. |
| `kesif_zamanlayici_kur.ps1` | Haftalık keşfi Görev Zamanlayıcı'ya kurar (her Pazar 14:00, penceresiz, kaçan çalışmayı telafi etmez). Seçeneksiz kurulum önizleme (`--dry-run`), `-OtomatikKabul` otomatik kabul (`--auto-accept`) modunu kurar; `-Kaldir` siler. Ayarları [Zamanlanmış keşif](#zamanlanmış-keşif-görev-zamanlayıcı) bölümündedir. |
| `golge_zamanlayici_kur.ps1` | Günlük gölge tahmin görevini kurar (11:00, penceresiz, uygun oturumda kaçan tetiklemeyi telafi eder); kullanıcı ortamında `API_DATABASE_URL` ister. `-Kaldir` ile siler. Ayarları [günlük gölge çalışması](#günlük-gölge-çalışması-python--m-appml-shadow-daily) bölümündedir. |
| `api_okuma_rolu.sql` | Yönetici hesabıyla çalıştırılan, tek işlemde rol/SELECT izinlerini hazırlayan ortam kurulumu. Yeni tablo veya migration oluşturmaz; fiyat/katalog satırlarını değiştirmez. Üretimde `fiyat_takip_api`, `_test` DB'de `fiyat_takip_api_test`; mevcut ayrıcalıklı/üye/sahip veya yazma yetkili rolü reddeder. |

### Testler ve CI

Son doğrulanmış test sayısı [README Güncel kapsam](../README.md#-güncel-kapsam)
tablosunda tarihle tutulur. Her yeni koşunun geçme/atlama bilgisi ayrıca
çıktısından doğrulanır.

| Yer | Ne sınar |
|---|---|
| `tests/conftest.py` | Her testte gerçek curl_cffi ve HTTPX ağ transport'ları kesilir; ASGI/TestClient/MockTransport süreç içinde çalışır. Kalıcı `DATABASE_URL` ve `API_DATABASE_URL` silinir. `db` yalnız `TEST_DATABASE_URL`'deki `_test` DB'yi her testte boşaltır; ortak test kilidi en çok 30 sn bekler. `api_db` ayrıca `TEST_API_DATABASE_URL` ve `fiyat_takip_api_test` ister; iki bağlantının aynı `_test` DB olduğunu denetleyip test şemasında SELECT izinlerini yeniden kurar. `migrated`, `db`'ye bütün migration'ları uygular. `world`, `client` ve `stub` fixture'ları `tests/support/read_world.py` ile `tests/support/api.py`'dedir; burada `pytest_plugins` ile kaydedildikleri için testler onları içe aktarmadan kullanır. Eksik test adresleri yerelde atlama, CI'da hata üretir. |
| `tests/support/` | Doğrudan pytest ile toplanan test modülleri değildir; ortak fixture ve Docker kabul yardımcılarıdır: sahte HTTP oturumu ve yanıtı (`fake_http.py`), `_test` DB'ye satır yazan `insert` (`database.py`), toplama turunun küçük sahte kataloğu ve sahte scraper'ları (`collection.py`), Cimri kayıtlı örnekleri ve sahte istemcisi (`market_history.py`), salt okunur sorgu ve API testlerinin küçük veritabanı dünyası ve satır ekleme yardımcıları (`read_world.py`), ML veri görüntüsünün küçük tablo örneği ve etiket, girdi, bölme, deney ile dondurulmuş model kanıtını üreten yardımcılar (`ml.py`), yerel API'nin sahte havuzu ve TestClient fixture'ları (`api.py`), istatistik testlerinin sentetik tur ve Cimri geçmişi (`price_statistics.py`), keşif testlerinin örnek dosyası okuyucusu, sabit katalog kopyası ve hedefleri (`discovery.py`), Streamlit ekranının yapay örnekleri, ekran yazılarını toplayan `messages` ve AppTest süre sınırı (`ui_samples.py`, 30 sn; varsayılan 3 sn yavaş makinede doğru ekranı da düşürebilir). Test dosyaları birbirinden içe aktarma yapmaz (`from test_…`, `import test_…`, `from tests.test_…`); bunu `tests/test_http.py` denetler. Yalnız tek dosyada kullanılan yardımcı o dosyada kalır. Buradaki `assert`'ler de pytest'in ayrıntılı hata mesajını verir (`conftest.py`'deki kayıt). |
| `tests/test_http.py` | HTTP katmanı: hata kodları (`invalid_host` mesajı hedef alan adını yazar, sorgu metnini yazmaz), indirme sırasında 8 MB sınırı, büyük hata/yönlendirme yanıtları, yönlendirme kuralları, 5xx tekrarı ve bekleme süreleri, istekler arası bekleme, scraper factory. Mimari sınır da burada: pazaryeri HTTP'si yalnız `app/scraper/http.py` ve curl_cffi ile; HTTPX yalnız `app/ui/api_client.py` için; UI veritabanı/havuz/sunucu katmanını yüklemez; test ve araç dosyaları başka bir test dosyasından içe aktarma yapmaz. |
| `tests/test_contracts.py` | Pydantic sözleşmeleri: satılabilir teklif fiyat ve satıcı taşır, puan ölçeği aşamaz, üstü çizili fiyat güncel fiyattan büyüktür, katalog kimlik/referans/alan adı kuralları, `money()` kuruş çevirimi. |
| `tests/test_url_identity.py` | Ortak ürün adresi kimliği: ürün yolu, sorgu, son eğik çizgi, küçük harfli SKU, eksik/bozuk kimlik ve bütün tüketicilerin aynı kimliği okuması. |
| `tests/test_trendyol_scraper.py`, `tests/test_hepsiburada_scraper.py` | Fiyat okuma: seçilen teklif, eşit fiyatta satıcı adı, çizili fiyat, Kritik Stok, Tükendi'nin yalnız açık sinyalle verilmesi, bozuk satıcı kayıtlarının reddi, ret nedenleri, `parse` dönüşümü. Sahte sayfa ve istemci; internete çıkmaz. |
| `tests/test_discovery_identity.py` | Keşif hedefi ve keşifle scraper'ın ortak kimlik kuralları: model/kapasite eşleşmesi, `exclude_terms`, aksesuar adları, ağ türü, yurt dışı sürüm, telefon kategorisi, Yenilio kenar durumları. Siteye ve keşif sınıfına gitmez. |
| `tests/test_discovery_trendyol.py` | Trendyol keşif adaptörü: arama imleci ve sayfalama, sayfa sınırları, varyantlar, renk seçici, filtre yedekleri, uyarı türleri ve izler; kayıtlı gerçek örneklerle ağ, Yenilio kapsamı ve adres kimliği. |
| `tests/test_discovery_hepsiburada.py` | Hepsiburada keşif adaptörü: API engellenince HTML kartları, arama API'sinde sayfalama ve tekrar, varyant kimliği ve çelişkisi, kanonik adres/SKU kuralı, ağ özelliği, sayfa sınırları. |
| `tests/test_discovery_catalog.py` | Katalog birleştirme ve rapor içeriği (siteye ve dosyaya gitmeden): kimliklerin korunması ve sıradan bağımsızlığı, `catalog_conflict`, aramada görünmeyen bağlantıların korunması, rapor özeti, renk kapsamı. |
| `tests/test_discovery_run.py` | Keşfin çalıştırılması: rapor ve katalog yazma, dry-run'ın kataloğa yazmaması, LF satır sonu, BOM'lu ayar dosyaları, eklenti yükleyici, gerçek `config/*.json` dosyalarının sözleşmeye uyması, UTF-8 çıktı, çıkış kodları, zamanlanmış keşif ve `--apply-report`. |
| `tests/test_discovery_acceptance.py` | Otomatik güvenli kabul: gerçek kaynak örnekleriyle doğrulandı/uyuşmazlık/kanıt yetersiz kararı, rapor ve katalog yazma koruması, kesinti sonrası uzlaştırma. |
| `tests/test_collection.py` | Toplama turu: sahte scraper'larla her sonuç türü, Ctrl+C, tur ortasında veritabanı hatası, yarım kalan tur, kilitlerin bırakılması, pasif sayfa/ürün/platform, ön ek, çıkış kodları, zamanlanmış turun logu, kapanış sonrası hatalar ve tur sonu ikinci okuma. |
| `tests/test_catalog_sync.py` | Katalog eşitleme: kararlar veritabanısız; yazma, deneme, çakışma ve komut satırı veritabanında. |
| `tests/test_database.py` | Migration koşucusu, şemanın bütün `CHECK`/`UNIQUE`/yabancı anahtar kuralları, 002 ve 003 tetikleyicileri, kodun gerçek güncellemelerinin geçmesi, "bilerek silme" yolu ve testlerin emniyet kemerleri. |
| `tests/test_comparability.py` | `product_run_prices` görünümü: aynı sayfa kümesi, hataya giriş/çıkış, yeni sayfa, Tükendi, `--prefix` turu, süren/yarıda kalan turlar, uzun boşluk. |
| `tests/test_database_read.py` | Salt okunur sorgular ve istatistiklerle bütünleşme: ürüne özel tamamlanmış tur, kısmi kapsam, ayrı Cimri/NULL, iki bağlantıyla tutarlı görüntü, sorgu hatası/zaman aşımı sonrası yeniden okuma. |
| `tests/test_ml_dataset.py` | ML veri görüntüsü (veritabanısız): yazma/okuma gidiş-dönüşü, satır sırasından bağımsız aynı baytlar, var olan klasöre yazmama, değiştirilmiş veya bozuk dosyanın ve parmak izi yenilenmiş tutarsız içeriğin reddi, kayıtlar arası bağ kuralları; `app/ml` modüllerinin (komut dosyası dışında) veritabanı, ağ ve pazaryeri katmanı yüklememesi. |
| `tests/test_ml_data.py` | Görüntünün `_test` DB'den okuma hesabıyla okunması (alanlar, sıra, işlemin kapanması); süren tur, bekleyen migration ve yazan hesap reddi; `python -m app.ml snapshot` çıktısı ve çıkış kodları. |
| `tests/test_ml_labels.py` | 30 günlük geçmiş, simetrik 6/7 gelecek, kuruşla %5 sınırı, sağlam akşam başlangıcı, tek tur, gün aşımı, değişen sayfa kapsamı, Cimri kimliği ve yarım gün kuralları. |
| `tests/test_ml_label_cli.py` | Ağsız etiket komutu, aynı dosyaların tekrar üretimi, parmak izi ve kesinti koruması, eski hesaplayıcıyla bağımsız sıkı çapraz kontrol. |
| `tests/test_ml_features.py` | Girdi formülleri ve eksikler, aile/segment, Cimri kimliği, ölçekten bağımsızlık; gelecek fiyat/stok/sayfa/ürün değişimlerine ve kayıtların kesilmesine karşı geçmiş girdilerin sabitliği; 4.2 başlangıç anahtarlarıyla eşleşme. |
| `tests/test_ml_feature_cli.py` | Ağsız, etiket ve eğitim modüllerini yüklemeyen features komutu; aynı dosyaların tekrarı, tipli şema, parmak izi, mevcut klasör ve kesinti/yazma hatası koruması. |
| `tests/test_ml_splitting.py` | Ortak tarih kesimleri, purge eşitliği, ayrı kalibrasyon, dört aylık katlar, boş/tek sınıflı bölüm, kendi kaynağının ayrılığı ve saklı test değişimlerine karşı geliştirme çıktısının sabitliği; kat girdilerinin eşleşmesi ve bozuk üyeliklerin reddi; son modelin dilimleri, yabancı rollü satırın reddi ve saklı testin ayrı giriş noktası. |
| `tests/test_ml_metrics.py` | Elle hesaplanan ölçütler, geçersiz anahtar/etiket/olasılık, uç değerler ve kovalar, küme/makro desteği, bütün ürün günlerini koruyan tekrar üretilebilir eşleştirilmiş bootstrap; saklı test girişlerinin doğrulama puanlamasıyla aynı sayıları vermesi ve karışık/boş hedefi tahminler okunmadan reddetmesi. |
| `tests/test_ml_split_cli.py` | Etiket/girdi bütünlüğü ve başlangıç eşleşmesi, yanlış kurallar/hedef sonu, belirlenimci bölme kanıtı, saklı test bilgi/üyelik koruması ve DB/ağ/eğitim katmanı yüklememe. |
| `tests/test_ml_models.py` | R0/R1 elle hesap kontrolü, çekirdek girdi sözleşmesi, eksikler ve yeni kategoriler, tekrar üretilebilirlik, eğitim/kalibrasyon ayrılığı, Platt dönüşümü, sabit ayarlar ve öğrenilen değerlerin özeti. Yapay veriyle, ağsız. |
| `tests/test_ml_experiment.py` | Kat ve birleşik ölçütler, seçim sonucunun üç durumu; saklı test/kendi kaynak/etiketsiz satırların X/y değişimlerine karşı çıktı baytlarının sabitliği ve eğitim değişiminin çıktıyı değiştirdiği olumlu kontrol. |
| `tests/test_ml_experiment_cli.py` | Deney kanıt zinciri, parmak izi yenilense de değiştirilmiş bölmenin reddi, aynı dosyaların tekrarı, doğrulama dışı/saklı test tahmininin reddi, yarım yazım ve mevcut klasör koruması, çıkış kodları, DB/ağ katmanı yüklememe. |
| `tests/test_ml_final.py` | Seçimden modelin türetilmesi, son dilimlerin ve katlarla aynı yöntemin kanıtı; saklı test etiket/girdisinin dondurmayı değiştirmemesi ve kalibrasyon etiketinin değiştirdiği olumlu kontrol; model yüklemede SHA, parmak izi, sürüm, çelişkili manifest ve yeniden üretim denetimleri (pickle açılmadan reddedilir); saklı test puanlarının bağımsız yeniden hesabı, okuma koşullarının üç durumu ve çıktı doğrulayıcısı. |
| `tests/test_ml_final_cli.py` | `freeze` ve `final-test` komutları: tam çalışma, aynı baytlar, var olan klasör, kesinti, yanlış SHA/değişmiş model/başka girdi (saklı test satırlarına gelinmeden çıkış 1), zorunlu SHA, DB/ağ katmanı yüklememe ve dondurmanın saklı test girişlerini çağırmaması. |
| `tests/test_ml_shadow.py` | Gölge tahmin kaydı (yapay veri): satırların `features` komutuyla aynı girdiler olması, olasılıkların dondurulan modelin çıktısı olması, 30 günden kısa geçmişe olasılık verilmemesi, gelecek verinin önceki tahmini değiştirmemesi (olumlu kontrolle), eksik gün eşiği, eğitimde olmayan aile, `recorded_after_days`; yazılan kaydın yeniden okunması, aynı baytlar, kayıtlı günün yeniden tahmin edilmemesi, manifestsiz klasörün kayıt sayılmaması, bozuk/yabancı/yinelenen kaydın hata vermesi, parmak izi yenilenmiş tutarsız satırların reddi, yanlış SHA'da pickle'ın açılmaması ve gerçek `config/shadow.json`'ın geçerliliği. |
| `tests/test_ml_shadow_cli.py` | `shadow-predict` komutu: deneme/resmi kayıt ayrımı, aynı günlerin ikinci kez yazılmaması (`--records-dir` dahil), var olan klasör, eksik/fazla alanlı ayar, yanlış SHA, eksik görüntü, kesinti sonrası manifestsiz klasör ve DB/ağ katmanı yüklememe. |
| `tests/test_ml_shadow_daily.py` | Günlük görüntü + gerçek tahmin akışı, tekrar çalışmada kayıtların değişmemesi, tur/keşif ve DB `running` kaydı için 5 dakika / 90 dakika bekleme, kayıt kilidi çakışması, eksik/hatalı kanıt ve adres, penceresiz log, çıkış kodları, gerçek `_test` okuma rolü ve yazan hesabın reddi; görev betiğinin BOM ve çalışma sözleşmesi. |
| `tests/test_ml_shadow_evaluation.py` | Kaydedilmiş olasılıktan puan, yeni görüntüde girdi eşleşmesi, geleceğin etiketi değiştirip eski girdiyi değiştirmemesi ve geçmiş değişiminin reddi, yeni sayfanın yalnız y_izlenen etkisi; NULL/kısa geçmiş/showable ayrımı, kapı eşikleri ve takvim sayımı, yarım/bozuk/yinelenen kayıt, kısa kilit, değişmez/aynı bayt çıktısı ve rapor doğrulaması. |
| `tests/test_ml_shadow_evaluation_cli.py` | Gerçek komut akışı ve çıkış kodları, hatalı SHA/ayar/görüntü, mevcut çıktı koruması, kilit ve kesinti, boş kayıtta yetersiz rapor; DB/ağ bağlantısı, pickle açma, eğitim ve tahmin çağrılarının ayrı süreçte engellenmesi. |
| `tests/test_ml_reliability.py` | `reliability-chart` (yapay raporlar): her dolu kovanın değer, konum ve destek işaretiyle aynen çizilmesi, iki rapor türünün başlıkları, kesin görüntü adı, aynı bayt; var olan dosya, `.svg` dışı uzantı, rapor klasörüne yazma, manifestten sonra değişmiş/tamamlanmamış/desteklenmeyen rapor, tutarsız kovalar ve satırsız rapor reddi; doğrulanamayan grafiğin silinmesi; numpy/scikit-learn/LightGBM, DB ve ağ katmanının ayrı süreçte yüklenmemesi. |
| `tests/test_price_statistics.py` | İstatistik hesabı: tam kapsam dönemi, 30 gün/14 geçiş/7 gün/18 saat eşikleri, İstanbul günü, NULL üzerinden geçmeme, değişkenlik, grafik aralığından bağımsızlık. Veritabanısız. |
| `tests/test_api_foundation.py` | API okuma rolünün izinleri (yazamaması, kalıcı nesne kuramaması) ve test ortamının ağ/adres korumaları. |
| `tests/test_api.py` | FastAPI: adresler ve OpenAPI, kuruş/UTC/NULL, fiyat yaşı, rol/şema hataları, dört bağlantı sınırı, kesinti ve yeniden bağlantı, 5 sn sorgu zaman aşımı, tutarlı cevap. |
| `tests/test_api_client.py` | Yerel API istemcisi: katı girdi/JSON ve alan tamlığı, sabit hedef/proxy/yönlendirme sınırı, güvenli hatalar, tekrar/önbellek olmaması, kaynak bırakma. |
| `tests/test_docker_entrypoint.py`, `tests/test_docker_lock.py` | Docker parolasının çıktıdan korunması, yalnız kopya DB hedefi, pgpass yazımı ve süreç devri; yanlış ortam, bozuk hash, eksik ek özellik ve pyproject/kilit uyuşmazlığının reddi. |
| `tests/test_delivery.py`, `tests/test_delivery_display.py`, `tests/test_delivery_cli.py` | Paket/kod/model/şema bütünlüğü, Docker kopyası ve gösterim onayı, PowerShell seçim/kilit/idempotence/kurtarma sözleşmesi. |
| `tests/test_docker_check.py`, `tests/support/docker_fixture.py`, `tests/support/docker_probe.py` | Kabul aracının alan/env/sır sınırları; CI ve yerel Docker için yalnız yapay kaynak, HTTP/rol/grafik/kapı/ağsız kabul yardımcıları. |
| `tests/test_ui.py` | Streamlit ekranı (AppTest) ve grafik verisi. Yapay örnekler `tests/support/ui_samples.py`'dedir; AppTest ve önizleme ortak kullanır, gerçek fiyat değildir. |
| `tests/test_api_ui_integration.py` | Gerçek test okuma hesabı → FastAPI → istemci → Streamlit zinciri; SQL ve hesaplama sahte değildir. |
| `tests/test_api_ui_check.py`, `tests/test_ml_data_check.py`, `tests/test_live_discovery_check.py` | Aşağıdaki denetim/kontrol araçlarının kendileri. |
| `tests/test_market_history.py`, `tests/test_market_history_import.py` | Cimri alımı ve aktarımı: kimlik, tarih/fiyat/eksik veri, ham kanıt ve parmak izi, istek bütçesi, kilit, ilk/tekrar aktarım, çelişki, READ ONLY önizleme, kesinti. |
| `tests/fixtures/` | Gerçek kaynaklardan küçültülmüş örnekler (kaynak yolu ve SHA-256 ile), kataloğun sabit kopyası (`discovery/catalog.json`) ve Cimri örneklerindeki 57 ürünün sabit kopyası (`cimri_catalog_products.json`). Testler `data/` veya ağa bağlı değildir; sonuçları canlı `config/catalog.json` içeriğine bağlı değildir. Gerçek dosyaların sözleşmesini bilerek denetleyen testlere örnekler: `test_real_config_files_match_contracts` (keşif ayarı ve katalog sözleşmeye uyar), `test_config_mapping_uses_existing_catalog_and_recorded_source_ids` (Cimri eşleştirmesi gerçek katalogdaki etkin ürünlere bağlı) ve `test_existing_catalog_keys_can_use_client_validation` (her gerçek ürün anahtarı ekran istemcisinin anahtar kuralından geçer). ML ve Docker denetimleri de ilgili ayar/kilit/kod dosyalarını kendi sözleşmeleri için okur; bu, canlı site veya fiyat doğrulaması değildir. |
| `.github/workflows/ci.yml` | Her push/pull request'te geçici PostgreSQL 17 (`C.UTF-8`) açar, `dev,web,ml` bağımlılıklarını kurar; yalnız `_test` DB'de API rolünü hazırlar ve Black/Flake8/tam testleri çalıştırır. Ayrı Docker işi imajı ve yapay _test kaynağını sıfırdan hazırlar, bütün akış kabulünü çalıştırıp yalnız raporu yükler. `ci_only` şifresi yalnız test işinin geçici sunucunundur. |
| `.github/workflows/bulut-deneme.yml` | Elle tetiklenen bulut erişim denemesi (zamanlama, veritabanı ve gizli anahtar yok): `tools/live_scraper_check.py samsung_galaxy_a55_128gb` ile 4 sayfayı GitHub'ın makinesinden okur; ardından iki Trendyol sayfası için gelen sayfanın kısa özetini (boyut, dil, başlık, veri blokları, koruma izleri, çerez adları) yazar. Sonuç "Bilinen sınırlar"dadır. Tur saatlerinde (10:00–10:40, 22:00–22:40) tetiklenmez: `data/scrape.lock` bu makineye özgüdür. |

### Canlı kontrol ve denetim araçları: `tools/`

Otomatik test değildir; `pytest` bu klasörü toplamaz. Araçlar proje kökünden
`.venv\Scripts\python.exe tools\<araç>.py` biçiminde çalıştırılır. Siteye giden
araçları kullanıcı kendi terminalinden, tur/keşif saatleri dışında çalıştırır.
Gerçek DB denetimi yalnız okuma hesabıyla yapılır; Docker kabulü ayrı yapay
`_test` kaynağını kullanır. Yetki sınırının kaynağı [AGENTS.md](../AGENTS.md)'dir.

| Araç | Ne işe yarar |
|---|---|
| `tools/docker_check.py` | Yalnız yapay _test verisiyle ayrı yerel Docker/CI kabulü; port/rol/dosya, HTTP/grafik, kalıcılık, kesinti, kapı ve ağsız çalışma. Ayrıntı [Docker kabulünde](#docker-tek-komutla-kullanım). |
| `tools/live_scraper_check.py` | Katalogdaki sayfaları canlı okur; bütün satıcıları gösterir. İsteğe bağlı `product_key` ön eki (ör. `samsung_`) ile yalnız o ürünler; sayfa seçimi toplama turuyla aynı fonksiyondur. Başka bir tarama sürüyorsa (ortak kilit) çıkış kodu 3'tür. |
| `tools/live_discovery_check.py` | Keşfi kataloğa yazmadan canlı çalıştırır; `--trace` ile her kararın nedenini gösterir. Normalde raporu `data/discovery_report.json` dosyasının üzerine yazar. `--save-responses KLASOR`, tek hedefin ham HTML/JSON yanıtlarını ve raporunu yeni klasöre kaydeder; karar izini de basar. |
| `tools/ui_preview.py` | Aynı Streamlit ekranını ağsız test istemcisiyle gösterir; kalıcı test verisi uyarısı vardır. API/DB veya canlı site gerekmez; kullanıcı görünüm/yenileme kontrolünü burada yapar. |
| `tools/ml_data_check.py` | Yalnız okuma hesabıyla günlük 30+7 ML pencereleri, %5 hedefi, eksik/kapsam nedenleri ve zaman bölümlerini hesaplar. Kendi/Cimri ayrı; `--snapshot` ile ağsız tekrar. Model eğitmez, API/site çağırmaz. |
| `tools/ml_label_check.py` | 4.1 görüntüsü ve 4.2 etiket klasörünü yalnız dosyadan okur; manifesti doğrular ve bütün sıkı pencereleri eski hesaplayıcıyla karşılaştırır. DB/site çağırmaz; dosya yazmaz. |
| `tools/api_ui_check.py` | Yerel API'nin gerçek veritabanını doğru sunduğunu, üretim kodunu kullanmadan bağımsız SQL hesabıyla karşılaştırır ([bağımsız denetim](#sqlapistreamlit-bağımsız-denetimi)). |
| `tools/docker_entrypoint.py` | İmajın girişidir; API için gizli dosyadan geçici pgpass hazırlar ve komutu `exec` ile devreder. UI parolayı okumaz; DB/site isteği yapmaz. |
| `tools/docker_lock.py` | `input` ile pyproject çalışma gereksinimlerini yazar; `lock` ile Linux pip raporunu doğrulayıp hash'li kilidi üretir. Paket kurmaz, ağ/DB kullanmaz. |

## Komutlar

Windows ve PowerShell, Python sanal ortamı `.venv`:

```powershell
# Kurulum: mevcut kod + test araçları + API/arayüz + ML kütüphaneleri
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev,web,ml]"

# Otomatik testler (internete çıkmaz; veritabanı testleri TEST_DATABASE_URL ister)
.venv\Scripts\python.exe -m pytest -q

# Veritabanı şeması: bekleyen migration'ları uygula / durumu göster
.venv\Scripts\python.exe -m app.database migrate
.venv\Scripts\python.exe -m app.database status

# Katalogu veritabanına eşitle (önce deneme; keşif kataloğu değiştirdikten sonra)
.venv\Scripts\python.exe -m app.database sync-catalog --dry-run
.venv\Scripts\python.exe -m app.database sync-catalog

# Fiyat toplama turu: sitelere istek atar ve sonuçları veritabanına yazar
.venv\Scripts\python.exe -m app.collection --prefix poco_   # yalnız POCO bağlantıları
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
- Hedeflerin güncel listesi `config/discovery.json` içindedir; tarihli kapsam
  sayıları [README Güncel kapsam](../README.md#-güncel-kapsam) tablosundadır.
  POCO X5 Pro iki sitede de satılmadığı için `active: false` bırakılmıştır.

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

Bu tarihsel örnek keşif ile fiyat okumasının bağlantısını anlatır; sayfa,
satıcı ve fiyat değerleri bugünkü durum değildir. Kaynak notunda doğrulama
tarihi bulunmadığından örnek güncel fiyat kanıtı olarak kullanılmaz.

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
3. Arama API'si sayfa sayfa okunur. Ürünün markası hedefe, ana kategori ya da
   tanım adı yeni telefona uyuyorsa varyantları model adıyla süzülür; iki
   alandan biri aksesuar/yenilenmiş diyorsa ürün elenir (iPhone'ların ana
   kategorisi "iPhone iOS Telefonlar", tanımı "Cep Telefonu"dur). İkinci
   sayfadan itibaren hedefe uyan yeni varyant kalmazsa sayfalama uyarısız
   durur: sonuçların alaka sırasıyla geldiği varsayılır. Sayfadaki bütün
   ürün kodları önceki sayfalarda görülmüşse `repeated_page` raporlanır. API
   engellenirse (`search_api`) HTML'den bulunanlar korunur.
4. Her ürün sayfası açılır ve kimlik kanıtı kaydedilir. Doğrulanmış sayfa aday
   üretir ve `allVariantCombinations` (bütün renk/kapasite seçenekleri) kuyruğa
   eklenir. Kabul edilmeyen sayfada marka/kategori, kendi SKU'sunun seçenekleri,
   model/kapasite ve hedefte varsa ağ denetimleri gezinmenin devamını belirler.
   Bu denetimlerden geçen sayfanın seçenekleri taranır ama kendisi aday olmaz;
   hata veren sayfanın seçenekleri eklenmez. Stoksuz olduğu için aramada
   görünmeyen kapasiteler de bu yolla bulunur.

Doğrulanmış adayın adresi, kanıtın toplandığı istenen ürün adresidir; canonical
bu adresin yerine yazılmaz. Canonical ürün yolundaki SKU başka bir ürünü
gösterirse `source_id_mismatch` kimlik çelişkisi oluşturur. Aynı SKU'nun başka
bir yazımı veya yolundan SKU çıkarılamayan bir canonical, aday adresini
değiştirmez. Küçük harfli SKU eşdeğerdir; yalnız sorgudaki SKU kullanılmaz.

### Otomatik güvenli kabul

`app/discovery/acceptance.py`, aynı sayfanın ürün koduna bağlı kimlik
kanıtlarını toplar ve `verified` (doğrulandı), `mismatch` (uyuşmazlık),
`insufficient` (kanıt yetersiz) kararı verir. Model, marka, kapasite, renk,
yeni telefon kategorisi ve kendi JSON-LD Product/ProductGroup teklifindeki
NewCondition birlikte aranır. Garanti yazısı yeni ürün kanıtı değildir;
yenilenmiş/aksesuar/ikinci el/teşhir kanıtı NewCondition etiketinden önce gelir.
Fiyat/satıcı/stok, kimlik kararı yerine kullanılmaz; kimliği tam stoksuz aday
kabul edilebilir. Yanlış başka SKU'nun fiyatı veya özelliği ödünç alınmaz.

İki adaptör de yalnız `verified` kararındaki adayı döndürür. Doğrulanmayan
sayfalarda eski kimlik denetimleri ayrıntılı `candidate_rejected` açıklamasını,
Hepsiburada'da ayrıca seçenek taramasının sınırını korur; bu denetimler ikinci
bir aday üretmez. Son rapor kontrolü bütün kararları kanıttan yeniden hesaplar;
`mismatch` ve `insufficient` sayfalar ret/eksik kanıt gerekçeleriyle raporlanır.

Ağ ayrımı hedefin kimliğine dahilse olumlu kanıt gerekir: kendi başlığında
açık 5G veya aynı kodun ağ özelliği. 5G yazmaması 4G kanıtı değildir; 4.5G
4G sayılır. Açık ağ, kapasite, renk veya RAM çelişkisi ret nedenidir; RAM'ın
bulunmaması tek başına ret değildir. Hepsiburada özellikleri yalnız ürünün
ana `productState.product`/ürün kökü içinde okunur; önerilen ürüne girilmez.
Renk kendi varyantı/ürün alanından alınır; kayıtlı satışa kapalı örneklerde
yalnız tam başlığın açık renk son eki de kullanılır. Sınırlı renk sözlüğü,
tanınmayan renkleri görselden tahmin etmez (bilinen sınırı: "Bilinen sınırlar"). Blue/Mavi eşitliği kayıtlı 6 Ekim
örneğine dayanır; genel WebColor “Çok Renkli” özgül renk sayılmaz.

Trendyol'da renk, sayfanın renk seçicisindeki addır (varyant listesindeki
`DsmColor` ve `product.slicingAttributes`): bu ad varsa satıcının "Renk"
özelliği ve JSON-LD rengi karşılaştırmaya girmez. Satıcı alanı genel ad
yazar ("Black" için "Siyah", "Cosmic Orange" için "Turuncu"), JSON-LD bazen
kapasite ("256 GB"). Seçici adı yoksa diğer renkler yine birbiriyle
karşılaştırılır; tamamı kapasite olan değer renk sayılmaz. İki seçici alanı
çelişirse sayfa reddedilir. Kural 19 Ekim raporundaki 109 Trendyol sayfasına
dayanır (hepsinde seçici adı vardı, iki alan hiç çelişmedi); kayıtlı
örnekler `tests/fixtures/discovery/acceptance_examples.json` içindedir.
Hepsiburada'da renk adı uyuşmazlığının gerçek örneği görülmediği için orada
kural değişmedi. Kural kanıttan yeniden hesaplandığı için bu değişiklikten
önce üretilmiş önizleme raporları `--apply-report` ile uygulanamaz; yeni
önizleme gerekir.

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
# Kurulu haftalık görevin otomatik kabul modu.
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
- Dosya kilit altında yeniden okunur ve atomik olarak (geçici dosya, diske
  zorla yazma, yer değiştirme) yazılır. Katalog, rapor ve hazırlık kaydı aynı
  yazıcıyı (`_atomic_json`) kullanır; yazılan baytlar parmak izi hesabındaki
  JSON'un aynısıdır. `--dry-run` kataloğa hiç yazmaz.

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
| `repeated_page` | Site aynı sonuç sayfasını tekrar döndürdü; sayfalama durduruldu. Hepsiburada API'sinde sayfadaki bütün ürün kodları önceki sayfalarda görülmüş demektir; yalnız hedefe uyan yeni sonuç kalmaması bu uyarıyı vermez. |
| `variant_fetch`, `missing_variants` | Varyant listesi alınamadı veya boş geldi. |
| `group_url_pending` | Hepsiburada arama API'sinin varyant kaydındaki adres ne ürün (`-p-`) ne grup (`-pm-`) biçiminde; aday çözülemedi. 1–2 Kasım 2026 API yanıtlarında görülmedi. HTML arama sayfasında bu iki kalıba uymayan bağlantılar (menü, kategori…) kart sayılmaz ve uyarısız atlanır. |
| `evidence_missing` | Kendi ürün koduna bağlı kritik kimlik/yeni ürün kanıtı eksik. Aday eklenmez. |

`rejected` içindeki kayıtlar (tek bir aday atlanır, tarama sürer):

| Kayıt | Anlamı |
|---|---|
| `candidate_rejected` | Aday sayfa doğrulanamadı; ayrıntıda neden ve ürün adı var (başka model, kapasite, ağ türü, yurt dışı sürüm, aksesuar…). Taramayı da kısmi sayar. |
| `catalog_conflict` | Sayfa katalogda başka bir ürüne bağlı; aday yazılmadı, mevcut kayıt korundu. |
| `identity_mismatch` | Kendi ürün koduna bağlı alanlarda açık model/kapasite/ağ/renk/RAM/kapsam çelişkisi. |

Komutun çıkış kodu: `0` tam tarama, `2` kısmi tarama (doğrulanmış kayıtlar yine
eklenir; Hepsiburada'da iPhone dışı hedeflerin model filtresi bulunamadığı için
(`model_filter_missing`) bugün pratikte her zaman 2; katalogla
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
bugün pratikte hep `2` olduğundan tek başına bir şey söylemez; uyarılar
`pending` nedenlerine göre sayıldığı için beklenen `model_filter_missing` ve
`search_api` ile gerçek sorunlar (ör. `search_fetch`, `variant_fetch`) bu
satırdan ayırt edilir. "Zaten kayıtlı", bu taramada yeniden görülen katalog sayfalarıdır;
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
| `offer_url` | Seçilen satıcının doğrulanmış teklif adresi veya `null` |
| `current_price` | Güncel fiyat (kuruş) |
| `original_price` | Üstü çizili fiyat (kuruş) veya `null` |
| `seller_name`, `seller_rating`, `seller_rating_scale` | Seçilen teklifin satıcısı ve puanı (puan yoksa `null`) |
| `stock_status` | `Stokta Var`, `Kritik Stok` veya `Tükendi` |
| `timestamp`, `currency` | UTC gözlem zamanı, `TRY` |

`null` hata anlamına gelmez; kaynakta o bilginin güvenilir olarak bulunmadığını
gösterir. Satıcıların bütün teklifleri tek tek kaydedilmez; yalnızca seçilen
teklif döner. Bütün teklifler canlı kontrol aracında (`all_offers`) görülebilir.

### Satıcı teklifinin adresi

`offer_url`, fiyatı seçilen satıcının ölçüm anındaki adresidir. Trendyol'da
kazanan satıcının kendi `merchant.url` alanından okunur; `merchantId` seçimi
bulunmalı ve kaynakta satıcı kimliği varsa onunla eşleşmelidir. Sayfanın ana
satıcısının (varsayılan gösterilen teklif) kaydında adres alanı yoktur; adres,
katalog adresine kaydındaki pozitif tam sayı kimlikle `?merchantId=<id>`
eklenerek kurulur. Diğer satıcıların adresindeki `merchantId` bu kimliktir ve
sayfayı o satıcının teklifiyle açar (27 Ekim'de tarayıcıda doğrulandı);
varsayılan satıcı sonradan değişse de bağlantı ölçülen satıcıda kalır. Kimlik
eksik veya geçersizse adres kurulmaz. Diğer satıcılar için adres kurulmaz,
çünkü o listede kardeş renk sayfalarının satıcıları da bulunur. Bu kuraldan
önceki turlarda (56–57) Trendyol ana satıcı sonuçlarının adresi boştur.

Hepsiburada'da satıcı listesi ile fiyat yanıtının `listingId`, `merchantId`
ve satıcı adı eşleşirse ürün adresindeki `magaza` parametresi kazananın URL
kodlanmış adıyla değiştirilir. Başka satıcıya ait mevcut `magaza` seçimi
taşınmaz.

Adres HTTPS, platformun izinli alan adı ve aynı ürün yol kimliğiyle
doğrulanır. Eksik veya çelişkili bağlantı `null` kalır; geçerli fiyatı,
satıcı seçimini veya mevcut kabul/ret kararını değiştirmez. Bunun için
ek pazaryeri isteği gönderilmez. Stoksuz, hatalı veya bakılmamış sonuç
satıcı bağlantısı taşımaz.

Bağlantı `listing_checks.offer_url` alanında fiyatla birlikte saklanır.
005 migration'ı eski satırlara `NULL` ekler; kapanmış gözlemler geriye dönük
doldurulmaz ve mevcut değişiklik korumaları sürer. Yeni adresler ancak yeni
toplama sonuçlarıyla dolar. Link ölçüm anındaki satıcıyı hedefler; pazaryerinde
sonradan değişen fiyatı, stoku veya satıcının satıştan kalkmasını engellemez.

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
  saatini, `LastTaskResult` ise çalışmakta olan turun sonucunu gösterir. Görev
  Zamanlayıcı geçmişi bu bilgisayarda kapalıdır; atılma, önceki turun logunun
  son yazılma saatinden doğrulanır (tur 7'nin logu 10:03:38'de kapandı).
- Görev yalnız oturum açıkken çalışır. Windows Update bilgisayarı kendiliğinden
  yeniden başlatırsa oturum kapanır ve kullanıcı oturum açana kadar tur
  başlamaz; oturum açılınca kaçan tur bir kez telafi edilir. 12 Kasım'da
  güncelleme 05:48–05:51'de yeniden başlattı, oturum 16:41'de açıldı ve 10:00
  turu 16:51'de yapıldı. Güncellemeden sonra otomatik oturum açma ayarı
  kullanıcı kararıyla açılmadı.
- Tur ortasında bilgisayar uyursa (1 Ekim 09:29, kritik pil, yaklaşık 6,5 dk)
  uyanma anındaki sayfalar `network` hatası alabilir (tur 7: 1 sayfa, DNS
  çözülemedi); tur tamamlanır. Tur sonu ikinci okuma bu sayfaları yeniden dener;
  düzelmezlerse çıkış kodu 2 olur.
- **Bu bilgisayarın güç ayarları:** dizüstünün uyku türü Modern Standby'dır;
  ekran bir zamanlayıcıyla kapanınca (kilit ekranında 30 sn, aksi hâlde 10 dk)
  bilgisayar da uykuya geçer ve tur durur. Kapak kapalı ve ekran kilitliyken
  turların çalışması için prizdeyken (AC) kapak eylemi "hiçbir şey yapma",
  uyku (`STANDBYIDLE`), ekran kapanma (`VIDEOIDLE`) ve kilit ekranında ekran
  kapanma (`VIDEOCONLOCK`) süreleri 0 olmalıdır. ASUS Armoury Crate güç planını
  kendiliğinden değiştirir (prizde "Performance", pilde "Silent"); bu yüzden
  ayarlar üç planın (Dengeli, Silent, Performance) hepsine yazılır. Şarj
  kablosunda temassızlık var (14 günde 52 kez 1–9 sn kesinti); kapak eylemi
  pildeyken de "hiçbir şey yapma"dır, yoksa kısa bir kesinti kapağı kapalı
  bilgisayarı uyutuyordu. Pildeki ekran ve uyku süreleri değişmedi (kilitliyken
  30 sn, aksi hâlde 3–4 dk). Pilde uyuyan bilgisayar kablo dönünce kendiliğinden
  uyanmaz; kilitliyken kısa kesintide uyuyup uyumadığı henüz sınanmadı. 22–23 Ekim:
  ayar yalnız "Dengeli"deyken 22:00 turu kaçtı, telafi turu (tur 48) 22:52'de
  başlayıp gece uykuda bekledi ve ertesi sabah 09:32'de bitti; üç plan
  düzeltildikten sonra tur 49 kapak kapalıyken 10:00'da başladı ve sayfalar
  arasında en uzun ara 42 sn oldu.

#### Geç veya kaçan turun nedeni

Görev Zamanlayıcı geçmişi kapalı olduğu için neden, Windows System olay
günlüğündeki güç ve oturum kayıtlarından okunur. Komut yalnız okur; tarih
aralığı incelenen tur zamanının birkaç saat öncesinden tur logunun
başlangıcına kadar seçilir:

```powershell
Get-WinEvent -FilterHashtable @{ LogName = 'System'
    StartTime = (Get-Date '2026-11-12 04:00'); EndTime = (Get-Date '2026-11-12 17:00') } |
    Where-Object {
        ($_.ProviderName -eq 'Microsoft-Windows-Kernel-General' -and $_.Id -in 12, 13) -or
        ($_.ProviderName -eq 'Microsoft-Windows-Kernel-Power' -and $_.Id -in 41, 42, 506, 507) -or
        ($_.ProviderName -eq 'Microsoft-Windows-Power-Troubleshooter' -and $_.Id -eq 1) -or
        ($_.ProviderName -eq 'User32' -and $_.Id -eq 1074) -or
        ($_.ProviderName -eq 'Microsoft-Windows-Winlogon' -and $_.Id -in 7001, 7002) } |
    Sort-Object TimeCreated | Select-Object TimeCreated, ProviderName, Id
```

| Kayıt | Anlamı |
|---|---|
| Kernel-General 12 / 13 | Açılış / kapanış |
| Kernel-Power 42 | Uykuya giriş |
| Power-Troubleshooter 1 | Uykudan uyanma (kaydın zamanı uyanma anıdır) |
| Kernel-Power 506 / 507 | Modern bekleme girişi / çıkışı |
| Kernel-Power 41 | Düzgün kapanmamış sistemin yeniden açılışı |
| User32 1074 | Kapatma/yeniden başlatma isteği; ayrıntıda isteyen süreç (ör. `Explorer.EXE` kullanıcı, `MoUsoCoreWorker.exe` Windows Update) |
| Winlogon 7001 / 7002 | Oturum açıldı / kapandı (kilit ekranı bu kaydı üretmez) |

Kernel-Power 107 (uykudan dönüş) zamanı uykuya giriş anını gösterebildiği için
uyanma zamanı olarak kullanılmaz. Tur saatinde son kayıt uyku, kapanış,
modern bekleme girişi veya oturum kapanmasıysa tur o anda başlayamazdı; telafi
turu sonraki uyanma/açılış ve oturum açılmasından birkaç dakika sonra başlar.

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
nedenleri, `pending` içinde beklenen `model_filter_missing`/`search_api` dışında
bir uyarı), uygunsa
`python -m app.discovery --apply-report data\discovery\kesif_<tarih-saat>.json`
ile uygulanır.

Otomatik ekleme, kaynakların eksiksiz tarandığı veya ML verisinin hazır olduğu
anlamına gelmez. Yeni sayfa ürünün izlenen kapsamını değiştirir; eski fiyatlar
silinmez. Güncel ML hesabında `y_sabit`, başlangıç akşamının sayfa kümesini
korur; sonradan eklenen sayfa önceki başlangıcın gelecek minimumuna girmez.
Yalnız kapsam değişmesi bu başlangıcın geçmiş süresini sıfırlamaz veya
etiketini geçersiz kılmaz. Eski sıkı 30+7 denetiminde ise kapsam değişen
pencere elenir; iki hesabın farkı [etiket rehberindedir](#günlük-seri-ve-etiketler-python--m-appml-labels).

Görev Zamanlayıcı "Son çalıştırma sonucu"
(`Get-ScheduledTaskInfo -TaskPath '\FiyatTakip\' -TaskName 'HaftalikKesif'`):
`0x0` tarama tam, `0x2` tarama kısmi (bugün beklenen sonuç; bkz. keşif çıkış
kodları), `0x3` kilit meşgul (keşif atlandı, telafi edilmez), `0x1` başlayamadı
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

Katalogdaki telefonların Cimri'de görünen bir yıllık fiyat geçmişi ayrı
`market_history` tablosundadır. İlk alım 8 Ekim 2026'da yapıldı (57 ürün,
20.805 kayıt). Son alım 2 Kasım 2026'da yapıldı
(`data/market_history/katalog_20261102_162033_694/`): 58 ürün kaydedildi,
iki eşleştirmesiz ürün atlandı. Önizleme ve aktarım 1.790 yeni gün ekledi,
19.360 gün aynı çıktı; çelişki yoktu. 8 Ekim satırlarındaki 20 yarım gün
farkında eski kayıt korundu. Güncel ürün/kayıt/eksik fiyat sayıları ve tarih
aralığı [README Güncel kapsam](../README.md#-güncel-kapsam) tablosundadır;
Galaxy S24 FE 128 GB 3 Kasım 2025'ten başlar. Her ürünün 8 Ekim ve 2 Kasım
satırları [yarım gündür](#ağsız-aktarım-import). Düzenli Cimri toplaması
yapılmaz; Cimri serisi kendi toplama serimizle birleştirilmez ve aynı ölçüm
sayılmaz. Kod (`app/market_history/`) korunur; yeni bir alım ayrı karar ister
([kullanım değerlendirmesi](#kullanım-değerlendirmesi)).

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

28 Ekim web aramasıyla, katalogda sonradan eklenen Galaxy S24 FE 128 GB
(`samsung_galaxy_s24_fe_128gb`) için [ana sayfa](https://www.cimri.com/cep-telefonlari/en-ucuz-samsung-galaxy-s24-fe-fiyatlari,a2372356868)
eklendi; dosyada 58 eşleştirme var. Bu sayfanın adında kapasite yazmıyor.
Modelin ilk çıktığı kapasitenin ana sayfası böyle adlandırılıyor; Galaxy
S25 128 GB eşleştirmesi de aynı kalıptadır. Renk sayfasında 128 GB yazıyor;
S24 FE 256 GB ise ayrı bir ana sayfadır. Cimri sayfası web aracına 403
verdiği için kimlik aramada doğrulanamadı; 2 Kasım son alımında doğrulandı
(Cimri 2372356868, "Samsung Galaxy S24 FE 128 GB 8 GB Ram"). Kimliği alımın kendi kontrolleri
(sayfa ve API kimliği, marka, kategori, başlık ve H1'lerin model/kapasitesi)
doğrular; bunlardan biri tutmazsa ürün `error` olur ve aktarılmaz. Aynı
aramada diğer iki ürün için yine yalnız başka ürünlere ait sayfalar çıktı.
Galaxy S25 512 GB'ın katalogda etkin sayfası da yoktur; ürün 20 Kasım'da
pasife alındı ([plan](../proje_plani.md#5-kararlar)).

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
İki eşleştirme açık olduğundan bütün 58 alım başarılı olsa bile katalog
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

**Yeni / yenilenmiş ayrımı:** `verified_page`, ürünün gömülü başlığına ve
her H1 başlığına ortak `verify_identity` kuralını uygular. Başlıktaki
yenilenmiş, refurbished, ikinci el, teşhir ve diğer kapsam dışı ifadeler
reddedilir; kategori tam `cep-telefonlari` olmalıdır. `yenilenmis-cep-telefonlari`
bu kontrolden geçmez. Aktarım da kaydedilmiş HTML'den aynı kimliği yeniden
doğrular; yalnız alım raporundaki sonuca güvenmez. Kategori ve başlık
korumaları ilk alım kodunda da vardır; testler yenilenmiş başlık ve kategoriyi
ayrı ayrı sınar. Bu kontrol sayfa kimliğine aittir; Cimri tekliflerinin her
birine ayrı durum filtresi uygulanmaz. Tarihsel fiyatların durum kanıtı
[Cimri sınırında](#bilinen-sınırlar) açıklanır.

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
yeniden birebir karşılaştırır. Diğer günler ile sıfır/eksik değer kuralı
korunur (grafikteki sayısal sıfır eksik sayılır, tabloyla çelişirse ret). Bugünün ham API fiyatı sıfır/null ise ilk
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
NULL–NULL aynı, NULL–fiyat farklıdır. Tam bir günde fiyat ya da herhangi bir
günde Cimri kimliği farklıysa o üründe hiç yeni gün yazılmaz; diğer
doğrulanmış ürünler devam eder.

**Yarım gün:** Alım günü Cimri'de henüz kapanmamıştır; o günün değeri gün
içinde değişir. 8 Ekim'deki alımlar arasında 19.292 geçmiş gün değerinin
hiçbiri değişmedi; alım gününün değeri ise 53 üründe 5 kez değişti. Günü,
alım anının (`captured_at`) İstanbul tarihine eşit olan değer yarım gündür.
Ortak bir günde fiyat farklıysa ve eski satır ya da gelen değer yarım günse
bu çelişki sayılmaz: ilk satır korunur, fark ürünün altında "Yarım gün farkı"
olarak raporlanır ve ürünün yeni günleri eklenir. Cimri kimliği farkı yarım
günde de çelişkidir. Yarım gün farkı "aynı" sayısına girmez ve çıkış kodunu
değiştirmez.

SQL/bağlantı hatasında komut durur, tamamlanan ürünler kalır. COMMIT
yanıtı kaybolduğunda son ürünün sonucu belirsiz olarak bildirilir; yeniden
çalıştırma aynı kaydı çoğaltmadan sonucu netleştirir.

`--dry-run` tek REPEATABLE READ, READ ONLY transaction'da çalışır; INSERT
deneyip geri almaz. Önizleme yazma yetkisi veya sonuç rezervasyonu değildir;
normal komut bütün kontrolleri yeniden yapar. Çıktı her ürünü, eklenecek/aynı
kayıtları, yarım gün farklarını, çelişkili tarihleri ve eski/yeni kuruş fiyatı
ile Cimri kimliğini gösterir. Kaynak dosyalarına veya giriş raporuna
yazılmaz; çıktı terminaldedir.
[PostgreSQL READ ONLY belgeleri](https://www.postgresql.org/docs/17/sql-set-transaction.html)

Çıkışlar: **0** girdideki ürünler aktarıldı/zaten aynı (yarım gün farkı olsa
da); **2** atlanan veya
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
kanıtı sayılmadı. Bu nedenle **19 Ekim'de** yeni alım/aktarım yapılmadı.
Kullanıcı **23 Ekim'de** son bir defalık alımı ve ML eğitiminde kullanımı
onayladı; son alım/aktarım **2 Kasım'da** tamamlandı
([kararlar](../proje_plani.md#5-kararlar), [alım kaydı](#cimri-geçmişi-bir-defalık-alım-ve-aktarım)).
Bu kullanıcı kararı kullanım uygunluğunun resmen doğrulandığı anlamına
gelmez; yukarıdaki sınır sürer. Düzenli Cimri toplaması yoktur, yeni alım
ayrı karar ister. Akakçe'ye ilişkin o tarihli değerlendirme de
[arşivdeki kullanım incelemesindedir](arsiv/teknik_2026-10-20.md#cimri-kullanım-değerlendirmesi-bakım-41-19-ekim).

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

Önce 001–005 uygulanmış olmalıdır. `scripts/api_okuma_rolu.sql` yönetici
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

Tam testler `dev,web,ml` kurulumu, `TEST_DATABASE_URL` ve rol testleri için
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
| `/api/v1/products/{product_key}/prediction` | Ayrı kayıtlı tahmin cevabı; bilinmeyen ürün 404, doğrulanamayan dosya 503 |

Ürün parametreleri `history_days=30` ve `cimri_days=366`; ikisi de 1–366.
Okuma katmanının son kayıtlı veriden açtığı, sınırları dahil aralıklar korunur.
Adresler/cevap modelleri `/docs` ve `/openapi.json` üzerinden belgelenir.
Önbellek yoktur; cevaplar `Cache-Control: no-store` taşır.

Ürün cevabı `product`, `state`, `current`, `checks`, `best_offer`,
`last_successful_offer`, `history`, `cimri_history`, `statistics`,
`generated_at`, `currency`, `price_age_seconds` ve `is_stale` alanlarıdır.
Tek `read_product` çağrısının görüntüsünden hazırlanır; istatistikler aynı
görüntünün bütün iç geçmişini kullanır. `all_history` JSON'a gönderilmez.

- `checks`, `best_offer` ve `last_successful_offer` kayıtları `offer_url`
  alanını açıkça taşır; adres yoksa JSON `null` döner. `url` mevcut katalog
  adresidir; ölçüm anındaki satıcı adresinin yerine geçirilmez. Alanın
  eklenmesi nedeniyle API ve katı cevap doğrulayan yerel istemci birlikte
  güncellenip yeniden başlatılır; endpoint adresleri değişmez.
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
| 503 | `prediction_unavailable` | Tahmin dosyaları veya kaynak görüntü doğrulanamadı |
| 503 | `database_unavailable` | DB bağlantısı/sorgusu veya zaman aşımı |
| 503 | `read_access_denied` | Okuma hesabı/izinleri uygun değil |
| 503 | `schema_not_ready` | Şema eksik/tutarsız |
| 500 | `internal_error` | Beklenmeyen kod/cevap doğrulama hatası |

### Kayıtlı tahmin cevabı

`GET /api/v1/products/{product_key}/prediction` sorgu parametresi istemez.
Ürün kimliği kısa bir salt okunur DB işlemiyle kontrol edilir; bağlantı
bırakıldıktan sonra dosyalar okunur. Mevcut fiyat cevabı değişmez.

| `state` | `reasons` | `forecast` |
|---|---|---|
| `closed` | `display_closed` veya `display_not_approved` | `null` |
| `unavailable` | `expected_daily_record_missing` | `null` |
| `insufficient_data` | Mevcut üç gölge yeterlilik gerekçesi | `null` |
| `available` | Boş dizi | Tahmin nesnesi |

Her cevapta UTC `generated_at` bulunur. Tahmin nesnesi `probability` (0–1),
`model_name`, `anchor_day`, `anchor_at`, `reference_price_kurus`,
`target_start`, `target_end`, `recorded_at` ve `listing_count` taşır.
Para tam sayı TRY kuruşudur; dönem başlangıç gününden sonraki 1–7. günlerdir.
Zamanlar UTC'dir; güncellik İstanbul takvimine göre yalnız dünün kaydıdır.
11:00 işi bitmeden `unavailable` dönebilir; eski güne geri dönüş yapılmaz.

Yalnız tamamlanmış resmi klasörler kullanılır; dosya hash'leri, ön kayıtlı
model, başlangıç ayarı, zamanlar ve ürün-gün tekilliği kontrol edilir.
Yarım klasörler atlanır. Başlangıç fiyatı, gerçek akşam turu zamanı ve sayfa
sayısı manifest SHA'sıyla eşleşen kaynak görüntünün günlük serisinden
çıkarılır. Kayıt girdileri ve yeterlilik gerekçeleri de bu görüntüyle
karşılaştırılır; güncel DB fiyatı başlangıcın yerine geçirilmez.

Bozuk kayıt, kaynak uyuşmazlığı veya okunamayan dosya, ayrıntı sızdırmayan
`503 prediction_unavailable` üretir. Fiyat uçları çalışmayı sürdürür.
API kilit/onay dosyası yazmaz, model açmaz, pickle yüklemez, eğitim veya
olasılık üretimi çalıştırmaz; dış ağa çıkmaz. Kapalı gösterim cevabında
olasılık bulunmaz. [Gösterim onayı](#tahmin-gösterim-onayı-python--m-appml-shadow-display)
ayrıdır; Streamlit bu cevabı [tek tahmin kartında](#tek-tahmin-kartı) gösterir.

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
içermez. Beş GET yalnız `http://127.0.0.1:8000` adresine gider;
adres/port ortam ayarı veya genel URL isteyen işlev yoktur.

### Ortak sözleşme ve işlevler

`app/api/schemas.py` mevcut cevap modellerini bağımsız tutar.
İstatistiklerin `Reason` tipi temel sözleşmededir; hesaplar değişmedi.
API'nin `models.py` modülü kaynak görüntüsünü ortak cevaba dönüştürür.
İstemci yalnız ortak sözleşmeleri yükler; DB/havuz/istatistik/uygulama
modüllerini içe aktarmaz. Mevcut ürün JSON alanları korunur; tahmin ayrı
cevap modelidir.

| İşlev | Doğrulanmış sonuç |
|---|---|
| `get_health()` | `HealthResponse` |
| `get_prediction(product_key)` | `PredictionResponse`; tahmin isteğinde gün parametresi yoktur |
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

İstek gönderilmeden GET yöntemi, şema/host/port, beş izinli yol ve
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
veritabanına veya pazaryerine erişmez. API ve ekran ortak cevap sözleşmesini kullanır.

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
  önceki fiyatla hesaplanır. Sıfır fark `0,00 TL`, gri ve oksuzdur; düşüş
  yeşil aşağı, artış kırmızı yukarı okla gösterilir. Yön ve renk, para metni
  yerine tamsayı kuruş farkından seçilir. Satıcının eski fiyatı ayrıca etiketlenir.
- Güncel teklifin `offer_url` alanı doluysa “Satıcı teklifini aç” düğmesi
  bu adresi kullanır. Boşsa “Ürün sayfasını aç” düğmesi katalog adresine gider
  ve satıcıya özel bağlantının bulunmadığı açıklanır.
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

### Tek tahmin kartı

Kart, **Güncel sonuç** bölümünden sonra ve fiyat istatistiklerinden önce
yer alır. Seçilen telefonun `get_prediction(product_key)` cevabını kullanır;
fiyat cevabından veya grafiklerden tahmin üretmez. Tahmin geçmişi listesi
veya grafiği yoktur.

| Durum | Ekran |
|---|---|
| `closed` | Gösterimin kapalı olduğu ve gerekli kesin değerlendirme/onay açıklaması; yüzde yok |
| `unavailable` | Dünün kaydı bekleniyor; 11:00 çalışması henüz bitmemiş olabilir; eski oran yok |
| `insufficient_data` | Kısa geçmiş, son 14 günde fazla eksik fiyat veya eğitimde görülmemiş aile gerekçeleri; yüzde yok |
| `available` | Bir ondalıklı Türkçe yüzde, ayrı başlangıç fiyatı, başlangıç günü, gerçek akşam turu zamanı, dönem, sayfa sayısı, model ve kayıt zamanı |

Kartın açıklaması “Takip edilen başlangıç sayfaları kapsamında en az %5
düşüş”tür. Para API'nin tamsayı kuruş alanından, saatler İstanbul'a
çevrilerek gösterilir. Başlangıç fiyatı güncel teklifin yerine geçirilmez.
Grafik aralığı seçimleri tahmin isteğine aktarılmaz ve dönemi değiştirmez.

Her yenilemede tahmin yeniden okunur; cevap veya hata oturumda saklanmaz.
Telefon değişince, kayıt eksilince, gösterim kapanınca veya tahmin isteği
başarısız olunca önceki yüzde kaldırılır. Tahmin hatası yalnız bu kartta
güvenli açıklama olarak görünür; fiyatlar, istatistikler ve grafikler
gösterilmeye devam eder. Sonraki yenileme yeniden dener. Fiyat cevabı
alınamazsa önceki fiyatlarla birlikte eski tahmin de ekranda tutulmaz.

Kartın bulunması gösterim onayı değildir. Gerçek gösterim
[kesin rapor ve açılış komutuna](#tahmin-gösterim-onayı-python--m-appml-shadow-display)
bağlıdır; varsayılan kapalıdır.

Gerçek örnek: iPhone 15 128 GB'ın 5 Kasım kaydı, o akşamki **56.649 TL**
başlangıç fiyatına ve **6–12 Kasım** dönemine aittir. Kaynak görüntü
`data/ml/golge/goruntuler/veri_20261106_110023_673048/`, kayıt
`data/ml/golge/tahmin_20261106_110023_673048/predictions.jsonl` içindedir.
Gösterim kapalıyken bu kaydın olasılığı API'ye veya karta çıkarılmaz.

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
global durum, seçilen ürün ve onun tahmini yeniden okunur; istemci `with` ile bırakılır.
Yalnız seçim/aralık tercihleri oturumda tutulur; veri/istemci önbelleği yoktur.
Fiyat API hatasında eski teklif/grafik/göstergeler ve tahmin kaldırılır;
tahmin isteği hatası yalnız tahmin kartında kalır. Güvenli Türkçe açıklama
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
.venv\Scripts\python.exe -m streamlit run tools\ui_preview.py --server.address 127.0.0.1 --server.port 8502 --server.headless true --browser.gatherUsageStats false
```

Proje klasöründen çalıştırılır; normal ekran `http://127.0.0.1:8501`,
test önizlemesi `http://127.0.0.1:8502` adresindedir. Önizleme aynı `render_app`
işlevine testteki MockTransport istemcisini verir; üretim demo modu yoktur.
“Test verisi — gerçek fiyatlar değildir” uyarısı sürekli görünür.
`tests/support/ui_samples.py` örnekleri AppTest ve önizleme için ortaktır; gerçek
fiyat kanıtı değildir. Sidebar'dan teklif/boşluk, eski/kısmi fiyat, stoksuzluk,
doğrulanamama, yalnız Cimri, eksik geçmiş, API hatası ve boş liste denenir.
Tahmin için açık (yapay), kapalı, kayıt yok, üç veri yetersizliği gerekçesi,
tahmin API hatası ve bozuk cevap senaryoları da vardır. Telefon değişimi
ve grafik aralığı seçimleri aynı kart üzerinden denenebilir; gerçek gösterim
onayı veya model kullanılmaz.

Telefon/aralık seçimi, dar ekran görünümü, grafik boşlukları ve hata sonrası
dönüş kontrol edilir. API cevabı saatinin açık oturumda yaklaşık 30 saniyede
değişmesi, elle Yenile'nin hemen yenilemesi ve tercihlerin korunması gözlenir.
Terminalde Ctrl+C önizlemeyi kapatır.

#### Tahmin kartının görsel kabul kontrolü

Bu kontrol yalnız test önizlemesinde yapılır; gerçek gösterim onayı gerekmez.
Geniş pencerede ve telefon genişliğine daraltılmış pencerede aşağıdaki sıra
izlenir. Test verisi uyarısı her durumda görünmelidir.

| Eylem | Beklenen sonuç |
|---|---|
| `Tahmin gösterimi açık (yapay)` seç | Kart Güncel sonuçtan sonra, istatistiklerden önce gelir; yüzde, başlangıç fiyatı, akşam turu, dönem ve kapsam okunur; metinler üst üste binmez. |
| Telefonu değiştir | Yeni telefonun bilgileri gelir; önceki telefonun yüzdesi kalmaz. |
| Grafik aralığını değiştir (örneğin 30 → 7 gün) | Yalnız ilgili grafik değişir; tahmin dönemi aynı kalır. |
| Güncel kayıt yok, üç yetersizlik, tahmin API hatası ve bozuk cevap senaryolarını seç | Yüzde kaldırılır; gerekçe yalnız kartta görünür, mevcut fiyat ve grafikler okunabilir kalır. |
| Açık yapay senaryoya geri dön | Uyarı kalkar ve o telefonun kartı yeniden gelir. |
| Elle Yenile'ye bas, ardından yaklaşık 30 saniye bekle | Ekrandaki API cevap zamanı elle ve otomatik yenilenir; telefon ve grafik tercihleri korunur. |

AppTest ekranın ürettiği değerleri ve durum geçişlerini denetler; tarayıcı
yerleşimini, dar ekrandaki taşmayı veya gerçek zamanlı otomatik yenilemeyi
görsel olarak doğrulamaz. Bu kontrollerin tamamlanma durumu
[tamamlanan uygulama adımlarının 7.4 satırında](../proje_plani.md#tamamlanan-uygulama-adımları) tutulur.

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

Denetim, `tools/api_ui_check.py` içindeki hesap ve şema kontrollerini
kullanır. `API_DATABASE_URL` ile yalnız SELECT hesabına bağlanır. Tek
görüntüyü UTC, 5 saniye sorgu sınırı ve `REPEATABLE READ / READ ONLY` işlemle
alır. Başlamadan önce çalışan turu kontrol eder. Hesabın sonunda sekiz
nesneyi yeniden okuyup parmak izlerini karşılaştırır. Toplama ve keşif
bittiğinde komutu proje kökünde kullanıcı çalıştırır.

```powershell
$env:API_DATABASE_URL = "postgresql://fiyat_takip_api@localhost:5432/fiyat_takip"
$mlAuditOut = "artifacts\ml_denetim_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
.venv\Scripts\python.exe tools/ml_data_check.py --output-dir $mlAuditOut
$LASTEXITCODE
```

Parolayı `pgpass.conf` sağlar. Araç doğrudan DB okur, API sunucusu
gerektirmez ve otomatik zamanlanmaz. Her deneme için yeni çıktı klasörü
kullanılır.

| Çıkış | Anlamı |
|---|---|
| 0 | Denetim doğrulandı; kullanılabilir örnek sayısı sıfır olabilir. ML hazır veya kullanım izni var anlamına gelmez. |
| 1 | Hesap/şema/girdi/DB/çıktı hatası; denetim tamamlanmadı. Ham hata ve bağlantı adresi yazdırılmaz. |
| 2 | Kaynak değişti; sonuç kesin kabul edilmedi. Bu görüntünün ağsız tekrarı da 2 kalır. |
| 130 | Kullanıcı durdurdu; tamamlanmış sonuç değildir. |

Tamamlanan denetim (çıkış 0 veya 2) `snapshot.json`, `rules.json`,
`source_check.json`, `windows.jsonl`, `daily.jsonl`, `report.json` ve
`report.md` üretir. `manifest.json` çıktıların SHA-256 değerlerini taşır.
Görüntü yalnız analiz alanlarını içerir. DSN, parola, satıcı, tur notu
ve ham hata metni dışarıda tutulur. `failure.json` varsa kısmi çıktılar
sonuç olarak kullanılmaz. Kaynak ve analiz hesaplayıcıları ayrı parmak
izleriyle kaydedilir (`analysis_verifier_sha256`). Parmak izi yerel
bütünlük kontrolüdür.

Kaydedilmiş görüntüyü ağsız tekrarlamak için şu komutu kullan.

```powershell
.venv\Scripts\python.exe tools/ml_data_check.py --snapshot "$mlAuditOut\snapshot.json" --output-dir "${mlAuditOut}_tekrar"
$LASTEXITCODE
```

Tekrar görüntünün sabit tarihiyle hesaplar. Aynı kod ve kurallarla
`report.json`, `windows.jsonl` ve `daily.jsonl` birebir eşleşmelidir.
`source_check.json` çalışma biçimini kaydeder. Geçersiz parmak izi, fazladan
alan, tekrarlı veya bozuk kimlik, plan–kontrol ve sonuç–fiyat çelişkisi
reddedilir.

**Sıkı sayım.** İstanbul 10:00 ve 22:00 dilimlerini yalnız zamanlanmış
turlar doldurur. Tur başlangıcı önceki en yakın dilime atanır. Bu nedenle
ertesi gün 09:00 başlangıcı önceki 22:00 dilimindedir. Eksik veya tekrarlı
dilim, yarıda kalma, günü aşan bitiş, planlanmamış ürün ya da eksik/hatalı
sayfa cevabı kalite kusurudur. İki turda ürünün kendi planlanan sayfa
kimlikleri eşleşmelidir.

Başlangıca akşam turunun ürün minimumu, gelecek güne iki turda görülen
minimum fiyat yazılır. Sabah fiyatı, akşam stoksuzsa gelecek minimumuna
girebilir. Başlangıcı yalnız akşam fiyatı sağlar. `Tükendi` geçerli cevaptır.
Cimri ayrı sayılır. Pencerede Cimri ürün kimliğinin değişmesi örneği eler.

Başlangıç günü `d` için `d−29…d` boyunca 30 başlangıç fiyatı, `d+1…d+7`
boyunca 7 günlük minimum gerekir. Kendi verimizde kapsam 37 gün boyunca
sabit ve cevaplar tam olmalıdır. Eksik veri, düşüş gözlense bile NULL etiket
üretir. Tam pencere kuruşla `100×gelecek_minimum ≤ 95×başlangıç` ise 1,
aksi halde 0 etiketini alır. İstanbul'da henüz kapanmamış gün dışarıda kalır.
API'nin 18 saat, 14 geçiş ve 7 gün gibi gösterge eşikleri ayrı hesaplara aittir.

Ürün ve kaynak raporunda tur, sonuç, süre, eksik gün veya fiyat aralığı,
kapsam dönemi, azami tur boşluğu ve pencere sınıfı sayıları bulunur.
`calendar_days` dönem uzunluğu, `observed_days` en az bir kontrol sonucu
veya kaydı bulunan nominal gün sayısıdır. Cimri'de NULL fiyatlı kayıt
gözlem sayılır. Bir pencerenin birden çok elenme gerekçesi olabilir.
İlk pencere sonu ve ertesi gün denetim tarihi etkin, sayfası olan ürün
ve güncel kapsam için koşullu hesaplanır. Cimri'nin veri yaşı ve ML kullanım
belirsizliği raporlanır.

Her kaynakta ortak uygun günlerin ilk taban %70'i eğitim, taban %85'e
kadarı doğrulama ve kalanı testtir. Tarih sınırları bütün ürünlerde ortaktır.
Hedef sonu sonraki dolu bölümün ilk başlangıcına eşit veya daha geç olan
önceki satırlar `purged` olur. Sınırlar temizleme öncesi, gün sayıları
sonrasıdır. Raporda boş ve tek sınıflı bölümler görünür. Çakışmayan 37 günlük
pencereler en erken olandan açgözlü seçilir. Ürünler arası bağımsızlık
ayrıca kanıt ister. `numerical_candidate` sayım engeli bulunmadığını belirtir.

## ML hazırlığı

ML akışı `app/ml` paketindedir. Tek salt okunur görüntüden etiket,
girdi, bölme ve deney ağsız yürür. Aynı görüntü, kod ve ortam aynı
çıktıları üretir. NumPy, scikit-learn ve LightGBM sürümleri için
`pyproject.toml` içindeki `ml` grubuna bak. Sıkı referans sayımı
[ML veri denetimindedir](#ml-veri-denetimi).

- [ML planı](../proje_plani.md#ml-hazırlığı-ve-ilk-deney-4046) ve [kalıcı kararlar](../proje_plani.md#5-kararlar)
- [Uygulama ve kabul geçmişi](gecmis.md#aşama-8-ml-gölge-mod-ve-tahmin-gösterimi)
- [Sadeleştirme öncesi ayrıntılı kayıt](arsiv/teknik_2026-11-23.md#ml-hazırlığı)

### Veri görüntüsü (`python -m app.ml snapshot`)

Toplama turu ve keşif çalışmıyorken proje kökünde kullanıcı terminalinden:

```powershell
$env:API_DATABASE_URL = "postgresql://fiyat_takip_api@localhost:5432/fiyat_takip"
.venv\Scripts\python.exe -m app.ml snapshot --output-dir "artifacts\ml_veri_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
$LASTEXITCODE
```

Parolayı `pgpass.conf` sağlar. Komut önce çıktı klasörünün henüz bulunmadığını,
okuma hesabını, migration uyumunu ve tamamlanmamış tur bulunmadığını
kontrol eder. Tek `REPEATABLE READ / READ ONLY` işlem (UTC, 5 saniye
sorgu sınırı) kullanır. Tarama kilidi yerine veritabanındaki `running`
kaydına bakar. `snapshot.json` yeniden okunur ve doğrulanır. Özet,
yolu ve SHA-256'yı, şema ve okuma anını, ürün/sayfa etkinliğini, tur
durumlarını, sayfa sonuçlarını ve Cimri kayıt/eksik fiyat sayılarını verir.

| Çıkış | Anlamı |
|---|---|
| 0 | Görüntü yazıldı, yeniden okunup doğrulandı. |
| 1 | Klasör var, adres tanımlı değil, okuma hesabı değil, şema hazır değil, bağlantı/sorgu ya da dosya hatası. Mesaj stderr'e `Görüntü alınmadı: …` diye yazılır. |
| 2 | Argüman hatası. |
| 3 | Tur sürüyor; klasör oluşturulmaz. Tur bitince yeniden çalıştırın. |

**Dosya.** `format_version=1` zarfı `payload` ve `sha256` alanlarını taşır.
Parmak izi, sıralı anahtarlı ve boşluksuz UTF-8 JSON içeriğine aittir.
Zaman UTC (`…Z`), fiyat tam sayı kuruştur. Ürün, platform, sayfa, tur,
sayfa sonucu ve Cimri satırları birincil anahtara göre sıralı ve tekildir.
Pasif ürün ve sayfalar, yarıda kalan turlar ve henüz kontrol edilmemiş
sayfalar görüntüde korunur. Satıcı, teklif adresi, ham hata, tur notu
ve bağlantı adresi görüntüye alınmaz.

Okuyucu zarfı, parmak izini, alanları ve tabloların bağlarını doğrular.
Turun sonuç satırı sayısı planlanan sayfa sayısıyla eşleşir. Fiyat yalnız
`offer` sonucunda bulunur. Sonuçlu satırın kontrol anı tur aralığında
olmalıdır. `running` tur ve geçersiz Cimri ürün bağı reddedilir. ML
modüllerinin komut dosyası dışında DB, ağ ve pazaryeri katmanı yüklememesi
`tests/test_ml_dataset.py` ile sınanır.

### Günlük seri ve etiketler (`python -m app.ml labels`)

Etiket komutu görüntü **klasörünü** ve parmak izini doğrular. İstanbul'da
görüntü anından önce kapanmış son güne kadar hesaplar. Kaynaklar ayrı
işlenir. Hesap tarihsel tur planlarını kullanır. Sonraki katalog,
eşleştirme ve etkinlik değişiklikleri geçmişi yeniden yazmaz.

```powershell
$mlLabelSnapshot = "artifacts\ml_veri_20261102_201315_398"
$mlLabelOut = "artifacts\ml_etiket_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
.venv\Scripts\python.exe -m app.ml labels --snapshot $mlLabelSnapshot --output-dir $mlLabelOut
$LASTEXITCODE
.venv\Scripts\python.exe tools/ml_label_check.py --snapshot $mlLabelSnapshot --labels-dir $mlLabelOut
$LASTEXITCODE
```

Çapraz kontrole `labels` çıkışı 0 ise geç. Her iki komut ağsız çalışır.
Yeni görüntü ayrı `snapshot` işlemidir.

**Kendi serimiz.** Yalnız zamanlanmış turlar, başlangıçlarına göre önceki
en yakın İstanbul 10:00/22:00 dilimine atanır. Tekrarlı, yarıda kalan ya da
kendi gününde bitmeyen dilim eksiktir. İlk gözlem, ürünün ilk gerçek fiyat
veya stoksuzluk cevabının nominal günüdür.

Başlangıç için aynı gün biten tekil 22:00 turunda ürünün bütün planlı
sayfaları `offer` veya `sold_out` dönmeli ve en az bir fiyat olmalıdır.
İlgili sayfada hata veya cevapsızlık gelecek günün minimumunu geçersiz
kılar. Gelecek minimumu için tek sağlam dilim yeterlidir. Bütün teklifler
stoksuzsa veya kullanılabilir turda ilgili sayfa planlanmamışsa minimum
NULL kalır. Kalite gerekçeleri duruma göre ayrı kaydedilir.

**Cimri:** ilk kayıtlı tarih geçmişi başlatır. Eksik tarih ve NULL fiyat
doldurulmaz. `day == captured_at` İstanbul tarihi olan kayıt yarım gündür;
görüntü daha sonra alınmış olsa bile fiyatı kullanılmaz. Ham kayıt fiyatı
günlük kanıtta kalır. Geçmiş ve gelecek boyunca birden fazla Cimri ürün
kimliği varsa pencere elenir.

**Örnek ve etiket:** fiyatı olan her geçerli başlangıç için geçmiş
`d−29…d`, gelecek `d+1…d+7`'dir. İlk gözlem günü birinci gündür; ilk uygun
başlangıç en erken `ilk gün + 29` olur. Geçmiş fiyat boşlukları satırı
otomatik elemez; 30 gün içindeki eksik başlangıç sayısı/oranı ve geçmiş
kapsam değişimleri kaydedilir. Başlangıcı olmayan gün `windows.jsonl`'a
girmez; gerekçesi `daily.jsonl` ve raporda kalır. Geçmişi henüz 30 gün
olmayan fiyatlı başlangıçlar tanılama için NULL etiketle saklanır.

Yedinci gelecek gün kapanmış ve en az altı günde güvenilir fiyat varsa
`100 × gelecek_minimum ≤ 95 × başlangıç` için etiket 1, aksi halde 0'dır.
Daha az gözlemde düşüş görülmüş olsa bile NULL'dır. Eşik tam sayı kuruşla
hesaplanır; eksik fiyat taşınmaz veya sıfır yapılmaz.

Kendi verimizde `primary`, `y_sabit`'tir: başlangıç akşam turunda planlanan
sayfa kümesi sabitlenir. Gelecekte yalnız bu kümeden o gün planlanan
sayfalar kullanılır; onların bütün cevapları aranır. Sonradan eklenen
sayfa bu minimuma girmez. Planlanmayan/eski pasif sayfanın fiyatı taşınmaz;
hiç ilgili sayfa planlanmadıysa o gün eksiktir. `tracked`, `y_izlenen`'dir:
o gün izlenen bütün sayfalar kullanılır. Gözlenen gün sayıları ve uygunluk
gerekçeleri iki hedef için ayrı tutulur. Cimri'de `primary` günlük
minimumdur, `tracked` NULL'dır. Kapsam fark oranının paydası yalnız iki
etiketi de hesaplanabilen pencerelerdir; olumlu satır sayısı bağımsız olay
sayısı değildir.

**Dosyalar.** `daily.jsonl` günlük fiyat, tur ve kalite gerekçelerini,
`windows.jsonl` başlangıç kapsamını, geçmişi ve iki hedefin gelecek
kanıtını taşır. `strict_windows.jsonl` tam 37 gün ve sabit kapsam
referansıdır. `report.json` ve `report.md` ürün, kaynak ve kapsam farkı
özetidir. Manifest (biçim 1, kural 2) görüntü SHA-256'sı ve beş çıktının
parmak izleriyle en son yazılır. Yarım veya uyuşmayan çıktı yeni klasörle
tekrarlanır. Aynı görüntü aynı dosyaları üretir.

`primary`, `tracked`, `target_end` ve `future_scope_change_days` gelecek
bilgisi taşır ve model girdilerine alınmaz.

**Sıkı çapraz kontrol.** `ml_label_check.py` aynı görüntüde eski
`own_series`, `market_series` ve `windows_for` hesaplarıyla anahtar,
fiyat, etiket ve gerekçeleri karşılaştırır. İki tarafta Cimri yarım günü
NULL yapılır. Eski envanterin kullanılmayan URL alanı `None` kalır.
Çapraz kontrol sıkı pencereye uygulanır. 6/7 kuralı ayrı sonuç verir.

| Çıkış | `labels` | `ml_label_check.py` |
|---|---|---|
| 0 | Dosyalar yazıldı, parmak izleri doğrulandı; sıfır etiket olabilir. | Bütün sıkı pencere kayıtları eşleşti. |
| 1 | Görüntü, mevcut klasör, veri veya dosya hatası. | Görüntü/manifest/dosya hatası ya da sıkı sonuç uyuşmazlığı. |
| 2 | Argüman hatası. | Argüman hatası. |
| 130 | Kullanıcı durdurdu. | Kullanıcı durdurdu. |

Yapay testler komutların ağ/DB açmadığını doğrular. Gerçek görüntüyle
yapılan çapraz kontrolün sonuçları
[uygulama geçmişindedir](gecmis.md#aşama-8-ml-gölge-mod-ve-tahmin-gösterimi).

### Model girdileri (`python -m app.ml features`)

Komut aynı görüntüyü doğrular ve `labels` ile ortak seri katmanını
kullanır. Kendi serisinde 22:00 başlangıcı, Cimri'de yarım günü
maskelenmiş fiyat kullanılır. Takvimi görüntü belirler. Girdiler
etiketler, canlı katalog ve çalışma anından bağımsız hesaplanır.

```powershell
$mlFeatureSnapshot = "artifacts\ml_veri_20261102_201315_398"
$mlFeatureOut = "artifacts\ml_girdi_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
.venv\Scripts\python.exe -m app.ml features --snapshot $mlFeatureSnapshot --output-dir $mlFeatureOut
$LASTEXITCODE
```

Çıkış 0 rapor yolunu, kaynağa göre satır ve tanınmayan aile sayılarını
ve doğrulama sonucunu verir. Geçerli başlangıç yoksa sıfır satır başarıdır.
Çıkış 1 girdi, dosya veya mevcut klasör hatası, 2 argüman hatası, 130
kullanıcı kesmesidir.

**Satır şeması.** `metadata`, ürün kimliği ve anahtarı, kaynak,
başlangıç günü ve anı ile ayı taşır. `anchor_at` kendi serimizde akşam
turunun UTC bitişi, Cimri'de NULL'dır. Etiket dosyası zamanı `+00:00`,
girdi dosyası `Z` ile yazabilir. Bölmede birleştirme ürün/kaynak/gün
anahtarıyla yapılır. Ay ve ürün anahtarı çekirdek girdilere eklenmez.

`features` sabit alanlıdır (Pydantic `strict`, `extra=forbid`). Kaynak,
kimlik, ham fiyat, tarih ve gelecek alanları çekirdekten çıkarılır.
Eksikler NULL, sayılar sonlu olmalıdır. Kodlama, ölçekleme ve eksik
doldurma modelin eğitim aşamasına aittir.

`d` başlangıç günü ve `p(d)` geçerli başlangıç fiyatı olmak üzere:

| Çekirdek alan | Hesap ve eksik davranışı |
|---|---|
| `log_return_1d`, `log_return_7d`, `log_return_14d`, `log_return_30d` | `ln(p(d)/p(d−k))`. Tam lag tarihinde fiyat yoksa NULL; yakın tarihe geçilmez. |
| `ratio_min_7d` | `p(d)/min(p(d−6…d))`; mevcut fiyatlarla, başlangıç dahil. |
| `ratio_min_30d` | `p(d)/min(p(d−29…d))`; mevcut fiyatlarla. |
| `ratio_mean_30d` | `p(d)/ortalama(p(d−29…d))`; mevcut fiyatlarla. |
| `volatility_30d` | İki ucu da `d−29…d` içinde fiyatlı ardışık takvim günlerinin log değişimlerinin örnek standart sapması; en az iki geçiş gerekir, yüzdeyle çarpılmaz. |
| `change_count_30d` | Aynı geçerli geçişlerde fiyatın farklı olduğu durumların sayısı; hiç geçiş yoksa NULL. |
| `days_since_drop_30d` | Aynı geçişlerde `100×sonraki ≤ 95×önceki` olan son düşüşün bitişinden bugüne gün. Geçiş var/düşüş yoksa 31, geçiş yoksa NULL. |
| `drop_observed_30d` | Geçerli geçişlerde uygun düşüş görüldüyse true, görülmediyse false; hiç geçiş yoksa NULL. |
| `history_days` | İlk kaynak gözleminden başlangıca kadar takvim günü sayısı, başlangıç dahil; 30'a kırpılmaz. İlk gözlem tanımı 4.2 serisiyle aynıdır. |
| `missing_ratio_30d` | `d−29…d` içindeki eksik başlangıç fiyatı sayısı / 30. |
| `weekday` | Kategori dizgisi: Pazartesi `"0"`, Pazar `"6"`. |
| `brand`, `family`, `segment`, `capacity` | Marka, nesil, sürüm ve GB kapasitesi kategorileri; kapasite de dizgidir (örn. `"128"`). |

Minimum ve ortalama için tek fiyat yeterlidir. Takvim boşlukları
geçiş kurulmasını engeller. `d−30` sadece 30 günlük lag'e girer. Oynaklık,
değişim ve 30 günlük özet penceresi `d−29…d` aralığıdır. Cimri'de diğer
kaynak ürün kimliklerinin fiyatı NULL olur. Kendi kapsam değişikliği
geçmiş fiyatı silmez. API istatistik eşikleri bu hesaba uygulanmaz.

**Aile ve segment.** iPhone nesli, Galaxy S/A numarası, Xiaomi T ve
Redmi Note numarası ile POCO X numarası aileyi verir. Pro/Pro Max/Plus/mini/Air,
Ultra/FE/Plus/Edge, Pro/Pro Plus ve POCO Pro ilgili ailenin segmentleridir.
Redmi'nin son 4G/5G eki yalnız bu kategoride çıkarılır. Ek yoksa `standard`,
desen tanınmazsa marka + tam model ve `unknown` yazılır. Ürün kimliği ve ağ
kuralları bu kategorilerden bağımsızdır.

**Zaman sınırı.** Hesap en çok `d−30…d` fiyatlarını okur. Kendi serimizde
geçmiş turun bitişi başlangıç anını aşamaz. 0, 1 veya NULL etiketli bütün
geçerli başlangıçlar girdi oluşturur. Cimri'nin tarihsel ölçüm ve ilk
erişilebilirlik saati bilinmediğinden bu girdi tarihsel erişim kanıtı
sağlamaz.

**Dosyalar.** `features.jsonl` sıralı, tekil ve tipli satırlar,
`feature_schema.json` alan ve hesap sözleşmesi, `report.json` ve
`report.md` kaynak/ürün dökümüdür. En son yazılan manifest biçim ve kural
sürümü 1, giriş SHA-256'sı ve dört çıktı parmak izi taşır. Yazılan dosyalar,
şema, satır tipleri ve sıra tekrar doğrulanır. Yarım veya parmak izi
uyuşmayan çıktı yeni klasörle tekrarlanır.

**Sızıntı denetimi.** Yapay testler gelecek verisini değiştirip ortak
geçmiş girdilerin sabit kaldığını, geçmiş fiyat değiştirilince ilgili
girdinin değiştiğini sınar. Anahtarlar aynı görüntünün geçerli etiket
başlangıçlarıyla karşılaştırılır. `features` komutu etiket, DB, ağ ve
eğitim modüllerini yüklemeden çalışır.

### Zaman bölmesi ve ölçütler (`python -m app.ml split`)

Komut etiket ve girdi klasörlerini ağsız birleştirir. Manifestleri,
kural/şema sürümlerini, dosya parmak izlerini, ortak görüntü SHA-256'sını ve
başlangıç anahtarlarının tekil, sıralı ve birebir eşleşmesini doğrular.
Hedef sonu başlangıç + 7 gündür. Girdi uyuşmazlığında çıktı oluşmaz.

```powershell
$mlSplitLabels = "artifacts\ml_etiket_20261102_201553_161"
$mlSplitFeatures = "artifacts\ml_girdi_20261102_201744_673"
$mlSplitOut = "artifacts\ml_bolme_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
.venv\Scripts\python.exe -m app.ml split --labels-dir $mlSplitLabels --features-dir $mlSplitFeatures --output-dir $mlSplitOut
$LASTEXITCODE
```

Çıkış 0; rapor yolu, ortak SHA-256, durum, kat ve başlangıç/saklı test
kayıt sayıları beklenir. `limited` (sınırlı), hesaplama hatası değil,
veride uygunluk engeli olduğunu belirtir. Çıkış 1 dosya/veri/mevcut klasör
hatası, 2 argüman hatası, 130 kullanıcı kesmesidir. Test açma seçeneği yoktur.

**Ana bölme.** Eğitim havuzu 0 veya 1 etiketli Cimri satırlarıdır. NULL
girdi dışlama nedeni değildir. Tekil uygun günlerin ilk `N×70//100`'ü
eğitim, `N×85//100`'e kadarı doğrulama, kalanı `test_reserved` olur.
Aynı tarihteki ürünler aynı bölümdedir. Kendi serimiz değerlendirme veya
etiketsiz, etiketsiz Cimri başlangıçları `unlabelled` olarak ayrılır.

**Purge.** Önceki bölümde hedef sonu, sonraki bölümün başlangıcından
kesinlikle önce olmalıdır. Erken düşüş hedef sonunu kısaltmaz. Ana bölmede
çıkarılanlar `purged_train` ve `purged_validation` olur. Girdi
pencerelerinin örtüşmesi tek başına dışlama nedeni değildir.
`first_anchor` ve `last_anchor` nominal sınırlar, rapor sayıları temizleme
sonrası üyelerdir. Kesin üyeler `assignments.jsonl` içindedir.

**Katlar.** İlk %85, saklı test sınırına göre temizlenir. Uygun aralıktaki
son dört tam takvim ayı, boş aylar dahil seçilir. Eğitim geçmişi genişler.
Kalibrasyon doğrulama ayından önceki 30 gündür. Eğitim, kalibrasyon ve
doğrulama hedef sonları sırasıyla kalibrasyon, doğrulama ve sonraki ay
başlangıcından önce olmalıdır. Katlar ana %70 kesimine göre kurulmadığından
uygun `purged_train` satırı bir kata girebilir. Dört tam ay olmadığında
veya bir dilim boş/tek sınıflı olduğunda kat durumu sınırlıdır. Bölme
sınırları ve eşikler sabittir.

**Saklı test.** Bölme raporu yalnız tarih aralığını ve kayıt sayısını,
atamalar anahtar ve rolü verir. `evaluation_targets` olağan doğrulama,
kat doğrulaması veya kendi değerlendirmesini seçer. Saklı test, sınırda
temizlenen satır ve bozuk kat üyeliği reddedilir. Genel puanlama
`test_reserved` rolünü kabul etmez.

**Ölçüt arayüzü.** `Target` anahtar, 0/1 etiket, rol, marka ve aileyi,
`Probability` aynı anahtar ve sınıf 1 olasılığını taşır.
`score_predictions(targets, probabilities, references, role=...)`
dizileri sırayla eşleştirir ve geçersiz/tekrarlı anahtarı, etiketi veya
[0,1] dışında veya sonlu olmayan olasılığı reddeder. Her kat ve birleşik puanlamadaki her
satır kendi eğitim diliminin R0 oranını kullanır.

| Alan | Anlamı ve sınırı |
|---|---|
| `average_precision` | scikit-learn average precision; trapez PR alanı değil. Taban olumlu oranla birlikte; boş/tek sınıfta NULL. |
| `brier` | `mean((p−y)^2)`, ikili [0,1] ölçeği. |
| `log_loss` | Float64, labels=[0,1]; yalnız bu hesapta olasılıklar makine epsilon sınırlarına kırpılır. |
| `reference_brier`, `brier_skill` | R0 vektörünün Brier kaybı ve `1−model_Brier/R0_Brier`; sıfır referansta skill NULL ve gerekçe. |
| `calibration` | On eşit genişlikli kova; son kova 1'i içerir. Sayı/ortalama tahmin/gerçekleşen oran; boşta ortalamalar NULL, 20'den az kayıtta düşük destek. |
| `breakdowns`, `macro` | Marka/aile/ürün kırılımı; yeterli ürünlerin eşit ağırlıklı ortalaması ve ölçüt başına kapsama. Ana sonuç bütün satırları ağırlıklandırır. |

Boş toplulukta puanlar NULL'dır. Tek sınıfta Brier ve log loss
hesaplanabilir. AP ve model seçimi için iki sınıf gerekir.

**Olumlu pencere kümeleri.** Aynı ürün ve kaynakta çakışan olumlu
`[d+1,d+7]` aralıkları ortak uç ve zincirleme örtüşme dahil birleştirilir.
Beşten az kümede skor yerine `insufficient_clusters` ve destek sayısı
yazılır. Küme sayısı bağımsız düşüş sayısından farklıdır. Makro ortalamada
yalnız yeterli ürünler kullanılır ve ölçüt başına kapsama yazılır.

**Güven aralığı.** `paired_bootstrap`, aynı doğrulama hedeflerinde
modelleri eşleştirir. 14 takvim günlük hareketli blok, 2.000 tekrar,
tohum 42 ve %95 güven düzeyi kullanılır. Boş günler korunur ve bloklar
eşit olasılıkla başlar. Örnek özgün takvim gün sayısına kırpılır, sonra
bu günlerdeki tüm ürünler alınır. İki model aynı örnekleri kullanır.
Tek sınıflı tekrarlar atlanır. En az 28 takvim günü ve 1.800 geçerli tekrar
gerekir. Aralık, AP farkının doğrusal %2,5 ve %97,5 yüzdelikleridir.
Bölme komutu planı çıkarır. Tahmin ve bootstrap ölçümü deneyde yapılır.

**Dosyalar.** `assignments.jsonl` anahtar ve rolü, `folds.json` kat
üyelerini ve dönemleri, `metrics_schema.json` hesap şemasını,
`report.json`/`report.md` uygunluğu taşır. En son yazılan manifest
biçim/bölme/ölçüt sürümü 1, ortak görüntü SHA-256'sı, iki giriş manifesti
ve beş çıktı parmak izi taşır. Dosya şeması, tekil anahtarlar, kat sınırı
ve saklı test sözleşmesi yeniden doğrulanır. Yarım çıktı yeni klasörle
tekrarlanır. X/y kopyası veya saklı test sınıf dağılımı üretilmez.

### Modeller ve deney (`python -m app.ml experiment`)

Komut etiket, girdi ve bölme kanıtlarını okuyarak her hazır katta
yeniden eğitim yapar. Puanlar, dört ileri yürüyen katın doğrulama
aylarına aittir. Ana %15 doğrulama, saklı test ve kendi serimiz ayrı
tutulur.

**Kanıt zinciri.** Giriş manifestleri, parmak izleri, ortak görüntü ve
başlangıç anahtarları doğrulanır. `assignments.jsonl`, `folds.json`,
`report.json` ve `report.md` yeniden üretilen planla bayt bayt,
`metrics_schema.json` kodun şemasıyla eşleşmelidir. Bu denetim
eğitim ve çıktıdan önce çalışır. Saklı test, etiketsiz, kendi kaynaklı,
girdisi eksik veya kat/purge sınırını aşan üye reddedilir.

```powershell
$mlExperimentLabels = "artifacts\ml_etiket_20261102_201553_161"
$mlExperimentFeatures = "artifacts\ml_girdi_20261102_201744_673"
$mlExperimentSplit = "artifacts\ml_bolme_20261102_202101_484"
$mlExperimentOut = "artifacts\ml_deney_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
$mlExperimentTimer = [System.Diagnostics.Stopwatch]::StartNew()
.venv\Scripts\python.exe -m app.ml experiment --labels-dir $mlExperimentLabels --features-dir $mlExperimentFeatures --split-dir $mlExperimentSplit --output-dir $mlExperimentOut
$mlExperimentExit = $LASTEXITCODE
$mlExperimentTimer.Stop()
$mlExperimentRun = [ordered]@{
    output_dir = $mlExperimentOut
    exit_code = $mlExperimentExit
    elapsed_seconds = $mlExperimentTimer.Elapsed.TotalSeconds
}
$mlExperimentRun | ConvertTo-Json | Set-Content -Encoding UTF8 ($mlExperimentOut + '_run.json')
Write-Output "Cikis kodu: $mlExperimentExit"
Write-Output "Sure (saniye): $($mlExperimentTimer.Elapsed.TotalSeconds)"
Write-Output "Klasor: $mlExperimentOut"
```

Kabuk süre ve çıkışı `ml_deney_<tarih-saat>_run.json` dosyasına kaydeder.
Bu dosya deney manifestinin dışındadır. Terminal uyarıları ayrı okunur.

Çıkış 0; rapor yolu, görüntü SHA-256, değerlendirilen kat ve doğrulama satırı
sayısı, ham/kalibre modellerin AP/Brier/log loss puanları ve seçim önerisi
beklenir. Çıkış 0 model başarısı anlamına gelmez; seçim sonucu
“karşılanmadı” veya “değerlendirilemedi” olduğunda da komut başarılıdır.
Çıkış 1 veri/dosya/eksik ML bağımlılığı/mevcut klasör hatası, 2 argüman
hatası, 130 kullanıcı kesmesidir. Test açma veya ayar arama seçeneği yoktur.

**Eğitim ve ön işlemler:** bütün modeller aynı çekirdek girdileri kullanır;
ay, ürün anahtarı/kimliği ve kaynak bilgisi modele verilmez. Her katta
modeller ve öğrenilen dönüşümler yalnız eğitim diliminden, kalibratörler
ayrı 30 günlük kalibrasyon diliminden öğrenir. Doğrulama etiketleri eğitim
ve kalibrasyona girmez.

| Model | Bugünkü kural |
|---|---|
| R0 | Eğitim diliminin olumlu oranını her satıra verir; kalibre edilmez. |
| R1 | `ratio_min_30d` için üst sınırları dahil 1,00 / 1,02 / 1,05 / 1,10 ve üzeri kovalar. Her kovada `(olumlu + 20 × R0) / (satır + 20)`; boş kova R0'a döner. |
| R2 | Sayısal eksikler eğitim medyanıyla doldurulur, eksiklik göstergeleri eklenir ve ölçeklenir; tamamen boş sütun korunur. Kategoriler one-hot, bilinmeyen kategori yok sayılır. L2 lojistik regresyon: C=1, lbfgs, en çok 1000 yineleme. |
| LightGBM | Sayısal eksikler NaN kalır; kategoriler eğitimden öğrenilen kodlara, bilinmeyenler NaN'a dönüşür. İkili amaç, 200 ağaç, öğrenme oranı 0,05, 15 yaprak, yaprakta en az 100 satır, L2=1; sınıf ağırlığı yok. Tek iş parçacığı, tohum 42, `deterministic=True`, `force_row_wise=True`. |

Platt sigmoid kalibrasyonu için R1, R2 ve LightGBM `FrozenEstimator`
ile sabitlenir. Olasılıklar `[1e-9, 1−1e-9]` aralığına kırpılıp log-odds'a
çevrilir. Kalibratör ayrı dilimde öğrenir. Eğim, kesişim ve sıralamanın
korunması raporlanır. Ham ve kalibre yedi vektör puanlanır. Ayarlar
`models.py` içindeki `MODEL_RULES` ve deney manifestindedir. Hiperparametre
araması yapılmaz.

**Ölçüm ve seçim önerisi:** kat puanları ve birleşik doğrulama puanları,
taban olumlu oranı, R0'a göre Brier skill, güvenilirlik kovaları,
marka/aile/ürün kırılımları ve yeterli ürünlerin makro ortalamaları
hesaplanır. Her satır kendi katının R0 olasılığını taşır. AP farkının
yukarıda tanımlanan tarih bloklu güven aralığı üç çiftte hesaplanır:
LightGBM + Platt − R2 + Platt (seçim), R1 + Platt − R0 ve
R2 + Platt − R1 + Platt (bilgi).

LightGBM + Platt için dört hazır kat, AP farkı güven aralığının alt sınırının
0'dan büyük olması, birleşik Brier ve log loss değerlerinin R2 + Platt'tan
büyük olmaması birlikte aranır. Sonuç şu sırayla belirlenir:

| Durum | Sonuç |
|---|---|
| Dört kat hazır değil | `not_evaluable` — Değerlendirilemedi. |
| Dört kat hazır, hesaplanan koşullardan en az biri sağlanmıyor | `not_met` — Karşılanmadı; başka koşulun aralığı/puanı NULL olsa bile. |
| Dört kat hazır, sağlanmayan koşul yok, en az bir koşul hesaplanamıyor | `not_evaluable` — Değerlendirilemedi. |
| Bütün koşullar sağlanıyor | `met` — Karşılandı. |

NULL ölçüm gerekçesiyle saklanır. Seçim önerisi `decides_model=False` ve
`model_frozen=False` olarak raporlanır. Son model ve saklı test için
[dondurma adımlarını](#model-dondurma-ve-saklı-test-python--m-appml-freeze-final-test) izle.

**Çıktılar:** yeni klasöre yazılır; var olan klasöre dokunulmaz.

| Dosya | İçerik |
|---|---|
| `predictions.jsonl` | Yalnız hazır katların doğrulama anahtarı, ayı, etiketi ve yedi model olasılığı. Eğitim, kalibrasyon, saklı test ve kendi serimiz tahminleri yazılmaz. |
| `models.json` | Kat başına R0 oranı, R1 kovaları, R2 katsayıları/yakınsama bilgisi, LightGBM ağaç sayısı/kazanç önemleri ve Platt katsayıları. Yeniden yüklenebilir eğitilmiş model dosyası değildir. |
| `report.json` | Kat ve birleşik puanlar, bütün kırılımlar, güvenilirlik kovaları, güven aralıkları, seçim koşulları/gerekçeleri, kural ve kütüphane sürümleri. |
| `report.md` | Puanlar, kat AP'leri, fark aralıkları, seçim sonucu, güvenilirlik tabloları, ürün makro/marka özeti ve sınırların Türkçe görünümü. |
| `manifest.json` | En son yazılan tamamlanma kaydı; görüntü SHA-256, etiket/girdi/bölme manifestlerinin SHA-256 değerleri, bölme/ölçüt/deney kuralları, kütüphane sürümleri ve dört çıktı parmak izi. |

Okuyucu parmak izlerinin yanında tahminlerin hazır kat üyeleriyle tam
eşleşmesini, etiketleri ve [0,1] olasılıklarını doğrular. Rapor
bayrakları dondurma, saklı test ve kendi seri puanlamasının deney
kapsamı dışında olduğunu gösterir. Yarım deneme yeni klasör gerektirir.

#### Gerçek deneyin ilk değerlendirmesi

3 Kasım Cimri deneyinde LightGBM + Platt'ın AP farkı güven aralığı
sıfırı içerdi ve seçim sonucu `not_met` oldu. Ön kayıt kuralıyla
[R2 + Platt donduruldu](#4-kasım-2026-dondurma-ön-kaydı).

Birleşik R0, kat başına eğitim oranını taşır. Kat içi sıralamayı koruyan
kalibrasyon katlar arası ölçeği ve birleşik AP'yi değiştirebilir.
Markalar arası AP, farklı taban oranlarıyla yorumlanır. Ürün makrosu
yalnız destekli ürünleri kapsar. Bu ilk ölçüm Cimri dönemine aittir.
[Deney kayıtları, puanlar ve yorumlar](arsiv/teknik_2026-11-23.md#gerçek-deneyin-ilk-değerlendirmesi)


### Model dondurma ve saklı test (`python -m app.ml freeze`, `final-test`)

İki komut da etiket, girdi ve bölme klasörlerini ağsız okur.
Çıkış 0 başarı, 1 girdi/dosya/veri veya mevcut klasör hatası, 2 argüman
hatası, 130 kullanıcı kesmesidir. `freeze` model seçimini deneyden
türetir. `final-test` için dondurulan modelin ön kayıtlı SHA-256 değeri
gerekir.

| Deney seçim sonucu | Dondurulan model |
|---|---|
| `met` | LightGBM + Platt |
| `not_met` | R2 + Platt (en güçlü referans) |
| `not_evaluable` | Dondurulmaz; çıkış 1. |

T, saklı testin ilk günüdür. Geliştirme satırı, ana bölmede eğitim,
doğrulama veya `purged_train` rolündeki etiketli Cimri satırıdır ve hedef
sonu T'den öncedir. Saklı test, `purged_validation`, etiketsiz ve kendi
kaynaklı üyeler geliştirme diliminde reddedilir.

| Dilim | Kural |
|---|---|
| Eğitim | Geliştirme satırı, başlangıç < T − 30 gün ve hedef sonu < T − 30 gün. Doğrulama dönemi de buna girer, bu yüzden dondurulan model kat modellerinden daha geniş veriyle kurulur. |
| Kalibrasyon | T − 30 gün ≤ başlangıç < T ve hedef sonu < T. |

R0 ve seçilen model, kat modelleriyle aynı `fit_models` ve `MODEL_RULES`
ayarlarıyla kurulur. Eğitim dilimi yukarıdaki son model dilimidir.

#### `freeze`

```powershell
$mlFreezeOut = "artifacts\ml_model_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
.venv\Scripts\python.exe -m app.ml freeze --labels-dir <ETIKET> --features-dir <GIRDI> --split-dir <BOLME> --experiment-dir <DENEY> --output-dir $mlFreezeOut
```

Önce `experiment` bölümündeki kanıt zinciri doğrulanır ve bölme
bayt bayt yeniden üretilir. Deney klasörü doğrulandıktan sonra model
seçilir. Yalnız geliştirme dilimleri kullanılır. Model yazımının sonunda
aşağıdaki yükleme denetimi yapılır. Manifest en son yazılır.

| Dosya | İçerik |
|---|---|
| `model.pkl` | Dondurulan model ve R0 (pickle, protokol 5). |
| `model.json` | Seçimin gerekçesi (deney sonucu ve değerleri), dilim sınırları ve sayıları, R0 oranı, R2 katsayıları/yakınsama veya LightGBM önemleri, Platt eğimi/kesişimi ve sıralamanın korunup korunmadığı, deneydeki birleşik doğrulama puanları. |
| `calibration_predictions.jsonl` | Kalibrasyon dilimindeki anahtar, etiket, R0 ve model olasılıkları; yükleme denetiminde kullanılır. |
| `report.md` | Türkçe özet. |
| `manifest.json` | Görüntü SHA-256, etiket/girdi/bölme manifestlerinin SHA-256 değerleri, deney manifestinin SHA-256'sı, bölme/ölçüt/model/son kuralları, kütüphane sürümleri, dosya parmak izleri ve `test_opened=false`. |

Çıktıda model, dilim sayıları, Platt sıralama bilgisi ve ön kayda
girecek **model manifest SHA-256** değeri bulunur. Sıralamanın korunmaması
raporlanır ve çıkış 0 kalır. Aynı girdi, kod ve ortam `model.pkl` dahil
aynı baytları üretir.

#### 4 Kasım 2026 dondurma ön kaydı

Deney seçim koşulu karşılanmadığı için **R2 + Platt** donduruldu. Bu
ön kayıt saklı test açılmadan Git'e gönderildi ve model seçimi bu
SHA-256 ile sabitlendi. Model klasörü
`artifacts/ml_model_20261104_104617_170/` (Git dışında).

Ön kayıtlı **model manifest SHA-256** değeri aşağıdadır.

```text
89c819ed7c9f5eaf0dcc11c8f403a4439f53cfad2527d973646b71474fba4cf2
```

Kanıtlar: `artifacts/ml_etiket_20261102_201553_161/`,
`artifacts/ml_girdi_20261102_201744_673/`,
`artifacts/ml_bolme_20261102_202101_484/` ve
`artifacts/ml_deney_20261103_135053_501/`.

| Dilim | Satır | Olumlu | İlk başlangıç | Son başlangıç | En geç hedef sonu |
|---|---:|---:|---|---|---|
| Eğitim | 14.923 | 1.517 | 7 Kasım 2025 | 27 Temmuz 2026 | 3 Ağustos 2026 |
| Kalibrasyon | 1.254 | 148 | 4 Ağustos 2026 | 26 Ağustos 2026 | 2 Eylül 2026 |

Saklı test 3 Eylül 2026'da başlar. R2 yakınsadı, Platt sıralamayı
korudu ve 1.254 kalibrasyon kaydının olasılığı yeniden üretildi.
`test_opened=false`. Python 3.13.15, NumPy 2.5.3, scikit-learn 1.9.1 ve
LightGBM 4.7.0 sürümleri manifestte kayıtlıdır.
[Ön kaydın ayrıntılı kanıtı](arsiv/teknik_2026-11-23.md#4-kasım-2026-dondurma-ön-kaydı)


#### Model yükleme (pickle güvenliği)

`load_frozen_model` sırayla şu denetimleri yapar.

1. Beklenen manifest SHA-256 değeri 64 onaltılık hanedir ve
   `manifest.json` parmak iziyle eşleşmelidir.
2. Biçim, tamamlanmış durum, görüntü ve etiket/girdi/bölme manifestleri,
   kurallar, model adı ve dosya kümesi uyuşmalıdır. `test_opened=false`
   ve Python, NumPy, scikit-learn, LightGBM sürümlerinin birebir eşitliği
   aranır.
3. Dört dosyanın parmak izi, `model.json` seçim sonucu ve model
   eşleşmesi doğrulanır. Kalibrasyon sıralı ve tekildir. Saklı test
   anahtarı reddedilir.
4. Bu denetimlerden sonra pickle açılır ve beklenen sınıf doğrulanır.
5. Kanıttan kurulan kalibrasyon diliminde anahtar, etiket ve olasılıklar
   kayıtla birebir eşleşmelidir.

Sürüm değişirse yükleme reddedilir. Yeniden dondurma yeni model ve SHA-256
üretir ve ayrı kullanıcı kararı gerektirir. Gölge çalışması mevcut
model ve sürümleri kullanır.



#### `final-test`

```powershell
$mlFinalSha = "<ön kayıtta yazılan model manifest SHA-256>"
$mlFinalOut = "artifacts\ml_son_test_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
.venv\Scripts\python.exe -m app.ml final-test --labels-dir <ETIKET> --features-dir <GIRDI> --split-dir <BOLME> --model-dir <MODEL> --expected-model-sha256 $mlFinalSha --output-dir $mlFinalOut
```

Komut yeni çıktı klasörü, kanıt zinciri ve ön kayıtlı SHA-256
kontrolünden sonra modeli açar. Hata olursa çıkış 1 ile saklı testten
önce durur. Yalnız bölme raporundaki sayıyla eşleşen etiketli Cimri test
satırları alınır. `score_reserved_test` ve `reserved_test_bootstrap`
yalnız saklı test rolünde model ve R0'ı puanlar. AP, Brier, log loss,
Brier skill, kovalar, kırılımlar, makro ortalama ve 14 günlük bloklarla
%95 AP farkı aralığı hesaplanır.

**Okuma koşulları.** Brier skill > 0 ve AP farkı güven aralığının alt
sınırı > 0 birlikte aranır. Hesaplanan bir koşul sağlanmazsa `not_met`,
böyle bir koşul yokken eksik hesap varsa `not_evaluable`, ikisi sağlanırsa
`met` olur. Rapor `decides_model=false` ve `model_changed=false` taşır.
Geçerli raporda komut çıkışı 0'dır.

| Dosya | İçerik |
|---|---|
| `predictions.jsonl` | Yalnız saklı test anahtarları, etiket, R0 ve model olasılığı. |
| `report.json` | Kurallar, model manifest SHA-256, puanlar, aralık, okuma sonucu, deneydeki doğrulama puanları; `test_opened=true`, `own_source_scored=false`, `model_changed=false`. |
| `report.md` | Türkçe özet: puanlar, fark aralığı, okuma koşulları, doğrulama aylarıyla yan yana tablo, güvenilirlik, makro/marka, sınırlar. |
| `manifest.json` | En son yazılan tamamlanma kaydı; `test_opened=true`, model manifest SHA-256 ve dosya parmak izleri. |

Yazım sonrası anahtarlar ve etiketler saklı test üyeleriyle birebir
eşleşmeli, olasılıklar [0,1] aralığında ve rapor bayrakları tutarlı olmalıdır.

**Tek açılış işletim kuralıdır.** Ön kayda alınan SHA-256 testten önce
Git'te korunur. `final-test` komutu teknik olarak aynı çıktıyı yeniden
üretebilir. Saklı testi yeniden çalıştırma. Model veya ayar seçimi
geliştirme verisiyle yapılır. Yaklaşık sekiz haftalık Cimri dönemindeki 14 günlük blok
sayısı sınırlıdır. Örtüşen pencereler bağımsız düşüş sayısını vermez.
Kendi serimiz gölge modda değerlendirilir. Doğrulama puanları ise
farklı eğitim dilimindeki kat modellerine aittir.


#### 4 Kasım 2026 saklı test sonucu

Saklı test, [ön kayıtlı modelle](#4-kasım-2026-dondurma-ön-kaydı)
bir kez açıldı. Brier skill ve AP farkı aralığının alt sınırı pozitifti.
Okuma koşulu `met` oldu. Dosya bütünlüğü, üyelik, ölçütler ve güven
aralığı kayıtlı olasılıklardan doğrulandı. Kanıt klasörü
`artifacts/ml_son_test_20261104_112007_023/`. Kapsam ve puanlar
[README'dedir](../README.md#-güncel-kapsam).

Ürün düzeyi ve POCO marka kırılımı için olumlu küme desteği yetersizdi.
0,2–0,3 ve 0,3–0,4 kovalarında gerçekleşme ortalama tahminden yüksekti.
Sonuç bu Cimri dönemiyle sınırlıdır. Kendi kaynağımızda gösterim
[ayrı gölge kapısına](#gölge-değerlendirmesi-python--m-appml-shadow-evaluate)
bağlıdır.
[Saklı testin ayrıntılı kanıtı](arsiv/teknik_2026-11-23.md#4-kasım-2026-saklı-test-sonucu)


### Gölge mod tahmin kaydı (`python -m app.ml shadow-predict`)

Komut [dondurulan modelle](#4-kasım-2026-dondurma-ön-kaydı) kendi
serimizde sonraki 7 günde en az %5 fiyat düşüşü olasılığını kaydeder.
Tahmin dosyalarını değerlendirme `shadow-evaluate`, günlük üretim
`shadow-daily` ile yapılır. `shadow-predict` yalnız görüntü klasöründen
ağsız çalışır. Tarama kilidini almadan, aktif tur sırasında da çalışabilir.
[Gölge mod planı](../proje_plani.md#gölge-mod-kalan-sıra-6-4-kasım-planı)

```powershell
$mlShadowOut = "artifacts\golge_deneme_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
.venv\Scripts\python.exe -m app.ml shadow-predict --snapshot <GORUNTU_KLASORU> --output-dir $mlShadowOut
$LASTEXITCODE
```

`--snapshot` bir [veri görüntüsü](#veri-görüntüsü-python--m-appml-snapshot)
klasörüdür; `--output-dir` yeni bir klasördür. İsteğe bağlı `--config`
(varsayılan `config/shadow.json`) ve `--records-dir` (varsayılan ayardaki
`records_dir`, yani `data/ml/golge`) verilebilir.

**Model.** `load_experiment_inputs` etiket, girdi ve bölmeyi,
`load_frozen_model` ön kayıtlı SHA-256, dosya parmak izleri, kütüphane
sürümleri ve kalibrasyonun yeniden üretimini doğrular. Varsayılan ayar
`data/ml/golge/kanitlar/{labels,features,split,model}/` altında orijinal
kanıtların birebir kopyalarını bekler. Eksik veya değişmiş kanıt
çıkış 1 verir.

**Satırlar.** `feature_rows` ile `start_day` ve sonrasındaki kayıtsız
başlangıçlar için tek satır üretilir. Son gün, görüntü anından önceki
kapanmış İstanbul günüdür.

| Gerekçe kodu | Anlamı |
|---|---|
| `history_below_30` | Geçmiş 30 günden az (`history_days`); **olasılık verilmez** (`probabilities` NULL). |
| `recent_missing_over_30_percent` | `d−13…d` içinde 22:00 fiyatı olmayan gün sayısı 14 günün %30'unu aşıyor (en az 5 gün); olasılık yazılır, satır gösterilebilir sayılmaz. |
| `family_not_in_training` | Ürün ailesi dondurulan modelin eğitim diliminde yok; olasılık yazılır, gösterilebilir sayılmaz. |

Gerekçe yoksa satır `showable` olur. `missing_days_14` eksik gün
sayısıdır. Olasılık anahtarları `r0` ve model adıdır (`r2_platt`).
`recorded_after_days`, görüntünün İstanbul tarihi eksi başlangıç
günüdür. 1 ertesi gün, daha yüksek değer geç veya geriye dönük kayıttır.
Girdiler başlangıcın 22:00 turuyla sınırlıdır.

**Çıktı klasörü.** Yeni klasöre yazılır, `manifest.json` en son oluşur:

| Dosya | İçerik |
|---|---|
| `predictions.jsonl` | Ürün ve güne göre sıralı, tekil satırlar: anahtar, `anchor_at`, `recorded_after_days`, girdiler, `missing_days_14`, gerekçeler, `showable`, olasılıklar. |
| `report.md` | Türkçe özet: sayılar, gerekçe dağılımı ve günlük döküm. |
| `manifest.json` | Biçim/kural sürümü, model adı ve manifest SHA-256'sı, görüntü SHA-256'sı ve okuma anı, son kapanmış gün, başlangıç günü, kütüphane sürümleri, özet ve dosya parmak izleri. |

Yazımdan sonra parmak izi, alan ve sıra, [0,1] olasılık aralığı,
gerekçe/`showable` uyumu ve satır özeti doğrulanır. Parmak izi yenilenmiş
tutarsız veri de reddedilir.

**Resmî kayıt.** `records_dir` altında doğrudan `tahmin_` önekini ve
tamamlanmış manifesti taşıyan klasörler geçerlidir. Kayıtlı ürün/gün
yeniden tahmin edilmez. Aynı anahtarın iki klasörde olması, başka model
veya uyumsuz SHA-256 çıkış 1 verir. Diğer yollar deneme çıktısıdır. Yeni
satır yoksa çıkış 0 ile klasör oluşturmadan durur.

Envanter, model doğrulama, tahmin ve yazım `records_dir/tahmin.lock`
altında yürür. Deneme dahil `shadow-predict` ile `shadow-daily` bu
kilidi kullanır. Meşgul kilit beklemeden çıkış 3 verir. Süreç bitince
işletim sistemi kilidi bırakır. Kilit dosyası diskte kalabilir.

| Çıkış | Anlamı |
|---|---|
| 0 | Kayıt yazılıp doğrulandı veya yeni kayıt yoktu. |
| 1 | Klasör var; ayar, görüntü, model/SHA, kanıt klasörü, kayıt klasörü ya da dosya hatası; ML kütüphaneleri eksik. |
| 2 | Argüman hatası. |
| 3 | Aynı resmi kayıt dizininde başka bir gölge tahmin yazıcısı çalışıyor. |
| 130 | Kullanıcı durdurdu (manifestsiz klasör kalır, kayıt sayılmaz). |

Kendi seri girdileriyle Cimri eğitim girdilerinin dağılımı farklıdır.
Bu durum olasılık ölçeğini etkileyebilir. `showable` kayıt yeterliliğidir.
Gösterim kararı için gölge değerlendirmesi ve onay gerekir. Kayıt parmak
izleri yerel bütünlüğü denetler.
[İlk deneme ve bağımsız doğrulama](arsiv/teknik_2026-11-23.md#gölge-mod-tahmin-kaydı-python--m-appml-shadow-predict)


### Günlük gölge çalışması (`python -m app.ml shadow-daily`)

`app/ml/daily.py` önce `API_DATABASE_URL` okuma hesabıyla `snapshot`,
ardından görüntüden `shadow-predict` çalıştırır. Veritabanı salt okunur
kullanılır. Tahmin aşaması ağsız ve mevcut modelle çalışır.

```powershell
# Kullanıcı ortamına bir kez; parola yalnız pgpass.conf'ta kalır.
[Environment]::SetEnvironmentVariable('API_DATABASE_URL', 'postgresql://fiyat_takip_api@localhost:5432/fiyat_takip', 'User')
$env:API_DATABASE_URL = [Environment]::GetEnvironmentVariable('API_DATABASE_URL', 'User')
.venv\Scripts\python.exe -m app.ml shadow-daily
$LASTEXITCODE
```

`--config AYAR_DOSYASI` varsayılan `config/shadow.json` yerine geçer.
`--scheduled` sadece log başlığını işaretler. `run_logged`, stdout,
stderr ve son çıkışı `data/logs/golge_<yerel tarih-saat>.log` dosyasına
yazar. `LOG_DIR` klasörü değiştirir. Log açılamazsa komut veri okumaz.
`pythonw.exe` ile de log yazılır.

**Bekleme.** Ortak tarama kilidi sadece görüntü okumasında tutulur.
Kilit doluysa veya DB'de `running` tur çıkış 3 üretirse komut 5
dakikada bir, monoton saatle en çok 90 dakika yeniden dener. Süre dolarsa
çıkış 3 ile tahmin aşamasına geçmeden durur. Diğer görüntü hataları
tekrar denenmez. Yarım turu toplama akışı uzlaştırır.

**Dosyalar.** Zaman damgası İstanbul saatinde, mikrosaniye içerir. Varsayılan
kayıt dizini `data/ml/golge/` altında:

| Yol | İçerik |
|---|---|
| `kanitlar/{labels,features,split,model}/` | Dondurulmuş modelin değişmeyen kanıtları. |
| `goruntuler/veri_<zaman>/snapshot.json` | O çalışmada alınan ve tahmin manifestinde SHA-256'sı kayıtlı görüntü. |
| `tahmin_<zaman>/` | Yukarıdaki değişmez resmi tahmin dosyaları; manifest en son yazılır. |
| `tahmin.lock` | Elle ve günlük tahmin yazıcısının ortak kilit dosyası. |

İlk çalışma 27 Ekim 2026'dan son kapanmış güne kadar kayıtsız
başlangıçları doldurur. Sonraki çağrılar yeni görüntü ve log alır.
Aynı başlangıçlar yeniden yazılmaz. Tahmin kilidi meşgulse çıkış 3 ile
hemen durur, 90 dakikalık bekleme burada uygulanmaz.

| Çıkış | Anlamı |
|---|---|
| 0 | Görüntü ve tahmin doğrulandı veya bütün başlangıçlar zaten kayıtlıydı. |
| 1 | Log, okuma adresi/rolü, görüntü, ayar, kanıt, model veya dosya hatası. |
| 2 | Argüman hatası. |
| 3 | 90 dakika sonunda tur/keşif/DB `running` sürüyor veya kayıt yazıcısı meşgul. |
| 130 | Kullanıcı durdurdu; tamamlanmamış tahmin klasörü resmi kayıt sayılmaz. |

**Windows görevi.** İlk elle çalışmanın sonucu doğrulandıktan sonra kullanıcı
kurar; betik UTF-8 BOM'ludur ve yönetici izni istemez:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\golge_zamanlayici_kur.ps1
# Geri almak için:
powershell -ExecutionPolicy Bypass -File scripts\golge_zamanlayici_kur.ps1 -Kaldir
```

Görev `\FiyatTakip\GolgeTahmin`, her gün 11:00'de
`.venv\Scripts\pythonw.exe -m app.ml shadow-daily --scheduled` çalıştırır.
Çalışma klasörü proje köküdür; konsol penceresi açılmaz. `StartWhenAvailable`
açıktır, kaçan tetikleme uygun oturumda telafi edilir; komut eksik günleri
bulur. Kullanıcının oturumu açık olmalıdır (`Interactive`, `Limited`);
ikinci tetikleme atlanır (`IgnoreNew`), süre sınırı 2 saattir, pilde de
çalışır. Bilgisayarı uyandırmaz. Kullanıcı ortamında `API_DATABASE_URL`
tanımlı değilse kurulmaz; kaldırma için bu değişken aranmaz. Tekrar kurulum
aynı görevi günceller; fiyat toplama ve keşif görevlerine dokunmaz.

İlk elle çalışma, yinelenmeme, görev kurulumu ve ilk otomatik
çalışma tarihli kanıtlarıyla arşivlenmiştir.
[İşletim kabul kayıtları](arsiv/teknik_2026-11-23.md#günlük-gölge-çalışması-python--m-appml-shadow-daily)
· [Güncel işletim kapsamı](../README.md#-güncel-kapsam)


### Gölge değerlendirmesi (`python -m app.ml shadow-evaluate`)

`app/ml/shadow_evaluation.py` kayıtlı olasılıkları yeni görüntünün
etiketleriyle karşılaştırır. Yalnız dosya okur ve mevcut olasılıkları
puanlar. Gölge görevinin ilk otomatik çalışmasını beklemeden geçerli
tahmin kayıtlarıyla değerlendirilebilir.

```powershell
$env:API_DATABASE_URL = [Environment]::GetEnvironmentVariable('API_DATABASE_URL', 'User')
$shadowStamp = Get-Date -Format yyyyMMdd_HHmmss_fff
$shadowSnapshot = "data\ml\golge\goruntuler\veri_degerlendirme_$shadowStamp"
$shadowReport = "data\ml\golge\degerlendirme_$shadowStamp"
.venv\Scripts\python.exe -m app.ml snapshot --output-dir $shadowSnapshot
if ($LASTEXITCODE -eq 0) {
    .venv\Scripts\python.exe -m app.ml shadow-evaluate --snapshot $shadowSnapshot --output-dir $shadowReport
    $LASTEXITCODE
}
```

`--snapshot` ve `--output-dir` zorunludur. Çıktı klasörü yeni olmalıdır.
`--config AYAR` varsayılan `config/shadow.json` yerine geçer. Sonucu
görüntünün okuma anı belirler.

**Kanıt zinciri.** `load_experiment_inputs` ve `verify_model_outputs`
ön kayıtlı manifesti ve dosya parmak izlerini doğrular. R0 için
dondurulan Cimri eğitim oranı JSON'dan okunur. Envanter `tahmin.lock`
altında belleğe alınır, sonra kilit bırakılır. Kayıt manifestlerinin
SHA-256 değerleri rapora alınır. Başka model, yinelenen anahtar, bozuk
başlık ve kayıt görüntüsünden eski görüntü reddedilir. Yarım klasörler
sağlık raporunda görünür.

Girdi yeniden hesaplanır. Ürün/gün, `product_key`, `anchor_at`,
özellikler, eksik gün, aile, geçmiş, `showable` ve ilk kayıt anından
hesaplanan `recorded_after_days` eşleşmelidir. Uyuşmazlık raporu
durdurur. Olasılık ilk resmi dosyadan alınır.

**Asıl topluluk**, geçmişi en az 30 gün olan, olasılığı kayıtlı,
`y_sabit` etiketi 0/1 ve `showable` olan `own_evaluation` satırlarıdır.
Tüm uygun satırlar ve `y_izlenen` ayrı puanlanır. İki etiketi de
bulunan gösterilebilir kayıtlar kapsam farkı için eşleştirilir.
NULL etiket puan dışındadır. Gösterim kapısı asıl topluluğa dayanır.

AP, Brier, log loss, Brier skill, güvenilirlik ve kırılımlar mevcut
`METRIC_RULES` ile hesaplanır. Tek sınıfta AP NULL, Brier ve log loss
hesaplanabilir. Desteksiz ürün ve marka hücreleri yetersiz görünür.
`own_evaluation_bootstrap` mevcut tarih bloklu AP farkını yalnız
`own` ve `own_evaluation` için hesaplar. Kısa dönem veya tek sınıfta
aralık gerekçeli olarak NULL kalır. AP farkı ve aralığı bilgi amaçlıdır.

**Kapı koşulları.** Asıl sonuçta ilk ve son etiketli başlangıç arasında
iki uç dahil en az 60 takvim günü, aralığın içinde 1–30 Kasım 2026'nın
tamamı, Kasım dışında en az 14 farklı etiketli gün ve en az 30 olumlu
pencere kümesi gerekir. Kasım içindeki boş günler ayrıca raporlanır.

Veri desteği yetersizse sonuç `not_evaluable` olur. Destek yeterliyse
Brier skill > 0, ortalama olasılık ile gerçekleşme farkı ≤ 0,05 ve en
az 20 satırlı her kovada fark ≤ 0,15 aranır. Destekli kova yoksa kova
koşulu belirsizdir. Hesaplanan bir performans koşulu sağlanmazsa
`not_met`, böyle bir sonuç yokken koşul belirsizse `not_evaluable`,
hepsi sağlanırsa `met` olur. Yuvarlama toleransı mutlak 1×10⁻¹²'dir.

Kasım ve diğer günler, `missing_ratio_30d ≤ 0,10` ve `> 0,10`,
22 Kasım öncesi ve sonrası bilgi amaçlı kırılımlardır. İşletim kuralı,
kesin değerlendirmeyi bir kez 5 Ocak 2027 görüntüsüyle yapmaktır.
`final_date_matches` görüntünün İstanbul tarihini doğrular. Tek
çalıştırma ve arayüz açılışı ayrı işletim adımlarıdır.

**Kayıt sağlığı.** Görüntünün İstanbul tarihi başlangıçtan bir gün sonraysa kayıt ertesi
gün sayılır. Daha geç kayıt, yalnız en erken kayıt görüntüsündeyse ilk
toplu doldurmadır. Diğerleri geç kayıttır. Eksik resmî tahmin, başlangıç fiyatı olmayan gün,
henüz gözlenmemiş ürün/gün, NULL etiket ve yarım klasör ayrı sayılır.

**Çıktılar.** Aynı girişler aynı baytları verir; manifest en son yazılır:

| Dosya | İçerik |
|---|---|
| `evaluations.jsonl` | Ürün/gün sıralı kayıtlar, ilk girdiler/olasılıklar, kaynak klasör/zaman, yeterlilik, gerçek birincil/ikincil etiket ve gelecek pencere kanıtları. |
| `report.json` | Kaynak manifestleri ve SHA'lar, kurallar, topluluklar, R0/model puanları, aralık, koşullar, kırılımlar ve kayıt sağlığı. |
| `report.md` | Türkçe puan, koşul, güvenilirlik kovası ve günlük sağlık tabloları. |
| `manifest.json` | Tamamlanma/kural sürümleri, giriş zinciri ve çıktı dosyalarının SHA-256'ları. |

Okuyucu parmak izi, satır sırası ve tekilliği, topluluk sayısı, kapı,
özet ve Türkçe raporu çapraz doğrular. Parmak izleri yerel bütünlük
kontrolüdür.

| Çıkış | Anlamı |
|---|---|
| 0 | Geçerli rapor yazılıp doğrulandı; kapının sonucu karşılandı/karşılanmadı/değerlendirilemedi olabilir. |
| 1 | Klasör var; ayar, görüntü, model/kanıt, kayıt/girdi uyumu veya dosya hatası; eksik bağımlılık. |
| 2 | Argüman hatası. |
| 3 | Kayıt kilidi meşgul; daha sonra yeniden denenir. |
| 130 | Kullanıcı durdurdu; manifesti oluşmamış çıktı tamamlanmış rapor sayılmaz. |

İlk gerçek değerlendirme ve bağımsız puan denetimi arşivdedir.
[İlk değerlendirme kanıtı](arsiv/teknik_2026-11-23.md#gölge-değerlendirmesi-python--m-appml-shadow-evaluate)
· [Güncel ara rapor](../README.md#-güncel-kapsam)


### Güvenilirlik grafiği (`python -m app.ml reliability-chart`)

`app/ml/reliability.py` saklı test veya gölge raporundaki kovaları
aynı değerlerle bağımsız SVG'ye çevirir. Sunum ve ara/kesin rapor için
kullanılabilir.

```powershell
.venv\Scripts\python.exe -m app.ml reliability-chart --report <RAPOR_KLASORU> --output "artifacts\ml_grafik_<tarih>\<ad>.svg"
```

| Rapor klasörü | Çizilen kovalar |
|---|---|
| Saklı test (`final-test` çıktısı; manifestte `test_opened`) | Dondurulan modelin saklı test kovaları |
| Gölge değerlendirme (`shadow-evaluate` çıktısı; manifestte `kind: shadow_evaluation`) | Dondurulan modelin asıl sonuç (gösterilebilir, etiketli) kovaları; kapı da bu kovaları kullanır |

**Okuma.** Yatay eksen ortalama olasılık, dikey eksen en az %5
düşüşün gerçekleşme oranıdır. Nokta köşegenin üstündeyse tahmin düşük,
altındaysa yüksektir. En az 20 satırlı kovalar dolu daireyle çizilir ve
birbirine bağlanır. Daha az satırlı kovalar boş dairedir. Çubuklar satır sayısını,
başlık rapor türü, dönem, satır sayısı ve `final_date_matches` durumunu
gösterir.

**Doğrulama.** Manifest `complete` olmalı ve `report.json` parmak iziyle
eşleşmelidir. On kovanın sınır, [0,1] aralığı, sayı, destek işareti,
ortalama ve toplamları doğrulanır. Çıktı rapor klasörü dışında yeni
bir `.svg` olmalıdır. Nokta ve çubukların `data-*` değerleri rapora
karşı yeniden okunur. Doğrulanamayan çıktı silinir. Aynı rapor aynı
baytları verir. Komut ML kütüphaneleri, DB ve ağ katmanı yüklemez.

| Çıkış | Anlamı |
|---|---|
| 0 | Grafik yazıldı ve rapordaki kovalarla doğrulandı. |
| 1 | Dosya var, uzantı `.svg` değil, rapor klasörüne yazma, eksik/değişmiş/desteklenmeyen rapor veya tutarsız kova. |
| 2 | Argüman hatası. |
| 130 | Kullanıcı durdurdu; yazılmış ama doğrulanmamış grafik silinir. |

[İlk grafikler ve görsel kabul](arsiv/teknik_2026-11-23.md#güvenilirlik-grafiği-python--m-appml-reliability-chart)


### Tahmin gösterim onayı (`python -m app.ml shadow-display`)

Gösterim varsayılan kapalıdır. Açılış yalnız 5 Ocak 2027 veya sonrasında,
İstanbul tarihi tam 5 Ocak olan kesin görüntünün raporuyla yapılır:

```powershell
.venv\Scripts\python.exe -m app.ml shadow-display --evaluation <KESIN_RAPOR_KLASORU>
```

Açma komutu değerlendirme dosyalarını, satır özetlerini ve kapıyı
doğrular. Asıl grubun puanları kayıtlı olasılıklardan yeniden hesaplanır.
Model kanıt zinciri ve R0 JSON üzerinden denetlenir. Raporun model
kimliği, `met` sonucu ve kaynak görüntünün SHA-256'sı/zamanı eşleşmelidir.
Görüntü, kayıt kökündeki `goruntuler/*/snapshot.json` dosyaları içinde
bulunmalıdır.

Onay atomik olarak `records_dir/gosterim_onayi.json` dosyasına yazılır.
Dosya model ve kesin rapor manifest SHA-256 değerlerini, rapor yolunu,
model adını, eğitim ailelerini ve UTC onay/güncelleme anlarını taşır. Aynı onay yinelenebilir. Farklı model veya
rapor, mevcut onay kapatılmış olsa da başka onaya dönüştürülemez.
Parmak izi yerel bütünlüğü doğrular.

```powershell
.venv\Scripts\python.exe -m app.ml shadow-display --disable
```

Kapatma bağları koruyarak `enabled=false` yazar. Zaten kapalıysa
başarıyla döner. İki eylemden biri seçilir. İkisi de isteğe bağlı
`--config <AYAR_DOSYASI>` alır. `gosterim_onayi.lock` elle verilen
onay eylemlerini sıraya koyar.

| Çıkış | Anlamı |
|---|---|
| 0 | Gösterim açıldı/kapatıldı veya aynı durumda kaldı |
| 1 | Tarih, rapor, model, kaynak veya dosya doğrulanamadı; onay değiştirilmedi |
| 2 | Eksik/çelişkili komut parametresi |
| 3 | Gösterim onayı kilidi meşgul |
| 130 | Kullanıcı durdurdu |

API açık gösterimde model bağını ve onaylı rapor parmak izlerini her
okumada kontrol eder. Model veya kayıt ayarı değiştiğinde eski onay
geçersizdir. Bozuk rapor güvenli 503 döndürür. Geliştirme testleri
yapay rapor ve klasör kullanır.

#### Gösterimi işletme sırası

1. Yerel [API'yi](#salt-okunur-fastapi) ve [ekranı](#başlatma-ve-test-önizlemesi)
   aç. Tahmin ucu eklenmeden önce başlamış süreçleri yeniden başlat.
   Onay olmadan kartta “Tahmin gösterimi kapalı” beklenir. Gerçek gösterim
   için doğrulanmış kesin rapor kullan.
2. Günlük `shadow-daily` ve [6.5 izlemesini](../proje_plani.md#65-kontrol-planı)
   sürdür. Kayıtları, kaynak görüntüleri, model kanıtını ve raporu bir
   arada koru. API onaylı raporu kayıtlı yolundan açar.
3. **5 Ocak 2027'de** günlük gölge görevinin bittiğini kontrol et. Aynı
   İstanbul tarihli görüntüyle [kesin raporu](#gölge-değerlendirmesi-python--m-appml-shadow-evaluate)
   yeni klasöre yaz.
4. Yalnız rapor sonucu `met` ise rapor klasörünü `shadow-display --evaluation`
   komutuna ver ve çıkış 0'ı kontrol et. Diğer iki sonuçta gösterim kapalı
   kalır. Onayı doğrulayıcı komut yazar. Model ve eşik değişikliği ayrı karar
   ve değerlendirme planı ister.
5. Gösterim açılınca Elle Yenile'ye bas veya bir sonraki başarılı otomatik
   okumayı bekle. `available` için İstanbul takvimindeki dünün yeterli
   kaydı gerekir. Gece yarısında eski oran kaldırılır. Yeni günlük tahmin
   yazılana kadar `unavailable` beklenebilir.
6. Sorunda `shadow-display --disable` çalıştırıp ekranı yenile.
   `closed` ve `forecast=null` beklenir. Tahmin kartının 503'ü fiyat
   ekranını durdurmaz. Dosya ve parmak izlerine müdahale etmeden kaynak
   uyuşmazlığını incele. Aynı doğrulanmış raporla yeniden açılabilir.

Açık API'de yalnız tahmin durumunu okumak için şu komutu kullan.

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/products/apple_iphone_15_128gb/prediction' -MaximumRedirection 0 -TimeoutSec 10 | Select-Object state, reasons, forecast
```

Kapalı gösterimde `state=closed` ve boş `forecast` beklenir.
Diğer durumlar [API sözleşmesindedir](#salt-okunur-fastapi).

#### Otomatik doğrulamanın kapsamı

`tests/test_api_ui_integration.py`, `_test` DB ve yapay tahmin/onayla
gerçek kayıt okuyucu, FastAPI, yerel istemci ve Streamlit AppTest'i
süreç içinde sınar. Gün değişimi, ürün ve aralık seçimi, yeni/eksik
tahmin, yetersizlik, bozuk kayıt veya kaynak, düzelme ve CLI kapatma
kontrol edilir. İstek sırasında model eğitimi, tahmin veya pickle
yüklemesi testi düşürür. `tests/test_prediction.py` kütüphane/ağ
sınırını, `tests/test_ml_shadow_display.py` kesin rapor ve onay
bağlarını denetler. Canlı ve görsel kabul ayrı kanıtlarla değerlendirilir.


### Gölge işletiminde kontrol komutları

Kontrol takvimi ve kabul ölçütleri [6.5 planındadır](../proje_plani.md#65-kontrol-planı).
Aşağıdaki komutlar proje kökünde görevi ve yerel dosyaları yalnız okur;
görevi başlatmaz veya yeniden kurmaz:

```powershell
$shadowTask = Get-ScheduledTask -TaskPath '\FiyatTakip\' -TaskName 'GolgeTahmin'
$shadowTaskInfo = Get-ScheduledTaskInfo -TaskPath '\FiyatTakip\' -TaskName 'GolgeTahmin'
$shadowTask | Select-Object TaskName, State
$shadowTaskInfo | Select-Object LastRunTime, LastTaskResult, NextRunTime
$shadowLog = Get-ChildItem -LiteralPath 'data\logs' -Filter 'golge_*.log' |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($shadowLog) {
    $shadowLog.FullName
    Get-Content -LiteralPath $shadowLog.FullName -Encoding UTF8 -Tail 30
}
```

En yeni log elle çalışmaya da ait olabilir. Dosyanın başlığındaki tarih ve
`(zamanlanmış)` ifadesi, görev zamanı ve sondaki `Çıkış kodu: 0` birlikte
okunur. Kısa görünüm başlığı içermiyorsa tam log okunur:

```powershell
if ($shadowLog) {
    Get-Content -LiteralPath $shadowLog.FullName -Encoding UTF8
}
```

Haftanın logları için `Select-Object -First 1` sınırını kaldır ve
tarihleri seç. `Running` durumunda son çıkış henüz yazılmamış olabilir.
Kontrol sırasında görevin kendi süresinde bitmesini bekle.
[Günlük bekleme ve kilit kuralları](#günlük-gölge-çalışması-python--m-appml-shadow-daily)

[Değerlendirme komutlarını](#gölge-değerlendirmesi-python--m-appml-shadow-evaluate)
toplama ve keşif tamamlandıktan sonra kullanıcı çalıştırır. `snapshot`
çıkış 3 verirse diğer iş bitince yeni klasörle tekrar dene. Yakın tarihli
görevin doğrulanmış görüntüsünü de kullanabilirsin. Kapsamı görüntünün
okuma anı belirler. Her rapor için yeni bir çıktı klasörü seç.

Başarılı değerlendirmeden sonra aynı komut bloğunun `$shadowReport`
değişkeniyle özet alanları okunabilir. Bu okuma, raporu yeniden üretmez:

```powershell
$shadowReview = Get-Content -LiteralPath (Join-Path $shadowReport 'report.json') -Raw -Encoding UTF8 |
    ConvertFrom-Json
$shadowReview.summary
$shadowReview.health.timing
$shadowReview.health.missing_records.Count
$shadowReview.health.incomplete_folders
$shadowReview.gate
```

Günlük ayrıntı `health.per_day`, kaynak manifestleri `input.records`
alanındadır; okunabilir tablolar `report.md` içindedir. Çıkış kodlarının
anlamı ilgili komut bölümündedir. Geçerli bir raporun kapısı
`not_evaluable` veya `not_met` olabilir; bu sonuçlar komut hatası değildir.

### Gölge kayıtlarının kontrol sırası

Takvim ve kapanış koşulları [6.5 planındadır](../proje_plani.md#65-kontrol-planı).

**İlk otomatik çalışma.** Görev zamanı, log tarihi, `(zamanlanmış)`
başlığı ve çıkış 0 aynı çalışmaya ait olmalıdır. Görev sürüyorsa bekleme
satırlarını incele. Yeni tahmin yoksa uygun başlangıçların zaten
kayıtlı olduğunu kontrol et. Elle denemeden önce görev/log kanıtını
koru. 10:00 ve 22:00 fiyat turları için bilgisayar açık, uyanık ve
oturum açık olmalıdır. Kilit ekranı uygundur. Kaçan fiyat turunun geçmiş
gözlemlerini gölge görevi geri getiremez.

**Haftalık raporda bakılacaklar:**

- Her günün zamanlanmış logunu ve son çıkışını kontrol et. Eksik,
  kapanmamış veya hatalı logu araştır. Keşif bitişini log/görevle doğrula.
  Yeterli kimlik kanıtıyla kabul edilen sayfalar otomatik eklenir.
- `health.missing_records` boş olmalı. `no_start_price`,
  `not_yet_observed` ve NULL etiket ayrı okunur. Beklenen kayıt sayısı
  geçerli başlangıçlara bağlıdır.
- Yarım klasörleri, ertesi gün kayıtlarını, ilk toplu doldurmayı ve geç
  kayıtları incele. Önceki kayıt manifestleri `input.records` içindeki
  karşılıklarıyla eşleşmelidir.
- Asıl topluluğun veri desteğini ve kapı sonucunu oku. Kısa dönemde
  NULL aralık veya “Değerlendirilemedi” geçerli sonuçtur. Ara rapor
  model, eşik ve kesin tarih için karar oluşturmaz.
- [Haftalık yedeği](#haftalık-yedek) al ve iki `verify` çıktısında
  paket SHA-256 değerini karşılaştır.

**Sorun çıkarsa izlenecek sıra:**

| Belirti | Yapılacak kontrol / sonraki adım |
|---|---|
| Log yok veya son çıkış satırı yok | Önce görev zamanı, durumu, sonucu ve varsa log korunur; çalışan iş ile hiç başlayamayan/kesilen iş ayrılır. Eylem, çalışma klasörü ve ortam değişkeninin varlığı incelenir; parola yazdırılmaz. |
| Çıkış 1 | Logdaki somut girdi, izin, bağlantı, sürüm veya SHA hatası incelenir. Eski tahmin/kanıt dosyaları değiştirilmez; yeniden dondurma veya kalibrasyon çözüm sayılmaz. |
| Çıkış 2 | Komut argümanları ve görev eylemi belgelenen komutla karşılaştırılır. |
| Çıkış 3 | Günlük komutta 90 dakikalık tur/DB beklemesi ile kayıt kilidi ayrılır; değerlendirmede kayıt kilidi beklenmeden hata verir. Diğer iş bittikten sonra kullanıcı kontrollü yeniden dener. Kilit dosyasının varlığı tek başına etkin kilit değildir; dosya silinmez. |
| Çıkış 130 veya yarım klasör | Kesinti kanıtı korunur; manifesti olmayan çıktı tamamlanmış sayılmaz. Gerekirse yeni çıktı klasörüyle yeniden denenir; resmi kayıtların üzerine yazılmaz. |
| Eksik tahmin, değişmiş manifest veya girdi uyuşmazlığı | Kaynak görüntü ve loglarla neden araştırılır; hatalı/eksik çıktıyla kapı kararı verilmez. Veri uydurulmaz, eski kayıt değiştirilmez. |

Bu çıkışlar uygulamanındır; Windows görev sonucu ayrıca yorumlanır. Sorun
nedeni bulunmadan tekrar tekrar çalıştırmak kontrolün yerine geçmez.

### Tatil dönemi tur kontrolü

5 Ocak kesin değerlendirmesinde süre koşulu (en az 60 takvim günü) ilk
etiketli başlangıç olan 27 Ekim'den sayılır. Bu yüzden **25–28 Aralık
arasında en az bir etiketli başlangıç** gerekir. Bunun için o akşamın 22:00
turunda ürünün bütün planlanan sayfaları cevap vermeli ve sonraki 7 günün
en az 6'sında fiyat gözlenmelidir (günün bir tam turu yeterlidir). 5 Ocak
görüntüsünde en geç 28 Aralık başlangıcı etiketlenebilir. Bu koşul
sağlanmazsa model sonucu ne olursa olsun kapı “değerlendirilemedi” olur.

24 Aralık–4 Ocak arasında bilgisayar evde, prizde ve oturumu açık kalır;
kapak kapatılabilir ([20 Kasım kararı](../proje_plani.md#5-kararlar)).
Windows ayarı ve görev değiştirilmez. Her sabah 11:00 gölge görevinden sonra
proje kökünde aşağıdaki salt okunur komut çalıştırılır. Son iki fiyat turunu
ve son gölge kaydını gösterir:

```powershell
& {
    [Console]::OutputEncoding = [Text.Encoding]::UTF8
    $son = @(Get-ChildItem data\logs -Filter 'tur_*.log' | Sort-Object Name -Descending | Select-Object -First 2) +
        @(Get-ChildItem data\logs -Filter 'golge_*.log' | Sort-Object Name -Descending | Select-Object -First 1)
    foreach ($log in $son) {
        $ozet = Get-Content -LiteralPath $log.FullName -Encoding UTF8 |
            Select-String -Pattern 'tamamlandı:|Yeni kayıt:|başarısız|başlatılmadı|tamamlanamadı|Çıkış kodu'
        "$($log.Name): $(($ozet | ForEach-Object { $_.Line.Trim() }) -join ' | ')"
    }
}
```

Beklenen: dünün `22-00` ve bugünün `10-00` tarihli tur logları, ikisinde de
`tamamlandı` ve `Çıkış kodu: 0` ya da `2` (tur tamamlandı, bazı sayfalarda
hata), ayrıca bugünün `golge_` logunda `Çıkış kodu: 0`. Eksik tarih, çıkış
1 veya 3 ya da sonu olmayan log aksama demektir: önce bilgisayarın açık,
prizde ve oturumunun açık olduğu sağlanır, sonra neden yukarıdaki sıra ve
[bilinen sınırlarla](#bilinen-sınırlar) araştırılır. Kaçan tur geriye dönük
toplanamaz. Tur, başlangıç saatine göre dilime yazılır: gece yarısından
sonra biten akşam turu o günün başlangıcını vermez; ertesi sabah 10:00'dan
önce başlayan telafi turu önceki akşamın dilimine yazılır ve gün aşımı
nedeniyle kullanılmaz; 10:00'dan sonra başlayan telafi turu o günün sabah
dilimi sayılır.

## Docker: imaj ve Compose temeli

Teslim ortamı ayrı Docker kopyasını kurar. İmaj, paket aktarımı,
API/ekran bağlantısı ve ortak PowerShell girişi
[Docker adımlarında](../proje_plani.md#docker-yazılımı-ve-yerel-kabul-9297)
kayıtlıdır. Windows görevleri ve canlı veritabanı kaynak sistemde kalır.

### İmaj ve servis tanımları

- Python `3.13.15-slim-bookworm` ve PostgreSQL `17.11-bookworm` imajları
  SHA-256 ile sabittir. LightGBM için `libgomp1` sürümü de sabittir.
  Bağımlılıklar kilitli wheel hash'leriyle kurulur ve `pip check` çalışır.
- Uygulama `/app/app` içindedir ve `/app` göreli ML yollarının köküdür.
  İmajda yalnız gerekli kaynak, bağımlılık kilidi, SQL okuma rolü betiği
  ve `/opt/delivery/shadow.json` ön kayıt referansı bulunur. Referans
  model kimliği ile yolları doğrular. Gerçek veri, model, rapor, parola
  ve çalışma ayarı Prepare ile sağlanır. `.dockerignore` izin listesiyle,
  Dockerfile açık `COPY` yollarıyla sınırlandırılır.
- API ve UI `10001:10001` ile, salt okunur dosya sistemi, yazılabilir
  `/tmp` ve `init: true` kullanır. Giriş komutu süreci devreder.
  Varsayılan imaj komutu Python sürümünü yazar.
- `db`, `api` ve `ui` için `restart: "no"` geçerlidir. UI
  `network_mode: service:api` ile API ağını paylaşır. Yalnız
  `127.0.0.1:8503 → 8501` yayımlanır. UI'nin API hedefi
  `127.0.0.1:8000` olarak kalır.
- Sağlık sırası DB → API `/health` → UI. Gerekli yeniden oluşturma
  API ve UI için birlikte yapılır. `depends_on.restart: true`
  Compose işlemine bağlıdır.
- `database`, `configuration` ve `shadow` alanları Compose proje adına
  (`-p`) göre ayrılır. PostgreSQL verisi `/var/lib/postgresql/data`
  altındadır. API, `/app/config` ve `/app/data/ml/golge` alanlarını salt
  okunur bağlar.

### Gizli dosyalar

`DELIVERY_STATE_DIR` varsayılan `data/teslim` konumunu değiştirir.
İlk Prepare, paket kimliğine bağlı ayrı parolaları üretir.

- `secrets/admin_password` DB ve bakım profili `transfer` içindir.
  DB dosyayı `POSTGRES_PASSWORD_FILE` ile okur.
- `secrets/api_password` API ve `transfer` içindir. `--api` giriş
  seçeneği `/tmp/api-pgpass-*` dosyasını `0600` izinle oluşturur ve
  `PGPASSFILE` yolunu yalnız başlattığı sürece verir. Parola URL'ye
  veya çıktıya yazılmaz. UI bu hazırlığı kullanmaz.

Giriş yardımcısı sabit `db:5432` üzerinde `fiyat_takip` ve
`fiyat_takip_api` çiftini kabul eder. Testte `_test` DB ve
`fiyat_takip_api_test` kullanılır. Parolalı/parametreli URI ve diğer
hedefler reddedilir. Hazırlık hatası güvenli mesajla 1, komut yokluğu
2 döner.

### Temel doğrulama ve kilit yenileme

Proje kökünde, Docker Desktop Linux motoru açıkken:

```powershell
docker compose config --quiet
docker build --platform linux/amd64 -t fiyat-takip-teslim:local .
docker run --rm --network none --read-only --tmpfs /tmp:mode=1777 fiyat-takip-teslim:local python --version
```

Bu kontroller imajı doğrular. Hazır kopyanın normal açılışı
[Start ile yapılır](#docker-tek-komutla-kullanım).

Bağımlılık kilidi için paket çözümlemesini Linux'ta yeniden çalıştır.
Windows `pip freeze` kilit girdisi olarak kullanılmaz.

```powershell
New-Item -ItemType Directory -Force artifacts/docker93 | Out-Null
.venv\Scripts\python.exe -m tools.docker_lock input --output artifacts/docker93/requirements.in
$dockerPythonImage = (Get-Content Dockerfile -First 1).Substring(5)
$dockerResolveMount = "type=bind,source=$((Resolve-Path artifacts/docker93).Path),target=/work"
docker run --rm --platform linux/amd64 --mount $dockerResolveMount --workdir /work $dockerPythonImage python -m pip install --dry-run --ignore-installed --only-binary=:all: --disable-pip-version-check --report report.json -r requirements.in
.venv\Scripts\python.exe -m tools.docker_lock lock --report artifacts/docker93/report.json --output requirements-linux.lock
```

`lock`, pip raporu sürüm 1 ve Python 3.13.15 / CPython / Linux
x86_64 bekler. Wheel'ler tekil, hash'li ve yayında olmalıdır. Doğrudan
URL reddedilir. Gereksinim ve ek özellikler `pyproject.toml` ile
eşleşmelidir. Kilit, bağımlılık girdi SHA'sını da taşır. Sürüm seçimini
incele ve kilit değişince imajı, testleri ve biçimi doğrula.


## Docker: paket ve veritabanı aktarımı

### Dışa aktarma ve paket sözleşmesi

Kaynak Windows sisteminde kullanıcı proje kökünden, toplama/keşif/gölge
yazımı bittikten sonra çalıştırır. `DATABASE_URL` şifresizdir. Parola
Windows `pgpass.conf` dosyasından okunur.

```powershell
$teslimPaket = "data\teslim\paketler\paket_$(Get-Date -Format yyyyMMdd_HHmmss)"
.venv\Scripts\python.exe -m app.delivery export --output $teslimPaket
.venv\Scripts\python.exe -m app.delivery verify --bundle $teslimPaket
```

PostgreSQL 17 aracı gerekir. Varsayılan yol
`C:\Program Files\PostgreSQL\17\bin\pg_dump.exe`, seçenek
`--pg-dump <DOSYA>`dır. Çıktı klasörü yeni ve resmî gölge kökünün
dışında olmalıdır. Kaynak URI'de parola, `passfile`, `service` ve
ortamda `PGPASSWORD`, `PGPASSFILE`, `PGSERVICE` reddedilir.

- Toplama/keşif kilidi ve `tahmin.lock` beklemeden alınır. `running`
  tur işlemi durdurur. Kapanmış `interrupted` turlar pakete girer.
- `REPEATABLE READ READ ONLY` işleminde tablo/görünüm sayısı, sıralı
  satır SHA'ları ve kimlik dizisi okunur. `pg_export_snapshot()`
  aynı görüntüyü `pg_dump --format=custom --snapshot=…` sürecine
  verir. Döküm `default_transaction_read_only=on` ile çalışır.
  Parola argümana eklenmez.
- Katalog/DB, migration checksum'ları ve PostgreSQL 17 yapısı
  doğrulanır. Tablo, sütun, indeks, kısıt, görünüm, fonksiyon,
  tetikleyici ve dizi tanımları kapsamdadır. Yapı parmak izi 001–005'e
  aittir. Yeni migration bu sözleşmenin test DB'de doğrulanmasını ve
  güncellenmesini gerektirir.
- Katalog, keşif, runtime, Cimri eşleştirmesi ve gölge ön kaydı;
  modelin etiket/girdi/bölme/model kanıtı; tamamlanmış resmî
  tahmin/değerlendirme ve zorunlu kaynak görüntüleri kopyalanır.
  Görüntüler içerik SHA'sına göre taşınır. Raporlardaki eski Windows
  yolları korunur. Yarım klasör, kilitler, sırlar, devir dosyaları ve
  Windows gösterim onayı paket dışındadır. Model kanıtı eğitim, yeni
  tahmin veya pickle yüklemesi olmadan doğrulanır.

En son yazılan `manifest.json` biçim, UTC hazırlama anı, Git commit'i,
çalışma ağacı durumu, kod/bağımlılık SHA'sı, DB/migration/yapı kanıtı,
model SHA'sı ve dosya SHA'larını taşır. Paket kimliği ham manifest
SHA'sıdır. Uyumluluk kod içeriğine dayanır. Kodda CRLF/LF normalize
edilir. Kanıt dosyalarının baytları korunur.

`verify` eksik/fazla dosyayı, güvensiz yolu, sembolik bağlantıyı veya
Windows yeniden yönlendirmesini reddeder. Hash, model, tekil ürün/gün,
kayıtların kaynak görüntüleri, kod, migration ve şema uyuşmalıdır.
Tek JSON satırı parola veya olasılık içermez. Başarıda `0`,
doğrulama/bağlantı/araç hatasında `1`, argüman hatasında `2`, meşgul
ortak kilitte `3` döner. Yarım
dışa aktarma korunur. Yeni klasörle tekrar denenir.


### Docker kopyasını hazırlama

Paket desteklenen Windows teslim bilgisayarında şu girişle hazırlanır:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\teslim.ps1 -Action Prepare -Bundle <PAKET_KLASORU>
```

`Bypass` yalnız çağrılan PowerShell süreci içindir. Prepare, Start ve
Rollback gerekirse Docker Desktop'ı gizli açmayı dener ve Linux
motorunu en çok iki dakika bekler. Docker/WSL2 ilk kurulumu kullanıcıya
aittir. Teslimde yerel Python/PostgreSQL gerekmez. İlk Prepare
uyumlu varsayılan imaj yoksa imajı oluşturur ve gerekirse sabit PostgreSQL
imajını indirir. Bu adım internet isteyebilir. Uyumsuz özel imaj veya
paket reddedilir.

1. Sabit `desktop-linux` motorunda paket, ağsız ve salt okunur
   doğrulanır. PostgreSQL 17.11 imajı hedef DB'yi oluşturmadan arşiv
   listesini okur.
2. Paket SHA'sının ilk 24 karakteri Compose proje adını belirler.
   Hazırlık `data/teslim/<TAM_SHA>/` altında tutulur. Ayrı rastgele
   parolaların Windows ACL'si mevcut kullanıcıya ve SYSTEM'e açıktır.
3. Yalnız `db` açılır. Yeni hedefte NOLOGIN `fiyat_takip_owner`
   oluşturulur. Arşiv konteynerin yerel soketinden tek işlemde yüklenir.
   DB adı korunur. Kaynak adresi hedefe verilmez.
4. Satır, şema ve dizi kanıtları eşleşir. DB, şema ve nesne sahibi
   NOLOGIN rolüdür. `api_okuma_rolu.sql` kullanılır.
   `validate_readiness` API'nin SELECT yetkisini ve yazma yetkisinin
   bulunmadığını doğrular.
5. Ayar ve ML dosyaları kopyalanır. Kalıcı alanda
   `.delivery_ready.json`, bilgisayarda `prepared.json` en son
   yazılır. Yeni kopyada gösterim kapalıdır.

`bootstrap`, `finalize` ve `check` bakım komutlarıdır. Linux Docker
dışında veya `db:5432` dışında yazan bağlantı açılmaz. CLI ayrıntılı
hatayı gizler. `transfer` ayar ve gölge alanlarını yazabilir. API
salt okunur bağlanır. UI DB sırrı almaz.

Aynı pakette Prepare, hazır veri, dosyalar, sahiplik ve okuma rolünü
yeniden doğrular. Geri yükleme tekrarlanmaz. Yarım veya başka pakete
ait alan korunur. Gerçek kopyada izinler salt okunur SQL ile incelenir.
Yazmanın reddi yapay `_test` kopyasında sınanır.
[İlk aktarım kabulü](arsiv/teknik_2026-11-23.md#docker-kopyasını-hazırlama)


### Docker: tek komutla kullanım

Ortak giriş `scripts/teslim.ps1` dosyasıdır. Kullanıcı adımları
[teslim rehberindedir](teslim.md).

**Export.** Kaynak Windows'ta `.venv`, PostgreSQL 17 araçları ve
şifresiz `DATABASE_URL` kullanır. Tarama ve gölge kilitlerini korur.
Zaman damgalı yeni klasör `-Output <YENI_KLASOR>` ile seçilebilir.
Teslim kopyasındaki diğer işlemler yerel Python/PostgreSQL istemez.

**Prepare ve Rollback.** Prepare, ekran kapalıysa paketi hazırlar ve
seçer. Ekranı Start açar. Ekran açıksa önce eski API/UI durur, aday
API/UI birlikte açılır. Sağlık doğrulanınca seçim değişir ve eski DB
kapanır. Aday açılamazsa aday durur, önceki ekran yeniden açılır ve
seçim korunur. Kurtarma hatası ayrıca bildirilir, veri korunur.
Rollback aynı geçişi kullanarak seçili ve önceki paketi değiştirir.
Aynı pakette Prepare seçim geçmişini ve DB'yi korur.

Seçim `data/teslim/selection.json` içindedir. Paketin `prepared.json`
dosyası imajın tam SHA kimliğini ve o paketin `compose.yaml` SHA'sını
tutar. Eski kayıt aynı paketin başarılı Prepare doğrulamasıyla,
DB yüklemeden bir kez güncellenir. Start ve Rollback kayıtlı imaj
kimliğini kullanır. Geri dönüş için eski imaj, paket ve alanlar gerekir.

**Start.** Paket, model, kod, hazır DB, rol ve dosya uyumu denetlenir.
DB → API → UI sağlıklıysa hazır mesajı verilir. Sağlıklı servisler
korunur. Yenileme gerekirse API/UI birlikte oluşturulur. Start, Stop ve
Rollback yerel imaj ve paketleri kullanır. Ekran yalnız
`http://127.0.0.1:8503` üzerindedir. Port başka uygulamadaysa işlem
durur. API/DB portları yayımlanmaz.

Ortak `.prepare.lock` meşgulse çağrı beklemeden hata verir. Geçici Compose
ortamı çağrı sonunda geri alınır. Status, Logs ve Stop kapalı motoru
açmaz. Logs sınırlı satır gösterir, parola ve parolalı DSN'yi maskeler.
Stop yalnız seçili servisleri kapatır. Kalıcı alanlar korunur.

PowerShell başarıda `0`, işlem/doğrulama hatasında `1`, parametre
bağlama hatasında PowerShell kodunu verir. Export Python CLI'ın
`0/1/2/3` kodunu korur. `teslim_hazirla.ps1` aynı Prepare yolunu çağırır.

`tools/docker_check.py` yeni bir `artifacts/` çıktı klasörü ve yerel
Docker motoru ister. Yalnız yapay `teslim_kabul_test` kaynağından
PostgreSQL 17 arşivi üretip ayrı hedefe yükler. Şema/veri/rol/dosya,
HTTP/grafik, hata/kesinti, kalıcılık, Linux kapısı ve güncellik denetlenir.
Canlı bağlantı ortamı aktarılmaz. Test parolaları kayıtta maskelenir.

Ayrı CI işi imajı kurar, aynı aracı çalıştırır ve yapay raporu yükler.
Yalıtılmış senaryoda hedef ağ `internal: true`, normal Start
`--pull never` kullanır. Ağ ayarı konteynerle sınırlıdır. Konteyner
içi HTTP/grafik ve dış TCP'nin başarısızlığı birlikte sınanır. Host
tarayıcı portu normal ağda ayrıca denetlenir.

```powershell
.venv\Scripts\python.exe tools/docker_check.py --context desktop-linux --output artifacts/docker-kabul-yeni
```

Yerel kabul 8503 portunu kullanır. Teslim ekranını önce Stop ile
kapat, sonra Start ile yeniden aç. Araç kendi projelerini kapatır
ve alanları korur. Her çalıştırmada yeni çıktı klasörü seç. Başarıda
`report.json`, hatada son başarılı adımlar ve maskelenmiş `failure.log`
korunur. Python yalnız geliştirici kabulü için gerekir.
[Yerel kabul ayrıntıları](arsiv/teknik_2026-11-23.md#docker-tek-komutla-kullanım)


### Docker kabul senaryoları

Bu senaryolar kaynak bilgisayarda ve CI'da uygulandı. İkinci fiziksel
Windows bilgisayarındaki ilk kurulum, [teslim sınırı](../proje_plani.md#6-bilinen-sınırlar-özet)
olarak kayıtlıdır. [Kullanıcı kontrolleri](teslim.md#kabulün-kapsamı)

- Boş Docker ortamına kurulum ve aynı paketi tekrar hazırlama.
- Eksik/bozuk dosya, yanlış model veya uyumsuz şemada aktarımın reddi.
- Kaynak/kopya veri karşılaştırması; migration ve resmi dosya hash eşleşmesi.
- API hesabıyla yazmanın reddi; ekranın DB bağlantısı/parolası almaması.
- Yalnız `127.0.0.1:8503` ekran erişimi ve mevcut yerel uygulamayla birlikte
  çalışma; API/DB kesintisi, yeniden başlatma ve API–ekranın birlikte
  yeniden oluşturulması.
- Durdur/aç ve konteyner yenilemesinde verinin korunması; yeni paket
  geçişinin başarısızlığında önceki pakete dönüş.
- Kapalı gösterimde olasılık çıkmaması, gün değişince eski tahminin
  gösterilmemesi; açma/kapatma koşullarının yapay testlerle Linux'ta doğrulanması.
- Hazırlanmış sistemin internet kapalıyken açılması.

### Docker servis bağlantısı ve gösterim bakımı

API Docker DB'sini SELECT hesabıyla, ayar ve gölge alanlarını salt
okunur açar. UI API ağını paylaşır ve `http://127.0.0.1:8000`
üzerindeki mevcut sözleşmeyi kullanır. Ekran
`http://127.0.0.1:8503` üzerindedir. UI yalnız salt okunur ayar
alanı alır, DB adresi veya parolası almaz.

`DELIVERY_MANIFEST_PATH=/app/config/.delivery_ready.json` ile UI
`DeliveryState` kaydını okur. Aktarım bildirimi şöyledir.

> Teslim kopyası · Veri aktarımı: … · İstanbul · Otomatik veri toplama yapılmaz.

Bildirimin İstanbul saati paketin UTC hazırlama zamanından gelir.
`_test` kopyası yapay veri uyarısı gösterir. Dosya eksik veya geçersizse
aktarım uyarısı görünür ve fiyat/grafik çalışır. Bu ayarı almayan
normal Windows ekranı hazırlık kaydını okumaz. `prepared.json`
bilgisayardaki hazırlık/seçim işlemlerine aittir.

Kod değişince yeni imaj ve aynı kodla yeni Export/Prepare gerekir.
Eski paketin kod SHA'sı korunur. Günlük açılış Start ile, gösterim
bakımı seçili kopyanın sabit Compose ve imajıyla yapılır.

```powershell
. .\scripts\teslim_ortak.ps1
$script:DeliveryRoot = (Get-Location).Path
$teslimSecim = Get-DeliverySelection
$teslimHazir = Read-DeliveryRecord $teslimSecim.current
```

Gösterim bakımı yalnız hazır Docker kopyasında çalışır. Native
Windows onayı aktarılmaz. `--evaluation` paketteki
`degerlendirme_…` klasörünün **adını** alır. Dış veya Windows
yolu reddedilir.

```powershell
Invoke-DeliveryCompose $teslimHazir @('run', '--rm', '--no-deps', '--pull', 'never', '-T', 'transfer', 'python', '-m', 'app.delivery', 'shadow-display', '--bundle', '/bundle', '--evaluation', '<DEGERLENDIRME_KLASOR_ADI>')
Invoke-DeliveryCompose $teslimHazir @('run', '--rm', '--no-deps', '--pull', 'never', '-T', 'transfer', 'python', '-m', 'app.delivery', 'shadow-display', '--bundle', '/bundle', '--disable')
```

Açılış; paket ve hazır kopya, veri/şema/rol/dosya uyumu, ön kayıtlı
model, 5 Ocak 2027 kesin görüntüsü, `met` sonucu ve bugünkü tarihi
doğrular. Erken açma veya tarih parametresi yoktur. Başarı JSON'u
`enabled` ve paket SHA'sını verir. Çıkış kodları teslim CLI'ıyla
aynıdır. Eğitim, yeni tahmin ve pickle yüklemesi yapılmaz. Rapor, model
ve resmî kayıtlar korunur.

Hazırlık kaydındaki `display_enabled: false` ilk durumu bildirir.
Güncel onay Linux kopyasında mutlak rapor yoluna bağlanan
`gosterim_onayi.json` dosyasıdır. `check` yalnız bu dosya ile
`gosterim_onayi.lock` dosyasını ayrı kontrol dosyası sayar. Kapalı
veya açık onayın model, aile, tarih ve paket raporu bağı doğrulanır.
Fazladan dosya, bozuk/yabancı onay ve sembolik bağlantı reddedilir.

API onayı istek sırasında okur. Değişiklik servis başlatmayı veya model
yüklemeyi gerektirmez. Gerçek olasılık yalnız İstanbul takviminde
dünün uygun kaydından gelir. Tahmin hatasında fiyat/grafik sürer. Yeni
teslim kopyası kapalı başlar.
[Servis ve gösterim kabulü](arsiv/teknik_2026-11-23.md#docker-servis-bağlantısı-ve-gösterim-bakımı)
· [Docker geliştirme geçmişi](gecmis.md#aşama-9-docker-teslim-yazılımı-ve-yerel-kabul)


## Haftalık yedek

Canlı veritabanı, resmi gölge kayıtları ve dondurulan modelin kanıtları
yalnız bu bilgisayardadır; kaçan veya kaybolan gözlem geriye dönük
toplanamaz. Bu yüzden her Pazar [haftalık kontrol](#gölge-kayıtlarının-kontrol-sırası)
bittikten sonra ve 5 Ocak 2027 kesin değerlendirmesinden sonra yedek alınır
([20 Kasım kararı](../proje_plani.md#5-kararlar)). Yeni kod veya görev yoktur:
yedek, [dışa aktarma](#dışa-aktarma-ve-paket-sözleşmesi) paketidir.

| Kopya | Yer | Koruduğu durum |
|---|---|---|
| Yerel | `E:\FiyatTakip_Yedek\yedek_<tarih>` (C:'den ayrı fiziksel disk) | C: diskinin bozulması |
| Bulut | `%OneDrive%\FiyatTakip_Yedek\yedek_<tarih>` | Bilgisayarın arızası veya kaybı |

Her yedek klasöründe iki bölüm vardır:

- `paket/`: Export paketi. Veritabanının `public` şemasının tam dökümü
  (`database.dump`), `config/` dosyaları, dondurulan modelin
  etiket/girdi/bölme/model kanıtları, manifesti tamamlanmış tahmin ve
  değerlendirme klasörleri ve bunların görüntüleri. Her dosyanın SHA-256'sı
  `manifest.json` içindedir.
- `kayitlar/logs` ve `kayitlar/discovery`: tur, keşif ve gölge logları ile
  keşif raporları. `verify` paket klasöründe fazladan dosya kabul etmediği
  için paketin yanına konur.

Yedeğe girmeyenler: `data/teslim/` (Docker kopyasının durum ve parola
dosyaları; parola buluta taşınmaz), `%APPDATA%\postgresql\pgpass.conf`,
`artifacts/` (tamamlanmış incelemelerin kanıtları; on binlerce dosya ve bu
hesabın okuyamadığı `b3_*` klasörleri içerir, sonuçları belgelerde
özetlenir) ve Git dışı yerel notlar.

Komut proje kökünde, kullanıcının terminalinde çalıştırılır. 10:00/22:00
turu, 11:00 gölge görevi veya Pazar 14:00 keşfi sürerken çalıştırılmaz.
`DATABASE_URL` mevcut şifresiz kaynak adresidir. Blok ilk hatada durur:

```powershell
& {
    [Console]::OutputEncoding = [Text.Encoding]::UTF8
    if (-not $env:OneDrive) { throw 'OneDrive klasörü bulunamadı' }
    $py = '.venv\Scripts\python.exe'
    $ad = "yedek_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    $yerel = Join-Path 'E:\FiyatTakip_Yedek' $ad
    $bulut = Join-Path $env:OneDrive "FiyatTakip_Yedek\$ad"
    & $py -m app.delivery export --output "$yerel\paket"
    if ($LASTEXITCODE -ne 0) { throw "Export tamamlanmadı (çıkış $LASTEXITCODE)" }
    & $py -m app.delivery verify --bundle "$yerel\paket"
    if ($LASTEXITCODE -ne 0) { throw "Yerel paket doğrulanamadı (çıkış $LASTEXITCODE)" }
    foreach ($klasor in 'logs', 'discovery') {
        robocopy "data\$klasor" "$yerel\kayitlar\$klasor" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "data\$klasor kopyalanamadı (robocopy $LASTEXITCODE)" }
    }
    robocopy $yerel $bulut /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "OneDrive kopyası tamamlanmadı (robocopy $LASTEXITCODE)" }
    & $py -m app.delivery verify --bundle "$bulut\paket"
    if ($LASTEXITCODE -ne 0) { throw "OneDrive paketi doğrulanamadı (çıkış $LASTEXITCODE)" }
    "Yedek tamamlandı: $yerel ve $bulut"
}
```

Çıktıda bakılacaklar:

- Export satırları: `Paket SHA-256` ve `Model manifest SHA-256`. İkincisi
  ön kayıtlı `89c819ed…4cf2` olmalıdır.
- İki `verify` satırı: aynı `bundle_sha256` (Export'un paket SHA-256'sı)
  ve aynı `files` sayısı.
- Son satır: `Yedek tamamlandı`. OneDrive simgesinde klasörün “güncel”
  görünmesi bulut yüklemesinin bittiğini gösterir; `verify` yalnız yerel
  OneDrive klasörünü sınar.

Çıkış 3, ortak kilidin dolu olduğunu (tur, keşif veya gölge kaydı sürüyor)
gösterir; iş bitince yeni zaman damgasıyla tekrar çalıştırılır. Çıkış 1 veya
robocopy hatasında yarım kalan klasör yedek sayılmaz. Git'te commit edilmemiş
değişiklik varsa manifestteki `source_dirty` alanı `true` olur; bu, yedeği
geçersiz kılmaz, yalnız o anki kod durumunu kaydeder.

Bütün yedekler proje sonuna kadar silinmeden tutulur (her biri yaklaşık
106 MB; 5 Ocak 2027'ye kadar toplam yaklaşık 1 GB). Paket biçiminin geri
yüklenebilirliği [Docker kopyasına aktarımla](#docker-kabul-senaryoları)
doğrulanmıştır; yedekten yalnız ayrı Docker kopyası hazırlanabilir. Canlı
sistemi yedekten yeniden kurmak kullanıcı kararı ve ayrı plan gerektirir.

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

Tarihli saha ve kabul incelemeleri
[arşivdeki sınırlar bölümündedir](arsiv/teknik_2026-11-23.md#bilinen-sınırlar).

- **Docker ve Windows bağlamı.** Eski `COPY .` denemesi Windows'ta
  erişim hatası verdi. Güncel Dockerfile yalnız gerekli kaynakları
  kopyalar. Klasör izinleri korunur. Dışlamalar yapay dosyalı ayrı
  bağlamda sınanır. Yerel temiz klasör ve yalıtılmış ağ kabulünün
  kapsamı kaynak bilgisayardır.
  İkinci fiziksel Windows bilgisayarında kurulum ve host interneti
  kapalı kullanım teslim sınırıdır. [Proje planı](../proje_plani.md#6-bilinen-sınırlar-özet)
- **Teslim yolu.** PowerShell 5.1 ve `LongPathsEnabled = 0` ile sınır
  259 karakterdir. `data\teslim\paketler\<paket>\` altında kullanılan
  pakette proje yoluna yaklaşık 147 karakter eklenir (en uzun iç yol
  103). Proje yolu yaklaşık 110 karakteri aşarsa Prepare yarıda
  kalabilir. [İlk kurulum](teslim.md#i%CC%87lk-kez-başka-bilgisayara-kurma)
- **Bağımlılıklar.** ML ve web paketleri `pyproject.toml` içinde kesin
  sürümlüdür ve yerel ortamla Docker kilidinde aynıdır. Pydantic,
  curl_cffi, Psycopg ve tzdata aralıkla tanımlıdır. CI aralık içindeki
  paketi kurar. Yerel ortam, Docker ve CI kendi testlerinden geçer.
  Teslime kadar sürüm kararı ve CI'da bağımlılık kaynaklı kırılma
  koşulu [plandadır](../proje_plani.md#bilerek-değiştirilmeyen-davranışlar).
  [20 Kasım sürüm karşılaştırması](arsiv/teknik_2026-11-23.md#bilinen-sınırlar)

- **Hepsiburada arama API'si.** Erişim engellenirse `search_api`
  raporlanır. İkinci sayfadan itibaren hedefe uyan yeni telefon
  bulunmazsa sayfalama alaka sırası varsayımıyla durur. Kartlar,
  API kayıtları ve seçenek listesi keşfedilebilir kapsamı belirler.
  `model_filter_missing`, `html_partial` ve reddedilen adaylar sonucu
  kısmi bırakabilir.
- **Hepsiburada model filtresi.** iPhone dışındaki markalarda genel
  arama kullanılır. HTML yalnız ilk 36 kartı gösterebildiği için
  kalabalık aramalar eksik kalabilir (`html_partial`).
- **Trendyol arama kapsamı.** Reklam kartları sayfaları kaydırabilir
  ve bazı ürünlere sayfalama ile ulaşılamaz (`count_mismatch`).
  Kardeş sayfalar varyant listesinden gelebilir. Arama ve varyantlar
  satıştaki sayfaları gösterir. Önceden kaydedilen stoksuz sayfa
  katalogda kalır.
- **Renk.** Trendyol renk seçicisi satıcının yazdığı adı verir.
  Örneğin `trendyol_762254869` varyant listesi bulunmadığı için
  “Çok Renkli” kaldı. Renk gösterim alanıdır. Platform renkleri
  birleştirilmez ve ürün kimliğine katılmaz.
- **4G/5G.** `network: "4G"` hedefi ağ alanı boş ve başlığında
  5G bulunmayan sayfayı 4G sayabilir. Bu durumda eksik 5G kaydı
  yanlış 4G ürününe girebilir. 4G ürün adında 4G eki aranmaz.
- **Garanti ve RAM.** Ürün kimliğine katılmaz. Yurt dışı sürüm
  garanti alanından bağımsız olarak addaki “International Version”,
  “Global Version” veya “Yurt Dışı” ifadeleriyle elenir. Adında
  işaret bulunmayan sürüm ayırt edilemez. Garanti ve RAM yalnız
  Trendyol keşif raporunda bilgi olarak tutulur.
- **Katalog.** Keşif mevcut sayfanın rengini veya ürün bağını
  güncellemez. Renk kaynağı gibi bir kural değişirse katalog yeniden
  kurulur. Sonradan eklenen `exclude_terms` ve `network` kuralları
  mevcut sayfaları kendiliğinden çıkarmaz.
- **Sürekli işletim.** Turun zamanında başlaması için bilgisayar
  açık, uyanık ve kullanıcı oturumu açık olmalıdır. Uyku, kapalı
  bilgisayar, kapalı oturum (Windows Update sonrası dahil),
  modern bekleme ve süren önceki tur
  (`IgnoreNew`) gecikme veya atlamaya yol açabilir. Yeni gecikme
  haftalık kontrolde [log ve olay günlükleriyle](#geç-veya-kaçan-turun-nedeni)
  incelenir. Pil ve güç sınırları [zamanlanmış turdadır](#zamanlanmış-tur-görev-zamanlayıcı).
- **Bulut ve sık tarama.** Tarihli GitHub denemelerinde Hepsiburada
  yanıt verdi. Trendyol HTTP 403 veya ürün durum verisi eksik sayfa
  döndürdü. Toplama yerel bilgisayarda kalır. Erişim engeli aşılmaz.
  Art arda sık Trendyol taraması geçici engel oluşturabilir.
- **Fiyat ve stok kapsamı.** Kayıtlar tur anındaki durumu gösterir.
  İki tur arasındaki değişim gözden kaçabilir. Sayfa yapısı
  değiştiğinde ayrıştırıcı hata raporlayabilir ve bakım gerekebilir.

- **Hepsiburada sayfasının model değiştirmesi.** Aynı adres farklı
  model gösterebilir. Kimlik doğrulaması `identity` döndürür ve
  fiyatı dışarıda tutar. Hedefli incelemeyle bağlantı pasife alınır
  veya katalogdan çıkarılır. Kalıcı çıkarmada ürün bağı
  `retired_listing_bindings` içinde tutulur.
- **Trendyol adres ve ürün kodu.** Model/kapasite doğrulamasından
  sonra URL'deki `-p-` kodu ile yapısal `product.id` eşleşmezse
  `identity` döner. Fiyat kaydedilmez. Aynı ürüne kalıcı
  yönlendirme de bu hatayı verebilir. 19 Kasım'da iki eski adres
  pasife alındı. Mevcut hedefler aynı üründe etkin kaldı.
  `trendyol_1212833893 → trendyol_985256829` ve
  `trendyol_1135932836 → trendyol_985256864`. Pasif kayıt ve
  geçmiş ürün bağı korunur. Keşif kaydı kendiliğinden açmaz.
  [Kaynak bakımı ve canlı kabul geçmişi](gecmis.md#sürekli-işletim-keşif-ve-kaynak-bakımı-22-ekimden-itibaren)
- **`invalid_host`.** Hepsiburada bazen `www3.hepsiburada.com` gibi
  izin dışı alana yönlendirir. Geçici olayların nedeni
  doğrulanmadı. İzin listesi mevcut hedeflerle sınırlıdır.
- **Otomatik kabulde renk.** Trendyol renk seçicisi ad verir.
  Hepsiburada kaynakları normalleştirilince eşleşmelidir.
  Belgelenen tek eş anlam `blue` → `mavi`dir. Başlık renkleri
  `TITLE_COLORS` ile tanınır. Yeni uyuşmazlık gerçek kayıtla incelenir.
- **Alan çelişkileri.** Başlık ve özellik çelişen yeni aday
  kabul edilmez. Örnekler arasında Trendyol 797850359 (5G/4G,
  12/8 GB RAM) ve Hepsiburada HBCV0000E8DHJL (256/512 GB) vardır.
  E8DHJL'nin mevcut kaydı 28 Ekim kararıyla izlenir.
- **Stoksuz Hepsiburada JSON-LD'si.** 0,00 TL ve `InStock` stokta
  olmayan sayfada da görünebilir. Tükendi kararı satıcı listesine
  dayanır.
- **Cimri.** [Kullanım uygunluğu](#kullanım-değerlendirmesi)
  doğrulanmadı. Eşleştirme kapsamı [README'dedir](../README.md#-güncel-kapsam). Tarihsel satıcı kapsamı
  ve günlerin bağımsız ölçümleri bilinmez. Grafik günlük satıcı,
  yeni veya yenilenmiş ürün alanı taşımaz. Bu nedenle her fiyatın
  yeni ürüne ait olduğu başlık ya da kategoriden doğrulanamaz.
  Akakçe örneği HTTP 403 döndürdü. Erişim engeli aşılmaz.
- **ML sonuçları.** Aylık ve marka düzeyindeki üstünlük değişir.
  Ürün puanları ve yüksek olasılık kovaları sınırlı destek taşır.
  Cimri ölçümünü kendi kaynağımız için ayrı gölge değerlendirmesi
  izler. [İlk deney](#gerçek-deneyin-ilk-değerlendirmesi)
  · [Saklı test](#4-kasım-2026-saklı-test-sonucu)
- **İlk gölge raporu.** Veri aralığı ve olay desteği yetersiz,
  kalibrasyon farkları ön kayıtlı eşiklerin dışındaydı. Erken rapor
  kesin karar veya ayar değişikliği için kullanılmaz.
  [Değerlendirme kuralları](#gölge-değerlendirmesi-python--m-appml-shadow-evaluate)
- **Cimri eğitim uç değerleri.** 4 Kasım incelemesinde
  `ratio_min_30d` alanı 87 satırda 3'ün üstünde veya 1/3'ün
  altındaydı. Uç değerler `StandardScaler` sapmasını yükseltti.
  R2'nin normal aralıktaki duyarlılığı düşüktür. R1'in kova kuralı
  ayrı çalışır. Neden ve veri temizliği, yeniden model geliştirilirse
  ele alınır. [Ölçüm ayrıntıları](arsiv/teknik_2026-11-23.md#bilinen-sınırlar)


### Gölge mod ön ölçümünün riskleri (4 Kasım 2026)

4 Kasım 2026, 12:57 UTC görüntüsündeki ön ölçümde eksik 22:00
başlangıçları nedeniyle `missing_ratio_30d` ortalaması kendi
serimizde 0,24, eğitimde 0,005'ti. Yaklaşık 5 standart sapmalık
fark ve daha kısa geçmiş, olasılık ölçeğini etkileyebilir.
Model Cimri günlük minimumuyla eğitildi, kendi başlangıcımız
22:00 turuna dayanır. 6.4 bu farkı bilgi amaçlı kırılımlarla izler.
Güncel sayılar [README'de](../README.md#-güncel-kapsam), kesin
koşullar [6.5 planındadır](../proje_plani.md#65-kontrol-planı).

11:00 tahmini, pencerenin ilk sabah turundan sonra kaydedilir.
Girdi hesabı o sabahın fiyatını kullanmaz. Yerel kayıt parmak
izleri bütünlüğü denetler. Dondurulan model aynı Python, NumPy,
scikit-learn ve LightGBM sürümlerini ister. Yeniden dondurma yeni
model sayılır.
[Tarihli ölçüm, varsayımlar ve kapsam](arsiv/teknik_2026-11-23.md#gölge-mod-ön-ölçümünün-riskleri-4-kasım-2026)
