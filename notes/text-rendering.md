# 文本渲染组件

> 类结构来源见 [il2cpp-dump.md](./il2cpp-dump.md)。背景中的待确认项见 [bg.md](./bg.md) §3.6。

## 分析目标

确认游戏使用的文本渲染组件类型，厘清 UI 文本与剧情文本的数据来源，判断是否存在独立的振假名渲染层。

## 手段

在 `dump.cs` / `script.json` 中搜索 `TMPro`、`CustomTextMesh`、`TalkWindow`、`WordingManager`、`FontAssetManager` 等符号。

## 过程

1. 确认存在 `Unity.TextMeshPro.dll` 程序集（Image 15）。
2. 定位 UI 封装类 `Sekai.UI.CustomTextMesh`：

   ```
   CustomTextMesh : TextMeshProUGUI, ICustomText
   ```

3. 定位剧情对话框 `Sekai.TalkWindow`：
   - `nameLabel` / `nameOutlineLabel` → `CustomTextMesh`
   - `wordsLabel` / `wordsOutlineLabel` → `CustomTextMesh`
4. 定位 UI 词表系统 `Sekai.WordingManager`：
   - 静态 `Dictionary<string, string>` 存储 key → 日文文本
   - `Get(key)` / `GetFormat(key, args)` 为查找入口
5. 检查 `ruby` 字段：出现在角色 Master 数据（`MasterCharacter` 等）中，为角色名读音标注，**非**剧情对话框的独立振假名渲染层。
6. 定位字体管理 `Sekai.FontAssetManager`：
   - 管理 `_baseFontDB/EB`、`_builtInFontDB/EB`、`_dynamicFontDB/EB` 等 `TMP_FontAsset`
   - `ClearFallbackFontAsset()` 操作 fallback 表

## 结论

| 问题 | 结论 |
|------|------|
| UI 文本组件 | **TextMeshPro**，封装为 `CustomTextMesh` |
| 剧情对话框组件 | `TalkWindow` → `CustomTextMesh`（TMP 上层封装） |
| UI 文本来源 | 大量走 `WordingManager` 词表 key，非全部裸字符串 |
| 振假名层 | 无独立剧情振假名渲染层；`ruby` 为角色 Master 字段 |
| 字体 | `FontAssetManager` 管理 TMP 字体资产及 fallback 表 |

`bg.md` 中「文本渲染组件待确认」**已关闭**。

## 相关笔记

- Hook 方案：[hook-strategy.md](./hook-strategy.md)
- IDA 函数验证：[ida-verification.md](./ida-verification.md)