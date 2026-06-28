# 待办事项

> 项目路线：`metadata 解密 → Il2CppDumper → IDA 验证 → Frida 原型 → Zygisk 模块`  
> 背景见 [notes/bg.md](notes/bg.md)。技术笔记见 [notes/README.md](notes/README.md)。

**状态标记**：`[ ]` 待办 · `[~]` 进行中 · `[x]` 完成 · `[-]` 搁置

---

## 当前焦点

**游戏 APK 下载中，设备已断开** — 阻塞项：真机 Frida 联调。

**静态分析结论（2026-06-28）**：当前两路 Hook（`WordingManager.Get` + `TalkWindow.SetWordsInfo`）只覆盖 **词表 key 类 UI** 与 **剧情明文**。未覆盖的 UI 主要来自：

1. **Master 表直出明文**（曲名/角色名/卡片技能等）→ `CustomTextMesh.SetText(slot)` 直写，不经 `Get`
2. **`UI_MODE=cn` 下 `SetText` Hook 被跳过**（`intercept.js` `prefixEnterArg` 早退）→ 明文显示层无替换
3. **`CustomText`**（legacy Unity Text，dump 约 140 处）→ 自有 `SetText` slot `0x4F2B1B4`，未 Hook
4. **数据缺口**：306 日服独有 key、`MSG_STARTAPP_*` 不在 CN diff

详见 [notes/text-rendering.md](notes/text-rendering.md) §UI 覆盖分层、[notes/hook-strategy.md](notes/hook-strategy.md) §未覆盖 UI 路径。

**下载完成后第一件事**：

1. 确认 `versionName` 与 `offsets.js`（6.5.5）一致 → `probe`
2. `intercept` E2E：词表 UI（确定/取消）+ 曲名/角色名等 Master 明文是否仍为日文
3. 若词表 OK、明文仍日文：在 `intercept.js` 为 `UI_MODE=cn` 启用 `SetText` 明文替换（需扩展 Master 映射表）
4. 核对 `Get` 的 `args[0]` 与 `intercept` 日志

---

## P0 — Frida 真机验证（阻塞后续）

- [ ] **国服词表 `intercept` E2E**：`UI_MODE=cn`，样本 `WORD_DECIDE`→确定、`WORD_CANCEL`→取消（游戏就绪后）
- [ ] **Master 明文 UI 补测**：曲名列表/角色名等（预期当前仍为日文，验证静态分析）
- [ ] **`UI_MODE=cn` + `SetText` E2E**：真机验证角色名/卡片文案等 Master 明文（游戏就绪后）
- [ ] **主界面菜单 `intercept`**：非剧情 dialog 的菜单按钮应显示简中
- [ ] **主界面 `monitor` 补测**：`TMP_Text.set_text` 在主界面调用与读串
- [ ] 确认设备 `versionName` 与本地 `apk/`、`offsets.js` 一致
- [x] **剧情 `SetWordsInfo` 验证**（前缀模式，见 notes/frida.md §4–5）
- [x] **UI 词表 `intercept` 验证**（`[TEST]` 前缀模式，见 notes/frida.md §6）
- [x] **UI 拦截策略确定**：`WordingManager.GetImpl` `onLeave` + key lookup

---

## P1 — 笔记与脚本同步

- [ ] 更新 [notes/frida.md](notes/frida.md)：`UI_MODE=cn`、`i18n-tools` 用法；删除旧脚本引用
- [x] [notes/hook-strategy.md](notes/hook-strategy.md)：版本维护 / 注入框架 / 运行时解析
- [x] [notes/text-rendering.md](notes/text-rendering.md)：国服 diff 与翻译包结构
- [ ] 修正 [notes/ida-verification.md](notes/ida-verification.md)：`SetText` 调用方 `X1` 多为空
- [ ] 关闭 [notes/bg.md](notes/bg.md) 中过时开放问题

---

## P2 — 剧情双语字幕（暂缓）

> 见 [notes/dual-subtitle.md](notes/dual-subtitle.md)。当前优先 UI 国服词表 + 单行剧情。

---

## P3 — 翻译数据管线

- [x] **i18n-tools**：`pjsk-i18n fetch/build` → `i18n/ui/wordings.json` + `manifest.json` + `gap-report.json`
- [x] **Frida 接入**：`run.py` 注入 `UI_WORDINGS`；`intercept.js` key → zh
- [ ] **真机 E2E**（P0，游戏下载后）
- [x] **Master 明文映射**：`pjsk-i18n build` → `i18n/ui/plain-text.json`（3440 jp→zh，musics/characters/cards/vocals/profiles）
- [x] **`intercept.js` cn + SetText**：`UI_PLAIN_TEXT` 明文 lookup；`CustomText.SetText(slot)` Hook
- [ ] `overrides/ui.yaml`：`MSG_STARTAPP_*`、日服独有 306 key（见 `i18n/reports/gap-report.json`）
- [~] **剧情国服挪用**：`pjsk-i18n story-inventory` + `story-build` → `i18n/story/text.json`；Frida `STORY_MODE=cn` 已接入；**待** `cache/scenario/` 全量 AssetBundle + 真机 E2E
- [x] 剧情 gap 清单：`story-inventory` → common=3882 / jp_only=476（`i18n-data/cache/scenario-inventory.json`）
- [ ] 翻译包热更新路径（manifest checksum 已有）

---

## P4 — Zygisk 模块

- [ ] 参照 gakuen-imas-localify 搭建 native 骨架（ShadowHook / Dobby）
- [ ] 三处 native Hook + `il2cpp_string_*` + 加载 `i18n/ui/wordings.json`
- [ ] 无 root 备选：LSPatch（低于 Zygisk）

---

## P5 — 字体注入

- [ ] `SetupBuiltinFontAsset` 调用时机验证
- [ ] CJK TMP_FontAsset + fallback 注入
- [ ] 真机无 tofu（国服词表 E2E 后优先）

---

## P6 — 资源与版本维护

- [ ] 游戏更新后：Il2CppDumper → IDA → `offsets.js` → `probe`（见 hook-strategy §版本更新）
- [ ] diff 更新后：`pjsk-i18n build` 并核对 `gap-report`
- [ ] AssetBundle XOR 解密脚本化

---

## 已完成

- [x] metadata 解密、Il2CppDumper、IDA 核心 Hook 验证
- [x] frida-gadget 真机补丁（TB322FC）
- [x] Frida `lib/` + `scripts/` + `run.py`；剧情 + UI `[TEST]` intercept E2E
- [x] 词表静态链路、国服 CN diff 调研、i18n-tools 构建管线

---

## 搁置 / 阻塞

- [-] **当前阻塞**：游戏下载中，无设备连接
- [-] 模拟器 frida-server；Master 缓存解密；内置词表提取脚本

---

## 相关命令

```powershell
uv sync

# 构建 UI 词表（国服 diff）
uv run --project i18n-tools pjsk-i18n build

# 剧情演示包（fixtures，无需 AssetBundle）
uv run --project i18n-tools pjsk-i18n story-build --demo

# 真机 intercept（自动 UI_MODE=cn / STORY_MODE=cn 若对应 json 存在）
uv run python frida/run.py intercept --duration 120

uv run python frida/run.py monitor --duration 120
uv run python frida/run.py probe
```