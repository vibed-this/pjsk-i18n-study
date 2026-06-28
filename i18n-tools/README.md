# pjsk-i18n-data

从 Sekai-World **国服** Master diff 拉取 UI 词表与 Master 明文表，合并 `i18n-data/overrides/`，生成日服 Mod 运行时用的翻译映射。

## 用法

```bash
# 仓库根目录
uv sync
uv run --project i18n-tools pjsk-i18n fetch
uv run --project i18n-tools pjsk-i18n build
```

产物：

- `i18n/ui/wordings.json` — `wordingKey → 中文`（`WordingManager.Get`）
- `i18n/ui/plain-text.json` — `日文明文 → 中文`（`SetText`，来自 musics/characters/cards 等）
- `i18n/manifest.json` — 版本与 checksum
- `i18n/reports/gap-report.json` — 日服独有 key、plain-text 统计

缓存（不提交 git）：`i18n-data/cache/`

## Frida

构建后 `frida/run.py intercept` 自动注入 `UI_WORDINGS` / `UI_PLAIN_TEXT`（若产物存在）：`Get` 按 key、`SetText` 按日文明文替换为国服译文。