# Akıllı Telefon İndirim Takip ve Tahmin Sistemi — Proje Planı

Son güncelleme: 29 Eylül 2026.

Bu belge **kararların ve aşama durumunun** ana kaynağıdır. Sistemin genel
tanıtımı [README.md](README.md), ayrıntılı işleyişi, komutları, kuralları ve
dosyaların görevleri [docs/teknik.md](docs/teknik.md) içindedir.
"Uygulandı", "planlandı" ve "karar bekliyor" ifadeleri birbirinin yerine
kullanılmaz; gerçek durum kod ve testlerle doğrulanır.

## 1. Amaç

Trendyol ve Hepsiburada'daki akıllı telefon tekliflerini düzenli olarak toplayıp
her telefon için takip edilen en ucuz fiyatı ve geçmişini sunmak; yeterli geçmiş
biriktiğinde fiyatın yakında düşüp düşmeyeceğini tahmin etmek.

Uzun vadeli akış:

**discovery.json → keşif → catalog.json → periyodik fiyat toplama → veritabanı →
hazır özetler (FastAPI) → Streamlit arayüzü → yeterli geçmişle ML**

Kullanıcı arayüzde arama yaptığında canlı scraping veya model eğitimi
çalışmaz; arayüz önceden hazırlanmış sonuçları okur.

## 2. Aşama durumu

| Aşama | Durum | Kanıt |
|---|---|---|
| 1. Fiyat okuma (Trendyol, Hepsiburada scraper) | ✅ Uygulandı | `a36b5b6`, `b0f466c`, `a716c9a` |
| 2. Otomatik model/kapasite/renk keşfi | ✅ Uygulandı | `e00a435` |
| 3. Trendyol doğrulanmış stoksuz sayfa | ✅ Uygulandı | `e6664a3` |
| 4. Scraper/discovery kabul kontrolü (6 adım) | ✅ Tamamlandı | `4d5613d`, Bölüm 5 |
| 5. Katalogun 25 hedefle sıfırdan kurulumu ve kod denetimi | ✅ Tamamlandı | Bölüm 6 |
| 6. Veritabanı ve zamanlanmış toplama | ⏳ Sürüyor: Adım 0–3, 5 ve 8 tamamlandı (şema, katalog eşitleme, toplama turu, ilk tam tur 326/326 hatasız, tek piyasa geçmişi araştırması); Adım 8 sonucunda aktarım kaynağı seçilmedi. Görev Zamanlayıcı kuruldu (28 Eylül), 2–3 günlük gözlem sürüyor | Bölüm 9 |
| 7. FastAPI ve Streamlit | 🔜 Planlandı, başlanmadı | Bölüm 9 |
| 8. ML (indirim tahmini) | 🔜 Planlandı, başlanmadı | Bölüm 9 |
| 9. Docker ve 7/24 işletim | 🔜 Planlandı, başlanmadı | Bölüm 9 |

Önceki aşamalardan kalan yerel taslaklar (eski `app/database`, `app/ml_model`,
`app/api`, `app/services`, `app/worker.py`, `frontend/`, Docker dosyaları ve
Akakçe/Cimri taslakları) 28 Eylül 2026'da `_eski_taslaklar/` klasörüne taşındı;
silinmedi, `.gitignore` ile Git dışında tutulur. Tamamlanmış iş değildir,
projeye bağlı değildir; yeni tasarımda yalnızca örnek olarak incelenebilir.

Güncel katalog (28 Eylül 2026): **59 ürün, 327 bağlantı** (Hepsiburada 213,
Trendyol 114; 1 bağlantı pasif). Keşif hedefleri 25: Apple 9, Samsung 8, Xiaomi 6, POCO 2
(X5 Pro satılmadığı için kapalı). Tam liste docs/teknik.md'deki "Yeni telefon ekleme"
bölümündedir.

## 3. Ürün kapsamı ve kimlik kuralları (uygulandı)

- Platformlar Trendyol ve Hepsiburada; kategori yalnızca yeni akıllı telefon.
  Başlangıç hedefi 20–30 modeldi; bugün 25 hedef kataloğa alınmıştır.
- Kullanıcı `config/discovery.json` içinde marka (sitedeki marka etiketi; POCO
  ayrı marka) ve tam model yazar; gerekirse `exclude_terms` ve `network`.
  Yeni telefon için Python kodu değişmez, renk bağlantısı elle toplanmaz.
- **Ürün** = marka + tam model + depolama kapasitesi. iPhone 15 128 GB ile
  256 GB farklı `product_id` alır. Pro, Plus, Pro Max, Ultra, FE, mini, Edge,
  Air, 16e ayrı hedeflerdir. **RAM ve garanti türü ürünü bölmez** (karar, 27
  Eylül 2026; Bölüm 6); bulunabilen RAM ve garanti yazısı raporda tutulur.
- **Bağlantı** = ürünün bir sitedeki bir sayfası (genelde bir renk). Aynı renk
  ve kapasitenin farklı sayfaları ayrı bağlantı olarak izlenebilir. Katalog
  satıcı başına adres tutmaz.
- Aynı adı taşıyan farklı telefonlar hedefteki isteğe bağlı `exclude_terms`
  (başlıktan) ve `network` (sayfanın yapısal "Mobil Bağlantı Hızı" değerinden)
  ile ayrılır. 4G hedefi: `model: "Redmi Note 14 Pro"`, `network: "4G"`,
  `exclude_terms: ["5G"]` → başlıkta veya özellikte 5G yazan sayfa dışlanır,
  gerisi (alanı boş olanlar dahil) 4G sayılır. Genel bir "5G ayrı model"
  kuralı bilinçli olarak yoktur.
- Yenilenmiş, ikinci el, teşhir, yurt dışı sürüm ve aksesuar ürünler reddedilir.
- Keşif ve scraper aynı kimlik kuralını kullanır (`app/scraper/parsing.py →
  identify`): model, kapasite (yapısal veri + başlık; çelişki reddedilir; TB
  desteklenir) ve dışlanan ifadeler birlikte doğrulanır. `_` ile ayrılmış
  adlar boşluklu gibi okunur.
- Trendyol'da bağlantının rengi sayfanın renk seçicisindeki addır (varyant
  listesi); satıcının "Renk" özelliği yalnız yedek olarak kullanılır.
- Fiyat karşılaştırması aynı `product_id` içindeki takip edilen teklifler
  arasındadır; farklı kapasiteler karşılaştırılmaz.
- Garanti türü ve RAM ürün kimliğine katılmaz (karar verildi, Bölüm 6).

## 4. Mimari ve veri kararları (uygulandı)

### Mimari

- Modüler yapı: scraper, discovery ve (ileride) kalıcılık, servis, ML ve sunum
  ayrı sorumluluklardır; dosya sınırı tek sorumluluğa göre belirlenir.
- Scraper/discovery HTTP istekleri yalnızca `app/scraper/http.py` üzerinden,
  `curl_cffi` ve `impersonate="chrome120"` ile yapılır. Playwright, Selenium,
  standart `requests` veya doğrudan `httpx` kullanılmaz.
- HTTP katmanı: izinli alan adları, zaman aşımı, sınırlı tekrar, 3 sn istek
  aralığı, yönlendirme kontrolü, yanıt boyutu sınırı, istek bütçesi;
  401/403/418/429 `blocked` sayılır, veri uydurulmaz.
- Scraper sözleşmesi `fetch(listing) -> PriceObservation`; platforma özgü işler
  `get_product_data` içindedir. Factory platform modülünü adından yükler; yeni
  site mevcut scraper'a koşul eklenerek değil kendi modülüyle eklenir.
- Discovery scraper'dan ayrıdır: keşif bağlantı bulur, scraper fiyat ve stok
  okur. Scraper/discovery içinde SQL veya ML yapılmaz. Scraper ile veritabanını
  yalnızca toplama turu (`app/collection`) bağlar; SQL `app/database` içindedir.
- Siteye giden bütün girişler (tur, keşif, canlı kontrol araçları) ortak bir
  dosya kilidi (`data/scrape.lock`) paylaşır; aynı anda iki süreç siteye gitmez.
- Tanılama izi (`trace`) ve bütün teklif listesi yalnız manuel kontrol
  araçlarında görünür; üretim sözleşmesi sade kalır ve araçlar aynı üretim
  kodunu kullanır.

### Fiyat ve stok

- Para TRY kuruş cinsinden tam sayıdır (5724900 = 57.249,00 TL); zamanlar UTC.
  Veri Pydantic V2 strict ile doğrulanır.
- **Güncel fiyat** = sayfada gösterilen koşulsuz indirimli fiyat. Trendyol'da
  `discountedPrice` ile `sellingPrice`'ın küçüğü; Hepsiburada'da
  `discountedPrice`, yoksa `price`. Adet/sepet/kupon koşullu indirimler dahil
  değildir.
- **Üstü çizili fiyat** = sayfada çizili görünen fiyat; güncel fiyattan büyük
  değilse `null`. İndirim tahmininin referansı değildir.
- Her sayfa için yalnızca seçilen (en ucuz uygun) teklif döner; fiyat, satıcı,
  puan ve stok aynı tekliften alınır. Eşitlikte satıcı adına göre karar verilir.
- **Tükendi** yalnızca açık stok sinyaliyle verilir (Trendyol: sayfadaki uygun
  teklifler açıkça stok dışı; Hepsiburada: satıcı listesinde satılabilir teklif
  yok). Ağ/ayrıştırma hatası, engellenme ve çelişkili yanıt Tükendi değildir.
- **Kritik Stok** yalnızca açık kaynak sinyaliyle verilir; bu sinyal yalnız
  Trendyol'da vardır.

### Katalog

- `config/discovery.json` kullanıcıya, `config/catalog.json` keşfe aittir.
- Kimlikler değişmez, yeniden kullanılmaz; görülmeyen kayıtlar silinmez.
  Tekrar çalıştırma çift kayıt üretmez.
- Katalogla çelişen aday yazılmaz, `catalog_conflict` olarak raporlanır;
  diğer geçerli adaylar eklenir.
- Katalog kilit altında yeniden okunur ve atomik olarak yazılır; `--dry-run`
  kataloğa yazmaz. Kısmi taramada doğrulanmış yeni kayıtlar eklenebilir.
- `complete` yalnızca kullanılan kaynakların tarandığını ifade eder; bütün
  pazaryerinin bulunduğunu kanıtlamaz.

## 5. Kabul kontrolü (24–25 Eylül 2026)

Veritabanından önce scraper ve discovery canlı veri ve kullanıcının tarayıcı
karşılaştırmasıyla 6 adımda denetlendi. Testler 25'ten 47'ye çıktı; her
düzeltme canlıda görülen gerçek bir örneğe dayanan regresyon testiyle korunur.

| Adım | Sonuç |
|---|---|
| 1. Keşif kapsamı | `--trace` eklendi. Trendyol'daki eksik kapasiteler (iPhone 16 256/512, iPhone 15 512) kaynakta yok; kod hiçbir iPhone 15/16 kartını yanlış elemedi. Hepsiburada'daki eksik aile `-pm-` bağlantısı yüzünden kaçırılıyordu. |
| 2. Kod hataları | Tek ortak kimlik kuralı; `-pm-` grup sayfaları; yenilenmiş kategorinin hariç tutulması ve `category_partial`; retlerde ürün adı; Hepsiburada stoksuz sayfa → Tükendi, çelişkili yanıt → `api_error`. |
| 3. Başka marka | Galaxy S24 ve Redmi Note 14 geçici hedeflerle doğru sonuç verdi. Boş SKU'lu varyant kaydı çökmesi ve Xiaomi marka filtresi düzeltildi; `exclude_terms` eklendi. |
| 4. Keşif → fiyat | Katalogdaki 44 sayfanın tamamı hatasız sınıflandı (16 Stokta Var, 5 Kritik Stok, 23 Tükendi). Satıcı listeleri ve fiyatlar tarayıcıyla eşleşti. Trendyol fiyat tanımı düzeltildi. |
| 5. Tekrar ve hata | Kataloğun kopyasında iki gerçek keşif: ikincisinde sıfır ekleme, dosya aynı. Çakışma davranışı değiştirildi. Yeni `hepsiburada_hbcv0000d3aulb` bağlantısı gerçek kataloğa eklendi (44 → 45). |
| 6. Durum kritiği | README ve bu plan yeniden yazıldı. Ölü kod taraması yapıldı: arama aşaması ve Hepsiburada adres doğrulaması sağlamlaştırıldı, kullanılmayan kod ve gelecek aşama kalıntıları (DB/ML/API tanımları, 9 çalışma ayarı, 9 bağımlılık) kaldırıldı. Temiz bir Python ortamında yalnızca 4 bağımlılıkla testler ve lint geçti. Veritabanına geçiş değerlendirmesi sıradaki iştir. |

Bu adımda alınan kararlar:

- Trendyol **model filtresi kullanılmayacak**: satıcı girişli olduğu için
  güvenilir değil (iPhone 16e sayfaları "iPhone 16" etiketli) ve hiçbir marka
  20 sayfa sınırına yaklaşmadı (Apple 3–4, Samsung 6, Xiaomi 4 sayfa).
  Filtreler yalnızca daraltma içindir; kimliği bizim kontrolümüz belirler.
- 4G/5G gibi ayrımlar hedef bazında `exclude_terms` ile yapılır.
- Güncel fiyat, sayfadaki koşulsuz indirimli fiyattır.
- Birleştirme çakışmasında yalnızca çakışan aday atlanır.
- Galaxy S24 ve Redmi Note 14 gerçek `discovery.json`'a eklenmedi; yalnızca
  denendi.

## 6. Katalog kurulumu (25–27 Eylül 2026)

Veritabanından önce katalog kalıcı hedef listesiyle sıfırdan kuruldu; böylece
ürün kimliği kararları (RAM, garanti, 4G/5G, renk kaynağı) veritabanı yokken,
kataloğu yeniden kurmanın ucuz olduğu anda verildi.

- Eski katalog (6 ürün / 45 bağlantı) boşaltıldı; elle verilmiş 3 Trendyol
  bağlantısı ve stoksuz sayfalar bilinçli olarak bırakıldı. Testler artık
  `tests/fixtures/discovery/catalog.json` sabit kopyasını okur. Program
  çıktıları, önbellekler ve geçici dosyalar temizlendi.
- Kullanıcı 23 yeni model seçti (toplam 25 hedef). Her marka için döngü:
  `discovery.json` → keşif → rapor incelemesi → canlı fiyat kontrolü →
  kullanıcının tarayıcı karşılaştırması. Komutları kullanıcı kendi
  terminalinden çalıştırdı; canlı işler arka planda yürütülmedi.
- Sonuç: 57 ürün, 306 bağlantı (1'i pasif). Son toplu fiyat kontrolünde 304/306
  okundu (163 Stokta Var, 70 Kritik Stok, 71 Tükendi); kalan 2 sayfanın "12 GB
  Ram" başlık sorunu düzeltildi ve iki sayfa yeniden hatasız okundu.
- Kapanış taraması (28 Eylül, gerçek yazma): düzeltilmiş kodla 24 etkin
  hedefin tamamı tarandı (ilk 7'si bir önceki dry-run'da). Sıfır çakışma,
  sıfır ağ hatası; yurt dışı sürüm sayfası yeni kuralla reddedildi. Satışa
  yeni giren veya Hepsiburada'nın ilk sayfasında bu kez görünen 21 bağlantı ve
  2 ürün (Galaxy S25 512 GB, Redmi Note 14 Pro 5G 256 GB) eklendi →
  **59 ürün, 327 bağlantı**. Aynı gün 21 yeni bağlantı çıkması, pazaryerinin
  sürekli değiştiğini ve keşfin düzenli çalışması gerektiğini gösterir
  (Bölüm 8, keşfin zamanlanması). Kullanıcı tarayıcıda 9 sayfada fiyat, satıcı,
  çizili fiyat ve stoku; 4 sayfada renk seçicisi ve ağ türü alanını doğruladı.
- Düzeltilenler (docs/teknik.md "Katalog kurulumu" tabloları): Trendyol `/sr` sayfası
  engeli (403), rapora HTTP kodu, `edge`/`air` ekleri, `_` ayraçlı adlar,
  renk kaynağı (varyant listesi), POCO markası, `network` alanı, "4.5G"
  dışlama hatası, "RAM" etiketli başlık kapasitesi, yurt dışı sürüm dışlama.
- Kodu baştan okuyan denetim (27 Eylül) ek olarak şunları buldu ve düzeltildi:
  Hepsiburada'da stok alanı eksikken Tükendi verilmesi (kural ihlali), 3 sn
  beklemenin bağlantılar arasında uygulanmaması, çerez çakışması hatası, "5G+"
  gibi ağ değerlerinin tanınmaması, katalogun CRLF yazılabilmesi. Testler
  47 → 59. Ertelenen bulgular Bölüm 7'deki bakım listesindedir.

Bu adımda alınan kararlar:

- **RAM ürünü bölmez:** 57 üründe aynı kapasitenin farklı RAM'li sürümü
  görülmedi; satıcı girişleri tutarsız (başlık "8+256", özellik "12 GB RAM").
- **Garanti türü ürünü bölmez:** görülen garanti yazıları Türkiye'de geçerli
  resmi garanti ("… Türkiye Garantili", "Resmi Distribütör Garantili", "KVK
  Garantili"); garanti yazısı raporda bilgi olarak tutulur.
- **Yurt dışı sürümler kapsam dışıdır:** satıcının garanti alanı güvenilir
  değil (yurt dışı sürüm `trendyol_991304922` sayfasında "Apple Türkiye
  Garantili" yazıyordu). Ürün adında "International Version", "Global
  Version" veya "Yurt Dışı" geçen sayfa yenilenmiş/teşhir gibi reddedilir; o
  bağlantı katalogda pasife alındı (tek seferlik düzeltme).
- **4G/5G:** başlıkta veya özellikte 5G yazan sayfa 5G; gerisi 4G
  (`network` + `exclude_terms`). Alanı boş bırakılmış, başlıksız bir 5G
  sayfasının 4G'ye girme riski kabul edildi.
- **Trendyol rengi** sayfanın renk seçicisindeki addır; dili karışıktır
  (İngilizce adlar çevrilmez).
- **Trendyol reklam kartları** (`count_mismatch`) için kod değişikliği yapılmadı;
  bilinen sınır.
- **POCO** ayrı marka olarak hedeflenir; X5 Pro satılmadığı için kapalı.

## 7. Bilinen ve kabul edilen sınırlar

- Hepsiburada arama API'si bizi engelliyor (HTTP 403, kalıcı); Hepsiburada
  taraması her zaman "kısmi" raporlanır. Kapsam arama/model sayfasının ilk
  sayfası (36 kart) ve ürün sayfalarındaki seçenek listesiyle sağlanır;
  kalabalık aramalarda eksik kalabilir (Galaxy S25: 36/140, Redmi aramaları
  kılıf ilanlarıyla dolu).
- Trendyol araması ve varyant listesi yalnızca satıştaki sayfaları gösterir;
  stoktan çıkan sayfa yeniden keşfedilemez, önceden eklenmişse korunur.
- Trendyol reklam kartları sayfa kaydırır; toplamdan 2–3 ürün hiçbir sayfaya
  düşmez (`count_mismatch`). Sayfalamayla ulaşılamadığı ölçüldü.
- Trendyol renk adları satıcı girdisi olduğu için dili karışıktır; bir sayfada
  "Çok Renkli" kaldı. Renk adları platformlar arasında birleştirilmez.
- Keşif, katalogdaki bağlantının rengini veya ürününü güncellemez; kural
  değişirse katalog yeniden kurulur.
- `exclude_terms` ve `network` keşif anında uygulanır; sonradan eklenen kural
  eski katalog kayıtlarını çıkarmaz.
- Arka arkaya çok tarama Trendyol'da geçici engele yol açabilir.
- Turlar bilgisayarın o anki internet bağlantısına bağlıdır. Bağlantı koparsa
  etkilenen sayfalara `network` hatası yazılır, veri uydurulmaz ve hata aynı
  tur içinde yeniden denenmez (tur 3, 28 Eylül: 47/326 sayfa; bilgisayar bir
  telefonun hotspot'una bağlıydı ve bağlantı birkaç dakika koptu).
- Fiyat ve stok iki tur arasında (12 saat) değişip geri dönebilir; bu
  değişiklikler görülmez. Geçmiş, turların anlık görüntüleridir (28 Eylül:
  bir sayfa 2 saatte Tükendi → Kritik Stok, bir başkası 71.059 → 75.524 TL).
- Ürün adında söylemeyen bir yurt dışı sürümü ayırt edilemez.
- Siteler değişebilir; bakım gerekebilir. "Bir daha bakmaya gerek yok" garantisi
  verilmez.
- Akakçe ve Cimri'nin 29 Eylül 2026'da incelenen kullanım koşulları, site
  içeriğinin kopyalanması/işlenmesi hakkında kısıtlar içeriyor. Az sayıda
  herkese açık sayfa teknik araştırma için incelenebilir; geçmişin düzenli
  indirilmesi ve projede saklanması ayrı değerlendirilir. Yazılı izin her
  web kazıma denemesi için zorunlu varsayılmaz.
  Kaynaklar: https://www.akakce.com/kullanim-sozlesmesi/ ve
  https://www.cimri.com/kullanim-kosullari .
  Cimri koşullarında kamuya açık bilginin kullanım amacı sınırlandırılıyor
  (2.2); site unsurlarının kopyalanması/işlenmesi (3.1) ve başka mecrada
  kullanılması (4.12) kısıtlanıyor. Bu koşullarla düzenli geçmiş indirip
  saklamak için uygun kullanım hakkı doğrulanmadı; araştırma sonunda
  veritabanına aktarım kaynağı seçilmedi. Bu, teknik erişim sonucundan ayrı.
- İlk Akakçe teknik denemesi (29 Eylül, iPhone 16 128 GB ürün sayfası) tek
  istekte HTTP 403 `blocked` verdi (`artifacts/market_history_probe/` yerel
  raporu). Ürün eşleşmesi veya geçmiş biçimi okunamadı. Aynı adrese tekrar
  istek atılmaz; bu tek sonuç bütün Akakçe sayfalarının erişilemez olduğunu
  kanıtlamaz.
- Cimri teknik denemeleri (29 Eylül) iPhone 16 128 GB, Galaxy S24 256 GB ve
  Xiaomi 14T Pro 256 GB sayfalarını okudu; üç başlık da katalogla eşleşti.
  "En Düşük Fiyat" tablolarında sırasıyla 49, 58 ve 29 farklı tarihli aday
  satır bulundu (ilk ikisi 2 Temmuz–28 Eylül, Xiaomi 2 Temmuz–27 Eylül).
  Tarihler kesintisiz günlük seri değil; fiyatın tam kapsamı ve eksik günlerin
  anlamı bu raporlarla doğrulanmadı.
- Xiaomi 14T Pro 256 GB sayfasında "Tablo Görünümü" 2 Temmuz 2026'dan başlıyor;
  "1 Yıl" grafik görünümünde ise 30 Eylül 2025 için 34.539,13 TL noktası
  göründü (29 Eylül). Kullanıcının tarayıcıda kaydettiği HTML'deki
  `priceHistoryTablePrices` 90 günlük kayıt içeriyor. Grafiğe ait tarayıcı
  yanıtındaki `priceHistoryV2`, ürün kimliği 2372365900, son gün 29 Eylül 2026
  ve yeniden eskiye sıralı 365 fiyat içeriyor; ilk gün 30 Eylül 2025 ve fiyatı
  34.539,13 TL. HTML'deki 90 günlük fiyatın tamamı bu diziyle eşleşti.
  Tekrarlanan fiyatlar, her gün bağımsız yeni fiyat gözlemi yapıldığını
  kanıtlamıyor. Grafik yanıtı `POST https://www.cimri.com/api/cimri` isteğinden
  geldi; JSON gövdesinde `queryName` değeri `priceHistoryV2Query`,
  `variables.productId` değeri `"2372365900"` ve `platform` değeri
  `CIMRI_DESKTOP_V2`. İstekte tarih aralığı yok;
  Xiaomi yanıtında 365 fiyat var. Araştırma veritabanına yazmadı.
- Cimri grafik yanıtını araştırma aracında okumak için kod ve sentetik
  verilerle ağsız testler hazırlandı; gerçek yanıtlar Git dışındadır. Ürün
  sayfası doğrulandıktan sonra aynı
  HTTP oturumunda API çağrılır; tarihli noktalar yerel rapora yazılır. Kullanıcı
  yeni kodla Xiaomi'yi canlı çalıştırdı (29 Eylül): 3 HTTP isteği, doğru ürün
  kimliği, 30 Eylül 2025–29 Eylül 2026 arasında 365 nokta, 0 eksik fiyat ve
  HTML'deki 90 günün tamamında fiyat eşleşmesi. İlk gün 34.539,13 TL, son gün
  46.549,05 TL. Apple canlı denemesi de 3 istekle doğru ürün kimliğini,
  30 Eylül 2025–29 Eylül 2026 arasında 365 noktayı, 0 eksik fiyatı ve 90/90
  tablo eşleşmesini verdi (ilk fiyat 54.999 TL, son fiyat 71.390,42 TL).
  Samsung canlı denemesi de 3 istekle doğru ürün kimliğini (2305983921),
  aynı tarih aralığında 365 noktayı, 0 eksik fiyatı ve 90/90 tablo eşleşmesini
  verdi (ilk fiyat 33.749 TL, son fiyat 42.750 TL). Üç ürünün tamamında
  teknik karşılaştırma olumlu; tarihsel satıcı kapsamı ve bağımsız günlük
  gözlem sıklığı hâlâ bilinmiyor.
- [Cimri ürün sayfasındaki](https://www.cimri.com/cep-telefonlari/en-ucuz-xiaomi-14t-pro-fiyatlari%2Ca2372365900)
  "2 satıcı arasındaki en ucuz" açıklaması, fiyatın Cimri'de listelenen
  teklifler arasında sunulduğunu gösteriyor. Tarihsel satıcı kapsamı ve eksik
  günlerin anlamı açıklanmıyor; bu seri bizim iki platformda takip ettiğimiz
  minimumla aynı kapsamda kabul edilmez.

### Bakım listesi (denetimde bulundu, ertelendi)

Hiçbiri yanlış fiyat veya stok üretmez; ya güvenli tarafta hata verir ya da
nadir durumdur. Veritabanı aşamasında veya bir hata görüldüğünde ele alınır.

- Tek bir satıcının bozuk fiyatı bütün sayfayı `parse` hatası yapar (fiyat
  uydurulmaz); teklif bazında atlanabilir.
- Hepsiburada fiyat isteğine konan yedek değerler yanıtla karşılaştırılmıyor.
- HTTP: 204/304 gibi yanıtlar başarı sayılıyor; POST yönlendirmede tekrar
  gönderiliyor; tekrarlar sonrası 5xx `network` diye raporlanıyor; 8 MB sınırı
  indirme sonrası denetleniyor.
- Keşif: Trendyol varyant adresi `-p-<id>` biçimi için denetlenmiyor;
  Hepsiburada canonical SKU'su alt dizeyle karşılaştırılıyor;
  `filter_unavailable` iki kez yazılabiliyor; hiç aday bulamayan Trendyol
  araması uyarısız "tam" sayılıyor; tarama sonrası yazma hatası "keşif
  başlatılamadı" (çıkış 1) diye görünüyor; rapor yolu sabit.
- Kimlik kuralında Türkçe ekler: aksesuar sözcükleri ek almış hâlleriyle
  ("Kılıfı", "Adaptörü") ve keşfin kategori süzgecinde "Kapağı" yakalanmıyor
  ("Cep Telefonu Kapağı" telefon kategorisi sayılıyor; `xfail` testiyle
  belgeli). Kapasite ve model doğrulaması ikinci koruma olduğu için yanlış fiyat
  üretmez; kural canlıda hedef markada bir örnek görülünce değiştirilir.
- 29 Eylül incelemesinde kapandı: test kapsamı maddeleri (Trendyol Kritik Stok,
  keşif CLI çıkış kodları, dry-run'ın kataloğa yazmaması, uyarı türleri, HTTP
  yönlendirme/yeniden deneme), ölü kod (etkisiz `except FetchError: raise`,
  erişilmez satır, tekrarlanan `_seller_rating`) ve hata kodu tablosu
  (docs/teknik.md "Hata kodları"). Regex'lerdeki `_` bilerek kaldı: tam
  genişlikli "＿" gibi nadir karakterler `normalize` sonrası yine `_` olur.

## 8. Açık kararlar

| Konu | Durum |
|---|---|
| Garanti türüne göre ayrım | **Karar verildi (27 Eylül 2026): ayrılmıyor;** yurt dışı sürümler ürün adından tanınıp kapsam dışı bırakılıyor. |
| Veritabanı teknolojisi, veri modeli, çalışma ortamı | **Karar verildi (28 Eylül 2026):** PostgreSQL 17, `psycopg` + ham SQL, kullanıcının bilgisayarı, günde 2 tur; ayrıntı Bölüm 9. SQLite önerisi bırakıldı. |
| Keşfin zamanlanması | **Karar verildi (28 Eylül 2026):** bu aşamada manuel, haftada bir; fiyat turuyla ortak kilit. Otomasyon, veritabanı birkaç hafta sorunsuz çalıştıktan sonra değerlendirilir. Kanıt: 28 Eylül kapanış taramasında tek günde 21 yeni bağlantı çıktı; Hepsiburada genel aramasının ilk 36 kartı her seferinde değişebildiği için tekrar eden keşif kapsamı artırır. |
| Piyasa geçmişi kaynağı | **Karar verildi (29 Eylül 2026):** Akakçe ve Cimri serileri birleştirilmeyecek. Adım 8 araştırması sonunda Cimri üç üründe teknik olarak doğrulandı; Akakçe'nin ilk örneği 403 verdi. Cimri'nin yayımlı koşullarında düzenli kopyalama/işleme için uygun hak doğrulanmadığından **şimdilik veritabanına aktarım kaynağı seçilmedi**; veri alımı başlamaz. Uygun kullanım hakkı veya başka kaynak bulunursa ayrıca planlanır. ML'de kullanımı o zaman kararlaştırılır (Bölüm 7 ve 9). |
| Cimri geçmişinin bir defalık kaydı | **Kullanıcı isteği (29 Eylül 2026):** katalogdaki telefonların Cimri geçmişi bir kez çekilip saklansın; Cimri'den düzenli toplama hedeflenmiyor. Üç örneğin tam serisi şimdilik yalnız Git dışındaki yerel araştırma raporlarında. Katalog geneli için eşleştirme, depolama ve veri kullanım kapsamı ayrı adımda netleştirilecek; toplu alım ve veritabanı aktarımı henüz yapılmadı. |
| Tur sonunda yalnız `network` hatası alan sayfalara ikinci geçiş | Karar bekliyor (Adım 6 gözleminden sonra). Kanıt: tur 3'te (28 Eylül) 47 sayfa bağlantı kesintisiyle `network` hatası aldı; son hatadan sonra kalan 154 sayfa cevap verdi, yani tur bitmeden bağlantı geri gelmişti. Yalnız `network` için ve tek geçiş düşünülüyor; `blocked` yeniden denenmez. |
| Gelecek aşama tanımları (`PricePoint`, `ProductSummary`, `MarketRecord`, `coverage_version`, zamanlama/ML ayarları, FastAPI/LightGBM/Streamlit bağımlılıkları) | Kaldırıldı (25 Eylül 2026). İlgili aşamada yeni tasarıma göre yeniden eklenecek; yerel taslaklar o zamana kadar çalışmaz. |

## 9. Sonraki aşamalar

### Veritabanı ve zamanlanmış toplama (sürüyor)

Amaç: katalogdaki etkin sayfaları günde 2 kez okuyup her sonucu kalıcı,
izlenebilir ve tekrarsız saklamak. Scraper ve discovery değişmez; yeni toplama
turu `fetch()` sonucunu veritabanına yazar. Korunacak gereksinimler: tekrar
kayıt engelleme; tur ve sayfa düzeyinde izlenebilirlik; fiyat gözlemi /
Tükendi / toplama hatasının ayrı tutulması; katalog kapsamı değiştiğinde sahte
fiyat düşüşü oluşmaması.

Kararlar (28 Eylül 2026, kullanıcıyla):

| Konu | Karar |
|---|---|
| Çalışma ortamı | Kullanıcının Windows bilgisayarı; Görev Zamanlayıcı ile her gün **10:00 ve 22:00**. Bilgisayar kapalıyken kaçan tur, açılınca bir kez telafi edilir. Sunucu Aşama 9'da. |
| Saklanan veri | Her turda sayfa başına yalnızca **seçilen teklif** (`fetch()` sonucu); scraper sözleşmesi değişmez. Satıcı bazlı geçmişin toplanmaması bilerek kabul edildi (27 Eylül ölçümü: 304 sayfada 1.021 uygun teklif). |
| Keşif | Bu aşamada manuel, haftada bir; kullanıcı çalıştırır ve raporu okur. Fiyat turu ile keşif **ortak kilit** paylaşır, aynı anda çalışmaz (3 sn bekleme süreç içinde tutulduğundan iki süreç siteye iki kat hızla gider). |
| Veritabanı | **PostgreSQL 17**, Windows servisi. Gerekçe: kısmi benzersizlik ve CHECK kısıtlarıyla kuralların veritabanında garanti edilmesi, `timestamptz`, transaction içinde migration, kullanıcının önceki deneyimi. |
| Erişim | **`psycopg` 3 + ham SQL + numaralı migration dosyaları**; ORM yok. Veri şekilleri Pydantic sözleşmelerinde kalır. |
| Sonuç tablosu | Tek tablo `listing_checks`: her tur × planlanan sayfa bir satır; `outcome` fiyat / Tükendi / hata. CHECK kısıtları hatanın fiyat veya Tükendi olarak yazılmasını engeller. |
| Sahte fiyat düşüşü | İki tur ancak **cevap veren sayfa kümesi** (fiyat veya Tükendi dönen sayfalar) aynıysa karşılaştırılır. Hata cevap değildir; Tükendi gerçek cevaptır. |
| Bağlantı ve yetki | Şifresiz `DATABASE_URL` / `TEST_DATABASE_URL`; şifre PostgreSQL'in `pgpass.conf` dosyasında, repoda değil. Proje kullanıcısı `fiyat_takip` yönetici değildir; yalnızca kendi iki veritabanının sahibidir. |

Adımlar (her biri ayrı commit). Uygulama sırası 28 Eylül'de **3 → 5 → 6 → 4**
olarak değiştirildi: canlı deneme ve zamanlayıcı öne alındı ki gerçek veri
erken birikmeye başlasın; görünüm (4) veri toplanırken yazılır ve gerçek
veriyle de denenir.

| Adım | Durum |
|---|---|
| 0. Hazırlık: taslakların taşınması, PostgreSQL 17, `fiyat_takip` kullanıcısı, `fiyat_takip` ve `fiyat_takip_test` veritabanları | ✅ Tamamlandı (28 Eylül) |
| 1. Şema, migrate komutu, CI'da PostgreSQL | ✅ Tamamlandı (28 Eylül): `001_initial.sql`, `python -m app.database migrate/status`, 32 veritabanı testi (toplam 91) |
| 2. Katalogun veritabanına eşitlenmesi | ✅ Tamamlandı (28 Eylül): `python -m app.database sync-catalog [--dry-run]`; kimlik değişiminde hiçbir şey yazmadan durur, katalogdan düşen kayıt pasife alınır; 22 test (toplam 113) |
| 3. Toplama turu ve ortak kilit | ✅ Tamamlandı (28 Eylül): `python -m app.collection [--prefix] [--scheduled]`; sayfa sonucu hemen ve bir kez yazılır, yarım kalan tur sonraki turda kapatılır; tur, keşif ve iki canlı kontrol aracı `data/scrape.lock` kilidini paylaşır; ayrıca veritabanı tur kilidi. Commit öncesi üç ek kontrol: (1) bağımsız kod incelemesi, 13 bulgu, 7 numara hariç hepsi düzeltildi ve testlendi (7 → Adım 4); (2) kasıtlı bozma testi: 37 bozmanın 33'ü testlerce yakalandı, kaçan 4'ü önceden tahmin edilen eşzamanlılık/güvenlik korumaları; (3) ilk canlı tur (`--prefix poco_`, 4 sayfa, 25 sn): 4/4 fiyat, çıkış 0. Testler 22 (toplam 143). |
| 4. Karşılaştırılabilirlik görünümü (sahte düşüş kuralı) | 🔜 (6'dan sonra). Aynı migration'a (002) ertelenen üç kural eklenecek: `sold_out` satırında fiyat/satıcı yasağı; kimlik alanlarının değiştirilmesini ve satır silinmesini reddeden tetikleyici (bugün yalnızca kodda korunuyor; elle SQL ile bozulabilir); çizili fiyatın güncel fiyattan büyük olması (sözleşme + CHECK; karar 29 Eylül). **Uygulama uyarısı:** kodda yeni migration varken veritabanı güncellenmemişse tur "şema güncel değil" deyip başlamaz; `migrate` 10:00 ve 22:00 turlarının dışında, kod değişikliğiyle aynı anda çalıştırılır. |
| 5. Canlı deneme (kullanıcı çalıştırır) | ✅ Tamamlandı (28 Eylül): ilk tam tur (tur 2, 15:48–16:19 TR saati, **30 dk 55 sn**): 326/326 sayfa okundu, **0 hata, 0 engellenme**; iki sayfa arası en uzun bekleme 9,4 sn. Hepsiburada 213: 139 fiyat, 74 Tükendi; Trendyol 113: 110 fiyat (77 Kritik Stok), 3 Tükendi. 8 ürünün bütün sayfaları Tükendi (çoğu eski iPhone'ların yüksek kapasiteleri). Tarayıcı karşılaştırması 4 sayfa: fiyat, çizili fiyat, satıcı, kuruşlu fiyat (turda 31 tane) ve Kritik Stok eşleşti; 15:49'da Tükendi okunan `trendyol_762254862` 17:47'de "Son 1 ürün" gösteriyordu, yeniden okumada da Kritik Stok çıktı (sayfa arada değişmiş). Aynı ürünün bir sayfasında fiyat 2 saatte 71.059 → 75.524 TL oldu. Bulunan tek hata: ön ek verilmeyen turda `note` NULL yerine boş yazı oluyordu (`concat_ws`); düzeltildi, test eklendi (toplam 144). Tur 2'nin kaydı elle değiştirilmedi. |
| 6. Görev Zamanlayıcı ve 2–3 günlük gözlem | ⏳ Kuruldu, gözlem sürüyor. Görev 28 Eylül akşamı `scripts/zamanlayici_kur.ps1` ile kuruldu; kullanıcı ilk turu `Start-ScheduledTask` ile başlattı (tur 3, `scheduled`, 23:22–23:55, 33 dk): `pythonw`, ortam değişkenleri, `pgpass.conf`, çalışma klasörü ve log dosyası Görev Zamanlayıcı ortamında çalıştı. 326 sayfanın 279'u cevap verdi (219 fiyat, 60 Tükendi), 47 sayfa `network` hatası aldı (DNS çözümlenemedi / zaman aşımı; Windows WLAN günlüğüne göre hotspot bağlantısı 23:27:38'de koptu, 23:30:52'de döndü); tur `completed`, çıkış 2, veri uydurulmadı. İlk tetikleyiciyle çalışan tur (tur 4, 29 Eylül 10:00:02, 30 dk 44 sn): 326/326 sayfa, **0 hata** (243 fiyat, 83 Tükendi), çıkış 0; aynı sabah temizlenen kodla gerçek sitelerde ilk tur, istek aralıkları önceki turlarla aynı (Hepsiburada ortalama 8,7 sn). Kararlar (28 Eylül, kullanıcıyla): görev **penceresiz** (`pythonw.exe`) çalışır, `--scheduled` çıktısı `data/logs/tur_<yerel tarih-saat>.log` dosyasına da yazılır (açık kalan bir pencere kapatılınca tur kesilirdi; Görev Zamanlayıcı çıktı saklamaz); görev repodaki `scripts/zamanlayici_kur.ps1` ile kurulur (ayarlar kodda, yeniden kurulabilir). Ayarlar: yerel saatle 10:00/22:00, kaçan tur açılınca bir kez, pilde de çalışır, uyandırmaz, 2 saat süre sınırı, kullanıcı adına yalnız oturum açıkken (docs/teknik.md "Zamanlanmış tur"). Kullanıcının dizüstünde boşta uyku kapalı (şarj ve pil). 5 yeni test (toplam 149); log kodunda 3 kasıtlı bozmanın 3'ü yakalandı; gerçek `pythonw.exe` ile siteye gitmeyen denemede log yazıldı, çıkış 1, tur açılmadı. **Commit öncesi projenin tamamı incelendi (29 Eylül):** 8 bağımsız inceleyici (scraper, keşif, veritabanı, tur, belgeler, güvenlik, okunabilirlik, test kalitesi) bütün dosyaları okudu; her bulgu ayrı bir doğrulayıcıya çürütülmek üzere verildi ve son bir denetçi kimsenin bakmadığı yerlere baktı. 168 ham bulgu → 135 tekil; 10'u çürütüldü, 125'i doğrulandı (57'si kısmen), +24 ek bulgu. Davranış değiştirmeyenler uygulandı: ölü kod temizliği, dışarıdan okuyana yönelik yorumlar (kilit numaraları, Tükendi kuralı, hata kodları, üç istekli Hepsiburada akışı…), belge düzeltmeleri ve testler **149 → 414** (116'sı PostgreSQL'de; yeni `tests/test_http.py`, `tests/test_contracts.py`). Kullanıcı davranış değiştiren bulgulardan üç grubu onayladı ve uygulandı: keşif sağlamlığı (UTF-8 çıktı, BOM'lu dosya okuma, kilit meşgulken çıkış 3, fazladan arama sayfası yok, pasif sayfalar "korunan" listesinde yok, adaptör hatası çıkış 1), migration koşucusu (yeniden adlandırılan dosya reddedilir, numara hatası bulunanları gösterir), tanılama çıktısı (boş satıcı kimliği, `missing_price`/`missing_seller`); her birinin testi önce eski kodda başarısız oldu. Çizili fiyat kuralı (sözleşme + CHECK) Adım 4'e alındı. Araç düzeni: Python `>=3.13,<3.14`, Black `>=26.1`; ortak yapay zekâ talimatları `AGENTS.md`'ye taşındı (Claude Code ve Codex aynı dosyayı okur), `.cursorrules` silindi. Testlere iki emniyet kemeri eklendi: gerçek ağ isteği ve kalıcı `DATABASE_URL` her testte kesilir. Yeni testler bellekte veya kopyada kasıtlı bozmalarla sınandı (75 bozmanın 73'ü yakalandı; kaçan 2'si eşdeğer bozma). Bir gerçek hata bulundu ve `xfail` ile belgelendi (Bölüm 7, Türkçe ekler). Davranış değiştiren bulgular kullanıcı kararına bırakıldı. |
| 7. Kapanış belgeleri | 🔜 |
| 8. Tek piyasa geçmişi kaynağı araştırması (Adım 6'nın 2–3 günlük gözlemi sırasında) | ✅ Araştırma tamamlandı (29 Eylül): Cimri üç üründe doğru kimlikle 365'er nokta (30 Eylül 2025–29 Eylül 2026), 0 eksik fiyat ve her üründe 90/90 tablo eşleşmesi verdi. Akakçe ilk örneği HTTP 403 verdi; diğer ürünlerine istek atılmadı. `tests/manual/market_history_probe.py` ortak HTTP katmanı/kilit ve dört istek bütçesiyle yalnız yerel rapor üretir. Cimri teknik adaydır; tarihsel satıcı kapsamı ve günlük gözlem sıklığı bilinmiyor. Yayımlı kullanım koşulları düzenli kopyalama/işleme için uygunluğu doğrulamadığından **aktarım kaynağı seçilmedi, veritabanına veri yazılmadı**. Kullanım hakkı veya alternatif kaynak netleşirse ayrı plan yapılır; iki seri birleştirilmez. |

Adım 8 canlı sonuçlar (29 Eylül 2026): Akakçe iPhone 16 128 GB sayfası 1
istekte HTTP 403 `blocked`; Cimri'nin üç örneğinde kimlik eşleşti ve HTML
tablosunda sırasıyla 49/58/29 farklı tarihli aday satır bulundu. Grafik API'si
Apple, Samsung ve Xiaomi için 365'er tarihli fiyat döndürdü; her birinde 0 eksik
fiyat ve 90/90 gömülü tablo eşleşmesi var (Bölüm 7). Tablo yaklaşık üç ayla
sınırlı, grafik 30 Eylül 2025'e uzanıyor. Cimri teknik adaydır; yayımlı
koşullarda düzenli kopyalama/işleme için uygun hak doğrulanmadığı için aktarım
kaynağı seçilmedi. Akakçe 403 için tekrar veya engel aşma yapılmaz.

Takvim (tahmin, 29 Eylül; kesin değil, Adım 8'in sonucuna bağlı):

| Tarih | İş |
|---|---|
| 29 Eylül | Adım 8 araştırması tamamlandı; kaynak seçilmedi. Adım 6 gözlemi sürüyor (turlar kendiliğinden çalışır) |
| 1 Ekim | Gözlem sonu: 6 turun özeti, bilerek yapılan kaçan tur telafi denemesi |
| 1–2 Ekim | Adım 4 (002 migration: görünüm ve kurallar) |
| 2–3 Ekim | Adım 7 kapanış belgeleri; veritabanı aşaması biter |
| Tarih belirsiz | Kullanıcının istediği Cimri geçmişinin bir defalık kaydı için kullanım kapsamı, katalog eşleştirmesi ve ayrı `market_history` tablosu/içe aktarma ayrıca planlanır |

Kendi verimizle ML için gereken 30 günlük geçmiş, ilk tam turdan (28 Eylül)
sayılırsa Ekim sonunda dolar; API/arayüz aşaması bu süre içinde ilerleyebilir.

Adım 0'da görülenler:

- Türkçe Windows'ta kurulum programının varsayılan locale'i
  (`Turkish_Türkiye.1254`) ASCII dışı karakter içerdiği için `initdb`
  başarısız oldu; kurulum programı yine de "tamamlandı" dedi, servis ve veri
  klasörü oluşmadı. Yeniden kurulumda küme `C` locale'iyle kuruldu; proje
  veritabanları `LOCALE_PROVIDER builtin`, `C.UTF-8` ile oluşturuldu (Türkçe
  karakterler saklanır, sıralama işletim sisteminden bağımsızdır).
- Yerel kurulum yalnızca bu bilgisayardan gelen bağlantılara izin verir
  (`pg_hba.conf`). Aşama 9'da sunucuya geçerken güçlü şifre ve erişim kuralları
  yeniden ele alınır.

Sıra gerekçesi: kendi fiyat verimiz geriye dönük toplanamaz; dış kaynakta
görünen geçmişin teknik erişimi ile kullanım hakkı ayrı değerlendirilir.
Bu yüzden önce toplama başlatılır; piyasa geçmişi
araştırması (Adım 8), Adım 6'da zamanlayıcının 2–3 gün gözlendiği bekleme
süresinde yapılır (karar, 28 Eylül 2026).

Eski canlı kontrol çıktıları veritabanına aktarılmaz (karar, 28 Eylül 2026):
`data/scraper_all.json` (27 Eylül, 304 sayfa) aynı gece düzeltilen hatalı
kodla toplandı. 304 sayfa 19 dakikada okunmuş (3 sn bekleme hatası; doğrusu
~35 dk), Hepsiburada'da stok alanı eksikken Tükendi verme hatası da o sırada
vardı; o günkü katalog 306 sayfaydı. Hangi kodla ve katalogla toplandığı
izlenemeyen tek bir anlık görüntünün ML'e katkısı ihmal edilebilir, yanlış veri
riski gerçektir. İlk gerçek veri Adım 5'teki canlı denemeyle girer; elle veri
eklenmez.

### FastAPI ve Streamlit

- FastAPI hazır ürün, geçmiş ve özetleri sunar; istek anında scraping veya
  tahmin çalışmaz. SlowAPI ile oran sınırlandırma.
- Streamlit telefon seçimini katalogdan beslenen açılır menüyle sunar; en ucuz
  teklif, platform, satıcı, puan ve son gözlem zamanı gösterilir.
- Son 30 günün dibi, tarihi zirve ve volatilite takip edilen geçmişten
  hesaplanır; 30 günlük veri yoksa rozet gösterilmez. Kritik stok uyarısı
  tahminden ayrı bir iş kuralıdır.

### ML

- Tek ortak LightGBM sınıflandırma modeli; ürün başına ayrı model yok.
- Hedef: tahmin anındaki takip edilen minimum fiyat P(t) ise, sonraki 7 günde
  gözlenen minimumlardan biri 0,95 × P(t) veya altındaysa 1.
- Başlangıç özellikleri: `product_id`, haftanın günü, ay, güncel fiyat / önceki
  30 günün ortalaması, son indirimden geçen gün.
- Kapsamı değişen pencereler eğitimde kullanılmaz; en az 30 günlük geçmiş veya
  doğrulanmış model yoksa olasılık gösterilmez. Zaman sıralı değerlendirme ve
  sabit referanstan iyi Brier skoru olmadan model yayımlanmaz.
- Akakçe/Cimri geçmişi Adım 8'de araştırıldı; uygun aktarım kaynağı
  seçilmedi. Kullanım hakkı veya alternatif kaynak netleşirse ayrı bir
  tabloda "piyasa minimumu" olarak tutulması planlanabilir; takip edilen
  tekliflerin minimumuymuş gibi etiketlenmez. ML'de kullanımı o zaman
  kararlaştırılır.

### İşletim

Docker Compose ile süreçler, veri ve model kalıcılığı; GitHub Actions ile CI
(bugün Black, Flake8, testler çalışıyor).

## 10. Çalışma ve Git disiplini

- Kullanıcı projeyi öğrenerek geliştiriyor: her değişiklikte amaç, akışa
  bağlantı, doğrulama ve sınırlar anlatılır; adım adım ilerlenir; plan veya
  açıklama isteği kod yazma isteğine dönüştürülmez.
- Otomatik testler kuralları kayıtlı yanıtlarla, canlı kontrol araçları bugünkü
  site uyumunu sınar; ikisi birbirine karıştırılmaz. "Testler geçti", "bütün
  pazaryeri tarandı" anlamına gelmez.
- Git'e yalnızca biten adımın dosyaları açıkça seçilerek eklenir; `git add .`
  kullanılmaz. Taslaklar, `data/` ve `artifacts/` çıktıları ve gizli ayarlar
  gönderilmez.
- Her plan adımı bitince tek commit atılır (karar, 28 Eylül 2026): testler ve
  biçim denetimleri geçer, dosya listesi ve Türkçe mesaj kullanıcıya gösterilir,
  onayıyla commit + push yapılır; her commit'te CI yeşil olmalıdır. Yazar
  yalnızca kullanıcıdır; commit mesajına ortak yazar satırı eklenmez.
- Black/Flake8 yerelde de CI'daki gibi `app tests` üzerinde çalıştırılır
  (taslaklar `_eski_taslaklar/` altında olduğu için mümkün).
