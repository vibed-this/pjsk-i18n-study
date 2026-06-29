// Source Han TMP_FontAsset — primary replacement (after il2cpp_unity.js)
'use strict';

const FONT_MANAGER_PRIMARY = {
    baseA: 0x20,
    baseB: 0x38,
};

let _fontInjectCfgCache = null;

function fontInjectCfg() {
    if (_fontInjectCfgCache) return _fontInjectCfgCache;
    const override = (typeof CFG_OVERRIDE !== 'undefined') ? CFG_OVERRIDE : {};
    _fontInjectCfgCache = Object.assign({
        FONT_BUNDLE_PATH: '/sdcard/Android/data/com.sega.pjsekai/files/i18n/font/source-han-fallback.bundle',
        FONT_ASSET_NAME: 'SourceHanSansSC-Regular SDF',
        FONT_MODE: 'replace',  // 'replace' | 'dual' | 'load'
        INJECT_BASES: ['baseA', 'baseB'],
    }, override);
    return _fontInjectCfgCache;
}

let _cachedScFont = null;
let _fontInjectDone = false;

function writeMgrPtr(mgr, offset, ptr) {
    if (!mgr || mgr.isNull() || !ptr || ptr.isNull()) return false;
    try {
        mgr.add(offset).writePointer(ptr);
        return true;
    } catch (_) {
        return false;
    }
}

function appendToFallbackList(baseFont, fallbackFont) {
    if (!baseFont || baseFont.isNull() || !fallbackFont || fallbackFont.isNull()) {
        return { ok: false, reason: 'null_font' };
    }
    if (baseFont.equals(fallbackFont)) {
        return { ok: false, reason: 'same_font' };
    }
    const list = readPtr(baseFont, TMP_FONT_FALLBACK_LIST);
    if (!list) return { ok: false, reason: 'no_fallback_list' };

    const size = list.add(IL2CPP_LIST_SIZE).readS32();
    const items = readPtr(list, IL2CPP_LIST_ITEMS);
    if (!items) return { ok: false, reason: 'no_list_items' };

    for (let i = 0; i < size; i++) {
        try {
            const existing = items.add(0x20 + i * Process.pointerSize).readPointer();
            if (existing && !existing.isNull() && existing.equals(fallbackFont)) {
                return { ok: true, reason: 'already_present', sizeBefore: size, sizeAfter: size };
            }
        } catch (_) {}
    }

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
    if (_cachedScFont) return _cachedScFont;
    bindIl2CppUnity();
    const cfg = fontInjectCfg();
    const bundle = unityLoadAssetBundleFromFile(cfg.FONT_BUNDLE_PATH);
    const asset = unityLoadTmpFontAsset(bundle, cfg.FONT_ASSET_NAME);
    _cachedScFont = asset;
    return asset;
}

function getCachedSourceHanFont() {
    return _cachedScFont;
}

function replacePrimaryFonts(mgr, scFont) {
    const cfg = fontInjectCfg();
    const wanted = cfg.INJECT_BASES || ['baseA', 'baseB'];
    const results = {};
    const originals = [];
    const seen = {};
    let slotOk = true;

    for (let i = 0; i < wanted.length; i++) {
        const label = wanted[i];
        const off = FONT_MANAGER_PRIMARY[label];
        if (off === undefined) {
            results[label] = { ok: false, reason: 'unknown_slot' };
            slotOk = false;
            continue;
        }
        const orig = readPtr(mgr, off);
        if (!orig) {
            results[label] = { ok: false, reason: 'missing_original' };
            slotOk = false;
            continue;
        }
        const key = orig.toString();
        results[label] = {
            ok: true,
            originalName: readUnityObjectName(orig),
            originalPtr: key,
        };
        if (!seen[key]) {
            seen[key] = true;
            originals.push(orig);
        }
    }

    if (!slotOk) {
        return { ok: false, mode: 'replace', reason: 'missing_slots', results: results };
    }

    const fallbackDemote = [];
    let fallbackWarn = false;
    for (let j = 0; j < originals.length; j++) {
        const orig = originals[j];
        const row = appendToFallbackList(scFont, orig);
        row.name = readUnityObjectName(orig);
        fallbackDemote.push(row);
        if (!row.ok && row.reason !== 'same_font' && row.reason !== 'already_present') {
            fallbackWarn = true;
        }
    }

    let replaceOk = true;
    for (let i = 0; i < wanted.length; i++) {
        const label = wanted[i];
        const off = FONT_MANAGER_PRIMARY[label];
        if (!writeMgrPtr(mgr, off, scFont)) {
            results[label].ok = false;
            results[label].reason = 'write_failed';
            replaceOk = false;
            continue;
        }
        results[label].replaced = true;
        results[label].primaryName = readUnityObjectName(scFont);
    }

    return {
        ok: replaceOk,
        mode: 'replace',
        scFont: describeTmpFontAsset(scFont),
        results: results,
        fallbackDemote: fallbackDemote,
        fallbackWarn: fallbackWarn,
        after: describeFontManager(mgr),
    };
}

function injectSourceHanIntoManager(mgr) {
    if (_fontInjectDone) {
        return { ok: true, skipped: true, reason: 'already_injected' };
    }
    if (!mgr || mgr.isNull()) {
        return { ok: false, reason: 'null_manager' };
    }

    const cfg = fontInjectCfg();
    const mode = cfg.FONT_MODE || 'replace';

    let scFont;
    try {
        scFont = loadSourceHanTmpFont();
    } catch (e) {
        return { ok: false, reason: 'load_failed', error: String(e), mode: mode };
    }

    if (mode === 'dual' || mode === 'load') {
        _fontInjectDone = true;
        return {
            ok: true,
            mode: mode,
            scFont: describeTmpFontAsset(scFont),
            skippedReplace: true,
            after: describeFontManager(mgr),
        };
    }

    const out = replacePrimaryFonts(mgr, scFont);
    if (out.ok) _fontInjectDone = true;
    return out;
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