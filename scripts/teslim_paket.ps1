function New-DeliveryCopy([string]$Bundle, [string]$Image) {
    $item = Get-Item -LiteralPath $Bundle
    if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $item.FullName.Contains(',')) { throw [InvalidOperationException]::new('Paket normal bir yerel klasör olmalı; yol virgül içeremez.') }
    $bundlePath = $item.FullName
    $digest = (Get-FileHash -LiteralPath (Join-Path $bundlePath 'manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    $state = Join-Path (Get-DeliveryBase) $digest
    $readyPath = Join-Path $state 'prepared.json'
    $existing = Test-Path -LiteralPath $readyPath
    if ((Test-Path -LiteralPath $state) -and -not $existing) { throw [InvalidOperationException]::new('Yarım hazırlık saklanıyor; mevcut alanın üzerine yazılmadı.') }
    $old = $null
    if ($existing) {
        $old = Get-Content -Raw -Encoding UTF8 -LiteralPath $readyPath | ConvertFrom-Json
        if ($old.bundle_sha256 -cne $digest -or $old.project_name -cne ('fiyat-takip-teslim-' + $digest.Substring(0, 24))) { throw [InvalidOperationException]::new('Mevcut hazırlık başka pakete ait.') }
        if ($old.image_id) { $Image = $old.image_id } else { $Image = $old.image }
    }
    $header = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $bundlePath 'manifest.json') | ConvertFrom-Json
    $rebuild = $false
    try {
        $imageId = (Invoke-DeliveryDocker @('image', 'inspect', $Image, '--format', '{{.Id}}')).Trim()
        $code = (Invoke-DeliveryDocker @('run', '--rm', '--pull', 'never', '--network', 'none', '--read-only', $imageId, 'python', '-c', 'from app.delivery.bundle import code_sha256; print(code_sha256())')).Trim()
        $rebuild = $code -cne $header.code_sha256
    } catch { $rebuild = $true }
    if ($rebuild) {
        if ($Image -cne 'fiyat-takip-teslim:local' -or $existing) { throw [InvalidOperationException]::new('Pakete uygun sabit uygulama imajı yok. İmajı geri yükleyin; mevcut kopya değiştirilmedi.') }
        Write-Host 'İlk hazırlık: uygulama imajı oluşturuluyor; internet gerekebilir.'
        Invoke-DeliveryDocker @('build', '--file', (Join-Path $script:DeliveryRoot 'Dockerfile'), '--tag', $Image, $script:DeliveryRoot) | Out-Null
        $imageId = (Invoke-DeliveryDocker @('image', 'inspect', $Image, '--format', '{{.Id}}')).Trim()
    }
    if ($imageId -cnotmatch '^sha256:[0-9a-f]{64}$') { throw [InvalidOperationException]::new('İmaj kimliği doğrulanamadı.') }
    Write-Host '1/4 — Paket, model ve kod doğrulanıyor.'
    $mount = "type=bind,source=$bundlePath,target=/bundle,readonly"
    $verified = Read-DeliveryJson (Invoke-DeliveryDocker @('run', '--rm', '--pull', 'never', '--network', 'none', '--read-only', '--tmpfs', '/tmp:mode=1777', '--mount', $mount, $imageId, 'python', '-m', 'app.delivery', 'verify', '--bundle', '/bundle'))
    if ($verified.bundle_sha256 -cne $digest -or $verified.database -cnotmatch '^(fiyat_takip|[a-z][a-z0-9_]*_test)$') { throw [InvalidOperationException]::new('Paket kimliği doğrulanamadı.') }
    if ($existing -and $old.image_id) {
        $record = Read-DeliveryRecord $digest
        if ($record.bundle_path -ine $bundlePath) { throw [InvalidOperationException]::new('Bu paket başka bir klasörden hazırlanmış; mevcut kayıt değiştirilmedi.') }
    } else {
        if (-not $existing) {
            foreach ($resource in @('container', 'volume', 'network')) {
                if ((Invoke-DeliveryDocker @($resource, 'ls', '-q', '--filter', ('label=com.docker.compose.project=fiyat-takip-teslim-' + $digest.Substring(0, 24)))).Trim()) { throw [InvalidOperationException]::new('Bu paket adına ait Docker alanı zaten var; üzerine yazılmadı.') }
            }
        }
        $postgres = [regex]::Match([IO.File]::ReadAllText((Join-Path $script:DeliveryRoot 'compose.yaml')), 'postgres:17\.11-bookworm@sha256:[0-9a-f]{64}').Value
        if (-not $postgres) { throw [InvalidOperationException]::new('Sabit PostgreSQL imajı Compose içinde bulunamadı.') }
        try { Invoke-DeliveryDocker @('image', 'inspect', $postgres) | Out-Null } catch {
            Write-Host 'İlk hazırlık: sabit PostgreSQL imajı indiriliyor.'
            Invoke-DeliveryDocker @('pull', '--platform', 'linux/amd64', $postgres) | Out-Null
        }
        Invoke-DeliveryDocker @('run', '--rm', '--pull', 'never', '--network', 'none', '--read-only', '--mount', $mount, '--entrypoint', 'pg_restore', $postgres, '--list', '/bundle/database.dump') | Out-Null
        [IO.Directory]::CreateDirectory($state) | Out-Null
        if (-not $existing) {
            [IO.Directory]::CreateDirectory((Join-Path $state 'secrets')) | Out-Null
            Write-DeliverySecret (Join-Path $state 'secrets/admin_password')
            Write-DeliverySecret (Join-Path $state 'secrets/api_password')
        }
        $composePath = Join-Path $state 'compose.yaml'
        if (Test-Path -LiteralPath $composePath) { throw [InvalidOperationException]::new('Sabit Compose dosyası zaten var; üzerine yazılmadı.') }
        [IO.File]::Copy((Join-Path $script:DeliveryRoot 'compose.yaml'), $composePath)
        $record = [PSCustomObject]@{
            bundle_sha256=$digest; bundle_path=$bundlePath; project_name=('fiyat-takip-teslim-' + $digest.Substring(0, 24));
            database=$verified.database; image=$Image; image_id=$imageId; code_sha256=$verified.code_sha256;
            compose_sha256=(Get-FileHash -LiteralPath $composePath -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    Write-Host '2/4 — Pakete özel veritabanı bekleniyor.'
    Invoke-DeliveryCompose $record @('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '120', 'db') | Out-Null
    if ($existing) {
        $ready = Read-DeliveryJson (Invoke-DeliveryCompose $record @('run', '--rm', '--no-deps', '--pull', 'never', '-T', 'transfer', 'python', '-m', 'app.delivery', 'check', '--bundle', '/bundle'))
        Write-Host 'Mevcut kopya doğrulandı; veri yeniden yüklenmedi.'
    } else {
        Invoke-DeliveryCompose $record @('run', '--rm', '--no-deps', '--pull', 'never', '-T', 'transfer', 'python', '-m', 'app.delivery', 'bootstrap', '--bundle', '/bundle') | Out-Null
        $databaseId = (Invoke-DeliveryCompose $record @('ps', '-q', 'db')).Trim()
        if ($databaseId -notmatch '^[0-9a-f]{64}$') { throw [InvalidOperationException]::new('Docker hedef kimliği doğrulanamadı.') }
        Write-Host '3/4 — Arşiv yalnız Docker kopyasına yükleniyor.'
        Invoke-DeliveryDocker @('cp', (Join-Path $bundlePath 'database.dump'), "${databaseId}:/tmp/delivery.dump") | Out-Null
        $dumpSha = (Invoke-DeliveryDocker @('exec', $databaseId, 'sha256sum', '/tmp/delivery.dump')).Split(' ')[0]
        if ($dumpSha -cne $verified.dump_sha256) { throw [InvalidOperationException]::new('Kopyalanan DB arşivinin SHA değeri uyuşmuyor.') }
        Invoke-DeliveryDocker @('exec', '--user', 'postgres', $databaseId, 'pg_restore', '--host=/var/run/postgresql', '--username=postgres', "--dbname=$($verified.database)", '--no-owner', '--no-privileges', '--role=fiyat_takip_owner', '--single-transaction', '--exit-on-error', '/tmp/delivery.dump') | Out-Null
        Invoke-DeliveryDocker @('exec', $databaseId, 'rm', '--', '/tmp/delivery.dump') | Out-Null
        Write-Host '4/4 — Veri, SELECT rolü ve resmi dosyalar karşılaştırılıyor.'
        $ready = Read-DeliveryJson (Invoke-DeliveryCompose $record @('run', '--rm', '--no-deps', '--pull', 'never', '-T', 'transfer', 'python', '-m', 'app.delivery', 'finalize', '--bundle', '/bundle'))
    }
    foreach ($name in @('bundle_sha256', 'database', 'code_sha256')) {
        if ($ready.$name -cne $record.$name) { throw [InvalidOperationException]::new('Kopyanın tamamlanma kaydı paketle eşleşmiyor.') }
    }
    if (-not $existing -or -not $old.image_id) {
        foreach ($name in @('project_name', 'bundle_path', 'image', 'image_id', 'compose_sha256')) { $ready | Add-Member -NotePropertyName $name -NotePropertyValue $record.$name }
        Write-DeliveryJson $readyPath $ready
    }
    Write-Host "Hazır paket: $digest"
    return (Read-DeliveryRecord $digest)
}
