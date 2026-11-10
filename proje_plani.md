# Akıllı Telefon İndirim Takip ve Tahmin Sistemi — Proje Planı

Son güncelleme: 9 Kasım 2026.

Bu belge **kararların, aşama durumunun ve sıradaki işin** tek kaynağıdır ve
kısa tutulur. Diğer bilgiler şuralardadır:

| Ne arıyorsanız | Nerede |
|---|---|
| Sistemin nasıl çalıştığı, komutlar, kurallar, hata kodları | [docs/teknik.md](docs/teknik.md) |
| Hangi adımın ne zaman yapıldığı (tarih, commit, CI) | [docs/gecmis.md](docs/gecmis.md) |
| 20 Ekim 2026'ya kadarki ayrıntılı oturum kayıtları ve kanıt açıklamaları | [docs/arsiv/proje_plani_2026-10-20.md](docs/arsiv/proje_plani_2026-10-20.md) |
| Yarım kalan iş ve anlık durum | Yerel `DEVAM.md` (Git dışında) |
| Projenin tanıtımı ve güncel kapsam sayıları | [README.md](README.md) |

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

| Aşama | Durum | Kapanış kanıtı |
|---|---|---|
| 1. Fiyat okuma (Trendyol, Hepsiburada scraper) | ✅ Uygulandı (23 Eylül) | `a36b5b6`, `b0f466c`, `a716c9a` |
| 2. Otomatik model/kapasite/renk keşfi | ✅ Uygulandı (24 Eylül) | `e00a435` |
| 3. Trendyol doğrulanmış stoksuz sayfa | ✅ Uygulandı (24 Eylül) | `e6664a3` |
| 4. Scraper/keşif kabul kontrolü (canlı veri ve tarayıcı karşılaştırması) | ✅ Tamamlandı (24–25 Eylül) | `4d5613d` |
| 5. Katalogun 25 hedefle sıfırdan kurulumu ve kod denetimi | ✅ Tamamlandı (28 Eylül) | `9528f63` |
| 6. Veritabanı ve zamanlanmış toplama (Cimri geçmişinin bir defalık aktarımı dahil) | ✅ Tamamlandı (8 Ekim) | `3c4d030`, CI 37813840435 |
| 7. FastAPI ve Streamlit | ✅ Tamamlandı (10 Ekim) | `c8d864b`, CI 38045257013 |
| ML öncesi bakım dizisi (Bakım 1–6; otomatik güvenli keşif kabulü dahil) | ✅ Tamamlandı (20 Ekim) | `7c0988b`, CI 39393708497 |
| Proje yapısının sadeleştirilmesi (Bölüm 8, Adım 1–5) | ✅ Tamamlandı (26 Ekim) | `75d4732` |
| ML öncesi ekran iyileştirmeleri 1–2 | ✅ Tamamlandı (28 Ekim) | `dd2e262`, `94045bd`, CI 40643349065 |
| Proje mühendisliğini pekiştirme | ⏸️ Pasif (28 Ekim kararı): iş sırasında değil; kullanıcı istediğinde Oturum 2'den sürer | Program aşağıda; oturum ilerlemesi yerel devir notunda |
| 8. ML (indirim tahmini) | 🔄 Hazırlık, model dondurma/saklı test ve gölge mod 6.0–6.4 tamamlandı; ilk otomatik günlük çalışma doğrulandı (6 Kasım). 7.1–7.3 tamamlandı, gönderildi ve CI doğrulandı. 6.5 izleme paralel; 7.4 uygulama, yerel testler ve kullanıcıyla görsel kabul tamam; gönderildi ve aynı SHA'nın CI'ı başarılı | Bölüm 9 ve kalan iş sırası |
| 9. Sürekli işletim ve Docker | 🔄 Sürekli işletim izleniyor; 9.2–9.4 tamamlandı, gönderim/CI kayıtları geçmişte izlenir. 9.5 API/ekran/ML bağlantısı, yapay ve gerçek kopya kabulü tamamlandı; gönderim/CI kapanışı geçmişte izlenir. Sırada 9.6 tek komutla kullanım; 9.6–9.7 henüz başlanmadı | Bölüm 9 |

Bugünkü işletim: fiyat turu her gün 10:00 ve 22:00'de, haftalık keşif her
Pazar 14:00'te (otomatik güvenli kabul modunda) Windows Görev Zamanlayıcı ile
kullanıcının bilgisayarında çalışır. Yerel API ve Streamlit ekranı elle
başlatılır. Güncel katalog ve veri sayıları [README](README.md#-güncel-kapsam)
içindedir.

Önceki aşamalardan kalan yerel taslaklar (eski `app/database`, `app/ml_model`,
`app/api`, `frontend/`, Docker dosyaları vb.) `_eski_taslaklar/` klasöründedir;
Git dışındadır, projeye bağlı değildir ve tamamlanmış iş sayılmaz.

## 3. Ürün kapsamı ve kimlik kuralları

- Platformlar Trendyol ve Hepsiburada; kategori yalnızca yeni akıllı telefon.
  25 keşif hedefi tanımlıdır (Apple 9, Samsung 8, Xiaomi 6, POCO 2); POCO X5 Pro
  satılmadığı için kapalıdır.
- Kullanıcı `config/discovery.json` içinde marka (sitedeki marka etiketi; POCO
  ayrı marka) ve tam model yazar; gerekirse `exclude_terms` ve `network`.
  Yeni telefon için Python kodu değişmez, renk bağlantısı elle toplanmaz.
- **Ürün** = marka + tam model + depolama kapasitesi. iPhone 15 128 GB ile
  256 GB farklı `product_id` alır. Pro, Plus, Pro Max, Ultra, FE, mini, Edge,
  Air, 16e ayrı hedeflerdir. **RAM ve garanti türü ürünü bölmez**; bulunabilen
  RAM ve garanti yazısı raporda bilgi olarak tutulur.
- **Bağlantı** = ürünün bir sitedeki bir sayfası (genelde bir renk). Aynı renk
  ve kapasitenin farklı sayfaları ayrı bağlantı olarak izlenebilir. Katalog
  satıcı başına adres tutmaz.
- Aynı adı taşıyan farklı telefonlar hedefteki `exclude_terms` (başlıktan) ve
  `network` (sayfanın yapısal "Mobil Bağlantı Hızı" değerinden) ile ayrılır.
  4G hedefi: `model: "Redmi Note 14 Pro"`, `network: "4G"`,
  `exclude_terms: ["5G"]` → başlıkta veya özellikte 5G yazan sayfa dışlanır,
  gerisi (alanı boş olanlar dahil) 4G sayılır. Genel bir "5G ayrı model"
  kuralı bilinçli olarak yoktur.
- Trendyol'da hedef modelde açık 5G bulunurken ürünün yapısal ağ özelliği açık
  4G/4.5G diyorsa sayfa `identity` ile reddedilir (keşif ve scraper aynı ortak
  kontrolü kullanır). Eksik/tanınmayan ağ alanı yeni sınıflandırma üretmez;
  5G'siz modelden 4G çıkarılmaz.
- Yenilenmiş, ikinci el, teşhir, yurt dışı sürüm, aksesuar ve "Yenilio
  (Outlet) A/B/C Kalite" başlıklı ürünler reddedilir.
- Keşif ve scraper aynı kimlik kuralını kullanır (`app/scraper/parsing.py →
  identify`): model, kapasite (yapısal veri + başlık; çelişki reddedilir; TB
  desteklenir) ve dışlanan ifadeler birlikte doğrulanır.
- Trendyol'da bağlantının rengi sayfanın renk seçicisindeki addır (varyant
  listesi); satıcının "Renk" özelliği yalnız yedek olarak kullanılır. Otomatik
  kabul de rengi bu addan okur; seçici adı varken satıcının genel rengi ve
  JSON-LD'deki kapasite yazan değer çelişki sayılmaz.
- Fiyat karşılaştırması aynı `product_id` içindeki takip edilen teklifler
  arasındadır; farklı kapasiteler karşılaştırılmaz.

Ayrıntılı kurallar: [teknik rehber, Kimlik kuralları](docs/teknik.md#kimlik-kuralları).

## 4. Mimari ve veri kararları

### Mimari

- Modüler yapı: scraper, keşif, kalıcılık, servis, sunum (ileride ML) ayrı
  sorumluluklardır; dosya sınırı tek sorumluluğa göre belirlenir.
- Pazaryeri HTTP istekleri yalnız `app/scraper/http.py` üzerinden, `curl_cffi`
  ve `impersonate="chrome120"` ile yapılır. Playwright, Selenium, `requests` veya
  pazaryeri için `httpx` kullanılmaz. Tek istisna: `app/ui/api_client.py`,
  HTTPX ile yalnız sabit `http://127.0.0.1:8000` yerel API adresine gider.
- HTTP katmanı: izinli alan adları, zaman aşımı, sınırlı tekrar, 3 sn istek
  aralığı, yönlendirme kontrolü, 8 MB yanıt sınırı, istek bütçesi;
  401/403/418/429 `blocked` sayılır, veri uydurulmaz, engel aşılmaz (vekil
  sunucu, adres döndürme, tarayıcı otomasyonu yok).
- Scraper sözleşmesi `fetch(listing) -> PriceObservation`; platforma özgü işler
  `get_product_data` içindedir. Yeni site mevcut scraper'a koşul eklenerek değil
  kendi modülüyle eklenir.
- Keşif scraper'dan ayrıdır: keşif bağlantı bulur, scraper fiyat ve stok okur.
  Scraper/keşif içinde SQL veya ML yapılmaz. Scraper ile veritabanını yalnız
  toplama turu (`app/collection`) bağlar; SQL `app/database` içindedir.
- Siteye giden bütün girişler (tur, keşif, Cimri alımı, canlı kontrol araçları)
  ortak dosya kilidini (`data/scrape.lock`) paylaşır; aynı anda iki süreç siteye gitmez.
- Yerel API ve ekran: yalnız bu bilgisayarda (`127.0.0.1`); API ayrı salt okunur
  veritabanı hesabıyla (`API_DATABASE_URL`, `fiyat_takip_api`) 1–4 bağlantılık
  havuzdan okur; arayüz veritabanına doğrudan bağlanmaz. Önbellek yoktur,
  ekran 30 sn'de bir yenilenir, 18 saatten eski fiyat uyarılır.

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
- İki tur ancak ürünün **cevap veren sayfa kümesi** aynıysa karşılaştırılır;
  hata cevap değildir, Tükendi gerçek cevaptır. Böylece okuma hatası sahte fiyat
  düşüşü üretmez.

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
- **Otomatik güvenli kabul:** haftalık keşif, aynı ürün koduna bağlı yeterli
  kimlik kanıtı (model, marka, kapasite, renk, yeni telefon kategorisi,
  NewCondition, gerekiyorsa ağ) bulunan adayları kendiliğinden kataloğa ekler.
  Eksik veya çelişkili adaylar gerekçeyle dışarıda kalır; süre dolması kabul
  nedeni değildir; stoksuzluk tek başına ret nedeni değildir.
- Etkin, tanımlı hedeflerin doğrulanan yeni kapasiteleri yeni ürün oluşturabilir;
  tanımlanmamış marka/model oluşturulmaz.
- Kalıcı kaldırılan bağlantının eski ürün bağı `config/discovery.json`
  `retired_listing_bindings` içinde korunur. Tam yeni kanıtla yalnız eski
  ürününe, eski `listing_id` ile dönebilir; başka ürüne taşınamaz. Katalogda
  bulunan pasif kayıt kendiliğinden açılmaz.
- Katalog Git'te kalır; otomatik eklemeler yerelde birikir, commit/push ayrı
  kullanıcı onayı ister. Otomatik Git işlemi yoktur.

## 5. Kararlar

Kalıcı kararlar, tarih ve kısa gerekçeyle. Kararın uygulanış ayrıntısı teknik
rehberde, o günkü tartışması arşivdedir.

| Tarih | Karar | Gerekçe |
|---|---|---|
| 24–25 Eylül | Trendyol model filtresi kullanılmaz; filtreler yalnız daraltma içindir, kimliği bizim kontrolümüz belirler. | Satıcı girişli, güvenilmez (iPhone 16e sayfaları "iPhone 16" etiketli); hiçbir marka 20 sayfa sınırına yaklaşmadı. |
| 24–25 Eylül | Güncel fiyat, sayfadaki koşulsuz indirimli fiyattır; birleştirme çakışmasında yalnız çakışan aday atlanır. | Kullanıcının tarayıcıda gördüğü satın alınabilir fiyat. |
| 27 Eylül | RAM ve garanti türü ürünü bölmez; yurt dışı sürümler ürün adından tanınıp kapsam dışı bırakılır. | Aynı kapasitenin farklı RAM'li sürümü görülmedi, satıcı girişleri tutarsız; garanti alanı güvenilmez (yurt dışı sürümde "Apple Türkiye Garantili" yazıyordu). |
| 27 Eylül | 4G/5G: başlıkta veya özellikte 5G yazan sayfa 5G, gerisi 4G (`network` + `exclude_terms`). | Alanı boş, başlıksız bir 5G sayfasının 4G'ye girme riski kabul edildi. |
| 27 Eylül | Trendyol rengi renk seçicisindeki addır (dili karışık, çevrilmez); POCO ayrı marka; reklam kartlarından doğan `count_mismatch` için kod değişikliği yok. | Kaynakta görülen gerçek davranış. |
| 28 Eylül | Veritabanı: PostgreSQL 17, `psycopg` 3 + ham SQL + numaralı migration, ORM yok; kullanıcının Windows bilgisayarı; günde 2 tur (10:00, 22:00); kaçan tur açılışta bir kez telafi edilir. | Kuralların veritabanında (CHECK, kısmi benzersizlik) garanti edilmesi; kullanıcının önceki deneyimi. |
| 28 Eylül | Her tur × sayfa için yalnız seçilen teklif saklanır; tek sonuç tablosu `listing_checks`; eski canlı kontrol çıktıları veritabanına aktarılmaz; elle veri eklenmez. | Satıcı bazlı geçmiş bilerek toplanmıyor; izlenemeyen eski çıktıların yanlış veri riski. |
| 30 Eylül | Cimri'nin erişilebilen bir yıllık geçmişi bir defa alınır, ayrı `market_history` tablosunda saklanır; amaç ML eğitimi. Seriler birleşmez; düzenli Cimri toplaması yapılmaz. | Kendi geçmişimiz geriye dönük toplanamaz; küçük kapsam farkları bu amaç için kabul edildi. Akakçe ilk örnekte HTTP 403 verdi. |
| 1 Ekim | Tur sonunda yalnız `network` hatası alan sayfalar bir kez yeniden okunur; ardışık 5 hatada durulur; 5xx ayrı kod almaz, `network` sayılır; `blocked` yeniden denenmez. | Bağlantı kopmaları tur içinde geri geliyordu (28 Eylül: 47 sayfa). |
| 6 Ekim | Toplama GitHub'ın bulut makinelerine taşınmaz (şimdilik). 22 Ekim denemesi aynı sonucu verdi. | Bulut denemesinde Trendyol HTTP 403 verdi; engel aşılmaz. |
| 6–7 Ekim | Kimlik kuralı değişiklikleri canlıda görülen gerçek örnek ve regresyon testi ister. Bakım 2, 4 ve 5'in önleyici düzeltmeleri için kullanıcı her maddeye ayrı istisna verdi; istisna diğer maddelere taşınmaz. | Yanlış ürün eşleşmesi sessiz veri bozulmasıdır. |
| 8 Ekim | Cimri grafiğinde aynı gün tabloda fiyat yoksa sayısal sıfır eksik (NULL) okunur, tabloyla çelişirse reddedilir; son günün fiyatı sayfadaki ilk teklif fiyatıyla değiştirilir (Cimri'nin kendi grafiği gibi). | Gerçek yanıtlar ve Cimri'nin grafik kaynak kodu incelendi. |
| 9 Ekim | API/ekran yalnız yerel; ayrı SELECT hesabı; HTTPX istisnası yalnız yerel istemci; 1–4 bağlantılık havuz; 30 sn yenileme, önbellek yok; 18 saatten itibaren eski veri uyarısı. İstatistik eşikleri: dip için 30 gün, değişkenlik için en az 14 geçiş/7 İstanbul günü, geçiş aralığı en çok 18 saat. Oran sınırlandırma (SlowAPI) dış erişim açılmadan önce ele alınacak. | Tek kullanıcı, yerel kullanım; eşikler proje kararıdır, evrensel yeterlilik iddiası değildir. |
| 13 Ekim | "Yenilio + (Outlet) + A/B/C Kalite" başlıklı ürünler kapsam dışı. | Gerçek kaynakta yenilenmiş kategorisinde oldukları görüldü. |
| 14 Ekim | Trendyol'da açık 5G model + açık 4G ürün özelliği → `identity`. | Gerçek örnek: 797850359. |
| 14 Ekim | Yeni keşif adaylarını tek tek tarayıcıda doğrulatmak rutin iş değildir; yerine yeterli kanıta dayalı otomatik kabul gelir. Her commit/push için ayrı açık onay gerekir; genel gönderim yetkisi yoktur. | Elle kontrol gün sürüyordu; gönderim kontrolü kullanıcıda kalmalı. |
| 16 Ekim | Başka modele dönen bağlantı (HBCV00008BCY51, S25 512 GB → S25+) pasife alınmak yerine katalogdan çıkarıldı; ürün ve geçmişi korunur. | Kullanıcı tercihi; kimlik bağı `retired_listing_bindings`'te korunuyor. |
| 19 Ekim | Cimri'den yeni alım/aktarım yapılmadı; mevcut kayıtlar korunur. 23 Ekim kararıyla değişti. | Resmî belgelerde projeye uygun kullanım doğrulanamadı; iki ürünün doğru Cimri sayfası bulunamadı. |
| 19 Ekim | Cimri geçmişi eksik diye ürün katalogdan çıkarılmaz; yeterli verisi olmayan ürün ileride ML tahmini dışında tutulur. | Kendi toplama verimiz ayrı değerlendirilir. |
| 19 Ekim | ML örnek kuralları: ürün başına günde bir örnek; kendi verimizde başlangıç fiyatı 22:00 turunun ürün minimumu, gelecek gün sonucu iki turda gözlenen minimum; 30 gün geçmiş + 7 gün gelecek; hedef `100 × gelecek_minimum ≤ 95 × başlangıç`; eksik etiket NULL; zaman bölümleri %70/%15/%15. | Bakım 5 veri denetimi; API gösterge eşikleri ML şartı sayılmaz. Örnek uygunluğu ve kapsam kuralı 28 Ekim kararlarıyla değişti. |
| 19 Ekim | 10:00 ve 22:00 turları korunur; sabah turunun katkısı veri birikince ölçülür. Tek tura geçiş ayrıca planlanır. | Sabah görülen düşük fiyat akşama kadar kaybolabilir; günlük örnek tek ölçüm gerektirmez. |
| 19 Ekim | Sürekli işletim, ML eğitiminden önce ayrıca planlanacak. | Bilgisayar uyuyunca/kapanınca turlar kaçıyor. |
| 19 Ekim | Haftalık keşif otomatik güvenli kabul moduna alındı (Bölüm 4, Katalog). | Kullanıcının ayrı katalog/otomasyon kabulü. |
| 20 Ekim | Test düzeni: canlı kontrol/denetim araçları `tools/` klasörüne taşınır; 29 Eylül'deki Cimri/Akakçe araştırma aracı (`market_history_probe`) ve testleri kaldırılır, görevini `python -m app.market_history capture` yapar; bulut deneme iş akışı korunur; Adım 3'ün her alt adımı ayrı commit. | Kullanıcı seçimi. |
| 22 Ekim | Otomatik kabulde Trendyol rengi renk seçicisindeki addır; seçici adı varken satıcının "Renk"i ve JSON-LD rengi karşılaştırılmaz, kapasite yazan değer renk sayılmaz. Hepsiburada değişmez. 25 Ekim keşfinden önce devreye alınır. | 19 Ekim raporu: 44 doğru Trendyol sayfası yalnız bu yüzden reddedilmişti; 109 sayfanın hepsinde seçici adı var ve hiç çelişmiyor. Değişiklik yalnız renk etiketini etkiler, ürün kimliğini değil. |
| 22 Ekim | Adım 4 kapsamı: katalog yazıcıları, zamanlanmış çalışma kopyası ve Cimri'nin kullanılmayan yolları sadeleşir; keşifteki eski kimlik kontrolü Adım 5'e taşınır; API'nin istek başı denetimi ve katalog okuma olduğu gibi kalır. | İnceleme: eski kimlik kontrolü ölü kod değil (rapor gerekçesi, Hepsiburada varyant kuyruğu); diğer iki madde gerekçesiyle "Bilerek değiştirilmeyen davranışlar"da. |
| 22 Ekim | Test dosyaları birbirinden içe aktarma yapmaz (bir test denetler); ortak fixture ve yardımcılar `tests/support/`'tadır. Yalnız `test_discovery.py` bölünür; tek konulu büyük dosyalar (toplama, Cimri, veritabanı) bölünmez. | Bölme, konu karışık olduğunda testi bulmayı kolaylaştırır; tek konulu dosyada yalnız dosya sayısını artırır. |
| 22 Ekim | Sürekli işletim için GitHub Actions + bulut PostgreSQL yolu kullanıcı isteğiyle yeniden sınandı ve kapandı: Hepsiburada okundu, Trendyol okunmadı. Toplama GitHub'a taşınmaz; engel aşılmaz. | `bulut-deneme.yml`: ilk denemede ürün verisi olmayan sayfa, teşhisli denemede HTTP 403 ve Cloudflare çerezleri; aynı iki sayfa aynı sabah evden okunmuştu. Sorun okuma kodunda değil, erişim engelinde. |
| 22 Ekim | Sürekli işletim: dizüstü sürekli açık kalır (prizde, oturum açık, ekran kilitli, kapak kapalı); prizdeyken kapak kapanınca uyumaz. Görevler ve 10:00/22:00 düzeni değişmez. 4 Kasım'da kullanıcı bilgisayarı geceleri çoğu zaman kapattığını, bazen açık bıraktığını bildirdi; karar fiilî durumla örtüşmüyor, güç ayarlarına yeni müdahale kararı yok. | Trendyol yalnız ev internetinden okunuyor; kullanıcı yeni cihaz alamıyor, eski cihazı yok. Uyku ve hazırda bekletme prizde zaten kapalıydı. |
| 23 Ekim | Cimri'den son bir defalık alım yapılır ve Cimri geçmişi ML eğitiminde kullanılır. Alım mevcut güvenli yolla (`python -m app.market_history capture`), kullanıcının terminalinden ve ayrı onayla, ML hazırlığına başlarken yapılır; sonrasında yalnız kendi verimiz birikir. Düzenli Cimri toplaması yine yoktur. | Kullanıcı kararı: proje yayınlanmayan bir staj projesi; Cimri'ye yazılan e-postaya yanıt gelmedi. Kullanım uygunluğu resmî olarak doğrulanmadı; bu bilinen sınır olarak kalır. |
| 26 Ekim | Galaxy S25 256 GB'ın `hepsiburada_hbcv0000atwvmc` bağlantısı kullanıcı onayıyla pasife alındı; katalog kaydı ve geçmişi korunur. | Tur 43–54'te kapasite doğrulanamadı; kullanıcının ekran görüntüsünde satış kapalı ve görünen bölümde kapasite yok. Ürün diğer bağlantılarıyla izleniyor. |
| 26 Ekim | Adım 5.2 davranışı koruyarak uygulanır: kullanılmayan aday üretimi kaldırılır; kabul kuralları, ayrıntılı retler ve Hepsiburada seçenek taraması korunur. | Kullanıcının kapsam seçimi ve uygulama onayı; eski yolun tamamını kaldırmak tarama kapsamını değiştirebilirdi. |
| 20 Ekim | Proje yapısı sadeleştirilecek (Bölüm 8). Plan, rehber ve kurallar yeniden düzenlenir; önceki "plan baştan yazılmaz" kuralı kaldırıldı, eski hâller arşivde. `app/market_history` kodu korunur; Git dışı inceleme kanıtları silinmeden proje dışına taşınır; renk kuralı Adım 5'te ele alınır. | Belgeler günlüğe dönmüştü (plan 374 KB, rehber 312 KB); karmaşa yönetimi zorlaştırıyordu. |
| 26 Ekim | Ekranın sıfır fiyat farkı ve satıcı bağlantısı iyileştirmeleri tek paket/commit olacak. Sıfır fark gri ve oksuz; doğrulanmış satıcı adresi yoksa açıklamayla ürün sayfası açılır. | Kullanıcının birlikte uygulama ve gösterim tercihleri; fiyat ve kabul kuralları korunur. |
| 26 Ekim | Geliştirme sırasından önce 18 oturumluk proje mühendisliği öğrenme turu yapılır; temelden, 20–30 dakikalık tek konularla, kod ve sistem değişikliği olmadan ilerlenir. | Kullanıcı projeyi pekiştirerek öğrenmek istiyor; otomatik görevler sürer, bekleyen dört işe turdan sonra dönülür. Sırası 27 Ekim kararıyla değişti. |
| 27 Ekim | Öğrenme turu geçici olarak beklemeye alınır; Claude araştırması için ML promptu tekrar hazırlanır. | Kullanıcı araştırmayı başlatmak istiyor; öğrenme programı ve geliştirme sırası korunur, kod/eğitim/alım başlatılmaz. |
| 27 Ekim | Kalan sıra: ekranın canlı kontrolü → ML raporlarının incelenmesi → öğrenme turu (Oturum 2'den) → son Cimri alımı → ML hazırlığı. | Kullanıcı öğrenmeyi ML modeline geçmeden önce tamamlamak istiyor; Cimri alımı 23 Ekim kararı gereği ML hazırlığına başlarken yapılır, tur bu ikisini ayırmaz. Sırası 28 Ekim kararıyla değişti. |
| 27 Ekim | Trendyol'da ana satıcının teklif adresi, kaydındaki satıcı kimliğinden üretilir. Önce canlı kanıt (kimlik alanı var mı, adres tarayıcıda o satıcıyı açıyor mu), sonra gerçek örnekli regresyon testiyle kod; uygulama planı ve gönderim ayrı onaylanır. | Tur 57'de 106 Trendyol fiyatının yalnız 3'ü adres aldı: ana satıcının kaydında satıcıya özel adres yok ([teknik rehber](docs/teknik.md#satıcı-teklifinin-adresi)). Kullanıcı özelliği bir kerede tamamlamak istiyor. |
| 28 Ekim | Öğrenme turu ML raporlarından önce yapılır. Kalan sıra: öğrenme turu (Oturum 2'den) → ML raporlarının incelenmesi ve ML planı → son Cimri alımı → ML hazırlığı. | Rapor incelemesi ML planına dönüşecek; kullanıcı kararları sistemi ve temel kavramları öğrendikten sonra vermek istiyor. Rapor, Cimri alımı ve ML hazırlığı art arda kalır. Oturum 17 kavramsal anlatılır. Aynı gün sonraki kararla değişti. |
| 28 Ekim | Öğrenme turu pasife alınır ve iş sırasından çıkar; kullanıcı istediğinde Oturum 2'den döner. Kalan sıra: ML raporlarının incelenmesi ve ML planı → son Cimri alımı → ML hazırlığı. | Kullanıcı projede ilerlemeyi öne alıyor; turun ML hazırlığından önce bitirilmesi şartı kalktı. |
| 28 Ekim | ML model yapısı: bütün ürünlerin satırlarını kullanan ortak model; ürün başına model yok. LightGBM baştan seçilmez: önce basit referanslar (sabit oran, basit kural, lojistik regresyon) kurulur, LightGBM ancak onları geçerse seçilir. Ürün kimliği sayı olarak verilmez; kategori olarak mı verileceği yoksa hiç mi verilmeyeceği ablasyonla belirlenir. Marka/aile bazlı model sonraki deneydir. | Cimri'de ürün başına ortalama ~31 olumlu örnek var, bazı ürünlerde 0–1. Ortak modeli literatür destekliyor (Montero-Manso & Hyndman 2021, M5); tek test dönemiyle model seçmek yanıltıcı (Ma & Fildes 2022). [Araştırma raporları](docs/arastirma/asama_08_ml/) ve kaynak denetimi. |
| 28 Ekim | Cimri ve kendi verimizin ML'deki rolü: model Cimri'de, yalnız iki kaynakta da hesaplanabilen girdilerle eğitilir ve seçilir. Kendi verimiz yalnız değerlendirme ve yeniden kalibrasyon için kullanılır (gölge mod: tahmin kaydedilir, gösterilmez). Kaynak bilgisi girdi olmaz; aynı ürün ve gün iki kaynaktan eğitime girmez; örtüşen günlerde iki kaynağın fiyat ve etiket uyumu ölçülür. | Ölçümler farklı: Cimri değeri Cimri mağazalarının günlük en düşüğüdür (`minPrice`; saati ve mağaza kümesi bilinmiyor), bizimki iki pazaryerinde 22:00 başlangıcıdır. Kendi verimiz eğitime yetmiyor. 30 Eylül (seriler birleşmez) ve 23 Ekim (Cimri eğitimde kullanılır) kararlarıyla uyumlu. |
| 28 Ekim | ML örnek uygunluğu: satır, sonucuna bakılmadan yalnız gözlem durumuna göre alınır. Gelecek 7 günün en az 6'sında fiyat gözlenmiş olmalı (gözlenen günlerde düşüş 1, yoksa 0; daha azsa NULL). Başlangıç günün 22:00 turundaki fiyattır; yoksa satır oluşmaz. Ürünün ilk gözleminden en az 30 gün geçmiş olmalı; aradaki eksik günler satırı atmaz, eksik gün oranı girdi olur. Bütün sayfaları Tükendi olan gün gözlenmemiş sayılır. Sıkı "37 günün hepsi kusursuz" kuralı duyarlılık analizi olarak kalır; hazard modeli ve eşik denemeleri sonraya bırakılır. | 28 Ekim salt okunur sayımı: 30 günün 9'unda tam iki zamanında tur yok; kusurlar bütün ürünleri vuruyor, sayfa hatası nadir (ürün×tur %97,5 hatasız). Sıkı kural kendi verimizde pratikte satır vermiyor ve yalnız sakin dönemleri bırakıyor. Sonuca göre seçim olumlu oranı şişirirdi. |
| 28 Ekim | ML kapsam kuralı: kendi verimizde birincil hedef `y_sabit`, yani gelecek minimumu yalnız başlangıçta takip edilen sayfalardan alınır. Sonradan eklenen sayfa satırı atmaz ve sahte düşüş üretmez; pasife alınan sayfa o günden sonra gözlenmemiş sayılır. Bütün izlenen sayfalardan hesaplanan `y_izlenen` ikincil rapordur; geçmişteki kapsam değişimi satırı atmaz, raporda izlenir. Cimri'de yalnız Cimri ürün kimliği değişimi satırı atar. | Keşif 43 sayfa ekledi, 60 ürünün 21'i etkilendi ve haftalık keşifle sürecek. Yeni ucuz sayfanın getirdiği düşüş gerçek indirim değildir. |
| 28 Ekim | ML ilk girdileri (yalnız 22:00 turunun bitişinde bilinen bilgi): son 1/7/14/30 gün fiyat değişim oranları; bugün / son 7 ve 30 günün en düşüğü; bugün / 30 gün ortalaması; 30 gün oynaklığı ve değişim sayısı; son ≥%5 düşüşten geçen gün (geçmiş fiyattan); haftanın günü; marka, aile, segment ve kapasite (kategori); geçmiş gün sayısı ve eksik gün oranı. "Ay" yalnız ablasyonda denenir. Kampanya takvimi, kur, enflasyon ve çıkış tarihi sonraya kalır. Stok, sayfa sayısı ve tur içi fark ilk modele girmez. Gelecek penceresine ait hiçbir bilgi girdi olmaz; TargetEncoder kullanılmaz. | Oranlar farklı fiyat düzeylerini karşılaştırılabilir yapar. Bir yıllık Cimri'de her ay bir kez geçer, "ay" ezbere yol açar. Kampanya tarihi ilan tarihi tutulmadan sızıntıdır. Stok ve sayfa bilgisi Cimri'de yok (Cimri'de eğitim kararı). sklearn 1.9.1 TargetEncoder zaman sıralı bölücüyü kabul etmiyor (her örnek doğrulamada tam bir kez olmalı). |
| 28 Ekim | ML bölme ve sızıntı: zaman sıralı %70/%15/%15 ve purge korunur; son %15 test, bütün seçimler dondurulduktan sonra tek kez kullanılır. Model seçimi ilk %85 içinde en az 4 ileri yürüyen katla yapılır (genişleyen eğitim, aylık doğrulama). Bütün ürünler aynı tarihte kesilir; kalibrasyon modelin eğitilmediği dilimde, ön işlemler yalnız eğitim kısmından öğrenilir. | Ardışık günlerin 7 günlük gelecekleri 6 gün ortaktır; rastgele bölme cevabı sızdırır. Tek dönemde iyi sonuç şans olabilir (Ma & Fildes 2022). Kampanya günleri bütün ürünleri birlikte etkiler. |
| 28 Ekim | ML başarı ölçütü: referans basamakları R0 (sabit oran), R1 (dipten uzaklık kovalarına göre basit kural), R2 (lojistik regresyon). LightGBM, R2'yi PR-AUC'de tarih bloklu bootstrap güven aralığıyla geçerse ve kalibrasyondan sonra Brier ile log loss'ta R2'den kötü değilse seçilir. Raporlananlar: PR-AUC (taban oranla), Brier, log loss, Brier skill, güvenilirlik diyagramı; marka ve ürün kırılımı (5'ten az olaylı hücre "yetersiz"); "yanlış bekle" TL kaybı ikincil rapor. | Olumlu oran ~%10; "hiç düşmez" diyen model %90 doğru görünür. PR eğrisi dengesiz veride ROC'tan bilgilendiricidir (Saito & Rehmsmeier 2015). Ardışık günler bağımsız değildir. Yalnız sabit referansı geçmek düşük bir çıtadır. |
| 28 Ekim | ML gösterim kapısı: Cimri deneyi (gösterim yok) → kendi verimizde gölge mod (tahmin kaydedilir, gösterilmez) → olasılık ekrana ancak gölge modda en az 60–90 günlük, bir kampanya ve bir sakin dönem içeren dönemde en az 30 farklı düşüş olayı, Brier skill > 0 ve büyük kalibrasyon sapması olmamasıyla çıkar. Ürün bazında geçmiş 30 günden azsa, son 14 günde eksik gün %30'u aşıyorsa veya ailesi eğitimde hiç görülmediyse "yetersiz veri" gösterilir. Ekran, olasılığın takip edilen sayfalara ve hangi 22:00 fiyatına göre olduğunu yazar. Model kaydı, yeniden eğitim ve geri alma ML hazırlığı planında. | Cimri'deki iyi sonuç, farklı ölçüm ve kapsam yüzünden kendi verimizde doğrulanmadan yeterli değildir. Eşikler proje tercihidir; gölge mod için 4 Kasım kararıyla sabitlendi. Kullanıcı bedeli kabul etti: ekranda olasılık en erken birkaç ay sonra çıkar. Sayımın başlangıcı 2 Kasım kararıyla değişti. |
| 28 Ekim | Son Cimri alımı Kasım başında, aktarım çakışması ve eşleştirme ön koşulları çözülünce yapılır; kalan sıra değişmez. Cimri serisi 9 Ekim 2025'ten alım gününe kadar uzanır (grafik alım gününden geriye en çok 366 gün verir); alım günü yarım gündür. | Kullanıcı projeyi bir ay bekletmek istemiyor. Bilinen bedel: Kasım 2026 kampanyaları Cimri verisine girmez; kendi verimizle örtüşme ~5 hafta kalır. |
| 28 Ekim | Cimri aktarımında yarım gün kuralı: günü, alım anının İstanbul tarihine eşit olan değer yarım gündür. Ortak günde yarım gün farkı çelişki sayılmaz; ilk satır korunur, fark raporlanır, ürünün yeni günleri eklenir. Tam gün farkı ve Cimri kimliği farkı çelişki kalır. Şema ve "kayıt değişmez" koruması değişmez. ML yarım günü gözlenmemiş gün sayar. | 8 Ekim satırları alım gününün 16:00 değeridir (57 satır, 5'i boş); gün sonu değeri farklı gelirse ürün tümden reddedilirdi. 8 Ekim alımları arasında 19.292 geçmiş gün değeri değişmedi. Arşivdeki 13:51 alımının önizlemesi eski kodla S24 256 GB'ı reddetti (çıkış 2), yeni kodla 1 yarım gün farkı raporladı (çıkış 0). Kullanıcı tabloyu değiştiren migration yerine bu yolu seçti. |
| 28 Ekim | Cimri eşleştirmesi 58/60: Galaxy S24 FE 128 GB, ana sayfası (`a2372356868`) ile eklenir; kimliğini son alımın kendi kontrolleri doğrular, tutmazsa ürün aktarılmaz. Galaxy S25 512 GB ve Redmi Note 14 Pro 5G 256 GB eşleştirmesiz kalır; yerlerine başka kapasite veya model konmaz. Ayrı doğrulama alımı yapılmaz. | Web aramasında S24 FE 128 GB için S25 128 GB ile aynı kalıpta ana sayfa bulundu; diğer ikisi için yine yalnız başka ürünlerin sayfaları çıktı. S25 512 GB'ın katalogda sayfası yok. Üç ürünün ailesi Cimri'de olduğu için ML engellenmez. |
| 28 Ekim | Kasım başındaki alımı beklerken önce E8DHJL kararı verilir, ardından ML hazırlığı (kalan sıra 4) mevcut Cimri verisiyle (9 Ekim 2025–8 Ekim 2026) planlanır. Alım gelince aynı adımlar uzatılmış veriyle yeniden çalıştırılır. | Kullanıcı projenin beklemesini istemiyor; model kararı gereği Cimri'de eğitilecek, mevcut bir yıllık veri hazırlığa başlamaya yeter. Sırası 2 Kasım kararıyla değişti. |
| 28 Ekim | `hepsiburada_hbcv0000e8dhjl` (Redmi Note 13 Pro 5G 256 GB) olduğu gibi katalogda kalır ve izlenir. | Başlık ve varyant 256 GB/8 GB RAM (512 GB sürüm 12 GB RAM). Fiyatı 20.999–23.999 TL (ortası 21.999) ile diğer 256 GB sayfalarıyla aynı aralıkta; 512 GB ürünün en ucuzu 23.999–25.999 TL. 26 turda hiç en ucuz sayfa olmadı. Ana kayıttaki 512 GB alanı satıcı hatası sayıldı; kesin kanıt değildir. |
| 28 Ekim | ML hazırlığının yapısı: hesaplama yeni `app/ml` paketinde (seriler, etiketler, girdiler, bölme, ölçütler, modeller, deney), SQL `app/database/ml_data.py`'de, komut `python -m app.ml`. Gerçek DB okuma hesabıyla bir kez parmak izli görüntü dosyasına okunur; etiket ve deney bu dosyadan ağsız çalışır. Kütüphaneler: numpy, scikit-learn, LightGBM (yeni `ml` grubu, kesin sürümler); pandas yok. Kendi verimizde gelecek gün, başlangıç sayfalarından o gün planlananların hepsi cevap verdiyse gözlenmiş sayılır. Adımlar 4.0–4.6 (Bölüm 9), her biri ayrı commit ve onay. | Mevcut klasör düzeni ve sorumluluk sınırları korunur. Görüntü dosyası aynı veriyle aynı sonucu verir ve testler DB istemez. Hata veren ucuz sayfa gerçek düşüşü saklayamaz. |
| 2 Kasım | 4.2 uygulama planı onaylandı: eksik diğer dilim varken tek sağlam tur gelecek günü sağlayabilir; günü aşan tur kendi diliminde eksik sayılır ve başka güne taşınmaz; başlangıç akşamında ürünün bütün planlanan sayfaları cevap vermelidir. 30 gün başlangıç dahil sayılır, eski sıkı çapraz kontrolde Cimri yarım gün maskesi iki tarafa da uygulanır. | Gözlenen minimumun anlamı korunur; kısmi akşam cevabının yanlış yüksek başlangıç üretmesi önlenir. Ayrıntılı bugünkü davranış teknik rehberde. |
| 2 Kasım | 4.3 uygulama planı onaylandı: fiyat değişimleri logaritmik oran, son ≥%5 düşüş ardışık takvim günleri arasındaki düşüş, aile nesil ve segment sürüm olacak. Girdiler etiketten bağımsız, eksikler NULL; ay ve ürün anahtarı çekirdek dışında tutulur. | Gelecek bilgisi karışmadan iki kaynakta ortak girdiler hazırlanır; formül ve sınırlar teknik rehberde sabittir. |
| 2 Kasım | Kalan sıra: bekleyen kayıt (1 Kasım keşfinin 7 sayfası ve 4.4 belgeleri) → Hepsiburada arama API'si düzeltmesi (8 Kasım keşfinden önce) → son Cimri alımı → 4.1–4.4 komutlarının uzatılmış veriyle yeniden çalıştırılması → 4.5 → 4.6. 4.5 ve 4.6 uzatılmış Cimri verisiyle yapılır. | API 1 Kasım'dan beri cevap veriyor ve canlı yanıtta iki kusur görüldü; düzeltmenin ilk canlı sınavı 8 Kasım keşfi. Alım 4.5'ten önce yapılınca modeller doğrudan güncel veriyle kurulur, aynı iş iki kez yapılmaz. |
| 2 Kasım | Hepsiburada arama API'si: ürünün ana kategori veya tanım adı yeni telefon diyorsa ürün geçer, biri aksesuar/yenilenmiş diyorsa elenir; ikinci sayfadan itibaren hedefe uyan yeni varyant yoksa sayfalama uyarısız durur, `repeated_page` yalnız sayfadaki bütün ürün kodları tekrarlanınca verilir. Ortak `phone_category` ve ürün sayfasındaki kimlik doğrulaması değişmez. | Canlı yanıtta iPhone'ların kategorisi "iPhone iOS Telefonlar" (tanımı "Cep Telefonu") olduğu için API'deki bütün iPhone'lar eleniyor, aksesuarla dolu ikinci sayfa "tekrar" sayılıyordu. Bilinen bedel: "tam" sonuç alaka sırası varsayımına dayanır. |
| 2 Kasım | Gösterim kapısının koşulları (60–90 gün, ≥30 farklı düşüş olayı, Brier skill > 0, büyük kalibrasyon sapması yok) değişmez; dönemin sayımı geriye dönük başlar. Yalnız Cimri'de seçilip dondurulan model, kendi verimizde ilk uygun başlangıç günü olan 27 Ekim'den itibaren her gün için yalnız o günün 22:00 turuna kadar bilinen veriyle tahmin üretir. Canlı gölge mod da başlar ve sayıma eklenir. Kendi verimizle yeniden kalibrasyon yapılırsa o günler değerlendirme sayımına girmez (ayrıntı gölge mod planında). Kapı Ocak başında karşılanmazsa olasılık ekrana çıkmaz. | Staj Ocak 2027'nin ilk veya ikinci haftasında bitiyor; o günkü takvimde canlı gölge modun Kasım sonunda başlaması ve yalnız ileriye dönük kaydın süreye yetmemesi bekleniyordu. Model kendi verimizi eğitimde ve seçimde görmediği için geriye dönük tahmin geçerli bir dışarıdan sınamadır; ancak zamanlayıcı ve kayıt gibi işletim parçalarını sınamaz. Kapının Ocak başında ancak sınırda karşılanabilmesi bilinen bedeldir. |
| 2 Kasım | Staj sonunda sunum yapılacak; içeriği ve biçimi sonra konuşulur. Hazırlığı takvimin son haftasındadır. | Kullanıcının staj gereksinimi. |
| 2 Kasım | 4.4 planı onaylandı: dört tam doğrulama ayı, her katta ayrı 30 gün kalibrasyon, olumlu pencere kümeleri ve %95 tarih bloklu güven aralığı; saklı testin puanlaması kapalı kalır. | Kullanıcı seçimleri: ölçülen ay kalibrasyonda görülmesin, tekrar eden olumlu satırlar olay diye sayılmasın; kesin kurallar teknik rehberde. |
| 2 Kasım | Sabah turunun katkısı ölçüldü; 10:00 ve 22:00 turları korunur (19 Ekim kararı sürer). | 2 Kasım görüntüsü, kendi serimiz (28 Eylül–25 Ekim başlangıçları, 4.2 kuralı, 30 gün şartı aranmadan): yalnız akşam turuyla kullanılabilir pencere 903'ten 508'e düşer (akşam turunun kullanılamadığı 7 gün); iki yolla da etiketlenen 508 pencerenin 8'inde (4 ürün) ≥%5 düşüşü yalnız sabah turu gördü. Veri ~5 hafta; ardışık pencereler bağımsız değil. |
| 3 Kasım | 4.5 seçim sonucunda dört kat hazır değilse “değerlendirilemedi”; dört kat hazırken hesaplanan bir koşul sağlanmıyorsa, başka koşul hesaplanamasa bile “karşılanmadı”; sağlanmayan koşul yokken eksik hesap varsa “değerlendirilemedi”; hepsi sağlanırsa “karşılandı”. | Kullanıcı sonuç görülmeden bu ayrımı onayladı: bilgi eksikliği ile sağlanmayan seçim koşulu ayrılır; NULL başarısız ölçüm sayılmaz. Kesin seçim yapılmaz; bugünkü davranış [teknik rehberde](docs/teknik.md#modeller-ve-deney-python--m-appml-experiment). |
| 3 Kasım | 4.6 uygulama planı onaylandı: mevcut 2 Kasım kanıtlarıyla sabit ayarlı ilk Cimri deneyi kullanıcı terminalinde çalıştırılır; süre/çıkış kodu kaydedilir, çıktılar yeniden eğitim olmadan doğrulanıp yorumlanır. | Başarı koşulları sonuçtan önce sabit kalır; saklı test, kendi kaynak değerlendirmesi ve kesin model seçimi sonraki ayrı adımlardadır. |
| 3 Kasım | Adım 5 uygulama planı onaylandı. Dondurulan model deney seçiminden kurala göre türetilir (`met` → LightGBM + Platt, `not_met` → R2 + Platt; bugünkü sonuç `not_met` olduğundan R2 + Platt). Saklı testte yalnız dondurulan model ve R0 puanlanır. Model pickle ile saklanır ve yalnız ön kayıtlı manifest SHA-256'sı, dosya parmak izleri ve birebir kütüphane sürümleri denetlendikten sonra açılır; yüklenen model kayıtlı kalibrasyon tahminlerini üretmelidir. Dondurma kaydı test açılmadan Git'e işlenir. Test sonucu zayıf olsa da model değişmez, gölge moda geçilir. Saklı test bir kez açılır ve seçim veya ayar için bir daha kullanılmaz. | Kullanıcı seçimleri. Kural sonuçtan önce sabittir; sonuç görüldükten sonra model değiştirmek testi bilgi vermez hâle getirir ve Cimri'de dokunulmamış başka test kalmadı. "Tek açılış" kodla zorlanmaz, ön kayıt ve bu kuralla sağlanır. Ayrıntılı davranış [teknik rehberde](docs/teknik.md#model-dondurma-ve-saklı-test-python--m-appml-freeze-final-test). |
| 4 Kasım | Gölge mod planı onaylandı (Bölüm 9, 6.0–6.5). Dondurulan R2 + Platt hiç değişmeden ve yeniden kalibrasyon olmadan kullanılır. Tahminler `data/ml/golge/` altında (Git dışı) değişmeyen, manifestli dosyalara yazılır; veritabanı tablosu ve migration yoktur. Günlük tahmin her gün 11:00'de, bilgisayar kapalıysa açılınca çalışır ve dünün 22:00 fiyatı için üretilir; kaçan gün sonraki çalışmada geç işaretiyle doldurulur. | Kullanıcı seçimleri. Ölçülen model, saklı testte sınanan modelin kendisi olur. Kullanıcı bilgisayarı geceleri çoğu zaman kapatıyor, gece görevi uygun değil; mevcut kod bir günü ancak ertesi takvim günü kapanmış sayar ve bu kural değişmez. Yeniden kalibrasyon sayım günlerini düşürürdü, 60 gün zaten sınırda. |
| 4 Kasım | Gölge mod değerlendirme kuralları sonuç görülmeden sabitlendi (28 Ekim kapısının koşulları sayıya çevrildi): satır = kendi verimiz, başlangıç 27 Ekim ve sonrası, geçmiş ≥ 30 gün, `y_sabit` etiketi 0/1; asıl sonuç yalnız "gösterilebilir" satırlarla (son 14 günde eksik gün ≤ %30, ailesi eğitimde görülmüş), tümü ikincil rapor; etiketli başlangıçların aralığı ≥ 60 takvim günü, Kasım'ın tamamını ve Kasım dışında en az 14 günü kapsar; ≥ 30 olumlu pencere kümesi; Brier skill > 0 (R0 = dondurulan modeldeki Cimri eğitim oranı); ortalama tahmin ile gerçekleşen oran farkı ≤ 0,05 ve en az 20 kayıtlı her güvenilirlik kovasında ≤ 0,15; sonuç üç durumlu (karşılandı / karşılanmadı / değerlendirilemedi). Kesin değerlendirme 5 Ocak 2027 görüntüsüyle bir kez yapılır; ara raporlar yalnız bilgi verir, kuralı, modeli veya tarihi değiştirmez. AP ve AP farkı aralığı yalnız bilgidir. | Kapı koşulları sonuç görülmeden sayıya bağlanmalı; sonradan eşik seçmek ölçümü anlamsız kılar. Eşikler proje tercihidir (28 Ekim kapısı gibi) ve plan onayıyla sabitlendi. 27 Ekim–28 Aralık 63 gündür ve Kasım kampanyalarını içerir. |
| 4 Kasım | Gölge mod 6.4 raporuna yalnız bilgi amaçlı kırılım eklenir: `missing_ratio_30d` dilimleri (≤ 0,10 ve üstü) ve 22 Kasım öncesi/sonrası. Ön kayıtlı kapı kuralları, model ve 5 Ocak 2027 tarihi değişmez. | 6.1 ölçümü: kendi satırlarında `missing_ratio_30d` eğitimden yaklaşık 5 sapma uzakta (ortalama 0,24 / 0,005) ve kaynağı 8 kusurlu gün; kapı kötü çıkarsa nedeni ayrılabilmeli. Kırılım karar değil açıklama aracıdır, sonuca bakıp kural değiştirilmez. |
| 5 Kasım | Gölge mod 6.3 ayrıntılı uygulama planı onaylandı: günlük komut ve görev kurulumu, kalıcı kanıt kopyaları ve ortak kayıt kilidi; yalnız 6.3 uygulanır. | Kullanıcının açık uygulama onayı; ilk resmi çalışma ve görev kurulumu kullanıcı terminalinde, gönderim ayrıca onaylanır. |
| 5 Kasım | 6.4 ayrıntılı uygulama planı onaylandı: süre ilk–son etiketli başlangıcın dahil takvim aralığıdır, Kasım'ın tamamı aralıkla kapsanır, Kasım dışında en az 14 farklı etiketli gün aranır. Süre/dönem/olay desteği yetersizse değerlendirilemedi; yeterli veride ölçülen başarısız performans koşulu karşılanmadı, eksik ölçü değerlendirilemedi, tümü sağlanırsa karşılandı. | Kullanıcı sayım ve üç durum yorumunu koddan önce açıkça onayladı; sayısal eşikler, model ve kesin tarih değişmedi. |
| 6 Kasım | Yol haritası öncelikleri onaylandı: R2 + Platt sabitken 6.5 haftalık performans/işletim izlemesi sürer (ilk kontrol 8 Kasım keşfi sonrası); sıradaki plan 7.1, ardından 7.2–7.4 gösterim işleri. 9.1 işletim paralel; 9.2 Docker kapsam/uygulama planı ve iş 8 sunum planda kalır. Model iyileştirmesi kalıcı sorun görülürse ayrı planlanır; 5 Ocak tarihi değişmez. | Kullanıcı önerilen sırayı kabul etti; kısa dönem sonucu nedeniyle yeni eğitime öncelik verilmedi. Bu karar ayrıntılı kod uygulaması veya commit/push onayı değildir. |
| 6 Kasım | 7.1 gösterim planı onaylandı: tek tahmin kartı; İstanbul takvimine göre yalnız dünün kaydı, eski orana dönüş yok; ayrı API ucu ve mevcut kayıttan okuma; 5 Ocak kesin raporuna bağlı komutla açılış ve kapatma. 7.1'in uygulaması yalnız kararların belgelenmesidir; API/CLI/ekran 7.2–7.4'te geliştirilir. | Kullanıcı planın uygulanmasını istedi. Seçili ürünün hangi fiyat/döneme göre değerlendirildiği açık kalır; geçersiz veya onaysız olasılık kullanıcıya çıkmaz. Commit/push onayı verilmedi. |
| 9 Kasım | [9.2 ayrıntılı Docker teslim planı](#docker-ve-teslim-hedefi-92) onaylandı: ayrı gerçek veri kopyası, tek PowerShell girişi, Docker'a özel gizli parola dosyaları ve ilk kurulumda internet; 9.3–9.7 sırası belirlendi. 9.2 yalnız planı ve çalışma kuralı istisnasını belgeler; geliştirmeler adım adım ilerler, gönderim ayrıca onaylanır. | Kullanıcı planın uygulanmasını istedi; canlı veri toplama ve dondurulan ML düzeni korunarak başka bilgisayarda tekrarlanabilir yerel web uygulaması teslim edilecek. |

### Bilerek değiştirilmeyen davranışlar

Denetimlerde incelenip gerekçesiyle olduğu gibi bırakılan davranışlar:

- Tek bir satıcının bozuk fiyatı bütün sayfayı `parse` hatası yapar. Teklifi
  atlamak, bozuk teklif en ucuzsa daha pahalı bir "en ucuz" yazdırır ve sahte
  yükseliş üretirdi; hata vermek güvenli taraftır.
- Hepsiburada fiyat isteğindeki yedek değerler yanıtla karşılaştırılmaz:
  yanıttaki fiyatın satıcı listesinden farklı olması normaldir.
- HTTP 204 sonradan `parse` olur; 304 için koşullu istek gönderilmez. POST
  yönlendirmesinde 303 GET'e çevrilmez (hiç görülmedi).
- Hiç aday bulamayan Trendyol araması uyarısız "tam" sayılır; aksi hâlde
  satılmayan model her hafta "kısmi" görünürdü.
- Elle çalıştırılan keşif raporu sabit yola (`data/discovery_report.json`),
  zamanlanmış keşif tarihli dosyaya yazar.
- Tur tamamlandıktan sonra özet sorgusu düşerse çıkış 1 olur ama tur
  `completed` kalır; kayıtlar ve kilitler korunur.
- Scraper ve keşfin iki eklenti yükleyicisi farklı sözleşmeleriyle ayrı kalır.
- API her istekte okuma hesabının yetkisini ve şemayı denetler (~20 küçük
  sorgu). Tek kullanıcılı yerel kullanımda maliyeti fark edilmez; API
  çalışırken migration uygulanır veya izin değişirse ekran yanlış veri yerine
  açık bir 503 alır.
- Katalog altı yerde okunur ama iki ayrı kuralla: veritabanı eşitlemesi
  parmak izini satır sonundan bağımsız hesaplar, keşif yazma güvenliği için
  ham baytları karşılaştırır. Tek okuyucuda birleştirmek bu farkı bozar.

## 6. Bilinen sınırlar (özet)

Ayrıntı ve kanıtları: [teknik rehber, Bilinen sınırlar](docs/teknik.md#bilinen-sınırlar).

- Hepsiburada arama API'si uzun süre HTTP 403 verdi, 1–2 Kasım'da cevap verdi
  (kalıcılığı belli değil); Hepsiburada taraması çoğunlukla "kısmi".
  Kalabalık aramalarda HTML'de ilk 36 kart görünür.
- Trendyol araması yalnız satıştaki sayfaları gösterir; stoktan çıkan sayfa
  yeniden keşfedilemez (önceden eklenmişse korunur). Reklam kartları 2–3 ürünü
  sayfalamadan düşürür.
- Bilgisayar uyuyunca veya kapanınca o saatin turu kaçar; açılışta yalnız bir
  tur telafi edilir. İnternet kesilirse sayfalar `network` hatası alır (tur sonu
  ikinci okuma kurtarabilir). Kaçan gözlem geriye dönük toplanamaz.
- Hepsiburada bir sayfanın içeriğini başka modele çevirebilir; kimlik kuralı
  bunu `identity` ile yakalar.
- Bazı Hepsiburada sayfaları ara sıra izinli alan adı dışına
  (`www3.hepsiburada.com`) gidiyor (`invalid_host`); neden doğrulanmadı.
- Ürün adında söylemeyen yurt dışı sürüm ayırt edilemez.
- Fiyat ve stok iki tur arasında değişip geri dönebilir; geçmiş, turların anlık
  görüntüleridir.
- Cimri'nin kullanım uygunluğu doğrulanmadı; iki ürünün eşleştirmesi yok;
  Cimri serisi kendi ölçümümüzle aynı kapsamda sayılmaz.
- Siteler değişebilir; "bir daha bakmaya gerek yok" garantisi verilmez.

## 7. Açık kararlar

| Konu | Durum |
|---|---|
| Sürekli işletimin doğrulanması | [Teknik rehberdeki işletim sınırı](docs/teknik.md#bilinen-sınırlar) kapanmadı; geciken turun nedeni açık. Güç ayarlarına yeni müdahale kararı verilmedi. Kullanıcı 4 Kasım'da bilgisayarı geceleri çoğu zaman kapattığını bildirdi (22 Ekim kararıyla örtüşmüyor); gölge mod görevi bu yüzden 11:00'e planlandı. |
| Staj bitişi ve sunum | Staj Ocak 2027'nin ilk veya ikinci haftasında bitiyor; kesin tarih ve sunumun biçimi/içeriği açık. Temel işler için 31 Aralık, sunum hazırlığı için 21–31 Aralık hedefi korunuyor. Docker teslimi 9 Kasım'da onaylandı ve [9.2 sözleşmesine](#docker-ve-teslim-hedefi-92) göre ilerliyor; karar beklemiyor. Kesin gösterim değerlendirmesi 5 Ocak 2027'de. |

## 8. Proje yapısının sadeleştirilmesi (tamamlandı)

Kullanıcı 20 Ekim'de projenin bütün yapısının incelenmesini ve daha düzenli,
yönetimi kolay hâle getirilmesini istedi. İnceleme sonucu: kod büyük ölçüde
sağlam; karmaşanın kaynağı günlüğe dönmüş belgeler, Git dışında birikmiş
kanıtlar ve birkaç gereksiz güvenlik katmanı. Her adım ayrı commit olur ve
kullanıcının ayrı onayıyla gönderilir; kod adımlarında bütün testler çalışır.
Zamanlanmış görevlerin komutları (`-m app.collection`, `-m app.discovery`) değişmez.

| Adım | İş | Durum |
|---|---|---|
| 1. Belgeler | Eski plan ve rehber `docs/arsiv/` altına olduğu gibi kopyalandı. İnce plan, yalnız bugünkü davranışı anlatan teknik rehber, `docs/gecmis.md`, kısa README ve sade `AGENTS.md`. | ✅ Tamamlandı (20 Ekim) |
| 2. Yerel klasörler | Biten incelemelerin kanıtları (`artifacts/`, eski `data/` kayıtları, `.scratch/`) silinmeden `C:\Users\Emir\Desktop\Staj_arsiv\2026-10-20\` klasörüne taşındı: 82 kayıt, 12.038 dosya; boyut ve SHA-256 parmak izleri taşıma öncesi ve sonrası eşleşti (`MANIFEST.json`). Kodun kullandığı `data/logs`, `data/discovery` ve rapor dosyası yerinde. Codex'in kısıtlı ortamında oluşmuş, bu hesabın içeriğini okuyamadığı beş `artifacts/b3_*` test klasörü taşınamadı ve yerinde bırakıldı (silmek için yönetici izni gerekir). | ✅ Tamamlandı (20 Ekim) |
| 3. Test düzeni | 3.1 araçlar `tools/`'a; 3.2 ortak test yardımcıları `tests/support/`'a; 3.3 `test_discovery.py` konularına göre beş dosyaya bölünür (kimlik, Trendyol, Hepsiburada, katalog, çalıştırma); 3.4 Streamlit testlerindeki 3 sn süre ve gerçek 6 sn beklemeler düzeltilir, canlı kataloğu okuyan test sabit kopyaya bağlanır; 3.5 3.2'de gözden kaçan kısa biçimli (`from test_…`) testler arası içe aktarmalar kaldırılır ve bir testle korunur. Her alt adım ayrı commit. | ✅ Tamamlandı (22 Ekim) |
| 4. Kod sadeleştirme | 4.1 keşfin iki katalog/rapor yazıcısı tek yazıcıda birleşir; 4.2 tur ve keşfin zamanlanmış çalışma kopyası (log, başlık, hata, çıkış kodu) `app/console.py`'de toplanır; 4.3 Cimri kodunun kullanılmayan eski yolları kaldırılır, alım ve aktarım korunur. Keşifteki eski kimlik kontrolü Adım 5'e taşındı; API kontrolü ve katalog okuma bilerek değiştirilmez (Bölüm 5). Her alt adım ayrı commit. | ✅ Tamamlandı (22 Ekim) |
| 5. Renk ve aday üretimi | 5.1 Trendyol rengi renk seçicisindeki addır; seçici adı varken satıcının "Renk"i ve JSON-LD rengi karşılaştırılmaz. 5.2 Adaptörler yalnız kanıt kararı `verified` ise aday döndürür; diğer sayfalarda ayrıntılı ret ve Hepsiburada seçenek taraması denetimleri korunur, atıl aday üretimi kaldırılır. Kabul kuralları ve raporun son kontrolü değişmedi. | ✅ Tamamlandı (26 Ekim) |

## Öğrenme programı: proje mühendisliğini pekiştirme

**Durum (28 Ekim):** Pasif; iş sırasında değil. Kullanıcı istediğinde
Oturum 2'den sürdürülür (Oturum 1 tamamlandı).

Kullanıcı onaylı program: temelden, kendi projemiz üzerinden 18 öğrenme
oturumu. Her oturum yaklaşık 20–30 dakika; toplam yaklaşık 6–9 saat,
kullanıcının temposuna göre bölünür. Kod yazma, satır satır kod dersi, canlı
komut veya sistem değişikliği yapılmaz. Otomatik toplama ve keşif sürer.
Mevcut belgeler, şemalar, ekranlar ve kayıtlı örnekler kullanılır.

Her oturum: problem → yöntemin ve terimlerin açıklaması → seçim, alternatif
ve bedelleri → proje örneği → iki kısa senaryo ve kullanıcının özeti.
Oturum sonunda durulur; anlaşılmayan yer farklı örnekle pekiştirilir.
Sonraki oturuma kullanıcı devam etmek istediğinde geçilir. İlerleme yalnız
`DEVAM.md`'de; temel başvuru [teknik rehber](docs/teknik.md).

| Oturum | Konu ve projedeki karşılığı | Beklenen kazanım |
|---|---|---|
| 1 | Problem, gereksinimler ve başarı ölçütü: amaç, kapsam, kullanıcı beklentisi ve doğru sonuç | Bir ihtiyacı sınanabilir kabul ölçütüne çevirmek |
| 2 | Uçtan uca harita: keşif → katalog → toplama → DB → API → ekran; ayrı Cimri kolu | Bir fiyatın yolunu ve bileşenlerin sorumluluklarını anlatmak |
| 3 | Ürün ve veri kimliği: ürün, kapasite, renk sayfası, satıcı, teklif ve ölçüm | Model/kapasite ayrımını ve renklerin aynı ürüne bağını açıklamak |
| 4 | Modüller, sözleşmeler ve ayarlar: sorumluluklar, Pydantic ve yapılandırma | Bileşenler arasındaki veri anlaşmasının neyi koruduğunu açıklamak |
| 5 | HTTP ve ağ: GET/POST, HTTPS, durum kodları, zaman aşımı ve curl_cffi | Erişim hatasıyla hatalı kaynak verisini ayırmak |
| 6 | Keşif ve ayrıştırma: HTML/JSON, BeautifulSoup, adaptörler, kimlik kanıtı ve kabul | Bağlantı bulmakla doğru fiyatı okumayı ayırmak |
| 7 | Toplama yaşam döngüsü: tur, planlanan sayfa, sonuç, yeniden deneme ve yarıda kalma | Tek sayfa hatasının tura etkisini anlatmak |
| 8 | Veritabanı: PostgreSQL, ilişkiler, anahtarlar, kısıtlar, indeks ve görünüm | Tablo ayrımını ve hatalı kayıt engellerini açıklamak |
| 9 | Kayıt güvenliği: işlem, geri alma, kapanmış kayıt ve migration | Yarım işlem riskini ve uygulanmış migration'ın değişmezliğini açıklamak |
| 10 | Fiyat karşılaştırması: minimum, eksik veri, stok, kapsam, zaman ve Cimri | Fiyat hareketinin hangi koşullarda karşılaştırılabileceğini açıklamak |
| 11 | API ve erişim: FastAPI, Uvicorn, okuma hesabı, havuz ve HTTPX istemcisi | Ekranın DB'ye doğrudan bağlanmamasının gerekçesini anlatmak |
| 12 | Sunum: Streamlit, Altair, veri yaşı, grafik, uyarı ve satıcı bağlantısı | Doğru sayının bağlamı ve sınırlamalarıyla gösterilmesini değerlendirmek |
| 13 | İşletim: Windows zamanlayıcısı, kilit, log, çıkış kodu ve güç durumu | Başarısız veya kaçan turu hangi kanıtlardan araştıracağını seçmek |
| 14 | Test: pytest, birim/entegrasyon/regresyon, sahte kaynak ve _test DB | Testin kanıtını ve canlı doğrulama ihtiyacını ayırmak |
| 15 | Ortam: Python paketleri, .venv, sürümler, ayarlar ve Docker'ın olası rolü | Sistemi başka ortamda tekrarlamak için gerekenleri açıklamak |
| 16 | Teslim: Git, commit/push, Black, Flake8, CI; kod/belge/veri/artifacts ayrımı | Bir değişikliğin inceleme, doğrulama ve gönderim yolunu anlatmak |
| 17 | ML hazırlığı: girdi, etiket, geçmiş/gelecek, veri yeterliliği ve deney | Modelden önce çözülmesi gereken veri ve değerlendirme sorularını belirlemek |
| 18 | Bütüncül çalışma: kayıtlı bir ürünün yolculuğu ve hata senaryoları | Akışı anlatıp bir sorunu ilgili bileşene kadar daraltmak |

ML ve Docker kavramsal hazırlıktır; model seçimi, eğitim veya kurulum yapılmaz.
Son oturumda fiyatın kaynaktan ekrana yolu, hata/stok/kapsam durumlarının
beklenen davranışı ve sonuca güvenmek için gereken kanıtlar açıklanır.

### Kalan iş sırası (6 Kasım kararı)

**Onaylanan öncelik:** mevcut R2 + Platt sabit tutulur; 6.5'te kayıt sağlığı ve
performans düzenli incelenirken ekran ve teslim işleri ilerler. Yeni model
eğitimi şu an öncelik değildir; daha geniş dönemde kalıcı sorun görülürse
ayrı iyileştirme planı hazırlanır. Docker ve sunum planda kalır.

**Numaraları okuma:** ana aşama **8 = ML**, ana aşama **9 = sürekli işletim ve
Docker**. ML içindeki iş 6 gölge mod, **6.0–6.5** onun alt adımlarıdır;
**6.6 yoktur**. ML'deki sonraki geliştirme iş 7 Gösterim ve alt adımları
**7.1–7.4** olur. **İş 8 — Sunum**, proje kapanışıdır; ana aşama 8 değildir.
ML hazırlığı, dondurma ve gölge modun tamamlanan adımları Bölüm 9'da;
gönderim/kapanış kanıtları [geçmiştedir](docs/gecmis.md).

Aşağıdaki öncelik sırası ve adım başlıkları onaylandı. Gösterim işinin
ayrıntılı sözleşmesi ve 9.2 Docker planı Bölüm 9'dadır. Her adımın amacı,
ilgili dosyaları ve doğrulaması başlamadan önce açıklanır; adımlar ayrı
tamamlanıp kullanıcıya sunulur. Commit/push onayı ayrıca alınır.

| Ana başlık | İş / adım | Somut çıktı | Sıra ve durum |
|---|---|---|---|
| Aşama 8 — ML | 6.5 — Gölge işletim ve performans izleme | Günlük tahmin kaydı; haftalık veri/kayıt sağlığı ve model performansı raporu; ara ve kesin değerlendirme | İzleme sürüyor. İlk haftalık kontrol 9 Kasım'da, 8 Kasım keşfi ve bugünkü 11:00 görüntüsüyle tamamlandı; görev/log, kaynak/kayıt bütünlüğü ve ara rapor doğrulandı. Hepsiburada sayfa tekrarı düzeltmesi zamanlanmış keşifte doğrulandı; kısmi kapsam sınırı sürüyor. Güncel sayılar/ölçümler README'de; kesin karar 5 Ocak. |
| Aşama 8 — ML | 7.1 — Gösterim kapsamı ve veri akışı planı | Bir ürün örneği üzerinden kayıt → API → ekran akışı; gösterilecek tarih/kapsam, kapalı gösterim ve yetersiz veri durumları; [onaylı sözleşme aşağıda](#gösterim-kalan-sıra-7-6-kasım-planı) | ✅ Tamamlandı (6 Kasım); plan onaylandı, belgelendi, gönderildi ve aynı SHA'nın CI'ı başarılı. 7.1 kod içermedi; API 7.2, ekran 7.3 kapsamındadır. |
| Aşama 8 — ML | 7.2 — API'den tahmin okuma | Kayıtlı tahmin ve yeterlilik bilgisinin doğrulanarak sunulması; eksik/bozuk kayıt ve kapalı gösterim davranışı | ✅ Tamamlandı (6 Kasım); ortak okuyucu, gösterim onayı, API ve yerel istemci uygulandı; yerel kontroller geçti. Kullanıcı onayıyla gönderildi, aynı SHA’nın CI’ı başarılı ([kayıt](docs/gecmis.md)). |
| Aşama 8 — ML | 7.3 — Ekranda tahmin durumları | Onaylı API sözleşmesine bağlı ekran; tarih/kapsam açıklamaları, yeterli/yetersiz veri ve kapalı gösterim durumları | ✅ Tamamlandı (6 Kasım); tek kart ve durum/hata açıklamaları uygulandı. Kullanıcı onayıyla gönderildi; aynı SHA'nın CI'ı başarılı ([kayıt](docs/gecmis.md)). Görsel kabul 7.4'te kullanıcıyla tamamlandı. |
| Aşama 8 — ML | 7.4 — Gösterim akışının bütün olarak doğrulanması | API/istemci/ekran uyumu, uygun ve yetersiz veri senaryoları, kapı durumları, güncel kullanım belgeleri | ✅ Tamamlandı (9 Kasım): kayıt dosyası → API → istemci → ekran testleri ve kullanım rehberi hazır; yerel tam test ve biçim kontrolleri başarılı. Yapay önizlemenin geniş/dar görünümü ve senaryo kartları kullanıcı görüntüleriyle, aralık/yenileme ve fiyat-grafik korunması kullanıcı teyidiyle doğrulandı. Kullanıcı onayıyla gönderildi; aynı SHA'nın CI tam test paketi, Black ve Flake8 kontrolleri başarılı ([kayıt](docs/gecmis.md)). |
| Aşama 9 — Sürekli işletim ve Docker | 9.1 — Sürekli işletim kanıtı | Zamanında/geç/kayıp görevlerin nedenleri ve mevcut çalışma düzeninin doğrulanması | 6.5 ile paralel sürer. 6–9 Kasım denetiminde beklenen işler zamanında tamamlandı; görev ayarı değiştirilmedi. Önceki geç turların nedeni açık kalır; güç ayarlarına yeni müdahale ayrıca kararlaştırılır. |
| Aşama 9 — Sürekli işletim ve Docker | 9.2 — Docker kapsam kararı ve planı | Teslim mimarisi, veri/model kalıcılığı, parola istisnası ve numaralı uygulama sırası | ✅ Plan belgelemesi tamamlandı (9 Kasım); [sözleşme](#docker-ve-teslim-hedefi-92). Gönderim/CI kayıtları [geçmiştedir](docs/gecmis.md); Docker kodu veya kurulum değişikliği yapılmadı. |
| Aşama 9 — Sürekli işletim ve Docker | 9.3 — İmaj ve Compose temeli | Dockerfile, .dockerignore, compose.yaml; sabit sürümler, Linux bağımlılık kilidi, kullanıcı ve ağ düzeni | ✅ Yerel uygulama/doğrulama tamamlandı (9 Kasım); gönderim/CI kayıtları [geçmiştedir](docs/gecmis.md). İmaj kuruldu; ağsız sürüm/izin, hafif API içe aktarımı, geçici pgpass, yapay bağlam dışlama ve paylaşılan localhost/Streamlit sağlığı kontrolleri geçti. Tam test ve biçim doğrulaması yapıldı; Windows dosya erişimi nedeniyle tekrarlanan senaryolar README'de açıklanır. Gerçek veri aktarılmadı. |
| Aşama 9 — Sürekli işletim ve Docker | 9.4 — Paket ve veritabanı aktarımı | Dışa aktarma, manifest doğrulama, ayrı kalıcı alanlara geri yükleme ve okuma rolü | ✅ Uygulama, yapay doğrulama ve ilk gerçek paket kabulü tamamlandı (9 Kasım). Kullanıcının dışa aktardığı paket bağımsız doğrulanıp ayrı Docker kopyasına yüklendi; veri/şema/dizi/dosya eşleşti, native kaynak değişmedi, NOLOGIN sahiplik ve API'nin SELECT/yazma yetkisi yokluğu doğrulandı. Aynı paket tekrar yüklenmedi; hazırlık kaydı ve konteyner korundu. Model/gösterim kapısı değişmedi. Test/biçim kanıtı son kodla eşleşiyor; Windows tekrar notu README'de. Kullanım [teknik rehberde](docs/teknik.md#docker-paket-ve-veritabanı-aktarımı); gönderim ve aynı SHA'nın CI kapanışı [geçmişte](docs/gecmis.md) izlenir. |
| Aşama 9 — Sürekli işletim ve Docker | 9.5 — API, ekran ve ML bağlantısı | Servislerin bağlanması, salt okunur dosyalar, aktarım tarihi bildirimi ve bakım komutu | ✅ Uygulama, yapay ve gerçek kopya kabulü tamamlandı (10 Kasım). Kullanıcının yeni paketi doğrulanıp ayrı Docker kopyasına alındı; API/UI/DB sağlıklı, gerçek HTTP ve ekran okumasında fiyat/grafikler, aralık/telefon değişimi, aktarım tarihi ve kapalı/olasılıksız tahmin doğrulandı. Native kaynak, model ve kapı korundu; RO/SELECT sınırları ve bakım sonrası tekrar hazırlama geçti. Linux'ta açma/kapatma ve güncellik yalnız yapay verilerle sınandı. Tam pytest/biçim kanıtı son kodla aynı. Kullanım [teknik rehberde](docs/teknik.md#docker-servis-bağlantısı-ve-gösterim-bakımı); gönderim ve aynı SHA'nın CI kapanışı [geçmişte](docs/gecmis.md) izlenir. 9.6'ya geçilmedi. |
| Aşama 9 — Sürekli işletim ve Docker | 9.6 — Tek komutla kullanım | PowerShell ile hazırlama, başlatma, durdurma, durum, log ve geri dönüş | 9.5 sonrası. İlk hazırlıktan sonra tek komutla sağlıklı açılış ve Türkçe hata çıktısı doğrulanacak. Henüz başlanmadı. |
| Aşama 9 — Sürekli işletim ve Docker | 9.7 — Bütün akış ve teslim kabulü | Docker CI kontrolü, temiz kurulum, kalıcılık/yenileme denemeleri ve kullanım rehberi | 9.6 sonrası. Yeni ortamda kurulum ve geri dönüş kanıtlanacak; belgeler tamamlanacak. Henüz başlanmadı. |
| Proje kapanışı | İş 8 — Sunum ve teslim hazırlığı | Sistemin akışı, örnek kullanım, sonuçlar ve sınırlar; onaylı kapsamın belgelerle teslimi | Planda kalır. Sunum iskeleti önceden hazırlanabilir; hazırlık hedefi 21–31 Aralık. Biçim ve içerik ayrıca netleştirilecek. |

**Takvim:** 7.1–7.3 tamamlandı, gönderildi ve CI doğrulandı.
7.4'ün uygulaması ve yerel/görsel doğrulaması tamamlandı; gönderildi ve aynı SHA'nın CI'ı başarılı.
[Görsel kabul adımları teknik rehberdedir](docs/teknik.md#tahmin-kartının-görsel-kabul-kontrolü).
Docker geliştirmeleri 6.5'in kapanmasını beklemez.
Temel geliştirmeler için **31 Aralık hedefi**, 21 Aralık haftasının
ara raporu ve **5 Ocak 2027 kesin değerlendirme tarihi** korunur.
Stajın kesin bitiş tarihi ve sunumun biçimi/içeriği açık karardır.
Docker bileşenleri ve başlatma/veri taşıma düzeni 9.2'de kararlaştırıldı.
Öğrenme turu iş sırasının dışında, pasif kalır (28 Ekim kararı); 7.1'de
örnek ürünle akışın açıklanması bu adımın kapsamındadır.

**Model performansına göre hareket:** günlük otomatik görev tahmin kaydeder;
performans değerlendirmesi ayrıca alınır. Haftalık raporda veri desteği,
R0 karşılaştırması, olasılık hatası ve kalibrasyon birlikte incelenir.
Kötü bir ara sonuçta veri/hesap hatası, eksik geçmiş ve kaynak farkları
kesin tarihi beklemeden araştırılır. Veri birikmesi model ağırlıklarını
değiştirmez veya başarının artacağını garanti etmez.

Daha geniş dönemde sorun sürerse ayrı model iyileştirmesi planlanır; önce
kapsam, kullanılacak veri ve yeni bağımsız değerlendirme dönemi kararlaştırılır.
Mevcut resmi kayıtlar korunur; açılmış Cimri saklı testi yeni ayar/seçim için
kullanılmaz, ayarlamada kullanılan günler tarafsız başarı kanıtı sayılmaz.
Girdi gruplarının tek tek katkısını çıkararak karşılaştıran deney henüz
yapılmadı. Kesin koşullar karşılanmazsa olasılık kapalı kalır; sonuç ve
sınırlar belgelenir.

## 9. Sonraki aşamalar

### Sürekli işletim (Aşama 9'un ilk bölümü)

Amaç, bilgisayarın uyuması veya kapanmasından doğan veri boşluklarını
azaltmak. Karar (22 Ekim): dizüstü sürekli açık kalır; prizdeyken kapak,
uyku ve ekran zamanlayıcıları uyku başlatmaz (üç ASUS güç planında; ayrıntı
[teknik rehber](docs/teknik.md#zamanlanmış-tur-görev-zamanlayıcı), 23 Ekim'de
kapak kapalıyken tur 49 ile doğrulandı). GitHub'ın makinelerinde Trendyol okunmadı (Bölüm 5), evde
ayrı cihaz yok. Görevler ve 10:00/22:00 düzeni değişmez. Etkisi birkaç gün
sonra turların zamanında başlayıp başlamadığıyla ölçülür. Docker teslim
kopyasının süreç, veri ve model kalıcılığı aşağıdaki onaylı planla
geliştirilecek; canlı Windows görevleri aynı düzende kalacak.

### Docker ve teslim hedefi (9.2)

**9 Kasım'da onaylanan sözleşme.** 9.2'nin çıktısı bu planın ve Docker
parola istisnasının belgelenmesidir. Belgeleme tamamlandı; gönderim/CI
kayıtları [geçmişte](docs/gecmis.md) tutulur. 9.3 imaj ve Compose temeli
uygulandı; [bugünkü davranış teknik rehberdedir](docs/teknik.md#docker-imaj-ve-compose-temeli).
9.4'ün paket ve DB hazırlığı, yapay doğrulama ve ilk gerçek paket kabulü
tamamlandı; gönderim durumu aşama tablosundadır. Aşağıdaki sözleşmenin
9.5'in servis bağlantısı/bakımı, yapay doğrulama ve gerçek paket kabulü
tamamlandı; gönderim durumu aşama tablosundadır. 9.6–9.7 tek komutla kullanım ve bütün
teslim kabulü **planlanmıştır, henüz uygulanmamıştır**. Her adım ayrı
tamamlanıp kullanıcıya sunulur.

#### Teslim hedefi ve kapsam

Kullanıcı, gerekli ilk veri/ayar hazırlığından sonra sistemi tek PowerShell
komutuyla başlatıp tarayıcıdan kullanacak. Streamlit, FastAPI ve PostgreSQL
Docker içinde çalışacak. Teslim; kod, veri paketi ve kullanım rehberidir.
İnternette herkese açık yayın veya `.exe` dağıtımı kapsamda değildir.

| Konu | Seçilen düzen |
|---|---|
| Ortam | Canlı sistemden ayrı Docker teslim ortamı |
| Veri | Gerçek fiyat geçmişi, dondurulan model, kanıtlar ve doğrulanmış kayıtların kopyası |
| Güncelleme | Canlı sistemden yeni paket hazırlama ve teslim ortamına kontrollü aktarma |
| Başlatma | İlk hazırlıktan sonra tek PowerShell komutu |
| İnternet | İlk kurulumda gerekli; hazırlanmış sistem sonraki açılışlarda çevrimdışı çalışabilir |
| İlk destek | Windows 11, x64, Docker Desktop ve WSL2 üzerinden Linux konteynerleri |

Windows'taki toplama, keşif ve 11:00 gölge görevleri kendi düzeninde
çalışmayı sürdürecek. Docker teslim ortamı veri toplamayacak ve günlük
tahmin üretmeyecek. Başka bilgisayarda uygulamayı açmak için Docker
hazırlığından sonra ayrıca Python/PostgreSQL kurulması gerekmeyecek;
kaynak bilgisayardaki dışa aktarma mevcut yerel araçları kullanacak.

#### Servisler, bağlantılar ve sağlık

**Tarayıcı → Streamlit → FastAPI → Docker PostgreSQL'i ve doğrulanmış
tahmin dosyaları.** Üç sürekli servis bulunacak:

| Servis | Görev ve erişim |
|---|---|
| `db` | Teslim kopyasının PostgreSQL verisini Docker ağı içinde saklar |
| `api` | Veritabanına yalnız SELECT hesabıyla bağlanır; kayıtlı fiyat ve tahmin durumunu okur |
| `ui` | Streamlit ekranını sunar; API'ye mevcut yerel istemci üzerinden erişir, veritabanı parolası almaz |

Ekran **`http://127.0.0.1:8503`** üzerinden açılacak; mevcut 8501 ekranı ve
8502 test önizlemesiyle çakışmayacak. API'nin 8000 ve veritabanının 5432
portları bilgisayara yayımlanmayacak.

Sabit `127.0.0.1:8000` istemci sözleşmesi korunacak: `ui`,
`network_mode: service:api` ile `api` servisinin ağ alanını paylaşacak.
Ekranın konteyner içindeki 8501 portunun dış eşlemesi ağ alanını sağlayan
`api` servisinde tanımlanacak. API ve ekran yeniden oluşturulurken birlikte
ele alınacak; ekran eski ağ alanında bırakılmayacak.
[Compose ağ düzeni](https://docs.docker.com/compose/how-tos/networking/).

Başlangıç sırası: DB bağlantı kabul eder → API `/health` ile şemayı,
migration durumunu ve okuma rolünü doğrular → Streamlit başlar ve kendi
sağlık ucu kontrol edilir. Kontroller bitmeden "uygulama hazır" denmeyecek.
Servisler kullanıcı komutuyla açılacak; Docker Desktop açılışına otomatik
çalışma eklenmeyecek. Sağlıklı sistemde tekrar `Start` veri aktarımını veya
servisleri gereksiz yere tekrarlamayacak.
[Compose başlangıç sırası](https://docs.docker.com/compose/how-tos/startup-order/).

#### Ortam, kalıcılık ve parolalar

- Python **3.13.15** (`python:3.13.15-slim-bookworm`) ve PostgreSQL **17.11**
  (`postgres:17.11-bookworm`) kullanılacak. Taban imajları SHA-256 özetiyle
  sabitlenecek. Linux'taki doğrudan ve dolaylı Python bağımlılıkları sürüm ve
  dosya hash'leriyle kilitlenecek; mevcut web/ML sürümleri korunacak.
  Linux kilidi Windows ortamından bağımsız hazırlanacak.
- PostgreSQL verisi, yapılandırma kopyası ve ML dosyaları ayrı, isimli kalıcı
  alanlarda tutulacak. Normal API çalışmasında yapılandırma ve ML alanları
  salt okunur bağlanacak. Durdurma ve konteyner yenileme veriyi koruyacak;
  kalıcı alanlar otomatik silinmeyecek.
  [Docker kalıcı alanları](https://docs.docker.com/engine/storage/volumes/).
- Yalnız ayrı Docker kopyası için üretilen yönetici/API parolalarının yerel
  gizli dosyalarda tutulmasına kullanıcı istisnası verildi. Compose secrets,
  geçici `PGPASSFILE`, canlı parola dosyasının taşınmaması ve çıktılarda
  parolaların bulunmaması kurallarının tek kaynağı
  [AGENTS.md — Canlı işler ve veri](AGENTS.md#canlı-işler-ve-veri) bölümüdür.
  [Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/),
  [PostgreSQL parola dosyası](https://www.postgresql.org/docs/17/libpq-pgpass.html).

#### Paket hazırlama, içe alma ve yenileme

`Export` kullanıcı tarafından çalıştırılacak:

1. Mevcut ortak kilitler kontrol edilecek; toplama, keşif veya tahmin kaydı
   yazımı sürüyorsa beklemeden durulacak. Veritabanında yarım tur bulunmadığı
   da doğrulanacak.
2. PostgreSQL 17 araçlarıyla canlı veritabanından salt okunur, tutarlı
   `pg_dump` özel arşivi alınacak.
   [PostgreSQL yedekleme sözleşmesi](https://www.postgresql.org/docs/17/app-pgdump.html).
3. İlgili yapılandırmalar, dondurulan modelin kanıt zinciri, tamamlanmış
   resmi tahmin/değerlendirme klasörleri ve bağlı kaynak görüntüleri
   kopyalanacak. Resmi dosyaların içerikleri değiştirilmeyecek.
4. Bütün kontrollerden sonra paket manifesti yazılacak: biçim sürümü,
   hazırlanma zamanı, kod commit'i, şema/migration bilgileri, model manifest
   SHA'sı ve taşınan dosyaların SHA-256 değerleri. Paket kimliği tamamlanmış
   manifestin hash'i olacak.

Parolalar, kilitler, geçici/yarım klasörler, yerel sanal ortam ve kişisel
devir dosyaları pakete alınmayacak. Paketler ve gerçek veriler Git dışında
kalacak.

İçe alma ve yenileme kuralları:

- Paket bütünlüğü ve kod uyumluluğu geri yüklemeden önce doğrulanacak.
  Her farklı paket için ayrı Docker proje/kalıcı alan grubu oluşturulacak.
- Geri yükleme yalnız Docker ağı içindeki sabit `db` adresine yapılacak;
  canlı bağlantı adresleri aktarılmayacak. İç DB adı mevcut API rolü
  sözleşmesi gereği `fiyat_takip` kalacak; ayrılık Docker ortamıyla
  sağlanacak. Şema ayrı, giriş yapamayan role ait olacak; API hesabı mevcut
  SELECT kurallarıyla kurulacak.
- Uygulanmış migration dosyaları değiştirilmeyecek; uyumsuz şema reddedilecek.
  Aynı paketin tekrar hazırlanması mevcut DB'nin üzerine yazmayacak.
- Yeni paket doğrulandıktan sonra ekran ona geçirilecek. Açılış başarısızsa
  önceki çalışan paket yeniden başlatılacak. Önceki paket ve kalıcı alanlar
  geri dönüş için korunacak.

#### Ekran ve gösterim onayı

Docker ekranında "Teslim kopyası · Veri aktarımı: … · Otomatik veri toplama
yapılmaz." bildirimi bulunacak. Yerel sunum bilgisini
`DELIVERY_MANIFEST_PATH` ayarı sağlayacak. Mevcut HTTP uçları ve cevap
şemaları değişmeyecek; normal Windows ekranı mevcut davranışını sürdürecek.

R2 + Platt, girdiler, eşikler ve resmi dosyalar korunacak. Aktarım ve API
istekleri eğitim, yeni tahmin veya pickle yüklemesi yapmayacak.
Windows'taki gösterim onayı tam Windows yolu içerdiği için pakete
alınmayacak; her yeni teslim kopyası gösterim kapalı başlayacak.

5 Ocak 2027 veya sonrasında uygun kesin rapor mevcutsa kullanıcı bakım
komutuyla mevcut `shadow-display` doğrulamasını Docker içinde
çalıştırabilecek. Onay Linux yoluyla yalnız teslim kopyasında oluşturulacak;
tarih, model ve `met` koşulları aynen uygulanacak. Erken açma seçeneği
eklenmeyecek. Açma/kapatma resmi tahmin veya değerlendirmeyi değiştirmeyecek.

#### Planlanan kullanım ve kabul kontrolleri

Tek giriş `scripts/teslim.ps1` olacak. **Bu dosya ve aşağıdaki komutlar
henüz mevcut değildir; kullanılabilir komutlar 9.6'da belgelenecek.**

| İşlem | Planlanan komut |
|---|---|
| Canlı sistemden paket hazırlama | `.\scripts\teslim.ps1 -Action Export` |
| İlk veya yeni paketi hazırlama | `.\scripts\teslim.ps1 -Action Prepare -Bundle <PAKET_KLASORU>` |
| Uygulamayı açma | `.\scripts\teslim.ps1 -Action Start` |
| Durumu görme | `.\scripts\teslim.ps1 -Action Status` |
| Logları görme | `.\scripts\teslim.ps1 -Action Logs` |
| Veriyi koruyarak kapatma | `.\scripts\teslim.ps1 -Action Stop` |
| Önceki pakete dönme | `.\scripts\teslim.ps1 -Action Rollback` |

Başlatma; Docker motorunu, hazırlanan paketi, portu ve servis sağlığını
kontrol edip ekran adresini gösterecek. İmaj ilk hazırlıkta oluşturulacak;
sonraki normal açılışlarda yeniden indirme veya kurulum gerekmeyecek.

9.7'nin zorunlu kabul senaryoları:

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

Her kod adımında tam pytest, Black ve Flake8 çalıştırılacak. Docker CI
denemesi yalnız yapay veri ve `_test` DB kullanacak; gerçek teslim paketi
CI'a gönderilmeyecek. Kullanım rehberi 9.7'de tamamlanacak.

Docker geliştirmeleri 6.5'in kapanmasını beklemez. 31 Aralık temel
geliştirme, 21–31 Aralık sunum hedefi ve 5 Ocak 2027 kesin değerlendirme
tarihi korunur. Aralık sunumunda fiyat ve grafikler çalışacak; gerçek
olasılık gösterimi kesin değerlendirmeye bağlı kalacak.

### ML

- Ortak sınıflandırma modeli; önce basit referanslar, LightGBM aday; ürün
  kimliği sayı olarak verilmez (Bölüm 5, 28 Ekim).
- Eğitim ve model seçimi Cimri'de, iki kaynakta ortak girdilerle; kendi
  verimiz değerlendirme, yeniden kalibrasyon ve gölge mod için (Bölüm 5, 28 Ekim).
- Hedef: başlangıç fiyatına göre sonraki 7 günde gözlenen minimumlardan biri
  %5 veya daha fazla düşükse 1 (kesin kural Bölüm 5, 19 Ekim). Gelecek 7
  günün en az 6'sı gözlenmeli; gelecek minimumu başlangıçta takip edilen
  sayfalardan alınır (`y_sabit`; Bölüm 5, 28 Ekim).
- İlk girdiler: ölçeksiz fiyat oranları, oynaklık ve değişim sayısı, son
  düşüşten geçen gün, haftanın günü, marka/aile/segment/kapasite, veri durumu
  (Bölüm 5, 28 Ekim). Değerlendirme: zaman sıralı %70/%15/%15, purge, ilk
  %85'te ileri yürüyen katlar, son test tek kez (Bölüm 5, 28 Ekim).
- Başarı: LightGBM ancak R0–R2 referanslarından R2'yi geçerse seçilir.
  Gösterim: Cimri deneyi → gölge mod → kapı (60–90 gün, ≥30 farklı olay,
  Brier skill > 0); ürün bazında "yetersiz veri" kuralları (Bölüm 5, 28 Ekim).
  Kapının sayımı 27 Ekim'den geriye dönük tahminlerle başlar (Bölüm 5, 2 Kasım).
- Veri durumu (23 Ekim denetimi, `tools/ml_data_check.py`; araç bugün hâlâ
  eski sıkı kuralla sayar): kendi serimizde kullanılabilir 30+7 pencere yok.
  Bütün ürünleri etkileyen kusurlu günler (17 Ekim: tur gece yarısını 5 dk
  geçti; 22 Ekim: tur 48 ertesi sabah bitti; 23 Ekim: 22:00 dilimi 24 Ekim
  02:50'de başladı) ve keşfin eklediği sayfalar sıkı sayacı sıfırlıyor; sıkı
  kuralla en erken 30 Kasım, o da yeni kusur olmazsa. 2 Kasım görüntüsünde
  de (son kapanmış gün 1 Kasım) kendi serimizde etiketli pencere yok: 30 gün
  geçmişi dolan ilk başlangıç 27 Ekim, gelecek penceresi 3 Kasım'da kapanır;
  ilk etiketler 4 Kasım veya sonrasında alınan görüntüde çıkar. Güncel
  denetim sayıları README Güncel kapsam tablosundadır.
  6 eski iPhone 16 günün hiçbirinde, 4'ü yarısından fazlasında fiyatsız (stok
  yok). Cimri, 23 Ekim kararıyla eğitimde kullanılacak. 2 Kasım son
  alımından sonra 58 ürünü ve 9 Ekim 2025–2 Kasım 2026 aralığını kapsar
  (sayılar README'de). Pencere sayıları 2 Kasım görüntüsüyle yeniden
  ölçüldü (README); olumlu oran yine ~%10. 8 Ekim ve 2 Kasım satırları yarım
  gündür; ML'de gözlenmemiş sayılır (Bölüm 5, 28 Ekim).

ML hazırlığının adımları (kalan sıra 4; yapı kararı Bölüm 5, 28 Ekim):

| Adım | İş | Durum |
|---|---|---|
| 4.0 | Bekleyen belge değişiklikleri | ✅ Tamamlandı (28 Ekim) |
| 4.1 | `ml` bağımlılık grubu, CI, salt okunur veri görüntüsü (`python -m app.ml snapshot`) | ✅ Tamamlandı (30 Ekim) |
| 4.2 | Günlük seriler ve etiketler; etiket raporu; sıkı varyantın eski araçla çapraz kontrolü | ✅ Tamamlandı (2 Kasım); gerçek görüntü, gönderim ve CI doğrulandı |
| 4.3 | Girdiler ve sızıntı testi | ✅ Tamamlandı (2 Kasım); gerçek görüntüde başlangıç eşleşmesi, gönderim ve CI doğrulandı |
| 4.4 | Zaman bölmesi (purge, ileri yürüyen katlar) ve ölçütler | ✅ Tamamlandı (2 Kasım); gerçek bölme/kat, gönderim ve CI doğrulandı |
| 4.5 | R0–R2, LightGBM, kalibrasyon ve deney raporu | ✅ Tamamlandı (3 Kasım); kod, belgeler, gönderim ve CI doğrulandı; gerçek deney 4.6'da |
| 4.6 | Son alımla uzatılmış Cimri verisiyle ilk deney; son %15 test açılmaz | ✅ Tamamlandı (3 Kasım); gerçek deney, doğrulama, yorum, belgeler, gönderim ve CI doğrulandı; kesin seçim yapılmadı |

Bu aşamada tahmin gösterilmez, gölge mod kurulmaz ve DB'ye yazılmaz; bunlar
ayrı planlardır. Son Cimri alımından sonra 4.1–4.4 komutları uzatılmış
veriyle yeniden çalıştırıldı (2 Kasım); 4.5 ve 4.6 bu veriyle yapılır
(2 Kasım kararı).

Model seçiminin dondurulması ve son testin tek kez açılması (kalan sıra 5,
3 Kasım planı); her adım ayrı commit ve onaydır:

| Adım | İş | Durum |
|---|---|---|
| 5.1 | `freeze` ve `final-test` komutları, saklı test için ayrı puanlama girişleri, güvenli model yükleme, testler ve belgeler | ✅ Tamamlandı (3 Kasım); kod, testler, belgeler, gönderim ve CI doğrulandı |
| 5.2 | Dondurma (ön kayıt): kullanıcı `freeze` komutunu çalıştırır, model SHA-256'sı ve özeti belgeye işlenir, commit/push, CI | ✅ Tamamlandı (4 Kasım); R2 + Platt donduruldu ve doğrulandı, [ön kayıt](docs/teknik.md#4-kasım-2026-dondurma-ön-kaydı) gönderildi ve CI doğrulandı; bu adımda saklı test açılmadı |
| 5.3 | Saklı testin tek kez açılması: kullanıcı `final-test` komutunu ön kayıtlı SHA ile çalıştırır; sonuç doğrulanır, belgelenir, commit/push, CI | ✅ Tamamlandı (4 Kasım); bir kez açıldı, kayıtlı tahminlerden puanlar ve güven aralığı doğrulandı, [sonuç](docs/teknik.md#4-kasım-2026-saklı-test-sonucu) belgelendi ve gönderildi, CI doğrulandı; model değişmedi |

### Gölge mod (kalan sıra 6, 4 Kasım planı)

Amaç: dondurulan R2 + Platt, kendi verimizdeki her gün için "önümüzdeki 7
günde ≥ %5 düşer mi" olasılığını üretir ve kaydeder; 7 gün sonra gerçek
sonuçla karşılaştırılır. Olasılık ekranda gösterilmez. Kararlar ve ön kayıtlı
değerlendirme kuralları Bölüm 5'te (4 Kasım). 6.0–6.4 tamamlandı; günlük
kayıt/görev kurulumu ve değerlendirme komutu uygulandı, ilk gerçek kayıt
ve rapor bağımsız doğrulandı, gönderildi ve ilgili commit'lerin CI'ı
başarılı oldu. İlk otomatik günlük çalışma da doğrulandı (6 Kasım).
6.5'in kontrol takvimi 6 Kasım kararıyla onaylandı; ilk haftalık kontrol
8 Kasım keşfi sonrasında yapılacak. İş 7 ile paralel izleme sürer.
Ayrı adımların durumu aşağıdaki tabloda gösterilir.

Günlük akış: her gün 11:00 (bilgisayar kapalıysa açılınca) → tur sürüyorsa
5 dakikada bir, en çok 90 dakika bekle → okuma hesabıyla veri görüntüsü →
dondurulan modeli ön kayıtlı SHA-256 ve kalibrasyon yeniden üretimiyle
doğrula → kendi verimizin girdilerini hesapla → kaydı olmayan her (ürün, gün)
için olasılık yaz → manifest en son. Girdi kodu yalnız `d−30…d` günlerini ve
`d` gününün 22:00 turunu okur; 11:00'de veritabanında bulunan sabah turu
girdiye girmez. Bir (ürün, gün) bir kez tahmin edilir; manifestli klasöre
yeniden yazılmaz, manifestsiz yarım klasör sayılmaz. Kayıt "kaç gün sonra
kaydedildi" bilgisini taşır (1 zamanında, daha fazlası geç; ilk toplu
doldurma geriye dönük).

Her alt adım ayrı commit ve ayrı onaydır:

| Adım | İş | Hedef | Durum |
|---|---|---|---|
| 6.0 | Kararların belgelenmesi (yalnız belge): bu bölüm ve Bölüm 5'teki 4 Kasım satırları | 5 Kasım | ✅ Tamamlandı (4 Kasım); belgeler gönderildi, CI başarılı ([kayıt](docs/gecmis.md)) |
| 6.1 | Kendi verimizin ön ölçümü (kod yok): kullanıcı `snapshot` → `labels` → `features` komutlarını tur dışında çalıştırır; 27 Ekim'den beri geçerli başlangıç sayısı, eksik/NULL gerekçeleri, "son 14 günde eksik > %30" ve eğitimde görülmemiş aileler, `history_days`/`missing_ratio_30d` dağılımının Cimri'ye göre farkı salt okunur incelenir. Model yüklenmez, tahmin üretilmez | 6 Kasım | ✅ Tamamlandı (4 Kasım); bulgular aşağıdaki risklerde ve [teknik rehberde](docs/teknik.md#bilinen-sınırlar), gönderildi, CI başarılı ([kayıt](docs/gecmis.md)) |
| 6.2 | `python -m app.ml shadow-predict`: `app/ml/shadow.py` (DB/ağ yüklemez; mevcut `load_frozen_model`, `analyze_features`, `predict_frozen` yeniden kullanılır), `config/shadow.json` (başlangıç günü 2026-10-27, ön kayıtlı model SHA-256, kanıt klasörleri), çıktı `data/ml/golge/tahmin_<zaman>/` (`predictions.jsonl`, `report.md`, `manifest.json`); yapay görüntülü testler (gelecek verisi sızmaz, yanlış SHA'da tahmin yok, 30 günden kısa geçmişe olasılık yok, mevcut anahtar yeniden tahmin edilmez, belirlenimci çıktı, DB/ağ yüklenmez); teknik rehberde "Gölge mod" bölümü | 12 Kasım | ✅ Tamamlandı (4 Kasım); kod, testler, belgeler ve gerçek görüntüyle deneme bağımsız denetimle doğrulandı, gönderildi, CI başarılı ([kayıt](docs/gecmis.md)) |
| 6.3 | `python -m app.ml shadow-daily [--scheduled]` (görüntü + tahmin, tur bekleme, `run_logged` ile `data/logs/golge_*.log`), `scripts/golge_zamanlayici_kur.ps1` (görev `\FiyatTakip\GolgeTahmin`, her gün 11:00, `StartWhenAvailable`, `-Kaldir`; `API_DATABASE_URL` yoksa kurmaz; UTF-8 BOM'lu). Kullanıcı bir kez `API_DATABASE_URL` tanımlar, ilk elle çalıştırma 27 Ekim'den dünü kadar geriye dönük doldurur, çıktı birlikte doğrulanır, görev kurulur | 16 Kasım | ✅ Tamamlandı (5 Kasım); günlük akış, ilk resmi kayıt ve bağımsız denetim, yinelenmeme ve gerçek görev kurulumu doğrulandı; gönderildi, aynı SHA için CI başarılı ([kayıt](docs/gecmis.md)) |
| 6.4 | `python -m app.ml shadow-evaluate`: yeni görüntüden etiketler, kayıtla anahtar eşleşmesi, **kayıttaki girdilerin sonraki görüntüden yeniden hesaplananlarla birebir aynı olduğu denetimi** (gerçek veride sızıntı kanıtı), `own_evaluation` rolüyle puanlar, güvenilirlik kovaları, Bölüm 5'teki kapı koşulları ve üç durumlu sonuç, Kasım/diğer günler kırılımı, `y_izlenen` ikincil rapor, işletim sağlığı (zamanında/geç/geriye dönük, eksik günler). AP farkı aralığı için `reserved_test_bootstrap` benzeri ayrı giriş eklenir; mevcut ölçüt işlevleri ve `METRIC_RULES` değişmez. Rapora yalnız bilgi amaçlı kırılım da girer: `missing_ratio_30d` dilimleri (≤ 0,10 ve üstü) ve 22 Kasım öncesi/sonrası; kapı kuralı bunlara bakmaz | 25 Kasım | ✅ Tamamlandı (5 Kasım); kod/test/belgeler, kullanıcı terminalindeki ilk rapor ve bağımsız girdi/etiket/puan/kapı denetimi doğrulandı; model/kayıtlar değişmedi, gönderildi ve aynı SHA için CI başarılı ([kayıt](docs/gecmis.md)) |
| 6.5 | İşletim ve izleme (kod yok): günlük görev kanıtı, haftalık keşif/gölge sağlığı, sunum ara raporu ve kesin değerlendirme; [kontrol planı aşağıda](#65-kontrol-planı) | İlk kontrol 6 Kasım; ilk haftalık kontrol 9 Kasım'da tamamlandı | 🔄 İzleme sürüyor; ilk otomatik ve haftalık kontrol doğrulandı. Kesin değerlendirme 5 Ocak'ta; gösterim kapalı |

#### 6.5 kontrol planı

**Amaç ve sınır:** 6.3'te kurulan görevin gerçekten çalıştığını, değişmez
tahminlerin eksiksiz biriktiğini ve 6.4 raporunun düzenli alınabildiğini
kanıtlamak. Yeni kod, görev veya model ayarı yoktur. R2 + Platt, kapı
eşikleri ve kesin değerlendirme tarihi değişmez; ML kütüphaneleri Ocak'taki
kesin değerlendirmeye kadar güncellenmez. Kurulu günlük görev mevcut
düzeninde çalışmaya devam eder; haftalık kontrol takvimi 6 Kasım
kararıyla onaylanmıştır.

**Durum ve takvim:** ilk otomatik günlük çalışma 6 Kasım'da doğrulandı.
İlk haftalık kontrol 9 Kasım'da tamamlandı: 8 Kasım keşfi, dönemin görev/logları
ve bugünkü 11:00 görevinin mevcut salt okunur görüntüsü incelendi. Yeni yerel
`shadow-evaluate` raporunda kayıt eksikliği veya yarım klasör yok; eski kayıtlar
değişmemiş. Erken performans koşulları sağlansa da veri desteği yetersizdir;
gösterim kapalı kalır. Sonuç sayıları README Güncel kapsam tablosundadır.
Haftalık kontrol 6 Kasım kararıyla 8 Kasım keşfi sonrasından itibaren her
Pazar yapılır. Aşağıdaki tarihler İstanbul saatidir; canlı komutları kullanıcı
çalıştırır, oluşan kanıtları ve salt okunur görev durumunu birlikte inceleriz.
Görev/log okuma ve rapor komutları [teknik rehberdedir](docs/teknik.md#gölge-işletiminde-kontrol-komutları).

| Ne zaman | Kontrol ve kanıt | Beklenen sonuç / doğrulama |
|---|---|---|
| 6 Kasım Cuma, 11:00 görevi tamamlandıktan sonra | Görevin son çalışma zamanı/durumu/sonucu, o çalışmanın `golge_*.log` dosyası, görüntü ve yeni tahmin manifesti | ✅ Doğrulandı: bugünkü tetikleme, `Ready`, görev sonucu ve log çıkışı 0; görüntü/kayıt/model parmak izleri, tekillik, ertesi gün kayıt ve eski dosyaların değişmediği doğrulandı ([kanıtlar](docs/teknik.md#günlük-gölge-çalışması-python--m-appml-shadow-daily)) |
| Her gün otomatik 11:00 | Mevcut görev görüntü ve tahmin üretir; ilk doğrulamadan sonra ayrıca her gün elle değerlendirme zorunluluğu yoktur | Bilgisayar kapalıysa uygun oturumda telafi; zamanında/geç kayıt bilgisi korunur |
| 8 Kasım Pazar'dan itibaren her Pazar, 14:00 keşfi gerçekten bittikten sonra | Keşif logu/raporu, haftanın gölge logları ve yeni salt okunur görüntüyle `shadow-evaluate` raporu | Kaynak sorunları ve gölge kayıt sağlığı ayrı incelenir; ilk Pazar Hepsiburada arama düzeltmesinin tam canlı sonucu da doğrulanır |
| 21 Aralık haftası | Aynı komutlarla yeni ara rapor; sunum için veri yeterliliği, ölçümler ve sınırlar | Bilgi amaçlı sonuç; erken kapı kararı veya model ayarı yapılmaz |
| 5 Ocak 2027 Salı, çalışan işler tamamlandıktan sonra | **O gün alınmış tek kesin görüntüyle** kesin değerlendirme ve kanıt dosyalarının korunması | Ön kayıtlı üç durumlu kapı sonucu belgelenir; komut ekranı kendiliğinden açmaz |

**İlk otomatik çalışma kontrolü:** kurulum çıktısı veya eski bir `LastTaskResult = 0`
yeterli değildir; son çalışma zamanı, log tarihi ve `(zamanlanmış)` başlığı
aynı çalışmayı göstermelidir. Görev hâlâ çalışıyorsa tur/keşif bekleme
satırlarına bakılır, tamamlanmadan sonuç verilmez. Yeni tahmin yoksa bu tek
başına hata değildir; görüntüdeki uygun başlangıçların önceden kayıtlı olup
olmadığı kontrol edilir. İlk tetikleme sorununu örtecek elle çalıştırmadan
önce görev ve log kanıtı korunur. 22:00 ve 10:00 fiyat turları için bilgisayar
açık, uyanık ve oturum açık tutulur; kilit ekranı uygundur. Sonradan çalışan
gölge görevi, kaçmış bir turun geçmiş fiyatlarını geri getiremez.

**Haftalık raporda bakılacaklar:**

- Haftadaki her günün zamanlanmış logu ve son çıkışı kontrol edilir; eksik
  log, kapanmamış log veya hata ayrıca araştırılır. Keşfin yaklaşık bitiş
  saati yeterli kanıt değildir; bitiş logu/görev durumu görülür. Yeterli
  kimlik kanıtıyla otomatik kabul edilen bağlantılar tek tek elle doğrulanmaz.
- `health.missing_records` boş olmalıdır: başlangıcı bulunup resmi tahmini
  olmayan ürün-günler araştırılır. `no_start_price`, `not_yet_observed` ve
  NULL etiketler ayrı okunur; sabit günlük ürün/kayıt sayısı beklenmez.
- Yarım klasörler ile zamanında, ilk toplu doldurma ve geç kayıt sayıları
  incelenir. Önceki rapordaki kayıt manifest SHA-256'ları yeni raporun
  `input.records` envanteriyle karşılaştırılır; eski kayıtlar aynı kalmalı,
  yeni klasörler ayrıca görünmelidir. Bütünlük uyuşmazlığı normal kabul edilmez.
- Asıl topluluğun veri desteği, kapı sonucu ve ölçümleri okunur; ikincil
  etiketler ve kırılımlar yalnız açıklamadır. Kısa dönemde NULL güven aralığı
  veya `Değerlendirilemedi` geçerli rapor sonucu olabilir; çıkış 0 modelin
  gösterim koşullarını karşıladığını söylemez. Erken iyi/kötü puana göre
  model, eşik veya kesin tarih değiştirilmez.

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

**İlerleme ve kapanış:** ilk otomatik çalışma ile ilk haftalık kontrolün
kanıtları doğrulanınca durum "izleme sürüyor" olur; planın hazırlanması
6.5'i tamamlamaz. Ara raporlar korunur; 5 Ocak kesin sonucu belgelenince
işletim adımı kapatılır, kapı karşılanmadıysa veya değerlendirilemediyse
olasılık gösterilmez. 5 Ocak görüntüsünde son kapanmış gün 4 Ocak olduğundan
en geç 28 Aralık başlangıcının 7 günlük sonucu kapanmış olabilir; 27 Ekim–28
Aralık 63 gün olması veri/olay desteğini garanti etmez. Tek kesin
değerlendirme işletim kuralıdır; tarih alanı bunu teknik olarak zorlamaz.
Kanıtlar `data/` ve `artifacts/` altında kalır; yeni sınır teknik rehbere,
karar ana plana, süren iş yerel devir notuna yazılır. Her gönderim ayrıca
açık onay ister.

Bilinen riskler (6.1 ölçümü, 4 Kasım 2026 12:57 UTC görüntüsü):

- 27 Ekim–28 Aralık 63 gündür; 60 gün sınırda (üç gün pay). ≥ 30 farklı olay
  için kaba öngörü 29–39 (eşik 30): kendi serimizde 28 Eylül–27 Ekim arası
  1.050 örnekte %7,6 olumlu ve 22 küme; Cimri oranıyla 29. Öngörü 8 kusurlu
  günü de içerir, yani sınırdadır; sağlanmazsa olasılık ekrana çıkmaz.
- Kapsam: 60 üründen 11'i 22:00'de hep stoksuz (iPhone 15 Pro 128/256/1024,
  15 Pro Max 512/1024, iPhone 16 256/512, 16 Pro 256/512/1024, Galaxy S25
  512 GB); başlangıçları olmadığından tahmin almazlar, en çok 49 ürün. Günlük
  "gösterilebilir" ürün 44–48; S24 FE 128 GB geçmişi yaklaşık 17 Kasım'a kadar
  30 günden azdır. 13 aile de eğitimde görülmüştür.
- Kendi başlangıçlarımız yok olan 8 gün: 30 Eylül; 2, 3, 4, 6, 17, 22, 23
  Ekim. 24 Ekim'den beri her gün 48–50 ürünün başlangıcı var.
- Girdi kayması: kendi satırlarında `missing_ratio_30d` ortalaması 0,24
  (eğitimde 0,005; 14.923 satırın 14.649'unda sıfır, sapma 0,048, yani yaklaşık
  5 sapma uzaklık) ve `history_days` 30–37 (eğitim medyanı 159, satırların %3'ü
  30–37). Dondurulan R2'nin katsayılarıyla tahmini ortalama lojit kayması
  yaklaşık +0,9, Platt sonrası yaklaşık +0,3. Bu doğrusal bir yaklaşımdır;
  gerçek etki gölge modda görülür. Kaynak yukarıdaki 8 kusurlu gündür: 22
  Kasım'dan itibaren 30 günlük pencereler bu günleri içermez (yeni kusurlu gün
  çıkmazsa). Yeniden kalibrasyon yoktur; sapma kapıda görünür. 6.4 raporu
  nedeni ayırmak için bilgi amaçlı kırılım taşır.
- Model Cimri'nin günlük en düşük fiyatıyla eğitildi, kendi serimiz 22:00
  turudur; olasılık ölçeği ayrıca bu yüzden kayabilir.
- 11:00 tahmini, tahmin penceresinin ilk sabah turundan sonra kaydedilir. Kod
  o veriyi okumaz (test ve 6.4 denetimi), ama "gelecek veri oluşmadan
  kaydedildi" denmez.
- Kayıt yerel ve imzasızdır; parmak izi yalnız bütünlük kontrolüdür.
- Python, NumPy, scikit-learn veya LightGBM sürümü değişirse dondurulan model
  yüklenmez (bilinçli güvenlik); yeniden dondurma yeni bir model sayılır.

### Gösterim (kalan sıra 7, 6 Kasım planı)

**7.1'in onaylı çıktısı bu sözleşmenin belgelenmesidir.** Aşağıdaki API,
okuyucu, komut ve istemci 7.2'de tamamlandı, gönderildi ve CI doğrulandı. Kart
7.3'te tamamlandı, gönderildi ve CI doğrulandı. 7.4'te kayıt dosyasından
ekrana kadar otomatik doğrulama, kullanım rehberi ve kullanıcıyla görsel
kabul tamamlandı; gönderildi ve aynı SHA'nın CI'ı başarılı.
R2 + Platt, girdiler ve değerlendirme eşikleri değişmez. İlk sürümde seçili
telefon için tek tahmin kartı vardır; tahmin geçmişi listesi/grafiği yoktur.

#### Veri akışı ve API sözleşmesi

**Günlük resmi kayıt → kayıt ve kaynak görüntü doğrulaması → API → kart.**
Uç `GET /api/v1/products/{product_key}/prediction` olarak uygulandı. Mevcut
ürün cevabı değişmez; tahmin hatası fiyat ekranını kapatmaz. API kayıtlı
tahmini okur; model yüklemez, eğitim veya yeni tahmin çalıştırmaz.

Gölge kayıt doğrulayıcıları NumPy/scikit-learn bağımlılığı olmayan
`app/ml/shadow_records.py` modülüne ayrıldı. Mevcut CLI sözleşmeleri ve
resmi dosya biçimi korunur. Yalnız manifesti tamamlanmış resmi klasörler
kullanılır; hash, model kimliği ve ürün-gün tekilliği doğrulanır. Yarım
klasörler kullanılmaz. Başlangıç fiyatı ve sayfa kapsamı, manifestteki SHA
ile eşleşen kaynak görüntüden mevcut günlük seri kurallarıyla çıkarılır;
güncel fiyat başlangıç fiyatının yerine geçmez.

Cevap `state`, `reasons`, `forecast`, `generated_at` alanlarını taşır:

| `state` | Anlamı | `forecast` |
|---|---|---|
| `closed` | Gösterim onayı yok veya kapatılmış | `null` |
| `unavailable` | Beklenen gün için kayıt yok | `null` |
| `insufficient_data` | Mevcut veri yeterliliği kuralları sağlanmıyor | `null` |
| `available` | Onaylı, güncel ve yeterli kayıt var | Tahmin bilgileri |

`forecast`; olasılık, model adı, başlangıç günü/saati, başlangıç fiyatı,
tahmin dönemi, kayıt zamanı ve başlangıç kapsamındaki sayfa sayısını taşır.
Para ve zamanlar mevcut API sözleşmesindeki birimlerle aktarılır.

**Güncellik:** İstanbul takvimine göre dünün başlangıç günü aranır. Daha
eski kayda dönülmez; 11:00 çalışması tamamlanmadan güncel kayıt bulunmadığı
açıklanabilir. Bozuk kayıt, kaynak uyuşmazlığı veya okunamayan dosya güvenli
`503` cevabı üretir; istemci hatayı yalnız tahmin kartında gösterir.

#### Kart ve gösterim onayı

Kart, **Güncel sonuç** bölümünden sonra ve fiyat istatistiklerinden önce
yer alır. Gösterim açıkken olasılık bir ondalık basamakla yüzde olarak
sunulur. Başlangıç fiyatı, gerçek akşam turu zamanı ve tahmin dönemi açıkça
yazılır; "Takip edilen başlangıç sayfaları kapsamında en az %5 düşüş"
açıklaması bulunur. Grafik aralığı seçimi tahmin dönemini değiştirmez.

Gerçek örnek: iPhone 15 128 GB'ın 5 Kasım kaydı, o akşamki **56.649 TL**
başlangıç fiyatına ve **6–12 Kasım** dönemine aittir. Kaynak görüntü
`data/ml/golge/goruntuler/veri_20261106_110023_673048/`, kayıt
`data/ml/golge/tahmin_20261106_110023_673048/predictions.jsonl` içindedir.
Gösterim kapalıyken bu kaydın olasılığı API'ye veya karta çıkarılmaz.

Gösterim varsayılan kapalıdır. Açılış komutu
`python -m app.ml shadow-display --evaluation <KESIN_RAPOR_KLASORU>`:

- Rapor bütünlüğünü, ön kayıtlı modeli, görüntünün İstanbul tarihinin
  **5 Ocak 2027** olmasını ve kapı sonucunun `met` olmasını doğrular.
  Çalıştırma tarihi de 5 Ocak veya sonrası olmalıdır.
- Başarılı doğrulama kayıt kökünde `gosterim_onayi.json` oluşturur; onay
  kesin rapor ve model SHA değerlerine bağlanır. Başka raporla sessizce
  değiştirilmez; başarısız komut onay oluşturmaz.
- `shadow-display --disable` gösterimi tekrar kapatır. Bu işlemler resmi
  tahmin veya değerlendirme dosyalarını değiştirmez.

Komutlar 7.2'de uygulandı; bugünkü tarih açılışa izin vermez. Gerçek
gösterim kapalıdır. Güncel alanlar, çıkış kodları ve kullanım
[teknik rehberdedir](docs/teknik.md#tahmin-gösterim-onayı-python--m-appml-shadow-display).

#### Uygulama sırası ve kabul kontrolleri

- **7.2:** ortak okuyucu, gösterim onayı komutu, API ve yerel istemci
  sözleşmesi. **7.3:** kart, durum açıklamaları ve tahmin hatasının fiyat
  ekranından ayrılması. **7.4:** bütün akış ve kullanım belgeleri.
- Her kod adımında tam test ve biçim kontrolleri yapılır. Gösterim kapalıyken
  cevapta olasılık bulunmaması; yeni günde eski oranın kaybolması ve yeni
  kayıtla yenilenmesi sınanır.
- Kısa geçmiş, fazla eksik gün, eğitimde görülmemiş aile; bozuk hash,
  yabancı model, yinelenen anahtar ve eksik kaynak görüntü sınanır.
- Uygun olmayan raporla açılışın reddi ve kapatmanın etkisi; telefon
  değişiminde/API hatasında önceki olasılığın kalmaması sınanır.
- İstek sırasında eğitim, tahmin, pickle yükleme veya dış ağ erişimi
  yapılmadığı denetlenir.

7.2–7.4, 6.5 kapanmadan sırayla ilerleyebilir. 31 Aralık temel işler hedefi,
6.5 haftalık izleme, 9.1 işletim kontrolleri, Docker 9.3–9.7 işleri ve sunum
hazırlığı korunur. Kesin gösterim kararı **5 Ocak** değerlendirmesine bağlıdır.

## 10. Çalışma ve Git disiplini

Çalışma kuralları [AGENTS.md](AGENTS.md) dosyasındadır: adım adım ilerleme ve
her adımdan sonra durma, canlı komutları kullanıcının çalıştırması, gerçek
veritabanına yalnız okuma, her commit/push için ayrı açık onay, yazarın yalnız
kullanıcı olması (yapay zekâ imzası yok).
