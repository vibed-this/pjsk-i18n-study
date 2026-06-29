// Font probe and/or Source Han primary replacement
'use strict';

const CFG = Object.assign({
    INJECT: false,
}, typeof CFG_OVERRIDE !== 'undefined' ? CFG_OVERRIDE : {});

const stats = {
    setupEnter: 0,
    setupLeave: 0,
    clearFallback: 0,
    fontInject: 0,
};

function emitFont(phase, hook, fields) {
    emit('font', Object.assign({ phase: phase, hook: hook }, fields));
}

function installProbe() {
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
}

function install() {
    if (CFG.INJECT) {
        bindIl2CppUnity();
        installFontInjectHook(stats);
    } else {
        installProbe();
    }

    emit('ready', {
        mode: CFG.INJECT ? 'font-inject' : 'font',
        inject: CFG.INJECT,
        fontMode: CFG.FONT_MODE || 'replace',
        stats: stats,
        managerFields: FONT_MANAGER_FIELDS,
        tmpFontFallbackOff: TMP_FONT_FALLBACK_LIST,
        bundlePath: CFG.FONT_BUNDLE_PATH || null,
        assetName: CFG.FONT_ASSET_NAME || null,
    });
}

start(stats, install);