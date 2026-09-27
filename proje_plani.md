# Akıllı Telefon İndirim Takip ve Tahmin Sistemi — Proje Planı

Son güncelleme: 28 Eylül 2026.

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
| 6. Veritabanı ve zamanlanmış toplama | ⏳ Sıradaki; **karar bekliyor** | Bölüm 8 |
| 7. FastAPI ve Streamlit | 🔜 Planlandı, başlanmadı | Bölüm 9 |
| 8. ML (indirim tahmini) | 🔜 Planlandı, başlanmadı | Bölüm 9 |
| 9. Docker ve 7/24 işletim | 🔜 Planlandı, başlanmadı | Bölüm 9 |

Yereldeki `app/database`, `app/ml_model`, `app/api`, `app/services`,
`app/worker.py`, `frontend/`, Docker dosyaları ve Akakçe/Cimri taslakları
tamamlanmış iş değildir; kullanıcıyla değerlendirilmeden projeye bağlanmaz,
silinmez ve Git'e gönderilmez.

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
  okur. Scraper/discovery içinde SQL veya ML yapılmaz.
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
- Ürün adında söylemeyen bir yurt dışı sürümü ayırt edilemez.
- Siteler değişebilir; bakım gerekebilir. "Bir daha bakmaya gerek yok" garantisi
  verilmez.

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
- Test kapsamı: Trendyol Kritik Stok, CLI çıkış kodları, dry-run'ın katalog
  yazmaması, birçok uyarı türü ve HTTP yönlendirme/yeniden deneme yolları
  testsiz.
- Küçük ölü kod: etkisiz `except FetchError: raise` blokları, erişilmez satır,
  regex'lerde artık gereksiz `_`, tekrarlanan `_seller_rating` çağrıları.
- Hata kodları (`parse`, `identity`, `network`, `limit`, `http_error`…) teknik rehberde
  tablo olarak yok.

## 8. Açık kararlar

| Konu | Durum |
|---|---|
| Garanti türüne göre ayrım | **Karar verildi (27 Eylül 2026): ayrılmıyor;** yurt dışı sürümler ürün adından tanınıp kapsam dışı bırakılıyor. |
| Veritabanı teknolojisi, veri modeli, çalışma ortamı | Karar bekliyor; SQLite önceki öneri, kesin değil |
| Keşfin zamanlanması | Bu aşamada manuel; worker aşamasında değerlendirilecek. Kanıt: 28 Eylül kapanış taramasında tek günde 21 yeni bağlantı çıktı; Hepsiburada genel aramasının ilk 36 kartı her seferinde değişebildiği için tekrar eden keşif kapsamı artırır. |
| Gelecek aşama tanımları (`PricePoint`, `ProductSummary`, `MarketRecord`, `coverage_version`, zamanlama/ML ayarları, FastAPI/LightGBM/Streamlit bağımlılıkları) | Kaldırıldı (25 Eylül 2026). İlgili aşamada yeni tasarıma göre yeniden eklenecek; yerel taslaklar o zamana kadar çalışmaz. |

Kullanıcının veritabanı için belirttiği tercihler (**karar değil**, değerlendirmede
kullanılacak): her kontrolde yalnızca seçilen teklifin saklanması, günde 2
fiyat toplama, keşfin bu aşamada manuel kalması; çalışma ortamı henüz belli değil.

## 9. Sonraki aşamalar (planlandı, başlanmadı)

### Veritabanı ve zamanlanmış toplama

Başlamadan önce kullanıcıyla durum değerlendirmesi yapılır. Korunacak
gereksinimler: tekrar kayıt engelleme, koşu ve bağlantı düzeyinde
izlenebilirlik, fiyat gözlemi / Tükendi / toplama hatasının ayrı tutulması,
katalog kapsamı değiştiğinde sahte fiyat düşüşü oluşmaması. SQLite seçilirse
önceki öneri WAL, `busy_timeout=5000`, tek yazıcı ve salt okunur okuyuculardır.

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
- Akakçe/Cimri geçmişi araştırılacak; piyasa minimumu, takip edilen tekliflerin
  minimumuymuş gibi etiketlenmez.

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
- Git'e yalnızca biten aşamanın dosyaları açıkça seçilerek eklenir; `git add .`
  kullanılmaz. Taslaklar, `data/` ve `artifacts/` çıktıları ve gizli ayarlar
  gönderilmez. Commit, aşama bitince kullanıcı izniyle yapılır.
- Black/Flake8 yerelde değişen dosyalarda çalıştırılır; CI Git'teki dosyaları
  denetler.
