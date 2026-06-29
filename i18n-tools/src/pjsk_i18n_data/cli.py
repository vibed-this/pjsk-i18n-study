from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .build import build_ui_pack
from .fetch import fetch_all
from .font_chars import build_font_charset_files
from .story import build_story_pack, fetch_scenario_inventory
from .story_stats import collect_story_targets, run_story_stats


def cmd_fetch(args: argparse.Namespace) -> int:
    cn, jp, master = fetch_all(refresh=args.refresh)
    print(f"[+] cn wordings: {cn.count} entries → {cn.path}")
    print(f"[+] jp wordings: {jp.count} entries → {jp.path}")
    for row in master:
        print(f"[+] {row.label}: {row.count} entries → {row.path}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    result = build_ui_pack(fetch=not args.no_fetch, refresh=args.refresh)
    print(f"[+] ui wordings: {result.count} keys → {result.wordings_path}")
    print(f"[+] plain text: {result.plain_count} pairs → {result.plain_text_path}")
    print(f"[+] manifest → {result.manifest_path}")
    print(f"[+] gap report → {result.report_path} (jp_only={len(result.jp_only)})")
    if result.override_count:
        print(f"[+] overrides applied: {result.override_count}")
    if args.with_story:
        out, gap = build_story_pack(
            demo=args.story_demo,
            fetch_inventory=not args.story_demo,
            write_per_scenario=args.per_scenario,
        )
        stats = gap.get("stats", {})
        print(f"[+] story text: {gap.get('entry_count', 0)} entries → {out}")
        print(
            f"[+] aligned {stats.get('scenarios_aligned', 0)}/{stats.get('scenarios_processed', 0)} "
            f"scenarios"
        )
    return 0


def cmd_font_chars(args: argparse.Namespace) -> int:
    charset_path, meta_path, meta = build_font_charset_files()
    print(f"[+] font charset: {meta['char_count']} chars → {charset_path}")
    print(f"[+] meta → {meta_path}")
    return 0


def cmd_story_inventory(args: argparse.Namespace) -> int:
    inv = fetch_scenario_inventory()
    counts = inv["counts"]
    print(f"[+] scenario inventory → common={counts['common']} jp_only={counts['jp_only']}")
    return 0


def cmd_story_stats(args: argparse.Namespace) -> int:
    if args.list_only:
        targets = collect_story_targets()
        print(f"[+] story targets: {len(targets)} scenario URLs")
        by_type: dict[str, int] = {}
        for t in targets:
            by_type[t.story_type] = by_type.get(t.story_type, 0) + 1
        for key in sorted(by_type):
            print(f"    {key}: {by_type[key]}")
        return 0

    report = run_story_stats(
        concurrency=args.concurrency,
        limit=args.limit,
        sample_per_type=args.sample_per_type,
        sample_seed=args.sample_seed,
    )
    print(f"[+] scenarios: {report['scenarios_ok']}/{report['scenarios_total']} ok")
    if report["scenarios_failed"]:
        print(f"[!] failed: {report['scenarios_failed']}")
    if "sample" in report:
        pop = report["sample"]["population_total"]
        print(
            f"[+] sample mode: {args.sample_per_type}/type "
            f"(population {pop} scenarios)"
        )
    print(f"[+] talk lines: {report['talk_lines']}")
    print(f"[+] fullscreen lines: {report['fullscreen_lines']}")
    print(f"[+] chars body: {report['chars_body']:,}")
    print(f"[+] chars name: {report['chars_name']:,}")
    print(f"[+] chars fullscreen: {report['chars_fullscreen']:,}")
    print(f"[+] chars dialogue (body+name): {report['chars_dialogue']:,}")
    print(f"[+] chars total (dialogue+fullscreen): {report['chars_total']:,}")
    print(f"[+] unique body strings: {report['unique_body_strings']:,}")
    print(f"[+] unique name strings: {report['unique_name_strings']:,}")
    print("[+] by type (sample):")
    for key in sorted(report["by_type"]):
        row = report["by_type"][key]
        chars = row["chars_body"] + row["chars_name"] + row["chars_fullscreen"]
        print(
            f"    {key}: ok={row['scenarios_ok']} lines={row['talk_lines']} chars={chars:,}"
        )
    if "estimate" in report:
        est = report["estimate"]["total"]
        print("[+] extrapolated estimate (JP full corpus):")
        print(f"    scenarios: {est['scenarios']:,}")
        print(f"    talk lines: {est['talk_lines']:,}")
        print(f"    chars body: {est['chars_body']:,}")
        print(f"    chars name: {est['chars_name']:,}")
        print(f"    chars dialogue: {est['chars_dialogue']:,}")
        print(f"    chars total: {est['chars_total']:,}")
        print("[+] estimate by type:")
        for key in sorted(report["estimate"]["by_type"]):
            row = report["estimate"]["by_type"][key]
            print(
                f"    {key}: pop={row['population']} "
                f"~{row['est_chars_total']:,} chars "
                f"({row['est_talk_lines']:,} lines)"
            )
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[+] report → {args.json_out}")
    return 0


def cmd_story_build(args: argparse.Namespace) -> int:
    if not args.demo and not args.no_inventory:
        fetch_scenario_inventory()
    out, gap = build_story_pack(
        demo=args.demo,
        fetch_inventory=not args.no_inventory and not args.demo,
        write_per_scenario=args.per_scenario,
    )
    stats = gap.get("stats", {})
    print(f"[+] story text: {gap.get('entry_count', 0)} entries → {out}")
    print(
        f"[+] aligned {stats.get('scenarios_aligned', 0)}/{stats.get('scenarios_processed', 0)} "
        f"scenarios (body={stats.get('body_pairs', 0)} name={stats.get('name_pairs', 0)})"
    )
    if args.demo:
        print("[+] demo mode: built from i18n-data/fixtures/scenario/")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pjsk-i18n",
        description="Fetch CN master data and build UI/story translation packs for JP client mod",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="download CN/JP wordings.json into i18n-data/cache")
    p_fetch.add_argument("--refresh", action="store_true", help="re-download even if cache exists")
    p_fetch.set_defaults(func=cmd_fetch)

    p_build = sub.add_parser("build", help="merge CN + overrides → i18n/ui/wordings.json")
    p_build.add_argument("--no-fetch", action="store_true", help="use existing cache only")
    p_build.add_argument("--refresh", action="store_true", help="re-download before build")
    p_build.add_argument(
        "--with-story",
        action="store_true",
        help="also run story-build after UI pack",
    )
    p_build.add_argument(
        "--story-demo",
        action="store_true",
        help="with --with-story: use fixtures instead of cache/scenario",
    )
    p_build.add_argument(
        "--per-scenario",
        action="store_true",
        help="with --with-story: write i18n/story/by-scenario/<id>.json",
    )
    p_build.set_defaults(func=cmd_build)

    p_font = sub.add_parser(
        "font-chars",
        help="collect translation chars → i18n/font/charset.txt for Source Han subset",
    )
    p_font.set_defaults(func=cmd_font_chars)

    p_inv = sub.add_parser(
        "story-inventory",
        help="fetch JP/CN scenarioId lists from master diff (no AssetBundle required)",
    )
    p_inv.set_defaults(func=cmd_story_inventory)

    p_story = sub.add_parser(
        "story-build",
        help="align JP/CN scenario JSON → i18n/story/text.json",
    )
    p_story.add_argument(
        "--demo",
        action="store_true",
        help="use bundled fixtures (Frida E2E sample lines)",
    )
    p_story.add_argument(
        "--no-inventory",
        action="store_true",
        help="skip refreshing scenario-inventory.json",
    )
    p_story.add_argument(
        "--per-scenario",
        action="store_true",
        help="also write i18n/story/by-scenario/<id>.json",
    )
    p_story.set_defaults(func=cmd_story_build)

    p_stats = sub.add_parser(
        "story-stats",
        help="count JP story dialogue chars from sekai.best scenario assets",
    )
    p_stats.add_argument("--list-only", action="store_true", help="only list scenario URL counts")
    p_stats.add_argument("--limit", type=int, default=None, help="process first N scenarios only")
    p_stats.add_argument(
        "--sample-per-type",
        type=int,
        default=None,
        help="stratified random sample: N scenarios per story type, then extrapolate",
    )
    p_stats.add_argument("--sample-seed", type=int, default=42, help="RNG seed for --sample-per-type")
    p_stats.add_argument("--concurrency", type=int, default=32, help="parallel HTTP fetches")
    p_stats.add_argument("--json-out", default=None, help="write full JSON report to path")
    p_stats.set_defaults(func=cmd_story_stats)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())