# Dark Chronicle: travelling to a town or dungeon floor at runtime

## What this covers

- How ChronicleTwo (Dark Chronicle, DC2) leaves the loop it is running and enters the town loop (`LOOP_EDIT`) or the dungeon loop (`LOOP_DUNGEON`) at a chosen map or floor, while the game runs.
- The safe point for that change (the frame end, reached on the game's fiber), and the cleanup each origin loop needs.
- Which loops and states must refuse a request, and the globals that detect them.
- How era, map numbers and save fields relate, and what an arrival needs.
- A station table: every town or field map (73 records of map types 1, 3 and 5) with its `--jump` string, era and world-map gate, and every dungeon (7) with its floor records, rooms, exit and floor specs.
- A proposal for `bool C2TravelRequest(const char *destination)` and `void C2TravelApplyAtCheckpoint()`, with the exact globals each one touches.

Basis: read-only review of the ChronicleTwo `ixion` branch (`chronicletwo:`), the extracted PAL data (`chronicletwo-data:`), and the Hop v0 ABI and spec (`ixion:`). The map, world-map and dungeon tables were parsed from the data for this document, and the counts below come from that parse. Nothing was built or run. Inference is labelled. Existing notes are cross-referenced rather than repeated: `ixion:docs/research/c2-mainloop-control.md`, `c2-towns-georama.md`, `c2-dungeons.md`, `c2-save.md`, `c2-time-travel.md`.

## Key facts

- Modes: `LOOP_MENU` 0, `LOOP_EDIT` 1, `LOOP_DUNGEON` 2, `LOOP_TITLE` 3, viewers 4 to 8, save conversion 9; `LOOP_MODE_NUM` is 10, and any other number ends the game (`chronicletwo:ps2/include/mainloop.hpp:31-42`). Dispatch arrays are at `chronicletwo:ps2/src/mainloop.cpp:100-135`.
- `NextLoop(loop, arg)` only writes `NextLoopNo` and `NextInitArg` (`chronicletwo:ps2/src/mainloop.cpp:349-352`). The switch happens when the port's inner loop breaks: `LoopExit[old]()` (`chronicletwo:port/src/mainloop.cpp:395`), then `PortLoopNo = PortNextLoopNo; InitArg = NextInitArg` (`:408-409`), then `LoopInit[new]` and `GameGiveOnArrival` (`:259-260`).
- The inner loop breaks when `LoopMain` returns non-zero (`chronicletwo:port/src/mainloop.cpp:333`, `:341-344`). `mgEndFrame` is at `:339`, so a hook placed right after it can end the current mode.
- `mgEndFrame` is not only the main loop's frame end. Its callers (grep, this pass) include the movie loop (`chronicletwo:ps2/src/event_func.cpp`, 2 sites), the loader and pause code (`chronicletwo:ps2/src/nowload.cpp`, 4 sites), menu drawing and the debug start menu (the last two unverified). A travel must be applied from `MainLoop`, not from inside `mgEndFrame`. `mgWaitFrame` is an empty port override (`chronicletwo:port/src/mglib.cpp:1374-1375`), so the call inside `EditMapJump` (`chronicletwo:ps2/src/editloop.cpp:2754`) does nothing.
- Town world move, cross-loop: sets `finish = 1` and `NextLoop(loop, {floor, map, event 1010})` (`chronicletwo:ps2/src/editloop.cpp:1370-1376`). The finish path then calls `PreExitLoop` and returns 1 (`:1397-1400`). Same-loop: `BurnEditParts(); EditMapJump(map); MainScene->RunEvent(100, NULL);` (`:1377-1380`).
- Dungeon floor 0 exit: `DngStatus.dungeon_no` indexes a fixed town table `{d01e01, s02, g02, g03, g04, d06e01, m05}`. The code sets `NextLoop(LOOP_EDIT, {town, event 100})` and `DNG_STATUS_EXIT` (`chronicletwo:ps2/src/dng_main.cpp:1078-1085`).
- Dungeon cleanup runs inside `LoopDungeonMain` when `DngStatus.mode == DNG_STATUS_EXIT`: `sgBreakSubGame`, `CheckItemDngKey`, `PlayerPartyCure` unless `DNG_PAUSE_EXIT_HEAL` (0x800, `chronicletwo:ps2/include/scenesnd.hpp:104`), clearing the seal bits, `EdEventTermination`, `BreakReadBG`, then `return true` (`chronicletwo:ps2/src/dng_main.cpp:1142-1165`). `FinishDungeonMain` is empty (`:980-981`). Breaking the loop without running that block skips the cleanup. The developer-menu path runs one extra frame in EXIT to get it (`chronicletwo:port/src/mainloop.cpp:287-292`).
- EDIT cleanup: `PreExitLoop` burns parts, saves the Georama layout, breaks sub-games, stops BGM and voice, and ends the event (`chronicletwo:ps2/src/editloop.cpp:516-527`). `EditExit` does not call it (`:959-969`). Callers are the finish path (`:1398`, `:1993`) and the developer menu (`chronicletwo:port/src/mainloop.cpp:282`). It is declared in `chronicletwo:port/src/mainloop_port.hpp:27`.
- `GamePrepareJump` is not reusable for travel. It calls `InitSaveData()` (`chronicletwo:port/src/test_hooks.cpp:172`), sets `DebugFlag = 1` (`:175`), and loads `dbg/pb.cfg` or `dbg/cap1.cfg` (`:188`, `:194`). Those files set `PROGRESS 4` and `PROGRESS 2` (`chronicletwo-data:dbg/pb.cfg`, `chronicletwo-data:dbg/cap1.cfg`).
- `--jump` grammar (`chronicletwo:port/src/test_hooks.cpp:78-123`): `town[:map]` with map 0 to 188; `dungeon[:map[:floor]]` with map 0 to 6 and floor 1 to 99 (floor 0 is rejected); `event:<id>`; `title`, `opening`, `menu`. `GameJump` defaults are map 10 and floor 1 (`chronicletwo:port/src/test_hooks.hpp:18-23`), so a bare `town` is Palm Brinks and a bare `dungeon` is dungeon 0 floor 1.
- Floor validity: `GetFloorInfoPtr(d, f)` is non-null only for `0 <= f < limit[d]`, with `limit = {9, 16, 25, 21, 23, 29, 39}` (`chronicletwo:ps2/src/savedatadungeon.cpp:13-33`; `chronicletwo:ps2/include/savedatadungeon.hpp:16-19`). The `--jump` parser uses the same check (`chronicletwo:port/src/test_hooks.cpp:98-101`).
- Map table: `map/map<LanguageCode>.cfg` is parsed at boot (`chronicletwo:ps2/src/mapselect.cpp:277-290`). The record index is the map number (`:205-264`). All seven language files hold 189 records with an identical name column (`chronicletwo-data:map/map0.cfg` to `map6.cfg`); a normal boot uses the French table (`chronicletwo:port/src/mainloop.cpp:99`), which changes only titles.
- `GetMapName` returns NULL for the empty records 5 to 8, but for a number outside the table it returns `SelectMapName`, an empty non-NULL string (`chronicletwo:ps2/src/mapselect.cpp:367-375`). `GetMapType` returns -1 outside the table (`:327-335`). `SearchMapNo` is a linear search on the name (`:385-408`). `EditInit` round-trips its map through the name (`chronicletwo:ps2/src/editloop.cpp:877`).
- `EditMapJump` (`chronicletwo:ps2/src/editloop.cpp:2713`) runs `InitEditEvent()` and `DeleteFileCache()` (`:2731-2732`) before its name check (`:2743-2748`). An in-table record with no name (5 to 8) therefore still tears down event state, and returns 0. A number outside the table passes that check because `GetMapName` is non-NULL there, and it continues with an empty name (not traced further).
- `MapJump` writes the save: `prev_map_no` gets the old main map, `map_no` the new one, `sub_map_no` and `prev_sub_map_no` get -1, and `area_no` gets the table's area when it is positive (`chronicletwo:ps2/src/mapjump.cpp:203-227`). It then calls `ResetBitCtrl(1)` (`:247`).
- `GetLoadMapInfo` reads `game_progress` for the sky (chapters 8 and 9 use the `b` sky) and for the train add-on (chapters 6 and 7 replace `trn/train` with `trn2/s36`) (`chronicletwo:ps2/src/mapjump.cpp:273`, `:285-292`, `:301-308`).
- Dungeon arrival: `InitDungeonMain` sets `stage_id = arg.map_no` (`chronicletwo:ps2/src/dng_main.cpp:345`), calls `SetFloorID(arg.floor_no)` when `floor_no >= 0` (`:347-349`), and sets `DngStatus.dungeon_no` and `DngStatus.mode = FIELD` (`:435-437`). `INIT_LOOP_ARG()` zeroes every field (`chronicletwo:ps2/include/mainloop.hpp:213-221`), so an arg that does not set `floor_no` enters floor 0.
- Entry event: a dungeon uses `arg.event_no`, or `DNG_EVENT_FLOOR_START` (1000) when it is 0 or below (`chronicletwo:ps2/src/dng_main.cpp:827-831`). A town uses 100 (`chronicletwo:ps2/src/editloop.cpp:922-926`).
- Event 1010 is used twice: the world-map dungeon entry passes it (`chronicletwo:ps2/src/editloop.cpp:1374-1375`), and the title's new game enters dungeon 0 floor 20 with event `0x3F2`, which is 1010 (`chronicletwo:ps2/src/title.cpp:1028-1032`). Its meaning at an ordinary floor is an open question.
- Time: `MainLoop` copies `now_time` and `day` from the save into the scene at each mode entry (`chronicletwo:port/src/mainloop.cpp:238-241`), and forces 22:00 when `game_progress == 2` (`:243-248`). The same copy also runs every frame outside the menu (`:304-308`), and sets the save's `now_time` to 22:00 on each such frame while `game_progress == 2` (`:310-315`). An in-place town jump skips `LoopInit`, but the per-frame copy still runs, so the scene clock follows the save after it.
- Save fields (`chronicletwo:ps2/include/savedata.hpp:214-243`): `game_progress` (s32; the chapter comes from `GetGameChapter`, `chronicletwo:ps2/src/vlgr_info.cpp:874-882`), `now_time` (float, hours), `day`, `map_no`, `sub_map_no`, `prev_map_no`, `prev_sub_map_no`, `area_no`, `edit_data[5]`, `save_dungeon`, `bit_ctrl`. The struct is asserted to 0x65930 bytes (`:504`).
- There is no era field. Era is a property of the map: `GetMapType(map_no)` is `MAP_TYPE_FUTURE` (5) or `MAP_TYPE_FUTURE_INTERIOR` (6) for future maps, and anything else is present (`chronicletwo:ps2/include/mapselect.hpp:43-49`). The consumers are the future branch of `EditMapJump` (`chronicletwo:ps2/src/editloop.cpp:2835-2857`), the time board and top-menu topic hidden on future maps (`chronicletwo:ps2/src/menumain.cpp:1769`, `:1871`, unverified), and the world-move refusal (`:2256-2267`, unverified).
- Interiors do not write the save's map fields. `GotoInterior` and `LoadSubMap` load the interior as a scene sub-map (`chronicletwo:ps2/src/mapjump.cpp:324-345`, `:459-558`). Only `MapJump` (`:203-227`) and `InitSaveData` (`chronicletwo:ps2/src/savedata.cpp:34`) write the save's `sub_map_no`, and both write -1. So the era of a player inside an interior is read from the scene's sub-map, not from the save (inference).
- Map types in the data (`chronicletwo-data:map/map1.cfg`, parsed this pass): type 0 (4 empty records), 1 (6, the Georama towns `g01` to `g05` and `s55`), 2 (17, Georama interiors), 3 (58), 4 (28), 5 (9), 6 (10), 7 (41, dungeon floors), 8 (16, dungeon basements). Type 5 includes the Central Lab interior `f03i04` and the Ixion Operations Room `s39`, so the type alone is not a clean "town" filter.
- World-map places: `POS` records are `POS id, map, loop, area, dng, floor, flag, type` (`chronicletwo:ps2/src/menumap.cpp:298-323`; `WMAP_POS_DATA` at `chronicletwo:ps2/include/menumap.hpp:117-128`). There are 30 records (`chronicletwo-data:menu/1/wldmap.cfg`). Twenty are town or field places (loop 1) and ten are dungeon entries (loop 2). Seven dungeon entries open the tree map (floor -1). Three go straight to a floor: dungeon 2 floor 18 (POS 12), dungeon 2 floor 8 (POS 13) and dungeon 3 floor 9 (POS 18).
- Future places on the world map are type 4 with flag 616. They are disabled once `SAVE_FLAG_CHAPTER_8` (0x2E0 = 736) is set (`chronicletwo:ps2/src/menumap.cpp:318-320`). The code names type 4 `WMAP_POS_TYPE_GEORAMA` (`chronicletwo:ps2/include/menumap.hpp:37`), so the enum name does not describe these places.
- World-map move quirks a travel should mirror or deliberately skip: `s12` (map 72) becomes `s34` when bit 700 is set (`chronicletwo:ps2/src/menumap.cpp:807-809`); a move from the interior station (`0x22`) to Palm Brinks (10) goes to 11 (`:839-842`); Georama-type places set the scene's now-map to the area's Georama town first (`:811-831`).
- Unlock flags are bit numbers passed to `CheckBitFlagMenu` (`chronicletwo:ps2/src/menumap.cpp:309`). Several have an enum name at that number that does not describe the use: 103 is `SAVE_FLAG_MENU_TIME_1AM`, 700 is `SAVE_FLAG_WORLD_MAP_S12_REDIRECT` (and it is also the unlock for POS 25, `g05`), 702 is `SAVE_FLAG_GEKKA_VIEW` (POS 27), 800 is `SAVE_FLAG_CHAPTER_8_STARTED` (POS 3), 600 is `SAVE_FLAG_WORLD_MAP_2` and 616 is `SAVE_FLAG_WORLD_MAP_4` (`chronicletwo:ps2/include/savedata.hpp:116-133`).
- No-move: `bit_ctrl` bit `MENU_DEBUG_BIT_CTRL_NO_MOVE` (0x01) refuses the world move (`chronicletwo:ps2/src/menumain.cpp:2270`; `chronicletwo:ps2/include/menumain.hpp:31-33`). `bit_ctrl` is `CSaveData::bit_ctrl` (`savedata.hpp:239`), cleared by `ResetBitCtrl`, which `MapJump` calls (`chronicletwo:ps2/src/savedata.cpp:191-193`).
- Town state globals (file-static): `LoopMode` (1 walk, 2 Georama edit, 3 walk menu, 4 Georama pre-menu, 5 Georama menu, 6 waiting for a background read) and `ControlMode` (1 player, 2 scene event, 3 event editor, 4 debug) (`chronicletwo:ps2/include/editloop.hpp:32-51`; `chronicletwo:ps2/src/editloop.cpp:132`, `:139`).
- Dungeon state: `DngStatus.mode` is FIELD 0, MENU 1, EVENT 2, EVENT_EDIT 3, EVENT_MENU 4, EXIT 5 (`chronicletwo:ps2/include/dng_main.hpp:44-51`).
- Sub-games: `SubGameRunning()` returns `SubGame != 0` (`chronicletwo:ps2/src/subgame.cpp:72-74`). Pause: `GetPauseFlag()` (`chronicletwo:ps2/src/nowload.cpp:461-463`).
- Scripts: `EventScript` is file-static (`chronicletwo:ps2/src/event.cpp:42`). `end` is 0 both before a run and during one, so "running" is `prog != NULL && !end` (`chronicletwo:ps2/src/runscript.cpp:117`, `:263-265`; inference).
- Save jobs: `CMemoryCardManager::Step` (`chronicletwo:ps2/src/memcard.cpp:500-531`). A job is idle when `func_no` is `MC_FUNC_IDLE` or `MC_FUNC_NONE` (`chronicletwo:ps2/include/memcard.hpp:24-25`). Jobs start from menus and from the title screen (`TitleMCCheck` in `chronicletwo:ps2/src/title.cpp`): save `chronicletwo:ps2/src/menuop.cpp:1865`, `:2371`, and the port's `chronicletwo:port/src/menu_save.cpp:125`; album save `chronicletwo:ps2/src/inventmn.cpp:5311`, `:5328`. No script command or autosave starts one (grep, this pass). The manager pointer is file-static (`chronicletwo:ps2/src/menuop.cpp:323`). The album menu uses a second static pointer, `MCManagerPtr` (`chronicletwo:ps2/src/inventmn.cpp:261`).
- Opening: dungeon 0 floor 20, event 1010 (`chronicletwo:ps2/src/title.cpp:1028-1032`). Floor 20 has no save record, so `GetFloorInfoPtr(0, 20)` is NULL. Dungeon 1 floor 100 is also outside the table (`ixion:docs/research/c2-dungeons.md`).
- Rooms: the `RI` rows in `chronicletwo-data:menu/dngmap/dmapN.cfg` carry the floor id as their first argument (`chronicletwo:ps2/src/dngfloor.cpp:211-214`). Room counts are 9, 16, 24, 21, 23, 28, 39. The save limits are 9, 16, 25, 21, 23, 29, 39. Dungeon 2 floor 24 and dungeon 5 floor 28 have save records but no room. The existing dungeon note recorded the grid counts; this pass confirms them.
- Dungeon names: the map table's `d0<n>f01` titles are the dungeon names (dungeon 0 is "Underground Channel", not the wiki's "Underground Water Channel" (wiki name unverified); `chronicletwo-data:map/map1.cfg`).
- Hop ABI: `checkpoint` returns 1 when the game was parked (`ixion:include/ixion_api.h:81`); `request_travel` is reserved in v0 (`:87`), and `IxionTravel.destination` is the `--jump` grammar (`:59-63`). The spec puts `EmbedCheckpoint` at the end of `mgEndFrame` (`ixion:docs/HOP-V0.md:70`).

## How it works

### 1. Where a travel can happen

- The only safe apply point is `MainLoop`, right after `mgEndFrame` (`chronicletwo:port/src/mainloop.cpp:339`), on the game's fiber. There the recording is closed, the frame is presented, and no clock pump is running. The Hop checkpoint sits inside `mgEndFrame`, which is fine for parking, but a travel applied there could run during a movie or a load loop.
- A request made during a frame is applied at the next `MainLoop` checkpoint, so it waits at most one game frame. Requests made during loading wait for the next frame (the same limit the Hop spec lists).
- A cross-loop travel finishes the current mode through the existing `mode_finished` path, so `LoopExit` and the `PortNextLoopNo` hand-off do the switch.

### 2. Origin to destination

| Origin | To a town | To a dungeon floor |
|---|---|---|
| EDIT walk (`LoopMode == 1`) | In place: `BurnEditParts`, `EditMapJump(map)`, `RunEvent(100)`. No mode change. `GameGiveOnArrival` must be called by hand. | `PreExitLoop`, `NextLoop(LOOP_DUNGEON, {dng, floor, 1010})`, finish. |
| DUNGEON field (`DngStatus.mode == 0`) | EXIT frame (`DngStatus.mode = 5`, one `LoopDungeonMain`), `NextLoop(LOOP_EDIT, {town, 100})`, finish. | EXIT frame, `NextLoop(LOOP_DUNGEON, {dng, floor, 1010})`, finish. |
| EDIT Georama, menus, events, sub-games | Refuse (wait or drop, see section 3). | Refuse. |
| TITLE, MENU, viewers 4 to 9 | Refuse. | Refuse. |

The in-place EDIT path is the code the world move uses (`chronicletwo:ps2/src/editloop.cpp:1377-1380`) and the developer menu uses (`:1405-1409`). The EXIT frame may open a pause (`chronicletwo:ps2/src/dng_main.cpp:1128-1130`) and heals the party unless `DNG_PAUSE_EXIT_HEAL` is set (`:1146-1148`); both need a decision before shipping.

### 3. Refusal states

| State | Detect with | Source |
|---|---|---|
| Title, opening | `PortLoopNo == LOOP_TITLE`. Opening: dungeon 0 with `GetFloorInfoPtr(0, floor_id[0]) == NULL` and an event running. | `chronicletwo:port/src/mainloop.cpp:103`; `chronicletwo:ps2/src/title.cpp:1028-1032` |
| Debug start menu, viewers, save conversion | `PortLoopNo` is 0 or 4 to 9. | `chronicletwo:ps2/include/mainloop.hpp:31-42` |
| Scene events (town) | `ControlMode != EDIT_CONTROL_PLAYER`, or `EventScript` busy (`prog != NULL && !end`). | `chronicletwo:ps2/include/editloop.hpp:46-51`; `chronicletwo:ps2/src/event.cpp:42` |
| Scene events (dungeon) | `DngStatus.mode` is 2, 3 or 4. | `chronicletwo:ps2/include/dng_main.hpp:44-51` |
| Cutscenes, movies | Implicit: a movie runs its own frame loop inside a script command, so `MainLoop`'s checkpoint is not reached until it returns (inference from `chronicletwo:ps2/src/event_func.cpp:4707-4861`). Scene sequences are covered by the event rows above. | |
| Sub-games (fishing, race, Spheda) | `SubGameRunning() != 0`. | `chronicletwo:ps2/src/subgame.cpp:72-74` |
| Georama editing | `LoopMode` is 2 or 4 (or 5 while the menu is up). | `chronicletwo:ps2/include/editloop.hpp:32-39` |
| Menus (town and dungeon) | `LoopMode` is 3 or 5; `DngStatus.mode` is 1 or 4. | as above |
| Save screens | Menu state, plus `CMemoryCardManager` job not idle (`func_no` not `MC_FUNC_IDLE` or `MC_FUNC_NONE`). | `chronicletwo:ps2/include/memcard.hpp:24-25`; `chronicletwo:ps2/src/menuop.cpp:323` |
| Pause | `GetPauseFlag() != 0`. | `chronicletwo:ps2/src/nowload.cpp:461-463` |
| Fades | `MainScene->fade.NowFade()` (town) or `DngMainScene->fade.NowFade()` (dungeon). | `chronicletwo:ps2/include/effectlist.hpp:254` |
| Background loads | Town: `now_load_map_no != -1` or `LoopMode == 6`. | `chronicletwo:ps2/src/editloop.cpp:976-1005`, `:139` |
| Inside an interior (town) | `InInterior() != 0`. `EditDataSave` is skipped there (`chronicletwo:ps2/src/editloop.cpp:3028`). Travel from inside is untested. | `chronicletwo:ps2/include/mapjump.hpp:201` |
| World-move ban | `bit_ctrl & MENU_DEBUG_BIT_CTRL_NO_MOVE`. | `chronicletwo:ps2/src/menumain.cpp:2270` |
| Scripted-only floors | `GetFloorInfoPtr(stage, floor_id[stage]) == NULL` (dungeon 0 floors 20 and 21, dungeon 1 floor 100). | `chronicletwo:ps2/src/savedatadungeon.cpp:15-33` |

Design choice: transient refusals (events, menus, fades, save job, pause, background load) keep the request pending until an expiry; permanent ones (title, menu, viewer) drop it and log.

### 4. Era, map numbers and save fields

- Era of the current main map: `GetMapType(save->map_no)`. Future is 5 or 6. Everything else is present. The code encodes no past era. The flashback maps (`s44`, `s46`, `s49`) are type 3, so they read as present (inference from their names and types).
- Era of a player inside an interior: the scene's sub-map, looked up with `GetMapType`. The save's `map_no` still names the town (inference from `MapJump` being the only writer of the map fields).
- Save fields that matter for travel and era:
  - `map_no` (current main map), `prev_map_no`, `area_no` (the world-map area, not the era).
  - `game_progress` (chapter through `GetGameChapter`).
  - `save_dungeon.stage_id` and `floor_id[stage_id]`, the dungeon and floor the player is on.
  - `edit_data[0..4]`, the Georama layouts. Georama towns use `GetEditData(MapNo)` for table indices 0 to 4 (`chronicletwo:ps2/src/editloop.cpp:3023-3030`); `GetEditData` returns NULL for other indices (`chronicletwo:ps2/src/savedata.cpp:155-161`).
  - Future places use `GetEditData(area)` with area 0 to 3 for `f01` to `f04` (`chronicletwo:ps2/src/editloop.cpp:2836-2849`). So `f01` shares slot 0 with `g01`, `f02` with `g02`, and so on (see the existing `c2-towns-georama.md` note).
  - `bit_flag` 616 (`SAVE_FLAG_WORLD_MAP_4`) and 736 (`SAVE_FLAG_CHAPTER_8`), which gate future places on the world map.
  - `bit_ctrl`, for the no-move ban.

### 5. What an arrival needs

- Town (`LOOP_EDIT`): `map_no` set from the name, `event_no` (100 by default), the time from the save (at a mode entry only), the party and active character (`CUserDataManager`, `active_chr_no`, `party_member`; `chronicletwo:ps2/src/editloop.cpp:936-937`). `EditMapJump` also loads villagers by map and progress (`chronicletwo:ps2/src/editloop.cpp:2877`), Georama layouts for type 1 (`:2800-2830`), future parts for type 5 (`:2835-2857`), and NPC talk for maps 10, 34 and 121 (`:2790`).
- Dungeon (`LOOP_DUNGEON`): `arg.map_no` = dungeon index (0 to 6), `arg.floor_no` set explicitly, `arg.event_no` (1010 by the world-map precedent). The floor record must exist, or `SetFloorID` writes a floor with no record. The map sound is `map_no * 1000 + 1601`, plus 1000 for dungeons 5 and 6 (`chronicletwo:ps2/src/dng_main.cpp:460-464`, from the existing dungeon note).
- Progress: no loader in this pass checks `game_progress` before loading a map or floor (`MapJump`, `EditMapJump`, `InitDungeonMain`; inference from the absence of a check). Progress affects the sky, the train add-on, the villager list and the scripts. Whether a low-progress arrival is safe is not verified. The debug configs set progress 4 for Palm Brinks and 2 for dungeons.
- Time: see the Key facts. The save's `time_stop` keeps time from passing in town (`chronicletwo:ps2/include/savedata.hpp:222`).

### 6. Station table: towns and fields

All 73 records of map types 1, 3 and 5, in map-number order. The `--jump` column is the spec string (`town:<n>`). "Gate" is the world-map POS record and its unlock bit; "-" means the place is not on the world map, so it can be reached only by script or by jump. "Era" is `present` unless the map type is 5. "Sel" is the debug map-selection category (`chronicletwo:ps2/src/mapselect.cpp:184-185`). Records 11 to 14 load as sub-maps of map 10 (`chronicletwo:ps2/src/editloop.cpp:2736-2739`).

| --jump | map | title | type | era | sel | add-path | world-map gate |
|---|---|---|---|---|---|---|---|
| town:0 | g01 | Sindain | 1 | present | Georama | g00/g00 | POS4 flag208 type1 |
| town:1 | g02 | Balance Valley | 1 | present | Georama | g00/g00 | POS9 flag302 type1 |
| town:2 | g03 | Veniccio | 1 | present | Georama | g00/g00 | POS15 flag402 type1 |
| town:3 | g04 | Heim Rada | 1 | present | Georama | g00/g00 | POS20 flag504 type1 |
| town:4 | g05 | Moon Flower Palace | 1 | present | Georama | - | POS25 flag700 type1 |
| town:9 | s40 | Veniccio | 3 | present | Submap | bs/battleship01 | - |
| town:10 | m01 | Palm Brinks | 3 | present | PalmBrinks | - | POS0 flag103 type3 |
| town:11 | m02 | Palm Brinks Station | 3 | present | PalmBrinks | - | - |
| town:12 | m03 | Palm Brinks Square | 3 | present | PalmBrinks | - | - |
| town:13 | m04 | Palm Brinks Residence | 3 | present | PalmBrinks | - | - |
| town:14 | m05 | Palm Brinks Park | 3 | present | PalmBrinks | - | - |
| town:15 | s01 | Channel Reservoir | 3 | present | Submap | trn/train | - |
| town:16 | s02 | Sindain Station | 3 | present | Submap | trn/train | POS5 flag207 type2 |
| town:17 | m06 | Palm Brinks | 3 | present | Event | - | - |
| town:18 | s07 | Inside of Train | 3 | present | Special | - | - |
| town:19 | m07 | Palm Brinks | 3 | present | Event | - | - |
| town:20 | m08 | Palm Brinks | 3 | present | Event | - | - |
| town:22 | d01e01 | Channel Entrance | 3 | present | Dungeon | - | - |
| town:23 | s08 | Inside of Locomotive | 3 | present | Special | - | - |
| town:25 | f01 | Jurak Mall | 5 | future | Future | - | POS8 flag616 type4 |
| town:26 | f02 | Starlight Temple | 5 | future | Future | - | POS14 flag616 type4 |
| town:34 | i02h01 | Station | 3 | present | PalmBrinks | trn/train | POS1 flag207 type2 |
| town:39 | i03h02 | Circus Tent | 3 | present | PalmBrinks | - | - |
| town:40 | i03h02a | Circus Tent | 3 | present | PalmBrinks | - | - |
| town:53 | s03 | Forest Tunnel | 3 | present | Submap | - | - |
| town:54 | s04 | Balance Valley Station | 3 | present | Submap | trn/train | POS10 flag300 type2 |
| town:72 | s12 | Moon Flower Palace Stop | 3 | present | Submap | trn2/s36 | POS26 flag648 type2 |
| town:73 | s25 | Carpenterion (Inner) | 3 | present | Submap | - | - |
| town:76 | s31 | Moon Flower Palace Stop | 3 | present | Submap | trn2/s36 | POS29 flag600 type2 |
| town:77 | s33 | Moon Flower Palace | 3 | present | Submap | - | POS28 flag600 type3 |
| town:78 | s35 | Moon Flower Palace Surfacing | 3 | present | Submap | - | - |
| town:82 | f03 | Luna Lab | 5 | future | Future | - | POS19 flag616 type4 |
| town:83 | s09 | Veniccio Station | 3 | present | Submap | trn/train | POS16 flag400 type2 |
| town:85 | s41 | Heim Rada Event | 3 | present | Event | bs/battleship01 | - |
| town:86 | s42 | Repair Shop | 3 | present | Event | - | - |
| town:87 | s10 | Heim Rada Stop | 3 | present | Submap | trn/train | POS21 flag500 type2 |
| town:95 | i03h04 | Finny Frenzy Races | 3 | present | Special | - | - |
| town:96 | i03h05 | Finny Frenzy Races | 3 | present | Special | - | - |
| town:99 | i03h03 | Fishing Contest Grounds | 3 | present | Special | - | - |
| town:102 | f04 | Gundorada Workshop | 5 | future | Future | - | POS23 flag616 type4 |
| town:103 | s11 | Kazarov Stonehenge | 3 | present | Submap | trn2/s36 | POS24 flag616 type3 |
| town:104 | s29 | Paznos (Observatory) | 5 | future | Submap | - | - |
| town:105 | s30 | Paznos (Bridge) | 5 | future | Submap | - | - |
| town:106 | s36 | Ixion (Outer) | 3 | present | Submap | - | - |
| town:107 | s39 | Operations Room | 5 | future | Future | - | - |
| town:108 | s37 | Ixion (Engine Room) | 3 | present | Submap | - | - |
| town:109 | d06e01 | Flower Palace Foyer | 3 | present | Dungeon | - | - |
| town:110 | f03i04 | Central Lab | 5 | future | Future | - | - |
| town:115 | s47 | Sindain (Event) | 3 | present | Event | - | - |
| town:120 | s38 | Ixion (Guest Room) | 3 | present | Special | - | - |
| town:121 | s45 | Palm Brinks Square | 3 | present | Special | - | - |
| town:122 | s46 | Max's Room-Flashback | 3 | present | Event | - | - |
| town:123 | s49 | Gaspard Flashback Scene | 3 | present | Event | - | - |
| town:126 | s44 | Moon Flower Palace-Flashback | 3 | present | Event | - | - |
| town:128 | s23 | Griffon's Chamber Door | 3 | present | Submap | - | - |
| town:130 | s51 | Raybrandt Castle | 3 | present | Event | - | - |
| town:131 | s53 | Central Lab (Event) | 3 | present | Event | trn2/s36 | - |
| town:149 | s28 | Paznos | 3 | present | Event | - | - |
| town:150 | s32 | Moon Flower Palace vs Paznos | 3 | present | Event | - | - |
| town:151 | s48 | Paznos (Robot) | 5 | future | Event | - | - |
| town:153 | s55 | Paznos Event (Battle) | 1 | present | Event | - | - |
| town:155 | s34 | Moon Flower Palace Stop | 3 | present | Submap | trn2/s36 | - |
| town:158 | s58 | Subdimension | 3 | present | Submap | trn2/s36 | - |
| town:159 | s59 | Luna Lab | 3 | present | Event | - | - |
| town:172 | s60 | Palm Brinks | 3 | present | Event | - | - |
| town:176 | s64 | Moon Flower Palace | 3 | present | Event | - | - |
| town:177 | s65 | Moon Flower Palace | 3 | present | Submap | - | - |
| town:178 | s98 | Kazarov Stonehenge | 3 | present | Event | - | - |
| town:179 | s66 | Kazarov Stonehenge | 3 | present | Event | - | - |
| town:180 | s67 | Palace Terrace | 3 | present | Event | - | - |
| town:186 | s68 | Moon Flower Palace | 3 | present | Event | - | - |
| town:187 | s70 | Moon Flower Palace | 3 | present | Event | - | - |
| town:188 | s71 | Moon Flower Palace Stop | 3 | present | Event | trn2/s36 | - |

Notes on the table:
- Type 5 rows marked `Submap` or `Event` (`s29`, `s30`, `s48`) are future-type scene maps, not destinations for a player walk. The `Future` rows are the walkable future places.
- `town:72` (`s12`) is redirected to `s34` (map 155) by the world map when bit 700 is set. A travel that copies the world map should do the same, or document the difference.
- Maps 34 and 121 load NPC talk messages on entry (`chronicletwo:ps2/src/editloop.cpp:2790`). No POS record targets Ixion or the train-room maps (`s36` to `s39`, `s07`, `s08`, `s38`; `chronicletwo-data:menu/1/wldmap.cfg`).

### 7. Station table: dungeons

Dungeon index `n` is the `stage_id`; its folder is `map/d/d0<n+1>` (`chronicletwo:ps2/src/dng_main.cpp:952-957`); its first floor map is `d0<n+1>f01` in the map table. All seven are present era (types 7 and 8).

| dungeon | folder | name (map table) | floor records (valid ids) | rooms | gap (record, no room) | floor 0 title | exit town (floor 0) | world-map entries (floor) | jump |
|---|---|---|---|---|---|---|---|---|---|
| 0 | d01 | Underground Channel | 9 (0 to 8) | 9 | - | Channel Entrance | d01e01 (town:22) | POS2 (tree map), flag100 | dungeon:0 (floor 1); dungeon:0:1 to dungeon:0:8 |
| 1 | d02 | Rainbow Butterfly Wood | 16 (0 to 15) | 16 | - | Sindain Station | s02 (town:16) | POS6 (tree map), flag209 | dungeon:1:1 to dungeon:1:15 |
| 2 | d03 | Starlight Canyon | 25 (0 to 24) | 24 | 24 | Balance Valley | g02 (town:1) | POS11 (tree map), flag306; POS12 (floor 18), flag332; POS13 (floor 8), flag312 | dungeon:2:1 to dungeon:2:23 (24 has no room) |
| 3 | d04 | Ocean's Roar Cave | 21 (0 to 20) | 21 | - | Veniccio | g03 (town:2) | POS17 (tree map), flag404; POS18 (floor 9), flag408 | dungeon:3:1 to dungeon:3:20 |
| 4 | d05 | Mount Gundor | 23 (0 to 22) | 23 | - | Heim Rada | g04 (town:3) | POS22 (tree map), flag504 | dungeon:4:1 to dungeon:4:22 |
| 5 | d06 | Moon Flower Palace | 29 (0 to 28) | 28 | 28 | Moon Flower Palace Foyer | d06e01 (town:109) | POS27 (tree map), flag702 | dungeon:5:1 to dungeon:5:27 (28 has no room) |
| 6 | d07 | Zelmite Mine | 39 (0 to 38) | 39 | - | Palm Brinks Park | m05 (town:14) | POS3 (tree map), flag800 | dungeon:6:1 to dungeon:6:38 |

Notes on the dungeon table:
- Floor 0 is the entry and the exit. `--jump` rejects `dungeon:<n>:0` (`chronicletwo:port/src/test_hooks.cpp:95-97`), so a floor-0 travel must use the exit path.
- Floor ids in the rooms table (`RI` first argument) are the authority for "has a room". Floors listed as valid by the save limit but with no room (`dungeon:2:24`, `dungeon:5:28`) pass the parser and should be refused by the proposal.
- The world-map floor -1 entries open the tree map from inside the menu, so a menu-free travel uses explicit floors only. POS 3 (Zelmite Mine, dungeon 6) has unlock bit 800, named `SAVE_FLAG_CHAPTER_8_STARTED`; the name suggests a chapter 8 gate but is not authoritative (inference).

### 8. World-map destination set (for an allowlist)

The world map is the game's own travel UI, so its destinations are the first allowlist. Its town-type POS maps are `10, 34, 0, 16, 65, 25, 1, 54, 26, 2, 83, 82, 3, 87, 102, 103, 4, 72, 77, 76` (20). The dungeon-exit maps add `22`, `109`, `14`. These 23 are tier A; the rest of section 6 is tier B, opt-in and untested. Dungeon floors use the POS floors (2/18, 2/8, 3/9) plus the tree-map entries, which need explicit floors.

## Proposed Ixion code

Files are new or changed in the ChronicleTwo port. Nothing here is built or tested.

### Public functions (new file `port/src/ixion_travel.hpp`)

```cpp
// Asks for a travel. destination uses the --jump grammar: "town:<map>" or "dungeon:<n>:<floor>".
// Returns false and logs a reason if the request is malformed, targets a map or floor that the
// world map would not offer (tier A, section 8), or another travel is already pending.
// Safe to call on any fiber that is not inside ClockPump; it only writes the statics below.
bool C2TravelRequest(const char *destination);

// Called from MainLoop immediately after mgEndFrame(NULL), on the game's fiber, and only when
// mode_finished is still 0. Applies a pending travel if the current state allows it, else keeps
// it pending (transient refusal) or drops it (permanent refusal). Sets the leave flag when the
// current mode must end this frame.
void C2TravelApplyAtCheckpoint();

// Returns true once after C2TravelApplyAtCheckpoint has decided the current mode must end.
bool C2TravelTakeLeave();
```

### Statics (new, in `port/src/ixion_travel.cpp`)

```cpp
static bool     travel_pending = false;   // a request waits for a checkpoint
static bool     travel_leave = false;     // the current mode must end this frame
static GameJump travel_jump;              // parsed by GameParseJump (test_hooks.hpp)
static int      travel_checkpoints = 0;   // checkpoints since the request, for expiry
static char     travel_reason[96] = "";   // last refusal, for the log and receipts
constexpr int   kTravelExpiry = 1500;     // checkpoints (about a minute at one per frame); a choice
```

### Existing globals and functions touched

- Read: `PortLoopNo` (`MainLoop_LoopNo`, `chronicletwo:port/src/mainloop_port.hpp:12`).
- Written, through `NextLoop`: `PortNextLoopNo` (`MainLoop_NextLoopNo`) and `NextInitArg` (`chronicletwo:ps2/src/mainloop.cpp:2133`).
- Read and written: `DngStatus` (`chronicletwo:ps2/src/dng_main.cpp:183`, declared `dng_main.hpp:420`), `DngSaveDataDungeon` (`dng_main.cpp:341`), `DngMainScene` (`dng_main.cpp`).
- Called: `GetMainScene()`, `GetSaveData()`, `GetMapName`, `GetMapType`, `SearchMapNo`, `GetLoadMapInfo` (no), `EditMapJump`, `BurnEditParts`, `PreExitLoop`, `GameParseJump`, `GameGiveOnArrival`, `NextLoop`, `LoopDungeonMain`, `mgBeginFrame`, `mgEndFrame`.
- Do not call: `GamePrepareJump` (`InitSaveData`, `DebugFlag`, `LoadGameConfig`), `EdDebugInfo.jump_map_no` (bypasses every gate in section 3), `GetLoadMapInfo` on its own.

### Exports the owning files need (each is a short accessor, because the state is file-static)

```cpp
// ps2/src/editloop.cpp  (LoopMode, ControlMode, now_load_map_no and SubMapLoadBG are static here)
bool EditTravelReady() {
    return LoopMode == EDIT_LOOP_WALK && ControlMode == EDIT_CONTROL_PLAYER &&
           now_load_map_no == -1 && !SubGameRunning() && GetPauseFlag() == 0 &&
           !MainScene->fade.NowFade() && !InInterior() && !SaveJobBusy() && !EventScriptBusy();
}

// ps2/src/dng_main.cpp  (DngStatus is global here; GetFloorInfoPtr is in savedatadungeon)
bool DngTravelReady() {
    const int stage = DngSaveDataDungeon->stage_id;
    return DngStatus.mode == DNG_STATUS_FIELD && !SubGameRunning() && GetPauseFlag() == 0 &&
           !DngMainScene->fade.NowFade() && !SaveJobBusy() &&
           DngSaveDataDungeon->GetFloorInfoPtr(stage, DngSaveDataDungeon->floor_id[stage]) != nullptr;
}

// Runs the dungeon's own cleanup, as the developer menu does (port/src/mainloop.cpp:287-292).
void DngTravelExitFrame() {
    DngStatus.mode = DNG_STATUS_EXIT;
    mgBeginFrame(NULL);
    LoopDungeonMain();    // returns true; its EXIT block does the cleanup (dng_main.cpp:1142-1165)
    mgEndFrame(NULL);     // nested checkpoint: see Risks
}

// ps2/src/event.cpp  (EventScript is static here)
bool EventScriptBusy() {
    return EventScript.prog != nullptr && !EventScript.end;
}

// ps2/src/menuop.cpp  (MemoryCardPtr is static here)
bool SaveJobBusy() {
    return MemoryCardPtr != nullptr && MemoryCardPtr->GetFuncNo() != MC_FUNC_IDLE &&
           MemoryCardPtr->GetFuncNo() != MC_FUNC_NONE;
}

// ps2/src/dngfloor.cpp  (new: does the floor have a room, from the RI rows)
bool DngFloorHasRoom(int dungeon, int floor);
```

### Apply body (pseudo-C++, `port/src/ixion_travel.cpp`)

```cpp
void C2TravelApplyAtCheckpoint() {
    if (!travel_pending) {
        return;
    }

    const int from = PortLoopNo;

    if (from == LOOP_TITLE || from == LOOP_MENU || (from >= LOOP_CHARA_VIEWER && from < LOOP_MODE_NUM)) {
        travel_pending = false;                       // permanent: drop and log
        Log("travel dropped: loop %d does not travel", from);
        return;
    }

    if (from != LOOP_EDIT && from != LOOP_DUNGEON) {
        return;                                       // unknown loop: keep pending
    }

    if (++travel_checkpoints > kTravelExpiry) {
        travel_pending = false;
        Log("travel expired");
        return;
    }

    const bool ready = from == LOOP_EDIT ? EditTravelReady() : DngTravelReady();

    if (!ready) {
        return;                                       // transient: keep pending
    }

    if (from == LOOP_EDIT && travel_jump.mode == JumpMode::Town) {
        // In place. Mirrors editloop.cpp:1377-1380 (world move) and :1405-1409 (debug jump).
        travel_pending = false;
        BurnEditParts();
        if (!EditMapJump(travel_jump.map)) {
            Log("EditMapJump failed after side effects");   // see Risks: partial state
        }
        MainScene->RunEvent(100, NULL);
        GameGiveOnArrival(LOOP_EDIT);
        return;
    }

    // Cross-loop: finish the current mode, then the next LoopInit runs.
    if (from == LOOP_EDIT) {
        PreExitLoop(MainScene);                       // editloop.cpp:1398 precedent
    } else {
        DngTravelExitFrame();                         // EXIT cleanup, one frame
    }

    INIT_LOOP_ARG arg = {};                           // zeroes floor_no and event_no; set both
    arg.map_no = travel_jump.map;                     // town map, or dungeon index
    if (travel_jump.mode == JumpMode::Town) {
        arg.event_no = 100;
        NextLoop(LOOP_EDIT, arg);
    } else {
        arg.floor_no = travel_jump.floor;
        arg.event_no = 1010;                          // world-map precedent (editloop.cpp:1374-1375)
        NextLoop(LOOP_DUNGEON, arg);
    }

    travel_pending = false;
    travel_leave = true;
    travel_checkpoints = 0;
}

bool C2TravelRequest(const char *destination) {
    if (travel_pending) {
        Refuse("another travel is pending");
        return false;
    }
    GameJump jump;
    if (destination == nullptr || !GameParseJump(destination, jump)) {
        Refuse("bad destination; use town:<map> or dungeon:<n>:<floor>");
        return false;
    }
    if (jump.mode == JumpMode::Town) {
        if (!TownTravellable(jump.map)) { Refuse("not a tier A town"); return false; }
    } else if (jump.mode == JumpMode::Dungeon) {
        if (!DngFloorHasRoom(jump.map, jump.floor)) { Refuse("no room for that floor"); return false; }
        if (jump.floor == 0) { Refuse("floor 0 is the exit"); return false; }   // parser already rejects it
    } else {
        Refuse("only town and dungeon can be travelled to");
        return false;
    }
    travel_jump = jump;
    travel_pending = true;
    travel_checkpoints = 0;
    return true;
}

bool C2TravelTakeLeave() {
    const bool leave = travel_leave;
    travel_leave = false;
    return leave;
}
```

`TownTravellable(map)` is tier A from section 8: `GetMapName != NULL`, `GetMapType` in {1, 3, 5}, and the map is in the 23-entry set. Tier B is the rest of section 6, behind a build flag.

### MainLoop wiring (`port/src/mainloop.cpp`, after line 339)

```cpp
            mgEndFrame(NULL);

            if (mode_finished == 0) {
                C2TravelApplyAtCheckpoint();
                mode_finished = C2TravelTakeLeave() ? 1 : 0;
            }

            if (mode_finished != 0) {          // existing code at :341-344, unchanged
                PauseCancel();
                break;
            }
```

The existing `NextLoop(LOOP_MENU, ...)` at `:263` runs once per mode entry, before the inner loop. A travel's `NextLoop` must run inside the loop, after it, so it overrides the default. No change is needed there.

## Risks and blockers

- Partial state on in-place travel. `EditMapJump` runs `InitEditEvent`, `DeleteFileCache`, `SeAllStop` and `EditDataSave` before it can fail (`chronicletwo:ps2/src/editloop.cpp:2731-2751`). Validating the name and type before the request is the only guard. A failing map after those side effects leaves the town half-loaded.
- Nested checkpoints. `DngTravelExitFrame` calls `mgEndFrame`, which in the Hop prototype calls `EmbedCheckpoint` (after the pacing wait, then `PresentRebase()`, `chronicletwo (Hop prototype):port/src/mglib.cpp:1369-1371`). The host may park the game there, mid-apply. `travel_pending` is still set during that frame, so a second request is refused, but the apply has not finished. Clear `travel_pending` first, or add a re-entry guard.
- Exit frame side effects: `PlayerPartyCure` (healing) and a possible `PauseStart` from the pad (`chronicletwo:ps2/src/dng_main.cpp:1128-1130`). These need a design decision, and a test with the pad idle.
- Floor arguments default to 0. `INIT_LOOP_ARG()` zeroes `floor_no`, so an arg without it enters floor 0 (`chronicletwo:ps2/src/dng_main.cpp:347`). The sketch sets it.
- Event 1010 at an ordinary floor is shared with the opening (`chronicletwo:ps2/src/title.cpp:1028-1032`). The world map uses it for every dungeon entry, which suggests it is the normal arrival value, but this is not confirmed by reading the scripts.
- Progress is not checked by the loaders. A travel to a map that the story has not reached may load and then misbehave in its scripts. Nothing in this pass proves a map safe at a given progress.
- Enum names at POS flag numbers mislead (`SAVE_FLAG_MENU_TIME_1AM` at 103, `SAVE_FLAG_WORLD_MAP_S12_REDIRECT` at 700). Use the numbers, not the names, when reading gates.
- Bit 700 is both an unlock (POS 25, `g05`) and the `s12` to `s34` redirect switch (`chronicletwo:ps2/src/menumap.cpp:807-809`). Travelling to `g05` may therefore change the `s12` redirect. Not traced further.
- The save layout offsets in the existing `c2-save.md` note conflict with the declared member sizes from `edit_data` onward. The asserted total (0x65930) is consistent with the earlier fields, but `CEditData` appears to be about 0x5510 bytes (its `unk_5110[0x400]` tail), which would not fit five copies. Do not use those offsets until a compile-time check resolves them. This document cites no offsets past `edit_data`.
- Interiors. Travelling from inside an interior is untested. `EditDataSave` is skipped there (`chronicletwo:ps2/src/editloop.cpp:3027`), and the scene's sub-map is not cleared by the save.
- `MemoryCardPtr` is a file-static pointer that may outlive its menu (inference, unverified). `SaveJobBusy` should check the job state, not only the pointer, and should be tested after a save menu closes. As written it checks only `MemoryCardPtr`; album save jobs run on the separate `MCManagerPtr` (`chronicletwo:ps2/src/inventmn.cpp:261`, `:5311`, `:5328`), so it misses them unless menu state already blocks the walk.
- Dungeon floors with no room (`dungeon:2:24`, `dungeon:5:28`) have save records. Arrival there may write a visit record for a floor the map does not have (inference). Tier A refuses them.

## Open questions

- What does event 1010 do at an ordinary dungeon floor, and is it the opening script's entry? This needs a decode of the `.stb` scripts or a runtime test. The world-map precedent uses it for every dungeon entry.
- Which maps load safely at progress 2 and at progress 4 from a fresh save? This needs one runtime test per tier-A destination, with the save's `game_progress` set to the minimum that the POS gate implies.
- Does the scene write `now_time` back to the save each frame, or only at mode entry? The save-to-scene copy runs every frame (`chronicletwo:port/src/mainloop.cpp:305-308`); the reverse direction is not traced. It decides whether an in-place travel keeps the clock.
- Where does the Dark Chronicle time-travel trigger live? Not located in this pass. It is probably an event script (`chronicletwo:ps2/src/event_func.cpp`), not a menu; the existing `c2-time-travel.md` note could not decode the `.stb` files.
- Is `sub_map_no` ever non-negative in a real save? Only -1 writers were found.
- Does `EditMapJump` return 0 for any map in tier A? Only the name check was traced.
- ABI: which side calls `C2TravelRequest`, and through what slot? `request_travel` is module-to-host only.
- Is the dungeon 6 route really gated by chapter 8 (POS 3, bit 800)? The name suggests so. Does a tier-B travel to an `Event` or `Special` map (for example `i03h04`) need minigame state set first?
