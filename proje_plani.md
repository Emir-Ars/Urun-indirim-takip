# Akıllı Telefon İndirim Takip ve Tahmin Sistemi — Proje Planı

Son güncelleme: 22 Ekim 2026.

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
| Proje yapısının sadeleştirilmesi (Bölüm 8, Adım 1–5) | 🔄 Sürüyor (20 Ekim'de başladı) | — |
| 8. ML (indirim tahmini) | 🔜 Planlandı, başlanmadı | Bölüm 9 |
| 9. Sürekli işletim ve Docker | 🔄 Sürekli işletim kararı verildi (22 Ekim: dizüstü sürekli açık); Docker başlanmadı | Bölüm 9 |

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
| 19 Ekim | Cimri'den yeni alım/aktarım yapılmadı; mevcut kayıtlar korunur. | Resmî belgelerde projeye uygun kullanım doğrulanamadı; iki ürünün doğru Cimri sayfası bulunamadı. |
| 19 Ekim | Cimri geçmişi eksik diye ürün katalogdan çıkarılmaz; yeterli verisi olmayan ürün ileride ML tahmini dışında tutulur. | Kendi toplama verimiz ayrı değerlendirilir. |
| 19 Ekim | ML örnek kuralları: ürün başına günde bir örnek; kendi verimizde başlangıç fiyatı 22:00 turunun ürün minimumu, gelecek gün sonucu iki turda gözlenen minimum; 30 gün geçmiş + 7 gün gelecek; hedef `100 × gelecek_minimum ≤ 95 × başlangıç`; eksik etiket NULL; zaman bölümleri %70/%15/%15. | Bakım 5 veri denetimi; API gösterge eşikleri ML şartı sayılmaz. |
| 19 Ekim | 10:00 ve 22:00 turları korunur; sabah turunun katkısı veri birikince ölçülür. Tek tura geçiş ayrıca planlanır. | Sabah görülen düşük fiyat akşama kadar kaybolabilir; günlük örnek tek ölçüm gerektirmez. |
| 19 Ekim | Sürekli işletim, ML eğitiminden önce ayrıca planlanacak. | Bilgisayar uyuyunca/kapanınca turlar kaçıyor. |
| 19 Ekim | Haftalık keşif otomatik güvenli kabul moduna alındı (Bölüm 4, Katalog). | Kullanıcının ayrı katalog/otomasyon kabulü. |
| 20 Ekim | Test düzeni: canlı kontrol/denetim araçları `tools/` klasörüne taşınır; 29 Eylül'deki Cimri/Akakçe araştırma aracı (`market_history_probe`) ve testleri kaldırılır, görevini `python -m app.market_history capture` yapar; bulut deneme iş akışı korunur; Adım 3'ün her alt adımı ayrı commit. | Kullanıcı seçimi. |
| 22 Ekim | Otomatik kabulde Trendyol rengi renk seçicisindeki addır; seçici adı varken satıcının "Renk"i ve JSON-LD rengi karşılaştırılmaz, kapasite yazan değer renk sayılmaz. Hepsiburada değişmez. 25 Ekim keşfinden önce devreye alınır. | 19 Ekim raporu: 44 doğru Trendyol sayfası yalnız bu yüzden reddedilmişti; 109 sayfanın hepsinde seçici adı var ve hiç çelişmiyor. Değişiklik yalnız renk etiketini etkiler, ürün kimliğini değil. |
| 22 Ekim | Adım 4 kapsamı: katalog yazıcıları, zamanlanmış çalışma kopyası ve Cimri'nin kullanılmayan yolları sadeleşir; keşifteki eski kimlik kontrolü Adım 5'e taşınır; API'nin istek başı denetimi ve katalog okuma olduğu gibi kalır. | İnceleme: eski kimlik kontrolü ölü kod değil (rapor gerekçesi, Hepsiburada varyant kuyruğu); diğer iki madde gerekçesiyle "Bilerek değiştirilmeyen davranışlar"da. |
| 22 Ekim | Test dosyaları birbirinden içe aktarma yapmaz (bir test denetler); ortak fixture ve yardımcılar `tests/support/`'tadır. Yalnız `test_discovery.py` bölünür; tek konulu büyük dosyalar (toplama, Cimri, veritabanı) bölünmez. | Bölme, konu karışık olduğunda testi bulmayı kolaylaştırır; tek konulu dosyada yalnız dosya sayısını artırır. |
| 22 Ekim | Sürekli işletim için GitHub Actions + bulut PostgreSQL yolu kullanıcı isteğiyle yeniden sınandı ve kapandı: Hepsiburada okundu, Trendyol okunmadı. Toplama GitHub'a taşınmaz; engel aşılmaz. | `bulut-deneme.yml`: ilk denemede ürün verisi olmayan sayfa, teşhisli denemede HTTP 403 ve Cloudflare çerezleri; aynı iki sayfa aynı sabah evden okunmuştu. Sorun okuma kodunda değil, erişim engelinde. |
| 22 Ekim | Sürekli işletim: dizüstü sürekli açık kalır (prizde, oturum açık, ekran kilitli, kapak kapalı); prizdeyken kapak kapanınca uyumaz. Görevler ve 10:00/22:00 düzeni değişmez. | Trendyol yalnız ev internetinden okunuyor; kullanıcı yeni cihaz alamıyor, eski cihazı yok. Uyku ve hazırda bekletme prizde zaten kapalıydı. |
| 20 Ekim | Proje yapısı sadeleştirilecek (Bölüm 8). Plan, rehber ve kurallar yeniden düzenlenir; önceki "plan baştan yazılmaz" kuralı kaldırıldı, eski hâller arşivde. `app/market_history` kodu korunur; Git dışı inceleme kanıtları silinmeden proje dışına taşınır; renk kuralı Adım 5'te ele alınır. | Belgeler günlüğe dönmüştü (plan 374 KB, rehber 312 KB); karmaşa yönetimi zorlaştırıyordu. |

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

- Hepsiburada arama API'si HTTP 403 veriyor; Hepsiburada taraması her zaman
  "kısmi". Kalabalık aramalarda ilk 36 kart görünür.
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
| Son bir Cimri alımı | Kullanıcı fikri (20 Ekim): örneğin 1 Kasım civarında son bir alım yapıp sonrasında yalnız kendi verimizle devam etmek. 19 Ekim incelemesinde kullanım uygunluğu doğrulanamadığı için **karar bekliyor**; yapılırsa ayrı onay ve mevcut güvenli aktarım yolu kullanılır. Son alım kendi serimizdeki boşlukları doldurmaz. |
| Keşifteki eski kimlik kontrolü | Döndürdüğü aday hep atılıyor; ret gerekçesi ve Hepsiburada varyant taraması ona bağlı; ~80 test durumu atılan adayı sınıyor. Adım 5.2 olarak 25 Ekim keşfinden sonra ayrı planla ele alınacak (planlandı). |
| HBCV0000E8DHJL | Başlık/varyant 256 GB, ana ürün alanı 512 GB. Mevcut bağlantıya müdahale **karar bekliyor**. |
| `hepsiburada_hbcv0000atwvmc` (Galaxy S25 256 GB) | Tur 43–47'de (20–22 Ekim) üst üste `identity`: sayfa adları yalnız "Samsung Galaxy" / "Samsung Galaxy S25", kapasite yok; tur 42'ye kadar 50.000 TL okunuyordu. Ürün diğer 13 sayfasıyla izleniyor (en ucuzu bu sayfa değildi). 25 Ekim keşif raporundaki kanıtla sayfanın tutulması/pasife alınması **karar bekliyor**. |
| ML ayrıntıları | Özellikler, değerlendirme yöntemi, Cimri verisinin kullanılıp kullanılmayacağı ML aşamasında kararlaştırılacak. |

## 8. Sıradaki işler: proje yapısının sadeleştirilmesi (20 Ekim kararı)

Kullanıcı 20 Ekim'de projenin bütün yapısının incelenmesini ve daha düzenli,
yönetimi kolay hâle getirilmesini istedi. İnceleme sonucu: kod büyük ölçüde
sağlam; karmaşanın kaynağı günlüğe dönmüş belgeler, Git dışında birikmiş
kanıtlar ve birkaç gereksiz güvenlik katmanı. Her adım ayrı commit olur ve
kullanıcının ayrı onayıyla gönderilir; kod adımlarında bütün testler çalışır.
Zamanlanmış görevlerin komutları (`-m app.collection`, `-m app.discovery`) değişmez.

| Adım | İş | Durum |
|---|---|---|
| 1. Belgeler | Eski plan ve rehber `docs/arsiv/` altına olduğu gibi kopyalandı. İnce plan, yalnız bugünkü davranışı anlatan teknik rehber, `docs/gecmis.md`, kısa README ve sade `AGENTS.md`. | ✅ Tamamlandı (20 Ekim) |
| 2. Yerel klasörler | Biten incelemelerin kanıtları (`artifacts/`, eski `data/` kayıtları, `.scratch/`) silinmeden `C:\Users\Emir\Desktop\Staj_arsiv\2026-10-20\` klasörüne taşındı: 82 kayıt, 12.038 dosya; boyut ve SHA-256 parmak izleri taşıma öncesi ve sonrası eşleşti (`MANIFEST.json`). Kodun kullandığı `data/logs`, `data/discovery` ve rapor dosyası yerinde. Codex'in kısıtlı ortamında oluşmuş, bu hesabın içeriğini okuyamadığı beş `artifacts/b3_*` test klasörü taşınamadı ve yerinde bırakıldı (silmek için yönetici izni gerekir). | ✅ Taşıma tamam (20 Ekim); belge notlarının gönderimi bekliyor |
| 3. Test düzeni | 3.1 araçlar `tools/`'a; 3.2 ortak test yardımcıları `tests/support/`'a; 3.3 `test_discovery.py` konularına göre beş dosyaya bölünür (kimlik, Trendyol, Hepsiburada, katalog, çalıştırma); 3.4 Streamlit testlerindeki 3 sn süre ve gerçek 6 sn beklemeler düzeltilir, canlı kataloğu okuyan test sabit kopyaya bağlanır; 3.5 3.2'de gözden kaçan kısa biçimli (`from test_…`) testler arası içe aktarmalar kaldırılır ve bir testle korunur. Her alt adım ayrı commit. | ✅ Tamamlandı (22 Ekim) |
| 4. Kod sadeleştirme | 4.1 keşfin iki katalog/rapor yazıcısı tek yazıcıda birleşir; 4.2 tur ve keşfin zamanlanmış çalışma kopyası (log, başlık, hata, çıkış kodu) `app/console.py`'de toplanır; 4.3 Cimri kodunun kullanılmayan eski yolları kaldırılır, alım ve aktarım korunur. Keşifteki eski kimlik kontrolü Adım 5'e taşındı; API kontrolü ve katalog okuma bilerek değiştirilmez (Bölüm 5). Her alt adım ayrı commit. | ✅ Tamamlandı (22 Ekim) |
| 5. Renk kuralı | 5.1 Otomatik kabulde Trendyol rengi renk seçicisindeki addır; seçici adı varken satıcının "Renk"i ve JSON-LD rengi karşılaştırılmaz, kapasite yazan değer renk sayılmaz; gerçek sayfalardan regresyon testleri (19 Ekim raporu). 5.2 Aynı kabul kodundaki eski kimlik kontrolü: döndürdüğü aday hep atılır, ama ret gerekçesi rapora yazılır, Hepsiburada'da doğrulanmamış sayfanın varyant taramasını belirler ve ~80 test durumu atılan adayı sınar; 25 Ekim keşfinden sonra ayrı planla. Kimlik kuralı değiştiği için her biri ayrı plan onayı ister. | 🔄 5.1 tamamlandı (22 Ekim); 5.2 25 Ekim keşfinden sonra |

Sonra: güncel veri yeterliliği → ML hazırlığı (sürekli işletim kararı 22 Ekim'de verildi).

## 9. Sonraki aşamalar

### Sürekli işletim (Aşama 9'un ilk bölümü)

Amaç, bilgisayarın uyuması veya kapanmasından doğan veri boşluklarını
azaltmak. Karar (22 Ekim): dizüstü sürekli açık kalır; prizdeyken kapak
kapanınca uyumaz. GitHub'ın makinelerinde Trendyol okunmadı (Bölüm 5), evde
ayrı cihaz yok. Görevler ve 10:00/22:00 düzeni değişmez. Etkisi birkaç gün
sonra turların zamanında başlayıp başlamadığıyla ölçülür. Docker Compose ile
süreç, veri ve model kalıcılığı ayrıca değerlendirilir.

### ML

- Tek ortak LightGBM sınıflandırma modeli; ürün başına ayrı model yok (taslak).
- Hedef: başlangıç fiyatına göre sonraki 7 günde gözlenen minimumlardan biri
  %5 veya daha fazla düşükse 1 (kesin kural Bölüm 5, 19 Ekim).
- Başlangıç özellikleri (taslak): `product_id`, haftanın günü, ay, güncel fiyat /
  önceki 30 günün ortalaması, son indirimden geçen gün.
- Kapsamı değişen pencereler eğitimde kullanılmaz; en az 30 günlük geçmiş veya
  doğrulanmış model yoksa olasılık gösterilmez. Zaman sıralı değerlendirme ve
  sabit referanstan iyi Brier skoru olmadan model yayımlanmaz.
- Veri durumu (19 Ekim denetimi): kendi serimizde henüz kullanılabilir 30+7
  pencere yok; mevcut kapsam sürerse ilk pencereler Kasım sonunda oluşur.
  Cimri'de sayısal olarak 17.668 pencere var, ancak kullanım uygunluğu
  doğrulanmadığı için eğitim başlatılmadı.

## 10. Çalışma ve Git disiplini

Çalışma kuralları [AGENTS.md](AGENTS.md) dosyasındadır: adım adım ilerleme ve
her adımdan sonra durma, canlı komutları kullanıcının çalıştırması, gerçek
veritabanına yalnız okuma, her commit/push için ayrı açık onay, yazarın yalnız
kullanıcı olması (yapay zekâ imzası yok).
