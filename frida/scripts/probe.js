// Verify libil2cpp.so load and hook offset resolution
'use strict';

function probe() {
    const mod = Process.findModuleByName(MODULE);
    if (!mod) {
        emit('probe', { ok: false, reason: 'not loaded' });
        return;
    }

    const rows = [];
    for (const [name, off] of Object.entries(OFFSETS)) {
        const addr = mod.base.add(off);
        let prot = '?';
        try {
            const range = Process.findRangeByAddress(addr);
            prot = range ? range.protection : 'unmapped';
        } catch (_) {}
        rows.push({ name: name, offset: off, addr: addr.toString(), protection: prot });
    }
    emit('probe', { ok: true, base: mod.base.toString(), size: mod.size, rows: rows });
}

emit('probe', { ok: false, reason: 'polling' });

const deadline = Date.now() + 180000;
(function tick() {
    if (Process.findModuleByName(MODULE)) {
        probe();
        return;
    }
    if (Date.now() > deadline) {
        emit('probe', { ok: false, reason: 'timeout' });
        return;
    }
    setTimeout(tick, 500);
})();