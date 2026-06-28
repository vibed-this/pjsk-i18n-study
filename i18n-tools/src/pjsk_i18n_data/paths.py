from __future__ import annotations

from pathlib import Path

# i18n-tools/src/pjsk_i18n_data/paths.py → repo root
REPO_ROOT = Path(__file__).resolve().parents[3]

I18N_DATA = REPO_ROOT / "i18n-data"
SOURCES_LOCK = I18N_DATA / "sources.lock.json"
OVERRIDES_UI = I18N_DATA / "overrides" / "ui.yaml"
CACHE_DIR = I18N_DATA / "cache"

OUT_ROOT = REPO_ROOT / "i18n"
OUT_UI = OUT_ROOT / "ui" / "wordings.json"
OUT_MANIFEST = OUT_ROOT / "manifest.json"
OUT_REPORT = OUT_ROOT / "reports" / "gap-report.json"

CACHE_CN = CACHE_DIR / "cn-wordings.json"
CACHE_JP = CACHE_DIR / "jp-wordings.json"