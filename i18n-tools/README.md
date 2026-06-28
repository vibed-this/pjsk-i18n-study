# pjsk-i18n-data

从 Sekai-World **国服** Master diff 拉取 UI 词表与 Master 明文表，合并 `i18n-data/overrides/`，生成日服 Mod 运行时用的翻译映射；剧情管线按 `scenarioId` 对齐 JP/CN scenario JSON。

## 用法

```bash
# 仓库根目录
uv sync
uv run --project i18n-tools pjsk-i18n fetch
uv run --project i18n-tools pjsk-i18n build

# UI + 剧情（fixtures，无需 AssetBundle）
uv run --project i18n-tools pjsk-i18n build --with-story --story-demo
```

### UI 产物

- `i18n/ui/wordings.json` — `wordingKey → 中文`（`WordingManager.Get`）
- `i18n/ui/plain-text.json` — `日文明文 → 中文`（`SetText`，来自 musics/characters/cards 等）
- `i18n/manifest.json` — 版本与 checksum
- `i18n/reports/gap-report.json` — 日服独有 key、plain-text 统计

### 剧情产物

```bash
# master diff 拉 scenarioId 清单（无需 AssetBundle）
uv run --project i18n-tools pjsk-i18n story-inventory

# fixtures 演示（Frida E2E 样本两句）
uv run --project i18n-tools pjsk-i18n story-build --demo

# 全量：需先把 scenario JSON 放入 cache（见下）
uv run --project i18n-tools pjsk-i18n story-build
```

- `i18n/story/text.json` — `日文明文 → 中文`（`TalkWindow.SetWordsInfo`）
- `i18n/reports/story-gap-report.json` — 行数不一致、仅日服 scenario、碰撞样本

**Scenario 缓存**（不提交 git，用 `sekai-assets-updater` 解包后复制）：

```
i18n-data/cache/scenario/jp/**/*.json
i18n-data/cache/scenario/cn/**/*.json
```

缓存（不提交 git）：`i18n-data/cache/`

### 字体字符集（思源黑体子集）

```bash
uv run --project i18n-tools pjsk-i18n font-chars
```

产物 `i18n/font/charset.txt`；烘焙流程见 [i18n-data/font/README.md](../i18n-data/font/README.md)。

## Frida

构建后 `frida/run.py intercept` 自动注入：

| 产物 | 模式 | Hook |
|------|------|------|
| `i18n/ui/wordings.json` | `UI_MODE=cn` | `WordingManager.Get` |
| `i18n/ui/plain-text.json` | `UI_MODE=cn` | `CustomTextMesh/CustomText.SetText` |
| `i18n/story/text.json` | `STORY_MODE=cn` | `TalkWindow.SetWordsInfo` |