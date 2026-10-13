# Chronicle rendering and presentation

## What this covers

How the Chronicle (DC1) PC port turns the game's draw calls into pixels on screen: who owns the SDL window, the Vulkan instance, device, surface and swapchain; how a tick's drawing becomes a display list and a canonical render; how display frames are interpolated and presented between ticks; how the 640x480 logical frame maps onto the window; and which of this state is process-global. The question for Ixion is whether the two games can share one window and one device, and what switching the visible game would require.

Code citations use `chronicle:` for the DC1 tree (pinned master 3bc16763), `kazarov@a0a5ff8:` for the Kazarov revision Chronicle pins (older layout: `port/gfx`, `port/platform`), `kazarov@9310c53:` for the Kazarov main branch (layout moved to `src/cpp/` and `include/`), and `chronicletwo:` for the DC2 tree. Line numbers refer to those revisions.

## Key facts

- **One window, one renderer, per process.** `WindowInit` stores a single `g_window` and `RendererInit` writes a single process-wide `extern Context g`. `RendererInit` starts with `g = {}`, discarding any previous state. (`kazarov@a0a5ff8:port/platform/window.cpp:16,61,96`; `kazarov@a0a5ff8:port/gfx/renderer.cpp:781-784`; `kazarov@a0a5ff8:port/gfx/context.hpp:340`)
- **Window shutdown tears down SDL.** `WindowShutdown` destroys the window, clears the event hooks and calls `SDL_Quit()`. (`kazarov@a0a5ff8:port/platform/window.cpp:161-167`)
- **Renderer shutdown releases the surface, not the window.** `RendererShutdown` destroys swapchain, targets, device, the Vulkan surface and instance, but never the SDL window. (`kazarov@a0a5ff8:port/gfx/renderer.cpp:815-865`)
- **Device choice is bound to the window's surface.** `PickPhysicalDevice` queries each device's capabilities against `g.surface`, so the device must be able to present to the window it was created for. (`kazarov@a0a5ff8:port/gfx/renderer.cpp:194-247`)
- **Swapchain is a blit target.** Swapchain images are created with `TRANSFER_DST` only. `PresentImage` blits the finished main colour image (the window's pixel size) onto the acquired swapchain image with `VK_FILTER_NEAREST`, then presents. (`kazarov@a0a5ff8:port/gfx/renderer.cpp:399-464`, `:935-973`)
- **Present mode fallback.** A `Fifo` request always gets FIFO. Otherwise `Immediate` is used if requested and offered, else `Mailbox` is used whenever it is offered (even if not requested), else FIFO. (`kazarov@a0a5ff8:port/gfx/renderer.cpp:371-389`)
- **Two frames in flight; one graphics queue.** (`kazarov@a0a5ff8:port/gfx/context.hpp:16`; `kazarov@a0a5ff8:port/gfx/gfx.hpp` Lifecycle, README) (one-queue part unverified; README only requires "a graphics queue")
- **Logical frame is per-renderer config.** `RendererConfig` fixes `logical_width` (default 640), `logical_height` (480) and `display_aspect` (4:3) at init. DC1 passes `kScreenWidth` (640) and `kScreenHeight` (480). (`kazarov@a0a5ff8:port/gfx/gfx.hpp:63-95`; `chronicle:port/src/main.cpp:421-431`; `chronicle:port/src/screen.hpp:4-5`)
- **DC2 uses a different logical frame.** DC2's `kLogicalWidth` is 512 and `kLogicalHeight` 480, and it sets `prog0_meshes = true`. (`chronicletwo:port/src/main.cpp:43-44,285-293`)
- **Non-4:3 logical frames are scaled per axis.** `MainMapping` uses a uniform scale only when the logical aspect equals `display_aspect`; otherwise it scales X and Y separately to fill the 4:3 frame. A 512x480 frame therefore shows non-square texels at 4:3. (`kazarov@a0a5ff8:port/gfx/draw.cpp:796-818`)
- **Aspect modes.** `AspectMode::Fill` (DC1 `video.aspect = auto`) lets 3D, frame grabs and full-frame 2D reach the window's edges; `Letterbox` clips everything to the 4:3 frame. Switchable at runtime with `SetFrameLayout`, which is refused inside a frame. (`kazarov@a0a5ff8:port/gfx/gfx.hpp:23-34`; `kazarov@a0a5ff8:port/gfx/renderer.cpp:1134-1149`; `chronicle:port/src/main.cpp:193-196`, `:221-236`)
- **Resize is lazy.** SDL's pixel-size event calls `gfx::RendererResize()`; the swapchain and main targets are rebuilt at the next frame begin. (`kazarov@a0a5ff8:port/platform/window.cpp:236-238`; `kazarov@a0a5ff8:port/gfx/renderer.cpp:867`)
- **The game's tick is recorded, not drawn.** `MGBeginFrame` calls `gfx::BeginRecording()` and `MGEndFrame` seals the list and renders it once as the tick's canonical image. (`chronicle:port/src/mglib.cpp:554-597`, `:600-641`)
- **Display frames are presented between ticks.** While `MGEndFrame` waits for the next tick, `GamePresentBetweenTicks` renders interpolated display frames from the last two lists and presents them, bounded by `video.max_fps`. (`chronicle:port/src/gameloop.cpp:712-743`, `:170-185`)
- **Interpolation is cut across renderers.** `RenderList` refuses a list whose `instance` tag differs from the current renderer, and a display render uses the previous list only if it has the same tag. (`kazarov@a0a5ff8:port/gfx/displaylist.cpp:1164-1166`, `:1182`)
- **Single-slot clock hooks.** The idle hook is a single slot; installing a new one replaces the previous one. Pump hooks are a list. (`kazarov@a0a5ff8:port/platform/clock.hpp:55-56`; whether the tick callback also replaces its predecessor is unverified)
- **Single event-hook list.** `WindowAddEventHook` appends to one process-wide list, cleared at window shutdown. (`kazarov@a0a5ff8:port/platform/window.cpp:252`)
- **The loading screen presents from the idle hook.** `PresentLoadingFrame` does its own `gfx::BeginFrame`/`EndFrame` and is refused while the game has a frame open. (`chronicle:port/src/nowload.cpp:143-158`, `:252`)
- **First-run creates and destroys its own window and renderer** before `main` creates the real ones: `FirstRunIfNoData` runs `WindowInit`, `RendererInit`, then `RendererShutdown` and `WindowShutdown`. This is the only in-process precedent for tearing the stack down and rebuilding it (unverified: "only" was not checked by searching the whole tree). (`chronicle:port/src/platform/firstrun.cpp:452-520`; `chronicle:port/src/main.cpp:372`)
- **Texture key space is process-global.** The texture registry keys every image and palette by a 14-bit TBP0/CBP value, held in a function-local static `Registry`. Keys 0 and 0xFFF are the frame keys (`kMGPortFrameTbp0`, `kMGPortPreviousFrameTbp0`). (`chronicle:port/src/texture_port.cpp:15,54-57`; `chronicle:port/src/texture_port.hpp:36`; `chronicle:port/src/mglib_port.hpp:32-33`)
- **Registry gating.** `RendererUp()` is `gfx::PipelineCount() != 0`; before the renderer exists, textures are placeholders only. (`chronicle:port/src/texture_port.cpp:59-61`)
- **3D visuals are keyed by game memory address.** `g_visuals` and `g_transient` map a game block pointer to a `Draw3DVisual` holding a `gfx` mesh; they are swept by a tag written into the block. (`chronicle:port/src/visualvu1.cpp:22-24`, `:397-436`)
- **2D services are swappable.** `draw2d::Services` is a struct of function pointers (draw state, texture resolve, find-texture, GS register setters), set through `SetServices`. (`chronicle:port/src/draw2d_port.hpp`; `chronicle:port/src/draw2d_port.cpp:14-34`)
- **Window identity is set once at start.** `GameSetIdentity` sets the title "Dark Cloud", app id `dcdecomp.darkcloud`, the icon, and the `DC` settings env prefix and path roots. (`chronicle:port/src/identity.cpp:8-15`)
- **DC2 identity differs.** `SettingsSetEnvPrefix("DC2")`, `app_dir = "chronicletwo"`, `DC2_DATA` and `DC2_SAVE`. (`chronicletwo:port/src/identity.cpp:8-9`)
- **Host library is one object library per build tree.** `kz_port_host_library(dc_host)` builds the host side (gfx, platform, audio, sce) as an OBJECT library linked into the single `darkcloud` executable. (`chronicle:port/CMakeLists.txt:35,214`; `kazarov@a0a5ff8:cmake/KazarovPort.cmake:33,97`)
- **Both games define `main`.** Chronicle's entry is `PORT_OVERRIDE int main` at `chronicle:port/src/main.cpp:471`; DC2's is at `chronicletwo:port/src/main.cpp:332`.
- **Tests run one process each.** Chronicle's GoogleTest cases run as separate processes under ctest, so the test suite never shares a renderer across cases. (`chronicle:docs/PC.md:1666-1669`) The Kazarov half of this claim is unverified.
- **Kazarov main has grown, not shrunk.** On `9310c53` the public API moved to `include/gfx/gfx.hpp` and the implementation to `src/cpp/gfx/`, `src/cpp/platform/`. `RecordingKind` (Game or Overlay), `Presentation2D`, `Interp2D`, and `texture_slots`/`mesh_slots` were added. The window and renderer entry points keep the same singleton shape. (`kazarov@9310c53:include/gfx/gfx.hpp`, `kazarov@9310c53:include/platform/window.hpp`)
- **Shared-device GPU tests are classified.** Kazarov main names its GPU tests with a `GfxGpu` prefix so consumers can exclude them, which implies a consumer expects to run them against one device. (`kazarov@9310c53:src/cpp/gfx/README.md`, "Shared device test classification")

## How it works

### Ownership

Everything that touches the display lives in one process-wide stack:

1. `WindowInit` calls `SDL_Init(SDL_INIT_VIDEO)` and creates one SDL window with `SDL_WINDOW_VULKAN` (unless offscreen), `SDL_WINDOW_RESIZABLE` and `SDL_WINDOW_HIGH_PIXEL_DENSITY`. Headless uses SDL's `offscreen` driver (or `windows` with a hidden window on Windows). (`kazarov@a0a5ff8:port/platform/window.cpp:61-108`)
2. `RendererInit(window, config)` creates the Vulkan instance (SDL asks for the surface extensions unless offscreen), the surface through `SDL_Vulkan_CreateSurface`, the physical device (Vulkan 1.3 minimum, with the feature list in `requirements.cpp`), the logical device, two frame slots, the pipeline layout, bindless resource tables, the main targets, and the pipelines against the on-disk pipeline cache. (`kazarov@a0a5ff8:port/gfx/renderer.cpp:781-813`)
3. The game's code calls `gfx::*` through its replacement units. Nothing outside the host (`port/platform`, `port/gfx`, `port/audio`) reaches SDL or Vulkan, except the game's own helpers: `textwipe.cpp` reads the SDL keyboard, `firstrun.cpp` opens a file dialog and sets the title, `options/rows.cpp` uses `SDL_` for display modes. (`chronicle:port/src/textwipe.cpp:40`; `chronicle:port/src/platform/firstrun.cpp:143-157`, `:221-237`)
4. `RendererShutdown` then `WindowShutdown` in `Run` tear everything down in reverse. (`chronicle:port/src/main.cpp:464-465`)

The window's pixel size, not its logical size, sets the main target. `CreateMainTargets` makes the two colour images, the display colour image and the depth images the size of the swapchain extent. (`kazarov@a0a5ff8:port/gfx/renderer.cpp:700-752`)

### Frame flow

Per game tick (60 Hz by default):

1. `MGBeginFrame` → `gfx::BeginRecording()`. Draws, copies and uploads are appended to a `DisplayList` and their arguments copied. (`chronicle:port/src/mglib.cpp:554`; `kazarov@a0a5ff8:port/gfx/displaylist.cpp:1124`)
2. `MGEndFrame` → `gfx::EndRecording()` → `GameRenderTick(list)` → `gfx::RenderList(list, 1, {.canonical = true})`. This runs every entry in order into the next main colour image, which becomes `kPreviousFrame` for the next tick and what screenshots, depth picks and frame grabs read. Nothing is presented here. (`chronicle:port/src/mglib.cpp:600-625`; `chronicle:port/src/gameloop.cpp:694-710`; `kazarov@a0a5ff8:port/gfx/gfx.hpp:673` and README "Display lists")
3. `MGEndFrame` pumps the clock and then, if the game is still due to wait, calls `ClockWaitNextTick(GamePresentBetweenTicks)`. That hook renders display frames from the newest and previous lists at `alpha` = elapsed fraction of the tick, into a separate display image with its own depth buffer, and presents each one. (`chronicle:port/src/mglib.cpp:643-648`; `chronicle:port/src/gameloop.cpp:712-743`; `kazarov@a0a5ff8:port/gfx/displaylist.cpp:1164`)
4. A tick that presented nothing presents its canonical image through `GamePresentTickEnd` → `PresentCanonicalFrame` → `gfx::PresentCanonical()`. (`chronicle:port/src/gameloop.cpp:745-760`; `kazarov@a0a5ff8:port/gfx/renderer.cpp:1102`)

The loading screen and the first-run screen bypass lists: they call `gfx::BeginFrame()`/`EndFrame()` directly from the clock's idle hook. (`chronicle:port/src/nowload.cpp:143-158`; `chronicle:port/src/platform/firstrun.cpp:104-110`)

Display frames interpolate 3D models, cameras and vertex animation between two lists using the tags the game sets (`SetInterpKey`, `MeshTransform`). 2D is not interpolated. The FPS counter is an overlay list that is never part of a canonical image. (`chronicle:docs/PC.md:748-830`; `kazarov@a0a5ff8:port/gfx/README.md` "Display lists")

### Resolution and aspect

- The game's logical space is 640x480 (`chronicle:port/src/screen.hpp:4-5`). `MainMapping` places it as the largest 4:3 rectangle that fits the window, centred with whole-pixel offsets (`kazarov@a0a5ff8:port/gfx/draw.cpp:796-818`).
- `video.aspect = auto` is `Fill`: the mapping is kept, but 3D projection uses the window's shape (vertical field of view is retail's; horizontal field of view grows with width), and full-frame 2D, frame grabs and the depth-of-field passes cover the window's full width. (`chronicle:docs/PC.md:904-955`; `chronicle:port/src/mglib.cpp:313-321`, `:347-370`)
- HUD pieces are anchored to a frame edge through `gfx::UiAnchor` (dungeon status panel, town clock). `video.ui_scale` scales depthless 2D about the window centre through `UiMapping`. (`kazarov@a0a5ff8:port/gfx/draw.cpp:821-838`; `chronicle:docs/PC.md:937-945`)
- `aspect = 4:3` is `Letterbox`; `ClearBars` paints the bars around the frame on the main target. (`chronicle:port/src/mglib.cpp:86-100`)

### Headless, screenshots and the test suite

- `--headless` sets SDL's offscreen driver and the unbounded clock (one tick per pump). If the Vulkan loader has no `VK_EXT_headless_surface`, the renderer runs with `RendererConfig::offscreen`: no surface and no swapchain, each frame drawn into the main target alone and nothing presented. (`chronicle:port/src/main.cpp:416`; `kazarov@a0a5ff8:port/gfx/renderer.cpp:1065-1119`; `chronicle:docs/PC.md:83-84`)
- `--screenshot` reads `gfx::kPreviousFrame` outside a frame, which is the newest canonical render, so a screenshot never holds the FPS counter. (`chronicle:port/src/gameloop.cpp:781`; `chronicle:port/src/main.cpp:358-359`; `chronicle:docs/PC.md:86`)
- Shared-device GPU tests in Kazarov are named `GfxGpu*`; Chronicle's tests are separate processes, so the test runner never shares a window or device between cases. (`chronicle:docs/PC.md:1666-1669`; `kazarov@9310c53:src/cpp/gfx/README.md`)
- Windows links the system `vulkan-1.dll` and SDL3 (`chronicle:docs/WINDOWS.md:107-111`). The renderer does not load a second loader or device per game.

### Input and window events

- `PumpHost` (`chronicle:port/src/main.cpp:221`) pumps window events, which calls `GameRequestStop` on close, then `DisplayPump`, then the layout check, then `InputPoll` and `InputScriptApply`. Every clock pump runs it. (`chronicle:port/src/main.cpp:221-236`; `kazarov@a0a5ff8:port/platform/clock.hpp` pump hooks)
- Window events reach `gfx::RendererResize()` through `WindowPollEvents`. Input sees each event through `WindowAddEventHook`. (`kazarov@a0a5ff8:port/platform/window.cpp:224-252`)

### Game-side drawing units

- `mglib_port.cpp` owns the GS register shadows (TEST, ZBUF, ALPHA, TEXA, window rectangle) and converts GS 12.4 coordinates and 24-bit Z into logical space and reverse-Z. (`chronicle:port/src/mglib_port.cpp:1-80`; `chronicle:port/src/mglib_port.hpp`)
- `texture_port.cpp` decodes TIM2 images into renderer textures and registers them. Named render targets (`#name#w#h#bpp` placeholders) become renderer targets that survive mode re-entry. (`chronicle:port/src/texture_port.cpp:317-398`)
- `draw2d_port.cpp` resolves TEX0 for 2D, snapshots the frame into a named target when a sprite samples the frame, and sets the 2D state. (`chronicle:port/src/draw2d_port.cpp:41-78`)
- `visualvu1.cpp` builds each VU1 MDT block into a `gfx` mesh once, then `DrawVu1` submits it with the matrices and lights the VU1 header carried. (`chronicle:port/src/visualvu1.cpp:397-460`, `:579-595`)
- `frame_draw.cpp` runs the per-frame model drawing and culls against `Draw3DVisibleExtent`. (`chronicle:port/src/frame_draw.cpp:111`; `chronicle:port/src/mglib.cpp:313`)
- `glyph_draw.cpp` and `clsmes.cpp` draw button symbols and message text. Message text can come from a TrueType face through `ttffont::Load`, which is a process-global singleton. (`chronicle:port/src/clsmes.cpp:45-68`)
- `dispctrl.cpp` draws the developer font as glyph quads through `gfx::Draw2D`. (`chronicle:port/src/dispctrl.cpp:38-188`)

## Ixion hooks

**Who owns the window and device today.** Each game's `main` (`chronicle:port/src/main.cpp:471`, `chronicletwo:port/src/main.cpp:332`) calls `WindowInit`, `RendererInit`, and the teardown calls. A combined executable must have one `main`, with each game's `Run` and `RunGame` behind its own entry point.

1. **Single host entry point.** Move `WindowInit` (`chronicle:port/src/main.cpp:418`), `gfx::RendererInit` (`:432`), `AudioOutputStart`, `ClockAddPumpHook(PumpHost)` (`:441`) and the teardown (`:464-465`) into one host function. Each game registers a tick callback and a layout, not a window.
2. **Renderer config union.** Choose one `RendererConfig`: `prog0_meshes` is true in DC2 (`chronicletwo:port/src/main.cpp:293`) and false in DC1 by default (`kazarov@a0a5ff8:port/gfx/gfx.hpp:95`; DC1's `main.cpp` at `chronicle:port/src/main.cpp:421-431` never sets it); `logical_width` is 640 in DC1 and 512 in DC2. A single renderer has one logical size, so the choice is a design decision (see Risks).
3. **Per-game display-list seam.** `GameRenderTick(list)` (`chronicle:port/src/gameloop.cpp:694`) and `GamePresentBetweenTicks` (`:712`) are where a tick's list is handed to the renderer. The host can route the list from whichever game is active and keep `g_list`/`g_previous_list` per game. On a switch, call `gfx::CutInterpolation()` (`kazarov@a0a5ff8:port/gfx/gfx.hpp` near `CutInterpolation`) so the first display frame of the new game does not interpolate from the old one.
4. **Clock ownership.** `MGInitVSyncCallBack` (`chronicle:port/src/mglib.cpp:544`) and `ClockSetIdleHook` (`chronicle:port/src/nowload.cpp:252`) both write single slots. The host should own them and dispatch to the active game. The loading screen's idle presenter needs the same treatment.
5. **Texture and visual namespaces.** The 14-bit registry (`chronicle:port/src/texture_port.cpp:15`) and the visual maps (`chronicle:port/src/visualvu1.cpp:23-24`) are process-global. Either namespace them per game, or release the outgoing game's owner set on a switch with `PortReleaseOwner` (`chronicle:port/src/texture_port.hpp`) and clear `g_visuals`/`g_transient`.
6. **Frame layout.** `Layout(config)` (`chronicle:port/src/main.cpp:193`) and `ApplyConfigChange` (`:311`) are the only places the game chooses aspect and UI scale. One layout serves both games, so a switch changes nothing unless the logical size changes.
7. **Window identity.** `GameSetIdentity` (`chronicle:port/src/identity.cpp:8-15`) and `WindowSetIdentity` set the title and icon once. A switch can call `SDL_SetWindowTitle` (precedent: `chronicle:port/src/platform/firstrun.cpp:292`) and `WindowSetIdentity` for the next start.
8. **Draw services.** `draw2d::SetServices` (`chronicle:port/src/draw2d_port.cpp:34`) is a precedent for swapping per-game function tables without touching the 2D units.
9. **Loading screen as a shared presenter.** `PresentLoadingFrame` (`chronicle:port/src/nowload.cpp:143`) draws through the renderer from the idle hook, so an Ixion transition screen can use the same path between two games' ticks.
10. **First-run precedent.** `FirstRunIfNoData` (`chronicle:port/src/platform/firstrun.cpp:452-520`) proves the renderer can be shut down and rebuilt in-process before a fresh start, which is the basic move for a switch that changes the logical size.

## Risks and blockers

- **No second renderer.** `extern Context g` and the SDL singletons mean two windows or two devices in one process are not supported. `RendererInit` clears `g` (`kazarov@a0a5ff8:port/gfx/renderer.cpp:783`). Making the context an instance would touch roughly 640 `g.` references across `renderer.cpp`, `draw.cpp`, `resources.cpp`, `pipelines.cpp`, `displaylist.cpp` and `memory.cpp` (a grep at `kazarov@a0a5ff8:port/gfx/` counts 642 across those six files; inference that a refactor is large).
- **Logical size is fixed per renderer.** `logical_width`/`logical_height` are set at `RendererInit`; `SetFrameLayout` changes only aspect and UI scale. A DC2 512x480 frame and a DC1 640x480 frame cannot share a renderer without either a Kazarov change (a per-draw or per-list logical size) or a re-init on each switch.
- **Re-init destroys GPU state.** `RendererShutdown` drops every texture, mesh, render target and palette, and every display list's resources (`kazarov@a0a5ff8:port/gfx/renderer.cpp:815-865`). Each game's registry (`texture_port.cpp`) holds handles that die with it, so both games must re-upload on a switch.
- **Non-square texels at 4:3 for DC2.** A 512x480 logical frame shown at 4:3 is scaled per axis (`kazarov@a0a5ff8:port/gfx/draw.cpp:796-818`). Whether DC2's look is intended to match DC1's square pixels is an Ixion decision, not a bug.
- **`prog0_meshes` cost.** If one renderer serves both games, it must set `prog0_meshes = true`, which precompiles the Vu_prog0 pipelines (`kazarov@a0a5ff8:port/gfx/gfx.hpp:95`). Cost for DC1 is unmeasured (open question).
- **Pipeline cache location.** Each game's cache is `<save>/pipeline_cache.bin` (`chronicle:port/src/main.cpp:427`; `chronicletwo:port/src/main.cpp:289`). A shared renderer takes one path. Two caches would mean two sets of shader compiles on first run.
- **Symbol and global collisions.** Both trees define `main`, and each has process-global game state (`RunGame` in `chronicle:port/src/gameloop.cpp:791`, the 27 MB `GlobalDataBuffer` described in `chronicle:docs/PC_PORT_PLAN.md` line 112). Linking both into one binary needs namespacing or separate translation units. This is an inference from the names and the build layout, not a verified link failure.
- **Settings and paths are one process-wide set.** `SettingsSetEnvPrefix` and `PathsConfigure` are called once at start (`chronicle:port/src/identity.cpp:8-15`). A combined process has one env prefix and one data root unless Kazarov's settings become per-game.
- **Clock and idle hook are single slots.** A game that installs the idle hook replaces another's (`kazarov@a0a5ff8:port/platform/clock.hpp:56`).
- **Display lists are renderer-bound.** `RenderList` refuses a list from another renderer instance (`kazarov@a0a5ff8:port/gfx/displaylist.cpp:1165`). A list recorded before a re-init is dead after it.
- **Single-threaded.** The renderer, clock and pump are single-threaded (`kazarov@a0a5ff8:port/gfx/README.md` Lifecycle). A switch must happen between ticks on the main thread.

## Open questions

- Does the switch need a logical-size change at all? If Ixion keeps DC2's 512x480 frame inside a 640x480 virtual frame (letterboxed through `UiMapping`), one renderer with one logical size would serve both. Not checked: how DC2's 2D and 3D coordinates would map into the 640 frame.
- How long does a renderer re-init take with a warm pipeline cache? `PipelineCompileSeconds()` (`kazarov@a0a5ff8:port/gfx/gfx.hpp` near `PipelineCount`) reports it, but no measurement was taken.
- Does SDL allow `SDL_Vulkan_CreateSurface` on the same window after `SDL_Vulkan_DestroySurface`, as a re-init does with the window kept? The code path implies yes (no `WindowShutdown` between). Not tested; the first-run precedent destroys the window too.
- Does DC2's `mgInit(MG_SCREEN_MODE_512X480, 3)` (`chronicletwo:docs/PC_PORT_PLAN.md:110`) imply the PS2 renderer's frame buffer is 512 wide at a 640-wide display? Not verified against code here.
- Will Kazarov main's `Presentation2D` and `Interp2D` (`kazarov@9310c53:include/gfx/gfx.hpp`) change any of the seams above? Only the public API was diffed; the implementation was not read.
- Which of the 3D visual and texture registries have DC2 equivalents keyed the same way? Not checked here.
