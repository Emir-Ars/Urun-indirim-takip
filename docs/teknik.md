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

[README](../README.md) kapsamı, [plan](../proje_plani.md) kararları,
[geçmiş](gecmis.md) commit/CI'ı, [AGENTS.md](../AGENTS.md) kuralları tutar.
`pyproject.toml` paket ve denetim ayarlarını tanımlar.
[Teslim rehberi](teslim.md) · [Arşiv envanteri](arsiv/teknik_2026-11-23.md#dosyalar-ve-sorumlulukları)

### Ayarlar: `config/` (kod değil, veri)

| Dosya | Sorumluluk |
|---|---|
| `discovery.json` | Hedefler, sınırlar, kaldırılmış bağlantı bağları |
| `catalog.json` | Keşfin ürettiği katalog |
| `runtime.json` | Zaman aşımı, tekrar ve 3 sn istek aralığı |
| `market_history.json` | [Cimri eşleştirmeleri](#eşleştirme-dosyası) |
| `shadow.json` | [Gölge başlangıcı, model SHA'sı ve yollar](#gölge-mod-tahmin-kaydı-python--m-appml-shadow-predict) |

### Ortak parçalar: `app/`

`contracts.py` veri, `settings.py` ayar, `scrape_lock.py` kilit,
`console.py` log, `price_statistics.py` istatistik katmanıdır.
Yol ayarları `CATALOG_PATH`, `DISCOVERY_PATH`, `RUNTIME_PATH`,
`SCRAPE_LOCK_PATH`, `LOG_DIR`, `DISCOVERY_REPORT_DIR` ile seçilebilir.

### Cimri geçmişi: `app/market_history/`

Alım, kimlik ve ağsız doğrulama. [Cimri komutları](#cimri-geçmişi-bir-defalık-alım-ve-aktarım)

### Fiyat okuma: `app/scraper/`

`http.py` pazaryeri HTTP'sini `curl_cffi` ve `impersonate="chrome120"`
ile sınırlar. 8 MB üstü reddedilir. 401/403/418/429 `blocked` olur.
`parsing.py` kimlik ve kuruş hesabını, `base.py`
`fetch(listing) -> PriceObservation` sözleşmesini sağlar.
[Fiyat okuma](#fiyat-okuma-nasıl-çalışır)

### Keşif: `app/discovery/`

Adaptörler kanıt toplar. `acceptance.py` kabulü, `service.py` yazımı
yönetir (`DiscoveryWriteError`). [Keşif](#keşif-nasıl-çalışır)

### Veritabanı: `app/database/`

`connection.py` UTC oturumu, 10 sn bağlantı ve 30 sn kilit sınırı
sağlar. Migration, katalog, tur ve Cimri yazımı burada yürür.
`read.py` ve `ml_data.py` salt okunurdur. [DB sözleşmesi](#veritabanı-postgresql)

### Fiyat toplama turu: `app/collection/`

Scraper ve DB'yi [toplama komutuyla](#toplama-turu-python--m-appcollection)
bağlar (`--prefix ÖN_EK`, `--scheduled`).

### Yerel API: `app/api/`

FastAPI, 1–4 salt okunur bağlantı ve [cevap sözleşmesi](#salt-okunur-fastapi).

### Yerel istemci ve ekran: `app/ui/`

Sabit yerel HTTPX istemcisi, Streamlit ekranı ve biçimleme.
[İstemci](#yerel-api-istemcisi) · [Ekran](#streamlit-ekranı)

### ML hazırlığı: `app/ml/`

Görüntü, etiket, girdi, eğitim ve gölge komutları.
[ML kanıt zinciri ve komutlar](#ml-hazırlığı)

### Kurulum ve zamanlayıcı: `scripts/`

`*_kur.ps1` görevleri kurar (`-Kaldir` siler), `api_okuma_rolu.sql`
SELECT rolünü hazırlar. `teslim.ps1` [Docker paket ve servis girişidir](#docker-tek-komutla-kullanım).

### Testler ve CI

`conftest.py` gerçek HTTP'yi ve canlı DB adreslerini engeller. Ortak
fixture ve örnekler `tests/support/` ve `tests/fixtures/` altındadır.
Testler birbirini içe aktarmaz. [Test DB kuralları](#test-ortamı-ve-sınırı)

`ci.yml` PostgreSQL 17 `C.UTF-8` testleri ve yapay Docker kabulünü
yürütür. Tur dışı elle `bulut-deneme.yml` girişi
`tools/live_scraper_check.py samsung_galaxy_a55_128gb` kullanır.

### Canlı kontrol ve denetim araçları: `tools/`

Kullanıcı proje kökünde `.venv\Scripts\python.exe tools\<araç>.py`
çalıştırır. Canlı iş tur/keşif dışında, DB denetimi salt okunurdur.

| Araç | Sorumluluk |
|---|---|
| `live_scraper_check.py` | Katalog/ön ek ile teklifler. Ortak kilit meşgulse 3. |
| `live_discovery_check.py` | Kataloğa yazmadan `data/discovery_report.json` üretir. `--trace` kararları, `--save-responses KLASOR` tek hedefin ham kanıtını yazar. |
| `ui_preview.py`, `api_ui_check.py` | Ağsız ekran ve bağımsız SQL–API denetimi |
| `ml_data_check.py`, `ml_label_check.py` | Sıkı sayım (`--snapshot` ağsız tekrar) ve etiket doğrulama |
| `docker_check.py`, `docker_entrypoint.py`, `docker_lock.py` | Yapay kabul, imaj girişi ve wheel kilidi (`input`, `lock`) |

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

Hedef → arama/varyant → doğrulanmış katalog → toplanan en ucuz teklif.
[Tarihsel örnek](arsiv/teknik_2026-11-23.md#örnek-iphone-15-128-gb-baştan-sona)

### Trendyol

Ana sayfa oturum açar. `/sr` yalnız `Referer`'dır. API marka + model
arar. Marka önce `canonicalFilters`, yoksa `aggregation/WebBrand` içinden okunur.
İlk geçerli telefon kategorisi taranır, birden fazlaysa
`category_partial`. Kart retleri `excluded_word`, `other_model`,
`excluded_term`, `brand`, `category`. Toplam en çok 20 sayfa gezilir.

`slicing-attributes` kardeş renk/kapasite sayfalarını verir. Adayın
`-p-<id>` yol kodu arama/varyant kimliğiyle eşleşmelidir. Yalnız sorgudaki
kod geçersizdir. Eksik/yanlış kod HTTP yapılmadan `identity` ve
`candidate_rejected` üretir. Ürün denemesi hakkını tüketir, HTTP bütçesini
tüketmez. Açılan sayfada ürün kimliği, marka, kategori, model, kapasite
ve gerekiyorsa mobil ağ yeniden doğrulanır.

### Hepsiburada

`ara?q=…` ve varsa `…-xc-…` model sayfası taranır. `-p-HBCV…` ürün,
`-pm-HBC…` grup yoludur. Grup yalnız gerçek SKU'lara çözülür.
API'de marka ve ana kategori/tanım yeni telefona uymalıdır. İki
alandan birindeki aksesuar veya yenilenmiş kanıtı eler. Varyantlar
modelle süzülür. İkinci sayfadan itibaren yeni uygun varyant kalmazsa
durulur. Tamamen tekrarlı kod sayfası `repeated_page`, engel
`search_api` üretir. API engelinde HTML adayları korunur.

Doğrulanan ürün adaydır. `allVariantCombinations` kuyruğa girer.
Retli sayfada yalnız marka/kategori/SKU/model/kapasite/ağ geçerse
seçenekler gezilir. Hatalı sayfada gezinilmez.
Aday URL'si kanıt adresidir. Canonical başka SKU ise `source_id_mismatch`.
Küçük harf eşdeğerdir. Sorgu SKU'su ve SKU'suz canonical adresi değiştirmez.

### Otomatik güvenli kabul

`acceptance.py`, aynı ürün koduna bağlı marka, model, kapasite, renk,
yeni telefon kategorisi ve kendi Product/ProductGroup teklifindeki
NewCondition kanıtıyla `verified`, `mismatch` veya `insufficient` verir.
Aksesuar/yenilenmiş/ikinci el/teşhir kanıtı NewCondition'dan önce gelir.
Garanti, fiyat, satıcı ve stok kabul kanıtı değildir. Stoksuz aday kimliği
tam ise kabul edilir. İki adaptör yalnız `verified` döndürür.
Rapor kararı kanıttan yeniden hesaplar.

- Hedefte ağ varsa kendi başlığından veya özelliğinden olumlu kanıt gerekir.
  5G yazmaması 4G kanıtı değildir. 4.5G, 4G sayılır. Ağ, kapasite, renk veya
  RAM çelişkisi reddedilir. RAM eksikliği tek başına ret değildir.
- Trendyol renk seçicisinde `DsmColor` ve `product.slicingAttributes`
  önceliklidir. Çelişirlerse ret verilir. Seçici yoksa satıcı "Renk"
  ve JSON-LD değeri karşılaştırılır. Salt kapasite renk sayılmaz.
- Hepsiburada özelliği ana `productState.product`/ürün kökünden, renk
  kendi varyantından veya ürün alanından gelir. Kayıtlı satışa kapalı
  biçimde açık başlık son eki kullanılabilir. Öneri ürününden ya da
  görselden kanıt alınmaz. “Çok Renkli” özgül renk değildir.
  Bilinen normalleştirme `blue` → `mavi`dir.

Yeni ürün yalnız etkin hedefin doğrulanmış kapasitesinden gelir.
Aynı platform kodunun çelişkili grubu elenir. Kısmi aramada kanıtlı
aday yazılabilir. `retired_listing_bindings` kaldırılan kod,
listing_id/product_id/product_key bağını saklar. Kalıcı kaldırmada
güncellenir. Tam kanıtla yalnız eski kimliğe ve ürüne döner.
Pasif katalog kaydı otomatik açılmaz.

```powershell
# Tek seferlik toplu önizleme; katalog yazmaz.
.venv\Scripts\python.exe -m app.discovery --scheduled --dry-run
# Kurulu haftalık görevin otomatik kabul modu.
.venv\Scripts\python.exe -m app.discovery --scheduled --auto-accept
```

`--scheduled` açıkça `--auto-accept` veya `--dry-run` ister. İkisi
birlikte geçersizdir. Seçeneksiz yazma da aynı kanıt kurallarına tabidir.

`decisions` URL, kod, gözlem zamanı, HTML parmak izi, alan/değer/kaynak/
owner_id ve gerekçeyi tutar. Alınamayan HTML'de iz boş kalır. Önce
hazırlık raporu ve önceki/sonraki SHA'lar, sonra
`data/discovery/pending_<katalog>.json` yazılır. Atomik katalog yazımı
ardından rapor tamamlanır. `preview` yazmasız, `prepared` hazırlık,
`applied` yazıldı, `unchanged` aynı, `not_applied` kesintiden sonra
önceki katalog kaldı demektir. Sonraki başlangıç önceki/sonraki SHA ile
uzlaştırır. İkisi de tutmazsa durur. Rapor hazırlanamıyorsa katalog yazılmaz.
Son rapor hatasında çıkış 1 olsa bile katalog değişmiş olabilir.

### Katalogla birleştirme (`service.py`)

Ürün marka/model/kapasite, bağlantı platform/SKU ile tekildir. Yeni
bağlantı `platform_urunkimligi` biçimindedir. Kimlikler, görülmeyen ve
pasif kayıtlar korunur. Aynı tarama ikinci kayıt üretmez. Başka ürüne
bağlı aday `catalog_conflict` olur, diğer adaylara devam edilir.
Katalog kilit altında yeniden okunur. `_atomic_json` geçici dosya,
diske yazma ve yer değiştirmeyle aynı JSON baytlarını kullanır.
`--dry-run` katalog yazmaz.

### İncelenen raporu uygulama (`--apply-report`)

`python -m app.discovery --apply-report RAPOR` yalnız BOM'lu veya BOM'suz
geçerli `dry_run: true` önizlemesini okur. `--trace` sarmalı ve daha önce
yazmış rapor geçersizdir. Eski kanıtsız rapor okunabilir, yeni aday ekleyemez.
Rapor, katalog ve ayar parmak izleri, kanıttan karar ve beklenen sonuç
doğrulanır. Kural değişince yeni önizleme gerekir.

Katalog kilidinde canlıyla aynı birleştirme yürür. Sonuç
`added_products`/`added_listings` alt kümesi olmalıdır. Yeni ekleme
çıkarsa yazmadan yeni önizleme istenir. Mevcut kayıt çoğaltılmaz.
Siteye gidilmez, `data/scrape.lock` alınmaz. Süren tur başlangıç
kataloğunu kullanır. Eklemeler `+` ile, çakışmalar ayrıca yazılır.
Tek aday seçilemez. İstenmeyen sayfa sonraki turdan önce `active: false`
yapılabilir. Sonraki tur DB'yi eşitler. Katalog onayla Git'e girer.
Geri alma kimlik tekrarına ve `CatalogConflict`e yol açabilir.

### Rapor: `data/discovery_report.json` (zamanlanmışta `data/discovery/kesif_<tarih-saat>.json`)

`generated_at` UTC, `dry_run` mod, `complete` kaynak tamamlanma durumu.
`results` hedef/platform kararları, `application` yazım ve SHA'lar,
`added_products`/`added_listings` planlanan veya uygulanan farktır.
`existing_listings` yeniden görülen, `retained_unobserved_listings`
görülmeyen etkin sayfadır. `pending` uyarı, `rejected` ret,
`observed_colors` kapasite/platform renkleri, `coverage_changes` ekleme sayısıdır.

| Uyarı | Anlamı |
|---|---|
| `search_fetch`, `search_api` | Arama tamamlanmadı / Hepsiburada API engellendi. |
| `model_filter_missing`, `html_partial` | Model filtresi yok / HTML kart sayısı eksik. |
| `filter_unavailable`, `category_partial`, `count_mismatch` | Trendyol kategori filtresi yok / yalnız ilk kategori / toplam uyuşmuyor. |
| `search_limit`, `product_limit`, `repeated_page` | Tarama sınırı doldu / sayfa tekrarlandı. Yalnız yeni hedef kalmaması tekrar sayılmaz. |
| `variant_fetch`, `missing_variants`, `group_url_pending` | Varyant listesi erişilemedi / boş / API ürün veya grup URL'si çözülemedi. |
| `evidence_missing`, `candidate_rejected`, `identity_mismatch`, `catalog_conflict` | Kanıt eksik / aday reddi / kimlik çelişkisi / katalog bağı çelişkisi. |

| Çıkış | Tarama | `--apply-report` |
|---|---|---|
| 0 | Tam | Güncellendi veya fark yok |
| 1 | Başlama (ör. tanımsız hedef), log veya yazma hatası | Rapor, ayar veya yazma hatası |
| 2 | Kısmi, çakışma veya etkin hedef yok. Yeterli adaylar yazılabilir | Çakışan aday atlandı |
| 3 | Ortak kilit meşgul | Ortak tarama kilidi kullanılmaz |

`--target KEY` tek hedef seçer. Geçersiz argüman 2 ile yazmadan,
log hatası 1 ile taramadan çıkar. UTF-8 stderr özeti ekleme, görülen,
görülmeyen, çakışma, ret ve uyarıları sayar. Ayar BOM kabul eder, katalog BOM'suz LF'dir.
`max_search_pages` sınırı `search_limit` üretir.

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

PostgreSQL 17, katalog kopyasını ve fiyat turlarını saklar.
[Zamanlanmış tur](#zamanlanmış-tur-görev-zamanlayıcı)

### Bir kerelik kurulum (Windows)

1. EDB PostgreSQL 17, Server ve Command Line Tools bileşenleri.
   Locale `C` seçilir. ASCII dışı Windows locale adı `initdb`'yi bozar.
2. Yönetici `psql -U postgres -h localhost` oturumunda:

   ```sql
   CREATE ROLE fiyat_takip LOGIN;
   \password fiyat_takip
   CREATE DATABASE fiyat_takip OWNER fiyat_takip TEMPLATE template0 ENCODING 'UTF8' LOCALE_PROVIDER builtin BUILTIN_LOCALE 'C.UTF-8';
   CREATE DATABASE fiyat_takip_test OWNER fiyat_takip TEMPLATE template0 ENCODING 'UTF8' LOCALE_PROVIDER builtin BUILTIN_LOCALE 'C.UTF-8';
   ```

   Rol yalnız bu DB'lerin sahibidir. Parolada ASCII kullan. `pg_hba.conf`
   yalnız yerel bağlantıya izin verir.
3. Parolayı `%APPDATA%\postgresql\pgpass.conf` dosyasına
   `localhost:5432:*:fiyat_takip:ŞİFRE` biçiminde kaydet.
4. Şifresiz kullanıcı değişkenlerini ayarla, terminali ve IDE'yi yeniden aç.

   ```powershell
   setx DATABASE_URL "postgresql://fiyat_takip@localhost:5432/fiyat_takip"
   setx TEST_DATABASE_URL "postgresql://fiyat_takip@localhost:5432/fiyat_takip_test"
   ```

5. `python -m app.database migrate` ile şemayı kur.

`python -m app.database migrate` / `status` / `sync-catalog [--dry-run]`
çıkışları 0 başarı, 1 komut hatası (stderr'de `Veritabanı komutu başarısız: …`),
2 argüman hatasıdır.

### Tablolar

| Tablo | İçerik |
|---|---|
| `platforms`, `products`, `listings` | Asıl kaynak `catalog.json` dosyasının DB kopyası. Bağlar yabancı anahtarlarla korunur. |
| `collection_runs` | Tetikleyici (`scheduled`/`manual`), durum (`running`/`completed`/`interrupted`), zaman, katalog SHA'sı ve planlanan sayfa. |
| `listing_checks` | Tur × planlanan sayfa. NULL bakılmadı, `offer` fiyat, `sold_out` Tükendi, `error` hata. Fiyat kuruştur. |
| `schema_migrations` | Uygulanan numara/ad ve parmak izi. |
| `market_history` | Ayrı Cimri ürün/kaynak/gün kaydı. |
| `product_run_prices` | Tamamlanmış tur × ürün için en düşük fiyat ve karşılaştırma. |

### Veritabanının zorladığı kurallar

`(run_id, listing_id)` tekil, `(listing_id, product_id)` yabancı anahtardır.
Tek `running` tur olabilir. Yalnız kapanmış turun bitiş zamanı vardır.
Marka/model/kapasite harf büyüklüğünden bağımsız tekildir.

`offer` pozitif fiyat, satıcı ve satılabilir stok ister. Puan ölçeğini
aşamaz. Çizili fiyat yalnız güncel fiyattan büyükse bulunabilir. `sold_out`
yalnız Tükendi stok durumunu taşır. Fiyat, çizili fiyat, satıcı, puan ve
ölçek boş kalır. Hata fiyat, satıcı veya stok taşımaz. Planlı satırın
sonuç alanları boştur. `CHECK` NULL'ı geçirebildiği için `CASE` ve
`IS NOT NULL` kullanılır. 005'in satıcı URL'si yalnız `offer` ile dolabilir.
Eski URL alanı NULL kalır.

#### Tetikleyiciler: neyin değişip neyin değişmediği

002 silme ve `TRUNCATE` işlemlerini engeller. İhlal SQLSTATE `23000` döner.

| Tablo | Kimlik alanları | Güncellenebilen |
|---|---|---|
| `platforms` | `key` | `name`, `active` |
| `products` | `product_id`, `product_key`, marka, model, kapasite | `active` |
| `listings` | `listing_id`, `product_id`, `platform` | `url`, `color`, `active` |
| `collection_runs` | `run_id` (`GENERATED ALWAYS`), tetikleyici, başlangıç, katalog SHA'sı, planlanan sayı | Çalışan turda `status`/`finished_at`, her turda `note` |
| `listing_checks` | `run_id`, `listing_id`, `product_id` | Çalışan turda sonuç bir kez yazılır ve donar. |

Tek istisna çalışan turun `network` sonucudur. `003_closed_run_guards.sql`
kapanmış turun ilk sonuç yazımını ve durum/bitiş güncellemesini reddeder.
Yazım, `FOR SHARE` ile tur kapanışıyla sıraya girer.
[İkinci okuma](#tur-sonu-ikinci-okuma)

- **Bilerek silme.** Sahibi tur dışında önce `SELECT` ile kapsamı
  kontrol eder. Tetikleyiciyi kapatır ve işlemden sonra açar.

  ```sql
  ALTER TABLE listing_checks DISABLE TRIGGER listing_checks_no_delete;
  DELETE FROM listing_checks WHERE listing_id = 'hepsiburada_ornek';
  ALTER TABLE listing_checks ENABLE TRIGGER listing_checks_no_delete;
  ```

  Tetikleyiciler `<tablo>_no_delete`, `<tablo>_no_truncate` ve
  `<tablo>_guard_update` biçimindedir.

### Karşılaştırılabilirlik (`product_run_prices`)

Yalnız `completed` tur × ürün satırı üretilir. Sayımlar
`planned_pages`, `answered_pages`, `offer_pages`, `sold_out_pages`,
`error_pages` alanlarındadır. `offer` ve `sold_out` cevap sayılır.
`best_price` ve `best_listing_id` minimum tekliftir. Eşitlikte küçük
kimlik kazanır, fiyat yoksa boş kalır. Önceki tur o ürünün bulunduğu önceki tamamlanmış turdur.
`comparable_with_previous` yalnız aynı cevap veren sayfa kümesinde
doğrudur. İlk, cevapsız veya kapsamı değişen tur karşılaştırılmaz.
`hours_since_previous` yalnız bilgidir. Hata, giriş ve dönüşte kapsamı bozar.

```sql
SELECT run_id, run_started_at, best_price / 100.0 AS en_ucuz_tl,
       previous_best_price / 100.0 AS onceki_tl,
       comparable_with_previous, hours_since_previous
FROM product_run_prices
WHERE product_id = 1
ORDER BY run_id;
```

### Toplama turu (`python -m app.collection`)

1. Ortak `data/scrape.lock` ve güncel şemadan sonra DB advisory lock
   alınır. Meşgul kilit çıkış 3 verir. İki kilit de alındığında eski
   `running` turlar `interrupted` yapılır.
2. Katalog eşitlenir. Çakışmada tur açılmaz. Etkin platform/ürün/sayfalar
   `--prefix` filtresiyle planlanır. Tur ve sonuçsuz satırlar tek işlemde yazılır.
3. Her sonuç hemen yazılır ve ilerleme basılır. Sonunda yalnız `network`
   için ikinci okuma yapılır. Tur kapanır, ardından özet okunur.

| Sonuç | Yazım |
|---|---|
| Stokta Var / Kritik Stok | `offer` ve teklif alanları |
| Tükendi | `sold_out`, fiyat ve satıcı boş |
| `FetchError` | `error`, aynı kod ve mesaj |
| Yanlış sayfa/geçersiz gözlem | `validation`. Scraper ayrıştırma hatası `parse` olabilir. |
| Beklenmeyen hata | `unexpected`, ayrıntı logda |
| Reddedilen DB değeri | `storage`. Metindeki NUL (`\x00`) temizlenir. |

Sayfa hatasında tur sürer. Ctrl+C/kesen DB hatasında `interrupted`,
bakılmayan sayfa NULL kalır. DB kopmuşsa sonraki tur kalan `running`
kaydını kapatır. İkinci kapanış reddedilir. `--scheduled` tetikleyicisi
`scheduled`, varsayılan `manual` olur. `--prefix` nota yazılır.

| Çıkış | Anlamı |
|---|---|
| 0 | Tamamlandı, sayfa hatası yok |
| 1 | Başlama (şema/ayar/çakışma/etkin sayfa), kesen DB veya özet hatası |
| 2 | Tamamlandı, sayfa hatası var |
| 3 | Kilit meşgul |
| 130 | Ctrl+C |

#### Kapanış sonrası hatalar

Autocommit kapanışından sonra SQL/bağlantı hatası 1, Ctrl+C 130
verir. Tur `completed`, sonuçlar kayıtlı kalır.

#### Tur sonu ikinci okuma

Yalnız `error`/`network` (5xx dahil), kapanıştan önce, yeni
scraper ve aynı `check_listing` ile bir kez denenir. İstek aralığı
3 sn'dir. Ardışık 5 `network` hatası geçişi durdurur. İlk geçiş
bu sınırla durmaz.

Başka sonuç gelirse `rewrite_network_result` aynı satırı yeni
`checked_at` ile değiştirir. Tekrar `network` veya yazma reddinde ilk
satır kalır. Ret loglanır. Log, denenen sayfa ve sonuçları; not, yalnız
düzelen/kalan/denenmeyen sayıları taşır. Son çıkış ve karşılaştırılabilirlik
düzeltilmiş sonuca göre hesaplanır. Hiç `network` yoksa ikinci okuma ve
not oluşmaz.

### Zamanlanmış tur (Görev Zamanlayıcı)

`scripts/zamanlayici_kur.ps1` yönetici izni istemeden
`\FiyatTakip\FiyatToplamaTuru` görevini kurar/yeniler, `-Kaldir` siler.
`-ExecutionPolicy Bypass` yalnız çağrılan süreç içindir. `pythonw.exe`
ve kullanıcı ortamında `DATABASE_URL` gerekir.

Yerel 10:00/22:00'de proje kökünde
`.venv\Scripts\pythonw.exe -m app.collection --scheduled` çalışır.
Oturum açıkken, kilitli ekran ve pilde de çalışır. Uyandırma yoktur,
2 saat sınırı vardır. Kaçan tetiklemeler uygun oturumda bir kez
telafi edilir. Kesinti, `IgnoreNew` veya kod 3 telafi edilmez.
`IgnoreNew` ayrı log/DB/çıkış bırakmaz. Kapanamayan `running` turu
sonraki tur kapatır. Ağ/uyku kesintilerinde ikinci okuma geçerlidir.

`data/logs/tur_<yerel tarih-saat>.log` başlangıç, ilerleme, hata,
özet ve çıkışı saklar. 1/3 de loglanır. Log açılamazsa tur başlamaz,
`pythonw` altında yalnız `0x1` görünür. Windows `0x0/0x1/0x2/0x3`
CLI ile aynıdır. `0x41301` çalışıyor demektir.

Modern Standby bu bilgisayarda ekran kapanınca uyutabilir. AC'de
kapak eylemi “hiçbir şey yapma”, `STANDBYIDLE`, `VIDEOIDLE`,
`VIDEOCONLOCK` 0'dır. Armoury Crate nedeniyle Dengeli/Silent/Performance
planlarının üçüne uygulanır. Pilde kapak eylemi aynı, ekran/uyku süreleri
mevcut ayardadır. [İşletim kanıtı](arsiv/teknik_2026-11-23.md#zamanlanmış-tur-görev-zamanlayıcı)

#### Geç veya kaçan turun nedeni

Görev geçmişi kapalıysa `LastRunTime`, `LastTaskResult`, önceki
log ve Windows System günlüğünü karşılaştır. Tarihleri tura uyarla.

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

12/13 açılış/kapanış, 42 uyku, Power-Troubleshooter 1 uyanış,
506/507 modern bekleme, 41 düzgün kapanmamış sistemin açılışıdır.
107 uyanma saati olarak kullanılmaz. User32 1074 isteği ve süreci,
Winlogon 7001/7002 oturum açılış/kapanışını gösterir. Kilit ekranı
oturumu kapatmaz. Telafi için bilgisayarın uyanık olması ve oturum
gerekir. Açılışta ağın hazır olması ayrı koşuldur.

### Zamanlanmış keşif (Görev Zamanlayıcı)

`scripts/kesif_zamanlayici_kur.ps1` yönetici izni istemeden
`\FiyatTakip\HaftalikKesif` görevini kurar/yeniler, `-Kaldir` siler.
Pazar 14:00'te proje kökünde `.venv\Scripts\pythonw.exe -m app.discovery --scheduled --dry-run`
çalışır. Kurulu `-OtomatikKabul` modu `--scheduled --auto-accept` kullanır.
Seçeneksiz kurulum önizlemeye döner. DB ve otomatik Git işlemi yoktur.

Oturum açık olmalıdır. Pilde çalışır, uyandırmaz, `IgnoreNew` ve 2
saat sınırı vardır. Kaçan/atlanan iş telafi edilmez. Çalışırken canlı
iş açma. `data/logs/kesif_<yerel tarih-saat>.log` ve
`data/discovery/kesif_<yerel tarih-saat>.json` aynı damgayı taşır.
Rapor klasörü taramadan önce hazırlanır. Yazılamazsa 1, kilit meşgulse
3. Log açılamazsa yalnız görev sonucu `0x1` görünür. Kesinti sonrası
hazırlık kaydını sonraki başlangıç uzlaştırır. İlerleme satırı yoktur.

`Get-ScheduledTaskInfo -TaskPath '\FiyatTakip\' -TaskName 'HaftalikKesif'`
sonucu `0x0` tam, `0x2` kısmi, `0x3` kilit, `0x1` hatadır.
Log tarihini ve son çıkışı kontrol et. Log ve rapor saklanır.
Kaçan keşfi kullanıcı elle başlatır.

Otomatik mod yalnız doğrulananları ekler. Sonraki tur DB'yi eşitler.
Önizleme `python -m app.discovery --apply-report data\discovery\kesif_<tarih-saat>.json`
ile uygulanır. Katalog Git'e ayrı onayla alınır. Yeni sayfalar geçmişi
silmez. `y_sabit` başlangıç kapsamını korur. Sıkı 30+7, kapsamı
değişen pencereyi eler. [Etiket kuralları](#günlük-seri-ve-etiketler-python--m-appml-labels)

### Katalog eşitleme (`sync-catalog`)

Asıl kaynak `catalog.json`, eşitleme tek transaction'dır.
`--dry-run` aynı işlemi geri alır. Tur başında da uygulanır.
Platform adı/aktifliği, ürün aktifliği ve sayfanın adres/renk/aktifliği
güncellenebilir. Kimlik alanı, başka kaydın `product_key`i veya
URL'siyle çakışma bütün işlemi durdurur. Katalogdan düşen kayıt
silinmeden pasife alınır.

Her tabloda önce güncelleme sonra ekleme yapılır. İki adresin
karşılıklı takası tek adımda reddedilir. BOM kabul edilir.
Şema güncel olmalıdır. İkinci eşitleme fark üretmez. Satır
sonundan bağımsız katalog SHA-256, `collection_runs.catalog_sha256`
ve komut çıktısında yer alır.

### Migration kuralları

`NNN_ad.sql`, 001'den boşluksuz, tekil numara ve küçük `.sql`
uzantısı ister. Dosyalar paket verisidir. Eksik/bozuk dosya veya
koddan yeni DB hata verir. Dosya başına tek transaction uygulanır.
Eşzamanlı `migrate` 30 sn'ye kadar bekler.

`migrate` ve `status` uygulanmış dosyanın adını ve satır sonundan
bağımsız SHA'sını denetler. Değişiklik yeni numarayla ayrı kopyada
geliştirilir. Bitince dosyayı ekle ve tur başlamadan, 10:00–10:40
ile 22:00–22:40 dışında `migrate` çalıştır.
[Eski şema ve işletim ayrıntıları](arsiv/teknik_2026-11-23.md#veritabanı-postgresql)

## Cimri geçmişi (bir defalık alım ve aktarım)

`market_history` ayrı seridir. Son alım 2 Kasım 2026'da tamamlandı.
Düzenli alım yoktur. Yeni alım ayrı karar ister. [Kapsam](../README.md#-güncel-kapsam)
[Alım ve aktarım kayıtları](arsiv/teknik_2026-11-23.md#cimri-geçmişi-bir-defalık-alım-ve-aktarım)

### Eşleştirme dosyası

`config/market_history.json`, `version: 1`, `source: "cimri"` ve `entries`
taşır. Tekil `product_key`, `url` ve `cimri_product_id`, etkin katalog
ürününe ait HTTPS Cimri telefon ana sayfasını gösterir. Model/kapasite
yerine benzer ürün veya renk sayfası kullanılmaz. URL/kimlik tahmin edilmez.
Alım sayfa ve API kanıtını ayrıca doğrular.
[Tarihli eşleştirme örnekleri](arsiv/teknik_2026-11-23.md#eşleştirme-dosyası)

### Yerel alım (`capture`)

Zamanlanmış işler bittiğinde kullanıcı çalıştırır.

```powershell
$cimriKlasor = "data\market_history\katalog_$(Get-Date -Format yyyyMMdd_HHmmss_fff)"
.venv\Scripts\python.exe -m app.market_history capture `
  --mapping config\market_history.json --output-dir $cimriKlasor
$LASTEXITCODE
```

`--mapping` ve `--output-dir` zorunludur. `--product-key` tekrarlanabilir.
Seçenek yoksa etkin katalog raporlanır. Var olan klasöre yazılmaz.
Ortak kilit meşgulse klasör oluşmaz. Alım DB'ye bağlanmaz.

`PageClient` sayfa ve `POST https://www.cimri.com/api/cimri`
`priceHistoryV2Query` sorgusu için toplam dört istek (yönlendirme/tekrar
dahil), ortak bekleme, alan adı ve 8 MB sınırı kullanır.
`__OCTOPUS_DATA__` kimliği eşleştirmeyle, marka katalogla, gömülü başlık
ve her H1 model/kapasiteyle eşleşmelidir. Kategori tam `cep-telefonlari`
olmalıdır. Yenilenmiş/ikinci el/teşhir başlıkları ve kategorileri elenir.
Sonra grafik istenir ve API kimliği doğrulanır. `blocked` kalan istekleri
durdurur, diğer ürün hatalarında devam edilir.

`lastDay` geriye doğru en çok 366 noktanın tarihini belirler. Pozitif,
en çok iki ondalıklı fiyat `money` ile kuruşa çevrilir. Sayısal sıfır,
tabloyla çelişmiyorsa eksiktir. Eksik NULL kalır. Ortak günler tabloyla
eşleşmelidir. Ortak gün yoksa `table_comparison: "unavailable"`.
Geçersiz tarih veya fiyat reddedilir.

İlk teklif yoksa API korunur. Geçerli ilk teklif yalnız son API
fiyatının yerini alır. İlk teklif varken son API fiyatı sıfır/NULL ise `parse`.
Dönüşüm için `page_started_at_utc` ve `captured_at_utc` sıralı ve
`lastDay` ile aynı İstanbul gününde olmalıdır. Fark `parse` olur.
Ortak tablo günleri dönüşümden sonra karşılaştırılır. `latest_price`
gün, `page_first_offer`/`api` kuralı, API/ilk teklif/etkin kuruşlar,
`changed` ve tablo karşılaştırmasını taşır. Ağsız doğrulama kayıtlı
zamanları, İstanbul hesabı `ZoneInfo`/`tzdata` kullanır.

`responses/<product_key>.html` alınmış metin, `responses/<product_key>.json`
ayrıştırılmış API nesnesidir. SHA-256 yerel baytlara aittir. Eksik gövde
üretilmez. Kimlik/grafik hatasında seri kabul edilmez. Sürüm 1 rapor
kaynak, UTC zaman, kapsam, ürün kimliği/eşleştirme, istek, yol/SHA ve
`history`yi tutar. Noktalar sıralı gün/kuruştur. Ürün `captured`,
`error`, `unmapped`, `not_attempted` veya `interrupted`, rapor
`running`, `completed`, `partial`, `interrupted` veya `failed` olur.
Ürün başına atomik yazım yapılır. Disk hatası isteği durdurur, Ctrl+C
kayıtları korur. İstemci ve kilit kapanır.

Çıkış 0 başarı, 2 kısmi (eşleştirmesiz ürün dahil), 1 ayar/seçim/klasör/
dosya hatası, 3 kilit, 130 Ctrl+C.

### Ağsız aktarım (`import`)

```powershell
.venv\Scripts\python.exe -m app.market_history import <alım_klasörü> --dry-run
.venv\Scripts\python.exe -m app.market_history import <alım_klasörü>
```

Sürüm 1, `source: cimri`, son durum ve UTC zamanları gerekir.
`running`, bozuk zarf ve tekrarlı kimlik reddedilir. Yalnız
`captured` doğrulanır. `page_started_at_utc` ve `latest_price` gerekir.
Kayıtlı eşleştirme ve alım klasöründeki HTML/API kullanılır. Katalog
kimliği, SHA, zaman ve yeniden hesaplanan geçmiş/özet eşleşmelidir.
Fiyat pozitif bigint veya NULL'dır. Karşılaştırılamayan tarihler raporlanır.

Dosya ve DB tur kilitleri beklemeden alınır. Önce tüm ürün kimlikleri
DB ile eşleşmelidir. Katalog eşitlenmez ve tur açılmaz/kapatılmaz.
Gün anahtarı `(product_id, source, day)`. Kaynak `cimri`, kimlik
pozitif rakam dizisi, URL HTTPS telefon yolu ve tarihler sonlu olmalıdır.
Üç SHA-256 HTML, API ve rapor baytlarını tanımlar. 004 tabloyu ekler.
UPDATE, DELETE ve TRUNCATE reddedilir.

Ürün başına READ COMMITTED işlem, önce karşılaştırma, sonra
`ON CONFLICT DO NOTHING`, commit öncesi yeniden okuma uygular.
Aynı fiyat (NULL–NULL dahil) ve Cimri kimliğinde ilk satır kalır.
Adres/zaman/hash tek başına fark değildir. Farklı Cimri kimliği veya
tam gün fiyatı bütün ürünü geri aldırır. Diğer uygun ürünler sürer.
Gün, alımın İstanbul tarihiyse yarımdır. Ortak günde iki kayıttan
biri yarımsa fiyat farkı ilk satırı korur ve “Yarım gün farkı”
olarak raporlanır. Aynı sayısına ve çıkışa etki etmez. Kimlik farkı
yarım günde de çelişkidir.

DB/SQL hatasında önceki ürünler kalır. COMMIT cevabı kaybolursa son
ürün belirsizdir. Tekrar çalıştırma sonucu çoğaltmadan netleştirir.
`--dry-run` tek REPEATABLE READ, READ ONLY işlemde terminale
ekleme/aynı/yarım gün/çelişki ve eski/yeni fiyat-kimlik bilgisi verir.
Normal aktarım kontrolleri yeniden yapar. Çıkış 0 başarı/aynı,
2 atlanan/çelişkili ürün, 1 yapı/kimlik/şema/DB hatası, 3 kilit,
130 Ctrl+C. Girdi dışında kalan eşleştirmeler çıkışı değiştirmez.

### Gerçek aktarımın akışı

Ana ve ek alımlar ayrı klasörlerde önizlenip ayrı aktarılır.
Ek alım başarısız/denenmemiş ürünleri tamamlar. READ ONLY denetim
kimlik, adres, gün, kuruş, zaman ve üç hash'i kanıtla karşılaştırır.
Tekrarda 0 yeni satır ve ilk kaynak beklenir. Atlanan ürün 2 verebilir.

### Kullanım değerlendirmesi

19 Ekim incelemesinde indirme/saklama kısıtlı, yerel gösterim ve
ML belirsiz bulundu. Kullanım uygunluğu doğrulanmadı. 23 Ekim kullanıcı
kararı son bir alımı ve ML kullanımını onayladı.
[Kararlar](../proje_plani.md#5-kararlar)
· [Tarihli koşul incelemesi](arsiv/teknik_2026-11-23.md#kullanım-değerlendirmesi)

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
