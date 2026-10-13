# DC1 extracted data catalogue (Dark Cloud, PAL data tree)

## What this covers

A catalogue of the extracted Dark Cloud (DC1) data tree that the Chronicle PC port reads at runtime. It covers:

- the top-level layout and per-directory counts,
- file formats identified by magic bytes and the DCExtractor specifications,
- the naming conventions that tie file names to characters, towns, fields, dungeons, bosses and monsters,
- a join table from each playable character, town, field, dungeon, boss, monster and key model to its data files,
- the Chronicle code that opens those paths, so each mapping is backed by a call site.

Scope limits: this is read-only analysis of the extracted tree, the Chronicle source, the DCExtractor format notes and the pulled wiki pages. No builds, no game runs, no text decoding of `.mes` message files. Community names come from the fandom pages and are labelled as such. Short Japanese place names were recovered by decoding the cp932 comment headers of the `.cfg` files; only the short phrases are cited.

Citation keys used below: `data:<path>` is the extracted DC1 tree (relative to its root). `chronicle:<path>:<line>` is the Chronicle repository (`ps2/` = original game units, `port/` = PC overrides). `refs/DCExtractor/...` is the format reference. `fandom:<page>` is the pulled wiki set.

## Key facts

- **Tree size and shape.** 5,425 files, about 1.8 GB, 18 top-level directories plus loose root files (`data:` root). Largest: `gedit/` 2,181 files / 840 MB; `commenu/` 821 / 362 MB; `dun/` 1,403 / 252 MB; `sound/` 259 / 105 MB; `opdat/` 301 / 78 MB (directory walk).
- **Language and region.** This is the PAL disc. The symbol maps for PAL and NTSC differ (`chronicle:ps2/config/pal/dun.symbols.txt:5114` vs `chronicle:ps2/config/ntsc/dun.symbols.txt:5088` for `BtEnemyLayoutList`). Do not mix NTSC data into this tree.
- **Case and index.** The tree has no uppercase names. The port indexes the tree with case-folded keys and checks the `data.hd2` index against it (`chronicle:port/src/dataread.cpp:46-47`, `:133`).
- **Six playable characters.** `enum Character` with `CHARA_TOAN = 0`, `CHARA_XIAO = 1`, `CHARA_GORO = 2`, `CHARA_RUBY = 3`, `CHARA_UNGAGA = 4`, `CHARA_OSMOND = 5` (`chronicle:ps2/include/itemdata.hpp:485-491`). The party model files, in the same order, are `dun/mainchara/c01d.chr`, `c04b.chr`, `c06b.chr`, `c05a.chr`, `c10b.chr`, `c18a.chr` (`chronicle:ps2/src/btitem.cpp:55-58`).
- **Chr name is not always the model name.** `data:dun/mainchara/c06b.chr` contains `c06a.mds` (Goro); `c10b.chr` contains `c10a.mds` (Ungaga). Use the pack's own entries, not the file name, to find the model.
- **Weapon packs** are `dun/mainchara/c01w.pac`, `c04w.pac`, `c06w.pac`, `c05w.pac`, `c10w.pac`, `c18w.pac` (prefix table at `chronicle:ps2/src/btmisc.cpp:108`). The pac holds per-weapon `cNNwMM.chr` entries (c01w has `c01w00`..`c01w19`).
- **Voices** are `sound/voice/voice0.snd`..`voice5.snd` for Toan, Xiao, Goro, Ruby, Ungaga, Osmond. Their internal entry names are `toan_s`, `syao_s`, `goro_s`, `ruby_s`, `unga_s`, `ozmd_s`. `voice6.snd` holds `turi_s` (role not verified). Selected by `UserStatus->cur_chara` (`chronicle:ps2/src/btitem.cpp:123`; `chronicle:ps2/src/snd.cpp:1378-1384`).
- **Shadow/kage icons** are root `commenu/kagetoan.img`, `kagesyao`, `kagegoro`, `kageruby`, `kageunga`, `kageozu`, in party order (`chronicle:ps2/src/battlemenu.cpp:3177`).
- **Menu model packs** are `commenu/dungeon/c01model.pak`..`c06model.pak`, indexed by `chara+1`, not by chr ID. c01model holds `c01d.mds` (Toan); c02model holds `c04b.mds` (Xiao); c03model holds `c06a.mds` (Goro); c04model holds `c05astat.*` (Ruby); c05model holds `c10astat.*` (Ungaga); c06model holds `c18a.mds` (Osmond) (`chronicle:ps2/src/menu_misc.cpp:1038`; pack entries from `data:commenu/dungeon/`).
- **Towns** are `gedit/e01`..`gedit/e05`: Norune Village, Matataki Village, Queens, Muska Lacka, and Yellow Drops. Evidence: `TOWN_*` enum (`chronicle:ps2/include/editground.hpp:14-21`), `TownOrDngPos` (`chronicle:ps2/src/battlemenu.cpp:8772-8788`), and the decoded Japanese `mapinfo.cfg` headers for e01-e04 (`data:gedit/e01/mapinfo.cfg` etc.). The e05 header has no name; its identity is inferred from `TownOrDngPos` index 11 (`WORLD_PLACE_YELLOW_DROPS`).
- **Dungeons** are seven indices, `DUNGEON_DIVINE_BEAST_CAVE=0` .. `DUNGEON_DEMON_SHAFT=6` (`chronicle:ps2/include/dungeon.h:7-15`), with map prefixes `d01`..`d07`. The decoded `dun/d0N*.cfg` headers name each one (`data:dun/d01boss.cfg` is "Divine Beast Cave (boss) Dran", and so on).
- **Boss-to-floor links agree across two sources.** The event scripts reference the boss models per floor (`data:dun/script/dNN/event.stb`), and the hard-coded floor layouts list the same monster indices (`chronicle:ps2/include/monstorunit_floor_data.inc`). Examples: `c12a`/Dran (index 78) in dungeon 0; `c14a-d`/Master Utan (79) in dungeon 1; `c13a`/Ice Queen (80) in dungeon 2; `c15a`+`c15b` (81, 82) in dungeon 3; `c16a`/Minotaur Joe (83) in dungeon 4; `c17a`/Dark Genie (84) and `c23a` final form (106) in dungeon 5; `c21a`/Black Knight (165) and `c22a` mount (166) in dungeon 6.
- **Monster table.** 167 rows in `chronicle:ps2/src/monstorunit.cpp` (each row has a `// N: Name` comment, model name and stb name). Several effect-type actors (`c13_*`, `c23_hasira`, `c23_syougeki`) have only a `.stb` file and no `.chr`; their model is found through alternate names in the same row (`chronicle:ps2/src/dun/gameloop.cpp:6492`; `chronicle:ps2/src/monstorunit.cpp`).
- **Floor layouts.** `BtEnemyLayout00..06` give 15, 17, 18, 18, 15, 26 and 100 floors for the seven dungeons, plus a back-side (`BtUraEnemyLayout`) table for each (`chronicle:ps2/include/monstorunit_floor_data.inc:475-478`).
- **Dungeon geometry lives in `dun/mpd_pack/*.mpd`.** The `.cfg` files hold the map-part definitions, but their `SET_PATH` folders (for example `dun/d01/floor_main/`, the example path unverified; `dun/d01/` has no such folder) do not exist in this tree; the names inside the `.cfg` resolve against the `.mpd` pack (`chronicle:ps2/src/shot_freefuncs.cpp:1310-1319`; inference from the missing directories).
- **Map number space.** `MapNoTransFunc` maps numbers to places: 0-9 towns, 11-199 fields, 200-205 dungeons (`chronicle:ps2/src/battlemenu.cpp:10140-10212`). `MenuGrobalMapNoTbl` maps each `WorldMapPlace` index to a map number (`chronicle:ps2/src/battlemenu.cpp:8771`).
- **Demon Shaft has no `TownOrDngPos` entry** (index 15 is the placeholder `"xx"`, `chronicle:ps2/src/battlemenu.cpp:8772-8788`), and its map number is 60 in `MenuGrobalMapNoTbl`, which sits inside the field range.
- **Demon Shaft unlock looks wrong.** `SaveData->VisitMap(MenuGrobalMapNoTbl[WORLD_PLACE_DEMON_SHAFT] <= 0, 0)` passes a comparison result, not the map number (`chronicle:ps2/src/battlemenu.cpp:8836`). This is probably an original-source quirk; flagged as a risk.
- **Languages.** Seven language codes (`chronicle:ps2/include/language.h:7-15`). Image folders: `img/` (Japanese), `img_1`..`img_6` (US, UK, FR, DE, IT, ES; `chronicle:ps2/src/nowload.cpp:105`), `dun/img/{jp,us,us_e,fr,gr,it,sp}`, `commenu/a_{jpn,usa,eng,fre,ger,ita,spa}`, `titledat/title*.pak` (`chronicle:ps2/src/title/titleloop.cpp:293-305`).
- **Sound archives** are keyed by number: `sound/bgm/bgmN.snd`, `sound/set/sndN.snd`, `sound/special/spN.snd`, `sound/voice/voiceN.snd` (`chronicle:ps2/src/snd.cpp:469-473`, `:844-848`, `:1378-1384`, `:1484-1488`). Dungeon music and sets are at offset 100 (`chronicle:ps2/src/dun/gameloop.cpp:1843-1847`).
- **Pack container.** `.chr`, `.pak`, `.pac`, `.mpd` and `.snd` are the same kind of file (unverified for `.mpd` and `.snd`; the PAK spec was checked): 80-byte entry headers with a 64-byte name and three int32 fields, then the data (`refs/DCExtractor/Specifications/Pack/PAK.md`). Images are `IMG\0` + version word wrapping TIM2 (`refs/DCExtractor/Specifications/Images/IMG (Version 2).md`, `TM2.md`).
- **Leftovers.** 32 files end in `_` (for example `data.hd2_`, `chara/iget.chr_`, `commenu/a_fre/kgetoan2.img__`), plus `.old` folders. The code does not open these names (inference from grep).

## How it works

### Top-level layout

| Directory | Files | Size | Role (verified by code or content) |
|---|---|---|---|
| `chara/` | 25 | 6.9 MB | Editor and fishing actors: `c01d.chr` (editor Toan, `chronicle:ps2/src/editloop_init.cpp:418`), fish models `f00s`, `f01a`..`f18a` (`f01a`-`f06a` loaded at `chronicle:ps2/src/fish.cpp:457-462`), `iget.chr` (item-get), `escape.chr` |
| `check/` | 10 | 972 KB | UI bitmaps: `ankfont.img` used in dungeon load (`chronicle:ps2/src/dun/gameloop.cpp:914`); `button`, `opennext`, `topframe` not referenced |
| `commenu/` | 821 | 362 MB | Menu art per language: `a_<lang>/` (34-36 entries each), root `itemicon.img`, `wepicon.img`, `allicon.img`, `kage*.img`, `dungeon/c0Nmodel.pak`, `map/` (world map) |
| `dun/` | 1,403 | 252 MB | Dungeons and in-dungeon actors (detail below) |
| `gedit/` | 2,181 | 840 MB | Towns (`e01`-`e05`), interiors (`interior/`), field maps (`s01`-`s99`) |
| `img/`, `img_1`..`img_6` | 46-45 each | ~5 MB each | Title, memory card, load screens per language |
| `meswin/` | 60 | 2.9 MB | Message-window fonts and `system*.mes` text |
| `noda_w/` | 14 | 588 KB | `dun00_eng*.mes` and `fconv*.bin`; not loaded by a literal path in `ps2/src` (the port's localisation test uses it as a key example) |
| `opdat/` | 301 | 78 MB | Opening movie data: `chara/`, `scene/` (`.sne` + `.cfg`), `norn*` town models, `toan` (Toan's house), `seirei` (spirit/Fairy King area), `opening.scr` |
| `rmdat/` | 20 | 40 MB | Room packs `rmdat1..9.pak` with `rmdatN.cfg` (location names decoded from comments) |
| `sound/` | 259 | 105 MB | `bgm/` (57), `set/` (62), `special/` (62), `sound_set/` (29, different copies, see Open questions), `battle/` (per dungeon), `voice/` (7), `tbl/` (setbl, sqtbl) |
| `titledat/` | 7 | 27 MB | `title.pak` plus `title_eu/_f/_g/_i/_s.pak` and `lang_set.img` |
| root | — | — | `data.hd2` (index into the original DAT), `gdata0.edt` (save/edit data), `mapeditor.ini`, `tmp.txt` (developer leftover, do not ship) |

### Naming conventions

- `cNN` + letter is a character model. `cNNa`/`cNNb`/`cNNd` are chr variants of the same character (`c01d` Toan, `c04b` Xiao, `c06b` Goro, `c05a` Ruby, `c10b` Ungaga, `c18a` Osmond). Inside a pack, `cNNa.mds` is the body, `cNNs.mds` is the SHADOW_MODEL (from `info.cfg`, for example `data:dun/monstor/c15a.chr`), `cNNa01.img` is the body texture, `cNN*.mot` motions, `cNN*.wgt` weights, `cNN*.bbp` body parts.
- `cNNw.pac` is a weapon pack; `cNNwMM.chr` is one weapon model; `cNN_ex00.chr` is an extra pack (item-get and hand models) per party member (`chronicle:ps2/src/btitem.cpp:209-211`).
- `eNNa` is an enemy (monster) model. The NN is not the table index: `e01a` is Master Jacket (index 0), `e163a` is Titan (Enhanced, index 161) (`chronicle:ps2/src/monstorunit.cpp`). Monsters have `eNNa.chr` plus `eNNa.stb` (behaviour script). The town `gedit/eNN/` folders are not monsters.
- `pNNa` is an NPC model; `gedit/eNN/chara/pNNa.chr` (for example `p01a`-`p14a` in Norune, `p21a`-`p32a` in Matataki). Names are not in the data; see Open questions.
- `eNNcMMx`/`eNNpMMa` are event-specific copies (for example `e403c18a.chr`, `e228c01d.chr`).
- `dNN` is a dungeon. `dNNboss.mpd`, `dNNinter.mpd`, `dNNinter2.mpd`, `dNNmain_a.mpd`, `dNNmain_b.mpd`, `dNNmain_c.mpd` are floor packs; `dNNboss.cfg` etc. are the matching map-part definitions.
- `sNN` is a field or sub-map (for example `s30` Dark Heaven near, `s76`/`s78` Demon Shaft boss).
- `eNN` in `gedit/` and `TownOrDngPos` is a town; `sNN` is a field; `dNN` is a dungeon.
- `_N` before `.mes` is the language index (`dun/script/d01/d01_3.mes`; `chronicle:port/src/localize.hpp:46`).
- A trailing `_` (for example `iget.chr_`) is a leftover, not loaded.

### Playable characters

| Enum | Name (enum and fandom) | Party chr | Model / shadow / texture (from pack entries) | Weapon pack | Extra pack | Voice | Kage icon | Cloth | Menu model |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Toan | `dun/mainchara/c01d.chr` | `c01d.mds`, `c01s.mds`, `c01d01_dun.img` | `c01w.pac` | `c01d_ex00.chr` | `voice0.snd` (toan_s) | `commenu/kagetoan.img` | `poncho1.clo` (in chr) | `c01model.pak` |
| 1 | Xiao | `dun/mainchara/c04b.chr` | `c04b.mds`, `c04s.mds`, `c04b01.img` | `c04w.pac` | `c04b_ex00.chr` | `voice1.snd` (syao_s) | `kagesyao.img` | — | `c02model.pak` |
| 2 | Goro | `dun/mainchara/c06b.chr` | `c06a.mds`, `c06s.mds`, `c06a01.img` | `c06w.pac` | `c06b_ex00.chr` | `voice2.snd` (goro_s) | `kagegoro.img` | `goro.clo` | `c03model.pak` |
| 3 | Ruby | `dun/mainchara/c05a.chr` | `c05a.mds`, `c05s.mds`, `c05a01.img` | `c05w.pac` | `c05a_ex00.chr` | `voice3.snd` (ruby_s) | `kageruby.img` | — | `c04model.pak` |
| 4 | Ungaga | `dun/mainchara/c10b.chr` | `c10a.mds`, `c10s.mds`, `c10a01.img` | `c10w.pac` | `c10b_ex00.chr` | `voice4.snd` (unga_s) | `kageunga.img` | `ungg2.clo` (also `ungg1.clo`) | `c05model.pak` |
| 5 | Osmond | `dun/mainchara/c18a.chr` | `c18a.mds`, `c18s.mds`, `c18a01.img` | `c18w.pac` | `c18a_ex00.chr` | `voice5.snd` (ozmd_s) | `kageozu.img` | — | `c06model.pak` |

Other party-related packs:

- `dun/mainchara/wep_eff/` (27 files): weapon effect models, for example `c05_e01.chr` (Ruby), `c06a_tameex.chr` (Goro charge, `chronicle:ps2/src/dun/gameloop.cpp:663`), `c10a_ex.chr` (Ungaga, `:723`).
- `dun/mainchara/c05w_h.img` is the hand texture referenced in the Ruby path (`chronicle:ps2/src/dun/gameloop.cpp:6941`).
- Town models for the party sit in `gedit/eNN/chara/` (`c01d.chr`, `c04b.chr`, `c06b.chr`, `c05a.chr`, `c10b.chr`, `c18a.chr` in various towns) and event variants (`e403c18a.chr`, `e228c01d.chr`).
- Opening/title copies: `opdat/chara/03c01d.chr`, `01c07a.chr`, `01c08a.chr`, `01c11a.chr`, `01c09a.chr` (`chronicle:ps2/src/title/op_b.cpp:370-375`).

### Towns and fields

| Town | Enum (`Town` / `WorldMapPlace`) | `gedit/` folder | Name (decoded comment) | BGM / SE set | World-map pack |
|---|---|---|---|---|---|
| Norune Village | TOWN 0 / PLACE 0 | `e01` | ノルン村 (Norune) | bgm1 / snd0 | (not a region) |
| Matataki Village | TOWN 1 / PLACE 2 | `e02` | マタタギの里 (Matataki) | bgm2 / snd1 | `commenu/map/matatagi.pac` (region 0) |
| Queens | TOWN 2 / PLACE 5 | `e03` | クイーンズ (Queens) | bgm3 / snd2 | `queen.pac` (region 1) |
| Muska Lacka | TOWN 3 / PLACE 7 | `e04` | ムスカラッカ (Muska Lacka) | bgm4 / snd3 | `musuka.pac` (region 2) |
| Yellow Drops | TOWN 4 / PLACE 11 | `e05` (header unnamed) | inferred from PLACE 11 | bgm14 / snd4 | `moon.pac` (region 3; inferred) |

Fields and sub-maps with decoded names (short phrases from the `gedit/sNN/mapinfo.cfg` headers):

| Field | Name (decoded) | Place enum | BGM / set | Notes |
|---|---|---|---|---|
| `s01`, `s47` | ゴローの家 (Goro's house) | — | bgm2 / snd1 (s01) | Goro's house |
| `s03` | 精霊の樹 (spirit tree) | — | bgm2 / snd1 | |
| `s04`, `s43` | ブラウンプーの村 (Brownpu village) | FIELD_S04 (4) | bgm6 / snd14 | map number 14 |
| `s09`, `s33` | イーストハーバー (East Harbor) | — | bgm3 / snd19 (s09) | |
| `s13` | イエロードロップ (Yellow Drops field) | FIELD_S13 (10) | bgm15 / snd23 | map number 23 |
| `s30` | ダークヘブン城（近距離）(Dark Heaven, near) | FIELD_S30 (13) | bgm30 / snd55 | map number 40; used by the Demon Shaft unlock check |
| `s14`, `s40` | ダークヘブン城（遠距離）(Dark Heaven, far) | — | — | |
| `s28` | Dark Heaven entrance | — | — | |
| `s32` | (no name) | FIELD_S32 (8) | bgm4 / snd3 | map number 42 |
| `s88` | ダークヘブン城（ボス）魔王 (Dark Heaven boss, Demon King) | — | — | |
| `s76`, `s78` | デーモンシャフト（ボス）黒騎士 (Demon Shaft boss, Black Knight) | DEMON_SHAFT (15) | — | |
| `s77` | 第二段階のラスボスマップ (second-phase last-boss map) | — | — | `d06boss2.cfg` |
| `s50`, `s51` | 100F dungeon exterior; Demon Shaft entrance | — | — | |
| `s79` | ウンガガ (キャラ特性鍵) (Ungaga character key) | — | — | |
| `s86` | シャオ (ネコジャンプ) (Xiao cat jump key) | — | — | |
| `s80`-`s85` | 踊場 (landings) by floor | — | — | |
| `s96`-`s98`, `s90`-`s94` | dungeon boss rooms (see boss table) | — | — | |
| `s24`, `s49` | 太陽と月の神殿（ドック）(Sun and Moon Temple dock) | — | — | |
| `s25`-`s28` | entrance maps for Shipwreck, Sun/Moon, Moon Sea, Dark Heaven | — | — | |
| `s31` | ロボット（内観）(robot interior) | — | — | |
| `s37` | 雲の通路 (cloud passage) | — | — | |
| `s39` | 最終イベント用（シーダ王の部屋）(final event room) | — | — | |

`gedit/interior/` (6 files) and `gedit/eNN/in/` (12 interiors in `e01`, for example `in/0101/`, `in/i01h10/`) hold house and shop interiors.

### Dungeons

| Index (`Dungeon`) | Map prefix | Name (decoded) | Floor layouts | Boss (cfg header) | Boss monster index / model | Dungeon BGM / set / battle folder |
|---|---|---|---|---|---|---|
| 0 | `d01` | 神獣の洞窟 (Divine Beast Cave) | 15 | 神獣の森（ボス）ドラン (Dran) | 78 / `c12a` | bgm100 / snd100 / `sound/battle/d01/` |
| 1 | `d02` | 白ひげふくろうの森 (Wise Owl Forest) | 17 | マスターウータン (Master Utan) | 79 / `c14a`-`c14d` | bgm101 / snd101 / `battle/d02/` |
| 2 | `d03` | 沈没船 (Shipwreck) | 18 | 氷の女王 (Ice Queen), 思い出の教会 church | 80 / `c13a` | bgm102 / snd102 / — |
| 3 | `d04` | 太陽と月の神殿 (Sun and Moon Temple) | 18 | 古代王の寝室 (ancient king's bedroom) | 81 / `c15a` (coffin), 82 / `c15b` | bgm103 / snd103 / — |
| 4 | `d05` | 月の海 (Moon Sea) | 15 | コロシアム (colosseum) | 83 / `c16a` (Minotaur Joe) | bgm104 / snd104 / — |
| 5 | `d06` | ダークヘブン城 (Dark Heaven Castle; Gallery of Time in the enum) | 26 | 魔王 (Demon King) | 84 / `c17a`, hands 85 `c17b`, 86 `c17c`; final form 106 / `c23a` (`d06boss2`) | bgm105 / snd105 / — |
| 6 | `d07` | デーモンシャフト (Demon Shaft) | 100 | 黒騎士 (Black Knight) | 165 / `c21a`, mount 166 / `c22a` | bgm106 / snd106 / — |

Dungeon-level data files per prefix: `dun/mpd_pack/dNN*.mpd` (floor packs), `dun/dNN*.cfg` (map-part definitions, text, cp932), `dun/script/dNN/event.stb` (event bytecode) with `dNN_<lang>.mes`, where `<lang>` is `LanguageCode` (`chronicle:ps2/src/btsysscript.cpp:103-104`), `dun/dNN/` (`anime`, `effect`, `event`, `stair_mos`), `dun/message/ww_mes/steve0N_<lang>.mes` (dungeon message set by floor group, `chronicle:ps2/src/shot_freefuncs.cpp:1250-1252`), `dun/img/<lang>/dname0N.img` (dungeon name card, `chronicle:ps2/src/dun/gameloop.cpp:9432`), `dun/img/<lang>/dname00..06.img`.

Dungeon-related sound: `sound/battle/dNN/` holds battle music and cues per dungeon (`dan01a.sq`, `dan01bgm.hd`, `dan02sc.bd`, and so on); `sound/bgm/bgm100..106.snd` and `sound/set/snd100..106.snd` are the dungeon ambience and sets.

### Monsters per dungeon (distinct monster indices in the floor layouts)

- Dungeon 0 (Divine Beast Cave), normal layout: 14 monsters including Master Jacket (0), Skeleton Soldier (1), Statue (2), Dasher (3), Ghost (36), Dragon (51), Cave Bat (52), Rockanoff (69), Dran (78), Yammich (96), Statue Dog (97), Opar (98).
- Dungeon 1 (Wise Owl Forest): 19 monsters, including the Sunday..Saturday set (10-16), Werewolf (4), Witch Illza (18), King Mimic/Mimic (70, 71), Master Utan (79), Haley Holey (99), King Prickly (100).
- Dungeon 2 (Shipwreck): 18 monsters, including Gunny (19), Gyon (20), Pirate's Chariot (21), Auntie Medu (22), Captain (23), Corcea (24), Sam (77), Ice Queen (80), and the Ice set (76, 92, 101-104).
- Dungeon 3 (Sun and Moon Temple): 15 monsters, including Golem (25), Mr. Blare (26), Dune (27), King's Curse Coffin (81), King's Curse (82), Gol (94), Sil (95).
- Dungeon 4 (Moon Sea): 14 monsters, including Titan (28), Arthur (35), Moon Bug (49), Vulcan (62), Crescent Baron (68), Minotaur Joe (83), Wine Keg (91).
- Dungeon 5 (Dark Heaven / Gallery of Time): 31 monsters, including the card-suit set (37-42), Lich (45), Living Armor (47), Dark Genie (84-86), Dark Genie companions (87-93), Gacious (105), Dark Genie final forms (106-110).
- Dungeon 6 (Demon Shaft, 100 floors): 56 monsters, the "Enhanced" set (113-164), Bishop Q (133), Silver Gear (144), Black Knight (165), Black Knight Mount (166).

### Bosses

| Boss (community name) | Monster index | Model chr | Dungeon / map | Evidence |
|---|---|---|---|---|
| Dran | 78 | `dun/monstor/c12a.chr` | d01 (Divine Beast Cave) | `d01boss.cfg`; `c12a` in `d01/event.stb` (160 refs) |
| Master Utan | 79 | `c14a.chr` (+ `c14b`, `c14c`, `c14d`) | d02 | `d02boss.cfg`; `c14a-c` in `d02/event.stb` |
| Ice Queen | 80 | `c13a.chr` | d03 (Shipwreck) | `d03boss.cfg`; `c13a` in `d03/event.stb` |
| King's Curse Coffin / King's Curse | 81 / 82 | `c15a.chr` / `c15b.chr` | d04 | `d04/event.stb` |
| Minotaur Joe | 83 | `c16a.chr` | d05 (Moon Sea) | `d05/event.stb`; `d05boss.cfg` (colosseum) |
| Dark Genie (Demon King) | 84 | `c17a.chr` (+ `c17b`, `c17c` hands) | d06 | `d06/event.stb` (351 refs) |
| Dark Genie final form | 106 | `c23a.chr` (+ `c23_beem.chr`, `c23_beem_s.chr`) | d06 (`d06boss2`) | `d06/event.stb`; `d06boss2.cfg` |
| Black Knight / mount | 165 / 166 | `c21a.chr` / `c22a.chr` | d07 (Demon Shaft) | `d07/event.stb`; `d07boss.cfg` |
| Sam | 77 | `e86a.chr` | d03 layout | monster table row 77 |

Non-dungeon boss-like actors: Gacious (105, `e124a`), Bishop Q (133, `e116a`), Gemron elements (111, 121, 132, 143, 154, `e111a`-`e115a`), Silver Gear (144, `e118a`).

### NPCs and key story models

- Town NPC models are `pNNa` files in each `gedit/eNN/chara/` folder: e01 has 15 (`p01a`-`p14a`, `p47a`), e02 13, e03 18, e04 11, e05 6. Names are not in the data. Only the Japanese dungeon, town and map names are decoded here.
- `opdat/chara/01p17a1a.chr`, `01p19a1a.chr` and `03p09a.chr`/`03p10a.chr` are opening-movie NPC models (`chronicle:ps2/src/title/op_a.cpp:354-564`).
- Fairy King / spirit area: `opdat/seirei.cfg` (comment: Norune village) with `opdat/norn4/seirei.pak` and `seirei2.pak`. Identification is inference from the name `seirei` (spirit).
- Toan's house: `opdat/toan.cfg` (トアンの家, night) with `opdat/toan/` (`t0101.mds`, `03komono.chr`).
- Norune village models: `opdat/norn*/` (`e01*.mds`, texture `*.img`), decoded from `opdat/norn.cfg` (エディット(ノルン村)).
- Fish: `chara/f01a.chr`..`f06a.chr` are fish models loaded by the fishing code (`chronicle:ps2/src/fish.cpp:457-480`); `chara/f00s.chr` is loaded there too (role inferred as the fishing stage); `chara/fishing.pak`, `commenu/a_eng/fishmenu.pac`.
- Steeb/town messages: `dun/message/old_data/steeb01.mes`..`steeb07_2.mes` (unverified) and `dun/message/ww_mes/steve01..07_*.mes` (floor-group message set; `chronicle:ps2/src/shot_freefuncs.cpp:1250-1252`).
- Dungeon-scale event actors used across floors: `c20a` (in `dun/ex/c20a.chr`, referenced in all seven `event.stb` files); role not identified.

### Items and icons

- Item icon banks: root `commenu/itemicon.img` (`chronicle:ps2/src/battlemenu.cpp:843`), `commenu/wepicon.img` (weapon icons), `commenu/allicon.img`, `commenu/a_<lang>/itemlst.img`, `itempack.img` (map symbols, `chronicle:ps2/src/dungeonmap.cpp:650`), `itemshop.pak` (`chronicle:ps2/src/shop.cpp:1056`), `quickchr.pac`/`charatex.img` (character-change portraits; `chronicle:ps2/src/menu_dungeon.cpp:1317`).
- Item and attachment models: `dun/item/main_data/` (`at*` names are attachments, for example `atfire`, `atice`, `atholy`, `atspeed`) and `dun/item/main_wep/` (215 files; `c01w00..` weapon models).
- Treasure-box and item-get models: `dun/etc/itemget_b/`, `itemget_s/` (`chronicle:ps2/src/shot_freefuncs.cpp:1346-1347`); `dun/etc/atr*` (Atla models, inferred from names).

### Language-specific trees

| Concept | Japanese | US | UK | FR | DE | IT | ES |
|---|---|---|---|---|---|---|---|
| Code (`LanguageCode`) | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
| `img` folder | `img/` | `img_1/` | `img_2/` | `img_3/` | `img_4/` | `img_5/` | `img_6/` |
| `dun/img` | `dun/img/jp/` | `us/` | `us_e/` | `fr/` | `gr/` | `it/` | `sp/` |
| `commenu` | `a_jpn/` | `a_usa/` | `a_eng/` | `a_fre/` | `a_ger/` | `a_ita/` | `a_spa/` |
| Title pack | `title.pak` | `title.pak` | `title_eu.pak` | `title_f.pak` | `title_g.pak` | `title_i.pak` | `title_s.pak` |

Codes come from `chronicle:ps2/include/language.h:7-15`; the title pack choice is `chronicle:ps2/src/title/titleloop.cpp:293-305`. `dun/img/<lang>/` holds `dname00..05.img` in every language; `dname06.img` exists in the six non-Japanese folders only. `gedit` and `dun/script` message files use `_N.mes` suffixes.

## Ixion hooks

- **Party registry.** Build one record per DC1 party member keyed on `Character` (`chronicle:ps2/include/itemdata.hpp:485`). Fields: chr name (`chronicle:ps2/src/btitem.cpp:56`), `cNNw` weapon prefix (`chronicle:ps2/src/btmisc.cpp:108`), `cNN_ex00` extra pack (`chronicle:ps2/src/btitem.cpp:209`), voice index (`chronicle:ps2/src/btitem.cpp:123`), kage icon (`chronicle:ps2/src/battlemenu.cpp:3177`), menu model index `chara+1` (`chronicle:ps2/src/menu_misc.cpp:1038`). DC2 characters can get the same record shape, with their own keys.
- **Place registry.** Use the place enum (`chronicle:ps2/include/battlemenu.hpp:281-299`) and the map-number table (`chronicle:ps2/src/battlemenu.cpp:8771`) as one join key for towns, fields and dungeons. Map numbers are already partitioned (towns 0-9, fields 11-199, dungeons 200-205), which leaves room for a second game's ids if they are offset.
- **Travel hook.** `BtMapJumpLoad` (`chronicle:ps2/src/shot_freefuncs.cpp:1215`) is the one place that loads `dun/mpd_pack/<map>.mpd` and `dun/<map>.cfg`. A cross-world dungeon jump can call it with a DC1 map name after the DC2 side sets the state. `SET_DUNGEON_MAP` (`chronicle:ps2/src/btsysscript.cpp:623`) and `LOAD_DUNGEON_MAP2` (`:631`) are the script-level equivalents.
- **Dungeon population.** `BtLoadMonstor` (`chronicle:ps2/src/dun/gameloop.cpp:6492`, layout pick at `:6537`) reads `BtEnemyLayoutList[selectMapNo][floor]`. A foreign dungeon can be populated by pointing the list at another layout table, using the same struct (`chronicle:ps2/include/monstorunit_floor_data.inc`).
- **Dungeon presentation.** `LoadStartLogo` picks `dname0N.img` and the floor texture by dungeon index (`chronicle:ps2/src/dun/gameloop.cpp:9432`). Music and sets follow `selectMapNo + 100` (`:1843-1847`), so a cross-world dungeon can keep its own music by passing the index.
- **Language selection.** Any shared asset must follow the same `LanguageCode` rules: `img`/`img_N` (`chronicle:ps2/src/nowload.cpp:105`), `commenu/a_<lang>` (`chronicle:ps2/src/menu_draw.cpp:60`), `dun/img/<lang>` (`chronicle:ps2/src/hitvalue.cpp:33`), `teximg2_N.pac` (`chronicle:ps2/src/dun/gameloop.cpp:1261`).
- **Loader.** The port's case-folded index (`chronicle:port/src/dataread.cpp:133`) and the `data.hd2` check (`:46`) can be reused as is for a combined tree, but the two games' tree roots must not collide (see Risks).
- **Verification helper.** The DCExtractor pack walk (80-byte entries) recovers entry names for every `.chr`, `.pak`, `.pac` and `.mpd` in this tree and is enough to build a cross-check table automatically.

## Risks and blockers

- **Name collisions.** DC1 and DC2 both use names like `c01d`, `e01`, `d01`, `s04`. A merged tree needs a namespace (for example a `dc1:` prefix on every id) before any shared lookup.
- **Demon Shaft routing.** The place has no `TownOrDngPos` string (`"xx"`, `chronicle:ps2/src/battlemenu.cpp:8772-8788`), map number 60 sits inside the field range, and the unlock check passes a boolean to `VisitMap` (`chronicle:ps2/src/battlemenu.cpp:8836`). Any "visit any dungeon" feature must special-case it.
- **Unnamed town.** `gedit/e05` has no name in its header; "Yellow Drops" is inferred from the enum and `towns[4]` (`chronicle:ps2/src/battlemenu.cpp:10140-10146`).
- **Unresolved NPCs.** Most `pNNa` and `eNNcMMx` names cannot be matched to characters without decoding the `.mes` text and the STB bytecode. Do not assign names from the file IDs alone.
- **Unknown record fields.** `BT_ENEMY_LAYOUT` has two unnamed s32 fields (`unk_00`, `unk_08`) and `BT_ENEMY_FLOOR` has `unk_6C` (`chronicle:ps2/include/monstorunit.hpp:560-575`). Copying a layout to another dungeon may change behaviour in ways the catalogue cannot show.
- **Floor geometry paths.** `SET_PATH` folders in the `.cfg` files do not exist in this tree; the geometry is only reachable through the `.mpd`. Any tool that expects the folders will fail.
- **Partial chr parsing.** The 80-byte entry walk stops early on several character packs (for example `dun/mainchara/c01d.chr`, which has no `info.cfg`, and several boss packs such as `dun/monstor/c13a.chr`, `c15a.chr`, `c23a.chr`). Model names were taken from `info.cfg` where it exists and from the first entries otherwise.
- **PAL-only data.** The tree is PAL. Symbol addresses for NTSC differ (see Key facts). Mixing the two will not load.
- **Leftover files.** `tmp.txt` in the root is a developer path list; it must not ship with any Ixion build. Files with trailing `_` are not loaded and should be excluded.
- **Public repository.** This catalogue cites names and identifiers only. It contains no game text, no asset bytes, and no local paths. Keep the extracted tree in a git-ignored location.

## Open questions

- Which `pNNa`/`eNNcMMx` models are Seda, Paige, Renee, Gina, Laura, Carl, Claude, Simba, Komacho, Macho, Pike, and the Fairy King? Needs `.mes` decoding and the STB bytecode of each `gedit/eNN/event.stb`.
- Role of `c20a` (in all seven dungeon event scripts and `dun/ex/c20a.chr`), of `c07a` (title and opening textures, but not a party member), of `c04cat` and `c04pcat` (cat models in `gedit/e01/chara/`, probably the Xiao cat), and of `turi` (`voice6.snd`, `c01d_turi.chr`).
- Which `mpd` each floor uses. The mapping is in the `SET_DUNGEON_MAP` calls inside `event.stb`, which needs the STB opcode table (`chronicle:ps2/src/btsysscript.cpp:1122` for the opcode list).
- Semantics of `BT_ENEMY_LAYOUT.unk_00` and `unk_08`, and `BT_ENEMY_FLOOR.unk_6C` (`chronicle:ps2/include/monstorunit.hpp:560-575`).
- Difference between `sound/sound_set/` and `sound/set/` (both have `snd0`, `snd14`, with different sizes; `sound_set` is not reached by any literal path in `chronicle:ps2/src/snd.cpp`).
- Whether `commenu/map/moon.pac` covers Moon Sea, Yellow Drops, or both.
- Whether `TownOrDngPos` entry `"xx"` and map number 60 are the intended Demon Shaft keys, and whether `chronicle:ps2/src/battlemenu.cpp:8836` is an original-source quirk or a port bug.
- Whether `commenu/c01model.pak` etc. (menu index) and `commenu/kage*` icons match the enum in every language folder.
- Whether the underscore-suffixed leftovers were ever read by the original PS2 build (they are absent from every literal path in `ps2/src`).
