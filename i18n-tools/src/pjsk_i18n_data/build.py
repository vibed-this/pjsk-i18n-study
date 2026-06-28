from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .fetch import fetch_wordings
from .master import build_plain_text_pack
from .overrides import load_ui_overrides
from .paths import (
    CACHE_CN,
    CACHE_JP,
    OVERRIDES_UI,
    OUT_MANIFEST,
    OUT_PLAIN_TEXT,
    OUT_REPORT,
    OUT_STORY_GAP_REPORT,
    OUT_STORY_TEXT,
    OUT_UI,
    REPO_ROOT,
    SOURCES_LOCK,
)
from .sources import SourcesLock, load_wordings_list, utc_now_iso, wordings_list_to_map, write_json
from .validate import validate_placeholders_preserved, validate_wordings_map


@dataclass
class BuildResult:
    count: int
    plain_count: int
    override_count: int
    jp_only: list[str]
    cn_only: list[str]
    manifest_path: Path
    wordings_path: Path
    plain_text_path: Path
    report_path: Path


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_manifest_story(*, demo: bool = False) -> None:
    """Merge story/text.json checksum into i18n/manifest.json (creates minimal manifest if missing)."""
    if not OUT_STORY_TEXT.is_file():
        return

    manifest: dict = {}
    if OUT_MANIFEST.is_file():
        manifest = json.loads(OUT_MANIFEST.read_text(encoding="utf-8"))

    outputs = manifest.setdefault("outputs", {})
    outputs["story_text"] = str(OUT_STORY_TEXT.relative_to(REPO_ROOT)).replace("\\", "/")
    outputs["story_text_sha256"] = _sha256_file(OUT_STORY_TEXT)
    outputs["story_text_count"] = len(
        json.loads(OUT_STORY_TEXT.read_text(encoding="utf-8"))
    )

    gap: dict = {}
    if OUT_STORY_GAP_REPORT.is_file():
        gap = json.loads(OUT_STORY_GAP_REPORT.read_text(encoding="utf-8"))

    manifest["story"] = {
        "demo": demo,
        "built_at": gap.get("built_at") or utc_now_iso(),
        "stats": gap.get("stats"),
        "inventory": gap.get("inventory"),
        "gap_report": str(OUT_STORY_GAP_REPORT.relative_to(REPO_ROOT)).replace("\\", "/"),
    }

    notes = manifest.get("notes", "")
    story_note = "story jp→zh (SetWordsInfo)"
    if story_note not in notes:
        manifest["notes"] = (notes + "; " if notes else "") + story_note

    write_json(OUT_MANIFEST, manifest)


def build_ui_pack(
    *,
    fetch: bool = True,
    refresh: bool = False,
) -> BuildResult:
    if fetch:
        fetch_wordings(refresh=refresh)

    if not CACHE_CN.exists():
        raise FileNotFoundError(f"CN cache missing: {CACHE_CN} — run fetch first")

    lock = SourcesLock.load(SOURCES_LOCK)
    cn_map = wordings_list_to_map(load_wordings_list(CACHE_CN))
    jp_map: dict[str, str] = {}
    if CACHE_JP.exists():
        jp_map = wordings_list_to_map(load_wordings_list(CACHE_JP))

    overrides = load_ui_overrides(OVERRIDES_UI)
    merged = dict(cn_map)
    for key, zh in overrides.items():
        merged[key] = zh

    val = validate_wordings_map(merged)
    if not val.ok:
        raise RuntimeError("validation failed:\n" + "\n".join(val.errors))

    placeholder_val = validate_placeholders_preserved(jp_map, merged) if jp_map else None

    jp_keys = set(jp_map)
    cn_keys = set(cn_map)
    jp_only = sorted(jp_keys - cn_keys)
    cn_only = sorted(cn_keys - jp_keys)

    write_json(OUT_UI, merged)

    _, plain_stats = build_plain_text_pack(fetch=fetch, refresh=refresh)

    gap_report = {
        "built_at": utc_now_iso(),
        "locale": lock.locale,
        "counts": {
            "cn_source": len(cn_map),
            "jp_source": len(jp_map),
            "merged": len(merged),
            "overrides": len(overrides),
            "jp_only": len(jp_only),
            "cn_only": len(cn_only),
            "intersection": len(jp_keys & cn_keys) if jp_map else None,
        },
        "jp_only_keys": jp_only,
        "cn_only_sample": cn_only[:30],
        "validation_warnings": val.warnings
        + (placeholder_val.warnings if placeholder_val else []),
        "plain_text": plain_stats,
    }
    write_json(OUT_REPORT, gap_report)

    manifest = {
        "built_at": utc_now_iso(),
        "locale": lock.locale,
        "target_client": "jp",
        "sources": {
            "cn_wordings_url": lock.cn_wordings_url,
            "jp_wordings_url": lock.jp_wordings_url,
            "cn_cache_sha256": _sha256_file(CACHE_CN) if CACHE_CN.exists() else None,
            "jp_cache_sha256": _sha256_file(CACHE_JP) if CACHE_JP.exists() else None,
        },
        "outputs": {
            "ui_wordings": str(OUT_UI.relative_to(REPO_ROOT)).replace("\\", "/"),
            "ui_wordings_sha256": _sha256_file(OUT_UI),
            "ui_plain_text": str(OUT_PLAIN_TEXT.relative_to(REPO_ROOT)).replace("\\", "/"),
            "ui_plain_text_sha256": _sha256_file(OUT_PLAIN_TEXT),
            "entry_count": len(merged),
            "plain_text_count": plain_stats.get("entry_count", 0),
        },
        "notes": "Runtime: wordingKey→zh (Get); jp plaintext→zh (SetText)",
    }
    write_json(OUT_MANIFEST, manifest)

    return BuildResult(
        count=len(merged),
        plain_count=int(plain_stats.get("entry_count", 0)),
        override_count=len(overrides),
        jp_only=jp_only,
        cn_only=cn_only,
        manifest_path=OUT_MANIFEST,
        wordings_path=OUT_UI,
        plain_text_path=OUT_PLAIN_TEXT,
        report_path=OUT_REPORT,
    )