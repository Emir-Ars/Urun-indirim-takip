<#
.SYNOPSIS
  Günlük gölge tahminini Görev Zamanlayıcı'ya kurar: her gün 11:00.

.DESCRIPTION
  Görev pythonw.exe ile penceresiz çalışır; çıktı data\logs\golge_*.log
  dosyasına, veri görüntüleri ve resmi kayıtlar data\ml\golge altına yazılır.
  Bilgisayar kapalıyken kaçan çalışma açılınca yapılır. Tur sürüyorsa komut
  5 dakika arayla en çok 90 dakika bekler. Tahminler ekranda gösterilmez.

  API_DATABASE_URL kullanıcı ortam değişkeni tanımlı olmalıdır; parola
  pgpass.conf'tan okunur. Görev yalnız bu kullanıcının oturumu açıkken çalışır.
  Yönetici izni gerekmez; yeniden kurulum aynı görevi günceller.

  Kurulum:  powershell -ExecutionPolicy Bypass -File scripts\golge_zamanlayici_kur.ps1
  Kaldırma: powershell -ExecutionPolicy Bypass -File scripts\golge_zamanlayici_kur.ps1 -Kaldir
#>
param([switch]$Kaldir)

$ErrorActionPreference = 'Stop'
$taskPath = '\FiyatTakip\'
$taskName = 'GolgeTahmin'

if ($Kaldir) {
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
if (-not (Test-Path -LiteralPath $pythonw)) {
    throw "Bulunamadı: $pythonw (önce .venv kurulmalı; README 'Hızlı başlangıç')"
}
if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable('API_DATABASE_URL', 'User'))) {
    throw 'API_DATABASE_URL kullanıcı ortam değişkeni tanımlı değil (docs/teknik.md, Günlük gölge çalışması)'
}

# pythonw.exe konsol açmaz; çalışma klasörü bütün göreli yolları projeye bağlar.
$action = New-ScheduledTaskAction -Execute $pythonw `
    -Argument '-m app.ml shadow-daily --scheduled' -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At '11:00'
$trigger.StartBoundary = (Get-Date '11:00').ToString('s')
# Kaçan günleri komut tamamlar; ikinci tetikleme ayrı süreç başlatmasın.
# 2 saat, 90 dakikalık tur beklemesine ve görüntü/model hesabına pay bırakır.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskPath $taskPath -TaskName $taskName -Action $action `
    -Trigger $trigger -Settings $settings -Principal $principal -Force `
    -Description 'Günlük gölge tahmini; log: data\logs\golge_*.log, kayıt: data\ml\golge' |
    Out-Null

$task = Get-ScheduledTask -TaskPath $taskPath -TaskName $taskName
$info = Get-ScheduledTaskInfo -TaskPath $taskPath -TaskName $taskName
Write-Host "Görev kuruldu: $taskPath$taskName ($user)"
Write-Host "Komut: $($task.Actions.Arguments)"
Write-Host "StartWhenAvailable: $($task.Settings.StartWhenAvailable)"
Write-Host "Sonraki çalışma: $($info.NextRunTime)"
