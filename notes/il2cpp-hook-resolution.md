# IL2CPP Hook 地址解析（包装器 / 实现体 / 运行时）

> 关联：[hook-strategy.md](./hook-strategy.md) §运行时 IL2CPP 解析、[ida-verification.md](./ida-verification.md) §`WordingManager.Get`、`text-rendering.md](./text-rendering.md) §UI 查表。

## 分析目标

记录 `WordingManager.GetImpl` 等特殊 Hook 点的定位方法，评估「纯硬编码 RVA」「Il2CppDumper」「`il2cpp_*` 运行时解析」「包装器 tail-call 追踪」的取舍，供版本更新与 Zygisk 迁移复用。

## 手段

- Il2CppDumper `script.json` / `dump.cs`（6.5.5、6.6.0）
- IDA Pro MCP 反汇编（Hook 入口以 **IDA 函数入口**为准）
- Capstone 离线复核（IDA 不可用时的补充）
- 社区实践：[Perfare Zygisk+Il2Cpp API](https://www.perfare.net/archives/1741)、[frida-il2cpp-bridge](https://github.com/vfsfitvnm/frida-il2cpp-bridge)、gakumas-localify `Il2cppUtils.hpp`
- 真机 Frida `intercept.js` E2E（6.5.5 已验证 `GetImpl` `onLeave`）

## 过程

### 1. 问题：`methodPointer` 不等于 Hook 入口

IL2CPP 静态方法常生成**薄包装器**（初始化静态字段 → 经 `MethodInfo` tail-call 到实现体）。`il2cpp_class_get_method_from_name` 与 Il2CppDumper 登记的 `Address` **同源**，指向包装器或 codegen 前缀区，不一定是应 Hook 的语义入口。

| 方法 | Dumper / `methodPointer` | IDA 入口（6.5.5） | Frida 实际 Hook |
|------|--------------------------|-------------------|-----------------|
| `WordingManager.Get` | `0x60242AC` | 包装器 `0x60241BC` | **实现体 `0x60282AC`（GetImpl）** |
| `TalkWindow.SetWordsInfo` | `0x6264FD8` | `0x6264FD8` | 同左（一致） |
| `CustomTextMesh.SetText` | `0x4F27590` | `0x4F27530` | IDA 入口（−`0x60` codegen 前缀） |

包装器上以 `onLeave` 替换返回值不可靠（tail-call 时 retval 尚未落在可改写的路径）。

### 2. 社区方案对比

| 方案 | 优点 | 对 `Get` 是否够用 |
|------|------|-------------------|
| 硬编码 `offsets.js` | 简单、真机已 E2E | ✅ 若 IDA 已确认 impl |
| `il2cpp_class_get_method_from_name` → `methodPointer` | 小版本免改常量 | ❌ 得包装器 |
| `frida-il2cpp-bridge` 真机 dump/trace | 无 metadata 文件也可枚举 | ❌ hijack 仍挂 `methodPointer` |
| 包装器反汇编 → tail-call 目标 | 版本内可自动化 | ✅ 宜作 GetImpl 动态解析 |
| Dumper `Get` + 固定 delta（6.5.5 为 `+0x4000`） | 快速候选 | ⚠️ 经验规律，需每版验证 |
| 改 `dictionary` 数据源 / `AddMasterWording` | 绕过 Get | ❌ 已搁置（见 text-rendering §6） |

### 3. 推荐混合策略（实施顺序）

1. **语义分裂方法**（`Get`、部分 slot/tail-call）：IDA 确认实现体 → 写入 `offsets.js`；版本更新时 IDA 复核。
2. **入口一致方法**（`SetWordsInfo` 等）：可改为运行时 `il2cpp_*` resolve，作版本锚点。
3. **可选增强**（未实施）：`resolveGetImpl()` = resolve 包装器 → Capstone/IDA 追 `B`/`BR` → fallback `metadata_Get + 0x4000` → fallback `offsets.js`。
4. **不可省略**：版本更新后 **`baseline` 命中统计** + `intercept` E2E；`probe` 仅证明可执行，不证明 Hook 点正确或参数语义对。

### 4. 版本迁移记录

#### 6.5.5（基线，真机 E2E）

| 符号 | Il2CppDumper | IDA Hook | 备注 |
|------|--------------|----------|------|
| `WordingManager.Get`（包装器） | `0x60242AC` | `0x60241BC` | 不用 onLeave |
| **`WordingManager.GetImpl`** | — | **`0x60282AC`** | `intercept` UI 查表 |
| `WordingManager.GetFormat` | `0x602F054` | 待核对 | 当前用 Dumper 邻近值 |

`GetImpl − Dumper_Get = +0x4000`（6.5.5 精确）。

#### 6.6.0（IDA 已确认，2026-06-29）

| 步骤 | 状态 |
|------|------|
| XAPK → `apk/`（`versionName=6.6.0`）、`sssekai`、`Il2CppDumper` | ✅ |
| IDA `libil2cpp.so.i64` 全表 Hook 入口 | ✅ |
| `offsets.js` 全量更新 | ✅ |
| gadget 重打 / `probe` + E2E | ✅（2026-06-29） |

**`WordingManager.Get` / GetImpl（关键结论）**

| 符号 | Il2CppDumper | IDA 入口 | 说明 |
|------|--------------|----------|------|
| `Get`（metadata stub） | `0x602B9FC` | `sub_602B9FC`（0x24） | 薄检查桩，非主逻辑 |
| **`Get` 包装器** | — | **`0x602B8C0`** | 静态 init → `sub_6456760` → **`BR X4`**（invoke） |
| **`GetImpl`** | — | **`0x60282AC`** | **RVA 与 6.5.5 相同**；`sub_72875F0(dict, key, &out)` 查表返回 |
| `+0x4000` 候选 | `0x602F9FC` | 落在 `sub_602F778` | ❌ **非 GetImpl**；6.6.0 上此经验规律失效 |

包装器 `0x602B8C0` 以 **`RET`** 结束（经 `sub_6456760` 内 `BR X4` 间接 tail-call），与 6.5.5 包装器 `0x60241BC` 直接 `BR X3` 形态不同。

**6.6.0 真机 baseline（2026-06-29）修正**：`GetImpl` / `Get_wrapper` / `SWT_impl` / `UWT_impl` **0 hit**；`Get` metadata @ `0x602B9FC`、`SWT` @ `0x4F2E9EC`、`UWT` @ `0x4F2E8D0` **有 hit**。静态上 impl 仍在 so 中，但 **Hook 须对齐 runtime 入口（methodPointer）**，非 IDA impl。

**6.6.0 Hook 表（Dumper = runtime methodPointer；生产 Hook 以 Dumper 为准）**

| 符号 | Dumper（**Hook**） | IDA / 其它 | 备注 |
|------|---------------------|------------|------|
| `WordingManager.Get` | **`0x602B9FC`** | impl `0x60282AC` | baseline impl **0 hit** |
| `WordingManager.GetFormat` | **`0x60327A4`** | impl `0x6032710` | 与 Get 同策略 |
| `CustomTextMesh.SetWordingText` | **`0x4F2E9EC`** | impl `0x4F2B408` | impl **0 hit** |
| `CustomTextMesh.UpdateWordingText` | **`0x4F2E8D0`** | impl `0x4F2B2EC` | impl **0 hit** |
| **`ScenarioPlayer.AttachSceneData`** | **`0x624F8B8`** | ~~`0x624F814`~~ ❌ | **误标**：`0x624F814` 为别函数；薄桩后实现体约 `0x624F9CC` |
| `TalkWindow.SetWordsInfo` | `0x6268830` | `0x62687FC` | cn 默认不 Hook（数据源 patch） |
| `ScenarioPlayer.SnippetActionTalk` | `0x62533E0` | `0x62533C4` | ctx 探测用 |
| `ScreenLayerScenario.OnFinishLoadScenario` | `0x63E7238` | `0x63E7170` | P1 备选 |
| `CustomTextMesh.SetText` | `0x4F2EB74` | impl **`0x4F27530`** | 实现体 RVA 未迁 |
| `CustomTextMesh.SetText`（slot） | — | `0x4F2B590` | 未迁 |
| `FontAssetManager.SetupBuiltinFontAsset` | `0x610604C` | `0x6105F88` | |
| `TMP_Text.set_text` | `0xA8E9160` | `0xA8E8E4C` | |

**`AttachSceneData` 误挂案例（2026-06-29）**

| 现象 | 原因 |
|------|------|
| `story_patch_summary None lines=0 patched=0` | Hook `0x624F814`：`args[1]` 非 `ScenarioSceneData*` |
| Capstone | `0x624F814` = 字段拷贝函数；Dumper `AttachSceneData` = **`0x624F8B8`** |
| 修复后 | `story_patch_diag` 有 `id`/`snippets`/`talk`；`patched>0`；屏幕简中 ✅ |

布局字段（`ScenarioSceneData.TalkData @+0x60`、`ScenarioSnippetTalk.Body @+0x20` 等）6.6.0 `dump.cs` 与 6.5.5 **不变**。

## 结论

| 项 | 结论 |
|----|------|
| `GetImpl` 为何特殊（6.5.5） | 无独立符号；E2E 证实须 Hook 实现体 `0x60282AC`，非包装器 |
| 6.6.0 运行时入口 | **methodPointer / Dumper 地址**；UI + 剧情 AttachSceneData 均须对齐；impl / 误标 IDA 入口可 0 hit 或参数错乱 |
| IDA「入口」陷阱 | `AttachSceneData`：`0x624F814` ≠ 该方法；须对照 `dump.cs` RVA + Capstone，勿盲信邻近符号 |
| 能否全运行时动态 | **部分能**：resolve 得 methodPointer；语义分裂方法仍要 baseline 验证 |
| 版本验证不可省略 | `baseline` hit → 改 `offsets.js` → `intercept` E2E；剧情另看 `story_patch_summary` / `story_patch_diag` |
| 量产路径（6.6.0 Frida） | UI：`Get` `0x602B9FC` `onLeave` + `wordings.json` ✅；剧情：`AttachSceneData` `0x624F8B8` + `text.json` patch ✅ |
| 兜底 | `run.py --story-fallback`：cn 时额外 Hook `SetWordsInfo` jp→zh（collision 风险） |
| 待办 | Zygisk 迁移同表；字体 bundle；`OnFinishLoadScenario` 备选 Hook |

## 相关笔记

- [hook-strategy.md](./hook-strategy.md) — 版本更新流程、Zygisk 框架
- [ida-verification.md](./ida-verification.md) — 各函数 IDA 验证表
- [toolchain.md](./toolchain.md) — 产物路径、`apk/` 6.6.0
- [ref.md](./ref.md) — 外部链接（可追加 Perfare / frida-il2cpp-bridge）