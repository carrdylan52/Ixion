# Ixion — Dark Cloud × Dark Chronicle

A fan-made crossover experiment built on the community PC ports of **Dark Cloud**
and **Dark Chronicle / Dark Cloud 2**. The goal is to combine places, characters
and gameplay systems from both games in one program.

**This is the `showcase-crossover` source branch.** It contains the later crossover
demo, including Opar's Dark Cloud behaviour running inside Dark Chronicle. `main`
contains the earlier Hop v0 prototype. This branch pins the versions used by the
working crossover; migration to current upstream asset formats is separate work.

## What's here

| Experiment | Implementation |
|---|---|
| Opar and other DC1 monsters in DC2 | Donor script native table, motion/collision adaptation, native DC2 monster slots and combat. |
| DC1 rooms in DC2 | Offline geometry, texture and collision conversion; room encounters, props and exit markers. |
| Toan, Goro, Ungaga and Xiao in DC2 | Converted bodies plus isolated DC1 combat code and lifecycle adapters. |
| Monica as Opar | Transformation profile and an experimental donor behaviour mode. |
| Ridepod and Vanguard in DC1 | Isolated donor mechanics, model converters and host-side collision/combat bridges. |
| Georama across both games | Norune houses/villagers in DC2 and a DC2 Shed in Norune. |
| Both games resident | Windows fiber host; F10 switches at frame checkpoints. A bounded kill ledger can deliver Water across games. |

These are experiments with different levels of coverage, not a finished merged
campaign. See [the demo guide](tools/playtest/PLAYTEST.md) for the 29 modes and
their specific limits. Six modes have a supplied pack recipe; the other 23
are source prototypes with pack recipes not yet published. Physical controller
feel, audible output and complete
campaign progression remain unqualified.

## Start here

```sh
git clone --branch showcase-crossover --recurse-submodules https://github.com/carrdylan52/Ixion.git
cd Ixion
python -B -m unittest discover -s tests -p "test_*.py"
```

The synthetic converter/protocol tests need Python 3.10+ and no game data. Cases
that need an owner's extraction skip when it is absent. Building/running the
games requires Windows, the pinned toolchain and your own discs.

**[Build and reproduce the Opar demo →](docs/SHOWCASE.md)**

Opar's implementation is in
[`ixion_dc1_monster.cpp`](https://github.com/carrdylan52/ChronicleTwo/blob/showcase-crossover/port/src/ixion_dc1_monster.cpp).
The source-only converters are in [`tools/`](tools/), including
[`monster_converter.py`](tools/monster_converter.py) and
[`room_converter.py`](tools/room_converter.py).
No disc assets, extracted packs, saves or playable binary bundle are included.

## Architecture and upstream

`host/` loads `ixion_c1.dll` and `ixion_c2.dll` through the plain C interface in
`include/ixion_api.h`. Each port keeps its own engine state; adapters live in the
PC port layer. The matching source branches are pinned as recursive submodules.
Read [host/README.md](host/README.md), [the original Hop design](docs/HOP-V0.md),
and [the room converter format](docs/room-converter.md) for implementation details.
The notes under `docs/research/` describe earlier investigations, not current
acceptance claims.

Ixion depends on the work of:

- [TheMoonPeople/Chronicle](https://github.com/TheMoonPeople/Chronicle) — Dark Cloud decompilation and PC port.
- [TheMoonPeople/ChronicleTwo](https://github.com/TheMoonPeople/ChronicleTwo) — Dark Chronicle decompilation and PC port.
- [TheMoonPeople/Kazarov](https://github.com/TheMoonPeople/Kazarov) — shared build/runtime infrastructure.

Please reproduce Ixion-specific issues on these pinned branches before reporting
them here. The upstream ports develop independently.

## License

Ixion's own source is [MIT licensed](LICENSE); submodules retain their upstream terms.
Dark Cloud and Dark Chronicle belong to their respective owners. This project
is unofficial and unaffiliated with them.
