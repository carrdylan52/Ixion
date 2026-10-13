# Chronicle (DC1): items, weapons and attachments

## What this covers

Chronicle's item, weapon and attachment data and the code that reads, changes and moves it:
the ID space and its tables (`ITEM_LIST`, `WeaponList`, `AttachList`, `ComItemInfo`), the
weapon and attachment record layouts, weapon level-up, status break (synthesis sphere) and
build-up, durability, shop prices and goods, chest and drop tables, the stock and dungeon
inventory, and the port's changes to the item accessors. Read from the `master` tree of the
Chronicle decomposition (ps2/src is retail, port/src is the PC port). Static reading only; no
build or run. Table counts and per-owner ranges were checked by parsing the source tables.

Section 4 of the design draft in ChronicleTwo (`chronicletwo:ixion/docs/DESIGN.md:195-240`)
depends on several Chronicle weapon rules described here. The Ixion hooks section notes where
the code bears on that draft (the 60% carry and the damage-type carry).

## Key facts

- The item ID space is one `enum Item` with four runs: attachments 81-131, dungeon items
  132-256, weapons 257-376, and an end marker `ITEM_WEAPON_END = 377`. `chronicle:ps2/include/itemdata.hpp:188-464`
- IDs 1-80 are a separate "menu/script" numbering for weapons. Runtime code converts them
  with `TransWepNo`, which is banded (not linear). `chronicle:ps2/src/menu_save.cpp:1717-1739`
- `ComItemInfo` (296 rows) maps every ID 81-376 to a kind (attach/item/weapon), an index into
  the matching table, an icon, and a name message ID. Kinds are contiguous: attach 81-131
  (51 rows), item 132-256 (125 rows), weapon 257-376 (120 rows). `chronicle:ps2/src/itemdata.cpp:1832-2129`
- `ITEM_LIST` has 175 entries. Indices 0-50 are unused "attach slot" placeholders. Item IDs
  132-255 use indices 51-174. ID 256 points at index 175, one past the array. `chronicle:ps2/src/itemdata.cpp:1654-1830`, `:1832`
- `AttachList` has 50 explicit entries (IDs 81-130). ID 131 maps to index 50, one past the
  end. `chronicle:ps2/src/itemdata.cpp:1551-1652`
- `WeaponList` has 120 entries (IDs 257-376), each 0x4C bytes. `chronicle:ps2/src/itemdata.cpp:1428-1549`; `chronicle:ps2/include/itemdata.hpp:656-681`
- Weapons are grouped by owner in contiguous chains. Chain position 0 is the "broken" default
  weapon for that character. `MenuDefaultWeaponNo` gives each character's chain start. `chronicle:ps2/src/battlemenu.cpp:117`
- Per-owner weapon counts: Toan 42, Xiao 15, Goro 17, Ruby 16, Ungaga 16, Osmond 14 (total 120).
  `MenuCharaWeaponMax` agrees. `chronicle:ps2/src/battlemenu.cpp:119`. Owner field and id-range routing agree for all 120 weapons (checked by parse).
- A weapon's owner is stored in `WeaponList[id-257].owner`. `GetItem` reaches it through a
  PS2 link-layout byte offset (`ItemPutListTbl12_bytes[750 + id*76]`). `chronicle:ps2/src/dngstatusdata.cpp:431`
- The port replaces that byte-offset lookup with a typed lookup. `chronicle:port/include/stubs/dngstatusdata.hpp:10-23`
- Weapon stat fields are on `WEAPON_DATA` (durability, attack, endurance, speed, magic, owner,
  six socket slots, five element values, ten monster-class values, exp base and per-level
  exp, flags, a 64-bit build-up mask split over two words, attack and magic caps, chain
  position). Four fields are unknown (`unk_34`, `unk_36`, `unk_3A`, `unk_4A`). `chronicle:ps2/include/itemdata.hpp:656-681`
- Owned weapons are `WEAPON_HAVE` (0xF8 bytes). It holds level (0-99), current stats,
  durability as `s16` and `float`, experience, element and monster values, six attachment
  slots, socket kinds, option flags, and synthesis points. `chronicle:ps2/include/itemdata.hpp:686-708`
- Attachments are `ATTACH_DATA` in the table (0x20 bytes) and `ATTACH_LIST` on a weapon or
  in inventory (0x20 bytes). Both carry the same attack, endurance, speed and magic fields,
  five elements, ten monster classes, and sphere metadata. `chronicle:ps2/include/itemdata.hpp:564-602`
- Attachment categories are ID ranges (element 81-90, stat 91-95, gem 96-109 and sun,
  slayer 111-121, other = 110). `chronicle:ps2/include/itemdata.hpp:643-649`
- Level cap is 99. Level-up adds +1 to attack, endurance, speed and magic (capped at 99 or the
  weapon's `attack_max`/`magic_max`), adds 1-3 durability, and resets experience. `chronicle:ps2/src/weaponlevelup.cpp:412-446`
- The level-up threshold is `GetWeaponMaxExp`: `exp_base` plus `exp_per_level` per level, with a
  999 ceiling. Kill exp stops at that threshold. Back-dungeon kills double the exp; flag `0x2000`
  multiplies it by 1.2. `chronicle:ps2/src/menu_draw.cpp:2733-2759`; `chronicle:ps2/src/monstorunit.cpp:2175-2210`
- Status break turns a level-5-or-higher weapon into a Synthesis Sphere (attachment ID 90)
  stored in the dungeon consumable area. Base stats, elements and monster values are carried at
  60%. Attachments are added at 60% too. `chronicle:ps2/src/weaponlevelup.cpp:448-530`; `chronicle:ps2/src/menu_misc.cpp:470-484`
- Build-up is gated by the destination's `WEAPON_DATA` attack, magic, elements and monster
  values used as minimums. Destinations come from `buildup_mask0`/`buildup_mask1` on the
  held weapon's data. `chronicle:ps2/src/weapon_buildup.cpp:50-85`, `:190-230`
- Build-up on apply copies only endurance, speed and durability from the destination. It does
  not copy attack, magic or elements. Attachments are not cleared. `chronicle:ps2/src/weapon_buildup.cpp:141-155`; `chronicle:ps2/src/weaponlevelup.cpp:902-926`
- Mardan Eins and Mardan Twei are gated on the fish count (5 and 15) rather than on weapon
  data. `chronicle:ps2/src/weapon_buildup.cpp:157-188`
- Chest contents come from `ItemPutListPtr[14]` (seven dungeons plus back floors, ordinary and
  special). Each list is per floor and holds up to 128 item IDs. `chronicle:ps2/src/dungeonparts.cpp:796`, `:867`; `chronicle:ps2/include/dungeonparts.hpp:238-250`
- Chest selection reduces a weapon's chance by 10 if held once, or 20 if held twice or more. `chronicle:ps2/src/dungeonparts.cpp:1605-1640`
- Retail chest selection copies its rate table from the wrong address (pointer-table bytes,
  not the list). The port reads the dungeon's own list instead. `chronicle:ps2/src/dungeonparts.cpp:1623`; `chronicle:port/src/dungeonparts.cpp:11-39`
- Shop prices are `PriceList[296]`, indexed by `id - 81`. Weapon buy prices run 2 to 6500.
  Forty-four weapon entries carry the placeholder 2/1, which suggests they are not shop goods
  (inference). `chronicle:ps2/src/shop.cpp:166`
- Sell price is the item's sell value plus the sell values of its attachments. `chronicle:ps2/src/shop.cpp:2584-2626`, `:2667-2684`
- Shop goods are `ItemShopList2[18][20]`, terminated by -1. `chronicle:ps2/src/shop.cpp:470-499`
- Fish-point exchange prizes are `exitemlst[35]`. `chronicle:ps2/src/shop.cpp:5355`
- Durability wear per use is `(1.5 - 0.01*endurance) * amount + 0.1*kind`, with a 2x
  multiplier for flag `0x100` (fragile), 0.5x for `0x200` (durable), and zero for the default
  weapon. Breaking swaps in the default weapon, or the base weapon if the broken one is
  equipped. Auto-repair powder can absorb a break. `chronicle:ps2/src/hitvalue.cpp:37-140`
- Lamb's Sword gets a 1.5x rate when durability is at or below 20%. `chronicle:ps2/src/menu_misc.cpp:460-468`
- Weapon option flags are a 14-bit field. Some bits cancel in pairs (`CheckWeaponOptionStatus`).
  `chronicle:ps2/src/menu_misc.cpp:1623-1660`
- Dungeon inventory: `ITEM_PACK` holds 103 item slots and 3 quick slots. `CheckItemGet`
  counts dungeon items (plus quick-slot quantities) up to `GetMaxDungeonItems()` and compares
  the result with `item_pack.num`. `consumable_items[43]` holds attachments. `chara_weapons[6][11]`
  holds weapons, and `GetItem` scans all 11 slots for the first empty one.
  `chronicle:ps2/include/userstatus.hpp:43-62`, `:127-128`; `chronicle:ps2/src/dngstatusdata.cpp:26`, `:203-262`, `:343-476`
- Stock inventory `CStockItem` (size 0x21C0) holds 60 dungeon items, 30 weapons and 30
  attachments. `chronicle:ps2/include/stockitem.hpp:29-33`, `:154`; `chronicle:ps2/src/stockitem.cpp:34-36`
- Monsters steal one item 10% of the time on a hit with flag `0x80`, provided the matching
  item pack section has room (`CheckItemGet` returns 0; this is a fullness test, not a
  "not already held" test). The item is carried by `CStealItem` (8 slots) and returned on arrival.
  `chronicle:ps2/src/monstorunit.cpp:1319-1323`; `chronicle:ps2/src/stealitem.cpp:24`
- Floor drops use `CRandomItem` (32 slots). A slot with `item_no == -1` is gold (unverified; the cited lines show the slot fields, and `item_no == -1` is only tested at `randomitem.cpp:148` and `:219`). `chronicle:ps2/include/randomitem.hpp`; `chronicle:ps2/src/randomitem.cpp:162-190`

## How it works

### 1. Identity and tables

Every item, weapon and attachment has one ID from the `Item` enum. The accessors all go
through `GetCommonItemInfo`, which turns the ID into a `COM_ITEM_INFO` row and then into the
right table. Items 1-80 are treated as a linear weapon alias
(`index = id + 175`, which is weapon `id + 256`), and IDs 81 and up index `ComItemInfo`
directly. `chronicle:ps2/src/itemdata.cpp:2139-2152`

`COM_ITEM_INFO` (8 bytes): `kind` (s8), `unk_01`, `index` (s16), `icon_index` (s16), `msg`
(s16, name message ID; the system message is `msg + 100`). `chronicle:ps2/include/itemdata.hpp:511-519`; `chronicle:ps2/src/itemdata.cpp:2202-2215`

| ID range | Kind | Table and index | Count | Notes |
|---|---|---|---|---|
| 0 | none | none | 1 | `GetCommonItemInfo` returns null |
| 1-80 | legacy weapon alias | `ComItemInfo[id+175]`, or via `TransWepNo` | 80 | Banded mapping to 257-376 in runtime code; linear alias in the accessors (conflict, see Risks) |
| 81-131 | attachment | `AttachList[index]` | 51 IDs | 81-130 defined; 131 reads one past the array |
| 132-256 | dungeon item | `ITEM_LIST[index]`, index 51-175 | 125 IDs | 256 reads one past the array |
| 257-376 | weapon | `WeaponList[id-257]` | 120 | Owners in contiguous chains (see 2) |
| 377 | end | none | - | `ITEM_WEAPON_END` |

Name messages: `msg` in `ComItemInfo`. Items use the ID as the message; weapons use index+1
for most entries (IDs 374-376 use 282, 283 and 0). `chronicle:ps2/src/itemdata.cpp:1832-2129`

Model paths: attachments and items use `ITEM_NAME_TBL_NEW[id-81]` (175 entries; placeholder
`no_item_name` for 86-90, 108-110, 121-131, 142-144, 156-158, 184, 192, 194, 213-215, 223, 232,
255). Weapons use `dun/item/main_wep/` plus a per-owner prefix (`c01w`, `c04w`, `c06w`,
`c05w`, `c10w`, `c18w`) and the chain offset. `chronicle:ps2/src/btitem.cpp:1332`; `chronicle:ps2/src/btmisc.cpp:107-130`, `:160-180`

### 2. Weapon owner sets

| Owner (Character) | IDs | Count | Chain 0 (default) | Model prefix | Weapon family (from names) |
|---|---|---|---|---|---|
| Toan (0) | 257-298 | 42 | 257 | c01w | Swords, daggers |
| Xiao (1) | 299-313 | 15 | 299 | c04w | Slingshots |
| Goro (2) | 314-330 | 17 | 314 | c06w | Hammers, axes |
| Ruby (3) | 331-346 | 16 | 331 | c05w | Rings, armlets |
| Ungaga (4) | 347-362 | 16 | 347 | c10w | Spears, sticks |
| Osmond (5) | 363-376 | 14 | 363 | c18w | Guns |

`chronicle:ps2/include/itemdata.hpp:485-492`; `chronicle:ps2/src/battlemenu.cpp:117-119`; `chronicle:ps2/src/btmisc.cpp:107-130`

Chain positions run 0..N for each owner. `WEAPON_DATA.chain_pos` repeats the position.
`chronicle:ps2/src/itemdata.cpp:1428-1549`

Routing: `CheckWeaponUser` maps an ID to its owner by id range; `GetItem` maps it by the
owner byte. Both agree for every weapon (checked by parse). `chronicle:ps2/src/dngstatusdata.cpp:264-294`, `:431`

### 3. Record layouts

WEAPON_DATA (table, 0x4C bytes): durability 0x00, attack 0x02, endurance 0x04, speed 0x06,
magic 0x08, owner 0x0A, hole[6] 0x0B (values 0 none, 1 normal socket, 2 synthesis-sphere socket;
counts over 120 weapons: 391 / 215 / 114), hole_num 0x11, elem[5] s16 0x12 (fire, ice,
thunder, wind, holy; max observed 90), vs_monster[10] s16 0x1C (slayer classes in
`AttachStat` order, max observed 88), exp_base 0x30, exp_per_level 0x32, flags 0x38,
buildup_mask0 0x3C (bit = chain position, positions 2-20), buildup_mask1 0x40 (bit k = position
20+k), attack_max 0x44, magic_max 0x46, chain_pos 0x48. `chronicle:ps2/include/itemdata.hpp:656-681`

Observed ranges across the table: base attack up to 212, base magic up to 210, durability,
endurance and speed up to 99, exp_base up to 125, exp_per_level up to 50, attack_max up to
350, magic_max up to 300. Five holes is the maximum (hole_num distribution: 6 weapons with 0,
2 with 1, 29 with 2, 67 with 3, 12 with 4, 4 with 5).

WEAPON_HAVE (owned, 0xF8 bytes): item_no 0x00, level 0x02, attack 0x04, endurance 0x06,
speed 0x08, magic 0x0A, durability 0x0C, durability_f (float) 0x10, experience 0x14,
best_elem 0x16, elem[5] 0x17, vs_monster[10] 0x1C, attach[6] (ATTACH_LIST) 0x28, attach_kind[6]
0xE8 (3 means doubled), flags 0xEE, synthesis_count (s32) 0xF0. `chronicle:ps2/include/itemdata.hpp:686-708`

ATTACH_LIST / ATTACH_DATA (0x20 bytes): item_no 0x00, sphere_weapon_no 0x02 (source weapon of a
sphere), sphere_flags 0x04 (source weapon options), sphere_level 0x06, status[4] 0x08 (attack,
endurance, speed, magic; `AttachStat` minus one), elem[5] 0x10, vs_monster[10] 0x15. `chronicle:ps2/include/itemdata.hpp:564-602`

ITEM_DATA (dungeon item table, 0x14 bytes): sort_key 0x00 (`ItemSortKey`), use_flags 0x04
(`ItemUseFlag`), kind_flags 0x08 (`ItemKindFlag`), vol 0x0A (fresh-copy volume; also the heal
amount, read through `&vol`), vol_range 0x0C (second amount, used by the drink path), stack_kind
0x10 (`ItemStackKind`). `chronicle:ps2/include/itemdata.hpp:524-557`; `chronicle:ps2/src/menu_misc.cpp:186-205`

ITEM_LIST summary: sort keys: none 65, quest 29, food 20, goods 18, key item 17, throw 12,
powder 9, fish 4, rotten 1. Stack kinds: never 94, multi 74, single 7. Non-zero volumes are
mostly on food, drink and amulets (amulets 132-135 roll `rand()%5+3` at pickup).
`chronicle:ps2/src/menu_draw.cpp:2942-2971`

Weapon flags (`WeaponFlag`): `0x08` quench (good), `0x10` thirst (bad), `0x100` fragile (bad),
`0x200` durable (good). The 14-entry good/bad table `IsWeaponOptionGoodOrBad` agrees with these
four bits; the other option bits are drawn as icons and their names are not in this source. `chronicle:ps2/include/itemdata.hpp:472-477`; `chronicle:ps2/src/menu_misc.cpp:1636-1650`

Flags on newly created non-default weapons are rolled: 1% durable, 1% fragile.
`chronicle:ps2/src/menu_draw.cpp:2914-2925`

### 4. Attachments and sockets

- Sockets: a weapon's `hole[i]` says whether a socket exists and what kind it is. A synthesis
  sphere only fits a socket with value 2. `chronicle:ps2/src/battlemenu.cpp:5339-5345`
- Doubled attachments: `attach_kind == 3` doubles that socket's contribution (x2). Only
  sockets that are not type 2 can be doubled, and at most one per roll (1 in 50).
  `chronicle:ps2/src/weaponlevelup.cpp:186-188`, `:396-404`
- Attachment totals are summed into a running record with caps. `AttachMentValuePlus` caps the
  attack and magic totals at the `attack_max`/`magic_max` of the weapon named in
  `sphere_weapon_no` (999 when that weapon is unknown), endurance and speed at 99, and elements
  and monster values at 99. `chronicle:ps2/src/weaponlevelup.cpp:35-78`
- Stat attachments (91-94) pick up at volume 1-3. Two rolls of `rand()*50` decide it: below 16
  gives 3, below 31 gives 2, otherwise 1. Other attachments have volume 0.
  `chronicle:ps2/src/btmisc.cpp:257-276`
- Stat attachment level is clamped to 1-3 when set into the dungeon consumable slot.
  `chronicle:port/src/menu_dungeon.cpp:34-72`; retail `chronicle:ps2/src/menu_dungeon.cpp:366`

### 5. Level-up, status break, build-up

Level-up (CWeaponLevelUp, effect-driven in the menu): `SetLevelUpValue` folds all attachment
totals into a preview weapon, clears the attachments, and rerolls doubled sockets. After the
effect, `SetLevelUpWeaponData` adds +1 to each base stat (capped) and 1-3 durability, then
`level++`, and the synthesis count is added. `chronicle:ps2/src/weaponlevelup.cpp:258-410`, `:412-446`; `chronicle:ps2/src/battlemenu.cpp:3711-3719`

Powder level-up: `ITEM_POWERUP_POWDER` (178) runs `WeaponLevelUpValueCalc` for a non-default
weapon with experience below max, then `level++` and clears the attachments.
`chronicle:ps2/src/menu_misc.cpp:382-398`

Status break: needs level 5 or higher (`WeaponStatusBreakEnable`). The sphere gets 60% base
stats, 60% elements and monster values, 60% of each attachment's totals, the source weapon ID,
level, and option flags. It is written to a free consumable slot. A default weapon is never
removed; its level resets to 0 and the character falls back to the default
(`lost_default_weapon`). `chronicle:ps2/src/weaponlevelup.cpp:448-530`, `:863-889`; `chronicle:ps2/src/menu_misc.cpp:470-484`

Build-up (weapon becomes another weapon in the same owner chain):
- Destinations: from the held weapon's build-up masks, positions 2 to max chain. The masks
  are only read for positions 2 and up. `chronicle:ps2/src/weapon_buildup.cpp:190-230`
- A destination is available if the held weapon's attack, magic, five elements and ten
  monster values meet the destination's base values (a negative requirement would mean "at
  most"; none are negative in the table). The held values come from `WeaponAllValueSet` with
  full rate, so attachment totals count toward them. `chronicle:ps2/src/weapon_buildup.cpp:50-85`; `chronicle:ps2/src/menu_dungeon.cpp:257-330`
- On apply: endurance, speed and durability are raised to the destination's base if lower;
  `item_no` changes; level and experience reset; destination option flags are OR'd in.
  `chronicle:ps2/src/weapon_buildup.cpp:141-155`; `chronicle:ps2/src/weaponlevelup.cpp:902-926`
- 14 weapons end their chain (`IsLastWeapon`): Arise Mardan, 7th Heaven, Sword of Zeus,
  Chronicle Sword, Super Steve, Ange Gear, Tall Hammer, Inferno, Mobius Ring, Secret Armlet,
  Hercules' Wrath, Babel's Spear, Star Breaker, Supernova. They get a different sound and
  effect. `chronicle:ps2/src/weapon_buildup.cpp:87-125`
- 82 of 120 weapons have a non-zero build-up mask (decoded by hand from the table; 38 have both
  masks zero and cannot be a build-up source) (unverified). Example, Baselard (chain 2) builds to chains 13 and 34. Choora (chain
  30) builds to chains 14 and 32 (unverified).

### 6. Durability and breakage

Each hit on the equipped weapon (not the default weapon) reduces `durability_f` by
`(1.5 - 0.01*endurance) * amount + 0.1*kind`, scaled by flags. When it reaches zero: auto-repair
powder restores full durability if held, otherwise the weapon breaks. If the broken weapon was
the base weapon, the default is restored; otherwise another weapon in the list is equipped and
the broken one is removed. `chronicle:ps2/src/hitvalue.cpp:37-140`

Repair powder (177) restores durability and, for a default weapon, upgrades the broken
version to the base version. `chronicle:ps2/src/menu_misc.cpp:366-380`

### 7. Experience and kills

`GetWeaponMaxExp` = `exp_base` (read as a signed byte, low byte only; all table values are
below 128 so the cast is latent) plus `exp_per_level * level`, capped at 999, and reset to 99
when the result is zero or below. `chronicle:ps2/src/menu_draw.cpp:2733-2759`

Kills: the last attacker gains the monster's exp (doubled in back dungeons, x1.2 with flag
`0x2000`), stopping at max. Reaching max raises a message. Under the no-weapon-change
restriction, exp is lost instead. `chronicle:ps2/src/monstorunit.cpp:2175-2210`

### 8. Inventory, pickup and routing

- `CDngStatusData::GetItem(id, qty)` routes by range: dungeon items to `item_pack` (first
  free slot, or an overflow slot; `overflow_flag`), attachments to `consumable_items`
  (43 slots, `SetAttachMentValue` sets stat levels), weapons to the owner's `chara_weapons`
  (11 slots, first empty). `chronicle:ps2/src/dngstatusdata.cpp:343-476`
- Full-pack checks: `CheckItemGet` returns 1 when the dungeon-item count (plus quick-slot
  quantities) reaches `item_pack.num` and 2 when attachments reach 40 (both are fullness tests, not "already held" tests).
  Weapons count non-empty slots among the first 10 (`CheckWeaponRot` returns the count; 10 means
  full for the big chest). `chronicle:ps2/src/dngstatusdata.cpp:203-262`, `:296-320`
- Big chest: when the owner's weapon count is 10 or more, the early branch shows a message and
  opens the chest. That branch does not reach the item hand-out (inference from the branch
  shape). If the chest holds Steve and the party already has Steve, Bone Slingshot is used
  instead. `chronicle:ps2/src/btitem.cpp:160-200`
- Small chest and attachment pickup go through `BtGetAttach_Init`, which gives the item and
  shows the pickup message. `chronicle:ps2/src/btitem.cpp:1107-1126`
- Chest selection (`PresetSmallItemNo_Get`): picks a floor's list, filters attachments for
  small chests, and draws from the dungeon's rate table (per-item chance out of 100). The port
  reads the dungeon's own rate list. `chronicle:ps2/src/dungeonparts.cpp:1605-1700`; `chronicle:port/src/dungeonparts.cpp:21-60`
- Gate keys (crests, slate and similar) take `BtGetGateKey_Init` instead of the normal pickup.
  Clown (Piero) items come from `GetPieroItem`. `chronicle:ps2/src/dun/gameloop.cpp:3446-3470`; `chronicle:ps2/src/btitem.cpp:984-1024`; `chronicle:ps2/src/dungeonparts.cpp:1515-1530`

### 9. Stock and sorting

The stock inventory sorts dungeon items by a rotating priority table (`sort_table__3`) and
attachments by a rotating `AttachKind` priority (`asort_table__3`). Each "Seiton" step
rotates the top priority by one. `chronicle:ps2/src/stockitem.cpp:14-36`, `:160-333`

### 10. Economy

- `PriceList[id-81]` gives `buy_price` and `sell_price` (s16 each). Dungeon items: buy 2-1000.
  Attachments: buy 2-5000. Weapons: buy 2-6500, with 44 placeholder 2/1 entries.
  `chronicle:ps2/src/shop.cpp:166-464`
- Sell price for a weapon in the shop is its own sell price plus the sell prices of its six
  attachment slots. `chronicle:ps2/src/shop.cpp:2599-2626`, `:2667-2684`
- Shop goods: `ItemShopList2[shop][0..19]`, -1 ends each list. Weapons appear in some shops
  (for example Kitchen Knife, Gladius, Bone Slingshot, Platinum Ring, Jackal, Snail).
  `chronicle:ps2/src/shop.cpp:470-499`
- Storage eligibility for a weapon (`IsEnableCharge`): enabled when the owner still holds the
  default or base weapon, or the owner is not in the party. Disabled while the held item came
  from an equipped slot. `chronicle:ps2/src/shop.cpp:1000-1040`

## Ixion hooks

The Ixion design draft (`chronicletwo:ixion/docs/DESIGN.md:195-240`) sketches a loaner
weapon, a one-way synthesis sphere, and a class map. The Chronicle side has the pieces it needs.

- **Canonical item key.** Build the key from `ComItemInfo` (kind, index, msg) plus the
  `Item` enum, not from the trailing comments in `ComItemInfo` (they are off by one; see Risks).
  Name lookup: `GetCommonItemDataMsg` (`chronicle:ps2/src/itemdata.cpp:2202`). Model lookup:
  `ITEM_NAME_TBL_NEW` and `makeWeaponName` (`chronicle:ps2/src/btitem.cpp:1332`; `chronicle:ps2/src/btmisc.cpp:107`).
- **Legacy ID intake.** Anything that carries a numeric weapon ID from a script, the editor or
  an external table should go through `TransWepNo` (banded) before any accessor. The editor
  already does this (`chronicle:ps2/src/edit.cpp:2013-2018`). Do not pass raw 1-80 IDs into
  `GetWeaponData` or `WepDataListToHaveCopy`.
- **Loaner weapon.** Park the origin `WEAPON_HAVE` whole (248 bytes). Translate a
  destination loaner from the destination's own base values (`WepDataListToHaveCopy`,
  `chronicle:ps2/src/menu_draw.cpp:2875-2925`). Growth to write back: `level`, `experience`,
  `synthesis_count`, `durability_f` and attachment totals.
- **Synthesis sphere (one-way, costly).** `CWeaponLevelUp::SetStatusBreak` already implements
  the 60% carry, and records the source weapon ID, level and option flags in the sphere
  (`chronicle:ps2/src/weaponlevelup.cpp:448-530`). It matches the design draft's "about 60%"
  claim. The sphere carries `sphere_weapon_no` (source) and `sphere_flags` (options), which an
  Ixion receiver can read back.
- **Damage-type carry.** Keep `elem[5]` (fire, ice, thunder, wind, holy) and `vs_monster[10]`
  (slayer classes) as the carried damage profile, which is what the design calls "damage type".
  Both are on `WEAPON_HAVE` (`chronicle:ps2/include/itemdata.hpp:686-708`).
- **Class map by chain.** The build-up graph (`buildup_mask0/1`) can serve as the "nearest
  weapon" lookup for a translated weapon. Chains are contiguous per owner, so "same family" is
  "same owner chain" (`chronicle:ps2/src/weapon_buildup.cpp:190-230`).
- **Ownership override.** Cross-cast weapons need routing that does not depend on the
  owner byte. The entry point is `CDngStatusData::GetItem` (weapon branch) and the port's
  `PortWeaponOwners` (`chronicle:ps2/src/dngstatusdata.cpp:431`; `chronicle:port/include/stubs/dngstatusdata.hpp:10-23`).
- **Shop and chest extension.** Add Ixion goods to `ItemShopList2` (`GetItemShopList`,
  `chronicle:ps2/src/shop.cpp:501`) and Ixion drops to `ItemPutListPtr` lists
  (`chronicle:ps2/src/dungeonparts.cpp:867`). Prices come from `PriceList`, indexed by `id-81`.
- **Post-crossing repair.** `REPAIR_POWDER` and the default-weapon fallback
  (`chronicle:ps2/src/hitvalue.cpp:80-140`) already give a "break and recover" path if the
  carried weapon fails on the far side.

## Risks and blockers

- **Conflicting legacy mappings.** `TransWepNo` (banded) and the linear `+256` in
  `GetCommonItemInfo` (`chronicle:ps2/src/itemdata.cpp:2144-2146`) and `WepDataListToHaveCopy`
  (`chronicle:ps2/src/menu_draw.cpp:2884`) disagree for legacy IDs 21-80. For example legacy 21:
  banded gives 299 (Xiao chain 0), linear gives 277. Any Ixion path that feeds legacy IDs to
  the accessors gets the wrong weapon. Ids 1-20 agree.
- **Out-of-range table reads.** ID 131 reads `AttachList[50]` and ID 256 reads `ITEM_LIST[175]`
  in retail; the port returns null for both (`chronicle:port/src/itemdata.cpp:52-68`).
  `SearchSpace` treats the dungeon range as inclusive of 255 only, while `CheckItemGet` treats
  it as up to 256 (`chronicle:ps2/src/stockitem.cpp:52`; `chronicle:ps2/src/dngstatusdata.cpp:203-212`).
- **Misleading comments.** `ComItemInfo` trailing comments are off by one name (for example
  "id 253 Clay Doll" where the enum says `ITEM_MANUAL` = 253; `ITEM_LIST` and the enum agree).
  `chronicle:ps2/src/itemdata.cpp:1832-1850`, `:1828-1829`. Do not derive names from them.
- **Header inaccuracy.** `WEAPON_HAVE.best_elem` is documented as -1 for none, but the code
  sets 5 (`WEAPON_ELEMENT_NONE`). `chronicle:ps2/include/itemdata.hpp:697`; `chronicle:ps2/src/menu_draw.cpp:2896`
- **Latent loop defect.** `WeaponLevelUpValueCalc` reuses `i` in the inner loop
  (`chronicle:ps2/src/weaponlevelup.cpp:103-104`). For `levels` 1-7 the body runs once rather
  than `levels` times, and for 8 or more the outer loop never ends (inference from the control
  flow). The one caller passes 1 (`chronicle:ps2/src/menu_misc.cpp:395`). Do not call it with
  more than 1 level without fixing it.
- **Chest rate bug (retail).** Retail reads the rate table from the wrong address (pointer-table
  bytes). Behaviour differs between NTSC and PAL. The port fixes it. Ixion must pick one and
  record which (`chronicle:port/src/dungeonparts.cpp:11-18`).
- **Build-up keeps held base stats.** `SetWeaponBuildValue` does not reset attack, magic or
  elements to the destination. A weapon can end up above the destination's `attack_max` (not
  verified in game; inference from code).
- **Port layout coupling.** `PortWeaponOwners` depends on `sizeof(WEAPON_DATA) == 76` and a
  fixed offset (`chronicle:port/include/stubs/dngstatusdata.hpp:14`). Changing the table breaks
  it at compile time, which is the intended guard.
- **Fixed-size character slots.** `chara_weapons[6][11]`, `defWeapon[6]`, `MenuCharaWeaponMax[6]`,
  `MenuDefaultWeaponNo[7]`, `CUserStatus` and the `CDngStatusData` size assert (0x8C9C) all
  assume six characters. Adding characters changes the save layout.
  `chronicle:ps2/include/userstatus.hpp:127`; `chronicle:ps2/include/dngstatusdata.hpp`
- **Unknown fields.** `WEAPON_DATA` `unk_34/36/3A/4A`, `ITEM_LIST` `unk_02/unk_0E`, and most
  `kind_flags`/`use_flags` bits (only some are named in the header). Layout is known; meaning
  is not.
- **Save format.** The save loader does not call `TransWepNo` (no match in `savedata.cpp`), so
  saves most likely store runtime IDs 257+ directly (inference). Confirm before writing a save
  translator.
- **Asset paths.** Translated items need model and texture paths. Weapon models are keyed by
  owner prefix and chain offset, and some item models are placeholders (`no_item_name`).

## Open questions

- Which numbering do Chronicle event scripts use for weapons: the banded 1-80 numbers the
  editor converts, or runtime IDs? The editor converts with `TransWepNo` on every item
  (`chronicle:ps2/src/edit.cpp:2174-2200`), which suggests scripts use 1-80. Verify in the
  script opcode code before relying on it.
- The meaning of `kind_flags` bits `0x1` and `0x2`, and of `use_flags` bits `0x100`, `0x1000`,
  `0x4000`, `0x10000`. Used in `menu_misc.cpp` and `itembombeffect.cpp` but not named in the header.
- The purpose of weapon option pairs `0x2/0x4` and `0x400/0x800`. Icons are drawn but the
  names are not in the source tree read here.
- Whether `buildup_mask1` bit 0 (position 20) is ever intended. It is never read (the code
  checks position 20 through `mask0`).
- Exact meaning of `WEAPON_DATA.unk_34` and `unk_36`, which sit between `exp_per_level` and `flags`.
- Whether the Mardan fish gate (5 and 15) counts fish held or fish ever caught
  (`chronicle:ps2/src/shop.cpp:5397-5430`).
- Whether any Chronicle weapon ever reaches `WepDataListToHaveCopy` with a legacy ID (the
  linear branch), which would make the Risks item above live rather than latent.
