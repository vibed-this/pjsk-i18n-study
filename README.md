# pjsk-i18n-study

**Project SEKAI（世界计划）** 日服 Android 客户端中文本地化 Mod 的逆向研究与原型仓库。

本仓库记录从 metadata 解密、IL2CPP 分析、Frida Hook 验证，到国服翻译数据管线与剧情 asset 提取的完整研究路径。目标是在不替换游戏资源包的前提下，于运行时注入国服 UI 词表与剧情译文，并替换 CJK 字体以消除缺字（tofu）。

> **声明**：仅供技术研究与交流。仓库**不包含**游戏 APK、解密 metadata、`libil2cpp.so` 等大体积或受版权保护的文件；请勿将本仓库用于商业分发或违反游戏服务条款的行为。

## 现状（2026-06）

| 模块 | 进度 | 说明 |
|------|------|------|
| UI 词表替换 | ✅ Frida E2E | `WordingManager.GetImpl` + 国服 `wordings.json`（4838 key） |
| UI 明文替换 | 🔧 已构建 | `plain-text.json`（3440 条）；`SetText` 链路透传待补测 |
| 剧情替换 | 🔧 数据就绪 | 活动剧情 1498 话 → 114,859 条 `jp→zh`；`STORY_MODE=cn` 待真机 E2E |
| 字体注入 | 🔧 管线就绪 | 主字体替换策略 + Unity 烘焙项目；bundle 真机验收进行中 |
| Zygisk 模块 | ⏳ 未开始 | 计划在 Frida 原型稳定后参照 gakuen-imas-localify |

当前焦点与待办见 [TODO.md](TODO.md)。

## 技术路线

```
metadata 解密 → Il2CppDumper → IDA 验证 → Frida 原型 → Zygisk 模块
```

1. **静态分析**：`global-metadata.dat` 解密 → 类/方法 RVA → IDA 确认 Hook 入口  
2. **数据管线**：国服 Master diff → `i18n/ui/*.json`；官方 CDN scenario → `i18n/story/text.json`  
3. **动态验证**：frida-gadget 补丁 APK → `intercept` / `monitor` 真机联调  
4. **量产方向**：native Hook + 加载 `i18n/` 翻译包（ShadowHook / Dobby）

## 仓库结构

```
├── notes/              # 研究笔记（按主题组织，索引见 notes/README.md）
├── TODO.md             # 任务队列（单一来源）
├── i18n/               # 构建产物：UI 词表、剧情表、manifest、gap 报告
├── i18n-data/          # 数据源配置、override、fixtures（cache 不提交）
├── i18n-tools/         # pjsk-i18n CLI：fetch / build / story-build / font-chars
│   ├── scripts/        # scenario CDN 下载与 bundle 提取脚本
│   └── font-bake-unity/# 思源黑体 TMP_FontAsset 烘焙（Unity）
├── frida/              # Frida 联调：gadget 补丁、Hook 脚本、run.py
└── Agents.md           # AI Agent 分析流程规范
```

**不纳入 git**（见 `.gitignore`）：`apk/`、`dump/`、`*.i64`、`i18n-data/cache/`、字体 bundle、gadget 构建产物等。

## 快速开始

### 环境

- Windows / Linux，Python 3.12+
- [uv](https://docs.astral.sh/uv/)（依赖管理）
- 真机调试：adb、已补丁的 PJSK + frida-gadget（见 [frida/gadget/README.md](frida/gadget/README.md)）
- 剧情全量构建额外需要：[sssekai](https://github.com/mos9527/sssekai)、UnityPy

```powershell
git clone https://github.com/vibed-this/pjsk-i18n-study.git
cd pjsk-i18n-study
uv sync
```

### 构建翻译包

```powershell
# UI 词表 + Master 明文
uv run --project i18n-tools pjsk-i18n fetch
uv run --project i18n-tools pjsk-i18n build

# UI + 活动剧情（需先将 scenario JSON 放入 i18n-data/cache/scenario/{jp,cn}/）
uv run --project i18n-tools pjsk-i18n story-inventory
uv run --project i18n-tools pjsk-i18n build --with-story
```

产物路径与 checksum 见 `i18n/manifest.json`。剧情 CDN 流程见 [notes/story-pipeline.md](notes/story-pipeline.md)。

### Frida 真机联调

```powershell
# 验证 Hook 偏移（spawn）
uv run python frida/run.py probe

# UI 国服词表替换（需先 build）
uv run python frida/run.py intercept --duration 120

# 剧情 + 字体（需 bundle，见 i18n-data/font/README.md）
uv run python frida/run.py intercept --font-inject --duration 120
```

Hook 偏移以 IDA 函数入口为准（游戏版本 **6.5.5**），详见 [notes/ida-verification.md](notes/ida-verification.md)。

## 核心 Hook 点（6.5.5）

| 用途 | 方法 | IDA 入口 |
|------|------|----------|
| UI 词表 | `WordingManager.Get` 实现体 | `0x60282AC` |
| UI 明文 | `CustomTextMesh.SetText` | `0x4F27530` |
| 剧情文本 | `TalkWindow.SetWordsInfo` | `0x6264FD8` |
| 剧情上下文 | `ScenarioPlayer.SnippetActionTalk` | `0x624FC28` |
| 字体 | `FontAssetManager.SetupBuiltinFontAsset` | `0x61028AC` |

## 文档索引

| 文档 | 内容 |
|------|------|
| [notes/bg.md](notes/bg.md) | 项目背景与目标 |
| [notes/hook-strategy.md](notes/hook-strategy.md) | Hook 分层、版本维护、Zygisk 规划 |
| [notes/story-pipeline.md](notes/story-pipeline.md) | 剧情官方 CDN → story-build 全流程 |
| [notes/frida.md](notes/frida.md) | gadget 补丁与真机验证记录 |
| [i18n-tools/README.md](i18n-tools/README.md) | CLI 详细用法 |
| [frida/README.md](frida/README.md) | Frida 脚本与命令 |

## 参考项目

- [chinosk6/gakuen-imas-localify](https://github.com/chinosk6/gakuen-imas-localify) — 同类 Unity IL2CPP 本地化架构参考  
- [mos9527/sssekai](https://github.com/mos9527/sssekai) — PJSK metadata 解密与 AssetBundle 工具  
- [Sekai-World/sekai-master-db-diff](https://github.com/Sekai-World/sekai-master-db-diff) — 国服 Master 差分（UI 词表来源）

## 许可证

研究笔记、脚本与构建管线代码以本仓库声明为准。游戏资产、商标与译文内容版权归各自权利人所有；二次分发时请遵守相关法律法规与服务条款。