# 待办事项

> 项目路线：`metadata 解密 → Il2CppDumper → IDA 验证 → Frida 原型 → Zygisk 模块`  
> 背景见 [notes/bg.md](notes/bg.md)。技术笔记见 [notes/README.md](notes/README.md)。

**状态标记**：`[ ]` 待办 · `[~]` 进行中 · `[x]` 完成 · `[-]` 搁置

---

## 当前焦点

**Frida 动态验证收尾** — 真机 gadget 环境已可用，偏移已确认；需在完整 UI / 剧情场景中验证文本读取与可见拦截，再进入 Zygisk 封装。

---

## P0 — Frida 验证（阻塞后续封装）

- [ ] **主界面 `intercept` 测试**：游戏完全加载后进主菜单，运行 `uv run python frida/run.py intercept`，确认屏幕出现 `[TEST]` 前缀
- [ ] **主界面 `monitor` 补测**：确认 `TMP_Text.set_text` 在主界面有调用且能读出日文正文（加载阶段已证实为 0 次属正常）
- [ ] **剧情 `SetWordsInfo` 验证**：进入任意对话场景，确认 `TalkWindow.SetWordsInfo` 触发，并在 `onEnter` 读到 `X2`（角色名）/ `X3`（正文）
- [ ] **词表 key 对照**：在 dump / sekai.best 中查找已抓到的 key 原文：
  - `MSG_STARTAPP_LOGIN`
  - `MSG_STARTAPP_MASTER`
- [ ] **修正字符串读取策略**（基于加载阶段 monitor 结论）：
  - `SetWordingText` `onEnter` 读 key — 已验证可用，保留
  - `UpdateWordingText` `onLeave` 读返回值 — 已证实不可靠（`wordingText` 计数增加但 `readStr` 全 null），改 Hook `TMP_Text.set_text` 或 IDA 追 `sub_60282AC` 实现体
  - 放弃在 `WordingManager.Get` 包装器上用 `onLeave`

---

## P1 — 笔记与脚本同步

- [ ] 更新 [notes/frida.md](notes/frida.md)：反映 `frida/run.py` + `lib/` + `scripts/` 新结构；删除对已移除脚本的引用
- [ ] 更新 [notes/hook-strategy.md](notes/hook-strategy.md)：将 `TMP_Text.set_text` 提升为主拦截点；补充 `SetWordingText` / `UpdateWordingText` 路径与 tail-call 限制
- [ ] 修正 [notes/ida-verification.md](notes/ida-verification.md)：`CustomTextMesh.SetText` 多数调用方 `X1` 为空，文本来自词表解析后内部状态
- [ ] 将本次 monitor 样本写入 [notes/frida.md](notes/frida.md)（base=`0x7521015000`，启动 key，`UpdateWordingText onLeave` 失败）
- [ ] 关闭 [notes/bg.md](notes/bg.md) 中已解决的开放问题，补充新发现项

---

## P2 — 翻译数据管线

- [ ] 从 sekai.best / Sekai-World 同步 **MasterWording** 词表，建立 `key → 日文 → 中文` 映射原型
- [ ] 同步 **scenario / unitystory** JSON，建立剧情文本 ID → 译文映射
- [ ] 在 `frida/scripts/intercept.js` 或新 `translate` 模式中接入 demo 词表（先覆盖 `MSG_STARTAPP_*` 等已观测 key）
- [ ] 设计翻译包格式（版本号、checksum、热更新路径）

---

## P3 — Zygisk 模块

- [ ] 参照 [gakuen-imas-localify](https://github.com/chinosk6/gakuen-imas-localify) 搭建 native 工程骨架（ShadowHook / Dobby）
- [ ] 用 Frida 已验证偏移实现三处 native Hook：
  - `TalkWindow.SetWordsInfo` @ `0x6264FD8`
  - `TMP_Text.set_text` @ `0xA8D1B98`（兜底）
  - `CustomTextMesh.SetWordingText` @ `0x4F2B408`（UI key 拦截）
- [ ] 集成 `il2cpp_string_new` / `il2cpp_string_chars` 做运行时字符串替换
- [ ] 无 root 备选：评估 LSPatch 路线（优先级低于 Zygisk）

---

## P4 — 字体注入

- [ ] Frida 验证 `FontAssetManager.SetupBuiltinFontAsset` @ `0x61028AC` 调用时机
- [ ] 准备含 CJK 的 TMP_FontAsset 子集
- [ ] Hook fallback 表注入（`TMP_FontAsset.fallbackFontAssetTable`）
- [ ] 真机验证中文渲染无 tofu

---

## P5 — 资源与版本维护

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