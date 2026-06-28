# Install gadget-patched PJSK to connected device
param(
    [string]$SdkAdb = "D:\SDK\Android\platform-tools\adb.exe"
)

$OutDir = Join-Path $PSScriptRoot "out"
$base   = Join-Path $OutDir "base.gadget.apk"
$arm    = Join-Path $OutDir "split_config.arm64_v8a.gadget.apk"
$data   = Join-Path $OutDir "split_UnityDataAssetPack.apk"

foreach ($f in @($base, $arm, $data)) {
    if (-not (Test-Path $f)) { throw "Missing $f — run patch_apk.ps1 first" }
}

$serial = & $SdkAdb devices | Select-String "device$" | ForEach-Object { ($_ -split "\s+")[0] } | Select-Object -First 1
if (-not $serial) { throw "No adb device" }

Write-Host "[*] uninstall old build (ignore errors)"
& $SdkAdb -s $serial uninstall com.sega.pjsekai 2>$null

Write-Host "[*] installing split APKs to $serial"
& $SdkAdb -s $serial install-multiple -r --no-incremental $base $arm $data
Write-Host "[+] done — run connect.ps1 and launch the game"