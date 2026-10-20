# Build the crossover showcase

Use this branch's recursive submodule pins. All three programs share ABI v2;
mixing them with Hop v0 DLLs fails the version check. These pins use the older
binary CHR/texture-catalog data generation. Current upstream glTF/v20 data is
not compatible with this candidate.

## Windows build

Requirements: PowerShell 7, Python 3.10+, CMake, 7-Zip, a Vulkan-capable GPU, and
the llvm-mingw/SDL3/Rust dependencies described by the pinned ports. The initial
port build acquires dependencies; cached/offline builds can reuse those roots.
No game data is needed to compile.

From the Ixion root, build each port once using its normal Windows launcher:

```powershell
Push-Location games/chronicle
.\build.bat windows-x64-release
if ($LASTEXITCODE) { throw 'Chronicle build failed' }
Pop-Location
Push-Location games/chronicletwo
.\build.bat windows-x64-release
if ($LASTEXITCODE) { throw 'ChronicleTwo build failed' }
Pop-Location
```

Then add the Ixion options to those configured build directories. The donor
libraries deliberately verify the pinned source; do not substitute newer
upstream checkouts or disable the provenance checks.

```powershell
$repo=(Get-Location).Path.Replace('\','/')
$deps="$repo/games/chronicletwo/.kazarov/windows/deps"
$env:CARGO_HOME="$deps/rust/cargo-home"
$env:PATH="$deps/rust/1.99.0-gnullvm/bin;$deps/llvm/llvm-mingw-20260922-ucrt-x86_64/bin;$env:PATH"
cmake -S games/chronicle -B games/chronicle/port/build/windows-x64-release `
  -DIXION_BUILD_PLUGIN=ON "-DIXION_API_DIR=$repo/include" `
  "-DIXION_DC2_SOURCE_DIR=$repo/games/chronicletwo"
if ($LASTEXITCODE) { throw 'Chronicle configuration failed' }
cmake -S games/chronicletwo -B games/chronicletwo/port/build/windows-x64-release `
  -DIXION_BUILD_PLUGIN=ON "-DIXION_API_DIR=$repo/include" `
  "-DIXION_DC1_SOURCE_DIR=$repo/games/chronicle"
if ($LASTEXITCODE) { throw 'ChronicleTwo configuration failed' }
& ./games/chronicle/tools/windows/build.ps1 `
  -Root "$repo/games/chronicle/.kazarov/windows" `
  -BuildDirectory "$repo/games/chronicle/port/build/windows-x64-release" `
  -Targets @('darkcloud','ixion_c1','dcdata')
if ($LASTEXITCODE) { throw 'Chronicle module build failed' }
& ./games/chronicletwo/tools/windows/build.ps1 `
  -Root "$repo/games/chronicletwo/.kazarov/windows" `
  -BuildDirectory "$repo/games/chronicletwo/port/build/windows-x64-release" `
  -Targets @('darkchronicle','ixion_c2','dc2data')
if ($LASTEXITCODE) { throw 'ChronicleTwo module build failed' }
pwsh -NoProfile -File host/build-windows.ps1 `
  -Deps games/chronicletwo/.kazarov/windows/deps -Build build/host
if ($LASTEXITCODE) { throw 'Host build failed' }
```

Fresh builds were verified with explicit cached dependency paths. The complete
first-download/acquisition sequence above has not been rerun end-to-end. The
build wrappers set their pinned toolchain/Cargo environment; the explicit
environment above also covers C2's reconfiguration step.

## Extract your discs

Both pinned ports use **PAL** data. Building does not extract it. Choose new
output folders outside the checkout, then run the just-built extractors:

```powershell
& ./games/chronicle/port/build/windows-x64-release/dcdata.exe `
  extract '<Dark Cloud PAL ISO>' '<new DC1 data directory>'
if ($LASTEXITCODE) { throw 'DC1 extraction failed' }
& ./games/chronicletwo/port/build/windows-x64-release/dc2data.exe `
  extract '<Dark Chronicle PAL ISO>' '<new DC2 game root>/data'
if ($LASTEXITCODE) { throw 'DC2 extraction failed' }
```

DC2's sibling `port_data/` and `data.json` must stay beside its `data/` folder.
Use the pinned extractor's version 3 output, not a newer v20 extraction. DC1's
extraction retains the raw `dun/monstor/e104a.chr`/`.stb` and room files required
by the helper, so that directory can serve both `-Dc1Data` and `--dc1-raw`.
Never put the disc inputs, extraction or converted packs into Git.

## Reproduce Opar

Create a new local package from your raw DC1 extraction:

```powershell
python -B tools/prepare_opar.py --dc1-raw '<raw DC1 data>' --output showcase-local
```

This runs both validators, creates `packs/room-d01inter` and
`packs/opar-r1-overlay`, and copies the donor script into the overlay. It refuses
an existing output directory. It does not download or distribute any game data.

Create `showcase-local/bin`. For the standalone Opar demo, copy the built
`darkchronicle.exe` and all its staged runtime DLLs from the C2 build there.
This pinned C2 uses its extracted retail font; it does not stage a `glyphs/`
directory. If also staging C1, preserve both its `lang/` and `glyphs/` directories
beside the binaries. For
the host and reverse demos also stage `ixion.exe`, `ixion_c1.dll`,
`ixion_c2.dll`, `darkcloud.exe` and their runtime dependencies. Use one shared
SDL3 DLL and inspect imports when combining runtime files.

```powershell
pwsh -NoProfile -File tools/playtest/Play-Ixion.ps1 -Mode Opar `
  -PackageRoot showcase-local -Dc2Data '<DC2 data directory>'
```

The launcher creates a fresh disposable save/run folder. `-DryRun` prints the
resolved plan and required paths without launching. Other modes are
listed in [the playtest guide](../tools/playtest/PLAYTEST.md). With this helper's
packs, both games' data and the staged binaries, six modes have a supplied
recipe: **Inspect, Hop, Opar, Ridepod, NativeDC1 and NativeDC2**. The other 23 are
source prototypes whose complete pack recipes are not published. Their menu
entries are labeled accordingly. No prebuilt asset package is included.

## Where the behaviour lives

- `games/chronicletwo/port/src/ixion_dc1_monster.cpp`: donor VM native table,
  program remapping, motion timing, collisions, projectiles and damage adapters.
- `games/chronicletwo/port/src/ixion_room*.cpp`: imported room, encounters,
  ownership, props and scene lifetime.
- `games/chronicletwo/port/ixdc1`: isolated DC1 combat routines and provenance gate.
- `games/chronicle/port/ixdc2`: isolated reverse-direction mechanics.
- `tools/monster_converter.py`: monster/player models and texture catalogs.
- `tools/room_converter.py`: room geometry, collision and authored markers.

Opar uses a real DC2 monster slot while executing its donor script through the
adapter. Other modes intentionally use different approaches; Monica's mapped
transformation profile is distinct from the donor-monster runtime.

## Validation and limits

```powershell
python -B -m unittest discover -s tests -p 'test_*.py'
cmake --build build/host --target ixion_fiber_smoke ixion_host_tests
build/host/ixion_fiber_smoke.exe
build/host/ixion_host_tests.exe
```

The pinned candidate previously had bounded local room/combat/ledger replays;
those results are not a fresh qualification against current upstream. The port
test suites contain focused Ixion cases and donor symbol/provenance gates.
The portable suite uses synthetic data and explicitly skips optional retail
checks without data. It cannot establish rendered gameplay or controller feel.

Full campaign progression, normal-balance Dran victory, physical input/audio
acceptance and several per-mode edge cases remain open. See the playtest guide
before treating any experiment as complete. The upstream migration also needs
native asset publication, 60 Hz retuning, save/autosave requalification and
render-thread lifetime checks.

### Publication check — 2026-10-20

Both standalone games and both DLLs rebuilt from these source snapshots with
cached dependencies. Donor provenance/isolation gates passed, each DLL exported
only `ixion_get_api`, and the negative symbol-gate checks passed (C1: 5; C2: 3).
The host regression and fiber tests passed. The portable suite ran 188 tests,
with 53 optional data-dependent skips; all 29 launcher plans resolved paths.

The Opar recipe reproduced the retained room/model/script bytes. A fresh
2,600-frame Opar run with the newly built game exited 0 and logged donor spawn,
script execution, projectile fire and a player hit. The freshly built host and
DLLs then completed 20 automatic switches over 2,401 host frames with zero
parked-state mismatches. These bounded checks do not qualify the other 28
modes, physical input/audio or a full campaign.
