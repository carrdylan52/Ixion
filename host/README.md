# Ixion host

`ixion.exe` runs Dark Cloud and Dark Chronicle as two game modules (`ixion_c1.dll`, `ixion_c2.dll`)
in one process and switches between them with F10. `ixion_fiber_smoke.exe` tests the fiber
switching the host depends on, with no games and no SDL. The host is Windows-only for v0. It links
only SDL3 and never includes game headers. The module ABI is `include/ixion_api.h`; the design
is `docs/HOP-V0.md`.

## Build

From a checkout with the Kazarov dependency root (`.kazarov/windows/deps`):

```
powershell -File host/build-windows.ps1 -Deps <deps root> -Build <build dir>
```

The script configures with the llvm-mingw `clang++`, builds `ixion` and `ixion_fiber_smoke`, and
copies `SDL3.dll`, `libc++.dll`, `libunwind.dll` and `libwinpthread-1.dll` beside them. It uses
`cmake` from PATH unless `-Cmake <cmake.exe>` is given.

For subsequent builds, use `cmake --build <build dir> --target ixion`.
Host and modules must all be rebuilt against ABI version 2; older modules are refused.

## Self-test

```
<build dir>/ixion_fiber_smoke.exe
```

Exit 0 means the fiber switches kept the root, game and nested fiber floating-point rounding modes
and resume order. Both `ixion` and the smoke test need the runtime DLLs in the same folder.

`cmake --build <build dir> --target ixion_host_tests ixion_module_probe` builds focused host
regressions and a DLL boundary probe. The probe takes a module path and a disposable save root;
it checks ABI rejection and that missing data returns through the actual module without setup.
Each game's plugin build also offers an explicit `ixion_c1_smoke` / `ixion_c2_smoke` target;
pass its known extracted-data root to test the recognizer as well as input, virtual gyro, audio
pause and embedded window lifecycle. These executables do not require the full ctest suite.

## Run

```
ixion.exe [--dc1 <ixion_c1.dll> --dc1-args "<args>"] [--dc2 <ixion_c2.dll> --dc2-args "<args>"]
          [--start dc1|dc2] [--auto-switch N:M] [--log <file>]
```

- `--dc1` and `--dc2` are optional module paths; supply at least one. Paths are made absolute before loading.
  Each supplied module uses its own data recognizer before boot. Missing data omits that game,
  without opening first-time extraction/setup; if none remain, startup exits 1. Extract each disc
  once with its game's tool, then use the extracted data without a mounted disc or ISO.
- `--dc1-args` and `--dc2-args` are passed to each game's `run()`. Words are split on whitespace.
  Double quotes group words and are removed. Backslashes are literal, so Windows paths need no
  escaping.
- `--start` picks the game shown first (default first available game, preferring `dc1`). If the
  requested game is unavailable, the remaining game starts. Only available games boot, and boot
  waits for a completed scene frame rather than accepting a loading checkpoint.
- `--auto-switch N:M` switches every N host frames, M times, then prints a summary. It exits 0 if
  no parked game's receipt (logic frames, clock ticks, mode, character, map, floor, position,
  scene readiness and rendered audio frames) changed while it was
  parked (checked when each parked game resumes, and at the end for the game parked last), and 2
  otherwise. Both receipts must report successful audio pause. F10 and `--auto-switch` require
  two available games: F10 logs a refusal in single-game mode; auto-switch is refused before boot.
- `--log <file>` also writes the log to a file. The log always goes to the console.

Example, with the layout from `HOP-V0.md`:

```
ixion.exe --dc1 ixion_c1.dll --dc1-args "--data <dc1 data> --save <dc1 save> --width 1280 --height 960 --jump edit:0" ^
          --dc2 ixion_c2.dll --dc2-args "--data <dc2 data> --save <dc2 save> --window 1280x960 --jump town:10"
```

Use fresh save folders. F10 travels between the games. Closing either window ends the program.

## Exit codes

| code | meaning |
| --- | --- |
| 0 | normal quit, or `--auto-switch` passed |
| 1 | bad arguments, SDL/module failure, no available data, or auto-switch with fewer than two games |
| 2 | `--auto-switch` saw a parked game's receipt change |
| 3 | a game did not reach scene readiness within 120 s |
| 4 | a game's `run()` returned |
| 5 | `--auto-switch` ended (quit or window close) before all M switches ran |

A game that never reaches a checkpoint cannot be timed out from the host's root fiber. The log
shows each game's boot step, so a stalled boot is visible.

A hosted `--frames` budget returns through `run()` and produces host exit 4, including when it
ends during loading. This is not auto-switch acceptance. Standalone frame-budget behavior is
unchanged. The host still ends the process directly on quit; orderly two-module teardown is future work.
