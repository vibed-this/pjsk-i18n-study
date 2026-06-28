from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .master import fetch_url
from .paths import (
    CACHE_SCENARIO_CN,
    CACHE_SCENARIO_INVENTORY,
    CACHE_SCENARIO_JP,
    FIXTURE_SCENARIO_CN,
    FIXTURE_SCENARIO_JP,
    OUT_STORY_BY_SCENARIO,
    OUT_STORY_GAP_REPORT,
    OUT_STORY_TEXT,
    SOURCES_LOCK,
)
from .build import patch_manifest_story
from .sources import SourcesLock, utc_now_iso, write_json

# ScenarioSnippet.ActionType.Talk
ACTION_TALK = 1

PLAYER_NAME_PLACEHOLDER = "{{playerName}}"


@dataclass
class TalkLine:
    display_name: str
    body: str


@dataclass
class ScenarioAlignResult:
    scenario_id: str
    line_count: int
    body_pairs: int
    name_pairs: int
    status: str  # ok | line_mismatch | missing_cn | missing_jp
    detail: str = ""


@dataclass
class StoryBuildStats:
    scenarios_processed: int = 0
    scenarios_aligned: int = 0
    body_pairs: int = 0
    name_pairs: int = 0
    collisions: list[str] = field(default_factory=list)
    align_results: list[ScenarioAlignResult] = field(default_factory=list)
    jp_only_scenario_ids: list[str] = field(default_factory=list)


def _find_key(obj: dict[str, Any], *names: str) -> str | None:
    if not isinstance(obj, dict):
        return None
    lower_map = {str(k).lower(): k for k in obj}
    for name in names:
        key = lower_map.get(name.lower())
        if key is not None:
            return str(key)
    return None


def _get_field(obj: dict[str, Any], *names: str, default: Any = None) -> Any:
    key = _find_key(obj, *names)
    if key is None:
        return default
    return obj.get(key, default)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(text: str | None) -> str | None:
    if text is None:
        return None
    s = str(text)
    return s if s else None


def parse_scenario_document(data: Any) -> dict[str, Any] | None:
    """Accept Unity typetree dict or single-element list wrapper."""
    if isinstance(data, list):
        for item in data:
            doc = parse_scenario_document(item)
            if doc is not None:
                return doc
        return None
    if not isinstance(data, dict):
        return None
    scenario_id = _get_field(data, "ScenarioId", "scenarioId")
    snippets = _get_field(data, "Snippets", "snippets")
    talk_data = _get_field(data, "TalkData", "talkData")
    if scenario_id is None or snippets is None or talk_data is None:
        return None
    return data


def scenario_id_from_document(data: Any) -> str | None:
    doc = parse_scenario_document(data)
    if doc is None:
        return None
    sid = _get_field(doc, "ScenarioId", "scenarioId")
    return str(sid) if sid else None


def extract_talk_lines(doc: dict[str, Any]) -> list[TalkLine]:
    snippets = _as_list(_get_field(doc, "Snippets", "snippets"))
    talk_data = _as_list(_get_field(doc, "TalkData", "talkData"))

    ordered = sorted(snippets, key=lambda s: _as_int(_get_field(s, "Index", "index")))
    lines: list[TalkLine] = []
    for snip in ordered:
        if not isinstance(snip, dict):
            continue
        action = _as_int(_get_field(snip, "Action", "action"))
        if action != ACTION_TALK:
            continue
        ref = _as_int(_get_field(snip, "ReferenceIndex", "referenceIndex"))
        if ref < 0 or ref >= len(talk_data):
            continue
        talk = talk_data[ref]
        if not isinstance(talk, dict):
            continue
        name = _normalize_text(_get_field(talk, "WindowDisplayName", "windowDisplayName")) or ""
        body = _normalize_text(_get_field(talk, "Body", "body")) or ""
        lines.append(TalkLine(display_name=name, body=body))
    return lines


def load_scenario_file(path: Path) -> tuple[str, dict[str, Any]] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    doc = parse_scenario_document(data)
    if doc is None:
        return None
    scenario_id = scenario_id_from_document(doc)
    if not scenario_id:
        scenario_id = path.stem
    return scenario_id, doc


def discover_scenario_files(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    found: dict[str, Path] = {}
    for path in sorted(root.rglob("*.json")):
        loaded = load_scenario_file(path)
        if loaded is None:
            continue
        scenario_id, _ = loaded
        found[scenario_id] = path
    return found


def _add_pair(
    out: dict[str, str],
    collisions: list[str],
    jp: str | None,
    zh: str | None,
    *,
    scenario_id: str,
    field: str,
    line_idx: int,
) -> bool:
    if not jp or not zh or jp == zh:
        return False
    if jp in out:
        if out[jp] != zh:
            collisions.append(
                f"{scenario_id}:{field}[{line_idx}]: {jp!r} -> {out[jp]!r} vs {zh!r}"
            )
            return False
        return False
    out[jp] = zh
    return True


def align_scenario_pair(
    scenario_id: str,
    jp_doc: dict[str, Any],
    cn_doc: dict[str, Any],
    out: dict[str, str],
    collisions: list[str],
) -> ScenarioAlignResult:
    jp_lines = extract_talk_lines(jp_doc)
    cn_lines = extract_talk_lines(cn_doc)
    result = ScenarioAlignResult(
        scenario_id=scenario_id,
        line_count=len(jp_lines),
        body_pairs=0,
        name_pairs=0,
        status="ok",
    )

    if len(jp_lines) != len(cn_lines):
        result.status = "line_mismatch"
        result.detail = f"jp={len(jp_lines)} cn={len(cn_lines)}"
        return result

    for idx, (jp_line, cn_line) in enumerate(zip(jp_lines, cn_lines)):
        if _add_pair(
            out,
            collisions,
            jp_line.body,
            cn_line.body,
            scenario_id=scenario_id,
            field="body",
            line_idx=idx,
        ):
            result.body_pairs += 1
        if _add_pair(
            out,
            collisions,
            jp_line.display_name,
            cn_line.display_name,
            scenario_id=scenario_id,
            field="name",
            line_idx=idx,
        ):
            result.name_pairs += 1

    return result


def fetch_scenario_inventory(*, sources_path: Path = SOURCES_LOCK) -> dict[str, Any]:
    lock = SourcesLock.load(sources_path)

    def load_ids(base: str, tables: tuple[str, ...]) -> set[str]:
        ids: set[str] = set()
        for table in tables:
            rows = json.loads(fetch_url(f"{base.rstrip('/')}/{table}.json").decode("utf-8"))
            for row in rows:
                sid = row.get("scenarioId")
                if sid:
                    ids.add(str(sid))
        return ids

    def load_event_episode_ids(base: str) -> set[str]:
        rows = json.loads(fetch_url(f"{base}/eventStories.json").decode("utf-8"))
        ids: set[str] = set()
        for row in rows:
            for ep in row.get("eventStoryEpisodes") or []:
                sid = ep.get("scenarioId")
                if sid:
                    ids.add(str(sid))
        return ids

    jp_cards = load_ids(lock.jp_master_base, ("cardEpisodes",))
    cn_cards = load_ids(lock.cn_master_base, ("cardEpisodes",))
    jp_events = load_event_episode_ids(lock.jp_master_base)
    cn_events = load_event_episode_ids(lock.cn_master_base)

    jp_all = jp_cards | jp_events
    cn_all = cn_cards | cn_events
    common = sorted(jp_all & cn_all)
    jp_only = sorted(jp_all - cn_all)

    inventory = {
        "built_at": utc_now_iso(),
        "counts": {
            "jp_card_episodes": len(jp_cards),
            "cn_card_episodes": len(cn_cards),
            "jp_event_episodes": len(jp_events),
            "cn_event_episodes": len(cn_events),
            "jp_total": len(jp_all),
            "cn_total": len(cn_all),
            "common": len(common),
            "jp_only": len(jp_only),
        },
        "common_scenario_ids": common,
        "jp_only_scenario_ids": jp_only,
    }
    write_json(CACHE_SCENARIO_INVENTORY, inventory)
    return inventory


def build_story_maps(
    *,
    jp_dir: Path = CACHE_SCENARIO_JP,
    cn_dir: Path = CACHE_SCENARIO_CN,
    inventory_path: Path = CACHE_SCENARIO_INVENTORY,
    write_per_scenario: bool = False,
) -> tuple[dict[str, str], StoryBuildStats, dict[str, Any]]:
    jp_files = discover_scenario_files(jp_dir)
    cn_files = discover_scenario_files(cn_dir)

    if not jp_files:
        raise FileNotFoundError(
            f"no JP scenario JSON under {jp_dir} — extract with sekai-assets-updater "
            f"(REGION=JP) or run `pjsk-i18n story-build --demo`"
        )
    if not cn_files:
        raise FileNotFoundError(
            f"no CN scenario JSON under {cn_dir} — extract with sekai-assets-updater "
            f"(REGION=CN) or run `pjsk-i18n story-build --demo`"
        )

    inventory: dict[str, Any] = {}
    if inventory_path.is_file():
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))

    out: dict[str, str] = {}
    stats = StoryBuildStats()
    per_scenario: dict[str, Any] = {}

    common_ids = sorted(set(jp_files) & set(cn_files))
    for scenario_id in common_ids:
        stats.scenarios_processed += 1
        jp_loaded = load_scenario_file(jp_files[scenario_id])
        cn_loaded = load_scenario_file(cn_files[scenario_id])
        if jp_loaded is None or cn_loaded is None:
            continue
        _, jp_doc = jp_loaded
        _, cn_doc = cn_loaded

        align = align_scenario_pair(scenario_id, jp_doc, cn_doc, out, stats.collisions)
        stats.align_results.append(align)
        if align.status == "ok":
            stats.scenarios_aligned += 1
            stats.body_pairs += align.body_pairs
            stats.name_pairs += align.name_pairs
        if write_per_scenario and align.status == "ok":
            per_scenario[scenario_id] = {
                "line_count": align.line_count,
                "lines": [
                    {
                        "jp_name": jp.display_name,
                        "zh_name": cn.display_name,
                        "jp_body": jp.body,
                        "zh_body": cn.body,
                    }
                    for jp, cn in zip(
                        extract_talk_lines(jp_doc),
                        extract_talk_lines(cn_doc),
                    )
                ],
            }

    jp_only_files = sorted(set(jp_files) - set(cn_files))
    stats.jp_only_scenario_ids = jp_only_files

    gap_report = {
        "built_at": utc_now_iso(),
        "sources": {
            "jp_dir": str(jp_dir),
            "cn_dir": str(cn_dir),
            "jp_files": len(jp_files),
            "cn_files": len(cn_files),
            "common_files": len(common_ids),
        },
        "inventory": inventory.get("counts"),
        "stats": {
            "scenarios_processed": stats.scenarios_processed,
            "scenarios_aligned": stats.scenarios_aligned,
            "body_pairs": stats.body_pairs,
            "name_pairs": stats.name_pairs,
            "text_entries": len(out),
            "collision_count": len(stats.collisions),
        },
        "line_mismatches": [
            {
                "scenarioId": r.scenario_id,
                "jp_lines": r.line_count,
                "detail": r.detail,
            }
            for r in stats.align_results
            if r.status == "line_mismatch"
        ],
        "jp_only_file_ids": jp_only_files[:100],
        "jp_only_file_count": len(jp_only_files),
        "collision_samples": stats.collisions[:30],
        "inventory_jp_only_count": len(inventory.get("jp_only_scenario_ids", [])),
    }

    gap_report["_per_scenario"] = per_scenario
    return out, stats, gap_report


def build_story_pack(
    *,
    demo: bool = False,
    fetch_inventory: bool = True,
    write_per_scenario: bool = False,
) -> tuple[Path, dict[str, Any]]:
    jp_dir = FIXTURE_SCENARIO_JP if demo else CACHE_SCENARIO_JP
    cn_dir = FIXTURE_SCENARIO_CN if demo else CACHE_SCENARIO_CN

    if fetch_inventory and not demo:
        fetch_scenario_inventory()

    text_map, _stats, gap = build_story_maps(
        jp_dir=jp_dir,
        cn_dir=cn_dir,
        write_per_scenario=write_per_scenario,
    )
    write_json(OUT_STORY_TEXT, text_map)

    per_scenario = gap.pop("_per_scenario", {})
    if write_per_scenario and per_scenario:
        OUT_STORY_BY_SCENARIO.mkdir(parents=True, exist_ok=True)
        for scenario_id, payload in per_scenario.items():
            write_json(OUT_STORY_BY_SCENARIO / f"{scenario_id}.json", payload)

    write_json(OUT_STORY_GAP_REPORT, gap)
    patch_manifest_story(demo=demo)

    gap["output"] = str(OUT_STORY_TEXT)
    gap["entry_count"] = len(text_map)
    gap["demo"] = demo
    return OUT_STORY_TEXT, gap