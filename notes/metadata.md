# IL2CPP 元数据取得

> 背景与总体目标见 [bg.md](./bg.md)。

## 分析目标

从项目现有 APK 中提取并解密 PJSK 的 `global-metadata.dat`，获得可供 Il2CppDumper 解析的标准 IL2CPP 元数据。

## 手段

| 工具 | 用途 |
|------|------|
| APK 解包（zip） | 从 `base.apk` 提取 `global-metadata.dat` |
| [sssekai](https://github.com/mos9527/sssekai) `il2cpp` 子命令 | 解密混淆 metadata |
| `libil2cpp.so`（split APK） | 提供解密所需密钥信息 |

依赖安装：

```bash
pip install "sssekai[il2cpp]"
```

## 过程

1. 从 `apk/base.apk` 提取：
   - `assets/bin/Data/Managed/Metadata/global-metadata.dat`（约 27.8 MB）
2. 从 `apk/split_config.arm64_v8a/lib/arm64-v8a/` 取得 `libil2cpp.so`（约 185 MB）
3. 检查原始 metadata 文件头：

   | 状态 | 魔术字节 |
   |------|----------|
   | 原始（混淆） | `17 25 47 57 ED 86 AB BC ...` |
   | 标准 IL2CPP | `AF 1B B1 FA` |

4. 执行解密：

   ```bash
   sssekai il2cpp dump/input/global-metadata.dat dump/input/libil2cpp.so dump/il2cpp/
   ```

5. 日志输出 `Metadata seems OK`，解密后文件头变为 `AF-1B-B1-FA`。

## 结论

- 元数据**已成功解密**，输出位于 `dump/il2cpp/`：
  - `global-metadata.dat` — 解密后标准 metadata
  - `il2cpp.so` — 配对的 native 二进制副本
- 动态路线（sssekai）可行，无需先逆向 `MetadataLoader::LoadMetadataFile`。
- 原始 metadata 的自定义混淆仅影响静态文件，sssekai 可自动处理日服 Android 版。

## 相关笔记

- 下游解析：[il2cpp-dump.md](./il2cpp-dump.md)
- 产物路径索引：[toolchain.md](./toolchain.md)