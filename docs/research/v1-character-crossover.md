# Playing a character from the other game: model, motion and control feasibility

## What this covers

How far each port is from drawing and controlling the other game's player character, for the v1 goal "be any character from either game". It covers the player model and skeleton files, the textures and palettes they use, the motion files and the locomotion code that picks them, the size and collision parameters, the menu models, and four options ranked by cost: (a) load the other game's model directly, (b) convert offline, (c) keep the native logic and swap the mesh or textures, (d) portrait-only passengers.

The brief's examples are reversed against the data. Max and Monica are Dark Chronicle (DC2) characters, and Toan is a Dark Cloud (DC1) character. This document treats both directions: a DC2 character in DC1 (Max in Norune) and a DC1 character in DC2 (Toan in a DC2 town).

Evidence:
- Decomp source: `chronicle:` (DC1) and `chronicletwo:` (DC2), read as checked out at the commits the existing notes name.
- Community specs under `refs/DCExtractor/Specifications/` (PAK, IMG, TM2, MDS, MOT, WGT).
- Extracted game data, cited as `dc1-data:<pack>/<entry>` and `dc2-data:<pack>/<entry>`. These are paths relative to each game's extracted data root. The data itself is not published.
- Byte-level walks of pack headers, MDS bone records, MDT blocks, MOT and WGT channel headers, IM2 and TIM2 headers, and PNG headers. These are read-only, and the counts are stated where used.

Existing notes read first: `c1-characters`, `c2-characters`, `engine-lineage-models`. Where this note corrects or extends them, the text says so. Inference is labelled as inference.

## Key facts

- **Identities.** Max's DC2 `info.cfg` NAME is the Japanese "Mints" family (`dc2-data:mainchr/c01_base.chr`, info.cfg NAME). Monica's is モニカ (`dc2-data:mainchr/c02_base.chr`). Toan's pack is `c01d.chr` in slot 0 of the DC1 pack table (`chronicle:ps2/src/btitem.cpp:56`, `charaNameTbl`). The DC2 notes found no Toan identifiers in DC2 source or data (`c2-characters`).
- **Base skeleton sizes.** Toan (`dc1-data:dun/mainchara/c01d.chr`, `c01d.mds`): 77 bones, 17 mesh-owning bones, 1,509 mesh vertices in total. Max base (`dc2-data:mainchr/c01_base.chr`, `c01b.mds`): 124 bones, 15 owners, 45 vertices in total. Monica base (`dc2-data:mainchr/c02_base.chr`, `c02a.mds`): 154 bones, 16 owners, 57 vertices. Bone count is read from the MDS header at +8 (`chronicle:ps2/include/mds.hpp:20`, `chronicletwo:ps2/include/mg_dataset.hpp:64`). Bone and owner counts were re-checked against the packs; the vertex totals were not (unverified).
- **Max's visible body is in costume packs (new).** Every DC2 base-pack mesh block has `vertex_num` = 3 (`MDT` header at +12, `chronicletwo:ps2/include/mg_visual.hpp:50`) (unverified). Max's costume pack `dc2-data:mainchr/c01fuku1.chr` (`c01f.mds`) has 123 bones, 14 owners and 1,652 vertices. The alternate pack `dc2-data:mainchr/c01d.chr` (`c01d.mds`, NAME ミンツ) has 79 bones and 1,536 vertices. The base pack is therefore a skeleton, motion and placeholder set, and the visible geometry comes from skin packs. The loader notes say clothing loads as a skin (`chronicletwo:ps2/src/charasetup.cpp:143-227`). The mechanism is inference until a load test runs.
- **Bone names do not transfer (new).** Toan's 17 mesh-owner names and Max's costume 14 mesh-owner names share only `kao` and `kaban`. Of Max's costume owners, 12 are absent from Toan's skeleton (`atoramiria--m1-`, `himo`, `kami`, `R_asi`, `L_asi`, `dora`, `ton`, `supana`, `skin1`, `skin2`, `R_te`, `L_te`). Byte walk of the two MDS files.
- **Bone contract.** Toan's base MDS has `weapon` and `item` and `jnt2_1`. It has no `dcol0` or `dcol1`, only `dcol`. Max's base MDS has `ef00`, `gun_hand`, `hat`, `item`, `hip`, `kao`, `skin1`, `R_te`, `L_te`, and no `weapon`. Monica's has `sword_hand`, `wr`, `ac`, `atoramiria`. The weapon attach lookups are `CharaMain.frame->SearchFrame("weapon")` (`chronicle:ps2/src/dun/gameloop.cpp:6561`, `:6578`, `:6701`). The `:6561` path (in `EquipReAttach`, which starts at `:6555`) calls `SetReference(hand)` with no NULL test. `EquipWeaponFrame` (`:6578`) does test it.
- **MDS container is compatible at header level.** Both games: 16-byte header with the object count at +8. Object records are 112 bytes, with the name at +8 (32 bytes), the data offset at +40, the parent at +44 and the matrix at +48 (`chronicle:ps2/include/mds.hpp:20-37`, `chronicletwo:ps2/include/mg_dataset.hpp:64-88`). Parsing DC2 `c01b.mds` with the DC1 record layout gives the same 124 records and 15 owners.
- **MDT header and materials.** The `MDT\0` magic and a 64-byte header are present in both games. `vertex_num` is at +12 and the material table offset is at +56 in both (`chronicle:ps2/include/mdt.hpp:10-22`, `chronicletwo:ps2/include/mg_visual.hpp:50-67`). Materials are 0x60 bytes with the texture name at +0x34 in both. The DC1 name field is 44 bytes (`chronicle:ps2/include/mdt.hpp:27-33`). The DC2 name field is 32 bytes, followed by `unk_54` and two floats (`chronicletwo:ps2/include/mg_visual.hpp:77-85`).
- **Toan's texture names.** Toan's dungeon mesh materials use `c01d01` through `c01d05`. Max's base mesh materials use `c01b01` only, on all 15 owners (byte walk). The DC1 names match the IM2 subheader names exactly (`dc1-data:dun/mainchara/c01d.chr`, `c01d01_dun.img`).
- **Toan's textures are 8-bit indexed (new).** `c01d01_dun.img` has the `IMG\0` magic and 7 TIM2 entries: `c01d01` at 128×128, `c01d02` to `c01d05` at 256×256, `c01d11` (the eye-blink strip, 128×192) and `c01d01dan` at 128×128. Each has a 256-entry, 1,024-byte palette and 1 byte per pixel (`imgBytes` = width × height) (entry list and sizes unverified). The field pack `dc1-data:chara/c01d.chr` has the same textures as an `IM2\0` archive, six entries. The eye animation is driven by `TEX_ANIME` lines in `base.cfg`. The TIM2 header byte at picture offset +35 reads 5 for these textures, which does not match the spec's naming. The 8-bit reading is inferred from the sizes.
- **Max's texture payloads are empty in the pack.** Every `c01b.img` entry in the DC2 mainchr packs that carry one (`c01c.chr`, `c01d.chr`, `c01fuku1.chr`) is zero-length. The `c01_base.chr` pack has no image entry at all. The real textures are in the DC2 port catalog (`port_data/catalog.json`, which sits beside the `data/` root rather than inside it). Its entries are PNG variants keyed by pack and archive, for example `chara/dmmy.chr/c01b.img/c01b01-entry-1-picture-0-variant-self-mip-0.png`. The same archive appears under `mainchr/c01d.chr/c01b.img/` and `mainchr/c01fuku1.chr/c01b.img/`. Variant names seen: `self` (c01b01 to c01b04), `c01ban` (c01b01 and c01ban) and `time_mints_an` (c01b01).
- **DC2 PNG format.** The one loose catalog texture (`dc2-data:port_data/img/c01b01_4.tm2.img/`, file `c01b01_4-entry-0-picture-0-variant-self-mip-0.png`) is a 128×128, 8-bit RGBA PNG (colour type 6). The directory name is the source archive entry, `c01b01_4`.
- **DC2 texture resolution.** `ResolveFile` returns an opaque 16-byte handle for a catalog key, and the game never receives TIM2 bytes (`chronicletwo:port/src/dataread.cpp:205-225`). `EnterIMGFile` pulls the catalog entries for the archive, including `cfg` animation entries (`chronicletwo:port/src/mg_texture.cpp:1086-1112`).
- **DC1 texture decoder accepts direct colour (new).** `PortDecodeTexture` treats TIM2 bpp codes 0 and 1 as indexed (4-bit and 8-bit) and codes 2 to 4 as direct RGBA8 (`chronicle:port/src/texture_port.cpp:281-310`). Not tested on a converted file. The mapping from the TIM2 header byte to the decoder's `bpp` argument was not traced.
- **Toan's motion rows.** `base.cfg` in `dc1-data:dun/mainchara/c01d.chr` has one motion set (`MOTION 0`) and 41 `KEY` rows (real motion numbers 0 to 40; the first `KEY` line is `KEY_START`). Row 0 is 立ち (stand). Row 1 is 走り (run; frames 70 to 90, speed 0.65). Row 2 is 歩き (walk; frames 35 to 55, speed 0.5). Row 23 (0x17) is やられ (defeated; frames 460 to 480). That is the row the code uses when HP is 0 (`chronicle:ps2/src/dun/gameloop.cpp:3170`). The mapping of row numbers to motion numbers is confirmed by the call sites below, not by the comments alone.
- **DC1 locomotion is a three-number contract.** `keyCtrl(stick_x, stick_y, motion)` returns 0 when the stick is still, 1 for run when |x| + |y| ≥ 0.85, and 2 for walk otherwise. It also writes the speed into `motion[2]`, so row 2 must exist (`chronicle:ps2/src/clothread.cpp:537-566`). The caller is `BtActStatus.motion_no = keyCtrl(...)` (`chronicle:ps2/src/dun/gameloop.cpp:3167`). The port replaces the whole dungeon move function, `DunMoveChara`, and keeps the same call at `chronicle:port/src/dun/movechara.cpp:412`.
- **DC2 Max's motion keys are named.** `info.cfg` has 46 `KEY` rows, each with a quoted name (`dc2-data:mainchr/c01_base.chr`, info.cfg). The three locomotion keys are 立ち (frames 362 to 364, speed 0.02), 歩き (11 to 31, 0.50) and 走り (35 to 55, 1.00).
- **DC2 locomotion picks by name.** `CActionChara::HumanMoveIF` calls `SetMotion` with 走り when the stick magnitude is ≥ 0.65, otherwise 歩き with `SetStep` (`chronicletwo:ps2/src/actionchara.cpp:1708-1722`). Stand is 立ち, or バトル立ち in battle stance (`:1656-1658`, `:1724-1726`). A missing name is silent. `SetMotionPara` does nothing when the name is not found, and only falls back to sequence names (`chronicletwo:ps2/src/character.cpp:792-817`).
- **Base motion files carry no vertex channels (new).** Walking the channel headers: `c01b.mot` (Max) has 76 channels, all rotation (type 0, 67) or translation (type 2, 9). `c01d.mot` (Toan, dungeon) has 41 channels, types 0 (36) and 2 (5). Neither has a type 12 vertex channel (unverified: the channel walk was not re-run). Walk stops at end of file, so every byte is accounted for.
- **Base skin is nearly empty (new).** `c01b.wgt` has 475 bone headers, and the header layout matches the community spec (`refs/DCExtractor/Specifications/Models/WGT.md`, `weightCount` at +16). The weight records total 15 across all headers (unverified). The skin weights for the visible body must be in the costume packs.
- **Body size fields.** Toan's `BODY_SIZE 17,7,60` is read as three floats (`chronicle:ps2/src/chararead.cpp:459-463`). Max's `BODY_SIZE 16.00, 4.00, 0.00` and Monica's `16.00, 4.00, 50.00` are read by `_BODY_SIZE` with `spiGetStackInt` (`chronicletwo:ps2/src/character.cpp:1795-1804`), so the decimals are truncated to integers (inference from the call, not run).
- **Who reads body size.** DC1: camera framing (`chronicle:ps2/src/editloop3.cpp:6156`), monster targeting (`chronicle:ps2/src/dun/gameloop.cpp:9191`) and NPC distance, which uses width (`chronicle:ps2/src/editloop3.cpp:9166`). DC2: target box and HUD (`chronicletwo:ps2/src/dng_hud.cpp:175`), damage number placement (`chronicletwo:ps2/src/dng_main.cpp:3097-3100`) and the body-versus-attacker height test (`chronicletwo:ps2/src/actionchara.cpp:1417-1422`).
- **DC1 player collision is fixed, not size-driven.** The dungeon move function queries the collision with a box of ±20 on X and Z and from −40 to +20 on Y around the position (`chronicle:port/src/dun/movechara.cpp:1279-1284`, and again at `:1383-1388`). `BODY_SIZE` does not feed this query.
- **DC2 hit volumes are data.** `OBJECT_NAME2` binds spheres to named bones with radii. Max's `OBJECT_NAME2 2, "bcol00", 4.00, "bcol01", 4.00` sets the body group (`chronicletwo:ps2/src/character.cpp:2235`, `chronicletwo:ps2/include/character.hpp:244`, `CHARA_ENTRY_GROUP_BODY`).
- **Menu models are 3D in both games (new).** DC1 has `dc1-data:commenu/dungeon/c01model.pak`, with `c01d.mds` (149,696 bytes), `c01dmenu.img` (`IMG\0`) and `c01dstat.mot` (15,552 bytes, a single pose). The name is built as `c0%dmodel.pak` (`chronicle:ps2/src/menu_misc.cpp:1031-1041`). DC2 has `dc2-data:menu/chara4/c01b_menu.chr`, with `c01_menu.mds` (19,664 bytes, the same size as `c01b.mds`), `c01_menu.mot` (15,104 bytes) and `.bbp` and `.wgt`. Neither menu is a flat image. Both are a full model with one pose motion.
- **Correction to the DC1 notes (new).** `d0%do.img` (`chronicle:ps2/src/menu_misc.cpp:1416`) is keyed by Georama, `cur_georama + 1`. It is a backdrop for the escape or dialogue screen, not a character portrait.
- **Hop v0 data roots.** Each game is started with its own data root (`ixion:docs/HOP-V0.md:118-119`, unverified: `HOP-V0.md` is not in the checked Ixion tree). A DC1 process cannot read a DC2 file from its own data tree without a copy or a host service.
- **Design constraints.** The first crossing is Max playing Toan through one cave floor with one weapon (`ixion:docs/DESIGN.md:22-24`). The loaner mechanism says no model crosses (`ixion:docs/DESIGN.md:199-201`). Phase 1 is passengers and portraits only (`ixion:docs/DESIGN.md:319-320`). Phase 4 is model crossover, including Toan in the Ridepod (`ixion:docs/DESIGN.md:335`, row 16 at `:302`).

## How it works

### Pack anatomy

Each game ships a character as a PAK-family archive (`refs/DCExtractor/Specifications/Pack/PAK.md`): an 80-byte header per entry (64-byte name, header size, file length, end offset, type), with the next entry at `endOffset`. The packs differ in what they hold.

- **Toan, field** (`dc1-data:chara/c01d.chr`): `info.cfg` (1,689 bytes), `c01d.mds`, `c01d01.img` (IM2), `c01dbas.bbp/.mot/.wgt` and `c01sbas.*`, plus cloth files. The field copy is named `info.cfg` rather than `base.cfg`; which loader reads it was not traced.
- **Toan, dungeon** (`dc1-data:dun/mainchara/c01d.chr`): `base.cfg`, `c01d.mds`, `c01d01_dun.img` (IMG, 7 entries), `c01d.bbp/.mot/.wgt`, `c01s.*` and cloth. Its motion set is a different file from the field set, so one body has two motion tables.
- **Max, base** (`dc2-data:mainchr/c01_base.chr`): `info.cfg` (v2 dialect, 4,188 bytes), `c01b.mds`, `c01b.bbp/.mot/.wgt`, `c01s.*` and `c01_atora.clo`. No image entry.
- **Max, costume and alternates** (`dc2-data:mainchr/c01fuku1.chr`, `c01d.chr`, `c01c.chr`): each has its own `.mds` with the visible geometry. `c01fuku1` (123 bones) and `c01d` (79 bones) have different skeletons from the base.
- **Monica, base** (`dc2-data:mainchr/c02_base.chr`): `c02a.mds` with 154 bones, and `c02s.mds` as the shadow.

### Models and skeletons

DC1: `ReadInfo` (`chronicle:ps2/src/chararead.cpp:135`) runs `CommandMODEL`, which calls `LoadMDSFile` (`chronicle:ps2/src/dataset.cpp:348`). Each bone becomes a `CFrameVu1`, and bones with a non-zero `associatedMDTOffset` get a visual. Attachment in the shared DC1 code is by bone name: the equipped weapon attaches to `weapon`, the held item to `item`, and Osmond's look frame is `jnt2_1` (`chronicle:ps2/src/dun/gameloop.cpp:5868`).

DC2: `_MODEL` (`chronicletwo:ps2/src/character.cpp:2007`) calls `mgLoadMDSFile` (`chronicletwo:ps2/src/mg_dataset.cpp:633`), and `CreateFrameVisual` (`chronicletwo:ps2/src/mg_dataset.cpp:480`) builds one visual per object. `SetupMainUnit` (`chronicletwo:ps2/src/charasetup.cpp:140`) builds the playable unit from slots. For Max it loads the base body, then the clothing as a skin, then the melee weapon at `ef00`, the gun at `gun_hand`, the hat at `hat`, and the action script `mainchr/c01.stb` (`charasetup.cpp:219`). For Monica it loads `mainchr/c02.stb` (`charasetup.cpp:289`).

Mesh-to-bone binding: a mesh is owned by a bone (its `associatedMDTOffset`), and skin channels in the `.wgt` address the owner by bone index and the driver by bone index. A new mesh therefore needs its owner bones to exist in the target skeleton, under the same index semantics. Toan's skeleton shares two owner names with Max's costume, so this binding does not transfer by name.

### Textures and palettes

- **Toan:** TIM2 8-bit indexed textures, 256 entries, RGBA32 palette per texture. `CommandIMG` registers the character's own IMG archive as texture block 0 (`chronicle:ps2/src/chararead.cpp:489`), and the material texture names are matched against the archive's subheader names (the match code was not traced; the names agree byte for byte). The eye strip `c01d11` is animated through `TEX_ANIME_DATA` rows that step a 48-pixel offset in the same texture (`dc1-data:dun/mainchara/c01d.chr`, `base.cfg`).
- **Max:** the texture is a 128×128 RGBA8 PNG in the catalog. There is no palette. The catalog variants (`self`, `c01ban`, `time_mints_an`) are alternate versions of the same archive entry, selected by the material or the costume (inference from the names).
- **Porting a DC2 texture into DC1:** a direct-colour TIM2 avoids palette quantisation, because the DC1 decoder accepts direct colour (`chronicle:port/src/texture_port.cpp:290-292`). The reverse direction (a DC1 palette into an RGBA8 PNG) loses nothing, since each palette entry is already RGBA32 (inference from the 1,024-byte palette sizes).
- **UV layout:** the UVs in each `MDT` are tied to a texture atlas. Max's UVs will not index Toan's atlas, so a texture-only swap onto Toan's mesh is unlikely to look right. This is the main blocker for option (c) texture-only.

### Motions and locomotion control

Both games play motions from three files per set: `.bbp` (bind matrices), `.mot` (rotation, scale, translation and visibility channels) and `.wgt` (skin channels). The shared record layout is in `refs/DCExtractor/Specifications/Models/MOT.md` and the decomp's `Mot_File_List`.

DC1 selects a motion by number. Row numbers are the motion numbers. The walk, run and stand numbers come from `keyCtrl`: 0 stand, 1 run, 2 walk. The shared code also uses 0x12 (`BtActStatus.motion_no = 0x12`, `chronicle:ps2/src/dun/gameloop.cpp:3273`), 0x17 (defeated, `:3170`) and 0x1D (recoil for Toan only, `:3175`). The numbers are a convention across the six members, not a schema. Each member's `base.cfg` must supply rows for every number the shared code uses, and the call sites were not checked for bounds.

DC2 selects a motion by name. The names are literals in the human move code, and they resolve through the `KEY` rows of the character's `info.cfg`. A character with a 立ち, 歩き and 走り row therefore gets walking and running through the existing code, with no change to `actionchara.cpp`. The rest of the behaviour lives in the per-character binary script (`mainchr/c01.stb`, an SB2 program, not decoded here), which is bound per character in `SetupMainUnit`.

Sample mapping, for a DC2 body in DC1 (Max into Toan's controls): DC1 row 0 ← 立ち (362–364, 0.02); DC1 row 1 ← 走り (35–55, 1.00); DC1 row 2 ← 歩き (11–31, 0.50). For a DC1 body in DC2 (Toan into DC2's controls): 立ち ← row 0 (frames 10–20, speed 0.2); 走り ← row 1 (70–90, 0.65); 歩き ← row 2 (35–55, 0.5). The frame ranges are the source's own. Frame counts differ by skeleton and are not verified to play at the same speed.

### Size and collision

The DC1 body is three floats (height, width, depth) read by `CommandBODY_SIZE`. Height is the camera and target anchor. Width is only used for NPC distance. The player's movement collision is the fixed box in the move function, independent of `BODY_SIZE`. A different body size therefore changes camera and targeting, not walls.

The DC2 body is three integers (the `_BODY_SIZE` parse). `body_height` is used for targeting, damage number placement and the vertical test against attackers. The DC2 world-collision path for the player was not traced in this brief. Its body-vs-body volumes are spheres from `OBJECT_NAME2`, so a DC1 body entering DC2 needs its hit spheres named in `info.cfg` or they are absent.

### Menu models and portraits

Both games show the character in the status and equipment screens with a full model and one pose motion. DC1 loads `c0%dmodel.pak` for the menu (`chronicle:ps2/src/menu_misc.cpp:1031-1041`). Its pose is `c01dstat.mot`, 15,552 bytes. DC2 uses `menu/chara4/c01b_menu.chr`, with `c01_menu.mot`, 15,104 bytes. The two pose files are the same size class, so a menu model is the cheapest 3D body that does not run the dungeon logic.

A portrait in the Ixion sense (a still image) is not native in either game for the playable character, as far as this brief traced. The DC2 NPC portraits are `menu/npc/t<model>.chr`, which are also models (`chronicletwo:ps2/src/npccfg.cpp:152-192`). The DC1 `d0%do.img` files are backdrops (see Key facts).

### Options ranked

Ranking is by cost and by how many blockers the option has in code and data. Every blocker below is from the code or the data above unless marked as inference.

1. **(d) Portrait-only passenger.** Cheapest, and matches Phase 1. The host draws a still in the Ixion Board window from a catalog PNG (for example the `c01b01` self variant, 128×128 RGBA8). Blockers: no face-specific PNG has been identified. The catalog keys do not say which variant is the face. Under Hop v0 the DC2 data root is passed to the DC2 module only (`ixion:docs/HOP-V0.md:118-119`, unverified), so the host needs its own copy of the entry or a new argument. Cheapest experiment: export one catalog PNG for Max, look at it, and draw it in a host window with no game code. Kill condition: no PNG in the catalog reads as a face.
2. **(c) Texture-only swap.** Replace one IMG entry's payload in a copy of Toan's dungeon archive with a direct-colour TIM2 of Max's `c01b01` and keep the subheader name. Blockers: UVs are Toan's. Toan's `c01d02` is 256×256 and `c01d01` is 128×128, and the atlas layout of `c01b01` is unknown. Cheapest experiment: one TIM2 written under the name `c01d02`, one run of the dungeon with the copy, one screenshot. Kill condition: the face and body look mapped to the wrong regions.
3. **(c) Mesh swap onto the native skeleton.** Dead as a rename. Only 2 of 17 Toan owner names are in Max's costume, and 12 of Max's 14 costume owners are not in Toan's skeleton. A swap needs a re-skin. Cheapest experiment, already run: the name-overlap walk above. Kill condition met.
4. **(b) Offline converter.** Possible in principle, and the most work. Blockers: skeleton retarget (Max's root is probably `hip`, the object at `OBJECT_NAME2` id 0, which Toan's skeleton does not have; this is inference, and Toan's root was not confirmed); owner-to-owner mesh mapping (above); weight transfer, since the references document only reading and writing existing WGT weights (the Blender tool is DC1-only), so new weights would need a new step; motion retarget (46 DC2 keys onto DC1's 41 rows, with the three locomotion rows first); textures (PNG to direct-colour TIM2, feasible). Minimal experiment: retarget only the three locomotion motions (立ち, 歩き, 走り) from Max's `c01b.mot` onto Toan's skeleton by bone name, plus the root map. Kill condition: root or owner mapping fails, or the retargeted walk has more than a few bones with no source channel.
5. **(a) Load the other game's model directly.** The container matches, so the parse succeeds. Blockers, in order of how early they fail: (1) the DC1 weapon-hand lookup calls `SetReference` with no NULL test at `chronicle:ps2/src/dun/gameloop.cpp:6561-6566`, and Max's base has no `weapon` bone; (2) DC1's `KEY` parser expects numeric rows in `base.cfg` (`chronicle:ps2/src/chararead.cpp:399`), while Max's rows are named, so the three locomotion rows would have to be re-emitted at numbers 0, 1 and 2 (not done); (3) the DC2 `info.cfg` dialect is not read by DC1's `ReadInfo`; (4) DC2 textures are PNG-only in the catalog, and DC1's loader reads TIM2 from an IM2 or IMG archive; (5) under Hop v0 each game has its own data root. Cheapest experiment: one call to `LoadMDSFile` (`chronicle:ps2/src/dataset.cpp:348`) on a copy of `c01f.mds` under DC1's data root, with a log of the owner names and the first failing `SearchFrame`. Kill condition: the first NULL `weapon` lookup, or a bone-count mismatch at the first motion. This experiment needs a build, which this brief did not run.

## Proposed Ixion code

None of the signatures below exist yet. The names are proposals for the next session. Each one lists the exact globals and functions it touches and where it must be called.

### 1. Host-side still for a passenger (option d)

```c
/* Host side, in the Ixion Board window. Returns the RGBA8 still for a catalog key, or 0. */
int IxionPassengerStill(const char *catalog_key, int *width, int *height, uint8_t **rgba);
```

- Reads the DC2 catalog entry (`texture_catalog::Find`, `chronicletwo:port/src/dataread.cpp:209`) and decodes the PNG. It is not a module call, so no ABI change is needed. Hop v0 passes each data root in the module's own arguments (`ixion:docs/HOP-V0.md:118-119`, unverified), so the host needs either its own copy of the catalog entry or a new startup argument (proposal, not decided).
- Keys to try first: `chara/dmmy.chr/c01b.img/c01b01-entry-1-picture-0-variant-self-mip-0.png` and the `c01ban` variant. The face variant is not known.

### 2. Locomotion row contract for a DC1 body (options a, b, c)

```c
/* DC1 side. Call from LoadChara2 (chronicle:ps2/src/dun/gameloop.cpp:6871) after its base.cfg LoadPackData2 call (about :6901), which reaches ReadInfo through chronicle:ps2/src/character.cpp:1023-1028. */
bool IxionDc1CheckLocoRows(const MOTION_INFO *rows, int row_count);
```

- Requires `row_count >= 3`, and rows 0 (stand), 1 (run) and 2 (walk) non-empty (`start < end`; the `MOTION_INFO` fields are `start` and `end`, `chronicle:ps2/include/gameutil.hpp:175`). It returns false otherwise, and the caller refuses the body rather than letting `keyCtrl` write `motion[2].speed` into a missing row.
- Touches `CharaMain.motion_type.motion_info` (`chronicle:ps2/src/dun/gameloop.cpp:3167`, `:6871`).

### 3. Name contract for a DC2 body (options a, b, and Toan in DC2)

```c
/* DC2 side. Call from SetupMainUnit after the info.cfg LoadPack and LoadSkin calls (chronicletwo:ps2/src/charasetup.cpp:171-215). Not from _MOTION (chronicletwo:ps2/src/character.cpp:2305), which runs per MOTION command during that parse. */
bool IxionDc2CheckLocoKeys(CCharacter2 *chr);
```

- Tests `GetKeyListPtr` for 立ち, 歩き and 走り (the names used at `chronicletwo:ps2/src/actionchara.cpp:1656`, `:1717`, `:1719`). A failed lookup is silent in `SetMotionPara` (`chronicletwo:ps2/src/character.cpp:792`), so this check is the only place the failure is visible.

### 4. Motion key map table (both directions)

```c
struct IxionKeyMap { int dc1_row; const char *dc2_name; };
static const IxionKeyMap kLocoMap[3] = {
    {0, "立ち"},   /* stand */
    {1, "走り"},   /* run   */
    {2, "歩き"},   /* walk  */
};
```

- Used by the offline converter (option b) and by any runtime bridge. The reverse map is the same table read backwards. Values are verified against both `info.cfg` and `base.cfg` above.

### 5. Weapon-hand guard in DC1 (option a only)

```c
/* In EquipReAttach (chronicle:ps2/src/dun/gameloop.cpp:6555-6566; the weapon lookup is at :6561). */
CFrame *hand = CharaMain.frame->SearchFrame("weapon");
if (hand == NULL) {
    hand = CharaMain.frame;  /* Ixion guard: attach to the root when the rig has no weapon bone */
}
```

- Touches `CharaMain.frame`, `hand` and `equipment->frame->SetReference`. This is a proposal for a foreign rig. It changes native behaviour only when the bone is missing. Toan's DC1 rig has `weapon`; the other five DC1 members were not checked (unverified).

### 6. Roster identity across games

```c
/* ABI-adjacent. IxionReceipt.character is per game today (ixion:include/ixion_api.h:44-57, unverified). */
int IxionRosterId(uint32_t game_id, int native_id);
```

- DC1 `UserStatus->cur_chara` is 0 to 5 (`chronicle:ps2/include/userstatus.hpp:86`, and `c1-characters`). DC2 `active_chr_no` is set through `CUserDataManager::SetActiveChrNo` (`chronicletwo:ps2/src/userdata.cpp:3409`); its ids are 0 to 3, with 2 the Ridepod and 3 the monster (`c2-characters`; unverified). `IxionReceipt.character` must not be compared across games until this map exists.

## Risks and blockers

- **Visible geometry is in the costume packs for DC2.** A DC2 character cannot be shown from its base pack alone. Any experiment must load the costume pack, and which pack is the default outfit (`c01fuku1`, `c01d`, or another) is not confirmed. The kit IDs map to files through the item data, which was not decoded here.
- **Bone-name contract is silent.** Weapon, held item and look bones are looked up by name. Missing names fail silently or in a NULL dereference, and the call sites are not all checked (`chronicle:ps2/src/dun/gameloop.cpp:6561-6566` is one that is not).
- **DC1 motion numbers are a convention.** The shared code uses 0x0A to 0x28 across members. A foreign motion table without those rows may misbehave. Bounds checks at the call sites were not traced.
- **Skin weights are per vertex.** A DC2 `.wgt` index names a vertex of a specific owner. Any retarget that changes vertex order or count breaks the weights. Toan's dungeon mesh has 17 owners and Max's costume has 14, and only two owner names match, so there is no one-to-one owner map to start from.
- **Format mismatch in the other direction.** DC2 `info.cfg` is a semicolon dialect with many commands (`SE`, `SEQ`, `OUTLINE`, `EFFECT`, `SKIN_MODEL`, `OBJECT_NAME2`). DC1 `base.cfg` has 19 commands. A DC1 loader cannot read the DC2 script, and the reverse needs the subset of commands used.
- **Texture atlas and palette.** Toan's textures are 8-bit indexed with a 256-entry palette. Max's are RGBA8. A palette conversion is lossy only if the source has more than 256 colours, which the TIM2 direct-colour path avoids. The UV atlas is the bigger issue.
- **Body size truncation.** DC2 `_BODY_SIZE` reads integers, so `16.00` and `4.00` become `16` and `4`, and any fractional value is lost (inference from the call; not run).
- **Save layout.** Both games store per-character arrays sized for their own roster. A passenger must not write into the native arrays (`c1-characters`, `c2-characters`).
- **Hop v0 data separation.** Each module is started with its own data root (`ixion:docs/HOP-V0.md:118-119`, unverified). Options (a) and (b) need a copy or a host service for the other game's files. The design's loaner rule says no model crosses (`ixion:docs/DESIGN.md:199-201`), so both options are later-phase work by the design's own terms.
- **Audio and voice.** DC1 voice is per ID (`SndVoiceLoad`, `chronicle:ps2/src/btitem.cpp:123`). DC2 Max's bank is set by his gun item (`chronicletwo:ps2/src/charasetup.cpp:108-138`). Neither is tested for a foreign body.

## Open questions

- Which DC2 costume pack is Max's default outfit, and which items map to `c01fuku1` and `c01d`? (The kit IDs are in the item data, which was not decoded.)
- Does `c01f.mds` (DC2 costume, 123 bones) carry `weapon` or `ef00`? It carries `ef00` and no `weapon` (checked). Its skin-weight count is not checked. The base `c01b.wgt` has only 15 weight records, so the costume's `.wgt` is the one to check.
- Which catalog PNG is Max's face? The catalog keys do not say, and no other source names it.
- Does the DC1 decoder take direct-colour TIM2 for these textures, and which TIM2 header value maps to each `bpp` argument of `PortDecodeTexture`?
- What is Toan's skeleton root? Candidates from the MDS record order are `c01d_1_2_1_1` and `ctr`, but the parent chain was not walked.
- Do the `dcol0` and `dcol1` weapon hit boxes live in weapon models rather than the base MDS? (`chronicle:ps2/src/charakey.cpp:238` names them; the base MDS has `dcol` only.)
- Does DC1's `SetMotion` for a missing row, or a short row table, write out of range at `motion[2]` (`chronicle:ps2/src/clothread.cpp:537`)?
- What does the DC2 player's world-collision query use? The DC2 move path was not traced, so only the body-versus-attacker test is known.
- Is the DC1 menu pose model (`c01dstat.mot`) usable as the status pose for a foreign body, given that DC1's `c01d.mds` in the menu pack is 149,696 bytes and the dungeon copy is 149,968 bytes?
