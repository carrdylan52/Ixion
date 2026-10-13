# Community references survey for Ixion

## What this covers

A survey of the community repositories under `refs/` (listed in `docs/SOURCES.md`) and the pulled notes under `docs/`, read for what each offers Ixion: format parsers and importers or exporters, runtime memory maps, cheat tables, mods, and engine reimplementations. Each repo has its own subsection in "How it works" with what it is, what Ixion can reuse, and its licence. The survey is read-only. Nothing was built or run. Where a claim could be checked against the decompilation source trees or the extracted PAL data, the check is noted. Community memory addresses are PCSX2 EE-RAM addresses from NTSC-U builds (SCUS-97111 and SCUS-97213). They are not the PC port's addresses, and they have not been validated against the PAL discs.

## Key facts

- The two PS2 decompilation trees define the main-loop mode numbers that community code also uses. Chronicle `GameMode` puts EDIT at 2 and DUNGEON at 3 (chronicle:ps2/include/main.hpp:16-20). Community DC1 code agrees (refs/DarkCloud-Reforged/src/game/addresses.py:6-12, TOWN=2, DUNGEON=3). ChronicleTwo `MainLoopMode` puts LOOP_EDIT at 1 and LOOP_DUNGEON at 2 (chronicletwo:ps2/include/mainloop.hpp:33-34).
- The DC2 Reforged address file has a wrong comment. Line 21 of refs/DarkCloud-Two-Reforged/src/game/addresses.py says "1=dungeon, 2=town". Its own `Mode` class (lines 12-13) and the ChronicleTwo enum both say 1 is town (edit) and 2 is dungeon. Trust the enum, not the comment.
- DC1 town-ally switching is done by writing a character file path string into game memory and reloading. Enhanced writes the path at `chrFileLocation` 0x2029AA08 (refs/DarkCloud-Enhanced/Dark Cloud Improved Version/Addresses.cs:382, TownCharacter.cs:189-296). Reforged does the same (refs/DarkCloud-Reforged/src/mods/allyswitch.py:15-21, 65-126). All five ally paths (`gedit/e01/chara/c04pcat.chr` and the rest) exist in the PAL DC1 extract.
- The config-file address for that swap is inconsistent across community code. Enhanced `Addresses.cs:381` gives `chrConfigFileLocation` = 0x2029A9F0. Reforged `game/addresses.py:176` gives `CHR_CONFIG_FILE_LOC` = 0x2029A9F0, but Reforged `mods/allyswitch.py:26` uses 0x2029AA18 and says it is "from Addresses.chrConfigFileLocation". Treat 0x2029A9F0 as the value that matches the Enhanced source, and verify before use.
- DC1 element item IDs are fixed in the Reforged item table: fire=81, ice=82, thunder=83, wind=84, holy=85 (refs/DarkCloud-Reforged/src/data/items.py:3-7). The DC1 cheat table lists ten anti-monster fields: Dragon, Undead, Marine, Rock, Plant, Beast, Sky, Metal, Mimic, Mage (docs/cheat-tables/Dark Cloud (fearlessrevolution).CT). This matches the "ten monster families" in DESIGN section 4.5.
- Gilda: Reforged reads a 16-bit unsigned value at 0x21CDD892 (refs/DarkCloud-Reforged/src/game/game_state.py:212, core/memory.py:59-60) and its cheat writes 65535 (mods/cheatcodes.py:103). This supports the 65,535 clamp in DESIGN 4.3. The signedness concern in DESIGN 4.3 is not resolved by these sources, because the read is unsigned and nothing shows the game's own type.
- DC2 invention recipes are available as data: 136 entries of the form (result item ID, two or three idea IDs), in refs/DarkCloud-Two-Reforged/src/data/inventions.py. Idea names (294 entries) are in src/data/idea_names.py. DC2 item names (about 70 visible in src/data/items.py) come from CommonData.
- DC2 script opcodes are documented in two independent places. The Reforged SB2 disassembler table (refs/DarkCloud-Two-Reforged/scripts/decompile_script.py, OPCODES) and OpenCloud's enum (refs/OpenCloud/code/script/bytecode.h:17-47) agree on the numbers from 0x0F to 0x1E (return, jump, branch, call, print, extended function, yield, and, or, not, sin, cos). They disagree on the terminator. The Reforged table calls 0x1B END, while OpenCloud's `exit` is 27 (0x1B) and its `end` is 0.
- The DC1 STB bytecode has a 31-opcode jump table at vaddr 0x0029FB80 and 464 external functions, and the DCFM interpreter `StbVm.cpp` is a port of the engine's CRunScript (docs/DC_STB_FORMAT.md:130, docs/DC_STB_EXTERNALS.md:1-10, refs/DarkCloud-Toolkit/src/Archives/StbVm.h:5). Every address there is SCUS_971.11, which is NTSC-U.
- DCFM (refs/DarkCloud-Toolkit) reads the DC1 game tables from the boot executable at runtime and does not ship them (docs/GAME_DATA.md:1-40). That pattern fits Ixion's rule that game data stays out of the repo.
- MDS writer status conflicts across DCFM docs. docs/FILE_FORMATS.md:95 and README.md:393 say there is no MDS writer. docs/TOOLING_INDEX.md:59-60 describes a parser and writer with a claimed byte-identical round trip over 4,782 models. The module header of app/fmt/mds-format.mjs describes `parse()` and `write()` and a round-trip requirement, but does not state the 4,782 count. The C++ product is read-only; the JS tooling has `write()`. Verify before relying on either.
- The Blender add-on's README says it imports and exports DC1 `.chr` files (refs/Blender-Tools-For-Dark-Cloud/README.md:2). The code has only `BlenderIO/Import.py`. `to_file`, `to_binary` and `Model.to_chr` all raise `NotImplementedError` (filetypes/MDS/MDSInterface.py:18-19, 28-29; filetypes/CHR/Model.py:29-30).
- The DC2 hash list in `dark-chronicle-reverse-engineering` (`file_hashes.csv`) matches the local PAL DC2 extract on `edit.cfg` and `geo0.cfg`, but it is not a clean match overall. In a 150-row sample spread across the list, 81 files matched by MD5, 49 differed, and 20 were not found under the mapped path (unverified: the sampling method is not recorded, so the counts were not reproduced). The list therefore cannot yet serve as an integrity check for the PAL extract (see Open questions).
- Licences are mixed. Four repos are copyleft (DCExtractor GPL-3.0, Xeeynamo DarkCloud GPL-2.0, Rainbow GPL-2.0, and the GPL-3.0-or-later `kConvertPy` exception inside DCFM). Eight repos have no licence file at all. Treat those as specification sources only, and do not copy code from them.

## How it works

### Survey table

| Repo (refs/) | Licence | What it is | Ixion value |
|---|---|---|---|
| DarkCloud-Toolkit (DCFM) | MIT, with GPL exception and zlib port | C++ file manager, decoders and Studio viewer for DC1 | High: decoders, STB VM, georama and town config readers |
| DarkCloud-Enhanced | BSD-2-Clause | C# external mod for DC1 on PCSX2 | High: ally swap, address list, item table reads |
| DarkCloud-Reforged | none | Python PINE mod for DC1 | High: address map, item and weapon tables, ally swap |
| DarkCloud-Two-Reforged | none (alpha) | Python PINE mod for DC2 | High for DC2: addresses, recipes, SB2 disassembler |
| OpenCloud | MIT | C++ reimplementation of DC2, dormant | Medium: SB2 analyzer, loop structure, pak header |
| dark-chronicle-reverse-engineering | MIT | DC2 archive notes, hash list, ISO explorer, CT | High for DC2 archive and PAL verification |
| SB2-File-Parser | MIT | C# SB2 to JSON | Medium: SB2 header reference |
| DarkCloud (Xeeynamo) | GPL-2.0 | WhiteCloud and LightCloud DAT and HD2/HD3 tools | Medium: archive reference |
| DCExtractor | GPL-3.0 | C# converter, 24 format specs | High as spec only, no repack |
| Blender-Tools-For-Dark-Cloud | MIT | Blender importer for DC1 `.chr` | Medium: import path only |
| noesis-mds-plugin | none | Noesis importer for `.mds`, `.chr`, `.img` | Low: an alternative viewer |
| paktools | none | Java pack extract and rebuild (DC1 and DC2 packs) | Medium: rebuild reference |
| HD6Tools | none | Java HD6 archive tools (later Level-5) | Low |
| Dragon-Quest-8-Tools | none | Python PAK family tools for DQ8 | Low to medium: pack family |
| Rainbow | GPL-2.0 | C# TIM2 and texture converter | Low to medium: texture reference |
| cwdemangle, dc2-demangler | MIT and Apache-2.0 (cwdemangle); MIT (dc2-demangler) | CodeWarrior demangler; Binary Ninja plugin (checkout has only the LICENSE) | Medium for symbol work |
| ghidra-emotionengine-reloaded | Apache-2.0 | Ghidra PS2 extension with save-state import | Medium: analysis tooling |
| ps2_bn | none | Binary Ninja PS2 architecture | Low |
| PS2DarkChronicle | MIT (per README) | Unity 6 PS2-look prototype | Low: rendering recipe |
| DarkCloud-MechanicsGuide | BSD-2-Clause | SvelteKit mechanics site, fishing simulator | Low to medium: fishing formulas |
| project_toan | none | Unity DC1 fan remake, large asset set | Low: reference only, do not ingest assets |
| docs/cheat-tables | unknown (community) | Five Cheat Engine tables for DC1 and DC2 | Medium: field names, offsets as pointer chains |

### DarkCloud-Toolkit (DCFM), `refs/DarkCloud-Toolkit`

- **What it is.** A Windows C++ application for DC1 (SCUS_971.11, NTSC-U). It has a file manager over ISO, HED/DAT and nested packs, model and texture viewers, a MIPS and VU disassembler, and a Studio 3D viewer. Studio includes a "Play" mode that walks a village or dungeon floor. Source is under `src/` (about 180 files under `src/Archives/`). JS tooling is under `app/`. The docs are the most detailed description of DC1 formats available.
- **What Ixion can reuse (as spec).**
  - Model and rig: `src/Archives/MdsModel.cpp`, `app/fmt/mds-format.mjs` (MDS0 container, MDT sections, polygon grammars). See docs/DC_FORMAT_RIG.md.
  - Script VM: `src/Archives/StbVm.cpp` (port of CRunScript), `StbExt*.cpp` (464 externals across edit, dungeon and monster tables; docs/DC_STB_EXTERNALS.md). docs/DC_STB_FORMAT.md gives the header, funcdata, opcode table and message block.
  - Georama and town config: `EdtFile.cpp` (`.edt` layout: count, size, then per-part id, rotation and position), `DcVillageCfg.cpp`, `DcDungeonCfg.cpp`, `DcGeoramaEdit.cpp`, `PtsArchive.cpp` (furniture and trigger records), docs/FILE_FORMATS.md.
  - Game loop and clock: docs/DC_GAMEPLAY_RUNTIME.md describes the 59.9401 Hz tick, the world/host split, and the disclosed gaps (for example, talk does not fire in Norune, MapNo 0).
  - Runtime table extraction: docs/GAME_DATA.md describes reading 54 named tables from the boot ELF, with a size check and a per-disc cache.
- **Licence.** MIT for the repo (LICENSE). The exceptions are documented in THIRD_PARTY_NOTICES.md. `kConvertPy` in `src/DcBlender.cpp` is GPL-3.0-or-later and is excluded from the MIT grant. A zlib-licensed SESQ walker is ported from VGMTrans into `src/Ps2AudioPreview.cpp` and carries attribution. Do not copy these two without handling their licences. Reading the specification is fine.

### DarkCloud-Enhanced, `refs/DarkCloud-Enhanced`

- **What it is.** A C# Windows executable that patches PCSX2's EE memory from outside the process. It is the source of much DC1 address knowledge. `Addresses.cs` holds about 145 `public const int` addresses (mode, gilda, map, position, dungeon messages, chests, circles, items).
- **What Ixion can reuse.**
  - Ally swap: `TownCharacter.cs` writes the `.chr` path and `info.cfg` name into fixed slots and triggers a reload (lines 189-296). This is the only town-side character swap mechanism in the community code.
  - Dungeon item tables: `Dayuppy.cs` reads item tables by fixed size from memory (for example, `ItemTbl0` at 252 bytes and `ItemTbl2` at 304 bytes, lines 22-30).
  - Ruby texture replacements: `Resources/RubyMemeFix/` (five element textures). The names match the DC1 element order.
- **Licence.** BSD-2-Clause (LICENSE). Code reuse is permitted with the notice retained.
- **Caution.** The repo bundles `Resources/pcsx2_offsetreader.dll`, a binary that exposes `GetEEMem`. Do not reuse binaries from this repo without checking them.

### DarkCloud-Reforged, `refs/DarkCloud-Reforged`

- **What it is.** A Python and tkinter mod for DC1 that talks to PCSX2 over PINE IPC (`src/core/pine_ipc.py`, TCP port 28011, opcodes read8 to read64, write8 to write64, status). It is a cross-platform port of DarkCloud-Enhanced.
- **What Ixion can reuse.**
  - Address map: `src/game/addresses.py` (about 270 lines). It has the game mode (`MODE` 0x202A2534), town and dungeon state, player position, shop, daily-shop, side-quest flags, chest, and the dungeon and town name tables (`DUNGEON_NAMES` 0 to 6; `TOWN_NAMES`). Note that `TOWN_NAMES` maps both area 5 and area 23 to "Yellow Drops". Check that before using the table.
  - Data tables: `src/data/items.py` (item IDs), `weapons.py` (base table addresses and per-character offsets), `enemies.py` (enemy offsets and type IDs), `dialogues.py` (about 890 lines of NPC lines per ally), `customchests.py`, `miniboss.py`, `rubyorbs.py`, `georama.py`, `dailyshopitem.py`.
  - Ally swap: `src/mods/allyswitch.py` (the `CHR_PATHS` table at lines 15-21, plus the reload logic).
  - Mod patch format: `pcsx2-files/*.pnach` shows how PS2 code caves are used. They are not portable to the PC port.
- **Licence.** None in the repo. Read as specification. Do not copy code or data.
- **Caution.** `src/port_structs.py` is a generator that reads C# from a sibling directory. It is not a struct definition.

### DarkCloud-Two-Reforged, `refs/DarkCloud-Two-Reforged`

- **What it is.** The DC2 counterpart of DarkCloud-Reforged, for SCUS-97213. It is in alpha and states that crashes are expected. It has the same PINE layer, a PINE relay (`src/core/pine_relay.py`, which exposes the connection over TCP for external tools), and an extensive set of PNACH patches (`pcsx2-files/pnach/`, 00 to 19).
- **What Ixion can reuse.**
  - Addresses: `src/game/addresses.py`. It has `LOOP_NO` 0x20376FCC, `NOW_MODE`, `ACTIVE_CHARA_NO` (0 Max, 1 Monica), `SAVE_DATA_BASE` 0x21E01810, and save-data offsets such as chapter at +0x1A08 and config at +0x1C574. The comment on `LOOP_NO` is wrong (see Key facts).
  - Recipes and names: `src/data/inventions.py` (136 recipes), `src/data/idea_names.py` (294 ideas), `src/data/items.py` (DC2 item names).
  - Script disassembler: `scripts/decompile_script.py` (SB2 opcode table, plus `EXT_FUNCS` names for dungeon scripts from 0 to 85 and up) and `scripts/dump_script.py` (reads the script buffer at 0x2037CEE0, for a live PCSX2 session).
  - Text: `scripts/decode_messages.py` and `src/game/dialog.py` (DC2 message encoding: 16-bit codes, control codes such as `[X]`, `[O]`, `[red]`).
- **Licence.** None. Alpha. Read as specification.

### OpenCloud, `refs/OpenCloud`

- **What it is.** An MIT-licensed C++ reimplementation of DC2, built on a Vulkan base, dormant since 2023-12. There are about 105 `.cc` files under `code/`. Its wiki describes the main loops (`Game-Loops.md` is a stub), the SB2 file layout (`SB2-File-Format.md`), and items (`Items.md`).
- **What Ixion can reuse.**
  - SB2 analysis: `code/script/analyzer.cc` (function and string discovery, instruction walk) and `code/script/bytecode.h` (opcode enum, value types integer/float/string, comparison functions 40 to 45).
  - Engine modules as spec: `code/engine/mapjump.h` (map jump info, partially named), `run_script.cc`, `script_interpreter.cc`, `villager.cc`, `npc.cc`, `editloop.cc`, `mainloop.cc`.
  - Archive: `code/data/pak.h` (64-byte name, header size, entry size, two unknown words).
- **Licence.** MIT (LICENSE).
- **Caution.** Its loop model is not the decompiled one. Use it for names and layouts only, and cross-check against chronicletwo:ps2/include/mainloop.hpp.

### dark-chronicle-reverse-engineering, `refs/dark-chronicle-reverse-engineering`

- **What it is.** DC2 archive notes, a DC2 file hash list, a DC2 ISO explorer, two Cheat Engine tables, and cover scans. The notes say most of the work used a PAL disc.
- **What Ixion can reuse.**
  - Archive layout: `data.hd2` (DC1 layout, 4-int file records with unused fields), `data.hd3` (DC2 layout: name offset, length, chunk offset, chunk count), and `data.hd4` (an unused variant with 8,752 files). Chunks are 2,048 bytes. The file pairs are documented in the README.
  - Hash list: `file_hashes.csv` lists 8,752 files with offset, name, MD5 and SHA256. Use it to verify the PAL DC2 extract.
  - Known anomaly: `wep_t\ws050_item.chr` is stored twice. The two copies are byte-identical.
  - ISO explorer: `DarkChronicle.NET`, a .NET reader (not needed for Ixion, but useful to look at the disc).
- **Licence.** MIT (LICENSE).

### SB2-File-Parser, `refs/SB2-File-Parser`

- **What it is.** A C# console tool. It reads an SB2 file header (magic `SB2\0`, function-data offset, code start, header size, external function count, global variable count, and nine unknown words), then reads the external function table and function entries, and prints JSON.
- **What Ixion can reuse.** A second, independent SB2 header reading to check the OpenCloud layout. Its field names (`unk0` to `unk9`) show which header words are still unknown.
- **Licence.** MIT (LICENSE).

### DarkCloud (Xeeynamo), `refs/DarkCloud`

- **What it is.** C tools: WhiteCloud unpacks DAT archives described by HD2 or HD3 index files, and LightCloud repacks them. `libDarkCloud/hd2.c` and `hd3.c` contain the index readers. The README says repacking replaces the original files in place.
- **What Ixion can reuse.** The simplest reference for DC1 and DC2 archive indexing (`Hd2GetLbaName`, `Hd2IsLbaEmtpy`, and so on). Use it to cross-check the DCFM archive reader.
- **Licence.** GPL-2.0 (LICENSE). Reading is fine. Do not copy code into a non-GPL repo.

### DCExtractor, `refs/DCExtractor`

- **What it is.** A C# WinForms converter for DC1 and DC2 with 24 format specifications in `Specifications/` (Configs, Data, Images, Models, Pack). The README says it is not a repacking tool, and that animations and map geometry do not export correctly.
- **What Ixion can reuse.** The specification set is the most usable format reference for both games. Highlights: MDS (`Models/MDS.md`, 672 lines, including the bone and mesh layout), MOT, WGT, BBP, the PAK family (`Pack/PAK.md`, 146 lines), TM2 (`Images/TM2.md`, 600 lines), HD2 and HD3, and DAT. The specs state that they are speculative and derived by reverse engineering.
- **Licence.** GPL-3.0 (LICENSE). Use the specs as reference. Do not copy the C# code.

### Blender-Tools-For-Dark-Cloud, `refs/Blender-Tools-For-Dark-Cloud`

- **What it is.** A Blender add-on for DC1 `.chr` import. The binary layer under `DarkCloudModelTools/serialisation/` is symmetric (`Reader` and `Writer`), so `CHRBinary` can parse and write its own containers. The interface layer for MDS, CHR and CFG is read-only (see Key facts).
- **What Ixion can reuse.** A Python parser for CHR, MDS, BBP, WGT, MOT, IMG and CFG. Use the parsers, not the import operator. The `MDSBinary` read path (`filetypes/MDS/MDSBinary.py`, 292 lines) is a second check on the spec.
- **Licence.** MIT (LICENSE). Blender add-ons use the `bpy` API, which the Blender Foundation treats as GPL-compatible. DCFM's notice takes that position for its own script. Treat any Blender script Ixion adds the same way.

### noesis-mds-plugin, `refs/noesis-mds-plugin`

- **What it is.** A single Python file (`fmt_mds.py`, 677 lines) for the Noesis viewer. It registers `.mds`, `.chr` and `.img` handlers, with a container parser (`parseContainer`) and a CHR loader.
- **What Ixion can reuse.** A quick viewer for checking models. Its CHR loader shows the section and container layout.
- **Licence.** None in the repo.

### paktools, `refs/paktools`

- **What it is.** A Java tool that extracts and rebuilds Level-5 packages (`.chr`, `.pac`, `.pak`, `.snd`). The `Reconstruction.java` operation is the rebuild path that DCExtractor lacks.
- **What Ixion can reuse.** Pack rebuild logic for `.pak` and `.chr` files, for writing modified packs back.
- **Licence.** None in the repo. The README says the release is a `.tar` (SOURCES.md notes this). Read as specification only.

### HD6Tools, `refs/HD6Tools`

- **What it is.** A Java tool for later Level-5 HD6 archives. The format family is related to DC2 but is not the same.
- **Licence.** None in the repo.
- **Ixion value.** Low. Useful only for format lineage.

### Dragon-Quest-8-Tools, `refs/Dragon-Quest-8-Tools`

- **What it is.** Python tools for Dragon Quest VIII (PS2, Level-5 pack family). `PakTools.py` handles `pak`, `mpk`, `pcp`, `ipk`, `nav`, `sky`, `snd`, `pac` and `chr` files. `HD6Tools.py` handles HD6 archives.
- **What Ixion can reuse.** Another independent implementation of the pack header (a file header then data, repeated), useful to cross-check paktools and DCFM.
- **Licence.** None in the repo.

### Rainbow, `refs/Rainbow`

- **What it is.** A C# image converter with full TIM2 support (and partial NUT and TPL). Its file-format wiki is referenced by DCExtractor's TM2 spec.
- **What Ixion can reuse.** TIM2 reference for cross-checking the DCFM texture reader.
- **Licence.** GPL-2.0 (LICENSE.md).

### cwdemangle and dc2-demangler, `refs/cwdemangle`, `refs/dc2-demangler`

- **What they are.** `cwdemangle` is a Rust CodeWarrior C++ demangler (CLI and library). `dc2-demangler` is a Binary Ninja plugin for DC2 symbols. In this checkout, `dc2-demangler` contains only its LICENSE file.
- **What Ixion can reuse.** `cwdemangle` can turn mangled names in the DC1 and DC2 symbol dumps into readable names for cross-referencing with the decompilations.
- **Licence.** `cwdemangle` is MIT or Apache-2.0. `dc2-demangler` is MIT.

### ghidra-emotionengine-reloaded, `refs/ghidra-emotionengine-reloaded`

- **What it is.** A Ghidra extension for PS2 EE code: MMI and VU0 macro support, a STABS analyzer for ELF `.mdebug` sections, a PCSX2 save-state importer (`ghidra_scripts/PCSX2SaveStateImporter.java`), and a symbol importer for `.sym` files.
- **What Ixion can reuse.** The save-state importer and the STABS analyzer would help match ELF symbols to PS2 runtime state for the parity work. Note the README's zstd caveat for PCSX2 2.1.178 and later.
- **Licence.** Apache-2.0 (LICENSE).

### ps2_bn, `refs/ps2_bn`

- **What it is.** A Binary Ninja architecture plugin for PS2 EE code, with ELF loading and an instruction decoder (`ps2/decode.py`, `ps2/instruction.py`, `ps2/intrinsics.py`).
- **What Ixion can reuse.** An alternative disassembler for checking EE instructions, if Binary Ninja is in use.
- **Licence.** None in the repo.

### PS2DarkChronicle, `refs/PS2DarkChronicle`

- **What it is.** A Unity 6 URP prototype of a Dark Chronicle-style town with PS2 rendering: 640 by 448 point upscale, vertex jitter, toon lighting with a warm rim light, a procedural town, and a day-night cycle. The README is in Japanese and states MIT (line 117).
- **What Ixion can reuse.** Shader and render ideas only, if Ixion ever targets a town look. It contains no game data.
- **Licence.** MIT (per README).

### DarkCloud-MechanicsGuide, `refs/DarkCloud-MechanicsGuide`

- **What it is.** A static SvelteKit site. It has a fishing simulator (`src/lib/sim/fishing.js`) and a fish table (`src/lib/data/fish.js`). The formulas are described as reverse-engineered from the DC1 code. Weapons, dungeons and enemies pages are stubs.
- **What Ixion can reuse.** Fishing rules, if Ixion keeps fishing as a cross-world activity. The fishing sim is pure JavaScript and easy to read.
- **Licence.** BSD-2-Clause (LICENSE).

### project_toan, `refs/project_toan`

- **What it is.** A Unity DC1 fan remake. The README is one line. The repo is about 649 MB with assets (SOURCES.md).
- **What Ixion can reuse.** Almost nothing from the assets. The `Config` and `Content` folders may hold level or character setup, but this survey did not inspect them.
- **Licence.** None in the repo. Do not ingest its assets.

### docs/cheat-tables, `docs/cheat-tables/*.CT`

- **What they are.** Five Cheat Engine tables: Dark Cloud (2019 collection, 2,328 entries), Dark Cloud (fearlessrevolution, 93), Dark Cloud 2 (2019 undub collection, 1,048), Dark Cloud 2 (fearlessrevolution, 43), and Dark Cloud 2 (SinStar87, 65).
- **What Ixion can reuse.** Field names and struct offsets, for example the DC1 inventory and weapon fields and the ten anti-monster fields. The addresses are pointer chains from the PCSX2 executable base (for example `"pcsx2-r5350.exe"+005EC074`, then offsets). They are not EE-RAM addresses. Convert them with care, or use the names only.
- **Licence.** Unknown. They are community files, and the repo does not record their licence.

### Pulled wiki and notes, `docs/tcrf`, `docs/fandom`, `docs/opencloud-wiki`

- **What they are.** TCRF pages (including Kojin's DC2 technical pages, a TIM2 page, and a disassembly page), 30 Fandom pages as wikitext, and OpenCloud's wiki.
- **What Ixion can reuse.** TCRF is the best public source on DC2 internals and the debug menu. Fandom pages give item, dungeon and character text that cross-check the data tables.
- **Licence.** Not recorded in the repo. Wiki text is normally under a CC licence, but that has not been checked here (see Open questions).

## Ixion hooks

- **Mode mapping** (`ps2/include/main.hpp` in chronicle; `ps2/include/mainloop.hpp` in chronicletwo). Where: any cross-world loop switch. Idea: keep a single table that maps each world's loop enum (DC1 GameMode: EDIT=2, DUNGEON=3; DC2 MainLoopMode: EDIT=1, DUNGEON=2) to Ixion's own state, so the two numbering schemes never mix. Use the enums, not the community comments.
- **Town character swap.** Where: the town-side character loader in the Chronicle port (not located in this survey; the reference points are DC1 `chara/c01d.chr` and the `gedit/*/chara/*.chr` paths, which all exist in the PAL extract, and the dungeon table at chronicle:ps2/src/btitem.cpp:57-58 and :209). Idea: keep the community approach of pointing the loader at another character's `.chr` and `info.cfg`, but do it in the port's file layer, not through memory writes.
- **Ally path table.** Where: the Ixion cast definition. Idea: use the six `CHR_PATHS` entries from `allyswitch.py` (Toan's `chara/c01d.chr` plus the five allies) as the DC1 cast source list, and check each against the port's loader before shipping.
- **SB2 and STB disassembly for event dispatch.** Where: ChronicleTwo event code (chronicletwo:ps2/src/event.cpp, event_func.cpp), and the DC1 STB interpreter. Idea: use the Reforged SB2 opcode table and OpenCloud's enum to build a checker that flags unknown opcodes in cross-world scripts. Use DCFM's `StbVm.cpp` as a second reading of CRunScript.
- **Invention recipes as data.** Where: a new Ixion data file, loaded like the translation table in DESIGN 4.5. Idea: start from the 136 recipes and 294 idea names in `inventions.py` and `idea_names.py`. Verify against the PAL DC2 disc before use, since the recipes were read from NTSC-U memory.
- **Element and anti-monster rows.** Where: the translation table in DESIGN 4.5 (`w_elem`, `w_monster`). Idea: seed the rows from the DC1 element IDs (81 to 85) and the ten DC1 anti-monster fields in the cheat table. Mark them as "verify" until checked against the DC2 attribute table.
- **Gilda read width.** Where: DESIGN 4.3 gilda row, and the DC1 money field. Idea: the Reforged read is 16-bit unsigned at 0x21CDD892. Confirm the width and sign in the port's struct before applying the 65,535 clamp.
- **Town and dungeon tables.** Where: the destination picker (DESIGN 3.3). Idea: use `DUNGEON_NAMES` and `TOWN_NAMES` from `addresses.py` as seeds. Resolve the duplicate "Yellow Drops" entry first.
- **Georama and town configs.** Where: a read-only layout loader for both worlds. Idea: reuse DCFM's `EdtFile.cpp` and `DcVillageCfg.cpp` as the spec for DC1 georama and village layouts. DC2 equivalents are `geo0.cfg` and similar files in the PAL extract, which DCFM does not cover.
- **Archive verification.** Where: the PAL extract step (the DC2 data root and `data.hd3`). Idea: run the `file_hashes.csv` check as a diagnostic, not a gate, and first explain the 49 sampled mismatches (region, build, or extraction path). Keep the list out of the repo, or cite it only by name.
- **PINE relay for parity.** Where: the test harness (not the PC port). Idea: the PINE client in Reforged and the relay in DC2 Reforged can read PCSX2 memory for a parity check against a PS2 build. That is useful only if a PS2 build is kept for comparison.
- **Save layout.** Where: Ixion's save ledger (DESIGN 4.6). Idea: the DC2 save offsets (chapter at +0x1A08, config at +0x1C574, SaveData base 0x21E01810) are a starting map for which save fields exist, but they come from an alpha mod and need checking.

## Risks and blockers

- **Build mismatch.** Almost every address in the community code is from NTSC-U (SCUS-97111 for DC1, SCUS-97213 for DC2). The workspace's extracted discs are PAL. Ally paths and the ten anti-monster fields may be the same across regions, but the memory addresses and the table offsets may not be. Check each address against the PAL build before use.
- **Address conflicts.** The chr config address conflicts within Reforged and Enhanced (0x2029A9F0 vs 0x2029AA18). The DC2 `LOOP_NO` comment is wrong. Treat these as leads, not facts.
- **MDS writer conflict.** DCFM docs disagree about whether an MDS writer exists. Do not design a model export path around either claim until the JS round-trip gate is run or the code is read.
- **Blender export claim.** The Blender add-on's README claims export. Its code does not implement it.
- **Licences.** Eight repos have no licence (DarkCloud-Reforged, DarkCloud-Two-Reforged, paktools, HD6Tools, Dragon-Quest-8-Tools, noesis-mds-plugin, ps2_bn, project_toan). Copy nothing from them. GPL repos (DCExtractor, DarkCloud, Rainbow) impose copyleft if code is copied. DCFM's `kConvertPy` is GPL-3.0-or-later, and its SESQ walker is zlib-licensed and needs attribution.
- **Alpha and abandoned sources.** DarkCloud-Two-Reforged is alpha. OpenCloud has been dormant since 2023-12. Their addresses and layouts may be wrong for later builds.
- **Gilda sign.** The 65,535 clamp in DESIGN depends on a 16-bit view that has not been checked against the game's own type.
- **Asset exposure.** project_toan and the DC2 hash list point at ripped assets or disc-derived data. Keep them out of the public repo.
- **Cheat-table addresses.** They are pointer chains from the PCSX2 executable base, so they can't be used as flat addresses without the chain resolution.

## Open questions

- Do the NTSC-U community addresses (the Enhanced and Reforged address maps, DC2 Reforged addresses) match the PAL builds of the same functions? A check of one value per table (for example, gilda, mode, and the ally config slot) would settle this.
- Which of the two MDS claims is right? Run the JS round-trip gate, or read `app/fmt/mds-format.mjs` `write()` against `MdsModel.cpp`, before relying on either.
- Does the Blender `.chr` import match DCFM's `MdsModel.cpp` on the same model? A two-reader comparison would help settle structure disputes.
- Why does the PAL DC2 extract differ from `file_hashes.csv` on about a third of a 150-file sample (81 match, 49 differ, 20 not found)? Candidate causes: the list was built from another region or build, the extract's paths differ from the list's, or some entries are duplicates or padding. Check the 49 differing names by size before drawing a conclusion.
- Are the DC2 SB2 opcodes 0x1B (END in Reforged, exit in OpenCloud) and the zero opcode (end in OpenCloud) the same thing? Check against the decompiled SB2 interpreter in ChronicleTwo.
- Do DC2 model and pack formats match DC1 (DCExtractor's specs claim both games)? Check one DC2 `.mds` or `.pak` against the DC1 spec.
- What licence do the TCRF and Fandom wikitext pages carry in the repo? Wiki text is normally CC-licensed, but this has not been checked.
- Is the cheat-table licence (2019 collection and fearlessrevolution) recorded anywhere? The tables are community files with no licence in the repo.
- Which DCFM "Play mode" gaps (talk in Norune, dungeon monsters, chest interact) are real for the PS2 build, and which were only DCFM's own limits? Check the parity document before treating them as game behaviour.
