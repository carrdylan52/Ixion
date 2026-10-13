# Ixion, Lore-First: Why the Train Runs, Who Drives It, and Who Rides

## 1. Scope and stance

This is the lore angle on Ixion. It treats what Dark Cloud (DC1) and Dark Chronicle (DC2) fix in-fiction as binding, names the gaps, and proposes how Ixion fills them. Engine hosting, passenger-state format, and asset conversion are out of scope except where a lore fact constrains them.

Every claim is tagged:

- **[canon]** stated in the games or in the wiki article cited.
- **[inferred]** follows from canon in one reasoning step.
- **[proposal]** an Ixion design choice. Not claimed as canon.

Sourcing note: the fandom pages for Ixion, Lunatic Wisdom Laboratories, and Station returned errors during this pass, so their text is not used. Their existence is confirmed from the wiki title index. Everything marked [canon] below comes from the local wiki articles (Dark Cloud, Dark Chronicle, Toan, Maximilian, Monica Raybrandt, Palm Brinks, Underground Water Channel, Divine Beast Cave, Dark Genie, Gundorada Workshop, Georama, Inventing, Spheda) or from the decomp sources (`chronicle:` and `chronicletwo:` prefixes).

## 2. Canon the train must respect

- **Atlamillia are time stones in DC2 and object-keepers in DC1.** [canon] In DC1 the Fairy King gives Toan a blue Atlamillia that rebuilds destroyed areas; Atla are opened and their contents kept in it. In DC2 there are three Atlamillia (Red/Earth Stone for Max, Blue/Moon Stone for Monica, Gold/Sun Stone held by Griffon), and they carry travel across time. Monica travels 100 years back; Max 100 years forward.
- **Time travel already exists in DC1.** [canon] Seda "traveled forward in time to retrieve the Atlamillia" in DC1, the Gallery of Time sequence returns the party to their own time, and Toan spends the stone's power to revive Sophia. The engine names the Gallery of Time as a dungeon mode (`chronicle:ps2/include/dungeon.h`, `DUNGEON_GALLERY_OF_TIME`).
- **The Moon People are in both games.** [canon] DC1's Moon People sealed the Dark Genie in an urn, lost their magic, and fly a Moon Ship to the moon city Yellow Drops. DC2's Griffon is a Moon Person in his true form, and Alexandra's Moon Flower Palace is a Moon-people site.
- **Osmond is in both games.** [canon] DC1's Osmond is leader of the Moon People on Yellow Drops and a gun-wielding party member. DC2's Osmond is a top researcher at the Luna Labs who pilots Ixion.
- **Origin points.** [canon] Griffon destroyed the origin points of future locations (Palm Brinks was spared; Gundorada Workshop's origin was destroyed "so that the workshop could never exist in the future"). Max and Monica restore Jurak's origin point at Sindain.
- **Atla hold people and objects.** [canon] In DC1, Atla contain houses, trees, villagers, and objects. When removed from a dungeon they "become pieces of the world," and only the main character can open them.
- **Ixion's route.** [canon] Lin reports that Griffon attacks from 10,000 years in the past. The Luna Labs finish Ixion at the start of Chapter 5, and Ixion departs "to head for Griffon's time period" with Osmond at the controls.
- **An Ixion item exists in the tech tree.** [canon] The Inventing data lists "Ixion" as an ingredient for Drill Arm III and Laser Arm II, alongside Luna Stone Shards.

## 3. Why the train can reach Terra

Dark Cloud's world, Terra, is never placed on DC2's timeline. Three candidate explanations:

**A. Terra is far past or far future of DC2's timeline.** [inferred]
DC1 frames its story as "a fairy tale read from a book found in ancient, nameless ruins," and scholars debate whether it is true. That is archival distance, not a parallel. Ixion's own mandate is an era roughly 10,000 years back. Terra can sit inside that span.
- Pro: uses two canon facts (ancient framing, 10,000-year route) and needs no new physics.
- Con: nothing dates Terra against DC2.

**B. Parallel branch.** [proposal]
Terra is a separate time stream sealed off by the Fairy King, and Ixion opens a door into it.
- Pro: explains why Terra's towns cannot be reached by ordinary time travel.
- Con: DC1 never mentions parallels. It would add a new cosmology.

**C. Atla as beacons.** [proposal]
The Fairy King sealed whole towns out of time into Atla. A train that can reach any preserved moment can reach a town that was preserved on purpose. Ixion's detection would key on Atla, the same way Atlamillia "chooses" its wielder (Gerald says his stone chose Max).
- Pro: ties Ixion to the Atlamillia rule that already exists.
- Con: relies on DC1 Atla being time-preserved rather than merely shrunk. Canon is ambiguous here.

**Recommendation: A plus C.** Terra is inside Ixion's reachable span, and its towns are preserved in Atla. Ixion's first Terra arrival is an Atla opening at a larger scale. B is held in reserve as a fallback if A is rejected.

## 4. Passenger state, explained by Atla

Ixion needs a lore reason to carry characters and items between worlds. The strongest candidate is already canon.

- [canon] In DC1, Atla are the only container in the games that holds people as well as objects. Villagers are inside them until placed in Georama.
- [proposal] Characters and items crossing worlds travel as Atla-packed passenger state. On arrival they are unpacked at a station.
- [proposal] Unpacking requires an Atlamillia. Max and Monica carry their own. Terra-side characters need a station-side key, which the Luna Labs could supply as Luna Stone Shards (already in the Inventing data).
- [proposal] Weapon and HP translation is an Ixion mechanic, not a lore requirement. The lore only needs the packing and unpacking step to exist.

This keeps the design honest: passenger state is an Atla operation, so its limits (who can open it, what it can hold) follow from canon rather than from engineering convenience.

## 5. Who runs Ixion

- **The Luna Labs** (Lunatic Wisdom Laboratories) at Veniccio. [canon] Max and Monica restore part of the Luna Labs in Chapter 4; Max and Monica board Ixion there in Chapter 5. [proposal] The Labs are Ixion's base station.
- **Osmond.** [canon] Pilots Ixion in DC2. DC1's Osmond leads the Moon People. [proposal] Two options:
  1. Same person, displaced in time (a Moon People elder who travelled forward). Cheap, and it explains the shared name.
  2. A lineage title ("Osmond"), with the DC2 researcher as a descendant of the Yellow Drops Osmond. Preserves both characters as they are.
  Recommend option 2, because DC1 and DC2 both fix Osmond's personality strongly and option 1 would have to reconcile them.
- **Dr. Nobb.** [canon] Builds a translation device for the Shigura and requests a direct link with Elena. [proposal] Ixion's chief engineer, and the person who first opens Atla for non-Atlamillia holders.
- **Elena.** [canon] Max's mother, reachable from the Labs. [proposal] Ixion's civilian authority: she holds the Terra-side rebel mandate.
- **Jaming and his grandson.** [canon] Jaming is Gaspard's ally and controlled the Shigura with a hovercraft; his grandson is at the Labs. [proposal] Source of internal tension. Ixion's staff includes a Griffon-aligned lineage.
- **Galen Agaris and Paznos.** [canon] Paznos is the warship restored at Gundorada. [proposal] Ixion's escort, not its engine.

## 6. Stations (in-fiction names)

Canon names, and what is only proposed:

| Name | Status | Source |
|---|---|---|
| Palm Brinks train station | canon, DC2 | Palm Brinks article: "the Blackstone Railroad from the train station" |
| Sindain Station | canon, DC2 title | Monica article: Blackstone One stops at Sindain Station |
| Veniccio Station | canon name only | wiki title index |
| Balance Valley Station | canon name only | wiki title index |
| Luna Labs (Veniccio) | canon, DC2 | Monica article |
| Yellow Drops | canon, DC1 moon city | Dark Cloud article |
| Norune, Matataki, Brownboo, Queens, Muska Lacka | canon, DC1 towns | Dark Cloud article |
| Kazarov Stonehenge | canon, DC2 | Monica article: Chrono Union site |

[proposal] Ixion stations are named after origin points. Each origin point is a time-anchor for a town. A station is "Town (Origin)" in its present-day form, and it carries the town's name in both games. Examples:

- Palm Brinks (Origin): the hub, since Palm Brinks was the one town Griffon spared.
- Norune (Origin): the Terra arrival station, at the Divine Beast Cave.
- Yellow Drops (Origin): the moon stop, modeled on the Moon Ship route.
- Gundorada (Origin): restored in Chapter 5 and reached through Mount Gundor.

Renaming rule [proposal]: station names should use the town's canon spelling from each game, not localised variants, because the localised string tables differ (the textpack contains Italian and Spanish variants, for example "FABBRICA LUNARE" for the Luna factory).

## 7. First-trip story beats

[proposal] Ixion's first Terra trip is a detour from the canon route.

1. **Departure.** Chapter 5 closes with Ixion finished and departing Luna Labs. Osmond's sensors pick up Atla preserved at Norune, in the Divine Beast Cave (DC1 floor B4 onward).
2. **Arrival.** Max and Monica step out at a Norune station on the cave floor where Toan first meets Seda. Toan is mid-dungeon and has not yet met Xiao, so the first encounter is with a boy whose Atlamillia is blue.
3. **Resonance.** Max's red Atlamillia and Toan's blue one react to each other. This is the first physical meeting of the two stone colours, and it gives Ixion's team the first data on how the Atlamillia pair.
4. **Passenger.** Xiao's Changing Potion came from Seda, who had travelled forward in time. Ixion's researchers want the potion, because a potion made from a time-traveller carries a residue that Ixion can read. Toan gives a sample. This is the first passenger in the reverse direction.
5. **Return.** The party returns to the Luna Labs with one Terra passenger packed in Atla. The Terra passenger is the proof of concept for passenger state.

This keeps the canon route intact, keeps the arrival small (one dungeon floor, one town's Atla), and gives the first Ixion trip a reason to exist beyond spectacle.

## 8. Character explanations

How each cast member from the other world is explained when they appear. Canon anchor first, then the proposed Ixion explanation.

| Character | Canon anchor | Ixion explanation [proposal] |
|---|---|---|
| Toan (DC1) | Blue Atlamillia from the Fairy King; Norune | A Terra native. Ixion does not move him. The Atla opening brings the Norune station to him. |
| Xiao (DC1) | Half-cat from Seda's Changing Potion | Passenger from the potion's time residue. Ixion reads the residue, which explains why she can exist in both eras. |
| Goro (DC1) | Matataki; earrings that let him understand forest creatures | Native passenger who only appears at the Terra station, never packed in Atla. He travels only with a Treant's blessing. |
| Ruby (DC1) | Genie found in a lamp in the Queens shipwreck | Genie as container. The lamp is an Atla-like vessel, so Ruby travels packed. |
| Ungaga (DC1) | Muska Lacka desert; the Sun and Moon Temple | Native passenger. The Sun and Moon Temple's alignment is the natural Terra-side anchor for a second station. |
| Osmond (DC1/DC2) | Moon People leader; Luna Labs researcher | Lineage title (see section 5). |
| Max (DC2) in Terra | Red Atlamillia (Earth Stone) | Arrives through the Ixion Atla opening. The red stone is his key. |
| Monica (DC2) in Terra | Blue Atlamillia (Moon Stone) | Arrives through the same opening. Her Moon Stone matches the Moon People's Terra lineage. |

## 9. Canon constraints Ixion must not break

- **Fixed deaths.** Crest, Gaspard, Flotsam, Seda, Flagg, Sophia (revived by Toan in DC1), Griffon/Sirus, and the Dark Genie stay dead or defeated. Ixion can revisit them only as memory, a time-residue, or a lineage, never by reversing the death.
- **Atlamillia count.** DC2 states that there are three Atlamillia. DC1 shows at least one more (Toan's), and Seda's stone is also in play. This is unresolved. Option: DC1's Atla stones are the same class, and the count of three is a DC2 statement about its own world. Ixion has to choose which world's count governs the merged world.
- **Terra's date.** Never stated. Ixion should not commit a year for Terra until a canon source exists.
- **Endings.** DC2's ending has Monica in Max's time with the Atlamillia gone and time travel forbidden. Ixion is a deliberate contradiction of that ending. The design has to name it as a post-canon branch, not as a retcon.

## 10. Open questions

1. Does DC2's "three Atlamillia" statement govern the merged world, or does DC1's Toan-plus-Seda count?
2. Is Osmond one person across time or a lineage title? (Recommendation: lineage.)
3. Does Terra sit inside Ixion's 10,000-year reach, or in a separate stream? (Recommendation: inside, with an Atla opening.)
4. Which station keys open Atla for non-Atlamillia holders? (Luna Stone Shards are the candidate.)
5. Should Ixion's first trip be Norune only, or should it include the Yellow Drops moon stop? (Recommendation: Norune only, to keep the asset cost low.)

## 11. Recommendation

Ship the lore frame A plus C. Start with one Terra arrival (Norune, Divine Beast Cave floors) and one Atla-packed passenger. Defer any content crossover (rendering Max inside DC1's engine, or Toan inside DC2's) until the packing and unpacking rules are proven on one passenger.

The lore gives Ixion three things an engineering-only design lacks: a reason the train reaches Terra (Atla preserve it), a reason the passenger survives the trip (Atla pack it), and a reason the cast is where it is (Max and Monica chase Griffon's time period, and Ixion's first detour goes to the Atla the Fairy King left behind).

## Sources

Local wiki articles (fandom dump):

- Dark Cloud; Dark Chronicle
- Toan; Maximilian; Monica Raybrandt; Dark Genie
- Palm Brinks; Underground Water Channel; Divine Beast Cave; Norune Village
- Gundorada Workshop; Georama; Inventing; Spheda

Wiki title index (existence only, content not fetched): Ixion; Lunatic Wisdom Laboratories; Station; Veniccio Station; Balance Valley Station; Sindain Station.

Decomp sources (paths relative to the repository, prefixes as in the Ixion README):

- `chronicle:ps2/include/dungeon.h` (`DUNGEON_GALLERY_OF_TIME`)
- `chronicle:tools/textpack/strings/titles.json` (localised names, including the Luna factory string)
- `chronicle:ps2/include/itemdata.hpp` (`ITEM_WEAPON_ATLAMILLIA_SWORD`)
