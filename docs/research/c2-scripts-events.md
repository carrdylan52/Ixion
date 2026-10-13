# ChronicleTwo scripts and events

## What this covers

The event and script layer of the ChronicleTwo (Dark Chronicle) PC port: the bytecode
virtual machine (`CRunScript`), the compiled program format (`SB2` binaries, `.stb`),
the three native command tables that scripts call into (scene events, effects, actions;
monsters noted for completeness), the scene event runner that starts a script from a map
point or a talk, the event loop that steps it and turns its requests into map changes,
how event points are placed on maps (tagged `.map` text), where script-visible flags and
counters live, and the port seams that replace PS2-only pieces. The last sections list
Ixion integration points that avoid editing `ps2/src`, and the blockers.

Not covered: the Chronicle (DC1) side (see `c1-scripts-events.md` next to this file),
message-window rendering, the battle-monster VM beyond its table, and decoding of
individual `.stb` programs. The sibling DC1 note is the comparison point for any cross-world
script work.

Method: static reading of `chronicletwo:ps2/src`, `chronicletwo:ps2/include` and
`chronicletwo:port/src` at the ixion base, Kazarov port tooling from the Kazarov clone,
and file counts over the read-only PAL data extract (names only, nothing decoded). No builds
or game launches.

## Key facts

- **Opcodes.** The VM defines 29 opcodes, numbered 1 to 30; only 22 is unassigned. chronicletwo:ps2/include/runscript.hpp:18-47. Dispatch is one `switch` in `CRunScript::exe`, chronicletwo:ps2/src/runscript.cpp:327-750.
- **Program file.** A compiled program starts with a 4-byte magic (`SB2` for programs with a global block), then `RS_PROG_HEADER` (main offset, code offset, program table offset and count, global count). chronicletwo:ps2/include/runscript.hpp:217-225. The loader reads it in place and sets the global block, chronicletwo:ps2/src/runscript.cpp:223-240.
- **Program table.** Each entry maps a script program number to a `funcdata` offset. `run(no)` searches it; a negative number runs the main function. chronicletwo:ps2/include/runscript.hpp:203-209; chronicletwo:ps2/src/runscript.cpp:257-306.
- **Disc structs are pinned on the host.** `vmcode_t` is 12 bytes, `funcdata` 16, `RS_PROGDATA` 8; the port asserts these with `PORT_RECORD_ASSERT`, chronicletwo:ps2/include/runscript.hpp:209, 382, 398. The runtime structs `RS_STACKDATA` (8 bytes on PS2, a union with pointer members) and `RS_CALLDATA` (three pointers) grow on a 64-bit host. chronicletwo:ps2/include/runscript.hpp:190-196, 352-363. On the port, `STATIC_ASSERT` expands to nothing, so the PS2 size checks do not run there, chronicletwo:port/include/port.h:37, 41.
- **Scene event commands.** 696 numbered external commands (`EVENT_EXT_*`), chronicletwo:ps2/include/event_func.hpp:54-758. Their handlers are listed in a 697-entry table (last entry is the terminator), chronicletwo:ps2/src/event_func.cpp:21079-21776. `SetEventFunc` copies them into a 1500-slot dispatch array (`EVENT_EXT_FUNC_NUM`), chronicletwo:ps2/include/event_func.hpp:44; chronicletwo:ps2/src/event_func.cpp:21779-21812. The highest retail id is 1274 (`FORCE_BOOT_TOUR`). Ids 1275 to 1499 are unused, and 804 ids below 1500 are free in total (counted from the enum).
- **Duplicate ids hang the game.** `SetEventFunc` spins in `while (true)` when two table entries share a number, chronicletwo:ps2/src/event_func.cpp:21795-21798.
- **Unknown commands fail quietly.** `CRunScript::ext` prints "not found ext" for an out-of-range or empty slot and "illegal function call" when a handler returns 0; the script keeps running. chronicletwo:ps2/src/runscript.cpp:202-221.
- **Effect scripts.** 128 commands (chronicletwo:ps2/src/effscript.cpp:5574-5703; chronicletwo:ps2/include/effscript.hpp:62-190), a 256-slot table, a 64-value stack and two call frames, chronicletwo:ps2/src/effscript.cpp:5562-5568. Effect bases come from a 219-row definition table, chronicletwo:ps2/src/effscript.cpp:36; chronicletwo:ps2/include/effscript.hpp:41.
- **Action scripts.** About 80 commands in one table (unverified), a 128-value stack and 512 call frames, chronicletwo:ps2/src/actscript.cpp:165, 2609-2616. Monster scripts have 174 numbered commands (unverified), chronicletwo:ps2/include/runscript_opcodes.hpp:21-197.
- **Event argument scripts.** Two commands (`EVENT_ARG_DATA`, `EVENT_ARG_ID_OFFSET`) and a 32-value stack, chronicletwo:ps2/include/event_func.hpp:759-772; loaded by `_LOAD_ARG`, chronicletwo:ps2/src/event_func.cpp:18657.
- **Event script files.** A map's script is `map/<a>/<abc>/<def>/<name>.stb` (the third directory exists only for names of six or more characters), built from the map name; the `_<lang>` variant is tried first, then the base name, chronicletwo:ps2/src/mapjump.cpp:372-381, 388-420; path shape from `GetMapPath`, chronicletwo:ps2/src/mapselect.cpp:306-325 (location inferred from the GetMapPath body). In the extracted PAL data there are 1356 `.stb` files: 962 under `map/` (810 of them `_N` language variants), 212 `dungeon/eff_script`, 144 `dungeon/monster`, 24 `dungeon/act_script`.
- **Event start chain.** A map event point gives `point_no` as the event number (chronicletwo:ps2/src/editctrl.cpp:1066). `CScene::RunEvent` records it and copies the trigger data (chronicletwo:ps2/src/sceneevent.cpp:134-155). The town loop picks up `event_run` (chronicletwo:ps2/src/editloop.cpp:2057-2100) and calls `RunEvent`, which runs `EventScript.run(event_no)` (chronicletwo:ps2/src/event.cpp:118-121).
- **Event numbers seen in code.** 100 is the default event number that a jump or load uses when the script names none (chronicletwo:ps2/src/event_func.cpp:3619, 3644, 4110). 1000 is the talk event (chronicletwo:ps2/src/editloop.cpp:1513). 201 and 310 are fixed town events (chronicletwo:ps2/src/editloop.cpp:1221; chronicletwo:ps2/src/editevent.cpp:382). 150 is the keyboard-opened event (chronicletwo:ps2/src/editloop.cpp:55). 300 and 400 are chosen for two game-object kinds (chronicletwo:ps2/src/sceneevent.cpp:209-211).
- **Map changes from scripts.** `_MAP_JUMP` (chronicletwo:ps2/src/event_func.cpp:4093), `_GOTO_INTERIOR` (3612), `_GOTO_OUTSIDE` (3637), `_FUNCTION_MAP_JUMP` (7410) and the `GOTO_DNG*` and `GOTO_EDIT` family set `EdEventInfo` fields and a request. The town loop resolves the name with `SearchMapNo` and jumps (chronicletwo:ps2/src/editloop.cpp:1553-1575).
- **Destination name buffer.** `jump_map_name` holds 32 bytes and sits between `jump_point` and `event_no` in `ED_EVENT_INFO` (chronicletwo:ps2/include/event_func.hpp:1097-1148, size asserted at 1148 on PS2 only). Scripts fill it with unbounded `strcpy` (chronicletwo:ps2/src/event_func.cpp:3614, 3639, 4098, 4101, 6120, 7423).
- **Story bit flags.** 2048 bits (`SAVE_BIT_FLAG_MAX`, chronicletwo:ps2/include/savedata.hpp:25, 216). `_SET_FLAG` and `_GET_FLAG` call `CSaveData::SetBitFlag` and `GetBitFlag` (chronicletwo:ps2/src/event_func.cpp:3843, 3865; chronicletwo:ps2/src/savedata.cpp:62-90). Out-of-range bits return 0 without a message (chronicletwo:ps2/src/savedata.cpp:54-60).
- **Story counters.** 128 signed 16-bit values (chronicletwo:ps2/include/savedata.hpp:32, 217), set and read by `_SET_CNT` and `_GET_CNT` (chronicletwo:ps2/src/event_func.cpp:3883, 3905).
- **Control byte.** One `u8` `bit_ctrl`, set and cleared by `_SET_BIT_CTRL` and `_GET_BIT_CTRL` (chronicletwo:ps2/include/savedata.hpp:239; chronicletwo:ps2/src/event_func.cpp:18613-18650). The header says map changes also write it.
- **Per-map flags.** 128 bits per map, 256 maps in the save (chronicletwo:ps2/include/map.hpp:36, 59-82; chronicletwo:ps2/include/savedata.hpp:39, 218). They record things like opened treasure boxes (chronicletwo:ps2/src/map.cpp:2021-2042). No script command reading or writing these was found in the command list.
- **Event-local state.** 2048 local flag bits and 64 local counters (chronicletwo:ps2/include/event_func.hpp:39; chronicletwo:ps2/src/event_func.cpp:2646-2758, commands at 4388 and 4399). Both are cleared in `EdEventMapInit` (chronicletwo:ps2/src/event_func.cpp:3345-3359), which runs on map entry (chronicletwo:ps2/src/editloop.cpp:2798; chronicletwo:ps2/src/dng_event.cpp:2322).
- **Event points in map files.** A `.map` file is tagged text read by the script interpreter with `map_tag` (chronicletwo:ps2/src/mapload.cpp:2092-2172). A point is `FUNC_POINT` with `FUNC_DATA "event"` and `FUNC_EVENT_DATA` (kind, event_no, point_no, arg1-3, target). Kind strings map to `FUNC_EVENT_*` bits (chronicletwo:ps2/src/mapload.cpp:1820-1880; chronicletwo:ps2/include/mapload.hpp:56-67). 158 PAL `.map` files contain `FUNC_EVENT_DATA`.
- **Trigger kinds.** Touch, action (confirm) and item (square) checks (chronicletwo:ps2/include/map.hpp:169-172). `CheckFuncEvent` tests a point's scaled volume and its action or item flag (chronicletwo:ps2/src/map.cpp:2104-2160). `CFuncPoint::Check` gates on enable and the hour range (chronicletwo:ps2/src/funcpoint.cpp:91-101).
- **Script access to event data.** `_GET_EVENT_DATA` and `_SET_EVENT_DATA` read and write the triggering `CSceneEventData` fields (chronicletwo:ps2/src/event_func.cpp:17316, 8556).
- **Shared storage.** `CScene` puts `map_jump_flags`, `map_jump_name`, door fields and `villager_id` in a union with `event_data` (chronicletwo:ps2/include/scenesnd.hpp:391-412).
- **Port seam for events.** `SetEventScript` is overridden in the port. It copies the retail table into a host array, calls `ReplaceEventVectorCallbacks`, and adds the sword and dungeon-effect slots (chronicletwo:port/src/event.cpp:93-117). The host arrays are 128 values and 512 calls, matching the PS2 sizes (chronicletwo:port/src/event.cpp:96-97).
- **Port callbacks.** Four retail slots are replaced: distance, two-point distance, attribute status and set-frame-position (chronicletwo:port/src/event_vector_callbacks.cpp:26-95; header at chronicletwo:port/src/event_vector_callbacks.hpp:5-6).
- **Build wiring.** Every `ps2/src` and `port/src` `.cpp` is globbed into the port build (chronicletwo:port/CMakeLists.txt:78-79). A `PORT_OVERRIDE` definition replaces the same-named `ps2/src` definition at build time (kazarov:scripts/build/port_override.py docstring; kazarov:include/kazarov/port.h:19-20). `RETAIL_BRIDGES` keeps a named retail body callable under a new link name (chronicletwo:scripts/port/unit_copy.py:41-44). Stub headers with `asm(...)` names declare cross-unit symbols (chronicletwo:port/include/stubs/event.hpp:4).
- **Tagged-text interpreter.** `CScriptInterpreter` reads map, character, dungeon and config files by tag name or, in binary form, by tag index (chronicletwo:ps2/include/scriptinterpreter.hpp; chronicletwo:ps2/src/scriptinterpreter.cpp:153-217, 478-551). The port overrides only `GetArg` (chronicletwo:port/src/scriptinterpreter.cpp:23-111).
- **Test pattern.** Handlers can be run without the game by calling `script.ext_func_table[id]` with `RS_STACKDATA` arrays (chronicletwo:port/src/tests/event_vector_test.cpp:24-40).

## How it works

### The virtual machine

`CRunScript` is a stack machine. Its operand stack holds tagged values (int, float, string,
or a pointer to another slot), and its call stack holds return address, caller frame and
caller function. A program uses a global block when its magic is `SB2`.

Calls and returns (`RS_OP_CALL`, `RS_OP_RET`) reserve the callee's frame and clear its
locals. `RS_OP_EXT` is the bridge to native code: it pops `arg1` values, the first of which
is the command number, and calls `ext_func_table[number]` with the remaining slots
(chronicletwo:ps2/src/runscript.cpp:697-704, 202-221). Handlers read arguments through
helper accessors and write results through pointer arguments. A handler returns non-zero
on success.

Suspension is cooperative. `RS_OP_WAIT` saves the program counter and returns to the caller
of `exe`; `resume()` continues from there (chronicletwo:ps2/src/runscript.cpp:247-255,
729-735). `RS_OP_END` and a top-level `RS_OP_RET` set `end` and stop (chronicletwo:ps2/src/runscript.cpp:705-728).

Skip is a second mode. `RS_OP_SKIP_END` marks the end of a skippable stretch. `skip()` sets
`skip_wait` and resumes, so execution runs without suspending until the next skip end
(chronicletwo:ps2/src/runscript.cpp:322-325, 736-745). While `skip_wait` is set, `EXT` is not
executed and the jump opcodes do not jump (chronicletwo:ps2/src/runscript.cpp:425-455,
700-702). See risk R5.

Comparison uses integer or float operands; mixing types promotes to float, and other types
stop the interpreter with a message (chronicletwo:ps2/src/runscript.cpp:457-520). Division
by zero aborts (chronicletwo:ps2/src/runscript.cpp:577-583, 64-75).

### Opcodes

| Group | Opcodes (number) |
|---|---|
| Data | LOAD 1, LOAD_ADDR 2, PUSH_CONST 3, POP 4, STORE 5 |
| Arithmetic | ADD 6, SUB 7, MUL 8, DIV 9, MOD 10, NEG 11, ITOF 12, FTOI 13, AND 24, OR 25, NOT 26, SIN 29, COS 30 |
| Compare and flow | CMP 14, RET 15, JMP 16, JMP_FALSE 17, JMP_TRUE 18, CALL 19 |
| Host | PRINT 20, EXT 21 |
| Suspend and end | WAIT 23, END 27, SKIP_END 28 |

Compare sub-codes are 40 to 45 (EQ, NE, LT, LE, GT, GE). Load and address modes are
bit flags from 0x1 (local) to 0x200 (global float), with indexed and pointer-indexed forms
(chronicletwo:ps2/include/runscript.hpp:274-308). Constants are int (1), float (2) or
string (3) (chronicletwo:ps2/include/runscript.hpp:294-298).

### Starting and stepping an event

1. A trigger resolves to an event number. Touch, action and item checks pick the nearest
   accepting point across active maps and parts (chronicletwo:ps2/src/map.cpp:1615-1690).
   The town then runs the point's kind logic: doors, treasure boxes and books become edit
   events; everything else passes `point_no` to `RunEvent`
   (chronicletwo:ps2/src/editctrl.cpp:1066-1094). Ladder points return early and start the
   ladder mode instead of an event.
2. `CScene::RunEvent` accepts the request when no event is running, or when the running
   event number is not 100. If the running event number is 100, the request is dropped. A
   line is printed whenever an event is running (chronicletwo:ps2/src/sceneevent.cpp:134-155). Data is
   copied into `event_data` (`CSceneEventData`, 0xD0 bytes, chronicletwo:ps2/include/sceneevent.hpp:61-97).
3. The town loop sees `event_run`, calls `InitEvent`, then `RunEvent` on the interpreter
   (chronicletwo:ps2/src/editloop.cpp:2057-2100; chronicletwo:ps2/src/event.cpp:97-101,
   118-121). The interpreter is one static object, `EventScript`, shared by towns and
   dungeons (chronicletwo:ps2/src/event.cpp:42).
4. Each frame `EventLoop` checks the skip state, then the command mode. In the normal
   mode it resumes the script; the door mode plays the door sequence in place of the
   script (chronicletwo:ps2/src/event.cpp:282-353; door sequence at 123-227). If the script
   is not finished it steps the sequences (`EdEventStep`, chronicletwo:ps2/src/event_func.cpp:3254-3286).
5. Requests from the script are read after the step. `GOTO`, `MAP_JUMP`, `INTERIOR`,
   `OUTSIDE`, `EDIT_MODE`, `RESET_EDIT` and `RESTART_EDIT` return to the loop with their
   number. `LOAD_SCRIPT` is handled inside `EventLoop`: it loads the new file, rebuilds the
   interpreter and starts the requested entry (chronicletwo:ps2/src/event.cpp:367-422).
6. When the script ends, `EdEventEnd` clears message buffers and sequences
   (chronicletwo:ps2/src/event.cpp:441-445; chronicletwo:ps2/src/event_func.cpp:3446-3450).
   `EdEventFinish` resets camera sequences, object sequences, sprites and hit effects
   (chronicletwo:ps2/src/event_func.cpp:3173-3250).

Dungeon events use the same interpreter. A dungeon starts an entry immediately with the
scene pointer `DngMainScene` (chronicletwo:ps2/src/event.cpp:407-410). The dungeon's
per-frame handler acts only on END, SUB_MODE and GOTO (chronicletwo:ps2/src/dng_main.cpp:2130-2143).

### Request codes

| Value | Name | Consumer |
|---|---|---|
| 0 | NONE | keep running |
| 1 | END | town and dungeon |
| 2 | SUB_MODE | menu hand-off |
| 3 | GOTO | walk or dungeon exit |
| 4 | INTERIOR | town switch (editloop.cpp:1565) |
| 7 | OUTSIDE | town switch (editloop.cpp:1576) |
| 8 | MAP_JUMP | town (editloop.cpp:1553-1564) |
| 15 | LOAD_SCRIPT | handled inside EventLoop |
| 17-19 | EDIT_MODE, RESET_EDIT, RESTART_EDIT | town |

Values from chronicletwo:ps2/include/event.hpp:21-33.

### Command table ranges

The 696 commands are grouped by number. The ranges below are read from the enum and
handler names (chronicletwo:ps2/include/event_func.hpp:54-758); the grouping is a reading,
not a retail label.

- 0-124: input pad, scene and map control, script flags and counters, character position,
  motion and visibility (for example `SET_FLAG` 13, `GET_FLAG` 14, `MAP_JUMP` 20,
  `GOTO_INTERIOR` 6, `LOAD_SCRIPT` 86, `SET_LOCAL_FLAG` 32, `SET_MOTION` 106).
- 192-231: message windows (`MES_*`).
- 300-326: `ASQ_*` character action sequences (inferred from names) and `IMG_*` image sets.
- 350-359: `SPRITE_*` event sprites (`CEventSprite2`, 0x30 of them).
- 400-436: `CMRS_*` camera sequences; 450-491: `OBJS_*` object sequences (32 of them, each
  with 256 nodes).
- 500-590: map, camera, menu, gyoracing, save data and dungeon helpers.
- 600-671: sound, streams and background music.
- 700-732: `EOH_*` event object handles: 32 handles of type none, character, object,
  sprite, frame or function point (chronicletwo:ps2/include/event_func.hpp:1055-1069).
- 750-788: `SPHIDA_*`, the sphida mini-game.
- 1000-1111: vector math, sword effects (`SWE_*` at 1030-1033), dungeon floor and pause,
  and the effect manager `ESM_*` at 1100-1111.
- 1200-1274: character conditions, time, floor and episode state, mono flash, sepia and
  miscellaneous tests.

Callbacks replaced in the port: distance and two-point distance (1007, 1008), attribute
status (1258), set-frame-position (483), dungeon effect clear (1265) and the sword effect
commands (1031-1033) (chronicletwo:port/src/event_vector_callbacks.cpp:90-95;
chronicletwo:port/src/event.cpp:76-116).

### Flags and counters, side by side

| Store | Size | Script commands | Lifetime |
|---|---|---|---|
| Story bit flags | 2048 bits | `SET_FLAG`, `GET_FLAG` | save data |
| Story counters | 128 x 16-bit | `SET_CNT`, `GET_CNT` | save data |
| Control byte | 8 bits | `SET_BIT_CTRL`, `GET_BIT_CTRL` | save data |
| Per-map flags | 128 bits per map | none found; read by map code | save data |
| Event-local flags | 2048 bits | `SET_LOCAL_FLAG`, `GET_LOCAL_FLAG` | cleared per map entry |
| Event-local counters | 64 ints | `SET_LOCAL_CNT`, `GET_LOCAL_CNT` | cleared per map entry |

Sources: chronicletwo:ps2/include/savedata.hpp:216-239; chronicletwo:ps2/src/map.cpp:36-70;
chronicletwo:ps2/src/event_func.cpp:2646-2758, 3345-3359.

### How events change maps

A script sets a destination name and a point, then leaves a request. The town loop does the
switch: `SearchMapNo(name)` finds the map, `EditMapJump` loads it, and `event_no` (default
100) is the event to start after the load (chronicletwo:ps2/src/editloop.cpp:1553-1564).
The dungeon handler does not act on map-jump requests (see R14). Map names are the stable
key: `GetMapName` and `SearchMapNo` work over the `MAP_NAME_INFO` table
(chronicletwo:ps2/include/mapselect.hpp:133-141; chronicletwo:ps2/src/mapselect.cpp:367).

Map scripts follow the map. `LoadMapScript(name)` loads the map's `.stb` and remembers its
path for later reloads (chronicletwo:ps2/src/mapjump.cpp:372-386). Language suffixes are
rewritten by `FileNameConvLanguage`: `_1.stb` becomes `_<n>.stb` for French, German, Italian
and Spanish only (chronicletwo:ps2/src/event_func.cpp:1842-1862).

Function-point map jumps keep their options in the scene's `map_jump_flags` word, and the
destination name is read from byte offset 24 of that block (chronicletwo:ps2/src/event_func.cpp:7410-7430;
chronicletwo:ps2/include/scenesnd.hpp:391-400). That block shares storage with `event_data`
(R6).

### Adding an event without editing ps2/src

The honest answer is that a new event needs bytecode, a new native handler, or both, and
the repo has no script compiler. Three routes, in order of effort:

1. **Data only.** Add a `FUNC_EVENT_DATA` line to a `.map` file with an event number and
   point number that already exist. This reuses retail programs and needs no code. The
   overlay channels are `CMapInfo::AddMapInfo` (chronicletwo:ps2/src/mapinfo.cpp:782-803)
   and the add pass in `CMap::CreateMap` (chronicletwo:ps2/src/map.cpp:1849-1860). The add
   pass uses the same `map_tag` table, so event tags are parsed there too (inference; the
   add pass was not traced past `LoadMapFile`).
2. **Native event, no bytecode.** Route selected event numbers to a C++ handler in
   `port/src`, bypassing `EventScript.run`. The seam is `StartEventSyori` or `CScene::RunEvent`
   (chronicletwo:ps2/src/event.cpp:229-241; chronicletwo:ps2/src/sceneevent.cpp:134). The
   handler must follow the request and end protocol that `EventLoop` expects
   (chronicletwo:ps2/src/event.cpp:355-452). This is the least risky route for new content.
3. **New bytecode.** Hand-assemble an `SB2` program: a header, a program table, and
   `vmcode_t` words (12 bytes each) against the opcode set above. The command numbers must
   match the table, so the new program can only call what the table has. No assembler or
   disassembler was found in the repo (see R8).

New native commands (ids in free slots, see H1) are callable only from bytecode that already
names them. Without route 2 or 3 they add nothing to retail scripts.

## Ixion hooks

- **H1. Register Ixion commands in free slots.** Where: `chronicletwo:port/src/event.cpp:93-117`
  (SetEventScript override), inside the window after `ReplaceEventVectorCallbacks` (line 112)
  and before `ext_func` at line 116; or in `chronicletwo:port/src/event_vector_callbacks.cpp:90-95`,
  which already is the scene's private-table hook. What: add handlers for ids 1275-1499, which no
  retail command uses. Define the ids in a port header, not in `ps2/include`. Put the handlers in a
  new `port/src` file; it is globbed into the build (chronicletwo:port/CMakeLists.txt:79).
- **H2. Native event routing.** Where: `chronicletwo:ps2/src/event.cpp:229` (`StartEventSyori`,
  retail body; add a `RETAIL_BRIDGES` entry in `chronicletwo:scripts/port/unit_copy.py:41-44`
  if the retail body is needed), or a port override of `CScene::RunEvent` in a new
  `port/src/sceneevent.cpp` section (the file already overrides `DrawSky`). What: when an event
  number is in an Ixion range, run native code that drives `EdEventInfo` and the scene instead
  of `EventScript.run`.
- **H3. Crossing request.** Where: `chronicletwo:ps2/src/event_func.cpp:3612-3634` (`_GOTO_INTERIOR`)
  shows the fields to set; the consumer is `chronicletwo:ps2/src/editloop.cpp:1553-1575`. What:
  an Ixion command that sets `jump_map_name`, `jump_point`, `event_no` and the request exactly as
  `_GOTO_INTERIOR` does, with a station key of 31 bytes or less. To intercept the request before the
  town switch, a port override of `EventLoop` (chronicletwo:ps2/src/event.cpp:282) can call a retail
  bridge of `EventLoop`; that bridge is not yet registered in `RETAIL_BRIDGES`.
- **H4. Ixion flag block.** Where: `chronicletwo:ps2/include/savedata.hpp:216-239`,
  `chronicletwo:ps2/src/savedata.cpp:54-103`. What: keep Ixion state in a separate port-only block
  rather than in spare bits of `bit_flag`, because the retail array covers its full range by index.
  Ixion commands from H1 read and write it.
- **H5. Overlay event points.** Where: `chronicletwo:ps2/src/mapload.cpp:1820-1880` (the parser for
  `FUNC_EVENT_DATA`) and the add pass in `chronicletwo:ps2/src/map.cpp:1849-1860`. What: an
  overlay `.map` fragment can place Ixion stations as event points that point at H1 or H2 numbers.
- **H6. Trigger data.** Where: `chronicletwo:ps2/src/event_func.cpp:8556` and `17316`
  (`_SET_EVENT_DATA`, `_GET_EVENT_DATA`). What: a station trigger can carry its destination in
  `arg1` to `arg3` and read it from the triggering `CSceneEventData`, without new storage.
- **H7. Overlay script files.** Where: `chronicletwo:ps2/src/mapjump.cpp:388-420` (`LoadScript`, with
  localised-then-base fallback) and `chronicletwo:ps2/src/event_func.cpp:5924-5940` (`_LOAD_SCRIPT`).
  What: load an Ixion-owned `.stb` by path through the same route. Keep names under 46 characters
  (R3).
- **H8. Handler tests.** Where: `chronicletwo:port/src/tests/event_vector_test.cpp:24-40`. What:
  test Ixion handlers by calling `script.ext_func_table[id]` directly, with no game launch.
- **H9. Effect-side commands.** Where: `chronicletwo:ps2/src/effscript.cpp:5562-5569` (`SetEffectScript`,
  PS2 only; the port does not override it) and `chronicletwo:ps2/src/effscript.cpp:5711-5725`
  (`SetEffectScriptFunc`). Ids 16-49, 59-99 and 115-124 are free in the 256-slot table. What: if an
  Ixion effect needs a native helper, add it by a port seam, as H1 does for events.

## Risks and blockers

- **R1. Duplicate ids hang at startup.** Adding a retail-style entry to `ext_func_info` with an
  existing number spins at boot (chronicletwo:ps2/src/event_func.cpp:21795-21798). The port
  path (H1) avoids the table and its check.
- **R2. Silent failures.** Unknown ids and handler returns of 0 print and continue
  (chronicletwo:ps2/src/runscript.cpp:202-221). A mistyped id or argument count is easy to miss.
- **R3. Fixed-size name buffers.** `jump_map_name` is 32 bytes and sits right before `event_no` in
  `ED_EVENT_INFO`, so a longer name overwrites the event number and the script name that follow
  (chronicletwo:ps2/include/event_func.hpp:1097-1148). `strcpy` is unbounded at the sites listed in
  the key facts. `script_name` is 64 bytes (`_LOAD_SCRIPT` at chronicletwo:ps2/src/event_func.cpp:5932),
  and `now_script_file` is 64 bytes while the path it receives is built in a 128-byte buffer
  (chronicletwo:ps2/src/mapjump.cpp:90, 372-379). A map path longer than 63 bytes overflows it;
  for a name of length N the path is N+18 bytes, so names of 46 or more characters are at risk
  (inference from `GetMapPath`).
- **R4. One interpreter, one event.** `EventScript` is shared by towns and dungeons, and
  `RunEvent` drops a new request while event 100 is running, and overwrites any other running
  event number (chronicletwo:ps2/src/sceneevent.cpp:134-155).
  Ixion events that stack (a station inside a talk) need explicit sequencing.
- **R5. Skipped stretches lose effects.** While skipping, `EXT` is not executed and jumps are
  not taken (chronicletwo:ps2/src/runscript.cpp:425-455, 700-702). Flags and map jumps placed in a
  skippable stretch do not happen. Conditional jumps also do not pop their operand while skipping
  (inference from the same code), so the operand stack can grow until the skip ends. The retail data
  presumably sets flags after the skip end; this was not checked against the bytecode.
- **R6. Storage aliasing.** The map-jump flags, the destination name and the door fields share
  storage with `event_data` (chronicletwo:ps2/include/scenesnd.hpp:391-412). Writing event data
  clears them, and writing them changes what `_GET_EVENT_DATA` returns (inference from the union).
- **R7. Host layout drift.** Runtime structs grow on the host (chronicletwo:ps2/include/runscript.hpp:190-196,
  352-363). `PrepareMonsterMemory` compensates for the monster arrays
  (chronicletwo:port/src/dng_event.cpp:16-25). The PS2-only size assert on `ED_EVENT_INFO`
  (chronicletwo:ps2/include/event_func.hpp:1148) does not run on the host, and that struct holds
  pointer fields (`npc_talk_text`, `dng_event_parts`); its host size was not checked (verify before
  adding fields).
- **R8. No script toolchain in the repo.** The `tools/compilers` tree holds MWCC linkers and
  assemblers for the PS2 build, not an `SB2` compiler or disassembler. Writing new bytecode means
  writing an assembler first (blocker for route 3 in "Adding an event").
- **R9. Binary tag tables are positional.** Binary-mode tags are read as an index into the tag
  table (chronicletwo:ps2/src/scriptinterpreter.cpp:478-487). Reordering a tag table breaks binary
  data built against the old order. Append new tags only.
- **R10. Duplicate tag name.** `FUNC_FIRE_DATA` appears twice in `map_tag`; the second entry
  (mapping to `mapFUNC_EFFECT_NAME`) is unreachable because the first match wins
  (chronicletwo:ps2/src/mapload.cpp:2169-2171; chronicletwo:ps2/src/scriptinterpreter.cpp:478-551).
  Inference from the search order; not exercised.
- **R11. Missing effect programs stall.** An effect whose program number is absent is never
  resumed and never deleted, since `prog_no` is only cleared when the program runs
  (chronicletwo:ps2/src/effscript.cpp:1005-1023). Inference from the step logic.
- **R12. Two call frames for effects.** `SetEffectScript` allots two call frames
  (chronicletwo:ps2/src/effscript.cpp:5565-5566). A third nested call exits the process
  (chronicletwo:ps2/src/runscript.cpp:175-180). Inference: a larger Ixion effect script would fail.
- **R13. Early return in finish.** `EdEventFinish` returns before resetting the event sprites, the
  event marker and the mouth-animation and motion state when there is no active camera (chronicletwo:ps2/src/event_func.cpp:3217).
  Inference: these would survive into the next event.
- **R14. Dungeon map jumps.** `RunMainEvent` handles END, SUB_MODE and GOTO only
  (chronicletwo:ps2/src/dng_main.cpp:2130-2143). A map-jump request from a dungeon event is consumed
  by `EventLoop` and then dropped, unless another path handles it. Verify before relying on it.
- **R15. Buffer budgets.** Dungeon scripts load into a 20000-unit buffer
  (chronicletwo:ps2/src/dng_main.cpp:296), and the editor's buffer is the same size
  (chronicletwo:ps2/src/editloop.cpp:603). The unit is taken as a 16-byte quadword (inference from
  `Alloc(size / 16 + 1)`, chronicletwo:ps2/src/event.cpp:70). The largest PAL map script is about
  310 KB, close to the 320 KB that gives. The largest dungeon `sys_script` file is about 361 KB; its
  load path was not traced.
- **R16. Event-object cross-talk.** Both towns and dungeons share the event-object handle table
  (32 handles) and the sequences, which `EdEventMapInit` and `EventSeqInit` reset on entry and end
  (chronicletwo:ps2/src/event_func.cpp:2790-2824, 3345-3360). Ixion code that keeps handles across
  a map change will see them cleared.

## Open questions

- Which retail commands and ids do the 1356 PAL `.stb` programs use, and how often? A census
  like the DC1 one (`c1-scripts-events.md`) would need an `SB2` decoder that the repo does not have.
- Do the two worlds share command numbers? The DC1 note should be checked before any cross-world
  program is run in either interpreter.
- Which story bit ranges does DC2 use? Without a census of `SET_FLAG` constants, Ixion cannot pick
  a safe range even in its own block.
- Does a dungeon ever receive `MAP_JUMP`, `GOTO_INTERIOR` or `GOTO_OUTSIDE` from an event, and if
  so, which code handles it (R14)?
- How does the static `EventScript` reach the port through the `asm` link name in
  `chronicletwo:port/include/stubs/event.hpp:4`? The mechanism was not traced past
  `kazarov:scripts/build/port_override.py`.
- What is the layout of `ED_EVENT_INFO` and `CScene` on the host, and are the pointer fields
  inside them covered by the header-fixup step?
- Does the per-map flag block (`CMapFlagData`) have a script path, or only the code path that
  treasure boxes use?
- Which dungeon `sys_script` files load through which path, and does any of them exceed the buffer?
