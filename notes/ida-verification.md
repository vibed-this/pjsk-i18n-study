# IDA 二进制验证

> RVA 来源见 [il2cpp-dump.md](./il2cpp-dump.md)。组件背景见 [text-rendering.md](./text-rendering.md)。

## 分析目标

验证 Il2CppDumper 给出的方法 RVA 在 `libil2cpp.so` 中是否为有效函数入口，并通过反汇编确认参数传递与行为，为 Frida / Zygisk Hook 提供最终偏移。

## 手段

| 工具 | 用途 |
|------|------|
| IDA Pro 8.3 | 打开 `libil2cpp.so.i64` |
| IDA Pro MCP | 远程调用 `lookup_funcs`、`disasm`、`xrefs_to`、`py_eval` 等 |
| Il2CppDumper `script.json` | 提供待验证的 RVA 对照 |

分析对象：

```
apk/split_config.arm64_v8a/lib/arm64-v8a/libil2cpp.so.i64
```

限制：当前环境 **Hex-Rays 不可用**（`hexrays_ready: false`），仅通过 ARM64 反汇编分析；符号未批量导入（`ida.py` 需交互选文件），手动重命名了 8 个关键函数。

## 过程

1. MCP `server_health` 确认 IDA 已加载 `libil2cpp.so`，`auto_analysis_ready: true`。
2. 对 4 个核心 Hook 候选逐一 `lookup_funcs` + `disasm` + `xrefs_to`。
3. 发现 Il2CppDumper RVA 与 IDA 函数入口存在轻微偏差（codegen 前缀），Hook 应打在 **IDA 识别的函数入口**。
4. 通过 `py_eval` 从 `script.json` 读取地址并重命名关键函数，保存 `.i64`。

## 各函数验证详情

### `Sekai_WordingManager_Get` — UI 词表查找

| 项 | 值 |
|----|-----|
| Il2CppDumper RVA | `0x60242AC` |
| IDA 函数入口 | `0x60241BC`（`sub_60241BC` → 已重命名） |
| 大小 | `0x114` |

行为：IL2CPP 生成的静态方法包装器；初始化静态字段后通过 vtable 查找，以 `BR X3` 间接跳转结束。仅 1 处 metadata 数据引用（经 il2cpp_codegen 间接调用）。

### `Sekai_TalkWindow_SetWordsInfo` — 剧情文本入口

| 项 | 值 |
|----|-----|
| Il2CppDumper RVA | `0x6264FD8` |
| IDA 函数入口 | `0x6264FD8`（完全吻合） |
| 大小 | `0xD8` |

ARM64 参数：

| 寄存器 | 含义 |
|--------|------|
| `X0` | this |
| `W1` | characterId |
| `X2` | displayName |
| `X3` | words（剧情正文） |
| `X4` | voiceId |
| `W5` | bookmarkSequenceId |
| `W6` | emotion |

行为（6.5.5，Capstone 反汇编）：将处理后的 `words` 字符串引用写入 **`[this+0x100]`**（`add x21, x19, #0x100` → `str`），再经 IL2CPP 字符串处理链更新显示。**无直接 `BL` xref**（全库扫描 `bl #0x6264FD8` = 0；经 `MethodInfo::methodPointer` 间接调用）。IDA 符号入口 `0x6264FD8` 含 codegen 前缀，实际函数体约 **`0x62650C4`**。Hook 仍以 IDA 入口 `0x6264FD8` 为准（Frida 已 E2E 验证）。

### `Sekai_UI_CustomTextMesh_SetText` — 通用 TMP 文本设置

| 项 | 值 |
|----|-----|
| Il2CppDumper RVA | `0x4F27590` |
| IDA 函数入口 | `0x4F27530` |
| 大小 | `0xC0` |

行为：`X1` = 文本字符串；先调父类 vtable（`[vtable+0x298]`），再调格式化函数，最后 `BR X2` 跳转。有 **30+** 调用者。

### `Sekai_FontAssetManager_SetupBuiltinFontAsset` — 内置字体加载

| 项 | 值 |
|----|-----|
| Il2CppDumper RVA | `0x61028AC` |
| IDA 函数入口 | `0x61028AC`（完全吻合） |
| 大小 | `0x27C` |

行为：通过资源加载函数取得 `TMP_FontAsset`，写入 `FontAssetManager` 字段并填充 fallback 表（`[font+0x138]`，List：`+0x10` items、`+0x18` size）。调用者为主初始化流程（`sub_6029F8C`）。

`FontAssetManager` 字段（6.5.5，本函数内可见）：

| 偏移 | 用途（推断） |
|------|----------------|
| `+0x20` | 主字体 A — 真机名 **`EB`**（接收 fallback） |
| `+0x28` | 加载资产 A — leave 后为新 EB 实例 |
| `+0x30` | fallback 源 A — EB |
| `+0x38` | 主字体 B — 真机名 **`DB`** |
| `+0x40` | 加载资产 B — leave 后为新 DB 实例 |
| `+0x48` | fallback 源 B — DB |

### `Sekai_FontAssetManager_ClearFallbackFontAsset` — 清空 fallback 表

| 项 | 值 |
|----|-----|
| Il2CppDumper / IDA | `0x61024F8` |
| 大小 | `0x74` |

行为：`X0` = manager，`X1` = `TMP_FontAsset`；读取 `[font+0x138]` 的 List，将 `size` 置 0（`SetupBuiltinFontAsset` 在写入新 fallback 前调用）。

**初步汉化替换点（2026-06-29）**：在 `SetupBuiltinFontAsset` **onLeave** 改写 `FontAssetManager` 的 `+0x20`（EB）、`+0x38`（DB）为主简中 `TMP_FontAsset` 指针；原 EB/DB 写入新字体的 `[font+0x138]` fallback List。勿仅在 fallback 链末尾追加（主字体有字形时不走 fallback）。策略见 [hook-strategy.md](./hook-strategy.md)、[text-rendering.md](./text-rendering.md)。

### `TMPro_TMP_Text_set_text` — TMP 底层兜底

| 项 | 值 |
|----|-----|
| Il2CppDumper RVA | `0xA8D1BE8` |
| IDA 函数入口 | `0xA8D1B98` |
| 大小 | `0x138` |

行为：`X0` = this，`X1` = value；读取 `[this+0x138]`（m_text），比较后更新。所有 TMP 文本的最终入口，但范围过宽。

## 结论

- 4 个核心 Hook 候选在二进制中**均为有效函数**，无额外混淆导致入口不可识别。
- RVA 与 IDA 入口的偏差（`0x50`~`0xF0`）属 IL2CPP codegen 正常现象，**Hook 地址以 IDA 函数入口为准**。
- IDA 中已重命名 8 个关键函数并保存至 `.i64`。
- **动态验证**（见 [frida.md](./frida.md)）：真机运行时 `base + 偏移` 与 `Interceptor.attach` 结果一致；`TalkWindow.SetWordsInfo`、`WordingManager.GetImpl`、`CustomTextMesh.SetText` 等已在真机成功安装 Hook。

### `methodPointer`（运行时解析）与 IDA 入口

Il2CppDumper `script.json` 的 `Address` 与 `il2cpp_class_get_method_from_name` 返回的 `MethodInfo::methodPointer` **同源**（metadata 登记值），**不一定等于** IDA 识别的最佳 Hook 入口：

| 方法 | Dumper / `methodPointer` | IDA 入口 | 备注 |
|------|--------------------------|----------|------|
| `WordingManager.Get` | `0x60242AC` | `0x60241BC`（包装器） | UI intercept 实际 Hook **实现体 `0x60282AC`**，非本表包装器 |
| `CustomTextMesh.SetText` | `0x4F27590` | `0x4F27530` | codegen 前缀 |
| `TalkWindow.SetWordsInfo` | `0x6264FD8` | `0x6264FD8` | 完全一致，适合作运行时 resolve 锚点 |
| `TMP_Text.set_text` | `0xA8D1BE8` | `0xA8D1B98` | codegen 前缀 |

Zygisk 若采用运行时 `il2cpp_*` 解析，须与 [hook-strategy.md](./hook-strategy.md)「运行时 IL2CPP 解析」章节的混合策略配合，不可 blindly Hook `methodPointer`。

---

## 剧情运行时 ID（2026-06-29）

### 分析目标

确认运行时能否取得与 `story-build` 对齐的 `(scenarioId, talkLineIdx)`，以替代全局 `jp→zh` 哈希表、消除 collision。

### 手段

- `dump.cs`：`ScenarioPlayer`、`ScenarioSceneData`、`ScenarioSnippet`、`ScenarioJumper`
- IDA：`ScenarioPlayer.<SnippetActionTalk>d__224.MoveNext`（`sub_62643DC`，主体自 `0x62643F0`）
- Capstone 反汇编 `libil2cpp.so`（6.5.5；IDA MCP/Hex-Rays 不可用时的补充验证）

### 过程

#### 1. 无全局台词 ID

| 层级 | 标识符 | 说明 |
|------|--------|------|
| 构建期 | `scenarioId` 字符串 + **talk 行序** | `story.py` 按 `Snippets` 中 `Action=Talk` 顺序 enumerate |
| Asset JSON | `ScenarioSnippet.ReferenceIndex` | 指向 `TalkData[]` 下标，**≠** talk 行序 |
| 运行时 `SetWordsInfo` | 仅 `characterId`、明文、`bookmarkSequenceId` | **无** `scenarioId` 参数 |

#### 2. 调用链

```
ScenarioPlayer.SnippetActionTalk(snippet)     @ 0x624FC28  （协程工厂；读写 player+0x1C0 talkingSnippet）
  → <SnippetActionTalk>d__224.MoveNext        @ 0x62643DC（主体 0x62643F0）
      读 [snippet+0x1C] ReferenceIndex；读 TalkData 字段
      → sub_6263F28 @ 0x6263F28               （从 talk 对象 +0x18/+0x28 取字段并做字符串处理）
      → 参数布置 @ 0x6264F34                  （w1/x2/x3/x4/w5）
      → 汇入 0x6264A04 → IL2CPP 间接调用
      → TalkWindow.SetWordsInfo               @ 0x6264FD8

ScenarioJumper.SnippetActionTalk(snippet, sequenceId)  @ 0x6244D80  （日志跳转/书签回放旁路）
```

> **修正（2026-06-29 Capstone）**：旧笔记写 `SetWordsInfo` 调用点在 **`0x6264A54`**；该地址实为 **il2cpp 静态初始化**（`ldr` + `bl #0x484ba94`），非 `SetWordsInfo` 调用。实际参数布置在 **`0x6264F34`**（`mov w1,w22` / `mov x3,x21` / `mov w5,w19`），经协程状态机间接分发，**无** `bl #SetWordsInfo` 直连。

> `0x6244D80` 属 **`ScenarioJumper`**，非 `ScenarioPlayer`。主播放路径用 `0x624FC28` / `0x62643DC`。

#### 3. `SetWordsInfo` 参数（MoveNext 出口 @ `0x6264F34`，6.5.5）

| 寄存器 | 含义 | 来源 |
|--------|------|------|
| `X0` | `TalkWindow` this | 协程状态 / `[ScenarioPlayer+0x160]` 链 |
| `W1` | `characterId` | `TalkCharacters[0].Character2dId` |
| `X2` | `displayName` | `sub_6263F28` 处理后显示名 |
| `X3` | `words` | `sub_6263F28` 处理后正文（**已做字符串处理，非原始 asset 明文**） |
| `X4` | `voiceId` | snippet talk voice |
| `W5` | **`bookmarkSequenceId`** | 协程状态传入（≈ snippet `Index`） |
| `W6` | `emotion` | 常 0 |

`BookmarkSequenceId` 为**时间轴 snippet 序号**（书签/跳过），与 `story-build` 的 **talk 行序** 不同。`{{playerName}}` 等占位符在 **`sub_6263F28` → `SetWordsInfo` 之前**处理，故 `STORY_MODE=cn` 扁平表查 `args[3]` 时须用**运行时最终明文**（或改 Hook 点提前拦截）。

#### 4. `ScenarioPlayer` 关键字段（6.5.5，`dump.cs`）

| 偏移 | 字段 | 用途 |
|------|------|------|
| `+0x1B0` | `scenarioScene` | `ScenarioSceneData*` |
| `+0x1B8` | `sequenceId` | 当前 snippet 时间轴 ID（`CurrentSequenceId`） |
| `+0x1C0` | `talkingSnippet` | 当前 Talk `ScenarioSnippet*` |
| `+0x1D8` | `currentSnippet` | 当前 snippet |
| `+0x2F0` | `EpisodeId` | Master **数值** episode ID，≠ `scenarioId` 字符串 |
| `+0x380` | `BookmarkSequenceId` | 传入 `SetWordsInfo` W5 |

`ScenarioSceneData`（`ScriptableObject`）：

| 偏移 | 字段 |
|------|------|
| `+0x18` | `ScenarioId`（`string`，如 `event_01_01`） |
| `+0x58` | `Snippets[]` |
| `+0x60` | `TalkData[]` |

`ScenarioSnippet`：

| 偏移 | 字段 |
|------|------|
| `+0x10` | `Index` |
| `+0x14` | `Action`（Talk = 1） |
| `+0x1C` | `ReferenceIndex` → `TalkData` |

### 结论

| 问题 | 结论 |
|------|------|
| 能否从 `SetWordsInfo`  alone 拿到 ID？ | **不能**；无 `scenarioId`，`bookmarkSequenceId` 亦非 talk 行序 |
| 推荐 Hook 点？ | **`ScenarioPlayer.SnippetActionTalk` `0x624FC28` `onEnter`**：写线程上下文，供 `SetWordsInfo` 消费 |
| 如何拼 composite key？ | `scenarioId = readStr([player+0x1B0]+0x18)`；`talkLineIdx = computeTalkLineIdx(player, snippet)`（与 `story.py` `extract_talk_lines` 同逻辑） |
| 日志跳转路径？ | 另 Hook **`ScenarioJumper.SnippetActionTalk` `0x6244D80`**（显式 `sequenceId` 参数 W2） |
| 真机验证（2026-06-29） | 顺序播放时 `scenarioId` 正确；**`++` 计数在 WORD_SKIP 后错位**（已改 `computeTalkLineIdx`） |
| `bookmarkSequenceId` | ≈ snippet `Index`（6/7/8），≠ talk 行序 |
| 待复测 | 跳过后 `computeTalkLineIdx`；`ScenarioJumper` 路径 |

实现策略见 [hook-strategy.md](./hook-strategy.md) §剧情运行时上下文。

---

## UI 词表加载链（归档，非实施路径，2026-06-29）

### 分析目标

曾调研 UI「改 wordings 数据源」所需的 **IDA 函数入口**、参数/数据布局。结论：**不必实施**——UI 有 `wordingKey`，继续 `GetImpl` 查表即可。本节仅保留偏移与结构供参考。

### 手段

- Il2CppDumper `script.json` / `dump.cs`（6.5.5）
- Capstone 反汇编 `dump/il2cpp/il2cpp.so`（IDA MCP 当次不可用）
- 对照 `MasterWording` / `CachedMaserDataAll` / `MasterDataManager` 字段偏移

### 过程

**1. 入口修正（Dumper ≠ IDA 落点）**

| 符号 | script.json / dump.cs | **IDA / Capstone 入口** | 偏差 |
|------|----------------------|---------------------------|------|
| `WordingManager.AddMasterWording` | `0x602EC68` | **`0x602EC40`** | −0x28（metadata 指向前缀区） |
| `WordingManager.ForceInit` | `0x602E574` | **`0x602E5A8`** | +0x34 |
| `MasterDataManager.GetWordings` | `0x606A988` | `0x606A988` | 0 |
| `MasterDataManager.UpdateMasterData` | `0x604EE24` | `0x604EE24` | 0 |
| `MasterDataManager.LoadMaster` | `0x604E5B0` | `0x604E5B0` | 0 |

`AddMasterWording` 入口 `0x602EC40` 尾声 **`B #0x6E77810`** 跳入共享实现体；`0x602EC68` 落在 class init 中间，**不可** Hook。

**2. `AddMasterWording` 实现体（`0x6E77810`）**

- 入参：`X0` 保留 / `X1` = `MasterDataManager` 单例（自静态字段 `+0x5b8` 解引用）。
- 通过内部调用取得 `List<MasterWording>`，逐条读 `wordingKey` / `value`，写入 `WordingManager` 静态 `dictionary`（`Dictionary<string,string>`，`set_Item` 链 `0x5B71CD8` 一带）。
- **无 BL 直接 xref** 至 `0x602EC40`（经 `B` / 间接调用）；调用频率：**Master 加载完成后一次**（与 `LoadMaster` → `UpdateMasterData` 同阶段）。

**3. `GetWordings`（`0x606A988`）**

- `MasterDataManager` 实例 `+0x40` → `CachedMaserDataAll* cachedMaster`。
- 返回 `cachedMaster.wordings`（`List<MasterWording>`，dump 字段 **`+0x350`**）。
- 若将来重做源注入：可在 `AddMasterWording` **`onEnter`** 调 `get_Instance` + `GetWordings`，按 `MasterWording+0x10/+0x18` 预 patch `value`（**当前不采用**）。

**4. `UpdateMasterData`（`0x604EE24`）**

- 签名：`void UpdateMasterData(SuiteMaster masterDataAll)`（`X1` = `SuiteMaster*`）。
- 将 `SuiteMaster` 各表写入 `cachedMaster`；`wordings` 在 `SuiteMaster+0x380`（`MasterWording[]`），落入 `CachedMaserDataAll+0x350` 列表。
- 体量大、多表并行；**词表专用**更宜 Hook `AddMasterWording`（单点、已遍历 list）。

**5. `ForceInit`（`0x602E5A8`）**

- `Resources.Load("Wording/wording")` → 解析内置 CSV → **直接**写 `dictionary`（不经 `MasterWording` 列表）。
- 覆盖 ~196 条（`MSG_STARTAPP_*` 等）；须 **`onLeave`** 枚举 `dictionary` 或保留 `Get` 兜底。

**6. 数据结构（Frida 用）**

| 类型 | 字段 | 偏移 |
|------|------|------|
| `MasterWording` | `wordingKey` / `value` | `+0x10` / `+0x18` |
| `MasterDataManager` | `cachedMaster` | `+0x40` |
| `CachedMaserDataAll` | `wordings` (`List<>`) | `+0x350` |
| `List<T>` | `_items` / `_size` | `+0x10` / `+0x18` |

### 结论

| 问题 | 结论 |
|------|------|
| 是否实施？ | **否**；UI 量产走 **`GetImpl` `onLeave` + `wordings.json`**（见 [hook-strategy.md](./hook-strategy.md) §UI） |
| 真机源注入探测 | `sourceAddEnter=0`、`sourceForceInit=0`；简中命中 `sourceGetFallback`（`Get` 兜底） |
| 若重做源注入的 Hook 点 | `AddMasterWording` @ `0x602EC40` `onEnter`；内置 196 条 `ForceInit` @ `0x602E5A8` `onLeave` |
| `UpdateMasterData` | 可选；优先度低于 `AddMasterWording` |
| 代码状态 | `wording_source.js`、`--source-inject` **已撤销**；`offsets.js` 不再保留上述 UI 加载链偏移 |
| 下一步 | **剧情** bundle 载入链 IDA（非本节） |

---

## 剧情 bundle 载入链与 TalkData 布局（2026-06-29）

### 分析目标

定位 scenario AssetBundle 反序列化后、`ScenarioPlayer` 播放前的 **Hook 候选**；确认运行时 `TalkData`（实为 `ScenarioSnippetTalk`）字段偏移，供 `STORY_MODE=cn` patch 与 JP 备份。

### 手段

- Il2CppDumper `dump.cs` / `script.json`（6.5.5）
- Capstone 反汇编 `dump/il2cpp/il2cpp.so`（IDA Pro MCP 当次不可用；RVA 与 `script.json` `Address` 一致）
- 辅助脚本：`tools/analyze_scenario_chain.py`、`tools/analyze_scenario_focus.py`
- 对照 `sub_6261648`（`AttachSceneData`/`Init` 内联路径）与 `sub_626453C`（`ScenarioSnippetTalk` 访问器）

### 过程

#### 1. 类型与 JSON 字段对应

| JSON / 笔记统称 | 运行时类型（`dump.cs`） | `ScenarioSceneData` 偏移 |
|-----------------|-------------------------|--------------------------|
| `ScenarioId` | `string` | `+0x18` |
| `Snippets` | `ScenarioSnippet[]` | `+0x58` |
| `TalkData` | **`ScenarioSnippetTalk[]`** | `+0x60` |

> 无独立 `TalkData` 类；离线 JSON 的 `TalkData` 数组即 `ScenarioSnippetTalk` 序列。

**`ScenarioSnippetTalk`（6.5.5）**

| 偏移 | 字段 | patch 目标 |
|------|------|------------|
| `+0x10` | `TalkCharacters[]` | — |
| `+0x18` | `WindowDisplayName` | ✅ 角色名 |
| `+0x20` | `Body` | ✅ 正文 |
| `+0x28` | `TalkTention` | — |
| `+0x40` | `Voices[]` | — |

Capstone 在 `sub_626453C` @ `0x626460C`–`0x6264624` 可见 getter/setter：`ldr/str` 相对 `+0x18` / `+0x20`。

**`ScenarioSnippet`**

| 偏移 | 字段 |
|------|------|
| `+0x10` | `Index` |
| `+0x14` | `Action`（Talk = 1） |
| `+0x1C` | `ReferenceIndex` → `TalkData[]` 下标 |

**IL2CPP 数组**（`sub_6261648` @ `0x62616B4`–`0x62616D0` 验证）

| 偏移 | 含义 |
|------|------|
| `+0x18` | `max_length` |
| `+0x20` | 首元素（`ScenarioSnippetTalk*` 指针数组，步长 8） |

访问：`talkPtr = [talkArr + 0x20 + refIdx * 8]`。

**`AssetManager.BundleElement`**

| 偏移 | 字段 |
|------|------|
| `+0x10` | `BundleName` |
| `+0x18` | `FileName` |
| `+0x20` | **`LoadedResource`**（`Object*`，scenario 场景下为 `ScenarioSceneData*`） |
| `+0x2C` | `LoadStatus` |

**`ScreenLayerScenario`**

| 偏移 | 字段 |
|------|------|
| `+0x78` | `scenarioPlayer` |
| `+0xE8` | `scenarioDatas`（`Dictionary<string, ScenarioSceneData>`） |
| `+0xF8` | `startScenarioId` |

**`ScenarioPlayer`**（播放期，见 §剧情运行时 ID）

| 偏移 | 字段 |
|------|------|
| `+0x1B0` | `scenarioScene` |

#### 2. 加载调用链（6.5.5）

```
ScreenLayerScenario.LoadScenarioSceneDataAsync          @ 0x63E1908
  coroutine MoveNext                                    @ 0x63E4868
    → AssetManager 下载 / 加载 bundle
    → OnFinishLoadScenario(BundleElement element)       @ 0x63E1F80
         LoadedResource @ element+0x20 → ScenarioSceneData
         写入 scenarioDatas @ layer+0xE8（按 scenarioId）
    → … 播放准备 …
    → ScenarioPlayer.AttachSceneData(ScenarioSceneData)   @ 0x624C100
         Init @ 0x624C120（同函数体延续）
         player.scenarioScene 供播放使用

旁路（工具/预载，非主 UI 链必走）：
ScenarioUtility.GetScenarioData(scenarioId, bundleName) @ 0x4C23834
  async MoveNext                                        @ 0x4C2B20C
    → 回调 <>c__DisplayClass3_0.<GetScenarioData>b__0   @ 0x4C26548
         入参 AssetManager.BundleElement*（LoadStatus==Success 时处理）
```

播放期读 Talk 字段（已验证，§剧情运行时 ID 补充）：

```
SnippetActionTalk.MoveNext @ 0x62643F0
  → sub_626453C：按 snippet.ReferenceIndex 取 TalkData
  → sub_6263F28：读 talk+0x18 / +0x28，处理后 → SetWordsInfo
```

`sub_6261648` 内联逻辑（`AttachSceneData` 调用 @ `0x624C264`）：

```asm
ldr x8, [player, #0x1b0]     ; scenarioScene
ldr x8, [x8, #0x60]          ; TalkData[]
ldrsw x9, [snippet, #0x1c]   ; ReferenceIndex
ldr w10, [x8, #0x18]         ; max_length
add x8, x8, x9, lsl #3
ldr x1, [x8, #0x20]          ; ScenarioSnippetTalk*
```

#### 3. Hook 候选（IDA 入口 RVA）

| 优先级 | 符号 | RVA | 时机 | Frida `onEnter` 参数 |
|--------|------|-----|------|----------------------|
| **P0** | `ScenarioPlayer.AttachSceneData` | `0x624C100` | 场景挂接到 player、**播放前** | `X0`=player，`X1`=`ScenarioSceneData*` |
| **P1** | `ScreenLayerScenario.OnFinishLoadScenario` | `0x63E1F80` | bundle 载入完成、写入缓存 | `X0`=layer，`X1`=`BundleElement*` → `+0x20` 为 scene |
| P2 | `ScenarioUtility.<>c__DisplayClass3_0.<GetScenarioData>b__0` | `0x4C26548` | 异步 GetScenarioData 回调 | `X1`=`BundleElement*` |
| 过渡 | `ScenarioPlayer.SnippetActionTalk` | `0x624FC28` | 每句 Talk（已有 ctx 方案） | 见 §剧情运行时 ID |

**推荐量产**：**P0 `AttachSceneData` `onEnter`** — 直接拿到 `ScenarioSceneData*`，单次 patch 整话；不依赖 `BundleElement` 解析。

**patch 伪代码**（与 `story-build` 行序一致）：

```javascript
const scene = args[1];
const scenarioId = readIl2CppString(readPtr(scene, SCENARIO_SCENE_ID));
const snippets = readPtr(scene, SCENARIO_SCENE_SNIPPETS);
const talkArr = readPtr(scene, 0x60);
let talkLineIdx = 0;
for (const snip of sortedSnippets(snippets)) {
  if (readS32(snip, SCENARIO_SNIPPET_ACTION) !== SCENARIO_ACTION_TALK) continue;
  const ref = readS32(snip, SCENARIO_SNIPPET_REF_INDEX);
  const talk = readPtr(talkArr, IL2CPP_ARRAY_VECTOR + ref * 8);
  const zh = lookup(`${scenarioId}:${talkLineIdx}`); // 或 by-scenario 文件
  if (STORY_MODE === 'cn' && zh) {
    writeIl2CppStringField(talk, 0x18, zh.name);
    writeIl2CppStringField(talk, 0x20, zh.body);
  } else if (STORY_MODE === 'dual') {
    backupJp(scenarioId, talkLineIdx, talk); // 深拷贝 +0x18/+0x20
  }
  talkLineIdx++;
}
```

### 结论

| 问题 | 结论 |
|------|------|
| `TalkData` 运行时类型？ | **`ScenarioSnippetTalk`**；`ScenarioSceneData+0x60` |
| 正文字段偏移？ | **`+0x20` `Body`**；显示名 **`+0x18`**（Capstone + dump.cs 一致） |
| 首选 Hook？ | **`ScenarioPlayer.AttachSceneData` `0x624C100` `onEnter`** |
| 备选 Hook？ | `OnFinishLoadScenario` `0x63E1F80`（更早，改 `scenarioDatas` 缓存） |
| 行序对齐？ | 遍历 `Snippets` 中 `Action==Talk`（按 `Index` 排序），**非**裸 `TalkData[]` 下标 |
| Frida 原型 | ✅ `frida/lib/story_patch.js` @ `0x624C100`（见 [frida.md](./frida.md) §8） |
| 下一步 | 真机 E2E（维护后）；备选 `OnFinishLoadScenario` `0x63E1F80` |

实现策略见 [hook-strategy.md](./hook-strategy.md) §剧情数据源 patch、[story-pipeline.md](./story-pipeline.md) §运行时注入。

## 相关笔记

- Hook 方案：[hook-strategy.md](./hook-strategy.md)
- Frida 实机验证：[frida.md](./frida.md)
- 工具与环境：[toolchain.md](./toolchain.md)