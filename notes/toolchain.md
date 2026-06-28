# 工具链与产物

> 各分析主题见 [metadata.md](./metadata.md)、[il2cpp-dump.md](./il2cpp-dump.md)、[ida-verification.md](./ida-verification.md)。

## 分析目标

记录逆向分析所需的工具、环境就绪状态，以及各阶段产物的存放路径。

## 手段

本地工具安装、APK 解包、sssekai 解密、Il2CppDumper dump、IDA Pro + MCP 联调。

## 过程

按关键路径依次搭建：

```
APK 解包 → sssekai 解密 metadata → Il2CppDumper → IDA 验证 Hook 点
```

## 工具就绪状态

### 已就绪

| 组件 | 状态 |
|------|------|
| APK 分包 | ✅ `apk/base.apk` 等 |
| metadata 解密 | ✅ `dump/il2cpp/global-metadata.dat` |
| Il2CppDumper 产物 | ✅ `tools/Il2CppDumper/` |
| IDA 数据库 | ✅ `libil2cpp.so.i64`（已重命名关键函数） |
| IDA Pro MCP | ✅ `127.0.0.1:13337` |
| Frida（PC 端） | ✅ 已安装 |
| sssekai | ✅ v0.8.0 + `[il2cpp]` extra |

### 未就绪

| 组件 | 说明 |
|------|------|
| Hex-Rays | 不可用，仅反汇编分析 |
| Il2CppDumper 符号批量导入 IDA | `ida_py3.py` 需交互选文件，未执行 |
| Frida 动态验证 | 无可用 Android 设备 / frida-server |
| gakuen-imas-localify 源码 | Zygisk 模块参考，未克隆 |
| 游戏版本号 | APK 对应的具体 `versionName` 未确认 |

## 结论

静态分析工具链已打通；阻塞项集中在 Hex-Rays 许可证、Frida 动态环境、参考实现源码三个方面。产物体积极大，已通过 `.gitignore` 排除出版本控制。

## 产物索引

```
dump/
├── input/
│   ├── global-metadata.dat      # 原始混淆 metadata
│   └── libil2cpp.so
└── il2cpp/
    ├── global-metadata.dat      # 解密后标准 metadata
    └── il2cpp.so

tools/Il2CppDumper/
├── dump.cs
├── script.json
├── stringliteral.json
├── il2cpp.h
└── DummyDll/

apk/split_config.arm64_v8a/lib/arm64-v8a/
├── libil2cpp.so
└── libil2cpp.so.i64             # IDA 数据库（已重命名关键函数）
```

## 相关笔记

- [ref.md](./ref.md) — 外部参考资料汇总
- [hook-strategy.md](./hook-strategy.md) — 下一步实施方向