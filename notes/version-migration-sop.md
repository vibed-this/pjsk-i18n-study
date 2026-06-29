# 版本迁移 SOP（Frida Hook）

> 前置：[toolchain.md](./toolchain.md) 产物路径、[il2cpp-hook-resolution.md](./il2cpp-hook-resolution.md) 地址分层、[frida.md](./frida.md) 联调命令。  
> 实例：**6.5.5 → 6.6.0**（2026-06-29 真机走完）。

## 分析目标

游戏大/小版本更新后，在**不重复踩坑**的前提下，把 Frida 原型（UI 词表 + 剧情 patch）迁移到新 `libil2cpp.so`，并确认运行时 Hook 点与替换逻辑仍有效。

## 手段

| 阶段 | 工具 / 产物 |
|------|-------------|
| 静态 | 新 APK、`Il2CppDumper`、`IDA` / Capstone、`tools/lookup_offsets.py` |
| 配置 | `frida/lib/offsets.js`、`frida/scripts/intercept.js`、`frida/run.py` |
| 真机 | gadget APK、`probe`、`baseline`、`intercept`、`attach-probe` |
| 数据 | `pjsk-i18n build` / `story-build` → `i18n/ui/*.json`、`i18n/story/text.json` |

## 过程

### 0. 原则（6.6.0 教训）

1. **Il2CppDumper `Address` = runtime `methodPointer`**，6.6.0 上往往是**生产 Hook 点**。
2. **IDA「函数入口」≠ 热路径**：`GetImpl`、`AttachSceneData` 误标邻域函数均可导致 **0 hit 或 `args` 语义错**。
3. **`probe` 只证明 `r-x`**，不证明挂对函数；**`baseline` 命中统计** + **`intercept` E2E** 不可省略。
4. **冷启动**：`am force-stop` 后启动；热 attach 且无 UI/剧情操作 → stats 全 0、exit 1 属正常。

### 1. 静态准备

```text
新版本 APK / XAPK
  → 放入 apk/（记录 versionName）
  → metadata 解密（格式变则先处理，见 metadata.md）
  → Il2CppDumper → tools/Il2CppDumper/{dump.cs, script.json}
  → IDA 打开 libil2cpp.so（或 Capstone 离线）
  → uv run python tools/lookup_offsets.py   # Dumper Address vs 旧 offsets.js
  → 更新 frida/lib/offsets.js（注明版本；runtime + _impl 双列备诊断）
```

**offsets 写法建议**：生产符号用 **Dumper `Address`**；`*_impl` / `*_body` 保留 IDA 实现体作 baseline 对照。

### 2. Gadget 与环境

```powershell
cd frida/gadget
.\patch_apk.ps1    # 产出 *.gadget.apk
.\install.ps1      # 或 adb install -r out/....gadget.apk
```

真机会话前：

```powershell
adb shell am force-stop com.sega.pjsekai
adb shell monkey -p com.sega.pjsekai -c android.intent.category.LAUNCHER 1
# 等待 gadget 暂停画面
```

### 3. 第一层：`probe`（可执行性）

```powershell
uv run python frida/run.py probe
```

| 通过 | 不保证 |
|------|--------|
| `libil2cpp` 已加载，各 RVA 可映射 `r-x` | 是否为目标函数、是否被调用 |

### 4. 第二层：`baseline`（运行时 call-site）

```powershell
uv run python frida/run.py baseline --duration 60
```

操作主界面 / 进剧情，观察各候选 **hit 计数**。

**6.6.0 UI 结论（示例）**

| 有 hit | 无 hit |
|--------|--------|
| `Get_runtime` `0x602B9FC` | `GetImpl` `0x60282AC` |
| `SWT_runtime` `0x4F2E9EC` | `SWT_impl` `0x4F2B408` |
| `UWT_runtime` `0x4F2E8D0` | `UWT_impl` `0x4F2B2EC` |

**裁决**：以 **有 hit 的 runtime 列** 改 `offsets.js` 生产 Hook。

### 5. 第三层：`intercept` prefix（Hook 语义）

```powershell
uv run python frida/run.py intercept --ui-mode prefix --story-mode prefix --duration 120
```

| 成功标志 |
|----------|
| `wordingGet > 0`，`intercept N/N ok` |
| 屏幕可见 `[TEST]` 前缀（非仅终端） |

验证 `onLeave` / `onEnter` 在 **runtime 入口** 上能否改字符串。

### 6. 第四层：`intercept` cn（真实汉化）

```powershell
uv run python frida/run.py intercept --ui-mode cn --story-mode cn --duration 300
```

**UI**：`intercept [OK] … mode=cn`，`uiWordings` / `uiPlainText` 非 0。  
**剧情**：不走 `SetWordsInfo`（`stats.story` 可为 0）；看 **`story_patch_diag`** / **`story_patch_summary`**。

### 7. 剧情 patch 专项（AttachSceneData）

Hook：`ScenarioPlayer.AttachSceneData` **methodPointer**（6.6.0 **`0x624F8B8`**）。

| 终端 | 含义 |
|------|------|
| `story_patch_diag` … `id='…'` `snippets=N` `talk=M` | `args[1]` 为有效 `ScenarioSceneData` |
| `story_patch_summary` … **`patched > 0`** | TalkData 已改写 |
| `None lines=0 patched=0` | **Hook 地址错**（6.6.0 曾误挂 `0x624F814`） |
| `lines>0 patched=0` | Hook 对，**词表未覆盖**（查 `story-gap-report.json`） |

兜底：`--story-fallback`（额外 `SetWordsInfo` jp→zh，有 collision 风险）。

### 8. 数据管线（与 Hook 并行）

```powershell
uv run --project i18n-tools pjsk-i18n build
uv run --project i18n-tools pjsk-i18n story-build   # 或 build --with-story
```

### 9. 文档收尾

- 更新 [il2cpp-hook-resolution.md](./il2cpp-hook-resolution.md) §版本表
- 更新 [ida-verification.md](./ida-verification.md) §全表迁移
- 更新 [frida.md](./frida.md) 真机结论
- 同步 [TODO.md](../TODO.md)：**仅**记录版本迁移相关待办（P6）；迁移中发现的**汉化覆盖缺口**（未走通的文本类型、字体等）写入 TODO 对应优先级，**不写入本 SOP**

---

## 结论

### 检查清单（可复制）

```text
[ ] 新 APK + versionName 记入 offsets.js 注释
[ ] Il2CppDumper + lookup_offsets.py 对照
[ ] offsets.js：生产 Hook = baseline 有 hit 的 runtime 地址
[ ] gadget 重打并安装
[ ] probe：全部 r-x
[ ] baseline：UI/剧情候选 hit 表截图或日志
[ ] intercept prefix：wordingGet>0，屏幕 [TEST]
[ ] intercept cn UI：mode=cn，替换逻辑命中（简中可见；字形/tofu 属 P5 字体，见 TODO）
[ ] intercept cn 剧情：story_patch patched>0，对话简中
[ ] 笔记（偏移/流程）+ TODO（缺口/后续）已同步
```

### 6.5.5 vs 6.6.0 生产 Hook 对照

| 链路 | 6.5.5（已 E2E） | 6.6.0（已 E2E） |
|------|-----------------|-----------------|
| UI 词表 | `GetImpl` `0x60282AC` `onLeave` | `Get` `0x602B9FC` `onLeave` |
| UI 刷新 | `SWT` `0x4F2B408` / `UWT` `0x4F2B2EC` | `0x4F2E9EC` / `0x4F2E8D0` |
| 剧情 patch | `AttachSceneData` `0x624C100` | **`0x624F8B8`**（非 `0x624F814`） |
| 剧情对话（过渡） | `SetWordsInfo` `0x6264FD8` | `0x62687FC`（cn 默认不 Hook） |


### 相关命令速查

```powershell
uv run python frida/run.py probe
uv run python frida/run.py baseline --duration 60
uv run python frida/run.py intercept --ui-mode prefix --duration 120
uv run python frida/run.py intercept --ui-mode cn --story-mode cn --duration 300
uv run python frida/run.py attach-probe
uv run python tools/lookup_offsets.py
```

## 相关笔记

- [hook-strategy.md](./hook-strategy.md) §版本更新与偏移维护（摘要 + 本 SOP 链接）
- [il2cpp-hook-resolution.md](./il2cpp-hook-resolution.md) — methodPointer vs impl、误挂案例
- [frida.md](./frida.md) — gadget、§6.6.0 baseline、§8 剧情 patch
- [toolchain.md](./toolchain.md) — APK / dump / il2cpp 路径