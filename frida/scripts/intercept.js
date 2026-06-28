// Intercept demo — in-game prefix + structured PC output
'use strict';

const CFG = Object.assign({
    PREFIX: '[TEST] ',
    SKIP_IF_PREFIXED: true,
    MAX_LOG: 200,
    INTERCEPT: { TMP: true, STORY: true, UI: true },
}, typeof CFG_OVERRIDE !== 'undefined' ? CFG_OVERRIDE : {});

const stats = { tmp: 0, story: 0, ui: 0, uiKey: 0, intercept: 0, skip: 0 };

function shouldSkip(text) {
    return CFG.SKIP_IF_PREFIXED && text && text.indexOf(CFG.PREFIX) === 0;
}

function prefixed(text) {
    return CFG.PREFIX + text;
}

function logIntercept(hook, original, replaced, ok, extra) {
    if (ok) stats.intercept++;
    emit('intercept', { hook: hook, original: original, replaced: replaced, ok: !!ok, extra: extra || '' });
}

function logCapture(tag, fields) {
    emit('capture', Object.assign({ tag: tag }, fields));
}

function install() {
    if (CFG.INTERCEPT.TMP) {
        hookAt('TMP_Text.set_text', OFFSETS.TMP_Text_set_text, {
            onEnter(args) {
                stats.tmp++;
                const orig = readStr(args[1]);
                if (!orig) return;
                if (shouldSkip(orig)) { stats.skip++; return; }
                const next = prefixed(orig);
                const rep = makeStr(next);
                const ok = !!(rep && !rep.isNull());
                if (ok) args[1] = rep;
                if (stats.tmp <= CFG.MAX_LOG) logIntercept('TMP_Text.set_text', orig, next, ok);
            },
        });
    }

    if (CFG.INTERCEPT.STORY) {
        hookAt('TalkWindow.SetWordsInfo', OFFSETS.TalkWindow_SetWordsInfo, {
            onEnter(args) {
                stats.story++;
                const name = readStr(args[2]);
                const words = readStr(args[3]);
                const cid = args[1].toInt32();
                let newName = name;
                let newWords = words;

                if (name && !shouldSkip(name)) {
                    newName = prefixed(name);
                    const rep = makeStr(newName);
                    if (rep && !rep.isNull()) args[2] = rep;
                }
                if (words && !shouldSkip(words)) {
                    newWords = prefixed(words);
                    const rep = makeStr(newWords);
                    if (rep && !rep.isNull()) args[3] = rep;
                }

                if (stats.story <= CFG.MAX_LOG) {
                    if (words) logIntercept('TalkWindow.SetWordsInfo', words, newWords, true, 'cid=' + cid);
                    if (name) logCapture('STORY_NAME', { name: name, replaced: newName, cid: cid });
                }
            },
        });
    }

    if (CFG.INTERCEPT.UI) {
        hookAt('CustomTextMesh.UpdateWordingText', OFFSETS.CustomTextMesh_UpdateWordingText, {
            onLeave(retval) {
                stats.ui++;
                const orig = readStr(retval);
                if (!orig) return;
                if (shouldSkip(orig)) { stats.skip++; return; }
                const next = prefixed(orig);
                const rep = makeStr(next);
                const ok = !!(rep && !rep.isNull());
                if (ok) retval.replace(rep);
                if (stats.ui <= CFG.MAX_LOG) logIntercept('UpdateWordingText', orig, next, ok);
            },
        });
    }

    hookAt('CustomTextMesh.SetWordingText', OFFSETS.CustomTextMesh_SetWordingText, {
        onEnter(args) {
            stats.uiKey++;
            if (stats.uiKey > CFG.MAX_LOG) return;
            const key = readStr(args[1]);
            if (key) logCapture('UI_KEY', { key: key });
        },
    });

    emit('ready', { mode: 'intercept', prefix: CFG.PREFIX, intercept: CFG.INTERCEPT, stats: stats });
}

start(stats, install);