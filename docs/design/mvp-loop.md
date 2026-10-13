# Ixion MVP Loop: one hop, one carried weapon

Angle: the smallest crossover that is fun and proves the concept. One station per
world, one crossing, one carried thing that changes what happens on the other side.
Everything after that is a playable step up, not a bigger plan.

Scope rules for this doc:

- Each world keeps its own engine. The hop is a state handoff, not a shared runtime.
- No model, motion, or format conversion in the MVP. Characters appear as the
  engine already has them.
- Facts about either game are cited to the decomp or the fan wiki. Design
  proposals are marked as proposals.

## 1. The pitch in one paragraph

You are Max, standing in Palm Brinks with a train ticket that does not exist yet.
You board the Blackstone Railroad, step off in a Dark Cloud town that is still
half-ruined, and play Toan for ten minutes with Max's melee weapon in his hand. You clear
one floor, win one thing back, and ride home. The weapon is the proof: it is the
one object that crossed, it fights differently in Toan's hands, and it comes back
changed. The player learns the whole concept from a single weapon.

## 2. Why this shape

- A single carried object makes the crossing legible. The player knows exactly what
  came through the seam and can check it on the way back.
- Money and HP are the obvious carries but they are invisible. A weapon is seen
  every time the player attacks, so the crossing is felt on every hit.
- The loop needs no new art. Palm Brinks and Norune Village already exist in their
  own games. The only new content is one platform per side and a short handoff
  scene.
- It forces the hardest design question early (what a weapon means across two
  combat systems) on a single item, where a bad answer is cheap to see and fix.

## 3. The two stations

**World A, Dark Chronicle (ChronicleTwo engine): Palm Brinks, Blackstone Railroad
station.** Palm Brinks is the town Max lives in. The Blackstone Railroad is the
town's train line, and the Palm Brinks wiki places the station on a plaza
with a coffee shop and a bar. The MVP adds a
conductor NPC and an Ixion boarding trigger on that plaza. The Ixion itself is
the time-travel train from Luna Labs in Veniccio; the station only needs a
departure point. The fare is one Starglass, the item Max and Monica buy at
Starlight Temple and use at the Moon Crystal Lighthouse.

**World B, Dark Cloud (Chronicle engine): Norune Village.** Toan's home village,
destroyed by the Dark Genie at the start of the game, with a Georama that is
rebuilt by collecting Atla (Norune Village and Georama wiki pages). The MVP adds one
Georama-style structure, a siding (proposal), placed in the village at the start
of the MVP. It is pre-placed for the MVP. Later it is earned through the Georama
system, which the DC1 engine already runs.

The dungeon for the MVP is the first floor of the Divine Beast Cave, the dungeon
attached to Norune Village in the wiki. It is only used as a floor the player
clears once. It is not a full dungeon visit.

## 4. The minute-to-minute loop (about 12 minutes)

| Time | Where | Player does | Player sees |
|---|---|---|---|
| 0:00 | Palm Brinks plaza | Walks to the station; Max is in the middle of his normal day | Ordinary town life, a conductor waving |
| 0:45 | Station | Chooses the carried weapon from a short list: Max's melee weapon only | A card showing the weapon, its level, and what it becomes (see section 6) |
| 1:15 | Station | Pays one Starglass, boards | A short train cutscene; the screen whites out |
| 1:30 | Seam | Nothing; the handoff is about 5 seconds | A sound cue and a title card: "Norune Village" |
| 1:40 | Norune siding | Toan steps off; the weapon appears in his hand as a second weapon slot | The weapon looks like Max's, now in a different hero's hands |
| 2:30 | Norune village | Talks to Renee and one resident who asks about the train | Dialogue with the traveller's name, using portraits only |
| 4:00 | Divine Beast Cave, floor 1 | Fights the floor with Toan | The carried weapon is the only one that can break the floor's shielded enemy (see section 6) |
| 8:00 | Floor 1 chest | Opens the chest; finds one Dark Cloud item (Fluffy Donut type, a known item) | Clear reward; the floor's boss is skipped in the MVP |
| 9:00 | Norune siding | Boards the return train | The weapon's level goes up by the kills it made |
| 10:00 | Seam | Handoff back | Max's title card |
| 10:30 | Palm Brinks | Steps off with the weapon, its new level, and the Dark Cloud item in the pack | The player feels the trip in the inventory screen |
| 11:00 | Palm Brinks | Free play resumes | The loop is over; the reason to do it again is the weapon |

The player controls the hero of the world they are in at every moment. The
passenger is the kit (weapon, money, HP share), not the body.

## 5. The handoff (what the player should experience, not how it is built)

- The handoff is a single record written on departure and read on arrival. Its
  fields are in section 7.
- The player must see the record change. On the station card, the weapon shows its
  old form and new form side by side. On arrival, the weapon slot shows a new
  name suffix, for example "(Ixion)", until the player goes home. The suffix is a
  placeholder; the name is for playtest to decide.
- A failed handoff must not lose the weapon. The MVP's rule: if the far side cannot
  load, the weapon returns to Max's pack on Palm Brinks, unchanged, and the
  Starglass is refunded.

## 6. The carried weapon: the design crux

The weapon is the only carried thing in the MVP, so its translation decides whether
the concept works.

What the two codebases say about weapons:

- Dark Chronicle (ChronicleTwo, `ps2/include/userdata.hpp`): a character has five
  equip slots, `CHARA_EQUIP_MELEE` being the first. Its comment lists Max's melee
  as "wrench, hammer or fishing rod", and Monica's as "sword". The equip slot is a
  `CGameDataUsed`.
- Dark Cloud (Chronicle, `ps2/include/userstatus.hpp`): each of six party members
  has a `WEAPON_HAVE chara_weapons[6][11]` table, and `equipped_weapon_slot[6]`
  picks the one in use. Weapons are per character, not per slot.

Those two systems do not share a weapon list, so translation is by class, not by
item. Proposed MVP mapping (to be checked against both item tables before
implementation):

| Max (Dark Chronicle) melee class | Carried into Dark Cloud as | Why |
|---|---|---|
| Sword (Monica's kit, increment 2) | Toan's sword line | Same weapon shape; the most literal match |
| Hammer | Hammer-class DC1 weapon, nearest by damage type | Heavy and slow in both |
| Wrench | Nearest blunt DC1 weapon | No direct equivalent; a stand-in |
| Fishing rod | Not carried in the MVP | Not a fight weapon in DC1 |

Rules for the carried weapon:

1. Its level is carried, clamped to the DC1 weapon's maximum level (proposal:
   clamp, never inflate).
2. Its special effects are dropped on the far side except one, the damage
   type. The damage type is what makes it matter on the floor (see section 4,
   floor 1).
3. On the far side, the weapon gains experience from kills it makes. The gain is
   written back on the return trip.
4. A weapon that is not in the list cannot be carried. The list is shown on the
   station card, so the rule is visible.

What makes the weapon matter on floor 1 (proposal): the floor's first enemy has a
shield that Toan's own weapon cannot break. The carried weapon can, once. This turns
the carried item into a key. The shield lookup must be checked against the DC1
enemy tables before the floor is built.

## 7. Passenger state for the MVP

Only these fields cross. Everything else stays in its home game.

| Field | Source (ChronicleTwo, `userdata.hpp`) | Target (Chronicle, `userstatus.hpp`) | Rule |
|---|---|---|---|
| Kit owner | which of Max or Monica is in front | a label only | Shown in the card; no body conversion |
| Melee weapon | `CHARA_DATA::equip[CHARA_EQUIP_MELEE]` | `chara_weapons[x][y]` | Class mapping, section 6 |
| Gilda | `CUserDataManager` money, int, 0 to 999,999 | `money`, u16, max 65,535 | Clamp to 65,535; the excess stays home |
| HP | `CHARA_DATA::hp` | `hp[]` for Toan | Carry the fraction, not the number |
| Thirst | `CHARA_STATUS_DRY` bit | `water_now` | Reset to full on arrival |
| Status ailments | `status_attr` | `ailments[]` | Cleared on crossing |
| Starglass | the item | removed | Consumed as the fare |

Two notes:

- The money clamp is the first real mismatch found in the code. The DC2 field
  holds up to 999,999; the DC1 field is a 16-bit unsigned value. A player with
  200,000 gilda should not lose it silently; the card says how much stayed home.
- HP as a fraction avoids the need to scale the two games' numbers. It is the
  cheapest honest rule.

## 8. Increment 1: the MVP (what is built first)

- One station on each side, one carried weapon, one floor, one out-and-back trip.
- The siding in Norune is pre-placed by a debug flag.
- The handoff is a single file written on departure, read on arrival, with a
  refund-on-failure path.
- Playtest question: after the trip, does the player want to bring a different
  weapon next time? If not, the carried thing is not doing its job.

## 9. Increment 2: passengers and a second weapon

- The player picks which of Max's or Monica's kit to carry: one weapon plus one
  item (an accessory, a food item, or any other item the player owns, chosen
  from the pack).
- Dialogue crosses with portraits. A Dark Chronicle character speaks in Norune
  as a named visitor, shown with a portrait only, no model. This is the cheapest
  content crossover and the first one the player can see.
- The return trip carries Toan's kit back. The Norune resident who asked about
  the train gets a reply that refers to the trip.

## 10. Increment 3: a station network

- Ixion has three to four stops per world, unlocked by the progress each world
  already tracks: Palm Brinks, Veniccio (Luna Labs), Norune Village, and
  Matataki Village (proposal).
- The station card gains a destination list. Each destination has a fare
  (Starglass) and a passenger list.
- A dungeon visit from the other world is possible but limited to one
  already-cleared floor, so the player does not have to re-learn a dungeon.

## 11. Increment 4: Georama and the time dial

- The siding in Norune is earned through Georama, using the DC1 Atla mechanic
  that already exists, not pre-placed.
- Dark Chronicle's time travel becomes a choice: the Starglass sends the player
  to a different era of the same town. Palm Brinks in the past and Palm Brinks
  in the future are both stops (proposal; the wiki places the time-travel gate at
  the Moon Crystal Lighthouse).
- The Georama progress of one world affects the other: a resident restored in
  Norune appears as a visitor in Palm Brinks. This is the first loop where
  progress in one game changes the other.

## 12. Increment 5: deferred

- Model crossover (Max rendered in the DC1 engine, or Toan in the DC2 engine).
  This is the expensive part. It needs model, motion, and format conversion, and
  it should wait until the MVP has shown the player wants it.
- A shared save file. Each engine keeps its own save. The passenger record is the
  only shared data.

## 13. What to test, in order

1. The weapon's translation. Give a playtester the trip, do not explain the
   mapping, and ask them to describe the weapon after the trip.
2. The clamp. Give a playtester 200,000 gilda and watch whether the card makes
   the loss clear.
3. The floor. Does the shield key feel like a reason to bring the weapon, or a
   tax? A tax means the mapping is wrong or the shield is too strong.
4. The return. Does the level gain feel earned on the way back?

Kill criteria: if playtesters do not care which weapon they bring after two
trips, the carried-thing idea is wrong and the next design should carry something
the player is already choosing between (a consumable, a passenger, a resident).

## 14. Open questions

- Whether the Ixion is visible on the Norune siding or only a sound and a title
  card. The MVP assumes sound and title card.
- Whether Max's wrench has any DC1 equivalent, or whether the MVP should only
  carry hammer-class weapons only and drop the wrench from the list.
- Whether the DC1 floor-1 shield enemy exists as described. This must be checked
  against the DC1 monster table before section 6's key rule is kept.
- The fare. One Starglass per crossing may be too cheap or too rare. Playtest
  decides.
