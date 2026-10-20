#!/usr/bin/env python3
"""Private offline step: add DC1 Norune villagers to a converted Georama sandbox pack (GEORAMA-R3).

Input is an existing Georama pack directory (tools/georama_converter.py output: a hard-linked copy of the DC2 data
with the ``gix`` map). Output is a new pack directory that adds, for each villager of the profile:

* ``data/chara/<model>.chr``: the DC1 body converted by ``monster_converter.convert_villager`` (a DC2 townsperson),
* rows in ``data/place.cfg`` (``NPC_PLACE`` on map 5) and ``data/npc_place4.cfg`` (``NPC_INFO`` and an ``NPC`` block
  scheduled from the default progress), which DC2's own loaders read (vlgr_info.cpp LoadPlaceInfo, LoadNPCInfo),
* ``data/ix_villagers.txt``: one row per villager with the Georama part id, the villager id and the NPC spot
  (DC1 ``func_hito02`` of the house, in house-local units) that the port places the villager at,
* ``data/ix_vtext.txt``: the DC1 talk lines (English, from the DC1 ``.mes``) the port shows in DC2's message window.

Everything it writes is retail-derived and private. The base pack is only read; a changed file is replaced, never
written through its hard link.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import shutil
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dc1_mes  # noqa: E402
import monster_converter as mc  # noqa: E402
from room_converter import ConvertError, checked_span, parse_mds, transform_point, world_matrices  # noqa: E402

SANDBOX_MAP = 5
PLACE_NUM = re.compile(rb"NPC_PLACE_NUM\s+(\d+)\s*;")
INFO_NUM = re.compile(rb"NPC_INFO_NUM\s+(\d+)\s*;")
INFO_ROW = re.compile(rb"^NPC_INFO\s+(\d+)\s*,", re.M)
NPC_ROW = re.compile(rb"^NPC\s+(\d+)\s*;", re.M)
PLACE_ROW = re.compile(rb"^NPC_PLACE\s+(\d+)\s*,", re.M)


def scene_part(scene: bytes, name: str) -> bytes:
    """LOD0 visual of one EPARTS_ARCHIVE in a DC1 scene.scn (same slot georama_converter reads)."""
    if scene[:4] != b"SCN\0":
        raise ConvertError("not a DC1 scene archive")
    count = struct.unpack_from("<I", scene, 4)[0]
    checked_span(scene, 16, count * 48, "scene directory")
    for i in range(count):
        at = 16 + i * 48
        if scene[at:at + 16].split(b"\0", 1)[0] != name.encode():
            continue
        base = struct.unpack_from("<i", scene, at + 16)[0]
        checked_span(scene, base, 0xE0, "EPARTS_ARCHIVE")
        offset = struct.unpack_from("<i", scene, base + 0x48)[0]
        size = struct.unpack_from("<i", scene, base + 0x58)[0]
        if offset < 0xE0 or size <= 0:
            raise ConvertError("missing LOD0 slot")
        return bytes(checked_span(scene, base + offset, size, "LOD0 slot"))
    raise ConvertError(f"part not found: {name}")


def house_frames(scene: bytes, house: str) -> dict:
    """World position and yaw of every ``func_*`` frame of a house LOD0, in house-local units (scale 1)."""
    objects = parse_mds(scene_part(scene, house))
    matrices = world_matrices(objects, (0, 0, 0), 0)
    out = {}
    for obj, m in zip(objects, matrices):
        if obj["name"].startswith("func_"):
            x, y, z = transform_point(m, (0.0, 0.0, 0.0))
            fx, fz = m[2], m[10]  # the frame's local +Z axis in house space, as editevent.cpp reads matrix[2]
            out[obj["name"]] = {"pos": [round(x, 3), round(y, 3), round(z, 3)], "yaw": round(math.atan2(fx, fz), 4)}
    return out


def replace_private(path: Path, data: bytes) -> None:
    """Write a new file and swap it in, so a hard-linked source file is never modified."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".tmp-")
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    os.replace(tmp, path)


# DC1 Norune townspeople have no authored paths. Each one random-walks (editloop3.cpp EdSetVillagerNextPos): one
# 100-unit axis step chosen relative to its facing with weights forward 40, left 20, back 5, right 20, or wait 15, and
# a step into a blocked cell becomes a wait. DC2 villagers follow MOVE_TO/WAIT routes instead, so the same rules are
# sampled offline with a fixed seed into a route. The step is shortened and the walk confined to the open side of the
# house's NPC spot (no collision exists for DC2 townspeople), and the route ends back on the spot so DC2 can loop it.
ROUTE_WEIGHTS = (("fwd", 40), ("left", 20), ("back", 5), ("right", 20), ("wait", 15))
ROUTE_STEP = 60.0
ROUTE_FRONT = 120.0   # how far outward (spot yaw direction) the walk may go
ROUTE_SIDE = 90.0     # how far to either side
ROUTE_WAIT_FRAMES = 60  # DC1 waits 60 frames when it does not move


def sample_route(seed: int, spot: dict, decisions: int = 10) -> list:
    """House-local route nodes: ``("move", x, y, z, yaw)`` and ``("wait", frames)``; the last move returns to the spot."""
    import random
    rng = random.Random(seed)
    quarter = round(spot["yaw"] / (math.pi / 2))
    out_axis = (round(math.sin(quarter * math.pi / 2)), round(math.cos(quarter * math.pi / 2)))  # (x, z) of +u
    side_axis = (out_axis[1], -out_axis[0])  # (x, z) of +v
    sx, sy, sz = spot["pos"]

    def world(u: float, v: float) -> tuple:
        return (round(sx + u * out_axis[0] + v * side_axis[0], 1), sy, round(sz + u * out_axis[1] + v * side_axis[1], 1))

    pos, facing = (0.0, 0.0), (1, 0)  # (u, v) and the facing axis in (u, v)
    nodes: list = []

    def move_to(u: float, v: float) -> None:
        a, b = world(*pos), world(u, v)
        yaw = round(math.atan2(b[0] - a[0], b[2] - a[2]), 2)
        nodes.append(("move", b[0], b[1], b[2], yaw))

    def wait() -> None:
        nodes.append(("wait", ROUTE_WAIT_FRAMES))

    for _ in range(decisions):
        names, weights = zip(*ROUTE_WEIGHTS)
        choice = rng.choices(names, weights)[0]
        if choice == "wait":
            wait()
            continue
        direction = {"fwd": facing, "back": (-facing[0], -facing[1]), "left": (-facing[1], facing[0]),
                     "right": (facing[1], -facing[0])}[choice]
        target = (pos[0] + direction[0] * ROUTE_STEP, pos[1] + direction[1] * ROUTE_STEP)
        if not (0.0 <= target[0] <= ROUTE_FRONT and abs(target[1]) <= ROUTE_SIDE):
            wait()  # blocked cell
            continue
        move_to(*target)
        pos, facing = target, direction
        wait()
    if pos != (0.0, 0.0):
        move_to(0.0, 0.0)
    wait()
    if not any(n[0] == "move" for n in nodes):
        raise ConvertError("sampled route never moves")
    return nodes


def route_rows(route: list) -> str:
    out = "\tMOVE_MOTION \"walk\";\r\n"
    for node in route:
        if node[0] == "move":
            out += f"\tMOVE_TO {node[1]:.1f},{node[2]:.1f},{node[3]:.1f},{node[4]:.2f};\r\n"
        else:
            out += f'\tWAIT "cnt",{node[1]},"stand";\r\n'
    return out


def place_rows(villagers: list) -> bytes:
    out = b""
    for v in villagers:
        x, y, z = v["spot"]["pos"]
        out += (f'//***;\r\n//Ixion sandbox: {v["name"]} (DC1 {Path(v["dc1_chr"]).stem}) at his Georama house\r\n'
                f'NPC_PLACE  {v["place_id"]} , {SANDBOX_MAP} ;\r\n\tPLACE_POS {x:.1f},{y:.1f},{z:.1f},{v["spot"]["yaw"]:.2f};\r\n'
                f'{route_rows(v["route"]) if v.get("route") else ""}'
                'NPC_PLACE_END;\r\n').encode("ascii")
    return out

def patch_place_cfg(text: bytes, villagers: list) -> bytes:
    match = PLACE_NUM.search(text)
    if not match:
        raise ConvertError("place.cfg has no NPC_PLACE_NUM")
    count = int(match[1])
    used = {int(m[1]) for m in PLACE_ROW.finditer(text)}
    for v in villagers:
        if v["place_id"] != count + villagers.index(v) or v["place_id"] in used:
            raise ConvertError(f"place id {v['place_id']} must extend the table contiguously from {count}")
    text = text[:match.start()] + b"NPC_PLACE_NUM %d;" % (count + len(villagers)) + text[match.end():]
    if not text.endswith(b"\n"):
        text += b"\r\n"
    return text + place_rows(villagers)


def patch_npc_cfg(text: bytes, villagers: list, model_names: dict) -> bytes:
    match = INFO_NUM.search(text)
    if not match:
        raise ConvertError("npc_place4.cfg has no NPC_INFO_NUM")
    infos = [(int(m[1]), m.start()) for m in INFO_ROW.finditer(text)]
    ids = [i for i, _ in infos]
    taken = ids + [int(m[1]) for m in NPC_ROW.finditer(text)]
    for v in villagers:
        if v["vlgr_id"] in taken or not 0 <= v["vlgr_id"] < mc_vlgr_place_max():
            raise ConvertError(f"villager id {v['vlgr_id']} is taken or outside the place table")
    # The info table is searched by binary search: insert each row in id order.
    rows = sorted(villagers, key=lambda v: v["vlgr_id"])
    for v in rows:
        row = (f'NPC_INFO  {v["vlgr_id"]} ,"{model_names[v["vlgr_id"]]}",-1,"","",-1 ,-1 ;\r\n').encode("ascii")
        after = [start for i, start in infos if i > v["vlgr_id"]]
        at = after[0] if after else text.index(b"\n", infos[-1][1]) + 1
        text = text[:at] + row + text[at:]
        infos = [(int(m[1]), m.start()) for m in INFO_ROW.finditer(text)]
    match = INFO_NUM.search(text)
    text = text[:match.start()] + b"NPC_INFO_NUM  %d ;" % (int(match[1]) + len(villagers)) + text[match.end():]
    blocks = b""
    for v in villagers:
        blocks += (f'NPC  {v["vlgr_id"]} ;//Ixion sandbox {v["name"]}\r\n\tPROGRESS  1 , 0 ,"default";\r\n'
                   f'\t\tNOON_PLACE  {v["place_id"]} ;\r\n\t\tNIGHT_PLACE  {v["place_id"]} ;\r\n\tPROGRESS_END;\r\nNPC_END;\r\n').encode("ascii")
    at = INFO_NUM.search(text).start()
    return text[:at] + blocks + text[at:]


def mc_vlgr_place_max() -> int:
    return 0x200  # VLGR_PLACE_MAX (vlgr_info.hpp)


def load_profile(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids = [v["vlgr_id"] for v in doc["villagers"]]
    places = [v["place_id"] for v in doc["villagers"]]
    parts = [v["part_id"] for v in doc["villagers"]]
    if len(set(ids)) != len(ids) or len(set(places)) != len(places) or len(set(parts)) != len(parts):
        raise ConvertError("profile repeats a villager, place or part id")
    for v in doc["villagers"]:
        if not re.fullmatch(r"[A-Za-z0-9 ]{1,15}", v["name"]):
            raise ConvertError(f"bad name {v['name']!r}")
    return doc


def talk_rows(dc1: Path, v: dict) -> list:
    table = dc1_mes.read_mes((dc1 / v["mes"]).read_bytes())
    rows = []
    for mid in v["mes_ids"]:
        if mid not in table:
            raise ConvertError(f"{v['mes']} has no message {mid}")
        pages = dc1_mes.to_pages(table[mid])
        if not pages:
            raise ConvertError(f"message {mid} decoded to nothing")
        rows.append({"id": mid, "pages": pages})
    return rows


def prepare(dc1: Path, base: Path, output: Path, profile: dict, workdir: Path) -> dict:
    if output.exists():
        raise ConvertError("output already exists; choose a new private directory")
    scene = (dc1 / "gedit/e01/scene.scn").read_bytes()
    base_prov = json.loads((base / "georama-provenance.json").read_text(encoding="utf-8"))
    placed_ids = {p["id"] for p in base_prov["parts"]}
    villagers = copy.deepcopy(profile["villagers"])
    packs, model_names = {}, {}
    for v in villagers:
        if v["part_id"] not in placed_ids:
            raise ConvertError(f"part {v['part_id']} is not in the base pack")
        frames = house_frames(scene, v["house"])
        if v["spot_frame"] not in frames:
            raise ConvertError(f"{v['house']} has no {v['spot_frame']} (has {sorted(frames)})")
        v["spot"] = frames[v["spot_frame"]]
        v["route"] = sample_route(v["vlgr_id"], v["spot"])
        v["frames"] = frames
        out = workdir / f"pack-{Path(v['dc1_chr']).stem}"
        prov = mc.convert_villager(dc1 / v["dc1_chr"], out, scale=profile.get("scale", 1.0), display_name=v["name"])
        v["model"] = prov["output_model"]
        v["pack_sha256"] = prov["output_chr_sha256"]
        model_names[v["vlgr_id"]] = prov["output_model"]
        packs[v["vlgr_id"]] = out
        v["talk"] = talk_rows(dc1, v)
    shutil.copytree(base / "data", output / "data", copy_function=os.link)
    shutil.copytree(base / "port_data", output / "port_data", copy_function=os.link)
    for name in ("data.json", "georama-provenance.json", "world_collision.mds"):
        if (base / name).is_file():
            shutil.copyfile(base / name, output / name)
    replace_private(output / "data/place.cfg", patch_place_cfg((base / "data/place.cfg").read_bytes(), villagers))
    replace_private(output / "data/npc_place4.cfg",
                    patch_npc_cfg((base / "data/npc_place4.cfg").read_bytes(), villagers, model_names))
    catalog = json.loads((base / "port_data/catalog.json").read_text(encoding="utf-8"))
    for v in villagers:
        src = packs[v["vlgr_id"]]
        shutil.copyfile(src / "data/chara" / f"{v['model']}.chr", output / "data/chara" / f"{v['model']}.chr")
        vcat = json.loads((src / "port_data/catalog.json").read_text(encoding="utf-8"))
        catalog["sources"].extend(vcat["sources"])
        for png in (src / "port_data").rglob("*.png"):
            rel = png.relative_to(src / "port_data")
            (output / "port_data" / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(png, output / "port_data" / rel)
    replace_private(output / "port_data/catalog.json", json.dumps(catalog).encode())
    rows = "".join(f'{v["vlgr_id"]} {v["part_id"]} {v["spot"]["pos"][0]} {v["spot"]["pos"][1]} {v["spot"]["pos"][2]} '
                   f'{v["spot"]["yaw"]} {v["model"]}\n' for v in villagers)
    replace_private(output / "data/ix_villagers.txt", ("# vlgr_id part_id x y z yaw model (house-local NPC spot)\n" + rows).encode())
    text = ""
    for v in villagers:
        for row in v["talk"]:
            # DC2 message text: a literal backslash-n is a line break (PreMesMake) and <page> ends a page (nd_meswin.cpp:2032).
            if any(c in "<>\t" for p in row["pages"] for c in p):
                raise ConvertError(f"message {row['id']} holds a character DC2 text reserves")
            text += f'{v["vlgr_id"]}\t' + "<page>".join(p.replace("\n", "\\n") for p in row["pages"]) + "\n"
    replace_private(output / "data/ix_vtext.txt", text.encode("ascii", "replace"))
    provenance = {"schema_version": 1, "base_pack": str(base), "profile_sha256": mc.sha256(json.dumps(profile, sort_keys=True).encode()),
                  "villagers": [{k: v[k] for k in ("name", "part_id", "vlgr_id", "place_id", "model", "pack_sha256", "spot_frame", "spot",
                                                   "frames", "dc1_chr", "mes", "mes_ids", "route")} for v in villagers],
                  "overlay_rows": {"place_cfg_added": len(villagers), "npc_cfg_added": len(villagers)},
                  "talk_pages": {str(v["vlgr_id"]): [len(r["pages"]) for r in v["talk"]] for v in villagers}}
    replace_private(output / "georama-villagers.json", json.dumps(provenance, indent=2).encode())
    return provenance


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dc1-root", type=Path, required=True)
    ap.add_argument("--base-pack", type=Path, required=True)
    ap.add_argument("--profile", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix="villagers-") as work:
            prov = prepare(args.dc1_root, args.base_pack, args.output, load_profile(args.profile), Path(work))
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(prov, indent=2))
    except (ConvertError, OSError, KeyError, ValueError) as error:
        ap.exit(2, f"georama-villagers: {error}\n")


if __name__ == "__main__":
    main()
