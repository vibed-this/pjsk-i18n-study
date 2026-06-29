from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .text_normalize import normalize_literal_escapes


@dataclass(frozen=True)
class SourcesLock:
    cn_wordings_url: str
    jp_wordings_url: str
    cn_master_base: str
    jp_master_base: str
    locale: str = "zh-Hans"
    description: str = ""

    @classmethod
    def load(cls, path: Path) -> SourcesLock:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            cn_wordings_url=raw["cn_wordings_url"],
            jp_wordings_url=raw["jp_wordings_url"],
            cn_master_base=raw.get(
                "cn_master_base",
                "https://sekai-world.github.io/sekai-master-db-cn-diff",
            ),
            jp_master_base=raw.get(
                "jp_master_base",
                "https://sekai-world.github.io/sekai-master-db-diff",
            ),
            locale=raw.get("locale", "zh-Hans"),
            description=raw.get("description", ""),
        )


def load_wordings_list(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"expected JSON array in {path}")
    return data


def wordings_list_to_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    dupes: list[str] = []
    for row in rows:
        key = row.get("wordingKey")
        value = row.get("value")
        if not key:
            continue
        if key in out:
            dupes.append(key)
        raw = "" if value is None else str(value)
        out[str(key)] = normalize_literal_escapes(raw)
    if dupes:
        raise ValueError(f"duplicate wordingKey in source ({len(dupes)}): {dupes[:5]}")
    return out


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()