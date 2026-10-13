# Chronicle (DC1) dungeons and floors

## What this covers

How the DC1 decomp (repo "Chronicle") runs a dungeon: the seven dungeon IDs, how a dungeon is entered and a floor chosen, how the floor's event script picks its map file and layout type, how random and free floors are built, back floors, exits and game over, and the state a jump has to set. It ends with the concrete path for Ixion to enter dungeon D at floor F.

Evidence: the decomp's `ps2/src` and `port/src` (read only), the PAL event scripts (`dun/script/d01..d07/event.stb`) decoded with the DarkCloud-Toolkit STB reader, and community notes. Nothing was built or run. The floor-to-layout table comes from stepping the floor-entry script on paper and in a small reader-based interpreter, not from a running game. Inference is labelled.

## Key facts

- Dungeons are the `Dungeon` enum, IDs 0 to 6, in `selectMapNo` order (`chronicle:ps2/include/dungeon.h:1-12`). `DUNGEON_COUNT` is 7.
- A dungeon is entered through map number 200 + D. `NextMapNo` in 200..299 selects `GAME_MODE_DUNGEON` and sets `main_select_menu_no = NextMapNo - 200` (`chronicle:ps2/src/main.cpp:982-996`). `MapJump(map, event)` only stores `NextMapNo` and `StartEventNo` (`chronicle:ps2/src/main.cpp:1053-1056`).
- `GameInit()` (retail `GameInit`, `chronicle:ps2/include/dun/gameloop.hpp:301`) takes the dungeon from `main_select_menu_no` (`chronicle:ps2/src/dun/gameloop.cpp:1414`), takes `UserStatus` from `SaveData->GetDngStatus()` (`:1415`), and writes `cur_georama = selectMapNo` (`:1434`).
- `GameInit()` ends by calling `SetNowFloor(0)` (`:1949`), setting `prev_floor = -1` (`:1953`), loading the dungeon's event script with `BtSystemScriptLoad(selectMapNo)` (`:1969`), and setting `BtEventInfo.script_no = 100` with `gameTask = GAME_TASK_SCRIPT_START` (`:1972-1975`). Script 100 of that `event.stb` is the floor-entry script.
- `BtSystemScriptLoad(floor)` reads `dun/script/d0<floor+1>/event.stb`, so its argument is the dungeon ID (`chronicle:ps2/src/btsysscript.cpp:95-111`).
- The floor is chosen in the entrance window. Script `_OPEN_ENTRANCE_WINDOW` stores an out-pointer and sets `BT_REQUEST_ENTRANCE_WINDOW` (`chronicle:ps2/src/btsysscript.cpp:597-605`). The game loop then calls `InitDunEnterMenu(0x17, selectMapNo, -1)` (`chronicle:ps2/src/dun/gameloop.cpp:4551-4554`). When the menu returns, the loop writes the floor to the out-pointer and calls `SetNowFloor(floor)` (`:2006-2017`).
- `InitDunEnterMenu` has a direct path: when `requested_floor >= 0` it skips the list and returns that floor (`chronicle:ps2/src/menu_dungeon.cpp:456-459`; result at `:598-601`). No retail caller passes a floor. Both callers pass -1 (`chronicle:ps2/src/dun/gameloop.cpp:4553`, `chronicle:port/src/dun/movechara.cpp:1812`).
- `InitDunEnterMenu` calls `SaveData->QuestDungeon(dungeon, 1)` on every entrance (`chronicle:ps2/src/menu_dungeon.cpp:437`).
- Floor state lives in `CDngStatusData`, a `CUserStatus`: `cur_georama` (the dungeon), `cur_floor`, `prev_floor`, and `floor_reached[7]` (`chronicle:ps2/include/userstatus.hpp:82-97`). `SetNowFloor(f)` sets `prev = cur`, `cur = f`, and raises `floor_reached[cur_georama]` to `f` if that is higher (`chronicle:ps2/src/dngstatusdata.cpp:36-44`).
- The script's `GET_OLD_FLOOR_LEVEL` (ext 1012) returns `prev_floor` (`refs/DarkCloud-Toolkit/docs/DC_STB_EXTERNALS.md`, entries 1010 to 1012). Because `GameInit` sets `prev_floor = -1`, a fresh dungeon entry always sees an old floor of -1. That sends script 100 into the entrance window.
- `SET_DUNGEON_MAP(name, type)` stores the map file name and the layout type (`chronicle:ps2/src/btsysscript.cpp:623-628`). `LOAD_DUNGEON_MAP2` reads `dun/mpd_pack/<name>.mpd` and `dun/<name>.cfg` (`:631-636`; `chronicle:ps2/src/shot_freefuncs.cpp:1215`, paths at `:1310-1316`).
- `SET_RANDOM_MAP` calls `BtCleatRandomMap()` when the layout type is 1, and `BtCleatFreeMap()` otherwise (`chronicle:ps2/src/btsysscript.cpp:644-650`).
- `BtCleatRandomMap()` builds the front floor with `buildRandomMap(6, 1)` (`chronicle:ps2/src/dun/gameloop.cpp:6382`) and also builds a back floor into `UraDungeonMap` with `buildRandomMap(6, 0)` (`:6432`). `BtCleatFreeMap()` builds no back floor (`:6454`).
- Back floors are requested with `BT_REQUEST_URA_DUNGEON` (from `SET_URA_DUNGEON`, ext 1036). `GAME_TASK_URA_SWAP` then switches `NowDngMap` to `UraDungeonMap` (`chronicle:ps2/src/dun/gameloop.cpp:4547-4548`, `:4616-4633`).
- Exits go to a town map chosen per dungeon in `GAME_TASK_EXIT_FADE_WAIT` (`chronicle:ps2/src/dun/gameloop.cpp:4886-4917`). Game over also leads there, after `SetDead()` (`:5630-5670`).
- The debug loader lists the seven dungeons by the names in `MapInfoNameArea` and jumps to `selectMapNo + 200` (`chronicle:ps2/src/dun/gameloop.cpp:9471-9476`, `:9578`).
- The PC port's `--jump dungeon:<n>` sets `selectMapNo` and `main_select_menu_no` to n and calls `MapJump(200 + n)` (`chronicle:port/src/gameloop.cpp:353-372`; `GameSetJump` at `:571`). It starts at the floor-select menu, not at a chosen floor (`docs/PC.md`, "Test hooks").
- `BtSetMapJumpFloor` writes `BtMapJumpFloor` (`chronicle:ps2/src/btsysscript.cpp:43`, `:261-262`). Dungeon scripts read it through `GET_DUNGEON_FLOOR` (ext 22; the table is at `chronicle:ps2/src/editloop3.cpp:7999-8000`, the handler at `:3625`). Of the seven dungeon scripts, dungeons 2, 3 and 5 branch on it and skip the entrance window when it is set. Dungeon 6 reads it without branching (unverified). Dungeons 0, 1 and 4 never read it. The town reset clears it (`chronicle:ps2/src/editloop.cpp:1121`), and so does `BtSystemScriptAfter` (`chronicle:ps2/src/btsysscript.cpp:222`). Retail scripts do call `SET_DUNGEON_FLOOR` (ext 21), which the earlier draft missed. In `d04` (dungeon 3) it is set to -1 right after the `GET_DUNGEON_FLOOR` read. In `d06` (dungeon 5) it is set to 24 (`25 - 1`) on two paths. The ext 21 call sites are at `d04` offset 0x0309cc and `d06` offsets 0x02dc50 and 0x02ddd0. The triggers for the `d06` paths were not traced (disassembly of the PAL `event.stb` files with the toolkit's `dis.mjs`).
- Floor counts agree in two places: `maxFloorTbl__4 = {15,17,18,18,15,25,100}` (`chronicle:ps2/src/menu_dungeon.cpp:100`) and `MaxFloorTbl[6] = {15,17,18,18,15,25}` (`chronicle:ps2/src/dungeonparts.cpp:1513`).
- Gallery of Time (dungeon 5) shows year labels through `BtGetFloorLevel` (`chronicle:ps2/src/btmisc.cpp:337-344`; used at `chronicle:ps2/src/menu_dungeon.cpp:1230-1231` and `chronicle:ps2/src/dun/gameloop.cpp:2766-2767`).

## How it works

### Dungeon IDs and fixed data

| D | Enum (`dungeon.h`) | Debug name (`MapInfoNameArea`) | Dark Cloud name (fandom) | Entry map | Floors | Exit map (`MapJump`) | Gate key item (random floors) |
|---|---|---|---|---|---|---|---|
| 0 | DIVINE_BEAST_CAVE | Cave of the Sacred Beast | Divine Beast Cave | 200 | 15 | 0 | `ITEM_DRAN_S_CREST` |
| 1 | WISE_OWL_FOREST | Forest of the Own | Wise Owl Forest | 201 | 17 | 1 | one of 0xC4, 0xC6, 0xCD |
| 2 | SHIPWRECK | Sunken Ship | Shipwreck | 202 | 18 | 0x13 | `ITEM_HOOK` |
| 3 | SUN_MOON_TEMPLE | Shrine of Sun and Moon | Sun and Moon Temple | 203 | 18 | 0x2A | `ITEM_KING_S_SLATE` |
| 4 | MOON_SEA | MoonOcean | Moon Sea | 204 | 15 | 0x17 | `ITEM_GUN_POWDER` |
| 5 | GALLERY_OF_TIME | DarkHeven Castle | Gallery of Time | 205 | 25 | 0x26 | `ITEM_CLOCK_HANDS` |
| 6 | DEMON_SHAFT | Deamon Shaft | Demon Shaft | 206 | 100 | 0x3C | `ITEM_BLACK_KNIGHT_CREST` |

Sources: enum and comment (`chronicle:ps2/include/dungeon.h`); names (`chronicle:ps2/src/dun/gameloop.cpp:9471-9476`); floor counts (`chronicle:ps2/src/menu_dungeon.cpp:100`); exit map numbers (`chronicle:ps2/src/dun/gameloop.cpp:4894-4912`); gate keys (`chronicle:ps2/src/dungeonmap.cpp:3617-3644`). Dark Cloud names are from `docs/fandom/Dungeon.wiki` in the Dark-Cloud-3 repo. The exit numbers are `MapNo` values; 0 and 1 are towns, and the others are sub maps (`docs/PC.md`, "Test hooks", on the `edit:<map>` numbering).

`gate_key_no` is set only in `buildRandomMap` (`chronicle:ps2/src/dungeonmap.cpp:3617-3644`). The gate key of a free floor was not traced. For dungeon 1 the key is picked at random among three items.

Atla rules are per dungeon. `noEntryTbl` lists the floors that never hand out Atla (`chronicle:ps2/src/dungeonparts.cpp:1489-1505`), and `chkAtraFloor` and `BtAtraListMake` use it (`:1889`, `:1919`). `BtAtraListMake` runs on a first visit, when `floor_reached[dungeon] == -1` (`chronicle:ps2/src/dun/gameloop.cpp:1887-1888`).

### Entry: town to dungeon to floor

1. A town map jump leads to 200 + D. Town jump points are door entries (`EPARTS_FUNC_DOOR`) found by `SearchMapJump` (`chronicle:ps2/src/edit_in.cpp:1416`), and their `map_no` comes from `MAPJUMP` (`chronicle:ps2/src/editmapscript.cpp:1634-1647`). In the extracted town scripts, the `MAP_JUMP` calls with constant arguments are all small numbers (map 0 to 4 and one 1000 for the ending), so dungeon entries are probably data-driven jump points (inference).
2. The main loop switches to `GAME_MODE_DUNGEON` (`chronicle:ps2/src/main.cpp:982-996`) and runs `GameInit` (`chronicle:ps2/src/main.cpp:694`; `GameInit` is `DUN.BIN`'s `GameInit`, `chronicle:ps2/include/dun/gameloop.hpp:301`).
3. `GameInit` sets up dungeon state, loads the event script, and starts script 100 (`chronicle:ps2/src/dun/gameloop.cpp:1405-1975`).
4. The GameLoop tick runs script 100 (`GAME_TASK_SCRIPT_START`, `chronicle:ps2/src/dun/gameloop.cpp:4455`).
5. Script 100 reads `GET_FLOOR_LEVEL` and `GET_OLD_FLOOR_LEVEL`. If the old floor is -1, it opens the entrance window and takes the floor the player picks. Otherwise it treats the floor as the current floor plus one and calls `SET_FLOOR_LEVEL`. This is read from the decoded bytecode of `dun/script/d01/event.stb`, script 100, instructions 21290 to 21330 (unverified for the instruction range); the other six scripts have the same shape (confirmed for d03, d04 and d06 at the `GET_OLD_FLOOR_LEVEL` and `GET_DUNGEON_FLOOR` branch, and in the `ext 2` listing).
6. The script then calls `SET_DUNGEON_MAP(name, type)` for the chosen floor, calls a loader subroutine that includes `LOAD_DUNGEON_MAP2`, then calls `SET_RANDOM_MAP`, `LOAD_MONSTOR`, and finally `GO_DUNGEON` (decoded bytecode, same script).
7. `GO_DUNGEON` sets `BT_REQUEST_GO_DUNGEON`. The game loop then runs `BtSystemScriptAfter()`, clears gate keys, shows the limit-zone message if one applies, and sets `GAME_TASK_PLAY` (`chronicle:ps2/src/dun/gameloop.cpp:4561-4590`).

### Floor-to-layout table

Stepping script 100 of each dungeon's `event.stb` for each floor index, with the entrance window answered by that floor, gives the map name and layout type the script leaves set (unverified: the per-floor table was not re-stepped in this check). Type 1 is procedurally built (`SET_RANDOM_MAP` calls `BtCleatRandomMap`). Types 0 and 2 use a fixed `.mpd` layout through `BtCleatFreeMap`.

- Dungeon 0 (15 floors): main_a (1) on 0 to 2 and 4 to 6; inter2 (0) on 3; inter (0) on 7; main_b (1) on 8 to 13; boss (2) on 14.
- Dungeon 1 (17): main_a on 0 to 7; inter (0) on 8; main_b on 9 to 15; boss (2) on 16.
- Dungeon 2 (18): main_a on 0 to 7; inter (0) on 8; main_b on 9 to 15; main_c (1) on 16; boss (2) on 17.
- Dungeon 3 (18): main_a on 0 to 7; inter (0) on 8; main_b on 9 to 16; boss (2) on 17.
- Dungeon 4 (15): main_a on 0 to 6; inter (0) on 7; main_b on 8 to 13; boss (2) on 14.
- Dungeon 5 (25): main_a on 0 to 5; main_b on 6 to 11; main_c on 12 to 17; main_d on 18 to 23; boss (2) on 24. Script 100 also tests local variable 4 for a value of 2 to choose a second boss map, `d06boss2`, on floor 24 (unverified). The code that sets variable 4 was not traced.
- Dungeon 6 (100): main_a on 0 to 19; main_b on 20 to 39; main_c on 40 to 59; main_d on 60 to 79; main_e on 80 to 97; main_f (1) on 98; boss (2) on 99.

Map names are the `dun/mpd_pack/<name>.mpd` and `dun/<name>.cfg` pairs (for example `d01main_a`). The table is from the PAL scripts. Method: the floor-entry function was stepped with a small interpreter over the `parse()` output of `refs/DarkCloud-Toolkit/app/stb/format.mjs`, using the VM rules in `refs/DarkCloud-Toolkit/docs/DC_STB_FORMAT.md` (EXT takes its function number from the first of its stack items) and `refs/DarkCloud-Toolkit/app/stb/dis.mjs` (`stackDelta`: a JZ or JNZ whose `b` flag is set does not pop). Calls to other subroutines were not stepped. The branch conditions for dungeon 0 were also checked by hand. The conditions use only the floor variable and the variable-4 flag above.

### Floor build

- Random floor (layout type 1): `buildRandomMap(room_max = 6, first_build)` (`chronicle:ps2/src/dungeonmap.cpp:3439`). On a first build it picks a seed from `rand()` and seeds the generator with it (`:3455-3458`). It clears event, box and Atla slots, places rooms on the 20 by 20 cell grid (room loop from `:3483`), joins room pairs, places room objects (`:3574`), dividers (`:3576-3577`), the under-dungeon start (`:3580-3583`), and stairs (`:3586-3587`), all of the last three only on a first build. It then filters the map parts (`:3590`), and on a first build, with about 51% chance, links rooms with a door and item (`GetRoomLinkInfo`, `:3606-3607`). It sets up character doors (`BuildCharaSpecialParts`, `:3610-3611`; the port overrides this, `chronicle:port/src/dungeonmap.cpp:28`), sets the gate key (`:3617-3644`), and calls `SetUnderLoad` (`:3647`).
- Free floor (layout type 0 or 2): `BtMapJumpLoad` reads the `.mpd` layout (`chronicle:ps2/src/shot_freefuncs.cpp:1215`). `BtCleatFreeMap` then calls `buildEventData(cur_floor, map_type, 1)` and `SetupEvent` on the floor's event manager (`chronicle:ps2/src/dun/gameloop.cpp:6454-6486`).
- Events and items per floor come from `buildEventData` (`chronicle:ps2/src/dungeonmap.cpp:2414`), which uses `PresetSmallItemNo_Get` and `BtAtraFloorCyoice`. The port overrides `PresetSmallItemNo_Get` (`chronicle:port/src/dungeonparts.cpp:21`).
- Monsters: `BtLoadMonstor(ura)` takes the row of `BtEnemyLayoutList[selectMapNo]` (or `BtUraEnemyLayoutList`) indexed by `cur_floor` (`chronicle:ps2/src/dun/gameloop.cpp:6492-6545`). Each row is a `BT_ENEMY_FLOOR` of 0x70 bytes with up to nine entries (`chronicle:ps2/include/monstorunit.hpp:568-595`). The tables are data in the executable and are not in the decomp source.
- `BtMapJumpLoad` skips the reload when the same map name is already cached in `BtCfgCash` (`chronicle:ps2/src/shot_freefuncs.cpp:1268`). `BtMapJumpCashClear` runs in `GameInit` (`chronicle:ps2/src/shot_freefuncs.cpp:1193`; `chronicle:ps2/src/dun/gameloop.cpp:1944`).

### Back floors

- A back floor is requested by an event: the `SET_URA_DUNGEON` call sits in a helper subroutine that is called from dungeon event entry 200 in dungeons 0, 1, 2, 3, 5 and 6, and from entry 201 in dungeons 3 and 4 (decoded bytecode) (unverified: no ext 1036 call showed up in the `d06` disassembly, so the entry list was not confirmed). The helper's guard was not traced (inference).
- `GAME_TASK_URA_SWAP` toggles `BtUraDongeon`, swaps `NowDngMap` and `NowEventMan` between `MainDungeonMap` and `UraDungeonMap`, reloads the monster unit from `BtUraEnemyLayoutList` on the back side, and returns to script run (`chronicle:ps2/src/dun/gameloop.cpp:4616-4684`).
- `UraDungeonMap` is only built on random floors, as a copy of the front floor followed by `buildRandomMap(6, 0)` (`chronicle:ps2/src/dun/gameloop.cpp:6394-6444`). Whether a back floor exists on a free floor is an open question.

### Exit, escape, game over

- The dungeon ends by setting `existFlag` (1 for a map jump, 2 for an exit). `GameLoop()` returns it (`chronicle:ps2/src/dun/gameloop.cpp:2048-2082`), and the main loop then reads `NextMapNo`.
- `GAME_TASK_MAPJUMP_FADE_*` jumps to 800 (`MapJump(0x320, -1)`, `chronicle:ps2/src/dun/gameloop.cpp:4854-4866`), which the main loop routes to the title (`chronicle:ps2/src/main.cpp`, mode table after `NextMapNo`). No setter of `GAME_TASK_MAPJUMP_FADE_START` exists in `ps2/src`, so this path is reachable only from a debug or future route.
- Escape: `GAME_TASK_ESCAPE_*` runs `BtEscape_Loop`, then goes to `GAME_TASK_EXIT_FADE_WAIT` (`chronicle:ps2/src/dun/gameloop.cpp:4869-4880`).
- Exit: `GAME_TASK_EXIT_FADE_WAIT` maps the dungeon to a town or sub map (table at `:4894-4912`), then calls `MapJump(map_no, -1)` and sets `existFlag = 2` (`:4916-4917`).
- Game over: `GAME_TASK_DEAD_GAMEOVER` leads to `GAME_TASK_EXIT_FADE_START`, after `SetDead()`, which halves the money (`chronicle:ps2/src/dun/gameloop.cpp:5630-5670`; `chronicle:ps2/src/dngstatusdata.cpp:751-753`).
- The next-floor logic is in script 160 of each dungeon. In dungeon 0 it reads the floor. If a flag (local variable 6) equals 2, it sets the floor to plus one and calls `MAP_JUMP(1)` (town map 0). Otherwise it runs script 100 again with `RUN_SCRIPT_NO(100)` (ext 1061) (decoded bytecode, instructions 18856 to 18881; inference on what the flag means).

### State a jump has to set

Set before `MapJump(200 + D)`:

- `main_select_menu_no = D`, which `GameInit` reads (`chronicle:ps2/src/dun/gameloop.cpp:1414`). The port's `ApplyJump` also sets `selectMapNo` (`chronicle:port/src/gameloop.cpp:367-369`).
- A save with a dungeon status block. `GameInit` calls `UserStatus->Init()` on it, which clears event flags and drink state (`chronicle:ps2/src/dngstatusdata.cpp:723-748`).
- Optionally `BtSetMapJumpFloor(F)` for dungeons 2, 3 and 5 (see Ixion hooks).

`GameInit` sets the rest itself: `cur_georama = D`, `SetNowFloor(0)`, `prev_floor = -1`, `BtSystemScriptLoad(D)`, and `script_no = 100`. Anything Ixion sets before `GameInit` for these fields is overwritten.

## Ixion hooks

1. Dungeon ID table. Keep a per-world table from Ixion's dungeon key to D (0 to 6 for DC1) and the entry map 200 + D. This is the only place a DC1 dungeon number has to be translated. The rest of the path reads `selectMapNo`.
2. Direct jump to dungeon D, floor F (retail-faithful, recommended). Set `main_select_menu_no = D`, call `MapJump(200 + D, -1)`, and let `GameInit` run. Then change the entrance request from -1 to a pending floor F at `chronicle:ps2/src/dun/gameloop.cpp:4553` and `chronicle:port/src/dun/movechara.cpp:1812`. `InitDunEnterMenu(0x17, D, F)` then takes the direct path (`chronicle:ps2/src/menu_dungeon.cpp:456-459`). The menu still runs its short fade and returns F through `entrance_result` (`chronicle:ps2/src/dun/gameloop.cpp:2010-2015`), which calls `SetNowFloor(F)`. Side effects: `QuestDungeon(D, +1)` and a possible raise of `floor_reached[D]`.
3. Script-honoured jump for dungeons 2, 3 and 5. Call `BtSetMapJumpFloor(F)` (`chronicle:ps2/src/btsysscript.cpp:261`) before `MapJump(200 + D, -1)`. Script 100 reads `GET_DUNGEON_FLOOR` into a local and, when it is 0 or more, sets the floor and skips the entrance window. Checked for dungeon 2 (`d03`), dungeon 3 (`d04`) and dungeon 5 (`d06`). `BtSystemScriptAfter` clears the value after use (`chronicle:ps2/src/btsysscript.cpp:222`). Retail `d04` and `d06` also write this value (see Key facts), so a write made before script 100 reads it can be overwritten; the timing is an open risk (unverified).
4. Post-`GameInit` floor injection (inference, not tested). After `GameInit` returns and before the first GameLoop tick (when `gameTask` is `GAME_TASK_SCRIPT_START`), set `cur_floor = F - 1` and `prev_floor = 0`. Script 100 then takes its else branch, sets floor F, and calls `SET_FLOOR_LEVEL(F)`, which bypasses the entrance window for all seven dungeons. The else branch adds one, so `cur_floor` must be F - 1, not F.
5. Exit routing. Replace the exit table at `chronicle:ps2/src/dun/gameloop.cpp:4894-4912` to send a DC1 dungeon to a different map number, or set `NextMapNo` from GameLoop through `existFlag`.
6. Back floor entry. The back-floor request is `BT_REQUEST_URA_DUNGEON` (`chronicle:ps2/src/dun/gameloop.cpp:4547-4548`). Setting `BtEventInfo.request` directly might reach `GAME_TASK_URA_SWAP` on a random floor (inference; the request is consumed in the script-run handler).
7. Floor labels. Gallery of Time (5) shows year labels through `BtGetFloorLevel` (`chronicle:ps2/src/btmisc.cpp:337-344`). An Ixion UI that shows floor numbers should use that mapping for dungeon 5 only.

## Risks and blockers

- Dungeon ID collisions. DC1 dungeon numbers 0 to 6 are only meaningful inside DC1. DC2 has its own dungeon list, whose numbering was not checked here, so any table keyed on `selectMapNo` (`BtEnemyLayoutList`, `ItemFreeAreaAll`, `PieroItemListPtr`, `UserStatus->floor_reached`, `atra_registry`) must be kept per world. Otherwise a merged dungeon index will read the wrong world's data.
- Duplicated static tables. `maxFloorTbl__4` (`chronicle:ps2/src/menu_dungeon.cpp:100`) and `MaxFloorTbl` (`chronicle:ps2/src/dungeonparts.cpp:1513`) are `static`, so the port's `PORT_OVERRIDE` rule cannot replace them (`docs/PC.md`, "How port/src takes precedence"). Ixion has to edit or copy them.
- Overlay globals. The port links the dungeon overlay once and does not re-run its constructors (`docs/PC.md`, "Overlay re-initialisation"). Globals a jump reads (`BtMapJumpFloor`, `BtEventInfo`, `BtUraDongeon`, the `BtCfgCash` cache at `chronicle:ps2/src/shot_freefuncs.cpp:1268`, `MainDungeonMap`, `UraDungeonMap`, `DngEventMan`) keep the previous visit's values unless `GameInit` or a helper resets them.
- Save side effects. A direct entry still increments the dungeon's quest counter (`chronicle:ps2/src/menu_dungeon.cpp:437`), can raise `floor_reached` (`chronicle:ps2/src/dngstatusdata.cpp:36-44`), and creates Atla on a first visit (`chronicle:ps2/src/dun/gameloop.cpp:1887`). Testing a jump on a real save changes that save.
- Hook 4 depends on the else-branch arithmetic. A second entry without a reset would bump the floor again.
- Floor scripts load DC1 assets (`dun/d0N/...`, `dun/script/d0N/*.mes`) and the DC1 event system. Running DC2 characters on DC1 floors needs asset and script handling outside this topic.
- The table in this document is from the PAL scripts. NTSC scripts may differ. The port keeps PAL-only branches in `BtSystemScriptLoad` (`chronicle:ps2/src/btsysscript.cpp:97-115`).
- `cur_floor` and `prev_floor` are `s8` (`chronicle:ps2/include/userstatus.hpp:84-85`). That is enough for 100 floors, but any value above 127 would overflow.

## Open questions

1. Are the per-floor map names and layout types the same in the NTSC scripts? Only the PAL extract was stepped.
2. What sets local variable 4 in dungeon 5's script 100, which chooses `d06boss2` on floor 24?
3. Which floors have a back floor? The guard in the helper called from entries 200 and 201 was not traced.
4. What does script 160 (descend or leave) do in full? Which flag selects "leave", and does `RUN_SCRIPT_NO(100)` take the entrance path or the else path? A live run or a fuller trace would settle it.
5. Which retail trigger reaches the `SET_DUNGEON_FLOOR` calls in `d04` (sets -1) and `d06` (sets 24)? Retail does set `BtMapJumpFloor`, so the script-honoured jump (hook 3) is not dormant by default. Whether either call can run between a jump and script 100's read was not traced.
6. The enemy layout tables (`BtEnemyLayoutList` at 0x002917b0 and `BtUraEnemyLayoutList` at 0x002917d0, per `chronicle:ps2/config/ntsc/dun.symbols.txt` and the toolkit's `refs/DarkCloud-Toolkit/src/Archives/DcMonsterArrange.h:15-20`) hold per-floor monster lists. The toolkit lists 26 rows for dungeon 5's front table, one more than the menu's floor count of 25. Which is right for the PAL disc was not checked.
7. Does a direct floor from `InitDunEnterMenu` need a bounds check against `maxFloorTbl__4`? The retail code does not check, and the port does not add one.
