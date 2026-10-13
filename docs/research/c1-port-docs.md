# Chronicle (DC1) port documentation digest

## What this covers

A digest of Chronicle's own port documentation: `docs/PC.md` (the reference for the
built PC port), `docs/PC_PORT_PLAN.md` and `docs/DECOUPLING_PLAN.md` (plans, some now
superseded), `docs/MACOS_PLAN.md`, `docs/WINDOWS.md`, `docs/PAL.md` and `README.md`. Doc
claims were spot-checked against the Chronicle tree at master 3bc16763, and the Kazarov
pins were read-only through the Kazarov clone (`git show` and `ls-tree` only). Scope is architecture,
decoupling from PS2 assumptions, modularity and running parts in isolation, since those
are what an Ixion merge would build on. Ixion is a proof of concept that joins Chronicle
(Dark Cloud) and ChronicleTwo (Dark Chronicle) in one game; this note covers only the
DC1 side.

## Key facts

- The PC port is the game's own code in `ps2/src`, kept as the PS2 build compiles it
  (only corrections that leave both PS2 builds byte-identical; chronicle:docs/PC.md:1657,
  1849-1866), compiled with clang as C++26 and linked with a replacement layer. The port defines PAL, not PAL_TIMING.
  (chronicle:port/CMakeLists.txt, `PORT_DEFINITIONS`; chronicle:ps2/CMakeLists.txt:51
  defines `PAL_TIMING` only for the PS2 PAL build.)
- Replacement is by tag only. A definition in `port/src` marked `PORT_OVERRIDE`
  replaces the same-named definition in `ps2/src`; `ps2/src` carries no mark. The
  `port_override.py` script lists tags, strips matching definitions into a copy of each
  unit, and checks every tag names a real definition.
  (chronicle:docs/PC.md:1677-1738; chronicle:port/include/port.h, `PORT_OVERRIDE`.)
- `static` functions cannot be replaced; a non-static caller must be replaced instead.
  Definitions in a class body, namespace or header cannot be replaced either.
  (chronicle:docs/PC.md:1677-1738.)
- The single executable links three object libraries: `dc_ps2` (the stripped `ps2/src`
  copies), `dc_port` (`port/src`), and `dc_host` (Kazarov's host layer). The test binary
  `darkcloud_tests` links the same set. (chronicle:port/CMakeLists.txt:121, 176, 212-219,
  222; chronicle:port/src/tests/CMakeLists.txt:1-3, 17.)
- Chronicle's tree pins `tools/kazarov` at a0a5ff8 (gitlink, checked with `git ls-tree`).
  At that pin Kazarov has a top-level `port/` tree (gfx, audio, platform, sce, 122 files).
  At ChronicleTwo's pin 3dc38ce the layout is `src/cpp` and `src/rust`, so the paths
  PC.md cites (`tools/kazarov/port/...`) do not exist there. (kazarov@a0a5ff8:port/;
  kazarov@3dc38ce:src/cpp/.)
- The host side (window, input, clock, audio output, config file IO, arenas, the
  renderer `gfx`) lives in Kazarov, and `port/src/platform/` keeps only game-specific
  pieces: config, discord, firstrun, save_state. (chronicle:docs/PC.md:846-848; the
  directory listing of `port/src/platform/`.)
- `PC_PORT_PLAN.md` section 4.1 describes a layout (`port/src/gfx/`, `port/src/sce/`,
  `port/src/audio/`, `port/src/platform/window.*`) that no longer exists in the tree. That
  plan is historical; PC.md is the current reference. (chronicle:docs/PC_PORT_PLAN.md:121-158;
  chronicle:port/src/ listing.)
- The frame rate is inconsistent across the docs. The code default is 60 ticks
  (`game.tick_rate`), and PC.md says the port runs 60 and leaves out `PAL_TIMING`. The
  plans still say 50 Hz. (chronicle:docs/PC.md:3-7, 122; chronicle:port/src/tests/platform_config_test.cpp:18;
  chronicle:docs/PC_PORT_PLAN.md:31, 452; chronicle:docs/DECOUPLING_PLAN.md:146.)
- Frame and tick are decoupled. Game logic runs at a fixed tick; each tick's draws are
  recorded as a display list, rendered once as the canonical image, and display frames
  are interpolated between the last two lists. (chronicle:docs/PC.md:748-792; the plan
  is chronicle:docs/DECOUPLING_PLAN.md:84-170, marked done for the aspect work
  at line 190 of that file.)
- Pointer truncation is fixed for linked code. The audit `scripts/port/truncations.py`
  reports zero round-trip sites that can run, and the executable is PIE with arenas
  above 4 GiB. (chronicle:docs/port/truncations.md:30-45; chronicle:docs/PC.md:1499-1538.)
- The arena allocator gives each arena its own mapping sized at four times retail's
  request (`kArenaHeadroom`), a stopgap. It is shared with Dark Chronicle through Kazarov.
  (chronicle:docs/PC.md:1474-1498.)
- Overlays are not reloaded. `TITLE.BIN` and `DUN.BIN` are linked once; `LoadOverlay`
  only rebuilds the title objects the port defines with host classes. Other globals keep
  the previous visit's values. This is a listed known gap. (chronicle:port/src/runtime.cpp:54;
  chronicle:docs/PC.md:835-838, 1575-1596.)
- Mode and map dispatch: `GameFollowMapJump` maps `NextMapNo` to a mode: under 200 is
  `GAME_MODE_EDIT` (towns and sub maps), 200 to 299 is `GAME_MODE_DUNGEON`, 400 is
  opening, 800 and up is title or the attract movie, and 1000 is the ending save.
  (chronicle:port/src/gameloop.cpp:409-445.)
- Test seams already exist for starting in a mode: `GameSetJump` accepts `edit[:map]`,
  `dungeon[:n]`, `title`, `rush`, `opening` and `menu`; `GameSetGive` grants items;
  `GameSetFastLoad` shortens loading holds. Each is exposed as a CLI flag. (chronicle:port/src/gameloop.hpp:29-41;
  chronicle:docs/PC.md:544-567.)
- Scripted input replaces the pads through `InputSetOverride` and a per-frame text
  script. (chronicle:docs/PC.md:502-527.)
- Saves: retail's 0x136A7-byte card image is kept as `saves/<N>/save.dat`, with a
  `state.json` for `last_save` and `game_clear`. Writes are atomic (temporary file,
  flush, rename). (chronicle:docs/PC.md:1115-1262.)
- Data: `tools/dcdata` extracts `DATA.DAT` and `DATA.HD2` into a lowercase directory tree
  under `data/`. `port/src/dataread.cpp` replaces the file API (`InitCDFile`, `LoadFile`,
  `LoadFile2`, `LoadFileBG`, `ReadBG`, `WriteFile`, `GetPackFile`) on top of a
  case-folded index. (chronicle:port/src/dataread.cpp:118, 155, 164, 229, 276, 290, 314;
  chronicle:docs/PC.md:1907-1958.)
- Localization: the extractor writes `languages.json` from a fingerprint of `DATA.HD2`,
  with per-release language sets (NTSC 1.02 has English only; the July 2001 PAL prototype
  has five). (chronicle:docs/PC.md:60-82; chronicle:docs/PAL.md, "Languages".)
- Platform support: Linux x64 (Flatpak packaging), Windows x64 with llvm-mingw clang (the
  pinned toolchain is Clang/lld 23.1.2; PC_PORT_PLAN asks for clang 20 or newer), and arm64
  macOS as a plan. Windows
  runs bounded offscreen tests only; interactive play is not qualified there.
  (chronicle:docs/WINDOWS.md:7-22, 149-159; chronicle:docs/MACOS_PLAN.md:1-84.)
- Floating point is pinned: `-ffp-contract=off` on every port target (`dc_options`), and
  `-ftrivial-auto-var-init=zero`, `-fno-strict-return`, `-fno-strict-aliasing`, `-fwrapv` on
  `dc_ps2` (the `ps2/src` copies) only. (chronicle:port/CMakeLists.txt:115, 127-128;
  chronicle:docs/PC.md:1849-1900.)
- Stubs: `libdma`, `libgraph` (except `sceGsSyncV`) and `libpkt` are `PS2_UNIMPLEMENTED`
  aborts. PC.md reports that none of the 44 aborting stub functions is linked into
  `darkcloud` (checked by disassembly) (unverified: the disassembly run was not repeated).
  (chronicle:docs/PC.md:1539-1574, 1562-1565.)
- Discord Rich Presence is built in and reads a fixed application id and per-character
  asset names. (chronicle:docs/PC.md:190-196; chronicle:port/src/platform/discord.hpp:14.
  The client id is confirmed; the asset names are not checked (unverified).)

## How it works

**Build composition.** `ps2/src` is the game as the PS2 build compiles it, 136 `.cpp`
files including `dun/` and `title/`. The port's CMake copies each unit into the build
directory with the `PORT_OVERRIDE` definitions removed (and the per-unit header under
`port/include/stubs/` included first when one exists), checks the tags, then compiles
the copies with `PORT` and `PAL` defined. `port/src` is compiled alongside, and the
executable is `darkcloud`, linked PIE with `--gc-sections`. The PS2 build remains
byte-identical: edits to `ps2/src` that help clang must keep both PS2 regions matching
(chronicle:docs/PC.md:1849-1900).

**Start-up and the main loop.** `main` in `port/src/main.cpp` parses options, loads
`config.json`, opens the window, initialises the renderer and audio, and starts
`RunGame` (`port/src/gameloop.cpp`). `RunGame` is retail's `main` with the hardware
removed: `init_all` is reduced to a few calls, `sceGsSyncV` waits become `ClockSyncV`,
and the per-mode `Init`/`Loop` structure is kept. Mode transitions are factored into
`GameApplyLoopResult` and `GameFollowMapJump`, which the tests call directly
(chronicle:docs/PC.md:693-745).

**Modes.** The mode enum is in `ps2/include/main.hpp` (TITLE 0, RUSH_MOVIE 1, EDIT 2,
DUNGEON 3, OPENING 5, MENU 7, LOADER 9, MEMORY_CHECK 10, TRIAL_END 11, SAVE 13,
LANGUAGE 14; several values are unused). The port's `LoadOverlay` maps modes to two
overlay groups, title and dungeon, and only the title group is reconstructed.

**Tick and presentation.** `MGBeginFrame` starts recording; `MGEndFrame` seals the list,
`GameRenderTick` renders it, then `GamePresentBetweenTicks` interpolates display frames
between the last two lists. Per-object identity is the `CFrame` pointer, and the camera
is interpolated; 2D is not (chronicle:docs/PC.md:748-792; chronicle:port/src/gameloop.cpp:694, 712).
Display frames are never written back as canonical images, so previous-frame effects
(the title trail, water, depth of field) are tick-exact.

**Clock.** `platform/clock` (in Kazarov) is the stand-in for the VSync interrupt. A
tick is one VSync; `ClockPump` runs the game's tick callback and the host's pump hooks;
every spin-wait in the retail code calls it. Input and window events are pumped from
the same place (chronicle:docs/PC.md:846-892).

**Config.** `config.json` has sections `game`, `video`, `audio`, `input` and `discord`,
with defaults and comments documented in PC.md. Unknown keys and bad values are reported
and ignored; the file is rewritten atomically when the Options screen changes a setting,
and hooks apply each section (`ConfigAddChangeHook`) (chronicle:docs/PC.md:108-118,
119-186, 225-265).

**Saves and host files.** `port/src/memorycardaccess.cpp` replaces `CMemoryCardAccess`
with direct file reads and writes; `port/src/save_slots.cpp` enumerates `saves/<N>/`;
`port/src/platform/save_state.cpp` writes `state.json`. The memory card itself is
never reached; the card checks always pass (chronicle:docs/PC.md:1115-1262).

**Arenas and allocation.** `CDataAlloc2<1>` and the carving functions in `dataset.cpp`
and `dataalloc2_1.cpp` give each arena a host allocation. The placement operators grow
the run they are handed to the host object's size, so nothing lands under a tail
(chronicle:docs/PC.md:1474-1498).

**Pointers.** Retail round trips through `int` are widened per function, each replaced
by a copy of the retail body with the cast fixed; records read from disc with pointer
fields are decoded into host structs (`eparts_port.cpp`, `runscript.cpp`)
(chronicle:docs/PC.md:1499-1538; chronicle:docs/port/truncations.md:30-45).

**Per-unit adjustments.** `port/include/stubs/<unit>.hpp` is included before the unit
and declares what the port defines or renames; `ps2/config/pal/object_fixups.json`
records the PS2 link's renames, which the port reproduces with `#define`, forwarders and
`linknames.cpp` (chronicle:docs/PC.md:1739-1837).

**Tests.** `darkcloud_tests` is GoogleTest, one process per case, linking the whole
game. Several cases drive the game loop through the globals: `integration_gameloop_test.cpp`
sets `mode`, `MapNo`, `NextMapNo` and calls the transition functions directly
(chronicle:port/src/tests/integration_gameloop_test.cpp:1-30).

**Plan status.** `PC_PORT_PLAN.md` waves 1 to 3 and P10 are marked landed. The
DECOUPLING plan's Part A (64-bit) and B.3.1 (display lists) are implemented as described
in PC.md, though the plan's own status lines are not updated. The MACOS plan is a
plan; its KosmicKrisp facts are marked verified or pending.

## Ixion hooks

- **`port/src/gameloop.cpp` `GameFollowMapJump` and `GameSetJump`.** The natural seam
  for "visit any town or dungeon": an Ixion mode could set `NextMapNo` (or call
  `GameSetJump`) with a DC1 map number, and let the existing mode loop run the town
  or dungeon. Map numbers 0 to 4 are DC1's towns and 200 to 206 are its dungeons; DC2's
  numbering would have to be mapped separately (inference from the number ranges).
- **`port/src/gameloop.cpp` `GameApplyLoopResult`.** The per-mode result handler is where a
  DC1 loop would signal a transition to the other world; this is the same place retail
  handles `mode` changes.
- **`port/src/runtime.cpp` `LoadOverlay`.** The only place overlay state is tracked. An
  Ixion world switch would need to reset the title and dungeon statics it depends on;
  the existing `TitleOverlayConstruct` path is a template for that (inference).
- **`port/src/gameloop.cpp` `GameRenderTick` and `GamePresentBetweenTicks`.** The display
  list is a natural place to composite a second world's list for a transition effect,
  or to hold the last canonical image across a world switch so the previous-frame
  effects stay continuous. Inference: both are untested for cross-world use.
- **`port/src/dataread.cpp` `LoadFile2` and `LoadFileBG`.** The single file-read
  seam for DC1 data. A layered lookup (DC1 root, then a DC2 root under a prefix) fits
  here, and the case-folded index is built in `InitCDFile` (chronicle:port/src/dataread.cpp:118).
- **Kazarov `port/platform/paths.cpp` (at a0a5ff8).** The data-root search order
  (`--data`, `DC_DATA`, `./data`, beside the executable, XDG) is where a second root for
  DC2 data would be added (chronicle:docs/PC.md:1907-1958).
- **`port/src/platform/config.cpp` and `port/src/memorycardaccess.cpp` / `save_slots.cpp`.**
  Config sections and save folders are the two persistence seams. Ixion's shared save
  would sit beside `saves/<N>/` (inference).
- **`port/CMakeLists.txt` `dc_ps2` and `dc_link_game`.** Where two game trees would be
  combined into one link. Units share file names across the two trees (both have
  `ps2/src/main.cpp` and `ps2/src/dataread.cpp`), so copy paths under `ps2_src/<unit>`
  collide (inference from the build rule at `port/CMakeLists.txt:69-78`).
- **`port/src/tests/CMakeLists.txt`.** The test target is the place for a cross-world
  integration test that starts a town and a dungeon in one process.
- **`--jump`, `--give`, `--frames`, `--screenshot` and `--input`.** These are already
  the headless harness for a scripted cross-world walkthrough. They work without a window.
- **`port/include/stubs/<unit>.hpp`.** The per-unit rename mechanism is how a second
  game's clashing names could be renamed without editing either tree.

## Risks and blockers

- **Tick rate.** Code runs at 60 ticks with PAL-timed data and `PAL_TIMING` code
  left out; the plans say 50. Any cross-world timing (time travel, Ixion's train) must
  pick one rate for both games (chronicle:docs/PC.md:3-7; chronicle:ps2/CMakeLists.txt:51).
- **Symbol collisions in one binary.** Both games use MWCC-era global names and
  identically named units. Combining them needs namespacing or separate link units.
  `PORT_OVERRIDE` matches names by signature, so a tag meant for one game would replace
  the other's definition if both were in one strip step (inference from
  `port_override.py` behaviour, chronicle:docs/PC.md:1677-1738).
- **Kazarov pin skew.** The two games pin Kazarov at incompatible layouts (a0a5ff8 `port/`
  versus 3dc38ce `src/cpp`). The DC1 docs cite `tools/kazarov/port/...` paths that do
  not exist at the newer pin. Ixion needs one Kazarov version, and it must build both
  games.
- **Overlay globals.** Retail re-ran overlay constructors on each switch; the port does
  not. Anything in DC1's title or dungeon that expects fresh statics after a world
  switch will carry stale values (chronicle:docs/PC.md:1575-1596).
- **Static functions cannot be replaced.** If Ixion needs to change behaviour inside a
  `static` helper, the non-static caller must be replaced instead, which copies more retail
  code (chronicle:docs/PC.md:1677-1738).
- **Arena headroom.** Four times retail's request is a stopgap and has not been measured
  against peak use; a combined heap would need its own measurement (chronicle:docs/PC.md:1474-1498).
- **Stub aborts.** Any DC2 path that reaches `libgraph`, `libdma` or `libpkt` (other than
  `sceGsSyncV`) will abort, so the ChronicleTwo renderer path must not depend on those
  calls (chronicle:docs/PC.md:1539-1574).
- **Save format.** The DC1 save is a fixed 0x136A7 image with checksums; Ixion must keep
  DC1 saves intact and cannot reuse the folder names without a separate namespace.
- **Plans are out of date.** `PC_PORT_PLAN.md` section 4.1 layout and the default tick rate
  are stale; relying on them would mislead an integration.
- **Discord.** Rich Presence uses Chronicle's application id and character assets; Ixion
  should not reuse that identity.

## Open questions

- Does Kazarov's newer layout (3dc38ce `src/cpp`) carry the same `gfx`, `platform`, `clock`
  and `arena` APIs that Chronicle's replacement units call? (Not checked; needs the newer
  Kazarov's headers compared against chronicle:port/src/platform users.)
- What is the target tick rate for Ixion's time system: 60 (current code) or 50 (plans)?
- Does Chronicle's `PAL_TIMING` exclusion change any gameplay values a cross-world route
  would depend on (fades, timers, animation speed)? PAL.md lists the changes; PC.md says
  they are left out of the port.
- How is `MapNo` numbering shared between DC1 and DC2 scripts? Chronicle's numbering
  (0 to 4 towns, 11+ sub maps, 200+ dungeons, 800+ title) must not collide with DC2's.
- Are `PORT_OVERRIDE` tags scoped per unit name, or only per signature? That decides
  whether two games can share one strip step.
- Does the headless harness (`--headless`, `--jump`, `--frames`) run on the Windows
  build? WINDOWS.md says offscreen runs are checked; interactive and audible output are not.
