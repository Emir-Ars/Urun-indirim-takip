function Invoke-DeliveryDocker([string[]]$DockerArguments) {
    $ErrorActionPreference = 'Continue'
    $result = & docker --context desktop-linux @DockerArguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw [InvalidOperationException]::new('Docker işlemi başarısız. Status ve Logs ile kontrol edin; gizli hata ayrıntıları gösterilmedi.') }
    return (($result | ForEach-Object { $_.ToString() }) -join "`n")
}

function Read-DeliveryJson([string]$Text) {
    $lines = @($Text -split "`n" | Where-Object { $_.Trim().StartsWith('{') -and $_.Trim().EndsWith('}') })
    if ($lines.Count -ne 1) { throw [InvalidOperationException]::new('Docker doğrulama cevabı okunamadı.') }
    return ($lines[0] | ConvertFrom-Json)
}

function Get-DeliveryBase { return (Join-Path $script:DeliveryRoot 'data/teslim') }

function Open-DeliveryGate {
    [IO.Directory]::CreateDirectory((Get-DeliveryBase)) | Out-Null
    try { return [IO.File]::Open((Join-Path (Get-DeliveryBase) '.prepare.lock'), 'OpenOrCreate', 'ReadWrite', 'None') } catch { throw [InvalidOperationException]::new('Başka bir teslim işlemi sürüyor; bekleyip tekrar deneyin.') }
}

function Write-DeliveryJson([string]$Path, $Value) {
    $temporary = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    try {
        [IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
        if ([IO.File]::Exists($Path)) {
            # PS 5.1 boş yedek yolunu null'a çevirmediği için gerçek bir geçici yedek kullanılır.
            $backup = $temporary + '.bak'
            [IO.File]::Replace($temporary, $Path, $backup)
            [IO.File]::Delete($backup)
        } else { [IO.File]::Move($temporary, $Path) }
    } finally { if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) } }
}

function Get-DeliverySelection {
    $path = Join-Path (Get-DeliveryBase) 'selection.json'
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $value = Get-Content -Raw -Encoding UTF8 -LiteralPath $path | ConvertFrom-Json
    if ($value.format_version -ne 1 -or $value.current -cnotmatch '^[0-9a-f]{64}$' -or
        ($null -ne $value.previous -and $value.previous -cnotmatch '^[0-9a-f]{64}$') -or
        $value.current -eq $value.previous) { throw [InvalidOperationException]::new('Paket seçim kaydı geçersiz; otomatik seçim yapılmadı.') }
    return $value
}

function Set-DeliverySelection([string]$Current, $Previous) {
    if ($Current -cnotmatch '^[0-9a-f]{64}$' -or
        ($null -ne $Previous -and $Previous -cnotmatch '^[0-9a-f]{64}$') -or $Current -eq $Previous) { throw [InvalidOperationException]::new('Paket seçimi geçersiz.') }
    Write-DeliveryJson (Join-Path (Get-DeliveryBase) 'selection.json') ([ordered]@{format_version=1; current=$Current; previous=$Previous})
}

function Assert-DeliveryEngine([bool]$Launch) {
    if (-not [Environment]::Is64BitOperatingSystem -or [Environment]::OSVersion.Platform -ne 'Win32NT') { throw [InvalidOperationException]::new('Teslim komutu Windows x64 ve Docker Desktop Linux motoru gerektirir.') }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw [InvalidOperationException]::new('Docker Desktop bulunamadı. İlk kurulum rehberini izleyin.') }
    $endpoint = (Invoke-DeliveryDocker @('context', 'inspect', 'desktop-linux', '--format', '{{.Endpoints.docker.Host}}')).Trim()
    if ($endpoint -ne 'npipe:////./pipe/dockerDesktopLinuxEngine') { throw [InvalidOperationException]::new('Yalnız yerel Docker Desktop Linux motoru kullanılabilir.') }
    try { $kind = (Invoke-DeliveryDocker @('info', '--format', '{{.OSType}}')).Trim() } catch {
        if (-not $Launch) { throw [InvalidOperationException]::new('Docker motoru kapalı. Açmak için Start çalıştırın.') }
        $binary = (Get-Command docker).Source
        $candidates = @((Join-Path (Split-Path (Split-Path (Split-Path $binary))) 'Docker Desktop.exe'), (Join-Path $env:ProgramFiles 'Docker/Docker/Docker Desktop.exe'))
        $desktop = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if (-not $desktop) { throw [InvalidOperationException]::new('Docker Desktop uygulaması bulunamadı; kendiniz açıp tekrar deneyin.') }
        Start-Process -FilePath $desktop -WindowStyle Hidden
        Write-Host 'Docker Desktop açılıyor; Linux motoru bekleniyor.'
        $deadline = [DateTime]::UtcNow.AddSeconds(120)
        do {
            Start-Sleep -Seconds 3
            try { $kind = (Invoke-DeliveryDocker @('info', '--format', '{{.OSType}}')).Trim() } catch { $kind = '' }
        } while (-not $kind -and [DateTime]::UtcNow -lt $deadline)
    }
    if ($kind -ne 'linux') { throw [InvalidOperationException]::new('Docker Linux motoru hazır değil. Docker Desktop WSL2 ayarını kontrol edin.') }
}

function Write-DeliverySecret([string]$Path) {
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    [IO.File]::WriteAllText($Path, [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant(), [Text.UTF8Encoding]::new($false))
    $acl = New-Object Security.AccessControl.FileSecurity
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.WindowsIdentity]::GetCurrent().User, 'FullControl', 'Allow'))
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-5-18'), 'FullControl', 'Allow'))
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Invoke-DeliveryCompose($Record, [string[]]$ComposeArguments) {
    $state = Join-Path (Get-DeliveryBase) $Record.bundle_sha256
    $values = @{
        DELIVERY_STATE_DIR=$state; DELIVERY_BUNDLE_DIR=$Record.bundle_path;
        DELIVERY_DATABASE=$Record.database; DELIVERY_IMAGE=$Record.image_id;
        DELIVERY_API_USER=$(if ($Record.database -eq 'fiyat_takip') { 'fiyat_takip_api' } else { 'fiyat_takip_api_test' })
    }
    $saved = @{}
    try {
        foreach ($key in $values.Keys) {
            $saved[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
            [Environment]::SetEnvironmentVariable($key, $values[$key], 'Process')
        }
        return (Invoke-DeliveryDocker (@('compose', '--project-directory', $script:DeliveryRoot, '-f', (Join-Path $state 'compose.yaml'), '-p', $Record.project_name) + $ComposeArguments))
    } finally {
        foreach ($key in $saved.Keys) { [Environment]::SetEnvironmentVariable($key, $saved[$key], 'Process') }
    }
}

function Read-DeliveryRecord([string]$Digest) {
    if ($Digest -cnotmatch '^[0-9a-f]{64}$') { throw [InvalidOperationException]::new('Paket kimliği geçersiz.') }
    $state = Join-Path (Get-DeliveryBase) $Digest
    $record = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $state 'prepared.json') | ConvertFrom-Json
    if ($record.bundle_sha256 -cne $Digest -or $record.project_name -cne ('fiyat-takip-teslim-' + $Digest.Substring(0, 24)) -or
        $record.status -cne 'complete' -or $record.format_version -ne 1 -or
        $record.database -cnotmatch '^(fiyat_takip|[a-z][a-z0-9_]*_test)$' -or
        $record.image_id -cnotmatch '^sha256:[0-9a-f]{64}$' -or $record.compose_sha256 -cnotmatch '^[0-9a-f]{64}$') { throw [InvalidOperationException]::new('Hazırlık kaydı geçersiz. Önce Prepare ile doğrulayın.') }
    foreach ($path in @($state, (Join-Path $state 'compose.yaml'), $record.bundle_path, (Join-Path $record.bundle_path 'manifest.json'))) {
        if ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw [InvalidOperationException]::new('Teslim dosyası veya klasörü bağlantı olamaz.') }
    }
    if ((Get-FileHash -LiteralPath (Join-Path $state 'compose.yaml') -Algorithm SHA256).Hash.ToLowerInvariant() -cne $record.compose_sha256 -or
        (Get-FileHash -LiteralPath (Join-Path $record.bundle_path 'manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant() -cne $Digest) { throw [InvalidOperationException]::new('Paket veya sabit Compose dosyası değişmiş; işlem durduruldu.') }
    return $record
}

function Get-DeliveryServices($Record) {
    $result = @{}
    foreach ($service in @('db', 'api', 'ui')) {
        $id = (Invoke-DeliveryDocker @('ps', '-aq', '--filter', "label=com.docker.compose.project=$($Record.project_name)", '--filter', "label=com.docker.compose.service=$service")).Trim()
        if (-not $id) { $result[$service] = $null; continue }
        if ($id -notmatch '^[0-9a-f]{12,64}$') { throw [InvalidOperationException]::new('Servis kimliği tekil değil.') }
        $container = @(Invoke-DeliveryDocker @('inspect', $id) | ConvertFrom-Json)[0]
        $result[$service] = [PSCustomObject]@{Id=$container.Id; Image=$container.Image; Running=$container.State.Running; Health=$container.State.Health.Status; Network=$container.HostConfig.NetworkMode}
    }
    return $result
}

function Test-DeliveryHealthy($Record, $Services) {
    foreach ($service in @('db', 'api', 'ui')) {
        if (-not $Services[$service] -or -not $Services[$service].Running -or $Services[$service].Health -ne 'healthy') { return $false }
    }
    return ($Services.api.Image -ceq $Record.image_id -and $Services.ui.Image -ceq $Record.image_id -and $Services.ui.Network -ceq ('container:' + $Services.api.Id))
}

function Get-DeliveryListeners {
    return [Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
}

function Assert-DeliveryPort($Record, $Services) {
    $busy = @(Get-DeliveryListeners | Where-Object { $_.Port -eq 8503 }).Count -gt 0
    if ($busy -and -not ($Services.api -and $Services.api.Running)) { throw [InvalidOperationException]::new('8503 portu başka bir uygulama tarafından kullanılıyor; bu uygulama kapatılmadı.') }
}

function Test-DeliveryCopy($Record) {
    $image = (Invoke-DeliveryDocker @('image', 'inspect', $Record.image_id, '--format', '{{.Id}}')).Trim()
    if ($image -cne $Record.image_id) { throw [InvalidOperationException]::new('Sabit uygulama imajı yerelde yok. Prepare ile tekrar hazırlayın.') }
    $mount = "type=bind,source=$($Record.bundle_path),target=/bundle,readonly"
    $verified = Read-DeliveryJson (Invoke-DeliveryDocker @('run', '--rm', '--pull', 'never', '--network', 'none', '--read-only', '--tmpfs', '/tmp:mode=1777', '--mount', $mount, $Record.image_id, 'python', '-m', 'app.delivery', 'verify', '--bundle', '/bundle'))
    if ($verified.bundle_sha256 -cne $Record.bundle_sha256 -or $verified.code_sha256 -cne $Record.code_sha256 -or $verified.database -cne $Record.database) { throw [InvalidOperationException]::new('Hazırlanan kopya paketle eşleşmiyor.') }
}

function Start-DeliveryCopy($Record) {
    Test-DeliveryCopy $Record
    $services = Get-DeliveryServices $Record
    Assert-DeliveryPort $Record $services
    if (-not ($services.db -and $services.db.Running -and $services.db.Health -eq 'healthy')) {
        Invoke-DeliveryCompose $Record @('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '120', 'db') | Out-Null
    }
    Invoke-DeliveryCompose $Record @('run', '--rm', '--no-deps', '--pull', 'never', '-T', 'transfer', 'python', '-m', 'app.delivery', 'check', '--bundle', '/bundle') | Out-Null
    if (Test-DeliveryHealthy $Record $services) { Write-Host 'Servisler zaten sağlıklı; yeniden oluşturulmadı.'; return }
    # UI, API'nin ağ alanını paylaştığından ikisi birlikte yenilenir.
    Invoke-DeliveryCompose $Record @('stop', 'ui', 'api') | Out-Null
    Invoke-DeliveryCompose $Record @('up', '-d', '--no-deps', '--no-build', '--pull', 'never', '--force-recreate', '--wait', '--wait-timeout', '120', 'api', 'ui') | Out-Null
    if (-not (Test-DeliveryHealthy $Record (Get-DeliveryServices $Record))) { throw [InvalidOperationException]::new('DB, API ve ekranın sağlık kontrolü tamamlanmadı.') }
}

function Stop-DeliveryCopy($Record, [bool]$Database = $true) {
    $services = @('ui', 'api')
    if ($Database) { $services += 'db' }
    Invoke-DeliveryCompose $Record (@('stop') + $services) | Out-Null
}

function Switch-DeliveryCopy($Target, $Selection) {
    $old = $null
    $running = $false
    if ($null -ne $Selection) {
        if ($Selection.current -ceq $Target.bundle_sha256) { Write-Host 'Aynı paket seçili; seçim geçmişi değiştirilmedi.'; return }
        $old = Read-DeliveryRecord $Selection.current
        $services = Get-DeliveryServices $old
        $running = ($services.api -and $services.api.Running) -or ($services.ui -and $services.ui.Running)
    }
    if (-not $running) {
        Set-DeliverySelection $Target.bundle_sha256 $(if ($old) { $old.bundle_sha256 } else { $null })
        Write-Host 'Paket seçildi. Ekranı açmak için Start çalıştırın.'
        return
    }
    Test-DeliveryCopy $Target
    try {
        Stop-DeliveryCopy $old $false
        Start-DeliveryCopy $Target
        Set-DeliverySelection $Target.bundle_sha256 $old.bundle_sha256
    } catch {
        try { Stop-DeliveryCopy $Target $true; Start-DeliveryCopy $old } catch { throw [InvalidOperationException]::new('Paket geçişi ve önceki kopyanın açılışı başarısız. Seçim eski pakette; Status/Logs ile kontrol edip Start çalıştırın. Kalıcı veriler korundu.') }
        throw [InvalidOperationException]::new('Yeni paket açılamadı; önceki çalışan paket yeniden açıldı. Seçim ve kalıcı veriler korundu.')
    }
    try { Stop-DeliveryDatabase $old } catch { Write-Host 'Yeni paket sağlıklı. Önceki paketin DB servisi kapatılamadı; kalıcı veriler korundu.' }
}

function Stop-DeliveryDatabase($Record) {
    Invoke-DeliveryCompose $Record @('stop', 'db') | Out-Null
}

function Protect-DeliveryLogs([string]$Text, $Record) {
    $state = Join-Path (Get-DeliveryBase) $Record.bundle_sha256
    foreach ($name in @('admin_password', 'api_password')) {
        $secret = [IO.File]::ReadAllText((Join-Path $state "secrets/$name")).Trim()
        if ($secret) { $Text = $Text.Replace($secret, '[gizli]') }
    }
    return [regex]::Replace($Text, '(?i)(postgres(?:ql)?://[^\s:/]+:)[^@\s]+@', '$1[gizli]@')
}
