// Read-only text monitor — no in-game modification
'use strict';

const CFG = { MAX_LOG: 80, STORY_CTX: true };
const stats = { tmp: 0, talk: 0, wordingKey: 0, wordingText: 0, storyCtx: 0 };
const storyCtx = { scenarioId: null, talkLine: -1, snippetIndex: -1, refIdx: -1 };

function readScenarioId(player) {
    const scene = readPtr(player, SCENARIO_PLAYER_SCENE);
    if (!scene) return null;
    return readStr(readPtr(scene, SCENARIO_SCENE_ID));
}

function readSnippetFields(snippet) {
    if (!snippet || snippet.isNull()) return { snippetIndex: -1, refIdx: -1 };
    try {
        return {
            snippetIndex: snippet.add(SCENARIO_SNIPPET_INDEX).readS32(),
            refIdx: snippet.add(SCENARIO_SNIPPET_REF_INDEX).readS32(),
        };
    } catch (_) {
        return { snippetIndex: -1, refIdx: -1 };
    }
}

function updateStoryCtx(player, snippet) {
    const sid = readScenarioId(player);
    const fields = readSnippetFields(snippet);
    const talkLine = computeTalkLineIdx(player, snippet);
    storyCtx.scenarioId = sid;
    storyCtx.talkLine = talkLine;
    storyCtx.snippetIndex = fields.snippetIndex;
    storyCtx.refIdx = fields.refIdx;
    return storyCtx;
}

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

    if (CFG.STORY_CTX) {
        hookAt('ScenarioPlayer.SnippetActionTalk', OFFSETS.ScenarioPlayer_SnippetActionTalk, {
            onEnter(args) {
                stats.storyCtx++;
                const player = args[0];
                const snippet = args[1];
                const ctx = updateStoryCtx(player, snippet);
                let seqId = -1;
                let bookmark = -1;
                if (player && !player.isNull()) {
                    try {
                        seqId = player.add(SCENARIO_PLAYER_SEQUENCE_ID).readS32();
                        bookmark = player.add(SCENARIO_PLAYER_BOOKMARK_SEQ).readS32();
                    } catch (_) {}
                }
                if (stats.storyCtx <= CFG.MAX_LOG) {
                    emit('story_ctx', {
                        scenarioId: ctx.scenarioId,
                        talkLine: ctx.talkLine,
                        snippetIndex: ctx.snippetIndex,
                        refIdx: ctx.refIdx,
                        sequenceId: seqId,
                        bookmarkSeq: bookmark,
                    });
                }
            },
        });
    }

    hookAt('TalkWindow.SetWordsInfo', OFFSETS.TalkWindow_SetWordsInfo, {
        onEnter(args) {
            stats.talk++;
            let extra = 'name=' + (readStr(args[2]) || '?') + ' cid=' + args[1].toInt32();
            try { extra += ' bookmark=' + args[5].toInt32(); } catch (_) {}
            if (CFG.STORY_CTX && storyCtx.scenarioId && storyCtx.talkLine >= 0) {
                extra += ' ctx=' + storyCtx.scenarioId + ':' + storyCtx.talkLine;
                extra += ' snip=' + storyCtx.snippetIndex + ' ref=' + storyCtx.refIdx;
            }
            logSample('STORY', readStr(args[3]), extra);
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