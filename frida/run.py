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

from device import PACKAGE, _adb, get_device

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
LIB = ROOT / "lib"
SCRIPTS = ROOT / "scripts"
UI_WORDINGS_PATH = REPO_ROOT / "i18n" / "ui" / "wordings.json"
UI_PLAIN_TEXT_PATH = REPO_ROOT / "i18n" / "ui" / "plain-text.json"
STORY_TEXT_PATH = REPO_ROOT / "i18n" / "story" / "text.json"
FONT_BUNDLE_LOCAL = REPO_ROOT / "i18n" / "font" / "source-han-fallback.bundle"
DEVICE_FONT_BUNDLE = f"/sdcard/Android/data/{PACKAGE}/files/i18n/font/source-han-fallback.bundle"
FONT_ASSET_NAME = "SourceHanSansSC-Regular SDF"
FONT_EXTRA_LIBS = ("il2cpp_unity.js", "font_inject.js")
STORY_PATCH_LIBS = ("story_patch.js",)

MODES = ("intercept", "monitor", "probe", "font")


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


def font_inject_cfg(*, font_mode: str = "replace") -> dict:
    return {
        "FONT_BUNDLE_PATH": DEVICE_FONT_BUNDLE,
        "FONT_ASSET_NAME": FONT_ASSET_NAME,
        "FONT_MODE": font_mode,
    }


def push_font_bundle() -> bool:
    if not FONT_BUNDLE_LOCAL.is_file():
        print(f"[!] font bundle missing: {FONT_BUNDLE_LOCAL}", flush=True)
        print("    bake TMP asset — see i18n-data/font/README.md", flush=True)
        return False
    remote_dir = f"/sdcard/Android/data/{PACKAGE}/files/i18n/font"
    _adb("shell", "mkdir", "-p", remote_dir)
    proc = _adb("push", str(FONT_BUNDLE_LOCAL), DEVICE_FONT_BUNDLE)
    if proc.returncode != 0:
        print(f"[!] adb push failed: {proc.stderr.strip()}", flush=True)
        return False
    print(f"[+] pushed font bundle → {DEVICE_FONT_BUNDLE}", flush=True)
    return True


def load_script(
    mode: str,
    cfg_override: dict | None = None,
    *,
    extra_libs: tuple[str, ...] | None = None,
) -> str:
    parts = [
        (LIB / "offsets.js").read_text(encoding="utf-8"),
        (LIB / "runtime.js").read_text(encoding="utf-8"),
    ]
    if cfg_override:
        parts.append(f"const CFG_OVERRIDE = {json.dumps(cfg_override, ensure_ascii=False)};\n")
    if extra_libs:
        for name in extra_libs:
            parts.append((LIB / name).read_text(encoding="utf-8"))
    wordings = load_ui_wordings()
    if wordings:
        parts.append(f"const UI_WORDINGS = {json.dumps(wordings, ensure_ascii=False)};\n")
    plain = load_ui_plain_text()
    if plain:
        parts.append(f"const UI_PLAIN_TEXT = {json.dumps(plain, ensure_ascii=False)};\n")
    story = load_story_text()
    if story:
        parts.append(f"const STORY_TEXT = {json.dumps(story, ensure_ascii=False)};\n")
    parts.append((SCRIPTS / f"{mode}.js").read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def intercept_cfg(args: argparse.Namespace) -> dict:
    if args.story_mode == "dual":
        cfg = {
            "STORY_MODE": "dual",
            "STORY_PATCH_ATTACH": True,
            "STORY_SET_WORDS_FALLBACK": True,
            "DUAL_STYLE": args.dual_style,
            "INTERCEPT": {"TMP": False, "STORY": True, "UI": False},
            "FONT_INJECT": args.font_inject,
        }
        if args.font_inject:
            cfg.update(font_inject_cfg(font_mode="dual"))
        return cfg
    ui_mode = "cn" if load_ui_wordings() else "prefix"
    story_mode = "cn" if load_story_text() else "prefix"
    cfg: dict = {
        "STORY_MODE": story_mode,
        "UI_MODE": ui_mode,
        "FONT_INJECT": args.font_inject,
        "STORY_PATCH_ATTACH": story_mode == "cn",
        "STORY_SET_WORDS_FALLBACK": False,
    }
    if ui_mode == "prefix" or story_mode == "prefix":
        cfg["PREFIX"] = args.prefix
    if args.font_inject:
        cfg.update(font_inject_cfg(font_mode="replace"))
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


def fmt_story_patch(p: dict) -> str:
    sid = p.get("scenarioId", "?")
    line = p.get("line", "?")
    body = p.get("jpBody") or ""
    zh = p.get("zhBody") or ""
    if len(body) > 80:
        body = body[:80] + "…"
    if len(zh) > 80:
        zh = zh[:80] + "…"
    return "\n".join([
        f"── story_patch {sid}:{line}",
        f"   JP: {body!r}",
        f"   ZH: {zh!r}",
    ])


def fmt_story_patch_summary(p: dict) -> str:
    return (
        f"── story_patch_summary {p.get('scenarioId')!r} "
        f"lines={p.get('lines')} patched={p.get('patched')} "
        f"backup={p.get('backedUp', 0)} mode={p.get('mode')!r}"
    )


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
    icfg = intercept_cfg(args)
    extra: list[str] = []
    if icfg.get("STORY_PATCH_ATTACH"):
        extra.extend(STORY_PATCH_LIBS)
    if args.font_inject:
        extra.extend(FONT_EXTRA_LIBS)
    extra_libs = tuple(extra) if extra else None
    if args.font_inject:
        push_font_bundle()
    js = load_script("intercept", cfg_override=icfg, extra_libs=extra_libs)
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
            font_bits = ""
            if p.get("fontInject"):
                font_bits = f" fontMode={p.get('fontMode')!r}"
            patch_bits = ""
            if p.get("storyPatchAttach"):
                patch_bits = " storyPatch=AttachSceneData"
            print(
                f"[*] ready storyMode={p.get('storyMode')!r} uiMode={p.get('uiMode')!r}"
                f"{patch_bits}{font_bits} "
                f"uiWordings={p.get('uiWordings')} uiPlainText={p.get('uiPlainText')} "
                f"storyText={p.get('storyText')} "
                f"demoKeys={p.get('demoKeys')}",
                flush=True,
            )
        elif ev == "font_inject":
            print(fmt_font_inject(p), flush=True)
        elif ev == "story_patch":
            print(fmt_story_patch(p), flush=True)
        elif ev == "story_patch_summary":
            print(fmt_story_patch_summary(p), flush=True)
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
                patch_note = "AttachSceneData patch" if s and icfg.get("STORY_PATCH_ATTACH") else "SetWordsInfo 按日文明文"
                print(f"国服词表 — {' + '.join(parts_msg)}；剧情 {patch_note}", flush=True)
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


def fmt_font(p: dict) -> str:
    hook = p.get("hook", "?")
    phase = p.get("phase", "?")
    lines = [f"── font [{phase}] {hook}"]
    if p.get("mgr"):
        lines.append(f"   mgr: {p['mgr']}")
    font = p.get("font")
    if font:
        lines.append(f"   font: {font.get('ptr')} name={font.get('name')!r} fallback={font.get('fallback')}")
    for key in ("before", "after"):
        block = p.get(key)
        if not block or not block.get("slots"):
            continue
        lines.append(f"   {key}:")
        for label, info in block["slots"].items():
            if not info:
                lines.append(f"      {label}: <null>")
                continue
            fb = info.get("fallback") or {}
            lines.append(
                f"      {label}: {info.get('ptr')} name={info.get('name')!r} "
                f"fallbackSize={fb.get('size', 0)}"
            )
    return "\n".join(lines)


def fmt_font_inject(p: dict) -> str:
    mark = "OK" if p.get("ok") else "FAIL"
    mode = p.get("mode", "?")
    lines = [f"── font_inject [{mark}] mode={mode}"]
    if p.get("skipped"):
        lines.append(f"   skipped: {p.get('reason')}")
    if p.get("skippedReplace"):
        lines.append("   replace: skipped (dual/load — SC loaded only)")
    if p.get("error"):
        lines.append(f"   error: {p['error']}")
    if p.get("reason") and not p.get("ok"):
        lines.append(f"   reason: {p['reason']}")
    if p.get("fallbackWarn"):
        lines.append("   warn: EB/DB demote to SC fallback partially failed")
    sc = p.get("scFont")
    if sc:
        fb = sc.get("fallback") or {}
        lines.append(
            f"   scFont: {sc.get('ptr')} name={sc.get('name')!r} "
            f"fallbackSize={fb.get('size', 0)}"
        )
    for label, row in (p.get("results") or {}).items():
        if not isinstance(row, dict):
            continue
        if row.get("replaced"):
            lines.append(
                f"   {label}: {row.get('originalName')!r} → {row.get('primaryName')!r} OK"
            )
        elif row.get("ok"):
            lines.append(f"   {label}: original={row.get('originalName')!r}")
        else:
            lines.append(f"   {label}: FAIL reason={row.get('reason')}")
    for row in p.get("fallbackDemote") or []:
        if not isinstance(row, dict):
            continue
        extra = ""
        if row.get("sizeAfter") is not None:
            extra = f" fb {row.get('sizeBefore')}→{row.get('sizeAfter')}"
        lines.append(
            f"   demote {row.get('name')!r}: {'OK' if row.get('ok') else row.get('reason')}{extra}"
        )
    after = p.get("after")
    if after and after.get("slots"):
        for label in ("baseA", "baseB"):
            info = after["slots"].get(label)
            if not info:
                continue
            fb = info.get("fallback") or {}
            lines.append(
                f"   after.{label}: name={info.get('name')!r} fallbackSize={fb.get('size', 0)}"
            )
    return "\n".join(lines)


def run_font(args: argparse.Namespace) -> int:
    cfg = {
        "INJECT": args.inject,
        **(font_inject_cfg(font_mode=args.font_mode) if args.inject else {}),
    }
    extra_libs = FONT_EXTRA_LIBS if args.inject else None
    if args.inject:
        push_font_bundle()
    js = load_script("font", cfg_override=cfg, extra_libs=extra_libs)
    events: list[dict] = []

    def on_message(message, _data):
        if message.get("type") != "send":
            return
        p = message["payload"]
        events.append(p)
        if args.json:
            print(json.dumps(p, ensure_ascii=False), flush=True)
        elif p.get("event") == "font":
            print(fmt_font(p), flush=True)
        elif p.get("event") == "font_inject":
            print(fmt_font_inject(p), flush=True)
        elif p.get("event") in ("ready", "stats", "hook", "il2cpp", "error"):
            print(json.dumps(p, ensure_ascii=False), flush=True)

    print("=" * 60, flush=True)
    if args.inject:
        print("思源主字体替换 — SetupBuiltinFontAsset onLeave", flush=True)
        print(f"mode: {args.font_mode}  bundle: {DEVICE_FONT_BUNDLE}", flush=True)
    else:
        print("字体探测 — SetupBuiltinFontAsset / ClearFallbackFontAsset", flush=True)
        print("冷启动或重进游戏以触发字体加载；leave 后看 fallbackSize", flush=True)
    print("=" * 60, flush=True)

    device = get_device()
    session, spawn_pid = attach(device, args.attach)
    script = session.create_script(js)
    script.on("message", on_message)
    script.on("message", _frida_error_handler)
    script.load()
    if spawn_pid is not None:
        device.resume(spawn_pid)

    print(f"[*] font probe {args.duration}s…", flush=True)
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print("\n[*] interrupted", flush=True)
    finally:
        session.detach()

    font_events = [e for e in events if e.get("event") == "font"]
    setup_leave = [e for e in font_events if e.get("hook") == "SetupBuiltinFontAsset" and e.get("phase") == "leave"]
    print(
        f"[*] done: {len(events)} events, font={len(font_events)}, setupLeave={len(setup_leave)}",
        flush=True,
    )
    return 0 if font_events or any(e.get("event") == "ready" for e in events) else 1


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
    parser.add_argument(
        "--inject",
        action="store_true",
        help="font mode: replace EB/DB with Source Han SC (requires bundle)",
    )
    parser.add_argument(
        "--font-mode",
        choices=("replace", "dual", "load"),
        default="replace",
        help="font --inject: replace=swap primary; dual/load=only load SC asset",
    )
    parser.add_argument(
        "--font-inject",
        action="store_true",
        help="intercept mode: also replace primary font (dual story → FONT_MODE=dual)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mode in ("intercept", "monitor", "font") and not args.spawn:
        args.attach = True
    if args.mode == "probe" and not args.attach:
        args.attach = False

    if args.mode == "intercept":
        return run_intercept(args)
    if args.mode == "monitor":
        return run_monitor(args)
    if args.mode == "font":
        return run_font(args)
    return run_probe(args)


if __name__ == "__main__":
    sys.exit(main())