# Ixion

Ixion joins Dark Cloud and Dark Chronicle into one program: play any character from either cast,
visit any town or dungeon from either world, and use Dark Chronicle's time travel to cross between
the two. It is named after the flying, time-travelling train built at the Lunatic Wisdom
Laboratories in Dark Chronicle.

It is a fan-made proof of concept built on top of the community PC ports, not a replacement for
them:

- [TheMoonPeople/Chronicle](https://github.com/TheMoonPeople/Chronicle): the Dark Cloud
  decompilation and PC port.
- [TheMoonPeople/ChronicleTwo](https://github.com/TheMoonPeople/ChronicleTwo): the Dark Chronicle
  decompilation and PC port.
- [TheMoonPeople/Kazarov](https://github.com/TheMoonPeople/Kazarov): the build system and runtime
  both ports share.

Those projects carry on as they are. Ixion builds on them, and keeps its changes to them as small
branches that could be offered back.

No game data is stored here. Both games' data come from your own discs, extracted the same way as
for the two ports.

## Status

**Hop v0** works on Windows: `ixion.exe` loads both games as modules, keeps both resident, and
switches between them at the end of a frame. Press F10 in Norune and Palm Brinks appears exactly
where you left it; press it again and Norune resumes on the frame it left. Nothing crosses between
the games yet. See [docs/HOP-V0.md](docs/HOP-V0.md) for the design, the acceptance checks and the
open items.

Next: the **Ixion launcher**. Pick Dark Cloud, Dark Chronicle or both (each disc optional), start
at any town or dungeon floor, and use one developer panel for both games.

## Layout

- `host/` the host program (`ixion.exe`) and a fiber self-test. It links only SDL3 and never sees
  game headers.
- `include/ixion_api.h` the plain C interface between the host and the game modules.
- `games/chronicle`, `games/chronicletwo` the two ports as submodules, on branches that add the
  module build (`IXION_BUILD_PLUGIN`). Each one's `tools/kazarov` submodule points at a Kazarov
  branch that adds embedded mode.
- `docs/` the design ([DESIGN.md](docs/DESIGN.md)), the architecture options, the Hop v0 spec, a
  glossary, and [research notes](docs/research/README.md) on how both games and the shared runtime
  work.
- `tools/` analysis scripts.

## Building (Windows, llvm-mingw)

```
git clone --recurse-submodules https://github.com/carrdylan52/Ixion
```

Each port builds as described in its own README, with two extra CMake options that also build its
module:

```
-DIXION_BUILD_PLUGIN=ON -DIXION_API_DIR=<this repo>/include
```

That gives `ixion_c1.dll` (Dark Cloud) and `ixion_c2.dll` (Dark Chronicle). Build the host with
`host/build-windows.ps1` (see [host/README.md](host/README.md)), then put `ixion.exe`, both modules
and one shared set of runtime libraries in one folder and run:

```
ixion.exe --dc1 ixion_c1.dll --dc1-args "--data <dc1 data> --save <dc1 save> --jump edit:0"
          --dc2 ixion_c2.dll --dc2-args "--data <dc2 data> --save <dc2 save> --jump town:10"
```

Use fresh save folders.

## References

Notes cite code with `chronicle:`, `chronicletwo:` and `kazarov:` prefixes for paths inside the
three upstream repositories, and `ixion:` for paths in this repository.

## License

Ixion's own files are under the MIT License (see [LICENSE](LICENSE)). The submodules keep their own
terms. Dark Cloud and Dark Chronicle are trademarks of their owners; this project is not affiliated
with them.
