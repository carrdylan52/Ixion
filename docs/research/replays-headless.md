# Headless runs and scripted verification

## What this covers

How the two ports run without a window and without a person at the keyboard: the
command-line switches, the `.input` replay format, screenshot and display-frame capture,
the test hooks that jump to a state, the CTest and script gates built on them, and the CI
jobs that run them. The end is a Windows cookbook for checking an Ixion prototype
automatically, with the commands and the output each should produce, then a comparison of
what Chronicle (DC1) has that matches ChronicleTwo (DC2).

Sources read: ChronicleTwo (`chronicletwo:`, the Ixion base, branch `ixion` off master f44a756),
Chronicle (`chronicle:`, master 3bc16763), and Kazarov (`kazarov:` is the kz main 9310c53 layout;
Chronicle's pinned copy at a0a5ff8 is cited as `chronicle:tools/kazarov/...`; ChronicleTwo's pin
3dc38ce is identical to kz for the files cited here unless noted). Nothing was built or run.
Every command below is derived from the code and docs, so it is a recipe to verify, not a
result. Where a value comes from a doc and was not re-checked, it is marked "doc claim".

## Key facts

- **ChronicleTwo has a full headless verification surface; Chronicle has the basics.** Both
  take `--headless`, `--offscreen`, `--frames`, `--screenshot`, `--input`, `--display-per-tick`,
  `--jump`, `--fast-load` and `--give`. ChronicleTwo adds `--screenshot-display N`, `--window WxH`,
  `--log-fps`, `event:<id>` and `town:`/`dungeon:n:floor` jumps, a tick-driven headless mixer, a
  data-root version check and a replay corpus (chronicletwo:port/src/main.cpp:66-100;
  chronicle:port/src/main.cpp:71-103).
- **`--frames N` exits after frame N, not tick N.** ChronicleTwo counts `mgEndFrame` calls and
  writes the screenshot inside `mgEndFrame` before `std::exit` (chronicletwo:port/src/mglib.cpp:1324-1351).
  Chronicle counts `g_frames` after `MGEndFrame` and returns from `RunGame`, then `main` writes the
  screenshot (chronicle:port/src/gameloop.cpp:917, 947; chronicle:port/src/main.cpp:450-452).
- **ChronicleTwo requires `--frames` with `--screenshot`, and `--screenshot-display` with `--screenshot`.**
  Chronicle accepts `--screenshot` alone and writes at window close (chronicletwo:port/src/main.cpp:166-171;
  chronicle:port/src/main.cpp:129-133).
- **`--frames 0` is accepted by Chronicle.** Its parser only rejects negatives, and the budget test is
  `g_frame_budget >= 0 && g_frames >= g_frame_budget`, so zero stops before the first frame (chronicle:port/src/main.cpp:118, 129;
  chronicle:port/src/gameloop.cpp:392-394). Inference: the screenshot then reads an empty
  `kPreviousFrame` and exits 1. ChronicleTwo requires a positive integer (chronicletwo:port/src/main.cpp:139).
- **The input-script parser is byte-identical in both pins.** `InputScriptParse` accepts
  `<frame> [pad1|pad2] [buttons] [key:NAME] [mouseN] [mouse:dx,dy] [wheel:n] [lx ly rx ry]`, `#` comments,
  and rejects a decreasing frame per pad (kazarov:src/cpp/platform/input_script.cpp:167-190;
  chronicle:tools/kazarov/port/platform/input_script.cpp:167-190). Keys and mouse drive pad 1 only (unverified).
- **Input frames are the same counter as `--frames`.** Both call the script's apply step from the
  pump hook with the frame count (chronicletwo:port/src/main.cpp:221; chronicle:port/src/main.cpp:237).
  Frame 0 covers the warm-up and loading screens (kazarov:include/platform/input_script.hpp header
  comment; chronicle:docs/PC.md:520-521).
- **ChronicleTwo ships a replay corpus; Chronicle ships none.** `tools/input/` holds 149 `.input`
  files, most with a header naming the `--jump`, `--frames`, `--window` and capture frames
  (chronicletwo:tools/input/). Chronicle has no `.input` file in its tree; its only worked script is
  a 15-line example in its PC doc (chronicle:docs/PC.md:527-535).
- **ChronicleTwo's gate suite is CTest-driven and mostly needs a GPU.** Eight headless test names carry the
  `gpu` label: `Smoke.HeadlessFramesScreenshot`, `Screenshot.OneFrameCommandLine`,
  `PresentIdentity.DisplayPerTickScreenshot`, `Matrix.Title`/`Matrix.Costume`, and
  `PcSettingsReplay.pad|mouse|zoom` (chronicletwo:port/src/tests/CMakeLists.txt:130-160;
  chronicletwo:port/src/tests/cmake/screenshot_one_frame.cmake; chronicletwo:port/src/tests/cmake/present-core.cmake;
  chronicletwo:port/src/tests/cmake/matrix.cmake:19-20; chronicletwo:port/src/tests/cmake/pc_settings.cmake).
  Chronicle has no equivalent; its only process-level test runs `darkcloud --headless --frames 1` with no data
  and checks status 3 (chronicle:port/src/tests/paths_xdg_test.cpp:58-75).
- **Only the fixture-based headless gates run in CI.** ChronicleTwo's Linux and macOS jobs run gpu-labelled
  tests (macOS excludes a list of report-only cases); its Windows job runs `ctest -LE gpu`, so hosted
  Windows runs no headless game (chronicletwo:.github/workflows/pc.yml:33, 91, 145). Real-data gates
  (`Matrix.*`, `PcSettingsReplay.*`) skip with status 77 when no data is present, which is the CI case
  (chronicletwo:port/src/tests/cmake/matrix.cmake:8-16; chronicletwo:scripts/port/pc_settings_replay.py:19-33).
- **Chronicle's CI runs darkcloud headless only on macOS and Flatpak.** The macOS job runs `--headless --frames 3`
  against a stand-in file and accepts exit 0 or 4; the Flatpak job checks exit 3 without data
  (chronicle:.github/workflows/pc.yml:98-110, 228-236). Its Linux job runs `ctest -j4` and the truncation audit only.
- **The data-root contract differs.** ChronicleTwo's first-run check requires `<root>/manifest.json`,
  `<root>/../port_data/manifest.json` and `<root>/../data.json` with `schema_version` 1 and the pinned
  `data_version` (chronicletwo:port/src/platform/firstrun.cpp:22-35; pinned value 3 in
  chronicletwo:tools/kazarov/data_version.json). A missing root exits 3 with a message naming the
  `dc2data extract` command (firstrun.cpp:37-67). Chronicle's `RequireData` only checks that the directory
  holds at least one regular file, with no version marker (chronicle:port/src/main.cpp:163-200).
- **Headless audio differs.** ChronicleTwo's headless mode renders the full mixer from the logic clock
  (`AudioInit(headless)` installs a pump hook, chronicletwo:port/src/audio_init.cpp:71-90), so voice levels and
  stream completion follow ticks. Chronicle's headless mode sets SDL's `dummy` audio driver
  (kazarov:src/cpp/platform/window.cpp:70) and opens a real-time device stream
  (chronicle:tools/kazarov/port/platform/audio.cpp:139-152), so its mixer is driven by the audio callback
  rather than by ticks (inference from those calls). Both
  pins write WAV capture tick by tick when a WAV path is set (kazarov:src/cpp/platform/audio.cpp:88-110).
- **Interpolation diagnostics exist only in ChronicleTwo's kazarov.** `KZ_INTERPOLATION_TRACE=<file>`
  appends per-draw classifications and `KZ_INTERPOLATION_TINT=1` tints interpolated draws
  (kazarov:src/cpp/gfx/displaylist.cpp:1060, 1632). Neither variable appears in Chronicle's pinned kazarov.
- **Environment prefixes differ.** ChronicleTwo sets `DC2`, Chronicle sets `DC`, and every
  `SettingsEnv` name is joined to the prefix at run time (chronicletwo:port/src/identity.cpp:8;
  kazarov:src/cpp/platform/settings.cpp:14-19). Kazarov's own `KZ_*` variables are read with raw `getenv`.
- **A PS2 stub aborts; on Windows that is status `0xC0000409`.** `PS2_UNIMPLEMENTED` calls abort
  (chronicletwo:docs/PC.md "Darkchronicle" exit statuses; chronicle:docs/PC.md:102-108). A
  harness sees `-1073740791` in `$LASTEXITCODE`, which is `0xC0000409` read as a signed 32-bit value.
- **A ChronicleTwo `--jump` turns on debug controls.** `GamePrepareJump` sets `DebugFlag = 1` and
  `PortGameBootInit` (chronicletwo:port/src/test_hooks.cpp:162-175), and `GameDebugEnabled` is true when a jump
  is set (test_hooks.cpp:156). Chronicle's jump sets `DebugMode` (chronicle:port/src/gameloop.cpp:827-829);
  its "debug mode on" line prints only when no jump is set (gameloop.cpp:833-835).
- **Jump grammar differs.** ChronicleTwo accepts `town[:n]`, `edit[:n]` (n up to 188),
  `dungeon[:n[:floor]]`, `event:<id>`, `title`, `opening`, `menu` (chronicletwo:port/src/test_hooks.cpp:78-141).
  Chronicle accepts `edit:n`, `dungeon:n` (floor select only), `title`, `rush`, `opening`, `menu`; a floor
  suffix or an unknown name exits 2 (chronicle:port/src/gameloop.cpp:571-604). `--jump edit` with no
  number selects map 0 in Chronicle (`Jump::map` defaults to 0, gameloop.cpp:197-201).

## How it works

### Frame and tick model

ChronicleTwo runs `MainLoop` (chronicletwo:port/src/mainloop.cpp). Each game frame is one
`MGBeginFrame`/`MGEndFrame` pair and one recorded display list; a frame spans `mgFrameRate` clock
ticks (chronicletwo:docs/PC.md "Ticks and display frames"). Headless sets `ClockSetUnbounded(true)`, so
the clock does not sleep and the loop runs as fast as the CPU allows (chronicletwo:port/src/main.cpp:305;
Chronicle's doc describes the same as "one tick per pump, no sleeping", chronicle:docs/PC.md:83).
Each frame renders one canonical image, which is what `--screenshot` reads through `kPreviousFrame`
(chronicletwo:port/src/mglib.cpp:1300-1340). `--display-per-tick N` renders N interpolated display frames
per tick and discards them, and the doc claims the screenshot bytes do not change
(chronicletwo:docs/PC.md:780, test `PresentIdentity.DisplayPerTickScreenshot`).

Chronicle has the same loop shape. Its headless run uses the unbounded clock, and the screenshot is
`GameScreenshot`, `ReadbackTexture(kPreviousFrame)` (chronicle:port/src/gameloop.cpp:781-782). It has
`--display-per-tick` with the same effect (chronicle:port/src/gameloop.cpp:751-753) but no test that
checks the identity.

### Input scripts

A script is a list of lines, each setting the held state of one pad from its frame onward until
the next line for that pad (kazarov:include/platform/input_script.hpp header comment). A line with no
buttons releases everything. A stick needs four numbers. Installation overrides the pad device
(`InputScriptInstall`, kazarov:src/cpp/platform/input_script.cpp:241-248), and each pump applies the
state for the current frame (`InputScriptApply`, input_script.cpp:250-262). Because a press is an edge in
`CGamePad`, a press needs a later release line (chronicle:docs/PC.md:524-525; the same rule holds for
both games).

Bad scripts exit 2 before the window opens. In ChronicleTwo the message is
`bad input script: <path>: line N: <reason>` (chronicletwo:port/src/main.cpp:263-270).

### Captures

- `--screenshot PATH` with `--frames N` writes the canonical image of frame N.
  Success prints `mglib: frame N written to PATH` (chronicletwo:port/src/mglib.cpp:1338). Failure prints
  `... could not be written to` and exits 1 (mglib.cpp:1341-1347).
- `--screenshot-display K` writes `<stem>-display-<i>.png` for i = 0..K-1, each at alpha i/K from the
  previous list to the newest (chronicletwo:port/src/mglib.cpp:320-343; the darkchronicle option table in
  chronicletwo:docs/PC.md, "darkchronicle"). Each success prints `mglib: display frame i of frame N written to ...`.
- `--screenshot-fps` draws the counter into the image; with `--offscreen`, the image is read from the
  display image instead (chronicletwo:docs/PC.md, "Ticks and display frames", last bullets).
- Chronicle's `--screenshot` writes after `RunGame` returns, so it captures the last canonical tick on a
  frame-budget exit, a window close, or a stop request. It prints nothing on success
  (chronicle:port/src/main.cpp:450-452, 354-364).

### Exit paths

| Status | ChronicleTwo | Chronicle |
|---|---|---|
| 0 | window closed, or frame N reached (with its screenshot) | window closed, or frame budget reached |
| 1 | window/renderer failure, or screenshot write failure | window/renderer failure, or screenshot write failure |
| 2 | usage error, bad `--jump`, `--give` or `--input` | same |
| 3 | data root missing or not current (no window opened in headless) | data root empty or missing (no window opened in headless) |
| 4 | game assert (`__assert`), e.g. `LoadFile` on a file that is not present | same |
| 134 / 0xC0000409 | `PS2_UNIMPLEMENTED` abort | same |

Sources: chronicletwo:port/src/platform/firstrun.cpp:55-67, chronicletwo:docs/PC.md "darkchronicle",
chronicle:port/src/exitcodes.hpp, chronicle:docs/PC.md:102-108.

### Data roots

ChronicleTwo's root is what `--data` (or `--run-dir`/`DC2_DATA`) names, and it must be the `data`
directory of a current extraction. Its parent holds `data.json`, `port_data/manifest.json` and
`datapacks/` (chronicletwo:docs/PC.md:164-184). `FirstRunDataMissing` rejects a root that lacks any of
these, or whose marker has a different `data_version` (firstrun.cpp:22-35). The check runs before
`--frames`, so a missing root never reaches the first frame.

The data path matters for a second reason: `PathsConsumeArgs` matches `--data`, `--save` and `--run-dir` by
prefix (kazarov:src/cpp/platform/paths.cpp:146-167). Any new option that begins with one of those
strings is taken as a path. When `--data` is absent, the fallback depends on the game. ChronicleTwo sets
`coherent_default_root` (chronicletwo:port/src/identity.cpp:10), so its fallback is the installed data
directory, not the working directory (kazarov:src/cpp/platform/paths.cpp:200-205). Chronicle does not set
that flag, so its fallback is `DC_DATA`, then `data/` in the working directory, then beside the executable
(kazarov:src/cpp/platform/paths.cpp:200-205; chronicle:port/src/identity.cpp:9-10). Always pass `--data` and
`--save` explicitly.

The Windows launcher is different. `tools/windows/kazarov.ps1` runs the game with
`--run-dir port\run` and extracts the disc into `port/run/data` first (chronicletwo:tools/windows/kazarov.ps1:132,
183). Its own process doc says not to run `run.bat` in a worktree because it re-extracts shared data
(chronicletwo:docs/port/process/SCHEDULE.md:321). For verification, run the built exe directly.

### Audio capture

ChronicleTwo: with `DC2_AUDIO_WAV=<path>`, the platform WAV capture advances the mixer per tick, the headless hook
is not installed, and `DC2_AUDIO=off` does not suppress the WAV (chronicletwo:docs/PC.md:883-885;
kazarov:src/cpp/platform/audio.cpp:139). The doc says the title capture at `--frames 2500` gives 60 s of
48 kHz stereo, silent through language select, with RMS about 750 and peaks near 24,000 at the title
(chronicletwo:docs/PC.md:941; doc claim, not re-run).

Chronicle: `DC_AUDIO_WAV` does the same, with the example `darkcloud --headless --jump title --fast-load --frames 600`
(chronicle:docs/PC.md:1100-1106). Without it, headless audio goes to the SDL dummy driver in real time.

## Cookbook (Windows)

These commands are for PowerShell from the Ixion checkout. Replace the placeholders. Nothing here has
been run. Expected outputs are from the code or doc cited with each step.

### Setup

```powershell
$repo  = "<ixion-checkout>"
$exe   = "$repo\port\build\windows-x64\darkchronicle.exe"
$tests = "$repo\port\build\windows-x64-tests"
$data  = "<game-root>\data"          # must sit beside <game-root>\data.json and <game-root>\port_data
$out   = "<scratch>\run-$(Get-Date -Format yyyyMMddHHmmss)"
New-Item -ItemType Directory -Force $out | Out-Null
```

The game root must be a current extraction (`data.json` with the pinned `data_version`). Keep it read-only
for verification. A run writes into its save root (saves, `config.json`, and `pipeline_cache.bin`,
chronicletwo:docs/PC.md "Startup" step 6), so give each run a fresh save directory.

### A. Build and unit gates

```powershell
.\build.bat windows-x64                                  # Debug build, port\build\windows-x64
.\tools\windows\configure-tests.ps1 -Root .kazarov\windows -BuildDirectory $tests
.\tools\windows\build.ps1 -Root .kazarov\windows -BuildDirectory $tests -Tests
ctest --test-dir $tests -LE gpu --output-on-failure -j4  # the CI Windows subset
ctest --test-dir $tests -R TestHooks --output-on-failure # jump-parser cases, no data needed
ctest --test-dir $tests -N -L gpu                        # list the device-needing cases
```

Expected: `100% tests passed, 0 tests failed out of N` for the first two (doc: chronicletwo:docs/PC.md Windows
section; chronicletwo:.github/workflows/pc.yml:145). `TestHooks.JumpAcceptsModesAndBounds` covers the parser
(chronicletwo:port/src/tests/test_hooks_test.cpp:17-38).

### B. Failure probes (no data, no GPU work)

```powershell
& $exe --headless --offscreen --data "$out\absent" --save "$out\save-absent" --frames 1
$LASTEXITCODE   # expect 3; stderr starts "No current Dark Chronicle data at ..."
```

```powershell
Set-Content "$out\bad.input" "0 cross`n5 bogus"
& $exe --headless --offscreen --data $data --save "$out\save-bad" --input "$out\bad.input" --frames 10
$LASTEXITCODE   # expect 2; stderr "bad input script: <path>: line 2: unknown button \"bogus\""
```

Both exit before any Vulkan device is created (chronicletwo:port/src/main.cpp:250-281).

### C. Smoke with real data

```powershell
& $exe --data $data --save "$out\save-smoke" --headless --offscreen --window 1024x768 `
       --frames 3 --screenshot "$out\smoke.png"
$LASTEXITCODE   # expect 0
```

Expected stderr, in this order: `Vulkan: using <device> (Vulkan x.y.z), offscreen` (renderer start-up; the
`, offscreen` tail appears only in offscreen mode; chronicletwo:tools/kazarov/src/cpp/gfx/renderer.cpp:242),
`compiling shaders k/n` lines on a cold cache, `dataread: indexed N files under ...` (after the renderer,
at `InitCDFile`; chronicletwo:docs/PC.md "Startup" step 9), and `mglib: frame 3 written to ...`. The PNG is 1024x768.
`N` is the count from the index walk, which for the 2026-10-13 extraction under the walk rules is 7511
(my count, not run). The PC doc says 8751 for DATA.DAT (doc claim). Treat the number as a
checkpoint to compare against the same binary, not as a fixed fact.

Drop `--offscreen` to get a hidden window on Windows (`--headless` alone). The renderer falls back to
offscreen when the instance lacks `VK_EXT_headless_surface` (renderer.cpp:1143; window.cpp:63-70).

### D. Checkpoint replays

Title screen, the matrix's Title scene (`Matrix.Title` uses frame 2500 for this script; the script's own
header says START at the title enters the next mode):

```powershell
& $exe --data $data --save "$out\save-title" --headless --offscreen --window 1024x768 `
       --input "$repo\tools\input\sweep-title.input" --frames 2500 --screenshot "$out\title.png"
```

Palm Brinks town, controllable Max (doc claim: by frame 120; chronicletwo:docs/DEBUG.md "Jump replays"):

```powershell
& $exe --data $data --save "$out\save-town" --headless --offscreen --window 1024x768 `
       --jump town:10 --fast-load --frames 120 --screenshot "$out\town.png"
```

Underground Channel floor 1, with movement (doc claim: HUD and minimap by 2100, moved by 2300):

```powershell
& $exe --data $data --save "$out\save-floor1" --headless --offscreen --window 1024x768 `
       --jump dungeon:0:1 --fast-load `
       --input "$repo\tools\input\jump-dungeon-floor1.input" --frames 2300 --screenshot "$out\floor1.png"
```

Read the PNGs with the file viewer tool to check them by eye; the game does not assert pixels in these runs.

### E. Determinism and display identity

```powershell
# Same binary, script, frames, window and config; fresh save each time.
& $exe --data $data --save "$out\save-a" --headless --offscreen --window 1024x768 `
       --input "$repo\tools\input\sweep-title.input" --frames 2500 --screenshot "$out\a.png"
& $exe --data $data --save "$out\save-b" --headless --offscreen --window 1024x768 `
       --input "$repo\tools\input\sweep-title.input" --frames 2500 --screenshot "$out\b.png"
Get-FileHash "$out\a.png", "$out\b.png" -Algorithm SHA256   # expect equal hashes

# Display frames must not change the canonical image.
& $exe --data $data --save "$out\save-c" --headless --offscreen --window 1024x768 `
       --input "$repo\tools\input\sweep-title.input" --frames 2500 --display-per-tick 4 `
       --screenshot "$out\c.png"
Get-FileHash "$out\a.png", "$out\c.png" -Algorithm SHA256   # expect equal hashes
```

The first equality is what the timing doc says a replay comparison needs (chronicletwo:docs/port/headless-replays.md,
last paragraph). The second is the `PresentIdentity` gate's claim. Neither was run here.

Display-frame capture at eight phases (interpolation check; stderr lines `mglib: display frame k of frame N written to`):

```powershell
& $exe --data $data --save "$out\save-d" --headless --offscreen --window 1024x768 `
       --input "$repo\tools\input\pc-settings.input" --jump town:10 --fast-load --frames 1850 `
       --screenshot "$out\settings.png" --screenshot-display 8
# writes settings-display-0.png .. settings-display-7.png
```

### F. Audio

```powershell
$env:DC2_AUDIO_WAV = "$out\title.wav"
& $exe --data $data --save "$out\save-audio" --headless --offscreen --window 1024x768 `
       --input "$repo\tools\input\sweep-title.input" --frames 2500
Remove-Item Env:DC2_AUDIO_WAV
```

Expected (doc claim): a 48 kHz stereo WAV, silent through language select, with title music after
the logo. Check with a short script that reads the RMS per second. The WAV path makes the WAV capture the
mixer's owner (chronicletwo:docs/PC.md:883-885), so compare WAV runs only with other WAV runs.

### G. Interpolation diagnostics

```powershell
$env:KZ_INTERPOLATION_TRACE = "$out\interp.txt"   # appended per draw at alpha 0
$env:KZ_INTERPOLATION_TINT  = "1"                 # tints interpolated draws on the main image
& $exe --data $data --save "$out\save-g" --headless --offscreen --window 1024x768 `
       --input "$repo\tools\input\pc-settings.input" --jump town:10 --fast-load --frames 1850 `
       --screenshot "$out\tinted.png" --screenshot-display 8
Remove-Item Env:KZ_INTERPOLATION_TRACE, Env:KZ_INTERPOLATION_TINT
```

These are for inspection. Do not compare tinted screenshots with untinted ones.

### H. CTest gates that run headless with fixtures or real data

```powershell
ctest --test-dir $tests -R "Smoke|Screenshot|PresentIdentity" --output-on-failure
```

Expected: each prints its marker and passes: `SMOKE_OK` (chronicletwo:port/src/tests/CMakeLists.txt:148),
`ONE_FRAME_CAPTURE_OK` (screenshot_one_frame.cmake:25), `PRESENT_IDENTITY_OK` (present_identity.cmake:40). These
use an empty fixture root (`empty_data.cmake`) and need a Vulkan device.

Real-data gates need the data root exported. CTest runs them from the build directory, and the script's
default `data` is relative to the working directory, so an unset `DC2_DATA` skips them (inference):

```powershell
$env:DC2_DATA = $data
python "$repo\scripts\port\matrix.py" --exe $exe --input "$repo\tools\input\sweep-title.input" `
       --frame 2500 --scene title --data $data --work "$out\matrix-title"
# exit 0 PASS, 1 FAIL, 77 SKIP. Needs numpy and Pillow (or DC2_PYTHON).
```

`matrix.py` launches about 11 runs per scene (the reference 1024x768, three Fill sizes, a letterbox
1280x720 and its Fill frame of 960x720, and four `--display-per-tick 4` variants). It writes `report.md` and
`summary.json`, and the check is `Result: PASS` (scripts/port/matrix.py:193-225, 366-390). PSNR below
35 dB is a flag unless `--psnr-gate` is passed (matrix.py:41-42).

```powershell
$env:DC2_DATA = $data
python "$repo\scripts\port\pc_settings_replay.py" --exe $exe --work "$out\pcs" --case pad
# expect: PASS: pad PC settings replay and saved configuration; receipts: ...
```

The `pad`, `mouse` and `zoom` cases use `--window 1280x960` and assert the saved `config.json` keys
(chronicletwo:scripts/port/pc_settings_replay.py:40-74).

### I. Save fixtures

`scripts/port/run_from_save.py` is meant to copy a fixture and replay it, but it checks for
`data/manifest.txt` and exits 2 on the current extraction, which has `manifest.json`
(run_from_save.py:21-22; extraction contents). Until that is fixed, copy the fixture by hand:

```powershell
Copy-Item -Recurse "<fixture>" "$out\save-fixture"     # copy the fixture root, which holds saves/
& $exe --data $data --save "$out\save-fixture" --headless --offscreen --window 1024x768 `
       --input "$repo\tools\input\pc-continue.input" --frames 5000 --screenshot "$out\loaded.png"
```

The fixture must have `saves/`, `mc0/` or `mc1/` (run_from_save.py:14-17). The copy keeps the fixture
unchanged.

### J. Chronicle equivalents (for comparison runs)

```powershell
& "<chronicle-build>\darkcloud.exe" --data "<chronicle-data>" --save "<save>" --headless --offscreen `
   --jump edit:0 --fast-load --frames 120 --screenshot "<out>\town.png"
```

Chronicle's extraction is a plain directory with `data.hd2` and no `data.json`, so `RequireData` only
checks that files exist (chronicle:docs/PC.md:1907-1958). Its headless window on Windows is hidden
(chronicle:docs/WINDOWS.md:84-88). `--jump edit:0` selects Chronicle's map 0 (Norune, `e01`, per the
Chronicle map numbering in chronicle:docs/PC.md "Test hooks"); its map numbers are its own, so look a
town up before comparing it with ChronicleTwo's `town:10`. Chronicle prints no success line for the
screenshot, so check the file.

## What Chronicle lacks compared with ChronicleTwo

- No `.input` replay corpus, no per-scene capture headers, and no checkpoint frames beyond one example.
- No gpu-labelled headless CTest gates (no `Smoke`, `OneFrameCommandLine`, `PresentIdentity`,
  `Matrix`, or `PcSettingsReplay` equivalents). Its one process test is the no-data status check.
- No Linux headless run in CI; its macOS job runs one, and its Windows job runs none.
- No pixel gate for `--display-per-tick`; the feature exists in code.
- No `--screenshot-display`, `--log-fps`, `--window WxH` (it has `--width` and `--height`), or `event:<id>` and
  floor-selecting `dungeon:n:floor` jumps.
- No boot index line (`dataread: indexed`), so a checker cannot read a file count from stderr.
- No data-version marker, so a stale extraction is not detected at boot.
- Headless audio is real-time through SDL's dummy driver unless a WAV path is given.
- `--frames 0` is accepted (see Key facts).
- Its pinned Kazarov lacks the interpolation trace and tint variables.

## Ixion hooks

1. **Jump grammar.** `GameParseJump` in `chronicletwo:port/src/test_hooks.cpp:78` is the single parse point.
   An Ixion cross-world destination (for example `world:dc1:town:10`) fits here, with the same
   bounds-check style. `GamePrepareJump` (test_hooks.cpp:162) is where its state is installed. Add the
   accept and reject cases to `TestHooks.JumpAcceptsModesAndBounds` (`port/src/tests/test_hooks_test.cpp`),
   which runs without data.
2. **Command-line option.** `ParseOptions` and `Usage` in `chronicletwo:port/src/main.cpp:66` and `:123`.
   An Ixion option (for example `--ixion-train-state`) follows the same pattern and must not start with
   `--data`, `--save` or `--run-dir`, because `PathsConsumeArgs` would take it as a path
   (kazarov:src/cpp/platform/paths.cpp:146-167).
3. **Second data root.** `PathsDataRoot` and `PathsSetDataRoot` (kazarov:src/cpp/platform/paths.cpp:188-207) give one
   root. A DC1 root for Ixion needs its own override, and `FirstRunDataMissing` (firstrun.cpp:22) needs a
   separate check, since Chronicle's layout has no `data.json`. Inference: this is the first design
   question for any cross-world run.
4. **Frame-keyed scripts for Ixion moments.** Scripts in `tools/input/ixion-*.input` (with headers in the
   existing style) can reach a station, a train arrival or a time-travel prompt by frame. Each script
   should name the `--jump` it starts from and the capture frames.
5. **Gate registration.** New `.cmake` files in `port/src/tests/cmake/` are included automatically by the glob
   at `chronicletwo:port/src/tests/CMakeLists.txt:161`. Use the `add_test` plus `LABELS gpu` form of
   `screenshot_one_frame.cmake` for Ixion smoke, and reuse `empty_data.cmake` for a no-data probe.
6. **Replay runner.** `scripts/port/matrix.py` writes a provenance receipt per run (binary hash, input hash,
   config hash, frames, window), which Ixion can copy for its own comparisons (matrix.py:226-290). Fix
   `run_from_save.py` first.
7. **Data sanity line.** The `dataread: indexed N` line (`chronicletwo:port/src/dataread.cpp:331`) gives a cheap
   assertion that the root is the expected extraction before any replay runs.
8. **Interpolation check.** `KZ_INTERPOLATION_TRACE` (kazarov:src/cpp/gfx/displaylist.cpp:1060) can confirm that
   any Ixion-added 3D object is tagged for interpolation, if Ixion adds moving models.
9. **Audio cues.** `AudioInit(headless)` (`chronicletwo:port/src/audio_init.cpp:71`) makes headless audio follow the
   logic clock (per the timing doc), so a WAV-based check of an Ixion sound cue (for example a train whistle)
   should be reproducible. Confirm before relying on it.
10. **Exit-time state dump.** The screenshot path runs inside `mgEndFrame` before `std::exit`
    (`chronicletwo:port/src/mglib.cpp:1326-1351`). An Ixion state line printed there would give a checker a
    value to assert on without reading pixels.

## Risks and blockers

- **Kazarov pins differ.** Chronicle is at a0a5ff8, ChronicleTwo at 3dc38ce, and the kz clone is at 9310c53. A
  merged Ixion build has to pick one pin. Any Chronicle baseline captured on the old pin is not comparable to
  an Ixion capture on the new one.
- **Real-data gates run only locally.** CI has no real data, so `Matrix.*` and `PcSettingsReplay.*` skip there,
  and Windows CI runs no headless game at all. A regression in an Ixion path that only shows on real data will
  not be caught by CI.
- **Frame-keyed replays drift.** Adding loading frames, logic frames or a new warm-up shifts every capture
  and every `--input` line. Re-baseline after any frame-count change, and treat the doc frame numbers as
  stale until re-checked.
- **Determinism is asserted, not verified here.** The docs say two runs with the same binary, script, frame
  limit, window and fresh save give the same bytes (chronicletwo:docs/port/headless-replays.md). Confirm
  with the section E hash check before building on it.
- **Debug state.** `--jump` enables `DebugFlag` and loads the debug presets (`dbg/pb.cfg`, `dbg/cap1.cfg`;
  test_hooks.cpp:175-195). A jumped run does not show ordinary play. Some replays need `game.debug_mode`
  in the save's `config.json` (`area-*-sweep.input` headers).
- **Device dependency.** Every headless run needs a Vulkan device on Windows, including `--offscreen`. The
  `Vulkan: using ...` line is the main record of the device and whether the run was offscreen.
- **Stub aborts look like crashes.** A `PS2_UNIMPLEMENTED` hit exits with `0xC0000409` and no screenshot. A
  checker that expects 0, 1, 2, 3 or 4 must treat the others as a fault.
- **Path fallback.** A missing `--data` falls back to `data/` in the working directory on Chronicle only; ChronicleTwo
  falls back to its installed data directory (see Data roots). Always pass it.
- **Broken helper.** `run_from_save.py` exits 2 on the current extraction (manifest name). `pc_settings_replay.py`
  defaults `DC2_DATA` to a relative `data` (pc_settings_replay.py:19), so it skips unless the variable is set.
- **Doc numbers.** The PC doc's startup section gives 8751 for the index count, and a process doc's `dc2data list`
  count is 8753; the WAV figures are doc claims. My walk-rule count for the 2026-10-13 extraction is 7511. Do
  not use any of these as a hard gate until a run confirms them.
- **Not every switch is pixel-verified.** `Matrix.*` compares sizes with each other and letterbox with Fill. It
  does not compare hidden-window runs with offscreen runs, and nothing here does either.
- **Frame-zero behaviour.** The script header says frame 0 covers the warm-up and loading screens, so
  timing-sensitive lines should start after a documented checkpoint rather than at frame 0 (inference from the
  header; not re-tested).

## Open questions

- What `dataread: indexed N` value does the current extraction print? The walk rules give 7511; the PC doc
  gives 8751 and a process doc's list count is 8753. Run once to settle it.
- Are two identical runs byte-identical in practice? The docs say so; no run here checked it.
- Does `--headless` on a hidden window and `--offscreen` give the same pixels for the same script? Nothing in
  the tests compares the two modes.
- Does the WAV from `sweep-title.input` at 2500 frames really run 60 s? The docs say so; the frame-to-tick ratio
  at the title may differ (inference).
- How will Ixion present two data roots to a process that expects one ChronicleTwo `data.json` layout, and what
  version marker will a Chronicle extraction carry?
- Does Chronicle's real-time headless audio change any of its screenshots? It is untested in both directions.
- Should `run_from_save.py` check `manifest.json` (as `pc_settings_replay.py` already does) or accept either name?
