// Read-only text monitor — no in-game modification
'use strict';

const CFG = { MAX_LOG: 80 };
const stats = { tmp: 0, talk: 0, wordingKey: 0, wordingText: 0 };

function logSample(tag, text, extra) {
    if (!text) return;
    const preview = text.length > 80 ? text.substring(0, 80) + '…' : text;
    emit('text', { tag: tag, text: preview, extra: extra || '' });
}

function install() {
    hookAt('TMP_Text.set_text', OFFSETS.TMP_Text_set_text, {
        onEnter(args) {
            stats.tmp++;
            if (stats.tmp <= CFG.MAX_LOG || stats.tmp % 100 === 0) {
                logSample('TMP', readStr(args[1]), '');
            }
        },
    });

    hookAt('TalkWindow.SetWordsInfo', OFFSETS.TalkWindow_SetWordsInfo, {
        onEnter(args) {
            stats.talk++;
            logSample('STORY', readStr(args[3]),
                'name=' + (readStr(args[2]) || '?') + ' cid=' + args[1].toInt32());
        },
    });

    hookAt('CustomTextMesh.SetWordingText', OFFSETS.CustomTextMesh_SetWordingText, {
        onEnter(args) {
            stats.wordingKey++;
            if (stats.wordingKey <= CFG.MAX_LOG || stats.wordingKey % 50 === 0) {
                logSample('UI_KEY', readStr(args[1]), '');
            }
        },
    });

    hookAt('CustomTextMesh.UpdateWordingText', OFFSETS.CustomTextMesh_UpdateWordingText, {
        onLeave(retval) {
            stats.wordingText++;
            if (stats.wordingText <= CFG.MAX_LOG || stats.wordingText % 50 === 0) {
                logSample('UI', readStr(retval), '');
            }
        },
    });

    emit('ready', { mode: 'monitor', stats: stats });
}

start(stats, install);