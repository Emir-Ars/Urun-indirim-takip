param(
    [Parameter(Mandatory = $true)][string]$Bundle,
    [ValidatePattern('^[a-z0-9][a-z0-9_./:@-]*$')][string]$Image = 'fiyat-takip-teslim:local'
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Console]::OutputEncoding
$deliveryRoot = Split-Path -Parent $PSScriptRoot
$deliveryGate = $null
$deliveryEnvironment = @{}

function Invoke-DeliveryDocker([string[]]$DockerArguments) {
    $ErrorActionPreference = 'Continue'
    $deliveryOutput = & docker --context desktop-linux @DockerArguments 2>&1
    $deliveryExit = $LASTEXITCODE
    if ($deliveryExit -ne 0) { throw 'Docker işlemi başarısız; veri ve parola ayrıntıları gösterilmedi.' }
    return (($deliveryOutput | ForEach-Object { $_.ToString() }) -join "`n")
}

function Read-DeliveryJson([string]$Text) {
    $deliveryJsonLines = @($Text -split "`n" | Where-Object { $_.Trim().StartsWith('{') -and $_.Trim().EndsWith('}') })
    if ($deliveryJsonLines.Count -ne 1) { throw 'Hazırlık komutunun cevabı doğrulanamadı.' }
    return ($deliveryJsonLines[0] | ConvertFrom-Json)
}

function Write-DeliverySecret([string]$Path) {
    $deliveryRandom = New-Object byte[] 32
    $deliveryGenerator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $deliveryGenerator.GetBytes($deliveryRandom) } finally { $deliveryGenerator.Dispose() }
    $deliveryPassword = [BitConverter]::ToString($deliveryRandom).Replace('-', '').ToLowerInvariant()
    [IO.File]::WriteAllText($Path, $deliveryPassword, [Text.UTF8Encoding]::new($false))
    $deliveryAcl = New-Object Security.AccessControl.FileSecurity
    $deliveryAcl.SetAccessRuleProtection($true, $false)
    $deliveryIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $deliveryAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($deliveryIdentity, 'FullControl', 'Allow'))
    $deliverySystem = [Security.Principal.SecurityIdentifier]::new('S-1-5-18')
    $deliveryAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($deliverySystem, 'FullControl', 'Allow'))
    Set-Acl -LiteralPath $Path -AclObject $deliveryAcl
    $deliveryPassword = $null
}

try {
    $deliveryBundleItem = Get-Item -LiteralPath $Bundle
    if (-not $deliveryBundleItem.PSIsContainer -or ($deliveryBundleItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Paket normal bir yerel klasör olmalı.'
    }
    $deliveryBundle = $deliveryBundleItem.FullName
    $deliveryEndpoint = (Invoke-DeliveryDocker @('context', 'inspect', 'desktop-linux', '--format', '{{.Endpoints.docker.Host}}')).Trim()
    if ($deliveryEndpoint -ne 'npipe:////./pipe/dockerDesktopLinuxEngine') { throw 'Yalnız yerel Docker Desktop Linux motoru kullanılabilir.' }
    if ((Invoke-DeliveryDocker @('info', '--format', '{{.OSType}}')).Trim() -ne 'linux') { throw 'Docker Linux motoru açık olmalı.' }
    Invoke-DeliveryDocker @('image', 'inspect', $Image) | Out-Null
    Write-Host '1/4 — Paket bütünlüğü, kod ve model doğrulanıyor.'
    $deliveryMount = "type=bind,source=$deliveryBundle,target=/bundle,readonly"
    $deliveryVerified = Read-DeliveryJson (Invoke-DeliveryDocker @('run', '--rm', '--network', 'none', '--read-only', '--tmpfs', '/tmp:mode=1777', '--mount', $deliveryMount, $Image, 'python', '-m', 'app.delivery', 'verify', '--bundle', '/bundle'))
    $deliveryDigest = $deliveryVerified.bundle_sha256
    if ($deliveryDigest -notmatch '^[0-9a-f]{64}$' -or $deliveryVerified.database -notmatch '^(fiyat_takip|[a-z][a-z0-9_]*_test)$') { throw 'Paket kimliği doğrulanamadı.' }
    $deliveryComposeConfig = Invoke-DeliveryDocker @('compose', '--project-directory', $deliveryRoot, '-f', (Join-Path $deliveryRoot 'compose.yaml'), 'config', '--format', 'json') | ConvertFrom-Json
    $deliveryPostgresImage = $deliveryComposeConfig.services.db.image
    if ($deliveryPostgresImage -notmatch '^postgres:17\.11-bookworm@sha256:[0-9a-f]{64}$') { throw 'PostgreSQL imajı sabit sözleşmeye uymuyor.' }
    Invoke-DeliveryDocker @('run', '--rm', '--network', 'none', '--read-only', '--mount', $deliveryMount, '--entrypoint', 'pg_restore', $deliveryPostgresImage, '--list', '/bundle/database.dump') | Out-Null
    $deliveryProject = 'fiyat-takip-teslim-' + $deliveryDigest.Substring(0, 24)
    $deliveryStateBase = Join-Path $deliveryRoot 'data\teslim'
    [IO.Directory]::CreateDirectory($deliveryStateBase) | Out-Null
    $deliveryGate = [IO.File]::Open((Join-Path $deliveryStateBase '.prepare.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $deliveryState = Join-Path $deliveryStateBase $deliveryDigest
    $deliveryReadyPath = Join-Path $deliveryState 'prepared.json'
    $deliveryAlreadyReady = Test-Path -LiteralPath $deliveryReadyPath
    if ((Test-Path -LiteralPath $deliveryState) -and -not $deliveryAlreadyReady) { throw 'Yarım hazırlık saklanıyor; mevcut alanın üzerine yazılmadı.' }
    if (-not $deliveryAlreadyReady) {
        foreach ($deliveryResource in @('container', 'volume', 'network')) {
            if ((Invoke-DeliveryDocker @($deliveryResource, 'ls', '-q', '--filter', "label=com.docker.compose.project=$deliveryProject")).Trim()) {
                throw 'Bu paket adına ait Docker alanı zaten var; üzerine yazılmadı.'
            }
        }
        [IO.Directory]::CreateDirectory((Join-Path $deliveryState 'secrets')) | Out-Null
        Write-DeliverySecret (Join-Path $deliveryState 'secrets\admin_password')
        Write-DeliverySecret (Join-Path $deliveryState 'secrets\api_password')
    } else {
        $deliveryPrevious = Get-Content -Raw -Encoding UTF8 -LiteralPath $deliveryReadyPath | ConvertFrom-Json
        if ($deliveryPrevious.bundle_sha256 -ne $deliveryDigest -or $deliveryPrevious.project_name -ne $deliveryProject) { throw 'Mevcut hazırlık başka pakete ait.' }
    }
    $deliveryValues = @{
        DELIVERY_STATE_DIR=$deliveryState; DELIVERY_BUNDLE_DIR=$deliveryBundle;
        DELIVERY_DATABASE=$deliveryVerified.database; DELIVERY_IMAGE=$Image;
        DELIVERY_API_USER=$(if ($deliveryVerified.database -eq 'fiyat_takip') { 'fiyat_takip_api' } else { 'fiyat_takip_api_test' })
    }
    foreach ($deliveryKey in $deliveryValues.Keys) {
        $deliveryEnvironment[$deliveryKey] = [Environment]::GetEnvironmentVariable($deliveryKey, 'Process')
        [Environment]::SetEnvironmentVariable($deliveryKey, $deliveryValues[$deliveryKey], 'Process')
    }
    $deliveryCompose = @('compose', '--project-directory', $deliveryRoot, '-f', (Join-Path $deliveryRoot 'compose.yaml'), '-p', $deliveryProject)
    Write-Host '2/4 — Pakete özel veritabanı hazırlanıyor.'
    Invoke-DeliveryDocker ($deliveryCompose + @('up', '-d', '--wait', '--wait-timeout', '90', 'db')) | Out-Null
    if ($deliveryAlreadyReady) {
        $deliveryReady = Read-DeliveryJson (Invoke-DeliveryDocker ($deliveryCompose + @('run', '--rm', '--no-deps', '-T', 'transfer', 'python', '-m', 'app.delivery', 'check', '--bundle', '/bundle')))
        Write-Host 'Mevcut kopya doğrulandı; veri yeniden yüklenmedi.'
    } else {
        Invoke-DeliveryDocker ($deliveryCompose + @('run', '--rm', '--no-deps', '-T', 'transfer', 'python', '-m', 'app.delivery', 'bootstrap', '--bundle', '/bundle')) | Out-Null
        $deliveryDatabaseId = (Invoke-DeliveryDocker ($deliveryCompose + @('ps', '-q', 'db'))).Trim()
        if ($deliveryDatabaseId -notmatch '^[0-9a-f]{64}$') { throw 'Docker hedef kimliği doğrulanamadı.' }
        Write-Host '3/4 — Arşiv yalnız Docker kopyasına yükleniyor.'
        Invoke-DeliveryDocker @('cp', (Join-Path $deliveryBundle 'database.dump'), "${deliveryDatabaseId}:/tmp/delivery.dump") | Out-Null
        $deliveryDumpSha = (Invoke-DeliveryDocker @('exec', $deliveryDatabaseId, 'sha256sum', '/tmp/delivery.dump')).Split(' ')[0]
        if ($deliveryDumpSha -ne $deliveryVerified.dump_sha256) { throw 'Kopyalanan DB arşivinin SHA değeri uyuşmuyor.' }
        Invoke-DeliveryDocker @('exec', '--user', 'postgres', $deliveryDatabaseId, 'pg_restore', '--host=/var/run/postgresql', '--username=postgres', "--dbname=$($deliveryVerified.database)", '--no-owner', '--no-privileges', '--role=fiyat_takip_owner', '--single-transaction', '--exit-on-error', '/tmp/delivery.dump') | Out-Null
        Invoke-DeliveryDocker @('exec', $deliveryDatabaseId, 'rm', '--', '/tmp/delivery.dump') | Out-Null
        Write-Host '4/4 — Veri eşleşmesi, okuma rolü ve dosyalar doğrulanıyor.'
        $deliveryReady = Read-DeliveryJson (Invoke-DeliveryDocker ($deliveryCompose + @('run', '--rm', '--no-deps', '-T', 'transfer', 'python', '-m', 'app.delivery', 'finalize', '--bundle', '/bundle')))
    }
    $deliveryReady | Add-Member -NotePropertyName project_name -NotePropertyValue $deliveryProject
    $deliveryReady | Add-Member -NotePropertyName bundle_path -NotePropertyValue $deliveryBundle
    $deliveryReady | Add-Member -NotePropertyName image -NotePropertyValue $Image
    if (-not $deliveryAlreadyReady) {
        $deliveryTemporary = Join-Path $deliveryState 'prepared.json.tmp'
        [IO.File]::WriteAllText($deliveryTemporary, ($deliveryReady | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
        [IO.File]::Move($deliveryTemporary, $deliveryReadyPath)
    }
    Write-Host "Hazır paket: $deliveryDigest"
    Write-Host "Docker projesi: $deliveryProject"
    Write-Host "Hazırlık kaydı: $deliveryReadyPath"
    Write-Host 'Kaynak DB değişmedi. Gösterim kapalı; ekran başlatılmadı.'
} catch {
    Write-Error ("Teslim hazırlığı tamamlanmadı: " + $_.Exception.Message) -ErrorAction Continue
    exit 1
} finally {
    foreach ($deliveryKey in $deliveryEnvironment.Keys) { [Environment]::SetEnvironmentVariable($deliveryKey, $deliveryEnvironment[$deliveryKey], 'Process') }
    if ($null -ne $deliveryGate) { $deliveryGate.Dispose() }
}
