param(
    [Parameter(Mandatory = $true)][ValidateSet('Export', 'Prepare', 'Start', 'Status', 'Logs', 'Stop', 'Rollback')][string]$Action,
    [string]$Bundle,
    [ValidatePattern('^[a-z0-9][a-z0-9_./:@-]*$')][string]$Image = 'fiyat-takip-teslim:local',
    [string]$Output,
    [ValidateRange(1, 1000)][int]$Lines = 100
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Console]::OutputEncoding
$script:DeliveryRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'teslim_ortak.ps1')
. (Join-Path $PSScriptRoot 'teslim_paket.ps1')
$gate = $null

try {
    if (($Action -eq 'Prepare') -ne [bool]$Bundle -or ($Output -and $Action -ne 'Export') -or
        ($PSBoundParameters.ContainsKey('Image') -and $Action -ne 'Prepare') -or ($PSBoundParameters.ContainsKey('Lines') -and $Action -ne 'Logs')) { throw [InvalidOperationException]::new('Bundle yalnız Prepare, Output yalnız Export, Image yalnız Prepare, Lines yalnız Logs ile kullanılır.') }
    if ($Action -eq 'Export') {
        if (-not $Output) { $Output = Join-Path $script:DeliveryRoot ('data/teslim/paketler/paket_' + (Get-Date -Format 'yyyyMMdd_HHmmss')) }
        $python = Join-Path $script:DeliveryRoot '.venv/Scripts/python.exe'
        if (-not (Test-Path -LiteralPath $python)) { throw [InvalidOperationException]::new('Export canlı Windows ortamındaki .venv ve PostgreSQL 17 araçlarını gerektirir.') }
        $Output = [IO.Path]::GetFullPath($Output)
        Push-Location $script:DeliveryRoot
        try { & $python -m app.delivery export --output $Output; $result = $LASTEXITCODE } finally { Pop-Location }
        exit $result
    }
    Assert-DeliveryEngine ($Action -in @('Prepare', 'Start', 'Rollback'))
    $gate = Open-DeliveryGate
    $selection = Get-DeliverySelection
    if ($Action -eq 'Prepare') {
        $record = New-DeliveryCopy $Bundle $Image
        Switch-DeliveryCopy $record $selection
    } else {
        if (-not $selection) { throw [InvalidOperationException]::new('Hazır paket seçilmedi. Önce Prepare -Bundle <PAKET_KLASORU> çalıştırın.') }
        $record = Read-DeliveryRecord $selection.current
        switch ($Action) {
            'Start' { Start-DeliveryCopy $record; Write-Host 'Uygulama hazır: http://127.0.0.1:8503' }
            'Stop' { Stop-DeliveryCopy $record; Write-Host 'Uygulama kapatıldı; paketler ve kalıcı veriler korundu.' }
            'Status' {
                Write-Host "Seçili paket: $($record.bundle_sha256)"
                Write-Host "Önceki paket: $($selection.previous)"
                $services = Get-DeliveryServices $record
                foreach ($name in @('db', 'api', 'ui')) {
                    $state = 'oluşturulmamış'
                    if ($services[$name]) { $state = if ($services[$name].Running) { 'çalışıyor / ' + $services[$name].Health } else { 'kapalı' } }
                    Write-Host "${name}: $state"
                }
                if (Test-DeliveryHealthy $record $services) { Write-Host 'Uygulama hazır: http://127.0.0.1:8503' }
            }
            'Logs' { Write-Host (Protect-DeliveryLogs (Invoke-DeliveryCompose $record @('logs', '--no-color', '--tail', $Lines.ToString(), 'db', 'api', 'ui')) $record) }
            'Rollback' {
                if (-not $selection.previous) { throw [InvalidOperationException]::new('Geri dönülecek önceki paket yok.') }
                $target = Read-DeliveryRecord $selection.previous
                Test-DeliveryCopy $target
                Switch-DeliveryCopy $target $selection
                Write-Host 'Önceki paket seçildi; kalıcı veriler korundu.'
            }
        }
    }
} catch {
    # Dosya/işletim sistemi hataları yol veya bağlantı ayrıntısı sızdırmamalı.
    $message = 'İşlem tamamlanmadı; dosya, izin veya bağlantı doğrulanamadı. Gizli ayrıntılar gösterilmedi.'
    if ($_.Exception -is [InvalidOperationException]) { $message = $_.Exception.Message }
    Write-Host ('Teslim: ' + $message)
    exit 1
} finally { if ($null -ne $gate) { $gate.Dispose() } }
