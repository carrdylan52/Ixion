# Kazarov build system and the version split

## What this covers

How the shared build system Kazarov is organised at the two pins the games use, what changed between them, and what a single CMake superbuild that compiles both games would have to resolve. Covers the CMake modules, the `scripts/kazarov` driver and each game's `kazarov.conf` contract, the shared host port library, disc extraction, the Rust data publisher and `data_version.json`, and the container image. Game code is out of scope except where a build rule touches it. Read-only survey: nothing was configured, built or run. Inference is labelled "[inference]".

Citation keys: `kazarov:` is Kazarov main at 9310c53 unless a commit is named (`kazarov@a0a5ff8:` is the older layout Chronicle pins). `chronicle:` is the DC1 repository at master 3bc16763. `chronicletwo:` is the DC2 repository, branch `ixion`.

## Key facts

- Pins. Chronicle records Kazarov at a0a5ff8 (gitlink in its tree). ChronicleTwo records 3dc38ce. The 3dc38ce commit is not an ancestor of main 9310c53 (merge base a393a0b), but `git diff --stat 3dc38ce 9310c53` is empty, so the two trees are identical. Treat "the new layout" as that one tree. [kazarov git history; chronicle and chronicletwo gitlinks]
- Size of the split. `git diff --stat a0a5ff8 9310c53` covers 206 files (+13407/-1916). The line count is dominated by new code and data: `Cargo.lock` (3466 lines), the new Rust sources (`src/rust/textures.rs` 1502 lines, `archive.rs` 917) and new test files. The moves are listed in the table under How it works.
- Entry point. The old include is `cmake/Kazarov.cmake`, which sets `KZ_ROOT` to the parent of its own directory (`kazarov@a0a5ff8:cmake/Kazarov.cmake:12`). The new entry is a root `CMakeLists.txt` that sets `KZ_ROOT` to its own directory (`kazarov:CMakeLists.txt:17`) and calls `project(kazarov NONE)` only when it is the top-level source (`kazarov:CMakeLists.txt:2-4`).
- Consumers are split on that entry point. Chronicle still includes the old file (`chronicle:ps2/CMakeLists.txt:46`); the file does not exist on main (`git cat-file -e 9310c53:cmake/Kazarov.cmake` fails). ChronicleTwo includes the new one (`chronicletwo:ps2/CMakeLists.txt:69`).
- Variables renamed or removed. `KZ_BIN` is gone and `KZ_BUILD_SCRIPTS` replaces it (`kazarov:cmake/KazarovToolchain.cmake:5`). `KZ_PYTHONPATH` now points at `scripts/`, not `python/` (`kazarov:cmake/KazarovToolchain.cmake:7`; old value in `kazarov@a0a5ff8:cmake/KazarovToolchain.cmake`). `kazarov:README.md:160` still lists `KZ_BIN` as set by the include, so the README is stale there.
- Chronicle's consumer files still name old paths. Its `kazarov.conf` calls `$KZ_ROOT/bin/kz-lock` and `$KZ_ROOT/bin/kz-cached` (`chronicle:kazarov.conf:119,123,126,128`). Its wrapper runs `tools/kazarov/bin/kazarov` (`chronicle:build.sh`). Its port CMake sets `PORT_OVERRIDE_SCRIPT` to `${KZ_ROOT}/scripts/port_override.py` (`chronicle:port/CMakeLists.txt:54`), which main has moved to `scripts/build/` (rename at 86% similarity). ChronicleTwo uses the new paths (`chronicletwo:kazarov.conf:126-146`, `chronicletwo:port/CMakeLists.txt:93`).
- Host library. `KZ_PORT_ROOT` is now `src/cpp/` and the include root is `include/` (`kazarov:cmake/KazarovPort.cmake:10-11,29-30`). The library gained a `KZ_PORT_BUILD_TIM2` option, default ON (`kazarov:cmake/KazarovPort.cmake:96-99`), and `-ffp-contract=off` on the host objects (`kazarov:cmake/KazarovPort.cmake:110`). Chronicle does not set the TIM2 option, so it gets the new default.
- ChronicleTwo forces the TIM2 option off in the cache: `set(KZ_PORT_BUILD_TIM2 OFF CACHE BOOL ... FORCE)` (`chronicletwo:port/CMakeLists.txt:39`). A FORCEd cache entry is one value for the whole configure.
- Shared tests. `kz_port_tests` globs `src/cpp/tests/*_test.cpp` into any consumer test executable (`kazarov:cmake/KazarovPort.cmake:134`). That set includes `gfx_tim2_test.cpp`, which uses `gfx/tim2.hpp` (`kazarov:src/cpp/tests/gfx_tim2_test.cpp:14`). ChronicleTwo's test executable adds `tim2.cpp` by hand (`chronicletwo:port/src/tests/CMakeLists.txt:22`) because its host library drops it. Chronicle's test executable does not add it.
- Shared SDK replacements. Both games compile the same `sce/` replacement sources from Kazarov, Chronicle with a shorter family list (`chronicle:port/CMakeLists.txt:175`) and ChronicleTwo with a longer one (`chronicletwo:port/CMakeLists.txt:194-195`). Both also compile their own copy of the host library (`chronicle:port/CMakeLists.txt:35`, `chronicletwo:port/CMakeLists.txt:42`).
- Rust publisher. It is new and opt-in. Corrosion v0.6.1 is fetched by URL and SHA-256 (`kazarov:cmake/KazarovRust.cmake:12-15`). The crate `kazarov_core` builds as `staticlib` and `rlib` (`kazarov:Cargo.toml:9`). The toolchain is pinned to 1.99.0 (`kazarov:rust-toolchain.toml:2`). The cxx bridge namespace is `kazarov` (`kazarov:src/rust/lib.rs:4`). Only ChronicleTwo includes it, through its `dc2data` target (`chronicletwo:tools/dc2data/CMakeLists.txt:2`).
- `data_version.json` is `{"schema_version":1,"data_version":3}` (`kazarov:data_version.json`). Three readers use it: CMake generates `kazarov/data_version.hpp` from a template (`chronicletwo:port/CMakeLists.txt:26-34`, `kazarov:include/kazarov/data_version.hpp.in:4`); Rust reads it with `include_str!` (`kazarov:src/rust/core.rs:39`); the Python texture tool reads it (`kazarov:scripts/kazarov_textures.py:277-282`). ChronicleTwo's first-run check compares a marker against `KAZAROV_DATA_VERSION` (`chronicletwo:port/src/platform/firstrun.cpp:36`). Chronicle has no reference to it.
- Extraction is split. The disc-to-files extractor `kz-extract` is byte-identical between the pins (rename at 100%). Both games call it through `kz_disc_setup` (`kazarov:cmake/KazarovSetup.cmake:54`; `chronicle:ps2/CMakeLists.txt:128`; `chronicletwo:ps2/CMakeLists.txt:127`). The game-data extraction is not shared: Chronicle builds its own C++ `dcdata` (`chronicle:tools/dcdata/CMakeLists.txt:4`), and ChronicleTwo builds the Rust-backed `dc2data` (`chronicletwo:tools/dc2data/CMakeLists.txt:4`).
- Global target names collide between the two PS2 trees. Both call `kz_disc_setup` and `kz_ctx`, which create `extract`, `setup`, `disassemble` and `ctx` (`kazarov:cmake/KazarovSetup.cmake:62,102,104`; `kazarov:cmake/KazarovContext.cmake:38`). Both also define `elf`, `iso`, `objdiff` and `verify_extracted` (`chronicle:ps2/CMakeLists.txt:250,380,386,423`; `chronicletwo:ps2/CMakeLists.txt:253,270,292-294`; `chronicletwo:ps2/cmake/Objdiff.cmake:100`). ChronicleTwo also defines `build` and `ps2_include`; Chronicle defines `provenance`, `dc_lang` and `dc_glyphs`.
- Port target names already avoid each other. Chronicle uses the `dc_` prefix (`dc_options`, `dc_host`, `dc_port`, `dc_ps2`, `chronicle:port/CMakeLists.txt:105,35,176,121`). ChronicleTwo uses `ct_` (`chronicletwo:port/CMakeLists.txt:150,42,196,171`). The executables differ (`darkcloud`, `darkchronicle`), and so do the tools (`dcdata`, `dc2data`).
- Kazarov's own names are global by design. `kz_port_headers`, `kazarov_core`, `kazarov_bridge`, `kz::ffmpeg` and the Windows runtime helpers are created once and guarded (`kazarov:cmake/KazarovPort.cmake:28-31`, `kazarov:cmake/KazarovRust.cmake:2`, `kazarov:cmake/KazarovFfmpeg.cmake:5,73`).
- `include_guard(GLOBAL)` is on four modules: `KazarovPort.cmake:8`, `KazarovRust.cmake:2`, `KazarovFfmpeg.cmake:5`, `KazarovWindowsRuntime.cmake:2`. The toolchain, objects, setup, context and overlay modules have no guard (`kazarov:cmake/*.cmake`).
- Game-provided hooks are per process. The host library expects the game to define `SettingsGet`, `SettingsChange`, `PathsConfigure` and `WindowSetIdentity` (`kazarov:README.md`, "The game provides", lines 271-274; the header comment at `kazarov:cmake/KazarovPort.cmake:5-6` names only the first two). Chronicle sets its identity to `chronicle`, `DC_DATA`, `DC_SAVE` (`chronicle:port/src/identity.cpp:10-11`). ChronicleTwo uses `chronicletwo`, `DC2_DATA`, `DC2_SAVE` (`chronicletwo:port/src/identity.cpp:9-11`). Their settings live in `port/src/platform/config.cpp` (`chronicle:...:568,572`; `chronicletwo:...:541,551`).
- Windows link flags differ. Chronicle's Windows link is `-fuse-ld=lld -Wl,--gc-sections -Wl,--error-limit=0` (`chronicle:port/CMakeLists.txt:202-204`). ChronicleTwo adds `-Wl,--allow-multiple-definition` (`chronicletwo:port/CMakeLists.txt:223`) and compiles with `-Xclang -mno-constructor-aliases` (`chronicletwo:port/CMakeLists.txt:164`), with the reason given in a comment there.
- Both games compile PIC and `-ffp-contract=off` into their own objects (`chronicle:port/CMakeLists.txt:22,115`; `chronicletwo:port/CMakeLists.txt:18,161`).
- The image changed. The new Dockerfile drops `/opt/kazarov/mwcc-debug` and `KZ_MWCC_DEBUG_DIR`. It adds the Rust toolchain, `cxxbridge-cmd` and Corrosion, plus X11, Wayland and EGL development packages (`kazarov@a0a5ff8:image/Dockerfile` against `kazarov:image/Dockerfile`). The image tag now hashes `image/`, `tools/ffmpeg/` and `.dockerignore` (`kazarov:scripts/lib/host.sh`, `kz_image_tag`), so the two pins build two different images.
- Chronicle's STATEFIX capture tool defaults to the removed path (`chronicle:scripts/build/statefix.py:825`). That only matters when the capture is used.

## How it works

### Include model

A game's PS2 directory includes Kazarov's rules with a set of inputs in the directory scope: `KZ_MWCC`, `KZ_MWLD`, `KZ_LIB_INCLUDE_DIRS`, `KZ_MWCC_RUNNER`, `KZ_AS_FLAGS` and, for overlays, `KZ_OVERLAYS` (`chronicle:ps2/CMakeLists.txt:34-38`; `chronicletwo:ps2/CMakeLists.txt:62-65`). Kazarov's defaults use `if(NOT DEFINED ...)` (`kazarov:cmake/KazarovToolchain.cmake:15,38-60`; `kazarov:cmake/KazarovOverlays.cmake:8-16`). Those defaults are read from whatever scope is visible at the include, so a value set in a superbuild root would reach both games. A PC directory calls `kz_port_host_library`, `kz_port_sce_sources` and `kz_port_tests` after including `KazarovPort.cmake`.

Functions in Kazarov read the caller's directory variables without taking them as arguments. The existing code depends on that: `_kz_port_vendor` reads `KZ_PORT_VENDOR_DIRS` (`kazarov:cmake/KazarovPort.cmake:16`), which the Chronicle port sets in its own directory (`chronicle:port/CMakeLists.txt:34`).

### Layout move, old to new

| Old (a0a5ff8) | New (9310c53) |
|---|---|
| `cmake/Kazarov.cmake` (entry) | `CMakeLists.txt` at the root |
| `bin/kazarov` | `scripts/kazarov` |
| `bin/kz-cached`, `bin/kz-mwcc`, `bin/kz-mwcc-exec`, `bin/kz-split-stamp` | `scripts/build/` |
| `scripts/m2ctx.py`, `scripts/port_override.py` | `scripts/build/` |
| `bin/kz-extract` | `scripts/extract/kz-extract` (unchanged) |
| `bin/kz-lock` | `scripts/lib/kz-lock` |
| `bin/kz-pcsx2` | `scripts/run/kz-pcsx2` |
| `lib/config.sh`, `lib/host.sh` | `scripts/lib/` |
| `host/kazarov.ps1`, `host/kazarov.cmd` | `scripts/` |
| `python/kazarov_elf/` | `scripts/kazarov_elf/` |
| `bin/kz-ffmpeg`, `image/kz-ffmpeg` | `scripts/build/kz-ffmpeg` launcher, `tools/ffmpeg/kz-ffmpeg` |
| `port/` (gfx, audio, platform, sce, tests) | `src/cpp/`; headers to `include/` |
| `image/mwcc-debug/` | removed |
| none | `Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml`, `src/rust/`, `data_version.json`, `cmake/KazarovRust.cmake`, `cmake/KazarovWindowsRuntime.cmake`, `include/kazarov/data_version.hpp.in`, `scripts/extract/kz-textures`, `scripts/kazarov_textures.py` |

Renames from `git diff -M a0a5ff8 9310c53`. Files with a rename score below 100% changed content as well as place.

### Driver and project contract

`scripts/kazarov` derives `KZ_ROOT` from its own location and `KZ_PROJECT_ROOT` as `KZ_ROOT/../..` unless the environment overrides it (`kazarov:scripts/kazarov:14-21`). It therefore assumes Kazarov sits at `<project>/tools/kazarov`. It sources the project's `kazarov.conf` (`kazarov:scripts/lib/config.sh:21-31`), which defines `kz_config`, the configuration arrays and the hooks. One project root has one `kazarov.conf`, so one driver invocation serves one game. The lock files `.kazarov/locks/*.lock` are per root (`kazarov:README.md`, Driver section).

Configurations in both games follow the same shape: `KZ_WHERE` is `container`, `host` or `windows`, `KZ_BUILD_DIR` is the build directory, and `KZ_CMAKE_ARGS` or `KZ_PRESET` configures it. Chronicle's PS2 configurations pass `-DPLATFORM=PS2 -DREGION=...` (`chronicle:kazarov.conf:76`). ChronicleTwo passes `-DPLATFORM=PS2` only (`chronicletwo:kazarov.conf:24`).

### PS2 pipeline

`kz_disc_setup` (`kazarov:cmake/KazarovSetup.cmake:19-114`) creates `extract` (only when the disc exists at configure time), `setup` (a stamp-guarded split) and `disassemble` (a forced split). Its split chain is checksum, snapshot, the project's split command, restore (`kazarov:cmake/KazarovSetup.cmake:85-90`). `kz_mwcc_object` runs `kz-mwcc` with the project's compiler and runner, and writes a depfile (`kazarov:cmake/KazarovObjects.cmake:92-158`). `kz_asm_object` assembles with `KZ_AS` (`kazarov:cmake/KazarovObjects.cmake:52-85`). `kz_ctx` writes the m2c declaration context (`kazarov:cmake/KazarovContext.cmake:9-39`).

### PC pipeline

`kz_port_host_library(<target>)` builds `gfx/`, `audio/` and `platform/` as one `OBJECT` library (`kazarov:cmake/KazarovPort.cmake:94-102`). It compiles the GLSL shaders to headers only in the first call, because `KZ_PORT_SHADERS_DEFINED` is a global property (`kazarov:cmake/KazarovPort.cmake:74-78`). It fetches or reuses the vendored single-file libraries at pinned hashes (`kazarov:cmake/KazarovPort.cmake:15-25,53-67`). `kz_port_sce_sources` returns the `sce/` sources for named families plus `unimplemented.cpp` (`kazarov:cmake/KazarovPort.cmake:113-130`).

The game then compiles its own `ps2/src` units through the override stripper (`chronicle:port/CMakeLists.txt:69-90`; `chronicletwo:port/CMakeLists.txt:110-133`). It links the host, sce and game objects into the executable with `$<TARGET_OBJECTS:...>` (`chronicle:port/CMakeLists.txt:214`; `chronicletwo:port/CMakeLists.txt:231`). Object-library sources are compiled once per game, so the two games' host and sce objects are separate copies.

### Port override tool

`scripts/build/port_override.py` has three subcommands, `list`, `strip` and `check` (`kazarov:scripts/build/port_override.py:566-590`). The new version adds `--private-variables`, `--private-functions` and `--private-function-unit`, each off by default (`kazarov:scripts/build/port_override.py:585-592`). It also rejects a `PORT_OVERRIDE` function declaration with no body unless the caller opts in (`kazarov:scripts/build/port_override.py:275,282`). A grep of both `port/src` trees for `PORT_OVERRIDE` lines ending in `;` found only variable tags (`chronicle:port/src/title/op_a.cpp:126-140`). That grep is not exhaustive for multi-line prototypes, and the script was not run. [inference from grep only]

### Data and extraction

Chronicle's data path is `dcdata extract <iso> <dir>` into `data/`, with freshness held by a `kz-cached` stamp at `data/.kazarov-data` (`chronicle:kazarov.conf:123-128`). ChronicleTwo's data path is `dc2data extract` into `port/run/data`, with freshness checked by `dc2data current` and `dc2data check` (`chronicletwo:kazarov.conf:126-142`). The two schemes do not share a marker.

The Rust side publishes ChronicleTwo's data. The `kazarov_core` crate exports `extract`, `list`, `sound`, `check`, `current` and `setup_data` through the bridge (`kazarov:src/rust/lib.rs:6-26`). Publishing checks the data version in `data.json` against `data_version.json` (`kazarov:src/rust/publish.rs:48`).

### Windows

`kz_windows_runtime` copies runtime DLLs beside each executable on every build, and its `INSTALL` option writes a package list (`kazarov:cmake/KazarovWindowsRuntime.cmake:4-65`). It needs the FFmpeg runtime list from `kz_ffmpeg` to exist first (`kazarov:cmake/KazarovWindowsRuntime.cmake:33-36`). Only ChronicleTwo calls it (`chronicletwo:port/CMakeLists.txt:264-271`). Each game also has its own Windows driver script copy, which the project's `kazarov.conf` names (`chronicle:kazarov.conf:14`; `chronicle:tools/windows/kazarov.ps1`).

### Three ways to hold both games

The options below are the build-side choices. None has been configured. The costs come from the facts above.

- A. Two configure trees, one link step. Each game keeps its own root and pin. Each game adds a `STATIC` library of its game objects (its `ps2/src` units and `port/src`), leaving out its host and sce copies (game-side edit only, no Kazarov change). A third step links those archives with one host library and one sce set, which both games already compile from the same Kazarov sources. Cost: the two games must agree on which sce families the union needs, and the merged link is the first place duplicate game symbols would show.
- B. One configure, namespaced. A superbuild root `add_subdirectory`s both games, with a per-game root variable replacing `CMAKE_SOURCE_DIR`, prefixed target names and per-game binary directories. Kazarov needs the changes in Ixion hooks 1-4 and 6. Cost: the largest edit, and every Kazarov fix is an upstream change that needs the project owner's approval before any push.
- C. Shared libraries. Each game becomes a `SHARED` library with hidden default visibility and one exported entry point, with one shared host library and one Rust module, all loaded by a launcher. Cost: the game-provided hooks (`SettingsGet`, `PathsConfigure`, `WindowSetIdentity`) become per-game tables instead of link-time symbols, and Windows needs `dllexport` on each entry. Not tested. [inference]

Option A needs the least Kazarov change. Option B is the only one that gives one executable without a second link. Option C is the one the brief names, and it is the least evidenced here.

## Ixion hooks

These are integration points in Kazarov or in the games' CMake that a combined build would touch. Each names the file and what Ixion could do there.

1. `kazarov:cmake/KazarovPort.cmake:94-102`, `kz_port_host_library`. One host library shared by both games is the natural shape, since Kazarov's host code never includes game headers (`kazarov:cmake/KazarovPort.cmake:4-5`). Ixion could call it once from its root and skip the second call (the function already has a `TARGET` guard pattern at `kazarov:cmake/KazarovPort.cmake:28`).
2. `kazarov:cmake/KazarovPort.cmake:8-11`, the GLOBAL include guard and the two root variables. A second game's directory does not get `KZ_PORT_ROOT` or `KZ_PORT_INCLUDE_ROOT`, because the file body runs once. Moving the two `get_filename_component` results into a function, or into an `INTERNAL` cache value, would make the module safe for a second caller. [inference: follows from GLOBAL semantics; not configured]
3. `kazarov:cmake/KazarovSetup.cmake:62,102,104` and `kazarov:cmake/KazarovContext.cmake:38`. Parameterising the target names (`extract`, `setup`, `disassemble`, `ctx`) lets both PS2 trees coexist. Ixion could also prefix the game-side names (`elf`, `iso`, `objdiff`, `verify_extracted`).
4. `kazarov:cmake/KazarovToolchain.cmake:3-4,32,78`, `kazarov:cmake/KazarovObjects.cmake:82,134,155` and `kazarov:cmake/KazarovSetup.cmake:58,98,106`. These use `CMAKE_SOURCE_DIR` as the project root. A superbuild root would be the wrong root for both games. A variable such as `KZ_PROJECT_ROOT` set per game, used in place of `CMAKE_SOURCE_DIR` in these ~10 sites, would fix it. The game side has more `CMAKE_SOURCE_DIR` references (CMake files only, grep counts: Chronicle 18 in `port/` and 81 in `ps2/`; ChronicleTwo 40 and 57), which would need the same change.
5. `chronicletwo:port/CMakeLists.txt:39`. The FORCE on `KZ_PORT_BUILD_TIM2` should go, or become a per-game argument. While it is in force, a shared cache would drop `gfx/tim2.cpp` from Chronicle's host copy, and Chronicle's shared test glob would still include a test that needs it. [inference on the link result; see Risks]
6. `chronicletwo:port/src/tests/CMakeLists.txt:22` and `kazarov:cmake/KazarovPort.cmake:134`. The shared test set is globbed into every consumer. Ixion needs one decision on whether one test executable holds both games' cases, and whether `tim2.cpp` belongs to the host library or the tests.
7. `chronicletwo:port/cmake/movies.cmake:4-5`. ChronicleTwo's LGPL FFmpeg link attaches to `ct_options`. A combined build would need that link once, not per game, and Chronicle has no FFmpeg dependency today.
8. `chronicletwo:port/CMakeLists.txt:150-171` and `chronicle:port/CMakeLists.txt:105-121`. The `ct_` and `dc_` option libraries are the seam where per-game compile flags live. A third prefix (for example `ix_`) keeps the existing names apart. The two `-include port.h` lines and the `-Wno-*` sets differ and would need to be merged per game.
9. `chronicle:port/CMakeLists.txt:202-211` and `chronicletwo:port/CMakeLists.txt:220-228`. The link option sets differ. A merged executable should use the union, and it should not carry `--allow-multiple-definition` (see Risks).
10. `chronicletwo:port/src/tests/CMakeLists.txt:14-22` and `kazarov:src/rust` through `kazarov:cmake/KazarovRust.cmake:20-21`. Rust is needed only by ChronicleTwo's `dc2data`. A combined build should link `kazarov_core` once, into one module. The cxx bridge is in namespace `kazarov`, so two copies would share symbol names.
11. `chronicletwo:port/src/identity.cpp:9-11` and `chronicle:port/src/identity.cpp:10-11`. These calls to `PathsConfigure` and `WindowSetIdentity` set per-process state. Ixion can define one identity in its own root and keep the two games' data directories separate by environment variable name (`DC_DATA`, `DC2_DATA`).
12. `kazarov:scripts/lib/config.sh:21-31` and `kazarov:scripts/kazarov:18-19`. The driver accepts `KZ_PROJECT_ROOT` from the environment. The project's `kazarov.conf` is still one file per root, so Ixion would need its own root with its own `kazarov.conf`, and a `kz_config` that names both games' builds.
13. `kazarov:data_version.json` and `chronicletwo:port/CMakeLists.txt:26-34`. Ixion can read the same file to generate its own `KAZAROV_DATA_VERSION` header. Chronicle's data would stay outside this scheme unless it adopts `dc2data`'s marker.

## Risks and blockers

- Chronicle cannot configure against main as it stands. The include at `chronicle:ps2/CMakeLists.txt:46` names a file that main does not have. The port's override script path (`chronicle:port/CMakeLists.txt:54`) and the `bin/` paths in `chronicle:kazarov.conf:119-128` are also gone. Every one of those needs editing for a pin bump.
- A pin bump changes Chronicle's behaviour, not just its build. Chronicle compiles Kazarov's shared host library and sce sources, so the 2026 changes reach it too. The diff stat for those files is large: `platform/input.cpp` (216 lines changed), `gfx/displaylist.cpp` (511), `audio/soundtrack.cpp` (101), `sce/libcdvd.cpp` (rewritten, 132 lines added), `platform/mouse.cpp` (50) and `audio/mixer.cpp` (52). Chronicle needs its own regression pass after any bump. [from diff stat; not run]
- `-ffp-contract=off` on the host library (`kazarov:cmake/KazarovPort.cmake:110`) is new for Chronicle's host objects. On x86-64 the baseline has no FMA, so there is no change there. On arm64 it changes rounding in the host code. [inference from the compiler note in the file]
- The image lost `KZ_MWCC_DEBUG_DIR`. Chronicle's `statefix.py` reads it when `STATEFIX_CAPTURE` is set (`chronicle:scripts/build/statefix.py:825`). Chronicle's own `tools/mwcc-debug` is still in its tree, so only the default path is affected. [inference; the capture path was not run]
- Global target names collide in one configure. `extract`, `setup`, `disassemble`, `ctx`, `elf`, `iso`, `objdiff` and `verify_extracted` are defined by both PS2 trees. CMake rejects a second `add_custom_target` of the same name in one project. [inference from CMake's documented uniqueness rule; not configured]
- Cache variables are shared. `PLATFORM` is a cache string in both root files with the same values (`chronicle:CMakeLists.txt:6`; `chronicletwo:CMakeLists.txt:6`), so a superbuild has one value. `KZ_PORT_BUILD_TIM2` (`chronicletwo:port/CMakeLists.txt:39`, FORCE) would override any other game's value. The Kazarov Rust module also sets three cache variables with FORCE: `CORROSION_BUILD_TESTS` always (`kazarov:cmake/KazarovRust.cmake:16`), `FETCHCONTENT_SOURCE_DIR_CORROSION` only when the `KZ_CORROSION_SOURCE_DIR` environment variable is set (`kazarov:cmake/KazarovRust.cmake:4-7`), and `Rust_CARGO_TARGET` only on Windows with Clang (`kazarov:cmake/KazarovRust.cmake:9-10`).
- Directory variables are inherited by children. If a superbuild root sets `KZ_MWCC` or `KZ_OVERLAYS`, the child directories see it, and Kazarov's `if(NOT DEFINED ...)` defaults will not replace it. [inference from CMake's directory-scope inheritance]
- Build-tree names are shared under a superbuild. Kazarov writes into `${CMAKE_BINARY_DIR}/kz_port/generated` and `${CMAKE_BINARY_DIR}/kz_port/vendor` (`kazarov:cmake/KazarovPort.cmake:22,71`). In a superbuild, `CMAKE_BINARY_DIR` is the root's directory, so both games would write the same paths. Chronicle's `port/CMakeLists.txt:179-185` and ChronicleTwo's `find_path` (`chronicletwo:port/CMakeLists.txt:201-202`) both search those directories.
- Shader rules are emitted once per configure. The second host library would depend on header outputs whose rule lives in another directory. [inference; a generator-specific risk that may only show with Makefiles]
- Link-level symbol duplication. Two host libraries and two sce sets in one executable would define the same symbols twice. A combined executable must use one copy of `gfx/`, `audio/`, `platform/` and `sce/`. That is an observed property of the build (both games compile the same sources into separate objects), not a test result.
- Windows link flags. ChronicleTwo's `--allow-multiple-definition` hides duplicate definitions (`chronicletwo:port/CMakeLists.txt:223`). A combined build should not inherit it, or duplicates would link silently.
- Chronicle has no data version; ChronicleTwo has one. A combined build with one `KAZAROV_DATA_VERSION` would need the two data formats to agree on it, or each game needs its own marker.
- Rust is a build requirement for any target that includes `KazarovRust.cmake`. Chronicle would need Rust 1.99.0 in its image if a superbuild includes that module at the root.
- The old `port/` root and the new `include/` root both serve `gfx/gfx.hpp` and `platform/*.hpp` (`chronicle:port/CMakeLists.txt:107-108` uses `${KZ_ROOT}/include` for the `dc_options` path), so the header move is probably transparent for Chronicle. Not checked file by file.
- `kazarov:README.md:160` names `KZ_BIN`, which the toolchain no longer sets. Use `cmake/KazarovToolchain.cmake` and `scripts/kazarov` as the source of truth.

## Open questions

- Does a superbuild root have to exist at all? The alternatives are (a) keep two configure trees and link their object archives in a third step, with one host and one sce copy, or (b) one configure with namespaced targets (Ixion hooks 1-4), or (c) two shared libraries built by each game's own CMake plus a thin launcher. The answer decides how much of Kazarov must change.
- Shared libraries: would a single `kazarov_host` shared library with default visibility satisfy both games, given that the host calls game-defined hooks (`SettingsGet`, `PathsConfigure`) at link time? Two games in one process would need per-game hook tables. Not tested.
- Windows DLL exports and `-Wl,--defsym` aliases (`chronicle:port/CMakeLists.txt:202-211`) are per link. Whether those aliases survive a shared-library split is untested.
- Does Chronicle's test executable link when `KZ_PORT_BUILD_TIM2` is OFF? Chronicle's test CMake calls `kz_port_tests(darkcloud_tests)` (`chronicle:port/src/tests/CMakeLists.txt:21`) and adds no `tim2.cpp`, so the shared `gfx_tim2_test.cpp` would need a decoder that only the host library provides. Chronicle's own tests use its `dcdata::Tim2` helpers instead. Only a configure and link can settle this.
- Which Kazarov pin should Ixion use? The tree at 9310c53 equals ChronicleTwo's pin and is the current layout. Chronicle would move to it. A pin bump needs a dated, separate commit in Chronicle, per that repository's rule for submodule bumps.
- Does `statefix-wibo.sh` (Chronicle's runner) work with the new image's `kz-mwcc-exec`? Not checked.
- Does the new Kazarov host library change Chronicle's behaviour on arm64 through `-ffp-contract=off`? Not measured.
- Should Ixion's `kazarov.conf` be a third project root, or should it sit inside one of the two game roots with `KZ_PROJECT_ROOT` set? The driver supports the override (`kazarov:scripts/kazarov:18-19`) but the config contract is one file per root.
</content>
