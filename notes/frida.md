# Frida 动态分析

> Hook 目标见 [hook-strategy.md](./hook-strategy.md)、[ida-verification.md](./ida-verification.md)。

## 分析目标

在 Android 设备上动态验证 IDA 确认的文本 Hook 点是否可拦截，并建立可复用的 Frida 原型环境（无 root 真机优先）。

## 手段

| 组件 | 版本/路径 |
|------|-----------|
| PC Frida | 17.10.1 |
| frida-gadget | 17.10.1 android-arm64 |
| apktool | 2.12.1（`frida/gadget/tools/apktool.jar`） |
| Android SDK | `D:\SDK\Android`（platform-tools adb、build-tools 36.0.0 apksigner/zipalign） |
| 测试设备 | Lenovo TB322FC（`HA28NJ1V`，arm64-v8a，**无 root**） |
| 模拟器 | MuMu `emulator-5554`（x86_64 + ARM 转译，有 root） |
| 注入点 | `MessagingUnityPlayerActivity.onCreate` → `System.loadLibrary("frida-gadget")` |
| Gadget 配置 | listen `127.0.0.1:27042`，`on_load: wait` |
| 运行入口 | `uv run python frida/run.py`（monitor / intercept / probe） |

## 过程

### 1. 模拟器 + frida-server（未成功）

- 部署 `frida-server-17.10.1-android-x86_64` 至模拟器 `/data/local/tmp/`。
- 模拟器进程实际加载 `lib/arm64/libil2cpp.so`（非 x86 原生库），IDA 偏移理论上可沿用。
- **问题**：
  - Windows 上 `frida.get_usb_device()` 不稳定，需 `adb forward tcp:27042` + `add_remote_device("127.0.0.1:27042")`。
  - spawn 注入后 150–180s 内探针未报告 `libil2cpp.so` 加载；attach 已运行进程报 `ProcessNotRespondingError`。
- **结论**：模拟器 + frida-server 方案搁置，改走真机 gadget。

### 2. 真机 + frida-gadget 重打包

1. `patch_apk.ps1` 解码 `apk/base.apk`，在 `MessagingUnityPlayerActivity.onCreate` 首行注入 `loadLibrary("frida-gadget")`。
2. 向 `split_config.arm64_v8a.apk` 写入：
   - `lib/arm64-v8a/libfrida-gadget.so`
   - `lib/arm64-v8a/libfrida-gadget.config.so`
3. 用 `frida/gadget/tools/debug.keystore` 签名三分包（含 `split_UnityDataAssetPack.apk`，**必须同一密钥**）。
4. `adb install-multiple -r --no-incremental` 安装至 TB322FC。

**安装踩坑**：

| 现象 | 原因 | 解法 |
|------|------|------|
| `signatures are inconsistent` | 数据分包仍用官方签名 | 三分包全部 debug 重签 |
| 增量安装 Success 但包不存在 | 增量安装未真正落盘 | 加 `--no-incremental` |

### 3. 联调与 Hook 验证（90s 样本）

1. `adb forward tcp:27042 tcp:27042`
2. 启动 PJSK → 画面暂停（gadget wait）
3. PC 端 `attach("Gadget")` — **进程名不是包名**
4. 加载 `hook_monitor_bundle.js`

**运行时地址（真机一次采样，每次启动 base 会变，偏移不变）**：

| Hook 点 | IDA 偏移 | 运行时绝对地址（样本） |
|---------|----------|------------------------|
| `WordingManager.Get` | `0x60241BC` | `0x75181071bc` |
| `TalkWindow.SetWordsInfo` | `0x6264FD8` | `0x7518347fd8` |
| `CustomTextMesh.SetText` | `0x4F27530` | `0x751700a530` |

`libil2cpp.so` base=`0x75120e3000`，size=197234688（与静态分析一致：绝对地址 = base + IDA 偏移）。

**调用统计**（主界面操作约 90s）：

| Hook 点 | 次数 | 说明 |
|---------|------|------|
| `WordingManager.Get` | 19 | UI 词表查找活跃 |
| `CustomTextMesh.SetText` | 13 | TMP 文本设置活跃 |
| `TalkWindow.SetWordsInfo` | 0 | 未进入剧情对话 |

**文本读取**：`stats` 计数正常，但 `readIl2CppString` 对 `WordingManager.Get` 的返回值多为 null（IL2CPP 静态包装器间接返回）。`CustomTextMesh` 的 `onEnter` 日志亦未打出 `event:text` 样本——待改进脚本或改 Hook 层验证。

### 4. monitor 长会话（2026-06-28，base=`0x7521015000`）

脚本：`frida/run.py monitor`。`il2cpp_string_*` API 读串。

**启动 / 加载阶段**（gadget 连接后约 20s）：

| Hook | 次数 | 文本读取 |
|------|------|----------|
| `SetWordingText` | 2 | key：`MSG_STARTAPP_LOGIN`、`MSG_STARTAPP_MASTER` |
| `UpdateWordingText` | 5 | `onLeave` 计数增加，**正文全 null** |
| `TMP_Text.set_text` | 0 | — |
| `SetWordsInfo` | 0 | — |

**剧情阶段**（进入对话后）：

| Hook | 次数 | 样本 |
|------|------|------|
| `SetWordsInfo` | 1 | `name=ミク`，`cid=21`，`words=こんにちは。\nここに誰かが来るなんて、珍しいな` |
| `SetWordingText` | +3（累计 6） | `WORD_DECIDE`、`WORD_CANCEL`、`MSG_MOVIE_SKIP_BODY` |
| `UpdateWordingText` | 23→37 | 仍无 `[UI]` 正文（`onLeave` 不可靠） |
| `TMP_Text.set_text` | **0** | 剧情早期显示未经过该 hook；后续 UI 操作后会增长 |

### 5. intercept 剧情验证（2026-06-28，base=`0x7521015000`）

脚本：`frida/run.py intercept`，`PREFIX='[TEST] '`。

| 项 | 结果 |
|----|------|
| `TalkWindow.SetWordsInfo` | ✅ 屏幕可见；`name=ミク`→`[TEST] ミク`，正文→`[TEST] わたしは、初音ミク。\nキミの名前は？` |
| `cid` | 21 |
| `TMP_Text.set_text` | 剧情初段 `tmp=0`，会话后期增至 **12**（UI 刷新后触发） |
| `UpdateWordingText` | `ui` 增至 9（替换逻辑已执行，monitor 层仍读不出原文） |

**结论**：剧情翻译 Hook 点 **`SetWordsInfo` 已完成 read + intercept E2E 验证**，可作为 Zygisk 剧情层实现依据。

### 剧情运行时 ID 探测（2026-06-29 monitor）

`monitor` 双 Hook：`ScenarioPlayer.SnippetActionTalk` @ `0x624FC28` + `SetWordsInfo` @ `0x6264FD8`。

| 观测 | 结果 |
|------|------|
| `scenarioId` | `event_01_01` / `event_01_02` 可读 ✅ |
| `bookmarkSequenceId` | ≈ **snippet `Index`**（6/7/8），≠ talk 行序 |
| `snippetIndex` / `refIdx` | 与 cache `Snippets` 一致，可用于诊断 |

**初版 bug（已修）**：`talkLine` 用会话内 `++` 计数。用户 **WORD_SKIP 跳到句中再重播** 时，计数与正文错位，例如：

| 现象 | 原因 |
|------|------|
| `ctx=event_01_01:0` 却是 talk[2] 正文（`……最近、ずっと雨`） | 跳过后首次 Talk 仍从 0 计数 |
| 重播后 `ん……` 显示 `:1`、第二句显示 `:2` | 计数未随 snippet Index 重置 |

**修复**：`computeTalkLineIdx(player, snippet)` — 读 `scenarioScene.Snippets[]`，按 `Index` 排序后对 `Action==Talk` 枚举，与 `story.py` `extract_talk_lines` 同逻辑。日志追加 `snip=` / `ref=`。

**待复测**：跳过后 `ctx` 是否稳定为 `event_01_01:2`；`ScenarioJumper` 书签路径。

详见 [ida-verification.md](./ida-verification.md) §剧情运行时 ID、[hook-strategy.md](./hook-strategy.md) §剧情运行时上下文。

### 6.6.0 baseline 运行时入口（2026-06-29）

## 分析目标

确认 6.6.0 UI 词表链实际调用的 RVA（impl vs methodPointer），解释 `intercept` stats 全 0。

## 手段

- `frida/run.py baseline`（`scripts/baseline.js`）：il2cpp 字符串 API smoke + 14 候选 `Interceptor.attach` 命中计数
- 真机 6.6.0 gadget；操作主界面按钮 / 剧情跳过 dialog

## 过程

1. `il2cpp_string_*` roundtrip **ok**。
2. 有 UI 交互后命中增长：

| id | RVA | hit |
|----|-----|-----|
| `Get_runtime` | `0x602B9FC` | ✅ `WORD_CANCEL` 等 |
| `SWT_runtime` | `0x4F2E9EC` | ✅ |
| `UWT_runtime` | `0x4F2E8D0` | ✅ |
| `GetImpl` | `0x60282AC` | ❌ 0 |
| `Get_wrapper` | `0x602B8C0` | ❌ 0 |
| `SWT_impl` / `UWT_impl` | `0x4F2B408` / `0x4F2B2EC` | ❌ 0 |

3. `offsets.js` / `intercept.js` 已改 Hook 到 **runtime 列**；`GetImpl` 等保留作诊断。

## 结论

| 项 | 结论 |
|----|------|
| 根因 | 6.6.0 热路径走 **Il2CppDumper / methodPointer**，非 6.5.5 的 impl 入口 |
| 命令 | `uv run python frida/run.py baseline --duration 60` |
| E2E（冷启动后） | `intercept` @ `0x602B9FC`：`wordingGet=6`、`intercept 6/6 ok`；`onLeave` 前缀替换可用 ✅ |
| baseline（主界面） | `Get_runtime=10`、`UWT_runtime=10`；`GetImpl` attach 偶发 fail（非生产 Hook） |
| 待补测 | 进主菜单后 `WORD_DECIDE` 等 dialog；`uiKey` / `SWT_runtime` 计数 |

---

### 6.6.0 `probe` vs `intercept` attach 差异（2026-06-29）

## 分析目标

解释 6.6.0 真机 `probe` 17/17 通过但首次 `intercept` 在 `GetImpl` 报 `unable to intercept function`。

## 手段

- 新增 `frida/run.py attach-probe`（`scripts/attach_probe.js`）：逐偏移 `Interceptor.attach`，含 `onLeave` 与 intercept 安装顺序复现
- 冷启动 `am force-stop` 后重跑 `intercept`；对比 on-disk `il2cpp.so` 入口字节

## 过程

1. **GetImpl Hook 逻辑未改**：`intercept.js` 仍 `hookAt('WordingManager.Get', OFFSETS.WordingManager_GetImpl, { onEnter, onLeave })`；偏移 `0x60282AC` 与 6.5.5 相同。
2. **`attach-probe`（游戏已运行）**：`GetImpl` / `GetFormat` / intercept 全顺序 **attach 均 OK**；`onEnter+onLeave` 亦 OK。
3. **冷启动后 `intercept`**：base 变化（ASLR），**全部 Hook 安装成功**，无复现首次错误。
4. **入口字节对比**：
   - on-disk `il2cpp.so` @ `0x60282AC`：`fd 7b bf a9 …`（IDA 序言 `STR X30,[SP,#-0x10]!`）
   - Hook 已安装后运行时：`31 a7 a0 97 …`（Frida trampoline `BL`）；页保护由 `r-x` 变为 **`rwx`**
5. 首次失败后会留下**部分 Hook**（`install()` 在 `GetImpl` 前已成功挂 5 个）；`session.detach()` 应恢复，但若异常断开可能需 **冷启动游戏** 再连。

## 结论

| 项 | 结论 |
|----|------|
| 根因 | **非偏移/逻辑错误**；更像 Frida **瞬时 attach 失败** 或异常断连后的**残留 trampoline 状态** |
| `probe` 局限 | 只查 `r-x` 映射，**不**验证 `Interceptor.attach` |
| 缓解（可选） | `hookAt` 重试已移除以便复测；若仍偶发失败则冷启动游戏 |
| 诊断命令 | `uv run python frida/run.py attach-probe` |
| 恢复步骤 | attach 失败 → `am force-stop` 冷启动 → 重连 `intercept` |

---

### 6. intercept UI 词表验证（2026-06-28，base=`0x7530bb4000`）

脚本：`frida/run.py intercept`。UI 路径 Hook：

| 函数 | 偏移 | 作用 |
|------|------|------|
| `WordingManager.Get`（实现体） | `0x60282AC` | `onLeave` 替换 lookup 返回值 ✅ |
| `WordingManager.GetFormat` | `0x602F054` | 带占位符文案 |
| `CustomTextMesh.SetText` | `0x4F27530` | 显示前改 `X1` |
| `CustomTextMesh.SetText`（slot） | `0x4F2B590` | `UpdateWordingText` tail-call 目标 |

**无效路径（已弃用）**：`UpdateWordingText onLeave`（tail-call，读返回值全 null）；词表 UI 早期 `TMP_Text.set_text` 计数为 0 属正常。

**样本**（剧情内跳过 dialog，屏幕可见 `[TEST]` 前缀）：

| key | 原文 | 替换 |
|-----|------|------|
| `WORD_DECIDE` | 決定 | `[TEST] 決定` |
| `WORD_CANCEL` | キャンセル | `[TEST] キャンセル` |
| `MSG_LIVE_SKIP_BODY` | ライブをスキップしますか？ | `[TEST] ライブをスキップしますか？` |

**结论**：UI 词表拦截 **`WordingManager.Get` 实现体 `onLeave`** 即可完成可见替换；Zygisk UI 层优先对齐此点，辅以 `CustomTextMesh.SetText` 兜底。

## 结论

| 项 | 状态 |
|----|------|
| Frida 原型环境（真机 gadget） | ✅ 可用 |
| IDA 偏移在真机运行时有效 | ✅ 已验证（3/3 安装成功） |
| Hook 点有实际调用 | ✅ UI + 剧情均已确认 |
| 文本内容抓取 | ✅ 剧情 `SetWordsInfo`；UI `SetWordingText` key + `WordingManager.Get` 日文 |
| 翻译替换原型 | ✅ 剧情 `SetWordsInfo` + UI `WordingManager.Get` 可见替换 |
| 模拟器 frida-server | ❌ 搁置 |

### 推荐联调流程

```powershell
cd E:\GithubRepos\pjsk-i18n-mod
uv sync
adb forward tcp:27042 tcp:27042
uv run python frida/run.py monitor --duration 120   # 只读
uv run python frida/run.py intercept --duration 120 # 可见替换
# 或：frida/gadget/connect.ps1
```

连接目标优先 **`Gadget`**，其次 `com.sega.pjsekai`。

### 脚本与产物索引

```
frida/
├── run.py / device.py / README.md
├── lib/offsets.js / lib/runtime.js / lib/story_patch.js
├── scripts/monitor.js / intercept.js / probe.js
└── gadget/
    ├── patch_apk.ps1 / install.ps1 / connect.ps1
    ├── libfrida-gadget.config.so
    ├── tools/          # apktool.jar, libfrida-gadget.so, debug.keystore
    └── out/            # *.gadget.apk（已签名，~500MB 总量）
```

### 7. font 字体加载探测（2026-06-29，base=`0x7511111000`）

脚本：`frida/run.py font`。冷启动 attach 后约 10s 内触发。

| 项 | 结果 |
|----|------|
| `SetupBuiltinFontAsset` | ✅ 1 次 enter/leave |
| `ClearFallbackFontAsset` | ✅ 4 次（写入前清空 fallback） |
| 内置字体名 | **`DB`**、**`EB`**（非 Master 明文名） |
| `baseA`（EB）| `fallbackSize`：0 → **2** |
| `baseB`（DB）| `fallbackSize`：0 → **2** |
| `loadedA/B` | leave 后填入新加载的 EB/DB `TMP_FontAsset` |

**策略（2026-06-29 定案）**：初步汉化采用**替换主字体**，非 fallback 追加。`SetupBuiltinFontAsset` **onLeave** 将 `+0x20`（EB）、`+0x38`（DB）换为思源 SC（或国服 CN）`TMP_FontAsset`；原 EB/DB 挂入新字体 `[font+0x138]` fallback，兜底未翻译日文。理由：主字体有字形时 TMP 不走 fallback，日文字形会与简中混搭。见 [text-rendering.md](./text-rendering.md) §初步汉化字体策略。

**实现**：`font_inject.js` `FONT_MODE=replace` 在 onLeave **替换** `+0x20`/`+0x38` 为 SC，原 EB/DB 写入 SC fallback；`dual`/`load` 仅加载 SC 不改主字体。

**字体源**：思源 SC 子集（`pjsk-i18n font-chars` + Unity 烘焙）；或 `sekai-assets-updater` `REGION=CN` 解 `font/` bundle 提取国服 TMP。

### 8. 剧情数据源 patch（2026-06-29，`story_patch.js`）

#### 分析目标

在 **bundle 载入后、播放前** patch `ScenarioSnippetTalk`，替代每句 `SetWordsInfo` + 全局 `jp→zh` 查表（有 collision）。

#### 手段

- Hook：`ScenarioPlayer.AttachSceneData` @ **`0x624F8B8`**（6.6.0 methodPointer；6.5.5 IDA `0x624C100`）
- 数据：`i18n/story/text.json`（114,859 条 jp→zh，由 `run.py` 注入为 `STORY_TEXT`）
- 结构：`enumerateScenarioTalkLines`（`runtime.js`）与 `story-build` 行序一致
- 诊断：`story_patch_diag`（scene 指针、`scenarioId`、snippets/talk 数组长度）

#### 过程

**默认配置**（存在 `text.json` 时 `intercept_cfg` 自动启用）：

| 项 | `STORY_MODE=cn` | `STORY_MODE=dual` |
|----|-----------------|-------------------|
| `STORY_PATCH_ATTACH` | `true` | `true` |
| `STORY_SET_WORDS_FALLBACK` | `false`（不 Hook SetWordsInfo 替换） | `true`（仍走 SetWordsInfo 双字幕） |
| 动作 | patch `talk+0x18` / `+0x20` | 仅 JP 备份到 `STORY_JP_BACKUP` |

**真机命令**（须冷启动，见 §6.6.0 baseline）：

```powershell
adb shell am force-stop com.sega.pjsekai
adb shell monkey -p com.sega.pjsekai -c android.intent.category.LAUNCHER 1
uv run python frida/run.py intercept --ui-mode cn --story-mode cn --duration 300
```

**成功判据**：

| 终端 | 含义 |
|------|------|
| `story_patch_diag` … `id='event_story_…'` `snippets=N` `talk=M` | `args[1]` 为有效 `ScenarioSceneData` |
| `story_patch_summary` … `lines=N` **`patched>0`** | 数据源 patch 命中 |
| `story_patch` JP/ZH 对照行 | 抽样替换内容 |
| `stats.story` **= 0** | 正常（cn 不走 `SetWordsInfo`） |
| 屏幕对话简中 | 端到端成功 |

**失败判据**：

| 终端 | 含义 |
|------|------|
| `story_patch_summary None lines=0 patched=0` | Hook 地址错或 `args[1]` 非 scene（曾误挂 `0x624F814`） |
| `lines>0 patched=0` | Hook 对但 `text.json` 未覆盖该场景 |

**可选**：`--story-fallback`（cn 时额外 `SetWordsInfo` jp→zh）；`--story-mode dual`（JP 备份 + 双字幕）。

#### 结论

| 项 | 状态 |
|----|------|
| 代码原型 | ✅ `story_patch.js` + `offsets.js` |
| 6.6.0 地址 | ✅ **`0x624F8B8`**（非误标 `0x624F814`，见 [il2cpp-hook-resolution.md](./il2cpp-hook-resolution.md)） |
| 真机 E2E | ✅ `STORY_MODE=cn`：patch + 屏幕简中 |
| 后续 | `by-scenario` 按行查表；`OnFinishLoadScenario` `0x63E7238` 备选 |

### 待验证项

- [x] 剧情 `TalkWindow.SetWordsInfo` 调用与文本读取
- [x] `intercept` 剧情替换游戏内可见（SetWordsInfo 路径，prefix）
- [x] **`AttachSceneData` patch E2E**：`story_patch_summary` `patched>0` + 游戏内简中（6.6.0）
- [x] `FontAssetManager.SetupBuiltinFontAsset` 调用时机与 fallback 表
- [x] 主界面 / UI 词表 `intercept` 简中命中（字体 tofu 待 P5）
- [ ] 主字体替换（思源 SC / 国服 CN）后 `UI_MODE=cn` 无 tofu、字形一致
- [ ] 剧情早期 `TMP_Text.set_text` 绕过规律（`SetWordsInfo` 直达显示）
- [ ] 主界面 `TMP_Text.set_text` 正文读取
- [ ] 游戏 `versionName` 与本地 `apk/` 一致性（真机 6.5.5）

## 相关笔记

- [hook-strategy.md](./hook-strategy.md) — Hook 优先级与 Zygisk 下一步
- [dual-subtitle.md](./dual-subtitle.md) — 剧情双语字幕（暂缓）
- [toolchain.md](./toolchain.md) — SDK 路径、环境状态
- [ida-verification.md](./ida-verification.md) — 静态偏移来源