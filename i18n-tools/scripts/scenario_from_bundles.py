"""Extract ScenarioSceneData MonoBehaviour JSON from decrypted PJSK AssetBundles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import orjson
import UnityPy

UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.52f1"


def _has_scenario(tree: dict) -> bool:
    if not isinstance(tree, dict):
        return False
    snippets = tree.get("Snippets") or tree.get("snippets")
    talk = tree.get("TalkData") or tree.get("talkData")
    sid = tree.get("ScenarioId") or tree.get("scenarioId")
    return bool(sid and snippets is not None and talk is not None)


def _scenario_id(tree: dict) -> str:
    sid = tree.get("ScenarioId") or tree.get("scenarioId")
    return str(sid)


def extract_tree(bundle_path: Path) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    try:
        env = UnityPy.load(str(bundle_path))
    except Exception:
        return out
    if not env:
        return out
    for _path, obj in env.container.items():
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if _has_scenario(tree):
            out.append((_scenario_id(tree), tree))
    return out


def extract_dir(
    bundle_root: Path,
    out_dir: Path,
    *,
    overwrite: bool = False,
) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = {"bundles": 0, "scenarios": 0, "skipped": 0, "failed": 0}
    for bundle_path in sorted(bundle_root.rglob("*")):
        if not bundle_path.is_file():
            continue
        stats["bundles"] += 1
        pairs = extract_tree(bundle_path)
        if not pairs:
            stats["failed"] += 1
            continue
        for scenario_id, tree in pairs:
            dest = out_dir / f"{scenario_id}.json"
            if dest.exists() and not overwrite:
                stats["skipped"] += 1
                continue
            dest.write_bytes(orjson.dumps(tree, option=orjson.OPT_INDENT_2))
            stats["scenarios"] += 1
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle_root", type=Path, help="decrypted bundle tree")
    parser.add_argument("out_dir", type=Path, help="output scenario json dir")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not args.bundle_root.is_dir():
        print(f"[!] not a directory: {args.bundle_root}", file=sys.stderr)
        return 1
    stats = extract_dir(args.bundle_root, args.out_dir, overwrite=args.overwrite)
    print(
        f"[+] bundles={stats['bundles']} scenarios_written={stats['scenarios']} "
        f"skipped={stats['skipped']} no_scenario={stats['failed']} → {args.out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())