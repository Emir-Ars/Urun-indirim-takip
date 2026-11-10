# Docker teslim kopyasını kullanma

Bu rehber Windows 11 x64, Docker Desktop ve WSL2 Linux konteynerleri içindir.
Uygulama tarayıcıda açılan yerel bir web uygulamasıdır. Teslim kopyası,
paketin hazırlandığı andaki fiyat geçmişini ve doğrulanmış ML kayıtlarını sunar.
Yeni veriler kaynak bilgisayardan yeni paketle aktarılır.

## İlk kez başka bilgisayara kurma

1. Docker Desktop/WSL2 kurulumunu tamamlayıp Linux konteynerlerini açın.
   İlk kurulum ve imaj oluşturma sırasında internet gerekir.
2. Pakete uygun proje sürümünü yazabildiğiniz bir klasöre çıkarın. Projenin
   içinde `data\teslim\paketler\` klasörünü oluşturup teslim edilen paket
   klasörünü buraya kopyalayın. Teslim; proje kodu, veri paketi ve bu
   rehberden oluşur. Paket ayrı verilir; GitHub deposu gerçek veriyi içermez.
3. Proje klasöründe PowerShell açın. İlk hazırlığı yapın:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\teslim.ps1 -Action Prepare -Bundle ".\data\teslim\paketler\<PAKET_KLASORU>"
```

`<PAKET_KLASORU>` yerine size verilen gerçek klasör adını yazın. Prepare,
paketin bütünlüğünü ve kod/model uyumunu kontrol eder; ayrı Docker
veritabanını ve dosya alanlarını hazırlar. Yönetici ve API parolaları bu
bilgisayarda ayrı üretilir. İlk hazırlık imaj oluşturduğu için sonraki
açılışlardan uzun sürebilir.

Hazırlık başarıyla bitince açın:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\teslim.ps1 -Action Start
```

**Uygulama hazır** mesajından sonra tarayıcıda **http://127.0.0.1:8503**
adresini açın. Veritabanı, API ve ekran sağlıklı olmadan hazır mesajı gelmez.
Ekranın üstündeki **Veri aktarımı** tarihini kontrol edin. Python ve
PostgreSQL uygulama imajında çalışır; teslim bilgisayarına ayrıca kurulmaz.
`Bypass` yalnız bu PowerShell sürecine aittir; kalıcı çalışma ilkesi değişmez.

Proje sürümü ile paket eşleşmelidir. Uyumsuzlukta manifest veya model
dosyalarını değiştirmeyin; pakete uygun kodu ya da yeni kodla hazırlanmış
paketi kullanın. İlk desteklenen ortam ve paket sözleşmesi
[proje planındadır](../proje_plani.md#docker-ve-teslim-hedefi-92).

## Sonraki açılışlar ve kapatma

Bilgisayarı yeniden başlattıktan veya uygulamayı Stop ile kapattıktan sonra
yukarıdaki **Start** komutunu kullanın. Kapalı Docker Desktop açılmaya
çalışılır ve Linux motoru beklenir. İlk hazırlığı tamamlanmış sistemde
normal açılış imaj indirmez veya yeniden kurulum yapmaz.

Tarayıcı sekmesini kapatmak servisleri durdurmaz; sekmeyi yeniden açmanız
yeterlidir. Çalışan ve sağlıklı sisteme tekrar Start vermek veriyi yeniden
yüklemez veya servisleri yenilemez.

Aynı komutta `-Action` değerini değiştirerek diğer işlemler yapılır:

| Değer | Kullanım |
|---|---|
| `Status` | Seçili/önceki paket ve DB/API/UI sağlık durumu |
| `Logs` | Son loglar; isteğe bağlı `-Lines 100` |
| `Stop` | Seçili uygulamayı kapatır, kalıcı veriyi korur |
| `Rollback` | Önceki hazırlanmış pakete döner |

Örneğin veriyi koruyarak kapatma:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\teslim.ps1 -Action Stop
```

Paket klasörleri, yerel hazırlık kayıtları ve Docker kalıcı alanları açılış
ve geri dönüş için gereklidir. Teslim kopyasının parolaları `data/teslim/`
altında Git dışında saklanır. Kaynak bilgisayarın hazırlık/sır klasörünü
başka bilgisayara taşımayın; yeni bilgisayar kendi Prepare işlemini yapar.

## Yeni veriyi aktarma

**Kaynak bilgisayarda**, canlı Windows ortamındaki araçlarla yeni paket alınır:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\teslim.ps1 -Action Export
```

Kaynak `.venv`, PostgreSQL 17 araçları ve mevcut parola dosyası düzenini
kullanır. Toplama, keşif veya tahmin kaydı yazımı sürerken paket alınmaz;
ortak kilit doluysa komut beklemeden durur. Kaynak görevleri kendi düzeninde
çalışır; teslim kopyası otomatik veri toplamaz.

Yeni paket klasörü teslim bilgisayarına kopyalanır. İlk kurulumdaki Prepare
komutuna yeni klasör verilir. Çalışan ekran varsa doğrulanan yeni kopyaya
geçer; açılış başarısızsa önceki çalışan kopyayı yeniden açmayı dener.
Ekran kapalıysa yeni paket seçilir, ardından Start gerekir. Aynı paket
tekrar verilirse mevcut DB'nin üzerine geri yükleme yapılmaz.

Önceki pakete dönüşte Rollback kullanılır. İlk kurulumda henüz önceki paket
yoktur; bir sonraki başarılı paket geçişinde geri dönüş kaydı oluşur.
Her paketin uygulama imajı kimliği sabittir. Paket/imaj/kalıcı alanları
korumak, eski sürüme dönebilmeyi sağlar.

## Tahmin kartı ve sorun giderme

Gerçek olasılık gösterimi varsayılan olarak kapalıdır. 5 Ocak 2027 kesin
değerlendirmesinin koşulları sağlanırsa kullanıcı ayrıca gösterim bakımını
çalıştırır. Yeni teslim paketi kendi onayını gerektirir. Bakımın değişmeyen
kuralları [teknik rehberdedir](teknik.md#docker-servis-bağlantısı-ve-gösterim-bakımı).

| Mesaj / durum | Yapılacak iş |
|---|---|
| Docker bulunamadı veya Linux motoru hazır değil | Docker Desktop/WSL2 ilk kurulumunu tamamlayın, Linux motorunu açıp tekrar deneyin |
| Hazır paket seçilmedi | Önce Prepare çalıştırın |
| Paket/kod/model veya hash uyuşmazlığı | Doğru kod ve bozulmamış paketle tekrar hazırlayın |
| 8503 başka uygulamada kullanılıyor | O uygulamayı belirleyip kapatın veya portu boşaltın; teslim komutu zorla kapatmaz |
| Yarım hazırlık / alan zaten var | Alanı koruyun; Status/Logs ve hazırlık hatasıyla hedefli inceleme yapın |
| Yeni paket açılamadı, önceki paket açıldı | Eski kopya kullanılabilir; yeni paketin hatasını inceleyin |
| Önceki kopya da açılamadı | Docker motorunu ve Status/Logs çıktısını kontrol edip Start deneyin |

Gizli dosyaları veya parola dosyası içeriğini hata çıktısına eklemeyin.
Normal işlemler veri alanlarını otomatik silmez.

## Kabulün kapsamı

Tekrarlanabilir yapay Docker kabulü `tools/docker_check.py` ile çalışır;
CI işi yalnız üretilmiş model/veri ve `teslim_kabul_test` kullanır. Gerçek
veri paketi CI'a gönderilmez. Kabul raporu, komutun yeni `artifacts/`
klasörüne yazılır. Dış ağsız denemede yalnız kabul projesinin Docker ağı
`internal` yapılır; bilgisayarın interneti ve canlı görevler değiştirilmez.
Bu ayar [Docker'ın ağ yalıtımı sözleşmesine](https://docs.docker.com/reference/compose-file/networks/#internal)
dayanır.

Ayrı bir Windows bilgisayarı mevcut olduğunda son kullanıcı kabulü:

- Temiz proje klasöründe ilk Prepare ve Start başarılı olmalı.
- Aktarım tarihi, örnek fiyatlar ve iki grafik verilen paketle eşleşmeli.
- Stop/Start sonrası veri korunmalı; yeni paket ve Rollback denenmeli.
- İlk hazırlık tamamlandıktan sonra test bilgisayarında internet kapalıyken
  Start ve tarayıcı ekranı çalışmalı.

Bu fiziksel bilgisayar denemesi, bu bilgisayardaki boş kurulum klasörü ve
yalıtılmış Docker ağ denemesiyle aynı kanıt değildir. Güncel tamamlanma ve
bekleyen kabul durumu [9.7 plan satırında](../proje_plani.md#kalan-iş-sırası-6-kasım-kararı)
izlenir.
