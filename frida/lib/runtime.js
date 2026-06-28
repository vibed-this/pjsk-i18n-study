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