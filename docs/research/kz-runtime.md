# Kazarov host runtime: singletons, process-wide state, and two-game requirements

## What this covers

The host runtime that both ports link from Kazarov: the Vulkan renderer and display lists (`gfx`), the SDL
window, display, input, mouse, clock, paths and settings (`platform`), the audio output and retail MIDI mixer
(`audio`), and the SDK replacements (`sce`: eekernel and its threads, libpad, libmc, libcdvd, sifdev, sifrpc,
libgraph and the stubs). It records which objects are singletons or process-wide globals, whether any
instance or context exists that a second game could own, and what one process hosting both games would need
from Kazarov.

Pins and citation rules:

- `kazarov:` means the Kazarov tree at main 9310c53. ChronicleTwo's gitlink is 3dc38ce, and `git diff` of
  `src/`, `include/` and `cmake/` between 3dc38ce and 9310c53 is empty, so line numbers below hold for both.
- Chronicle's gitlink is a0a5ff8, an older layout (`port/gfx`, `port/platform`, `port/sce`, `port/audio`,
  `port/tests`, and `include/kazarov/port.h`). It is cited as `kazarov@a0a5ff8:<path>`. The singleton shapes are
  the same there. The API differs in ways that matter for two games: `RecordingKind` and the `texture_catalog`
  namespace do not exist at a0a5ff8, and `BeginRecording()` takes no argument
  (`kazarov@a0a5ff8:port/gfx/displaylist.cpp:1124`).
- `chronicle:` and `chronicletwo:` are the two game repositories, cited by repo-relative path.

## Key facts

### Ownership model

- There is no host-wide context object. The only host-level state holder that a caller can instantiate is
  `audio::Mixer` (`kazarov:include/audio/mixer.hpp:28`) and the per-list `DisplayList`
  (`kazarov:include/gfx/displaylist.hpp:137`, shared as `DisplayListRef`). Everything else is file-scope or
  function-static state, one copy per process.
- The renderer context is a single struct value `gfx::detail::Context g`, declared once
  (`kazarov:src/cpp/gfx/renderer.cpp:20`) and `extern` in `kazarov:include/gfx/context.hpp:344`. The public gfx API
  is free functions with no handle (`kazarov:include/gfx/gfx.hpp:113-143`, `:548-565`).
- Host modules are compiled per game, not once per machine. `kz_port_host_library` builds the gfx, audio and
  platform sources as one OBJECT library per consumer (`kazarov:cmake/KazarovPort.cmake:34`, object at `:102`).
  Chronicle's is `dc_host` (`chronicle:port/CMakeLists.txt:35`); ChronicleTwo's is `ct_host`
  (`chronicletwo:port/CMakeLists.txt:42`). The SDK sources are also per consumer, from
  `kz_port_sce_sources` (`kazarov:cmake/KazarovPort.cmake:113`; Chronicle at `chronicle:port/CMakeLists.txt:175`,
  ChronicleTwo at `chronicletwo:port/CMakeLists.txt:194-195`).

### Inventory of process-wide state

| State | Location | Reset or lifetime |
|---|---|---|
| Renderer context `g` (device, swapchain, frames, texture and mesh tables, pipelines, recorder) | `kazarov:src/cpp/gfx/renderer.cpp:20`, `kazarov:include/gfx/context.hpp:247-342` | `RendererInit` does `g = {}` (`renderer.cpp:796`); `RendererShutdown` again (`:878`) |
| Renderer generation counter | `kazarov:src/cpp/gfx/renderer.cpp:795-797` (`static uint64_t instances`) | Bumped per init; tags lists (`displaylist.cpp:1568`, `context.hpp:319`) |
| Open display-list recorder | `kazarov:src/cpp/gfx/displaylist.cpp:1551-1553` (`g.list`) | Single slot; a second `BeginRecording` returns silently |
| Reservation sizes, two histories | `kazarov:src/cpp/gfx/displaylist.cpp:52-53` | Keyed by renderer instance |
| Grab twins (per-destination copies) | `kazarov:src/cpp/gfx/displaylist.cpp:919-920` | Reset when the renderer instance changes (`:931-933`) |
| Instanced-key set | `kazarov:src/cpp/gfx/displaylist.cpp:343` | Cleared by `CutInterpolation` (`:1597`) |
| Named render targets | `kazarov:include/gfx/context.hpp:305` | Process-wide string map; cleared per target by `DestroyTexture` (`resources.cpp:634`) |
| Blend equations, device memory pools | `kazarov:src/cpp/gfx/pipelines.cpp:139`, `kazarov:src/cpp/gfx/memory.cpp:33` | Rebuilt at init; `ShutdownMemory` clears pools (`memory.cpp:169-176`) |
| SDL window, identity, event hooks | `kazarov:src/cpp/platform/window.cpp:16-20` | `WindowShutdown` clears hooks and calls `SDL_Quit` (`:161-167`) |
| Display fields and window seam | `kazarov:src/cpp/platform/display.cpp:7-21`, `kazarov:include/platform/display.hpp:26` | `DisplayUseWindow` swaps the function pointers |
| Clock state, pump hooks | `kazarov:src/cpp/platform/clock.cpp:30-32` | Only `ClockReset` re-anchors |
| Tick callback slot, idle slot | `kazarov:src/cpp/platform/clock.cpp:107-117`, `kazarov:include/platform/clock.hpp:51,56` | One each; installing replaces |
| Audio stream, render callback, user pointer | `kazarov:src/cpp/platform/audio.cpp:21-26` | First successful start wins (`:130-133`) |
| Default audio mixer | `kazarov:src/cpp/audio/mixer.cpp:715-718` | Never destroyed by design |
| Soundtrack recording cache | `kazarov:src/cpp/audio/soundtrack.cpp:104` | `SoundtrackReload` rebuilds it |
| Path config and cached roots | `kazarov:src/cpp/platform/paths.cpp:25-31` | `PathsReset` (test hook); `PathsSetDataRoot` and `PathsSetSaveRoot` drop the cache (`:188-196`) |
| Environment prefix | `kazarov:src/cpp/platform/settings.cpp:8` | Set once by the game |
| Input slots, device state, overrides, bindings | `kazarov:src/cpp/platform/input.cpp:170-178` | `InputShutdown` resets part of it (`:733`) |
| Mouse state | `kazarov:src/cpp/platform/mouse.cpp:12-22` | `MouseStop` |
| Glyph state (function-static) | `kazarov:src/cpp/platform/glyphs.cpp:50-51` | `Reset` (`:267`) |
| TrueType message font and atlas | `kazarov:src/cpp/platform/ttffont.cpp:38-39` | Not reset by a second game |
| Texture catalog | `kazarov:src/cpp/platform/texture_catalog.cpp:14` | `Load` clears first (`:30`); `Clear` (`:122`) |
| Arena blocks (owner-keyed) | `kazarov:src/cpp/platform/arena.cpp:16-19` | `ArenaClearAll` zeroes every block (`:69`) |
| Thread scheduler (function-static) | `kazarov:src/cpp/sce/eekernel_threads.cpp:151-156` | No reset path |
| Interrupt-enable flag | `kazarov:src/cpp/sce/eekernel_threads.cpp:412` | Flag only; no interrupts exist |
| libpad open ports | `kazarov:src/cpp/sce/libpad.cpp:23` | `scePadInit` clears (`:31-33`) |
| libmc cards, files, pending result | `kazarov:src/cpp/sce/libmc.cpp:117-119` | Shared by every caller |
| sifdev open descriptors | `kazarov:src/cpp/sce/sifdev.cpp:30` | Shared |

### Renderer

- `RendererConfig` is read once at init. The logical size, `prog0_meshes`, layout, present mode, validation,
  pipeline cache path and the texture and mesh budget are all process-wide
  (`kazarov:include/gfx/gfx.hpp:63-99`). `LogicalWidth()` and `LogicalFrame()` return the one value
  (`kazarov:src/cpp/gfx/renderer.cpp:788-792`).
- The two games disagree on the logical size. Chronicle uses 640x480 (`chronicle:port/src/screen.hpp:4-5`,
  applied at `chronicle:port/src/main.cpp:423`). ChronicleTwo uses 512x480 (`chronicletwo:port/src/main.cpp:43-44`,
  applied at `:285-286`).
- Only ChronicleTwo sets `prog0_meshes = true` (`chronicletwo:port/src/main.cpp:293`), which builds the
  Vu_prog0 families: 840 pipelines instead of 504 (`kazarov:include/gfx/gfx.hpp:94-95`;
  `kazarov:src/cpp/gfx/README.md`, "Pipelines").
- Both games pass `PathsSaveRoot() / "pipeline_cache.bin"` as the cache path
  (`chronicle:port/src/main.cpp:427`, `chronicletwo:port/src/main.cpp:289`). The cache is checked against the
  device UUID only (`kazarov:src/cpp/gfx/pipelines.cpp:177-195`), so one file serves any pipeline set, and the
  last process to exit overwrites it (`:197-223`).
- `NamedRenderTarget` returns an existing target only when size, shape and alpha all match. Otherwise it destroys
  the target and creates a new one under the same name (`kazarov:src/cpp/gfx/resources.cpp:602-622`). The name
  `"dof frame"` is used by both games with different shapes. Chronicle makes it a frame target at 640 x 480
  (`chronicle:port/src/effectmacro.cpp:208`); ChronicleTwo makes a non-frame target at the frame's size
  (`chronicletwo:port/src/screeneffect.cpp:139`). Each call from either game would destroy the other's target.
- Texture and mesh handles are the slot in the low 16 bits and a generation in the high 16 bits
  (`kazarov:src/cpp/gfx/resources.cpp:20-27`). The tables are one budget of 8192 textures and 65535 meshes (`kazarov:include/gfx/context.hpp:18,23`; `gfx.hpp:97-98` lets a caller lower them
  for tests only).
- Interpolation keys are game-chosen 64-bit values in one namespace per process
  (`kazarov:include/gfx/gfx.hpp:658-662`). Both games derive them from object addresses
  (`chronicle:port/src/frame_draw.cpp:100`, `chronicletwo:port/src/mglib.cpp:991`).
- `RecordingKind` gives two reservation histories, Game and Overlay, not two recorders
  (`kazarov:include/gfx/gfx.hpp:697-702`, `kazarov:src/cpp/gfx/displaylist.cpp:52-53`). ChronicleTwo's host
  overlay uses the Overlay kind (`chronicletwo:port/src/present.cpp:62`). Chronicle at a0a5ff8 has no such kind.
- The renderer is single-threaded. Only the audio callback runs off the game thread, and the mixer takes its own
  lock (`kazarov:src/cpp/gfx/README.md`, "Lifecycle"; `kazarov:include/audio/mixer.hpp:28`).

### Window, display and input

- One SDL window with one identity (title, app id, icon) (`kazarov:src/cpp/platform/window.cpp:16-20`,
  `:59`). `WindowInit` has no re-entry guard (`:61`).
- Window event hooks are a vector with no removal call. `WindowAddEventHook` does not check for duplicates
  (`kazarov:src/cpp/platform/window.cpp:252`), while `ClockAddPumpHook` does (`clock.cpp:124`). `InputInit`
  registers `InputHandleEvent` every time it runs (`kazarov:src/cpp/platform/input.cpp:678`), and `InputShutdown`
  does not remove it (`:733-760`).
- Pads: two slots, `kInputPadCount = 2`. The keyboard and mouse drive pad 0
  (`kazarov:include/platform/input.hpp:12-15`). The action table is file-scope and in game-read order
  (`kazarov:src/cpp/platform/input.cpp:51`, `:109`).
- ChronicleTwo's `PumpHost` calls `std::exit` when the window asks to close (`chronicletwo:port/src/main.cpp:215-218`).
  Nothing else gives a game a way to end its own loop from the host.

### Clock

- One clock. `ClockPump` runs the tick callback once per elapsed tick, then the pump hooks in order, then the
  idle hook once (`kazarov:src/cpp/platform/clock.cpp:133-158`). It is not reentrant: a pump from inside the
  callback or a hook returns the current count (`:134-136`).
- One tick-callback slot (`clock.cpp:107-108`) and one idle-hook slot (`clock.cpp:115-117`). Chronicle swaps both
  around its loading screen (`chronicle:port/src/nowload.cpp:251-252`, `:349`) and clears the callback between
  sub-sessions (`chronicle:port/src/mglib.cpp:539-540`). ChronicleTwo sets its VSync callback once
  (`chronicletwo:port/src/main.cpp:307`).
- The tick count is the VSync count of the whole process. Unbounded mode advances one tick per pump
  (`kazarov:include/platform/clock.hpp`, header comment; `clock.cpp:145`).

### Settings and paths

- Game settings enter through two link-time functions every game must define with global linkage:
  `SettingsGet()` and `SettingsChange(const HostSettings &)` (`kazarov:include/platform/settings.hpp:96-97`;
  `kazarov:cmake/KazarovPort.cmake`, header comment). Chronicle defines them at `chronicle:port/src/platform/config.cpp:568-574`
  and ChronicleTwo at `chronicletwo:port/src/platform/config.cpp:541-553`.
- The environment prefix is one string (`kazarov:src/cpp/platform/settings.cpp:8`). Chronicle sets `DC`
  (`chronicle:port/src/identity.cpp:9`); ChronicleTwo sets `DC2` (`chronicletwo:port/src/identity.cpp:8`).
- One path configuration. Chronicle sets neither `coherent_default_root` nor `installed_save_default`
  (`chronicle:port/src/identity.cpp:10`), so it takes the default local-first roots: `Local("data")` beside the working
  directory or the executable (`kazarov:src/cpp/platform/paths.cpp:198-209`). ChronicleTwo sets
  `coherent_default_root` and `installed_save_default`, so data and saves go to a per-user root
  (`chronicletwo:port/src/identity.cpp:9-10`; `paths.cpp:211-240`).
- Roots are computed once and cached, and the returned references point into that cache. `PathsSetDataRoot`
  resets the cache (`kazarov:src/cpp/platform/paths.cpp:188-191`), so a reference taken before the call dangles.

### Audio

- One output stream. `AudioOutputStart` returns true at once when a stream is running and ignores the new render
  function and user pointer (`kazarov:src/cpp/platform/audio.cpp:131-133`). The SDL callback `Feed`
  runs on SDL's audio thread (`audio.cpp:71`).
- Both games use the one `audio::DefaultMixer()` singleton. Chronicle has 8 call sites
  (`chronicle:port/src/main.cpp`, `sound.cpp`, `gameutil_midi.cpp`), ChronicleTwo about 20
  (`chronicletwo:port/src/audio_init.cpp:92-93`, `sound.cpp`, `movie.cpp`, `ezmidi.cpp`, `ezbgm.cpp`). Both
  games also call `AudioOutputStart`; Chronicle calls it at `chronicle:port/src/main.cpp:437` and again from
  `chronicle:port/src/sound.cpp:499`, which is a no-op when the stream runs.
- The mixer is one class with 16 ports, each with a bank, a sequence, 16 channels and a stream slot
  (`kazarov:include/audio/mixer.hpp:21-22`, `:116-135`). Port numbers are not namespaced by game.
- The soundtrack option reads one `soundtrack/soundtrack.json` beside the save root, keyed by sequence filename
  (`kazarov:src/cpp/audio/soundtrack.cpp:79`, `:111-112`; `kazarov:include/audio/soundtrack.hpp` header comment).

### SDK replacements and threads

- The eekernel scheduler is a function-static object created on first use, holding every thread, semaphore and
  ready queue (`kazarov:src/cpp/sce/eekernel_threads.cpp:151-156`). The main thread is id 1
  (`:38`). Contexts are Windows fibers, or `ucontext` on POSIX, with 1 MiB stacks (`:22-32`, `:44-83`).
  Everything stays on one OS thread.
- A thread switch while `ClockPump` runs aborts the process (`kazarov:src/cpp/sce/eekernel_threads.cpp:209-211`).
  Clock waits spin and pump, so threads switch only at semaphore waits, signals and priority changes.
- Chronicle's SDK list does not include `eekernel_threads` (`chronicle:port/CMakeLists.txt:175`). ChronicleTwo
  includes it, plus libdev, libmpeg, libsdr, modmsin and sifdma (`chronicletwo:port/CMakeLists.txt:194-195`), and
  sets its main priority (`chronicletwo:port/src/main.cpp:310-311`).
- `GetThreadId` always returns 0 and `ChangeThreadPriority` does nothing (`kazarov:src/cpp/sce/eekernel.cpp:16-22`).
- `Exit` calls `std::exit` (`kazarov:src/cpp/sce/eekernel.cpp:12-14`), so any game's `Exit` ends the process.
- libcdvd resolves `sceCdSearchFile` names under `PathsDataRoot()` (`kazarov:src/cpp/sce/libcdvd.cpp:34`).
  Reads are not implemented (`:89`), so each game's loader reads files itself.
- libmc maps each card to `PathsSaveRoot()/mcN` (`kazarov:src/cpp/sce/libmc.cpp:130-132`). Both games would
  address the same `mc0` directory unless they namespace the file names they write.
- sifdev maps every `host0:` and device path under `PathsSaveRoot()/host0` (`kazarov:src/cpp/sce/sifdev.cpp:32-47`).
- `sceGsSyncV` returns the field parity derived from the clock (`kazarov:src/cpp/sce/libgraph.cpp:5-8`).
- sifrpc and the IOP are stubs: module load returns a counter (`kazarov:src/cpp/sce/sifrpc.cpp:17`); RPC calls
  abort through `PS2_UNIMPLEMENTED` (`:24-50`).
- Interrupt and DMA handler registration abort (`kazarov:src/cpp/sce/eekernel_threads.cpp:428-440`). The
  interrupt-enable flag only reports state (`:412-425`), since "there are no asynchronous interrupts on the host"
  (`:410-411`).
- `PORT_OVERRIDE` is an empty marker (`kazarov:include/kazarov/port.h:20-21`). The `PORT_INIT`, `PORT_RETURN` and
  `PORT_FIX` macros are defined only under `PORT` (`port.h:5-19`). Both games build with `PORT` and `PAL`
  (`chronicle:port/CMakeLists.txt:48`, `chronicletwo:port/CMakeLists.txt:86`).
- Kazarov already compiles one SDK source against two header sets. `sdk_params.hpp` exists because "the games'
  transcribed libmc.h and libpad.h disagree on some parameter types, and neither header can change"
  (`kazarov:include/sce/sdk_params.hpp:1-8`). `kazarov:src/cpp/sce/libmc.cpp:37-40` uses it, and so does `kazarov:src/cpp/sce/libpad.cpp:21` (the `PadPortBuffer` alias).

### Arena memory

- `ArenaBlock(owner, bytes)` returns a zeroed block kept for one owner pointer (`kazarov:src/cpp/platform/arena.cpp:50-66`).
  Blocks outgrown are retired, not freed (`:19`). This is the nearest thing to a per-object context in the host.
- `ArenaClearAll` zeroes every owner's block, not only the caller's (`kazarov:src/cpp/platform/arena.cpp:69-72`).
  Chronicle calls it from its dataset code (`chronicle:port/src/dataset.cpp:37`, `:55`).
- `PortImagePointer` widens a truncated 32-bit pointer to the nearest address that matches, anchored to a static
  inside the host's own image (`kazarov:src/cpp/platform/arena.cpp:92-96`). The rule assumes the image is well
  under 2 GiB (`kazarov:include/platform/arena.hpp`, `WidenNear`).

### Build linkage

- Chronicle leaves `KZ_PORT_BUILD_TIM2` at its default of ON (`kazarov:cmake/KazarovPort.cmake:96`). ChronicleTwo
  forces it OFF (`chronicletwo:port/CMakeLists.txt:39`), which removes `gfx/tim2.cpp` from its host library
  (`KazarovPort.cmake:97-98`). The two host objects differ.
- ChronicleTwo's Windows link adds `--allow-multiple-definition` (`chronicletwo:port/CMakeLists.txt:223`), so a
  duplicate strong definition is resolved silently rather than reported.
- The shader headers are generated once per CMake project. A second host library in the same project reuses the
  first's outputs (`kazarov:cmake/KazarovPort.cmake:74-77`).

## How it works

**Frame and tick.** `ClockSetTickCallback` installs the game's VSync function. A game's main loop waits with
`ClockWaitNextTick` or `ClockSyncV`, which pump the clock. Each pump runs the callback for every elapsed tick, then
the host hooks (window events via `PumpHost`, input sampling, display pump), then the idle hook. The renderer is
driven from inside the game's tick: `BeginRecording`, the game draws into the list, `EndRecording`, then
`RenderList` renders it, canonical and display variants (`kazarov:include/gfx/gfx.hpp:709-735`). Chronicle does
the same through `RenderList` at `chronicle:port/src/gameloop.cpp:175`. ChronicleTwo renders through
`chronicletwo:port/src/camera_fixed.cpp:258` and presents an overlay list at `chronicletwo:port/src/present.cpp:141`.

**Renderer lifecycle.** `RendererInit(window, config)` creates the instance, device, swapchain, main targets,
pipelines and pipeline cache, and exits the process with a message if no device qualifies (`kazarov:include/gfx/gfx.hpp:111-113`;
`kazarov:src/cpp/gfx/renderer.cpp:794-828`). `RendererShutdown` waits for the device, frees everything and resets
`g` (`renderer.cpp:830-880`). Lists recorded before a re-init carry the old instance and are rejected
(`displaylist.cpp:1607`).

**Audio.** `AudioOutputStart(rate, render, user)` opens SDL's default device as a float stream and pulls frames
from `render` on SDL's thread (`kazarov:src/cpp/platform/audio.cpp:130-158`). `<prefix>_AUDIO_WAV` replaces the
device with a tick-driven WAV writer (`audio.cpp:116-126`), and `<prefix>_AUDIO=off` skips it. ChronicleTwo
hands `DefaultMixer` to the stream (`chronicletwo:port/src/audio_init.cpp:92-93`).

**Paths and settings.** A game calls `SettingsSetEnvPrefix` and `PathsConfigure` once, typically from an
identity unit (`chronicle:port/src/identity.cpp`, `chronicletwo:port/src/identity.cpp`). The data root resolves in
the order `--data`, `--run-dir`, the environment variable, a local `data/`, then an installed copy
(`kazarov:src/cpp/platform/paths.cpp:198-206`). The save root follows a similar chain and is created on first use
(`paths.cpp:211-240`). Command-line overrides are consumed process-wide (`paths.cpp:137-183`).

**Input.** `InputInit` opens the gamepad subsystem, applies `SettingsGet()` bindings, registers the event hook and
starts the mouse (`kazarov:src/cpp/platform/input.cpp:670-680`). Each read of pad 0 latches the mouse motion since
the previous read (`kazarov:include/platform/input.hpp`, `InputLatchPad`). ChronicleTwo's headless path applies the
bindings without the gamepad subsystem (`chronicletwo:port/src/platform/input_startup.cpp:6-13`).

**SDK replacements.** Each `sce/*.cpp` implements one PS2 SDK call in host C++. Calls that touch hardware the host
does not have either succeed at once (sync, reset, IOP load), map onto host state (pads, memory cards, host files,
the clock), or abort through `PS2_UNIMPLEMENTED` (`kazarov:src/cpp/sce/unimplemented.cpp:6`). The game's own
`ps2/src` units are compiled with `PORT` defined, and `port/src` supplies `PORT_OVERRIDE` replacements for
functions the PS2 code could not keep (`kazarov:cmake/KazarovPort.cmake` and each game's `port/CMakeLists.txt`).

## Ixion hooks

1. **Keep one process per game, and share only files.** Each game already owns its identity, its clock, its
   renderer and its paths. `FilesWrite` gives an atomic write with replace (`kazarov:include/platform/files.hpp:18`),
   which suits a passenger pack or a station state file handed from one child process to another. Nothing in the
   host changes. Where: `chronicletwo:port/src/identity.cpp`, `chronicle:port/src/identity.cpp`, an Ixion
   launcher above both.
2. **Sequential crossing as a renderer re-init.** `RendererShutdown` followed by `RendererInit` with the other
   game's `RendererConfig` is self-contained (`kazarov:src/cpp/gfx/renderer.cpp:830-880`). The pipeline cache
   path (`kazarov:include/gfx/gfx.hpp:71`) makes the second init cheaper. Hold no `DisplayListRef` across the
   crossing. Where: the crossing code in the Ixion host, between the two games' main loops.
3. **Reset list for one process, one game at a time.** Before the second game starts: clear the tick callback and
   idle slot (`kazarov:include/platform/clock.hpp:51,56`; pattern at `chronicle:port/src/mglib.cpp:539-540`);
   call `texture_catalog::Clear()` (`kazarov:src/cpp/platform/texture_catalog.cpp:122`); swap the path roots with
   `PathsSetDataRoot` and `PathsSetSaveRoot` (`kazarov:src/cpp/platform/paths.cpp:188-196`) or call `PathsReset`
   for tests only; reset the mixer (`audio::DefaultMixer()`, `Mixer::Reset()`, `kazarov:include/audio/mixer.hpp`);
   and do not call `InputShutdown`/`InputInit` without `WindowShutdown` in between, since the event hook is never
   removed (see Risks). The scheduler has no reset at all.
4. **Prefix shared names per game.** Give each game's named targets its own prefix, for example `"dc1/dof frame"`
   and `"dc2/dof frame"` (`chronicle:port/src/effectmacro.cpp:208`, `chronicletwo:port/src/screeneffect.cpp:139`).
   Give each game its own card directory and host-file directory under its own save root
   (`kazarov:src/cpp/sce/libmc.cpp:130-132`, `kazarov:src/cpp/sce/sifdev.cpp:47`). This needs game-side changes
   only.
5. **Two mixers, one output.** `audio::Mixer` is a real class (`kazarov:include/audio/mixer.hpp:28`) with a
   `Render(float *, int)` entry (`:99`). Two mixers can be summed into one buffer inside one `AudioOutputStart`
   callback. This avoids the first-call-wins trap (`kazarov:src/cpp/platform/audio.cpp:131-133`). Inference: the
   two games' port numbers are then in separate mixers, which removes the port-collision risk. A small Ixion
   wrapper around `DefaultMixer` and a second `Mixer` instance would do it; the games' `DefaultMixer()` call sites
   would need routing by game.
6. **Own the tick.** Install one tick callback in the Ixion host (`ClockSetTickCallback`,
   `kazarov:include/platform/clock.hpp:51`) that forwards to the active game's VSync function, and one idle hook
   forwarding to the active game's loading presenter (`clock.hpp:56`). This matches the pattern Chronicle already
   uses (`chronicle:port/src/nowload.cpp:251-252`).
7. **Give the window close to the host.** `PumpHost` exits the process on close (`chronicletwo:port/src/main.cpp:215-218`).
   An Ixion pump hook that reads `WindowPollEvents` and its return value (`kazarov:src/cpp/platform/window.cpp:224`)
   can decide what closing means for the whole station, and the game's own pump should not exit then.
8. **Keep input shared.** Both games read pads 0 and 1 through `InputGetPad` (`kazarov:include/platform/input.hpp`),
   so one player's pad works in both worlds. Re-apply bindings with `InputApplyConfig` after a settings change
   (`kazarov:src/cpp/platform/input.cpp:682`).
9. **Renderer-wide logical frame.** A combined renderer picks one logical size. Either re-init per crossing (hook 2),
   or add a per-game transform in each game's 2D path so that a 512-wide game and a 640-wide game can share one
   640x480 frame (inference: `LogicalFrame()` is read by the full-frame rule, so a transform in the game's own
   `Draw2D` coordinates is the only option that does not touch the renderer).

## Risks and blockers

- **Everything is process-wide.** No host object carries a game identity. Two games alive at once need an
  instance-based renderer, clock, scheduler, mixer, path set and settings provider. Two games run one after another
  need only the resets in hook 3.
- **The pins differ.** Chronicle is at a0a5ff8 and ChronicleTwo at 3dc38ce (`git ls-tree` of each game's
  `tools/kazarov`). The older layout lacks `RecordingKind`, the texture catalog and `g_recording_sizes`. Any
  combined build must move one game to the other's Kazarov or backport the newer API.
- **Renderer config is one value.** Logical size (640 against 512), `prog0_meshes` (840 pipelines against 504), and
  the texture and mesh budget cannot be set per game (`kazarov:include/gfx/gfx.hpp:63-99`).
- **Named targets are overwritten, not refused.** `"dof frame"` is shared with different shapes
  (`kazarov:src/cpp/gfx/resources.cpp:602-622`). Each call from either game destroys and recreates the target
  (`effectmacro.cpp:208`, `screeneffect.cpp:139`). The result is lost contents and churn, not a crash. The
  same mechanism is what a crossing would trigger if both games used the name.
- **Link-time duplicates.** Each game defines `SettingsGet`, `SettingsChange`, and the whole `sce*` family, and each
  links its own copy of the host. A combined executable defines `scePadRead`, `sceMcOpen`,
  `gfx::RendererInit` and the rest twice. ChronicleTwo's Windows link tolerates duplicates
  (`chronicletwo:port/CMakeLists.txt:223`), so the clash would pick one silently. The comment at
  `chronicletwo:port/CMakeLists.txt:216-219` says the PS2 build renames per-object symbols through
  `port/include/stubs` so that "no symbol is defined twice". Whether that covers the two games' SDK duplicates was not
  checked (unverified).
- **Scheduler has no reset.** `Sched()` is created once and never torn down (`kazarov:src/cpp/sce/eekernel_threads.cpp:151-156`).
  Threads, semaphores and ready-queue entries from one game persist, and thread ids continue from the last value.
  `DeleteThread` removes only dormant threads (`:317-330`). ChronicleTwo's main loop runs on a PS2 thread (unverified); Chronicle's
  does not use the scheduler at all (no thread creation found in its `port/src`).
- **Thread switch inside the clock aborts.** A game that switches threads from a tick callback or pump hook kills
  the process (`kazarov:src/cpp/sce/eekernel_threads.cpp:209-211`). Any Ixion scheduler that switches games from a
  callback has to avoid this.
- **Window hooks are never removed.** `WindowAddEventHook` has no remover and no duplicate check
  (`kazarov:src/cpp/platform/window.cpp:252`). `InputInit` after `InputShutdown` without `WindowShutdown` in between
  registers `InputHandleEvent` a second time, and each event is then handled twice. `WindowInit` has no guard against
  a second call either (`window.cpp:61`).
- **`WindowShutdown` tears down everything.** It calls `SDL_Quit`, which stops audio and the gamepad subsystem
  (`kazarov:src/cpp/platform/window.cpp:161-167`). A crossing must not call it between games unless every subsystem
  is started again.
- **Process exit is shared.** `Exit`, `Fatal`, `Ps2Unimplemented` and ChronicleTwo's `PumpHost` all call `exit` or
  `abort`, so any one game's failure ends both (`kazarov:src/cpp/sce/eekernel.cpp:12-14`,
  `kazarov:src/cpp/gfx/renderer.cpp:22-29`, `kazarov:src/cpp/sce/unimplemented.cpp:6`).
- **Arena clear is global.** `ArenaClearAll` zeroes all blocks (`kazarov:src/cpp/platform/arena.cpp:69-72`). Chronicle
  calls it from its dataset code (`chronicle:port/src/dataset.cpp:37,55`). A second game's arena contents would be
  zeroed by the first game's clear.
- **Pointer widening assumes one image.** `PortImagePointer` anchors to a static in the host (`arena.cpp:92-96`).
  Inference: if the two games' PS2 units lived in separate images more than about 2 GiB apart, the nearest-address
  rule would pick the wrong address. One merged executable avoids this.
- **Shared file roots.** The data root (`paths.cpp:198-209`), the save root (`paths.cpp:211-240`), the card
  directories (`libmc.cpp:130-132`), `host0:` (`sifdev.cpp:47`), the soundtrack folder (`soundtrack.cpp:79`) and
  the pipeline cache (`pipelines.cpp:177-223`) are one set per process. Two games writing the same names collide.
- **Shared soundtrack keys.** The soundtrack mapping is keyed by sequence filename (`soundtrack.cpp:104`). If the two
  games share a sequence filename, one game's recording would play for the other. Not checked against either data
  tree.
- **Clock is shared.** The tick count and the pump run for the whole process (`kazarov:src/cpp/platform/clock.cpp:133-158`).
  A game that is not being run still sees the clock move. Inference: any time one game is paused is a visible stall
  for the other.
- **Pointer-keyed interpolation.** Both games key draws by object address (`chronicle:port/src/frame_draw.cpp:100`,
  `chronicletwo:port/src/mglib.cpp:991`). Inference: an object freed by one game and reallocated at the same
  address by the other could match the old draw, because `SetInterpKey` carries no generation (only `Interp2D` does,
  `kazarov:include/gfx/gfx.hpp:670-677`).
- **Thread contract.** gfx and the window are single-threaded (`kazarov:src/cpp/gfx/README.md`, "Lifecycle"). Any Ixion
  worker thread that touches them breaks the contract.
- **Texture and mesh budget is shared.** Both games' resources count against 8192 textures and 65535 meshes
  (`kazarov:include/gfx/context.hpp:18,23`).

## Open questions

- Is the target a single process at all? The Ixion design text (`docs/DESIGN.md`, section 1) says each world keeps
  its own engine. If yes, hook 1 needs no Kazarov change. If no, hooks 2 to 6 are the minimum for a sequential swap.
  Concurrent operation needs an instance-based host, which Kazarov does not have.
- Should a combined build pick the 3dc38ce layout for both games, and what does Chronicle need to move? The
  differences at a0a5ff8 that matter here are `RecordingKind`, `texture_catalog`, and the Overlay recording path. Not
  diffed beyond the names in this pass.
- Which of the two games' SDK symbol definitions overlap at link time? Not checked by listing both `ps2/src` and
  `port/src` definitions.
- Do the two games' sequence filenames, card names and host-file names overlap? Not checked against the extracted
  data trees.
- Is `PathsSetDataRoot` safe mid-process? It drops the cache (`paths.cpp:188-191`), so references held by the games
  dangle. Whether any game caches `PathsDataRoot()` by reference was not checked.
- What does `ClockReset` do to waiting threads? It re-anchors the count (`kazarov:src/cpp/platform/clock.cpp:98`).
  Chronicle uses it between sub-sessions (`chronicle:port/src/mglib.cpp:540`). Its effect on a second game's
  pending tick was not traced.
- Is `sceMcEnd` or `scePadEnd` enough to reset libmc or libpad between games (`kazarov:src/cpp/sce/libmc.cpp:563`,
  `kazarov:src/cpp/sce/libpad.cpp:99`)? Read, not run.
