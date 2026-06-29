// Minimal il2cpp API smoke test + per-RVA hit counters (6.6.0 call-site discovery)
'use strict';

const CANDIDATES = [
    { id: 'GetImpl',          off: OFFSETS.WordingManager_GetImpl,              argKey: 0 },
    { id: 'Get_wrapper',      off: OFFSETS.WordingManager_Get_wrapper,          argKey: 0 },
    { id: 'Get_runtime',      off: OFFSETS.WordingManager_Get,                  argKey: 0 },
    { id: 'GetFormat_impl',   off: OFFSETS.WordingManager_GetFormat_impl,       argKey: 0 },
    { id: 'GetFormat_runtime', off: OFFSETS.WordingManager_GetFormat,           argKey: 0 },
    { id: 'SWT_impl',         off: OFFSETS.CustomTextMesh_SetWordingText_impl,  argKey: 1 },
    { id: 'SWT_runtime',      off: OFFSETS.CustomTextMesh_SetWordingText,       argKey: 1 },
    { id: 'UWT_impl',         off: OFFSETS.CustomTextMesh_UpdateWordingText_impl, argKey: null },
    { id: 'UWT_runtime',      off: OFFSETS.CustomTextMesh_UpdateWordingText,    argKey: null },
    { id: 'SetText_impl',     off: 0x4F27530,                            argKey: 1 },
    { id: 'SetText_dumper',   off: 0x4F2EB74,                            argKey: 1 },
    { id: 'SetText_slot',     off: OFFSETS.CustomTextMesh_SetText_slot, argKey: 1 },
    { id: 'TMP_set_text',     off: OFFSETS.TMP_Text_set_text,           argKey: 1 },
    { id: 'SetWordsInfo',     off: OFFSETS.TalkWindow_SetWordsInfo,     kind: 'story' },
];

const MAX_HIT_LOG = 40;
const stats = { hits: {}, attachFail: [] };

function smokeTestIl2Cpp() {
    const out = { ok: false, exports: {}, roundtrip: null, error: null };
    const names = ['il2cpp_string_new', 'il2cpp_string_length', 'il2cpp_string_chars'];
    try {
        for (let i = 0; i < names.length; i++) {
            out.exports[names[i]] = findExport(names[i]).toString();
        }
        bindIl2CppApi();
        const s = makeStr('baseline');
        out.roundtrip = readStr(s);
        out.ok = out.roundtrip === 'baseline';
    } catch (e) {
        out.error = String(e);
    }
    emit('baseline_api', out);
    return out.ok;
}

function bump(id) {
    if (!stats.hits[id]) stats.hits[id] = 0;
    stats.hits[id]++;
    return stats.hits[id];
}

function attachCandidate(row) {
    const mod = Process.findModuleByName(MODULE);
    const addr = mod.base.add(row.off);
    const meta = { id: row.id, off: row.off, addr: addr.toString() };
    try {
        if (row.kind === 'story') {
            Interceptor.attach(addr, {
                onEnter(args) {
                    const n = bump(row.id);
                    if (n > MAX_HIT_LOG) return;
                    emit('baseline_hit', {
                        id: row.id,
                        n: n,
                        name: readStr(args[2]),
                        body: readStr(args[3]),
                    });
                },
            });
        } else {
            Interceptor.attach(addr, {
                onEnter(args) {
                    const n = bump(row.id);
                    if (n > MAX_HIT_LOG) return;
                    const hit = { id: row.id, n: n };
                    if (row.argKey !== null) {
                        hit.arg = readStr(args[row.argKey]);
                    }
                    emit('baseline_hit', hit);
                },
            });
        }
        emit('baseline_attach', Object.assign({ ok: true }, meta));
    } catch (e) {
        const fail = Object.assign({ ok: false, error: String(e) }, meta);
        stats.attachFail.push(fail);
        emit('baseline_attach', fail);
    }
}

function install() {
    const apiOk = smokeTestIl2Cpp();
    const mod = Process.findModuleByName(MODULE);
    emit('baseline_ready', {
        apiOk: apiOk,
        base: mod.base.toString(),
        size: mod.size,
        candidates: CANDIDATES.length,
        hint: '操作 UI/剧情；baseline_hit 里增长的 id 即为真实入口',
    });
    for (let i = 0; i < CANDIDATES.length; i++) {
        attachCandidate(CANDIDATES[i]);
    }
    setInterval(function () {
        emit('baseline_tick', { hits: stats.hits, attachFail: stats.attachFail.length });
    }, 5000);
}

start(stats, install);