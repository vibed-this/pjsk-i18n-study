# 待办事项

> 项目路线：`metadata 解密 → Il2CppDumper → IDA 验证 → Frida 原型 → Zygisk 模块`  
> 背景见 [notes/bg.md](notes/bg.md)。技术笔记见 [notes/README.md](notes/README.md)。

**状态标记**：`[ ]` 待办 · `[~]` 进行中 · `[x]` 完成 · `[-]` 搁置

---

## 当前焦点

**CJK 字体注入（P5）** — Frida **主字体替换**与 Unity 烘焙管线已落地；**待**：`bake.ps1` 产出 bundle → 真机 `font --inject` / `intercept --font-inject` 验收无 tofu。

**下一步**：

1. `cd i18n-tools/font-bake-unity && .\bake.ps1` → `i18n/font/source-han-fallback.bundle`
2. 真机冷启动 + `uv run python frida/run.py intercept --font-inject --duration 120`
3. 补测 legacy `CustomText`（Unity `Text`）是否仍 tofu

详见 [notes/hook-strategy.md](notes/hook-strategy.md) §字体、[i18n-data/font/README.md](i18n-data/font/README.md)。

---

## P0 — Frida 真机验证（阻塞后续）

- [x] **国服词表 `intercept` E2E**：`UI_MODE=cn`，按钮/对话框简中命中；**字体 tofu**（待 P5 bundle）
- [ ] **Master 明文 UI 补测**：曲名/角色界面，`uiPlain` 是否 > 0
- [ ] **`UI_MODE=cn` + `SetText` E2E**：`mode=cn-plain` 命中
- [x] **主界面菜单 `intercept`**：非剧情 dialog 按钮已简中（字体缺字）
- [ ] **主界面 `monitor` 补测**：`TMP_Text.set_text` 在主界面调用与读串
- [x] **probe 偏移**：`base=0x7530bb4000`，11/11 Hook 可执行（6.5.5）
- [x] **剧情 `SetWordsInfo` 验证**（前缀模式，见 notes/frida.md §4–5）
- [ ] **剧情 `STORY_MODE=cn` E2E**：`i18n/story/text.json`（114,859 条）真机活动剧情抽样
- [x] **UI 词表 `intercept` 验证**（`[TEST]` 前缀模式，见 notes/frida.md §6）
- [x] **UI 拦截策略确定**：`WordingManager.GetImpl` `onLeave` + key lookup

---

## P1 — 笔记与脚本同步

- [ ] 更新 [notes/frida.md](notes/frida.md)：`UI_MODE=cn`、`i18n-tools` 用法；删除旧脚本引用
- [x] [notes/hook-strategy.md](notes/hook-strategy.md)：版本维护 / 注入框架 / 字体替换策略
- [x] [notes/text-rendering.md](notes/text-rendering.md)：国服 diff / 字体策略 / 双语混排
- [ ] 修正 [notes/ida-verification.md](notes/ida-verification.md)：`SetText` 调用方 `X1` 多为空
- [ ] 关闭 [notes/bg.md](notes/bg.md) 中过时开放问题

---

## P2 — 剧情双语字幕（暂缓）

> 见 [notes/dual-subtitle.md](notes/dual-subtitle.md)。当前优先 UI 国服词表 + 单行剧情。
> 字体：dual 模式**不做**全局 SC 替换；物理双 label 分绑 EB/DB（日）与 SC（中），或打字完成后 `<font>` 分段。

---

## P3 — 翻译数据管线

- [x] **i18n-tools**：`pjsk-i18n fetch/build` → `i18n/ui/wordings.json` + `manifest.json` + `gap-report.json`
- [x] **Frida 接入**：`run.py` 注入 `UI_WORDINGS`；`intercept.js` key → zh
- [ ] **真机 E2E**（P0，游戏下载后）
- [x] **Master 明文映射**：`pjsk-i18n build` → `i18n/ui/plain-text.json`（3440 jp→zh，musics/characters/cards/vocals/profiles）
- [x] **`intercept.js` cn + SetText**：`UI_PLAIN_TEXT` 明文 lookup；`CustomText.SetText(slot)` Hook
- [ ] `overrides/ui.yaml`：`MSG_STARTAPP_*`、日服独有 306 key（见 `i18n/reports/gap-report.json`）
- [~] **剧情国服挪用**：活动剧情 **event_story** 已 dump+build（114,859 条）；Frida `STORY_MODE=cn` 已接入；**待**卡片 `character/member/` + 真机 E2E（见 [notes/story-pipeline.md](notes/story-pipeline.md)）
- [x] 剧情 gap 清单：`story-inventory` → common=3882 / jp_only=476（`i18n-data/cache/scenario-inventory.json`）
- [ ] 翻译包热更新路径（manifest checksum 已有）

---

## P4 — Zygisk 模块

- [ ] 参照 gakuen-imas-localify 搭建 native 骨架（ShadowHook / Dobby）
- [ ] 三处 native Hook + `il2cpp_string_*` + 加载 `i18n/ui/wordings.json`
- [ ] 无 root 备选：LSPatch（低于 Zygisk）

---

## P5 — 字体注入（当前焦点）

- [ ] 国服 `TMP_FontAsset` 提取（备选）：`sekai-assets-updater` `REGION=CN` 解 `font/` bundle
- [x] `SetupBuiltinFontAsset` 真机探测（notes/frida.md §7）
- [x] **主字体替换**：`font_inject.js` — `FONT_MODE=replace` 换 `+0x20/0x38` 为 SC，EB/DB 降级 fallback；`dual` 仅预加载
- [x] `run.py`：`--font-inject`、`--font-mode`、`fmt_font_inject` 更新
- [x] **Unity 烘焙项目**：`i18n-tools/font-bake-unity`（`PjskFontBake.cs` + `bake.ps1`）；思源 OTF 已下载（本地 gitignore）
- [ ] **跑 `bake.ps1`** → `i18n/font/source-han-fallback.bundle`
- [ ] 真机：`font --inject` / `intercept --font-inject`，`UI_MODE=cn` 无 tofu
- [ ] legacy `CustomText` / Unity `Text` 缺字路径

---

## P6 — 资源与版本维护

- [ ] 游戏更新后：Il2CppDumper → IDA → `offsets.js` → `probe`（见 hook-strategy §版本更新）
- [ ] diff 更新后：`pjsk-i18n build` 并核对 `gap-report`
- [x] AssetBundle XOR 解密脚本化（`sssekai abdecrypt` + `i18n-tools/scripts/scenario_*`）

---

## 已完成

- [x] metadata 解密、Il2CppDumper、IDA 核心 Hook 验证
- [x] frida-gadget 真机补丁（TB322FC）
- [x] Frida `lib/` + `scripts/` + `run.py`；剧情 + UI `[TEST]` intercept E2E
- [x] 词表静态链路、国服 CN diff 调研、i18n-tools 构建管线
- [x] 字体策略定案：初步汉化**替换主字体**（非 fallback 补字）；双语混排笔记
- [x] 剧情路径 A：官方 CDN → scenario JSON → `story-build`（活动 1498 话，114,859 `jp→zh`）

---

## 搁置 / 阻塞

- [-] **剧情卡片/unit 构建**：活动 `event_story` 已完成；卡片 `character/member/`、unitstory、actionset 待按 [story-pipeline.md](notes/story-pipeline.md) 扩展 filter
- [-] 模拟器 frida-server；Master 缓存解密；内置词表提取脚本

---

## 相关命令

```powershell
uv sync

uv run --project i18n-tools pjsk-i18n build
uv run --project i18n-tools pjsk-i18n build --with-story
uv run --project i18n-tools pjsk-i18n story-inventory
uv run --project i18n-tools pjsk-i18n story-build
uv run --project i18n-tools pjsk-i18n font-chars

# 剧情 scenario 提取（需 sssekai + UnityPy；缓存见 i18n-data/cache/）
python i18n-tools/scripts/scenario_abcache_download.py --region jp --filter "^event_story/.*/scenario$" ...
python i18n-tools/scripts/scenario_from_bundles.py i18n-data/cache/ab-dec/jp i18n-data/cache/scenario/jp

# Unity 烘焙（Hub 打开 i18n-tools/font-bake-unity）
cd i18n-tools\font-bake-unity
.\bake.ps1

# 真机（需 bundle + 冷启动）
uv run python frida/run.py font --inject --duration 180
uv run python frida/run.py intercept --font-inject --duration 120
uv run python frida/run.py intercept --duration 120
uv run python frida/run.py probe
```