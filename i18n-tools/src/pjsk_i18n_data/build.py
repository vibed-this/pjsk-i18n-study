from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .fetch import fetch_wordings
from .overrides import load_ui_overrides
from .paths import (
    CACHE_CN,
    CACHE_JP,
    OVERRIDES_UI,
    OUT_MANIFEST,
    OUT_REPORT,
    OUT_UI,
    REPO_ROOT,
    SOURCES_LOCK,
)
from .sources import SourcesLock, load_wordings_list, utc_now_iso, wordings_list_to_map, write_json
from .validate import validate_placeholders_preserved, validate_wordings_map


@dataclass
class BuildResult:
    count: int
    override_count: int
    jp_only: list[str]
    cn_only: list[str]
    manifest_path: Path
    wordings_path: Path
    report_path: Path


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            "entry_count": len(merged),
        },
        "notes": "Runtime lookup: wordingKey → zh for WordingManager.Get on JP client",
    }
    write_json(OUT_MANIFEST, manifest)

    return BuildResult(
        count=len(merged),
        override_count=len(overrides),
        jp_only=jp_only,
        cn_only=cn_only,
        manifest_path=OUT_MANIFEST,
        wordings_path=OUT_UI,
        report_path=OUT_REPORT,
    )