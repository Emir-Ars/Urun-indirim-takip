param(
    [Parameter(Mandatory = $true)][string]$Bundle,
    [ValidatePattern('^[a-z0-9][a-z0-9_./:@-]*$')][string]$Image = 'fiyat-takip-teslim:local'
)

# Eski giriş aynı hazırlama koduna yönlenir; iki geri yükleme yolu tutulmaz.
& (Join-Path $PSScriptRoot 'teslim.ps1') -Action Prepare -Bundle $Bundle -Image $Image
exit $LASTEXITCODE
