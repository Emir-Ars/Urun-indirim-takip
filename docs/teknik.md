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
| `settings.py` | Ayar dosyalarını okur. `CATALOG_PATH`, `DISCOVERY_PATH`, `RUNTIME_PATH` ortam değişkenleriyle başka dosya gösterilebilir. |

### Fiyat okuma: `app/scraper/`

| Dosya | Ne işe yarar |
|---|---|
| `http.py` | İnternete açılan tek kapı. `curl_cffi` + `impersonate="chrome120"`; yalnızca izinli alan adları, zaman aşımı, sınırlı tekrar, istek aralığı (alan adı başına, bütün istemciler arasında ortak), yönlendirme kontrolü, 8 MB yanıt sınırı, istek bütçesi. 401/403/418/429 yanıtları `blocked` olarak sınıflanır. Playwright, Selenium veya `requests` kullanılmaz. |
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
| `service.py` | Platformları çalıştırır, sonuçları katalogla birleştirir, raporu yazar. |
| `__main__.py` | Komut satırı: `python -m app.discovery`. |

### Testler ve CI

| Yer | Ne işe yarar |
|---|---|
| `tests/test_trendyol_scraper.py`, `tests/test_hepsiburada_scraper.py`, `tests/test_discovery.py` | Kayıtlı örnek verilerle otomatik testler (59 test). İnternete çıkmaz. |
| `tests/fixtures/discovery/` | Testlerin kullandığı örnek site yanıtları ve kataloğun sabit bir kopyası (`catalog.json`); testler gerçek kataloğa bağlı değildir. |
| `tests/manual/live_scraper_check.py` | Katalogdaki sayfaları canlı okur; bütün satıcıları gösterir. İsteğe bağlı `product_key` ön eki (ör. `samsung_`) ile yalnız o ürünler. |
| `tests/manual/live_discovery_check.py` | Keşfi kataloğa yazmadan canlı çalıştırır; `--trace` ile her kararın nedenini gösterir. |
| `.github/workflows/ci.yml` | Her push/pull request'te Black, Flake8 ve testleri çalıştırır. |

## Komutların ayrıntısı

Windows ve PowerShell, Python sanal ortamı `.venv`:

```powershell
# Kurulum: yalnız biten aşamanın bağımlılıkları + test/biçim araçları
.venv\Scripts\python.exe -m pip install -e ".[dev]"

# Otomatik testler (internete çıkmaz)
.venv\Scripts\python.exe -m pytest tests/test_trendyol_scraper.py tests/test_hepsiburada_scraper.py tests/test_discovery.py -q

# Biçim ve kalite kontrolü (yalnız değişen dosyalarda çalıştırın)
.venv\Scripts\python.exe -m black --check <dosyalar>
.venv\Scripts\python.exe -m flake8 <dosyalar>

# Keşif: önce kataloğu değiştirmeden rapor
.venv\Scripts\python.exe -m app.discovery --dry-run --target apple_iphone_15

# Keşif: doğrulanan yeni sayfaları kataloğa ekle
.venv\Scripts\python.exe -m app.discovery --target apple_iphone_15

# Keşif tanılaması: rapor + her kararın izi (katalog değişmez)
.venv\Scripts\python.exe tests\manual\live_discovery_check.py apple_iphone_15 --trace

# Canlı fiyat kontrolü: katalogdaki bütün sayfalar (veya yalnız bir ön ek)
.venv\Scripts\python.exe tests\manual\live_scraper_check.py
.venv\Scripts\python.exe tests\manual\live_scraper_check.py samsung_ | Out-File -Encoding utf8 data\scraper_samsung.json
```

Türkçe karakterlerin terminalde doğru görünmesi için oturum başında bir kez
`[Console]::OutputEncoding = [Text.Encoding]::UTF8` çalıştırın. Keşif hedef
başına yaklaşık 2 dakika sürer (istekler arası 3 sn bekleme); 24 etkin hedefin
tamamı yaklaşık 50 dakikadır. Keşif raporu her çalışmada (dry-run dahil)
`data/discovery_report.json` dosyasının üzerine yazılır; saklamak istediğiniz
raporu kopyalayın.

`--target` verilmezse bütün etkin hedefler taranır. Yerelde sonraki aşamalara
ait taslak dosyalar bulunduğu için Black/Flake8'i bütün `app` klasöründe değil,
değişen dosyalarda çalıştırın; CI yalnızca Git'teki dosyaları denetler.

Gerçek dosyalara dokunmadan denemek için ortam değişkeni kullanılabilir:

```powershell
$env:CATALOG_PATH = "data/deneme_katalog.json"   # kataloğun kopyası
$env:DISCOVERY_PATH = "data/deneme_hedef.json"   # geçici hedefler
```

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
7. Her aday sayfa açılır: ürün kimliği, marka, telefon kategorisi, model,
   kapasite ve (hedefte `network` varsa) "Mobil Bağlantı Hızı" doğrulanır.

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

### Rapor: `data/discovery_report.json`

| Alan | Anlamı |
|---|---|
| `dry_run` | Çalışma katalog yazmadan mı yapıldı. |
| `complete` | Kullanılan kaynakların tamamı tarandı mı. Bütün pazaryerinin bulunduğunu **kanıtlamaz**. |
| `results` | Hedef × platform başına ayrıntı: adaylar (renk, RAM, garanti yazısı), uyarılar, taranan arama/ürün sayfası sayısı. RAM ve garanti yazısını yalnız Trendyol doldurur. |
| `added_products`, `added_listings` | Bu çalışmada eklenen ürünler/sayfalar. |
| `existing_listings` | Yeniden görülen, zaten katalogda olan sayfalar. |
| `retained_unobserved_listings` | Bu taramada görülmeyen ama katalogda korunan sayfalar; güncel teklif sayılmaz. |
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
| `filter_unavailable` | Trendyol telefon kategorisi filtresi bulunamadı. |
| `category_partial` | Birden çok telefon kategorisi var, yalnızca ilki tarandı. |
| `count_mismatch` | Trendyol'un bildirdiği toplamla gelen ürün sayısı farklı. Bugünkü nedeni reklam kartları: sonuçların arasına giren reklamlar 2–3 ürünü hiçbir sayfaya düşürmez (bkz. bilinen sınırlar). |
| `search_limit`, `product_limit` | Sayfa veya ürün sınırı doldu. |
| `repeated_page` | Site aynı sonuç sayfasını tekrar döndürdü; sayfalama durduruldu. |
| `variant_fetch`, `missing_variants` | Varyant listesi alınamadı veya boş geldi. |
| `group_url_pending` | Hepsiburada kartının adresi ne ürün (`-p-`) ne grup (`-pm-`) biçiminde; çözülemedi. |

`rejected` içindeki kayıtlar (tek bir aday atlanır, tarama sürer):

| Kayıt | Anlamı |
|---|---|
| `candidate_rejected` | Aday sayfa doğrulanamadı; ayrıntıda neden ve ürün adı var (başka model, kapasite, ağ türü, yurt dışı sürüm, aksesuar…). Taramayı da kısmi sayar. |
| `catalog_conflict` | Sayfa katalogda başka bir ürüne bağlı; aday yazılmadı, mevcut kayıt korundu. |

Komutun çıkış kodu: `0` tam tarama, `2` kısmi tarama (doğrulanmış kayıtlar yine
eklenir), `1` keşif başlatılamadı.

## Fiyat okuma nasıl çalışır

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
   seçenek listesindeki `Kapasite`).
2. `/api/v1/product/listings/{sku}` ile bütün satıcılar alınır.
3. Satıcı yoksa veya her satıcı açıkça satılamaz (`isSalable: false`) ise sonuç
   `Tükendi` olur. Bir satıcıda stok alanı hiç yoksa sonuç Tükendi **değil**,
   `parse` hatasıdır; site alanı değiştirirse sayfalar sessizce Tükendi olmaz.
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

## Kimlik kuralları

Keşif ve scraper aynı fonksiyonu (`app/scraper/parsing.py → identify`) kullanır;
böylece keşfin kabul ettiği sayfayı scraper aynı girdilerle reddetmez.

- Başlık tam modeli içermeli: "iPhone 16" hedefi "iPhone 16e", "16 Plus",
  "16 Pro" başlıklarını; "Galaxy S24" hedefi "S24+", "S24 FE", "S24 Ultra"
  başlıklarını; "iPhone 13" hedefi "13 mini" başlığını kabul etmez.
- Yenilenmiş, ikinci el, teşhir, **yurt dışı sürüm** ("International Version",
  "Global Version", "Yurt Dışı") ve aksesuar (kılıf, şarj, koruyucu…) reddedilir.
- Kapasite, sayfanın yapısal verisinden ve başlıktan okunur; iki kaynak
  çelişirse sayfa reddedilir, hiçbirinde yoksa da reddedilir. TB desteklenir
  (1 TB = 1024 GB). Ardından "RAM" yazan değer hafıza sayılmaz ("128 GB 12 GB
  Ram" → 128). Etiketsiz iki değer varsa ("12GB+512GB") başlık kullanılmaz,
  yapısal veri kullanılır.
- Ayrı model sayılan ekler: Pro, Plus, Max, Ultra, FE, Lite, mini, **Edge, Air**.
  "Galaxy S25 Edge" S25 hedefine, "iPhone 17 Air" yazan bir sayfa iPhone 17
  hedefine girmez.
- Satıcıların `_` ile ayırdığı adlar ("Galaxy S25 Ultra_12GB_256GB") boşlukla
  ayrılmış gibi okunur; aksi halde "Ultra" görülmüyor ve sayfa hem S25 hem S25
  Ultra sayılıyordu (canlıda `catalog_conflict` olarak yakalandı).
- Hedefin `exclude_terms` ifadelerini içeren başlıklar reddedilir; hedefte
  `network` varsa sayfanın yapısal ağ türü hedefle çelişemez.

## Testler ne kanıtlar, ne kanıtlamaz

- **Otomatik testler (59):** Kuralların doğru çalıştığını kayıtlı yanıtlarla
  kanıtlar. Hata düzeltmelerinin her biri, canlıda görülen gerçek bir örneğe
  dayanan regresyon testiyle korunur. Sitelerin bugün hâlâ aynı yapıda olduğunu
  kanıtlamaz.
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
- Arka arkaya çok tarama Trendyol'da geçici engele yol açabilir (25 Eylül'de
  yarım saatte 7 tarama sonrası 10 dakika engel). Günlük fiyat toplama bu
  yoğunlukta değildir; keşif seyrek çalışır.
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
Hepsiburada/Trendyol). Son
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
