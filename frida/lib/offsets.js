// Hook offsets — IDA function entry (see notes/ida-verification.md)
// Game version: 6.5.5 (device TB322FC; confirm local apk/ versionName on update)
'use strict';

const MODULE = 'libil2cpp.so';
const PACKAGE = 'com.sega.pjsekai';

const OFFSETS = {
    TMP_Text_set_text:                0xA8D1B98,
    TalkWindow_SetWordsInfo:          0x6264FD8,
    ScenarioPlayer_SnippetActionTalk: 0x624FC28,  // 协程工厂；写剧情上下文
    ScenarioJumper_SnippetActionTalk: 0x6244D80,  // 日志跳转旁路
    CustomTextMesh_SetWordingText:    0x4F2B408,
    CustomTextMesh_UpdateWordingText: 0x4F2B2EC,
    CustomTextMesh_SetText:           0x4F27530,  // CustomTextMesh.SetText（IDA 入口）
    CustomTextMesh_SetText_slot:      0x4F2B590,  // ICustomText.SetText slot — UpdateWordingText tail-call 目标
    CustomText_SetText_slot:          0x4F2B1B4,  // CustomText.SetText slot（legacy Unity Text）
    CustomText_SetWordingText:        0x4F2B02C,  // CustomText.SetWordingText(string key)
    WordingManager_Get:               0x60241BC,  // 静态包装器（tail-call，Frida onLeave 不可靠）
    WordingManager_GetImpl:           0x60282AC,  // Get(string key) 实现体
    WordingManager_GetFormat:         0x602F054,  // GetFormat(key, args)
    FontAssetManager_SetupBuiltinFontAsset: 0x61028AC,
    FontAssetManager_ClearFallbackFontAsset: 0x61024F8,  // 清空 TMP_FontAsset.fallbackFontAssetTable
    ScenarioPlayer_AttachSceneData:       0x624C100,  // 剧情 bundle patch 首选（见 ida-verification §剧情 bundle）
    ScreenLayerScenario_OnFinishLoadScenario: 0x63E1F80,
};

// FontAssetManager @ 6.5.5（IDA SetupBuiltinFontAsset 反汇编）
const FONT_MANAGER_FIELDS = [
    { off: 0x20, label: 'baseA' },
    { off: 0x28, label: 'loadedA' },
    { off: 0x30, label: 'fallbackSrcA' },
    { off: 0x38, label: 'baseB' },
    { off: 0x40, label: 'loadedB' },
    { off: 0x48, label: 'fallbackSrcB' },
];

const TMP_FONT_FALLBACK_LIST = 0x138;
const IL2CPP_LIST_ITEMS = 0x10;
const IL2CPP_LIST_SIZE = 0x18;

// ScenarioPlayer / ScenarioSceneData（6.5.5，见 notes/ida-verification.md §剧情运行时 ID）
const SCENARIO_PLAYER_SCENE = 0x1B0;
const SCENARIO_PLAYER_SEQUENCE_ID = 0x1B8;
const SCENARIO_PLAYER_BOOKMARK_SEQ = 0x380;
const SCENARIO_SCENE_ID = 0x18;
const SCENARIO_SCENE_SNIPPETS = 0x58;
const SCENARIO_SCENE_TALK_DATA = 0x60; // ScenarioSnippetTalk[]（JSON 称 TalkData）
const SCENARIO_SNIPPET_TALK_NAME = 0x18; // WindowDisplayName
const SCENARIO_SNIPPET_TALK_BODY = 0x20;
const SCENARIO_PLAYER_ATTACH_SCENE_DATA = 0x624C100;
const SCREEN_LAYER_ON_FINISH_LOAD_SCENARIO = 0x63E1F80;
const BUNDLE_ELEMENT_LOADED_RESOURCE = 0x20;
const SCENARIO_SNIPPET_INDEX = 0x10;
const SCENARIO_SNIPPET_ACTION = 0x14;
const SCENARIO_SNIPPET_REF_INDEX = 0x1C;
const SCENARIO_ACTION_TALK = 1;
const IL2CPP_ARRAY_MAX_LENGTH = 0x18;
const IL2CPP_ARRAY_VECTOR = 0x20;