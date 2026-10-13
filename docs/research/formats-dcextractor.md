# DCExtractor format reference for Dark Cloud and Dark Chronicle

## What this covers

A per-format reference for the file formats that DCExtractor documents for Dark Cloud 1 (Chronicle, "DC1") and Dark Cloud 2 (ChronicleTwo, "DC2"): archive indexes (DAT with HD2/HD3), pack containers (PAK and its family), image archives (IM2/IMG/IM3) and TIM2 textures, models (MDS, MOT, WGT, BBP), configuration text, and the data formats that DCExtractor does not cover.

Sources, in order of weight:

1. The C# loaders in the DCExtractor tree, the implementation the author shipped. Where a spec and the code disagree, the code is cited first.
2. The 24 Specifications notes, which the author marks as speculative.
3. Read-only scans of the two extracted trees on the research host (counts and byte checks, no game was launched and nothing was built). Scan results are labelled "observed". Anything reached only by reading code is labelled "code reading, not executed".
4. Game-side structs in chronicle and chronicletwo, and Kazarov's texture converter, where they bear on a format.

The DC1 tree is the dcdata extraction of the PAL prototype. The DC2 tree is the output of Kazarov's texture conversion, so its texture payloads are not disc data (see Key facts). Sibling notes `research/c1-data-loading.md` and `research/c2-data-loading.md` describe the trees and the runtime index.

## Key facts

- The spec set is 24 files under `refs/DCExtractor/Specifications/`: Configs 6, Data 3, Images 3, Models 4, Pack 8. Each header says "This format is speculative", and the README says the project is no longer maintained. Treat the C# as the stronger reference where they differ (`refs/DCExtractor/README.md`, Disclaimer).
- DC1 game index: `data.hd2` holds 5,425 named HD2 records, every one with `position == blockPosition * 0x800` and all unused words zero (observed). This matches the 5,425 named records in `research/c1-data-loading.md`. The file is a copy of the disc index made by dcdata, so it is the disc's layout but not the disc file itself.
- DC2 sound index: `sound/sound.hd3` holds 3,101 HD3 records of 16 bytes. Names are zero-terminated ASCII in the name table. 3,100 names are unique and one is duplicated, which agrees with `research/c2-data-loading.md` (observed).
- DC2 game index is not HD2/HD3. The game opens `cdrom0:\DATA.HD4` and reads 12-byte records of name offset, size and sector, with the count taken as the first u32 divided by 12 (`chronicletwo:ps2/src/dataread.cpp:520-535`, `chronicletwo:ps2/include/dataread.hpp:67-77`). No DCExtractor spec covers it. It appears to be the HD3 record without `blockSize` (inference).
- HD3 name bug (likely): `HD3.cs:134` calls `BinaryReader.ReadString()`, which reads a 7-bit length prefix. The only `ReadString` extension in the tree takes an int limit, so the no-argument call binds to the instance method. HD2 uses its own zero-terminated reader (`HD2.cs:146`). The DC2 sound HD3 names are zero-terminated (observed), so the first name byte ("0", 0x30) would be read as a length of 48. Code reading only; not executed.
- One pack entry layout covers the whole PAK family. Each entry is an 80-byte header: a 64-byte name, then four little-endian words at +64, +68, +72 and +76. The words are headerSize (always 0x50), fileLength, endOffset (relative to the entry start, so it locates the next entry), and a type word. Data starts at entry+80, and entries are 16-byte aligned (`PAK.cs:230`). The game's `PACK_ENTRY` names the same words as `offset` (0x50), `size` and `next` (`chronicle:ps2/src/dataread.cpp:43-48`). Observed: +64 is 0x50 in every entry the walks accepted, in both games.
- The walk rule holds across both games. Using the game's rule (offset from entry, next from entry, an empty name ends the table; the scan also stopped on a 0xFFFFFFFF size or a headerSize other than 0x50), DC2's 4,365 pack files parse with 2 failures, and every DC1 `.chr`, `.pak`, `.pac` and `.snd` walked parses (observed).
- Pack terminators vary. The spec describes an all-zero header. DC1 `fishing.pak` ends with a header whose size and endOffset are 0xFFFFFFFF (observed). `PAK.cs:211` and `:243` accept only `0 < fileLength < file length`.
- DCExtractor does not step by endOffset. For a zero-length entry it resumes at entry+80 (`PAK.cs:254`, `ReadHeader`); for a non-empty entry it reads fileLength bytes from entry+80 (`PAK.cs:268-269`, `ExtractFileData`) and resumes after them. Embedded `.img` entries have fileLength 0 with the real span in endOffset, so the walker steps through their payload 80 bytes at a time. This is only safe when the payload is zero.
- DC2 texture payloads are not in the extracted tree. All 3,719 embedded `.img` entries have fileLength 0 and all-zero payloads (unverified), and no TIM2, IM2 or IM3 magic appears in any DC2 file (observed; re-checked over the extracted tree, where a four-byte `IMG\0` match occurs once, inside a `.pss` movie, and is not an archive). Kazarov's transform zero-fills texture spans and zeroes the size word of each replaced pack member (`kazarov:src/rust/textures.rs:804-805, 846`). The zeros are therefore converter output (inference from the code, which matches the observation), not disc content.
- DC1 image archives use two magics with the same layout. 548 files start `IM2\0` and 230 start `IMG\0`. Both have a 16-byte header, 48-byte sub-entries with the TIM2 offset at +32, and TIM2 data at each offset (observed for all 778). `IMG.cs` accepts only the IM2 and IM3 magics and otherwise shows an error and returns (`IMG.cs:20-21, 297, 364`). The port's own test fixture writes `IMG` for one variant and `IM2` for "pre-swizzled 8-bit pixels" (`chronicle:port/src/tests/tex_fixture.hpp:85-86`). The meaning of the difference is inference from that comment.
- DC2 IM3: `IMG.cs:21` says DC2 uses IM3, but no IM2 or IM3 magic exists anywhere in the DC2 tree. IM3 on DC2 discs is unverified.
- TIM2 size field: the game names the picture word at +8 `image_size` and defines it as the total byte size of the image data (`chronicle:ps2/include/tim2.hpp:45`). DCExtractor's guard `imageDataSize == imageWidth * imageHeight` (`TM2.cs:244`) can only hold for 8-bit pictures, and in the sample it held for most of them. In a sample of 9,525 first pictures from DC1 TIM2s (standalone and embedded), 8-bit gave 8,575 with 8,371 passing the guard, and 4-bit (203), 32-bit (713) and 24-bit (34) gave zero passes (observed). Code reading only: DCExtractor would therefore produce no pixel data for most non-8-bit textures.
- The same guard decides whether the image and palette bytes are read at all (`TM2.cs:244-248`). When it fails, the stream does not advance past them, so later pictures in the same TIM2 would parse from the wrong offset. Every TIM2 in the sample has pictureCount 1 (observed), so this has not been hit yet.
- DCExtractor doubles 32-bit alpha for every game (`ColorHelpers.cs:85-94`), with the comment that DC2 stores alpha at half intensity. DC1 has not been checked.
- MDS mesh header: the spec and `MDS.cs` both give a 64-byte header, but the fields listed after the magic total 60 bytes. The four bytes at +60 are unread. They were 0 in one sample and 0xCDCDCDCD in others (observed).
- MDS polygon header: the spec says unknown1 is 0 or 0xBB000C. In 1,006 DC1 polygons sampled from loose files, 702 held 0xCDCDCDCD, 165 held 0xBB000C and 136 held 0 (observed). The 0xCDCDCDCD value is the usual debug fill for uninitialised memory, so it suggests the field is padding. DC2 pack-embedded polygons are almost all 0.
- MDS strip styles: DCExtractor handles only GL_TRIANGLES (3), GL_TRIANGLE_STRIP (4) and DC2_COLLISION_TRIANGLES (0x13). Any other style makes the whole model fail (`MDS.cs:398-404`, `DCTriangleStrip.cs:30`). Observed: 48 of about 2,760 DC1 models and 120 of 3,900 DC2 models contain another style. Styles 3 and 4 dominate both games. DC2 has 213 strips with style 0x13 and dozens of other values. DC1 has 6.
- MDS strip index types: DC1 loose models use only type 0 (VertexNormalUV, 7,704 strips). DC2 uses all four (type 0: 416,858; type 1: 9,329; type 2: 2,064; type 3: 148 strips). The walk of strip data ends exactly on `polygonBlockSize` for about 99% of DC2 meshes (observed).
- BBP: DCExtractor applies each bind matrix to the vertices of the container mesh named by `associatedMDTOffset` at load (`MDS.cs:212-234`). BBP sizes are multiples of 64 in both games (observed).
- MOT layout holds. Every embedded MOT (2,152 in DC1, 2,042 in DC2) and all 15 loose DC1 MOTs walk exactly, with 32-byte channel headers and 32-byte keyframes (observed).
- MOT `animationByteSize` equals 32 + 32 × keyframeCount in 843 of 858 loose-file channels. The other 15 hold 0 (observed).
- MOT channel types: DCExtractor's enum knows 0 (Rotation), 1 (Scale), 2 (Translation) and 40 (uniform scale) (`DCAnimation.cs:96-99`). Other types fall to `default`, which skips 16 bytes and discards the value (`MOT.cs:181-185`). Observed counts in embedded DC1 MOTs: type 0 = 44,207; 2 = 22,219; 12 = 13,525; 1 = 6,341; 40 = 4,816; 30 = 88; 31 = 88; 50 = 63; 33 = 60; 20 = 3. DC2: type 0 = 57,642; 2 = 16,897; 40 = 10,701; 1 = 9,577; 12 = 1,028; 50 = 12. Type 12 is about 98 percent of DC1's channels with types outside the enum, and it is the largest unhandled group in either game.
- Slicing semantics differ from the spec. DCExtractor reads only `info.cfg` in the MOT's directory (`MOT.cs:119`), and treats CFG start and end as 0-based, half-open indexes into the keyframe array (`DCAnimation.cs`, `Channel.Slice`). The spec says `<mds>.cfg` may also be used, that frames are 1-based and that ends are inclusive.
- WGT: the header is 32 bytes and each weight entry is 32 bytes, with the weight stored ×100 (`WGT.cs:115`). The spec's magic bytes AC E6 37 01 and B0 F0 FC 77 are present at +24 and +28 in 1,002 of 1,663 DC2 entries (observed). In DC1 the same slots hold address-like values (for example 0x0135E888, which looks like a PS2 RAM address), and none of the 1,309 sampled entries carries the DC2 bytes. Reading this as "not a magic word" for DC1 is inference.
- `.pac` is not in DCExtractor's PAK type list (`DCExtractor.cs:145-154`), but DC1 has 312 and DC2 has 226 `.pac` files, and all of them walk with the PAK rule (observed). Unpack All therefore skips them.
- DC2 `.mpk` files hold only `.pcp` entries (222 top-level entries in the scan), and `.ipk` files hold only `.img` entries, all zero-filled (observed).
- Text configs and effects are not parsed by DCExtractor. `CLO` files start with a `SIZE` line, `EFF` samples are command scripts using `SIZE`, `NUM`, `COUNT` and `REPEAT`, and `EM` samples add `BUFFER_SIZE` and `EFFECT_START`, and DC2's map files (`.map`, `.mpl`, `.mpp`, `.pcl`, `.ptl`) are text that names the packs and models a map uses (observed in samples).

## How it works

### Shared formats and differences

| Format | DC1 (Chronicle) | DC2 (ChronicleTwo) | Evidence |
|---|---|---|---|
| DAT with HD2 | Game index `data.hd2`, 5,425 records, ISO-aligned | Not the game index; DC2's index is `DATA.HD4` (12-byte records) | Specs; `chronicletwo:ps2/include/dataread.hpp:67-77`; observed |
| HD3 | Not seen in the tree | `sound.hd3`, 16-byte records, 3,101 entries | Observed; `HD3.cs` |
| PAK family (80-byte entries) | `.chr` 1,116; `.pak` 540; `.pac` 312; `.snd` 218 | `.chr` 2,782; `.snd` 841; `.pak` 15; `.pac` 226; `.mpk` 210; `.ipk` 210; `.sky` 56; `.efp` 23 | Observed |
| IM2 image archive | 548 `IM2\0` plus 230 `IMG\0` | None present; payloads zero-filled by conversion | Observed; `kazarov:src/rust/textures.rs` |
| IM3 image archive | Not seen | Claimed by DCExtractor; not present in the tree | `IMG.cs:21` |
| TIM2 texture | Standalone (119, all version 4, one picture) and embedded | None present | Observed |
| MDS model | 412 loose and embedded; styles 3/4 dominate | About 3,900 models; style 0x13 and many more styles; all four index types | Observed |
| MOT motion | Channel types 0, 1, 2, 12, 20, 30, 31, 33, 40, 50 | Types 0, 1, 2, 12, 40, 50 | Observed |
| WGT weights | 1,309 entries; magic slots hold address-like values | 1,663 entries; magic bytes in 1,002 | Observed |
| BBP bind matrices | 1,353 entries | 2,133 entries | Observed |
| info.cfg (KEY_START) | Present | Present; FRAME_START appears in 52 files | Observed (string search) |

### Containers: DAT, HD2, HD3, DATA.HD4

- A DAT is a flat run of file bodies with no headers. HD2 and HD3 are its index. `DAT.cs` writes each entry from `position` (HD2) or `blockPosition * 0x800` (HD3) for `size` bytes (`DAT.cs:281-282`, `HD3.cs` `position` property).
- HD2 entries are 32 bytes: nameOffset, three unused words, position, size, blockPosition, blockSize. The list ends at a record whose four position/size fields are zero (`HD2.cs`, `isEmpty`). Names are read from the offset as zero-terminated text.
- HD3 entries are 16 bytes: nameOffset, size, blockPosition, blockSize. The list ends when size, blockPosition and blockSize are all zero (`HD3.cs`, `isEmpty`). See the name bug in Key facts.
- DATA.HD4 (DC2, game side) is 12 bytes per record: name offset, size, sector (2,048-byte units, unverified). It is the HD3 layout without blockSize (inference from `dataread.hpp:67-77`, not decoded from a disc).
- DCExtractor does not repack. It cannot read DC2's `DATA.HD4` index, because it looks only for `.hd2` and `.hd3`.

### Pack family (PAK, CHR, IPK, MPK, PCP, EFP, SND, SKY, plus PAC)

- Layout: `name[64]`, `headerSize` (0x50), `fileLength`, `endOffset`, `type`, then the file body. Next header at entry + endOffset (the game's `next`), 16-byte aligned (`PAK.cs:230`); DCExtractor steps by fileLength instead (see Key facts). Observed alignment matches the endOffset values in every walked pack.
- `type` is not a simple enum. The same pack type has many values (for example, DC1 `.chr` entries show 0x12EDD4, 0x1 and 0xC). Its meaning is unknown (open question).
- Pack contents (observed entry extensions): DC1 `.chr` is `mot` 1,856, `mds` 1,688, `img` 1,308, `cfg` 1,265, `bbp` 1,177, `wgt` 1,151, `chr` 113, `clo` 61. DC2 `.chr` is `mds` 3,359, `img` 2,972, `cfg` 2,763, `bbp` 2,133, `mot` 2,042, `wgt` 1,791. DC1 `.snd` holds `bd` 553, `hd` 553, `sq` 250, `txt` 218 and `cfg` 145. DC2 `.snd` holds `mid` 2,147, `bd` 841, `hd` 841, `cfg` 841, `vol` 841 and `sq` 435.
- DC2 `.mpk` nests `.pcp` packs (222 entries). Each `.pcp` appears to hold one map's models and images (inference from entry names; the nested contents were not walked). DC2 `.ipk` packs hold only zero-filled `.img` entries (in this tree).
- Zero-length entries: DC1 `.chr` 18, `.pak` 14, `.pac` 6, `.snd` 164. DC2 `.chr` 2,990, `.ipk` 257, `.sky` 224, `.pac` 345 (observed).

### Images: IM2, IM3 and TIM2

- IM2/IMG archive: 16-byte header (magic, imageCount, two zero words), then imageCount 48-byte entries (32-byte name, offset to the TIM2, three zero words), then the TIM2 bodies (`IMG.cs`; `IMG (Version 2).md`). The DC1 variant `IMG\0` has the same layout (observed).
- IM3 archive (as DCExtractor reads it): 16-byte header with a first-header offset (read but not used), then 64-byte entries. The C# names the spec's `headerSize` slot `imageChunkSize`, and its `imageSize` slot lines up with the spec (`IMG.cs:344-354`). Payloads are assumed to follow each other with no padding. Unverified.
- TIM2 file: 16-byte header (magic `TIM2`, version, format, 16-bit picture count, 8 bytes unused). Each picture has a 48-byte header (totalSize, paletteSize, imageDataSize, headerSize, colorEntries, imageFormat, mipmapCount, CLUT format, a depth byte, width, height, GS registers and TEX registers), then `headerSize - 48` bytes of user data, then the pixels, then the palette (`TM2.cs`, `ReadTIM2Picture`). Depth byte: 1 = 16-bit, 2 = 24-bit, 3 = 32-bit, 4 = 4-bit indexed, 5 = 8-bit indexed (`chronicle:ps2/include/tim2.hpp:18-22` agrees).
- Pixel size: `imageDataSize` is a byte count (for 4-bit it is width × height / 2 in the sample, observed for `mt01.tm2`, 384 × 128, 4-bit, 16-entry RGBA32 palette, file size = 16 + 48 + 24,576 + 64). The guard in `TM2.cs:244` is therefore wrong for everything except 8-bit.
- Palette: `isLinearPalette` is bit 7 of the CLUT byte. Otherwise the palette is interleaved in 8-entry stripes (`TIM2Picture.cs`, `GetPalette`). Pixels for 4-bit and 8-bit are unswizzled with the matrices in the spec (`Swizzle.cs`), and the rows are then flipped (`TIM2Picture.cs:228`).
- Colour: 16-bit is ABGR1555 with `a` as bit 15 (`ColorHelpers.cs`). 32-bit alpha is doubled, as noted above.

### Models: MDS, MOT, WGT, BBP

- MDS: magic `MDS\0`, a version word (1 in the spec, 0 in one sampled file), boneCount, boneOffset (16). Each bone is 112 bytes: index, size, 32-byte name, associatedMDTOffset, parentIndex, and a 4x4 float matrix (`MDS.cs:137-160`). The loader does not check the magic (`MDS.cs:137-138`).
- Meshes are found by scanning for `MDT\0`. A mesh holds a 64-byte header (magic, headerSize, meshDataSize, then offset/count pairs for vertices, normals, colours, polygons, UVs and materials), then the data arrays (`MDS.cs`, `LoadMesh`). Vertices, normals, UVs and colours are 16-byte float4s. Materials are 96 bytes: three colours, a float, and a 44-byte texture name.
- Polygons: a 16-byte polygon header (unknown1, unknown2 = 0x10, stripCount, zero), then strips. A strip header is 12 bytes: style byte, type byte, two zero bytes, indexCount, materialIndex. Index size depends on type: 12, 16, 8 or 4 bytes (`MDS.cs`, `ReadIndex`).
- Style 0x13 forces type to Vertex (`MDS.cs`, `eType`). Triangles are implied: indexCount / 3 for lists and indexCount - 2 for strips.
- Bones bind to meshes through `associatedMDTOffset`, which is the file offset of the mesh's `MDT\0`. When a BBP file sits next to the MDS and a bone's association matches a mesh, the BBP transform is applied (`MDS.cs:212-234`).
- MOT: a sequence of channels. Each channel is 32 bytes (boneIndex, unused, type, headerSize = 32, keyframeCount, animationByteSize, two unused words), followed by keyframes of 32 bytes (index, 12 unused bytes, 16 value bytes). Rotations are read as WXYZ quaternions and stored XYZW (`MOT.cs`, `ReadQuaternionWXYZ`). Keyframe indexes are 1-based in the file (`MOT.cs:155`).
- Channels for the same bone are merged after expanding to a common length, and missing keyframes are linearly interpolated (`DCAnimation.cs`, `CombineChannels`, `Expand`). This is DCExtractor's choice, not a property of the file.
- WGT: 32-byte bone headers (meshBoneIndex, boneIndex, unknown, headerSize = 32, weightCount, nextHeaderOffset, two magic-like words), then weightCount 32-byte entries (vertex index, padding, float weight ×100, padding). Observed: the walk is exact in every sampled file.
- BBP: a flat list of 64-byte float matrices, one per bone, in bone order (`BBP.cs`). Observed: sizes are multiples of 64.

### Configs and text

- CFG (`info.cfg`): a text command script. DCExtractor parses only `KEY_START;`, `KEY ...;` and `KEY_END;` lines for animation slices (`MOT.cs`, `LoadSlicesFromCFG`). The DC2 dialect also uses FRAME_START, VERTEX_L and MODEL, which DCExtractor does not parse (per `research/c1-data-loading.md`; FRAME_START string counts observed).
- BAK and LST: lists of ASCII strings, unparsed by DCExtractor.
- CLO (cloth), EFF and EM (effects): text command scripts, unparsed. Command names are the only documentation (samples observed).
- DC2 `.map`, `.mpl`, `.mpp`, `.pcl`, `.ptl`, `.gpi`, `.mapb` and `.lst`: map descriptions in text (or a small binary for `.mapb`). A `.map` names the IMG and PCP packs and the MDS pieces a map uses (observed).

### Formats not covered by DCExtractor (observed in the trees)

| Extension | DC1 count | DC2 count | Notes |
|---|---|---|---|
| `.stb` | 285 | 1,356 | Starts `STB\0` (observed); DC1 `test.stb` is a `STB\0` table |
| `.mes` | 752 | 70 | Message text; not parsed by DCExtractor |
| `.scn` | 204 | 0 | Not decoded; an extensionless DC1 file starts with `SCN\0` (observed) |
| `.sne` | 129 | 0 | Not identified |
| `.sq` | 21 | 435 (in snd) | Sequence data; not identified |
| `.txt` | 18 | 1,104 | Shift-JIS-looking bytes (observed); not decoded |
| `.gpi` | 0 | 38 | Text, `EDIT_PARTS_NUM` lines (observed) |
| `.pss` | 0 | 9 | Movie (MPEG-PS style start code observed) |
| `.ico` | 0 | 3 | Windows icon |
| `.edt` | 6+ | 0 | Editor data (`gdata0.edt`) |
| `.bd`, `.hd` in snd packs | 9 (loose) | 841 (in snd) | Sound bank and header pairs |
| `.hed`, `.div` | 0 | 1 each | Not identified |

## Ixion hooks

- Pack reader (one reader for both games): `chronicle:port/src/dataread.cpp` `GetPackFile` (lines 314-336) already walks the entry-relative layout, following `next` and reading `offset` and `size`. Both games use the same 80-byte entry (Key facts), and the DC2 pack files walked (about 4,365, 2 failures) support pointing that reader at DC2 packs. Confirm the two failures before relying on it.
- DC2 index: a DATA.HD4 reader (12-byte records) belongs next to the game's index code, using `chronicletwo:ps2/src/dataread.cpp:520-550` as the reference. Do not reuse DCExtractor's HD2/HD3 path.
- TIM2 decode: size pixel data from the picture's `image_size` as bytes (`chronicle:ps2/include/tim2.hpp:45`) and handle all five image types (`tim2.hpp:18-22`). Do not copy the `TM2.cs:244` guard. A test over the observed 4-bit sample (`mt01.tm2`) would confirm the size rule before wiring it in.
- IMG archive: accept the `IMG\0` magic in addition to IM2 for DC1 (230 files), and decide whether an `IMG` archive's 8-bit pixels need unswizzling, using the fixture's note (`chronicle:port/src/tests/tex_fixture.hpp:85-86`) as the starting question.
- MDS loader: use the game's own mesh path rather than DCExtractor's all-or-nothing style check (`MDS.cs:398-404`). Keep style 0x13 collision strips separate. Flag the 48 DC1 and 120 DC2 models with other styles for a manual look.
- MOT animation: keep the raw channels of unknown type (12, 20, 30, 31, 33, 50) instead of dropping them. Decode type 12 only after comparing against the game's animation reader. Type 12 is 13,525 DC1 channels and 1,028 DC2 channels.
- BBP: apply the bind matrix to container meshes at load, as DCExtractor does (`MDS.cs:212-234`), but on the Ixion side.
- Slicing: take the slice frame convention (0- or 1-based, inclusive or not) from the game's `info.cfg` reader, not from DCExtractor or the spec. Test with one character whose clip boundaries are known.
- DC2 textures: take them from Kazarov's catalog and PNG overlays, not from the extracted tree's `.img` entries (see Risks).
- Verification: the scans used here (walk rules, magic counts, strip walks) could become a regression script over both trees. That is a suggestion only, not implemented.

## Risks and blockers

- Nothing was executed. Claims about DCExtractor's output (the TIM2 guard, the HD3 name read, the MDS style rejection, the MOT default branch) come from reading the code plus byte samples. Running DCExtractor on a few files would confirm them.
- The DC2 tree cannot answer any texture question. Its IMG payloads were zeroed by conversion, so DC2 texture formats (IM3 or otherwise) need the disc image or the `DATA.DAT` file, which are not in the repository. `rip/` is git-ignored, so a per-host copy is needed.
- DCExtractor is unmaintained and its specs are speculative. Where the spec and the C# disagree (IM2 versus IM3 application, MDS header size, MOT slice convention, CFG file names, polygon unknown1 values), neither is confirmed against the game's code. The game-side code (chronicle and chronicletwo) is the arbiter.
- The 4,365-file pack walk is a structural check. It does not prove that each entry's contents are right, only that the walk ends at valid headers.
- Pack `type`, MDS `+60`, MDS unknown1, WGT magic-like words and the MOT `animationByteSize` anomaly all look like padding or leftovers, but no source confirms that. Treat them as unknown.
- The DC1 alpha doubling is untested. If DC1 textures are drawn with it, they will look wrong.
- Several DC2 text formats (`.mpl`, `.mpp`, `.lst`) embed build-machine paths. Do not publish them or reuse them as data.

## Open questions

- What is MOT channel type 12 (and 20, 30, 31, 33, 50)? It is the largest unhandled group in DC1, so this decides whether DCExtractor's animations are usable at all.
- Do DC2 disc archives contain IM3 texture archives, and what is the meaning of the 64-byte entry fields (the spec and the C# name them differently)?
- Is the pack `type` word an enum, a hash, or a per-pack flag? The same pack type has many values.
- Is the `0xCDCDCDCD` value in MDS polygon and mesh headers a build artifact of the authoring tool, and does the game ever read those words?
- Does the DC1 `IMG\0` variant differ from `IM2\0` in pixel storage, as the port's fixture comment implies? Which games or assets use which?
- Does DC1 TIM2 storage need the alpha doubling? Compare the game's texture decode with the sample alpha values.
- Which frame convention does the game use for `info.cfg` slices (`KEY` start and end), and does it read `info.cfg` or `<mds>.cfg`?
- Does DC2's `DATA.HD4` match HD3 without the block size field? Check against the disc.
- Are DC2 `.pcp` packs nested in `.mpk` always PAK-layout? The scan walked the `.mpk` level and not each `.pcp` inside it.
- Do the two DC2 pack walk failures (one `.chr`, one `.pcp`) hide a different layout?
