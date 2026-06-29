// Headless TMP SDF bake for PJSK i18n mod (Unity 2022.3 batchmode / CI).
using System;
using System.IO;
using System.Linq;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.TextCore.LowLevel;

public static class PjskFontBake
{
    const string FontAssetName = "SourceHanSansSC-Regular SDF";
    const string BundleName = "source-han-fallback";
    const int SamplingPointSize = 90;
    const int AtlasPadding = 5;

    static string RepoRoot => FindRepoRoot();

    static string CharsetPath => Path.Combine(RepoRoot, "i18n", "font", "charset.txt");
    static string OtfPath => Path.Combine(RepoRoot, "i18n-data", "font", "SourceHanSansSC-Regular.otf");
    static string BundleOutPath => Path.Combine(RepoRoot, "i18n", "font", "source-han-fallback.bundle");

    static string FindRepoRoot()
    {
        var dir = Path.GetFullPath(Application.dataPath);
        for (var i = 0; i < 8; i++)
        {
            if (File.Exists(Path.Combine(dir, "Agents.md")) && Directory.Exists(Path.Combine(dir, "i18n")))
                return dir;
            dir = Path.GetFullPath(Path.Combine(dir, ".."));
        }
        throw new InvalidOperationException("repo root not found (expected Agents.md + i18n/)");
    }

    [MenuItem("PJSK/Font Bake (local)")]
    public static void BuildMenu() => Build();

    public static void Build()
    {
        var exitCode = 0;
        try
        {
            exitCode = Bake();
        }
        catch (Exception ex)
        {
            Debug.LogError($"[PjskFontBake] failed: {ex}");
            exitCode = 1;
        }

        if (Application.isBatchMode)
            EditorApplication.Exit(exitCode);
    }

    static int Bake()
    {
        if (!File.Exists(CharsetPath))
            throw new FileNotFoundException($"charset missing — run: pjsk-i18n font-chars{Environment.NewLine}{CharsetPath}");

        if (!File.Exists(OtfPath))
            throw new FileNotFoundException($"Source Han OTF missing — download to:{Environment.NewLine}{OtfPath}");

        var charset = File.ReadAllText(CharsetPath);
        if (string.IsNullOrWhiteSpace(charset))
            throw new InvalidOperationException("charset.txt is empty");

        var charCount = charset.Distinct().Count();
        var atlasSize = charCount > 2500 ? 8192 : 4096;
        Debug.Log($"[PjskFontBake] repo={RepoRoot} chars={charCount} atlas={atlasSize}x{atlasSize}");

        Directory.CreateDirectory(Path.Combine(Application.dataPath, "Generated"));
        var otfAssetPath = "Assets/Generated/SourceHanSansSC-Regular.otf";
        File.Copy(OtfPath, Path.Combine(Application.dataPath, "Generated", "SourceHanSansSC-Regular.otf"), true);
        AssetDatabase.ImportAsset(otfAssetPath, ImportAssetOptions.ForceUpdate);

        var sourceFont = AssetDatabase.LoadAssetAtPath<Font>(otfAssetPath);
        if (sourceFont == null)
            throw new InvalidOperationException($"failed to import font: {otfAssetPath}");

        var fontAsset = TMP_FontAsset.CreateFontAsset(
            sourceFont,
            SamplingPointSize,
            AtlasPadding,
            GlyphRenderMode.SDFAA,
            atlasSize,
            atlasSize,
            AtlasPopulationMode.Static);

        if (fontAsset == null)
            throw new InvalidOperationException("TMP_FontAsset.CreateFontAsset returned null");

        fontAsset.name = FontAssetName;

        if (!fontAsset.TryAddCharacters(charset, out var missing))
            Debug.LogWarning($"[PjskFontBake] TryAddCharacters returned false; missing={missing?.Length ?? 0}");

        if (!string.IsNullOrEmpty(missing))
            Debug.LogWarning($"[PjskFontBake] missing glyphs ({missing.Length}): {missing.Substring(0, Math.Min(120, missing.Length))}…");

        var fontAssetPath = $"Assets/Generated/{FontAssetName}.asset";
        AssetDatabase.CreateAsset(fontAsset, fontAssetPath);
        if (fontAsset.material != null)
            AssetDatabase.AddObjectToAsset(fontAsset.material, fontAsset);
        if (fontAsset.atlasTexture != null)
            AssetDatabase.AddObjectToAsset(fontAsset.atlasTexture, fontAsset);
        AssetDatabase.SaveAssets();

        var buildDir = Path.Combine(Application.dataPath, "..", "Build", "android");
        Directory.CreateDirectory(buildDir);

        var build = new AssetBundleBuild
        {
            assetBundleName = BundleName,
            assetNames = new[] { fontAssetPath },
        };

        var manifest = BuildPipeline.BuildAssetBundles(
            buildDir,
            new[] { build },
            BuildAssetBundleOptions.ForceRebuildAssetBundle,
            BuildTarget.Android);

        if (manifest == null)
            throw new InvalidOperationException("BuildAssetBundles failed");

        var builtBundle = Path.Combine(buildDir, BundleName);
        if (!File.Exists(builtBundle))
            throw new FileNotFoundException($"bundle not found after build: {builtBundle}");

        Directory.CreateDirectory(Path.GetDirectoryName(BundleOutPath)!);
        File.Copy(builtBundle, BundleOutPath, true);

        var sizeKb = new FileInfo(BundleOutPath).Length / 1024;
        Debug.Log($"[PjskFontBake] OK → {BundleOutPath} ({sizeKb} KiB)");
        return 0;
    }
}