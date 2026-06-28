# 待办事项

> 项目路线：`metadata 解密 → Il2CppDumper → IDA 验证 → Frida 原型 → Zygisk 模块`  
> 背景见 [notes/bg.md](notes/bg.md)。技术笔记见 [notes/README.md](notes/README.md)。

**状态标记**：`[ ]` 待办 · `[~]` 进行中 · `[x]` 完成 · `[-]` 搁置

---

## 当前焦点

**游戏 APK 下载中，设备已断开** — 阻塞项：真机 Frida 联调。

**就绪**：`i18n-tools` 已从国服 diff 构建 `i18n/ui/wordings.json`（4838 keys）；`intercept` 已接 `UI_MODE=cn`（`WordingManager.Get` 按 key 替换成简中）。

**下载完成后第一件事**：

1. 确认本地 `apk/` / 设备 `versionName` 与 `offsets.js` 注释（6.5.5）一致，必要时 `probe`
2. `uv run --project i18n-tools pjsk-i18n build`（若 diff 有更新）
3. `uv run python frida/run.py intercept` — 主界面 + 剧情 dialog，确认 **确定 / 取消** 等国服译文（非 `[TEST]` 前缀）
4. 若 UI 仍为日文：核对 `Get` 的 key 参数索引（`args[0]`）与终端 `intercept` 日志

---

## P0 — Frida 真机验证（阻塞后续）

- [ ] **国服词表 `intercept` E2E**：`UI_MODE=cn`，样本 `WORD_DECIDE`→确定、`WORD_CANCEL`→取消（游戏就绪后）
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
- [ ] `overrides/ui.yaml`：`MSG_STARTAPP_*`、日服独有 306 key（见 `i18n/reports/gap-report.json`）
- [ ] 剧情：**scenario** JSON 对齐（`sekai-assets-updater` `REGION=CN`），独立于 UI 词表
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

# 真机 intercept（自动 UI_MODE=cn 若 i18n/ui/wordings.json 存在）
uv run python frida/run.py intercept --duration 120

uv run python frida/run.py monitor --duration 120
uv run python frida/run.py probe
```