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

---

## 词表 key 与日文数据来源（2026-06-28）

### 分析目标

厘清 UI 词表 **key 定义在何处**、**日语文本存放在何处**，为翻译数据管线（TODO P3）提供依据。

### 手段

| 手段 | 用途 |
|------|------|
| `dump.cs` / `stringliteral.json` | 类结构、内嵌 key 字面量 |
| IDA `sub_602EC68` / `sub_4F2B2EC` / `sub_60282AC` | `AddMasterWording`、词表查找、UI 刷新链路 |
| Frida 真机样本 | 已观测 key：`MSG_STARTAPP_*`、`WORD_DECIDE` 等 |
| [sekai-master-db-diff/wordings.json](https://sekai-world.github.io/sekai-master-db-diff/wordings.json) | 社区公开 Master 词表对照 |

### 过程

#### 1. key 的三类来源

| 来源 | 说明 | 示例 |
|------|------|------|
| **C# 硬编码** | `stringliteral.json` 中 `MSG_*` / `WORD_*` 字面量，代码或运行时 `SetWordingText(key)` 传入 | `WORD_DECIDE`、`MSG_MOVIE_SKIP_BODY` |
| **Prefab 序列化** | `CustomTextMesh.wordingKey`（偏移 `0x7A0`）+ `useWordingKey`（`0x79D`）写在 UI 预制体上 | 启动画面按钮等 |
| **动态传参** | 各 UI 逻辑调用 `SetWordingText` / `SetWordingKey` | Frida 在 `SetWordingText` `onEnter` 读到 key |

`stringliteral.json` 共 **1651** 个 `MSG_*`/`WORD_*` 字面量；真机观测的 `MSG_STARTAPP_LOGIN` 等亦在此列。

#### 2. 日语文本的存放与加载

数据结构（MessagePack）：

```csharp
class MasterWording {
    [Key("wordingKey")] public string wordingKey;  // key
    [Key("value")]      public string value;       // 日文正文（可含 TMP 标签、{0} 占位符）
}
```

聚合位置：

| 容器 | 字段 | 访问入口 |
|------|------|----------|
| `SuiteMaster` | `MasterWording[] wordings` @ `0x380` | 服务端 API 分片下载 |
| `CachedMaserDataAll` | `List<MasterWording> wordings` @ `0x350` | `MasterDataManager.cachedMaster` |
| `WordingManager` | 静态 `Dictionary<string,string> dictionary` | `Get` / `GetFormat` |

加载链路（IDA 验证）：

```
登录 SystemResponse.suiteMasterSplitPath
  → MasterDataManager.LoadMaster → GetSuiteMasterAPI（MessagePack 分片）
  → UpdateMasterData → CachedMaserDataAll.wordings
  → WordingManager.AddMasterWording（0x602EC68）
       遍历 GetWordings()（0x606A988），dictionary[key]=value
  → WordingManager.Get(key)（0x60282AC）查表返回日文
```

UI 显示链路：

```
CustomTextMesh.SetWordingText(key)  // 0x4F2B408，仅存 key 到 0x7A0
  → UpdateWordingText()               // 0x4F2B2EC
       WordingManager.Get(key)        // 0x60282AC
       [可选] GetFormat + formatArgs  // 0x7C8
  → TMP set_text（tail-call）
```

**结论**：日语文本**不在** `stringliteral.json`（那里只有 key 名）；正文在 **Master 词表** `MasterWording.value`，运行时落入 `WordingManager.dictionary`。

另：`stringliteral.json` 有路径 `"Wording/wording"`（`0xB731450`），疑为 AssetBundle 内词表资源引用，与 Master API 并行存在，具体用途待验证。

#### 3. 外部公开词表对照

下载 `sekai-master-db-diff/wordings.json`（**3519** 条）与二进制字面量交叉比对：

| 指标 | 数量 |
|------|------|
| 二进制 `MSG_*`/`WORD_*` 字面量 | 1651 |
| 与公开库交集 | 1530 |
| 仅存在于二进制（公开库缺失） | 121 |
| 仅存在于公开库 | 1989 |

已观测 key 对照：

| key | 公开库 | 日文 value |
|-----|--------|------------|
| `WORD_DECIDE` | ✅ | 決定 |
| `WORD_CANCEL` | ✅ | キャンセル |
| `MSG_MOVIE_SKIP_BODY` | ✅ | ムービーをスキップしますか？ |
| `MSG_STARTAPP_LOGIN` | ❌ | 待从设备 Master 缓存或新版库提取 |
| `MSG_STARTAPP_MASTER` | ❌ | 同上 |

`MSG_STARTAPP_*` 共 4 个字面量均在二进制中，但不在当前公开 `wordings.json`——可能是**较新版本新增 key**，需从真机 `MasterDataManager` 缓存或更新版 master diff 补齐。

#### 4. 与剧情文本的区分

| 类型 | 数据形态 | Hook 点 |
|------|----------|---------|
| **UI 词表** | key → `MasterWording.value` | `SetWordingText` / `WordingManager.Get` / `TMP_Text.set_text` |
| **剧情对话** | 明文（角色名 + 正文） | `TalkWindow.SetWordsInfo`；数据来自 scenario JSON，**不走词表 key** |

### 结论

| 问题 | 结论 |
|------|------|
| key 在哪 | 代码字面量 + Prefab `wordingKey` 字段 + 运行时 `SetWordingText` 传参 |
| 日文在哪 | `MasterWording.value`，经 `MasterDataManager` 加载后写入 `WordingManager.dictionary` |
| 离线数据源 | 首选 `sekai-master-db-diff/wordings.json`（覆盖 1530/1651 已知字面量）；缺口 key 需抓设备 Master 缓存 |
| 翻译接入点 | 在 `WordingManager.Get` 或 `TMP_Text.set_text` 用 `key → 中文` 替换；剧情走 `SetWordsInfo` 独立映射 |

## 相关笔记

- Hook 方案：[hook-strategy.md](./hook-strategy.md)
- IDA 函数验证：[ida-verification.md](./ida-verification.md)