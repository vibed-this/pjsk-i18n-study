# Agent 工作说明

本文档约束 AI Agent 在本项目中的分析流程与笔记维护规范。

## 项目概要

PJSK（世界计划）Android 端中文本地化 Mod 的逆向研究仓库。核心路线：

```
metadata 解密 → Il2CppDumper → IDA 验证 → Frida 原型 → Zygisk 模块
```

背景与目标见 [notes/bg.md](notes/bg.md)。笔记按**主题**组织，索引见 [notes/README.md](notes/README.md)。

---

## 每次分析的标准流程

进行任何技术分析之前和完成之后，**必须**执行以下步骤。

### 1. 分析前：检索已有情报

在 `notes/` 目录下检索，确认目标问题是否已有记录：

1. 阅读 [notes/README.md](notes/README.md)，定位可能相关的主题文件。
2. 用关键词搜索 `notes/`（类名、函数名、偏移、工具名、文件名等）。
3. 若情报涉及外部资源，同时检查 [notes/ref.md](notes/ref.md) 是否已收录对应 URL。

**禁止**在未检索的情况下重复记录已知结论，也**禁止**凭记忆覆盖已有笔记而不核对原文。

### 2. 分析中：区分新情报与补充

| 情况 | 处理方式 |
|------|----------|
| 已有记录且结论仍然正确 | 不修改，或在报告中注明「已见于 `xxx.md`」 |
| 已有记录但结论需修正 | 修改对应主题文件，在「过程」中说明修正原因 |
| 全新情报 | 按下方决策规则选择新增或追加 |
| 仅新的外部链接 | 追加到 [notes/ref.md](notes/ref.md) |

### 3. 分析后：更新笔记

获得可复用情报（结论、偏移、流程、产物路径、工具状态、阻塞项等）后，**必须**将结果写入 `notes/`。不可仅在对话中报告而不落盘。

---

## 新增文件 vs 修改已有文件

### 修改已有文件（默认首选）

当新情报属于下列已有主题之一时，**追加到对应文件**，不新建：

| 主题文件 | 适用范围 |
|----------|----------|
| [metadata.md](notes/metadata.md) | `global-metadata.dat` 提取、解密、混淆格式 |
| [il2cpp-dump.md](notes/il2cpp-dump.md) | Il2CppDumper 产物、类/方法 RVA、版本信息 |
| [text-rendering.md](notes/text-rendering.md) | 文本组件、词表系统、字体资产、振假名 |
| [ida-verification.md](notes/ida-verification.md) | IDA 反汇编验证、函数入口、参数、xref |
| [hook-strategy.md](notes/hook-strategy.md) | Hook 点选择、优先级、策略取舍、实施下一步 |
| [toolchain.md](notes/toolchain.md) | 工具安装、环境就绪状态、产物路径索引 |
| [bg.md](notes/bg.md) | 项目级背景变更、阶段性结论、开放问题状态 |
| [ref.md](notes/ref.md) | 外部 URL、参考仓库、博客链接 |

### 新增主题文件

仅当新情报构成**独立主题**，且无法自然归入上表任一文件时，才新建 `notes/<主题名>.md`：

- 文件名用英文 kebab-case 或简短中文拼音，描述主题而非日期（**禁止** `analysis-2026-xx-xx.md` 式命名）。
- 新建后**必须**更新 [notes/README.md](notes/README.md) 索引表。
- 新文件开头注明与已有笔记的关联（「前置」「见 xxx.md」）。

### 判断示例

| 新情报 | 决策 |
|--------|------|
| 确认 `TalkWindow.SetWordsInfo` 的 ARM64 参数 | 修改 `ida-verification.md` |
| 发现新的 UI 词表类 `WordingManager.GetFormat` 行为 | 修改 `text-rendering.md` + 可能 `hook-strategy.md` |
| 完成 Frida Hook 验证并记录脚本偏移 | 修改 `hook-strategy.md`；若形成完整 Frida 专题则新建 `frida.md` |
| 开始 AssetBundle XOR 解密研究 | 新建 `asset-bundle.md` |
| 找到一篇新的逆向博客 | 追加 `ref.md` |

---

## 笔记写作格式

每个主题文件（或文件内的每个独立章节）按以下四段结构组织：

```markdown
## 分析目标
（本次要解决什么问题，一句话说清楚）

## 手段
（使用的工具、脚本、数据源、MCP 工具等）

## 过程
（操作步骤、观察到的现象、中间产物）

## 结论
（最终可复用的结论；表格优先；标注待验证项）
```

### 格式要求

- 用中文撰写，技术符号（类名、偏移、寄存器）保留英文。
- 地址统一写 `0x` 前缀十六进制；Hook 地址以 **IDA 函数入口**为准。
- 文件间用「相关笔记」章节互链，避免大段复制粘贴。
- 不在笔记中记录对话过程或 Agent 内心推理，只记可复用情报。
- 不创建按日期命名的文件；进度通过修改对应主题文件体现。

---

## 工具与环境约束

- 大型二进制、dump 产物、IDA 数据库**不提交 git**（见 `.gitignore`）。笔记中只记路径与结论，不嵌入大二进制。
- IDA 分析优先通过 **IDA Pro MCP** 直接调用工具，不要绕路发 HTTP 请求。
- APK / metadata / dump 产物路径索引维护在 [toolchain.md](notes/toolchain.md)。

---

## 分析会话检查清单

每次分析结束前，逐项确认：

- [ ] 已在 `notes/` 检索，确认情报是否重复
- [ ] 新结论已写入正确的主题文件（或已新建主题文件并更新 README）
- [ ] 笔记包含「分析目标 / 手段 / 过程 / 结论」四段
- [ ] 相关文件间已添加交叉链接
- [ ] 若修正了旧结论，过程中说明了修正原因
- [ ] 若关闭了 `bg.md` 中的开放问题，已同步更新 `bg.md` 对应条目