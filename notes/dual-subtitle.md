# 剧情双语字幕

> 前置：文本组件见 [text-rendering.md](./text-rendering.md)；剧情 Hook 见 [hook-strategy.md](./hook-strategy.md)、[frida.md](./frida.md)、[ida-verification.md](./ida-verification.md)。**本主题暂缓实施**，待打字机机制调研后再继续。

## 分析目标

评估 PJSK 剧情对话能否实现**双语字幕**（上行译文 + 下行原文，类似 ruby / 双轨字幕），并记录已试方案、失败原因与后续方向。

与「单行替换为纯中文」不同：双语字幕要求**同时展示两种语言**，且尽量不破坏原作打字机体验。

## 手段

| 手段 | 说明 |
|------|------|
| 静态分析 | `TalkWindow` 字段（`wordsLabel` / `wordsOutlineLabel`）；`SetWordsInfo` → `AddLog` tail-call（[ida-verification.md](./ida-verification.md)） |
| Frida 原型 | `frida/run.py intercept --story-mode dual`；`frida/scripts/intercept.js` 中 `DEMO_ZH` + `[[...]]` 译文行标记 |
| 真机 | Lenovo TB322FC，gadget，剧情 cid=21（ミク）样本 |

## 过程

### 1. 需求分层（2026-06-28）

| 层级 | 描述 | 预期难度 |
|------|------|----------|
| 行级双字幕 | 一行 `[[译文]]` + 一行原文 | 中（打字机时机） |
| 字级 ruby | 汉字上方悬浮假名 | 高（无原生层） |

[text-rendering.md](./text-rendering.md) 已确认：剧情**无**独立振假名渲染层；`ruby` 字段在角色 Master，不适用于对话正文。

### 2. Frida 注入点

剧情明文经 `TalkWindow.SetWordsInfo` @ `0x6264FD8` 写入，在打字机**之前**（见 [hook-strategy.md](./hook-strategy.md)）。`onEnter` 替换 `X2`（角色名）/ `X3`（正文）已在 [frida.md](./frida.md) §5 完成 E2E 验证。

双字幕原型在 `SetWordsInfo` 一次性拼接：

```
[[译文内容]]
原文日文…
```

- 译文行用 `[[...]]` 包裹，便于调试识别（`DUAL_TAG='[['` 防重复注入）。
- 无词表条目时占位 `[[译]]`；demo 词表见 `intercept.js` 内 `DEMO_ZH`。

### 3. 方案 A：`plain` 双行纯文本

**命令**：`uv run python frida/run.py intercept --story-mode dual --dual-style plain`

**现象**：

- 双行内容**可以显示**。
- 打字机对整串（含 `\n`）逐字揭示，两行**分别被打字机推进**，节奏割裂，观感异常。

**样本**（cid=21）：

| 字段 | 原文 | 替换后（预期） |
|------|------|----------------|
| 正文 | `こんにちは。\nここに…` | `[[你好。这里居然…]]\nこんにちは。\n…` |
| 角色名 | `ミク` | `[[初音未来]]\nミク` |

**实现踩坑**：初版 `alreadyDualSubtitle` 用「文本含 `\n` 且包含自身」判断，导致**多行日文正文被误判为已处理**、跳过替换；已改为仅识别以 `[[` 开头。

### 4. 方案 B：`rich` TMP 富文本

**命令**：`--dual-style rich`，下行原文包 `<size=75%><color=#888888>…</color></size>`。

**现象**：

- 打字机**逐字显示标签字符**，打字过程中 `<size=75%>` 等会裸露在屏幕上。
- **不可用**于「边打边显」流程。

### 5. 根因归纳

打字机按**可见字符索引**推进，不解析：

- 换行（行语义）
- TMP 标签（ markup 语义）

在 `SetWordsInfo` 阶段塞入双行或富文本，会把译文行与标签一并纳入打字队列。

## 结论

| 项 | 结论 |
|----|------|
| 行级双字幕（静态） | ✅ 字符串拼接 + `SetWordsInfo` 可写到屏幕 |
| 与打字机共存 | ❌ 当前「一次性注入」方案不可用；plain 观感差，rich 露标签 |
| 推荐暂缓 | 先完成单行中文替换与 Zygisk；双语字幕单独立项，后续再攻 |
| 译文行标记 | 调试期保留 `[[...]]` 约定 |

### 后续方向（待验证，未实施）

| 优先级 | 方案 | 思路 |
|--------|------|------|
| 1 | **两阶段提交** | `SetWordsInfo` 仅保留 JP；打字完成后再注入 `[[译]]` 或更新第二 label |
| 2 | **物理双 label** | `wordsLabel` 只打 JP；独立 `CustomTextMesh` 在完成后显示译文（无打字机） |
| 3 | **可选禁用打字机** | Mod 设置「瞬间显示」，双行 plain 一次展示 |
| 4 | 字级 ruby | 暂不投入；需自定义排版或顶点级 TMP |

### 待调研 Hook 候选

| 符号 | IDA 偏移 | 用途 |
|------|----------|------|
| `TalkWindow.SetWordsInfo` | `0x6264FD8` | 阶段 1：仅 JP |
| `TalkWindow.AddLog` | `0x6268DD0` | `SetWordsInfo` tail-call；观察每句生命周期 |
| `CustomTextMesh` / TMP | 待定 | `maxVisibleCharacters` 或打完判定 |
| `wordsOutlineLabel` | 待定 | 疑似描边复制层，**不宜**默认作第二字幕 |

### 原型命令索引

```powershell
uv run python frida/run.py intercept --story-mode dual --dual-style plain
uv run python frida/run.py intercept --story-mode dual --dual-style rich
```

### 6. 双语混排与字体（2026-06-29）

与 [text-rendering.md](./text-rendering.md) §初步汉化字体策略衔接：UI/单行简中采用**全局主字体替换**；双字幕因 JP+CN **同屏混排**，策略不同。

#### 问题

双字幕字符串形如：

```
[[你好。这里居然…]]     ← 简中
こんにちは。            ← 日文
```

若写入**同一** `wordsLabel` 且只配置一条 TMP 主字体 + fallback 链：

| 主字体 | 简中行 | 日文行 |
|--------|--------|--------|
| 思源 SC | ✅ 简体字形 | ⚠️ 假名可显示；与简中**共用码位的汉字**显示中国形（非日文形） |
| EB/DB | ⚠️ 简体专用字靠 fallback；共用汉字为日本形 | ✅ 日文形 |

**结论**：单 label、单主字体无法让两行同时满足区域字形；fallback 只解决**缺字**，不解决**同码位不同字形**。

#### 推荐方案（按优先级）

| 优先级 | 方案 | 字体处理 |
|--------|------|----------|
| **1** | **物理双 label**（见 §后续方向 #2） | 日文 label → `font` = EB/DB（游戏默认）；译文 label → `font` = 思源 SC `TMP_FontAsset`。各走各的 atlas，无混排冲突。`wordsOutlineLabel` 须与对应正文 label **同步**字体。 |
| **2** | **两阶段 + `<font>` 标签** | 阶段 1：label 仅 JP，EB/DB 打字。阶段 2：打字完成后追加/更新译文，用 `<font="SourceHanSansSC-Regular SDF">译文</font>` 包简中段（需两资产已 `LoadAsset`）。 |
| **3** | **单 label 妥协** | SC 主 + EB/DB fallback：接受日文行汉字「中国形」；仅作过渡，不作终态。 |

#### 与全局字体替换的关系

| `STORY_MODE` | 字体 Mod 行为 |
|--------------|----------------|
| `cn` / UI `UI_MODE=cn` | `SetupBuiltinFontAsset` onLeave **替换** EB/DB 为 SC 主字体 |
| `dual` | **不**做全局替换；保留 EB/DB 给日文 label；另载 SC bundle，仅绑译文 label 或 rich 段 |
| `prefix` / 默认 | 可不注入字体，或仅 EB/DB |

实现要点：

- 运行时同时保留 **EB/DB + 思源 SC** 三份（或两份：SC + EB/DB）`TMP_FontAsset` 引用。
- `font_inject.js` 宜支持 `FONT_MODE=replace|dual`：`dual` 只加载 SC 资产到缓存，不改 `FontAssetManager+0x20/0x38`。
- 第二 label 若运行时创建，材质/Shader 须与 `CustomTextMesh` 一致（复用 EB 的 material 模板或 SC 烘焙材质）。

#### 与打字机、富文本的叠加

- **plain 双行单 label**：字体混排问题如上；打字机两行分别推进（§方案 A）— 字体与节奏双重问题 → 仍推荐双 label。
- **rich 边打边显**：标签裸露（§方案 B）— 与 `<font>` 无关，打字完成后再用 rich 可同时解决**节奏 + 分字体**。

### 开放问题

- [ ] 打字机完成事件 / `maxVisibleCharacters` 稳定判定
- [ ] 是否存在可复用第二 label 或需运行时挂节点
- [ ] 双行布局与对话框高度、立绘遮挡
- [x] 双语混排字体：单主字体不可行 → **双 label 分字体** 或 **打字后 `<font>` 分段**（见 §6）
- [ ] 译文 label 复用 `wordsOutlineLabel` 是否安全（描边复制层 vs 独立节点）
- [x] `FONT_MODE=dual`：`font_inject.js` 仅加载 SC，不替换 EB/DB

## 相关笔记

- [frida.md](./frida.md) — gadget 联调、剧情 intercept 验证
- [hook-strategy.md](./hook-strategy.md) — 剧情首选 `SetWordsInfo`
- [text-rendering.md](./text-rendering.md) — `TalkWindow` 组件结构
- [TODO.md](../TODO.md) — P2 功能扩展条目