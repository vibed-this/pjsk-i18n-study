# Il2CppDumper 静态解析

> 前置步骤见 [metadata.md](./metadata.md)。

## 分析目标

将解密后的 metadata 与 `libil2cpp.so` 解析为可读的类结构、方法签名及 RVA 偏移，供后续 Hook 目标筛选。

## 手段

| 工具 | 版本 | 用途 |
|------|------|------|
| Il2CppDumper | v6.7.46 | 生成 dump.cs、script.json、DummyDll |
| dnSpy / ILSpy | — | 可打开 DummyDll 进一步浏览类结构（未在本阶段执行） |

## 过程

1. 输入文件：
   - `dump/il2cpp/il2cpp.so`
   - `dump/il2cpp/global-metadata.dat`
2. Il2CppDumper 初始化信息（按游戏版本）：

| 版本 | Metadata / Il2Cpp | CodeRegistration | MetadataRegistration |
|------|-------------------|------------------|----------------------|
| 6.5.5（基线） | 31 / 31 | `0xACDB068` | `0xB15A060` |
| **6.6.0**（当前 `apk/`） | 31 / 31 | **`0xACEBF10`** | **`0xB16B538`** |

3. 警告：`ERROR: This file may be protected`（指 `libil2cpp.so` 存在一定保护），但 dump 仍正常完成。
4. 产物输出至 `tools/Il2CppDumper/`（当前为 **6.6.0** dump；6.5.5 产物未单独归档）。

## 结论

| 产物 | 路径 | 用途 |
|------|------|------|
| 类结构 dump | `tools/Il2CppDumper/dump.cs` | 浏览所有类、方法、字段 |
| 方法地址表 | `tools/Il2CppDumper/script.json` | 方法 RVA 与签名 |
| 伪 .NET 程序集 | `tools/Il2CppDumper/DummyDll/` | dnSpy / ILSpy 可视化 |
| 字符串字面量 | `tools/Il2CppDumper/stringliteral.json` | 游戏内嵌字符串 |
| C 头文件 | `tools/Il2CppDumper/il2cpp.h` | native 开发参考 |

Il2CppDumper 解决了「找什么类、什么方法」；尚不能确认二进制中对应地址是否可直接 Hook。二进制验证见 [ida-verification.md](./ida-verification.md)。

## 相关笔记

- 上游解密：[metadata.md](./metadata.md)
- 文本组件分析：[text-rendering.md](./text-rendering.md)
- 产物路径索引：[toolchain.md](./toolchain.md)