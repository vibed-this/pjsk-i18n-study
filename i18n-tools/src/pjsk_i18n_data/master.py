from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .fetch import FetchResult
from .paths import CACHE_DIR, MASTER_BASE_CN, MASTER_BASE_JP, OUT_PLAIN_TEXT, SOURCES_LOCK
from .sources import SourcesLock, utc_now_iso, write_json


@dataclass(frozen=True)
class MasterTableSpec:
    name: str
    id_field: str
    text_fields: tuple[str, ...]
    composites: tuple[tuple[str, ...], ...] = field(default_factory=tuple)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_url(url: str, *, timeout: float = 120.0) -> bytes:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content


MASTER_TABLES: tuple[MasterTableSpec, ...] = (
    MasterTableSpec(
        "gameCharacters",
        "id",
        ("firstName", "givenName"),
        composites=(("firstName", "givenName"),),
    ),
    MasterTableSpec(
        "musics",
        "id",
        ("title", "pronunciation", "lyricist", "composer", "arranger", "description"),
    ),
    MasterTableSpec("musicVocals", "id", ("caption",)),
    MasterTableSpec(
        "cards",
        "id",
        ("prefix", "cardSkillName", "specialTrainingSkillName", "gachaPhrase", "flavorText"),
    ),
    MasterTableSpec(
        "characterProfiles",
        "characterId",
        (
            "characterVoice",
            "school",
            "schoolYear",
            "hobby",
            "specialSkill",
            "favoriteFood",
            "hatedFood",
            "weak",
            "introduction",
        ),
    ),
)


def _master_url(base: str, table: str) -> str:
    return f"{base.rstrip('/')}/{table}.json"


def _cache_path(label: str, table: str) -> Path:
    return CACHE_DIR / f"{label}-{table}.json"


def fetch_master_tables(
    *,
    sources_path: Path = SOURCES_LOCK,
    refresh: bool = False,
) -> list[FetchResult]:
    lock = SourcesLock.load(sources_path)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    results: list[FetchResult] = []

    for spec in MASTER_TABLES:
        for label, base in (("jp", lock.jp_master_base), ("cn", lock.cn_master_base)):
            url = _master_url(base, spec.name)
            out_path = _cache_path(label, spec.name)
            if out_path.exists() and not refresh:
                raw = out_path.read_bytes()
                rows = json.loads(raw.decode("utf-8"))
            else:
                body = fetch_url(url)
                out_path.write_bytes(body)
                raw = body
                rows = json.loads(body.decode("utf-8"))
            results.append(
                FetchResult(
                    label=f"{label}:{spec.name}",
                    url=url,
                    path=out_path,
                    count=len(rows),
                    sha256=_sha256_bytes(raw),
                )
            )
    return results


def _load_table(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"expected JSON array in {path}")
    return data


def _row_id(row: dict[str, Any], id_field: str) -> Any:
    if id_field not in row:
        raise KeyError(f"missing {id_field!r} in row keys={list(row)[:8]}")
    return row[id_field]


def _field_text(row: dict[str, Any], field: str) -> str | None:
    if field not in row:
        return None
    val = row[field]
    if val is None:
        return None
    text = str(val).strip()
    return text or None


def _composite_text(row: dict[str, Any], fields: tuple[str, ...]) -> str | None:
    parts = [_field_text(row, f) for f in fields]
    if any(p is None for p in parts):
        return None
    return "".join(parts)  # type: ignore[arg-type]


def build_plain_text_map(
    *,
    sources_path: Path = SOURCES_LOCK,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Join JP/CN master rows by id; map differing text fields jp → zh."""
    out: dict[str, str] = {}
    collisions: list[str] = []
    stats: dict[str, Any] = {"tables": {}, "pairs": 0, "skipped_same": 0, "skipped_empty": 0}

    for spec in MASTER_TABLES:
        jp_path = _cache_path("jp", spec.name)
        cn_path = _cache_path("cn", spec.name)
        if not jp_path.exists() or not cn_path.exists():
            raise FileNotFoundError(
                f"missing master cache for {spec.name} — run fetch (jp={jp_path.exists()} cn={cn_path.exists()})"
            )

        jp_rows = _load_table(jp_path)
        cn_rows = _load_table(cn_path)
        jp_by_id = {_row_id(r, spec.id_field): r for r in jp_rows}
        cn_by_id = {_row_id(r, spec.id_field): r for r in cn_rows}
        common_ids = set(jp_by_id) & set(cn_by_id)

        table_pairs = 0
        table_same = 0
        table_empty = 0

        def add_pair(jp_text: str | None, cn_text: str | None) -> None:
            nonlocal table_pairs, table_same, table_empty
            if not jp_text or not cn_text:
                table_empty += 1
                return
            if jp_text == cn_text:
                table_same += 1
                return
            if jp_text in out:
                if out[jp_text] != cn_text:
                    collisions.append(
                        f"{spec.name}: {jp_text!r} → {out[jp_text]!r} vs {cn_text!r}"
                    )
                    return
                table_same += 1
                return
            out[jp_text] = cn_text
            table_pairs += 1

        for row_id in common_ids:
            jp_row = jp_by_id[row_id]
            cn_row = cn_by_id[row_id]
            for field in spec.text_fields:
                add_pair(_field_text(jp_row, field), _field_text(cn_row, field))
            for composite in spec.composites:
                add_pair(_composite_text(jp_row, composite), _composite_text(cn_row, composite))

        stats["tables"][spec.name] = {
            "jp_rows": len(jp_rows),
            "cn_rows": len(cn_rows),
            "common_ids": len(common_ids),
            "pairs_added": table_pairs,
            "skipped_same": table_same,
            "skipped_empty": table_empty,
        }
        stats["pairs"] += table_pairs
        stats["skipped_same"] += table_same
        stats["skipped_empty"] += table_empty

    stats["collision_count"] = len(collisions)
    stats["collision_samples"] = collisions[:20]
    stats["built_at"] = utc_now_iso()
    return out, stats


def build_plain_text_pack(
    *,
    fetch: bool = True,
    refresh: bool = False,
) -> tuple[Path, dict[str, Any]]:
    if fetch:
        fetch_master_tables(refresh=refresh)
    plain_map, stats = build_plain_text_map()
    write_json(OUT_PLAIN_TEXT, plain_map)
    stats["output"] = str(OUT_PLAIN_TEXT)
    stats["entry_count"] = len(plain_map)
    return OUT_PLAIN_TEXT, stats