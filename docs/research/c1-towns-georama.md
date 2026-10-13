# Chronicle (DC1) towns and Georama

## What this covers

How Chronicle (DC1) represents its five Georama towns and the sub maps that share the same editor loop: how a map number becomes a loaded town, what the town script and villager data drive, how the player's Georama ground and Atla progress persist in the save, and where Ixion could enter a town directly or redirect its state. Scope is `ps2/src` (retail units, which the PC port compiles unchanged except for `PORT_OVERRIDE` bodies in `port/src`), with the port overrides noted where they differ. Dungeons, the battle system and the DC2 side are only touched where a town hands off to them.

Citations: `chronicle:` is the `c1` checkout, `refs/` is the community reference set.

## Key facts

- The five Georama towns are `TOWN_NORUNE=0`, `TOWN_MATATAKI=1`, `TOWN_QUEENS=2`, `TOWN_MUSKA_LACKA=3`, `TOWN_YELLOW_DROPS=4`, with `TOWN_COUNT=5` (`chronicle:ps2/include/editground.hpp:14-20`). Muska Lacka is spelled "Muska Racka" in some code comments (`chronicle:ps2/include/editground.hpp:117`, `chronicle:ps2/include/editground.hpp:571`).
- A town's map number is its `MapNo`, and its data folder is `gedit/eNN` with `NN = MapNo + 1` (`chronicle:ps2/src/editloop.cpp:722`). The docs agree: `e0N` is town N, 1 to 5 (`chronicle:docs/PC.md:674`). The data tree on disk has `gedit/e01` to `gedit/e05` only.
- Sub maps use `MapNo` 11 and up, mapped to `gedit/sNN` with `NN = MapNo - 10` (`chronicle:ps2/src/editloop.cpp:728-734`). `MapNo` 99 is the interior test map (`chronicle:ps2/src/editloop.cpp:739`). The data tree has no `s02`, `s05` to `s08`, `s10`, `s18` to `s20` folders.
- Dark Heaven Castle is not a Georama town. The dungeon enum says `DUNGEON_GALLERY_OF_TIME = 5` is "Dark Heaven Castle in the map files" (`chronicle:ps2/include/dungeon.h:13`). On the world map it is place 14, mapped to `MapNo` 205 (`chronicle:ps2/src/battlemenu.cpp:8771`).
- The world-map table `MenuGrobalMapNoTbl[16]` maps places to map numbers: Norune 0, Matataki 1, Queens 2, Muska Lacka 3, Yellow Drops 4, dungeons 200 to 205 (Divine Beast Cave, Wise Owl Forest, Shipwreck, Sun and Moon Temple, Moon Sea, Gallery of Time), and Demon Shaft 60, which is a sub map (`chronicle:ps2/src/battlemenu.cpp:8771`, names in `chronicle:ps2/include/battlemenu.hpp:281-297`). The sub-map entries are MapNo 14 (s04), 42 (s32), 23 (s13) and 40 (s30), at table indexes (places) 4, 8, 10 and 13.
- `MapNo` below 200 selects `GAME_MODE_EDIT`; 200 to 299 selects `GAME_MODE_DUNGEON` with dungeon `MapNo - 200` (`chronicle:ps2/src/main.cpp:982-996`; port mirror `chronicle:port/src/gameloop.cpp:409-422`).
- `MapJump(map_no, event_no)` only sets `NextMapNo` and `StartEventNo`; the main loop applies them at the next mode switch (`chronicle:ps2/src/main.cpp:1053-1056`, `chronicle:ps2/src/main.cpp:982-986`). The port exposes it as `MapJump__Fii` (`chronicle:port/src/main.cpp:520`).
- `EditInit` is the single arrival function for every editor map. It is called from the mode switch with a null parameter (`chronicle:ps2/src/main.cpp:670-671`; port body `chronicle:port/src/editloop_init.cpp:124`).
- Only towns persist Georama ground. `EditSave` and `EditLoad` are guarded by `MapNo < TOWN_COUNT` for the ground and parts info, while the clock is saved for every map (`chronicle:ps2/src/editloop.cpp:440-466`).
- The save slot's resume map is `CSaveData::map_no` at byte offset 0x1C8 (`chronicle:ps2/include/savedata.hpp:120`; the offset is hard-coded in `chronicle:ps2/src/main.cpp:727`, `chronicle:ps2/src/title/titleloop.cpp:699` and `chronicle:port/src/gameloop.cpp:69`). The offset follows from the struct layout (`config[18]` at 72 bytes plus `chara_name[6][32]` at 384 bytes gives 456, which is 0x1C8). In sample save images from the Chronicle test runs, the value at 0x1C8 read back as 0 for Norune saves (unverified: the sample saves were not re-read in this check).
- `CSaveData` is 78272 bytes (`chronicle:ps2/include/savedata.hpp:501`). The 0x136A7-byte save image is that struct, a 32-byte version string, and one checksum byte per 64 bytes (`chronicle:docs/PC.md:1128-1135`; 1223 checksum bytes, consistent with the sizes).
- Georama progress is stored per town in `georama[6]`, an `SV_GEORAMA_DATA` of 104 bytes of request data, 24 `SV_EDIT_PARTS_INFO` plots, 130 `SV_GRD_PART` placed-part records, and 20 `SV_GRD_NPC` slots (`chronicle:ps2/include/savedata.hpp:63-101`). Its element chips are `elem_data[6][128]` (`chronicle:ps2/include/savedata.hpp:130`).
- Sub maps have no Georama ground of their own. Their NPC slots live in `special_npc[320]`, selected from a fixed list of six maps `{14, 23, 11, 19, 42, 38}` (`chronicle:ps2/src/savedata.cpp:215-240`; the list is verified, the 320 and 12-byte sizes are unverified).
- The clock is `CSaveData::now_time` in units from 0 to 12, where each unit is two displayed hours (`chronicle:ps2/src/edit.cpp:2872-2892`; loaded by `chronicle:ps2/src/editloop.cpp:466`). The day counter advances when the clock crosses 8.5 (`chronicle:ps2/src/savedata.cpp:65-80`).
- The town's time period is `EdGetTime(clock)`, which returns `ED_TIME_DAY`, `EVENING`, `NIGHT` or `MORNING` by threshold ranges (`chronicle:ps2/src/editloop3.cpp:1724-1748`, enum at `chronicle:ps2/include/editloop3.hpp:13-16`).
- The player's model in every town is `chara/c01d.chr`, and the party index is reset to 0 on arrival (`chronicle:ps2/src/editloop.cpp:1003`, `chronicle:ps2/src/editloop.cpp:1135`; port `chronicle:port/src/editloop_init.cpp:418`).
- Villagers in towns are drawn at random from a roster of up to 15 IDs (`PEOPLE_LIST`), reshuffled on every entry with `rand()` (`chronicle:ps2/src/editloop3.cpp:673-705`, called from `chronicle:ps2/src/editloop.cpp:1000` and `chronicle:port/src/editloop_init.cpp:415`). No save field for the roster was found, so it is not persisted (inference from the struct layout).
- A town's placed parts are capped by the plot's stock: `SetMapParts` refuses when `placed == stock` (`chronicle:ps2/src/editground.cpp:113-118`).
- Atla pickups are routed by dungeon index: `getAtraToSaveData(atra, ..., dungeon, ...)` calls `AtraPartsGet(dungeon, plot)` for IDs below 40 and `AtraChipGet(dungeon, id - 40)` otherwise (`chronicle:ps2/src/btmisc.cpp:238-246`). So dungeon `d` feeds Georama `d`.
- Atla visibility for a map uses `GetNowMapTransAtraMap`, which sends sub maps 11 to 40 to a village through a 35-entry table (indexes 0 to 29 are the ones used), sends `MapNo` 200 and up to `MapNo - 200`, and clamps to the Atla village count (`chronicle:ps2/src/menu_draw.cpp:134-176`).

## How it works

### Map numbers and the world map

Three number spaces meet in the town code, and they are easy to conflate:

- `MapNo` below 200: the editor loop (towns and sub maps). Towns are 0 to 4, sub maps 11 and up, interior test 99.
- `MapNo` 200 to 299: dungeons. `MapNo - 200` is the dungeon index (`chronicle:ps2/include/dungeon.h:4-13`). Dungeon 6 (Demon Shaft) is not reached through `MapNo` 206; the world map uses 60 for it.
- `MapNo` 400, 800, 801, 1000: opening, title, attract movie and save-ending sentinels (`chronicle:ps2/src/main.cpp:988-1027`).

Town and dungeon index reference (from the enums, `MenuGrobalMapNoTbl`, and the save layout):

| Town | MapNo | Data folder | Georama index | World-map place | Request check |
|---|---|---|---|---|---|
| Norune | 0 | `gedit/e01` | 0 | 0 | `NornRequest` (`parts_max` 8) |
| Matataki | 1 | `gedit/e02` | 1 | 2 | `MatatagiRequest` |
| Queens | 2 | `gedit/e03` | 2 | 5 | `QueensRequest` |
| Muska Lacka | 3 | `gedit/e04` | 3 | 7 | `MuskaRequest` |
| Yellow Drops | 4 | `gedit/e05` | 4 | 11 | `YellowRequest` |

Georama index 4 is also the one the robot-workshop script opcode clears (`chronicle:ps2/src/editloop.cpp:3674-3695`, `_DELETE_ROBO_PARTS` at `chronicle:ps2/src/editloop3.cpp:5514-5517`). Dungeon index `d` (`MapNo` 200 + d, `chronicle:ps2/include/dungeon.h:4-13`) maps to world-map entries 200 (Divine Beast Cave), 201 (Wise Owl Forest), 202 (Shipwreck), 203 (Sun and Moon Temple), 204 (Moon Sea), 205 (Gallery of Time); Demon Shaft is 60 (sub map `s50`) in the same table. A read-only check of a sample save agrees with this layout: the Norune `request_count` at the expected offset reads 8, which is the `parts_max` that `NornRequest` sets (`chronicle:ps2/src/editground.cpp:2430`) (unverified: the sample save was not re-read in this check).

The developer menu's town row (`e0N`, N from 1 to 5) enters `GAME_MODE_EDIT` with `main_select_menu_no` set to N-1, which is the town's `MapNo` (`chronicle:docs/PC.md:673-674`). The story-event row in the same menu hard-codes three `MapJump` pairs: map 23 with event 310, map 41 with 150, map 19 with 305 (`chronicle:ps2/src/main.cpp:1257-1258`).

### Arrival: what EditInit does

`EditInit` (`chronicle:ps2/src/editloop.cpp:703`) runs in this order, with the port's copy mirroring it (`chronicle:port/src/editloop_init.cpp:124-550`):

1. Marks the map visited (`VisitMap(MapNo, 1)`, line 711) and sets `NowEditMap = MapNo` (line 718).
2. Builds `EditMapName` and `EditDataDir` (`gedit/eNN/`, or `gedit/sNN/`, or the interior test folder) (lines 720-745).
3. Allocates the editor arenas and loads the map's `mapinfo` script through `LoadEditMapData` (lines 757-781; text fallback from `.cfb` to `.cfg`, `chronicle:ps2/src/editmapscript.cpp:524-560`).
4. Plays the map BGM and ambient sound, unless `StartEventNo >= 0`, in which case the BGM load is skipped (`chronicle:ps2/src/editloop.cpp:833-846`).
5. Loads event scripts through `LoadScript` (line 886; `chronicle:ps2/src/editloop.cpp:327`): the shared `event.stb`, the map's `_<lang>.mes` text, and the system `event.stb`.
6. Loads the ground for towns only through `LoadGroundData` (lines 899-900; `chronicle:ps2/src/editloop.cpp:4794`), which builds the sky, sun, area grids, motion parts and the placement cursor (the cursor model always comes from `gedit/e01`, line 4889), and calls `EditPartsInfo.Initialize(NowEditMap)` and `LoadObjectParts`.
7. Restores the Georama state with `EditLoad` (lines 917-918), except on one path described below.
8. Builds the villager tables (lines 1000-1001) and loads the player model (line 1003).
9. Runs the start event: `RunEvent(128)` when `StartEventNo < 0`, otherwise the requested event (lines 1129-1131; port `chronicle:port/src/editloop_init.cpp:541-546`). The event is consumed and `StartEventNo` reset (line 1134).

Event 128 is the ordinary arrival event for a town. The script content was not decoded in this pass.

The developer-menu path is different: when `old_main_mode == 7` and `main_select_padrup == 0`, `EditInit` does not call `EditLoad`. It marks the first 22 plots obtained with every element enabled, clears all 128 element chip slots to empty, and loads `gdata0.edt` from the data root (`chronicle:ps2/src/editloop.cpp:917-953`; port `chronicle:port/src/editloop_init.cpp:339-380`).

### Town script and villagers

`LoadEditMapData` runs the map's script, which is either compiled (`.cfb`, a numbered command stream) or text (`.cfg`), and each command writes the `EDIT_MAP_INFO` (`chronicle:ps2/include/editloop.hpp:307-370`). The commands that matter for towns:

- `PEOPLE` appends one villager record: name, character, model, weapon, initial motion, speed, position and rotation (`chronicle:ps2/src/editmapscript.cpp:1674-1695`). Up to 16 records (unverified).
- `PEOPLE_LIST` gives the roster of up to 15 villager IDs (`chronicle:ps2/src/editmapscript.cpp:1946-1952`).
- `TIME_TABLE_NO` and `TIME_TABLE` write weekly schedule rows `time_tables[week][row][16]` (`chronicle:ps2/src/editmapscript.cpp:1698-1725`).
- `ENTRANCE` and `MAPJUMP` define door and map-jump event points (`chronicle:ps2/src/editmapscript.cpp:1575-1660`). The `ENTRANCE` side letter sets `side`, and the point's `map_no` comes from the last `MAPJUMP`.

After the script runs, for towns only, the first 16 villager records take their name, character, model and hide flag from the compiled default table `EditCharaData[6][20]` (`chronicle:ps2/src/editmapscript.cpp:165`, copy at lines 698-709). So for towns the script's `PEOPLE` names and models are overwritten by that table. Positions and motions from `PEOPLE` survive.

The villager set is then selected in three steps:

- `EdCreateVillagerTable` shuffles the roster `people_list[0..14]` with `rand()` for each of the four periods and writes the first ten into `time_tables[0][period]` (`chronicle:ps2/src/editloop3.cpp:673-705`). This overwrites the first ten entries of week 0 rows 0 to 3 of any scripted `TIME_TABLE`. The only reader is `EdInitVillagerTable` (`chronicle:ps2/src/editloop3.cpp:708-713`), which reads week 0 rows only, so scripted rows 4 to 11 and other weeks are written but never read. This is an inference from the reads and writes, not something a run confirmed.
- `EdSelectVillager` builds the ten-slot cast for the current period: villagers the script has forced on or out come first (at most six), then entries from the period's table that are not forced off or in (`chronicle:ps2/src/editloop3.cpp:795-867`).
- `EdCheckVillagerIn` and `EdCheckVillager` gate each villager on the Georama state: the villager's `character_no` must be a plot whose `elements[model_no].enabled` is set, and the plot's part must stand on the ground (`chronicle:ps2/src/editloop3.cpp:870-950`).

Placement in towns is random. `EdInitVilagerPosition` splits the present villagers into stationary and moving halves and draws positions at random, using the `rand()` state and `srand` to restore it (`chronicle:ps2/src/editloop3.cpp:1105-1316`). The branch for `MapNo > 10` (sub maps) uses the ground's people markers instead (`chronicle:ps2/src/editloop3.cpp:1108-1131`).

Villager talk state and flags persist per town in `npc[20]` (`chronicle:ps2/include/savedata.hpp:86-92`). Script opcodes read and write them through `GetGrdNPCData(NowEditMap, slot)` (`chronicle:ps2/src/editloop3.cpp:5120-5140`), and `SSET_REQUEST_EVENT_FLAG` writes `request_event_flag` (`chronicle:ps2/src/editloop3.cpp:7375-7385`).

### The Georama ground and Atla placement

The ground is a `CEditGround` with 128 placed `CMapParts` and up to four editable areas (`chronicle:ps2/include/editground.hpp:95-128`). Each part is a plot number plus a rotation and a grid position. `SetMapParts` finds a cell, refuses on a full plot, and increments `placed` (`chronicle:ps2/src/editground.cpp:26-120`). Picking up a part decrements it (`chronicle:ps2/src/editground.cpp:355-416`).

The plot table is `EditPartsData[6]`: for each georama, 24 plots, each with `max`, `stackable`, texture and message numbers, a `kind`, and six element attachments with model names and an optional villager (`chronicle:ps2/src/editpartsdata.cpp:1-160`; struct `chronicle:ps2/include/editpartsdata.hpp:24-47`). `kind == 2` marks a plot that fires an event on completion: when the player stands on a kind-2 plot that is complete but whose completion flag is still clear, the loop calls `FadeOutToEvent(plot + 200)` (`chronicle:ps2/src/editloop.cpp:3876-3880`). The completion flag itself is set by a script opcode through `CEditPartsInfo::SetCompEvent` (`chronicle:ps2/src/editloop3.cpp:5491`, `chronicle:ps2/src/editpartsinfo.cpp:45`). Norune's plot 8 is one such plot.

Atla placement has two layers:

- Acquisition: a dungeon Atla adds to `stock` (for stackable plots, +5 up to `max`) or fills an element chip slot in `elem_data` (`chronicle:ps2/src/savedata.cpp:455-520`).
- Placement on the board: `AtoraBoardKey` places a chip onto an element slot when the tip id matches, the element is not yet enabled, its `required_element` is enabled, and the chip is displayable (`chronicle:ps2/src/memcard.cpp:2493`, fit test at lines 2699-2720). The board opens in place mode from the Georama menu with `InitMenuAtora1(ATORA_OPEN_PLACE, NowEditMap, ...)` (`chronicle:ps2/src/editmenu.cpp:919-928`; `chronicle:ps2/src/memcard.cpp:1451`). Other maps' boards load `BtEditPartsInfo` from the save (`chronicle:ps2/src/memcard.cpp:1550-1557`).

### Leaving a town

- Dungeon hand-off: a door whose destination is the string `dungeon` runs event 130 (`chronicle:ps2/src/editloop.cpp:3858-3859`). The event's return code `ED_EVENT_RETURN_DUNGEON` calls `GotoDungeon` (`chronicle:ps2/src/editloop.cpp:3606`, body at line 3666), which later makes the loop exit with `MapJump(NowEditMap + 0xC8, -1)` (`chronicle:ps2/src/editloop.cpp:2030-2033`). The dungeon index equals the town index, which also explains the Atla link above.
- Interior doors: `GotoInterior` builds `gedit/<town>/in/<name>/<name><m|e|n>` with the time-of-day suffix and places the player at the door (`chronicle:ps2/src/editloop.cpp:3706-3730`). Interiors run in the same editor mode (`EditInInit`, `chronicle:ps2/src/edit_in.cpp:488`). Doors with `minimum_progress > 0` run the event that `EdInitGotoInterior` returns, instead of entering directly (`chronicle:ps2/src/editloop.cpp:3862-3866`; body `chronicle:ps2/src/ebattle.cpp:2834`).
- Ordinary map jumps: `ED_EVENT_RETURN_MAP_JUMP` ends the loop; the map jump's target is in `NextMapNo` (`chronicle:ps2/src/editloop.cpp:3610`, `chronicle:ps2/src/editloop3.cpp:3602-3611`).
- The loop's return value is not a clean dispatch. After the three `if`s, any nonzero result sets `GAME_MODE_MENU`, which overrides the title and edit assignments above it; only 3 goes to the dungeon (`chronicle:ps2/src/main.cpp:858-876`, port mirror in `chronicle:port/src/gameloop.cpp:486-495`). This is as retail does it, and Ixion should not rely on the title or edit branches.

### Persisting the Georama state

`EditSave` writes the current town's ground (`CEditGround::Save(int, CSaveData*)`, `chronicle:ps2/src/editground.cpp:1696-1746`) and plot info (`CEditPartsInfo::Save`, `chronicle:ps2/src/editpartsinfo.cpp:115-142`), then the clock (`chronicle:ps2/src/editloop.cpp:440-456`). It runs on exit from the loop (`chronicle:ps2/src/editloop.cpp:472-476`) and when the save menu enters save mode (`chronicle:ps2/src/memcard.cpp:4478-4481`). `EditLoad` reverses it on arrival and after a save (`chronicle:ps2/src/editloop.cpp:458-466`; `chronicle:ps2/src/memcard.cpp:4689`).

Plot info loads with `load_requests = 0` on arrival (`chronicle:ps2/src/editloop.cpp:460`; the gate is `chronicle:ps2/src/editpartsinfo.cpp:144-172`), so the placed counts and the request flags are not restored from the save; placed counts are rebuilt as parts are re-placed from the saved part records, and requests are recomputed by `RequestCheck` (`chronicle:ps2/src/editground.cpp:2158-2205`). The per-town request checks are dispatched on `map_no` to `NornRequest`, `MatatagiRequest`, `QueensRequest`, `MuskaRequest` and `YellowRequest` (`chronicle:ps2/src/editground.cpp:2181-2196`).

A fresh save is initialised with every part slot `-1`, every chip `-1`, and every plot zeroed (`chronicle:ps2/src/savedata.cpp:628-663`).

## Ixion hooks

- Enter town T directly: `MapJump(T, -1)` (`chronicle:ps2/src/main.cpp:1053`; port `chronicle:port/src/main.cpp:520`), called while the current mode is ending, with `T` in 0 to 4. The main loop applies `NextMapNo` once the current mode's loop returns (`chronicle:ps2/src/main.cpp:982-986`). This sets `MapNo`, enters `GAME_MODE_EDIT`, and runs `EditInit` with the ordinary `EditLoad` path. Pass a real event number as the second argument to run that event instead of event 128, but expect the town BGM load and the loading transition to be skipped (`chronicle:ps2/src/editloop.cpp:833`, `chronicle:ps2/src/main.cpp:611`).
- Test-harness equivalent: `--jump edit:T` (`chronicle:port/src/gameloop.cpp:571-600`, applied at `chronicle:port/src/gameloop.cpp:353-372`; documented in `chronicle:docs/PC.md:548-553`). It accepts any `T >= 0`, so `edit:5` to `edit:10` is parsed but has no data behind it (see Risks).
- Arrival wrapper: hook `EditInit` in `chronicle:port/src/editloop_init.cpp:124`. Insert Ixion's state fix-ups before `EditLoad` (line 339) to restore or substitute the Georama state, and after `EdLoadMainChara` (line 418) to swap the walking character. This is the one place where the town's data, save and player are all set up.
- Player character: `EdLoadMainChara("chara/c01d.chr", "info.cfg", &CharaBuffer)` at `chronicle:port/src/editloop_init.cpp:418` (retail `chronicle:ps2/src/editloop.cpp:1003`) is the only place the walker is chosen. `cur_chara` is set to 0 at `chronicle:ps2/src/editloop.cpp:1135`. Everything the town calls "the player" is `Chara`, which points at `MainChara` (`chronicle:ps2/src/editloop.cpp:4757`, `EdLoadMainChara`).
- Georama persistence: `CEditGround::Save(int town, CSaveData*)` and `Load(int town, CSaveData*)` (`chronicle:ps2/src/editground.cpp:1696`, `1748`) take the town index directly. Ixion can redirect the `town` argument to a different georama slot, or pass a slot used by a DC2 town, without touching the save layout.
- Save-backed slot access: `CSaveData::GetGrdData`, `GetEditPartsInfo`, `GetParts`, `GetElemData`, `GetGrdNPCData` and the flag helpers (`chronicle:ps2/src/savedata.cpp:195-240`, `327-530`). These are the public API for reading and writing a town's progress outside the editor.
- Resume map: the save's `map_no` at 0x1C8 (`chronicle:ps2/include/savedata.hpp:120`). The title's Continue reads it (`chronicle:ps2/src/title/titleloop.cpp:699`). Setting it to T makes a save resume in town T. It is rewritten from `MapNo` at each mode start (`chronicle:ps2/src/main.cpp:725-727`), so the write must happen after the target is set.
- Dungeon to Georama link: `getAtraToSaveData` (`chronicle:ps2/src/btmisc.cpp:238-246`) and `GetNowMapTransAtraMap` (`chronicle:ps2/src/menu_draw.cpp:156-176`). A DC2 dungeon can be made to feed a DC1 Georama by calling `AtraPartsGet` or `AtraChipGet` with the chosen slot, and the Atla board uses the same slot through `GetNowMapTransAtraMap`.
- Town-to-dungeon exit: `MapJump(NowEditMap + 0xC8, -1)` at `chronicle:ps2/src/editloop.cpp:2032`. Changing that expression lets a DC1 town's dungeon door target any dungeon index, which is the simplest way to get "visit any dungeon" from a town.
- World-map registry: `MenuGrobalMapNoTbl` (`chronicle:ps2/src/battlemenu.cpp:8771`) is the list of world-map destinations. It is 16 entries long and indexed by `WORLD_PLACE_*` (`chronicle:ps2/include/battlemenu.hpp:281-297`), so adding places needs a size change.
- Villager roster: `EdCreateVillagerTable` (`chronicle:ps2/src/editloop3.cpp:673`) and the defaults table (`chronicle:ps2/src/editmapscript.cpp:165`, copy at 698-709). Ixion can make the roster deterministic or insert DC2 villagers here.
- Time of day: `EdSetClock` (`chronicle:ps2/src/editloop.cpp:636`) and the save's `now_time` (`chronicle:ps2/include/savedata.hpp:122`) set the clock, and `EdGetTime` (`chronicle:ps2/src/editloop3.cpp:1724`) picks the period for villagers and interior suffixes.
- Map flags: `EdGetMapFlag` and `EdSetMapFlag` (`chronicle:ps2/src/editloop.cpp:577-600`) key flags by the current `MapNo`, which means a town's flags are per town number. Ixion must not reuse those numbers for DC2 maps in the same save without a namespace.

## Risks and blockers

- Map-number collision: `MapNo` 0 to 4 are DC1 towns, and the save indexes `map_flags[80]`, `visit_map[80]`, `georama[6]` and `special_npc` by the same numbers. A combined save needs a translation layer or separate tables. This note did not check DC2's numbering, which is another researcher's topic.
- Globals and re-entry: `EditInit` rebuilds the editor's static arenas (`DataBuffer__2` at 1,216,000 bytes, `EtcDataBuffer`, `CharaBuffer`) and singletons (`pEditGround`, `EditPartsInfo`, `EdVillager`) (`chronicle:ps2/src/editloop.cpp:703-790`). Two towns cannot be live at once (inference from the singleton globals), and DC2 state left in these globals across a jump is not cleared by the editor.
- The developer path (`old_main_mode == 7`, `main_select_padrup == 0`) skips `EditLoad` and loads `gdata0.edt` with every plot obtained. Entering through the developer menu will not show a player's real progress, and it does not read the save's Georama.
- Random villagers: the roster is reshuffled on every entry using `rand()`. In the port, `rand` is a plain LCG seeded with 1 at boot (`chronicle:port/src/runtime.cpp:33-41`), so a run is repeatable only from the same boot and call sequence. Comparison tests need a fixed `srand` before entry.
- Only towns persist Georama ground. Sub maps get empty plot tables (`CEditPartsInfo::Initialize` guards `georama_no >= 6`, `chronicle:ps2/src/editpartsinfo.cpp:204`) and no ground save, so a route through a field map keeps only its clock, flags and NPC slots.
- Event 128 and the start-event path: the arrival event's content was not decoded. Passing a non-negative `StartEventNo` also skips the BGM load (`chronicle:ps2/src/editloop.cpp:833`) and the loading transition (`chronicle:ps2/src/main.cpp:611`).
- Missing data for `MapNo` 5 to 10, and for most of the sub-map range. `EditInit` will try to open `gedit/e06` and similar. The behaviour on a missing file was not traced.
- The walker is always `chara/c01d.chr` in towns, which is the first entry of the dungeon party-model table (`chronicle:ps2/src/btitem.cpp:57`, Toan at `CHARA_TOAN = 0`, `chronicle:ps2/include/itemdata.hpp:486`). A DC2 character walking a DC1 town needs their own model, animation pack and texture block. The player's texture block is 8 and the event NPCs start at block 54 (`chronicle:ps2/src/editloop.cpp:878-879`; the `editloop3.cpp:997` cite is unverified), so any new model needs a free block.
- Some Chronicle code is PAL-first (`#ifdef PAL` in `EditInit` at `chronicle:ps2/src/editloop.cpp:751`, and the debug chord in the main loop). Any Ixion change should build for the same region as the data.
- Dark Heaven Castle is not a town in this code. The task premise is wrong on this point and should be corrected in any Ixion spec.
- The town name "Muska Lacka" in the enum is "Muska Racka" in several comments; code search for either spelling.

## Open questions

- What does the sixth Georama (`georama[5]`, with six plots and no model names in `EditPartsData[5]`, `chronicle:ps2/src/editpartsdata.cpp:134-160`) represent? It is reachable by dungeon 5 through `getAtraToSaveData`, so it is probably the Gallery of Time (Dark Heaven Castle) Atla store. This is inference and was not confirmed.
- Demon Shaft is `MapNo` 60 (sub map `s50`). Georama index 6 does not exist (`GetGrdData` bounds 0 to 5, `chronicle:ps2/src/savedata.cpp:175-181`), so where a dungeon-6 Atla would go is not traced.
- What does event 128 do, and which event IDs are the Georama completion events 200 to 215 (`plot + 200`)? The `event.stb` payloads were not decoded.
- Which values of `SV_GRD_NPC.flags` other than bit 1 (`chronicle:ps2/include/savedata.hpp:86-92`) are used?
- Besides the `== 7` check that selects the developer path (`chronicle:ps2/src/editloop.cpp:917`), `old_main_mode` also picks the BGM for mode 5 (the opening) at `chronicle:ps2/src/editloop.cpp:837`. Whether any other arrival step reads it was not exhaustively traced.
- Are there DC1 town interiors that are keyed by `MapNo` rather than by the town's folder? The interior path uses the town folder (`chronicle:ps2/src/editloop.cpp:3711-3718`), so probably not, but the interior test map path (`MapNo` 99) was not walked.
