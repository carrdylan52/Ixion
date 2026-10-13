# Visiting a map from the other game: town and dungeon format feasibility

## What this covers

Two questions, kept apart because they have different answers.

1. **Native travel (what v1 part (a) describes).** The destination game loads one of its own towns or floors on its own fiber. This needs no format work. Section "How it works" lists the jump entry points each game already has.
2. **Cross-world rendering.** A Dark Cloud town or dungeon floor drawn by the Dark Chronicle engine, or the reverse. This is where the format gap matters. Options are ranked (a) load directly, (b) convert offline, (c) assemble parts through the other game's random floor generator, (d) background only.

It covers container and scene formats, the load code in each port, collision and movement, lights, fog and sky, and textures. It also corrects three statements in `engine-lineage-maps.md` and resolves one open question in it (see Key facts).

Not covered: battle, Georama economy and villager rules, except where they constrain loading.

Citation prefixes: `chronicle:` (DC1 decomp), `chronicletwo:` (DC2 decomp), `kazarov:` (runtime library), `refs/DCExtractor/` (community format notes). `dc1-data:` and `dc2-data:` are the extracted game trees, relative to their roots. `dc2-port-data:` is the DC2 port's converted asset set (`port_data/`), which sits beside the DC2 data root. Ixion-side files are `ixion:` (design doc and Hop v0 spec).

## Key facts

- **v1 travel does not need a foreign map.** The Hop v0 spec starts each game on its own jump, for example `--jump edit:0` for DC1 and `--jump town:10` for DC2 (`ixion:docs/HOP-V0.md` lines 118-119). The ABI reserves `IxionTravel.destination` as "the destination module's own startup jump" (`ixion:include/ixion_api.h:62`). The design puts "floors from the other world" in Phase 2 but treats content crossover (models, scripts, floors) as tier T3, and model crossover as "the expensive part; it waits for evidence of demand" (`ixion:docs/DESIGN.md`, section 5 tier list and section 6 phases 2 to 4). Inference: the v1 brief's wording ("executed by the destination module") means native travel, and cross-world rendering is a later decision.
- **Both games have a native arrival path for a town or floor.** DC1: a `NextMapNo` in 200 to 299 selects `GAME_MODE_DUNGEON` and sets `main_select_menu_no`, and `MapJump(map, event)` only stores `NextMapNo` and `StartEventNo` (`chronicle:ps2/src/main.cpp:982-996`, `:1053-1056`). DC2: `EditMapJump(int map_no)` (`chronicletwo:ps2/src/editloop.cpp:2713`) is reached by name from `EditInit` through `SearchMapNo(GetMapName(...))` (`chronicletwo:ps2/src/editloop.cpp:877`).
- **Both games use a per-map file family with different shapes.** DC1 town `gedit/eNN/` holds `scene.scn`, `mds.pak`, `img.pak`, `mapinfo.cfg`, `event.stb`, `gdata0.edt`, plus `in/` (interiors) and `mds/` (dc1-data:gedit/e01/). DC2 map `map/<c>/<cc>/<name>/` holds `<name>.map`, `.mpk`, `.ipk`, `.efp`, `.cfg`, and an optional `.sky` (`chronicletwo:ps2/src/mapjump.cpp:251-300`; dc2-data:map/g/g01/).
- **Correction 1 to the lineage note: the DC1 town parts are in the extract.** `mapinfo.cfg` names parts such as `BLD_PARTS 0, "e01h01.pts"` (dc1-data:gedit/e01/mapinfo.cfg:292). These are records inside `scene.scn`, not loose files. `LoadObjectParts` finds them with `SearchPTS(scn_data, name)` (`chronicle:ps2/src/editloop.cpp:5168`, and `:4981` for the fixed parts), and the buffer comes from `scene.scn` (`chronicle:ps2/src/editloop.cpp:4930-4932`). `SearchPTS` reads a 16-byte `PTS_HEADER` and 0x30-byte `PTS_ENTRY` records (`chronicle:ps2/src/dispctrl.cpp:19-38`). Checked by decoding bytes: `scene.scn` starts with the magic `SCN\0`, count 34, and entry 0 is `e01h01` at offset 0xC10. The file is 3,544,896 bytes and entry 0's offset 0xC10 was checked; the other 33 offsets are unverified.
- **Correction 2 to the lineage note: DC1 floor models are in the extract.** Floor models are in `dun/mpd_pack/<name>.mpd`, a flat pack for `d01main_a` (the 111-entry count is unverified; the first entries `texanime.cfg` and `d01m01.img` were checked) (`.img` textures, `.mds` models, `.chr` and `.mot` motion, `texanime.cfg`). The floor's part list is the text config `dun/<name>.cfg` (dc1-data:dun/d01main_a.cfg). `BtMapJumpLoad` opens both (`chronicle:ps2/src/shot_freefuncs.cpp:1310-1316`) and parses the config with `TEIGIAnalyz` (`chronicle:ps2/src/itemdata.cpp:478`).
- **Correction 3 to the lineage note: the DC1 town config is readable as shipped.** `EditInit` asks for the compiled `mapinfo.cfb` (`chronicle:ps2/src/editloop.cpp:776`). `LoadEditMapData` falls back to the text file beside it when the compiled file is missing (`chronicle:ps2/src/editmapscript.cpp:524`, comment "No compiled script: read the text one beside it" near `:546`). The `.cfg` in the extract is what the game reads.
- **Resolved open question: DC2 textures are PNGs in the PC port, not raw `.ipk` payloads.** The `.ipk` payloads in the extract are zero-filled. `g01.ipk` (2,001,936 bytes) has 118 non-zero bytes in total; the one-entry, size-0 `IMG` claim is unverified. The DC2 port does not decode them. `ResolveFile` returns an opaque `KZTX:` handle for any name present in the converted catalog (`chronicletwo:port/src/dataread.cpp:205-216`). The catalog is loaded from `port_data/catalog.json` (`chronicletwo:port/src/dataread.cpp:341`) and has 5,245 sources, 550 of them under `map/`, each mapped to PNG levels (`kazarov:src/cpp/platform/texture_catalog.cpp:74-83`; dc2-port-data:catalog.json).
- **DC1 textures are raw IM2 or IMG blobs in `img.pak`.** The entries carry the magic `IM2\0` or `IMG\0` (dc1-data:gedit/e01/img.pak; the first two entries carry `IM2\0`, and the count of 12 is unverified). DC1's port overrides `LoadTexture` to take a `TM2_head` (`chronicle:port/src/nowload.cpp:320-325`). The DC1 port has no texture catalog.
- **The pack container is shared, the map pack nesting is not.** Both use a 64-byte name followed by offset, size and next words, with data at entry + offset (`chronicletwo:ps2/include/dataread.hpp:126`, 0x4C bytes; `chronicletwo:ps2/src/dataread.cpp:1075` and `chronicle:ps2/src/dataread.cpp:701`; `refs/DCExtractor/Specifications/Pack/PAK.md`). DC1 `mds.pak` is flat: 14 `.mds` entries (unverified; the first entries are `e01s06_0.mds` and `e01s01_1.mds`). DC2 `.mpk` nests one level: each map has one `*_0.pcp` entry, and the scenes sit inside it (dc2-data:map/g/g01/g01.mpk; the first name is `g01_0.pcp`, and the entry count is unverified).
- **Scene and model headers are close.** The MDS header and 0x70-byte object records match, and so does the MDT header frame, except the word at 0x24 and the material layout (`chronicle:ps2/include/mdt.hpp:10,27`; `chronicletwo:ps2/include/mg_visual.hpp:50,77`). The existing lineage note checked these against bytes. Not re-checked here.
- **Collision is the hard incompatibility.** DC1 reads an explicit collision set at `model->mesh_ofs`: `MDT_COLLISION` holding `MDT_CPOLY` records with per-triangle info indices (`chronicle:ps2/src/collisionmdt.cpp:150-160`, `chronicle:ps2/include/mdt.hpp:38-56`). DC2 builds collision from the draw faces at `faces_ofs`. `CreateCollisionMDT` returns NULL for any triangle-strip primitive (`chronicletwo:ps2/src/collision.cpp:565`) and for any colour-indexed face (`:569`). Surface attributes come from the material's diffuse channels (`:601-606`).
- **The DC2 area encoding is fragile.** `area_kind` is a `short` set from `materials[n].diffuse[2] * 0.7f + 0.01f` (`chronicletwo:ps2/src/collision.cpp:601-606`). The `diffuse` field is a float vector (`chronicletwo:ps2/include/mg_visual.hpp:78`) and is the colour the material draws with (same header, `:78`). Reaching area kind 5 (flat) needs a diffuse value near 7.1, and kind 11 (no place) needs about 16. A bake through this path would therefore change how the surface is drawn unless it uses a separate material (inference from the arithmetic and the field comment).
- **The area-kind enumerations do not overlap.** DC1 `AreaKind` (`chronicle:ps2/include/collision.hpp:11`) and DC2 `CCPolyAreaKind` (`chronicletwo:ps2/include/collision.hpp:41`: none 0, water 1, flat 5, fishing water 7, healing 8, edit walk 9, no place 11) use different values with no shared table.
- **Movement queries are engine-specific.** DC1 `EdMoveChara` (`chronicle:ps2/src/ebattle.cpp:1504`) is not the function that holds the loop; the loop that gathers `CCPoly` lists with `CFrame::PickUpNearPoly` on the part's collision frame is in `EdMoveVillager` (`chronicle:ps2/src/editloop3.cpp:1379`, loop at `:1487-1490`) and takes floor height from `CCollisionMDT::GetMaxY` (`chronicle:ps2/src/collisionmdt.cpp:169`), a vertical line test with no y bound. DC2 uses `CCollisionMDT::GetMaxY` (`chronicletwo:ps2/src/collision.cpp:115`), `CColFrame::PickUpNearPoly` (`:324`) and `CCollision::Intersection` (`:254`). Both trees define `CCollisionMDT` and `CCPoly` with different layouts, so one binary cannot hold both.
- **Lights, fog and sky exist in both, with different fields.** DC1 town config: `AMBIENT`, `LIGHT_C` once per time of day (`LIGHT_NO`), `FOG near,far,r,g,b,...`, `BG_COL` and `BG_COL2` gradient colours, and sun MDS layers (`SUN` entries 1 to 4, for example `e01s01_1.mds`; the e01 config has no moon entry) loaded in `LoadGroundData` (dc1-data:gedit/e01/mapinfo.cfg; command table `chronicle:ps2/src/edit.cpp:2684-2688`; `chronicle:ps2/src/editloop.cpp:4825`). DC2 map script: `LIGHT_SET` blocks with `AMBIENT`, `FOG_ENABLE`, `FOG`, then `TIME_LIGHT_NUM` and `SKY_INFO` (dc2-data:map/g/g01/g01.map; command table `chronicletwo:ps2/src/mapinfo.cpp:27-67`). DC2 sky is an optional `.sky` file, 56 in the extract, none for g01 or d01f01. DC1 dungeon config carries `FOG`, `AMBIENT`, `LIGHT_C`, `BG_COL` and `URA_*` variants (dc1-data:dun/d01main_a.cfg).
- **DC1 random floors use the global RNG.** `BtCleatRandomMap` (`chronicle:ps2/src/dun/gameloop.cpp:6313`) calls `buildRandomMap(6, 1)` (`:6382`). That draws `map_seed` from `rand()` and reseeds the RNG with it (`chronicle:ps2/src/dungeonmap.cpp:3456-3457`; the function starts at `:3439`). The grid is 20 by 20 cells (`chronicle:ps2/include/dungeonmap.hpp:218`; `c1-dungeons.md`); the 160-unit cell size is unverified. Non-grid floors use `BtCleatFreeMap` (`chronicle:ps2/src/dun/gameloop.cpp:6454`).
- **DC1 floor selection is script-driven.** `_SET_DUNGEON_MAP` stores the floor file name and `map_type` (`chronicle:ps2/src/btsysscript.cpp:623-628`). `_LOAD_DUNGEON_MAP2` calls `BtMapJumpLoad` (`:631-634`). `_SET_RANDOM_MAP` picks the random or free build by `map_type == 1` (`:644-650`).
- **DC2 floor selection is one map load plus a generator.** `_LOAD_DUNGEON_MAP_FILE` (`chronicletwo:ps2/src/event_func.cpp:5580`) calls `LoadDungeonMapFile` (`chronicletwo:ps2/src/dng_event.cpp:2077`), which calls `GetLoadMapInfo` (`:2193`) and `DngMainScene->LoadMap` (`:2198`). The call is `DngMainScene->LoadMap` (verified). That it reaches the same `LoadMapFromMemory` path as a town (`chronicletwo:port/src/sceneload.cpp:33`) is unverified. It then calls `AutoMapGen.Build()` (`:2315`, `chronicletwo:ps2/src/automap.cpp:2264`). `Build` has a fixed-floor mode from one preset (`AUTOMAP_GEN_FIXED_FLOOR`, `automap.cpp:2275`), a preset-by-floor mode (`:2285`), and a fixed-start 20 by 16 random mode (`:2320`).
- **The part vocabularies differ.** DC1 has 72 part slots in its grid (`chronicle:ps2/include/dungeonmap.hpp:215`) and `MapPartsNo` values 0 to 25 (`chronicle:ps2/include/dungeonparts.hpp:25`). DC2 has 277 `AUTOMAP_PARTS_INFO` entries in families `door`, `way`, `room`, `part` and `step` (`chronicletwo:ps2/include/automap.hpp:38-60`, `:137`). DC2 presets live in `dungeon/cfg_file/<name>.cfg`, as `RD` rows of part id and rotation (the `cfg_file` directory exists in the extract; the row layout is unverified).
- **Each game has its own RNG, file reader and asset set.** Ixion keeps each game in its own DLL, so `rand()` state, the file layer and the asset catalog are per game (inference from the design's per-DLL rule in `ixion:docs/DESIGN.md` and the HOP-V0 spec). Foreign data has to reach each game's own reader, so the rip directory must be visible to both DLLs.

## How it works

### Native travel (v1 part a)

The destination DLL receives a travel request at a checkpoint, on its own fiber. It then uses its own jump:

- **DC1.** Set the jump state the way `MapJump` does (`NextMapNo`, `StartEventNo`) and let the main loop's mode switch take it (`chronicle:ps2/src/main.cpp:982-996`). For a dungeon, `GameInit` reads `main_select_menu_no` (`chronicle:ps2/src/dun/gameloop.cpp:1414`), sets the floor with `SetNowFloor(0)` (`:1949`), and loads the floor script (`BtSystemScriptLoad`, see the existing `c1-dungeons.md`). A floor other than 0 must therefore be set after `:1949`. Inference: a hook placed before `GameInit` would be overwritten.
- **DC2.** For an outdoor town, `EditMapJump` (`chronicletwo:ps2/src/editloop.cpp:2713`) loads the map and the roster (`LoadVillager`, `:2877`). Interiors use `GotoInterior` and `InteriorMapJump`. For a floor, the DC2 path runs through an event that calls `_LOAD_DUNGEON_MAP_FILE` (`chronicletwo:ps2/src/event_func.cpp:5580`); a native jump needs such an event or a call into `LoadDungeonMapFile` (`dng_event.cpp:2077`) with the save's dungeon state already set. Inference: calling `LoadDungeonMapFile` directly from a fiber is possible but skips the event state the game sets before it.

### DC1 town load (`gedit/eNN`)

1. `EditInit` (`chronicle:ps2/src/editloop.cpp:703`; port override `chronicle:port/src/editloop_init.cpp:124`) maps `MapNo` to `EditMapName` (`eNN` when `MapNo` is below 9, `sNN` for sub maps above 10) and sets `EditDataDir` to `gedit/<name>/` (`:741`).
2. It loads the map config through `LoadEditMapData` (`chronicle:ps2/src/editmapscript.cpp:524`), which runs the text parser on `mapinfo.cfg`.
3. `LoadGroundData` (`chronicle:ps2/src/editloop.cpp:4794`) loads `mds.pak` (`:4800`), the sky layers (`:4825`), then `scene.scn` (`:4930-4932`).
4. For each `MAP_PARTS_INFO`, it finds the `.pts` record (`SearchPTS`, `:4981` and `:5168`) and calls `LoadPTS`. The port's `LoadPTS` (`chronicle:port/src/editloop_parts.cpp:44`) maps the archive's LOD0 to LOD3, shadow, collision (slot 5), shade, extra and camera records into `CMapParts` (`names[0..8]`) (unverified).

Collision for a town part therefore comes from a model record in the parts archive, not from a separate file. The archive's `info_offset` gives the definition block that `EPartsLoad` decodes (`chronicle:port/src/eparts_port.hpp`).

### DC1 floor load (`dun/mpd_pack/<name>.mpd` and `dun/<name>.cfg`)

1. The floor script calls `_SET_DUNGEON_MAP(file, map_type)` and then `_LOAD_DUNGEON_MAP2` (`chronicle:ps2/src/btsysscript.cpp:623-634`).
2. `BtMapJumpLoad` (`chronicle:ps2/src/shot_freefuncs.cpp:1215`) loads the pack, then the config (`:1310-1316`). `TEIGIAnalyz` parses `DEF_PATS` blocks with `PT_BASE`, `PT_COLS`, `PT_CAM`, `PT_FIRE`, `PT_WATER`, `PT_MARKER` and `PT_NPC` (`chronicle:ps2/src/itemdata.cpp:478`; counts in the existing `c1-dungeons.md`).
3. `TEIGIImgLoad` and `TEIGIMdsLoad` load the pack's textures and models (`:1326-1328`).
4. The floor is built by `_SET_RANDOM_MAP`, which runs `BtCleatRandomMap` (grid, `map_type == 1`) or `BtCleatFreeMap` (free placement). Both end with `buildEventData` and `SetupEvent`.

### DC2 town and floor load

1. `GetLoadMapInfo(&load_info, map_no)` resolves the name to the file family (`chronicletwo:ps2/src/mapjump.cpp:251-300`), with the `_<lang>.stb` override at `:372-410` (unverified beyond `:372`).
2. `LoadMapFromMemory` runs in steps (`chronicletwo:port/src/sceneload.cpp:33`; the step names are unverified). `CREATE` builds the `CEditMap`. `MAP_INFO` parses the `.map` script (`map.map_info.LoadMapInfo`). `DATA` runs `CMap::LoadData` on the `.mpk` and `.ipk`. `EFFECT` creates effects from `.efp` and, when present, the sky from `.sky` (`sky_tex_block`).
3. The floor path adds `place_parts_max = 400` (`chronicletwo:ps2/src/dng_event.cpp:2196`) and, for generated floors, `AutoMapGen.Build()` places preset parts (`IndexToPartsPlace`, `chronicletwo:ps2/src/automap.cpp:2316`).

### What movement and collision need from a map

Both games need four things for a walkable map. A foreign map must supply all four in the destination's own structures.

- **Triangles near a point or box**, with a box query (`PickUpNearPoly`) on a collision frame. DC1 `CFrame::PickUpNearPoly` (defined at `chronicle:ps2/src/frame.cpp:1414`, called at `chronicle:ps2/src/editloop3.cpp:1490`); DC2 `CColFrame::PickUpNearPoly` (`chronicletwo:ps2/src/collision.cpp:324`).
- **Floor height at a point**, a vertical query. DC1 `CCollisionMDT::GetMaxY` (`chronicle:ps2/src/collisionmdt.cpp:169`); DC2 `CCollisionMDT::GetMaxY` (`chronicletwo:ps2/src/collision.cpp:115`).
- **Per-triangle attributes**: ground kind, foot sound, area kind, ignore mask. DC2 `CCPoly` fields (`chronicletwo:ps2/include/collision.hpp:70-76`); DC1 `CCPolyInfo` fields (`chronicle:ps2/include/collision.hpp:55-58`).
- **Event points and triggers**, separate from collision. DC1 `ED_EVENT_POINT` lists in the map's event data (`chronicle:ps2/src/editloop.cpp:4808`, `work.events.points`); DC2 `FUNC_POINT` blocks in `.map` (`dc2-data:map/a/a01/a01ia.map`).

### Options, ranked

Each option lists its verdict, its blockers and the cheapest experiment. Experiments are described, not run.

**(d) Background only.** Verdict: feasible, low payoff, and cheapest. Blockers: in Hop each game has its own window and fiber (`ixion:docs/HOP-V0.md`, F10 section, "hide its window, show and raise the other's"), so a foreign background has to be drawn by the destination in its own window. Data is simple: DC1 `BG_COL` and `BG_COL2` are colour triples (dc1-data:gedit/e01/mapinfo.cfg), and DC1's fog parameters are already applied through the port's `MGSetFogParm` (`chronicle:port/src/mglib.cpp:787`). Cheapest experiment: at the checkpoint, read the origin's `BG_COL` and `FOG` values from its town config and set the destination's clear and fog colours. This is a change to one or two calls. A picture-based skybox is a second step and needs the texture route in (b).

**(a) Load directly (the other engine reads the other game's files as-is).** Verdict: not feasible. The containers and the scene and model headers match, but four things stop a direct load.

- DC1 town data needs the `scene.scn` PTS reader and the EPARTS decoder (`chronicle:port/src/eparts_port.hpp`). DC2 has neither.
- DC1 floor data needs the `TEIGI` config parser (`chronicle:ps2/src/itemdata.cpp:478`). DC2 has no equivalent.
- DC2 maps need the SPI `.map` interpreter (`chronicletwo:ps2/src/mapload.cpp`). DC1 uses its own editor script grammar (`chronicle:ps2/src/editmapscript.cpp:321`).
- Collision: DC2's builder returns NULL for DC1 strip meshes (`chronicletwo:ps2/src/collision.cpp:565`), and DC1 collision is a separate set that DC2 never reads.

Cheapest experiment: from the DC2 side, feed one DC1 model (for example `e01s06_0.mds` from `mds.pak` (`e01h06_0.mds` is not in that archive)) to the DC2 MDS loader in a headless test. Check the object count, the vertex count and whether the face section parses. This tests the header claim and nothing else. If it parses, the next test is `CreateCollisionMDT` on the same model, which should fail for strip meshes, and that failure is the expected result.

**(b) Convert offline.** Verdict: feasible for a one-way bake of a town or floor, and large. The target layout is DC2's: `.map` script, `.mpk` with a `.pcp` holding MDS and MDT, `.ipk` as converted PNG catalog rows, `.efp` and `.sky`. Blockers, in order of difficulty:

- **Collision re-encoding.** Emit DC2 faces from the DC1 collision set (`MDT_CPOLY` records). Each triangle needs a material whose diffuse channels encode its area kind, but the encoding (`* 0.7 + 0.01` into a `short`) pushes kinds beyond 1 into diffuse values the renderer would also draw. The bake needs a separate material per area kind, with the draw colour carried elsewhere. The DC1 to DC2 kind table does not exist and must be designed.
- **Georama layout.** A DC1 town is a 16 by 16 cell grid of parts (`chronicle:ps2/include/editarea.hpp:47`; the other cites are unverified). A DC2 map is a list of placed pieces with position, rotation, scale and collision type (`PIECE` blocks). The bake turns each cell into a `PARTS` block and one `PIECE` per model, with quarter-turn rotation. Inference: this is a mechanical transform, but the part semantics (roads, rivers, bridges, ground) need their own rules.
- **Events and scripts.** DC1 `event.stb` and DC2 `.stb` scripts use different command tables (`chronicle:ps2/src/editmapscript.cpp:321`, `chronicletwo:ps2/src/mapload.cpp:2129`). Function points must be re-expressed as DC2 `FUNC_POINT` entries.
- **Lights and fog.** DC1 `LIGHT_C` and DC2 `LIGHT_SET` are both per time band, so the time bands can be matched. The field meanings differ and must be mapped by hand.
- **Textures.** Each DC1 `IM2` or `IMG` needs decoding and a `port_data` catalog row (kind `im2` or `img`). The DC2 catalog already has `im2` rows (58) and `img` rows (3), so the path exists but the row format for DC1 images is unverified.

Cheapest experiment: bake one DC1 part (for example `e01h01`, LOD0 plus its collision set) into a DC2 `PCP`, add one `PIECE` to a copy of a small DC2 map, and load it. Two checks at once: the piece draws with its converted texture, and `CreateCollisionMDT` returns a collision object for the converted face set. This tests the two hardest links without a full town.

**(c) Assemble DC1 dungeon parts with DC2's generator, or the reverse.** Verdict: the highest payoff for dungeons and the highest risk. The two generators are different designs, so this needs a part mapping, not a file change.

- **DC2 generator, DC1 parts (forward).** `CAutoMapGen` joins rooms from `room_info` presets (`RD` rows) and link flags (`AUTOMAP_LINK`). Each DC1 part must become a DC2 `PARTS` entry in a family (`door`, `way`, `room`, `part`, `step`), with the matching link semantics and room size. Blockers: DC1 road, wall, door and floor kinds (`MapPartsNo` 0 to 25) have no DC2 family mapping; DC1 collision and camera collision (`PT_COLS`, `PT_CAM`) must be re-encoded as in (b); DC1 boxes, atra and events come from `buildEventData` and would need DC2 equivalents. Cheapest experiment: take one DC1 floor's grid as a fixed list of part ids (captured from a seeded `buildRandomMap` run, `chronicle:ps2/src/dungeonmap.cpp:3456`), write a DC2 preset with those ids, and run it through `AUTOMAP_GEN_FIXED_FLOOR`. This tests the part mapping on a fixed floor with no generator logic.
- **DC1 generator, DC2 parts (reverse).** `buildRandomMap` fills a fixed grid of part slots with `MapPartsNo` values (`chronicle:ps2/include/dungeonparts.hpp:25`), and the grid holds 72 slots (`chronicle:ps2/include/dungeonmap.hpp:215`). Adding DC2 parts means widening the enum and the `PT_*` tables in the `.cfg` (`TEIGI`). Blockers: the enum and tables are compile-time sized in the retail unit, and the DC2 parts would need DC1 `.mds`-format models (see (b)). Cheapest experiment: replace one `PT_BASE` model in a copy of a DC1 `.mpd` with a converted DC2 model, keeping the DC1 part id, and check draw and collision. This is the smallest real DC2 model in a DC1 floor.

## Proposed Ixion code

These are signatures and pseudo-C++ for the next step. They are not implemented here. Each lives in a new `port/src` unit in the game's own tree, so the retail units stay unchanged (`chronicle:port/src/dungeonmap.cpp:28` and `chronicletwo:port/src/map.cpp:7` show the override pattern).

1. **Native travel dispatcher, one per DLL.** File: `port/src/ixion_visit.cpp` in each game. Call site: the checkpoint hook that runs on the destination fiber, after the origin has parked (`ixion:docs/HOP-V0.md` travel section). Pseudo-body for DC1:

   ```c++
   // Returns 1 when a jump was queued. Runs on the destination fiber at its checkpoint.
   int IxionVisit_Apply(const IxionTravel *travel) {
       // "town:N": N is a MapNo in 0..4 or a sub map 11 and up.
       // "dungeon:D:F": D is a Dungeon id 0..6, F the floor.
       if (parse_town(travel->destination, &map)) {
           MapJump(map, 0);                       // main.cpp:1053, NextMapNo/StartEventNo only
           return 1;
       }
       if (parse_dungeon(travel->destination, &dungeon, &floor)) {
           MapJump(200 + dungeon, 0);             // main.cpp:982-996 sets main_select_menu_no
           pending_floor = floor;                 // applied after GameInit's SetNowFloor(0), dun/gameloop.cpp:1949
           return 1;
       }
       return 0;
   }
   ```

   The DC2 body calls `EditMapJump(SearchMapNo(name))` (`editloop.cpp:2713`; the existing call is at `editloop.cpp:877`, inside `EditInit` at `:548`; `mapselect.cpp:385` is unverified) for towns and raises the floor event for dungeons. The floor path is an open question (see below).

2. **PTS directory reader (data only, for (b) and (c)).** File: a new unit in `port/src`. Signature: `int Dc1Scn_ListParts(const uint8_t *scn, size_t size, Dc1PtsEntry *out, int cap);`. It reads the `SCN\0` header and the 0x30-byte `PTS_ENTRY` records (`chronicle:ps2/src/dispctrl.cpp:19-38`) and returns name, offset and size for each entry. Called once when a converted map is opened. It touches no engine globals.

3. **Collision from a DC1 collision set (for (b)).** File: `port/src/collision_dc1.cpp` in the DC2 tree. Signature: `CCollisionMDT *CreateCollisionFromDc1Set(const MDT_COLLISION *set, mgCMemory *memory, const uint8_t *area_table);`. Body: for each `MDT_CPOLY`, copy the three vertices, compute the normal with `mgPlaneNormal` as `CreateCollisionMDT` does (`chronicletwo:ps2/src/collision.cpp:609`), and set `area_kind` from `area_table[info_index]`. Call site: `LoadCollisionFile` (`chronicletwo:ps2/src/collision.cpp:456`), when the MDT has a DC1 collision set. The `area_table` is the missing DC1 to DC2 kind table.

4. **Texture catalog rows (offline, for (b)).** Signature: `void IxionTexture_AddRow(const char *source_key, const char *png_path, int width, int height, const char *kind);`. It appends one row to `port_data/catalog.json`, in the schema `texture_catalog::Load` expects (`kazarov:src/cpp/platform/texture_catalog.cpp:53-83`). The loader rejects legacy `palette` and `levels` fields for `texture` entries, so rows must use the newer `variants` form.

5. **Preset floor from a grid (for (c), forward).** Signature: `void IxionDungeon_UseGrid(const IxionGrid *grid);`. Body: fill `room_info[0]` with `w`, `h` and the `RD` rows from `grid`, set `gen_flag |= AUTOMAP_GEN_FIXED_FLOOR`, as `dng_event.cpp:2314` does, so the flags already set survive, and call `AutoMapGen.Build()` (`chronicletwo:ps2/src/automap.cpp:2275`, `:2264`) from the same place as `LoadDungeonMapFile` (`dng_event.cpp:2315`). The `room_info` pointer is at `chronicletwo:ps2/include/automap.hpp:397` and `AUTOMAP_ROOM_INFO` at `:182-191` (the `:92-99` range is the `AUTOMAP_GEN_FLAG` enum); `CreatFixedMap(0)` reads `room_info[preset_no]` (`chronicletwo:ps2/src/automap.cpp:2084`).

6. **Background colours (for (d)).** Signature: `void IxionBackground_Apply(const IxionOriginLook *look);`, where `IxionOriginLook` holds the origin's `BG_COL`, `BG_COL2`, fog near and far, and fog colour. Body: call `MGSetFogParm` (`chronicle:port/src/mglib.cpp:787`) and set the clear colour. Call site: the destination's first frame after the travel.

## Risks and blockers

- **Collision mismatch is the main blocker for (a), (b) and (c).** DC1's explicit collision set, DC2's face-derived collision with material-coded attributes, and non-overlapping area-kind values all have to be bridged. A wrong mapping makes floors walkable where they should not be, or blocks them.
- **Area encoding can change rendering.** The DC2 area encoding works through the material diffuse channel, which is also the draw colour (`chronicletwo:ps2/include/mg_visual.hpp:78`). A bake through that channel would change how surfaces look unless it uses separate materials.
- **Strip and colour-indexed meshes are rejected by the DC2 builder.** Any DC1 model used as collision must be re-encoded as DC2 faces, or DC2 gets no collision for it (`chronicletwo:ps2/src/collision.cpp:565`, `:569`).
- **DC1 floors depend on the global RNG.** `buildRandomMap` reseeds `rand()` (`chronicle:ps2/src/dungeonmap.cpp:3456-3457`). Any cross-game copy of a floor needs the seed, or a captured grid, to reproduce the same layout.
- **Event and gameplay state do not carry over with geometry.** Treasure boxes, atra, healing points, doors and event triggers have engine-specific state (`CDungeonMap` lists in DC1, `CAutoMapGen` cells in DC2). A baked floor carries layout, not these rules.
- **Shared names with different layouts.** `CMap`, `CMapParts`, `CCollision`, `CCollisionMDT`, `CCPoly` and the MDT and MDS headers exist in both trees with different layouts. A single binary needs renaming or per-DLL isolation, which Hop already provides.
- **DC2 texture data in the extract is zero-filled.** The PC port reads converted PNGs, so the game runs from `port_data`. Anything that reads the raw `.ipk` (for example a tool that re-extracts textures) will get zeros. Treat `port_data` as the source of truth for DC2 textures.
- **Licensing and publication.** Baked assets derive from game data. They belong in the git-ignored rip area. This note contains offsets, names and counts only.
- **Native travel into a DC2 floor needs the event path.** Calling `LoadDungeonMapFile` directly skips the event state the game sets before it (`chronicletwo:ps2/src/event_func.cpp:5580`). Getting this wrong would load a floor with the wrong save state.

## Open questions

- **Dungeon floor entry for v1 (DC2).** Is there a direct event id that starts a floor, or must the destination raise an event that runs `_LOAD_DUNGEON_MAP_FILE`? The answer decides whether v1 needs a script hook in DC2.
- **Floor number after `GameInit` (DC1).** Is `UserStatus->cur_floor` read before or after `SetNowFloor(0)` (`chronicle:ps2/src/dun/gameloop.cpp:1949`) on every dungeon entry path, including the Gallery of Time? The v1 hook has to set the floor at the right point.
- **DC1 to DC2 area-kind table.** What does each DC1 `AreaKind` (`chronicle:ps2/include/collision.hpp:11`) mean in play, and which DC2 `CCPolyAreaKind` (`chronicletwo:ps2/include/collision.hpp:41`) is its nearest equivalent? Shared code paths (shadow or camera-height rules) may decide this.
- **Are DC1 collision sets stored as faces anywhere?** The DC1 `MDT_COLLISION` set is read by its own query code. Does any DC1 path read the draw mesh as collision, which would make the strip rejection moot?
- **Do DC2 material diffuse values ever exceed 1 in shipped data?** If yes, the area encoding is in use and the kind range is known. If no, the path is dead as written.
- **DC2 `.sky` format and the DC1 sun layers.** Which fields of `.sky` (`chronicletwo:port/src/sceneload.cpp`, EFFECT step) correspond to DC1's `sun1`, `sun2`, `sun3` and `moon` MDS layers?
- **Which DC1 frame loop should host `IxionVisit_Apply`?** The DC1 port's per-frame function is not confirmed here (`chronicle:port/src/gameloop.cpp` and `chronicle:port/src/main.cpp` are candidates). The DC2 candidate is `MainLoop` (`chronicletwo:port/src/mainloop.cpp:73`).
- **Are the `-m`, `-a` and `-c` piece-name suffixes in DC2 `.map` files collision flags?** The lineage note asks this; it matters for (b) because the bake must set them correctly.
