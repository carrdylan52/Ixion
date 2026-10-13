# ChronicleTwo: characters, Max and Monica

## What this covers

How Dark Chronicle (ChronicleTwo, "DC2") represents and runs its playable party: the user-data roster, the in-dungeon actor classes, how the active character is switched in towns, dungeons and events, how each character's model, motion script, weapon, sound and sword trail are assembled, Monica's monster form, the Ridepod with Max riding inside it, and the townsperson "party NPC" system. It ends with the PC-port layer that touches these paths and with concrete hooks for Ixion (adding or substituting a playable character, for example Toan).

Source read: chronicletwo `ps2/src`, `ps2/include` (retail units, the reference), `port/src` (PC overrides), `docs/PC.md`, `docs/PC_PORT_PLAN.md`, the extracted PAL data tree (file names and sizes only), and the Ixion design notes. Line numbers are as checked on the ixion branch of the ChronicleTwo clone. Nothing was built or run.

Out of scope: the Chronicle (DC1) party (see `ixion:docs/research/c1-characters.md`), battle damage math, the action-script bytecode itself (binary `.stb`, not decoded here), and event scripts beyond the calls that touch characters.

## Key facts

- The roster enum has four ids: `USER_CHARA_MAX=0` (Max), `USER_CHARA_MONICA=1`, `USER_CHARA_ROBO=2` (the Ridepod), `USER_CHARA_MONSTER=3` (Monica's monster form), `USER_CHARA_NUM=4`. chronicletwo:ps2/include/userdata.hpp:20-26
- Only Max and Monica have a human body and a `CHARA_DATA` record. The record array is fixed at two elements, `chara_data[2]`. chronicletwo:ps2/include/userdata.hpp:1153
- `GetCharaDataPtr` returns a pointer only for ids 0 and 1 and NULL for ROBO and MONSTER. chronicletwo:ps2/src/userdata.cpp:2836-2842
- `CUserDataManager` has a static size assert of `0x457A0` bytes, so the roster layout is part of the save format. chronicletwo:ps2/include/userdata.hpp:2180
- Roster bitfields are indexed by `USER_CHARA`: `party_member` and `chara_change` are `u16`, `chara_change_mask` is `u8`. chronicletwo:ps2/include/userdata.hpp:1161-1163
- The played character is `active_chr_no` (`s16`). `SetActiveChrNo` also re-points the battle view `CBattleCharaInfo`. chronicletwo:ps2/include/userdata.hpp:1165; chronicletwo:ps2/src/userdata.cpp:3409-3416
- `CBattleCharaInfo::SetChrNo` chooses which status it reads by range: ids 0..1 are human, 2 is the Ridepod, 3 is the monster. chronicletwo:ps2/src/userdata.cpp:4812-4860
- New-game defaults: active = Max, party = Max, change-enabled = Max, `monster_id = -1`; the two human starting HP capacities are 32 (Max) and 48 (Monica). chronicletwo:ps2/src/userdata.cpp:2764-2774
- The Monica opening (title entry) runs dungeon event `0x3F2` on floor `0x14`, then makes Monica the only party member and the active character. chronicletwo:ps2/src/title.cpp:1028-1042
- Dungeon hotkeys: L3 requests a partner swap (Max to Monica or back), R3 requests a ride swap (Max to Ridepod or back, Monica to monster or back). chronicletwo:ps2/src/dng_main.cpp:2303-2308; chronicletwo:ps2/src/dng_main.cpp:3039-3068
- Town and dungeon gating: `SetEnvUserDataMan(TOWN)` disables ROBO and MONSTER changes; `DUNGEON` enables them. chronicletwo:ps2/src/userdata.cpp:4714-4727
- `CheckEnableCharaChange` requires: Max or Monica with HP above zero and no STOP or STONE status; the Ridepod with its own HP and Max alive; the monster with Monica alive. Floor flags `DNG_FLOOR_DISABLE_MAX` (1) and `DNG_FLOOR_DISABLE_MONICA` (2) block them indirectly: `CheckEnableCharaChange` takes its `allowed` bit from `GetEnableCharaChangeFlag`, which masks Max and the Ridepod under flag 1 and Monica and the monster under flag 2. The flags are also reported in `out` as a reason. chronicletwo:ps2/src/userdata.cpp:3053-3135, 3216-3240; chronicletwo:ps2/include/scenesnd.hpp:89-90
- The party-bit table in `GetEnableCharaChangeFlag` tests the Monica bit for the MONSTER entry, so the monster form is available when Monica is in the party and the change is enabled. chronicletwo:ps2/src/userdata.cpp:3216-3222
- Menu gate: `InitMainCharaBG` refuses the change unless `QUICK_CHANGE_STATE_ENABLED` (0x2) is set, then calls `SetActiveChrNo`. chronicletwo:ps2/src/menuchr.cpp:6181-6210; chronicletwo:ps2/include/userdata.hpp:93-96
- Menu open types: `MENU_OPEN_CHARA_CHANGE` (4, town), `MENU_OPEN_CHARA_CHANGE_DUNGEON` (14), `MENU_OPEN_MAIN_CHARA_BG_DUNGEON` (21, the dungeon ride or partner screen). chronicletwo:ps2/include/menumain.hpp:91,101,108
- Human body model name: `c01_base<N>.chr` for Max with `N = clamp(melee.model_no, 0, 3) + 2`; `c02_base<N>.chr` for Monica with `N = clamp(melee.model_no, 0, 3)`. Edit mode uses the unnumbered name under `chara/`. chronicletwo:ps2/src/userdata.cpp:1710-1750; chronicletwo:ps2/src/userdata.cpp:1696-1708
- Action script per character is hard-coded: `mainchr/c01.stb` for Max, `mainchr/c02.stb` for Monica, `dungeon/act_script/robo.stb` for the Ridepod, a per-monster script for monster forms. chronicletwo:ps2/src/charasetup.cpp:219,289,336,~350-357
- Attachment frame names that the model rig exposes: Max melee `ef00`, gun `gun_hand`, hat `hat`; Monica melee `sword_hand`, sub `wr`, hat `ac`. chronicletwo:ps2/src/charasetup.cpp:186,197,210,259,271,280
- Equipment file paths follow the item type: weapons and costumes from `mainchr/`, ridepod parts from `dungeon/robo/`, everything else from `item/`. Menu weapon icons use `wep_t/<name>_item.chr`. chronicletwo:ps2/src/gamedata.cpp:1507-1548
- Sound bank: Max's bank follows his gun item (IDs `0x16`..`0x28` map to `snd2/chara/CH_0xx.snd`), Monica's is fixed at `CH_020.snd`, the Ridepod's follows its arm name, but that branch is unreachable as written (see Risks). chronicletwo:ps2/src/charasetup.cpp:108-138
- Default kit per human, five entries (order inferred to match `CHARA_EQUIP_SLOT`: melee, sub, head, feet, clothes): Max `0x1, 0x16, 0x6F, 0x75, 0x102`; Monica `0x29, 0x5B, 0x7B, 0x81, 0x107`. Language group 1 uses `0x104` for Max's clothes. chronicletwo:ps2/src/userdata.cpp:4730-4751; chronicletwo:ps2/include/userdata.hpp:228-234
- The community wiki identifies the Battle Wrench as Max's starting melee weapon (`docs/fandom/Battle_Wrench.wiki`). That fits item `0x1`, but the ID-to-name table is not in the extracted text (see Open questions).
- Sword trail texture is picked per character by `blur_type` (Max 0 gives texture offset 64,0; Monica 1 gives 0,0; the Ridepod arm gets the default 0,32). chronicletwo:ps2/src/maintex.cpp:279-300; chronicletwo:ps2/src/charasetup.cpp:202,263,326
- The Ridepod is assembled into six scene slots: leg (0), arm (1), body (2), mints (3, Max riding), back pack (4), hat/cap (5). chronicletwo:ps2/src/charasetup.cpp:593-666; chronicletwo:ps2/include/charasetup.hpp:20-30
- Max's riding body model name is chosen by his clothing item and body type (+10 once `SAVE_FLAG_COSTUME_UNLOCK` is set). chronicletwo:ps2/src/charasetup.cpp:668-741
- Ridepod status is its own record `robo_data` (energy `hp`, absorption `abs`, four parts ARM/BODY/PACK/LEG). Energy drains per step at `0.006 * used / capacity`. chronicletwo:ps2/include/userdata.hpp:260-282; chronicletwo:ps2/src/userdata.cpp:5025
- Monster form is driven by badges: `CMonsterBox` holds 64 `MOS_CHANGE_PARAM` slots (size `0x2F00`). Each badge has a level, class, progress and absorption gauge. chronicletwo:ps2/include/userdata.hpp:331-340,406-472
- The monster's combat numbers come from `mos_henge_param[57]` (base attack and defence per monster id), scaled by badge level and degree. chronicletwo:ps2/src/userdata.cpp:68; chronicletwo:ps2/src/userdata.cpp:2480-2522
- Monster HP is Monica's HP pool: for `BATTLE_CHARA_MONSTER`, `hp` points at `chara_data[MONICA].hp`. chronicletwo:ps2/src/userdata.cpp:4856 (inside `SetChrNo`)
- Monster stat rules in `RefreshParamater`: drain 0.005 per step (0.0025 with badge 12); attack, durability and defence all scaled by 1.25 with badge 11. chronicletwo:ps2/src/userdata.cpp:5042-5058
- Monster selection in the menu calls `SetActiveChrNo(USER_CHARA_MONSTER)` and writes `monster_id`. chronicletwo:ps2/src/menuchr.cpp:4799-4800
- The badge box (`ITEM_ID_BADGE_BOX = 0x134`) adds the MONSTER bit to `GetNowPartyMember`, and `gcMONSTER` joins the monster to the party. chronicletwo:ps2/include/gamedata.hpp:112; chronicletwo:ps2/src/userdata.cpp:3026-3034; chronicletwo:ps2/src/mainloop.cpp:2014-2028
- Monster body quirk: `SetupMonster` sets `chara_type = ACTION_CHARA_MONSTER`, but `SetupMainUnit` overwrites it with `ACTION_CHARA_MAX` afterward. chronicletwo:ps2/src/charasetup.cpp:366-367,759
- Script-visible character API: `ACTION_EXT_CHECK_EQUIP` (31) reads `GetCharaDataPtr(chara_type)->equip` with no NULL check. chronicletwo:ps2/src/actscript.cpp:426-436; chronicletwo:ps2/include/actscript.hpp:23-113
- Party NPCs (townspeople): 32 party slots, `party_chara[32]`, each `PARTY_CHARA_INFO` with an id and status bits. chronicletwo:ps2/include/userdata.hpp:768-776,1159
- `NowPartyCharaID` returns the first in-party townsperson (1-based), and the battle view caches it as `now_npc`. chronicletwo:ps2/src/userdata.cpp:3624-3632; chronicletwo:ps2/src/userdata.cpp:4984
- Party NPC table: loaded from `npc<LanguageCode>.cfg` as `NPC_INFO` rows (id, display name, model base name, abilities, costs). Up to 180 entries. chronicletwo:ps2/src/npccfg.cpp:17-24,48-107; chronicletwo:ps2/include/npccfg.hpp:51-60
- Party NPCs have no battle body. Their models load only in events (`_LOAD_CHARA_NPC`) and as a menu portrait. chronicletwo:ps2/src/event_func.cpp:5471-5500; chronicletwo:ps2/src/menuchr.cpp:6508
- In-battle NPC effects are keyed on fixed ids. Only id 10 has an active-item heal in `UseNPCPoint`; other ids gate drops and events. chronicletwo:ps2/src/userdata.cpp:4883-4906; chronicletwo:ps2/src/monster.cpp:1151,1282,2092,2096; chronicletwo:ps2/src/runscript_opcodes.cpp:3216,3318; chronicletwo:ps2/src/dng_event.cpp:2134
- Main unit assembly needs six scene character slots: `SetupMainUnit` returns false if any of slots 0..5 is missing. chronicletwo:ps2/src/charasetup.cpp:140-156; chronicletwo:ps2/src/scene.cpp:936-942
- Action scripts load as binary programs with the `SB2` magic. chronicletwo:ps2/src/runscript.cpp:233; chronicletwo:ps2/include/runscript.hpp:127,218
- PC port: data files that exist at startup can be replaced by same-path files in a datapack folder. Only indexed files are replaced; movies and sounds are not overlaid. chronicletwo:port/src/dataread.cpp:300-330; chronicletwo:port/src/platform/datapacks.hpp:24-34; chronicletwo:docs/PC.md:107-170
- PC port overrides that touch characters: `CCharacter2::DeleteExtMotion/DeleteImage` (`port/src/character.cpp`), skinned MDT (`port/src/visualmotion.cpp`), menu character buffers (`port/src/menuchr.cpp`), active icon copy (`port/src/menu_icons.cpp:57`), eye view (`port/src/dungeon_eye.cpp:8`), base stack array (`port/src/dng_main.cpp:7`). Overrides follow the `PORT_OVERRIDE` rule in chronicletwo:docs/PC_PORT_PLAN.md (section 3.3).
- No Toan identifiers appear in the ChronicleTwo source or the extracted text data. (Source checked; extracted text data unverified.) Toan is Dark Cloud's protagonist (`docs/fandom/Toan.wiki`).

## How it works

### Roster and the active character

The user-data manager owns the roster: two human records, one Ridepod record, the monster badge box and the party bits. `active_chr_no` names the character the player controls. Every switch goes through `SetActiveChrNo`, which also re-points the battle view (`CBattleCharaInfo::SetChrNo`) so that HP, equipment and the monster's combat numbers come from the right record (userdata.cpp:3409-3416, 4812-4860).

Two separate permissions decide whether a switch may happen:

1. Membership and enablement. `party_member` (who has joined) and `chara_change` (who may be switched to) are bitfields. `GetEnableCharaChangeFlag` masks `chara_change` by `chara_change_mask` and by party bits (userdata.cpp:3216-3240). `SetEnvUserDataMan` flips ROBO and MONSTER on or off per town or dungeon (userdata.cpp:4714-4727).
2. Per-switch state. `CheckEnableCharaChange` checks life, status conditions, which character is alive, and the floor flags (userdata.cpp:3053-3135). `CheckQuickChange` packs the result into `QUICK_CHANGE_STATE_*` bits (userdata.cpp:3137-3202).

### Switch paths

- Dungeon, player-initiated: L3 and R3 call `ChangeSetUnit`, which maps the current id to its partner or ride target (dng_main.cpp:3039-3068). Note that it tests `CheckQuickChange` as a boolean, which is true for any non-zero state, including a character that is not enabled. The real gate is the menu's `InitMainCharaBG` check on the ENABLED bit (menuchr.cpp:6203-6208). The menu opens with `MENU_OPEN_MAIN_CHARA_BG_DUNGEON` (dng_main.cpp:2317).
- Dungeon, on exit: a ridden Max or Monica returns to Max or Monica, so the saved active character is never a Ridepod or monster after a floor (dng_main.cpp:1154-1160).
- Town, player-initiated: the party change screen (`CHR_CNG_ACTION_CHANGE`) calls `SetActiveChrNo`, then allocates the new character's stacks with the EDIT layout when the menu was opened from a town (`MENU_OPEN_MAIN_TOWN`) and with the dungeon layout otherwise (menuchr.cpp:2097-2110). The main-character background screen loads the unnumbered `chara/` variant when opened as `MENU_OPEN_MAIN_CHARA_BG` (town) and the numbered `mainchr/` variant for `MENU_OPEN_MAIN_CHARA_BG_DUNGEON` (menumain.cpp:1265-1273; menuchr.cpp:5149-5156). (Unverified: where `MenuLoadInfo.town_model` is set was not traced, so the open-type mapping is inferred.) The monster is chosen through the monster box (menuchr.cpp:4784-4800).
- Events: `_DNG_SETUP_MAIN_UNIT` rebuilds the main unit for any `chara_no`. It calls `SetupMainUnit`, reloads the item icons, loads the sound bank (bank 3 for human, 1 for the Ridepod, 0 for the monster) and sets the active id (event_func.cpp:18391-18460). `_SET_ACTIVE_CHR_NO` sets the id only (event_func.cpp:5210-5221).
- Script debug path: `gcACTIVE_CHARA` clamps its argument to Max..Monica, so the Ridepod and monster cannot be selected that way (mainloop.cpp:2079-2096).
- Title opening: Max leaves the party, Monica joins and becomes active (title.cpp:1039-1042).

### Building a playable unit (`SetupMainUnit`)

`SetupMainUnit` (charasetup.cpp:140-367) is the single place where a main unit is loaded. It takes six scene character slots, initialises them, then branches on `chara_type`:

- Max: loads the base body `c01_base<N>.chr` into `chara/` (edit) or `mainchr/` (game), calls `LoadPack(..., "info.cfg", ...)`, loads clothing as a skin, then the melee weapon into slot 1 (attached at `ef00`), the gun into slot 2 (attached at `gun_hand`), the hat into slot 3 (attached at `hat`), the feet as a second skin, and finally `mainchr/c01.stb` as the action script. It sets `chara_type = ACTION_CHARA_MAX` and `move_type = ACTION_MOVE_HUMAN` (charasetup.cpp:143-227).
- Monica: the same pattern, with `mainchr/c02.stb`, the melee weapon attached at `sword_hand` with a sword trail, the sub-item at `wr`, and the hat at `ac`. Her `chara_type` is `ACTION_CHARA_MONICA` (charasetup.cpp:228-297).
- Ridepod: loads the leg model from `dungeon/robo/<leg>.chr`, the arm, body, mints and back pack models, Max's head item as the cap from `mainchr/`, then `dungeon/act_script/robo.stb` (charasetup.cpp:298-342; hat path from charasetup.cpp:~668-741).
- Monster: loads `dungeon/monster/<model>` with its config, then `dungeon/act_script/<script>.stb` (charasetup.cpp:343-367).

Each branch first calls `GetCharaMemAllocPtr` to carve its stacks from a memory table (`mem_table`, charasetup.cpp:54-60, 398-427), then `SetupUnitMan` to attach the parts to the scene slots (charasetup.cpp:450-491). `SetupMints`, `SetupMonica` and `SetupMonster` each reset parent links, attach named parts and set the `chara_type`/`move_type` fields (charasetup.cpp:494-541, 544-590, 743-765).

The script side is a per-character binary program. `InitScript` runs the `INIT` program, then sets the main program (actionchara.cpp:3219-3228). The action character's `chara_type` tells the script which record to read; `move_type` selects the movement handler (`_RUN_MAIN_MOVE` for human and monster, `_RUN_ROBO_MOVE` for the Ridepod modes) (actscript.cpp:711-795; actionchara.hpp:28-55).

### Model naming and equipment

Max's and Monica's base bodies are picked by the melee weapon's `model_no` (`CDataWeapon::model_no`, a `u8`). That is the only way the weapon changes the body model (userdata.cpp:1696-1750; gamedata.hpp:390). The clothing, hat and feet are their own `CGameDataUsed` items and load as skins or attachments. The sound bank and sword trail follow the same character identity (charasetup.cpp:108-138, maintex.cpp:279-300).

### Ridepod assembly

`SetupRobo` takes the six slots: slot 0 is the leg (the root), slot 1 the arm (attached at the arm item's joint name, then its `ude` frame is moved onto the body's mount frame), slot 2 the body, slot 3 Max riding (`mints`), slot 4 the back pack and slot 5 the cap. Joint names come from `joint_names` (`spine`, `joint2`, `joint1`, `hat`) and from `robo_info_body` (charasetup.cpp:593-666, 768-780). `GetRoboPartsInfo` builds the `ROBO_INFO_DATA` record, with `move_type` from the leg and `attack_type` from the arm (charasetup.cpp:668-741). Ridepod energy and absorption come from `robo_data`, not from Max's record (userdata.cpp:5025).

### Monster form

Monica's monster is a `CActionChara` with the monster's model and script loaded into the same main unit. The monster id is stored in `monster_id`, and the model/config/script/sound files come from `GetMonsterModelFile` (menuchr.cpp:3594), which reads the monster table entry. Combat numbers come from `mos_henge_param` scaled by the badge's level, and the monster's hit points are Monica's pool (userdata.cpp:2470-2522, 4856). The transformation is gated by badges, by the badge box and by Monica being in the party (userdata.cpp:3026-3034, 3219-3222).

### Party NPCs

Townspeople are data-driven entries in `npc<lang>.cfg`. Their party state lives in `party_chara[]`, and only one is "now NPC" at a time (`NowPartyCharaID`, the first in-party entry). They do not walk into battle. Their models are loaded for events (`_LOAD_CHARA_NPC` loads `chara/<model>.chr` or `event/train/t<model>.chr`) and their face or portrait is loaded for menus (menu/npc/t<model>.chr) (event_func.cpp:5471-5500; npccfg.cpp:152-192). Gameplay effects are small and keyed on ids (userdata.cpp:4883-4906; monster.cpp:1151-2096).

### PC port layer

The port compiles the retail units unchanged and replaces hardware-bound definitions with `PORT_OVERRIDE` definitions in `port/src` (chronicletwo:docs/PC_PORT_PLAN.md section 3.3). For characters this means the motion and texture cleanup on `CCharacter2`, the skinned-model vertex path, the menu character memory partitions (a per-id capacity table covering ids 0..3), the active icon copy, and the eye-view reset. The data reader indexes the game data at startup and lets datapacks replace any indexed file (dataread.cpp:300-330).

## Ixion hooks

1. Visual-only identity swap in Monica's slot, no code. Put replacement files at the same relative paths under a datapack folder (`mainchr/c02.stb`, `chara/c02_base.chr`, `mainchr/c02_base0..3.chr`, the `c02fuku*` clothing, the NPC `.chr` files). This uses the existing overlay rule in `port/src/dataread.cpp:300-330` and `docs/PC.md:107-170`. It only works for files that already exist in the data index, so new files need stubs at existing names. Motion names and frame names in the replacement must match what `c02.stb` expects.
2. Code-level identity swap in Monica's slot. `SetupMainUnit`, `GetMainCharaModelName` (userdata.cpp:1710) and `GetCharacterSnd` (charasetup.cpp:108) are non-static retail functions, so `port/src` can `PORT_OVERRIDE` them to redirect the Monica branch to another character's `.stb`, `.chr` and sound bank. Save layout, party bits and the roster stay unchanged. Monica-specific hooks (monster form, Atlamillia frames keyed on `c02_base.chr`, event scripts that name id 1) would still act on the substitute. The Atlamillia debug toggle is keyed on file names (event_func.cpp:3777-3781), and it calls `AtraMiriaOnOff` (mapselect.cpp:1116).
3. A third human record (true new playable character). This needs the full list, and it is the expensive path:
   - enum: append `USER_CHARA_*` as id 4 (`userdata.hpp:20-26`) and widen `chara_change_mask` from `u8` (`userdata.hpp:1163`);
   - storage: grow `chara_data[2]` and the save assert (`userdata.hpp:1153, 2180`);
   - accessors: `GetCharaDataPtr` (`userdata.cpp:2836`), `GetCharaHpGage` (2844), `GetCharaStatusAttirbutePtr` (3247), `CBattleCharaInfo::SetChrNo` range test `USER_CHARA_MAX <= chr_no && chr_no < USER_CHARA_ROBO` (4822);
   - switching: the three hard-coded pairs in `ChangeSetUnit` (dng_main.cpp:3044-3067), the `CheckEnableCharaChange` and `CheckQuickChange` branches, the party-bit table (userdata.cpp:3219-3222) and the dungeon-exit reset (dng_main.cpp:1154-1160);
   - assembly: `GetCharaMemAllocPtr` switch and a new `mem_table` row (charasetup.cpp:54-60, 398-427), `SetupMainUnit` and `SetupUnitMan` branches (charasetup.cpp:140-367, 450-491), `ACTION_CHARA_TYPE` (actionchara.hpp:28-34);
   - sound: `GetCharacterSnd` branch (charasetup.cpp:108-138);
   - menus: the face loop over `USER_CHARA_NUM` (menuchr.cpp:1062-1072), the port capacity table (`port/src/menuchr.cpp`) and icon copy (`port/src/menu_icons.cpp:57`);
   - new script: a new `.stb` program and any new `ACTION_EXT` calls, which are a fixed C++ table (actscript.hpp:23-113).
4. Toan as the Ridepod pilot (`ixion:docs/DESIGN.md` table row 16). Max's melee-and-clothing identity is baked into the Ridepod's rider model (charasetup.cpp:668-741), and `ROBO` requires Max alive (userdata.cpp:3053-3135). A Toan pilot needs a new rider model branch in `GetRoboPartsInfo` and a relaxed Max-alive test, plus a new rider `.chr`. This is Phase 4 content crossover in the design doc, not a data-only change.
5. Toan's sword as Monica's kit (`ixion:docs/DESIGN.md` class map). Monica's melee is `CHARA_EQUIP_MELEE` (userdata.hpp:229), and her body model follows the melee `model_no` (userdata.cpp:1710-1750). A carried loaner weapon can take Monica's sword line by copying its `model_no` and pallet, which is a data-side choice; the sword trail is tied to the character id, not the weapon (maintex.cpp:279).
6. Monster forms with Dark Cloud stats (`ixion:docs/DESIGN.md` item 4). The combat numbers come from `mos_henge_param` (userdata.cpp:68, a fixed 57-row table), so new rows are a code-table edit. The model still has to be a DC2-format monster under `dungeon/monster/`, so a Dark Cloud monster needs asset conversion first.
7. Portrait-only passenger (`ixion:docs/DESIGN.md` Phase 1). The party-NPC path loads a menu portrait without a battle body (menuchr.cpp:6508; npccfg.cpp:152-192). A Toan visitor could be a `NPC_INFO` row with a `menu/npc/t<model>.chr` portrait and no body. Only ids 1..31 pass the event loader (event_func.cpp:5480-5484) and ids 1..32 pass the path function (npccfg.cpp:152-160), so ids must stay in that range.
8. Script seam. The character's behaviour is its `.stb`. Ixion can stage a new actor by giving it a script that uses only the existing `ACTION_EXT` calls, since adding a call means C++ (actscript.hpp:23-113).

## Risks and blockers

- Save layout: `CUserDataManager` is a fixed-size record with a static assert (userdata.hpp:2180). Any new human record or wider roster field changes the save format and invalidates existing saves unless it lives in a side table.
- NULL record access: `GetCharaDataPtr` returns NULL for ids 2 and 3, and `_CHECK_EQUIP` dereferences the result with no check (actscript.cpp:426-436). Any script that calls `ACTION_EXT_CHECK_EQUIP` on a character whose `chara_type` is ROBO crashes. The monster body is saved as `ACTION_CHARA_MAX` (charasetup.cpp:366), so it avoids this, by accident rather than design.
- Missing switch default: `GetCharaMemAllocPtr` has no `default` case, so `row` and `count` are uninitialised for an unknown `chara_type` (charasetup.cpp:398-427).
- Sound lookup on a NULL record: `GetCharacterSnd` reads `chara->equip` (charasetup.cpp:109-110) before it checks the unit, and `GetCharaDataPtr` returns NULL for the Ridepod and the monster (userdata.cpp:2836-2842). Passing id 2 or 3 is therefore undefined behaviour, and the Ridepod arm-name branch (charasetup.cpp:132-135) can never run as written. Any other non-Max, non-Monica id writes nothing, so the caller's `sound_path` keeps its old contents. `_DNG_SETUP_MAIN_UNIT` passes that buffer to `LoadFile` (event_func.cpp:18443-18444).
- Move-type collision: `ACTION_MOVE_MONSTER` and `ACTION_MOVE_ROBO_BIKE` are both `3` (actionchara.hpp:40-55). A monster script that calls the Ridepod move dispatcher would enter the bike handler.
- Monster `chara_type` quirk: the value set by `SetupMonster` is overwritten (charasetup.cpp:366 versus 759). Any code that reads `chara_type` to mean "monster" sees `ACTION_CHARA_MAX` for the monster body.
- Gate ordering: `ChangeSetUnit` treats any non-zero `CheckQuickChange` result as allowed, so the ENABLED check happens only later in the menu (dng_main.cpp:3044-3067; menuchr.cpp:6203-6208). A new character inherits that order.
- Port menu table: `MenuMemoryAdjust` (port/src/menuchr.cpp) has capacity rows for ids 0..3 only. Any other id falls through with zero capacities and no buffer assignment, so its menu stacks are left stale rather than sized.
- Chunked model files: the extracted PAL data has `c01_base0..c01_base4.chr` only. Max's formula gives `c01_base2..c01_base5`, so a melee weapon with `model_no` 3 would reference `c01_base5.chr`, which is not in the extracted tree. Whether such a weapon exists is unverified.
- Datapacks replace files, not formats. A replacement `.chr` or `.stb` must match the loader's pack layout, and only files already in the index are overlaid (docs/PC.md:160-170).
- Monica-coupled logic: monster form, Atlamillia toggles and floor flags all name Monica by id. A Monica-slot substitute inherits all of them.
- Design conflict: Phase 0 of the design says "no model crosses" (ixion:docs/DESIGN.md section 4); a playable Toan needs the content crossover of Phase 4. Keep the first slice on the loaner-weapon route.

## Open questions

- Which melee weapons have `model_no` 3, and does `c01_base5.chr` exist in another archive? The ID-to-name table is in the item script loaded from the game's data archive, and is not in the extracted text.
- Do any ridepod or monster `.stb` files call `ACTION_EXT_CHECK_EQUIP` (31)? The scripts are binary and were not decoded.
- Are DC2's `info.cfg` packs and DC1's `base.cfg` packs interchangeable for a Toan body, or do they need conversion? (DC1 side: ixion:docs/research/c1-characters.md.)
- How the menu's end-of-change handler reloads the scene slots (the `MENU_ETC_FLAG_CHARA_RELOAD` consumer, menumain.cpp:1328-1346) was not traced to the end.
- Is the monster `chara_type` overwrite (charasetup.cpp:366) intentional? If scripts depend on `ACTION_CHARA_MAX` for monsters, a fix would change them.
- Every entry of `monster_progress_tbl` (menuchr.cpp:7909-7928) should have a `mos_henge_param` row; this was not checked against all 57 rows.
- The meaning of the `atoramiria` and `himo` frames (toggled by `AtraMiriaOnOff`, mapselect.cpp:1116) is inferred as the Atlamillia strap and glow. Not confirmed against the models.
