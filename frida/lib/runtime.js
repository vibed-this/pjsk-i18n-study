// Shared IL2CPP + Frida helpers (prepended by run.py)
'use strict';

const _api = {};

function emit(event, data) {
    send(Object.assign({ event: event, ts: Date.now() }, data));
}

function findExport(name) {
    const mod = Process.findModuleByName(MODULE);
    if (!mod) throw new Error('module not found: ' + MODULE);
    const hit = mod.enumerateExports().filter(function (e) { return e.name === name; })[0];
    if (!hit) throw new Error('export missing: ' + name);
    return hit.address;
}

function bindIl2CppApi() {
    _api.length = new NativeFunction(findExport('il2cpp_string_length'), 'int', ['pointer']);
    _api.chars   = new NativeFunction(findExport('il2cpp_string_chars'), 'pointer', ['pointer']);
    _api.newStr  = new NativeFunction(findExport('il2cpp_string_new'), 'pointer', ['pointer']);
}

function readStr(p) {
    if (!p || p.isNull()) return null;
    try {
        const len = _api.length(p);
        if (len < 0 || len > 65536) return null;
        const ch = _api.chars(p);
        if (!ch || ch.isNull()) return null;
        return ch.readUtf16String(len);
    } catch (_) {
        return null;
    }
}

function makeStr(text) {
    if (!text) return null;
    const buf = Memory.allocUtf8String(text);
    return _api.newStr(buf);
}

function hookAt(name, offset, callbacks) {
    const addr = Process.findModuleByName(MODULE).base.add(offset);
    emit('hook', { name: name, addr: addr.toString() });
    Interceptor.attach(addr, callbacks);
}

function readPtr(base, offset) {
    if (!base || base.isNull()) return null;
    try {
        const p = base.add(offset).readPointer();
        return p && !p.isNull() ? p : null;
    } catch (_) {
        return null;
    }
}

function readUnityObjectName(obj) {
    if (!obj || obj.isNull()) return null;
    const candidates = [0x60, 0x58, 0x68, 0x50, 0x48];
    for (let i = 0; i < candidates.length; i++) {
        const namePtr = readPtr(obj, candidates[i]);
        const s = readStr(namePtr);
        if (s && s.length > 0 && s.length < 160) return s;
    }
    return null;
}

function readIl2CppListSize(list) {
    if (!list || list.isNull()) return 0;
    try {
        const n = list.add(IL2CPP_LIST_SIZE).readS32();
        return n >= 0 && n < 10000 ? n : 0;
    } catch (_) {
        return 0;
    }
}

function readIl2CppArrayLength(arr) {
    if (!arr || arr.isNull()) return 0;
    try {
        const n = arr.add(IL2CPP_ARRAY_MAX_LENGTH).readS32();
        return n >= 0 && n < 20000 ? n : 0;
    } catch (_) {
        return 0;
    }
}

function readIl2CppArrayElement(arr, index) {
    if (!arr || arr.isNull() || index < 0) return null;
    try {
        const p = arr.add(IL2CPP_ARRAY_VECTOR + index * Process.pointerSize).readPointer();
        return p && !p.isNull() ? p : null;
    } catch (_) {
        return null;
    }
}

// talkLineIdx：与 story-build extract_talk_lines 一致（Snippets 按 Index 排序后 Talk 行序）
function computeTalkLineIdx(player, snippet) {
    if (!player || player.isNull() || !snippet || snippet.isNull()) return -1;
    const scene = readPtr(player, SCENARIO_PLAYER_SCENE);
    if (!scene) return -1;
    const arr = readPtr(scene, SCENARIO_SCENE_SNIPPETS);
    const len = readIl2CppArrayLength(arr);
    if (!len) return -1;
    let curIndex = -1;
    try {
        curIndex = snippet.add(SCENARIO_SNIPPET_INDEX).readS32();
    } catch (_) {
        return -1;
    }
    const rows = [];
    for (let i = 0; i < len; i++) {
        const sn = readIl2CppArrayElement(arr, i);
        if (!sn) continue;
        try {
            rows.push({
                index: sn.add(SCENARIO_SNIPPET_INDEX).readS32(),
                action: sn.add(SCENARIO_SNIPPET_ACTION).readS32(),
            });
        } catch (_) {}
    }
    rows.sort(function (a, b) { return a.index - b.index; });
    let talkLine = -1;
    for (let j = 0; j < rows.length; j++) {
        if (rows[j].action !== SCENARIO_ACTION_TALK) continue;
        talkLine++;
        if (rows[j].index === curIndex) return talkLine;
    }
    return -1;
}

function describeFallbackList(fontAsset) {
    const list = readPtr(fontAsset, TMP_FONT_FALLBACK_LIST);
    if (!list) return { list: null, size: 0 };
    return { list: list.toString(), size: readIl2CppListSize(list) };
}

function describeTmpFontAsset(ptr) {
    if (!ptr || ptr.isNull()) return null;
    const fb = describeFallbackList(ptr);
    return {
        ptr: ptr.toString(),
        name: readUnityObjectName(ptr),
        fallback: fb,
    };
}

function describeFontManager(mgr) {
    if (!mgr || mgr.isNull()) return null;
    const slots = {};
    const fields = typeof FONT_MANAGER_FIELDS !== 'undefined' ? FONT_MANAGER_FIELDS : [];
    for (let i = 0; i < fields.length; i++) {
        const f = fields[i];
        const asset = readPtr(mgr, f.off);
        slots[f.label] = describeTmpFontAsset(asset);
    }
    return { mgr: mgr.toString(), slots: slots };
}

function waitForIl2Cpp(timeoutMs) {
    const deadline = Date.now() + (timeoutMs || 180000);
    return new Promise((resolve, reject) => {
        const tick = () => {
            const mod = Process.findModuleByName(MODULE);
            if (mod) return resolve(mod);
            if (Date.now() > deadline) return reject(new Error('timeout: ' + MODULE));
            setTimeout(tick, 300);
        };
        tick();
    });
}

function start(stats, installFn) {
    setInterval(() => emit('stats', { stats: stats }), 10000);
    waitForIl2Cpp().then((mod) => {
        try {
            bindIl2CppApi();
            emit('il2cpp', { base: mod.base.toString(), size: mod.size });
            installFn();
        } catch (e) {
            emit('error', { message: String(e), stack: e.stack || '' });
        }
    }).catch((e) => emit('error', { message: String(e), stack: e.stack || '' }));
}