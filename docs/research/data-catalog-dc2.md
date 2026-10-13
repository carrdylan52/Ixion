# DC2 data catalogue: Dark Chronicle PAL data tree

## What this covers

A catalogue of the extracted Dark Chronicle (ChronicleTwo, "DC2") PAL data tree: the playable cast (Max, Monica, the ridepod, Monica's monster form), the map registry (towns, Georama houses, dungeons, future-era maps, shared and Ixion/train maps), the world map and Georama configuration, dungeon configuration, bosses from the event viewer, party NPCs and their placement, and the Ixion/train filename search.

Each table row is cross-checked against the ChronicleTwo code that opens the file.

Conventions used below:

- `dc2-data:<path>` is a path relative to the extracted data root (PAL build, read-only).
- `chronicletwo:<path>:<line>` is a line in the ChronicleTwo repository.
- Inference is labelled "(inference)". Everything else was read from a file or line.
- Counts were taken from the tree on 2026-10-13. Japanese-only text is not translated except where an English string exists in the data.

Filename search (case-insensitive, `ixion`, `kisha`, `rail`, `train`): no file name contains `ixion`, `kisha` or `rail`. Train-related names are all `train` (listed under Ixion and trains). The word "Ixion" appears only inside event and map script text, never in a file name or in ChronicleTwo code.

## Key facts

- **Tree size.** 10,623 files, about 4.0 GB. `dc2-data:manifest.json` lists 10,622 files with SHA-256 digests (`dc2-data:manifest.json`). Top-level counts: `map/` 1,828 files, `event/` 2,061, `menu/` 788, `sound/` 3,945 (of which `snd2/` 843), `mainchr/` 177, `chara/` 90, `item/` 168, `dungeon/monster/` 487, `dungeon/robo/` 146, `movie/` 9 `.pss` files.
- **Language indexing.** Several sets exist once per language index: `dc2-data:map/map0.cfg` to `map6.cfg` (map name tables), `dc2-data:npc0.cfg` to `npc6.cfg` (party NPC table), `dc2-data:geo0.cfg` to `geo6.cfg` (Georama analysis), and `dc2-data:menu/0/` to `menu/5/` (menu language directories). The index comes from `LanguageCodeNo` (`chronicletwo:ps2/include/mainloop.hpp:54-63`: 0 Japanese, 1 English, 2 French, 3 German, 4 Italian, 5 Spanish, 6 Chinese, 7 Korean).
- **Map table.** `dc2-data:map/map1.cfg` (English) has 189 `MAP_NAME` records, 185 of them named. `map0.cfg` is the Japanese copy. `dc2-data:map/map.cfg` (86 records, Japanese) is not read by the code; only `map.lst` (`chronicletwo:ps2/src/mapselect.cpp:434`) and `map%d.cfg` (`chronicletwo:ps2/src/mapselect.cpp:281`) are opened.
- **Record layout.** Name, title, add-on path, type, selection type, sound id (6th field), area id (7th field) (`chronicletwo:ps2/src/mapselect.cpp:227-262`). The area id is the world-map `AREA` index (see the table below).
- **Files per map.** The path is derived from the name as `map/<c1>/<c1-3>/<c4-6>/<name>` (`chronicletwo:ps2/src/mapselect.cpp:306-322`). The file set per map uses extensions `.map`, `.mpk`, `.ipk`, `.sky`, `.efp`, `.cfg`, `.stb`, plus rarer `.pcp`, `.div`, `.pcl`, `.ptl`, `.mpl`, `.mpp`, `.mapb`. The load path is `chronicletwo:ps2/src/mapjump.cpp:264-282`.
- **Missing map files.** 181 of 185 named maps have files at the derived path. Four have none: `i01h03`, `i02h02`, `i03h02a`, `d01f02` (the derived directories `map/i/i01/h03/`, `map/i/i02/h02/` and `map/d/d01/f02/` do not exist, and `map/i/i03/h02/` has no `i03h02a.*`).
- **Unregistered map files.** 18 `.map` files exist on disk but have no record in `map1.cfg`. They include `d01f09`, `d02f09`, `d03b03`, `d03b04`, `d03f01s`, `d03f09`, `d04f09`, `d05b99`, `d05f09`, `d05f10`, `d06f97`, `d06f98`, `d06f99`, `f01_2`, `i03h06`, `i03h07`, `z01`, `z99`. Code can only reach a map through `SearchMapNo`, which searches the registered names (`chronicletwo:ps2/src/mapselect.cpp:385`), so these are unreachable by name (inference).
- **Map types.** The enum names only types 1, 2, 4, 5, 6 (`chronicletwo:ps2/include/mapselect.hpp:44-48`: Georama 1, Georama interior 2, interior 4, future 5, future interior 6). Type 3 (58 maps), 7 (41) and 8 (16) are not named in the enum (inference: field and sub-map, dungeon floor, dungeon boss and special room).
- **Selection types.** `MapSelType` 0 to 7: New, Georama, PalmBlinks, Submap, Future, Dungeon, Event, Special (`chronicletwo:ps2/include/mapselect.hpp:29-40`).
- **Chapters.** Progress points come from `PROG_INFO` in `dc2-data:npc_place4.cfg`. The loader keeps (id, chapter, section) (`chronicletwo:ps2/src/vlgr_info.cpp:815-822`, loaded at line 851). Ids 2 to 10 are chapters 1 to 8 (2 is the opening, 3 is chapter 1 section 1), and id 100 is the trial version.
- **Chapter-gated map logic.** In chapters 6 and 7 the add-on path `trn/train` becomes `trn2/s36` (`chronicletwo:ps2/src/mapjump.cpp:305-307`). In chapters 8 and 9 the sky name gets a `b` suffix (`chronicletwo:ps2/src/mapjump.cpp:288-291`).
- **Playable cast.** `USER_CHARA_MAX` 0, `USER_CHARA_MONICA` 1, `USER_CHARA_ROBO` 2, `USER_CHARA_MONSTER` 3 (`chronicletwo:ps2/include/userdata.hpp:21-25`).
- **Max's models.** Max uses `mainchr/c01_base<n>.chr` with `n` = weapon model number + 2, capped at 5 (`chronicletwo:ps2/src/userdata.cpp:1729-1747`). The tree has `c01_base0` to `c01_base4` only, so `c01_base5` is absent (see Risks).
- **Monica's models.** `mainchr/c02_base0.chr` to `c02_base3.chr` are all present (`chronicletwo:ps2/src/userdata.cpp:1739-1747`, `chronicletwo:ps2/src/charasetup.cpp:229-291`).
- **Weapon model numbers.** Seven weapons in `dc2-data:menu/cfg7/wepdat.cfg` have model number 3; counts are 0 (71), 1 (19), 2 (15), 3 (7). The model number is the 7th field of `WEP_SPE` (`chronicletwo:ps2/src/gamedata.cpp:838-860`).
- **Party NPCs.** `dc2-data:npc1.cfg` has 177 `NPC_INFO` rows. Twenty-six (ids 1 to 26) have the debug flag set, and 12 have abilities. The table is loaded by `chronicletwo:ps2/src/npccfg.cpp:89-104`.
- **NPC models.** 176 of 177 NPC model names resolve to `chara/<model>.chr` (or `event/train/t<model>.chr` / `menu/npc/t<model>.chr`). The remaining row is the placeholder `dmy` for Monica (id 260).
- **Dungeons.** Dungeon numbers 1 to 7 map to `map/d/d01` to `map/d/d07`. The event viewer's dungeon column uses the same numbers (`dc2-data:event/view_pal.txt`).
- **Bosses.** The event viewer (`dc2-data:event/view_pal.txt`) has 27 rows whose title starts with the full-width "VS" (battle entries). Section 5 lists them.
- **World map.** `dc2-data:menu/0/wldmap.cfg` has `AREA_NUM 9` (areas 0 to 8). The English file `dc2-data:menu/1/wldmap.cfg` names area 8 "Griffon's Castle". The map image is `wmap<type>.pac` (`chronicletwo:ps2/src/menumap.cpp:1326`).
- **Ixion maps.** `s36` "Ixion (Outer)", `s37` "Ixion (Engine Room)", `s38` "Ixion (Guest Room)" are registered (`dc2-data:map/map1.cfg`). They sit in the shared area 0. The shared train shell `dc2-data:map/cmn/trn2/s36.*` is the add-on for seven maps. Its contents differ from the `s36` folder copy (different MD5, `dc2-data:map/s/s36/`).
- **Event evidence for Ixion.** Event 448 (train development, at `f03i04`), event 600 (launch, at `f03i04`; script text `dc2-data:event/e600/e600/e600_1.txt` and `e600_2.txt` names Ixion, the train and its operator Osmond; the base `e600.txt` names none of them), and event 648 (back into the palace, at `s37`). Viewer rows at `dc2-data:event/view_pal.txt`.
- **Name-keyed code.** ChronicleTwo branches on specific map names: `s07`/`s38` and `s37` camera (`chronicletwo:ps2/src/editctrl.cpp:753-763`), `s07`/`s38` party join (`chronicletwo:ps2/src/menuchr.cpp:1864`), `s12` to `s34` world-map redirect (`chronicletwo:ps2/src/menumap.cpp:807-808`), `f01` to `f04` future maps (`chronicletwo:ps2/src/editloop.cpp:2776-2910`), dungeon entry maps (`chronicletwo:ps2/src/dngmenu.cpp:2733-2757`), and start maps (`chronicletwo:ps2/src/title.cpp:580`, `:708`, `:1086`).
- **PC port jump hooks.** `chronicletwo:port/src/test_hooks.cpp` parses `town:N` (N up to 188), `dungeon:N:F` (N up to 6) and `event:N`. Event numbers are resolved through `event/view_pal.txt` (`ResolveEvent`, `test_hooks.cpp:41-70`).

## How it works

### Tree layout and language indexing

Top-level directories, by role:

- `map/`: map geometry, textures, models, sky, scripts. Subfolders `a` (Straw, Wooden, Brick and Steel house interiors and church), `g` (Georama towns g01 to g05 and their interiors), `i` (town interiors), `s` (sub-maps: stations, train, Ixion, Paznos, Moon Flower sub-areas), `f` (future maps f01 to f04 and interiors), `m` (Palm Brinks), `d` (dungeons d01 to d07), `z` (z01, z99; no code reference found), `cmn` (shared: `bs` battleships, `g00` Georama base, `trn` train shell, `trn2` Ixion shell).
- `chara/` and `mainchr/`: character models. `mainchr` also holds costumes (`c01fuku1..5`, `c02fuku1..5`), hats, shoes, and weapons (`wg`, `wm`, `wr`, `ws` prefixes, plus `ac`, `bo`, `ha`, `sh` for accessories).
- `dungeon/`: `chara` (12 files), `monster` (487 files, boss and monster models), `robo` (146 ridepod parts), `act_script`, `cfg_file` (per-dungeon treasure and floor configs), `msg` (per-dungeon text), `eff_script`, `articles`.
- `event/`: event scripts and models per event number (`e<chapter><nn>`), plus `train/` (train event models), `time_gate/` (red and blue time-gate effects), `talk/`, `boss_btl_lose*.txt`, `view_pal.txt`.
- `menu/`: `0` to `5` are language directories (see below); `cfg5`, `cfg6` and `cfg7` hold item data. Only `cfg7` is opened by code (`chronicletwo:ps2/src/gamedata.cpp:1160`, `:1180-1186`). `cfg5` and `cfg6` are not referenced (inference: stale copies).
- `dbg/`: start-state and debug scripts (`cap1..8.cfg`, `db_cap1..8.cfg`, `game*.cfg`, `pb.cfg`).
- `snd2/`, `sound/`, `movie/`, `title/`, `effect/`, `item/`, `etc/`, `wep_t/`: sound, movies, title art, effects, item models, misc.

The language directory for menus is chosen by `langdirpathTable` = {"0/", "1/", "2/", "3/", "4/", "5/", "1/"} (`chronicletwo:ps2/src/menucommon.cpp:884`). Language 6 therefore reuses `menu/1`, the English art (inference from the table).

Language-indexed script sets follow the same numbering. `npc6.cfg` and `map6.cfg` use `[Uxxxx]` escapes whose code points decode to Korean syllables (for example the name for Charlotte, the Japanese `シャーロット`, is spelled out in Hangul escapes). The enum calls index 6 "Chinese" and index 7 "Korean", and there is no `map7.cfg` (see Open questions).

### Catalogue: characters and models

| Character | User index | Model files in tree | Code | Notes |
|---|---|---|---|---|
| Max | 0 (`USER_CHARA_MAX`) | `mainchr/c01_base2..4.chr` present; `c01_base5.chr` absent; action script `mainchr/c01.stb`; edit-mode model `chara/c01_base.chr`; alternates `c01_event.chr`, `c01_base_f.chr`, `c01c.chr`, `c01d.chr` | `chronicletwo:ps2/src/charasetup.cpp:155-222`; `chronicletwo:ps2/src/userdata.cpp:1710-1750` | Two weapons, gun and wrench per the community wiki (unverified); fishing model `chara/c01_fishing.chr` (`chronicletwo:ps2/src/fishing.cpp:1036`) |
| Monica | 1 (`USER_CHARA_MONICA`) | `mainchr/c02_base0..3.chr` all present; `mainchr/c02.stb`; stray `mainchr/c02.stb_` (not read) | `chronicletwo:ps2/src/charasetup.cpp:229-291` | Two weapons, sword and armband per the community wiki (unverified) |
| Ridepod | 2 (`USER_CHARA_ROBO`) | `dungeon/robo/*.chr` (146 files); `dungeon/act_script/robo.stb` | `chronicletwo:ps2/src/charasetup.cpp:299-340` | Parts loaded by name from `dungeon/robo/` (`chronicletwo:ps2/src/gamedata.cpp:1528-1535`) |
| Monica's monster form | 3 (`USER_CHARA_MONSTER`) | `dungeon/monster/<model>.chr` and `dungeon/act_script/<model>` | `chronicletwo:ps2/src/charasetup.cpp:350-356` | Model name chosen at run time (not traced) |

Character item-model paths (`chronicletwo:ps2/src/gamedata.cpp:1507-1545`): weapons and costumes come from `mainchr/`, ridepod parts from `dungeon/robo/`, everything else from `item/`. Item names and model names are in `dc2-data:menu/cfg7/comdat.cfg` (for example `COM ... "wm001"`).

Dungeon-side character files (`dc2-data:dungeon/chara/`): `c01_base`, `c01_gio`, `c01b_miss`, `c01b_win`, `c02_base`, `c02_gio`, `c02_win`, `c02a_miss`, `c02a_win`, `c01_fishing`, `mints_01in`, `monica_01in`. The suffixes `win`, `miss` and `gio` are unverified (inference: victory pose, miss pose, and a town or event variant).

### Catalogue: party-capable NPCs

The NPC table gives the party roster. Each `NPC_INFO` row holds id, English name, model base name, ability count, point limits and a debug flag (`chronicletwo:ps2/src/npccfg.cpp:48-89`). Selected rows, English names from `dc2-data:npc1.cfg`:

| Id | Name | Model | Place (room in `map1.cfg`, name match: inference) |
|---|---|---|---|
| 1 | Cedric | `p01_03a` | `i01h01` Cedric's Shop |
| 2 | Borneo | `p01_06a` | not matched |
| 3 | Gordon | `p01_18a` | not matched |
| 4 | Donny | `p01_04a` | not matched |
| 5 | Parn | `p01_10a` | `i04h03` Parn's Studio |
| 6 | Dr. Dell | `p01_17a` | `i05h01` Dell Clinic |
| 8 | Claire | `p01_16a` | `i04h02` Claire's House |
| 9 | Pau | `p00_13a` | `s27` Pau's House |
| 12 | Aunt Polly | `p01_02a` | `i01h02` Polly's Bakery |
| 14 | Sheriff Blinkhorn | `p01_05a` | `i01h06` Police Station |
| 16 | Gerald | `p01_11a` | `i04h01` Gerald's room |
| 17 | Mayor Need | `p01_01a` | `i03h01a` Mayor's Office |
| 18 | Priest Bruno | `p01_27a` | `a20i01` Church Interior |
| 26, 251 | Lin | `p00_28a` | `g02i02` Lin's House |
| 33 | Morton | `p01_26a` | `i04h05` Morton's House |
| 200 | Lao Chao | `p00_19a` | `f02i08` Lao Chao's Bistro |
| 205 | Great Sage Crest | `p00_16a` | (future, Balance Valley) |
| 260 | Monica | `dmy` | placeholder |
| 300 to 329 | Luna Lab staff (for example Alec 300) | `p03_11a` etc. | `f03i03xx` labs |
| 301 | Osmond | `p00_31a` | `f03i0301` (event 412 names it, `view_pal.txt`) |
| 303 | Dr. Nobb (Japanese "Dr. Chap") | `p00_32a` | `f03i0302` (event 428, `view_pal.txt`) |
| 400 | Galen Agaris | `p00_05a` | not matched |

The placement scripts are `dc2-data:npc_place4.cfg` (141 `NPC` blocks; `PROGRESS` plus `NOON_PLACE` and `NIGHT_PLACE` place ids) and `dc2-data:place.cfg` (935 lines). Only `npc_place4.cfg` is opened (`chronicletwo:ps2/src/vlgr_info.cpp:835-858`). The older `npc_place.cfg` to `npc_place3.cfg` are not read.

Event-only models include Griffon (`event/e612/e612_griffon.chr`, `event/e640/e640_griffon.chr`, `event/e716/e716_griffon.chr`), Guiltoni (`event/e00/e50/e50_guiltoni.chr` and several `e3xx`/`e5xx` copies), Osmond's Ixion scene (`event/e600/e600/e600_osmond.chr`), and Halloween (`event/e100/e110/e110_halloween.chr`). Steve's model is `chara/e105_steve.chr` (party table id 32).

### Catalogue: towns, areas and eras

Area ids come from the 7th field of each map record and index the English world-map table (`dc2-data:menu/1/wldmap.cfg`).

| Area | World-map name (English) | Georama town (type 1) | Future map (type 5) | Interiors | Dungeons (map dirs) | Story events |
|---|---|---|---|---|---|---|
| 1 | Palm Brinks | none (town maps `m01` to `m08`, type 3) | none | `i01h01` to `i05h01` shops and houses, `i04h05` | `d01` Channel Reservoir (`d01b01`, `d01e01`, `d01f01`, `d01f02` missing, `d01f09`) | 1xx (chapter 1) |
| 2 | Sindain | `g01` | `f01` Jurak Mall | `g01i07` Dwarves' House | `d02` Rainbow Falls and Rainbow Butterfly Wood (`d02b01..03`, `d02f01`, `d02f01r`, `d02f01s`, `d02f09`) | 2xx (chapter 2) |
| 3 | Balance Valley | `g02` | `f02` Starlight Temple | `g02i02` Lin's House, `f02i06`, `f02i07`, `f02i08` | `d03` Starlight Canyon and Lighthouse on the Cape (`d03b01..04`, `d03f01..03`, `d03f01r..`, `d03f09`) | 3xx (chapter 3) |
| 4 | Veniccio | `g03` | `f03` Luna Lab | `f03i04` Central Lab, `f03i0301..04` labs | `d04` Ocean's Roar Cave (`d04f00..02`, `d04b01` Shigura Village, `d04f09`) | 4xx (chapter 4) |
| 5 | Heim Rada | `g04` | `f04` Gundorada Workshop | `f04i03`, `f04i04`, `f04i05` | `d05` Mount Gundor (`d05b01`, `d05b99`, `d05f01..02`, `d05f09`, `d05f10`) | 5xx (chapter 5) |
| 6 | Kazarov Stonehenge | none | none | none | none (`s11`, `s98`, `s66`) | not in event viewer |
| 7 | Moon Flower Palace | `g05` | none | none | `d06` Moon Flower Palace and Palace Terrace (`d06b01..03`, `d06e01`, `d06f01..03`, `d06f97..99`) | 6xx to 7xx (chapters 6 and 7) |
| 0 | Common Area | none | Paznos-era `s29`, `s30`, `s39`, `s48` (type 5) | Ixion `s36` to `s38`, Lapis chambers `s13` to `s16`, Zelmite Mine `d07` (`d07b01`, `d07f01`), `s52`, `s61` to `s63`, `s69` | `d07` Zelmite Mine; `d06b01`, `d06b02` | mixed |

Map type counts (185 named maps): type 1: 6 (Georama towns and Paznos event), type 2: 17 (Georama houses), type 3: 58, type 4: 28 (town interiors), type 5: 9 (future and Paznos), type 6: 10 (future interiors), type 7: 41 (dungeon floors, inference), type 8: 16 (dungeon boss and special rooms, inference).

Selection type counts: 1 (Georama) 24, 2 (Palm Brinks) 32, 3 (submap) 26, 4 (future) 16, 5 (dungeon) 56, 6 (event) 24, 7 (special) 7.

Eras. The Georama towns (`g`, type 1 and 2) are the towns Max's side rebuilds with Geostones. Their future counterparts are the `f` maps (types 5 and 6, one per town from Sindain to Heim Rada), where the enum comment reads "a map of the future, where the time board and world map are hidden" (`chronicletwo:ps2/include/mapselect.hpp:47`). The community wiki (Dark Chronicle page) places Max's time as the past and Monica's as the future, 100 years apart; that is outside the data and is not verified here. The Paznos-era maps `s29`, `s30`, `s39` and `s48` carry the future type (5), which is consistent with the Paznos base being future-side (inference).

### Catalogue: dungeons

Map directories per dungeon (from `dc2-data:map/d/`), with names from `map1.cfg`:

| No. | Name (English) | Map dirs | Dungeon config | Boss rows (viewer id, floor) |
|---|---|---|---|---|
| 1 | Channel Reservoir (sewers under Palm Brinks) | `d01/b01`, `d01/e01`, `d01/f01`, `d01/f09` | `dungeon/cfg_file/d01f01.cfg`, `tbox_d01.cfg` | Linda (21010, floor 4); Halloween (21020, floor 7) |
| 2 | Rainbow Falls, Rainbow Butterfly Wood | `d02/b01..03`, `d02/f01`, `d02/f01r`, `d02/f09` | `d02f01.cfg`, `tbox_d02.cfg` | Butterfly (22030, floor 15) |
| 3 | Starlight Canyon, Lighthouse on the Cape | `d03/b01..04`, `d03/f01..03`, `d03/f09` | `d03f01..03.cfg`, `tbox_d03.cfg` | Memo Eater (23020, floor 18); Gaspard and Fire (23030, floor 23) |
| 4 | Ocean's Roar Cave, Shigura Village | `d04/b01`, `d04/f00..02`, `d04/f09` | `d04f00..02.cfg`, `tbox_d04.cfg` | Puppet Shigura (24010, floor 9); Jaming and Shingala (24020, floor 20) |
| 5 | Mount Gundor | `d05/b01`, `d05/b99`, `d05/f01..02`, `d05/f09`, `d05/f10` | `d05f01.cfg`, `tbox_d05.cfg` | Gaspard 2 (25020) and Monster Gaspard (25030), floor 22; Death Ark (25010, floor 16, in `s20`) |
| 6 | Moon Flower Palace | `d06/b01..03`, `d06/e01`, `d06/f01..03`, `d06/f97..99` | `d06f01..03.cfg`, `tbox_d06.cfg` | Sirus (26050, floor 0); Emperor Griffon 1-3 (27010, floor 27); Dream Spiral 1 to 5 (27020 to 27060); Dark Element (27070) |
| 7 | Zelmite Mine | `d07/b01`, `d07/f01` | `d07f01.cfg`, `tbox_d07.cfg` | Metal Flotsam (28010, floor 27); Dark Genie (28020, floor 38) |

Also present: `dc2-data:dungeon/cfg_file/tbox_d08.cfg`, whose header reads as a second back dungeon (inference from the Japanese comment). There is no `d08` map directory or registry entry.

Shared bosses placed in common maps (viewer rows): Trentos (26010, `s13`, dungeon 2 floor 12), Lapis Garter (26020, `s14`), Sea Dragon (26030, `s15`), Inferno (26040, `s16`), Memo Eater (`s18`), Death Ark (`s20`), Flotsam subgame (22010, `s03`), King Mardan fishing (22020), Boss Sfida (23010, no map).

Dungeon text and scripts: `dc2-data:dungeon/msg/d01_<lang>.mes` (`chronicletwo:ps2/src/dng_main.cpp:518`), per-monster talk `dungeon/msg/mostalk<n>_<lang>.txt` (`chronicletwo:ps2/src/event_func.cpp:4488`), dungeon script `map/d/d0N/d0N_<lang>.stb` (`chronicletwo:ps2/src/dng_main.cpp:952-957`), treasure config `dungeon/cfg_file/tbox_d0N.cfg` (`chronicletwo:ps2/src/dngmenu.cpp:2847`).

Boss models: `dc2-data:dungeon/monster/` holds `b01a` to `b18a` (for example `b08a.chr`, `b09a.chr`, `b10a.chr`), `lin_boss.chr`, and `atora_*` (Atlamillia monsters). Event-local boss models are named by event, for example `event/e700/e716/e716_boss08a.chr`. Linking an event-local model to a viewer row is inference from the naming.

### Catalogue: world map and Georama

- `dc2-data:menu/0/wldmap.cfg`: `POS` rows (position, area, event number in the last fields) and `AREA` rows with names (`chronicletwo:ps2/src/menumap.cpp:478-490`). `menu/0` is the Japanese copy; `menu/1` is the English copy.
- `dc2-data:menu/<n>/wmap1.pac` to `wmap4.pac`: world map images chosen by save flags `SAVE_FLAG_WORLD_MAP_1..4` (`chronicletwo:ps2/src/menumap.cpp:1300-1330`). `menu/0` also has `wmap.cfg`.
- Georama analysis: `dc2-data:geo<n>.cfg` holds one `GEO_ANALYZE` block with 108 `ANALYZE` and 98 `CONDITION` entries in every language, so each file is a per-language copy of one rule set (compare `dc2-data:geo0.cfg` with `geo1.cfg`). The loader is `LoadEditAnalyzeData(int area_no, ...)`, which is called with the language code (`chronicletwo:ps2/src/mainloop.cpp:452`, `chronicletwo:ps2/src/editdata.cpp:908-930`). The parameter name is misleading. Which town each rule applies to is not traced (open question).
- Georama houses (`a01ia..id`, `a02ia..id`, `a04..`, `a05..`, `a20i01`) are type 2 maps in area 1 (Palm Brinks houses) and area 0 (shared).

### Catalogue: train and Ixion assets

Filename search results (case-insensitive): no `ixion`, `kisha`, or `rail` file names. Train-related files:

- Shared train shell: `dc2-data:map/cmn/trn/train.{map,mpk,ipk}`. Used as the add-on `trn/train` by `i02h01`, `s01`, `s02`, `s04`, `s09`, `s10` (`dc2-data:map/map1.cfg`).
- Ixion shell: `dc2-data:map/cmn/trn2/s36.{map,mpk,ipk}`. Used as the add-on `trn2/s36` by `s11`, `s12`, `s31`, `s34`, `s53`, `s58`, `s71`. In chapters 6 and 7, `trn/train` is replaced by `trn2/s36` at load time (`chronicletwo:ps2/src/mapjump.cpp:305-306`).
- Ixion maps: `s36` (outer; no `.stb`; `.sky` present), `s37` (engine room; `.stb` with 5 localized copies `_1` to `_5`), `s38` (guest room; `.stb`). `map/s/s38/` also holds a stray copy of `i03h02.*` (inference: leftover).
- Station and train-interior maps: `s01` Channel Reservoir station, `s02` Sindain Station, `s03` Forest Tunnel, `s04` Balance Valley Station, `s07` inside train, `s08` locomotive, `s09` Veniccio Station, `s10` Heim Rada Stop, `s12` / `s31` / `s34` Moon Flower Palace stops, `s58` Subdimension.
- Train event models: `dc2-data:event/train/` (33 entries, `tp00..tp02` plus `steam/`), `event/nanahige/`, `event/lm/train.chr`, `event/e600/e600/e600_chap.chr`, `event/e200/e202/e202_train_pika.chr`. Train HP image `train_hp` is read in `chronicletwo:ps2/src/pbuggy.cpp:516`.
- Ixion events (viewer rows): 448 (train development, `f03i04`, chapter 4), 600 (launch, `f03i04`, chapter 6), 648 (back into the palace, `s37`, chapter 6), 616 (temporary return, `s70`, chapter 6), 640 (chrono union, `s66`, chapter 6). Event folders `dc2-data:event/e400/e448/`, `e600/e600/`, `e600/e616/`, `e600/e648/` contain the script text that names "Ixion" (`e448_1..5.txt`, `e540_*.txt`, `e600_*.txt`, `e616_*.txt`, `talk/npc_talk_c6_*.txt`).

Time travel items: Atlamillia models `dungeon/eff_script/atora*.chr`, `dungeon/monster/atora_*.chr`, and `event/e700/e728/atora_*.chr`. Time-gate effects `event/time_gate/red/` and `blue/`, and `effect/tg_*.chr`. Viewer row 522 (red Atlamillia glows blue, `f04`, chapter 5) and row 523 (red Atlamillia time warp to the past; the map column is blank, chapter 5).

### Catalogue: debug entry points

- Start states: `dc2-data:dbg/cap1.cfg` to `cap8.cfg` set `PROGRESS` to 2, 4, 4, 6, 7, 8, 9, 10 (chapters 1 to 8). `db_cap*.cfg` is the debug variant (`chronicletwo:ps2/src/mainloop.cpp:1357-1365`). `game*.cfg` (for example `game1.cfg`) load through `dbg/game%d.cfg` (`chronicletwo:ps2/src/mainloop.cpp:1057`).
- Port jump: `town:N` loads `dbg/pb.cfg` and enters the map table at index N; `dungeon:N:F` loads `dbg/cap1.cfg` (`chronicletwo:port/src/test_hooks.cpp:176-210`).

## Ixion hooks

1. **Map registry.** Append cross-world records to the map name table. `LoadMapName` reads `map<lang>.cfg` at load (`chronicletwo:ps2/src/mapselect.cpp:277-291`). `mlMAP_NAME_NUM` preallocates by count (`chronicletwo:ps2/src/mapselect.cpp:205-225`), so the count line must change with any addition. Name lookup is linear (`SearchMapNo`, `chronicletwo:ps2/src/mapselect.cpp:385`).
2. **Single map-load funnel.** `GetLoadMapInfo` (`chronicletwo:ps2/src/mapjump.cpp:251`) resolves a map to its directory, sky, add-on path, and script. The existing precedent is the chapter-6/7 swap at `chronicletwo:ps2/src/mapjump.cpp:305-306`. A cross-world load can remap a DC1 town to a DC2 file set here, or add an add-on shell the same way `trn2/s36` is added.
3. **Progress gating.** `GAME_PROGRESS_INFO.chapter` (`chronicletwo:ps2/include/vlgr_info.hpp:44-48`) drives swaps and sky names. Ixion can gate cross-world behaviour on the chapter the save is in.
4. **Model selection.** `GetMainCharaModelName` (`chronicletwo:ps2/src/userdata.cpp:1710`) and `SetupMainUnit` (`chronicletwo:ps2/src/charasetup.cpp:140`) choose the model per user index. A DC1 cast member can be routed through the same `USER_CHARA_*` slots, or given a new slot beyond 3.
5. **Party roster.** The `NPC_INFO` table (`chronicletwo:ps2/src/npccfg.cpp:48-89`, `GetPartyNPCData` in `chronicletwo:ps2/include/npccfg.hpp:122`) is the roster source. New DC1 party entries would need ids outside the used ranges (1 to 26, 32 to 34, 50 to 62, 100 to 105, 150 to 172, 200 to 214, 250 to 260, 300 to 329, 400 to 413, 1012 to 1018 in `npc1.cfg`).
6. **NPC placement by progress.** `niNOON_PLACE` and `niNIGHT_PLACE` (`chronicletwo:ps2/src/vlgr_info.cpp:420-460`) read `npc_place4.cfg`. Cross-world NPCs can be placed per progress id.
7. **World map.** Add areas by appending `AREA` rows to `menu/<lang>/wldmap.cfg` (`chronicletwo:ps2/src/menumap.cpp:484`). A new area id needs a matching `AREA` row and a `POS` row. The existing redirect at `chronicletwo:ps2/src/menumap.cpp:807-808` (`s12` to `s34`) is a model for a save-flag-driven jump.
8. **Train as add-on.** The `trn/train` versus `trn2/s36` decision (`chronicletwo:ps2/src/mapjump.cpp:297-313`) is the natural place to choose an Ixion-owned train shell for DC1-linked stations. The thirteen maps that use `trn/train` (six) or `trn2/s36` (seven) are listed above.
9. **Event jumps.** The PC port's `event:N` jump (`chronicletwo:port/src/test_hooks.cpp:41-70`) already resolves an event number to a map through `view_pal.txt`. It can serve as a test harness for Ixion scenes.
10. **Debug start states.** `dbg/cap*.cfg` and `dbg/pb.cfg` use a small command language (`PROGRESS`, `ITEM_SET`, `GET_ITEM`, `EQUIP`, `HP`, `DEFENSE`). The same format can seed a mixed party for testing.
11. **Name-keyed branches.** `s37`, `s38`, `s07` camera and party rules (`chronicletwo:ps2/src/editctrl.cpp:753-763`, `chronicletwo:ps2/src/menuchr.cpp:1864`) are the places where Ixion-specific maps already get special handling. Any new Ixion map should copy this pattern rather than adding ids.

## Risks and blockers

- **Missing Max model.** `c01_base5.chr` is requested when the equipped melee weapon has model number 3, which seven weapons do (`chronicletwo:ps2/src/userdata.cpp:1729-1747`). The file is absent from the tree. The effect at run time is not traced (inference: model load fails silently). Test the seven weapons with Max equipped before using the Max model path in Ixion.
- **Missing map files.** `i01h03`, `i02h02`, `i03h02a` and `d01f02` have records but no files at the derived path. Any route into them crashes or fails the load (inference: `scene->LoadMap` returns negative, `chronicletwo:ps2/src/mapjump.cpp:231`).
- **Orphan map files.** 18 map folders are unregistered. Do not assume they load; the registry is the only route in.
- **Language index drift.** `map6.cfg` and `npc6.cfg` contain Korean escapes while the enum names index 6 "Chinese". `menu/` language 6 reuses English art. Any DC1 text merge must agree with this numbering before shipping.
- **Duplicate Ixion shell.** `dc2-data:map/cmn/trn2/s36.*` and `dc2-data:map/s/s36/s36.*` differ by hash. The sub-map and the add-on each use their own copy. Changing one without the other shows the wrong shell in some routes.
- **Chapter gating.** The train swap and the sky suffix both depend on chapter numbers. A DC1 integration that changes progress ids will shift these.
- **Index size.** The PC port's file index expects 10,240 files as a reserve hint (`chronicletwo:port/src/dataread.cpp:34`, `:300`). Only 7,511 files are indexable after the excluded roots `manifest.json`, `movie`, `sound`, `port_data` (`chronicletwo:port/src/dataread.cpp:36-38`). The hint has no correctness impact.
- **Build coupling.** Everything here is the PAL tree. NTSC or other regional data was not checked. Do not copy game data into the repository; keep it in the git-ignored data area.

## Open questions

- Does `c01_base5.chr` exist in another data source, or is the weapon model-3 path unreachable in practice? Which seven weapons have model number 3, and which can Max equip?
- Are `c01_base0.chr` and `c01_base1.chr` used by any path? The Max code path starts at 2.
- What is the purpose of the `r`, `s`, `b99`, `f09`, `f97` to `f99`, `f10`, `b03`, `b04` and `_2` map variants? Which of them are reached only through a `_2` suffix in `editloop.cpp:2779-2780`?
- Which Georama rule set applies to which town? The `geo<n>.cfg` files are per-language copies of one set (108 `ANALYZE`, 98 `CONDITION`). The per-town binding is not traced.
- Is `z01`/`z99` referenced? No name match was found in ChronicleTwo sources. Is it a title or ending scene loaded by file name?
- Is `dungeon/cfg_file/tbox_d08.cfg` (second back dungeon) reachable? There is no `d08` map and no caller for `tbox_d08`.
- `dc2-data:dbg/cap3.cfg` and `db_cap3.cfg` set `PROGRESS 4` (chapter 2) while the comment says chapter 3 (progress 5). `db_cap4.cfg` sets `PROGRESS 46` while `cap4.cfg` sets 6. Are these intentional?
- The `.mapb` files (`map/cmn/g00/g00.mapb`, `map/i/i04/h01/i04h01a.mapb`) are not referenced by name in `ps2/src`. What loads them?
- Japanese-only sources: `dc2-data:map/map.cfg` and `dc2-data:event/view.txt` contain titles and names not present in the English tables. A translation pass would need a reviewer.
- Event 448 and event 600 are the Ixion development and launch events. The exact chapter gating for the first Ixion ride (for example, whether the chapter-6 train swap begins before or after event 600) is not traced.
