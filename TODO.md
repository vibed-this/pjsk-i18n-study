# 待办事项

> 项目路线：`metadata 解密 → Il2CppDumper → IDA 验证 → Frida 原型 → Zygisk 模块`  
> 背景见 [notes/bg.md](notes/bg.md)。技术笔记见 [notes/README.md](notes/README.md)。

**状态标记**：`[ ]` 待办 · `[~]` 进行中 · `[x]` 完成 · `[-]` 搁置

---

## 当前焦点

**CJK 字体注入（P5）** — 真机已验证：`UI_MODE=cn` 词表替换成功（`wordingGet≈388`），但简中大量 tofu；剧情 demo 仅 3 条，全量 story 暂缓。

**下一步（字体）**：

1. 用 `sekai-assets-updater` `REGION=CN` 解出国服 `TMP_FontAsset` bundle（与 JP 同版本），作 fallback 源
2. Frida/IDA 验证 `FontAssetManager.SetupBuiltinFontAsset` @ `0x61028AC` 调用时机与 fallback 表字段
3. 在 `SetupBuiltinFontAsset` onLeave 向 `_builtInFont*` 的 `fallbackFontAssetTable` 注入国服 CJK 子集（或整包替换）
4. 补测 legacy `CustomText`（Unity `Text`，约 140 处）是否仍 tofu

详见 [notes/hook-strategy.md](notes/hook-strategy.md) §字体、[notes/ida-verification.md](notes/ida-verification.md) §SetupBuiltinFontAsset。

---

## P0 — Frida 真机验证（阻塞后续）

- [x] **国服词表 `intercept` E2E**：`UI_MODE=cn`，按钮/对话框简中命中；**字体 tofu**（待 P5）
- [ ] **Master 明文 UI 补测**：曲名/角色界面，`uiPlain` 是否 > 0
- [ ] **`UI_MODE=cn` + `SetText` E2E**：`mode=cn-plain` 命中
- [x] **主界面菜单 `intercept`**：非剧情 dialog 按钮已简中（字体缺字）
- [ ] **主界面 `monitor` 补测**：`TMP_Text.set_text` 在主界面调用与读串
- [x] **probe 偏移**：`base=0x7530bb4000`，11/11 Hook 可执行（6.5.5）
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
- [~] **剧情国服挪用**：管线 + Frida `STORY_MODE=cn` 已接入；全量构建 **搁置**（需 `cache/scenario/`，见下）
- [x] 剧情 gap 清单：`story-inventory` → common=3882 / jp_only=476（`i18n-data/cache/scenario-inventory.json`）
- [ ] 翻译包热更新路径（manifest checksum 已有）

---

## P4 — Zygisk 模块

- [ ] 参照 gakuen-imas-localify 搭建 native 骨架（ShadowHook / Dobby）
- [ ] 三处 native Hook + `il2cpp_string_*` + 加载 `i18n/ui/wordings.json`
- [ ] 无 root 备选：LSPatch（低于 Zygisk）

---

## P5 — 字体注入（当前焦点）

- [ ] 国服 `TMP_FontAsset` 提取：`sekai-assets-updater` `REGION=CN`，过滤 `font/` 相关 bundle（与 JP 6.5.5 对齐）
- [ ] 对比 JP/CN 字体 bundle 名与 `FontAssetManager` 字段（`_builtInFontDB/EB`、`_baseFontDB` 等）
- [~] `SetupBuiltinFontAsset` @ `0x61028AC`：`frida/run.py font` 探测脚本已加；**待**真机跑 leave 日志确认 fallbackSize
- [ ] fallback 注入原型：向 `[font+0x138]` fallback 表追加国服 CJK `TMP_FontAsset`（Zygisk 或 Frida）
- [ ] legacy `CustomText` / Unity `Text` 缺字路径（若 fallback 后仍 tofu）
- [ ] 真机：`UI_MODE=cn` 下按钮/剧情无 tofu

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

- [-] **剧情全量构建**：需 `sekai-assets-updater` JP+CN scenario → `cache/scenario/`；开场剧情已不可重进，不阻塞字体线
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

# 字体加载探测
uv run python frida/run.py font --duration 180
```