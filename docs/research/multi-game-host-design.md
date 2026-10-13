# Hosting two independently built game modules in one process

## What this covers

Design research for one process that runs two game modules: the Dark Cloud port (`chronicle`) and the Dark Chronicle port (`chronicletwo`). Each module is built with its own copy of the Kazarov host layer. The note covers:

- the module boundary (shared library, symbol visibility, C ABI);
- C++ runtimes, Windows fibers and ucontext for each game's main loop;
- SDL3, windows, Vulkan devices and audio;
- input routing;
- a draft C ABI, `ixion_module.h`, with init, tick, suspend, resume, travel request, passenger get and set, and shutdown.

Nothing was built or run. Citations are read from the source. Where a claim comes from reading code rather than running it, the text says so. Inference is labelled.

Citation roots: `chronicle:` is the Dark Cloud checkout (master 3bc16763, Kazarov pin a0a5ff8, old layout). `chronicletwo:` is the Dark Chronicle checkout (branch `ixion` off f44a756, Kazarov pin 3dc38ce). `kazarov:` is the Kazarov checkout at main 9310c53. The two pins have identical `src/`, `include/` and `cmake/` trees for the paths cited here, so line numbers hold at both pins except where a note says otherwise. `refs/` names are community projects and are not used here.

## Key facts

- Both games already compile their game code, their port code and the host layer as CMake OBJECT libraries, then link them into one executable. Chronicle: `dc_host`, `dc_ps2`, `dc_port` and `darkcloud` (`chronicle:port/CMakeLists.txt:35,121,176,222`). Dark Chronicle: `ct_host`, `ct_ps2`, `ct_port` and `darkchronicle` (`chronicletwo:port/CMakeLists.txt`, `ct_link_game`). Nothing in either tree is a SHARED or MODULE target today.
- Position-independent code is already on in both ports (`chronicle:port/CMakeLists.txt:22`, `chronicletwo:port/CMakeLists.txt:18`). Executables are linked `-pie` on Linux (`chronicle:port/CMakeLists.txt:209`, `chronicletwo:port/CMakeLists.txt`, `CT_LINK_OPTIONS`).
- On Windows, Dark Chronicle links with `-fuse-ld=lld` and `-Wl,--allow-multiple-definition` (`chronicletwo:port/CMakeLists.txt`, `CT_LINK_OPTIONS`). The second flag hides duplicate strong definitions at link time. It is a guard, not a merge.
- The Kazarov host library is an OBJECT library compiled into each consumer. `kz_port_host_library` adds the gfx, audio and platform sources, links `SDL3::SDL3` and `Vulkan::Vulkan`, and sets `-ffp-contract=off` (`kazarov:cmake/KazarovPort.cmake`, function `kz_port_host_library`). A consumer therefore gets its own copy of every host global.
- The Rust crate `kazarov_core` and its cxx bridge `kazarov_bridge` are imported with Corrosion and linked into each consumer (`kazarov:cmake/KazarovRust.cmake`). This is the first-run setup UI and the data extractor. It adds a second copy of the Rust runtime to each module (inference that the default Corrosion link is static; the CMake does not say).
- The Windows runtime bundle copies `SDL3.dll`, `libc++.dll`, `libwinpthread-1.dll`, `libunwind.dll`, `vulkan-1.dll` and the ffmpeg DLLs next to the executable (`kazarov:cmake/KazarovWindowsRuntime.cmake`, function `kz_windows_runtime`). SDL3 and the C++ runtime are therefore already shared DLLs on Windows. Only Kazarov and the games are static.
- The game settings hook is two link-time symbols, `SettingsGet()` and `SettingsChange(const HostSettings &)`, that each game must define (`kazarov:include/platform/settings.hpp:96-97`; contract in `kazarov:cmake/KazarovPort.cmake` header comment). In a shared-module build, each module provides its own.
- The Chronicle PS2 scheduler source is not compiled. Its `kz_port_sce_sources` list is `libvu0 libpad libmc sifdev sifrpc eekernel libcdvd libgraph libdma libpkt` with no `eekernel_threads` (`chronicle:port/CMakeLists.txt:175`). Dark Chronicle's list adds `eekernel_threads` and others (`chronicletwo:port/CMakeLists.txt`). So Chronicle has no PS2 fiber threads, and Dark Chronicle does.
- Kazarov's PS2 threads are fibers on Windows and `ucontext` elsewhere, one OS thread only. The Windows path calls `ConvertThreadToFiber` in `ContextInitMain`, reached from `EnsureMain` on the first scheduler call (`kazarov:src/cpp/sce/eekernel_threads.cpp:54-60`, `:139-148`). The non-Windows path makes a `ucontext` with a 1 MiB stack (`kazarov:src/cpp/sce/eekernel_threads.cpp`, `ContextCreate`; stack size constant near the top of the file).
- The Microsoft `ConvertThreadToFiber` reference documents a NULL return with `GetLastError` on failure. It does not say what a second conversion on a thread that is already a fiber does (fetched 2026-10-13). Treat that case as untested, not as a known failure.
- The Kazarov `ContextInitMain` aborts if `ConvertThreadToFiber` returns NULL (`eekernel_threads.cpp:56-58`). A second module that converts the same host thread would abort at its first scheduler call if the conversion fails.
- Kazarov's window module holds one `SDL_Window *` and one identity per copy (`kazarov:src/cpp/platform/window.cpp`, file-scope `g_window`, hooks and identity). `WindowInit` calls `SDL_SetAppMetadata` (`window.cpp:62`), sets the video and audio driver hints (the headless audio driver is `dummy`, `window.cpp:66-70`), calls `SDL_Init(SDL_INIT_VIDEO)` (`window.cpp:72`) and creates the window (`window.cpp:96`).
- `WindowShutdown` calls `SDL_Quit()` (`kazarov:src/cpp/platform/window.cpp:166`). That tears down every SDL subsystem in the process, including another module's audio and gamepad.
- `WindowPollEvents` drains `SDL_PollEvent` and runs every hook on every event, whatever window the event names (`kazarov:src/cpp/platform/window.cpp:224-249`). A pixel-size change on any window calls `gfx::RendererResize()` on the one renderer (`window.cpp:236-238`). A close request on any window ends the poll loop (`window.cpp:232-234`).
- The mouse-capture hook does filter by window ID (`kazarov:src/cpp/platform/mouse.cpp:119`), and relative mouse mode is set per window (`mouse.cpp:36`).
- The renderer state is one `gfx::detail::Context g`, defined in `kazarov:src/cpp/gfx/renderer.cpp:20` and declared `extern` in `kazarov:include/gfx/context.hpp:344`. Device creation is `vkCreateInstance` at `renderer.cpp:149`, `vkCreateDevice` at `:348`, and `SDL_Vulkan_CreateSurface` at `:805`.
- `RendererConfig.offscreen` renders without a window (`kazarov:include/gfx/gfx.hpp`, struct `RendererConfig`; comment near line 85). Its presence is the existing path to a host-composited design.
- The Vulkan reference describes `VK_ERROR_NATIVE_WINDOW_IN_USE_KHR` as "already in use by Vulkan or another API in a manner which prevents it from being used again" (docs.vulkan.org VkResult reference, fetched 2026-10-13). That makes two live swapchains on one native window an error. The rule that a window holds one swapchain at a time is inference from that description.
- Audio: `AudioOutputStart` returns true at once if a stream already runs, without replacing the render function or user pointer (`kazarov:src/cpp/platform/audio.cpp:130-133`). Each copy has its own file-scope `g_stream`, `g_render` and `g_user` (`audio.cpp`, anonymous namespace). The device callback `Feed` runs on SDL's audio thread (`audio.cpp:71`). The stream is opened with `SDL_OpenAudioDeviceStream` on the default playback device (`audio.cpp:150`).
- Dark Chronicle's audio comment says stream levels and completion are game inputs, used for voice animation and script waits. Headless runs therefore pull the mixer on ticks (`chronicletwo:port/src/audio_init.cpp`, `AudioInit`, headless branch and comment).
- Input: `InputPoll` reads each opened gamepad handle with `SDL_GetGamepadButton` and `SDL_GetGamepadAxis` (`kazarov:src/cpp/platform/input.cpp:389-402`), and runs once per tick through `PumpHost`. Pad 0 is always connected (`input.cpp:803-812`). Keyboard input arrives as events through `WindowAddEventHook(InputHandleEvent)` (`input.cpp:670-680`).
- The clock is one process-wide object per copy, with one tick-callback slot and one idle-hook slot (`kazarov:src/cpp/platform/clock.cpp:18-32`). `ClockPump` runs the tick callback once per tick it crosses, then the pump hooks (`clock.cpp:133-146`). Setting the rate with `ClockSetTickRate` re-anchors the clock without moving the tick count (`clock.cpp:76-82`; `Anchor` copies the current count into `anchor_count`, `clock.cpp:34-38`).
- Dark Cloud's game loop has a stop request and a frame budget. `GameRequestStop` sets a flag (`chronicle:port/src/gameloop.cpp:671`), `FrameBoundaryStop` tests it with the budget (`gameloop.cpp:392`), and `RunGame` returns `kExitOk` at a frame boundary (`gameloop.cpp:917-919`). `RunGame` itself starts at `gameloop.cpp:791`.
- Dark Chronicle has no stop request. `PumpHost` calls `std::exit(kExitOk)` when the window closes (`chronicletwo:port/src/main.cpp`, `PumpHost`, about lines 214-218). A frame budget exits from `mgEndFrame` (`chronicletwo:port/src/mglib.cpp:1351`, `std::exit(status)`). A second exit sits in the overlay display-list path (`chronicletwo:port/src/present.cpp`, `DisplayOverlayList`, lines 51-56), which exits when `WindowPollEvents` fails.
- `mgEndFrame` in Dark Chronicle ends with `mgSendPacket(manager)` and `dbuff_id ^= 1` (`chronicletwo:port/src/mglib.cpp:1363-1364`). The function starts at `mglib.cpp:1273`. Dark Cloud's `MGEndFrame` starts at `chronicle:port/src/mglib.cpp:600`; its clock pumps are at `:644-648` and its buffer flip at `:653`.
- Chronicle's `main` is `Run` with identity, option parsing, `WindowInit` (`chronicle:port/src/main.cpp:418`), `RendererInit` (`:432`) and `ClockSetTickRate` (`:439`). Dark Chronicle's `Run` has the same order (`chronicletwo:port/src/main.cpp`, `Run`, about lines 250-317).
- Identity sets process-global state. Chronicle's `GameSetIdentity` sets the settings env prefix `DC`, the app directory `chronicle`, the window title and the app id (`chronicle:port/src/identity.cpp:8-14`). Dark Chronicle's sets `DC2`, app directory `chronicletwo`, and `coherent_default_root` (`chronicletwo:port/src/identity.cpp:7-12`). `PathsConfigure` and `SettingsSetEnvPrefix` are process-wide (`kazarov:src/cpp/platform/paths.cpp`, `kazarov:src/cpp/platform/settings.cpp`).
- Jump specs differ. Chronicle's `GameSetJump` takes `edit:N`, `dungeon:N`, `title`, `rush`, `opening` and `menu` (`chronicle:port/src/gameloop.cpp:571-605`). Dark Chronicle's `GameParseJump` takes `town:N`, `edit:N`, `dungeon:map:floor`, `event:N`, `title`, `opening` and `menu` (`chronicletwo:port/src/test_hooks.cpp:78-119`).
- Save state is not shared. Chronicle's `CUserStatus` holds `u16 money` (Gilda) and six-wide per-character arrays such as `max_hp[6]` and `hp[6]` (`chronicle:ps2/include/userstatus.hpp:88-141`, money at `:110`). Dark Chronicle's money is an `int` documented as up to 999999 (`chronicletwo:ps2/include/userdata.hpp:1168`), and its add-money routine keeps it between 0 and 999999 (`chronicletwo:ps2/include/userdata.hpp:2131`). Its `CHARA_DATA` is 0x38C bytes and asserted (`chronicletwo:ps2/include/userdata.hpp:241-253`). Its roster is `USER_CHARA` with ids 0 Max, 1 Monica, 2 Ridepod and 3 monster form (`chronicletwo:ps2/include/userdata.hpp:20-26`, from the existing character notes).
- Dark Cloud's party is a prefix of its six-member ID order (`chronicle:ps2/src/battlemenu.cpp:2259`, from the existing character notes). Only Max and Monica have a human body in Dark Chronicle; the Ridepod and monster forms have no `CHARA_DATA` pointer (`chronicletwo:ps2/src/userdata.cpp:2836-2842`).
- A symbol-intersection pass over the two baseline executables found about 3,013 names defined in both builds, most of them compiler and runtime names. It is run by `chronicletwo:ixion/tools/symbol_collisions.py`. The game-owned collisions it found include `SaveData`, which Dark Chronicle defines as a complete object (`chronicletwo:ps2/src/mainloop.cpp:2157`) and Chronicle defines as a pointer to its save (`chronicle:ps2/src/main.cpp:119`, `CSaveData *SaveData;`).

## How it works

### Process topology

Recommended shape for the first prototype (inference from the facts above, not yet built):

- One host executable. It owns `main`, the one SDL3 lifecycle, the event pump, the outer fibers and the travel router.
- Two module shared libraries, one per game. Each contains its game objects, its private Kazarov host copy, its own Vulkan renderer, its own mixer and clock, and its own PS2 scheduler. Each module exports exactly one function, `ixion_module_get_api`, returning a table of C function pointers.
- SDL3 and the C++ runtime are shared DLLs or `.so` files, as they already are on Windows (see Key facts).
- Both modules stay resident. Switching the visible game does not call `Run` or `MainLoop` again. It resumes the parked module's own fiber from where it stopped.

This is the design the earlier feasibility notes call "one executable and two private DLLs". Its main cost is that Kazarov's process-wide singletons must be made per-module or explicitly host-owned, and the table below lists each one.

### Module boundary and symbols

- Windows: export only `ixion_module_get_api` with `__declspec(dllexport)`. For the module link, add an export-exclusion option such as lld's `--exclude-all-symbols`, so MinGW does not auto-export everything (option name from the lld help; not tested here). Hidden symbols in one DLL do not bind to another DLL's internals on PE, so two modules with the same internal names do not collide at load time. Imports of `SDL3.dll` and `vulkan-1.dll` bind to one shared copy each.
- Linux and other ELF: compile modules with `-fvisibility=hidden` and link them with `-shared` and a version script that exports only the entry point. Load with `dlopen(path, RTLD_NOW | RTLD_LOCAL)`. The host executable must not export its symbols (no `-rdynamic`), or a module could bind to a host symbol by interposition.
- Dark Chronicle's `--allow-multiple-definition` on Windows is an internal COFF guard for header COMDATs. It is not a substitute for the boundary above. Module builds should drop it and fix any duplicate strong definitions that appear.
- Each module has `main` or `wmain` compiled out, replaced by a callable `Run` wrapper. Chronicle's `main.cpp` also carries C-name bridges used by the game (per the existing notes), so the unit is kept and only its entry is changed.

### Threads, fibers and the frame checkpoint

- The host runs on the process main thread and converts it to a fiber once, at startup. Each module's PS2 main thread is a fiber the host creates for it.
- `tick()` is a synchronous call from the host's view. Inside `tick()`, the module records the caller's current fiber, then switches to the module's saved game fiber. When the game reaches a checkpoint, the module saves `GetCurrentFiber()` and switches back to the recorded host fiber. `tick()` returns with status `IXION_PARKED`.- The module must save the exact current fiber, not always its main fiber. A PS2 controller or loader thread can be the one that reaches the checkpoint (`chronicletwo:port/src/gamepad.cpp`, `UpDate` ends with a thread rotation; the existing mainloop notes) (unverified: `UpDate` exists at line 26, the rotation was not found). A raw switch from a child thread is safe only because it is the same OS thread and the scheduler's running pointer does not change.
- Checkpoint candidates, with the state each one needs:
  - Dark Chronicle: after `mgEndFrame` completes its buffer flip (`chronicletwo:port/src/mglib.cpp:1363-1364`). The recording is closed and `ClockPump` is not active.
  - Dark Cloud: after `MGEndFrame` completes its buffer flip (`chronicle:port/src/mglib.cpp:653`). The clock pumps at `:644-648` are finished.
  - Both: the frame-end point is the only checkpoint in the first version. Loading screens and menus that call `ClockWaitNextTick` or `sceGsSyncV` directly are not checkpoints, because the pump hooks and tick callback run inside them.
- Never switch fibers inside `ClockPump`. The scheduler aborts when a switching call happens inside `ClockPumping()` (`kazarov:src/cpp/sce/eekernel_threads.cpp`, `Run`, the abort path). The hook functions only record requests.
- Dark Chronicle needs a change to adopt the host's fiber. `ContextInitMain` must use the current fiber when the thread already is one (`IsThreadAFiber`), instead of calling `ConvertThreadToFiber` again. This is a Kazarov change, not a port change.
- Dark Cloud has no scheduler in its build. Its `RunGame` can run directly on a fiber the host created, with no PS2 threads to adopt. Its existing stop flag and frame budget are useful for orderly exit.
- Linux: the `ucontext` path creates each game's context from its own `malloc`'d stack (`eekernel_threads.cpp`, `ContextCreate`). The host's root is a `ucontext` captured on the first `tick()`. The same checkpoint logic applies with `swapcontext`.

### Clock and pacing

Each module has its own clock. Two options:

- Option A, rebase on resume. Each module keeps its real-time clock. On `resume()`, the module re-anchors its clock with the tick-rate call that preserves the count (`clock.cpp:76-82`), so parked time does not replay as tick callbacks. Tick callbacks add play time and move timed events in both games (`chronicletwo:ps2/src/mainloop.cpp:424-429`; the existing mainloop notes). Frame-scoped wall-clock timers also need a rebase: Dark Chronicle's scene-load timer and frame-duration measure use wall time (`chronicletwo:port/src/sceneload.cpp`, `chronicletwo:port/src/mglib_time.cpp`; per the existing notes). This is the smaller change.
- Option B, host-paced virtual clock. Each module runs in unbounded mode (`ClockSetUnbounded`, `clock.cpp`), so `ClockWaitNextTick` returns at once. The host calls `tick()` at the active game's real-time rate and sleeps only for the visible game. Module time moves only while that module runs, which removes the replay problem by construction. It also changes pacing for presentation and audio, and it needs a host wait hook. Inference: this is the better long-term shape, not the first step.

### Window, SDL and events

- SDL is initialised once by the host. The host sets `SDL_SetAppMetadata` and the video and audio driver hints once (`window.cpp:62-72` are process-wide). A module's `WindowInit` must not call `SDL_Init` or `SDL_SetHint` on the shared process, and its `WindowShutdown` must not call `SDL_Quit` (`window.cpp:166`).
- Two windows (first prototype): each module creates its own SDL window (`window.cpp:96`). The inactive window is hidden with `SDL_HideWindow` and keeps its renderer. The renderer is not torn down on a switch. This needs no change to Vulkan ownership.
- One window (later): the host owns one SDL window. The active module creates its surface for that window, and the outgoing module destroys its swapchain and surface first. Vulkan's error for a window still held by another swapchain (see Key facts) makes the order mandatory. This needs a Kazarov API to rebind the surface, and a window's pixel-size events must go to the active module only (`window.cpp:236-238`).
- Event routing: `WindowPollEvents` must stop calling `SDL_PollEvent` inside a module. The host drains the queue once per frame, routes each event by window ID to the module that owns it, and the module's `poll_event` callback returns the next event for itself. Kazarov's hooks (`WindowAddEventHook`) keep working on the module side.
- Headless: a headless run uses the `dummy` audio driver and the offscreen video driver (`window.cpp:66-70`). Both hints are process-wide. The host must choose one mode for the whole process. A module cannot run headless while the other is graphical.

### Vulkan: devices and presentation

- Each module's renderer creates its own instance, device and swapchain today (`renderer.cpp:149,348,805`). The Vulkan loader itself is one shared library. Per-module devices are the first choice: they need no change to `gfx` and each module's `RendererInit` keeps its own `g`.
- Costs of per-module devices (inference): each module keeps its own texture table (8192 slots), mesh table and pipeline cache. The pipeline cache path is `PathsSaveRoot()/pipeline_cache.bin` (`chronicletwo:port/src/main.cpp`, `renderer.pipeline_cache`), which differs per game because the save roots differ. VRAM use roughly doubles for shared assets.
- A shared device would need `gfx::detail::Context` to become a handle, so that instance, device and queue are owned by the host. That is a large `gfx` refactor (the global is used in several hundred places). It is not needed for the first prototype.
- `RendererConfig.offscreen` lets a module render without a surface (`gfx.hpp`). A host-composited design would render both games offscreen and copy the frames into one window. That needs a cross-device copy or a readback every frame. Inference: too expensive for the first prototype, but it is the only option that gives both games one swapchain.
- `RendererInit` resets the whole context (`renderer.cpp`, the `g = {}` reset noted in the existing gfx notes). A second init in the same module would discard its own display lists. Each module calls `RendererInit` once.

### Audio

- Each module opens its own device stream. `AudioOutputStart` in a module returns true at once only if that module's stream is already running (`audio.cpp:130-133`). Because each copy has its own statics, two modules get two streams. SDL 3 mixes streams bound to the same default playback device (SDL documentation; not re-checked here).
- A parked module's stream must be paused, not left running. Otherwise `Feed` (`audio.cpp:71`) keeps pulling from the parked mixer on SDL's thread. Kazarov has no pause or resume call for the output stream today. A small addition is needed, for example `AudioOutputPause` and `AudioOutputResume` around `SDL_PauseAudioStreamDevice`.
- Dark Chronicle's stream completion gates game logic (voice and script waits; `audio_init.cpp`, headless comment). A parked module's state must not depend on the device rendering while it is parked. Pausing the stream and resuming it on `resume(visible=1)` keeps its mixer state as it was left. Inference: nothing in the code confirms this holds for every script wait.
- Headless modules use tick audio (`RenderTicks`, a pump hook) and no device stream. In a mixed process, the headless choice is process-wide (see Window), so a graphical module and a tick-audio module cannot coexist without a per-module audio choice.
- Surround and WAV capture are per-module settings read through `SettingsEnv` with each module's prefix (`audio.cpp`, `StartCapture`). They need no change.

### Input routing

- Gamepads: `InputPoll` reads device state through handles opened per module (`input.cpp:389-402`, `:798-821`). SDL's gamepad state is device state, not window state, so an inactive module would see button presses. The module must gate its pad reads on the `visible` flag set by `resume()`. The host should also open each physical gamepad once and feed the state, which is a larger change.
- Keyboard and mouse: these arrive as events through the hook list (`input.cpp:670-680`, `mouse.cpp:119`). The host routes keyboard events to the visible module only, and clears capture and held keys on every switch.
- Pad slots: Kazarov has two pad slots (`kazarov:include/platform/input.hpp`). Chronicle's `GamePad` and Dark Chronicle's `GamePad__2` are process-global (`chronicle:ps2/src/gamepad.cpp:11`; `chronicletwo:ps2/src/mainloop.cpp:2119`). Each module has its own copy, so the one-pad-per-game mapping is per module.
- Mouse capture (`mouse.cpp:36`, `SDL_SetWindowRelativeMouseMode`) must be released on every switch, or the parked window keeps the pointer.

### Save state, passengers and travel

- The two save formats cannot be shared. Chronicle's and Dark Chronicle's save images differ in layout, size and content (see Key facts). The ABI therefore carries neutral passenger records, not save bytes.
- A passenger record names the origin game, a neutral id, a role (lead, party member, or vehicle or monster form), level, HP and status bits. Money travels as a `u32` and is clamped on arrival, because Chronicle's `money` is `u16` (`chronicle:ps2/include/userstatus.hpp:110`) and Dark Chronicle's maximum is 999999 (`chronicletwo:ps2/include/userdata.hpp:1168`).
- Neutral ids need a table per game. Chronicle has six members in `Character` order (`chronicle:ps2/include/itemdata.hpp:485-491`, per the existing notes). Dark Chronicle has Max, Monica and the Ridepod and monster forms (`USER_CHARA`). Neither table is written yet.
- Equipment and items use the same approach: neutral ids mapped through a table, with a loss list for anything with no counterpart. The ABI reserves space but does not list items.
- Travel: a module requests travel by filling a request record and returning `IXION_TRAVEL` from `tick()`. The host calls `take_travel` to collect it, decides the destination game, and calls `arrive` on the destination module with a destination and the passenger list. Destinations are structured (kind, map, floor, event), not jump strings, because the two jump grammars differ (see Key facts).
- `get_passengers` and `set_passengers` read and write the neutral list while the module is parked, between frames. They must not run inside a frame recording or a pump.

## Ixion hooks

### Host and module ABI (draft)

The draft below is the proposed `ixion_module.h`. It is a draft for review and is not in any tree yet. Field names are provisional. The earlier hop-v0 contract used a different shape (the module runs its own loop and calls a host checkpoint). This draft is tick-driven: the host calls `tick()` and the module returns at its next checkpoint, which keeps the host in control of pacing.

```c
/* ixion_module.h -- draft host <-> game-module ABI, version 1. Not yet implemented. */
#ifndef IXION_MODULE_H
#define IXION_MODULE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define IXION_MODULE_ABI 1u

#if defined(_WIN32)
#define IXION_EXPORT __declspec(dllexport)
#else
#define IXION_EXPORT __attribute__((visibility("default")))
#endif

typedef enum IxionGame {
    IXION_GAME_DARK_CLOUD = 1,
    IXION_GAME_DARK_CHRONICLE = 2
} IxionGame;

typedef enum IxionStatus {
    IXION_OK = 0,
    IXION_PARKED = 1,    /* tick() returned at a checkpoint; the game is suspended, not finished */
    IXION_TRAVEL = 2,    /* a travel request is pending; call take_travel */
    IXION_FINISHED = 3,  /* the game asked to exit; call shutdown */
    IXION_ERR_ABI = -1,
    IXION_ERR_INIT = -2,
    IXION_ERR_DATA = -3,
    IXION_ERR_STATE = -4 /* call made in the wrong state */
} IxionStatus;

/* Opaque per-module instance. The module defines the struct. */
typedef struct IxionInstance IxionInstance;

/* Services the host gives a module. Valid until shutdown. */
typedef struct IxionHostServices {
    uint32_t size;
    uint32_t abi;
    void    *user;
    /* Copies the next SDL_Event routed to this module into *event and returns 1, or returns 0. */
    int      (*poll_event)(void *user, void *event);
    void     (*log)(void *user, const char *line);
    uint64_t (*now_ns)(void *user); /* monotonic host time in nanoseconds */
} IxionHostServices;

typedef enum IxionClockMode {
    IXION_CLOCK_REALTIME = 0,      /* module paces itself; resume() rebases its clock */
    IXION_CLOCK_HOST_PACED = 1     /* unbounded clock; the host paces by calling tick() */
} IxionClockMode;

typedef struct IxionInit {
    uint32_t    size;
    uint32_t    abi;
    uint32_t    game;              /* IxionGame */
    const char *data_root;         /* UTF-8, the game's own data folder */
    const char *save_root;         /* UTF-8, the game's own save folder */
    const char *jump;              /* optional start spec in the game's own grammar, or NULL */
    void       *sdl_window;        /* SDL_Window * for one-window mode, or NULL for own window */
    uint32_t    window_width;      /* 0 for default */
    uint32_t    window_height;
    uint32_t    clock_mode;        /* IxionClockMode */
    uint32_t    headless;          /* 0 or 1; process-wide, must match the host */
} IxionInit;

/* Passenger state: neutral records, never save bytes. */
#define IXION_MAX_PASSENGERS 8

typedef enum IxionRole {
    IXION_ROLE_LEAD = 1,
    IXION_ROLE_PARTY = 2,
    IXION_ROLE_VEHICLE = 3         /* Ridepod, monster form and similar */
} IxionRole;

typedef struct IxionPassenger {
    uint32_t size;
    uint32_t origin;               /* IxionGame that the record came from */
    uint32_t ixion_id;             /* neutral id from the shared roster table, 0 = none */
    uint32_t native_id;            /* the origin game's own id, for same-game restores */
    uint32_t role;                 /* IxionRole */
    uint32_t level;
    int32_t  hp;
    int32_t  max_hp;
    uint32_t status_bits;          /* neutral status set; table not yet written */
    uint32_t reserved[4];
} IxionPassenger;

typedef struct IxionPassengers {
    uint32_t       size;
    uint32_t       count;          /* in: capacity is IXION_MAX_PASSENGERS; out: records filled */
    uint32_t       money;          /* neutral money, 0..999999 */
    uint32_t       reserved[3];
    IxionPassenger list[IXION_MAX_PASSENGERS];
} IxionPassengers;

typedef enum IxionDest {
    IXION_DEST_TOWN = 1,
    IXION_DEST_DUNGEON = 2,
    IXION_DEST_EVENT = 3
} IxionDest;

typedef struct IxionTravel {
    uint32_t        size;
    uint32_t        to_game;       /* IxionGame of the destination */
    uint32_t        dest;          /* IxionDest */
    uint32_t        map;           /* town or dungeon index in the destination's own table */
    uint32_t        floor;         /* dungeon only */
    uint32_t        event;         /* event only */
    uint32_t        via;           /* reserved: train, time warp and similar */
    IxionPassengers passengers;
} IxionTravel;

/* Each function returns IxionStatus unless it says otherwise. */
typedef struct IxionApi {
    uint32_t abi;

    /* Creates the instance. Does not start the game. */
    IxionStatus (*init)(IxionInstance **out, const IxionInit *cfg, const IxionHostServices *host);

    /* Runs the game until its next checkpoint, then returns. IXION_PARKED is the normal result. */
    IxionStatus (*tick)(IxionInstance *inst);

    /* Requests a park at the next checkpoint. The next tick() returns IXION_PARKED at once. */
    IxionStatus (*suspend)(IxionInstance *inst);

    /* visible = 1 makes this module the visible game (audio on, input on, capture allowed).
       visible = 0 hides it (audio paused, input gated, capture released). Takes effect before the
       next tick(). Rebases the clock in realtime mode. */
    IxionStatus (*resume)(IxionInstance *inst, uint32_t visible, uint64_t host_now_ns);

    /* After IXION_TRAVEL: fills *out with the pending request and clears it. */
    IxionStatus (*take_travel)(IxionInstance *inst, IxionTravel *out);

    /* Places a traveller: sets the destination and the passenger list before the next tick(). */
    IxionStatus (*arrive)(IxionInstance *inst, const IxionTravel *in);

    /* Reads the current passengers while parked. Must not be called inside a tick. */
    IxionStatus (*get_passengers)(IxionInstance *inst, IxionPassengers *out);

    /* Writes passengers while parked, applied at the next checkpoint. */
    IxionStatus (*set_passengers)(IxionInstance *inst, const IxionPassengers *in);

    /* Releases everything the instance owns. The instance must be parked or not yet started. */
    void (*shutdown)(IxionInstance *inst);
} IxionApi;

/* The module's only export. Returns NULL if the module does not speak this ABI version. */
IXION_EXPORT const IxionApi *ixion_module_get_api(uint32_t abi);

#ifdef __cplusplus
}
#endif

#endif /* IXION_MODULE_H */
```

### Integration points

- Host (new, `ixion` executable): one `main` that calls `SDL_Init` once, converts the main thread to a fiber, loads each module with `LoadLibrary` or `dlopen`, calls `ixion_module_get_api`, and runs a loop of `poll events, route, tick the visible module, switch`. Hook: the new host's `main`, not any existing game file.
- Kazarov `platform/window.cpp`: `WindowInit` and `WindowShutdown` must not own SDL in module mode. Hooks: the `SDL_Init` (`:72`) and `SDL_Quit` (`:166`) calls, and `SDL_SetAppMetadata` (`:62`). `WindowPollEvents` (`:224-249`) must read from the host-fed queue. Also gate `RendererResize` (`:237`) by window ID.
- Kazarov `sce/eekernel_threads.cpp`: `ContextInitMain` (`:54-60`) adopts the current fiber if the thread already is one. Expose a create-and-switch pair for the host's checkpoint, or have `tick()` do the raw switch.
- Kazarov `platform/clock.cpp`: add a rebase call (re-anchor without moving the count), used by `resume()`. The existing tick-rate call already preserves the count (`:76-82`), so this can start as a wrapper.
- Kazarov `platform/audio.cpp`: add `AudioOutputPause` and `AudioOutputResume` around the stream (`:130-153`). `Feed` (`:71`) is unchanged.
- Kazarov `platform/input.cpp`: `InputPoll` (`:798-821`) takes an active flag. `InputInit` (`:670-680`) keeps its hook.
- Dark Cloud `port/src/main.cpp`: make `Run` callable from the module's entry, with its `main` and `wmain` removed in module builds. `GameSetIdentity` (`:368`) must run once per process, so the host supplies identity instead.
- Dark Cloud `port/src/gameloop.cpp`: `RunGame` (`:791`) as the module's game fiber body. Checkpoint after `MGEndFrame` completes (`port/src/mglib.cpp:653`). Its stop flag (`:671`) becomes the exit path for `shutdown`.
- Dark Chronicle `port/src/main.cpp`: `PumpHost` (`:214-218`) must not call `std::exit` in module mode; it returns to the host with `IXION_FINISHED`. `Run` (`:250-317`) as the module's entry. Checkpoint after `mgEndFrame` (`port/src/mglib.cpp:1363-1364`).
- Dark Chronicle `port/src/test_hooks.cpp`: `GameParseJump` (`:78-119`) is the precedent for `arrive()`, which writes the mode and init argument before the first `LoopInit`.
- Dark Chronicle `port/src/identity.cpp` and Dark Cloud `port/src/identity.cpp`: identity is per process today. In module mode, the host sets the env prefix and window identity once.
- Build: a `ixion_dc1` and `ixion_dc2` SHARED target for each game, built from the existing OBJECT libraries (`dc_*` and `ct_*`), with `-fvisibility=hidden` and a version script. The host links `SDL3::SDL3` and `Vulkan::Vulkan` and no game objects.

## Risks and blockers

- Singletons. The host layer is one `Context`, one clock, one window, one audio stream, one input table and one path table per copy (see Key facts). Per-module copies avoid collisions, but make the two modules independent of each other, which is what the design needs. Anything shared across modules (SDL, the event queue, the audio device, the Vulkan loader) has to be owned by the host.
- SDL lifetime. `SDL_Quit` in any module ends every subsystem (`window.cpp:166`). The host must be the only caller of `SDL_Init` and `SDL_Quit` in module mode.
- Event ownership. `WindowPollEvents` dispatches every event to every hook (`window.cpp:224-249`). Without host routing, a window close or resize in one game affects the other.
- Fiber adoption. `ContextInitMain` converts the thread (`eekernel_threads.cpp:54-60`). Whether a second conversion fails is not documented on the reference page; the design avoids it, but the Kazarov change must be tested on Windows.
- Parking safety. A checkpoint is safe only with no open recording, no pump in progress and no scheduler switch in progress. Dark Cloud's `MGEndFrame` and Dark Chronicle's `mgEndFrame` have these properties at their tails (see Key facts). Loading and menu loops that call `ClockWaitNextTick` directly are not checkpoints.
- Clock replay. Without a rebase, a parked module replays its parked time as tick callbacks (`clock.cpp:133-146`), which adds play time (`chronicletwo:ps2/src/mainloop.cpp:424-429`).
- Exit. Dark Chronicle exits the process from `PumpHost` and from `mgEndFrame` on a frame budget (see Key facts). A module that calls `exit` takes the other module with it. Those calls must become returns in module builds.
- Audio statefulness. Dark Chronicle reads stream completion as a game input. Pausing a stream while parked must not change the game's view of its voices or scripts. Not verified.
- Vulkan window ownership. Only one swapchain per native window (Vulkan description of `VK_ERROR_NATIVE_WINDOW_IN_USE_KHR`). The one-window design needs a strict teardown and creation order at every switch.
- Memory. Two renderers, two texture tables and two pipeline caches roughly double GPU memory for shared assets (inference). Not measured.
- Save formats. Dark Chronicle's `CUserDataManager` and `CSaveData` have static size asserts (`chronicletwo:ps2/include/userdata.hpp`, `CUserDataManager` 0x457A0 bytes). Any passenger code must not reuse those layouts.
- Macros and globals. Dark Cloud's `SaveData` pointer and Dark Chronicle's `SaveData` object share one name at link time (see Key facts). Module builds must keep them in separate DLLs; a single merged link still cannot work.
- Platforms. Windows is the only platform the builds are known to work on today. Linux builds the same CMake targets; the module build and the `dlopen` path are untested. macOS is not covered: no toolchain or hardware for it was used, and Kazarov's macOS context declarations are not verified against the module design. Treat macOS as out of scope for this note.
- Symbol collisions in a combined build are not the same as collisions in shared modules. The collision tool measures merged-link names only.

## Open questions

- Should Kazarov's host layer be shared as a third DLL (one copy for both games, with per-module contexts) instead of two private copies? That would save memory and make SDL-facing state single-owner, but it needs the context refactor first.
- Does a second `ConvertThreadToFiber` on the same thread fail in practice, and with which error? A small test on Windows would settle it.
- Is `tick()` (synchronous from the host's view, with a raw fiber switch inside) acceptable to the Kazarov scheduler, given that it does not go through the scheduler's ready queue?
- Option A (rebase) or option B (host-paced virtual clock) for the first prototype? Option B changes presentation pacing and needs measurement.
- Do SDL3 gamepad handles opened by two modules report the same button state, and is closing one handle safe while the other is open? Not checked against SDL source.
- How do streams opened by two modules on the default playback device interact when one is paused? Expected to mix cleanly, not measured.
- What is the neutral roster table (Max, Monica, Ridepod, monster form and the six Chronicle members), and which Chronicle stats have a meaningful counterpart in Dark Chronicle?
- Should passenger records carry equipment and inventory now, or wait for the item tables?
- Is `IXION_CLOCK_HOST_PACED` needed for the time-travel scene, which may need both clocks to agree on the moment of arrival?
- How should the host choose headless or graphical for the whole process, when one module is run for tests and the other for play?
