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

MODES = ("intercept", "monitor", "probe", "attach-probe", "baseline", "font")


def _normalize_literal_escapes(text: str) -> str:
    """CN wordings may contain literal \\n instead of newline (see text_normalize.py)."""
    if "\\" not in text:
        return text
    return (
        text.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace("\\t", "\t")
    )


def load_json_string_map(path: Path) -> dict[str, str] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object in {path}")
    return {str(k): _normalize_literal_escapes(str(v)) for k, v in data.items()}


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


def _resolve_intercept_mode(cli: str, *, has_data: bool) -> str:
    """Map --ui-mode / --story-mode CLI to runtime 'cn' | 'prefix'."""
    if cli == "auto":
        return "cn" if has_data else "prefix"
    if cli in ("cn", "prefix"):
        return cli
    raise ValueError(f"unexpected mode: {cli!r}")


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
    ui_mode = _resolve_intercept_mode(args.ui_mode, has_data=load_ui_wordings() is not None)
    story_mode = _resolve_intercept_mode(args.story_mode, has_data=load_story_text() is not None)
    cfg: dict = {
        "STORY_MODE": story_mode,
        "UI_MODE": ui_mode,
        "FONT_INJECT": args.font_inject,
        "STORY_PATCH_ATTACH": story_mode == "cn",
        "STORY_SET_WORDS_FALLBACK": getattr(args, "story_fallback", False),
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


def resume_gadget_app(device: frida.core.Device) -> None:
    """Resume gadget-paused process after script load (on_load=wait)."""
    candidates: list[tuple[str, int]] = []
    try:
        front = device.get_frontmost_application()
        if front and front.pid:
            candidates.append((front.identifier, front.pid))
    except Exception:
        pass
    for app in device.enumerate_applications():
        if app.pid and app.identifier == PACKAGE:
            candidates.append((app.identifier, app.pid))
    for proc in device.enumerate_processes():
        if proc.pid and (proc.name == PACKAGE or "pjsekai" in proc.name):
            candidates.append((proc.name, proc.pid))
    seen: set[int] = set()
    for label, pid in candidates:
        if pid in seen:
            continue
        seen.add(pid)
        try:
            device.resume(pid)
            print(f"[*] resumed {label} pid={pid}", flush=True)
            return
        except Exception as exc:
            print(f"[*] resume {label} pid={pid}: {exc}", flush=True)
    print("[!] resume: no pid found — 若画面冻结请冷启动游戏后重连", flush=True)


def after_script_load(device: frida.core.Device, spawn_pid: int | None) -> None:
    if spawn_pid is not None:
        device.resume(spawn_pid)
    else:
        resume_gadget_app(device)


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
            off = p.get("offsets") or {}
            off_bits = ""
            if off:
                off_bits = (
                    f" off=SWT:0x{off.get('SetWordingText', 0):X}"
                    f" UWT:0x{off.get('UpdateWordingText', 0):X}"
                    f" ST:0x{off.get('SetText', 0):X}"
                )
            print(
                f"[*] ready storyMode={p.get('storyMode')!r} uiMode={p.get('uiMode')!r}"
                f"{patch_bits}{font_bits}{off_bits} "
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
        elif ev == "story_patch_diag":
            bits = [f"player={p.get('player')}", f"scene={p.get('scene')}"]
            if p.get("objName"):
                bits.append(f"name={p.get('objName')!r}")
            if p.get("scenarioIdPeek"):
                bits.append(f"id={p.get('scenarioIdPeek')!r}")
            if "snippetsLen" in p:
                bits.append(f"snippets={p.get('snippetsLen')}")
            if "talkLen" in p:
                bits.append(f"talk={p.get('talkLen')}")
            print(f"── story_patch_diag {' '.join(bits)}", flush=True)
        elif ev in ("hook", "il2cpp", "error"):
            print(json.dumps(p, ensure_ascii=False), flush=True)

    if not args.json:
        print("=" * 60, flush=True)
        if args.story_mode == "dual":
            print("剧情双字幕 — 上行中文（demo 词表）、下行原文；仅 Hook SetWordsInfo", flush=True)
        elif icfg.get("UI_MODE") == "cn" or icfg.get("STORY_MODE") == "cn":
            w = load_ui_wordings()
            p = load_ui_plain_text()
            s = load_story_text()
            parts_msg = []
            if w and icfg.get("UI_MODE") == "cn":
                parts_msg.append(f"UI {len(w)} keys")
            if p and icfg.get("UI_MODE") == "cn":
                parts_msg.append(f"plain {len(p)}")
            if s and icfg.get("STORY_MODE") == "cn":
                parts_msg.append(f"story {len(s)}")
            patch_note = (
                "AttachSceneData patch"
                if icfg.get("STORY_PATCH_ATTACH")
                else "SetWordsInfo 按日文明文"
            )
            mode_bits = f"uiMode={icfg.get('UI_MODE')!r} storyMode={icfg.get('STORY_MODE')!r}"
            data_bits = " + ".join(parts_msg) if parts_msg else "（无 cn 数据源或未强制 cn）"
            print(f"国服词表 — {data_bits}；{mode_bits}；剧情 {patch_note}", flush=True)
        else:
            print(
                f"前缀拦截 — uiMode={icfg.get('UI_MODE')!r} storyMode={icfg.get('STORY_MODE')!r} "
                f"prefix={icfg.get('PREFIX')!r}；屏幕应出现前缀，终端打印 intercept 事件",
                flush=True,
            )
        print("=" * 60, flush=True)

    device = get_device()
    session, spawn_pid = attach(device, args.attach)
    script = session.create_script(js)
    script.on("message", on_message)
    script.on("message", _frida_error_handler)
    script.load()
    after_script_load(device, spawn_pid)

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
    after_script_load(device, spawn_pid)

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
    after_script_load(device, spawn_pid)

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


def load_baseline_script() -> str:
    """Minimal bundle: offsets + runtime + baseline.js (no wordings JSON)."""
    parts = [
        (LIB / "offsets.js").read_text(encoding="utf-8"),
        (LIB / "runtime.js").read_text(encoding="utf-8"),
        (SCRIPTS / "baseline.js").read_text(encoding="utf-8"),
    ]
    return "\n\n".join(parts)


def fmt_baseline_hit(p: dict) -> str:
    parts = [f"── hit {p.get('id')} #{p.get('n')}"]
    if p.get("arg") is not None:
        parts.append(f"   arg: {p.get('arg')!r}")
    if p.get("name") or p.get("body"):
        parts.append(f"   name: {p.get('name')!r}")
        body = p.get("body") or ""
        if len(body) > 80:
            body = body[:80] + "…"
        parts.append(f"   body: {body!r}")
    return "\n".join(parts)


def run_baseline(args: argparse.Namespace) -> int:
    js = load_baseline_script()
    hits: list[dict] = []
    ticks: list[dict] = []
    attach_rows: list[dict] = []

    def on_message(message, _data):
        if message.get("type") != "send":
            return
        p = message["payload"]
        ev = p.get("event")
        if args.json:
            print(json.dumps(p, ensure_ascii=False), flush=True)
            return
        if ev == "baseline_hit":
            hits.append(p)
            print(fmt_baseline_hit(p), flush=True)
        elif ev == "baseline_tick":
            ticks.append(p)
            h = p.get("hits") or {}
            active = ", ".join(f"{k}={v}" for k, v in sorted(h.items()) if v) or "(none)"
            print(f"[tick] {active}", flush=True)
        elif ev == "baseline_ready":
            print(
                f"[*] baseline ready apiOk={p.get('apiOk')} base={p.get('base')} "
                f"candidates={p.get('candidates')}",
                flush=True,
            )
            print(f"    {p.get('hint')}", flush=True)
        elif ev == "baseline_attach":
            attach_rows.append(p)
            print(json.dumps(p, ensure_ascii=False), flush=True)
        elif ev in ("baseline_api", "il2cpp", "error"):
            print(json.dumps(p, ensure_ascii=False), flush=True)

    if not args.json:
        print("=" * 60, flush=True)
        print("baseline — il2cpp 字符串 API + 多候选 RVA 命中计数（无替换逻辑）", flush=True)
        print("=" * 60, flush=True)

    device = get_device()
    session, spawn_pid = attach(device, args.attach)
    script = session.create_script(js)
    script.on("message", on_message)
    script.on("message", _frida_error_handler)
    script.load()
    after_script_load(device, spawn_pid)

    print(f"[*] baseline {args.duration}s — 请操作 UI 按钮或剧情对话", flush=True)
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print("\n[*] interrupted", flush=True)
    finally:
        session.detach()

    final = ticks[-1]["hits"] if ticks else {}
    print("[+] baseline summary", flush=True)
    if not final:
        print("    无命中 — 检查是否操作 UI，或真实入口不在候选表", flush=True)
    else:
        for k, v in sorted(final.items(), key=lambda x: -x[1]):
            print(f"    {k}: {v}", flush=True)
    fail = [r for r in attach_rows if not r.get("ok")]
    if fail:
        print(f"    attach_fail: {len(fail)}", flush=True)
    return 0 if final else 1


def run_attach_probe(args: argparse.Namespace) -> int:
    js = load_script("attach_probe")
    phases: list[dict] = []

    def on_message(message, _data):
        if message.get("type") != "send":
            return
        p = message["payload"]
        if p.get("event") == "attach_probe":
            phases.append(p)
            print(json.dumps(p, ensure_ascii=False), flush=True)

    device = get_device()
    session, spawn_pid = attach(device, args.attach)
    script = session.create_script(js)
    script.on("message", on_message)
    script.on("message", _frida_error_handler)
    script.load()
    after_script_load(device, spawn_pid)

    deadline = time.time() + args.duration
    done = False
    while time.time() < deadline:
        for m in phases:
            if m.get("phase") == "get_impl_only":
                done = True
                break
            if m.get("reason") in ("timeout",):
                session.detach()
                return 1
        if done:
            break
        time.sleep(0.5)

    session.detach()
    if not done:
        print("[!] attach-probe timeout", flush=True)
        return 1

    singles = next((m for m in phases if m.get("phase") == "singles"), None)
    seq = next((m for m in phases if m.get("phase") == "intercept_order"), None)
    solo = next((m for m in phases if m.get("phase") == "get_impl_only"), None)

    print("[+] attach-probe summary", flush=True)
    if singles:
        for row in singles["rows"]:
            mark = "OK" if row.get("attach") == "ok" else "FAIL"
            err = f" — {row['error']}" if row.get("error") else ""
            print(f"    {row['name']}: {mark}{err}", flush=True)
    if seq and seq.get("result"):
        fail = seq["result"].get("failedAt")
        print(f"    intercept_order: {'FAIL at ' + fail if fail else 'ALL OK'}", flush=True)
    if solo and solo.get("result"):
        fail = solo["result"].get("failedAt")
        print(f"    get_impl_only: {'FAIL' if fail else 'OK'}", flush=True)

    get_impl = next((r for r in (singles or {}).get("rows", []) if r["name"] == "WordingManager_GetImpl"), None)
    if get_impl and get_impl.get("attach") != "ok":
        return 1
    if seq and seq.get("result", {}).get("failedAt"):
        return 1
    return 0


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
    after_script_load(device, spawn_pid)

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
    parser.add_argument("--prefix", default="[TEST] ", help="visible prefix when ui/story mode is prefix")
    parser.add_argument(
        "--ui-mode",
        choices=("auto", "cn", "prefix"),
        default="auto",
        help="UI intercept: auto=cn if wordings.json exists else prefix; force cn or prefix",
    )
    parser.add_argument(
        "--story-mode",
        choices=("auto", "cn", "prefix", "dual"),
        default="auto",
        help="story: auto=cn if text.json exists else prefix; dual=双字幕; force cn/prefix",
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
    parser.add_argument(
        "--story-fallback",
        action="store_true",
        help="cn story: also Hook SetWordsInfo jp→zh (when AttachSceneData patch misses lines)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mode in ("intercept", "monitor", "font", "attach-probe", "baseline") and not args.spawn:
        args.attach = True
    if args.mode == "probe" and not args.attach:
        args.attach = False

    if args.mode == "intercept":
        return run_intercept(args)
    if args.mode == "monitor":
        return run_monitor(args)
    if args.mode == "font":
        return run_font(args)
    if args.mode == "attach-probe":
        return run_attach_probe(args)
    if args.mode == "baseline":
        return run_baseline(args)
    return run_probe(args)


if __name__ == "__main__":
    sys.exit(main())