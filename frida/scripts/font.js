// Font probe — SetupBuiltinFontAsset / ClearFallbackFontAsset (read-only)
'use strict';

const stats = {
    setupEnter: 0,
    setupLeave: 0,
    clearFallback: 0,
};

function emitFont(phase, hook, fields) {
    emit('font', Object.assign({ phase: phase, hook: hook }, fields));
}

function install() {
    hookAt('FontAssetManager.SetupBuiltinFontAsset', OFFSETS.FontAssetManager_SetupBuiltinFontAsset, {
        onEnter(args) {
            stats.setupEnter++;
            this.mgr = args[0];
            this.before = describeFontManager(this.mgr);
            emitFont('enter', 'SetupBuiltinFontAsset', {
                mgr: this.mgr ? this.mgr.toString() : null,
                before: this.before,
            });
        },
        onLeave(_retval) {
            stats.setupLeave++;
            const after = describeFontManager(this.mgr);
            emitFont('leave', 'SetupBuiltinFontAsset', {
                mgr: this.mgr ? this.mgr.toString() : null,
                before: this.before,
                after: after,
            });
        },
    });

    hookAt('FontAssetManager.ClearFallbackFontAsset', OFFSETS.FontAssetManager_ClearFallbackFontAsset, {
        onEnter(args) {
            stats.clearFallback++;
            const font = args[1];
            const info = describeTmpFontAsset(font);
            emitFont('enter', 'ClearFallbackFontAsset', {
                mgr: args[0] ? args[0].toString() : null,
                font: info,
            });
        },
    });

    emit('ready', {
        mode: 'font',
        stats: stats,
        managerFields: FONT_MANAGER_FIELDS,
        tmpFontFallbackOff: TMP_FONT_FALLBACK_LIST,
    });
}

start(stats, install);