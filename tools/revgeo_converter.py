#!/usr/bin/env python3
"""Private, offline Dark Chronicle (DC2) Georama part -> Dark Cloud (DC1) Norune Georama part pack.

Round 1 converts the DC2 Shed. DC2 builds a part from the PIECE list of a ``PARTS`` block in
g00.map: a visual MDS, hidden placement volumes and collision. DC1 builds it from one
``EPARTS_ARCHIVE`` (scene.scn directory entry): a part definition with a cell footprint, a
level-of-detail 0 scene and a collision scene whose ``MDT_COLLISION`` carries per-polygon
attribute records. This tool writes that archive as a one-entry private scene
(``revgeo.scn``), plus RGBA pictures and a manifest the DC1 port reads (see
``port/src/ixion_revgeo.cpp``). Nothing here is retail-derived data in git: the pack goes under
``packs/revgeo-*`` only. Both datasets are only read.

Direction: DC2 world units are DC1's times 1.5584790683 (monster_converter.DC1_TO_DC2_SCALE), so a
DC2 object enters DC1 at the reciprocal, the same factor the Ridepod uses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from monster_converter import DC1_TO_DC2_SCALE, mdt_header, parse_pack, read_mds  # noqa: E402
from room_converter import ConvertError, parse_mds, transform_point, world_matrices  # noqa: E402
from room_converter import png_rgba as room_png  # noqa: E402

DC2_TO_DC1_SCALE = 1.0 / DC1_TO_DC2_SCALE
CELL_UNIT = 100.0          # Norune's EDITAREA unit size (mapinfo.cfg: EDITAREA 0 ... 14, 12, 100, 10)
CELL_OCCUPIED = 0x80       # what every retail house cell holds
MDS_RECORD = 112
MDT_MATERIAL = 96
PLOT = 17                  # Norune's unused plot slot: zero-filled in EditPartsData, absent from scene.scn
PART_NAME = "ixrg_shed"    # SearchPTS key; at most 15 characters
TEXTURE_PREFIX = "ixrg_"
FACE_COLOUR = 0x100
COLLISION_TAG = 0x340038   # first word of retail's MDT_COLLISION header
SHED = {"parts": "p02_a0101", "pieces": "a010201", "id": 2, "display": "Shed"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def align(value: int, to: int = 16) -> int:
    return (value + to - 1) // to * to


# ---------------------------------------------------------------------------------------------
# DC2 sources


def walk_pcp(data: bytes) -> list[tuple[str, bytes]]:
    """A DC2 PCP: 80-byte entry headers (name[64], header, size, step) with repeatable names."""
    out, at = [], 0
    while at + 80 <= len(data):
        raw = data[at:at + 64]
        if raw[:1] == b"\0":
            break
        name = raw.split(b"\0", 1)[0].decode("ascii", "replace")
        header, size, step = struct.unpack_from("<3i", data, at + 64)
        if header != 80 or size < 0 or step < 80 or at + 80 + size > len(data):
            raise ConvertError(f"bad PCP entry at {at}: {name!r}")
        out.append((name, data[at + 80:at + 80 + size]))
        at += step
    return out


def load_shed_pieces(dc2: Path) -> dict[str, bytes]:
    """The Shed's four pieces from g00.mpk -> g00_2.pcp (the piece names carry the shed's id)."""
    mpk = (dc2 / "map" / "cmn" / "g00" / "g00.mpk").read_bytes()
    members = parse_pack(mpk)
    wanted = {f"{SHED['pieces']}-{suffix}.mds" for suffix in "mhac"}
    found: dict[str, bytes] = {}
    for member in members.values():
        if not member.data[:8].startswith(b"info.cfg"):
            continue
        for name, payload in walk_pcp(member.data):
            if name in wanted and name not in found:
                found[name] = payload
        if len(found) == len(wanted):
            return found
    raise ConvertError(f"Shed pieces not found in g00.mpk: missing {sorted(wanted - set(found))}")


def mds_world_points(data: bytes) -> list[tuple[float, float, float]]:
    objects = parse_mds(data)
    matrices = world_matrices(objects, (0, 0, 0), 0)
    points = []
    for obj, matrix in zip(objects, matrices):
        if not obj["mesh"]:
            continue
        h = mdt_header(data, obj["mesh"])
        for i in range(h["vertex_num"]):
            points.append(tuple(transform_point(matrix, struct.unpack_from("<3f", data, obj["mesh"] + h["vertex_ofs"] + i * 16))))
    if not points:
        raise ConvertError("MDS has no vertices")
    return points


def bounds_of(points) -> list[list[float]]:
    return [[min(p[k] for p in points), max(p[k] for p in points)] for k in range(3)]


def dc2_collision_triangles(data: bytes, label: str) -> list[list[list[float]]]:
    """Vertex-only triangle lists (face type 0x213) of every object, in the object's frame."""
    triangles = []
    matrices = world_matrices(parse_mds(data), (0, 0, 0), 0)
    for obj, matrix in zip(read_mds(data, label), matrices):
        if not obj.mesh:
            continue
        h = mdt_header(data, obj.mesh)
        faces = obj.mesh + h["faces_ofs"]
        groups = struct.unpack_from("<i", data, faces + 8)[0]
        cur = faces + 16
        vertices = obj.mesh + h["vertex_ofs"]
        for _ in range(groups):
            ftype, count, _material = struct.unpack_from("<3I", data, cur)
            if ftype & 0xFF != 0x13 or count % 3:
                raise ConvertError(f"{label}: unexpected collision face type {ftype:#x} x{count}")
            cur += 12
            indices = struct.unpack_from(f"<{count}i", data, cur)
            cur += count * 4
            for k in range(0, count, 3):
                tri = []
                for idx in indices[k:k + 3]:
                    if not 0 <= idx < h["vertex_num"]:
                        raise ConvertError(f"{label}: collision vertex index {idx} out of range")
                    tri.append(list(transform_point(matrix, struct.unpack_from("<3f", data, vertices + idx * 16))))
                triangles.append(tri)
    if not triangles:
        raise ConvertError(f"{label}: no collision triangles")
    return triangles


# ---------------------------------------------------------------------------------------------
# Visual scene: DC2 MDS -> DC1 MDS


def convert_visual(visual: bytes, scale: float, shift: tuple[float, float, float], texture_map: dict[str, str],
                   shadow_cards: set[str]) -> tuple[bytes, dict]:
    """Scale and rename in place. DC1 shares DC2's MDS/MDT layout; what differs is only that DC1's renderer
    reads a strip's primitive as 3 (list) or 4 (strip) and takes the vertex-colour column from the header,
    where DC2 sets 0x100 on the face type for it."""
    out = bytearray(visual)
    stats = {"objects": 0, "meshes": 0, "triangles": 0, "dropped": [], "colour_strips": 0, "materials": 0}
    objects = read_mds(visual, "shed visual")
    for obj in objects:
        stats["objects"] += 1
        record = 16 + obj.index * MDS_RECORD
        if obj.parent == -1:  # recentre by moving the roots; children follow
            for axis in range(3):
                at = record + 48 + (12 + axis) * 4
                struct.pack_into("<f", out, at, struct.unpack_from("<f", out, at)[0] * scale + shift[axis])
        else:
            for axis in range(3):
                at = record + 48 + (12 + axis) * 4
                struct.pack_into("<f", out, at, struct.unpack_from("<f", out, at)[0] * scale)
        if not obj.mesh:
            continue
        h = mdt_header(visual, obj.mesh)
        names = []
        for m in range(h["material_num"]):
            at = obj.mesh + h["material_ofs"] + m * MDT_MATERIAL + 52
            names.append(visual[at:at + 44].split(b"\0", 1)[0].decode("ascii"))
        if names and all(n in shadow_cards for n in names):
            struct.pack_into("<i", out, record + 40, 0)  # a DC2 blob-shadow card: DC1 draws its own shadows
            stats["dropped"].append(obj.name)
            continue
        stats["meshes"] += 1
        for i in range(h["vertex_num"]):
            at = obj.mesh + h["vertex_ofs"] + i * 16
            x, y, z = struct.unpack_from("<3f", out, at)
            struct.pack_into("<3f", out, at, x * scale, y * scale, z * scale)
        for m, name in enumerate(names):
            at = obj.mesh + h["material_ofs"] + m * MDT_MATERIAL + 52
            if name not in texture_map:
                raise ConvertError(f"{obj.name}: texture {name!r} has no converted picture")
            out[at:at + 44] = texture_map[name].encode("ascii").ljust(44, b"\0")
            stats["materials"] += 1
        faces = obj.mesh + h["faces_ofs"]
        groups = struct.unpack_from("<i", visual, faces + 8)[0]
        cur = faces + 16
        for _ in range(groups):
            ftype, count, _material = struct.unpack_from("<3I", visual, cur)
            stride = 3 + (1 if ftype & FACE_COLOUR else 0)
            prim = ftype & 0xFF
            if prim not in (3, 4) or ftype & ~(FACE_COLOUR | 0xFF):
                raise ConvertError(f"{obj.name}: unsupported face type {ftype:#x}")
            if ftype & FACE_COLOUR:
                if h["colour_num"] <= 0 or h["colour_ofs"] <= 0:
                    raise ConvertError(f"{obj.name}: colour strip without a colour section")
                struct.pack_into("<I", out, cur, prim)
                stats["colour_strips"] += 1
            stats["triangles"] += (count // 3) if prim == 3 else (count - 2)
            cur += 12 + count * stride * 4
    return bytes(out), stats


# ---------------------------------------------------------------------------------------------
# DC1 collision scene


def dc1_collision_mds(triangles: list, name: str) -> tuple[bytes, dict]:
    """DC1 MDS holding one object whose MDT is an MDT_COLLISION (ps2/include/mdt.hpp): positions, the
    {unk, 16, n, 0, 3, n} poly-set header, 20-byte MDT_CPOLY records, normals and 16-byte attribute records.
    Attribute record 0 is the retail house's: no ground kind, no foot sound, no area kind, nothing ignored."""
    if not triangles or len(triangles) > 1024:
        raise ConvertError("collision triangle count outside bound")
    index: dict[tuple, int] = {}
    vertices = bytearray()
    polys = []
    normals = bytearray()
    for tri in triangles:
        ids = []
        for v in tri:
            key = tuple(round(c, 4) for c in v)
            if key not in index:
                index[key] = len(index)
                vertices += struct.pack("<4f", *v, 1.0)
            ids.append(index[key])
        polys.append(ids)
        a, b, c = tri
        ux, uy, uz = (b[k] - a[k] for k in range(3))
        vx, vy, vz = (c[k] - a[k] for k in range(3))
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        length = math.sqrt(sum(x * x for x in n)) or 1.0
        normals += struct.pack("<4f", n[0] / length, n[1] / length, n[2] / length, 0.0)
    count = len(polys)
    vertex_ofs = 64
    mesh_ofs = vertex_ofs + len(vertices)
    mesh = bytearray(struct.pack("<4i2i", COLLISION_TAG, 16, count, 0, 3, count))
    for ids in polys:
        mesh += struct.pack("<5i", *ids, 0, 0)
    normal_ofs = align(mesh_ofs + len(mesh))
    mesh += b"\0" * (normal_ofs - mesh_ofs - len(mesh))
    info_ofs = normal_ofs + len(normals)
    record = b"\0" * 8 + b"\xff" * 8
    size = info_ofs + 2 * len(record)
    header = b"MDT\0" + struct.pack("<15i", 64, size, len(index), vertex_ofs, count, normal_ofs, 0, 0,
                                    16 + 8 + count * 20, mesh_ofs, 0, 0, 1, info_ofs, 0)
    mdt = header + vertices + bytes(mesh) + bytes(normals) + record + record
    assert len(mdt) == size
    matrix = (1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.)
    entry = struct.pack("<2i", 0, MDS_RECORD) + name.encode().ljust(32, b"\0")
    entry += struct.pack("<2i16f", 16 + MDS_RECORD, -1, *matrix)
    mds = b"MDS\0" + struct.pack("<3i", 1, 1, 16) + entry + mdt
    xs = [k[0] for k in index]
    zs = [k[2] for k in index]
    ys = [k[1] for k in index]
    return mds, {"triangles": count, "vertices": len(index),
                 "bounds": [[min(xs), max(xs)], [min(ys), max(ys)], [min(zs), max(zs)]]}


# ---------------------------------------------------------------------------------------------
# Pictures


def png_rgba(data: bytes) -> tuple[bytes, int, int]:
    """Bounded non-interlaced 8-bit RGBA PNG reader for the DC2 texture catalog."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ConvertError("bad PNG signature")
    pos, compressed, dimensions = 8, bytearray(), None
    while pos < len(data):
        if len(data) - pos < 12:
            raise ConvertError("truncated PNG chunk")
        n = struct.unpack_from(">I", data, pos)[0]
        if n > len(data) - pos - 12:
            raise ConvertError("PNG chunk escapes file")
        tag, chunk = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if zlib.crc32(tag + chunk) != struct.unpack_from(">I", data, pos + 8 + n)[0]:
            raise ConvertError("PNG CRC mismatch")
        if tag == b"IHDR":
            if dimensions or n != 13:
                raise ConvertError("invalid PNG IHDR")
            w, h, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", chunk)
            if not (0 < w <= 2048 and 0 < h <= 2048) or (depth, color, compression, filtering, interlace) != (8, 6, 0, 0, 0):
                raise ConvertError("expected bounded RGBA8 non-interlaced PNG")
            dimensions = (w, h)
        elif tag == b"IDAT":
            compressed.extend(chunk)
        elif tag == b"IEND":
            break
        pos += n + 12
    if dimensions is None:
        raise ConvertError("missing PNG IHDR")
    w, h = dimensions
    stride = w * 4
    decoder = zlib.decompressobj()
    raw = decoder.decompress(bytes(compressed), (stride + 1) * h + 1)
    if len(raw) != (stride + 1) * h or not decoder.eof or decoder.unused_data:
        raise ConvertError("invalid PNG scanline extent")
    out, previous = bytearray(), bytes(stride)
    for row in range(h):
        at = row * (stride + 1)
        kind, scan = raw[at], bytearray(raw[at + 1:at + 1 + stride])
        if kind > 4:
            raise ConvertError("unknown PNG filter")
        for i in range(stride):
            a = scan[i - 4] if i >= 4 else 0
            b = previous[i]
            c = previous[i - 4] if i >= 4 else 0
            if kind == 4:
                p = a + b - c
                distances = (abs(p - a), abs(p - b), abs(p - c))
                predictor = (a, b, c)[distances.index(min(distances))]
            else:
                predictor = (0, a, b, (a + b) // 2)[kind]
            scan[i] = (scan[i] + predictor) & 255
        out.extend(scan)
        previous = scan
    return bytes(out), w, h


def gs_rgba(rgba: bytes) -> bytes:
    """GS alpha is 0..128 (0x80 = opaque)."""
    out = bytearray(rgba)
    for i in range(3, len(out), 4):
        out[i] = (out[i] * 128 + 127) // 255
    return bytes(out)


def catalog_textures(catalog_file: Path, source: str, names: set[str]) -> dict[str, dict]:
    catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
    entries = {}
    for item in catalog["sources"]:
        if item["source"] != source:
            continue
        for entry in item["entries"]:
            if entry["name"] in names:
                entries[entry["name"]] = entry
    missing = names - set(entries)
    if missing:
        raise ConvertError(f"catalog lacks pictures {sorted(missing)} in {source}")
    return entries


def safe_catalog_file(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or ".." in Path(name).parts or "\\" in name or ":" in name:
        raise ConvertError("unsafe catalog path")
    return path


# ---------------------------------------------------------------------------------------------
# The part's picture on DC1's part card


GLYPHS = {
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
}
ICON_SIZE = 84     # DC1's part-picture cells are 84 x 84 (memcard.cpp: CRect_i_(u, v, 0x54, 0x54))
ICON_SHEET = 128   # the texture holding it


def mesh_triangles(visual: bytes) -> list:
    """World-space triangles of the converted visual: (positions, normals, uvs, material) per triangle."""
    objects = parse_mds(visual)
    matrices = world_matrices(objects, (0, 0, 0), 0)
    out = []
    for obj, matrix in zip(objects, matrices):
        mesh = obj["mesh"]
        if not mesh:
            continue
        h = mdt_header(visual, mesh)
        verts = [struct.unpack_from("<3f", visual, mesh + h["vertex_ofs"] + i * 16) for i in range(h["vertex_num"])]
        norms = [struct.unpack_from("<3f", visual, mesh + h["normal_ofs"] + i * 16) for i in range(h["normal_num"])]
        uvs = [struct.unpack_from("<2f", visual, mesh + h["uv_ofs"] + i * 16) for i in range(h["uv_num"])]
        materials = []
        for m in range(h["material_num"]):
            at = mesh + h["material_ofs"] + m * MDT_MATERIAL
            materials.append(visual[at + 52:at + 96].split(b"\0", 1)[0].decode("ascii"))
        faces = mesh + h["faces_ofs"]
        groups = struct.unpack_from("<i", visual, faces + 8)[0]
        cur = faces + 16
        for _ in range(groups):
            prim, count, material = struct.unpack_from("<3I", visual, cur)
            stride = 4 if h["colour_ofs"] > 0 and h["colour_num"] > 0 else 3
            cur += 12
            entries = [struct.unpack_from("<3i", visual, cur + k * stride * 4) for k in range(count)]
            cur += count * stride * 4
            order = []
            if prim == 3:
                order = [(k, k + 1, k + 2) for k in range(0, count - 2, 3)]
            else:
                order = [((k, k + 1, k + 2) if k % 2 == 0 else (k + 1, k, k + 2)) for k in range(count - 2)]
            for a, b, c in order:
                tri = []
                for idx in (a, b, c):
                    vi, ni, ti = entries[idx]
                    tri.append((tuple(transform_point(matrix, verts[vi])), norms[ni], uvs[ti]))
                out.append((tri, materials[material]))
    return out


def render_icon(visual: bytes, pictures: dict[str, tuple[bytes, int, int]], label: str = "SHED") -> bytes:
    """A 128 x 128 RGBA sheet whose top-left 84 x 84 cell is the converted part seen from the front-right
    above, shaded and textured by a small software rasteriser, with its name in a pixel font under it."""
    scale_ss = 3
    size = ICON_SIZE * scale_ss
    yaw, pitch = math.radians(35.0), math.radians(30.0)
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)

    def project(p):
        x = p[0] * cy - p[2] * sy
        z = p[0] * sy + p[2] * cy
        return x, p[1] * cp - z * sp, p[1] * sp + z * cp  # screen x, screen y (up), depth (toward the camera = smaller)
    light = (-0.45, 0.8, -0.4)
    ln = math.sqrt(sum(c * c for c in light))
    light = tuple(c / ln for c in light)
    triangles = mesh_triangles(visual)
    if not triangles:
        raise ConvertError("nothing to draw in the icon")
    projected = [[project(v[0]) for v in tri] for tri, _ in triangles]
    xs = [p[0] for tri in projected for p in tri]
    ys = [p[1] for tri in projected for p in tri]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    usable = size * 0.74
    k = usable / span
    ox = size / 2 - (max(xs) + min(xs)) / 2 * k
    oy = size * 0.62 + (max(ys) + min(ys)) / 2 * k   # below centre: the name goes above
    depth = [[1e30] * size for _ in range(size)]
    pixels = [[None] * size for _ in range(size)]
    for (tri, material), pro in zip(triangles, projected):
        pts = [(ox + p[0] * k, oy - p[1] * k, p[2]) for p in pro]
        min_x = max(0, int(min(p[0] for p in pts)))
        max_x = min(size - 1, int(max(p[0] for p in pts)) + 1)
        min_y = max(0, int(min(p[1] for p in pts)))
        max_y = min(size - 1, int(max(p[1] for p in pts)) + 1)
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = pts
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-9:
            continue
        nrm = [sum(t[1][i] for t in tri) / 3 for i in range(3)]
        nl = math.sqrt(sum(c * c for c in nrm)) or 1.0
        shade = 0.55 + 0.45 * max(0.0, sum(nrm[i] / nl * light[i] for i in range(3)))
        texture = pictures.get(material)
        for py in range(min_y, max_y + 1):
            for px in range(min_x, max_x + 1):
                cx, cy_ = px + 0.5, py + 0.5
                w0 = ((x1 - cx) * (y2 - cy_) - (x2 - cx) * (y1 - cy_)) / area
                w1 = ((x2 - cx) * (y0 - cy_) - (x0 - cx) * (y2 - cy_)) / area
                w2 = 1 - w0 - w1
                if w0 < 0 or w1 < 0 or w2 < 0:
                    continue
                z = w0 * z0 + w1 * z1 + w2 * z2
                if z >= depth[py][px]:
                    continue
                if texture is not None:
                    data, tw, th = texture
                    u = (w0 * tri[0][2][0] + w1 * tri[1][2][0] + w2 * tri[2][2][0])
                    v = (w0 * tri[0][2][1] + w1 * tri[1][2][1] + w2 * tri[2][2][1])
                    tx = int((u % 1.0) * tw) % tw
                    ty = int(((v % 1.0)) * th) % th
                    r, g, b, a = data[(ty * tw + tx) * 4:(ty * tw + tx) * 4 + 4]
                    if a < 40:
                        continue
                else:
                    r, g, b = 180, 160, 120
                depth[py][px] = z
                pixels[py][px] = (min(255, int(r * shade * 1.15)), min(255, int(g * shade * 1.15)), min(255, int(b * shade * 1.15)))
    sheet = bytearray(ICON_SHEET * ICON_SHEET * 4)
    for y in range(ICON_SIZE):
        for x in range(ICON_SIZE):
            r = g = b = hit = 0
            for sy_ in range(scale_ss):
                for sx_ in range(scale_ss):
                    p = pixels[y * scale_ss + sy_][x * scale_ss + sx_]
                    if p is not None:
                        r += p[0]; g += p[1]; b += p[2]; hit += 1
            if hit:
                at = (y * ICON_SHEET + x) * 4
                sheet[at:at + 3] = bytes((r // hit, g // hit, b // hit))
                sheet[at + 3] = min(255, 255 * hit // (scale_ss * scale_ss) + 60)
    # Name in a 5x7 pixel font, two screen pixels per dot, with a dark outline.
    dot = 2
    width = len(label) * (5 * dot + dot) - dot
    left = (ICON_SIZE - width) // 2
    top = 4
    mask = set()
    for index, ch in enumerate(label):
        for row, line in enumerate(GLYPHS[ch]):
            for col, c in enumerate(line):
                if c == "#":
                    for dy in range(dot):
                        for dx in range(dot):
                            mask.add((left + index * 6 * dot + col * dot + dx, top + row * dot + dy))
    for (x, y) in mask:
        for ox_ in (-1, 0, 1):
            for oy_ in (-1, 0, 1):
                nx, ny = x + ox_, y + oy_
                if (nx, ny) not in mask and 0 <= nx < ICON_SIZE and 0 <= ny < ICON_SIZE:
                    at = (ny * ICON_SHEET + nx) * 4
                    sheet[at:at + 4] = bytes((20, 12, 8, 255))
    for (x, y) in mask:
        at = (y * ICON_SHEET + x) * 4
        sheet[at:at + 4] = bytes((255, 236, 150, 255))
    return bytes(sheet)


# ---------------------------------------------------------------------------------------------
# DC1 archive


def part_definition(width: int, height: int, cell: int, kind: int) -> bytes:
    """EPartsDiscHeader (0x78) + cell map; no elements, no function records."""
    cells = bytes([cell]) * (width * height)
    func_off = align(0x78 + len(cells), 8)
    data_size = func_off
    head = struct.pack("<5i", 0x78, data_size, width, height, kind)
    head += bytes([0] * 8 + [1] + [0] * 7)               # unk_14, as retail's houses and tree
    head += struct.pack("<3f3f", 0, 0, 0, 0, 0, 0)       # position, rotation
    head += struct.pack("<I", 0x78)                      # cell map offset
    head += struct.pack("<6i", *([-1] * 6))              # element ids
    head += struct.pack("<6I", *([0] * 6))               # element names
    head += struct.pack("<Ii", func_off, 0)
    assert len(head) == 0x78
    return head + cells + b"\0" * (data_size - 0x78 - len(cells))


def eparts_archive(name: str, definition: bytes, lod0: bytes, collision: bytes) -> bytes:
    """EPARTS_ARCHIVE (ps2/include/editpartsinfo.hpp, 0xE0 bytes) followed by its parts."""
    info_off = 0xE0
    lod0_off = align(info_off + len(definition))
    col_off = align(lod0_off + len(lod0))
    total = align(col_off + len(collision))
    out = bytearray(0xE0)
    out[0:4] = b"PTS\0"
    struct.pack_into("<i", out, 4, info_off)
    for k, suffix in enumerate(("_0", "_1", "_2", "_m")):
        label = (name + suffix + ".mds").encode()[:15]
        out[8 + 16 * k:8 + 16 * k + len(label)] = label
    struct.pack_into("<i", out, 0x48, lod0_off)
    struct.pack_into("<i", out, 0x58, len(lod0))
    struct.pack_into("<i", out, 0x78, col_off)
    struct.pack_into("<i", out, 0x7C, len(collision))
    out += definition
    out += b"\0" * (lod0_off - len(out))
    out += lod0
    out += b"\0" * (col_off - len(out))
    out += collision
    out += b"\0" * (total - len(out))
    return bytes(out)


def scene_of(name: str, archive: bytes) -> bytes:
    """A one-entry scene: 'SCN\\0', count, then a 48-byte directory entry (name[16], offset)."""
    base = 64
    head = b"SCN\0" + struct.pack("<I", 1) + b"\0" * 8
    entry = name.encode().ljust(16, b"\0") + struct.pack("<i", base) + b"\0" * 28
    return head + entry + archive


# ---------------------------------------------------------------------------------------------


def convert(dc2: Path, catalog_file: Path, output: Path, scale: float = DC2_TO_DC1_SCALE, stock: int = 4) -> dict:
    if output.exists():
        raise ConvertError("output exists; refusing to overwrite")
    if not 0.05 <= scale <= 3.0:
        raise ConvertError("scale outside plausible range")
    pieces = load_shed_pieces(dc2)
    visual_src = pieces[f"{SHED['pieces']}-m.mds"]
    place_src = pieces[f"{SHED['pieces']}-h.mds"]
    wall_src = pieces[f"{SHED['pieces']}-a.mds"]
    camera_src = pieces[f"{SHED['pieces']}-c.mds"]

    # Recentre on the placement volume, so the model origin is the middle of its cells.
    place_bounds = bounds_of(mds_world_points(place_src))
    centre_x = (place_bounds[0][0] + place_bounds[0][1]) / 2
    centre_z = (place_bounds[2][0] + place_bounds[2][1]) / 2
    shift = (-centre_x * scale, 0.0, -centre_z * scale)
    span_x = (place_bounds[0][1] - place_bounds[0][0]) * scale
    span_z = (place_bounds[2][1] - place_bounds[2][0]) * scale
    width, height = max(1, math.ceil(span_x / CELL_UNIT)), max(1, math.ceil(span_z / CELL_UNIT))
    if width * height > 32:
        raise ConvertError(f"footprint {width}x{height} cells exceeds the 32-cell definition")

    # Pictures: the materials of the meshes that stay.
    material_names = set()
    cards = set()
    for obj in read_mds(visual_src, "shed visual"):
        if not obj.mesh:
            continue
        h = mdt_header(visual_src, obj.mesh)
        mats = [visual_src[obj.mesh + h["material_ofs"] + m * MDT_MATERIAL + 52:obj.mesh + h["material_ofs"] + m * MDT_MATERIAL + 96]
                .split(b"\0", 1)[0].decode("ascii") for m in range(h["material_num"])]
        material_names.update(mats)
        if mats and all(n.startswith("kage") for n in mats):
            cards.update(mats)
    kept_names = set()
    for obj in read_mds(visual_src, "shed visual"):
        if not obj.mesh:
            continue
        h = mdt_header(visual_src, obj.mesh)
        mats = [visual_src[obj.mesh + h["material_ofs"] + m * MDT_MATERIAL + 52:obj.mesh + h["material_ofs"] + m * MDT_MATERIAL + 96]
                .split(b"\0", 1)[0].decode("ascii") for m in range(h["material_num"])]
        if not all(n in cards for n in mats):
            kept_names.update(mats)
    texture_map = {n: TEXTURE_PREFIX + n for n in sorted(kept_names)}
    texture_map.update({n: TEXTURE_PREFIX + n for n in sorted(cards)})
    entries = catalog_textures(catalog_file, "map/cmn/g00/g00.ipk/a01.img", kept_names)
    files, textures, sources_rgba = {}, [], {}
    for name in sorted(kept_names):
        entry = entries[name]
        if entry.get("no_image") or entry["format"] != "rgba8":
            raise ConvertError(f"catalog picture {name} is not RGBA8")
        level = entry["variants"][0]["levels"][0]
        png = safe_catalog_file(catalog_file.parent, level).read_bytes()
        rgba, w, h = png_rgba(png)
        if (w, h) != (entry["width"], entry["height"]):
            raise ConvertError("catalog dimensions disagree")
        pixels = gs_rgba(rgba)
        sources_rgba[TEXTURE_PREFIX + name] = (rgba, w, h)
        file_name = TEXTURE_PREFIX + name + ".rgba"
        files[file_name] = pixels
        textures.append({"name": TEXTURE_PREFIX + name, "source_name": name, "file": file_name, "width": w, "height": h,
                         "tex1": entry["tex1"], "sha256": sha256(pixels), "source_png": level, "source_sha256": sha256(png)})

    visual, vis_stats = convert_visual(visual_src, scale, shift, texture_map, cards)

    # The card picture: DC1 has none for a part it never shipped.
    icon = render_icon(visual, sources_rgba, SHED["display"].upper())
    files["ixrg_icon.rgba"] = gs_rgba(icon)
    files["ixrg_icon.png"] = room_png(ICON_SHEET, ICON_SHEET, icon)
    textures.append({"name": "ixrg_icon", "source_name": "(rendered)", "file": "ixrg_icon.rgba", "width": ICON_SHEET,
                     "height": ICON_SHEET, "tex1": 608, "sha256": sha256(files["ixrg_icon.rgba"]),
                     "role": "card-picture", "cell": [0, 0, ICON_SIZE, ICON_SIZE]})

    # Collision: the wall piece (-a) walks; the camera piece (-c) is the same shape.
    def scaled(triangles):
        return [[[(tri[k][0] * scale) + shift[0], tri[k][1] * scale, (tri[k][2] * scale) + shift[2]] for k in range(3)]
                for tri in triangles]
    wall_tris = dc2_collision_triangles(wall_src, "shed -a")
    camera_tris = dc2_collision_triangles(camera_src, "shed -c")
    collision, col_info = dc1_collision_mds(scaled(wall_tris), PART_NAME + "_col")

    definition = part_definition(width, height, CELL_OCCUPIED, 0)
    archive = eparts_archive(PART_NAME, definition, visual, collision)
    scene = scene_of(PART_NAME, archive)
    files["revgeo.scn"] = scene

    manifest = {
        "format": "ixion-revgeo-dc1",
        "version": 1,
        "town": 0,
        "plot": PLOT,
        "scale": scale,
        "scene": "revgeo.scn",
        "scene_sha256": sha256(scene),
        "part": {"name": PART_NAME, "display": SHED["display"], "stock": stock, "cells": [width, height],
                 "cell_code": CELL_OCCUPIED, "unit": CELL_UNIT},
        "textures": textures,
        "provenance": {
            "source": "DC2 map/cmn/g00/g00.mpk g00_2.pcp " + SHED["parts"] + " (EDIT_PARTS ID %d)" % SHED["id"],
            "pieces": {k: {"bytes": len(v), "sha256": sha256(v)} for k, v in sorted(pieces.items())},
            "recentre_shift": list(shift),
            "placement_bounds_dc2": place_bounds,
            "footprint_span_dc1": [span_x, span_z],
            "visual": vis_stats,
            "visual_bounds_dc1": bounds_of(mds_world_points(visual)),
            "collision": col_info,
            "camera_piece_triangles": len(camera_tris),
            "archive_bytes": len(archive),
        },
    }
    text = json.dumps(manifest, indent=2, sort_keys=True)
    output.mkdir(parents=True)
    for name, payload in files.items():
        with (output / name).open("xb") as handle:
            handle.write(payload)
    with (output / "revgeo.json").open("x", encoding="utf-8") as handle:
        handle.write(text + "\n")
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dc2-data", type=Path, required=True, help="DC2 data root (read only)")
    parser.add_argument("--catalog", type=Path, required=True, help="DC2 port_data/catalog.json (read only)")
    parser.add_argument("--output", type=Path, required=True, help="new private pack directory (must not exist)")
    parser.add_argument("--scale", type=float, default=DC2_TO_DC1_SCALE)
    parser.add_argument("--stock", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        manifest = convert(args.dc2_data, args.catalog, args.output, args.scale, args.stock)
    except ConvertError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps({k: manifest[k] for k in ("scene_sha256", "scale")} | {"part": manifest["part"],
                                                                      "collision": manifest["provenance"]["collision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
