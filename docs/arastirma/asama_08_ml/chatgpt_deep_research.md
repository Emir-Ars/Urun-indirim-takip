# 1) Mevcut Sistem Değerlendirmesi ve Önerilen İlk Yaklaşım  
Mevcut sistemde 60 ürün için günlük iki turda (10:00, 22:00) fiyat/stok verisi toplanmakta, en düşük uygun teklif saklanmaktadır. Etiketler 7 günlük *en düşük fiyat %5’in altına inme* olayı şeklinde tanımlıdır. Veri sayısı az (toplam ~17.668 pencere, %10 olumlu) ve birçok üründe etiket çok az. Başlangıç için öneri, tüm ürünleri kapsayan tek bir **global model** kurmaktır. Her ürünün geçmiş özellikleri ayrı hesaplanıp (“ürün kimliği” özellik olarak eklenebilir) ortak veri seti oluşturulur. Böylece tüm ürünlerin verisini kullanan bir model (ör. LightGBM veya CatBoost) eğiterek ortak desenler öğrenilebilir. CatBoost’un sayısal ve kategorik değişkenleri direkt işleyebilmesi avantajdır. Varsayım: Farklı ürünlerin fiyat hareketlerinde ortak kalıplar vardır ve az verili ürünler için global model yardımı olasıdır. Deney: Global model ile her ürün için ayrı küçük modeller karşılaştırılarak (örn. doğrulama veri seti performansı) en iyi yaklaşım seçilir.  

# 2) Ortak/Ürün/Grup Model Karşılaştırması  
| Yaklaşım               | Avantajlar                                                          | Dezavantajlar                                                            |
|:-----------------------|:--------------------------------------------------------------------|:------------------------------------------------------------------------|
| **Tek Ortak Model**    | Tüm verilerden öğrenir (daha fazla veri ile genelleme). **CatBoost** kategorik (ürün ID, marka) girdi destekler. Yeni ürünler için genel bilgiler kullanılabilir. | Çok farklı ürün dinamiklerini tek bir modelde öğrenmek zor. Bazı ürünlerin hatası artabilir. Aykırı ürünler zayıf modellenebilir. |
| **Ürün Başı Model**    | Her ürünün özgün dinamiklerini yakalar, ürünler karışmaz.           | Küçük veri setlerinde aşırı uyum riski (overfitting). Birçok ürün için yeterli örnek yok. Veri bölünmesi ve takvim uyumsuzluğu. |
| **Marka/Grup Model**   | Ürünler marka/seriye göre gruplanarak ortak ve özgün desenler yakalanabilir. Ara model çözüm. | Grup tanımı ve karmaşıklığı artar. Karmaşık implementasyon. Performans artışı tartışmalı olabilir. |

Tablodaki her öneri mevcut verilerle doğrudan kurulabilir. Örneğin ortak modelde “ürün kimliği” veya marka kategorik özelliği eklemek ve genel veriyi kullanmak mümkündür. Varsayımlar ve etkilerini bu üç yaklaşımı doğrulama setinde karşılaştırarak test edebiliriz.  

# 3) Veri Seti Örnek Tanımı ve Etiket Kuralları  
Her örnek bir **ürün-kaynak-tahmin zamanı** (örn. 22:00 ture göre) ilişkilidir. Satır şu sütunları içerir: ÜrünID, Kaynak (ör. “kendi” ya da “Cimri”), Gözlem tarihi/saati, başlangıç fiyatı (22:00’deki en düşük uygun TRY cinsinden), stok durumu, son tarifeli hatalar vs. Etiket = 1, eğer takip edilen gelecek 7 günün herhangi birinde (hem 10:00 hem 22:00 turları değerlendirilerek) en düşük fiyat, başlangıç fiyatının %95’inin altına düşerse; aksi halde 0. Ancak hesaplama için aşağıdaki kontroller uygulanır:  
- **Geçmiş Kontrolü:** En az 30 günlük geçerli geçmiş verisi olmalı (yetersizse satır atılır).  
- **Eksik Geçmiş:** Eğer geçmişte kopukluk, ağ hatası ya da stok durumu varsa bunlar özellik olarak eklenir; eksik veri varsa satır yine de alınır ama açıklanmalı (ör. “sonraki veri gecikti”).  
- **Gelecek Eksikliği:** Eğer hedef pencere (gelecek 7 gün) için yeterince fiyat gözlemi yoksa (örneğin yeni ürün keşfedildiği için veri tamamlanmadıysa), bu örnek etiketlemeden **dışlanmalı**; yanlışlıkla “indirimsiz” diye etiketlenmemeli. Bu, seçilim yanlılığını önler.  
- **Cimri ve Kendi Veri:** Her iki kaynaktaki aynı gün/ürün çifti çakışıyorsa, çifte sayımı önlemek için örnekler birleştirilir veya bir kaynak tercih edilir. Örneğin, kendi ölçümümüz mevcutsa onu kullanabiliriz. Kaynak sütunu modele eklenerek farklar öğrenebilir.  
- **Diğer Hususlar:** Eski fiyat, bülten fiyatı vb. kullanılmaz. Kupon/indirim türleri dahil edilmez.   

Bu kurallara göre satırlar oluşturulur ve etiketlenir. Her önemli öneride (ör. eksik veri dışlama) hangi verilerle yapıldığı ve hangi varsayıma dayanıldığı açıkça belirtilmeli. Örneğin “Gelecekte veri eksikse etiket null yapılır; varsayılan etkinin yanlış pozitif önleme olduğu deneyle kanıtlanabilir.”  

# 4) Fiyat Özellik İşleme  
Fiyatı doğrudan ham TRY kuruş değeri olarak kullanabiliriz, ancak daha iyi sonuçlar için çeşitli dönüşümler eklenir:  
- **Log Fiyat:** Enflasyon ya da büyük fiyat farklarında oransal değişimleri vurgulamak için doğal logaritma veya log10 (örn. 𝑙𝑜𝑔(TRY)) alınabilir. Log kullanımı, oran hesaplamalarında aritmetiği kolaylaştırır.  
- **Yüzde Değişimler:** Dünü ve bir önceki haftayı referans alarak günlük/haftalık **fiyat değişim yüzdeleri** (ör. (Bugün-Fırsat_Günü_öncesi)/Fırsat_Günü_öncesi) hesaplanabilir. Bu, göreceli düşüşleri modele aktarır.  
- **Göreceli Ölçek:** Güncel fiyatın geçmiş ortalama/minimum/maksimuma oranları verilebilir (örn. bugünkü fiyat / son 30 gün ortalaması). Bu, farklı fiyat düzeyindeki ürünlerin normalizasyonuna yardımcı olur.  
- **Oynaklık (Volatilite):** Son 30 günde fiyat dalgalanmalarını ölçmek için standart sapma veya ortalama mutlak değişim (ör. günlük yüzde değişimlerin std. sapması) hesaplanabilir. Yüksek oynaklık, indirim olasılığını etkileyebilir.  
- **Fiyat Değişim Frekansı:** Son düşüşten geçen gün sayısı, son düşüş büyüklüğü ve kaç günde bir fiyat değiştiği (fiyat günleri) gibi özellikler eklenebilir. Örneğin “önceki düşüş 10 gün önce” gibi.  
- **Kıyaslama Fiyat:** Aynı kapasite/model ürünlerin fiyat seviyesi farklı olabilir; bu durumda örneğin kapasiteye göre normalize etme (ör. GB başına TRY) veya benzer ürünlerin fiyatlarıyla karşılaştırma özellikleri düşünülebilir.  
- **Tarihsel Fiyat Boşlukları:** Gerçek sabit fiyat (hiç değişmeyen) ile veri eksikliği farklıdır. Boş değer yerlerini ileri-doldurma (forward-fill) yapmak nerede mantıklı, nerede yanıltıcı açıklanmalı. Gelecek oluşturulurken gözlenmemiş fiyat hiçbir zaman gerçekmiş gibi etiketlemeye alınmamalıdır.  

Bu özellikler, yalnızca tahmin anında bilinen geçmiş veriler kullanılarak hesaplanır. İleri-doldurma sadece küçük boşluklar için ve bir “istatistiksel sabit fiyat” işareti (ör. çok uzun değişimsizlik) olarak değerlendirilebilir.  

# 5) Kullanılacak Girdiler (Özellikler)  
İlk sürüm için sınırlı ama anlamlı özellikler önerilir:  
- **Ürün Bilgileri:** Ürün kimliği, marka, model, depolama kapasiteleri. Bu kategorik özellikler modelde kullanılabilir. (Örneğin CatBoost, ürün ve marka bilgisini doğrudan kategorik olarak işleyebilir.) Renk, RAM veya garanti türü şu anda ürün kimliğini ayırmıyor, ancak eklenecekse ayrı özellik yapılmalı. Ürün kimliği içeren modelde veri sızıntısını önlemek için target encoding (etiket ortalaması) vb. uygulanacaksa sadece eğitim seti içinde, çapraz doğrulama kullanılarak yapılmalı. Yeni kategori (yeni ürün) geldiğinde ‘diğer’ sınıfı veya basit rastgele değerle işlenebilir.  
- **Geçmiş Fiyat Hareketleri:** Yukarıda saydığımız güncel fiyat dönüşümleri (ham, log, yüzde değişimler) ve oynaklık özellikleri. Son 7, 14, 30 günün minimum, maksimum, ortalama fiyatı gibi zaman aralıkları da özellik olabilir. Tarihsel veri kalitesi (örneğin belirli bir dönemde kaç gün fiyat ölçümü eksik kaldı) ayrı bir özellik olarak eklenebilir.  
- **Takvim Bilgisi:** Hafta içi/haftasonu veya ayın günü gibi takvimsel veriler fayda sağlayabilir (örn. Cuma fiyat eğilimleri farklı olabilir). Türkiye’de kampanya dönemlerini (Black Friday vb.) dış veri olmadan doğrudan alamıyoruz. Ancak yıl-başı gibi genel mevsimsellik etkisi olabilir.  
- **Geçmiş Veri Kalitesi ve Yaşı:** Son veri toplama ile tahmin zamanı arasındaki saat/dakika farkı, bir sonraki beklenen toplama turunda veri geç geldiyse veya hiç gelmediyse bir işaretçi. Sürekli istikrarlı takip edilmeyen ürünler için ayrı bayrak koyulabilir.  
- **Stok/Pazaryeri/Kapsam:** Kendi verimizdeki stok bilgisi (ör. şu anda stokta mı), pazaryeri (Trendyol/Hepsiburada) ve takip kapsamındaki sayfa sayısı (kaç kaynak satıcı takip ediliyor) gibi bilgiler kullanılabilir. Örneğin takip edilen sayfa sayısının artması rekabeti etkiler.  

Döviz kuru (TRY dışı para birimleri) ve enflasyon gibi ek veriler, dışsal veriyi gerektirir. İlk etapta mevcut verilerle başlayıp, ihtiyaç halinde ek veri kaynakları (CPI endeksi, kampanya takvimi, ürün çıkış tarihi) ikinci adımda değerlendirilmelidir.  

# 6) Model Karşılaştırma Planı  
Model karşılaştırması için sınırlı bir deney planı oluşturulur. Ortam kontrolü için tüm modeller aynı **özellik seti, eğitim/val/test bölünmesi** ile test edilir. Plan şöyle olabilir:  
- **Basit Olasılık Referansı:** Eğitim verisindeki ortalama olay oranı (yaklaşık %10) alsın. Bu, “constant predictor” görevi görür.  
- **Lojistik Regresyon:** Temel olasılık modelidir. Özelliklerden doğrusal kombinasyon öğrenir ve sonuçları olasılık olarak verir. Interpretasyonu kolaydır.  
- **LightGBM:** Hızlı, hafif ve yüksek performanslı bir gradient boosting yöntemidir. Cevap olarak hızlı öğrenme ve iyi doğruluk sunar. Eksik değerlere toleranslıdır.  
- **CatBoost:** Kategorik değişken desteğiyle güçlü bir boosting kütüphanesidir. Karmaşık etkileşimleri yakalar, kampüs problemi azdır.  
- **Diğer:** Karmaşıklığı gerekçelendirmek koşuluyla ARIMA/Prophet gibi klasik zaman serisi modelleri veya basit derin öğrenme (LSTM) önerilmemiştir; bunlar doğrudan olasılık sunmaz veya çok fazla veri ister. (Varsa ek araştırma olarak belirtilebilir, ancak ilk sürümde kapsam dışı kalmalıdır.)  

Her model eğitim sırasında geçmişi kullanarak eğitilir, doğrulama setiyle ayar parametreleri seçilir ve test setinde (son %15’te) karşılaştırılır. Mümkünse birden fazla “ileri kaydırmalı” zaman bölünmesi kullanarak sonuçların kararlılığı sınanır. Bu plan doğrultusunda her modelin **precision/recall, Brier, log-loss, AP** gibi metriklerle performansı ölçülür.  

# 7) Cimri Verisinden Kendi Verimize Geçiş  
“Cimri” geçmiş verisi ayrı tabloda tutuluyor ve yoğunluğu farklı (günde ~1 kayıt, eksik stok/satıcı bilgisi). Kullanım şekilleri:  
- **Sadece Cimri Modeli:** İlk modelleme Cimri ile yapılabilir (özellikle başlangıç için örnek sayısı artsın diye). Ancak Cimri verisi tam kapsamı temsil etmeyebilir.  
- **Ortak Eğitim (Birleştirme):** Her kaynağı ayrı özellikle (kaynak sütunu) tutarak hem Cimri hem kendi verilerinden oluşan tek eğitim seti oluşturulabilir. Model kaynak farkını öğrenir. Ancak fiyat dağılımları ve etiket tanımları uyumsuzsa sorun olur. Aynı ürün/tarih içeren kopyalar çifte sayımdan kaçınılarak tekleştirilmelidir.  
- **Ayrı Modeller:** Cimri ve kendi verisi için ayrı modeller eğitmek (örneğin ağırlıklı katmanlı model) düşünülebilir. Daha sonra sonuçlar birleştirilebilir.  
- **Transfer Öğrenme:** Cimri verisinde model eğitildikten sonra bu bilgiyi kendi veri üzerinde ince ayar (fine-tune) yapmak da bir stratejidir. Örneğin Cimri’den elde edilen erken dönem fiyat trendlerini model başlatmak için kullanmak.  

Kaynaklar arasındaki farklı fiyat kapsamı ve örnek tanımları çakışıyorsa dikkatli olmak gerekir. İki kaynağı olduğu gibi uç uca eklemek yerine, her kaynaktan aynı ölçü fonksiyonları/özellikler üretip kaynağı belirten bir etiket ekleyerek öğretmek genelde daha güvenlidir. Ancak “kaynak” sütunu, veri kaynağındaki farkı tek başına çözmeyebilir (çünkü hatalı ölçümler veya eksiklikler kaynakla örtüşebilir). Bu geçiş planı, deneyle test edilerek gelişmelidir. Örneğin ilk olarak sadece Cimri ile test modeli kurup sonuç karşılaştırılmalı, sonra kendi veride yeniden deneyerek farklar analiz edilmelidir.  

# 8) Değişen Katalog ve Takip Kapsamı  
Yeni ürün sayfaları keşfedildikçe mevcut fiyat takibi dışına girmiş olabilir. Eğer bir ürün için takip edilen sayfa seti değiştiyse ortaya çıkan fiyat düşüşü *gerçek bir indirim* olmayabilir. Örneğin yeni, daha ucuz bir satıcı eklendiyse bu bir indirim değil ekleme etkisidir. Bu durumu ele almak için:  
- **Yeni Sayfa Bayrağı:** 7 günlük hedef penceresi içinde yeni sayfa eklenip eklenmediğine dair bir özellik eklenebilir. Eğer varsa, bu örnek etiketlemeden önce incelenebilir veya dışlanabilir.  
- **Kapsam Sabitliği Şartı:** Mevcut “sabit kapsam” kuralı çok kısıtlayıcıysa (örneğin sürekli yeni ürün ekleniyorsa yeterli örnek çıkmıyorsa), bunu genişletmek gerekebilir. Örneğin yalnızca bir süre sabit sayfalarla örnek oluşturmak yerine, belirli sayıda keşif izni verilebilir. Fakat bu bir politika değişikliği olup açıkça raporda belirtilmeli.  
- **Politika Önerisi:** En iyisi, “hedef pencere içinde kesinlikle sabit takip edilen sayfa gereksinimi” esnetilerek, yeni sayfa etkisi ayrı işaretlenmelidir. Böylece örnek üretimi artar ve model, yeni sayfa girişi ile indirim arasındaki farkı öğrenebilir.  
- **Gelecekteki Özellikler:** Halen kullanılamayan ama kullanılabilir özellikler (örneğin yeni sayfa öncesi kategori/tenote) bu raporda yüzeysel kalmalıdır; entegre etmeden önce ilk deneylerde mevcut verilerle sınanmalı.  

Bu konuda yapılacak deney, yeni sayfa etkilerinden arındırılmış bir alt kümede modeli eğitip karşılaştırmak olabilir. Örneğin, yalnızca sabit sayfa setli örneklerle eğitilen bir model ile tüm veri kullanan modelin performans farkı ölçülerek politika değişikliği doğrulanabilir.  

# 9) Model Eğitim ve Test Şeması  
Zaman serisi yapıyı koruyarak geçmişten geleceğe bölümleme yapılmalıdır. Örnek bir şema:  
- **Zaman Temelli Bölünme:** Tüm ürünler için kronolojik olarak eğitim/%70, doğrulama/%15, test/%15 şeklinde sabit tarihler belirlenir. Örneğin verinin %70’i kadar süre eğitim, sonraki %15 doğrulama, kalan %15 test olarak ayrılabilir. Bölmeler arasında 7 günlük (hedef pencere) boşluk bırakılmalı ki ilerideki bilgisi sızmasın. Yani test başlangıç tarihinden 7 gün geriye kadar eğitimde hiçbir örnek bulunmamalı.  
- **Yürüyen Pencere Değerlendirmesi:** Sabit bir tek bölümlendirme yerine, farklı başlangıç tarihli birden çok değerlendirme dönemi (walk-forward validation) kullanılabilir. Her döngüde eskiden belirlenen tarihler bir sonraki periyotla ilerletilir; bu sayede modelin zaman içindeki kararlılığı görülür.  
- **Örtüşen Örnekler:** 7 günlük hedef pencereler tipik olarak komşu günlerde birbirine kısmen overlap eder. Bu durum örnek bağımsızlığını bozar. Buna rağmen çoğu pratik yaklaşım ardışık günleri örnek olarak alır. Sonuçlardaki belirsizliği değerlendirirken bu bağımlılık göz önünde bulundurulmalı (örneğin ürün düzeyinde ya da zaman bloklarında bootstrap ile belirsizlik tahmini yapılabilir).  
- **Özellik/Model Öğrenme:** Özellik seçimi, dönüşümler ve model hiperparametre ayarları yalnızca eğitim/validasyon verisinde yapılmalı, test seti dokunulmamalıdır. Örneğin kaldıralacak veya impute edilecek değişkenler, encode işlemleri hep eğitimde öğrenilip, val/test setine aynı işlemler uygulanmalıdır. İleri sızıntıyı önlemek için veriye dayalı (target encoding gibi) işlemler validasyon katlarında yapılmalıdır.  
- **Son Test Korunması:** Tüm model seçimi ve ayarları yapıldıktan sonra, son test bölümü **kesinlikle** (adi model seçimi ya da kalibrasyon aşamasında) kullanılmamalıdır. Son test sadece nihai performansı raporlar.  

Örneğin eğer model 1 Kasım 2026’da eğitildiyse, 2 Kasım 2026’dan itibaren 7 gün sonuçlarına bakılmadan test değerlendirmesi yapılmalı. Başlangıç verilerinin tahmin anı 22:00 olduğu için, 2 Kasım sabah 10:00 verisi zaten test etkileyecektir. Bu tarz zaman farkları şemada net belirtilmelidir.  

# 10) Başarı ve Güvenilirlik Ölçütleri  
Tahmin edilen olasılık ve indirim olaylarını ayırt etme bakımından uygun metrikler seçilmelidir:  
- **Kesinlik/Duyarlılık ve AP:** Pozitif (indirim) sınıf nadir olduğundan ROC eğrisinden çok **Precision-Recall (PR)** eğrisi ve **Average Precision (AP)** kullanılmalıdır. AP, Farklı eşiklerde elde edilen precision değerlerinin recall artışına göre ağırlıklı ortalamasıdır. İyi AP, modelin pozitifleri yüksek olasılıkla bulma kabiliyetini gösterir. Precision = TP/(TP+FP), Recall = TP/(TP+FN) tanımlarıyla ölçülür. Bu metrikler dengesiz veri için uygundur.  
- **Brier Skoru ve Log Loss:** Modelin olasılık çıktılarının bütüncül doğruluğunu ölçmek için *Brier skoru* ve *log-loss (lojistik kayıp)* kullanılmalıdır. Brier skoru, tahmin edilen olasılık ile gerçek etiketi arasındaki ortalama kare hata olarak tanımlanır. Log-loss, çapraz-entropi şeklinde olup, lojistik regresyon gibi modellerde temel kayıp fonksiyonudur. Her ikisi de düşük olması istenir. Brier skoru düzgünlük (kalibrasyon) ve ayırt edicilik birleşimine duyarlıdır. Unutulmamalıdır ki düşük Brier skoru *sadece* iyi kalibrasyon anlamına gelmeyebilir; aynı zamanda modelin yüksek çözünürlüğü (ayırma gücü) de etkiler.  
- **Kalibrasyon Eğrileri:** Tahmin edilen olasılıkların gerçekte ne kadar tutarlı olduğunu görmek için kalibrasyon eğrileri (güvenilirlik diyagramı) kullanılmalıdır. Örneğin tahmin olasılığı 0.8 olan örneklerin yaklaşık %80’inin indirim yaşayıp yaşamadığına bakılır. Gerekirse model kalibrasyonu (Platt, isotonic vb.) düşünebiliriz.  
- **Alt Gruplar:** Ana metriklere ek olarak ürün/marka/kapasite bazında sonuç raporlanmalıdır. Her ürünün eşit önemde olduğu bir değerlendirme de (ör. ürün bazlı ortalama doğruluk) sağlanabilir. Olumlu örnek içermeyen gruplar (örneğin hiç indirim olmayan bir ürün) için precision/recall tanımsız olabilir; bu durumda o grupta raporlanacak metrik sınırlı olmalıdır (örneğin yalnız accuracy).  
- **Sınıf Dengesizliği:** Yaklaşık %10’luk pozitif oran nedeniyle sınıf dengesizliğine dikkat edilmelidir. Eğitim sırasında ağırlık ayarı veya örnekleme yapılabilir, ancak ölçü olarak dengesiz veri için AP ve PR eğrileri ön planda olmalıdır.  

Toplam sonuç yanı sıra alt gruplar arası tutarlılık (bias) ve örnekler arası bağımlılığın neden olduğu belirsizlikler (bootstrap ile güven aralıkları) göz önünde bulundurulmalıdır.  

# 11) Veri Yeterliliği, Tahmin Gösterilmeme ve Yayınlama  
Her ürün için geçmiş miktarı, olumlu olay sayısı ve toplam örnek adedi kontrol edilmelidir. Örneğin, bir ürünün <30 günlük geçmişi veya 5’ten az indirim olayı varsa, model bu ürüne güvenilir bir tahmin üretmeyebilir; böyle durumlarda “tahmin gösterme” kararı verilebilir. Ayrıca model henüz doğrulanmamışsa (ilk eğitim başarı düzeyini yakalamadıysa) sonuçlar yayınlanmamalıdır. Veri dağılımındaki değişimleri izleyecek bir **monitoring** sistemi kurulmalıdır: her gün toplanan verilerle etiket oranları ve özellik dağılımları takip edilerek anormal değişiklikler (drift) algılanabilir.  

**Yeniden Eğitim:** Belirli aralıklarla (ör. haftalık veya aylık) modeli yeniden eğitmek önerilir. Her yeniden eğitimde hem özellik hesaplama yöntemleri (aynı geçmiş dönemi, ölçüm aralığı) hem de model parametreleri sabit kalmalıdır.  

**Araç Sunumu:** Kullanıcıya gösterilecek olasılık her gece 22:00 turu verisi üzerinden hesaplanır. Ertesi sabah 10:00 turunda fiyat değiştiyse, bu modeli yeniden eğitmeden değişen bir şey olduğuna işaret eder. Kullanıcı arayüzünde bu durum şu şekilde açıklanabilir: *“Bu olasılık 26 Ekim 22:00 fiyatına göre hesaplanmıştır. 27 Ekim 10:00 fiyatı geldiğinde olasılık değişmiş olabilir.”* API/arayüz yapısı mevcut olduğundan, her gün eğitim tamamlanır tamamlanmaz tahminler hesaplanıp veritabanına yazılabilir; UI bunu olduğu gibi çekip gösterir. Eğitim başlatmak için arayüz açılmasını beklemeye gerek yoktur.  

# 12) Öncelikli ve Sonraya Bırakılacak Geliştirmeler  
- **Öncelikli İşler:** Ortak model kurulumu ve eğitim otomasyonu; eğitim/val/test bölünme şeması; temel özellik seti ile ilk modellerin çalıştırılması; performans değerlendirme. İzleme altyapısı (veri dağılımı, hedef oranları) kurulmalı.  
- **Sonraya Bırakılacaklar:** Yeni veri kaynaklarının (enflasyon, kampanyalar) entegrasyonu; daha karmaşık modeller (ör. derin öğrenme) ancak yeterli veri toplandıktan sonra; yeni sayfa etkilerinin modelde kullanımı (bu veri yavaş yavaş birikebilir). Hiperparametre optimizasyonu ve otomatik model seçme (AutoML) ileri aşama için düşünülebilir.  

Gerekli ek veri ve ölçümler arasında gelecekteki olay oranlarının güncel takip edilmesi, sayfa keşiflerinin kaydı, test sonuçlarının şeffaf takibi sayılabilir.  

# Kaynakça  
- Scikit-Learn Kütüphanesi Dokümantasyonu – *Probability calibration*: “Strictly proper scoring rules like Brier and log loss assess calibration and resolution… Calibration curves (reliability diagrams) compare predicted probability with actual frequency.”  
- Wikipedia – *Brier skoru*: Brier skoru, olasılık tahminlerinin üç bileşenli bir ayrışımıyla (uncertainty, reliability, resolution) ifade edilir. Düşük Brier skoru, hem daha iyi kalibrasyon hem de daha yüksek çözünürlük anlamına gelebilir.  
- Scikit-Learn Kütüphanesi – *average_precision_score*: “AP summarizes a precision-recall curve as the weighted mean of precisions at each threshold.”  
- Wikipedia – *Precision and Recall*: Binary sınıflandırmada Precision = TP/(TP+FP), Recall = TP/(TP+FN) olarak tanımlanır.  
- LightGBM Resmi Dokümantasyonu: LightGBM, ağaç temelli Gradient Boosting yöntemidir; **hızlı eğitim, yüksek verimlilik, daha iyi doğruluk** gibi avantajları vardır.  
- Wikipedia – *Logistic Regression*: “Logistic regression is a supervised machine learning algorithm widely used for binary classification… transforms input features via logistic (sigmoid) function to output probability between 0 and 1”.  
- CatBoost GitHub – *README*: CatBoost, karar ağaçları üzerinde çalışan bir gradient boosting kütüphanesidir; kategorik değişken desteği ve üstün model kalitesi sunar.  
- Scikit-Learn Kütüphanesi – *log_loss*: Log loss (lojistik kayıp), “cross-entropy loss”, lojistik regresyonda olasılık tahminlerinin negatif log-yapısıdır.  

