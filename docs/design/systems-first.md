# Ixion: Systems That Survive the Crossing

Scope: which state crosses between the two worlds, how it is translated, and what stays behind. Content crossover (models, motion, map formats) is out of scope except where it limits a rule.

Sources: the two decompiled codebases, cited by identifier (`chronicle:` for Dark Cloud, `chronicletwo:` for Dark Chronicle), and the fandom wiki. Wiki-only claims are marked (wiki). Anything not checked against code is marked (unverified).

## 1. Premise corrections

- Dark Chronicle has no water gauge, but it has thirst. The `CHARA_STATUS_DRY` bit (0x40) is a status ailment, applied by a weapon special (`WEAPON_SPECIAL_DRY`, 50% per hit) or a food-type item, and cured by a drink. While thirsty, eating is blocked except the Plum Rice Ball. Treat "DC2 thirst" as a status, not as "none".
- Dark Cloud's `WEAPON_HAVE::durability` is weapon hit points (WHP). Dark Chronicle's "Durable" is a stat that adds to WHP per level (wiki). Map by meaning, never by field name.
- Item IDs are not shared. Dark Cloud uses 0..377 (weapons 257..377). Dark Chronicle uses its own space (`ITEM_COMMON_DATA_MAX` 432). Table rows key on a canonical item key, and each world's numeric ID is a lookup.

## 2. Core model: a passenger manifest, not live sync

A crossing is a discrete transaction at a station. The host loads one engine at a time. (1) Seal: serialise the origin's passenger-relevant state into a canonical manifest. (2) Journal: write the manifest and a pending flag to a sidecar ledger (fsync), then write the origin's native save. (3) Unload the origin engine and load the destination. (4) Apply: translate the manifest into destination structures, then clear the pending flag.

Both engines already own their process and save record. Dark Chronicle's save is one fixed record (`CSaveData`, 0x65930 bytes) and the port asserts record sizes. Dark Cloud's party and dungeon state live in `CUserStatus` and `CDngStatusData`. Neither layout changes; everything new lives in the sidecar. The fiction fits: a crossing is a jump, so state is re-seated at the station, and a crossing counts as a save point in both directions.

### 2.1 Four buckets for every field

Each piece of state falls into exactly one bucket, chosen before any formula.

- Carry: translated by a rule into the destination, possibly lossy. Examples: HP ratio, gilda, attack.
- Shadow: opaque abroad, kept in the ledger, restored on return. Examples: Dark Cloud water-drain flags, speed, endurance.
- Local: never leaves its world. Examples: floor flags, Atla and Geostone state, Georama layouts.
- Cargo: no destination analogue, held in the station cargo box. Examples: Ridepod parts, monster-form items, unmapped items.

Hold, don't burn. Nothing the player owns is destroyed by a crossing. A value the destination cannot hold (gilda above a cap, an item with no analogue) goes to the ledger or cargo and comes back when it can be spent or returned.

### 2.2 Round-trip rule

Every Shadow field must survive origin, destination, origin unchanged. This is the most common porting bug and the cheapest to prevent. The ledger keeps the raw origin record for each passenger and weapon, and a return trip restores from those stored values, never from the destination's approximation.

## 3. Party and character switching

Current cast shape (verified in code):

- Dark Cloud: six party slots (Toan, Xiao, Goro, Ruby, Ungaga, Osmond), each with its own HP, defence, water and 11 weapon slots. Floors can restrict fighting to one character (`ResLimitZone` 0..5, plus no-weapon-change and thirst zones).
- Dark Chronicle: two active humans (Max, Monica), the Ridepod (`ROBO_DATA`), and Monica's monster form. The Ridepod and monster forms can only be selected in a dungeon (`USER_DATA_ENV_DUNGEON`). Floors can bar Max or Monica (`CHARA_CHANGE_REASON_FLOOR_LIMITED`).

Rule 3.1: the destination's floor gate is authoritative. Both games already have a per-floor "who may fight" gate, so the arriving world decides who can be fielded, and a roster cannot override it.

Rule 3.2: a passenger roster, not a party. The station keeps every character from either world with home world, native role, HP ratio and status bits. The active party in any world is drawn from the roster, subject to that world's slot count and gate.

Rule 3.3: phase the cast. The first build runs each engine with its own cast. A cross-cast character who cannot yet render in the other engine is "on the train": in the roster, counted for station requirements, not selectable in battle. This is an honest phase-1 version of "play any character" and needs no content work.

Rule 3.4: a crossing never leaves zero living characters. If a manifest would, the lowest-HP passenger is revived at 10% and the ledger logs it.

Open question: the role crosswalk (Max with gun and wrench, Monica with sword and armband, against Dark Cloud's melee and ranged roles). This is a cast decision. The roster carries a `role` field so the crosswalk can change without touching crossing code.

## 4. HP, defence, status, thirst

### 4.1 HP

Dark Cloud keeps `hp[]` and `max_hp[]` (s16), and `AILMENT_KNOCKED_OUT` (0x02) counts as zero HP. Dark Chronicle keeps a `COMMON_GAGE` per character plus the Ridepod energy gauge.

Rule: carry the HP ratio (current / max), clamped to 0..1. Absolute values do not carry, because max HP differs by world and growth path. A character at ratio 0 stays knocked out. Revival comes from revival items, which both worlds have (Dark Cloud's Revival Powder, Dark Chronicle's Resurrection Powder, 0x111). The station does not revive, because a free revive makes crossing a free heal. Knob: a heal floor of 25% of max for anyone below it on arrival (a starting guess).

### 4.2 Defence

Dark Cloud keeps `defense[]` (s32), raised by favourite food up to 99. Dark Chronicle keeps `defence` (u16) per character, raised by equipment.

Rule: carry defence as a fraction of that world's own cap for that character. Calibrate caps from the data tables before fixing numbers (unverified). Raw numbers never copy across worlds.

### 4.3 Thirst

Dark Cloud (`CUserStatus::Step`): `water_max` is fixed at 30 (three drops of 10). `water_now` drains each step at `0.003 * (1 + 0.2 * georama)`. The thirst zone multiplies that by 5, and weapon flags 0x8 and 0x10 multiply it by 0.8 and 2. An empty gauge costs 1 HP every 120 steps. The dry warning fires below 10% (`SetStatus_Dry`).

Dark Chronicle has a status bit: no gauge, no drain. The canonical value is `thirst` in 0..1, where 1 is a full Dark Cloud gauge.

- DC1 to DC2: DRY is set if `thirst < 0.10`, else cleared. The gauge itself is held in the ledger.
- DC2 to DC1: if DRY, `thirst = 0.05`. Otherwise the last ledger value stands.
- While abroad, the non-native gauge is frozen: no drain, no HP loss.
- On arrival in Dark Cloud, thirst is clamped to at least 0.10, so a crossing cannot kill on step one.

Drink items in both games map to one canonical "drink" action that raises `thirst` by an item-specific amount. Dark Chronicle keeps its rules intact and sees Dark Cloud thirst only through its DRY bit.

## 5. Weapon growth

The hardest translation and the most design-heavy.

### 5.1 What each game grows

Dark Cloud (`WEAPON_HAVE`) levels to 99 on ABS (`experience`), with attack, endurance, speed, magic, WHP, five elements (fire, ice, thunder, wind, holy), ten monster families (`vs_monster`), six attachment slots, `synthesis_count`, and flags. ABS requirements grow per level (wiki). Status Break at +5 seals a weapon into a Synth Sphere that keeps 60% of base stats, its attachments and its abilities (wiki).

Dark Chronicle (`CDataWeapon`) has `levelup_exp`, WHP, two status values (Attack, Durable), eight attributes (four elements: Flame, Chill, Cyclone, Lightning; four anti-monster: Excorcism, Smash, Beast, Scale; wiki), `special` bits, `fusion_point` gained per level, and build-up requirements. Spectrumising makes a Synth Sphere. A level 5 or higher weapon keeps its parameters (`SPECTOL_TYPE_WEAPON`); below level 5 it gives one random parameter (`SPECTOL_TYPE_WEAPON_LOW`). A sphere keeps about 60% of total stats, with attack on a formula (wiki).

Both games retain 60% when a weapon becomes a sphere, so the sphere is the natural conversion medium.

### 5.2 Two mechanisms

Mechanism A, Sphere (one-way, permanent). The origin weapon becomes a Synth Sphere at the station by the origin's own rule. It crosses as a Carry item at 60% retention and is spent in the destination under its synthesis rules.

Mechanism B, Loaner (round-trip safe). The origin weapon is parked in the ledger at full fidelity, with its Shadow fields. The destination receives a loaner at translated base values with no growth. Growth earned on the loaner (level, ABS, synthesis points) is written back to the parked original at 60% on return.

Recommendation for the proof of concept: Loaner for everyday play. Sphere only as an explicit, visibly costly player choice at the station, because it is permanent.

### 5.3 Field translation (weapons)

| Canonical | Dark Cloud | Dark Chronicle | Rule | Loss |
|---|---|---|---|---|
| attack | `attack` | `status[0]` | 1:1, clamp to destination cap | none in range |
| WHP | `durability` | WHP | Separate field; never map Durable onto it | n/a |
| durable | none | `status[1]` | Shadow on DC1 side | n/a |
| elements | `elem[0..3]` (fire, ice, thunder, wind) | `attribute[0..3]` (flame, chill, cyclone, lightning) | Pair by meaning; verify order | verify |
| holy | `elem[4]` | Excorcism | Verify; likely anti-monster | verify |
| monster families | `vs_monster[10]` | Beast, Excorcism, Smash, Scale | Max over the family set; unmatched families are Shadow | lossy |
| magic | `magic` | none | Fold into elemental multiplier; Shadow on return | lossy |
| speed, endurance | `speed`, `endurance` | none | Shadow | n/a |
| synthesis | `synthesis_count` | `fusion_point` | 1:1; Dark Chronicle caps at 999 | none |
| level | `level` (to 99) | level (wiki, to 99) | Carry; above destination cap held in Shadow | none in range |
| ABS progress | `experience` | levelup progress | Carry as fraction of next level | rounding |
| flags 0x8, 0x10 | drain modifier | none | Shadow; no effect abroad | n/a |
| special bits | attachment and ability data | `special` | Carry where an analogue exists, else Shadow | verify |

The monster-family mapping is the largest unverified piece. Dark Cloud's ten families (Dino, Undead, Sea, Stone, Plant, Beast, Sky, Metal, Mimic, Mage) and Dark Chronicle's four anti-monster attributes do not map one to one.

## 6. Items and Gilda

### 6.1 Gilda

Dark Cloud stores money in a u16 (`CUserStatus::money`) and halves it on death (`CDngStatusData::SetDead`). Dark Chronicle stores an int capped at 999999 and halves it to pay for a floor jump (`jump_pay`).

Rule: the ledger holds canonical gilda (integer, up to 999999). The Dark Cloud view shows `min(canonical, u16 cap)`, and the excess is held, not lost. The crossing fare is a knob, proposed at 5% rounded down (a starting guess). Do not copy halve-on-death into crossing, because it compounds with the fare.

### 6.2 Items

Canonical item key: a stable string (`revival_powder`, `drink_water`, `repair_powder_melee`) assigned once, with per-world IDs as lookups. Unmapped items go to cargo.

- Cargo is shown at the station and can be claimed on any return trip.
- Dark Chronicle Ridepod parts and monster-form items are Cargo, because they have no Dark Cloud analogue.
- Quest items (Atla, Geostone, dungeon keys) are Local and never cross.
- Pack capacity differs: the Dark Cloud dungeon pack holds 103 slots plus three quick-use slots, and the Dark Chronicle item board has a main board and overflow places. An overflowing crossing puts the excess in cargo, never on the floor.

## 7. Georama in each world

Dark Cloud: Atla are per-floor spheres that only Toan can open (wiki). An opened Atla yields a piece of the town (buildings, people, objects, roads). Progress is per town, complete at 100%. The save keeps an Atla grid and a registry per dungeon (`ATRA_SAVE`).

Dark Chronicle: one Geostone per floor (wiki) unlocks Georama part blueprints. Parts need crafting materials and consume Polyn, a per-area budget. Culture Points measure progress. The save keeps layouts per area, and floor flags carry Geostone found and read.

Rule 7.1: Georama progress is Local. A town belongs to its world's engine and layout.

Rule 7.2: a visit does not change the other world's Georama. Visiting a Dark Cloud town from Dark Chronicle shows its native state, read-only unless the player is in its home world.

Rule 7.3: a shared unlock, not shared state. Completing a town in one world grants a station-level reward in both, such as a cargo box slot or a blueprint buildable from the destination's own materials. This is the only Georama link in phase 1. Importing Atla objects as Dark Chronicle parts is content work for a later phase.

Rule 7.4: Polyn and Culture Points never cross. They are per-area budgets with no meaning elsewhere.

## 8. Dungeon progress

Dark Cloud keeps per-floor arrays (`kills[6][100]`, `res_limit_zone_id`, `floor_reached[7]`, `atra_registry`). Dark Chronicle keeps seven dungeons and 162 floor records with flags (open, clear, practice clear, fast destroy, fishing, talk monster, Spheda clear, Geostone found and read, seal clear). Both are per-world.

Rule 8.1: a guest visit never changes home-world progress. A guest visit runs a dungeon from the other world against the ledger's guest record for that floor. This blocks sequence breaks, such as clearing a floor in the wrong world to open a story gate.

Rule 8.2: items and gilda found on a guest run are real (Carry), because they belong to the player. Story flags and floor clears are not carried.

Rule 8.3: a guest run does not award the Georama unlock. The unlock is the home-world floor's first clear.

Rule 8.4: a floor's restriction applies as written. If a Dark Cloud floor allows only Toan, a roster without a valid party is refused at the gate, not at the floor.

## 9. Time of day

Dark Chronicle's clock has gameplay effects: `GetStatusParam(time)` shifts some weapon attack by time of day (Monica's Lamb's Sword, per its item comment), and fish fatigue steps on the save clock. I found no time-of-day gameplay hook in the Dark Cloud play sources; the matches there are editor and save-menu code.

Rule: the Dark Chronicle clock is the station clock and drives time-of-day effects when that engine is loaded. Dark Cloud ignores it. A loaned time-of-day weapon keeps its stored base value abroad (unverified; needs a code check).

## 10. Save and crash safety

- Each world keeps its native save, unchanged in format.
- The sidecar holds the roster, the ledger (Shadow, Local guest records, cargo, parked weapons) and a pending-crossing record.
- Order: pending record, origin save, load destination, apply manifest, clear pending. A crash between steps replays the pending record on next start.
- A failed apply is never a silent loss. The manifest stays pending and the player sees a station notice.
- Ixion never deletes a save or sidecar entry it did not create in the current session.

## 11. Translation table structure

Every row is data, not code. A loader reads rows and applies a small set of transforms, so balance changes never touch the crossing engine.

Schema, one row per canonical field and direction:

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
status      verified | wiki | unverified
```

Sample rows:

| id | bucket | DC1 side | DC2 side | transform | on miss | status |
|---|---|---|---|---|---|---|
| hp_ratio | carry | hp / max_hp | COMMON_GAGE ratio | ratio_of_cap | n/a | verified |
| thirst_out | carry | water_now / 30 | DRY bit | threshold 0.10 | n/a | verified |
| thirst_in | carry | DRY bit | water_now = 0.05 x 30 | lookup | n/a | verified |
| gilda | carry | money (u16) | money (int, cap 999999) | clamp, hold excess | ledger | verified |
| defence | carry | defense (s32, cap 99) | defence (u16) | ratio_of_cap | default | unverified |
| w_attack | carry | attack | status[0] | clamp | shadow | verified |
| w_whp | carry | durability | WHP | identity | n/a | verified |
| w_fire | carry | elem[0] | attribute[0] (flame) | identity | shadow | verify |
| w_monster | carry | vs_monster[i] | anti-monster | fold (max) | shadow | unverified |
| w_synth | carry | synthesis_count | fusion_point (cap 999) | identity | ledger | verified |
| w_drain_flags | shadow | flags 0x8, 0x10 | none | identity | n/a | verified |
| ridepod_parts | cargo | none | ROBO parts | n/a | cargo | verified |
| atla_state | local | atra_registry | n/a | n/a | n/a | verified |

## 12. Balance: starting knobs

All numbers are starting guesses for tuning after playtests, not facts about either game.

- Crossing fare: 5% of gilda, a cost that does not punish a poor party.
- HP heal floor: 25% of max, so crossing is not a full heal.
- Thirst floor on arrival: 0.10, so no death on the first step.
- Sphere retention: 60%, matching both games.
- Loaner growth write-back: 60%, so a round trip is neither free nor punitive.
- Revival on crossing: none. Revival items remain the only revival.
- Guest floor rewards: items and gilda only, which keeps story gates in order.

Rule of thumb: a crossing should cost at most the fare plus one sphere's worth of growth. Anything more is a player choice made at the station.

## 13. Phases

- Phase 1 (proof of concept): both engines native. Passenger manifest, four buckets, round-trip shadow, gilda, HP ratio, thirst bit mapping, loaner weapons, guest records, cargo box. Cross-cast characters are on the train only.
- Phase 2: sphere conversion as a player choice; shared Georama unlocks at station level; a proxy cast if the team accepts it (a character from one world rendered with the other world's stats, labelled as such).
- Phase 3: Atla and Geostone content conversion, cross-cast rendering, and a verified monster-family crosswalk checked against both engines.

## 14. Open questions for the research wave

1. Verify the Dark Cloud element order and the holy and anti-monster mapping in the weapon code.
2. Verify the ten Dark Cloud monster families against the Dark Chronicle anti-monster set, including Smash and Scale.
3. Confirm the Dark Cloud gilda cap in the write path. The field is u16, but the clamp is unconfirmed.
4. Confirm how Dark Chronicle time-of-day weapons behave when loaned.
5. Confirm growth paths for each character in both games. Not checked here.
6. Decide the role crosswalk for Max, Monica and the Dark Cloud six.
7. Decide whether a sphere is a station-only choice or a field choice.
