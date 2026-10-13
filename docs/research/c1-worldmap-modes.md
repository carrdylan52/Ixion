# Chronicle: game modes, map jumps and the world map

## What this covers

Chronicle's (DC1, PAL PC port) top-level mode machine: the global `mode` value and the
mode-to-mode transitions, the `NextMapNo` map-jump channel that drives them, the per-mode
step functions (title, attract movie, opening movie, town editor, dungeon, developer menu,
save, language), the sub-state machines inside the town and dungeon loops, and the in-game
"world map" travel page. It also marks where a new destination type (Ixion, or any other
world) could be attached and where control could be handed away and back.

Read-only research. Nothing was built or run. Line numbers are from the Chronicle checkout
at master 3bc16763. Retail-side code is `ps2/src`, port-side code is `port/src`.

## Key facts

- The top-level loop is `main()` in the retail unit (chronicle:ps2/src/main.cpp:436). The PC
  port's `Run` (chronicle:port/src/main.cpp:367) calls `RunGame` at chronicle:port/src/main.cpp:450
  (defined at chronicle:port/src/gameloop.cpp:791); the port's `main` is at chronicle:port/src/main.cpp:471. `RunGame` is the port's reproduction of
  the retail loop: one `switch` for setup, one `do { ... } while (result == 0)` per mode.
- The mode values are the `GameMode` enum in chronicle:ps2/include/main.hpp (values 0-14).
  Real modes: TITLE 0, RUSH_MOVIE 1, EDIT 2, DUNGEON 3, OPENING 5, MENU 7 (developer menu),
  LOADER 9 (dungeon picker), MEMORY_CHECK 10, TRIAL_END 11, SAVE 13, LANGUAGE 14. Values 4,
  6, 8 and 12 are documented as never entered (chronicle:ps2/include/main.hpp:16-32).
- Overlay file per mode: `binfile[15]` maps 0, 1, 5 to TITLE.BIN; 3, 4, 8, 9 to DUN.BIN;
  the rest to nothing (chronicle:ps2/src/main.cpp:274-276). The PC build links both
  overlays into the executable; `LoadOverlay` only decides whether to re-run the title
  overlay's constructors (`TitleOverlayConstruct`); the dungeon overlay re-runs nothing
  (chronicle:port/src/runtime.cpp:54-67).
- Map transitions go through one channel: `MapJump(map_no, event_no)` only writes
  `NextMapNo` and `StartEventNo` (chronicle:ps2/src/main.cpp:1053-1056). The loop consumes
  `NextMapNo` once, after the mode's loop has returned (chronicle:ps2/src/main.cpp:982;
  chronicle:port/src/gameloop.cpp:960 calls `GameFollowMapJump`).
- `GameFollowMapJump` (chronicle:port/src/gameloop.cpp:409-445) is the only place that
  turns a map number into a mode. The ranges, from the code:
  - `< 200`: EDIT, `MapNo = n`. Towns are 0-4, sub-maps start at 11, 99 is the interior test.
  - `200 <= n < 300`: DUNGEON, `LocalMapNo = n - 200`, `main_select_menu_no = LocalMapNo`.
    Dungeons are 200-206 (`Dungeon` enum, chronicle:ps2/include/dungeon.h:7-16).
  - `== 400`: OPENING.
  - `>= 800`: TITLE for 800, RUSH_MOVIE for 801, otherwise `MapNo` is set and the mode is
    left alone. `1000` is special: it sets SAVE with `mc_mode = SAVE_MENU_MODE_ENDING`
    (chronicle:port/src/gameloop.cpp:439-443).
  - 300-399 and 401-799 match no branch and are silently ignored (`OldMapNo` is still set).
- What each mode's loop returns decides the next mode in `GameApplyLoopResult`
  (chronicle:port/src/gameloop.cpp:447-546). The retail version is the same table written
  as ifs in the `switch (mode)` after `old_main_mode = mode` (chronicle:ps2/src/main.cpp:763-1033).
- Title exits: `TitleLoop` returns `CCursol.GetSelect() + 1` on `TITLE_STEP_EXIT`
  (chronicle:ps2/src/title/titleloop.cpp:727-731). New game is 1 (goes to `MapJump(400)`,
  the opening movie, then `MapJump(0)` into Norune). Load is 2 (goes to the saved map). The
  attract selection is 4 (goes to `MapJump(801)`). See the inference note in Risks.
- A non-debug boot never lingers in the developer menu. At the top of each frame, if
  `mode == MENU` and DebugMode is off, the loop sets `MapNo = 801` and `mode = RUSH_MOVIE`.
  The DebugMode test is PAL-only: the non-PAL branch (chronicle:ps2/src/main.cpp:573) has none
  (PAL: chronicle:ps2/src/main.cpp:571-575; port: chronicle:port/src/gameloop.cpp:874-877).
- The save file records the current map on every mode start: the loop writes `MapNo` at
  `SaveData + 0x1C8` (chronicle:ps2/src/main.cpp:727; port: chronicle:port/src/gameloop.cpp:69,
  913). That field is `CSaveData::map_no`, "the map that the game resumes on"
  (chronicle:ps2/include/savedata.hpp:120). Title LOAD jumps to it (chronicle:ps2/src/title/titleloop.cpp:699).
- Town clock: `NowTime` is taken from the save (`SaveData->GetNowTime()`) and advanced with
  `AddNowTime` (chronicle:ps2/src/editloop.cpp:458-467, 3392-3425). It is per save, not per map.
- Visited flags: the editor marks `SaveData->VisitMap(MapNo, 1)` on every town entry
  (chronicle:ps2/src/editloop.cpp:703-712). The travel page gates each place on those flags
  (chronicle:ps2/src/battlemenu.cpp:9996-10030).
- `map.cpp` and `mapobject.cpp` are not part of the mode machine. `CMap` is a category/LOD
  container of scenery objects, declared and used only by the title and movie scene code
  (chronicle:ps2/src/map.cpp; `CMap` users in chronicle:ps2/src/title/op_a.cpp, opening.cpp,
  rushmovi.cpp, title.cpp, titleloop.cpp). `mainselect.cpp` is a 16-line stub; the state
  globals were moved into `main.cpp` (chronicle:ps2/src/mainselect.cpp, chronicle:ps2/src/main.cpp:240-262).
- The world map is not `CMap`. It is the travel page in the battle-menu code: `MenuMove`,
  with 16 fixed places (`WorldMapPlace`, chronicle:ps2/include/battlemenu.hpp:278-300) and a
  place-to-map table `MenuGrobalMapNoTbl` (chronicle:ps2/src/battlemenu.cpp:8771).

## How it works

### Boot

1. `main()` sets `mode = GAME_MODE_MENU`, runs `init_all`, waits for VSync, and runs the
   60-tick warm-up (chronicle:ps2/src/main.cpp:436-545; port: chronicle:port/src/gameloop.cpp:791-870).
2. Retail PAL, not in debug: `MapNo = -1`, `mode = LANGUAGE` (chronicle:ps2/src/main.cpp:544).
   Retail NTSC: `mode = MEMORY_CHECK` directly (chronicle:ps2/src/main.cpp:549).
3. LANGUAGE's result goes to MEMORY_CHECK (PAL) or straight to RUSH_MOVIE with `MapNo = 801`
   (chronicle:ps2/src/main.cpp:779-790). The memory-card check then goes to RUSH_MOVIE with 801
   (chronicle:ps2/src/main.cpp:898-903).
4. The port skips the memory-card check. With one language it applies LANGUAGE result 1 at
   once. With several, it uses the language from config if it is supported, or stops at the
   language screen (chronicle:port/src/gameloop.cpp:842-856; comment at chronicle:port/src/gameloop.cpp:449-453).

### Frame-level loop (one mode's lifetime)

Each mode start runs in this order (`RunGame`, chronicle:port/src/gameloop.cpp:874-960):

1. `LoadOverlay(mode)`, `MGSetRenderInfo`, then for MENU/LOADER/MEMORY_CHECK/LANGUAGE `MapNo = -1`.
2. `init_now_loading(MapNo)` unless `StartEventNo >= 0`. The loading art is keyed by map
   number (chronicle:ps2/src/nowload.cpp:79-115; port: chronicle:port/src/nowload.cpp:182).
3. `ModeInit` (chronicle:port/src/gameloop.cpp:223-287): calls the mode's Init. Its `default`
   calls `GameInit` (the dungeon). Mode 4 and any unknown value therefore run the dungeon.
4. `check_now_loading()` spins until the load screen finishes.
5. The `do { ... } while (result == 0)` frame loop: `MGBeginFrame`, `SetEnv`, `ModeLoop`,
   `GameApplyLoopResult`, `GiveOnArrival`, `GamePad.Step`, `MGEndFrame`, `PresenceTick`,
   `GameCheckDebugToggle`, and the developer-menu chord check. A non-zero result ends the loop.
6. After the loop: `GameFollowMapJump()`, then the trial-end check, then `ReadBGSync`.

### Mode table (retail `main()` ↔ port `ModeInit`/`ModeLoop`/`GameApplyLoopResult`)

| Mode | Init / Loop (retail) | Overlay | Loop result routing |
|---|---|---|---|
| TITLE 0 | `TitleInit` / `TitleLoop` (chronicle:ps2/src/title/titleloop.cpp:242, 440) | TITLE.BIN | 1: EDIT(e01) + MapJump(400); 2: EDIT(menu 1); 4: MapJump(801); 3 and 5 are not reached by the title's own flow (see Risks) |
| RUSH_MOVIE 1 | `RushInit` / `RushLoop` (chronicle:ps2/src/title/rushmovi.cpp:357, 404) | TITLE.BIN | non-zero: MapJump(800) |
| EDIT 2 | `EditInit` / `EditLoop` (chronicle:ps2/src/editloop.cpp:703, 1168) | none | 2: EDIT; any non-zero: MENU (1 is overwritten); 3: DUNGEON |
| DUNGEON 3 | `GameInit` / `GameLoop` (chronicle:ps2/src/dun/gameloop.cpp:1405, 1977) | DUN.BIN | non-zero: MENU, unless a jump is pending |
| OPENING 5 | `OpeningInit` / `OpeningLoop` (chronicle:ps2/src/title/opening.cpp:179, 513) | TITLE.BIN | non-zero: TITLE, then MapJump(0) |
| MENU 7 | `MenuInit` / `MenuLoop` (chronicle:ps2/src/main.cpp:1058, 1087) | none | port: -1 (Circle) returns to the saved mode or MapJump(800) |
| LOADER 9 | `LoaderInit` / `LoaderLoop` (chronicle:ps2/src/dun/gameloop.cpp:9533, 9549) | DUN.BIN | non-zero: DUNGEON (port: result 2 goes to MENU) |
| MEMORY_CHECK 10 | `MemCheckInit` / `MemCheckLoop` (chronicle:ps2/src/main.cpp:1324-1461) | none | non-zero: RUSH(801) |
| TRIAL_END 11 | `TrialEndInit` / `TrialEndLoop` (chronicle:ps2/src/main.cpp:1567-1569) | none | non-zero: `MapNo = 800`, `mode = TITLE` directly (port `GameApplyLoopResult`; no MapJump) |
| SAVE 13 | `InitSave` / `LoopSave` (chronicle:ps2/src/main.cpp:1537, 1561) | none | non-zero: MENU |
| LANGUAGE 14 | `LangsetInit` / `LangsetLoop` (chronicle:ps2/src/langset.cpp:24, 47; port: chronicle:port/src/langset.cpp:7) | none | non-zero: RUSH(801) |

`CheckTrialEnd` always returns 0 (chronicle:ps2/src/main.cpp:1573), so TRIAL_END is never
entered from the loop.

### Title (`titleloop.cpp`)

`CProcess.no` steps: FADE_IN, WAIT, LOGO, MENU, MENU_BLINK, MENU_FADE_OUT, ATTRACT_FADE_OUT,
OPENING_BOOK_INIT, OPENING_BOOK, SAVE_INIT, SAVE, OPTION_INIT, OPTION, RETURN_FADE_IN, EXIT
(chronicle:ps2/src/title/titleloop.cpp:453-736). Menu rows: NEW_GAME 0, LOAD 1, OPTION 2,
ATTRACT 3 (chronicle:ps2/include/title/cursol.hpp:9-13). Idle for 1800 ticks selects ATTRACT
(chronicle:ps2/src/title/titleloop.cpp:609). OPTION always returns to the menu through
RETURN_FADE_IN. The LOAD save screen returns to the menu when cancelled and reaches EXIT only
when a save is loaded (chronicle:ps2/src/title/titleloop.cpp:690-706). EXIT is reached from the
opening book (cursor 0), a loaded save (cursor 1) and attract (cursor 3).

### Attract and opening movies

`RushLoop` and `OpeningLoop` are self-contained scene loops that return 1 when done
(chronicle:ps2/src/title/rushmovi.cpp:404-; chronicle:ps2/src/title/opening.cpp:513-).
Both use `CMap`/`CMapObject` scene objects. The movie modes do not hand control to any other
part of the game beyond the `NextMapNo` result.

### Town editor (`EDIT`, `editloop.cpp`)

- Map naming: `MapNo < 9` gives `e0N`; `MapNo > 10` gives `s<N-10>`; 99 is the interior
  test. The data folder is `gedit/<name>/` (chronicle:ps2/src/editloop.cpp:703-740; port:
  chronicle:port/src/editloop_init.cpp:124-165).
- `GameMode` (the town's sub-mode) is the `EdGameMode` enum (chronicle:ps2/include/editmapscript.hpp:11-29):
  WALK 1, TALK 2, GEORAMA 4, GEORAMA_MENU 5-6, MENU 7-8, RETURN_MENU 9-10, DOOR_OPEN 11,
  MAP_JUMP 12, EVENT 14, FISHING 16. TIME_CHANGE 3 has handlers but no code path sets it.
- Interiors are not maps. Entering a door sets `EdInteriorFlag = 1` and runs `EditInLoop`
  inside the town's loop (chronicle:ps2/src/editloop.cpp:1212-1220; chronicle:ps2/src/edit_in.cpp:582).
  `EditInLoop` returns 1 to walk back out to the town, and 99 to request a map jump.
- Events can ask for a dungeon, an interior, or a map jump through `EdEventInfo.return_code`
  (`EdEventReturn`, chronicle:ps2/include/edit.hpp:10-20). `EventMode` dispatches them
  (chronicle:ps2/src/editloop.cpp:3591-3625). A dungeon request is `GotoDungeon()`
  (chronicle:ps2/src/editloop.cpp:3666), which at the end of the loop becomes
  `MapJump(NowEditMap + 200)` (chronicle:ps2/src/editloop.cpp:2028-2035). So a town's dungeon
  gate uses the town's own number as the dungeon index.
- Ending the loop: `EdExitLoop()` sets `exit_loop` (chronicle:ps2/src/editloop.cpp:608-610).
  Returning 1 without a pending jump falls to MENU, which the non-debug boot turns into the
  attract movie (see Key facts).
- Script opcodes that touch the mode machine: `_WORLD_MAP` opens the travel page
  (chronicle:ps2/src/editloop3.cpp:3576-3583); `_MAP_JUMP` calls `MapJump(arg-1, event)` and
  sets the return code (chronicle:ps2/src/editloop3.cpp:3602-3611; opcode table entry at line 7998);
  `_GOTO_OUTSIDE` sets `outside_map_no` (chronicle:ps2/src/editloop3.cpp:3591-3595).
- Events that stay in the same map: `FadeOutToEvent` (chronicle:ps2/src/editloop.cpp:418-).

### Dungeon (`dun/gameloop.cpp`, `port/src/dun/movechara.cpp`)

- `GameInit` takes the dungeon index from `main_select_menu_no` and sets `selectMapNo`
  and `cur_georama` (chronicle:ps2/src/dun/gameloop.cpp:1405-1420). The dungeon index is
  0-6 (chronicle:ps2/include/dungeon.h:7-16).
- Outer switch: `BtGameModeFlag` (PLAY, BATTLE_MENU, ITEM_SELECT, ENTRANCE_MENU, CHARA_CHANGE,
  ESCAPE_MSG; chronicle:ps2/include/dun/gameloop.hpp:11-18). `GameLoop` returns `existFlag`
  when set (chronicle:ps2/src/dun/gameloop.cpp:2048-2085).
- `existFlag = 1`: a system script's MAP_JUMP (`EdEventInfo.return_code ==
  ED_EVENT_RETURN_MAP_JUMP`) (chronicle:ps2/src/dun/gameloop.cpp:4534; port:
  chronicle:port/src/dun/movechara.cpp:1794). The dungeon script reuses the town's event engine
  (`EdEventMode`, chronicle:ps2/src/dun/gameloop.cpp:4517).
- `existFlag = 2`, the normal exit: `GAME_TASK_EXIT_FADE_WAIT` picks a town from
  `selectMapNo`: 0 to 0, 1 to 1, 2 to 0x13, 3 to 0x2A, 4 to 0x17, 5 to 0x26, 6 to 0x3C
  (chronicle:ps2/src/dun/gameloop.cpp:4892-4918; port copy: chronicle:port/src/dun/movechara.cpp:2145-2176).
- Travel from a dungeon is an escape: the battle menu's move page in dungeon mode is
  `MENU_MOVE_DUNGEON_ESCAPE` (the value 0 matches `BATTLE_MENU_MODE_DUNGEON` 0; see
  chronicle:ps2/src/battlemenu.cpp:390-400, 531-540 and chronicle:ps2/src/menu_misc.cpp:90-107).
  Leaving sets `MenuMapJumpMode` (chronicle:ps2/src/battlemenu.cpp:9138), which ends in the
  table above at `GAME_TASK_MENU_CLOSE` (chronicle:ps2/src/dun/gameloop.cpp:5377; port:
  chronicle:port/src/dun/movechara.cpp:2574-2576). The chosen place is not used there.
- Party wipe: `EXIT_FADE_START` from the character-select death path (chronicle:ps2/src/dun/gameloop.cpp:5461, 5662-5666),
  which exits the same way. In debug mode, the party is revived instead.
- `GAME_TASK_MAPJUMP_FADE_START/WAIT` (which would `MapJump(0x320)`, title) has no code that
  sets it (chronicle:ps2/src/dun/gameloop.cpp:4854-4867; port: chronicle:port/src/dun/movechara.cpp:2113-2124).

### World map (travel page, `battlemenu.cpp`)

- Entry points: a town script's `_WORLD_MAP` (menu_mode 7, chronicle:ps2/src/edit.cpp:2111-2112),
  which calls `InitMenuMove(MENU_MOVE_WORLD_MAP_DIRECT, ...)`; or the battle menu's MOVE page
  (chronicle:ps2/src/battlemenu.cpp:1527-1541), whose mode comes from
  `NowGetGameFlagForBtlMenu` (chronicle:ps2/src/menu_misc.cpp:90-107): INTERIOR_OUT inside an
  interior, LOCKED if the first dungeon is not done, FIRST_DUNGEON early, otherwise WORLD_MAP.
- States (`MenuMoveState`, chronicle:ps2/include/battlemenu.hpp:262-272): SELECT, OPEN, CLOSE,
  ZOOM_IN, CONFIRM, ZOOM_OUT, INTERIOR_FADE. `MenuMoveKey` drives them
  (chronicle:ps2/src/battlemenu.cpp:8922-9290).
- Places: `MenuGrobalMapNoTbl` = {0, 200, 1, 201, 14, 2, 202, 3, 42, 203, 23, 4, 204, 40, 205, 60}
  (chronicle:ps2/src/battlemenu.cpp:8771). The 16 places are town/field maps (0-4, 14, 42, 23,
  40, 60) and dungeons (200-205). `TownOrDngPos` gives each place's model frame name
  (chronicle:ps2/src/battlemenu.cpp:8772-8789). Place 15 (Demon Shaft) maps to 60, not 206.
- Confirm: `MenuMapJumpMode = MenuGrobalMapNoTbl[cursor]` (chronicle:ps2/src/battlemenu.cpp:9229).
  Repeating the current map is refused unless the mode is WORLD_MAP_DIRECT (9231-9234).
- Town side: EDIT's ED_MODE_MENU, after the menu finishes, does
  `MapJump(MenuMapJumpMode, -1)` (chronicle:ps2/src/editloop.cpp:1566-1580). That is the
  world map's hand-off into the mode machine.
- Gate: `GetVisitInfo` reads visit flags (towns and sub-maps by `VisitMap`, dungeons by
  `QuestDungeon`) (chronicle:ps2/src/battlemenu.cpp:9996-10030). Map 1 counts as visited
  for the world map (chronicle:ps2/src/battlemenu.cpp:10029).

### Developer menu and test hooks

- Developer menu: `MenuLoop` lists "game start" (800), `e0N`, sub-maps (11+), "interior" (99),
  "dungeon" (200), "opening" (400), and event/memory/language rows (chronicle:ps2/src/main.cpp:1087-1135).
- Port-only: Start+Select in debug mode leaves any mode and returns to the menu
  (`GameDeveloperMenuRequested` and `GameEnterDeveloperMenu`, chronicle:port/src/gameloop.cpp:623-650).
  The return point is saved in `g_developer_return_*` and restored when the menu exits with -1
  (chronicle:port/src/gameloop.cpp:205-209, 530-541). This is the one existing "suspend and
  resume" pattern in the mode machine.
- `GameSetJump` accepts `edit[:n]`, `dungeon[:n]`, `title`, `rush`, `opening`, `menu`
  (chronicle:port/src/gameloop.hpp:29-36; chronicle:port/src/gameloop.cpp:571-605). The
  `--jump` option and `DC_JUMP` env var feed it (chronicle:port/src/main.cpp:139, 374).

## Ixion hooks

Ixion's destinations should be ports-only, so the seams are in `port/src`, not `ps2/src`
(the PC.md rule: "port accommodations never live in `ps2/src` or `ps2/include`",
chronicle:docs/PC.md Layout section).

1. **Board Ixion from any MapJump caller.** `GameFollowMapJump`
   (chronicle:port/src/gameloop.cpp:409-445) is the single translator. Reserve a range (or a
   port-only flag set by the caller) and send it to a port-owned mode, e.g. `GAME_MODE_IXION`
   (a value outside 0-14, declared in a port header). Keep the `NextMapNo == 1000` and the
   `>= 800` branches intact.
2. **Hand control away and back.** The developer-menu return record
   (chronicle:port/src/gameloop.cpp:205-209, 634-650) is the template: snapshot `mode`, `MapNo`,
   `LocalMapNo` and `main_select_menu_no` on the way out. The pending jump is not saved there; it is
   dropped (`NextMapNo` and `StartEventNo` are reset to -1). Restore the snapshot when the Ixion
   mode's loop returns a code, and fall back to `MapJump(800)` if no snapshot is pending (530-541). `GameApplyLoopResult` is where that return code is
   mapped (chronicle:port/src/gameloop.cpp:447-546).
3. **Register the new mode in every switch.** `ModeInit` and `ModeLoop` (chronicle:port/src/gameloop.cpp:223-340)
   both fall through to the dungeon in `default`. A missing case runs the dungeon, which is the
   easiest way to get a silent wrong mode.
4. **Town-side destination from the world map.** The travel page's confirm
   (chronicle:ps2/src/battlemenu.cpp:9229) and EDIT's hand-off (chronicle:ps2/src/editloop.cpp:1575-1579)
   already turn a chosen place into a map jump. Adding a 17th place touches fixed-size tables
   (`WORLD_PLACE_COUNT`, `MenuGrobalMapNoTbl`, `TownOrDngPos`, the region table in `IsLoadMapNo`
   at chronicle:ps2/src/battlemenu.cpp:10049) and the world-map model frames (see Risks). A
   separate chooser, or a `MenuMapJumpMode` value handled in `GameFollowMapJump`, avoids that.
5. **Script-level hand-off.** `_MAP_JUMP` (chronicle:ps2/src/editloop3.cpp:3602-3611) is the one
   opcode that both town scripts and dungeon scripts use to leave (unverified: only the dungeon side was checked; "the one opcode" was not exhausted) (dungeon side at
   chronicle:ps2/src/dun/gameloop.cpp:4534). It is the natural place for a DC1 event to "board"
   a train or a DC2 map without touching the menus.
6. **Dungeon exit redirect.** The exit table at `GAME_TASK_EXIT_FADE_WAIT`
   (chronicle:port/src/dun/movechara.cpp:2145-2176; retail chronicle:ps2/src/dun/gameloop.cpp:4892-4918)
   is where a dungeon's "return to town" number is chosen. An Ixion hand-off from a dungeon
   would change that number (or add a flag checked before it).
7. **Save and continue.** `SaveData + 0x1C8` is written at every mode start
   (chronicle:port/src/gameloop.cpp:913). Title LOAD jumps to whatever it holds
   (chronicle:port/src/title/titleloop.cpp:288). A new map-number range must either be
   representable there or be mapped to a safe place before saving.
8. **Loading art.** `init_now_loading(MapNo)` (chronicle:port/src/nowload.cpp:182-200) keys the
   image on `mt<N>.tm2` by number. A new range needs its own entry or a fallback.
9. **Overlay table.** `LoadOverlay` (chronicle:port/src/runtime.cpp:54-67) has 15 entries.
   Modes at or above 15 return early and load nothing, which is safe for a port-only mode.
10. **Test hook.** `GameSetJump` (chronicle:port/src/gameloop.cpp:571-605) would take an
    `ixion[:...]` spec in the same style. Headless `--jump` and `DC_JUMP` already exist.

## Risks and blockers

- **Shared globals are the state.** `mode`, `MapNo`, `OldMapNo`, `LocalMapNo`,
  `main_select_menu_no`, `selectMapNo`, `NextMapNo`, `StartEventNo`, `EdInteriorFlag`,
  `MenuMapJumpMode`, `BtGameModeFlag`, `gameTask`, `existFlag` and the town/dungeon `static`s
  all persist across modes. A hand-off must save and reset each of them, not just `mode`.
- **Overlay re-initialisation is partial.** Retail reloads and re-runs overlay constructors on
  each switch; the port links both overlays once and re-runs only the title objects
  (chronicle:docs/PC.md "Known gaps", Overlay re-initialisation). Values from the previous
  visit persist. Crossing into DC2 code may see DC1 leftovers.
- **Map numbers are a single namespace with holes.** Towns 0-4, sub-maps 11+, interior 99,
  opening 400, dungeons 200-206, title 800, attract 801, save 1000. Ranges 300-399 and
  401-799 are ignored by the translator. Any new range must not collide with these, and the
  save file must hold it.
- **Demon Shaft has two numbers in play.** The travel page uses map 60 (`MenuGrobalMapNoTbl[15]`,
  dungeon exit `0x3C`); the loader's dungeon 6 is 206. By `EditInit`'s naming rule, 60 loads as
  sub-map `s50` (inference, not checked against the data).
- **Non-debug fallthrough to the attract movie.** Any mode that exits without a pending jump
  ends in MENU, which a non-debug boot sends to RUSH (chronicle:ps2/src/main.cpp:571-575). A
  new mode that forgets to set a jump will look like "the attract movie".
- **Dead or unreached paths.** `MAPJUMP_FADE_*` tasks and `ED_MODE_TIME_CHANGE` have no code that
  sets them. Title result 3 would need the cursor on OPTION, which never reaches EXIT; result 5
  has no producer in `TitleLoop` (the return is `CCursol.GetSelect() + 1` with cursor values 0-3,
  so results 1-4 only; OPTION never reaching EXIT (unverified)). Mode 4 falls through to the dungeon. These were read from
  the code, not exercised.
- **The world-map model is authored per place.** `TownOrDngPos` names frames (`e01`, `d01`,
  ...) in the region's world-map model. A new place needs its frame in the model, which is data,
  not code (inference from `WORLD_MAP_POS` usage at chronicle:ps2/src/battlemenu.cpp:9754-9846).
- **Port deviations from retail.** LOADER result 2 goes to MENU in the port only. The Circle
  return is at chronicle:port/src/dun/gameloop.cpp:820; the port routes it at
  chronicle:port/src/gameloop.cpp:525-527, while retail sends any non-zero result to DUNGEON
  (chronicle:ps2/src/main.cpp:931-935). The memory-card check and the PAL language
  path are skipped. Anything written against retail's sequence should be checked against
  `port/src/gameloop.cpp`.
- **Town clock is per save.** A DC2-style time-of-day would need to reconcile with
  `SaveData->GetNowTime()` (chronicle:ps2/src/editloop.cpp:3392-3425).

## Open questions

- Whether any MAP_JUMP target in the script data uses a number outside the ranges above.
  This was not scanned (it is data-side, under the extracted game data).
- How ChronicleTwo's mode machine maps onto this one (its MapJump-equivalent, its overlays,
  and its save field). Ixion's cross-world seam depends on both sides agreeing on the
  hand-off record.
- Whether the travel page should grow a DC2 destination in place, or whether a second chooser
  is cleaner.
- Whether a dungeon can be left to a non-town destination (a train) without changing
  `existFlag` semantics, or whether a new `existFlag` value is needed.
- The retail `main()` loop is now replaced by `RunGame` in the port; whether the port's
  developer-menu return record is correct when a loader or a save screen is the interrupted mode
  was not tested.
