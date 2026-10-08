# Proje çalışma talimatları (Claude Code ve Codex için ortak)

Bu dosya projede çalışan her yapay zekâ aracının ortak talimatıdır. Codex bu
dosyayı doğrudan okur; Claude Code yerel `CLAUDE.md` üzerinden içe aktarır.
Çalışma kuralları yalnız burada değiştirilir. Araçların kendi hafızasına
güvenilmez; diğer araç onu göremez. Kalıcı bilgi repodaki dosyalarda durur.

## Oturum başında

1. `proje_plani.md`: kararların ve aşama durumunun ana kaynağı.
2. `DEVAM.md` (varsa): yerel devir notu, Git dışında. Son oturumdan kalan yarım
   işi, bekleyen kararları ve sıradaki adımı içerir.
3. `git status` ve `git log --oneline -5`: commit edilmemiş değişiklikler.
4. Gerekirse `README.md` (proje tanıtımı) ve `docs/teknik.md` (çalıştırma,
   işleyiş, kurallar, hata kodları).

## Oturum sonunda ve araç değiştirmeden önce

`DEVAM.md` yeniden yazılır. Kullanıcı "devir notunu güncelle" dediğinde ya da
oturum biterken bunu yap. Kalıcı karar ve durum bilgisi `proje_plani.md`'ye,
çalışma kuralı bu dosyaya yazılır. İki araç aynı anda çalıştırılmaz.
Kullanıcının geçiş adımları ve kopyala-yapıştır mesajları yerel
`ARAC_GECISI.md` dosyasındadır (Git dışında).

`DEVAM.md` başlıkları:

- Tarih, saat ve notu yazan araç
- Aşama ve adım (`proje_plani.md` Bölüm 9)
- Yapıldı, commit edilmedi: dosyalar ve ne değiştiği
- Bekleyen kararlar: kullanıcıya sorulacaklar ve verilmiş cevaplar
- Sıradaki iş
- Kullanıcının çalıştırması gereken komutlar ve çıktıda neye bakılacağı
- Riskler ve açık sorular

## Belgeleri güncel tutma (kullanıcı istemeden, aynı oturumda)

Belgeleri bu araçlar okur ve günceller; kullanıcının ayrıca hatırlatması
beklenmez. Güncellenen belgeyi mesajda bir cümleyle söyle.

| Ne olduğunda | Hangi belge |
|---|---|
| Kullanıcı bir karar verdi; plan, takvim veya sıra değişti | `proje_plani.md`: ilgili adım satırı, Bölüm 8 (açık kararlar) veya takvim |
| Bir plan adımı bitti | `proje_plani.md` durum tabloları (Bölüm 2 ve 9); README'deki sayılar (test, katalog) |
| Kodun davranışı, komutu, çıkış kodu veya kuralı değişti | `docs/teknik.md` ilgili bölüm; gerekiyorsa README |
| Canlıda yeni bir sınır veya hata görüldü | `proje_plani.md` Bölüm 7 (bilinen sınırlar / bakım listesi) |
| Kullanıcı kalıcı bir çalışma kuralı söyledi ("bundan sonra hep…") | Bu dosya (`AGENTS.md`) |
| Oturum bitiyor veya araç değişecek | `DEVAM.md` |

`proje_plani.md` uzun ve katmanlıdır; kullanıcı yeniden düzenlenmesini
istemedi. Yeni bilgi ilgili yere eklenir, eski ve yeni bilgi çelişirse
eskisi düzeltilir; belge baştan yazılmaz.

## Kullanıcıyla çalışma

- Kullanıcı projeyi öğrenerek geliştiren bir stajyer. Bütün mesajlar Türkçe
  yazılır, kısa durum satırları dahil.
- Adım adım ilerle ve her adımdan sonra dur. Her değişiklikte amacı, akışa
  bağlantısını, doğrulamayı ve açık sınırları anlat; terimleri açıkla. Hızlı ve
  toplu değişiklik kullanıcıyı kaybettirir.
- Kararlar netleşmeden kod yazma: önce plan, sonra kullanıcının onayı. Plan veya
  açıklama istendiğinde kod üretme.
- Yeni mimari seçimleri kullanıcıyla netleştir. Kullanıcının güncel kararı eski
  bir belgeyle çelişirse çelişkiyi söyle ve belgeyi karara uydur.
- Planlanan, uygulanmış ve karar bekleyen işleri birbirine karıştırma.
  Tamamlanan adımın durumunu plana işle.
- Dosyaları sorumluluğa göre ayır; gereksiz iskelet ve dosya çoğaltma.

## Canlı işler ve veri

- Siteye giden komutları kullanıcı kendi terminalinden çalıştırır: toplama turu
  (`python -m app.collection`), keşif (`python -m app.discovery`) ve
  `tests/manual/*`. Sen komutu ve çıktıda neye bakılacağını ver; arka planda
  canlı iş yürütme.
- Zamanlanmış tur her gün 10:00 ve 22:00'de başlar ve yaklaşık 31 dakika sürer.
  Görevi Görev Zamanlayıcı başlatır: `\FiyatTakip\FiyatToplamaTuru`, logları
  `data/logs/`. O sırada canlı komut çalıştırma. Tur kodu başlarken içe
  aktarır; o saatlerde `app/` altındaki dosyaları yarım bırakma.
- Zamanlanmış keşif her Pazar 14:00'te başlar ve yaklaşık 35 dakika sürer
  (`\FiyatTakip\HaftalikKesif`; logları `data/logs/kesif_*.log`, raporları
  `data/discovery/`). Katalog yazmaz; yeni sayfalar kullanıcı raporu inceleyip
  `python -m app.discovery --apply-report <rapor>` çalıştırınca girer. O sırada
  canlı komut çalıştırma ve `app/discovery/` ile ortak dosyaları yarım bırakma.
- Gerçek kaynakta bulunmayan fiyat, stok, kimlik veya kapsam bilgisini uydurma.
- Gerçek veritabanına (`fiyat_takip`) yalnız okuma sorgusuyla bak. Testler
  yalnız adı `_test` ile biten veritabanını kullanır. Veritabanı şifresi yalnız
  `%APPDATA%\postgresql\pgpass.conf` dosyasındadır; repoya, belgeye veya mesaja
  yazılmaz.
- Uygulanmış bir migration dosyası (ör. `001_initial.sql`) tek bir bayt bile
  değiştirilmez; şema değişikliği yeni numaralı dosyayla yapılır.

## Kod ve kontrol

- Sözleşmeleri koru:
  - Scraper'ın sözleşmesi `fetch(listing) -> PriceObservation`'dır.
  - HTTP yalnız `app/scraper/http.py` ve `curl_cffi` ile yapılır;
    requests/httpx/Playwright/Selenium kullanılmaz. Bunu `tests/test_http.py`
    denetler.
  - Yeni telefon veriyle, `config/discovery.json` üzerinden eklenir.
- Scraper ve keşfin kimlik kuralları yalnız canlıda görülen gerçek bir örnekle
  değiştirilir ve her değişikliğe regresyon testi eklenir.
- Kod tanımlayıcıları İngilizce, yorumlar ve kullanıcıya dönük mesajlar
  Türkçedir. Yorum yalnız "neden böyle?" sorusunu yanıtlar.
- Kod değiştiğinde bütün testleri ve biçim denetimlerini çalıştır (Windows):
  `.venv\Scripts\python.exe -m pytest -q`,
  `.venv\Scripts\python.exe -m black --check app tests` ve
  `.venv\Scripts\python.exe -m flake8 app tests`.
  Veritabanı testleri `TEST_DATABASE_URL` ister; değişken tanımlı değilse
  yerelde atlanır. Çıktıda `skipped` sayısı 0 değilse "bütün testler geçti"
  denmez.
- Test sonucunu canlı sonuçla karıştırma. Testler kuralları sınar; "testler
  geçti", "siteler bugün doğru okunuyor" ya da "pazaryerinin tamamı tarandı"
  anlamına gelmez.
- Yerel taslakları (`_eski_taslaklar/`) veya kurulu bağımlılıkları tamamlanmış
  özellik sayma.

## Git

- `git add .` kullanılmaz; dosyalar tek tek seçilir ve kullanıcının
  değişiklikleri korunur. `data/`, `artifacts/`, `_eski_taslaklar/`,
  `DEVAM.md`, `ARAC_GECISI.md` ve `CLAUDE.md` gönderilmez.
- Her plan adımı bitince tek commit atılır:
  1. Testler ve biçim denetimleri geçer.
  2. Dosya listesi ve Türkçe commit mesajı kullanıcıya gösterilir.
  3. Kullanıcı onaylarsa commit ve push yapılır.
  4. Push sonrası CI (GitHub Actions) yeşil olmalıdır.
- Commit'lerde ve PR'larda yazar yalnız kullanıcıdır (Emir-Ars).
  `Co-Authored-By` satırı veya herhangi bir yapay zekâ imzası (Claude, Codex…)
  eklenmez.
- `gh` kurulu değil. CI sonucu herkese açık API'den okunur:
  `https://api.github.com/repos/Emir-Ars/Urun-indirim-takip/actions/runs`.

## Windows notları

- Python: `.venv\Scripts\python.exe`. Kabuk: Windows PowerShell 5.1.
- Türkçe commit mesajını UTF-8 bir dosyaya yaz ve `git commit -F <dosya>` kullan;
  here-string ile boru hattı mesajı bozar.
- PowerShell'den `psql -c` sorgusunda Türkçe harf kullanma (kod sayfası
  857/1254); veritabanı okuması için küçük bir Python betiği daha güvenlidir.
- `.ps1` dosyaları UTF-8 **BOM'lu** kaydedilir; PowerShell 5.1 BOM'suz
  dosyadaki Türkçe karakterleri bozar.
- Terminalde Türkçe çıktı için `[Console]::OutputEncoding = [Text.Encoding]::UTF8`.
