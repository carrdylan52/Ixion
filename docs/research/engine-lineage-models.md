# Engine lineage: character models and motions

## What this covers

How character models, skeletons, skin weights, motions and textures are stored and played in Dark Cloud (Chronicle, DC1) and Dark Chronicle (ChronicleTwo, DC2), and whether the two formats are one family. It compares the DC1 loader (`chararead`, `motionmodel`, `dataset`, `gameutil`, `frame`) with the DC2 loader (`character`, `visualmotion`, `mg_dataset`, `mg_visual`, `gameutil`, `mg_frame`), checks the community specs in `refs/DCExtractor/Specifications/Models` against the decomp and against bytes from the extracted PAL data, and reads the Noesis and Blender tools in `refs/`. It ends with what a converter would need in each direction.

Evidence labels: **fact** = read in code or checked in bytes; **survey** = counted over the extracted PAL data (counts include the same file in several packs, so they are not unique-model counts); **inference** = one step beyond what was read.

This file replaces an earlier draft at the same path. The earlier draft stated that DC2 runs `.wgt` skin channels through `MotionProc3` for the main character. The code shows that the main model's weights do not go through that list. The list serves the DC2 shadow model and the `SKIN_MOTION` command (see Key facts), so that statement is corrected here.

## Key facts

### Containers

- **fact**: `.chr` is a PACK archive in both games. Each entry is a 76-byte header (64-byte name, then offset, size and next, all relative to the entry) followed by data. The first entry's data starts at byte 80, and `next` is 16-byte aligned. The same struct is used in both trees: `chronicle:ps2/src/dataread.cpp:43` (`PACK_ENTRY`) and `chronicletwo:port/src/dataread_pack.cpp:44` (`RegisterMember` walks `PACK_ENTRY`).
- **survey**: `chara/f00s.chr` (DC1) holds `info.cfg`, `f00s.mds`, `f00s.img`, `f00s.wgt`, `f00s.mot`, `f00s.bbp`. `chara/c01_base.chr` (DC2) holds `info.cfg`, `c01b.mds/.bbp/.mot/.wgt`, `c01s.mds/.bbp/.wgt` and `c01_atora.clo`. All entries parse cleanly with the same walker in both.
- **fact**: the community CHR spec (`refs/DCExtractor/Specifications/Pack/CHR.md`) says `.chr` is identical to PAK. The 80-byte header and name field agree with the data. The spec's fourth field ("type") behaves as the relative offset to the next entry (**inference** from the `next` values).

### Scene files (.mds)

- **fact**: the `.mds` is a scene file, not a skeleton-only file. The header is `MDS\0`, a word that is 1 in shipped files, the object count, and the offset of the first object (16). Each object is a 112-byte record: two words (index, then size 112), a 32-byte name, a data offset (0 for a plain bone), a parent index (-1 for root), and a 4x4 float matrix relative to the parent. `chronicle:ps2/include/mds.hpp:20` (`MDS_HEADER`) and `:31` (`MDS_OBJECT`) describe it; `chronicletwo:ps2/include/mg_dataset.hpp:64` (`MDS_HEADER`) and `:79` (`MDTOBJ_HEADER`, size 0x70) describe the same bytes.
- **fact**: the community MDS spec (`refs/DCExtractor/Specifications/Models/MDS.md`) matches the shipped files on the header and the 112-byte records. Its "bone" is the same record as the decomp's "object". Its "version" field is 1 in the shipped files (and 0 in one test file), and the Blender tool asserts 1 (`refs/Blender-Tools-For-Dark-Cloud/DarkCloudModelTools/filetypes/MDS/MDSBinary.py:22`).
- **survey**: object counts agree with the `.bbp` sizes. `f00s.mds` has 35 objects and `f00s.bbp` is 2240 bytes (35 x 64). `c01b.mds` has 124 objects and `c01b.bbp` is 7936 bytes. `c01s.mds` has 110 and `c01s.bbp` is 7040 bytes.

### Model blocks (MDT)

- **fact**: an MDT block has a 64-byte header with the same field order in both games: `MDT\0`, header size 64, mesh-data size, vertex count and offset, normal count and offset, colour count and offset, face-section size and offset, UV count and offset, material count and offset, and one spare word. Field positions match `chronicle:ps2/include/mdt.hpp:10` (`MDT_HEADER`) and `chronicletwo:ps2/include/mg_visual.hpp:50` (`MDT_HEADER`). Both headers were read on sample blocks: DC1 `f00s` object 11 has 8 vertices, 8 normals, 8 UVs, 1 material; DC2 `c01b` object 7 has 3 vertices, 1 normal, 3 UVs, 1 material. The field positions are the same; the offsets differ because the counts differ.
- **fact**: vertices, normals and UVs are 16-byte vec4s. In the DC2 sample the fourth component is 1.0 for vertices and normals, and UVs carry u, v and padding. The DC2 builder writes zero in a normal's fourth component (`chronicletwo:ps2/include/mg_dataset.hpp`, `MG_MDT_DATA_NORMAL` comment), so shipped data and builder disagree there. The fourth normal component is probably unused (**inference**).
- **fact**: the face section starts with a 16-byte header (`unk`, `0x10`, primitive count at +8, `unk`). Each primitive has a 12-byte header (a word holding the GL primitive style in its low byte and the index type in the next byte, the vertex count, and the material index), then the indices. An index holds 3 ints (vertex, normal, UV) for type 0, 4 ints (plus colour) for type 1, 2 ints for type 2, and 1 int for type 3. This is the community spec's polygon and triangle-strip layout (`refs/DCExtractor/Specifications/Models/MDS.md`, "Polygon" and "TriangleStrip"). DC2 names it `MDT_FACES` and `FACES_ID` (`chronicletwo:ps2/include/mg_visual.hpp:95`, `:110`), and the DC2 port walks it the same way (`chronicletwo:port/src/visualmotion.cpp:8`, the `prim_num` loop).
- **survey**: DC2 uses all four index types (type 0: 410,595 strips; type 1: 5,968; type 2: 37; type 3: 9). DC1 is almost entirely type 0 (94,115 strips; type 1: 1).
- **survey, unresolved**: in 51 DC1 blocks with a non-zero colour offset, 81 strips carry index type 0. Both the retail reader and the DC1 port choose the index stride from the colour offset alone, so these strips would be read with 4 ints per index (unverified). See Risks.
- **fact**: a material is 96 bytes in both games. Diffuse, ambient and specular vec4s, a float (50.0 in the samples), then the texture name at +52. The community spec gives a 44-byte name (`refs/DCExtractor/Specifications/Models/MDS.md`). DC1 reads 44 bytes (`chronicle:ps2/include/mdt.hpp:32`, inside the struct at `:27`). DC2 declares 32 bytes and uses the rest for an int and two floats (`chronicletwo:ps2/include/mg_visual.hpp:77`).
- **survey**: texture names are short in both. The longest DC1 name in 39,295 material records is 15 characters. The longest DC2 name in 65,054 records is 19 characters. Nothing overruns the 32-byte field.

### Skeleton matrices (.bbp)

- **fact**: `.bbp` is one 4x4 float matrix per object in MDS order, 64 bytes each, with no header. `refs/DCExtractor/Specifications/Models/BBP.md` says the same. Both engines take it as the motion's base matrices: `chronicle:ps2/src/gameutil.cpp:587` (`CreateAnimeDataEX`, slot 0) and `chronicletwo:ps2/src/gameutil.cpp:875` (`CreateAnimeDataEX`, `info[0]`). DC2's `_MOTION` also copies the same bytes into the root frame's `init_matrix` (`chronicletwo:ps2/src/character.cpp:2360`).
- **survey**: the first rotation key of each DC2 channel equals the bind rotation in the MDS object matrix (see Quaternions below), which fits `.bbp` being the rest pose the keys start from.

### Motions (.mot)

- **fact**: `.mot` is a sequence of channels. Each channel is a 32-byte header: bone (object) index, a word that is 0 in every sample, channel type, header size (32), key count, `animationByteSize`, and two unused words. Each key is 32 bytes: a 1-based frame index, 12 bytes of padding, and four floats. The DC1 decomp reads the same bytes as `Mot_File_List` and `Mot_Key` (`chronicle:ps2/include/gameutil.hpp:226` and `:252`), with the `more` field at +20 in the position the spec calls `animationByteSize`. The loader in `CreateAnimeDataEX` (`chronicle:ps2/src/gameutil.cpp:587`) keeps reading records in a `do ... while (record->more != 0L)` loop. DC2's loop is the same (`chronicletwo:ps2/src/gameutil.cpp:875`).
- **survey**: every sampled `.mot` walks exactly. `animationByteSize` equals the channel's total byte size (header plus keys), which is `(key_count + 1) * 32`. The last channel in a file has `animationByteSize` 0, which is the terminator (unverified). The Noesis plugin uses the same field as a block size (`refs/noesis-mds-plugin/fmt_mds.py:259`, `LoadOldMotion`, `bs.seek(start + blockSize)`).
- **fact**: the community MOT spec (`refs/DCExtractor/Specifications/Models/MOT.md`) describes the same layout and calls the trailing field "unknown". It also says `.mot` holds a whole animation set with `KEY` slices in `info.cfg`. Both games do that (see Scripts).
- **fact, conflict**: the channel-type list differs. The spec gives rotation 0, scale 1, translation 2, "UniformScale" 0x28 (40) and "Unknown" 0x32 (50). The decomp enums name 40 as material alpha and 50 as visible (`chronicle:ps2/include/gameutil.hpp:28`-`:44`; `chronicletwo:ps2/include/gameutil.hpp:28`-`:41`). The engines are the better reference for the type numbers, but the spec was written by reverse engineering, and nothing in the decomp checks the spec's labels.
- **survey, channel types (unverified)**: DC1 `.mot` entries in packs use types 0, 1, 2, 12 (vertex), 20 (two channels), 30 and 31 (camera position and target), 32, 33 (camera FOV), 40 (material alpha), 50 (visible). DC2 `.mot` entries in packs use 0, 1, 2, 12, 40 and 50. Type 20 (`MOTION_KEY_SKIN_WEIGHTED`, `chronicletwo:ps2/include/gameutil.hpp:32`) is in the DC2 enum but does not appear in DC2 `.mot` data. It is the value in every `.wgt` header (see Weights).

### Quaternions

- **fact**: DC1 `QuatToMat` reads component 0 as w (`chronicle:ps2/src/frame.cpp:212`, the `wx = quaternion[0] * x2` family). The Noesis plugin reads the file's first float as w (`refs/noesis-mds-plugin/fmt_mds.py:240` and `:253`, `NoeQuat([v[1], v[2], v[3], v[0]])`).
- **fact, naming**: DC2 `QuatToMat` (`chronicletwo:ps2/src/mg_frame.cpp:46`) names component 0 `x` and component 3 `w`. Working through the matrix formulas by hand, these names are wrong and the arithmetic is the standard (w, x, y, z) rotation. The engine's convention is therefore w-first in both games (**inference** from the algebra, checked on two matrix entries).
- **survey**: DC1 rest keys are (1, 0, 0, 0). DC2 `c01b` first rotation keys, read as (w, x, y, z) and built into a matrix, equal the local 3x3 of the matching MDS object exactly, for the 40 channels tested (unverified). Read as (x, y, z, w) they miss by a median of 7.8 in squared error. The test used the row-major reading of the object matrix, which matched the bind pose exactly.
- **fact, sign handling differs**: DC1 negates the w component before building the matrix in its rotation branch (`chronicle:ps2/src/gameutil.cpp:228`, and inside `QuatSlerp` at `:125`). DC2 `MotionProc` does not negate in its rotation branch (`chronicletwo:ps2/src/gameutil.cpp:77` onward). DC1's `QuatToMat` also writes the transposed off-diagonal terms (`chronicle:ps2/src/frame.cpp:212`). The two sign and layout conventions probably cancel, but this was not verified numerically (see Open questions).

### Skin weights (.wgt)

- **fact**: `.wgt` is a list of weight blocks. Each block is a 32-byte header: mesh-owner object index, driver (bone) object index, a word that is 20 in every sample (`0x14`), header size (32), weight count, next-block offset (`32 + 32 * count`), and two words that are not constant (the community spec's magics `0xACE63701` and `0xB0F0FC77` are not present). Each weight is 32 bytes: vertex index at +0, a float at +16 on a 0 to 100 scale, and zeros elsewhere. `refs/DCExtractor/Specifications/Models/WGT.md` describes this. The Blender tool asserts the 20 and 32 (`refs/Blender-Tools-For-Dark-Cloud/DarkCloudModelTools/filetypes/WGT/WGTBinary.py:49`-`:50`).
- **fact**: the DC2 decomp names the same fields `VertexWeightBlock` (`chronicletwo:ps2/src/visualmotion.cpp:37`) and `VertexWeightEntry` (`:51`). The word that is 20 is `MOTION_KEY_SKIN_WEIGHTED` in the DC2 enum (**inference**: the header's type field; DC1 ignores type except for `MOTION_KEY_SKIP`).
- **survey**: weights sum to 100 per vertex across the sampled blocks. Per-vertex influence counts over all `.wgt` entries in packs (unverified):

| Game | Entries | 0 bones | 1 | 2 | 3 | 4 | 5 | Owners with more than 32 driver bones |
|---|---|---|---|---|---|---|---|---|
| DC1 | 1,253 | 17 | 262 | 434 | 415 | 101 | 24 | 18 |
| DC2 | 1,791 | 128 | 114 | 928 | 472 | 133 | 16 | 16 |

### How each engine applies skin weights

- **fact, DC1 main model**: the `.wgt` is passed as the motion's third file and turned into a second key list (`proc_list2`) by `CreateAnimeDataEX` (`chronicle:ps2/src/gameutil.cpp:587`, `files[2]`). `SetMotionEX` runs `MotionProc2` over that list every frame (`chronicle:ps2/src/gameutil.cpp:543` and `:567`). `MotionProc2` moves each vertex by the driver's transform, scaled by `0.01 * weight` (`chronicle:ps2/src/gameutil.cpp:456`, inside `MotionProc2` at `:401`; PC port at `chronicle:port/src/gameutil_motion.cpp:51` with `SkinVertex` at `:20`). A model is set up for this when its `VERTEX_ANIME` flag is set. That makes `visual_type` 6, which keeps a copy of the MDT data (`chronicle:ps2/src/chararead.cpp:221`-`:232`; `chronicle:ps2/src/dataset.cpp:498`, `CreateVisual`, `attr & 2`).
- **fact, DC2 main model**: `_MODEL` loads the `.wgt` by name, taking the model's base name plus `.wgt` (`chronicletwo:ps2/src/character.cpp:2032`-`:2033`), and passes it to `mgLoadMDSFile` (`:2061`). Objects named by `VERTEX_ANIME` become `mgCVisualMotionMDT`, which builds a per-vertex table of up to four bone slots and weights (`chronicletwo:ps2/src/visualmotion.cpp:58`). There are at most 32 bone slots per model (`chronicletwo:ps2/include/visualmotion.hpp:68`). The GPU path uses those slots as a matrix palette (`chronicletwo:port/src/visualmotion.cpp:8`, `DataAssignMotionMDT`, which calls `CreateVertexWeight` at line 23).
- **fact, DC2 weight limits**: a fifth influence is not stored. The loop only fills four slots and reports "Weight Num Over" (`chronicletwo:ps2/src/visualmotion.cpp:123`, `:141`). A 33rd driver bone for one owner aborts the weight build for that model: "Bone Num Over", and the weight pointer is cleared (`chronicletwo:ps2/src/visualmotion.cpp:114`). So DC2 drops both kinds of data silently.
- **fact, DC2 shadow model and special skins**: `_MOTION` (main) sets the weight slot to NULL (`chronicletwo:ps2/src/character.cpp:2342`). `_SHADOW_MOTION` passes the `.wgt` through `GetPackFile` (`:2411`) into the motion's skin list. That list is evaluated on the CPU by `DeformMesh`, which calls `MotionProc2` or `MotionProc3` (`chronicletwo:ps2/src/gameutil.cpp:716`; called from `chronicletwo:ps2/src/character.cpp:679` for the shadow). `_SKIN_MOTION` (`chronicletwo:ps2/src/character.cpp:3313`) is a separate command with its own matrix and weight files, and it feeds the skin list through `ChangeWeight` (`:3440`).
- **inference**: the DC2 CPU path has no four-influence or 32-bone limit. It walks the key list. A converter could therefore keep a DC1 model's full weights by using the shadow-style path, but this was not tested.

### Scripts (info.cfg)

- **fact**: DC1 `info.cfg` is line-based with space-separated arguments and no semicolons. The dispatch table has 19 commands (`chronicle:ps2/src/chararead.cpp:92`): `VERTEX_ANIME`, `SHADOW_VERTEX_ANIME`, `MODEL`, `SHADOW_MODEL`, `MOTION`, `SHADOW_MOTION`, `KEY`, `KEY_START`, `MOTION_END`, `CLOTH`, `BODY_SIZE`, `ALLOC_MDT`, `ALLOC_DBUFF`, `ALLOC_SHADOW_MDT`, `ALLOC_SHADOW_DBUFF`, `IMG`, `IMG_END`, `FOOT`, `EVENT`.
- **fact**: DC2 `info.cfg` starts with `v2;`, uses semicolon-terminated statements, and has a much larger command table (`chronicletwo:ps2/src/character.cpp:290`-`:330`; `MODEL` at 294, `MOTION` at 298, `VERTEX_ANIME` at 301, `KEY_START` at 303, `CLOTH_START` at 309). Its extra commands include `OUTLINE`, `OBJECT_NAME2`, `SCALE`, `POLY_NUM`, `SHAPE_ANIME`, `SEQ_START`/`SEQ`, `SE_START`/`SE`, `POSITION`, `ROTATION`, `EFFECT_START`/`EFFECT`, and `LOD_MODEL_START`/`LOD_MODEL`.
- **fact**: the `MOTION` argument order is the same in both: motion, bone, weight (`chronicle:ps2/src/chararead.cpp:283`; `chronicletwo:ps2/src/character.cpp:2305`).
- **fact**: `VERTEX_ANIME` differs in kind. DC1 takes an integer flag (`chronicle:ps2/src/chararead.cpp:213`, `vertex_anime = *(int *)`). DC2 takes a list of object names (`chronicletwo:ps2/src/character.cpp:2443`; the `c01b` script has `VERTEX_ANIME "skin1", "skin2", "skin3", "R_te", "L_te"`).
- **fact**: the weight file name is explicit in DC1 and derived in DC2. A DC1 script can name any `.wgt`. DC2 always uses the model's base name plus `.wgt` for the main model, although `MOTION` still names one.
- **fact**: DC1 `KEY` lines hold only a start frame, end frame and speed, with the motion name left in a comment (`chronicle:ps2/src/chararead.cpp:399`). DC2 `KEY` lines take a quoted name, and `SetMotion(char *)` looks motions up by name (`chronicletwo:ps2/src/character.cpp:2488` and `:771`).
- **fact**: the two community-side readers assume the DC1 dialect. The Blender tool reads the `MOTION` line by fixed token index (`refs/Blender-Tools-For-Dark-Cloud/DarkCloudModelTools/filetypes/CFG/CFGInterface.py:37`-`:49`). The Noesis plugin has a `bDarkCloud1` switch that changes how `IMG` and `MODEL` lines are split (`refs/noesis-mds-plugin/fmt_mds.py:5`, `:106`-`:111`).

### Textures

- **fact**: DC1 `.img` archives begin with `IM2\0` (or `IMG\0`). In `f00s.img` the picture is a TIM2 at byte 64, after a 16-byte header and one 48-byte sub-header. This matches the community IM2 spec (`refs/DCExtractor/Specifications/Images/IMG (Version 2).md`), and the TIM2 layout is in `refs/DCExtractor/Specifications/Images/TM2.md`. Blender (`refs/Blender-Tools-For-Dark-Cloud/DarkCloudModelTools/filetypes/CHR/CHRBinary.py:86`-`:91`) and Noesis (`refs/noesis-mds-plugin/fmt_mds.py:192`, `:220`, `0x324D4954` TIM2) read the same bytes.
- **survey**: DC1 pack entries: 1,555 `IM2` and 892 `IMG` archives over all packs.
- **fact**: DC2's engine knows three archive versions: `IMG` (0x30-byte entries), `IM2` (0x30 entries, swizzled pixels) and `IM3` (0x40 entries with block, flags and clamp) (`chronicletwo:ps2/include/mg_texture.hpp:52`-`:57`; `mgIMG_HEADER` at `:175`). Its `IM2` check is at `chronicletwo:ps2/src/mg_texture.cpp:1058`.
- **survey, blocker**: in the extracted DC2 data, no `.img` entry in a `.chr` pack holds an `IM2`, `IMG` or TIM2 header. Of 2,972 `.img` entries, 2,859 are zero-length and the rest are zero-filled (unverified). The DC2 `.ipk` map pack `i04h01` is 1.7 MB and has only 122 non-zero bytes (unverified). The DC2 port explains this design: `RegisterMember` returns an opaque in-memory handle for any source in the texture catalog, and the comment says "the published PACK has no texture payload" (`chronicletwo:port/src/dataread_pack.cpp:44`-`:60`).
- **fact**: the texture catalog is a versioned JSON file (`schema_version` 1) with per-source entries: type, name, block, swizzle and clamp flags, size, and palette and level file paths (`kazarov:include/platform/texture_catalog.hpp:12`, `Entry`; `:41`, `Source`; `:54`, `Load`). Loading is in `kazarov:src/cpp/platform/texture_catalog.cpp:29`. `chronicletwo:port/src/texture_source.hpp:8` registers a game-visible buffer against its catalog source.
- **fact**: the DC1 PC port reads TIM2 header structures from the IM2 archive directly (`chronicle:port/src/texture.cpp:434`, `TM2_head` from the entry offset). It does not go through the catalog.

## How it works

### Loading a character, DC1

1. `ReadInfo` (`chronicle:ps2/src/chararead.cpp:135`) reads the pack's `info.cfg`, strips comments, and runs each command through the table at `:92`.
2. `CommandMODEL` (`:221`) fetches the `.mds` and calls `LoadMDSFile` (`chronicle:ps2/src/dataset.cpp:348`). The loader makes one `CFrameVu1` per object, skipping names that start with `func_`, sets its parent from the file, and builds a visual from the MDT data at the object's offset (`CreateVisual`, `dataset.cpp:498`). Attribute bits decide the visual class and whether the MDT copy and a second VU buffer are kept (`dataset.cpp:498`-`:580`).
3. `CommandMOTION` (`chararead.cpp:283`) fetches `.mot`, `.bbp` and `.wgt` and passes them to `CreateAnimeDataEX` (`gameutil.cpp:587`). Each file becomes a channel list (`proc_list`, `proc_list2`) or the base matrices. `AnimeDataInit` (`gameutil.cpp:707`) then records each frame's parent and base vertices for skinning.
4. `KEY_START`, `KEY` and `MOTION_END` (`chararead.cpp:390`, `:399`, `:415`) define the named slices of the master animation. `KEY` lines hold start, end and speed.
5. Playback: `SetMotionEX` (`gameutil.cpp:509`) interpolates the list with `MotionProc` (`:179`), then the skin list with `MotionProc2` (`:401`). Rotation uses slerp (`:114`), and the other channel types use linear interpolation.

### Loading a character, DC2

1. `CCharacter2::LoadPack` and `LoadChrFile` (`chronicletwo:ps2/src/character.cpp:1597`, `:1605`) call `ScanInfoFile` (`:1727`), which runs the script through the command table (`:290`-`:330`). The data is read through `GetPackFile`.
2. `_MODEL` (`:2007`) finds the `.mds` and derives `.wgt` from its name (`:2032`). It calls `mgLoadMDSFile` (`chronicletwo:ps2/src/mg_dataset.cpp:646`). A visual becomes `mgCVisualMotionMDT` only when a weight is present; otherwise it becomes the fixed-MDT class (`mg_dataset.cpp:563`).
3. `_MOTION` (`:2305`) fetches the three files. It copies the bone file into `init_matrix` and calls `CreateAnimeDataEX` (`chronicletwo:ps2/src/gameutil.cpp:875`) with the weight slot set to NULL (`character.cpp:2342`). The `motion_list` holds the keys. The weights reach the model through `mgCVisualMotionMDT`, not through the motion.
4. Playback: `SetMotionTime` and `ChangeMotion` run `MotionProc` over `motion_list` (`chronicletwo:ps2/src/gameutil.cpp:700`, `:708`). `DeformMesh` (`:716`) runs `MotionProc3` (normals) or `MotionProc2` over `skin_list`, which is used for shadows.

### Format comparison

| Item | DC1 (Chronicle) | DC2 (ChronicleTwo) | Same bytes? |
|---|---|---|---|
| Pack entry | 76-byte header, data at entry + offset | same | yes |
| Scene header and 112-byte object record | `MDS_HEADER`, `MDS_OBJECT` | `MDS_HEADER`, `MDTOBJ_HEADER` | yes |
| MDT header (64 bytes) | `MDT_HEADER` | `MDT_HEADER` | yes |
| Face section | polygon + strip headers (style, index type) | `MDT_FACES`, `FACES_ID` | yes; DC2 uses index types 0 to 3, DC1 nearly only 0 |
| Material (96 bytes) | 44-byte name | 32-byte name plus two extra fields | record size yes; name width differs but no name is affected in the data |
| Bind matrices | 64 bytes per object | same | yes |
| Motion channel and key | 32 + 32 bytes | same | yes |
| Quaternion order | w, x, y, z | w, x, y, z (names in `QuatToMat` are wrong) | yes |
| Quaternion sign in rotation branch | negates w | no negation | no (sign convention) |
| Weight block | 32-byte header, 32-byte weights, type word 20 | same | yes |
| Skin evaluation | `MotionProc2` on every skinned model | VU1 palette (main model, 4 influences, 32 bones) and CPU `MotionProc2` (shadow) | no |
| Script | 19 commands, space separated | `v2;` header, semicolon statements, many more commands | no |
| `VERTEX_ANIME` | integer flag | list of object names | no |
| Weight file name | explicit in `MOTION` | `<model>.wgt`, derived | no |
| Texture archive | `IM2` / `IMG` with TIM2 | `IMG` / `IM2` / `IM3`; payloads absent from this extraction | same family; DC2 payloads not testable locally |

## Ixion hooks

- **chronicletwo:ps2/src/character.cpp:1597-1605** (`LoadPack`, `LoadChrFile`): the entry point for a DC2 character. A DC1 pack could be accepted here by an adapter that rewrites its `info.cfg` into the DC2 dialect before `ScanInfoFile` (`:1727`). The rest of the loader is unchanged.
- **chronicletwo:ps2/src/character.cpp:2032-2033** (weight name in `_MODEL`): if the adapter repacks the DC1 weight under `<model>.wgt`, the DC2 loader finds it without changes. This is the cheapest seam for the weights.
- **chronicletwo:ps2/src/character.cpp:2342** (weight slot NULL in `_MOTION`): a DC1 main model can be given the CPU skin path by passing the weight into the skin list the way `_SHADOW_MOTION` does (`:2411`). That bypasses the four-influence and 32-bone limits of the VU1 path. The trade-off is CPU cost (**inference**).
- **chronicletwo:ps2/src/visualmotion.cpp:58-141** (`CreateVertexWeight`): the limit point. A normaliser that keeps the four largest influences per vertex and splits owners that have more than 32 drivers would make DC1 weights fit this path. The adapter could do it offline instead.
- **chronicletwo:ps2/src/gameutil.cpp:875** (`CreateAnimeDataEX`): the record layout is shared, so a DC1 `.mot` or `.wgt` can be read here as it is. Remapping the `frame` and `target` fields (object indices) per record is the cleanest place for a skeleton map.
- **chronicletwo:ps2/src/gameutil.cpp:521, :606, :716** (`MotionProc2`, `MotionProc3`, `DeformMesh`) and **chronicletwo:port/src/visualmotion.cpp:8** (`DataAssignMotionMDT`): the skin consumers. Any change to which vertices a driver moves must keep these consistent.
- **chronicle:ps2/src/chararead.cpp:213-232** (`VERTEX_ANIME`, visual type 6): a DC2 skinned model loaded into DC1 needs this flag to keep the MDT copy that `MotionProc2` writes into. The adapter must emit `VERTEX_ANIME 1` for any model whose DC2 script lists skinned objects.
- **chronicle:ps2/src/gameutil.cpp:228** (w negation in `MotionProc`) and **chronicletwo:ps2/src/gameutil.cpp:77** (no negation): one of these must change when rotation keys move between engines, or rotations will invert. Verify with a single bone before relying on either.
- **chronicle:port/src/visualvu1.cpp:55-67** (`View`, stride from colour offset) and **:598** (`CreateVUdataFromMDT`): the DC1 PC reader. A DC2 model with mixed index types in one block would be misread, so either split such blocks or fix the reader to use the per-strip type.
- **chronicle:port/src/gameutil_motion.cpp:51** (DC1 PC `MotionProc2`): the DC1 port's skinning. A DC2 weight table can feed this directly if its records are in the layout of `CreateAnimeDataEX`.
- **chronicletwo:port/src/dataread_pack.cpp:44** (`RegisterMember`): the catalog hook. A converted DC1 texture can be registered here under the name its material uses. The DC2 port then decodes it from the catalog, not from TIM2 bytes.
- **kazarov:src/cpp/platform/texture_catalog.cpp:29** (`Load`): the catalog loader. A DC1-to-catalog exporter would write `schema_version` 1 entries with level paths.
- **refs/Blender-Tools-For-Dark-Cloud/DarkCloudModelTools/filetypes/MDS/MDSBinary.py:20-22** and **refs/Blender-Tools-For-Dark-Cloud/DarkCloudModelTools/filetypes/WGT/WGTBinary.py:49-50**: an independent DC1 reader for validating converter output.

## Risks and blockers

- **Index-type stride (unresolved)**: 81 strips in 51 DC1 blocks with a colour offset carry index type 0. Both the retail reader (`chronicle:ps2/src/visualvu1.cpp:748`-`:753`) and the port (`chronicle:port/src/visualvu1.cpp:64`) pick the stride from the colour offset alone. Either those strips are never drawn, or the type byte does not mean what the spec says, or the stride rule is wrong. Any converter that rebuilds DC1 faces from the spec would inherit the same question. Check with a runtime frame of one such model before trusting the spec's index-type rule.
- **Skin limits**: Of the DC1 weight files (pack entries), 24 have a vertex with five influences and 18 have more than 32 driver bones for one owner (unverified). The DC2 figures are 16 and 16 (unverified). The DC2 VU1 path loses the extra influences and fails the whole skin for the 33+ bone cases. A DC2 model converted into DC1 has no such limit (the DC1 `MotionProc2` loops over all keys), so that direction is safer.
- **Quaternion convention**: DC1 negates w in the rotation branch and DC2 does not. Mixing motions and models from the two without a sign fix can invert rotations. The sign and transpose conventions may cancel, but this was not checked on a moving bone.
- **Skeleton mismatch**: MOT channels and WGT blocks index objects by MDS order. If the donor and the target skeleton differ in object count or order, every channel drives the wrong bone. The object counts were checked only for single files (DC1 `f00s` 35, DC2 `c01b` 124, DC2 `c01s` 110). No cross-game skeleton map was built here.
- **DC2 texture payloads**: the extracted DC2 `.img` entries are empty, so DC2 texture bytes cannot be checked locally, and the port's catalog holds converted PNG variants rather than TIM2. A DC2-to-DC1 texture path needs the source textures from another source (the disc or the catalog).
- **Script coverage**: DC2 scripts use commands that a DC1 script never provides (`SE`, `SEQ`, `EFFECT`, `OBJECT_NAME2`, `OUTLINE`, `SKIN_*`). A DC1 pack converted into the DC2 dialect would need defaults for each. A missing `OBJECT_NAME2` or `SEQ` might fail silently or crash. Not tested.
- **Key names**: DC2's `SetMotion(char *)` needs names that DC1 `KEY` lines do not carry. Names would have to come from the DC1 comments (inference: those comments hold the Japanese names, shown as raw bytes in the extract) or be supplied by hand.
- **Unknown words**: the MOT header's word at +12 and the WGT words at +24 and +28 are not understood. A converter must copy them through unchanged.
- **Assets**: converted models, motions and textures are game data. They belong in the git-ignored data area and must not go into any public commit or PR.

## Open questions

- Does the retail DC1 engine really pick the stride from the colour offset for every strip? Run one of the 51 colour blocks with type-0 strips and see whether those strips are drawn, and what they look like.
- Which quaternion convention is right when a DC1 rotation is played through the DC2 `MotionProc`? Test one bone on each engine with a known rest pose.
- Are the MOT types 0x28 and 0x32 (spec "UniformScale" and "Unknown") actually 40 and 50 in the data? The engine enums say material alpha and visible. A check needs a file that uses type 40 with a single float or type 50 with a single value.
- DC1 `.mot` entries contain two type-20 channels. Which blocks are they, and do they belong to a skin set rather than a motion?
- Does DC2's CPU shadow path (`DeformMesh` via `MotionProc2`) accept more than four influences and more than 32 drivers without loss? This would make a full-weight DC1 model possible in DC2 with a shadow-style path. Not tested.
- Are DC2 texture payloads absent from the disc, or only from this extraction? The port's catalog design suggests the PACK intentionally has none.
- Which DC2 pack corresponds to which named character? The decomp refers to `chara/c01d.chr` for the DC1 hero (`chronicle:ps2/src/editloop.cpp:1003`) and lists `c01_base` among DC2 character packs (`chronicletwo:ps2/src/userdata.cpp:1713`). The mapping from pack to name was not checked against the game data.
- What does the DC2 `.wgt` word at +8 mean beyond being 20? Its value matches the DC2 skin-weighted key type, but no code path was found that checks it.
