// Hook offsets — IDA function entry (see notes/ida-verification.md)
'use strict';

const MODULE = 'libil2cpp.so';
const PACKAGE = 'com.sega.pjsekai';

const OFFSETS = {
    TMP_Text_set_text:                0xA8D1B98,
    TalkWindow_SetWordsInfo:          0x6264FD8,
    CustomTextMesh_SetWordingText:    0x4F2B408,
    CustomTextMesh_UpdateWordingText: 0x4F2B2EC,
    CustomTextMesh_SetText:           0x4F27530,  // CustomTextMesh.SetText（IDA 入口）
    CustomTextMesh_SetText_slot:      0x4F2B590,  // ICustomText.SetText slot — UpdateWordingText tail-call 目标
    WordingManager_Get:               0x60241BC,  // 静态包装器（tail-call，Frida onLeave 不可靠）
    WordingManager_GetImpl:           0x60282AC,  // Get(string key) 实现体
    WordingManager_GetFormat:         0x602F054,  // GetFormat(key, args)
};