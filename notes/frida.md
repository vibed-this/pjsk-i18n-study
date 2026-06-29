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
├── lib/offsets.js / lib/runtime.js
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

### 待验证项

- [x] 剧情 `TalkWindow.SetWordsInfo` 调用与文本读取
- [x] `intercept` 剧情替换游戏内可见
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