# Ixion Game Design

Status: proof-of-concept design draft. The spine is the one-hop, one-weapon design,
with grafts from four others (see Sources).

Tags used throughout:

- **canon**: stated in either game or its wiki article.
- **inferred**: one reasoning step from canon.
- **proposal**: an Ixion design choice, not a claim about either game.
- **verify**: needs a code or disc check before anything relies on it.

Code references use the repository prefixes `chronicle:` (Dark Cloud) and
`chronicletwo:` (Dark Chronicle).

## 1. Pitch

Ixion runs two games side by side and lets the player cross between them on the
time-travelling train. Each world keeps its own engine. Ixion is a launcher, a
bundle format and a set of station rules, not a shared runtime.

The first crossing is small. Max boards the train at the Luna Labs, steps off in
Norune Village and plays Toan through one cave floor carrying one weapon. The
weapon fights differently in Toan's hands, gains kills on the far side and comes
home changed. One object teaches the whole concept. The design then widens in
steps: more passengers, more stops, sub-games, and only last the content
crossover (models and motion) that is the expensive part.

The long-term fantasy is any character and any town or dungeon from either world.
Section 6 says what is playable at each phase.

## 2. Premise

### 2.1 Canon the train must respect

- **canon**: Ixion is built at the Luna Labs in Veniccio. Max and Monica board it
  there, Osmond pilots it, and it is sent toward Griffon's era, about 10,000 years
  in the past.
- **canon**: Dark Chronicle's Atlamillia are time stones; Monica travels back and
  Max forward. Dark Cloud has a Gallery of Time dungeon mode
  (`chronicle:ps2/include/dungeon.h`) and Seda's forward travel, so Dark Cloud is
  not a world without time travel.
- **canon**: Atla hold houses, people and objects, and become pieces of the town
  once removed. The Moon People appear in both games.

### 2.2 Why the train reaches Terra

**proposal**: Terra sits inside Ixion's reachable span (inferred from the
10,000-year route; canon never dates Terra) and its towns are preserved in Atla. A
Terra arrival is an Atla opening at station scale. Fallback if rejected: Terra is a
separate time stream that Ixion opens.

### 2.3 Passengers are Atla-packed

**proposal**: characters and items cross as Atla-packed passenger state and are
unpacked at a station on arrival. This gives the crossing a canon operation.
Weapon and HP translation are Ixion mechanics, not lore requirements. Who may
unpack is open (section 9).

### 2.4 Who runs Ixion

- **proposal**: the Luna Labs at Veniccio is the base station.
- **proposal**: Osmond is a lineage title, not one person. The Yellow Drops leader
  and the Luna Labs researcher are two holders of it. This avoids reconciling two
  fixed personalities.
### 2.5 Canon constraints

- **canon, binding**: characters who die stay dead. Ixion revisits them only as
  memory, time-residue or lineage. The Dark Chronicle epilogue's Dark Genie fight is
  existing canon and can be replayed.
- **post-canon branch**: Dark Chronicle's ending (time travel forbidden) is not
  retconned. Ixion is a named branch from it.

## 3. Player flow

### 3.1 Boarding Ixion

- **Dark Chronicle**: the Luna Labs in Veniccio is the canonical boarding point.
  Palm Brinks is a destination, not the departure.
- **Dark Cloud**: there is no train in-world. The **Ixion Halt** is a
  Georama-style build the player places in a rebuilt town. The MVP pre-places one
  at Norune by debug flag. In the full game it is earned through Georama plus a
  bridging item (open).
- Boarding is refused in combat, in a dungeon or during a cutscene. The prompt
  says why. The first boarding in each world plays a short departure beat.
- **proposal**: the fare is one Starglass, a time-travel key (where it is bought is
  verify).

### 3.2 The train as hub

The hub is the only place both worlds appear together. Time does not pass and
there are no random encounters.

| Car | Contents |
|---|---|
| Observation | Destination board; default seat on arrival |
| Lab | Ixion save, passenger roster, manifest; Osmond at the controls; inventing (a Dark Chronicle system) |
| Dining | Heals the active party; lists who is in the car |
| Cargo | Shared storage; items cross only if marked on the manifest |
| Engine | The only exit, back to the last world visited |

### 3.3 Destination picker

- Three axes: era, world, place. Eras filter the list; they never gate it.
- **Visited only.** A place is pickable once the player has been there in that
  world. Unvisited places show as "not reached" so the route is visible.
- Dungeons open a floor select, read from the owning world's save. Dark Cloud's era
  is open (section 9).

### 3.4 Character picker

- Two lists in the Lab car: the **active party** (in the field) and
  **passengers** (on the train).
- A character is field-ready only in a world whose engine can render their model
  and motion. Others are shown as passengers with the reason, not hidden.
- Party size is the current engine's own limit.
- A floor's "who may fight" restriction is authoritative.

### 3.5 The time jump

1. **Decide**: pick the destination and the passengers to carry.
2. **Manifest**: the carry-over screen. The player confirms or adjusts.
3. **Depart**: the bundle is written (section 3.6), then the time-slip.
4. **Arrive**: the destination's native state takes over.

The manifest has a CARRIED column and a LEFT BEHIND column. Every left-behind
entry gives a reason, and the manifest cannot be skipped while it has entries.
Gilda shows carried and held amounts (section 4.3). The weapon row shows the old
and new form side by side, so the translation is legible before the player commits.

The time-slip reuses the Dark Cloud loading-bar style (target: under 10 seconds for
a same-era jump). If the destination cannot load, the jump rolls back: the weapon
returns unchanged and the fare is refunded.

### 3.6 Saves

- An Ixion save is a **bundle**: a folder holding a manifest plus each engine's
  state for that save. It is marked complete only when every part is written.
- **Ixion never writes to the native save slots.** The two original games keep
  their own saves and do not know about Ixion. Each engine writes its state into
  the bundle folder through its own save routine (verify that the routine accepts
  a path).
- **Partial bundle.** The manifest can be read but not loaded; the screen names the
  missing half. No silent fallback. A native continue never touches the bundle.

## 4. What crosses between worlds

### 4.1 Rules

1. **Four buckets for every field**, chosen before any formula:
   - **carry**: translated by a rule, possibly lossy;
   - **shadow**: opaque abroad, kept in the ledger, restored on return;
   - **local**: never leaves its world (floor flags, Atla and Geostone state,
     Georama layouts);
   - **cargo**: no analogue in the destination, held in the Cargo car.
2. **Hold, don't burn.** Nothing the player owns is destroyed by a crossing. A value
   the destination cannot hold goes to the ledger or cargo.
3. **Round trip.** Every shadow field survives origin, destination, origin. The
   ledger keeps the raw origin record, and a return restores from it, never from the
   destination's approximation. Growth earned abroad is written back at a stated
   rate (4.4).
4. **Destination gates are authoritative**, and **no free heal or revive**. Revival
   items remain the only revival. A crossing that would leave no living party
   member is refused at the station.
5. **Native progress stays home.** A guest visit never changes home-world progress.
   Floor clears and story flags do not cross. Items and gilda earned abroad do.

### 4.2 Roster

- The station keeps every character from either world with home world, role, HP
  ratio and status bits.
- **Phase-1 rule**: a cross-cast character who cannot yet render in the current
  engine is "on the train". They count for station requirements but are not
  selectable in battle. This answers "play any character" without content work.
- The role crosswalk (Max's gun and wrench, Monica's sword and armband, against
  Dark Cloud's melee and ranged roles) is a cast decision. The roster carries a
  `role` field so the crosswalk can change without touching crossing code.

### 4.3 Field rules

| Field | Rule | Status |
|---|---|---|
| HP | Carry the current/max ratio per character, clamped 0 to 1. Absolute values do not carry. Knocked out stays at 0. | proposal |
| Defence | Carry as a fraction of that world's cap for that character. | verify caps |
| Gilda | One canonical pool in the ledger (up to 999,999, the Dark Chronicle cap). Dark Cloud shows `min(canonical, 65,535)`; the excess is held and shown on the manifest as "held". | verify |
| Thirst | Dark Chronicle has a DRY status bit (`CHARA_STATUS_DRY`, 0x40) and no gauge. Dark Cloud has a water gauge with a per-character max, since items can raise it. To Dark Cloud: DRY below 0.10 fraction. To Dark Chronicle: fraction 0.05 if DRY, else the last ledger value. Gauge frozen abroad. Arrival floors the fraction at 0.10, so a crossing cannot kill on step one. | proposal |
| Ailments | Cleared on crossing, except knocked out. | proposal |
| Items | Canonical item key with per-world IDs as lookups. Mapped items carry; unmapped go to cargo. Quest, Atla and Geostone items stay local. Overflow goes to cargo, never the floor. | proposal |

Gilda caution: Dark Cloud's money field is 16-bit unsigned, but its union has a
signed view (`chronicle:` `userstatus.hpp`). Values above 32,767 may read negative,
so verify before fixing the 65,535 clamp. Neither halve-on-death nor the Dark
Chronicle jump's halving copies into crossing.

### 4.4 Weapons

Two mechanisms.

- **Loaner (default).** The origin weapon is parked in the ledger at full fidelity.
  The destination gets a loaner at translated base values, mapped to a native
  weapon of its own world, so no model crosses. Growth earned on the loaner (level,
  kills, synthesis points) is written back to the parked original at 60% on return.
  "Round-trip safe" here means the original is preserved and growth is written back
  at a stated rate.
- **Sphere (explicit, costly, one-way).** At the station the origin weapon becomes a
  Synth Sphere under its own game's rule. Both games keep about 60% of a weapon's
  stats through that step. The sphere crosses as a carry item and is spent under the
  destination's synthesis rules. It is permanent, so it is a visible player choice,
  never the default.

MVP class map (proposal, to be checked against both item tables):

| Max's melee (Dark Chronicle) | Carried as (Dark Cloud) | Note |
|---|---|---|
| Sword (Monica's kit) | Toan's sword line | Most literal match |
| Hammer | Nearest heavy Dark Cloud weapon | Heavy and slow in both |
| Wrench | Nearest blunt Dark Cloud weapon | Stand-in; may be dropped from the list |
| Fishing rod | Not carried | Not a fight weapon in Dark Cloud (`CHARA_EQUIP_MELEE` comment) |

Weapon rules:

- Level is carried. A level above the destination's cap is held in shadow, not
  inflated. Special effects are dropped except the damage type.
- Kills made on the far side add experience to the loaner, written back at 60%.
- A weapon not on the list cannot be carried. The station card shows the list.

**proposal, verify**: the far-side floor's first enemy has a shield only the carried
weapon's damage type can break, so the carried weapon becomes a key. Check the Dark
Cloud enemy tables first. If the shield does not exist as described, cut it.

### 4.5 Translation table

Every row is data, not code. A loader reads rows and applies a small set of
transforms, so balance changes never touch the crossing engine.

Row schema:

```
id          canonical key, e.g. "hp_ratio"
bucket      carry | shadow | local | cargo
from / to   world, struct, field (or ledger key)
transform   identity | ratio_of_cap | clamp | threshold | lookup | fold | sphere_60
bounds      min, max, destination cap
loss        none | rounding | lossy | verify
on_miss     shadow | cargo | default(value)
round_trip  restore_from_shadow | recompute
rule        rule id in this document
status      verified | canon | proposal | verify
```

Sample rows:

| id | bucket | Dark Cloud side | Dark Chronicle side | transform | on miss | status |
|---|---|---|---|---|---|---|
| hp_ratio | carry | hp / max_hp | gauge ratio | ratio_of_cap | n/a | proposal |
| thirst_out | carry | water / per-character max | DRY bit | threshold 0.10 | n/a | proposal |
| gilda | carry | money (u16 view) | money (cap 999,999) | clamp; hold excess | ledger | verify |
| w_elem | carry | element order (fire, ice, thunder, wind, holy) | attribute order (flame, chill, cyclone, lightning) | lookup | shadow | verify |
| w_monster | carry | ten monster families | four anti-monster attributes | fold (max) | shadow | verify |
| ridepod_parts | cargo | none | Ridepod parts | n/a | cargo | canon |

### 4.6 Crash safety and write order

1. Write the pending-crossing record to the sidecar, fsynced.
2. Write the origin's engine state into the bundle.
3. Unload the origin engine and load the destination.
4. Apply the manifest, then clear the pending flag.

A crash replays the pending record on the next start. A failed apply leaves the
crossing pending with a station notice, never a silent loss.

## 5. Mashup features, ranked

Ranking is wow per unit of engineering, cheapest and highest-wow first. It is a
judgement, not a measurement.

Wow runs 1 to 5. Tiers: **T0** data and UI only; **T1** a value, picture or file
crosses the process boundary; **T2** a self-contained sub-game module is ported into
the other engine; **T3** asset or format conversion (models, motion, scripts, maps);
**T4** runtime co-habitation (two worlds' actors in one live frame, battle or floor).

**No crossover needed** means the feature uses only its own world's content and
passenger-state numbers. **Needs content crossover** means it shows or runs another
world's models, pictures, scripts, floors or sub-game assets.

| # | Feature | Wow | Tier | Crossover | From |
|---|---|---|---|---|---|
| 1 | Carried weapon, class-mapped to a native Dark Cloud weapon (the spine) | 4 | T1 | no crossover needed | mvp-loop |
| 2 | Ixion hub: destination board, roster and manifest | 3 | T0 | no crossover needed | wacky-max, player-ux |
| 4 | Monica's monster form: Dark Cloud monster stats on a Dark Chronicle model | 4 | T0 | no crossover needed | wacky-max |
| 5 | Dark Genie fight in the Zelmite Mine epilogue, as a replay | 5 | T0 (T3 if the model is absent) | no crossover needed, verify model | wacky-max |
| 6 | Synth Sphere attachments read as Ridepod energy-pack parts | 3 | T0 | no crossover needed | wacky-max |
| 7 | Starglass time dial: Dark Chronicle era boards as stops | 3 | T1 | no crossover needed | mvp-loop |
| 8 | Spheda as a sub-game, rewards in Atla or ABS | 4 | T2 | needs content crossover | wacky-max |
| 9 | Finny Frenzy with Dark Cloud river fish | 3 | T2 + asset | needs content crossover | wacky-max |
| 10 | Gallery of Time: a station that replays Dark Cloud memory pictures | 3 | T0 + T1 | needs content crossover (pictures) | wacky-max, lore-first |
| 11 | Photo-to-invent: a Dark Cloud picture becomes a Dark Chronicle invention source | 4 | T2 + T1 | needs content crossover (picture) | wacky-max |
| 12 | Ghost Atla: Dark Cloud objects drift into Dark Chronicle towns as billboards | 3 | T1 + T3 | needs content crossover | wacky-max |
| 13 | Toan's lines in the Ridepod voice unit | 4 | T0 + asset | needs content crossover (voice files) | wacky-max |
| 14 | Monica transforms into a Dark Cloud monster with its own model | 5 | T3 | needs content crossover | wacky-max |
| 15 | Ixion Halt in Georama, with Atla houses beside Georama parts | 4 | T3 | needs content crossover | wacky-max, player-ux |
| 16 | Toan drives the Ridepod with his own model | 4 | T3 | needs content crossover | wacky-max |
| 17 | Dark Cloud floor as a Dark Chronicle battle backdrop | 3 | T3 | needs content crossover | wacky-max |
| 18 | Max's gun and Xiao's slingshot trade shots in one battle | 5 | T4 | needs content crossover | wacky-max |
| 19 | Monsters from both worlds on one floor | 5 | T4 | needs content crossover | wacky-max |

The playable slice is items 1 to 3 and 7. They need only T0 to T1 work, and nothing
in them requires two worlds to share a frame, a battle or a floor.

## 6. Roadmap

**Phase 0, first playable hop.** Two launches with a bundle. Luna Labs boarding, a
Norune Halt pre-placed by debug flag, one weapon, Divine Beast Cave floor 1, one
return trip. Plain loading screens. The gilda clamp is shown on the card. Kill test:
if playtesters do not care which weapon they bring after two trips, the
carried-object premise is wrong, and the next design carries something the player
already chooses between.

**Phase 1, passengers and a live hub.** Passengers and portraits (a Dark Chronicle
visitor speaks in Norune with a portrait only, no model). Gilda held and thirst
mapping live. The Lab car roster and manifest. The hub runs in a host scene and
hands state over in memory. The loaner-or-sphere station choice. The Cargo car.

**Phase 2, network and time.** Three or four stops per world, unlocked by the
progress each world already tracks (Palm Brinks, Veniccio, Norune, and Matataki as a
proposal). Floors from the other world, limited to floors already cleared in that
world. The Starglass time dial. Spheda, Finny Frenzy and the Gallery of Time as
sub-game ports. The Dark Genie replay if its model is verified. The Ixion Halt
earned through Georama.

**Phase 3, first content crossover (pictures).** Photo-to-invent, Gallery of Time
memory pictures, Ghost Atla billboards. Cheapest content crossover: pictures, not
models.

**Phase 4, model crossover.** Monica's monster models, Toan in the Ridepod, Atla
objects as Georama parts. The expensive part; it waits for evidence of demand.

**Phase 5, co-residency (optional).** Shared floors and co-op battles, only if
demand shows. The flow does not depend on it.

## 7. Code and canon references

- `chronicletwo:` `userdata.hpp` (`CHARA_STATUS_DRY`, `CHARA_EQUIP_MELEE`, money
  cap), `savedata.hpp` (`CSaveData` size), `monster.hpp` (`MOS_HENGE_PARAM`),
  `photo.cpp`, `sphida.cpp`, `gyorace.cpp`.
- `chronicle:` `ps2/include/dungeon.h` (`DUNGEON_GALLERY_OF_TIME`), `userstatus.hpp`
  (`WEAPON_HAVE chara_weapons[6][11]`, money field).
- 
## 8. Decisions taken in this draft

- Boarding is at the Luna Labs in Veniccio (canon), not Palm Brinks.
- Gilda over the destination cap is held in the ledger and shown as "held". One
  canonical pool, not per-world shares.
- Ixion never writes native saves. The bundle holds each engine's state.
- Round trip means "original preserved, growth written back at a stated rate".
- Loaner growth is written back at 60%.
- No revive on crossing. A crossing with no living member is refused.
- Thirst uses a per-character max.
- The fare is one Starglass (proposal), replacing an earlier 5% gilda fare.

## 9. Open design questions

1. Does Dark Chronicle's "three Atlamillia" govern the merged world, or Dark Cloud's
   count (Toan's stone plus Seda's)?
2. Who may unpack an Atla-packed passenger? Does Ixion need a station key (Luna
   Stone Shards are the candidate)?
3. Dark Cloud's era: its own line, or mapped onto a Dark Chronicle era?
4. What unlocks the Ixion Halt in Dark Cloud: a story beat, an item, or a Georama
   milestone?
5. The role crosswalk for Max, Monica and Dark Cloud's six.
6. Is the sphere a station-only choice or a field choice?
7. Does the floor-1 shield key exist in the Dark Cloud enemy tables? Keep or drop
   the wrench from the carry list?
8. The gilda signed view and the real clamp value (section 4.3).
9. Do Dark Chronicle time-of-day weapons keep their base value when loaned?
10. Does each engine's save routine accept a bundle path? Phase 0 depends on it.
11. Does the hub run in one of the two engines, or in a third scene?
12. Fare: Starglass or gilda, and where the Starglass is bought.
13. Thirst threshold and arrival floor (both 0.10): playtest values.
14. Is the Dark Genie model on the Dark Chronicle disc, and under what name? (The
    wiki links the epilogue's Genie to a "Fake Genie" page.)
15. The Dark Cloud monster-family crosswalk (ten families against four anti-monster
    attributes).
16. Is Terra inside the 10,000-year reach (the recommendation), or a separate
    stream? Canon never dates Terra. Party size defaults to each engine's own limit.

## Sources

- **mvp-loop** (spine): the one-hop loop, carried-weapon crux, class map, Starglass
  fare, Norune Halt placement, kill test, increment order.
- **lore-first**: Atla as passenger container and Terra reach (2.2, 2.3); Osmond as
  a lineage title (2.4); canon tags and post-canon branch (2.5).
- **systems-first**: four buckets, hold-don't-burn, round-trip shadow and ledger
  (4.1); loaner and sphere (4.4); translation schema (4.5); thirst mapping (4.3);
  crash-safe write order (4.6).
- **wacky-max**: tier framework and ranking (5); photo-to-invent, Spheda, Finny
  Frenzy, Gallery of Time, Ghost Atla, Monica monster row, Dark Genie replay.
- **player-ux**: canonical boarding, train cars, visited-only board, field-ready
  rule, manifest, bundle rules, phase 0.
