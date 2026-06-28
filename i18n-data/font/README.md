# 思源黑体 TMP 字体烘焙

日服客户端使用 TMP `DB`/`EB` 字体，不含完整简体字形。Mod 用 **思源黑体 SC**（`Source Han Sans SC`）生成 `TMP_FontAsset`，运行时挂到 fallback 链。

## 1. 导出字符集

```powershell
cd E:\GithubRepos\pjsk-i18n-mod
uv run --project i18n-tools pjsk-i18n font-chars
```

产物：`i18n/font/charset.txt`（来自 wordings + plain-text + story）

## 2. 下载思源黑体

从 [Adobe Source Han Sans](https://github.com/adobe-fonts/source-han-sans/releases) 下载  
`SourceHanSansSC-Regular.otf`，放到：

```
i18n-data/font/SourceHanSansSC-Regular.otf
```

（大文件不提交 git）

## 3. Unity 2022.3 烘焙（与游戏同大版本）

1. 新建 Unity **2022.3.x** 项目，安装 **TextMeshPro** 包  
2. `Window → TextMeshPro → Font Asset Creator`  
3. **Source Font File**：上一步 OTF  
4. **Character Set**：`Custom Characters`，粘贴 `charset.txt` 全文  
5. **Atlas Resolution**：4096（字多时用 8192）  
6. **Padding**：5；**Render Mode**：SDF  
7. Generate Font Atlas → 保存为 `SourceHanSansSC-Regular SDF`  
8. 将 `TMP_FontAsset` + 材质 + atlas 纹理打成 Android AssetBundle：

```csharp
// Editor 脚本示例
var build = new AssetBundleBuild {
    assetBundleName = "source-han-fallback",
    assetNames = new[] { "Assets/Fonts/SourceHanSansSC-Regular SDF.asset" },
};
BuildPipeline.BuildAssetBundles("Build/android", new[] { build },
    BuildAssetBundleOptions.ForceRebuildAssetBundle, BuildTarget.Android);
```

9. 复制 `Build/android/source-han-fallback` →  
   `i18n/font/source-han-fallback.bundle`

**Asset 名**须与 Frida 配置一致（默认 `SourceHanSansSC-Regular SDF`）。

## 4. 推送到手机并注入

```powershell
uv run python frida/run.py font --inject --duration 180
# 或翻译 + 字体一并：
uv run python frida/run.py intercept --font-inject --duration 120
```

Bundle 路径（自动 adb push）：

```
/sdcard/Android/data/com.sega.pjsekai/files/i18n/font/source-han-fallback.bundle
```