# Lore: time travel, Ixion and the two worlds

## What this covers

How time travel works in the story and gameplay of Dark Chronicle (DC2, called Dark Cloud 2 in the US), what Ixion is and when it appears, the canon links back to Dark Cloud (DC1), and a short proposed premise for Ixion crossing between the two worlds.

Sources, in order of weight:

- Pulled wiki text in `docs/fandom/` (Dark_Chronicle, Dark_Cloud, Monica_Raybrandt, Maximilian, Toan, Dark_Genie, Palm_Brinks, Gundorada_Workshop, Items, Georama and others).
- TCRF pages in `docs/tcrf/` (the DC2 Debug Menu page gives event-flag labels and map IDs).
- Extracted DC2 event scripts and asset folders (names and paraphrase only; the data is git-ignored and not redistributed).
- Chronicle and ChronicleTwo source enums and identifiers, cited where they exist.
- A few web pages. The Dark Cloud fandom wiki returned HTTP 402 to direct fetch, so its Ixion, Starglass and Gallery of Time pages were not read. Claims that rest only on search snippets are marked.

## Key facts

- DC2 is set roughly 100 years apart across two protagonists. Max (Maximilian) lives in Palm Brinks; Monica Raybrandt lives 100 years ahead. (`docs/fandom/Dark_Chronicle.wiki`, `docs/fandom/Monica_Raybrandt.wiki`)
- The DC2 wiki states the story, setting and characters are "completely unrelated" to DC1, but Georama, Atlamillia, several items and locales, and four original characters (Master Utan is the only one named) return. (`docs/fandom/Dark_Chronicle.wiki`)
- Three Atlamillia exist in DC2: Max's red (Earth Stone), Monica's blue (Moon Stone), and Emperor Griffon's gold (Sun Stone). Monica can travel back 100 years; Max's stone sends him 100 years forward. (`docs/fandom/Monica_Raybrandt.wiki`, `docs/fandom/Maximilian.wiki`, `docs/fandom/Dark_Chronicle.wiki`)
- DC1's Toan also carries a blue Atlamillia, but its power in DC1 is to open Atla (sealed objects) and keep their contents in the Atlamillia, not to move through time (`docs/fandom/Toan.wiki`, `docs/fandom/Georama.wiki`). (`docs/fandom/Toan.wiki`, `docs/fandom/Georama.wiki`)
- Ixion is the time-travelling locomotive built at the Lunatic Wisdom Laboratories ("Luna Labs"). A DC2 research event describes it as a non-stop express that can cross time and space, and says its first job is to reach Griffon ten thousand years in the past. (`chronicletwo: event/e400/e448/e448_1.txt`, extracted data; `docs/fandom/Monica_Raybrandt.wiki` Chapter 4 and 5)
- Ixion's in-game name appears on the soundtrack as track 46 of disc 1, "Launch!! Space Time Train Ixion". (`docs/fandom/Dark_Chronicle.wiki`, soundtrack table)
- Ixion's story timeline: research is complete in Chapter 4 (event flag 448, "Research Complete: The Train That Crosses Time"); construction finishes in Chapter 5 (Heim Rada / Paznos arc); Ixion departs in Chapter 6 (event flag 600, "Ixion Departs: Setting Off To The Future"). Chapter-to-folder mapping (e4xx = Ch4 and so on) is inferred from the wiki chapter sections plus these flags. (`docs/tcrf/Dark Cloud 2_Debug Menu - The Cutting Room Floor.html`; `docs/fandom/Monica_Raybrandt.wiki`)
- Whether Ixion flies is not established: the departure event says the train "can travel through space and time" (`chronicletwo: event/e600/e600/e600_1.txt`), and no line in the cited scripts says it flies (unverified). Its maps are listed in the DC2 Debug Menu page: Moon Flower Palace surfacing (s35), Ixion Outer (s36), Engine Room (s37), Guest Room (s38), plus "Inside of Train" (s07) and "Inside of Locomotive" (s08). (`docs/tcrf/Dark Cloud 2_Debug Menu - The Cutting Room Floor.html`; `chronicletwo: event/e600/e600/e600_1.txt`)
- Ixion is piloted by Osmond on departure from Luna Labs. Osmond is also DC1's Moon People leader; the name is shared. (`docs/fandom/Monica_Raybrandt.wiki` Chapter 5; `docs/fandom/Dark_Cloud.wiki`)
- Starglass: a rare item that "can turn back time" and transport people to the past. Its in-game description says it can reverse the flow of time, and the event script adds that it only turns back time to a moment of deep significance to the user. (`docs/fandom/Items.wiki`; `chronicletwo: event/e300/e368/e368_1.txt`, extracted data)
- Starglass is sold at a "Star Items" shop in Starlight Temple once Georama Progress 2 is reached (TCRF event flag 368, labelled "Item Shop (Starglass)"; DC2 map IDs f02 "Starlight Temple", f02i06 "Star Items"). (`docs/tcrf/Dark Cloud 2_Debug Menu - The Cutting Room Floor.html`)
- Monica uses a Starglass in Chapter 3 to return to the Moon Crystal Lighthouse attack by the Death Ark, and again in Chapter 8 to reach Max's era at the Zelmite Mine. (`docs/fandom/Monica_Raybrandt.wiki`)
- Discrepancy: the Monica wiki says the Chapter 3 Starglass was bought at Starlight Temple. The Chapter 8 event script has Monica say she got a Starglass from Crest ("she" in the script); the wiki identifies the Great Sage in that role as Lin after Crest's death. Source of Chapter 8 Starglass is unresolved. (`chronicletwo: event/e800/e804/e804_1.txt`, extracted data)
- Time Gates are the in-world time-travel points. An early gate script (`event/e200/e250`, chapter inferred) says "Red brings you to the future, and blue to the past" (the two Atlamillia stones, used with the gate to move between eras), and a later script says a place with a Time Gate lets you "go directly into the future". Gate assets sit in `event/time_gate/red` and `event/time_gate/blue`. (`chronicletwo` extracted data: `event/e200/e250/e250_1.txt`, `event/e600/e616/e616_1.txt`, `event/time_gate/`)
- Origin points: Griffon destroyed origin points of future locations to stop a rebellion (Palm Brinks was spared). Restoring the past-side origin point makes the future location exist: Jurak's origin point at Sindain (Chapter 2, `docs/fandom/Monica_Raybrandt.wiki`). Gundorada Workshop's origin point was destroyed (`docs/fandom/Gundorada_Workshop.wiki`); the pulled text shows Max and Monica restoring the workshop at Heim Rada in the Chapter 5 section, but does not explicitly say its origin point was restored (unverified).
- Gallery of Time is a DC1 location. Chronicle has `WORLD_PLACE_GALLERY_OF_TIME = 14` (`chronicle:ps2/include/battlemenu.hpp:296`) and it appears in the six-dungeon list (`chronicle:ps2/src/battlemenu.cpp:10206`; `:10165` is a per-map place table entry, not the list). DUNGEON_GALLERY_OF_TIME is handled in `chronicle:ps2/src/dungeonmap.cpp:3297`, `chronicle:ps2/src/monstorunit.cpp:506`, and `chronicle:ps2/src/dun/gameloop.cpp:2702`.
- The Chronicle port formats Gallery floors as years-ago in Discord presence (`chronicle:port/src/presence.cpp:38` and `:88`; a test expects "Gallery of Time · 102 Years Ago" for floor 6, `chronicle:port/src/tests/platform_discord_test.cpp:152`). Fandom-derived floor data for the same dungeon lists 382 and 400 years ago for the last two floors (`almarsguides.com` Dark Cloud Gallery of Time walkthrough, fetched) (unverified: the walkthrough is not in the local sources).
- DC1's Gallery of Time is where Seda's memories are stored; Toan views them to learn the Dark Genie's origin, can not stop its creation, and then uses the Atlamillia to revive Sophia. Seda opened the Gallery in his last moments. (`docs/fandom/Dark_Cloud.wiki`, `docs/fandom/Dark_Genie.wiki`)
- The Dark Genie returns in DC2 in the Zelmite Mine epilogue, where the fight is a DC1 boss returning. The DC1 Dark Genie infobox lists "Zelmite Mine (Dark Cloud 2)" as residence, and the DC2 wiki links "Dark Genie" to "Fake Genie". (`docs/fandom/Dark_Genie.wiki`, `docs/fandom/Monica_Raybrandt.wiki`; TCRF "Vs. Zelmite Dark Genie" event label)
- Chronicle and ChronicleTwo share Georama as a mechanic. DC1 uses Atla (sealed objects) and DC2 uses Geostones (dungeon drops) with Carpenterion. (`docs/fandom/Georama.wiki`, `docs/fandom/Dark_Chronicle.wiki`)
- The DC2 Ch6 "Chrono Union" at Kazarov Stonehenge syncs Paznos across eras by gathering gems from four dungeons. Kazarov Stonehenge exists as a map in DC2 (debug IDs s11, s66, s98). (`docs/fandom/Monica_Raybrandt.wiki` Chapter 6; `docs/tcrf` Debug Menu page)

Canon link summary (places, characters, items), as found in the sources above:

- Places: Dark Heaven Castle and Gallery of Time are DC1 places; no DC2 use was found in the pulled text. Underground Water Channel is a DC2 dungeon (Chapter 1) per `docs/fandom/Underground_Water_Channel.wiki`. Moon Flower Palace is a DC2 flying palace; its relation to DC1's moon locations (Moon Sea, Yellow Drops) is not stated in the sources. DC1's place enum (`chronicle:ps2/include/battlemenu.hpp:282-297`) lists Norune, Divine Beast Cave, Matataki, Wise Owl Forest, Queens, Shipwreck, Muska Lacka, Sun and Moon Temple, Yellow Drops, Moon Sea, Gallery of Time, and Demon Shaft.
- Characters shared by name: Osmond (DC1 Moon People leader; DC2 Moon Person and Luna Labs pilot), Master Utan (DC1 forest guardian; the DC2 wiki says he reappears), Dark Genie (DC1 final boss; DC2 Zelmite Mine fight). Seda and Sophia are DC1 story figures; no DC2 appearance was confirmed. Each game's playable cast is separate (Max and Monica in DC2; Toan, Xiao, Goro, Ruby, Ungaga and Osmond in DC1).
- Items shared by name or role: Atlamillia (DC1 Atla keeper; DC2 time key), Georama (both games), Time Bomb (DC2 item from Gundorada, per the Chapter 5 summary). Starglass is DC2 only. An early DC2 item-translation list in TCRF also has a Magic Cherry described as stopping and starting time; its relation to the Starglass is unknown.

## How it works

### Time travel in the DC2 story

1. Atlamillia are the story's time keys. Each holder can move between their own era and the other (100 years, forward or back). Griffon's gold stone lets him reach 10,000 years back and move a palace through time. (`docs/fandom/Monica_Raybrandt.wiki`, `docs/fandom/Dark_Chronicle.wiki`)
2. Starglass is the consumable/item route: it reverses the flow of time, so it can carry people to the past without holding an Atlamillia. It is used at story beats in Chapter 3 and Chapter 8. (`docs/fandom/Items.wiki`, `docs/fandom/Monica_Raybrandt.wiki`)
3. Ixion is the long-range route. After Ch4 research and Ch5 construction it departs Luna Labs for Griffon's era, roughly 10,000 years back. The story puts the Ch6 palace arc on it. (`chronicletwo` event e448, e600; `docs/fandom/Monica_Raybrandt.wiki`)
4. Restoration pays off in both eras. Each rebuilt past location (origin point, Georama progress) changes the future version of the same place. The DC2 wiki's summary is that rebuilding the past restores the future. (`docs/fandom/Dark_Chronicle.wiki`, Georama section)

### Time travel in gameplay

1. Georama work in the present unlocks future shops, people and places (`docs/fandom/Dark_Chronicle.wiki`, Georama system; the unlock conditions are not traced in the scripts, unverified). The red Time Gate takes the player to the future and the blue gate to the past (see Key facts). The gating condition for each gate is not verified.
2. Starglass sales and Georama progress may gate each other: the TCRF debug label for flag 368 is "Georama Progress 2: Item Shop (Starglass)", which matches a Star Items shop unlock, but no shop code was checked (unverified). Flag 352 is labelled "Using The Starglass" and does not by itself gate the shop.
3. Ixion is a player-driven travel system in DC2 after Chapter 6. The Chapter 6 script (`chronicletwo: event/e600/e616/e616_1.txt`) says that "by using the Ixion's time travel system" you can "jump to any place you like in this time or the future", and that the Ixion's time travel system can be controlled remotely. The same script says a place with a Time Gate lets you "go directly into the future". The DC2 Debug Menu page lists the Ixion interior and exterior maps as shared scenes. Whether the travel menu is reachable from the map menu is not verified.

### DC1 Gallery of Time

DC1's Gallery of Time is a time-travelling dungeon. Its floors step back through years of Seda's memory, with the final floor around 400 years back (almars walkthrough, unverified). Chronicle's code treats it as one of six dungeons with years-ago display text, and it has special-case floor logic (`chronicle:ps2/src/monstorunit.cpp:1339`, `chronicle:ps2/src/dun/gameloop.cpp:4150`). What those special cases do in detail was not traced. Its story role is memory and origin, not transport.

## Ixion hooks

1. Travel menu (Ixion as a destination picker). The Chapter 6 script (`chronicletwo: event/e600/e616/e616_1.txt`) describes an Ixion time travel system that lets the player jump to any place in this time or the future, so a destination picker has story support. The DC2 map list (s36, s37, s38, s07, s08) gives Ixion scenes, and grep for "ixion" in `chronicletwo: ps2/src` and `port/src` finds no identifier. Hook candidate: add a travel option once the map and event flags for Ixion are known. Blocker: the menu owner has not been located yet.
2. Gating by event flags. Use DC2 flag 448 (train research) and flag 600 (Ixion departs) as preconditions for any Ixion travel option, so the port matches story progression. Source of flag numbers: TCRF debug labels.
3. Time Gate siblings. Treat Ixion as a third traversal beside the red and blue Time Gates (`chronicletwo` extracted `event/time_gate/`). Same data layout can host an Ixion travel event.
4. Starglass shop as ticket office. The Star Items shop (f02i06) already sells the time item; an Ixion ticket or cross-world rail pass could sit next to it. This is a design option, not evidence.
5. Gallery of Time as the cross-world anchor. The DC1 dungeon (`chronicle:ps2/include/battlemenu.hpp:296`, `chronicle:port/src/presence.cpp:88`) already displays years-ago floors, so a cross-world entry point can reuse its floor-year label.
6. Zelmite Mine encounter. The DC2 Chapter 8 Dark Genie fight is the existing place where DC1 content surfaces; a crossover encounter could reuse its event flags.
7. Atlamillia as keys. Red (Max), blue (Monica, Toan), gold (Griffon) stones are the story's time keys; Ixion could require one or more to start a crossing.

### Proposed premise (inference, not canon)

Two years after the Griffon finale, Luna Labs notices a resonance in Ixion's time-drive log that matches the Gallery of Time's old memory signature. Dr. Nobb's team tunes the train with a red and a blue Atlamillia and finds the resonance opens a crossing to the Dark Cloud era. Max and Monica board Ixion to follow it and arrive in Terra, where Toan and Xiao are rebuilding Norune with Atla. The crossing only stays open while both worlds supply Atla or Geostones, so each cast has to help the other to keep the train running. The residue of the Dark Genie (the Fake Genie in the Zelmite Mine) is the cargo nobody wants to carry, and it is the reason Ixion can find the crossing at all. The premise keeps the two timelines separate in canon terms and only adds a rail link between them.

## Risks and blockers

- The Dark Cloud fandom wiki returned HTTP 402 to WebFetch. Its Ixion, Starglass and Gallery of Time pages were not read. Only search snippets were available, and those are marked as unverified. Use the local pulled wiki text and TCRF for now, or fetch the pages later with another method.
- Canon tension: the DC2 wiki says the story and characters are "completely unrelated" to DC1. A merge has to be framed as fan crossover, not canon.
- Chronicle and ChronicleTwo both use Georama, but the Atla (DC1) and Geostone (DC2) mechanics differ. A shared travel system needs a mapping decision.
- Starglass source discrepancy between the Monica wiki and the Chapter 8 script.
- Ambiguous Dark Genie naming: "Dark Genie" in DC2 links to "Fake Genie". Any port text needs to be explicit about which entity it means.
- No Ixion-named identifier exists in `chronicletwo: ps2/src` or `port/src`. The train code path is not located, so hooks in this document are data-led.
- Chapter-to-folder mapping (e4xx = Ch4 and so on) is inferred, not verified against the chapter table.
- Publication constraint: this document cites script filenames and paraphrases. Do not paste script text or extracted assets into the public repo.

## Open questions

- Which four DC1 characters return in DC2 besides Master Utan? (`docs/fandom/Dark_Chronicle.wiki` says four, names only one.)
- Is the Gallery of Time reachable or referenced in DC2 at all? Local evidence shows it only in DC1 (WORLD_PLACE enum, OST track 40 in DC1).
- The brief's term "Gate of Time" was not found in local sources. Likely means the Time Gate (red and blue), but this is inference.
- Exact Ixion travel rules: is it a player-selectable destination picker after Ch6? The Ch6 script (`event/e600/e616/e616_1.txt`) says the player can jump to any place in this time or the future with the Ixion's time travel system; the menu and its conditions are not located (unverified).
- Is Starglass one-way (to the past) only, or does it carry the player forward too? Wiki text says "transport people to the past"; the script says it "reverses the flow of time".
- Who gave Monica the Chapter 8 Starglass? The script says Crest; the story says Lin took over as Great Sage. Verify against the event text in context.
- Unresolved editor map names EDIT_ANALYZE_MAP_SHARLOT and EDIT_ANALYZE_MAP_STERA (`chronicletwo: ps2/include/editanalyze.hpp:24-25`). The header comments call them towns analysed by AnalyzeSharlot and AnalyzeStera, but the town names are not mapped in the sources read.
- Does Kazarov Stonehenge's Chrono Union (Ch6) offer a model for Ixion-based cross-era sync? Inference only.
