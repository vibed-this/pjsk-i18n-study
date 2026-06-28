# 待办事项

> 项目路线：`metadata 解密 → Il2CppDumper → IDA 验证 → Frida 原型 → Zygisk 模块`  
> 背景见 [notes/bg.md](notes/bg.md)。技术笔记见 [notes/README.md](notes/README.md)。

**状态标记**：`[ ]` 待办 · `[~]` 进行中 · `[x]` 完成 · `[-]` 搁置

---

## 当前焦点

**Frida 剧情 + UI 词表 intercept E2E 已通过** — 下一步：主界面菜单补测、`TMP_Text.set_text` 行为确认，然后 demo 翻译表 + Zygisk 封装。

---

## P0 — Frida 验证（阻塞后续封装）

- [ ] **主界面 `intercept` 测试**：游戏完全加载后进主菜单，运行 `uv run python frida/run.py intercept`，确认屏幕出现 `[TEST]` 前缀
- [ ] **主界面 `monitor` 补测**：确认 `TMP_Text.set_text` 在主界面有调用且能读出日文正文（加载阶段已证实为 0 次属正常）
- [x] **剧情 `SetWordsInfo` 验证**：`talk=1`，成功读到 `name=ミク` `cid=21`、正文含换行（见 notes/frida.md §4）
- [x] **剧情 `intercept` 验证**：`SetWordsInfo` 替换可见；样本 `name=ミク` `cid=21`，正文含换行（见 notes/frida.md §5）
- [x] **UI 词表 `intercept` 验证**：`WordingManager.Get` `onLeave` 可见替换；样本 `WORD_DECIDE`/`WORD_CANCEL`/`MSG_LIVE_SKIP_BODY`（见 notes/frida.md §6）
- [ ] **主界面菜单 `intercept` 补测**：进主菜单后确认菜单按钮 `[TEST]`（非剧情 dialog）
- [ ] **调查剧情早期 `TMP_Text.set_text` 为 0**：显示经 `SetWordsInfo` 直达；后续 UI 操作后 `tmp` 会增长
- [~] **词表 key 对照**：静态链路已理清（见 [text-rendering.md](notes/text-rendering.md) §词表）；`WORD_*` / 部分 `MSG_*` 已在 sekai-master-db-diff 对照
  - [x] `WORD_DECIDE` / `WORD_CANCEL` / `MSG_MOVIE_SKIP_BODY` → 公开库可查
  - [x] `MSG_STARTAPP_*` 静态来源 — `TitleController` 登录链硬编码；见 [text-rendering.md](notes/text-rendering.md) §4
  - [x] `MSG_STARTAPP_*` 日文 value — APK 内置引导词表已确认（§5）；非 Master 表
- [x] **UI 拦截/读取策略确定**：
  - `SetWordingText` `onEnter` 读 key — 保留
  - `WordingManager.Get` **实现体** `0x60282AC` `onLeave` — 读/替换日文 ✅
  - `CustomTextMesh.SetText` / `SetText(slot)` — 显示前兜底
  - 放弃：`UpdateWordingText onLeave`、包装器 `0x60241BC` onLeave（tail-call）

---

## P1 — 笔记与脚本同步

- [ ] 更新 [notes/frida.md](notes/frida.md)：反映 `frida/run.py` + `lib/` + `scripts/` 新结构；删除对已移除脚本的引用
- [ ] 更新 [notes/hook-strategy.md](notes/hook-strategy.md)：将 `TMP_Text.set_text` 提升为主拦截点；补充 `SetWordingText` / `UpdateWordingText` 路径与 tail-call 限制
- [ ] 修正 [notes/ida-verification.md](notes/ida-verification.md)：`CustomTextMesh.SetText` 多数调用方 `X1` 为空，文本来自词表解析后内部状态
- [~] 将 monitor 样本写入 [notes/frida.md](notes/frida.md)（启动 + 剧情样本）
- [ ] 关闭 [notes/bg.md](notes/bg.md) 中「剧情 SetWordsInfo 未验证」条目

---

## P2 — 功能扩展：剧情双语字幕（暂缓）

> 情报见 [notes/dual-subtitle.md](notes/dual-subtitle.md)。当前优先单行翻译 + Zygisk。

- [x] plain / rich 原型与打字机冲突结论 — 已记入 `dual-subtitle.md`
- [ ] **打字机策略调研**：`AddLog` / `maxVisibleCharacters` / 打完回调（恢复本项时再动）
- [ ] **双字幕 v2**：两阶段提交或物理双 label
- [ ] **调查 `wordsOutlineLabel`**：是否可作第二字幕
- [ ] **数据**：`lineId → {jp, zh}` 与 `[[...]]` 译文行格式定稿

## P3 — 翻译数据管线

- [~] 从 sekai.best / Sekai-World 同步 **MasterWording** 词表，建立 `key → 日文 → 中文` 映射原型（数据源：`sekai-master-db-diff/wordings.json`，3519 条；见 [text-rendering.md](notes/text-rendering.md)）
- [x] **解包词表路径调研**（暂缓脚本化）：内置 `Wording/wording` ~196 条可 APK 解包；全量须解密 `p6FeKw3CVfhD2S5E/YUHXZyDBFcwbeeFD` 或 CDN suiteMaster — 见 [text-rendering.md](notes/text-rendering.md) §5
- [-] **内置词表提取脚本**：从 `112b24b5d05c9446b9dc9a758f423bbd` 解析 CSV → JSON（暂缓）
- [-] **Master 缓存解密**：`FastAESCrypt` + `YUHXZyDBFcwbeeFD` → 全量 `wordings`（暂缓）
- [ ] 同步 **scenario / unitystory** JSON，建立剧情文本 ID → 译文映射
- [ ] 在 `frida/scripts/intercept.js` 或新 `translate` 模式中接入 demo 词表（可先覆盖内置 196 条 + `MSG_STARTAPP_*`）
- [ ] 设计翻译包格式（版本号、checksum、热更新路径）

---

## P4 — Zygisk 模块

- [ ] 参照 [gakuen-imas-localify](https://github.com/chinosk6/gakuen-imas-localify) 搭建 native 工程骨架（ShadowHook / Dobby）
- [ ] 用 Frida 已验证偏移实现三处 native Hook：
  - `TalkWindow.SetWordsInfo` @ `0x6264FD8`
  - `TMP_Text.set_text` @ `0xA8D1B98`（兜底）
  - `CustomTextMesh.SetWordingText` @ `0x4F2B408`（UI key 拦截）
- [ ] 集成 `il2cpp_string_new` / `il2cpp_string_chars` 做运行时字符串替换
- [ ] 无 root 备选：评估 LSPatch 路线（优先级低于 Zygisk）

---

## P5 — 字体注入

- [ ] Frida 验证 `FontAssetManager.SetupBuiltinFontAsset` @ `0x61028AC` 调用时机
- [ ] 准备含 CJK 的 TMP_FontAsset 子集
- [ ] Hook fallback 表注入（`TMP_FontAsset.fallbackFontAssetTable`）
- [ ] 真机验证中文渲染无 tofu

---

## P6 — 资源与版本维护

- [ ] 确认设备 `versionName` 与本地 `apk/` 一致（当前真机 **6.5.5**）
- [ ] 建立游戏版本更新后的偏移重验证流程（Il2CppDumper → IDA diff → Frida probe）
- [ ] AssetBundle XOR 解密脚本化（剧情素材离线提取）

---

## 已完成

- [x] metadata 解密（sssekai）
- [x] Il2CppDumper 产物与类结构分析
- [x] IDA 验证核心 Hook 候选入口与 ARM64 参数
- [x] frida-gadget 真机补丁（TB322FC，无 root）
- [x] Frida 脚本整理：`lib/` + `scripts/` + `run.py`（intercept / monitor / probe）
- [x] uv Python 环境（`pyproject.toml`，frida 17.10.1）
- [x] 真机验证 4 处 Hook 安装成功，偏移 `base + IDA` 正确（含 `TMP_Text.set_text`、`SetWordingText`、`UpdateWordingText`）
- [x] 启动阶段词表 key 抓取：`MSG_STARTAPP_LOGIN`、`MSG_STARTAPP_MASTER`
- [x] 剧情 `TalkWindow.SetWordsInfo` 文本读取（`il2cpp_string_*`，`onEnter` X2/X3）
- [x] 剧情 UI 词表 key：`WORD_DECIDE`、`WORD_CANCEL`、`MSG_MOVIE_SKIP_BODY`
- [x] 剧情 `intercept` 可见替换：角色名 + 对话正文均出现 `[TEST]` 前缀
- [x] UI 词表 `intercept`：`WordingManager.Get` 替换 `決定`/`キャンセル`/`ライブをスキップ…` 可见

---

## 搁置 / 阻塞

- [-] **模拟器 + frida-server**：x86_64 转译环境下 spawn 后长期未见 il2cpp 加载；改走 gadget 真机
- [-] **`UpdateWordingText` / `WordingManager.Get` 的 `onLeave` 读返回值**：tail-call（`BR X3`）导致 Frida 层不可靠；改走 `TMP_Text.set_text` 或 native Hook

---

## 相关命令

```powershell
# 环境
uv sync

# 只读监控
uv run python frida/run.py monitor --duration 120

# 拦截演示（进主界面后）
uv run python frida/run.py intercept --duration 120

# 偏移探针
uv run python frida/run.py probe
```