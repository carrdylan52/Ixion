# ChronicleTwo platform layer: input, audio, config and paths

## What this covers

The host-facing layer of the ChronicleTwo (Dark Chronicle, PAL) PC port: the
startup sequence and command line, environment variables, the config file and
its save root, the save-slot and memory-card directories, the pad and mouse
input path, the menu and camera mouse, the audio device and the retail sound
driver port, the movie player, and the data index. For each, the note says
whether the state is process-wide (and so collides when a second game shares
the process) and which paths or names would need per-game namespacing in
Ixion.

Citations: `chronicletwo:` is the ChronicleTwo checkout (branch base
f44a756); `kazarov:` is the Kazarov submodule at the ChronicleTwo pin
3dc38ce (the kz clone's main, 9310c53, has no file differences in these
paths); `chronicle:` is the Chronicle (DC1) checkout, read only for the
comparisons that matter for collisions.

## Key facts

- Startup order is fixed in one function: identity, argument consumption,
  option parsing, config load, data-root check, window, input, renderer,
  audio, clock, change hook, data index, main loop
  (`chronicletwo:port/src/main.cpp:250-317`).
- The identity call is the only place that sets the environment prefix
  (`DC2`), the path configuration (app dir `chronicletwo`, env names
  `DC2_DATA` and `DC2_SAVE`, both coherent-root flags) and the window
  title and app id (`Dark Chronicle`, `chronicletwo`)
  (`chronicletwo:port/src/identity.cpp:7-12`).
- Chronicle's identity call sets prefix `DC`, app dir `chronicle`, env
  `DC_DATA` and `DC_SAVE` without the coherent flags, title `Dark Cloud`
  and app id `dcdecomp.darkcloud` (`chronicle:port/src/identity.cpp:9-14`).
- Kazarov keeps exactly one environment prefix per process; `SettingsEnv`
  returns null when none is set (`kazarov:src/cpp/platform/settings.cpp:8-20`).
  The shared Kazarov code therefore reads only one game's `<PREFIX>_*`
  variables.
- Kazarov's path configuration is one struct of globals; the data and save
  roots are memoised on first use, so the first caller wins
  (`kazarov:src/cpp/platform/paths.cpp:25-31`, `:198-242`).
- Data-root precedence: `--data`, then `--run-dir` (`<dir>/data`), then
  `DC2_DATA`, then the per-user default (`paths.cpp:198-207`). The default
  for ChronicleTwo is `Installed("data")`, never a local folder, because the
  coherent flag skips the local probe (`paths.cpp:203`).
- Save-root precedence: `--save`, `--run-dir` (`<dir>/saves`), `DC2_SAVE`,
  then for ChronicleTwo the per-user `saves` folder (`paths.cpp:215-222`).
  An identity without the coherent flag (Chronicle's, as its current
  `identity.cpp` sets it) instead probes a local `save/` and a local `data/`
  parent (`paths.cpp:225-231`). Chronicle's pinned Kazarov predates the flags,
  so its actual behaviour is the older branch described under Key facts.
- On Windows, `Installed` resolves to `%LOCALAPPDATA%\<app dir>\<name>`
  (`paths.cpp:66-72`); elsewhere `$XDG_DATA_HOME` or `~/.local/share`
  (`paths.cpp:73-81`).
- Command-line flags consumed by Kazarov: `--data`, `--save`, `--run-dir`
  (`paths.cpp:137-182`). The port parses the rest: `--jump`, `--give`,
  `--fast-load`, `--headless`, `--offscreen`, `--frames`, `--window WxH`,
  `--display-per-tick`, `--show-fps`, `--log-fps`, `--screenshot`,
  `--screenshot-display`, `--screenshot-fps`, `--input`
  (`chronicletwo:port/src/main.cpp:66-92`, `:123-173`).
- Environment variables read through `SettingsEnv` (prefix `DC2_`):
  `JUMP` (main.cpp:255), `GIVE` (:256), `FAST_LOAD` (:261),
  `VULKAN_VALIDATION` (:294), `AUDIO=off` and `AUDIO_WAV=<path>`
  (`audio_init.cpp:58-76`, `kazarov:src/cpp/platform/audio.cpp:139-142`),
  `AUDIO_TRACE` (`kazarov:src/cpp/audio/trace.cpp:12`). Test-only names:
  `GFX_OFFSCREEN`, `TEST_FONT`, `DC2_CAPTURE_DIR`, and the recovery-root
  variables in `save_slots_test.cpp`.
- Environment variables read with no prefix: `KZ_INTERPOLATION_TRACE` and
  `KZ_INTERPOLATION_TINT` (`kazarov:src/cpp/gfx/displaylist.cpp:1060`,
  `:1632`), and `LOCALAPPDATA`, `XDG_DATA_HOME`, `HOME` (paths.cpp:69-75).
- `DC2_DATA` is read with the wide `_wgetenv` (`paths.cpp:36-41`), but
  `AUDIO_WAV` and the other `SettingsEnv` values use the narrow
  `std::getenv` (`settings.cpp:19`).
- The config file is `<save root>/config.json`. It has four sections
  (`game`, `video`, `audio`, `input`) and 36 recognised keys
  (`chronicletwo:port/src/platform/config.cpp:196-311`). Unknown keys are
  reported on stderr and ignored; unknown keys already in the file survive a
  save (`config.cpp:316-356`).
- The tick rate defaults to 50 Hz for the PAL disc
  (`chronicletwo:port/src/platform/config.hpp:8-9`).
- `config.json` is replaced through a temporary file with the fixed name
  `config.json.tmp` (`config.cpp:358-377`, the temp name at `:360`). The
  save path also writes `key_cap.bin` (`gamepad.cpp:157`) and
  `pipeline_cache.bin` (`main.cpp:289`) into the save root.
- Config has a single change-hook slot (`config.cpp:571-573`). Only
  `ApplyConfigChange` in the port's main registers it (`main.cpp:308`).
- Config-change side effects: clock rate, present mode, input bindings,
  sound settings, soundtrack reload, and the present settings
  (`chronicletwo:port/src/main.cpp:233-248`).
- Save slots: `SaveSlotsRoot()` is `<save root>/saves`; slot files are
  `BESCES-51190dkcl<n>`, with `.card2` for the second card
  (`chronicletwo:port/src/save_slots.cpp:36`, `:288-291`). Slot names are
  recognised only if they start with that prefix (`save_slots.cpp:294-300`).
- Chronicle's memory-card directory is `BESCES-50295dkcloud`
  (`chronicle:ps2/src/memorycardaccess.cpp:35`), so the two games' slot names
  do not overlap.
- The save image version tag is `dc2Ver4` (written at
  `chronicletwo:port/src/memcard.cpp:125`); older `dc2Ver2` is read
  (`save_slots.cpp:362-363`).
- The import archive is `<save root>/imported/mc0|mc1`
  (`save_slots.cpp:224-225`). Legacy per-save folders are scanned from
  `<save root>/mc0|mc1` (`save_slots.cpp:398`).
- The PS2 memory-card shim maps card `N` to `<save root>/mc<N>`
  (`kazarov:src/cpp/sce/libmc.cpp:130`). The host-file shim maps to
  `<save root>/host0` (`kazarov:src/cpp/sce/sifdev.cpp:47`). The CD shim
  resolves against the data root (`kazarov:src/cpp/sce/libcdvd.cpp:34`).
  So the same `mc0` directory is both a live card and a legacy import source.
- Soundtrack mapping and recordings live in a `soundtrack/` folder beside the
  save root (`kazarov:src/cpp/audio/soundtrack.cpp:79`, `:111`), and only
  when the config option is on (`soundtrack.cpp:137`).
- Glyph art is searched in the executable folder and then `<save root>/glyphs`
  (`kazarov:src/cpp/platform/glyphs.cpp:66-72`). The optional sharp font is
  searched in the save root and the executable folder (`font.cpp:36`).
- Pads: two pads (`kazarov:include/platform/input.hpp:15`). The first gamepad,
  keyboard and mouse drive pad 0; the second gamepad drives pad 1.
- The action table is fixed in code: 16 buttons, 8 half-axes, 4 whole axes, and
  5 host actions (`fps_toggle`, `developer_menu`, `debug_menu`, `gyro_hold`,
  `zoom_reset`) (`kazarov:src/cpp/platform/input.cpp:51-85`,
  `:110-111`). Config bindings can only rebind these names.
- `InputInit` opens the SDL gamepad subsystem and registers a window event
  hook (`kazarov:src/cpp/platform/input.cpp:670-680`). Headless runs skip
  the SDL subsystem and only apply bindings
  (`chronicletwo:port/src/platform/input_startup.cpp:70-78`).
- The pad read path is `CGamePad::UpDate` (`chronicletwo:port/src/gamepad.cpp:26`)
  -> `PortReadPad` -> the retail `read_pad` state machine
  (`chronicletwo:port/include/stubs/gamepad.hpp:4,7-9`) -> the libpad shim
  (`kazarov:src/cpp/sce/libpad.cpp:36-62`), which reads the Kazarov input
  state.
- `UpDate` disables the keyboard-to-D-pad fallback every frame
  (`gamepad.cpp:29`).
- The mouse-look latch runs only for the retail `GamePad__2` object
  (`chronicletwo:port/src/padcontrol.cpp:12-14`). `GamePad__2` is a single
  global (`chronicletwo:ps2/src/mainloop.cpp:2119`).
- Camera consumers keep their own static "last read" counters:
  `cameracontrol.cpp:77-79`, `:183`; `camera_fixed.cpp:229`;
  `first_person_walk.cpp:62`.
- Menu mouse state is file-scope (`chronicletwo:port/src/menu_mouse.cpp:27-47`).
  Its capture toggles the Kazarov menu-mouse flag (`menu_mouse.cpp:132`).
- The Options screen state is a file-scope singleton `g_screen`
  (`chronicletwo:port/src/options/screen.cpp:30`). Its saves go through
  `DisplayApply` and `ConfigChange` (`screen.cpp:48-49`).
- Audio output is one device stream. `AudioOutputStart` returns true at once if
  a stream already runs (`kazarov:src/cpp/platform/audio.cpp:130-131`). The
  stream state is file-scope (`audio.cpp:13-18`).
- The mixer is a never-destroyed singleton (`kazarov:src/cpp/audio/mixer.cpp:715`).
  It has 16 ports, 16 channels and a 48-voice synth
  (`kazarov:include/audio/mixer.hpp`, class comment), and a 48 kHz rate
  (`kazarov:include/audio/synth.hpp:11`).
- The retail sound driver state is global: `CSnd` (`chronicletwo:ps2/src/mainloop.cpp:2117`),
  `PortInfo[16]` (`chronicletwo:ps2/src/snd_mngr.cpp:102`), `init_snd` and
  `PortVolf` (`chronicletwo:port/src/snd_mngr.cpp:16-17`), and the port table,
  queue and `initialised` flag (`chronicletwo:port/src/sound.cpp:75-77`).
- Game sound ports map to driver ports in `GetCSndPortNo`
  (`chronicletwo:port/src/snd_mngr.cpp:28-95`). The driver-port layout table
  sits above `sound.cpp:75`. Driver port 5 is reserved for movie audio
  (`chronicletwo:port/src/movie_port.hpp:7-8`).
- The 16 `ezBgm` stream slots are a function-local static array attached to
  the mixer once (`chronicletwo:port/src/ezbgm.cpp:56-69`). Their files
  are looked up under `<data root>/sound` (`ezbgm.cpp:119-127`).
- Movies are one set of file-scope statics (`chronicletwo:port/src/movie.cpp:24-42`).
  Their path is `<data root>/movie/<name>` (`movie.cpp:134`).
- The data index is one process-wide map (`chronicletwo:port/src/dataread.cpp:44`)
  plus a current-directory string (`dataread.cpp:47`). It is built from one
  root in `DataReadIndex` (`dataread.cpp:336-346`), called once from
  `InitCDFile` (`dataread.cpp:360`).
- The catalog is `<data root>/../port_data/catalog.json`
  (`dataread.cpp:340`). The pack folder is the sibling `datapacks/` of
  `port_data` (`chronicletwo:port/src/platform/datapacks.cpp:245`). The pack list
  is global (`datapacks.cpp:31-33`).
- The first-run gate checks `manifest.json` in the data root, and `data.json` and
  `port_data/manifest.json` in the data root's parent, plus the data version
  (`chronicletwo:port/src/platform/firstrun.cpp:22-37`). Its setup-window title is fixed to
  `Dark Chronicle — Game data` (`firstrun.cpp:58`).
- Window state: `g_identity`, `g_window`, and the event-hook vector are
  file-scope in Kazarov (`kazarov:src/cpp/platform/window.cpp:16-20`). The
  app identity goes to SDL with `SDL_SetAppMetadata`, which is process-wide
  (`window.cpp:62`).
- Clock state is one global (`kazarov:src/cpp/platform/clock.cpp:30-32`).
  `ClockSetTickCallback` replaces the single callback slot (`clock.cpp:107-109`).
- The retail memory-card manager is a file-scope pointer
  (`chronicletwo:port/src/memcard.cpp:16`) and the save catalogue is a global
  (`chronicletwo:port/src/save_slots.cpp:32-33`, `:38`).
- Shared overrides: 36 `PORT_OVERRIDE` names are defined in both ports (unverified count; a looser extraction gives 37),
  including `main`, `CSound::Init`, `CSound::SE_Play`, `CGamePad::On`,
  `CGamePad::MenuModeOn`, `InitCDFile`, `ezMidi` and `ezMidiInit`. (Found by
  comparing the `PORT_OVERRIDE` definitions in both `port/src` trees.)
- The Kazarov pin differs between the two ports. Chronicle's older pin
  (`a0a5ff8`) has a `PathsConfig` without `installed_save_default` or
  `coherent_default_root` (`kazarov@a0a5ff8:port/platform/paths.hpp:24-30`),
  and its save root has no coherent branch.

## How it works

**Startup.** `Run` calls `GameSetIdentity` first, so the prefix and path
configuration exist before any path is read (`main.cpp:251`). It then consumes
the three path flags, parses the rest, and loads `config.json` before the
data-root check, so the data root can be used before the window exists
(`main.cpp:252-272`). The window, then input (`InputInitForRun`, which picks
headless or SDL mode), then the renderer (`RendererInit`) start in that order
(`main.cpp:279-295`). The audio device is opened after the renderer
(`main.cpp:297-302`), and `AudioShutdown` is registered with `atexit`.

**Paths.** Every path call goes through `PathsDataRoot()` or
`PathsSaveRoot()`. Both are memoised; `PathsSetDataRoot` and
`PathsSetSaveRoot` clear the memo (`paths.cpp:188-196`). Consumers are:
the data index (`dataread.cpp:360`), movies (`movie.cpp:134`), the sound
folder (`ezbgm.cpp:121`), soundtrack (`soundtrack.cpp:79,111`), save slots
(`save_slots.cpp:224,288`), the memory cards (`libmc.cpp:130`), host files
(`sifdev.cpp:47`), `config.json` (`config.cpp:457,513`), `key_cap.bin`
(`gamepad.cpp:157,176`), `pipeline_cache.bin` (`main.cpp:289`), screenshots
(`mglib.cpp:1428`), glyphs (`glyphs.cpp:72`), and the font (`font.cpp:36`).

**Save layout as written.** Save-slot files go to `<save root>/saves/`
(`save_slots.cpp:288`). The save-slot test sets the save root to a temporary
folder and creates `saves/` inside it (`tests/save_slots_test.cpp:40-45`), which
matches this reading. With the default ChronicleTwo save root, slot files
therefore sit under `<app>/saves/saves/` and `config.json` sits directly in
`<app>/saves/`. This is inference from the code and the test, not a live run.

**Input.** Once per frame, `CGamePad::UpDate` reads both pads through the
retail state machine and the libpad shim, applies the stick-to-D-pad threshold
and key repeat, and advances the capture state (`gamepad.cpp:26-98`). The
`CPadControl` object for `GamePad__2` latches mouse look and menu mouse
(`padcontrol.cpp:8-19`). Kazarov turns the mouse into camera look only after
`InputLatchPad` (`input.hpp:95-98`), and the camera code reads the result
through `InputGetMouseLook` or `InputPeekMouseLookTotal`.

**Audio.** `AudioInit` either marks the mixer as tick-clocked (headless without
a WAV capture), or calls `AudioOutputStart` (`audio_init.cpp:71-94`). Headless
rendering advances the mixer from the clock pump, so `EzBgmStep` stays idle
(`ezbgm.cpp:248-255`). With a WAV capture the mixer renders on the game thread
and writes a file (`kazarov:src/cpp/platform/audio.cpp:91-114`, `:116`). A
device stream runs `Feed` on SDL's audio thread (`audio.cpp:71-89`).

**Config changes.** The options screen builds a new `Config`, calls
`DisplayApply`, which calls `ConfigChange` (`options/screen.cpp:48-49`).
`ConfigChange` re-parses the serialised form so out-of-range values are
normalised, saves, calls `DisplayChanged`, and then calls the single change hook
(`config.cpp:557-569`).

## Ixion hooks

- **Identity and prefix (one place).** `GameSetIdentity`
  (`chronicletwo:port/src/identity.cpp:7-12`) is where Ixion must choose a
  single environment prefix, a single app directory and a single window
  identity. Kazarov's `SettingsEnv` honours only the prefix set here
  (`settings.cpp:14-20`). Ixion can keep `DC2_*` and read `DC_*` names through
  its own helper, or rename both and document the change.
- **Path roots per game.** Wrap the data and save roots in one Ixion helper
  that returns a per-game subtree (for example `<save>/chronicletwo/` and
  `<save>/chronicle/`). The memo in `paths.cpp:198-242` means the choice must
  be made before first use, or the roots must be reset with `PathsSetSaveRoot`
  and `PathsSetDataRoot` at a game boundary (`paths.cpp:188-196`). That reset
  is safe only with no open file handles.
- **Data index.** `DataReadIndex` (`dataread.cpp:336-346`) builds one index from
  one root and derives `port_data` from `root.parent`. A merged index needs
  either a combined root with a per-game prefix on every key, or a change to
  `BuildIndex` so it can walk two roots. Calling it twice replaces the first
  index.
- **Datapacks.** `datapacks::Load` takes the catalog's parent
  (`dataread.cpp:344`) and replaces the global pack list (`datapacks.cpp:281`).
  Ixion needs one pack list per game, or a loader that merges packs with
  prefixed keys.
- **Save slots.** `SaveSlotsRoot` and `SaveSlotPath` (`save_slots.cpp:288-291`)
  and the prefix filter (`save_slots.cpp:294-300`) are the place to add a
  per-game folder or a per-game prefix. Chronicle's prefix is already
  distinct, so a shared folder would not confuse the listing.
- **Memory-card shims.** `CardRoot` (`libmc.cpp:130`) and the legacy scan
  (`save_slots.cpp:398`) both use `<save root>/mc<N>`. If Ixion namespaces
  saves, these two must be redirected together.
- **Config hook.** `ConfigSetChangeHook` takes one function
  (`config.cpp:571-573`). Ixion needs a dispatcher that calls both games'
  change handlers, starting with `ApplyConfigChange` (`main.cpp:233-248`).
- **Clock callback.** `ClockSetTickCallback` (`clock.cpp:107-109`) takes one
  callback. The port's `VSyncCallBack` (`main.cpp:307`) is the one registered by ChronicleTwo, so
  Ixion's dispatcher has to call both games' tick functions from it.
- **Audio device.** Own `AudioInit` and `AudioShutdown` in Ixion and call
  `AudioOutputStart` once. A second caller silently receives the first
  caller's render function (`audio.cpp:131`).
- **Mixer.** `audio::DefaultMixer()` (`mixer.cpp:715`) is the one mixer the
  sound driver, the movies and the stream channels all use. Ixion can either
  give each game its own `audio::Mixer` by making `DefaultMixer` return the
  active game's instance, or partition the driver ports. The C2 layout uses
  driver ports 0-3 and 7-15 (the driver-port table above `sound.cpp:75` and
  `snd_mngr.cpp:28-95`), movies use 5, which leaves 4 and 6 free.
- **Stream channels.** The 16 `ezBgm` slots (`ezbgm.cpp:56-69`) are attached to
  the mixer once. Two games in one mixer would share them. Ixion needs a per-game
  slot array or a different channel count.
- **Soundtrack.** The custom soundtrack mapping is keyed by original sequence
  filename (`kazarov:include/audio/soundtrack.hpp`). Ixion should prefix those
  keys by game if both games' sequence names can overlap, which is not yet
  checked.
- **Input.** Keep one `InputInit` and one `GamePad__2`. A single binding table
  suits a single control scheme; per-game bindings would need a change to the
  fixed action table (`input.cpp:51-85`). Route pad state through
  `InputSetOverride` (`input.hpp:151`) only for tests.
- **Jump and give.** `GameSetJump` and `GameSetGive` (`test_hooks.cpp:143-152`)
  and `GamePrepareJump` (`test_hooks.cpp:162-175`) use ChronicleTwo's map and
  item numbers. Ixion needs a game selector in front of these, or a crosswalk.
- **Movie.** `MoviePortPath` (`movie.cpp:134`) uses the data root. Ixion's
  per-game data root covers it, but movies play one at a time through one
  global player.

## Risks and blockers

- Single-slot globals are overwritten silently by a second setter:
  `PathsConfigure` (`paths.cpp:92`), `SettingsSetEnvPrefix` (`settings.cpp:12`),
  `WindowSetIdentity` (`window.cpp:59`), `ConfigSetChangeHook` (`config.cpp:571`),
  `ClockSetTickCallback` (`clock.cpp:107`) and `ClockSetIdleHook`.
- `AudioOutputStart` returns true early if a stream already runs
  (`audio.cpp:131`). A second game's audio start would share the first game's
  callback and its shutdown would stop both.
- 36 retail symbols are defined by both ports with `PORT_OVERRIDE` (listed in
  Key facts; unverified count), including `main`, `CSound::Init` and `InitCDFile`. These cannot
  both be linked in one binary without renaming or unit separation.
- The two Kazarov pins differ in path configuration. Chronicle's pin lacks the
  coherent and installed-save flags (`kazarov@a0a5ff8:port/platform/paths.hpp:24-30`),
  so one Kazarov version must be chosen before any path code is merged.
- Shared save-root names: `config.json`, `key_cap.bin`, `pipeline_cache.bin`,
  `glyphs/`, `imported/`, `mc0`, `mc1`, `host0/`, `saves/`, and the sibling
  `soundtrack/` folder. All are per process, so two games need either shared
  files with careful merge, or separate save roots.
- The sibling `soundtrack/` folder is derived from the save root's parent
  (`soundtrack.cpp:79`). With `--save DIR` it lands outside `DIR`, which may not
  be what the user expects.
- `config.json` is written through the fixed name `config.json.tmp`
  (`config.cpp:360`), not a unique temporary file as `FilesWrite` uses
  (`kazarov:include/platform/files.hpp`). Two processes saving at once can
  clobber each other. `key_cap.bin` is truncated in place (`gamepad.cpp:160`).
- Path-valued environment variables read through the narrow `std::getenv`
  (`settings.cpp:19`, used for `AUDIO_WAV` at `audio.cpp:139`) may be
  mangled for non-ASCII paths on Windows. This is inference from the CRT
  behaviour and has not been tested. `DC2_DATA` uses `_wgetenv`
  (`paths.cpp:36-41`), so the two behave differently.
- `data.json` in the data root's parent records the source disc's path and
  fingerprint. It must not be copied into any public artefact.
- `FirstRunRequireData` checks one data root (`firstrun.cpp:49-68`). A merged
  Ixion setup needs its own gate, or the check passes for one game and not the
  other.
- `wavetable.cpp` implements `CWaveTable::CreateTexture`, which fills a texture
  from a slope-to-intensity curve (`chronicletwo:port/src/wavetable.cpp:16-40`).
  It is not a sound module, despite the name, and it is not a platform risk.

## Open questions

- Does Chronicle's Kazarov pin (`a0a5ff8`) share the same audio, input and
  settings behaviour as the ChronicleTwo pin? This pass compared only the path
  configuration.
- Which driver ports and stream channels does Chronicle's sound code use?
  The overlap with ChronicleTwo's map (0-3, 7-15) decides whether two games
  can share one mixer. This pass did not read Chronicle's sound tables.
- Does the renderer validate `pipeline_cache.bin` against the content it was
  built for? If not, two games sharing it could load each other's cache.
- Do the two games' sequence file names overlap? That decides whether the
  soundtrack mapping can be shared without prefixing.
- Does the default ChronicleTwo save layout really nest slot files under
  `saves/saves/`? The code and the save-slot test point that way, but no live
  run was made, so this is unverified.
- Are the Ixion path flags, environment names and window title to be the
  ChronicleTwo ones, the Chronicle ones, or new names? This decides which
  saves the user can see from the existing installs.
