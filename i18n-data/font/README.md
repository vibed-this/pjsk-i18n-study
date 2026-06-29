# 思源黑体 TMP 字体烘焙

日服客户端使用 TMP `DB`/`EB` 字体，不含完整简体字形。Mod 用 **思源黑体 SC** 生成 `TMP_FontAsset`，运行时**替换**主字体。

## 1. 导出字符集

```powershell
cd E:\GithubRepos\pjsk-i18n-mod
uv run --project i18n-tools pjsk-i18n font-chars
```

产物：`i18n/font/charset.txt`

## 2. 思源 OTF

`i18n-data/font/SourceHanSansSC-Regular.otf`（不提交 git）

## 3. Unity 烘焙

项目路径（Hub 添加此文件夹）：

```
i18n-tools/font-bake-unity
```

（与 `unity-example/PJSK-Bake-Font` 同源，任选其一在 Hub 打开。）

```powershell
cd i18n-tools\font-bake-unity
.\bake.ps1
```

或 Hub 打开项目 → **PJSK → Font Bake (local)**

产物：`i18n/font/source-han-fallback.bundle`  
资产名：`SourceHanSansSC-Regular SDF`

## 4. 真机注入

```powershell
uv run python frida/run.py font --inject --duration 180
uv run python frida/run.py intercept --font-inject --duration 120
```