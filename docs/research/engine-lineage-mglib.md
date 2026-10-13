# Engine lineage: the shared mglib

## What this covers

The Level-5 graphics layer that both games draw every model, frame, texture, camera and sprite through. Chronicle (DC1) has it as the `mglib`, `frame`, `texture`, `visual*`, `object*`, `camera`, `spritetable` and `dataalloc` units. ChronicleTwo (DC2) has it as `mglib` plus the `mg_*` units. This note maps the equivalent types and functions, compares struct layouts, names what each PC port replaces, and judges how far content from one game could be drawn by the other game's engine.

Scope limits: read-only analysis of the pinned source trees, the PAL extractions, and the DCExtractor specifications. No builds and no game launches. Byte-level checks used a few sample blocks from each extraction and a full scan of model block headers; those are labelled as observations. Model and motion file formats are covered in depth by the companion note `engine-lineage-models.md`. Data loading is in `c2-data-loading.md`, and the two render and present notes are `c1-render-present.md` and `c2-render-present.md`.

Citation prefixes: `chronicle:` is the DC1 tree (ps2/ and port/), `chronicletwo:` is the DC2 tree, `kazarov:` is the Kazarov library on its current layout (pin 3dc38ce for DC2), and `kazarov@a0a5ff8:` is the older layout that DC1 pins.

## Key facts

- **Same family, same vocabulary.** DC1 exposes plain C functions and globals (`MGInit`, `MGDraw`, `MGSetViewMatrix`, `extern "C" RenderInfo mgRenderInfo`) (chronicle:ps2/include/mglib.hpp:36, :206, :337). DC2 exposes the same roles as `mg`-prefixed functions and C++ classes (`mgCFrame`, `mgCVisualMDT`, `mgCTextureManager`, `mgRENDER_INFO mgRenderInfo`) (chronicletwo:ps2/include/mglib.hpp:365, :688; chronicletwo:ps2/include/mg_frame.hpp:284).
- **Both PC ports lift the PS2 units the same way.** `PORT_OVERRIDE` is an empty marker (kazarov:include/kazarov/port.h:20). The port compiles copies of the ps2 units without the overridden definitions and links the port/src replacements (chronicle:port/CMakeLists.txt:4-8).
- **Both render through the same Kazarov gfx API.** DC1 pins the older layout (`kazarov@a0a5ff8:port/gfx/gfx.hpp`, 687 lines). DC2 pins the current layout (kazarov:include/gfx/gfx.hpp, 749 lines). Both declare `DrawState`, `MeshConstants`, `Prog0Constants`, `TextureBinding` and `InterpKey`. The DC1 pin also contains the Prog0 names (13 matches).
- **Only DC2 uses the Prog0 shader.** DC2 draws face groups with `gfx::DrawMeshProg0`, called through `mgPortDrawMeshProg0` (chronicletwo:port/src/mg_visual.cpp:316; chronicletwo:port/src/mglib.cpp:969), and a `Prog0Constants` block (chronicletwo:port/src/mglib_port.hpp:165). The shader's flags mirror the Vu_prog0 microprogram (kazarov:include/gfx/gfx.hpp:435-457; chronicletwo:docs/vu1/prog0.md). The DC1 port has no Prog0 reference. It draws through `gfx::DrawMesh` with fixed material constants (chronicle:port/src/visualvu1.cpp:558).
- **DC1's headers do not name its VU1 programs, and its port runs no VU microcode.** The `VU1_PROGRAM` enum is a placeholder whose comment says nothing implements the DrawVu1 family (chronicle:ps2/include/vu1.hpp:1-14). That comment is stale: `visualvu1.cpp` implements those functions in ps2/src, and the PC port replaces them. DC1's frame passes the single program value `VU1_PROGRAM_UNKNOWN6` (chronicle:ps2/src/frame.cpp:1274).
- **DC2 has named VU1 programs.** `mgVU_PROG_ID` names main, shadow and 3D-sprite programs plus a user table (chronicletwo:ps2/include/mglib.hpp:42-50). The retail microcode is documented per program in `docs/vu1/` (chronicletwo:docs/vu1/progmain.md, prog0.md, prog_sdw.md, prog_3dsp.md).
- **Struct-size asserts behave differently on PC.** DC1's `STATIC_ASSERT` is compiled out on the port (chronicle:port/include/port.h:60). DC2's `PORT_RECORD_ASSERT` is a live `static_assert` on the port (chronicletwo:port/include/port.h:41), so DC2 layout claims are checked at PC compile time and DC1's are not.
- **The render-info global has the same name in both games with different types.** DC1 `RenderInfo mgRenderInfo` (chronicle:ps2/include/mglib.hpp:36; definition chronicle:ps2/src/mglib.cpp:77). DC2 `mgRENDER_INFO mgRenderInfo` (chronicletwo:ps2/include/mglib.hpp:365). The same applies to `struct MG_PICKZ`, which has the same four fields (`enable`, `x`, `y`, `z`) in both, though the DC2 `z` comment describes an 8 by 8 block, and a different slot count (16 in DC1 at chronicle:ps2/include/mglib.hpp:97, 4 in DC2 at chronicletwo:ps2/include/mglib.hpp:400).
- **Frame attributes are inline in DC1 and a separate object in DC2.** DC1 `CFrame` embeds `CFrameAttr` (chronicle:ps2/include/frame.hpp:25, :58). DC2 `mgCFrame` holds `mgCFrameAttr *attr` and a cached `lw_matrix` (chronicletwo:ps2/include/mg_frame.hpp:284-320; chronicletwo:ps2/include/mg_drawenv.hpp:285).
- **The draw-visibility bits match.** Both use 1 = draw, 2 = skip children, 4 = skipped by parent (chronicle:ps2/include/frame.hpp:27-28 comment; chronicletwo:ps2/include/mg_frame.hpp:21-27 `mgFrameDrawFlag`).
- **Name flags are the main semantic break.** Both games put attribute codes after a double-underscore marker in object names. DC1 parses the letters in place (chronicle:ps2/src/dataset.cpp:198, :234-300). DC2 rewrites each bare letter into a digit-suffixed code and then parses the digits (chronicletwo:ps2/src/mg_dataset.cpp:44-160, called from :512). Two letters mean opposite or different things across the two (details in How it works).
- **The model container and object record are the same on disk.** Both DC1 and DC2 model blocks start with a 16-byte `MDS` header whose object count and offset sit at +8 and +12, with a 112-byte object record whose 32-byte name is at +0x18 in the file (sample-verified; see How it works, "Model containers"). DCExtractor's MDS specification describes the same fields (refs/DCExtractor/Specifications/Models/MDS.md).
- **The model block (MDT) header is word-for-word the same in both games.** Field offsets from +0x0C through +0x38 agree in the two headers (chronicle:ps2/include/mdt.hpp:10-25; chronicletwo:ps2/include/mg_visual.hpp:50-65). Two sample blocks (one per game) carry the same field meanings in the same words: header size 0x40, vertex data starting at 0x40, and the next block starting exactly the block-size word later. The DCExtractor MDTHeader prose (refs/DCExtractor/Specifications/Models/MDS.md, lines 87-91) omits the block-size word, but its struct listing (lines 207-221) includes `meshDataSize` at +0x08 and agrees with both decompiled headers.
- **Material records are the same size with a different name window.** Both are 0x60 bytes: diffuse, ambient or specular vectors, a float at +0x30, and the texture name at +0x34. DC1 declares the name as 44 bytes (chronicle:ps2/include/mdt.hpp:27-33). DC2 declares it as 32 (chronicletwo:ps2/include/mg_visual.hpp:77-87) and copies with `strcpy` (chronicletwo:ps2/src/mg_dataset.cpp:1085-1093).
- **Face and strip layouts agree on the header and differ in flags.** DC1 reads a mesh section with the strip count at word 2 and strips from word 4 (chronicle:port/src/visualvu1.cpp:55-70). DC2's `MDT_FACES` puts the primitive count at +8 (chronicletwo:ps2/include/mg_visual.hpp:95-101). DC2's `FACES_ID.type` word carries the GL primitive in its low 3 bits and flags for flat shading, no texture, colour and no normal (chronicletwo:ps2/include/mg_visual.hpp:25-35).
- **Texture containers are shared; DC2's data has no texture payloads.** DC1 data holds IMG archives of both version 1 and version 2 (IM2), with TIM2 pictures (sampled IMG magics: IM2 in 344 of 400 files, IMG in 56). DC2's extracted tree has no binary TIM2 or IMG/IM2/IM3 archive anywhere (a full scan of all 10,623 files found none; the only files that begin with `IMG` are text `.map` references such as `IMG "a01ia.img";`). DC2 textures come from `port_data/catalog.json` through the Kazarov texture catalog (chronicletwo:port/src/dataread_pack.cpp:50-52; kazarov:include/platform/texture_catalog.hpp:10-60; see `c2-data-loading.md`).
- **DC2 reads three IMG versions; DC1 reads two, as one layout.** DC2 recognises `IMG`, `IM2` and `IM3`, with 0x30-byte entries for the first two and 0x40-byte entries for IM3 (chronicletwo:ps2/src/mg_texture.cpp:1190-1212, :1262-1273). DC1's `EnterIMGFile` treats `IMG` and `IM2` as the same 0x30-byte layout and only flags `IM2` as swizzled (chronicle:ps2/src/texture.cpp:924-935). DCExtractor documents IM3 as a DC2 format (refs/DCExtractor/Specifications/Images/IMG (Version 3).md).
- **Texture registries differ in shape.** DC1 has 72 blocks of 196 textures, fixed at construction (chronicle:ps2/include/texture.hpp:91-101). DC2 has a 101-chain name hash, per-block lists and page-rounded VRAM accounting (chronicletwo:ps2/include/mg_texture.hpp:26, :595-949).
- **Point lights exist only in DC2.** DC1's `MGSetPLight` takes two matrices and stores four directional lights (chronicle:ps2/src/mglib.cpp:741-752), although its doc block calls them point lights (chronicle:ps2/include/mglib.hpp:161). DC2 has directional `mgSetLight` and point lights `mgSetPlight` with a 0x30-byte `mgPOINT_LIGHT` (chronicletwo:ps2/include/mglib.hpp:866, :917; chronicletwo:ps2/include/mg_drawenv.hpp:75-90). DC2's frame draw uses them when a frame has the point-light attribute (chronicletwo:port/src/mg_frame.cpp:107).
- **Cameras are in the hierarchy in DC1 and beside it in DC2.** DC1 `CCamera` embeds a `CFrame` (chronicle:ps2/include/camera.hpp:17-19, size asserted at :215). DC2 `mgCCamera` is a standalone object with a follow subclass (chronicletwo:ps2/include/mg_camera.hpp:27, :306).
- **Sprites differ in use.** DC1's `CSpriteTable` is a 2D pool used only by `spritetable.cpp` and `editloop3.cpp`. DC2 has `mgCSprite` (2D) and `mgC3DSprite` (camera-facing), used by character, effect, event and screen-effect code (chronicletwo:ps2/src/mg_sprite.cpp; grep of chronicletwo:ps2/src for `mgC3DSprite` returns the effect units).
- **Two DC1 headers declare `CVisual` and `CVisualVu1` with different layouts.** `visual.hpp` declares `CVisual` at :30 and `CVisualVu1 : CVisual` at :70, with `vu_data` and `vu_size` (chronicle:ps2/include/visual.hpp:30-75). `visualvu1.hpp` declares a standalone `CVisualVu1` at :15 and a separate `CVisual` at :120 (chronicle:ps2/include/visualvu1.hpp:15-146). The two are used by different translation units.
- **Object names collide.** DC1 `CObject` is a physics and game object of 0xB0 bytes (chronicle:ps2/include/object.hpp:14, :382). DC2 `CObject` is a drawable map object deriving from `mgCObject` at 0x70 bytes (chronicletwo:ps2/include/object.hpp:19). Both have a `CObjectFrame` (chronicle:ps2/include/objectframe.hpp:21, 0xD0 bytes; chronicletwo:ps2/include/object.hpp:217).

## How it works

### Class map

| Concept | DC1 (chronicle) | DC2 (chronicletwo) | Notes |
|---|---|---|---|
| Global render state | `RenderInfo mgRenderInfo` (ps2/include/renderinfo.hpp:16) | `mgRENDER_INFO mgRenderInfo` (ps2/include/mg_drawenv.hpp:339, 0x1020 at :615) | DC1 unasserted; DC2 holds per-context draw envs and light sets |
| Draw environment | Loose GS shadows `mgPixelTest`, `mgZBuffer`, `mgAlpha`, `mgTEX1Env` (ps2/include/mglib.hpp) | `mgCDrawEnv`, 0x40 bytes (ps2/include/mg_drawenv.hpp:150-228) | DC2 keeps two contexts |
| Frame node | `CFrame` (ps2/include/frame.hpp:58) | `mgCFrame`, 0x110 (ps2/include/mg_frame.hpp:284, :775) | DC2 derives from `mgCObject` (0x50) |
| Frame attributes | `CFrameAttr` inline (frame.hpp:25) | `mgCFrameAttr`, 0x90 (mg_drawenv.hpp:285, :331) over `mgCVisualAttr`, 0x18 (:235, :266) | Name-flag fields differ, see below |
| Frame draw | `CFrameVu1::DrawVu1` (ps2/src/frame.cpp:1018) | `mgCFrame::Draw` (ps2/src/mg_frame.cpp:1416; port override port/src/mg_frame.cpp:39) | Both cull by bound, then draw the visual |
| Visual base | `CVisual`, `CVisualVu1` (visual.hpp:30, :70) | `mgCVisual`, 0x20 (mg_visual.hpp:176, :325) | Two conflicting DC1 declarations |
| Model visual | `CVisualMDTVu1` (visual.hpp:143; ps2/src/visualvu1.cpp:939) | `mgCVisualMDT`, 0x50 (mg_visual.hpp:333, :562); `mgCVisualFixMDT`; motion visuals | DC1 builds one VU block per visual |
| Shadow visual | `CVisualShadow` (visual.hpp:201; ps2/src/visualshadow.cpp) | `mgCShadowMDT`, 0x50 (mg_shadow.hpp:23, :81) | DC1 reads shadow sections; DC2 derives shadows from faces (mg_shadow.cpp:150-170) |
| 2D sprite | `CSpriteTable`, 0x94 (ps2/include/spritetable.hpp:50, :123) | `mgCSprite` on `mgCVisualPrim` (mg_sprite.hpp:107) | Different roles, see Key facts |
| 3D sprite | `MGRotTransPers3DSprite` (ps2/src/mglib.cpp:1020) | `mgC3DSprite`, 0x50 (mg_sprite.hpp:191, :340) | DC2 uses Vu_prog_3dsp |
| Texture object | `CTexture`, four mip pointers (texture.hpp:50) | `mgCTexture`, 0x70 (mg_texture.hpp:219, :286) | DC2 adds clamp and VRAM sizes |
| Texture registry | `CTextureManager`, 72 blocks (texture.hpp:91, :99) | `mgCTextureManager`, 0x21C (mg_texture.hpp:595, :949) | DC2 has a name hash |
| Texture animation | `CTextureAnime`, 0x1F0 (textureanime.hpp:77, :190) | `mgCTextureAnime`, 0x1E4 (mg_texture.hpp:355, :515) | Similar purpose |
| Camera | `CCamera`, 0x2C0 (camera.hpp:17, :215) | `mgCCamera`, 0x70; `mgCCameraFollow`, 0xC0 (mg_camera.hpp:27, :299, :306, :547) | DC1 camera sits in the hierarchy |
| Game object | `CObject`, 0xB0 (object.hpp:14, :382) | `CObject`, 0x70 over `mgCObject` (object.hpp:19) | Same name, different role |
| Object with LODs | `CObjectFrame`, 0xD0, four `CFrameVu1 *` (objectframe.hpp:21, :126) | `CObjectFrame` with one frame pointer (object.hpp:217) | |
| Memory | `CDataAlloc2<Kind>` and `CDataAlloc<Kind, Size>` templates (ps2/include/dataalloc.hpp:22) | `mgCMemory`, 0x30, heap and stack modes (mg_memory.hpp:44, :245) | DC1 sizes are compile-time |
| Model loader | `LoadMDSFile` (ps2/src/dataset.cpp:348), `CreateVisual` (:498) | `mgLoadMDSFile` (ps2/src/mg_dataset.cpp:646), `CreateFrameVisual` (:480) | Both walk the object records |
| Name flags | `SetFrameAttr` (ps2/src/dataset.cpp:198) | `mgSetFrameAttr` (ps2/src/mg_dataset.cpp:209) fed by `conv_new_text` (:44) | See below |
| Packet building | VIF packets written directly (ps2/src/frame.cpp, visualvu1.cpp) | `mgCDrawManager`, 0x80, sort table; `mgCDrawPrim`, 0x120 (mg_drawprim.hpp:131, :265, :273, :777) | DC2 batches by texture group |
| VU1 program ids | placeholder enum, value 6 used (vu1.hpp:14; frame.cpp:1274) | `mgVU_PROG_ID` 0 to 2 plus user table (mglib.hpp:42-50) | Different identifier spaces |
| Lights | four directional via `MGSetPLight` (ps2/src/mglib.cpp:741) | directional `mgSetLight` (mglib.hpp:866), point `mgSetPlight` (:917) | DC2 superset |
| Fog | `MGSetFogParm` (ps2/src/mglib.cpp:833) | `mgFOG_PARAM`, 0x30 (mg_drawenv.hpp:113, :143) and `mgSetFogParam` | |
| Projection | `MGSetRenderInfo` (ps2/src/mglib.cpp:625) | `mgSetRenderInfo` (mglib.hpp:785) | Both take a scale and clip range |

### Model containers (MDS and MDT)

Verified against one sample per game and against the DCExtractor MDS specification.

- MDS header (16 bytes): the magic `MDS\0` at +0, a word at +4, the object count at +8, and the first-object offset at +12, which is 0x10 in every sample. DC2's struct names +8 and +12 `object_num` and `object_ofs` (chronicletwo:ps2/include/mg_dataset.hpp:64-71). The word at +4 is 1 in most samples and 0 in one DC1 check file; the specification says it is always 1 (refs/DCExtractor/Specifications/Models/MDS.md). Its meaning is not established.
- Object record (0x70 bytes at +0x10): an index word, a size word of 0x70, a 32-byte name at +0x18, then the associated-block offset, the parent index and a 64-byte local matrix (refs/DCExtractor/Specifications/Models/MDS.md). DC2's `MDTOBJ_HEADER` is 0x70 bytes (chronicletwo:ps2/include/mg_dataset.hpp:79-88). The name at +0x18 is what both name parsers read.
- MDT block (magic `MDT\0`, header 0x40 bytes). The words, with DC1's and DC2's names:

| Offset | DC1 name (mdt.hpp) | DC2 name (mg_visual.hpp) | Sample value (one block per game) |
|---|---|---|---|
| +0x00 | magic (`unk_00[0]`) | `magic` | `MDT\0` |
| +0x04 | `unk_00[1]` | `header_size` | 0x40 |
| +0x08 | `size` (block size) | `unk_08` | 0xEE0 and 0xAF0; the next block begins exactly this many bytes later in both samples |
| +0x0C | `vertex_num` | `vertex_num` | 38 and 35 |
| +0x10 | `vertex_ofs` | `vertex_ofs` | 0x40 |
| +0x14 / +0x18 | `normal[0]` count / `normal[1]` offset | `normal_num` / `normal_ofs` | 44 / 0x940 and 35 / 0x5E0 |
| +0x1C / +0x20 | `colour_count` / `colour_ofs` | `colour_num` / `colour_ofs` | 0 / 0 and 0 / -1 (none) |
| +0x24 | `unk_24` | `faces_size` | face-section byte size |
| +0x28 | `mesh_ofs` | `faces_ofs` | face section offset |
| +0x2C / +0x30 | `uv[0]` count / `uv[1]` offset | `uv_num` / `uv_ofs` | 38 / 0xC10 and 34 / 0x810 |
| +0x34 / +0x38 | `uv[2]` (material count) / `info_ofs` | `material_num` / `material_ofs` | 1 / 0xE70 and 2 / 0xA30 |
| +0x3C | (not declared) | `unk_3c` | 0 |

The DC1 struct as declared ends at +0x3C, so its size is not asserted. The DCExtractor struct listing (refs/DCExtractor/Specifications/Models/MDS.md, lines 207-221) puts `meshDataSize` at +0x08 and `vertexCount` at +0x0C, the same offsets as both decompiled headers. Its prose list (lines 87-91) omits the size word, which is the likely source of a one-word offset mismatch. Both decompiled headers agree with the bytes.

- Face or mesh section: a 16-byte header of which word 1 is 0x10 and word 2 is the primitive or strip count, in both games (DC2 `MDT_FACES`, chronicletwo:ps2/include/mg_visual.hpp:95-101; DC1 port reads the count at word 2, chronicle:port/src/visualvu1.cpp:66-67). Then a series of primitive records of 12 bytes plus indices: type word, count word, material word (DC2 `FACES_ID`, mg_visual.hpp:110-116).
- Primitive type word: low byte is the GL primitive (3 = triangles, 4 = strip). DC2 adds flags to the same word: 0x08 flat and 0x10 no texture in the low byte, 0x100 colour and 0x200 no normal in the next byte (chronicletwo:ps2/include/mg_visual.hpp:25-35). Per-vertex index count is 3 plus one for colour, minus one for no normal, minus one for no texture (chronicletwo:ps2/src/mg_visual.cpp:475-482).
- Material record: diffuse, ambient, specular (16 bytes each), a float, then the name. DC1 names 44 bytes (chronicle:ps2/include/mdt.hpp:27-33). DC2 names 32 bytes and has two more fields (chronicletwo:ps2/include/mg_visual.hpp:77-87).

Observed in the full scan (all `MDT\0` blocks in each extraction, with header checks):

- DC1: 1,003 model blocks in the `.mds` files, all with a 0x40 header size. Of 7,708 primitive records walked with the stride rule, 7,705 had a zero type byte and zero padding. Style 4 (strip) accounted for 4,644 and style 3 (triangles) for 3,041. The few other values appear in a short tail, probably from blocks that the simple walker could not follow. Colour sections are absent (colour offset -1) in 963 of 1,003 blocks. Material names are at most 15 characters (995 materials).
- DC2: 92,672 blocks across the whole extraction, every one with a 0x40 header and a face header of 0x10, and every face chain walked to its end with the stride rule. Primitive type words: 0x04 (495,074), 0x104 (100,938), 0x03 (98,589), 0x103 (19,619), 0x213 (15,257), plus smaller counts with 0x200, 0x100 and 0x10 bits. Material names are at most 19 characters.

Inference from these counts: DC1 content uses only the two primitive styles without flags. DC2's flags are a superset. The DCExtractor specification's type-byte names (0 VertexNormalUV, 1 VertexNormalUVColor, 2 VertexNormal, 3 Vertex) do not match DC2's flag bits for type 2 (DC2 treats 0x200 as "no normal"). The DC2 bit reading is the one the walker confirms.

### Frame names and attribute codes

Both games store attribute codes in object names after `__`. DC2 converts them at load time in `conv_new_text`, and DC1 parses them in place. The parsers do not agree.

- DC1 `SetFrameAttr` reads the code letter, then a code body where needed (chronicle:ps2/src/dataset.cpp:234-300). Relevant entries: `c` sets `use_color` and an ambient colour (:234-240); `n` clears `clip_enable` (:242-244); `z` clears `depth_write` (:270-272); `f` clears `fog_enable`; `s` sets `program_option` to 1; `m` sets `eye_relative`; `b` then `Y` or `A` sets billboard to 2 or 3 (around :296-300); `t` sets `ambient_boost`; `o` sets `ignore_depth`; `a` takes a blend pair (PP, NN) or a hex alpha reference.
- DC2 `conv_new_text` copies the object name up to `__` (rewritten to `--`), then rewrites each bare letter into a letter plus a digit: `c` to `c0`, `n` to `n1`, `z` to `z0`, `f` to `f0`, `s` to `s1`, `m` to `m1`, `o` to `o1`, `v` to `v0`. `a` and `b` carry their following code character through (chronicletwo:ps2/src/mg_dataset.cpp:44-160). `mgSetFrameAttr` then parses the digits (chronicletwo:ps2/src/mg_dataset.cpp:267-277 for `c` and `n`, and the other cases beside them).
- Where the two agree: `z`, `f`, `s`, `m`, `o` and `t` have the same effect after conversion (z with digit 0 clears depth write; f0 clears fog; s1 sets program option; m1 sets program mode 1; o1 sets ignore-depth style test; t sets ambient boost). Inference from the code, not tested.
- Where they disagree:
  - `c`: DC1 means "use the frame colour as ambient light" (use_color). DC2's conversion produces `c0`, which parses as `no_light = true` (mg_dataset.cpp:267-271). The same letter means a different thing.
  - `n`: DC1 means "clip off" (clip_enable false). DC2's conversion produces `n1`, which parses as `clip_enable = true` (mg_dataset.cpp:273-277). The same letter has the opposite sense.
  - Billboards: DC1 `bY` is 2 and `bA` is 3 (dataset.cpp:296-300). DC2 `BY` is `MG_FRAME_BILLBOARD_Y` (2) and `BA` is `MG_FRAME_BILLBOARD_FULL` (1) (mg_dataset.cpp:362-369; mg_frame.hpp:32-37). In `GetBBoardMatrix` (mg_frame.cpp:817) bit 2 turns about the vertical axis, and the pitch branch under bit 1 recomputes the yaw axes too. So value 1 gives the full billboard, which is the same visual as DC1's 3. This is an inference from the code; the encodings differ.
- Data check: DC1 names carry these codes in practice. Scanning DC1 dungeon and character models, the most common suffixes were `__m`, `__a01a`, `__a01b`, `__bacz`, `__a01c` and `__c`. DC2 names carry the same convention (`__m`, `__C`, `__C1`, `__cf`, `__appz`), which is why the `--` search finds nothing in the extracted DC2 files. (unverified: the suffix counts and the `--` search result were not re-run.)

So a DC1 name with `c` or `n` loaded through DC2's loader turns on the opposite behaviour. A bare `c` in a DC2 name means `no_light` to DC2 after conversion, but DC1's parser reads the same byte as `use_color`.

### Textures and the registry

- Container: DC1 `IM2` (swizzled 8-bit pixels) and `IMG` (version 1) archives hold TIM2 pictures, read by `EnterIMGFile` (chronicle:ps2/src/texture.cpp:924-935). DC2 `GetIMGVersion` accepts `IMG`, `IM2` and `IM3` (chronicletwo:ps2/src/mg_texture.cpp:1190-1212) and computes entry offsets per version (:1262-1273). DC2's `IM3` entries carry the swizzle flag, a block number, a no-image flag, a size and a 64-bit clamp word (chronicletwo:ps2/src/mg_texture.cpp:1284-1294; the version enumerator is at mg_texture.hpp:56).
- Registry: DC1 has 72 `CTextureBlock`s and 196 `CTexture`s over a staging buffer and a VRAM allocator (chronicle:ps2/include/texture.hpp:91-101). DC2 has `mgCTextureBlock` lists (mg_texture.hpp:524-572), a 101-chain hash (:26), and VRAM accounting in whole GS pages (:26-31).
- PC keys: the DC1 port keys textures by TBP0 in a 14-bit space shared with palettes, with 0 and 0xFFF reserved for the frame buffers (chronicle:port/src/texture_port.hpp:16-36; chronicle:port/src/mglib_port.hpp:31-33). DC2's port looks textures up by `mgCTexture` or TEX0 through `mgPortSetTextureLookup` (chronicletwo:port/src/mglib_port.hpp:117-125), and frame grabs are registry entries found by TBP0 (chronicletwo:port/src/mglib.cpp:431). DC2 does not use the 0xFFF key in `mglib.cpp` or `mg_texture.cpp` (grep).
- Payloads: DC1's extraction carries the pixels. DC2's carries none: a full scan of the extracted tree found no `TIM2` header and no binary `IM2`, `IM3` or `IMG` header. Its `.map` files name the texture archives (for example `IMG "a01ia.img";`), and the archives sit inside pack entries whose data the scan did not find as IMG headers. The port's own comment says the published PACK has no texture payload (chronicletwo:port/src/dataread_pack.cpp:50-52), and converted textures come from the Kazarov texture catalog (kazarov:include/platform/texture_catalog.hpp:10-60).

### Draw flow

DC1 (PS2 path): `MGBeginFrame` opens the packet; `CFrameVu1::DrawVu1` walks the hierarchy, applies the frame attributes (fog, depth, alpha, billboard, ambient) to the GS shadows, then calls the visual's `DrawVu1`, which emits the VU block (chronicle:ps2/src/frame.cpp:1018, :1274; chronicle:ps2/src/visualvu1.cpp:705 for `CreateVUdataFromMDT`).

DC1 (PC path): `CFrameVu1::DrawVu1` is replaced (chronicle:port/src/frame_draw.cpp:111). `CreateVUdataFromMDT` builds a `Draw3DVisual` keyed by the block pointer in a side table (chronicle:port/src/visualvu1.cpp:23-24, :598). Each strip becomes a list of vertices with a texture run; a strip with style 4 is turned into a triangle list (:644). `Draw3DDrawVisual` draws with `gfx::DrawMesh` and fixed material constants (chronicle:port/src/visualvu1.cpp:554-558). Interpolation is keyed by the object pointer through `Draw3DIdentityScope` (chronicle:port/src/draw3d.hpp:91; chronicle:port/src/frame_draw.cpp:103).

DC2 (PS2 path): `mgCFrame::Draw` culls by bound and calls `mgCVisualMDT::Draw`, which emits a per-face packet with a VU1 batch sequence (chronicletwo:ps2/src/mg_frame.cpp:1416; chronicletwo:ps2/src/mg_visual.cpp:1061 for `CreateFacePacket`). Batches run the resident Vu_prog0, which is documented in `docs/vu1/prog0.md`.

DC2 (PC path): `mgCFrame::Draw` is replaced (chronicletwo:port/src/mg_frame.cpp:39). Each face becomes a `mgVisualFaceMesh` (chronicletwo:port/src/mg_visual_port.hpp:21). A face group is drawn with `mgPortDrawMeshProg0` and a `Prog0Constants` block that carries the model matrix, four light directions and colours, the material and the point lights (chronicletwo:port/src/mg_visual.cpp:310-316; kazarov:include/gfx/gfx.hpp:457-470). The render packet for the setup program is replaced with `CreateRenderInfoPacket` (chronicletwo:port/src/mg_visual.cpp:418).

### Cameras, lights, memory

- Camera: DC1's `CCamera::Step` moves an eye and a look-at point by a speed in steps, with a snap range (chronicle:ps2/src/camera.cpp:13; camera.hpp:24-29). DC2's `mgCCamera` has `pos_speed` and `ref_speed` with the same idea, and `mgCCameraFollow` circles a point at a distance and height (chronicletwo:ps2/include/mg_camera.hpp:27-60, :306-330). Both drive the view matrix that the render info holds (`MGSetViewMatrix`, chronicle:ps2/include/mglib.hpp:337; `mgSetViewMatrix`, chronicletwo:ps2/include/mglib.hpp:958).
- Lights: DC1 has four directional lights in `light_direction` and `light_color`. DC2 has the same directional set plus eight `mgLIGHT_INFO` sets (0x150 bytes each, chronicletwo:ps2/include/mg_drawenv.hpp:97-104) and point lights.
- Memory: DC1 hands out memory from `CDataAlloc2` bump blocks whose sizes are template constants (chronicle:ps2/include/dataalloc.hpp:22-60). DC2 uses `mgCMemory` with a heap and a stack mode (chronicletwo:ps2/include/mg_memory.hpp:44-120).

### Port seams

Both ports put a thin seam between the replaced `mg` functions and the gfx layer.

- DC1 seam: `MGPort*` helpers in `mglib_port.hpp` (65 lines; chronicle:port/src/mglib_port.hpp:1-65) and `PortTextureRef` and `PortCreateTexture` in `texture_port.hpp` (chronicle:port/src/texture_port.hpp:19-74).
- DC2 seam: `mgPort*` functions in `mglib_port.hpp` (218 lines; chronicletwo:port/src/mglib_port.hpp:1-218), including the interpolation scope (:184), the depth queries and the screenshot exit path.

Neither seam knows about the other game. A shared renderer would need a single render-info owner, a single texture key space and a single frame-target policy.

## Ixion hooks

1. **Name-flag translation at the DC2 loader boundary.** `CreateFrameVisual` calls `conv_new_text` on every object name (chronicletwo:ps2/src/mg_dataset.cpp:480-512). Ixion could run a per-source translation here for DC1 names: map DC1 `c` and `n` to the meanings DC1 had, and leave the rest. This is a small change that would address the sign problem for DC1 models loaded through the DC2 loader.
2. **DC1 model loading into the DC2 tree.** `mgLoadMDSFile` (chronicletwo:ps2/src/mg_dataset.cpp:646) builds the `mgCFrame` tree from the object records. A DC1 `.mds` has the same header and object layout (see How it works), so this loader is the natural entry point for DC1 meshes. The DC1 MDT blocks need the face check in hook 3 first.
3. **Face-type translation.** `mgVisualPortBuildFace` (chronicletwo:port/src/mg_visual_port.hpp:21) turns a `mgCFace` into a `mgVisualFaceMesh`. Ixion could add a DC1 path here that reads the same primitive records (every DC1 record in the sample has type word 3 or 4 with no flags, so the stride is 3, or 4 for the few blocks with colour data). The face builder is shared by every DC2 visual, so the DC1 path should be a separate function.
4. **Texture lookup across both registries.** `mgPortSetTextureLookup` (chronicletwo:port/src/mglib_port.hpp:125) lets one resolver answer both games' TEX0 lookups. DC1's `PortTextureFromTex0` (chronicle:port/src/texture_port.hpp:19-30) is the mirror. A combined resolver would have to keep the two TBP0 spaces apart; DC1 reserves 0 and 0xFFF, and DC2's frame grabs are registry entries.
5. **One render-info owner.** Both games write a global named `mgRenderInfo` with different types (chronicle:ps2/include/mglib.hpp:36; chronicletwo:ps2/include/mglib.hpp:365). Ixion needs one owner that both draw paths read, with the DC1 `RenderInfo` fields and the DC2 `mgRENDER_INFO` fields filled from the same camera. The matrices are `view`, `screen` and `view_scaled` on one side and `view`, `world_screen` and the clip boxes on the other.
6. **Choose the shader for DC1 meshes.** DC1's `Draw3DDrawVisual` uses `gfx::DrawMesh` (chronicle:port/src/visualvu1.cpp:558). DC2 uses `gfx::DrawMeshProg0` (chronicletwo:port/src/mg_visual.cpp:316). Moving DC1 onto the Prog0 path would plausibly give DC1 meshes the point-light and specular behaviour that DC2 uses (inference; not tried). That is a rendering decision, not a format one.
7. **Camera bridge.** DC1's `CCamera` owns a `CFrame` (chronicle:ps2/include/camera.hpp:19). DC2's `mgCCamera` is standalone (chronicletwo:ps2/include/mg_camera.hpp:27). An Ixion camera could drive both view matrices from one `mgCCamera`-style state, with the DC1 camera frame as a child that copies its world matrix.
8. **Shadows.** DC1's shadow volumes come from MDT shadow sections (chronicle:ps2/include/mdt.hpp:83-95; chronicle:ps2/src/dataset.cpp:581 `ArrangeShadowMDT`). DC2's come from faces (chronicletwo:ps2/src/mg_shadow.cpp:150-170). For a DC1 model in DC2, the DC2 path would simply ignore the DC1 shadow sections. Whether DC2 model blocks carry a shadow section was not checked; if they do not, `CVisualShadow` would need a face-derived path to draw them.
9. **Port layout checks.** Turn on a PC-side layout check for the DC1 structs. DC2's `PORT_RECORD_ASSERT` (chronicletwo:port/include/port.h:41) is the pattern. DC1's `STATIC_ASSERT` is empty on the port (chronicle:port/include/port.h:60), so `CFrameVu1 == 0x270` and `CCamera == 0x2C0` are not checked on PC today.
10. **Single declaration of CVisual.** Pick one of the two DC1 `CVisual`/`CVisualVu1` declarations (visual.hpp or visualvu1.hpp) for the merged build, and point each translation unit at it. The one that matches `visualvu1.cpp` is `visual.hpp`.

## Risks and blockers

- **Symbol collisions in a merged build.** Both games define `mgRenderInfo` (different types), `MG_PICKZ` (struct and `mgPickZBuff`, 16 versus 4 slots), `mgBackColor`, `mgClearBackFlag`, `mgDBuff`, `DmaCH1`, `DmaCH2`, `DmaCH8`, `VSyncField` (DC1 uses `VSyncField__2`), `StoreImage` (DC1 `void StoreImage()` at chronicle:ps2/src/mglib.cpp:270; DC2 `StoreImage(int)` at chronicletwo:port/src/mglib.cpp:1420), and `CObject` and `CObjectFrame` (different layouts). `Vu_prog0` and `Vu_progmain` are PS2 data in DC1's symbol configuration (chronicle:ps2/config/ntsc/main.symbols.txt:4027, :4527), and DC2's port defines them as one-element placeholders (chronicletwo:port/src/linknames.cpp:12-15).
- **DC1 declares two conflicting `CVisual` families.** The two headers differ in members and base classes (chronicle:ps2/include/visual.hpp:30-75 versus visualvu1.hpp:15-146). A translation unit that includes the wrong one gets the wrong layout for `vu_data` and `vu_size`. Virtual dispatch is also at risk, because the two headers declare different method sets.
- **DC1 layouts are not checked on PC.** See hook 9.
- **Name-flag polarity.** `n` and `c` mean different things across the two loaders, and DC2's converter adds digits that DC1 never wrote. Any cross-game name is a translation problem, not a copy.
- **Texture name width.** DC1 names materials in 44 bytes, DC2 in 32. Samples show at most 15 characters (DC1) and 19 characters (DC2), so no truncation was observed. A longer DC1 name would be cut by DC2's `strcpy` into a 32-byte field (chronicletwo:ps2/src/mg_dataset.cpp:1088).
- **DC2 textures need the catalog.** A DC2 texture has no payload in the extraction. Without `port_data/catalog.json` the DC2 texture path cannot run, so any Ixion build depends on a derived artefact. DC1 textures come straight from the IMG archives.
- **IM3 is not in DC1's loader.** `IM3` archives (0x40-byte entries) would be misread by DC1's `EnterIMGFile`, which only knows `IMG` and `IM2`.
- **Primitive flags are not in DC1's stride logic.** DC1's visual uses one stride for the whole visual (3, or 4 with colour), from `view.colour` (chronicle:port/src/visualvu1.cpp:64). A DC2 primitive with no-normal or no-texture flags would be read at the wrong stride. DC2's face-type flags are in the type word, not a per-visual setting.
- **Point lights and Prog0 features.** DC2 content that depends on point lights, environment mapping or the Prog0 specular path has no DC1 equivalent on the PC port. DC1 has no slot for a DC2 point-light set; its four directional slots are the only place one could go, and the result would be wrong (inference).
- **Kazarov pins differ.** DC1 pins `a0a5ff8` (port/ layout) and DC2 pins `3dc38ce` (src/ and include/ layout) (unverified). Their gfx headers have the same core types but DC2 adds `RecordingKind`, `Interp2D` and `Presentation2D`. Any shared build has to pick one pin.
- **Billboard codes.** Equal visuals, different numbers (DC1 3 versus DC2 1 for full). A translation table is needed.
- **Collision types.** `CCPoly` is asserted at 0x50 bytes in both games (chronicle:ps2/include/collision.hpp:120; chronicletwo:ps2/include/collision.hpp:79). That suggests the collision layer is shared, but its members were not compared here.

## Open questions

- Only 3 of 1,003 DC1 blocks carry colour data. Is DC1 vertex colour a rare path, or does the extraction hide colour data in blocks the scan did not reach?
- Are there DC1 primitive records with a non-zero type byte in the blocks the walker could not follow? The scan stopped early in 8 blocks out of 1,003 (about 7,700 records were walked); those blocks should be looked at before DC1 is treated as strictly flagless.
- Does the DCExtractor type-byte naming for type 2 (VertexNormal) reflect a different DC2 meaning from the one the walker confirms (0x200 as no normal)? The walk succeeded with DC2's stride rule over all DC2 blocks, which favours the code reading. A direct check against a known model would settle it.
- What does the word at MDS +4 do? It is 1 in most samples and 0 in one DC1 file. DCExtractor says it is always 1.
- Do DC2 names ever carry a bare `c` or `n` after `__`? The converter rewrites those to `c0` and `n1`, so DC2's own intent for them is only as good as the loader. A survey of DC2 names would show which bare letters occur and whether DC2's authors used them with the converted meaning.
- DC2's `mgCVisualPrim` and 2D sprite path are used heavily. Does DC1's `CSpriteTable` have a DC2 equivalent for its HUD and fade work, or does DC2 draw those through another unit?
- Which `RenderInfo` fields does DC1's `CFrameVu1::DrawVu1` write that DC2's Prog0 path reads from `mgRENDER_INFO`, and the reverse? The two are not field-compatible by name.
- The sizes of `CFrame` and `CFrameAttr` in DC1 are not asserted. Are they the same as the DC2 frame and attribute sizes once the vtable and pointer fields are counted? A layout check would answer it.
