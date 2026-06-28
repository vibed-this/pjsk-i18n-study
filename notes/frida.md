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
| 监控脚本 | `frida/hook_monitor_bundle.js` |

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

## 结论

| 项 | 状态 |
|----|------|
| Frida 原型环境（真机 gadget） | ✅ 可用 |
| IDA 偏移在真机运行时有效 | ✅ 已验证（3/3 安装成功） |
| Hook 点有实际调用 | ✅ UI 层已确认；剧情层待测 |
| 文本内容抓取 | ⏳ 计数 OK，字符串读取待修 |
| 翻译替换原型 | ⏳ `hook_translate.js` 未测 |
| 模拟器 frida-server | ❌ 搁置 |

### 推荐联调流程

```powershell
cd frida/gadget
.\install.ps1                    # 首次或更新补丁后
adb forward tcp:27042 tcp:27042  # connect.ps1 内含
# 手机启动 PJSK（暂停）→ PC 连接：
.\connect.ps1
# 或 Python：
cd ..\..
python frida/run_session.py hook_monitor_bundle.js --duration 90 --attach
```

连接目标优先 **`Gadget`**，其次 `com.sega.pjsekai`。

### 脚本与产物索引

```
frida/
├── config.js / il2cpp.js
├── hook_monitor.js / hook_monitor_bundle.js
├── hook_translate.js
├── device.py / run_session.py / run_probe.py
└── gadget/
    ├── patch_apk.ps1 / install.ps1 / connect.ps1
    ├── libfrida-gadget.config.so
    ├── tools/          # apktool.jar, libfrida-gadget.so, debug.keystore
    └── out/            # *.gadget.apk（已签名，~500MB 总量）
```

### 待验证项

- [ ] 剧情场景中 `TalkWindow.SetWordsInfo` 调用与文本读取
- [ ] `CustomTextMesh.SetText` 实际文本内容打印
- [ ] `hook_translate.js` 替换是否在游戏内可见
- [ ] 游戏 `versionName` 与本地 `apk/` 一致性（模拟器曾见 6.5.5）

## 相关笔记

- [hook-strategy.md](./hook-strategy.md) — Hook 优先级与 Zygisk 下一步
- [toolchain.md](./toolchain.md) — SDK 路径、环境状态
- [ida-verification.md](./ida-verification.md) — 静态偏移来源