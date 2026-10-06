# Akıllı Telefon İndirim Takip ve Tahmin Sistemi — Proje Planı

Son güncelleme: 6 Ekim 2026.

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
| 6. Veritabanı ve zamanlanmış toplama | ⏳ Sürüyor: Adım 0–6, 8, 10 ve 11 tamamlandı (şema, katalog eşitleme, toplama turu, ilk tam tur 326/326 hatasız, zamanlayıcı gözlemi: 7 tur, tur 4–6 hatasız, tur 7'de 1 `network` hatası; tek piyasa geçmişi araştırması; haftalık keşif zamanlayıcısı; `002` migration: koruyucu kurallar ve karşılaştırılabilirlik görünümü; tur sonu `network` ikinci okuması). Görev Zamanlayıcı 28 Eylül'den beri çalışıyor. Kalan sıra (1 Ekim kararı; Adım 10 ve 4 5 Ekim'de, Adım 11 6 Ekim'de kapandı): **9 → 7**; Adım 9 ML eğitimi için Cimri geçmişinin bir defalık aktarımı (karar 30 Eylül), Adım 7 kapanış belgeleri | Bölüm 9 |
| 7. FastAPI ve Streamlit | 🔜 Planlandı, başlanmadı | Bölüm 9 |
| 8. ML (indirim tahmini) | 🔜 Planlandı, başlanmadı | Bölüm 9 |
| 9. Docker ve 7/24 işletim | 🔜 Planlandı, başlanmadı | Bölüm 9 |

**6 Ekim ikinci denetimi sonrası bakım (kullanıcı onayı):** Hepsiburada bozuk
satıcı yanıtı düzeltildi (552 test). İki SQL koruması `003_closed_run_guards.sql`
ile test edildi (571 test), kullanıcı 6 Ekim'de gerçek veritabanına uyguladı;
salt okunur denetimle doğrulandı. Üç bakım bulgusu kapandı; Aşama 6'nın kalan
sırası Adım 9 → 7 (Bölüm 7).

**6 Ekim ertelenmiş bakım planı (kullanıcı onayı):** yedi madde ayrı adımlarla
kontrol edilip gerekli düzeltmeler yapılacak; eksik kanıt için hedefli canlı
komutları kullanıcı çalıştıracak. İlk madde, HTTP indirme sınırı, tamamlandı
(598 test). İkinci maddenin kayıt ve hedefli canlı kontrolü yapıldı; bu örnekte
kimlik uyuşmazlığı yok, iki yapay riskin gerçek uyuşmazlık kanıtı bekleniyor.
Ham yanıt kaydı için manuel araç hazırlandı (611 test). Üçüncü madde,
Türkçe ekli aksesuarlar, kullanıcı onayıyla düzeltildi (652 test, 0 atlandı,
0 beklenen başarısızlık); kullanıcı commit/push işlemini onayladı. 4–7'ye geçilmedi.
Ayrıntı ve durumlar Bölüm 7'de.

Önceki aşamalardan kalan yerel taslaklar (eski `app/database`, `app/ml_model`,
`app/api`, `app/services`, `app/worker.py`, `frontend/`, Docker dosyaları ve
Akakçe/Cimri taslakları) 28 Eylül 2026'da `_eski_taslaklar/` klasörüne taşındı;
silinmedi, `.gitignore` ile Git dışında tutulur. Tamamlanmış iş değildir,
projeye bağlı değildir; yeni tasarımda yalnızca örnek olarak incelenebilir.

Güncel katalog (6 Ekim 2026): **59 ürün, 334 bağlantı** (Hepsiburada 217,
Trendyol 117; 2 bağlantı pasif: yurt dışı sürüm `trendyol_991304922` ve içeriği
S25+'ya dönen `hepsiburada_hbcv00007miemh`, aşağıda Bölüm 7; 28 Eylül'e göre +7
bağlantı, ilk haftalık keşif raporuyla eklendi, Bölüm 9 Adım 10). Keşif hedefleri 25: Apple 9, Samsung 8, Xiaomi 6, POCO 2
(X5 Pro satılmadığı için kapalı). Tam liste docs/teknik.md'deki "Yeni telefon ekleme"
bölümündedir.

## 3. Ürün kapsamı ve kimlik kuralları (uygulandı)

- Platformlar Trendyol ve Hepsiburada; kategori yalnızca yeni akıllı telefon.
  Başlangıç hedefi 20–30 modeldi; bugün 25 hedef tanımlıdır, 24'ünün ürünleri
  kataloğa alınmıştır (POCO X5 Pro satılmadığı için kapalı).
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
  etkilenen sayfalara `network` hatası yazılır ve veri uydurulmaz (tur 3, 28 Eylül:
  47/326 sayfa; bilgisayar bir telefonun hotspot'una bağlıydı ve bağlantı birkaç
  dakika koptu). Hata aynı tur içinde hemen yeniden denenmez; **6 Ekim'den beri
  (Adım 11) tur sonunda bu sayfalar bir kez yeniden okunur** (Bölüm 8). Kesinti tur
  bitene kadar sürerse ya da bilgisayar uyursa sayfalar hatalı kalır; ikinci okuma
  gerçek bir turda henüz görülmedi.
- Bilgisayar Wi-Fi ve telefon hotspot'u arasında değişen bağlantılarla çalışır
  (kullanıcı, 1 Ekim); `network` hataları bu yüzden tekrarlanabilir.
- Görev bilgisayarı uyandırmaz. Bilgisayar uyurken gelen tur kaçar ve açılışta bir
  kez telafi edilir (30 Eylül 22:00 turu kaçtı; bilgisayar 30 Eylül 17:57'den 1
  Ekim 09:20'ye kadar uykudaydı, telafi turu 1 Ekim 09:26'da çalıştı). Kaçan
  turun verisi geriye dönük toplanamaz; yalnız o saatin gözlemi kaybolur.
- Telafi turu bir sonraki tur saatine (10:00 ya da 22:00) sarkarsa o tetikleme
  Windows tarafından atılır (`IgnoreNew`): ayrı log, veritabanı satırı ve çıkış
  kodu bırakmaz, sonradan telafi edilmez (1 Ekim 10:00; Görev Zamanlayıcı geçmişi
  kapalı olduğu için atılma olayı doğrulanamadı). `LastTaskResult` o durumda
  çalışan turun sonucunu gösterir.
- Tur ortasında bilgisayar uyursa (1 Ekim 09:29, kritik pil, yaklaşık 6,5 dk)
  uyanma anındaki sayfalar `network` hatası alabilir (tur 7: 1 sayfa); veri
  uydurulmaz, tur tamamlanır (Adım 11'den beri tur sonunda bu sayfalar yeniden
  okunur).
- Uzun uykuda birden çok tur kaçar ve telafi yalnız tek turdur. Bilgisayar 2 Ekim
  17:58'den 4 Ekim 02:02'ye kadar uyudu: 2 Ekim 22:00, 3 Ekim 10:00 ve 22:00
  turları kaçtı, açılışta tek telafi turu çalıştı (tur 10, 4 Ekim 02:08). 4 Ekim
  22:00 turu da kaçtı (bilgisayar 20:49'dan 5 Ekim 09:16'ya kadar uykudaydı,
  telafi turu 09:26'da çalıştı, tur 12). Veritabanında 2 Ekim 10:30 ile 4 Ekim
  02:08 arasında yaklaşık 40 saatlik veri boşluğu var. Kaçan turun hiç satırı
  oluşmaz; boşluk yalnız tur başlangıç zamanlarından görülür. Telafi turunun
  tur saatine sarkması her zaman olmaz: 5 Ekim'de telafi turu 09:57'de bitti ve
  10:00 turu normal çalıştı.
- İnternet kesintisi tur veya keşfin başında da olabilir: tur 11'de (4 Ekim
  10:00) ilk 109 sayfa art arda DNS (`network`) hatası aldı, sonra bağlantı
  geldi (217 sayfa okundu; Adım 11'in tur sonu ikinci okuması bu 109 sayfayı
  kurtarırdı). Aynı gün 14:00'teki zamanlanmış keşifte Trendyol ve
  Hepsiburada'nın 21'er hedefi DNS hatası aldı; tarama 7 dk'da boş bitti (tam
  sonuç 3/48, yeni sayfa 0, 285 kayıt "görülmeyen", katalogda korunur). Keşifte
  ikinci geçiş yoktur; kesintiden sonra keşif elle yeniden çalıştırılır.
- Hepsiburada bir sayfanın içeriğini başka modele çevirebilir:
  `hepsiburada_hbcv00007miemh` (katalogda Galaxy S25 256 GB Lacivert; tur 2–11'de
  TEKNAT, 72.499 TL) tur 12 ve 13'te "Galaxy S25+ 256 GB" başlığıyla okundu;
  kullanıcının tarayıcısında da sayfa S25+ (görsel, renk fiyatları 69.999–77.799
  TL, "geçici olarak temin edilememektedir") görünüyordu, adres hâlâ
  `samsung-galaxy-s25-…` diyor. Kimlik kuralı sayfayı `identity` hatası yazdı, S25+
  fiyatı S25 geçmişine girmedi. Sayfa tur 12–15'te (4 tur) her turda 1 `identity`
  hatası verdi (tur çıkış kodu 2). **Karar (6 Ekim, kullanıcı): sayfa pasife alındı**
  (`config/catalog.json`'da `"active": false`; sonraki fiyat turunun katalog
  eşitlemesi veritabanında da pasif yapar, geçmiş silinmez). Hepsiburada sayfayı S25
  içeriğine geri çevirirse sayfa elle yeniden etkinleştirilebilir.
- Hepsiburada sayfası `hepsiburada_hbcv00004x9zcl` (iPhone 15 128 GB Yeşil; tur
  2–13'te hep Tükendi) tur 14'te (5 Ekim 22:00) `invalid_host` hatası verdi: adres
  veya yönlendirme hedefi platformun izinli alan adı dışında. **Tur 15'te (6 Ekim
  10:00) tekrarlamadı** (sayfa yine Tükendi) ve geçici sayıldı. Nedeni bilinmiyor
  (bir yönlendirme olabilir, doğrulanmadı): hata mesajı hedef alan adını
  yazmıyordu; 6 Ekim'den itibaren mesaj hedefin alan adını ve yolunu (sorgu metni
  hariç) yazar, böylece tekrarlarsa neden tur kaydından görülür. Veri uydurulmadı;
  ürün 1'in tur 14 ve 15 satırları karşılaştırılamaz sayıldı (hata, sonra hatadan
  çıkış).
- GitHub'ın bulut makineleri Trendyol'a erişemiyor görünüyor (ön bulgu, 6 Ekim): bulut
  denemesinde Trendyol sayfası HTTP 403 verdi, Hepsiburada sayfaları sorunsuz okundu
  (tek örnek; Bölüm 8, "Bulutta çalıştırma"). Bilgisayardaki turlarda Trendyol hiç
  engellenmedi. Sonuç, toplamanın GitHub'ın makinelerine taşınmasını şimdilik
  engeller; engel aşılmaz.
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
  29 Eylül araştırması sonunda veritabanına aktarım kaynağı seçilmedi.
  30 Eylül kullanıcı kararıyla Cimri'nin bir defalık aktarımı Adım 9 olarak
  planlandı; önceki kullanım koşulu bulgusu bu kararla doğrulanmış veya
  çözülmüş sayılmaz, aktarım adımında ele alınır.
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

Önceki maddeler güvenli tarafta hata veren veya nadir durumlardı. **6 Ekim
2026 ilk denetimi:** 13 maddenin hiçbiri düzeltilmemişti; kodla tek tek yeniden
okundu ve aşağıdaki gibi ayrıldı. Aynı gün yapılan ikinci denetim, aşağıda
ayrıca belirtilen bir yanlış stok ihtimalini ve iki SQL koruma açığını doğruladı.

İkinci denetimde doğrulandı (6 Ekim, Codex):
- Hepsiburada `_response_listings`, sözlük olmayan satıcı kayıtlarını sessizce
  atlıyor. Örneğin `[null]` veya `["bozuk kayıt"]` yanıtı boş listeye dönüşüp
  `Tükendi` üretiyor; kaynak açık stok sinyali vermediği için bu ayrıştırma hatası
  olmalı. Gerçek HTTP isteği olmadan sahte yanıtlarla yeniden üretildi; canlıda
  böyle bir yanıt görüldüğüne dair kanıt yok. **Düzeltildi (6 Ekim, kullanıcı
  onayıyla):** liste ve bütün kayıtlar doğrulanıyor; sözlük olmayan tek kayıt bile
  varsa `parse` hatası veriliyor. Gerçekten boş liste ve açık stok sinyalleri
  mevcut kurallarla işleniyor. Yedi regresyon testi eski kodda başarısız oldu;
  düzeltmeden sonra tüm kontroller `551 passed, 1 xfailed`, 0 atlandı, Black ve
  Flake8 temiz (toplam 552; 200 PostgreSQL testi). Kimlik kuralı değişmedi.
- `002` içindeki `guard_listing_checks_update`, `OLD.outcome IS NULL` dalında
  tur durumunu denetlemiyor. Kapanmış turun sonuçsuz satırı doğrudan SQL ile
  doldurulabiliyor. Üretimdeki `record_result` bunu reddediyor; eksik olan
  veritabanının kendi koruması. `_test` veritabanında geçici şemada doğrulandı.
- `guard_collection_runs_update`, biten turun `status = 'running',
  finished_at = NULL` ile yeniden açılmasını reddetmiyor. Böylece eski `network`
  sonucu, tetikleyici kapatılmadan `rewrite_network_result` ile değiştirilebiliyor.
  Normal tur kodu bu geçişi yapmıyor; doğrudan SQL'e karşı koruma eksik.
  `_test` veritabanında geçici şemada doğrulandı. İki SQL açığı da uygulanmış
  `002` değiştirilmeden, yeni numaralı migration ile ele alınmalı.
- Denetim kanıtı: mevcut testler `544 passed, 1 xfailed`, sıfır atlandı; Black
  ve Flake8 temiz. Git dışındaki `.scratch/test_audit_invariants.py` sekiz ek
  sınama içerir: yukarıdaki açıkların altı varyantı başarısız, iki kontrol örneği
  geçti; test işlemleri sonunda geri alındı. Ölü üretim kodu doğrulanmadı.
  Gerçek veritabanı yalnız okundu: 15 tur `completed`, planlanan sayfa sayıları
  tutarlı, sonuçsuz tamamlanmış satır ve kapanış sonrası gözlem yok;
  `product_run_prices` görünümündeki 827 satır bağımsız Python hesabıyla eşleşti.

**Düzeltme kararı (6 Ekim, kullanıcı):** önce Hepsiburada bozuk satıcı yanıtı
(yukarıda tamamlandı), ardından iki SQL koruma açığı; sonra Adım 9 ve Adım 7'ye
dönülecek. **SQL düzeltmesi tamamlandı ve uygulandı (6 Ekim):**
Önce ayrı proje kopyasında geliştirilen `003_closed_run_guards.sql`, iki mevcut
tetikleyici işlevini yeniler. İlk sonuç ve `network` yeniden yazımı yalnız
`running` turda kabul edilir; tur satırı işlem sonuna kadar `FOR SHARE` ile
kilitlenir, böylece aynı anda kapanış ile sonuç yazımı yarışamaz. Kapanmış turun
durumu ve bitiş zamanı değişmez; notu güncellenebilir. `001` ve `002` baytları
değişmedi; yeni migration veri satırlarını, görünümü veya tetikleyicileri
yeniden kurmaz. **Kanıt:** 19 yeni PostgreSQL testi; açıkları ve eşzamanlı yazımı
sınayan 16 test eski SQL'de başarısızdı. Kopyada tüm kontroller `570 passed,
1 xfailed`, 0 atlandı (571 toplam, 219 PostgreSQL); Black ve Flake8 temiz.
`002` uygulanmış ve kayıtları olan veritabanından `003`'e geçişte tur/sayfa
satırları, görünüm sonuçları ve tetikleyici kimlikleri aynı kaldı; ikinci
`migrate` değişiklik yapmadı. **Canlı uygulama (6 Ekim 13:30 TR):** kullanıcı
dosyayı gerçek klasöre alıp tur saatleri dışında `migrate` çalıştırdı;
`status` üç uygulanmış migration ve "Şema güncel" gösterdi. Sonraki salt okunur
denetimde bütün migration parmak izleri ve iki işlevin SQL içeriği dosyayla
eşleşti; 15 tetikleyici açık, 15 tur tamamlanmış, sonuç sayıları aynı
(3.207 fiyat, 1.213 Tükendi, 162 hata). Görünümün 827 satırı bağımsız Python
hesabıyla uyuştu; plan sayısı uyuşmazlığı, tamamlanmış sonuçsuz satır veya
kapanış sonrası gözlem yok. Gerçek veritabanına denetim amacıyla yazılmadı.
**003 de artık uygulanmış dosyadır, değiştirilemez.** Keşif → katalog → toplama → veritabanı akışı,
tur saatleri ve scraper sözleşmesi aynı kalır. Bozuk yanıt `parse` olarak yazılır,
tur diğer sayfalara devam eder; bu sayfa o turda cevap veren kümeye katılmaz.

Düzeltildi (6 Ekim, kod ve test):
- Trendyol keşfinde `filter_unavailable` aynı aramada iki kez yazılıyordu (filtre
  isteği hata verince ayrıca "kategori bulunamadı" da yazılıyordu); artık hata
  kodlu ilk uyarı kalır.
- Tarama sonrası katalog/rapor yazma hatası "keşif başlatılamadı" diye
  görünüyordu; artık "Tarama bitti ama sonuç yazılamadı" der (çıkış kodu yine 1).
- Ek: `invalid_host` hata mesajı hedef alan adını yazar (Bölüm 7, tur 14 vakası);
  `live_scraper_check.py` kilit meşgulken diğer araçlar gibi 3 döner.
- HTTP: 8 MB sınırı artık indirme sırasında uygulanır (`content_callback`);
  aşan parça biriktirilmeden aktarım durur. Tam eşik kabul edilir; başarılı
  HTTP yanıtındaki taşma `too_large` kalır. Büyük engel/hata yanıtlarında HTTP
  sınıflandırması, yönlendirme, 5xx tekrarı ve istek bütçesi korunur. Her
  denemede boş tampon açılır; yeni bağımlılık, migration veya kimlik kuralı yok.
  **Kanıt:** 27 yeni HTTP testi (88 HTTP, 598 toplam); yeni sınamaların ilk
  21'inden 20'si eski kodda başarısızdı. Tüm testler `597 passed, 1 xfailed`,
  0 atlandı (219 PostgreSQL); Black ve Flake8 temiz. Kurulu curl_cffi'nin gerçek C callback'inde
  eşik/taşma durdurma sinyali ayrıca ağsız doğrulandı. Canlı okuma yapılmadı.

Bilerek kapatıldı, kod değişmedi (gerekçeyle):
- Tek bir satıcının bozuk fiyatı bütün sayfayı `parse` hatası yapar: teklifi
  atlamak, bozuk teklif en ucuzsa daha pahalı bir "en ucuz" yazdırır; sayfa cevap
  sayıldığı için `product_run_prices` bu sahte yükselişi karşılaştırılabilir
  görürdü. Hata vermek güvenli taraftır; canlıda hiç görülmedi.
- Hepsiburada fiyat isteğine konan yedek değerler yanıtla karşılaştırılmıyor:
  yanıttaki fiyatın satıcı listesindekinden farklı olması normaldir (API'nin işi
  bu); kaba bir karşılaştırma sahte hata üretirdi.
- HTTP 204/304: 204 sonradan zaten `parse` olur; 304 için koşullu istek başlığı hiç
  gönderilmediğinden gelmez. POST yönlendirmede tekrar gönderme: tek POST kullanıcısı
  Hepsiburada fiyat API'sidir, 307/308'de bu doğrudur; 303'te tarayıcılar GET'e
  çevirir, bu kod çevirmez ama 303 hiç görülmedi.
- Tekrarlardan sonra 5xx `network` diye raporlanıyor: **karar (6 Ekim, kullanıcı)
  böyle kalır.** 5xx geçicidir ve Adım 11'in ikinci geçişi yalnız `network`'ü
  yeniden okuyacağı için 5xx'i de kapsar; ayrı kod 003 migration da gerektirirdi.
- Hiç aday bulamayan Trendyol araması uyarısız "tam" sayılıyor: kullanıcı yapılmamasını
  seçti; gerçekten satılmayan bir model her hafta "kısmi" görünürdü.
- Rapor yolu elle çalıştırmada sabit (`data/discovery_report.json`): bilinçli;
  zamanlanmış çalışma tarihli dosya yazar (Adım 10), elle çalıştırma tek dosyadır.

Açık kalanlar:
- Keşif: Trendyol varyant adresi `-p-<id>` biçimi için denetlenmiyor (kimlik sayfada
  doğrulanıyor; kayıtta kimlik yoksa scraper her turda `identity` verir, yani güvenli
  tarafta); Hepsiburada canonical SKU'su alt dizeyle karşılaştırılıyor (tam eşitlik
  olmalı). İkisi de kimlik kuralına dokunur: canlı örnek görülünce değiştirilir.
- Tur tamamlandıktan sonra özet sorgusu (`run_summary`) düşerse çıkış kodu 1 olur ama
  tur `completed` kalır (nadir; docs/teknik.md'de yazılı).

Yeni (6 Ekim denetimi; henüz uygulanmadı, bazı birleştirmeler davranışı değiştirir):
- Aynı adres-kimliği düzenli ifadesi beş yerde yazılı (`discovery/service.py`
  `_url_identity`, iki scraper, iki keşif modülü); `trendyol_scraper.py` sondaki
  `(?:[/?]|$)` kısmını atlıyor, yani anlamca hafif farklı. `_url_identity` platform
  adlarını koda gömüyor ("yeni site için mevcut koda koşul eklenmez" ilkesine ters).
- İki eklenti yükleyicisi (`scraper/factory.py`, `discovery/service.py` `_adapter`)
  aynı yapıda.
- `discovery/hepsiburada.py` `_variants` sayfadaki **son** boş olmayan varyant
  listesini alıyor; `hepsiburada_scraper.py` `variant_capacity` SKU'yu bulduğu
  **ilk** listede duruyor. Sayfada birden çok varyant listesi olursa ikisi farklı
  listeye bakabilir (canlıda görülmedi).
- Adres ve varyant yardımcılarını birleştirmek kimlik kuralına dokunduğu için
  canlı örnek ve regresyon testi ister. Eklenti yükleyicileri farklı sözleşmeler
  taşır: scraper nesne kurar ve hatayı `plugin` yapar; keşif sınıf döndürür ve
  yükleme hatası komutu durdurur. Yalnız kod benzerliği hata kanıtı değildir.

**6 Ekim ertelenmiş bakım kontrolü (kullanıcı isteği, Codex):** yedi bakım
grubu kod ve kayıtlı raporlarla incelendi; Git dışındaki yerel denetimde
14 sınama geçti (gerçek HTTP kesildi, veritabanı sınaması yalnız `_test`).
Sınamalar mevcut davranışı doğrular, risklerin düzeltildiği anlamına gelmez.
Üç keşif raporundaki 357 adayın adres kimliği beklenenle eşleşti; ekli aksesuar
adlarını içeren 16 uyarıda sayfalar reddedilmişti. Yapay sayfalarda Trendyol
kimliksiz adresi, Hepsiburada farklı SKU içeren canonical adresi ve ilk listenin
kapasitesiyle son listenin renginin birlikte kullanılması üretildi; canlı örnek
kanıtı bulunmadı. Özet sorgusu hata verdiğinde tamamlanmış tur, yedi sonuç ve
kilidin bırakılması korundu. HTTP sınırının indirme sonrası uygulandığı hem
koddan hem sahte istemciden doğrulandı. **Kullanıcı yedi maddelik kontrol ve
gerekli düzeltme planını onayladı; ilk madde (HTTP sınırı) aynı gün tamamlandı.**
Adres ve çoklu varyant riskleri için gerçek kaynak kanıtı gerekir; bu maddeler
henüz değiştirilmedi. Türkçe ekli aksesuarlar sonraki bakım 3'te düzeltildi.

**6 Ekim bakım 2, adres kimliği kontrolü:** `data/` altındaki 58 JSON dosyası
incelendi. Bunların 50'si keşif raporu içeriyor; 951 aday kaydındaki 333 farklı
adres (116 Trendyol, 217 Hepsiburada) ve katalogdaki 334 sayfanın adres kimliği
beklenenle eşleşti. Bu kayıtlar Trendyol varyant yanıtındaki `pageUrl` veya
Hepsiburada canonical alanını saklamıyor; kabul edilmiş aday adresleri iki
riskin kaynakta hiç oluşmadığını kanıtlamaz. Önceki iki yapay sınama yeniden
çalıştırıldı; kimliksiz Trendyol adresi ve beklenen SKU'yu alt dize olarak
içeren farklı Hepsiburada canonical adresi hâlâ kabul ediliyor. Canlı hata
kanıtı yok, kimlik kuralları değiştirilmedi; madde **kanıt bekliyor**.

Eksik kanıtı almak için `tests/manual/live_discovery_check.py` aracına
`--save-responses KLASOR` eklendi: tek hedef zorunlu, yeni klasör açılır,
başarılı HTTP yanıtlarının özgün HTML/JSON baytları platforma göre saklanır.
Her `index.json` istenen adresi, zamanı, dosyayı veya okuma hata kodunu ve gerçek
istek sayısını kaydeder. Hata yanıtının gövdesi saklanmaz; yönlendirme sonrası
adres HTTP katmanından çıkmadığı için index'teki adres ilk istenen adrestir.
Rapor aynı klasörde `report.json` olur; standart raporun üzerine yazılmaz.
Yeni istek gönderilmez; ortak HTTP sınırları, bütçe, kilit ve dry-run korunur.
Ham dosyalar `data/` altında Git dışındadır. Araç için 12 ağsız test eklendi;
tam çalışmada `609 passed, 1 xfailed`, 0 atlandı (219 PostgreSQL). Black
43 dosyada ve Flake8 temiz. Canlı komut kullanıcı tarafından tur saatleri
dışında çalıştırıldı (aşağıdaki sonuç). Bu hazırlık, adres
kimliği düzeltmesinin tamamlandığı anlamına gelmez.

**6 Ekim 16:24–16:26 hedefli canlı kontrol (kullanıcı çalıştırdı):** iPhone 15,
Trendyol 13 ve Hepsiburada 20 gerçek istek. Çıkış kodu **2** yalnız bilinen
Hepsiburada arama API'sinin HTTP 403 engelinden (`search_api: blocked`) geliyor;
başka uyarı veya reddedilen aday yok. Trendyol tam sonuç, 5 aday; Hepsiburada
kısmi sonuç, 16 aday; yeni ürün/sayfa yok, katalog/veritabanı yazılmadı.
Ham yanıtlar `data/kimlik_iphone15_20261006/`, karar izi aynı adlı `_iz.json`
dosyasında; salt okunur inceleme özeti `identity_analysis.json` olarak kaydedildi.

- Trendyol: ham varyant API'sindeki 5 farklı `id/pageUrl` çifti, istenen
  adreslerin kimliği ve açılan sayfalardaki `product.id` birebir eşleşti.
  Eksik veya farklı kimlikli varyant adresi görülmedi.
- Hepsiburada: 16 ürünün istenen SKU'su, tam ürün bağlamındaki SKU ve JSON-LD
  SKU'su eşleşti. Canonical adreslerin **9'u `-pm-` grup adresi, 7'si model/kategori
  adresi**; hiçbiri ürün SKU adresi değil. Mevcut kod bu adresleri kullanmadı,
  16 doğrulanmış mevcut ürün adresini korudu. Beklenen SKU'yu alt dize olarak
  içeren farklı SKU canonical örneği görülmedi.

**Sonuç:** bu gerçek örneğin kontrolü tamamlandı; kimlik kuralları değişmedi.
Yapay örnekte doğrulanan iki risk düzeltildi sayılmaz; gerçek uyuşmazlık
örneği için durum **kanıt bekliyor** olarak kalır. Aynı hedefi yeniden
çalıştırmak gerekmiyor; sonraki bakım 3'e ayrı devam talebiyle geçilir.
Kullanıcı, sonraki bakım maddesine geçmeden ham kayıt aracı, testleri ve
kontrol notlarının ayrı commit/push işlemini onayladı.

**Bakım 2'nin Git/CI doğrulaması:** araç ve kontrol notları `feee4bd` ile
commit/push edildi. İlk CI'da Black ve Flake8 geçti; pytest'te yeni ham kayıt
testi başarısız oldu (`608 passed, 1 failed, 1 xfailed`). Kullanıcının paylaştığı
günlük, Linux'ta dosyaların Windows'takinden farklı sırayla listelenmesini
doğruladı. Test gereksiz yere sabit sıra istiyordu; dosya kümesi karşılaştırması
ile düzeltildi, normal/ters sıra aynı testte ayrı ayrı sınanıyor (13 araç
testi, toplam 611). Ters sıra eski kontrolde yerelde de başarısızdı. Araç ve
kimlik kuralları değişmedi; düzeltme bu commit/push talebinin CI doğrulaması
kapsamındadır. Düzeltme sonrası tam çalışma `610 passed, 1 xfailed`, 0 atlandı
(219 PostgreSQL), 45,91 sn; Black 43 dosyada ve Flake8 temiz. Sonraki bakım
maddesine geçilmedi.

**6 Ekim bakım 3, Türkçe ekli aksesuarlar (kullanıcı onayıyla düzeltildi):**
Ortak başlık kuralına yalnız `kilifi`, `adaptoru`, `kapagi`; keşfin kategori
süzgecine `kapagi`, `adaptoru` eklendi. "Kılıfı" kategorisi mevcut kuralla zaten
reddediliyordu. Genel Türkçe ek tahmini yapılmadı; keşif ve scraper aynı
model/kapasite kimlik kuralını kullanır, ret kodu `identity` olarak kalır.

Gerçek sözcük kanıtları kayıtlı izlerde: `trace_s25.json`
`/traces/1/trace/28` Hepsiburada `HBCV00007I6EKM` ("Hızlı Sarj Adaptörü");
`trace_xiaomi_poco_x6_pro.json` `/traces/0/trace/576` Trendyol `4894840`
("Moto G Arka Kapak Batarya Pil Kapağı Mavi");
`trace_xiaomi_redmi_note_14_pro_4g.json` `/traces/1/trace/13` Hepsiburada
`HBCV0000FS4I6K` ("Telefon Kılıfı"). Bu gerçek örnekler başka korumalardan
reddedilmişti; canlıda yanlış fiyat kaydı kanıtlanmadı. Tek başına ekli sözcük
taşıyan doğru model/kapasite başlıkları ve "Cep Telefonu Kapağı/Adaptörü"
kategorileri yapay regresyon örnekleridir; gerçek kategori hatası diye sunulmaz.

Seçili 42 sınama eski kodda **20 başarısız, 22 başarılı** idi. Düzeltme sonrası
tam paket **652 passed**, 0 atlandı, 0 `xfail` (219 PostgreSQL), 43,79 sn;
Black 43 dosyada, Flake8 temiz. Önceki "Kapağı" `xfail` testi normal teste
çevrildi; toplam 41 ek sınama var. Kullanıcının iPhone 15 ham yanıtlarındaki
21 geçerli sayfanın özgün adları ve kapasite verisi
`tests/fixtures/discovery/phone_identity_examples.json` içine alındı;
kalıcı testler ham `data/` dosyalarına veya internete bağımlı değil.
Katalog, gerçek veritabanı ve migration dosyaları değişmedi. Kod/test/belge
hazır; kullanıcı commit/push işlemini onayladı. Bakım 4'e geçilmedi.

Onaylanan bakım sırası ve durum (her adımdan sonra sonuç anlatılıp durulur):

| Bakım maddesi | Durum |
|---|---|
| 1. HTTP 8 MB indirme sınırı | ✅ Kod ve test tamamlandı; kullanıcı commit/push işlemini onayladı. Gerçek turda henüz görülmedi. |
| 2. Trendyol varyant / Hepsiburada canonical adresi | ⏳ Gerçek uyuşmazlık kanıtı bekliyor. Kayıt kontrolü ve 6 Ekim hedefli canlı kontrol tamamlandı: TY 5 varyant/adres/sayfa kimliği eşleşti; HB 16 SKU eşleşti, 9 grup/7 kategori canonical adresi kullanılmayıp mevcut adresler korundu. İki yapay risk canlıda görülmedi; kimlik kuralları değişmedi. Ham kayıt aracı ve 13 ağsız test hazır; ilk CI'daki dosya sırası testi düzeltildi. |
| 3. Türkçe ekli aksesuar adları | ✅ Düzeltildi: üç kayıtlı yazım için dar başlık/kategori kuralı; model, başlık/yapısal kapasite ve birden çok ad sınandı, 21 kayıtlı telefonun kabulü korundu. 652 test geçti, atlanan/xfail yok. Kullanıcı commit/push işlemini onayladı. |
| 4. Hepsiburada çoklu varyant listesi | 🔜 Aynı SKU için kaynakların kapasite/renk tutarlılığı; gerçek örnek doğrulanırsa ortak veri ve çelişkide ret. |
| 5. Beş adres kimliği kuralı | 🔜 Aynı adreslerle davranış karşılaştırması; ortaklaştırma yalnız gerekli düzeltmeyi destekliyorsa. |
| 6. Tur sonu özet sorgusu | 🔜 Özet/bağlantı/kapanış sonrası kesinti; tur, sonuç, kilit, çıkış kodu kontrolü. Güvenli mevcut davranış kod değişmeden belgelenebilir. |
| 7. İki eklenti yükleyicisi | 🔜 Geçerli/eksik/yanlış/soyut/kurulamayan adaptör kontrolü; farklı sözleşmeler korunur, yalnız benzerlik için birleştirilmez. |

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
| Keşfin zamanlanması | **Karar verildi (28 Eylül 2026):** bu aşamada manuel, haftada bir; fiyat turuyla ortak kilit. Otomasyon, veritabanı birkaç hafta sorunsuz çalıştıktan sonra değerlendirilir. Kanıt: 28 Eylül kapanış taramasında tek günde 21 yeni bağlantı çıktı; Hepsiburada genel aramasının ilk 36 kartı her seferinde değişebildiği için tekrar eden keşif kapsamı artırır. **29 Eylül güncellemesi (kullanıcıyla):** haftalık zamanlayıcı değerlendirildi; şimdilik elle devam, **Adım 6 gözlemi bitince (1 Ekim sonrası) otomatikleştirilecek**. Biçim o gün seçilecek: (A) önerilen, görev keşfi deneme modunda çalıştırır ve tarihli rapor bırakır, yeni sayfaları kullanıcı inceleyip tek komutla ekler; 2–3 hafta rapor temiz giderse (B)'ye geçiş değerlendirilir. (B) tam otomatik: yeni sayfalar doğrudan kataloğa girer. B'nin riski: yanlış bir sayfa kataloğa girerse tur onu birkaç saat içinde veritabanına ekler, fiyatları ürünün geçmişine yazılır ve sayfa sonradan yalnız pasife alınabilir; ayrıca `catalog.json` Git'te olduğu için her hafta commit edilmemiş değişiklik birikir. Teknik gereksinimler: keşfe `--scheduled` (log + tarihli rapor + özet satırı; bugün rapor her çalışmada üzerine yazılır); görev tur saatlerinden uzak olmalı (ör. Pazar 14:00, keşif ~50 dk tahmin edilmişti, 5 Ekim'de 34 dk ölçüldü); keşif görevinde kaçan çalışmayı telafi **kapalı** olmalı, yoksa geç açılan bilgisayarda telafi keşfi 22:00 turunu kilitle atlatabilir; keşif çıkış kodu Hepsiburada yüzünden hep 2'dir, özet satırı ayrıca okunmalı. **Karar verildi (1 Ekim 2026, kullanıcı): A seçildi, ekleme komutuyla (A1).** Görev her Pazar 14:00'te keşfi deneme modunda çalıştırır ve tarihli log + rapor + özet satırı bırakır; kaçan çalışmayı telafi etmez. Kullanıcı raporu inceler; yeni bir komut (`--apply-report`) siteye gitmeden **tam olarak incelenen** raporu kataloğa uygular. Gerekçe: bugün yazmanın tek yolu keşfi yeniden çalıştırmaktır ve Hepsiburada'nın ilk 36 kartı değişebildiği için ikinci tarama incelenenden farklı sonuç verebilir. Rapor 2–3 hafta temiz giderse (B)'ye geçiş yeniden değerlendirilir. Uygulama Adım 10'dur ve 5 Ekim'de tamamlandı (Bölüm 9): ilk zamanlanmış çalışma (4 Ekim) internet kesintisi yüzünden boş bitti, elle yapılan tam tarama ve `--apply-report` 5 Ekim'de 7 sayfa ekledi. |
| Piyasa geçmişi kaynağı | **29 Eylül araştırma sonucu:** Cimri üç üründe teknik olarak doğrulandı; Akakçe'nin ilk örneği 403 verdi. O tarihte aktarım kaynağı seçilmedi. **Güncel karar (30 Eylül 2026, kullanıcı; Codex):** ML eğitimi için geçmiş fiyat hareketinin kaynağı Cimri olacak; katalogdaki telefonların mevcut geçmişi bir defa alınacak. Akakçe ve Cimri serileri birleştirilmeyecek, düzenli Cimri toplaması yapılmayacak. Kullanım koşullarına ilişkin önceki bulgu Bölüm 7'de korunur ve aktarım adımında ele alınır. |
| Cimri geçmişinin bir defalık kaydı ve ML amacı | **Karar verildi (30 Eylül 2026, kullanıcı; Codex):** Aşama 6'ya **Adım 9** eklenir; Adım 4'ten sonra, Adım 7 kapanışından önce yapılır. Veriler aynı PostgreSQL veritabanında ayrı `market_history` tablosunda saklanır. Amaç, erişilebilen bir yıllık geçmiş fiyat hareketini model eğitiminde kullanmaktır. **Gerekçe:** Cimri daha geniş kaynak kapsamına sahip olsa da kullanıcı küçük fiyat farklarını bu amaç için kabul ediyor; öncelik geçmişteki değişimdir. Cimri serisi kendi Hepsiburada/Trendyol gözlemlerimizle aynı ölçüm olarak etiketlenmez. Eğitimin nasıl yapılacağı, mutlak fiyatın mı değişimin mi kullanılacağı ve değerlendirme ayrıntıları ML aşamasında kararlaştırılır. Üç örneğin tam serisi hâlen yerel araştırma raporlarında; toplu alım, tablo ve aktarım henüz uygulanmadı. |
| Tur sonunda yalnız `network` hatası alan sayfalara ikinci geçiş | **Karar verildi (1 Ekim 2026, kullanıcı): yapılacak, tek geçiş. Uygulandı (6 Ekim 2026, Adım 11).** Tasarım kararları (6 Ekim, kullanıcı): ikinci okuma da `network` verirse ilk satır olduğu gibi kalır; ardışık 5 sayfa yine `network` verirse geçiş durur (bağlantı hâlâ yok); tur notuna yalnız sayılar yazılır, sayfa kimlikleri logdadır; 5xx ayrı kod almaz ve `network` olarak yeniden okunur. Kanıt: tur 3'te (28 Eylül) 47 sayfa bağlantı kesintisiyle `network` hatası aldı; son hatadan sonra kalan 154 sayfa cevap verdi, yani tur bitmeden bağlantı geri gelmişti. Tur 7'de (1 Ekim) 1 sayfa uyku sonrası DNS hatası aldı. Yalnız `network` yeniden okunur; `blocked` yeniden denenmez. İkinci okuma, hata satırının üzerine yazılır (tur × sayfa başına tek satır kuralı korunur); tur notu ve log kaç sayfanın düzeldiğini söyler. Yeniden okunamayan sayfa hata olarak kalır. |
| Bulutta çalıştırma (PC açık kalmak zorunda olmasın) | **Deneme kararı (6 Ekim 2026, kullanıcı):** Görev Zamanlayıcı aynen çalışmaya devam eder; bu sürede GitHub Actions'tan canlı okuma denenir (`.github/workflows/bulut-deneme.yml`: elle tetiklenir, zamanlama yok, veritabanı ve gizli anahtar yok; Samsung Galaxy A55 128 GB'ın 4 sayfası, Trendyol ve Hepsiburada). **Gerekçe:** PC uyuyunca veya kapalıyken turlar kaçıyor (2–4 Ekim: 4 tur, ~40 saat boşluk; geri alınamaz). Kod taşınabilir (`filelock`, `psycopg`, standart PostgreSQL; `app/` içinde Windows'a bağlı kod yok, yalnız `scripts/*.ps1` kurulum betikleri ve Görev Zamanlayıcı). **Bilinmeyenler (deneme öncesi; (1) aşağıdaki sonuçla yanıtlandı):** (1) Trendyol ve Hepsiburada GitHub'ın bulut adreslerini engelliyor mu (Hepsiburada ev adresimizde bile arama API'sinde 403 veriyor); (2) veritabanı nerede duracak (GitHub'daki bir iş veritabanı tutamaz: kendi sunucumuz mu, yönetilen hizmet mi; yeni mimari karar, verilmedi); (3) maliyet ve bakım (GitHub Actions limitleri teyit edilmedi). **Sonuç (6 Ekim 2026 09:41, çalışma 37425171004, 42 sn):** Hepsiburada'nın 3 sayfası buluttan okundu ve bilgisayarın son üç turuyla birebir aynı çıktı (36.999 TL, 39.999 TL, 1 Tükendi); Trendyol'un 1 sayfası **HTTP 403** (`blocked`) verdi. Aynı kodla bilgisayarda son turda 116 Trendyol sayfasının hiçbiri engellenmedi ve bugüne kadar hiçbir turda `blocked` yok; fark kodda değil çıkış adresinde görünüyor. Ancak bulutta tek örnek var (tekrar denemesi ucuz: 1 Trendyol isteği). **İlke:** 403 `blocked` sayılır ve engel aşılmaz (proxy, adres döndürme, tarayıcı taklidi yapılmaz; Akakçe kararıyla aynı). **Durum:** GitHub'ın makineleriyle tam toplama şimdilik uygun görünmüyor (Trendyol 117 sayfa). Seçenekler (sunucu denemesi, evde 7/24 açık küçük cihaz, bilgisayarı tur için uyandırma) kullanıcıyla değerlendirilecek; karar verilmedi. |
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
| Keşif | Haftada bir. Bu satırın ilk hâli (28 Eylül) "kullanıcı elle çalıştırır" diyordu; **1 Ekim kararıyla (Bölüm 8, A1) görev her Pazar 14:00'te keşfi deneme modunda kendiliğinden çalıştırır ve raporu kullanıcı inceleyip `--apply-report` ile uygular** (Adım 10). Fiyat turu ile keşif **ortak kilit** paylaşır, aynı anda çalışmaz (3 sn bekleme süreç içinde tutulduğundan iki süreç siteye iki kat hızla gider). |
| Veritabanı | **PostgreSQL 17**, Windows servisi. Gerekçe: kısmi benzersizlik ve CHECK kısıtlarıyla kuralların veritabanında garanti edilmesi, `timestamptz`, transaction içinde migration, kullanıcının önceki deneyimi. |
| Erişim | **`psycopg` 3 + ham SQL + numaralı migration dosyaları**; ORM yok. Veri şekilleri Pydantic sözleşmelerinde kalır. |
| Sonuç tablosu | Tek tablo `listing_checks`: her tur × planlanan sayfa bir satır; `outcome` fiyat / Tükendi / hata. CHECK kısıtları hatanın fiyat veya Tükendi olarak yazılmasını engeller. |
| Sahte fiyat düşüşü | İki tur ancak **cevap veren sayfa kümesi** (fiyat veya Tükendi dönen sayfalar) aynıysa karşılaştırılır. Hata cevap değildir; Tükendi gerçek cevaptır. |
| Bağlantı ve yetki | Şifresiz `DATABASE_URL` / `TEST_DATABASE_URL`; şifre PostgreSQL'in `pgpass.conf` dosyasında, repoda değil. Proje kullanıcısı `fiyat_takip` yönetici değildir; yalnızca kendi iki veritabanının sahibidir. |

Adımlar (her biri ayrı commit). Uygulama sırası 28 Eylül'de **3 → 5 → 6 → 4**
olarak değiştirildi: canlı deneme ve zamanlayıcı öne alındı ki gerçek veri
erken birikmeye başlasın; görünüm (4) veri toplanırken yazılır ve gerçek
veriyle de denenir. **30 Eylül kullanıcı kararı:** Cimri'nin bir defalık geçmiş
aktarımı yeni **Adım 9** olarak eklenir; kalan sıra **6 → 4 → 9 → 7** olur.
Adım 8 tamamlanmış araştırmadır; Adım 9 henüz uygulanmamış aktarım işidir.
**1 Ekim kullanıcı kararı:** Adım 6 kapandı; haftalık keşif zamanlayıcısı
(**Adım 10**, ilk zamanlanmış keşif Pazar 4 Ekim'den önce) ve tur sonu `network`
ikinci geçişi (**Adım 11**) eklendi. Kalan sıra **10 → 4 → 11 → 9 → 7**.
**5 Ekim:** Adım 10 ve Adım 4 kapandı; geriye **11 → 9 → 7** kaldı.
**6 Ekim:** Adım 11 kapandı; geriye **9 → 7** kaldı.

**6 Ekim ikinci denetimi sonrası kullanıcı kararı:** Adım 9'dan önce üç bakım
bulgusu düzeltilecek. Hepsiburada bozuk satıcı yanıtı düzeltmesi tamamlandı;
iki SQL koruması `003` ile ayrı kopyada geliştirilip test edildi, gerçek
veritabanına 6 Ekim 13:30'da kullanıcı tarafından uygulandı ve salt okunur doğrulandı.
Üç bakım işi tamamlandı; sıradaki plan adımı 9 (Bölüm 7).
Kullanıcı 22:00 turunu beklerken ertelenmiş bakımların incelenmesini istedi;
inceleme sonrası yedi maddelik kontrol ve gerekli düzeltme planını onayladı.
İlk madde (HTTP indirme sınırı) kod ve testle tamamlandı; kullanıcı commit/push
işlemini onayladı ve `3388c6b` push/CI yeşil tamamlandı. Adres kimliği kontrolünde
kayıtlar ve 6 Ekim hedefli canlı örnek eşleşti; iki risk için gerçek uyuşmazlık
kanıtı bekleniyor (Bölüm 7).
Manuel kayıt aracı hazırlandı; Adım 9'a geçilmedi.
Kullanıcı, sonraki bakım kontrolünden önce bu araç ve kontrol notları için
commit/push yapılmasını onayladı.
Bakım 3'ün dar kural ve regresyon planı da onaylandı ve uygulandı: 652 test,
0 atlandı/xfail; kullanıcı commit/push işlemini onayladı. Bakım 4–7 ve Adım 9 başlamadı.

| Adım | Durum |
|---|---|
| 0. Hazırlık: taslakların taşınması, PostgreSQL 17, `fiyat_takip` kullanıcısı, `fiyat_takip` ve `fiyat_takip_test` veritabanları | ✅ Tamamlandı (28 Eylül) |
| 1. Şema, migrate komutu, CI'da PostgreSQL | ✅ Tamamlandı (28 Eylül): `001_initial.sql`, `python -m app.database migrate/status`, 32 veritabanı testi (toplam 91) |
| 2. Katalogun veritabanına eşitlenmesi | ✅ Tamamlandı (28 Eylül): `python -m app.database sync-catalog [--dry-run]`; kimlik değişiminde hiçbir şey yazmadan durur, katalogdan düşen kayıt pasife alınır; 22 test (toplam 113) |
| 3. Toplama turu ve ortak kilit | ✅ Tamamlandı (28 Eylül): `python -m app.collection [--prefix] [--scheduled]`; sayfa sonucu hemen ve bir kez yazılır, yarım kalan tur sonraki turda kapatılır; tur, keşif ve iki canlı kontrol aracı `data/scrape.lock` kilidini paylaşır; ayrıca veritabanı tur kilidi. Commit öncesi üç ek kontrol: (1) bağımsız kod incelemesi, 13 bulgu, 7 numara hariç hepsi düzeltildi ve testlendi (7 → Adım 4); (2) kasıtlı bozma testi: 37 bozmanın 33'ü testlerce yakalandı, kaçan 4'ü önceden tahmin edilen eşzamanlılık/güvenlik korumaları; (3) ilk canlı tur (`--prefix poco_`, 4 sayfa, 25 sn): 4/4 fiyat, çıkış 0. Testler 22 (toplam 143). |
| 4. Karşılaştırılabilirlik görünümü (sahte düşüş kuralı) | ✅ **Tamamlandı (5 Ekim):** `002_guards_and_comparability.sql`; kullanıcı `migrate` ile uyguladı (14:29 yerel, `status`: iki migration uygulandı). **Kullanıcı kararları (5 Ekim):** tetikleyiciler beş tabloda; görünüm zaman boşluğunu engellemez, yalnız gösterir; çizili fiyat sözleşmede reddedilir (sayfa hata olur). **İçerik:** (A) iki CHECK: `listing_checks_sold_out_has_no_offer` (Tükendi satırı fiyat, çizili fiyat, satıcı, puan ve ölçek taşımaz) ve `listing_checks_original_above_current` (çizili fiyat yalnız güncel fiyattan büyükse; aynı kural `PriceObservation` sözleşmesinde de, scraper'lar zaten `null` verir); (B) 15 tetikleyici: her beş tabloda `DELETE`/`TRUNCATE` reddi, kimlik alanları değişmez (`collection_runs.run_id`'yi PostgreSQL `GENERATED ALWAYS` ile zaten korur), `listing_checks` sonucu bir kez yazılır sonra donar; tek istisna çalışan turdaki `error/network` satırı (Adım 11'in ön koşulu); hata SQLSTATE `23000`; bilerek silmek için tablo sahibi tetikleyiciyi kapatır (docs/teknik.md); (C) `product_run_prices` görünümü: biten tur × ürün için en ucuz fiyat, önceki tur, `hours_since_previous` ve `comparable_with_previous` (cevap veren sayfa kümesi aynıysa ve cevap sayısı > 0). **Kanıt:** testler 450 → 519 (+69: `tests/test_database.py` 131, yeni `tests/test_comparability.py` 14, `tests/test_contracts.py` +3; 182'si gerçek PostgreSQL'de), 0 atlandı, Black ve Flake8 temiz; projenin kopyasında 21 kasıtlı bozmanın 21'i testlerce yakalandı; migrate'ten önce gerçek veride kural ihlali yoktu (1.013 `sold_out` satırında fiyat/satıcı yok, 491 çizili fiyatın hepsi güncel fiyattan büyük); görünümün SELECT'i gerçek veride (709 satır, 13 tur) Python'daki bağımsız hesapla 0 uyuşmazlık verdi ve migrate'ten sonra gerçek veritabanında aynı değerleri gösterdi (15 tetikleyici açık, 2 CHECK var). Önceki tura göre karşılaştırılamayan ürün sayısı: tur 3: 11, 4: 11, 7: 1, 8: 1, 11: 21, 12: 22, diğerleri 0 (tur 11'deki 109 DNS hatası ve tur 12'deki S25+ `identity` hatası dahil). **Bulgu:** `run_id` zaten korunuyor, tetikleyiciden çıkarıldı. **Öğrenilen uyarı:** yeni migration dosyası klasöre girince veritabanı güncellenene kadar tur başlamaz; bu yüzden geliştirme projenin kopyasında yapıldı, dosya gerçek klasöre bitince konuldu ve `migrate` hemen, tur saatleri dışında çalıştırıldı. **Kapsam dışı:** görünümü okuyan API/ML henüz yok (Aşama 7 ve 8); `comparable_with_previous = false` satırlarının yorumu tüketen aşamanın işidir. **Canlı kanıt (5 Ekim 22:00, tur 14):** tur yeni CHECK ve tetikleyicilerle ilk kez çalıştı: 333 sayfa planlandı (334 bağlantı, 1 pasif), `completed`, 36 dk, 229 fiyat, 102 Tükendi, 2 hata, çıkış 2. Hatalar: S25+ `identity` (beklenen) ve ilk kez görülen `invalid_host` (Bölüm 7); tetikleyici veya CHECK kaynaklı `storage` hatası yok, yani 333 sayfanın sonucu kurallara takılmadan yazıldı. Tur başındaki katalog eşitlemesi 7 yeni sayfayı ekledi (`listings` 334). Yeni 7 sayfa ilk okumada 6 fiyat (iPhone 17 Pro Max 2 TB için 168.999–169.999 TL, Galaxy S24 FE 44.999 TL, 14T Pro 42.999 TL, Redmi Note 14 Pro 24.699 TL) ve 1 Tükendi (Redmi Note 13 Pro 5G) verdi. Görünümde `comparable_with_previous` tur 14'te öngörülen ürünlerde (29, 40, 47, 51, 55: yeni sayfa) ve `invalid_host` yüzünden ürün 1'de `false` oldu; ürün 31 (S25+ sayfası iki turdur eksik) bozulmadı. |
| 5. Canlı deneme (kullanıcı çalıştırır) | ✅ Tamamlandı (28 Eylül): ilk tam tur (tur 2, 15:48–16:19 TR saati, **30 dk 55 sn**): 326/326 sayfa okundu, **0 hata, 0 engellenme**; iki sayfa arası en uzun bekleme 9,4 sn. Hepsiburada 213: 139 fiyat, 74 Tükendi; Trendyol 113: 110 fiyat (77 Kritik Stok), 3 Tükendi. 8 ürünün bütün sayfaları Tükendi (çoğu eski iPhone'ların yüksek kapasiteleri). Tarayıcı karşılaştırması 4 sayfa: fiyat, çizili fiyat, satıcı, kuruşlu fiyat (turda 31 tane) ve Kritik Stok eşleşti; 15:49'da Tükendi okunan `trendyol_762254862` 17:47'de "Son 1 ürün" gösteriyordu, yeniden okumada da Kritik Stok çıktı (sayfa arada değişmiş). Aynı ürünün bir sayfasında fiyat 2 saatte 71.059 → 75.524 TL oldu. Bulunan tek hata: ön ek verilmeyen turda `note` NULL yerine boş yazı oluyordu (`concat_ws`); düzeltildi, test eklendi (toplam 144). Tur 2'nin kaydı elle değiştirilmedi. |
| 6. Görev Zamanlayıcı ve 2–3 günlük gözlem | ✅ Tamamlandı (1 Ekim; kuruldu ve gözlendi, gözlem sonucu satırın sonunda). Görev 28 Eylül akşamı `scripts/zamanlayici_kur.ps1` ile kuruldu; kullanıcı ilk turu `Start-ScheduledTask` ile başlattı (tur 3, `scheduled`, 23:22–23:55, 33 dk): `pythonw`, ortam değişkenleri, `pgpass.conf`, çalışma klasörü ve log dosyası Görev Zamanlayıcı ortamında çalıştı. 326 sayfanın 279'u cevap verdi (219 fiyat, 60 Tükendi), 47 sayfa `network` hatası aldı (DNS çözümlenemedi / zaman aşımı; Windows WLAN günlüğüne göre hotspot bağlantısı 23:27:38'de koptu, 23:30:52'de döndü); tur `completed`, çıkış 2, veri uydurulmadı. İlk tetikleyiciyle çalışan tur (tur 4, 29 Eylül 10:00:02, 30 dk 44 sn): 326/326 sayfa, **0 hata** (243 fiyat, 83 Tükendi), çıkış 0; aynı sabah temizlenen kodla gerçek sitelerde ilk tur, istek aralıkları önceki turlarla aynı (Hepsiburada ortalama 8,7 sn). Kararlar (28 Eylül, kullanıcıyla): görev **penceresiz** (`pythonw.exe`) çalışır, `--scheduled` çıktısı `data/logs/tur_<yerel tarih-saat>.log` dosyasına da yazılır (açık kalan bir pencere kapatılınca tur kesilirdi; Görev Zamanlayıcı çıktı saklamaz); görev repodaki `scripts/zamanlayici_kur.ps1` ile kurulur (ayarlar kodda, yeniden kurulabilir). Ayarlar: yerel saatle 10:00/22:00, kaçan tur açılınca bir kez, pilde de çalışır, uyandırmaz, 2 saat süre sınırı, kullanıcı adına yalnız oturum açıkken (docs/teknik.md "Zamanlanmış tur"). Kullanıcının dizüstünde boşta uyku kapalı (şarj ve pil). 5 yeni test (toplam 149); log kodunda 3 kasıtlı bozmanın 3'ü yakalandı; gerçek `pythonw.exe` ile siteye gitmeyen denemede log yazıldı, çıkış 1, tur açılmadı. **Commit öncesi projenin tamamı incelendi (29 Eylül):** 8 bağımsız inceleyici (scraper, keşif, veritabanı, tur, belgeler, güvenlik, okunabilirlik, test kalitesi) bütün dosyaları okudu; her bulgu ayrı bir doğrulayıcıya çürütülmek üzere verildi ve son bir denetçi kimsenin bakmadığı yerlere baktı. 168 ham bulgu → 135 tekil; 10'u çürütüldü, 125'i doğrulandı (57'si kısmen), +24 ek bulgu. Davranış değiştirmeyenler uygulandı: ölü kod temizliği, dışarıdan okuyana yönelik yorumlar (kilit numaraları, Tükendi kuralı, hata kodları, üç istekli Hepsiburada akışı…), belge düzeltmeleri ve testler **149 → 414** (116'sı PostgreSQL'de; yeni `tests/test_http.py`, `tests/test_contracts.py`). Kullanıcı davranış değiştiren bulgulardan üç grubu onayladı ve uygulandı: keşif sağlamlığı (UTF-8 çıktı, BOM'lu dosya okuma, kilit meşgulken çıkış 3, fazladan arama sayfası yok, pasif sayfalar "korunan" listesinde yok, adaptör hatası çıkış 1), migration koşucusu (yeniden adlandırılan dosya reddedilir, numara hatası bulunanları gösterir), tanılama çıktısı (boş satıcı kimliği, `missing_price`/`missing_seller`); her birinin testi önce eski kodda başarısız oldu. Çizili fiyat kuralı (sözleşme + CHECK) Adım 4'e alındı. Araç düzeni: Python `>=3.13,<3.14`, Black `>=26.1`; ortak yapay zekâ talimatları `AGENTS.md`'ye taşındı (Claude Code ve Codex aynı dosyayı okur), `.cursorrules` silindi. Testlere iki emniyet kemeri eklendi: gerçek ağ isteği ve kalıcı `DATABASE_URL` her testte kesilir. Yeni testler bellekte veya kopyada kasıtlı bozmalarla sınandı (75 bozmanın 73'ü yakalandı; kaçan 2'si eşdeğer bozma). Bir gerçek hata bulundu ve `xfail` ile belgelendi (Bölüm 7, Türkçe ekler). Davranış değiştiren bulgular kullanıcı kararına bırakıldı. **Gözlem sonu (1 Ekim):** gerçek veritabanı (yalnız okuma) ve loglar eşleşti: 7 tur kayıtlı, hepsi `completed`, takılı `running` tur ve boş `outcome` satırı yok. Tur 4–6 (29 Eylül 10:00 – 30 Eylül 10:00): 326/326, 0 hata, çıkış 0. **30 Eylül 22:00 turu çalışmadı:** bilgisayar 17:57'de uyudu (Windows günlüğü: uyku nedeni "Application API"; kesin tetikleyici belirlenmedi) ve 1 Ekim 09:20'de uyandı; yukarıdaki "boşta uyku kapalı" ayarı bunu önlemedi. Kaçan tur 1 Ekim 09:26'da açılışta bir kez telafi edildi (tur 7, `scheduled`, 37 dk, 234 fiyat, 91 Tükendi, 1 `network`, çıkış 2): telafi mekanizması bilerek kaçırma denemesine gerek kalmadan gerçek bir uykuda doğrulandı. Aynı turda 09:29'da kritik pil yüzünden yaklaşık 6,5 dk uyku oldu; sayfa 31 uyanma anında DNS hatası aldı, tur veri uydurmadan tamamlandı. 10:00 tetiklemesi tur 7 sürerken geldi ve `IgnoreNew` ile atıldı (ayrı log ve tur kaydı yok); `LastTaskResult = 2` tur 7'nin sonucudur. Bulgular Bölüm 7'ye sınır olarak, kararlar Bölüm 8'e işlendi. |
| 7. Kapanış belgeleri | 🔜 Adım 9'dan sonra; kendi fiyat toplama altyapısı ve Cimri geçmiş aktarımının sonuçları birlikte belgelenir, veritabanı aşaması kapanır. |
| 8. Tek piyasa geçmişi kaynağı araştırması (Adım 6'nın 2–3 günlük gözlemi sırasında) | ✅ Araştırma tamamlandı (29 Eylül): Cimri üç üründe doğru kimlikle 365'er nokta (30 Eylül 2025–29 Eylül 2026), 0 eksik fiyat ve her üründe 90/90 tablo eşleşmesi verdi. Akakçe ilk örneği HTTP 403 verdi; diğer ürünlerine istek atılmadı. `tests/manual/market_history_probe.py` ortak HTTP katmanı/kilit ve dört istek bütçesiyle yalnız yerel rapor üretir. Tarihsel satıcı kapsamı ve günlük gözlem sıklığı bilinmiyor. Araştırma tarihinde kullanım koşulları düzenli kopyalama/işleme için uygunluğu doğrulamadığından aktarım kaynağı seçilmedi; veritabanına veri yazılmadı. **30 Eylül kararıyla bir defalık Cimri aktarımı ayrı Adım 9 olarak planlandı**; araştırmanın tamamlanması aktarımın tamamlandığı anlamına gelmez. |
| 9. Cimri geçmişinin bir defalık aktarımı | 🔜 Planlandı (30 Eylül); **Adım 4'ten sonra, Adım 7'den önce**. Katalogdaki telefonlar Cimri ürünleriyle doğrulanarak eşleştirilir; erişilebilen bir yıllık tarihli fiyat hareketi bir defa alınır ve aynı PostgreSQL veritabanında ayrı `market_history` tablosuna aktarılır. Ürün eşleşmesi, tarih, fiyat, kaynak ve alınma zamanı saklanır; tekrar aktarımın kayıt çoğaltmaması sağlanır. Eşleşmeyen ürünler ve eksik geçmiş raporlanır, veri uydurulmaz. Kullanım koşulu bulgusu ele alınır; tablo yeni numaralı migration ile kurulur. Kod ve ağsız/veritabanı testleri hazırlanır; canlı alım ve gerçek veritabanına yazma komutlarını kullanıcı çalıştırır. Amaç ML eğitimi için geçmiş hareketi saklamaktır; eğitim yöntemi bu adımın işi değildir. Düzenli Cimri toplaması yapılmaz; kendi tur sonuçlarıyla aynı seri gibi birleştirilmez. |
| 10. Haftalık keşif zamanlayıcısı (A1) | ✅ **Tamamlandı (5 Ekim).** Kod, test, belgeler ve görev kurulumu 1 Ekim'de hazırdı; canlı kanıt 4–5 Ekim'de geldi (satırın sonunda). Uygulananlar: ortak log yardımcıları `app/console.py`'ye taşındı (fiyat turunun davranışı ve testleri değişmedi); keşfe `--scheduled` (yalnız `--dry-run` ile; `data/logs/kesif_<ts>.log`, `data/discovery/kesif_<ts>.json`, nedene göre sayılmış tek satırlık özet) ve `--apply-report <rapor>` (siteye gitmez; eklenecekler önizlemedeki listenin alt kümesi olmalı, aksi hâlde hiçbir şey yazılmaz; aynı rapor ikinci kez uygulanırsa bir şey eklenmez) eklendi; `DiscoveryReport.generated_at` ve `DISCOVERY_REPORT_DIR` eklendi; `scripts/kesif_zamanlayici_kur.ps1` görevi `\FiyatTakip\HaftalikKesif` olarak kurar (Pazar 14:00, kaçan çalışmayı telafi etmez, uyandırmaz, 2 saat sınırı; betiği kullanıcı 1 Ekim'de çalıştırdı). Testler 426 → 450 (24 yeni, hepsi ağsız ve veritabanısız); projenin kopyasında 14 kasıtlı bozmanın 14'ü testlerce yakalandı. **Canlı kanıt (1 Ekim, kullanıcı):** `--scheduled --dry-run --target apple_iphone_15` (~79 sn): çıkış 2, log ve rapor aynı damgalı, sabit `data/discovery_report.json` ezilmedi, katalog değişmedi, rapor sözleşmeye uyuyor (Trendyol 5 aday `count_mismatch`, Hepsiburada 15 aday `search_api`, 0 yeni, 20 zaten kayıtlı). Görev kuruldu ve kayıtlı ayarlar salt okunur doğrulandı: haftalık Pazar 14:00 (yerel), `StartWhenAvailable=False`, `WakeToRun=False`, `IgnoreNew`, 2 saat sınırı, `pythonw -m app.discovery --scheduled --dry-run`, çalışma klasörü proje klasörü; fiyat görevi değişmedi (2 tetikleyici, sonraki çalışma 22:00); sonraki keşif 4 Ekim 14:00. **Canlı kanıt (4–5 Ekim):** İlk zamanlanmış çalışma 4 Ekim 14:00:03'te kendiliğinden başladı (`pythonw`, Görev Zamanlayıcı): aynı damgalı log ve rapor yazıldı, loga `Çıkış kodu: 2` düştü; ama internet kesildiği için tarama 7 dk'da boş bitti (DNS hatası: Trendyol 21, Hepsiburada 21 hedef; tam sonuç 3/48, yeni sayfa 0; Bölüm 7). Bu çalışma altyapıyı doğruladı, içeriği doğrulamadı. **5 Ekim 11:00'de kullanıcı aynı komutu elle çalıştırdı** (`--scheduled --dry-run`, normal `python`; tur 13 bitmişti, kilit boştu): 34 dk (11:00:14–11:34:09), DNS hatası yok, tam sonuç 23/48 (Trendyol 23/24; Hepsiburada 24/24 kısmi: arama API'si 403, 16 `model_filter_missing`, 2 `html_partial`), çıkış 2, rapor 305 KB, 0 yeni ürün, **7 yeni sayfa** (iPhone 17 Pro Max 2 TB için 3 Hepsiburada; Galaxy S24 FE 256 GB, Xiaomi 14T Pro 256 GB ve Redmi Note 14 Pro 512 GB için 1'er Trendyol; Redmi Note 13 Pro 5G 256 GB için 1 Hepsiburada), 146 reddedilen (başka hedefin modeli, aksesuar, bilinen yurt dışı sürüm), 37 görülmeyen (korunur), 0 çakışma. Kullanıcı `python -m app.discovery --apply-report data\discovery\kesif_2026-10-05_11-00-14.json` çalıştırdı: 7 sayfa eklendi, 289 zaten kayıtlıydı; `config/catalog.json` +56 satır (LF), eklenen `product_id`'ler (29, 40, 47, 51, 55) veritabanından okunarak doğru ürünlere ait çıktı; katalog **59 ürün, 334 bağlantı**. Sonraki fiyat turu (5 Ekim 22:00) yeni sayfaları veritabanına ekler. **Sınırlar:** tam tarama Görev Zamanlayıcı altında henüz görülmedi (ilk fırsat Pazar 11 Ekim 14:00); Redmi Note 14 Pro 512 GB (Trendyol, `trendyol_1208111572`) sayfasının 4G olduğu ekleme sonrası kullanıcı tarafından tarayıcıda doğrulandı (5 Ekim; ürün sayfasında 4G yazıyor; ağ türü raporda görünmediği için eklemeden önce görülemedi); keşif logu ilerleme satırı yazmaz, yalnız 4 satır (başlık, özet, rapor yolu, çıkış kodu) bırakır. |
| 11. Tur sonunda `network` ikinci geçişi | ✅ **Tamamlandı (6 Ekim):** 1 Ekim kararı (Bölüm 8) uygulandı; migration gerekmedi (Adım 4'teki 002 tetikleyicisi çalışan turdaki `network` satırının yeniden yazılmasına zaten izin veriyordu). `app/collection/service.py` `retry_network_errors`: sayfa döngüsü bittikten sonra, tur kapatılmadan önce yalnız o turda `error`/`network` sonuçlu sayfalar (5xx dahil) bir kez yeniden okunur; yeni `app/database/runs.py` `rewrite_network_result` yalnız süren turun `error`/`network` satırını yazar (`record_result` ile ortak `_write_result`). **Davranış (kullanıcı kararları, 6 Ekim):** düzelirse satır yeni sonuçla değişir (fiyat, Tükendi ya da `network` dışında bir hata); ikinci okuma da `network` verirse ilk satır (mesaj ve zaman damgası dahil) olduğu gibi kalır; veritabanı yeni sonucu reddederse ilk satır kalır ve tur sürer; ardışık 5 sayfa yine `network` verirse geçiş durur (kalanlar denenmez); `blocked`, `parse`, `identity` ve diğer hatalar hiç yeniden denenmez; log `[tekrar i/n]` satırları taşır; tur notuna yalnız sayılar yazılır (`network hatası alan 109 sayfa, ikinci okuma: 104 düzeldi, 5 hâlâ hatalı`), sayfa kimlikleri logdadır; çıkış kodu ve özet ikinci okumadan sonraki duruma göre hesaplanır; düzelen sayfa cevap sayıldığı için görünümde sahte "karşılaştırılamaz" satırı oluşmaz. **Kanıt:** testler 527 → 545 (+18, hepsi gerçek PostgreSQL'de: 182 → 200), 0 atlandı, Black ve Flake8 temiz; akış testleri eski kodda başarısızdı (9 akış testi kırmızı; 7 "yalnız `network` yeniden okunur" koruması ve 2 `rewrite_network_result` birim testi eski kodda da geçer, çünkü işlev yeni); projenin kopyasında 20 kasıtlı bozmanın 20'si testlerce yakalandı. **Sınırlar:** gerçek bir turda henüz görülmedi (`network` hatası olmayan turlarda ikinci okuma çalışmaz); bilgisayar uyursa ya da kesinti tur bitene kadar sürerse sayfalar hatalı kalır (kalıcı çözüm sunucu, Aşama 9); düzelen sayfanın `checked_at` değeri ikinci okuma anıdır (ilk denemeden en çok tur süresi kadar sonra). Ayrıntı: docs/teknik.md "Tur sonu ikinci okuma". |

Adım 8 canlı sonuçlar (29 Eylül 2026): Akakçe iPhone 16 128 GB sayfası 1
istekte HTTP 403 `blocked`; Cimri'nin üç örneğinde kimlik eşleşti ve HTML
tablosunda sırasıyla 49/58/29 farklı tarihli aday satır bulundu. Grafik API'si
Apple, Samsung ve Xiaomi için 365'er tarihli fiyat döndürdü; her birinde 0 eksik
fiyat ve 90/90 gömülü tablo eşleşmesi var (Bölüm 7). Tablo yaklaşık üç ayla
sınırlı, grafik 30 Eylül 2025'e uzanıyor. Cimri teknik adaydır; yayımlı
koşullarda düzenli kopyalama/işleme için uygun hak doğrulanmadığı için aktarım
kaynağı araştırma tarihinde seçilmedi. 30 Eylül'de Cimri'nin bir defalık
aktarımı Adım 9'a alındı (Bölüm 8). Akakçe 403 için tekrar veya engel aşma
yapılmaz.

Takvim (tahmin, 6 Ekim güncellemesi; Adım 9 ve 11'in süresi henüz belirlenmedi):

| Tarih | İş |
|---|---|
| 29 Eylül | Adım 8 araştırması tamamlandı; kaynak seçilmedi |
| 1 Ekim | **Adım 6 kapandı:** 7 turun özeti; kaçan turun telafisi gerçek bir uykuda doğrulandı. Keşif A1 ve `network` ikinci geçişi kararları işlendi |
| 1–5 Ekim | **Adım 10 kapandı (5 Ekim):** kod ve görev 1 Ekim'de; ilk zamanlanmış keşif 4 Ekim (internet kesintisi yüzünden boş); elle tam tarama ve `--apply-report` 5 Ekim (7 sayfa, 334 bağlantı) |
| 5 Ekim | **Adım 4 kapandı:** `002` migration (koruyucu kurallar ve görünüm) projenin kopyasında geliştirildi, tur saatleri dışında uygulandı |
| 6 Ekim | Plan adımı değil: **bulut denemesi** (GitHub'dan Hepsiburada okundu, Trendyol 403; strateji kararı verilmedi, Bölüm 8) ve Adım 11'den önce **genel denetim** (ölü kod taraması, belge–kod tutarlılığı, bakım listesi): eskimiş belge ve yorumlar düzeltildi, `invalid_host` mesajı, keşif uyarısı/yazma hatası ve kilit çıkış kodu düzeltildi, S25+ sayfası pasife alındı, bakım listesi yeniden düzenlendi (Bölüm 7) |
| 6 Ekim | **Adım 11 kapandı:** tur sonunda `network` ikinci okuması (kod ve testler; gerçek turda henüz görülmedi) |
| 6 Ekim | İkinci denetim bakımı tamamlandı: Hepsiburada bozuk satıcı yanıtı düzeltildi (`572061c`, CI yeşil); iki SQL koruması `003` ile kopyada test edildi, kullanıcı 13:30'da uyguladı, salt okunur denetim temiz |
| 6 Ekim | Yedi ertelenmiş bakım için kontrol ve gerekli düzeltme planı onaylandı; ilk madde (indirme sırasında 8 MB sınırı) tamamlandı: 27 yeni test, toplam 598; kullanıcı commit/push işlemini onayladı |
| 6 Ekim | Bakım 2: kayıtlı 333 farklı adres/334 katalog sayfası ve kullanıcının 16:24–16:26 iPhone 15 kontrolündeki TY 5/HB 16 kimliği eşleşti. HB grup/kategori canonical adresleri doğru biçimde kullanılmadı. Çıkış 2 yalnız bilinen arama API 403'ü; iki yapay risk için gerçek uyuşmazlık kanıtı bekleniyor. Manuel ham kayıt aracı ve 12 ağsız test hazır (610 toplam); kimlik kuralı değişmedi |
| 6 Ekim | Bakım 3: kayıtlı Kılıfı/Adaptörü/Kapağı yazımları için dar kimlik ve kategori düzeltmesi uygulandı. 41 ek sınama ve normal teste çevrilen xfail; 21 gerçek telefonun kabulü korundu. 652 test geçti, 0 atlandı/xfail; Black/Flake8 temiz. Kullanıcı commit/push işlemini onayladı |
| Adım 11 sonrası | **Adım 9:** Cimri geçmişinin bir defalık alımı, katalog eşleştirmesi ve ayrı `market_history` tablosuna aktarım |
| Adım 9 sonrası | **Adım 7:** kapanış belgeleri; veritabanı aşaması biter. Önceki 2–3 Ekim kapanış tahmini yeni adımlara göre yeniden değerlendirilecek |

Kendi topladığımız geçmiş, ilk tam turdan (28 Eylül) sayılırsa Ekim sonunda
30 güne ulaşır; bu süre tek başına yeterli eğitim verisi garantisi değildir.
ML eğitimi için bir yıllık geçmiş hareket hedefi Cimri aktarımıyla (Adım 9)
karşılanacak; katalog genelindeki gerçek tarih kapsamı aktarımda doğrulanır.
API/arayüz aşaması kendi geçmişimiz birikirken ilerleyebilir.

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
- **Karar (30 Eylül 2026, kullanıcı; Codex):** Cimri'nin erişilebilen bir
  yıllık geçmiş fiyat hareketi model eğitiminde kullanılmak üzere Adım 9'da
  bir defa alınacak ve ayrı `market_history` tablosunda saklanacak. Daha
  geniş kaynak kapsamından doğan küçük fiyat farkları kullanıcı tarafından
  bu amaç için kabul edildi; kendi takip edilen minimumumuzla aynı ölçüm
  olduğu varsayılmaz. Mutlak fiyatın mı değişimin mi kullanılacağı, eğitim
  yöntemi ve değerlendirme ayrıntıları ML aşamasında netleştirilir;
  yukarıdaki model taslağı o aşamada bu veriyle birlikte değerlendirilir.

### İşletim

Docker Compose ile süreçler, veri ve model kalıcılığı; GitHub Actions ile CI
(bugün Black, Flake8, testler çalışıyor). Ayrıca elle tetiklenen bir bulut
denemesi var (`.github/workflows/bulut-deneme.yml`, 6 Ekim; zamanlama ve
veritabanı yok, yalnız canlı okuma dener; sonucu Bölüm 8'de). Toplamanın nerede
çalışacağı (bilgisayar, evde 7/24 cihaz, kiralık sunucu) bu aşamanın kararıdır
ve henüz verilmedi.

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
