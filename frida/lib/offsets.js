// Hook offsets — IDA function entry (see notes/ida-verification.md)
// Game version: 6.6.0 (apk/base.apk versionName; device may lag — re-probe after install)
'use strict';

const MODULE = 'libil2cpp.so';
const PACKAGE = 'com.sega.pjsekai';

const OFFSETS = {
    TMP_Text_set_text:                0xA8E8E4C,
    TalkWindow_SetWordsInfo:          0x62687FC,
    ScenarioPlayer_SnippetActionTalk: 0x62533C4,  // 协程工厂；写剧情上下文
    ScenarioJumper_SnippetActionTalk: 0x6248418,  // 日志跳转旁路
    CustomTextMesh_SetWordingText:    0x4F2E9EC,  // 6.6.0 runtime（Il2CppDumper）；impl 0x4F2B408 无 hit
    CustomTextMesh_UpdateWordingText: 0x4F2E8D0,  // 6.6.0 runtime；impl 0x4F2B2EC 无 hit
    CustomTextMesh_SetWordingText_impl: 0x4F2B408,
    CustomTextMesh_UpdateWordingText_impl: 0x4F2B2EC,
    CustomTextMesh_SetText:           0x4F27530,  // Sekai_UI_CustomTextMesh_SetText（6.6.0 未迁）
    CustomTextMesh_SetText_slot:      0x4F2B590,  // ICustomText.SetText slot — vtable +0x558 tail-call
    CustomText_SetText_slot:          0x4F2B1B4,  // CustomText.SetText slot（legacy Unity Text）
    CustomText_SetWordingText:        0x4F2B02C,  // CustomText.SetWordingText(string key)
    WordingManager_Get:               0x602B9FC,  // 6.6.0 runtime（methodPointer）；baseline 有 hit
    WordingManager_Get_wrapper:       0x602B8C0,  // 静态包装器（invoke + BR X4）
    WordingManager_GetImpl:           0x60282AC,  // 查表实现体（6.6.0 热路径不经此入口）
    WordingManager_GetFormat:         0x60327A4,  // 6.6.0 runtime（Dumper）；impl 0x6032710
    WordingManager_GetFormat_impl:    0x6032710,
    FontAssetManager_SetupBuiltinFontAsset: 0x6105F88,
    FontAssetManager_ClearFallbackFontAsset: 0x6105B7C,  // 清空 TMP_FontAsset.fallbackFontAssetTable
    ScenarioPlayer_AttachSceneData:       0x624F8B8,  // 6.6.0 runtime（Dumper）；0x624F814 非 AttachSceneData
    ScenarioPlayer_AttachSceneData_body:  0x624F9CC,  // 薄桩 tail 后实现体（诊断用）
    ScreenLayerScenario_OnFinishLoadScenario: 0x63E7170,
};

// FontAssetManager @ 6.5.5（IDA SetupBuiltinFontAsset 反汇编；6.6.0 字段布局待复测）
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

// ScenarioPlayer / ScenarioSceneData（6.6.0 dump.cs 与 6.5.5 一致）
const SCENARIO_PLAYER_SCENE = 0x1B0;
const SCENARIO_PLAYER_SEQUENCE_ID = 0x1B8;
const SCENARIO_PLAYER_BOOKMARK_SEQ = 0x380;
const SCENARIO_SCENE_ID = 0x18;
const SCENARIO_SCENE_SNIPPETS = 0x58;
const SCENARIO_SCENE_TALK_DATA = 0x60; // ScenarioSnippetTalk[]（JSON 称 TalkData）
const SCENARIO_SNIPPET_TALK_NAME = 0x18; // WindowDisplayName
const SCENARIO_SNIPPET_TALK_BODY = 0x20;
const SCENARIO_PLAYER_ATTACH_SCENE_DATA = 0x624F8B8;
const SCREEN_LAYER_ON_FINISH_LOAD_SCENARIO = 0x63E7170;
const BUNDLE_ELEMENT_LOADED_RESOURCE = 0x20;
const SCENARIO_SNIPPET_INDEX = 0x10;
const SCENARIO_SNIPPET_ACTION = 0x14;
const SCENARIO_SNIPPET_REF_INDEX = 0x1C;
const SCENARIO_ACTION_TALK = 1;
const IL2CPP_ARRAY_MAX_LENGTH = 0x18;
const IL2CPP_ARRAY_VECTOR = 0x20;