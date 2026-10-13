# Chronicle (DC1): characters and the party

## What this covers

Chronicle's playable party: the six character IDs, how the active leader is switched (script, in-field menu, dead-party swap, dungeon entry and exit), and how each member's model, motion sets, cloth, weapons, held-item bones, effects, voice and special-ability code are defined and loaded. It also covers how a substitute or a seventh playable character would be wired in for Ixion. Villagers (NPCs) are covered only where they share the loader. ChronicleTwo (DC2) is cross-referenced, not studied.

Source scope: `ps2/src` and `ps2/include` in the Chronicle checkout (master 3bc16763), `port/src` and `port/CMakeLists.txt` for the PC overrides, and the extracted PAL pack entries for the six `dun/mainchara/*.chr` files. Community pages were checked for behaviour (`docs/fandom/Dark_Cloud.wiki`, `docs/fandom/Toan.wiki`).

## Key facts

- Six playable characters, enum `Character`: TOAN=0, XIAO=1, GORO=2, RUBY=3, UNGAGA=4, OSMOND=5. chronicle:ps2/include/itemdata.hpp:485-491
- The active leader is `CUserStatus::cur_chara` (s8), documented as the index of the controlled party member. chronicle:ps2/include/userstatus.hpp:86
- Party membership is a prefix of ID order. The battle menu gives any `SysChara` entry whose `chara >= party_size` a different cursor and frame. chronicle:ps2/src/battlemenu.cpp:2259 (the code shows a different layout, not a confirmed hide; unverified)
- The debug "add member" path raises `party_size` and gives member `party_size-1` its default weapon, which confirms the prefix model. chronicle:ps2/src/battlemenu.cpp:1975-1981
- Script opcodes read and write the party count (`_SGET_PARTY_NUM` 709, `_SSET_PARTY_NUM` 710) and grant skills (`_SSKILL_GET` 715). chronicle:ps2/src/editloop3.cpp:7362-7371, 7411-7420, 8224-8228
- The player is one global object, `CCharacter CharaMain`, not one object per character. Switching a character reloads that object's model, motions, textures and weapons. chronicle:ps2/include/dun/gameloop.hpp:184; chronicle:ps2/src/dun/gameloop.cpp:6871-6923
- The helper object `CharaHand` (also a plain `CCharacter`) is the second model used by the hand actions of Xiao, Ruby and Osmond. Only Xiao and Ruby load a hand rig into it (`hand_up.cfg`). chronicle:ps2/src/dun/gameloop.cpp:457, 5089-5100; chronicle:ps2/src/dun/gameloop.cpp:6909-6921
- Per-member asset files are named by `charaNameTbl`: `dun/mainchara/c01d.chr`, `c04b`, `c06b`, `c05a`, `c10b`, `c18a` for Toan, Xiao, Goro, Ruby, Ungaga, Osmond. chronicle:ps2/src/btitem.cpp:56-60
- The menu side uses a different two-digit name for the same member (`charaFile` = 01d, 04b, 06b, 05a, 10b, 18a with `.chr` appended), and the portrait/model pack name is `c0<chara+1>model.pak` (so Osmond is `c06` in menus and `c18a` in the dungeon). chronicle:ps2/src/menu_misc.cpp:1031-1041, 1132; chronicle:port/src/linknames.cpp:45
- Weapon model files use a per-owner prefix (`c01w`, `c04w`, `c06w`, `c05w`, `c10w`, `c18w`) plus the weapon's index counted from that owner's first weapon ID. chronicle:ps2/src/btmisc.cpp:191-211
- Weapon ownership is by ID range, not by a stored owner lookup at this call site: `CDngStatusData::CheckWeaponUser` maps each `ITEM_WEAPON_*_BROKEN` boundary to a character. chronicle:ps2/src/dngstatusdata.cpp:264-290
- Per-member defaults (`defWeapon[6]`) are copied into four separate translation units rather than shared. chronicle:ps2/src/btitem.cpp:53; chronicle:ps2/src/dngstatusdata.cpp:24; chronicle:ps2/src/menu_misc.cpp:41; chronicle:ps2/src/shot_freefuncs.cpp:18
- Starting life, weapon and stat values are a six-entry table in `CDngStatusData::Initialize`, with `cur_chara = CHARA_TOAN` and `party_size = 1`. chronicle:ps2/src/dngstatusdata.cpp:887-894
- Each member's `base.cfg` (inside its `.chr` pack) is a text script read by `ReadInfo`. The reader recognizes 19 commands. chronicle:ps2/src/chararead.cpp:92-113, 135
- Every member's `base.cfg` defines exactly one motion set (`MOTION 0`), with a `.mot`/`.bbp`/`.wgt` triple and between 36 and 41 `KEY` rows. Toan has 41, Goro 37, Ungaga 40, and Xiao, Ruby and Osmond 36 each (counted from the extracted packs; unverified, the packs are binary and the counts were not re-run).
- Extension packs (`*_ex00.chr`, `base2.cfg`) add motion sets 3 to 5 with `KEY_START` 42 to 46. These serve the chest and Atla presentations, not party play. chronicle:ps2/src/btitem.cpp:208-212, 466-469 (chara_files table)
- Cloth is declared per member: Toan has `turban.clo`, `poncho1.clo`, `poncho2.clo`; Goro `goro.clo`; Ungaga `ungg1.clo`, `ungg2.clo`. Xiao, Ruby and Osmond have none in `base.cfg` (extracted packs; unverified).
- Body size is a per-member `BODY_SIZE` line (for example Ungaga `20,6,60` against `17,7,60` for most others; extracted packs). A separate per-ID height table, `CharaHeight`, is duplicated in five places. chronicle:ps2/src/dun/gameloop.cpp:195; chronicle:ps2/src/monstorunit.cpp:52; chronicle:ps2/include/charaheight.hpp:15; chronicle:port/src/dun/gameloop.cpp:155; chronicle:port/src/dun/movechara.cpp:209
- Voice is a per-ID bank: `SndVoiceLoad(id)` loads `sound/voice/voice<id>.snd` with `voice<id>.txt`. The extracted data has voice0 to voice6. chronicle:ps2/src/snd.cpp:1378-1415; chronicle:ps2/src/btitem.cpp:123
- The effect table is a per-ID switch: `Get_Main_EffectPtr(chara, form)`. Ruby selects one of five forms, Osmond has its own entries, and the table `MyEffectEntry_Tbl[15]` holds the results. chronicle:ps2/src/dun/gameloop.cpp:6763-6780 and the table around 790-809
- The UI menu has a fixed six-slot ring: `MenuChara.slot_count = 6`, `SysChara[6]`, `MenuCharaWeaponMax[6] = {42,15,17,16,16,14}`, `MenuWepPolyOffset[6]`. chronicle:ps2/src/battlemenu.cpp:108, 119, 121, 1058
- Save-state storage is six-wide throughout: `max_hp[6]`, `hp[6]`, `ailments[6]`, `chara_weapons[6][11]`, `atra_grid[6][40][8]`, `kills[6][100]`, `skill_owned[6]`, `equipped_weapon_slot[6]`. chronicle:ps2/include/userstatus.hpp:88-141
- Each member's special ability is a per-ID dispatch, not a data table: `ToanKey_On/Play` (charakey.cpp:54, 98), `UngagaKey_On/Play` (604, 642), `GoroKey_On/Play` (936, 960), `BattleActionOn_Jinn` for Xiao (gameloop.cpp:7655), `BattleActionOn_Ruby` (7822), and `BattleActionOn_Ozumond` plus the `_H` and `_F` gun variants (8071, 8084, 8098). The dispatch sites are gameloop.cpp:3675-3730 and 5099-5140.
- Atla (Atlamillia) pickup is Toan-only. Any other member gets `NotGetAtraMes`. chronicle:ps2/src/dun/gameloop.cpp:3641-3647
- Osmond has ID-specific field rules: movement is allowed during an action (`cur_chara == CHARA_OSMOND`), a ground-kind test for kind 0xA shows message 0x50 and blocks the action, and the battle menu refuses for ground kind 10 (message 0x1A1). chronicle:ps2/src/dun/gameloop.cpp:3163, 3568, 5081; chronicle:ps2/src/battlemenu.cpp:1912
- The Osmond tail is a named frame, `tukene1`, and the look frame is `jnt2_1`. chronicle:ps2/src/dun/gameloop.cpp:5843-5846, 5868
- `CDungeonMap::SetCharaDoor` has one case per ID, each placing that member's door part on a random floor cell. Toan's case only runs when `party_size >= 2`. chronicle:ps2/src/dungeonmap.cpp:3355-3440; the port overrides it at chronicle:port/src/dungeonmap.cpp:259 and uses `std::uintptr_t` for the address arithmetic
- The port overrides almost none of the character-loading path. There are no `PORT_OVERRIDE` definitions for `ReadInfo`, `LoadChara2`, `selectChrUnit`, `BtMenuLoadChara`, `LoadWeapon2`, `CheckWeaponUser`, `Get_Main_EffectPtr` or `CharaChangeKey` (checked by grep of `port/src`). The character unit `character.cpp` overrides only `CCharacter::ClothStep`; `chararead.cpp` in `port/src` has no `PORT_OVERRIDE` (it defines `StretchBind2` and `vuabs`). chronicle:port/src/character.cpp:13-38; chronicle:port/src/chararead.cpp
- The port build compiles `ps2/src` units unchanged, strips PORT_OVERRIDE definitions from copies, and checks that every override replaces a real `ps2/src` definition. chronicle:port/CMakeLists.txt:37-99

## How it works

### 1. Identity and storage

Every per-member array is indexed by the `Character` value. The leader is `UserStatus->cur_chara`. The party is the first `party_size` IDs. Saves store six slots per field, so the ID space is a storage layout as well as a code convention (see Risks).

### 2. Loading a member into the player object

`LoadChara2(chara, keep_place, chara_data, crash_data, default_data, main_data)` (chronicle:ps2/src/dun/gameloop.cpp:6871) does the work for every switch:

1. It remembers the old model's position and rotation unless `keep_place` is set.
2. It deletes texture blocks `0x11`, `0x1D` and `0x10`, cleans the buffers, and re-initializes `CharaMain` and `CharaMainTexAnim[64]`.
3. It calls `CharaMain.LoadPackData2(chara_data, "base.cfg", ...)`, which runs `ReadInfo` (chronicle:ps2/src/chararead.cpp:135).
4. For Xiao and Ruby it loads the hand rig from `hand_up.cfg` into `CharaHand` and sets its clipping. For Osmond it loads the hand texture `c05w_h.img` into block `0x46` and an effect file `mgan01.chr`. For Ruby it loads `c05_f03.chr` as the default effect.
5. It sizes the weapon buffer to what is left, then calls `LoadWeapon2`.

`LoadWeapon2` (chronicle:ps2/src/dun/gameloop.cpp:6609-6645) loads three weapon packs: a crash weapon (index 0), a default weapon (index 1), and the equipped weapon, whose index is its item number minus the owner's first weapon ID. The equipped weapon is then attached to the `weapon` bone of the player model (`EquipWeaponFrame`, gameloop.cpp:6569-6579).

### 3. What `ReadInfo` does with base.cfg

`ReadInfo` tokenizes the text and runs a fixed table of 19 commands (chararead.cpp:92-113). The commands that matter for a party member:

- `MODEL` loads the `.mds` into the frame through `LoadMDSFile`, sets the vertex-animation type and stores the config text for texture animation (chararead.cpp:221-264).
- `MOTION set, mot, bbp, wgt` creates the motion data, with `ALLOC_*` lines able to put it in named arenas (chararead.cpp:283-337).
- `KEY_START n` and `KEY start, end, speed` rows fill a `MOTION_INFO` table. `MOTION_END` closes the set and fixes `motion_start` and `motion_end` (chararead.cpp:390-443).
- `SHADOW_MODEL` and `SHADOW_MOTION` do the same for the shadow.
- `CLOTH` creates cloth simulations (chararead.cpp:445-457), and `BODY_SIZE` sets height, width and depth.
- `FOOT left,right` and `EVENT frame,kind,no` schedule footstep and sound events per motion set (chararead.cpp:549-558). `CharaEventKind` has FOOT_SOUND=0 and SOUND_EFFECT=1 (character.hpp).
- `IMG slot, name` and `IMG_END` load textures into the character's texture block, then hand the `.cfg` to `tex_anime` (chararead.cpp:489-547).

A motion number is a row in the `KEY` table. `CCharacter::GetMotionParam` maps a global motion number to the set whose `[start, end)` range covers it (chronicle:ps2/src/character.cpp:410-455). CHARA_MOTION_MAX is 8 sets per character (character.hpp:35).

### 4. Switching the leader

There are four paths.

- **Script (synchronous).** `_SET_MAIN_CHR2` clamps the ID to 0..5, calls `selectChrUnit(chara, reload)` and records `script_main_chr`. `_RESET_MAIN_CHR` switches back. Opcode numbers 1067 and 1071. chronicle:ps2/src/btsysscript.cpp:847-870, 1134-1135. `selectChrUnit` (btitem.cpp:80-130) reads the member's pack, the three weapon packs and the effect into the shared read buffer, calls `LoadChara2`, calls `SndVoiceLoad(cur_chara)`, reloads the item-list icons and resets HP to 1 if the member is dead.
- **In-field (menu, asynchronous).** Pressing SELECT with `party_size >= 2` (gameloop.cpp:3185-3196) opens the mini-selector. Confirming a member in the change menu sets `cur_chara` through `SetStatusChara` (menu_dungeon.cpp:1462, 1638), refuses knocked-out members, and in one mode (`ChangeMenu.mode == 1`) consumes `ITEM_STAND_IN_POWDER`. The loading steps then call `BtMenuLoadChara` (menu_dungeon.cpp:1476; menu_misc.cpp:1209), which sets `cur_chara` and calls `LoadChara2`. The pre-read of the three packs happens in `CharaChangeInitToGL` (menu_misc.cpp:1134-1186). The battle menu has its own copy of the same sequence (battlemenu.cpp:1722-1735).
- **Dead party.** When the leader is down and a living member is left, `GAME_TASK_DEAD_CHANGE_CHARA` opens the mini-selector with `BtMiniChrSelect_Init(1)` and sets `swapped_on_death` (gameloop.cpp:5673-5695).
- **Dungeon boundaries.** Entering a dungeon runs `LoadData`, which sets `cur_chara = 0` and loads Toan (gameloop.cpp:6981-7020, entry at 1870). Leaving resets `cur_chara` to Toan and restores HP to max unless `no_status_recover` is set (gameloop.cpp:2040-2080).

The battle-menu ring gives members outside the `party_size` prefix a different cursor and frame (battlemenu.cpp:2259); whether they are hidden was not confirmed (unverified). The mini-selector and change menu were not traced for the same rule, so whether a non-prefix member can be picked there is an open question.

### 5. Weapons and held items

`CheckWeaponUser` maps weapon item IDs to owners by range. Toan owns the dagger range, Xiao the slingshot range, Goro the mallet range, Ruby the gold-ring range, Ungaga the fighting-stick range and Osmond the machine-gun range (dngstatusdata.cpp:264-290). `ITEM_WEAPON_START` is 257 and `ITEM_WEAPON_END` 377 (itemdata.hpp:346, 463). `WEAPON_DATA::owner` is a byte that `BtGetWeaponNamePath3` uses to pick a file prefix (btmisc.cpp:213-229).

The held-item and throw bones are fixed names: `item` for held items (`CMainItemModel::SetHandModel` at mainitemmodel.cpp:84-99, the `CharaMain.frame->SearchFrame("item")` at btitem.cpp:1035 and gameloop.cpp:7519-7540), `weapon` for the equipped weapon (gameloop.cpp:6578, 6701), `dcol0` and `dcol1` for weapon hit boxes (charakey.cpp:238 and others), and `pati1` for Xiao's held-out slingshot frame (gameloop.cpp:6576).

### 6. Special abilities

The ability code is written per ID, and each ID has a different shape:

| ID | Member | Field ability (code) | Combat ability (code) |
|---|---|---|---|
| 0 | Toan | Only member who can take Atla (gameloop.cpp:3641-3647); his door part on a random floor needs party >= 2 (dungeonmap.cpp:3367) | `ToanKey_On/Play`, timed multi-hit damage windows, with a `skill_owned[0]` charge branch (charakey.cpp:54-440) |
| 1 | Xiao | Hand rig (`CharaHand`) with `BattleActionOn_Jinn` on the hand action (gameloop.cpp:7655, 5099-5105); held-out weapon frame `pati1` (gameloop.cpp:6576). Fandom: Xiao can jump across chasms (Dark_Cloud.wiki) | Slingshot-type ranged action through the hand rig (inference from the handler name and the `Jinn` path) |
| 2 | Goro | `GoroKey_On/Play` (charakey.cpp:936-1133); plays `SE_GORO_SMASH` (charakey.cpp:1133) | Hammer melee (fandom: a single attack animation) |
| 3 | Ruby | Ring charge with `ruby_effect_id`; `BattleActionOn_Ruby` (gameloop.cpp:7822) | Ring shots, with a different effect per form (Get_Main_EffectPtr, gameloop.cpp:6772-6780) |
| 4 | Ungaga | `UngagaKey_On/Play` (charakey.cpp:604-930); sets `skill_owned[4]` at charakey.cpp:611 | Staff attacks (fandom: staves) |
| 5 | Osmond | Tail `tukene1`; ground kinds 10 and 0xA restrict actions; movement uses 8 steps not 1 (port movechara.cpp:2243) | Three gun modes `_M`, `_H`, `_F` (gameloop.cpp:8071-8288) |

Dispatch for the special attack is `switch (UserStatus->cur_chara)` at gameloop.cpp:3675-3730, and for the hand actions at gameloop.cpp:5099-5140. The port repeats the same dispatch in port/src/dun/movechara.cpp:927-964.

### 7. Common motion numbers

The shared code refers to fixed motion numbers across members: `0x0A`, `0x0C`, `0x0D`, `0x0E`, `0x12`, `0x17`, `0x1A`, `0x1B`, `0x1C`, `0x1D`, `0x1E`, `0x21`, plus `0x24`–`0x28` for Toan's combo. `0x17` is assigned for any member at gameloop.cpp:3170, 5594 and 5674 (the last is the dead-party swap). Each member's `base.cfg` has a separate table, and Osmond's has only 36 rows. This means the shared code relies on an informal convention for the low numbers, which the data files do not enforce (inference from the row counts and the references).

### 8. Villagers and NPCs

`CNPCharacter : CCharacter` (npcharacter.hpp:36) is the NPC class. Villagers load `chara/<name>.chr` from the editor data directory through `EdLoadVillager` (chronicle:ps2/src/editloop3.cpp:1011-1063), using `info.cfg` or `<name>.cfg`. `VILLAGER_INFO::character_no` is a Georama parts index, not a party ID (editloop.hpp:202-206; editloop3.cpp:886-936). The dungeon has `NPCUnit[6]` (gameloop.cpp:480), which is a separate array from the party.

### 9. PC port specifics

- `CCharacter::wind` is an `s32` that holds an image pointer. The port converts it with `PortImagePointer` in `ClothStep` (chronicle:port/src/character.cpp:13-38). Title code stores `(int) &Wind__4` into it (chronicle:ps2/src/title/title.cpp:417).
- `itemOpenItemMds` and `itemOpenItemImg` are `int` globals holding pointers. The port keeps them whole in `port/src/btitem.cpp` (comment at btitem.cpp:47-48), which is a pattern to check for any new code.
- `GetWeaponData` has a port override (port/src/itemdata.cpp:70). `port/src/menu_misc.cpp` overrides `EnterWeaponModel`, `WeaponModelBuildFunc` and `DngWeaponEquipModelBuild` at chronicle:port/src/menu_misc.cpp:68, 160, 244.

### 10. Cross-reference: ChronicleTwo

DC2's character code is not the same system. `CCharacter2 : CObjectFrame` (chronicletwo:ps2/include/character.hpp:374) and `charasetup.cpp` build Max and Monica from several parts with `LoadPack(... "info.cfg" ...)` and parent parts (chronicletwo:ps2/src/charasetup.cpp:171-257). The DC2 setup also covers a ridepod with Max aboard and a monster form for Monica (chronicletwo:ps2/include/charasetup.hpp:11-12). A grep of DC2's `ps2/src` and `port/src` for `base.cfg` and `ReadInfo(` found nothing, so DC2 does not appear to use the DC1 `base.cfg` loader (inference from the absence). Max and Monica's ability code is in `actionchara.hpp` (ACTION_CHARA_MAX=0, ACTION_CHARA_MONICA=1; chronicletwo:ps2/include/actionchara.hpp:29-30).

## Ixion hooks

These are the places where Ixion could add or substitute a playable character. The brief asks about Max and Monica; the hooks are written for any substitute.

1. **Substitute into an existing slot (least invasive).** Keep the six IDs and replace the data behind one slot. The loader is by file name (`charaNameTbl`, btitem.cpp:56-60), so a different pack under the same name changes the model without touching the code. The catch is that the pack must be a DC1-format `.chr` (section 3 above), which DC2 assets are not (inference from section 10). A conversion tool would have to produce `base.cfg`, the `.mds`, `.mot`/`.bbp`/`.wgt`, and the weapon packs under the slot's prefix.

2. **A roster indirection, one table per slot.** There are roughly fifteen separate `[6]` tables keyed by the same index: `defWeapon` (four copies), `charaNameTbl`, `charaFile`, the weapon prefix list in `BtGetWeaponNamePath2` (btmisc.cpp:193), `StartLoadCharaMDS`'s `c0%d` naming, `CharaHeight` (five copies), `SysChara`, `MenuCharaWeaponMax`, `MenuWepPolyOffset`, `start_hp`/`start_stat`, `MyEffectEntry_Tbl`, `LoadWeapon2`'s `weapon_kind`/`weapon_first` (gameloop.cpp:6610-6611), and `SetCharaDoor`. A single roster struct per slot (pack name, weapon prefix, default weapon, height, voice set, effect table, menu name) would let Ixion swap identities without editing each unit. This is the main recommended hook, and it is inference from the code shape.

3. **Override the switch functions in `port/src`.** `selectChrUnit` (btitem.cpp:80), `BtMenuLoadChara` (menu_misc.cpp:1209) and `LoadChara2` (gameloop.cpp:6871) have no PC overrides. A PORT_OVERRIDE can replace any of them as a whole, because the build strips and checks overrides against `ps2/src` definitions (port/CMakeLists.txt:37-99). Replacing `selectChrUnit` lets Ixion map a slot to a roster entry (for example Max's pack under slot 1) at the one place every script switch goes through.

4. **Motion table contract.** A substitute model needs motion numbers that cover every number the shared code uses (section 7). The simplest route is to author a `base.cfg` `KEY` table with the same low-numbered rows, mapping DC2 animations onto them. This is data work, not code work.

5. **Bone names.** A substitute needs bones named `weapon` (hand), `item` (held item), `dcol0` and `dcol1` (weapon hit boxes), and `jnt2_1` (look target). Xiao needs `pati1` (used only when Xiao holds the weapon out, `EquipWeaponFrame`, gameloop.cpp:6576), and Osmond needs `tukene1`. A model that lacks one of these is expected to lose the feature behind that name. The `SearchFrame` callers were not checked for null handling, so whether a missing bone crashes or silently skips is unverified. These names are the contract for any new model.

6. **Abilities by roster identity.** The per-ID `switch` blocks (gameloop.cpp:3675-3730, 5099-5140; movechara.cpp:927-964) test `cur_chara`. A substitute that keeps the ID keeps Xiao's hand and slingshot behaviour. If Max or Monica should have their own abilities, add an indirection from slot to ability (or a new ability key) rather than editing each switch.

7. **Save layout.** Keep the six-slot arrays. Store any Ixion-only roster in a separate section or a sidecar that the DC1 save does not read, so the existing layout is not changed. This is inference: the arrays in `userstatus.hpp:88-141` are the constraint.

8. **Voice.** Voice is loaded by ID (snd.cpp:1378-1415). A substitute keeps its own voice bank only if the loader is redirected, so the hook is the same place as item 3 (`selectChrUnit` calls `SndVoiceLoad(cur_chara)`, btitem.cpp:123).

9. **Party order.** Because the party is a prefix of ID order (battlemenu.cpp:2259), a member in slot k is only in the party once `party_size` exceeds k. Any Ixion roster that reorders members has to reorder the points where `party_size` grows, which live in the event scripts (not read here).

## Risks and blockers

- **Six is hard-wired in the UI.** The ring menu uses six slots (battlemenu.cpp:1058 and `PosAngle = TWO_PI / MenuChara.slot_count`). A seventh playable member does not fit without rewriting the ring layout and the portrait tables. Keeping six is the practical limit.
- **Save layout is six-wide.** `userstatus.hpp:88-141` has `[6]` in every per-member field, and the save stores these directly. Adding a seventh member would change the size of these arrays, and so the save layout (inference from the struct declarations; no save-format test was run).
- **Behaviour is keyed by ID.** The special-ability, Atla, door-key, Osmond ground, and movement code all test IDs directly. Swapping data under an ID changes assets but not logic, which may or may not be what Ixion wants.
- **Motion numbers are an informal convention.** The shared code uses `0x0A`–`0x28` across members (section 7), and the per-member tables have 36 to 41 rows. A substitute that is missing a row used by the shared code may misbehave; the call sites were not traced for bounds checks, so the failure mode is unverified.
- **Bone names are a silent contract.** A missing `weapon` or `item` bone loses the weapon or held item; whether that is silent or a crash depends on each `SearchFrame` caller, which was not checked.
- **Pointers in `s32` fields.** `CCharacter::wind` (and the `int` pointer globals in `btitem.cpp`) hold addresses. The port handles known instances, but other `(int)` casts of pointers may exist elsewhere in the character path. Any new code should use `std::uintptr_t` or the port helpers.
- **Extracted weapon files do not match the table counts.** The extracted `commenu/weapon` folder has 41 (Toan), 15 (Xiao), 15 (Goro), 14 (Ruby), 13 (Ungaga) and 13 (Osmond) `cNNw` files, against `MenuCharaWeaponMax` of 42, 15, 17, 16, 16 and 14. The gaps are not explained by the code read here (open question).
- **Asset use.** The workspace treats ripped assets as placeholders and study material only. A DC2-to-DC1 conversion would need to respect that rule, and the public documentation should describe the mechanism, not the data.
- **Cross-engine.** DC2's Max and Monica use a parts system and a ridepod (section 10). Their animations, weapons and abilities are not directly expressible in the DC1 `base.cfg` and per-ID switches without new code. This is the largest blocker for the stated goal.

## Open questions

- Which extracted weapon files are missing against `MenuCharaWeaponMax`, and is the gap in the data or in the table? (The extracted folder is the only evidence here.)
- Where are the story join points for each member, and do the event scripts set `party_size` directly (`_SSET_PARTY_NUM`) or rely on prefix growth? The opcode is confirmed; the calls were not traced.
- Are the `KEY` rows used by the shared code (for example `0x17`, `0x1D`, `0x21`) present in all six packs? This was counted, not verified against the per-member motion names.
- Do DC2's `info.cfg` parts or `.mds` files share a format with DC1's `.mds`, so that any conversion is only a container change? This was not checked here.
- Does the PAL `SysChara` ring have any hidden seventh slot in the data, or is six a hard UI limit? Only the code path was read.
- Where are the `ITEM_LIST`/`WeaponList` data for the per-owner weapon ranges kept, and can Ixion add rows without a rebuild? (The port reads them through `GetWeaponData`, port/src/itemdata.cpp:70, but the table itself was not read.)
- Which event scripts call `_SET_MAIN_CHR2` and `_RESET_MAIN_CHR` (cutscene leader changes), and do any of them skip `LoadChara2`-equivalent loading? Only the opcode bodies were read.
- The ChronicleTwo side of the question (how Max and Monica are loaded and switched, and whether any DC2 mechanism maps onto the DC1 six-slot model) is covered by the DC2 research pages, not here.
