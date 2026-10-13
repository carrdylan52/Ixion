# ChronicleTwo: time travel, the world map and the Ixion train

## What this covers

How ChronicleTwo (Dark Chronicle, DC2) moves the player between towns, dungeons, interiors and
the two eras it uses: the map table that names every destination, the world map menu that
lists and loads them, the event commands that jump between maps, the future-era maps (types 5
and 6) and the Georama layouts they share save slots with, and the Ixion train maps. It also
records where a second world (Dark Cloud's Chronicle world) could be attached.

Read-only research. Nothing was built or run. Code is at the ChronicleTwo master branch
(`ixion` branch, base f44a756). Retail code is `ps2/src`; the PC port replaces only a few
scene functions with `PORT_OVERRIDE` definitions in `port/src`.

Citation forms used below:
- `chronicletwo:ps2/src/x.cpp:N` for game code.
- `chronicletwo-data:map/map0.cfg` for the extracted PAL data (not in git; the
  map and menu scripts are plain text, CRLF, Shift-JIS titles in map0.cfg, ASCII English titles
  in map1.cfg).
- `community-wiki:<page>` for the pulled fandom pages used for lore only.

## Key facts

- **Map table.** Every destination is a `MAP_NAME` record. The code reads
  `map/map<LanguageCode>.cfg` only (`chronicletwo:ps2/src/mapselect.cpp:277-290`, called from
  `chronicletwo:ps2/src/mainloop.cpp:444` and `:579`). Seven language files exist
  (`map0.cfg` to `map6.cfg`, 189 records each). `map/map.cfg` (86 records) is never opened by the
  code; grep finds no reference to it.
- **Record fields.** name, title, add_path, type, sel_type, snd_data_id, area_no
  (`chronicletwo:ps2/include/mapselect.hpp:133-143`; parser `mlMAP_NAME` at
  `chronicletwo:ps2/src/mapselect.cpp:227-264`). Map numbers are table indices, so the
  order of records is load-bearing. Several hard-coded numbers depend on it (see Ixion hooks).
- **Map types.** The named values are `MAP_TYPE_GEORAMA=1`, `GEORAMA_INTERIOR=2`,
  `INTERIOR=4`, `FUTURE=5`, `FUTURE_INTERIOR=6` (`chronicletwo:ps2/include/mapselect.hpp:43-49`).
  The data also uses types 3, 7 and 8, which the code never names. By inspection of the table
  (inference): 3 is town, station or sub-map; 7 and 8 are dungeon floors and dungeon basements,
  since every `d*` record carries one of them.
- **Future-era maps in data.** `f01` Jurak Mall, `f02` Starlight Temple, `f03` Luna Lab,
  `f04` Gundorada Workshop (all type 5, sel_type 4 "Future"; English titles from
  `chronicletwo-data:map/map1.cfg`). Their interiors are `f02i06`, `f02i07`, `f02i08`,
  `f03i04`, `f03i0301`-`f03i0304`, `f04i03`-`f04i05` (type 6, except `f03i04` which is type 5).
- **Ixion maps in data.** `s36` "Ixion (Outer)" (type 3, sel 3), `s37` "Ixion (Engine Room)"
  (type 3), `s38` "Ixion (Guest Room)" (type 3, sel 7), `s39` "Operations Room" (type 5, sel 4).
  Paznos maps `s29`, `s30`, `s48` are type 5 (`chronicletwo-data:map/map1.cfg`).
- **No "Ixion" string in code.** A case-insensitive grep of `ps2/` and `port/src/` is empty
  for the word. The train is referred to only through map names (`s37`, `s38` in
  `chronicletwo:ps2/src/editctrl.cpp:752-770`, `chronicletwo:ps2/src/menuchr.cpp:1864`), the
  add path `trn2/s36`, and the data titles. The word "train" in code is the normal train
  (`trn/train`), train NPC seats and a train-defence sub game (see below).
- **Two train add-ons.** Station maps attach a shared train file as `add_path`: `trn/train`
  (the normal train car) on `s01`, `s02`, `s04`, `s09`, `s10`, `i02h01`, and `trn2/s36` (the
  Ixion exterior) on `s11`, `s12`, `s31`, `s34`, `s53`, `s58`, `s71`
  (`chronicletwo-data:map/map0.cfg`).
- **Chapter swap.** While the story progress chapter is 6 or 7, every `trn/train` add-on is
  replaced by `trn2/s36` (`chronicletwo:ps2/src/mapjump.cpp:301-308`). Chapter 8 and later keep
  `trn/train`. The chapter comes from the progress table in `npc_place4.cfg`
  (`chronicletwo:ps2/include/vlgr_info.hpp:44-51`).
- **Sky swap.** Chapters 8 and 9 use the "b" sky variant (`chronicletwo:ps2/src/mapjump.cpp:285-292`).
- **World map script.** `menu/<lang>/wldmap.cfg` holds `POS` records (a place: map, loop, area,
  dungeon, floor, unlock flag, icon type) and `AREA` records (a region with a screen mark and a
  name) (`chronicletwo:ps2/src/menumap.cpp:274-394`). `menu/<n>/` exists for `n` 0 to 5 in the
  extract.
- **Unlock flags are save-bit numbers.** Each POS unlocks through `CheckBitFlagMenu(flag_no)`
  (`chronicletwo:ps2/src/menumap.cpp:308-314`). The future places (`f01` to `f04`, POS 8, 14, 19,
  23) use flag 616, which equals `SAVE_FLAG_WORLD_MAP_4` (0x268) in the enum
  (`chronicletwo:ps2/include/savedata.hpp:129`). POS 24 (a type 3 place in area 6) also uses 616, so
  that flag is not future-only. The two Griffon's Castle places (area 8) use
  flag 600, which is `SAVE_FLAG_WORLD_MAP_2`.
- **Future places are disabled after Chapter 8 is reached.** A POS with type 4 is set to
  disabled when `SAVE_FLAG_CHAPTER_8` (0x2E0) is set (`chronicletwo:ps2/src/menumap.cpp:318-320`).
  Type 4 is the only type that the data gives to `f01` to `f04`. The code calls type 4
  `WMAP_POS_TYPE_GEORAMA` (`chronicletwo:ps2/include/menumap.hpp:36-38`), so the label in code
  and the era in the data disagree; the data is the one that identifies it as future.
- **Area gates.** Area 8 closes under `SAVE_FLAG_WORLD_MAP_4`; areas 6 and 7 close under
  `SAVE_FLAG_CHAPTER_8_STARTED` (`chronicletwo:ps2/src/menumap.cpp:375-383`). These area numbers
  are literals in the code.
- **World map layouts.** The background is `wmap<N>.pac`, with N chosen by flags in the order
  2, then 4, then 3, the last one set winning (`chronicletwo:ps2/src/menumap.cpp:1313-1323`).
  Layout 4 also swaps the map textures (`chronicletwo:ps2/src/menumap.cpp:459-462`). A layout is a
  progress stage, not an era; the code has no past or present field.
- **Travel result.** Choosing a place sets `MenuArg.end_code = MENU_END_WORLD_MOVE` and
  `result[0..2] = loop, map, floor` (`chronicletwo:ps2/src/menumap.cpp:785-846`). The edit loop
  then either calls `NextLoop(loop, {map, floor, event 1010})` when the loop is not `LOOP_EDIT`,
  or calls `EditMapJump(result[1])` and runs event 100 (`chronicletwo:ps2/src/editloop.cpp:1362-1381`).
- **Dungeon places.** For loop 2 (`LOOP_DUNGEON`), the `dng_no` field replaces the map number,
  and `floor = -1` opens the floor's tree map first
  (`chronicletwo:ps2/src/menumap.cpp:793-805`). The tree map returns to a town through
  `MakeDngTreeMapJumpNo` (`chronicletwo:ps2/src/dngmenu.cpp:2723-2760`).
- **Georama-type places set the present town first.** Before a type 4 place is loaded, the
  scene's `now_map_no` is set to the Georama town of the place's area, looked up in a fixed
  table: area 2 to `g01`, 3 to `g02`, 4 to `g03`, 5 to `g04`, 7 to `g05`
  (`chronicletwo:ps2/src/menumap.cpp:811-831`).
- **Future maps share save slots with the Georama towns.** `EditMapJump` gives `f01` to `f04`
  area indices 0 to 3 and uses `GetEditData(area)` (`chronicletwo:ps2/src/editloop.cpp:2835-2857`,
  `:2896-2912`). Georama towns save their layout to `GetEditData(MapNo)`, where `MapNo` is the
  table index (`g01` is 0 through `g05` is 4) (`chronicletwo:ps2/src/editloop.cpp:3026-3050`).
  So `f0k` and `g0k` read and write the same `CEditData` record. The town-area pairing from the
  data is `f01`/`g01` (area 2), `f02`/`g02` (area 3), `f03`/`g03` (area 4), `f04`/`g04` (area 5).
- **Only five edit slots.** `SAVE_EDIT_DATA_MAX` is 5 (`chronicletwo:ps2/include/savedata.hpp:60`,
  `:231`). Slot 4 (`g05`, Moon Flower) has no future partner.
- **Analysis flags drive future parts.** `CEditMap::PartsOnOff` shows or hides parts of a future
  map from the area's analysis flags (`chronicletwo:ps2/src/editdata.cpp:659-697`). A flag is the
  AND of up to eight `analyze.condition` values (`chronicletwo:ps2/src/editdata.cpp:808-838`).
  Conditions are recomputed from the Georama layout each time a Georama town is saved or
  loaded (`chronicletwo:ps2/src/editloop.cpp:3042`, `:3069`; `AnalyzeEditMap` at
  `chronicletwo:ps2/src/editanalyze.cpp:80`).
- **Map load path.** `MapJump` clears characters 8 to 63, records the previous main and sub
  numbers in the save (`map_no`, `prev_map_no`, `sub_map_no`, `prev_sub_map_no`), deletes the old
  maps, builds the new main map and runs its script (`chronicletwo:ps2/src/mapjump.cpp:191-249`;
  save fields at `chronicletwo:ps2/include/savedata.hpp:225-229`).
- **Edit-loop wrapper.** `EditMapJump` adds villagers, town events, the future-area parts, and
  for map numbers 11 to 14 it loads the map as a sub-map of map 10
  (`chronicletwo:ps2/src/editloop.cpp:2736-2740`, `:2880-2888`).
- **Interiors are sub-maps.** `GotoInterior`, `InteriorMapJump`, `ExitInterior` keep the
  interior in map slot 1 and the town in slot 0. The return position is the function point
  whose door target is the previous interior, or `exit`
  (`chronicletwo:ps2/src/mapjump.cpp:483-658`).
- **Event commands.** Map travel from scripts goes through `EdEventInfo.request`:
  `_MAP_JUMP` (EXT 20, `chronicletwo:ps2/src/event_func.cpp:4093`), `_GOTO_INTERIOR` (EXT 6,
  `:3612`), `_GOTO_OUTSIDE` (EXT 7, `:3637`), `_MOVE_INTERIOR` (EXT 91, `:6118`), `_GOTO_DNG`
  (EXT 62, `:5397`), `_GOTO_EDIT` (EXT 63, `:5425`), `_FUNCTION_MAP_JUMP` (EXT 544, `:7410`).
  `_GET_MAP_TYPE` (EXT 1092, `:18736`) lets a script test a map's type. The request is consumed in
  `chronicletwo:ps2/src/editloop.cpp:1553-1586`. The `jump_point` value is stored by these
  commands and I found no reader for it in `ps2/src` (inference: unused).
- **Events can open the world map.** `_GOTO_MENU` (EXT 509, `chronicletwo:ps2/src/event_func.cpp:6378`)
  sets `MenuArg.open_type` and the parameters, then sub-mode opens the menu. Open type 13
  (`MENU_OPEN_WORLD_MOVE`) or 19 opens the world map with `param[0]` as a POS index that marks
  the player's area (`chronicletwo:ps2/include/menumain.hpp:100`, `:106`;
  `chronicletwo:ps2/src/menumap.cpp:502-519`). Index 8, 9, 10 are remapped to 14, 15, 21.
- **Top menu gate.** The world map is closed until `SAVE_FLAG_EARLY_GAME_DONE` (0x36) is set
  (`chronicletwo:ps2/src/menumain.cpp:1960-1964`, `:2023-2028`). In future maps the clock's
  AM/PM and hour parts are hidden (`chronicletwo:ps2/src/menumain.cpp:1769-1785`), the world move
  entry is refused with a message (`:2256-2272`), and the top-menu topic is not drawn
  (`chronicletwo:ps2/src/menumain.cpp:1871`).
- **Debug future menu.** `FutureMapSelect` hard-codes `{0x19, 0x1A, 0x52, 0x66}` = `f01` to `f04`
  and starts `LOOP_EDIT` with event 99 or 100 (`chronicletwo:ps2/src/mainloop3.cpp:115-222`).
  It is opened from debug event-select row 7 (`chronicletwo:ps2/src/mainloop.cpp:1157-1169`,
  `chronicletwo:ps2/include/mainloop.hpp:130`).
- **Villagers follow the map number.** `GetLoadVillagerList` asks the villager manager for the
  residents of a map number at the current progress and time
  (`chronicletwo:ps2/src/scenevillager.cpp:507-530`). Data comes from `place.cfg` and
  `npc_place4.cfg` (`chronicletwo:ps2/src/vlgr_info.cpp:834-858`).
- **Train-adjacent code.** `_GET_TRAIN_NPC_POS` (EXT 76, `chronicletwo:ps2/src/event_func.cpp:5758`)
  pushes train seat positions for scripted NPCs. The event model directory `event/train/` is used
  for train NPC models (`chronicletwo:ps2/src/npccfg.cpp:180-181`,
  `chronicletwo:ps2/src/event_func.cpp:5491`). The buggy sub game, sub game 3, defends a train
  (`chronicletwo:ps2/include/pbuggy.hpp:8-11`).
- **Port overrides on this path.** The PC port overrides the stepped loader `LoadMapFromMemory`
  (`chronicletwo:port/src/sceneload.cpp:33`), `SetEventScript` (`chronicletwo:port/src/event.cpp:93`)
  and `ClearStack` (`chronicletwo:port/src/scene.cpp:8`). No port file overrides the map table,
  the world map, the jump logic or the interior logic. The port does override `EditControl`
  (`chronicletwo:port/src/editctrl.cpp:60`), which calls `PortEditCameraControl` instead of the retail
  `EditCameraControl` that holds the s07/s37/s38 camera rule (`chronicletwo:ps2/src/editctrl.cpp:665`,
  `:752-770`). The port's stub (`chronicletwo:port/include/stubs/editctrl.hpp:32`) keeps only a
  forced-follow for those three maps.
- **Lore.** In the story, Max and Monica travel 100 years between eras with Atlamillia; Monica
  uses a Starglass to return; the Ixion is the time train built at Luna Labs; Griffon destroyed the
  "origin points" of future towns; Starlight Temple is a future town
  (`community-wiki:Dark_Chronicle`, `community-wiki:Monica_Raybrandt`,
  `community-wiki:Gundorada_Workshop`). The brief's "Gate of Time" and "Origin Points" do not
  appear as identifiers in ChronicleTwo or Chronicle code or data.

## How it works

### 1. Destination table

At boot, `LoadMapName` builds `map_name[]` from the language file. `mlMAP_NAME_NUM` reserves
`count + 1` records and string space inside a fixed arena (`MapNameBuff`, 0x800 quadwords,
about 32 KiB; `chronicletwo:ps2/src/mapselect.cpp:141`, `:205-220`). `mlMAP_NAME` copies name, title
and add path and reads type, sel_type, sound id and area (`chronicletwo:ps2/src/mapselect.cpp:227-264`).
`GetMapName`, `GetMapType`, `GetMapAreaNo`, `GetMapSelType` and `GetAddMapPath` index the
same table (`chronicletwo:ps2/src/mapselect.cpp:327-428`). `SearchMapNo` converts a name back to
a number by linear search (`chronicletwo:ps2/src/mapselect.cpp:385-408`).

Map file paths follow the name: `map/<a>/<abc>/<def>/<name>` with the segments taken from the
name prefix (`chronicletwo:ps2/src/mapselect.cpp:306-325`). Adding a record needs no new path rule
as long as the name follows the scheme. `GetLoadMapInfo` gives the main map its files and the
add-path its files under `map/cmn/` (`chronicletwo:ps2/src/mapjump.cpp:251-322`).

### 2. The world map menu

`WorldMoveInit` allocates `CWorldMapMenu`, picks the layout by flags, and reads `wmap<N>.pac`
(`chronicletwo:ps2/src/menumap.cpp:1290-1337`). `WorldMoveKey` steps it and, for a dungeon tree
map opened from it, the tree map (`chronicletwo:ps2/src/menumap.cpp:1339-1373`).

The menu's first frame reads `wldmap.cfg` through the script interpreter, with tags `POS_NUM`,
`POS`, `AREA_NUM`, `AREA` (`chronicletwo:ps2/src/menumap.cpp:274-404`). `_WMAP_POS` gives each POS
its unlock state and then `_WMAP_AREA` builds the area's list of up to eight POS pointers, with
`enable` set when any place in it is unlocked (`chronicletwo:ps2/src/menumap.cpp:341-394`).

Cursor movement picks the nearest enabled area in the pushed direction, using a cosine threshold
that falls from 0.72 (`chronicletwo:ps2/src/menumap.cpp:610-707`). Decide opens the place list
of the area, which shows at most six enabled places (`WMAP_AREA_POS_LIST`,
`chronicletwo:ps2/include/menumap.hpp:24-29`). Choosing a place asks for confirmation
(`chronicletwo:ps2/src/menumap.cpp:745-854`). Choosing the place the player is already at is
refused (`chronicletwo:ps2/src/menumap.cpp:769-770`).

### 3. Load

On confirm, `result[]` is set and the menu fades out (`chronicletwo:ps2/src/menumap.cpp:549-554`).
The edit loop reads it (`chronicletwo:ps2/src/editloop.cpp:1362-1381`). Two branches:

- Loop is `LOOP_EDIT` (1): `EditMapJump(map)` loads a town or future map in place, then runs
  event 100.
- Any other loop (the dungeon loop 2 is the one in the data): the edit loop ends, and
  `NextLoop(loop, {map, floor, 1010})` starts that loop.

`EditMapJump` (`chronicletwo:ps2/src/editloop.cpp:2713-2940`) calls `MapJump` (which resets the
main map and the characters), loads villagers and town events, loads the Georama layout for
Georama types, applies the future analysis for future types, creates treasure boxes, and loads
the sub-map for numbers 11 to 14.

### 4. Interiors

`EditGotoInterior` chooses between `GotoInterior` (first entry) and `InteriorMapJump` (already inside),
and `EditExitInterior` calls `ExitInterior` (`chronicletwo:ps2/src/editloop.cpp:2942-3020`).
`GotoInterior` saves the player's position, camera and music in `SaveBeforeInterior`, loads the
interior into slot 1, and puts the player at the door whose target is `PrevInterior` or `exit`
(`chronicletwo:ps2/src/mapjump.cpp:459-558`). `ExitInterior` restores all of that
(`chronicletwo:ps2/src/mapjump.cpp:571-634`).

### 5. Scripts

A script can request any of these, which the edit loop turns into a jump on the next frame:
map jump by name (`_MAP_JUMP`), interior by name (`_GOTO_INTERIOR`, `_MOVE_INTERIOR`), outside
(`_GOTO_OUTSIDE`, `_FUNCTION_MAP_JUMP` with `exit`), dungeon floor (`_GOTO_DNG`), edit mode
(`_GOTO_EDIT`) or a menu (`_GOTO_MENU`, which can open the world map). Event 100 is the default
start event; `_MAP_JUMP` takes an optional event number (`chronicletwo:ps2/src/event_func.cpp:4093-4117`).

### 6. Eras in practice

There is no era field. In practice the code separates the two eras by:
- map type (5 and 6 are future; everything else is present, with dungeon and town types ignored
  by the era logic);
- the POS unlock bit for each future place (616) and the Chapter 8 cut-off (type 4 disabled);
- the save slot shared with a Georama town, through `EditMapJump`'s area index;
- the top-menu gates on future maps (time board hidden, world move refused).

Anything else that is "future" (the Ixion engine room, the operations room) is either a future
type (`s39`) or a present-type sub-map with a camera or party rule keyed by name (`s37`, `s38`).

## Ixion hooks

- **Destination list, data.** `menu/<lang>/wldmap.cfg`: append POS records (raise `POS_NUM`),
  give each one a map number, loop, area, dungeon, floor, unlock bit and icon type; add AREA
  records (raise `AREA_NUM`). The count is read at runtime, so the table grows without a code
  change (`chronicletwo:ps2/src/menumap.cpp:282-296`, `:325-339`). Do this for all six
  language folders, or the new place is missing in that language.
- **Destination list, code limits.** A place needs an area index below `AREA_NUM`. Area 6, 7
  and 8 have literal gates (`chronicletwo:ps2/src/menumap.cpp:375-383`) that a new area with the
  same index would inherit. The Chapter 8 cut-off for type 4 (`:318-320`) would also apply to any
  new type-4 place, so do not reuse type 4 for a place that must stay reachable after Chapter 8.
- **Map table.** Add `MAP_NAME` rows to all seven `map<N>.cfg` files and raise `MAP_NAME_NUM`.
  Append after record 188: many numbers are hard-coded (`0x19`, `0x1A`, `0x52`, `0x66` in
  `chronicletwo:ps2/src/mainloop3.cpp:122`; `0x22` and `10` in
  `chronicletwo:ps2/src/menumap.cpp:839-842`; `0xA`, `0x22`, `0x79` in
  `chronicletwo:ps2/src/editloop.cpp:2790`; `10` in `chronicletwo:ps2/src/editloop.cpp:883`).
  Check the 32 KiB name arena after adding; the current table is about 5 KiB of records before
  strings.
- **Era or dimension marker.** A new map type (for example 9) would need the era gates added:
  the time-board and top-menu checks (`chronicletwo:ps2/src/menumain.cpp:1769`, `:1871`, `:2257`)
  and `EditMapJump`'s future branch (`chronicletwo:ps2/src/editloop.cpp:2835`). `MapType` in
  `chronicletwo:ps2/include/mapselect.hpp:43-49` would need the new value. Without the gates, a
  new map type behaves as a plain present town.
- **Trigger from events.** To open the world map from a script, use `_GOTO_MENU` with open type
  13 and a POS index (`chronicletwo:ps2/src/event_func.cpp:6378`). To travel to a single map with
  no menu, use `_MAP_JUMP` or `_GOTO_EDIT`. For a time-train cutscene that ends in a future
  town, the script would call `_MAP_JUMP` with a future map name; no code path checks that the
  player has earned the trip, so the gate would be the script's own.
- **Ixion as a travel vehicle.** The Ixion exterior is an add-path, not a destination. To make the
  train visible at a station, add `trn2/s36` as the add-path of that station's record. To make
  it appear for every chapter, remove or widen the chapter 6-7 condition at
  `chronicletwo:ps2/src/mapjump.cpp:304-306`. The interior rooms (`s37`, `s38`, `s39`) are
  ordinary sub-map records that `_GOTO_INTERIOR` can enter; `s37` and `s38` already have camera
  rules in retail (`chronicletwo:ps2/src/editctrl.cpp:752-770`); the PC port reimplements only a
  forced-follow for them (see Key facts).
- **Party joins on a train.** When a party member is joined through the character-change menu in `s07`
  (a train car) or `s38` (Ixion guest room), that member's character is made active in the scene
  (`chronicletwo:ps2/src/menuchr.cpp:1864`). A new train interior would need the same rule added there
  for the member to appear.
- **A new future area.** A new future place needs a `CEditData` slot. The five slots are all
  used by Georama towns (`chronicletwo:ps2/include/savedata.hpp:60`). The cheapest option is
  to reuse `g05`'s slot 4 for a future partner, which means changing the area-index switch in
  `EditMapJump` (`chronicletwo:ps2/src/editloop.cpp:2836-2849`), not the save format.
- **Debug menu.** `FutureMapSelect` (`chronicletwo:ps2/src/mainloop3.cpp:122`) lists only four
  maps. A new future map would need a row there to be testable from the debug menu.

## Risks and blockers

- **Cross-game data.** A Dark Cloud (Chronicle) world would need its towns, dungeons and events
  converted to ChronicleTwo's formats: `.map`, `.mpk`, `.ipk`, `.efp`, `.sky`, `.cfg` and the
  event script `.stb`. The loader is `CScene::LoadMapFromMemory`
  (`chronicletwo:ps2/src/sceneload.cpp:284-300`, port override at `chronicletwo:port/src/sceneload.cpp:33`).
  Whether Chronicle's formats map onto these was not checked.
- **Loop enum is closed.** `LOOP_MODE_NUM` is 10; any other loop number ends the game
  (`chronicletwo:ps2/include/mainloop.hpp:42`). A second world as its own loop needs a new loop
  number and a dispatcher case. A second world as edit-loop maps needs no new loop.
- **Chapter 8 kills future travel.** Once `SAVE_FLAG_CHAPTER_8` is set, every type 4 place is
  disabled (`chronicletwo:ps2/src/menumap.cpp:318-320`). A new Ixion destination must not be type 4
  if it is meant to be reachable later.
- **Literal gates scattered through the code.** Area 6/7/8 (`menumap.cpp:375-383`), map 0x22
  redirect (`menumap.cpp:839-842`), `s12` to `s34` (`menumap.cpp:807-809`), dungeon 0 floor 8
  (`dngmenu.cpp:2733`), and `s07`/`s38`/`s37` (`editctrl.cpp:752-770`, `menuchr.cpp:1864`). Each
  one is invisible in the data and breaks silently when a number moves.
- **Language table gap.** Only `map0.cfg` to `map6.cfg` exist, but `LanguageCode` has eight values
  (`chronicletwo:ps2/include/mainloop.hpp:54-61`). If Korean (7) is reachable, the map table is
  empty. Not verified whether the title screen can select it.
- **Save slot coupling.** `CEditData` slot N is shared by `gN+1` and `fN+1`. Changing the area
  mapping for future maps changes which Georama layout drives them, and the save data does not
  record the mapping.
- **Event scripts unreadable here.** The `.stb` event scripts are binary. I could identify
  which maps they name (for example `s12` and `s02` reference `s36`-`s39`) but not the call sites
  that open the Ixion rooms or the world map. Some of those strings are motion names, not map
  names, so a plain grep over-counts.
- **PC port.** The port does not override the map table, world map or jump logic, so changes
  there are compiled as-is. The port's `LoadMapFromMemory` override (`chronicletwo:port/src/sceneload.cpp:33`)
  must be kept in sync with any new loading step.

## Open questions

- Which event scripts call `_GOTO_MENU` with open type 13 or 19, and which call `_MAP_JUMP` or
  `_GOTO_INTERIOR` to reach `s36` to `s39`? Needs a decode of the `.stb` opcode stream (not done).
- Is the Ixion trip in the story a world-map destination (a POS entry, not present in the data
  for `s36` to `s39`) or purely a scripted event? The data suggests scripted: no POS entry points to
  an Ixion map.
- What are map types 3, 7 and 8? The code does not name them; the names above are inference from
  the data.
- Is the `map/map.cfg` file (86 records) a leftover from an earlier build? No code reads it.
- Are the "origin points" in the lore represented by the analysis flags of the `CEditData` slots
  (inference from `PartsOnOff`), or by something else?
- Does the Starglass item, which the lore has Monica use to travel back, appear in any code path
  here? Not searched.
- Does `jump_point` have any reader? None found in `ps2/src`; confirm with a wider search.
