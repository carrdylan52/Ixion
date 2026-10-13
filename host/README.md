# Ixion host

`ixion.exe` runs Dark Cloud and Dark Chronicle as two game modules (`ixion_c1.dll`, `ixion_c2.dll`)
in one process and switches between them with F10. `ixion_fiber_smoke.exe` tests the fiber
switching the host depends on, with no games and no SDL. The host is Windows-only for v0. It links
only SDL3 and never includes game headers. The module ABI is `ixion/include/ixion_api.h`; the design
is `ixion/docs/HOP-V0.md`.

## Build

From a checkout with the Kazarov dependency root (`.kazarov/windows/deps`):

```
powershell -File ixion/host/build-windows.ps1 -Deps <deps root> -Build <build dir>
```

The script configures with the llvm-mingw `clang++`, builds `ixion` and `ixion_fiber_smoke`, and
copies `SDL3.dll`, `libc++.dll`, `libunwind.dll` and `libwinpthread-1.dll` beside them. It uses
`cmake` from PATH unless `-Cmake <cmake.exe>` is given.

## Self-test

```
<build dir>/ixion_fiber_smoke.exe
```

Exit 0 means the fiber switches kept the root, game and nested fiber floating-point rounding modes
and resume order. Both `ixion` and the smoke test need the runtime DLLs in the same folder.

## Run

```
ixion.exe --dc1 <ixion_c1.dll> --dc1-args "<args>" --dc2 <ixion_c2.dll> --dc2-args "<args>"
          [--start dc1|dc2] [--auto-switch N:M] [--log <file>]
```

- `--dc1` and `--dc2` are the module paths; both are required. Paths are made absolute before loading.
- `--dc1-args` and `--dc2-args` are passed to each game's `run()`. Words are split on whitespace.
  Double quotes group words and are removed. Backslashes are literal, so Windows paths need no
  escaping.
- `--start` picks the game shown first (default `dc1`). Both games boot before it is shown.
- `--auto-switch N:M` switches every N host frames, M times, then prints a summary. It exits 0 if
  no parked game's receipt (logic frames, clock ticks, map, floor, position) changed while it was
  parked (checked when each parked game resumes, and at the end for the game parked last), and 2
  otherwise.
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
| 1 | bad arguments, SDL failure, or a module that will not load |
| 2 | `--auto-switch` saw a parked game's receipt change |
| 3 | a game did not reach its first checkpoint within 120 s |
| 4 | a game's `run()` returned |
| 5 | `--auto-switch` ended (quit or window close) before all M switches ran |

A game that never reaches a checkpoint cannot be timed out from the host's root fiber. The log
shows each game's boot step, so a stalled boot is visible.
