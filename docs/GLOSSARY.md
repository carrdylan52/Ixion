# Glossary

Terms a newcomer meets across Dark Cloud, Dark Chronicle, their ports and the Ixion host. Each entry gives a one-line definition and the research note that explains it in detail. Note links are relative to `docs/research/`. The index of notes is in [research/README.md](research/README.md).

## Games and projects

- **Dark Cloud (DC1)**: The 2000 PS2 game, called Chronicle in its port. Its six playable characters are Toan, Xiao, Goro, Ruby, Ungaga and Osmond. See [data-catalog-dc1.md](research/data-catalog-dc1.md).
- **Dark Chronicle (DC2)**: The 2003 PS2 sequel, called ChronicleTwo in its port. Its playable characters are Max and Monica, plus the Ridepod and Monica's monster form. See [data-catalog-dc2.md](research/data-catalog-dc2.md).
- **Ixion**: The project that would host both games in one process, with a shared window, clock and travel between worlds. See [multi-game-host-design.md](research/multi-game-host-design.md).
- **Hop (v0, v1)**: The earlier milestone names for the Ixion host ABI and its first prototype. See [v1-board-window.md](research/v1-board-window.md).
- **Passenger**: The party, HP, gilda, thirst or DRY state and equipped weapon that a v1 traveller carries from one game to the other. See [v1-c1-passenger-state.md](research/v1-c1-passenger-state.md) and [v1-c2-passenger-state.md](research/v1-c2-passenger-state.md).
- **Station**: A town, field map, or dungeon floor a traveller can visit, identified by map number and data folder. See [v1-c1-runtime-warp.md](research/v1-c1-runtime-warp.md).

## Game terms

- **Georama**: The town-rebuilding system in both games, where the player restores a town's parts and buildings over time. In DC1 its progress is `georama[6]` in the save; in DC2 the five Georama towns each have a save slot. See [c1-towns-georama.md](research/c1-towns-georama.md) and [c2-towns-georama.md](research/c2-towns-georama.md).
- **Atla**: A DC1 floor object in dungeons, not an item, that places a Georama part when collected. Atla are registered per dungeon and floor in the save. See [c1-dungeons.md](research/c1-dungeons.md) and [crosswalk-items-world.md](research/crosswalk-items-world.md).
- **Geostone**: A DC2 stone on a dungeon floor, tracked as a floor flag rather than a carried item, that links to Georama rebuild requests. See [c2-dungeons.md](research/c2-dungeons.md) and [c2-towns-georama.md](research/c2-towns-georama.md).
- **Origin Point**: In the DC2 lore, a point in the past whose restoration makes the future version of a place exist, and which Griffon destroyed to stop a rebellion. See [lore-time-travel.md](research/lore-time-travel.md).
- **Ridepod**: The DC2 mech suit that Max rides, assembled from six scene parts with its own energy record. See [c2-characters.md](research/c2-characters.md).
- **Atlamillia**: The DC2 time keys (red, blue, gold) that let a holder move between eras. See [lore-time-travel.md](research/lore-time-travel.md).
- **Time Gate**: The in-world DC2 travel point where a red Atlamillia goes to the future and a blue one to the past. See [lore-time-travel.md](research/lore-time-travel.md) and [v1-time-gates.md](research/v1-time-gates.md).
- **Starglass**: A DC2 item that the lore presents as the route to the past; its source is unresolved in the notes. See [lore-time-travel.md](research/lore-time-travel.md).
- **Ixion train**: The DC2 time-travel vehicle, a scripted map pair (s36 to s39) switched on for chapters 6 and 7. See [c2-time-travel.md](research/c2-time-travel.md).
- **World map**: The DC1 travel page of 16 fixed places, and the DC2 `wldmap.cfg` POS graph with reachable flags. See [c1-worldmap-modes.md](research/c1-worldmap-modes.md) and [c2-time-travel.md](research/c2-time-travel.md).
- **Gallery of Time**: DC1 dungeon 5, whose floor labels show years. See [c1-dungeons.md](research/c1-dungeons.md).
- **Spheda**: A DC2 sub-game played on dungeon floors with per-floor prize tables. See [c2-subgames.md](research/c2-subgames.md).
- **Finny Frenzy**: The DC2 fish race, whose loop is an abort stub on the PC port, so it cannot be completed there. See [c2-subgames.md](research/c2-subgames.md).
- **Gilda**: The money in both games. See [c1-characters.md](research/c1-characters.md) and [crosswalk-characters.md](research/crosswalk-characters.md).
- **DRY**: The DC2 status bit for thirst, which DC1 models with a water gauge. See [crosswalk-characters.md](research/crosswalk-characters.md).
- **Monster form (badge)**: Monica's transformation in DC2, driven by ten badge families. See [c2-battle-monsters.md](research/c2-battle-monsters.md).
- **Medal (yarikomi)**: A DC2 dungeon challenge reward. See [c2-dungeons.md](research/c2-dungeons.md).
- **Map number (MapNo)**: The integer that names a town, field, or dungeon map. In DC1 it chooses the mode by range. See [c1-worldmap-modes.md](research/c1-worldmap-modes.md).
- **MapJump**: The call that moves the game to a new map number. See [c1-dungeons.md](research/c1-dungeons.md) and [c1-mainloop-control.md](research/c1-mainloop-control.md).
- **Event script (STB, SB2)**: The bytecode that drives map and battle events, with a 1500-slot table in DC1 and 696 scene commands in DC2. See [c1-scripts-events.md](research/c1-scripts-events.md) and [c2-scripts-events.md](research/c2-scripts-events.md).
- **Wldmap / POS record**: A DC2 world-map entry in `wldmap.cfg` that routes travel to a place. See [c2-time-travel.md](research/c2-time-travel.md).
- **Save slot / saves**: Each game keeps its own save image, with the DC1 image at 0x136A7 bytes and the DC2 image built from `CSaveData`. See [c2-save.md](research/c2-save.md) for the DC2 image.

## Engine terms

- **mglib**: The graphics and engine vocabulary (`MGBeginFrame`, `MGEndFrame` and related calls) shared in lineage by both games. See [engine-lineage-mglib.md](research/engine-lineage-mglib.md).
- **Frame**: The span between `MGBeginFrame` and `MGEndFrame`, in which a display list is recorded and rendered as the canonical image. The word also names the `mgCFrame` scene node. See [c1-render-present.md](research/c1-render-present.md) and [engine-lineage-mglib.md](research/engine-lineage-mglib.md).
- **Visual**: A renderable model object, such as `CVisual` or `CVisualVu1` in DC1 and the mg_visual face builder in DC2. Two DC1 headers declare `CVisual` with different layouts. See [engine-lineage-mglib.md](research/engine-lineage-mglib.md).
- **VU1**: The PS2 vector unit used for transforms and skinning. DC1 skins through `visualvu1.cpp`, and DC2 uses a VU1 palette limited to four influences per vertex. See [engine-lineage-models.md](research/engine-lineage-models.md).
- **Arena**: A quadword memory region that replaces a PS2 buffer, implemented in Kazarov as `ArenaBlock`. `ArenaClearAll` zeroes every live arena in the process. See [c1-memory-globals.md](research/c1-memory-globals.md) and [c2-memory-globals.md](research/c2-memory-globals.md).
- **Display list / canonical image**: The recorded draw commands for one game tick, rendered at `MGEndFrame` as the image that display frames interpolate from. See [c1-render-present.md](research/c1-render-present.md).
- **Clock tick and pump**: Kazarov's wall-time logic clock, which calls one tick callback and one idle hook on each wait. See [c1-mainloop-control.md](research/c1-mainloop-control.md).
- **Kazarov**: The shared host runtime (window, renderer, clock, audio, paths and SDK emulation) that each port builds against, pinned at a different commit per game. See [kz-runtime.md](research/kz-runtime.md) and [kz-build-data.md](research/kz-build-data.md).
- **Fiber**: The PS2 thread emulation scheduler, bound to the first thread that calls it. See [c2-mainloop-control.md](research/c2-mainloop-control.md).
- **MDS / MDT / MOT / WGT / BBP**: The model scene, model block, motion, weight and bone-matrix formats that the two games share as one family. See [engine-lineage-models.md](research/engine-lineage-models.md) and [formats-dcextractor.md](research/formats-dcextractor.md).
- **PACK / .chr**: The archive format that holds a character's model and motion files. See [engine-lineage-models.md](research/engine-lineage-models.md).
- **TIM2 / IMG / IM2 / IM3**: Texture container formats across the two games. See [formats-dcextractor.md](research/formats-dcextractor.md).
- **Mode / LOOP_EDIT / LOOP_DUNGEON**: The game state, such as town, dungeon, title or menu, that the main loop runs next. See [c1-worldmap-modes.md](research/c1-worldmap-modes.md) and [c2-mainloop-control.md](research/c2-mainloop-control.md).

## Port terms

- **PORT_OVERRIDE**: A tag on a PS2 `ps2/src` definition that the port replaces. `port_override.py` strips each tagged copy from the build and checks that the replacement matches a real definition. See [c1-build-link.md](research/c1-build-link.md) and [c2-port-docs.md](research/c2-port-docs.md).
- **Stubs**: The `port/include/stubs` headers that declare replacement symbols and renamed link names for PS2 SDK and game functions. See [c1-build-link.md](research/c1-build-link.md) and [c2-build-link.md](research/c2-build-link.md).
- **Truncations**: The audit of pointer and integer narrowing sites that break on PC addresses above 4 GiB, tracked in `docs/port/truncations.md`. See [c1-port-docs.md](research/c1-port-docs.md) and [c2-memory-globals.md](research/c2-memory-globals.md).
- **Canonical render / interpolation**: The rule that each tick is rendered once and display frames are interpolated between ticks. See [c2-render-present.md](research/c2-render-present.md).
- **Checkpoint**: A frame-end safe point, after the buffer flip and with no open recording or clock pump, where Ixion may park or switch games. See [multi-game-host-design.md](research/multi-game-host-design.md).
- **Singleton**: A process-wide global, such as the window, path config, settings prefix, clock slot or mixer, that two games in one process would share. See [c1-platform-io.md](research/c1-platform-io.md) and [c2-platform-io.md](research/c2-platform-io.md).
- **Symbol collision**: A duplicate name between the two builds, which a merged link must rename or namespace. See [symbol-collisions.md](research/symbol-collisions.md).
- **Datapack**: A loose-file override directory that the port reads ahead of the packed data. See [c2-characters.md](research/c2-characters.md) and [c2-data-loading.md](research/c2-data-loading.md).
- **Replay / headless run**: A scripted, frame-counted run with `--headless`, `--frames` and `--screenshot`, used for verification. See [replays-headless.md](research/replays-headless.md) and [c1-debug-testing.md](research/c1-debug-testing.md).
- **Jump (`--jump`)**: The debug or test option that starts a run directly in a town or dungeon, such as `town:<map>` or `dungeon:<n>[:<floor>]`. See [c2-debug-testing.md](research/c2-debug-testing.md).
