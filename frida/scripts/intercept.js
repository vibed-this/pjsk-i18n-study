// Intercept — prefix demo or story dual-subtitle (zh + jp)
'use strict';

const DEMO_ZH = {
    'ミク': '初音未来',
    'こんにちは。\nここに誰かが来るなんて、珍しいな': '你好。这里居然还会有人来，真少见。',
    'わたしは、初音ミク。\nキミの名前は？': '我是初音未来。你的名字是？',
};

function uiWordingsMap() {
    return (typeof UI_WORDINGS !== 'undefined' && UI_WORDINGS) ? UI_WORDINGS : {};
}

function uiPlainTextMap() {
    return (typeof UI_PLAIN_TEXT !== 'undefined' && UI_PLAIN_TEXT) ? UI_PLAIN_TEXT : {};
}

function storyTextMap() {
    return (typeof STORY_TEXT !== 'undefined' && STORY_TEXT) ? STORY_TEXT : {};
}

const CFG = Object.assign({
    PREFIX: '[TEST] ',
    UI_MODE: 'prefix',  // 'cn' | 'prefix' — run.py sets 'cn' when wordings.json loaded
    STORY_MODE: 'prefix',   // 'prefix' | 'cn' | 'dual'
    DUAL_STYLE: 'plain',    // 'plain' | 'rich'
    DUAL_PLACEHOLDER: '译',
    DUAL_TAG: '[[',         // 译文行以 [[...]] 包裹；用开头检测防重复
    SKIP_IF_PREFIXED: true,
    MAX_LOG: 200,
    INTERCEPT: { TMP: true, STORY: true, UI: true },
    FONT_INJECT: false,
}, typeof CFG_OVERRIDE !== 'undefined' ? CFG_OVERRIDE : {});

const stats = {
    tmp: 0, story: 0, ui: 0, uiKey: 0,
    wordingGet: 0, wordingFmt: 0, uiSetText: 0, uiPlain: 0, storyCn: 0,
    intercept: 0, skip: 0, dual: 0,
};

function lookupZh(jp) {
    if (!jp) return CFG.DUAL_PLACEHOLDER;
    if (Object.prototype.hasOwnProperty.call(DEMO_ZH, jp)) return DEMO_ZH[jp];
    return CFG.DUAL_PLACEHOLDER;
}

function alreadyDualSubtitle(text) {
    return !!(text && text.indexOf(CFG.DUAL_TAG) === 0);
}

function wrapZh(zh) {
    return '[[' + zh + ']]';
}

function formatDualSubtitle(jp) {
    const zhLine = wrapZh(lookupZh(jp));
    if (CFG.DUAL_STYLE === 'rich') {
        return zhLine + '\n<size=75%><color=#888888>' + jp + '</color></size>';
    }
    return zhLine + '\n' + jp;
}

function shouldSkipPrefix(text) {
    return CFG.SKIP_IF_PREFIXED && text && text.indexOf(CFG.PREFIX) === 0;
}

function prefixed(text) {
    return CFG.PREFIX + text;
}

function replaceArg(argPtr, nextText) {
    const rep = makeStr(nextText);
    if (!rep || rep.isNull()) return { ok: false, text: nextText };
    return { ok: true, text: nextText, ptr: rep };
}

function logIntercept(hook, original, replaced, ok, extra) {
    if (ok) stats.intercept++;
    emit('intercept', { hook: hook, original: original, replaced: replaced, ok: !!ok, extra: extra || '' });
}

function logCapture(tag, fields) {
    emit('capture', Object.assign({ tag: tag }, fields));
}

function applyStoryDual(jp) {
    if (!jp || alreadyDualSubtitle(jp)) {
        return { changed: false, text: jp };
    }
    const next = formatDualSubtitle(jp);
    const rep = makeStr(next);
    if (!rep || rep.isNull()) return { changed: false, text: jp };
    stats.dual++;
    return { changed: true, text: next, ptr: rep };
}

function replaceEnterArgPlain(args, index, hookName, statBump) {
    if (statBump) statBump();
    const orig = readStr(args[index]);
    if (!orig) return;
    const zh = lookupUiPlain(orig);
    if (!zh) return;
    const hit = replaceArg(args[index], zh);
    if (hit.ok) {
        args[index] = hit.ptr;
        stats.uiPlain++;
    }
    if (stats.intercept < CFG.MAX_LOG) {
        logIntercept(hookName, orig, zh, hit.ok, 'mode=cn-plain');
    }
}

function prefixEnterArg(args, index, hookName, statBump) {
    if (statBump) statBump();
    const orig = readStr(args[index]);
    if (!orig) return;
    if (CFG.UI_MODE === 'cn') {
        replaceEnterArgPlain(args, index, hookName, null);
        return;
    }
    if (CFG.STORY_MODE === 'dual') return;
    if (shouldSkipPrefix(orig)) { stats.skip++; return; }
    const next = prefixed(orig);
    const hit = replaceArg(args[index], next);
    if (hit.ok) args[index] = hit.ptr;
    if (stats.intercept < CFG.MAX_LOG) logIntercept(hookName, orig, next, hit.ok);
}

function lookupUiZh(key) {
    if (!key) return null;
    const map = uiWordingsMap();
    if (Object.prototype.hasOwnProperty.call(map, key)) return map[key];
    return null;
}

function lookupUiPlain(jp) {
    if (!jp) return null;
    const map = uiPlainTextMap();
    if (Object.prototype.hasOwnProperty.call(map, jp)) return map[jp];
    return null;
}

function lookupStoryZh(jp) {
    if (!jp) return null;
    const map = storyTextMap();
    if (Object.prototype.hasOwnProperty.call(map, jp)) return map[jp];
    return null;
}

function replaceRetvalZh(retval, zh, hookName, orig) {
    const hit = replaceArg(retval, zh);
    if (hit.ok) retval.replace(hit.ptr);
    if (stats.intercept < CFG.MAX_LOG) logIntercept(hookName, orig, zh, hit.ok, 'mode=cn');
    return hit.ok;
}

function prefixLeaveRetval(retval, hookName, statBump, key) {
    if (statBump) statBump();
    if (CFG.STORY_MODE === 'dual') return;
    const orig = readStr(retval);
    if (!orig) return;
    if (CFG.UI_MODE === 'cn' && key) {
        const zh = lookupUiZh(key);
        if (zh) {
            replaceRetvalZh(retval, zh, hookName, orig);
            return;
        }
    }
    if (shouldSkipPrefix(orig)) { stats.skip++; return; }
    const next = prefixed(orig);
    const hit = replaceArg(retval, next);
    if (hit.ok) retval.replace(hit.ptr);
    if (stats.intercept < CFG.MAX_LOG) logIntercept(hookName, orig, next, hit.ok);
}

function applyStoryPrefix(jp) {
    if (!jp || shouldSkipPrefix(jp)) {
        if (jp && shouldSkipPrefix(jp)) stats.skip++;
        return { changed: false, text: jp };
    }
    const next = prefixed(jp);
    const rep = makeStr(next);
    if (!rep || rep.isNull()) return { changed: false, text: jp };
    return { changed: true, text: next, ptr: rep };
}

function applyStoryCn(jp, field) {
    if (!jp) return { changed: false, text: jp };
    const zh = lookupStoryZh(jp);
    if (!zh) return { changed: false, text: jp };
    const rep = makeStr(zh);
    if (!rep || rep.isNull()) return { changed: false, text: jp };
    stats.storyCn++;
    return { changed: true, text: zh, ptr: rep };
}

function install() {
    if (CFG.INTERCEPT.TMP) {
        hookAt('TMP_Text.set_text', OFFSETS.TMP_Text_set_text, {
            onEnter(args) {
                stats.tmp++;
                const orig = readStr(args[1]);
                if (!orig) return;
                if (CFG.STORY_MODE === 'dual') return;
                if (shouldSkipPrefix(orig)) { stats.skip++; return; }
                const next = prefixed(orig);
                const hit = replaceArg(args[1], next);
                if (hit.ok) args[1] = hit.ptr;
                if (stats.tmp <= CFG.MAX_LOG) logIntercept('TMP_Text.set_text', orig, next, hit.ok);
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

                if (CFG.STORY_MODE === 'dual') {
                    let wordsHit = { changed: false, text: words };
                    let nameHit = { changed: false, text: name };
                    if (name) nameHit = applyStoryDual(name);
                    if (words) wordsHit = applyStoryDual(words);
                    newName = nameHit.text;
                    newWords = wordsHit.text;
                    if (nameHit.changed) args[2] = nameHit.ptr;
                    if (wordsHit.changed) args[3] = wordsHit.ptr;
                    if (stats.story <= CFG.MAX_LOG) {
                        if (words) {
                            logIntercept('TalkWindow.SetWordsInfo', words, newWords, wordsHit.changed,
                                'mode=dual cid=' + cid + ' style=' + CFG.DUAL_STYLE);
                        }
                        if (name) {
                            logCapture('STORY_NAME', {
                                name: name, replaced: newName, ok: nameHit.changed, cid: cid, mode: 'dual',
                            });
                        }
                    }
                    return;
                }

                if (CFG.STORY_MODE === 'cn') {
                    if (name) {
                        const hit = applyStoryCn(name, 'name');
                        newName = hit.text;
                        if (hit.changed) args[2] = hit.ptr;
                    }
                    if (words) {
                        const hit = applyStoryCn(words, 'body');
                        newWords = hit.text;
                        if (hit.changed) args[3] = hit.ptr;
                    }
                } else {
                    if (name && !shouldSkipPrefix(name)) {
                        const hit = applyStoryPrefix(name);
                        newName = hit.text;
                        if (hit.changed) args[2] = hit.ptr;
                    }
                    if (words && !shouldSkipPrefix(words)) {
                        const hit = applyStoryPrefix(words);
                        newWords = hit.text;
                        if (hit.changed) args[3] = hit.ptr;
                    }
                }

                if (stats.story <= CFG.MAX_LOG) {
                    const mode = CFG.STORY_MODE === 'cn' ? 'mode=cn' : '';
                    if (words) {
                        logIntercept('TalkWindow.SetWordsInfo', words, newWords, newWords !== words,
                            'cid=' + cid + (mode ? ' ' + mode : ''));
                    }
                    if (name) {
                        logCapture('STORY_NAME', {
                            name: name, replaced: newName, ok: newName !== name, cid: cid,
                            mode: CFG.STORY_MODE,
                        });
                    }
                }
            },
        });
    }

    if (CFG.INTERCEPT.UI) {
        // 词表 UI：SetWordingText 只存 key → Get/GetFormat → CustomTextMesh.SetText（vtable）。
        // tmp=0 正常：不经 TMP_Text.set_text；UpdateWordingText onLeave 亦不可用。
        hookAt('CustomTextMesh.SetText', OFFSETS.CustomTextMesh_SetText, {
            onEnter(args) {
                prefixEnterArg(args, 1, 'CustomTextMesh.SetText', () => { stats.uiSetText++; });
            },
        });
        hookAt('CustomTextMesh.SetText(slot)', OFFSETS.CustomTextMesh_SetText_slot, {
            onEnter(args) {
                prefixEnterArg(args, 1, 'CustomTextMesh.SetText(slot)', () => { stats.uiSetText++; });
            },
        });
        hookAt('CustomText.SetText(slot)', OFFSETS.CustomText_SetText_slot, {
            onEnter(args) {
                prefixEnterArg(args, 1, 'CustomText.SetText(slot)', () => { stats.uiSetText++; });
            },
        });
        hookAt('WordingManager.Get', OFFSETS.WordingManager_GetImpl, {
            onEnter(args) {
                this.key = readStr(args[0]);
            },
            onLeave(retval) {
                prefixLeaveRetval(retval, 'WordingManager.Get', () => { stats.wordingGet++; }, this.key);
            },
        });
        hookAt('WordingManager.GetFormat', OFFSETS.WordingManager_GetFormat, {
            onEnter(args) {
                this.key = readStr(args[0]);
            },
            onLeave(retval) {
                prefixLeaveRetval(retval, 'WordingManager.GetFormat', () => { stats.wordingFmt++; }, this.key);
            },
        });
        hookAt('CustomTextMesh.UpdateWordingText', OFFSETS.CustomTextMesh_UpdateWordingText, {
            onEnter() { stats.ui++; },
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
    hookAt('CustomText.SetWordingText', OFFSETS.CustomText_SetWordingText, {
        onEnter(args) {
            stats.uiKey++;
            if (stats.uiKey > CFG.MAX_LOG) return;
            const key = readStr(args[1]);
            if (key) logCapture('UI_KEY', { key: key, component: 'CustomText' });
        },
    });

    if (CFG.FONT_INJECT && typeof installFontInjectHook === 'function') {
        bindIl2CppUnity();
        installFontInjectHook(stats);
    }

    emit('ready', {
        mode: 'intercept',
        storyMode: CFG.STORY_MODE,
        uiMode: CFG.UI_MODE,
        fontInject: CFG.FONT_INJECT,
        fontMode: CFG.FONT_MODE || 'replace',
        dualStyle: CFG.DUAL_STYLE,
        prefix: CFG.PREFIX,
        intercept: CFG.INTERCEPT,
        demoKeys: Object.keys(DEMO_ZH).length,
        uiWordings: Object.keys(uiWordingsMap()).length,
        uiPlainText: Object.keys(uiPlainTextMap()).length,
        storyText: Object.keys(storyTextMap()).length,
        stats: stats,
    });
}

start(stats, install);