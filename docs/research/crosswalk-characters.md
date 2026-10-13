# Crosswalk: the two casts

## What this covers

The playable party of each game, side by side: Dark Cloud's six (Toan, Xiao, Goro, Ruby, Ungaga, Osmond) and Dark Chronicle's two humans (Max, Monica) with their two attached forms (the Ridepod for Max, the monster form for Monica). For each character it gives the weapon classes and counts, the combat specials, starting and growth stats (HP, defence, thirst or the DRY status), and the dungeon field abilities. It then proposes a crosswalk (which weapon class maps to which, and how stats convert) and lists the minimum per-character record Ixion needs.

Sources: Chronicle (DC1) `ps2/src` and `ps2/include`; ChronicleTwo (DC2) `ps2/src`, `ps2/include` and the Ixion design draft; the PAL extracted data tables for both games (counts and item ids only, nothing reproduced); and the community wiki pages in `docs/fandom`. `refs/DarkCloud-MechanicsGuide` has no character data: its weapons route is a placeholder (`refs/DarkCloud-MechanicsGuide/src/routes/weapons/+page.svelte`). Nothing was built or run. Labels: **verified** means read in code or data; **inference** is one reasoning step; **proposal** is an Ixion design choice; **verify** needs a check before anything depends on it.

## Key facts

### Roster and identity

- DC1 enum `Character`: TOAN=0, XIAO=1, GORO=2, RUBY=3, UNGAGA=4, OSMOND=5. chronicle:ps2/include/itemdata.hpp:485-492 (verified)
- DC2 enum `USER_CHARA`: MAX=0, MONICA=1, ROBO=2 (the Ridepod), MONSTER=3 (Monica's transformation). Only the two humans have a `CHARA_DATA` record (`chara_data[2]`). chronicletwo:ps2/include/userdata.hpp:20-26, 241-258 (verified)
- DC1 starting values are per-slot arrays in `CDngStatusData::Initialize`: `start_hp = {70, 60, 100, 90, 110, 100}`, `start_stat = {3, 1, 12, 23, 38, 46}`, water max 30 for everyone. Only Toan's dagger is granted there (`GetItem(ITEM_WEAPON_DAGGER, 0)`). chronicle:ps2/src/dngstatusdata.cpp:892-893, 915, 921 (verified)
- DC2 starting values: HP capacity `lifetbl = {32, 48}` (Max, Monica), defence 4 (Max) and 8 (Monica). chronicletwo:ps2/src/userdata.cpp:2764-2804 (verified)
- DC2 default kit (`GetCharaDefaultWeapon`): Max = item 0x1 (Battle Wrench, melee), 0x16 (= 22, first gun), hat 0x6F, shoes 0x75, clothes 0x102 or 0x104 by language group. Monica = 0x29 (= 41, first sword), 0x5B (= 91, first armband), hat 0x7B, boots 0x81, clothes 0x107. chronicletwo:ps2/src/userdata.cpp:4730-4744 (verified)
- DC2 equipment slots: MELEE = Max's wrench, hammer or fishing rod, or Monica's sword; SUB = Max's gun, or Monica's armband. chronicletwo:ps2/include/userdata.hpp:228-236 (verified)
- The DC2 wiki matches: Max carries a gun and a wrench (or hammers), Monica a sword and an armband that makes elemental magic. docs/fandom/Dark_Chronicle.wiki:63 (verified)

### Weapons: Dark Cloud

- Each DC1 weapon is a `WEAPON_DATA` row with durability (WHP), attack, endurance, speed, magic, owner, five element values (fire, ice, thunder, wind, holy), ten monster-family values, and a special-flag word. chronicle:ps2/include/itemdata.hpp:656-684 (verified)
- The 120-row `WeaponList` is a C table, one row per weapon, with the owner as `CHARA_*`. chronicle:ps2/src/itemdata.cpp:1428-1549 (verified)
- Owner is also decided by item-id range in `CDngStatusData::CheckWeaponUser`. Ranges, with counts from the table: Toan 257-298 (42), Xiao 299-313 (15), Goro 314-330 (17), Ruby 331-346 (16), Ungaga 347-362 (16), Osmond 363-376 (14). chronicle:ps2/src/dngstatusdata.cpp:264-290; itemdata.hpp:346-377 (verified)
- Weapon classes (wiki): melee blades, hammers and staves; ranged magic rings, guns and slingshots. docs/fandom/Dark_Cloud.wiki:31 (verified). Toan's pages say daggers and swords (docs/fandom/Toan.wiki, Gameplay section).
- Per-owner ranges over the table (includes placeholder and broken rows, so minimums are low):

| Owner | Weapons | Attack range | WHP range | Endurance range | Speed range | Magic range |
|---|---|---|---|---|---|---|
| Toan | 42 | 1-199 | 30-99 | 0-99 | 50-89 | 0-110 |
| Xiao | 15 | 1-150 | 40-70 | 0-70 | 40-80 | 0-99 |
| Goro | 17 | 1-199 | 5-88 | 0-60 | 5-65 | 0-128 |
| Ruby | 16 | 1-99 | 5-89 | 5-70 | 5-88 | 1-210 |
| Ungaga | 16 | 1-212 | 5-87 | 0-70 | 5-99 | 0-50 |
| Osmond | 14 | 1-128 | 0-84 | 0-98 | 40-88 | 0-55 |

(verified by parsing the table; the same rows are what the code reads)

- Ruby's rings are element-typed; Osmond's guns and Ruby's shots both use `(attack >> 1) + (magic >> 1)` as damage. chronicle:ps2/src/dun/gameloop.cpp:7833-7838 (Ruby), 8115-8118 (Osmond) (verified)
- Attachment and weapon element order: fire, ice, thunder, wind, holy. Monster families are ten slots in slayer-id order (dino, undead, sea, stone, plant, beast, sky, metal, mimic, mage). chronicle:ps2/include/itemdata.hpp:218-229, 656-684 (verified for element order; family order is inference from the slayer ids 111-120)
- Speed sets the action-gauge refill: gain = speed / 30 per tick, minimum 1. chronicle:ps2/src/dun/gameloop.cpp:6088-6104 (verified)

### Weapons: Dark Chronicle

- The weapon catalogue is text, read by the game from `menu/cfg7/` (not cfg5 or cfg6). chronicletwo:ps2/src/gamedata.cpp:1159-1160 (verified). The extracted PAL tree has three language folders with different `WEP_SPE` arities (5, 6 and 7 fields), so the folder matters. Counts below are from cfg7.
- Record shapes: `WEP` = durability, level-up experience; `WEP_ST` = attack, durability; `WEP_ST2` = eight attribute values; `WEP_SPE` = initial fusion, pallet, unused, fusion points, special bits, attack type, model number. chronicletwo:ps2/src/gamedata.cpp:756-761, 838-859 (verified)
- Attribute order: index 0 is Flame and index 4 is Smash (the Battle Wrench's data has flame 2 at index 0 and smash 5 at index 4; the wiki's Battle Wrench page agrees). The wiki's full order is flame, chill, lightning, cyclone, smash, exorcism, beast, scale. docs/fandom/Battle_Wrench.wiki (verified against data); docs/fandom/Weapon_attributes.wiki, Dark Chronicle section (wiki). Whether index 3 (cyclone) counts as an element for the "highest of the first four" rule is verify.
- Category counts, joined from the item catalogue (`COM` type 1 to 4) and weapon rows:

| DC2 type | Owner | Count | Item ids | Attack | Durability (WHP) | Fusion points |
|---|---|---|---|---|---|---|
| 1 `ITEM_DATA_MAX_MELEE` | Max | 25 (incl. 2 fishing rods, 1 duplicate-name variant) | 1-21, 90, 302, 303, 387 | 1-150 | 16-100 | 3-6 |
| 2 `ITEM_DATA_MAX_GUN` | Max | 19 | 22-40 | 7-150 | 32-100 | 3-6 |
| 3 `ITEM_DATA_MONICA_MELEE` | Monica | 49 (swords) | 41-89 except 53, and 110 | 15-150 | 36-100 | 3-6 |
| 4 `ITEM_DATA_MONICA_MAGIC` | Monica | 19 (armbands) | 91-109 | 14-150 | 42-100 | 3-6 |

  chronicletwo:ps2/include/gamedata.hpp:139-143 (type enum); chronicletwo:ps2/src/gamedata.cpp:1572-1580 (types 1 to 4 are weapons); menu/cfg7/comdat.cfg and wepdat.cfg (verified by parsing)
- Gun attack types (`WEAPON_ATTACK_*`) inside Max's gun class: ordinary (0) = ids 22-27 (6); launcher (10) = 28, 29, 30, 39 (4); laser (20) = 31-34 (4); machine gun (30) = 35-38, 40 (5). chronicletwo:ps2/include/gamedata.hpp:684-693 (enum); data from cfg7 `WEP_SPE` field 6 (verified)
- Melee model number drives Max's body: `c01_base<N>` with N = clamp(model, 0, 3) + 2. Monica's is `c02_base<N>` with N = clamp(model, 0, 3). chronicletwo:ps2/src/userdata.cpp:1710-1750 (verified). Max's melee model numbers in the data are 0, 1 and 2 only, which uses c01_base2 to c01_base4 (all in the extracted tree) (unverified: all 112 `WEP_SPE` records in cfg7 carry model numbers 0 to 3, but the record-to-item mapping for Max's melee rows was not checked). This answers the open question in the existing DC2 note; no current Max weapon reaches c01_base5 (inference from the data).
- Monica's 49 swords and Max's 25 melee entries do not match the wiki's 48 swords, 15 right-hand weapons and 19 guns (docs/fandom/Monica_Raybrandt.wiki, Maximilian.wiki). The data counts include duplicates and the fishing rods; the wiki's split is unexplained (verify).

### HP, defence and thirst

- DC1 max HP is set once per character. The only non-debug path that raises it that was found is Fruit of Eden: each use adds the item's volume to `max_hp`, capped per character at 170 (Toan), 140 (Xiao), 170 (Goro), 140 (Ruby), 180 (Ungaga), 160 (Osmond). chronicle:ps2/src/menu_misc.cpp:276-288 (verified; a grep of `ps2/src` found no other writer). The debug path raises max HP separately (battlemenu.cpp:1963-1970) and is not part of play.
- DC1 defence (`defense[6]`) is a flat guard subtracted from each hit, doubled under stamina. chronicle:ps2/src/dun/gameloop.cpp:7136-7146 (verified). Favourite foods 136 to 141 add to it by character index (item minus 136): each adds the item's volume plus a random roll, capped at 99. chronicle:ps2/src/menu_misc.cpp:221-240; chronicle:ps2/include/itemdata.hpp:235-240 (ITEM_FLUFFY_DOUGHNUT=136 to ITEM_CARROT_COOKIE=141) (verified). Toan's Fluffy Doughnut: docs/fandom/Toan.wiki (verified).
- DC1 thirst is a water gauge per character (`water_now`, `water_max`). `CUserStatus::Step` drains it by `0.003 * (1 + 0.2 * cur_georama)` per call, five times faster in the thirst zone, times 0.8 with the quench weapon flag (0x8), and times 2 with the thirst flag (0x10). At zero water, thirst damage accumulates at 1/120 per call and costs 1 HP. chronicle:ps2/src/dngstatusdata.cpp:634-680 (verified). `Step(0)` is called from `motionDrive` (call at gameloop.cpp:6201; `motionDrive` itself starts at 5783) (verified). The per-tick rate is unverified (see open question 5). The index is the georama (town or dungeon) index, not the floor (inference from the comment).
- The dungeon loop sets `water_drain_disable` when the stick is centred, so drain stops while the stick is idle (chronicle:ps2/src/dun/gameloop.cpp:3117-3121, verified). Whether every field state passes through that block is inference.
- DC1 "dry" warning threshold is 10 percent of water max. chronicle:ps2/src/dngmessageman.cpp:33-34 (verified)
- DC2 max HP is a gauge per human (`COMMON_GAGE hp`). Fruit of Eden adds 8 to max HP, capped at 255. chronicletwo:ps2/src/menucls1.cpp:1130-1137; gamedata.hpp:105 (verified)
- DC2 defence starts at 4 (Max) and 8 (Monica). Potato Pie (0x184) adds 4 only when the equipped melee is Max's melee class; Witch Parfait (0x185) adds 4 only with Monica's sword. Cap is 0x80 (128). chronicletwo:ps2/src/menucls1.cpp:1112-1122; chronicletwo:ps2/include/gamedata.hpp:128-129 (verified). Defence is a flat subtraction from damage (chronicletwo:ps2/src/actionchara.cpp:2989, verified); Power status multiplies weapon attack by 1.5 (userdata.cpp:4990-4998).
- DC2 has no thirst gauge. Thirst is the `CHARA_STATUS_DRY` bit (0x40). chronicletwo:ps2/include/userdata.hpp:44-53 (verified). A DRY weapon special (`WEAPON_SPECIAL_DRY`) applies it on a 50 percent roll per hit (actionchara.cpp:3071, verified). While DRY, food is refused except Plum Rice Ball (menucls1.cpp:1112, 1165, verified).
- Witch Parfait exists in both games with different ids and effects: DC1 139 (Ruby's favourite food, defence, cap 99) and DC2 0x185 (Monica's defence, melee-gated, cap 128). Name collision, not a shared item.

### Specials and gauges: Dark Cloud

- Toan's special (`ToanKey_On` / `ToanKey_Play`): a combo chain with action ids 0x24 to 0x27. A follow-up needs at least 20 gauge and costs 25 per hit. One charge branch (charge time at least 2.5, charge level 1) needs `skill_owned[0]`, which events set. chronicle:ps2/src/charakey.cpp:54-98, 226-371, 438-447 (verified)
- Ungaga's special (`UngagaKey_On` / `UngagaKey_Play`): a combo with at least 40 gauge to queue, costing 20 per hit. It writes `skill_owned[4] = 1`, and no reader was found in `ps2/src`. chronicle:ps2/src/charakey.cpp:604-640, 740-796 (verified)
- Goro's special (`GoroKey_On` / `GoroKey_Play`): one smash that needs the full 100 gauge and resets it to 0. chronicle:ps2/src/charakey.cpp:936-948, 1117-1133 (verified)
- Xiao's special (`BattleActionOn_Jinn`): needs exactly 100 gauge and fires a shot of attack damage with a 120-frame life. chronicle:ps2/src/dun/gameloop.cpp:7655-7760 (verified)
- Ruby's special (`BattleActionOn_Ruby` / `BattleActionShotRuby`): needs 100 gauge. Her form is the ring's best element: five effect sets F1, C1, T1, W1, H1. chronicle:ps2/src/dun/gameloop.cpp:7822-7840, 6763-6780 (verified); btitem.cpp:114 (verified)
- Osmond's three gun styles (`gun_type`) come from the equipped gun id: Jackal, G Crusher, Star Breaker, Machine Gun and others default to 0 (machine gun, rapid); Hexa Blaster, Supernova and Snail are 1 (homing, needs 100 gauge); Blessing Gun and Skunk are 2 (flame). chronicle:ps2/src/dun/gameloop.cpp:6780-6812; 8071-8098 (verified)
- Action gauge gain: Toan and Ungaga gain a quarter while idle and nothing while swinging. Osmond gains nothing while not exhausted in machine-gun or flame mode, half when exhausted, and times 1.5 in homing mode. Xiao and Ruby gain times 1.5. chronicle:ps2/src/dun/gameloop.cpp:6088-6170 (verified)

### Specials and gauges: Dark Chronicle

- No DC2 action gauge or per-character special was traced. Max's and Monica's attacks are weapon-driven. The sub slot's armband fires a point-shaped magic attack of kind `DAMAGE_KIND_MONICA_MAGIC` (chronicletwo:ps2/src/colprim.cpp:400, verified). Floor practice masks are the only class-level behaviour found (see below).
- Practice masks (`DNG_PRACTICE_ACTION`) record which class hit a monster on a floor: item 0x01, Max melee 0x02, Max gun 0x04, Monica melee 0x08, Monica magic 0x10, ridepod 0x20, monster 0x40, heal 0x80. chronicletwo:ps2/include/dngfloor.hpp:103-112 (verified)
- Floor practice types include "weapon only" (uses one practice bit), "ridepod only", "monster only" and "no heal". chronicletwo:ps2/include/dngfloor.hpp:119-127 (verified)

### Field abilities: Dark Cloud

- Atla pickup is Toan only. Any other member gets a refusal message. chronicle:ps2/src/dun/gameloop.cpp:3641-3647 (verified)
- Each character has a map key part placed on the floor (`CDungeonMap::SetCharaDoor`). Toan's case places `MAP_PARTS_KEY_XIAO` once, and only when `party_size >= 2`. Xiao, Goro and Ruby each get the room doors of their own kind (north, east, south, west, by part id 55-67). Ungaga (68) and Osmond (69) each get a single key cell. chronicle:ps2/src/dungeonmap.cpp:3355-3440; ps2/include/dungeonparts.hpp:92-117 (verified). Toan using the Xiao key part id is a naming oddity (verify).
- Ruby's door key is an element 0 to 4 chosen at load (`BtRubyDoorKey`); events with key -2 read it. chronicle:ps2/src/itemdata.cpp:488-495, 1275-1288 (verified)
- Osmond's special movement: he can move while an action is running (gameloop.cpp:3163); a ground kind 0xA interaction is his alone (gameloop.cpp:3568, 5081); ground kind 10 refuses the battle menu with a message (battlemenu.cpp:1912). verified
- Xiao "can jump across chasms" (docs/fandom/Dark_Cloud.wiki:31). The code has a rotation branch for Xiao's action 0xC (gameloop.cpp:3343), but no jump routine was traced (verify).
- Hand rigs: Xiao and Ruby (and Osmond's hand actions) use the `CharaHand` model for their hand actions (gameloop.cpp:5089-5140). verified

### Field abilities: Dark Chronicle

- Max rides the Ridepod. The ride is an R3 swap, allowed only when Max is alive and the floor does not disable him (`DNG_FLOOR_DISABLE_MAX`, scenesnd.hpp:89). The Ridepod's energy gauge (`ROBO_DATA.hp`) drains at `0.006 * used / capacity` per step (userdata.cpp:5025). chronicletwo:ps2/src/userdata.cpp:3053-3135, 5025 (verified). The wiki calls it a fuel meter (docs/fandom/Ridepod.wiki).
- Monica's monster form comes from the Badge Box (item 0x134, gamedata.hpp:112). Its HP is Monica's own pool (`hp = &manager->GetCharaDataPtr(USER_CHARA_MONICA)->hp`, userdata.cpp:4856) and drains 0.005 per step, or 0.0025 with badge 12 (userdata.cpp:5043-5046). verified
- Monica is disabled on floors with `DNG_FLOOR_DISABLE_MONICA` (scenesnd.hpp:90). Town disables Ridepod and monster changes (`SetEnvUserDataMan`, userdata.cpp:4714-4727). verified
- Partner swap: L3 switches Max and Monica, R3 switches Max to the Ridepod or Monica to the monster (dng_main.cpp:3039-3068, per the DC2 character note). inference from the existing note
- Max's fishing rods (ids 302, 303) are melee-class entries (docs/fandom/Maximilian.wiki says Max may equip fishing rods). verified

### Stats: side by side

| Quantity | DC1 (Dark Cloud) | DC2 (Dark Chronicle) | Source |
|---|---|---|---|
| Start max HP | Toan 70, Xiao 60, Goro 100, Ruby 90, Ungaga 110, Osmond 100 | Max 32, Monica 48 | dngstatusdata.cpp:892; userdata.cpp:2766 |
| HP growth | Fruit of Eden: + item volume, cap 140-180 by character | Fruit of Eden: +8, cap 255 | menu_misc.cpp:276-288; menucls1.cpp:1130-1137 |
| Start defence | Toan 3, Xiao 1, Goro 12, Ruby 23, Ungaga 38, Osmond 46 | Max 4, Monica 8 | dngstatusdata.cpp:893; userdata.cpp:2803-2804 |
| Defence cap | 99 (foods) | 128 (foods) | menu_misc.cpp:224-240; menucls1.cpp:1119-1121 |
| Defence use | flat subtraction, doubled under stamina | flat subtraction | gameloop.cpp:7136-7146; actionchara.cpp:2989 |
| Thirst | water gauge, max 30 start; drained by movement | DRY bit, no gauge | dngstatusdata.cpp:634-680; userdata.hpp:51 |
| Thirst threshold | 10 percent of water max | DRY bit | dngmessageman.cpp:33-34 |
| Weapon counts | 42, 15, 17, 16, 16, 14 | 25, 19 (Max); 49, 19 (Monica) | itemdata.cpp:1428; cfg7 |
| Durability | WHP 0-99 | durability 16-100 | itemdata.hpp:656 ; cfg7 `WEP` |
| Attack | 1-212 by owner | 1-150 | itemdata.cpp; cfg7 `WEP_ST` |

## How it works

### 1. Two different models of "character"

DC1 has six slots, and every per-character field is a `[6]` array indexed by the `Character` value. The party is the first `party_size` slots (battlemenu.cpp:2259, per the existing DC1 note). Its weapon, HP, defence and thirst each live in a separate array, so a crossing has to read several arrays per character. DC2 has two human records with real structs (`CHARA_DATA`, `ROBO_DATA`, `MOS_CHANGE_PARAM`), plus flags for who may be switched to. The two models share almost nothing, so the crosswalk has to be built from concepts (HP, defence, thirst, weapon class), not from fields.

### 2. Weapons: classes, not characters

Both games sort weapons by owner, but differently. DC1 has one owner per weapon, stored in `WEAPON_DATA.owner`, and the owner is also the id range. DC2 has no owner field in `CDataWeapon`: the owner is the item's `COM` type (1 to 4), which says Max melee, Max gun, Monica sword or Monica armband. The natural crosswalk is therefore by class, with each DC1 owner group pointing at a DC2 class:

| DC1 owner (weapon class) | DC2 class (type) | Fit | Notes |
|---|---|---|---|
| Toan (blade: dagger, sword) | Monica sword (3) | Close | Both are plain blades. Toan's combo special has no DC2 counterpart. |
| Goro (hammer: mallet, crusher) | Max melee (1) | Close | Max's melee is wrenches and hammers. Goro's full-gauge smash has no counterpart. |
| Ungaga (staff, spear: fighting stick, javelin, halbert) | Max melee (1) | Weak | No long-reach class in DC2. Falls back to a blunt melee class. verify |
| Xiao (slingshot) | Max gun, ordinary and launcher (2) | Medium | Ranged in both. Xiao's full-gauge shot has no counterpart. |
| Osmond (gun: machine gun, launcher, flame, homing) | Max gun, launcher, laser, machine gun (2) | Medium | Maps by gun attack type (0 ordinary, 10 launcher, 20 laser, 30 machine gun). DC1's flame and homing styles have no DC2 class. |
| Ruby (magic ring, elemental) | Monica armband (4) | Close | Both are elemental magic. DC2 weapons and armbands use the wiki's four elemental attributes, DC1 rings use five (with holy). |

Reverse direction: Monica sword (3) to Toan; Max melee (1) to Goro (or to Ungaga as a fallback); Max gun (2) to Osmond or Xiao by attack type; Monica armband (4) to Ruby. There are two DC2 kits and six DC1 kits, so the mapping should be per class, not per person.

### 3. Stat conversion

- **HP.** Absolute values cannot carry (DC1 60 to 110 against DC2 32 and 48). Carry the current/max ratio, and track growth separately: DC1 Fruit of Eden volume and cap per world, DC2 +8 per Fruit up to 255. This matches the existing design (`ixion:docs/DESIGN.md` section 4.3).
- **Defence.** Both games subtract defence flat from damage, so the scale of the damage numbers decides whether a flat carry is safe. Converting by fraction of each world's cap (DC1 99, DC2 128) gives starting fractions of Osmond 46 percent against Monica 6 percent, or Ungaga 38 percent against Max 3 percent. Those fractions are very different from each other, so a fraction carry is a design choice, not a neutral translation (proposal, verify against a damage comparison).
- **Attack.** Normalise within the source owner, then map to the target class range: `frac = attack / owner_max_attack`, then `dc2_attack = 1 + frac * 149`. DC1 owner maxima are Toan 199, Xiao 150, Goro 199, Ruby 99, Ungaga 212, Osmond 128. DC2 maxima are 150 for every class (proposal).
- **Durability.** `whp_frac = whp / 99` (the DC1 maximum), then scale to DC2's 16 to 100 range (proposal).
- **Elements.** DC1 fire, ice, thunder and wind map to DC2 flame, chill, lightning and cyclone (approximate; wind and cyclone are not the same effect). DC1 holy has no DC2 element and goes to the ledger (proposal).
- **Anti-monster.** DC1 has ten families and DC2 has four. A rough map: dino to scale, undead to exorcism, beast to beast, stone and metal to smash, sky to cyclone. The others go to the ledger (proposal, verify).
- **Speed and endurance.** DC1 only (action-gauge refill; WHP loss rate). DC2 has no counterpart, so carry them in the ledger and fall back to class defaults when a DC2 weapon is built.
- **Magic.** DC1 uses magic in Ruby's and Osmond's damage. DC2 has no magic stat in the weapon record, so fold it into attack or ledger it (proposal).
- **Thirst.** DC1 water at or below 10 percent of max means DRY; a DC2 DRY bit maps to a fraction of 0.05 (the existing design's value). Arrival floors the fraction at 0.10 so a crossing does not kill on step one (`ixion:docs/DESIGN.md` section 4.3, proposal).

### 4. What is world-only

Monica's monster form, the Ridepod and DC1's Atla right have no counterpart in the other game. They are local (not translated) by the design's four-bucket rule (`ixion:docs/DESIGN.md` section 4.1). A DC1 character in DC2 has no monster form or Ridepod, and a DC2 character in DC1 has no Atla pickup unless the crossing grants that right.

## Ixion hooks

1. **Roster record per (world, character id).** Store the minimum record described in the next section. Source values: DC1 `CDngStatusData::Initialize` (chronicle:ps2/src/dngstatusdata.cpp:892-921) and DC2 `CUserDataManager::Initialize` (chronicletwo:ps2/src/userdata.cpp:2764-2804). No engine change is needed; the record is filled from these tables at station time.
2. **Weapon class map at the station.** Keep a small table from DC1 owner ranges (`CheckWeaponUser`, chronicle:ps2/src/dngstatusdata.cpp:264-290) to DC2 type codes (cfg7 `COM` field 1). The conversion reads both data tables (`WeaponList` and `menu/cfg7/wepdat.cfg`) and does not touch either engine's functions.
3. **HP ratio write.** On arrival, set the current value from the ratio. DC1: `CUserStatus::max_hp[]`, `hp[]`, `SetNextLife` (chronicle:ps2/include/userstatus.hpp). DC2: `chara_data[i].hp` (`COMMON_GAGE`, chronicletwo:ps2/include/gamedata.hpp:487-491). Both are per-slot writes.
4. **Thirst mapping.** DC1 `CUserStatus::water_now[]` and `water_max[]` (chronicle:ps2/src/dngstatusdata.cpp:634-680) and DC2 `CHARA_STATUS_DRY` in `CHARA_DATA::status_attr` (chronicletwo:ps2/include/userdata.hpp:44-53). The DRY threshold in DC1 is `SetStatus_Dry` (chronicle:ps2/src/dngmessageman.cpp:33-34).
5. **Guest specials.** DC1 dispatches specials by `UserStatus->cur_chara` in one switch (chronicle:ps2/src/dun/gameloop.cpp:3675-3730). A guest that keeps its own slot runs its own special. A new ability key per roster row is cleaner than editing the switch (see the existing DC1 note).
6. **Floor practice bits.** When a guest hits a monster, set the DC2 `DNG_PRACTICE_ACTION` bit for its class (chronicletwo:ps2/include/dngfloor.hpp:103-112), so cross-cast play still satisfies floor challenges.
7. **Kit at arrival.** DC2 `GetCharaDefaultWeapon` (chronicletwo:ps2/src/userdata.cpp:4730) gives a default kit for a human slot. A DC1 guest's kit is built from the class map in hook 2.
8. **Switching gate.** DC2 `CheckEnableCharaChange` (chronicletwo:ps2/src/userdata.cpp:3053) is the place a guest's alive-and-allowed rule would be read.

## Risks and blockers

- **Item id collision.** DC1 weapon ids are 257 to 377. DC2 weapon ids are 1 to 110 plus 302, 303 and 387, which overlap DC2's own item-number space. A single table needs a world prefix on every key.
- **Two data formats.** DC1 weapons are C structs (byte-for-byte, itemdata.cpp:1422-1427). DC2 weapons are text in `menu/cfg7/`, parsed by the script interpreter. Ixion's converter must read both, and must read cfg7 (cfg5 and cfg6 have different field counts and would give wrong attack types).
- **Defence and damage scales.** Flat subtraction in both games makes the defence carry sensitive to damage scale. Starting fractions differ widely (Osmond 46 percent of cap, Monica 6 percent). Carrying by fraction could make some crossings trivial or impossible.
- **Ruby, Osmond and Toan are keyed by id.** DC1 logic tests `cur_chara` against fixed ids in many places (Atla, Osmond's ground kinds, Ruby's element door, Xiao's hand). A guest that keeps the id keeps these behaviours. A guest in another slot would lose them.
- **DRY and thirst timing.** DC1's drain is per `motionDrive` call. The call rate (per frame or per motion tick) is not verified, so the 120-call damage tick and the drain time are not in seconds.
- **Save layout.** DC1 keeps six-wide arrays in `CUserStatus`; DC2 asserts `CUserDataManager` is `0x457A0` bytes (existing DC2 note). Ixion must write only its own bundle, never either native save (`ixion:docs/DESIGN.md` section 3.6).
- **Counts disagree with the wiki.** Monica has 49 swords in data against the wiki's 48. Max's melee list has 25 entries against the wiki's 15. Any "starter weapon count" shown to players needs the data number, with the wiki split noted as unexplained.

## Open questions

1. How does a DC2 armband's element reach damage? The attribute path was not traced, so Ruby's five forms cannot yet be matched to Monica's four elements.
2. Who reads `skill_owned[4]` (set by Ungaga's special in DC1)? No reader was found in `ps2/src`.
3. What is the runtime path that lets each character's door or key part open? `SetCharaDoor` places them, but the open check was not traced.
4. Is Toan's key part (`MAP_PARTS_KEY_XIAO`) intended, or a copy-paste from Xiao's case?
5. How often is `Step` called per second? This sets the real-time thirst rate and the 120-tick damage interval.
6. Does DC2 have any action gauge or special for Max or Monica beyond weapon attacks? None was traced.
7. Is the DC2 cyclone attribute an element (in the "highest of the first four" rule) or only an anti-flying attribute? The wiki lists it in both roles.
8. What are the true DC2 weapon counts? The data (49 swords, 25 melee entries) and the wiki (48, 15) disagree, and the reason is not known.
9. Should a DC1 character keep its own special in DC2 (as a per-slot ability), or lose it? That is a design decision, and it sets how much of each switch needs a roster key.
10. Are DC2 weapon `special` bits (drain, steal, dry and others) meaningful on a DC1 target, or should they be dropped? The DC2 bits are not mapped to DC1 flags anywhere yet.
