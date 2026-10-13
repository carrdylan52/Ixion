# ChronicleTwo debug and test facilities

## What this covers

The debug and test surface of ChronicleTwo (DC2, Dark Chronicle) as of the `ixion` branch (HEAD 8d7d7fc8), with the Kazarov submodule at 3dc38ce:

- the boot-time debug switch (`game.debug_mode`) and the `--jump`, `--give` and `--fast-load` test hooks (`port/src/debug_mode.cpp`, `port/src/test_hooks.cpp`);
- the retail debug surfaces that those hooks unlock: the Start+Select developer menu, the pad-1 chord, the pause and frame-step controls, the town and dungeon debug pages, and the six `*viewlp` debug viewers;
- scripted input (`--input`), frame-bounded exits and screenshots, and the retail pad record/play capture;
- the gtest and CTest layout, the data-free and real-data CTest fixtures, and the three CI jobs;
- the cheapest headless boot into a chosen map, and what it costs.

Basis: read-only review of the repository and its pinned Kazarov. Nothing was built or run. Retail citations are `ps2/src` file:line; PC citations are `port/src` or Kazarov (`kazarov:` is `tools/kazarov` at 3dc38ce). Statements marked "inference" are read from code, not observed in a run.

## Key facts

- Three separate switches gate debug behaviour. `game.debug_mode` in `config.json` (default false, `chronicletwo:port/src/platform/config.hpp:22`, parsed at `chronicletwo:port/src/platform/config.cpp:201`). `GameDebugEnabled()` is true when that flag is set or any `--jump` is present (`chronicletwo:port/src/test_hooks.cpp:156`). Retail's runtime gate is `DebugFlag`, which the pad-2 Circle toggle and the pad-1 chord flip (`chronicletwo:ps2/src/mainloop.cpp:674-678`, `chronicletwo:port/src/mainloop.cpp:328`).
- `DebugModeBoot` runs once at boot. It sets `MasterDebugCode` and `MasterDebugModeOn` when debug is enabled, which stands in for a developer save (`chronicletwo:port/src/debug_mode.cpp:7-13`, called at `chronicletwo:port/src/mainloop.cpp:119`). The other gate, `GameDebugEnabled()`, reads `ConfigGet()` on every call, so a run-time config change is seen immediately (inference: no run-time path changes `debug_mode` today).
- `--jump` grammar, parsed by `GameParseJump` (`chronicletwo:port/src/test_hooks.cpp:78-122`):
  - `town[:N]` and `edit[:N]`, map N 0-188, default 10;
  - `dungeon[:n[:floor]]`, n 0-6, floor 1-99, default floor 1;
  - `event:<id>`, id above 0;
  - `title`, `opening`, `menu`, with no argument.
- Dungeon floors are checked at parse time against `CSaveDataDungeon::GetFloorInfoPtr` (`chronicletwo:port/src/test_hooks.cpp:88-101`). The unit test `TestHooks.JumpAcceptsModesAndBounds` runs this without a data fixture (`chronicletwo:port/src/tests/test_hooks_test.cpp:17-38`), so the floor table is code-resident (inference from the test having no fixture).
- Town maps are checked only after data loads. `GamePrepareJump` calls `GetMapType(jump.map) < 0` (`chronicletwo:port/src/test_hooks.cpp:184-186`). The map-name table is read from the data at runtime (`chronicletwo:ps2/src/mapselect.cpp:205-215`), so the set of valid town numbers comes from the extracted data, not from the binary.
- A failed target is a usage error. `BadTarget` prints a message and exits with status 2 (`chronicletwo:port/src/test_hooks.cpp:36-39`, used at lines 186 and 215). The message says the target is absent from the game tables; it is also the path taken when the event table file cannot be opened, because `ResolveEvent` returns false for a missing file (`chronicletwo:port/src/test_hooks.cpp:41-75`).
- Preset state per jump (`chronicletwo:port/src/test_hooks.cpp:162-219`):
  - every jump runs `InitSaveData()`, sets `DebugFlag = 1` (line 175) and sets `PortGameBootInit = 1` (line 176), which the retail title reads to skip its memory-card boot path (`chronicletwo:ps2/src/title.cpp:665-669`, `812-825`) (unverified: the retail source reads its static `GameBootInit` at `chronicletwo:ps2/src/title.cpp:180`, and no ps2/ source declares the `Title_GameBootInit` label that the alias depends on);
  - town loads `dbg/pb.cfg` and uses event 100 (lines 187-192);
  - dungeon loads `dbg/cap1.cfg` for every dungeon number and uses the requested floor (lines 193-198);
  - `opening` forces dungeon 0, floor 20, event 1010 and makes Monica the only party member (lines 199-211);
  - `event:<id>` resolves a row of `event/view_pal.txt` (lines 212-216).
- `event/view_pal.txt` columns are name, dungeon, floor, event id (`chronicletwo:port/src/test_hooks.cpp:41-75`). In the extracted data, the row with event 26010 has dungeon 2 and floor 12, so it resolves to dungeon index 1, floor 12 (inference from `ResolveEvent`, `dungeon - 1`). The row for event 10010 has an empty dungeon column, so it resolves to a town by name through `SearchMapNo` (`chronicletwo:port/src/test_hooks.cpp:62-71`).
- Language is forced to English on any jump (`chronicletwo:port/src/mainloop.cpp:99`), and the logo fade is skipped (`chronicletwo:port/src/mainloop.cpp:100-102`). A jumped run and an ordinary boot therefore differ in text.
- `--give` is applied on every town or dungeon arrival, after `LoopInit` (`chronicletwo:port/src/test_hooks.cpp:221-235`, called at `chronicletwo:port/src/mainloop.cpp:259-260`). Items already held are skipped.
- `--fast-load` changes only the loading progress bar step (`chronicletwo:port/src/nowload.cpp:9`).
- Options are parsed in `ParseOptions` (`chronicletwo:port/src/main.cpp:123-170`). Usage text is at `chronicletwo:port/src/main.cpp:66-92`. `--jump`, `--give` and `--fast-load` also read `DC2_JUMP`, `DC2_GIVE` and `DC2_FAST_LOAD`, with the command line winning (`chronicletwo:port/src/main.cpp:253-262`).
- Exit statuses (`chronicletwo:docs/PC.md:302-310`, `chronicletwo:port/src/exitcodes.hpp`): 0 normal or frame limit reached; 1 SDL, window or renderer error, or screenshot write failure; 2 usage error, bad `--input`, bad `--jump` or `--give` target; 3 no extracted data when headless; 4 game assertion.
- `--frames N` exits inside `mgEndFrame` once the frame count reaches N, after writing the screenshot and logging `mglib: frame N written to <path>` (`chronicletwo:port/src/mglib.cpp:1324-1344`). A failed write exits 1 (line 1344). If the main loop leaves its mode table first, `MainLoop` breaks out (`chronicletwo:port/src/mainloop.cpp:214-215`) and the process returns 0 with no screenshot (`chronicletwo:port/src/main.cpp:317-320`). The frame count includes boot, logo and title frames, so a jump run has fewer frames than a retail one.
- Input scripts (`kazarov:include/platform/input_script.hpp:1-20`, parser `kazarov:src/cpp/platform/input_script.cpp:108` and `167`):
  - one line per change: `<frame> [pad1|pad2] [button ...] [key:<name> ...] [mouseN] [mouse:dx,dy] [wheel:n] [lx ly rx ry]`;
  - a line holds until the next line for that pad;
  - keys and mouse drive pad 1 only (`input_script.cpp:` `ParseLine` rejects them on pad 2);
  - frames must not decrease per pad (`InputScriptParse`);
  - pad 1 is released before its first line; pad 2 stays on its device unless a line names it.
- Script frames are main-loop iterations. `InputScriptApply(mgPortFrameCount())` runs in the pump on every tick (`chronicletwo:port/src/main.cpp:221`), and `mgPortFrameCount()` increments once per `mgEndFrame` (`chronicletwo:port/src/mglib.cpp:1324`).
- Pause and frame step (`chronicletwo:port/src/mainloop.cpp:356-385`). Pad-1 L2+Select pauses only when debug is enabled (`chronicletwo:port/src/test_hooks.cpp:252-258`). Pad-2 Select always pauses (`chronicletwo:ps2/src/mainloop.cpp:724-727`). While paused, modified Start stores a frame image (`chronicletwo:port/src/mainloop.cpp:376`), and Right steps one frame.
- Frame images are written to the save root as `i%05d.png`, from a counter that starts at 0 each process (`chronicletwo:port/src/mglib.cpp:83`, `1413-1428`). A second run in the same save root overwrites the first run's images.
- Developer menu on PC: Start+Select on pad 1, read from host input so it works past the game's pad lock (`chronicletwo:port/src/test_hooks.cpp:237-250`). It is edge-triggered and ignored in the menu itself. The port request runs each mode's cleanup before entering the menu (`chronicletwo:port/src/mainloop.cpp:265-283`). The retail title check is `chronicletwo:ps2/src/title.cpp:848`, which also needs `DebugFlag`.
- Retail debug start menu, rows from `DebugMenuRow` (`chronicletwo:ps2/include/mainloop.hpp:104-114`) and labels at `chronicletwo:ps2/src/mainloop.cpp:876-878`:
  - row 0 "game start" opens the event select (`mainloop.cpp:1043-1044`);
  - rows 1 to 8 are "map", "dungeon", "title", "chrview", "texview", "mapview", "sound view" and "movie view". Each goes to `NextLoop(select, arg)` with the mode number of the same value (`mainloop.cpp:1077`). Row 1 opens the map selector when its argument is below zero;
  - row 9 "Language" calls `LanguageChange` (`mainloop.cpp:1046`);
  - row 10 "Item" calls `DebugGetItem` (`mainloop.cpp:1050`);
  - row 11 "Save Data" opens the save editor (`mainloop.cpp:1053`);
  - row 12 "Load cfg" runs `InitSaveData` then `LoadGameConfig("dbg/game%d.cfg")` (`mainloop.cpp:1057`);
  - row 13 "Convert Save Data" goes to `LOOP_SV_CONV_VIEW` (`mainloop.cpp:1071`).
  - Select in the menu cycles the capture mode (`mainloop.cpp:1015-1020`).
- Event-select rows load configs by name: Palm Brinks `pb.cfg` (`chronicletwo:ps2/src/mainloop.cpp:1389`), chapters `cap%d.cfg` and `db_cap%d.cfg` (lines 1360-1362), sub-games `sg%d.cfg` (line 1385), georama `geo.cfg` (line 1402). The row enum is `DebugEventRow` (`chronicletwo:ps2/include/mainloop.hpp:122-135`).
- Loop-mode numbers 4 to 9 are the viewers and the save converter (`chronicletwo:ps2/include/mainloop.hpp:36-41`). The dispatch tables are at `chronicletwo:ps2/src/mainloop.cpp:100-134`.
- Viewer status, read from the bodies:
  - `charaviewlp` (`chronicletwo:ps2/src/charaviewlp.cpp:1-12`): empty init and exit; the loop returns true at once, so the row leaves to the menu;
  - `texviewlp` (`chronicletwo:ps2/src/texviewlp.cpp:1-12`), `mapviewlp` (`chronicletwo:ps2/src/mapviewlp.cpp:1-12`) and `sndviewlp` (`chronicletwo:ps2/src/sndviewlp.cpp:1-11`): empty; the loop returns 1 at once;
  - `movieviewlp` (`chronicletwo:ps2/src/movieviewlp.cpp:157-330`): real. Init reads `mv.cfg` through the script interpreter (`movieviewlp.cpp:157-236`). Start or Cross leaves (lines 251-252); Circle plays the selected movie through the movie decoder (lines 275-330);
  - `convviewlp` (`chronicletwo:ps2/src/convviewlp.cpp:183-240`, `326-513`): real and destructive. Left and Right pick a card slot; Cross starts the conversion. `SaveDataConvertLoop` renames card directories with `sceMcRename` (lines 477-497). Nothing converts until Cross is pressed on the select screen.
- The card calls land in a host directory. Each memory card is a directory under the save root (`mc0`, `mc1`), and `sceMcRename` works inside it (`kazarov:src/cpp/sce/libmc.cpp:131`, `579-600`). A fresh save root therefore contains the conversion.
- The town debug page is also a teleport. R3 opens the edit debug menu under `DebugFlag` (`chronicletwo:ps2/src/editloop.cpp:1720-1731`). Its map page has a "Map Jump" row; Circle sets `jump_map_no` (`chronicletwo:ps2/src/editdebug.cpp:426-430`, value table at line 139). The next frame calls `EditMapJump` and then `RunEvent(100)` (`chronicletwo:ps2/src/editloop.cpp:1405-1411`). Every debug map jump therefore arrives at event 100.
- `EditMapJump` (`chronicletwo:ps2/src/editloop.cpp:2713-2785`) calls `MapJump` (`chronicletwo:ps2/src/mapjump.cpp:191`). Map numbers 11 to 14 are redirected to 10 with a sub-map (`chronicletwo:ps2/src/editloop.cpp:2736-2738`). Town entry itself passes its number through `GetMapName` and `SearchMapNo` (`chronicletwo:ps2/src/editloop.cpp:877`).
- Retail record and play is a separate mechanism. `PortCaptureMode` is shared with retail's `CaptureMode` (`chronicletwo:port/src/mainloop_port.hpp:14`). Recording starts at mode entry and writes `key_cap.bin` on mode exit, six bytes per frame, overwriting any previous file (`chronicletwo:port/src/gamepad.cpp:113`, `156-170`; `chronicletwo:port/src/mainloop.cpp:400`). Play loads the file at each mode start (`chronicletwo:port/src/mainloop.cpp:227-230`). The capture mode resets when a non-menu mode exits (`chronicletwo:port/src/mainloop.cpp:403`).
- `docs/port/records.md` is not a replay facility. It is the inventory of struct layouts that are read from disc, pack or card files, checked by `scripts/port/records.py` (`chronicletwo:docs/port/records.md:1-27`; `chronicletwo:port/src/tests/cmake/records.cmake:1-12`). "Record" there means a struct instance.
- Headless timing (`chronicletwo:docs/port/headless-replays.md`): `--headless` uses an unbounded clock (`chronicletwo:port/src/main.cpp:305`) and advances the mixer from the same ticks. Captures are comparable only with the same binary, script, frame limit, config and a fresh save root. Debug-event fixtures need `game.debug_mode=true` in their own config.
- Input-script corpus: 149 files in `tools/input`. 61 carry the header `Requires game.debug_mode=true in the replay save root config.json` and 88 do not (count by grep). The `area-*-sweep` scripts drive the retail debug event select from a title boot (for example `tools/input/area-event110-sweep.input`), which is slower than a jump.
- Test suite: 1,077 cases (805 `TEST`, 267 `TEST_F`, 5 `TEST_P`) in 123 `*_test.cpp` files under `port/src/tests` (static count). Each case runs in its own process because game state is global (`chronicletwo:port/src/tests/CMakeLists.txt:1-4`). The test binary links the port and the game (`chronicletwo:port/src/tests/CMakeLists.txt:20-34`).
- Test labels and timeouts. Default case timeout 5 s (`CT_TEST_TIMEOUT`); GPU-slow cases get at least 30 s (`chronicletwo:port/src/tests/CMakeLists.txt:42-46`). Device-bound cases carry the label `gpu`, with CPU-only exceptions listed in `CT_CPU_TESTS` (lines 48-52). `scripts/port/gpu_test_labels.py` fails configure if a new test creates a device without the label.
- Data-free CTest fixtures that boot the binary (all labelled `gpu`):
  - `Smoke.HeadlessFramesScreenshot` runs `--headless --offscreen --frames 3 --screenshot` on an empty publisher fixture and checks exit 0, the `dataread: indexed` and `mglib: frame 3 written to` lines, and the PNG signature (`chronicletwo:port/src/tests/CMakeLists.txt:151-170`; `chronicletwo:port/src/tests/cmake/empty_data.cmake`);
  - `PresentIdentity.DisplayPerTickScreenshot` checks that `--display-per-tick 4` gives the same image (`chronicletwo:port/src/tests/cmake/present-core.cmake:4-7`, `present_identity.cmake`);
  - `Screenshot.OneFrameCommandLine` checks display frames at one tick (`chronicletwo:port/src/tests/cmake/screenshot_one_frame.cmake:27-32`).
- Real-data CTest fixtures, which exit 77 (skip) without data:
  - `Matrix.Title` and `Matrix.Costume` run `sweep-title` at frame 2500 and `sweep-costume` at frame 4800 through `scripts/port/matrix.py` (`chronicletwo:port/src/tests/cmake/matrix.cmake:1-20`); the runner skips with 77 when `DC2_DATA` is unset (`chronicletwo:scripts/port/matrix.py:118`, `409`);
  - `PcSettingsReplay.{pad,mouse,zoom}` boot with `--jump town:10 --fast-load`, use their own save root, and check the saved `config.json` after the run (`chronicletwo:port/src/tests/cmake/pc_settings.cmake:1-11`; `chronicletwo:scripts/port/pc_settings_replay.py:19-60`).
  - Gtest cases that read `DC2_DATA` call `GTEST_SKIP` (for example `chronicletwo:port/src/tests/mglib_present_test.cpp:1304`, `dataread_test.cpp:490`). Gtest reports a skip as a pass, so ctest does too (inference from gtest's exit code).
- Python-side CTest entries need no data: `Matrix.Runner`, `NativeUnitFixups`, `NativeRetailBridges` (`matrix.cmake:22-35`), `PalettePaths.Check` (`chronicletwo:port/src/tests/CMakeLists.txt:15-17`), `Records.Check` and `Truncations.Check` (non-Windows only; exit 77 without the clang bindings; `cmake/records.cmake`, `cmake/uptr.cmake`).
- CI, `chronicletwo:.github/workflows/pc.yml`:
  - Linux, `ubuntu-26.04`: configures `linux-x64` with `-DCT_TEST_TIMEOUT=60` (lavapipe renders on the CPU, as the comment above the Configure step says), checks that the clang bindings import, runs `ctest -j4` with no label filter (line 33), then the native gate and a PIE check;
  - macOS, `macos-26`: full `ctest` minus `MACOS_GPU_REPORT_ONLY` (lines 90-91), and a report-only run of that list with `continue-on-error` (lines 93-95);
  - Windows, `windows-2025`: `ctest ... -LE gpu` (line 145). The hosted runner has no Vulkan device.
- No CI workflow sets `DC2_DATA`, `DC2_SAVE` or a disc path (grep of `.github/workflows`). The real-data tests and the jump replays therefore never run in CI.
- `progress.yml` runs only on master with a private checkout, builds the decomp objdiff report and posts progress. It does not run the game (`chronicletwo:.github/workflows/progress.yml:26-80`).

## How it works

### Boot path for a jump

1. `Run` (`chronicletwo:port/src/main.cpp:250`) sets the identity, parses options and takes `--jump` or `DC2_JUMP` into `GameSetJump`. A malformed jump string is a usage error (lines 257-260).
2. `ConfigLoad` reads `config.json` from the save root (line 271). `FirstRunRequireData` checks for `data.json` beside the data directory and `port_data/manifest.json`. Headless with no data exits 3 (`chronicletwo:port/src/platform/firstrun.cpp:22-67`; the check is at lines 27-28).
3. The renderer starts, with the offscreen surface when `--offscreen` is set (`main.cpp:276-296`). `InputScriptInstall` installs the script (line 281). The clock is unbounded when headless (line 305). `InitCDFile` indexes the data (line 312).
4. `--frames` and `--screenshot` are armed (`main.cpp:313-316`), then `MainLoop` runs (`chronicletwo:port/src/mainloop.cpp`).
5. `MainLoop` sets English, sets `DebugModeBoot`, runs `GamePrepareJump` (`mainloop.cpp:99`, `119`, `202`). Each mode entry runs `mgPortCutInterpolation`, `LoopInit`, then `GameGiveOnArrival` (`mainloop.cpp:258-260`).
6. Each frame calls `LoopMain`, then the pad and debug checks (`mainloop.cpp:326-330`), then `mgEndFrame`, which advances `mgPortFrameCount()` and may exit (`mglib.cpp:1324`).

### Cheapest headless boot into a map

Command template (placeholders in angle brackets; a Windows build behaves the same):

```
darkchronicle --data <dc2-root>/data --save <empty-dir> --headless --offscreen \
  --jump town:<map> --fast-load --frames <N> --screenshot <out>.png
```

- `--data` takes the `data` directory. Its siblings `port_data/` and `data.json` must be present (`firstrun.cpp:27-28`). The extracted layout has these three entries side by side.
- `--save` must be empty or fresh. It receives `config.json` (absent means defaults), `i%05d.png` pause captures, `key_cap.bin` recordings and the `mc0`/`mc1` card directories once a card call is made (inference).
- No `--input` is needed for a static checkpoint. Add `--input tools/input/<file>.input` to drive the scene. Add `--screenshot-display N` for interpolated frames and `--window WxH` for the layout.
- Needs a Vulkan device. The renderer is initialised unconditionally (`main.cpp:295`), and `--offscreen` only changes the surface (inference from the call site). The CI labels agree: the device-bound cases are excluded on the Windows runner (inference from the labels and the workflow).
- Needs real data. The town map check depends on the extracted tables (`test_hooks.cpp:184-186`). On the publisher-only fixture a `town:` jump should exit 2 (inference from the code, not run).
- Verification: exit status 0; stderr contains `mglib: frame <N> written to`, because a frame limit that the loop never reaches exits 0 silently; the PNG begins with the signature `89 50 4E 47 0D 0A 1A 0A`. Status 2 means a bad target or script. Retail `printf` lines in stdout are noise.
- Map identity is not logged. No positive log line names the loaded town (inference from the `printf` sites; only the `not found map` failure line names a number). Check the screenshot, or check the town name map by number against the data. The `not found map` message (`chronicletwo:ps2/src/editloop.cpp:2746`) cannot fire, because `GetMapName` never returns NULL (`chronicletwo:ps2/src/mapselect.cpp:367-375`).
- The documented frame counts (`town:10` controllable by frame 120; `dungeon:0:1` by 250; `title`, `opening` and `menu` by 250; `event:26010` in the boss arena by 250; `chronicletwo:docs/DEBUG.md`, "Jump replays") are the author's measurements and are not checked by CI.

### Scripted play and checkpoints

- Use the `jump-*.input` files as templates. A button press is a line with the button, then a release line one or six frames later (for example `tools/input/jump-town-menu-unknown.input`).
- Start+Select from a jump opens the developer menu through the host chord. `jump-*-menu-*.input` files navigate it. For example, `tools/input/area-town-entry.input` opens event select with a circle at frame 100, moves down four rows to Palm Brinks, and confirms.
- Pad 2 Select pauses. A modified Start while paused writes `i%05d.png` to the save root.
- For long walkthroughs, retail record writes `key_cap.bin` on mode exit and replays it on mode entry. The file belongs to the save root and is overwritten by each recording.

### Developer menu and retail debug

- The menu opens from the title (`chronicletwo:ps2/src/title.cpp:848`, needs `DebugFlag`), or from any non-menu mode on PC (`chronicletwo:port/src/test_hooks.cpp:237-250`; `mainloop.cpp:265-283`).
- Modes that hold state get cleanup first: `PreExitLoop` in town, `DngStatus.mode = DNG_STATUS_EXIT` and a Start+Select pass through `LoopDungeonMain` in dungeon, and the title's exit branch (`mainloop.cpp:280-300`). The menu's destination is chosen after that cleanup.
- Destructive rows reachable with the menu open: Save Data (row 11), Load cfg (row 12, which also resets the save with `InitSaveData`), Convert (row 13). All write under the save root only.

### Input and replay

- `--input` loads at start-up (`main.cpp:157-160`, `264-270`), and the pump applies the script every tick (`main.cpp:221`). The pad override is set through `InputSetOverride`, and keys and mouse go through `InputSetScriptedDevices` (`kazarov:src/cpp/platform/input_script.cpp:250-261`; `kazarov:src/cpp/platform/input.cpp:1438-1443`).
- Keyboard defaults in Kazarov's action table (`kazarov:src/cpp/platform/input.cpp:51-84`): Start is Return, Select is Backspace or C, L1 Z, L2 Q, R1 F or X, R2 R, R3 B or Mouse3. Circle is Mouse2, and the keyboard feeds pad 1 only.
- `fps_toggle` is the only host action with a reader in `port/src/` (`port/src/present.cpp:46`). `developer_menu` and `debug_menu` are bound (`kazarov:src/cpp/platform/input.cpp:81-82`) with no reader in `port/src` or Kazarov. `port/src/options/rows.cpp` hides `developer_menu` and shows `debug_menu` as "Debug menu" (lines 103, 135).

### Test layers

- Unit: gtest cases with no device and no data, for example the jump parser (`port/src/tests/test_hooks_test.cpp:17-38`), `--give` lists (lines 40-48), pad routing (lines 50-103), the developer-menu edge (lines 104-150), and the chord and boot (`port/src/tests/debug_mode_test.cpp`). `DebugFixture` isolates a temporary save root and sets `debug_mode` per case (`port/src/tests/debug_fixture.hpp:1-30`).
- Device: gtest cases that create a renderer or device, labelled `gpu` (for example `MglibPresent.*`, `GfxGpu*`, `MgVisual.*`; `port/src/tests/CMakeLists.txt:54-87`).
- Generated-script CTest: `Smoke`, `PresentIdentity`, `Screenshot.OneFrameCommandLine`, the four `Records`/`Truncations` pointer checks, and the Python runners.
- Real data: `Matrix.*`, `PcSettingsReplay.*` and the `DC2_DATA` gtest cases. These need an extracted data tree and are not in CI.

## Ixion hooks

- **Destination lookup.** `GameParseJump` and `ResolveEvent` (`chronicletwo:port/src/test_hooks.cpp:41-122`) are a ready table of destinations keyed by name or event id. An Ixion mode in the same style (for example `ixion:<name>`) would resolve to an existing town map or dungeon floor and event, reading the same `event/view_pal.txt`. The retail tables stay as they are.
- **Arrival state.** `GameGiveOnArrival` (`chronicletwo:port/src/test_hooks.cpp:221-235`), called after `LoopInit` at `chronicletwo:port/src/mainloop.cpp:260`, is the per-arrival seam. It already grants items on every arrival. Per-visit Ixion state (for example a cast or a time-travel marker) could hang here. Inference: it must not depend on the init order of the mode.
- **Mode-change seam.** `mgPortCutInterpolation()` and `LoopInit[PortLoopNo]` (`chronicletwo:port/src/mainloop.cpp:258-259`) are the single entry for every mode change. A cross-world transition would be intercepted here, and the request side is `NextLoop` (`chronicletwo:ps2/src/mainloop.cpp:349`).
- **Teleport seam.** `EditMapJump` (`chronicletwo:ps2/src/editloop.cpp:2713`) and `MapJump` (`chronicletwo:ps2/src/mapjump.cpp:191`) are the in-session route to another town. The debug map page (`chronicletwo:ps2/src/editdebug.cpp:426-430`) and the call site (`chronicletwo:ps2/src/editloop.cpp:1405-1411`) show the calling pattern. Note that the retail route always runs event 100 on arrival.
- **Cast seeding.** The `opening` branch (`chronicletwo:port/src/test_hooks.cpp:199-211`) changes party membership with `LeavePartyMember`, `JoinPartyMember`, `EnableCharaChange` and `SetActiveChrNo`. This is the template for "play any character". The DC1 character IDs would need mapping (inference).
- **Headless checkpoints.** One `tools/input/<name>.input` per Ixion checkpoint, run with `--jump`, `--frames` and `--screenshot`, follows the "Jump replays" pattern in `chronicletwo:docs/DEBUG.md`. A runner modelled on `chronicletwo:scripts/port/pc_settings_replay.py` could assert the saved state, not only pixels, by reading the files it wrote under the save root.
- **Coverage matrix.** `scripts/port/matrix.py` already takes `--scene`, `--frame` and `--input` (`chronicletwo:scripts/port/matrix.py:75`). A list of town numbers with a `--jump` each would give a screenshot per town.
- **Unit tests with no data.** Add `ixion:` cases to `chronicletwo:port/src/tests/test_hooks_test.cpp` in the style of `JumpAcceptsModesAndBounds` (lines 17-38). These run on all three CI platforms.
- **Gate.** `GameDebugEnabled` (`chronicletwo:port/src/test_hooks.cpp:156`) and `DebugModeBoot` (`chronicletwo:port/src/debug_mode.cpp:7`) are the one switch for the debug surfaces. An Ixion build meant to ship should change these, because any `--jump` turns the surfaces on.
- **Long walkthroughs.** Retail record and play (`chronicletwo:port/src/gamepad.cpp:113-170`) captures a sequence once, but only within one mode, and the file is overwritten on each mode exit. It suits a single town visit, not a cross-world trip.

## Risks and blockers

- **No CPU-only path.** The renderer starts before `MainLoop` (`chronicletwo:port/src/main.cpp:295`) and no option skips it. Every boot needs a Vulkan device. The Windows CI job excludes `gpu` cases (`chronicletwo:.github/workflows/pc.yml:145`), so Smoke and any device-bound jump check do not run there.
- **Skips count as passes.** The real-data cases exit 77 or call `GTEST_SKIP` without `DC2_DATA` (`matrix.py:409`, `pc_settings_replay.py:33`). CI sets no data, so a regression in `--jump`, `--input`, the sweeps or the settings replays would not fail any job. `docs/PC.md:80` records the same rule for the two pointer checks, `Records.Check` and `Truncations.Check`.
- **Silent exit without a screenshot.** If the loop leaves its mode table before `--frames` (`chronicletwo:port/src/mainloop.cpp:214-215`), the process exits 0 and writes nothing (`chronicletwo:port/src/main.cpp:317-320`). Check the log line and the PNG, not only the status.
- **Stale data-root manifest check.** `chronicletwo:scripts/port/run_from_save.py:21-22` requires `manifest.txt` at the data root. The extraction writes `manifest.json` and `data.json` (`chronicletwo:port/src/platform/firstrun.cpp:27-28`), and the extracted root has no `manifest.txt`. The runner would reject a valid data root; `docs/PC.md:343-351` documents it without a test (inference from the code and the extracted tree; not run).
- **Stale comment.** `kazarov:include/platform/input_script.hpp:43` says `key:grave` toggles debug mode "as the live key does". No action binds the grave key by default (`kazarov:src/cpp/platform/input.cpp:51-84`); the name only maps to a scancode (`input.cpp:1402-1403`). No code path toggles `DebugFlag` from it. The comment is wrong for the pinned Kazarov.
- **Dead null checks.** `GamePrepareJump` tests `GetMapName(...) == nullptr` (`chronicletwo:port/src/test_hooks.cpp:185`) and `EditMapJump` tests the same (`chronicletwo:ps2/src/editloop.cpp:2745`). `GetMapName` returns the `SelectMapName` buffer instead of NULL (`chronicletwo:ps2/src/mapselect.cpp:367-375`), so both branches cannot fire. `GetMapType(...) < 0` (`mapselect.cpp:327-334`) is the working guard.
- **Name round trip at town entry.** Town entry runs the number through `GetMapName` and then `SearchMapNo` (`chronicletwo:ps2/src/editloop.cpp:877`). If two entries share a name, `town:N` may load a different map than requested. The sub-map redirect for 11-14 (`editloop.cpp:2736-2738`) points the same way (inference; verify by screenshot).
- **Four viewers are empty.** `chrview`, `texview`, `mapview` and `sound view` do nothing and return to the menu (`charaviewlp.cpp`, `texviewlp.cpp`, `mapviewlp.cpp`, `sndviewlp.cpp`). Their menu rows look usable and are not.
- **Destructive debug rows.** Save Data, Load cfg and Convert are reachable under a jump or `debug_mode`. The converter renames card directories (`chronicletwo:ps2/src/convviewlp.cpp:477-497`). Use only a fresh save root.
- **Global jump state.** `GameSetJump` stores one target (`chronicletwo:port/src/test_hooks.cpp:143-150`). A second `--jump` in one process would overwrite the first. Unit tests rely on one process per case.
- **Language change.** Any jump forces English (`chronicletwo:port/src/mainloop.cpp:99`), so a jumped run cannot be compared text-for-text with an ordinary boot.
- **Frame counts depend on the boot path.** `--frames` counts every main-loop frame from process start. A jump skips the logos, so frame numbers in input scripts are relative to the jump, not to a retail boot.
- **Fragile symbol link.** `PortGameBootInit` is declared with `asm("Title_GameBootInit")` (`chronicletwo:port/src/test_hooks.cpp:21`). A rename of the retail symbol breaks the jump (inference from the asm label). The retail source declares the static `GameBootInit` (`chronicletwo:ps2/src/title.cpp:180`) and no ps2/ source carries the `Title_GameBootInit` label, so how the link binds the two is (unverified).
- **Debug surfaces in the release binary.** `test_hooks.cpp` and `debug_mode.cpp` compile into `darkchronicle`. They are off by default, but the command line and environment variables enable them.
- **Global frame-image counter.** `store_count` starts at 0 each process (`chronicletwo:port/src/mglib.cpp:83`). A second run in the same save root overwrites `i00000.png`.
- **Unused host actions.** `developer_menu` and `debug_menu` have no reader (`kazarov:src/cpp/platform/input.cpp:81-82`). The options page still shows `debug_menu` (`chronicletwo:port/src/options/rows.cpp:135`), so a player can bind a control that does nothing.
- **Name collision.** "Records" in `docs/port/records.md` means struct-layout inventory. A reader looking for replay or recording tools will not find them there.
- **Abort on stubs.** `PS2_UNIMPLEMENTED` aborts (SIGABRT, or `0xC0000409` on Windows) so a debugger stops at it (`chronicletwo:docs/PC.md:310`). A jump into an unimplemented path shows as a crash, not an exit code.

## Open questions

- What does event 100 do in each town? It is the default entry event (`chronicletwo:ps2/src/editloop.cpp:922-925`) and runs on every `town:N` jump and every debug map jump. It is not in `event/view_pal.txt`, so its content needs the event scripts.
- Which town numbers are valid? The table is read from data at runtime (`chronicletwo:ps2/src/mapselect.cpp:205-215`). A list would need the data tree and a loop over `GetMapType`.
- Does `--jump title` or `--jump menu` run on the publisher-only fixture? If so, a jump smoke test could run in the Linux job without the disc. Not tested here.
- Do `town:11` to `town:14` land on the sub-map of town 10, as `EditMapJump` suggests, or on their own maps?
- What are the real frame counts for each checkpoint, on a Windows GPU and on lavapipe? The documented ones are the author's.
- Should `run_from_save.py` move to `manifest.json` and `data.json`, with a test?
- Should `debug_menu` be removed from the PC options page until something reads it (`chronicletwo:port/src/options/rows.cpp:135`)?
- Is the `key:grave` comment (`kazarov:include/platform/input_script.hpp:43`) a leftover from an older toggle binding? A git history check in the Kazarov repository would settle it.
