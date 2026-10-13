# The Ixion Board: a host-drawn station window, and SDL3 sharing

## What this covers

Two questions for Hop v0 and the v1 prototype.

1. **SDL3 sharing.** Hop v0 needs `ixion_c1.dll`, `ixion_c2.dll` and `ixion.exe` to bind one `SDL3.dll`.
   This note inventories the SDL3 version and every other runtime DLL each game ships, compares the two
   games, lists SDL global state in both Kazarov layouts, and recommends a staging plan.
2. **The Ixion Board.** A host-drawn window (SDL_Renderer, no Vulkan) listing stations from both games, the
   active game, recent receipts and the passenger record. This note covers event routing by window id,
   coexistence with two Vulkan game windows (one hidden), and a proposed `board.cpp` structure.

Read-only research. Nothing was built or run.

Citation labels: `chronicle:` Dark Cloud (DC1, Chronicle at 86c2b4c8); `kazarov@a0a5ff8:` Kazarov at the DC1 pin
(older layout, `port/`); `chronicletwo:` Dark Chronicle (DC2, `ixion` branch); `kazarov:` Kazarov at main
9310c53 (current layout, `src/cpp/`), which the research notes record as the same tree DC2 pins at 3dc38ce for
the paths cited (unverified: the pin hash was not checked); `sdl3:` the SDL 3.4.18 headers shipped in both dependency folders; `ixion:` the Hop v0 worktree;
`chronicletwo-data:` extracted DC2 data. Hashes are SHA-256 prefixes. "Inference" marks anything not read directly.

## Key facts

### SDL3 version and sharing

- Both games build against **SDL 3.4.18** (`sdl3:include/SDL3/SDL_version.h:47,56,65`). DC2's acquire script pins
  the same archive (`chronicletwo:tools/windows/acquire.ps1:13`) and DC1's Windows doc names it
  (`chronicle:docs/WINDOWS.md:107`).
- The x64 `SDL3.dll` is **byte-identical** in the DC1 build, the DC2 Windows release build and both dependency
  folders: `4659d5a1`, 5,384,859 bytes, file version 3.4.18.0.
- Kazarov calls `find_package(SDL3 REQUIRED CONFIG)` with no version (`kazarov@a0a5ff8:cmake/KazarovPort.cmake:35`,
  `kazarov:cmake/KazarovPort.cmake:36`). The version is pinned by each game's Windows acquire path. DC2's configure
  points `SDL3_DIR` at 3.4.18 (`chronicletwo:tools/windows/configure.ps1:26`), and so does Hop's build script.
- Linux differs: the Kazarov Docker image installs distro `libsdl3-dev` (`kazarov@a0a5ff8:image/Dockerfile:88`, unverified).
  Not relevant to Windows-only Hop v0.

### Runtime DLL inventory

| DLL | DC1 (Dark Cloud) | DC2 (Dark Chronicle) | Match |
|---|---|---|---|
| `SDL3.dll` | 3.4.18, `4659d5a1` | 3.4.18, `4659d5a1` | yes |
| `libc++.dll` | `9779d03d`, 2,002,944 B | same | yes |
| `libwinpthread-1.dll` | `f50ee782`, 1.0.0.0 | same | yes |
| `libunwind.dll` | llvm-mingw `5de31028`, 185,856 B | Rust gnullvm `13bf4e99`, 90,624 B | **no** |
| `vulkan-1.dll` | not staged; System32 copy 1.4.341 (`0f8b9d12`) | LunarG 1.4.363.0 (`e1fcfc94`) | **no** |
| FFmpeg `avcodec-61`, `avutil-59`, `swresample-5` | absent | LGPL shared n7.1.1 (61.19.101, 59.39.100, 5.3.100) | DC2 only |
| glslang, shaderc | none at runtime (glslang is a build tool and static `.lib`; no shaderc anywhere) | same | n/a |

- DC2 runtime set: `chronicletwo:tools/windows/acquire.ps1:11-19`. The LGPL check is at `:40-42`. Copied by
  `kz_windows_runtime` (`kazarov:cmake/KazarovWindowsRuntime.cmake`).
- DC1 runtime set: `chronicle:docs/WINDOWS.md:107-111`. DC1 links the **system** `vulkan-1.dll` (`:111`). Its
  Kazarov layout has no `KazarovWindowsRuntime.cmake`; the staged build folder holds SDL3, libc++, libunwind and
  libwinpthread, and no Vulkan loader.
- Glslang 16.6.0 in both (`chronicletwo:tools/windows/acquire.ps1:15`). Shaders compile at build time with
  `GLSLANG_VALIDATOR` (`kazarov@a0a5ff8:cmake/KazarovPort.cmake:85`). Vulkan headers 1.4.363 in both.

Import tables (`llvm-readobj --coff-imports`):

- `darkcloud.exe`: `SDL3.dll`, `vulkan-1.dll`, `libc++.dll`, `libunwind.dll`, UCRT api-sets. Nothing else.
- `darkchronicle.exe`: the same four, plus `avcodec-61.dll`, `avutil-59.dll` and Windows system DLLs from link
  flags (`chronicletwo:port/CMakeLists.txt:240`). `OPENGL32.dll` is linked but the DC2 port source does not call GL (unverified).

The libunwind mismatch is less serious than the file sizes suggest:

- DC1 imports one libunwind name (`_Unwind_Resume`). DC2's `darkchronicle.exe` and `libc++.dll` import 12 names
  together: `_GCC_specific_handler`, `_Unwind_DeleteException`, `_Unwind_GetDataRelBase`, `_Unwind_GetIP`,
  `_Unwind_GetIPInfo`, `_Unwind_GetLanguageSpecificData`, `_Unwind_GetRegionStart`, `_Unwind_GetTextRelBase`,
  `_Unwind_RaiseException`, `_Unwind_Resume`, `_Unwind_SetGR`, `_Unwind_SetIP`.
- Both copies export all 12. Only the llvm copy also exports `unw_resume_with_frames_walked` and `unw_strerror`,
  which no game imports.
- Kazarov's Windows module copies libunwind from the Rust toolchain on purpose (`kazarov:cmake/KazarovWindowsRuntime.cmake`,
  `KZ_UNWIND_DLL` in `rust_bin`: "Rust's unwind runtime also serves the C++ code").

Hop's staging script (`ixion:host/build-windows.ps1`, `$runtime`) copies `SDL3.dll`, `libc++.dll`,
`libunwind.dll` and `libwinpthread-1.dll` from llvm-mingw. So Hop stages the **DC1** libunwind. It does **not**
copy `vulkan-1.dll` or the FFmpeg DLLs, although `ixion:docs/HOP-V0.md` step 4 names FFmpeg (step text unverified).

### SDL global state in both Kazarov layouts (same line numbers unless noted)

- **Window lifecycle.** `SDL_SetAppMetadata` (`kazarov:src/cpp/platform/window.cpp:62`); headless-only hints
  (`:66-70`); `SDL_Init(SDL_INIT_VIDEO)` (`:72`); `SDL_Quit()` in `WindowShutdown` (`:166`); `SDL_PollEvent` in
  `WindowPollEvents` (`:227`). The DC1 layout has the same numbers (`kazarov@a0a5ff8:port/platform/window.cpp`).
- **Event hooks.** A process-global hook list (`window.cpp:252`). Input registers `InputHandleEvent` there
  (`kazarov:src/cpp/platform/input.cpp:678`).
- **No event watch and no event filter.** `SDL_AddEventWatch` and `SDL_SetEventFilter` appear in no source file of
  either game or either Kazarov layout (checked by name). The one match is inside a built `SDL3.dll`. The single
  `SDL_PollEvent` is the only event-queue reader.
- **Audio.** `SDL_InitSubSystem(SDL_INIT_AUDIO)` (`kazarov:src/cpp/platform/audio.cpp:145`), `SDL_QuitSubSystem(AUDIO)`
  (`:153`, `:189`).
- **Gamepads.** Subsystem init and quit (`input.cpp:672`, `:761`). `SDL_OpenGamepad` (`:526`), `SDL_CloseGamepad`
  (`:507`, `:756`), LED write (`:435`), gyro enable (`:477`), rumble (`:548`), per-frame polling (`:389-457`). Both
  modules would hold gamepad handles and write device state.
- **Mouse.** `SDL_SetWindowRelativeMouseMode` on the module's own window (`mouse.cpp:36`); the same hint value set
  in both games (`mouse.cpp:88` is the Kazarov copy; the game-side copy is unverified), harmless.
- **DC1 port.** Its first-run path has its own event loop (`chronicle:port/src/platform/firstrun.cpp:309`,
  `SDL_WaitEventTimeout`), its own video init and quit (`:458`, `:474`), and a file dialog (`:236`). An options row
  pushes an `SDL_EVENT_QUIT` event (`chronicle:port/src/options/rows.cpp:98-100`), not a user event.
- **DC2 port.** No `SDL_Init` or `SDL_Quit`. It reads input focus through
  `SDL_GetWindowFlags(WindowHandle()) & SDL_WINDOW_INPUT_FOCUS` (`chronicletwo:port/src/menu_mouse.cpp:91`,
  `menu_mouse_item.cpp:122`).

### SDL 3.4.18 API facts used below

- `SDL_Init` and `SDL_InitSubSystem` are reference-counted per subsystem; `SDL_QuitSubSystem` decrements; `SDL_Quit` is a
  "force shutdown" (`sdl3:include/SDL3/SDL_init.h:36-39, 214-217`). Treating it as ignoring other callers' counts is
  inference from that wording.
- `SDL_SetAppMetadata` and `SDL_SetHint` are process-wide.
- **`SDL_RenderDebugText` exists** (since 3.2.0; `sdl3:include/SDL3/SDL_render.h:2856`). 8 by 8 font (`:2815`), ASCII only
  (non-ASCII is not drawn), no wrapping, draw colour from `SDL_SetRenderDrawColor`, glyph texture kept until the renderer
  is destroyed. `SDL_RenderDebugTextFormat` at `:2884`.
- `SDL_CreateRenderer(window, NULL)` lets SDL choose; the default is platform-dependent (`SDL_render.h:240-265`,
  `SDL_HINT_RENDER_DRIVER` in `SDL_hints.h`).
- Presentation: `SDL_SetRenderLogicalPresentation` (`SDL_render.h:1576`) with `SDL_LOGICAL_PRESENTATION_LETTERBOX` (`:136`);
  `SDL_ConvertEventToRenderCoordinates` (`:1719`); `SDL_SetRenderVSync` (`:2784`), off by default (`:2764`).
- Window ids: `windowID` on `SDL_KeyboardEvent` (`sdl3:include/SDL3/SDL_events.h:365`), mouse motion (`:458`), mouse
  button (`:477`), wheel (`:497`), window events (`:328`). Gamepad events carry only `which` (`:624-707`), so they cannot be
  routed by window. `SDL_GetWindowFromEvent` (`SDL_events.h:1611`).
- `SDL_SetWindowParent` (`sdl3:include/SDL3/SDL_video.h:2757`): hiding or showing a parent applies to children; children
  hidden only as a side effect return when the parent is shown. `SDL_SetWindowModal` (`:2777`) blocks the parent; do not use.
- Flags: `SDL_WINDOW_HIDDEN` (`SDL_video.h:200`), `SDL_WINDOW_HIGH_PIXEL_DENSITY` (`:210`), `SDL_WINDOW_ALWAYS_ON_TOP` (`:213`),
  `SDL_WINDOW_UTILITY` (`:214`), `SDL_WINDOW_VULKAN` (`:219`).

### Hop v0 routing (current code)

- `RouteEvent` (`ixion:host/host.cpp:271-292`): close-requested from **any** window sets `h.quit` (`:274-275`), so a board
  close would end the program. Unowned window ids fall back to the active game (`:289-290`), so board events would leak.
- F10 is handled first (`:279-282`). `PumpEvents` drains all windows (`:294-296`). `EventWindowId` already covers
  `SDL_EVENT_WINDOW_*` (`:251-253`).
- `MainLoop` resumes the active game at `:469`. `ShowStart` (`:387-397`) and `Travel` (`:403-420`) only show and hide game
  windows.
- Each game drains its own deque (`host.cpp:41`, `:158-166`). A parked game's queue grows and replays on resume.

### Station and passenger data

- **DC1 towns.** Five Georama towns, `TOWN_NORUNE=0` to `TOWN_YELLOW_DROPS=4` (`chronicle:ps2/include/editground.hpp:14-20`).
  Map and index table in `ixion:docs/research/c1-towns-georama.md:42-52`.
- **DC1 dungeons.** Seven, entry map `200 + D` (`chronicle:ps2/include/dungeon.h:4-13`), floor counts
  `{15,17,18,18,15,25,100}` (`chronicle:ps2/src/menu_dungeon.cpp:100`). Progress in `CDngStatusData.floor_reached[7]`
  (`chronicle:ps2/include/userstatus.hpp:82-97`). Town visit flags `visit_map[80]`, `map_flags[80]`
  (`ixion:docs/research/c1-towns-georama.md:139`). Jump: `--jump dungeon:<n>` (`chronicle:port/src/gameloop.cpp:353-372`).
- **DC2 places.** `menu/0/wldmap.cfg` has 31 `POS` rows (counted with `grep -c "^POS"`; whether one is a header or sentinel is unverified); field order per `ixion:docs/research/c2-towns-georama.md:24`
  (name, map, loop, area, dungeon, floor, reachable, type). Ten lead into dungeons (`ixion:docs/research/c2-dungeons.md:61`).
- **DC2 dungeons.** Seven, IDs 0 to 6, with floor-record counts `9, 16, 25, 21, 23, 29, 39`
  (unverified; `chronicletwo:ps2/include/savedatadungeon.hpp:17-18` gives only the totals, 7 dungeons and 162 floor records, and the listed counts do sum to 162). Floor OPEN bit `0x1` (`ixion:docs/research/c2-dungeons.md:35`).
  Jump: `--jump dungeon:<n>[:<floor>]` (`c2-dungeons.md:12`). Five Georama towns in the same notes.
- **Design rules.** Visited-only places, unvisited shown as "not reached" (`ixion:docs/DESIGN.md` section 3.3). Native
  progress stays home (section 4.1, rule 5). Passenger fields: HP ratio, gilda, thirst, ailments (section 4.3) and the
  carried weapon (section 4.4).
- `IxionReceipt` (`ixion:include/ixion_api.h`) carries no HP, gilda, thirst or weapon, so the passenger record needs its own export.

## How it works

### 1. One SDL3 per process

- Windows binds imports by DLL base name. If `SDL3.dll` is already loaded, a later module binds to that loaded copy whatever
  folder its own copy is in (standard loader behaviour; verify with the Hop build). The same holds for `vulkan-1.dll` and
  `libunwind.dll`.
- The first copy loaded is the copy every module uses. A mismatched copy is silently shadowed, never reported. The host must
  check versions itself rather than rely on folder layout.
- Today SDL3 matches exactly, so SDL3 sharing works as designed. The Vulkan and libunwind mismatches are real and need a decision.

### 2. Recommended staging (one folder beside `ixion.exe`)

| File | Choice | Reason |
|---|---|---|
| `SDL3.dll` | 3.4.18 x64, `4659d5a1` | identical in both games |
| `libc++.dll`, `libwinpthread-1.dll` | `9779d03d`, `f50ee782` | identical in both games |
| `libunwind.dll` | llvm `5de31028` by default; Rust `13bf4e99` as the tested fallback | the copies differ; both pass the import check |
| `vulkan-1.dll` | LunarG 1.4.363.0 (`e1fcfc94`) | DC2's known-good; headers match both builds |
| `avcodec-61.dll`, `avutil-59.dll`, `swresample-5.dll` | DC2 pin, LGPL shared | `ixion_c2.dll` imports them |

- **libunwind.** The llvm copy is the one the llvm-mingw `libc++.dll` was built alongside (inference from the shared release
  tag) and the one the current Hop script stages. Keep the Rust copy as the fallback for DC2's Rust-side unwinding. Both pass
  the import check, so this is a test question. The Rust copy has no version resource, so its release cannot be confirmed.
- **vulkan-1.dll.** Staging LunarG changes DC1 inside Hop from system 1.4.341 to 1.4.363. The alternative changes DC2 instead.
  Test both games on whichever is chosen.
- **Version check.** Each module compares its compiled `SDL_MAJOR_VERSION.MINOR.MICRO` with `SDL_GetVersion()` at `bind`; the
  host does the same at startup and fails the bind on mismatch.
- **Build check.** Run `llvm-readobj --coff-imports` on `ixion.exe` and both modules and fail on any import no staged DLL exports.

### 3. The Ixion Board: a separate SDL window

- **Window.** `SDL_CreateWindow("Ixion Board", ..., SDL_WINDOW_HIDDEN | SDL_WINDOW_RESIZABLE | SDL_WINDOW_HIGH_PIXEL_DENSITY)`.
  No `SDL_WINDOW_VULKAN` and no `SDL_WINDOW_OPENGL`.
- **Renderer.** `SDL_CreateRenderer(window, NULL)`. Vsync stays off, because a vsync-blocked board present would add a wait to every
  host frame. Draw only when dirty.
- **Size.** 480 by 320 logical pixels with letterbox presentation gives 60 by 40 cells at 8 pixels. Default window 1440 by 960.
  Mouse hit-testing uses `SDL_ConvertEventToRenderCoordinates`.
- **Layout (proposal).** Left 34 columns: stations grouped by game, reached and not-reached marks. Right 25 columns: active game,
  receipts for each game, passenger record.
- **Keys (proposal).** Up and Down, PageUp and PageDown, Home and End move the selection. Return travels to a reached station.
  Escape hides the board. F10 stays the global travel key. F9 is a candidate toggle: no `SDLK_F9` appears in either game or
  either Kazarov layout (nor F8, F11, F12).
- **Mouse (proposal).** Motion sets the hover row; left button selects; click on the selected row travels; wheel scrolls.
- **Threading.** SDL video is main-thread only. Board calls run on the root fiber. The board draws after `ResumeGame` returns,
  when the active game is parked at its checkpoint with its frame presented.

### 4. Event routing by window id (proposal)

1. `SDL_EVENT_QUIT` ends the program.
2. An event whose window id is the board's goes to the board and stops. Close-requested hides the board.
3. Close-requested for a game window ends the program, as now.
4. F10 is a travel request, as now.
5. Events with a window id go to the owning game. Unknown window ids are dropped, not sent to the active game (the fix for `host.cpp:289-290`).
6. Events with no window id (gamepad, joystick, audio, display) go to the active game, as now.

Only keyboard and mouse events carry a window id, so the board never sees gamepad input and a game never sees board keys.

### 5. Coexistence with two Vulkan windows (one hidden)

- Three SDL windows: two game windows with Vulkan surfaces and one SDL_Renderer board. Nothing in SDL's video layer forbids mixing
  APIs across windows (inference; test on Windows).
- The hidden game window stays hidden. Only the active game and the board are shown.
- **Parenting (proposal).** Parent the board to the active game window with `SDL_SetWindowParent`, so it stays above its game and
  follows it. A hidden parent hides its children, so `Travel` must reparent the board to the incoming game before showing it.
  Closing the board uses an explicit hide, so it does not reappear with the parent.
- **Focus side effects.** Board focus removes `SDL_WINDOW_INPUT_FOCUS` from the game window. DC2's menu mouse path is gated on that
  flag (`chronicletwo:port/src/menu_mouse.cpp:91`), so the board disables DC2's menu mouse while open. The `activate` header comment
  says a module releases mouse capture when it is switched away from (`ixion:include/ixion_api.h`, `activate`, lines 105-108). DC2's
  menu mouse also treats loss of input focus as inactive and releases the pointer (`chronicletwo:port/src/menu_mouse.cpp:89-91`), so
  board focus may release capture in DC2 too. Whether capture can stay engaged on the game window is unverified.
- **Keyboard focus.** `SDL_RaiseWindow` may not move keyboard focus on Windows (inference). Mouse selection must work without it.

### 6. ABI additions for the board (proposal, v1)

The host cannot read game globals, so each module exports what the board needs: a station list and a passenger record. Append both
to `IxionApi`, bump the ABI version, and let the host read a member only when `api->size` covers it.

## Proposed Ixion code

### `ixion/include/ixion_api.h` (ABI v2 additions)

```c
typedef struct IxionStation {
    uint32_t size;
    uint32_t game_id;
    uint32_t kind;          /* IXION_STATION_TOWN, IXION_STATION_DUNGEON, IXION_STATION_FLOOR */
    int32_t  map;           /* the module's own map or stage number */
    int32_t  floor;         /* -1 unless kind == IXION_STATION_FLOOR */
    int32_t  floor_count;   /* dungeons: floors in the dungeon; else 0 */
    uint32_t reached;       /* 1 if the player has been there in this world */
    char     name[48];      /* ASCII label */
    char     jump[40];      /* the module's own --jump string, e.g. "edit:0", "dungeon:5:3" */
} IxionStation;

typedef struct IxionPassenger {
    uint32_t size;
    uint32_t game_id;
    int32_t  character;     /* active playable character, -1 if unknown */
    float    hp_ratio;      /* current/max, 0..1, -1 if unknown */
    int64_t  gilda;         /* the module's own money, before any clamp; -1 if unknown */
    float    thirst;        /* water fraction, -1 if the module has no gauge */
    char     weapon[40];    /* carried weapon name, "" if none */
    int32_t  weapon_level;  /* -1 if unknown */
} IxionPassenger;

/* Appended to IxionApi (abi_version 2):
 *   int (*stations)(uint32_t index, IxionStation *out);  0 = filled, 1 = past the end
 *   int (*passenger)(IxionPassenger *out);                0 = filled, nonzero = unavailable
 */
```

### `ixion/host/board.hpp`

```cpp
// The Ixion Board: a host-drawn SDL_Renderer window. Owned by the host; never touches a game.
#pragma once
#include <cstdint>
#include <vector>
#include <SDL3/SDL.h>
#include "ixion_api.h"

namespace ixion {

struct BoardStation {          // a row copy of IxionStation
    uint32_t game_id; uint32_t kind; int32_t map; int32_t floor; bool reached;
    char name[48]; char jump[40];
};

struct BoardRequest {          // what a board event asks the host to do
    bool travel = false; uint32_t toGame = 0; char jump[40] = {};
};

struct BoardLine { uint32_t gameId; char text[96]; };

struct Board {
    SDL_Window *window = nullptr;
    SDL_Renderer *renderer = nullptr;
    SDL_WindowID id = 0;
    bool visible = false, dirty = true;
    uint32_t activeGame = IXION_GAME_DARK_CLOUD;
    std::vector<BoardStation> stations;
    int selected = 0, top = 0;
    BoardLine receipts[8]; int receiptCount = 0;     // newest last, both games
    IxionPassenger passenger[2] = {}; bool passengerValid[2] = {false, false};
};

bool BoardCreate(Board *b);                  // after SDL_Init; creates the hidden window and renderer
void BoardDestroy(Board *b);
bool BoardOwns(const Board &b, SDL_WindowID id);
void BoardHandleEvent(Board *b, const SDL_Event &ev, BoardRequest *req);
void BoardSetVisible(Board *b, bool on, SDL_Window *activeGameWindow);
void BoardReparent(Board *b, SDL_Window *gameWindow);   // call in Travel before the game is shown
void BoardRefreshStations(Board *b, const IxionApi *const apis[2]);
void BoardNoteReceipt(Board *b, uint32_t gameId, const char *tag, const IxionReceipt &r);
void BoardNotePassenger(Board *b, uint32_t gameId, const IxionPassenger &p);
void BoardDraw(Board *b);                    // visible and dirty only; once per host frame

}  // namespace ixion
```

### `ixion/host/board.cpp` (key bodies)

```cpp
bool BoardCreate(Board *b) {
    b->window = SDL_CreateWindow("Ixion Board", 1440, 960,
                                 SDL_WINDOW_HIDDEN | SDL_WINDOW_RESIZABLE | SDL_WINDOW_HIGH_PIXEL_DENSITY);
    if (!b->window) return false;                              // plain window: no Vulkan or GL flag
    b->renderer = SDL_CreateRenderer(b->window, nullptr);      // SDL picks the driver; log SDL_GetRendererName
    if (!b->renderer) { SDL_DestroyWindow(b->window); b->window = nullptr; return false; }
    SDL_SetRenderLogicalPresentation(b->renderer, 480, 320, SDL_LOGICAL_PRESENTATION_LETTERBOX);
    b->id = SDL_GetWindowID(b->window);
    return true;
}

void BoardDestroy(Board *b) {
    if (b->renderer) SDL_DestroyRenderer(b->renderer);
    if (b->window) SDL_DestroyWindow(b->window);
    *b = Board{};
}

bool BoardOwns(const Board &b, SDL_WindowID id) { return b.id != 0 && id == b.id; }

void BoardHandleEvent(Board *b, const SDL_Event &ev, BoardRequest *req) {
    switch (ev.type) {
    case SDL_EVENT_WINDOW_CLOSE_REQUESTED:
        BoardSetVisible(b, false, nullptr);                    // hide; never quits the host
        return;
    case SDL_EVENT_KEY_DOWN:
        if (ev.key.repeat) return;
        switch (ev.key.key) {
        case SDLK_UP:       if (b->selected > 0) b->selected--; break;
        case SDLK_DOWN:     if (b->selected + 1 < (int)b->stations.size()) b->selected++; break;
        case SDLK_PAGEUP:   b->selected = b->selected >= 10 ? b->selected - 10 : 0; break;
        case SDLK_PAGEDOWN: /* clamp to size - 1 */ break;
        case SDLK_HOME:     b->selected = 0; break;
        case SDLK_END:      /* size - 1 */ break;
        case SDLK_RETURN:   /* if stations[selected].reached: fill req (travel, jump) */ break;
        case SDLK_ESCAPE:   BoardSetVisible(b, false, nullptr); return;
        default:            return;
        }
        break;
    case SDL_EVENT_MOUSE_MOTION:
    case SDL_EVENT_MOUSE_BUTTON_DOWN:
    case SDL_EVENT_MOUSE_WHEEL:
        SDL_ConvertEventToRenderCoordinates(b->renderer, const_cast<SDL_Event *>(&ev));
        /* hit-test the logical y against the row grid: set selected / top; click on selected -> req */
        break;
    default:
        return;
    }
    b->dirty = true;
}

void BoardSetVisible(Board *b, bool on, SDL_Window *activeGameWindow) {
    b->visible = on;
    if (on) {
        if (activeGameWindow) SDL_SetWindowParent(b->window, activeGameWindow);
        SDL_ShowWindow(b->window);
        SDL_RaiseWindow(b->window);
        b->dirty = true;
    } else {
        SDL_HideWindow(b->window);                             // explicit hide
    }
}

void BoardDraw(Board *b) {
    if (!b->visible || !b->dirty) return;
    SDL_SetRenderDrawColor(b->renderer, 16, 18, 24, 255);
    SDL_RenderClear(b->renderer);
    /* rows: SDL_RenderFillRect for the selected row, SDL_RenderDebugText for each name (ASCII).
       right column: active game, receipts[] newest last, passenger[activeGame] if passengerValid. */
    SDL_RenderPresent(b->renderer);
    b->dirty = false;
}
```

### `ixion/host/host.cpp` changes (proposed)

| Where | Change |
|---|---|
| `HostState` (`host.cpp:52`) | add `Board board;` and `BoardRequest boardReq;` |
| `RouteEvent` (`host.cpp:271-292`) | order from section 4: board check first; unknown window ids dropped; close-requested split by owner |
| `RunHost` after `SDL_Init` (`host.cpp:584`) | `BoardCreate(&h.board)` before `ShowStart` (`host.cpp:604`) |
| `MainLoop` after `ResumeGame` (`host.cpp:469`) | `BoardDraw(&h.board);` (the active game is parked here) |
| `Travel` (`host.cpp:403-420`) | `BoardReparent(&h.board, WindowOf(in))` before showing the incoming game; honour `boardReq` (v1) |
| `LogReceipt` (`host.cpp:116`) | also `BoardNoteReceipt` |
| F9 (proposal) | toggles the board via `BoardSetVisible` in `RouteEvent` |

Nothing here calls `SDL_Quit`. The games' `WindowShutdown` does (`window.cpp:166`), so embed mode must skip that path as `HOP-V0.md` already plans.

## Risks and blockers

1. **Silent shadowing.** A non-first copy of `SDL3.dll`, `vulkan-1.dll` or `libunwind.dll` is ignored without error. Enforce the version and import checks.
2. **Hop's staging gaps.** `build-windows.ps1` copies no Vulkan loader and no FFmpeg, so `ixion_c2.dll` cannot load from a clean folder. It stages the llvm libunwind, which differs from DC2's copy.
3. **DC1 Vulkan change.** Staging LunarG 1.4.363 changes DC1 from system 1.4.341 inside Hop. DC1 has not been tested on that loader in this layout.
4. **Shared SDL shutdown.** `WindowShutdown` calls `SDL_Quit` (`window.cpp:166`). Under Hop that would destroy the board and the other game's window. DC1's first-run path calls `SDL_QuitSubSystem(VIDEO)` (`firstrun.cpp:474`); the reference count should protect the host, but that is inference until tested.
5. **Process-wide metadata.** Each game's `WindowInit` overwrites `SDL_SetAppMetadata` (`window.cpp:62`). Harmless for the board; embed mode skips it.
6. **Shared gamepads.** Both modules open the same devices and write LEDs, sensors and rumble (`input.cpp:435, 477, 548`). The header does not say whether two `SDL_OpenGamepad` calls on one device share a handle (`sdl3:include/SDL3/SDL_gamepad.h:741-754`).
7. **Stale pad edges and parked queues.** A parked game does not poll, so a button changed while parked looks like a fresh press on resume. Routed events wait in the parked game's deque and replay; DC1 drops mouse motion older than 0.25 s (`ixion:docs/research/c1-platform-io.md:28`, unverified), but replayed keys still arrive. Discard stale input on resume.
8. **Board focus changes game input.** It disables DC2's menu mouse (`menu_mouse.cpp:91`) and may leave relative mouse capture engaged on the game window.
9. **ASCII only.** `SDL_RenderDebugText` draws ASCII only. Station labels from the games' text tables may not be ASCII in every language. The export needs ASCII labels or transliteration.
10. **Keyboard focus and raise.** `SDL_RaiseWindow` may not give the board keyboard focus (inference).
11. **Frame cost.** The board renders in the host frame. Keep vsync off and draw only when dirty. Not measured.
12. **Reached flags need the save.** `reached` depends on each module's save state. `stations()` is meaningful only after a save is loaded.
13. **Travel semantics.** Return on a station starts a v1 travel that the destination must honour on its own fiber. The v0 `Travel` ignores destinations, so the board cannot do v1 travel until that exists.

## Open questions

1. Is the board a host window (this note, per the brief) or a scene inside one game? `DESIGN.md` section 9 item 11 leaves this open.
2. Which key toggles the board? F9 is free in both games; a gamepad chord may be wanted later.
3. Should station lists come from the modules (proposed) or a host-side table? Only the module knows `reached`.
4. libunwind default: llvm or Rust copy? Needs a DC2 test under Hop, including a Rust-side panic path.
5. Vulkan loader: LunarG 1.4.363 for both games, or the system 1.4.341 with DC2 changed instead?
6. Does `SDL_OpenGamepad` share one handle across two opens of one device? Needed before both modules poll pads.
7. Parent the board to the active game (proposed) or use `SDL_WINDOW_ALWAYS_ON_TOP`? Parenting follows the game; always-on-top does not.
8. Does `SDL_CreateRenderer` on the default Windows driver coexist with the Vulkan loader in one process? Expected, untested.
9. For v1, is travel a `--jump`-style string passed to the destination's `run()`, or a new in-process entry point? The board's Return depends on the answer.
