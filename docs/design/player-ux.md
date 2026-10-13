# Ixion: player flow and hub UX

Status: design draft for the proof of concept. Scope is the player-facing flow:
boarding, the train hub, destinations, the character picker, saves, the
time-jump transition, and developer shortcuts. Engine architecture, the station
catalogue, and the character, item, and map crosswalks live in sibling documents
and are only referenced here.

Naming: "Dark Cloud" and "Dark Chronicle" are the in-game titles (Dark Chronicle
is "Dark Cloud 2" in the US release). The repository calls them Chronicle and
ChronicleTwo. This document uses the badges **W1** (Dark Cloud) and **W2**
(Dark Chronicle).

## 1. Goals and non-goals

Goals

- Make crossing worlds feel like the game's own idea: Ixion is the time-travelling
  train, so every transition is a departure.
- Keep each world playable as its original game, with native saves untouched.
- Show the player what travels with them before they go. Carry-over is the most
  likely source of confusion, so it gets its own screen.
- Work with the first architecture (each world on its own engine, hosted
  together) without depending on seamless co-residency.

Non-goals for the proof of concept

- Walking between worlds with no loading.
- Rendering W2 characters in the W1 engine, or the reverse. Those are
  content-crossover costs, phased in later (section 10).
- Balance or economy changes.

## 2. Assumptions

Each world runs on its original engine. A passenger state (party identity,
levels, HP, gilda, some items, translated weapons) is serialized at departure and
restored on arrival. The hub may run in either engine or a small host scene
(section 11); the player flow is the same either way.

## 3. Boarding Ixion

Ixion is built at the Lunatic Wisdom Laboratories in Dark Chronicle, so boarding
needs a canonical place in each world.

**W2.** The Luna Labs at Veniccio is the native boarding point, matching the
story where Max and Monica get access to Ixion there.

**W1.** Dark Cloud has no train. The **Ixion Halt** is a Georama-style build:
the player places a small station in a town they have rebuilt. Georama is the
game's own town-rebuilding system, so the station reads as part of that loop.
It unlocks after a bridging beat (open question) and costs the usual Georama
materials plus one bridging item.

```
  NORUNE VILLAGE                                     [Halt: built]
  ..........................................................
     Toan  ^                    ____  ____
           |                   | == || == |    <- Ixion Halt
                               |____||____|
  ---------------------------------------------------------
                 [X] Board Ixion   (party: Toan, Xiao)
```

Boarding rules

- The active party boards together. Everyone else appears in the Lab car as a
  passenger.
- Boarding is refused in combat, in a dungeon, or during a cutscene; the prompt
  says why. The first boarding in each world plays a short departure beat once.

## 4. The train as hub

The hub is the only place the player sees both worlds at once. The destination
board, the passenger roster, and the Ixion save all live here. Time does not pass
in the hub and there are no random encounters.

```
  [ENGINE]--[LAB]--[DINING]--[OBSERVATION]--[CARGO]
     exit     save,    rest,     destination    shared
              roster,  heal,     board          storage
              manifest passengers
```

- **Observation**: the destination board, and the default seat on arrival.
- **Lab**: the Ixion save, the passenger roster, and the manifest. Osmond is at
  the controls in the story, so he attends the Lab. The Idea Book and inventing
  also sit here, since inventing is a W2 system.
- **Dining**: heals the party and lists who is in the car.
- **Cargo**: storage shared across both worlds. Items are carried over only if
  marked for the manifest (section 7).
- **Engine**: the only exit, back to the last world visited.
```
 +-----------------------------------------------------------------+
 | IXION  -  Observation car                      Passengers: 3    |
 |   [window: stars streaming past, a faint pale band in the glass] |
 |   Current era: Present (W2)        Last stop: Palm Brinks       |
 |   [X] Destinations   [Square] Lab   [Tri] Dining   [O] Engine   |
 +-----------------------------------------------------------------+
```

## 5. Destination picker

The board has three axes: **era**, then **world**, then **place**. Era comes
first because it is where the player's sense of time is. Dark Chronicle's eras
(past, present, future, as the story uses them) map onto the board directly.
Dark Cloud has no time-travel mechanic of its own in the sources read so far, so
it sits on its own era line rather than being assigned to a W2 era. That choice
is a story decision and is left open.

```
 +----------------- IXION DESTINATIONS ---------------------------+
 | ERA:  < Terra (W1) >   [ Present ]   [ Future ]   [ Past ]     |
 |                                                                |
 |  > Norune Village         W1   visited   floors -              |
 |    Palm Brinks            W2   visited   floors -              |
 |    Divine Beast Cave      W1   dungeon   2 / 8 floors          |
 |    Gundorada Workshop     W2   ? not reached                   |
 |    Veniccio               W2   visited   (Luna Labs)           |
 |                                                                |
 |  Left/Right: era   Up/Down: place   X: go   O: back            |
 +----------------------------------------------------------------+
```

Rules

- **Visited only.** A place is pickable after the player has been there in that
  world. Unvisited places show as "? not reached", so the route is visible.
- **Eras filter, they do not gate.** Changing era only filters the list.
- **Dungeons open a floor select.** Floor progress is read from the engine save
  that owns the dungeon, so the board never invents progress.

```
 +------------- DIVINE BEAST CAVE (W1) ---------------+
 |  F1   cleared                                       |
 |  F2   cleared                                       |
 |  F3   open  <- entry point                          |
 |  F4   locked (not reached)                          |
 |  X: enter at selected floor    O: back              |
 +-----------------------------------------------------+
```

Entering at a floor needs that floor cleared or reached in the world's save.

## 6. Character picker

Two lists, in the Lab car, because the party is a train decision rather than a
field decision.

1. **Active party**: who is in the field after the jump.
2. **Passengers**: everyone else on the train. They wait in the Lab car and can
   be swapped in at a stop that can render them.

```
 +------------------- PASSENGERS -----------------------------+
 | ACTIVE PARTY                                               |
 |  [1] Toan      W1  Lv 12   field-ready                     |
 |  [2] Monica    W2  Lv 30   field-ready                     |
 |  [3] --                                                    |
 | PASSENGERS (on the train, not in the field)                |
 |      Max       W2  Lv 31   field-ready only in W2          |
 |      Xiao      W1  Lv 10   field-ready only in W1          |
 |  X: set slot   Triangle: swap   O: back                    |
 +------------------------------------------------------------+
```

The key rule: a character is field-ready only in a world whose engine can render
their model and motion. A character who is not field-ready in the current world
is shown as a passenger with the reason, not hidden. That stops the picker from
offering something the engine cannot draw. Crossover work (section 10) turns more
characters field-ready without changing the picker. Party size follows the
current engine's own limit; the picker does not invent a combined limit.

## 7. Save and load across two games

An Ixion save is a bundle. Ixion never writes the native saves, so each game
stays playable on its own.

- The bundle is a manifest plus the two engine saves it refers to, in one folder.
  The Dark Cloud port already keeps one folder per save with a small shared state
  file, so the bundle follows that pattern.
- The manifest holds the passengers, the roster, the active party, the era and
  place, the cargo marks, and the time of the last jump.
- Writing is one action: both engine saves and the manifest. If either write
  fails, the bundle is not marked complete and the player is told which half
  failed.

```
 IXION SAVE                                                 Slot 2
 +----------------------------------------------------------------+
 | Party:       Toan Lv 12, Monica Lv 30                           |
 | Passengers:  Max Lv 31, Xiao Lv 10                              |
 | Location:    Present (W2) - Palm Brinks                         |
 | Gilda:       3,400 (W1 share 1,200 / W2 share 2,200)            |
 | Saved:       2026-10-13 16:20                                   |
 |  X: load bundle    Triangle: view manifest    O: back           |
 +----------------------------------------------------------------+
```

Load rules

- **Partial bundle.** If one engine save is missing or unreadable, the bundle
  shows as incomplete. Its manifest can be read but it cannot be loaded, and the
  screen names the missing half. No silent fallback.
- **Native saves stay separate.** The title screen lists Ixion Continue beside
  the two native continues. A native continue never touches the bundle.
- **Autosave on departure.** Each jump writes the bundle before the time-slip. A
  crash during a jump loses at most the time-slip.
- **Title order.** Ixion Continue sits above the two native continues.

## 8. The time jump: transition and loading

A time jump is a sequence the player sees, not a hidden load. It has four beats,
and all but the first can be skipped after the first time.

1. **Decide**: destination picked on the board.
2. **Manifest**: the carry-over screen. The player confirms or adjusts.
3. **Depart**: the departure beat in the hub. The bundle is written here.
4. **Time-slip**: the loading screen, then the destination engine takes over.

```
 +------------------------- MANIFEST --------------------------+
 | CARRIED                              | LEFT BEHIND           |
 |  Toan     Lv 12   HP 88/120          |  <weapon> (no class   |
 |  Monica   Lv 30   HP 301/340         |     equivalent in W1) |
 |  Gilda    3,400                      |  <item> x2 (not in    |
 |  Items    6 of 9 (cargo marks)       |     the crosswalk)    |
 |  Weapons  2 translated to nearest    |                       |
 |  X: depart    Triangle: adjust items    O: cancel            |
 +--------------------------------------------------------------+
```

```
 +--------------------------------------------------------------+
 |                  ~  T I M E   S L I P  ~                     |
 |   Toan ..................... carried                          |
 |   Monica ................... carried                          |
 |   Gilda .................... 3,400                             |
 |   Weapon (Toan) ............ translated                       |
 |   [==========..........]  arriving: Divine Beast Cave        |
 +--------------------------------------------------------------+
```

Timing and behavior

- The time-slip reuses the Dark Cloud loading-bar style so the games feel like one
  train. Target: under 10 seconds for a same-era jump on proof-of-concept hardware.
  The bar must keep moving on longer jumps.
- The manifest is never skipped when it has a "left behind" entry.
- One item that fails to translate goes to "left behind" with a reason. Only an
  unreadable or unwritable bundle aborts the jump.
- Levels, HP, and gilda carry over as-is. Mapped items carry; unmapped ones are
  left behind. Weapons go to the nearest class and are marked "translated".
  Cargo carries only if marked in the Cargo car. The crosswalks define the mapping.

## 9. Debug and developer shortcuts

A prototype needs fast travel and a way to see state. All of it sits behind debug
mode, so release players never see it.

- The W2 port already has a developer toggle: a shoulder-button chord plus R3,
  active once the developer code is set (`debug_mode` in the port source). Ixion
  reuses that chord and adds a developer menu behind it. The W1 port's debug
  gating has not been checked and must be confirmed before the menu is wired
  there.
- The developer menu offers: warp to any station (visited or not); jump without
  manifest review; skip the time-slip; dump passenger state to the log as JSON;
  mark every place visited; force a bundle reload from disk to test partial
  bundles.
- The menu is off in release builds and not reachable from the title screen.
  No login is involved; the debug chord is the only gate, as in the existing ports.

## 10. Phasing

**Phase 0, two launches with a bundle.** The bundle exists and the hub is a
static menu. A jump writes the bundle, closes the current engine, and starts the
other with the bundle loaded. The time-slip is a plain loading screen.

**Phase 1, passengers and a live hub.** The hub runs in a host scene. Passengers
and the picker are live, and jumps hand the passenger state over in memory. The
time-slip becomes the real transition. Only characters with a native model in
the current engine are field-ready.

**Phase 2, crossover and co-residency.** Converted characters become field-ready in
the other world; the picker does not change. If both engines can share a process,
the time-slip can shrink. This is the expensive phase; the flow does not need it.

## 11. Open questions

1. **Hub host.** Does the hub run in one of the two engines or in a small third
   scene? It changes how the time-slip is built, not what the player sees.
2. **Dark Cloud's bridging beat.** What unlocks the Ixion Halt in W1: a story
   beat, an item, or a Georama milestone?
3. **Era for Dark Cloud.** Its own era line (the default here) or a mapping onto
   a Dark Chronicle era. A story decision.
4. **Party size across worlds.** Each engine has its own limit. The default here
   is the current world's limit rather than the lower of the two.
5. **Co-residency feasibility.** Decides whether Phase 2 can drop the time-slip.
   Architecture owns this.
6. **Manifest wording.** "Translated" and "left behind" need a playtest.
