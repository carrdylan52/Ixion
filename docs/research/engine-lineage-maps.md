# Engine lineage: maps and dungeon geometry

## What this covers

How the two decompiled ports load and build their maps: Chronicle (DC1) town
("Georama", `gedit/eNN`) and dungeon floors (`dun/*.cfg` plus `mpd_pack`), and
ChronicleTwo (DC2) towns and dungeon floors (`map/<x>/<xNN>/<xNNyy>/` with
`.map`, `.cfg`, `.mpk`, `.ipk`, `.stb`). It compares the container formats
(PAK, MDS scene, MDT model), the collision and surface-attribute encoding, the
script grammars, the dungeon generators, and the symbol-level overlap that
decides whether both engines could share one binary.

It answers the brief's question: could a DC1 town or floor be loaded by the DC2
engine, or the reverse, and is one engine per world the only realistic path.

Citation conventions: `chronicle:` is the DC1 decomp, `chronicletwo:` is the DC2
decomp, `kazarov:` is the build tool, `refs/DCExtractor/` is the community format
reference. `dc1-data:` and `dc2-data:` mean the extracted PAL disc trees,
relative to their roots. Byte offsets are from those files. Anything not checked
against bytes or code is labelled as inference.

## Key facts

- **The model containers are one family.** The MDS scene header is 16 bytes
  with the object count at offset 8 in both games (`chronicle:ps2/include/mds.hpp:20`;
  `chronicletwo:ps2/include/mg_dataset.hpp:64`). The scene object record is 0x70
  bytes in both, with a name at +8 (32 bytes), a model offset at +0x28, a
  parent index at +0x2C and a 4x4 matrix at +0x30 (`chronicle:ps2/include/mds.hpp:31`;
  `chronicletwo:ps2/include/mg_dataset.hpp:79`, size assert at line 88). Checked
  by bytes: `dc1-data:gedit/e01/mds/e01a03_0.mds` has object count 1 and its
  object record points at offset 0x80, where the `MDT\0` block starts.
- **The MDT model header is the same 0x40-byte shape with a different field
  naming.** Both put the vertex count at +0x0C, vertex offset at +0x10, normal
  count and offset at +0x14/+0x18, colour count and offset at +0x1C/+0x20, the
  face/mesh offset at +0x28, UV count and offset at +0x2C/+0x30, and the material
  offset at +0x38 (`chronicle:ps2/include/mdt.hpp:10`; `chronicletwo:ps2/include/mg_visual.hpp:50`,
  size assert at line 69). DC2 also names a section size at +0x24 and a material
  count at +0x34 and adds a trailing `unk_3c`. DC1 has no named field there: its
  size word is at +0x08, +0x24 is `unk_24`, and +0x34 is the third `uv[]` word.
  The names differ:
  DC1 calls +0x28 `mesh_ofs` and +0x38 `info_ofs`, DC2 calls them `faces_ofs`
  and `material_ofs`. Checked by bytes: in `dc2-data:map/d/d01/f01/d01f01.mpk`
  the MDT at byte 30336 has vertex count 0x16 at +0x0C and vertex offset 0x40.
- **The face/strip record and the 16-byte polygon block header match.** DC1's
  visual mesh starts with a 16-byte header whose second word is 0x10 and whose
  third word is the strip count (`chronicle:ps2/src/visualvu1.cpp:737-757`). DC2's
  `MDT_FACES` has the same shape: `header_size` 0x10 and `prim_num` at +8
  (`chronicletwo:ps2/include/mg_visual.hpp:95`). Each strip or face record is
  three words: type (style plus flags), index count, material index
  (`chronicletwo:ps2/include/mg_visual.hpp:110`). Checked by bytes: a DC1 town
  MDT in `dc1-data:gedit/e01/scene.scn` (MDT at byte 3438688) has its strip
  block at header+0x12B0, with 15 strips; the first strip is type word 3,
  count 0x1D4, material 0.
- **DCExtractor's MDS spec matches the MDS and bone layout, but its MDT header
  description is internally inconsistent.** `refs/DCExtractor/Specifications/Models/MDS.md`
  describes the 112-byte bone record correctly. Its prose (around line 88) lists
  `vertexCount` directly after the header-size word, which would be +8, but its
  struct listing (lines 208-211) puts `meshDataSize` at +8 and `vertexCount` at
  +12. Both engine structs and the sample bytes put a size word at +8 and the
  vertex count at +12. Trust the engine structs and the bytes for that field.
- **Collision is built differently.** DC1 keeps collision triangles in a
  separate `MDT_COLLISION` section at `mesh_ofs`, with an info index per
  triangle into an attribute table at `info_ofs` (`chronicle:ps2/include/mdt.hpp:56`;
  `chronicle:ps2/src/dataset.cpp:777-822`). DC2 has no collision section. It
  derives triangles from the visual faces and reads surface attributes from the
  material's diffuse channels (`chronicletwo:ps2/src/collision.cpp:532-617`, the
  attribute copy at lines 601-604). It rejects triangle-strip and coloured faces
  (`chronicletwo:ps2/src/collision.cpp:564-570`).
- **The collision triangle is the same size in both.** `CCPoly` is 0x50 bytes in
  both, with the same first attribute words at 0x40-0x47 (`chronicle:ps2/include/collision.hpp:120`;
  `chronicletwo:ps2/include/collision.hpp:79`). DC2 adds `parts_no`, `attr` and
  `attr_value` in the last 8 bytes. DC1 leaves those bytes as `unk_48[8]`.
- **The area-kind values are not the same.** DC1 `AreaKind` has FADE_OUT 2,
  AMBIENT 3/4 and HIGH_CAMERA 10 (`chronicle:ps2/include/collision.hpp:11`).
  DC2 `CCPolyAreaKind` has WATER 1, FLAT 5, FISHING_WATER 7, HEALING 8,
  EDIT_WALK 9 and NO_PLACE 11 (`chronicletwo:ps2/include/collision.hpp:41`).
  The same field carries different meanings, so a raw copy misclassifies
  surfaces.
- **DC1 uses one attribute as an event trigger.** A non-zero `ground_kind` under
  the town character starts an event (`chronicle:ps2/src/editloop.cpp:1961-1963`).
  DC2's `ground_kind` is documented as "what the surface is made of"
  (`chronicletwo:ps2/include/collision.hpp:67`). Whether DC2 has an equivalent
  trigger was not checked.
- **Town part files are typed by suffix in DC1 and by a script `TYPE` in DC2.**
  DC1's `BUILD` entries in `dc1-data:gedit/e01/mapinfo.cfg` list per-part files:
  `_0`, `_1`, `_2` for LOD levels, `_s` for shadow, `_a` for collision, `_k`, and
  `_r` for ripples (unverified: the sampled `BUILD` lines are bare names, with `_0.mds` only in a comment). `LoadMapObject` assigns the roles by slot
  (`chronicle:ps2/src/edit_in.cpp:278-312`). DC2 model packs carry a text
  script with `TYPE 0` (model), `1` (collision), `2` (camera collision) and `3`/`4`
  (character) per entry, read by `pcpTYPE` (`chronicletwo:ps2/src/mdslist.cpp:638-665`).
- **DC1 towns and DC1 floors are two different part classes.** Towns use
  `CMapParts` with `CMapObject` (`chronicle:ps2/include/mapparts.hpp:49`).
  Floors use `CDungeonMap` and `CDungeonParts` over a 20 by 20 cell grid of
  `MAPPARTS` (`chronicle:ps2/include/dungeonmap.hpp:84,198`;
  `chronicle:ps2/include/dungeonparts.hpp:138`).
- **DC2 towns and floors are one class.** Both are loaded as `CMap` through
  `LoadMapFile` and the scene loader (`chronicletwo:ps2/src/mapload.cpp:2183`;
  `chronicletwo:ps2/src/sceneload.cpp:25-91`). Floors are reached through
  `GetLoadMapInfo` and `DngMainScene->LoadMap` (`chronicletwo:ps2/src/dng_event.cpp:2180-2199`).
  The procedural floor builder places named parts into the same `CMap`
  (`chronicletwo:ps2/src/automap.cpp:1992-1998`).
- **DC1 floor generation is a numbered-part grid.** `buildRandomMap` fills a
  20 by 20 grid with numbered parts from `MapPartsNo`, which has 70 entries
  (`chronicle:ps2/src/dungeonmap.cpp:3439`; `chronicle:ps2/include/dungeonparts.hpp:25`).
  Cells are 160 world units wide (`chronicle:ps2/src/dungeonparts.cpp:2147`).
  The floor type is set by the battle script (`chronicle:ps2/src/btsysscript.cpp:623-629`,
  `:644-650`); type 1 means grid.
- **DC2 floor generation is a named-part room builder.** `CAutoMapGen::Build`
  has four modes: a fixed floor, a preset floor from a room script, a 20 by 16
  fixed start, and a 14 by 14 random floor (`chronicletwo:ps2/src/automap.cpp:2264-2343`).
  The room script is `dungeon/cfg_file/<name>.cfg` (`chronicletwo:ps2/src/dng_event.cpp:2309-2316`).
  Its `GRID_SIZE` sets the cell size; `dc2-data:dungeon/cfg_file/d01f01.cfg` uses
  320 (`chronicletwo:ps2/src/automap.cpp:716-727`). The kind table
  `PartsInfoData` is static, with 277 entries named `wayNN`
  (`chronicletwo:ps2/src/automap.cpp:37`; `chronicletwo:ps2/include/automap.hpp:22`).
- **DC2 dungeon floors can run in the town loop.** `MakeDngTreeMapJumpNo` sends
  some floors to `LOOP_EDIT` (`chronicletwo:ps2/src/dngmenu.cpp:2730-2757`).
  `EditMapJump` (`chronicletwo:ps2/src/editloop.cpp:2713`) is the same entry used
  for towns.
- **DC1 towns run in `CEditGround` and `CMapParts`, not the dungeon engine.**
  The town path is `gedit/eNN/` with `NN = map_no + 1` for map numbers below 9
  (`chronicle:ps2/src/editloop.cpp:722`); interiors use `s0N` derived from `MapNo`
  (`:727-733`), and the directory is built from the name at `:741`.
  `LoadEditMapData` handles a compiled `mapinfo.cfb` and the text `mapinfo.cfg`
  (`chronicle:ps2/src/editmapscript.cpp:524-548`, the `cfb` branch at `:603`; the
  preference order is unverified).
- **DC1 floors are described by text plus a pack.** `dc1-data:dun/d01main_a.cfg`
  holds `DEF_PATS` blocks with `PT_BASE`, `PT_COLS` (collision) and `PT_CAM`
  (camera) model names, plus fire points. The floor's models are in
  `dc1-data:dun/mpd_pack/d01main_a.mpd`. `BtMapJumpLoad` reads both
  (`chronicle:ps2/src/shot_freefuncs.cpp:1215-1290`); the text is parsed by
  `TEIGIAnalyz` and the models loaded by `TEIGIMdsLoad`
  (`chronicle:ps2/src/itemdata.cpp:478`, `:693`).
- **DC2 map text is an SPI script; DC1 map text is a separate command table.**
  DC2 `.map` and `.cfg` files are run by `CScriptInterpreter` with tags for
  `PIECE`, `PARTS`, `PIECE_COL_TYPE`, `WATER_*` and so on
  (`chronicletwo:ps2/src/mapload.cpp:2183-2199`, `:2538`). DC1 uses
  `EditMapScript` with a command table (`chronicle:ps2/src/editmapscript.cpp:311`),
  and the floor text uses the `TEIGI` table (`chronicle:ps2/src/itemdata.cpp:61-170`).
- **Both ports compile the retail units with overrides.** DC1 overrides in the
  dungeon engine include `DrawMap`, `DrawDummyModel` and `DrawAtraBoll`
  (`chronicle:port/src/dungeonmap.cpp:340,567,588`). DC2 overrides a collision
  query in asm (`chronicletwo:port/src/collision_asm.cpp:13`) and map buffer
  setup (`chronicletwo:port/src/map.cpp:7`).
- **Both engines define the same names with different layouts.** `CMap`,
  `CCollision`, `CCollisionMDT`, `CCPoly`, `MDT_HEADER`, `MDS_HEADER`,
  `LoadCollisionFile` and `CreateCollisionMDT` appear in both decomps with
  different members and signatures (for example `chronicle:ps2/include/collision.hpp:96`
  and `chronicletwo:ps2/include/collision.hpp:188`). A single binary holding
  both would hit ODR and vtable clashes.

## How it works

### Containers and the shared model family

Both games wrap their data in 80-byte-header PAK archives. The header holds a
64-byte name, a length, an end offset and a type word
(`refs/DCExtractor/Specifications/Pack/PAK.md`). DC1 town model packs such as
`dc1-data:gedit/e01/mds.pak` (15 model names) and texture packs such as
`dc1-data:gedit/e01/img.pak` use this layout. The texture entries start with
an `IM2` magic in this sample. DC2 map packs use the same extension family:
`.mpk` (models, with the text script inside), `.ipk` (images), `.efp`
(effects), `.sky` and `.pcp` (`refs/DCExtractor/Specifications/Pack/PAK.md`).

A scene file is an MDS: 16-byte header, then 112-byte object records, then the
MDT blocks they point at (`refs/DCExtractor/Specifications/Models/MDS.md`).
The DC1 town file `dc1-data:gedit/e01/scene.scn` contains 132 `MDS` magic
hits (not all verified as block headers) and also `PTS`-tagged part records
naming model files. The `PTS` records are
inferred to be placement lists; their exact fields were not decoded.

Within an MDT, both engines use the same sections: vertices (16-byte
`sceVu0FVECTOR`), normals, colours, UVs, faces or strips, and materials. Material
records are 0x60 bytes in both. DC1 names a 44-byte texture field at +0x34
(`chronicle:ps2/include/mdt.hpp:27`). DC2 names a 32-byte texture field at the
same offset, followed by one unknown word and two extra floats
(`chronicletwo:ps2/include/mg_visual.hpp:77`).

### Visual drawing

DC1 walks the strip list in `visualvu1.cpp`, reading each strip's type and
count and feeding the VU1 packet builder (`chronicle:ps2/src/visualvu1.cpp:720-760`).
DC2 walks the face list with `mgCVisualMDT::DataAssignMDT`, which calls
`CreateFace` once per record (`chronicletwo:ps2/src/mg_visual.cpp:558-580`).
The record shape is the same (type, count, material), so a reader that maps
DC1 strips to DC2 faces is small. The style encodings may not be identical; see
Open questions.

### Collision

DC1 collision is an `MDT_COLLISION` section: a 16-byte block, then an 8-byte
set header (an unused word and the triangle count), then triangles of five
words each (three vertex indices, an info index and one unused word). The info index selects a 16-byte attribute record
(`chronicle:ps2/src/dataset.cpp:777-822`; `chronicle:ps2/src/collisionmdt.cpp:150-200`).
Queries use `CCollisionMDT::GetMaxY`, `Intersection` and `PickUpNearPoly`
(`chronicle:ps2/src/collisionmdt.cpp:169`, `:243`, `:373`).

DC2 collision is derived from the faces of each piece that has `col_type` 0
(`chronicletwo:ps2/src/mdslist.cpp:111-124`, the `col_type` test at line 116).
`CreateCollisionMDT` walks the face list, assumes one index word per vertex
(`words += 3` per triangle), and rejects strips and coloured faces
(`chronicletwo:ps2/src/collision.cpp:564-570`). It copies attributes from the
material diffuse floats, scaled by 0.7 and offset by 0.01: `ground_kind` from
channel 0, `foot_sound` from 1, `area_kind` from 2, and `ignore_mask` as
`1 - alpha` (`chronicletwo:ps2/src/collision.cpp:601-604`).

A DC1 collision triangle and a DC2 collision triangle therefore differ in how
they are stored (per-triangle info record versus per-material floats) and in what
the attribute numbers mean. The triangle geometry itself can be carried over.

### Town layout

DC1 town layout is data in `gedit/eNN/`: `mapinfo.cfg` (or `.cfb`) declares
the lighting, fog, `BUILD` entries and object events, while `gdata0.edt` holds
the player's placed ground. The placed parts come from a fixed catalogue of
24 part slots (`CMapParts[24]`), 16 river slots and 6 road slots
(`chronicle:ps2/src/editloop.cpp:769-772`). Placed-part counts are checked
against the plot stock (`chronicle:ps2/src/editground.cpp:113-118`).

DC2 town layout is a `.map` script that places named parts with `PARTS` and
`PIECE`. Each piece has a name, a position, rotation, scale, a collision type
and a time band (`chronicletwo:ps2/src/mapload.cpp:851-1131`). The parts
catalogue for a town is `dc2-data:map/g/g01/g01.gpi`, whose header is
`EDIT_PARTS_NUM 48` (keyword handler at `chronicletwo:ps2/src/editinfo.cpp:171`). The town
`g01.map` in the sample has 165 `PIECE` entries, of which 19 carry collision
type 1.

### Dungeon floors

DC1 floors are a grid of numbered parts or a free layout of parts, decided by
the battle script. For a grid floor, `buildRandomMap` picks a seed, lays out
rooms and corridors in the 20 by 20 grid, and then `setCollisionData` looks up
each cell's collision model by part number
(`chronicle:ps2/src/dungeonparts.cpp:2076-2160`). Per-box collision models are added in
`setCollisionData` (`chronicle:ps2/src/dungeonparts.cpp:2132-2138`; that they are treasure boxes is unverified),
and atla balls in `CDungeonMap::CreateCollision` (`chronicle:ps2/src/dungeonmap.cpp:1329`).

DC2 floors are authored maps, loaded by the same `CMap` path as towns. Random
floors come from `CAutoMapGen`: a room script gives a preset layout, the
generator grows a tree of rooms and links through the named parts, and
`IndexToPartsPlace` puts them into the map (`chronicletwo:ps2/src/automap.cpp:1942`;
the tree is grown in `RandomMapMainProc` at `:2128`). The dungeon's tree map is a separate graph of floors in
`CDngFloorManager`, loaded from `menu/dngmap/` tables (`chronicletwo:ps2/src/dngfloor.cpp:393-431`).

## Ixion hooks

- **DC2, map registry (`chronicletwo:ps2/src/mapselect.cpp:306,367,385,434`).**
  `GetMapPath` builds the `map/<x>/<xNN>/<xNNyy>/<name>` path, `GetMapName` and
  `SearchMapNo` resolve map numbers, and `map/map.lst` lists the files. A converted
  DC1 town could get a `map.lst` entry and a `MAP_TYPE_GEORAMA` type
  (`chronicletwo:ps2/include/mapselect.hpp:44`), which routes it through the
  existing town path in `EditMapJump`.
- **DC2, load seam (`chronicletwo:ps2/src/mapjump.cpp:251`).** `GetLoadMapInfo`
  fills `SCN_LOADMAP_INFO2`, including a second file slot that
  `SCN_LOADMAP_FILES_MAX = 2` allows (`chronicletwo:ps2/include/sceneload.hpp:28`).
  A converted overlay could be loaded through the second slot.
- **DC2, collision seam (`chronicletwo:ps2/src/collision.cpp:532-617`).**
  `CreateCollisionMDT` is the one place where DC2 turns a model into
  triangles with attributes. A converter or adaptor here could translate
  DC1-style attribute records into DC2 material floats, or remap the area-kind
  values, provided the input is known to be DC1 data.
- **DC2, tree-map routing (`chronicletwo:ps2/src/dngmenu.cpp:2730`).**
  `MakeDngTreeMapJumpNo` chooses the loop and map name for a floor. It is the
  narrowest point for routing a floor to a different map name.
- **DC2, floor generator input (`chronicletwo:ps2/src/dng_event.cpp:2309-2316`,
  `chronicletwo:ps2/src/automap.cpp:818`).** `SetupRoomInfo` reads a room script
  by name. A converted room script would have to use DC2 kind names (`wayNN`,
  `p01_gio`, `obj01`, `obj02`).
- **DC1, town object attach (`chronicle:ps2/src/edit_in.cpp:278-312`).**
  `LoadMapObject` attaches LOD, shadow, collision, shade and ripple models to a
  placed part by slot. A DC2-derived piece set would have to fill those slots.
- **DC1, floor entry (`chronicle:ps2/src/shot_freefuncs.cpp:1215`,
  `chronicle:ps2/src/btsysscript.cpp:623-650`).** `BtMapJumpLoad` is the single
  floor loader. `_SET_DUNGEON_MAP` and `_SET_RANDOM_MAP` pick the grid or free
  layout. Ixion could route a floor request here, but only to DC1 assets.
- **Linking (see Risks).** Any in-process mix needs separate translation units
  behind an interface, or a separate process.

## Risks and blockers

- **Visual format.** DC1 draws strips through VU1 packets, and DC2 draws faces
  through `mgCDrawPrim`. The records are close, but a DC2 engine cannot read
  DC1 models without a reader or a converter (`chronicle:ps2/src/visualvu1.cpp:720-760`;
  `chronicletwo:ps2/src/mg_visual.cpp:558-580`).
- **Collision attributes.** DC1 stores attributes per triangle; DC2 stores them
  per material and rejects strips and coloured faces. Copying the collision
  block raw gives wrong surfaces (`chronicletwo:ps2/src/collision.cpp:564-604`).
- **Area and ground semantics.** The same `area_kind` numbers mean different
  things (DC1 3/4 are ambient, DC2 1 is water, DC1 10 is high camera, DC2 11 is
  no-place). `ground_kind` is also an event trigger in DC1
  (`chronicle:ps2/src/editloop.cpp:1961`), with no confirmed DC2 equivalent.
- **Two script grammars.** DC1 towns use `EditMapScript`, DC1 floors use the
  `TEIGI` table, and DC2 uses SPI. Each needs its own parser, and a converter
  must emit DC2 `.map` and `.cfg` text.
- **Town gameplay state.** DC1 towns track plots, stock and the `gdata0.edt`
  ground save (`chronicle:ps2/src/editground.cpp:113`). DC2 has an `EDIT_PARTS`
  catalogue and its own save layout. Static geometry can move; the town's game
  state does not map across.
- **Dungeon grids.** DC1 has 20 by 20 cells of 70 numbered kinds at 160 units.
  DC2 uses a 14 by 14 random grid, a 20 by 16 fixed start, or a preset's own
  size, with 277 named kinds and 320-unit cells in the sampled floor. A DC2 floor cannot be placed into DC1's grid without re-gridding, and a
  DC1 floor cannot be expressed as a DC2 preset without a kind crosswalk.
- **Symbol clashes.** `CMap`, `CCollisionMDT`, `CCPoly`, `MDT_HEADER`,
  `MDS_HEADER`, `LoadCollisionFile` and `CreateCollisionMDT` are defined in both
  decomps with different layouts (see Key facts). Linking both engines needs
  namespacing, or each world runs in its own process.
- **Texture containers.** DC1 texture entries carry `IM2` magic in the sampled
  pack. DC2's `.ipk` entries were not checked, so texture compatibility is
  unknown.
- **Developer paths in data.** DC2 model packs embed a text manifest with
  original build-tree paths. Do not copy that text into public notes, generated
  output or Ixion docs.

## Open questions

- **Face type bits.** DC2 names `0x100` as per-vertex colour, which matches the
  DCExtractor type byte `0x01` (vertex, normal, UV, colour). DC2 names `0x200` as
  "no normal", but DCExtractor's type byte `0x02` is vertex and normal. Which
  reading is right needs a byte check on a face whose type word has `0x200` set
  (`chronicletwo:ps2/include/mg_visual.hpp:25`; `refs/DCExtractor/Specifications/Models/MDS.md`).
- **DC1 collision record.** The DC1 engine reads collision as five-word triangle
  records with an info index. DCExtractor describes collision as strips with
  style `0x13` and vertex-only indices. These may describe different sections,
  but no collision block was decoded in this pass.
- **Unit scale.** DC1 floor cells are 160 world units and DC2's sampled floor
  uses 320. Town scale in each game was not checked.
- **Piece suffixes in DC2.** The meaning of `-a`, `-c`, `-h` and `-m` in DC2
  piece names is inferred from the type and collision-type fields, not confirmed.
- **`PTS` records in DC1 `scene.scn`.** Their field layout (the 20-byte name
  stride) was not fully decoded.
- **DC2 texture pack header.** The first entry of `dc2-data:map/g/g01/g01.ipk`
  was not decoded past its PAK header.
- **DCExtractor MDT header.** Its description (vertex count at +8) disagrees
  with both engine structs and the sampled bytes. Flag it upstream; do not edit
  `refs/`, which is read-only here.
