# 工具链与产物

> 各分析主题见 [metadata.md](./metadata.md)、[il2cpp-dump.md](./il2cpp-dump.md)、[ida-verification.md](./ida-verification.md)、[frida.md](./frida.md)。

## 分析目标

记录逆向分析所需的工具、环境就绪状态，以及各阶段产物的存放路径。

## 手段

本地工具安装、APK 解包、sssekai 解密、Il2CppDumper dump、IDA Pro + MCP 联调、Frida gadget 真机注入。

## 过程

按关键路径依次搭建：

```
APK 解包 → sssekai 解密 metadata → Il2CppDumper → IDA 验证 Hook 点 → Frida gadget 真机验证
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
| Frida（PC 端） | ✅ 17.10.1 |
| Android SDK | ✅ `D:\SDK\Android`（adb / apksigner / zipalign） |
| frida-gadget 补丁 | ✅ `frida/gadget/out/*.gadget.apk`，已安装 TB322FC |
| Frida 动态验证（真机） | ✅ gadget 联调成功，三 Hook 点计数已验证 |
| sssekai | ✅ v0.8.0 + `[il2cpp]` extra |

### 未就绪 / 搁置

| 组件 | 说明 |
|------|------|
| Hex-Rays | 不可用，仅反汇编分析 |
| Il2CppDumper 符号批量导入 IDA | `ida_py3.py` 需交互选文件，未执行 |
| Frida 动态验证（模拟器） | frida-server + ARM 转译不稳定，spawn 后未见 il2cpp 加载 |
| 游戏版本号（本地 APK） | 本地 `apk/base.apk` **6.6.0**（`versionCode=300118`）；设备可能仍装 6.5.5 gadget |
| gakuen-imas-localify 源码 | Zygisk 模块参考，未克隆 |
| 文本内容动态抓取 | Hook 计数 OK，字符串读取脚本待改进 |

## 结论

静态分析 + IDA 验证 + Frida 真机原型已打通。当前阻塞项：Hex-Rays、模拟器动态环境、Zygisk 封装。产物体积极大，已通过 `.gitignore` 排除出版本控制。

### 偏移与游戏版本绑定

| 项 | 值 / 说明 |
|----|-----------|
| Hook RVA 配置 | `frida/lib/offsets.js`（IDA 入口，非运行时 base） |
| 当前分析版本 | 本地静态分析 **6.6.0**；真机 gadget 可能仍为 **6.5.5**（需重打补丁） |
| 版本不一致风险 | 设备 APK ≠ 本地分析 so → Hook 可能装得上但行为错误；见 `frida/gadget/README.md` |
| 更新后流程 | Il2CppDumper → IDA → 更新 `offsets.js` → `probe` + E2E（详见 [hook-strategy.md](./hook-strategy.md) §版本更新） |

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

apk/
├── base.apk
├── split_config.arm64_v8a.apk
└── split_UnityDataAssetPack.apk

apk/split_config.arm64_v8a/lib/arm64-v8a/
├── libil2cpp.so
└── libil2cpp.so.i64             # IDA 数据库（已重命名关键函数）

frida/
├── hook_monitor_bundle.js       # 真机验证用监控脚本
├── device.py                    # adb forward + Frida 连接
└── gadget/
    ├── patch_apk.ps1 / install.ps1 / connect.ps1
    ├── tools/                   # apktool, libfrida-gadget.so, debug.keystore
    └── out/                     # 签名后的 *.gadget.apk

i18n/                            # 提交 git 的翻译包
├── manifest.json
├── ui/wordings.json
├── ui/plain-text.json
├── story/text.json              # 剧情 jp→zh（story-build 产出）
└── reports/story-gap-report.json

i18n-data/                       # 管线数据（cache 不入库）
├── cache/
│   ├── wordings-{jp,cn}.json    # UI 词表缓存
│   ├── scenario-inventory.json  # Master scenarioId 交叉统计
│   ├── abcache-{jp,cn}.db       # sssekai abcache 索引
│   ├── ab-raw/{jp,cn}/          # 加密 AssetBundle
│   ├── ab-dec/{jp,cn}/          # XOR 解密后 bundle
│   └── scenario/{jp,cn}/        # ScenarioSceneData JSON
├── fixtures/scenario/           # story-build --demo
└── font/                        # 字体子集源（见 i18n-data/font/README.md）

i18n-tools/scripts/
├── scenario_abcache_download.py # sssekai abcache 封装
└── scenario_from_bundles.py     # UnityPy 提取 scenario JSON
```

## 相关笔记

- [frida.md](./frida.md) — gadget 补丁与联调流程
- [ref.md](./ref.md) — 外部参考资料汇总
- [hook-strategy.md](./hook-strategy.md) — 下一步实施方向
- [story-pipeline.md](./story-pipeline.md) — 剧情 CDN dump 与 story-build