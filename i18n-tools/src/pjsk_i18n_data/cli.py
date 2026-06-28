from __future__ import annotations

import argparse
import sys

from .build import build_ui_pack
from .fetch import fetch_wordings


def cmd_fetch(args: argparse.Namespace) -> int:
    cn, jp = fetch_wordings(refresh=args.refresh)
    print(f"[+] cn: {cn.count} entries → {cn.path}")
    print(f"[+] jp: {jp.count} entries → {jp.path}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    result = build_ui_pack(fetch=not args.no_fetch, refresh=args.refresh)
    print(f"[+] ui wordings: {result.count} keys → {result.wordings_path}")
    print(f"[+] manifest → {result.manifest_path}")
    print(f"[+] gap report → {result.report_path} (jp_only={len(result.jp_only)})")
    if result.override_count:
        print(f"[+] overrides applied: {result.override_count}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pjsk-i18n",
        description="Fetch CN master wordings and build UI translation pack for JP client mod",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="download CN/JP wordings.json into i18n-data/cache")
    p_fetch.add_argument("--refresh", action="store_true", help="re-download even if cache exists")
    p_fetch.set_defaults(func=cmd_fetch)

    p_build = sub.add_parser("build", help="merge CN + overrides → i18n/ui/wordings.json")
    p_build.add_argument("--no-fetch", action="store_true", help="use existing cache only")
    p_build.add_argument("--refresh", action="store_true", help="re-download before build")
    p_build.set_defaults(func=cmd_build)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())