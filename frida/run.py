#!/usr/bin/env python3
"""Unified Frida runner for PJSK gadget sessions.

Examples:
  uv run frida-intercept              # intercept demo (default 120s)
  uv run frida-monitor -- --duration 90
  uv run frida-probe
  uv run python frida/run.py intercept --prefix "[CN] "
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import frida

from device import PACKAGE, get_device

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
LIB = ROOT / "lib"
SCRIPTS = ROOT / "scripts"
UI_WORDINGS_PATH = REPO_ROOT / "i18n" / "ui" / "wordings.json"
UI_PLAIN_TEXT_PATH = REPO_ROOT / "i18n" / "ui" / "plain-text.json"
STORY_TEXT_PATH = REPO_ROOT / "i18n" / "story" / "text.json"

MODES = ("intercept", "monitor", "probe")


def load_json_string_map(path: Path) -> dict[str, str] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object in {path}")
    return {str(k): str(v) for k, v in data.items()}


def load_ui_wordings() -> dict[str, str] | None:
    return load_json_string_map(UI_WORDINGS_PATH)


def load_ui_plain_text() -> dict[str, str] | None:
    return load_json_string_map(UI_PLAIN_TEXT_PATH)


def load_story_text() -> dict[str, str] | None:
    return load_json_string_map(STORY_TEXT_PATH)


def load_script(mode: str, cfg_override: dict | None = None) -> str:
    parts = [
        (LIB / "offsets.js").read_text(encoding="utf-8"),
        (LIB / "runtime.js").read_text(encoding="utf-8"),
    ]
    wordings = load_ui_wordings()
    if wordings:
        parts.append(f"const UI_WORDINGS = {json.dumps(wordings, ensure_ascii=False)};\n")
    plain = load_ui_plain_text()
    if plain:
        parts.append(f"const UI_PLAIN_TEXT = {json.dumps(plain, ensure_ascii=False)};\n")
    story = load_story_text()
    if story:
        parts.append(f"const STORY_TEXT = {json.dumps(story, ensure_ascii=False)};\n")
    if cfg_override:
        parts.append(f"const CFG_OVERRIDE = {json.dumps(cfg_override, ensure_ascii=False)};\n")
    parts.append((SCRIPTS / f"{mode}.js").read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def intercept_cfg(args: argparse.Namespace) -> dict:
    if args.story_mode == "dual":
        return {
            "STORY_MODE": "dual",
            "DUAL_STYLE": args.dual_style,
            "INTERCEPT": {"TMP": False, "STORY": True, "UI": False},
        }
    ui_mode = "cn" if load_ui_wordings() else "prefix"
    story_mode = "cn" if load_story_text() else "prefix"
    cfg: dict = {"STORY_MODE": story_mode, "UI_MODE": ui_mode}
    if ui_mode == "prefix" or story_mode == "prefix":
        cfg["PREFIX"] = args.prefix
    return cfg


def attach(device: frida.core.Device, use_attach: bool) -> tuple[frida.core.Session, int | None]:
    """Return (session, spawn_pid). spawn_pid is set only when the process was spawned paused."""
    if not use_attach:
        pid = device.spawn([PACKAGE])
        session = device.attach(pid)
        print(f"[*] spawned {PACKAGE} pid={pid}", flush=True)
        return session, pid

    for target in ("Gadget", PACKAGE):
        try:
            session = device.attach(target)
            print(f"[*] attached: {target}", flush=True)
            return session, None
        except Exception as exc:
            print(f"[*] attach {target}: {exc}", flush=True)

    apps = [a for a in device.enumerate_applications() if a.identifier == PACKAGE and a.pid]
    if apps:
        session = device.attach(apps[0].pid)
        print(f"[*] attached pid={apps[0].pid}", flush=True)
        return session, None

    raise RuntimeError("cannot attach — launch game on phone first (gadget wait)")


def fmt_intercept(p: dict) -> str:
    hook = p.get("hook", "?")
    orig = p.get("original")
    repl = p.get("replaced")
    ok = p.get("ok")
    extra = p.get("extra", "")
    mark = "OK" if ok else "FAIL"
    return "\n".join([
        f"── intercept [{mark}] {hook} {extra}".rstrip(),
        f"   原文: {orig!r}" if orig is not None else "   原文: <null>",
        f"   替换: {repl!r}" if repl is not None else "   替换: <null>",
    ])


def fmt_capture(p: dict) -> str:
    tag = p.get("tag", "?")
    lines = [f"── capture [{tag}]"]
    for key in ("key", "name", "text", "replaced", "cid", "note", "extra"):
        if key in p and p[key] is not None:
            val = p[key]
            if isinstance(val, str) and len(val) > 100:
                val = val[:100] + "…"
            lines.append(f"   {key}: {val!r}" if isinstance(val, str) else f"   {key}: {val}")
    return "\n".join(lines)


def run_intercept(args: argparse.Namespace) -> int:
    js = load_script("intercept", cfg_override=intercept_cfg(args))
    intercepts: list[dict] = []
    captures: list[dict] = []
    stats: list[dict] = []

    def on_message(message, _data):
        if message.get("type") != "send":
            return
        p = message["payload"]
        ev = p.get("event")
        if args.json:
            print(json.dumps(p, ensure_ascii=False), flush=True)
            return
        if ev == "intercept":
            intercepts.append(p)
            print(fmt_intercept(p), flush=True)
        elif ev == "capture":
            captures.append(p)
            print(fmt_capture(p), flush=True)
        elif ev == "stats":
            stats.append(p)
            print(f"[stats] {p.get('stats')}", flush=True)
        elif ev == "ready":
            print(
                f"[*] ready storyMode={p.get('storyMode')!r} uiMode={p.get('uiMode')!r} "
                f"uiWordings={p.get('uiWordings')} uiPlainText={p.get('uiPlainText')} "
                f"storyText={p.get('storyText')} "
                f"demoKeys={p.get('demoKeys')}",
                flush=True,
            )
        elif ev in ("hook", "il2cpp", "error"):
            print(json.dumps(p, ensure_ascii=False), flush=True)

    if not args.json:
        print("=" * 60, flush=True)
        if args.story_mode == "dual":
            print("剧情双字幕 — 上行中文（demo 词表）、下行原文；仅 Hook SetWordsInfo", flush=True)
        else:
            w = load_ui_wordings()
            p = load_ui_plain_text()
            s = load_story_text()
            if w or s:
                parts_msg = []
                if w:
                    parts_msg.append(f"UI {len(w)} keys")
                if p:
                    parts_msg.append(f"plain {len(p)}")
                if s:
                    parts_msg.append(f"story {len(s)}")
                print(f"国服词表 — {' + '.join(parts_msg)}；SetWordsInfo 按日文明文", flush=True)
            else:
                print("拦截演示 — 屏幕应出现前缀，终端同步打印（未找到 i18n/ui/wordings.json）", flush=True)
        print("=" * 60, flush=True)

    device = get_device()
    session, spawn_pid = attach(device, args.attach)
    script = session.create_script(js)
    script.on("message", on_message)
    script.on("message", _frida_error_handler)
    script.load()
    if spawn_pid is not None:
        device.resume(spawn_pid)

    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print("\n[*] interrupted", flush=True)
    finally:
        session.detach()

    ok = [x for x in intercepts if x.get("ok")]
    with_text = [x for x in captures if x.get("text") or x.get("key") or x.get("name")]
    print(f"\n[*] intercept: {len(intercepts)} ({len(ok)} ok), capture: {len(captures)} ({len(with_text)} with text)", flush=True)
    if stats:
        print(f"[*] final stats: {stats[-1].get('stats')}", flush=True)
    return 0 if ok or with_text else 1


def run_monitor(args: argparse.Namespace) -> int:
    js = load_script("monitor")
    events: list[dict] = []

    def on_message(message, _data):
        if message.get("type") != "send":
            return
        p = message["payload"]
        events.append(p)
        if args.json:
            print(json.dumps(p, ensure_ascii=False), flush=True)
        elif p.get("event") == "text":
            print(f"[{p.get('tag')}] {p.get('text')!r} {p.get('extra', '')}", flush=True)
        elif p.get("event") in ("ready", "stats", "hook", "il2cpp", "error"):
            print(json.dumps(p, ensure_ascii=False), flush=True)

    device = get_device()
    session, spawn_pid = attach(device, args.attach)
    script = session.create_script(js)
    script.on("message", on_message)
    script.on("message", _frida_error_handler)
    script.load()
    if spawn_pid is not None:
        device.resume(spawn_pid)

    print(f"[*] monitoring {args.duration}s…", flush=True)
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        pass
    finally:
        session.detach()

    text_events = [e for e in events if e.get("event") == "text"]
    print(f"[*] done: {len(events)} events, {len(text_events)} text samples", flush=True)
    return 0 if events else 1


def run_probe(args: argparse.Namespace) -> int:
    js = load_script("probe")
    results: list[dict] = []

    def on_message(message, _data):
        if message.get("type") != "send":
            return
        p = message["payload"]
        if p.get("event") == "probe":
            results.append(p)
            print(json.dumps(p, ensure_ascii=False), flush=True)

    device = get_device()
    session, spawn_pid = attach(device, not args.attach)
    script = session.create_script(js)
    script.on("message", on_message)
    script.on("message", _frida_error_handler)
    script.load()
    if spawn_pid is not None:
        device.resume(spawn_pid)

    deadline = time.time() + args.duration
    ok = False
    while time.time() < deadline:
        for m in results:
            if m.get("ok") and "rows" in m:
                ok = True
                break
            if m.get("reason") in ("timeout",):
                session.detach()
                return 1
        if ok:
            break
        time.sleep(0.5)

    session.detach()
    if not ok:
        print("[!] probe failed", flush=True)
        return 1

    result = next(m for m in results if m.get("ok") and "rows" in m)
    print(f"[+] base={result['base']} size={result['size']}", flush=True)
    for row in result["rows"]:
        print(f"    {row['name']}: {row['addr']} prot={row.get('protection', '?')}", flush=True)
    return 0


def _frida_error_handler(message, _data):
    if message.get("type") == "error":
        print("[frida-error]", message.get("stack") or message.get("description"), flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PJSK Frida runner")
    parser.add_argument("mode", choices=MODES, nargs="?", default="intercept")
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--attach", action="store_true", help="attach gadget/running app (default for intercept/monitor)")
    parser.add_argument("--spawn", action="store_true", help="spawn package (probe default)")
    parser.add_argument("--prefix", default="[TEST] ", help="prefix when --story-mode=prefix")
    parser.add_argument(
        "--story-mode",
        choices=("prefix", "dual"),
        default="prefix",
        help="story intercept style: prefix or dual-subtitle",
    )
    parser.add_argument(
        "--dual-style",
        choices=("plain", "rich"),
        default="plain",
        help="dual mode: plain newlines or TMP rich text for jp line",
    )
    parser.add_argument("--json", action="store_true", help="raw JSON output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mode in ("intercept", "monitor") and not args.spawn:
        args.attach = True
    if args.mode == "probe" and not args.attach:
        args.attach = False

    if args.mode == "intercept":
        return run_intercept(args)
    if args.mode == "monitor":
        return run_monitor(args)
    return run_probe(args)


if __name__ == "__main__":
    sys.exit(main())