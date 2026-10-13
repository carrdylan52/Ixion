# Dark Cloud: reading and writing the passenger (party, HP, gilda, water, weapon)

## What this covers

Where Dark Cloud (DC1, the Chronicle port) keeps the state that a Hop v1 passenger record needs: the leader and the party, per-member HP and max HP, the water (thirst) gauge and its per-member maximum, status ailments, gilda, the equipped weapon and its stored fields, the carried item list, and the dungeon-only state that must not cross. It then names the caches that hold copies of these values, lists the writes that are unsafe mid-dungeon, and proposes bodies for `C1ExportPassenger` and `C1ImportPassenger`, with the frame-boundary hook they must run from.

Sources: the Chronicle pin (commit 86c2b4c8, `ps2/` game units and `port/` overrides) and the Hop v0 ABI (`ixion:include/ixion_api.h`, `ixion:docs/HOP-V0.md`; both are on the hop branch and are not at the Ixion HEAD 8d7d7fc8). Pages already written are referenced, not repeated: the roster and loader (`c1-characters.md`), item and weapon tables (`c1-items-weapons.md`), monster hit bits and ailments (`c1-battle-monsters.md`), the main loop (`c1-mainloop-control.md`), and dungeon entry (`c1-dungeons.md`).

Offsets were computed from the header declarations with a layout script. The results agree with the header size assertions (`CUserStatus` 0x8B20, `CDngStatusData` 0x8C9C, `WEAPON_HAVE` 0xF8, `CSaveData` 78,272). No build or run was done. Inference is labelled as inference.

## Key facts

### Where the state lives

- There is one live copy of the party state: `CSaveData::dng_status`, a `CDngStatusData` of 0x8C9C bytes at offset 0x540C of the save image (unverified: the offset comes from the layout script, which was not re-run). chronicle:ps2/include/savedata.hpp:136; size assert chronicle:ps2/include/dngstatusdata.hpp:192; `CSaveData` size assert chronicle:ps2/include/savedata.hpp:501.
- The savedata.hpp comment at lines 133-135 says `minimap_status` sits at 0x9748 from `this`. The layout gives 0x540C + 0x433C = 0x9748, so the offsets used below are consistent with the header.
- `SaveData` is `extern CSaveData *SaveData` (chronicle:ps2/include/savedata.hpp:499). `GetDngStatus()` returns `&dng_status` (savedata.hpp:354). The port points `SaveData` at its own image, `g_save_data` (chronicle:port/src/gameloop.cpp:211, 812).
- `UserStatus` is a `CUserStatus *` global (chronicle:ps2/src/dun/gameloop.cpp:972). Only `GameInit` assigns it, to `SaveData->GetDngStatus()` (chronicle:ps2/src/dun/gameloop.cpp:1415). It is an alias of the save copy, and it is stale or NULL outside a dungeon session. Town and editor code reads `SaveData->GetDngStatus()` directly (chronicle:ps2/src/editloop.cpp:1135; chronicle:ps2/src/battlemenu.cpp:1050; the NULL guard at chronicle:ps2/src/menu_misc.cpp:1176, unverified).
- The port's `DngWeaponEquipModelBuild` checks `UserStatus != NULL` before reading it (chronicle:port/src/menu_misc.cpp:244-252). A town path that reaches for `UserStatus` gets 0 for the weapon kind, which is a silent fallback, not a crash.
- `CUserStatus` (chronicle:ps2/include/userstatus.hpp:78) and `CDngStatusData` (chronicle:ps2/include/dngstatusdata.hpp:8) hold only plain arrays, unions and nested structs. Neither has a pointer or a virtual member. Inference: the PC port compiles the same headers, so these records have the PS2 layout on the host. A `memcpy` of the passenger fields is therefore safe across the ABI, as long as the record itself uses fixed-width types.
- Town and dungeon share the same status object. There is no separate town copy (chronicle:ps2/src/battlemenu.cpp:1045-1050).

### Party and leader

- Enum `Character`: TOAN=0, XIAO=1, GORO=2, RUBY=3, UNGAGA=4, OSMOND=5 (chronicle:ps2/include/itemdata.hpp:485-491).
- The leader is `cur_chara` (s8, userstatus.hpp:86). The party size is `party_size` (s8, userstatus.hpp:87).
- Membership is the prefix `i < party_size`. The battle menu hides any ring slot with `party_size <= chara` (chronicle:ps2/src/battlemenu.cpp:2259). `GetLiveUnit` counts only `i < party_size` (chronicle:ps2/src/dngstatusdata.cpp:193). This is the only unlock mechanism found: there is no separate bitmask.
- `Initialize` sets `party_size = 1` and `cur_chara = CHARA_TOAN` (chronicle:ps2/src/dngstatusdata.cpp:887-888).
- The writers found are `_SSET_PARTY_NUM` (chronicle:ps2/src/editloop3.cpp:7368, which passes the value to the plain setter `SetPartySize` with no check at the call site; opcode 710 at editloop3.cpp:8225) and the PAL debug path (chronicle:ps2/src/battlemenu.cpp:1063-1066, and 1974-1984 behind `party_size < 6`). The event scripts that call `_SSET_PARTY_NUM` were not traced (the scripts are binary bytecode).
- `_SSKILL_GET` sets `skill_owned[c] = 1` (chronicle:ps2/src/editloop3.cpp:7411-7420). That is a skill grant, not an unlock.
- Default weapons. The broken default IDs in `defWeapon` are 257, 299, 314, 331, 347 and 363 for Toan through Osmond (chronicle:ps2/src/dngstatusdata.cpp:24). The usable default is the same ID plus one (`GetItem(GetDefaultWeaponNo(c) + 1)`, chronicle:ps2/src/battlemenu.cpp:1065; table at chronicle:ps2/src/battlemenu.cpp:117).
- Start values in `Initialize`: `max_hp` {70, 60, 100, 90, 110, 100}, `defense` {3, 1, 12, 23, 38, 46}, water 30 for everyone (chronicle:ps2/src/dngstatusdata.cpp:892-893, 904-916).
- Toan is given the dagger (ID 258) through `GetItem`, and `equipped_weapon_slot[0]` is set to 0. `GetItem`'s weapon branch places the copy in the first free row entry (inference: that is row 0 for a fresh save). The other members start at -1 (chronicle:ps2/src/dngstatusdata.cpp:909, 920-921).

### HP and max HP

- `max_hp[6]` and `hp[6]` are s16 (chronicle:ps2/include/userstatus.hpp:88-89). `hp` is documented as the current displayed life.
- The interpolated gauge is `next_hp[6]` and `life_step[6]` (s16, userstatus.hpp:129-130). `CUserStatus::Step` moves `hp` toward `next_hp` by `life_step` each frame and stops at the target (chronicle:ps2/src/dngstatusdata.cpp:701-719).
- `AddNowLife` (chronicle:ps2/src/dngstatusdata.cpp:530) and `SetNextLife` (chronicle:ps2/src/dngstatusdata.cpp:597) clear `life_step` as they write. Direct writes do not: the gameloop writes at chronicle:ps2/src/dun/gameloop.cpp:1423, 2069, 5569 and the menu at chronicle:ps2/src/menu_misc.cpp:314 set `hp` alone.
- Max HP caps. Fruit of Eden caps max HP at {170, 140, 170, 140, 180, 160}, in member order (chronicle:ps2/src/menu_misc.cpp:276-287, a local array). Gourd raises max water only while it is at most 90 (chronicle:ps2/src/menu_misc.cpp:296-301).
- Alive test: `CheckLife` reads `hp` and, while a change is in flight, `next_hp` (chronicle:ps2/src/dngstatusdata.cpp:582-592). Knock-out is ailment bit 0x02 (userstatus.hpp:30). When the leader is dead, `selectChrUnit` sets `hp` to 1 (chronicle:ps2/src/btitem.cpp:131-135).
- The dungeon HUD reads `hp` and `max_hp` every frame in `topStatusInfo` (chronicle:ps2/src/shot_freefuncs.cpp:682-696), and `HealingWater` reads them too (chronicle:ps2/src/shot_freefuncs.cpp:304-322). No HUD copy exists.

### Gilda (money)

- `union { u16 money; s16 money_signed; }` (chronicle:ps2/include/userstatus.hpp:109-112). Retail reads the unsigned view (for example chronicle:ps2/src/battlemenu.cpp:9642 and chronicle:ps2/src/shop.cpp:1868). The signed alias is used only for bit operations.
- Width and range: 16 bits, unsigned, 0 to 65535. Every writer that can overflow saturates at 0xFFFF (chronicle:ps2/src/dun/gameloop.cpp:8859-8861 for the trap; chronicle:ps2/src/shop.cpp:2771-2776; chronicle:ps2/src/battlemenu.cpp:7657-7662). This settles the open width question in `community-refs.md` for DC1.
- `SetDead` halves it: `money_signed = (u32)(u16)money_signed >> 1` (chronicle:ps2/src/dngstatusdata.cpp:751-753). It is called on the death-exit paths (chronicle:ps2/src/dun/gameloop.cpp:5462, 5663-5667; chronicle:ps2/src/btsysscript.cpp:881).
- The port's damage override takes a fifth of `UserStatus->money` on a 20 percent roll (chronicle:port/src/dun/movechara.cpp:3100-3109, inside `BtCheckDamageProc`, PORT_OVERRIDE at line 3012).

### Water (thirst)

- `water_max[6]` and `water_now[6]` are float (userstatus.hpp:101-102). The comment says the unit is ten per drop. Water maximum starts at 30 (chronicle:ps2/src/dngstatusdata.cpp:915-916).
- Interpolation fields: `drink_next[6]` and `drink_step[6]`, both s16 (userstatus.hpp:134-135). `AddDrink` (chronicle:ps2/src/dngstatusdata.cpp:493-526) first flushes an in-flight drink (`water_now = drink_next`, `drink_step = 0`). A direct write has to do the same flush.
- Drain. `CUserStatus::Step(0)` runs once per dungeon frame, called from `motionDrive` (chronicle:ps2/src/dun/gameloop.cpp:6201; `motionDrive` begins at :5783). It drains only the leader (`cur_chara`). The rate scales with `cur_georama` depth, is multiplied by 5 under `RES_LIMIT_ZONE_THIRST`, and is scaled by the flags of the dungeon copy of the weapon: 0x8 gives 0.8, 0x10 gives 2.0 (chronicle:ps2/src/dngstatusdata.cpp:634-660). At zero water it adds to `thirst_damage[c]` and costs one HP per full unit (chronicle:ps2/src/dngstatusdata.cpp:671-678).
- `DngMessMan.SetStatus_Dry` reads `water_max` and `water_now` after each step (chronicle:ps2/src/dun/gameloop.cpp:6202-6204; chronicle:ps2/src/dngmessageman.cpp:33).

### Status ailments

- `s32 ailments[6]` (userstatus.hpp:99), with the bits in the `StatusAilment` enum (userstatus.hpp:29-36): KNOCKED_OUT 0x02, FREEZE 0x04, STAMINA 0x08, POISON 0x10, CURSE 0x20, GOO 0x40. Bit 0x01 has no name. `s16 ailment_frames[6]` (userstatus.hpp:100) holds the frames left.
- `Initialize` zeroes both (chronicle:ps2/src/dngstatusdata.cpp:907-908). `GameInit` zeroes them unless `no_status_recover` is 1 (chronicle:ps2/src/dun/gameloop.cpp:1418-1427), and the exit path does the same (chronicle:ps2/src/dun/gameloop.cpp:2065-2072).

### The equipped weapon

- `WEAPON_HAVE`, size 0xF8 (chronicle:ps2/include/itemdata.hpp:686-708). Fields and offsets: `item_no` 0x00 (s16, the item ID), `level` 0x02 (s16, up to 99), `attack` 0x04, `endurance` 0x06, `speed` 0x08, `magic` 0x0A, `durability` 0x0C, `durability_f` 0x10 (float), `experience` 0x14 (s16), `best_elem` 0x16 (s8, -1 for none), `elem[5]` 0x17 (s8, fire, ice, thunder, wind, holy), `vs_monster[10]` 0x1C (char), `attach[6]` 0x28 (ATTACH_LIST, 0x20 each), `attach_kind[6]` 0xE8, `flags` 0xEE (s16), `synthesis_count` 0xF0 (s32, drawn as stars).
- The carried weapon is the row entry `chara_weapons[c][equipped_weapon_slot[c]]` (userstatus.hpp:107, 127). The slot is an s8 index into a row of 11, not a pointer. -1 means none (chronicle:ps2/src/dngstatusdata.cpp:909). Several readers index with it unguarded, for example `selectChrUnit` for any member (chronicle:ps2/src/btitem.cpp:102).
- The dungeon copy is a separate global. `WeaponHave` (chronicle:ps2/src/dun/gameloop.cpp:465) is the storage and `NowWeaponHave` points at it (chronicle:ps2/src/dun/gameloop.cpp:1063, set at 1581; extern at chronicle:ps2/include/dun/gameloop.hpp:247). `SetWeaponAttachStatus(NowWeaponHave)` rebuilds it from the row (chronicle:ps2/src/menu_dungeon.cpp:232-245), through `WeaponAllValueSet` (chronicle:ps2/src/menu_dungeon.cpp:257-330).
- In `WeaponAllValueSet`, the effective attack is (stored attack plus attachment totals) times a rate, clamped to `attack_max` (chronicle:ps2/src/menu_dungeon.cpp:257-330). Inference: the stored `attack` is the base value, and the effective value exists only in the copy. Writing the copy does nothing to the row.
- A new weapon is seeded by `WepDataListToHaveCopy` (chronicle:ps2/src/menu_draw.cpp:2875-2925). That function rolls `rand()` for the durable and fragile flags (chronicle:ps2/src/menu_draw.cpp:2917). `GetItem`'s weapon branch owns the row placement and picks the owner from a byte table, `ItemPutListTbl12_bytes[750 + id * 76]` (chronicle:ps2/src/dngstatusdata.cpp:429-455; chronicle:ps2/include/dungeonparts.hpp:338). The byte table was not cross-checked against the range function `CheckWeaponUser` (chronicle:ps2/src/dngstatusdata.cpp:264-290).
- Level changes. A broken or default weapon is reset to level 0 when it is lost (chronicle:ps2/src/weaponlevelup.cpp:877, 907). The battle menu adds the synthesis points when the player levels a weapon up (chronicle:ps2/src/battlemenu.cpp:3713).

### Inventory

- `ITEM_PACK`, size 0x1AA (chronicle:ps2/include/userstatus.hpp:53-62, stored at 0x4360 in `dng_status`, unverified). `num` is the capacity, set to 50 by `Initialize` (chronicle:ps2/src/dngstatusdata.cpp:960). `item_count` is a derived count. `quick_item_slot[3]` and `quick_item_qty[3]` are the quick-use slots. `item[103]` and `item_vol[103]` are the inventory, where -1 means empty.
- The byte-level view is `DNG_ITEM_BLOCK` (chronicle:ps2/src/dngstatusdata.cpp:869-876). Its offsets match `ITEM_PACK`: `num` at 0, quick slots at 2 and 8, `item` at 14, `item_vol` at 220.
- Item ID ranges (chronicle:ps2/include/itemdata.hpp): attachments and consumables 81 to 131; dungeon items 132 to 255 (`ITEM_DUNGEON_START` at line 230, `ITEM_DUNGEON_END` = 255 at line 344); weapons 257 to 376 (`ITEM_WEAPON_START` = 257 at line 346; `ITEM_WEAPON_END` = 377 at line 463 is the exclusive bound). An empty weapon row entry is `item_no` -1 (dngstatusdata.cpp:912), and the code tests emptiness with `< ITEM_WEAPON_START`.
- `GetItem` fills `item[i]` for i below 103, and on overflow it uses slots `num`, `num+1`, `num+2` (chronicle:ps2/src/dngstatusdata.cpp:351-394). `ItemDataToHaveCopy` rolls `rand()` for the volume (chronicle:ps2/src/menu_draw.cpp:2942-2968).
- The recount rule for `item_count` is in `ShopMenuExit`. It sums the quick-slot quantities for ids of at least 132, and adds one for each inventory slot below `num` with an id of at least 132 (chronicle:ps2/src/shop.cpp:1138-1152). The battle menu does the same count on exit, in `ExitBattleMenu` (chronicle:ps2/src/battlemenu.cpp:915-939), and also resets every inventory slot below 132 to -1 and every quick slot below 132 to empty. An import that writes ids below 132 would be erased on menu exit.
- `consumable_items[43]` (chronicle:ps2/include/userstatus.hpp:43-48, 128) holds attachments, 0x20 bytes each. It is not in the proposed record.
- Quick-slot uses left: `active_item_vol[3]` (userstatus.hpp:141).
- Icons for the quick items and the equipped weapon are copied into reserved textures from `BtItemListCashFlag` (chronicle:ps2/src/dun/gameloop.cpp:1190, read at 2288-2292 and 2311-2315; chronicle:ps2/src/menu_dungeon.cpp:2007-2054).

### Dungeon-only state

- Location: `cur_georama` (dungeon index), `cur_floor` and `prev_floor` (s8, userstatus.hpp:82-85). `floor_reached[7]` (userstatus.hpp:97) is save-wide progress, not passenger state.
- Keys: `CDngStatusData::LostGateKey` removes DRAN's crest, the shiny stone, the red berry, the hook, the king's slate, the gun powder, the clock hands, the pointy chestnut, the black knight crest, and every ID from 216 to 222 (`ITEM_BONE_KEY` through `ITEM_SILVER_KEY`, chronicle:ps2/include/itemdata.hpp:307-313; chronicle:ps2/src/dngstatusdata.cpp:140-184). It runs on dungeon exit (chronicle:ps2/src/dun/gameloop.cpp:2063) and when a random dungeon is rebuilt (chronicle:ps2/src/dun/gameloop.cpp:6324). The gate-key stack is a separate 32-entry array, cleared at entry (chronicle:ps2/src/collisiondata.cpp:752-756).
- Story item `ITEM_WORLDMAP` (238) sets `special_flag_238` when picked up (chronicle:ps2/src/dngstatusdata.cpp:353-355; chronicle:ps2/include/itemdata.hpp:327). Inference: it is story-bound and should stay local.
- Event flags: `event_flags[50]` are cleared by `CUserStatus::Init`, which `GameInit` calls on every entry (chronicle:ps2/src/dngstatusdata.cpp:723-748; chronicle:ps2/src/dun/gameloop.cpp:1416).
- Restriction zone: `res_limit_zone_current` is reset at entry and exit (chronicle:ps2/src/dun/gameloop.cpp:1428, 2074). `res_limit_zone_id[6][25]` is the per-floor table (userstatus.hpp:95).
- Per-scene control: `step_disable`, `water_drain_disable`, `thirst_damage`, `next_hp`, `life_step`, `drink_next`, `drink_step`, `unk_8A74`, `unk_8A8C` (userstatus.hpp:129-141). `GameInit` resets the disables (chronicle:ps2/src/dun/gameloop.cpp:1891-1892).
- Atla and kill ledgers: `atra_grid[6][40][8]`, `atra_registry[6][100]`, `kills[6][100]` (userstatus.hpp:91-93). These are dungeon progress and do not cross.
- Save-wide, not in a party record: `stock_item` (chronicle:ps2/include/savedata.hpp:137; `CStockItem` at chronicle:ps2/include/stockitem.hpp:29), `chara_name` (savedata.hpp:119), the flag arrays, play time and the Georama data.

### Scene entry and the leader

- `GameInit` (chronicle:ps2/src/dun/gameloop.cpp:1405) does this in order: it takes `UserStatus` from the save (1415); it resets `hp` to `max_hp` and clears ailments unless `no_status_recover == 1` (1418-1428); it sets `cur_georama` (1434); it calls `LoadData` (1870); then it sets `nowUnitNow = cur_chara` (1893).
- `LoadData` sets `UserStatus->cur_chara = 0` and loads Toan and Toan's equipped weapon (chronicle:ps2/src/dun/gameloop.cpp:6981-7020, the assignment at 6998). The leader is always Toan at dungeon entry, whatever the passenger carried.
- `EditInit` sets `cur_chara = 0` for the town (chronicle:ps2/src/editloop.cpp:1135).
- `ModeInit` (chronicle:port/src/gameloop.cpp:217) runs once per scene from the outer loop of `RunGame`, at line 896, before the inner frame loop. It calls `GameInit` in its default case (line 278) and `EditInit` at line 255. An import placed at the top of the inner frame loop therefore runs after both, for each scene.

### Model, effect and voice reloads

- `selectChrUnit(chara, reload)` (chronicle:ps2/src/btitem.cpp:80-150) is the one routine that switches the leader. It returns early when `chara == cur_chara && reload == 0` (line 90). It sets `cur_chara` (line 94), loads the member's pack and the three weapon packs, and calls `LoadChara2` (line 112). It then calls `SetWeaponAttachStatus` (113), picks the effect from `Get_Main_EffectPtr(chara, best_elem)` (114), reloads the voice (123), sets `BtItemListCashFlag` (128) and `nowUnitNow` (129), and revives a dead leader to 1 HP (131-135).
- `LoadChara2` (chronicle:ps2/src/dun/gameloop.cpp:6871) deletes texture blocks 0x11, 0x1D and 0x10 and calls `LoadWeapon2` (chronicle:ps2/src/dun/gameloop.cpp:6609, the model index at 6639 from `chara_weapons[owner][equipped]`). Those texture blocks are the leader's, so a reload is visible.

### Safe point

- `RunGame`'s inner loop is the only clean point found. `FrameBoundaryStop` is tested at chronicle:port/src/gameloop.cpp:910-913. `MGBeginFrame` is at 917, `ModeLoop` at 922, `MGEndFrame` at 940, and the extra blank tick at 951-952 (`c1-mainloop-control.md`).
- The checkpoint that `HOP-V0.md` places at the end of `MGEndFrame` (chronicle:port/src/mglib.cpp:599) is later than the loop top and is still inside the frame function. `MGEndFrame` can also run more than once per `RunGame` frame, from the fades in `EditLoop` (chronicle:port/src/editloop.cpp:250-258, 544-558). Import or export inside the checkpoint callback is therefore not safe.

## How it works

### Export (origin, at the loop top)

1. Read the leader, the party size and the leader's row, all from `SaveData->GetDngStatus()`. Do not read `UserStatus` (it may be stale in town) and do not read `NowWeaponHave` (it is a derived copy).
2. Convert `hp`, `water_now` and `money` to the record. Carry `max_hp` so that a same-game import can restore it.
3. Carry the equipped row entry's `item_no`, `level`, `attack` and `elem[5]`. Skip the dungeon-only items in the list above, and skip `ITEM_WORLDMAP`.
4. Pack the inventory and the quick slots into the item list, with the overflow slots (103 entries) included. The record holds 16, so a count of the rest goes in `item_total`.

### Import (destination, at the first loop top after the scene init)

1. Choose the leader only if it is in the party (`want < party_size`). Otherwise keep the scene's leader and return a partial code. Do not write `st->cur_chara` yet, because `selectChrUnit(c, 0)` returns early when the leader already matches (line 90).
2. Set `max_hp` (same game only, capped), then set `hp` through `SetNextLife(c, hp, 0.0f)`, which clamps and clears `life_step`.
3. Set `money` with the 0xFFFF saturation.
4. Flush `drink_step` as `AddDrink` does, then set `water_now` and `drink_next`.
5. Set the ailment bits. Strip knock-out (see Risks).
6. Write the weapon into the owner's row, reusing a row entry with the same ID or else the first empty entry (`item_no < ITEM_WEAPON_START`). Fill the other `WEAPON_HAVE` fields from `GetWeaponData` and not from `WepDataListToHaveCopy`, so that no `rand()` is consumed.
7. Write items into inventory slots below `num`, and quick items into empty quick slots. Recount `item_count`.
8. In the dungeon only: if the leader changed or the weapon changed, call `selectChrUnit(c, 1)`. Then call `SetWeaponAttachStatus(NowWeaponHave)` and set `nowUnitNow`. In the town, stop after the status writes (the town's leader model load was not traced).
9. Set `BtItemListCashFlag = 1` so that the icons are rebuilt.

### Caches that hold copies, and what refreshes them

| Value | Reader or cache | After a write |
|---|---|---|
| `hp`, `max_hp` | `topStatusInfo` and `HealingWater` read them per frame (shot_freefuncs.cpp:304-322, 682-696) | None for the HUD. Clear `life_step` and set `next_hp`, or use `SetNextLife` |
| `water_now`, `water_max` | Water readers in `battlemenu.cpp:624-625, 732-748, 8504-8511`, `topStatusInfo` (801), `SetStatus_Dry` | Flush `drink_step` first |
| `money` | `CommonMoneyBoardDraw` (battlemenu.cpp:7906, 9643); shop reads `ShopUserStatusPt` (shop.cpp:1092) | None while no shop is open |
| `ailments` | `CheckLife` and the battle menu | None |
| Equipped row entry | `NowWeaponHave` and `WeaponHave` (gameloop.cpp:465, 1063); `DngWepHavePt` (battlemenu.cpp:1056) | `SetWeaponAttachStatus(NowWeaponHave)` in the dungeon. `DngWepHavePt` points into the row and needs no refresh |
| Weapon model, effect, voice | `LoadChara2`, `Get_Main_EffectPtr`, `SndVoiceLoad` (btitem.cpp:112-123) | `selectChrUnit(c, 1)` |
| Quick-item and weapon icons | `DngActiveItemTextureCopy`, `DngActiveWeaponTextureCopy` (menu_dungeon.cpp:2007, 2054) | `BtItemListCashFlag = 1` |
| Leader | `nowUnitNow` (gameloop.cpp:1134, 1893, 5389) and `oldUnitNow` (5355) | Set `nowUnitNow` |
| `item_count` | Recounted on shop exit (shop.cpp:1138) and in the battle menu (battlemenu.cpp:939) | Recount |
| Menu pointers | `BtlMenuStatusPt` (battlemenu.cpp:1045-1050), `MenuItemPackPt` (1057), `ShopUserStatusPt` (shop.cpp:1092) | None, since they point into the save. Close open menus first |

### Writes that are unsafe mid-dungeon

- Writing `cur_chara` without `selectChrUnit`. The action dispatch reads `cur_chara` (gameloop.cpp:3675-3730, 5099-5140), so the wrong model and the wrong ability run together.
- Writing `party_size`. It changes which members are fightable and the dead-party logic (gameloop.cpp:3185, 5618, 5637) and the battle menu ring. Only the story scripts should move it.
- Writing `equipped_weapon_slot` or a row entry without `SetWeaponAttachStatus` and a model reload. The damage code reads the copy (gameloop.cpp:7669, 8297), and the thirst drain reads its flags (dngstatusdata.cpp:654-660).
- Writing `hp` or `max_hp` with no clamp. `max_hp` below `hp` leaves a value the HUD still draws.
- Writing `cur_georama`, `cur_floor` or `floor_reached` outside the map-jump path. The loaded geometry belongs to the old floor.
- Writing `res_limit_zone_current`, `event_flags` or `step_disable`. These change the floor's rules while it runs.
- Calling `GetItem` or `WepDataListToHaveCopy`. They consume `rand()`, which the port shares across the game.

## Proposed Ixion code

These are proposals. None of this code exists in the tree. The file is `port/src/ixion_passenger.cpp` (new) and the header is `port/src/ixion_passenger.h` (new), in the Chronicle port. Both use only the fixed-width types of the ABI.

### The record (plain C, for `ixion_passenger.h`)

```c
/* Proposed: ixion/include/ixion_passenger.h. Plain C, fixed-width fields only. */
#include <stdint.h>
#include "ixion_api.h"   /* IXION_GAME_DARK_CLOUD, IXION_GAME_DARK_CHRONICLE */

#define IXION_PASSENGER_V1_ITEMS 16

typedef struct IxionPassengerItem {
    int16_t item_id;  /* Dark Cloud dungeon item, 132..256 (Item enum) */
    int16_t vol;      /* item_vol of the slot, or active_item_vol for a quick slot */
    int16_t qty;      /* copies: 1 for an inventory slot, quick_item_qty for a quick slot */
    uint8_t quick;    /* 1 when the entry came from a quick-use slot */
    uint8_t pad;
} IxionPassengerItem;

typedef struct IxionPassengerWeapon {
    uint8_t kind;        /* 0 = none, 2 = ITEMKIND_WEAPON */
    uint8_t pad;
    int16_t item_id;     /* WEAPON_HAVE::item_no, 257..376 */
    int16_t level;       /* WEAPON_HAVE::level, 0..99 */
    int16_t attack;      /* WEAPON_HAVE::attack, the stored base value */
    int8_t  elements[5]; /* WEAPON_HAVE::elem: fire, ice, thunder, wind, holy */
} IxionPassengerWeapon;

typedef struct IxionPassengerV1 {
    uint32_t size;               /* sizeof(IxionPassengerV1), set by the caller */
    uint32_t home_game;          /* IXION_GAME_DARK_CLOUD or IXION_GAME_DARK_CHRONICLE */
    int32_t  character;          /* 0..5 (Character enum), -1 if none */
    float    hp_ratio;           /* hp / max_hp, 0..1 */
    int32_t  max_hp;             /* origin max; used only when home_game is this game */
    uint32_t gilda;              /* Dark Cloud money is u16; 0..65535 */
    float    thirst_ratio;       /* water_now / water_max, 0..1 */
    uint32_t status_bits;        /* StatusAilment bits of ailments[character] */
    IxionPassengerWeapon weapon;
    uint32_t item_total;         /* non-empty items in the origin, before the cap */
    uint32_t item_count;         /* entries used in items[] */
    IxionPassengerItem items[IXION_PASSENGER_V1_ITEMS];
} IxionPassengerV1;
```

### Helpers (C++, `port/src/ixion_passenger.cpp`)

```cpp
// Live status: the one copy in the save. Never UserStatus, which is stale in town.
static CDngStatusData *C1Status() {
    return SaveData != nullptr ? SaveData->GetDngStatus() : nullptr;   // savedata.hpp:354
}

// Items that stay in the origin: the LostGateKey list (dngstatusdata.cpp:145-181),
// the key range 216..222, and ITEM_WORLDMAP (inference: story-bound).
static bool C1IsDungeonLocalItem(int id) {
    if (id == ITEM_WORLDMAP || (id >= ITEM_BONE_KEY && id <= ITEM_SILVER_KEY)) return true;
    return id == ITEM_DRAN_S_CREST || id == ITEM_SHINY_STONE || id == ITEM_RED_BERRY ||
           id == ITEM_HOOK || id == ITEM_KING_S_SLATE || id == ITEM_GUN_POWDER ||
           id == ITEM_CLOCK_HANDS || id == ITEM_POINTY_CHESTNUT || id == ITEM_BLACK_KNIGHT_CREST;
}

// Same rule as ShopMenuExit (shop.cpp:1138-1152).
static void C1RecountItemCount(ITEM_PACK *pack) {
    int count = 0;
    for (int k = 0; k < 3; k++)
        if (pack->quick_item_slot[k] >= ITEM_DUNGEON_START) count += pack->quick_item_qty[k];
    for (int j = 0; j < pack->num; j++)
        if (pack->item[j] >= ITEM_DUNGEON_START) count++;
    pack->item_count = (s8) count;
}

// Max HP caps from ItemUseFunc's Fruit of Eden table (menu_misc.cpp:277).
static const int kFruitOfEdenCap[6] = {170, 140, 170, 140, 180, 160};

static const uint32_t kPassengerAilmentMask = AILMENT_KNOCKED_OUT | AILMENT_FREEZE |
    AILMENT_STAMINA | AILMENT_POISON | AILMENT_CURSE | AILMENT_GOO;   // 0x7E
```

### Export

```cpp
// Reads only. Call from C1PassengerFrameHook(), never from inside a checkpoint.
extern "C" int C1ExportPassenger(IxionPassengerV1 *out) {
    if (out == nullptr || out->size != sizeof(*out)) return -1;
    CDngStatusData *st = C1Status();
    if (st == nullptr) return -1;
    const int c = st->cur_chara;                                  // userstatus.hpp:86
    if (c < 0 || c > 5 || c >= st->party_size) return -2;         // leader must be in the party

    memset(out, 0, sizeof(*out));
    out->size = sizeof(*out);
    out->home_game = IXION_GAME_DARK_CLOUD;
    out->character = c;

    const int mx = st->max_hp[c];                                 // userstatus.hpp:88
    out->max_hp = mx;
    out->hp_ratio = mx > 0 ? clampf(st->hp[c] / (float) mx, 0.0f, 1.0f) : 0.0f;  // :89
    out->gilda = st->money;                                       // u16 view (:110)
    const float wmax = st->water_max[c];                          // :101
    out->thirst_ratio = wmax > 0.0f ? clampf(st->water_now[c] / wmax, 0.0f, 1.0f) : 0.0f;
    out->status_bits = (uint32_t) st->ailments[c] & kPassengerAilmentMask;   // :99

    // Carried weapon: the equipped row entry (:107, :127), not NowWeaponHave.
    const int slot = st->equipped_weapon_slot[c];                 // s8, -1 if none
    if (slot >= 0 && slot < 11) {
        const WEAPON_HAVE &w = st->chara_weapons[c][slot];
        if (w.item_no >= ITEM_WEAPON_START && w.item_no < ITEM_WEAPON_END) {
            out->weapon.kind = ITEMKIND_WEAPON;
            out->weapon.item_id = w.item_no;
            out->weapon.level = w.level;
            out->weapon.attack = w.attack;
            for (int i = 0; i < 5; i++) out->weapon.elements[i] = w.elem[i];
        }
    }

    // Inventory slots (all 103, so overflow is included), then quick slots.
    ITEM_PACK &pack = st->item_pack;
    for (int i = 0; i < 103; i++) {
        const int id = pack.item[i];
        if (id < ITEM_DUNGEON_START || id >= ITEM_WEAPON_START || C1IsDungeonLocalItem(id)) continue;
        out->item_total++;
        C1PushItem(out, id, pack.item_vol[i], 1, 0);
    }
    for (int k = 0; k < 3; k++) {
        const int id = pack.quick_item_slot[k];
        if (id < ITEM_DUNGEON_START || id >= ITEM_WEAPON_START || C1IsDungeonLocalItem(id)) continue;
        out->item_total++;
        C1PushItem(out, id, st->active_item_vol[k], pack.quick_item_qty[k], 1);
    }
    return 0;
}
```

`C1PushItem` appends when `item_count < IXION_PASSENGER_V1_ITEMS` and does nothing otherwise. It is a plain helper and is not shown.

### Import

```cpp
// Writes state. Call only from C1PassengerFrameHook(), at the first loop top after
// GameInit or EditInit has finished (see Safe point).
// Returns 0 = all applied, 1 = applied with fallbacks, negative = refused before any write.
extern "C" int C1ImportPassenger(const IxionPassengerV1 *in) {
    if (in == nullptr || in->size != sizeof(*in)) return -1;
    if (in->home_game != IXION_GAME_DARK_CLOUD && in->home_game != IXION_GAME_DARK_CHRONICLE) return -3;
    CDngStatusData *st = C1Status();
    if (st == nullptr) return -1;

    const bool same_game = in->home_game == IXION_GAME_DARK_CLOUD;
    int status = 0;

    // 1. Leader. Do not assign cur_chara here: selectChrUnit(c, 0) returns early when it matches.
    int c = st->cur_chara;
    if (in->character >= 0 && in->character <= 5 && in->character < st->party_size) {
        c = in->character;
    } else {
        status = 1;                                               // not unlocked here: keep the leader
    }

    // 2. HP. Max first, then SetNextLife, which clamps and clears life_step (dngstatusdata.cpp:597).
    int mx = st->max_hp[c];
    if (same_game && in->max_hp > 0) {
        mx = in->max_hp < kFruitOfEdenCap[c] ? in->max_hp : kFruitOfEdenCap[c];
    }
    st->max_hp[c] = (s16) mx;
    int hp = (int) lroundf(clampf(in->hp_ratio, 0.0f, 1.0f) * (float) mx);
    if (hp < 1) hp = 1;                                           // KO passenger arrives at 1 HP
    st->SetNextLife(c, (s16) hp, 0.0f);

    // 3. Gilda, u16 with the retail saturation.
    st->money = in->gilda > 0xFFFF ? 0xFFFF : (u16) in->gilda;

    // 4. Water. Flush any drink in flight as AddDrink does (dngstatusdata.cpp:494-497).
    if (st->drink_step[c] != 0) {
        st->water_now[c] = (float) st->drink_next[c];
        st->drink_step[c] = 0;
    }
    const float wnow = clampf(in->thirst_ratio, 0.0f, 1.0f) * st->water_max[c];
    st->water_now[c] = wnow;
    st->drink_next[c] = (s16) lroundf(wnow);                      // drink_next is s16 (:134)

    // 5. Ailments. Knock-out is stripped, so the ailment bits never mark the leader dead.
    st->ailments[c] = (s32) (in->status_bits & kPassengerAilmentMask & ~AILMENT_KNOCKED_OUT);
    st->ailment_frames[c] = 0;                                    // frames do not cross

    // 6. Weapon: a complete WEAPON_HAVE in the owner's row, with no rand() calls.
    bool weapon_changed = false;
    if (same_game && in->weapon.kind == ITEMKIND_WEAPON) {
        int row = -1;
        for (int j = 0; j < 11 && row < 0; j++)                   // same ID first
            if (st->chara_weapons[c][j].item_no == in->weapon.item_id) row = j;
        for (int j = 0; j < 11 && row < 0; j++)                   // then an empty entry (item_no -1)
            if (st->chara_weapons[c][j].item_no < ITEM_WEAPON_START) row = j;
        if (row >= 0 && C1FillWeapon(&st->chara_weapons[c][row], in->weapon)) {
            st->equipped_weapon_slot[c] = (s8) row;
            weapon_changed = true;
        } else {
            status = 1;                                           // no room: keep the current weapon
        }
    }

    // 7. Items. Inventory writes stay below pack.num; GetItem is not used (it rolls rand()).
    ITEM_PACK &pack = st->item_pack;
    for (uint32_t n = 0; n < in->item_count; n++) {
        const IxionPassengerItem &it = in->items[n];
        if (!same_game || it.item_id < ITEM_DUNGEON_START || it.item_id >= ITEM_WEAPON_START ||
            C1IsDungeonLocalItem(it.item_id)) { status = 1; continue; }
        if (it.quick) {
            int k = 0;
            while (k < 3 && pack.quick_item_slot[k] != -1) k++;
            if (k == 3) { status = 1; continue; }
            pack.quick_item_slot[k] = it.item_id;
            pack.quick_item_qty[k] = it.qty;
            st->active_item_vol[k] = it.vol;
        } else {
            int i = 0;
            while (i < pack.num && pack.item[i] >= ITEM_DUNGEON_START) i++;
            if (i == pack.num) { status = 1; continue; }
            pack.item[i] = it.item_id;
            pack.item_vol[i] = it.vol;
        }
    }
    C1RecountItemCount(&pack);

    // 8. Model and dungeon copies. Only when the dungeon copy is this save's.
    if (mode == GAME_MODE_DUNGEON && UserStatus == st) {          // dun/gameloop.cpp:972
        if (c != st->cur_chara || weapon_changed) {
            selectChrUnit(c, 1);                                  // btitem.cpp:80; sets cur_chara and reloads
        }
        SetWeaponAttachStatus(NowWeaponHave);                     // menu_dungeon.cpp:232
        nowUnitNow = st->cur_chara;                               // gameloop.cpp:1134
    }

    // 9. Icons. Rebuilt on the next draw (gameloop.cpp:2288-2292).
    BtItemListCashFlag = 1;                                       // gameloop.cpp:1190
    return status;
}
```

`clampf` (used in the export and the import) is not defined anywhere in the Chronicle tree, so the port has to supply it (unverified that the port has no equivalent under another name). `C1FillWeapon` sets `item_no`, `level`, `attack`, `elem[5]`, `best_elem` (the largest element, or -1 when all are zero), and takes `endurance`, `speed`, `magic`, `durability`, `durability_f`, `vs_monster` (cast from s16 to char), and `flags` from `GetWeaponData(id)` (`port/src/itemdata.cpp:70`). It clears `experience`, `attach` and `attach_kind`, and `synthesis_count` is passed through from the record once the record carries it. It returns false when `GetWeaponData` returns null. The helper is not shown.

### Frame hook (the only caller)

```cpp
// Proposed. Called in RunGame's inner loop after FrameBoundaryStop and before MGBeginFrame
// (port/src/gameloop.cpp:911-917). g_c1_scene_ready is set by ModeInit after GameInit or EditInit.
void C1PassengerFrameHook() {
    if (g_c1_export_requested) {
        g_c1_export_result = C1ExportPassenger(&g_c1_export_buf);
        g_c1_export_requested = false;
    }
    if (g_c1_import_pending && g_c1_scene_ready) {
        g_c1_import_result = C1ImportPassenger(&g_c1_import_buf);
        g_c1_import_pending = false;
        g_c1_scene_ready = false;
    }
}
```

The hook is called from `RunGame` between `FrameBoundaryStop` and `MGBeginFrame`. The Hop v0 checkpoint stays in `MGEndFrame`. A travel request only sets `g_c1_import_pending` and copies the record into `g_c1_import_buf`. The module's `request_travel` callback and the `checkpoint` return are unchanged.

## Risks and blockers

- **Knock-out.** The import strips the knock-out bit and sets 1 HP. This is a product choice. A passenger who was knocked out in the origin arrives alive, and the dead-party logic (gameloop.cpp:5618-5690) is never exercised by a passenger.
- **Leader not in party.** A passenger whose character is not unlocked keeps the scene's leader, which is Toan after `LoadData` (gameloop.cpp:6998). The status return is 1. As written, however, the body still uses `c` (the leader) for steps 2 to 6, so the passenger's HP, max HP, water, ailments and weapon row are written into the leader's slots. The body should return before step 2, or skip those per-character writes, when the character is not in the party. This is a defect in the proposal, not a fallback.
- **Equipped index -1.** Several readers index `chara_weapons[c][equipped]` with no guard (btitem.cpp:102, gameloop.cpp:6639, hitvalue.cpp:41). Export and import both guard the index, but any other code path that runs after a party member joins can still read -1.
- **RNG.** The port overrides `rand` and `srand` with one global state (chronicle:port/src/runtime.cpp:25-43). `GetItem`, `ItemDataToHaveCopy` and `WepDataListToHaveCopy` all draw from it. The proposed import draws none, so a passenger does not change the origin's or the destination's random sequence. The port comment says the exact sequence matters in places (`runtime.cpp`).
- **Stored versus effective weapon.** The record carries the stored `attack`, and the effective attack is recomputed. Any caller that compares the two will see a difference (inference).
- **Writes persist.** `dng_status` is the save image. A passenger weapon or item written into it becomes permanent in the destination's save. Whether Ixion wants that is a product decision, not a code question. The sidecar alternative is in Open questions.
- **Texture lifetime.** `LoadChara2` deletes texture blocks 0x11, 0x1D and 0x10 (chronicle:ps2/src/dun/gameloop.cpp:6871, per `c1-characters.md`). The previous tick's display list may still reference them, and the loop top is the earliest point after the last render. Inference: confirm against the renderer's list lifetime before relying on it.
- **Town leader.** The town's leader model is not reloaded by the import. Whether the town shows the wrong leader is unverified.
- **Port bounds.** `GetItemData` rejects indices of 175 and above, and `GetWeaponData` rejects indices of 120 and above (chronicle:port/src/itemdata.cpp:61-77). The record uses item IDs, so this affects only lookups inside the port.
- **Passenger cap.** The record holds 16 items. The remainder is counted in `item_total` and not carried.
- **Debug path.** The party add at battlemenu.cpp:1063-1066 moves `party_size`. It sits inside `#ifdef PAL` (battlemenu.cpp:1061-1070), so a non-PAL build should not compile it. The party add at 1974-1984 was not checked for its preprocessor guard.
- **Unknown fields.** `CUserStatus` has undocumented blocks: `unk_01E[0x25A]`, `unk_4148[200]`, `unk_42A6[25]`, `unk_42C6[2]`, `unk_8A74[6]`, `unk_8A8C[6]`, `unk_8AEE[2]` and `unk_450A[2]` (userstatus.hpp:90, 94, 96, 98, 131-132, 136, 126). The export and import do not touch them. Anything the game keeps there is not carried.
- **Table disagreement.** Owner lookup in `GetItem` (a byte table) and `CheckWeaponUser` (ID ranges) were not cross-checked. A weapon routed by one but read by the other would sit in the wrong row.
- **Unnamed status bit.** Bit 0x01 of `ailments` has no name (userstatus.hpp:29-36). The mask in the proposal drops it.

## Open questions

- Which event scripts call `_SSET_PARTY_NUM` (opcode 710), and in what order do members join? The opcode and its writer are confirmed. The script call sites are not, because the event data is bytecode.
- Does the town load a leader model? `EditInit` sets `cur_chara` (editloop.cpp:1135). Whether the town then loads the member's model, and through which function, was not traced.
- Should a passenger weapon replace the equipped row entry for the trip only, or persist in the destination's save? The proposal writes it persistently.
- Should attachments (`consumable_items`, ids 81 to 131) and the `attach[6]` sockets cross? Both are in the origin's save, and neither is in the record.
- How do `attack` and `level` change through `CWeaponLevelUp`? The proposal assumes the stored `attack` is the base. This was confirmed only by the read of `WeaponAllValueSet`, not by a full trace of the level-up path.
- Is the flag at `ailments` bit 0x01 used, and what does it do?
- Should `ailment_frames` cross? A freeze or poison carried across a trip would restart its timer in the proposal.
- How do the two owner lookups agree? `ItemPutListTbl12_bytes` (dngstatusdata.cpp:431) and `CheckWeaponUser` (dngstatusdata.cpp:264) should give the same owner for every weapon ID. This was not checked for all 120 entries.
- Is the durable and fragile roll in `WepDataListToHaveCopy` (menu_draw.cpp:2917, which runs only for weapons that are not default) needed for a passenger weapon? The proposal skips it. If it is needed, it must use a fixed seed or a stored value.
- Does `selectChrUnit(c, 1)` at the loop top (step 8) run inside an interval where the renderer is idle? The loader calls `wait_now_loading_vsync`, which pumps the clock. A stop inside that call should be tested.
- What is the record's `size` check for cross-version use? The proposal requires an exact `sizeof` match, which is strict but simple. ABI version negotiation belongs in the module API, not this record.
- Is the DC2 gilda width (the design note says 999,999 maximum, `multi-game-host-design.md`) enough to justify a `u32` in the record? The DC1 side is settled at 16 bits unsigned.
