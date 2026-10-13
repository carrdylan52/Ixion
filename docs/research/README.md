# Ixion research notes

Index of the research notes in this folder. Each note is read-only analysis of the two source games, their ports, or the shared host. Nothing here was built or run unless a note says so. Each note labels its own inference and fact-check status. Start with [GLOSSARY](../GLOSSARY.md) if a term is unfamiliar.

## Dark Cloud (DC1, Chronicle)

- [c1-battle-monsters.md](c1-battle-monsters.md): Damage runs through `CMonstorUnit::CheckDmg`, which the port does not override, and player hits share a 96-slot collision pool that overflows undefined.
- [c1-build-link.md](c1-build-link.md): The port is three OBJECT libraries linked into one executable, and a shared-library target would need the static-init, exit and singleton audit first.
- [c1-characters.md](c1-characters.md): The party is six fixed IDs reloaded through one `LoadChara2` path, so substituting data under an existing ID is the least invasive route to a new character.
- [c1-data-loading.md](c1-data-loading.md): All reads go through the PORT_OVERRIDE layer in `dataread.cpp` and one hash index, so a second data root needs a second index consulted on a miss.
- [c1-debug-testing.md](c1-debug-testing.md): The `--headless --jump ... --frames N --screenshot` path can boot a town or dungeon directly, though nothing in the note was run.
- [c1-dungeons.md](c1-dungeons.md): Dungeons are entered at `MapJump(200+D)`, and a direct floor jump is possible but has save side effects.
- [c1-items-weapons.md](c1-items-weapons.md): The item ID space, owner-routed weapon chains and chest tables are catalogued, and legacy weapon IDs 21 to 80 conflict between two mappings.
- [c1-mainloop-control.md](c1-mainloop-control.md): `RunGame` is terminal and holds all mode state in globals, so a host needs a split init and per-frame step API before it can drive the game.
- [c1-memory-globals.md](c1-memory-globals.md): PS2 quadword arenas are re-hosted as Kazarov arena blocks, and `ArenaClearAll` would wipe a second game's live memory unless it gets a domain.
- [c1-platform-io.md](c1-platform-io.md): Window, audio, clock, config and path singletons are process-wide, so two games in one process need per-game namespacing for each of them.
- [c1-port-docs.md](c1-port-docs.md): The port's own documentation digest, with the main drift being a stale 50 Hz plan against the 60-tick code.
- [c1-render-present.md](c1-render-present.md): One SDL window, one Kazarov renderer and one swapchain serve the game, and the fixed 640x480 logical size blocks sharing a renderer with Dark Chronicle.
- [c1-scripts-events.md](c1-scripts-events.md): The event bytecode VM has a 1500-slot table, and the port's `CRunScript::ext` path is the cleanest hook for new opcodes.
- [c1-towns-georama.md](c1-towns-georama.md): Towns are MapNo 0 to 4 with Georama progress stored in `CSaveData`, and villager rosters are reshuffled with `rand()` on each entry and not saved.
- [c1-worldmap-modes.md](c1-worldmap-modes.md): The mode machine is driven by `NextMapNo` ranges in `GameFollowMapJump`, and the world map is a battle-menu travel page rather than a separate map.

## Dark Chronicle (DC2, ChronicleTwo)

- [c2-battle-monsters.md](c2-battle-monsters.md): Combat is entirely retail `ps2/src` code, with a 115-row named damage table, so a crossover attack must match a row name or it silently does nothing.
- [c2-build-link.md](c2-build-link.md): The port builds OBJECT libraries linked into each executable, and about 30 process-exit sites would need redirecting before a shared-library build is safe.
- [c2-characters.md](c2-characters.md): Max and Monica are the only human bodies, and a third human needs a new roster ID, save layout change and several switch branches.
- [c2-data-loading.md](c2-data-loading.md): DC2 loads from `DATA.HD4`/`DATA.DAT` through a directory-walk index, and `IndexKey` strips any prefix before a colon, so a game prefix must be intercepted earlier.
- [c2-debug-testing.md](c2-debug-testing.md): The cheapest headless boot is `--jump town:<map>` with `--headless --offscreen`, but every boot needs a Vulkan device and real-data gates skip without a data root.
- [c2-dungeons.md](c2-dungeons.md): The seven dungeons, their floor graphs, geostone and medal flags, and the `--jump dungeon:<n>[:<floor>]` path are catalogued, with derived counts labelled.
- [c2-mainloop-control.md](c2-mainloop-control.md): `MainLoop` is a single blocking function on the main thread, so a host can suspend only at the post-`mgEndFrame` or mode-switch boundaries or by hoisting the loop state.
- [c2-memory-globals.md](c2-memory-globals.md): Save data and the main arena are single file-scope managers reclaimed on every loop entry, so cross-world data copied late is silently corrupted.
- [c2-platform-io.md](c2-platform-io.md): ChronicleTwo's host layer shares its env prefix, path config, window identity, mixer and clock slots with Chronicle, and 35 PORT_OVERRIDE symbols collide.
- [c2-port-docs.md](c2-port-docs.md): The port documentation digest, which names the test-hook jump parser and the mode dispatch as the main seams for a cross-world visit.
- [c2-render-present.md](c2-render-present.md): The window, Vulkan device, swapchain and renderer are process singletons, and the logical size is fixed at init, so one host must own the renderer.
- [c2-save.md](c2-save.md): The save is a raw `CSaveData` plus `CUserDataManager` image with 1/64-sampled check digits, and `SaveSlotRead`/`SaveSlotWrite` can take a bundle path without touching the catalog.
- [c2-scripts-events.md](c2-scripts-events.md): The `CRunScript` VM has 696 scene-event commands, and free IDs 1275 to 1499 let Ixion register native commands, though no SB2 compiler exists in the repo.
- [c2-subgames.md](c2-subgames.md): Side games sit behind one dispatcher, and the PC port's fish-race stub means Finny Frenzy cannot be completed on PC.
- [c2-time-travel.md](c2-time-travel.md): Time travel is a map-table and world-map system where future maps are types 5 and 6, and the Ixion train is a scripted map pair switched on for chapters 6 and 7.
- [c2-towns-georama.md](c2-towns-georama.md): Five Georama towns are positional map indices 0 to 4 with five save slots, so inserting a map shifts every later number and an append-only table is needed.

## Kazarov (shared host runtime)

- [kz-build-data.md](kz-build-data.md): The two Kazarov pins differ in layout, and a single superbuild is blocked by `CMAKE_SOURCE_DIR` use, duplicate target names and shared cache variables.
- [kz-runtime.md](kz-runtime.md): Kazarov has no host-wide context, so two games in one process need resets or a refactor across the renderer, clock, paths, mixer and scheduler.

## Engine lineage and formats

- [engine-lineage-mglib.md](engine-lineage-mglib.md): Both engines share the mg vocabulary and the MDT/MDS/IMG container layouts, but name flags, lights and shading diverge, and DC1 content into the DC2 engine looks like the more feasible direction.
- [engine-lineage-models.md](engine-lineage-models.md): The `.chr`, `.mds`, `.mot`, `.wgt` and `.bbp` formats are one family, and the main conversion costs are the info.cfg dialect and DC2's four-influence skin limit.
- [engine-lineage-maps.md](engine-lineage-maps.md): Model containers are partly readable across both games, but collision attributes, scripts and floor generators differ, so one engine per world is the realistic path for dungeons.
- [formats-dcextractor.md](formats-dcextractor.md): The DCExtractor specifications are a useful format reference, though several of its claims (TIM2 guard, HD3 names, MOT default branch) were not confirmed by running it.

## Data catalogues

- [data-catalog-dc1.md](data-catalog-dc1.md): Maps the DC1 PAL data tree to the six cast members, five towns, seven dungeons and their bosses, with some NPC names still unresolved.
- [data-catalog-dc2.md](data-catalog-dc2.md): Maps the DC2 PAL data tree (about 10,600 files) to the cast, the 189-record map registry, the dungeons and the Ixion shell assets, with four registered maps lacking files.

## Crosswalks and lore

- [crosswalk-characters.md](crosswalk-characters.md): Compares the six DC1 characters with Max and Monica, covering weapon owners, start HP and defence, and thirst against the DRY bit, and proposes a per-character roster record.
- [crosswalk-items-world.md](crosswalk-items-world.md): Proposes a world-prefixed item crosswalk and a draft station catalogue, noting that name matches across weapon classes are unreliable.
- [community-refs.md](community-refs.md): Surveys the community references and their licences, and warns that most community memory addresses are NTSC-U while the workspace discs are PAL.
- [lore-time-travel.md](lore-time-travel.md): Atlamillia are the time keys, Starglass is the route to the past, and Ixion is a locomotive built at Luna Labs, though the fandom wiki pages were unreachable and the premise is marked as inference.
- [symbol-collisions.md](symbol-collisions.md): A single merged link would hard-fail on 664 duplicate names and silently change behaviour for four more, so `--allow-multiple-definition` must not be carried into an Ixion link.

## Hosting and testing

- [multi-game-host-design.md](multi-game-host-design.md): Recommends one host executable with two hidden-symbol game modules, each with a private Kazarov copy, parked at frame-end checkpoints.
- [replays-headless.md](replays-headless.md): ChronicleTwo has a full gate suite and replay corpus, while Chronicle has only basic flags, and `run_from_save.py` still checks for `manifest.txt`.

## Ixion v1 design notes

- [v1-board-window.md](v1-board-window.md): Proposes a host-drawn station window on SDL_Renderer, and shows that Hop v0's three DLLs must bind one shared SDL3 build.
- [v1-c1-passenger-state.md](v1-c1-passenger-state.md): Lists where DC1 keeps the passenger state (party, HP, gilda, water, weapon) and proposes export and import bodies at the frame-boundary hook.
- [v1-c2-passenger-state.md](v1-c2-passenger-state.md): Lists where DC2 keeps the same passenger state (including DRY and the Ridepod) and which caches a write must refresh.
- [v1-c1-runtime-warp.md](v1-c1-runtime-warp.md): Shows which DC1 loop states can safely take a map jump from the frame-end checkpoint and proposes a `C1TravelRequest` form.
- [v1-c2-runtime-warp.md](v1-c2-runtime-warp.md): Shows how DC2 leaves its current loop for `LOOP_EDIT` or `LOOP_DUNGEON` at a frame end and proposes `C2TravelRequest` and an apply-at-checkpoint function.
- [v1-character-crossover.md](v1-character-crossover.md): Ranks four options for playing a character from the other game, from loading its model directly to a portrait-only passenger, with the native-logic cost of each.
- [v1-map-crossover.md](v1-map-crossover.md): Separates native travel, which needs no format work, from cross-world rendering of a town or floor, which does.
- [v1-time-gates.md](v1-time-gates.md): Finds the existing code paths in each game that move the player between eras or worlds, and where the port could call the reserved `request_travel`.
