param([string]$Case, [string]$Root)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
. (Join-Path (Split-Path (Split-Path $PSScriptRoot)) 'scripts/teslim_ortak.ps1')
. (Join-Path (Split-Path (Split-Path $PSScriptRoot)) 'scripts/teslim_paket.ps1')
$script:DeliveryRoot = $Root
[IO.Directory]::CreateDirectory((Get-DeliveryBase)) | Out-Null
$a = 'a' * 64
$b = 'b' * 64
$old = [PSCustomObject]@{bundle_sha256=$a; image_id=('sha256:' + $a); project_name='old'}
$script:oldRecord = $old
$target = [PSCustomObject]@{bundle_sha256=$b; image_id=('sha256:' + $b); project_name='new'}
$selection = [PSCustomObject]@{current=$a; previous=$null}
$script:events = @()
function Assert($Value, [string]$Message) { if (-not $Value) { throw $Message } }
function Expect-Error([scriptblock]$Code, [string]$Contains) {
    $caught = $false
    try { & $Code } catch { $caught = $true; Assert ($_.Exception.Message.Contains($Contains)) $_.Exception.Message }
    Assert $caught 'Beklenen hata oluşmadı.'
}
function Mock-Switch {
    function script:Read-DeliveryRecord($Digest) { Assert ($Digest -eq $a) 'Yanlış eski paket'; return $script:oldRecord }
    function script:Get-DeliveryServices($Record) { return @{api=@{Running=$true}; ui=@{Running=$true}} }
    function script:Test-DeliveryCopy($Record) { $script:events += 'verify:' + $Record.project_name }
    function script:Stop-DeliveryCopy($Record, $Database) { if ($Record.project_name -eq 'old') { Assert (-not $Database) 'Geçişte eski DB erken kapatılmamalı' } else { Assert $Database 'Başarısız aday DB kapatılmalı' }; $script:events += 'stop:' + $Record.project_name }
    function script:Stop-DeliveryDatabase($Record) { $script:events += 'db-stop:' + $Record.project_name }
    function script:Start-DeliveryCopy($Record) { $script:events += 'start:' + $Record.project_name }
}
function Mock-Start {
    function script:Test-DeliveryCopy($Record) { $script:events += 'verify' }
    function script:Assert-DeliveryPort($Record, $Services) { $script:events += 'port' }
    function script:Invoke-DeliveryCompose($Record, $ComposeArguments) { $script:events += ($ComposeArguments -join ' ') }
    function script:Get-DeliveryServices($Record) {
        return @{db=@{Running=$true; Health='healthy'}; api=@{Running=$true; Health='healthy'; Image=$old.image_id; Id=$a}; ui=@{Running=$true; Health='healthy'; Image=$old.image_id; Network=('container:' + $a)}}
    }
}
try {
    switch ($Case) {
        'exclusive_action' {
            $held = Open-DeliveryGate
            try { Expect-Error { Open-DeliveryGate } 'Başka bir teslim işlemi' } finally { $held.Dispose() }
            $next = Open-DeliveryGate
            $next.Dispose()
        }
        'selection' {
            Set-DeliverySelection $a $null
            Assert ((Get-DeliverySelection).current -eq $a) 'İlk seçim'
            Set-DeliverySelection $b $a
            Assert ((Get-DeliverySelection).previous -eq $a) 'Önceki seçim'
            Assert (@(Get-ChildItem (Get-DeliveryBase)).Count -eq 1) 'Geçici dosya kaldı'
        }
        'bad_selection' {
            foreach ($value in @('../outside', ('A' * 64), $a)) {
                Expect-Error { Set-DeliverySelection $value $a } 'geçersiz'
            }
            Write-DeliveryJson (Join-Path (Get-DeliveryBase) 'selection.json') @{format_version=1; current='../outside'; previous=$null}
            Expect-Error { Get-DeliverySelection } 'geçersiz'
        }
        'same_package' {
            Mock-Switch
            Switch-DeliveryCopy $old $selection
            Assert ($script:events.Count -eq 0) 'Aynı pakette gereksiz işlem'
            Assert (-not (Get-DeliverySelection)) 'Seçim geçmişi değişti'
        }
        'stopped_switch' {
            Mock-Switch
            function Get-DeliveryServices($Record) { return @{api=@{Running=$false}; ui=$null} }
            Switch-DeliveryCopy $target $selection
            Assert ((Get-DeliverySelection).current -eq $b) 'Yeni paket seçilmedi'
            Assert ($script:events.Count -eq 0) 'Kapalı uygulama açıldı'
        }
        'running_switch' {
            Mock-Switch
            Switch-DeliveryCopy $target $selection
            Assert (($script:events -join ',') -eq 'verify:new,stop:old,start:new,db-stop:old') 'Geçiş sırası'
            Assert ((Get-DeliverySelection).previous -eq $a) 'Geri dönüş kaydı'
        }
        'failed_switch' {
            Mock-Switch
            Set-DeliverySelection $a $null
            function Start-DeliveryCopy($Record) { $script:events += 'start:' + $Record.project_name; if ($Record.project_name -eq 'new') { throw 'Arızalı API' } }
            Expect-Error { Switch-DeliveryCopy $target $selection } 'önceki çalışan paket yeniden açıldı'
            Assert (($script:events -join ',') -eq 'verify:new,stop:old,start:new,stop:new,start:old') 'Kurtarma sırası'
            Assert ((Get-DeliverySelection).current -eq $a) 'Hatalı paket seçildi'
        }
        'failed_recovery' {
            Mock-Switch
            Set-DeliverySelection $a $null
            function Start-DeliveryCopy($Record) { throw 'Kapalı motor' }
            Expect-Error { Switch-DeliveryCopy $target $selection } 'önceki kopyanın açılışı başarısız'
            Assert ((Get-DeliverySelection).current -eq $a) 'Eski seçim korunmadı'
        }
        'failed_selection_write' {
            Mock-Switch
            function Set-DeliverySelection($Current, $Previous) { throw 'Disk dolu' }
            Expect-Error { Switch-DeliveryCopy $target $selection } 'önceki çalışan paket yeniden açıldı'
            Assert ($script:events[-1] -eq 'start:old') 'Seçim yazılamazsa kurtarma yapılmadı'
        }
        'healthy_start' {
            Mock-Start
            Start-DeliveryCopy $old
            Assert ($script:events.Count -eq 3) 'Sağlıklı servis yeniden oluşturuldu'
            Assert ($script:events[-1] -like '*app.delivery check*') 'Kopya denetlenmedi'
        }
        'recreate_pair' {
            Mock-Start
            $script:healthChecks = 0
            function Test-DeliveryHealthy($Record, $Services) { $script:healthChecks++; return ($script:healthChecks -gt 1) }
            Start-DeliveryCopy $old
            Assert ($script:events[-2] -eq 'stop ui api') 'Birlikte durdurulmadı'
            Assert ($script:events[-1] -like '*--no-build --pull never --force-recreate*api ui') 'Birlikte ve yerel imajla açılmadı'
        }
        'check_failure' {
            Mock-Start
            function Invoke-DeliveryCompose($Record, $ComposeArguments) { throw 'Dosya hash uyuşmazlığı' }
            Expect-Error { Start-DeliveryCopy $old } 'hash'
            Assert (($script:events -join ',') -eq 'verify,port') 'Kontrol öncesi servis değişti'
        }
        'port_conflict' {
            function Get-DeliveryListeners { return @([PSCustomObject]@{Port=8503}) }
            Expect-Error { Assert-DeliveryPort $old @{api=$null} } '8503'
            Assert-DeliveryPort $old @{api=@{Running=$true}}
        }
        'record_integrity' {
            $state = Join-Path (Get-DeliveryBase) $a
            $package = Join-Path $Root 'bundle'
            [IO.Directory]::CreateDirectory($state) | Out-Null
            [IO.Directory]::CreateDirectory($package) | Out-Null
            [IO.File]::WriteAllText((Join-Path $package 'manifest.json'), '{}')
            [IO.File]::WriteAllText((Join-Path $state 'compose.yaml'), 'fake')
            Write-DeliveryJson (Join-Path $state 'prepared.json') @{format_version=1; status='complete'; bundle_sha256=$a; project_name=('fiyat-takip-teslim-' + $a.Substring(0, 24)); database='fiyat_takip_test'; image_id=('sha256:' + $a); compose_sha256=$a; bundle_path=$package}
            Expect-Error { Read-DeliveryRecord $a } 'değişmiş'
            Expect-Error { Read-DeliveryRecord '../outside' } 'geçersiz'
        }
        'environment' {
            [Environment]::SetEnvironmentVariable('DELIVERY_DATABASE', 'original', 'Process')
            function Invoke-DeliveryDocker($DockerArguments) {
                Assert ($env:DELIVERY_IMAGE -eq $old.image_id) 'Etiket yerine imaj kimliği kullanılmalı'
                Assert ($env:DELIVERY_DATABASE -eq 'fiyat_takip_test') 'Yanlış DB'
                throw 'mock'
            }
            $old | Add-Member database 'fiyat_takip_test'
            $old | Add-Member bundle_path $Root
            Expect-Error { Invoke-DeliveryCompose $old @('up') } 'mock'
            Assert ($env:DELIVERY_DATABASE -eq 'original') 'Ortam geri yüklenmedi'
            Assert (-not $env:DELIVERY_IMAGE) 'Ortam sızıntısı'
        }
        'logs' {
            $secrets = Join-Path (Get-DeliveryBase) "$a/secrets"
            [IO.Directory]::CreateDirectory($secrets) | Out-Null
            [IO.File]::WriteAllText((Join-Path $secrets 'admin_password'), 'fake-admin')
            [IO.File]::WriteAllText((Join-Path $secrets 'api_password'), 'fake-reader')
            $safe = Protect-DeliveryLogs 'fake-admin fake-reader postgresql://user:other@db:5432/test' $old
            Assert ($safe -notmatch 'fake-admin|fake-reader|other') 'Log sırrı sızdı'
            Assert ($safe.Contains('[gizli]')) 'Maskeleme yok'
        }
        'half_prepared' {
            $package = Join-Path $Root 'bundle'
            [IO.Directory]::CreateDirectory($package) | Out-Null
            $manifest = Join-Path $package 'manifest.json'
            [IO.File]::WriteAllText($manifest, '{}')
            $digest = (Get-FileHash $manifest -Algorithm SHA256).Hash.ToLowerInvariant()
            [IO.Directory]::CreateDirectory((Join-Path (Get-DeliveryBase) $digest)) | Out-Null
            function Invoke-DeliveryDocker($DockerArguments) { throw 'Docker çağrılmamalı' }
            Expect-Error { New-DeliveryCopy $package 'fake:image' } 'Yarım hazırlık'
        }
    }
    Write-Output ('OK:' + $Case)
} catch { Write-Output $_.Exception.Message; exit 1 }
