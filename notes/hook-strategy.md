# Hook 策略

> 组件分析见 [text-rendering.md](./text-rendering.md)。偏移验证见 [ida-verification.md](./ida-verification.md)。

## 分析目标

综合 Il2CppDumper 类结构分析与 IDA 二进制验证，确定运行时文本替换与字体注入的 Hook 方案。

## 手段

- Il2CppDumper 类继承关系与调用链分析
- IDA 反汇编确认 ARM64 参数传递与函数入口
- 参照 gakuen-imas-localify 的 Zygisk + IL2CPP Hook 路线（尚未实施）

## 过程

1. 从 `dump.cs` 确认文本流经 `WordingManager`（UI）与 `TalkWindow`（剧情）两条主线。
2. 在 IDA 中验证各候选函数的入口地址、参数寄存器与调用频率。
3. 排除仅在 metadata 中引用的间接调用点，优先选择有直接 `xrefs_to` 的函数。
4. 按覆盖范围与性能开销分层，确定优先级。

## 推荐 Hook 点（按优先级）

```
剧情文本  → TalkWindow.SetWordsInfo   @ 0x6264FD8   替换 X2（角色名）/ X3（正文）
UI 文本   → WordingManager.Get        @ 0x60241BC   key → 中文 lookup，替换返回值
通用兜底  → CustomTextMesh.SetText    @ 0x4F27530   替换 X1（文本字符串）
字体注入  → FontAssetManager.SetupBuiltinFontAsset @ 0x61028AC  注入 CJK fallback
次级兜底  → TMP_Text.set_text         @ 0xA8D1B98   替换 X1（所有 TMP 文本）
```

## 策略说明

| 层级 | 函数 | 优势 | 劣势 |
|------|------|------|------|
| 剧情 | `SetWordsInfo` | 在打字机效果之前拦截；参数明确；调用者少 | 仅覆盖剧情对话 |
| UI | `WordingManager.Get` | 一次 Hook 覆盖大部分菜单/按钮词表 | 静态方法包装器，需在入口拦截 |
| 兜底 | `CustomTextMesh.SetText` | 覆盖所有 CustomTextMesh 实例 | 调用频繁，需高效 lookup |
| 字体 | `SetupBuiltinFontAsset` | 在字体加载时注入 fallback | 需准备 CJK TMP_FontAsset |
| 底层 | `TMP_Text.set_text` | 覆盖所有 TMP 文本 | 范围过宽，性能压力大 |

## 结论

- 静态研究阶段的 Hook 目标选择**已完成**，可进入 Frida 原型验证。
- UI 文本需维护 `WordingKey → 中文` 词表；剧情文本可在 `SetWordsInfo` 层按原文 lookup 替换。
- 字体方案优先考虑向 `TMP_FontAsset.fallbackFontAssetTable` 注入含 CJK 字符的子集字体。

## 下一步

1. **Frida 原型**：在 Android 设备上 Hook `TalkWindow.SetWordsInfo` 与 `WordingManager.Get`，验证文本拦截可行性。
2. **Zygisk 模块**：参照 gakuen-imas-localify 封装 native Hook 库。
3. **翻译数据**：从 sekai.best 同步 scenario JSON 与 MasterWording 词表，建立 key/原文 → 中文映射。

## 相关笔记

- 环境与阻塞项：[toolchain.md](./toolchain.md)