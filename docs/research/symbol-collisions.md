# Symbol collisions between the Chronicle and ChronicleTwo builds

## What this covers

How many global names the two PC builds define in common, which of those would collide if the game and port objects of both went into one executable, what kind of collision each one is, and which isolation options follow from the numbers.

Inputs: the DC1 (Chronicle) and DC2 (ChronicleTwo) build trees as they existed for this pass, their symbol receipts (`dc1.syms`, `dc2.syms`, `common.syms`), and the Kazarov lineage each build compiles. The counts come from `tools/symbol_collisions.py` in this repository, run in its default linked mode:

```
python3 tools/symbol_collisions.py --build-a <dc1-build> --build-b <dc2-build> \
    --nm <llvm-nm> --label-a dc1 --label-b dc2 --receipts <receipts-dir> --json out.json
```

Scope limits are in Risks and blockers. In particular the build trees are older than the masters the repos currently point at, so re-run the tool on fresh builds before any design decision that depends on a specific count.

## Key facts

- **Linked inputs match the link edges.** DC1 `darkcloud.exe` takes 306 object inputs in the current `build.ninja`: 136 game (`dc_ps2`), 117 port (`dc_port`, `port/src`), 12 SCE (9 Kazarov `port/sce` objects plus 3 stubs), 39 host-copy (`dc_host`, all compiled from `tools/kazarov/port/{platform,audio,gfx}`), one object from `darkcloud.dir/src` and one resource object (build.ninja, `darkcloud.exe` edge). An earlier count of 270 (90 port, 32 host-copy, 11 SCE) does not match that edge; the build tree it came from is unverified. DC2 `darkchronicle.exe` takes 326 object inputs: 149 game (`ct_ps2`), 115 port and 62 host-layer objects (58 Kazarov C++, 40 of them in `ct_host`, plus 4 platform copies). It also takes two archives, `libkazarov_bridge.a` and `libkazarov_core.a` (build.ninja, `darkchronicle.exe` edge). The DC2 counts were checked against the edge. The tool itself was not re-run (no `llvm-nm` on this host), so the DC1 figures come from `build.ninja` alone.
- **Unlinked objects are excluded.** DC1 has 21 test objects (including `libgtest.a`) and 1 tool object outside the executable. DC2 has 148 cargo `.rlib` dependencies, 4 Kazarov `.rlib` copies, 7 import libraries and 2 tool objects outside it. Tree-wide analysis would overstate DC2 by about 16,000 defined names (46,407 against 30,049) without changing the cross-collision count.
- **Defined names in the merged sets.** DC1: 6,050 names, 4,969 strong and 1,081 weak-only. DC2: 30,049 names, 28,421 with a strong definition, of which 21,251 come only from the Kazarov Rust archives (about 1,900 archive members, `libkazarov_core.a`).
- **Undefined names.** DC1 references 3,442 names, 422 of them unresolved in the tree (SDL 63, Vulkan 104, libc++ 157, CRT 11, operator new/delete 4, other 83). DC2 references 11,583, 693 unresolved (SDL 78, Vulkan 104, libc++ 158, win32-like 175, ffmpeg 15, CRT 24, other 135).
- **Cross-build collisions: 1,449 names** are defined in both merged sets. Under a single link: **664 are hard link errors** (629 code, 35 data), **4 are silent strong-wins** (all code) and **781 are silent first-wins** (639 code, 142 data). Total 664 + 4 + 781 = 1,449. (unverified: the tool could not be re-run here, and the receipts below do not contain the per-name effect data.)
- **By component pair.** Host layer 803 names (449 hard, 354 silent), game-vs-game 154 (144 hard, 4 strong-wins, 6 first-wins), port-vs-port 45 (39 hard), game-vs-port 34 (30 hard), libc++ template and runtime names 411 (all silent first-wins), operator new/delete 2 (hard).
- **Game globals collide.** The 28 game-vs-game data names that are hard errors include `CSnd`, `MainCamera`, `SaveData`, `DmaCH1`/`DmaCH2`/`DmaCH8`, `WorkBuffer`, `SystemMessage` and `gs_simage`/`mgRenderInfo`. Game-vs-port data adds `My_dma_start0`, `Vu_prog0`, `Vu_progmain`. Port-vs-port data adds `SaveSlots`, `SaveSlotNew`.
- **Game vtables collide.** Five game-vs-game vtables are hard errors: `vtable for CObject`, `CObjectFrame`, `CCollision`, `CCollisionMDT`, `CMapParts`. These are the same classes whose method surface differs between the builds (see classes below).
- **Silent strong-wins that change behavior.** `CCollision::Initialize()`, `CCollision::CreateBBox()`, `CCollision::GetMaxY(float*)` and `CMap::Draw()` are out-of-line strong definitions in DC1 and weak (Any-selection COMDAT) in DC2. Checked: the DC1 definitions exist as plain out-of-line functions (`ps2/src/dataset.cpp`, `collisionmdt.cpp`, `map.cpp`), and in DC2 the first three are declared `virtual` with inline bodies in `ps2/include/collision.hpp`. The DC2 side of `CMap::Draw` is unverified. A merged link would silently bind DC2 callers to DC1's bodies.
- **Host layer lineage.** The DC1 build compiles its audio, gfx and platform host sources (`dc_host`, 39 objects in the current `build.ninja`) from `tools/kazarov/port/{audio,gfx,platform}`, not from `port/src`; only `port/src/platform` exists in the chronicle tree at `3bc16763`. Those copies were forks in an earlier layout: DC1's `audio/mixer.cpp` differs from Kazarov's `port/audio/mixer.cpp` at the pinned `a0a5ff8` by 173 changed lines in a plain diff (unverified: the last committed DC1 `port/src/audio/mixer.cpp` gives 118 changed lines, and the current `tools/kazarov/port/audio/mixer.cpp` is identical to `a0a5ff8`). DC2 compiles Kazarov's `src/cpp` directly at the pinned `3dc38ce`, and its copy of `audio/mixer.cpp` matches that pin exactly (kazarov `src/cpp/audio/mixer.cpp` at `3dc38ce`). The host-layer collisions are therefore one code lineage present in two copies: `host-copy / host` 385, `host-copy / host-copy` 143, `sce / host` 122.
- **Class layouts diverge.** 129 owners of constructors, vtables or typeinfo are defined by both builds: 99 are libc++ (skipped), 30 are project classes. Of the 30: 9 have the same method surface, 6 have the same surface with different code lengths, and 15 differ in method set or vtable length. Examples: `ClsMes` (37 methods in DC1, 67 in DC2), `CObject` (39 vs 17, vtable length differs), `CMapParts` (19 vs 36), `audio::Mixer` (29 vs 38), `CObjectFrame`, `CScriptInterpreter`, `CWater`, `CRunScript`, `CCollisionMDT`, `CCollision`. Inference only: symbols cannot prove layout equality.
- **DC2 link tolerates duplicates.** The DC2 `darkchronicle.exe` link carries `-Wl,--allow-multiple-definition` (build.ninja, `darkchronicle.exe` LINK_FLAGS; chronicletwo `port/CMakeLists.txt:223`), and the CMake comment calls it a guard for COMDAT copies that remain after `header_fixups.py` (chronicletwo `port/CMakeLists.txt:221-222`). DC1's `darkcloud.exe` does not carry it. A probe (below) shows the flag turns the duplicate error into a warning and first-wins. Within each build's linked set the tool finds zero strong duplicates, so the flag hides nothing the symbol tables show today.
- **Port override mechanism.** Both halves compile every ps2 unit as a copy with the port-overridden definitions removed (chronicle `port/CMakeLists.txt:1-6` and `:54-62`, calling `port_override.py`). `EditLoop` is an example: tagged in `port/src/editloop.cpp:186`, and in DC1's linked set the only definition is the port object.
- **Weak defaults already exist.** DC1 `port/src/linknames.cpp` defines names as `PORT_LINK_NAME` (`__attribute__((weak))`, line 28), documented as replaceable defaults (lines 4-6). The DC1 build has 19 weak externals (symbol letter `W`), none in the collision list (unverified: not re-counted).
- **Receipts agree with the executables.** `dc1.syms` has 9,722 names, `dc2.syms` 28,698, and `common.syms` (3,013) equals their intersection. Breakdown of the 3,013: 1,210 are cross collisions present in both executables; 239 of the 1,449 cross collisions are missing from at least one executable's symbol table (most likely removed by `--gc-sections`; lld still reports such duplicates at link time, see the probe); 799 linker artifacts; 632 names that are in neither merged set and are not shared imports (a random sample was mostly file-local `_ZL...` and anonymous-namespace `_GLOBAL__N_1` names, plus libc++ names; the rest were not classified); 369 shared import or library names (SDL 57, Vulkan 103, libc++ 129, CRT 11, operator new 4, other 65); 3 defined on one side only.
- **Undefined crosses are tiny.** DC1 needs three names that DC2 defines (`___chkstk_ms`, `__divti3`, `__udivti3`). DC2 needs no name from DC1.
- **Probe results** (linked with the toolchain's clang 23 and lld, in a scratch directory outside both trees):
  - Two external definitions of one non-inline name, emitted with `-ffunction-sections -fdata-sections` the way the builds compile, give `duplicate symbol` from lld, for both functions and data, even when neither is referenced under `--gc-sections`.
  - Two `inline` (Any-selection) definitions link silently.
  - A strong definition and an inline-only reference to the same name link silently and bind to the strong copy.
  - `-Wl,--allow-multiple-definition` downgrades the duplicate error to a warning and links.
  - `llvm-objcopy` rejects `--localize-symbol(s)`, `--prefix-symbols` and `--weaken-symbol` on COFF ("option is not supported for COFF"). `--redefine-sym` works. Renaming a colliding name in every object of one build (mangled function names and data) removes the errors.
  - Two DLLs that each define a same-named global, not exported, link into one host executable.
- **Counts by component (linked mode).** Per-category counts overlap, so a name defined in two categories of one build is counted in both. Undefined counts are names referenced by that category.

| Component | DC1 objects | DC1 defined | DC1 referenced | DC2 objects | DC2 defined | DC2 referenced |
|---|---|---|---|---|---|---|
| game (`ps2_src`) | 136 | 3,935 | 1,830 | 149 | 5,858 | 3,487 |
| port (`port/src`, PORT_OVERRIDE and port code) | 117 | 992 | 1,998 | 115 | 1,290 | 1,374 |
| host-copy (DC1 audio, gfx, platform copies; DC2 platform) | 39 | 1,284 | 533 | 4 | 613 | 149 |
| host (Kazarov C++, `tools/kazarov/src/cpp`) | 0 | 0 | 0 | 58 | 1,483 | 567 |
| SDK stubs (`port/src/sce`) | 12 | 165 | 77 | 0 | 0 | 0 |
| Kazarov Rust archives (`libkazarov_core.a`, `libkazarov_bridge.a`) | 0 | 0 | 0 | 2 | 21,398 | 6,902 |
| resource object | 1 | 0 | 0 | 0 | 0 | 0 |

## How it works

**Scope.** Linked mode reads `build.ninja`, finds the executable link edge (largest non-test, non-data, non-bridge `.exe`, or `--exe-a/--exe-b`), and takes its explicit object inputs and implicit archive inputs. Every other object in the tree is counted and skipped. Tree mode (`--mode tree`) keeps every object outside test, tool and import-library categories; it gives the same cross-collision count here but a wrong inventory for DC2.

**Symbol reads.** `llvm-nm --format=posix -g --defined-only` and `--undefined-only` per object or archive member. `llvm-readobj --symbols` on the same file gives, per section, the COFF selection value from the section-definition auxiliary record, plus weak-external records. Archive output is split on its `File:` headers so each member keeps its own selection data.

**What counts as weak.** A definition is weak if its section's COMDAT selection is `Any`, `Largest`, `SameSize`, `ExactMatch` or `Associative`, or if it is a weak external (`W`/`V`/`w`/`v`). It is not weak because of the `IMAGE_SCN_LNK_COMDAT` flag alone: with `-fdata-sections` every data global, including file-local statics such as `.bss$GameClearFlag`, carries that flag with selection `NoDuplicates`. `NoDuplicates` is treated as strong, because lld rejects two of them (probe).

**Link effect per name.** Each name's cross-build status is strong (plain object), archive-only strong, or weak. Strong on both sides: `hard-link-error`. Strong on one side and weak on the other: `silent-strong-wins`. Weak on both: `silent-first-wins`. Strong only inside an archive member: `archive-pull-dependent`. The last category is empty in this build pair because all Kazarov archive definitions that overlap DC1 are weak.

**Attribution.** Each object is classed from `compile_commands.json` where the object has an entry (`game` for `ps2_src`, `port` for `port/src`, `host-copy` for `port/src/{audio,gfx,platform}`, `sce` for `port/src/sce` and stubs, `host` for `tools/kazarov`, `test`, `tool`). Objects without an entry are classed by path: `gtest`/`googletest`/`tests` as test, `libkazarov_*` archives as `rust-kazarov`, cargo dependencies as `rust`, `ct_host.dir` as host. Test archives such as `libgtest.a` must be classed as test; otherwise their libc++ copies appear as strong collisions.

**Code or data.** A collision is `code` if every definition's symbol letter is `T`, `t`, `W` or `w`, else `data`.

**Classes.** Owners of constructors, destructors, vtables and typeinfo are recovered from `llvm-cxxfilt` output. Two builds are compared by method signature set, vtable length and code-length (COMDAT section length). `same-surface` means equal method sets and vtable length; `surface-or-vtable-differs` means a method set or vtable length differs.

**Undefined names.** Each unresolved name is classed by name pattern (libc++, CRT, operator new/delete, SDL, Vulkan, ffmpeg, win32-like) for the report only.

**Output.** Markdown to stdout (inventory, cross collisions by group, effect and kind, examples per group ordered most severe first, classes, undefined crosses, receipts breakdown) and optional JSON with every cross record (`name`, `demangled`, `group`, `effect`, `kind`, `pair`, `a_state`, `b_state`). The JSON is the input for generating per-build rename lists.

## Ixion hooks

Isolation options compared. "Probed" means a synthetic probe in a scratch directory behaved as stated; no option has been tested on the real builds yet.

| Strategy | What it removes | Cost | Status |
|---|---|---|---|
| Separate DLLs (or processes) with an export list of the cross-world API | All link-level collisions between worlds, and shared layouts | Cross-world calls become bridge calls; data crosses by value | Probed: same-named private globals in two DLLs link into one host |
| Per-build rename of colliding names over every object of that build (`--redefine-sym`) | The named collisions, so one executable links | Generated rename list per build; must cover archive members and references | Probed on COFF, including mangled function names |
| Keep duplicates as hard errors (no `--allow-multiple-definition`) | Nothing by itself; keeps failures loud | None | Probed: the flag converts errors to warnings |
| One host layer (Kazarov `src/cpp` at `3dc38ce`, retire DC1 copies) | The 803 host-layer names | Port DC1 host code onto the Kazarov tree | Source comparison only |
| Compile-time C++ namespaces per world | C++ names, including classes | Changes to the port_override copy step; extern "C" names still need asm labels | Not probed |
| `llvm-objcopy --localize-symbols` or `--prefix-symbols` | Would be the cheapest rename | Not available: rejected for COFF | Probed: rejected |

1. **Per-build rename list at the copy step.** The port build already produces a per-unit copy of every ps2 unit (chronicle `port/CMakeLists.txt:54-62`). A rename pass after the copy step, driven by a list generated from `symbol_collisions.py --json` (`cross_records` with effect `hard-link-error` or `silent-strong-wins`), is the cheapest in-executable fix. Apply it to every object of that build, including archive members, or a half-renamed build fails at link time. Verified as possible on COFF with `llvm-objcopy --redefine-sym`; mangled names are needed for C++ functions.
2. **Bridge DLLs instead of one executable.** Build each world as its own DLL (or process) with an explicit export list of the cross-world API only, using `__declspec(dllexport)` and a `.def` file. The probe showed same-named private globals in two DLLs link into one host. Pass structured data across the boundary, not C++ objects, because the layouts diverge (15 classes).
3. **Drop the duplicate-tolerant link flag in any merged link.** Do not carry `-Wl,--allow-multiple-definition` (chronicletwo `port/CMakeLists.txt:223`) into an Ixion executable. The tool's zero-duplicate result for DC2 says the flag is idle today, so removing it costs nothing now and keeps the 664 hard errors visible.
4. **One host layer.** Pick Kazarov's `src/cpp` at `3dc38ce` (the DC2 lineage, identical to what DC2 builds) and retire DC1's `port/src` host copies, or make DC1 consume the same Kazarov tree. That removes the 803 host-layer names and the `sce`-versus-`host` split (`sce / host` 122).
5. **Weak defaults for world-specific fallbacks.** `PORT_LINK_NAME` (chronicle `port/src/linknames.cpp:28`) is the existing mechanism for a name one world needs and the other does not. Extend it for cross-world stubs rather than defining them strong.
6. **Extern "C" names.** `main`, `wmain`, `rand`, `srand`, `exit__2`, `mwInit` and `__construct_new_array` collide as port-port or game-port names (port-vs-port and game-vs-port hard errors). Rename through the asm-label pattern that already exists (chronicle `port/include/port.h:16`, `PORT_ASM_NAME`) rather than a C++ namespace.
7. **CI gate.** Run the tool on each build in CI. Fail on any new `hard-link-error` or `silent-strong-wins` name not on a reviewed allowlist, and report the counts above as the baseline.

## Risks and blockers

- **664 hard link errors** mean a single-executable merge of these two builds does not link as they stand. That is a loud failure, which is the good kind.
- **The DC2 link flag would hide all of them.** If an Ixion link inherits `--allow-multiple-definition`, the 664 become silent first-wins with only lld warnings.
- **Four silent strong-wins change behavior** without any error (the `CCollision` and `CMap::Draw` names above). Any gate has to treat them as blockers, not warnings.
- **Layouts cannot be proven equal** for the 30 shared project classes. Matching method surfaces do not match `sizeof`, field offsets or inline bodies. Only a probe header with `static_assert`s compiled against both builds could show that.
- **The build trees are not the masters.** The DC1 build tree is described as a 2026-10-07 worktree whose `port/src` contains `audio/`, `gfx/` and `platform/` copies (unverified for that tree). At the chronicle master (`3bc16763`, checked), `port/src` has `platform/` only and no `audio/` or `gfx/`; that code sits under `tools/kazarov/port/`, and the current DC1 `build.ninja` compiles from there too. The 803 host-layer names may be different on master. The DC1 `build.ninja` also has 306 linked objects, not the 270 this document first gave. The DC2 tree is a `pr2ci` worktree, not `f44a756`. Re-run on fresh builds from the masters before using any count.
- **Platform and toolchain.** The NoDuplicates and duplicate-definition results are for lld in the llvm-mingw toolchain used here (clang 23). MSVC `link.exe` was not tested, and the PC port is Windows-only, but a future non-clang build would need its own probe.
- **Archive semantics.** Archive members are treated as candidates. Pull-in is not modelled, so a name that only an archive member defines may collide with a plain object definition in a link that never pulls the member. No such pairs appeared here.
- **Receipts include file-local names.** `dc1.syms` and `dc2.syms` are not limited to global names; 632 of the 3,013 common names are outside both merged sets and mostly appear to be file-local (sampled, not exhaustively classified), so they cannot collide as globals. Do not count receipts as link-level collisions.
- **Heuristic buckets.** `sdk:win32-likely` (175 DC2 names) is a name-shape guess, not an import table lookup. `sdk:other` and the class-level comparison are also inference.
- **Probe artifacts are not a real link.** The probes used small synthetic objects. Confirm each claim with a real link of an isolated tree (not the source trees), for example a test executable that links DC1 and DC2 objects after the rename pass.

## Open questions

- Why does the toolchain give every `-fdata-sections` global, including file-local statics, a `NoDuplicates` COMDAT here? Is `-fms-extensions` involved (the DC1 unit compile flags include it)? The answer decides whether game globals are intended to be weak.
- DC2 game objects define `EditLoop`, `TitleDraw`, `TitleLoop`, `GetPackFile`, `StartReadBG`, `MenuCalcBufAlignment` and `chk_int` (the game-vs-port pairs with DC1 as port). Which DC2 override list covers them, and is DC2 intentionally keeping the PS2 bodies that DC1 overrides?
- Which DC2 objects provide `___chkstk_ms`, `__divti3` and `__udivti3`, and does DC1 get them from the toolchain runtime?
- Do the 411 libc++ silent first-wins names come from the same libc++ build? Both use the `nqe230102` ABI tag, but that does not prove identical code or typeinfo.
- Do the 35 data-name hard errors survive the rename pass, given that data globals use C names and some use mangled names? Test a mixed set before generating the full list.
- Is the DC2 `--allow-multiple-definition` guard covering symbols the tool filters out (artifact prefixes, `$`-names)? The zero-duplicate count does not rule that out.
- How does the class comparison look on fresh masters? The 15 divergent classes are from the supplied build trees.
