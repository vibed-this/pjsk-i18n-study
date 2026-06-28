from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_ui_overrides(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"overrides must be a mapping: {path}")

    out: dict[str, str] = {}
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        k = str(key)
        if isinstance(value, str):
            out[k] = value
        elif isinstance(value, dict):
            zh = value.get("zh")
            if zh is None:
                raise ValueError(f"override {k} object missing 'zh' in {path}")
            out[k] = str(zh)
        else:
            raise ValueError(f"override {k} must be string or {{zh: ...}} in {path}")
    return out