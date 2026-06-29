"""Count JP story dialogue volume from sekai.best scenario assets."""

from __future__ import annotations

import asyncio
import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import httpx

from .master import fetch_url
from .paths import SOURCES_LOCK
from .sources import SourcesLock
from .story import extract_talk_lines, parse_scenario_document

ASSET_BASE = "https://storage.sekai.best/sekai-jp-assets"
FULLSCREEN_TEXT = 24
MASTER_BASE = "https://sekai-world.github.io/sekai-master-db-diff"


@dataclass
class StoryTarget:
    story_type: str
    scenario_id: str
    url: str


@dataclass
class StoryStats:
    scenarios_total: int = 0
    scenarios_ok: int = 0
    scenarios_failed: int = 0
    talk_lines: int = 0
    fullscreen_lines: int = 0
    chars_body: int = 0
    chars_name: int = 0
    chars_fullscreen: int = 0
    unique_body_strings: set[str] = field(default_factory=set)
    unique_name_strings: set[str] = field(default_factory=set)
    by_type: dict[str, dict[str, int]] = field(
        default_factory=lambda: defaultdict(
            lambda: {
                "scenarios_ok": 0,
                "talk_lines": 0,
                "fullscreen_lines": 0,
                "chars_body": 0,
                "chars_name": 0,
                "chars_fullscreen": 0,
            }
        )
    )
    failed_samples: list[str] = field(default_factory=list)


def _load_json(url: str) -> Any:
    return json.loads(fetch_url(url).decode("utf-8"))


def _char_len(text: str) -> int:
    return len(text)


def _extract_fullscreen_text(doc: dict[str, Any]) -> list[str]:
    snippets = doc.get("Snippets") or doc.get("snippets") or []
    effects = doc.get("SpecialEffectData") or doc.get("specialEffectData") or []
    out: list[str] = []
    for snip in snippets:
        if not isinstance(snip, dict):
            continue
        action = int(snip.get("Action", snip.get("action", -1)))
        if action != 2:  # SnippetAction.SpecialEffect
            continue
        ref = int(snip.get("ReferenceIndex", snip.get("referenceIndex", -1)))
        if ref < 0 or ref >= len(effects):
            continue
        effect = effects[ref]
        if not isinstance(effect, dict):
            continue
        effect_type = int(effect.get("EffectType", effect.get("effectType", -1)))
        if effect_type != FULLSCREEN_TEXT:
            continue
        text = effect.get("StringVal") or effect.get("stringVal") or ""
        if text:
            out.append(str(text))
    return out


def collect_story_targets(*, master_base: str = MASTER_BASE) -> list[StoryTarget]:
    targets: list[StoryTarget] = []
    seen_urls: set[str] = set()

    def add(story_type: str, scenario_id: str, url: str) -> None:
        if url in seen_urls:
            return
        seen_urls.add(url)
        targets.append(StoryTarget(story_type, scenario_id, url))

    event_stories = _load_json(f"{master_base}/eventStories.json")
    for chapter in event_stories:
        bundle = chapter["assetbundleName"]
        for ep in chapter.get("eventStoryEpisodes") or []:
            sid = ep["scenarioId"]
            add(
                "eventStory",
                sid,
                f"{ASSET_BASE}/event_story/{bundle}/scenario/{sid}.asset",
            )

    unit_stories = _load_json(f"{master_base}/unitStories.json")
    for unit in unit_stories:
        for chapter in unit.get("chapters") or []:
            bundle = chapter["assetbundleName"]
            for ep in chapter.get("episodes") or []:
                sid = ep["scenarioId"]
                add(
                    "unitStory",
                    sid,
                    f"{ASSET_BASE}/scenario/unitstory/{bundle}/{sid}.asset",
                )

    for profile in _load_json(f"{master_base}/characterProfiles.json"):
        sid = profile.get("scenarioId")
        if sid:
            add("charaStory", sid, f"{ASSET_BASE}/scenario/profile/{sid}.asset")

    cards = {c["id"]: c for c in _load_json(f"{master_base}/cards.json")}
    for ep in _load_json(f"{master_base}/cardEpisodes.json"):
        sid = ep.get("scenarioId")
        if not sid:
            continue
        bundle = ep.get("assetbundleName")
        if not bundle:
            card = cards.get(ep.get("cardId"))
            bundle = card.get("assetbundleName") if card else None
        if bundle:
            add(
                "cardStory",
                sid,
                f"{ASSET_BASE}/character/member/{bundle}/{sid}.asset",
            )

    for action in _load_json(f"{master_base}/actionSets.json"):
        sid = action.get("scenarioId")
        if not sid:
            continue
        group = action["id"] // 100
        add(
            "areaTalk",
            sid,
            f"{ASSET_BASE}/scenario/actionset/group{group}/{sid}.asset",
        )

    for chapter in _load_json(f"{master_base}/specialStories.json"):
        ch_bundle = chapter.get("assetbundleName", "")
        for ep in chapter.get("episodes") or []:
            sid = ep.get("scenarioId")
            if not sid:
                continue
            if sid.startswith("op"):
                path = f"scenario/special/{ch_bundle}/{sid}.asset"
            else:
                ep_bundle = ep.get("assetbundleName", "")
                path = f"scenario/special/{ep_bundle}/{sid}.asset"
            add("specialStory", sid, f"{ASSET_BASE}/{path}")

    return targets


def sample_story_targets(
    targets: list[StoryTarget],
    *,
    per_type: int = 60,
    seed: int = 42,
) -> tuple[list[StoryTarget], dict[str, int]]:
    """Stratified random sample; keeps all targets when a type has <= per_type items."""
    by_type: dict[str, list[StoryTarget]] = defaultdict(list)
    for target in targets:
        by_type[target.story_type].append(target)

    rng = random.Random(seed)
    sampled: list[StoryTarget] = []
    population: dict[str, int] = {}
    for story_type in sorted(by_type):
        items = by_type[story_type]
        population[story_type] = len(items)
        if len(items) <= per_type:
            sampled.extend(items)
        else:
            sampled.extend(rng.sample(items, per_type))
    return sampled, population


async def _fetch_one(
    client: httpx.AsyncClient, target: StoryTarget
) -> tuple[StoryTarget, dict[str, Any] | None, str | None]:
    try:
        resp = await client.get(target.url)
        if resp.status_code != 200:
            return target, None, f"HTTP {resp.status_code}"
        data = resp.json()
        doc = parse_scenario_document(data)
        if doc is None:
            return target, None, "parse failed"
        return target, doc, None
    except Exception as exc:  # noqa: BLE001
        return target, None, str(exc)


def _accumulate(stats: StoryStats, target: StoryTarget, doc: dict[str, Any]) -> None:
    stats.scenarios_ok += 1
    bucket = stats.by_type[target.story_type]
    bucket["scenarios_ok"] += 1

    for line in extract_talk_lines(doc):
        stats.talk_lines += 1
        bucket["talk_lines"] += 1
        if line.body:
            stats.chars_body += _char_len(line.body)
            bucket["chars_body"] += _char_len(line.body)
            stats.unique_body_strings.add(line.body)
        if line.display_name:
            stats.chars_name += _char_len(line.display_name)
            bucket["chars_name"] += _char_len(line.display_name)
            stats.unique_name_strings.add(line.display_name)

    for text in _extract_fullscreen_text(doc):
        stats.fullscreen_lines += 1
        bucket["fullscreen_lines"] += 1
        stats.chars_fullscreen += _char_len(text)
        bucket["chars_fullscreen"] += _char_len(text)


async def compute_story_stats(
    *,
    master_base: str = MASTER_BASE,
    concurrency: int = 32,
    limit: int | None = None,
    sample_per_type: int | None = None,
    sample_seed: int = 42,
) -> tuple[StoryStats, list[StoryTarget], dict[str, int] | None]:
    all_targets = collect_story_targets(master_base=master_base)
    population: dict[str, int] | None = None
    if sample_per_type is not None:
        targets, population = sample_story_targets(
            all_targets, per_type=sample_per_type, seed=sample_seed
        )
    elif limit is not None:
        targets = all_targets[:limit]
    else:
        targets = all_targets

    stats = StoryStats(scenarios_total=len(targets))
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:

        async def run_one(target: StoryTarget):
            async with sem:
                return await _fetch_one(client, target)

        tasks = [asyncio.create_task(run_one(t)) for t in targets]
        for coro in asyncio.as_completed(tasks):
            target, doc, err = await coro
            if doc is None:
                stats.scenarios_failed += 1
                if len(stats.failed_samples) < 20:
                    stats.failed_samples.append(f"{target.story_type}:{target.scenario_id} {err}")
                continue
            _accumulate(stats, target, doc)

    return stats, targets, population


def _extrapolate_sample(
    stats: StoryStats,
    population: dict[str, int],
) -> dict[str, Any]:
    est: dict[str, dict[str, float | int]] = {}
    totals = {
        "scenarios": 0,
        "talk_lines": 0.0,
        "fullscreen_lines": 0.0,
        "chars_body": 0.0,
        "chars_name": 0.0,
        "chars_fullscreen": 0.0,
    }
    for story_type, pop in population.items():
        sample = stats.by_type.get(story_type)
        if not sample or sample["scenarios_ok"] == 0:
            continue
        ok = sample["scenarios_ok"]
        factor = pop / ok
        row = {
            "population": pop,
            "sample_ok": ok,
            "est_talk_lines": int(round(sample["talk_lines"] * factor)),
            "est_chars_body": int(round(sample["chars_body"] * factor)),
            "est_chars_name": int(round(sample["chars_name"] * factor)),
            "est_chars_fullscreen": int(round(sample["chars_fullscreen"] * factor)),
        }
        row["est_chars_dialogue"] = row["est_chars_body"] + row["est_chars_name"]
        row["est_chars_total"] = row["est_chars_dialogue"] + row["est_chars_fullscreen"]
        est[story_type] = row
        totals["scenarios"] += pop
        totals["talk_lines"] += row["est_talk_lines"]
        totals["chars_body"] += row["est_chars_body"]
        totals["chars_name"] += row["est_chars_name"]
        totals["chars_fullscreen"] += row["est_chars_fullscreen"]
    totals["chars_dialogue"] = int(totals["chars_body"] + totals["chars_name"])
    totals["chars_total"] = int(totals["chars_dialogue"] + totals["chars_fullscreen"])
    totals["talk_lines"] = int(totals["talk_lines"])
    totals["chars_body"] = int(totals["chars_body"])
    totals["chars_name"] = int(totals["chars_name"])
    totals["chars_fullscreen"] = int(totals["chars_fullscreen"])
    return {"by_type": est, "total": totals}


def stats_to_report(
    stats: StoryStats,
    *,
    population: dict[str, int] | None = None,
    sample_per_type: int | None = None,
) -> dict[str, Any]:
    chars_dialogue = stats.chars_body + stats.chars_name
    chars_total = chars_dialogue + stats.chars_fullscreen
    report: dict[str, Any] = {
        "scenarios_total": stats.scenarios_total,
        "scenarios_ok": stats.scenarios_ok,
        "scenarios_failed": stats.scenarios_failed,
        "talk_lines": stats.talk_lines,
        "fullscreen_lines": stats.fullscreen_lines,
        "chars_body": stats.chars_body,
        "chars_name": stats.chars_name,
        "chars_fullscreen": stats.chars_fullscreen,
        "chars_dialogue": chars_dialogue,
        "chars_total": chars_total,
        "unique_body_strings": len(stats.unique_body_strings),
        "unique_name_strings": len(stats.unique_name_strings),
        "by_type": dict(stats.by_type),
        "failed_samples": stats.failed_samples,
    }
    if population is not None and sample_per_type is not None:
        report["sample"] = {
            "per_type": sample_per_type,
            "population_total": sum(population.values()),
            "population_by_type": population,
        }
        report["estimate"] = _extrapolate_sample(stats, population)
    return report


def run_story_stats(
    *,
    master_base: str | None = None,
    concurrency: int = 32,
    limit: int | None = None,
    sample_per_type: int | None = None,
    sample_seed: int = 42,
) -> dict[str, Any]:
    base = master_base
    if base is None:
        lock = SourcesLock.load(SOURCES_LOCK)
        base = lock.jp_master_base
    stats, _, population = asyncio.run(
        compute_story_stats(
            master_base=base,
            concurrency=concurrency,
            limit=limit,
            sample_per_type=sample_per_type,
            sample_seed=sample_seed,
        )
    )
    return stats_to_report(
        stats,
        population=population,
        sample_per_type=sample_per_type,
    )