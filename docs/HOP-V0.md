# Hop v0: both games in one program

The first Ixion prototype. One program, `ixion.exe`, loads Dark Cloud and Dark Chronicle as two
shared libraries, keeps both games alive, and switches between them with a key: press F10 in Norune
and Dark Chronicle appears exactly where it was; press it again and Dark Cloud resumes on the same
frame it left. No state crosses between the games yet; that is v1 (stations and the passenger
record). Windows first; the design keeps Linux and macOS open.

## Why this shape

The two games cannot be linked into one executable as they are: they define thousands of the same
names with different meanings. `SaveData` is a pointer in Dark Cloud
(`chronicle:ps2/src/main.cpp`) and a whole save record in Dark Chronicle
(`chronicletwo:ps2/src/mainloop.cpp`). Each also expects to own a private copy of the Kazarov
runtime: one window, one Vulkan device, one mixer, one clock, one PS2 thread scheduler.

So each game becomes a module (`ixion_c1.dll`, `ixion_c2.dll`) that keeps all of that inside and
exports only `ixion_get_api` (`ixion/include/ixion_api.h`). The host gives each game a fiber and
runs it until the game reaches a checkpoint at the end of a frame, where it may switch to the other
game. A parked game's stacks, globals, GPU resources and window stay resident, so resuming it is
instant and loses nothing.

## The pieces

### 1. The ABI (`ixion/include/ixion_api.h`)

Plain C. The module gets `IxionHost` (event queue, checkpoint, log) and offers `IxionApi` (bind, run,
activate, window, inspect). See the header for the exact contract.

### 2. Kazarov embedded mode (both Kazarov layouts)

`include/platform/embed.hpp` (current layout) and `port/platform/embed.hpp` (the older layout Dark
Cloud pins) declare the same API: `EmbedEnable`, `EmbedActive`, `EmbedPollEvent`, `EmbedCheckpoint`.
Implementation, in `platform/embed.cpp` plus small changes elsewhere, all inert unless embedded:

- `platform/window.cpp`: when embedded, `WindowInit` skips `SDL_SetAppMetadata` and the headless
  driver hints and calls `SDL_InitSubSystem(SDL_INIT_VIDEO)` instead of `SDL_Init`;
  `WindowShutdown` destroys the window but does not call `SDL_Quit`; `WindowPollEvents` takes events
  from `EmbedPollEvent` instead of `SDL_PollEvent`. Everything else in `WindowPollEvents` (hooks,
  resize, mode events, close) is unchanged.
- `platform/clock.hpp/.cpp`: add `void ClockRebase();`, which re-anchors the tick schedule at now
  while keeping `ClockTickCount()` (as `ClockSetTickRate(ClockTickRate())` does). `ClockReset` is
  wrong here because it zeroes the count.
- `platform/audio.hpp/.cpp`: add `void AudioOutputPause(bool paused);`, which pauses or resumes the
  game's own SDL audio stream device (`SDL_PauseAudioStreamDevice` / `SDL_ResumeAudioStreamDevice`).
  A paused stream's callback does not run, so the parked game's mixer does not advance. Each module
  has its own stream, so the active game stays audible.
- `EmbedCheckpoint(reason)`: if not embedded, or if `ClockPumping()`, return false. Otherwise call
  the host's checkpoint; if it reports the game was parked, call `ClockRebase()` and return true.
- Current layout only, `sce/eekernel_threads.cpp`: on Windows, `ContextInitMain` uses
  `GetCurrentFiber()` when `IsThreadAFiber()` is already true, instead of `ConvertThreadToFiber`
  (which fails on a fiber). Dark Cloud does not compile the scheduler.

Standalone builds must behave exactly as before.

### 3. Each game as a module

For each port (`chronicle:port`, `chronicletwo:port`):

- `port/src/ixion_plugin.cpp`: the module's `ixion_get_api`. `bind` stores the host. `run` builds
  `EmbedHooks` that forward to the host (poll_event, checkpoint) and calls `EmbedEnable`, then runs
  the game through the same function `main` uses. `activate` calls `AudioOutputPause(!active)`;
  when deactivating it also releases mouse capture or relative mouse mode if the port holds it.
  `window` returns `WindowHandle()`. `inspect` fills what it can (logic frames, clock ticks, mode,
  map, floor, active character, position, place name) from the game's globals.
- `port/src/main.cpp`: expose the existing run path as a function the plugin can call, keeping
  `main` and its behaviour unchanged for the standalone executable.
- The frame end (`MGEndFrame` in Dark Cloud's `port/src/mglib.cpp`, `mgEndFrame` in Dark
  Chronicle's): after the frame is presented and the buffer index has flipped, call
  `EmbedCheckpoint(kEmbedFrameEnd)`; if it returns true, reset any frame pacing the port measures
  against wall time (for example Dark Chronicle's present timing).
- `port/CMakeLists.txt`: option `IXION_BUILD_PLUGIN` (default OFF). When ON, also build a SHARED
  library (`ixion_c1` / `ixion_c2`) from the same objects and link flags as the game executable,
  plus `ixion_plugin.cpp`, with `-Wl,--exclude-all-symbols` so only `ixion_get_api` (marked
  `IXION_EXPORT`) is exported. The ABI header comes from `IXION_API_DIR`. The standalone executable
  and tests are unchanged.

### 4. The host (`ixion/host`)

A small standalone CMake project that links only SDL3; it never sees game headers.

- Starts SDL (`SDL_SetAppMetadata("Ixion", ...)`, `SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS)`),
  converts the main thread to the root fiber, and loads each module by absolute path.
- Gives each game a fiber whose entry calls `api->run(argc, argv)` with that game's own arguments
  (data root, save root, window size, startup jump).
- Boots them in turn: runs game 1 until its first checkpoint, then game 2, then shows game 1's
  window and hides game 2's.
- Main loop on the root fiber: pump SDL events and route them: events with a window ID go to the
  game owning that window; keyboard, mouse and gamepad events with no window go to the active game;
  F10 is a travel request and goes to no game; `SDL_EVENT_QUIT` and a close request on either window
  end the program. Then resume the active game's saved fiber until its next checkpoint.
- The checkpoint callback records `GetCurrentFiber()` (a game may reach a checkpoint from one of its
  PS2 thread fibers, not only from the fiber the host made) and switches to the root fiber. When it
  is resumed it returns whether the game was parked in between.
- Travel (F10): call `activate(0)` on the outgoing game, hide its window, show and raise the other's,
  call `activate(1)` on it, mark it parked, and resume it.
- Log a receipt (`inspect`) for both games at every switch.
- `--auto-switch N:M`: switch every N host frames, M times, then exit with status 0 if every parked
  game's receipt (logic frames, clock ticks, map, position) was unchanged while it was parked, and
  nonzero otherwise. This is the automatic acceptance test.
- Quitting ends the process directly (`TerminateProcess` on itself) once logs are flushed; v0 does
  not attempt an orderly shutdown of two parked games.
- `ixion/host/fiber_smoke.cpp`: a self-test with no games: root fiber, two game fibers, one of which
  makes a nested fiber and checkpoints from it; checks resume order and that the x87/SSE control
  words survive switches.

## Building and running (Windows, llvm-mingw)

1. Build Dark Chronicle with `-DIXION_BUILD_PLUGIN=ON -DIXION_API_DIR=<ixion/include>`, giving
   `ixion_c2.dll` beside `darkchronicle.exe`.
2. Build Dark Cloud the same way, giving `ixion_c1.dll`.
3. Build `ixion/host`, giving `ixion.exe` and `ixion_fiber_smoke.exe`.
4. Stage `ixion.exe`, both modules and one shared set of runtime libraries (SDL3, libc++, libunwind,
   winpthread, FFmpeg) in one folder. Both modules must load the same SDL3.dll.
5. Run:

   ```
   ixion.exe --dc1 ixion_c1.dll --dc1-args "--data <dc1 data> --save <dc1 save> --width 1280 --height 960 --jump edit:0"
             --dc2 ixion_c2.dll --dc2-args "--data <dc2 data> --save <dc2 save> --window 1280x960 --jump town:10"
   ```

   Press F10 to cross. Use fresh save folders.

## Acceptance

1. `ixion_fiber_smoke` passes.
2. Each module exports only `ixion_get_api` (`llvm-readobj --coff-exports`).
3. Both games boot in one process; Dark Cloud shows Norune, Dark Chronicle shows Palm Brinks.
4. `--auto-switch 120:20` exits 0: twenty crossings, and neither game advanced while parked.
5. By hand: move Toan, cross, move Max, cross back; Toan is where he was and the game carries on.

## Known limits

- Windows only (the scheduler adoption and the host's fibers use the Win32 fiber API).
- Switching happens only at frame ends, so a press of F10 during loading waits for the next frame.
- Wall-clock presentation effects (text wipes, scene-load timers) may jump after a long park.
- Nothing crosses between the games yet. Two Vulkan devices and two mixers are resident at once.

## Status (2026-10-13)

Acceptance 1 to 4 pass on Windows: the fiber smoke passes; each module exports only
`ixion_get_api`; both games boot in one process (Toan in Norune, Max in Palm Brinks); and
`--auto-switch 120:20` makes twenty crossings with no receipt change while parked. Each game's
logic frames and clock ticks rose only during its own active stints, so parked time was never
replayed. A scripted walk across the switches moved each character only while its game was active.
Acceptance 5 (by hand, at a keyboard) is still to do.

Open items from review, for v0.1:

- A game that exits the process (`--frames`, quitting, missing data) ends the host too, possibly
  with status 0. Do not pass `--frames` or `--screenshot` to embedded games yet.
- Input held at the moment of crossing is seen for one frame when that game resumes.
- Controller sensor, LED and rumble settings are shared by both runtimes and are not reapplied when
  a game becomes active.
- Receipts are partial: Dark Cloud's character and place stay unknown, Dark Chronicle's dungeon map
  is the scene map. A loading frame counts as booted.
- Dark Chronicle can leave the system cursor hidden after a switch when mouse capture is off.
