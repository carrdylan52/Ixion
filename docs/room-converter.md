# Offline DC1 room converter

`tools/room_converter.py` converts a DC1 fixed-floor room (one part, or every `DEF_PATS` part with
`--all-parts`) from its DC1 MPD archive into the frozen Ixion `ixion-room` JSON v1 pack. It does not load either game, execute donor scripts,
or change game source or data. The output is a directory containing `room.json` and PNG textures.

## Example

```powershell
python tools/room_converter.py convert `
  --pack <dc1-data>/dun/mpd_pack/d01inter.mpd `
  --cfg <dc1-data>/dun/d01inter.cfg `
  --output <private-output>/d01inter `
  --room d01inter `
  --visual d01i01_0.mds `
  --collision d01i01_a.mds `
  --spawn 0,0,0 --enemy-spawn 64,0,0 --exit 128,0,0 `
  --scale <measured-uniform-scale>
python tools/room_converter.py validate <private-output>/d01inter

# Whole room, all parts, markers from a per-room marker file
python tools/room_converter.py convert `
  --pack <dc1-data>/dun/mpd_pack/d01boss.mpd --cfg <dc1-data>/dun/d01boss.cfg `
  --output <private-output>/room-d01boss --room d01boss --all-parts `
  --markers tools/rooms/d01boss.markers.json --scale <measured-uniform-scale>
python tools/room_plot.py <private-output>/room-d01boss <private-output>/d01boss-collision.png
```

A multi-part room is still one v1 pack: visuals and collision of every part are concatenated in cfg
order and `bounds` is their union. Without `--all-parts` only the part whose `PT_BASE` is `--visual`
is converted (this keeps the R3 d01inter pack byte-identical).

## Markers

`--spawn/--enemy-spawn/--exit` are output-space coordinates and must already sit on walkable
collision (within 0.1 output units). A marker file (`tools/rooms/<room>.markers.json`) instead gives
each marker as `{"frame": name, "part": first PT_BASE name}` or `{"donor": [x, y, z]}` in donor units.
A frame marker follows DC1 `PT_MARKER` semantics: the named frame of that part's `PT_COLS` model,
placed and turned with the collision (`itemdata.cpp:1254`). Each marker is then dropped onto the
highest walkable collision surface (|normal.y| >= 0.65) at most `rise` (default 2) above and `drop`
(default 20) donor units below it, or conversion fails. The result reports straight-line support of
the spawn-enemy-exit polyline for information only; real routes need not be straight.

## Part placement and turns (DC1 semantics)

`PT_BASE "<mds>", d, x, y, z, t`: `x/y/z*10` is the frame offset, `t` (field 6) is `frame_turn`, and
`d` (field 2) is only `direction_offset`, a minimap tile index (`itemdata.cpp:979-993`,
`dungeonmap.cpp:666-668`); the converter ignores it. Fixed floors force cell direction 0
(`dungeonmap.cpp:288`), so a frame's visual turn is `frame_turn`, and a part's collision turn is
`frame_turn[0] + PT_COLS turn`, placed at frame 0's offset (`dungeonparts.cpp:2115-2132, 2341`).
Turns are normalised as DC1 does (`if (k > 3) k -= 3; if (k == 3) k = -1`, so 4 becomes 1) and
applied as `SetRotation(0, -90*k deg, 0)`: `local' = RotMatrixY(angle) * local`, translation plus the
offset (`frame.cpp:489-514`). Offsets are not rotated. A part without `PT_COLS` has no collision
model in DC1 (the fixed-floor collision loop skips it) and contributes visuals only. Only frame 0 of
an MDS is the placed CFrame, so placing a multi-root MDS is rejected. The texture image is the cfg's
`GRD_IMG` (`itemdata.cpp:621-640`).

Coordinates given with `--spawn` etc. are already in output space. The converter scales donor
geometry and collision by `--scale`, but preserves these marker coordinates. The scale is measured from
native-hierarchy mesh bounds: DC2 Max height divided by combined DC1 Toan body/accessory height.
It is an asset-space alignment estimate, not a campaign-tuned value.

## Native MDS matrix convention

MDS stores each transform as four libvu0 column vectors. The native operation is
`out[i] = m[0][i]*v[0] + m[1][i]*v[1] + m[2][i]*v[2] + m[3][i]*v[3]`; raw flat entries
12..14 are translation. DC1 `dataset.cpp` copies these sixteen floats unchanged into
`CFrame::SetTransMatrix`, `frame.cpp` copies them into the local frame, and `GetLWMatrix`
composes `parent_world * local`. The converter transposes exactly once at the MDS parse boundary
into standard row-major matrices with translation at entries 3, 7, and 11. Parent composition and
point application then use that standard representation. The test oracle independently implements
libvu0 Apply/Multiply indexing and compares retail d01inter object origins and donor vertices,
including noncommuting parent/child rotations.

Normals use the inverse-transpose of the composed linear transform and are normalized. Non-affine
or singular matrices are rejected.

## Conversion and rejection behavior

The reader follows DC1 pack entry-relative offsets, checks every member range and terminator, then
parses the config-selected MDS and MDT resources. Visual transforms follow the MDS parent graph;
face strips and lists become triangle lists with material texture indices, donor UVs, vertex normals
and diffuse colors. Collision triangles come from the separate DC1 `PT_COLS` MDS. DC1's own
`PT_BASE` translation multiplier (10) and `MDT_COLLISION` record layout are encoded in the reader.
`IM2` TIM2 PSMT8 room textures are decoded into RGBA PNGs using the texture swizzle mapping used by
the DC1 port.

Unsupported magic, multi-root placement, texture layouts, primitive types, missing material
textures, non-finite values, invalid indices, path traversal, truncated sections and configured
count limits fail conversion. The pack is staged privately and renamed into place only after the
v1 consumer schema validates. Existing output directories are never overwritten.

The supported MDS graph places parents before children. Invalid negative parents, forward edges,
cycles and sections that escape their individual MDT resource are rejected.

Per-index colours follow the port's `visualvu1.cpp`: a mesh has colours iff `colour_ofs > 0`, and
then every strip entry is `{v, n, uv, colour}`. The vertex colour becomes the GS byte
`round(value*128)` saturated at 255 and modulates by `byte/0x80`; the converter stores
`clamp01(material diffuse * that factor)` per component in the v1 vertex colour. Without colours the
v1 colour is the clamped material diffuse, as before.

The parser limits are deliberate: 64 MiB per archive, 4,096 members/objects, 2,000,000 vertices or
triangles, 1,024 images/materials and 16,777,216 pixels per texture. The intended consumer is a
triangle-list loader. Published packs additionally require at most 128 textures, 100,000 visual
groups, 2,000,000 expanded visual vertices and 1,000,000 collision triangles, positive bounds,
contained markers/geometry and nondegenerate collision. The native consumer validates independently
before creating runtime resources.

A separate compatibility receipt can record a stable namespaced content ID, producer commit,
conversion options, supported subset, required consumer capabilities and hashes of every output.
This preserves the v1 JSON shape. The receipt is provenance evidence; this tool does not implement
installation discovery, cached-source policy or launcher capability gating. Static room conversion
does not preserve donor events, navigation, collision-area semantics or progression.

## Validation

The unit tests include malformed pack/MDS inputs, native matrix-oracle checks, normal transforms,
schema/material/path checks, and a real local donor-data qualification. Set `IXION_DC1_DATA` to the extracted DC1 data
root and `IXION_ROOM_PACK` to the converter output directory to run the retail-room checks. The
real-data test verifies member identity, room placement parsing, visual/collision geometry counts,
texture names and consumer triangle shape. `IXION_DC2_DATA` additionally enables actual Toan/Max
model height comparison, which is the basis for choosing a donor-to-consumer room scale.

## Arena sidecar (`arena.json`)

`room_converter.py arena --room-pack <pack> --pack <room>.mpd --cfg <room>.cfg` writes `arena.json`
and `arena/fire/*.png` beside an existing v1 pack (room.json stays byte-identical). It carries the cfg
records the v1 converter drops, all in output units:

- `field_tiles`: the twelve `CDranMapField` slots (`DRANS_PARTS` i + `DRANS_COLS` i, in file order).
  Each tile has its MDS objects with object-local triangle groups (`texture` indexes room.json
  `textures`), a rest transform, and the collapse motion baked per whole motion frame
  (`track.t`, `track.q` as (w,x,y,z) with the standard R*v matrix, `track.alpha` per MDT material,
  1 = opaque), plus its collision (every triangle has `ground_kind` = slot + 1). `rule` is the DC1
  state machine: 3 intact, a projectile map hit on ground_kind k decrements slot k-1 while >= 2,
  2 plays the field sound and becomes 1, 1 has no collision and plays the motion until time >= 59,
  0 is gone (dranmapfield.cpp, shot_utils.cpp).
- `fires`: every `PT_FIRE` placed as DrawFireFreeStyle places it, the decoded `FIRE_IMG` textures,
  a baked (approximate) flame flipbook and the CFireOmni draw parameters.
- `camera_collision`: each `PT_CAM` model placed and turned like its part (autoCamTrial geometry).
- `markers`: every `PT_MARKER` with radius, script, item-use, auto-start, switch and ext-memory
  flags, the trigger window, and its position from the part's collision frame.
- `floor_support`: the straight spawn->enemy->exit support count without and with intact tiles.

`validate_arena` checks the sidecar against the room.json it names by sha256.


## Random floors (`floor` mode)

DC1's random dungeon floors are one 20x20 grid of kit parts (`CDungeonMap::cells`), not a fixed room.
The grid is not derivable from the cfg: it is the output of `CDungeonMap::buildRandomMap(6, 1)`, a
function of one map seed (`map_seed = rand() / 100000`, 0..21474, `ps2/src/dungeonmap.cpp:3454-3458`).
The port's `randfloor_dump` tool (Chronicle branch `randfloor-dump-20261014`,
`port/src/tests/randfloor_dump.cpp`, `cmake --build ... --target randfloor_dump`) runs the real
generator for a seed and writes `ixion-dc1-randfloor` v1 JSON:

```
randfloor_dump <map_seed> <floor> <out.json> [dungeon]
```

The tool finds the `srand()` argument whose first `rand()` gives the seed (the port's rand is an LCG,
`port/src/runtime.cpp:35-41`), calls the same functions the game does (`gameloop.cpp:6382-6386`,
`buildRandomMap` then `buildEventData`) and runs the whole generation twice in one process; the two
dumps must be byte-identical. The back floor is not dumped: it is built from an RNG state that
`buildEventData` has advanced and is not a function of the seed alone.

Round 2 adds the monsters. Floor script program 100 runs `_SET_RANDOM_MAP` then `_LOAD_MONSTOR`, whose
`ArrangementPos(&MainDungeonMap, 15, -1, 0)` places 15 monsters (`btsysscript.cpp:638-641`,
`gameloop.cpp:6487-6490`). The dump tool runs the rest of `BtCleatRandomMap` for real (the back floor's
`buildRandomMap(6, 0)` and `buildEventData`, the only RNG users in between) so the RNG stream reaches
`ArrangementPos` in the game's state, then runs a line-for-line copy of `ArrangementPos` and `SetKey` over
the real map (`SearchiDoPutArea`, `CheckTreasureBox`, `CheckAtra`, `CheckTrapCircle`). It needs each
model's program 1 verified for RNG use and position changes; only dungeon 0's models are (the Cave Bat lifts
21 units), anything else is refused. The dump gains `monsters` (slot, monster_no, model id, x/y/z) and `gate_key`
(the one monster that holds the key, `CMonstorUnit::SetKey`).

Dump fields: `map_seed`, `srand_argument`, `floor` (1-based; `cur_floor = floor - 1`), `grid`, `rooms`,
`gate_key_no`, `stair_down` / `stair_up` / `ura_entrance` (`col`, `row`, `direction`), `chests`
(world x/y/z, `item_no`, `kind`, `trap_no`), `atla`, `trap_circles`, and four row-major 400-entry
arrays: `parts_no` (MapPartsNo = DEF_PATS index, -1 = none), `direction` (0..3), `content`
(`BuildCellFlag` bits, `dungeonmap.cpp:38-49`) and `room_links` (bit per room).

```powershell
python tools/room_converter.py floor `
  --pack <dc1-data>/dun/mpd_pack/d01main_a.mpd --cfg <dc1-data>/dun/d01main_a.cfg `
  --dump <seed.json> --output <private-output>/randfloor-<seed> --scale 1.5584790682688
python tools/room_converter.py floor-ascii <seed.json>
```

Placement follows the game: cell (col, row) is at (160*col, 0, 160*row). A part's frames are drawn
at that position plus the frame offset, turned by `dc1_turn(direction + frame_turn)`
(`CDungeonParts::Draw`, `dungeonparts.cpp:2245-2275`); its `PT_COLS` model is placed at the cell
position with no offset, turned by `dc1_turn(direction + PT_COLS turn)` (`dungeonparts.cpp:2156-2175`,
`2324-2338`). Only the 16x16 playable area is placed; column 19 holds the back floor's road
(`SetUnderLoad`, `dungeonmap.cpp:3049-3054`) and is skipped unless `--include-under-road`.

Markers: `spawn` is the stair-in cell (`MAP_PARTS_STAIR_DOWN`, "stair that the player comes in by"), `exit` the
stair-out cell. A stair part has a gate wall a few units from its cell centre (so the centre is a sealed
pocket), so both markers are put 40 donor units from the centre toward the next cell on the grid
path. `enemy_spawn` is a bare room cell on that path. Heights are the walkable surface nearest
y=0 (kit parts also carry roof collision 45-65 units up that `ground_heights` cannot tell from
floor). Output is a pack directory with `room.json` (v1, unchanged), textures and a sidecar
`floor.json` (`ixion-randfloor-meta`: cell centres in output units, stair / back-floor-entrance cells,
path, free room cells and corridor cells as chest and monster candidates, the dump's real chests,
atla and trap circles with output positions, DC1's monster arrangement, the gate key rule as data, and the walk
check). Consumers that only read v1 ignore it.

`props.json` (format `ixion-room-props` v1, the DC2 adapter's props format) is written beside it: the dump's
chests as `treasure_box` props at their cells with the DC2 item (`contents.dc2_item`, `mapping` says equivalent or
stand-in; the table is `CHEST_ITEMS`, anything unlisted falls back to Bread and says so), DC1's monsters as
`monster_spawn` props (nearest the entrance first, because DC2's floor has few free monster slots), and
`native_boxes: park` (a floor spans the DC2 floor, so native treasure boxes always lie inside it). The gate key
is carried as data only: `floor.json` `gate_key.holder` is the arranged monster that holds it in DC1;
runtime use waits for a decision between DC1's rule and DC2's drop-on-any-death.

Self-check: the grid path from entrance to exit is found over the generator's own build flags, then
walked every 4 donor units following the ground (rise 6, drop 12 per step); `walk.void` must be 0.
`walk.wall_crossings` counts steep collision triangles crossed by the walked track at 8 and 24 units
above the ground and must be 0. Both are reported in the converter's output and in `floor.json`.
`room.json` rounds attributes (positions to 4 places, normals and UVs to 5, colours to 4) because
every kit mesh repeats once per cell; a 99-cell floor is about 15 MB. The pack must stay under the
consumer's 64 MiB JSON limit and inside DC2's 14x14x320 native grid (about 4,480 units).
