<#
.SYNOPSIS
  Fiyat toplama turunu Görev Zamanlayıcı'ya kurar: her gün 10:00 ve 22:00.

.DESCRIPTION
  Görev bu kullanıcı adına ve yalnızca oturum açıkken çalışır; Windows şifresi
  saklanmaz, veritabanı şifresi kullanıcının pgpass.conf dosyasından okunur.
  Yönetici izni gerekmez. Tekrar çalıştırmak görevi aynı ayarlarla yeniden kurar.

  Kurulum:  powershell -ExecutionPolicy Bypass -File scripts\zamanlayici_kur.ps1
  Kaldırma: powershell -ExecutionPolicy Bypass -File scripts\zamanlayici_kur.ps1 -Kaldir
#>
param([switch]$Kaldir)

$ErrorActionPreference = 'Stop'
$taskPath = '\FiyatTakip\'
$taskName = 'FiyatToplamaTuru'

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
if (-not [Environment]::GetEnvironmentVariable('DATABASE_URL', 'User')) {
    throw 'DATABASE_URL kullanıcı ortam değişkeni tanımlı değil (docs/teknik.md, Veritabanı)'
}

# pythonw.exe konsol penceresi açmaz; çıktı data\logs altındaki log dosyasına yazılır.
# Çalışma klasörü proje klasörüdür: config\ ve data\ yolları buna göre bulunur.
$action = New-ScheduledTaskAction -Execute $pythonw `
    -Argument '-m app.collection --scheduled' -WorkingDirectory $root
$triggers = foreach ($at in '10:00', '22:00') {
    $trigger = New-ScheduledTaskTrigger -Daily -At $at
    # Varsayılan saati UTC'ye çevirir; yerel saat olarak yazılır (saat dilimi
    # veya yaz saati değişse de tur yerel 10:00 ve 22:00'de başlar).
    $trigger.StartBoundary = (Get-Date $at).ToString('s')
    $trigger
}
# StartWhenAvailable: bilgisayar kapalıyken kaçan tur açılınca bir kez yapılır.
# Pil: Windows'un varsayılanı yalnız şarjdayken çalıştırmaktır; dizüstünde kapatılır.
# WakeToRun verilmez: bilgisayar uyandırılmaz. Takılan tur 2 saatte durdurulur;
# o tur 'running' kalır ve bir sonraki tur onu 'interrupted' yapar.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskPath $taskPath -TaskName $taskName -Action $action `
    -Trigger $triggers -Settings $settings -Principal $principal -Force `
    -Description 'Fiyat toplama turu (python -m app.collection --scheduled); log: data\logs' |
    Out-Null

$info = Get-ScheduledTaskInfo -TaskPath $taskPath -TaskName $taskName
Write-Host "Görev kuruldu: $taskPath$taskName ($user)"
Write-Host "Sonraki çalışma: $($info.NextRunTime)"
