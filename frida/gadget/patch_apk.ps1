# Patch PJSK split APKs with frida-gadget (arm64, listen @ 127.0.0.1:27042)
param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [string]$SdkRoot = "D:\SDK\Android"
)

$ErrorActionPreference = "Stop"

$ApkDir       = Join-Path $ProjectRoot "apk"
$GadgetDir    = $PSScriptRoot
$ToolsDir     = Join-Path $GadgetDir "tools"
$OutDir       = Join-Path $GadgetDir "out"
$DecodeDir    = Join-Path $OutDir "base"
$ApktoolJar   = Join-Path $ToolsDir "apktool.jar"
$GadgetSo     = Join-Path $ToolsDir "libfrida-gadget.so"
$GadgetCfg    = Join-Path $GadgetDir "libfrida-gadget.config.so"
$Keystore     = Join-Path $ToolsDir "debug.keystore"
$BuildTools   = Join-Path $SdkRoot "build-tools\36.0.0"
$Zipalign     = Join-Path $BuildTools "zipalign.exe"
$Apksigner    = Join-Path $BuildTools "apksigner.bat"

$BaseApk      = Join-Path $ApkDir "base.apk"
$SplitArm     = Join-Path $ApkDir "split_config.arm64_v8a.apk"
$SplitData    = Join-Path $ApkDir "split_UnityDataAssetPack.apk"

$OutBase      = Join-Path $OutDir "base.gadget.apk"
$OutSplitArm  = Join-Path $OutDir "split_config.arm64_v8a.gadget.apk"
$OutSplitData = Join-Path $OutDir "split_UnityDataAssetPack.apk"

function Ensure-File($path, $label) {
    if (-not (Test-Path $path)) { throw "Missing $label : $path" }
}

Ensure-File $BaseApk "base.apk"
Ensure-File $SplitArm "arm64 split"
Ensure-File $ApktoolJar "apktool"
Ensure-File $GadgetSo "libfrida-gadget.so"
Ensure-File $GadgetCfg "gadget config"
Ensure-File $Zipalign "zipalign"
Ensure-File $Apksigner "apksigner"

New-Item -ItemType Directory -Force -Path $OutDir, $ToolsDir | Out-Null

if (-not (Test-Path $Keystore)) {
    Write-Host "[*] generating debug.keystore"
    & keytool -genkeypair -v `
        -keystore $Keystore -storepass android -alias androiddebugkey -keypass android `
        -keyalg RSA -keysize 2048 -validity 10000 `
        -dname "CN=Android Debug,O=Android,C=US"
}

if (-not (Test-Path (Join-Path $DecodeDir "apktool.yml"))) {
    Write-Host "[*] decoding base.apk"
    & java -jar $ApktoolJar d -f -o $DecodeDir $BaseApk
}

$Smali = Join-Path $DecodeDir "smali_classes8\com\google\firebase\MessagingUnityPlayerActivity.smali"
Ensure-File $Smali "MessagingUnityPlayerActivity.smali"

$text = Get-Content $Smali -Raw
if ($text -notmatch 'frida-gadget') {
    Write-Host "[*] injecting System.loadLibrary(frida-gadget)"
    $text = $text -replace '\.method protected onCreate\(Landroid/os/Bundle;\)V\s*\r?\n\s*\.locals 1',
@'
.method protected onCreate(Landroid/os/Bundle;)V
    .locals 2

    const-string v1, "frida-gadget"
    invoke-static {v1}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
'@
    Set-Content -Path $Smali -Value $text -NoNewline
} else {
    Write-Host "[*] smali already patched"
}

Write-Host "[*] rebuilding base.apk"
$BaseUnsigned = Join-Path $OutDir "base.unsigned.apk"
if (Test-Path $BaseUnsigned) { Remove-Item $BaseUnsigned -Force }
& java -jar $ApktoolJar b -o $BaseUnsigned $DecodeDir

Write-Host "[*] patching arm64 split with gadget libs"
$SplitUnsigned = Join-Path $OutDir "split.arm64.unsigned.apk"
Copy-Item $SplitArm $SplitUnsigned -Force
python -c @"
import zipfile, pathlib
apk = pathlib.Path(r'$SplitUnsigned')
so  = pathlib.Path(r'$GadgetSo')
cfg = pathlib.Path(r'$GadgetCfg')
with zipfile.ZipFile(apk, 'a', compression=zipfile.ZIP_STORED) as zf:
    for src, arc in [(so, 'lib/arm64-v8a/libfrida-gadget.so'), (cfg, 'lib/arm64-v8a/libfrida-gadget.config.so')]:
        if arc not in [i.filename for i in zf.infolist()]:
            zf.write(src, arc)
            print('added', arc)
        else:
            print('exists', arc)
"@

function Sign-Apk($unsigned, $aligned, $signed) {
    if (Test-Path $aligned) { Remove-Item $aligned -Force }
    if (Test-Path $signed) { Remove-Item $signed -Force }
    & $Zipalign -f 4 $unsigned $aligned
    Copy-Item $aligned $signed -Force
    & $Apksigner sign --ks $Keystore --ks-pass pass:android --key-pass pass:android --ks-key-alias androiddebugkey $signed
    & $Apksigner verify --verbose $signed | Out-Null
}

$BaseAligned = Join-Path $OutDir "base.aligned.apk"
$SplitAligned = Join-Path $OutDir "split.arm64.aligned.apk"

Sign-Apk $BaseUnsigned $BaseAligned $OutBase
Sign-Apk $SplitUnsigned $SplitAligned $OutSplitArm

$DataUnsigned = Join-Path $OutDir "split.data.unsigned.apk"
$DataAligned  = Join-Path $OutDir "split.data.aligned.apk"
Copy-Item $SplitData $DataUnsigned -Force
Sign-Apk $DataUnsigned $DataAligned $OutSplitData

Write-Host "[+] patched APKs:"
Write-Host "    $OutBase"
Write-Host "    $OutSplitArm"
Write-Host "    $OutSplitData"
Write-Host "[*] install: adb install-multiple -r `"$OutBase`" `"$OutSplitArm`" `"$OutSplitData`""