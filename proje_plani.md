`# 📱 E-Ticaret Akıllı Telefon İndirim Tahmin Sistemi (MVP) - Nihai Mimari Planı`

`**Doküman Tipi:** Ürün Gereksinim Dokümanı (PRD) & Teknik Mimari Raporu`

&nbsp;

`## 🎯 1. Proje Kapsamı ve Kurallar (Guardrails)`

`*   **Platformlar:** Sadece Trendyol ve Hepsiburada.`

`*   **Kategori & Hacim:** Sadece "Akıllı Telefonlar". Başlangıç için en popüler 20-30 model (Örn: iPhone 13, 14, 15, Samsung S24) eklenecektir.`

`*   **Varyant Yönetimi:** Farklı hafıza kapasiteleri (Örn: iPhone 15 128GB vs 256GB) sistemde **tamamen bağımsız, ayrı ürünler** olarak tanımlanacaktır. Renk seçenekleri dikkate alınmayacak, ilgili kapasitedeki en ucuz renk baz alınacaktır.`

`*   **Satıcı Karmaşası (Buybox) Çözümü:** Üründeki tüm satıcılar taranmayacaktır. Sadece o ürün sayfasındaki **"En Düşük Fiyat"** (Buybox fiyatı) ve o satıcının bilgileri baz alınacaktır.`

``*   **Mimari Yaklaşım:** Modüler yapı (`scraper`, `database`, `ml_model`, `api`).``

&nbsp;

`## 💾 2. Veri Mimarisi & Çalışma Mantığı (Backend & Scraping)`

``*   **Veritabanı:** SQLite (`price_history` tablosu).``

`*   **Ana Tablo Şeması:**`

&nbsp;&nbsp;&nbsp;&nbsp;``*   `id` (Primary Key)``

&nbsp;&nbsp;&nbsp;&nbsp;``*   `platform` (Trendyol / Hepsiburada)``

&nbsp;&nbsp;&nbsp;&nbsp;``*   `product_id` (Her telefon modeline ait benzersiz sayısal kimlik - Örn: iPhone 15 için 1, S24 için 2)``

&nbsp;&nbsp;&nbsp;&nbsp;``*   `product_name` (Örn: Apple iPhone 15 128GB)``

&nbsp;&nbsp;&nbsp;&nbsp;`` *   `product_url` ``

&nbsp;&nbsp;&nbsp;&nbsp;``*   `current_price` (O anki en düşük satış fiyatı)``

&nbsp;&nbsp;&nbsp;&nbsp;``*   `original_price` (Üstü çizili fiyat)``

&nbsp;&nbsp;&nbsp;&nbsp;``*   `seller_name` (Örn: Telefoncunuz, Hepsiburada)``

&nbsp;&nbsp;&nbsp;&nbsp;``*   `seller_rating` (Satıcı Puanı, Örn: 9.6)``

&nbsp;&nbsp;&nbsp;&nbsp;``*   `stock_status` ("Stokta Var", "Kritik Stok", "Tükendi")``

&nbsp;&nbsp;&nbsp;&nbsp;`` *   `timestamp` ``

`*   **Periyodik Veri Toplama (Batch Processing):** Kullanıcı arama yaptığında **anlık scraping yapılmayacaktır**. Sistem anti-ban (IP ban) yemek ve yüksek hız (latency < 0.1s) sağlamak için, arka planda periyodik olarak (Örn: her sabah 03:00 / 06:00'da) çalışıp verileri veritabanına kaydedecektir. Kullanıcı sisteme girdiğinde veriyi doğrudan SQLite veritabanından okuyacaktır.`

`*   **Soğuk Başlangıç & Piyasa Korelasyonu:** ML modelini eğitebilmek için Akakçe/Cimri geçmiş grafik API'lerinden tersine mühendislikle veri çekilecektir. Amazon/N11 gibi diğer sitelerin varlığı, modelin genel piyasa reflekslerini öğrenmesi için avantaj olarak kullanılacaktır.`

&nbsp;

`## 🧠 3. Makine Öğrenmesi (MLOps) & Veri Birleştirme Stratejisi`

``*   **Model Mimarisi:** Her ürün için ayrı bir model dosyası (`.pkl`) **oluşturulmayacaktır**. Sistemde tüm telefonlar için ortak çalışacak **TEK BİR genelleştirilmiş model** (LightGBM sınıflandırma modeli) bulunacaktır.``&nbsp;

``*   **Farklı Ürünlerin Birleştirilmesi (Normalizasyon):** iPhone ile Xiaomi gibi farklı fiyat karakteristiğine sahip ürünlerin tek modelde eğitilebilmesi için mutlak fiyatlar (TL) değil, **Göreceli Fiyat Oranı** (`Guncel_Fiyat / Son_30_Gun_Ortalamasi`) kullanılacaktır. Böylece tüm ürünler aynı matematiksel oran düzleminde birleştirilecektir.``

``*   **Ürün Kimliği (Context):** Modelin, her telefonun kendine özgü fiyat hareketini (örneğin iPhone'un daha yavaş, bazı modellerin ani değer kaybetmesini) kaçırmaması için eğitim matrisine `product_id` kategorik değişkeni eklenecektir.``

``*   **Feature Engineering (Öznitelik Çıkarımı):** `product_id`, `haftanin_gunu` (0-6 arası tam sayı), `ay` (1-12 arası tam sayı), `normalize_fiyat_orani`, `son_indirimden_gecen_gun_sayisi`.``

``*   **Çıktı & İş Mantığı:** "7 gün içinde indirime girme olasılığı" (% oran). Model indirim beklese dahi, `stock_status` verisi "Kritik Stok" ise indirim tahmini, FOMO (Fırsatı Kaçırma Korkusu) uyarısıyla çapraz analiz edilerek sunulacaktır.``

&nbsp;

`## 🚀 4. Backend ve Frontend`

`*   **Backend:** FastAPI ve Pydantic V2 (Strict Mode ile hatalı veri girişlerinin engellenmesi - Örn: Fiyat alanına "Tükendi" metni gelirse verinin reddedilmesi).`

`*   **Frontend (Arayüz):** Streamlit.`

`*   **Arayüz / Dashboard Özellikleri:**`

&nbsp;&nbsp;&nbsp;&nbsp;`*   **Arama Çubuğu (Selectbox):** Kullanıcı yazım hatalarını ("iphon 15" vb.) önlemek için serbest metin kutusu yerine, DB'deki telefonların listelendiği zorunlu açılır menü kullanılacaktır.`

&nbsp;&nbsp;&nbsp;&nbsp;`*   **Fırsat Panosu:**`&nbsp;

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`*   O anki En Ucuz Platform, Satıcı Adı ve Satıcı Puanı.`

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`*   🔥 *Son 30 Günün Dibi Rozeti* (Mevcut fiyat son 1 ayın en düşük seviyesindeyse).`

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`*   📉 *Tarihi Zirve Fiyatı* (Psikolojik çıpalama için).`

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`*   📊 *Fiyat Volatilitesi* (Fiyatın hareketlilik özeti).`

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`*   🚨 *Kritik Stok Uyarısı*.`

&nbsp;

`## 🛠️ 5. DevOps, Dağıtım ve Güvenlik`

``*   **Konteynerleştirme:** Docker ve `docker-compose.yml` (Scraper/DB, FastAPI, Streamlit tek tuşla ayağa kalkacak). Bulut sunucuda 7/24 çalışacak altyapı.``

`*   **Veri Kalıcılığı:** Docker Volumes ile SQLite DB'nin ve WAL dosyalarının silinmesi önlenecek.`

`*   **Zamanlanmış Görevler:** Arka planda periyodik bot çalıştırma mimarisi.`

``*   **Güvenlik & Stabilite:** SlowAPI ile IP tabanlı oran sınırlandırma (Rate Limiting). SQLite eşzamanlılık kilitlenmelerini önlemek için `busy_timeout=5000` ve Tek Yazıcı (Single-Writer) kuyruk modeli.``

`*   **Sürekli Entegrasyon (CI):** GitHub Actions ile otomatik kod testi (Black, Flake8).`

&nbsp;

&nbsp;