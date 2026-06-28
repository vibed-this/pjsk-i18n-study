# pjsk-i18n-data

从 Sekai-World **国服** `wordings.json` 拉取 UI 词表，合并 `i18n-data/overrides/`，生成日服 Mod 运行时用的 `wordingKey → 中文` 映射。

## 用法

```bash
# 仓库根目录
uv sync
uv run --project i18n-tools pjsk-i18n fetch
uv run --project i18n-tools pjsk-i18n build
```

产物：

- `i18n/ui/wordings.json` — 运行时查表
- `i18n/manifest.json` — 版本与 checksum
- `i18n/reports/gap-report.json` — 日服独有 key 等缺口

缓存（不提交 git）：`i18n-data/cache/`

## Frida

构建后 `frida/run.py intercept` 会自动注入 `UI_WORDINGS`（若 `i18n/ui/wordings.json` 存在），`WordingManager.Get` 按 key 替换为国服译文。