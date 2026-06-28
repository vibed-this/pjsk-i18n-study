// Source Han TMP_FontAsset fallback injection (after il2cpp_unity.js)
'use strict';

let _fontInjectCfgCache = null;

function fontInjectCfg() {
    if (_fontInjectCfgCache) return _fontInjectCfgCache;
    const override = (typeof CFG_OVERRIDE !== 'undefined') ? CFG_OVERRIDE : {};
    _fontInjectCfgCache = Object.assign({
        FONT_BUNDLE_PATH: '/sdcard/Android/data/com.sega.pjsekai/files/i18n/font/source-han-fallback.bundle',
        FONT_ASSET_NAME: 'SourceHanSansSC-Regular SDF',
        INJECT_BASES: ['baseA', 'baseB'],
    }, override);
    return _fontInjectCfgCache;
}

let _cachedFallbackFont = null;
let _fontInjectDone = false;

function appendToFallbackList(baseFont, fallbackFont) {
    if (!baseFont || baseFont.isNull() || !fallbackFont || fallbackFont.isNull()) {
        return { ok: false, reason: 'null_font' };
    }
    const list = readPtr(baseFont, TMP_FONT_FALLBACK_LIST);
    if (!list) return { ok: false, reason: 'no_fallback_list' };

    const size = list.add(IL2CPP_LIST_SIZE).readS32();
    const items = readPtr(list, IL2CPP_LIST_ITEMS);
    if (!items) return { ok: false, reason: 'no_list_items' };

    const capacity = items.add(0x18).readS32();
    if (size < 0 || size >= capacity) {
        return { ok: false, reason: 'list_full', size: size, capacity: capacity };
    }

    items.add(0x20 + size * Process.pointerSize).writePointer(fallbackFont);
    list.add(IL2CPP_LIST_SIZE).writeS32(size + 1);
    try {
        const ver = list.add(0x1C).readS32();
        list.add(0x1C).writeS32(ver + 1);
    } catch (_) {}

    return { ok: true, sizeBefore: size, sizeAfter: size + 1 };
}

function loadSourceHanTmpFont() {
    if (_cachedFallbackFont) return _cachedFallbackFont;
    bindIl2CppUnity();
    const cfg = fontInjectCfg();
    const bundle = unityLoadAssetBundleFromFile(cfg.FONT_BUNDLE_PATH);
    const asset = unityLoadTmpFontAsset(bundle, cfg.FONT_ASSET_NAME);
    _cachedFallbackFont = asset;
    return asset;
}

function injectSourceHanIntoManager(mgr) {
    if (_fontInjectDone) {
        return { ok: true, skipped: true, reason: 'already_injected' };
    }
    if (!mgr || mgr.isNull()) {
        return { ok: false, reason: 'null_manager' };
    }

    let fallback;
    try {
        fallback = loadSourceHanTmpFont();
    } catch (e) {
        return { ok: false, reason: 'load_failed', error: String(e) };
    }

    const targets = {
        baseA: readPtr(mgr, 0x20),
        baseB: readPtr(mgr, 0x38),
    };
    const results = {};
    let ok = true;
    const wanted = fontInjectCfg().INJECT_BASES || ['baseA', 'baseB'];
    for (let i = 0; i < wanted.length; i++) {
        const label = wanted[i];
        const base = targets[label];
        if (!base) {
            results[label] = { ok: false, reason: 'missing_base' };
            ok = false;
            continue;
        }
        results[label] = appendToFallbackList(base, fallback);
        results[label].baseName = readUnityObjectName(base);
        if (!results[label].ok) ok = false;
    }

    if (ok) _fontInjectDone = true;
    return {
        ok: ok,
        fallback: describeTmpFontAsset(fallback),
        results: results,
        after: describeFontManager(mgr),
    };
}

function installFontInjectHook(stats) {
    hookAt('FontAssetManager.SetupBuiltinFontAsset', OFFSETS.FontAssetManager_SetupBuiltinFontAsset, {
        onEnter(args) {
            this.mgr = args[0];
        },
        onLeave(_retval) {
            const out = injectSourceHanIntoManager(this.mgr);
            if (stats) stats.fontInject = (stats.fontInject || 0) + 1;
            emit('font_inject', out);
        },
    });
}