# ChronicleTwo port documentation digest

## What this covers

A digest of ChronicleTwo's port documentation (Dark Chronicle / Dark Cloud 2, PAL `SCES_511.90`): `docs/PC.md`, `docs/PC_PORT_PLAN.md`, `docs/port/HANDOFF.md`, `docs/port/stubs.md`, `docs/port/buildperf.md`, `docs/port/process/`, `docs/SATANSFIDDLE.md`, `docs/vu1/` and `README.md`. The aim is the port architecture and the seams Ixion could build on.

Method: every document was read. `PC.md` and `PC_PORT_PLAN.md` were read in full, with the phase work-package detail skimmed. The process folder was read selectively (wave reports, addenda, NEEDS files, the VU audit, the p2-base triage; `SCHEDULE.md` and the Kazarov patch were sampled). The VU1 specs were read for their headers, entry tables and native-replacement notes, not their listings. Claims about current code were spot-checked with read-only greps and `git show`/`ls-tree` against the ChronicleTwo checkout (branch `ixion`, which carries `master` plus Ixion design docs) and the Kazarov clone at the two pinned commits. Nothing was built or run.

Citation forms: `chronicletwo:<path>:<line>` for the ChronicleTwo tree, `kazarov:<path>` for the shared code (with the pin noted where it matters), and `chronicletwo:docs/<name>` for documents.

## Key facts

- **PAL only.** The port builds only the PAL release (`SCES_511.90`); ChronicleTwo ships only PAL. Evidence: `chronicletwo:docs/PC.md:3`, `chronicletwo:README.md` (PAL disc image in `rom/pal/`).
- **Bounded checkpoints, not a campaign.** Supported checkpoints are boot movies, title, costume selection, the opening event, Palm Brinks exploration and the first Underground Channel floor. Town and dungeon movement, item use, menus, photos and save/continue have native code and replay fixtures. Campaign completion and all sub-games are not established. Evidence: `chronicletwo:docs/PC.md:5`, `chronicletwo:docs/port/HANDOFF.md:6`.
- **Replacement, not emulation.** Every game function is either compiled from `ps2/src` unchanged or replaced by a `PORT_OVERRIDE` definition in `port/src`. No GS, VU, VIF/DMA, SPU2, IOP or scratchpad emulation. Evidence: `chronicletwo:docs/PC_PORT_PLAN.md` section 1 ("No emulation"), `chronicletwo:docs/PC.md:1-7`.
- **Units are not compiled verbatim.** The build copies each `ps2/src` unit into the build tree, strips `PORT_OVERRIDE` definitions, applies header and unit fixups, applies the long64 rewrite and appends preserved retail bridge bodies, with `#line` markers kept. Evidence: `chronicletwo:docs/PC.md:988-1011`, `chronicletwo:docs/PC.md:1019-1047`.
- **Override volume.** Grep count of `PORT_OVERRIDE` in this checkout: about 82 files under `port/src` (largest: `mglib.cpp` 41, `sound.cpp` 24, `dataread.cpp` 18, `memcard.cpp` 10). Grep counts, not an audited number. Evidence: `chronicletwo:port/src/mglib.cpp`, `chronicletwo:port/src/sound.cpp`, `chronicletwo:port/src/dataread.cpp`, `chronicletwo:port/src/memcard.cpp`.
- **Wrap, do not fork.** `RETAIL_BRIDGES` in `chronicletwo:scripts/port/unit_copy.py:41` re-emits a retail routine under a new name, so a native `PORT_OVERRIDE` can add behaviour and delegate to the retail body. Used for camera-cut seams around `ResetViewMode` and `ResetEyeView`. Evidence: `chronicletwo:docs/PC.md:1000-1011`.
- **PS2 build must stay byte-identical.** Any edit to `ps2/` requires `./build.sh ps2-pal` and `verify.py -c` to pass. Ten `ps2/` files carry port-motivated edits (`PC.md` table), plus the `inventmn.cpp` constructor handled by a unit fixup. Evidence: `chronicletwo:docs/PC.md:1196-1221`, `chronicletwo:docs/PC_PORT_PLAN.md` section 1.
- **PS2 compile path is special.** The retail build uses MWCC 3.0-011126 through Satan's Fiddle, a pinned wrapper that checks the compiler SHA-256 and applies per-translation-unit rows (helper masks, expression evaluation order, placement scheduling) to reproduce retail bytes. Evidence: `chronicletwo:docs/SATANSFIDDLE.md:1-50`, `chronicletwo:docs/SATANSFIDDLE.md:220-336`.
- **Startup order.** `Run` (`chronicletwo:port/src/main.cpp:250`) calls `GameSetIdentity` (251), `ConfigLoad` (271), `FirstRunRequireData` (272), `InputInitForRun` (280), `AudioInit` (298) and `InitCDFile` (312). `MainLoop` (`chronicletwo:port/src/mainloop.cpp:73`) runs the retail loop. Evidence: `chronicletwo:docs/PC.md:356-371`.
- **Identity is one process, one game.** `GameSetIdentity` sets the `DC2` environment prefix, directory names and window title; data root, save root and config are single roots per process. Evidence: `chronicletwo:docs/PC.md:356-358`, `chronicletwo:docs/PC.md:166-177`.
- **Threads are cooperative fibers on one OS thread.** Switches happen only in `StartThread`, `RotateThreadReadyQueue`, a blocking `WaitSema`, `SignalSema` preemption and thread exit. A switch inside `ClockPump` aborts. Evidence: `chronicletwo:docs/PC.md:722-724`, `chronicletwo:docs/PC.md:740-748`.
- **Long64 is kept, not avoided.** `long` becomes `long long` (and `L`/`UL`/`%l` forms) across the build copies, so 64-bit `unsigned long` matches the PS2 on Windows too. 87 tokens in 21 files change. Evidence: `chronicletwo:docs/PC.md:710-720`.
- **Memory is host-native and above 4 GiB.** Arenas come from Kazarov's `ArenaBlock` (`kazarov:src/cpp/platform/arena.cpp` at the ChronicleTwo pin). Each block is 64-byte aligned, guarded, and holds four times the retail quadword count (`kArenaHeadroom`). Windows images link with high-entropy ASLR so the image lies above 4 GiB. Evidence: `chronicletwo:docs/PC.md:726-738`.
- **Pointer discipline.** `uptr` replaces pointer-in-integer casts in `ps2/src`; `sptr` only where signedness matters. Parameter types and pointer-typed declarations do not change, because they feed mangled names. Disc records keep their 32-bit layout and carry `PORT_RECORD_ASSERT`. Evidence: `chronicletwo:docs/PC.md:1097-1119`, `chronicletwo:ps2/include/types.h`.
- **Truncation debt is small and tracked.** `docs/port/truncations.md`: 14 counted narrowing sites in compiled `ps2/` code (`menusys.cpp` 1, `mg_visual.cpp` 1, `movie.cpp` 12 unreachable after the movie replacement) and 18 benign sites. No open round trips in linked code. Evidence: `chronicletwo:docs/PC.md:1162-1172`, `chronicletwo:docs/port/process/wave3-report.md` (Linux gate: 47 rows, 15 owned narrowing sites, 0 open round trips).
- **Rendering is a GS-state shadow, not a GS emulator.** GS registers are tracked in `mgPortGsState` (`chronicletwo:port/src/mglib_port.hpp:86`) and translated to `gfx::DrawState` at draw time. No packet is built or sent; `SendDMA` is empty; VU programs are never uploaded. Evidence: `chronicletwo:docs/PC.md:788-800`, `chronicletwo:docs/vu1/dma_start0.md` section 8.
- **Frames are display lists.** `mgBeginFrame` (`chronicletwo:port/src/mglib.cpp:1195`) opens a `gfx` recording; `mgEndFrame` (`chronicletwo:port/src/mglib.cpp:1273`) seals it and renders one canonical image per game frame. Display frames between ticks are interpolated. Evidence: `chronicletwo:docs/PC.md:764-786`.
- **Tick rate.** Logic ticks at `game.tick_rate` (default 50). `mgFrameRate` keeps retail meaning (ticks per game frame, default 2), so the game steps at 25 game frames per second. Evidence: `chronicletwo:docs/PC.md:772`, `chronicletwo:docs/PC_PORT_PLAN.md` section 3.7.
- **Reverse-Z.** Near maps to 1, far to 0. GS Z is `depth * 1.67e7` (or `* 65000` for 16-bit Z). Evidence: `chronicletwo:docs/PC.md:802-808`.
- **Render targets are keyed by TBP0.** A GS VRAM base address selects the main target, a frame grab, or a `gfx` render target, created on first use and recreated on size or format change. Evidence: `chronicletwo:docs/PC.md:810-814`.
- **Aspect rule.** Logic stays in 512x480 logical space. `video.aspect = auto` fills the window (3D field of view follows the window); `4:3` letterboxes. Culls use `mgPortVisibleExtent()` in place of retail's 256/240 half extents. Evidence: `chronicletwo:docs/PC.md:867-877`.
- **VU1 programs are specified, then replaced natively.** The six programs (`Vu_progmain`, `My_dma_start0`, `Vu_prog0`, `Vu_prog_sdw`, `Vu_prog_3dsp`, `Vu_prog_wtr`) each have a behavioural spec under `chronicletwo:docs/vu1/` derived from disassembly. The runtime path uses Kazarov's `mesh_prog0.vert` plus float helpers in `chronicletwo:port/src/vu1/` (`vu1_math.hpp`, `sdw_geom.cpp`, `sprite3d_geom.cpp`, `water_geom.cpp`). Evidence: `chronicletwo:docs/vu1/progmain.md` header, `chronicletwo:docs/PC_PORT_PLAN.md` section 3.6.
- **Shadow volumes on master are stencil-based.** `chronicletwo:port/src/mg_shadow.cpp:160-182` uses a z-fail stencil volume (DecrementWrap/IncrementWrap, colour writes off). The older colour-counting path in the VU audit describes a branch tip, not master. Evidence: `chronicletwo:port/src/mg_shadow.cpp:166-176`, `chronicletwo:docs/port/process/vu-native-audit.md` item 3.
- **One mixer, Sony formats through Kazarov.** `CSound` (`chronicletwo:port/src/sound.cpp`) plays through `audio::DefaultMixer()` with a 48-voice synth standing in for the SPU2. Up to 16 banks per port (`MIDI_PORT_BANK_MAX`, `chronicletwo:ps2/include/sound.hpp:21`). The port layout table is `kLayout` (`sound.cpp:59`); bank upload is `SoundLoadHdBd` (`sound.cpp:396`). Evidence: `chronicletwo:docs/PC.md:879-905`.
- **Streams.** `ezBgm` drives 16 `audio::StreamChannel`s; opens read the SOUND.DAT entry extracted to `data/sound/<name>`. Voice packs under `VOICE\` and `V\` are not on the PAL disc, so their opens fail as retail's did. Evidence: `chronicletwo:docs/PC.md:907-933`.
- **Movies.** `CMovie` is overridden whole (`chronicletwo:port/src/movie.cpp:139-205`: `Load`, `Play`, `SwitchThread`, `Term`, `EndCheck`, `IsStarted`). One movie at a time, no threads. Video is MPEG-2 decoded by a minimal LGPL libavcodec and drawn by the game into the `"moviework"` texture; PCM soundtrack goes to mixer port 5. Evidence: `chronicletwo:docs/PC.md:945-969`.
- **Config.** `<save root>/config.json`, sections `game`, `video`, `audio`, `input`; comments accepted; unknown keys preserved on write (`ConfigChange` merges only changed keys). Readers are in `chronicletwo:port/src/platform/config.cpp` (`game.tick_rate` at line 196, `input.mouse_zoom` at line 285). Evidence: `chronicletwo:docs/PC.md:385-441`, `chronicletwo:docs/PC.md:435-440`.
- **Data.** `dc2data` extracts the disc to `data/` (`DATA.HD4` has 8,753 records: 8,751 files plus one duplicate, `chronicletwo:docs/PC_PORT_PLAN.md:131-132`; `InitCDFile` prints the count). Textures become RGBA PNG catalogues under `port_data/`. A `data.json` version marker gates reuse; extraction publishes in stages. Evidence: `chronicletwo:docs/PC.md:86-106`, `chronicletwo:docs/PC_PORT_PLAN.md` section 2 ("Data").
- **Datapacks.** Texture and ordinary-file replacements live in `datapacks/` beside `port_data/`, activated by `datapacks.json` `load_order`. Implementation: `chronicletwo:port/src/platform/datapacks.cpp`. Evidence: `chronicletwo:docs/PC.md:107-183`.
- **Saves are flat files.** Each save is one file `saves/BESCES-51190dkcl<N>`; legacy `mc0`/`mc1` payloads are copied in and archived; the payload is the port's host-layout `CSaveData`, explicitly not PS2 save-compatible. Evidence: `chronicletwo:docs/PC.md:184-266`.
- **Debug jump hook.** `--jump MODE[:ARG]` with `town:<map>`, `dungeon:<n>[:<floor>]`, `event:<id>`, `title`, `opening`, `menu`; `--give`; `--fast-load`. Enables debug controls. Evidence: `chronicletwo:docs/PC.md:314-340`, `chronicletwo:port/src/test_hooks.cpp:143` (`GameSetJump`), `:162` (`GamePrepareJump`).
- **Headless replay harness.** `--headless --offscreen --frames N --screenshot PATH`, input scripts (149 files under `tools/input/`), `scripts/port/run_from_save.py` for save fixtures, `scripts/port/matrix.py` for resolution and display-rate identity. Evidence: `chronicletwo:docs/PC.md:268-312`, `chronicletwo:docs/PC.md:1223-1227`.
- **Exit codes are fixed.** 0 normal, 1 SDL/window/screenshot failure, 2 usage, 3 no data, 4 game assertion. `PS2_UNIMPLEMENTED` aborts instead of exiting. Evidence: `chronicletwo:docs/PC.md:302-310`.
- **Shared-code pin.** ChronicleTwo pins Kazarov `3dc38ce`; Chronicle pins `a0a5ff8`. The two pins use different layouts: `a0a5ff8` keeps shared code under `port/` (no `src/cpp/` tree), `3dc38ce` under `src/cpp/` with `include/` headers. Both games must build green on any shared commit before either re-pins. Evidence: `kazarov:src/cpp/{gfx,audio,platform}` at `3dc38ce` (46 files); `kazarov:port/{audio,platform}` at `a0a5ff8`; `chronicletwo:docs/PC_PORT_PLAN.md` section 3.5.
- **Abort stubs.** Source counts: 2 game bodies (`port/src/gyorace.cpp:6`, `port/src/mg_visual.cpp` `GetScrPad`, unreachable) and 89 SDK bodies in Kazarov's `sce` tree. Linked binary: one direct caller, `sgLoopGyoRace`, reached from the sub-game dispatch at `chronicletwo:ps2/src/subgame.cpp:155`. Evidence: `chronicletwo:docs/port/stubs.md`, `chronicletwo:docs/PC.md:1068-1076`.
- **Hardware audit.** Of 137 grep hits for hardware addresses in the unit copies, 10 are real hardware accesses and none link. Evidence: `chronicletwo:docs/PC.md:1078-1095`.
- **Live CI.** Linux runs the full ctest with the headless smoke test on an empty data directory (`Smoke.HeadlessFramesScreenshot`), the native gate and a PIE check. Windows runs the test build and excludes `gpu`-labelled cases. Data-backed boots are a local or Windows activity. Evidence: `chronicletwo:docs/PC.md:76-84`, `chronicletwo:docs/PC.md:312`.
- **Licences are unresolved.** Neither ChronicleTwo nor Chronicle has a LICENSE file; Kazarov is MIT; the LGPL FFmpeg build must ship its notice and source offer. Evidence: `chronicletwo:docs/PC_PORT_PLAN.md` section 6 (Q12).

## How it works

### Layers

1. **`ps2/` (retail game).** `ps2/src` and `ps2/include` hold the 149 PAL units (about 261k lines) as the PS2 build compiles them. The PS2 build is `./build.sh ps2-pal` in the container. Port code does not live here, except `#ifndef PORT` guards around MWCC assembly, the `uptr`/`sptr` selection in `ps2/include/types.h`, and the `PORT_RECORD_ASSERT` hook. Evidence: `chronicletwo:docs/PC.md:971-976`, `chronicletwo:docs/PC_PORT_PLAN.md` section 2 ("Source").
2. **`port/` (native build).** `port/src` holds code only the port compiles: `main.cpp`, `identity.cpp`, `<unit>.cpp` replacements that mirror `ps2/src` units, `*_asm.cpp` for functions written in MWCC assembly, `video/` (PSS demux and MPEG-2 wrapper), `platform/` (game-specific config, datapacks, first run, input startup) and `tests/` (GoogleTest, one process per case). `port/include/stubs/<unit>.hpp` declares what each unit needs from the port. Evidence: `chronicletwo:docs/PC.md:971-976`, `chronicletwo:docs/PC_PORT_PLAN.md` section 3.1.
3. **`tools/kazarov/` (shared submodule).** Renderer (`gfx`), audio (`audio`, with mixer, stream channels, HS message decoder), game-agnostic platform (`clock`, `files`, `paths`, `window`, `input`, `arena`, `settings`), and SDK replacements (`sce`: libvu0, libpad, libmc, sifdev, sifrpc, eekernel, libcdvd, libgraph and stub families). Evidence: `chronicletwo:docs/PC_PORT_PLAN.md` section 3.1 and 3.5; `kazarov:src/cpp/` at `3dc38ce`.
4. **`tools/dc2data`** extracts the disc. Its index formats are DC2-specific (`DATA.HD4` 12-byte records, `SOUND.HD3`). Evidence: `chronicletwo:docs/PC_PORT_PLAN.md` section 3.5 (table row for `tools/dcdata` / `tools/dc2data`).

### Build and link

The root `CMakeLists.txt` picks `ps2/` or `port/` by platform. The PC build enables tests and always builds both halves: the override list and the stripped copies.

1. `port_override.py list` reads the tags in `port/src` and records the link names in `port/build/pc/port_overrides.txt`.
2. `scripts/port/unit_copy.py`, once per unit, writes a copy of each `ps2/src` unit under the build tree with overridden definitions removed, the `RETAIL_BRIDGES` bodies appended, header fixups and unit fixups applied, and long64 applied.
3. `port_override.py check` fails the build if a tagged name is defined by no `ps2/src` unit.
4. The copies compile with `PORT` defined and `port/include/port.h` force-included; `port/src` links against them with lld, `--gc-sections`, and (Windows) `--dynamicbase --high-entropy-va`.

A replacement must match the signature `ps2/src` gives it. A `static` function cannot be replaced; its non-static callers are. Fixups exist for MWCC-only constructs: `CRedMarkModel::Draw` and `CLockOnModel::Draw` return `int` so clang keeps the vtable slots; `CFuncPoint` gets a memberwise copy assignment; `ClsMes::Init` is inline in every unit; `#pragma` lines are blanked. Evidence: `chronicletwo:docs/PC.md:988-1058`.

Windows uses llvm-mingw, Ninja, SDL3, FFmpeg (LGPL shared build) and Rust for the Kazarov GUI setup window, with SHA-256 pinned archives. Measured configuration times are in `buildperf.md` (see Risks for the date caveat). Evidence: `chronicletwo:docs/PC.md:26-52`, `chronicletwo:docs/port/buildperf.md:21-37`.

### Startup and the main loop

`Run` (`port/src/main.cpp:250`) parses the `DC2_*` identity, options and `config.json`, then checks the single data root. If it is missing, a windowed run opens Kazarov's setup window to extract it; a headless run exits with status 3. It opens the window or offscreen surface, starts input, starts the renderer (`gfx::RendererInit`, 512x480 logical, pipeline cache under the save root), starts audio (`AudioInit`, device-driven or tick-driven), indexes the data root with `InitCDFile` (`port/src/dataread.cpp`), then calls `MainLoop` (`port/src/mainloop.cpp:73`). Evidence: `chronicletwo:docs/PC.md:356-371`.

`MainLoop` keeps the retail boot and mode-dispatch order. Native additions are: pointer-width alignment; mapped arenas; retained static helpers through link-name bridges; writable paths; arena high-water logging; `GamePrepareJump` (`port/src/mainloop.cpp:202`) for explicit scene jumps; the debug chord and capture/resume handling. Mode changes cut interpolation. Evidence: `chronicletwo:docs/PC.md:379-384`.

### Clock, threads and presentation

The Kazarov clock drives the logic tick (`ClockPump`). Retail thread loops (gamepad vibration, now-loading, fishing data load, movie threads) run unchanged as fibers. `WaitVSync` (`port/src/mglib_time.cpp:39`) waits the requested tick count, rotating the ready queue when a rotate priority is set. Headless runs use an unbounded clock, so output is deterministic. Evidence: `chronicletwo:docs/PC.md:740-748`, `chronicletwo:docs/PC.md:722-724`.

Each game frame becomes one recorded display list (`mgBeginFrame` to `mgEndFrame`). `mgEndFrame` queues the `mgPickZBuff` reads, renders the list once canonically (screenshots and depth queries read this image), then presents interpolated display frames until the next tick. Interpolation alpha is the elapsed fraction of the game frame. Meshes are tagged with `mgPortInterpScope` (teleport distance 200 units); skinned draws blend their 32-bone model-space palette per bone. Evidence: `chronicletwo:docs/PC.md:764-786`.

### Rendering model

- **Draw path.** Retail `mgCDrawPrim`/draw-manager calls become `mgPortDraw2D`, `mgPortDrawMesh` and `mgPortDrawMeshImmediate` in `mglib.cpp`. Sprites snap to GS texel boundaries with a 1/64-texel bias for nearest UVs (`mg_drawprim.cpp`, `AssembleSprite`). Evidence: `chronicletwo:docs/PC.md:792-797`.
- **Packets.** `mgInitVif1Packet` and `mgSetPacketBuffer` ignore their buffers; `mgVif1Packet` points at a sentinel; `mgDrawDirect` returns the sizes the draws report (0 on PC). Data buffers still back the draw manager's sort lists. Evidence: `chronicletwo:docs/PC.md:788-790`.
- **Initial GS state.** `mgPortResetGs` sets the state `My_dma_start0` leaves the GS in (ALPHA `0x44`, TEXA `0x0000008000008080`, TEX1 `0x61`, fog colour 200, SCISSOR 0..639 x 0..223). Evidence: `chronicletwo:docs/PC.md:798-800`, `chronicletwo:docs/vu1/dma_start0.md` section 8.1.
- **Shadows.** A z-fail stencil volume is built per shadow draw, then composited over the visible extent (`mgEndDrawShadow`). Evidence: `chronicletwo:port/src/mg_shadow.cpp:160-182`, `chronicletwo:docs/PC.md:826-829`.
- **Grabs and fades.** `mgSetPkMoveImage` copies or blits the main target or previous display frame into a frame target. `CFadeInOut::CaptureScreen` captures the last completed scene for crossfades. Evidence: `chronicletwo:docs/PC.md:816-825`.
- **Fonts.** Retail `mgInitFont` returns 0; the message font is the retail texture. An opt-in "sharp" ASCII painter draws existing text cells with a user-supplied TTF. Evidence: `chronicletwo:docs/PC.md:830-866`.

### Audio and movies

`CSound` (`port/src/sound.cpp`) keeps retail's command surface. `SE_Play`/`SE_SetVol`/`SE_SetPan` queue short and HS messages that `CSound::Step` delivers to `Mixer::ShortMessage` and `Mixer::HsMessage`. `ezMidi` serves scalar commands; address-carrying commands are traced and return 0. `ezBgm` (`chronicletwo:port/src/ezbgm.cpp:143`) implements the stream command table, with synchronous opens and a one-second hold on the end-of-stream state. `SetMasterVol`, `SetReverb` and `sndWaitSema`/`sndSignalSema` are adjusted or empty. Evidence: `chronicletwo:docs/PC.md:895-935`.

Movies: `CMovie::Load` maps the name to `data/movie/<name>`; `Play` binds the picture texture (`"moviework"`); `SwitchThread` and `EndCheck` advance the player against elapsed clock time, once per game frame; there are no threads. The game draws the picture itself, so its fades and letterboxes stay the game's. Evidence: `chronicletwo:docs/PC.md:945-969`, `chronicletwo:port/src/movie.cpp:139-205`.

### Input, menus, camera and settings

- **Keyboard, mouse, touchpad, gyro** feed the retail pad. Keyboard menu navigation is WASD or left-stick keys; mouse clicks become Cross/Circle presses; the wheel scrolls lists. Evidence: `chronicletwo:docs/PC.md:467-482`, `chronicletwo:docs/PC.md:483-545`.
- **Mouse menus, item drag and drop, shops and PC SETTINGS** use a shared pointer layer (`port/src/menu_mouse.cpp`) with per-menu adapters. Evidence: `chronicletwo:docs/PC.md:483-545`, `chronicletwo:docs/PC.md:607-647`.
- **Camera.** `CCameraControl::MoveCamera` (`port/src/cameracontrol.cpp`) consumes one latched mouse sample per logic update in town walking and dungeon follow modes. Fixed-camera town rooms get a separate capped look offset. Wheel zoom is opt-in. Evidence: `chronicletwo:docs/PC.md:546-595`, `chronicletwo:docs/PC.md:648-709`.
- **PC SETTINGS** changes apply immediately and write only changed keys to `config.json`. Evidence: `chronicletwo:docs/PC.md:442-466`.

### Saves and data

- **Data root resolution:** `--data`, `--run-dir` plus `/data`, `DC2_DATA`, then the per-user data directory. Evidence: `chronicletwo:docs/PC.md:164-170`.
- **Save root** resolution parallels it (`--save`, `--run-dir`, `DC2_SAVE`, per-user `saves`). Evidence: `chronicletwo:docs/PC.md:171-177`.
- **Save semantics:** the save list has no 13-file cap; New Save takes the first unused `BESCES-51190dkcl<N>` name and never replaces an occupied one; loads read and validate the full image before changing game state; writes go through `FilesWrite` (exclusive temp file, then rename). Evidence: `chronicletwo:docs/PC.md:184-266`.
- **Records** read from disc in place keep their 32-bit offsets. The inventory is `chronicletwo:docs/port/records.md` (598 `STATIC_ASSERT` structs; 65 records; 57 carry `PORT_RECORD_ASSERT`). `funcdata::name` is the one pointer-typed declaration changed, for layout reasons. Evidence: `chronicletwo:docs/PC.md:1113-1120`.

### Test and verification surface

- **Gates.** PS2 byte identity (`verify.py -c`), Linux build plus `ctest` under lavapipe, Windows build plus tests, macOS (MoltenVK), and `truncations.py --check`. Evidence: `chronicletwo:docs/PC_PORT_PLAN.md` section 5; `chronicletwo:docs/PC.md:1174-1195`.
- **Deterministic replays.** Input scripts (`tools/input/*.input`), `--display-per-tick N` (byte-identical screenshots), `--screenshot-display N`, and per-scene `--jump` presets. Evidence: `chronicletwo:docs/PC.md:314-355`, `chronicletwo:docs/PC.md:770-786`.
- **Stub inventory script.** `scripts/port/stub_inventory.py` regenerates `docs/port/stubs.md`; `--binary` adds linked callers. Evidence: `chronicletwo:docs/port/stubs.md:38-40`.

### VU1 replacement status

Per `chronicletwo:docs/vu1/*.md` and the process audit (dated 2026-10-12, about branch tips as well as master):

- `Vu_progmain` is resident. It runs `__main` on MSCAL 0 for setup, and the switchable programs enter through a dispatcher on MSCAL 2 (`docs/vu1/progmain.md`, section 1).
- `Vu_prog0` (`docs/vu1/prog0.md`, 1,058 lines) is the default face-batch program: skinning, environment UVs, four lit families, point lights, transform, clip, cull and PACKED output. Native replacement is Kazarov's `mesh_prog0.vert` with specialisation constants.
- `Vu_prog_sdw`, `Vu_prog_3dsp` and `Vu_prog_wtr` are replaced by CPU extrusion and sprite expansion into float geometry, and a water mesh with a refraction sample. Evidence: `chronicletwo:docs/PC_PORT_PLAN.md` section 3.6 table.
- Master still has one PS2-format path in the runtime: `mgCDrawPrim::Kick` (`chronicletwo:port/src/mg_drawprim.cpp:268`), reached from `Vertex4` (`:404`) and fed by `Data0`/`Data4` (`chronicletwo:port/src/mg_drawprim_asm.cpp:22`, `:27`) through `Ftoi4` and back to float. `mgCDrawPrim::Data(int*)` (`mg_drawprim.cpp:369`) does not call `Kick`; it copies to the write buffer and logs once when packed GIF data arrives. The audit lists it as class c (emulation in the runtime path). Evidence: `chronicletwo:docs/port/process/vu-native-audit.md` item 1; grep in this checkout.

## Ixion hooks

These are the seams where a second game's behaviour could enter without touching `ps2/`.

- **Scene-jump seam (`chronicletwo:port/src/test_hooks.cpp:143-200`).** `GameSetJump` and `GamePrepareJump` already turn a textual target into a loop mode and argument (`LOOP_EDIT` for towns, `LOOP_DUNGEON` for dungeons, `event:<id>` resolved through `event/view_pal.txt` under the data root, `test_hooks.cpp:41`). Ixion could add a world argument here and send a DC1 town or dungeon id through the same modes. Validation at line 185 uses `GetMapName` and `GetMapType`, which are retail DC2 tables. This is the cheapest first test of "visit any town".
- **Mode dispatch (`chronicletwo:port/src/mainloop.cpp:73` and `:202`).** `MainLoop` is the retail dispatch. A world switch or an Ixion-train transition would hook the mode change here, not in each scene. Mode changes cut interpolation (`chronicletwo:docs/PC.md:383`), so a transition should expect a presentation cut.
- **Map load (`chronicletwo:port/src/sceneload.cpp:33`, `CScene::LoadMapFromMemory` override).** The single map-load entry point. Candidate for world-aware loading (inference: a DC1 map would need its own loader here, through `RETAIL_BRIDGES` if the retail body must still run).
- **Startup (`chronicletwo:port/src/main.cpp:250-312`).** `FirstRunRequireData` (272) checks one data root and `InitCDFile` (312) indexes one. Ixion needs a second root or a namespaced index. The disc formats differ (`docs/PC_PORT_PLAN.md` section 3.5: DC1 HD2 32-byte records versus DC2 HD4 12-byte records), so a second index is a new reader, not a flag.
- **Config (`chronicletwo:port/src/platform/config.cpp:196`, `:285`).** The reader already accepts and preserves unknown keys. An Ixion section can be added without changing the existing schema (`docs/PC.md:385-441`).
- **Datapacks (`chronicletwo:port/src/platform/datapacks.cpp`, `docs/PC.md:107-183`).** Replacement by folder and `load_order`. Useful for cross-world art swaps (Chronicle textures under DC2 names) without touching data, if the names match.
- **Render seam (`chronicletwo:port/src/mglib.cpp:1195` and `:1273`, `mgPortGsState` at `chronicletwo:port/src/mglib_port.hpp:86`).** `mgBeginFrame`/`mgEndFrame` and the `DrawState` translation. A world transition can reuse the frame-target and capture primitives (`mgSetPkMoveImage`, `CFadeInOut::CaptureScreen`, `PC.md:816-825`) rather than add a renderer path.
- **Movies (`chronicletwo:port/src/movie.cpp:139-205`).** `Load`/`Play`/`EndCheck` are a complete surface for an intro or transition clip with the game's own fades. One movie at a time (inference: a second overlapping movie would need its own player).
- **Audio banks (`chronicletwo:port/src/sound.cpp:59` `kLayout`, `:396` `SoundLoadHdBd`).** Banks are registered per port with a 16-bank cap per port. Cross-world music would register DC1 banks on unused ports; the layout table is the place to see free ports.
- **Saves (`chronicletwo:port/src/memcard.cpp`, `docs/PC.md:184-266`).** A cross-world save needs a new file-name family, because the flat-save naming and legacy import rules are DC2-specific.
- **`RETAIL_BRIDGES` (`chronicletwo:scripts/port/unit_copy.py:41`).** The wrap-not-replace pattern. For any DC2 behaviour Ixion must extend without forking a retail unit.
- **Headless harness (`chronicletwo:docs/PC.md:268-312`, `tools/input/`).** `--headless --offscreen --frames N --screenshot` with a fixed input script gives a deterministic checkpoint per scene. Good for Ixion smoke tests, but data-backed runs need Windows or a local extraction.
- **Stub gate (`chronicletwo:port/src/gyorace.cpp:6`, `chronicletwo:ps2/src/subgame.cpp:155`).** The fish race is the only linked unimplemented sub-game path. Any Ixion route through it is blocked here.
- **Pointer rules (`chronicletwo:docs/PC.md:1097-1119`).** Any cross-game table that packs addresses or IDs into `int` must use `uptr` on the DC1 side too; `scripts/port/truncations.py` is the audit to copy.

## Risks and blockers

- **Byte identity on `ps2/`.** Any Ixion change to `ps2/src` must pass `verify.py -c` against the PAL disc, and `ps2/` is built through Satan's Fiddle with per-unit calibration rows. A change that is not byte-neutral needs a documented row (`chronicletwo:docs/SATANSFIDDLE.md:220-336`). The cheap path is `port/src` overrides and `RETAIL_BRIDGES`.
- **Two Kazarov pins with different layouts.** ChronicleTwo is at `3dc38ce` (`src/cpp/`); Chronicle is at `a0a5ff8` (older `port/` layout). A merged Ixion build needs one pin that both build green on (`docs/PC_PORT_PLAN.md` section 3.5). Inference: the file-level diff between the two layouts was not compared.
- **Pointer width across two games.** Arenas sit above 4 GiB. Any shared 32-bit ID or pointer-in-int will truncate on PC. The DC2 `uptr` policy is written; the DC1 side uses the same audit script, but its table was not read here.
- **Campaign coverage.** `HANDOFF.md` says campaign completion and sub-games are not established. Ixion's "play any character" premise assumes coverage the port has not claimed.
- **Fish race abort.** `sgLoopGyoRace` aborts through `PS2_UNIMPLEMENTED`. Reachability from campaign content is not stated in the docs.
- **Single-process identity.** The `DC2` env prefix, `chronicletwo` app id, window title and per-user data and save directories are all DC2 names (`docs/PC.md:356-358`). A merged build must choose one identity and rename the other's variables; `kazarov` identity is a parameter (`PC_PORT_PLAN.md` section 3.4).
- **Packed GS path still in runtime code.** `mgCDrawPrim::Kick` (`mg_drawprim.cpp:268`, reached from `Vertex4`) keeps a 12.4-fixed-point round trip alive on master (the fixed-point format is unverified). This is the class-c item in the VU audit. Ixion should not add more packed-format helpers to the runtime path.
- **Stale or misdated documents.**
  - `docs/PC_PORT_PLAN.md` section 2 says the port stops at "Confirm Max's costume?"; `PC.md` and `HANDOFF.md` describe later checkpoints. Use `PC.md` and `HANDOFF.md` as current.
  - `docs/port/HANDOFF.md` is 12 lines and points to `PC.md` and the process folder. The wave3 report and the plan refer to a "HANDOFF section 4" that no longer exists.
  - `docs/port/buildperf.md` says it was measured "on 2026-10-14", a date after today's. Treat its numbers as unverified.
  - The VU audit (2026-10-12) describes branch tips, not master, except where it says so.
- **Personal paths in the process docs.** The `docs/port/process/` folder and `PC_PORT_PLAN.md` contain local absolute paths and an account name (27 matches in 8 files, found by grep). The ChronicleTwo repo is public-facing; Ixion should not copy those lines, and its own docs must not add them.
- **Licences.** Neither ChronicleTwo nor Chronicle has a LICENSE file. The LGPL FFmpeg build (`avcodec`, `avutil`) needs its notice and source offer with any shipped binary (`PC_PORT_PLAN.md` section 6, Q12).
- **Movie player is a minimal FFmpeg build.** Only `mpeg2video` plus the `mpegvideo` parser are compiled; the Windows DLL names (`avcodec-61`, `avutil-59`) are pinned to FFmpeg 7.1 (`PC_PORT_PLAN.md` section 6).
- **Data-backed checks are not in CI.** CI runs the smoke test on an empty data directory. Junctions do not resolve inside the Linux container (`process/ADDENDUM-W0.md`), so data-dependent checks run on Windows or in the main checkout.
- **Render targets keyed by VRAM address.** Targets are keyed by TBP0 (`PC.md:810-814`). Two games loaded in one process would need distinct key spaces, or texture collisions are possible (inference from the keying; not tested).

## Open questions

- Which shared Kazarov commit should a merged Ixion build pin, and does it build both games green? The pins use different layouts, and neither doc answers this.
- How will DC1's `DATA.HD4`-equivalent (32-byte records) be indexed next to DC2's 12-byte index? Is a second `dataread` index planned, or a namespace?
- Is the fish race reachable from any campaign path Ixion would open, or only from sub-game menus?
- Does `chronicletwo:docs/port/process/SCHEDULE.md` (619 lines, binding briefs) still describe the current gating, or was it superseded by `PC.md` and `HANDOFF.md`?
- The wave3 report counts 14 `Ps2Unimplemented` callers (9 game, 5 SDK) while `stubs.md` counts 2 game bodies and 89 SDK bodies. These are different metrics (callers versus bodies); which one is current at the pin?
- Is the `docs/port/headless-replays.md` mixer-ownership contract (referenced by `HANDOFF.md`) a prerequisite for any cross-game audio test? Not read in this digest.
- The packed `Data`/`Kick` path (`mg_drawprim.cpp:268`) is listed as the one remaining class-c item. Is it scheduled for removal, and does `scripts/port/native_gate.py` detect it in the linked binary? The gate's regex was not checked against `nm`.
- Does `Smoke.HeadlessFramesScreenshot` run in the Linux CI job exactly as `PC.md:312` describes, and does any job boot the real PAL data (the process docs ask for this under WP7.6)? The workflow file was not read.
