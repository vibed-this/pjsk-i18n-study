# IDA 二进制验证

> RVA 来源见 [il2cpp-dump.md](./il2cpp-dump.md)。组件背景见 [text-rendering.md](./text-rendering.md)。

## 分析目标

验证 Il2CppDumper 给出的方法 RVA 在 `libil2cpp.so` 中是否为有效函数入口，并通过反汇编确认参数传递与行为，为 Frida / Zygisk Hook 提供最终偏移。

## 手段

| 工具 | 用途 |
|------|------|
| IDA Pro 8.3 | 打开 `libil2cpp.so.i64` |
| IDA Pro MCP | 远程调用 `lookup_funcs`、`disasm`、`xrefs_to`、`py_eval` 等 |
| Il2CppDumper `script.json` | 提供待验证的 RVA 对照 |

分析对象：

```
apk/split_config.arm64_v8a/lib/arm64-v8a/libil2cpp.so.i64
```

限制：当前环境 **Hex-Rays 不可用**（`hexrays_ready: false`），仅通过 ARM64 反汇编分析；符号未批量导入（`ida.py` 需交互选文件），手动重命名了 8 个关键函数。

## 过程

1. MCP `server_health` 确认 IDA 已加载 `libil2cpp.so`，`auto_analysis_ready: true`。
2. 对 4 个核心 Hook 候选逐一 `lookup_funcs` + `disasm` + `xrefs_to`。
3. 发现 Il2CppDumper RVA 与 IDA 函数入口存在轻微偏差（codegen 前缀），Hook 应打在 **IDA 识别的函数入口**。
4. 通过 `py_eval` 从 `script.json` 读取地址并重命名关键函数，保存 `.i64`。

## 各函数验证详情

### `Sekai_WordingManager_Get` — UI 词表查找

| 项 | 值 |
|----|-----|
| Il2CppDumper RVA | `0x60242AC` |
| IDA 函数入口 | `0x60241BC`（`sub_60241BC` → 已重命名） |
| 大小 | `0x114` |

行为：IL2CPP 生成的静态方法包装器；初始化静态字段后通过 vtable 查找，以 `BR X3` 间接跳转结束。仅 1 处 metadata 数据引用（经 il2cpp_codegen 间接调用）。

### `Sekai_TalkWindow_SetWordsInfo` — 剧情文本入口

| 项 | 值 |
|----|-----|
| Il2CppDumper RVA | `0x6264FD8` |
| IDA 函数入口 | `0x6264FD8`（完全吻合） |
| 大小 | `0xD8` |

ARM64 参数：

| 寄存器 | 含义 |
|--------|------|
| `X0` | this |
| `W1` | characterId |
| `X2` | displayName |
| `X3` | words（剧情正文） |
| `X4` | voiceId |
| `W5` | bookmarkSequenceId |
| `W6` | emotion |

行为：将 `words` 写入 `[this+0xA0]`，保留字符串引用后 tail-call 到 `Sekai_TalkWindow_AddLog`（`0x6268DD0`）。有 **5 处**直接代码引用。

### `Sekai_UI_CustomTextMesh_SetText` — 通用 TMP 文本设置

| 项 | 值 |
|----|-----|
| Il2CppDumper RVA | `0x4F27590` |
| IDA 函数入口 | `0x4F27530` |
| 大小 | `0xC0` |

行为：`X1` = 文本字符串；先调父类 vtable（`[vtable+0x298]`），再调格式化函数，最后 `BR X2` 跳转。有 **30+** 调用者。

### `Sekai_FontAssetManager_SetupBuiltinFontAsset` — 内置字体加载

| 项 | 值 |
|----|-----|
| Il2CppDumper RVA | `0x61028AC` |
| IDA 函数入口 | `0x61028AC`（完全吻合） |
| 大小 | `0x27C` |

行为：通过资源加载函数取得 `TMP_FontAsset`，写入 `[this+0x28/0x30/0x40]`，操作 fallback 表（`[font+0x138]`），调用 `ClearFallbackFontAsset`。调用者为主初始化流程（`sub_6029F8C`）。

### `TMPro_TMP_Text_set_text` — TMP 底层兜底

| 项 | 值 |
|----|-----|
| Il2CppDumper RVA | `0xA8D1BE8` |
| IDA 函数入口 | `0xA8D1B98` |
| 大小 | `0x138` |

行为：`X0` = this，`X1` = value；读取 `[this+0x138]`（m_text），比较后更新。所有 TMP 文本的最终入口，但范围过宽。

## 结论

- 4 个核心 Hook 候选在二进制中**均为有效函数**，无额外混淆导致入口不可识别。
- RVA 与 IDA 入口的偏差（`0x50`~`0xF0`）属 IL2CPP codegen 正常现象，**Hook 地址以 IDA 函数入口为准**。
- IDA 中已重命名 8 个关键函数并保存至 `.i64`。

## 相关笔记

- Hook 方案：[hook-strategy.md](./hook-strategy.md)
- 工具与环境：[toolchain.md](./toolchain.md)