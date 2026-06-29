# PJSK 中文本地化 Mod 研究笔记

> 整理自 2026-06-24 研究讨论，包含背景、目标、现阶段分析与结论。

---

## 一、背景

**Project SEKAI COLORFUL STAGE! feat. 初音未来**（下称 PJSK / 世界计划）是由 Colorful Palette 开发、SEGA 发行的 Unity 手游。目前游戏仅提供日文版本，无官方中文支持。

游戏技术栈如下：

- 引擎：Unity 2022
- 脚本后端：**IL2CPP**（C# 编译为 native 二进制）
- 平台：Android / iOS
- 资源管理：Unity AssetBundle，按需下载（OnDemand）
- 网络协议：MessagePack 序列化 + AES-128-CBC 加密 + TLS 传输
- 元数据：`global-metadata.dat` 存在自定义混淆

参考的已有工作：

- [chinosk6/gakuen-imas-localify](https://github.com/chinosk6/gakuen-imas-localify) — 学园偶像大师（同为 Unity IL2CPP 游戏）本地化插件，架构高度相似，是最直接的参考
- [mos9527/sssekai](https://github.com/mos9527/sssekai) — PJSK 专用资源工具，支持 metadata 解密及资源提取
- [Sekai-World 组织](https://github.com/Sekai-World) — 维护 sekai.best 及各类资源同步工具，已将解密后的游戏数据公开同步

---

## 二、目标

编写一个 **PJSK Android 端中文本地化 Mod**，核心功能包括：

1. 将游戏 UI 文本（按钮、菜单、提示等）替换为中文
2. 将剧情 / 活动故事文本替换为中文译文
3. 注入支持 CJK 字符的字体，确保中文正常显示
4. 提供翻译数据的版本管理与热更新机制

---

## 三、现阶段分析

### 3.1 IL2CPP 反混淆

PJSK 的 `global-metadata.dat` 存在自定义混淆，魔术字节不符合标准 IL2CPP 格式，直接用 Il2CppDumper 分析会报错。

两条可行路线：

**静态路线：** 用 IDA 分析 `libil2cpp.so`，定位 `MetadataLoader::LoadMetadataFile`，逆向其解密逻辑，手动解密后再输入 Il2CppDumper。

**动态路线（推荐）：** 用 sssekai 工具自动化解密日服 Android 版 metadata；或用 Frida + frida-gadget 在运行时从内存中 dump 已解密的 metadata。iOS 版（5.5.0 以前）不需要此步骤，可直接分析，但 5.5.0 之后 iOS 版也已实施相同保护。

获得 DummyDll 后，用 dnSpy / ILSpy 可还原完整类结构，找到目标方法的偏移地址。

### 3.2 AssetBundle 解包

游戏按需下载的资源缓存于 `sdcard/Android/data/{包名}/data`，采用轻度 XOR 混淆：

- 去掉开头 4 字节的 flag
- 将 Header 前 `0x80` 字节与 `FF FF FF FF FF 00 00 00` 循环异或

还原为标准 UnityFS 格式后，可用 AssetStudio 或 UnityPy 正常解包。

剧情文本（scenario / unitystory）以 JSON 格式存在 AssetBundle 内。[Sekai-World/sekai-assets-updater](https://github.com/Sekai-World/sekai-assets-updater) 和 [sekai.best](https://sekai.best/) 已定期同步解密后的资产，可直接取用作为翻译原始素材。

### 3.3 运行时文本替换

Hook 框架层：通过 **Zygisk**（Magisk 模块）在目标进程启动时注入自定义 `.so`。

文字拦截：在注入的 native 库里 Hook 文本组件的 `set_text()` 类方法，查翻译表后改写内容。具体 Hook 目标取决于游戏实际使用的文本渲染组件（见下文「待确认项」）。

Hook 框架选择：推荐 **ShadowHook**（字节跳动开源，ARM64 友好）或 **Dobby**，二者均可处理 IL2CPP 内部方法的 hook。

参考实现：gakuen-imas-localify 同样采用 Zygisk + IL2CPP API hook 方案，LSPatch 可提供无 root 的替代注入方式。

### 3.4 中文字体注入

游戏默认字体（`EB`/`DB`）按日文设计；仅替换文本会导致简中缺字（tofu），且日文字形与简中写法在大量统一码位上不同。

**初步汉化定案（2026-06-29）**：**替换主字体**，不用 fallback 补字。

- Hook `FontAssetManager.SetupBuiltinFontAsset` onLeave，将 `+0x20` / `+0x38` 换为 **思源黑体 SC** 子集或国服 CN `TMP_FontAsset`
- 原 EB/DB 降级为新字体的 `fallbackFontAssetTable`，兜底未翻译日文与假名
- 弃用「日文字体主 + fallback 追加」：只能消 tofu，无法保证简中字形一致

详见 [text-rendering.md](./text-rendering.md) §初步汉化字体策略、[hook-strategy.md](./hook-strategy.md) §字体替换挂点。

### 3.5 服务端数据

游戏部分数据由服务端下发，使用 MessagePack 序列化，AES-128-CBC 加密（key / IV 硬编码于 IL2CPP 编译产物中），通过 TLS 传输且 TLS 证书校验发生在 libunity.so 内的 curl 层，无法通过导入根证书绕过，需 binary patch。

对汉化而言，服务端数据以静态 JSON 资产替换为主，MITM 代理方案维护成本较高，非首选。

### 3.6 文本渲染组件（待确认）

**这是目前最关键的待确认项。**

现有证据：
- 游戏个人资料系统支持 `<indent=88%>` 等 TMP 富文本标签，说明 UI 层至少部分使用了 TextMeshPro
- 游戏基于 Unity 2022，该版本已将 TMP 作为内置包默认包含
- 大多数现代 Unity 手游使用 TMP

不确定因素：
- 剧情对话框的文本渲染组件尚未通过 IL2CPP dump 直接确认
- 游戏可能在 TMP 上层封装了自定义的打字效果、振假名（furigana）支持层
- 不排除使用 Legacy `UnityEngine.UI.Text` 或完全自定义的文本渲染器

**确认方法：** 解密 metadata 后用 dnSpy 搜索 `TMPro` 命名空间，检查 `Assembly-CSharp.dll` 中文本相关类是否继承自 `TMP_Text` 或 `TextMeshProUGUI`，几分钟内可得出答案。

---

## 四、现阶段结论

### 可行性

技术上完全可行。gakuen-imas-localify 已在同类游戏上验证了完整路线，PJSK 的技术架构高度类似，核心难点均有已知解法。

### 关键路径

```
metadata 解密（sssekai）
    ↓
IL2CPP dump → 定位文本渲染类及方法偏移
    ↓
确认文本渲染组件（TMP / 自定义）
    ↓
Zygisk 模块 + native Hook 库
    ↓
字体注入 + 文本替换逻辑
    ↓
翻译数据管理（JSON + 热更新）
```

### 难点优先级

| 难度 | 问题 | 备注 |
|---|---|---|
| ★★★★★ | metadata 解密 / 符号恢复 | 每次版本更新可能变化，sssekai 可辅助 |
| ★★★★☆ | 中文字体注入 | TMP Atlas 替换涉及底层资源格式 |
| ★★★☆☆ | 文本 Hook 实现 | Frida 原型已验证偏移与调用；待 Zygisk 封装 |
| ★★★☆☆ | AssetBundle 解密 + 替换 | XOR 逻辑简单，难在资源管理与时机 |
| ★★☆☆☆ | 翻译数据管理 | 纯工程问题，维护量大但技术不难 |

### 最优起点

1. 用 sssekai 解密 metadata，用 dnSpy 打开 DummyDll，**确认文本渲染组件类型**（TMP 或自定义）
2. 参照 gakuen-imas-localify 源码，理解 Zygisk + IL2CPP hook 的工程结构
3. ~~用 Frida 脚本快速原型化文本拦截~~ → **已完成 gadget 真机验证**（见 [frida.md](./frida.md)），下一步封装 Zygisk 模块
4. 翻译素材优先从 sekai.best 同步的现有解密数据中获取

### 已确认的开放问题

- ~~剧情对话框文本渲染组件~~ → 已确认，见 [text-rendering.md](./text-rendering.md)
- ~~剧情 Hook `SetWordsInfo` 真机验证~~ → 已验证，`onEnter` 可读 `X2`/`X3`（见 [frida.md](./frida.md) §4）
- `WordingManager.Get` 返回值在 Frida 层难以直接读取，native Hook 实现方式待决
- 游戏是否使用了自定义振假名层（影响字体注入策略）→ 见 [text-rendering.md](./text-rendering.md)，无独立剧情振假名层

---

## 五、参考资料汇总

**核心工具与仓库**

- https://github.com/mos9527/sssekai — PJSK 专用资源工具
- https://github.com/chinosk6/gakuen-imas-localify — 最直接的参考实现
- https://github.com/Sekai-World/sekai-assets-updater
- https://github.com/Perfare/Il2CppDumper
- https://github.com/Perfare/Zygisk-Il2CppDumper
- https://github.com/vertesan/nitidus — Zygisk IL2CPP hook 模板

**逆向分析笔记**

- https://mos9527.com/posts/pjsk/archive-20240105/ — PJSK 逆向系列（metadata 解密、API 分析、AssetBundle 等）
- https://dev.moe/en/3045 — PJSK 早期资源结构分析（XOR 混淆、Live2D、音频加密）
- https://rylie.moe/blog/sekai-decompiling/ — PJSK IL2CPP decompile 过程记录
- https://orangeegg1937.github.io/post/android/unity-il2cpp-based-translator-part-1/ — IL2CPP API + TMP Hook 实践
- https://bbs.kanxue.com/thread-278275.htm — IL2CPP 逆向初探（metadata 混淆处理）
- https://github.com/kurikomoe/TCAA_CHS/blob/main/Unity%E6%B1%89%E5%8C%96%E6%95%99%E7%A8%8B.md — Unity IL2CPP 汉化教程

**社区数据资源**

- https://sekai.best/ — PJSK 数据库（已解密资源）
- https://github.com/Sekai-World — Sekai-World 组织（各类资源同步工具）
- https://gakumas.natsume.io/localify/android-mobile-emulator — 学园偶像大师 localify 安装文档