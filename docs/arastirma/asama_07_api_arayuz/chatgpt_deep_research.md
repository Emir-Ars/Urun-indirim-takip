# Akıllı Telefon Fiyat Takip Projesi — Aşama 7 FastAPI ve Streamlit Teknik Hazırlık Araştırması

**Araştırma tarihi:** 8 Ekim 2026, Europe/Istanbul  
**İncelenen kaynak durumu:** Eklenen `AGENTS.md`, `proje_plani.md`, `pyproject.toml` ve `teknik.md` dosyalarını yerel eklerden; kaynak kodunu ise `b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5` commit’inden inceledim. Ekli `AGENTS.md`, `proje_plani.md` ve `teknik.md` dosyaları CRLF→LF satır sonu normalizasyonundan sonra commit’teki Git blob’larıyla birebir aynı çıktı; `pyproject.toml` doğrudan aynı Git blob hash’ine sahipti. Dolayısıyla belge–commit karşılaştırmasında sürüm belirsizliği yok. Commit de tam olarak istenen SHA’dır. fileciteturn1file0 fileciteturn22file0

**Ana sonuç:** Proje, **Aşama 7’ye veri ve veritabanı temeli bakımından hazır; API/UI sözleşmesi bakımından henüz hazır değil**. İlk FastAPI/Streamlit sürümünü çıkarmak için 001–004 migration’larını değiştirmeyi veya yeni canlı veri toplamayı zorunlu kılan bir eksik görmedim. Asıl eksikler API okuma katmanı, API cevap sözleşmeleri, “güncel/eski/kısmi/karşılaştırılamaz” durumlarının kesin semantiği, özet ölçütlerinin tanımları, Streamlit→FastAPI HTTP kuralı ve önbellek yenileme protokolüdür. Mevcut kod bunların hiçbirini uygulanmış göstermiyor; bunu varsayım olarak değil, commit’in dosya ağacı, bağımlılıklar ve planın açık “henüz başlanmadı” durumu destekliyor. fileciteturn3file0 fileciteturn11file0 fileciteturn13file0

## Mevcut duruma ilişkin kısa değerlendirme

### Belge, plan ve kod birbiriyle büyük ölçüde uyumlu

Commit’te `app/` altında `collection`, `database`, `discovery`, `market_history`, `scraper` gibi tamamlanmış aşamalar var; FastAPI’ye veya Streamlit’e ayrılmış bir uygulama modülü yok. `pyproject.toml` da FastAPI, Streamlit, Uvicorn, SlowAPI veya Psycopg connection-pool paketini içermiyor. README ve plan FastAPI/Streamlit’i açıkça “planlanan” iş olarak gösteriyor. Bu nedenle **“Aşama 7 uygulanmış olabilir ama belgeler geride kalmış” şeklinde bir tutarsızlık bulmadım**. fileciteturn3file0 fileciteturn11file0 fileciteturn20file0

Planın uzun vadeli akışı da mevcut kararlarla uyumlu: veritabanından hazırlanmış sonuçlar FastAPI’ye, oradan Streamlit’e gider; kullanıcı araması canlı scraping veya model eğitimi başlatmaz. FastAPI bölümü “hazır ürün, geçmiş ve özetler”, Streamlit bölümü “katalogdan telefon seçimi, en ucuz teklif ve geçmiş göstergeleri” tarif ediyor. fileciteturn20file1 fileciteturn17file0

Veritabanı tarafı API için beklenenden daha iyi hazırlanmış durumda. `products`, `listings`, `collection_runs` ve `listing_checks` ürün, bağlantı, tur ve sonuç düzeylerini ayrı tutuyor; fiyatlar pozitif tam sayı kuruş, `sold_out` fiyat taşıyamıyor ve `error` fiyat/stok gibi sunulamıyor. Ayrıca bir tur başlarken bütün planlanmış bağlantılar sonuçsuz oluşturulduğu için, API bir turun “henüz bakılmamış”, “hata”, “Tükendi” ve “teklif” durumlarını birbirinden ayırabilir. fileciteturn6file0 fileciteturn7file0

`product_run_prices` görünümü de Aşama 7 açısından kritik bir altyapı sağlıyor: yalnız tamamlanmış turları içeriyor; ürün başına planlanan, cevaplayan, teklif veren, tükenen ve hata veren bağlantı sayılarını; en düşük fiyatı; önceki turu; iki turun cevap veren bağlantı kümelerinin aynı olup olmadığını taşıyor. Dolayısıyla “fiyat düştü” mesajını güvenilirlik koşuluna bağlamak için yeni bir temel tablo gerekmiyor. fileciteturn7file0

Cimri geçmişi de API/UI için kullanılabilir biçimde ayrı tutulmuş: `market_history` günlük `day`, nullable `price_kurus`, kaynak kimliği/adresi ve alım kanıtlarını saklıyor; kayıtlar sonradan değiştirilemiyor. Bu, UI’nin iki ölçüm kaynağını karıştırmadan göstermesine imkân veriyor. fileciteturn9file0

### Aşama 7’ye geçiş için gerçek engel veri değil, sözleşme eksikliği

Şu anda “hangi SQL sorgusuyla hangi kullanıcı anlamının üretileceği” kodda tanımlı değil. Örneğin:

* “Güncel fiyat” çalışan turun yarım sonucu mu, son tamamlanmış turun fiyatı mı, yoksa son başarılı fiyatın taşınmış hâli mi?
* Bir ürünün son tamamlanmış turunda bütün sayfalar Tükendi ise “güncel fiyat” `null` mı olacak?
* Bir sayfa son turda hata verdi ama önceki turda fiyatı vardıysa eski fiyat ana kartta gösterilecek mi?
* `comparable_with_previous=false` iken yüzde değişim alanı nasıl davranacak?
* “30 günlük dip” tam 30 günlük izleme yoksa ne demek?
* “Tarihi zirve” katalog kapsamı değişmiş dönemleri aynı evrene dahil edecek mi?

Plan bunların kullanıcıya gösterileceğini söylüyor fakat cevap sözleşmesini tanımlamıyor. Bu, Aşama 7’ye başlamadan önce çözülmesi gereken en önemli tasarım boşluğu. fileciteturn17file0

### Şema değişikliği ilk sürüm için zorunlu görünmüyor

**Araştırma önerisi:** İlk API sürümünde yeni migration’ı bir önkoşul yapmayın. Mevcut tablolar ve `product_run_prices` ürün seçimi, son tamamlanmış gözlem, teklif ayrıntısı, tarihçe, kapsam kalitesi ve Cimri geçmişi için gerekli ham veriyi taşıyor. `listing_checks` üzerinde `(product_id, checked_at)` indeksi de ürün zaman serisi sorgusu için zaten var. fileciteturn6file0

Bu öneri “ileride hiçbir yeni indeks veya görünüm gerekmeyecek” anlamına gelmez. Aşama 7 gerçek sorguları ölçüldükten sonra gerekirse **005 ve sonrası yeni migration** eklenebilir; fakat 001–004’ün değiştirilmesini gerektiren bir neden bulmadım. Özellikle bugünkü katalog ve tur ölçeğinde önce ölçmek, sonra indeks eklemek daha savunulabilir.

### Sürüm sınırı

Projede Python aralığı bilinçli olarak `>=3.13,<3.14`; Psycopg mevcut bağımlılığı `>=3.2,<4`. Psycopg’un güncel kararlı dağıtımı Python 3.13 ve PostgreSQL 17’yi destekliyor. fileciteturn11file0 citeturn4search6turn10search2

8 Ekim 2026 itibarıyla FastAPI’nin en yeni non-pre-release sürümü **0.143.0 ve tam bugün yayımlandı**; resmi sürüm notunda telemetri otomatik yapılandırmasına ilişkin breaking change de var. Streamlit’in güncel kararlı sürümü **1.65.0**, 2 Ekim 2026 tarihli ve Python 3.13 sınıflandırmasına sahip. Bu nedenle **araştırma önerim FastAPI 0.143.0’ı yalnız “en yeni” olduğu için doğrudan sabitlememek**; önce 0.142.4 ve 0.143.0 için proje testlerini çalıştırıp seçilen minor seriyi sabitlemektir. Streamlit 1.65.x ise Aşama 7 için makul güncel adaydır. FastAPI 0.143.0 bir geliştirme snapshot’ı değildir, ancak aynı gün çıkmış yeni bir sürümdür; “bugünün en yenisi” ile “bu proje için doğrulanmış sürüm” aynı şey değildir. citeturn4search1turn9search1turn5search0turn9search2

Doğrudan kaynaklar: [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/), [Streamlit 2026 release notes](https://docs.streamlit.io/develop/quick-reference/release-notes/2026).

## Doğrulanmış eksikler ve kabul edilmiş sınırlar

Aşağıdaki ayrım özellikle önemlidir: her “henüz yok” bulgusu hata değildir. Bazıları planlanmış iş, bazıları bilinçli sınır, bazıları ise kullanıcı kararı gerektiren tasarım noktasıdır.

| Sınıf | Bulgu | İlgili dosya/bölüm | Somut gerekçe |
|---|---|---|---|
| **Doğrulanmış eksik** | FastAPI/Streamlit uygulaması yok | `app/`, `pyproject.toml` | `app/` ağacında API/UI modülü yok; bağımlılıklarda FastAPI, Streamlit veya Uvicorn yok. fileciteturn3file0 fileciteturn11file0 |
| **Doğrulanmış eksik** | API cevap modelleri ve read/repository katmanı yok | `app/contracts.py`, `app/database/` | Mevcut Pydantic modelleri katalog, scraper ve keşif sözleşmeleri; API’ye özel `ProductSummary`, history response, pagination veya durum sözleşmesi yok. Eski gelecek-aşama sözleşmelerinin bilinçli olarak kaldırıldığı plan tarafından da kaydedilmiş. fileciteturn21file0 fileciteturn15file0 |
| **Doğrulanmış eksik** | “Son 30 gün dibi / zirve / volatilite” kesin tanımları yok | `proje_plani.md`, FastAPI ve Streamlit bölümü | Plan yalnız bu değerlerin takip geçmişinden hesaplanacağını ve 30 günlük veri yoksa 30 günlük rozetin gösterilmeyeceğini söylüyor; kapsama uygunluk, eksik tur, örneklem eşiği ve volatilite formülü tanımlı değil. fileciteturn17file0 |
| **Doğrulanmış eksik** | UI önbellek geçersizleştirme protokolü yok | Plan/kod | Yeni tamamlanan run’ın Streamlit’e nasıl yansıyacağı veya cache anahtarının ne olacağı mevcut kodda bulunmuyor. API/UI de henüz yok. fileciteturn3file0 |
| **Açık karar** | Streamlit’in FastAPI’ye hangi HTTP istemcisiyle ve hangi klasmandan ulaşacağı | `AGENTS.md`, `tests/test_http.py` | `app/` altında `requests/httpx/Playwright/Selenium` yasak; `curl_cffi` yalnız `app/scraper/http.py` tarafından import edilebilir. Bu kural testle zorlanıyor. fileciteturn18file0 fileciteturn18file2 |
| **Açık karar** | Senkron bağlantı, bağlantı havuzu veya async Psycopg | `app/database/connection.py` | Mevcut uygulama senkron `psycopg.connect()` ve autocommit kullanıyor; pool yok. fileciteturn5file0 |
| **Açık karar** | “Eski veri” eşiği | Plan + scheduler | Tur saati belli olsa da API’de `stale` kavramı tanımlı değil. Eşiğin 12, 18, 24 saat vb. olması veri gerçeği değil ürün kararıdır. |
| **Açık karar** | Özetlerin hangi “kapsam dönemi” üzerinde hesaplanacağı | `product_run_prices` | Görünüm ardışık iki turun karşılaştırılabilirliğini veriyor; bütün tarih boyunca tek sabit kapsam garantisi vermiyor. fileciteturn7file0 |
| **Açık karar** | SlowAPI Aşama 7’ye dahil edilecek mi | `proje_plani.md` | Plan SlowAPI’yi tek cümleyle öngörüyor, fakat bağımlılık kaldırılmış ve proje teknik belgesi geçmişte “henüz kullanılmayan gelecek-aşama bağımlılığı” olarak temizlendiğini kaydediyor. fileciteturn12file0 fileciteturn17file0 |
| **Kabul edilmiş sınır** | UI canlı scrape/discovery/train yapmayacak | plan | Uzun vadeli akış bunu açıkça koruyor. fileciteturn20file1 |
| **Kabul edilmiş sınır** | Bir hata Tükendi değildir; eksik fiyat sıfır değildir | migration’lar | Veritabanı CHECK’leri bunu zorunlu kılıyor. fileciteturn6file0 fileciteturn7file0 |
| **Kabul edilmiş sınır** | Cimri ile kendi ölçümlerimiz tek seri değil | `004_market_history.sql`, plan | `market_history` ayrı tablo; plan da aynı ölçüm olduklarını varsaymıyor. fileciteturn9file0 fileciteturn17file0 |
| **Kabul edilmiş sınır** | İki Cimri ürün eşleşmesi doğrulanmadı; NULL’lar korunuyor | plan kapanışı | 57 ürün, 20.805 kayıt, 553 NULL; iki ürün atlanmış. fileciteturn13file0 |
| **Kabul edilmiş sınır** | Test sonucu canlı sitelerin bugünkü sağlığını kanıtlamaz | `teknik.md`, plan | Plan 1190/276 test sonucunu canlı kaynak kontrollerinden açıkça ayırıyor. fileciteturn13file0 |
| **Gelecek aşama** | ML, Docker, sürekli/bulut işletimi | plan | FastAPI/Streamlit sonrası olarak bırakılmış; toplamanın gelecekte nerede sürekli çalışacağı henüz seçilmemiş. fileciteturn17file0 |

### Planla bugünkü ekosistem arasında önemli bir güncelleme gereksinimi: SlowAPI

Planın “SlowAPI ile oran sınırlandırma” satırını **uygulanmış karar değil, yeniden doğrulanması gereken eski öneri** olarak değerlendirmek gerekir. Güncel SlowAPI sürümü 0.1.10, 13 Haziran 2026’da yayımlandı ve Python 3.13 sınıflandırması var; ancak upstream issue tracker’da Temmuz 2026’da açılan bir rapor, FastAPI `>=0.137.0` ile router kullanıldığında `default_limits` davranışının çalışmadığını bildiriyor. Bugünkü FastAPI 0.143.0 bu aralığın içinde ve SlowAPI 0.1.10 bu hata raporundan daha eski. Bu raporu burada “kesin kanıtlanmış bütün SlowAPI bozuk” şeklinde genellemiyorum; **ancak Aşama 7’ye sorgusuz eklememek için yeterli uyumluluk riski** sayıyorum. citeturn8search1turn7search1

**Araştırma önerisi:** Yerel ilk sürümde SlowAPI olmasın. API ileride gerçekten dış ağa açılacaksa, o aşamada seçilmiş FastAPI sürümüyle entegrasyon testi yapılıp rate limiting yeniden kararlaştırılsın. SlowAPI’nin kendi belgeleri de endpoint’te açık `Request` parametresi gerektirdiğini ve WebSocket sınırlamasını belirtiyor. citeturn7search2

Doğrudan kaynaklar: [SlowAPI projesi](https://github.com/laurentS/slowapi), [FastAPI >=0.137 router uyumluluk raporu](https://github.com/laurentS/slowapi/issues/281), [SlowAPI 0.1.10](https://pypi.org/project/slowapi/).

## Aşama 7 için gerekli kararlar ve seçenekler

### API’nin temel semantiği

En önemli tasarım kuralı şu olmalı:

> **“Şu an gösterilen fiyat”, yarım çalışan bir turdan veya farklı yaşlardaki son başarılı sayfalardan oluşturulan sentetik bir anlık görüntü olmamalı.**

Mevcut veritabanı bunu güvenli biçimde yapabilecek durumda. `product_run_prices` yalnız `completed` turları kullanıyor; çalışan ve kesintiye uğramış turlar görünüm dışında. Ayrıca sonuç yazımı yalnız tur `running` iken yapılabiliyor ve kapanmış tur tekrar değiştirilemiyor. fileciteturn7file0 fileciteturn8file0

**Araştırma önerisi:** Ürün için “current” cevaplarının veri sınırı **o ürünü içeren son tamamlanmış tur** olsun. Daha yeni bir tur çalışıyorsa cevap yine önceki tamamlanmış turdan gelsin fakat `collection_in_progress=true` benzeri ayrı durum bilgisi verilsin.

Bu özellikle kısmi/manual turlar için önemlidir: global olarak “en son completed run” seçmek yerine **ürün başına onu gerçekten içeren en son completed run** seçilmelidir. Aksi hâlde sınırlı bir manuel tur diğer ürünlerin yanlışlıkla eski/yok görünmesine neden olabilir. `product_run_prices` zaten ürün başına turları ayrı sıraladığı için bu davranış mevcut şemayla kurulabilir. fileciteturn7file0

### Önerilen ilk API yüzeyi

Aşağıdakiler **araştırma önerisidir; kabul edilmiş mimari değil**.

| Uç | Amaç | Temel anlam |
|---|---|---|
| `GET /api/v1/status` | Toplama/veri tazeliği | Çalışan tur varsa kimliği/başlangıcı; son tamamlanmış global tur; API zamanı/veri sürümü |
| `GET /api/v1/products` | Telefon seçici | Kayıtlı ürünler; varsayılan yalnız aktif ürünler |
| `GET /api/v1/products/{product_key}` | Ürün kimliği | Marka, model, kapasite, active; UI için kararlı kimlik |
| `GET /api/v1/products/{product_key}/offers/current` | Son güvenli teklif görünümü | O ürünü içeren son tamamlanmış turdaki her bağlantının `offer/sold_out/error` durumu + en iyi teklif + kapsam özeti |
| `GET /api/v1/products/{product_key}/history` | Kendi toplama geçmişi | Tamamlanmış turların `best_price`, kapsam ve comparability noktaları |
| `GET /api/v1/products/{product_key}/summary` | Hazırlanmış göstergeler | Son fiyat, son başarılı fiyat, veri yaşı, 30 günlük dip/zirve/volatilite ve kalite metadatası |
| `GET /api/v1/products/{product_key}/market-history` | Cimri geçmişi | Yalnız ayrı kaynak serisi; nullable fiyatlar korunur |

İlk sürümde ayrı “search” scraping ucu, discovery ucu, model-training ucu veya “refresh prices now” ucu olmamalıdır; bunlar korunacak proje kararlarıyla çelişir. fileciteturn20file1

### Alanların anlamı ve NULL sözleşmesi

API’nin yalnız `price: null` döndürmesi yeterli değildir. Aynı `null` farklı gerçekleri temsil edebilir:

| Durum | Fiyat | Durum alanı | UI anlamı |
|---|---:|---|---|
| Satılabilir teklif | pozitif kuruş | `offer` | Fiyat göster |
| Açık stoksuzluk | `null` | `sold_out` | “Tükendi” |
| Sayfa okunamadı | `null` | `error` + `error_code` | “Fiyat alınamadı”; **Tükendi değil** |
| Çalışan turda henüz bakılmadı | `null` | `pending/unchecked` yalnız operasyon durumunda | Kullanıcı fiyatı olarak gösterme |
| Tamamlanmış turda ürünün hiçbir sayfasında teklif yok | `best_price=null` | sayım alanlarıyla açıklanır | “Bu turda satılabilir teklif bulunamadı” |
| Cimri’de eksik gün | `price_kurus=null` | kaynak serisi | “Kaynakta fiyat değeri yok”; 0’a dönüştürme |

Bunların temel veri ayrımı şemada zaten zorlanıyor. fileciteturn6file0 fileciteturn9file0

**Para sözleşmesi:** API’nin kanonik parasal alanı da kuruş cinsinden integer olmalı; TL biçimlendirmesi Streamlit’in görüntüleme sorumluluğu olmalı. Mevcut Pydantic `Money` tipi ve şema bu modeli zaten kullanıyor. fileciteturn21file0

**Zaman sözleşmesi:** Toplama tarihleri UTC-aware timestamp olarak dışarı verilmeli; UI İstanbul saatine dönüştürebilir. `market_history.day` ise timestamp değil, kaynak tarihidir. Bu iki türü aynı alan tipine zorlamak doğru olmaz. Şemada da `checked_at`/`started_at` `timestamptz`, Cimri günü `date` olarak ayrılmış. fileciteturn6file0 fileciteturn9file0

### Süren tur, son tamamlanan tur, son başarılı fiyat ve eski veri birbirinden ayrılmalı

Bunlar dört farklı kavramdır:

**Süren tur** operasyonel durumdur. UI “Yeni toplama devam ediyor” diyebilir fakat yarım turdan ürün fiyatı oluşturmaz.

**Son tamamlanmış tur** anlık görüntünün güvenli veri sınırıdır. Ürün ana fiyatı burada aranır.

**Son başarılı fiyat** tarihsel bir fallback bilgisidir. Son tur hata/Tükendi ise kullanıcıya ayrıca “son fiyat gördüğümüz zaman…” şeklinde gösterilebilir, fakat güncel fiyat yerine geçirilemez.

**Eski veri** fiyatın doğruluğundan değil yaşından bahseder. API’nin önce `observed_at` ve `age_seconds` gibi olgusal bilgileri vermesi; `stale=true` eşik değerinin ayrıca kararlaştırılması daha temizdir.

**Araştırma önerisi:** İlk sürüm için sabit 12 saatlik “eski” eşiğini doğrudan kodlamayın. Tur yaklaşık 12 saat aralıkla planlanıyor fakat bilgisayar uyuması, tur süresi ve eksik turlar bilinen gerçekler. Kullanıcı bir eşik isterse **18 saat** başlangıç adayı olarak değerlendirilebilir: normal 12 saatlik aralığa birkaç saat tolerans tanır. Bu 18 saat veri tabanından türetilen gerçek değil, ürün kararıdır ve onay gerektirir.

### Tarih aralığı ve sayfalama

**Araştırma önerisi:**

`history` için timestamp aralığı `[from, to)` yani başlangıç dahil, bitiş hariç olsun. Böylece komşu tarih pencereleri çakışmaz. Tarihler RFC 3339 / timezone-aware olsun; UI “son 30 gün” seçerken İstanbul gün sınırını UTC’ye çevirebilir.

`market-history` günlük olduğundan `from_day` ve `to_day` ISO `YYYY-MM-DD` tarihleriyle tanımlanmalı; bu endpoint’in tarih sözleşmesinin toplama timestamp’lerinden ayrı olduğu açıkça belgelenmeli.

59 ürün için ürün listesini sayfalamak bugün teknik zorunluluk değil. Yine de API sözleşmesini geleceğe açık tutmak için `limit` + kararlı `product_id` cursor kullanılabilir. History sürekli büyüyeceği için `run_id` tabanlı keyset/cursor sayfalama, yüksek offset’lerden daha kararlı bir tasarımdır. Grafik ekranı için ayrıca makul bir maksimum zaman penceresi belirlemek, çoğu kullanımda pagination ihtiyacını ortadan kaldırabilir.

Önerilen başlangıç değerleri kararlaştırılmamış olmak üzere: ürünlerde 50/100 sınırı; history’de varsayılan 30 gün, bir istekte en çok 366 gün; cursor gerektiğinde `before_run_id`. Bunlar performans gerçeği değil API ürün tercihidir.

### Karşılaştırılamayan turlarda değişim hesabı

Burada veritabanının mevcut kuralı doğrudan korunmalı:

`comparable_with_previous=false` ise **fiyat değişimi ve indirim yüzdesi üretilmemeli**.

Yani:

```text
best_price = 42.999 TL
previous_best_price = 44.999 TL
comparable_with_previous = false
```

durumunda UI’nin “%4,4 düştü” demesi yanlıştır. `delta_kurus`, `delta_percent` gibi türetilmiş alanlar `null` olmalı ve neden örneğin `coverage_changed` olarak aktarılmalıdır. Görünümün tasarlanma nedeni de bir sayfanın hata alıp geri dönmesinin sahte fiyat hareketi yaratmasını önlemektir. fileciteturn7file0

`hours_since_previous` ayrı bir kalite işaretidir. Mevcut görünüm uzun aralığı comparability’yi otomatik olarak false yapmıyor; bunu tüketen tarafın yorumlaması gerektiğini SQL yorumları açıkça söylüyor. UI bu nedenle “karşılaştırılabilir” ile “zaman aralığı normal” kavramlarını birleştirmemeli. fileciteturn7file0

### PostgreSQL ile eşzamanlı toplama ve API okuması

PostgreSQL’in MVCC modeli altında normal bir `SELECT`, sorgu başlarken commit edilmiş satırların snapshot’ını görür; uncommitted yazıları görmez. `READ COMMITTED` düzeyinde iki ardışık SELECT farklı snapshot görebilir; `REPEATABLE READ` ise aynı transaction’daki ardışık sorguların aynı snapshot’ı görmesini sağlar. citeturn5search3

Doğrudan kaynak: [PostgreSQL Transaction Isolation](https://www.postgresql.org/docs/17/transaction-iso.html).

Bu proje açısından bundan çıkan **araştırma önerisi**:

* Tek SQL’den oluşan basit endpoint için varsayılan `READ COMMITTED` yeterlidir.
* “Son run’ı bul → run satırlarını oku → summary hesapla” gibi birden fazla sorguyla tek mantıksal cevap üretilecekse, kısa **READ ONLY + REPEATABLE READ** transaction kullanılmalıdır.
* Önce kullanılacak completed `run_id` seçilip, sonraki bütün sorgular açıkça o `run_id` ile sınırlandırılmalıdır.
* API hiçbir zaman collection advisory lock’ını almamalıdır; bu kilit toplama süreçlerinin birbirini engellemesi içindir. Writer tarafındaki mevcut advisory lock ve DB guard’ları olduğu gibi kalmalıdır. fileciteturn10file0

Böylece toplama çalışırken API eski tamamlanmış snapshot’ı normal şekilde okumaya devam eder. Tur tamamlanıp commit edildiğinde yeni API isteği yeni completed run’ı görebilir; yarım sonuçlar kullanıcı anlık görüntüsüne sızmaz.

### Senkron, asenkron ve bağlantı havuzu seçenekleri

Mevcut kod **senkron Psycopg** kullanıyor. FastAPI normal `def` endpoint ve bağımlılıklarını kendi dış thread pool’unda çalıştırabiliyor; dolayısıyla sırf FastAPI kullanılıyor diye mevcut veritabanı erişimini async’e çevirmek zorunlu değil. citeturn4search12

Doğrudan kaynak: [FastAPI async davranışı](https://fastapi.tiangolo.com/async/).

| Seçenek | Artısı | Eksisi | Bu proje için değerlendirme |
|---|---|---|---|
| Her istekte `psycopg.connect()` | En az yeni mimari | Her istekte bağlantı kurulumu; bağlantı sayısını merkezi kontrol etmez | İlk prototipte çalışır ama uzun vadeli tercih değil |
| **Senkron `ConnectionPool`** | Mevcut ham SQL ve sync kod korunur; sınırlı bağlantı sayısı; düşük refactor | `psycopg_pool` yeni bağımlılık | **Önerilen seçenek** |
| `AsyncConnectionPool` + async query layer | Yüksek eşzamanlılıkta bloklamayan DB I/O | Mevcut katmanın daha geniş yeniden yazımı; iki I/O modelini karıştırır | Mevcut ölçek için gereksiz karmaşıklık |

Psycopg hem `ConnectionPool` hem `AsyncConnectionPool` sunuyor; pool paketi ana `psycopg` paketinden ayrı dağıtılıyor. Güncel kararlı `psycopg_pool` 3.3.3 Python 3.13’ü destekliyor. citeturn4search0turn10search3

Doğrudan kaynaklar: [Psycopg connection pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html), [psycopg-pool paketi](https://pypi.org/project/psycopg-pool/).

**Önerim:** Aşama 7’nin ilk sürümünde mevcut ham SQL yaklaşımı + senkron FastAPI endpoint/dependency + küçük senkron bağlantı havuzu. Havuzun kesin `min_size/max_size` değerleri ölçülmeden “4 kesin doğrudur” gibi sabitlenmemeli; tek Streamlit istemcili yerel ortam için çok küçük bir havuz yeterli olacaktır.

FastAPI’nin paylaşılan kaynakları uygulama başlangıcında açıp kapanışta temizlemek için önerdiği yöntem `lifespan`’dır; eski startup/shutdown event yaklaşımı alternatif/deprecated yol olarak belgeleniyor. Pool seçilirse yaşam döngüsü buraya oturur. citeturn4search13

Doğrudan kaynak: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/).

### Streamlit→FastAPI ve mevcut HTTP kuralı gerçek bir mimari karardır

Şu anki kural çok açık: `app/` içinde HTTP yalnız `app/scraper/http.py` ve `curl_cffi` üzerinden; `requests/httpx/Playwright/Selenium` yok. Test ayrıca `curl_cffi` import eden tek dosyanın scraper HTTP modülü olduğunu denetliyor. fileciteturn18file0 fileciteturn18file2

Streamlit’in localhost FastAPI’ye HTTP yapması bu kuralla **kavramsal olarak farklı bir trafik sınıfı** yaratıyor. Scraper’ın pazaryeri HTTP katmanını yerel API istemcisi olarak yeniden kullanmak doğru değil; o modülün site alan adı, gecikme ve hata davranışları başka amaç için tasarlanmış.

Üç seçenek var:

| Seçenek | Kural etkisi | Değerlendirme |
|---|---|---|
| Streamlit’i `app/` dışında tut; iç API client da `app/` dışında olsun | Mevcut `app/` testi değişmez | En az müdahale |
| `app/` içinde ayrı internal-API client’a dar izin ver; mimari testi buna göre güncelle | Mevcut kural açıkça revize edilir | **Uzun vadede en temiz seçenek, ancak kullanıcı onayı şart** |
| Streamlit doğrudan PostgreSQL okusun | HTTP çakışması yok | FastAPI’yi atlar, aynı SQL/semantiği iki yerde çoğaltır; **önerilmez** |

**Benim mimari önerim:** Kuralı sessizce delmek yerine ikinci seçeneği ayrı kullanıcı kararı olarak kabul etmek: “Pazaryeri HTTP’si yalnız scraper/http + curl_cffi; Streamlit’in yalnız kendi FastAPI servisine yaptığı internal HTTP için ayrı, açıkça sınırlandırılmış istemciye izin.” Bunun etkisi `tests/test_http.py` mimari testinin bilinçli olarak güncellenmesidir. Kullanıcı kuralı hiç açmak istemezse ilk seçenek uygulanabilir.

## Önerilen ilk sürüm kapsamı ve mimari

### Veri akışı

Önerilen sınır şu olur:

```text
Windows Görev Zamanlayıcı
        │
        ▼
mevcut collection ─────────► PostgreSQL
                                  │
                                  │ salt-okunur sorgular
                                  ▼
                              FastAPI
                                  │
                                  │ internal HTTP
                                  ▼
                             Streamlit
```

Bu tasarımda **collection/discovery/scraper kod yoluna Aşama 7’den hiçbir çağrı gitmez**. Streamlit yalnız API konuşur; FastAPI yalnız kayıtlı veriyi okur. Böylece kullanıcı seçimi fiyat toplama zamanlamasını veya site trafiğini değiştiremez.

### Telefon seçimi ve ana ekran

İlk Streamlit ekranının tek sayfalı, üç ana bilgi katmanlı olması yeterlidir:

**Telefon seçimi:** marka/model/kapasite düzeyinde. Renk seçici olmamalı; renk ürün kimliği değil listing özelliğidir. Mevcut `Product` sözleşmesi de ürün kimliğini marka/model/storage olarak tutuyor. fileciteturn21file0

**Teklif özeti:** en ucuz güncel güvenli teklif, platform, satıcı, satıcı puanı, stok durumu ve gözlem zamanı. Aynı blokta “son tamamlanan tur”, “yeni tur çalışıyor” ve veri yaşı görünür olmalı.

**Geçmiş:** kendi toplama geçmişi ana grafik; bunun altında veya ayrı sekmede Cimri kaynak geçmişi.

Kullanıcıya yalnız tek büyük fiyat gösterip veri kalitesini dipnota saklamak yerine fiyatın hemen yanında kapsam bilgisi verilmesi doğru olur. Örneğin:

> **42.999 TL — Trendyol / Satıcı X**  
> Son tamamlanmış gözlem: 8 Ekim 22:31  
> Cevap: 6/6 sayfa · 4 teklif · 2 Tükendi · 0 hata

Kısmi cevapta:

> **43.499 TL — mevcut cevaplar arasındaki en düşük fiyat**  
> 5/6 sayfa cevap verdi · 1 sayfa okunamadı  
> Tam kapsam olmadığı için önceki turla değişim gösterilmiyor.

Bu ayrım doğrudan veritabanındaki `planned_pages`, `answered_pages`, `offer_pages`, `sold_out_pages`, `error_pages` alanlarından üretilebilir. fileciteturn7file0

### Tükendi, okunamadı, eski ve kısmi kapsam

Önerilen sunum sözlüğü:

| Veri durumu | Kullanıcı metni | Kesinlikle yapılmaması gereken |
|---|---|---|
| `sold_out` | **Tükendi** | 0 TL gösterme |
| `error/network` | **Bağlantı hatası — fiyat alınamadı** | Tükendi gösterme |
| diğer `error` | **Sayfa okunamadı** + gerekirse kısa sebep | Önceki fiyatı güncelmiş gibi taşıma |
| `best_price=null`, bütün cevaplar sold_out | **Bu turda satılabilir teklif yok** | “0 TL” veya indirim |
| cevap veren sayfa eksik | **Kısmi kapsam** | Güvenilir indirim yüzdesi |
| son tamamlanmış gözlem eşikten eski | **Eski veri — son gözlem …** | Yaşı gizleyerek “güncel” etiketi |
| aktif toplama | **Yeni fiyat turu devam ediyor** | Yarım turu mevcut snapshot’a karıştırma |

### Grafiklerde NULL ve eksik turlar

İki farklı boşluğu ayırmak gerekir.

**Tamamlanmış tur var ama fiyat yoksa:** `best_price=null` noktası korunmalıdır. Bu, örneğin bütün sayfaların Tükendi olduğu bir gözlem olabilir. Grafiğin bu noktadan düz çizgiyle eski fiyatı taşımaması gerekir.

**Tur hiç yoksa:** veritabanında sahte nokta oluşturulmamalıdır. İlk sürümde grafik yalnız gerçek turları çizebilir ve tur boşlukları zamansal x ekseninden görülebilir. Daha sonra planlanan 10:00/22:00 slotları görselleştirilmek istenirse bu ayrı “beklenen slot” veri katmanı olmalıdır; DB’ye uydurma price observation yazılmamalıdır.

Cimri tarafında `price_kurus=NULL` günlük satır da aynı şekilde boş kalmalıdır. 004 migration bunu geçerli ve bilinçli veri biçimi olarak kabul ediyor. fileciteturn9file0

Grafik kütüphanesinin null noktaları otomatik birleştirip birleştirmediği Aşama 7 UI testinde özellikle doğrulanmalıdır; veri katmanında null’ı kaldırarak “görseli güzelleştirmek” doğru çözüm değildir.

### Cimri geçmişinin sunumu

**Öneri:** Kendi takip geçmişi ile Cimri’yi ilk sürümde aynı çizgide göstermeyin.

Ana grafik:

> **Kendi fiyat takibimiz — Trendyol + Hepsiburada, tamamlanmış turlar**

İkinci grafik/sekme:

> **Cimri kaynak geçmişi — ayrı tarihsel kaynak**

Cimri kartında şu uyarı görünür olmalı:

> “Bu seri kendi fiyat toplama gözlemlerimizle aynı ölçüm olarak birleştirilmez.”

Bu yalnız UI tercihi değil; plan ve DB tasarımının mevcut anlamının korunmasıdır. fileciteturn9file0 fileciteturn17file0

İki doğrulanmamış Cimri eşleşmesi olan üründe “geçmiş yok” ile “eşleştirme doğrulanamadı” aynı mesaj olmamalıdır. Mevcut veritabanında bu iki neden doğrudan ayrı bir status tablosuyla saklanmıyor; yalnız `market_history` satırının olmaması API açısından “Cimri verisi yok” demeye yeter, fakat **nedenin “eşleştirme doğrulanamadı” olduğunu runtime DB’den tek başına çıkarmak mümkün görünmüyor**. Bu nedenle iki ürünün eşleştirme durumunu UI’de özel göstermek isteniyorsa bunun yapılandırılmış olarak nerede tutulacağı açık karardır. Plan belgesi bu iki ürünü biliyor, fakat plan runtime veri kaynağı değildir. fileciteturn13file0

Bu, Aşama 7 için bulduğum az sayıdaki gerçek **veri modelleme boşluklarından biridir**, fakat ilk sürümün çalışmasını engellemez: Cimri endpoint’i basitçe boş dizi döndürebilir; “neden yok?” ayrıntısı sonraki küçük şema/config kararı olabilir.

### Özet metriklerin güvenli tanımı

Plan “son 30 günün dibi, tarihi zirve, volatilite” diyor fakat isimler tek başına yeterince kesin değil. fileciteturn17file0

**Araştırma önerisi — temel uygunluk noktası:** Bir fiyat noktası summary metriğine ancak:

1. tur `completed`,
2. `best_price IS NOT NULL`,
3. tercihen `answered_pages = planned_pages`

ise girsin.

Üçüncü koşul muhafazakârdır: hata veren bir sayfa varken “bütün takip edilen tekliflerden minimum” dediğimizden emin oluruz.

#### Son 30 günlük dip

Önerilen tanım:

> **Son 30 takvim günü içindeki uygun, tam cevaplı turlarda gözlenen en düşük `best_price`.**

Metinde “piyasadaki gerçek 30 günlük dip” değil, **“takibimizde son 30 günde gözlenen en düşük fiyat”** denmelidir.

Planın “30 günlük veri yoksa rozet yok” kararını daha kesin uygulamak için yalnız son üç günlük veride min hesaplayıp “30 günlük dip” etiketi koymayın. Önerim:

* takip geçmişinin pencerenin başlangıcına kadar uzanması;
* en az 30 takvim günlük izleme süresinin bulunması;
* uygun gözlem sayısının response metadata’sında verilmesi.

Kaç eksik turun metriği tamamen geçersiz kılacağı ayrıca ürün kararıdır. Muhafazakâr ilk sürümde `eligible_points` sayısını da gösterip veri yetersizse değer `null` bırakılabilir.

#### Tarihi zirve

“Historical high”ın kapsam değişimlerinden etkilenme riski vardır. İki seçenek vardır:

**Geniş tanım:** bütün tam cevaplı completed turların maksimumu. Avantajı basit olması, dezavantajı 334→332 vb. kapsam değişimlerinde farklı teklif evrenlerini aynı geçmişe koymasıdır.

**Muhafazakâr tanım:** yalnız mevcut karşılaştırılabilir kapsam zincirindeki maksimum. Bu daha doğru kıyaslama sağlar fakat artık “tüm tarih zirvesi” değil **“mevcut kapsam döneminin zirvesi”** olur.

**Önerim ikinci tanım** veya geniş tanım kullanılıyorsa etiketin “takipte gözlenen en yüksek fiyat” olarak değiştirilmesidir. “Tarihi zirve”yi kapsam değişimlerini yok sayarak göstermek yanıltıcı olabilir.

#### Volatilite

Basit fiyat standart sapması telefonun fiyat seviyesine bağlı olduğu için karşılaştırmalı anlamı zayıftır. Önerilen ölçü:

> ardışık **karşılaştırılabilir** turlar için `ln(P_t / P_{t-1})` getirilerinin örnek standart sapması.

Ayrıca:

* her geçişte `comparable_with_previous=true` olmalı;
* iki fiyat da mevcut olmalı;
* uzun veri boşlukları ayrı tutulmalı;
* değer yeterli örnek olmadan yayınlanmamalı.

**Başlangıç için araştırma önerisi:** en az **14 geçerli geçiş ve en az 7 ayrı takvim günü** olmadan volatilite `null` olsun. 14 sayısı matematiksel zorunluluk değil, küçük örneklemde sahte kesinliği azaltmak için ürün eşiği önerisidir.

İlk sürümde volatiliteyi yıllıklaştırmak da önerilmez; turlar arasındaki süre her zaman tam 12 saat değil ve `hours_since_previous` bunu açıkça gösteriyor. fileciteturn7file0

Cimri için bu üç metriği aynı summary’ye katmayı önermiyorum. Cimri günlük kaynak serisidir, kendi toplama serisiyle aynı ölçüm olmadığı proje kararıdır. Cimri metrikleri istenirse ileride **kaynağa özel ayrı metrikler** olarak tanımlanmalıdır. fileciteturn17file0

### Streamlit önbelleği ve yeni tur

Streamlit `st.cache_data` TTL ile cache tutabiliyor ve fonksiyon/cache bazında temizleme destekliyor. `st.fragment(run_every=...)` ise kullanıcı oturumu açıkken belirli aralıklarla sadece bir ekran parçasını yeniden çalıştırabiliyor. citeturn6search3turn6search1

Doğrudan kaynaklar: [st.cache_data](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data), [st.fragment](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment).

**Önerilen protokol:**

FastAPI `/status`, son tamamlanmış `run_id` değerini bir **data version** olarak sunsun.

Streamlit kısa aralıklarla yalnız `/status` okur. `run_id` değişmediyse ağır history çağrılarını tekrarlamaz. `run_id` değişince history/current/summary çağrılarının cache anahtarı da değişir; böylece eski değer “TTL dolana kadar” görünmez.

Çalışan tur varken:

> “Yeni toplama devam ediyor. Aşağıda son tamamlanmış tur gösteriliyor.”

Tur tamamlandığında `data_version` değişir ve görünüm yenilenir.

Bu yaklaşımın salt “cache TTL = 12 saat” tasarımından üstün yanı, yeni turun ne zaman bittiğine bağlı olmasıdır.

İlk sürümde sistem yalnız tek yerel kullanıcı tarafından kullanılacaksa **hiç cache kullanmamak da geçerli bir başlangıç seçeneğidir**. 59 ürün ve küçük API yükünde önce doğruluğu kurup, ölçülen ihtiyaç üzerine cache eklemek en basit yoldur. Cache eklenirse “background refresh ile bilerek expired data döndürme” davranışını fiyat ana kartında kullanmak istemem; Streamlit bunu desteklese de fiyat tazeliği açısından semantiği karmaşıklaştırır. citeturn6search3

### Yerel kullanım ve dış erişim

İlk yerel sürümde hem FastAPI/Uvicorn hem Streamlit yalnız loopback’e bağlanabilir. Uvicorn’un varsayılan bind adresi `127.0.0.1`; `0.0.0.0` kullanmak uygulamayı yerel ağa açar. citeturn7search0

Doğrudan kaynak: [Uvicorn settings](https://www.uvicorn.org/settings/).

Streamlit de belirli bir `server.address` üzerinde dinleyebiliyor; CORS ve XSRF korumaları için ayrı yapılandırma seçenekleri var. citeturn7search6

Doğrudan kaynak: [Streamlit config.toml](https://docs.streamlit.io/develop/api-reference/configuration/config.toml).

**Yerel Aşama 7:** loopback, auth yok, SlowAPI yok, TLS yok kabul edilebilir.

**İleride dış erişim:** bind adresi değiştirmek tek başına yeterli değildir. Kimlik doğrulama, TLS/reverse proxy, hangi proxy header’larına güvenileceği, host/origin politikası, secrets ve rate limiting yeniden ele alınmalıdır. Uvicorn özellikle forwarded IP başlıklarının yalnız güvenilen proxy’lerden kabul edilmesini yapılandırabiliyor. citeturn7search0

Bunların Docker/bulut sağlayıcısı kısmı bu araştırmanın kapsamı dışındadır.

### Mevcut Windows görevlerini bozmadan çalışma

API ve Streamlit **ayrı okuma süreçleri** olarak çalıştırılabilir. Mevcut 10:00/22:00 collection ve Pazar keşif Task Scheduler görevlerini değiştirmek gerekmiyor. FastAPI/Streamlit scraping yapmadığı için scrape lock’a katılması da gerekmiyor; PostgreSQL MVCC ile okuyucu ve mevcut writer normal biçimde birlikte çalışabilir. Mevcut collection’ın veritabanı advisory lock’ı yalnız toplama turu koordinasyonu için tasarlanmış. fileciteturn10file0

İlk Aşama 7 doğrulamasında API ve Streamlit’i **manuel ayrı süreçler** olarak başlatmak, Task Scheduler’a üçüncü/dördüncü servis eklemekten daha düşük riskli. API/UI’nin Windows başlangıcında sürekli servis hâline getirilmesi “işletim/sürekli çalışma” aşamasına bırakılabilir. Bu, mevcut zamanlayıcıları hiç değiştirmeme hedefiyle uyumludur.

## Alt adımlar ve kabul testleri

### Önerilen uygulama sırası

Her adım ayrı doğrulanabilir olmalı; sonraki adım öncekinin semantiğine dayanmalı.

| Alt adım | Amaç | Bağımlılıklar | Kabul ölçütü | Bu adımda kullanıcı kararı |
|---|---|---|---|---|
| **Sözleşmeleri dondurma** | “current”, “last successful”, stale, partial, comparable ve metric anlamlarını yazılı belirlemek | Mevcut şema/plan | API sözleşme belgesi veri örnekleriyle bu durumların hepsini ayırıyor; kod yokken bile cevap belli | Stale eşiği; metric tanımları; HTTP kuralı |
| **Salt-okunur DB sorgu katmanı** | API’den bağımsız SQL okuma işlevlerini kurmak | Mevcut Psycopg, 001–004 | Yalnız `_test` DB’de ürün/current/history/Cimri sorguları bütün edge-case’leri geçiyor; gerçek DB’ye test erişimi yok | Sync connect vs sync pool |
| **FastAPI iskeleti ve yaşam döngüsü** | API process, DB dependency/pool, health/readiness, Pydantic response’lar | Önceki adım; seçilen FastAPI/Uvicorn sürümü | DB açık/kapalı durumları doğru HTTP sonucu; startup/shutdown kaynak sızıntısız; ağsız test | FastAPI sürümü; pool |
| **Ürün ve güncel teklif uçları** | Seçici ve ana kartı beslemek | DB layer + API | Çalışan tur asla current snapshot’a karışmıyor; Tükendi/error ayrılıyor; fiyat kuruş | “current” son product-completed-run kararı |
| **Geçmiş, comparability ve summary** | Grafik ve göstergeler | Önceki uçlar | NULL korunuyor; comparable=false → delta yok; veri yetersiz metric=null | 30d/high/volatility kesin eşikleri |
| **Cimri ayrı endpoint’i** | Harici geçmişi göstermek | `market_history` | 553 türündeki NULL noktalar korunabilir; kendi history payload’ıyla birleşmez | Eşleşmemiş iki ürün için UI açıklaması |
| **Streamlit ilk ekranı** | Telefon seçimi + summary + teklifler + iki history görünümü | API sözleşmesi | DB’ye doğrudan erişmez; seçme işlemi scrape etmez; hata/stale/kısmi durumları doğru render eder | Internal HTTP kuralının seçeneği |
| **Tazelik ve yerel işletim kapanışı** | Cache/version ve eşzamanlı collection senaryosunu doğrulamak | Tam UI/API | Yeni completed run cache’i yeniler; running turda eski completed snapshot açık etiketle kalır; scheduler dosyaları/değerleri değiştirilmez | Cache stratejisi; yalnız-local kapsam |

Bu sıra “önce FastAPI endpoint’lerini yazıp sonra semantik uydurma” riskini engeller. Özellikle ilk adım koddan önce yapılmalı; çünkü veritabanındaki `NULL` ve run durumları teknik olarak açık olsa da kullanıcı dilindeki anlamları henüz kararlaştırılmış değil.

### API kabul senaryoları

**Boş geçmiş:** Ürün var ama completed history yok. Ürün endpoint’i 200; history boş dizi; summary fiyat/30d/high/volatility alanları `null`. “0 TL” veya sahte başlangıç noktası yok.

**Tükendi:** Son completed turda bütün cevaplar `sold_out`. Current endpoint `best_price=null`, sold-out sayısı doğru; UI “satılabilir teklif yok/Tükendi” gösteriyor.

**Hata:** `network` veya parse/storage hatası olan sayfa `error`; `sold_out` sayısına katılmıyor. Önceki başarılı fiyat varsa yalnız “son başarılı fiyat” alanında timestamp ile bulunuyor.

**Kısmi kapsam:** Örneğin 5/6 sayfa cevap verdi. En düşük cevap fiyatı gerekiyorsa mevcut cevap olarak verilebilir, fakat `coverage_complete=false`; fiyat değişimi/indirim iddiası yalnız DB comparability koşulu karşılanıyorsa ve seçilen ürün politikası izin veriyorsa üretilir. En muhafazakâr ilk sürümde kısmi kapsamta summary değişim alanları null tutulmalıdır.

**Karşılaştırılamayan fiyat:** `best_price` iki turda da olsa `comparable_with_previous=false`. API `delta_kurus=null`, `delta_percent=null`, neden alanı açık. UI aşağı/yukarı ok göstermiyor.

**Süren tur:** Run B `running`; Run A son `completed`. API current = A. `/status` B’nin çalıştığını söylüyor. B içindeki 1, 100 veya bütün sayfa sonuçları current’a sızmıyor.

**Tur kapanışı yarışı:** İki DB bağlantısıyla API transaction’ı ve collection kapanışı eşzamanlı sınanmalı. Tek API cevabı ya eski tamamlanmış snapshot’ın tamamını ya yeni tamamlanmış snapshot’ın tamamını görmeli; ikisini karıştırmamalı. PostgreSQL `REPEATABLE READ` bu çok-sorgulu cevap için uygun araçtır. citeturn5search3

**Eski veri:** Son completed product observation seçilen stale eşiğinden eski. Fiyat saklanıyor fakat `stale/age` bilgisi kullanıcıya açık. Eski veri silinmiyor ve bugünkü gibi sunulmuyor.

**Cimri NULL:** Günlük satır `price_kurus=NULL`; JSON null kalıyor; grafik boşluk bırakıyor.

**Bağlantı kesintisi — DB:** PostgreSQL’e erişilemiyor. API fiyat uydurmuyor; readiness/ilgili endpoint kontrollü hata, önerim `503 Service Unavailable`. Streamlit daha önce cache’lenmiş veriyi göstermeye karar verirse “API erişilemiyor; gösterilen veri … zamanına ait” uyarısı zorunlu olmalı.

**Geçersiz tarih aralığı:** `from >= to`, timezone’suz collection timestamp, aşırı büyük limit gibi istekler doğrulama hatası vermeli; sessizce parametre değiştirilmemeli.

**Pasif ürün/listing:** Ürün seçici varsayılan olarak aktif ürünler; eski history silinmez. Explicit product lookup’ın pasif ürünü 404 mü yoksa `active=false` ile mi döndüreceği sözleşmede tek biçimde belirlenmeli. Önerim explicit lookup’ın tarihi korumak için ürünü döndürmesi, UI seçicinin filtrelemesidir.

### Veritabanı kabul testleri

Testler yalnız adı `_test` ile biten database üzerinde çalışmalı; bu mevcut güvenlik modelinin devamıdır. Canlı PostgreSQL veya canlı fiyat sitelerine Stage 7 otomatik testinden erişim gerekmiyor. Projenin bugünkü test disiplini zaten HTTP ve DB için bu ayrımı yapıyor. fileciteturn18file1 fileciteturn13file0

Özellikle iki bağımsız bağlantı kullanılan concurrency testi önemlidir:

1. completed run A hazırlanır;
2. run B `running` açılır;
3. B’ye bazı sonuçlar yazılır;
4. API read sorgusu çalışır ve A’yı görür;
5. B tamamlanır;
6. sonraki yeni API transaction’ı B’yi görür.

Bu, “MVCC teoride çalışıyor” demekten daha değerli proje kabul testidir.

### Streamlit kabul testleri

UI testinin gerçek API process veya internet kullanması gerekmez; internal API client sahte cevaplarla beslenebilir.

Kontrol edilmesi gereken görsel durumlar:

| Senaryo | Beklenen UI |
|---|---|
| normal tam tur | fiyat + satıcı + zaman + kapsam |
| Tükendi | 0 TL yok |
| error | “Tükendi” yok |
| running | son completed görünür + “toplama devam ediyor” |
| stale | fiyat yanında eski veri uyarısı |
| comparable=false | indirim yüzdesi/ok yok |
| history null | grafik boşluğu korunur |
| Cimri null | sıfır noktası oluşturulmaz |
| Cimri history yok | boş durum mesajı |
| API unavailable | eski cache varsa açık stale/offline etiketi; yoksa kontrollü hata |
| yeni run completed | `data_version` değişimiyle yenileme |

### Aşama kapanış ölçütü

Aşama 7’nin “tamamlandı” sayılması için benim önerdiğim asgari kapanış:

FastAPI ve Streamlit bağımlılıkları sabit/test edilmiş; API yalnız DB okuyor; Streamlit yalnız API kullanıyor; canlı scraping tetiklenmiyor; current/run/stale/error/sold_out/comparability semantiği testlerle sabit; Cimri ayrı; null’lar korunuyor; mevcut 001–004 değişmemiş; testler internetsiz ve `_test` DB’de; mevcut Task Scheduler görevleri değişmemiş; seçilen FastAPI/Streamlit sürümleri ve yerel başlatma yolu teknik belgede kayıtlı.

1190 eski testin tekrar geçmesi gerekli regresyon kanıtıdır, fakat yeni Stage 7 testlerinin ayrıca geçmesi gerekir. Eski “1190 passed” sonucu API/UI’nin doğru olduğunu kanıtlayamaz; o commit’te API/UI yoktur. fileciteturn13file0 fileciteturn3file0

## Kullanıcıya sorulacak sorular

Aşağıdaki kararlar uygulamaya başlamadan önce gerçekten kullanıcı kararı gerektiriyor. Yanlarına araştırma açısından önerdiğim varsayılanı ekledim; **öneriler henüz kabul edilmiş karar değildir**.

| Karar | Önerilen varsayılan | Kararın etkisi |
|---|---|---|
| **Streamlit→FastAPI HTTP kuralı nasıl çözülsün?** | Pazaryeri HTTP kuralı aynen korunsun; internal localhost API client için dar, açık bir istisna tanımlansın | `tests/test_http.py` bilinçli güncellenir; scraper taşıma katmanı kirlenmez |
| **“Güncel fiyat” ne olsun?** | Ürünü içeren son `completed` run’ın fiyatı | Running tur kısmi veri sızdırmaz |
| **Son başarılı eski fiyat ana fiyat yerine kullanılabilir mi?** | Hayır; yalnız ayrı “son başarılı” bilgi olarak | Hata/Tükendi durumunda yanlış güncellik engellenir |
| **Veri ne zaman “eski” sayılsın?** | Başlangıç adayı 18 saat; API her durumda age’i de döndürsün | UI rozet davranışı |
| **Özet metrikleri kısmi kapsamlı turları içersin mi?** | Hayır; ilk sürümde `answered=planned` fiyat noktaları | Daha az ama daha güvenilir summary |
| **“Tarihi zirve” bütün history mi, mevcut kapsam dönemi mi?** | Mevcut karşılaştırılabilir kapsam dönemi; etiketi de buna göre değiştir | Kapsam değişiminden doğan yanıltıcı seviyeleri engeller |
| **Volatilite yeterlilik eşiği?** | ≥14 comparable geçiş ve ≥7 gün; uzun boşlukları dışla | Küçük örneklemde sahte kesinliği engeller |
| **DB erişimi?** | Sync Psycopg + küçük `ConnectionPool`; async’e geçme | Mevcut ham SQL yaklaşımını korur |
| **FastAPI sürüm adayı?** | Önce 0.142.4 ile baseline; 0.143.0 aynı test matrisiyle ayrıca denensin | Aynı gün çıkan 0.143.0’a kör geçiş önlenir. citeturn4search1 |
| **Streamlit sürüm adayı?** | 1.65.x | Python 3.13 destekli güncel kararlı seri. citeturn9search2 |
| **SlowAPI ilk yerel sürümde olsun mu?** | Hayır | Güncel uyumluluk riski ve yerel-only kullanımda düşük fayda. citeturn7search1turn8search1 |
| **Cimri iki eşleşmemiş üründe neden gösterilsin mi?** | İlk sürüm “Cimri geçmişi bulunmuyor”; gerekçeyi runtime’da göstermek istenirse ayrı yapılandırılmış metadata kararı | Plan belgesini runtime veri tabanı gibi kullanma ihtiyacı doğmaz |
| **History API maksimum aralığı?** | İlk sürüm 366 gün | Sınırsız cevapların önüne geçer; Cimri bir yıllık görüntülemeyi kapsar |
| **Aşama 7 yalnız yerel mi kapansın?** | Evet | Auth/TLS/public rate limit işletim aşamasına taşınır; mevcut Windows scheduler etkilenmez |

Bu kararların içinde en önce verilmesi gerekenler **HTTP kuralı**, **current/stale semantiği** ve **summary metric tanımlarıdır**. Bunlar belirlenmeden kod yazılırsa API response modelleri, SQL sorguları ve Streamlit ekranı aynı anda değişmek zorunda kalır.

## Kaynaklar ve doğrulanamayan noktalar

### Proje kaynakları

İstenen başlangıç commit’i gerçekten erişilebildi ve incelendi: [`b4d1e985…`](https://github.com/Emir-Ars/Urun-indirim-takip/commit/b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5). Commit mesajı README/teknik rehber görev paylaşımını düzenliyor; API/UI’nin henüz geliştirilmediğini de içerikte koruyor. fileciteturn1file0

İncelenen başlıca kaynaklar:

* [`proje_plani.md` @ b4d1e985](https://github.com/Emir-Ars/Urun-indirim-takip/blob/b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5/proje_plani.md) — Aşama durumu, FastAPI/Streamlit hedefleri, Cimri ve işletim kararları. fileciteturn13file0 fileciteturn17file0
* [`docs/teknik.md` @ b4d1e985](https://github.com/Emir-Ars/Urun-indirim-takip/blob/b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5/docs/teknik.md) — mevcut çalışma/test kuralları. fileciteturn22file0
* [`AGENTS.md` @ b4d1e985](https://github.com/Emir-Ars/Urun-indirim-takip/blob/b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5/AGENTS.md) — HTTP ve test mimari kuralları. fileciteturn18file0
* [`pyproject.toml` @ b4d1e985](https://github.com/Emir-Ars/Urun-indirim-takip/blob/b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5/pyproject.toml) — Python/bağımlılık sınırları; FastAPI/Streamlit bugün yok. fileciteturn11file0
* [`app/contracts.py`](https://github.com/Emir-Ars/Urun-indirim-takip/blob/b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5/app/contracts.py) — mevcut Pydantic sözleşmeleri ve kuruş para tipi. fileciteturn21file0
* [`001_initial.sql`](https://github.com/Emir-Ars/Urun-indirim-takip/blob/b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5/app/database/migrations/001_initial.sql) — ürün/listing/run/check şeması. fileciteturn6file0
* [`002_guards_and_comparability.sql`](https://github.com/Emir-Ars/Urun-indirim-takip/blob/b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5/app/database/migrations/002_guards_and_comparability.sql) — DB guard’ları ve `product_run_prices`. fileciteturn7file0
* [`003_closed_run_guards.sql`](https://github.com/Emir-Ars/Urun-indirim-takip/blob/b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5/app/database/migrations/003_closed_run_guards.sql) — kapanmış tur/result yarış korumaları. fileciteturn8file0
* [`004_market_history.sql`](https://github.com/Emir-Ars/Urun-indirim-takip/blob/b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5/app/database/migrations/004_market_history.sql) — ayrı Cimri geçmişi. fileciteturn9file0
* [`app/database/connection.py`](https://github.com/Emir-Ars/Urun-indirim-takip/blob/b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5/app/database/connection.py) — senkron Psycopg, autocommit, UTC ve lock timeout. fileciteturn5file0
* [`app/database/runs.py`](https://github.com/Emir-Ars/Urun-indirim-takip/blob/b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5/app/database/runs.py) — advisory lock, start/result/finish davranışları. fileciteturn10file0
* [`tests/test_http.py`](https://github.com/Emir-Ars/Urun-indirim-takip/blob/b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5/tests/test_http.py) — `app/` HTTP mimari kuralı. fileciteturn18file2

Ekli belgelerin commit sürümüyle içerik eşitliği ayrıca yerel Git blob hash karşılaştırmasıyla kontrol edildi. Ek dosyalardaki fark yalnız Windows CRLF satır sonlarıydı; LF’ye normalize edildiğinde `AGENTS.md`, `proje_plani.md`, `teknik.md` commit blob SHA’larıyla eşleşti. `pyproject.toml` zaten doğrudan aynı Git blob hash’ine sahipti. Bu nedenle raporda “ekli plan başka, commit planı başka” belirsizliği yok. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2 fileciteturn0file3

### Resmî ve birincil teknik kaynaklar

**FastAPI**

[FastAPI release notes](https://fastapi.tiangolo.com/release-notes/) — 0.143.0, 8 Ekim 2026; aynı günkü breaking telemetry değişikliği. citeturn4search1  
[FastAPI async](https://fastapi.tiangolo.com/async/) — normal `def` path operation/dependency’lerin thread pool davranışı. citeturn4search12  
[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/) — pool gibi paylaşılan kaynakların startup/shutdown yaşam döngüsü. citeturn4search13  
[FastAPI 0.143.0 PyPI](https://pypi.org/project/fastapi/0.143.0/) — Python sürüm metadatası ve release tarihi. citeturn9search1

**PostgreSQL / Psycopg**

[PostgreSQL transaction isolation](https://www.postgresql.org/docs/17/transaction-iso.html) — Read Committed ve Repeatable Read snapshot davranışı. citeturn5search3  
[PostgreSQL explicit locking](https://www.postgresql.org/docs/17/explicit-locking.html) — normal SELECT ile lock davranışlarının ayrımı. citeturn5search9  
[Psycopg features](https://www.psycopg.org/features/) — Python/PostgreSQL uyumluluğu ve sync/async desteği. citeturn4search6  
[Psycopg connection pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html) — sync/async pool modeli. Bu URL güncel geliştirme dokümantasyonu olarak servis edildiğinden burada yalnız API yaklaşımını doğrulamak için kullanıldı, belirli dev sürümünü önermek için kullanılmadı. citeturn4search2  
[psycopg-pool PyPI](https://pypi.org/project/psycopg-pool/) — kararlı pool dağıtımı ve Python 3.13 desteği. citeturn10search3

**Streamlit / Uvicorn**

[Streamlit 2026 release notes](https://docs.streamlit.io/develop/quick-reference/release-notes/2026) — 1.65.0, 2 Ekim 2026. citeturn5search0  
[Streamlit 1.65.0 PyPI](https://pypi.org/project/streamlit/1.65.0/) — Python 3.13 ve Production/Stable metadata. citeturn9search2  
[`st.cache_data`](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data) — TTL ve cache temizleme. citeturn6search3  
[`st.fragment`](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment) — oturum açıkken periyodik bölüm yenileme. citeturn6search1  
[Streamlit configuration](https://docs.streamlit.io/develop/api-reference/configuration/config.toml) — address, CORS, allowed host ve XSRF seçenekleri. citeturn7search6  
[Uvicorn settings](https://www.uvicorn.org/settings/) — varsayılan loopback binding ve proxy-header güven ayarları. citeturn7search0

**SlowAPI**

[SlowAPI proje deposu](https://github.com/laurentS/slowapi) — özellikler ve bilinen kullanım sınırlamaları. citeturn7search2  
[SlowAPI 0.1.10 PyPI](https://pypi.org/project/slowapi/) — 13 Haziran 2026 release ve Python 3.13 metadata. citeturn8search1  
[FastAPI >=0.137 router/default-limits issue](https://github.com/laurentS/slowapi/issues/281) — 17 Temmuz 2026 tarihli açık upstream hata raporu. Bu rapor bu araştırmada bağımsız olarak yeniden üretilmedi; bu nedenle “kanıtlanmış genel arıza” değil, entegrasyon öncesi doğrulanması gereken uyumluluk riski olarak kullanıldı. citeturn7search1

### Doğrulanamayan veya bilerek doğrulanmayan noktalar

**Gerçek `fiyat_takip` veritabanının 8 Ekim 2026 bu araştırma anındaki içeriğine bağlanmadım.** Dolayısıyla 59 ürün/334 bağlantı/332 aktif bağlantı, son tur 237 teklif + 95 Tükendi, 20.805 Cimri satırı ve benzeri operasyonel sayılar commit’teki kapanış kanıtlarından doğrulanmıştır; bu rapor yeni bir canlı DB denetimi değildir. fileciteturn13file0

**Trendyol, Hepsiburada veya Cimri’ye canlı istek atmadım.** Bu nedenle 1190 testin veya 8 Ekim sabahı başarılı turun ardından kaynak sitelerin şu anda hâlâ aynı HTML/API davranışına sahip olduğunu iddia etmiyorum. Bu, kullanıcı talebiyle de uyumludur.

**Windows Task Scheduler’ın makinedeki bugünkü gerçek durumunu incelemedim.** Commit belgeleri 10:00/22:00 toplama ve Pazar 14:00 keşif düzenini bildiriyor; burada önerdiğim “API/UI bu görevleri değiştirmesin” planı mevcut belgelenmiş düzene dayanıyor. fileciteturn13file0

**API sorgu performansı gerçek veri üzerinde benchmark edilmedi.** Bu nedenle connection-pool boyutu, history maksimum response boyutu ve ek indeks gereksinimi tahminle “kesinleştirilmedi”. Mevcut ölçek için önce mevcut indekslerle ölçmek öneriliyor.

**SlowAPI’nin açık FastAPI >=0.137 uyumluluk raporunu bu proje üzerinde yeniden üretmedim.** 0.1.10 sürümünün rapordan önce yayımlanmış olması ve issue’nun hâlâ upstream’de görünmesi, yalnız “yerel ilk sürümün zorunlu bağımlılığı yapmama” önerisini destekliyor. citeturn7search1turn8search1

**30 günlük dip, tarihi zirve ve volatilite için plan tarafından onaylanmış formül yok.** Bu rapordaki tam-kapsam filtresi, karşılaştırılabilir zincir, log-getiri ve minimum örneklem eşikleri açıkça **araştırma önerisidir**; mevcut kullanıcı kararı gibi değerlendirilmemelidir. Planın mevcut kararı yalnız bu göstergelerin takip geçmişinden türetileceği ve 30 günlük veri yoksa 30 günlük rozetin gösterilmeyeceği kadardır. fileciteturn17file0

**Son hazırlık değerlendirmesi:** Aşama 7 için zorunlu yeni veri toplama, 001–004 migration değişikliği veya ML/Docker çalışması gerekmiyor. Kodlamadan önce kapanması gereken çekirdek karar seti; **API “current” semantiği, stale eşiği, summary ölçütleri, Streamlit→FastAPI HTTP istisnası ve sync pool tercihidir**. Bunlar kapandıktan sonra veri tabanı okuma katmanı → FastAPI → history/summary → Streamlit → tazelik/işletim sırası, her adımı `_test` veritabanı ve ağsız testlerle ayrı doğrulanabilen en düşük riskli Aşama 7 yolu olarak görünüyor.