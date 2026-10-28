# Akıllı Telefon Fiyat Takibi için ML Araştırması: Veri Seti, Hedef, Model ve Değerlendirme Tasarımı

Bugün yapılabilecek doğru iş model seçmek değil. Önce hedefi gözlem kapsamına ve sansürlemeye (censoring) dayanıklı biçimde yeniden tanımlamak gerekiyor. Ardından Cimri verisinde, tarihe göre ileri yürüyen ve 7 günlük etiketleri temizleyen (purging) bir değerlendirmeyle üç basit referansı ve tek bir ortak (global) gradient boosting modelini karşılaştırmak gerekiyor. Kendi verimizde olasılık göstermek ise ayrı bir kanıt eşiğine bağlanmalı.

## TL;DR

- **Önerilen başlangıç:** Bütün ürünlerin satırlarını kullanan tek bir ortak sınıflandırıcı kurulmalı. Girdiler ölçeksiz olmalı: log fiyat oranları, geçmiş minimuma uzaklık, oynaklık ve kapsam göstergeleri. Ürün kimliği sayı olarak verilmemeli; kategori olarak ya da hiç verilmemeli. Bu model; sabit olasılık, basit kural ve lojistik regresyondan oluşan üç referansı, aynı ileri yürüyen değerlendirmede PR-AUC, Brier ve log loss ölçütlerinin hepsinde geçmeden seçilmemeli. LightGBM ve CatBoost yalnız aday. Montero-Manso & Hyndman (2021) ve M5 bulguları ortak modeli destekliyor, ama bu destek bizim projeye uyarlanmış bir çıkarım.
- **Hedef değişmeli:** "7 gün içinde ≥%5 düşüş" etiketi kalabilir, ancak üç düzeltme gerekiyor. (1) Etiketin uygun sayılması, sonuca değil yalnız gözlem desenine bağlanmalı. (2) Düşüş, referans anında var olan sayfa kümesi üzerinde ölçülmeli; böylece yeni ve ucuz sayfanın minimumu düşürmesi gerçek düşüş sayılmaz. (3) Eksik pencereler atılmak yerine discrete-time hazard (kesikli zamanlı risk) formülasyonuyla sansürlü gözlem olarak kullanılmalı. Sıkı 30+7 tam-pencere kuralı kendi verimizde sıfır pencere verdiği için yalnız bir duyarlılık analizi olarak kalmalı.
- **Cimri ile ilgili sınır:** Cimri'deki 17.668 pencere bağımsız örnek değil; örtüşme, aile ve kampanya bağımlılığı yüzünden etkili örnek sayısı çok daha düşük ve henüz ölçülmedi. Cimri'deki iyi bir sonuç, kendi 22:00 referansımızda ve sayfa kapsamımızda ileriye dönük doğrulanmadan kullanıcıya olasılık göstermeye yetmez. Ayrıca Cimri'nin Kullanım Koşulları madde 2.2, ziyaretçi erişimiyle alınan bilgiyi "mesleki ve ticari olmayan amaçlarla" sınırlıyor.\[1\] Son alımdan önce hukuki uygunluk, teknik uygunluktan ayrı olarak netleştirilmeli.

## Durum ayrımı: uygulanmış sistem ve öneri

- **Uygulanmış sistem (kullanıcı beyanı, doğrulamadım):** Toplama, kapsam denetimi, PostgreSQL şeması ve Cimri tablosu. Kod tabanına ve veritabanına erişimim yok. Bu rapordaki bütün veri sayıları kullanıcının 23 Ekim 2026 denetiminden alındı ve yeniden ölçülmedi.
- **Öneri:** Aşağıdaki hedef tanımları, özellikler, deney sırası ve işletim planı. Hiçbiri henüz uygulanmadı ve hiçbiri için performans vaadi verilmiyor.
- **Etiketleme:** Raporda [Doğrulanmış], [Çıkarım], [Varsayım], [Öneri] ve [Deneyle ölçülecek] etiketleri kullanılıyor. Kaynakların erişim ve araştırma tarihi 27 Ekim 2026.

## Key Findings

1. **[Doğrulanmış] Ortak (global) model, ürün başına (local) modellerden daha kısıtlayıcı değil.** Montero-Manso & Hyndman, *International Journal of Forecasting* 37(4), 1632–1653 (2021), bir zaman serisi kümesi için global ve local yöntemlerin aynı tahminleri üretebildiğini gösteriyor. Ayrıca "global linear models show an unreasonable effectiveness" tespitini yapıyorlar.\[2\] **[Çıkarım]** 60 ürün ve ürün başına birkaç yüz günlük seri, local model için çok kısa. Bu nedenle başlangıç ortak model olmalı.
2. **[Doğrulanmış] M5 yarışmasını LightGBM tabanlı havuzlanmış modeller kazandı. Ama bu bulgu zamana karşı sağlam çıkmadı.** M5 Accuracy sonuç makalesine (Makridakis vd., IJF, 2022) göre kazanan çözüm, mağaza (10), mağaza-kategori (30) ve mağaza-departman (70) bazında havuzlanmış LightGBM modellerinin eşit ağırlıklı ortalamasıydı.\[3\] İlk 50 yöntemin hepsi ML'di.\[4\] Ma & Fildes'in *IJF* 38(4), 1492–1499 (2022) yorumu ise bu global modellerin "inconsistent performance over the various test periods" gösterdiğini, alt düzeyde iyi sonuç verseler de toplulaştırılmış düzeyde "lacked robustness" olduğunu buldu. **[Çıkarım]** Bu bulgu bizim için iki şey söylüyor. "Grup bazlı havuzlama" seçeneği gerçek bir aday. Tek bir zaman bölmesiyle model seçmek ise yanıltıcı olur.
3. **[Çıkarım] Mevcut etiket kuralında gizli bir seçilim yanlılığı riski var.** "Eksik gelecekte düşüş görüldüyse 1" kuralı ile "0 için tam gözlem gerekir" kuralı birlikte uygulanırsa, eksik pencereler yalnız olumluysa veri setine girer. Bu da olumlu oranı yapay biçimde şişirir. Çözüm ya simetrik uygunluk kuralıdır ya da sansürü doğrudan modelleyen kesikli zamanlı hazard yaklaşımıdır.
4. **[Doğrulanmış] Örtüşen ileriye dönük etiketler standart çapraz doğrulamayı iyimser yapar.** López de Prado, *Advances in Financial Machine Learning* (Wiley, 2018) 7. bölümde, eğitim satırlarından etiket aralığı test aralığıyla çakışanların silinmesini (purging) ve test sonrasına tampon (embargo) konmasını öneriyor.\[5\] Aynı kitap, örtüşen etiketlerin "ortalama tekliğini" (average uniqueness) ölçmeyi öneriyor.\[6\] **[Çıkarım]** 7 günlük ufukta ardışık günlerin etiketleri 6 günü paylaşır.
5. **[Doğrulanmış] Yaklaşık %10 olumlu sınıfta PR eğrisi, ROC eğrisinden daha bilgilendirici.** Kaynak: Saito & Rehmsmeier, *PLoS ONE* 10(3): e0118432 (2015).\[7\]\[8\] Boosted ağaçlar ise olasılıkları 0 ve 1'den uzaklaştırarak sigmoid biçimli bir bozulma üretir.\[9\] Niculescu-Mizil & Caruana (ICML 2005) bunu gösteriyor ve Platt ya da isotonic kalibrasyonla düzeldiğini buluyor.\[10\]
6. **[Doğrulanmış] "Al ya da bekle" probleminin doğrudan bir öncülü var.** Etzioni vd., "To Buy or Not to Buy" (KDD 2003) çalışmasında Hamlet, 12.000'den fazla uçak bileti fiyat gözlemiyle eğitildi. Model, 341 simüle yolcuya "al" ya da "bekle" önerisi verdi ve toplam $198.074 tasarruf sağladı.\[11\]\[12\] Çalışmada yanlış "bekle" önerisinin maliyeti, MetaCost ile asimetrik olarak ele alındı.\[13\] **[Çıkarım]** Bizim değerlendirmede de "yanlış bekle"nin TL cinsinden maliyeti ayrı ölçülmeli.
7. **[Doğrulanmış] Hukuki risk ayrı bir konu.** Cimri Kullanım Koşulları madde 2.2'ye göre ziyaretçilerin eriştiği bilgiler "mesleki ve ticari olmayan amaçlarla kullanılabilir". Madde 4.12'ye göre ise Cimri'nin izni olmadan sitedeki bilgiyi "başka bir mecra ya da internet sitesinde kullanmak, çoğaltmak ve yayınlamak kesinlikle yasaktır".\[1\] Trendyol'un üyelik sözleşmesinde "otomatik program, robot, web crawler, örümcek, veri madenciliği (data mining) ve veri taraması (data crawling) gibi 'screen scraping'" yasağı bulunduğu bilgisi, R10.net Bilişim Hukuku forumunda 20.03.2023 tarihinde madde 3.9'dan yapılan bir alıntıya dayanıyor; bu ikincil bir kaynak ve canlı metni doğrulayamadım. Hepsiburada'nın robots.txt dosyası normal ürün sayfalarını (`-p-`, `-pm-`) engellemiyor.\[14\] Ancak robots.txt hukuki izin anlamına gelmez. Ben hukukçu değilim; bu konuda hukuki görüş alınmalı.

## Details

### 1. Ürünleri tek veri setinde toplamak

| Yaklaşım | Avantaj | Sınır | Bizim veriye uygunluk |
|---|---|---|---|
| Ürün başına ayrı model | Ürüne özgü davranış | 60 model gerekir; her biri birkaç yüz örtüşen satırla eğitilir; olumlu olay sayısı ürün başına çok az; yeni üründe çalışmaz | **Uygun değil** [Çıkarım] |
| Ortak model (bütün satırlar) | Ortak düşüş dinamiğini öğrenir; yeni ürüne genellenebilir | Fiyat düzeyi farklarını ölçeksiz girdilerle çözmek gerekir; ürün ezberleme riski var | **Başlangıç önerisi** |
| Marka/aile bazlı modeller | M5'te havuzlama düzeyi bir tasarım parametresiydi | Grup başına veri daha da azalır; Apple ve Samsung dışındaki gruplar çok küçük kalır | İkinci aşama deneyi |
| Ortak + ürüne özgü (partial pooling) | Az verili ürün ortalamaya çekilir (shrinkage) | Hiyerarşik Bayes modelleri bakım ve hesap maliyeti getirir | Ortak modele kategori ve hedef istatistiği eklemek, bunun pratik yaklaşığıdır [Çıkarım] |

**Farklı fiyat düzeyleri:** Ham fiyat yerine ölçeksiz girdiler kullanılmalı: log(p_t / p_{t-k}), p_t / min_30, p_t / medyan_30, log-getirilerin standart sapması. Hedef de zaten oransal (≥%5). Bu sayede 15.000 TL'lik ve 90.000 TL'lik telefonlar aynı uzayda yer alır. Ham log fiyat yalnız "pahalılık segmenti" bilgisi olarak ayrı bir girdi olabilir. [Öneri]

**128 GB ile 256 GB arasında bilgi paylaşımı:** Bu iki ürün ayrı satırlarda kalır. Paylaşım iki yoldan sağlanır. (a) Ortak `model_ailesi` kategorisi (ör. "iPhone 16"). (b) Aile düzeyi tarih özellikleri: aynı günde aynı ailedeki diğer kapasitelerin son 1 ve 7 gündeki fiyat değişimi. Bu özellikler yalnız t anına kadar olan veriyle hesaplanmalı. [Öneri]

**Kimlik temsili:** `marka`, `model_ailesi` ve `seri_segmenti` (Pro/Max/FE gibi) kategori olarak verilmeli. Kapasite hem kategori olarak hem de log2(GB) sayısı olarak denenebilir. LightGBM tam sayı kodlu kategorileri Fisher (1958) yöntemiyle ayırıyor. Belgeler küçük veri ve çok kategori durumunda aşırı öğrenmeye karşı `min_data_per_group` ve `cat_smooth` parametrelerini öneriyor.\[15\] LightGBM 4.7 belgelerine göre tahmin anında eğitimde görülmeyen kategoriler eksik değer gibi işleniyor.\[16\] [Doğrulanmış]

**product_id sayı olarak verilirse:** Model, rastgele atanmış kimliklerde "id < 37" gibi anlamsız sıralama bölmeleri yapar. Katalog yeniden numaralandığında davranış değişir. Yeni ürünün kimliği, eğitim aralığının dışına düşerek keyfi bir yaprağa gider. [Çıkarım] Kimlik ya hiç verilmemeli ya da kategori olarak verilip ayrıca ablasyonla test edilmeli.

**Az geçmişi olan veya yeni ürün:** [Öneri] Model sırayla aile, marka ve global bilgiye düşer. Eksik gecikmeli özellikler NaN olarak verilir; LightGBM eksik değerleri varsayılan olarak ele alıyor (`use_missing`).\[17\] Aynı zamanda `geçmiş_gün_sayısı` özelliği verilir. Kullanıcı arayüzünde ise bölüm 9'daki "tahmin gösterme" kuralı uygulanır.

**Ezber mi, ortak davranış mı?** [Deneyle ölçülecek] Üç ayrı ölçümle ayırt edilir:
(1) Ürün kimliği olan ve olmayan modellerin ileri yürüyen skor farkı.
(2) Model ailesini dışarıda bırakan değerlendirme (leave-family-out): bütün iPhone 16 varyantları eğitimden çıkarılıp yalnız testte kullanılır.
(3) Permütasyon önemi: `product_id` ya da `marka` en önemli özellik çıkarsa, model büyük olasılıkla ürünlerin taban olay oranını ezberliyor demektir.

**Aile ve kampanya bağımlılığı:** Bir Efsane Kasım günü onlarca ürünün aynı anda olumlu etiket üretmesine yol açar. Bu satırlar bağımsız sayılırsa güven aralığı yapay olarak daralır. Belirsizlik bu yüzden tarih blokları ve aile kümeleri üzerinden bootstrap ile hesaplanmalı (bölüm 8). [Çıkarım]

**Çürütme deneyleri:** Aile bazlı LightGBM ortak modeli geçerse, ya da kimliksiz model kimlikli modelle eşit çıkarsa, başlangıç önerisi güncellenir. Birinci sonuç "havuzla ama grupla" seçeneğine, ikinci sonuç daha sade modele işaret eder.

### 2. Tahmin problemi ve etiket

| Formülasyon | Kullanıcıya faydası | Sorun | Karar |
|---|---|---|---|
| 7 gün içinde ≥%5 düşüş (ikili) | "Beklemeye değer mi?" sorusuna doğrudan cevap verir | Eşikler keyfi; sansürle ilgili sorunlar var | **Ana hedef** (düzeltilmiş hâliyle) |
| Gelecek fiyat veya % değişim regresyonu | Beklenen fiyatı verir | Fiyatlar basamaklı ve sıfır yoğunluklu; ortalama hata karar için anlamsız | İkincil araştırma |
| Düşüşe kadar süre (survival) | "Ne zaman?" sorusunu cevaplar; sansürü doğal biçimde ele alır | Daha karmaşık; açıklaması zor | **Etiketin sansür-doğru eşi** olarak deneyde yer almalı |
| Kantil regresyon (7 gün içindeki minimumun dağılımı) | "%X olasılıkla en az Y TL düşer" türünden bilgi verir | Kalibrasyonu zor | Sonraki aşama |

**Kullanıcıya en yararlı çıktı [Öneri]:** "Önümüzdeki 7 günde bu sayfa kümesinde ≥%5 daha ucuz fiyat görülme olasılığı ≈ %P". Bu, olasılık ancak kalibre edilmiş ve bölüm 9'daki eşikler geçilmişse gösterilmeli. Aksi durumda yalnız açıklayıcı bilgi gösterilmeli: "Son 30 günün en düşüğüne %3 uzaklıkta" gibi.

**Kapsam tanımı:** Tahmin "bizim takip kapsamımızda gözlenecek düşüş" olarak tanımlanmalı. Pazaryerinin tamamındaki gerçek minimum gözlenmiyor. Bu ifade arayüzde açıkça yazılmalı. [Öneri]

**Kapsam değişikliği ve yeni sayfa [Öneri]:** İki etiket tanımlanmalı:
- `y_sabit`: Gelecek minimum, yalnız referans anında aktif olan sayfa kümesi S_t üzerinden alınır. Bu "gerçek fiyat düşüşü"ne en yakın tanımdır ve **birincil hedef** olmalı.
- `y_izlenen`: Gelecek minimum, o gün izlenen bütün sayfalar üzerinden alınır. Kullanıcının göreceği minimum budur.
İkisinin farkı "kapsam kaynaklı düşüş" oranını verir [Deneyle ölçülecek]. Böylece kapsam değişen pencereleri atmaya gerek kalmaz, eşleşmiş sayfa kümesi kullanılır.

**Eksik gelecek, stoksuzluk ve satıştan kalkma:**
- *Bilinen olumlu:* Gözlenen ilk k gün içinde düşüş görüldüyse etiket 1'dir. Kalan günlerin eksik olması bunu değiştirmez.
- *Bilinmeyen:* Düşüş görülmedi ve gözlenen gün sayısı yetersiz.
- **Sorun [Çıkarım]:** Olumluyu eksik pencerede kabul edip olumsuz için tam pencere istemek, eksik pencereleri sonuca göre seçmek demektir. Bu, olumlu oranını yukarı çeker ve olasılıkları bozar.
- **Çözüm A (simetrik uygunluk):** Uygunluk yalnız gözlem desenine göre belirlenir, ör. "7 günün ≥6'sı gözlendi". Bu kurala uyan pencerelerde etiket olağan biçimde atanır; uymayan pencereler sonuç ne olursa olsun dışarıda kalır.
- **Çözüm B (discrete-time hazard):** Her (ürün, referans günü, ufuk günü h=1..7) bir satırdır. Hedef "h. günde ilk kez düşüş"tür. Gözlemin bittiği gün sansür noktasıdır. 7 günlük olasılık P = 1 − Π(1 − h_k) formülüyle hesaplanır.\[18\] Suresh vd., *BMC Medical Research Methodology* 22 (2022), kişi-dönem (person-period) veri setinde lojistik regresyonun kesikli zamanlı survival modeli olarak kullanılabildiğini anlatıyor.\[19\] Bu yöntem eksik geleceği atmaz, sansürlü gözlem olarak kullanır.\[20\] [Doğrulanmış yöntem; uyarlaması Çıkarım]
- *Stoksuzluk:* Gelecekte "stokta yok" durumu fiyat gözlemi değildir. O gün o sayfa için eksik sayılır, fiyatı sıfır kabul edilmez. Bütün S_t kümesi stoksuzsa o gün gözlenmemiş sayılır.
- *Satıştan kalkma:* Ürün kalıcı olarak kalkarsa sansürlenir. Ayrıca bir "rekabet eden risk" (competing risk) olayı olarak not edilmeli. [Öneri]

**Sıkı tam-pencere yaklaşımı:** Avantajı etiketin temiz olması. Dezavantajı seçilim yanlılığı: tam veri genelde sakin dönemlerde oluşur, çünkü kampanya günlerinde sayfalar daha sık hata verir ve kapsam daha sık değişir [Varsayım]. Kendi verimizde sıfır pencere bırakması da pratikte yöntemi kullanılamaz kılıyor. Bu yüzden yalnız duyarlılık analizi olarak tutulmalı: A ve B çözümlerinin sonuçları, sıkı alt kümede de tutarlı mı?

**Eşikler (%5 ve 7 gün):** Bunlar bir proje tercihidir; literatürde evrensel bir değer yok. [Deneyle ölçülecek] Eşik ızgarası {%3, %5, %8} × {3, 7, 14 gün} için olay oranı ve referans modellerin PR-AUC kazancı raporlanmalı. Hazard formülasyonu tek modelle bütün ufukları verir; eşik seçimi böylece model eğitiminden ayrılır.

**Etiket uygunluğu ile tahmin girdisi ayrımı:** "Geleceğin kaç günü gözlendi", "S_t gelecekte cevap verdi mi" gibi alanlar **yalnız etiket uygunluğu** için kullanılır. Hiçbir zaman özellik olamazlar. Özellik yalnız t günündeki 22:00 turu *tamamlandıktan* sonra bilinen bilgiden hesaplanır.

### 3. Eğitim satırının ve hedefin kesin tanımı [Öneri]

- **Satır:** (product_id, referans_tarihi t). Satır, t günündeki 22:00 turunun gerçek tamamlanma zamanı T_t'de verilen bir tahmini temsil eder. Bütün özellikler yalnız T_t veya öncesinde kaydedilmiş gözlemlerden hesaplanır.
- **Referans fiyat p_t:** t günündeki 22:00 turunda, S_t kümesindeki uygun tekliflerin minimumu. 22:00 turu ürün için başarısızsa satır **oluşturulmaz**; bu bir etiket sorunu değil, tahmin anının olmamasıdır. Alternatif olarak 10:00 turu yedek referans olarak kullanılabilir; bu ayrı bir deney.
- **Gelecek:** t+1 … t+7 takvim günleri, her gün iki tur.
- **Gelecek gün fiyatı f_d:** d günündeki iki turda, S_t ∩ (o gün cevap veren sayfalar) üzerindeki minimum.
- **y_sabit = 1:** Gözlenmiş bir d için 100·f_d ≤ 95·p_t ise. Para tam sayı kuruş olarak tutulduğu için bu tam sayı karşılaştırması yuvarlama hatası üretmez.
- **y = 0:** Uygunluk kuralını karşılayan ve olay içermeyen pencere.
- **y = NULL:** Uygunluk kuralını karşılamayan pencere (A çözümü). B çözümünde bu pencere sansürlü satır olur.
- **Bölümleme:** t tarihine göre yapılır. Etiket aralığı [t+1, t+7] sınırı aşan satırlar temizlenir.

### 4. Aday özellik tablosu

| Özellik | Anlamı | Ham veri | Tahmin anında var mı? | Bizde / Cimri'de | Eksikse | Sızıntı riski |
|---|---|---|---|---|---|---|
| log_ret_1, _7, _14, _30 | log(p_t/p_{t-k}) | Günlük fiyat serisi | Evet | Var / Var (günlük) | NaN + `eksik_gecikme` bayrağı | Düşük; dikkat: p_{t-k} yalnız t'ye kadar olan veriden alınmalı |
| ratio_min_7/14/30 | p_t / min(p_{t-k..t}) | Aynı | Evet | Var / Var | Pencere içindeki mevcut günlerden hesaplanır; gün sayısı ayrı özellik olarak verilir | Pencere t+ günlerini içermemeli |
| ratio_mean_30, ratio_med_30 | p_t / ortalama veya medyan | Aynı | Evet | Var / Var | Aynı | Düşük |
| vol_14, vol_30 | Günlük log getirilerin standart sapması | Aynı | Evet | Var / Var | NaN | Düşük |
| gun_son_dusus | Son ≥%5 düşüşten bu yana geçen gün | Aynı | Evet | Var / Var | Sınır değer (ör. 31) + bayrak | **Orta:** "Son düşüş" tanımı geleceğe bakan etiketten değil, geçmiş fiyattan hesaplanmalı |
| n_degisim_30 | 30 günde fiyat değişim sayısı | Aynı | Evet | Var / Var | NaN | Düşük |
| ic_gun_fark | 10:00 ile 22:00 arasındaki fark | Tur bazlı fiyat | Evet | Var / **Yok** | Cimri'de NaN | Kaynak farkını kodlar (bölüm 5) |
| log_fiyat_duzeyi | log(p_t) | Fiyat | Evet | Var / Var | – | Ürün ezberine vekil olabilir |
| marka, model_ailesi, segment | Kategori | Katalog | Evet | Var / eşleştirme gerekir | "bilinmiyor" kategorisi | Düşük |
| kapasite_log2 | log2(GB) | Katalog | Evet | Var / eşleştirme gerekir | – | Düşük |
| aile_ret_7 | Aynı ailedeki diğer kapasitelerin 7 günlük medyan değişimi | Aile serileri | Evet | Var / Var | NaN | Diğer ürünlerin t+ verisi kullanılmamalı |
| hafta_gunu, ay | Takvim | Tarih | Evet | Var / Var | – | Düşük; ay özelliği 1–2 yıllık veride döneme aşırı uyum sağlayabilir |
| kampanya_yakinlik | Önceden ilan edilmiş kampanyaya kalan gün; pencere kampanya ile çakışıyor mu | **Elle tutulan takvim tablosu** | Evet, *ilan tarihinden sonra* | Takvim yok; oluşturulmalı | 0 / bilinmiyor | **Yüksek:** Geçmiş kampanya tarihleri sonradan bilindiği için girilirse sızıntı olur; kampanyanın ilan tarihi de kaydedilmeli |
| n_sayfa, n_cevap | S_t büyüklüğü, cevap veren sayfa sayısı | Tur kayıtları | Evet | Var / **Yok** | – | Düşük |
| kapsam_degisim_30 | 30 günde eklenen veya çıkan sayfa sayısı | Keşif kayıtları | Evet | Var / Yok | 0 + bayrak | Düşük |
| eksik_oran_30 | 30 günde gözlenmeyen gün oranı | Tur kayıtları | Evet | Var / Var (Cimri eksikleri) | – | **Orta:** Kaynak kimliğini sızdırabilir |
| stok_durumu, stoksuz_gun_30 | Seçilen teklifin stok durumu | Tur kayıtları | Evet | Var / Yok | NaN | Düşük |
| gecmis_gun_sayisi | Ürünün izlendiği gün sayısı | Katalog | Evet | Var / Var | – | Yeni ürün sinyali |
| kaynak | Cimri veya kendi verimiz | Meta | Evet | – | – | **Yüksek** (bölüm 5) |

**Kullanılmayacak alanlar:** Döviz kuru geçmişi, satış adedi, bütün satıcı teklifleri ve çıkış tarihi sistemde yok. *Ek veri önerisi:* Çıkış tarihi elle girilebilir; 60 ürün için yaklaşık bir saatlik iş. Bu veri olmadan `gecmis_gun_sayisi` vekil olarak kullanılır. Kur verisi TCMB'den alınabilir, ancak bu yeni bir entegrasyon ve sızıntı denetimi maliyeti getirir. İlk deneyde bu veri gerekli değil. [Öneri]

**Önişleme yalnız eğitim bölümünden öğrenilmeli [Doğrulanmış]:** scikit-learn "Common pitfalls" belgesi, veriyi önce bölmeyi ve dönüşümleri (StandardScaler, SimpleImputer, özellik seçimi dahil) yalnız eğitim alt kümesinde öğrenmeyi, bunun için de `Pipeline` kullanmayı öneriyor.\[21\] `TargetEncoder.fit_transform` iç cross-fitting yapıyor; varsayılan `cv=5` ve görülmeyen kategoriler hedef ortalamasıyla kodlanıyor.\[22\]\[23\]\[24\] **[Çıkarım, önemli]:** Bu iç bölme zamanı gözetmiyor. scikit-learn 1.9.1 belgesine göre sınıflandırmada StratifiedKFold kullanılıyor ve `shuffle` varsayılan olarak True, yani tarih sırası karışıyor. Örtüşen etiketlerde bu bir sızıntı kaynağı olabilir. Bu nedenle hedef kodlama ya hiç kullanılmamalı, ya `cv` parametresine zaman tabanlı bir bölücü verilmeli (1.9 sürümünden itibaren bölücü kabul ediliyor, ancak belge doğrulama fold'larında örnek tekrarlamayan bir bölücü şart koşuyor; TimeSeriesSplit gibi bölücülerin kabul edilip edilmediği denenmeli), ya da CatBoost'un ordered target statistics yöntemine bırakılmalı. CatBoost makalesi (Prokhorenkova vd., arXiv:1706.09516) bu yöntemin hedef sızıntısından kaynaklanan "prediction shift" sorununu gidermek için tasarlandığını anlatıyor.\[25\] Ancak CatBoost'ta da varsayılan rastgele permütasyon zaman sırasını izlemez. Satırlar zaman sırasıyla verilmeli ve `has_time=True` kullanılmalı; CatBoost "Common parameters" belgesine göre bu parametre girdideki sırayı kullanır ve kategorik özellik dönüşümü ile ağaç yapısı seçiminde rastgele permütasyon yapmaz (varsayılan False) [Doğrulanmış].

### 5. Cimri ve kendi verimiz

**Aynı hedefi mi ölçüyorlar? Hayır, ya da bilinmiyor.** Cimri'nin günlük fiyatının hangi anı temsil ettiği (gün sonu mu, günlük minimum mu, tek bir anlık görüntü mü) ve hangi satıcı ve sayfa kümesinden geldiği bilinmiyor. Bizim 22:00 referansımız tek bir tura ait. Gelecek gün değerimiz ise iki turun minimumu ve bu tanım sistematik olarak daha düşük çıkar. [Çıkarım] Cimri'nin günlük değeri daha geniş bir satıcı kümesinin minimumuysa, Cimri'deki olay oranı bizimkinden farklı olacaktır.

| Seçenek | Değerlendirme |
|---|---|
| Ayrı modeller | Temiz, ama kendi verimiz eğitime yetmez |
| Kaynak alanıyla tek veri seti | Model, kaynak farkını "tahmin başarısı" gibi öğrenebilir; örneğin Cimri'de olay oranı farklıysa `kaynak` özelliği tek başına ayırt edici olur |
| Yalnız ortak özellikler | Sızıntı riski en düşük seçenek; tur içi ve kapsam özellikleri kaybedilir |
| Cimri'de öğren, kendi verimizde doğrula veya uyarla | **Önerilen** |
| Yalnız araştırma | Kendi verisi yeterli olana kadar kullanıcıya olasılık gösterilmemeli |

**Öneri:** Model yalnız ortak özelliklerle Cimri'de eğitilip seçilir. Kendi verimizde ise yalnız *değerlendirme* ve *yeniden kalibrasyon* yapılır. Kaynak alanı modele özellik olarak verilmez; raporlamada katman olarak kullanılır.

**Aynı ürün ve tarih iki kaynakta varsa:** Aynı (ürün, t) iki satır olarak eğitime girmemeli. Bu durumda aynı olay iki kez sayılır ve test sırasında kopyası eğitimde kalabilir. Örtüşen dönemler, iki kaynağın uyum analizinde kullanılmalı: günlük fiyat farkının dağılımı, olay etiketi uyumu (Cohen κ) ve olay tarihi gecikmesi. [Öneri]

**Dağılım kayması:** Cimri verisi son alımla birlikte donacak, kendi verimiz ise birikmeye devam edecek. Bu üç tür kayma yaratır:
- Kovaryat kayması (covariate shift): yeni modeller ve yeni fiyat düzeyleri.
- Önsel olasılık kayması (prior shift): kampanya yoğunluğu değişir.
- Ölçüm kayması: tanımlar farklı.
[Çıkarım] Bu yüzden canlı performans yalnız kendi verimizde, olgunlaşmış etiketlerle izlenmeli.

**Cimri'deki iyi bir sonuç tek başına yeterli değil.** Ek olarak üç kanıt gerekir:
(1) Kendi verimizde, eğitimden sonraki bir dönemde PR-AUC ve Brier skorunun referansları geçmesi.
(2) Kendi verimizde kalibrasyon eğrisinin kabul edilebilir olması.
(3) `y_sabit` ve `y_izlenen` arasındaki farkın küçük olması.

**Son Cimri alımından önce kesinleşmesi gerekenler [Öneri]:**
1. **Hukuki karar:** Madde 2.2 ("mesleki ve ticari olmayan amaçlar") ve madde 4.12 karşısında projenin niteliği nedir: kişisel, akademik ya da ticari?\[1\] Bu karar teknik uygunluktan ayrı ve önce verilmeli. Gerekirse Cimri'den yazılı izin istenmeli.
2. **Ürün eşleştirmesi:** Her Cimri ürün kimliği ile bizim marka + model + kapasite anahtarımız arasında bire bir eşleşme tablosu kurulmalı. Cimri'nin renk veya RAM varyantlarını birleştirip birleştirmediği kontrol edilmeli. Bugün 60 ürünün 57'si eşleşiyor; kalan 3 ürünün nedeni belgelenmeli.
3. **Alanlar:** Tarih (hangi saat dilimi), fiyat (KDV ve kargo dahil mi), fiyat tanımı (minimum mu, tek satıcı mı), satıcı sayısı varsa, eksik gün işareti, alım zamanı ve ham yanıtın saklanması.
4. **Dönem:** Mümkün olan en eski tarihten alım tarihine kadar. Özellikle geçmiş Kasım kampanyaları ve iPhone çıkış dönemleri kapsanmalı.
5. **Örtüşme dönemi:** Kendi ölçümlerimizle çakışan bütün günler alınmalı; uyum analizi bunları gerektiriyor.
6. **Sürüm:** Alım bir veri kesim tarihi ve sağlama toplamı (hash) ile değişmez bir anlık görüntü olarak saklanmalı.

### 6. Modeller ve referanslar

| Aday | Beklenen avantaj ve sınır | Veri ihtiyacı | Kategorik / eksik veri | Windows'ta maliyet | Seçilme koşulu |
|---|---|---|---|---|---|
| **R0 sabit olasılık** | Eğitim dönemindeki olay oranı; ayırt etme gücü yok | Çok az | – | Yok denecek kadar az | Referans |
| **R1 basit kural** | Örneğin p_t/min_30 kovalarına göre eğitim dönemindeki olay sıklığı, artı "son 7 günde düşüş var mı"; açıklanabilir | Az | – | Az | R0'ı PR-AUC'de geçmeli |
| **R2 lojistik regresyon** | 6–10 ölçeksiz özellik, L2 düzenlileştirme; kalibrasyonu genelde iyi | Orta | One-hot ve imputation `Pipeline` içinde | Saniyeler | R1'i geçmeli |
| **M1 LightGBM (ortak)** | Etkileşimleri ve doğrusal olmayan ilişkileri yakalar; eksik veriyi ve kategoriyi doğal olarak işler | Orta-yüksek | Var, yerleşik | pip wheel ile kurulur; [Çıkarım] yaklaşık 20 bin satır × 30 özellik ile saniyeler mertebesinde eğitilir | R2'yi tarih bloklarıyla bootstrap güven aralığında PR-AUC'de geçmeli **ve** kalibrasyon sonrası Brier ile log loss'ta R2'den kötü olmamalı |
| **M2 CatBoost** | Ordered target statistics, az veride daha az ayar ihtiyacı | Orta | Var, yerleşik | LightGBM'den daha yavaş, ama bu ölçekte sorun değil | M1 ile aynı koşul; ikisinden sade olanı tercih edilir |
| **H1 kesikli zamanlı hazard (lojistik veya LightGBM)** | Sansürü doğru ele alır; bütün ufukları tek modelle verir | Satır sayısı ×7 | Aynı | Az-orta | Aynı 7 günlük olayda M1 ile eşit veya daha iyi kalibrasyon |

**Klasik zaman serisi yöntemleri:** ETS ve ARIMA sürekli değerler varsayar; basamaklı ve uzun süre sabit kalan fiyatlarda zayıftır. Olay olasılığı için de simülasyon gerekir. Yalnız `y_regresyon` deneyinde, ürün başına referans olarak kullanılabilir. [Çıkarım]

**Derin öğrenme:** Bu veri ölçeğinde (57–60 seri, yaklaşık 1 yıl) anlamlı değil. Montero-Manso & Hyndman'ın global modellerle ilgili bulguları, derin modelin ancak çok sayıda seride avantaj sağladığını düşündürüyor. [Çıkarım] Bakım maliyeti de yüksek.

**Hiyerarşik Bayes (partial pooling):** Bu formülasyon teorik olarak uygun, ama ilk deney sırasına alınmamalı. M1, ürün ve aile düzeyinde belirgin biçimde kötü kalibre çıkarsa sonraki aday odur.

**En küçük anlamlı deney sırası [Öneri]:**
1. Cimri'de R0 → R1 → R2. Hedef `y` (A çözümü), ufuk 7 gün, eşik %5.
2. Aynı bölmelerle M1. Kalibrasyon yalnız ayrı tutulan doğrulama dilimiyle yapılmalı.
3. Ablasyon: M1 kimlikli ve kimliksiz; leave-family-out.
4. Etiket varyantları: sıkı tam pencere, A ve B (H1).
5. Eşik ızgarası (bölüm 2).
6. M2, yalnız M1, R2'yi geçerse denenir.
7. Kendi verimizde ileriye dönük gölge değerlendirme.

### 7. Değerlendirme ve veri sızıntısı

**Rastgele satır bölmenin riskleri:** Ardışık günlerin etiketleri 7 günlük ufkun 6 gününü paylaşır. Rastgele bölmede t günü testte, t+1 günü eğitimde olur. Model böylece "geleceği" eğitimde görmüş olur. Aynı kampanya günleri de iki tarafa dağılır. López de Prado'nun purging ve embargo önerisi tam olarak bu sızıntıyı hedefliyor.\[26\] [Doğrulanmış] scikit-learn'ün `TimeSeriesSplit` sınıfı `gap` parametresine sahip, ancak örnek bazında çalışıyor ve sabit aralıklı tek bir seri varsayıyor.\[27\] Çok ürünlü panelde ise **tarih bazlı** bir bölücü yazılmalı. [Çıkarım]

**Plan [Öneri]:**
1. **Ortak tarih sınırları:** Bütün ürünler aynı tarihte kesilir.
2. **İleri yürüyen değerlendirme (rolling origin):** Hyndman & Athanasopoulos, *Forecasting: Principles and Practice* ("evaluation on a rolling forecasting origin") yaklaşımı.\[28\] Genişleyen eğitim penceresi; doğrulama blokları aylık; en az 4–6 başlangıç noktası (fold). Fold sayısı Cimri tarih aralığına göre belirlenmeli [Deneyle ölçülecek].
3. **Purging:** Eğitimde yalnız t+7 < doğrulama başlangıcı olan satırlar kalır. Doğrulama veya test sınırını aşan etiket pencereleri de silinir. **Embargo:** Doğrulamadan sonra eğitime geri dönülmez (yalnız ileri yürünür). Bu nedenle embargo esas olarak son test dilimi ile önceki dilimler arasında gerekir; 7 gün yeterli.
4. **Örtüşen geçmiş ile sızan etiket farklı şeyler:** Test satırının 30 günlük geçmişinin eğitim dönemiyle çakışması sızıntı **değildir**; bu bilgi gerçek tahmin anında da mevcuttur. Sızıntı, eğitimdeki bir **etiketin** test dönemindeki fiyatları kullanmasıdır.
5. **Tahmin anı:** Özellikler T_t (22:00 turunun tamamlanma zamanı) itibarıyla `as-of` sorgusuyla hesaplanır. Turun bitmemiş sayfaları ve sonradan eklenen yeniden denemeler, kayıt zamanı T_t'den sonraysa kullanılmaz. Bunun için ham tabloda `observed_at` ve `ingested_at` alanları ayrı tutulmalı. [Öneri]
6. **Önişleme ve ayar:** Her fold'da `Pipeline` yeniden fit edilir.\[29\] Hiperparametre araması yalnız iç fold'larda yapılır. Kalibratör, modelin eğitilmediği son doğrulama diliminde öğrenilir. scikit-learn kalibrasyon belgesi de kalibrasyonun model eğitiminde kullanılmamış veriyle yapılmasını şart koşuyor.\[30\]\[31\] [Doğrulanmış]
7. **Son test:** Cimri verisinin son yaklaşık %15'i ve kendi verimizin ileriye dönük dönemi, **tek kez**, model seçimi dondurulduktan sonra kullanılır. Kaç kez bakıldığı deney günlüğüne yazılır.
8. **Bağımlılık:** Güven aralıkları için hareketli blok bootstrap kullanılır (ör. 14 günlük tarih blokları, bütün ürünler birlikte). Ayrıca model ailesi bazında küme bootstrap yapılır. [Öneri; blok uzunluğu deneyle duyarlılık analiziyle belirlenmeli]
9. **Görülmeyen ürünler:** Leave-family-out değerlendirme, ayrı bir tablo olarak raporlanır.

**Accuracy neden yetersiz:** Olumlu oran yaklaşık %10 olduğunda, her zaman "düşmez" diyen model %90 accuracy alır, ama hiçbir bilgi vermez. [Doğrulanmış mantık]

**Ölçütler:**
- **PR-AUC** (`average_precision_score`): Nadir olumlu sınıfta sıralama kalitesini ölçer (Saito & Rehmsmeier 2015).\[32\] Her zaman taban oranla birlikte raporlanmalı, çünkü rastgele modelin PR-AUC'si taban orana eşittir.
- **Brier skoru ve log loss:** Olasılık kalitesini ölçen uygun skor kurallarıdır (proper scoring rules).\[33\] scikit-learn belgesi, Brier'in kalibrasyon ve ayrıştırma (refinement) kayıplarının bileşimi olduğunu, bu yüzden düşük Brier'in daha iyi kalibrasyon anlamına gelmediğini belirtiyor.\[34\]\[35\] Bu nedenle **güvenilirlik diyagramı** (reliability diagram) da gösterilmeli.\[33\]
- **Brier skill score:** R0'a göre iyileşme.
- **Eşikli precision ve recall:** Yalnız ürün kararı için seçilen eşikte raporlanır.

**Toplu ve kırılımlı raporlama:** Toplam sonuç, marka, aile ve ürün bazındaki sonuçlarla birlikte verilmeli. Her hücrede *farklı olay sayısı* yazılmalı. 5'ten az olay içeren hücrelerde skor yerine "yetersiz" yazılmalı (proje tercihi). Toplam sonuç, ürünleri eşit ağırlıklandıran makro ortalama ve satır ağırlıklı mikro ortalama olarak birlikte verilmeli.

**Örtüşme ve etkili örnek sayısı:**
- *Farklı olay:* Ürün başına, aynı fiyat düşüş episodunu (ör. aynı gün başlayan düşüş) kapsayan olumlu pencereler tek bir olay sayılır.
- *Ortalama teklik:* López de Prado'nun tanımına göre, her gün için o günü kapsayan etiket sayısı c_d hesaplanır; satırın tekliği ortalama(1/c_d) olur. Etkili N, bu tekliklerin toplamıdır.\[6\]
- [Çıkarım, ölçülmedi] Cimri'deki 17.668 pencerenin tekliğe göre etkili N değeri bunun çok altında kalacaktır. Bağımsız olay sayısı ise olumlu satır sayısından (yaklaşık 1.770) birkaç kat azdır.
- Teklik değeri örnek ağırlığı olarak da denenebilir.

**"Bekle" hatasının maliyeti:** Hamlet çalışmasından uyarlama. [Öneri] Her test satırı için karar kuralı şudur: P ≥ τ ise "bekle", değilse "şimdi al". Bekleyen kullanıcı en kötü durumda 7. gün alır. Pişmanlık (regret) şöyle tanımlanır: bekleme kararında satın alma fiyatı − p_t, şimdi alma kararında ise p_t − min(f). Bu değerler TL ve yüzde olarak raporlanır. Ayrıca "her zaman şimdi al" ve "her zaman bekle" politikalarıyla karşılaştırılır. Kullanıcı, alım gününde stoksuzluk varsa bunun yanlış "bekle" sayılacağını dikkate almalı. τ, doğrulama diliminde seçilir; testte değiştirilmez.

### 8. Veri yeterliliği ve canlıya alma

Bu bölümdeki bütün eşikler **proje tercihi** olup deneyle güncellenmeli. Literatürde evrensel bir değer yok.

| Kapı | Ölçüt (öneri) |
|---|---|
| **Veri denetimine başlama** | Hemen. Herhangi bir veri yeterli; amaç kapsam ve eksik desenini görmek |
| **İlk araştırma deneyi** | Cimri'de: ≥6 ay tarih aralığı, ≥4 ileri yürüyen fold, her doğrulama fold'unda iki sınıfın da bulunması, toplamda ≥100 farklı olay ve olayların ≥20 ürün ile ≥3 marka arasında dağılması. Kendi verimizde: yalnız tanımlayıcı istatistik |
| **Model seçme** | Fold'ların çoğunda referansı geçmesi; blok bootstrap ile %90 güven aralığının R2 farkında sıfırı dışlaması; leave-family-out'ta R0'dan kötü olmaması |
| **Olasılığı kullanıcıya gösterme** | Kendi verimizde, eğitimden sonraki **en az bir kampanya dönemi ve bir sakin dönem** içeren ileriye dönük değerlendirme (pratikte 60–90 gün); ≥30 farklı olay; kalibrasyon eğrisinde büyük sapma olmaması; Brier skill > 0; `y_sabit` ile `y_izlenen` farkının küçük olması |

**Tahmin göstermeme (abstention) [Öneri]:** Aşağıdaki durumlarda olasılık yerine "yetersiz veri" gösterilir:
- `gecmis_gun_sayisi < 30`,
- son 14 günün eksik oranı > %30,
- p_t/min_30 değeri eğitim dağılımının 1–99 persentil aralığı dışında,
- ailenin eğitimde hiç görülmemiş olması ve leave-family-out skorunun kapıyı geçmemiş olması,
- kalibrasyon kovasında 20'den az doğrulama örneği bulunması.

Bu kural, seçici sınıflandırma (selective classification) ve risk-kapsam (risk-coverage) eğrisiyle değerlendirilmeli: tahmin gösterilen satırların payı karşısında hata. Conformal yöntemler sonraki aşamaya bırakılabilir. Bu literatürün birincil kaynakları bu araştırmada ayrıca doğrulanmadı.

**İşletim (küçük proje, Windows) [Öneri]:**
- **Sürüm:** `models/{tarih}_{kısa_hash}/` klasöründe model dosyası, `metadata.json` (veri kesim tarihi, özellik listesi, kütüphane sürümleri, eğitim fold sınırları, metrikler, kalibratör) ve veri anlık görüntüsünün hash'i tutulur. PostgreSQL'de bir `model_registry` tablosu ve `active` bayrağı bulunur.
- **Yeniden eğitim:** Aylık, ya da kampanya döneminden 7 gün sonra (etiketler olgunlaşınca). Windows Görev Zamanlayıcı ile manuel onaylı çalıştırılır. Arayüz eğitim başlatmaz; bu mevcut ilkeyle uyumlu.
- **İzleme:** Haftalık olarak olgunlaşmış etiketlerde (7 gün gecikmeli) Brier ve kalibrasyon, tahmin edilen ortalama olasılık ile gerçekleşen oranın karşılaştırması, özellik dağılımı (PSI) ve abstention oranı izlenir.
- **Bozulma ve geri alma:** Son 4 haftanın Brier değeri R2'nin üzerine çıkarsa, `active` bayrağı önceki sürüme ya da R1/R2 kuralına çevrilir. Geri dönüş tek bir SQL güncellemesiyle yapılır.

### 9. Hukuki uyarı (teknik uygunluktan ayrı)

- **Cimri:** Kullanım Koşulları madde 2.2 ve 4.12 yukarıda alıntılandı (erişim 27.10.2026).\[1\] Kullanıcı sözleşmesi de üyelerin "Cimri bilgilerini ... yeniden satamaz, paylaşamaz, dağıtamaz" olduğunu söylüyor.\[36\] Son alımın teknik olarak mümkün olması, kullanım hakkı olduğu anlamına gelmez.
- **Trendyol:** R10.net Bilişim Hukuku forumu (20.03.2023), Trendyol üyelik sözleşmesinin madde 3.9'unu "Platformun üzerinde otomatik program, robot, web crawler, örümcek, veri madenciliği (data mining) ve veri taraması (data crawling) gibi 'screen scraping' yazılımları veya sistemleri kullanılması" yasağı olarak alıntılıyor; başka bir ikincil kaynak aynı listeyi madde 3.11 olarak veriyor, yani numara sürüme göre değişmiş olabilir. Canlı metni doğrulayamadım.
- **Hepsiburada:** robots.txt dosyası `/product/`, `/api/`, `/kiyasla/` yollarını ve sıralama/filtre parametrelerini engelliyor, `-p-` ve `-pm-` ürün sayfalarını engellemiyor.\[14\] Bulduğum eski üyelik sözleşmesinde açık bir scraping maddesi yok.\[37\] Daha güncel bir metin bulunamadı.
- **[Öneri]** Proje ticarileşecekse hukuki görüş alınmalı. ML aşaması, toplama yükünü artırmamalı.

## Recommendations

**Bugün yapılabilecekler (veri yetersizken):**
1. Etiket uygunluk kuralını simetrik hâle getirin ve `y_sabit` ile `y_izlenen` hesaplayan bir **etiket denetim raporu** yazın: kendi verimizde ve Cimri'de pencere sayısı, olay sayısı, farklı olay sayısı ve kapsam kaynaklı düşüş oranı.
2. Ham tabloda `observed_at` ve `ingested_at` ayrımını ve tur tamamlanma zamanını garanti altına alın.
3. **Kampanya takvim tablosu** oluşturun: kampanya adı, başlangıç ve bitiş tarihi, ilan tarihi, kaynak. 2026 için örnekler: Hepsiburada Efsane Premium Günleri, 26 Ekim–1 Kasım 2026 (basın bülteni ve ikincil kaynak).\[38\]\[39\] Trendyol 11.11 Süper Alışveriş Günleri, 6–11 Kasım 2026, ve Trendyol Efsane Günler, 26 Kasım–2 Aralık 2026 (Trendyol'un kendi sayfası).\[40\]\[41\] Bazı haber siteleri Trendyol Efsane Günler için 24–27 Kasım tarihini veriyor; bu çelişkide platformun kendi sayfası esas alınmalı.\[42\] **Not:** Araştırma tarihi (27.10.2026) bir kampanya dönemine denk geliyor. Önümüzdeki 5 hafta kendi verimiz için olağan dışı bir dönem.
4. Cimri ürün eşleştirme tablosunu ve hukuki kararı tamamlayın; ardından son alımı yapın.
5. Tarih bazlı ve purging uygulayan bölücüyü, metrik ve bootstrap raporlayıcısını tasarlayın. Bu aşamada model yok.

**Kullanıcının karar vermesi gereken açık noktalar:**
- Projenin niteliği (kişisel, akademik, ticari) ve Cimri'den izin istenip istenmeyeceği.
- Birincil hedefin `y_sabit` mi `y_izlenen` mi olacağı (önerim: `y_sabit`).
- Kullanıcı çıktısı: olasılık mı, üç kademeli öneri ("al", "bekle", "belirsiz") mi?
- Abstention eşikleri ve "yanlış bekle" için kabul edilebilir TL kaybı.
- 22:00 turu başarısız olduğunda 10:00 turunun yedek referans olup olmayacağı.
- Kapasite ve kampanya takvimini elle sürdürme sorumluluğu.

**Aşamalı yol haritası:**
- **Aşama 0 (şimdi–Kasım sonu):** Hukuki karar, eşleştirme, etiket denetimi, kampanya tablosu, son Cimri alımı.
- **Aşama 1:** Cimri üzerinde R0–R2, M1, ablasyonlar ve etiket varyantları. Çıktı: deney raporu; kullanıcıya gösterim yok.
- **Aşama 2:** Kendi verimizde gölge mod. Tahminler kaydedilir ama gösterilmez; etiketler olgunlaşınca kalibrasyon ve pişmanlık ölçülür.
- **Aşama 3:** Kapılar geçilirse, abstention kuralıyla sınırlı gösterim (ör. yalnız olasılık kovaları). Model kaydı ve geri alma mekanizması devrede olur.
- **Aşama 4:** Kendi verisi çoğaldığında Cimri ağırlığı azaltılır. Hazard modeli ve aile bazlı havuzlama yeniden değerlendirilir.

## Caveats

- Proje kodu ve veritabanı incelenmedi. Bütün veri sayıları kullanıcının 23 Ekim 2026 beyanına dayanıyor.
- Guo vd. kalibrasyon çalışması, conformal ve selective prediction, dataset shift taksonomisi ve block bootstrap kaynakları bu araştırmada birincil kaynaktan ayrıca doğrulanamadı. Bu konulardaki öneriler genel yöntem bilgisine dayanıyor.
- CatBoost'un zaman sıralı ayar parametresi ve scikit-learn `CalibratedClassifierCV`'nin `prefit` kullanımı sürüme göre değişebilir; kurulu sürüm belgesiyle teyit edilmeli.\[43\]
- Kampanya tarihleri kısmen haber ve kupon sitelerinden geliyor ve kaynaklar arasında çelişki var. Platformların kendi duyuruları esas alınmalı.
- Hiçbir model için başarı oranı öngörülmedi. Raporda geçen bütün eşikler proje tercihidir ve deneyle güncellenmelidir.

## Sources

1. [Cimri Kullanım Koşulları | Üyelik ve Hizmet Şartları | Cimri](https://www.cimri.com/kullanim-kosullari)
2. [Principles and algorithms for forecasting groups of time series: locality and globality](https://robjhyndman.com/publications/global-forecasting/)
3. [M5 accuracy competition: Results, findings, and conclusions - ScienceDirect](https://sciencedirect.com/science/article/pii/S0169207021001874?via=ihub%3D)
4. [The M5 Accuracy competition: Results, findings and ...](https://statmodeling.stat.columbia.edu/wp-content/uploads/2021/10/M5_accuracy_competition.pdf)
5. [Purged Cross-Validation for Financial ML (2026)](https://www.quantt.co.uk/resources/purged-cross-validation)
6. [Sample Uniqueness & the Sequential Bootstrap](https://daru.finance/research-review/lopez-de-prado/sample-uniqueness-and-bootstrapping)
7. [The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0118432)
8. [A Closer Look at AUROC and AUPRC under Class Imbalance](https://arxiv.org/pdf/2401.06091)
9. [Predicting good probabilities with supervised learning](https://transferlab.ai/refs/niculescu-mizil_predicting_2005/)
10. [1.6a Predicting Good Probabilities with Supervised Learning (2005 - Annual2005\_4ai)](https://ams.confex.com/ams/Annual2005/techprogram/paper_88928.htm)
11. [\[PDF\] To buy or not to buy: mining airfare data to minimize ticket purchase price](https://www.semanticscholar.org/paper/To-buy-or-not-to-buy:-mining-airfare-data-to-ticket-Etzioni-Tuchinda/b43e0bb7e5393502fc599ecb22aa055839a03d4a)
12. [www.stat.berkeley.edu](https://www.stat.berkeley.edu/users/aldous/157/Papers/etzioni.pdf)
13. [To Buy or Not to Buy: Mining Airfare Data to Minimize Ticket Purchase Price](https://www.stat.berkeley.edu/~aldous/157/Papers/etzioni.pdf)
14. <https://www.hepsiburada.com/robots.txt>
15. [Advanced Topics — LightGBM 3.3.2 documentation](https://lightgbm.readthedocs.io/en/v3.3.2/Advanced-Topics.html)
16. [Advanced Topics — LightGBM 4.7.0 documentation](https://lightgbm.readthedocs.io/en/stable/Advanced-Topics.html)
17. [Advanced Topics — LightGBM 4.7.0.99 documentation](https://lightgbm.readthedocs.io/en/latest/Advanced-Topics.html)
18. [Differentially Private Regression for Discrete-Time Survival Analysis](https://arxiv.org/pdf/1708.07436)
19. [Survival prediction models: an introduction to discrete-time modeling](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9316420/)
20. [Discrete-Time Survival Analysis for Heart Failure Mortality Prediction](https://arxiv.org/pdf/2608.04140)
21. [12\. Common pitfalls and recommended practices — scikit-learn 1.9.1 documentation](https://scikit-learn.org/stable/common_pitfalls.html)
22. [TargetEncoder — scikit-learn 1.9.1 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.TargetEncoder.html)
23. [sklearn.preprocessing.TargetEncoder — scikit-learn 1.3.2 documentation](https://scikit-learn.org/1.3/modules/generated/sklearn.preprocessing.TargetEncoder.html)
24. [8.3. Preprocessing data — scikit-learn 1.9.1 documentation](https://scikit-learn.org/stable/modules/preprocessing.html)
25. [CatBoost: unbiased boosting with categorical features](https://arxiv.org/pdf/1706.09516)
26. [Purged & Embargoed Cross-Validation, Explained](https://quantmemo.com/concepts/purged-embargoed-cv)
27. [sklearn.model\_selection.TimeSeriesSplit — scikit-learn 1.1.3 documentation](https://scikit-learn.org/1.1/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
28. [Measuring forecast accuracy Rob J Hyndman Monday, 31 March 2014](https://robjhyndman.com/papers/forecast-accuracy.pdf)
29. [Data leakage through preprocessing](https://theneuralbase.com/scikit-learn/learn/beginner/data-leakage-through-preprocessing/)
30. [1.16. Probability calibration — scikit-learn 0.16.1 documentation](https://scikit-learn.org/0.16/modules/calibration.html)
31. [1.16. Probability calibration — scikit-learn 0.23.2 documentation](https://scikit-learn.org/0.23/modules/calibration.html)
32. [The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4349800/)
33. [Calibrating confidence scores of a machine learning model trained as a natural language interface](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12430330)
34. [1.16. Probability calibration — scikit-learn 0.21.3 documentation](https://scikit-learn.org/0.21/modules/calibration.html)
35. [1.16. Probability calibration — scikit-learn 1.1.3 documentation](https://scikit-learn.org/1.1/modules/calibration.html)
36. [Cimri Kullanıcı Sözleşmesi](https://www.cimri.com/kullanici-sozlesmesi)
37. <https://images.hepsiburada.net/assets/gif/hepsiburada/uyeliksozlesmesi.html>
38. [Hepsiburada Efsane Premium Günleri 2026](https://markodi.com/hepsiburada-efsane-premium-gunleri-2026/)
39. [Türkiye'nin Efsane Kasım'ı Hepsiburada ile başladı - Hibya Haber Ajansı](https://hibya.com/turkiyenin-efsane-kasimi-hepsiburada-ile-basladi-1071542)
40. [2026 Efsane Günler & Black Friday İndirimleri - Trendyol](https://www.trendyol.com/s/efsane-gunler)
41. [2026](https://www.trendyol.com/s/11-kasim-super-alisveris-gunleri)
42. [Black Friday Ne Zaman 2026: Kara Cuma'da Neler İndirime Giriyor? Trendyol Kasım İndirimi - Haber Kocaeli](https://haberkocaeli.com/black-friday-ne-zaman-2026-kara-cumada-neler-indirime-giriyor-trendyol-kasim-indirimi)
43. [1.16. Probability calibration — scikit-learn 1.5.2 documentation](https://scikit-learn.org/1.5/modules/calibration.html)
