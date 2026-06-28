# Frida 联调

真机 gadget 补丁见 [gadget/README.md](gadget/README.md)。Hook 偏移见 `notes/ida-verification.md`。

## 目录

```
frida/
├── run.py              # 统一入口（Python）
├── device.py           # adb forward + Frida 连接
├── lib/
│   ├── offsets.js      # Hook 偏移（IDA 入口）
│   └── runtime.js      # il2cpp_string_* 与通用 helper
├── scripts/
│   ├── intercept.js    # 拦截演示（屏幕可见 + 终端输出）
│   ├── monitor.js      # 只读监控
│   ├── font.js         # 字体加载探测（SetupBuiltinFontAsset）
│   └── probe.js        # 验证 il2cpp 加载与偏移
└── gadget/             # APK 补丁与安装
```

## 环境

```powershell
cd E:\GithubRepos\pjsk-i18n-mod
uv sync
```

## 常用命令

手机冷启动 PJSK（gadget wait，画面暂停）后：

```powershell
# 拦截演示 — 推荐测试用
uv run python frida/run.py intercept

# 只读监控
uv run python frida/run.py monitor --duration 90

# 字体加载探测（冷启动触发 SetupBuiltinFontAsset）
uv run python frida/run.py font --duration 180

# 验证 il2cpp 与偏移（spawn 模式）
uv run python frida/run.py probe

# UI 国服词表（需先构建 i18n 包）
uv run --project i18n-tools pjsk-i18n build
uv run python frida/run.py intercept

# 自定义前缀
uv run python frida/run.py intercept --prefix "[CN] " --duration 120
```

## 模式

| 模式 | 作用 | 游戏内效果 |
|------|------|------------|
| `intercept` | 抓取并替换文本 | 国服替换或 `[TEST]` 前缀 |
| `monitor` | 只读监控 | 无 |
| `font` | 字体加载探测 | 无 |
| `probe` | 检查模块与偏移 | 无 |

`intercept` / `monitor` / `font` 默认 **attach**（连 gadget）；`probe` 默认 **spawn**。

## 连接说明

- `adb forward tcp:27042 tcp:27042` 由 `device.py` 自动执行
- attach 目标优先 `Gadget`，其次 `com.sega.pjsekai`
- 冷启动前建议 `adb shell am force-stop com.sega.pjsekai`