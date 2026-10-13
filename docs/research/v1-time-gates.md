# Time-travel triggers: where each game could ask Ixion to travel

## What this covers

Where, in each source game, an existing code path moves the player between eras or worlds, and where
the port could call the host's `request_travel` (reserved in ABI v1, `ixion_api.h`, `IxionHost`) instead
of, or after, the normal travel. Covers:

- ChronicleTwo (Dark Chronicle, DC2): the Gate of Time markers, the Ixion scripts and maps, the future
  towns and their exits, the world-map menu, and the message window a port can drive.
- Chronicle (Dark Cloud, DC1): the world-map travel page, scripted `_MAP_JUMP`, the Escape Powder
  dungeon exit, and the message path a port can drive. DC1 has no time travel, so its candidates are
  return-trip triggers.

Read-only research. Nothing was built or run. The DC2 event scripts are binary `SB2` programs; they were
read with a throwaway read-only parser (layout from `chronicletwo:ps2/include/runscript.hpp:156-222`,
opcodes from `chronicletwo:ps2/include/runscript.hpp:14-50`). Script results below are decoded facts
unless marked inference. The parser is not in any repo.

Citation forms: `chronicletwo:` (game code), `chronicle:` (DC1 code), `chronicletwo-data:` (extracted DC2
PAL data, not in git), `chronicle-data:` (extracted DC1 data), `ixion:docs/DESIGN.md` (design doc),
`ixion-abi:include/ixion_api.h` (ABI header). Existing research notes are cited by file name only.

## Key facts

### DC2 (ChronicleTwo)

- **The Gate of Time is a map game object, not a menu.** A static table places eight markers:
  red on map 0, 1, 2, 3 and blue on map 25, 26, 82, 102 (`chronicletwo:ps2/src/scenevillager.cpp:61-69`,
  struct at `chronicletwo:ps2/include/scenevillager.hpp:112-126`). Map numbers are the record indices of
  `chronicletwo-data:map/map1.cfg` (the `// N` comment on each record):
  - red: `g01` Sindain (0), `g02` Balance Valley (1), `g03` Veniccio (2), `g04` Heim Rada (3);
  - blue: `f01` Jurak Mall (25), `f02` Starlight Temple (26), `f03` Luna Lab (82), `f04` Gundorada
    Workshop (102).
  - Red sits in the present (Georama, type 1); blue sits in the future (type 5). The `f04` blue marker
    has position (0, 0, 0) (`scenevillager.cpp:69`), which looks like a placeholder (inference).
- **Markers are not drawn in Chapter 8.** `LoadGameObject` skips the red and blue slots when the
  chapter is 8 (`chronicletwo:ps2/src/scenevillager.cpp:1371-1374`, with the red and blue loads gated at `:1399` and `:1414`; enum comments at
  `chronicletwo:ps2/include/scenevillager.hpp:88-89`). Gates vanish for the late game.
- **Pressing action on a marker runs event 300 of the current map.** `GetMapEvent` takes the marker
  slot `0x78` from `GetGameObjectEvent` and, for action checks, sets `point_no = 300`
  (`chronicletwo:ps2/src/sceneevent.cpp:195-211`; `chronicletwo:ps2/src/scenevillager.cpp:1435-1480`).
  The town loop passes that to `RunEvent` (`chronicletwo:ps2/src/editctrl.cpp:1065-1092`).
- **The gate's own script does the jump (decoded; unverified here, the parser is not in any repo).** Event 300 of each gate map is a `MAP_JUMP`
  (ext 20) with jump point 1:
  - `g01` (`chronicletwo-data:map/g/g01/g01_1.stb`) to `f01`;
  - `g02` to `f02`; `g03` to `f03`;
  - `g04` (`chronicletwo-data:map/g/g04/g04_1.stb`) to `s39` (Operations Room), not `f04`;
  - `f01` to `g01`; `f02` to `g02`; `f03` to `g03`; `f04` to `g04`.
  The `g01` event also reads story flags 270 and 280 (`GET_FLAG`, ext 14) and `GET_ANALYZE` (ext 565)
  before the jump. No enum name for flags 270 or 280 was found in `chronicletwo:ps2/include/savedata.hpp`.
  The gate condition is therefore data-driven, and the branch structure was not fully mapped (inference).
- **`_MAP_JUMP` only sets a request.** It reads the jump point, the destination (a map index through
  `GetMapName`, or a string), and an optional event number (default 100), then sets
  `EdEventInfo.request = EVENT_REQUEST_MAP_JUMP` and returns
  (`chronicletwo:ps2/src/event_func.cpp:4093-4115`). The jump point is stored and has no reader
  (`chronicletwo:ps2/src/event_func.cpp:4094`; existing note `c2-scripts-events.md` concurs).
- **The map load happens one frame later, in the town loop.** `EditLoop` consumes
  `EVENT_REQUEST_MAP_JUMP`: `BurnEditParts()`, then `EditMapJump(SearchMapNo(jump_map_name))`, then
  the start event (`chronicletwo:ps2/src/editloop.cpp:1553-1560`; function starts at
  `chronicletwo:ps2/src/editloop.cpp:1007`). `EditMapJump(int)` is non-static
  (`chronicletwo:ps2/src/editloop.cpp:2713`) and calls `LoadGameObject` for the new map
  (`chronicletwo:ps2/src/editloop.cpp:2833`).
- **Event acceptance guard (correction to the existing note).** `CScene::RunEvent` is
  `if (event_run == 0 || (printf(...), event_no != 100))` then it accepts the request
  (`chronicletwo:ps2/src/sceneevent.cpp:134-155`). So a request is accepted when nothing is running or
  when the running event is not 100, and it is refused only while event 100 runs. The existing note
  `c2-scripts-events.md` (section "How it works", step 2) states the reverse. Treat the code as correct
  until a test shows otherwise.
- **Ixion scripts form a small graph (decoded, per program entry; unverified here).** Map names from `map1.cfg`:
  - `s59` Luna Lab (type 3) to `s37` on events 150 and 500;
  - `s53` Central Lab (Event, `trn2/s36` add-path) to `s37` on event 500;
  - `s37` Ixion (Engine Room) to `s38` Ixion (Guest Room) on event 202, and back;
  - `s37` to `s11` Kazarov Stonehenge (`trn2/s36`) on events 520, 530 and 16480, and `s11` to `s37` on
    502 and 1000;
  - `s37` to `s59` on event 500 (the way back to the Luna Lab);
  - `s11` to `s12` Moon Flower Palace Stop (`trn2/s36`) on event 520, and `s12` to `s11` on 590;
  - `s66` and `s71` (Moon Flower Palace Stop) to `s11` on 650 and 590; `s65` and `s68` to `s12` on 532;
  - `s30` Paznos (Bridge, type 5) to `f04` on event 600, landing at event 601; `s39` Operations Room
    (type 5) to `f04` on event 551.
  Event 600 is the debug-menu "Ixion Departs" script (named in the existing lore note); its message bank is
  `chronicletwo-data:event/e600/e600/e600.txt` (Shift-JIS, IDs 6000010 to 6000460; not quoted here).
- **Train add-path swap.** Chapters 6 and 7 replace `trn/train` with `trn2/s36` on every station
  (`chronicletwo:ps2/src/mapjump.cpp:302-306`, see `c2-time-travel.md`). `s11`, `s12`, `s34`, `s53`,
  `s58`, `s71` already carry `trn2/s36` (`chronicletwo-data:map/map1.cfg` add-path column).
- **Future towns cannot be left through the world map.** `MENU_MODE_WORLD_MOVE` is refused in future
  map types (5 and 6) with message 0x28 or 0x2E (`chronicletwo:ps2/src/menumain.cpp:2256-2272`).
  The world-move open path itself is `chronicletwo:ps2/src/menumain.cpp:1210-1211`.
- **No Starlight Temple destination menu exists in the code or in the scripts.** A census of every
  `f/` and `d/` program (ext 509 `_GOTO_MENU`, 63 `_GOTO_EDIT`, 62 `_GOTO_DNG`, 544
  `_FUNCTION_MAP_JUMP`) found none in an `f/` map (decoded; unverified here). The only future-town exits in scripts are
  the blue markers and scripted jumps such as `f02` to `s33` (event 510). The debug future select
  `FutureMapSelect` lists `f01` to `f04` (`chronicletwo:ps2/src/mainloop3.cpp:115-222`, existing note).
- **Message window from port code.** `ClsMes::MakeMesWin(char *str, int open, int reset_fade)`
  (`chronicletwo:ps2/include/nd_meswin.hpp:861`) is what `_MES_MAKE` calls for a string argument
  (`chronicletwo:ps2/src/event_func.cpp:9529-9600`, `RS_STR` case). The scene's message slot 0 is
  `EventMes1` (`chronicletwo:ps2/src/editloop.cpp:789`), reached with `GetEventMessage(index)`
  (`chronicletwo:ps2/src/event.cpp:454-462`). The town loop steps and draws `EventMes1` (slot 0) and the three system messages every frame
  (`chronicletwo:ps2/src/editloop.cpp:2151-2154`, `:2594-2595`). `_MES_CLOSE` clears a slot with
  `draw_speed` and `mes_no = -1` (`chronicletwo:ps2/src/event_func.cpp:9606-9616`).
- **Port overrides can replace an ext command by number.** `SetEventScript` copies the ext table and
  overwrites entries, for example `functions[EVENT_EXT_DNG_EFFECT_ALL_CLEAR] = ClearDungeonEffects`
  (`chronicletwo:port/src/event.cpp:93-116`). The same mechanism can replace `EVENT_EXT_MAP_JUMP` (20).
- **Visual assets for the time slip.** `chronicletwo-data:event/time_gate/{red,blue}/` holds the marker
  models (`tg_maru_*`, `tg_sita_*`), Atlamillia glow models (`atora_glare*`, `atora_shine*`), and warp
  models `c01b_warp.chr` (red) and `c02a_warp.chr` (blue). The script warp effect is `b06a_warp`
  (`chronicletwo:ps2/src/effscript.cpp:166-167`). Which events play the warp models was not traced
  (inference).

### DC1 (Chronicle)

- **No time travel; the time-themed content is a dungeon.** `DUNGEON_GALLERY_OF_TIME = 5`
  (`chronicle:ps2/include/dungeon.h:13`). Its dungeon exit maps to world map number 0x26
  (`chronicle:ps2/src/dun/gameloop.cpp:4894-4918`). `WORLD_PLACE_GALLERY_OF_TIME
  = 14` (`chronicle:ps2/include/battlemenu.hpp:296`).
- **World map (travel page).** The MOVE page is chosen by `NowGetGameFlagForBtlMenu` and includes
  `MENU_MOVE_WORLD_MAP` (`chronicle:ps2/src/battlemenu.cpp:393-398`). A town script's `_WORLD_MAP`
  (`chronicle:ps2/src/editloop3.cpp:3576`) sets `menu_mode = ED_MENU_WORLD_MAP`, and that menu case calls
  `InitMenuMove(MENU_MOVE_WORLD_MAP_DIRECT, ...)` (`chronicle:ps2/src/edit.cpp:2111-2112`).
- **World-map places.** `MenuGrobalMapNoTbl[16]` = {0, 200, 1, 201, 14, 2, 202, 3, 42, 203, 23, 4, 204,
  40, 205, 60} (`chronicle:ps2/src/battlemenu.cpp:8771`). Confirm sets
  `MenuMapJumpMode = MenuGrobalMapNoTbl[cursor]` (`chronicle:ps2/src/battlemenu.cpp:9229`). Repeating
  the current map is refused unless the mode is `WORLD_MAP_DIRECT`.
- **Hand-off from the editor.** `ED_MODE_MENU` calls `MapJump(MenuMapJumpMode, -1)` after the menu closes,
  then `RunSystemEvent(2, ...)` (`chronicle:ps2/src/editloop.cpp:1576-1578`).
- **Scripted `_MAP_JUMP`.** `map = arg - 1`, event defaults to -1, `MapJump`, and
  `return_code = ED_EVENT_RETURN_MAP_JUMP` (`chronicle:ps2/src/editloop3.cpp:3602-3611`).
- **Every map change is one sink.** `MapJump(int, int)` only writes `NextMapNo` and `StartEventNo`
  (`chronicle:ps2/src/main.cpp:1053-1057`). The port's `GameFollowMapJump()` translates `NextMapNo` into
  `mode` and `MapNo` (`chronicle:port/src/gameloop.cpp:403-445`). It is called from the mode switch
  (`chronicle:port/src/gameloop.cpp:365-377`) and from `:954`. The translation is: below 200 is edit,
  200 to 299 is dungeon, 400 is opening, 800 and above is title or movie, 1000 is save or ending.
  Nothing is loaded at that point.
- **Escape Powder.** `EscapeDungeonMode` returns `ESCAPE_DNG_POWDER` when the party holds
  `ITEM_ESCAPE_POWDER` (`chronicle:ps2/src/battlemenu.cpp:285-296`; item 175 at
  `chronicle:ps2/include/itemdata.hpp:270`). The powder is removed when the escape is chosen
  (`chronicle:ps2/src/battlemenu.cpp:9118-9119`). `ESCAPE_DNG_PAY`, `_POWDER` and `_FREE` are at
  `chronicle:ps2/include/battlemenu.hpp:254-256`.
- **Dungeon exit table.** `GAME_TASK_EXIT_FADE_WAIT` maps the dungeon to a town or sub-map
  (`chronicle:ps2/src/dun/gameloop.cpp:4886-4918`), calls `MapJump(map_no, -1)`, and sets
  `existFlag = 2`. The port mirror is `chronicle:port/src/dun/movechara.cpp:2145`.
- **Warp Powder is unresolved.** `ITEM_WARP_POWDER = 173` (`chronicle:ps2/include/itemdata.hpp:268`),
  but the item table comment reads "id 174" (`chronicle:ps2/src/itemdata.cpp:1926`). The same table labels Escape Powder as id 176, while the enum has `ITEM_ESCAPE_POWDER = 175` (`chronicle:ps2/include/itemdata.hpp:270`), so the table and the enum disagree by one for both powders and the table comments are not a reliable id source. No `ps2/src` use
  site was found by name. Its field effect was not traced.
- **Message window: numbered only.** `ClsMes::MakeMesWin(int mes_no)` is the only overload
  (`chronicle:ps2/include/clsmes.hpp:521`). There is no string overload. The system message API is
  keyed by number: `EdSetSystemMes(mes_no, count, position, input_key, args, value)`
  (`chronicle:ps2/src/edit.cpp:2299-2318`). It steps and draws through `EdSystemMesStep` and
  `EdSystemMesDraw` (`chronicle:ps2/src/edit.cpp:2397`, `:2426`), which `edit_in.cpp:1122-1123` calls.
  The draw function reloads the window's textures every frame (comment above `EdSystemMesDraw`).
- **Port text path exists.** `GameTextFile::Set(id, utf8)` builds a message file
  (`chronicle:port/src/gametext.cpp:417`). `GameText::Set(utf8)` lays the text out into its own `ClsMes`
  (`chronicle:port/src/gametext.cpp:503`, `:564-572`: `SetBuff`, then `MakeMesWin(0)`). `GameText::Mes()`
  exposes the `ClsMes` (`chronicle:port/src/gametext.hpp`, accessor on the class). The menus use
  `GameText::Draw`. A dialogue window would reuse the same `ClsMes` (inference from the class shape).
- **Save and town stations.** The existing notes `c1-worldmap-modes.md` and `c1-towns-georama.md` give the
  save slot and jump state (`SaveData + 0x1C8`, `main_select_menu_no`, `GameInit`); see the Risks below.

### Ixion design constraints that bind the hooks

- Boarding in DC2 is at the Luna Labs in Veniccio; DC1 boards at an "Ixion Halt" that is a Georama-style
  build, pre-placed at Norune by debug flag (`ixion:docs/DESIGN.md` section 3.1).
- The hub is the train. Its Engine car is "the only exit, back to the last world visited" (section 3.2).
- The time jump is decide, manifest, depart (write the bundle, then the slip), arrive. A failed load rolls
  back the weapon and refunds the fare (section 3.5).
- The ABI says `request_travel` is reserved for v1 (null in v0), and that `IxionTravel.destination` is the
  destination module's own startup jump, for example `town:10` (`ixion-abi:include/ixion_api.h`, `IxionTravel`
  and `IxionHost`). The header does not say that the destination handles the request on its own fiber at its
  next checkpoint (unverified). The v0 host notes describe checkpoints as the point where the host may switch
  games (`ixion:docs/HOP-V0.md`, "The pieces", section 4); the "Acceptance" and "Known limits" sections do not
  cover checkpoints.

## How it works

### DC2 gate, end to end

1. The player stands within 20 units of a marker (`chronicletwo:ps2/src/scenevillager.cpp:1458`, `mgDistVector` < 20).
2. Action is pressed. `GetMapEvent` (`sceneevent.cpp:157`) asks the maps first, then the game objects.
   If the marker slot `0x78` is active, it returns `point_no = 300`.
3. `editctrl.cpp:1065-1092` calls `RunEvent(300)`. The guard above decides whether it is accepted.
4. The town loop starts event 300 in the map's `.stb`. The script runs flag checks and then `MAP_JUMP`.
5. `_MAP_JUMP` sets `EdEventInfo`. The town loop's next iteration calls `BurnEditParts`,
   `EditMapJump`, and starts the destination's event 100 (default `event_no`).

### DC2 Ixion route

Boarding and story trips are also `MAP_JUMP` calls (`s59` to `s37`, `s37` to `s11`, `s30` to `f04`
on 600). Each one can be matched by name in the same ext hook, because the destination string is
stored in `EdEventInfo.jump_map_name` before the request is read.

### DC1 jump path

Every DC1 exit that reaches `MapJump` (world map confirm, scripted `_MAP_JUMP`, dungeon exit table,
the Escape Powder route through that table) passes through `GameFollowMapJump`, where `NextMapNo` is still
the retail value and `mode` and `MapNo` have not changed. A port hook placed there therefore sees
every DC1 exit once, with the old map still loaded.

## Trigger table

| Game | Trigger | Retail path | Recommended hook | State at the hook | Use for v1 |
|---|---|---|---|---|---|
| DC2 | Red marker (present Georama) | action, `GetMapEvent` point 300, script `MAP_JUMP` to `f0x` | ext 20 replacement, armed by `GetMapEvent` | script mid-run; `EdEventInfo` set; old map loaded | Primary return trigger: the gate is the in-game "go to the other era" |
| DC2 | Blue marker (future) | same, `MAP_JUMP` to `g0x` | same | same | Primary trigger, opposite direction |
| DC2 | Luna Lab boarding | `s59` event 150 or 500 to `s37` | ext 20 replacement by name | same | Candidate Ixion "board" |
| DC2 | Story trips | `s30` 600 to `f04`; `s39` 551 to `f04` | leave alone by default | same | Do not reroute in the first prototype |
| DC2 | Future-town world move | refused, `menumain.cpp:2256` | none | n/a | No trigger; gates are the only UI exit |
| DC1 | World-map confirm | `battlemenu.cpp:9229`, `editloop.cpp:1576` | `GameFollowMapJump` | `NextMapNo` set, mode unchanged | Return from DC1 to the Ixion Halt, or pick Halt as a place |
| DC1 | Scripted `_MAP_JUMP` | `editloop3.cpp:3602` | `GameFollowMapJump` | same | Event-driven return (boarding event) |
| DC1 | Escape Powder dungeon exit | `battlemenu.cpp:9118`, exit table `dun/gameloop.cpp:4894` | exit table (port mirror `movechara.cpp:2145`) | `existFlag` set; target map chosen | Return after a dungeon, consumes the powder |
| DC1 | Warp Powder | not traced | none yet | n/a | Open question |

## Proposed Ixion code

The signatures below are proposals. Retail names are the real ones. Where a retail function is
`static`, the port cannot override it by name; the design uses an ext-table replacement or a copied body
instead.

### A. DC2: replace the `MAP_JUMP` ext (ChronicleTwo port)

```cpp
// chronicletwo: port/src/event.cpp, anonymous namespace next to ClearDungeonEffects.
// Replaces _MAP_JUMP (ps2/src/event_func.cpp:4093) by number. Field-for-field copy of the
// retail parse, plus one Ixion check.
int PortMapJump(RS_STACKDATA *stack, int argc);

// Globals and helpers it touches (proposed, port-only):
//   struct IxionGateState { int from_map; };   // map the armed marker belongs to, -1 if none
//   extern IxionGateState IxionGate;
//   bool IxionGateRoute(int from_map, const char *jump_name, IxionTravel *out);
//   host->request_travel(host->user, IXION_GAME_DARK_CHRONICLE, &travel)  // the ABI call

int PortMapJump(RS_STACKDATA *stack, int argc) {
    EdEventInfo.jump_point = GetStackInt(stack++);
    switch (stack->type) {
        case RS_INT:
            strcpy(EdEventInfo.jump_map_name, GetMapName(GetStackInt(stack++), NULL));
            break;
        case RS_STR:
            strcpy(EdEventInfo.jump_map_name, GetStackString(stack++));
            break;
        default:
            return false;
    }
    EdEventInfo.event_no = argc > 2 ? GetStackInt(stack) : 100;

    IxionTravel travel;
    if (IxionGate.from_map >= 0 &&
        IxionGateRoute(IxionGate.from_map, EdEventInfo.jump_map_name, &travel)) {
        IxionGate.from_map = -1;               // consumed; one use per gate press
        host->request_travel(host->user, IXION_GAME_DARK_CHRONICLE, &travel); // enqueues only; IxionGateRoute must fill travel.size, to_game, destination (unverified design)
        EdEventInfo.request = EVENT_REQUEST_END; // no load; the script's RET ends the event
        return true;
    }
    EdEventInfo.request = EVENT_REQUEST_MAP_JUMP;  // retail behaviour
    return true;
}

// Install, in SetEventScript (chronicletwo:port/src/event.cpp:93-116), after the
// ClearDungeonEffects line:
//     functions[EVENT_EXT_MAP_JUMP] = PortMapJump;
```

### B. DC2: arm the gate (wrap `GetMapEvent`)

```cpp
// chronicletwo: port/src/sceneevent.cpp, PORT_OVERRIDE on CScene::GetMapEvent (line 157).
// Retail body is kept as PortRetailGetMapEvent through RETAIL_BRIDGES
// (chronicletwo:scripts/port/unit_copy.py:41-44 pattern, as used for ResetViewMode).
PORT_OVERRIDE int CScene::GetMapEvent(float *position, int check_type, CSceneEventData *event) {
    IxionGate.from_map = -1;                               // clear every check: no stale arm
    int hit = PortRetailGetMapEvent(position, check_type, event);
    if (hit && check_type == MAP_EVENT_CHECK_ACTION && event->event.point_no == 300) {
        // Only a marker hit arms the gate; map points numbered 300 (for example in f04) do not.
        if (GetGameObjectEventSlot(position) == SCENE_GAMEOBJ_SLOT_TG) {   // the retail call, see note
            IxionGate.from_map = GetMainMapNo();
        }
    }
    return hit;
}
```

Notes: `GetGameObjectEventSlot` is a hypothetical helper that runs the retail
`GetGameObjectEvent` (`chronicletwo:ps2/src/scenevillager.cpp:1435`) for the same `position` and
returns the slot. Calling it again also rewrites `event->rotation`, and `event->gameobj_no` for save points, not only
`event->position`. The proposal would also clear `IxionGate` in `EdEventEnd`
(`chronicletwo:ps2/src/event_func.cpp:3446`); retail `EdEventEnd` only calls `ResetMesFileBuffAll` and
`EventSeqInit`, so that clear is new code, not existing behaviour.

### C. DC2: one line in the event message window

```cpp
// chronicletwo: port/src/ixion_text_dc2.cpp (new).
// Shows one line in the town's event window (message slot 0). Valid only while EventScene is set,
// that is, inside a town or dungeon loop. Returns false when there is no scene message.
bool IxionShowLineDc2(const char *text);
void IxionCloseLineDc2();

bool IxionShowLineDc2(const char *text) {
    ClsMes *mes = GetEventMessage(0);                // chronicletwo:ps2/src/event.cpp:454
    if (mes == NULL) return false;
    mes->MakeMesWin((char *) text, 0, 1);            // nd_meswin.hpp:861, as _MES_MAKE does
    return true;
}

void IxionCloseLineDc2() {                           // as _MES_CLOSE, event_func.cpp:9606
    ClsMes *mes = GetEventMessage(0);
    if (mes != NULL) {
        mes->draw_speed = mes->GetDrawSpeedDef();
        mes->mes_no = -1;
        mes->text_ptr = NULL;
        mes->open = 0;
    }
}
// Caller: the gate hook in PortMapJump, before returning, so the line shows while the player is
// in transit. The town loop already steps and draws slot 0 (editloop.cpp:2151, :2594).
// Open: the text encoding the window expects (see Open questions).
```

### D. DC2: Ixion arrival (optional, for v1 arrival work)

```cpp
// chronicletwo: port/src/editloop_ixion.cpp (new), PORT_OVERRIDE on EditMapJump(int)
// (chronicletwo:ps2/src/editloop.cpp:2713), retail body kept as PortRetailEditMapJump.
int EditMapJump(int map_no) {
    int result = PortRetailEditMapJump(map_no);     // loads the map and its villagers, runs nothing
    if (result != 0 && IxionArrivalPending()) {
        IxionOnArrive(map_no);                      // apply the passenger record here, not earlier
    }
    return result;
}
```

State at this point: the new map is loaded, `EdEventInfo.event_no` is still set, and the event has not
started. Applying the passenger record here is valid. Starting the event is the caller's job.

### E. DC1: one translator for every map jump

```cpp
// chronicle: port/src/gameloop.cpp, top of GameFollowMapJump() (line 403).
// Returns true when the host has taken the jump; the jump is then dropped, nothing loads.
bool IxionTakeMapJump(int map_no, int event_no);   // proposed, port/src/ixion_hook.cpp

void GameFollowMapJump() {
    if (NextMapNo >= 0 && IxionTakeMapJump(NextMapNo, StartEventNo)) {
        NextMapNo = -1;
        StartEventNo = -1;
        return;                                    // mode and MapNo stay as they were
    }
    if (NextMapNo < 0) {
        return;
    }
    // ... retail body unchanged ...
}

// Proposed body (port/src/ixion_hook.cpp):
//   bool IxionTakeMapJump(int map_no, int event_no) {
//       if (!IxionReturnArmed() && !IxionWorldPlace(map_no)) return false;
//       IxionTravel travel = {sizeof travel, IXION_GAME_DARK_CLOUD, "..."};  // to_game is the origin here, not the destination (unverified which game is meant)
//       host_request_travel(&travel);               // enqueue; origin parks at its checkpoint
//       return true;
//   }
```

The origin game must be consistent when it is parked. Leaving the Halt town as it is, with the map still
loaded, is the simplest parked state (inference). The return path (Engine car exit) would then restore
the same town.

### F. DC1: mark an Escape Powder exit as an Ixion return

```cpp
// chronicle: port/src/dun/movechara.cpp, the GAME_TASK_EXIT_FADE_WAIT case (line 2145 onward).
// Set before the table picks a town; the table is chronicle:ps2/src/dun/gameloop.cpp:4894-4918.
void IxionArmReturn(int reason);   // reason: ESCAPE_DNG_POWDER, or a script flag
// In the exit case, after the table has chosen map_no and before MapJump(map_no, -1):
//     if (IxionReturnArmed()) { IxionArmReturn(0); /* the jump is then taken in GameFollowMapJump */ }
// The powder is already removed at chronicle:ps2/src/battlemenu.cpp:9119 by then.
```

### G. DC1: one line in a port-owned window

```cpp
// chronicle: port/src/ixion_hook.cpp (new). A separate ClsMes, not EditSystemMes, so retail
// system messages are not overwritten.
static GameText gIxionLine;          // port/src/gametext.hpp
static int      gIxionFrames = 0;

// Lays the line out once. Returns false only when layout fails (GameText::Set gives -1); characters that do not fit are counted, shown as '?', and the call still returns true.
bool IxionShowLineDc1(std::string_view utf8, int frames) {
    if (gIxionLine.Set(utf8) < 0) return false;
    gIxionFrames = frames;
    return true;
}

// Per frame, from the port's town draw path (after the window textures are reloaded, as
// EdSystemMesDraw does at chronicle:ps2/src/edit.cpp:2426-2440):
//   if (gIxionFrames > 0 && --gIxionFrames == 0) { /* hide */ }
//   gIxionLine.Mes().DrawMesWin();
```

## Risks and blockers

- **The existing scripts note is inverted on the `RunEvent` guard.** `c2-scripts-events.md` says a
  request is dropped when a non-100 event is running. The code (`sceneevent.cpp:135`) drops it only when
  event 100 runs. Any hook that depends on the guard needs a test. Do not cite the note for this.
- **`EVENT_REQUEST_END` is not verified as a clean cancel for a `MAP_JUMP`.** `PortMapJump` returns
  true with `request = END` after queuing a host travel. The script's trailing `RET` should end the
  event. The town loop's END case sets `return_to_player = 1` (`chronicletwo:ps2/src/editloop.cpp:1543-1545`),
  but the path through `EdEventEnd` (`chronicletwo:ps2/src/event_func.cpp:3446`) was not traced.
- **Arming depends on `GetMapEvent`'s call order.** The gate arm is cleared at every `GetMapEvent`, which
  runs every frame for touch and action checks (`sceneevent.cpp:157`). A press that does not reach
  `RunEvent` leaves nothing armed. A marker touch without action does not arm either, because the
  `point_no == 300` test requires `MAP_EVENT_CHECK_ACTION`.
- **Gates vanish in Chapter 8.** `LoadGameObject` skips markers when the chapter is 8
  (`chronicletwo:ps2/src/scenevillager.cpp:1371-1374`, loads gated at `:1399` and `:1414`). Any gate-based v1 trigger is limited to chapters 1 to 7 unless another
  trigger is added.
- **Event 300 is not unique to gates.** Map points numbered 300 exist in several maps (for example
  `f04`, `s06`, `d01`; unverified here), so the arm test must include the marker slot, as in section B.
- **Heim Rada's gate goes to `s39`, not `f04`.** This is the decode of `g04_1.stb` event 300. A second
  method (a play-through, or a check of its flags) is needed before the route table is trusted.
- **Future towns have no world-move exit.** Any v1 "board" or "return" UI must be placed where a
  gate or script can reach it. Adding a world-move entry is refused by `menumain.cpp:2256`.
- **DC2 message encoding is unknown.** `MakeMesWin(char*)` is fed Shift-JIS script bytes by `_MES_MAKE`.
  The English PAL font path and whether ASCII is accepted were not verified. A port string must be
  tested before use.
- **DC1 has no literal-string message window.** `ClsMes::MakeMesWin` takes a number only
  (`clsmes.hpp:521`). The port text path (`GameTextFile`, `GameText`) is the only literal route, and it
  has been used for menus, not for a dialogue window in the traced code.
- **The DC1 Halt needs a placed object.** The design says it is a Georama-style build. How a build is
  added to a town (parts, plot records) was not traced. A script event at a fixed spot is the simpler
  first step.
- **`jump_point` has no reader.** A `MAP_JUMP` on the Ixion route cannot use it to place the player. The
  destination's event 100 sets the position (`c2-scripts-events.md`).
- **Passenger application must wait for the destination.** Applying the record in `PortMapJump` would run
  before the destination is loaded. Section D places it after `EditMapJump`.
- **Dungeon exits are a second table.** The retail dungeon exit map numbers (`dun/gameloop.cpp:4894-4918`)
  and their port mirror (`movechara.cpp:2145`) must change together.
- **Warp Powder and its effect are unknown.** The enum and the table disagree (173 vs 174 for Warp, 175 vs 176 for Escape), and the
  use path was not traced.

## Open questions

- Which flags 270 and 280 gate the red markers, and does the Chapter 8 cut-off (`SAVE_FLAG_CHAPTER_8`,
  `0x2E0`) match the marker skip? Needs a name table for the story flags.
- Do `GET_ANALYZE` (ext 565) with argument 103 and the flag tests decide whether a gate works at all, or
  only whether it shows? The full branch structure of event 300 was not mapped.
- Is the `f04` blue marker at (0, 0, 0) reachable in game, or a placeholder?
- Does the DC2 engine accept English text in `MakeMesWin(char*)`, and with which encoding? Check
  `chronicletwo:port/src/tests/font_test.cpp` for the expected inputs.
- Which DC1 world-map places should map to the Ixion Halt, and does `MenuGrobalMapNoTbl` have room for a
  new place (`WORLD_PLACE_COUNT`, `battlemenu.hpp:298`)?
- Where is `EdSystemMesStep` called in the town loop (only `edit_in.cpp:1122` was traced)?
- What does the Warp Powder (173 or 174) do outside a dungeon, and does a script use it?
- Does the DC1 `GameFollowMapJump` caller ever run with `NextMapNo` set and `mode` already changed, which
  would make the hook in section E unsafe?
- Is the DC2 Luna Lab (`s59`) the only Ixion boarding point, or do `s53` and `s37` also begin trips?
