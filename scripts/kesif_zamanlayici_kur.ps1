<#
.SYNOPSIS
  Haftalık keşfi Görev Zamanlayıcı'ya kurar: her Pazar 14:00, önizleme veya otomatik kabul.

.DESCRIPTION
  Görev `python -m app.discovery --scheduled --dry-run` komutunu penceresiz çalıştırır:
  siteleri tarar (yaklaşık 35 dakika), kataloğa yazmaz ve data\logs\kesif_<tarih-saat>.log
  ile data\discovery\kesif_<tarih-saat>.json dosyalarını bırakır. Raporu inceledikten
  sonra kataloğa eklemek için (siteye gitmeden):
    .venv\Scripts\python.exe -m app.discovery --apply-report data\discovery\kesif_<tarih-saat>.json

  -OtomatikKabul seçilirse görev --scheduled --auto-accept çalıştırır: yeterli
  kimlik kanıtı olan adaylar otomatik kataloğa eklenir; eksik/çelişkili olanlar
  dışarıda kalır. İlk geçiş ayrı kullanıcı kabulü ister. Git işlemi yapılmaz.
  Seçeneksiz yeniden kurulum önizleme moduna döndürür.

  Görev bu kullanıcı adına ve yalnızca oturum açıkken çalışır; Windows şifresi saklanmaz.
  Yönetici izni gerekmez. Keşif veritabanı kullanmaz. Tekrar çalıştırmak görevi aynı
  ayarlarla yeniden kurar. Fiyat toplama görevine (zamanlayici_kur.ps1) dokunmaz.

  Kurulum:  powershell -ExecutionPolicy Bypass -File scripts\kesif_zamanlayici_kur.ps1
  Otomatik: powershell -ExecutionPolicy Bypass -File scripts\kesif_zamanlayici_kur.ps1 -OtomatikKabul
  Kaldırma: powershell -ExecutionPolicy Bypass -File scripts\kesif_zamanlayici_kur.ps1 -Kaldir
#>
param([switch]$Kaldir, [switch]$OtomatikKabul)

$ErrorActionPreference = 'Stop'
$taskPath = '\FiyatTakip\'
$taskName = 'HaftalikKesif'

if ($Kaldir -and $OtomatikKabul) {
    throw '-Kaldir ve -OtomatikKabul birlikte kullanılamaz.'
}

if ($Kaldir) {
    # Görev yoksa (ör. arayüzden silinmiş) Unregister-ScheduledTask 'Stop'
    # ayarıyla anlaşılmaz bir İngilizce CIM hatasıyla düşerdi.
    $existing = Get-ScheduledTask -TaskPath $taskPath -TaskName $taskName `
        -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Host "Görev zaten kurulu değil: $taskPath$taskName"
        return
    }
    Unregister-ScheduledTask -TaskPath $taskPath -TaskName $taskName -Confirm:$false
    Write-Host "Görev kaldırıldı: $taskPath$taskName"
    return
}

$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $pythonw)) {
    throw "Bulunamadı: $pythonw (önce .venv kurulmalı; README 'Hızlı başlangıç')"
}

# pythonw.exe konsol penceresi açmaz; çıktı data\logs altındaki log dosyasına yazılır.
# Çalışma klasörü proje klasörüdür: config\ ve data\ yolları buna göre bulunur.
$arguments = '-m app.discovery --scheduled --dry-run'
$description = 'Haftalık keşif önizlemesi; katalog yazılmaz'
if ($OtomatikKabul) {
    $arguments = '-m app.discovery --scheduled --auto-accept'
    $description = 'Haftalık keşif; kimlik kanıtı yeterli adaylar otomatik kataloğa eklenir'
}
$action = New-ScheduledTaskAction -Execute $pythonw `
    -Argument $arguments -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '14:00'
# Varsayılan saati UTC'ye çevirir; yerel saat olarak yazılır (saat dilimi veya yaz
# saati değişse de keşif yerel Pazar 14:00'te başlar).
$trigger.StartBoundary = (Get-Date '14:00').ToString('s')
# StartWhenAvailable bilerek verilmez: kaçan keşif sonradan telafi edilmez. Geç açılan
# bir bilgisayarda telafi keşfi (~35 dk) ortak kilidi tutup 22:00 fiyat turunu
# atlatabilirdi; kaçan hafta elle çalıştırılır. WakeToRun da yok: bilgisayar
# uyandırılmaz. Çalışırken gelen ikinci tetikleme atılır (IgnoreNew); takılan keşif
# 2 saatte durdurulur; hazırlık kaydı varsa sonraki başlangıç uzlaştırır.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskPath $taskPath -TaskName $taskName -Action $action `
    -Trigger $trigger -Settings $settings -Principal $principal -Force `
    -Description "$description ($arguments); log: data\logs, rapor: data\discovery" |
    Out-Null

$task = Get-ScheduledTask -TaskPath $taskPath -TaskName $taskName
$info = Get-ScheduledTaskInfo -TaskPath $taskPath -TaskName $taskName
Write-Host "Görev kuruldu: $taskPath$taskName ($user)"
Write-Host "Komut: $arguments"
Write-Host "StartWhenAvailable: $($task.Settings.StartWhenAvailable) (False: kaçan çalışma telafi edilmez)"
Write-Host "Sonraki çalışma: $($info.NextRunTime)"
