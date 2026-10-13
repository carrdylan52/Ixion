# ChronicleTwo data loading and the DC2 data tree

## What this covers

- The retail file loader and its replacement on PC: `chronicletwo:ps2/src/dataread.cpp`, `chronicletwo:port/src/dataread.cpp`, `chronicletwo:port/src/dataread_pack.cpp`, `chronicletwo:port/src/dataread_port.hpp`.
- The texture side channel that hides converted textures from the game: `chronicletwo:port/src/texture_source.cpp`, and Kazarov's `texture_catalog` (`kazarov:src/cpp/platform/texture_catalog.cpp`) and `datapacks` (`chronicletwo:port/src/platform/datapacks.cpp`).
- Where the data root comes from (per-game identity), and the first-run gate.
- The extraction pipeline: `dc2data` (`chronicletwo:tools/dc2data/main.cpp`) and Kazarov's Rust publisher (`kazarov:src/rust/core.rs`, `archive.rs`, `textures.rs`, `publish.rs`), plus `data_version.json`.
- The map, scene, script, sound and model loaders that sit on top of the file loader: `chronicletwo:ps2/src/sceneload.cpp`, `mapjump.cpp`, `mapselect.cpp`, `map.cpp`, `mapload.cpp`, `mdslist.cpp`, and `chronicletwo:port/src/ezbgm.cpp`, `movie.cpp`.
- The extracted PAL tree: top-level directories, file counts, sizes and what each holds.
- `chronicletwo:docs/DATA_LAYOUT.md` and `chronicletwo:docs/SOUND_DAT.md`. DATA_LAYOUT is about the decompilation's native-data and objdiff layout, not runtime loading; it is noted but not relied on. SOUND_DAT covers SOUND.DAT/SOUND.HD3 and is used below.

Basis: read-only review of the `ixion` branch of the ChronicleTwo checkout (HEAD 40ec9083). Its `tools/kazarov` submodule is at the pin 3dc38ce. The Kazarov main checkout (9310c53) has byte-identical `src/rust` and `data_version.json` at that pin. Chronicle's Kazarov pin (a0a5ff8) predates the Rust publisher. Nothing was built or run. File and directory counts come from walking the extracted PAL tree on disk, not from `dc2data check`. Inference is labelled.

## Key facts

- Retail loads one index at boot. `InitCDFile` finds `DATA.DAT` on the disc, reads `DATA.HD4` into a 0x50000-byte buffer, and records count = first u32 / 12 (`chronicletwo:ps2/src/dataread.cpp:499-558`, `chronicletwo:ps2/include/dataread.hpp:67-75`, `DATA_HEADER` = name offset, size, sector).
- Retail's default device is the disc (`chronicletwo:ps2/src/dataread.cpp:34`). Prefixes `host:`/`host0:`, `cdrom:`, `net:` and `psf0:` are recognised; any other `dev:` prefix is stripped and the default device applies (`chronicletwo:ps2/src/dataread.cpp:561-637`).
- The PC port replaces the `DATA.HD4` index with a recursive walk of the data root. The walk runs on the first lookup if it has not already run, and keys each file by its lower-cased relative path (`chronicletwo:port/src/dataread.cpp:144-152`, `289-334`; header comment `chronicletwo:port/src/dataread_port.hpp:4-11`).
- The walk skips root-level `manifest.txt`, `manifest.json`, `movie/`, `sound/`, `port_data/`, dot entries and `*.dc2tmp` (`chronicletwo:port/src/dataread.cpp:38`, `77-88`). Movies and sounds are read by their own code paths instead.
- Index keys are built by `IndexKey` (`chronicletwo:port/src/dataread.cpp:90-137`): backslash becomes slash, a trailing `;<digits>` is dropped, slash runs collapse, bytes >= 0x80 and `%` are percent-encoded as in dc2data's `DiskName`, and the rest is folded to lower case. Any text before the first colon is stripped, so `cdrom0:\...` and `host:...` lose their prefix there.
- Converted textures never reach the game as IMG/TIM2 bytes. `ResolveFile` returns a 16-byte opaque handle `KZTX:asset` when the key is a texture-catalog source (`chronicletwo:port/src/dataread.cpp:205-222`). The source name is attached to the buffer's address (`chronicletwo:port/src/texture_source.cpp:14-18`; lookup by address at `:24-45`) and texture entry points look it up to find the catalog entry (`chronicletwo:port/src/mg_texture.cpp:1066-1100`).
- PACK members are read by basename, ASCII-case-insensitively, by name or index (`chronicletwo:port/src/dataread_pack.cpp:71-105`). A converted member gets a stable 16-byte handle from a static map keyed by source name. A non-converted member points into the pack buffer.
- Replacement assets ("datapacks") overlay the index only for files the index already holds. They come from `datapacks/datapacks.json` beside `port_data/` (`chronicletwo:port/src/platform/datapacks.cpp:237-290`, `Resolve` at `291`; `chronicletwo:docs/PC.md:105-160`).
- The data root for DC2 is chosen in this order: `--data`, `--run-dir` plus `/data`, `DC2_DATA`, then the per-user data directory. DC2 sets `coherent_default_root`, so it never probes a `./data` beside the working directory (`chronicletwo:port/src/identity.cpp:9-10`; `kazarov:src/cpp/platform/paths.cpp`, `PathsDataRoot`). DC1 does not set that flag, so it does probe locally.
- The first-run gate `FirstRunRequireData` checks for a current extraction (`data.json` schema 1 with `data_version` equal to `KAZAROV_DATA_VERSION`, plus `data/manifest.json` and `port_data/manifest.json`). If the data is missing it opens Kazarov's setup window, or in headless mode prints the `dc2data extract` command and exits with status 3 (`chronicletwo:port/src/platform/firstrun.cpp:22-67`).
- `data_version.json` is `{"schema_version":1,"data_version":3}`. The CMake build and the Rust publisher both read it (`kazarov:data_version.json`; `chronicletwo:port/CMakeLists.txt:26-33`; `kazarov:src/rust/core.rs`, `data_version()`).
- `dc2data` is a thin C++ front end over Kazarov's Rust core through a cxx bridge. It has five commands: `extract`, `list`, `sound`, `check`, `current` (`chronicletwo:tools/dc2data/main.cpp:30-37`, `62-80`).
- Extraction stages a copy under the output root, verifies, and publishes with rollback (`kazarov:src/rust/publish.rs`, `publish()` and `verify()`). The staged tree is `data/` (non-texture payloads, sound, movies) plus `port_data/` (PNG overlays, `catalog.json`, `manifest.json`), with `data.json` as the version marker (`kazarov:src/rust/core.rs`, `extract_with_progress`).
- SOUND.HD3 is parsed with first-match semantics. The one duplicated name (`8640040.wav`) keeps only its first record, and the second is recorded as "shadowed" (`kazarov:src/rust/archive.rs`, `parse_sound_index` at `324`; `chronicletwo:docs/SOUND_DAT.md` sections 2 and 6).
- The sound driver `ezBgm` opens plain names from `PathsDataRoot()/sound/<lower-case name>` (`chronicletwo:port/src/ezbgm.cpp:115-127`). Names with a device prefix go through `DataReadFind`, which does not search `sound/` (`chronicletwo:port/src/ezbgm.cpp:129-135`).
- Movies are read from `PathsDataRoot()/movie/<name>` with the `;1` suffix removed and lower-casing (`chronicletwo:port/src/movie.cpp:111-134`). `movie/` is outside the index.
- A map is named by its entry in a per-language table, `map/map<LanguageCode>.cfg`, loaded by `LoadMapName` (`chronicletwo:ps2/src/mapselect.cpp:277-295`). The map number is the table index (`SearchMapNo`, `chronicletwo:ps2/src/mapselect.cpp:385-401`). The current map number is saved as a signed 16-bit field (`chronicletwo:ps2/include/savedata.hpp:225-227`).
- A map's directory is derived from its name: `map/<c1>/<c1-3>/<c4-6>/<name>` (`GetMapPath`, `chronicletwo:ps2/src/mapselect.cpp:306-321`).
- Per map, `LoadMapData` reads `.map`, `.cfg`, `.mpk`, `.sky` (falling back to `map/def.sky` or `defb.sky`), `.ipk` and `.efp`, each padded to 64 bytes in one load buffer (`chronicletwo:ps2/src/sceneload.cpp:25-178`, sky fallback at `112-122`).
- Add-on maps come from `map/cmn/<dir>` (`GetLoadMapInfo`, `chronicletwo:ps2/src/mapjump.cpp:251-322`). For chapters 6 and 7, the add-on `trn/train` is replaced by `trn2/s36` (`chronicletwo:ps2/src/mapjump.cpp:305-306`).
- Map scripts are tried as `<name>_<LanguageCode>.stb` first, then `<name>.stb` (`LoadScript`, `chronicletwo:ps2/src/mapjump.cpp:388-435`).
- `mapload.cpp` performs no file I/O. Its `CMap::LoadMapFile` and `CMap::LoadCfgFile` interpret script text that `sceneload.cpp` has already read (`chronicletwo:ps2/src/mapload.cpp:2183`, `2538`; called from `chronicletwo:ps2/src/map.cpp:1849-1861`).
- Model lists (`CMdsListSet`) are keyed by name and refuse a second load under the same name (`chronicletwo:ps2/src/mdslist.cpp:288-368`). A PCP list collects every `.mds` and `.chr` member of a pack and reads `info.cfg` (`chronicletwo:ps2/src/mdslist.cpp:748-790`).
- The language enum is `LANG_JAPANESE=0` through `LANG_KOREAN=7` (`chronicletwo:ps2/include/mainloop.hpp:53-62`). The port starts in English when the jump option is set and in French otherwise (`chronicletwo:port/src/mainloop.cpp:99`).
- Message-window folders are chosen by language: `meswin/jpn`, `meswin/eu/{fra,ger,ita,spn}`, `meswin/usa` (`chronicletwo:ps2/src/gaiji.cpp:10-35`). The PAL extraction has no `meswin/jpn` directory (measured).
- Kazarov's pinned revisions differ. DC2 pins 3dc38ce, which has `src/rust/`, `data_version.json` (version 3) and a `cxx` bridge. Chronicle pins a0a5ff8, which has `bin/kz-extract` and a `python/` tree and no `data_version.json` or `src/rust/` (`git ls-tree` on both commits).

## How it works

### Retail loader (what the port must reproduce)

- Names are data-root-relative paths such as `map/a/a01/a01ia.map`. A `CurrentDir__2` string is prepended unless a device prefix is present (`GetFullPath`, `chronicletwo:ps2/src/dataread.cpp:639-673`; `SetCurrentDir`/`ChangeDir` at `181`/`198`).
- `LoadFile2` has three modes: read whole, size only, and open for background read (`chronicletwo:ps2/include/dataread.hpp:32-36`). Disc reads (`CDRead`, `chronicletwo:ps2/src/dataread.cpp:853-876`) retry until `sceCdGetError` is clear.
- A background-read queue of 32 slots and a 16-entry file cache keyed by name sit on top (`BG_READ_MAX`, `FILE_CACHE_MAX`, `chronicletwo:ps2/include/dataread.hpp:55-60`; `LoadFileCacheBG` at `chronicletwo:ps2/src/dataread.cpp:963`).
- A missing file in `LoadFile` is fatal (`File open error` then `Exit__2(0)`, `chronicletwo:ps2/src/dataread.cpp:675-682`). The port keeps this (`chronicletwo:port/src/dataread.cpp:499-505`).

### PC index and resolution

- `ResolveFile` (`chronicletwo:port/src/dataread.cpp:205-246`) tries, in order: (1) a texture-catalog source, returning the handle; (2) for `host:` names only, the save tree, so a file written by `WriteFile` shadows the extract; (3) the index. `size_only` stats the file instead of reading it.
- The read path is synchronous. `LoadFileBG` copies the file at once and leaves the slot pending, so callers that poll `ReadBGSync` still see retail's issued and done states (`chronicletwo:port/src/dataread.cpp:401-443`; `ReadBG` at `464-476`). Each slot needs two calls.
- `LoadFile2` with `LOAD_FILE_OPEN` is effectively unreachable on the port: the only caller is retail's `LoadFileBG`, which the port replaces (inference from grep of callers).
- `ReadWhole` zeroes the tail of the last 2048-byte sector so results do not depend on the caller's buffer (`chronicletwo:port/src/dataread.cpp:163-181`).
- The file cache keys on the same `CacheKey`, which is `IndexKey` with a `host:` marker (`chronicletwo:port/src/dataread.cpp:139-142`). It holds 16 entries.

### Textures, PACK members and datapacks

- The catalog is one global object. `texture_catalog::Load` clears and replaces the previous contents (`kazarov:src/cpp/platform/texture_catalog.cpp:29-30`; storage at `:14`). `DataReadIndex` loads `port_data/catalog.json` from the sibling of the data root and then calls `datapacks::Load` (`chronicletwo:port/src/dataread.cpp:336-346`).
- Texture identity is by buffer address. `TextureSourceRegister` keeps a hash map of buffer pointer to source name and size; `TextureSourceLookup` also resolves an address inside a registered range to `source#offset:N` (`chronicletwo:port/src/texture_source.cpp:9-45`).
- `DataReadIndex` clears the texture-source registry on every call (`chronicletwo:port/src/dataread.cpp:337`).
- Datapacks: `datapacks::Load` reads `datapacks/datapacks.json` (schema 1, `load_order` of folder names), indexes each folder case-insensitively, and rejects traversal and case-only duplicates (`chronicletwo:port/src/platform/datapacks.cpp:237-290`). `Resolve` returns the highest-priority pack file (`:291`). `BuildIndex` applies it to every indexed file (`chronicletwo:port/src/dataread.cpp:324`).

### Sound and movies

- `ezbgm` opens: plain names go to `data/sound/<name>`; device-prefixed names go to the index (`chronicletwo:port/src/ezbgm.cpp:115-135`). Sound names are `%07d.wav` and friends (`chronicletwo:docs/SOUND_DAT.md` section 3).
- `data/sound/` also holds two whole copies, `sound.dat` and `sound.hd3`, kept until playback is confirmed (SOUND_DAT section 6). These are about 0.97 GB of duplicate audio.
- Movies are MPEG-2 PSS files. A missing or non-MPEG-2 file logs and the caller's busy-wait ends (`chronicletwo:docs/PC.md:949`).

### Extraction pipeline

- Input is either a disc image (ISO 9660 mount, `kazarov:src/rust/archive.rs`, `open_image` at `142-192`) or a folder holding `DATA.DAT`, `DATA.HD4`, `SOUND.DAT`, `SOUND.HD3` and `MOVIE/` (`open_directory` at `213`).
- `plan_archive` (`kazarov:src/rust/archive.rs:397-460`) builds the raw file plan: each game record (first path wins), each movie as `movie/<name>`, `sound/sound.dat`, `sound/sound.hd3`, and each first-match sound as `sound/<folded name>`. Any duplicate or unsafe output path is an error.
- `textures::convert_tree_with_progress` (`kazarov:src/rust/textures.rs:1070`) turns each texture-bearing file into PNG overlays and a catalog. Payloads are not written under `data/`. `audit_payload` rejects any surviving TIM2 or IMG bytes (`textures.rs:538-560`). Files over 128 MiB are accepted only for `sound/sound.dat` and `movie/*.pss` (`large_known_non_texture`, `textures.rs:561`).
- `verify` checks manifest digests, the set of files in both trees, the marker, and the audit (`kazarov:src/rust/publish.rs`, `verify()`). `current` compares source size and mtime metadata with the marker (`kazarov:src/rust/core.rs`, `current()`), so moving or touching the disc forces re-extraction.
- Output tree markers: `data.json` holds `schema_version`, `data_version`, `source_sha256` and `source_state`. The state includes the source path, which is why it is not reproduced here.

### Map, scene and model loads

- `CScene::LoadMap` calls `LoadMapData` (immediate or deferred), then `LoadMapFromMemory` in steps (`chronicletwo:ps2/src/sceneload.cpp:284-316`, `467-516`).
- `CMap::CreateMap` runs the add-on map script first, then the main map script (`chronicletwo:ps2/src/map.cpp:1849-1861`).
- Model packs (`.mpk`) and texture packs (`.ipk`) are handed to `CMap::LoadData` (`chronicletwo:ps2/src/sceneload.cpp:371`, `377`).
- Characters load from packs by name with `GetPackFileExt(pack, "cfg", ...)` when the name is null (`chronicletwo:ps2/src/sceneload.cpp:209`).

### The extracted PAL tree

Counts from the extracted tree on disk. Sizes are bytes as reported by `du -sb`.

Top level of `data/` (17 directories and 28 files, including `manifest.json`):

| Entry | Files | Bytes | What it holds (basis) |
|---|---|---|---|
| `chara/` | 90 | 37.3 M | Party and player character models, `.chr`. `CharaSetup` loads `chara/%s` (`charasetup.cpp:163`, `237`); the fishing model `chara/c01_fishing.chr` is read from `fishing.cpp:1036`. |
| `dbg/` | 42 | 19.5 K | Debug capture and game config `.cfg` (`dbg/game%d.cfg`, `dbg/%s` referenced by debug code). |
| `dungeon/` | 1,162 | 213.9 M | Dungeon content: `act_script/` (`.stb`), `articles/` (`.chr`, `.img`), `cfg_file/`, `chara/`, `eff_script/`, `effect/`, `monster/`, `msg/` (`.mes`, `.txt`), `robo/`, `sphida/`, `sys_script/`. Minimap images are read as `dungeon/minimap/%s.img` (`dng_event.cpp:2213`). |
| `effect/` | 17 | 0.86 M | Effect models and scripts (`.chr`, `.efp`, `.eep`, `.em`, `.eff`). |
| `etc/` | 19 | 0.23 M | Editor and utility assets: `.mds`, `.mes`, `gsys.pak` (`editmode.cpp:641`), `hdd_head.hed`. |
| `event/` | 2,061 | 417.8 M | Event assets: motion sets such as `event/basic_evmot/`, boss and battle text `.txt`, `.stb` scripts, and `train/` (33 files, including NPC models read as `event/train/t%s.chr`, `npccfg.cpp:181`). |
| `item/` | 168 | 4.5 M | Item models (`.chr`), for example `item/d_box.chr`. |
| `mainchr/` | 177 | 28.2 M | Main-character models `ac000.chr` and so on, plus `c01.stb` and `c02.stb` (`charasetup.cpp:219`, `289`). |
| `map/` | 1,828 | 598.9 M | World and dungeon maps. 168 map sets (directories holding a `.map` file, measured; the earlier figure of 210 did not reproduce) laid out `map/<letter>/<area>/<name>/`, each with `.map`, `.mpk`, `.ipk`, `.efp`/`.cfg`/`.sky`/`.stb`. `map/cmn/` holds add-on maps (`bs`, `g00`, `trn`, `trn2`). `map/map0.cfg` to `map6.cfg` are the per-language name tables; `map.lst` lists maps for the selection screen; `def.sky` and `defb.sky` are default skies. |
| `menu/` | 788 | 185.8 M | Menu assets: `.pac` packs, `.chr`, `.cfg`, `.txt`, lists (`inv*.lst`, `neta*.lst`), shop lists, numbered subfolders `0`-`5`, and `aqua`, `cfg5`-`cfg7`, `chara4`, `dngmap`, `eff`, `mhenge`, `monster`, `npc`. |
| `meswin/` | 41 | 1.07 M | Message-window text and fonts by region: `eu/{fra,ger,ita,spn}`, `usa`, `kor`, `try`. No `jpn`. |
| `movie/` | 9 | 661.6 M | MPEG-2 PSS movies (`e54001.pss` and others, `end1`/`end2`, `l5logo`, `open1`, `rush`). Not in the index. |
| `sg/` | 75 | 14.1 M | Sub-game assets: `fish/` (fishing `.chr`, `.cfg`, `.pak`, `.mes`), `gyo/` (`sg/gyo` read by code), `pb/` (`sg/pb`, pbuggy), and `sig/` (not traced). |
| `snd2/` | 843 | 128.3 M | The game's own sound banks, `.snd`, in `bgm/`, `bs/`, `chara/`, `env/`, `event/`, `fg/`, `mon/`, `ob/`, `sp/`, `system/`, plus `sy_000.snd`, `rev.bin` and `map_index.txt` (read at `chronicletwo:port/src/mainloop.cpp:~180`). |
| `sound/` | 3,102 | 1,936.0 M | 3,100 `.wav` streams (`%07d.wav`, first match wins), plus whole copies `sound.dat` and `sound.hd3`. Not in the index. |
| `title/` | 10 | 0.09 M | Title and boot UI: `title%d.img`, `lang_select.img`, `hdd*.img`, `hddchk*.mes`, icons. |
| `wep_t/` | 163 | 6.0 M | Weapon models `.chr`, with `_item` variants (`wep_t/%s.chr`, `%s_item.chr`). |
| (root files) | 28 | — | `geo0.cfg`-`geo6.cfg` (georama, `geo%d.cfg` in code), `npc0.cfg`-`npc6.cfg`, `npc.cfg`, `npc_place.cfg` to `npc_place4.cfg`, `place.cfg`, `gyop.cfg` and `uofp.cfg` (both read at `menuaqua.cpp:7169`), `gyorace.cfg`, `edit.cfg`, `mv.cfg` (the movie table, `movieviewlp.cpp:212`), `mv.bak`, `test.stb`, `manifest.json`. |

Whole tree: `data/` has 10,623 files (4.24 GB). Of those, 7,511 are indexed by the port (everything except root `manifest.json`, `movie/` and `sound/`). `port_data/` has 20,870 files (776 MB): 15,623 PNGs, 5,245 catalog sources in `catalog.json` (unverified), a `manifest.json`, and per-directory mirrors of `chara/`, `dungeon/`, `effect/`, `etc/`, `event/`, `img/`, `item/`, `mainchr/`, `map/`, `menu/`, `meswin/`, `sg/`, `title/` and `wep_t/`. `port_data/` has no `dbg/`, `movie/`, `snd2/`, or `sound/`. `port_data/img/` holds numbered subfolders `0`-`6` with root-level texture bundles (`allitem.img`, `esystem*.img`, `font*.img`, `loading.img` and others); the grouping rule was not traced.

## Ixion hooks

- **Second data root.** The data root is process-global (`PathsDataRoot`, `kazarov:src/cpp/platform/paths.cpp`) and the index, catalog and datapacks are all process-global too. The narrowest seam that can serve a second root is `InitCDFile` and `DataReadIndex` (`chronicletwo:port/src/dataread.cpp:336-362`). Direct callers of `PathsDataRoot` that also need the second root are `ezbgm.cpp:121`, `movie.cpp:134` and `main.cpp:272`. `platform/firstrun` does not call `PathsDataRoot`; it receives the root as an argument from `main.cpp:272`.
- **Game-scoped name prefix before `IndexKey`.** `IndexKey` strips everything before a colon (`dataread.cpp:90-137`). A prefix such as `c2:` on a game path would therefore be silently removed, so an Ixion prefix must be intercepted before the key is built, in `ResolveFile`, `LoadFile2`, `LoadFileBG`, `LoadFileCacheBG`, `SearchFileCache` and `CacheKey` (`dataread.cpp:139`).
- **Texture catalog namespacing.** `EnterTexture` and `EnterIMGFile` (`chronicletwo:port/src/mg_texture.cpp:1066-1100`) call `texture_catalog::Find(source_name)`. Ixion can keep a second catalog, or prefix source names at `ResolveFile` so the lookup lands in the right catalog. `texture_catalog::Load` must not run for the second game after the first, because it clears (`kazarov:src/cpp/platform/texture_catalog.cpp:29-30`).
- **Datapacks per game.** `datapacks::Load` takes a single `port_data` root and reads `datapacks/` beside it (`chronicletwo:port/src/platform/datapacks.cpp:237-246`). A second game needs its own pack list or a namespaced `Resolve`.
- **Map registry.** `LoadMapName` and `SearchMapNo` fill and search one table (`chronicletwo:ps2/src/mapselect.cpp:277`, `385`), and the number is what saves store (`savedata.hpp:225`). Ixion can either keep DC2's numbers and append DC1 entries after them, or give each game a numeric range and map at save time. Either way the DC2 numbers must stay stable for existing saves.
- **Map directory routing.** `GetMapPath` (`mapselect.cpp:306`) and `GetLoadMapInfo` (`mapjump.cpp:251`) build `map/...` paths. Routing a map to the other game's root can be done here, or in `LoadMapData` (`sceneload.cpp:25`) where each path is finally formed.
- **Train add-on remap.** The `trn/train` to `trn2/s36` substitution for chapters 6 and 7 (`mapjump.cpp:305-306`) is a chapter-keyed data swap in the add-on loader. It is the one place the DC2 train interior is chosen by data, so it is the natural hook for Ixion's train travel. The train's NPC models are read from `event/train/` (`npccfg.cpp:181`).
- **Per-map script language.** `LoadScript` tries `<name>_<LanguageCode>.stb` first (`mapjump.cpp:388-435`). A cross-game map can use the same rule for its localised scripts.
- **Language unification.** `LanguageCode` is set once (`port/src/mainloop.cpp:99`) and selects `meswin/` folders, gaiji, font tables and the map name table. Ixion needs one value for both games.
- **Model-list names.** `CMdsListSet::LoadPCPFile` refuses a duplicate name (`mdslist.cpp:338-347`). Model-pack names from the two games must therefore be prefixed, or the second load silently fails.
- **Background queue and cache.** The queue has 32 slots and the cache 16 entries, keyed by name (`dataread.hpp:55-60`). Two games streaming at once share both, so Ixion may need a per-game budget.

## Risks and blockers

- **Process-global state.** Data root, index, catalog, datapacks, texture-source registry, current directory, background slots and file cache are all globals (`dataread.cpp:44-62`, `texture_source.cpp:9`, `texture_catalog.cpp:14`, `datapacks.cpp` globals). Loading DC1 and DC2 together needs a per-game object or a careful reset discipline. Calling `DataReadIndex` for the second root wipes the first root's texture-source map (`dataread.cpp:337`).
- **Prefix stripping.** Any game-level prefix collides with `IndexKey`'s colon stripping, as above.
- **Name collisions.** Exact relative-path overlap between the DC2 and DC1 extractions is small: seven files (`meswin/system_1.mes` to `system_6.mes`, and `test.stb`), measured on the two trees. The collision risk is in the shared directory names (`chara/`, `meswin/`, `sound/`, `map/`), because the game code uses those names unqualified. Full overlap was not measured against the DC1 index format.
- **Two Kazarov pins.** DC2 pins a Rust publisher with `data_version` 3. Chronicle pins an older Python extractor with no `data_version.json`. `chronicletwo:docs/PC.md:985` requires both games to build green on any shared Kazarov commit before either pins it. A merged project must choose one commit and re-verify both extractions, or keep two Kazarov checkouts.
- **Data-root defaults differ.** DC2 never probes a local `data/` (`identity.cpp:9-10`), DC1 does. A merged launcher must not let one game's default find the other's data.
- **Disk footprint.** The DC2 extraction is about 5.0 GB (data plus port_data). `sound.dat` duplicates the audio (about 0.97 GB) until playback is confirmed (SOUND_DAT section 6). Movies are about 0.66 GB.
- **Shadowed sound.** `8640040.wav` appears twice; only the first copy is reachable, which is retail behaviour (SOUND_DAT section 3).
- **Missing Japanese messages.** `LANG_JAPANESE` loads `meswin/jpn/gaiji.img`, which the PAL extraction lacks (`gaiji.cpp:15-18`). Port `LoadFile` then exits. The port starts in English or French, so this is reachable only through debug paths (inference).
- **Missing file is fatal.** `LoadFile` exits on a missing file (`dataread.cpp:499-505`). A merged data set with one gap aborts the game at the load that needs it.
- **Re-extraction.** `current` compares source path, size and mtime (`core.rs`, `current()`). A copied or touched disc forces a full re-extract, which takes long and writes about 5 GB.
- **Disc prerequisites.** Each game needs its own disc image or extracted folder. `extract` requires a folder holding `DATA.HD4`, `DATA.DAT`, `SOUND.HD3`, `SOUND.DAT` and `MOVIE` (`archive.rs`, `open_directory` at `213`).

## Open questions

- Does the DC2 `DATA.HD4` record count reconcile? `chronicletwo:docs/PC.md:368` says the PAL `DATA.DAT` holds 8,751 files. The extraction has 7,511 indexed files plus texture payloads that are converted and not written under `data/`. The gap is inferred but not verified against `dc2data list`.
- The contents of `sg/sig/`, `dbg/`, `port_data/img/0`-`6` grouping and `event/train/steam/` were inferred from names and code references, not traced.
- Whether `map/map0.cfg` to `map6.cfg` index by `LanguageCode` as-is for every language (the PAL disc has seven tables; `LANG_CHINESE` and `LANG_KOREAN` are enum values only).
- Whether any DC2 path reads a `host:` file that a DC1 path also writes, since the save tree is searched first for `host:` names (`dataread.cpp:205-222`).
- How the port's `CacheKey` interacts with datapack-overridden files (cache is keyed by name, not by the pack source) (inference).
