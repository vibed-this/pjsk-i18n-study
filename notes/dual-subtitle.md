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

### 开放问题

- [ ] 打字机完成事件 / `maxVisibleCharacters` 稳定判定
- [ ] 是否存在可复用第二 label 或需运行时挂节点
- [ ] 双行布局与对话框高度、立绘遮挡
- [ ] 与 CJK 字体注入的叠加（译文行中文可能 tofu）

## 相关笔记

- [frida.md](./frida.md) — gadget 联调、剧情 intercept 验证
- [hook-strategy.md](./hook-strategy.md) — 剧情首选 `SetWordsInfo`
- [text-rendering.md](./text-rendering.md) — `TalkWindow` 组件结构
- [TODO.md](../TODO.md) — P2 功能扩展条目