# Ixion architecture options

Status: architecture decision draft, written after the Hop v0 prototype and the research pass in
`ixion/docs/research/`. It compares the ways two PC ports could become one game, recommends one,
says where it hooks into each port, and breaks the next wave of work into units.

## Conventions

- `chronicle:` is TheMoonPeople/Chronicle (Dark Cloud, DC1). Line numbers are for commit 86c2b4c8,
  the base of the Dark Cloud module (`port/src/ixion_plugin.cpp`), which lives on Chronicle's `ixion`
  branch.
- `chronicletwo:` is TheMoonPeople/ChronicleTwo (Dark Chronicle, DC2), `ixion` branch at e9d850c7.
- `kazarov:` is TheMoonPeople/Kazarov. Current layout (`src/cpp/`, `include/`) is main 9310c53, which
  ChronicleTwo pins as 3dc38ce. Chronicle pins the older layout a0a5ff8 (`port/`). The embedded-mode
  commits Hop v0 uses are 3366d98 (current layout) and a5bb691 (older layout); neither is on upstream
  main.
- `ixion/...` is this folder. `research/<name>.md` is a note in `ixion/docs/research/`.
- **inference** marks a claim reached by reasoning, not by reading code or running it. **unmeasured**
  marks a cost that nobody has measured yet.

## Summary

Keep the two engines separate and resident in one process, each game a hidden-symbol shared library
driven by a small host, as Hop v0 already does. Build the crossover on top of that in layers: a travel
request each game applies on its own fiber at a frame boundary, a plain-C passenger record that each
game exports and imports, a host-side ledger that translates it, and only later, offline converters
that turn one game's characters and map pieces into the other game's native formats. A single merged
binary and a port of one world into the other engine are both rejected as foundations: the first
fails on 664 hard link errors and a runtime built of process singletons, and the second means
re-implementing a game. Separate processes stay as the fallback, because the module ABI is POD-only
and can be carried over a pipe.

## 1. The options

### Facts every option has to face

- **Shared names.** The two executables share 3,013 defined symbol names. In linked mode 1,449 names
  are defined in both merged sets; a single link would fail on 664 (629 code, 35 data), silently bind 4
  strong-wins that change behaviour (`CCollision`, `CMap::Draw`) and silently first-win 781
  (`research/symbol-collisions.md`). Fifteen shared project classes have diverging method surfaces,
  and at least `CSaveData`, `CGamePad` and `ClsMes` diverge in layout (`research/c2-memory-globals.md`). `SaveData` is a
  pointer in DC1 (`chronicle:ps2/src/main.cpp`) and a whole record in DC2
  (`chronicletwo:ps2/src/mainloop.cpp`).
- **A runtime of singletons.** Kazarov has no host context object. Window, renderer (`extern Context
  g`, about 550 references), clock (one tick slot, one idle slot), path roots, settings prefix, texture
  catalog, mixer and PS2 thread scheduler are each one per process (`research/kz-runtime.md`).
- **Two Kazarov layouts.** Chronicle cannot configure against the current layout without path edits,
  and a pin bump changes shared host code substantially (`research/kz-build-data.md`).
- **Different logical frames.** DC1 renders 640x480, DC2 512x480, and the logical size is fixed at
  `RendererInit` (`research/c1-render-present.md`, `research/c2-render-present.md`).
- **Blocking main loops with process exits.** DC1's `RunGame` (`chronicle:port/src/gameloop.cpp:793`)
  and DC2's `MainLoop` (`chronicletwo:port/src/mainloop.cpp`) never return mid-game, and both games
  leave the process directly from inside the game stack (`std::exit` in DC2's `PumpHost`,
  `chronicletwo:port/src/main.cpp:215-217`; `_Exit`, `exit` and `abort` in
  `chronicle:port/src/runtime.cpp:11-17, 47-49` and in Kazarov fatal paths).
- **Different content.** Item numbers overlap (DC1 1-376, DC2 1-428), save records are fixed-size
  with six-wide DC1 party arrays and two DC2 human records, and the two engines read different script,
  collision and map formats (`research/crosswalk-items-world.md`, `research/engine-lineage-maps.md`).

### Option A: separate processes with a hand-off

**A1, cold hand-off.** One game runs at a time. A launcher writes a bundle, closes the origin and
starts the destination at the chosen place. This is the shape of the design draft's Phase 0
(`ixion/docs/DESIGN.md` section 6, "two launches with a bundle").

- Costs:
  - Every crossing is a cold boot: window, Vulkan device and pipeline cache, data index (DC2 walks
    7,511 files, `research/c2-data-loading.md`), arena commit and the game's own boot path. The design
    target is under 10 seconds (`ixion/docs/DESIGN.md` 3.5). Unmeasured.
  - Return is never frame-exact. The origin reboots from a save, and DC1 has no save on shutdown
    (`chronicle:port/src/main.cpp:450-466`), so the crossing must write a save first.
  - The only startup jumps are debug paths. DC1 `--jump` forces `DebugMode` on
    (`research/c1-debug-testing.md`). DC2 `GamePrepareJump` calls `InitSaveData`, sets `DebugFlag` and
    loads `dbg/pb.cfg` or `dbg/cap1.cfg` (`chronicletwo:port/src/test_hooks.cpp:162-219`). A
    non-debug "load this save, arrive here" entry has to be written in both games anyway.
  - DC1 saves are slot-indexed and checksummed (`CMemoryCardAccess::SaveToMc` and `LoadFromMc`,
    `chronicle:port/src/memorycardaccess.cpp:237, 275`; 1,223 block sums, `research/c1-save.md`).
    DC2 already has path-taking `SaveSlotRead` and `SaveSlotWrite`
    (`chronicletwo:port/src/save_slots.hpp:47-58`).
- Gains: no symbol work, no Kazarov change, full crash isolation.
- Blockers: none technical. The cost is the experience: a loading boot per crossing and no live hub.

**A2, warm processes.** Both games stay alive in two processes; a launcher shows one window, and the
hidden game waits at a frame-end checkpoint until told to resume.

- Costs: the same frame-end checkpoint as option B, plus an IPC channel, cross-process window
  activation and focus rules (inference: Windows foreground-lock rules apply), two SDL instances
  each opening the same gamepads, and passenger records serialised over the channel.
- Gains: crash isolation with frame-exact resume.
- Verdict: the fallback if in-process hosting proves unstable. The module ABI
  (`ixion/include/ixion_api.h`) passes only plain C types, so the same contract can be carried over a
  pipe.

### Option B: one process, each game a hidden-symbol module

Each game is built as a shared library that exports only `ixion_get_api` and keeps its globals and
its private copy of Kazarov inside. A host loads both, runs each on a fiber and switches at frame ends.
This is Hop v0 (`ixion/docs/HOP-V0.md`).

- Evidence: built and passing acceptance 1 to 4 on Windows. Both games boot in one process,
  `--auto-switch 120:20` makes twenty crossings, and a parked game's logic frames, clock ticks, map and
  position do not change while parked (`ixion/docs/HOP-V0.md`, Status).
- How the symbol problem disappears: `ixion_c2` links the same objects as the executable with
  `-Wl,--exclude-all-symbols` (`chronicletwo:port/CMakeLists.txt`, `IXION_BUILD_PLUGIN`). Same-named
  private globals in two DLLs link (probe in `research/symbol-collisions.md`), and Hop v0 shows them
  running side by side.
- How the singleton problem disappears: each module owns its own Kazarov copy, so each has its own
  window, renderer and logical size, clock, mixer, scheduler, path roots and texture catalog. Embedded
  mode (`kazarov:include/platform/embed.hpp` at 3366d98; `port/platform/embed.hpp` at a5bb691) hands
  SDL init and the event queue to the host, rebases the clock after a park (`ClockRebase`) and pauses
  the module's audio stream (`AudioOutputPause`).
- Costs:
  - Memory: both main arenas reserve and, on Windows, commit about 207 MiB together
    (`research/c2-memory-globals.md`); a DC1 dungeon's distinct arena keys reach about 181 MB reserved
    (`research/c1-memory-globals.md`); plus two Vulkan devices, two swapchains and two mixers. Total
    commit charge is unmeasured.
  - Two Kazarov layouts each carry the embedded-mode patch.
  - Windows only today: the host fibers and the scheduler's fiber adoption use the Win32 fiber API.
    A Linux host needs its own fibers and adoption (inference).
  - Shared SDL device state: both modules open the same gamepads and write LEDs, sensors and rumble
    (`research/v1-board-window.md`, risk 6).
  - Any module exit still ends the host (about 30 exit sites in DC2, `research/c2-build-link.md`).
  - DLL staging: one `SDL3.dll` (3.4.18, byte-identical in both games) is shared; `libunwind.dll` and
    `vulkan-1.dll` differ between the games and the first copy loaded wins silently
    (`research/v1-board-window.md`).
- Blockers: none fundamental. Travel, passenger state and exit containment are the remaining work.

### Option C: single static binary with symbol localisation

Link both games into one executable, renaming or localising every colliding name.

- Costs and blockers:
  - 664 hard errors and 785 silent bindings to resolve (`research/symbol-collisions.md`).
    `llvm-objcopy` rejects `--localize-symbol` and `--prefix-symbols` on COFF; only `--redefine-sym`
    works, so every object, archive member and mangled class name needs a generated rename list.
  - ODR divergence in shared classes is undefined behaviour, not a link error.
  - ChronicleTwo's Windows link uses `--allow-multiple-definition`
    (`chronicletwo:port/CMakeLists.txt:221-223`), which would turn the hard errors into silent
    first-wins if inherited.
  - One Kazarov copy means one pin (a dated Chronicle bump and a regression pass,
    `research/kz-build-data.md`) and, for two live games, an instance-based Kazarov that does not
    exist. The alternative, a sequential swap with `RendererShutdown` then `RendererInit`, drops every
    GPU resource at each crossing and has to switch the logical size (`research/kz-runtime.md`).
  - Static initialisers of both games run in one link order (61 init functions in DC1 alone,
    `research/c1-build-link.md`).
- Gains over B: one file. B already shares the address space.
- Verdict: rejected.

### Option D: port one world's content into the other engine

**D1, whole-world port.** Re-implement one game's towns, dungeons, party, items and scripts in the
other engine. The containers are one family (MDS 0x70 object records, MDT 0x40 headers, 80-byte PAK
entries, shared MOT, WGT and BBP layouts; `research/engine-lineage-models.md`), but almost nothing
above the containers matches:

- collision: DC1 explicit per-triangle sets against DC2 face-derived, material-coded collision;
  `CreateCollisionMDT` returns NULL for strip meshes (`chronicletwo:ps2/src/collision.cpp:565`);
- scripts: different event VMs and command tables, and no SB2 compiler in the repo
  (`research/c2-scripts-events.md`);
- floor generators: DC1's 20x20 grid against DC2's `CAutoMapGen` with 277 part entries
  (`research/v1-map-crossover.md`);
- skins: DC2's VU1 palette path takes at most four influences and 32 bones
  (`research/engine-lineage-models.md`), and only 2 of Toan's 17 mesh-owner bone names exist in Max's
  costume (`research/v1-character-crossover.md`);
- textures: DC2 reads PNG variants from the port catalog, and the extracted `.ipk` payloads are
  zero-filled (`research/v1-map-crossover.md`);
- systems: Georama, Atla against geostones, two item number spaces, two fixed save layouts.

Verdict: rejected as a foundation; it is rebuilding a game.

**D2, asset conversion.** Convert individual characters, pictures or map pieces offline into the
destination's native formats and let the destination engine load them. The lineage notes judge DC1
content into the DC2 engine the more feasible direction (`research/engine-lineage-mglib.md`).
Verdict: kept, as the content-crossover layer on top of B (section 2.5).

### Option E: hybrids

- **E1, B plus D2 (recommended).** Two resident engines joined by travel and a passenger record, with
  offline conversion for content crossover.
- **E2, B with A2 as the escape hatch.** Same ABI, carried over a pipe to a per-game child process if
  in-process hosting fails in practice.
- **E3, the hub.** A host-drawn board window (SDL_Renderer, no Vulkan;
  `research/v1-board-window.md`) for menus, plus DC2's own train maps (`s36` to `s39` and the `trn2/s36`
  add-on, `research/c2-time-travel.md`) as the in-world train. No third engine.
- **E4, one process with a sequential single-Kazarov swap.** Needs all of option C's link work.
  Rejected.

### Comparison

| | A1 cold | A2 warm | B modules | C one binary | D1 port |
|---|---|---|---|---|---|
| Frame-exact return | no | yes | yes | yes, if swapped live | n/a |
| Crossing time | cold boot (unmeasured) | window swap | one frame | renderer re-init | n/a |
| Crash isolation | full | full | none yet | none | n/a |
| Symbol work | none | none | export list only | 1,449 names | n/a |
| Kazarov work | none | embedded mode | embedded mode (done) | instance-based runtime | n/a |
| Memory | one game | two processes | two games, one process | one game plus swap | one game |
| State | design draft | not built | working prototype | rejected | rejected |

## 2. Recommended architecture

```
+--------------------------------------------------------------------------+
| L0 host: ixion.exe  (SDL owner, event router, fibers, board, ledger,     |
|          travel controller, bundle, exit policy)                         |
+--------------------------------+-----------------------------------------+
| L1 ixion_c1.dll (Dark Cloud)   | L1 ixion_c2.dll (Dark Chronicle)        |
|   private Kazarov (old layout) |   private Kazarov (current layout)      |
|   L2 C1 travel mailbox         |   L2 C2 travel mailbox                  |
|   L3 C1 passenger export/import|   L3 C2 passenger export/import         |
|   L4 data overlay for converted|   L4 datapacks / second index for       |
|      content                   |      converted content                  |
+--------------------------------+-----------------------------------------+
  host <-> module: ixion_api.h only (plain C, size-gated structs)
```

Two rules hold across all layers:

1. **Game state is touched only on the game's own fiber, at a frame boundary.** The host never reads
   or writes a module's globals. Host calls into a parked module only copy data into or out of a
   mailbox; the module services the mailbox when it next reaches its checkpoint. This extends the v0
   rule for `activate` (`ixion/include/ixion_api.h`).
2. **A parked game is frozen.** It does not run, its clock is rebased on resume, and nothing it owns
   is edited while it is parked. Round trips restore from the ledger, never from the destination's
   approximation (`ixion/docs/DESIGN.md` 4.1 rule 3).

### 2.1 L0: host

Existing (`ixion/host/host.cpp`): SDL init and the only event pump, `RouteEvent` (:271), the root
fiber and one fiber per game, `HostCheckpoint` (:171), `Travel` (:403, show and hide only), `MainLoop`
(:450), receipts (`LogReceipt`, :116) and `--auto-switch`.

To add:

- **Event routing fixes** (`research/v1-board-window.md` section 4): drop events for unknown window
  ids instead of sending them to the active game (`host.cpp:289-290`); split close-requested by owner;
  flush or mask input held across a crossing.
- **Board** (`ixion/host/board.cpp`): a hidden SDL_Renderer window listing stations from both games,
  receipts and the passenger manifest. F9 is free in both games and both Kazarov layouts.
- **Travel controller** (`ixion/host/travel.cpp`): the state machine in section 2.3, with timeouts,
  refusal reasons and rollback.
- **Ledger** (`ixion/host/ledger.cpp`): holds the raw origin passenger record (shadow), applies the
  data-driven translation rows (`ixion/docs/DESIGN.md` 4.5) in each direction, and computes write-back
  on return.
- **Bundle** (`ixion/host/bundle.cpp`): see section 2.4.
- **Exit policy**: a module that finishes or fails returns to the host (section 2.2); the host shows
  the reason and keeps the other game alive.
- **Debug travel**: F10 stays a raw switch for testing, but is refused while a passenger is abroad, so
  it cannot bypass the ledger.

### 2.2 L1: game modules

Each module is the unmodified game plus `port/src/ixion_plugin.cpp` and a few port-only hooks. Retail
units (`ps2/src`) stay untouched; file-static retail state is reached through the existing stub
headers: ChronicleTwo redeclares statics with link names (`chronicletwo:port/include/stubs/mainloop.hpp`),
and Chronicle gives statics global forwarders (`chronicle:port/include/stubs/editloop3.hpp`).

**ABI v2.** Append to `IxionApi` and bump `IXION_ABI_VERSION`; a host reads a member only when
`api->size` covers it, so v1 modules keep working:

| Member | Called by | Effect |
|---|---|---|
| `travel(const IxionTravel *)` | host, module parked | stores the request in the module's mailbox; returns at once |
| `travel_status(IxionTravelStatus *)` | host, module parked | idle, requested, leaving, arrived or refused, with a reason string |
| `stations(uint32_t index, IxionStation *)` | host, module parked | one station row: kind, native map, floor, floor count, reached flag, ASCII name, native jump string |
| `passenger_request(uint32_t op, const IxionPassengerV1 *in)` | host, module parked | queues an export or an import |
| `passenger_result(IxionPassengerV1 *out)` | host, module parked | result code and, for an export, the record |

`IxionHost.request_travel` goes live so that in-game triggers can ask the host to travel. The
`IxionStation` shape is the one proposed in `research/v1-board-window.md` section 6.

**Hook points per port.**

| Hook | Dark Cloud (chronicle) | Dark Chronicle (chronicletwo) |
|---|---|---|
| Run entry | `RunDarkCloud` in `port/src/main.cpp` | `RunGame` in `port/src/main.cpp` |
| Park checkpoint | `MGEndFrame`, after the buffer flip (`port/src/mglib.cpp:654`) | `mgEndFrame`, after the buffer flip (`port/src/mglib.cpp`, `PORT_OVERRIDE void mgEndFrame`) |
| Travel and passenger service point | `RunGame` frame loop after `GameCheckDebugToggle()` (`port/src/gameloop.cpp:952`), next to the developer-menu request | `MainLoop` right after `mgEndFrame(NULL)` and only when `mode_finished == 0` (`port/src/mainloop.cpp:339-344`) |
| Arrival point | `GiveOnArrival()` in the frame loop (`port/src/gameloop.cpp`, before `MGEndFrame`) for mode changes; the town or dungeon init for EDIT-to-EDIT | `GameGiveOnArrival` after `LoopInit` (`port/src/mainloop.cpp:259-260`); called by hand after an in-place town jump |
| Exits to contain | `port/src/runtime.cpp:11-17, 47-49`; Kazarov fatal paths in the older layout | `PumpHost` (`port/src/main.cpp:215-217`); the `--frames` exit in `mgEndFrame`; the script VM's `exit(-1)` |
| Receipts | `Inspect` in `port/src/ixion_plugin.cpp` | `PluginInspect` in `port/src/ixion_plugin.cpp` |

The service points are not inside `MGEndFrame` or `mgEndFrame`, because both are also called from
nested places: DC1's `EditLoop` interior and door branches (`chronicle:port/src/editloop.cpp:250, 544`)
and DC2's movie loop, loader, pause and menu capture (`research/v1-c2-runtime-warp.md`). Parking at a
nested frame end is fine; changing mode there is not.

**Exit containment.** Turn process exits into a return to the host. Two candidate mechanisms:
link-time `-Wl,--wrap=exit,--wrap=_Exit,--wrap=abort` on the module (does lld honour it for COFF? see
open question 1), or a Kazarov `EmbedFatal` hook called from the exit sites the ports own, with
`PumpHost` and the frame-budget exit checking `EmbedActive()` first. The wrapped function switches back
to the root fiber with a "finished" status and never returns to the game.

### 2.3 L2: travel and the time jump

**Inside one game (warp).** Both games already have a native route; Ixion only triggers it at a safe
moment and validates the destination.

- DC1 (`research/v1-c1-runtime-warp.md`). `MapJump` only queues `NextMapNo` and `StartEventNo`
  (`chronicle:ps2/src/main.cpp:1053`); the mode only changes when the mode returns non-zero. So:
  1. at the service point, if the safety predicate passes, set the mode's own exit flag
     (`exit_loop` in a town, as `EdExitLoop` does; `existFlag = 1` in a dungeon) and mark the
     request "leaving";
  2. the mode runs its own cleanup (`EditExit`, or the `existFlag` block at
     `chronicle:ps2/src/dun/gameloop.cpp:2048-2082`) and returns;
  3. immediately before `GameFollowMapJump()` (`chronicle:port/src/gameloop.cpp:962`), overwrite
     `NextMapNo` and `StartEventNo` with the travel target, which also overrides any `MapJump` the
     exiting mode wrote;
  4. for a dungeon floor, pass the floor instead of -1 to `InitDunEnterMenu`
     (`chronicle:port/src/dun/movechara.cpp:1812`), which takes the game's own `DUN_ENTER_DIRECT`
     path (`chronicle:ps2/src/menu_dungeon.cpp:425-459`).

  Safe states: town walk, talk or Georama; dungeon play or first-person with
  `BtGameModeFlag == BT_GAME_MODE_PLAY`. Defer during menus, events, interiors, dungeon scripts and
  fades. Refuse title, rush, opening, developer menu and the interior test (the full predicate is in
  the research note). This replaces the note's `MGEndFrame` phase tracking with two fixed points in
  `RunGame`, which is simpler and avoids the nested frame ends.
- DC2 (`research/v1-c2-runtime-warp.md`). `NextLoop` only writes `NextLoopNo` and `NextInitArg`
  (`chronicletwo:ps2/src/mainloop.cpp:349-352`). Town to town in place: `BurnEditParts`,
  `EditMapJump(map)`, `RunEvent(100)` (the world-move precedent, `chronicletwo:ps2/src/editloop.cpp:1377-1380`).
  Cross-loop: `PreExitLoop` (town) or one dungeon EXIT frame (`DngStatus.mode = DNG_STATUS_EXIT`, as the
  developer menu does at `chronicletwo:port/src/mainloop.cpp:287-292`), then
  `NextLoop(LOOP_EDIT | LOOP_DUNGEON, arg)` with `floor_no` and `event_no` set explicitly, then
  `mode_finished = 1`. Never call `GamePrepareJump` for travel. Validate before the request, because
  `EditMapJump` tears down event state before it can fail
  (`chronicletwo:ps2/src/editloop.cpp:2731-2751`).

**Across worlds (the time jump).** The host runs this sequence; each arrow is one or more host frames.

1. **Decide.** The player picks a station on the board, or an in-game trigger calls
   `request_travel`. The host checks that the origin is at a station state (module's `travel_status`
   or a dry-run flag) and that the destination station is reached.
2. **Manifest.** The host asks the origin for a passenger export, translates it through the ledger
   and shows CARRIED and LEFT BEHIND (`ixion/docs/DESIGN.md` 3.5).
3. **Depart.** The host writes the pending-crossing record (section 2.4), keeps the raw origin record
   as shadow, deactivates and parks the origin. The origin stays loaded where it is, which is the
   station the player will return to.
4. **Arrive.** The host queues `travel` on the destination, activates and resumes it, and waits until
   `travel_status` says arrived and the receipt's mode and map match. It then queues the translated
   passenger import, which the destination applies at its arrival point.
5. **Return.** The destination exports, the ledger computes write-back against the shadow, and the
   origin imports the result when it resumes. The origin's own values were never changed while it was
   parked, so there is nothing to debit and nothing is counted twice.
6. **Rollback.** A refusal, a timeout or a load failure before step 4 completes resumes the origin
   with no import and clears the pending record ("the weapon returns unchanged and the fare is
   refunded", `ixion/docs/DESIGN.md` 3.5).

**In-game triggers** (`research/v1-time-gates.md`):

- DC2: replace the `MAP_JUMP` ext by number in `SetEventScript`
  (`chronicletwo:port/src/event.cpp:93`), with a copy of the retail parse plus one check: if the
  armed gate or the jump name matches an Ixion route, call `request_travel` and end the event instead
  of loading. Gate markers resolve to event 300; Luna Labs boarding is the `s59` to `s37` jump.
- DC1: one translator at the top of `GameFollowMapJump` (`chronicle:port/src/gameloop.cpp:403`), which
  sees every exit (world-map confirm, scripted `_MAP_JUMP`, dungeon exit table, Escape Powder) once,
  with the old map still loaded. An "Ixion Halt" world-map place can use a reserved number in the
  currently ignored 300-399 range, which `GameFollowMapJump` has no branch for.

### 2.4 L3: passenger state bridge

**Record.** One plain-C header, `ixion/include/ixion_passenger.h`, shared by host and both modules.
The two research proposals differ (`research/v1-c1-passenger-state.md` has one weapon with five
elements and u16 gilda; `research/v1-c2-passenger-state.md` has two weapon slots, four elements,
durability and absorb). Reconcile into one record with world-tagged native ids: `home_game`,
`character`, `hp_ratio`, `max_hp`, `gilda` (int64), `thirst_ratio`, `status`, up to two weapon slots
with a five-wide element array and optional fields, and up to 16 items as `(world, native id, count)`.
Translation is the ledger's job, never the module's: a module exports and imports only its own world's
ids.

**Module side.**

| | Dark Cloud | Dark Chronicle |
|---|---|---|
| Live state | `SaveData->GetDngStatus()`, the one copy in the save; never `UserStatus`, which only `GameInit` assigns (`chronicle:ps2/src/dun/gameloop.cpp:1415`) | `GetUserDataMan()`, `CHARA_DATA`, `money`, `used_data` (`chronicletwo:ps2/include/userdata.hpp`) |
| Party and leader | `cur_chara`, `party_size` (`chronicle:ps2/include/userstatus.hpp:86-87`) | `active_chr_no`, `party_member` |
| Weapon write | `chara_weapons`, owner routing through `PortWeaponOwners` (`chronicle:port/include/stubs/dngstatusdata.hpp`) | `SetChrEquip`, then a visible-unit rebuild |
| Import timing | after `GameInit`, which refills HP and resets `cur_chara` unless `BtEventInfo.no_status_recover` (`chronicle:ps2/src/dun/gameloop.cpp:1418-1429, 2065-2081`) | after `LoopInit`, at `GameGiveOnArrival` |
| New file | `port/src/ixion_passenger.cpp` | `port/src/ixion_passenger.cpp` |

Every field a module reads or writes gets an `offsetof` static assertion, because the existing
assertions only check total sizes (`research/c1-save.md`).

**Ledger and translation.** Rows are data (`ixion/data/translate.tsv`, schema in
`ixion/docs/DESIGN.md` 4.5): HP as a ratio, defence as a fraction of cap, one gilda pool with the
excess over DC1's limit held, thirst against the DRY bit, ailments cleared except knocked out, and
weapons as loaners mapped through a class table (`research/crosswalk-characters.md`). Item keys are
always world-prefixed, because the two number spaces interleave (`research/crosswalk-items-world.md`).

**Saves (bundle).** Hop already passes each module its own `--save` root, and each module's path
roots live in its private Kazarov copy, so a per-module save root is per game, not per process. An
Ixion save is therefore a folder holding `dc1/` and `dc2/` save roots plus `ixion.json` (ledger,
manifest, pending-crossing record, generation counters). Each game saves natively into its own
sub-root, which satisfies "Ixion never writes to the native save slots" (`ixion/docs/DESIGN.md` 3.6)
without a save-to-path routine in DC1. Write order follows `ixion/docs/DESIGN.md` 4.6, and every host
write uses an atomic replace (the pattern of `kazarov:include/platform/files.hpp` `FilesWrite`). Known
side effect: DC2's soundtrack folder is derived from the save root's parent
(`research/c2-platform-io.md`), so the bundle layout must give each module its own parent.

### 2.5 L4: content crossover

Content crossover is one-way, offline and native: a converter in `ixion/tools/` reads one game's
extracted data and writes the other game's formats into a local overlay folder outside the
repository, which the destination engine reads with its own loader. No game data or converted asset
is committed.

**Overlay entry points.** DC1 indexes the data root with a `normalized/` overlay and resolves every
read through one lookup (`chronicle:port/src/dataread.cpp`, `Lookup`, `LoadFile2`, `LoadFileBG`).
DC2 replaces existing files through datapacks (`chronicletwo:port/src/platform/datapacks.cpp`), but only
for names already in the index, so new files need a second root or an index extension in
`DataReadIndex` (`chronicletwo:port/src/dataread.cpp:336-362`). DC2's `IndexKey` strips any text
before a colon, so a game prefix must be handled before it (`research/c2-data-loading.md`).

**Characters**, cheapest first (`research/v1-character-crossover.md`):

1. Portrait-only passenger. The host draws a still in the board from a decoded catalog PNG (DC2) or
   menu image (DC1). Matches the design's Phase 1. No game change.
2. Texture swap under an existing body, through the overlay. Blocked mainly by UV atlases.
3. Roster substitution under an existing id. DC1: every switch goes through `LoadChara2`
   (`chronicle:ps2/src/dun/gameloop.cpp:6871`) and `selectChrUnit` (`chronicle:ps2/src/btitem.cpp:80`);
   about fifteen per-slot `[6]` tables would move into one roster struct (`research/c1-characters.md`).
   DC2: `SetupMainUnit` (`chronicletwo:ps2/src/charasetup.cpp:140`) and `GetMainCharaModelName` choose
   files by character id, so a port override of the Monica branch redirects her files.
4. Converted body. Skeleton retarget, owner mapping, weight normalisation to four influences and 32
   drivers, and the three-row locomotion contract: DC1 rows 0, 1 and 2 (stand, run, walk; `keyCtrl`,
   `chronicle:ps2/src/clothread.cpp:537-566`), DC2 keys 立ち, 走り and 歩き
   (`chronicletwo:ps2/src/actionchara.cpp:1708-1722`). DC1's `EquipReAttach` dereferences the `weapon`
   bone with no NULL test (`chronicle:ps2/src/dun/gameloop.cpp:6555-6566`) and needs a guard first.

A seventh DC1 party member or a third DC2 human changes both save layouts and the DC1 battle ring
(six slots, `research/c1-characters.md`); Ixion substitutes under existing ids until a save-format
change is chosen deliberately.

**Maps**, cheapest first (`research/v1-map-crossover.md`):

1. Native travel only: each world's places stay in their own engine (section 2.3). This already
   delivers "visit any town or dungeon from either world".
2. Look only: carry the origin's background and fog colours into the destination's first frame.
3. One baked piece: convert one DC1 house (MDS, MDT, collision set) into a DC2 piece and add it to a
   copy of a DC2 map. Collision goes through a new `CreateCollisionFromDc1Set` at `LoadCollisionFile`
   (`chronicletwo:ps2/src/collision.cpp:456`), which needs a DC1-to-DC2 area-kind table nobody has
   designed. New DC2 places are appended after record 188 of `map/map0.cfg` to `map6.cfg` and to
   `wldmap.cfg` POS rows, never inserted, because map numbers are positional and stored in saves
   (`research/c2-time-travel.md`).
4. Whole towns or generated floors from the other world. Large, and last.

## 3. Prototype ladder

Each rung is the smallest demo that proves the next claim. "Build" means a C++ build of a game module
or the host; tools in Python do not count.

| Rung | Name | Demo | Build | Proves |
|---|---|---|---|---|
| 0 | Hop v0 (done) | F10 in Norune shows Palm Brinks; F10 again resumes Norune on the same frame; `--auto-switch 120:20` exits 0 | yes (done) | two engines live in one process |
| 1 | Paper manifest | a tool reads a DC1 `save.dat` and a DC2 save, applies `translate.tsv` and prints CARRIED and LEFT BEHIND for "Max boards with 50,000 gilda and a sword" | no | the translation rules on real numbers |
| 2 | Hop v0.1 | a module that exits (`--frames 300`) returns to the host, which stays up and keeps the other game; held keys are not replayed after a crossing | yes | crash and exit containment |
| 3 | Board | F9 opens a board listing both games' stations (static table) and the last receipts | host only | the host can present a combined world |
| 4 | Warp | from the board, pick Matataki: Dark Cloud leaves Norune through its own exit and arrives; pick a DC2 dungeon floor: Dark Chronicle loads it | yes | runtime travel inside each game |
| 5 | Crossing | in Norune pick Palm Brinks: one action parks Dark Cloud, warps Dark Chronicle and switches windows | yes | the cross-world travel controller |
| 6 | Passenger v1 | Max's gilda, HP ratio and one weapon arrive in Dark Cloud as a loaner; on return the original weapon comes back with written-back growth | yes | the ledger round trip in live games |
| 7 | Gates | walk into the Luna Labs boarding or a red time gate in DC2, arrive at Dark Cloud's Ixion Halt; leave from the Halt's world-map place | yes | in-world triggers instead of a debug board |
| 8 | Bundle | quit and reload an Ixion save mid-crossing; both games resume, the passenger is where it was | yes | crash-safe saves without touching native slots |
| 9 | Portrait passengers | the board shows Max's face beside the manifest; a one-line visitor message in a Dark Cloud town | host only, then yes | cheapest visible character crossover |
| 10 | First skin | Toan's slot shows a converted texture or Monica's slot loads another body through the overlay | yes, plus tool | character content through native loaders |
| 11 | First foreign piece | one Dark Cloud house stands in a copy of a Dark Chronicle map, drawn and walkable around | yes, plus tool | map content and collision conversion |
| 12 | Full vision | any character, any town or dungeon from either world, the train as hub | yes | the design's Phase 5 scope |

Rungs 1 and 3 can run in parallel with rung 2. Rungs 9 to 11 do not depend on 7 and 8.

## 4. Work breakdown for the next wave

Units are sized to be built and reviewed one at a time. Units marked "no build" can be written, reviewed and verified
without a C++ build of either game.

| Id | Unit | Depends on | Build |
|---|---|---|---|
| IX-01 | ABI v2 header and passenger record | none | no build (syntax check) |
| IX-02 | Station catalogue and checker | none | no build |
| IX-03 | Translation table and crosswalk seeds | IX-01 | no build |
| IX-04 | Paper manifest dry run | IX-03 | no build |
| IX-05 | Bundle format specification | IX-01 | no build |
| IX-06 | Module and staging checker | none | no build |
| IX-07 | Portrait candidate survey | none | no build |
| IX-08 | DC1 town and collision dumper | none | no build |
| IX-09 | Motion and bone inspector | none | no build |
| IX-10 | Ledger library with round-trip tests | IX-01, IX-03 | host only |
| IX-11 | Host routing and resume hygiene | none | host only |
| IX-12 | Board window | IX-02, IX-11 | host only |
| IX-13 | Exit containment | open question 1 | yes |
| IX-14 | DC1 runtime travel | IX-02 | yes |
| IX-15 | DC2 runtime travel | IX-02 | yes |
| IX-16 | DC1 passenger export and import | IX-01 | yes |
| IX-17 | DC2 passenger export and import | IX-01 | yes |
| IX-18 | Module ABI v2 plumbing | IX-01, IX-14, IX-15, IX-16, IX-17 | yes |
| IX-19 | Host travel controller | IX-10, IX-12, IX-18 | host only |
| IX-20 | DC2 gate and boarding trigger | IX-18 | yes |
| IX-21 | DC1 Ixion Halt trigger | IX-18 | yes |

### IX-01 ABI v2 header and passenger record

- Files: `ixion/include/ixion_api.h`, `ixion/include/ixion_passenger.h` (new),
  `ixion/include/abi_check.c` (new).
- Work: append `travel`, `travel_status`, `stations`, `passenger_request` and `passenger_result` to
  `IxionApi`; define `IxionTravelStatus`, `IxionStation` and the reconciled `IxionPassengerV1`
  (section 2.4); document the mailbox rule; bump the version and state the size-gated compatibility
  rule.
- Verify: `abi_check.c` compiles with `clang -fsyntax-only` as C99 and as C++17, with static
  assertions on every struct size and on the offset of each appended `IxionApi` member.

### IX-02 Station catalogue and checker

- Files: `ixion/data/stations.tsv` (new), `ixion/tools/stations_check.py` (new).
- Work: one row per station from the tables in `research/v1-c1-runtime-warp.md` (5 towns, loadable
  sub-maps, 7 dungeons, 16 world-map places) and `research/v1-c2-runtime-warp.md` (tier A towns, 7
  dungeons with floor records and rooms), with game, kind, native map, floor, jump string, reached-flag
  source and an ASCII name.
- Verify: the checker parses every jump string with each game's grammar, refuses DC1 `edit:99`, the
  folder gaps and floors at or above `{15, 17, 18, 18, 15, 25, 100}`, refuses DC2 floors without a
  room or at or above `{9, 16, 25, 21, 23, 29, 39}`, and prints counts that match the research tables.

### IX-03 Translation table and crosswalk seeds

- Files: `ixion/data/translate.tsv`, `ixion/data/weapon_classes.tsv`,
  `ixion/data/items_crosswalk.tsv`, `ixion/tools/translate_check.py` (all new).
- Work: rows in the `ixion/docs/DESIGN.md` 4.5 schema for every `IxionPassengerV1` field in both
  directions; weapon class map from `research/crosswalk-characters.md`; item seeds keyed
  `world:native_id` with EQUIV, ANALOG, CLASS or NONE (`research/crosswalk-items-world.md`).
- Verify: the checker validates enums, that every passenger field has exactly one row per direction,
  and that no item key lacks a world prefix.

### IX-04 Paper manifest dry run

- Files: `ixion/tools/saves/dc1_save.py`, `ixion/tools/saves/dc2_save.py`,
  `ixion/tools/manifest_dry_run.py` (all new).
- Work: read-only parsers for the passenger fields (DC1 image 0x136A7 bytes with version string and
  1,223 block sums, `research/c1-save.md`; DC2 only for fields whose offsets the research confirms,
  `research/c2-save.md`), then apply `translate.tsv` and print the manifest.
- Verify: on a fresh save from each game the DC1 checksums recompute to the stored values, the tool
  opens files read-only, and the printed gilda, HP and weapon match what each game shows in its menu.

### IX-05 Bundle format specification

- Files: `ixion/docs/BUNDLE.md` (new).
- Work: folder layout (`dc1/`, `dc2/`, `ixion.json`), manifest and ledger schema, pending-crossing
  record, generation counters, write order (`ixion/docs/DESIGN.md` 4.6), partial-bundle behaviour, and
  the soundtrack parent-folder rule.
- Verify: review against `ixion/docs/DESIGN.md` 3.6 and 4.6 and against each port's save-root use
  (`research/c1-platform-io.md`, `research/c2-platform-io.md`); every file a module writes under its
  save root is listed.

### IX-06 Module and staging checker

- Files: `ixion/tools/check_modules.py` (new), `ixion/host/build-windows.ps1`.
- Work: fail unless each module exports only `ixion_get_api` and every import of the host and both
  modules resolves to a staged DLL; stage `vulkan-1.dll` and DC2's FFmpeg DLLs, and pick one
  `libunwind.dll` (`research/v1-board-window.md`, staging table).
- Verify: run against the existing Hop v0 build output; the export check passes and the import check
  reports the currently missing loader and FFmpeg DLLs.

### IX-07 Portrait candidate survey

- Files: `ixion/tools/portraits.py` (new).
- Work: list DC2 catalog PNG keys for each playable character and DC1 menu images, decode them into a
  contact sheet in a local output folder outside the repository.
- Verify: the sheet exists and names, for Max, Monica and Toan, at least one image a reviewer reads as
  the character's face, or records that none exists (the kill condition in
  `research/v1-character-crossover.md`).

### IX-08 DC1 town and collision dumper

- Files: `ixion/tools/dc1_scn.py` (new).
- Work: Python reader for `scene.scn` PTS entries (`chronicle:ps2/src/dispctrl.cpp:19-38`) and for
  `MDT_COLLISION` sets (`chronicle:ps2/include/mdt.hpp:38-56`); print parts, triangle counts and a
  histogram of info indices and area kinds for one town.
- Verify: part names match the `BLD_PARTS` lines of that town's `mapinfo.cfg`, and the histogram is the
  input for the area-kind table (open question 10).

### IX-09 Motion and bone inspector

- Files: `ixion/tools/chr_inspect.py` (new).
- Work: walk a `.chr` pack, list MDS bones and mesh owners, and print DC1 `base.cfg` KEY rows or DC2
  `info.cfg` named keys; emit the locomotion key map.
- Verify: on Toan's and Max's packs the output reproduces the counts in
  `research/v1-character-crossover.md` (77 and 124 bones, 41 and 46 KEY rows).

### IX-10 Ledger library with round-trip tests

- Files: `ixion/host/ledger.hpp`, `ixion/host/ledger.cpp`, `ixion/host/tests/ledger_test.cpp` (new),
  `ixion/host/CMakeLists.txt`.
- Work: load `translate.tsv`, translate depart and return, keep the shadow record, apply write-back.
  No SDL and no game headers.
- Verify: the host test binary passes origin-to-destination-to-origin cases that restore shadow fields
  exactly, hold excess gilda, refuse a crossing with no living member, and write back loaner growth at
  the table's rate.

### IX-11 Host routing and resume hygiene

- Files: `ixion/host/host.cpp`.
- Work: the routing order of `research/v1-board-window.md` section 4; drop unknown window ids; clear a
  game's queued keyboard and button events on resume; refuse F10 while a passenger is abroad.
- Verify: `--auto-switch 120:20` still exits 0 with the existing modules; a scripted key held across a
  switch is not seen by the resumed game.

### IX-12 Board window

- Files: `ixion/host/board.hpp`, `ixion/host/board.cpp` (new), `ixion/host/host.cpp`,
  `ixion/host/CMakeLists.txt`.
- Work: the SDL_Renderer board from `research/v1-board-window.md`, reading stations from
  `stations.tsv` until modules export them.
- Verify: F9 toggles the board, closing it does not quit, receipts update at each switch, and both
  game windows keep rendering.

### IX-13 Exit containment

- Files: `kazarov:include/platform/embed.hpp`, `kazarov:src/cpp/platform/embed.cpp` and the older
  layout's `port/platform/embed.*`; `chronicletwo:port/src/main.cpp` (`PumpHost`),
  `chronicletwo:port/src/mglib.cpp` (frame-budget exit); `chronicle:port/src/runtime.cpp`; both
  `port/CMakeLists.txt` module targets.
- Work: settle open question 1 with the toy DLL, then implement wrap or hook; a finished module
  returns a status to the host instead of exiting.
- Verify: an embedded module started with `--frames 300` ends, the host logs the finish and keeps the
  other game running; standalone executables still exit as before.

### IX-14 DC1 runtime travel

- Files: `chronicle:port/src/ixion_travel.hpp`, `chronicle:port/src/ixion_travel.cpp` (new);
  `chronicle:port/src/gameloop.cpp` (split `ParseJumpSpec` out of `GameSetJump` at :565, poll after
  :952, override before :962); `chronicle:port/src/dun/movechara.cpp:1812`; a stub header exposing the
  town exit statics; `chronicle:port/src/tests/ixion_travel_test.cpp`.
- Work: request, safety predicate and two-point apply from section 2.3, plus a standalone debug option
  that requests a travel after N frames.
- Verify: unit tests for the parser whitelist and the predicate table; headless runs that travel
  `edit:0` to `edit:1` and `edit:0` to `dungeon:0:3` and capture a screenshot at arrival.

### IX-15 DC2 runtime travel

- Files: `chronicletwo:port/src/ixion_travel.hpp`, `chronicletwo:port/src/ixion_travel.cpp` (new);
  `chronicletwo:port/src/mainloop.cpp` (after :339); stub headers for `LoopMode`, `ControlMode`,
  `EventScript` and the memory-card manager (`chronicletwo:port/include/stubs/`);
  `chronicletwo:port/src/tests/ixion_travel_test.cpp`.
- Work: `C2TravelRequest`, `C2TravelApplyAtCheckpoint` and readiness checks from
  `research/v1-c2-runtime-warp.md`, with a re-entry guard around the dungeon EXIT frame and an expiry.
- Verify: unit tests for the allowlist and refusal states; headless runs from `town:10` to a second
  tier A town and to a dungeon floor, with arrival screenshots and receipts.

### IX-16 DC1 passenger export and import

- Files: `chronicle:port/src/ixion_passenger.cpp` (new), `chronicle:port/src/tests/ixion_passenger_test.cpp`.
- Work: export and import from `research/v1-c1-passenger-state.md` against `IxionPassengerV1`, with
  `offsetof` assertions and the import timing rule after `GameInit`.
- Verify: tests on a synthetic `CSaveData`: export, import, export gives the same record; dungeon-local
  key items never leave; gilda clamps at the u16 limit.

### IX-17 DC2 passenger export and import

- Files: `chronicletwo:port/src/ixion_passenger.cpp` (new),
  `chronicletwo:port/src/tests/ixion_passenger_test.cpp`.
- Work: export and import from `research/v1-c2-passenger-state.md`; exclude Core and Map items; refuse
  an import that would drop a displaced weapon.
- Verify: tests on a synthetic user-data manager covering the same round trip, the item exclusions and
  the no-room refusal.

### IX-18 Module ABI v2 plumbing

- Files: `chronicle:port/src/ixion_plugin.cpp`, `chronicletwo:port/src/ixion_plugin.cpp`.
- Work: implement the v2 members as mailboxes serviced at the service points; export station rows with
  reached flags from save state; fill DC1's character and place in receipts.
- Verify: a v1 host still runs both modules; a v2 host lists stations with correct reached flags on a
  fresh save and on a save with a second town visited.

### IX-19 Host travel controller

- Files: `ixion/host/travel.hpp`, `ixion/host/travel.cpp` (new), `ixion/host/host.cpp`,
  `ixion/host/main.cpp`.
- Work: the Decide, Manifest, Depart, Arrive, Return and Rollback sequence of section 2.3, with
  `--auto-travel` as the acceptance mode.
- Verify: `--auto-travel` crosses Norune to Palm Brinks and back five times, each arrival receipt
  matches the requested station, and the ledger round-trip check passes.

### IX-20 DC2 gate and boarding trigger

- Files: `chronicletwo:port/src/event.cpp`, `chronicletwo:port/src/ixion_gate.cpp` (new).
- Work: the `MAP_JUMP` ext replacement and gate arming from `research/v1-time-gates.md` (A and B),
  routing only the routes listed in a table and leaving story trips alone.
- Verify: with routing off, a time gate behaves as retail; with it on, using the gate produces one
  `request_travel` and no map load.

### IX-21 DC1 Ixion Halt trigger

- Files: `chronicle:port/src/gameloop.cpp` (top of `GameFollowMapJump`),
  `chronicle:port/src/ixion_hook.cpp` (new).
- Work: the translator from `research/v1-time-gates.md` (E) and a reserved 300-399 place number for the
  Halt.
- Verify: a scripted world-map pick of the Halt produces one `request_travel`, leaves `mode` and
  `MapNo` unchanged, and every other destination still loads normally.

## 5. Open questions and the cheapest experiment for each

| # | Question | Cheapest experiment |
|---|---|---|
| 1 | Does lld honour `--wrap=exit`, `_Exit` and `abort` when linking a COFF DLL with llvm-mingw, including calls from libc++? | A two-file toy DLL that calls `exit(3)`, linked with the wrap flags; check `llvm-readobj --coff-imports` and run it from a host that expects the wrapper |
| 2 | Is the commit charge of two resident games acceptable? | Run `--auto-switch` with both games in a dungeon and read private bytes and commit for the process |
| 3 | Do two `SDL_OpenGamepad` calls on one device share a handle, and is closing one safe? | A 40-line SDL program that opens one gamepad twice, closes one handle and keeps polling the other |
| 4 | Can a game stay parked for a long time (display change, sleep, device loss on a hidden window)? | Park one game for 30 minutes across a monitor change and a sleep, then resume and check presentation and audio |
| 5 | Does a host pick of `dungeon:<d>:<floor>` through `InitDunEnterMenu` work in DC1, and what are its save side effects? | A standalone headless run with a temporary hard-coded floor at `chronicle:port/src/dun/movechara.cpp:1812`, then compare `floor_reached` and the quest counter before and after |
| 6 | What do DC1 town event 128 and DC2 dungeon event 1010 do at an ordinary arrival? | Headless travel to each town and to floor 1 of each dungeon with a screenshot at arrival; decoding the scripts is the expensive alternative |
| 7 | Which DC2 places load safely at low story progress? | A sweep of the tier A list from a fresh save with `game_progress` set to each POS gate's minimum, logging load result and a screenshot per place |
| 8 | Do both games honour `--save` for every file they write (config, pipeline cache, captures, soundtrack)? | Run each module from an empty save root inside an empty parent and list every file created anywhere on disk during one boot and one save |
| 9 | Can the native saves inside a bundle drift from the ledger (player saves in one game, crashes in the other)? | Paper walk-through of the IX-05 write order against each failure point, then one forced kill per step on the bundle rung |
| 10 | What is the DC1-to-DC2 area-kind table? | IX-08's histogram for one town, set against DC2's `CCPolyAreaKind` values (`chronicletwo:ps2/include/collision.hpp:41`) |
| 11 | Which catalog PNG is a character's face? | IX-07 |
| 12 | Does the DC1 texture decoder take direct-colour TIM2 for a converted texture? | Replace one entry in a copy of Toan's IMG with a direct-colour TIM2 and run one headless dungeon frame |
| 13 | Is the hub better as DC2's train maps or as the host board alone? | `--jump town:<n>` into the Ixion Operations Room (`s39`) and the train cars (`s36` to `s38`) at the debug progress, with screenshots |
| 14 | Should the Kazarov embedded mode go upstream, and should Chronicle move to the current layout? | Configure Chronicle against current Kazarov in a scratch tree and count the edits `research/kz-build-data.md` predicts |
| 15 | What does a Linux host need? | Port `ixion/host/fiber_smoke.cpp` to `ucontext` on Linux and check resume order and floating-point control state, before touching the scheduler adoption |
| 16 | Are the DC2 save offsets past `edit_data` right? | An `offsetof` probe in the DC2 test binary for the fields `research/c2-save.md` lists, compared with the note |
