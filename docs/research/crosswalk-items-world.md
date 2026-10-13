# Crosswalk: items, weapons, Atla and Georama parts, and the station catalogue

## What this covers

How each world stores and classifies its items, and where the two item systems line up. The DC1 side is the Chronicle decomposition (`chronicle:`), the DC2 side is the ChronicleTwo decomposition (`chronicletwo:`) at the ixion branch head. Data counts come from the PAL text tables that the games load at run time (`chronicletwo-data:` is `menu/cfg7/*.cfg`, `menu/*.lst`, `map/*.cfg`, `map/g/g0N/*.gpi`, `menu/dngmap/*.cfg`). Nothing was built or run. Counts were produced by parsing those files with awk/grep, and the parse rules were checked against the loaders' field order.

The covered topics are: weapon, attachment, dungeon-item and ridepod families; the Atla and Georama-part systems; inventions; gilda, shops and medals; keys and story items; and inventory containers. The last two sections give a proposed crosswalk structure and a draft station catalogue (every town, Georama site, dungeon and world-map place in both games, with floor counts and the internal IDs the code reveals). Inference is labelled. Existing notes in `docs/research/` (`c1-items-weapons.md`, `c1-dungeons.md`, `c2-dungeons.md`, `c1-towns-georama.md`, `c2-towns-georama.md`) were read first and their claims re-checked where this note depends on them.

## Key facts

### Item identity and tables

- DC1 has one `Item` enum: attachments 81-131 (unverified), dungeon items 132-255 (`ITEM_ALMIGHTY_PASS` = 255 is the last named one), weapons 257-376, end marker `ITEM_WEAPON_END` 377. `chronicle:ps2/include/itemdata.hpp:188-464`.
- DC1 `ComItemInfo[296]` maps every ID 81-376 to a kind, an index and a name message (`msg`, system message is `msg + 100`). `chronicle:ps2/src/itemdata.cpp:1832`; `chronicle:ps2/include/itemdata.hpp:511-519`.
- DC1 `WeaponList[120]` holds the weapon records (durability, attack, owner, six sockets, build-up masks). `chronicle:ps2/src/itemdata.cpp:1428`; `chronicle:ps2/include/itemdata.hpp:656-681`.
- DC1 weapons per owner are 42 Toan, 15 Xiao, 17 Goro, 16 Ruby, 16 Ungaga, 14 Osmond (sum 120). `chronicle:ps2/src/battlemenu.cpp:117-119`.
- DC1 `ITEM_LIST` is declared `[175]` and its first rows are `/* attach slot */` placeholders, so the 125-dungeon-item count is unverified; `AttachList` holds 50 explicit attachments (see the existing item note for the per-ID mapping). `chronicle:ps2/src/itemdata.cpp:1654-1830`, `:1551-1652`.
- DC1 item sort keys are NONE, FOOD, THROW, POWDER, QUEST, KEY_ITEM, GOODS, FISH, ROTTEN. `chronicle:ps2/include/itemdata.hpp:22-31`.
- DC2 has no single item enum. Items are defined by `menu/cfg7/comdat.cfg` (one `COM` row per item number, 423 rows, item numbers 1-428), and each family has its own file. `chronicletwo:ps2/src/gamedata.cpp:1173-1187`; `chronicletwo-data:menu/cfg7/comdat.cfg`.
- DC2 `CDataCommon` is 0x2C bytes and carries `type`, `list_no` (index into the family table), `icon_no`, `message_no`, `max_num`, `stack_num`, a 32-bit `attribute` (trash, spectol-transformable, bait, Georama material, usable, unique) and a name pointer. `chronicletwo:ps2/include/gamedata.hpp:299-316`; `chronicletwo:ps2/include/gamedata.hpp:182-189`.
- DC2 item numbers are not contiguous by family. Weapons span 1-387, costumes 111-267, attachments 175-383, fish 310-336, ridepod parts 135-421, the item family 172-428. Use the COM lookup, not range arithmetic. Counted from `comdat.cfg`.
- DC2 `ITEM_NO_MAX` is 0x200 (the conversion table size) and `ITEM_COMMON_DATA_MAX` is 432. `chronicletwo:ps2/include/gamedata.hpp:223-224`.
- DC2 `ITEM_DATA_TYPE` has type codes 0-35 (with gaps); `ConvertUsedItemType` folds them into 9 owned-item families (NONE, ITEM, ATTACH, WEAPON, COSTUME, ROBO_PART, FISH, GIFT_BOX, BOILED). `chronicletwo:ps2/include/gamedata.hpp:18-27`, `:139-175`; `chronicletwo:ps2/src/gamedata.cpp:1572-1597`.
- DC2 `ConvertUsedItemType` classes ridepod cores (type 11) as ITEM, not ROBO_PART, because of the test `item_type == ITEM_DATA_ROBO_CORE || item_type >= GEORAMA_MATERIAL` (`chronicletwo:ps2/src/gamedata.cpp:1585`). The 63 ridepod body/arm/leg/energy parts are ROBO_PART. Quirk, not an error the code notices.

### Family counts side by side (counted from data and checked against loader header counts)

| Owned-item family | DC1 (Chronicle) | DC2 (ChronicleTwo) |
|---|---|---|
| Weapon | 120 weapon records (IDs 257-376) | 112 (`WEPNUM 112`; types 1-4: Max melee 25, Max gun 19, Monica melee 49, Monica magic 19) |
| Attachment (elements, stats, gems, slayers, spheres) | 51 IDs (81-131); 50 explicit `AttachList` rows | 36 (`AT_INIT 36`; crystal 10, spectol 1, gem 14, coin 10, monster drop 1) |
| Ridepod part | none | 63 (`ROBOINIT 63`) plus 7 cores in the item family |
| Costume (clothes, hat, shoes, accessory, boots) | none | 34 (types 5-10) |
| Usable item, key item, dungeon key, material, etc. | 124 dungeon IDs (132-255; 256 is unnamed) | 158 in the item family, plus 1 gift box and 1 boiled-fish row in the item table (`ITEMINIT 160`) |
| Fish | 4 fish-sort items (`ITEM_SORT_FISH`) | 18 (`FISHINIT 18`) |
| Georama material (consumed) | none (Atla are placed, not consumed; see below) | 36 Georama materials (type 20, IDs 210-245) |
| Georama build unit | Atla plots (24 per town) and element chips | 86 distinct part kinds across the five towns (IDs 1-90, four gaps) |
| Invention recipe | none | 136 recipe rows, 128 distinct products |

Sources: DC1 `chronicle:ps2/include/itemdata.hpp:188-464`, `:22-31`, `chronicle:ps2/src/battlemenu.cpp:117-119`. DC2 `chronicletwo-data:menu/cfg7/*.cfg` (row counts), `chronicletwo:ps2/src/gamedata.cpp:1572-1597`. The DC2 family split is a count of the COM rows by type code.

### Weapons

- DC1 weapon owner chains are contiguous per character; chain position 0 is the broken default (`chronicle:ps2/src/battlemenu.cpp:117`). Owners carry these families (names from the `WeaponList` comments): Toan swords and daggers, Xiao slingshots, Goro hammers and axes, Ruby rings and armlets, Ungaga spears and sticks, Osmond guns and launchers. `chronicle:ps2/src/itemdata.cpp:1428-1549`.
- DC2 weapons are owned by Max (melee 25, guns 19) and Monica (swords 49, armbands 19). Type 1 includes the Fishing Rod (302) and Lure Rod (303), so fishing gear is a melee-family weapon in DC2 (`chronicletwo-data:menu/cfg7/comdat.cfg`; family codes at `chronicletwo:ps2/include/gamedata.hpp:139-143`).
- DC2 weapon base data (`CDataWeapon`, 0x4C bytes) holds durability, level-up experience, two status values and their limits, eight attribute values and limits, a 32-bit special-ability mask, `initial_fusion_point`, `fusion_point`, three build-up targets (item numbers) and three build-up monsters. `chronicletwo:ps2/include/gamedata.hpp:373-410`; loader `chronicletwo:ps2/src/gamedata.cpp:868-886`.
- DC2 build-up targets are item numbers, not chain positions. 92 distinct targets appear in `WEP_BUILD` rows; all are weapon-family items. 21 weapons have no target. Counted from `chronicletwo-data:menu/cfg7/wepdat.cfg` (unverified: not re-counted).
- DC2 owned weapons carry `WEAPON_USED` with a durability gauge and an absorption gauge (the weapon levels up when absorption fills), level up to 99, two status values, eight attributes and synthesis points (up to 999, or 9999 for a fishing rod). `chronicletwo:ps2/include/gamedata.hpp:580-600`.
- DC2 weapon element is the largest of attribute[0..3]; `GetActiveElem` returns the index and the magic effect table has four kinds. `chronicletwo:ps2/src/userdata.cpp:1662-1676`, `:951-994`; kinds `WEAPON_ELEMENT_FIRE`, `_COLD`, `_THUNDER`, `_WIND` at `chronicletwo:ps2/include/dng_effect.hpp:60-70`.
- DC1 weapon elements are five (fire, ice, thunder, wind, holy) on attachments and weapon records (`chronicle:ps2/include/itemdata.hpp:564-602`). DC2 has four weapon element slots but its thrown-item flags name five elements, including holy (`chronicletwo:ps2/include/gamedata.hpp:253-257`). Holy has no DC2 weapon element slot.
- Exact name matches between the two weapon lists (after lower-casing and removing punctuation) number 38. Examples: Baselard, Gladius, Kitchen Knife, Lamb's Sword, Dark Cloud, Atlamillia Sword, Chronicle Sword, Sword of Zeus, Star Breaker, Supernova. Counted with normalised names from `chronicle:ps2/src/itemdata.cpp:1428-1549` and `chronicletwo-data:menu/cfg7/comdatmes1.cfg` (unverified: not re-counted).
- Several name matches cross class boundaries and must not be used as equivalences: Flamingo (DC1 Xiao slingshot; DC2 Max melee, type 1), Frozen Tuna and Big Bucks Hammer (DC1 Goro hammers; DC2 Max melee), Angel Shooter (DC1 Xiao slingshot; DC2 Monica armband, type 4).

### Attachments, spheres and spectol

- DC1 attachment IDs: five elements 81-85 (fire, ice, thunder, wind, holy), synthesis sphere 90, stats 91-94 (attack, endurance, speed, magical power), gems 95-107 (Garnet to Sun), slayers 111-121, other 110. `chronicle:ps2/include/itemdata.hpp:189-229`.
- DC2 attachments: type 16 crystals (Flame, Chill, Lightning, Wind, Holy, Hunter, Destruction, Sea Dragon, Power, Protector), type 18 gems (14: Garnet through Turquoise, plus Sun Stone and Moon Stone), type 19 coins (10 special-ability coins), type 17 spectol (item 185), type 34 monster drop (item 383, `ITEM_ID_MONSTER_DROP`, `chronicletwo:ps2/include/gamedata.hpp:125`). `chronicletwo-data:menu/cfg7/comdat.cfg`; names from `comdatmes1.cfg`.
- Gem names match one to one: DC1 Garnet, Amethyst, Aquamarine, Diamond, Emerald, Pearl, Ruby, Peridot, Sapphire, Opal, Topaz, Turquoise match DC2 type-18 names (12 exact). DC1 Sun (107) is closest to DC2 Sun Stone. DC2 Moon Stone has no DC1 name. DC1 has 13 gem IDs (95-107), DC2 has 14 gem items.
- DC2 spectol (`SPECTOL_TYPE`) is the closest analogue of the DC1 synthesis sphere. Its source kinds are weapon at level 5 or more (parameters kept), attachments (multiplied by count), weapon below level 5 (one random parameter), and item or fish. `chronicletwo:ps2/include/userdata.hpp:215-222`. The level-5 threshold also appears in DC1 status break (`chronicle:ps2/src/weaponlevelup.cpp:448-530`) (unverified: that range has the 0.6 factor but no level-5 test; the DC2 level-5 threshold comes from the enum comment only).
- DC2 spectol converts an item to an attachment through `etcitem_spectol_table[0x1A9]`, with a row per item number. `chronicletwo:ps2/src/gamedata.cpp:17`; `chronicletwo:ps2/src/gamedata.cpp:1635-1653`.
- DC2 ATTACH_USED stores `spectol_type`, `spectol_value`, `spectol_item_no`, `level`, `special` and a 26-byte spectol name (`chronicletwo:ps2/include/gamedata.hpp:561-577`). DC1 sphere stores source weapon ID, source flags and level in `ATTACH_LIST` (`chronicle:ps2/include/itemdata.hpp:564-602`).

### Atla, geostones and Georama parts

- DC1 Atla are not items. They are floor objects with a row in `AtraAppearData[dungeon]` (`ATRA_APPEAR`: Atla ID, floor, count), registered per dungeon and floor into the save's atra grid. `chronicle:ps2/include/editpartsdata.hpp:51-58`; `chronicle:ps2/src/editpartsdata.cpp:300-405`; `chronicle:ps2/src/dungeonparts.cpp:1919-1980`.
- DC1 Atla table row counts are 78, 87, 71, 65, 56, 62 for dungeons 0-5 (419 rows total). IDs below 40 are plot parts (22, 21, 17, 17, 14, 12 rows) and IDs 40 and above are element chips (56, 66, 54, 48, 42, 50 rows). Counted from the table rows. There is no table for dungeon 6 (Demon Shaft). `chronicle:ps2/src/editpartsdata.cpp:403-405`.
- DC1 Atla pickup routes by dungeon index into the Georama of the same index: `AtraPartsGet(dungeon, plot)` for IDs below 40, `AtraChipGet(dungeon, id - 40)` otherwise. `chronicle:ps2/src/btmisc.cpp:238-246`.
- DC2 replaces Atla with geostones. A geostone is a floor object placed at setup when the floor carries the geostone flag and `GEOSTONE_FOUND` is clear. `chronicletwo:ps2/src/dng_event.cpp:1870-1895`; `chronicletwo:ps2/include/savedatadungeon.hpp:34-35`. Geostones are not inventory items in either game (no geostone entry in either item table).
- DC2 Georama parts are defined per town in `map/g/g0N/g0N<lang>.gpi` as `EDIT_PARTS` blocks with ID, name, attributes, `PARTS_MATERIAL` (item and count, up to several per part), `CPOINT`, `WEIGHT`, `GEO_STONE` (dungeon times 100 plus floor), `MAX_NUM`, `PAINT_NUM`, `PARTS_TYPE`, `MAP_NO`. `chronicletwo:ps2/src/editinfo.cpp:271-372`; `chronicletwo:ps2/include/editparts.hpp:87-133`.
- The part-definition block counts for language 0 are 56 (Sindain), 48 (Balance Valley), 49 (Veniccio), 52 (Heim Rada), 13 (Moon Flower). The `EDIT_PARTS_NUM` header overstates the count (57, 49, 50, 53, 58). Counted from `chronicletwo-data:map/g/g0N/g0N0.gpi`.
- Part IDs are one shared space (1-90 with gaps at 3, 55, 58, 84). Across the five towns, 86 IDs each carry one part name; no ID carries two different names. Counted from the same files.
- A Georama part is unlocked by its geostone. The Georama download-announcement builder `MakeDownLoadAnaunce` (`chronicletwo:ps2/src/editmenu.cpp:2324-2441`) reads `geo_stone / 100` as the dungeon and `% 100` as the floor. A part whose floor has `GEOSTONE_FOUND` clear is counted into the buildable table (`ok_table`); one whose floor has `GEOSTONE_FOUND` set and `GEOSTONE_READ` clear is announced (`chronicletwo:ps2/src/editmenu.cpp:2434-2445`). The first test is inverted relative to what the flag name suggests; confirm the flag meaning before relying on it.
- DC2 geostone links in the language-0 part files per dungeon: dungeon 1 (71 link lines), 2 (78), 3 (31), 4 (12), 5 (11); dungeons 0 and 6 have none. Counted from `GEO_STONE` lines.
- Building a DC2 part adds one copy to a stock counter: `build_parts_num[0x100]` in the save, capped at 9999 per index (`chronicletwo:ps2/include/savedata.hpp:230`; `chronicletwo:ps2/src/savedata.cpp:116-146`). Stock is added when a part is made (`chronicletwo:ps2/src/editmenu.cpp:3996`) and removed when one is placed or destroyed (`chronicletwo:ps2/src/editmode.cpp:1047`, `chronicletwo:ps2/src/editmenu.cpp:4685`). The material list the make screen reads is `PARTS_MATERIAL`.
- The Georama materials that DC2 parts consume are type-20 items 210-245 (36 items: Rolling Log, Sturdy Rock, Gunpowder, Holy Element, Paint colours and so on). `chronicletwo-data:menu/cfg7/comdatmes1.cfg`.

### Inventions (DC2 only)

- The invention recipes are `menu/inv6.lst` (136 `DATASET` rows, after one `DATATABLESET 136`). A row is: product item ID, three idea IDs, one to three (material item, count) pairs, one unknown short, then a model scale and three model position floats. `chronicletwo:ps2/src/inventmn.cpp:1771-1812`; `chronicletwo:ps2/include/inventmn.hpp:483-500`.
- 128 distinct products. Families: weapons 29, costumes 11, ridepod parts 63 (every ridepod part has one recipe), items 25 (recovery 9, throwing 4, powder 4, amulet 5, key item 1, gift box 1, aquarium 1). Counted from the DATASET rows.
- Ideas are photo IDs 1-295 (157 distinct used) and scoop IDs 1000 and up (32 distinct values above 295 are used; all fall in the scoop range as far as the rows show). `chronicletwo:ps2/include/inventmn.hpp:90-96`; `chronicletwo-data:menu/neta.lst`.
- The Camera (item 369) enables the invention menu. `chronicletwo:ps2/include/gamedata.hpp:123`.

### Gilda, shops and medals

- DC1 gilda is an unsigned 16-bit field (`money`, `chronicle:ps2/include/userstatus.hpp:110`). The battle item menu clamps at 0xFFFF (`chronicle:ps2/src/battlemenu.cpp:7657-7662`). Monster gilda drops are random items with `item_no == -1` (`chronicle:ps2/src/monstorunit.cpp:2250-2268`).
- DC2 money is an int kept between 0 and 999999 (`chronicletwo:ps2/src/userdata.cpp:4662`; `chronicletwo:ps2/include/userdata.hpp:1168`).
- DC2 medals (`yarikomi_medal`) are clamped 0-999 and are a shop currency mode (`chronicletwo:ps2/src/userdata.cpp:4299-4311`; `chronicletwo:ps2/src/menushop.cpp:489-509`). No DC1 medal analogue was found in the item enum.
- DC1 buy and sell prices are `PriceList[296]`, indexed by `id - 81`, s16 each. Weapon buy prices run 2 to 6500. `chronicle:ps2/src/shop.cpp:166`.
- DC2 shop prices are `PRICE` rows, one per item number (428 rows, five with no COM row). Weapons buy 0-3000 and sell 0-1500. Ridepod parts buy 0-1500 and cores buy 500-6500. Attachments buy up to 32000. Key items, dungeon keys and several family codes are not for sale (buy 0). Counted from `chronicletwo-data:menu/shoplst1.cfg`.
- DC2 shops are loaded per chapter, with eight chapter files and an English variant `shopusa<n>.cfg` when the language code is above zero. `chronicletwo:ps2/src/menushop.cpp:680-700`.

### Keys and story items

- DC1 gate keys by dungeon: Divine Beast Cave 195 (Dran's Crest), Wise Owl Forest one of 196, 198, 205 (random), Shipwreck 201 (Hook), Sun and Moon Temple 202 (King's Slate), Moon Sea 203 (Gun Powder), Gallery of Time 204 (Clock Hands), Demon Shaft 206 (Black Knight Crest). `chronicle:ps2/src/dungeonmap.cpp:3617-3644`.
- DC2 gate keys by dungeon index: 337, 339, 341, 342, 344, 348, 350. Door keys: 338, 340, none, 343, 346, 349, 351. Dungeon 4 (Mount Gundor) switches to Rope (345) and White Wind Vase (347) from floor 17. `chronicletwo:ps2/src/dng_event.cpp:57-59`, `:884-902`.
- DC2 dungeon keys are type 26 (15 items; the rows checked have stack 999). Story items are type 27 (33 items). `chronicletwo-data:menu/cfg7/comdat.cfg`.
- DC1 key and story items are sort keys QUEST and KEY_ITEM (`chronicle:ps2/include/itemdata.hpp:22-31`).

### Inventory containers

- DC1 dungeon inventory: `ITEM_PACK` holds 103 item slots and 3 quick-use slots (`chronicle:ps2/include/userstatus.hpp:43-62`); `consumable_items[43]` holds attachments; `chara_weapons[6][11]` holds owned weapons. `chronicle:ps2/include/userstatus.hpp:127-128`.
- DC2 inventory is `used_data[150]`: the item board (138 places, 144 when `SAVE_FLAG_ITEM_BOARD_EXPANDED` is set) followed by overflow places. `chronicletwo:ps2/include/userdata.hpp:1152`; `chronicletwo:ps2/src/userdata.cpp:3387-3398`.
- DC2 equipment is `equip[5]` per character (melee, sub, head, feet, clothes), `active_item[3]`, `parts[4]` (ridepod) and aquarium tanks (`chronicletwo:ps2/include/userdata.hpp:248-249`, `:280`, `:494-496`).

### Towns and dungeons

- DC1 Georama towns: five, `TOWN_NORUNE=0`, `TOWN_MATATAKI=1`, `TOWN_QUEENS=2`, `TOWN_MUSKA_LACKA=3`, `TOWN_YELLOW_DROPS=4` (`chronicle:ps2/include/editground.hpp:14-20`). Their MapNo is 0-4 and the data folder is `gedit/e0N` (`chronicle:ps2/src/editloop.cpp:722`).
- DC1 dungeons: seven, IDs 0-6 (`chronicle:ps2/include/dungeon.h:4-13`), entered at MapNo 200 + D (`chronicle:ps2/src/main.cpp:982-996`). Floor counts are 15, 17, 18, 18, 15, 25, 100 (`chronicle:ps2/src/menu_dungeon.cpp:100`).
- DC1 town-to-dungeon door arithmetic is `MapJump(NowEditMap + 0xC8)` (`chronicle:ps2/src/editloop.cpp:2030-2033`). For towns 0-4 this gives dungeons 0-4 (Norune to Divine Beast Cave, Matataki to Wise Owl Forest, Queens to Shipwreck, Muska Lacka to Sun and Moon Temple, Yellow Drops to Moon Sea), which matches the Dark Cloud wiki's location table (`docs/fandom/Dungeon.wiki`, Dungeons section).
- DC2 Georama towns: five, map numbers 0-4 (`g01` to `g05`), with world areas 2, 3, 4, 5 and 7 (`chronicletwo-data:map/map1.cfg`, `menu/1/wldmap.cfg`). Their analysis names are Sharlot, Stera, Benietio, Heim and Moon Flower (`chronicletwo:ps2/include/editanalyze.hpp:23-29`). The English titles are Sindain, Balance Valley, Veniccio, Heim Rada and Moon Flower Palace.
- DC2 future twins `f01` to `f04` (map numbers 25, 26, 82, 102) read Georama slots 0 to 3 through `PartsOnOff` (`chronicletwo:ps2/src/editloop.cpp:2835-2851`).
- DC2 dungeons: seven, index 0-6, map folders `d01` to `d07` (`chronicletwo:ps2/src/dng_main.cpp:345`, `:952-957`). Grid rooms per dungeon, counted from `chronicletwo-data:menu/dngmap/dmap0..6.cfg`, are 9, 16, 24, 21, 23, 28, 39 (160 total). Save and menu ceilings are 9, 16, 25, 21, 23, 29, 39 (`chronicletwo:ps2/src/savedatadungeon.cpp:13`) and 8, 15, 24, 20, 22, 28, 38 max ids (`chronicletwo:ps2/src/dngmenu.cpp:2767-2768`).
- DC2 dungeon names (English) from the fandom Dark Chronicle table: Underground Channel, Rainbow Butterfly Wood, Starlight Canyon, Ocean's Roar Cave, Mount Gundor, Moon Flower Palace, Zelmite Mine. The dungeon-to-area mapping is in the world-map POS rows (see the catalogue).
- DC2 world map: 30 `POS` rows and nine `AREA` rows (`chronicletwo-data:menu/1/wldmap.cfg`). Ten POS rows have loop 2 (dungeon). Parser `chronicletwo:ps2/src/menumap.cpp:298-325`.
- DC2 map table: 189 records in `map/map1.cfg` (English titles) and `map/map0.cfg`, read positionally (`chronicletwo:ps2/src/mapselect.cpp:277-294`). The map number is the record index.
- DC2 map types (`MapType`): 1 Georama, 2 Georama interior, 4 interior, 5 future, 6 future interior (`chronicletwo:ps2/include/mapselect.hpp:43-49`). Types 3, 7 and 8 are used in the table but are not named in the enum. Type 7 rows are dungeon floor maps (`d0Nf..`), type 8 rows are dungeon side and boss rooms (`d0Nb..`, and some s-series), type 3 covers ordinary exteriors and stations (inference from names).
- DC2 train add-on: maps whose asset field is `trn/train` (s01, s02, s04, s09, s10, i02h01) and maps already written as `trn2/s36` (s11, s12, s31, s34, s53, s58, s71). The loader rewrites `trn/train` to `trn2/s36` only for chapters 6 and 7 (`chronicletwo:ps2/src/mapjump.cpp:296-318`).

## How it works

### 1. What "the same item" means across the two games

Neither game has a shared item identity. Each item is one row in its own table. Crossing an item means choosing a relation between two rows, and the relation kind matters as much as the target:

- **Equivalent**: same role and same numbers (for example, a DC1 gem and a DC2 gem of the same name).
- **Analogue**: same role but different mechanics (a DC1 synthesis sphere and a DC2 spectol; both gate on a weapon at level 5 (the DC1 gate is unverified) and carry its stats forward, at different rates: DC1 sphere keeps about 60%; DC2 spectol keeps a weapon's parameters when the weapon is at level 5 or more, and gives one random parameter below that).
- **Class-only**: same weapon or item family but no named match (Max's melee weapons and Goro's hammers and Ungaga's sticks).
- **None**: no counterpart in the other world (DC2 ridepod parts and costumes; DC1 Atla as items).

The design draft already assumes per-world IDs with a canonical key (`chronicletwo:ixion/docs/DESIGN.md:188`, Items row of the save table). This note supplies the crosswalk rows that the draft leaves open.

### 2. Proposed crosswalk structure

Canonical record (one per crossing-relevant item):

- `key`: `<world>:<native id>`, for example `c1:258` (Toan's Dagger, chain position 1) or `c2:12` (Flamingo). The world prefix is required because the number spaces overlap (DC1 1-376, DC2 1-428, both interleaved).
- `world`, `native_id`, `native_family` (the DC1 `ComItemInfo.kind` or the DC2 `ConvertUsedItemType` family).
- `ixion_class`: one of WEAPON, ATTACHMENT_ELEMENT, ATTACHMENT_STAT, ATTACHMENT_GEM, ATTACHMENT_SLAYER, ATTACHMENT_SPHERE (DC1) or SPECTOL (DC2), ATTACHMENT_OTHER, CONSUMABLE, KEY_ITEM, GATE_KEY, DOOR_KEY, MATERIAL, RIDEPOD_PART, RIDEPOD_CORE, COSTUME, FISH, LURE, FISHING_ROD, BOILED_FISH, GIFT_BOX, AQUARIUM, MONSTER_DROP, BADGE_BOX, ATLA (DC1 only; not an item), GEOSTONE (DC2 only; not an item).
- `owner_set`: DC1 weapon owner (Toan, Xiao, Goro, Ruby, Ungaga, Osmond), DC2 user (Max, Monica, robo).
- `stack`: DC1 `stack_kind` / DC2 `stack_num`; `max_num`.
- `price`: buy and sell (DC1 `PriceList`, DC2 `PRICE`).
- `effect`: DC1 `use_flags`/`kind_flags` or DC2 `USEITEM_EFFECT` (use, action, target, three values).
- `name_key`: DC1 `ComItemInfo.msg` (+100 for the system message) or DC2 `message_no` with the language file.
- `relation`: `EQUIV | ANALOG | CLASS | NONE`, with `target` (the other world's key), `confidence` (verified | name-only | inference), and `note`.

Pair table: one row per DC1 item that has a candidate DC2 counterpart, plus one row per DC2 item with no DC1 counterpart. The first pass can be seeded from the name matches (38 weapon names, 12 exact gem names, and the five element crystals) and the class map (section 3), and must be verified by a person against the in-game names before use.

Carry rules (proposal, consistent with `chronicletwo:ixion/docs/DESIGN.md:188-235`):

- Weapons: carry through a loaner (class map) or through a sphere/spectol (one-way); never copy the model.
- Attachments: element and gem attachments map by name (EQUIV); stat and slayer attachments are CLASS only; DC2 coins and DC2 monster drop are NONE.
- Consumables and key items: carry by EQUIV where the name matches; otherwise cargo.
- Gate and door keys: do not carry (proposal). Keys are dungeon-keyed (section 5), so an Ixion gate key should be a dungeon-keyed rule, not an item rule.
- Atla and geostones: stay local (`chronicletwo:ixion/docs/DESIGN.md:188`). Both are floor objects that feed Georama; they are a parallel system, not items.
- Georama parts: local to the town; stock counts (`build_parts_num`) are per save and can be shared across towns because part IDs are one space.
- Gilda: one canonical pool (DESIGN section 4.3). DC1 cap 65535 (or 0xFFFF clamp), DC2 cap 999999.

### 3. Class map (weapons)

| Ixion class | DC1 owner families (count) | DC2 families (count) | Relation |
|---|---|---|---|
| Sword and dagger | Toan (42) | Monica melee (49) | CLASS; several exact name matches (see Key facts) |
| Hammer, axe, stick, spear, wrench | Goro hammers (17), Ungaga sticks and spears (16) | Max melee (25; two of them are fishing rods and one is a wrench) | CLASS (inference) |
| Gun and launcher | Osmond (14) | Max gun (19) | CLASS |
| Slingshot | Xiao (15) | none (Max guns cover the ranged slot) | CLASS (inference; DC2 has no slingshot family) |
| Ring, armlet, armband (magic) | Ruby (16) | Monica magic (19) | CLASS (inference) |
| Fishing rod | none (dungeon item 185) | Fishing Rod (302), Lure Rod (303) | NONE for combat use |

The class map is the same shape as `chronicletwo:ixion/docs/DESIGN.md:211-218` but covers both full lists and not only the Max melee rows.

### 4. Atla, geostones and Georama parts

Both worlds turn a dungeon floor into Georama progress through a floor object, not an item. The parallel:

| Concept | DC1 (Chronicle) | DC2 (ChronicleTwo) |
|---|---|---|
| Floor object | Atla (table row per dungeon) | Geostone (one per flagged floor) |
| Acquire | `AtraPartsGet` / `AtraChipGet` into the Georama of the dungeon's index | `GEOSTONE_FOUND` bit and `GEOSTONE_READ` bit |
| Unlock | Plot (24 per town) and element chip slot | Part kind whose `GEO_STONE` names the floor |
| Build | Place on the board (no consumption) | Spend materials (`PARTS_MATERIAL`) from the stock counter |
| Scope | Per dungeon index = per Georama index | Per dungeon floor; parts appear in any town whose file names that floor |

This suggests the Ixion station can treat both as one "floor-to-Georama" event with two codecs, not as items (inference from the code shape; both designs keep the object out of the inventory).

### 5. Key items and dungeon keys

DC2 has a dungeon-keyed gate and door key system: the key for dungeon D (and for floors 17 and up of dungeon 4) comes from a fixed table (see Key facts, "Keys and story items"). DC1 has a dungeon-keyed gate system with random selection on one dungeon (Wise Owl Forest). An Ixion gate rule should be keyed by `(world, dungeon, floor)` and resolve to each world's native key, not translate key items one to one.

### 6. Station catalogue (draft)

Internal IDs are the native ones the code reveals. Floor counts are menu or grid counts (see the notes). Town-level places have no floors and show "n/a".

#### 6a. Towns and Georama sites

| Ixion key (proposed) | World | Name (English) | Native ID | Georama or future twin | World-map place | Floors | Notes |
|---|---|---|---|---|---|---|---|
| c1.town.norune | DC1 | Norune Village | MapNo 0 (`gedit/e01`), Georama 0 | Georama 0 | WORLD_PLACE_NORUNE 0 | n/a | First town; door to dungeon 0 |
| c1.town.matataki | DC1 | Matataki Village | MapNo 1 (`gedit/e02`), Georama 1 | Georama 1 | WORLD_PLACE_MATATAKI 2 | n/a | Door to dungeon 1 |
| c1.town.queens | DC1 | Queens | MapNo 2 (`gedit/e03`), Georama 2 | Georama 2 | WORLD_PLACE_QUEENS 5 | n/a | Door to dungeon 2 |
| c1.town.muska_lacka | DC1 | Muska Lacka | MapNo 3 (`gedit/e04`), Georama 3 | Georama 3 | WORLD_PLACE_MUSKA_LACKA 7 | n/a | Door to dungeon 3 |
| c1.town.yellow_drops | DC1 | Yellow Drops | MapNo 4 (`gedit/e05`), Georama 4 | Georama 4 | WORLD_PLACE_YELLOW_DROPS 11 | n/a | Door to dungeon 4 |
| c2.town.sindain | DC2 | Sindain (analysis: Sharlot) | map 0 `g01` | Georama 0; future `f01` (map 25) | POS 4 (area 2) | n/a | Georama parts 56 (lang 0) |
| c2.town.balance_valley | DC2 | Balance Valley (Stera) | map 1 `g02` | Georama 1; future `f02` (map 26) | POS 9 (area 3) | n/a | Parts 48; `LoadGeoNPC` walk |
| c2.town.veniccio | DC2 | Veniccio (Benietio) | map 2 `g03` | Georama 2; future `f03` (map 82) | POS 15 (area 4) | n/a | Parts 49 |
| c2.town.heim_rada | DC2 | Heim Rada (Heim) | map 3 `g04` | Georama 3; future `f04` (map 102) | POS 20 (area 5) | n/a | Parts 52; fire burns parts on exit |
| c2.town.moon_flower | DC2 | Moon Flower Palace (Moon Flower) | map 4 `g05` | Georama 4; no future twin | POS 25 (area 7) | n/a | Parts 13 (fewest) |
| c2.town.palm_brinks | DC2 | Palm Brinks (hub) | map 10 `m01` | none (area 1 hub) | POS 0 (area 1) | n/a | Sub maps m02-m05 (11-14), m06-m08 (17, 19, 20) |
| c2.place.station_m02 | DC2 | Palm Brinks Station | map 11 `m02` | none | not in POS | n/a | Palm Brinks sub map |
| c2.place.kazarov | DC2 | Kazarov Stonehenge | map 103 `s11` | none | POS 24 (area 6) | n/a | Train add-on `trn2/s36` |
| c2.place.griffon | DC2 | Griffon's Castle area | map 77 `s33`, map 76 `s31` | none | POS 28, 29 (area 8) | n/a | Area is Griffon's Castle |

Future maps (type 5) that twin a Georama: `f01` Jurak Mall (25), `f02` Starlight Temple (26), `f03` Luna Lab (82), `f04` Gundorada Workshop (102). Counted from `chronicletwo-data:map/map1.cfg`.

DC1 field places in the world map (not towns): `s04` (MapNo 14), `s13` (23), `s30` (40), `s32` (42), counted in the place table. DC1 Demon Shaft is MapNo 60 (sub map `s50`). `chronicle:ps2/src/battlemenu.cpp:8771`; `chronicle:ps2/src/editloop.cpp:728-734`.

#### 6b. Dungeons

| Ixion key (proposed) | World | Dungeon name | Native ID | Entry | Floors (count) | Gate key | Notes |
|---|---|---|---|---|---|---|---|
| c1.dng.0 | DC1 | Divine Beast Cave | D 0, MapNo 200 | Norune (town 0) and place 1 | 15 | 195 Dran's Crest | exit MapNo 0 |
| c1.dng.1 | DC1 | Wise Owl Forest | D 1, MapNo 201 | Matataki and place 3 | 17 | 196, 198 or 205 (random) | exit MapNo 1 |
| c1.dng.2 | DC1 | Shipwreck | D 2, MapNo 202 | Queens and place 6 | 18 | 201 Hook | exit MapNo 19 (`s09`) |
| c1.dng.3 | DC1 | Sun and Moon Temple | D 3, MapNo 203 | Muska Lacka and place 9 | 18 | 202 King's Slate | exit MapNo 42 (`s32`) |
| c1.dng.4 | DC1 | Moon Sea | D 4, MapNo 204 | Yellow Drops and place 12 | 15 | 203 Gun Powder | exit MapNo 23 (`s13`) |
| c1.dng.5 | DC1 | Gallery of Time (Dark Heaven Castle) | D 5, MapNo 205 | place 14 | 25 | 204 Clock Hands | exit MapNo 38 (`s28`) |
| c1.dng.6 | DC1 | Demon Shaft | D 6, sub map MapNo 60 (`s50`) | place 15 | 100 (menu cap) | 206 Black Knight Crest | no Atla table |
| c2.dng.0 | DC2 | Underground Channel | dungeon 0, `d01` | Palm Brinks (POS 2) | 9 rooms (save 9) | 337 Key Handle | exit room 8; boss room |
| c2.dng.1 | DC2 | Rainbow Butterfly Wood | dungeon 1, `d02` | Sindain (POS 6) | 16 (save 16) | 339 Fairy Saw | boss room; floor 100 special |
| c2.dng.2 | DC2 | Starlight Canyon | dungeon 2, `d03` | Balance Valley (POS 11; direct POS 12 floor 18, POS 13 floor 8) | 24 rooms (save 25) | 341 Giant Meat | no boss room; floor 8 self-answers |
| c2.dng.3 | DC2 | Ocean's Roar Cave | dungeon 3, `d04` | Veniccio (POS 17; direct POS 18 floor 9) | 21 (save 21) | 342 Luna Stone | boss room |
| c2.dng.4 | DC2 | Mount Gundor | dungeon 4, `d05` | Heim Rada (POS 22) | 23 (save 23) | 344 Magma Rock, then 345 Rope from floor 17 | boss room |
| c2.dng.5 | DC2 | Moon Flower Palace | dungeon 5, `d06` | Moon Flower Palace area (POS 27) | 28 rooms (save 29) | 348 Queen's Watering Pot | boss room |
| c2.dng.6 | DC2 | Zelmite Mine | dungeon 6, `d07` | Palm Brinks area (POS 3) | 39 (save 39) | 350 Trolley Oil | boss room; no geostones |

DC1 floor counts are from `menu_dungeon.cpp:100`. DC2 room counts are from the tree-map RI rows; save ceilings from `savedatadungeon.cpp:13`. DC2 floor-map folders per dungeon, counted from the English map table (`map/map1.cfg`): `d01` has `f01`, `f02`, `b01`, `e01` (entry); `d02` has `f01` with variants `f01r` and `f01s`, and `b01`, `b02`, `b03`; `d03` has `f01`, `f01r`, `f02`, `f02r`, `f02s`, `f03`, `f03r` and `b01`, `b02`; `d04` has `f00`, `f01`, `f01s`, `f02`, `f02r`, `b01`; `d05` has `f01`, `f01r`, `f01s`, `f02`, `b01`; `d06` has `f01`-`f03`, `b01`-`b03`, `e01`; `d07` has `f01`, `b01`. The `r` and `s` suffixes are not explained in code (open question).

#### 6c. Stations (train stops and train-add-on maps)

DC2 has the train add-on on maps whose asset field is `trn/train` or `trn2/s36`. The loader rewrites `trn/train` to `trn2/s36` only for chapters 6 and 7 (`chronicletwo:ps2/src/mapjump.cpp:296-318`). Counted from `chronicletwo-data:map/map1.cfg`.

| Map | Title | Asset | In world map POS? |
|---|---|---|---|
| s01 (15) | Channel Reservoir | trn/train | no |
| s02 (16) | Sindain Station | trn/train | POS 5 |
| i02h01 (34) | Station (Palm Brinks) | trn/train | POS 1 |
| s04 (54) | Balance Valley Station | trn/train | POS 10 |
| s09 (83) | Veniccio Station | trn/train | POS 16 |
| s10 (87) | Heim Rada Stop | trn/train | POS 21 |
| s11 (103) | Kazarov Stonehenge | trn2/s36 | POS 24 |
| s12 (72) | Moon Flower Palace Stop | trn2/s36 | POS 26 |
| s31 (76) | Moon Flower Palace Stop | trn2/s36 | POS 29 |
| s34 (155) | Moon Flower Palace Stop | trn2/s36 | no |
| s53 (131) | Central Lab (Event) | trn2/s36 | no |
| s58 (158) | Subdimension | trn2/s36 | no |
| s71 (188) | Moon Flower Palace Stop | trn2/s36 | no |

Maps s36 (106, "Ixion (Outer)"), s37 (108, "Ixion (Engine Room)") and s38 (120, "Ixion (Guest Room)") carry Ixion names in the English table (`chronicletwo-data:map/map1.cfg`). Reading them as the train's own interior is inference from the names; the code does not name them.

#### 6d. World-map places (the place table both games expose)

DC1: 16 places (`WorldMapPlace` enum, `chronicle:ps2/include/battlemenu.hpp:281-297`), mapped by `MenuGrobalMapNoTbl` (`chronicle:ps2/src/battlemenu.cpp:8771`). Field places are MapNo 14, 23, 40, 42 (s04, s13, s30, s32); Demon Shaft is 60.

DC2: 30 places (`chronicletwo-data:menu/1/wldmap.cfg`, POS rows). Loop 1 is a town or editor map; loop 2 is a dungeon (`chronicletwo:ps2/include/mainloop.hpp:32-35`). Full list is in the POS index: 0 Palm Brinks (10), 1 Station (34), 2 Underground Channel (55, dng 0), 3 Zelmite Mine (160, dng 6), 4 Sindain (0), 5 Sindain Station (16), 6 Rainbow Butterfly Wood (57, dng 1), 7 Fish Monster Swamp (65), 8 Jurak Mall (25), 9 Balance Valley (1), 10 Balance Valley Station (54), 11 Starlight Canyon (58, dng 2), 12 Yorda's Valley (98, dng 2 floor 18), 13 Barga's Valley (81, dng 2 floor 8), 14 Starlight Temple (26), 15 Veniccio (2), 16 Veniccio Station (83), 17 Ocean's Roar Cave (64, dng 3), 18 Cave of Ancient Murals (84, dng 3 floor 9), 19 Luna Lab (82), 20 Heim Rada (3), 21 Heim Rada Stop (87), 22 Mount Gundor (79, dng 4), 23 Gundorada Workshop (102), 24 Kazarov Stonehenge (103), 25 Moon Flower Palace (4), 26 Moon Flower Palace Stop (72), 27 Moon Flower Palace (97, dng 5), 28 Moon Flower Palace (77; area Griffon's Castle), 29 Moon Flower Palace Stop (76; area Griffon's Castle).

Field order in each POS row is index, map number, loop, area, dungeon, floor, reachable flag, icon type (`chronicletwo:ps2/src/menumap.cpp:298-325`). The flag is an event bit (`CheckBitFlagMenu`, `chronicletwo:ps2/src/menumap.cpp:309`).

## Ixion hooks

- **Crosswalk file.** Add a pair table keyed by `world:native_id` with the relation kind and confidence (section 2). The first seed is the 38 weapon name matches, the 12 exact gem matches and the five element crystals, filtered by the class map. This is data, not code, so it fits the design's translation-table idea (`chronicletwo:ixion/docs/DESIGN.md:236-248`).
- **Weapon routing.** The owner byte decides which character can carry a DC1 weapon (`WeaponList[].owner`) and the DC2 `ConvertUsedItemType` family decides the slot. A crossing that inserts a DC2 item into a DC1 `chara_weapons` slot must set the owner byte, or the item will be routed to the wrong character. The routing at `chronicle:ps2/src/dngstatusdata.cpp:431` reads `ItemPutListTbl12_bytes[750 + item_id * 76]`, not `WeaponList[].owner`, so the owner-byte rule is unverified.
- **Spectol as sphere analogue.** For a DC1 weapon crossing into DC2, a sphere-type result can use the spectol source kinds (weapon at level 5 or more keeps parameters). For a DC2 spectol crossing into DC1, the `SPECTOL_TYPE_WEAPON` path is the closest DC2 source of a carried weapon's stats. The 60% factor is DC1's sphere rule (`chronicle:ps2/src/weaponlevelup.cpp:448-530`), not a DC2 rule (`chronicletwo:ps2/include/userdata.hpp:215-222`). Which rate a crossing uses is a design choice (inference).
- **Gate keys by dungeon.** Resolve a gate key from `(world, dungeon, floor)` with `GetGateKeyIndex` (DC2, `chronicletwo:ps2/src/dng_event.cpp:889`) or `gate_key_no` (DC1, `chronicle:ps2/src/dungeonmap.cpp:3617`), not from the item the player carries.
- **Atla and geostone event.** Hook the Georama unlock rather than the item system. DC1: `AtraPartsGet`/`AtraChipGet` (`chronicle:ps2/src/btmisc.cpp:238-246`). DC2: `GEOSTONE_FOUND` and the `geo_stone` link (`chronicletwo:ps2/src/editmenu.cpp:2434-2440`).
- **Station catalogue as data.** Use the POS rows (DC2) and `MenuGrobalMapNoTbl` (DC1) as the single travel graph. Add Ixion places as POS rows with a map number, loop, area and flag (`chronicletwo:ps2/include/menumap.hpp:117-128`).
- **Invention recipes as cross-world sources.** The 136 recipes are the largest DC2 item-to-item map. A recipe's product can be a crossing candidate when its three ideas are in the player's photos or idea notebook (the check is `CheckInventItem`, `chronicletwo:ps2/src/inventmn.cpp:1838-1883`).
- **Gilda and medals.** Canonical gilda pool at 999999 with a 65535 DC1 display clamp (DESIGN section 4.3). Medals are a DC2 currency with a shop mode; a DC1 shop has no medal mode, so medals stay DC2-local.

## Risks and blockers

- **Namespace overlap.** DC1 item IDs 1-376 and DC2 item IDs 1-428 overlap numerically and are interleaved. A crosswalk keyed on the bare number silently routes the wrong item. Always carry the world prefix.
- **Legacy DC1 weapon aliases.** DC1 has two mappings for legacy IDs 21-80 (banded `TransWepNo` and the linear `+256` in `GetCommonItemInfo`), which disagree. The existing item note has the detail (`chronicle:ps2/src/itemdata.cpp:2144-2146`). Any Ixion path that feeds legacy DC1 IDs to the accessors gets a wrong weapon.
- **Name matches are not class matches.** Some of the 38 exact weapon-name matches cross classes (Flamingo, Frozen Tuna, Big Bucks Hammer, Angel Shooter). A name seed must be checked against the class map before it is used.
- **DC2 weapon elements are four, DC1 are five.** Holy has no DC2 weapon element. A holy DC1 weapon crossing has no element to carry and needs a rule (for example, carry the slot and drop it, or map to the DC2 holy flag `WEAPON_SPECIAL_HOLY_WATER`, `chronicletwo:ps2/include/gamedata.hpp:46-70`).
- **Geostones are not items.** The design draft's "Geostone items stay local" (`chronicletwo:ixion/docs/DESIGN.md:188`) is a floor flag in code. Treat it as a floor event, not a row in the item crosswalk.
- **Demon Shaft has no Atla table and no door route.** DC1 `AtraAppearData` has six tables (dungeons 0-5). Demon Shaft's world-map entry is MapNo 60 (sub map `s50`). The town-door arithmetic `NowEditMap + 0xC8` reaches dungeons 0-4 only, for towns 0-4 (`chronicle:ps2/src/editloop.cpp:2030-2033`).
- **Moon Flower Georama has 13 part blocks.** The other four towns have 48 to 56. The `EDIT_PARTS_NUM` header says 58. Moon Flower may be incomplete in the data, or the header is an allocation size. Confirm before using Moon Flower as a build target.
- **Georama part stock is one space.** Because part IDs are shared across towns, `build_parts_num` is one counter for all towns. A part stock from one town can be spent in another. The names agree for every shared ID, so one shared counter may be intended (inference). Any Ixion change to town-local stock must split the counter.
- **Ridepod cores are typed as items.** `ConvertUsedItemType` puts type 11 in the ITEM family. Any crosswalk that filters "ridepod part" by family misses the cores.
- **Gift box and boiled fish share the item table.** Both are accepted by `GetItemData` alongside the ITEM family (`chronicletwo:ps2/src/gamedata.cpp:1317`), so they count toward the 160 ITEMINIT rows.
- **Shop lists differ by chapter.** `shoplst1..8.cfg` are chapter lists, not one catalogue. A crosswalk price must be read at a stated chapter.
- **Gilda on DC1 is 16-bit.** The design draft notes a signed view that could read values above 32767 as negative (`chronicle:ps2/include/userstatus.hpp:110-111`). Verify before fixing the 65535 clamp.
- **Positional map numbers in DC2.** The map table is read by record order (`chronicletwo:ps2/src/mapselect.cpp:277-294`). Inserting a record shifts later numbers. Key DC2 stations by folder name (`s11`, `d03f01`), not by the number.
- **DC2 dungeon 2 floor 24 and dungeon 5 floor 28.** The menu maximum IDs for these two dungeons are 24 and 28 (`chronicletwo:ps2/src/dngmenu.cpp:2767-2768`), which equal the room counts in section 6b rather than one less as in the other five dungeons. The earlier "one more than the RI row count" wording is unverified; check the RI rows before an Ixion floor table carries or drops the extra ID.

## Open questions

- Which character owns each DC2 weapon? The type codes (`ITEM_DATA_MAX_MELEE`, `ITEM_DATA_MONICA_MAGIC` and so on, `chronicletwo:ps2/include/gamedata.hpp:139-175`) give the owner, but the Max/Monica split in this note is inferred from the English names and should be checked against the in-game equip rules (`CheckItemEquip`, `chronicletwo:ps2/src/gamedata.cpp:1792`).
- What do the eight `GRD` values per costume mean? The table covers exactly the costume families (types 5-10) and is loaded as a guard table (`chronicletwo:ps2/src/gamedata.cpp:1096-1100`). Probably defence or resistances (inference).
- Does the DC1 `ATRA_APPEAR.count` field (how many floors a row is put on when the floor is not fixed) give the number of Atla placed per playthrough? The row totals (419) are not the placement totals.
- Which DC2 floors carry a geostone flag and which floors carry the `r` or `s` variants? The parallel in section 4 is structural only; no code links the two sets.
- What is the `unk_3` byte of `INVENT_MATERIAL` (after the count)? The parser never writes it (`chronicletwo:ps2/include/inventmn.hpp:435-446`, `chronicletwo:ps2/src/inventmn.cpp:1771-1812`).
- Which dungeon floor-map suffixes `r` and `s` select a variant? Both `d02f01r` and `d02f01s` exist, `d03f02r` and `d03f02s` exist, but `d03f01s` does not. Not explained in code or data.
- Does any DC1 town or dungeon path reach Demon Shaft through the door arithmetic, or only through the world map? The world map is the only verified route.
- Does the DC2 `GetItemBoardMaxNum` expansion flag (`SAVE_FLAG_ITEM_BOARD_EXPANDED`) have a fixed unlock event? Not traced.
- Are the DC2 chapter shop files (`shoplst`/`shopusa`) identical in item identity across chapters, or do chapter files reuse IDs with different prices? Not compared.
