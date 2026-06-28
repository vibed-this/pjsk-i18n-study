# Hook 策略

> 组件分析见 [text-rendering.md](./text-rendering.md)。偏移验证见 [ida-verification.md](./ida-verification.md)。Frida 实机验证见 [frida.md](./frida.md)。

## 分析目标

综合 Il2CppDumper 类结构分析与 IDA 二进制验证，确定运行时文本替换与字体注入的 Hook 方案。

## 手段

- Il2CppDumper 类继承关系与调用链分析
- IDA 反汇编确认 ARM64 参数传递与函数入口
- Frida gadget 真机动态验证（TB322FC，见 [frida.md](./frida.md)）
- 参照 gakuen-imas-localify 的 Zygisk + IL2CPP Hook 路线（尚未实施）

## 过程

1. 从 `dump.cs` 确认文本流经 `WordingManager`（UI）与 `TalkWindow`（剧情）两条主线。
2. 在 IDA 中验证各候选函数的入口地址、参数寄存器与调用频率。
3. 排除仅在 metadata 中引用的间接调用点，优先选择有直接 `xrefs_to` 的函数。
4. 按覆盖范围与性能开销分层，确定优先级。
5. **2026-06-28 Frida 验证**：真机 gadget 注入后，三处首选 Hook 点均成功 `Interceptor.attach`；主界面 90s 内 `WordingManager.Get` 19 次、`CustomTextMesh.SetText` 13 次；`SetWordsInfo` 未触发（未进剧情）。

## 推荐 Hook 点（按优先级）

偏移来源：`frida/lib/offsets.js`（**IDA 函数入口 RVA**，见 [ida-verification.md](./ida-verification.md)）。真机地址 = `libil2cpp.so.base + RVA`（ASLR 只影响 base，不影响 RVA）。

```
剧情文本  → TalkWindow.SetWordsInfo              @ 0x6264FD8   替换 X2（角色名）/ X3（正文）
UI 词表   → WordingManager.Get 实现体（GetImpl）  @ 0x60282AC   onLeave 替换返回值 ✅
UI 格式   → WordingManager.GetFormat              @ 0x602F054   带占位符文案
UI key    → CustomTextMesh.SetWordingText         @ 0x4F2B408   onEnter 读 key
UI 显示   → CustomTextMesh.SetText                @ 0x4F27530   替换 X1（显示前兜底）
UI slot   → CustomTextMesh.SetText（ICustomText） @ 0x4F2B590   UpdateWordingText tail-call 目标
字体注入  → FontAssetManager.SetupBuiltinFontAsset  @ 0x61028AC   注入 CJK fallback
次级兜底  → TMP_Text.set_text                     @ 0xA8D1B98   替换 X1（所有 TMP 文本）
```

**勿 Hook**：`WordingManager.Get` 静态包装器 `0x60241BC`（tail-call `BR X3`，`onLeave` 读返回值不可靠）；`UpdateWordingText onLeave` 同理。

## 策略说明

| 层级 | 函数 | 优势 | 劣势 | Frida 验证 |
|------|------|------|------|------------|
| 剧情 | `SetWordsInfo` | 在打字机效果之前拦截；参数明确；调用者少 | 仅覆盖剧情对话 | ✅ 明文读取 + `[TEST]` 可见替换（cid=21） |
| UI | `WordingManager.GetImpl` | 一次 Hook 覆盖大部分词表 lookup；`onLeave` 可替换返回值 | 实现体非 metadata 独立符号，偏移需 IDA 定位 | ✅ `WORD_DECIDE` 等可见 `[TEST]` |
| UI | `SetWordingText` | 直接拿到词表 key | 不经过此处的不覆盖 | ✅ key 读取 |
| 兜底 | `CustomTextMesh.SetText` / slot | 覆盖显示链路末端 | 调用频繁；slot 与 impl 需分清 | ✅ 有调用 |
| 字体 | `SetupBuiltinFontAsset` | 在字体加载时注入 fallback | 需准备 CJK TMP_FontAsset | 未测 |
| 底层 | `TMP_Text.set_text` | 覆盖所有 TMP 文本 | 范围过宽；剧情初段计数为 0 | ⏳ 待主界面补测 |

## 结论

- 静态 + 动态验证表明：**首选 Hook 点的 IDA 偏移在真机运行时正确**，可作为 Zygisk native Hook 的地址依据。
- UI 拦截主点：**`WordingManager.GetImpl` `onLeave`**；辅以 `CustomTextMesh.SetText` / slot 与 `SetWordingText`（读 key）。剧情首选 `SetWordsInfo`。
- 字体方案优先考虑向 `TMP_FontAsset.fallbackFontAssetTable` 注入含 CJK 字符的子集字体。

---

## 版本更新与偏移维护

### 分析目标

明确 `offsets.js` 中 RVA 与游戏版本的关系，以及 APK 更新后的重验证流程。

### 过程

1. `offsets.js` 记录的是**某一版** `libil2cpp.so` 的 IDA 入口 RVA，绑定当前分析 APK（真机曾装 **6.5.5**，本地 `apk/` versionName 待确认）。
2. 游戏更新 → `libil2cpp.so` 重编译 → **RVA 通常会整体变化**；`mod.base`（ASLR）每次启动也变，但脚本用 `base + RVA` 动态计算，**无需手改 base**。
3. `frida/run.py probe` 仅检查 `base + RVA` 是否落在可执行区（`r-x`），**不验证是否为目标函数**；版本错位时可能 Hook 到错误代码或静默失效。
4. 相对稳定、更新后往往仍可用：类名/方法名（Il2CppDumper）、Hook 策略、词表 key 字符串、`il2cpp_string_*` 导出符号名。metadata 解密流程则可能随版本变化（见 [bg.md](./bg.md)）。

### 结论

| 变更类型 | 是否需更新 offsets | 备注 |
|----------|-------------------|------|
| 小版本 / hotfix（so 重编） | ✅ 是 | 最常见 |
| 仅资源包更新（so 不变） | ❌ 否 | 需确认 split 是否含新 `libil2cpp.so` |
| 类/方法重命名或删除 | ✅ 是 | 运行时解析亦失败 |
| ASLR | ❌ 否 | 已由 `base + RVA` 处理 |

**更新流程**（对应 [TODO.md](../TODO.md) P6）：

```
新版本 APK
  → metadata 解密（格式变则先处理）
  → Il2CppDumper → script.json
  → IDA 核对函数入口（Hook 以 IDA 为准）
  → 更新 frida/lib/offsets.js（注明 versionName）
  → uv run python frida/run.py probe
  → intercept / monitor 真机 E2E
```

Zygisk 阶段建议：`versionName → offsets` 映射表；特征码扫描为可选增强（未实施）。

---

## 生产注入框架（Zygisk / LSPatch / LSPosed）

### 分析目标

明确 Frida 原型之后，正式 Mod 的注入方式与 Hook 机制是否仍依赖 offset。

### 过程

本项目主路线为 **Zygisk**（Magisk 模块早期注入 native `.so`），无 root 备选为 **LSPatch**（重打包注入）；**LSPosed 未列入当前计划**。Frida gadget 仅作原型验证。

IL2CPP 游戏的核心逻辑在 `libil2cpp.so`，`WordingManager.Get`、`TalkWindow.SetWordsInfo` 等**不在 Java 层**。无论 Zygisk、LSPatch、LSPosed 还是 Frida，文本 Hook 的实质均为：

```
注入层（Frida / Zygisk / LSPatch / LSPosed+loadLibrary）
  → native .so（ShadowHook / Dobby）
  → libil2cpp.so.base + IDA RVA
  → il2cpp_string_new 等构造替换串
```

LSPosed 若采用，典型形态是 **Xposed 模块壳 + `System.loadLibrary`**，内核与 Zygisk 共用同一份 native Hook 库；**不能**仅靠 Java/Xposed API 直接 Hook 上述 IL2CPP 方法。

### 结论

- **换注入框架不改变 offset 维护需求**；变的是进进程方式，不是 Hook 原理。
- 计划封装：参照 gakuen-imas-localify，用 Frida 已验证偏移 + ShadowHook/Dobby（见 [bg.md](./bg.md) §3.3）。

---

## 运行时 IL2CPP 解析（`il2cpp_*` API）

### 分析目标

评估用 `il2cpp_class_from_name` → `il2cpp_class_get_method_from_name` → `MethodInfo::methodPointer` 替代硬编码 RVA 的可行性与陷阱。

### 手段

- Il2CppDumper `script.json` 的 `Address` 与 `methodPointer` 同源
- IDA 入口 vs Dumper 地址偏差（见 [ida-verification.md](./ida-verification.md)）
- Frida 已验证的包装器 / 实现体 / tail-call 行为（见 [frida.md](./frida.md) §6）

### 过程

**运行时解析能带来的好处：**

- 小版本 so 重编后自动拿到新 `methodPointer`，少改十六进制常量
- 用 `Sekai.WordingManager` + `Get` 等符号自描述，便于 Zygisk 配置

**主要陷阱（按严重程度）：**

| 坑 | 说明 | PJSK 实例 |
|----|------|-----------|
| 解析指针 ≠ 应 Hook 的入口 | `methodPointer` 常指向 **metadata 登记入口**，不一定是 IDA 最佳落点或实现体 | `Get` 解析得包装器 `~0x60241BC`，intercept 需 **GetImpl `0x60282AC`** |
| 包装器 vs 实现体 | 静态方法包装器 tail-call（`BR X3`），`onLeave` 不可靠 | 已弃用 `0x60241BC` onLeave |
| 接口 slot vs 实现体 | 虚调用 / tail-call 走 slot | `SetText` impl `0x4F27530` vs slot `0x4F2B590` |
| `methodPointer` vs IDA 入口 | codegen 前缀偏差 `0x50`~`0xF0` | `CustomTextMesh.SetText`：Dumper `0x4F27590`，IDA `0x4F27530` |
| 注入时机 | Zygisk 注入早于 `il2cpp_init`，过早 resolve 得 null | 需等 `il2cpp_domain_get` 非空 |
| 重载 / 程序集 | 需正确 `param_count` 与 image（`Assembly-CSharp`） | `Get(string)` vs `GetFormat(string, object[])` |
| 导出裁剪 | 部分游戏 strip `il2cpp_*` 导出 | 当前版可用（Frida 已调 `il2cpp_string_*`） |
| 版本语义变更 | 类改名、逻辑内联、管线切换 | 与硬编码 offset 同样失效 |

`probe` 对运行时解析**无帮助**：`methodPointer` 落在 `r-x` 仍可能是错误函数。

### 结论

- **推荐混合方案**，非二选一：
  1. 简单、入口一致的方法（如 `TalkWindow.SetWordsInfo`）可全托管运行时解析作**版本锚点**。
  2. 包装器/实现体分裂、`tail-call`、接口 slot 等点：**仍以 IDA 入口为准**；解析结果仅作校验或 `wrapper → impl` 的 delta 参考。
  3. 解析失败时 fallback：`versionName → offsets` 表（`offsets.js`）。
- 运行时解析替代的是「查表拿地址」，**不替代**「分析该 Hook 哪」；P6 重验证流程仍不可省略。
- native 字符串替换仍依赖 `il2cpp_string_new` / `il2cpp_string_chars`（与解析正交）。

## 未覆盖 UI 路径与补 Hook 候选（2026-06-28）

### 分析目标

在「词表 Get + 剧情 SetWordsInfo」之外，定位仍显示日文的 UI 旁路，并给出优先级与 IDA 入口。

### 手段

- `dump.cs` + IDA 反汇编（`MusicInfoContent.SetupMusicInfo`、`CustomText.UpdateWordingText`、`TalkWindow.SetText`）
- 对照 `intercept.js` `UI_MODE=cn` 逻辑

### 过程

**根因摘要**（详见 [text-rendering.md](./text-rendering.md) §UI 覆盖分层）：

1. **Master 明文直写**：`SetupMusicInfo` 等对 `CustomTextMesh.SetText(slot)` 传入 `MasterMusic.title` 等，不经 `WordingManager.Get`。
2. **脚本缺口**：`UI_MODE=cn` 时 `prefixEnterArg` 跳过 `SetText` 替换，明文显示层无操作。
3. **`CustomText`**：与 `CustomTextMesh` 同实现 `ICustomText`，明文走 Unity `Text.set_text`，RVA 独立。
4. **词表数据缺口**：306 日服独有 key、`MSG_STARTAPP_*` 不在 CN diff。

**补 Hook / 数据候选（IDA 入口 RVA）**：

| 优先级 | 符号 | RVA | 用途 |
|--------|------|-----|------|
| P0 | `CustomTextMesh.SetText` / slot | `0x4F27530` / `0x4F2B590` | Master 明文显示；**cn 模式须启用明文 lookup** |
| P0 | （数据）CN `music.json` / `gameCharacters.json` | — | `SetText` 按日文字符串 lookup |
| P1 | `CustomText.SetText` slot | `0x4F2B1B4` | legacy Text 明文 |
| P1 | `CustomText.UpdateWordingText` | `0x4F2AF14` | 监控 / 与 Mesh 对称 |
| P1 | `CustomText.SetWordingText` | `0x4F2B02C` | 读 key（词表路径已由 Get 覆盖） |
| P2 | `TMP_Text.set_text` | `0xA8D1B98` | `TextMeshProUGUI` 直连兜底 |
| P2 | `TalkWindow.SetText` | `0x6269A6C` | 打字机刷新；若 `SetWordsInfo` 已替换则通常冗余 |
| P2 | `TalkWindow.SetLabel` | `0x6269A20` | 角色名标签刷新 |
| P3 | `MusicInfoContent.SetupMusicInfo` | `0x5FE6860` | 按 ID 翻译（比 SetText 泛化更难维护） |

**推荐实施顺序**：

```
1. i18n-tools 扩展：CN diff → music / gameCharacters / cards 等「原文→中文」表
2. intercept.js：UI_MODE=cn 时 SetText(slot/impl) onEnter 按原文 lookup（保留 Get key lookup）
3. offsets.js + intercept：补 CustomText.SetText(slot)
4. 真机 E2E：曲名列表 vs 菜单按钮对照
5. 仍漏：启用 TMP_Text.set_text 兜底
```

### 结论

- 未覆盖 UI **不是**「漏了另一个词表类」，而是 **Master 明文 + SetText 显示层在 cn 模式下未替换**。
- 词表 Hook 保持；下一增量重点是 **明文映射表 + SetText Hook 启用**。

## 下一步

1. **数据 + 脚本**：CN Master 明文表；`intercept.js` cn 模式 `SetText` lookup。
2. **Frida E2E**（游戏就绪）：词表 UI vs 曲名/角色名 Master UI 对照。
3. **Zygisk**：已验证偏移 + 混合 resolve；明文表与词表一并打包进 `i18n/`。
4. **版本维护**：P6 checklist；`offsets.js` 补 `CustomText.*`。

## 相关笔记

- Frida 联调细节：[frida.md](./frida.md)
- 双语字幕（暂缓）：[dual-subtitle.md](./dual-subtitle.md)
- 环境与阻塞项：[toolchain.md](./toolchain.md)