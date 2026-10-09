# Aşama 7 (FastAPI + Streamlit) Hazırlık Değerlendirmesi — Urun-indirim-takip

Altyapı Aşama 7'ye **koşullu olarak hazır**: veri modeli (değişmez sonuçlar, tur bazlı karşılaştırılabilirlik görünümü, ayrı Cimri tablosu) güvenli bir salt okunur API için sağlam bir temel sunuyor, ancak kod yazmaya başlamadan önce en az beş karar netleşmeli (Streamlit→FastAPI HTTP istemcisinin app/ kuralıyla ilişkisi, sayfa/teklif düzeyinde "güncel teklif" sorgusunun yeri ve 005 migration ihtiyacı, salt okunur DB rolü, veri yaşı eşikleri, Cimri verisinin arayüzde gösterilip gösterilmeyeceği) ve planlanan 30 günlük rozetler kendi geçmişimizle en erken Ekim 2026 sonunda üretilebilir.

**Araştırma tarihi:** 8 Ekim 2026 (Europe/Istanbul). **Önemli erişim sınırı:** Bu araştırmada yalnızca reponun `main` dalındaki ana sayfa/README okunabildi; b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5 commit'indeki kaynak dosyalar (migration'lar, `connection.py`, `test_http.py`, `teknik.md`, `proje_plani.md`, `ci.yml`) ve CI sonucu açılamadı. Bu yüzden şema ve fonksiyon davranışına dair her ifade **"belgeden doğrulanmış (kodla doğrulanmadı)"** düzeyindedir.

## TL;DR

- **Hazırlık:** Veri katmanı sunuma uygun (kapanmış tur sonuçları donuk, `product_run_prices` karşılaştırılabilirliği zaten işaretliyor), fakat güncel teklif ekranı için gereken sayfa/satıcı/stok düzeyi okuma, "son başarılı fiyat" ve "veri yaşı" tanımları, salt okunur rol ve FastAPI/Streamlit bağımlılıkları henüz yok; bunlar doğrulanmış eksik veya açık karar olarak ele alınmalı.
- **Mimari önerisi:** Senkron `def` uç noktaları + Psycopg 3 senkron bağlantı (gerekirse küçük `psycopg_pool.ConnectionPool`), `READ ONLY` ve çok sorgulu özetlerde `REPEATABLE READ` işlemleri, Uvicorn ve Streamlit yalnız 127.0.0.1'de, tek worker; önbellek anahtarı "son tamamlanan tur kimliği" olduğu için yeni tur bitince eski veri kendiliğinden geçersizleşir. SlowAPI yerel tek kullanıcılı ilk sürümde gereksiz; dış erişim aşamasına ertelenmeli.
- **Uygulama sırası:** Aşama 7'yi 10 küçük alt adıma (7.0 kararlar → 7.9 işletim belgesi) bölün; her adım canlı ağsız, yalnız `*_test` veritabanında koşan kabul testleriyle kapansın; ilk adım kullanıcıya sorulacak kararların kapatılmasıdır, kod değil.

## 1. Mevcut duruma ilişkin kısa değerlendirme

**Projeden doğrulanan (README, `main` dalı; commit eşleşmesi doğrulanmadı):**
- README "Keşif, fiyat toplama ve veritabanı aşamaları tamamlandı. API, kullanıcı arayüzü ve tahmin modeli henüz geliştirilmedi" diyor; yol haritasında FastAPI/Streamlit satırı "Planlandı".\[1\]
- 8 Ekim 2026 itibarıyla: 24 model ailesi; 59 ürün, 334 bağlantı (332 etkin); son tur 332 sonuç (237 fiyat, 95 Tükendi, 0 hata); Cimri geçmişi 57 ürün, 20.805 kayıt (20.252 fiyat + 553 eksik); 1190 test, 276'sı PostgreSQL üzerinde.\[1\]
- Kök dizinde `.github/workflows`, `app`, `artifacts`, `config`, `data`, `docs`, `scripts`, `tests`, `AGENTS.md`, `README.md`, `proje_plani.md`, `pyproject.toml` var; repo 37 commit içeriyor; CI rozeti `ci.yml` iş akışına bağlı.\[1\]
- README "Cimri geçmişi bu akışın gözlemleriyle birleştirilmez" ve "Okuma hatası stoksuzluk olarak kaydedilmez" ifadelerini içeriyor.\[1\]

**Belgeden doğrulanmış (ekli AGENTS.md/pyproject/plan/teknik özeti; kodla doğrulanmadı):**
- `pyproject.toml` FastAPI, Streamlit, SlowAPI içermiyor (25 Eylül'de kaldırılmış).
- `product_run_prices` normal görünüm; yalnız `completed` turları içeriyor; tur × ürün en ucuz fiyat, önceki tur fiyatı ve `comparable_with_previous` veriyor.
- 002/003 tetikleyicileri sonuçları bir kez yazılıp donan hâle getiriyor; kapanmış tura yazım reddediliyor.
- Kendi geçmiş 28 Eylül 2026'dan beri (~10 gün, 19 tur); 2–4 Ekim arasında ~40 saatlik boşluk var.

**Değerlendirme (öneri):** Bu veri modelinin en değerli özelliği, kapanmış turların **değişmez** olmasıdır. Bu, API ve Streamlit tarafında önbelleği "son tamamlanan `run_id`" ile anahtarlamayı güvenli kılar: aynı `run_id` için sonuç asla değişmez, yeni tur bitince anahtar değişir. Asıl risk teknik değil, **sunum anlamı** tarafındadır: eski veri, kısmi kapsam, Tükendi ve karşılaştırılamayan turların kullanıcıya yanlış "indirim" gibi görünmesi.

## 2. Doğrulanmış eksikler ve kabul edilmiş sınırlar

Etiketler: **[DE]** doğrulanmış eksik · **[AK]** açık karar · **[KS]** kabul edilmiş sınır · **[GA]** gelecek aşama. Kanıt düzeyi: *README* (canlı repo ana sayfası), *Belge* (ekli belge özeti, kodla doğrulanmadı), *Erişilemedi*.

| # | Bulgu | Sınıf | İlgili dosya/bölüm | Gerekçe | Kanıt |
|---|---|---|---|---|---|
| 1 | FastAPI, Uvicorn, Streamlit bağımlılıkları yok | DE | `pyproject.toml` | 25 Eylül'de kaldırıldı; "ilgili aşamada yeni tasarıma göre yeniden eklenecek" | Belge |
| 2 | API ve arayüz kodu yok | DE | `app/` | README: "API, kullanıcı arayüzü … henüz geliştirilmedi"; `_eski_taslaklar/` Git dışı, tamamlanmış iş sayılmaz | README + Belge |
| 3 | Güncel teklif ekranı için sayfa düzeyi okuma yok | DE | `002_guards_and_comparability.sql` (`product_run_prices`) | Görünüm yalnız `best_price`/`best_listing_id` veriyor; platform, satıcı, puan, stok durumu, sayfa bazlı sonuç için `listing_checks` + `listings` birleştiren ayrı sorgu/görünüm gerekir | Belge |
| 4 | "Ürün başına son başarılı fiyat" ve "veri yaşı" tanımı yok | DE | `product_run_prices`, plan Bölüm 9 | Görünüm hepsi Tükendi ise `best_price = NULL` veriyor; son fiyatlı tura geri dönüş ve yaş hesabı tanımlı değil | Belge |
| 5 | Ayrı salt okunur DB rolü yok | DE / AK | `teknik.md` kurulum, `connection.py` | `fiyat_takip` iki DB'nin sahibi; API bu rolle bağlanırsa yazma yetkisi taşır | Belge |
| 6 | Bağlantı havuzu yok | AK | `app/database/connection.py` | Toplama için gerekmedi; API için gerekip gerekmediği ölçeğe bağlı (Bölüm 3) | Belge |
| 7 | Streamlit→FastAPI HTTP istemcisi ile app/ HTTP kuralı çelişebilir | AK | `AGENTS.md`, `tests/test_http.py` | Kural app/ içinde requests/httpx yasaklıyor; FastAPI `TestClient` httpx'e dayanıyor | Belge + dış kaynak; `test_http.py` erişilemedi |
| 8 | Plan "SlowAPI ile oran sınırlandırma" diyor ama bağımlılık kaldırıldı ve erişim yalnız localhost | AK (plan tutarsızlığı) | `proje_plani.md` Bölüm 9, `pyproject.toml` | Plan ile mevcut çalışma ortamı uyuşmuyor | Belge |
| 9 | 30 günlük dip / zirve / volatilite tanımı ve veri yeterlilik koşulu yok | DE | `proje_plani.md` Bölüm 9 | Plan yalnız "30 günlük veri yoksa rozet gösterilmez" diyor; hangi seri (kendi/Cimri), hangi kapsam eşiği belirsiz | Belge |
| 10 | 30 günlük kendi geçmiş henüz yok | KS (geçici) | — | İlk tur 28 Eylül; 30 güne en erken ~28 Ekim 2026'da ulaşılır, boşluklar nedeniyle kapsam eşiği daha geç sağlanabilir | Belge |
| 11 | Cimri verisinin arayüzde gösterilmesi | AK | `004_market_history.sql`, `teknik.md` | Cimri kullanım koşullarında kopyalama/işleme kısıtları (2.2, 3.1, 4.12) belirtilmiş; kullanım izni doğrulanmamış | Belge |
| 12 | İki Cimri ürünü eşleşmemiş (Galaxy S25 512 GB, Redmi Note 14 Pro 5G 256 GB) | KS | `market_history` | Eksik doldurulmayacak; arayüzde "Cimri geçmişi yok" denmeli\[1\] | README + Belge |
| 13 | Bilgisayar uyurken tur kaçıyor (~40 saatlik boşluk) | KS | Görev Zamanlayıcı | Uyandırma yok; grafikte boşluk olarak korunmalı | Belge |
| 14 | Katalog pazaryerinin tamamını kapsamaz; Kritik Stok yalnız Trendyol sinyali\[1\] | KS | README, `teknik.md` | "Takip edilen en ucuz" ifadesi kullanılmalı, "piyasanın en ucuzu" değil | README + Belge |
| 15 | Geçmiş sorguları için indeks yeterliliği | AK (doğrulanamadı) | migration'lar | Migration dosyaları okunamadı; `listing_checks (product_id, run_id)` vb. indekslerin varlığı bilinmiyor | Erişilemedi |
| 16 | teknik.md test tablosunun 1190 toplamıyla tutarlılığı | Doğrulanamadı | `docs/teknik.md` | Dosya açılamadı; README yalnız toplamı veriyor | Erişilemedi |
| 17 | Başlangıç commit'inin CI sonucu | Doğrulanamadı | `.github/workflows/ci.yml`, Actions | GitHub API bot korumasıyla reddetti | Erişilemedi |
| 18 | ML, Docker, sürekli çalışma, dış erişim | GA | plan Aşama 8+ | Kapsam dışı | Belge |

**Plan–belge–kod tutarsızlıkları (özet):** (a) SlowAPI planda var, bağımlılıklarda ve gereksinimde yok; (b) plan "takip edilen geçmişten" diyor, Cimri'nin rozet hesabına girip girmeyeceği yazılı değil; (c) `product_run_prices` "comparable_with_previous = false satırlarının yorumu tüketen aşamanın işidir" diyor, ancak bu yorum kuralı henüz hiçbir belgede tanımlı değil. Kodla karşılaştırma yapılamadığı için kod tarafında ek tutarsızlık olup olmadığı **açık sorudur**.

## 3. Aşama 7 için gerekli kararlar ve seçenekler

### 3.1 Streamlit→FastAPI iletişimi ve app/ HTTP kuralı (Karar 7 — açık karar)

**Dış kaynak:** FastAPI test belgesi `TestClient`'ın HTTPX'e dayandığını ve "To use TestClient, first install httpx" dediğini belirtir (https://fastapi.tiangolo.com/tutorial/testing/). \[2\] Haziran 2026 tarihli bir FastAPI GitHub tartışmasında Starlette'in `httpx` kullanımını kullanımdan kaldırma uyarısı verdiği ve `httpx2` önerdiği bildiriliyor (https://github.com/fastapi/fastapi/discussions/15742) \[3\] — bu resmî belge değil, kurulum sırasında sürüm notlarıyla doğrulanmalı. Streamlit 1.64.0 sürüm notları uygulama kodunda async/await ve httpx gibi kütüphanelerin doğrudan kullanılabildiğini söylüyor (https://docs.streamlit.io/develop/quick-reference/release-notes). \[4\]

| Seçenek | Açıklama | Kuralla ilişkisi | Artı | Eksi |
|---|---|---|---|---|
| A. `frontend/` ayrı üst dizin, httpx ile API çağrısı | Streamlit kodu app/ dışında | Kural metni "app/ içinde" dediği için **çelişmez**, ama kuralın amacı (tek HTTP kapısı) yeniden yorumlanır | Katmanlar net; FastAPI tek veri kaynağı | Yeni bağımlılık; `test_http.py`'nin tarama kapsamı doğrulanmalı |
| B. Streamlit doğrudan DB okur (paylaşılan sorgu modülü) | HTTP yok | Çelişki yok | En basit, en az parça | Karar 2'nin "FastAPI hazırlanmış özetleri sunar" amacıyla örtüşmez; iki tüketici aynı mantığı paylaşmalı |
| C. `app/scraper/http.py` ve curl_cffi ile API çağrısı | Kural harfiyen korunur | Çelişmez | Yeni HTTP kütüphanesi yok | Tarayıcı taklidi yapan kazıma istemcisini iç API için kullanmak sorumluluk karışıklığı yaratır |
| D. Kural kapsamını "dış ağ HTTP'si" olarak yeniden yazmak | — | **Kural değişikliği** | Uzun vadede net | Kullanıcı kararı gerekir; sessizce yapılamaz |

**Öneri:** A seçeneği; `TestClient` için httpx (veya doğrulandıysa httpx2) yalnız `dev` bağımlılığı ve `tests/` altında; Streamlit istemcisi `frontend/` altında. Bu, kural metnini değiştirmez ama `test_http.py`'nin app/ dışını taramadığı **kodla doğrulanmalıdır** (dosyaya erişilemedi). Kullanıcıdan açık onay alınmalı.

### 3.2 Senkron/asenkron erişim ve bağlantı yönetimi

**Dış kaynak:**
- FastAPI: normal `def` ile tanımlanan path operation "external threadpool" içinde çalışır; `async def` olay döngüsünde çalışır ve içinde bloklayan G/Ç olmamalıdır (https://fastapi.tiangolo.com/async/). \[5\]
- Psycopg: "On Windows, Psycopg is not compatible with the default ProactorEventLoop. Please use a different loop, for instance the SelectorEventLoop" (https://www.psycopg.org/psycopg3/docs/advanced/async.html). Bağlantı nesneleri thread-safe, cursor'lar değil.\[6\]
- psycopg_pool ayrı pakettir (`psycopg[pool]`); `ConnectionPool` çok thread'li kullanım içindir, varsayılan `min_size=4`, `timeout=30`; `open` varsayılanının ileride `False` olabileceği, async havuzu yapıcıda açmanın kullanımdan kalktığı uyarılıyor; FastAPI için `lifespan` örneği veriliyor; `NullConnectionPool` önceden bağlantı açmayan alternatiftir (https://www.psycopg.org/psycopg3/docs/advanced/pool.html). \[7\]\[8\] *Not: okunan belge sayfası 3.3.7.dev1 geliştirme sürümüne ait; davranış kararlı 3.3.x ile kurulumda karşılaştırılmalı.*

| Seçenek | Uygunluk (1 kullanıcı, 59 ürün, Windows) | Değerlendirme |
|---|---|---|
| `def` + istek başına `psycopg.connect` | Yeterli | localhost bağlantısı ucuz; mevcut `connection.py` (UTC, timeout'lar) yeniden kullanılabilir; ek bağımlılık yok |
| `def` + `ConnectionPool(min_size=1, max_size=4)` | İyi | Streamlit birkaç paralel çağrı yaparsa gecikme azalır; `lifespan` ile aç/kapa; `psycopg-pool` bağımlılığı eklenir |
| `async def` + `AsyncConnectionPool` | Bu ölçekte gereksiz | Windows'ta SelectorEventLoop zorunluluğu; Uvicorn'un döngü seçimiyle etkileşim test gerektirir; öğrenme maliyeti yüksek |

**Öneri:** İlk sürümde senkron `def` uç noktaları. Havuz tercihi bir **açık karar**: "istek başına bağlantı" ile başlanıp ölçüm sonrası `ConnectionPool`'a geçmek mümkündür; her iki durumda da bağlantı ayarları (UTC, `connect_timeout`) tek yerden gelmeli.

### 3.3 Eşzamanlı toplama ile API okumaları

**Dış kaynak:** PostgreSQL 17'de Read Committed her ifadenin başında yeni anlık görüntü alır; Repeatable Read ise işlemdeki ilk (işlem kontrolü olmayan) ifadenin başındaki anlık görüntüyü tüm işlem boyunca kullanır ve eşzamanlı işlemlerin işlediği değişiklikleri görmez (https://www.postgresql.org/docs/17/transaction-iso.html). \[9\] `SET TRANSACTION … READ ONLY` işlem erişim kipini belirler (https://www.postgresql.org/docs/current/sql-set-transaction.html). \[10\]

**Öneri:**
- Tüm API okumaları `READ ONLY` işlemde; birden fazla sorgudan oluşan yanıtlar (özet: son tur + teklifler + istatistik) `REPEATABLE READ READ ONLY` içinde, böylece yanıt ortasında tur kapanırsa karışık veri dönmez.
- API `data/scrape.lock` dosya kilidini ve tur advisory kilidini **almamalı**; MVCC okumaları yazıcıyı bloklamaz. Bu, mevcut zamanlayıcı akışının etkilenmemesinin temel koşuludur.
- Uzun sorguya karşı API rolüne `statement_timeout` (ör. 5 sn) atanması önerilir — bu değer kaynakla doğrulanmadı, öneridir.
- Salt okunur rol: PostgreSQL resmî "Predefined Roles" belgesine göre `pg_read_all_data` "allows reading all data (tables, views, sequences), as if having SELECT rights on those objects, and USAGE rights on all schemas" (https://www.postgresql.org/docs/current/predefined-roles.html; rol PostgreSQL 14'te eklendi); alternatif olarak şema/tablo bazında `GRANT SELECT` kullanılabilir. `default_transaction_read_only` bir güvenlik önlemi değildir, oturumda geri alınabilir (https://postgresqlco.nf/doc/en/param/default_transaction_read_only/); asıl koruma yetki (GRANT) düzeyinde olmalı.\[11\] `pg_read_all_data` tüm tabloları okuttuğu için en dar yetki açısından tablo/görünüm bazında GRANT tercih edilmeli. PostgreSQL CREATE ROLE belgesi "You must have CREATEROLE privilege or be a database superuser to use this command" der (https://www.postgresql.org/docs/current/sql-createrole.html); `fiyat_takip` superuser olmadığından ve CREATEROLE yetkisi yoksa rolü bir superuser (ör. `postgres`) oluşturmalıdır — aynı belge CREATEROLE sahibi rolleri "almost-superuser-roles" saymayı önerdiği için bu yetkiyi `fiyat_takip`'e vermek önerilmez.

### 3.4 Tur durumları ve veri yaşı ayrımı

| Kavram | Önerilen tanım | Kaynak tablo |
|---|---|---|
| Süren tur | `collection_runs.status = 'running'` (kısmi benzersiz indeks tek tane garanti ediyor — belge) | `collection_runs` |
| Son tamamlanan tur | `status = 'completed'` olan en büyük `started_at` | `collection_runs` / `product_run_prices` |
| Ürünün son gözlemi | Son tamamlanan turda ürünün satırı (fiyat, hepsi Tükendi veya cevap yok) | `product_run_prices` |
| Ürünün son başarılı fiyatı | `best_price IS NOT NULL` olan en son tamamlanan tur; ayrı alan olarak ve **kendi zaman damgasıyla** | `product_run_prices` |
| Veri yaşı | `now() − son tamamlanan turun started_at` (UTC); ürün düzeyinde ayrıca "son başarılı fiyat yaşı" | — |
| Eski veri | Öneri: yaş > 14 saat (12 saatlik aralık + 2 saatlik tur sınırı) "eski", > 36 saat "çok eski" | Açık karar |

**Öneri:** Süren turun fiyatları ilk sürümde **gösterilmez** (görünüm zaten dışlıyor); yalnız "Toplama sürüyor (başlangıç saati)" bilgisi verilir. `interrupted` turlar fiyat kaynağı olmaz, sadece işletim bilgisinde listelenir.

## 4. Önerilen ilk sürüm kapsamı ve mimari

### 4.1 Mimari (öneri)

```
Görev Zamanlayıcı (değişmez) → app.collection → PostgreSQL (fiyat_takip)
                                                   ↑ salt okunur rol, READ ONLY işlemler
                             FastAPI (Uvicorn, 127.0.0.1:8000, 1 worker, def uç noktaları)
                                                   ↑ HTTP (localhost)
                             Streamlit (frontend/, 127.0.0.1:8501, st.cache_data)
```

**Sürümler (8 Ekim 2026, PyPI/resmî notlar):** FastAPI 0.143.0 8 Ekim 2026'da, 0.142.2 30 Eylül'de yayımlandı (https://pypi.org/project/fastapi/, https://fastapi.tiangolo.com/release-notes/); \[12\]\[13\] araştırma günü çıkan sürüm yerine bir önceki kararlı satırın (0.142.x) üst sınırla sabitlenmesi önerilir, FastAPI 0.x olduğu için küçük sürümler arasında kırılma olabilir. Streamlit en son 1.64.0 (15 Eylül 2026) ve `st.cache` 1.62.0'da kaldırıldı (https://docs.streamlit.io/develop/quick-reference/release-notes, https://docs.streamlit.io/develop/concepts/architecture/caching); \[4\]\[14\] `streamlit-nightly` gibi ön sürümler kullanılmamalı. SlowAPI 0.1.10 (13 Haziran 2026), sınıflandırıcıları Python 3.13'ü içeriyor (https://pypi.org/project/slowapi/). \[15\] Python 3.13 uyumluluğu FastAPI/Streamlit/psycopg-pool için kurulumda `pip` çözümlemesiyle doğrulanmalı — bu araştırmada her paketin 3.13 tekerleği tek tek doğrulanmadı.

### 4.2 İlk sürüm uç noktaları (öneri)

| Uç nokta | Amaç | Temel alanlar | Boş/NULL kuralı |
|---|---|---|---|
| `GET /health` | DB erişimi, şema sürümü | `db_ok`, `schema_version` | DB yoksa 503 |
| `GET /runs/status` | Süren ve son tamamlanan tur | `running_run {run_id, started_at} \| null`, `last_completed_run {run_id, started_at, finished_at}`, `data_age_hours`, `freshness` (`fresh`/`stale`/`very_stale`) | Hiç tur yoksa `last_completed_run: null` |
| `GET /products` | Telefon seçimi | `product_id, brand, model, storage_gb, active, has_market_history` | Sayfalama: `limit` (vars. 100, en çok 200) + `offset`; 59 ürün için tek sayfa yeter |
| `GET /products/{id}` | Ürün kimliği | yukarıdaki + etkin sayfa sayısı | 404 |
| `GET /products/{id}/offers/latest` | Güncel teklif ekranı | son tamamlanan tur için her sayfa: `listing_id, platform, color, outcome (offer/sold_out/error), error_code, current_price_kurus, original_price_kurus, seller_name, seller_rating, seller_rating_scale, stock_status, checked_at` + ürün özeti `best_price_kurus, best_listing_id, answered_pages, planned_pages` + `last_successful_price {price_kurus, run_id, run_started_at}` | Tükendi'de fiyat `null` (asla 0); hata satırında fiyat `null` + `error_code` |
| `GET /products/{id}/history?from=&to=` | Kendi geçmiş | tur başına `run_id, run_started_at, best_price_kurus\|null, planned/answered/offer/sold_out/error_pages, comparable_with_previous, previous_best_price_kurus, hours_since_previous` | Tarih aralığı UTC ISO 8601, yarı açık `[from, to)`; varsayılan son 30 gün; en çok 400 gün; sıralama `run_started_at` artan |
| `GET /products/{id}/summary` | Hazır özet | `current`, `change_vs_previous` (yalnız karşılaştırılabilirse), `low_30d`, `high_since_tracking`, `volatility_30d`; her istatistikte `value\|null`, `status` (`ok`/`insufficient_data`), `n_runs`, `coverage_ratio`, `window_start/end` | Yetersiz veride `value: null` + neden |
| `GET /products/{id}/market-history?source=cimri` | Cimri ayrı kaynak | `day, price_kurus\|null, source='cimri', captured_at` + kaynak açıklaması | Eşleşme yoksa 404 değil, boş liste + `matched: false` (Karar 11'e bağlı) |

**Alan kuralları (öneri):** Para her zaman `_kurus` sonekli tamsayı; TL biçimlendirme yalnız Streamlit'te. Zamanlar UTC (`Z`); Streamlit Europe/Istanbul'a çevirir. `null` = "bilinmiyor/gözlenmedi"; `0` hiçbir zaman "yok" anlamına gelmez. Pydantic yanıt modelleri `response_model` ile tanımlanmalı ve `None` alanlar açıkça `Optional` olmalı.

**Uygulama yeri (açık karar):** 3, 4 numaralı eksikler için (a) API içinde ham SQL sorgusu, (b) yeni `005_*.sql` migration'ı ile görünüm(ler) (ör. son tamamlanan tur sayfa sonuçları, ürün başına son başarılı fiyat) ve gerekirse indeks + salt okunur rol GRANT'ları. 001–004 değiştirilmez. Görünüm yaklaşımı mantığı DB'de tek yerde toplar ve testlenebilirliği artırır, fakat migration gerektirir ve "tur şema güncel değil" kontrolü nedeniyle migrate edilmeden toplama turu başlamaz — uygulama zamanlaması tur saatlerinin dışına alınmalı. Kalıcı (materialized) görünüm bu ölçekte gereksiz: 59 ürün × günde 2 tur küçük bir veri kümesi.

### 4.3 Kullanıcıya doğru bilgi sunma kuralları (öneri)

- **Tükendi:** "Tükendi" rozeti, fiyat hücresi boş; ürünün tüm sayfaları Tükendi ise "Takip edilen sayfalarda stok yok" + varsa "son görülen fiyat X (tarih)" ayrı satırda.
- **Okunamayan sayfa (error):** "Okunamadı (`network`/`blocked`…)" — asla "Tükendi" değil; ürün özetinde "332 sayfadan N'i okunamadı" yerine ürün düzeyinde `answered_pages/planned_pages` kapsam göstergesi.
- **Kısmi kapsam:** `answered_pages < planned_pages` ise en ucuz fiyatın yanında "kısmi kapsam (x/y sayfa)" uyarısı.
- **Eski fiyat:** `freshness` `stale` ise sayfa başında sarı uyarı ve son tur saati; `very_stale` ise fiyatlar soluk gösterilir.
- **Yanıltıcı indirimi önleme:** "Önceki tura göre değişim" yalnız `comparable_with_previous = true` iken gösterilir; değilse "karşılaştırılamaz: cevap veren sayfalar değişti". `hours_since_previous` büyükse (ör. 40 saat) "önceki gözlem X saat önce" bilgisi eklenir. `original_price` (üstü çizili) satıcı beyanı olarak etiketlenir, "indirim" hesabına referans yapılmaz (belgedeki kural).
- **Grafikler:** Vega-Lite'ta varsayılan olarak `null` x/y değerleri çizgiyi kırar; `invalid` kipi `filter`, `break-paths-filter-domains`, `break-paths-show-domains` seçeneklerini sunar (https://vega.github.io/vega-lite/docs/invalid-data.html, https://vega.github.io/vega-lite/docs/line.html). \[16\]\[17\] Kritik ayrıntı: **hiç satırı olmayan** kaçmış turlar `null` üretmez, çizgi 40 saatlik boşluğu düz bağlar. Bu yüzden API veya Streamlit, ardışık turlar arası boşluk eşik (ör. 18 saat) aşınca araya açık bir `null` noktası eklemeli; Tükendi turları `null` olarak kalmalı (sıfır değil). Bu kontrol için `st.altair_chart` ile açık Altair tanımı önerilir; `st.line_chart`'ın `null` davranışı bu araştırmada doğrulanmadı.
- **Cimri:** Ayrı sekme veya ayrı renk/çizgi stili, "Cimri'de listelenen satıcılar arasındaki en ucuz (günlük, dış kaynak)" açıklamasıyla; kendi serimizle aynı eksende birleştirilmez, aynı çizgiye eklenmez; 553 eksik gün boşluk olarak kalır; tekrarlanan değerlerin bağımsız gözlem olmadığı notu. Gösterimin kendisi Karar 11'e bağlı.

### 4.4 İstatistik tanımları ve yeterli veri koşulları (öneri — dış kaynakla desteklenmedi)

Bu araştırmada fiyat volatilitesi/eksik örneklem için güvenilir bir dış kaynak toplanamadı; aşağıdakiler gerekçeli önerilerdir ve kullanıcı onayı gerektirir.

| Ölçüm | Önerilen tanım | Yeterli veri koşulu | Yetersizse |
|---|---|---|---|
| 30 günlük dip | Pencere `[now−30g, now)` içindeki tamamlanan turların `best_price` minimumu (yalnız kendi serimiz) + gerçekleştiği tur zamanı | İlk turdan bu yana ≥ 30 gün **ve** penceredeki beklenen 60 turun ≥ %75'i (≥ 45) tamamlanmış **ve** fiyatlı tur sayısı ≥ 30 | `null` + `insufficient_data`; rozet yok |
| Tarihi zirve | Takip başlangıcından bu yana `best_price` maksimumu; adı "takip başlangıcından (28 Eylül 2026) beri en yüksek" | ≥ 10 fiyatlı tur (öneri) | `null`; "tüm zamanlar" ifadesi kullanılmaz |
| Volatilite | Önce Europe/Istanbul gününe göre günlük minimum; ardışık **takvim günleri** arasında log getiri; standart sapması. Ardışık olmayan günler (boşluk) getiri üretmez | Pencerede ≥ 20 geçerli günlük getiri | `null`; alternatif olarak sadece "30 günlük aralık % = (max−min)/medyan" gösterilebilir |

**Gerekçe:** Günde 2 anlık görüntü düzensiz (kaçan turlar, 40 saatlik boşluk); boşlukları enterpolasyonla doldurmak Karar 4'ü (eksik fiyat uydurulmaz) ihlal eder. Günlük toplama, 10:00/22:00 tur farklarını yumuşatır ve Cimri'nin günlük yapısıyla kavramsal olarak uyumludur — ama seriler yine birleştirilmez. Cimri tabanlı ayrı bir "365 günlük dip/zirve" istenirse, ayrı alan ve ayrı etiketle sunulmalı; bu da Karar 11'e bağlı. Karşılaştırılamayan turların dibe dahil edilip edilmemesi açık karar: bir turda daha çok sayfa cevap verdiyse daha düşük bir minimum gerçek bir gözlemdir, ancak "dip" rozetini daha dar kapsamlı turlarla karşılaştırmak yanıltabilir.

### 4.5 Streamlit ekranları ve önbellek (öneri)

**Ekranlar:**
1. **Seçim:** `st.selectbox` — "Marka Model Kapasite" etiketi, katalogdan (`/products`); pasif ürünler ayrı işaretli. Seçim yalnız API okuması tetikler (Karar 1).
2. **Teklif özeti:** üstte durum çubuğu (son tur saati, veri yaşı, süren tur varsa bilgi); en ucuz teklif kartı (fiyat, platform, satıcı, puan/ölçek, stok, gözlem zamanı, kapsam x/y); altında sayfa tablosu (Tükendi/Okunamadı rozetleri).
3. **Geçmiş:** kendi serimiz grafiği (boşluklar korunmuş), karşılaştırılabilirlik işaretli noktalar; istatistik kartları (yetersiz veride "henüz yeterli veri yok: n/45 tur"); ayrı Cimri sekmesi.

**Önbellek:** `st.cache_data` `ttl` ve `func.clear()` / `st.cache_data.clear()` destekler; `persist="disk"` iken `ttl` yok sayılır; süresi dolan girdiler tembel temizlenir (https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data, https://docs.streamlit.io/develop/concepts/architecture/caching). \[14\]\[18\]\[19\]\[20\] Önerilen düzen: `/runs/status` kısa `ttl` (ör. 60 sn) ile; ürün verisi fonksiyonları `last_completed_run_id` parametresi alır ve uzun `ttl` ile önbelleklenir — yeni tur tamamlanınca `run_id` değişir, yeni anahtar oluşur, eski veri kendiliğinden kullanılmaz. Disk kalıcılığı kullanılmamalı. Otomatik yenileme için Streamlit belgesi `st.fragment(func=None, *, run_every=None, parallel=False, key=None)` imzasını verir ve "If run_every is set, Streamlit will also rerun the fragment at the specified interval while the session is active, even if the user is not interacting with your app" der (https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment); ilk sürüm için "Yenile" düğmesi yeterli, `run_every` yalnız durum çubuğu için düşünülebilir.

### 4.6 Erişim sınırları ve SlowAPI

- **Yerel kullanım:** Uvicorn `--host` varsayılanı 127.0.0.1'dir; `--workers` varsayılanı 1'dir; `--reload` ile `--workers` birlikte kullanılamaz (https://uvicorn.dev/settings/, https://uvicorn.dev/deployment/). \[21\]\[22\]\[23\]\[24\]\[25\]\[26\] Streamlit `server.address` ayarlandığında sunucu yalnız o adresten erişilebilir (https://docs.streamlit.io/develop/api-reference/configuration/config.toml); \[27\] Streamlit'in varsayılan olarak tüm arayüzlere bağlandığı bir GitHub issue'sunda bildiriliyor (https://github.com/streamlit/streamlit/issues/10155) \[28\] — bu yüzden `server.address = "127.0.0.1"` ve `headless = true` açıkça yazılmalı. Kimlik doğrulama, CORS ve oran sınırı gerekmez (aynı makine, tek kullanıcı, Streamlit sunucu tarafından çağırdığı için tarayıcı CORS'u devreye girmez).
- **İleride dış erişim (gelecek aşama):** TLS sonlandıran ters vekil, kimlik doğrulama (API anahtarı/OAuth), CORS beyaz listesi, oran sınırlama, Cimri verisinin yeniden yayımlanması riskinin hukuki değerlendirmesi (bu rapor hukuki yorum yapmaz).
- **SlowAPI:** Bakımı sürüyor (0.1.10, Haziran 2026), Starlette/FastAPI için `limits` kütüphanesi üzerine sarmalayıcı, bellek/Redis/Memcached arka uçları ve sync/async uç nokta desteği var; README "tam async'e geçerken API değişiklikleri olabilir" uyarısı taşıyor (https://pypi.org/project/slowapi/, https://libraries.io/pypi/slowapi). \[15\]\[29\]\[30\] **Öneri:** İlk sürümde eklenmesin; plan satırı "dış erişim aşamasında değerlendirilecek" olarak güncellensin. Bu bir plan değişikliği önerisidir (korunan kararlardan biri değil); etkisi: bir bağımlılık ve bir yapılandırma katmanı daha az, test yüzeyi küçük.

### 4.7 Windows'ta çalıştırma (öneri)

- Mevcut `\FiyatTakip\FiyatToplamaTuru` ve `\FiyatTakip\HaftalikKesif` görevlerine dokunulmaz; API/arayüz aynı kilitleri almadığı için çakışmaz.
- İlk sürüm: iki PowerShell penceresinde elle başlatma (`.venv\Scripts\python.exe -m uvicorn … --host 127.0.0.1 --port 8000` ve `… -m streamlit run … --server.address 127.0.0.1`). Uvicorn Windows'ta spawn kullandığı için çoklu worker da çalışır, ama gerek yok.\[23\]\[26\]
- İsteğe bağlı: oturum açılışında tetiklenen ayrı bir Görev Zamanlayıcı görevi (ayrı klasör/ad, ör. `\FiyatTakip\ArayuzSunucu`), "yalnız oturum açıkken". NSSM gibi servis sarmalayıcıları bu araştırmada incelenmedi — açık soru; sürekli çalışma zaten gelecek aşamada.
- Port çakışması (8000/8501) ve PostgreSQL servisinin kapalı olması durumunda `/health` 503 dönmeli; Streamlit "veritabanına ulaşılamıyor" mesajı göstermeli, eski önbelleği "son bilinen veri" etiketiyle sunup sunmamak açık karar.

## 5. Alt adımlar ve kabul testleri

Tüm testler: canlı ağ yok, yalnız `*_test` veritabanı, sabit zaman (enjekte edilen "şimdi"), Black/Flake8 temiz, CI'da PostgreSQL 17 servisiyle.

| Adım | Amaç | Bağımlılık | Kabul ölçütü | Kullanıcıya sorulacak |
|---|---|---|---|---|
| 7.0 Kararlar | Bölüm 6'daki soruları kapatmak, plan Bölüm 9'u güncellemek | — | Plan/teknik belgede kararlar yazılı; kod yok | Tümü |
| 7.1 Bağımlılıklar | FastAPI, Uvicorn, Streamlit, (ops.) psycopg-pool, dev: httpx/httpx2 | 7.0 | `pip` çözümü Python 3.13'te temiz; üst sınırlı sürümler; mevcut 1190 test geçer; `test_http.py` hâlâ geçer | Sürüm sabitleme politikası |
| 7.2 Salt okunur rol | API için yalnız SELECT yetkili rol | 7.0 | Rol ile INSERT/UPDATE reddedilir; test DB'de doğrulanır; şifre pgpass'te | Rolü kim oluşturacak (superuser gerekir mi) |
| 7.3 Okuma sorguları / 005 | Son tamamlanan tur sayfa sonuçları, son başarılı fiyat, (ops.) indeks | 7.0, 7.2 | 001–004 bayt bayt aynı; 005 migrate edilir; sorgu testleri aşağıdaki senaryoları geçer | Görünüm mü sorgu mu; migration zamanı |
| 7.4 İstatistik fonksiyonları | Dip, zirve, volatilite + yeterlilik | 7.3 | Saf fonksiyon testleri: yetersiz veride `null`; boşluk enterpolasyonu yok | Eşikler (%75, 45 tur, 20 getiri) |
| 7.5 FastAPI iskeleti | `/health`, `/runs/status`, `/products` | 7.1–7.3 | TestClient ile 200/404/503; OpenAPI şeması üretilir | — |
| 7.6 Teklif/geçmiş/özet uçları | Bölüm 4.2 | 7.4, 7.5 | Senaryo testlerinin tamamı | Veri yaşı eşikleri |
| 7.7 Cimri ucu | Ayrı kaynak | 7.5, Karar 11 | `source='cimri'` dışında veri dönmez; kendi seriyle birleşmez | Göster/gösterme |
| 7.8 Streamlit | Seçim, teklif, geçmiş ekranları | 7.6 | API taklit edilerek (mock) ekran mantığı testleri; grafik verisinde boşluk `null`'ları; Tükendi'de 0 yok | İstemci konumu (frontend/) |
| 7.9 İşletim belgesi | Başlatma, port, sorun giderme | 7.8 | README/teknik.md güncel; zamanlayıcı görevleri değişmemiş | Açılışta otomatik başlatma |

**Kabul testi senaryoları (test DB fikstürleriyle):**
1. **Boş geçmiş:** Hiç tur yok → `/runs/status` `last_completed_run: null`; `/history` boş liste; özet istatistikleri `insufficient_data`.
2. **Hata:** Bir sayfa `error/network` → teklif listesinde `outcome=error`, fiyat `null`, "Tükendi" değil; kapsam x/y doğru.
3. **Tükendi:** Ürünün tüm sayfaları Tükendi → `best_price null`, `last_successful_price` önceki fiyatlı turdan; arayüzde 0 TL yok.
4. **Eski veri:** Sabit "şimdi" son turdan 20 saat sonra → `freshness=stale`; 40 saat → `very_stale`.
5. **Bağlantı kesintisi (DB):** Bağlantı reddi simülasyonu → `/health` 503, diğer uçlar 503 ve anlamlı hata gövdesi; Streamlit hata mesajı.
6. **Süren tur:** `running` tur + kısmi `listing_checks` → bu turun fiyatları hiçbir uçta görünmez; `running_run` dolu; son tamamlanan tur değişmez.
7. **Tur yanıt sırasında kapanır:** REPEATABLE READ işlem içinde ikinci sorgudan önce başka bağlantı turu tamamlar → yanıt tek tutarlı `run_id` içerir.
8. **Karşılaştırılamayan fiyat:** `comparable_with_previous=false` → `change_vs_previous` `null` + neden; arayüzde indirim rozeti yok.
9. **Boşluk:** 40 saatlik kaçan turlar → grafik verisinde araya `null` eklenmiş; volatilite boşluk üzerinden getiri hesaplamaz.
10. **Cimri ayrımı:** Eşleşmeyen ürün → `matched:false`; Cimri `NULL` günleri `null` kalır; kendi geçmiş ucuna Cimri satırı sızmaz.
11. **Yetki:** API rolüyle yazma denemesi reddedilir; API kodu `fiyat_takip` gerçek DB'ye testte bağlanmaz (bağlantı dizesi `_test` ile bitmiyorsa test başlamaz).
12. **Kural testi:** `test_http.py` app/ içinde httpx/requests olmadığını doğrulamaya devam eder.

## 6. Kullanıcıya sorulacak sorular

1. Streamlit→FastAPI istemcisi `frontend/` altında httpx ile mi olsun (Seçenek A), yoksa B/C/D'den biri mi? `test_http.py` app/ dışını tarıyor mu?
2. `TestClient` için httpx (veya httpx2) yalnız dev bağımlılığı olarak eklenebilir mi?
3. Sayfa düzeyi güncel teklif ve son başarılı fiyat için 005 migration ile görünüm mü, API içinde ham SQL mi?
4. Salt okunur DB rolü oluşturulsun mu; bunu hangi yetkili kullanıcı yapacak?
5. Bağlantı havuzu (`psycopg-pool`) ilk sürüme eklensin mi, yoksa istek başına bağlantıyla mı başlansın?
6. Veri yaşı eşikleri: "eski" 14 saat, "çok eski" 36 saat uygun mu?
7. 30 günlük dip için kapsam eşiği (%75 / 45 tur) ve karşılaştırılamayan turların dahil edilmesi?
8. Volatilite: günlük log getiri standart sapması mı, daha basit "aralık %" mi?
9. Cimri geçmişi arayüzde gösterilsin mi; gösterilirse yalnız yerelde mi? Kullanım koşulları riski nasıl kayda geçirilsin?
10. Plan Bölüm 9'daki SlowAPI satırı dış erişim aşamasına ertelensin mi?
11. API/Streamlit elle mi başlatılsın, oturum açılışında ayrı bir görevle mi?
12. DB'ye ulaşılamadığında Streamlit son önbelleği "son bilinen veri" etiketiyle göstersin mi?

## 7. Kaynaklar ve doğrulanamayan noktalar

**Projeden gerçekten erişilen:** yalnız https://github.com/Emir-Ars/Urun-indirim-takip (`main` dalı ana sayfası ve README). Sayfada commit SHA'sı görünmediğinden b4d1e98 ile aynı içerik olduğu doğrulanmadı.

**Erişilemeyen (izin/bot koruması):** commit ağacı sayfası, `raw.githubusercontent.com` üzerindeki migration dosyaları, `app/database/connection.py`, `tests/test_http.py`, `docs/teknik.md`, `proje_plani.md`, `.github/workflows/ci.yml`, GitHub Actions API (`/actions/runs`). Ek bir alt araştırma da aynı dosyalara ulaşamadı. Doğrulama yolu: yerel klonda `git show b4d1e9852fd0f3c122f7eefc114f406b2cdedbd5:<yol>` ve `gh run list --commit b4d1e98`.

**Bu nedenle doğrulanamayanlar:** `product_run_prices` gerçek sütun tanımı; `connection.py` ayarları; mevcut indeksler; `test_http.py` tarama kapsamı; teknik.md test tablosunun 1190 toplamıyla tutarlılığı (README yalnız "1190 test; 276'sı PostgreSQL" diyor); başlangıç commit'inin CI sonucu; Plan Aşama 6 satırındaki "aynı commit CI'da doğrulanır" ifadesinin gerçekleşip gerçekleşmediği.

**Dış kaynaklar (resmî öncelikli):** FastAPI Concurrency/async, Testing, Release Notes; PyPI fastapi, slowapi; Psycopg 3 Connection pools ve Concurrent operations (geliştirme sürümü 3.3.7.dev1 belgeleri — kararlı sürümle karşılaştırılmalı); PostgreSQL 17 Transaction Isolation ve SET TRANSACTION; PostgreSQL Predefined Roles ve CREATE ROLE; Streamlit st.cache_data, st.fragment, Caching overview, config.toml, Release notes; Vega-Lite Invalid Data ve Line; Uvicorn Settings ve Deployment. İkincil/topluluk kaynakları (yalnız destekleyici): FastAPI GitHub tartışması #15742 (httpx2 uyarısı), Streamlit issue #10155 (varsayılan bağlanma adresi), postgresqlco.nf (`default_transaction_read_only`).

**Kaynakla desteklenemeyen öneriler (açık soru olarak):** volatilite ve kapsam eşikleri; `statement_timeout` değeri; `st.line_chart`'ın `null` işleme biçimi; NSSM/servis seçenekleri; her paketin Python 3.13 tekerlek uyumluluğu (SlowAPI dışında).

## Sources

1. [GitHub - Emir-Ars/Urun-indirim-takip](https://github.com/Emir-Ars/Urun-indirim-takip)
2. [Testing - FastAPI](https://fastapi.tiangolo.com/tutorial/testing/)
3. [httpx deprecated for starlette TestClient · fastapi/fastapi · Discussion #15742](https://github.com/fastapi/fastapi/discussions/15742)
4. [Release notes - Streamlit Docs](https://docs.streamlit.io/develop/quick-reference/release-notes)
5. [Concurrency and async / await - FastAPI](https://fastapi.tiangolo.com/async/)
6. [Concurrent operations - psycopg 3.3.7.dev1 documentation](https://www.psycopg.org/psycopg3/docs/advanced/async.html)
7. [psycopg\_pool](https://dokk.org/documentation/psycopg/3.1.16/api/pool/)
8. [Connection pools - psycopg 3.3.7.dev1 documentation](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
9. [PostgreSQL: Documentation: 17: 13.2. Transaction Isolation](https://www.postgresql.org/docs/17/transaction-iso.html)
10. [SET TRANSACTION - PostgreSQL: Documentation: 18](https://www.postgresql.org/docs/current/sql-set-transaction.html)
11. [PostgreSQL Documentation: default\_transaction\_read\_only parameter](https://postgresqlco.nf/doc/en/param/default_transaction_read_only/)
12. [Release Notes - FastAPI - Tiangolo.com](https://fastapi.tiangolo.com/release-notes/)
13. [fastapi · PyPI](https://pypi.org/project/fastapi/)
14. [Caching overview - Streamlit Docs](https://docs.streamlit.io/develop/concepts/architecture/caching)
15. [slowapi · PyPI](https://pypi.org/project/slowapi/)
16. [Modes for Handling Invalid Data](https://vega.github.io/vega-lite/docs/invalid-data.html)
17. [Line](https://vega.github.io/vega-lite/docs/line.html)
18. [What Is Streamlit Caching? st.cache\_data vs st.cache\_resource](https://docs.kanaries.net/topics/Streamlit/streamlit-caching)
19. [st.cache\_data - Streamlit Docs](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data)
20. [Question about st.cache\_data TTL and Memory Cleanup - Using Streamlit - Streamlit](https://discuss.streamlit.io/t/question-about-st-cache-data-ttl-and-memory-cleanup/122070)
21. [Uvicorn Connection Refused Error: Fix It in 3 Commands](https://markaicode.com/errors/uvicorn-connection-refused-error-fix/)
22. [FastAPI Uvicorn - Interview Questions and Answers - ParikshaPatr](https://parikshapatr.com/interviews/backend-web-development-interview/fastapi-interview/fastapi-uvicorn-interview-questions-and-answers)
23. [Fix: Uvicorn Not Working — Worker Errors, Reload Issues, and Production Deployment - FixDevs](https://fixdevs.com/blog/uvicorn-not-working/)
24. [uvicorn/docs/settings.md at main · Kludex/uvicorn](https://github.com/Kludex/uvicorn/blob/main/docs/settings.md)
25. [Settings - Uvicorn](https://uvicorn.dev/settings/)
26. [Index - Uvicorn](https://uvicorn.dev/deployment/)
27. [config.toml - Streamlit Docs](https://docs.streamlit.io/develop/api-reference/configuration/config.toml)
28. [streamlit should by default only bind to localhost \[SECURE BY DEFAULT ❤️\] · Issue #10155 · streamlit/streamlit](https://github.com/streamlit/streamlit/issues/10155)
29. [slowapi · Python Simple Repository Browser](https://simple-repository.app.cern.ch/project/slowapi)
30. [slowapi 0.1.9 on PyPI - Libraries.io - security & maintenance data for open source software](https://libraries.io/pypi/slowapi)
