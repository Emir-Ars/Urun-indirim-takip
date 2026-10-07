# Teknik rehber

Bu belge, [README](../README.md)'de özetlenen sistemin **nasıl** çalıştığını
ayrıntısıyla anlatır: dosyaların görevleri, komutlar, keşif ve fiyat okuma
adımları, kimlik kuralları, rapor alanları, bilinen sınırlar ve geliştirme
geçmişi. Kararların ve aşama durumunun ana kaynağı
[proje_plani.md](../proje_plani.md) dosyasıdır.

## İçindekiler

- [Dosyalar ve sorumlulukları](#dosyalar-ve-sorumlulukları)
- [Komutların ayrıntısı](#komutların-ayrıntısı)
- [Yeni telefon ekleme: bütün kurallar](#yeni-telefon-ekleme-bütün-kurallar)
- [Keşif nasıl çalışır](#keşif-nasıl-çalışır)
- [Fiyat okuma nasıl çalışır](#fiyat-okuma-nasıl-çalışır)
- [Veritabanı (PostgreSQL)](#veritabanı-postgresql)
- [Kimlik kuralları](#kimlik-kuralları)
- [Testler ne kanıtlar, ne kanıtlamaz](#testler-ne-kanıtlar-ne-kanıtlamaz)
- [Bilinen sınırlar](#bilinen-sınırlar)
- [Geliştirme geçmişi](#geliştirme-geçmişi)

## Dosyalar ve sorumlulukları

### Ayarlar: `config/` (kod değil, veri)

| Dosya | Ne işe yarar | Kim yazar |
|---|---|---|
| `discovery.json` | Takip edilecek telefonlar ve tarama sınırları | Kullanıcı |
| `catalog.json` | Keşfin doğruladığı ürünler ve sayfalar | Keşif (elle yazılmaz) |
| `runtime.json` | Zaman aşımı, tekrar deneme, istekler arası bekleme (3 sn) | Kullanıcı, nadiren |

### Ortak parçalar: `app/`

| Dosya | Ne işe yarar |
|---|---|
| `contracts.py` | Verinin şekilleri ve doğrulaması (Pydantic V2 strict): `Product`, `Listing`, `Catalog`, `PriceObservation`, keşif hedefleri ve raporu. Hatalı veri içeri giremez (ör. fiyat alanına "Tükendi"). Yalnızca biten aşamanın kullandığı tanımları içerir. |
| `settings.py` | Ayar dosyalarını okur. `CATALOG_PATH`, `DISCOVERY_PATH`, `RUNTIME_PATH`, `SCRAPE_LOCK_PATH`, `LOG_DIR`, `DISCOVERY_REPORT_DIR` ortam değişkenleriyle başka dosya veya klasör gösterilebilir. |
| `scrape_lock.py` | Siteye giden bütün girişlerin paylaştığı kilit (`data/scrape.lock`). Fiyat turu, keşif ve üç canlı kontrol aracı (`live_scraper_check`, `live_discovery_check`, `market_history_probe`) alır; biri sürerken diğeri beklemeden "sürüyor" deyip çıkar. Süreç çökse bile işletim sistemi kilidi bırakır. |
| `console.py` | Komut satırı araçlarının ortak çıktı yardımcıları: UTF-8 çıktı (`utf8_output`; fiyat turu, keşif, `app.database` ve canlı kontrol araçları kullanır), `<ön ek>_<tarih-saat>.log` dosyası açma ve stdout/stderr'i log dosyasına da yazan `tee_output` (yalnız zamanlanmış tur ve keşif). pythonw.exe altında ekran akışları yoktur (`None`); hepsi buna dayanır. |

### Fiyat okuma: `app/scraper/`

| Dosya | Ne işe yarar |
|---|---|
| `http.py` | İnternete açılan tek kapı. `curl_cffi` + `impersonate="chrome120"`; yalnızca izinli alan adları, zaman aşımı, sınırlı tekrar, istek aralığı (alan adı başına, bütün istemciler arasında ortak), yönlendirme kontrolü, indirme sırasında 8 MB gövde sınırı, istek bütçesi. 401/403/418/429 yanıtları `blocked` olarak sınıflanır. Playwright, Selenium veya `requests` kullanılmaz. |
| `parsing.py` | Ortak yardımcılar: fiyatı kuruşa çevirme (`money`), metin normalleştirme, sayfaya gömülü JSON okuma ve **kimlik kuralları** (`identify`, `verify_identity`, `matches_model`, `network_type`). Keşif ve scraper aynı kuralları kullanır. |
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
| `__main__.py` | Komut satırı: `python -m app.discovery [--dry-run] [--target KEY]`, `--scheduled --dry-run` (Görev Zamanlayıcı) ve `--apply-report RAPOR`. |

### Veritabanı: `app/database/`

| Dosya | Ne işe yarar |
|---|---|
| `connection.py` | PostgreSQL bağlantısı. Adres `DATABASE_URL` ortam değişkeninden okunur (şifresiz); şifre PostgreSQL'in `pgpass.conf` dosyasındadır. Oturum saati UTC; bağlanma 10 sn, tablo kilidi bekleme 30 sn ile sınırlı (yarım bırakılmış bir işlem turu sonsuza kadar bekletmez, hata verir). |
| `migrate.py` | Migration koşucusu: `migrations/` altındaki numaralı SQL dosyalarını sırayla, her birini tek transaction'da ve yalnızca bir kez uygular; `schema_migrations` tablosuna parmak iziyle yazar. |
| `migrations/001_initial.sql` | Katalog kopyası, toplama turları ve sayfa sonuçları tabloları; bütün kurallar (`CHECK`, `UNIQUE`, yabancı anahtarlar). |
| `migrations/002_guards_and_comparability.sql` | İki yeni `CHECK` (Tükendi satırı fiyat taşımaz, çizili fiyat güncel fiyattan büyüktür), beş tabloda 15 tetikleyici (silmeyi ve `TRUNCATE`'i reddeder, kimlik alanlarını korur, yazılmış sayfa sonucunu dondurur), `product_run_prices` görünümü. |
| `migrations/003_closed_run_guards.sql` | İki tetikleyici işlevini yeniler: kapanmış turun sonuçsuz satırına yazımı ve kapanmış turun durum/bitiş zamanı değişimini reddeder; ilk sonuç ve `network` yeniden yazımını tur kapanışıyla sıraya alır. Veri satırlarını ve görünümü değiştirmez. |
| `catalog_sync.py` | `catalog.json`'u veritabanındaki kopyaya eşitler: `plan_sync` farkı veritabanına dokunmadan hesaplar, `sync_catalog` tek transaction'da yazar. |
| `runs.py` | Tur SQL'leri: veritabanı tur kilidi, yarım kalan turu kapatma, turu ve planlanan sayfaları açma, sayfa sonucunu (bir kez, yalnızca süren tura) yazma, süren turdaki `network` hatası satırını ikinci okumanın sonucuyla değiştirme (`rewrite_network_result`, tek istisna), turu kapatma, özet. |
| `__main__.py` | Komut satırı: `python -m app.database migrate` / `status` / `sync-catalog [--dry-run]`. Çıkış kodları: `0` başarılı; `1` komut başarısız (şema, katalog çakışması, bağlantı, ayar; mesaj stderr'e `Veritabanı komutu başarısız: …` diye yazılır); `2` argüman hatası. |

### Fiyat toplama turu: `app/collection/`

| Dosya | Ne işe yarar |
|---|---|
| `service.py` | Bir tur: şema kontrolü, yarım kalan turu kapatma, katalog eşitleme, planlama, her sayfayı mevcut scraper'la okuyup sonucunu hemen yazma, `network` hatası alan sayfaları tur sonunda bir kez yeniden okuma, turu kapatma. Scraper ile veritabanını bağlayan tek yer. |
| `__main__.py` | Komut satırı: `python -m app.collection [--prefix ÖN_EK] [--scheduled]`; ortak kilidi alır. `--scheduled` ile çıktı `data/logs/` altındaki log dosyasına da yazılır. |

### Zamanlayıcı: `scripts/`

| Dosya | Ne işe yarar |
|---|---|
| `zamanlayici_kur.ps1` | Fiyat toplama turunu Windows Görev Zamanlayıcı'ya kurar (her gün 10:00 ve 22:00, penceresiz); `-Kaldir` ile siler. Ayarları [Zamanlanmış tur](#zamanlanmış-tur-görev-zamanlayıcı) bölümündedir. |
| `kesif_zamanlayici_kur.ps1` | Haftalık keşfi Görev Zamanlayıcı'ya kurur (her Pazar 14:00, katalog yazmadan, penceresiz, kaçan çalışmayı telafi etmez); `-Kaldir` ile siler. Ayarları [Zamanlanmış keşif](#zamanlanmış-keşif-görev-zamanlayıcı) bölümündedir. |

### Testler ve CI

| Yer | Ne işe yarar |
|---|---|
| `tests/conftest.py` | Bütün testlerin emniyet kemerleri: her testte gerçek curl_cffi isteği kesilir (sahte istemci kullanmayı unutan test siteye gitmek yerine başarısız olur) ve kalıcı `DATABASE_URL` silinir. `db` fixture'ı yalnızca `TEST_DATABASE_URL`'deki, adı `_test` ile biten veritabanını kullanır ve her testten önce onu boşaltır; aynı anda iki pytest çalışırsa ikincisi en çok 30 sn bekler. `TEST_DATABASE_URL` yoksa veritabanı testleri yerelde atlanır; `CI` ortam değişkeni tanımlıysa (GitHub Actions tanımlar) başarısız olur. |
| `tests/test_http.py` | HTTP katmanı (88 test): hata kodları (`invalid_host` mesajı hedef alan adını yazar, sorgu metnini yazmaz), indirme sırasında 8 MB sınırı (parçalı/tek parça taşma, tam eşik, aktarımın durması, UTF-8 parçaları, boş yanıt, yarım gövdenin tekrar öncesi atılması), büyük hata/yönlendirme yanıtlarında aynı sınıflandırma ve istek bütçesi, yönlendirme kuralları, 5xx tekrarı ve bekleme süreleri, istekler arası bekleme, factory. Ayrıca mimari kural: `app/` içinde `requests`/`httpx`/`playwright`/`selenium` yok, `curl_cffi` yalnız `http.py`'de. |
| `tests/test_contracts.py` | Pydantic sözleşmeleri (74 test): satılabilir teklif fiyat ve satıcı taşır, puan ölçeği aşamaz, üstü çizili fiyat güncel fiyattan büyüktür, katalog kimlik/referans/alan adı kuralları, `money()` kuruş çevirimi. |
| `tests/test_trendyol_scraper.py`, `tests/test_hepsiburada_scraper.py` | Fiyat okuma (40 + 32 test): seçilen teklif, eşit fiyatta satıcı adı, çizili fiyat, Kritik Stok, Tükendi'nin yalnız açık sinyalle verilmesi, bozuk satıcı kayıtlarının reddi, ret nedenleri, `parse` dönüşümü. Sahte sayfa ve istemci; internete çıkmaz. |
| `tests/test_discovery.py` | Keşif (141 test): kimlik kuralları, sayfalama ve uyarı türleri, katalog birleştirme (aynı adaylar hep aynı kimlikleri alır), dry-run'ın kataloğa yazmaması, LF satır sonu, BOM'lu ayar dosyaları, UTF-8 çıktı, çıkış kodları ve gerçek `config/*.json` dosyalarının sözleşmeye uyması. Ekli aksesuarlar model, başlık/yapısal kapasite, birden çok ürün adı ve kategori düzeyinde reddedilir; kayıtlı 21 telefonun kimlik kabulü korunur. Zamanlanmış keşif (log ve tarihli rapor, `--dry-run` zorunluluğu, konsolsuz çalışma, kilit meşgul, program hatası, log açılamaması, rapor klasörünün baştan denetimi, özet satırı) ve `--apply-report` (siteye gitmez, canlı yazmayla bayt bayt aynı katalog, ikinci uygulamada yazmama, önizleme olmayan/bozuk/sarmalı/yabancı alan adlı/önizlemeyi aşan rapor reddi) ağsız sınanır. Trendyol filtre uyarısının tek yazılması ve tarama sonrası yazma hatasının ("Tarama bitti ama sonuç yazılamadı", çıkış 1; log dahil) "başlatılamadı"dan ayrılması da burada denenir. |
| `tests/test_collection.py` | Toplama turu (66 test; 61'i gerçek PostgreSQL'de): sahte scraper'larla her sonuç türü, Ctrl+C, tur ortasında veritabanı hatası, yarım kalan tur, başka süreçteki tur, iki kilidin her durumda bırakılması, pasif sayfa/ürün/platform, ön ek, çıkış kodları (keşif ve `live_scraper_check` kilit meşgulken 3 verir) ve zamanlanmış turun log dosyası (ekran akışı yokken ve log açılamazken dahil). Kapanış sonrası özet SQL hatası, bağlantının kapatılması ve Ctrl+C, elle/zamanlanmış girişlerde sınanır; turun ve sonuçların bütün alanları, kilitler, log ve sonraki tur korunur (7 test). Tur sonu ikinci okuma (18 test): `network` düzelince satırın değişmesi, ikinci hatada ilk satırın (mesaj ve zaman damgasıyla) kalması, `network` dışındaki hataların hiç yeniden okunmaması, bir sayfanın en çok bir kez yeniden okunması, ardışık 5 hatada durma ve düzelmede sayaç sıfırlama, veritabanı reddi, Ctrl+C, tur notu (ön ekle birlikte), görünümde sahte "karşılaştırılamaz" oluşmaması ve `rewrite_network_result`'ın yalnız `network` satırına ve süren tura yazması. |
| `tests/test_catalog_sync.py` | Katalog eşitleme (29 test; 13'ü gerçek PostgreSQL'de): kararlar veritabanısız, yazma/deneme/çakışma ve komut satırı veritabanında. |
| `tests/test_database.py` | Migration koşucusu, şemanın bütün `CHECK`/`UNIQUE`/yabancı anahtar kuralları (her biri geçerli ve geçersiz örnekle), `migrate`/`status` komutları (yeniden adlandırılan migration dahil) ve iki emniyet kemerinin kendisi; 002'nin iki `CHECK` kuralı, silme/kimlik değişimi/yazılmış sonucu değiştirme tetikleyicileri (her tabloda), kodun gerçek güncellemelerinin hâlâ geçtiği ve "bilerek silme" yolu da burada denenir. 003 için kapanmış turun ilk sonuç yazımı, durum/bitiş zamanı koruması, not güncellemesi, eşzamanlı kapanış/yazım ve mevcut kayıtlarla migration geçişi sınanır (150 test; 138'i gerçek PostgreSQL'de). |
| `tests/test_comparability.py` | `product_run_prices` görünümü: aynı sayfa kümesi, hata (girerken ve çıkarken), yeni sayfa, Tükendi, cevapsız ürün, ürünlerin ayrı karşılaştırılması, `--prefix` turu, süren ve yarıda kalan turların dışarıda kalması, uzun boşluk (14 test, hepsi gerçek PostgreSQL'de). |
| `tests/test_market_history_probe.py` | Piyasa geçmişi araştırmasında aday tablo satırları, ürün kimliği, sentetik 365 günlük grafik yanıtı, eksik/bozuk fiyat ve tablo uyuşmazlığı (12 ağsız test). Gerçek fiyat dizileri Git dışındaki yerel raporlardadır. |
| `tests/test_live_discovery_check.py` | Ham keşif kanıtı kaydı (13 ağsız test): HTML/JSON baytları, istek bütçesi ve tekrarlar, bozuk JSON'un korunması, tek hedef/yeni klasör zorunluluğu, kilit ve disk hatası, platformların ayrı kaydı ve eski komut çıktısının korunması. Dosyalar normal veya ters sırada listelense de kayıt denetimi aynıdır. |
| `tests/fixtures/discovery/` | Testlerin kullandığı örnek site yanıtları ve kataloğun sabit bir kopyası (`catalog.json`); testler gerçek kataloğa bağlı değildir. `phone_identity_examples.json`, kullanıcının 6 Ekim iPhone 15 kontrolündeki 21 sayfanın özgün adlarını, doğrulanan kapasitesini ve kaynak dosya bilgisini taşır; testler Git dışındaki ham dosyalara ihtiyaç duymaz. |
| `tests/manual/live_scraper_check.py` | Katalogdaki sayfaları canlı okur; bütün satıcıları gösterir. İsteğe bağlı `product_key` ön eki (ör. `samsung_`) ile yalnız o ürünler; sayfa seçimi toplama turuyla aynı fonksiyondur. Başka bir tarama sürüyorsa (ortak kilit) çıkış kodu 3'tür. |
| `tests/manual/live_discovery_check.py` | Keşfi kataloğa yazmadan canlı çalıştırır; `--trace` ile her kararın nedenini gösterir. Normalde raporu `data/discovery_report.json` dosyasının üzerine yazar. `--save-responses KLASOR`, tek hedefin ham HTML/JSON yanıtlarını ve raporunu yeni klasöre kaydeder; karar izini de basar. |
| `tests/manual/market_history_probe.py` | Akakçe için tek örnek sayfayı, Cimri için ürün sayfası ve grafik API'sini ortak HTTP katmanı ve tarama kilidiyle okur. Cimri'nin tarihli fiyat noktalarını Git dışındaki yerel JSON raporuna yazar; ham HTML'yi ve veritabanını yazmaz. |
| `.github/workflows/ci.yml` | Her push/pull request'te geçici bir PostgreSQL 17 açar (yereldeki gibi `C.UTF-8`) ve Black, Flake8 ile bütün testleri çalıştırır. |
| `.github/workflows/bulut-deneme.yml` | Elle tetiklenen bulut denemesi (zamanlama, veritabanı ve gizli anahtar yok): `tests/manual/live_scraper_check.py samsung_galaxy_a55_128gb` ile 4 sayfayı (Trendyol ve Hepsiburada) GitHub'ın makinesinden okur; her iki site de hatasız okunduysa başarılı, aksi hâlde başarısız biter ve sonucu çalışmanın özet sayfasına yazar. Soru: siteler bulut adreslerini engelliyor mu ([proje_plani.md](../proje_plani.md) Bölüm 8). **İlk sonuç (6 Ekim):** Hepsiburada'nın 3 sayfası okundu, Trendyol'un sayfası HTTP 403 (`blocked`) verdi; tek örnek (bkz. "Bilinen sınırlar"). Tetiklemek: GitHub → Actions → "Bulut deneme (canlı okuma)" → Run workflow. Bilgisayardaki tur saatlerinde (10:00–10:40, 22:00–22:40) tetiklenmemelidir: `data/scrape.lock` bu makineye özgüdür, GitHub'daki çalışma onu almaz ve aynı siteye iki yerden gidilir (iş tanımı bunu denetlemez, yalnız yorumda uyarır). |

## Komutların ayrıntısı

Windows ve PowerShell, Python sanal ortamı `.venv`:

```powershell
# Kurulum: yalnız biten aşamanın bağımlılıkları + test/biçim araçları
.venv\Scripts\python.exe -m pip install -e ".[dev]"

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
.venv\Scripts\python.exe -m black --check app tests
.venv\Scripts\python.exe -m flake8 app tests

# Keşif: önce kataloğu değiştirmeden rapor
.venv\Scripts\python.exe -m app.discovery --dry-run --target apple_iphone_15

# Keşif: doğrulanan yeni sayfaları kataloğa ekle
.venv\Scripts\python.exe -m app.discovery --target apple_iphone_15

# Zamanlanmış keşfin komutu (elle de çalışır): katalog yazılmaz; log data\logs\kesif_*.log,
# rapor data\discovery\kesif_*.json (aynı tarih-saat damgası)
.venv\Scripts\python.exe -m app.discovery --scheduled --dry-run --target apple_iphone_15

# İncelenen önizleme raporunu siteye gitmeden kataloğa ekle
.venv\Scripts\python.exe -m app.discovery --apply-report data\discovery\kesif_2026-10-04_14-00-03.json

# Haftalık keşfi Görev Zamanlayıcı'ya kur (her Pazar 14:00); -Kaldir ile siler
powershell -ExecutionPolicy Bypass -File scripts\kesif_zamanlayici_kur.ps1

# Keşif tanılaması: rapor + her kararın izi (katalog değişmez)
.venv\Scripts\python.exe tests\manual\live_discovery_check.py apple_iphone_15 --trace

# Adres kimliği incelemesi için tek hedefin ham yanıtları (yeni klasör gerekir)
.venv\Scripts\python.exe tests\manual\live_discovery_check.py apple_iphone_15 --save-responses data\kimlik_iphone15_20261006

# Canlı fiyat kontrolü: katalogdaki bütün sayfalar (veya yalnız bir ön ek)
.venv\Scripts\python.exe tests\manual\live_scraper_check.py
.venv\Scripts\python.exe tests\manual\live_scraper_check.py samsung_ | Out-File -Encoding utf8 data\scraper_samsung.json
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

### Piyasa geçmişi araştırması (Adım 8)

Kaynak seçimi için örnekler: `apple_iphone_16_128gb`,
`samsung_galaxy_s24_256gb`, `xiaomi_14t_pro_256gb`. Akakçe ve Cimri için
ürün geçmişi URL'si tarayıcıda ayrı ayrı bulunur; araç otomatik arama yapmaz.
Her çalışmada yönlendirme/tekrar dahil en çok dört HTTP denemesi yapılır ve
`data/scrape.lock` kilidi alınır. Cimri'de önce sayfanın model/kapasitesi ve
gömülü ürün kimliği doğrulanır; sonra aynı HTTP oturumuyla
`POST https://www.cimri.com/api/cimri` üzerinden `priceHistoryV2Query`
çağrılır. Örnek komut biçimi:

```powershell
.venv\Scripts\python.exe tests\manual\market_history_probe.py akakce apple_iphone_16_128gb "<ürünün HTTPS adresi>"
.venv\Scripts\python.exe tests\manual\market_history_probe.py cimri xiaomi_14t_pro_256gb "https://www.cimri.com/cep-telefonlari/en-ucuz-xiaomi-14t-pro-fiyatlari%2Ca2372365900"
```

Rapor varsayılan olarak `artifacts/market_history_probe/<kaynak>_<product_key>.json`
dosyasına yazılır (`--output-dir` başka bir yerel klasör gösterir); aynı örnek
tekrar çalıştırılırsa dosya güncellenir. Terminal yalnız
kısa özet gösterir. Cimri raporunda eski tarihten yeniye `history.points`
(`day`, `price_tl`), nokta/eksik fiyat sayısı ve gömülü tablonun grafikle
karşılaştırılması bulunur. `null` fiyat uydurulmadan korunur; kimlik veya ortak
tarihte fiyat uyuşmazlığı hata olur. Çıkış 0 okuma/ayrıştırma tamamlandı ve
**manuel inceleme gerekiyor**, 1 örnek ürün etkin katalogda yok (istek atılmaz),
2 HTTP/kimlik/veri hatası, 3 ortak kilit meşgul demektir. Testlerin geçmesi canlı API erişimini veya her günün ayrı fiyat
gözlemi olduğunu kanıtlamaz. Ham sayfa, veritabanı ve katalog değiştirilmez.

29 Eylül 2026'da [Akakçe kullanım sözleşmesinde](https://www.akakce.com/kullanim-sozlesmesi/)
ve [Cimri kullanım koşullarında](https://www.cimri.com/kullanim-kosullari)
içerik kopyalama/işleme kısıtları görüldü. Az sayıda sayfa teknik araştırma
için incelenir; düzenli geçmiş indirme ve projede saklama ayrıca
değerlendirilir. Kaynak seçilirse yalnız onun geçmişi ele alınır; iki sitenin
serileri birleştirilmez.

Kullanıcının çalıştırdığı üç Cimri canlı denemesinde ürün kimliği eşleşti;
her biri 365 nokta (30 Eylül 2025–29 Eylül 2026), 0 eksik fiyat ve gömülü
tablodaki 90/90 fiyat eşleşmesini verdi. Bu teknik doğrulama, fiyatların her
gün bağımsız ölçüldüğünü veya tarihsel satıcı kapsamını kanıtlamaz. Resmî
koşullardaki kopyalama/işleme kısıtları nedeniyle Cimri verisinin düzenli
indirilmesi ve veritabanına alınması bu araştırma sonunda başlatılmadı.

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

6 Ekim iPhone 15 ve 7 Ekim Galaxy S24 ham kayıtlarında 36 ürün sayfasının
canonical adresleri 13 grup (`-pm-`), 23 model/kategori adresiydi. Kabul edilen
24 adayın özgün adresleri korundu; diğer 12 sayfa başka model olduğu için
reddedildi. Gerçek farklı SKU canonical örneği görülmedi. Tam eşitlik koruması
7 Ekim'de kullanıcının bakım 2'ye özel onayıyla önleyici olarak uygulandı
([proje_plani.md](../proje_plani.md), Bölüm 7).

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
| `results` | Hedef × platform başına ayrıntı: adaylar (renk, RAM, garanti yazısı), uyarılar, taranan arama/ürün sayfası sayısı. RAM ve garanti yazısını yalnız Trendyol doldurur. |
| `added_products`, `added_listings` | Bu çalışmada eklenen ürünler/sayfalar. |
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

`rejected` içindeki kayıtlar (tek bir aday atlanır, tarama sürer):

| Kayıt | Anlamı |
|---|---|
| `candidate_rejected` | Aday sayfa doğrulanamadı; ayrıntıda neden ve ürün adı var (başka model, kapasite, ağ türü, yurt dışı sürüm, aksesuar…). Taramayı da kısmi sayar. |
| `catalog_conflict` | Sayfa katalogda başka bir ürüne bağlı; aday yazılmadı, mevcut kayıt korundu. |

Komutun çıkış kodu: `0` tam tarama, `2` kısmi tarama (doğrulanmış kayıtlar yine
eklenir; Hepsiburada arama API'si engelli olduğu için bugün her zaman 2; katalogla
çelişen aday, `catalog_conflict`, de taramayı kısmi sayar; hiç etkin hedef
yoksa sonuç listesi boştur ve çıkış yine 2'dir), `1` keşif başlatılamadı
(`--target` ile verilen anahtar `discovery.json`'da yok, ayar dosyası bozuk,
platform adaptörü yüklenemedi…) **ya da** tarama bitti ama sonuç kataloğa veya
rapora yazılamadı (disk, kilit zaman aşımı; mesaj "Tarama bitti ama sonuç
yazılamadı" der ve bu çalışmanın sonucu kaybolmuştur), `3` kilit meşgul (tur, başka bir keşif veya canlı kontrol
sürüyor). `--apply-report` için: `0` katalog güncellendi ya da eklenecek bir şey
kalmadı, `2` güncellendi ama katalogla çelişen aday atlandı, `1` hiçbir şey
yazılmadı (rapor okunamadı ya da geçersiz, önizleme değil, katalog önizlemeden
sonra değişmiş, yabancı alan adı…). `--scheduled` kodları tarama kodlarıyla aynıdır;
ek olarak log dosyası açılamazsa `1` döner ve keşif hiç başlamaz. Argüman hatası
(`--scheduled` `--dry-run` olmadan, `--apply-report` başka seçenekle) çıkış `2`
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
| `network` | HTTP | Bağlantı hatası, zaman aşımı veya 5xx; tekrarlardan sonra da sürdü. 5xx bilerek ayrı bir kod almaz (karar, 6 Ekim): geçicidir ve [tur sonu ikinci okuma](#tur-sonu-ikinci-okuma-adım-11) yalnız `network`'ü yeniden okuduğu için 5xx'i de kapsar. |
| `too_large` | HTTP | Başarılı yanıtın gövdesi indirme sırasında 8 MB sınırını aştı; aktarım durduruldu, tekrar denenmez. |
| `parse` | HTTP, scraper | Yanıt UTF-8 metin/JSON değil ya da sayfa verisi beklenen yapıda değil; teklif sözleşme doğrulamasından geçmedi. |
| `identity` | scraper, keşif | Sayfa hedef ürün değil: model, kapasite, dışlanan ifade, ağ türü ya da yenilenmiş/aksesuar/yurt dışı sürüm. |
| `no_eligible_offer` | scraper | Uygun satılabilir teklif yok, ama Tükendi için açık stok sinyali de yok. |
| `api_error` | Hepsiburada | Satıcı listesi veya fiyat API'si başarısız ya da satılabilir satıcı için boş yanıt verdi. |
| `plugin` | factory | Platform adaptörü yüklenemedi. |
| `validation`, `unexpected`, `storage` | toplama turu | Gözlem doğrulanamadı veya başka sayfaya ait; beklenmeyen istisna (ayrıntı loga yazılır); veritabanı değeri reddetti. Tur üçünde de sürer. |

## Veritabanı (PostgreSQL)

Fiyat toplama turlarının sonuçları PostgreSQL 17'de saklanır. Bugün şema,
`migrate`, katalog eşitleme, toplama turu, koruyucu kurallar (002) ve turlar arası
karşılaştırılabilirlik görünümü hazırdır. İlk tam tur 28 Eylül
2026'da 326 sayfanın tamamını 31 dakikada hatasız okudu. Günde 2 turu
Görev Zamanlayıcı başlatır ([Zamanlanmış tur](#zamanlanmış-tur-görev-zamanlayıcı);
durum: [proje_plani.md](../proje_plani.md) Bölüm 9).

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
  okunup yerine sonuç yazılabilir ([tur sonu ikinci okuma](#tur-sonu-ikinci-okuma-adım-11),
  `runs.rewrite_network_result`). Başka hata kodları ve biten turun satırları
  değiştirilemez. **`003_closed_run_guards.sql` 6 Ekim'de kullanıcı tarafından
  gerçek veritabanına uygulandı.** `003`, ilk sonuç
  yazımını da çalışan turla sınırlar; sonuç yazarken tur satırını işlem sonuna
  kadar `FOR SHARE` ile kilitler, eşzamanlı kapanışı sıraya alır. Kapanmış turun
  durumu ve bitiş zamanı değişmez, notu güncellenebilir. Mevcut kayıtlar ve
  görünüm korunur; `001` ve `002` değişmez. 19 yeni PostgreSQL testiyle
  toplam 571 test (`570 passed, 1 xfailed`, 0 atlandı; 219 PostgreSQL), Black ve
  Flake8 temiz. Uygulama sonrası salt okunur denetimde migration parmak izleri,
  iki işlevin SQL içeriği ve açık tetikleyicileri doğrulandı; 15 mevcut turun
  sonuç sayıları korundu, görünümün 827 satırı bağımsız hesapla eşleşti
  (`proje_plani.md`, Bölüm 7).
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
   (aşağıda [Tur sonu ikinci okuma](#tur-sonu-ikinci-okuma-adım-11)).
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

#### Kapanış sonrası hata kontrolü (bakım 6)

Turun kapanışı özet sorgusundan önce, autocommit bağlantıda kalıcıdır.
Özet SQL hatası veya özet okunurken kullanılan bağlantının kapanması, yazılmış
sonuçları ve `completed` durumunu değiştirmez; komut çıkış kodu 1 olur.
Kapanış sonrası Ctrl+C'de de tur `completed` kalır, çıkış kodu 130 olur.
Tur ortasında kesilme ve bağlantı kopması kuralları yukarıdaki gibi sürer.

Ctrl+C mesajı kapanmış ve yarım kalmış turu ayırır:

> Komut durduruldu. Tamamlanmış tur 'completed' kalır; yarım kalan tur 'interrupted' olarak kapatılır. Kapatılamadıysa bir sonraki tur kapatır.

7 Ekim kontrolünde 7 kalıcı sınama eklendi: doğrudan toplama girişindeki
özet hatası ve elle/zamanlanmış komutta üç kapanış sonrası hata durumu.
Gerçek SQL hatası üretilir, yalnız test bağlantısı kontrollü kapatılır veya
Ctrl+C taklit edilir; scraper'lar sahtedir. Bağımsız bağlantıdan turun bütün
alanları (bitiş zamanı dahil) ve yedi sonucun bütün sütunları hata öncesiyle
karşılaştırılır. Veritabanı kilidi başka bağlantıdan, dosya kilidi tekrar
alınarak doğrulanır; sonraki tur başlar ve eski tamamlanmış turu değiştirmez.
Zamanlanmış çalışmada hata mesajı ve çıkış kodu logda da bulunur. Eski kodda
5 sınama geçti; 2 Ctrl+C sınaması yalnız yanıltıcı mesaj yüzünden başarısızdı.
**Veri koruması kontrol edildi, mevcut davranış kabul edildi; kesinti mesajı
düzeltildi.** Toplama/kapanış/özet sırası, API, şema ve çıkış kodları değişmedi.
Bu kontrollü testler canlı turda bu hataların görüldüğü anlamına gelmez.

#### Tur sonu ikinci okuma (Adım 11)

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
  hatalı kalır; bu kalıcı çözüm değildir (sunucu, Aşama 9). Gerçek turda henüz
  görülmedi: `network` hatası olmayan turlarda ikinci okuma çalışmaz.

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
| Tetikleyiciler | Her gün yerel saatle 10:00 ve 22:00 | Karar ([proje_plani.md](../proje_plani.md) Bölüm 9). Görev Zamanlayıcı saati varsayılan olarak UTC'ye çevirir; script yerel saat yazar. |
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
  okunur ([Tur sonu ikinci okuma](#tur-sonu-ikinci-okuma-adım-11)). Kesinti tur
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
fiyat görevine dokunmaz). Karar (1 Ekim 2026, [proje_plani.md](../proje_plani.md)
Bölüm 8): keşif haftada bir kendiliğinden çalışır ve kataloğa **yazmaz**;
kullanıcı raporu inceler, sonra `--apply-report` o raporu siteye gitmeden uygular.

| Ayar | Değer | Neden |
|---|---|---|
| Tetikleyici | Her Pazar yerel saatle 14:00 | Fiyat turları 10:00 ve 22:00'de başlayıp ~31 dk sürer; keşif (~35 dk) onlardan uzak bir saate konur. Saat yerel yazılır (UTC'ye çevrilmez). |
| Eylem | `.venv\Scripts\pythonw.exe -m app.discovery --scheduled --dry-run`; çalışma klasörü proje klasörü | Penceresiz. `config\` ve `data\` yolları çalışma klasörüne göredir. `--dry-run` görevin kataloğa hiç yazmamasını sağlar. |
| Kaçan çalışma | **Telafi edilmez** | Geç açılan bir bilgisayarda telafi keşfi ortak kilidi ~35 dk tutar ve o sırada gelen 22:00 fiyat turu "kilit meşgul" (kod 3) deyip atlanırdı. Kaçan fiyat turu geriye dönük toplanamaz; keşif raporu ise elle her zaman alınabilir. |
| Pil | Pildeyken de başlar, pile geçince durmaz | Windows'un varsayılanı yalnız şarjdayken çalıştırmaktır. |
| Uyandırma | Yok | Uykudaki bilgisayar uyandırılmaz; o hafta keşif kaçar. |
| Aynı anda | Görev çalışıyorsa yeni kopya başlatılmaz | Ortak kilit de engeller. |
| Süre sınırı | 2 saat | Normal çalışma ~35 dk (5 Ekim: 34 dk). Görev Zamanlayıcı süreci zorla kapatırsa rapor oluşmaz ve logun son satırı `Çıkış kodu` olmaz. |
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

Haftalık akış:

1. Pazar 14:00'te görev başlar; yaklaşık 35 dk sonra log ve rapor oluşur.
2. Log'un sonundaki özet satırına ve rapora bakılır: yeni ürün ve sayfalar,
   `rejected` nedenleri, `pending` içinde beklenen `search_api` dışında bir uyarı
   (ör. `search_fetch`, `variant_fetch`) olup olmadığı.
3. Uygunsa `python -m app.discovery --apply-report data\discovery\kesif_<tarih-saat>.json`
   (yukarıdaki "İncelenen raporu uygulama" bölümü).
4. `config/catalog.json` değişikliği commit edilir; sonraki fiyat turu yeni sayfaları
   veritabanına ekler.
5. Rapor 2–3 hafta temiz giderse tam otomatik biçime (yeni sayfaların doğrudan
   kataloğa girmesi) geçiş yeniden değerlendirilir; yanlış bir sayfa kataloğa girerse
   fiyatları ürünün geçmişine yazılır ve sayfa sonradan yalnız pasife alınabildiği
   için bu şimdilik yapılmaz.

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
- Raporlar silinmez; klasör zamanla büyür. Tam taramanın raporu 5 Ekim'de ölçüldü:
  305 KB (haftada bir dosya, yılda yaklaşık 16 MB). İnternet kesilince rapor küçük
  kalır (4 Ekim: 78 KB, tarama 7 dk).
- Testler komut akışını kayıtlı sonuçlarla sınar; görevin gerçek sitelerle
  çalıştığı ve raporun doğruluğu canlı kanıt ister. Canlı kanıt: 4 Ekim'de görev
  kendiliğinden çalıştı (`pythonw`, log ve rapor yazıldı) ama internet kesintisi
  yüzünden tarama boş kaldı; 5 Ekim'de elle çalıştırılan tam tarama ve
  `--apply-report` gerçek raporla çalıştı (7 sayfa eklendi). Tam taramanın Görev
  Zamanlayıcı altında görülmesi Pazar 11 Ekim 14:00'i bekliyor.

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
  sayılmaz. Katalog eşleştirmede bilinmeyen platform `None` döndürür. Bakım 2'nin
  kaynak/adres/sayfa karşılaştırması ve canonical tam SKU koruması sürer.
- Başlık tam modeli içermeli: "iPhone 16" hedefi "iPhone 16e", "16 Plus",
  "16 Pro" başlıklarını; "Galaxy S24" hedefi "S24+", "S24 FE", "S24 Ultra"
  başlıklarını; "iPhone 13" hedefi "13 mini" başlığını kabul etmez.
- Yenilenmiş, ikinci el, teşhir, **yurt dışı sürüm** ("International Version",
  "Global Version", "Yurt Dışı") ve aksesuar (kılıf, şarj, koruyucu…) reddedilir.
  Kayıtlı "Kılıfı", "Adaptörü", "Kapağı" yazımları da başlıklarda bütün sözcük
  olarak reddedilir (`kilifi`, `adaptoru`, `kapagi`). Başlık veya yapısal veri
  doğru kapasiteyi taşısa da ret `identity` olur. Genel Türkçe ek tahmini yoktur.
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

6 Ekim ekli aksesuar bakımının kaynak kanıtları: `data/trace_s25.json` içindeki
Hepsiburada `HBCV00007I6EKM` başlığında "Hızlı Sarj Adaptörü";
`data/trace_xiaomi_poco_x6_pro.json` içindeki Trendyol `4894840` başlığında
"Moto G Arka Kapak Batarya Pil Kapağı Mavi";
`data/trace_xiaomi_redmi_note_14_pro_4g.json` içindeki Hepsiburada
`HBCV0000FS4I6K` başlığında "Telefon Kılıfı" var. Bu gerçek örnekler başka
korumalardan zaten reddedilmişti. Regresyonlarda aynı sözcükler tek başına,
doğru model ve kapasiteyle yapay başlıklarda sınanır; canlıda yanlış fiyat
kaydedildiğine dair kanıt yoktur. 21 geçerli telefon örneği ise kullanıcının
`data/kimlik_iphone15_20261006/` ham yanıtlarından çıkarılmış sabit test verisidir.

7 Ekim Hepsiburada varyant bakımı **önleyici düzeltmedir**. İncelenen iPhone 15
ve Galaxy S24 yanıtlarında (40 HTML, 37 tek dolu liste) gerçek çelişki yoktu.
Kullanıcı yalnız bu madde için canlı çelişki örneğini bekleme şartına istisna
verdi; yapay kapasite/renk çelişkileri canlı hata kanıtı olarak sunulmaz.
`tests/fixtures/discovery/hepsiburada_identity_examples.json`, bu iki kayıttaki
36 ürün sayfasının yalnız kimlik alanlarını içerir; tekrar eden altı liste
ortak saklanır. Fiyat/stok verisi içermez, testler `data/` veya ağa bağlı değildir.
24 kabul edilmiş adayın bütün alanları ve diğer modele ait 12 sayfanın reddi
korundu. Yeni 75 sınama; liste sırası, tek liste içi çelişki, eşdeğer tekrar,
eksik alan/başlık yedeği, başka SKU ve keşfin diğer adaylarla devamını kapsar.
Eski kodda 31 yeni sınama başarısızdı (24 çelişki reddi dahil), 44'ü geçti;
kayıtlı 36 sayfanın koruma sınamaları eski kodda da geçti.

7 Ekim adres kimliği bakımı da **önleyici düzeltmedir**; kullanıcı bakım 2 için
ayrı istisna verdi. Aynı iki gerçek kayıttaki 6 TY varyant/adres/sayfa kimliği ve
36 HB ürün SKU'su eşleşti; sorunlu kaynak yanıtı veya yanlış kayıt kanıtı yok.
`tests/fixtures/discovery/trendyol_identity_examples.json`, 6 kabul edilen
TY adayının adresi, hedefi, varyant rengi ve sayfada kullanılan kimlik alanlarını
saklar; fiyat/stok içermez. Bütün aday alanları gerçek raporla eşleştirilir.
Mevcut HB fixture'ındaki 24 aday ve 12 model reddi de korunur. 31 yeni sınamada
kimliksiz/farklı TY adresi, bozuk son ek, sorgu metninin kimlik gibi kullanılması,
HB SKU alt dize tuzağı, geçerli sorgu/eğik çizgi/küçük harfli SKU, sayfa kimliği
reddi ve keşfin devamı denetlendi. Eski kodda 12 yeni sınama başarısız, 19 başarılı
oldu; kayıtlı 6 TY adayının koruma sınamaları eski kodda da geçti.

7 Ekim bakım 5'te beş tüketicinin ürün adresi kuralları ortaklaştırıldı.
Önce/sonra karşılaştırmasında 334 katalog adresinin ve kayıtlardaki 333 farklı
aday adresinin kimliği değişmedi; katalog kayıt kimlikleri ve dosya içeriği
korundu. Yapay sınamada eski Trendyol scraper'ı bozuk son ekli veya yalnız
sorguda kimlik taşıyan ucuz teklifi seçebiliyordu; Hepsiburada scraper'ı da
sorgudaki SKU'yu ürün kodu sayabiliyordu. Canlı yanlış fiyat/kayıt kanıtı yoktur.
Kullanıcı yalnız bakım 5 için de gerçek uyuşmazlık örneğini bekleme şartına ayrı
istisna verip önleyici düzeltme planını onayladı; genel gerçek kaynak şartı sürer.
39 yeni sınama, tüketicilerin aynı adreslerdeki sonucu ve scraper girişlerindeki
fiyat seçimi/kimlik reddini kapsar. Eski kodda 13'ü başarısız, 26'sı başarılıydı.
Mevcut sabit katalog testleri, 6 TY/24 HB adayın bütün alanları ve diğer modele
ait 12 sayfanın reddi korundu. Son tam paket 797 geçti, atlanan/xfail yok;
219 veritabanı testi yalnız `fiyat_takip_test` üzerinde çalıştı. Black/Flake8
temiz. Gerçek DB, katalog ve uygulanmış migration dosyaları değişmedi.

## Testler ne kanıtlar, ne kanıtlamaz

- **Otomatik testler (804; 226'sı gerçek PostgreSQL'de):** Kuralların doğru
  çalıştığını kayıtlı ve sahte yanıtlarla kanıtlar. Kimlik değişiklikleri gerçek
  kaynak örneği ve regresyon ister; 7 Ekim varyant ve adres bakımları kullanıcının
  her maddeye ayrı onayıyla yapay çelişkilere karşı önleyici koruma olarak uygulandı.
  Sitelerin bugün hâlâ aynı yapıda olduğunu kanıtlamaz. Veritabanı testleri
  şema kurallarının, migration koşucusunun, katalog eşitlemenin ve toplama
  turunun gerçek PostgreSQL'de doğru çalıştığını kanıtlar; tur testleri sahte
  scraper kullanır, turun gerçek sitelerle çalıştığını yalnızca canlı tur
  gösterir. Türkçe ekler için önceki `xfail(strict=True)` testi 6 Ekim'de
  düzeltmeyle normal teste çevrildi; güncel pakette beklenen başarısızlık yoktur.
- **Kasıtlı bozma (mutasyon) denetimi:** Testlerin gerçekten hata
  yakalayabildiğini sınamak için kodun kritik satırları projenin bir kopyasında
  ya da yalnız bellekte (ağ kapalıyken) tek tek bozuldu ve testlerin bozmayı
  yakalayıp yakalamadığına bakıldı (sonuçlar: proje_plani.md Bölüm 9, Adım 3 ve
  Adım 6). Yakalanmayanlar bilinçli olarak testsiz bırakılan eşzamanlılık
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
  [proje_plani.md](../proje_plani.md) Bölüm 8.
- Arka arkaya çok tarama Trendyol'da geçici engele yol açabilir (25 Eylül'de
  yarım saatte 7 tarama sonrası 10 dakika engel). Günlük fiyat toplama bu
  yoğunlukta değildir; keşif seyrek çalışır.
- Fiyat ve stok iki tur arasında değişip geri dönebilir; veritabanındaki geçmiş
  turların anlık görüntüleridir. 28 Eylül'de bir Trendyol sayfası 2 saatte
  Tükendi'den Kritik Stok'a ("Son 1 ürün"), bir Hepsiburada sayfası 71.059
  TL'den 75.524 TL'ye geçti.
- Siteler sayfa yapısını değiştirebilir; bu durumda bakım gerekebilir. Kod,
  değişiklikte sessizce yanlış sonuç üretmek yerine hatayı raporlamaya çalışır.

## Geliştirme geçmişi

### Kabul kontrolü (Eylül 2026)

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

Kararlar: RAM ve garanti türü ürün kimliğine katılmadı (gerekçe: [proje_plani.md](../proje_plani.md)
Bölüm 6); yurt dışı sürümler kapsam dışı; POCO X5 Pro satılmadığı
için kapatıldı.
