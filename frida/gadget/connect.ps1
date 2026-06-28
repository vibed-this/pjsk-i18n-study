# Connect Frida to gadget-patched PJSK on USB device
param(
    [ValidateSet("intercept", "monitor", "probe")]
    [string]$Mode = "intercept",
    [int]$Duration = 120,
    [string]$Prefix = "[TEST] ",
    [string]$SdkAdb = "D:\SDK\Android\platform-tools\adb.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path "$PSScriptRoot\..\.."

$serial = & $SdkAdb devices | Select-String "device$" | Where-Object { $_ -notmatch "emulator" } | ForEach-Object { ($_ -split "\s+")[0] } | Select-Object -First 1
if (-not $serial) {
    $serial = (& $SdkAdb devices | Select-String "device$" | ForEach-Object { ($_ -split "\s+")[0] } | Select-Object -First 1)
}
if (-not $serial) { throw "No adb device online" }

Write-Host "[*] device: $serial"
& $SdkAdb -s $serial forward tcp:27042 tcp:27042
Write-Host "[*] adb forward tcp:27042 -> device:27042"
Write-Host "[*] Launch PJSK on phone — app pauses until Frida connects (gadget on_load=wait)"
Write-Host "[*] mode=$Mode duration=${Duration}s"

Push-Location $RepoRoot
try {
    $args = @("frida/run.py", $Mode, "--duration", $Duration)
    if ($Mode -eq "intercept") {
        $args += @("--prefix", $Prefix)
    }
    if ($Mode -ne "probe") {
        $args += "--attach"
    }
    uv run python @args
} finally {
    Pop-Location
}