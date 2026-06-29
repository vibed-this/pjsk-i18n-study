// Per-offset Interceptor.attach sanity check (probe only checks r-x mapping)
'use strict';

const TARGETS = [
    'WordingManager_GetImpl',
    'WordingManager_Get',
    'WordingManager_GetFormat',
    'CustomTextMesh_SetText',
    'ScenarioPlayer_AttachSceneData',
    'TMP_Text_set_text',
];

function hexBytes(addr, n) {
    const out = [];
    for (let i = 0; i < n; i++) {
        out.push(('0' + addr.add(i).readU8().toString(16)).slice(-2));
    }
    return out.join(' ');
}

function rangeInfo(addr) {
    try {
        const r = Process.findRangeByAddress(addr);
        if (!r) return { protection: 'unmapped' };
        return {
            protection: r.protection,
            file: r.file ? r.file.path : null,
            base: r.base.toString(),
            size: r.size,
        };
    } catch (e) {
        return { protection: 'error', error: String(e) };
    }
}

function tryAttach(name, offset, callbacks) {
    const mod = Process.findModuleByName(MODULE);
    const addr = mod.base.add(offset);
    const row = {
        name: name,
        offset: offset,
        addr: addr.toString(),
        range: rangeInfo(addr),
        bytes: hexBytes(addr, 16),
        callbacks: callbacks ? Object.keys(callbacks).join('+') : 'onEnter',
    };
    const cbs = callbacks || { onEnter() {} };
    try {
        const hook = Interceptor.attach(addr, cbs);
        row.attach = 'ok';
        hook.detach();
        row.detach = 'ok';
        row.bytesAfter = hexBytes(addr, 16);
    } catch (e) {
        row.attach = 'fail';
        row.error = String(e);
    }
    return row;
}

function tryAttachSequence(names) {
    const mod = Process.findModuleByName(MODULE);
    const hooks = [];
    const steps = [];
    for (let i = 0; i < names.length; i++) {
        const name = names[i];
        const offset = OFFSETS[name];
        const addr = mod.base.add(offset);
        const step = { step: i + 1, name: name, addr: addr.toString() };
        try {
            hooks.push(Interceptor.attach(addr, { onEnter() {} }));
            step.attach = 'ok';
        } catch (e) {
            step.attach = 'fail';
            step.error = String(e);
            steps.push(step);
            for (let j = 0; j < hooks.length; j++) {
                try { hooks[j].detach(); } catch (_) {}
            }
            return { sequence: names.join(' -> '), steps: steps, failedAt: name };
        }
        steps.push(step);
    }
    for (let j = 0; j < hooks.length; j++) {
        try { hooks[j].detach(); } catch (_) {}
    }
    return { sequence: names.join(' -> '), steps: steps, failedAt: null };
}

function run() {
    const mod = Process.findModuleByName(MODULE);
    if (!mod) {
        emit('attach_probe', { ok: false, reason: 'not loaded' });
        return;
    }

    emit('attach_probe', {
        ok: true,
        phase: 'meta',
        base: mod.base.toString(),
        size: mod.size,
        frida: Frida.version,
        platform: Process.platform,
        arch: Process.arch,
    });

    const singles = TARGETS.map(function (name) {
        return tryAttach(name, OFFSETS[name]);
    });
    emit('attach_probe', { ok: true, phase: 'singles', rows: singles });

    const getImplLeave = tryAttach('WordingManager_GetImpl', OFFSETS.WordingManager_GetImpl, {
        onEnter(args) { this.key = args[0]; },
        onLeave(retval) { /* read only */ retval.toString(); },
    });
    emit('attach_probe', { ok: true, phase: 'get_impl_onleave', row: getImplLeave });

    const getImplReplace = tryAttach('WordingManager_GetImpl', OFFSETS.WordingManager_GetImpl, {
        onEnter(args) { this.key = args[0]; },
        onLeave(retval) {
            try { retval.replace(ptr(0)); } catch (_) {}
        },
    });
    emit('attach_probe', { ok: true, phase: 'get_impl_onleave_replace', row: getImplReplace });

    const interceptOrder = [
        'TMP_Text_set_text',
        'ScenarioPlayer_AttachSceneData',
        'CustomTextMesh_SetText',
        'CustomTextMesh_SetText_slot',
        'CustomText_SetText_slot',
        'WordingManager_Get',
        'WordingManager_GetFormat',
    ];
    const seq = tryAttachSequence(interceptOrder);
    emit('attach_probe', { ok: true, phase: 'intercept_order', result: seq });

    const getOnly = tryAttachSequence(['WordingManager_Get']);
    emit('attach_probe', { ok: true, phase: 'get_runtime_only', result: getOnly });

    // Fresh mapping: compare entry bytes to APK on-disk (no hooks yet on this page)
    const fresh = tryAttach('WordingManager_GetImpl_fresh_bytes', OFFSETS.WordingManager_GetImpl);
    emit('attach_probe', { ok: true, phase: 'entry_bytes', row: fresh });
}

emit('attach_probe', { ok: false, reason: 'polling' });

const deadline = Date.now() + 180000;
(function tick() {
    if (Process.findModuleByName(MODULE)) {
        run();
        return;
    }
    if (Date.now() > deadline) {
        emit('attach_probe', { ok: false, reason: 'timeout' });
        return;
    }
    setTimeout(tick, 500);
})();