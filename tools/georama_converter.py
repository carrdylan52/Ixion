#!/usr/bin/env python3
"""Private, offline Norune Georama part -> DC2 Georama sandbox preparer (tree by default, houses by profile).

Never modifies either dataset. Output must be a new directory. Native files are
hard-linked read-only by convention; every changed file is replaced atomically.
The tree keeps DC1 world units, at scale 1. Its collision triangles become a
DC2 vertex-only triangle list; placement areas 1/3/5 use an explicit bbox footprint.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from monster_converter import (build_pack, pack_members_ordered, rewrite_mds,
                               decode_chr_img, tim2_gstex1, _catalog_source, sha256,
                               read_mds, validate_mdt, mdt_header)
from room_converter import (ConvertError, checked_span, parse_collision_mds, parse_mds,
                            transform_point, world_matrices)


def scene_part(scene: bytes, name: str, offset_word: int, size_word: int) -> bytes:
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
        offset = struct.unpack_from("<i", scene, base + offset_word)[0]
        size = struct.unpack_from("<i", scene, base + size_word)[0]
        if offset < 0xE0 or size <= 0:
            raise ConvertError("missing part slot")
        return bytes(checked_span(scene, base + offset, size, "part slot"))
    raise ConvertError(f"part not found: {name}")


def select_img(container: bytes, names: set[str]) -> bytes:
    """Select only the tree's pictures from Norune's mixed-format IM2 member."""
    for match in re.finditer(b"IM2\0|IMG\0", container):
        start = match.start()
        if start + 16 > len(container):
            continue
        count = struct.unpack_from("<I", container, start + 4)[0]
        if not 0 < count <= 1024 or start + 16 + count * 48 > len(container):
            continue
        entries = []
        for i in range(count):
            at = start + 16 + i * 48
            name = container[at:at + 32].split(b"\0", 1)[0].decode("ascii", "replace")
            if name not in names:
                continue
            off = struct.unpack_from("<I", container, at + 32)[0]
            head = checked_span(container, start + off, 20, "TIM2")
            if head[:4] != b"TIM2":
                raise ConvertError("bad TIM2 signature")
            size = 16 + struct.unpack_from("<I", head, 16)[0]
            entries.append((name, bytes(checked_span(container, start + off, size, "TIM2 payload"))))
        if {n for n, _ in entries} != names:
            continue
        out = bytearray(container[start:start + 16])
        struct.pack_into("<I", out, 4, len(entries))
        out += b"\0" * (len(entries) * 48)
        for i, (name, picture) in enumerate(entries):
            at = 16 + i * 48
            out[at:at + 32] = name.encode().ljust(32, b"\0")
            struct.pack_into("<I", out, at + 32, len(out))
            out += picture
            out += b"\0" * ((-len(out)) % 16)
        return bytes(out)
    raise ConvertError("tree textures not found together in IMG/IM2")


def collision_mds(triangles: list, placement: bool = True, name: str = "ix_tree_col") -> tuple[bytes, dict]:
    if not triangles or len(triangles) > 1024:
        raise ConvertError("tree collision triangle count outside bound")
    bounds = [[min(v[k] for t in triangles for v in t), max(v[k] for t in triangles for v in t)]
              for k in range(3)]
    x0, x1 = bounds[0]
    z0, z1 = bounds[2]
    groups = [(2, triangles)]
    for area in ((1, 3, 5) if placement else ()):
        if area == 5:
            # Area 5 is river overlap, not a second ground footprint. Vertical
            # bounds have zero projected area while retaining the placement extent.
            bottom = [[x0, 0, z0], [x0, 0, z1], [x1, 0, z1], [x1, 0, z0]]
            top = [[x, bounds[1][1], z] for x, _, z in bottom]
            sides = []
            for i in range(4):
                j = (i + 1) % 4
                sides += [[bottom[i], top[i], top[j]], [bottom[i], top[j], bottom[j]]]
            groups.append((area, sides))
            continue
        y = 0 if area == 1 else bounds[1][1]
        a, b, c, d = [x0, y, z0], [x0, y, z1], [x1, y, z1], [x1, y, z0]
        groups.append((area, [[a, b, c], [a, c, d]]))
    vertices = bytearray()
    faces = bytearray(struct.pack("<4i", 0, 16, len(groups), 0))
    materials = bytearray()
    for index, (area, tris) in enumerate(groups):
        first = len(vertices) // 16
        for tri in tris:
            for v in tri:
                vertices += struct.pack("<4f", *v, 1)
        n = len(tris) * 3
        faces += struct.pack("<3i", 0x213, n, index)
        faces += struct.pack(f"<{n}i", *range(first, first + n))
        # CreateCollisionMDT: area_kind = diffuse[2] * .7 + .01.
        materials += struct.pack("<4f", 0, 0, area / .7, 1) + b"\0" * 80
    face_size = len(faces)
    faces += b"\0" * ((-len(faces)) % 16)
    vo = 64
    fo = vo + len(vertices)
    mo = fo + len(faces)
    size = mo + len(materials)
    header = b"MDT\0" + struct.pack("<15i", 64, size, len(vertices) // 16, vo,
                                      0, 0, 0, 0, face_size, fo, 0, 0, len(groups), mo, 0)
    matrix = (1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.)
    record = struct.pack("<2i", 0, 112) + name.encode().ljust(32, b"\0")
    record += struct.pack("<2i16f", 128, -1, *matrix)
    mds = b"MDS\0" + struct.pack("<3i", 1, 1, 16) + record + header + vertices + faces + materials
    return mds, {"source_triangles": len(triangles), "areas": {str(a): len(t) for a, t in groups},
                 "bounds": bounds, "scale": 1.0}


def replace_private(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".georama-new")
    with temporary.open("xb") as file:
        file.write(data)
    os.replace(temporary, path)  # breaks only our hard link; never writes the original inode


SANDBOX_IDS = (50, 51, 52, 54, 55, 56, 58)  # zero preview-scale entries, none used by native g01 (see port seam)

DEFAULT_PROFILE = {
    "pack": "georama-norune-tree",
    "scale": 1.0,
    "parts": [{"id": 50, "scene": "e01t01", "name": "Norune tree", "comment": "DC1 e01t01, scale 1:1",
               "max_num": 16}],
}


def load_profile(path: Path | None) -> dict:
    """Parts are names and ids only; the profile never carries retail bytes."""
    profile = copy.deepcopy(DEFAULT_PROFILE) if path is None else json.loads(path.read_text(encoding="utf-8"))
    parts = profile.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ConvertError("profile has no parts")
    seen_ids, seen_scenes = set(), set()
    for part in parts:
        if part.get("id") not in SANDBOX_IDS:
            raise ConvertError(f"part id {part.get('id')} is not one of the sandbox ids {SANDBOX_IDS}")
        if not re.fullmatch(r"e\d\d[a-z]\d\d", part.get("scene", "")):
            raise ConvertError(f"bad scene part name {part.get('scene')!r}")
        if part["id"] in seen_ids or part["scene"] in seen_scenes:
            raise ConvertError("duplicate part id or scene in profile")
        if len(part.get("name", "")) > 15 or not re.fullmatch(r"[A-Za-z0-9 ]+", part.get("name", "")):
            raise ConvertError(f"part name {part.get('name')!r} must be 1-15 letters, digits or spaces")
        seen_ids.add(part["id"])
        seen_scenes.add(part["scene"])
    profile.setdefault("scale", 1.0)
    return profile


def drop_objects(visual: bytes, pattern: str | None) -> tuple[bytes, list]:
    """Detach matching objects' meshes (the frame stays, so parents and child frames keep their places)."""
    if not pattern:
        return visual, []
    out = bytearray(visual)
    dropped = []
    expression = re.compile(pattern)
    for obj in read_mds(visual, "house visual"):
        if obj.mesh and expression.search(obj.name):
            struct.pack_into("<i", out, 16 + obj.index * 112 + 40, 0)
            dropped.append(obj.name)
    if len(dropped) == sum(1 for o in read_mds(visual, "house visual") if o.mesh):
        raise ConvertError("drop pattern removes every mesh")
    return bytes(out), dropped


def mesh_materials(visual: bytes) -> set[str]:
    """Texture names of every material of every remaining mesh (rewrite_mds renames all of them)."""
    names = set()
    for obj in read_mds(visual, "visual"):
        if not obj.mesh:
            continue
        h = mdt_header(visual, obj.mesh)
        for m in range(h["material_num"]):
            at = obj.mesh + h["material_ofs"] + m * 0x60
            name = visual[at + 52:at + 96].split(b"\0", 1)[0].decode("ascii").casefold()
            if name:
                names.add(name)
    return names


def visual_bounds(visual: bytes) -> list:
    objects = parse_mds(visual)
    matrices = world_matrices(objects, (0, 0, 0), 0)
    points = []
    for obj, matrix in zip(objects, matrices):
        if not obj["mesh"]:
            continue
        h = mdt_header(visual, obj["mesh"])
        for i in range(h["vertex_num"]):
            points.append(transform_point(matrix, struct.unpack_from("<3f", visual, obj["mesh"] + h["vertex_ofs"] + i * 16)))
    return [[round(min(p[k] for p in points), 2), round(max(p[k] for p in points), 2)] for k in range(3)]


def convert_part(scene: bytes, container: bytes, part: dict, scale: float) -> dict:
    """One scene part to visual + collision + textures. Raises ConvertError with the refusal reason."""
    name = part["scene"]
    visual = scene_part(scene, name, 0x48, 0x58)
    donor_col = scene_part(scene, name, 0x78, 0x7C)
    visual, dropped = drop_objects(visual, part.get("drop"))
    # validate_mdt refuses out-of-range indices (e01h06) and unknown face types for every remaining mesh
    tex_names = mesh_materials(visual)
    if not tex_names:
        raise ConvertError(f"{name}: no textured meshes")
    img = select_img(container, tex_names)
    decoded = decode_chr_img(img)  # refuses non-PSMT8 pictures
    tex_map = {n: "ix_" + n for n in tex_names}
    visual, rewrites = rewrite_mds(visual, lambda n: n, tex_map, name)
    poly_cost = vertex_cost = size_cost = 0
    for obj in read_mds(visual, name):
        if obj.mesh:
            poly_cost += validate_mdt(visual, obj.mesh, obj.name).triangles
            vertex_cost += mdt_header(visual, obj.mesh)["vertex_num"]
            size_cost += (struct.unpack_from("<i", visual, obj.mesh + 8)[0] + 15) // 16
    triangles = parse_collision_mds(donor_col, (0, 0, 0), 0)
    triangles = [[[c * scale for c in v] for v in tri] for tri in triangles]
    prefix = "ix_" + name
    col, col_info = collision_mds(triangles, True, prefix + "_col")
    world_col, _ = collision_mds(triangles, False, prefix + "_wcol")
    return {"part": part, "scale": scale, "visual": visual, "col": col, "world_col": world_col, "col_info": col_info,
            "img": img, "decoded": decoded, "tex1s": tim2_gstex1(img), "tex_map": tex_map, "dropped": dropped,
            "rewrites": rewrites, "costs": [poly_cost, vertex_cost, size_cost], "bounds": visual_bounds(visual),
            "pcp": build_pack([
                (prefix + ".mds", visual), (prefix + "-h.mds", col), (prefix + "-w.mds", world_col),
                ("info.cfg", (f'MDS "{prefix}.mds"; TYPE 0; FAR_CLIP 0,0; MDS_END;\r\n'
                              f'MDS "{prefix}-h.mds"; TYPE 1; FAR_CLIP 0,0; MDS_END;\r\n'
                              f'MDS "{prefix}-w.mds"; TYPE 1; FAR_CLIP 0,0; MDS_END;\r\n').encode())])}


def parts_script(prefix: str, scale: float) -> bytes:
    text = f'\r\nPARTS "{prefix}";\r\nLIGHT_FLAG 1,1; MOVE_FLAG 1,1,1,1;\r\n'
    for model, col_type, show, piece_scale in [(prefix + ".mds", 0, 1, scale), (prefix + "-h.mds", 1, 0, 1.0),
                                               (prefix + "-w.mds", 0, 1, 1.0)]:
        text += (f'PIECE "{model}",{show}; PIECE_POS 0,0,0; PIECE_ROT 0,0,0; '
                 f'PIECE_SCALE {piece_scale:g},{piece_scale:g},{piece_scale:g}; PIECE_COL_TYPE {col_type},0; '
                 'PIECE_TIME 0,0; PIECE_END;\r\n')
    return (text + 'PARTS_END;\r\n').encode()


def edit_parts_entry(result: dict) -> bytes:
    part = result["part"]
    poly, vertex, size = result["costs"]
    return (f'\r\nEDIT_PARTS "{part["name"]}"; ID {part["id"]}; PARTS_NAME "ix_{part["scene"]}"; PARTS_ATR 0; '
            f'PARTS_COMMENT "{part.get("comment", "DC1 " + part["scene"])}"; CPOINT 0,0; WEIGHT 0; GEO_STONE 0; '
            f'MAX_NUM {part.get("max_num", 4)}; PAINT_NUM 0; PARTS_TYPE 6; PLACE_EPS 0.98; '
            f'POLYN {poly},{vertex},{size}; MAP_NO -1; EDIT_PARTS_END;\r\n').encode()


def prepare(dc1: Path, dc2: Path, output: Path, profile: dict | None = None):
    profile = profile or load_profile(None)
    if output.exists():
        raise ConvertError("output already exists; choose a new private directory")
    default_scale = float(profile["scale"])
    for part in profile["parts"]:
        if not 0.1 <= float(part.get("scale", default_scale)) <= 10:
            raise ConvertError("scale outside 0.1-10")
    scene_path = dc1 / "gedit/e01/scene.scn"
    scene = scene_path.read_bytes()
    img_path = dc1 / "gedit/e01/img.pak"
    container = img_path.read_bytes()
    results, refusals = [], []
    for part in profile["parts"]:
        try:
            results.append(convert_part(scene, container, part, float(part.get("scale", default_scale))))
        except ConvertError as error:
            refusals.append({"id": part["id"], "scene": part["scene"], "name": part["name"], "reason": str(error)})
            if not part.get("optional"):
                raise ConvertError(f"{part['scene']}: refused: {error}") from error
    if not results:
        raise ConvertError("every part was refused")
    # One catalog-backed picture set serves every part (names are namespaced ix_*, identical across parts).
    pictures: dict[str, tuple] = {}
    for result in results:
        for (pname, value), tex1 in zip(result["decoded"].items(), result["tex1s"]):
            pictures.setdefault("ix_" + pname, (value, tex1))
    data_root = dc2 / "data"
    if not data_root.is_dir():
        raise ConvertError("--dc2-root must contain data/ and port_data/")
    # Unchanged files are shared only as inputs. Changed scripts/packs/catalog are new inodes.
    shutil.copytree(data_root, output / "data", copy_function=os.link)
    shutil.copytree(dc2 / "port_data", output / "port_data", copy_function=os.link)
    if (dc2 / "data.json").is_file():
        shutil.copyfile(dc2 / "data.json", output / "data.json")
    g01 = data_root / "map/g/g01"
    gix = output / "data/map/g/gix"
    gix.mkdir()
    for file in g01.iterdir():
        if file.is_file():
            target = file.name.replace("g01", "gix", 1)
            shutil.copyfile(file, gix / target)
    for table_path in sorted((data_root / "map").glob("map[0-5].cfg")):
        table = table_path.read_bytes().splitlines(keepends=True)
        if b'// 5' not in table[6] or b'MAP_NAME "","","",0,0' not in table[6]:
            raise ConvertError("map record 5 is not the expected empty slot")
        table[6] = b'MAP_NAME "gix","Ixion sandbox","g00/g00",1,1,2000,2;// 5\r\n'
        replace_private(output / "data/map" / table_path.name, b"".join(table))
    outer = pack_members_ordered((g01 / "g01.mpk").read_bytes())
    for result in results:
        outer.append((f'ix_{result["part"]["scene"]}.pcp', result["pcp"]))
    replace_private(gix / "gix.mpk", build_pack(outer))
    ipk = pack_members_ordered((g01 / "g01.ipk").read_bytes())
    ipk.append(("ix_norune.img", b""))
    replace_private(gix / "gix.ipk", build_pack(ipk))
    map_script = (g01 / "g01.map").read_bytes()
    header = b'IMG "ix_norune.img";\r\n' + b"".join(f'PCP "ix_{r["part"]["scene"]}.pcp";\r\n'.encode() for r in results)
    map_script = header + map_script
    for result in results:
        map_script += parts_script("ix_" + result["part"]["scene"], result["scale"])
    replace_private(gix / "gix.map", map_script)
    for gpi_path in sorted(g01.glob("g01[0-5].gpi")):
        gpi = gpi_path.read_bytes()
        for result in results:
            if re.search(rb'\bID\s+%d\s*;' % result["part"]["id"], gpi):
                raise ConvertError(f"sandbox ID {result['part']['id']} is already occupied")
        count = int(re.search(rb'EDIT_PARTS_NUM\s+(\d+)', gpi)[1])
        gpi = re.sub(rb'EDIT_PARTS_NUM\s+\d+', f'EDIT_PARTS_NUM {count + len(results)}'.encode(), gpi, count=1)
        replace_private(gix / gpi_path.name.replace("g01", "gix", 1), gpi + b"".join(edit_parts_entry(r) for r in results))
    catalog = json.loads((dc2 / "port_data/catalog.json").read_text())
    for source in list(catalog["sources"]):
        if source["source"].startswith("map/g/g01/g01."):
            alias = copy.deepcopy(source)
            alias["source"] = source["source"].replace("map/g/g01/g01.", "map/g/gix/gix.", 1)
            catalog["sources"].append(alias)
    pngs = {}
    catalog["sources"].append(_catalog_source(
        "map/g/gix/gix.ipk/ix_norune.img", {k: v[0] for k, v in pictures.items()},
        [v[1] for v in pictures.values()], pngs))
    for rel, png in pngs.items():
        replace_private(output / "port_data" / rel, png)
    replace_private(output / "port_data/catalog.json", json.dumps(catalog).encode())
    provenance = {"schema_version": 2, "map": "gix", "slot": 5, "scale": default_scale, "pack": profile.get("pack"),
                  "source_scene_sha256": sha256(scene), "source_img_sha256": sha256(container),
                  "parts": [{"id": r["part"]["id"], "scene": r["part"]["scene"], "name": r["part"]["name"],
                             "scale": r["scale"], "dropped_objects": r["dropped"], "textures": sorted(r["tex_map"].values()),
                             "collision": r["col_info"], "visual_bounds": r["bounds"],
                             "rewrites": r["rewrites"], "polyn_cost": r["costs"],
                             "visual_sha256": sha256(r["visual"]), "collision_sha256": sha256(r["col"]),
                             "world_collision_sha256": sha256(r["world_col"]), "pcp_sha256": sha256(r["pcp"])}
                            for r in results],
                  "refusals": refusals,
                  "draw_budget_note": "POLYN[2] sums the kept visual MDT sizes in quadwords; not a measured VU packet cost",
                  "native_data": str(dc2.resolve()), "campaign_slots": "unchanged 0-4"}
    first = results[0]
    replace_private(output / "world_collision.mds", first["world_col"])  # first part's, kept for the R1 native test
    replace_private(output / "georama-provenance.json", json.dumps(provenance, indent=2).encode())
    print(json.dumps(provenance, indent=2))
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dc1-root", type=Path, required=True)
    parser.add_argument("--dc2-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, help="JSON list of parts (ids, scene names, drop patterns)")
    args = parser.parse_args()
    try:
        prepare(args.dc1_root, args.dc2_root, args.output, load_profile(args.profile) if args.profile else None)
    except (ConvertError, OSError, ValueError) as error:
        parser.exit(2, f"georama: {error}\n")


if __name__ == "__main__":
    main()
