#!/usr/bin/env python3
"""Build the atmosphere.json sidecar for a converted DC1 room.

The sidecar carries what room.json v1 does not: the donor floor's music and its fog and light.
Music: DC1 dungeon entry runs SndBgmLoad(selectMapNo + 100) then SndBgmPlay(0)
(chronicle ps2/src/dun/gameloop.cpp:1843-1844), and SndBgmPlay(n) plays the n-th sequence the
pack's bgmN.txt lists (chronicle port/src/sound.cpp LoadSoundFileFromPack/RegisterSequence).
The DC1 pack has the same PACK_ENTRY layout DC2 reads, but DC2's sndLoadSound also needs a
DC2-style .cfg and a .vol member (chronicletwo port/src/snd_mngr.cpp:209-215). This tool repacks
DC1's own .hd/.bd/.sq bytes unchanged and synthesises those two text members from DC1's tables:
sound/tbl/sqtbl.txt gives each sequence's volume and the pack's bgmN.cfg its REVERBE line.

Fog and light: DC1 TEIGIMdsLoad (chronicle ps2/src/itemdata.cpp:731-786) reads
  LIGHT_C dx, dy, dz, r, g, b, slot   (direction normalised into main_light column slot-1,
                                       colour into main_lightcolor row slot-1)
  AMBIENT r, g, b
  FOG near, far, r, g, b, far_value, near_value
  BG_COL r, g, b
and the dungeon loop applies them each frame with MGSetPLight/MGSetAmbient/MGSetFogParm
(chronicle ps2/src/dun/gameloop.cpp:2299-2303). DC2's mgSetFogParam takes the same seven
arguments with the same formula (chronicletwo ps2/src/mg_drawenv.cpp:424-443), so the values
carry over unchanged except that distances are scaled by the room's DC1->DC2 unit scale.

The outputs are retail-derived: write them only to private, git-ignored directories.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path

FORMAT = "ixion-room-atmosphere"
VERSION = 1
MAX_PACK = 16 * 1024 * 1024
ENTRY = 80  # name[64], offset, size, next, reserved


class AtmosError(ValueError):
    pass


def read_pack(data: bytes) -> list[tuple[str, bytes]]:
    """Members in pack order. Retail DC1 music packs end their list with a zero-size entry whose
    name is not ASCII (the SJIS end mark of bgmN.txt); such entries are skipped."""
    if len(data) > MAX_PACK:
        raise AtmosError("pack exceeds 16 MiB")
    members: list[tuple[str, bytes]] = []
    pos = 0
    while True:
        if pos + ENTRY > len(data):
            raise AtmosError("truncated pack entry header")
        raw = data[pos:pos + 64].split(b"\0", 1)[0]
        if not raw:
            break
        offset, size, step = struct.unpack_from("<iii", data, pos + 64)
        if step < ENTRY or step % 16 or offset < ENTRY or size < 0 or offset > step or size > step - offset:
            raise AtmosError(f"invalid pack entry at {pos:#x}")
        if pos + offset + size > len(data):
            raise AtmosError(f"pack member at {pos:#x} leaves the file")
        try:
            name = raw.decode("ascii")
        except UnicodeDecodeError:
            if size != 0:
                raise AtmosError(f"non-ASCII member with data at {pos:#x}")
            name = None
        if name is not None:
            members.append((name, data[pos + offset:pos + offset + size]))
        pos += step
    return members


def write_pack(members: list[tuple[str, bytes]]) -> bytes:
    out = bytearray()
    for name, payload in members:
        encoded = name.encode("ascii")
        if not encoded or len(encoded) >= 64:
            raise AtmosError(f"bad member name {name!r}")
        step = ((ENTRY + len(payload) + 15) // 16) * 16
        out += encoded.ljust(64, b"\0")
        out += struct.pack("<iiii", ENTRY, len(payload), step, 0)
        out += payload
        out += b"\0" * (step - ENTRY - len(payload))
    out += b"\0" * ENTRY
    return bytes(out)


def sequence_order(txt: bytes) -> tuple[str, list[str]]:
    """The bank and the sequences a DC1 bgmN.txt lists, in SndBgmPlay index order."""
    bank = None
    sequences: list[str] = []
    for line in txt.replace(b"\r", b"").split(b"\n"):
        name = line.strip()
        if len(name) < 9:
            continue
        try:
            text = name[:9].decode("ascii")
        except UnicodeDecodeError:
            continue
        if text.endswith(".hd") and bank is None:
            bank = text
        elif text.endswith(".sq") and text[5] == "a":  # slot letter 'a' is the BGM port
            sequences.append(text)
    if bank is None or not sequences:
        raise AtmosError("bgm list names no bank or no BGM sequence")
    return bank, sequences


def sq_volumes(table: bytes) -> dict[str, int]:
    volumes: dict[str, int] = {}
    for line in table.decode("ascii", "replace").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1].lstrip("-").isdigit():
            volumes[parts[0].casefold()] = int(parts[1])
    return volumes


def dc1_reverb(cfg: bytes | None) -> tuple[int, int] | None:
    if not cfg:
        return None
    match = re.search(rb"REVERBE\s+(-?\d+)\s*,\s*(-?\d+)", cfg)
    return (int(match.group(1)), int(match.group(2))) if match else None


def dc2_volume(dc1_volume: int) -> int:
    """DC1 hands the table volume straight to the mixer (chronicle port/src/sound.cpp StartSequence);
    DC2 multiplies its .vol value by 2.015748 first (chronicletwo port/src/sound.cpp SQ_Play)."""
    return max(1, min(127, round(dc1_volume / 2.015748)))


def build_bgm_pack(dc1_pack: bytes, table: bytes, label: str) -> tuple[bytes, dict]:
    members = read_pack(dc1_pack)
    by_name = {name.casefold(): data for name, data in members}
    txt_name = next((n for n, _ in members if n.lower().endswith(".txt")), None)
    if txt_name is None:
        raise AtmosError("DC1 music pack has no .txt list")
    bank, sequences = sequence_order(by_name[txt_name.casefold()])
    bd = bank[:-2] + "bd"
    for needed in [bank, bd, *sequences]:
        if needed.casefold() not in by_name:
            raise AtmosError(f"DC1 music pack lacks {needed}")
    volumes = sq_volumes(table)
    reverb = dc1_reverb(by_name.get(txt_name.casefold()[:-4] + ".cfg"))
    stem = Path(txt_name).stem
    # DC2 .cfg: a header row, then number name description category file program key flag.
    # The flag column carries the SJIS mark DC2's own BGM rows use.
    rows = [f"BG\t{label}\t{stem}".encode("ascii")]
    vol_rows = []
    if reverb is not None:
        vol_rows.append(f"REVERB\t{reverb[0]}\t{reverb[1]}".encode("ascii"))
    sequence_info = []
    for index, sequence in enumerate(sequences):
        base = sequence[:-3]
        rows.append(f"{index}\t{base}\t{base}\t0\t{sequence}\t*\t*\t".encode("ascii") + b"\x81\x9b")
        dc1_vol = volumes.get(sequence.casefold())
        if dc1_vol is None:
            raise AtmosError(f"sqtbl.txt has no volume for {sequence}")
        vol_rows.append(f"{index}\t{dc2_volume(dc1_vol)}".encode("ascii"))
        sequence_info.append({"index": index, "name": sequence, "dc1_volume": dc1_vol,
                              "dc2_volume": dc2_volume(dc1_vol)})
    rows.append(b"END")
    vol_rows.append(b"END")
    out_members = [(bank, by_name[bank.casefold()]), (bd, by_name[bd.casefold()])]
    out_members += [(s, by_name[s.casefold()]) for s in sequences]
    out_members += [(f"{stem}.vol", b"\n".join(vol_rows) + b"\n"),
                    (f"{stem}.cfg", b"\r".join(rows) + b"\r")]
    info = {"bank": bank, "sequences": sequence_info,
            "reverb": list(reverb) if reverb is not None else None}
    return write_pack(out_members), info


NUMBER = r"-?\d+(?:\.\d*)?"


def cfg_rows(cfg: bytes, keyword: str) -> list[list[float]]:
    rows = []
    pattern = re.compile(rb"^\s*" + keyword.encode() + rb"\s+(.*)$")
    for line in cfg.replace(b"\r", b"").split(b"\n"):
        line = line.split(b"//", 1)[0]
        match = pattern.match(line)
        if match:
            values = [float(v) for v in re.findall(NUMBER.encode(), match.group(1))]
            rows.append(values)
    return rows


def normalise(v: list[float]) -> list[float]:
    length = math.sqrt(sum(c * c for c in v))
    if not math.isfinite(length) or length < 1e-9:
        raise AtmosError("zero-length light direction")
    return [c / length for c in v]


def parse_room_cfg(cfg: bytes, scale: float) -> dict:
    lights = []
    for row in cfg_rows(cfg, "LIGHT_C"):
        if len(row) != 7:
            raise AtmosError(f"LIGHT_C needs 7 values, got {row}")
        slot = int(row[6])
        if not 1 <= slot <= 4:
            raise AtmosError(f"LIGHT_C slot {slot} outside 1..4")
        lights.append({"slot": slot, "direction": normalise(row[0:3]), "color": row[3:6]})
    fog_rows = cfg_rows(cfg, "FOG")
    if len(fog_rows) != 1 or len(fog_rows[0]) != 7:
        raise AtmosError("room cfg needs exactly one 7-value FOG line")
    near, far, r, g, b, far_value, near_value = fog_rows[0]
    ambient = cfg_rows(cfg, "AMBIENT")
    bg = cfg_rows(cfg, "BG_COL")
    result = {
        "fog": {"near": near * scale, "far": far * scale, "color": [int(r), int(g), int(b)],
                "far_value": far_value, "near_value": near_value,
                "dc1": fog_rows[0]},
        "lights": sorted(lights, key=lambda light: light["slot"]),
    }
    if ambient:
        if len(ambient[0]) != 3:
            raise AtmosError("AMBIENT needs 3 values")
        result["ambient"] = ambient[0]
    if bg:
        if len(bg[0]) != 3:
            raise AtmosError("BG_COL needs 3 values")
        result["bg_color"] = bg[0]
    return result


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(room_json: Path, dc1_data: Path, output: Path, map_no: int) -> dict:
    room = json.loads(room_json.read_text(encoding="utf-8"))
    if room.get("format") != "ixion-room" or room.get("version") != 1:
        raise AtmosError("not an ixion-room v1 room.json")
    donor = room["donor"]
    scale = float(room["units"]["scale"])
    cfg_source = next((s for s in donor["sources"] if s["path"].lower().endswith(".cfg")), None)
    if cfg_source is None:
        raise AtmosError("room.json names no donor cfg")
    cfg_path = dc1_data / "dun" / cfg_source["path"]
    cfg = cfg_path.read_bytes()
    if sha(cfg) != cfg_source["sha256"]:
        raise AtmosError(f"{cfg_path} does not match room.json's donor cfg hash")
    bgm_rel = f"sound/bgm/bgm{map_no + 100}.snd"
    bgm_bytes = (dc1_data / bgm_rel).read_bytes()
    table_rel = "sound/tbl/sqtbl.txt"
    table = (dc1_data / table_rel).read_bytes()
    pack, bgm_info = build_bgm_pack(bgm_bytes, table, donor["room"])
    output.mkdir(parents=True, exist_ok=True)
    (output / "bgm.snd").write_bytes(pack)
    document = {
        "format": FORMAT,
        "version": VERSION,
        "room": {"donor_room": donor["room"], "room_json_sha256": sha(room_json.read_bytes()), "unit_scale": scale},
        "bgm": {"pack": "bgm.snd", "pack_sha256": sha(pack), "sequence": 0,
                "dc1_set": map_no + 100, **bgm_info},
        **parse_room_cfg(cfg, scale),
        "sources": [{"path": f"dun/{cfg_source['path']}", "sha256": sha(cfg)},
                    {"path": bgm_rel, "sha256": sha(bgm_bytes)},
                    {"path": table_rel, "sha256": sha(table)}],
    }
    (output / "atmosphere.json").write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--room-json", type=Path, required=True)
    parser.add_argument("--dc1-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="private directory for atmosphere.json and bgm.snd")
    parser.add_argument("--map-no", type=int, default=0, help="DC1 selectMapNo of the donor dungeon (0 = Divine Beast Cave)")
    args = parser.parse_args(argv)
    try:
        document = build(args.room_json, args.dc1_data, args.output, args.map_no)
    except (AtmosError, OSError, KeyError, ValueError) as exc:
        print(f"room_atmosphere: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {args.output / 'atmosphere.json'}: bgm set {document['bgm']['dc1_set']} "
          f"sequences {[s['name'] for s in document['bgm']['sequences']]} fog {document['fog']['dc1']} "
          f"lights {len(document['lights'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
