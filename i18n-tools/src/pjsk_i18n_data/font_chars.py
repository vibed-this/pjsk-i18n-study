from __future__ import annotations

import json
from pathlib import Path

from .paths import (
    OUT_FONT_CHARSET,
    OUT_FONT_META,
    OUT_PLAIN_TEXT,
    OUT_STORY_TEXT,
    OUT_UI,
    REPO_ROOT,
)
from .sources import utc_now_iso, write_json

# TMP 富文本与常见标点（翻译表可能未单独出现的字符）
_EXTRA_CHARS = (
    " \n\t\r"
    "0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    "…—·「」『』（）《》【】、。，；：？！"
    "<>/=%+-_*#@&|{}[]"
)


def _chars_from_text(text: str) -> set[str]:
    return set(text)


def _load_map_chars(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return set()
    out: set[str] = set()
    for key, value in data.items():
        out.update(_chars_from_text(str(key)))
        out.update(_chars_from_text(str(value)))
    return out


def collect_font_charset() -> tuple[str, dict]:
    chars: set[str] = set(_EXTRA_CHARS)
    sources: dict[str, int] = {}

    for label, path in (
        ("ui_wordings", OUT_UI),
        ("ui_plain_text", OUT_PLAIN_TEXT),
        ("story_text", OUT_STORY_TEXT),
    ):
        file_chars = _load_map_chars(path)
        sources[label] = len(file_chars)
        chars.update(file_chars)

    ordered = sorted(chars, key=lambda c: ord(c))
    text = "".join(ordered)
    meta = {
        "built_at": utc_now_iso(),
        "char_count": len(ordered),
        "codepoint_count": len({ord(c) for c in ordered}),
        "sources": sources,
        "output_charset": str(OUT_FONT_CHARSET.relative_to(REPO_ROOT)).replace("\\", "/"),
        "notes": "Subset Source Han Sans SC to this charset before TMP SDF bake",
    }
    return text, meta


def build_font_charset_files() -> tuple[Path, Path, dict]:
    text, meta = collect_font_charset()
    OUT_FONT_CHARSET.parent.mkdir(parents=True, exist_ok=True)
    OUT_FONT_CHARSET.write_text(text, encoding="utf-8")
    write_json(OUT_FONT_META, meta)
    return OUT_FONT_CHARSET, OUT_FONT_META, meta