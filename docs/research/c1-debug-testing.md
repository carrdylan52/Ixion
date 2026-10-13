# Chronicle (DC1): debug, test and headless facilities

## What this covers

Chronicle's (DC1, repo "Chronicle") debug and test facilities as of master 3bc16763:

- the retail PAL debug code in `ps2/src` (DebugMode, the developer menu, map-jump call sites);
- the port's command-line options, environment variables and "test hooks" (`port/src/main.cpp`, `port/src/gameloop.cpp`);
- scripted input, screenshots and the frame budget used for headless runs;
- `port/src/tests` and the `darkcloud_tests` target, plus the pinned Kazarov test fixtures it links;
- the CI workflow `.github/workflows/pc.yml`.

It answers two Ixion questions: the cheapest way to boot DC1 straight into a given town or dungeon, and how to check a prototype headlessly (screenshots, input scripts, asserts).

Nothing here was built or run. Every command below is a sketch from reading the code and docs, not a tested recipe. Paths are repo-relative.

## Key facts

- **Direct boot exists and is documented.** `--jump MODE[:MAP]` (or `DC_JUMP`) skips the warm-up and the language select, sets `DebugMode`, and starts in `edit:<map>`, `dungeon:<0-6>`, `title`, `rush`, `opening` or `menu`. Bad values exit 2. (chronicle:port/src/main.cpp:51-104 Options/Usage; chronicle:port/src/gameloop.cpp:571-606 `GameSetJump`; chronicle:docs/PC.md "Test hooks")
- **`edit:<map>` is a direct town/interior load.** `ApplyJump` sets `MapNo`, `LocalMapNo` and `main_select_menu_no` to the map and mode to `GAME_MODE_EDIT`; `EditInit` then derives the folder from `MapNo`: below 9 is `e0N` (so 0 is `e01`, Norune), above 10 is `sNN` (`MapNo - 10`), and 99 is the interior test map that loads `gedit/interior/` (chronicle:port/src/gameloop.cpp:353-390; chronicle:ps2/src/editloop.cpp:703-745; chronicle:ps2/src/editloop.cpp:783).
- **`GameSetJump` does not range-check `edit:` numbers.** It accepts any non-negative integer for `edit` (only `jump.map < 0` is refused), so a number with no data folder fails later in the loader (chronicle:port/src/gameloop.cpp:571-606, `edit` branch at :587). `dungeon:` is limited to 0-6 (chronicle:port/src/gameloop.cpp:589).
- **Dungeons jump to floor select, not into a floor.** `dungeon:<n>` calls `MapJump(200 + n)` and leaves the game at the dungeon loader's floor select. Entering floor 1 needs a press in the loader (Cross or Start) (unverified). (chronicle:port/src/gameloop.cpp:367-372; chronicle:ps2/src/dun/gameloop.cpp:9533-9578; chronicle:docs/PC.md "Developer menu")
- **`--give ITEM,...` is the item hook.** Items and weapons (1 to `ITEM_WEAPON_END`, 377) are granted when a town or dungeon starts; one already held is skipped (chronicle:port/src/gameloop.cpp:111-141, 553-569; chronicle:ps2/include/itemdata.hpp:346,463).
- **`--frames N` counts main-loop frames only.** The counter `g_frames` increments after `MGEndFrame` in `RunGame`; loading screens and the pre-frame warm-up do not count (chronicle:port/src/gameloop.cpp:940-947; chronicle:port/src/gameloop.cpp:663-664, 392-394).
- **Screenshots are the last canonical tick image.** `--screenshot PATH` writes `kPreviousFrame` on exit: the newest tick's image, or the loading screen's frame if it presented since. Never a display frame, so never the FPS counter (chronicle:port/src/main.cpp:354-365; chronicle:port/src/gameloop.cpp:781-783; chronicle:docs/PC.md "Command line" table).
- **Headless means unbounded clock and no window.** `--headless` uses SDL's offscreen driver with `VK_EXT_headless_surface`, sets `ClockSetUnbounded(true)`, and falls back to `--offscreen` (image only) when no headless surface exists (chronicle:port/src/main.cpp:440, 431-432 for the renderer; chronicle:docs/PC.md, `darkcloud` options table under "Building and running").
- **Input scripts replay pad and keyboard input by frame.** `--input FILE` (or `DC_INPUT`) takes lines `<frame> [pad1|pad2] [buttons] [key:NAME] [mouseN] [mouse:DX,DY] [wheel:N] [lx ly rx ry]`. Keys and mouse drive pad 1 only. Frames must not decrease per pad. A bad script exits 2 before the window opens (kazarov:port/platform/input_script.cpp:167-190, pinned at a0a5ff8; chronicle:port/src/main.cpp:240-262; chronicle:docs/PC.md "Scripted input").
- **The script can toggle debug mode.** `key:grave` toggles debug mode as the live key does (kazarov:port/platform/input_script.hpp, header comment, pinned at a0a5ff8).
- **`--jump` forces debug mode on.** `RunGame` sets `DebugMode = 1` whenever a jump is set, so every debug-gated branch runs in a jump run (chronicle:port/src/gameloop.cpp:827-830). The retail gate is the `DebugMode` global, read in 15 files under ps2/src and ps2/include (e.g. chronicle:ps2/src/ebattle.cpp:2490, a fishing-cast branch; chronicle:ps2/src/main.cpp:964, the retail toggle).
- **Developer menu is retail code, still present.** `MenuLoop` lists game start, `e0N` towns (1-5), sub maps `sN`, interior, dungeon, opening, three story events (maps 23/41/19 with events 310/150/305), memory-card modes and language (chronicle:ps2/src/main.cpp:1087-1100, 1257). Its version string is "Ver3.07 2001/07/12", a PAL prototype build (unverified) (chronicle:ps2/src/main.cpp, DebugFont text in `MenuLoop`).
- **Start+Select returns to the developer menu from any mode** while `DebugMode` is set (chronicle:port/src/gameloop.cpp:623-653).
- **Event scripts jump maps with a 1-based index.** The `MAP_JUMP` opcode subtracts 1 from the script's map number and takes an optional event (chronicle:ps2/src/editloop3.cpp:3602-3611).
- **Door jumps use the interior's EPARTS data.** `SearchMapJump` walks `EPARTS_FUNC_DOOR` entries and sets `EdInteriorJumpID` (chronicle:ps2/src/edit_in.cpp:1416-1434).
- **Visiting a map records it in the save.** `EditInit` calls `SaveData->VisitMap(MapNo, 1)` on every town or interior load, so a jump marks the map visited (chronicle:ps2/src/editloop.cpp:711).
- **The integration test pattern.** `port/src/tests/integration_gameloop_test.cpp` drives `GameFollowMapJump` and `GameApplyLoopResult` from a `Reset`/`Jump` helper, with no game data, and covers map-jump transitions, loop results, the developer menu, the frame budget and the `--give` parser.
- **Test binary and CI wiring.** `darkcloud_tests` links the whole port and game and compiles every `port/src/tests/*_test.cpp` (glob at chronicle:port/src/tests/CMakeLists.txt:16-17) plus the pinned Kazarov `port/tests/*_test.cpp` (kazarov:cmake/KazarovPort.cmake:124-130, pinned a0a5ff8). The count is 259 `TEST`/`TEST_F` cases in the 28 Chronicle test files and 124 in the 18 Kazarov test files at the pin (counted by grep, approximate). Each case runs in its own process under ctest, timeout `DC_TEST_TIMEOUT` (5 s default, 60 s in CI), and `PlatformClock.*` cases run serially (chronicle:port/src/tests/CMakeLists.txt:26-34).
- **GPU test fixture validates.** Kazarov's `GfxFixture` builds an offscreen or hidden-window renderer with `validation = true`; any Vulkan validation message fails the test (kazarov:port/tests/gfx_fixture.hpp:36-53, pinned a0a5ff8). `area_card_test` writes PNGs from this fixture (chronicle:port/src/tests/area_card_test.cpp:31-41).
- **CI runs the port on three OSes.** Linux (clang-22, Debug, lavapipe, `env -u DC_DATA ctest -j4`, then a pointer-truncation audit with `scripts/port/truncations.py --check`); macOS (MoltenVK, ctest minus two GfxMeshDc2 cases, then headless and windowed `darkcloud` runs with a stand-in data file, expecting exit 0 or 4); Windows (ctest minus Gfx/Tex cases, no darkcloud run); Flatpak (`--headless --frames 1` with no data, expecting exit 3) (chronicle:.github/workflows/pc.yml).
- **Exit codes.** 0 window closed or frames spent; 1 window/renderer/screenshot failure; 2 bad arguments; 3 no game data; 4 a game assertion (retail `__assert`, for example a `LoadFile` of a missing file) (chronicle:port/src/exitcodes.hpp:1-14).
- **Data gaps.** The extracted PAL tree holds `gedit` folders e01-e05, `interior`, and sub maps s01, s03, s04, s09, s11-s17, s21-s51, s76-s88 and s90-s99. Sub maps s02, s05-s08, s10, s18-s20, s52-s75 and s89 are absent from that tree (a directory listing of the extracted data; a `MapNo` for one of those would hit `LoadFile` and exit 4). The extracted `dun/` tree holds dungeon folders d01, d02, d03, d05 and d06 only; d04 and d07 have `.cfg` files but no folder. How `dungeon:<n>` maps to these folder names was not traced, so the mapping to `dungeon:0` to `dungeon:6` is unverified.
- **Existing Windows build predates `--give`.** The darkcloud.exe in a local Windows build dated 2026-10-07 contains the `--jump`, `--input`, `--screenshot`, `--fast-load` and `--display-per-tick` strings but not `--give` (read-only string check). Any Ixion run needs a fresh build from master.
- **Docs drift.** `docs/PC.md` says the `AudioRealData` cases and `audio_real_title_*` tests read the title pack from `DC_DATA`. Neither name exists in the Chronicle tree or the pinned Kazarov tree. The CI comment "The real-data cases skip without DC_DATA" has no matching case either. `docs/PC.md` and `CMakePresets.json` say clang 20; CI passes `clang++-22`.

## How it works

### Start-up path (headless)

1. `main` (chronicle:port/src/main.cpp:471) calls `Run`. `Run` takes `--data`/`--save`, parses options, applies `--jump`, `--give` and `--fast-load` (also from `DC_JUMP`, `DC_GIVE`, `DC_FAST_LOAD`), and calls `RequireData()` (chronicle:port/src/main.cpp:367-395, 163-199).
2. A bad `--jump` or `--give` exits 2 here, before any window. `--jump` stores a `Jump` struct; the mode change happens later in `RunGame` (chronicle:port/src/gameloop.cpp:197-203, 828-857).
3. `LoadInputScript` installs the script as the pad override (chronicle:port/src/main.cpp:240-262), `WindowInit`, `RendererInit` and `AudioOutputStart` run (headless audio is off with `DC_AUDIO=off`), then `RunGame`.
4. `RunGame` (chronicle:port/src/gameloop.cpp:791) does the retail `main` steps with the hardware removed. With a jump set, it skips the 60-tick warm-up (`kWarmUpTicks`) and the language select, and calls `ApplyJump`.
5. In the main loop, each iteration runs `ModeInit`, `check_now_loading` (the loading screen, uncounted), then frames of `ModeLoop`. After each frame: `GiveOnArrival`, pad update, `MGEndFrame`, `++g_frames`, the debug-toggle check and the developer-menu chord check (chronicle:port/src/gameloop.cpp:938-958).
6. `FrameBoundaryStop` ends the run when `--frames` is spent or a stop is requested, at a frame boundary. Then `main` writes the screenshot and the present statistics (`DC_PRESENT_STATS=1`), and shuts down (chronicle:port/src/main.cpp:440-470).

### Jump and transition code

- `MapJump(map, event)` (retail, chronicle:ps2/src/main.cpp:1053) only sets `NextMapNo` and `StartEventNo`. `GameFollowMapJump` (chronicle:port/src/gameloop.cpp:409-445) turns `NextMapNo` into a mode: below 200 is `EDIT`, 200-299 `DUNGEON` (with `LocalMapNo = n - 200`), 400 `OPENING`, 800 title, 801 attract movie, and 1000 the ending save.
- `GameApplyLoopResult` (chronicle:port/src/gameloop.cpp:447-545) decides the next mode from each mode's loop result. Its unit test is `IntegrationGameloop.LoopResults`.
- Retail's `MenuLoop` writes `main_select_menu_no`, `LocalMapNo` and `mode` directly and returns 1; `DeveloperMenuKeepsTheModeItPicked` covers that path.

### Give on arrival

`GiveOnArrival` (chronicle:port/src/gameloop.cpp:127-141) keeps a static `last_mode` and fires when `mode` changes to `EDIT` or `DUNGEON`. Inference from the code: a town-to-town map jump that stays in `EDIT` does not re-trigger it, and the first frame of a `--jump` run does (the static starts at -1). `--give` therefore works with `--jump edit:N`.

### Screenshot and pixel checks

- `--screenshot` reads `kPreviousFrame` through `gfx::ReadbackTexture` after the run (chronicle:port/src/gameloop.cpp:781-783).
- `--screenshot-fps` with `--show-fps` writes the counter-over-image instead (chronicle:port/src/gameloop.cpp:785-789).
- `--display-per-tick N` renders N interpolated display frames per tick, offscreen only (chronicle:docs/PC.md "Command line" table).

### Input replay

The script is consumed by `InputScriptApply(GameFrameCount())` in the pump hook (chronicle:port/src/main.cpp:221-238), so its frame numbers are main-loop frames, the same counter as `--frames`. Frame 0 covers the warm-up and the loading screens before the first frame (chronicle:docs/PC.md "Scripted input"). The doc's example reaches the title menu at about frame 560.

### Verification harness

- Unit tests (`*_test.cpp`) do not run the game. `darkcloud_tests` links the port and the game, so a test can call game functions directly, as `integration_gameloop_test.cpp` does.
- Tests that need data read `DC_DATA`; the default CI run unsets it (chronicle:.github/workflows/pc.yml, Linux "Test" step).
- `paths_xdg_test.cpp` runs the real `darkcloud --headless --frames 1` as a subprocess (`std::system`, chronicle:port/src/tests/paths_xdg_test.cpp:62-70) and checks the status 3 message.

### Debug-only telemetry env vars

| Variable | What it shows | Where |
|---|---|---|
| `DC_PRESENT_STATS=1` | draws per tick, render time, display frames | chronicle:port/src/main.cpp:330 |
| `DC_SPRITE_TRACE=1` | each distinct sprite texture and rect, once | chronicle:port/src/gameutil_sprite.cpp:43-45; chronicle:port/src/snd.cpp:63 |
| `DC_TEXTURE_DUMP=<dir>` | every texture the game enters, as PNG | chronicle:port/src/texture.cpp:106-109 |
| `DC_LOCALIZE_TRACE=1` | each message file loaded, named as its JSON key | chronicle:port/src/localize.cpp:153-156 |
| `DC_AUDIO_TRACE=1`, `DC_AUDIO_WAV=<path>` | sound calls; WAV capture of the mixer per tick | chronicle:docs/PC.md "Audio" |
| `VULKAN_VALIDATION` / `DC_VULKAN_VALIDATION` | Khronos validation layer | chronicle:port/src/main.cpp:431; chronicle:docs/PC.md "Building and running" |

## Ixion hooks

These are integration points in Chronicle's code. Ixion would add to them, not replace them.

1. **Jump spec (`GameSetJump`, `ApplyJump`).** `port/src/gameloop.cpp:571` and `:353`. Add a spec form for a second-world destination, or a `world:map` syntax, with its own `Jump` mode. Add a `GameSetJump` case test next to `GiveListParses`.
2. **Single map-transition sink (`GameFollowMapJump`).** `port/src/gameloop.cpp:409`. Every ordinary transition passes through `NextMapNo`. A cross-world hop could be detected here, before the mode is set. Inference: because `MapJump` (retail, `ps2/src/main.cpp:1053`) is compiled unchanged from `ps2/src`, a `PORT_OVERRIDE` definition in `port/src` with the same signature is the way to intercept it. `docs/PC.md` ("How port/src takes precedence") describes the override rules; the build fails if an override names nothing in `ps2/src`.
3. **Folder naming (`EditInit`).** `ps2/src/editloop.cpp:703-745`, with `gedit/interior` at `:783`. This is where a `MapNo` becomes a data folder. Second-world maps would need their own id range and folder mapping here (or an override).
4. **Visited flags (`VisitMap`).** `ps2/src/editloop.cpp:711`. A cross-world visit would call the same bit set, or a separate one, depending on what the design needs.
5. **Arrival gifts (`GiveOnArrival`).** `port/src/gameloop.cpp:127-141`. The place to sync party and inventory on arrival. Caveat: detection is by mode change, not by map change, so a same-mode change (`EDIT` to `EDIT`) needs its own trigger.
6. **Developer menu (`MenuLoop`).** `ps2/src/main.cpp:1087`, with the `map_no[]` table at `:1099` and the event table at `:1258`. This is a ready picker for towns, sub maps, interiors, dungeons and events, reachable with Start+Select in debug mode (`port/src/gameloop.cpp:623`). A second-world picker can copy its row structure.
7. **Event script jumps (`_MAP_JUMP`).** `ps2/src/editloop3.cpp:3602`. Story-driven cross-world hops go through this opcode. Its map number is 1-based.
8. **Dungeon loader.** `ps2/src/dun/gameloop.cpp:9578` (`MapJump(selectMapNo + 200)`) and the port's `LoaderLoop` at `port/src/dun/gameloop.cpp:793`.
9. **Headless options.** `port/src/main.cpp:51-104` (Options and Usage) and `Run` at `:367`. A new option (for example `--world`) follows the same parse-then-check pattern and reuses the exit codes in `port/src/exitcodes.hpp`.
10. **Test pattern.** `port/src/tests/integration_gameloop_test.cpp` (`Reset`, `Jump`, `MapJumpTransitions`, `LoopResults`). New `*_test.cpp` files are picked up by the CONFIGURE_DEPENDS glob in `port/src/tests/CMakeLists.txt`, so a new file needs no CMake edit, only a reconfigure. Each case is its own process under ctest.
11. **Pixel checks.** Kazarov `GfxFixture` (`port/tests/gfx_fixture.hpp`) gives an offscreen renderer with validation on. `gfx::WritePng` (used by `area_card_test.cpp:41`) writes the result for a diff against a reference image.
12. **Deterministic repro.** `--input` scripts for menu paths (developer menu, title, loader). Use `key:grave` to enable debug mode from a script.
13. **Asset tracing.** `DC_LOCALIZE_TRACE=1` and `DC_TEXTURE_DUMP` prove which files and textures a town or dungeon loaded. Useful when a cross-world asset is missing and the screen goes wrong without an assert.

### Fast recipes (untested sketches)

Replace `<data>` and `<save>` with local directories. Use a scratch `--save`, since the run writes saves and `config.json`.

- Town with items, headless, one frame budget, screenshot:
  `DC_AUDIO=off darkcloud --headless --jump edit:0 --give 210,211 --fast-load --frames 120 --screenshot town.png --data <data> --save <save>`
- Dungeon floor select:
  `DC_AUDIO=off darkcloud --headless --jump dungeon:0 --fast-load --frames 60 --screenshot dun.png --data <data> --save <save>`
  (PC.md reports the floor select after about five seconds on lavapipe.)
- Dungeon floor 1 entered: the same run with an `--input` script that presses Cross in the loader after the first 60 frames. The frame number needs measuring on the target machine; no value is verified here.

## Risks and blockers

- **Nothing here is verified.** No build or run was done, per the brief. The commands and frame counts are guesses until run on the target.
- **`--jump` changes gameplay.** It forces `DebugMode` on, which unlocks debug branches across ps2/src (fishing cast, editor overlays, shop and menu shortcuts). Verification screenshots of a player-facing prototype may show debug-only behaviour.
- **`edit:N` is not range-checked.** A bad map number reaches `LoadFile` and exits 4 (assert), not 2.
- **Stale build.** The 2026-10-07 Windows binary lacks `--give`. Rebuild before relying on it.
- **Doc claims without code.** `AudioRealData` and `audio_real_title_*` are described in `docs/PC.md` but absent from both trees; the CI comment about real-data skips points at nothing. Do not rely on them as coverage.
- **One game per process.** All state is retail-named globals (`MapNo`, `mode`, `SaveData`, `DebugMode`). Two games in one executable would collide on these names; the ctest per-process isolation does not help a merged runtime. This is outside this document's scope but bears directly on the jump design.
- **Windows headless is a hidden window.** `docs/WINDOWS.md` says a headless Vulkan window is a hidden Win32 window and that offscreen works without a surface. The Windows CI job runs no darkcloud, so Windows headless behaviour is checked only by hand.
- **Frame-accurate input.** Loader and menu presses are keyed to main-loop frames, and loading holds are not counted. A script that works with `--fast-load` may not with normal timing, and the reverse.
- **Pointer truncation audit.** CI runs `scripts/port/truncations.py --check` on Linux. Any new Ixion code that casts pointers to 32-bit integers fails that check unless widened.

## Open questions

- Which `--frames` value gets a town's NPCs and parts onto the screen for `edit:0`? Needs a run.
- Does `--jump edit:N` for a sub map absent from the extracted tree exit 4 at `LoadFile`, as expected, or does a fallback path exist? (Inference: yes, exit 4.)
- Does `--give` fire for a town-to-town transition within `EDIT` through a door or event (inference: no)? Check with a test that counts gifts across a jump.
- What frame does the loader's floor-1 entry need, with `--fast-load` on and off?
- Does the 2026-10-07 build have `DC_JUMP`/`DC_FAST_LOAD` env handling that matches current master? Only the flag strings were checked.
- Is the `ps2/src` debug-mode code path for the fishing cast (`ps2/src/ebattle.cpp:2490`) gated on `DebugMode` alone, and does a `--jump` run therefore change fishing? Confirm by reading the enclosing function before relying on it.
- Should the PC.md and CI-comment drift about `AudioRealData` be fixed upstream, or is that coverage intended and simply not yet merged? Only the owner can say.
