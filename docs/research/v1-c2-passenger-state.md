# Dark Chronicle: reading and writing the passenger (party, HP, gilda, DRY, weapon)

## What this covers

Where Dark Chronicle (ChronicleTwo, DC2) keeps the state a v1 passenger record needs, how to read it and write it at a frame-end checkpoint without leaving the game's caches stale, and proposed bodies for `C2ExportPassenger` and `C2ImportPassenger`. It covers the active character (Max, Monica, Monica's monster form, the Ridepod), per-character HP and max HP, the status bits (`CHARA_STATUS_DRY` and the rest), gilda, equipped and carried weapons, the inventory board, the state that must stay dungeon-local, and the caches a write must refresh.

Builds on `ixion:docs/research/c2-save.md` (save image and offsets), `c2-characters.md` (roster, switching, monster form) and `c2-dungeons.md`. Those facts are not repeated here except where the passenger needs them.

Sources: chronicletwo `ps2/src` and `ps2/include` (retail units, the reference), chronicletwo `port/src` (PC overrides), the Hop v0 DC2 plugin on the hop worktree (`port/src/ixion_plugin.cpp`, `port/src/mglib.cpp`), `ixion:docs/HOP-V0.md` (unverified: not present in this checkout), and `ixion:docs/DESIGN.md` section 4.3. Nothing was built or run. Offsets marked "computed" come from member sizes and are relative to the start of `CSaveData`. Sizes marked "asserted" are checked by a static assert in the source. Inference is labelled.

## Key facts

### Active character and roster

- `USER_CHARA` ids: 0 Max, 1 Monica, 2 Ridepod, 3 the monster form Monica transforms into. `chronicletwo:ps2/include/userdata.hpp:20-26`.
- The played character is `CUserDataManager::active_chr_no` (s16, a `USER_CHARA`). Computed `CSaveData` offset: `user_data` is at 0x1D2A0 (`chronicletwo:ps2/include/savedata.hpp:234-235`), and `active_chr_no` is at +0x44D96, so 0x62036 (`chronicletwo:ps2/include/userdata.hpp:1165`).
- `SetActiveChrNo` writes `active_chr_no` and then calls `CBattleCharaInfo::SetChrNo` on the battle view. `chronicletwo:ps2/src/userdata.cpp:3409-3416`.
- Party membership is a bitfield. `party_member` (u16, computed 0x62030) and `chara_change` (u16, computed 0x62032) use bit `1 << USER_CHARA` (`JoinPartyMember` does `party_member |= 1 << chara_no`, `chronicletwo:ps2/src/userdata.cpp:3010-3016`). This resolves the open item in c2-save.md about the bit mapping. The monster bit is added to `GetNowPartyMember()` whenever the Badge Box (`ITEM_ID_BADGE_BOX` 0x134) is in the bag (`chronicletwo:ps2/src/userdata.cpp:3026-3032`).
- Dungeon ride pairs (`ChangeSetUnit`): Max and Monica (partner, L3); Max and Ridepod, Monica and monster (ride, R3). `chronicletwo:ps2/src/dng_main.cpp:3039-3068`, reached from the unit-change block at `dng_main.cpp:2296-2330`.
- Leaving a dungeon resets the ride: an active Ridepod goes back to Max, and an active monster goes back to Monica (`chronicletwo:ps2/src/dng_main.cpp:1154-1158`). A town checkpoint therefore always has `active_chr_no` in {0, 1}. Mid-dungeon it can be 2 or 3.
- Monster form: `monster_id` (s16, computed 0x62038). While the monster is active, the battle view's `hp` points at Monica's `CHARA_DATA::hp` (`chronicletwo:ps2/src/userdata.cpp:4812-4868`, the `BATTLE_CHARA_MONSTER` branch). Monica's HP pool is the monster's HP.
- `GetCharaDataPtr` returns a `CHARA_DATA` only for 0 and 1. It returns NULL for the Ridepod and the monster (`chronicletwo:ps2/src/userdata.cpp:2836-2842`).

### HP and max HP

- `CHARA_DATA` is 0x38C bytes, asserted (`chronicletwo:ps2/include/userdata.hpp:241-252`, assert at line 252) and carries `PORT_RECORD_ASSERT` (line 253). Fields: `hp` COMMON_GAGE (+0x00), `status_attr` u16 (+0x08), `defence` u16 (+0x0A), `status_time[4]` s16 (+0x0C; POWER, SLOW, STOP, STONE, `userdata.hpp:245`), `active_item[3]` (+0x2C), `equip[5]` (+0x170). Both arrays are `CGameDataUsed`, 0x6C each (8 entries, 0x2C + 8 × 0x6C = 0x38C).
- `COMMON_GAGE` is `{ float max; float now; }` (`chronicletwo:ps2/include/gamedata.hpp:487-491`, size asserted at line 543). `GetRate()` is `now / max`, or 0 if `max` is 0 (`chronicletwo:ps2/src/userdata.cpp:285-291`).
- Absolute offsets (computed): Max's `CHARA_DATA` at 0x211E8 (`hp.max` at 0x211E8, `hp.now` at 0x211EC, `status_attr` at 0x211F0), Monica's at 0x21574 (unverified: the offset of `chara_data` within `CUserDataManager` was not computed).
- Start capacities are `lifetbl = {32, 48}` (`chronicletwo:ps2/src/userdata.cpp:2766-2795`; the mapping to Max and Monica is unverified). An event sets Max's capacity to 48 later (`chronicletwo:ps2/src/userdata.cpp:6825-6826`). Capacity is save state, not a function of level. The passenger should carry `max_hp` as a value, and import should keep the destination's own max.
- `GetHp` truncates `now` with `fptosi` (`chronicletwo:ps2/src/userdata.cpp:2873-2880`). A knocked-out character has `now == 0`. Recovery code raises a KO'd human to 1.0 (`chronicletwo:ps2/src/userdata.cpp:6182-6186`), which is a precedent for a minimum of 1 after a write.
- Ridepod energy is `robo_data.hp` (ROBO_DATA +0x20; computed CSaveData 0x21920) and its absorption gauge is +0x28. `ROBO_DATA` is 0x220 bytes, asserted (`chronicletwo:ps2/include/userdata.hpp:272-308`; the assert is at line 307). The +0x20 and +0x28 offsets and the computed 0x21920 are unverified. The Ridepod's energy is not Max's HP, so a rider's record HP does not change while riding.

### Status bits and DRY

- `CHARA_STATUS_ATTR`: POISON 0x01, SLOW 0x02, CURSE 0x04, STOP 0x08, POWER 0x10, STONE 0x20, DRY 0x40, ALL 0x7F (`chronicletwo:ps2/include/userdata.hpp:44-52`).
- The bits live in `CHARA_DATA::status_attr` and nowhere else. Battle code writes through `CUserDataManager::SetCharaStatusAttirbute` and reads back `GetCharaStatusAttirbute` (`CBattleCharaInfo::SetAttr`, `chronicletwo:ps2/src/userdata.cpp:5472-5481`). There is no cached copy in the battle view.
- `GetCharaStatusAttirbutePtr` returns NULL for the Ridepod and the monster, so status writes for those ids do nothing (`chronicletwo:ps2/src/userdata.cpp:3247-3268`). `SetCharaStatusAttirbute` applies POWER's ward: adding POWER clears POISON and SLOW (`chronicletwo:ps2/src/userdata.cpp:3271-3300`).
- DRY has no gauge and no timer. It is set by `WEAPON_SPECIAL_DRY` hits with a 50% roll (`chronicletwo:ps2/src/actionchara.cpp:3071-3073`), by `ITEM_USE_FLAG_ADD_DRY` (`chronicletwo:ps2/src/userdata.cpp:5843-5845`), and cleared by `ITEM_USE_FLAG_CURE_DRY` (`chronicletwo:ps2/src/userdata.cpp:5867-5869`). The eating references (`chronicletwo:ps2/src/menucls1.cpp:1112`, `:1165`) are DRY checks that gate eating, not clears; any clear by eating is unverified. DRY is not in `status_time[]`. `CheckBadStatus` counts it as a bad status (`chronicletwo:ps2/src/userdata.cpp:5880-5887`).
- STOP and STONE block changing character (`CheckEnableCharaChange`, `chronicletwo:ps2/src/userdata.cpp:3053-3135`; reason bits at `chronicletwo:ps2/include/userdata.hpp:82-86`). A passenger whose active character is stopped or petrified cannot be switched to by the game's own rules.

### Gilda

- `int money` at CUserDataManager +0x44D9C, computed CSaveData 0x6203C (`chronicletwo:ps2/include/userdata.hpp:1168`). It is a signed 32-bit int. The cap is 999999.
- The only writes are `AddMoney` (clamps to 0..999999, `chronicletwo:ps2/src/userdata.cpp:4662-4673`) and the new-game reset (`chronicletwo:ps2/src/userdata.cpp:2776`). Every reader takes the int (`chronicletwo:ps2/src/event_func.cpp:7465`, `chronicletwo:ps2/src/menushop.cpp:485`, `chronicletwo:ps2/src/menusys.cpp:6729`). DC2 has no 16-bit view of gilda. The width caution in `ixion:docs/DESIGN.md` 4.3 is about Dark Cloud; it does not apply to DC2 gilda.

### Weapons

- `WEAPON_USED` is 0x5C bytes (computed; not asserted). Fields: `whp` COMMON_GAGE, the durability gauge (+0x00); `abs` COMMON_GAGE, the absorption gauge (+0x08; the weapon levels up when it fills); `level` s16 (+0x10, up to 99); `status[2]` s16 (+0x12; `[0]` is `WEAPON_STAT_ATTACK`, `[1]` is durability, `chronicletwo:ps2/include/gamedata.hpp:35-38`); `attribute[8]` s16 (+0x16; the first four are elemental strengths and the highest is the element); `special` u32 (+0x28); `fusion_point` s16 (+0x2C, synthesis points up to 999, 9999 for a fishing rod); `name[0x20]` (+0x33). `chronicletwo:ps2/include/gamedata.hpp:580-594`.
- `CGameDataUsed` is 0x6C bytes, asserted (`chronicletwo:ps2/include/gamedata.hpp:1324`). Fields: `used_type` s16 (+0), `item_no` s16 (+2), `item_type` s8 (+4), `rename_flag` s8 (+5), and a union `data` at +0x10 (`chronicletwo:ps2/include/gamedata.hpp:700-714`). The weapon is `data.weapon`. `GetLevel()` returns `data.weapon.level` for weapons (`chronicletwo:ps2/src/userdata.cpp:493-503`).
- `GetActiveElem()` returns the index of the largest of `attribute[0..3]`, with the first index winning ties (`chronicletwo:ps2/src/userdata.cpp:1662-1679`). The armband family (`ITEM_DATA_MONICA_MAGIC`, Monica's sub slot) reads `attribute[elem]` as its effect power (`chronicletwo:ps2/src/userdata.cpp:975-990`).
- The battle attack is `status[0]`, multiplied by 1.5 under POWER (`CBattleCharaInfo::RefreshParamater`, `chronicletwo:ps2/src/userdata.cpp:4972-5020`). Lamb's Sword (`ITEM_ID_LAMBS_SWORD` 0x38, `chronicletwo:ps2/include/gamedata.hpp:75`) has its attack halved or raised by time band (`GetStatusParam(short*, float)`, `chronicletwo:ps2/src/userdata.cpp:1561-1571`). An export should use the base `status[0]`, not the time-modified value.
- Equipped weapons are not referenced by index. `CHARA_DATA::equip[5]` holds full `CGameDataUsed` copies, indexed by `CHARA_EQUIP_SLOT`: 0 melee (Max's wrench, hammer or rod; Monica's sword), 1 sub (Max's gun; Monica's armband), 2 head, 3 feet, 4 clothes (`chronicletwo:ps2/include/userdata.hpp:228-236`; slots 0 and 1 verified, slots 2 to 4 unverified). The battle view keeps a raw pointer to the same array (`CBattleCharaInfo::equip`, `chronicletwo:ps2/include/userdata.hpp:2202-2230`).
- Equip moves items. `MenuDataSwap` (`chronicletwo:ps2/src/menusys.cpp:3158`) moves items between the hand, the bag and the equip slots; its gift-box branch shows the source being consumed with `DeleteNum`. Whether an equipped weapon also stays counted in the bag was not fully traced. Inference: no, so the bag and `equip[]` never both hold it. Verify with a runtime count before import relies on it.
- `CUserDataManager::SetChrEquip(chara, CGameDataUsed *item)` (`chronicletwo:ps2/src/userdata.cpp:3935`) exchanges the item with the owner's slot through `GameDataSwap` (`chronicletwo:ps2/src/userdata.cpp:369-...`). `GameDataSwap` copies the two structs into each other. The displaced weapon ends up in the struct the caller passed, so the caller must put it back into the bag.
- `CGameDataUsed::CopyDataWeapon(item_no)` is the fresh-weapon initialiser (`chronicletwo:ps2/src/userdata.cpp:1976-2014`). It sets `level = 0`, `whp` and `abs.max` from the item record, `status` and `attribute` from the record, `fusion_point` from `initial_fusion_point`, and the name from the item message.
- The melee's `model_no` chooses the body file (`c01_base<N>` for Max, `c02_base<N>` for Monica; `chronicletwo:ps2/src/userdata.cpp:1710-1750`, from c2-characters.md). A melee change therefore needs a unit rebuild, not only a stat refresh.

### Inventory

- `used_data[150]` at CUserDataManager +0, computed CSaveData 0x1D2A0 (`chronicletwo:ps2/include/userdata.hpp:1152`). The main board is 0x8A (138) slots, or 0x90 (144) when `SAVE_FLAG_ITEM_BOARD_EXPANDED` (0xFE) is set. The overflow is 12 or 6 slots. `GetItemBoardMaxNum(ITEM_BOARD_ALL)` is 150 either way (`chronicletwo:ps2/src/userdata.cpp:3379-3410`; flag at `chronicletwo:ps2/include/savedata.hpp:123`).
- A count: `CGameDataUsed::GetNum()` (`chronicletwo:ps2/src/userdata.cpp:546`). For the ITEM family the count is `ITEM_USED::num` (s16 at +0x10 of the union, `chronicletwo:ps2/include/gamedata.hpp:550-554`).
- `CUserDataManager::GetItem(item_no, count)` (`chronicletwo:ps2/src/userdata.cpp:4318-4340`) is not a plain add. Its helper `GetItemNotOver` special-cases `ITEM_ID_CORE` (it fits ridepod parts and joins the Ridepod, `chronicletwo:ps2/src/userdata.cpp:4342-4358`) and `ITEM_ID_MAP` (it takes `&GetMainScene()->battle_area` for every item before its test, and for `ITEM_ID_MAP` sets the minimap reveal, `chronicletwo:ps2/src/userdata.cpp:4360-4370`). An import that uses `GetItem` must exclude those ids.
- Item families are `ITEM_DATA_*` (`chronicletwo:ps2/include/gamedata.hpp:139-180`). Attribute bits are `ITEM_ATTRIBUTE_*` (`chronicletwo:ps2/include/gamedata.hpp:182-190`, including `ITEM_ATTRIBUTE_UNIQUE` 0x40).

### Dungeon-only state (stays local)

- `CSaveDataDungeon` (`save_dungeon`, computed CSaveData 0x1C5B4, 0xCE4 bytes) holds floor progress and floor flags. It is never part of a passenger (c2-dungeons.md, c2-save.md).
- `DNG_BATTLE_AREA` (`BattleAreaScene`) holds the floor status, the seal bits, the minimap reveal and `battle_clear` (`chronicletwo:ps2/include/scenesnd.hpp:149-180`).
- Dungeon-session pointers `DngSaveData`, `DngUserData` and `DngSaveDataDungeon` are set at dungeon init (`chronicletwo:ps2/src/dng_main.cpp:116`, `:335-341`). They point into the live save, so they stay valid across writes.
- The actor `MainChara__2`, its scene slots, the throw and lock-on state, and the battle view's magic-sword charge state (`magic_sword_elem`, `magic_sword_num`, `magic_sword_pow[7]`, `chronicletwo:ps2/include/userdata.hpp:2202-2230`) are all transient.

### Where the live save lives

- `SaveData` is a static `CSaveData` object (`chronicletwo:ps2/src/mainloop.cpp:2157`). `GetSaveData()` returns `ActiveSaveData`, a static pointer set to `&SaveData` at boot (`chronicletwo:ps2/src/mainloop.cpp:218`, `:329-331`, `:484`). `GetUserDataMan()` returns `&GetSaveData()->user_data` (`chronicletwo:ps2/src/userdata.cpp:258-261`).
- `CSaveData` is 0x65930 bytes, asserted (`chronicletwo:ps2/include/savedata.hpp:504`). `CUserDataManager` is 0x457A0 bytes, asserted (`chronicletwo:ps2/include/userdata.hpp:2180`).
- The passenger types are plain data. `CHARA_DATA`, `CGameDataUsed` and `WEAPON_USED` hold only scalars, char arrays and COMMON_GAGE floats, with no pointers. `CHARA_DATA` is pinned by `PORT_RECORD_ASSERT`. `CGameDataUsed` has only the static assert. A `memcpy` of these records is safe in-process. `USER_PICTURE_INFO` (`char *`) lives in `invent_data`, which the passenger does not touch.
- Each game module keeps its own copy of these globals (ixion ABI, `ixion:docs/HOP-V0.md`). The host cannot read DC2 state directly. Export and import must be functions inside the DC2 module.

### Frame-end checkpoint

- `mgEndFrame` (`chronicletwo:port/src/mglib.cpp:1273`) is the frame end. It is also called from the menu screen grab (`chronicletwo:port/src/menudraw.cpp:129`) and from the developer-menu path (`chronicletwo:port/src/mainloop.cpp:292`). So it is not only the idle point of the logic loop. A checkpoint can fire while a menu owns `MenuUserParam` pointers.
- Hop branch: the checkpoint is `EmbedCheckpoint(kEmbedFrameEnd)` after present and the buffer flip (hop worktree `port/src/mglib.cpp:1367-1371`; unverified, since `EmbedCheckpoint` does not appear in the ChronicleTwo `mglib.cpp`). The main loop's per-frame end is `mgEndFrame` at `chronicletwo:port/src/mainloop.cpp:339`.
- The hop plugin's inspect reports `chara->chara_type` as the character (hop worktree `port/src/ixion_plugin.cpp`, `PluginInspect`). For the monster body, `chara_type` is `ACTION_CHARA_MAX` (c2-characters.md; unverified), so the receipt cannot tell Monica's monster form apart. A passenger must use `active_chr_no`, not `chara_type`.
- The loop ids are `LOOP_EDIT` (town and Georama editing) and `LOOP_DUNGEON` (`chronicletwo:ps2/include/mainloop.hpp:32-42`). Town runs in `LOOP_EDIT`.

### Caches that a write must refresh

- `BattleParamater`, returned by `GetBattleCharaInfo()` (`chronicletwo:ps2/src/userdata.cpp:5811-5813`). Its pointers (`hp`, `equip`, `active_item`, `chara_data.human`) remain valid because they point into the live save. Its cached values do not: `disp_hp`, `disp_hp_max`, `prev_hp`, `prev_hp_max` (the HP bar animates toward `hp->now`), `defence`, `weapon_param[2]` (copied out of the weapons), `robo_hp_drain`, `monster_hp_drain`, `now_npc`. `SetChrNo` (`chronicletwo:ps2/src/userdata.cpp:4812-4868`) resets the display values and calls `RefreshParamater()`.
- `RefreshParamater` (`chronicletwo:ps2/src/userdata.cpp:4972-5060`) takes `GetMainScene()` into `scene` (line 4987) and reads `scene->time` (lines 5007 and 5069); no null check was seen on that path. It must run with a live scene.
- Menu state: `MenuActiveSaveData` (`chronicletwo:ps2/src/menumain.cpp:425`), the `user_data` and `chara[]` pointers of `MenuUserParam` (`chronicletwo:ps2/include/menumain.hpp:211`, `chronicletwo:ps2/include/menusys.hpp:923`), `MenuArg.user_data` set from `DngUserData` at menu open (`chronicletwo:ps2/src/dng_main.cpp:430-431`), and `CMenuItemInfo` item pointers into `chara->equip[]` (`chronicletwo:ps2/src/menusys.cpp:5586`, `:7666-7703`). A write while a menu is open leaves these stale. (The menu line references in this bullet are unverified.)
- The visible unit: `SetupMainUnit` builds the body, weapons, clothing and action script (`chronicletwo:ps2/src/charasetup.cpp:140-367`). The sound bank comes from `GetCharacterSnd` (`chronicletwo:ps2/src/charasetup.cpp:108-138`). The active icon comes from `CopyActiveIconTexture`. The dungeon's own build call is `SetupMainUnit(BuffReadData, &BuffCharacter, BaseCharacter, 16, DngMainScene, DngUserData, active, 0)` (`chronicletwo:ps2/src/dng_main.cpp:639-643`).
- The event path `_DNG_SETUP_MAIN_UNIT` (`chronicletwo:ps2/src/event_func.cpp:18391-18460`) is the in-place swap template. It returns early when `chara_no == active_chr_no` (`:18414-18416`). It first deletes texture blocks and effect scripts (`:18418-18427`), then rebuilds, reloads the icon (`:18439`), reloads the sound bank with `sndLoadSound` (`:18443-18458`; bank 3 human, 1 Ridepod, 0 monster; bank indices unverified), and sets the active id again (`:18460`).

## How it works

### Export (read)

1. `ud = GetUserDataMan()`. The active human is Max or Monica. A Ridepod rides Max, and a monster is Monica's form, so the human is Monica when `active_chr_no` is 1 or 3, and Max otherwise.
2. From the human's `CHARA_DATA`: HP ratio and max (`GetRate()`, `hp.max`), `status_attr & CHARA_STATUS_ALL`, and the DRY bit as the thirst mapping.
3. Gilda: `ud->money`.
4. Weapons: `equip[CHARA_EQUIP_MELEE]` and `equip[CHARA_EQUIP_SUB]`, copied only when `used_type == USED_ITEM_TYPE_WEAPON`. Level, attack (`status[0]`), `attribute[0..3]`, durability and absorption ratios, fusion points.
5. Items: walk `used_data[0 .. GetItemBoardMaxNum(ITEM_BOARD_ALL) - 1]` and keep carriable ITEM-family entries with their counts, up to 16.

### Import (write)

Import is a live write into the parked game's globals, and it must run on the game's own fiber at a safe point. The steps are ordered so that nothing is written until every check has passed.

1. Validate the record: `size`, `version`, `home_game`, and ranges. v1 accepts only `home_game == DARK_CHRONICLE`. Cross-game weapon and item ids need a mapping table that this note does not define.
2. Check the destination's human is in the party (`party_member` bit). Refuse otherwise; the opening event owns joining.
3. Plan: check bag room for every item and for any displaced weapon. A conservative count is enough, since a refusal is safe and a silent loss is not.
4. Gilda: clamp to 0..999999 and store. The excess (`in->gilda - 999999`, when positive) is "held" and is reported by the host, not written.
5. HP: `now = clamp(ratio) × this world's max`. Raise a positive value to at least 1. A zero ratio stays knocked out. A crossing with no living member is refused by the host, not here.
6. Status: keep only DRY, derived from `thirst_ratio < 0.10`. Zero `status_time[0..3]`. The DESIGN threshold is a proposal (DESIGN 4.3, playtest value).
7. Weapons: build a `CGameDataUsed` with `CopyDataWeapon`, overwrite level, attack, attributes, gauges and fusion, then call `SetChrEquip(human, &incoming)`. The displaced weapon ends up in `incoming`, so bag it. `SetChrEquip` picks the slot from the item's type (`IsItemtypeWhoisEquip`, `chronicletwo:ps2/src/userdata.cpp:3935-3960`), not from the record's `kind`, and returns 0 when the owner or slot does not match. Skip and log a failure. The plan count in step 3 uses the array index as the slot, so a record whose `kind` disagrees with the item type is not counted correctly.
8. Items: call `GetItem(item_id, count)` for the carriable families only (see `C2IsCarriableItem`), which excludes `ITEM_ID_CORE` and `ITEM_ID_MAP`.
9. Party bits: step 2 already requires the party bit, so no join call is made. `EnableCharaChange(human)` lets the change gate allow a later switch.
10. `SetActiveChrNo(human)`, which re-points the battle view. Then `SetChrNo(human)` to reset the display values. If the visible body differs from the record, run the in-place unit rebuild (`C2RefreshVisibleUnit`).
11. Return `IXION_PASSENGER_OK`. Excess gilda and any dropped weapons or items are logged by the module; the host recomputes the excess from the record if it needs the number.

### Caches after a write

| Cache | Holds | Refresh after import |
|---|---|---|
| `BattleParamater` (`CBattleCharaInfo`) | HP display values, weapon params, `defence`, pointers | `SetActiveChrNo` then `SetChrNo(human)` (re-runs `RefreshParamater`) |
| Visible unit (models, weapons, script) | body file from melee `model_no`, sub, clothing | `SetupMainUnit` plus the event's texture and effect cleanup (`event_func.cpp:18418-18427`) |
| Sound bank | `GetCharacterSnd` file for the human | `GetCharacterSnd` and `sndLoadSound` on bank 3 (`event_func.cpp:18443-18458`) |
| Menu pointers | `MenuUserParam`, `CMenuItemInfo` item pointers | none; the import must not run while a menu is open |

## Proposed Ixion code

These are proposals for a new file, `port/src/ixion_passenger.cpp` in the DC2 port, plus one new header shared through the ABI. Names follow the retail identifiers. Nothing is built.

### Shared record (plain C, fixed width)

```c
/* ixion/include/ixion_passenger.h (new). Plain C; both modules and the host include it. */
#define IXION_PASSENGER_VERSION        1u
#define IXION_PASSENGER_MAX_ITEMS      16u
#define IXION_PASSENGER_WEAPON_SLOTS   2u   /* kind 0 melee, kind 1 sub: CHARA_EQUIP_SLOT */

enum {
    IXION_PASSENGER_OK = 0,
    IXION_PASSENGER_ERR_ARG = 1,
    IXION_PASSENGER_ERR_NOT_READY = 2,   /* not at a safe point; retry next frame */
    IXION_PASSENGER_ERR_REFUSED = 3,     /* destination rule refused it (not joined, other game) */
    IXION_PASSENGER_ERR_NO_ROOM = 4,     /* bag or equip swap would lose an item */
};

typedef struct IxionPassengerItem {
    int32_t item_id;   /* DC2 item number (ITEM_ID_*) */
    int32_t count;
} IxionPassengerItem;

typedef struct IxionPassengerWeapon {
    uint32_t kind;             /* CHARA_EQUIP_SLOT: 0 melee, 1 sub */
    int32_t  item_id;          /* 0 = no weapon in this slot */
    int32_t  level;            /* WEAPON_USED::level, 0..99 */
    int32_t  attack;           /* WEAPON_USED::status[0], base value (no POWER, no time band) */
    int32_t  elements[4];      /* WEAPON_USED::attribute[0..3] */
    float    durability;       /* whp.now / whp.max, 0..1 */
    float    absorb;           /* abs.now / abs.max, 0..1 */
    int32_t  fusion_point;     /* WEAPON_USED::fusion_point */
} IxionPassengerWeapon;

typedef struct IxionPassengerV1 {
    uint32_t size;             /* sizeof(IxionPassengerV1), set by the caller */
    uint32_t version;          /* IXION_PASSENGER_VERSION */
    uint32_t home_game;        /* IXION_GAME_DARK_CHRONICLE */
    int32_t  character;        /* the human whose record this is: 0 Max, 1 Monica */
    int32_t  form;             /* informational: active USER_CHARA at export (0..3) */
    float    hp_ratio;         /* human CHARA_DATA::hp now/max, 0..1; 0 = knocked out */
    float    max_hp;           /* CHARA_DATA::hp.max in the home game */
    int32_t  gilda;            /* money, 0..999999 */
    float    thirst_ratio;     /* proposal: 0.05 when DRY, else 1.0 */
    uint32_t status;           /* CHARA_STATUS_ATTR bits, masked with CHARA_STATUS_ALL */
    IxionPassengerWeapon weapon[IXION_PASSENGER_WEAPON_SLOTS];
    uint32_t item_count;       /* <= IXION_PASSENGER_MAX_ITEMS */
    IxionPassengerItem items[IXION_PASSENGER_MAX_ITEMS];
} IxionPassengerV1;
```

The brief asked for a single `weapon{...}`. Max carries both a melee and a gun, and the design's role crosswalk maps both, so the record holds two slots. A host that wants one weapon reads `weapon[0]`.

### Export

```cpp
/* Read-only. Safe while the game is parked, and on the game's fiber at any checkpoint.
   Touches: GetUserDataMan (userdata.cpp:258), active_chr_no (userdata.hpp:1165),
   GetCharaDataPtr (userdata.cpp:2836), COMMON_GAGE::GetRate (userdata.cpp:285),
   money (userdata.hpp:1168), used_data (userdata.hpp:1152), GetItemBoardMaxNum (userdata.cpp:3387). */
int C2ExportPassenger(IxionPassengerV1 *out) {
    if (out == nullptr || out->size != sizeof(IxionPassengerV1)) return IXION_PASSENGER_ERR_ARG;
    CUserDataManager *ud = GetUserDataMan();
    if (ud == nullptr) return IXION_PASSENGER_ERR_NOT_READY;

    const int active = ud->active_chr_no;
    const int human = (active == USER_CHARA_MONICA || active == USER_CHARA_MONSTER)
                          ? USER_CHARA_MONICA : USER_CHARA_MAX;
    CHARA_DATA *c = ud->GetCharaDataPtr(human);
    if (c == nullptr) return IXION_PASSENGER_ERR_NOT_READY;

    memset(out, 0, sizeof *out);
    out->size = sizeof *out;
    out->version = IXION_PASSENGER_VERSION;
    out->home_game = IXION_GAME_DARK_CHRONICLE;
    out->character = human;
    out->form = active;
    out->max_hp = c->hp.max;
    out->hp_ratio = c->hp.GetRate();
    out->gilda = ud->money;
    out->status = c->status_attr & CHARA_STATUS_ALL;
    out->thirst_ratio = (c->status_attr & CHARA_STATUS_DRY) ? 0.05f : 1.0f;

    C2PackWeapon(&c->equip[CHARA_EQUIP_MELEE], CHARA_EQUIP_MELEE, &out->weapon[0]);
    C2PackWeapon(&c->equip[CHARA_EQUIP_SUB], CHARA_EQUIP_SUB, &out->weapon[1]);

    const int bag = ud->GetItemBoardMaxNum(ITEM_BOARD_ALL);   /* 150 */
    for (int i = 0; i < bag && out->item_count < IXION_PASSENGER_MAX_ITEMS; i++) {
        CGameDataUsed *g = &ud->used_data[i];
        if (g->used_type != USED_ITEM_TYPE_ITEM) continue;
        if (!C2IsCarriableItem(g->item_no, g->item_type)) continue;
        out->items[out->item_count].item_id = g->item_no;
        out->items[out->item_count].count = g->GetNum();     /* userdata.cpp:546 */
        out->item_count++;
    }
    return IXION_PASSENGER_OK;
}

/* Fills one slot. Leaves item_id 0 when the slot holds no weapon.
   Touches: data.weapon (gamedata.hpp:580-594), COMMON_GAGE::GetRate. */
static void C2PackWeapon(CGameDataUsed *g, int kind, IxionPassengerWeapon *w) {
    w->kind = (uint32_t) kind;
    if (g->used_type != USED_ITEM_TYPE_WEAPON || g->item_no <= 0) return;
    const WEAPON_USED &x = g->data.weapon;
    w->item_id = g->item_no;
    w->level = x.level;
    w->attack = x.status[WEAPON_STAT_ATTACK];
    for (int k = 0; k < 4; k++) w->elements[k] = x.attribute[k];
    w->durability = x.whp.GetRate();
    w->absorb = x.abs.GetRate();
    w->fusion_point = x.fusion_point;
}

/* Carried set for v1: consumables, throwing items, powders and amulets. Keys, quest and story
   items, Georama materials, the aquarium, fish, the Badge Box and unique items stay local
   (DESIGN 4.3; ITEM_DATA_* at gamedata.hpp:139-180; ITEM_ATTRIBUTE_UNIQUE at gamedata.hpp:188). */
static bool C2IsCarriableItem(int item_no, int item_type) {
    switch (item_type) {
        case ITEM_DATA_RECOVERY:
        case ITEM_DATA_THROWING:
        case ITEM_DATA_POWDER:
        case ITEM_DATA_AMULET:
            break;
        default:
            return false;
    }
    CDataCommon *common = GetCommonItemData(item_no);
    return common != nullptr && (common->attribute & ITEM_ATTRIBUTE_UNIQUE) == 0;
}
```

### Import

```cpp
/* Writes. Call only from C2ServicePassengerMailbox, on the game's fiber, at a safe point.
   Touches: money (AddMoney clamp rule, userdata.cpp:4662), hp (COMMON_GAGE), status_attr and
   status_time (userdata.hpp:241-249), SetChrEquip (userdata.cpp:3935), CopyDataWeapon
   (userdata.cpp:1976), GetItem (userdata.cpp:4318), JoinPartyMember (userdata.cpp:3010),
   EnableCharaChange, SetActiveChrNo (userdata.cpp:3409), SetChrNo (userdata.cpp:4812). */
int C2ImportPassenger(const IxionPassengerV1 *in) {
    if (in == nullptr || in->size != sizeof *in || in->version != IXION_PASSENGER_VERSION)
        return IXION_PASSENGER_ERR_ARG;
    if (in->home_game != IXION_GAME_DARK_CHRONICLE) return IXION_PASSENGER_ERR_REFUSED;  /* v1: same game only */
    if (!C2SafePoint()) return IXION_PASSENGER_ERR_NOT_READY;

    CUserDataManager *ud = GetUserDataMan();
    const int human = (in->character == 1) ? USER_CHARA_MONICA : USER_CHARA_MAX;
    CHARA_DATA *c = ud->GetCharaDataPtr(human);
    if (c == nullptr) return IXION_PASSENGER_ERR_ARG;
    if ((ud->party_member & (1u << human)) == 0) return IXION_PASSENGER_ERR_REFUSED;   /* not joined */

    /* Phase 1: plan. No writes until every room check passes. */
    int needed_bag = 0;
    for (int k = 0; k < (int) IXION_PASSENGER_WEAPON_SLOTS; k++) {
        const IxionPassengerWeapon *w = &in->weapon[k];
        if (w->item_id <= 0) continue;
        if (c->equip[k].item_no > 0) needed_bag++;             /* the displaced weapon */
    }
    for (uint32_t i = 0; i < in->item_count; i++) needed_bag++;    /* conservative: one place per entry */
    if (C2BagFreeCount(ud) < needed_bag) return IXION_PASSENGER_ERR_NO_ROOM;

    /* Phase 2: write. Failures here are logged, not rolled back; phase 1 made them unlikely. */
    const int gilda = in->gilda < 0 ? 0 : (in->gilda > 999999 ? 999999 : in->gilda);
    ud->money = gilda;                                             /* same cap as AddMoney */

    float r = in->hp_ratio < 0.0f ? 0.0f : (in->hp_ratio > 1.0f ? 1.0f : in->hp_ratio);
    c->hp.now = r * c->hp.max;                                     /* this world's max */
    if (r > 0.0f && c->hp.now < 1.0f) c->hp.now = 1.0f;            /* precedent: userdata.cpp:6182-6186 */

    c->status_attr = (in->thirst_ratio < 0.10f) ? CHARA_STATUS_DRY : 0;   /* ailments cleared; proposal threshold */
    c->status_time[0] = c->status_time[1] = c->status_time[2] = c->status_time[3] = 0;

    for (int k = 0; k < (int) IXION_PASSENGER_WEAPON_SLOTS; k++) {
        /* false = CopyDataWeapon or SetChrEquip refused (item type does not fit the slot); nothing moved. */
        (void) C2ImportWeapon(ud, human, &in->weapon[k]);
    }

    for (uint32_t i = 0; i < in->item_count; i++) {
        const IxionPassengerItem *it = &in->items[i];
        if (it->count <= 0) continue;
        if (!C2IsCarriableItem(it->item_id, GetItemDataType(it->item_id))) continue;
        ud->GetItem(it->item_id, it->count);                       /* excludes CORE and MAP side effects */
    }

    ud->EnableCharaChange(human);
    ud->SetActiveChrNo(human);                                     /* re-points battle view */
    C2RefreshVisibleUnit(ud, human);                               /* only if the body changed */
    return IXION_PASSENGER_OK;
}

/* Puts a weapon into the owner's slot and bags whatever it displaced.
   Touches: CopyDataWeapon, WEAPON_USED fields (gamedata.hpp:580-594), SetChrEquip (userdata.cpp:3935). */
static bool C2ImportWeapon(CUserDataManager *ud, int human, const IxionPassengerWeapon *w) {
    if (w->item_id <= 0) return true;                              /* keep the destination's own weapon */
    CGameDataUsed incoming;
    incoming.Init();
    if (!incoming.CopyDataWeapon(w->item_id)) return false;
    WEAPON_USED &x = incoming.data.weapon;
    x.level = (short) w->level;
    x.status[WEAPON_STAT_ATTACK] = (short) w->attack;
    for (int k = 0; k < 4; k++) x.attribute[k] = (short) w->elements[k];
    x.whp.now = x.whp.max * clampf(w->durability, 0.0f, 1.0f);
    x.abs.now = x.abs.max * clampf(w->absorb, 0.0f, 1.0f);
    x.fusion_point = (short) w->fusion_point;
    if (!ud->SetChrEquip(human, &incoming)) return false;          /* incoming now holds the displaced item */
    if (incoming.item_no > 0) C2BagPut(ud, &incoming);            /* room was checked in phase 1 */
    return true;
}

/* First empty bag place, counting the whole 150-place extent. Touches: used_data (userdata.hpp:1152). */
static int C2BagFreeCount(CUserDataManager *ud) {
    int free = 0;
    const int bag = ud->GetItemBoardMaxNum(ITEM_BOARD_ALL);
    for (int i = 0; i < bag; i++)
        if (ud->used_data[i].item_no <= 0) free++;
    return free;
}

static bool C2BagPut(CUserDataManager *ud, const CGameDataUsed *src) {
    const int bag = ud->GetItemBoardMaxNum(ITEM_BOARD_ALL);
    for (int i = 0; i < bag; i++) {
        if (ud->used_data[i].item_no <= 0) {
            ud->used_data[i] = *src;
            return true;
        }
    }
    return false;
}
```

### Safe point and visible-unit refresh

```cpp
/* True only at a point where the game owns no menu and no event. Called before every write.
   Touches: GetNowLoopNo (mainloop.hpp:32-42), GetMainScene, DngStatus.mode (dng_main.cpp:2296-2338),
   MainChara__2->CheckRunEvent (dng_main.cpp:2311). The menu-open test is not yet identified. */
static bool C2SafePoint() {
    const int loop = GetNowLoopNo();
    if (loop != LOOP_DUNGEON && loop != LOOP_EDIT) return false;   /* LOOP_EDIT is town */
    if (GetMainScene() == nullptr) return false;
    if (loop == LOOP_DUNGEON) {
        if (DngStatus.mode == DNG_STATUS_MENU || DngStatus.mode == DNG_STATUS_EXIT) return false;
        if (MainChara__2 == nullptr || !MainChara__2->CheckRunEvent()) return false;
    }
    if (C2MenuIsOpen()) return false;                              /* TODO: identify the global */
    return true;
}

/* Rebuilds the visible unit only when the body or sound changed. Follows _DNG_SETUP_MAIN_UNIT
   (event_func.cpp:18391-18460) minus its early return, and the dungeon's own build call
   (dng_main.cpp:639-643). Town path not traced: see open questions. */
static void C2RefreshVisibleUnit(CUserDataManager *ud, int human) {
    CScene *scene = GetMainScene();
    if (scene == nullptr) return;
    /* 1. delete texture blocks 0x10..0x17, clear effect scripts, delete MONSTER_EFFECT_TEX_BLOCK
          (event_func.cpp:18418-18427) */
    /* 2. SetupMainUnit(BuffReadData, &BuffCharacter, BaseCharacter, 16, scene, ud, human, 0)
          (charasetup.cpp:140; dng_main.cpp:642-643) */
    /* 3. CopyActiveIconTexture(icons, human, NULL)  (event_func.cpp:18439) */
    /* 4. GetCharacterSnd(ud, human, snd_path); LoadFile(snd_path, ...);
          sndLoadSound(SND_PORT_CHARA, ..., bank 3 human | 1 ridepod | 0 monster)
          (charasetup.cpp:108; event_func.cpp:18443-18458) */
    /* 5. ud->SetActiveChrNo(human) again; GetBattleCharaInfo()->SetChrNo(human) (userdata.cpp:4812) */
}
```

### Call site and mailbox

```cpp
/* Hop-branch placement, unverified in this tree: after the hop checkpoint (hop worktree mglib.cpp:1369-1371),
   inside chronicletwo port/src/mglib.cpp mgEndFrame (line 1273). The parked and not-parked return paths were not traced. */
if (EmbedCheckpoint(kEmbedFrameEnd)) {
    PresentRebase();
}
C2ServicePassengerMailbox();

/* Mailbox state. The host sets the request while the game is parked on the root fiber; the game
   services it on its own fiber. v1 ABI work: add export and import entries to IxionApi, or a
   mailbox struct in IxionHost. Neither exists in the v0 header. */
static bool g_pending_export, g_pending_import;
static IxionPassengerV1 g_export_buf, g_import_buf;
static int g_export_rc, g_import_rc;

void C2ServicePassengerMailbox() {
    if (!g_pending_export && !g_pending_import) return;
    if (!C2SafePoint()) return;                    /* retry at the next frame end */
    if (g_pending_export) {
        g_export_rc = C2ExportPassenger(&g_export_buf);
        g_pending_export = false;
    }
    if (g_pending_import) {
        g_import_rc = C2ImportPassenger(&g_import_buf);
        g_pending_import = false;
    }
}
```

## Risks and blockers

- Live write, not a native save. The import changes the in-memory `SaveData` (`chronicletwo:ps2/src/mainloop.cpp:2157`). Any native save the player makes later in the same session writes the imported gilda, items and HP to the card. That conflicts with the design rule "Ixion never writes native saves" (DESIGN section 8) unless the import is undone or the origin is re-imported on return. Decide before enabling the write.
- Double counting. Export is non-destructive. The origin is parked and resumes with its old values. Gilda or items that the ledger already moved to the destination are still in the origin's live state. Only a frozen origin, or a return path that restores from the ledger and not from live state, avoids duplication. DESIGN section 4 says a return restores from the ledger's raw origin record, not from live state (`ixion:docs/DESIGN.md:159`); the origin side needs a debit or a restore.
- Stale menu pointers. `mgEndFrame` also fires from the menu screen grab (`chronicletwo:port/src/menudraw.cpp:129`). A mailbox serviced there would write into state that the menu has already copied (`MenuUserParam`, `CMenuItemInfo`). `C2SafePoint` must reject menu frames, and the menu-open global has not been identified.
- `GetItem` side effects. `ITEM_ID_CORE` joins the Ridepod and fits parts, and `ITEM_ID_MAP` sets the minimap reveal, after `&GetMainScene()->battle_area` is taken for every item (`chronicletwo:ps2/src/userdata.cpp:4342-4370`). The carriable filter must exclude both. Overflow behaviour when the overflow places are full is not traced (open question).
- Displaced weapon loss. `SetChrEquip` swaps and returns the displaced item in the struct the caller passed. If the bag is full, the item is lost. The phase-1 room check prevents this, but its count is conservative, not exact.
- Visible-unit rebuild cost. The in-place swap deletes texture blocks and effect scripts before rebuilding (`chronicletwo:ps2/src/event_func.cpp:18418-18427`). A rebuild that skips that cleanup can leave stale textures or effect state. A melee change also changes the body file (`model_no`), so a stats-only refresh is not enough.
- Monster receipts. `PluginInspect` reports `chara_type`, which is `ACTION_CHARA_MAX` for the monster body (c2-characters.md). The passenger uses `active_chr_no`. The receipt should be changed too, or the two will disagree in logs.
- Cross-game ids. Items and weapons use DC2 `ITEM_ID_*` numbers. A Dark Cloud origin needs a mapping table that is not in this note. v1 accepts only same-game records.
- Lamb's Sword. Its battle attack changes with the time band (`chronicletwo:ps2/src/userdata.cpp:1561-1571`). The record carries the base `status[0]`, so a passenger's time of day is the destination's.

## Open questions

- Town unit rebuild: the event path uses `EventScene`, `BaseCharacter` and `read_buffer` (`event_func.cpp:18391-18460`). A town swap would need the town scene and buffers, which were not traced. The menu's reload flag (`MENU_ETC_FLAG_CHARA_RELOAD`) consumer was not traced to the end either (c2-characters.md).
- Menu-open test: which global says a menu owns the current frame? `C2SafePoint` needs it.
- Equip and bag: does an equipped weapon also keep a bag entry? A runtime count of `used_data` before and after an equip would settle it.
- Overflow: what does `GetOverItem` do when the overflow places are full? Does the count drop silently?
- Joining: should an import of an un-joined Monica refuse, or set the party bit the way the opening does (`chronicletwo:ps2/src/title.cpp:1039-1042`)? Setting the bit without the event may skip story flags.
- Thirst: is DRY a state that should persist across a crossing at all? DESIGN 4.3 says ailments clear on crossing, and thirst is a separate rule. Playtest values for the 0.10 threshold (DESIGN open item 13).
- Ridepod: should a passenger carry the rider's Ridepod energy, or always land on the human? This note assumes the human.
- Origin debit: the export is a snapshot. Who debits the origin's gilda and items, and when? The design only says "carry".
- `CHARA_DATA::defence` and `status_time` are not in the record. Are they needed for a faithful round trip?
