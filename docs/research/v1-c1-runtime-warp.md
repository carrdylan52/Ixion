# Dark Cloud: travelling to a town or dungeon floor at runtime

## What this covers

How the Dark Cloud (DC1, Chronicle) PC port changes mode and map while the game runs, and what Ixion v1 needs to do the same from outside:

- what the town loop (`EditLoop`) and the dungeon loop (`GameLoop`) do when a map jump is pending, and what they clean up on the way out;
- whether a host may call `MapJump(n, -1)` from the frame-end checkpoint, by state (town walk, town event, town menu, interior, dungeon play, dungeon script, dungeon fades, title and menus), and how to detect the unsafe ones;
- how a dungeon is entered at a chosen floor, and how a town is entered at a chosen entrance or position;
- a station table for every town, dungeon and world-map place, with map numbers, data folders and load preconditions;
- a proposed `C1TravelRequest` (same grammar as `--jump`) and `C1TravelApplyAtCheckpoint`, with the exact globals they touch.

Pinned source is Chronicle at 86c2b4c8, the commit Ixion pins. Kazarov citations use the current layout (main 9310c53). `chronicle:` means the Chronicle checkout (`ps2/src` is the retail unit, `port/src` is the PC port). Read-only research: nothing was built or run. Points already covered by the existing notes (`ixion:docs/research/c1-mainloop-control.md`, `c1-worldmap-modes.md`, `c1-dungeons.md`, `c1-towns-georama.md`) are referenced, not repeated. Some of those notes cite older line numbers; the numbers here are for 86c2b4c8.

## Key facts

- **`MapJump` only queues.** `MapJump(map, event)` writes `NextMapNo` and `StartEventNo` and nothing else (`chronicle:ps2/src/main.cpp:1053-1056`). The one reader that changes mode is `GameFollowMapJump()` (`chronicle:port/src/gameloop.cpp:403-439`), called once after the frame loop ends (`chronicle:port/src/gameloop.cpp:954`). The frame loop ends only when a mode returns non-zero (`chronicle:port/src/gameloop.cpp:909-949`). A `MapJump` written while the mode keeps returning 0 has no effect.
- **The mode's return value decides the exit; the jump is applied after it.** `GameApplyLoopResult` maps a mode's return code to a mode (`chronicle:port/src/gameloop.cpp:441-545`). `GameFollowMapJump` then overrides `mode` and `MapNo` when `NextMapNo >= 0`.
- **Two ways a host's jump gets lost.** (a) `GameFollowMapJump` has no branch for `NextMapNo` in 300-399 or 401-799, so `mode` stays what `GameApplyLoopResult` set (MENU for town and dungeon exits; `chronicle:port/src/gameloop.cpp:403-439`, `:480-490`, `:539-543`). (b) Several exits call `MapJump` themselves and overwrite the host's value: TITLE result 1 calls `MapJump(400)` and 4 calls `MapJump(801)` (`chronicle:port/src/gameloop.cpp:464-470`); RUSH calls `MapJump(800)` (`:477`); OPENING calls `MapJump(0)` (`:516`); the developer MENU exit with no pending return calls `MapJump(800)` (`:532`); the interior's leave calls `MapJump(800)` and returns 99 (`chronicle:port/src/edit_in.cpp:864-868`, retail `chronicle:ps2/src/edit_in.cpp:962-966`). A checkpoint apply must run after `GameApplyLoopResult`.
- **Town exit is `exit_loop`.** `EditLoop` tests `exit_loop` near its end (the function closes at `chronicle:port/src/editloop.cpp:1109`), calls `EditExit()` and returns 1 (`chronicle:port/src/editloop.cpp:1077-1080`). `EdExitLoop()` sets the flag (`chronicle:ps2/src/editloop.cpp:608-610`). The town's own `_MAP_JUMP` script opcode calls `MapJump` and sets `ED_EVENT_RETURN_MAP_JUMP` (`chronicle:ps2/src/editloop3.cpp:3610-3611`). `EventMode` turns that return code into `EdExitLoop()` (`chronicle:ps2/src/editloop.cpp:3610-3611`). So the game's own script-driven map jump leaves the town through the same flag a host would set.
- **Town exit cleanup.** `EditExit` (`chronicle:ps2/src/editloop.cpp:472-497`) calls `EditSave` (`:440-453`), which saves the Georama ground and parts only for `MapNo < 5` and saves the clock unless time stops. It then fades the BG colour, runs `StopAllSound`, drains `ReadBGSync`, stops ambient and BGM (`SndBgmFadeOutStop`, `SndBgmStop`, `SndBgmInit`, only when `map_jump_bgm_stop` is set), stops the source and SE sounds, and restores the scissor and pad lock. It does not free models or textures. The next mode's Init sets up its own buffers (for example `InitializeDataBuffer` in `EditInit`, `chronicle:port/src/editloop_init.cpp:169`).
- **The town loop never reads `NextMapNo`.** Nothing in `EditLoop` reads it. The only thing a pending jump changes in the town is the mode the loop returns to.
- **Three town states ignore `exit_loop`.** (1) Interior: `GameMode == ED_MODE_MAP_JUMP` (12; its enum comment at `chronicle:ps2/include/editmapscript.hpp:25` says "Jumping to another map", but the port branch runs the interior loop) is handled in a branch that returns at `chronicle:port/src/editloop.cpp:324`, before the exit test. The branch is entered at `:231`. (2) The interior test (`MapNo == 99`, `interior_test`) returns at `chronicle:port/src/editloop.cpp:396`. (3) The door-open path returns 0 at `:562` once the door has finished opening. Leaving an interior is honoured only by `EditInLoop()` returning 0x63 (`chronicle:port/src/editloop.cpp:237-240`). `EditInLoop` leaves through its own `static int end_count` (`chronicle:port/src/edit_in.cpp:851`), which a host cannot reach without a port-side hook.
- **Dungeon exit is `existFlag`.** `GameLoop` returns `existFlag` after its `BtGameModeFlag` switch (`chronicle:ps2/src/dun/gameloop.cpp:1977-2082`; the test is at `:2048`). Nothing between the switch and the test returns, so `existFlag = 1` is honoured in any dungeon sub-state as long as `GameLoop` runs. The exit block (`:2048-2082`) drains `ReadBGSync`, stops sound (`SndExit` and `SndBgmInit` when `map_jump_bgm_stop` is set, otherwise `SndStopAllSe`), calls `LostGateKey`, restores HP and ailments unless `BtEventInfo.no_status_recover` is set, sets `UserStatus->cur_chara = CHARA_TOAN`, sets `prev_floor = -1`, and returns `existFlag`. Script MAP_JUMP sets `existFlag = 1` (`chronicle:port/src/dun/movechara.cpp:1793-1795`). The exit table sets `existFlag = 2` (`:2145-2176`).
- **Dungeon script state is not restored on a host exit.** While a system script runs, `read_buffer` is moved into the script's buffer (`chronicle:port/src/dun/movechara.cpp:1764`) and restored at script end (`:1778`, `:1823`). `GameInit` copies `read_buffer` into `old_read_buffer` (`chronicle:ps2/src/dun/gameloop.cpp:1465`). A host exit mid-script skips the restore, so the next dungeon's `old_read_buffer` would hold the wrong pointer (inference from the code; the developer chord has the same gap).
- **Developer-chord precedent.** `GameEnterDeveloperMenu` already ends any mode mid-frame: it drains `ReadBGSync`, stops sound, unlocks the pad, clears `NextMapNo` and `StartEventNo`, and sets MENU (`chronicle:port/src/gameloop.cpp:628-647`). The frame loop breaks out at `:945-948` without calling `GameApplyLoopResult`. This is the only existing "leave now" path, and it does not carry a destination.
- **Dungeon entry.** `GameInit` reads the dungeon from `main_select_menu_no` into `selectMapNo` (`chronicle:ps2/src/dun/gameloop.cpp:1414`). It refills HP unless `no_status_recover` (`:1418-1429`), sets `cur_georama` (`:1434`), calls `SetNowFloor(0)` (`:1949`), sets `prev_floor = -1` (`:1953`), loads the dungeon's event script (`:1969`) and starts script 100 (`:1972-1974`). `GameInit` does not read any floor value from the host.
- **The floor is `UserStatus->cur_floor`.** It is held in `CDngStatusData` (`chronicle:ps2/src/dngstatusdata.cpp:36-44`, `SetNowFloor`, which also raises `floor_reached[cur_georama]`). Script 100 takes the entrance window when `GET_OLD_FLOOR_LEVEL` is -1, which is always the case after `GameInit` (`ixion:docs/research/c1-dungeons.md`, "Entry").
- **`BtMapJumpFloor` is not a loader input.** `_SET_DUNGEON_FLOOR` calls `BtSetMapJumpFloor`, which writes it (`chronicle:ps2/src/editloop3.cpp:3620-3623`; `chronicle:ps2/src/btsysscript.cpp:261-263`). Only `_GET_DUNGEON_FLOOR` reads it (`:3625-3628`), and it is reset in `initialize_data` (`chronicle:ps2/src/main.cpp:431`) and in `BtSystemScriptAfter` (`chronicle:ps2/src/btsysscript.cpp:222`). `GameInit` does not read it.
- **Floor geometry is built by the floor script, not by `GameInit`.** Script 100 chooses the map file and layout and calls `_SET_DUNGEON_MAP` (`chronicle:ps2/src/btsysscript.cpp:623-629`), `_LOAD_DUNGEON_MAP2` (`:631-636`), `_SET_RANDOM_MAP` (`:644-652`, which calls `BtCleatRandomMap` or `BtCleatFreeMap`) and `_LOAD_MONSTOR` (`:638-642`).
- **Direct floor path already exists.** `InitDunEnterMenu(texture_block, dungeon, requested_floor)` takes `DUN_ENTER_DIRECT` when `requested_floor >= 0` and returns that floor after the short fade (`chronicle:ps2/src/menu_dungeon.cpp:425-459`, `:565-603`, result at `:598-602`). The game's own callers always pass -1: `chronicle:ps2/src/dun/gameloop.cpp:4553` (retail) and `chronicle:port/src/dun/movechara.cpp:1812` (port). The result goes to the script's out-pointer and to `SetNowFloor(floor)` (`chronicle:ps2/src/dun/gameloop.cpp:2006-2017`).
- **Floor limits.** The entrance menu's per-dungeon floor counts are `maxFloorTbl__4 = {15, 17, 18, 18, 15, 25, 100}` (`chronicle:ps2/src/menu_dungeon.cpp:100`). The six-entry `MaxFloorTbl` in `dungeonparts.cpp` (`:1513`) is only used by `BtAtraListMake`, which returns early for dungeon 6 (`:1920-1922`), so it is not an overrun.
- **Town arrival.** `EditInit` calls `RunEvent(StartEventNo)` when `StartEventNo >= 0` and `RunEvent(128)` otherwise, then sets `StartEventNo = -1` (`chronicle:port/src/editloop_init.cpp:541-549`). A non-negative `StartEventNo` also skips the town BGM load (`:254-272`) and the loading art (`chronicle:port/src/gameloop.cpp:886`). `EditLoop` consumes the start event on its first frame, and only when `EdDebugEventEnable != 0 && start_event_no > 0` (`chronicle:port/src/editloop.cpp:997`; consumed at `:1015`, reset at `:1030`). A `StartEventNo` of 0 is therefore never started and stays set.
- **Named entrances.** `EdSearchEvent(param, name, map_no, time)` returns the `ED_EVENT_POINT` whose `destination` equals `name` and whose `map_no` equals the key (`chronicle:ps2/src/editloop3.cpp:512-518`). The interior-exit path uses it to put the player back at the door (`chronicle:port/src/editloop.cpp:262-292`). Town `mapinfo.cfg` files store these as text records such as `MAPJUMP <key>,"<name>"` (`chronicle:ps2/src/editmapscript.cpp:1634-1647`; e01's record at line 198 is `MAPJUMP 0,"dungeon"`).
- **Town dungeon gate.** The gate calls `GotoDungeon()` (`chronicle:ps2/src/editloop.cpp:3666-3667`), and the loop turns that into `MapJump(NowEditMap + 200, -1)` (`chronicle:port/src/editloop.cpp:1061-1066`). Each town gates its own dungeon: `NowEditMap` 0 gives 200, 1 gives 201, and so on.
- **World map.** Confirming a place stores `MenuMapJumpMode = MenuGrobalMapNoTbl[cursor]` (`chronicle:ps2/src/battlemenu.cpp:9227-9236`). The town's menu branch then calls `MapJump(MenuMapJumpMode, -1)` and `RunSystemEvent(2, ...)` with `integer_arguments[0]` set to the destination (`chronicle:port/src/editloop.cpp:593-601`). Script opcodes read `integer_arguments` (`chronicle:ps2/src/editloop3.cpp:7770`). The departure event is therefore the game's own travel animation, and it leaves through the same exit flag (inference: system event 2 was not decoded).
- **Progress gates are UI-only.** The travel page is locked while `QuestDungeon(0, 0) == 0` (`chronicle:ps2/src/menu_misc.cpp:94-104`). A place is shown when `GetVisitInfo` is non-zero (`chronicle:ps2/src/battlemenu.cpp:8898-8906`; `:9996-10040`): towns and field maps by `VisitMap(map)`, dungeons by `QuestDungeon(d)`. Demon Shaft unlocks on the game-clear word (`config[14]`) and a visit to field s30 (map 40) (`chronicle:ps2/src/battlemenu.cpp:8832-8848`). That check has a precedence slip: `VisitMap(MenuGrobalMapNoTbl[15] <= 0, 0)` at `:8836` tests `VisitMap(0, 0)`. None of these checks run on a direct `MapJump`.
- **Visit flags are set on entry.** `EditInit` marks the map visited (`chronicle:port/src/editloop_init.cpp:132`). `InitDunEnterMenu` calls `QuestDungeon(dungeon, 1)` (`chronicle:ps2/src/menu_dungeon.cpp:437`), and the direct path does too.
- **Startup jump grammar.** `GameSetJump` parses `edit[:n]`, `dungeon[:n]` (n must be at most 6), `title`, `rush`, `opening` and `menu` (`chronicle:port/src/gameloop.cpp:565-598`). It accepts any non-negative `edit` number, so it is not a whitelist. `--jump` and `DC_JUMP` feed it (`chronicle:port/src/main.cpp:373-386`). `ApplyJump` writes `mode` directly for EDIT (`chronicle:port/src/gameloop.cpp:352-359`), which is only safe at startup.

## How it works

### Map-number namespace

Three ranges share `NextMapNo` and `MapNo` (`chronicle:port/src/gameloop.cpp:403-439`):

| Range | Mode | Meaning |
|---|---|---|
| 0-98, 100-109 | EDIT (`MapNo` = n) | towns 0-4, sub-maps (`gedit/sNN`, n = NN + 10), interior test 99 |
| 200-206 | DUNGEON (`LocalMapNo` = n - 200) | dungeons 0-6 |
| 400 | OPENING | opening movie |
| 800 / 801 | TITLE / RUSH | title / attract movie |
| 1000 | SAVE (ending) | ending save screen |
| 300-399, 401-799 | none | ignored; `mode` keeps the exit mode's value |

Town folders are `gedit/eNN` with NN = MapNo + 1 for MapNo 0-4 (`chronicle:ps2/src/editloop.cpp:721-723`). Sub-map folders are `gedit/sNN` with NN = MapNo - 10 (`:725-735`). Sub-map folder names are Shift-JIS labels, not translated here.

### Leaving cleanly

Both loops end with one flag and return a non-zero code, and the main loop does the rest:

1. A host (or the game's own script) sets `exit_loop` (town) or `existFlag` (dungeon) during a frame.
2. The loop finishes that frame, runs its own cleanup (`EditExit`, or the `existFlag` block), and returns non-zero.
3. `GameApplyLoopResult` puts `mode` at MENU (town and dungeon exits).
4. The frame loop ends. `MGBeginFrame` and `MGEndFrame` run once more as a blank frame (`chronicle:port/src/gameloop.cpp:951-952`), then `GameFollowMapJump` applies `NextMapNo` (`:954`), then `ReadBGSync` is drained (`:963-965`).
5. `ModeInit` runs the destination's Init; `check_now_loading` spins until the loading screen ends (`:896-901`).

`MGEndFrame` also runs in nested places: `EditLoop` calls it at `chronicle:port/src/editloop.cpp:250` and `:544` (with matching `MGBeginFrame` at `:258` and `:558`), inside its interior-exit and door-open branches. A checkpoint placed in `MGEndFrame` must tell those apart from RunGame's own frame ends (steps 4 and the blank frame at `:951-952`).

### Safe states for a leave request

Predicate by state, from the code paths above. "Honoured" means the loop reaches its exit test in that frame.

| State (globals) | Host `MapJump` alone | Host action | Verdict |
|---|---|---|---|
| Town walk / talk / georama (`GameMode` 1, 2, 4) | ignored until the loop returns | `exit_loop = 1` at a frame boundary | safe |
| Town menus (`GameMode` 6, 8, 9, 10; fishing 16) | exit honoured at the tail; menu left open | `exit_loop = 1`; `EditInit` resets menus (`chronicle:port/src/editloop_init.cpp:535`) | defer in the predicate (the exit would work; waiting keeps the menu's own cleanup) |
| Town event (`GameMode` 14) | exit honoured; `EditSave` runs mid-script | `exit_loop = 1` | exit is what `_MAP_JUMP` does, but save may hold a half-run event; prefer waiting for `GameMode == 1` |
| Town door open (11) or interior (12, `EdInteriorFlag == 1`) | exit ignored (early returns at `:324`, `:562`) | defer; port hook needed to reach `EditInLoop` | defer |
| Town interior test (`MapNo == 99`, `interior_test`) | exit ignored (`:396`) | none | refuse (not a station) |
| Town already leaving (`end_counter != 0`, `goto_dungeon`, `exit_loop`) | exit honoured; end code overrides | none | defer |
| Dungeon play or first-person (`gameTask` 0x0, 0xA; `BtGameModeFlag == BT_GAME_MODE_PLAY`) | `existFlag` honoured | `existFlag = 1` | safe |
| Dungeon battle, item, entrance or escape-message window (`BtGameModeFlag` != PLAY) | honoured after the switch; window state left open | defer | defer |
| Dungeon script (`gameTask` 0x190, 0x191) | honoured; `read_buffer` not restored | defer, or restore `read_buffer` first | defer |
| Dungeon fades and exits (`gameTask` 0x97, 0x98, 0xAA, 0xAB, 0xAF, 0xB0, 0xC8-0xCA) | races the game's own `MapJump` | none | refuse (already leaving) |
| Dungeon pause or debug (`gameTask` 0x9B, 0xDC-0xE4) | honoured | defer | defer |
| TITLE, RUSH, OPENING, developer MENU (`gameloop.cpp:465, 469, 477, 516, 532`); SAVE, LOADER, LANGUAGE, MEMORY_CHECK, TRIAL_END (no own `MapJump`; the exit sets `mode` directly, `chronicle:port/src/gameloop.cpp:446-449`, `:496-523`) | overwritten by that mode's own `MapJump` (first group); not overwritten in the second group, so a host jump would reach `GameFollowMapJump` (inference) | none | refuse |
| Init or loading spin (`ModeInit`, `check_now_loading`) | no RunGame frame end | none | not applicable |

Detection needs only globals the code already has: `mode`, `GameMode`, `EdInteriorFlag`, `MapNo`, `interior_test`, `end_counter`, `goto_dungeon`, `exit_loop` (`chronicle:ps2/src/editloop.cpp:145-146`, `:192`), `existFlag`, `BtGameModeFlag`, `gameTask`. The town fields are file-level, so the predicate needs a port accessor.

### Entering a dungeon at a floor

The loader reads only `main_select_menu_no` (and so `selectMapNo`). The floor is `UserStatus->cur_floor`, which `GameInit` zeroes and the entrance window sets. Two ways to set it:

- **Preferred: the direct entrance path.** Pass the wanted floor as `requested_floor` to the call that opens the entrance window (`chronicle:port/src/dun/movechara.cpp:1812`). That call takes the game's own path: `DUN_ENTER_DIRECT`, a short fade, the result written to the script's out-pointer, and `SetNowFloor(floor)` (`chronicle:ps2/src/dun/gameloop.cpp:2006-2017`). The script then builds the floor as it normally does. Side effects: `QuestDungeon(d, 1)` and a possible raise of `floor_reached[d]`. No retail caller passes a floor, so this path is untested in the retail game (inference: it reads cleanly).
- **Post-`GameInit` injection** (`ixion:docs/research/c1-dungeons.md`, hook 4): set `cur_floor = F - 1` and `prev_floor = 0` before the first tick. Script 100 then takes its else branch. Not tested. It depends on the script's `+1` arithmetic.

`BtSetMapJumpFloor` (the script-honoured route in `c1-dungeons.md`, hook 3) only works for dungeons 2, 3 and 5, and only if the script reads it (unverified). It is a secondary option.

### Arriving in a town

- **Default:** `StartEventNo = -1` gives `RunEvent(128)` (`chronicle:port/src/editloop_init.cpp:541-547`). Event 128 is the town's ordinary arrival event; its content was not decoded (`ixion:docs/research/c1-towns-georama.md`).
- **Chosen event:** `StartEventNo = n > 0` plays event n instead. It also skips the BGM and loading art, so the host must load them itself if wanted.
- **Chosen entrance:** after `EditInit`, the host can call `EdSearchEvent(&entry, name, key, NowTime)` and place `Chara` and the camera as the interior-exit path does (`chronicle:port/src/editloop.cpp:262-292`). Event 128 has to be suppressed first: clear `start_event_no` before the first `EditLoop` frame, which that frame's start-event gate then skips (`chronicle:port/src/editloop.cpp:997`).
- **Chosen position:** the same placement, from an `ED_EVENT_POINT`'s `position` and `rotation` (`chronicle:ps2/include/edit.hpp:68-78`).

### Station table

Towns (`MapNo`, names from the port's table at `chronicle:port/src/presence.cpp:42-48`, which matches `TOWN_*` at `chronicle:ps2/include/editground.hpp:14-20`):

| MapNo | Name | Folder | `mapinfo` | `event.stb` | Jump | World-map place | Dungeon gate |
|---|---|---|---|---|---|---|---|
| 0 | Norune Village | `gedit/e01` | yes | yes | `edit:0` | 0 | 200 |
| 1 | Matataki Village | `gedit/e02` | yes | yes | `edit:1` | 2 | 201 |
| 2 | Queens | `gedit/e03` | yes | yes | `edit:2` | 5 | 202 |
| 3 | Muska Lacka | `gedit/e04` | yes | yes | `edit:3` | 7 | 203 |
| 4 | Yellow Drops | `gedit/e05` | yes | yes | `edit:4` | 11 | 204 |

Load precondition for all five: none found in `EditInit` beyond the folder and `mapinfo` (`chronicle:port/src/editloop_init.cpp:124-200`). The port's own test hook starts town 1 from a fresh save (`docs/PC.md`, "--jump menu enters town 1"), but no note says whether every town was run.

Dungeons (`D`, debug names from `chronicle:ps2/src/dun/gameloop.cpp:9471-9474`, enum names from `chronicle:ps2/include/dungeon.h:7-16` and `chronicle:port/src/presence.cpp:32-40`):

| D | Name | Debug name | Jump | Entry `MapNo` | Floors (menu max) | Exit `MapNo` (folder) | World-map place |
|---|---|---|---|---|---|---|---|
| 0 | Divine Beast Cave | Cave of the Sacred Beast | `dungeon:0` | 200 | 15 | 0 (e01) | 1 |
| 1 | Wise Owl Forest | Forest of the Own | `dungeon:1` | 201 | 17 | 1 (e02) | 3 |
| 2 | Shipwreck | Sunken Ship | `dungeon:2` | 202 | 18 | 19 (s09) | 6 |
| 3 | Sun and Moon Temple | Shrine of Sun and Moon | `dungeon:3` | 203 | 18 | 42 (s32) | 9 |
| 4 | Moon Sea | MoonOcean | `dungeon:4` | 204 | 15 | 23 (s13) | 12 |
| 5 | Gallery of Time | DarkHeven Castle | `dungeon:5` | 205 | 25 | 38 (s28) | 14 |
| 6 | Demon Shaft | Deamon Shaft | `dungeon:6` | 206 | 100 | 60 (s50) | 15 |

Exit map numbers are from `chronicle:port/src/dun/movechara.cpp:2145-2176`. The "Dark Heaven" in the brief is the debug name of dungeon 5. The enum comment calls it "Dark Heaven Castle in the map files" (`chronicle:ps2/include/dungeon.h`), and the port's presence table calls it Gallery of Time. No separate map number exists for it. Dungeon 5's floor 24 uses a second boss map (`ixion:docs/research/c1-dungeons.md`).

Load preconditions for dungeons: `GameInit` reads no progress flag. A first visit (`floor_reached == -1`) builds the Atla list (`chronicle:ps2/src/dun/gameloop.cpp:1887-1888`). The travel page's gates (above) are UI-only. Demon Shaft's place is map 60, not 206. `dungeon:6` still goes through `MapJump(206)` and loads as a dungeon.

World-map places (`chronicle:ps2/include/battlemenu.hpp:281-299`; `MenuGrobalMapNoTbl` at `chronicle:ps2/src/battlemenu.cpp:8771`):

| Place | Name | MapNo | Jump |
|---|---|---|---|
| 0 | Norune Village | 0 | `edit:0` |
| 1 | Divine Beast Cave | 200 | `dungeon:0` |
| 2 | Matataki Village | 1 | `edit:1` |
| 3 | Wise Owl Forest | 201 | `dungeon:1` |
| 4 | Field map s04 | 14 | `edit:14` |
| 5 | Queens | 2 | `edit:2` |
| 6 | Shipwreck | 202 | `dungeon:2` |
| 7 | Muska Lacka | 3 | `edit:3` |
| 8 | Field map s32 | 42 | `edit:42` |
| 9 | Sun and Moon Temple | 203 | `dungeon:3` |
| 10 | Field map s13 | 23 | `edit:23` |
| 11 | Yellow Drops | 4 | `edit:4` |
| 12 | Moon Sea | 204 | `dungeon:4` |
| 13 | Field map s30 | 40 | `edit:40` |
| 14 | Gallery of Time | 205 | `dungeon:5` |
| 15 | Demon Shaft | 60 | `edit:60` (sub-map s50; the dungeon 206 is not used) |

Sub-maps (`gedit` folders; `mapinfo.cfg` is present in every directory). Names are not mapped beyond the world-map places above.

| MapNo | Folder | `event.stb` | Load note |
|---|---|---|---|
| 11, 13, 14, 19, 21-27 | s01, s03, s04, s09, s11-s17 | yes | 14 is field s04 |
| 31, 32 | s21, s22 | n/a | plain files, not folders: not loadable |
| 33-41 | s23-s31 | yes | 38 is dungeon 5's exit (s28); 40 is field s30 |
| 42-51 | s32-s41 | yes | 42 is field s32 |
| 52-59 | s42-s49 | no | no start event (`EdEventInit` with NULL data returns 0; `chronicle:ps2/src/editloop3.cpp:8470-8473`) |
| 60, 61 | s50, s51 | yes | 60 is the Demon Shaft exit and place |
| 86 | s76 | no | no start event |
| 87-89 | s77-s79 | yes | |
| 90-95 | s80-s85 | no | no start event |
| 96-98 | s86-s88 | yes | |
| 100-109 | s90-s99 | yes | |
| 99 | (none; `gedit/interior`) | n/a | interior test: not a station |
| 5-10, 12, 15-18, 20, 28-30, 62-85 | no folder | n/a | refuse |

Sub-maps are not checked for story flags on the direct path; `EditInit` only marks them visited. Whether a sub-map's arrival script needs flags was not checked.

### Jump grammar for travel

The runtime grammar keeps `--jump`'s spelling and adds one form:

- `edit:<n>`, n from the station table (towns and sub-maps), with 99 and the gaps refused;
- `dungeon:<d>`, d 0-6, and optionally `dungeon:<d>:<floor>` with floor below the menu maximum for that dungeon;
- `title`, `rush`, `opening`, `menu` are refused for travel.

## Proposed Ixion code

All of this is port-only (`port/src/`). Nothing goes in `ps2/src`. The Ixion module exports only `ixion_get_api`, and the travel API is called from the plugin (`ixion:docs/HOP-V0.md`, "Each game as a module").

**1. Frame phase, in `chronicle:port/src/gameloop.cpp` (`RunGame`, lines 909-954).**

```cpp
// port/src/gameloop.cpp, RunGame
enum class C1FramePhase : std::uint8_t { kOutside, kModeLoop, kModeReturned };
C1FramePhase g_c1_phase = C1FramePhase::kOutside;

// set just before ModeLoop (line 922):        g_c1_phase = C1FramePhase::kModeLoop;
// set after the language block (after 932):   g_c1_phase = result != 0 ? C1FramePhase::kModeReturned : C1FramePhase::kOutside;
// set before the blank frame (before 951):    g_c1_phase = C1FramePhase::kModeReturned;
// set after the frame loop (before 954):      g_c1_phase = C1FramePhase::kOutside;
```

Also split `GameSetJump`'s parser (`chronicle:port/src/gameloop.cpp:565-598`) into `bool ParseJumpSpec(std::string_view spec, Jump &out)`, shared by `--jump` and the travel request. It must not write `g_jump`.

**2. Header, `port/src/ixion_travel.hpp` (new).**

```cpp
enum class C1TravelState : std::uint8_t { kIdle, kRequested, kLeaving, kArrived, kRefused };
enum class C1Safety : std::uint8_t { kSafe, kDefer, kRefuse };

struct C1TravelStatus {
    C1TravelState state;
    int           map_no;       // NextMapNo to apply (<200 EDIT, 200-206 DUNGEON)
    int           start_event;  // StartEventNo to apply (-1 = default arrival event 128)
    int           dungeon;      // -1 unless a dungeon destination
    int           floor;        // -1 = normal entrance window; >= 0 = direct floor
    const char   *reason;       // last refusal or deferral, or nullptr
};

bool         C1TravelRequest(const char *destination);      // "edit:<n>", "dungeon:<d>[:<floor>]"
void         C1TravelApplyAtCheckpoint();                   // end of MGEndFrame, after DBuffID flip
C1Safety     C1TravelSafety(const char **reason);           // reads the globals listed below
int          C1TravelTakeDungeonFloor(int dungeon);         // -1 when none pending
void         C1TravelAfterModeInit();                       // optional: entrance placement, EDIT only
C1TravelStatus C1TravelInspect();
```

**3. `C1TravelRequest`, `port/src/ixion_travel.cpp` (new).** Writes only the travel record.

```cpp
bool C1TravelRequest(const char *destination) {
    if (g_travel.state == C1TravelState::kRequested || g_travel.state == C1TravelState::kLeaving) {
        return refuse("a travel is already pending");           // one at a time
    }
    Jump jump;
    if (!ParseJumpSpec(destination, jump)) {                    // shared with --jump
        return refuse("bad spec");
    }
    if (jump.mode == GAME_MODE_EDIT) {
        if (!C1IsStationMap(jump.map)) return refuse("not a station");   // table above
        g_travel = {C1TravelState::kRequested, jump.map, -1, -1, -1, nullptr};
        return true;
    }
    if (jump.mode == GAME_MODE_DUNGEON) {                       // jump.map is 0-6
        int floor = jump.floor;                                  // new optional field
        if (floor >= 0 && floor >= C1DungeonFloorMax(jump.map)) return refuse("floor out of range");
        g_travel = {C1TravelState::kRequested, 200 + jump.map, -1, jump.map, floor, nullptr};
        return true;
    }
    return refuse("title, rush, opening and menu are not towns or dungeons");
}
```

**4. `C1TravelApplyAtCheckpoint`, called at the end of `MGEndFrame` (`chronicle:port/src/mglib.cpp:651`, after `DBuffID = !DBuffID`).** It runs before Hop's `EmbedCheckpoint`, so a parked game resumes with its state already applied (unverified: `EmbedCheckpoint` is not in the Ixion sources checked). It does no pumping and no drawing.

```cpp
void C1TravelApplyAtCheckpoint() {
    if (g_c1_phase == C1FramePhase::kModeLoop) return;          // nested frame end inside a mode loop
    switch (g_travel.state) {
    case C1TravelState::kRequested: {
        if (g_c1_phase != C1FramePhase::kOutside) return;       // leave only from a frame boundary
        const char *why = nullptr;
        if (C1TravelSafety(&why) != C1Safety::kSafe) {
            g_travel.reason = why;                              // stays pending; retried next frame end
            return;
        }
        if (mode == GAME_MODE_EDIT) {
            exit_loop = 1;                                      // == EdExitLoop()
        } else {                                                // GAME_MODE_DUNGEON
            existFlag = 1;                                      // GameLoop tail, dun/gameloop.cpp:2048
        }
        g_travel.state = C1TravelState::kLeaving;
        return;
    }
    case C1TravelState::kLeaving:
        if (g_c1_phase != C1FramePhase::kModeReturned) return;  // mode has returned; GameApplyLoopResult ran
        NextMapNo = g_travel.map_no;                            // overrides any MapJump the mode wrote
        StartEventNo = g_travel.start_event;
        g_travel.state = C1TravelState::kArrived;
        return;
    default:
        return;
    }
}
```

**5. `C1TravelSafety`, `port/src/ixion_travel.cpp` (new).** The predicate from the table above. `refuse`, `defer`, `refuse_or` and `C1IsStationMap` / `C1DungeonFloorMax` are small helpers (not defined in this note); `C1DungeonFloorMax` takes the per-dungeon menu maxima (`chronicle:ps2/src/menu_dungeon.cpp:100`), which are `static` there and need a copy.

```cpp
C1Safety C1TravelSafety(const char **reason) {
    switch (mode) {
    case GAME_MODE_EDIT:
        if (MapNo == 99 || interior_test != 0)                    return refuse_or(C1Safety::kRefuse, "interior test", reason);
        if (EdInteriorFlag != 0 || GameMode == ED_MODE_MAP_JUMP
            || GameMode == ED_MODE_DOOR_OPEN)                     return defer("in an interior or door", reason);
        if (end_counter != 0 || goto_dungeon != 0 || exit_loop != 0) return defer("already leaving", reason);
        if (GameMode == ED_MODE_EVENT)                            return defer("event running", reason);
        if (GameMode != ED_MODE_WALK && GameMode != ED_MODE_TALK && GameMode != ED_MODE_GEORAMA)
                                                                  return defer("menu open", reason);
        return C1Safety::kSafe;
    case GAME_MODE_DUNGEON:
        if (existFlag != 0)                                       return defer("already leaving", reason);
        if (gameTask != GAME_TASK_PLAY && gameTask != GAME_TASK_EYE_CAMERA) return defer("dungeon busy", reason);
        if (BtGameModeFlag != BT_GAME_MODE_PLAY)                  return defer("dungeon menu open", reason);
        return C1Safety::kSafe;
    default:
        return refuse_or(C1Safety::kRefuse, "not in a town or dungeon", reason);
    }
}
```

The `end_counter`, `goto_dungeon` and `exit_loop` globals are file-level in `chronicle:ps2/src/editloop.cpp:145-146, 192`. `interior_test` and `EdInteriorFlag` need port accessors if they are not already visible.

**6. `C1TravelTakeDungeonFloor`, called at `chronicle:port/src/dun/movechara.cpp:1812`.** Replace the `-1` argument.

```cpp
// was: InitDunEnterMenu(0x17, selectMapNo, -1);
InitDunEnterMenu(0x17, selectMapNo, C1TravelTakeDungeonFloor(selectMapNo));

int C1TravelTakeDungeonFloor(int dungeon) {
    if (g_travel.state != C1TravelState::kArrived || g_travel.dungeon != dungeon || g_travel.floor < 0) return -1;
    int floor = g_travel.floor;
    g_travel.floor = -1;                                         // one-shot
    return floor;
}
```

**7. `C1TravelAfterModeInit` (optional), called from `RunGame` after `ModeInit` (`chronicle:port/src/gameloop.cpp:896`) and before the first frame.** Only for an entrance or position arrival in a town. It needs `entrance`, `entrance_name` and `entrance_key` fields on the travel record, which the struct in step 2 does not yet have.

```cpp
void C1TravelAfterModeInit() {
    if (g_travel.state != C1TravelState::kArrived || mode != GAME_MODE_EDIT || !g_travel.entrance) return;
    start_event_no = -1;                                          // suppress event 128 (editloop.cpp:997)
    ED_EVENT_PARAM entry;
    if (EdSearchEvent(&entry, g_travel.entrance_name, g_travel.entrance_key, NowTime) != 0) {
        Chara->SetPosition(entry.position);                       // same as editloop.cpp:262-292
        Chara->SetRotation(entry.rotation[0], entry.rotation[1], entry.rotation[2]);
        MainCamera.SetPos(entry.camera_pos);
        // ...rest of the interior-exit placement, copied from editloop.cpp:262-292
    }
}
```

## Risks and blockers

- **Silent no-op.** A `MapJump` alone does nothing while the mode returns 0. Any host that only writes `NextMapNo` will see the game keep running. The predicate and the flag are both needed.
- **Overwrite by the mode's own exit.** The title, rush, opening, developer menu and interior exits write `NextMapNo` themselves. Apply only after `GameApplyLoopResult` (step 4), and refuse those modes outright.
- **Interior is unreachable.** `exit_loop` is ignored inside interiors and for MapNo 99. Leaving an interior needs a port-side flag read at `chronicle:port/src/edit_in.cpp:864` (where `end_count == 1` already returns 99), or a deferral until the player walks out.
- **Mid-event save.** `EditExit` saves the town. Leaving during a town event saves a half-run script. Prefer waiting for `GameMode == ED_MODE_WALK`.
- **Dungeon script state.** A host exit mid-script leaves `read_buffer` pointing into the script buffer, and the next `GameInit` copies it into `old_read_buffer` (`chronicle:port/src/dun/movechara.cpp:1764`, `chronicle:ps2/src/dun/gameloop.cpp:1465`). Restore `read_buffer = old_read_buffer` when leaving from a script, or defer.
- **Dungeon globals persist.** `GameInit` sets `script_no` and `ext_memory` (`chronicle:ps2/src/dun/gameloop.cpp:1972-1973`) but not `BtEventInfo.request` or other pending requests. The port does not re-run overlay constructors (`docs/PC.md`, "Overlay re-initialisation"). A travel started with a request queued could open a stray window in the next dungeon.
- **Passenger record vs. HP and character.** The exit block refills HP and sets `cur_chara = CHARA_TOAN` (`chronicle:ps2/src/dun/gameloop.cpp:2065-2081`), and `GameInit` refills HP again (`:1418-1429`), unless `BtEventInfo.no_status_recover == 1`. A passenger HP ratio or active character applied before `GameInit` is overwritten. Apply it after `GameInit`, or set `no_status_recover` for the travel (v1 part b).
- **Start-event ordering.** `EditInit` calls `RunEvent(128)` and the event starts on the first frame. A chosen-entrance arrival must clear `start_event_no` before that frame (proposal step 7). If the town's default position comes from event 128 itself, placing the player without it may leave the camera or position unset (not traced).
- **`StartEventNo` of 0.** Never starts (`chronicle:port/src/editloop.cpp:997`) and is not reset, so it would linger. The grammar must not produce it.
- **Missing or broken data.** Sub-maps 31 and 32 are files, not folders, so `gedit/s21/mapinfo.cfb` cannot load. Sub-maps 52-59, 86 and 90-95 have no `event.stb`, so they start with no event. `EdEventInit` returns 0 on NULL data (`chronicle:ps2/src/editloop3.cpp:8470-8473`), so there is no crash on that path (inference from the guard; not run).
- **Unvalidated spec.** `GameSetJump` accepts any `edit:n` (`chronicle:port/src/gameloop.cpp:565-598`). `edit:200` would enter EDIT with a dungeon number, which is a corrupt state. The runtime parser must whitelist.
- **Demon Shaft gate bug.** `VisitMap(MenuGrobalMapNoTbl[15] <= 0, 0)` at `chronicle:ps2/src/battlemenu.cpp:8836` tests `VisitMap(0, 0)`. Not reached by the travel path, but a host that mirrors the travel page's gate would inherit it.
- **Crash containment.** `__assert` exits the process (`ixion:docs/research/c1-mainloop-control.md`). A bad jump that crashes takes both games down.
- **Pinned data.** The extracted DC1 tree is not in git. The station table is from folder listings and code, not from a running game.

## Open questions

1. Which station loads cleanly from a fresh save? The port's `--jump` runs `dungeon:0` headless and `--jump menu` enters town 1 (`docs/PC.md`, lines 564 and 689); no note there documents `dungeon:6` running (unverified). A headless run per station would settle it. Not run here.
2. What does event 128 do in each town, and does it position the player? Its `event.stb` payload was not decoded (`ixion:docs/research/c1-towns-georama.md`, Open questions).
3. What position does a town use when no start event runs (for example a sub-map with no `event.stb`)? `EditInit` was not traced past the event start.
4. Does `EdEventInit` fully reset the script VM after an exit from mid-script? The retail `_MAP_JUMP` only exits at a script boundary.
5. What does system event 2 (the world-map departure) do with `integer_arguments[0]`? Not decoded; it may be a second travel option to reuse.
6. Are the direct-floor path's side effects (`QuestDungeon`, `floor_reached`, first-visit Atla) acceptable for a travel that the player did not choose (`ixion:docs/research/c1-dungeons.md`, Risks)?
7. Does the Demon Shaft unlock (`config[14]`) need to gate a travel request, or is it a UI-only rule?
8. Does `EditInLoop` have a clean way to return 99 from outside (for example an `EdInteriorForceLeave` flag read at `chronicle:port/src/edit_in.cpp:864`), and does that path run `EditExit` normally?
9. Do any sub-maps (other than 60) use the travel page's `MENU_MOVE_INTERIOR_OUT` path, which may need a different exit?
