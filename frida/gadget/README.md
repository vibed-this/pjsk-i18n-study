# Frida-Gadget 真机方案

> 适用于**无 root** 的 ARM64 真机。PC Frida 版本：**17.10.1**（须与 gadget 版本一致）。

## 原理

1. 向 `split_config.arm64_v8a.apk` 注入 `libfrida-gadget.so` + 配置
2. 在 `MessagingUnityPlayerActivity.onCreate` 最早处 `System.loadLibrary("frida-gadget")`
3. Gadget **listen** `127.0.0.1:27042`，`on_load: wait`（启动后暂停，等 PC 连接）
4. PC 通过 `adb forward` 连接，运行 `frida/run.py`

## 一次性准备（本机执行）

```powershell
cd E:\GithubRepos\pjsk-i18n-mod\frida\gadget
.\patch_apk.ps1
```

产物：

```
frida/gadget/out/
├── base.gadget.apk
├── split_config.arm64_v8a.gadget.apk
└── split_UnityDataAssetPack.apk   # 未修改，原样复制
```

## 真机连接后

```powershell
# 1. 确认设备
D:\SDK\Android\platform-tools\adb.exe devices

# 2. 安装（会卸载旧版 PJSK）
.\install.ps1

# 3. 在手机上点开 PJSK — 会卡在启动画面（正常，等 Frida 连接）

# 4. 连接（默认拦截演示 120s）
.\connect.ps1
# 只读监控：
.\connect.ps1 -Mode monitor -Duration 90
```

## 手动连接

```powershell
cd E:\GithubRepos\pjsk-i18n-mod
adb forward tcp:27042 tcp:27042
uv run python frida/run.py intercept
# 或：uv run python frida/run.py monitor --duration 90
```

连接成功后游戏会继续启动。`intercept` 模式屏幕上应出现 `[TEST]` 前缀；终端打印抓取日志。

## 文件说明

| 文件 | 作用 |
|------|------|
| `libfrida-gadget.config.so` | Gadget 配置（listen / wait） |
| `tools/libfrida-gadget.so` | Frida 17.10.1 arm64 gadget |
| `tools/apktool.jar` | 反编译/重打包 base.apk |
| `tools/debug.keystore` | 调试签名（首次自动生成） |

## 注意

- 仅适用于 **arm64-v8a** 真机；x86 模拟器请用 frida-server 方案（本项目模拟器验证未成功）
- 补丁 APK 使用**调试签名**，若已装官方版需先卸载
- **三分包必须同一 debug 密钥签名**（含 `split_UnityDataAssetPack.apk`）
- 安装推荐 `adb install-multiple -r --no-incremental`（增量安装可能假成功）
- 连接时进程名常为 **`Gadget`**（非包名），见 `connect.ps1`
- 游戏版本须与本地 `apk/` 一致，否则 Hook 偏移需重新验证

详细结论见 [notes/frida.md](../../notes/frida.md)。