# Ixion

Ixion is an experiment in joining Dark Cloud (Chronicle) and Dark Chronicle
(ChronicleTwo) into one game: play any character from either cast, visit any
town or dungeon from either world, and use Dark Chronicle's time travel to
cross between the two. It is named after the flying, time-travelling train
built at the Lunatic Wisdom Laboratories in Dark Chronicle.

This is a proof of concept on a branch of ChronicleTwo. Nothing here is meant
for upstream as-is. Both games' data come from the user's own discs, as for
the two ports; no game data is stored in this repository.

## Layout

- `ixion/docs/research/` notes on how each game and the shared Kazarov build
  work, written while exploring them for Ixion.
- `ixion/docs/` the Ixion design: architecture, the station catalogue, the
  crosswalks between the two games' characters, items and maps.
- `ixion/tools/` analysis and conversion scripts.

Source references use `chronicle:`, `chronicletwo:` and `kazarov:` prefixes for
paths inside TheMoonPeople/Chronicle, TheMoonPeople/ChronicleTwo and
TheMoonPeople/Kazarov.
