# 剧情 dump 与 build 管线

> 前置：剧情挪用可行性见 [text-rendering.md](./text-rendering.md) §剧情文本能否直接挪用国服；运行时 Hook 见 [frida.md](./frida.md)、[hook-strategy.md](./hook-strategy.md)。工具路径见 [toolchain.md](./toolchain.md)。

## 分析目标

验证**不依赖 sekai.best**、从**官方 CDN** 拉取活动剧情 AssetBundle，解密并提取 `ScenarioSceneData` JSON，再经 `pjsk-i18n story-build` 生成 `i18n/story/text.json` 的全链路。

## 手段

| 组件 | 用途 |
|------|------|
| [sssekai](https://github.com/mos9527/sssekai) `abcache` | 官方 CDN 索引 + 增量下载加密 bundle |
| sssekai `abdecrypt` | AssetBundle 文件名 XOR 解密 |
| `i18n-tools/scripts/scenario_abcache_download.py` | 封装 `abcache`，按 regex 过滤 bundle |
| `i18n-tools/scripts/scenario_from_bundles.py` | UnityPy 从解密 bundle 提取 `ScenarioSceneData` |
| `pjsk-i18n story-build` | JP/CN scenario JSON 按 `scenarioId`+行序对齐 → `jp→zh` 表 |
| `pjsk-i18n story-inventory` | Master diff 统计共有 / 仅日服 `scenarioId`（无需 AssetBundle） |

## 过程

### 1. 端到端流程（路径 A，2026-06-29 跑通）

```
sssekai abcache（官方 CDN）
  → i18n-data/cache/ab-raw/{jp,cn}/   # 加密 bundle
  → sssekai abdecrypt（XOR）
  → i18n-data/cache/ab-dec/{jp,cn}/
  → scenario_from_bundles.py（UnityPy MonoBehaviour）
  → i18n-data/cache/scenario/{jp,cn}/*.json
  → pjsk-i18n story-build
  → i18n/story/text.json + i18n/reports/story-gap-report.json
```

**本次范围**：仅 `^event_story/.*/scenario$`（活动剧情正文容器）。**未含**卡片 `character/member/`、unitstory、actionset、profile 等。

### 2. 官方 CDN 与解密

| 区服 | 版本（本次） | bundle-info / 资产主机 |
|------|-------------|------------------------|
| JP | app **6.5.5** | `game-version.sekai.colorfulpalette.org` + `production-{hostHash}-assetbundle*.sekai.colorfulpalette.org` |
| CN | app **6.0.0** | Nuverse CDN（sssekai `app_region=cn` 自动解析） |

- bundle 列表 AES-128-CBC：JP/CN 常用 key `g2fcC0ZczN9MTJ61`、IV `msx3IV0i9XE5uYZ1`（与社区/sssekai 一致）。
- JP `bundle-info` 需游客 auth；直接调 `sssekai.entrypoint.abcache.main_abcache` 可绕过 CLI `NameError` 问题。
- 解密：`sssekai abdecrypt --input <ab-raw> --output <ab-dec>`（XOR，非整包 AES）。

### 3. 下载与提取（活动剧情示例）

```powershell
# 依赖：sssekai[il2cpp] + UnityPy + orjson（可在 sssekai 自带 venv 中跑脚本）

# JP 活动 scenario bundle
python i18n-tools/scripts/scenario_abcache_download.py `
  --region jp --filter "^event_story/.*/scenario$" `
  --download-dir i18n-data/cache/ab-raw/jp `
  --db i18n-data/cache/abcache-jp.db `
  --app-version 6.5.5 --app-hash <jp_app_hash>

# CN 同理，--region cn，版本/hash 取国服当前包

# 解密（sssekai CLI 或 entrypoint.abdecrypt）
# ab-raw → ab-dec

python i18n-tools/scripts/scenario_from_bundles.py `
  i18n-data/cache/ab-dec/jp i18n-data/cache/scenario/jp

python i18n-tools/scripts/scenario_from_bundles.py `
  i18n-data/cache/ab-dec/cn i18n-data/cache/scenario/cn
```

### 4. story-build

```powershell
uv run --project i18n-tools pjsk-i18n story-inventory   # 刷新 scenario-inventory.json
uv run --project i18n-tools pjsk-i18n story-build
# 或合并进 UI 构建：
uv run --project i18n-tools pjsk-i18n build --with-story
```

对齐逻辑（`i18n-tools/src/pjsk_i18n_data/story.py`）：

1. 取 JP/CN 目录下共有 `scenarioId` 文件；
2. 解析 `TalkData` + `Snippets` 中 `Action=Talk` 的 `ReferenceIndex`，得到有序 talk 行；
3. 行序一致则写入 `jp_body→cn_body`、`jp_displayName→cn_displayName`；
4. 行数不一致记入 `line_mismatches`，该 scenario 不参与对齐；
5. 全局 `text.json` 为 **日文明文 → 中文** 扁平表；同句多译时**先写入者优先**（`collision_count`）。

### 5. 实测数据（2026-06-29）

| 阶段 | JP | CN |
|------|----|----|
| 下载 bundle（`event_story/.../scenario`） | 206 / ~14 MB | 182 / ~12.7 MB |
| 写出 scenario JSON（写入次数 / 唯一文件） | 1696 / **1688** | 1506 / 1498 |
| story-build 共有文件 | — | 1498（与 Master 活动话数一致） |

JP 写入 1696 次但磁盘仅 1688 个唯一 `scenarioId`（**8 次同 ID 覆盖**）；`discover_scenario_files` 对重复 ID 静默取后者，提取脚本应补冲突告警。

**story-build 产出**（`manifest.json` / `story-gap-report.json`）：

| 指标 | 值 |
|------|-----|
| scenarios_processed | 1498 |
| scenarios_aligned | 1495（99.8%） |
| line_mismatches | 3：`event_115_03`、`event_145_08`、`event_150_08` |
| text_entries | **114,859** `jp→zh` |
| collision_count | 5364 |
| demo | `false` |

Master 清单（`story-inventory`）：活动共有 **1498** 话；卡片共有 **2384** 话；仅日服 **476**（190 活动 + 286 卡片）— 卡片 JSON **尚未**按路径 A 拉取。

### 6. 结构与代码复核（2026-06-29）

| 检查项 | 结论 |
|--------|------|
| `extract_talk_lines` 模型 | ✅ 与 IDA/Capstone、`computeTalkLineIdx` 一致（`Snippets` 按 `Index`，`Action=1`） |
| 3 个 `line_mismatch` | CN `TalkData`/Talk snippet **多于** JP（+1/+6/+10）；非 Talk snippet 数量一致 → **资产版本差**（JP 6.5.5 vs CN 6.0.0），非提取 bug |
| 全局 `jp→zh` collision | 5364 条记录；已对齐 scenario 中约 **3.9%** body 行（5007/127530）与按行正确译文不一致 → 扁平表为权宜方案 |
| 运行时查表 | `SetWordsInfo` 收到**处理后**明文（见 [ida-verification.md](./ida-verification.md) §剧情运行时 ID）；量产推荐 `(scenarioId, talkLineIdx)` 按行查表 |

## 结论

| 问题 | 结论 |
|------|------|
| 能否不走 sekai.best？ | **能**；官方 CDN + sssekai 已跑通活动剧情 |
| 是否有解密脚本？ | **有**；`sssekai abdecrypt` + 本仓库 `scenario_*` 脚本 |
| 台词有无全局 ID？ | **无**（不像 UI `wordingKey`）；构建期用 `(scenarioId, 行序)`；运行时 `SetWordsInfo` 仅明文 → 当前 Frida 用 **`jp→zh` 哈希表** |
| collision 原因 | 跨 scenario 重复句、同句多译；全局表先写入者优先，约 3.9% 行可能译错 |
| 代码/结构有无根本错误？ | **无**；待改进的是版本对齐、重复 ID 告警、按行查表与真机 E2E |
| 缓存是否入库？ | **否**；`i18n-data/cache/` 已在 `.gitignore` |

### 产物路径

| 路径 | 说明 |
|------|------|
| `i18n/story/text.json` | 运行时剧情替换表（`STORY_MODE=cn`） |
| `i18n/reports/story-gap-report.json` | 对齐统计、line_mismatch、jp_only 列表 |
| `i18n/manifest.json` → `story` | `demo`、`stats`、`inventory` 摘要 |
| `i18n-data/cache/scenario/{jp,cn}/` | 本地 scenario JSON（重建用） |
| `i18n-data/cache/ab-raw/`、`ab-dec/` | 中间 bundle（可删后重拉） |

### 待办

- [ ] 真机 `STORY_MODE=cn` E2E（114k 条表 + 活动剧情抽样）
- [ ] 卡片剧情：`character/member/`（及 unitstory / actionset）按同路径扩展 filter
- [ ] 行数不一致的 3 个 scenario：人工核对或 fallback 策略
- [ ] Hook `ScenarioPlayer.SnippetActionTalk` @ `0x624FC28` 注入 `(scenarioId, talkLineIdx)`（见 [ida-verification.md](./ida-verification.md)、[hook-strategy.md](./hook-strategy.md) §剧情运行时上下文）

### 相关笔记

- [text-rendering.md](./text-rendering.md) — 剧情与 UI 分流、对齐策略
- [toolchain.md](./toolchain.md) — 缓存目录索引
- [ref.md](./ref.md) — sssekai、sekai-assets-updater 链接