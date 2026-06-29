// ScenarioSceneData patch @ AttachSceneData（见 notes/ida-verification.md §剧情 bundle 载入链）
'use strict';

const STORY_JP_BACKUP = {};

function storyByScenarioMap() {
    return (typeof STORY_BY_SCENARIO !== 'undefined' && STORY_BY_SCENARIO) ? STORY_BY_SCENARIO : null;
}

function lookupStoryLineZh(scenarioId, talkLineIdx, jpName, jpBody) {
    const bySc = storyByScenarioMap();
    if (bySc && Object.prototype.hasOwnProperty.call(bySc, scenarioId)) {
        const lines = bySc[scenarioId];
        if (Array.isArray(lines) && talkLineIdx >= 0 && talkLineIdx < lines.length) {
            const row = lines[talkLineIdx];
            if (row && typeof row === 'object') {
                const name = row.name || row.zhName || row.displayName || null;
                const body = row.body || row.zhBody || row.zh || null;
                if (name || body) return { name: name, body: body };
            }
        }
    }
    const map = (typeof STORY_TEXT !== 'undefined' && STORY_TEXT) ? STORY_TEXT : {};
    const nameZh = jpName && Object.prototype.hasOwnProperty.call(map, jpName) ? map[jpName] : null;
    const bodyZh = jpBody && Object.prototype.hasOwnProperty.call(map, jpBody) ? map[jpBody] : null;
    if (!nameZh && !bodyZh) return null;
    return { name: nameZh, body: bodyZh };
}

function readTalkFields(talk) {
    const name = readStr(readPtr(talk, SCENARIO_SNIPPET_TALK_NAME));
    const body = readStr(readPtr(talk, SCENARIO_SNIPPET_TALK_BODY));
    return { name: name, body: body };
}

function backupScenarioTalkLines(scenarioId, lines) {
    if (!scenarioId) return;
    const bucket = [];
    for (let i = 0; i < lines.length; i++) {
        const fields = readTalkFields(lines[i].talk);
        bucket[lines[i].talkLineIdx] = {
            name: fields.name,
            body: fields.body,
        };
    }
    STORY_JP_BACKUP[scenarioId] = bucket;
}

function patchScenarioSceneData(scene, stats, cfg) {
    if (!scene || scene.isNull()) return { scenarioId: null, lines: 0, patched: 0 };
    const scenarioId = readStr(readPtr(scene, SCENARIO_SCENE_ID));
    const talkLines = enumerateScenarioTalkLines(scene);
    if (!talkLines.length) {
        return { scenarioId: scenarioId, lines: 0, patched: 0 };
    }

    if (cfg.STORY_MODE === 'dual') {
        backupScenarioTalkLines(scenarioId, talkLines);
        return { scenarioId: scenarioId, lines: talkLines.length, patched: 0, backedUp: talkLines.length };
    }

    if (cfg.STORY_MODE !== 'cn') {
        return { scenarioId: scenarioId, lines: talkLines.length, patched: 0 };
    }

    let patched = 0;
    for (let i = 0; i < talkLines.length; i++) {
        const row = talkLines[i];
        const fields = readTalkFields(row.talk);
        const zh = lookupStoryLineZh(scenarioId, row.talkLineIdx, fields.name, fields.body);
        if (!zh) continue;
        let hit = false;
        if (zh.name && fields.name && zh.name !== fields.name) {
            if (writeStringField(row.talk, SCENARIO_SNIPPET_TALK_NAME, zh.name)) hit = true;
        }
        if (zh.body && fields.body && zh.body !== fields.body) {
            if (writeStringField(row.talk, SCENARIO_SNIPPET_TALK_BODY, zh.body)) hit = true;
        }
        if (hit) {
            patched++;
            if (stats.storyPatchLog < cfg.MAX_LOG) {
                emit('story_patch', {
                    scenarioId: scenarioId,
                    line: row.talkLineIdx,
                    refIdx: row.refIdx,
                    jpName: fields.name,
                    jpBody: fields.body,
                    zhName: zh.name,
                    zhBody: zh.body,
                });
            }
        }
    }
    return { scenarioId: scenarioId, lines: talkLines.length, patched: patched };
}

function installStoryAttachHook(stats, cfg) {
    if (!cfg.STORY_PATCH_ATTACH) return;
    if (cfg.STORY_MODE !== 'cn' && cfg.STORY_MODE !== 'dual') return;
    stats.storyPatchAttach = 0;
    stats.storyPatchLines = 0;
    stats.storyPatchHits = 0;
    stats.storyPatchLog = 0;

    hookAt('ScenarioPlayer.AttachSceneData', OFFSETS.ScenarioPlayer_AttachSceneData, {
        onEnter(args) {
            stats.storyPatchAttach++;
            const scene = args[1];
            if (stats.storyPatchLog < cfg.MAX_LOG) {
                const diag = { player: args[0] ? args[0].toString() : null, scene: scene ? scene.toString() : null };
                if (scene && !scene.isNull()) {
                    diag.objName = readUnityObjectName(scene);
                    diag.scenarioIdPeek = readStr(readPtr(scene, SCENARIO_SCENE_ID));
                    diag.snippetsLen = readIl2CppArrayLength(readPtr(scene, SCENARIO_SCENE_SNIPPETS));
                    diag.talkLen = readIl2CppArrayLength(readPtr(scene, SCENARIO_SCENE_TALK_DATA));
                }
                emit('story_patch_diag', diag);
            }
            const result = patchScenarioSceneData(scene, stats, cfg);
            stats.storyPatchLines += result.lines || 0;
            stats.storyPatchHits += result.patched || 0;
            if (result.backedUp) stats.storyPatchBackup = (stats.storyPatchBackup || 0) + result.backedUp;
            if (stats.storyPatchLog < cfg.MAX_LOG) {
                emit('story_patch_summary', {
                    scenarioId: result.scenarioId,
                    lines: result.lines,
                    patched: result.patched,
                    backedUp: result.backedUp || 0,
                    mode: cfg.STORY_MODE,
                });
            }
            stats.storyPatchLog++;
        },
    });
}