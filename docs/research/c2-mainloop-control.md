# ChronicleTwo main loop and control flow

## What this covers

- How the ChronicleTwo PC port boots, runs its top-level mode loop, and changes modes (`chronicletwo:port/src/main.cpp`, `chronicletwo:port/src/mainloop.cpp`, retail `chronicletwo:ps2/src/mainloop.cpp` and `chronicletwo:ps2/src/mainloop3.cpp`).
- The tick clock and vsync waits (Kazarov `clock.cpp`), the frame-end wait and presentation pacing (`chronicletwo:port/src/mglib.cpp`, `chronicletwo:port/src/mglib_time.cpp`, `chronicletwo:port/src/present.cpp`, `chronicletwo:port/src/present_timing.hpp`).
- The cooperative PS2 thread emulation (Kazarov `eekernel_threads.cpp`) and the threads that share the main loop.
- Event-scene sequencing (`chronicletwo:ps2/src/sceneseq.cpp`, `chronicletwo:ps2/src/event.cpp`, `chronicletwo:ps2/src/runscript.cpp`) as the finer control layer under the mode loop.
- Yield-point candidates for an Ixion host that wants to suspend between frames and resume later.

Basis: read-only review of the `ixion` branch of the ChronicleTwo checkout (HEAD 40ec9083). Its `tools/kazarov` submodule is pinned at 3dc38ce; the clock, thread, and libgraph files cited here are byte-identical to the Kazarov main checkout (9310c53). Nothing was built or run. Inference is labelled.

## Key facts

- Entry is `main` (`chronicletwo:port/src/main.cpp:332`, which replaces retail `main` in `chronicletwo:ps2/src/main.cpp:138`). `Run` (`main.cpp:250`) parses options, loads config, opens the window and renderer, sets the tick rate, sets unbounded mode for headless, installs `PumpHost` as a pump hook and `VSyncCallBack` as the tick callback, sets the main thread priority to 10, and calls `MainLoop()` (`main.cpp:304-317`).
- Only process exits in the main path: window close in `PumpHost` (`main.cpp:215-217`), `--frames` in `mgEndFrame` (`chronicletwo:port/src/mglib.cpp:1350-1351`), window close in the FPS-overlay path (`chronicletwo:port/src/present.cpp:53-55`), `Exit()` (`kazarov:src/cpp/sce/eekernel.cpp:12-14`, `chronicletwo:port/src/dataread.cpp:502`), and assertions (`chronicletwo:port/src/runtime.cpp:10-15`). `main.cpp:214` states the game has no stop request for its loop.
- The game frame is `mgFrameRate` clock ticks. `MainLoop` sets it to 2 at every mode entry (`chronicletwo:port/src/mainloop.cpp:236`). `mgInit` also sets it to 2 (`chronicletwo:port/src/mglib.cpp:1113`). Default tick rate is 50 Hz (`chronicletwo:port/src/platform/config.hpp:9`; `chronicletwo:docs/PC.md` config table, unverified), so logic runs at 25 game frames per second.
- The clock is pump-driven, not threaded. `ClockPump` (`kazarov:src/cpp/platform/clock.cpp:133-160`) advances the count one tick at a time, runs the tick callback once per tick it crossed, then runs every pump hook in order, then the idle hook. A guard makes re-entry a no-op.
- `sceGsSyncV(mode)` is `ClockSyncV()&1` (`kazarov:src/cpp/sce/libgraph.cpp:7-9`). `ClockSyncV` waits for the next tick deadline, then pumps (`clock.cpp:194-197`). The field parity comes from the tick count (`chronicletwo:port/src/mglib_time.cpp:23-29`).
- Unbounded mode (headless, `main.cpp:305`) makes `ClockWaitNextTick` return at once without calling any wait hook (`clock.cpp:183-186`). `ClockPump` then advances exactly one tick per call (`clock.cpp:133-146`).
- The frame-end wait: `mgEndFrame` calls `PresentWaitFrame(old_vcount, mgFrameRate)` (`chronicletwo:port/src/mglib.cpp:1354`), which calls `mgTimeWaitTicks(start, frames, BetweenTicks)` (`chronicletwo:port/src/present.cpp:240-244`). That loop runs `ClockWaitNextTick(hook)` then `ClockPump()` until `count - start >= frames` (`chronicletwo:port/src/mglib_time.cpp:49-57`). `old_vcount` is then set to the count after the wait (`mglib.cpp:1355`), so an overrunning frame loses time rather than catching up.
- `BetweenTicks` is the only presentation work done during the wait. It draws interpolated display frames from the newest and previous display lists while the tick has not yet elapsed (`chronicletwo:port/src/present.cpp:154-192`). `PresentPacer` enforces `max_fps` and gives a due tick priority over display (`chronicletwo:port/src/present_timing.hpp:22-39`).
- Tick-callback side effect: the retail VSync callback adds one unit of play time per tick while `PlayTimeCountFlag` is set (`chronicletwo:ps2/src/mainloop.cpp:424-429`). The port registers it through `mgInitVSyncCallBack` (`chronicletwo:port/src/mainloop.cpp:98`).
- Mode dispatch uses three arrays indexed by mode: `LoopInit`, `LoopMain`, `LoopExit` (`chronicletwo:ps2/src/mainloop.cpp:100-135`). Modes are MENU, EDIT (town and georama), DUNGEON, TITLE, and five debug viewers and a save converter (`chronicletwo:ps2/include/mainloop.hpp:31-42`). Any mode number outside 0..9 ends the loop (`chronicletwo:port/src/mainloop.cpp:214-216`).
- `NextLoop(mode, arg)` only records `NextLoopNo` and `NextInitArg` (`chronicletwo:ps2/src/mainloop.cpp:349-352`). The switch happens when the inner loop breaks (`chronicletwo:port/src/mainloop.cpp:341-344`, `395-409`).
- `NextLoop` callers: `chronicletwo:ps2/src/title.cpp:1032` (title to dungeon), `chronicletwo:ps2/src/mapselect.cpp:966-968`, `chronicletwo:ps2/src/event_func.cpp:5415,5438`, `chronicletwo:ps2/src/dng_main.cpp:1083`, `chronicletwo:ps2/src/mainloop.cpp:647,899,1071`, `chronicletwo:ps2/src/mainloop3.cpp:216`.
- Frame body order inside the inner loop (`chronicletwo:port/src/mainloop.cpp:332-339`): `mgBeginFrame`, `LoopMain[mode]()`, `sndStep`, `MainScene.StepSnd`, pad `UpDate`, `PadCtrl.Update`, frame border, `mgEndFrame`. Then `mode_finished` is tested (`mainloop.cpp:341`).
- Every `GamePad__2.UpDate()` ends with `SwitchGamePadThread()` (`chronicletwo:port/src/gamepad.cpp` end of `UpDate`; `chronicletwo:ps2/src/gamepad.cpp:793-795`), which rotates the priority-10 ready queue. The controller thread (created at `chronicletwo:port/src/mainloop.cpp:196`; its priority constant is at `chronicletwo:ps2/include/gamepad.hpp:202`) runs its vibration step and rotates back (`chronicletwo:ps2/src/gamepad.cpp:803-818`).
- Kazarov threads are ucontext (POSIX) or Win32 fibers, each with a fixed 1 MiB stack. The PS2 `ThreadParam.stack` argument is ignored (`kazarov:src/cpp/sce/eekernel_threads.cpp:37`, `62-66`, `90-98`). Lower priority number wins; equal priorities rotate FIFO (`eekernel_threads.cpp:188-217`, `283-298`).
- Switches happen only in `StartThread` when the new thread outranks the caller (`eekernel_threads.cpp:262-281`), `RotateThreadReadyQueue` (`:283-298`), a blocking `WaitSema` (`:354-378`), a `SignalSema` whose waiter outranks the caller (`:380-414`), and thread return (`:219-233`). `Run` aborts if a switch is attempted while `ClockPumping()` is true (`:203-215`).
- The main thread is created with priority 1 (`eekernel_threads.cpp:140-148`). The game raises it to 10 (`chronicletwo:port/src/main.cpp:310-311`).
- Loading screen: `NowLoadingLoop` runs as its own thread at priority 10 (`chronicletwo:ps2/src/nowload.cpp:366-367`). It calls `mgBeginFrame`/`mgEndFrame` itself with `mgSetRotateThread(10)` set around the call (`nowload.cpp:273-275`). `DeleteNowLoading` spins on `SwitchNowLoadingThread` until the loader reports end (`nowload.cpp:390-401`).
- Event layer: `EventLoop` (`chronicletwo:ps2/src/event.cpp:282`) resumes the event script VM in its default command mode, that is, when it is not waiting on a door sequence or a sub-mode (`EventScript.resume()`, `CRunScript::resume` at `chronicletwo:ps2/src/runscript.cpp:247-254`, which calls `exe(pc)`). It then calls `EdEventStep` once if the script has not ended (`event.cpp:355-357`).
- `EdEventStep` (`chronicletwo:ps2/src/event_func.cpp:3254-3265`) calls `Play()` on each event object track and on the camera sequence, once per call. Per-frame sequence state is kept in node lists and fields, not on the C stack.
- `CSceneCmrSeq::Play` (`chronicletwo:ps2/src/sceneseq.cpp:1809`) walks five camera tracks. A command returning `SCENE_SEQ_WAIT` ends its track for this frame; `SCENE_SEQ_RETURN` jumps to the track's keep marker (`sceneseq.cpp:~1887-1893`; enum at `chronicletwo:ps2/include/sceneseq.hpp:17-21`). `CSceneObjSeq::Play` is at `sceneseq.cpp:3843`.
- `CONVERT_TO_PAL_FRAMES` rescales authored frame counts by 50/60 (macro near the top of `chronicletwo:ps2/src/sceneseq.cpp`; used 23 times). This fits one sequence step per two-tick game frame (inference from the 25 fps game-frame rate).
- Frame ends that are not the loop's own: `LoadMovie` runs its own frame loop with `mgBeginFrame`/`mgEndFrame` per movie frame (`chronicletwo:ps2/src/event_func.cpp:4707`, loop at `:4769`, `mgEndFrame` at `:4796` and `:4861`), reached from the `_LOAD_MOVIE` script command (`:4881`). So one `LoopMain` or `EventLoop` call can span many game frames. `MenuCapture` ends and begins a frame mid-menu (`chronicletwo:port/src/menudraw.cpp:129-130`). `PauseLoop` (`chronicletwo:ps2/src/nowload.cpp:514-628`) does one paused frame per call and ends it with `mgEndFrame` at `nowload.cpp:608`.
- The debug pause loop in the inner loop (`chronicletwo:port/src/mainloop.cpp:350-386`) calls `sceGsSyncV` and `UpDate` with no `mgEndFrame` in its body. Inference: nothing is presented while it runs.
- Input is pumped per tick: `PumpHost` calls `WindowPollEvents`, `DisplayPump`, `InputPoll`, and `InputScriptApply(mgPortFrameCount())` (`chronicletwo:port/src/main.cpp:215-221`). Scripted input is keyed to the game frame count, not wall time.
- A tick-rate config change re-anchors the clock without moving the tick count (`main.cpp:233-236`; `kazarov:src/cpp/platform/clock.cpp:76-82`).
- Headless runs never reach `BetweenTicks`, because the unbounded wait returns before the hook (`clock.cpp:183-186`). Their presents happen in `PresentTickEnd` and `PresentCanonicalFrame` (`present.cpp:246-261`).
- Documentation mismatch: `kazarov:include/platform/clock.hpp` says the default tick rate is 60 Hz. The port's config default is 50 (`chronicletwo:port/src/platform/config.hpp:9`) and `main.cpp:304` applies it before `MainLoop`. The effective default is 50.
- Retail loop variables are reached through link-name aliases (`chronicletwo:port/include/stubs/mainloop.hpp:6-26`; `chronicletwo:port/src/mainloop_port.hpp:11`). Inference: the unit-copy build step exports the retail statics under those names.

## How it works

### Boot to loop

1. `Run` (`main.cpp:250`) sets the game identity, parses options, applies jump and give hooks (`GameSetJump`, `GameSetGive`), and loads config.
2. It opens the window and the renderer (`gfx::RendererInit`), then sets the tick rate (`main.cpp:304`), unbounded mode for headless (`:305`), the pump hook (`:306`), the tick callback (`:307`), and the config-change hook (`:308`).
3. `MainLoop` (`port/src/mainloop.cpp:73`) maps the main arenas, initialises save and pad state, calls `mgInit` (`:96`), registers the VSync callback (`:98`), and runs a fixed sequence of `sceGsSyncV` calls to settle the first fields (`:111-127`). It loads fonts, sound and text tables, then starts the controller thread (`:196`).
4. `GamePrepareJump` (`port/src/test_hooks.cpp:162-219`) sets the first mode and its `INIT_LOOP_ARG` when a jump is requested. Otherwise the game boots into the logo fade and the title mode (`mainloop.cpp:199-202`, `:103`).

### Mode table

The three dispatch arrays are in `chronicletwo:ps2/src/mainloop.cpp:100-135`. Each row is mode number, then the Init, Main (per-frame step), and Exit functions.

| Mode | Name | Init | Main (per frame) | Exit |
|---|---|---|---|---|
| 0 | MENU (debug start menu; converted to TITLE unless DebugFlag) | `MenuInit` | `MenuLoop` | `MenuExit` |
| 1 | EDIT (town and georama) | `EditInit` | `EditLoop` (`editloop.cpp:1007`) | `EditExit` |
| 2 | DUNGEON | `InitDungeonMain` | `LoopDungeonMain` (`dng_main.cpp:983`) | `FinishDungeonMain` |
| 3 | TITLE | `TitleInit` | `TitleLoop` (`title.cpp:847`) | `TitleExit` |
| 4 | CHARA_VIEWER | `InitCharaViewerMain` | `LoopCharaViewerMain` | `FinishCharaVieweMain` |
| 5 | TEX_VIEWER | `InitTextuerViewerMain` | `LoopTextuerViewerMain` | `FinishTextuerVieweMain` |
| 6 | MAP_VIEW | `MapViewInit` | `MapViewLoop` | `MapViewExit` |
| 7 | SOUND_VIEWER | `InitSoundViewerMain` | `LoopSoundViewerMain` | `FinishSoundVieweMain` |
| 8 | MOVIE_VIEW | `MovieViewInit` | `MovieViewLoop` | `MovieViewExit` |
| 9 | SV_CONV_VIEW | `SVConvViewInit` | `SVConvViewLoop` | `SVConvViewExit` |

- Modes 1 (EDIT), 2 (DUNGEON), and 3 (TITLE) are the play modes. The developer-menu chord and the debug pause apply to them (`chronicletwo:port/src/mainloop.cpp:277-299`, `350-386`). Modes 4 to 8 are debug viewers; mode 9 is the save-conversion screen (`chronicletwo:ps2/include/mainloop.hpp:31-42`).
- `LoopMain` returns an int. Zero means the mode continues. Non-zero breaks the inner loop (`mainloop.cpp:341-344`).
- Frame timing at the default settings: tick = 20 ms; game frame = 40 ms (two ticks); display frames are paced by `video.max_fps` and interpolation (`chronicletwo:port/src/present.cpp:174-186`).

### Outer loop and mode change

- The outer `while (1)` (`mainloop.cpp:204`) resets the subgame arena for title or menu (`:205-210`), runs the optional capture hooks (`:222-234`), sets the frame rate to 2 (`:236`), refreshes time and day from save data (`:238-248`), and clears sound on the title (`:250-254`).
- It then calls `cut_interpolation`, `LoopInit[mode](InitArg)`, and `GameGiveOnArrival(mode)` (`:258-260`), and sets the pending mode to MENU (`:263`).
- The inner `while (1)` (`:276`) handles the developer menu chord (`:277-299`) and the capture and pad-driven pause checks, then runs the frame body (`:332-339`).
- When `mode_finished` is non-zero the inner loop breaks (`:341-344`). Then `LoopExit[mode]()` runs (`:395`), the previous mode and init are saved (`:406-409`), `PortLoopNo` takes the pending mode (`:408`), and the loop syncs twice and then spins `sceGsSyncV` until the field parity is 0 (`:410-416`).

### Frame timeline (one game frame, bounded clock)

1. `mgBeginFrame` (`chronicletwo:port/src/mglib.cpp:1195`) starts a display-list recording unless one is open. It applies a pending interpolation cut (`:1226-1232`).
2. `LoopMain[mode]()` runs one step of game logic. Mode functions return a non-zero value to finish the mode. Most of them are step functions with state in statics or objects.
3. `UpDate` on the pad and the `PadCtrl` update each switch to the controller fiber and back (see above).
4. `mgEndFrame` (`mglib.cpp:1273`) closes the recording, renders the canonical image, records the tick (`PresentTickRendered`, `present.cpp:217`), queues pick reads, and then calls `PresentWaitFrame`. The wait keeps running `BetweenTicks` for display frames until two ticks have elapsed (`present.cpp:240-244`), calling `ClockPump` after each tick. `PresentTickEnd` (`present.cpp:246`) presents the canonical image if no display frame was shown. Then `mgNowFrameRate` is set from the wall clock (`mglib.cpp:1357-1361`).

### Ticks and pumping

- `ClockPump` (`clock.cpp:133`) computes the target tick (`TickAt(now)` bounded, `count+1` unbounded). It runs the tick callback for each tick it advances, then pump hooks in registration order, then the idle hook. Pump hooks are `PumpHost` (`main.cpp:215`) and, headless, the audio mixer (`chronicletwo:port/src/audio_init.cpp:85`; the headless condition is unverified).
- Because callbacks run per elapsed tick, wall-time gaps are not lost: a stall of N ticks runs N callbacks (play time grows by N while enabled). Frame logic does not catch up, since `old_vcount` is reset after the wait.
- `ClockWaitNextTick()` (`clock.cpp:166`) sleeps until the next deadline. `SleepUntil` (`clock.cpp:65`) sleeps short of the deadline by `kSpinMargin` (1.5 ms) and spins the rest.

### Threads sharing the main loop

- Three PS2 threads run at priority 10 during normal play: the main game thread (`main.cpp:310`), the controller thread (`gamepad.hpp:202`), and, during loads, the loader (`nowload.cpp:366`). They rotate FIFO. A `UpDate` call round-trips through the controller thread.
- A thread blocked in `WaitSema` with nothing else ready aborts as a deadlock (`eekernel_threads.cpp:354-378`). `SignalSema` preempts only if the waiter outranks the signaller (`:380-414`).
- Movie threads are not used: the port replaces `CMovie` (`chronicletwo:port/src/movie.cpp`; `chronicletwo:docs/PC.md`, movie section around line 947).

### Event scene sequencing

- The event system is a two-level loop. `EventLoop` (`event.cpp:282`) runs the script VM to its next suspension point, then steps the sequences once for the frame, then acts on any request. Requests such as GOTO, LOAD_SCRIPT, SUB_MODE return codes to the mode loop, which then calls `NextLoop` or a map load (`chronicletwo:ps2/src/event.cpp`, from line 355 to the end of `EventLoop`).
- Each sequence command's result is `SCENE_SEQ_NEXT` (run the next command this frame), `SCENE_SEQ_WAIT` (resume next frame), or `SCENE_SEQ_RETURN` (jump to a marked command). That state lives in `_SEN_CMR_SEQ` and `_SEN_OBJ_SEQ` nodes and in the sequence objects.

## Ixion hooks

### Yield-point candidates

Each candidate is listed with what is live at that point. "Safe" means the stack holds no open recording and the clock is not pumping. Those are the two constraints `Run` and the display-list code enforce.

- **Y1, after mgEndFrame in the inner loop** (`chronicletwo:port/src/mainloop.cpp:339-342`). The frame is rendered and presented, and the recording is closed. Live locals: `mode_finished`, `developer_menu_requested`. Statics: `pmeter_flag`, `pause`. This is the best per-frame candidate. Safe.
- **Y2, PauseLoop boundary** (`mainloop.cpp:388-390`). `PauseLoop` returns after its own `mgEndFrame` (`nowload.cpp:608`). It keeps its state in statics (`InitFlag`, `PauseFlag__2`). Safe, and resumable without a stack if the caller is restructured.
- **Y3, mode-switch boundary** (`mainloop.cpp:395-409`, then `:259-260`). After `LoopExit` and before `LoopInit`, no mode is live. `PortNextLoopNo` and `NextInitArg` can be rewritten here. This is the natural place for a cross-world arrival. Safe.
- **Y4, tick boundary inside the frame wait** (`chronicletwo:port/src/mglib_time.cpp:49-57`, between `ClockWaitNextTick(hook)` and `ClockPump()`). Called once per tick during a frame's wait. Safe, but frequent. Not available in unbounded mode.
- **Y5, BetweenTicks** (`present.cpp:154-192`). Runs inside the wait hook, before the tick elapses. It is not pumping. Frequent, and not reached in unbounded mode. Host work here is presentation-only.
- **Y6, inside sceGsSyncV** (`clock.cpp:194-197`, between `ClockWaitNextTick()` and `ClockPump()`). Used by the boot sequence, mode-switch spin, debug pause, and several menus (`chronicletwo:ps2/src/menuop.cpp:650-713, 868`; `chronicletwo:ps2/src/editdata.cpp:313`). Safe.
- **Y7, debug pause loop** (`mainloop.cpp:360-382`). Each iteration is one `sceGsSyncV` and one `UpDate`. No `mgEndFrame`. Safe, but no presentation runs there (inference).
- **Y8, LoadMovie frame loop** (`event_func.cpp:4769-4861`). Each movie frame ends with `mgEndFrame`. Safe only with a preserved C stack, because it is inside one script command.
- **Y9, MenuCapture frame end** (`chronicletwo:port/src/menudraw.cpp:129-130`). Mid-menu frame. Needs a preserved stack.
- **Not safe:** anywhere inside `ClockPump` (tick callback `mglib_time.cpp:23`, `PumpHost` `main.cpp:215`, audio tick hook `audio_init.cpp:85`, idle hook). `Run` aborts a switch there (`eekernel_threads.cpp:203-215`). Also not safe between `mgBeginFrame` and `mgEndFrame` (the recording is open), and not safe to change frame layout inside a frame (`main.cpp:223-230` already guards this).

### Suspension options

- **A. Step refactor, no stack switch.** The retail structure supports this. The inner body (`mainloop.cpp:276-393`) holds only `mode_finished`, `developer_menu_requested` (captured by a lambda at `:265-274`), and the statics `pmeter_flag` and `pause`. The outer loop holds `memory`, `main_arena`, `user_data`, and `file_buffer`, of which only `memory` and `main_arena` are used past boot (`:205-210`). Hoist these and split the inner body into a function that returns "frame done, mode done, developer menu requested". The host can then return from `MainLoop` at Y1 or Y3 and re-enter later. Cost: the non-loop frame ends (Y8, Y9) still need a stack. Inference, not yet tested.
- **B. Run the game loop on a PS2 thread and hand off with semaphores.** This uses only existing Kazarov APIs. Sketch (inference from `eekernel_threads.cpp`): the host runs on the main thread, which sits at priority 1 (`:140-148`). The game thread runs `MainLoop` at priority 10. At a yield point (Y1, Y3, or Y6), the game calls `SignalSema(host_done)`, which preempts to the host because the host outranks it (`:380-414`), then `WaitSema(game_go)`. The host resumes the game by signalling `game_go` and waiting on `host_done`. The host must stay at a numerically lower priority than the game for the handoff to be immediate. `main.cpp:310` raises the main thread to 10, which would have to change. Cost: a 1 MiB stack for the game (see Risks).
- **C. Export a host fiber API from Kazarov.** `ContextCreate` and `ContextSwitch` are present but in an anonymous namespace (`eekernel_threads.cpp:62-104`). Exporting a minimal create, switch, and destroy pair would make option B unnecessary. This is a Kazarov change, so it would need a fork.

### Clock choice when suspended

- Use unbounded mode (`ClockSetUnbounded(true)`, `clock.cpp:89`) for suspendable runs. The tick count then moves only when the host pumps, the frame wait returns at once, and `BetweenTicks` is not called (`clock.cpp:166-192`).
- Under a real-time clock, a suspension of N seconds means N * tickrate callbacks on resume (`clock.cpp:133-146`). That adds play time while the play-time flag is set (`ps2/src/mainloop.cpp:424-429`). It also makes timed events jump.
- Changing the tick rate on resume does not move the count (`clock.cpp:76-82`). It only changes the rate of later ticks.

### World-crossing hook

- Set `PortNextLoopNo` and `NextInitArg` between `mainloop.cpp:395-409` and the next `LoopInit` at `:259`. `GamePrepareJump` (`test_hooks.cpp:162-219`) is the existing precedent for writing mode and `INIT_LOOP_ARG` before the first `LoopInit`.
- `INIT_LOOP_ARG` is 0x50 bytes with fields `map_no`, `floor_no`, `event_no`, `mc_load`, and an unknown 0x40-byte block at offset 4 (`chronicletwo:ps2/include/mainloop.hpp:213-223`). Any arg built across games must respect that layout.

## Risks and blockers

- **One loop per process.** Both games' loops, mode tables, and save and scene globals are file-scope singletons linked under `MainLoop_*` alias names (`port/include/stubs/mainloop.hpp:6-26`). Inference: a single Ixion binary that links units from both games would collide on those names and on `LoopNo`, `LoopInit`, and the save data. Merging them is a build-level decision, not a loop change.
- **Kazarov pins differ.** Chronicle pins an older Kazarov layout (a0a5ff8) and ChronicleTwo pins 3dc38ce. The clock and thread files should be re-checked against any Chronicle-side Kazarov before the two are combined.
- **Stack size.** A Kazarov thread gets 1 MiB regardless of the PS2 `ThreadParam.stack` (`eekernel_threads.cpp:37`, `62-66`, `90-98`). The retail controller thread's 1 KB stack (`ps2/src/gamepad.cpp:46`) is therefore not the real limit. Option B would move `MainLoop` onto a 1 MiB fiber. The deepest call path (event script, movie, menu) is unmeasured.
- **Thread-safety of the scheduler.** `Sched()` is a single static (`eekernel_threads.cpp:151-157`). The main thread is converted to a fiber at first use (`:54-59`), so kernel calls from any other OS thread are invalid.
- **No stop request.** Window close and `--frames` both call `std::exit` from inside the game's stack (`main.cpp:215-217`, `mglib.cpp:1351`). A host needs its own stop flag, polled at Y1 or Y3.
- **Frame boundaries are not unique.** `mgEndFrame` is called from `LoadMovie`, `MenuCapture`, `PauseLoop`, the loader thread, and `EventLoop`-driven code, not only from the inner loop. Counting "frames" by `MainLoop` iterations is wrong. Use `mgPortFrameCount()` (`chronicletwo:port/src/mglib.cpp`, Frame section near line 540) if frame identity matters.
- **Unbounded mode changes behaviour.** `BetweenTicks` never runs, and present happens only at frame end (`present.cpp:246-261`). In that mode `PresentTickEnd` draws `display_per_tick` interpolated display frames at each tick end (`present.cpp:253-257`), not from `BetweenTicks`, so a suspended run cannot be compared frame-for-frame with a bounded one.
- **Doc mismatch on the default tick rate** (see Key facts). Any Ixion code that reads the clock header as authoritative will get 60 Hz wrong.
- **Hidden switches.** `GamePad__2.UpDate()` switches threads. A host that assumes `UpDate` is pure will see extra fiber switches (`chronicletwo:port/src/gamepad.cpp` end of `UpDate`).

## Open questions

- Does any consumer depend on the field parity of the mode-switch spin at `mainloop.cpp:416`? If so, a host re-entry must preserve it.
- Does `LoadMovie`'s frame loop (`event_func.cpp:4769`) need to be suspendable in Ixion, or can the host refuse suspension during movies?
- What is the stack high-water mark of `MainLoop` under the heaviest scene (dungeon with event script and menu open)? This decides whether option B fits in 1 MiB.
- Is the debug pause loop (`mainloop.cpp:360-382`) reachable in a normal Ixion run, or only through the developer chord (`mainloop.cpp:277-299`)?
- Does the Chronicle side (DC1) use the same `ClockPump` / `WaitVSync` model? This was not checked here.
- Does retail `main` in `ps2/src/main.cpp` compile at all in the port build, or is it stripped by `PORT_OVERRIDE`? The override at `port/src/main.cpp:332` is the only `main` visible in the port source.
