# Akıllı Telefon İndirim Takip ve Tahmin Sistemi — Proje Planı

Son güncelleme: 8 Ekim 2026.

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
| 6. Veritabanı ve zamanlanmış toplama | ✅ **Tamamlandı (8 Ekim): Adım 0–11 ve yedi bakım kapandı.** 001–004 şeması ve katalog/DB eşitliği doğrulandı: 59 ürün, 334 sayfa (332 etkin). Son zamanlanmış tur 19: 332/332 sonuç, 237 fiyat/95 Tükendi/0 hata; log ve DB aynı. Karşılaştırılabilirlik görünümü 59 ürün için bağımsız doğrulandı. Cimri: 57 ürün/20.805 kayıt/553 NULL; tekrar aktarım ve ilk kaynak bilgileri korundu, iki eşleştirme eksikliği belgeli. Bilinen sınırlar ve canlı gözlem bekleyen senaryolar korunuyor. Adım 7 kapanış belge commit/push işlemi kullanıcı tarafından onaylandı; aynı SHA CI gönderim akışında doğrulanır; API/arayüz başlamadı. | Bölüm 7, Adım 7 kapanışı; Bölüm 9 |
| 7. FastAPI ve Streamlit | 🔜 Planlandı, başlanmadı | Bölüm 9 |
| 8. ML (indirim tahmini) | 🔜 Planlandı, başlanmadı | Bölüm 9 |
| 9. Docker ve 7/24 işletim | 🔜 Planlandı, başlanmadı | Bölüm 9 |

**6 Ekim ikinci denetimi sonrası bakım (kullanıcı onayı):** Hepsiburada bozuk
satıcı yanıtı düzeltildi (552 test). İki SQL koruması `003_closed_run_guards.sql`
ile test edildi (571 test), kullanıcı 6 Ekim'de gerçek veritabanına uyguladı;
salt okunur denetimle doğrulandı. Üç bakım bulgusu kapandı; o tarihte kalan
sıra Adım 9 → 7 idi. 8 Ekim’de Adım 9 ve ardından Adım 7 tamamlandı;
veritabanı aşaması kapandı (Bölüm 7).

**6 Ekim ertelenmiş bakım planı (kullanıcı onayı):** yedi madde ayrı adımlarla
kontrol edilip gerekli düzeltmeler yapılacak; eksik kanıt için hedefli canlı
komutları kullanıcı çalıştıracak. İlk madde, HTTP indirme sınırı, tamamlandı
(598 test). İkinci maddenin kayıt ve hedefli canlı kontrolü yapıldı; bu örnekte
kimlik uyuşmazlığı yoktu, iki yapay riskin gerçek uyuşmazlık kanıtı bekleniyordu.
Ham yanıt kaydı için manuel araç hazırlandı (611 test). Üçüncü madde,
Türkçe ekli aksesuarlar, kullanıcı onayıyla düzeltildi (652 test, 0 atlandı,
0 beklenen başarısızlık); kullanıcı commit/push işlemini onayladı.
Dördüncü maddede iPhone 15 ve Galaxy S24 için 40 Hepsiburada HTML'de
37 tek dolu liste, 0 çelişki görüldü. Kullanıcı bu madde için gerçek çelişkiyi
bekleme şartına istisna verdi; önleyici kapasite/renk doğrulaması uygulandı
(727 test, 0 atlandı/xfail; Black/Flake8 temiz). Kullanıcı commit/push işlemini onayladı;
5–7'ye geçilmedi. Kullanıcı 7 Ekim'de önce bakım 2'nin açık adres risklerine
dönülmesini, ardından 5 → 6 → 7 sırasıyla ayrı ilerlenmesini istedi. İki hedefin
ham kayıtları yeniden incelendi: TY 6 varyant/adres/sayfa kimliği, HB 36 ürün
SKU'su eşleşti; gerçek uyuşmazlık görülmedi. Kullanıcı bu maddeye de ayrı istisna
verdi; iki dar adres koruması önleyici olarak uygulandı. 31 yeni sınama, toplam
758 geçti/0 atlandı/xfail (219 PostgreSQL); Black/Flake8 temiz. Kullanıcı
commit/push işlemini onayladı; bakım 5'e geçilmedi.
Ayrıntı ve durumlar Bölüm 7'de.

**7 Ekim bakım 5 (kullanıcı onayı, önleyici düzeltme uygulandı):** beş tüketicide
ürün adresi kimliği yalnız ürün yolundan ortak kuralla okunuyor; iki yardımcı
mevcut `app/scraper/parsing.py` içinde, eski dönüş/hata sözleşmeleri korundu.
334 katalog ve 333 farklı kayıtlı aday adresinde önce/sonra kimlik farkı yok.
Kullanıcı yalnız bakım 5 için gerçek uyuşmazlık örneğini bekleme şartına ayrı
istisna verip planı onayladı; yapay fiyat seçimi riski regresyonla kapandı,
canlı yanlış kayıt kanıtı yok. 39 yeni sınama; toplam 797 geçti/0 atlandı/xfail
(219 PostgreSQL), Black/Flake8 temiz. Gerçek katalog/veritabanı/migration
değişmedi. Kullanıcı commit/push işlemini onayladı; `ac9c6b6` gönderildi,
aynı SHA için CI 37616987979 yeşil.

**7 Ekim bakım 6 (kullanıcı onayı, tamamlandı):** veri koruması kontrol edildi,
mevcut davranış kabul edildi; kapanış sonrası Ctrl+C'yi yanlış anlatan mesaj
düzeltildi. Özet SQL hatası, bağlantının kontrollü kapanması ve Ctrl+C,
elle/zamanlanmış girişlerde sınandı; completed tur ve bütün kayıtlar, iki kilit
ve sonraki tur korundu. Çıkışlar özet/bağlantı hatasında 1, Ctrl+C'de 130.
7 yeni sınama; 804 geçti/0 atlandı/xfail (226 PostgreSQL), Black/Flake8 temiz.
Gerçek DB/katalog/migration/zamanlayıcı değişmedi. Kullanıcı commit/push
işlemini onayladı; `ea4248e` gönderildi, aynı SHA için CI 37625155724 yeşil.

**7 Ekim bakım 7 (kullanıcı onayı, kontrol edildi ve mevcut davranış kabul edildi):**
iki eklenti yükleyicisinin farklı sözleşmeleri korundu; üretim kodu değişmedi.
Yükleme/kurma hatası, Ctrl+C, tur/keşif devam-durma davranışı, kayıt ve dosya
koruması, kapanışlar, loglar ve kilitler kalıcı testlerle doğrulandı. 28 yeni
sınama; hedefli 43 geçti, son tam paket 832 geçti/0 atlandı/xfail (228 PostgreSQL),
Black/Flake8 temiz. Yedi bakım maddesinin kontrol/düzeltmesi tamamlandı;
kullanıcı bakım 7'nin commit/push işlemini onayladı, yeni özellik aşamasına geçilmedi.

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

Keşif adres riski 7 Ekim'de bakım 2'ye özel kullanıcı istisnasıyla kapandı:
TY adres yolu/kaynak/sayfa kimliği eşleştirilir; HB canonical SKU'su tam
eşitlikle doğrulanır. Gerçek kaynakta uyuşmazlık görülmedi, önleyici düzeltmedir.

Kontrol edilip kabul edilen sınır (7 Ekim, bakım 6):
- Tur tamamlandıktan sonra özet sorgusu (`run_summary`) düşerse çıkış kodu 1 olur ama
  tur `completed` kalır. Özet SQL hatası, bağlantının kapatılması ve kapanış
  sonrası Ctrl+C'de bütün kayıtlar, kilitler ve sonraki tur kalıcı testlerle
  doğrulandı. Veri/akış değişikliği gerekmedi; yalnız Ctrl+C mesajı düzeltildi
  (ayrıntı aşağıda ve docs/teknik.md'de).

6 Ekim denetimindeki ortaklaştırma bulgularının güncel durumu:
- Beş yerdeki ürün adresi desenleri ve davranış farkları 7 Ekim bakım 5'te
  ortak iki yardımcıyla kapatıldı; kimlik yalnız ürün yolundan okunur.
  `_url_identity` mevcut iki platformu seçmeye devam eder; bilinmeyen platform
  `None` döndürür. Yeni site/eklenti mimarisi bu bakımın kapsamında değildir.
- İki eklenti yükleyicisi (`scraper/factory.py`, `discovery/service.py` `_adapter`)
  bakım 7'de ayrı kontrol edildi; farklı sözleşmeleri kabul edildi, birleştirilmedi.
- Kimlik değişikliklerinde canlı örnek ve regresyon şartı sürer. Bakım 2, 4
  ve 5'in önleyici düzeltmeleri için kullanıcı her maddeye ayrı istisna verdi.
  Varyant tutarlılığı riski bakım 4'te, adres farkları bakım 2 ve 5'te kapandı.
  Eklenti yükleyicileri farklı sözleşmeler
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
Adres riskleri ilk incelemede gerçek kaynak kanıtı bekledi; 7 Ekim'de ayrı
kullanıcı istisnasıyla bakım 2'de önleyici olarak düzeltildi. Çoklu varyant riski
de aynı gün kullanıcının bu maddeye özel kararıyla düzeltildi. Türkçe ekli
aksesuarlar bakım 3'te düzeltildi.

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
O tarihte yapay örnekte doğrulanan iki risk düzeltilmemişti; gerçek uyuşmazlık
örneği için durum **kanıt bekliyor** olarak kaldı (7 Ekim kapanışı aşağıda).
Aynı hedefi yeniden
çalıştırmak gerekmedi; sonraki bakım 3 kullanıcı talebiyle ayrı tamamlandı.
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

**7 Ekim bakım 2'ye dönüş (kullanıcı kararı):** bakım 4'ün `afe03e4`
commit/push ve yeşil CI doğrulamasından sonra kullanıcı önce bu iki açık riski
yeniden kontrol etmeyi, ardından **5 → 6 → 7** sırasıyla ayrı ilerlemeyi istedi.
`data/kimlik_iphone15_20261006/` ve `data/varyant_s24_20261007_105625/`
özgün yanıtları ağsız yeniden incelendi; her kökte `identity_recheck.json`
yerel inceleme sonucu tutuldu. Yeni canlı istek, katalog veya veritabanı yazımı
yapılmadı.

- Trendyol: iPhone 15'te 5, S24'te 1 farklı varyant `id/pageUrl` çifti ve açılan
  sayfanın `product.id` değeri istenen adresle eşleşti; eksik/farklı kimlik yok.
- Hepsiburada: iPhone 15'te 16, S24'te 20 ürün sayfasında istenen SKU, tam ürün
  bağlamı ve JSON-LD SKU'su eşleşti. S24 canonical adresleri 4 grup/16
  kategori-model adresi; toplam 36 sayfada 13 grup/23 kategori-model canonical,
  ürün SKU'su taşıyan canonical yok. Kabul edilen 24 adayın doğrulanmış özgün
  adresi korundu; S24'te diğer modellere ait 12 sayfanın reddi adres uyuşmazlığı
  değildir. Arama API 403'ü de adres hatası değildir.
- İki tarihsel yapay risk sınaması güncel kodda tekrar geçti: kimliksiz TY
  adresi ve beklenen SKU'yu alt dize olarak içeren farklı HB canonical adresi
  kabul edilebiliyor. Bu, riskin sürdüğünü gösterir; düzeltme testi veya canlı
  yanlış kayıt kanıtı değildir. Katalog sözleşmesi HTTPS/alan adı ve referansları
  denetler; bu iki durumda aday kimliği ile adres kimliğini ayrıca eşitlemez.

**Onaylanan ve uygulanan kapanış planı (7 Ekim):** kullanıcı "tamam
uygula o zaman amaç bakım ve kontroldü zaten" diyerek bu iki dar korumayı ve
yalnız bakım 2 için gerçek uyuşmazlık örneğini bekleme şartına istisnayı onayladı:

1. TY adayında mevcut ürün adresi kimliği, kaynakta beklenen ürün kimliğiyle
   karşılaştırılır; eksik/farklı kimlik `identity` hatasıyla aday reddine gider.
   Sayfanın kendi kimliğini doğrulama ve diğer adaylarla devam davranışı korunur.
2. HB canonical ürün SKU'su tam eşitlikle karşılaştırılır; başka SKU varsa
   canonical kullanılmaz, doğrulanmış istenen ürün adresi korunur. Aynı SKU'nun
   canonical adresi kullanılabilir; grup/kategori ve başka alan adı davranışı
   korunur.
3. Eksik/farklı TY adresi ve HB alt dize tuzağı eski kodda başarısız olan kalıcı
   regresyonlarla sınanır; geçerli adresler, sorgu/son eğik çizgi/küçük harfli HB
   SKU, sayfa kimliği reddi ve taramanın devamı korunur. Altı kayıtlı TY adayının
   ve 24 HB adayının alanları ile 12 diğer model reddi ağsız örneklerle sınanır.
4. Bütün pytest, Black ve Flake8 çalışır; PostgreSQL yalnız `_test`, atlananlar
   açıkça bildirilir. Belgeler güncellenir; dosya listesi ve Türkçe commit mesajı
   gösterilip durulur, commit/push ayrı onayladır.

Yeni telefon/kapsam veya beş adres tüketicisini ortaklaştırma bu plana dahil
değildir. Katalog, gerçek veritabanı, migration ve geçmiş kayıtlar değişmez.
`AGENTS.md` genel gerçek kaynak şartı yürürlüktedir; bakım 2 için ayrı kullanıcı
onayı alındı, bakım 4'e verilen istisna otomatik taşınmadı. İstisna diğer kimlik
ve kapsam değişikliklerini kapsamaz. Gerçek uyuşmazlık bulunduğu iddia edilmez.
Yeniden kontrol sırasında yalnız iki yerel risk sınaması çalıştırıldı (2 geçti);
bu aşamada kod değişmediği için tam 727 test tekrar çalıştırılmadı.

**Bakım 2 uygulaması tamamlandı (7 Ekim):** `app/discovery/trendyol.py`
adayın ürün yolunu o adımda kullanılan `PRODUCT_ID` kuralıyla kaynak kimliğine
eşitler (bakım 5'te bu desen ortak yardımcıya taşındı);
eksik/farklı kimlikte istek göndermez, `identity` hatası raporda aday reddi olur.
Ürün sayfası deneme sınırı ve diğer adaylara devam korunur; sayfanın kendi
kimliği ayrıca doğrulanır. `app/discovery/hepsiburada.py` aynı alan adındaki
canonical ürün yolundan SKU çıkarıp tam eşitlikle karşılaştırır; farklı SKU,
grup/kategori veya yalnız sorguda geçen kimlik varsa doğrulanmış istenen adres
korunur. Bu adımda beş adres tüketicisi ortaklaştırılmadı; sonraki bakım 5'te
ayrı plan ve kullanıcı onayıyla ortaklaştırıldı.

31 kalıcı sınama eklendi: eski kodda **12 başarısız, 19 başarılı**. Kimliksiz,
farklı/bozuk son ekli TY adresleri ve sorguda kimlik bulunması; HB alt dize
tuzağı ve yanlış canonical; geçerli sorgu/son eğik çizgi/küçük harfli SKU,
sayfa kimliği reddi ve keşfin diğer adaylarla devamı sınandı. Yeni
`tests/fixtures/discovery/trendyol_identity_examples.json`, iki ham kayıttan
6 TY adayının yalnız kimlik alanlarını ve beklenen bütün aday bilgilerini
saklar (fiyat/stok yok, `data/` ve ağdan bağımsız). Bu 6 adayın ve mevcut HB
fixture'ındaki 24 aday/12 model reddinin korumaları başarılı.

Nihai tam test: **758 passed**, 0 atlandı/xfail, 44,42 sn; 219 PostgreSQL testi
yalnız `fiyat_takip_test`. Black 43 dosyada, Flake8 temiz. İlk hedefli yeşil
denemede iki yeni testin rapor mesajı beklentisi düzeltildi (mevcut rapor mesajı
hata kodu öneki taşımıyor); üretim rapor sözleşmesi değiştirilmedi. Son tam
çalışma bu düzeltme ve Black sonrası yapıldı. README test sayısı ve teknik
belge güncellendi. Gerçek katalog/veritabanı, migration ve geçmiş kayıtlar
değişmedi; kullanıcıdan yeni canlı komut istenmedi. Durum **önleyici düzeltme
uygulandı**; kullanıcı commit/push işlemini onayladı, bakım 5'e geçilmedi.
Kullanıcı bakım numarasının commit geçmişinde görünmesini istedi; seçilen mesaj:
**2. bakım düzeltmesi: keşifte ürün adresi kimliğini ve canonical SKU eşitliğini doğrula**.

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

**6 Ekim bakım 4, Hepsiburada varyant tutarlılığı (kontrol planı onaylandı):**
Kullanıcının iPhone 15 ham yanıtlarındaki 19 Hepsiburada HTML incelendi.
17 sayfada birer boş olmayan `allVariantCombinations` listesi bulundu;
hiçbirinde aynı sayfa içinde kapasite/renk çelişkisi veya çoklu dolu liste yok.
Diğer iki HTML varyant taşımıyor. `HBCV0000D3AULB` kaydında `Kapasite`
alanı yok; 128 GB başlıktan hâlâ doğrulanıyor. Eksik alan çelişki sayılmadı.
Kayıttaki tek HTTP hata, bilinen Hepsiburada arama API'sinin `blocked`/403'ü;
varyant hatası olarak sınıflandırılmadı.

Git dışındaki `.scratch/check_hepsiburada_variants.py` yalnız kaydedilmiş
Hepsiburada HTML/index dosyalarını okur; aynı SKU'nun bütün listelerdeki
kapasite/renk bilgilerini ve kaynak JSON konumunu karşılaştırır. Kapasite GB'ye,
renk mevcut normalizasyonla karşılaştırılır; boş alan ve eşdeğer tekrar çelişki
sayılmaz. Altı yapay kontrol, çelişki/tekrar/eksik alan/eşdeğer birim/farklı SKU/
tek liste içi çelişki ayrımını doğruladı; bunlar canlı hata kanıtı değildir.
Gerçek inceleme çıktısı `data/kimlik_iphone15_20261006/variant_analysis.json`.
Yerel inceleme aracı uygulamaya bağlı değildir ve tamamlanmış özellik sayılmaz.
Hazırlık sonrası tam paket `652 passed`, 0 atlandı/xfail (219 PostgreSQL),
41,99 sn; Black ve Flake8 uygulama, testler ve yerel inceleme aracında temiz.

**7 Ekim ilk devam durumu:** kullanıcının önceki paylaştığı çıkış 2, mevcut ham kayıt
klasörü nedeniyle komutun tarama başlamadan reddedilmesidir; kaynak 403'ü veya
varyant çelişkisi değildir. `data/varyant_s24_20261006/` içinde önceki denemeden
yalnız 3 Trendyol yanıtı ve index var; Hepsiburada klasörü ve `report.json` yok.
Önceki denemenin neden yarım kaldığı bu dosyalardan belirlenemiyor. Kayıtlar
korundu; yeni komut tarih-saat damgasıyla farklı klasör açtı. Kullanıcı
7 Ekim 10:00 turunun bittiğini bildirdi; salt okunur kontrolde görev `Ready`,
son çalışma 10:00:01, son görev sonucu 0, sıradaki tetikleme 22:00 olarak görüldü.
Canlı kontrolü kullanıcı çalıştırdı; ajan site isteği göndermedi.

**7 Ekim Galaxy S24 kaynak kontrolü tamamlandı (10:56:26–10:57:58, yerel):**
Ham kayıt `data/varyant_s24_20261007_105625/` içinde, karar izi aynı adlı
`_iz.json` dosyasında. Trendyol 13 gerçek istekle tam sonuç/1 aday, Hepsiburada
22 gerçek istekle kısmi sonuç/8 aday verdi. Bu yeni çalışmanın çıkış 2 nedeni
Hepsiburada'da `model_filter_missing` ve arama API'sinin `blocked`/403'üdür;
klasör hatası veya varyant çelişkisi değildir. Başka modeller olan S24+, Ultra
ve FE'ye ait 12 sayfa kimlik kontrolüyle reddedildi. Yeni ürün/sayfa yok;
katalog ve veritabanı yazılmadı.

Hepsiburada'nın 21 HTML yanıtı incelendi: 20 ürün sayfasında birer dolu
`allVariantCombinations` listesi, arama sayfasında bir boş liste var.
Ham metindeki liste sayıları ayrıştırılmış JSON ile eşleşti; aynı sayfa/SKU
içinde kapasite veya renk çelişkisi ve çoklu dolu liste yok. Kabul edilen
8 Galaxy S24 adayının kapasite ve rengi kayıtlı seçeneğiyle eşleşiyor;
scraper ve keşfin mevcut kapasite seçimi aynı. İnceleme çıktısı aynı kökte
`variant_analysis.json` olarak saklandı.

**İlk kontrol sonucu: uyuşmazlık kanıtı bekleniyordu.** İki hedefin toplam
40 HTML yanıtında 37 tek dolu liste ve 0 çelişki var; bu sınırlı örnekler
pazaryerinde çoklu liste bulunmadığını kanıtlamaz. İlk kanıt toplama planı gereği
uygulama kodu ve kimlik kuralları korunuyor; başlıktan kapasite doğrulama
değişmedi. Gerçek çelişki görülürse kaynak örneğine dayanan kesin düzeltme
planı ve regresyonlar ayrıca onaya sunulacaktı. Bu ilk kontrolde yalnız kayıt
incelemesi ve belge güncellemesi yapıldı; son doğrulama 6 Ekim'deki 652 test/Black/Flake8,
testler yeniden çalıştırılmadı. Bakım 5'e ve yeni özelliklere geçilmedi.

**7 Ekim kullanıcı kararı ve uygulama: önleyici düzeltme uygulandı.** Kullanıcı,
gerçek çelişkiyi beklemek yerine bakım 4'ün planlanıp düzeltilmesini istedi ve
kesin uygulama planını onayladı. Bu, AGENTS.md'deki gerçek kaynak şartına yalnız
bu madde için istisnadır; genel kural değişmedi. Bakım 2'nin istisnası daha sonra
ayrı kullanıcı onayıyla verildi (yukarıdaki adres bakımı).
Gerçek kaynakta çelişki görülmediği bilgisi korunur.

`variant_identity(soup, sku)` aynı SKU'nun bütün seçenek kayıtlarında kapasite
ve rengi birlikte doğrular. `variant_capacity` ve keşif bu ortak sonucu kullanır;
ilk kapasite/son renk karışımı kaldırıldı. Farklı kapasite veya renk `identity`
üretir; scraper satıcı/fiyat isteği yapmaz, keşif yalnız o adayı reddedip sürer.
Eşdeğer tekrarlar (TB/GB ve mevcut renk normalizasyonu), boş/ayrıştırılamayan
alanlar ve başka SKU'nun çelişkisi reddedilmez. Kapasite alanı bulunmazsa
başlıktan doğrulama sürer; SKU keşifte herhangi bir listede bulunabilir.
Grup sayfalarının bağlantı kuyruğu, adres kuralları ve sözleşmeler korundu.

75 yeni sınama eklendi. Eski kodda **31 failed, 44 passed**: çelişki reddi için
24 sınamanın tamamı başarısızdı; kalan başarısızlıklar eşdeğer renk/eksik alan/
önceki listede SKU ve keşfin diğer adaylarla devamını kapsıyordu. 36 gerçek
ürün sayfasından kimlik alanları sabit test verisine çıkarıldı; 24 kabul edilen
adayın bütün alanları ve diğer modele ait 12 sayfanın reddi korundu. Kaynak
fiyat/stok verisi eklenmedi; kalıcı testler ham `data/` kayıtlarına bağlı değil.
Son doğrulama **727 passed**, 0 atlandı/xfail, 50,64 sn (219 PostgreSQL);
Black 43 dosyada temiz, Flake8 tek işçiyle temiz. Gerçek DB, katalog ve migration
değişmedi; canlı site komutu çalıştırılmadı. Kullanıcı commit/push işlemini onayladı.
Bakım 5'e geçilmedi.

**7 Ekim bakım 5: ürün adresi kimliği kuralları ortaklaştırıldı.** Kullanıcı
yalnız bu bakım için gerçek uyuşmazlık örneğini bekleme şartına ayrı istisna
verdi ve uygulama planını onayladı. Çalışma önleyici düzeltmedir; gerçek
kaynaklarda sorunlu son ek/sorgu kimliği veya yanlış fiyat kaydı görülmedi.

`app/scraper/parsing.py` içindeki `trendyol_product_id(url)` ve
`hepsiburada_sku(url)` kimliği yalnız ürün yolundan metin olarak okur,
bulunamazsa `None` döndürür. Trendyol küçük harfli `-p-`/rakam kuralını,
Hepsiburada harf/rakam SKU'sunu büyük harfe çevirme kuralını kullanır.
Sorgu/alan adı metni kimlik sayılmaz; bozuk son ek reddedilir. Geçerli sorgu,
son eğik çizgi, göreli yol ve baştaki sıfırlar korunur. İki scraper, iki keşif
modülü ve katalog eşleştirme bu yardımcıları kullanır; yinelenen ürün desenleri
kaldırıldı. `_product_id`, `_sku_from_url`, `_url_identity` dönüş/hata
sözleşmeleri, HB keşif grup kuralı ve bakım 2'nin adres/sayfa/canonical
korumaları değişmedi. Adres yeniden yazımı veya yeni eklenti mimarisi yoktur.

39 yeni sınama eklendi. Eski kodda **13 failed, 26 passed**: tüketicilerin
adres farkları, iki sorunlu ucuz TY teklifinin fiyat seçiminden elenmesi,
iki geçersiz TY ürün adresinin reddi ve HB'nin sorgudaki SKU'yu reddi açığı
yakaladı. Grup adresleri, bilinmeyen platform, geçerli sorgu/eğik çizgi/küçük
harfli SKU ve mevcut istek sırası ayrıca korundu.

334 katalog adresi ve kayıtlı 333 farklı aday adresinin önce/sonra kimlikleri
aynı; katalog kayıt kimlikleri, katalog ve uygulanmış migration dosyalarının
bayt parmak izleri değişmedi. Sabit katalog testleri, kayıtlı 6 TY/24 HB adayın
bütün alanları ve diğer modele ait 12 sayfanın reddi korundu. Son tam test
**797 passed**, 0 atlandı/xfail, 40,18 sn; 219 PostgreSQL testi yalnız
`fiyat_takip_test` üzerinde çalıştı. Black 44 dosyada temiz, Flake8 tek işçiyle
temiz. Canlı site komutu veya gerçek DB yazımı yapılmadı. Durum **önleyici
düzeltme uygulandı**; kullanıcı commit/push işlemini onayladı, bakım 6'ya geçilmedi.

**7 Ekim bakım 6: veri koruması kontrol edildi, mevcut davranış kabul edildi;
kesinti mesajı düzeltildi.** Kullanıcı kalıcı kontrol ve yanıltıcı Ctrl+C
mesajının düzeltme planını onayladı. Üretimde yalnız bu mesaj değişti;
toplama → sonuç kaydı → kapanış → özet sırası, API/şema ve çıkış kodları korundu.
Kapanış sonrası özet/bağlantı hatasında tur `completed`, komut çıkışı 1;
Ctrl+C'de tur yine `completed`, çıkış 130. Yeni mesaj tamamlanmış ve yarım
kalmış turu koşullu anlatır; turun kesinlikle `interrupted` olduğunu söylemez.

7 yeni kalıcı sınama eklendi. Yerel özet hatası kontrolü test paketine taşındı;
elle ve zamanlanmış komutlarda SQL hatası, kullanılan bağlantının kontrollü
kapatılması ve Ctrl+C sınandı. Bağımsız bağlantıyla turun bütün alanları,
bitiş zamanı ve yedi sayfa sonucunun bütün sütunları hata öncesiyle eşleşti.
Veritabanı kilidi başka bağlantıdan, dosya kilidi yeniden alınarak doğrulandı;
sonraki normal tur başladı, önceki tamamlanmış turun kayıtları değişmedi.
Zamanlanmış logda hata mesajı/çıkış kodu korundu; mevcut tur ortası kesinti
testleri de geçti. Eski kodda **2 failed, 5 passed**: iki Ctrl+C sınaması
yalnız yanlış mesajı yakaladı, veri koruma kontrolleri zaten güvenliydi.

Son tam test **804 passed**, 0 atlandı/xfail, 41,35 sn; 226 PostgreSQL testi
yalnız `fiyat_takip_test`. Black 44 dosyada, Flake8 tek işçiyle temiz.
Gerçek DB'ye erişim/yazım ve canlı site komutu yapılmadı; katalog, ayarlar,
uygulanmış migration, toplama/veritabanı servisleri ve zamanlayıcı dosyaları
değişmedi. Canlı turda bu hataların görüldüğü iddia edilmez. Kullanıcı
commit/push işlemini onayladı; `ea4248e` gönderildi, aynı SHA için
CI 37625155724 yeşil.

**7 Ekim bakım 7: kontrol edildi ve mevcut davranış kabul edildi.** Kullanıcı
kontrol/kalıcı test planını onayladı; üretim davranışının ve hata çıktılarının
korunmasını seçti. Scraper nesne kurup olağan yükleme/kurma hatasını `plugin`
yapar, asıl hata nedenini korur; keşif sınıf döndürür, nesne keşif akışında
kurulur ve yükleme/kurma hatası taramayı durdurur. Geçersiz anahtar içe
aktarmadan reddedilir; eksik modül/sınıf, yanlış taban sınıfı, soyut sınıf,
yükleme ve kurucu hataları ile Ctrl+C kontrol edildi. Ctrl+C normal eklenti
hatasına çevrilmez.

28 yeni kalıcı sınama eklendi; mevcut sınıf ve hata nedeni kontrolleri de
güçlendirildi. Scraper tarafında gerçek factory ve sahte sınıflarla elle ve
zamanlanmış turda 3 `error/plugin`, 4 fiyat kaydı, `completed`, çıkış 2,
kurulan nesnelerin kapanışı ve iki kilit doğrulandı. Sonraki normal tur
başladı, önceki turun bütün alanları/sonuçları aynı kaldı. Keşifte ilk adaptör
tamamlanıp kapandıktan sonra ikinci adaptörün yükleme/kurulum hataları
elle/zamanlanmış girişlerde sınandı; diğer hedeflere geçilmedi, katalog ve
önceki rapor korundu, yeni sonuç raporu yazılmadı. Dosya kilidi bırakıldı;
ardından iki hedef/iki platformun normal sahte keşfi tamamlandı.

Keşifte bilinen hatalar açıklamalı çıkış 1; beklenmeyen `RuntimeError`/`TypeError`
elle yukarı iletilir, zamanlanmış girişte ayrıntı loga yazılıp çıkış 1 olur.
Keşif kurulumundaki Ctrl+C iki girişte de yukarı iletilir; zamanlanmış logda
başlangıç kalır, normal çıkış satırı yazılmaz. Bu mevcut davranış kabul edildi,
yeni mesaj veya ortak yükleyici eklenmedi; teknik belgede açıklandı.

Hedefli **43 passed**, 0 atlandı, 367 seçilmedi (2,17 sn). Son tam test
**832 passed**, 0 atlandı/xfail, 44,56 sn; 228 PostgreSQL testi yalnız
`fiyat_takip_test`. Black 44 dosyada ve Flake8 tek işçiyle temiz. Testler
mevcut üretim kodunda geçti; hata düzeltmesi iddiası veya başarısız eski-kod
regresyonu yok. Üretim/ayar/zamanlayıcıya ait 36 takip edilen dosyanın bayt
parmak izleri başlangıçla eşleşti; gerçek DB'ye erişim/yazım ve canlı site
komutu yapılmadı. Yedi bakım maddesinin kontrol/düzeltmesi tamamlandı;
Kullanıcı bakım 7'nin commit/push işlemini onayladı. Cimri Adım 9 ve yeni özellikler başlamadı.

Onaylanan bakım sırası ve durum (her adımdan sonra sonuç anlatılıp durulur):

| Bakım maddesi | Durum |
|---|---|
| 1. HTTP 8 MB indirme sınırı | ✅ Kod ve test tamamlandı; kullanıcı commit/push işlemini onayladı. Gerçek turda henüz görülmedi. |
| 2. Trendyol varyant / Hepsiburada canonical adresi | ✅ Önleyici düzeltme uygulandı (7 Ekim, bu maddeye ayrı kullanıcı istisnası): TY adres yolu/kaynak/sayfa kimliği doğrulanıyor; HB canonical tam SKU eşitliği, farklıysa özgün adres korunuyor. Gerçek uyuşmazlık görülmedi. 31 yeni sınama; 758 passed/0 atlandı/xfail, Black/Flake8 temiz. Kayıtlı 6 TY/24 HB aday ve 12 model reddi korundu. Kullanıcı commit/push işlemini onayladı; ardından 5 → 6 → 7 ayrı ilerleyecek. |
| 3. Türkçe ekli aksesuar adları | ✅ Düzeltildi: üç kayıtlı yazım için dar başlık/kategori kuralı; model, başlık/yapısal kapasite ve birden çok ad sınandı, 21 kayıtlı telefonun kabulü korundu. 652 test geçti, atlanan/xfail yok. Kullanıcı commit/push işlemini onayladı. |
| 4. Hepsiburada çoklu varyant listesi | ✅ Önleyici düzeltme uygulandı (7 Ekim, yalnız bu madde için kullanıcı istisnası): ortak SKU kapasite/renk doğrulaması; çelişkide identity, eşdeğer/eksik alan ve başlık yedeği korunuyor. 75 yeni sınama, toplam 727 geçti/0 atlandı/xfail. Gerçek kaynakta çelişki görülmedi; 24 adayın bilgileri ve 12 diğer modelin reddi korundu. Kullanıcı commit/push işlemini onayladı. |
| 5. Beş adres kimliği kuralı | ✅ Önleyici düzeltme uygulandı (7 Ekim, bu maddeye ayrı kullanıcı istisnası): beş tüketici ortak ürün yolu kimliği kullanıyor; sorunlu TY fiyat seçimi ve HB sorgu SKU'su reddi kapandı. 334 katalog/333 farklı aday kimliği korundu. 39 yeni sınama; 797 passed/0 atlandı/xfail (219 PostgreSQL), Black/Flake8 temiz. Gerçek uyuşmazlık görülmedi. ac9c6b6 push/aynı SHA için CI 37616987979 yeşil. |
| 6. Tur sonu özet sorgusu | ✅ Veri koruması kontrol edildi, mevcut davranış kabul edildi; kesinti mesajı düzeltildi (7 Ekim). SQL hatası/bağlantı kapanması/Ctrl+C elle-zamanlanmış girişlerde sınandı; completed tur, bütün kayıtlar, iki kilit ve sonraki tur korundu. Çıkışlar 1/130 değişmedi. 7 yeni sınama; 804 passed/0 atlandı/xfail (226 PostgreSQL), Black/Flake8 temiz. ea4248e push/aynı SHA için CI 37625155724 yeşil. |
| 7. İki eklenti yükleyicisi | ✅ Kontrol edildi ve mevcut davranış kabul edildi (7 Ekim, kullanıcı onayı). Geçerli/eksik/yanlış/soyut sınıf, içe aktarma/kurulum hatası ve Ctrl+C; elle/zamanlanmış toplama-keşif kayıtları, dosyalar, loglar, kapanışlar, kilitler ve sonraki normal çalışma doğrulandı. Farklı sözleşmeler korundu; üretim kodu değişmedi. 28 yeni sınama; 832 passed/0 atlandı/xfail (228 PostgreSQL), Black/Flake8 temiz. Kullanıcı commit/push işlemini onayladı. |

- 29 Eylül incelemesinde kapandı: test kapsamı maddeleri (Trendyol Kritik Stok,
  keşif CLI çıkış kodları, dry-run'ın kataloğa yazmaması, uyarı türleri, HTTP
  yönlendirme/yeniden deneme), ölü kod (etkisiz `except FetchError: raise`,
  erişilmez satır, tekrarlanan `_seller_rating`) ve hata kodu tablosu
  (docs/teknik.md "Hata kodları"). Regex'lerdeki `_` bilerek kaldı: tam
  genişlikli "＿" gibi nadir karakterler `normalize` sonrası yine `_` olur.

### Cimri Adım 9 yeniden kontrolü (7 Ekim araştırması; 8 Ekim uygulama durumu)

Web araştırmasında [Xiaomi 14T Pro sayfasında](https://www.cimri.com/cep-telefonlari/en-ucuz-xiaomi-14t-pro-fiyatlari,a2372365900)
fiyat analizi gösterilmedi. [Galaxy S24 sayfasında](https://www.cimri.com/cep-telefonlari/en-ucuz-samsung-galaxy-s24-5g-256gb-8gb-ram-fiyatlari,a2305983921)
29 Eylül fiyatı yerel rapordan farklı göründü. Web görünümü, API'nin güncel
cevabı veya bütün serinin değiştiği şeklinde yorumlanmaz; bu nedenle üç ürünün
yeni ham HTML/JSON kontrolü gerekti, 8 Ekim sonucu aşağıdadır. Kopyalama/işleme koşulları tekrar incelendi;
bir defalık aktarım kararı kullanım izni olarak sunulmaz.

9.1 yerel alım aracı hazır; ilk üç eşleştirme mevcut gerçek araştırma
kayıtlarına dayanır. 8 Ekim yeni üç yanıt incelendi; aşağıdaki kaynak
sınırı kullanıcı kararıyla ele alındı. 8 Ekim devamında 59 ürünün 57'sinin
ana adresi web araştırmasıyla eşleştirildi. 10:49–10:58 alımında 53 geçmiş
kabul edildi, dört üründe tablo/grafik fiyatı çelişti. Galaxy S25 512 GB ve Redmi Note 14 Pro 5G 256 GB için doğru
ana adres doğrulanamadı, kaynakta olmadıkları iddia edilmez. Veritabanı
tablosu ve 004 henüz yok.

**8 Ekim 09:24–09:25 pilot alım (kullanıcı çalıştırdı):**
`data/market_history/pilot_20261008_092438_295/report.json` çıkış 2.
iPhone 16 128 GB ve Galaxy S24 256 GB: 365’er nokta,
2025-10-09–2026-10-08, eksik fiyat 0, 90’ar tablo eşleşmesi. Xiaomi
14T Pro 256 GB grafiğinde 2–5 Ekim için dört sayısal sıfır var; bu tarihler
HTML fiyat tablosunda yok. Kalan 361 fiyat pozitif, mevcut 86 tablo satırı
grafikle eşleşiyor. İlk alım pozitif fiyat kuralıyla Xiaomi’yi `parse` olarak
reddetti; ürün kimlikleri ve altı dosyanın parmak izi yeniden doğrulandı.

**Aynı oturumdaki kullanıcı kararı ve dar düzeltme:** Grafik sıfırı, aynı
tarihte tabloda fiyat yoksa eksik değer (`null`) olarak ele alınıyor;
tablo fiyatı varsa çelişki reddediliyor. Ham yanıt değiştirilmez, negatif
ve bozuk fiyatlar kabul edilmez. Bu bir kaynak yorumudur; eksikliğin nedeni
ve sıfırın resmî API anlamı doğrulandı denmez. Eski TL araştırma aracının
sıfırı reddeden sözleşmesi korunur. Kayıtlı yeni yanıtlar ağsız yeniden
doğrulandı: 1.095 nokta, dört eksik gün, 266 tablo eşleşmesi; iPhone/Samsung
kayıtları aynı kaldı. İlk rapor ve ham dosyalar değiştirilmedi; DB’ye yazılmadı.
12 yeni kalıcı testin altısı eski kodda başarısız, altı koruma testi başarılıydı.
Son paket 929 passed, 0 atlandı/xfail, 228 PostgreSQL yalnız fiyat_takip_test;
Black/Flake8 temiz. 9.1 kapanmadı; katalog alımının sonucu aşağıdadır.

**8 Ekim eşleştirme araştırması:** `config/market_history.json` üçten 57
ana adrese genişletildi; ilk üç adres/kimlik korundu. 57 görünen başlığın
tamamı mevcut model/kapasite kontrolünden geçti. Araştırma anında gömülü
sayfa kimliği ve grafik erişimi yalnız üç pilotta kontrol edilmişti;
ardından 57 ürünün tamamının yanıtı alındı (sonuç aşağıda). Yerel araştırma izi:
`data/market_history/mapping_research_20261008_073732.json`.
İki açık anahtar `samsung_galaxy_s25_512gb` ve
`xiaomi_redmi_note_14_pro_5g_256gb`; başka model/kapasite bunların yerine
konmadı. Redmi Note 14 Pro 4G'nin 256/512 GB sayfalarında ağ özelliği 4G,
5G 512 GB ayrı sayfa; POCO marka etiketi korundu (kaynaklar teknik belgede).
Kod/kimlik kuralları, katalog ve migration değişmedi. İki eşleştirme eksik
olduğundan katalog komutu 57 başarıda da çıkış 2 verir; gerçek alımda ayrıca
dört ürünün fiyat uyuşmazlığı görüldü. 9.2'ye geçilmedi.

**8 Ekim 10:49:37–10:58:07 katalog alımı (kullanıcı):**
`data/market_history/katalog_20261008_104936_277/report.json`, çıkış 2.
53 kabul edilmiş geçmiş, dört fiyat uyuşmazlığı, iki açık eşleştirme;
denenmeden kalan yok. 57 üründe üçer HTTP denemesi (171), kimlik/HTTP hatası
yok. 114 kaynak dosyasının parmak izi ve 57 sayfa/API kimliği ağsız yeniden
doğrulandı. 53 geçmişin tarih/kuruş değerleri bağımsız hesapla da aynı:
her biri 365 nokta (2025-10-09–2026-10-08), toplam 19.345 nokta,
18.792 pozitif fiyat ve 14 üründe 553 eksik değer. Bunların hepsi grafik
sıfırlarından gelir; 4.413 tablo satırı eşleşti, eksiklik nedeni bilinmiyor.

Dört üründe yalnız 2026-10-08 fiyatı farklı; diğer 89 ortak tablo satırı
aynı. Tablo / grafik: iPhone 16 Pro Max 512 GB 159.000 / 114.999 TL,
Galaxy S24 256 GB 44.719,29 / 44.160 TL, Galaxy S24 Ultra 512 GB
73.304 / 73.920 TL, Redmi Note 13 Pro 4G 512 GB 24.910,01 / 21.999 TL.
Kaynağın neden farklı fiyat döndürdüğü kanıtlanmadı. Onaylanan çelişki
reddi çalıştı; hata geçiştirilmedi, bugünün fiyatı atılmadı ve kaynaklardan
biri seçilmedi. Ham kanıt korundu; bu dört ürünün kabul edilmiş geçmişi yok.
Yalnız dört ürünün bir kez daha alımı istendi; sonucu aşağıdadır.
Eski 53 ürünün tekrar alınması gerekmiyor. Bu oturumda kod değişmedi,
tam testler yeniden çalıştırılmadı (son sonuç 929 passed / 0 atlandı).
Belgeler güncellendi; 9.1 kapanmadı, 9.2/004/aktarım başlamadı.

**8 Ekim 11:12:45–11:13:18 tekrar (kullanıcı):**
`data/market_history/tekrar_20261008_111245_044/report.json`, dört hata,
12 HTTP denemesi, çıkış 2. Önceki ve yeni alımın toplam 16 dosya parmak izi
doğrulandı. Dört grafik JSON'u önceki alımla bayt düzeyinde aynı; HTML
dosyaları değişse de kimlikler ve 90'ar tablo fiyatı aynı. Her üründe
365 pozitif grafik noktası ve 89 eşleşen tablo satırı var; yalnız 8 Ekim'in
yukarıdaki fiyat farkları sürüyor. Kaynak uyuşmazlığının nedeni bilinmiyor;
aynı komutun gerekçesiz tekrarı önerilmiyor. Mevcut kabul 53 ürün, dört
ret ve iki açık eşleştirme olarak kaldı.

**Kullanıcı ekran kontrolü sonrası düzeltme (8 Ekim):** Kullanıcı dört
ürünün tarayıcıdaki grafik ve tablosunun uyuştuğunu bildirdi; S24 Ultra
512 GB'da 73.920 TL, diğer üçünde önceki tablo değerleri görülüyor. Agent'ın
ham API yanıtını ekranda çizilen grafikle aynı kabul etmesi doğrulanmamıştı.
Kaydedilmiş HTML günlük dizisi ile ayrı API yanıtında fark gerçek; ekranda
iki görünümün çeliştiği iddiası çıkarılamaz. Aynı tarih kontrolü soruldu,
cevabı bekleniyor. Yeni fiyat kuralı onaylanmış değildir.

Dört HTML'de bugünkü tablo değeri sayfanın en ucuz teklif fiyatıyla aynı.
Görünen tablo yalnız değişim günlerini gösteriyor (S24: 7 Ekim; S24 Ultra:
5 Ekim son satır); günlük gömülü dizide 8 Ekim var. Grafiğin API üzerinde
hangi dönüşümü yaptığı bu ilk incelemede henüz bilinmiyordu. **Alım gününü null yapma önerisi
geri çekildi; uygulanmadı.** Kullanıcı 13:04'te kayıtlı HTML'nin işaret ettiği
iki JavaScript dosyasını aldı; çıkış 0, iki HTTP isteği. Kaynak:
`data/market_history/frontend_20261008_130454_461756/index.json`.
İki dosyanın parmak izi doğrulandı. Metin incelemesi, `priceHistoryWrapper`
bölümünün grafik modülünü (27401) sonradan yüklenen 7401 ve 1657 numaralı
iki dosyadan aldığını gösterdi; fiyat dönüşümü henüz görülmedi. Bu dosyaların
adresleri `product.js` içindeki yükleme tablosundan çıkarıldı, tahmin edilmedi.
Web aracı bunları da açamadı; `.scratch/cimri_frontend_check.py` yalnız bu
iki ek dosyayı yeni klasöre alacak şekilde güncellendi ve ağsız sınandı.
İndirilen JavaScript çalıştırılmadı; üretim/test kodu değişmedi.
53 kabul/dört ret/iki açık eşleştirme, kaynak dosyaları ve gerçek DB korunur.
9.1 açık; 9.2'ye geçilmedi.

**13:12 grafik kaynağı sonucu (8 Ekim):** Kullanıcının
`data/market_history/frontend_20261008_131242_210133/` alımı iki HTTP isteğiyle
başarılı; iki dosyanın SHA-256 değeri doğru. `chart_7401.js` içindeki 27401
modülü, teklif varsa API'nin ilk fiyatını `product.offers[0].price` ile
değiştiriyor; diğer günler API'den kalıyor. Tablo HTML dizisini kullanıyor.
Grafik tarihi tarayıcının gününden geriye sayılıyor; API `lastDay` alanı bu
bileşende kullanılmıyor. Kayıtlı 57 üründe `lastDay` ve alımın İstanbul günü
aynı (8 Ekim). İlk teklif verisinin HTML'den geldiği `product.js` içindeki
`__OCTOPUS_DATA__` → `window.__NEXT_DATA__` atamasıyla da doğrulandı.

Yalnız bellekte aynı ilk fiyat dönüşümüyle 57 ürün mevcut tablo kontrolünden
geçti: 20.805 nokta, 20.252 fiyat, 553 eksik değer ve 4.773 tablo eşleşmesi.
Dört ret çözülüyor. Önceden kabul edilen 53 üründen 52'sinin çıktısı tamamen
aynı; S24 Ultra 1 TB'nin yalnız 8 Ekim fiyatı 85.680 → 86.220 TL oluyor.
Bu ürünün tablosu 7 Ekim'de bitiyor; eski kontrol bugünkü fiyatı kapsamıyordu.
Dört ürünün tekrar alımında da 360 tablo satırı eşleşiyor; ilk üç pilotun
sonucu değişmiyor. Araştırma izi aynı klasörde `offline_analysis.json`.
İndirilen JS çalıştırılmadı; raporlar/ham yanıtlar ve üretim kodu değişmedi.
**Bu sonuç yeni başarılı alım değildir:** mevcut rapor hâlâ 53 kabul/dört ret.
Kullanıcının sonradan gördüğü S24 Ultra 512 GB 73.920 TL ile kayıt anındaki
73.304 TL farkının zamanı/nedeni bu dosyalarla kanıtlanamaz.

**Dar düzeltme planı — kullanıcı “uygula” onayıyla uygulandı (8 Ekim):**

1. Yeni kuruş alımında, kimliği doğrulanmış HTML'nin ilk teklif fiyatını
   kaynakta görülen biçimde yalnız bugünkü nokta için kullan. Diğer fiyatları,
   sıfır/eksik değer kuralını ve kimlik doğrulamasını koru; bozuk fiyatları
   dönüşümün arkasına saklama. İlk teklif yoksa mevcut API davranışı sürsün.
2. Tarihleri mevcut API `lastDay` alanından üretmeye devam et. Güncel teklif
   kullanılırken API tarihi kayıtlı alımın İstanbul günüyle eşleşsin;
   gün sınırı veya eski API yanıtında ürün reddedilsin. Yeniden doğrulama
   çalıştırıldığı günün saatini değil, kayıtlı alınma zamanını kullansın.
3. Tabloyla bütün ortak günler yine birebir karşılaştırılsın. Bugünkü tablo
   satırı yoksa bu sınır raporda açıkça yer alsın. Ham API fiyatı, kullanılan
   ilk teklif fiyatı, tarih ve uygulanan kaynak kuralı raporda izlenebilsin;
   özgün HTML/API ve eski raporlar değiştirilmesin.
4. Dört ret ve S24 Ultra 1 TB için küçük gerçek örneklerden regresyon ekle;
   önce eski kodda başarısızlığı göster. Değişmeyen 52 ürün, önceki günler,
   eksik/geçersiz teklif, tarih uyuşmazlığı ve çözülmeyen tablo çelişkisini
   sına. Eski TL araştırma sözleşmesini koru.
5. Bütün pytest/Black/Flake8 çalışsın; PostgreSQL yalnız `_test`, atlananlar
   bildirilsin. Kayıtlı 57 ürün yeni kuralla ağsız yeniden kontrol edilsin.
   Sonuç ve dar canlı doğrulama komutu kullanıcıya sunulsun; yeni alımı
   kullanıcı çalıştırsın. Commit/push ayrı onayla; 9.2'ye geçilmesin.

**Uygulama ve doğrulama sonucu:** İlk teklif dönüşümü yeni kuruş alımına
eklendi. Sayfa isteği başlangıcı ve API bitişi UTC kaydediliyor; ilk teklif
için İstanbul günü ve API `lastDay` eşitliği zorunlu. Ham API fiyatı önce
doğrulanıyor; bugünkü sıfır/null ilk teklifle doldurulmuyor, `parse` kalıyor.
Raporda ham/ilk teklif/etkin fiyat, kaynak kuralı, değişim ve son günün tablo
kontrolü ayrı. Son gün tablo satırı yoksa komut bunu belirtiyor. İlk teklif
yoksa API korunuyor. Eski TL araştırması, HTTP bütçesi/kilit ve çıkışlar aynı.

Beş gerçek regresyon eski kodda başarısızdı (dört ret + 1 TB son fiyatı).
100 ek sınama ile son tam sonuç **1029 passed, 0 skipped/xfail, 54,20 sn**;
228 PostgreSQL yalnız `fiyat_takip_test`, Black 49 dosya ve Flake8 temiz.
İlk tam koşuda beş teklifsiz örneğin test beklentisindeki eksik kontrol
düzeltildi; üretim davranışı API'yi zaten koruyordu. Son koşu tamamı geçti.
57 tam kayıt yeni kodla ve bağımsız tarih/Decimal hesabıyla doğrulandı:
20.805 nokta/20.252 fiyat/553 eksik/4.773 tablo eşleşmesi. 52 eski ürünün
bütün noktaları aynı; S24 Ultra 1 TB'de yalnız 8 Ekim değişti.
İz: `data/market_history/frontend_20261008_131242_210133/implemented_validation.json`.
Eski rapor/ham dosyalar değiştirilmedi; bu bir yeni canlı alım değildir.

Bu düzeltmenin dosyaları: `app/market_history/cimri.py`, `capture.py`,
`__main__.py`; `tests/test_market_history.py`,
`tests/fixtures/cimri_recorded_samples.json`; `pyproject.toml` (İstanbul
saat diliminin Windows'ta da bulunması için açık `tzdata` bağımlılığı);
README, teknik belge, bu plan ve yerel DEVAM. Gerçek DB, katalog,
migration'lar ve zamanlayıcı değişmedi. Dört eski ret ile S24 Ultra 1 TB
için canlı teyit tamamlandı; 9.1 için kullanıcı commit/push onayı verdi; aynı SHA CI doğrulanacak.
9.1 commit mesajı önerisi: **“Adım 9.1: Cimri geçmişinin doğrulanmış yerel
alımını ve güncel fiyat dönüşümünü hazırla”**. Kullanıcı 8 Ekim tarihinde
commit/push işlemini onayladı; aynı commit için CI doğrulaması yapılacak.
9.2'ye geçilmedi.

**Canlı teyit (8 Ekim 13:51:43–13:52:25, kullanıcı):**
`data/market_history/duzeltme_20261008_135142_423/report.json`, beş
`captured`, 15 HTTP denemesi ve çıkış 0. On kaynak parmak izi,
katalog/eşleştirme, kimlikler ve alım tarihleri doğrulandı; rapor hem yeni
ayrıştırıcıyla hem bağımsız tarih/Decimal hesabıyla kontrol edildi.
1.825 nokta/1.754 fiyat/71 eksik/450 tablo eşleşmesi; son gün beşinde de
tabloyla eşleşti. S24 Ultra 1 TB'deki 71 eksik tarih ilk kayıttakiyle aynı.
Yeni ilk teklif fiyatı 85.680 TL; 512 GB sürümünde 73.920 TL. Eski
alımın rakamları yeni alıma taşınmadı. Dört API ilk alımla aynı; S24 256 GB
API yanıtı değişmiş, yeni son fiyatı ilk teklifle doğrulandı.
İz: aynı klasörde `verification.json`; kaynaklar ve eski raporlar değişmedi.

**9.1 uygulama/canlı doğrulaması tamamlandı; kullanıcı 8 Ekim tarihinde commit/push onayı verdi.**
Yeni kodla 57 kayıt ağsız doğrulandı ve sorunlu beş ürün canlıda teyit edildi.
Galaxy S25 512 GB ve Redmi Note14 Pro 5G 256 GB eşleştirmeleri hâlâ açık;
bu eksiklik raporlandı, kapsam/aktarım kapanışı 9.3'ün işi. 57 ürün tek yeni
alım raporu gibi sunulmaz; farklı alımlar korunur, aktarım girdilerinin seçimi
9.2/9.3'te doğrulanır. Bu oturum yalnız inceleme/belge güncellemesi; kod
değişmedi, tam testler tekrar edilmedi. Son 1029 passed/0 atlandı ve
Black/Flake8 sonucu geçerli. Kullanıcı commit/push onayı verdi; aynı SHA CI
doğrulaması gönderim akışının parçasıdır. Güncel commit ve CI kaydı yerel
DEVAM notunda tutulur; yeni alt adıma geçilmedi.

### Adım 9.2 aktarım altyapısı (8 Ekim; tamamlandı)

Kullanıcı ayrıntılı planı onayladı. Uygulama `.scratch/market_history_9_2`
kopyasında tamamlandı ve test edildi. `c64d14f` gönderildi;
[aynı SHA için CI 37777433986 başarılı](https://github.com/Emir-Ars/Urun-indirim-takip/actions/runs/37777433986).
Ana klasöre geçiş tamamlandı. Kullanıcı 004’ü **2026-10-08 12:35:53 UTC**’de
uyguladı. Salt okunur gerçek DB kontrolü: 001–004 ad/parmak izi uyumlu,
bekleyen migration yok; `market_history` boş ve üç koruma etkin. Katalog,
001–003 dosyaları ve zamanlayıcılar korunuyor. Bekleyen şema nedeniyle tur
başlamasını engelleyen durum kalktı; sonraki turun canlı sonucu henüz bilinmiyor.

`import <klasör>` ve `--dry-run`: sonlandırılmış raporun yalnız `captured`
kayıtlarını SHA-256, kayıtlı UTC zamanları, katalog kimliği ve aynı kaynak
baytlarından yeniden hesaplanan kimlik/geçmiş/özetle doğrular. Eski raporlara
uyumluluk eklenmez; 9.3'te güncel araçla yeni toplu alım yapılacak.

004 ayrı `market_history` tablosu ve korumalarını ekler: ürün/kaynak/gün
tekil, fiyat pozitif bigint veya NULL, Cimri kimliği/adresi, UTC alım zamanı,
HTML/API/rapor parmak izleri saklanır. Güncelleme/silme/TRUNCATE reddedilir.
Ürün başına transaction ve ON CONFLICT sonrası tekrar karşılaştırma vardır.
İlk kayıt korunur; NULL–NULL aynıdır, NULL–fiyat veya farklı Cimri kimliği
o ürünün bütün yeni günlerini reddettirir. Önizleme READ ONLY/REPEATABLE READ;
INSERT/rollback yöntemi yok. Ortak dosya ve tur kilidi kullanılır. COMMIT
sonucu belirsizse bildirilir; yeniden çalıştırma kayıt çoğaltmaz. Çıkışlar
0/2/1/3/130 planla aynı. Ayrıntı: docs/teknik.md, Adım 9.2.

**Kanıt:** 161 yeni test (48 PostgreSQL); tam paket **1190 passed**, 0
atlandı/xfail, 73,10 sn. Toplam 276 PostgreSQL testi yalnız `fiyat_takip_test`;
Black 52 dosya ve Flake8 temiz. İlk sandbox çalışmasında Windows geçici klasör
izni sorunu çıktı; uygun izinle çalıştırıldı. Yeni tarih çıktı testindeki
örnek API tarihi düzeltildikten sonra tam paket yeniden geçti. Testler canlı
siteye çıkmadı. 001–003 → 004 geçişinde eski tur/görünüm sonuçları korundu;
aktarımı ve kesintiyi izleyen normal sahte toplama turları başarılı.

Yeni okuyucu kayıtlı `duzeltme_20261008_135142_423` girdisinde 5 ürün,
10 kaynak dosyası ve 1825 noktayı kabul etti (71 NULL). Eski katalog raporunda
53 başarılı kaydın yeni zaman/özet alanları eksik; dördü hata, ikisi
eşleştirmesiz: 59 kayıt da aktarım adayı olmadı. Kaynaklar değiştirilmedi;
bu ağsız kontrolde veritabanına bağlanılmadı. Yerel iz:
`.scratch/market_history_9_2_offline_check.json`.

**Durma noktası:** 9.2 kod/test, commit/push, CI, ana geçiş ve gerçek
migration teyidiyle tamamlandı. Gerçek geçmiş aktarımı ve yeni toplu alım 9.3’te;
iki açık eşleştirme orada ele alınacak. 9.3'e geçilmedi.

### Adım 9.3 gerçek aktarım ve kapsam kapanışı (8 Ekim; tamamlandı)

Onaylanan sıra: yeni toplu alım → rapor incelemesi → READ ONLY önizleme →
kullanıcının gerçek aktarımı → bağımsız okuma ve aynı girdinin tekrar aktarımı.
Her durakta sonuç kullanıcıya gösterilir; gerçek yazma komutlarını kullanıcı
çalıştırır. Yeni komut/API/migration eklenmez; eski raporlar aktarım girdisi
olarak kullanılmaz, kaynak dosyaları korunur.

İlk hazırlık tamam: 59 etkin ürünün katalog/DB kimlikleri eşleşiyor,
001–004 güncel, `market_history` satır sayısı 0 (READ ONLY kontrol).
57 eşleştirme mevcut. Galaxy S25 512 GB için bulunan Plus 512 GB,
Redmi Note 14 Pro 5G 256 GB için bulunan 512 GB sayfaları farklı kimlikte;
eşleştirmeye alınmadı. İki ürün için **eşleştirme doğrulanamadı**;
Cimri’de bulunmadıkları sonucu çıkarılmadı. Planlama araştırması ve 59 ürünün
yeni alım öncesi durumu yerelde kaydedildi:
`data/market_history/mapping_research_9_3_20261008_125156_159288.json`.
Kod, katalog, eşleştirme dosyası ve uygulanmış migration dosyaları değişmedi.
8 Ekim 15:49’da iki zamanlayıcı görevi Ready idi; kullanıcı yeni alımı
15:59–16:08 arasında gerçekleştirdi.

Rapor sonrası bütün kaynak hash’leri, kimlikler, tarihler, kuruş fiyatları,
NULL ve tablo karşılaştırması yeniden doğrulanır. Geçici ağ hatasında yalnız
başarısız ürünlere bir ek alım yapılabilir; kimlik/ayrıştırma hatası kör tekrar
edilmez, blocked önce değerlendirilir. Başarılı ürünler yeniden alınmaz;
raporlar elle değiştirilmez veya birleştirilmez. Her ürün için alım klasörü ve
rapor hash’i seçilir; ana alımı yalnız eksikleri tamamlayan ayrı girdiler izler.

Önizleme sonucu ve bağımsız okumada değişmeyen DB gösterildikten sonra gerçek
aktarım komutu kullanıcıya verilir. Sonrasında bütün satır alanları
(ürün/kaynak/kimlik/adres/gün/kuruş/zaman ve üç hash), ürün sayıları/tarih
aralıkları/NULL sayıları raporla karşılaştırılır. Kullanıcı aynı klasörleri
tekrar aktarır: 0 yeni kayıt ve ilk kaynak bilgilerinin korunması beklenir.
Atlanan ürünler varsa çıkış 2 tek başına başarısız aktarım sayılmaz.

Kapanış: 59 ürün aktarılmış veya gerekçeli eksik olarak raporlanmış, kabul
edilen bütün satırlar eşleşmiş, tekrar aktarım çoğaltmamış ve çözülmemiş araç/DB
hatası kalmamış olmalı. Klasör/hash referanslı tarihli yerel kapanış raporu
hazırlanır; ham veriler Git’e gönderilmez. Kod/test değişirse dar düzeltme
ayrıca planlanır; tam pytest/Black/Flake8 ve yalnız `_test` DB kullanılır.
Kod değişmezse son 1190 testlik sonuç yeni gerçek kontrollerden ayrı belirtilir.

**Yeni alımın doğrulaması (8 Ekim 15:59–16:08, kullanıcı):**
`data/market_history/aktarim_20261008_155952_339/report.json`; rapor SHA-256:
`20343f1d2d3af544b59c696a0b9f62c4c01bbe87f53f973630f214b0854f0844`.
59 ürün: **57 captured, iki unmapped**, 171 HTTP denemesi; hata/denenmemiş ürün
yok. Çıkış 2 yalnız Galaxy S25 512 GB ve Redmi Note 14 Pro 5G 256 GB
eşleştirmelerinin eksikliğinden. Ek alım gerekmiyor.

114 kaynak dosyasının hash’i, güncel eşleştirme/katalog kimlikleri ve bütün
hesaplanmış fiyat/özet alanları mevcut ağsız okuyucuyla yeniden doğrulandı.
Rapor + kaynak dosyalarının 115 hash’i işlem öncesi/sonrası aynı.
Her üründe 365 nokta, 2025-10-09–2026-10-08: toplam **20.805 nokta,
20.252 fiyat, 553 NULL**. Tabloda ortak 4.773 ürün/gün fiyatı eşleşti;
16.032 ürün/gün için tablo satırı yok, bu günler için tablo teyidi iddia edilmez.
52 ürünün son gününde ilk teklif kuralı çalıştı (dokuzunda ham API fiyatından
farklı); beşinde ilk teklif yok, API kuralı kullanıldı ve son günün tablo
satırı da yok: iPhone 15 512 GB, 15 Pro 1 TB, 15 Pro Max 1 TB, 16 Pro 512 GB,
16 Pro 1 TB. Tekrarlanan fiyatlar ayrı günlük gözlem kanıtı sayılmıyor.

57 ürünün tamamı için seçilen aktarım girdisi aynı yeni alım klasörüdür;
eski raporlar seçilmedi. Bağımsız READ ONLY kontrol: 59 ürünün DB kimliği
uyumlu, 001–004 güncel ve market_history hâlâ 0 satır. Önizleme öncesi durum
ve ürün bazında kaynak referansları şu yerel doğrulama kaydında:
`data/market_history/capture_verification_9_3_20261008_131025_927553.json`.
Bu kayıt aktarım/kapanış raporu değildir. Kod/test değişmedi;
1190 testlik önceki sonuç ile bu gerçek dosya doğrulaması ayrı tutuluyor.

**Önizleme doğrulandı (8 Ekim):** Kullanıcının `import --dry-run` çıktısında
57 ürünün her biri 365 eklenecek / 0 aynı; toplam **20.805 eklenecek, 0 aynı,
0 çelişkili ürün, 2 atlanan ürün**, çıkış 2. Atlananlar yalnız iki unmapped
ürün. Rapor SHA-256 aynı; 115 girdi dosyası değişmemiş. Ürün bazında tarih,
NULL, tablo eşleşmesi ve karşılaştırılamayan tarih aralıkları da kayıtla aynı.
Bağımsız 16:48 READ ONLY sorgusu: şema/59 kimlik uyumlu, market_history
önce/sonra 0 satır. Önizlemenin yazmadığı doğrulandı. Yerel kanıt:
`data/market_history/dry_run_verification_9_3_20261008_135103_464459.json`.

**İlk gerçek aktarım doğrulandı (8 Ekim, 16:59 bağımsız kontrol):**
Kullanıcı aynı klasörü aktardı: **20.805 eklendi, 0 aynı, 0 çelişkili ürün,
2 atlanan ürün**, çıkış 2. Atlananlar yalnız iki eşleştirmesiz ürün.
Gerçek DB’ye READ ONLY / REPEATABLE READ bağlantıyla bakıldı: bütün tablodaki
20.805 satırın **10 alanı** doğrulanmış alım verisiyle birebir aynı;
eksik, beklenmeyen veya farklı satır yok. 57 ürün × 365 gün,
20.252 fiyat + 553 NULL, 2025-10-09–2026-10-08; her ürünün sayı/tarih/NULL
özeti de aynı. 59 katalog/DB kimliği uyumlu, 001–004 güncel, 115 alım dosyası
değişmemiş. İlk kayıtların bütün alanlarını kapsayan tekrar kontrolü parmak izi:
`475761674af17e6760a23663de39fcd66013d27204444a173f4849972ad70f35`.
Ürün bazında hash’ler, komut çıktısı ve doğrulama sonucu yerelde:
`data/market_history/import_verification_9_3_20261008_135906_391044.json`.

**Tekrar aktarım ve kapsam kapanışı (8 Ekim, 17:12 bağımsız kontrol):**
Kullanıcı aynı girdiyi tekrar aktardı: **0 eklendi, 20.805 aynı,
0 çelişkili ürün, iki atlanan ürün**, çıkış 2. Bütün 20.805 satırın
10 alanı READ ONLY / REPEATABLE READ sorgularla yeniden kaynakla karşılaştırıldı;
eksik/fazla/farklı satır yok. İlk aktarım ile tekrar sonrası bütün tablo hash’i
ve 57 ürünün ayrı hash’leri aynı; ilk adres, alınma zamanı ve üç kaynak hash’i
korundu. 115 alım dosyası da değişmedi. 553 eksik fiyat NULL kaldı.

**Kapsam 59/59 raporlandı:** 57 ürün aktarıldı ve doğrulandı; Galaxy S25 512 GB
ve Redmi Note 14 Pro 5G 256 GB için eşleştirme doğrulanamadığından kayıt
yazılmadı. Bu iki eksiklik gerekçeli olarak kapatıldı; ürünlerin Cimri’de
bulunmadığı veya 59 ürünün hepsinin aktarılmış olduğu iddia edilmiyor.
Kaynakta tablo satırı olmayan günler ve ayrı günlük gözlem belirsizliği
kapanış raporunda korunuyor. Çözülmemiş araç veya DB hatası yok.

**9.3 ve Adım 9 tamamlandı.** 59 ürünün durumunu, alım klasörü/rapor hash’ini,
araştırma–alım–önizleme–ilk aktarım kanıtlarını ve tekrar kontrolünü içeren
tek tarihli yerel kapanış raporu:
`data/market_history/kapanis_9_3_20261008_141239_175902.json`.
Gerçek alım ve yazma komutlarını kullanıcı çalıştırdı; asistan gerçek DB’ye
yalnız okuma yaptı. Kod/test değişmedi; 1190 testlik önceki sonuç geçerli,
bu adımın gerçek kayıt kontrolleri ondan ayrı tutuluyor.

**Gönderim kararı (8 Ekim):** Kullanıcı kapanış belgelerinin commit/push
işlemini onayladı. Aynı SHA CI sonucu GitHub Actions kaydından izlenir.
9.3 gönderiminde Adım 7 henüz başlamamıştı; ardından aşağıdaki kapanış
kontrolüyle tamamlandı.
Gönderilecek kapanış belgeleri README.md, docs/teknik.md ve proje_plani.md;
DEVAM ve yerel veri/raporlar Git dışında. Commit mesajı:
**Adım 9.3: Cimri geçmişinin gerçek aktarımını ve katalog kapsamını doğrula**.

### Adım 7: veritabanı ve zamanlanmış toplama kapanışı (8 Ekim; tamamlandı)

Kullanıcı kapanış planını onayladı. 19:55 kontrolünde gerçek veritabanına
baştan READ ONLY / REPEATABLE READ bağlantıyla yalnız okuma yapıldı.
Yeni tur, keşif, alım veya aktarım çalıştırılmadı; kod, katalog, şema ve
zamanlayıcılar değişmedi. Bağımsız kontrol kanıtı Git dışındadır:
`data/adim7_kapanis_20261008_165558_563093.json`.

| Kontrol | Doğrulanmış sonuç |
|---|---|
| Şema ve katalog | 001–004 ad/parmak izi uyumlu, bekleyen migration yok. İki platform, 59 ürün ve 334 sayfanın bütün DB alanları katalogla aynı; 332 sayfa etkin. |
| Son fiyat turu | Tur 19, scheduled/completed; 8 Ekim 10:00:01–10:31:03 yerel saat. 332 sonuç: 237 fiyat, 95 Tükendi, 0 hata. Her log satırının kimlik, sonuç, fiyat, satıcı ve stok alanları DB ile birebir aynı; kapanış zamanı kayıtlı. |
| Tur bütünlüğü | 19 tur kayıtlı; süren tur yok. Tamamlanmış turlarda sonuçsuz veya okunma zamanı boş satır yok. |
| Karşılaştırılabilirlik | Son turun 59 ürün satırında sayılar, minimum fiyat/seçilen sayfa ve önceki turun cevap veren sayfa kümeleri bağımsız SQL okumalarıyla doğrulandı; 59’u önceki turla karşılaştırılabilir. |
| Cimri geçmişi | Güncel okuyucu 57 kaynak kaydını yeniden doğruladı. 20.805 satırın 10 alanı alımla birebir aynı; 553 NULL ve ilk kaynak bilgileri korundu. Bütün tablo hash’i 9.3 kapanışıyla aynı, 115 girdi dosyası değişmedi. UPDATE/DELETE/TRUNCATE korumaları etkin. |
| Bakımlar | Yedi bakımın tamamlanmış kod/test veya mevcut davranışı kabul kararları Bölüm 7’de kayıtlı. |
| Otomatik doğrulama | Önceki yerel tam paket: 1190 passed, 0 skipped/xfail; 276 PostgreSQL testi yalnız `_test` DB. Mevcut `2c78af2` için CI 37795271692 yeniden kontrol edildi: pytest/Black/Flake8 başarılı. Bu kapanışta kod değişmediği için pytest yeniden çalıştırılmadı. |

**Aşama 6 ve Adım 0–11 tamamlandı.** Tamamlanma, kabul edilen kaynak/işletim
sınırlarının ortadan kalktığı anlamına gelmez: Hepsiburada araması kısmi;
bilgisayar uyurken veya internet kesildiğinde gözlem kaybı olabilir; iki
Cimri eşleştirmesi doğrulanamadı, NULL fiyatlar doldurulmadı. Kaynak geçmişinin
günlük bağımsız gözlem sıklığı bilinmiyor ve kendi toplama serimize katılmıyor.

**İzleme olarak açık kalanlar:** tur sonu network ikinci okuması incelenen
loglarda henüz çalışmadı; ağsız/DB testleri mevcut. Haftalık keşif ilk kez
4 Ekim’de kendiliğinden başladı, ancak ağ kesintisi nedeniyle kapsamı boş kaldı;
5 Ekim’de aynı scheduled komutu elle çalıştı. Sağlıklı ağla otomatik haftalık
çalışma henüz görülmedi; sonraki fırsat Pazar 11 Ekim 14:00. Bu iki canlı
senaryo için hata oluşturulmayacak veya yalnız gözlem beklemek üzere kapanış
ertelenmeyecek; normal çalışmanın çıktısı geldiğinde durum güncellenecek.

**Gönderim kararı (8 Ekim):** Kullanıcı README.md, docs/teknik.md ve
proje_plani.md için commit/push işlemini onayladı. Aynı yeni commit’in CI
sonucu GitHub Actions kaydından izlenir. Commit mesajı:
**Adım 7: veritabanı ve zamanlanmış toplama aşamasının kapanışını belgele**.
README’nin tanıtım odaklı düzenlenmesi ve teknik belgeyle görev paylaşımının
incelenmesi kapanıştan sonraki ayrı iş; henüz uygulanmadı. FastAPI/Streamlit,
ML ve işletim aşamalarına başlanmadı.

## 8. Açık kararlar

| Konu | Durum |
|---|---|
| Adım 7 kapanışı | **Kullanıcı planı onayladı; uygulama tamamlandı (8 Ekim):** mevcut tur/katalog/şema/Cimri kanıtları salt okunur teyit edildi ve Aşama 6 kapatıldı. Kapanış belge commit/push işlemi kullanıcı tarafından onaylandı; gönderim sonrası aynı SHA CI kontrol edilecek. |
| README ve teknik belgenin görev paylaşımı | **Karar verildi (8 Ekim, kullanıcı):** önce veritabanı kapanışı tamamlanır; ardından ayrı çalışmada README projeyi dışarıdan inceleyenlere tanıtacak şekilde düzenlenir. Çalıştırma/bakım ayrıntıları teknik belgede tutulur; bilgi kaybı olmadan tekrarlar değerlendirilir. Bu kapsamlı düzenleme henüz uygulanmadı; mevcut kapanışta yalnız durum/tutarlılık değişiklikleri yapıldı. |
| Garanti türüne göre ayrım | **Karar verildi (27 Eylül 2026): ayrılmıyor;** yurt dışı sürümler ürün adından tanınıp kapsam dışı bırakılıyor. |
| Veritabanı teknolojisi, veri modeli, çalışma ortamı | **Karar verildi (28 Eylül 2026):** PostgreSQL 17, `psycopg` + ham SQL, kullanıcının bilgisayarı, günde 2 tur; ayrıntı Bölüm 9. SQLite önerisi bırakıldı. |
| Keşfin zamanlanması | **Karar verildi (28 Eylül 2026):** bu aşamada manuel, haftada bir; fiyat turuyla ortak kilit. Otomasyon, veritabanı birkaç hafta sorunsuz çalıştıktan sonra değerlendirilir. Kanıt: 28 Eylül kapanış taramasında tek günde 21 yeni bağlantı çıktı; Hepsiburada genel aramasının ilk 36 kartı her seferinde değişebildiği için tekrar eden keşif kapsamı artırır. **29 Eylül güncellemesi (kullanıcıyla):** haftalık zamanlayıcı değerlendirildi; şimdilik elle devam, **Adım 6 gözlemi bitince (1 Ekim sonrası) otomatikleştirilecek**. Biçim o gün seçilecek: (A) önerilen, görev keşfi deneme modunda çalıştırır ve tarihli rapor bırakır, yeni sayfaları kullanıcı inceleyip tek komutla ekler; 2–3 hafta rapor temiz giderse (B)'ye geçiş değerlendirilir. (B) tam otomatik: yeni sayfalar doğrudan kataloğa girer. B'nin riski: yanlış bir sayfa kataloğa girerse tur onu birkaç saat içinde veritabanına ekler, fiyatları ürünün geçmişine yazılır ve sayfa sonradan yalnız pasife alınabilir; ayrıca `catalog.json` Git'te olduğu için her hafta commit edilmemiş değişiklik birikir. Teknik gereksinimler: keşfe `--scheduled` (log + tarihli rapor + özet satırı; bugün rapor her çalışmada üzerine yazılır); görev tur saatlerinden uzak olmalı (ör. Pazar 14:00, keşif ~50 dk tahmin edilmişti, 5 Ekim'de 34 dk ölçüldü); keşif görevinde kaçan çalışmayı telafi **kapalı** olmalı, yoksa geç açılan bilgisayarda telafi keşfi 22:00 turunu kilitle atlatabilir; keşif çıkış kodu Hepsiburada yüzünden hep 2'dir, özet satırı ayrıca okunmalı. **Karar verildi (1 Ekim 2026, kullanıcı): A seçildi, ekleme komutuyla (A1).** Görev her Pazar 14:00'te keşfi deneme modunda çalıştırır ve tarihli log + rapor + özet satırı bırakır; kaçan çalışmayı telafi etmez. Kullanıcı raporu inceler; yeni bir komut (`--apply-report`) siteye gitmeden **tam olarak incelenen** raporu kataloğa uygular. Gerekçe: bugün yazmanın tek yolu keşfi yeniden çalıştırmaktır ve Hepsiburada'nın ilk 36 kartı değişebildiği için ikinci tarama incelenenden farklı sonuç verebilir. Rapor 2–3 hafta temiz giderse (B)'ye geçiş yeniden değerlendirilir. Uygulama Adım 10'dur ve 5 Ekim'de tamamlandı (Bölüm 9): ilk zamanlanmış çalışma (4 Ekim) internet kesintisi yüzünden boş bitti, elle yapılan tam tarama ve `--apply-report` 5 Ekim'de 7 sayfa ekledi. |
| Piyasa geçmişi kaynağı | **29 Eylül araştırma sonucu:** Cimri üç üründe teknik olarak doğrulandı; Akakçe'nin ilk örneği 403 verdi. O tarihte aktarım kaynağı seçilmedi. **Güncel karar (30 Eylül 2026, kullanıcı; Codex):** ML eğitimi için geçmiş fiyat hareketinin kaynağı Cimri olacak; katalogdaki telefonların mevcut geçmişi bir defa alınacak. Akakçe ve Cimri serileri birleştirilmeyecek, düzenli Cimri toplaması yapılmayacak. Kullanım koşullarına ilişkin önceki bulgu Bölüm 7'de korunur ve aktarım adımında ele alınır. |
| Cimri Adım 9 uygulama sırası | **Karar verildi (7 Ekim 2026, kullanıcı; plan onaylandı):** 9.1 eşleştirme/yerel alım → 9.2 ayrı ağsız aktarım ve yeni 004 → 9.3 katalog kapsamı/gerçek aktarım/kapanış. Önce rapor, sonra ayrı aktarım; aynı ürün/tarihte farklı fiyat veya Cimri kimliği olursa eski kayıt korunur, o ürünün aktarımı durur. İlk aktarımda yeni alım esas; 29 Eylül üç raporu yalnız araştırma/test kanıtı olarak kalır. Her alt adım ayrı durma ve commit/push onayı; gerçek site/DB yazma komutları kullanıcıda. Şu an üç yeni kaynak kontrol edildi, Xiaomi sıfır kuralı ayrı kullanıcı kararıyla düzeltildi. 57 adresin ham alımı incelendi: 53 geçmiş kabul, dört fiyat uyuşmazlığı, iki açık eşleştirme. Dört ürünün ikinci alımında aynı ham veri farkı sürdü; kullanıcı ekranda uyum gördü. Null önerisi geri çekildi; kaynakta ilk teklif dönüşümü doğrulandı. Dar düzeltme kullanıcı onayıyla uygulandı; tarih ve tablo kontrolleri korunuyor, beş ürünün canlı teyidi tamamlandı. 9.1 gönderimi kullanıcı tarafından onaylandı; CI sonucu GitHub Actions kaydından izlenir. 9.2 tamamlandı; aktarım komutu ana projede, 004 gerçek veritabanında kullanıcı tarafından uygulandı ve salt okunur teyit edildi. |
| Cimri Adım 9.3 uygulaması | **Tamamlandı (8 Ekim):** yeni alım, önizleme, kullanıcı gerçek/tekrar aktarımı ve bağımsız satır doğrulaması tamam. 59 ürünün kapsamı: 57 aktarılmış (20.805 kayıt/553 NULL), iki gerekçeli eşleştirme eksik. Tekrar 0 yeni/20.805 aynı; ilk kaynak bilgileri ve dosyalar korundu. Kapanış belgeleri `2c78af2` ile gönderildi; aynı SHA CI 37795271692 başarılı. Ardından Adım 7 de tamamlandı; API/arayüz başlamadı. |
| Cimri aktarım girdisi ve güvenliği | **9.2 tamamlandı ve devreye alındı (8 Ekim):** 9.3’te eşleşen 57 ürün güncel araçla yeniden alındı. Önceki eksik zaman/özet alanları tahmin edilmeyecek. Önizleme gerçekten READ ONLY; her ürün atomik, ilk kayıt korunur, NULL–fiyat farkı çelişkidir. Ortak dosya/tur kilitleri kullanılır. Gerçek ve tekrar aktarım 9.3’te kullanıcı tarafından yapıldı; bağımsız okuma sonucu doğrulandı. |
| Cimri grafik sıfırlarının anlamı | **Karar verildi ve uygulandı (8 Ekim 2026, kullanıcı):** Gerçek Xiaomi yanıtında grafik sıfırı olan dört tarihte tablo fiyatı yok; yeni kuruş alımı bu sıfırları eksik `null` olarak okur. Tabloda fiyat varsa çelişki reddedilir; negatif/bozuk fiyat, ham dosyalar ve eski TL araştırma sözleşmesi korunur. Kaynağın resmî sıfır tanımı olduğu iddia edilmez. |
| Cimri ham geçmiş yanıtı ile ekrandaki grafik | **Kullanıcı onayıyla uygulandı (8 Ekim):** Cimri grafiğinin bugünkü ilk teklif dönüşümü yeni alımda kullanılıyor. API/alım günü, ham fiyat ve tablo eşitliği doğrulanıyor; kaynak raporda açık. Beş regresyon eski kodda başarısızdı, son 1029 test geçti/0 atlandı. 57 tam kayıt yeni kodla ağsız doğrulandı: dört ret çözülüyor, 52 eski ürünün noktaları aynı, S24 Ultra 1 TB yalnız 8 Ekim değişiyor. Eski raporlar korunuyor; beş ürünün canlı teyidi tamam; commit/push onaylandı; CI sonucu GitHub Actions kaydından izlenir. Alım gününü null yapma önerisi uygulanmadı. |
| Cimri geçmişinin bir defalık kaydı ve ML amacı | **Karar verildi (30 Eylül 2026, kullanıcı; Codex):** Aşama 6'ya **Adım 9** eklenir; Adım 4'ten sonra, Adım 7 kapanışından önce yapılır. Veriler aynı PostgreSQL veritabanında ayrı `market_history` tablosunda saklanır. Amaç, erişilebilen bir yıllık geçmiş fiyat hareketini model eğitiminde kullanmaktır. **Gerekçe:** Cimri daha geniş kaynak kapsamına sahip olsa da kullanıcı küçük fiyat farklarını bu amaç için kabul ediyor; öncelik geçmişteki değişimdir. Cimri serisi kendi Hepsiburada/Trendyol gözlemlerimizle aynı ölçüm olarak etiketlenmez. Eğitimin nasıl yapılacağı, mutlak fiyatın mı değişimin mi kullanılacağı ve değerlendirme ayrıntıları ML aşamasında kararlaştırılır. 57 adresin yerel alımı ve 9.1 doğrulaması tamam; 9.2 tablo/aktarım altyapısı ana projede, 004 gerçek veritabanında uygulandı. 9.3 güncel alımıyla 57 ürünün 20.805 geçmiş kaydı gerçek veritabanına aktarıldı ve bağımsız okumayla doğrulandı; tekrar aktarım da ilk kaynak bilgilerini koruyarak doğrulandı; Adım 9 tamamlandı. |
| Tur sonunda yalnız `network` hatası alan sayfalara ikinci geçiş | **Karar verildi (1 Ekim 2026, kullanıcı): yapılacak, tek geçiş. Uygulandı (6 Ekim 2026, Adım 11).** Tasarım kararları (6 Ekim, kullanıcı): ikinci okuma da `network` verirse ilk satır olduğu gibi kalır; ardışık 5 sayfa yine `network` verirse geçiş durur (bağlantı hâlâ yok); tur notuna yalnız sayılar yazılır, sayfa kimlikleri logdadır; 5xx ayrı kod almaz ve `network` olarak yeniden okunur. Kanıt: tur 3'te (28 Eylül) 47 sayfa bağlantı kesintisiyle `network` hatası aldı; son hatadan sonra kalan 154 sayfa cevap verdi, yani tur bitmeden bağlantı geri gelmişti. Tur 7'de (1 Ekim) 1 sayfa uyku sonrası DNS hatası aldı. Yalnız `network` yeniden okunur; `blocked` yeniden denenmez. İkinci okuma, hata satırının üzerine yazılır (tur × sayfa başına tek satır kuralı korunur); tur notu ve log kaç sayfanın düzeldiğini söyler. Yeniden okunamayan sayfa hata olarak kalır. |
| Bulutta çalıştırma (PC açık kalmak zorunda olmasın) | **Deneme kararı (6 Ekim 2026, kullanıcı):** Görev Zamanlayıcı aynen çalışmaya devam eder; bu sürede GitHub Actions'tan canlı okuma denenir (`.github/workflows/bulut-deneme.yml`: elle tetiklenir, zamanlama yok, veritabanı ve gizli anahtar yok; Samsung Galaxy A55 128 GB'ın 4 sayfası, Trendyol ve Hepsiburada). **Gerekçe:** PC uyuyunca veya kapalıyken turlar kaçıyor (2–4 Ekim: 4 tur, ~40 saat boşluk; geri alınamaz). Kod taşınabilir (`filelock`, `psycopg`, standart PostgreSQL; `app/` içinde Windows'a bağlı kod yok, yalnız `scripts/*.ps1` kurulum betikleri ve Görev Zamanlayıcı). **Bilinmeyenler (deneme öncesi; (1) aşağıdaki sonuçla yanıtlandı):** (1) Trendyol ve Hepsiburada GitHub'ın bulut adreslerini engelliyor mu (Hepsiburada ev adresimizde bile arama API'sinde 403 veriyor); (2) veritabanı nerede duracak (GitHub'daki bir iş veritabanı tutamaz: kendi sunucumuz mu, yönetilen hizmet mi; yeni mimari karar, verilmedi); (3) maliyet ve bakım (GitHub Actions limitleri teyit edilmedi). **Sonuç (6 Ekim 2026 09:41, çalışma 37425171004, 42 sn):** Hepsiburada'nın 3 sayfası buluttan okundu ve bilgisayarın son üç turuyla birebir aynı çıktı (36.999 TL, 39.999 TL, 1 Tükendi); Trendyol'un 1 sayfası **HTTP 403** (`blocked`) verdi. Aynı kodla bilgisayarda son turda 116 Trendyol sayfasının hiçbiri engellenmedi ve bugüne kadar hiçbir turda `blocked` yok; fark kodda değil çıkış adresinde görünüyor. Ancak bulutta tek örnek var (tekrar denemesi ucuz: 1 Trendyol isteği). **İlke:** 403 `blocked` sayılır ve engel aşılmaz (proxy, adres döndürme, tarayıcı taklidi yapılmaz; Akakçe kararıyla aynı). **Durum:** GitHub'ın makineleriyle tam toplama şimdilik uygun görünmüyor (Trendyol 117 sayfa). Seçenekler (sunucu denemesi, evde 7/24 açık küçük cihaz, bilgisayarı tur için uyandırma) kullanıcıyla değerlendirilecek; karar verilmedi. |
| Gelecek aşama tanımları (`PricePoint`, `ProductSummary`, `MarketRecord`, `coverage_version`, zamanlama/ML ayarları, FastAPI/LightGBM/Streamlit bağımlılıkları) | Kaldırıldı (25 Eylül 2026). İlgili aşamada yeni tasarıma göre yeniden eklenecek; yerel taslaklar o zamana kadar çalışmaz. |

## 9. Sonraki aşamalar

### Veritabanı ve zamanlanmış toplama (tamamlandı; 8 Ekim)

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
Bu karar tarihinde Adım 8 araştırması tamamlanmış, Adım 9 aktarımı henüz
uygulanmamıştı; 8 Ekim’de Adım 9 da tamamlandı.
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
kayıtlar ve 6 Ekim hedefli canlı örnek eşleşti; o aşamada iki risk için gerçek
uyuşmazlık kanıtı beklendi (7 Ekim kapanışı Bölüm 7'de).
Manuel kayıt aracı hazırlandı; Adım 9'a geçilmedi.
Kullanıcı, sonraki bakım kontrolünden önce bu araç ve kontrol notları için
commit/push yapılmasını onayladı.
Bakım 3'ün dar kural ve regresyon planı da onaylandı ve uygulandı: 652 test,
0 atlandı/xfail; kullanıcı commit/push işlemini onayladı. `57595f9` push/CI yeşil
tamamlandı. Bakım 4'ün onaylı kaynak kontrolü 7 Ekim'de tamamlandı: iPhone 15
ve Galaxy S24 için toplam 40 HB HTML/37 tek dolu liste/0 çelişki. Kullanıcı
bu madde için gerçek çelişki örneğini bekleme şartına istisna verip önleyici
düzeltme planını onayladı; uygulandı, 727 test/0 atlandı/xfail, biçim denetimleri
temiz. Kullanıcı commit/push işlemini onayladı. Bakım 4 `afe03e4` gönderildi,
aynı SHA için CI 37603817085 yeşil. Kullanıcı 7 Ekim'de bakım 2'ye geri dönmeyi,
ardından 5 → 6 → 7 sırasını istedi. Yeniden kontrol tamamlandı: iki hedefte
TY 6/HB 36 sayfa kimliği eşleşti, iki yapay risk sürdü. Kullanıcının bakım 2'ye
ayrı istisnasıyla dar önleyici düzeltme uygulandı: 31 yeni sınama, 758 test/
0 atlandı/xfail, biçim denetimleri temiz. Kullanıcı commit/push işlemini onayladı (Bölüm 7);
`8598e3c` gönderildi, aynı SHA için CI 37609748487 yeşil. Ardından bakım 5'in
ortak ürün adresi planı ayrı kullanıcı istisnasıyla onaylanıp uygulandı:
39 yeni sınama, 797 test/0 atlandı/xfail (219 PostgreSQL), biçim denetimleri temiz.
334 katalog/333 farklı aday kimliği korundu; `ac9c6b6` push/aynı SHA için
CI 37616987979 yeşil. Ardından bakım 6 planı onaylanıp uygulandı: kapanış
sonrası hata/kesintide veri ve kilit koruması kabul edildi, yalnız Ctrl+C
mesajı düzeltildi. 7 yeni sınama; 804 test/0 atlandı/xfail (226 PostgreSQL),
biçim denetimleri temiz. `ea4248e` gönderildi, aynı SHA için CI 37625155724 yeşil.
Ardından kullanıcı bakım 7 kontrol/kalıcı test planını onayladı: mevcut eklenti
sözleşmeleri ve hata akışı üretim değişmeden doğrulandı; 28 yeni sınama,
832 test/0 atlandı/xfail (228 PostgreSQL), biçim denetimleri temiz. Yedi bakım
maddesi tamamlandı; kullanıcı bakım 7'nin commit/push işlemini onayladı.
O tarihte başlamamış olan Adım 9, 8 Ekim’de gerçek ve tekrar aktarımı
doğrulanarak tamamlandı; ardından Adım 7 ile veritabanı aşaması kapandı.

| Adım | Durum |
|---|---|
| 0. Hazırlık: taslakların taşınması, PostgreSQL 17, `fiyat_takip` kullanıcısı, `fiyat_takip` ve `fiyat_takip_test` veritabanları | ✅ Tamamlandı (28 Eylül) |
| 1. Şema, migrate komutu, CI'da PostgreSQL | ✅ Tamamlandı (28 Eylül): `001_initial.sql`, `python -m app.database migrate/status`, 32 veritabanı testi (toplam 91) |
| 2. Katalogun veritabanına eşitlenmesi | ✅ Tamamlandı (28 Eylül): `python -m app.database sync-catalog [--dry-run]`; kimlik değişiminde hiçbir şey yazmadan durur, katalogdan düşen kayıt pasife alınır; 22 test (toplam 113) |
| 3. Toplama turu ve ortak kilit | ✅ Tamamlandı (28 Eylül): `python -m app.collection [--prefix] [--scheduled]`; sayfa sonucu hemen ve bir kez yazılır, yarım kalan tur sonraki turda kapatılır; tur, keşif ve iki canlı kontrol aracı `data/scrape.lock` kilidini paylaşır; ayrıca veritabanı tur kilidi. Commit öncesi üç ek kontrol: (1) bağımsız kod incelemesi, 13 bulgu, 7 numara hariç hepsi düzeltildi ve testlendi (7 → Adım 4); (2) kasıtlı bozma testi: 37 bozmanın 33'ü testlerce yakalandı, kaçan 4'ü önceden tahmin edilen eşzamanlılık/güvenlik korumaları; (3) ilk canlı tur (`--prefix poco_`, 4 sayfa, 25 sn): 4/4 fiyat, çıkış 0. Testler 22 (toplam 143). |
| 4. Karşılaştırılabilirlik görünümü (sahte düşüş kuralı) | ✅ **Tamamlandı (5 Ekim):** `002_guards_and_comparability.sql`; kullanıcı `migrate` ile uyguladı (14:29 yerel, `status`: iki migration uygulandı). **Kullanıcı kararları (5 Ekim):** tetikleyiciler beş tabloda; görünüm zaman boşluğunu engellemez, yalnız gösterir; çizili fiyat sözleşmede reddedilir (sayfa hata olur). **İçerik:** (A) iki CHECK: `listing_checks_sold_out_has_no_offer` (Tükendi satırı fiyat, çizili fiyat, satıcı, puan ve ölçek taşımaz) ve `listing_checks_original_above_current` (çizili fiyat yalnız güncel fiyattan büyükse; aynı kural `PriceObservation` sözleşmesinde de, scraper'lar zaten `null` verir); (B) 15 tetikleyici: her beş tabloda `DELETE`/`TRUNCATE` reddi, kimlik alanları değişmez (`collection_runs.run_id`'yi PostgreSQL `GENERATED ALWAYS` ile zaten korur), `listing_checks` sonucu bir kez yazılır sonra donar; tek istisna çalışan turdaki `error/network` satırı (Adım 11'in ön koşulu); hata SQLSTATE `23000`; bilerek silmek için tablo sahibi tetikleyiciyi kapatır (docs/teknik.md); (C) `product_run_prices` görünümü: biten tur × ürün için en ucuz fiyat, önceki tur, `hours_since_previous` ve `comparable_with_previous` (cevap veren sayfa kümesi aynıysa ve cevap sayısı > 0). **Kanıt:** testler 450 → 519 (+69: `tests/test_database.py` 131, yeni `tests/test_comparability.py` 14, `tests/test_contracts.py` +3; 182'si gerçek PostgreSQL'de), 0 atlandı, Black ve Flake8 temiz; projenin kopyasında 21 kasıtlı bozmanın 21'i testlerce yakalandı; migrate'ten önce gerçek veride kural ihlali yoktu (1.013 `sold_out` satırında fiyat/satıcı yok, 491 çizili fiyatın hepsi güncel fiyattan büyük); görünümün SELECT'i gerçek veride (709 satır, 13 tur) Python'daki bağımsız hesapla 0 uyuşmazlık verdi ve migrate'ten sonra gerçek veritabanında aynı değerleri gösterdi (15 tetikleyici açık, 2 CHECK var). Önceki tura göre karşılaştırılamayan ürün sayısı: tur 3: 11, 4: 11, 7: 1, 8: 1, 11: 21, 12: 22, diğerleri 0 (tur 11'deki 109 DNS hatası ve tur 12'deki S25+ `identity` hatası dahil). **Bulgu:** `run_id` zaten korunuyor, tetikleyiciden çıkarıldı. **Öğrenilen uyarı:** yeni migration dosyası klasöre girince veritabanı güncellenene kadar tur başlamaz; bu yüzden geliştirme projenin kopyasında yapıldı, dosya gerçek klasöre bitince konuldu ve `migrate` hemen, tur saatleri dışında çalıştırıldı. **Kapsam dışı:** görünümü okuyan API/ML henüz yok (Aşama 7 ve 8); `comparable_with_previous = false` satırlarının yorumu tüketen aşamanın işidir. **Canlı kanıt (5 Ekim 22:00, tur 14):** tur yeni CHECK ve tetikleyicilerle ilk kez çalıştı: 333 sayfa planlandı (334 bağlantı, 1 pasif), `completed`, 36 dk, 229 fiyat, 102 Tükendi, 2 hata, çıkış 2. Hatalar: S25+ `identity` (beklenen) ve ilk kez görülen `invalid_host` (Bölüm 7); tetikleyici veya CHECK kaynaklı `storage` hatası yok, yani 333 sayfanın sonucu kurallara takılmadan yazıldı. Tur başındaki katalog eşitlemesi 7 yeni sayfayı ekledi (`listings` 334). Yeni 7 sayfa ilk okumada 6 fiyat (iPhone 17 Pro Max 2 TB için 168.999–169.999 TL, Galaxy S24 FE 44.999 TL, 14T Pro 42.999 TL, Redmi Note 14 Pro 24.699 TL) ve 1 Tükendi (Redmi Note 13 Pro 5G) verdi. Görünümde `comparable_with_previous` tur 14'te öngörülen ürünlerde (29, 40, 47, 51, 55: yeni sayfa) ve `invalid_host` yüzünden ürün 1'de `false` oldu; ürün 31 (S25+ sayfası iki turdur eksik) bozulmadı. |
| 5. Canlı deneme (kullanıcı çalıştırır) | ✅ Tamamlandı (28 Eylül): ilk tam tur (tur 2, 15:48–16:19 TR saati, **30 dk 55 sn**): 326/326 sayfa okundu, **0 hata, 0 engellenme**; iki sayfa arası en uzun bekleme 9,4 sn. Hepsiburada 213: 139 fiyat, 74 Tükendi; Trendyol 113: 110 fiyat (77 Kritik Stok), 3 Tükendi. 8 ürünün bütün sayfaları Tükendi (çoğu eski iPhone'ların yüksek kapasiteleri). Tarayıcı karşılaştırması 4 sayfa: fiyat, çizili fiyat, satıcı, kuruşlu fiyat (turda 31 tane) ve Kritik Stok eşleşti; 15:49'da Tükendi okunan `trendyol_762254862` 17:47'de "Son 1 ürün" gösteriyordu, yeniden okumada da Kritik Stok çıktı (sayfa arada değişmiş). Aynı ürünün bir sayfasında fiyat 2 saatte 71.059 → 75.524 TL oldu. Bulunan tek hata: ön ek verilmeyen turda `note` NULL yerine boş yazı oluyordu (`concat_ws`); düzeltildi, test eklendi (toplam 144). Tur 2'nin kaydı elle değiştirilmedi. |
| 6. Görev Zamanlayıcı ve 2–3 günlük gözlem | ✅ Tamamlandı (1 Ekim; kuruldu ve gözlendi, gözlem sonucu satırın sonunda). Görev 28 Eylül akşamı `scripts/zamanlayici_kur.ps1` ile kuruldu; kullanıcı ilk turu `Start-ScheduledTask` ile başlattı (tur 3, `scheduled`, 23:22–23:55, 33 dk): `pythonw`, ortam değişkenleri, `pgpass.conf`, çalışma klasörü ve log dosyası Görev Zamanlayıcı ortamında çalıştı. 326 sayfanın 279'u cevap verdi (219 fiyat, 60 Tükendi), 47 sayfa `network` hatası aldı (DNS çözümlenemedi / zaman aşımı; Windows WLAN günlüğüne göre hotspot bağlantısı 23:27:38'de koptu, 23:30:52'de döndü); tur `completed`, çıkış 2, veri uydurulmadı. İlk tetikleyiciyle çalışan tur (tur 4, 29 Eylül 10:00:02, 30 dk 44 sn): 326/326 sayfa, **0 hata** (243 fiyat, 83 Tükendi), çıkış 0; aynı sabah temizlenen kodla gerçek sitelerde ilk tur, istek aralıkları önceki turlarla aynı (Hepsiburada ortalama 8,7 sn). Kararlar (28 Eylül, kullanıcıyla): görev **penceresiz** (`pythonw.exe`) çalışır, `--scheduled` çıktısı `data/logs/tur_<yerel tarih-saat>.log` dosyasına da yazılır (açık kalan bir pencere kapatılınca tur kesilirdi; Görev Zamanlayıcı çıktı saklamaz); görev repodaki `scripts/zamanlayici_kur.ps1` ile kurulur (ayarlar kodda, yeniden kurulabilir). Ayarlar: yerel saatle 10:00/22:00, kaçan tur açılınca bir kez, pilde de çalışır, uyandırmaz, 2 saat süre sınırı, kullanıcı adına yalnız oturum açıkken (docs/teknik.md "Zamanlanmış tur"). Kullanıcının dizüstünde boşta uyku kapalı (şarj ve pil). 5 yeni test (toplam 149); log kodunda 3 kasıtlı bozmanın 3'ü yakalandı; gerçek `pythonw.exe` ile siteye gitmeyen denemede log yazıldı, çıkış 1, tur açılmadı. **Commit öncesi projenin tamamı incelendi (29 Eylül):** 8 bağımsız inceleyici (scraper, keşif, veritabanı, tur, belgeler, güvenlik, okunabilirlik, test kalitesi) bütün dosyaları okudu; her bulgu ayrı bir doğrulayıcıya çürütülmek üzere verildi ve son bir denetçi kimsenin bakmadığı yerlere baktı. 168 ham bulgu → 135 tekil; 10'u çürütüldü, 125'i doğrulandı (57'si kısmen), +24 ek bulgu. Davranış değiştirmeyenler uygulandı: ölü kod temizliği, dışarıdan okuyana yönelik yorumlar (kilit numaraları, Tükendi kuralı, hata kodları, üç istekli Hepsiburada akışı…), belge düzeltmeleri ve testler **149 → 414** (116'sı PostgreSQL'de; yeni `tests/test_http.py`, `tests/test_contracts.py`). Kullanıcı davranış değiştiren bulgulardan üç grubu onayladı ve uygulandı: keşif sağlamlığı (UTF-8 çıktı, BOM'lu dosya okuma, kilit meşgulken çıkış 3, fazladan arama sayfası yok, pasif sayfalar "korunan" listesinde yok, adaptör hatası çıkış 1), migration koşucusu (yeniden adlandırılan dosya reddedilir, numara hatası bulunanları gösterir), tanılama çıktısı (boş satıcı kimliği, `missing_price`/`missing_seller`); her birinin testi önce eski kodda başarısız oldu. Çizili fiyat kuralı (sözleşme + CHECK) Adım 4'e alındı. Araç düzeni: Python `>=3.13,<3.14`, Black `>=26.1`; ortak yapay zekâ talimatları `AGENTS.md`'ye taşındı (Claude Code ve Codex aynı dosyayı okur), `.cursorrules` silindi. Testlere iki emniyet kemeri eklendi: gerçek ağ isteği ve kalıcı `DATABASE_URL` her testte kesilir. Yeni testler bellekte veya kopyada kasıtlı bozmalarla sınandı (75 bozmanın 73'ü yakalandı; kaçan 2'si eşdeğer bozma). Bir gerçek hata bulundu ve `xfail` ile belgelendi (Bölüm 7, Türkçe ekler). Davranış değiştiren bulgular kullanıcı kararına bırakıldı. **Gözlem sonu (1 Ekim):** gerçek veritabanı (yalnız okuma) ve loglar eşleşti: 7 tur kayıtlı, hepsi `completed`, takılı `running` tur ve boş `outcome` satırı yok. Tur 4–6 (29 Eylül 10:00 – 30 Eylül 10:00): 326/326, 0 hata, çıkış 0. **30 Eylül 22:00 turu çalışmadı:** bilgisayar 17:57'de uyudu (Windows günlüğü: uyku nedeni "Application API"; kesin tetikleyici belirlenmedi) ve 1 Ekim 09:20'de uyandı; yukarıdaki "boşta uyku kapalı" ayarı bunu önlemedi. Kaçan tur 1 Ekim 09:26'da açılışta bir kez telafi edildi (tur 7, `scheduled`, 37 dk, 234 fiyat, 91 Tükendi, 1 `network`, çıkış 2): telafi mekanizması bilerek kaçırma denemesine gerek kalmadan gerçek bir uykuda doğrulandı. Aynı turda 09:29'da kritik pil yüzünden yaklaşık 6,5 dk uyku oldu; sayfa 31 uyanma anında DNS hatası aldı, tur veri uydurmadan tamamlandı. 10:00 tetiklemesi tur 7 sürerken geldi ve `IgnoreNew` ile atıldı (ayrı log ve tur kaydı yok); `LastTaskResult = 2` tur 7'nin sonucudur. Bulgular Bölüm 7'ye sınır olarak, kararlar Bölüm 8'e işlendi. |
| 7. Kapanış belgeleri | ✅ **Tamamlandı (8 Ekim):** son tur 19’un 332 log satırı DB ile birebir aynı (237 fiyat/95 Tükendi/0 hata), katalog 59 ürün/334 sayfa (332 etkin) ve 001–004 güncel. Karşılaştırma görünümünün 59 ürün sonucu bağımsız doğrulandı. Cimri’nin 20.805 kaydının tüm alanları kaynakla aynı, 553 NULL ve ilk kaynak bilgileri korunmuş. Bilinen sınırlar ve canlı kanıt bekleyen durumlar belgeli; kod değişmedi. Kapanış belge commit/push işlemi kullanıcı tarafından onaylandı; aynı yeni SHA CI gönderimden sonra kontrol edilecek. README’nin tanıtım amaçlı düzenlenmesi sonraki ayrı iş; API/arayüz başlamadı. |
| 8. Tek piyasa geçmişi kaynağı araştırması (Adım 6'nın 2–3 günlük gözlemi sırasında) | ✅ Araştırma tamamlandı (29 Eylül): Cimri üç üründe doğru kimlikle 365'er nokta (30 Eylül 2025–29 Eylül 2026), 0 eksik fiyat ve her üründe 90/90 tablo eşleşmesi verdi. Akakçe ilk örneği HTTP 403 verdi; diğer ürünlerine istek atılmadı. `tests/manual/market_history_probe.py` ortak HTTP katmanı/kilit ve dört istek bütçesiyle yalnız yerel rapor üretir. Tarihsel satıcı kapsamı ve günlük gözlem sıklığı bilinmiyor. Araştırma tarihinde kullanım koşulları düzenli kopyalama/işleme için uygunluğu doğrulamadığından aktarım kaynağı seçilmedi; veritabanına veri yazılmadı. **30 Eylül kararıyla bir defalık Cimri aktarımı ayrı Adım 9 olarak planlandı**; araştırmanın tamamlanması aktarımın tamamlandığı anlamına gelmez. |
| 9. Cimri geçmişinin bir defalık aktarımı | ✅ **Tamamlandı (8 Ekim): 9.1 yerel alım, 9.2 aktarım altyapısı/004 ve 9.3 gerçek aktarım/kapsam teyidi tamam.** 59 ürünün 57’si aktarıldı: 20.805 kayıt = 20.252 fiyat + 553 NULL, 2025-10-09–2026-10-08. Galaxy S25 512 GB ve Redmi Note 14 Pro 5G 256 GB eşleştirmeleri gerekçeli eksik olarak raporlandı. Bağımsız READ ONLY kontrolde bütün 10 alan kaynakla aynı, eksik/fazla/farklı satır yok; tekrar aktarım 0 yeni/20.805 aynı ve ilk kaynak bilgileri aynı. 115 alım dosyası korundu. Ayrı market_history tablosu kendi toplama serisine katılmaz; düzenli Cimri toplaması veya ML eğitimi yapılmadı. 9.1/9.2 kod commit’leri gönderildi ve CI başarılı; 9.3 kapanış belgeleri `2c78af2` ile gönderildi; aynı SHA CI 37795271692 başarılı. Adım 7 kapanışı da tamamlandı. Ayrıntılar ve yerel kapanış raporu Bölüm 7/9.3. |
| 10. Haftalık keşif zamanlayıcısı (A1) | ✅ **Tamamlandı (5 Ekim).** Kod, test, belgeler ve görev kurulumu 1 Ekim'de hazırdı; canlı kanıt 4–5 Ekim'de geldi (satırın sonunda). Uygulananlar: ortak log yardımcıları `app/console.py`'ye taşındı (fiyat turunun davranışı ve testleri değişmedi); keşfe `--scheduled` (yalnız `--dry-run` ile; `data/logs/kesif_<ts>.log`, `data/discovery/kesif_<ts>.json`, nedene göre sayılmış tek satırlık özet) ve `--apply-report <rapor>` (siteye gitmez; eklenecekler önizlemedeki listenin alt kümesi olmalı, aksi hâlde hiçbir şey yazılmaz; aynı rapor ikinci kez uygulanırsa bir şey eklenmez) eklendi; `DiscoveryReport.generated_at` ve `DISCOVERY_REPORT_DIR` eklendi; `scripts/kesif_zamanlayici_kur.ps1` görevi `\FiyatTakip\HaftalikKesif` olarak kurar (Pazar 14:00, kaçan çalışmayı telafi etmez, uyandırmaz, 2 saat sınırı; betiği kullanıcı 1 Ekim'de çalıştırdı). Testler 426 → 450 (24 yeni, hepsi ağsız ve veritabanısız); projenin kopyasında 14 kasıtlı bozmanın 14'ü testlerce yakalandı. **Canlı kanıt (1 Ekim, kullanıcı):** `--scheduled --dry-run --target apple_iphone_15` (~79 sn): çıkış 2, log ve rapor aynı damgalı, sabit `data/discovery_report.json` ezilmedi, katalog değişmedi, rapor sözleşmeye uyuyor (Trendyol 5 aday `count_mismatch`, Hepsiburada 15 aday `search_api`, 0 yeni, 20 zaten kayıtlı). Görev kuruldu ve kayıtlı ayarlar salt okunur doğrulandı: haftalık Pazar 14:00 (yerel), `StartWhenAvailable=False`, `WakeToRun=False`, `IgnoreNew`, 2 saat sınırı, `pythonw -m app.discovery --scheduled --dry-run`, çalışma klasörü proje klasörü; fiyat görevi değişmedi (2 tetikleyici, sonraki çalışma 22:00); sonraki keşif 4 Ekim 14:00. **Canlı kanıt (4–5 Ekim):** İlk zamanlanmış çalışma 4 Ekim 14:00:03'te kendiliğinden başladı (`pythonw`, Görev Zamanlayıcı): aynı damgalı log ve rapor yazıldı, loga `Çıkış kodu: 2` düştü; ama internet kesildiği için tarama 7 dk'da boş bitti (DNS hatası: Trendyol 21, Hepsiburada 21 hedef; tam sonuç 3/48, yeni sayfa 0; Bölüm 7). Bu çalışma altyapıyı doğruladı, içeriği doğrulamadı. **5 Ekim 11:00'de kullanıcı aynı komutu elle çalıştırdı** (`--scheduled --dry-run`, normal `python`; tur 13 bitmişti, kilit boştu): 34 dk (11:00:14–11:34:09), DNS hatası yok, tam sonuç 23/48 (Trendyol 23/24; Hepsiburada 24/24 kısmi: arama API'si 403, 16 `model_filter_missing`, 2 `html_partial`), çıkış 2, rapor 305 KB, 0 yeni ürün, **7 yeni sayfa** (iPhone 17 Pro Max 2 TB için 3 Hepsiburada; Galaxy S24 FE 256 GB, Xiaomi 14T Pro 256 GB ve Redmi Note 14 Pro 512 GB için 1'er Trendyol; Redmi Note 13 Pro 5G 256 GB için 1 Hepsiburada), 146 reddedilen (başka hedefin modeli, aksesuar, bilinen yurt dışı sürüm), 37 görülmeyen (korunur), 0 çakışma. Kullanıcı `python -m app.discovery --apply-report data\discovery\kesif_2026-10-05_11-00-14.json` çalıştırdı: 7 sayfa eklendi, 289 zaten kayıtlıydı; `config/catalog.json` +56 satır (LF), eklenen `product_id`'ler (29, 40, 47, 51, 55) veritabanından okunarak doğru ürünlere ait çıktı; katalog **59 ürün, 334 bağlantı**. Sonraki fiyat turu (5 Ekim 22:00) yeni sayfaları veritabanına ekler. **Sınırlar:** tam tarama Görev Zamanlayıcı altında henüz görülmedi (ilk fırsat Pazar 11 Ekim 14:00); Redmi Note 14 Pro 512 GB (Trendyol, `trendyol_1208111572`) sayfasının 4G olduğu ekleme sonrası kullanıcı tarafından tarayıcıda doğrulandı (5 Ekim; ürün sayfasında 4G yazıyor; ağ türü raporda görünmediği için eklemeden önce görülemedi); keşif logu ilerleme satırı yazmaz, yalnız 4 satır (başlık, özet, rapor yolu, çıkış kodu) bırakır. |
| 11. Tur sonunda `network` ikinci geçişi | ✅ **Tamamlandı (6 Ekim):** 1 Ekim kararı (Bölüm 8) uygulandı; migration gerekmedi (Adım 4'teki 002 tetikleyicisi çalışan turdaki `network` satırının yeniden yazılmasına zaten izin veriyordu). `app/collection/service.py` `retry_network_errors`: sayfa döngüsü bittikten sonra, tur kapatılmadan önce yalnız o turda `error`/`network` sonuçlu sayfalar (5xx dahil) bir kez yeniden okunur; yeni `app/database/runs.py` `rewrite_network_result` yalnız süren turun `error`/`network` satırını yazar (`record_result` ile ortak `_write_result`). **Davranış (kullanıcı kararları, 6 Ekim):** düzelirse satır yeni sonuçla değişir (fiyat, Tükendi ya da `network` dışında bir hata); ikinci okuma da `network` verirse ilk satır (mesaj ve zaman damgası dahil) olduğu gibi kalır; veritabanı yeni sonucu reddederse ilk satır kalır ve tur sürer; ardışık 5 sayfa yine `network` verirse geçiş durur (kalanlar denenmez); `blocked`, `parse`, `identity` ve diğer hatalar hiç yeniden denenmez; log `[tekrar i/n]` satırları taşır; tur notuna yalnız sayılar yazılır (`network hatası alan 109 sayfa, ikinci okuma: 104 düzeldi, 5 hâlâ hatalı`), sayfa kimlikleri logdadır; çıkış kodu ve özet ikinci okumadan sonraki duruma göre hesaplanır; düzelen sayfa cevap sayıldığı için görünümde sahte "karşılaştırılamaz" satırı oluşmaz. **Kanıt:** testler 527 → 545 (+18, hepsi gerçek PostgreSQL'de: 182 → 200), 0 atlandı, Black ve Flake8 temiz; akış testleri eski kodda başarısızdı (9 akış testi kırmızı; 7 "yalnız `network` yeniden okunur" koruması ve 2 `rewrite_network_result` birim testi eski kodda da geçer, çünkü işlev yeni); projenin kopyasında 20 kasıtlı bozmanın 20'si testlerce yakalandı. **Sınırlar:** gerçek bir turda henüz görülmedi (`network` hatası olmayan turlarda ikinci okuma çalışmaz); bilgisayar uyursa ya da kesinti tur bitene kadar sürerse sayfalar hatalı kalır (kalıcı çözüm sunucu, Aşama 9); düzelen sayfanın `checked_at` değeri ikinci okuma anıdır (ilk denemeden en çok tur süresi kadar sonra). Ayrıntı: docs/teknik.md "Tur sonu ikinci okuma". |

**Adım 9 onaylanan alt adımlar (7 Ekim kullanıcı kararı):**

9.1 yerel doğrulaması (8 Ekim): 197 yeni ağsız sınama; son tam paket **1029 passed**, 0 atlandı/xfail (228 PostgreSQL yalnız fiyat_takip_test). Black/Flake8 temiz. İlk üç yeni kaynak doğrulandı; Xiaomi’nin dört sıfırı kullanıcı kararıyla eksik değer olarak okunuyor. Mevcut app/config/scripts dosyaları ve 001–003 migration değişmedi; yeni app/market_history ve 57 adresli eşleştirme eklendi. Katalog alımı kontrol edildi: 53 kabul edilmiş geçmiş, dört fiyat uyuşmazlığı, iki açık eşleştirme. İkinci alımda ham veri farkı sürdü; kullanıcı ekranda uyum gördü. Null önerisi geri çekildi; bugünkü ilk teklif dönüşümü kaynakta doğrulandı, dar düzeltme kullanıcı onayıyla uygulandı; 57 kayıt yeni kodla ağsız doğrulandı, beş ürünün canlı teyidi tamam; commit/push onaylandı; CI sonucu GitHub Actions kaydından izlenir. 9.1 uygulama ve canlı doğrulaması tamam; commit/push onaylandı; CI sonucu GitHub Actions kaydından izlenir. 9.1 kapandığında Adım 9’un aktarım alt adımları açıktı; 9.3 gerçek ve tekrar aktarım teyidiyle Adım 9, 8 Ekim’de tamamlandı.

| Alt adım | Durum / durma noktası |
|---|---|
| 9.1 Eşleştirme ve yerel alım | ✅ Uygulama ve canlı doğrulama tamam; gönderim onaylı. Ortak HTTP/kilit ile `python -m app.market_history capture` hazır; yeni klasöre HTML, API JSON'u, SHA-256 ve UTC zamanlı rapor kaydeder. Fiyat kuruş, eksik değer null; engelde kalan istekler durur. Mevcut araştırma aracı ortak Cimri ayrıştırıcısını kullanır, TL rapor sözleşmesi korunur. İlk üç araştırılmış adres ve yeni yanıt doğrulaması hazır; Xiaomi’nin 2–5 Ekim grafik sıfırları eksik değer olarak okunuyor, 86 tablo satırı eşleşiyor. İlk rapor ve ham dosyalar değiştirilmedi. 57/59 ana adres araştırıldı; Galaxy S25 512 GB ve Redmi Note 14 Pro 5G 256 GB açık. 57 ürünün ham yanıtı alındı: 53 geçmiş kabul edildi, dört üründe yalnız 8 Ekim fiyatı tablo/grafik arasında farklı. Dört ürünün ikinci alımında aynı ham veri farkı sürdü; kullanıcı ekranda uyum gördü. Null önerisi geri çekildi; bugünkü ilk teklif dönüşümü kaynakta doğrulandı, dar düzeltme kullanıcı onayıyla uygulandı; 57 kayıt yeni kodla ağsız doğrulandı, beş ürünün canlı teyidi tamam; commit/push onaylandı; CI sonucu GitHub Actions kaydından izlenir. 9.1 uygulama ve canlı doğrulaması tamam; gönderim onayı verildi, aynı SHA CI doğrulaması gönderim akışının parçasıdır. |
| 9.2 Veritabanı aktarımı | ✅ **Tamamlandı (8 Ekim): kod/test, gönderim/CI, ana geçiş ve gerçek 004 uygulaması doğrulandı.** 004, ağsız import/--dry-run, kaynak/rapor/kimlik doğrulaması, ürün bazında transaction, ilk kaydı koruma ve eşzamanlı çelişki kontrolü uygulandı. 161 yeni test; **1190 passed, 0 atlandı/xfail (276 PostgreSQL yalnız `_test`)**, Black/Flake8 temiz. 001–003 korunuyor. `c64d14f` gönderildi, aynı SHA CI 37777433986 başarılı. Kullanıcı 004’ü 12:35 UTC’de uyguladı; salt okunur kontrol şemanın güncel, tablonun boş ve korumaların etkin olduğunu doğruladı. Fiyat aktarımı 9.3’te. |
| 9.3 Katalog kapsamı ve kapanış | ✅ **Tamamlandı (8 Ekim):** 57 ürün/20.805 kayıt, 553 NULL; iki eşleştirme eksikliğiyle 59 ürünün kapsamı raporlandı. Tekrar 0 yeni/20.805 aynı/0 çelişki/iki atlanan, çıkış 2; tüm ilk kaynak alanları ve 115 dosya korundu. `2c78af2` gönderildi; aynı SHA CI 37795271692 başarılı. Adım 7 kapanışında kaynaklar ve bütün DB satırları tekrar teyit edildi. |

Alt adımlarda testler/biçim denetimleri ve sonuç değerlendirmesi sonrası dosya
listesi ile Türkçe commit mesajı gösterilir; ayrı onayla commit/push, aynı SHA
CI kontrolü yapılır. Düzenli Cimri toplaması, ML eğitimi ve API/UI bu adımın
işi değildir; kaynak serileri birleştirilmez. 29 Eylül raporları ilk aktarıma
otomatik alınmaz; erişilemeyen veya eksik yeni geçmiş olduğu gibi raporlanır.

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

Takvim (8 Ekim güncellemesi; Adım 9 ve Adım 7 tamamlandı, veritabanı aşaması kapandı):

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
| 6 Ekim | Bakım 4 kontrol planı onaylandı; 19 kayıtlı HB HTML'de 17 tek dolu liste, 0 çelişki. Yerel analiz hazır; Galaxy S24 ham yanıtlarını kullanıcı çalıştıracak. Gerçek uyuşmazlık kanıtı bekleniyor, uygulama kodu değişmedi |
| 7 Ekim | Bakım 4 kaynak kontrolü tamamlandı: kullanıcının Galaxy S24 kaydındaki 21 HB HTML'de 20 tek dolu liste/0 çelişki; 8 kabul edilen adayın kapasite/renk bilgisi eşleşti. Çıkış 2 model filtresi bulunamaması ve arama API 403'ünden. İki hedef toplam 40 HTML/37 tek dolu liste; kod korunuyor, gerçek uyuşmazlık kanıtı bekleniyor. Bakım 5'e geçilmedi |
| 7 Ekim | Bakım 4 önleyici düzeltmesi kullanıcı istisnasıyla uygulandı: aynı SKU'nun bütün kapasite/renk kayıtları doğrulanıyor, çelişkide identity. 75 yeni sınama; 727 test geçti/0 atlandı/xfail, Black/Flake8 temiz. 24 geçerli adayın bilgileri ve 12 diğer modelin reddi korundu. Kullanıcı commit/push işlemini onayladı; bakım 5'e geçilmedi |
| 7 Ekim | Kullanıcının sırası 2 → 5 → 6 → 7. Bakım 2 iki hedefle yeniden kontrol edildi: TY 6/HB 36 kimlik eşleşti, gerçek uyuşmazlık yok. Ayrı kullanıcı istisnasıyla TY adres kimliği ve HB canonical tam SKU korumaları uygulandı; 31 yeni sınama, 758 passed/0 atlandı/xfail, Black/Flake8 temiz. 6 TY/24 HB aday ve 12 model reddi korundu. Kullanıcı commit/push işlemini onayladı; bakım 5 başlamadı |
| 7 Ekim | Bakım 5 önleyici düzeltmesi ayrı kullanıcı istisnasıyla uygulandı: beş tüketici ortak ürün yolu kimliği kullanıyor. Sorunlu TY ucuz teklifi ve HB sorgu SKU'su reddediliyor. 334 katalog/333 farklı aday kimliği korundu; gerçek DB/katalog/migration değişmedi. 39 yeni sınama; 797 passed/0 atlandı/xfail (219 PostgreSQL), Black/Flake8 temiz. Kullanıcı commit/push işlemini onayladı; bakım 6'ya geçilmedi |
| 7 Ekim | Bakım 6 kontrolü ve mesaj düzeltmesi tamamlandı: kapanış sonrası SQL hatası/bağlantı kapanması/Ctrl+C'de completed tur, bütün kayıtlar, kilitler ve sonraki tur korundu. Yalnız Ctrl+C mesajı değişti, çıkışlar 1/130 aynı. 7 yeni sınama; 804 passed/0 atlandı/xfail (226 PostgreSQL), Black/Flake8 temiz. Kullanıcı onayıyla ea4248e push/aynı SHA için CI 37625155724 yeşil |
| 7 Ekim | Bakım 7 kontrol/kalıcı test planı uygulandı: yükleyicilerin farklı sözleşmeleri kabul edildi; hata/Ctrl+C, kayıt/dosya koruması, log, kapanış, kilitler ve sonraki normal çalışma doğrulandı. Üretim kodu değişmedi. 28 yeni sınama; 832 passed/0 atlandı/xfail (228 PostgreSQL), Black/Flake8 temiz. Yedi bakım maddesi tamamlandı; kullanıcı bakım 7'nin commit/push işlemini onayladı, yeni özelliklere geçilmedi |
| 7–8 Ekim | **Adım 9.1 uygulama/canlı doğrulaması tamam, gönderim onaylandı:** yerel alım aracı ve 57/59 ana adres hazır; ilk üç yeni kaynak kontrol edildi. Kullanıcının 8 Ekim kararıyla grafik sıfırları tabloda fiyat yoksa eksik okunuyor; 1029 test geçti/0 atlandı; ilk teklife dayanan güncel fiyat dönüşümü de doğrulandı. Galaxy S25 512 GB ve Redmi Note 14 Pro 5G 256 GB eşleştirmeleri açık. 10:49–10:58 katalog alımı: 53 geçmiş kabul, dört fiyat uyuşmazlığı; 11:12–11:13 dört ürün tekrarı da aynı sonucu verdi; kullanıcı ekranda uyum gördü, null önerisi geri çekildi; grafik kaynağındaki bugünkü ilk teklif dönüşümü doğrulandı, dar düzeltme kullanıcı onayıyla uygulandı; 57 kayıt yeni kodla ağsız doğrulandı, beş ürünün canlı teyidi tamam; commit/push onaylandı; CI sonucu GitHub Actions kaydından izlenir. 9.2 ve 004 başlamadı |
| 8 Ekim | **Adım 9.2 tamamlandı:** 161 yeni test, 1190 passed/0 atlandı (276 PostgreSQL). c64d14f gönderildi; aynı SHA CI 37777433986 başarılı. Ana geçişten sonra kullanıcı 004’ü 12:35 UTC’de uyguladı; gerçek DB salt okunur kontrolü başarılı, geçmiş tablosu boş. 9.3 için yeni toplu alım kararı kesinleşti. |
| 8 Ekim | **Adım 9.3 planı onaylandı, ilk hazırlık tamam:** 59 katalog/DB kimliği uyumlu, 001–004 güncel ve geçmiş tablosu boş; 57 eşleştirme, iki açık ürünün araştırma kaydı hazır. Kullanıcının yeni capture raporu bekleniyor. |
| 8 Ekim 15:59–16:08 | **9.3 yeni alım tamam:** 57 başarılı/iki eşleştirmesiz, 171 HTTP; 114 kaynak dosyası yeniden doğrulandı, 20.805 nokta/553 NULL. Ek alım gerekmiyor; gerçek DB boş, kullanıcı dry-run çıktısı bekleniyor. |
| 8 Ekim, önizleme | **9.3 dry-run doğrulandı:** 20.805 eklenecek, 0 aynı, 0 çelişkili ürün, iki atlanan; çıkış 2. 115 girdi dosyası aynı, bağımsız READ ONLY kontrolde DB hâlâ boş. Kullanıcı gerçek aktarımını bekliyoruz. |
| 8 Ekim, ilk aktarım | **9.3 gerçek aktarımı doğrulandı:** 57 ürün/20.805 satır, 20.252 fiyat/553 NULL; bütün 10 alan alımla birebir aynı, eksik/fazla/farklı satır yok. İki eşleştirmesiz ürün atlandı, çıkış 2. Sırada aynı girdinin tekrar aktarımı ve ilk kaynak bilgilerinin korunması. |
| 8 Ekim, 17:12 kontrolü | **9.3 ve Adım 9 tamamlandı:** tekrar aktarım 0 yeni/20.805 aynı/0 çelişki/iki atlanan, çıkış 2; bütün 10 alan ve 57 ürünün hash’i ilk aktarımla aynı. 59 ürün kapsamı: 57 aktarılmış, iki gerekçeli eşleştirme eksik. Kapanış raporu hazır; kullanıcı belge commit/push işlemini onayladı; aynı SHA CI gönderim akışında doğrulanır. Adım 7’ye geçilmedi. |
| Adım 11 sonrası | **Adım 9:** Cimri geçmişinin bir defalık alımı, katalog eşleştirmesi ve ayrı `market_history` tablosuna aktarım |
| 8 Ekim, Adım 7 kapanışı | **Aşama 6 tamamlandı:** 19:55 bağımsız salt okunur kontrolde son tur logları, katalog, şema, 59 ürünün karşılaştırma görünümü ve Cimri geçmişi doğrulandı. Kapanış belgeleri hazır; kullanıcı commit/push işlemini onayladı; aynı SHA CI gönderim akışında doğrulanır. Sonraki iş README/teknik belge düzenlemesini ayrı planlamak; API/arayüz başlamadı. |

Kendi topladığımız geçmiş, ilk tam turdan (28 Eylül) sayılırsa Ekim sonunda
30 güne ulaşır; bu süre tek başına yeterli eğitim verisi garantisi değildir.
Cimri aktarımında (Adım 9) 57 ürünün bir yıllık tarihli serisi doğrulandı;
iki ürünün eşleştirmesi açık. Bu sonuç tek başına ML eğitimi için yeterlilik
garantisi değildir; kendi toplama serisiyle aynı ölçüm sayılmaz.
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
