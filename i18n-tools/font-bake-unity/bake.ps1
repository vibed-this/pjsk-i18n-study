# Headless TMP font bake → i18n/font/source-han-fallback.bundle
$ErrorActionPreference = "Stop"
$Project = $PSScriptRoot
$RepoRoot = Resolve-Path (Join-Path $Project "..\..")  # i18n-tools/font-bake-unity → repo root

$Editors = @(
    "C:\Program Files\Unity\Hub\Editor\2022.3.62f3\Editor\Unity.exe",
    "C:\Program Files\Unity\Hub\Editor\2022.3.21f1\Editor\Unity.exe"
)
$Unity = $Editors | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Unity) {
    Write-Error "Unity 2022.3 not found. Install via Unity Hub."
}

$charset = Join-Path $RepoRoot "i18n\font\charset.txt"
$otf = Join-Path $RepoRoot "i18n-data\font\SourceHanSansSC-Regular.otf"
if (-not (Test-Path $charset)) {
    Write-Error "Missing $charset — run: uv run --project i18n-tools pjsk-i18n font-chars"
}
if (-not (Test-Path $otf)) {
    Write-Error "Missing $otf — download Source Han Sans SC Regular"
}

$log = Join-Path $Project "Logs\bake.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

Write-Host "[*] baking with $Unity"
& $Unity `
    -batchmode -nographics -quit `
    -projectPath $Project `
    -executeMethod PjskFontBake.Build `
    -logFile $log

if ($LASTEXITCODE -ne 0) {
    Write-Error "Unity bake failed (exit $LASTEXITCODE). See $log"
}

$out = Join-Path $RepoRoot "i18n\font\source-han-fallback.bundle"
if (-not (Test-Path $out)) {
    Write-Error "Bundle not found at $out"
}
Write-Host "[+] $out ($([math]::Round((Get-Item $out).Length / 1KB)) KiB)"