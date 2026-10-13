# Chronicle (DC1) scripts and events

## What this covers

How Dark Cloud's PC port runs its scripts and events: the bytecode virtual machine
(`CRunScript`), the three opcode tables that bind native functions to bytecode numbers,
the event lifecycle in towns, interiors and dungeons, the text and compiled map-layout
scripts (`.cfg` / `.cfb`), the message engine (`ClsMes`, `sysmes`, `CDngMessageMan`),
the trigger types that start events, and how script opcodes change maps, items, flags and
messages. The last section lists concrete Ixion integration points that avoid editing
`ps2/src`.

Not covered: the monster battle VM beyond its opcode table, the Dark Chronicle side, and the
rendering of message windows (only the state machine is described).

Method: source reading of `chronicle:` at the pinned master, plus a read-only static census
over the 285 extracted `.stb` files of the PAL data (inline analysis; nothing committed).
The census tracks operand-stack depth locally within each statement. Every `EXT` site in the
corpus resolved to a constant `PUSHCONST int` function number, so the call-site identities are
reliable; control-flow merges were approximated. Counts are "files containing at least one
call", not call totals.

## Key facts

- **One VM class, several instances.** `CRunScript` is the stack machine for everything.
  The town, interior, dungeon and system event VM is a single `static CRunScript
  EdEventScript` (chronicle:ps2/src/editloop3.cpp:2791). The monster battle VM is a separate
  table with `BtSetEventScript` (chronicle:ps2/src/runscript_opcodes.cpp:1583). The map-layout
  reader and several small units use a text tag interpreter, `CScriptInterpreter`
  (chronicle:ps2/src/editmapscript.cpp:641-644, chronicle:ps2/src/edit_in.cpp:2161-2166,
  chronicle:ps2/src/snd.cpp:3474, chronicle:ps2/src/textureanime.cpp:352).

- **Bytecode shape.** 12-byte instructions `{op, arg1, arg2}`; the `RS_OPCODE` enum names 29
  opcodes (chronicle:ps2/include/runscript.hpp:9-39). The DCFM notes count 31 in the retail jump
  table (refs/DarkCloud-Toolkit/docs/DC_STB_FORMAT.md, "The 31 opcodes"). Stack items are tagged int, float, string or
  pointer; 8 bytes on disc, 16 on the host. `EXT` consumes `a` stack items; the first is the
  native function number, the rest are its arguments (chronicle:ps2/src/runscript.cpp:602-607,
  chronicle:ps2/src/runscript.cpp:138-146).

- **Port VM.** The PC port reimplements `CRunScript::load`, `run` and `exe` in
  `port/src/runscript.cpp` (chronicle:port/src/runscript.cpp:95, :131, :172), and decodes the
  disc's 16-byte function records into host `funcdata` (chronicle:port/src/runscript.cpp:13-22,
  :31-38). `call_func`, `ret_func`, `ext`, `resume` and `skip` are still retail code compiled
  unchanged. This is the pattern Ixion would reuse.

- **Event opcode table.** `ext_func_info` in `editloop3.cpp` lists about 300 town/map opcodes
  (chronicle:ps2/src/editloop3.cpp:7980-8290). Numbers run 0–1002; 1001 and 1002 exist only in
  PAL builds (chronicle:ps2/src/editloop3.cpp:8287-8289).

- **Dungeon opcode table.** `ext_func_info` in `btsysscript.cpp` lists opcodes 1010–1101
  (chronicle:ps2/src/btsysscript.cpp:1097-1166). `AddSystemEventScript` adds them into the same
  global dispatch array as the town table (chronicle:ps2/src/btsysscript.cpp:1168-1193).

- **Shared dispatch array.** Both tables live in one global `int (*ext_func__2[1500])`
  (chronicle:ps2/src/editloop3.cpp:2807; extern at chronicle:ps2/include/editloop3.hpp:200).
  `EdSetEventScript` zeroes all 1500 entries, refills them from the town table, and calls
  `EdEventScript.ext_func(ext_func__2, 1500)` (chronicle:ps2/src/editloop3.cpp:8294-8344).

- **Monster table.** 91 opcodes in a separate 256-slot array, numbers 10–253
  (chronicle:ps2/src/runscript_opcodes.cpp:31, :1594, :1689-1717).

- **Census of opcode use, all 285 `.stb`.** (Not re-run in this check; unverified.)
  - 32 of the 308 edit-table entries are never referenced by a shipped script. Examples:
    `_GET_PADUP` (2), `_NEXT_EVENT` (5), `_EXIT_CODE` (9), `_GET_CHARA_POS` (64), `_GET_CHARA_ROT` (69),
    `_SGET_MAP_FLAG` (704), `_SSET_TIME` (721), `_SGET_TIME` (722), `_SADD_TIME` (723), `_TEST` (1000).
  - Dungeon-table entries never referenced: 1069, 1071, 1087, 1091, 1093, 1101.
  - Highest referenced number is 1100 (unverified). No reference lands in 1003–1009, 1102–1499, or 1500 and above.
  - Files using selected opcodes: `_SET_RETURN_CODE` (3) 77; `_MAP_JUMP` (15) 65; `_GOTO_INTERIOR` (6) 8;
    `_SSET_GAME_FLAG` (700) 32; `_SGET_GAME_FLAG` (701) 60; `_SITEM_GET` (702) 51; `_SSET_MAP_FLAG` (703) 9;
    `_SGET_MAP_FLAG` (704) 0; `_SET_WORK_FLAG` (705) 10; `_SSET_GAME_INT_FLAG` (711) 8;
    `_SGET_GAME_INT_FLAG` (712) 52; `_SSET_REQUEST_EVENT_FLAG` (713) 5; `_SADD_VISIT_MAP` (714) 2;
    `_SADD_MAXITEM` (717) 1; `_ITEM_GET_MES` (206) 50; `_RUN_SCRIPT_NO` (1061) 7;
    `_SET_EVENT_FLG` (1024) 7; `_SET_DUNGEON_MAP` (1051), `_LOAD_DUNGEON_MAP2` (1052), `_GO_DUNGEON` (1050) 7 each.
  - Opcode 1060 (`_GET_NOW_USER_ID`, a dungeon-table op) is also called from `gedit/s27/event.stb`,
    a town-type script. That call resolves only while a dungeon's table is installed (inference:
    probably harmless, worth checking).

- **Event start.** `EdEventInit(event, arena, program)` clears the message windows and return
  code, sets `event_no`, computes lighting, and calls `EdRunEvent`
  (chronicle:ps2/src/editloop3.cpp:8470-8540). `EdRunEvent` calls `RunEvent`, which calls
  `script->run(program)` (chronicle:ps2/src/editloop3.cpp:8568-8592). The port's `EdRunEvent`
  records the result explicitly (chronicle:port/src/runscript.cpp:126-129), because retail falls
  off the end of it.

- **Program numbers.** An `event.stb` holds a table of program ids (`RS_PROGDATA`) plus a main
  function. `CRunScript::run(no)` looks up `no`, or runs main for a negative id
  (chronicle:ps2/src/runscript.cpp:175-216). One file carries many numbered programs.

- **Per-frame stepping.** `EdEventMode` resumes the VM once per frame when no menu is open
  (chronicle:ps2/src/editloop3.cpp:8897). It finishes the event when `return_code > 0`
  (chronicle:ps2/src/editloop3.cpp:8965-8970). `_WAIT` yields until the next frame
  (chronicle:ps2/src/runscript.cpp:634-640).

- **Return codes.** `EdEventReturn`: 0 none, 4 interior, 5 dungeon, 6 continue, 7 outside,
  8 map jump, 9 talk, 10 exit, 11 fishing (chronicle:ps2/include/edit.hpp:12-21). Consumed by
  `EventMode` (chronicle:ps2/src/editloop.cpp:3591-3625).

- **Opcodes that set the return code.** `_SET_RETURN_CODE` (3) writes any value
  (chronicle:ps2/src/editloop3.cpp:3487-3490). `_GOTO_INTERIOR` (6) sets 4, storing the interior
  name and entrance (chronicle:ps2/src/editloop3.cpp:3497-3509). `_GOTO_OUTSIDE` (13) sets 7
  (chronicle:ps2/src/editloop3.cpp:3591-3595). `_MAP_JUMP` (15) sets 8
  (chronicle:ps2/src/editloop3.cpp:3602-3613).

- **Script map numbers are 1-based.** `_MAP_JUMP` subtracts one from its argument
  (chronicle:ps2/src/editloop3.cpp:3603). So do `_SADD_VISIT_MAP` (chronicle:ps2/src/editloop3.cpp:7394-7409)
  and `_SGET_REQUEST`. `_GET_OLD_MAPNO` adds one back (chronicle:ps2/src/editloop3.cpp:3616).

- **Map number routing.** `MapJump(map, event)` only stores `NextMapNo` and `StartEventNo`
  (chronicle:ps2/src/main.cpp:1053-1056). The main loop routes: below 200 an editor map, 200–299 a
  dungeon (local number `n-200`), 400 the opening, 800 and 801 title and movie, 1000 the save
  screen (chronicle:ps2/src/main.cpp:982-1032).

- **Town map directories.** For `MapNo` 0–8 the name is `gedit/e0<n+1>/`; for `MapNo` above 10 it is
  `gedit/s<NN>/`; 99 selects the interior test set (chronicle:ps2/src/editloop.cpp:718-741).
  The shipped data has `e01`–`e05` and a set of `s` directories. The port's `--jump edit:<map>`
  hook uses the same numbering (chronicle:docs/PC.md:548-556).

- **Town map layout.** `LoadEditMapData` reads `mapinfo.cfb` if it exists, else the text
  `mapinfo.cfg` beside it (chronicle:ps2/src/editmapscript.cpp:524-553,
  chronicle:ps2/src/editloop.cpp:776). The shipped tree has `.cfg` text only (verified: no `.cfb`
  in the extracted data). The text tag set is 61 tags (chronicle:ps2/src/editmapscript.cpp:301-430).
  A compiled `.cfb` is a stream of `[command number, typed arguments]` records
  (chronicle:ps2/src/editmapscript.cpp:603-628).

- **Doors and arrivals.** `ENTRANCE` and `MAPJUMP` tags create `ED_EVENT_POINT` records of type
  DOOR (chronicle:ps2/src/editmapscript.cpp:1575-1668). A door carries a destination name, a
  `map_no` (from `MAPJUMP`), a trigger range and a position. Town arrivals are placed by
  `EdSearchEvent(param, name, 0, time)`, which matches destination name and `map_no == 0`
  (chronicle:ps2/src/editloop.cpp:3755-3760, chronicle:ps2/src/editloop3.cpp:512-540). Interior
  arrivals pass `EdInteriorJumpID` instead (chronicle:ps2/src/editloop.cpp:1244).

- **Interiors.** `GotoInterior` reads `in/<name>/<name><m|e|n>`, with the suffix chosen by time
  period (chronicle:ps2/src/editloop.cpp:3706-3716). Its info file is parsed by the 15-tag
  interpreter in `edit_in.cpp` (chronicle:ps2/src/edit_in.cpp:2117-2166).

- **Town event triggers.** `EdMoveChara` evaluates them each frame (chronicle:ps2/src/ebattle.cpp:2215-2290).
  - Event points come from `EdGetEvent` (chronicle:ps2/src/editloop3.cpp:291-392). A point counts
    only if `CheckEventPoint` passes: enabled, not completed by a set map flag, frame visible, in
    its time window, and for item boxes, floor progress is met (chronicle:ps2/src/editloop.cpp:5620-5690).
    The selected point is the one with the smallest `trigger_range[0]`; the variable is named
    `nearest`, and the comparison is on the range (inference from the code).
  - Map event (`EVENT`, `side > 0`): runs event number `side` on proximity, with no button
    (chronicle:ps2/src/ebattle.cpp:2244-2246).
  - Item box: needs the confirm button (`PadDown(0x40)`). It sets the completion map flag to 1 and
    grants the item (chronicle:ps2/src/ebattle.cpp:2226-2236).
  - Ladder: needs the button; starts system event 1 (chronicle:ps2/src/ebattle.cpp:2249-2256).
  - Door (`DOOR`): destination `"dungeon"` runs event 130 on proximity. Any other door needs the
    confirm button and then runs `GotoInterior`, or an init event when `minimum_progress > 0`
    (chronicle:ps2/src/editloop.cpp:3857-3866).
  - Villager talk: a near villager with `talk_event_no > 0` and `talk_event_level != 0` starts the
    talk through `EdTalkModeInit` (chronicle:ps2/src/ebattle.cpp:2265-2270). With the button held
    and no point chosen, a near villager gives event 256 (chronicle:ps2/src/ebattle.cpp:2272-2276).
  - Ground polygon: with the button held and no villager near, the first non-zero `ground_kind`
    among polygons hit by a ray from the eye (chronicle:ps2/src/gameutil.cpp:1364-1404) runs as an
    event (chronicle:ps2/src/ebattle.cpp:2277-2278).
  - Automatic: landing on a polygon with `ground_kind > 0` runs that event once and clears the
    field (chronicle:ps2/src/editloop.cpp:1960-1963).

- **Villager talk events** come from the map-script tag `TALK_EVENT` (chronicle:ps2/src/editmapscript.cpp:1901-1906).
  At most 16 villagers per map (chronicle:ps2/src/editmapscript.cpp:1674-1675).

- **Event gating.** `EdDebugEventEnable` defaults to 1 and gates the start of events in both the
  town and interior loops (chronicle:ps2/src/edit.cpp:88, chronicle:ps2/src/editloop.cpp:1968,
  chronicle:ps2/src/edit_in.cpp:907). `EdSetEventScript` sets `event_enable = 0` when there is no
  common script, and `EdEventInit` then returns 0 (chronicle:ps2/src/editloop3.cpp:8296-8300,
  :8470-8540).

- **Start hooks.** The town loop consumes the globals `start_event_no` and `start_system_event`
  (chronicle:ps2/src/editloop.cpp:168-170, :1968-2000). The port reads the same globals
  (chronicle:port/src/editloop.cpp:86, :997-1030). Interiors use a file-static copy
  (chronicle:ps2/src/edit_in.cpp:157).

- **Dungeon triggers.** Floor events are `CDungeonEvent` slots (`name`, `radius`, `script_no`,
  `chara_no`, `key_id`, `switch_on`, `ext_mem`; chronicle:ps2/include/dungeoneventdata.hpp:13-28),
  laid out per map part by `SetupEvent` (chronicle:ps2/src/dungeoneventman.cpp). The main path
  that starts a script on a hit sets `BtEventInfo.script_no` and moves the task machine to
  `GAME_TASK_SCRIPT_START` (chronicle:ps2/src/dun/gameloop.cpp:5187-5200, :4455-4520).
  `SearchDataSlotPos` can return events with `chara_no == -1`, but that path starts only events with
  `chara_no != -1` (inference from the check at :5189).

- **Dungeon script requests do not nest.** `_RUN_SCRIPT_NO` (1061), `_OPEN_ENTRANCE_WINDOW`,
  `_ITEM_USE_WINDOW`, `_GO_DUNGEON`, `_SET_URA_DUNGEON` and `_OPEN_ESCAPE_WINDOW` only set
  `BtEventInfo.request`. The dungeon task machine services it after the VM yields
  (chronicle:ps2/src/btsysscript.cpp:578-625, :739-756; chronicle:ps2/src/dun/gameloop.cpp:4541-4600).

- **Dungeon exit mapping.** On exit, `selectMapNo` is mapped to a town map by a hard-coded switch
  (chronicle:port/src/dun/movechara.cpp:2151-2175; the retail copy is in
  chronicle:ps2/src/dun/gameloop.cpp near :4892). The switch has no default. Entering a dungeon
  from a town uses `MapJump(NowEditMap + 200)`, so the town's number is the dungeon id
  (chronicle:ps2/src/editloop.cpp:2030-2033).

- **Item grants.** `_SITEM_GET` calls `EdGetItem`, which converts the weapon numbering
  (`ConvertItemNo` / `TransWepNo`) and calls `CDngStatusData::GetItem`
  (chronicle:ps2/src/editloop3.cpp:7293-7303, chronicle:ps2/src/edit.cpp:2013-2031, :2174-2195,
  chronicle:ps2/src/dngstatusdata.cpp:343). `_SITEM_CHECK` uses the same conversion
  (chronicle:ps2/src/edit.cpp:2233-2243). `_SADD_MAXITEM` clamps the pack to 100 slots
  (chronicle:ps2/src/editloop3.cpp:7435; chronicle:ps2/src/edit.cpp:2201-2205). The item-get banner uses
  system message numbers `item_no + 100` (chronicle:ps2/src/sysmes.cpp:224-265).

- **Game flags** (`CSaveData`):
  - Game flags: 8192 bits (`game_flags[256]`), `_SSET_GAME_FLAG` and `_SGET_GAME_FLAG`
    (chronicle:ps2/include/savedata.hpp:138, chronicle:ps2/src/savedata.cpp:258-308,
    chronicle:ps2/src/editloop3.cpp:7249-7270).
  - Game integer flags: 32 ints (chronicle:ps2/src/savedata.cpp:310-325, chronicle:ps2/src/editloop3.cpp:7271-7292).
  - Map flags: 512 bits per map, for `map_no < 80` (chronicle:ps2/include/savedata.hpp:140,
    chronicle:ps2/src/savedata.cpp:327-390). Other map numbers return 0 and store nothing.
  - Work flags: 32 ints, runtime only (chronicle:ps2/src/editloop3.cpp:7319-7330).
  - Dungeon event flags: 50 bits (`_SET_EVENT_FLG`, chronicle:ps2/src/btsysscript.cpp:381-398).
  - Visit counts: `visit_map[80]` (chronicle:ps2/include/savedata.hpp:142,
    chronicle:ps2/src/savedata.cpp:521-533; `_SADD_VISIT_MAP` at chronicle:ps2/src/editloop3.cpp:7394-7409).

- **Map flag sense is inverted between script and engine.** `_SSET_MAP_FLAG` stores `(value == 0)`
  into the bit, and `_SGET_MAP_FLAG` returns the inverse of the bit (chronicle:ps2/src/editloop3.cpp:7305-7316).
  But `CheckEventPoint` and the item box treat a set bit as completed (chronicle:ps2/src/editloop.cpp:5635-5637,
  chronicle:ps2/src/ebattle.cpp:2227). So a script that writes 0 marks a map flag done. The DCFM
  externals notes record the same inversion for opcode 703 (refs/DarkCloud-Toolkit/docs/DC_STB_EXTERNALS.md).

- **Messages.** `ClsMes` is the text window (chronicle:ps2/include/clsmes.hpp:149-595). In-text
  control codes are `MES_CODE_NEWLINE = -0x100`, `END = -0xFF`, `SPACE = -0xFE`, `PAGE = -0xFD`
  (chronicle:ps2/include/clsmes.hpp, `enum MesCode`). Name inserts are `-0x506..-0x500`
  (chronicle:ps2/src/clsmes.cpp:1038-1040). Gaiji glyphs are `-0x300..-0x250`. Substitution codes
  0xEF–0xFE pick `mes_no[0..7]` (chronicle:ps2/src/clsmes.cpp:985-1010).

- **Message blocks.** A message file holds a count, a byte offset to the last text, then
  `(msgId, wordOffset)` pairs and 16-bit text (chronicle:ps2/src/clsmes.cpp:1239-1249,
  `GetTextLineDataTop`; `SetBuff` at :456-460). This matches the layout in the DCFM notes
  (refs/DarkCloud-Toolkit/docs/DC_STB_FORMAT.md, "Message block").

- **Town message windows.** `EdEventInfo.messages[8]` holds the windows. `_MES_MAKE(slot, msg,
  [value], [slot messages...])` shows one (chronicle:ps2/src/editloop3.cpp:5150-5190). The map's
  buffer is `<map>_<lang>.mes` (chronicle:ps2/src/editloop.cpp:327-366), or the block embedded at
  header offset 0x14 of `event.stb` when no file is loaded (chronicle:ps2/src/editloop3.cpp:8294-8314).
  System text is `meswin/system_a[_lang].mes` (chronicle:ps2/src/sysmes.cpp:126-143);
  `SetSystemMes` shows one-line messages with up to four numbers (chronicle:ps2/src/sysmes.cpp:330-363).

- **Skip.** During an event pause, Cross calls `EdEventSkip` (chronicle:ps2/src/editloop3.cpp:8838).
  Skip runs until an `UNSKIP` (0x1C) instruction. While skipping, `JMP`, `JZ` and `JNZ` are not
  taken, `JZ`/`JNZ` do not pop their condition, and `EXT` pops its arguments without calling
  (chronicle:ps2/src/runscript.cpp:327-346, :602-607, :641-648; the port matches at
  chronicle:port/src/runscript.cpp:250-266, :528-535, :567-574).

- **Ext return values.** `CRunScript::ext` prints "illegal function call" when a native returns 0,
  then carries on (chronicle:ps2/src/runscript.cpp:138-146).

- **Port overrides in the script area.** `port/src/btsysscript.cpp` overrides `BtSystemScriptLoad`,
  `BtSystemScriptRun` and `_ITEM_USE_WINDOW` (chronicle:port/src/btsysscript.cpp:33-84).
  `port/src/runscript.cpp` overrides the VM. `port/src/dun/movechara.cpp` overrides `DunMoveChara`,
  which contains the exit switch. `port/src/edit_in.cpp` overrides `SearchMapJump` and
  `GetMapJumpPos`. `port/src/editmapscript.cpp` overrides `CommandWATER_SHAKE`. The override rules
  are in chronicle:docs/PC.md, section "How port/src takes precedence".

- **External reference.** The DarkCloud-Toolkit notes (NTSC binary) give the same three dispatch
  arrays, the 1010–1101 dungeon range and the `.stb` container. They also include a text
  assembler, `app/stb/asm.mjs`, and a round-trip checker (refs/DarkCloud-Toolkit/docs/DC_STB_FORMAT.md,
  "Opcode stream", "External functions", "Assembling").

## How it works

**Bytecode and VM.** A compiled script is a 0x18-byte header, an id table of (program id,
funcdata offset) pairs, funcdata records (code offset, frame size, argument count, by-value
flags), then code and inline strings. The event VM has an operand stack of 128 slots and a call
stack of 512 records (chronicle:ps2/src/editloop3.cpp:8303). A call makes a frame whose
arguments are the caller's operand slots, so nothing is copied (chronicle:ps2/src/runscript.cpp:112-129).
`EXT` is a native call; its first operand selects the table slot. The VM checks only that the
number is below `ext_func_num` and that the slot is not null.

**Event lifecycle.**
1. A trigger (door, item box, talk, ground polygon, ladder, dungeon slot, or a start-number
   global) requests an event number.
2. `EdEventInit` resets state and calls `EdRunEvent`, which binds the event's program and calls `run(no)`.
3. `EdEventMode` resumes the VM each frame until it yields (`_WAIT`) or sets a return code.
4. A nonzero return code runs `EdEventFinish` and dispatches the request: map jump, interior,
   dungeon, talk, fishing, or continue.
5. Dungeon scripts use the request block (`BtEventInfo.request`) instead, and the dungeon task
   machine services it after the VM yields.

**Map change.** A map change is never done inside the VM. The script sets `NextMapNo` through
`MapJump` and returns code 8. The town or dungeon loop exits, and the main loop reads `NextMapNo`.

**Where scripts touch state.** Opcode families of the edit table, by number range:
- 0–18 control and return codes; 23–27 BGM at map jump; 32–75 scene and character loading;
- 130–160 NPCs; 192–209 messages; 256–269 clock, parts and checks; 320–336 objects;
- 384–390 talk; 416–442 camera; 500–529 draw, fade and light; 600–618 action sequences;
- 650–651 object animation; 700–725 flags, items, party and time; 800–826 sound;
- 900–903 pad and argument readers; 950–958 `EB_*` (name only); 994–1002 fishing, loading and PAL language.
- Dungeon table 1010–1101: floor state, objects, map files, monsters, event switches and flags,
  the entrance and escape windows, and battle items.
- Monster table 10–253: monster motion, collision, status, sound and shots.

**Map layout data.** Each town directory has `mapinfo.cfg` (or `.cfb`), `event.stb`,
`<map>_<lang>.mes`, a scene file and graphics. The layout parser fills the editor's
`EDIT_MAP_INFO`: parts, villagers (up to 16), event points (up to 256), water, sky, lights, time
tables and talk events (chronicle:ps2/src/editmapscript.cpp:524-700).

## Ixion hooks

1. **Ext fallback for new opcodes (preferred).** `port/src/runscript.cpp` already overrides
   `CRunScript::load`, `run` and `exe` (chronicle:port/src/runscript.cpp:95-172). Add a PORT_OVERRIDE
   of `CRunScript::ext(RS_STACKDATA *, int)`, whose retail body is at chronicle:ps2/src/runscript.cpp:138-146.
   For `args->i >= ext_func_num` (1500 for the event VM, 256 for the monster VM), route to an Ixion
   table; keep retail behaviour otherwise. This avoids timing against the shared array and leaves
   the table code untouched.
2. **Bytecode for Ixion scripts.** New programs need `EXT` sites with the new numbers. The
   DarkCloud-Toolkit text assembler can emit `.stb` (refs/DarkCloud-Toolkit/app/stb/asm.mjs; its
   "Assembling" notes give the relocation rules). Check its licence, and whether a compile step can
   be part of the Ixion build, before depending on it.
3. **Free slots in the shared array (fallback).** Numbers 1003–1009 and 1102–1499 have no shipped
   references (census; unverified). They can be written into `ext_func__2` (chronicle:ps2/include/editloop3.hpp:200)
   after `EdSetEventScript` and `AddSystemEventScript` have run. The natural dungeon hook is the
   port's `BtSystemScriptLoad` (chronicle:port/src/btsysscript.cpp:33-53). Towns have no port
   override of `LoadScript` (chronicle:ps2/src/editloop.cpp:327), so this route is more fragile.
4. **A station as a map.** Author a new `s<NN>` directory with a text `mapinfo.cfg` (the loader
   accepts text directly), an `event.stb` and `<map>_<lang>.mes`. Keep `MapNo` below 80, or its flags
   and visit counts silently do not persist (chronicle:ps2/include/savedata.hpp:140-142). Enter it
   with `_MAP_JUMP` from a shipped event, or with a port call to `MapJump`
   (chronicle:ps2/src/main.cpp:1053-1056).
5. **Arrival by destination name.** A DOOR point in the station's `mapinfo.cfg`, with a destination
   string and `MAPJUMP` id 0, is found by `EdSearchEvent` for normal town arrivals
   (chronicle:ps2/src/editloop.cpp:3755-3760). This is the cleanest hook for "Ixion arrives here".
6. **Starting a town event from port code.** Set the global `start_event_no` to an event number
   (chronicle:ps2/src/editloop.cpp:168; the port already declares it extern at chronicle:port/src/editloop.cpp:86).
   It is consumed when `EdDebugEventEnable` is nonzero (chronicle:ps2/src/editloop.cpp:1968).
   Interiors need an override, because their copy is static (chronicle:ps2/src/edit_in.cpp:157).
7. **Dungeon routing.** Override the exit switch in `DunMoveChara` (chronicle:port/src/dun/movechara.cpp:2151-2175)
   to send a dungeon id to a station map. Entering a dungeon from a town uses `MapJump(NowEditMap + 200)`
   (chronicle:ps2/src/editloop.cpp:2030-2033), so a station-to-dungeon route can call `MapJump(200 + n)` directly.
8. **Flags.** Use game flags for Ixion-only state (8192 bits; reserve a range), and game integer
   flags (32 ints) for counters. Avoid map flags above 79, and flag 0, which `EdSetMapFlag` ignores
   (chronicle:ps2/src/editloop.cpp:588-595).
9. **Items and messages from port code.** `EdGetItem` (chronicle:ps2/src/edit.cpp:2174) and
   `SetSystemMes`/`ItemGetMes` (chronicle:ps2/src/sysmes.cpp:224, :330) can be called directly.
10. **Testing.** `darkcloud --headless --jump edit:<map>` and `--jump dungeon:<n>` start in a map or
    dungeon, and `--give` grants items (chronicle:docs/PC.md:548-565). The port has no VM unit test
    (none under chronicle:port/src/tests). An Ixion VM test would run a small `.stb` through
    `CRunScript::run` on the host.

## Risks and blockers

- **One event VM.** Town, interior, dungeon and system events share `EdEventScript`
  (chronicle:ps2/src/editloop3.cpp:2791). Events cannot nest. A station event must wait until the
  running event finishes (`EdEventFinish`) and must not reload the VM mid-event.
- **Map numbering limits.** Persistent map state covers `MapNo < 80` (chronicle:ps2/src/savedata.cpp:327-390,
  :521-533). The directory name for `MapNo` 5–8 would be `e06`–`e09`, which the shipped data lacks;
  `MapNo` 9 and 10 match neither branch, so the name is left unchanged (chronicle:ps2/src/editloop.cpp:718-735;
  read from the branch conditions, not run). `TOWN_COUNT = 5` gates ground-based behaviour
  (chronicle:ps2/include/editground.hpp:20).
- **Dungeon ids equal town numbers.** Entering a dungeon from a town uses the town's `MapNo + 200`
  (chronicle:ps2/src/editloop.cpp:2030-2033). The exit switch lists only the seven shipped dungeons
  (chronicle:port/src/dun/movechara.cpp:2151-2175). A new dungeon needs changes in both places.
- **Map flag inversion.** Script and engine disagree about what a set bit means
  (chronicle:ps2/src/editloop3.cpp:7305-7316 against chronicle:ps2/src/editloop.cpp:5635-5637).
  Ixion must choose one convention per flag and document it.
- **Missing returns.** Several script ops fall off the end of non-void functions: `_SET_WORK_FLAG`
  (chronicle:ps2/src/editloop3.cpp:7319-7324), `_SATRA_PARTS_GET` (:7446-7450), `_SATRA_CHIP_GET`
  (:7452-7456), and `_RESET_MAIN_CHR` (chronicle:ps2/src/btsysscript.cpp:864-872). The port keeps them
  defined only through `-fno-strict-return` (chronicle:port/CMakeLists.txt:127-128). New Ixion ops must return explicitly.
- **Unbounded indices.** `GetGameIntFlag` and `SetGameIntFlag` check only the upper bound
  (chronicle:ps2/src/savedata.cpp:310-325), so a negative index writes out of bounds.
  `_MES_MAKE` copies every argument past the third into `mes_no`, which has 10 entries
  (chronicle:ps2/src/editloop3.cpp:5176-5180, chronicle:ps2/include/clsmes.hpp:216).
- **Skip semantics.** Skip mode does not take branches, and leaves `JZ`/`JNZ` conditions on the
  operand stack (chronicle:ps2/src/runscript.cpp:327-346). Any Ixion script with branches inside a
  skippable section may drift the stack. Keep skippable sections linear.
- **Dead opcodes.** `_NEXT_EVENT` and `_EXIT_CODE` write fields that nothing reads
  (chronicle:ps2/src/editloop3.cpp:3492-3495, :3538-3541; no readers in `ps2/src` or `port/src`).
  Do not use them as return channels. The census also shows 32 unused edit opcodes.
- **Duplicate-number hangs.** `EdSetEventScript`, `AddSystemEventScript` and `BtSetEventExtendTable`
  spin forever on a duplicate opcode number (chronicle:ps2/src/editloop3.cpp:8326-8330,
  chronicle:ps2/src/btsysscript.cpp:1176-1183, chronicle:ps2/src/runscript_opcodes.cpp:1703-1707).
  Any change to the static tables must avoid reusing a number.
- **Message control codes disagree on paper.** `clsmes` treats `0xFF00` as a newline
  (chronicle:ps2/include/clsmes.hpp, `MES_CODE_NEWLINE`). The DCFM notes read the same word as a
  per-message start marker (refs/DarkCloud-Toolkit/docs/DC_STB_FORMAT.md, "Codes"). Do not generate
  message text with that word until it is verified.
- **Missing message block.** `EdSetEventScript` reads header offset 0x14 as the embedded message
  offset without checking for zero (chronicle:ps2/src/editloop3.cpp:8305-8307). The DCFM notes say 97
  of 285 scripts carry one. A new `event.stb` with no embedded block and no `.mes` file reads the
  header as text.
- **Destructive name handling.** `EdMapJump` writes a NUL into the caller's name when its first
  lookup fails (chronicle:ps2/src/editloop3.cpp:562-580). Its `kind` and `index` arguments are unused.
- **Cast indices.** Scripts select party members by index 0–5 (`_SET_MAIN_CHR2`,
  chronicle:ps2/src/btsysscript.cpp:847-862; `_SGET_EQUIP_WEAPON`, chronicle:ps2/src/editloop3.cpp:7423-7433).
  A second cast would not fit these bounds (inference from the bounds; the characters work covers the cast).
- **Dungeon exit default.** The exit switch has no default, so `map_no` is uninitialised for any
  `selectMapNo` outside the seven shipped dungeons (chronicle:port/src/dun/movechara.cpp:2151-2175).
- **Fixed sizes.** Event points: 256 per map. Event references per map part: 8
  (chronicle:ps2/src/editmapscript.cpp:1576-1625). Message windows: 8. Villagers: 16. The
  nearby-villager search covers 10 (chronicle:ps2/src/ebattle.cpp:2203).

## Open questions

- Do retail scripts rely on skip-mode behaviour with branches, or is that path dead? A corpus
  check would need to locate `UNSKIP` placements.
- Which shipped town scripts use `_SET_RETURN_CODE` with 5 (dungeon) or 10 (exit)? Which use
  `_SET_EVENT_SW`? The census counted files, not values.
- How is `ED_EVENT_POINT.map_no` set for arrival doors in shipped maps? The census did not track
  `MAPJUMP` arguments.
- Are the PAL and NTSC event tables identical apart from 1001 and 1002? The DCFM notes are NTSC.
- Is `SearchDataSlotPos` ever used for `chara_no == -1` events, given the traced path ignores them?
- Does `gedit/s27/event.stb` reach `_GET_NOW_USER_ID` (1060) in a town context, where it would not resolve?
- `EdTalkModeInit` gates the villager proximity talk; its own button check was not traced.
- Which map scripts use the `if` construct of the text interpreter? The registry holds only one
  function (`test`), so Ixion authoring should avoid `if` until this is checked.
