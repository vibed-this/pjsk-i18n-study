// Hook offsets — IDA function entry (see notes/ida-verification.md)
'use strict';

const MODULE = 'libil2cpp.so';
const PACKAGE = 'com.sega.pjsekai';

const OFFSETS = {
    TMP_Text_set_text:                0xA8D1B98,
    TalkWindow_SetWordsInfo:          0x6264FD8,
    CustomTextMesh_SetWordingText:    0x4F2B408,
    CustomTextMesh_UpdateWordingText: 0x4F2B2EC,
    CustomTextMesh_SetText:           0x4F27530,
    WordingManager_Get:               0x60241BC,
};