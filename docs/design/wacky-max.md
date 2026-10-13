# Ixion: the maximum mashup

This is the wild-idea pass for Ixion. It assumes the baseline the research wave is
checking: each world keeps its own engine, the two run side by side, and a
passenger state crosses the time gate. Every idea below is ranked by wow per unit
of engineering, and each one says how much content crossover it needs. The
ranking is a judgement, not a measurement. The engineering tiers are defined
first so the table can be read without the prose.

## How to read the ranking

Wow is 1 to 5: how much a player would stop and say "wait, that's in the game?"

Engineering tiers, cheapest first:

- **T0, data and UI only.** Tables, names, string maps, a new screen. No new
  code path in either engine.
- **T1, handoff.** A value, a picture or a file crosses the process boundary
  (see the architecture note below). The receiving engine reads it through a new
  loader.
- **T2, sub-game port.** A self-contained module from one codebase is compiled
  into the other. Its own state, its own input and its own draw code move with
  it. No new asset format is needed if the module reads only data it can name.
- **T3, asset or format conversion.** Models, motion, monster scripts or map
  parts from one game are converted into the other game's formats. This is the
  expensive part the brief describes.
- **T4, runtime co-habitation.** Two worlds' actors share one live frame, one
  battle or one floor, with one collision and one script clock. This is the
  most expensive tier, and it is the one that pushes toward a unified engine.

Crossover flags: `none` (each world keeps its own content), `data` (names,
numbers, icons), `picture` (a rendered frame or texture moves across),
`asset` (a model, motion or script moves across), `runtime` (two worlds' actors
share a live scene).

## Engine facts that bound the ideas

These were checked in the two decompiled trees (chronicle: is Dark Cloud,
chronicletwo: is Dark Chronicle). They are facts about the code, not the
wiki.

- **Both are PS2 decompilations with PC ports on the same shared base.** Each
  has its own `main` in `port/src/main.cpp`, so each already runs as its own
  process. The shared Kazarov layer supplies the renderer and mixer. Both trees
  have `ps2/src/mglib.cpp`, so the mg library lineage is real.
- **Same-process hosting collides on names.** `class CSaveData` and
  `class CMenuCursor` are declared in both trees' `savedata.hpp`, with different
  layouts. Putting both engines in one binary needs namespacing, separate
  static libraries, or a shim. The first version should use two processes and a
  launcher, which is what the wider design already assumes.
- **Dark Chronicle code has the systems Max and Monica use.** Photo mode
  (`photo.cpp`, `TakePhotoMode` with a shutter that copies the frame buffer into
  a picture), inventing (`inventmn.cpp`), fishing (`fishing.cpp`, `fishingobj.cpp`),
  Spheda (`sphida.cpp`, `CSphidaData` with per-player horl scores), Finny Frenzy
  (`gyorace.cpp`, `CGyoRaceData`), the Ridepod as an action character
  (`ACTION_CHARA_ROBO` with walk, tank and bike movers), and Monica's monster
  transformations (`monster.hpp`, `MOS_CHANGE_PARAM`, `MOS_HENGE_PARAM`).
- **The monster transformation is keyed by name.** `MOS_HENGE_PARAM` holds a
  `script_name` that the loader turns into a `.stb` path, plus four effect base
  names. That is a seam: a Dark Cloud monster can be given a Dark Chronicle
  transformation row, and the loader will look for its script by basename. The
  files it finds are the hard part.
- **Dark Cloud has fishing and an attribute-based synthesis, not photo or
  Spheda.** `fish.hpp` (`FishInfo`, 0x48 bytes, with bait affinity) and
  `fishing.cpp` exist. No Ridepod, photo, inventing or Spheda source turns up
  in the Dark Cloud tree. Weapon synthesis and Synth Spheres are described in
  the wiki; their code was not traced in this pass.
- **Dark Cloud already has test hooks for mashup work.** The PC notes list a
  `--jump` flag (any town, interior or dungeon floor select), `--give` (items by
  number), and a developer menu. That lets a mashup scene be reached on demand
  without finishing either story.
- **The Dark Genie is in the Dark Chronicle canon.** The wiki says a Dark Genie
  attacks in the optional Zelmite Mine epilogue. A name search of the
  Chronicle Two source turned up no `genie` reference, so the model is probably
  in the disc data under a different name. That needs checking against the
  extracted assets before any idea below depends on it.

Not verified in code, and treated as open: whether Spheda and Finny Frenzy
depend on Dark Chronicle-only globals, whether Dark Cloud's enemy scripts can
drive the Dark Chronicle monster loader, and whether the Ridepod's movers need
Dark Chronicle character rigs.

## The ranked list

Rank order is wow per engineering, with cheap, high-wow ideas first.

| # | Idea | Wow | Tier | Crossover | First step |
|---|------|-----|------|-----------|------------|
| 1 | Photograph a Dark Cloud town or floor, then invent a Ridepod part from the picture | 4 | T2 + T1 | picture | Port the photo mode into the Dark Cloud process as a camera module; write the picture into the passenger file |
| 2 | Toan's voice in the Ridepod's Voice Unit (random lines) | 4 | T0 | data | Add a line table keyed on pilot; reuse the Voice Unit trigger |
| 3 | Dark Genie boss fight in the Zelmite Mine, used as a Dark Chronicle boss rush with Griffon | 5 | T0 if the model exists, else T3 | asset | Confirm the Genie model and motion in the extracted data |
| 4 | Spheda on Dark Cloud floor clears, rewarded in Atla or ABS | 4 | T2 | none | Port `sphida.cpp` into the Dark Cloud tree with its own state |
| 5 | Finny Frenzy with Dark Cloud river fish | 3 | T2 + T0 | data | Feed the Dark Cloud fish table into the race's fish list |
| 6 | Dark Chronicle lure fishing in Dark Cloud rivers | 3 | T2 | data | Port the lure-rod path; keep Dark Cloud `FishInfo` for the fish |
| 7 | Synth Sphere attachments read as Ridepod energy-pack parts | 3 | T0 | data | Crosswalk table: sphere stats to pack stats |
| 8 | Ixion train as a menu hub that lists any unlocked floor from either world | 4 | T0 | none | A screen that reads both passenger files and the floor list |
| 9 | Gallery of Time as a station that replays Dark Cloud memory floors | 3 | T0 + T1 | picture | A still picture per memory, shown in the Ixion hub |
| 10 | Ghost Atla: Dark Cloud Atla objects drift into a Dark Chronicle town as memories | 3 | T1 + T3 | picture, asset | Start with billboard sprites rendered from the Dark Cloud frame |
| 11 | Monica transforms into a Dark Cloud monster (stats and name only, Dark Chronicle model) | 4 | T0 | data | Add `MOS_HENGE_PARAM` rows with Dark Cloud stats; reuse a Chronicle model |
| 12 | Monica transforms into a Dark Cloud monster with its own model and motion | 5 | T3 | asset | Convert one monster's model and `.stb` script |
| 13 | Toan drives the Ridepod with his own model | 4 | T3 | asset | Port one character rig into the Ridepod rig loader |
| 14 | Dark Cloud Ridepod-style mech in the Dark Cloud tree (the Ridepod ported in reverse) | 4 | T3 + T2 | asset | Port the mover code; reuse Dark Cloud rigs |
| 15 | Georama town where Atla houses sit beside Georama parts | 4 | T3 | asset | Map Atla structures onto Georama part IDs with a fixed model set |
| 16 | Dungeon character change (the Stand-In Powder the Dark Cloud dev menu references) for Max and Monica | 2 | T0 | none | Item and state swap; no new model |
| 17 | Xiao's slingshot and Max's gun trade shots in one battle | 5 | T4 | runtime | Requires a shared battle loop; treat as a late-phase goal |
| 18 | Monsters from both worlds on the same floor | 5 | T4 | runtime | Requires one spawn table and one script clock; late-phase |
| 19 | Dark Genie versus Griffon as a shared finale on the Sun Stone floor | 5 | T4 | runtime | Requires both bosses in one scene; late-phase |
| 20 | Dark Cloud floor as the backdrop of a Dark Chronicle battle | 3 | T3 | asset | Load a Dark Cloud floor mesh as a static stage |

### Notes on the top items

**1. Photo-to-invent across worlds.** This is the best ratio. Photo mode in
Dark Chronicle is a camera state that copies the frame buffer into a picture
and stores the subject distance. Porting that camera module into the Dark Cloud
process gives Toan a camera without touching Dark Cloud's rendering. The picture
goes into the passenger file, and Dark Chronicle's inventing screen reads it
as an idea source. The wow is that a Dark Cloud object becomes a Dark Chronicle
blueprint. The cost is one module port, one handoff and a crosswalk of which
Dark Cloud objects can be invented.

**2. Toan in the Voice Unit.** The Ridepod's Voice Unit already makes random
comments, which is a data trigger. Toan lines from the Dark Cloud data would be
a T0 change if the voice files are converted to the Dark Chronicle sound format,
which is a small asset task.

**3. Genie and Griffon.** The Dark Genie already shows up in Dark Chronicle's
canon. A boss rush against Griffon and the Genie is the strongest wow in the
list. The first thing to confirm is whether the Dark Chronicle disc already has
a Genie model and motion. If it does, this is T0. If it does not, it becomes a
model conversion (T3), which is the same work as idea 12.

**4. Spheda on Dark Cloud floors.** The Spheda module is self-contained enough
to read as a sub-game. It keeps its own player and score data, and it is the
kind of code that moves as one unit. The Dark Cloud floor reward would need a
replacement for the medal, and Atla or ABS fit.

## Shape of a playable slice

A first slice that shows the wow without any runtime co-habitation:

1. The Ixion hub (idea 8) lists the floors and passenger files.
2. Toan, passed in as a passenger, takes a photo of a Dark Cloud town (idea 1),
   which the Dark Chronicle inventing screen then reads.
3. Max and Monica get a Spheda game on a Dark Cloud floor clear (idea 4), and
   the reward is passed back as an Atla item.
4. A Dark Genie fight in the Zelmite Mine (idea 3) is the finale, if the model
   check passes.

That slice needs T0, T1 and T2 work only. Nothing in it requires two worlds to
share a frame, a battle or a floor.

## What this doc does not decide

- The station catalogue and the passenger-state fields. Those belong in the
  architecture doc.
- Whether to pursue content conversion at all. The ideas marked T3 and T4 are
  the ones that justify a unified engine, and this doc does not argue for one.
- Legal and distribution limits on shipping converted game assets. Ixion runs
  each game from the user's own disc. No game data is stored in the repository.

## Open checks before committing to any idea

- Confirm the Dark Genie's model, motion and script in the Dark Chronicle data.
- Confirm whether Spheda and Finny Frenzy read only their own state or reach
  into other Dark Chronicle globals.
- Confirm whether the Dark Cloud save layout exposes the Atla and ABS values
  that the rewards would write.
- Check the Dark Chronicle monster loader against a Dark Cloud enemy script
  before choosing between idea 11 and idea 12.
