#!/usr/bin/env python3
"""Offline converter: rigid DC1 monster pack -> DC2-native rigid .chr pack.

Byte study (MC-R1): DC1 visual MDTs already use DC2's 0x40 MDT header and
MDT_FACES/FACES_ID face section, MDS records and Mot_File_List records are the
same layout, so the model work is a targeted rewrite, not a re-encode:

* MDS: object order kept (the .mot addresses objects by index); hit frames
  renamed ``xcolN`` -> ``xcol0N``; MDT bodies rewritten in place.
* MDT: ``colour_ofs`` -1 -> 0 when there are no colours, the unused trailing
  header word zeroed, every material's 44-byte DC1 name field rewritten as
  DC2's 32-byte name (namespaced) + zeroed ``unk_54``/``extra``.
* .mot: copied byte for byte (rotation keys unchanged, see wave1-quat-numeric).
* IMG: entry names namespaced; RGBA PNGs + a port texture-catalog fragment are
  emitted because the PC port only accepts catalog-backed textures.
* cfg: a DC2 ``v2`` dialect cfg is authored from a motion/frame mapping table
  against the brain's own cfg.

The validator re-implements what DC2's LoadPack/LoadChrFile/mgCVisualMDT path
reads and also accepts native DC2 packs (round-trip proof).

``convert-player`` handles a skinned DC1 player body driven by a BodyProfile
(``--profile tools/profiles/<body>.json``; default toan-c01d.json): .mot/.wgt are
copied byte for byte (same record layouts, frame order kept), VERTEX_ANIME names
the skin frame, null frames are renamed to DC2 sockets, missing sockets are
synthesised as null frames appended after the last frame (MDS record, mesh-offset
shift, one .bbp row each), and a DC2 cfg with DC1-ordered keys plus Max's motion
names is authored. The validator walks .wgt files as CreateVertexWeight does
(32 bones / 4 influences per frame).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import struct
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from room_converter import ConvertError, checked_span, parse_pack, png_rgba, unswizzle_psmt8, validate_png  # noqa: E402

DC1_TO_DC2_SCALE = 1.5584790683
PACK_HEADER = 80
MDS_RECORD = 112
MDT_HEADER = 0x40
MDT_MATERIAL = 0x60
FACES_HEADER = 0x10
MDS_NAME_MAX = 31          # char name[32]
KEY_NAME_MAX = 0x24 - 1    # CHRINFO_KEY_SET::name[0x24]
PACK_NAME_MAX = 63         # PACK_ENTRY::name[64]
MODEL_NAME_MAX = 15        # BASE_MONSTER_TBL::model[16]
TEXTURE_SUFFIX = "_m"      # monster.cpp sets name_suffix "_m" while a monster pack loads
TEXTURE_NAME_MAX = 0x20 - 1 - len(TEXTURE_SUFFIX)  # EnterTexture builds name+suffix in char[0x20]
ENTRY_OBJECT_MAX = 24      # CHARA_ENTRY_OBJECT_MAX
MOTION_SET_MAX = 8         # CHARA_MOTION_SET_MAX
MG_FACE_PRIM_MASK = 0x7
MG_FACE_FLAT = 0x8
MG_FACE_NO_TEXTURE = 0x10
MG_FACE_COLOUR = 0x100
MG_FACE_NO_NORMAL = 0x200
KNOWN_FACE_BITS = MG_FACE_PRIM_MASK | MG_FACE_FLAT | MG_FACE_NO_TEXTURE | MG_FACE_COLOUR | MG_FACE_NO_NORMAL
MOTION_KEY_TYPES = {0, 1, 2, 12, 20, 21, 30, 31, 32, 33, 40, 41, 50, 51}
DC2_CFG_TAGS = {
    "V2", "NAME", "IMG", "IMG_END", "BODY_SIZE", "SCALE", "MATERIAL_ANIME", "POLY_NUM", "MODEL",
    "SHADOW_MODEL", "OBJECT_NAME", "OBJECT_NAME2", "MOTION", "SHADOW_MOTION", "OUTLINE",
    "VERTEX_ANIME", "SHAPE_ANIME", "KEY_START", "KEY", "KEY_END", "SEQ_START", "SEQ", "SEQ_END",
    "CLOTH_START", "CLOTH", "CLOTH_END", "POSITION", "ROTATION", "SE_START", "SE", "SELP", "SE_END",
    "MOTION_END", "EFFECT_START", "EFFECT", "EFFECT_END", "LOD_MODEL_START", "LOD_MODEL", "LOD_MODEL_END",
}
HIT_FRAME = re.compile(r"^(bcol|dcol|mcol)(\d)$")
CHARA_ENTRY_GROUP_DAMAGE = 3
CHARA_DEFORM_FRAME_MAX = 24  # character.hpp:33; _VERTEX_ANIME refuses more names
VERTEX_ANIME_NAME_MAX = 15   # alloc_vertex[25][16] (character.cpp:156), filled by strcpy
WGT_RECORD = 32              # VertexWeightBlock / VertexWeightEntry (visualmotion.cpp:36-57)
WGT_KEY_TYPE = 20            # third header word in every DC1 and DC2 .wgt block (Mot_File_List type 20)
SKIN_BONE_MAX = 32           # CreateVertexWeight "Bone Num Over!!!" nulls the table (visualmotion.cpp:114)
SKIN_INFLUENCE_MAX = 4       # mgVertexWeight has 4 slots; more renormalises ("Weight Num Over!!!")
MATRIX_BYTES = 64            # one sceVu0FMATRIX; _MOTION memcpys frame_num of them from the .bbp
NEUTRAL_RADIUS = 5.0       # brainless OBJECT_NAME2 placeholder; the chosen brain's table replaces it

# DC1 e03a (Skeleton Soldier) onto the DC2 Vanguard (e202a) brain. Slots are
# info.cfg KEY indices (their Shift-JIS comments name them); explicit ranges are
# authored sub-ranges where e03a has no equivalent motion.
E03A_ON_E202A = {
    "motions": [
        {"name": "立ち", "slot": 0, "why": "立ち (idle) 10-20"},
        {"name": "歩き", "slot": 1, "why": "歩き (walk) 25-45"},
        {"name": "攻撃１", "slot": 13, "why": "攻撃1 (sword swing 1) 50-70"},
        {"name": "攻撃２", "slot": 16, "why": "攻撃2 (sword swing 2) 75-95"},
        {"name": "攻撃３in", "start": 75, "end": 80, "step": 0.4, "why": "no 3rd attack: wind-up of 攻撃2"},
        {"name": "攻撃３", "start": 80, "end": 90, "step": 0.6, "why": "no spin: body of 攻撃2 (script loops it)"},
        {"name": "攻撃３out", "start": 90, "end": 95, "step": 0.4, "why": "recovery of 攻撃2"},
        {"name": "吹っ飛び", "slot": 11, "why": "死亡 (collapse) 205-225; Vanguard's 吹っ飛び also ends on its death pose"},
        {"name": "ダメージ", "slot": 8, "why": "ダメージ1 125-135"},
        {"name": "死に", "slot": 12, "why": "死亡ループ (held death pose) 225"},
        {"name": "気絶", "slot": 10, "step": 0.17, "why": "no stun: 起き上がり (get up) 165-185"},
        {"name": "会話", "slot": 0, "why": "same as 立ち, as the brain cfg does"},
    ],
    # (group, [(frame, radius), ...]) in the brain cfg's group order. Radii are the
    # brain's own (e202a.cfg) values; groups: 0 target, 1 shadow, 2 hit, 3 damage, 4 body.
    "groups": [
        [0, [["lockon", 3.0]]],
        [1, [["dummyRoot", None]]],
        [2, [["bcol00", 10.0], ["bcol01", 5.0], ["bcol02", 5.0]]],
        [3, [["dcol00", 15.0], ["mcol03", 5.0], ["mcol04", 5.0], ["bcol01", 5.0], ["bcol02", 5.0]]],
        [4, [["mcol00", 10.0], ["mcol01", 5.0], ["mcol02", 5.0]]],
    ],
}
DEFAULT_MAPPINGS = {("e03a", "e202a"): E03A_ON_E202A}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- PACK

def build_pack(entries: list[tuple[str, bytes]]) -> bytes:
    """Write a PACK the way retail packs are laid out: 80-byte entry headers, 16-byte strides."""
    out = bytearray()
    seen = set()
    for name, payload in entries:
        raw = name.encode("ascii")
        if not raw or len(raw) > PACK_NAME_MAX or "/" in name or "\\" in name:
            raise ConvertError(f"invalid pack member name {name!r}")
        if name.casefold() in seen:
            raise ConvertError(f"duplicate pack member {name!r}")
        seen.add(name.casefold())
        step = ((PACK_HEADER + len(payload) + 15) // 16) * 16
        out += raw.ljust(64, b"\0") + struct.pack("<iii", PACK_HEADER, len(payload), step) + b"\0" * 4
        out += payload + b"\0" * (step - PACK_HEADER - len(payload))
    out += b"\0" * PACK_HEADER
    return bytes(out)


def pack_members_ordered(data: bytes) -> list[tuple[str, bytes]]:
    members = parse_pack(data)
    return [(m.name, m.data) for m in members.values()]


# ---------------------------------------------------------------- cfg (SPI script)

def spi_statements(text: str, skipped: list | None = None) -> list[tuple[str, list]]:
    """Tokenise a character script into (COMMAND, args). Statements end at ';' or newline.

    With a ``skipped`` list (DC1 sources only) unparseable statements are recorded there and
    dropped instead of raising: e104a's info.cfg has a bare annotation line inside its key list.
    """
    out = []
    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = raw_line
        # strip // comments outside quotes
        buf, quote = [], False
        i = 0
        while i < len(line):
            c = line[i]
            if c == '"':
                quote = not quote
            if not quote and line.startswith("//", i):
                break
            buf.append(c)
            i += 1
        for stmt in _split_outside_quotes("".join(buf), ";"):
            stmt = stmt.strip()
            if not stmt:
                continue
            try:
                out.append(_spi_statement(stmt))
            except ConvertError:
                if skipped is None:
                    raise
                skipped.append(stmt)
    return out


def _spi_statement(stmt: str) -> tuple[str, list]:
    m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*(.*)$", stmt, re.S)
    if not m:
        raise ConvertError(f"unparseable cfg statement {stmt!r}")
    cmd = m.group(1).upper()
    args: list = []
    for tok in _split_outside_quotes(m.group(2), ","):
        tok = tok.strip()
        if not tok:
            continue
        if tok.startswith('"'):
            if len(tok) < 2 or not tok.endswith('"'):
                raise ConvertError(f"unterminated string in {stmt!r}")
            args.append(tok[1:-1])
        else:
            try:
                args.append(float(tok) if any(ch in tok for ch in ".eE") else int(tok))
            except ValueError as exc:
                raise ConvertError(f"bad number {tok!r} in {stmt!r}") from exc
    return cmd, args


def _split_outside_quotes(text: str, sep: str) -> list[str]:
    parts, cur, quote = [], [], False
    for c in text:
        if c == '"':
            quote = not quote
        if c == sep and not quote:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    if quote:
        raise ConvertError("unterminated string in cfg")
    parts.append("".join(cur))
    return parts


@dataclass
class ChrCfg:
    imgs: list = field(default_factory=list)
    model: str | None = None
    shadow_model: str | None = None
    motions: list = field(default_factory=list)       # (id, mot, base, wgt)
    shadow_motions: list = field(default_factory=list)
    keys: dict = field(default_factory=dict)          # motion id -> [(name|None, start, end, step)]
    groups: list = field(default_factory=list)        # (group, [(frame, size)])
    body_size: tuple | None = None
    scale: tuple | None = None
    poly_num: tuple | None = None
    se: list = field(default_factory=list)            # raw (cmd, args) of the SE block
    other: list = field(default_factory=list)
    skipped: list = field(default_factory=list)       # DC1 statements the tokeniser could not read


def parse_chr_cfg(text: str, dc1_comment_names: bool = False) -> ChrCfg:
    cfg = ChrCfg()
    motion_id = 0
    in_keys = in_se = False
    lines = text.replace("\r\n", "\n").split("\n")
    skipped: list = []
    stmts = spi_statements(text, skipped if dc1_comment_names else None)
    cfg.skipped = skipped
    # DC1 KEY lines carry no name; their trailing comment names the slot.
    comment_names = []
    if dc1_comment_names:
        for line in lines:
            m = re.match(r"\s*KEY\s+[-\d.]+\s*,\s*[-\d.]+\s*,\s*[-\d.]+\s*,?\s*//\s*(\S+)", line)
            if m:
                comment_names.append(m.group(1))
    dc1_key_index = 0
    for cmd, args in stmts:
        if cmd == "IMG":
            cfg.imgs.append((int(args[0]), str(args[1])))
        elif cmd == "MODEL":
            cfg.model = str(args[0])
        elif cmd == "SHADOW_MODEL":
            cfg.shadow_model = str(args[0])
        elif cmd == "MOTION":
            motion_id = int(args[0])
            cfg.motions.append((motion_id, *[str(a) for a in args[1:4]]))
        elif cmd == "SHADOW_MOTION":
            cfg.shadow_motions.append(tuple(str(a) for a in args[:3]))
        elif cmd == "KEY_START":
            in_keys = True
            cfg.keys.setdefault(motion_id, [])
        elif cmd == "KEY_END" or (cmd == "MOTION_END" and dc1_comment_names):
            in_keys = False  # DC1 info.cfg closes its key list with MOTION_END alone
        elif cmd == "KEY":
            if isinstance(args[0], str):
                name, rest = args[0], args[1:]
            else:
                name = comment_names[dc1_key_index] if dc1_key_index < len(comment_names) else None
                rest = args
                dc1_key_index += 1
            if len(rest) < 3:
                raise ConvertError(f"KEY with too few arguments: {args!r}")
            cfg.keys.setdefault(motion_id, []).append((name, int(rest[0]), int(rest[1]), float(rest[2])))
        elif cmd == "OBJECT_NAME2":
            group = int(args[0])
            rest = args[1:]
            pairs = []
            if len(args) < 3:
                pairs.append((str(rest[0]), None))
            else:
                for i in range(0, len(rest) - 1, 2):
                    pairs.append((str(rest[i]), float(rest[i + 1])))
            cfg.groups.append((group, pairs))
        elif cmd == "BODY_SIZE":
            cfg.body_size = tuple(float(a) for a in args[:3])
        elif cmd == "SCALE":
            cfg.scale = tuple(float(a) for a in args[:3])
        elif cmd == "POLY_NUM":
            cfg.poly_num = tuple(int(a) for a in args)
        elif cmd == "SE_START":
            in_se = True
            cfg.se.append((cmd, args))
        elif cmd == "SE_END":
            in_se = False
            cfg.se.append((cmd, args))
        elif in_se:
            cfg.se.append((cmd, args))
        else:
            cfg.other.append((cmd, args))
    if in_keys:
        raise ConvertError("KEY_START without KEY_END")
    return cfg


def find_cfg_member(members: dict, model_hint: str | None = None):
    if model_hint and f"{model_hint}.cfg".casefold() in members:
        return members[f"{model_hint}.cfg".casefold()]
    if "info.cfg" in members:
        return members["info.cfg"]
    cfgs = [m for k, m in members.items() if k.endswith(".cfg")]
    if len(cfgs) != 1:
        raise ConvertError("pack must contain exactly one cfg")
    return cfgs[0]


# ---------------------------------------------------------------- MDS / MDT

@dataclass
class MdsObject:
    index: int
    name: str
    mesh: int
    parent: int


def read_mds(data: bytes, label: str) -> list[MdsObject]:
    if len(data) < 16 or data[:4] != b"MDS\0":
        raise ConvertError(f"{label}: bad MDS signature")
    version, count, records = struct.unpack_from("<III", data, 4)
    if version != 1 or records != 16 or not 0 < count <= 4096:
        raise ConvertError(f"{label}: unsupported MDS header")
    checked_span(data, records, count * MDS_RECORD, f"{label} object table")
    objs = []
    table_end = records + count * MDS_RECORD
    for i in range(count):
        at = records + i * MDS_RECORD
        index, rec_size = struct.unpack_from("<ii", data, at)
        raw = data[at + 8:at + 40]
        if b"\0" not in raw:
            raise ConvertError(f"{label}: object {i} name is not NUL-terminated")
        try:
            name = raw.split(b"\0", 1)[0].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ConvertError(f"{label}: non-ASCII object name") from exc
        mesh, parent = struct.unpack_from("<ii", data, at + 40)
        if index != i or rec_size != MDS_RECORD:
            raise ConvertError(f"{label}: object {i} record header ({index},{rec_size}) is not ({i},{MDS_RECORD})")
        if parent < -1 or parent >= i:
            raise ConvertError(f"{label}: object {name} parent {parent} is not an earlier object")
        if not all(math.isfinite(v) for v in struct.unpack_from("<16f", data, at + 48)):
            raise ConvertError(f"{label}: non-finite matrix in {name}")
        if mesh:
            if mesh < table_end or mesh % 16 or mesh > len(data) - MDT_HEADER:
                raise ConvertError(f"{label}: MDT offset {mesh} of {name} out of range")
        objs.append(MdsObject(i, name, mesh, parent))
    return objs


@dataclass
class MdtInfo:
    triangles: int
    materials: list
    face_types: dict


def mdt_header(data: bytes, mesh: int) -> dict:
    keys = ("header_size", "unk_08", "vertex_num", "vertex_ofs", "normal_num", "normal_ofs", "colour_num",
            "colour_ofs", "faces_size", "faces_ofs", "uv_num", "uv_ofs", "material_num", "material_ofs", "unk_3c")
    return dict(zip(keys, struct.unpack_from("<15i", data, mesh + 4)))


def validate_mdt(data: bytes, mesh: int, label: str, source: bool = False) -> MdtInfo:
    """Mirror of what mgCVisualMDT::CopyMDTData/DataAssignMDT/CreateFace read."""
    if data[mesh:mesh + 4] != b"MDT\0":
        raise ConvertError(f"{label}: bad MDT signature")
    h = mdt_header(data, mesh)
    if h["header_size"] != MDT_HEADER:
        raise ConvertError(f"{label}: MDT header_size {h['header_size']} != 0x40")
    size = h["unk_08"]
    if size < MDT_HEADER or size > len(data) - mesh:
        raise ConvertError(f"{label}: MDT size {size} escapes MDS")

    def section(num_key, ofs_key, stride):
        num, ofs = h[num_key], h[ofs_key]
        if num < 0:
            raise ConvertError(f"{label}: negative {num_key}")
        if num == 0:
            if ofs != 0 and not (MDT_HEADER <= ofs <= size) and not (source and ofs == -1):
                raise ConvertError(f"{label}: {ofs_key}={ofs} with no data must be 0 or in range")
            return
        if ofs < MDT_HEADER or ofs % 16 or num * stride > size - ofs:
            raise ConvertError(f"{label}: {num_key}/{ofs_key} section escapes MDT")

    section("vertex_num", "vertex_ofs", 16)
    section("normal_num", "normal_ofs", 16)
    section("colour_num", "colour_ofs", 16)
    section("uv_num", "uv_ofs", 16)
    section("material_num", "material_ofs", MDT_MATERIAL)
    if h["vertex_num"] <= 0:
        raise ConvertError(f"{label}: MDT has no vertices")
    if h["material_num"] > 1024:
        raise ConvertError(f"{label}: implausible material count")
    fofs, fsize = h["faces_ofs"], h["faces_size"]
    if fofs < MDT_HEADER or fsize < FACES_HEADER or fsize > size - fofs:
        raise ConvertError(f"{label}: face section escapes MDT")
    base = mesh + fofs
    unk0, fhdr, prims, unk_c = struct.unpack_from("<iiii", data, base)
    if fhdr != FACES_HEADER:
        raise ConvertError(f"{label}: MDT_FACES header_size {fhdr} != 16")
    if prims < 0 or prims > 100000:
        raise ConvertError(f"{label}: bad primitive count")
    cur, end = base + FACES_HEADER, base + fsize
    triangles = 0
    types: dict = {}
    for p in range(prims):
        if end - cur < 12:
            raise ConvertError(f"{label}: FACES_ID {p} header escapes face section")
        ftype, vnum, mat = struct.unpack_from("<III", data, cur)
        if ftype & ~KNOWN_FACE_BITS:
            raise ConvertError(f"{label}: FACES_ID {p} has unknown type bits 0x{ftype:x}")
        prim = ftype & MG_FACE_PRIM_MASK
        if prim not in (3, 4, 5):
            raise ConvertError(f"{label}: FACES_ID {p} primitive {prim} is not a triangle type")
        stride = 1 + (0 if ftype & MG_FACE_NO_NORMAL else 1) + (0 if ftype & MG_FACE_NO_TEXTURE else 1) + (1 if ftype & MG_FACE_COLOUR else 0)
        if vnum < 3 or (prim == 3 and vnum % 3):
            raise ConvertError(f"{label}: FACES_ID {p} vertex count {vnum} invalid for primitive {prim}")
        if mat >= max(h["material_num"], 1):
            raise ConvertError(f"{label}: FACES_ID {p} material {mat} >= {h['material_num']}")
        cur += 12
        if vnum * stride * 4 > end - cur:
            raise ConvertError(f"{label}: FACES_ID {p} indices escape face section")
        limits = [h["vertex_num"]]
        if not ftype & MG_FACE_NO_NORMAL:
            limits.append(h["normal_num"])
        if not ftype & MG_FACE_NO_TEXTURE:
            limits.append(h["uv_num"])
        if ftype & MG_FACE_COLOUR:
            limits.append(h["colour_num"])
        idx = struct.unpack_from(f"<{vnum * stride}i", data, cur)
        for k, value in enumerate(idx):
            if not 0 <= value < limits[k % stride]:
                raise ConvertError(f"{label}: FACES_ID {p} index {value} out of range")
        cur += vnum * stride * 4
        triangles += vnum // 3 if prim == 3 else vnum - 2
        types[ftype] = types.get(ftype, 0) + 1
    if cur != end:
        raise ConvertError(f"{label}: face section has {end - cur} trailing bytes")
    mats = []
    for m in range(h["material_num"]):
        at = mesh + h["material_ofs"] + m * MDT_MATERIAL
        if not all(math.isfinite(v) for v in struct.unpack_from("<13f", data, at)):
            raise ConvertError(f"{label}: non-finite material {m}")
        raw = data[at + 52:at + 84]
        if b"\0" not in raw:
            raise ConvertError(f"{label}: material {m} texture name fills char[32] with no NUL")
        try:
            name = raw.split(b"\0", 1)[0].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ConvertError(f"{label}: non-ASCII material texture name") from exc
        mats.append(name)
    return MdtInfo(triangles, mats, types)


def rewrite_mds(data: bytes, rename_frame, texture_map: dict[str, str], label: str) -> tuple[bytes, dict]:
    """Return a DC2-shaped copy of a DC1 MDS: frames renamed, MDTs fixed in place."""
    objs = read_mds(data, label)
    out = bytearray(data)
    stats = {"renamed": {}, "colour_ofs_fixed": 0, "unk_3c_zeroed": 0, "materials": 0}
    names = set()
    for o in objs:
        at = 16 + o.index * MDS_RECORD
        new = rename_frame(o.name)
        if new != o.name:
            stats["renamed"][o.name] = new
        if len(new) > MDS_NAME_MAX:
            raise ConvertError(f"{label}: frame name {new!r} exceeds char[32]")
        if new in names:
            raise ConvertError(f"{label}: renaming produced duplicate frame {new!r}")
        names.add(new)
        out[at + 8:at + 40] = new.encode("ascii").ljust(32, b"\0")
        if not o.mesh:
            continue
        mesh = o.mesh
        validate_mdt(data, mesh, f"{label}:{o.name} (source)", source=True)
        h = mdt_header(data, mesh)
        if h["colour_num"] == 0 and h["colour_ofs"] != 0:
            struct.pack_into("<i", out, mesh + 32, 0)
            stats["colour_ofs_fixed"] += 1
        if h["unk_3c"] != 0:
            struct.pack_into("<i", out, mesh + 60, 0)
            stats["unk_3c_zeroed"] += 1
        for m in range(h["material_num"]):
            at_m = mesh + h["material_ofs"] + m * MDT_MATERIAL
            src = data[at_m + 52:at_m + 96].split(b"\0", 1)[0]
            try:
                src_name = src.decode("ascii")
            except UnicodeDecodeError as exc:
                raise ConvertError(f"{label}: non-ASCII DC1 material name") from exc
            new_name = texture_map.get(src_name.casefold(), src_name) if src_name else ""
            if len(new_name) > TEXTURE_NAME_MAX:
                raise ConvertError(f"{label}: texture name {new_name!r} exceeds {TEXTURE_NAME_MAX} chars "
                                   f"(char[32] minus the '{TEXTURE_SUFFIX}' suffix)")
            out[at_m + 52:at_m + 96] = new_name.encode("ascii").ljust(44, b"\0")
            stats["materials"] += 1
        validate_mdt(bytes(out), mesh, f"{label}:{new} (output)")
    return bytes(out), stats


# ---------------------------------------------------------------- MOT

def walk_mot(data: bytes, object_count: int, label: str) -> dict:
    """Walk Mot_File_List records as CreateAnimeDataEX does; return stats."""
    pos, channels, max_frame, types = 0, 0, 0, {}
    while True:
        if len(data) - pos < 32:
            raise ConvertError(f"{label}: motion record header escapes file")
        frame, target, ktype, _u, count, more = struct.unpack_from("<iiiIII", data, pos)
        if ktype not in MOTION_KEY_TYPES:
            raise ConvertError(f"{label}: unknown motion key type {ktype}")
        if ktype in (0, 1, 2) and not 0 <= frame < object_count:
            raise ConvertError(f"{label}: motion drives object {frame} of {object_count}")
        if count > (len(data) - pos - 32) // 32:
            raise ConvertError(f"{label}: motion keys escape file")
        last = -1
        for k in range(count):
            kf = struct.unpack_from("<I", data, pos + 32 + k * 32)[0]
            if ktype not in (20, 21) and kf < last:
                raise ConvertError(f"{label}: motion key frames not ascending")
            last = kf
            if not all(math.isfinite(v) for v in struct.unpack_from("<4f", data, pos + 32 + k * 32 + 16)):
                raise ConvertError(f"{label}: non-finite motion key")
        if ktype in (0, 1, 2):
            max_frame = max(max_frame, last)
        types[ktype] = types.get(ktype, 0) + 1
        channels += 1
        pos += 32 + count * 32
        if not more:
            break
    return {"channels": channels, "max_frame": max_frame, "types": types, "bytes_used": pos}


# ---------------------------------------------------------------- textures

def tim2_tex1(img: bytes) -> list[int]:
    count = struct.unpack_from("<I", img, 4)[0]
    out = []
    for i in range(count):
        off = struct.unpack_from("<I", img, 16 + i * 48 + 32)[0]
        out.append(struct.unpack_from("<Q", img, off + 16 + 40)[0])
    return out


def decode_chr_img(img: bytes) -> dict[str, tuple[bytes, int, int]]:
    """Decode a DC1 character/monster IMG (8-bit CLUT, 256 colours, CSM1) to RGBA PNGs.

    The pixel order follows the container: ``IMG\0`` (v1) pixels are linear, ``IM2\0`` (v2) pixels are
    GS PSMT8 pages. Decoding c01d02, e03a01 or c12a01 (IMG) through the PSMT8 unswizzle gives two
    side-by-side stippled copies; e104a01 and c15a01 (IM2) only come out clean through it
    (TOAN-BODY-R1, scratch/toan-body/tex/*-linear.png vs *-swz.png).
    """
    if len(img) < 16 or img[:4] not in (b"IM2\0", b"IMG\0"):
        raise ConvertError("unsupported IMG signature")
    count = struct.unpack_from("<I", img, 4)[0]
    if count > 1024 or 16 + count * 48 > len(img):
        raise ConvertError("invalid IMG entry table")
    out = {}
    for i in range(count):
        at = 16 + i * 48
        name = img[at:at + 32].split(b"\0", 1)[0].decode("ascii")
        off = struct.unpack_from("<I", img, at + 32)[0]
        head = checked_span(img, off, 80, "TIM2 picture header")
        if head[:4] != b"TIM2":
            raise ConvertError(f"unsupported TIM2 payload for {name}")
        width, height = struct.unpack_from("<HH", head, 36)
        image_size = struct.unpack_from("<I", head, 24)[0]
        header_size, colors = struct.unpack_from("<HH", head, 28)
        clut_type, psm = head[34], head[35]
        if psm != 5 or colors != 256 or (clut_type & 0x3f) == 1 or header_size < 48:
            raise ConvertError(f"unsupported texture layout {name}: psm={psm} colours={colors}")
        if not 0 < width * height <= image_size:
            raise ConvertError(f"invalid indexed texture dimensions for {name}")
        pixels = off + 16 + header_size
        raw = bytes(checked_span(img, pixels, width * height, f"pixels for {name}"))
        if img[:4] == b"IM2\0":
            raw = unswizzle_psmt8(raw, width, height)
        palette = bytes(checked_span(img, pixels + image_size, colors * 4, f"palette for {name}"))
        csm1 = (clut_type & 0xc0) == 0
        rgba = bytearray(width * height * 4)
        for j, index in enumerate(raw):
            slot = ((index & ~0x18) | ((index & 0x08) << 1) | ((index & 0x10) >> 1)) if csm1 else index
            r, g, b, a = palette[slot * 4:slot * 4 + 4]
            rgba[j * 4:j * 4 + 4] = bytes((r, g, b, min(a * 2, 255)))
        out[name] = (png_rgba(width, height, bytes(rgba)), width, height)
    return out


def tim2_gstex1(img: bytes) -> list[int]:
    """GsTex1 of every IMG entry: TIM2 picture header +32 (the file header is 16 bytes)."""
    count = struct.unpack_from("<I", img, 4)[0]
    return [struct.unpack_from("<Q", img, struct.unpack_from("<I", img, 16 + i * 48 + 32)[0] + 16 + 32)[0]
            for i in range(count)]


def rename_img(img: bytes, texture_map: dict[str, str]) -> bytes:
    if img[:4] not in (b"IMG\0", b"IM2\0"):
        raise ConvertError("unsupported IMG signature")
    out = bytearray(img)
    count = struct.unpack_from("<I", img, 4)[0]
    for i in range(count):
        at = 16 + i * 48
        name = img[at:at + 32].split(b"\0", 1)[0].decode("ascii")
        new = texture_map.get(name.casefold(), name)
        if len(new) > TEXTURE_NAME_MAX:
            raise ConvertError(f"IMG texture name {new!r} too long")
        out[at:at + 32] = new.encode("ascii").ljust(32, b"\0")
    return bytes(out)


# ---------------------------------------------------------------- validator

@dataclass
class BrainContract:
    name: str
    key_names: list            # every KEY name in the brain's cfg (order kept)
    stb_motion_names: list     # subset of key_names that appear as strings in the brain .stb
    groups: dict               # group -> number of entries the brain cfg binds
    stb_frame_names: list      # hit-frame-like strings the .stb binds by name (_SET_OBJ etc.)


def stb_strings(stb: bytes) -> set[str]:
    out = set()
    for m in re.finditer(rb"(?:[\x20-\x7e]|[\x81-\x9f\xe0-\xfc][\x40-\xfc])+\x00", stb):
        try:
            out.add(m.group()[:-1].decode("cp932"))
        except UnicodeDecodeError:
            continue
    return out


def brain_contract(brain_pack: bytes, brain_model: str, brain_stb: bytes | None) -> tuple[BrainContract, ChrCfg]:
    members = parse_pack(brain_pack)
    cfg = parse_chr_cfg(find_cfg_member(members, brain_model).data.decode("cp932"))
    keys = [k[0] for mid in sorted(cfg.keys) for k in cfg.keys[mid] if k[0]]
    strings = stb_strings(brain_stb) if brain_stb else set()
    groups: dict = {}
    for g, pairs in cfg.groups:
        groups[g] = groups.get(g, 0) + len(pairs)
    frames = sorted(s for s in strings if re.fullmatch(r"[bdm]col\d+|lockon", s))
    return BrainContract(brain_model, keys, [k for k in keys if k in strings], groups, frames), cfg


def validate_wgt(data: bytes, objs: list, mds: bytes, deform_frames: list[str] | None, label: str,
                 limits: bool = True) -> dict:
    """Walk a .wgt as mgCVisualMotionMDT::CreateVertexWeight does and check DC2's skin limits.

    Blocks with ``count == 0`` are skipped before a bone slot is claimed (visualmotion.cpp:87), so
    the 32-bone cap counts only non-empty blocks per frame (wave1-dc1-skinned trap: raw headers
    over-count). ``deform_frames`` (VERTEX_ANIME names) must each be meshed and carry weights.
    ``limits=False`` reports a source frame over the bone cap instead of refusing it (the converter splits it).
    """
    pos, headers = 0, 0
    per_frame: dict = {}
    while True:
        if len(data) - pos < WGT_RECORD:
            raise ConvertError(f"{label}: weight block header escapes file")
        fid, bone, ktype, _u, count, more = struct.unpack_from("<IiIIII", data, pos)
        headers += 1
        if ktype != WGT_KEY_TYPE:
            raise ConvertError(f"{label}: weight block {headers - 1} type {ktype} != {WGT_KEY_TYPE}")
        if fid >= len(objs):
            raise ConvertError(f"{label}: weight block targets frame {fid} of {len(objs)}")
        if count > (len(data) - pos - WGT_RECORD) // WGT_RECORD:
            raise ConvertError(f"{label}: weight entries escape file")
        rec = per_frame.setdefault(fid, {"headers": 0, "active": 0, "bones": [], "infl": {}})
        rec["headers"] += 1
        if count:
            if not 0 <= bone < len(objs):
                raise ConvertError(f"{label}: weight bone {bone} outside {len(objs)} frames")
            mesh = objs[fid].mesh
            if not mesh:
                raise ConvertError(f"{label}: weights on unmeshed frame {objs[fid].name}")
            vnum = mdt_header(mds, mesh)["vertex_num"]
            rec["active"] += 1
            if bone not in rec["bones"]:
                rec["bones"].append(bone)
            for k in range(count):
                at = pos + WGT_RECORD + k * WGT_RECORD
                vid = struct.unpack_from("<I", data, at)[0]
                w = struct.unpack_from("<f", data, at + 16)[0]
                if vid >= vnum:
                    raise ConvertError(f"{label}: weight vertex {vid} >= {objs[fid].name} vertex_num {vnum}")
                if not math.isfinite(w) or not 0.0 <= w <= 100.0:
                    raise ConvertError(f"{label}: weight {w} outside 0..100")
                if w != 0.0:
                    rec["infl"].setdefault(vid, []).append(w)
        pos += WGT_RECORD + count * WGT_RECORD
        if not more:
            break
    if pos != len(data):
        raise ConvertError(f"{label}: {len(data) - pos} bytes after the last weight block")
    frames = {}
    for fid, rec in per_frame.items():
        name = objs[fid].name
        if limits and len(rec["bones"]) > SKIN_BONE_MAX:
            raise ConvertError(f"{label}: {name} uses {len(rec['bones'])} bones > {SKIN_BONE_MAX} (DC2 'Bone Num Over')")
        max_infl = max((len(v) for v in rec["infl"].values()), default=0)
        if max_infl > SKIN_INFLUENCE_MAX:
            raise ConvertError(f"{label}: {name} has a vertex with {max_infl} influences > {SKIN_INFLUENCE_MAX}")
        sums = [sum(v) for v in rec["infl"].values()]
        frames[name] = {"frame": fid, "headers": rec["headers"], "active_blocks": rec["active"],
                        "bones": [objs[b].name for b in rec["bones"]], "bone_count": len(rec["bones"]),
                        "vertices_weighted": len(rec["infl"]), "max_influences": max_infl,
                        "weight_sum_min": min(sums, default=0.0), "weight_sum_max": max(sums, default=0.0)}
    for name in deform_frames or []:
        hit = [o for o in objs if o.name == name]
        if not hit:
            raise ConvertError(f"{label}: VERTEX_ANIME frame {name!r} is not in the model")
        if not hit[0].mesh:
            raise ConvertError(f"{label}: VERTEX_ANIME frame {name!r} has no mesh")
        if name not in frames or not frames[name]["active_blocks"]:
            raise ConvertError(f"{label}: VERTEX_ANIME frame {name!r} has no non-empty weight block")
    return {"blocks": headers, "frames": frames}


def validate_chr(pack: bytes, model: str, contract: BrainContract | None = None, catalog: dict | None = None,
                 catalog_root: Path | None = None, require_textures: bool = True, strict: bool = True,
                 pack_dir: str = "dungeon/monster", cfg_name: str | None = None, require_motion: bool = True,
                 player: "PlayerContract | None" = None) -> dict:
    """Structural validation of a DC2 monster pack against DC2 loader expectations.

    strict=True (converter output) refuses everything below. strict=False (native census) turns the
    conditions retail data is known to tolerate into report warnings: unknown cfg tags, a shadow MDS
    larger than the model, unresolved OBJECT_NAME2 frames (SearchFrame fails silently), a missing
    MOTION, textures provided by another pack, and zero-filled IMG members without a catalog source.
    """
    warnings: list[str] = []

    def problem(msg: str) -> None:
        if strict:
            raise ConvertError(msg)
        warnings.append(msg)

    if len(model) > MODEL_NAME_MAX:
        raise ConvertError(f"model name {model!r} exceeds BASE_MONSTER_TBL::model[16]")
    members = parse_pack(pack)
    cfg_member = members.get((cfg_name or f"{model}.cfg").casefold())
    if cfg_member is None:
        raise ConvertError(f"pack lacks {cfg_name or model + '.cfg'}, which the loader opens by name")
    text = cfg_member.data.decode("cp932")
    stmts = spi_statements(text)
    for cmd, _ in stmts:
        if cmd not in DC2_CFG_TAGS:
            problem(f"cfg command {cmd} is not in DC2's character script tag table")
    cfg = parse_chr_cfg(text)
    report: dict = {"model": model, "members": [m.name for m in members.values()]}

    def member(name: str, what: str) -> bytes:
        got = members.get(name.casefold())
        if got is None:
            raise ConvertError(f"{what} {name!r} is not a pack member")
        return got.data

    if not cfg.model:
        raise ConvertError("cfg has no MODEL")
    model_objs = read_mds(member(cfg.model, "MODEL"), cfg.model)
    frame_names = [o.name for o in model_objs]
    model_data = member(cfg.model, "MODEL")
    texture_refs: set[str] = set()
    tri = 0
    for o in model_objs:
        if o.mesh:
            info = validate_mdt(model_data, o.mesh, f"{cfg.model}:{o.name}")
            tri += info.triangles
            texture_refs.update(n for n in info.materials if n)
    shadow_tri = 0
    shadow_objs = []
    if cfg.shadow_model:
        sdata = member(cfg.shadow_model, "SHADOW_MODEL")
        shadow_objs = read_mds(sdata, cfg.shadow_model)
        for o in shadow_objs:
            if o.mesh:
                info = validate_mdt(sdata, o.mesh, f"{cfg.shadow_model}:{o.name}")
                shadow_tri += info.triangles
                texture_refs.update(n for n in info.materials if n)
        if len(shadow_objs) > len(model_objs):
            # _SHADOW_MODEL indexes the model's frame_list with the shadow's frame index.
            problem("shadow MDS has more frames than the model MDS")
    report.update(frames=len(model_objs), meshed=sum(1 for o in model_objs if o.mesh), triangles=tri,
                  shadow_triangles=shadow_tri, poly_num=list(cfg.poly_num) if cfg.poly_num else None)
    for name in texture_refs:
        if len(name) > TEXTURE_NAME_MAX:
            raise ConvertError(f"material texture {name!r} longer than {TEXTURE_NAME_MAX} chars")
    # skin: _MODEL builds MOTION_MDT visuals only for VERTEX_ANIME names already listed, and loads
    # "<model basename>.wgt" for them (character.cpp:2007-2058)
    order = [c for c, _ in stmts]
    bad_deform = [a for c, args in stmts if c == "VERTEX_ANIME" for a in args if not isinstance(a, str)]
    if bad_deform:
        # DC1's "VERTEX_ANIME 1": spiGetStackString returns NULL for an int and _VERTEX_ANIME strcpys it
        # (character.cpp:2451; wave3-dc2-player-draw section 4.2).
        raise ConvertError(f"VERTEX_ANIME takes frame-name strings in DC2, got {bad_deform!r} (DC1 int form crashes)")
    deform = [str(a) for c, args in stmts if c == "VERTEX_ANIME" for a in args]
    if deform:
        if order.index("VERTEX_ANIME") > order.index("MODEL"):
            raise ConvertError("VERTEX_ANIME after MODEL: _MODEL would build no skinned visual")
        if len(deform) > CHARA_DEFORM_FRAME_MAX:
            raise ConvertError(f"{len(deform)} VERTEX_ANIME frames > CHARA_DEFORM_FRAME_MAX {CHARA_DEFORM_FRAME_MAX}")
        for name in deform:
            if not name or len(name.encode("ascii")) > VERTEX_ANIME_NAME_MAX:
                raise ConvertError(f"VERTEX_ANIME name {name!r} does not fit alloc_vertex[][16]")
        weight_name = cfg.model.split(".", 1)[0] + ".wgt"
        report["skin"] = validate_wgt(member(weight_name, "model weight (<model>.wgt)"), model_objs, model_data,
                                      deform, weight_name)
    for tag in ("SCALE", "OBJECT_NAME2", "MOTION"):
        # these act on CObjectFrame::frame, which only exists once MODEL has run
        if tag in order and order.index(tag) < order.index("MODEL"):
            raise ConvertError(f"{tag} before MODEL")
    # motions
    if not cfg.motions and require_motion:
        problem("cfg has no MOTION")
    max_frames = {}
    for mid, mot, base, wgt in cfg.motions:
        if not 0 <= mid < MOTION_SET_MAX:
            raise ConvertError(f"MOTION id {mid} outside CHARA_MOTION_SET_MAX")
        if mot:
            stats = walk_mot(member(mot, "MOTION"), len(model_objs), mot)
            max_frames[mid] = stats["max_frame"]
            report.setdefault("motion_files", {})[mot] = stats
        for extra in (base, wgt):
            if extra:
                member(extra, "MOTION base/weight")
        if base:
            # _MOTION memcpys root->frame_num matrices from the .bbp into init_matrix
            got = len(member(base, "MOTION base"))
            if got != len(model_objs) * MATRIX_BYTES:
                raise ConvertError(f"{base} is {got} bytes; {cfg.model} needs {len(model_objs)} x {MATRIX_BYTES}")
    for mot, base, wgt in cfg.shadow_motions:
        if not cfg.shadow_model:
            raise ConvertError("SHADOW_MOTION without SHADOW_MODEL")
        if order.index("SHADOW_MOTION") < order.index("SHADOW_MODEL"):
            raise ConvertError("SHADOW_MOTION before SHADOW_MODEL (shadow_frame is NULL)")
        # _SHADOW_MOTION drops its first (.mot) argument; only base/weight files are read.
        for extra in (base, wgt):
            if extra:
                member(extra, "SHADOW_MOTION base/weight")
        if base and len(member(base, "SHADOW_MOTION base")) != len(shadow_objs) * MATRIX_BYTES:
            raise ConvertError(f"{base} does not hold {len(shadow_objs)} shadow matrices")
        if wgt:
            report["shadow_skin"] = validate_wgt(member(wgt, "SHADOW_MOTION weight"), shadow_objs,
                                                 member(cfg.shadow_model, "SHADOW_MODEL"), None, wgt)
    key_names = []
    for mid, keys in cfg.keys.items():
        for name, start, end, step in keys:
            if not name:
                raise ConvertError("DC2 KEY needs a name")
            raw = name.encode("cp932")
            if len(raw) > KEY_NAME_MAX:
                raise ConvertError(f"KEY name {name!r} exceeds CHRINFO_KEY_SET::name[0x24]")
            if not 0 <= start <= end or end > max_frames.get(mid, 0) or not math.isfinite(step) or step < 0:
                raise ConvertError(f"KEY {name!r} range {start}-{end} step {step} invalid for motion length {max_frames.get(mid, 0)}")
            key_names.append(name)
    report["key_names"] = key_names
    # entry objects
    total = 0
    resolved_groups: dict = {}
    for group, pairs in cfg.groups:
        for frame, size in pairs:
            total += 1
            if frame not in frame_names:
                # SearchFrame failure is silent at runtime; refuse it offline.
                problem(f"OBJECT_NAME2 group {group} frame {frame!r} is not in {cfg.model}")
                continue
            resolved_groups[group] = resolved_groups.get(group, 0) + 1
    if total > ENTRY_OBJECT_MAX:
        raise ConvertError("OBJECT_NAME2 entries exceed CHARA_ENTRY_OBJECT_MAX")
    report["groups"] = resolved_groups
    # textures
    imgs = []
    for idx, img in cfg.imgs:
        data = member(img, "IMG")
        imgs.append((img, data))
    if require_textures:
        provided: set[str] = set()
        for img, data in imgs:
            source_key = f"{pack_dir}/{model}.chr/{img}".lower()
            if catalog is not None and source_key in catalog:
                for entry in catalog[source_key]["entries"]:
                    if entry.get("type") != "texture":
                        continue
                    provided.add(entry["name"].casefold())
                    if catalog_root is not None:
                        for variant in entry["variants"]:
                            for level in variant["levels"]:
                                png = (catalog_root / level).read_bytes()
                                validate_png(png)
                                w, h = struct.unpack(">II", png[16:24])
                                if (w, h) != (entry["width"], entry["height"]):
                                    raise ConvertError(f"catalog PNG {level} is {w}x{h}, entry says {entry['width']}x{entry['height']}")
            elif data and data[:4] not in (b"IMG\0", b"IM2\0", b"IM3\0"):
                problem(f"{img} is not an IMG file and has no catalog source")
            elif data:
                count = struct.unpack_from("<I", data, 4)[0]
                for i in range(count):
                    provided.add(data[16 + i * 48:16 + i * 48 + 32].split(b"\0", 1)[0].decode("ascii").casefold())
            else:
                raise ConvertError(f"{img} has no payload and no catalog source {source_key}")
        missing = sorted(n for n in texture_refs if n.casefold() not in provided)
        if missing:
            problem(f"material textures not provided by IMG/catalog: {missing}")
        report["textures"] = sorted(texture_refs)
    # brain contract
    if contract is not None:
        missing_keys = [k for k in contract.key_names if k not in key_names]
        if missing_keys:
            raise ConvertError(f"motions the brain {contract.name} asks for are missing: {missing_keys}")
        for group, count in contract.groups.items():
            have = resolved_groups.get(group, 0)
            if have == 0:
                raise ConvertError(f"brain group {group} has no resolved frame")
            if group == CHARA_ENTRY_GROUP_DAMAGE and have < count:
                # _SET_DMG2 addresses group-3 entries by index.
                raise ConvertError(f"damage group 3 has {have} entries; the brain cfg binds {count}")
        missing_frames = [f for f in contract.stb_frame_names if f not in frame_names]
        if missing_frames:
            raise ConvertError(f"frames the brain script binds by name are missing: {missing_frames}")
        report["brain"] = {"name": contract.name, "keys_required": contract.key_names,
                           "keys_in_stb": contract.stb_motion_names, "groups_required": contract.groups,
                           "stb_frame_names": contract.stb_frame_names}
    if player is not None:
        report["player"] = check_player_contract(player, key_names, frame_names)
    report["warnings"] = warnings
    return report


# ---------------------------------------------------------------- player body contract (DC2 Max path)

# Motion names DC2's human move code asks for by literal (CActionChara, actionchara.cpp). The "-足" and
# "-キャタピラ" names and 左旋回 are Ridepod leg paths and are not part of the human body contract.
DC2_PLAYER_MOTION_LITERALS = {
    "立ち": "actionchara.cpp:1658,1726,2747,2756", "走り": "actionchara.cpp:1717,2741",
    "歩き": "actionchara.cpp:1719,2743", "バトル立ち": "actionchara.cpp:1656,1724",
    "バトル歩き（前）": "actionchara.cpp:1684", "バトル歩き（後）": "actionchara.cpp:1688",
    "バトル歩き（右）": "actionchara.cpp:1692", "バトル歩き（左）": "actionchara.cpp:1698",
    "落下中": "actionchara.cpp:1761", "持ち上げ停止": "actionchara.cpp:1813", "持ち上げ歩き": "actionchara.cpp:1829",
    "ためループ": "actionchara.cpp:1873", "ため移動": "actionchara.cpp:1876", "着地": "actionchara.cpp:3404",
}
# Frames the stock Max setup binds on the body. A failed SetRef prints and continues, leaving the part
# unparented after SetupMints' ResetParent (charasetup.cpp:186-210, 497-530).
DC2_MAX_ATTACH_FRAMES = {"ef00": "charasetup.cpp:186,507 (melee)", "gun_hand": "charasetup.cpp:197,507 (sub)",
                         "hat": "charasetup.cpp:210,507 (head)"}


@dataclass
class PlayerContract:
    name: str
    key_names: list           # Max info.cfg KEY names (the stb and C++ ask by these)
    stb_motion_names: list
    stb_frame_names: list     # names c01.stb binds that are Max body frames or hit-frame-like
    required_frames: list     # sockets the Ixion seam itself needs on the body


def player_contract(max_pack: bytes, max_stb: bytes | None, required_frames: list[str],
                    cfg_name: str = "info.cfg") -> PlayerContract:
    members = parse_pack(max_pack)
    cfg = parse_chr_cfg(members[cfg_name.casefold()].data.decode("cp932"))
    keys = [k[0] for mid in sorted(cfg.keys) for k in cfg.keys[mid] if k[0]]
    max_frames = {o.name for o in read_mds(members[cfg.model.casefold()].data, cfg.model)}
    strings = stb_strings(max_stb) if max_stb else set()
    frames = sorted(s for s in strings if s in max_frames or re.fullmatch(r"[bdm]col\d+|ef\d+|n?gun", s))
    return PlayerContract("max", keys, [k for k in keys if k in strings], frames, list(required_frames))


def check_player_contract(contract: PlayerContract, key_names: list, frame_names: list) -> dict:
    """Motions are strict (a missing name starts no motion: GetKeyListPtr returns NULL, character.cpp:1349);
    seam sockets are strict; Max-path attach and stb-bound frames are advisory (the Ixion seam decides)."""
    need = list(dict.fromkeys(list(DC2_PLAYER_MOTION_LITERALS) + contract.key_names))
    missing = [k for k in need if k not in key_names]
    if missing:
        raise ConvertError(f"player motions DC2 asks for are missing: {missing}")
    sockets = [f for f in contract.required_frames if f not in frame_names]
    if sockets:
        raise ConvertError(f"seam sockets missing from the body: {sockets}")
    advisory = list(dict.fromkeys(list(DC2_MAX_ATTACH_FRAMES) + contract.stb_frame_names))
    return {"motions_required": len(need), "seam_sockets": contract.required_frames,
            "max_path_frames_present": [f for f in advisory if f in frame_names],
            "max_path_frames_missing": [f for f in advisory if f not in frame_names]}


# ---------------------------------------------------------------- converter

def default_rename_frame(name: str) -> str:
    m = HIT_FRAME.match(name)
    return f"{m.group(1)}0{m.group(2)}" if m else name


def resolve_motion_table(mapping: dict, dc1_keys: list) -> list[dict]:
    rows = []
    for row in mapping["motions"]:
        name = row["name"]
        if "slot" in row:
            slot = row["slot"]
            if not 0 <= slot < len(dc1_keys):
                raise ConvertError(f"motion {name!r} maps to missing DC1 slot {slot}")
            dc1_name, start, end, step = dc1_keys[slot]
            start = row.get("start", start)
            end = row.get("end", end)
            step = row.get("step", step)
            src = f"slot {slot} ({dc1_name})"
        else:
            start, end, step = row["start"], row["end"], row["step"]
            src = "authored range"
        rows.append({"name": name, "start": int(start), "end": int(end), "step": float(step), "source": src,
                     "why": row.get("why", "")})
    return rows


def fmt(v: float) -> str:
    return f"{v:.2f}"


def author_cfg(display_name: str, imgs: list[str], model_mds: str, shadow_mds: str | None, mot: str,
               shadow_mot: str | None, body: tuple, scale: float, poly: tuple, groups: list, motions: list[dict],
               dc1_keys: list, brain_cfg: ChrCfg | None, aliases: list[dict] | None = None,
               deform: list[str] | None = None, bbp: str | None = None, wgt: str | None = None) -> str:
    out = ["v2;", "", f'NAME "{display_name}";', ""]
    for i, img in enumerate(imgs):
        out.append(f'IMG {i}, "{img}";')
    out += ["IMG_END;", "", "MATERIAL_ANIME 0;"]
    if deform:
        # Skinned donor: VERTEX_ANIME names the ALLOC_DBUFF skin frames and must precede MODEL (_MODEL builds the
        # MOTION_MDT visuals only for names already listed). DC1's `VERTEX_ANIME 1` int form is not carried.
        out.append("VERTEX_ANIME " + ", ".join(f'"{d}"' for d in deform) + ";")
    out.append(f'MODEL "{model_mds}";')
    for cmd, args in (brain_cfg.other if brain_cfg else []):
        if cmd == "OUTLINE":
            out.append(f'OUTLINE "", {fmt(float(args[1]))};')
    if shadow_mds:
        out.append(f'SHADOW_MODEL "{shadow_mds}";')
    out += ["", f"BODY_SIZE {fmt(body[0])}, {fmt(body[1])}, {fmt(body[2])};", "",
            f"POLY_NUM {poly[0]}, {poly[1]};", "", f"SCALE {scale:.6f}, {scale:.6f}, {scale:.6f};", ""]
    for group, pairs in groups:
        parts = []
        for frame, radius in pairs:
            parts.append(f'"{frame}"' if radius is None else f'"{frame}", {fmt(radius)}')
        out.append(f"OBJECT_NAME2 {group}, {', '.join(parts)};")
    out += ["", f'MOTION 0, "{mot}", "{bbp or ""}", "{wgt or ""}";']
    if shadow_mot:
        out.append(f'SHADOW_MOTION "{shadow_mot}", "", "";')
    out.append("KEY_START;")
    names = set()
    for row in motions:
        out.append(f'\tKEY "{row["name"]}", {row["start"]}, {row["end"]}, {fmt(row["step"])};')
        names.add(row["name"])
    # Keep every DC1 slot addressable by a stable ASCII name for later brains.
    for i, (_n, start, end, step) in enumerate(dc1_keys):
        out.append(f'\tKEY "dc1_{i:02d}", {start}, {end}, {fmt(step)};')
    # Profile aliases come after the dc1_NN slots, so key indices 0-N stay the DC1 slot numbers.
    for row in aliases or []:
        out.append(f'\tKEY "{row["name"]}", {row["start"]}, {row["end"]}, {fmt(row["step"])};')
    out += ["KEY_END;", "MOTION_END;", ""]
    se_names = [str(a[0]) for c, a in brain_cfg.se if c in ("SE", "SELP")] if brain_cfg else []
    if brain_cfg and brain_cfg.se and all(n in names for n in se_names):
        for cmd, args in brain_cfg.se:
            rendered = ", ".join(f'"{a}"' if isinstance(a, str) else (fmt(a) if isinstance(a, float) else str(a)) for a in args)
            out.append(("\t" if cmd in ("SE", "SELP") else "") + (f"{cmd} {rendered};" if rendered else f"{cmd};"))
        out.append("")
    return "\r\n".join(out) + "\r\n"


def neutral_groups(frame_names: list[str]) -> list:
    """Brainless OBJECT_NAME2 groups: DC1 hit/col frames by class, placeholder radius (TODO per brain)."""
    def cls(prefix: str) -> list:
        found = sorted((n for n in frame_names if re.fullmatch(prefix + r"\d+", n)), key=lambda n: (len(n), n))
        return [[n, NEUTRAL_RADIUS] for n in found]
    target = "lockon" if "lockon" in frame_names else frame_names[0]
    groups = [[0, [[target, NEUTRAL_RADIUS]]], [1, [[frame_names[0], None]]]]
    for group, prefix in ((2, "bcol"), (3, "dcol"), (4, "mcol")):
        if cls(prefix):
            groups.append([group, cls(prefix)])
    if sum(len(p) for _g, p in groups) > ENTRY_OBJECT_MAX:
        raise ConvertError("neutral OBJECT_NAME2 groups exceed CHARA_ENTRY_OBJECT_MAX")
    return groups


PROFILE_FIELDS = {"frame_style", "aliases", "scale", "scale_why", "why"}


def resolve_profile_aliases(profile: dict, dc1_keys: list) -> list[dict]:
    """Brainless profile aliases: extra KEY names over DC1 slots, for a DC2 script that asks for its
    own motion names (for example a player form's act script). Names must be unique and must not
    shadow the dc1_NN slot names."""
    unknown = set(profile) - PROFILE_FIELDS
    if unknown:
        raise ConvertError(f"unknown profile fields {sorted(unknown)}")
    rows = resolve_motion_table({"motions": profile.get("aliases", [])}, dc1_keys)
    seen: set = set()
    for row in rows:
        name = row["name"]
        if not isinstance(name, str) or not name:
            raise ConvertError("profile alias needs a non-empty name")
        if re.fullmatch(r"dc1_\d+", name):
            raise ConvertError(f"profile alias {name!r} shadows a dc1_NN slot name")
        if name in seen:
            raise ConvertError(f"profile alias {name!r} is listed twice")
        if len(name.encode("cp932")) > KEY_NAME_MAX:
            raise ConvertError(f"profile alias {name!r} exceeds CHRINFO_KEY_SET::name")
        seen.add(name)
    return rows


def convert(dc1_pack_path: Path, brain_pack_path: Path | None, brain_stb_path: Path | None, out_root: Path,
            prefix: str = "ix_", scale: float = DC1_TO_DC2_SCALE, mapping: dict | None = None,
            brain_model: str | None = None, profile: dict | None = None) -> dict:
    """Convert one rigid DC1 pack. With no brain pack the output is brainless: every DC1 key slot
    is carried as ``dc1_NN``, hit frames keep their DC1 names and OBJECT_NAME2 groups are neutral.
    A brainless ``profile`` ({frame_style, aliases, scale}) renames hit frames and appends KEY aliases;
    its scale, when present, replaces the ``scale`` argument (a player form is sized for its slot)."""
    if profile is not None and "scale" in profile:
        scale = float(profile["scale"])
    if not math.isfinite(scale) or scale <= 0:
        raise ConvertError("scale must be finite and positive")
    if profile is not None and brain_pack_path is not None:
        raise ConvertError("a profile is for brainless packs; with a brain pack pass a mapping")
    src_bytes = dc1_pack_path.read_bytes()
    brain_bytes = brain_pack_path.read_bytes() if brain_pack_path else None
    stb_bytes = brain_stb_path.read_bytes() if brain_stb_path else None
    src_model = dc1_pack_path.stem
    brain_model = brain_model or (brain_pack_path.stem if brain_pack_path else None)
    if not re.fullmatch(r"[A-Za-z0-9_]+", prefix):
        raise ConvertError("prefix must be [A-Za-z0-9_]+")
    out_model = f"{prefix}{src_model}"
    if len(out_model) > MODEL_NAME_MAX:
        raise ConvertError(f"namespaced model {out_model!r} exceeds BASE_MONSTER_TBL::model[16]")
    members = parse_pack(src_bytes)
    dc1_cfg_m = find_cfg_member(members, src_model)
    dc1_cfg = parse_chr_cfg(dc1_cfg_m.data.decode("cp932"), dc1_comment_names=True)
    if not dc1_cfg.model or len(dc1_cfg.motions) != 1:
        raise ConvertError("DC1 cfg must name one MODEL and one MOTION")
    _mid, dc1_mot, dc1_base, dc1_wgt = dc1_cfg.motions[0]
    # Skinned donor (SKINNED-R1): the MOTION names a .bbp and a .wgt. Rigid packs keep the old path untouched.
    skinned = bool(dc1_base or dc1_wgt or any(k.endswith(".wgt") for k in members))
    deform: list[str] = []
    shadow_dropped = None
    if skinned:
        if not (dc1_base and dc1_wgt):
            raise ConvertError("DC1 MOTION must name both a .bbp and a .wgt for a skinned donor")
        if dc1_cfg.model.split(".", 1)[0] + ".wgt" != dc1_wgt:
            raise ConvertError(f"weight {dc1_wgt!r} is not <model>.wgt; DC2 _MODEL loads the weight by model basename")
        if dc1_wgt.casefold() not in members or dc1_base.casefold() not in members:
            raise ConvertError(f"skinned donor lacks {dc1_base!r} or {dc1_wgt!r}")
        deform = [str(a) for c, args in dc1_cfg.other if c == "ALLOC_DBUFF" for a in args]
        if not deform:
            raise ConvertError("skinned donor has no ALLOC_DBUFF skin frame (VERTEX_ANIME would be empty)")
        if any(sb or sw for _sm, sb, sw in dc1_cfg.shadow_motions):
            present = [n for n in (dc1_cfg.shadow_motions[0][1], dc1_cfg.shadow_motions[0][2])
                       if n and n.casefold() in members]
            if present or (dc1_cfg.shadow_model and dc1_cfg.shadow_model.casefold() in members):
                raise ConvertError("skinned shadow (SHADOW_MOTION names .bbp/.wgt) is not supported yet: "
                                   + (f"the pack ships {present} (shadow-skin path needed)" if present else
                                      f"the pack ships {dc1_cfg.shadow_model} with a skinned SHADOW_MOTION"))
            # The cfg names a skinned shadow the pack does not ship (Dran: c12s.*). DC1 itself prints "not found"
            # and runs with no shadow frame (chararead.cpp:266-280), so the shadow is dropped, not invented.
            shadow_dropped = {"shadow_model": dc1_cfg.shadow_model,
                              "shadow_motion": list(dc1_cfg.shadow_motions[0]),
                              "why": "named by the DC1 cfg but absent from the pack; DC1's CommandSHADOW_MODEL prints "
                                     "'not found' and leaves shadow_frame NULL (chararead.cpp:266-280), so retail "
                                     "draws no shadow model for this body either"}
            dc1_cfg.shadow_model = None
            dc1_cfg.shadow_motions = []
    dc1_keys = dc1_cfg.keys.get(0, [])
    if not dc1_keys:
        raise ConvertError("DC1 cfg has no KEY slots")
    contract = brain_cfg = None
    if brain_bytes is not None:
        if mapping is None:
            mapping = DEFAULT_MAPPINGS.get((src_model, brain_model))
            if mapping is None:
                raise ConvertError(f"no built-in mapping for {src_model} on {brain_model}; pass --mapping")
        contract, brain_cfg = brain_contract(brain_bytes, brain_model, stb_bytes)
    elif mapping is not None:
        raise ConvertError("a motion/frame mapping needs the brain pack it maps onto")
    # Brain-specific: e202a binds two-digit xcol0N names; DC1-lineage DC2 brains (e11a, e25a) bind
    # one-digit names. Brainless output keeps DC1 names.
    frame_style = (mapping or profile or {}).get("frame_style", "two_digit" if mapping else "keep")
    if frame_style not in ("two_digit", "keep"):
        raise ConvertError(f"unknown frame_style {frame_style!r}")
    rename_frame = default_rename_frame if frame_style == "two_digit" else (lambda n: n)

    def ns(name: str) -> str:
        new = f"{prefix}{name}"
        if len(new) > PACK_NAME_MAX:
            raise ConvertError(f"namespaced member {new!r} too long")
        return new

    # textures: namespace every IMG entry name
    texture_map: dict[str, str] = {}
    img_names = []
    for _i, img in dc1_cfg.imgs:
        data = members[img.casefold()].data
        count = struct.unpack_from("<I", data, 4)[0]
        for i in range(count):
            tname = data[16 + i * 48:16 + i * 48 + 32].split(b"\0", 1)[0].decode("ascii")
            texture_map[tname.casefold()] = ns(tname)
        img_names.append(img)
    for new in texture_map.values():
        if len(new) > TEXTURE_NAME_MAX:
            raise ConvertError(f"namespaced texture {new!r} exceeds {TEXTURE_NAME_MAX} chars")
    out_entries: list[tuple[str, bytes]] = []
    stats = {}
    model_out, stats["model"] = rewrite_mds(members[dc1_cfg.model.casefold()].data, rename_frame, texture_map, dc1_cfg.model)
    out_entries.append((ns(dc1_cfg.model), model_out))
    skin_info = None
    if skinned:
        src_model_bytes = members[dc1_cfg.model.casefold()].data
        src_objs = read_mds(src_model_bytes, dc1_cfg.model)
        wgt_src = members[dc1_wgt.casefold()].data
        wstats = validate_wgt(wgt_src, src_objs, src_model_bytes, deform, dc1_wgt, limits=False)
        skin_bones = {b for f in wstats["frames"].values() for b in f["bones"]}
        out_names_by_index = [o.name for o in read_mds(model_out, "model")]
        renamed = [o.name for o, new in zip(src_objs, out_names_by_index) if o.name != new]
        if set(renamed) & (skin_bones | set(deform)):
            raise ConvertError(f"frame rename touched skin frames: {sorted(set(renamed) & (skin_bones | set(deform)))}")
        # DRAN-R1: a skin frame over 32 bones or 800 vertices becomes sibling visuals (split_skin_frame).
        bbp_src, wgt_out, splits = members[dc1_base.casefold()].data, wgt_src, []
        for name in list(deform):
            frame = wstats["frames"][name]
            vnum = mdt_header(src_model_bytes, src_objs[frame["frame"]].mesh)["vertex_num"]
            if frame["bone_count"] > SKIN_BONE_MAX or vnum > DEF_VRTX_MAX:
                model_out, bbp_src, wgt_out, split = split_skin_frame(model_out, bbp_src, wgt_out, name, dc1_cfg.model)
                splits.append(split)
                at = deform.index(name)
                deform[at:at + 1] = [v["name"] for v in split["visuals"]]
        if splits:
            out_entries[0] = (ns(dc1_cfg.model), model_out)  # the model is the first entry
        skin_objs = read_mds(model_out, "model") if splits else src_objs
        skin_indices = [next(o.index for o in skin_objs if o.name == name) for name in deform]
        bbp_out, bbp_stats = model_space_bbp(skin_objs, bbp_src, skin_indices, dc1_base)
        if splits:
            validate_wgt(wgt_out, skin_objs, model_out, deform, dc1_wgt + " (split)")
        skin_info = {"wgt": wstats, "bbp": bbp_stats, "vertex_anime": {"dc1": [a for c, args in dc1_cfg.other
                                                                                if c == "VERTEX_ANIME" for a in args],
                                                                        "dc2": deform}}
        if splits:
            skin_info["split"] = splits
    shadow_name = None
    if dc1_cfg.shadow_model:
        # Shadow frames are matched to model frames by name; leave their names alone.
        sh_out, stats["shadow"] = rewrite_mds(members[dc1_cfg.shadow_model.casefold()].data, lambda n: n, texture_map, dc1_cfg.shadow_model)
        shadow_name = ns(dc1_cfg.shadow_model)
        out_entries.append((shadow_name, sh_out))
    mot_bytes = members[dc1_mot.casefold()].data
    # DC1 MotionProc holds its last pose beyond the final channel key. Represent
    # that pose explicitly in DC2 instead of depending on its divide-by-zero path.
    max_frame = walk_mot(mot_bytes, len(read_mds(model_out, "model")), dc1_mot)["max_frame"]
    motion_key_clamps = []
    for slot, (name, start, end, step) in enumerate(dc1_keys):
        if end > max_frame:
            if start > max_frame:
                raise ConvertError(f"KEY {slot} starts beyond motion length {max_frame}")
            motion_key_clamps.append({"slot": slot, "start": start, "original_end": end,
                                      "end": max_frame, "step": step})
            dc1_keys[slot] = (name, start, max_frame, step)
            print(f"monster-converter: clamped KEY {slot} ({name}) end {end} -> {max_frame}; DC1 final-pose hold", file=sys.stderr)
    out_entries.append((ns(dc1_mot), mot_bytes))
    # DC2 _SHADOW_MOTION discards its first (.mot) argument before CreateAnimeDataEX, and native
    # rigid packs (e202a) have no SHADOW_MOTION: the shadow follows model frames matched by name.
    # So the DC1 shadow .mot is not carried; unmatched shadow frames are reported instead.
    shadow_mot = None
    if dc1_cfg.shadow_model:
        model_names = {o.name for o in read_mds(model_out, "model")}
        stats["shadow_frames_unmatched"] = [o.name for o in read_mds(members[dc1_cfg.shadow_model.casefold()].data, "shadow")
                                            if o.name not in model_names]
    img_out_names = []
    textures = {}
    for img in img_names:
        data = members[img.casefold()].data
        new_img = rename_img(data, texture_map)
        img_out_names.append(ns(img))
        out_entries.append((ns(img), new_img))
        textures[ns(img)] = (decode_chr_img(new_img), tim2_tex1(new_img))
    # POLY_NUM from the same triangle count the validator computes
    def tri_count(mds: bytes) -> int:
        return sum(validate_mdt(mds, o.mesh, "poly").triangles for o in read_mds(mds, "poly") if o.mesh)
    poly = (tri_count(model_out), tri_count(dict(out_entries)[shadow_name]) if shadow_name else 0)
    motions = resolve_motion_table(mapping, dc1_keys) if mapping else []
    aliases = resolve_profile_aliases(profile, dc1_keys) if profile else []
    groups = mapping["groups"] if mapping else neutral_groups([o.name for o in read_mds(model_out, "model")])
    body = tuple(v * scale for v in (dc1_cfg.body_size or (0.0, 0.0, 0.0)))
    skin_bbp_name = skin_wgt_name = None
    if skinned:
        basename = ns(dc1_cfg.model).split(".", 1)[0]
        skin_bbp_name, skin_wgt_name = f"{basename}.bbp", f"{basename}.wgt"
        for name in (skin_bbp_name, skin_wgt_name):
            if len(name) > PACK_NAME_MAX:
                raise ConvertError(f"namespaced member {name!r} too long")
        out_entries.append((skin_bbp_name, bbp_out))
        out_entries.append((skin_wgt_name, wgt_out))
    cfg_text = author_cfg(out_model, img_out_names, ns(dc1_cfg.model), shadow_name, ns(dc1_mot), shadow_mot,
                          body, scale, poly, groups, motions, dc1_keys, brain_cfg, aliases,
                          deform or None, skin_bbp_name, skin_wgt_name)
    cfg_bytes = cfg_text.encode("cp932")
    entries = [e for e in out_entries if e[0].endswith(".mds")]
    entries += [e for e in out_entries if e[0].endswith(".mot")]
    entries += [e for e in out_entries if e[0].endswith((".bbp", ".wgt"))]
    entries += [e for e in out_entries if e[0].endswith(".img")]
    entries.append((f"{out_model}.cfg", cfg_bytes))
    pack = build_pack(entries)
    # catalog fragment
    catalog_sources = []
    png_files = {}
    for img_name, (decoded, tex1s) in textures.items():
        source = f"dungeon/monster/{out_model}.chr/{img_name}"
        entries_json = []
        for i, (tname, (png, w, h)) in enumerate(decoded.items()):
            rel = f"{source}/{tname}-entry-{i}-picture-0-variant-self-mip-0.png"
            png_files[rel] = png
            entries_json.append({"block": 0, "bpp": 32, "clamp": 0, "format": "rgba8", "height": h, "name": tname,
                                 "no_image": False, "picture": 0, "source_bpp": 8, "swizzled": True, "tex0": 0,
                                 "tex1": tex1s[i], "type": "texture",
                                 "variants": [{"levels": [rel], "palette_source": tname}], "width": w})
        catalog_sources.append({"entries": entries_json, "kind": "img", "size": 0, "source": source})
    catalog = {"schema_version": 1, "sources": catalog_sources}
    out_root = out_root.resolve()
    out_root.parent.mkdir(parents=True, exist_ok=True)
    if out_root.exists():
        raise ConvertError(f"output {out_root} already exists; choose a new path")
    with tempfile.TemporaryDirectory(prefix=out_root.name + ".tmp-", dir=out_root.parent) as staging_name:
        staging = Path(staging_name)
        chr_path = staging / "data" / "dungeon" / "monster" / f"{out_model}.chr"
        chr_path.parent.mkdir(parents=True)
        chr_path.write_bytes(pack)
        cat_root = staging / "port_data"
        for rel, png in png_files.items():
            p = cat_root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(png)
        (cat_root / "catalog.json").write_text(json.dumps(catalog, indent=1), encoding="utf-8")
        cat_index = {s["source"].lower(): s for s in catalog_sources}
        report = validate_chr(pack, out_model, contract, cat_index, cat_root)
        provenance = {
            "format": "ixion-monster-pack", "version": 1,
            "output_model": out_model, "output_chr": f"data/dungeon/monster/{out_model}.chr",
            "output_chr_sha256": sha256(pack),
            "sources": {"dc1_pack": {"path": dc1_pack_path.name, "sha256": sha256(src_bytes)},
                        "brain_pack": {"path": brain_pack_path.name, "sha256": sha256(brain_bytes)} if brain_bytes else None,
                        "brain_stb": {"path": brain_stb_path.name, "sha256": sha256(stb_bytes)} if stb_bytes else None},
            "options": {"prefix": prefix, "scale": scale, "brain": brain_model,
                        "frame_rename": "xcolN -> xcol0N" if frame_style == "two_digit" else "none (DC1 names kept)",
                        "groups_radius": "brain table" if mapping else f"placeholder {NEUTRAL_RADIUS} (TODO: brain)",
                        "texture_suffix_reserved": TEXTURE_SUFFIX},
            "scale_note": "applied through cfg SCALE (base_scale); BODY_SIZE multiplied by scale; geometry and .mot bytes unchanged",
            "motion_table": motions, "profile_aliases": aliases, "groups": groups,
            "dc1_slots": [list(k) for k in dc1_keys],
            "motion_key_clamps": motion_key_clamps,
            "dc1_cfg_skipped_statements": dc1_cfg.skipped,
            "rewrite_stats": stats, "texture_map": texture_map, "catalog_fragment": "port_data/catalog.json",
            "validation": report,
        }
        if skin_info is not None:
            # Rigid provenance stays byte-identical: these keys exist only for skinned donors.
            provenance["skin"] = skin_info
            provenance["copied_unchanged"] = [dc1_mot] if "split" in skin_info else [dc1_mot, dc1_wgt]
            provenance["dropped_skin"] = {"shadow_mot": [sm for sm, _b, _w in dc1_cfg.shadow_motions],
                                          "dc1_cfg_commands": sorted({c for c, _ in dc1_cfg.other}
                                                                     - {"ALLOC_DBUFF", "MATERIAL_ANIME", "IMG_END"})}
            if shadow_dropped is not None:
                provenance["dropped_skin"]["shadow"] = shadow_dropped
        (staging / "provenance.json").write_text(json.dumps(provenance, indent=1, ensure_ascii=False), encoding="utf-8")
        replace_with_retry(staging, out_root)
    return provenance


def replace_with_retry(src: Path, dst: Path, tries: int = 5) -> None:
    """os.replace of a freshly written directory can hit a transient WinError 5 (scanner holding a handle)."""
    import time
    for attempt in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == tries - 1:
                raise
            time.sleep(0.5 * (attempt + 1))


# ---------------------------------------------------------------- skinned player body (BodyProfile)

# A BodyProfile (tools/profiles/*.json, names and numbers only, no retail bytes) maps one skinned DC1 body onto
# DC2's player slot. KEY 0-N keep DC1 order and ranges as dc1_00..dc1_NN so SetMotion(int) (GetKeyListIndexPtr)
# maps DC1 motion numbers 1:1; Max's 46 info.cfg KEY names follow as aliases. Frame renames only touch null
# frames that are neither skin bones nor meshed (.mot, .bbp and .wgt address frames by index) and are applied to
# the shadow MDS too so _SHADOW_MODEL's name link still pairs them. Synthesised frames are null frames appended
# after the last model frame (so every existing index stays valid) with a matching .bbp row.
PROFILES_DIR = Path(__file__).resolve().parent / "profiles"
BODY_PROFILE_FORMAT = "ixion-body-profile"
BODY_PROFILE_REQUIRED = {"frame_renames", "groups", "body_size", "outline", "seam_sockets", "aliases"}
BODY_PROFILE_OPTIONAL = {"format", "version", "name", "why", "source", "synth_frames", "weapon_hit_frame", "scale",
                         "scale_why", "_status", "frame_renames_optional_absent",
                         # Xiao R1: a skin-frame subset of ALLOC_DBUFF, a weapon with no melee hit frame (null), and
                         # weapon frames the handler reads by name (her sling's eff30) that must survive conversion.
                         "deform_frames", "deform_frames_why", "weapon_hit_frame_why", "weapon_points",
                         "weapon_points_why"}
SYNTH_FRAME_FIELDS = {"name", "parent", "local_translation", "model_offset", "model_target", "why"}
SYNTH_OFFSET_FIELDS = ("local_translation", "model_offset", "model_target")


def load_body_profile(profile) -> dict:
    """Read and check a BodyProfile (a path or an already-parsed dict). Unknown fields are refused so a typo
    cannot silently fall back to a default."""
    doc = json.loads(Path(profile).read_text(encoding="utf-8")) if isinstance(profile, (str, Path)) else profile
    if not isinstance(doc, dict):
        raise ConvertError("body profile must be a JSON object")
    unknown = set(doc) - BODY_PROFILE_REQUIRED - BODY_PROFILE_OPTIONAL
    if unknown:
        raise ConvertError(f"unknown body profile fields {sorted(unknown)}")
    missing = BODY_PROFILE_REQUIRED - set(doc)
    if missing:
        raise ConvertError(f"body profile lacks {sorted(missing)}")
    if doc.get("format", BODY_PROFILE_FORMAT) != BODY_PROFILE_FORMAT or doc.get("version", 1) != 1:
        raise ConvertError("body profile format/version is not ixion-body-profile 1")
    renames = doc["frame_renames"]
    if not isinstance(renames, dict):
        raise ConvertError("frame_renames must map DC1 frame -> [DC2 name, why]")
    for old, val in renames.items():
        if not (isinstance(val, list) and len(val) == 2 and isinstance(val[0], str) and val[0]):
            raise ConvertError(f"frame_renames[{old!r}] must be [DC2 name, why]")
    targets = [v[0] for v in renames.values()]
    synth = doc.get("synth_frames", [])
    for row in synth:
        if not isinstance(row, dict) or set(row) - SYNTH_FRAME_FIELDS or not {"name", "parent"} <= set(row):
            raise ConvertError(f"synth frame needs name, parent and one offset, got {row!r}")
        given = [f for f in SYNTH_OFFSET_FIELDS if f in row]
        if len(given) != 1:
            raise ConvertError(f"synth frame {row['name']!r} needs exactly one of local_translation / model_offset "
                               "/ model_target")
        vec = row[given[0]]
        if not (isinstance(vec, list) and len(vec) == 3 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in vec)):
            raise ConvertError(f"synth frame {row['name']!r} offset must be three finite numbers")
        targets.append(row["name"])
    if len(set(targets)) != len(targets):
        raise ConvertError("body profile names a DC2 frame twice (renames plus synth frames)")
    for name in targets:
        if not re.fullmatch(r"[A-Za-z0-9_]{1,31}", name):
            raise ConvertError(f"DC2 frame name {name!r} must be 1-31 ASCII word characters")
    b = doc["body_size"]
    if not (isinstance(b, list) and len(b) == 3 and all(isinstance(v, (int, float)) for v in b)):
        raise ConvertError("body_size must be three numbers")
    if "scale" in doc and not (isinstance(doc["scale"], (int, float)) and math.isfinite(doc["scale"]) and doc["scale"] > 0):
        raise ConvertError("profile scale must be finite and positive")
    for row in doc["aliases"]:
        if not (isinstance(row, list) and len(row) == 3 and isinstance(row[0], str)
                and (isinstance(row[1], int) or (isinstance(row[1], list) and len(row[1]) == 3))):
            raise ConvertError(f"alias row must be [name, slot | [start, end, step], why], got {row!r}")
    if "weapon_hit_frame" in doc and not (doc["weapon_hit_frame"] is None or
                                          (isinstance(doc["weapon_hit_frame"], str) and doc["weapon_hit_frame"])):
        raise ConvertError("weapon_hit_frame must be a frame name or null (a weapon with no melee hit frame)")
    for field in ("deform_frames", "weapon_points"):
        if field in doc and not (isinstance(doc[field], list) and doc[field]
                                 and all(isinstance(v, str) and v for v in doc[field])
                                 and len(set(doc[field])) == len(doc[field])):
            raise ConvertError(f"{field} must be a non-empty list of distinct frame names")
    out = dict(doc)
    out.setdefault("synth_frames", [])
    out.setdefault("weapon_hit_frame", "dcol1")  # charakey.cpp:119 reads dcol1 on the weapon part
    return out


# Toan's mapping (TOAN-BODY-R1) now lives in tools/profiles/toan-c01d.json; it stays the default profile.
TOAN_C01D = load_body_profile(PROFILES_DIR / "toan-c01d.json")


def _mat_mul(a, b) -> list:
    """Column-major 4x4 product a*b (element index col*4+row; translation in 12..14), as DC1 chains bones."""
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def _solve3(m, v) -> list:
    """Solve M x = v for the upper 3x3 of a column-major 4x4 (Cramer's rule)."""
    a = [[m[c * 4 + r] for c in range(3)] for r in range(3)]

    def det(x):
        return (x[0][0] * (x[1][1] * x[2][2] - x[1][2] * x[2][1]) - x[0][1] * (x[1][0] * x[2][2] - x[1][2] * x[2][0])
                + x[0][2] * (x[1][0] * x[2][1] - x[1][1] * x[2][0]))
    d = det(a)
    if abs(d) < 1e-9:
        raise ConvertError("synth frame parent has a singular bind rotation")
    out = []
    for col in range(3):
        x = [row[:] for row in a]
        for r in range(3):
            x[r][col] = v[r]
        out.append(det(x) / d)
    return out


def bind_chain(objs: list, bbp: bytes) -> list:
    """Model-space bind matrices: DC1's .bbp rows are parent-relative (TOAN-BODY-R2), chained root-down."""
    world: list = []
    for o in objs:
        local = list(struct.unpack_from("<16f", bbp, o.index * MATRIX_BYTES))
        world.append(_mat_mul(world[o.parent], local) if o.parent >= 0 else local)
    return world


def model_space_bbp(objs: list, bbp: bytes, skin_indices: list[int], label: str) -> tuple[bytes, dict]:
    """Rewrite a DC1 parent-relative .bbp as the model-space table DC2 reads.

    DC2 copies the .bbp over init_matrix (character.cpp:2359-2360) and skins with inv(base[skin]) * base[bone]
    (port visualmotion.cpp), so every row must be the chained bind matrix. DC1 instead chains parent.bone_base *
    base_matrices[frame] at run time and starts the chain at the skin owner's parent. Toan's runtime seam
    (AccumulateDc1BindPose, TOAN-BODY-R2) chains every row root-down and then copies each skin owner's parent
    entry over the skin owner's own; this does the same offline, so a monster needs no runtime seam and the
    .bbp is the only skinned member that differs from DC1.
    Rows of rigid parts may be all zero in DC1 (never read by the skin); they chain to zero and stay unread.
    """
    if len(bbp) != len(objs) * MATRIX_BYTES:
        raise ConvertError(f"{label}: .bbp holds {len(bbp) // MATRIX_BYTES} rows for {len(objs)} frames")
    world = bind_chain(objs, bbp)
    reset = []
    for skin in skin_indices:
        parent = objs[skin].parent
        if parent >= 0:
            world[skin] = list(world[parent])
            reset.append({"skin": objs[skin].name, "index": skin, "parent": objs[parent].name})
    out = b"".join(struct.pack("<16f", *m) for m in world)
    zero_rows = sum(1 for o in objs if not any(struct.unpack_from("<16f", bbp, o.index * MATRIX_BYTES)))
    return out, {"rows": len(objs), "zero_source_rows": zero_rows, "skin_owner_reset_to_parent": reset,
                 "rule": "world[i] = world[parent] * local[i]; world[skin] = world[parent(skin)] "
                         "(AccumulateDc1BindPose, ixion_toan_body.cpp)"}


IDENTITY_ROW = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


def identity_zero_bind_ancestors(objs: list, bbp: bytes, frames: list[int]) -> tuple[bytes, list]:
    """Write identity over every all-zero .bbp row that is an ancestor of ``frames`` (skin owners, synth parents).

    DC1 never reads those rows: MotionProc2 starts the bind chain at the skin owner's parent with identity
    (Chronicle gameutil_motion.cpp:87-89). DC2 chains every row root-down (AccumulateDc1BindPose,
    ixion_toan_body.cpp), so one zero ancestor (Xiao's c04b dummyRoot) zeroes the skin owner and every bone under
    it, and DC2's inv(base[skin]) * base[bone] has no inverse. Identity there gives DC2 DC1's chain. Bodies with
    no such row (Toan, Goro, Ungaga) come back byte-identical.
    """
    fixed: list = []
    out = bytearray(bbp)
    for start in frames:
        i = objs[start].parent if start >= 0 else -1
        while i >= 0:
            if not any(struct.unpack_from("<16f", out, i * MATRIX_BYTES)) and objs[i].name not in fixed:
                struct.pack_into("<16f", out, i * MATRIX_BYTES, *IDENTITY_ROW)
                fixed.append(objs[i].name)
            i = objs[i].parent
    return bytes(out), fixed


def append_null_frames(mds: bytes, bbp: bytes, synth: list, label: str) -> tuple[bytes, bytes, list]:
    """Append synthesised null frames to an MDS and its .bbp.

    Each new 112-byte record goes after the last record, so every existing frame index (.mot targets, .wgt
    frame/bone ids, .bbp rows, shadow pairing) is unchanged. The MDT data that followed the table moves down by
    112 bytes per new frame, so every non-zero absolute ``mesh`` offset is shifted by the same amount (MDT-internal
    offsets are relative to the MDT and do not move). The record and the new .bbp row hold the same local matrix:
    identity rotation plus the parent-relative translation. ``model_offset`` is a bind-pose model-space delta from
    the parent, turned into the parent-local translation through the chained .bbp rotation.
    """
    objs = read_mds(mds, label)
    if len(bbp) != len(objs) * MATRIX_BYTES:
        raise ConvertError(f"{label}: .bbp holds {len(bbp) // MATRIX_BYTES} rows for {len(objs)} frames")
    if not synth:
        return mds, bbp, []
    names = [o.name for o in objs]
    world = bind_chain(objs, bbp)
    count = len(objs)
    add = len(synth)
    shift = add * MDS_RECORD
    table_end = 16 + count * MDS_RECORD
    out = bytearray(mds[:table_end])
    for o in objs:
        if o.mesh:
            struct.pack_into("<i", out, 16 + o.index * MDS_RECORD + 40, o.mesh + shift)
    new_bbp = bytearray(bbp)
    info = []
    for k, row in enumerate(synth):
        name, parent_name = row["name"], row["parent"]
        if name in names:
            raise ConvertError(f"{label}: synth frame {name!r} already exists")
        if names.count(parent_name) != 1:
            raise ConvertError(f"{label}: synth frame {name!r} parent {parent_name!r} occurs {names.count(parent_name)} times")
        parent = names.index(parent_name)
        if "local_translation" in row:
            local_t = [float(v) for v in row["local_translation"]]
        elif "model_offset" in row:
            local_t = _solve3(world[parent], [float(v) for v in row["model_offset"]])
        else:
            # Xiao R1: an absolute bind-pose model-space target (her keri under rotated leg frames, floor Y 0).
            local_t = _solve3(world[parent], [float(t) - world[parent][12 + k] for k, t in enumerate(row["model_target"])])
        local = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, local_t[0], local_t[1], local_t[2], 1.0]
        index = count + k
        rec = struct.pack("<ii", index, MDS_RECORD) + name.encode("ascii").ljust(32, b"\0")
        rec += struct.pack("<ii", 0, parent) + struct.pack("<16f", *local)
        out += rec
        new_bbp += struct.pack("<16f", *local)
        names.append(name)
        bound = _mat_mul(world[parent], local)
        world.append(bound)
        info.append({"name": name, "index": index, "parent": parent_name, "parent_index": parent,
                     "local_translation": [round(v, 6) for v in local_t],
                     "model_offset": row.get("model_offset"),
                     **({"model_target": row["model_target"]} if "model_target" in row else {}),
                     "bind_parent_model": [round(v, 4) for v in world[parent][12:15]],
                     "bind_model": [round(v, 4) for v in bound[12:15]], "why": row.get("why", "")})
    struct.pack_into("<I", out, 8, count + add)
    out += mds[table_end:]
    result = bytes(out)
    new_objs = read_mds(result, label)
    for o in objs:
        if o.mesh:
            a, b = mds[o.mesh:o.mesh + mdt_header(mds, o.mesh)["unk_08"]], result[o.mesh + shift:o.mesh + shift + mdt_header(mds, o.mesh)["unk_08"]]
            if a != b or new_objs[o.index].mesh != o.mesh + shift:
                raise ConvertError(f"{label}: MDT of {o.name} did not move intact")
    return result, bytes(new_bbp), info


# ---------------------------------------------------------------- skin split (DRAN-R1)

# DC2's skinned visual takes at most 32 bones (CreateVertexWeight, visualmotion.cpp:114). DeformMesh, DC2's CPU skin
# path, accumulates into float def_vrtx[800][4] (gameutil.cpp:28); the GPU path does not use it, but a visual kept
# under 800 vertices stays valid for both. A skin frame over either limit is split into sibling visuals.
DEF_VRTX_MAX = 800
SPLIT_SUFFIXES = "bcdefghijklmnopqrstuvwxyz"


@dataclass
class FacePrim:
    ftype: int
    material: int
    corners: list  # per corner: (vertex, [normal], [uv], [colour]) in FACES_ID index order


def face_kinds(ftype: int) -> list[str]:
    """Index order of one FACES_ID corner, as validate_mdt checks it: vertex, normal, uv, colour."""
    return (["vertex"] + ([] if ftype & MG_FACE_NO_NORMAL else ["normal"])
            + ([] if ftype & MG_FACE_NO_TEXTURE else ["uv"]) + (["colour"] if ftype & MG_FACE_COLOUR else []))


def read_face_prims(data: bytes, mesh: int) -> tuple[tuple[int, int], list[FacePrim]]:
    h = mdt_header(data, mesh)
    base = mesh + h["faces_ofs"]
    unk0, _fh, prims, unk_c = struct.unpack_from("<iiii", data, base)
    cur = base + FACES_HEADER
    out = []
    for _ in range(prims):
        ftype, vnum, mat = struct.unpack_from("<III", data, cur)
        cur += 12
        stride = len(face_kinds(ftype))
        idx = struct.unpack_from(f"<{vnum * stride}i", data, cur)
        cur += vnum * stride * 4
        out.append(FacePrim(ftype, mat, [tuple(idx[k * stride:(k + 1) * stride]) for k in range(vnum)]))
    return (unk0, unk_c), out


def prim_triangles(p: FacePrim) -> list[tuple]:
    """Triangles of one primitive with their winding (list 3, strip 4 alternating, fan 5)."""
    c, prim = p.corners, p.ftype & MG_FACE_PRIM_MASK
    if prim == 3:
        return [(c[k], c[k + 1], c[k + 2]) for k in range(0, len(c) - 2, 3)]
    if prim == 4:
        return [(c[k], c[k + 1], c[k + 2]) if k % 2 == 0 else (c[k + 1], c[k], c[k + 2]) for k in range(len(c) - 2)]
    return [(c[0], c[k], c[k + 1]) for k in range(1, len(c) - 1)]


def wgt_blocks(data: bytes) -> list[tuple[bytes, list[bytes]]]:
    """(32-byte header, [32-byte entries]) per weight block, in file order."""
    pos, out = 0, []
    while True:
        count, more = struct.unpack_from("<II", data, pos + 16)
        out.append((data[pos:pos + WGT_RECORD], [data[pos + WGT_RECORD * (k + 1):pos + WGT_RECORD * (k + 2)]
                                                 for k in range(count)]))
        pos += WGT_RECORD * (count + 1)
        if not more:
            return out


def build_wgt(blocks: list[tuple[bytes, list[bytes]]]) -> bytes:
    """Write weight blocks; ``next`` is the byte step to the following block and 0 on the last (visualmotion.cpp)."""
    out = bytearray()
    for i, (head, entries) in enumerate(blocks):
        h = bytearray(head)
        struct.pack_into("<II", h, 16, len(entries), 0 if i == len(blocks) - 1 else WGT_RECORD * (len(entries) + 1))
        out += h + b"".join(entries)
    return bytes(out)


def _partition_units(units: list, vertex_bones: dict, positions: list, bone_cap: int, vertex_cap: int):
    """First-fit packing of face units into groups under both caps, tried in face order and sorted by centroid
    along x, y and z; the order giving the fewest groups, then the fewest duplicated vertices, wins."""
    for u in units:
        bones = set().union(*(vertex_bones.get(v, set()) for v in u["vertices"]))
        if len(bones) > bone_cap or len(u["vertices"]) > vertex_cap:
            raise ConvertError(f"one face unit needs {len(bones)} bones / {len(u['vertices'])} vertices; caps "
                               f"{bone_cap} / {vertex_cap}")
        u["bones"] = bones
    orders = [("face order", units)]
    for axis, name in enumerate("xyz"):
        def centroid(u, axis=axis):
            return (sum(positions[v][axis] for v in u["vertices"]) / len(u["vertices"]), u["key"])
        orders.append((f"centroid {name}", sorted(units, key=centroid)))
    best = None
    for label, order in orders:
        groups = []
        for u in order:
            for g in groups:
                if len(g["bones"] | u["bones"]) <= bone_cap and len(g["vertices"] | u["vertices"]) <= vertex_cap:
                    break
            else:
                g = {"bones": set(), "vertices": set(), "units": []}
                groups.append(g)
            g["bones"] |= u["bones"]
            g["vertices"] |= u["vertices"]
            g["units"].append(u)
        dup = sum(len(g["vertices"]) for g in groups) - len(set().union(*(g["vertices"] for g in groups)))
        if best is None or (len(groups), dup) < (len(best[1]), best[2]):
            best = (label, groups, dup)
    return best


def write_split_mdt(data: bytes, mesh: int, faces_hdr: tuple[int, int], prims: list[FacePrim]) -> tuple[bytes, dict]:
    """A new MDT holding only what ``prims`` index: vertex, normal, uv and colour arrays sub-selected (ascending
    source order, so shared corners are duplicated per visual), corners renumbered, every material copied so the
    material indices are unchanged. Sections are laid out as DC1 writes them: vertices, faces, normals, colours,
    uvs, materials, each 16-aligned."""
    h = mdt_header(data, mesh)
    used: dict = {"vertex": set(), "normal": set(), "uv": set(), "colour": set()}
    for p in prims:
        kinds = face_kinds(p.ftype)
        for corner in p.corners:
            for kind, value in zip(kinds, corner):
                used[kind].add(value)
    maps = {kind: {src: i for i, src in enumerate(sorted(vals))} for kind, vals in used.items()}
    faces = bytearray(struct.pack("<iiii", faces_hdr[0], FACES_HEADER, len(prims), faces_hdr[1]))
    for p in prims:
        kinds = face_kinds(p.ftype)
        faces += struct.pack("<III", p.ftype, len(p.corners), p.material)
        for corner in p.corners:
            faces += struct.pack(f"<{len(corner)}i", *(maps[k][v] for k, v in zip(kinds, corner)))

    def rows(kind: str) -> bytes:
        ofs = h[f"{kind}_ofs"]
        return b"".join(data[mesh + ofs + 16 * i:mesh + ofs + 16 * i + 16] for i in sorted(used[kind]))

    body = bytearray(MDT_HEADER)
    layout = {}
    for name, blob in (("vertex", rows("vertex")), ("faces", bytes(faces)), ("normal", rows("normal")),
                       ("colour", rows("colour")), ("uv", rows("uv")),
                       ("material", data[mesh + h["material_ofs"]:mesh + h["material_ofs"] + h["material_num"] * MDT_MATERIAL])):
        layout[name] = len(body) if blob else 0
        body += blob + b"\0" * (-len(blob) % 16)
    n = {k: len(v) for k, v in used.items()}
    struct.pack_into("<4s15i", body, 0, b"MDT\0", MDT_HEADER, len(body), n["vertex"], layout["vertex"], n["normal"],
                     layout["normal"], n["colour"], layout["colour"], len(faces), layout["faces"], n["uv"], layout["uv"],
                     h["material_num"], layout["material"], 0)
    return bytes(body), maps


def split_skin_frame(mds: bytes, bbp: bytes, wgt: bytes, frame_name: str, label: str,
                     bone_cap: int = SKIN_BONE_MAX, vertex_cap: int = DEF_VRTX_MAX) -> tuple[bytes, bytes, bytes, dict]:
    """Split one skinned frame into sibling visuals of at most ``bone_cap`` bones and ``vertex_cap`` vertices.

    Units are whole strips and fans plus the single triangles of list primitives (winding is kept). Visual 0
    rewrites the frame's MDT in place (zero padded to the old size, so no other offset moves); each further visual
    is a new frame ``<name>_b``, ``_c``... appended after the last record (every existing frame index in .mot,
    .wgt and .bbp is unchanged; mesh offsets shift by 112 per record as in append_null_frames), with the same
    parent and local matrix, its MDT appended at the end, and a copy of the frame's parent-relative .bbp row.
    The frame's weight blocks are rebuilt per visual with visual-local vertex ids. Conservation is checked:
    every source triangle lands in exactly one visual and every visual vertex carries its source weights."""
    objs = read_mds(mds, label)
    hits = [o for o in objs if o.name == frame_name]
    if len(hits) != 1 or not hits[0].mesh:
        raise ConvertError(f"{label}: skin frame {frame_name!r} is not one meshed frame")
    src = hits[0]
    if len(bbp) != len(objs) * MATRIX_BYTES:
        raise ConvertError(f"{label}: .bbp holds {len(bbp) // MATRIX_BYTES} rows for {len(objs)} frames")
    h = mdt_header(mds, src.mesh)
    faces_hdr, prims = read_face_prims(mds, src.mesh)
    blocks = wgt_blocks(wgt)
    vertex_bones: dict = {}
    vertex_weights: dict = {}
    for head, entries in blocks:
        fid, bone = struct.unpack_from("<Ii", head, 0)
        if fid != src.index:
            continue
        for e in entries:
            vid = struct.unpack_from("<I", e, 0)[0]
            vertex_bones.setdefault(vid, set()).add(bone)  # DC2 claims a slot for every entry, zero weight or not
            vertex_weights.setdefault(vid, []).append((bone, e[4:]))
    positions = [struct.unpack_from("<3f", mds, src.mesh + h["vertex_ofs"] + 16 * i) for i in range(h["vertex_num"])]
    units = []
    for pi, p in enumerate(prims):
        if p.ftype & MG_FACE_PRIM_MASK == 3:
            for k in range(0, len(p.corners) - 2, 3):
                units.append({"key": (pi, k), "prim": pi, "slice": (k, k + 3),
                              "vertices": {c[0] for c in p.corners[k:k + 3]}})
        else:
            units.append({"key": (pi, -1), "prim": pi, "slice": None, "vertices": {c[0] for c in p.corners}})
    strategy, groups, dup = _partition_units(units, vertex_bones, positions, bone_cap, vertex_cap)
    if len(groups) - 1 > len(SPLIT_SUFFIXES):
        raise ConvertError(f"{label}: {frame_name} needs {len(groups)} visuals")
    names = [frame_name] + [f"{frame_name}_{SPLIT_SUFFIXES[i]}" for i in range(len(groups) - 1)]
    taken = {o.name for o in objs}
    for name in names[1:]:
        if name in taken or len(name) > VERTEX_ANIME_NAME_MAX:
            raise ConvertError(f"{label}: split visual name {name!r} is taken or too long for VERTEX_ANIME")
    mdts, maps_per_group, prims_per_group = [], [], []
    for g in groups:
        out_prims: list[FacePrim] = []
        last_list = None
        for u in sorted(g["units"], key=lambda u: u["key"]):
            p = prims[u["prim"]]
            if u["slice"] is None:
                out_prims.append(FacePrim(p.ftype, p.material, list(p.corners)))
                last_list = None
            else:
                if last_list is None or last_list[0] != u["prim"]:
                    last_list = (u["prim"], FacePrim(p.ftype, p.material, []))
                    out_prims.append(last_list[1])
                last_list[1].corners.extend(p.corners[u["slice"][0]:u["slice"][1]])
        blob, maps = write_split_mdt(mds, src.mesh, faces_hdr, out_prims)
        mdts.append(blob)
        maps_per_group.append(maps)
        prims_per_group.append(read_face_prims(blob, 0)[1])  # what was written, in visual-local indices
    # conservation: triangles (with winding) and weights
    want: dict = {}
    for p in prims:
        for t in prim_triangles(p):
            want[t] = want.get(t, 0) + 1
    got: dict = {}
    for out_prims, maps in zip(prims_per_group, maps_per_group):
        back = {k: {v: s for s, v in m.items()} for k, m in maps.items()}
        for p in out_prims:
            kinds = face_kinds(p.ftype)
            for t in prim_triangles(p):
                key = tuple(tuple(back[k][v] for k, v in zip(kinds, c)) for c in t)
                got[key] = got.get(key, 0) + 1
    if got != want:
        raise ConvertError(f"{label}: split of {frame_name} lost or duplicated triangles")
    # MDS: grow the table, rewrite visual 0 in place, append the others
    count, add = len(objs), len(groups) - 1
    shift, table_end = add * MDS_RECORD, 16 + len(objs) * MDS_RECORD
    old_size = h["unk_08"]
    if len(mdts[0]) > old_size:
        raise ConvertError(f"{label}: split visual 0 ({len(mdts[0])} B) outgrew {frame_name}'s MDT ({old_size} B)")
    table = bytearray(mds[:table_end])
    for o in objs:
        if o.mesh:
            struct.pack_into("<i", table, 16 + o.index * MDS_RECORD + 40, o.mesh + shift)
    tail = bytearray(mds[table_end:])
    rel = src.mesh - table_end
    tail[rel:rel + old_size] = mdts[0].ljust(old_size, b"\0")
    tail += b"\0" * (-len(tail) % 16)
    src_rec = mds[16 + src.index * MDS_RECORD:16 + (src.index + 1) * MDS_RECORD]
    new_bbp = bytearray(bbp)
    appended = bytearray()
    visuals = []
    for k in range(1, len(groups)):
        index = count + k - 1
        offset = table_end + shift + len(tail) + len(appended)
        rec = bytearray(src_rec)
        struct.pack_into("<ii", rec, 0, index, MDS_RECORD)
        rec[8:40] = names[k].encode("ascii").ljust(32, b"\0")
        struct.pack_into("<i", rec, 40, offset)
        table += rec
        appended += mdts[k] + b"\0" * (-len(mdts[k]) % 16)
        new_bbp += bbp[src.index * MATRIX_BYTES:(src.index + 1) * MATRIX_BYTES]
    struct.pack_into("<I", table, 8, count + add)
    out_mds = bytes(table + tail + appended)
    new_objs = read_mds(out_mds, label)
    frame_ids = [src.index] + list(range(count, count + add))
    for fid, blob in zip(frame_ids, mdts):
        o = new_objs[fid]
        if out_mds[o.mesh:o.mesh + len(blob)] != blob:
            raise ConvertError(f"{label}: split visual {o.name} did not land at its mesh offset")
        validate_mdt(out_mds, o.mesh, f"{label}:{o.name} (split)")
    for o in objs:
        if o.mesh and o.index != src.index:
            size = mdt_header(mds, o.mesh)["unk_08"]
            if mds[o.mesh:o.mesh + size] != out_mds[o.mesh + shift:o.mesh + shift + size]:
                raise ConvertError(f"{label}: MDT of {o.name} did not move intact")
    # .wgt: the frame's blocks become one run per visual (local ids, empty blocks dropped), placed where the
    # frame's first block was; blocks of other frames are kept as they are.
    group_blocks = []
    for fid, maps in zip(frame_ids, maps_per_group):
        vmap = maps["vertex"]
        for head, entries in blocks:
            if struct.unpack_from("<I", head, 0)[0] != src.index:
                continue
            kept = [struct.pack("<I", vmap[struct.unpack_from("<I", e, 0)[0]]) + e[4:]
                    for e in entries if struct.unpack_from("<I", e, 0)[0] in vmap]
            if kept:
                group_blocks.append((struct.pack("<I", fid) + head[4:], kept))
    out_blocks, placed = [], False
    for head, entries in blocks:
        if struct.unpack_from("<I", head, 0)[0] == src.index:
            if not placed:
                out_blocks += group_blocks
                placed = True
        else:
            out_blocks.append((head, entries))
    out_wgt = build_wgt(out_blocks)
    # weights conserved per visual vertex
    for fid, maps in zip(frame_ids, maps_per_group):
        local: dict = {}
        for head, entries in out_blocks:
            f, bone = struct.unpack_from("<Ii", head, 0)
            if f == fid:
                for e in entries:
                    local.setdefault(struct.unpack_from("<I", e, 0)[0], []).append((bone, e[4:]))
        for s, v in maps["vertex"].items():
            if sorted(local.get(v, [])) != sorted(vertex_weights.get(s, [])):
                raise ConvertError(f"{label}: split visual {fid} vertex {v} lost the weights of source vertex {s}")
    referenced = set().union(*(set(m["vertex"]) for m in maps_per_group))
    for fid, name, g, blob, out_prims in zip(frame_ids, names, groups, mdts, prims_per_group):
        visuals.append({"name": name, "frame": fid, "vertices": len(g["vertices"]), "bones": len(g["bones"]),
                        "triangles": sum(len(prim_triangles(p)) for p in out_prims), "primitives": len(out_prims),
                        "mdt_bytes": len(blob)})
    info = {"frame": frame_name, "strategy": strategy, "bone_cap": bone_cap, "vertex_cap": vertex_cap,
            "source": {"vertices": h["vertex_num"], "triangles": sum(want.values()),
                       "bones": len(set().union(*vertex_bones.values())) if vertex_bones else 0,
                       "primitives": len(prims)},
            "visuals": visuals, "duplicated_vertices": dup,
            "unreferenced_source_vertices_dropped": h["vertex_num"] - len(referenced),
            "conservation": "every source triangle (with winding) in exactly one visual; every visual vertex keeps "
                            "its source (bone, weight) entries",
            "rule": "units = whole strips/fans + single list triangles; first-fit under both caps in face order and "
                    "by centroid x/y/z; fewest visuals then fewest duplicated vertices wins"}
    return out_mds, bytes(new_bbp), out_wgt, info


def _catalog_source(source: str, decoded: dict, tex1s: list, png_files: dict) -> dict:
    entries_json = []
    for i, (tname, (png, w, h)) in enumerate(decoded.items()):
        rel = f"{source}/{tname}-entry-{i}-picture-0-variant-self-mip-0.png"
        png_files[rel] = png
        entries_json.append({"block": 0, "bpp": 32, "clamp": 0, "format": "rgba8", "height": h, "name": tname,
                             "no_image": False, "picture": 0, "source_bpp": 8, "swizzled": True, "tex0": 0,
                             "tex1": tex1s[i], "type": "texture",
                             "variants": [{"levels": [rel], "palette_source": tname}], "width": w})
    return {"entries": entries_json, "kind": "img", "size": 0, "source": source}


def _namespace_textures(members: dict, imgs: list, ns) -> dict:
    texture_map = {}
    for _i, img in imgs:
        data = members[img.casefold()].data
        for i in range(struct.unpack_from("<I", data, 4)[0]):
            tname = data[16 + i * 48:16 + i * 48 + 32].split(b"\0", 1)[0].decode("ascii")
            texture_map[tname.casefold()] = ns(tname)
    for new in texture_map.values():
        if len(new) > TEXTURE_NAME_MAX:
            raise ConvertError(f"namespaced texture {new!r} exceeds {TEXTURE_NAME_MAX} chars")
    return texture_map


def author_toan_cfg(name: str, img: str, model: str, shadow: str, mot: str, bbp: str, wgt: str, shadow_bbp: str,
                    shadow_wgt: str, deform: list, poly: tuple, scale: float, mapping: dict, keys: list[dict]) -> str:
    out = ["v2;", "", f'NAME "{name}";', "", f'IMG 0, "{img}";', "IMG_END;", "", "MATERIAL_ANIME 0;",
           "VERTEX_ANIME " + ", ".join(f'"{d}"' for d in deform) + ";", "", f'MODEL "{model}";']
    out += [f'OUTLINE "{part}", {fmt(width)};' for part, width in mapping["outline"]]
    b = mapping["body_size"]
    out += [f'SHADOW_MODEL "{shadow}";', "", f"BODY_SIZE {fmt(b[0])}, {fmt(b[1])}, {fmt(b[2])};", "",
            f"POLY_NUM {poly[0]}, {poly[1]};", "", f"SCALE {scale:.6f}, {scale:.6f}, {scale:.6f};", ""]
    for group, pairs in mapping["groups"]:
        out.append(f"OBJECT_NAME2 {group}, " + ", ".join(f'"{f}"' if r is None else f'"{f}", {fmt(r)}' for f, r in pairs) + ";")
    out += ["", f'MOTION 0, "{mot}", "{bbp}", "{wgt}";', f'SHADOW_MOTION "", "{shadow_bbp}", "{shadow_wgt}";',
            "KEY_START;"]
    out += [f'\tKEY "{k["name"]}", {k["start"]}, {k["end"]}, {fmt(k["step"])};' for k in keys]
    out += ["KEY_END;", "MOTION_END;", ""]
    return "\r\n".join(out) + "\r\n"


def author_part_cfg(name: str, img: str, model: str) -> str:
    """DC2 weapon dialect (as mainchr/ws001.chr info.cfg): no shadow, no motion."""
    out = ["v2;", "", f'NAME "{name}";', "", f'IMG 0, "{img}";', "IMG_END;", "", "MATERIAL_ANIME 0;",
           f'MODEL "{model}";', 'OUTLINE "", 2.00;', "BODY_SIZE 0.00, 0.00, 0.00;", ""]
    return "\r\n".join(out) + "\r\n"


def toan_keys(mapping: dict, dc1_keys: list, motion_frames: int | None = None) -> list[dict]:
    # Xiao R1: c04b base.cfg keys slots 29 (690-710) and 30 (756-766) past its .mot's last frame (568). DC2's KEY
    # check refuses such a range, so those slots are written as DC1's own placeholder row (KEY 1, 1, 1.0, as c04b's
    # slots 3, 5 and 14-17) and no alias may target them. Bodies with every slot inside their motion are unchanged.
    beyond = {i for i, (_n, _s, e, _st) in enumerate(dc1_keys) if motion_frames is not None and e > motion_frames}
    keys = [{"name": f"dc1_{i:02d}", "start": s, "end": e, "step": st, "source": f"DC1 slot {i} ({n})"}
            if i not in beyond else
            {"name": f"dc1_{i:02d}", "start": 1, "end": 1, "step": 1.0,
             "source": f"DC1 slot {i} ({n}) {s}-{e} lies past the motion's last frame {motion_frames}: placeholder"}
            for i, (n, s, e, st) in enumerate(dc1_keys)]
    for name, target, why in mapping["aliases"]:
        if isinstance(target, int):
            if not 0 <= target < len(dc1_keys):
                raise ConvertError(f"alias {name!r} maps to missing DC1 slot {target}")
            if target in beyond:
                raise ConvertError(f"alias {name!r} maps to DC1 slot {target}, which lies past the motion")
            _n, s, e, st = dc1_keys[target]
            src = f"slot {target}"
        else:
            s, e, st = target
            src = "authored range"
        keys.append({"name": name, "start": int(s), "end": int(e), "step": float(st), "source": src, "why": why})
    names = [k["name"] for k in keys]
    if len(set(names)) != len(names):
        raise ConvertError("duplicate KEY names in the Toan table")
    return keys


def convert_player_body(dc1_pack_path: Path, out_root: Path, weapon_pac_path: Path | None = None,
                        weapon_member: str = "c01w01.chr", max_pack_path: Path | None = None,
                        max_stb_path: Path | None = None, prefix: str = "ix_", scale: float = DC1_TO_DC2_SCALE,
                        mapping: dict | Path | str | None = None, pack_dir: str = "mainchr") -> dict:
    """Convert a skinned DC1 body (and optionally its weapon) into DC2 player-slot packs.

    ``mapping`` is a BodyProfile (path or dict, see ``load_body_profile``); the default is Toan's
    ``tools/profiles/toan-c01d.json``. A profile ``scale`` replaces the ``scale`` argument.
    .mot and .wgt bytes are copied unchanged (DC1 and DC2 share the record layouts and the frame order is
    kept); .bbp is copied unchanged unless the profile synthesises frames, which appends one row each. MDS
    names, MDT headers and material names are rewritten as for monsters; the cfg is authored. DC1's
    ``VERTEX_ANIME 1`` is not carried (an int there makes DC2's _VERTEX_ANIME strcpy a NULL string,
    character.cpp:2451; wave3-dc2-player-draw section 4.2): VERTEX_ANIME names the ALLOC_DBUFF skin frames,
    as TOAN-BODY-R1 did. Cloth (.clo), ALLOC_*, FOOT, EVENT and TEX_ANIME (eye blink) have no DC2 equivalent
    and are dropped.
    """
    profile_path = Path(mapping) if isinstance(mapping, (str, Path)) else None
    mapping = load_body_profile(mapping) if mapping is not None else TOAN_C01D
    if "scale" in mapping:
        scale = float(mapping["scale"])
    if not math.isfinite(scale) or scale <= 0:
        raise ConvertError("scale must be finite and positive")
    if not re.fullmatch(r"[A-Za-z0-9_]+", prefix):
        raise ConvertError("prefix must be [A-Za-z0-9_]+")
    src_bytes = dc1_pack_path.read_bytes()
    members = parse_pack(src_bytes)
    dc1_cfg_m = find_cfg_member(members, dc1_pack_path.stem) if "base.cfg" not in members else members["base.cfg"]
    dc1_cfg = parse_chr_cfg(dc1_cfg_m.data.decode("cp932"), dc1_comment_names=True)
    if not dc1_cfg.model or len(dc1_cfg.motions) != 1 or not dc1_cfg.shadow_model:
        raise ConvertError("DC1 body cfg must name MODEL, SHADOW_MODEL and one MOTION")
    _mid, mot, bbp, wgt = dc1_cfg.motions[0]
    if not (bbp and wgt):
        raise ConvertError("DC1 MOTION names no .bbp/.wgt: not a skinned body")
    if dc1_cfg.model.split(".", 1)[0] + ".wgt" != wgt:
        raise ConvertError(f"weight {wgt!r} is not <model>.wgt; DC2 _MODEL loads the weight by model basename")
    smot, sbbp, swgt = dc1_cfg.shadow_motions[0] if dc1_cfg.shadow_motions else ("", "", "")
    dc1_keys = dc1_cfg.keys.get(0, [])
    deform = [str(a) for c, args in dc1_cfg.other if c == "ALLOC_DBUFF" for a in args]
    if not deform:
        raise ConvertError("DC1 cfg has no ALLOC_DBUFF skin frame")
    # Xiao R1: a profile may keep a subset of ALLOC_DBUFF as the DC2 skin frames (c04b also lists "o", a meshed
    # frame with no weight block, which validate_wgt and DC2's VERTEX_ANIME would refuse).
    deform_dropped: list = []
    if mapping.get("deform_frames") is not None:
        unknown = [n for n in mapping["deform_frames"] if n not in deform]
        if unknown:
            raise ConvertError(f"deform_frames {unknown} are not ALLOC_DBUFF frames {deform}")
        deform_dropped = [n for n in deform if n not in mapping["deform_frames"]]
        deform = list(mapping["deform_frames"])
    dropped = sorted({c for c, _ in dc1_cfg.other} - {"ALLOC_DBUFF", "MATERIAL_ANIME", "VERTEX_ANIME", "IMG_END"})

    def ns(name: str) -> str:
        new = f"{prefix}{name}"
        if len(new) > PACK_NAME_MAX:
            raise ConvertError(f"namespaced member {new!r} too long")
        return new

    out_model = ns(dc1_pack_path.stem)
    if len(out_model) > MODEL_NAME_MAX:
        raise ConvertError(f"namespaced model {out_model!r} exceeds 15 characters")
    renames = {k: v[0] for k, v in mapping["frame_renames"].items()}
    model_src = read_mds(members[dc1_cfg.model.casefold()].data, dc1_cfg.model)
    skin_bones = set()
    for o in model_src:
        if o.name in renames and o.mesh:
            raise ConvertError(f"rename of meshed frame {o.name!r} refused")
    wstats = validate_wgt(members[wgt.casefold()].data, model_src, members[dc1_cfg.model.casefold()].data, deform, wgt)
    for f in wstats["frames"].values():
        skin_bones.update(f["bones"])
    if skin_bones & set(renames):
        raise ConvertError(f"rename of skin bones refused: {sorted(skin_bones & set(renames))}")
    names_src = [o.name for o in model_src]
    for old in renames:
        if names_src.count(old) != 1:
            raise ConvertError(f"rename source {old!r} occurs {names_src.count(old)} times in {dc1_cfg.model} "
                               "(a profile lists only frames the body has; synthesise missing ones)")
    texture_map = _namespace_textures(members, dc1_cfg.imgs, ns)
    rename_frame = lambda n: renames.get(n, n)  # noqa: E731
    stats: dict = {}
    model_out, stats["model"] = rewrite_mds(members[dc1_cfg.model.casefold()].data, rename_frame, texture_map, dc1_cfg.model)
    shadow_out, stats["shadow"] = rewrite_mds(members[dc1_cfg.shadow_model.casefold()].data, rename_frame, texture_map,
                                              dc1_cfg.shadow_model)
    # Synthesised null frames go on the model only: the shadow pairs frames by name (_SHADOW_MODEL,
    # character.cpp:2136-2150), so a model frame with no shadow twin is simply not linked.
    names_now = [rename_frame(o.name) for o in model_src]
    chain_from = [names_now.index(n) for n in deform] + [names_now.index(r["parent"]) for r in mapping["synth_frames"]
                                                         if names_now.count(r["parent"]) == 1]
    bbp_src, bbp_identity = identity_zero_bind_ancestors(model_src, members[bbp.casefold()].data, chain_from)
    model_out, bbp_out, synth_info = append_null_frames(model_out, bbp_src, mapping["synth_frames"], dc1_cfg.model)
    dc1_vertex_anime = [a for c, args in dc1_cfg.other if c == "VERTEX_ANIME" for a in args]
    img = dc1_cfg.imgs[0][1]
    if len(dc1_cfg.imgs) != 1:
        raise ConvertError("expected one IMG in the DC1 body cfg")
    img_out = rename_img(members[img.casefold()].data, texture_map)

    def tri_count(mds: bytes) -> int:
        return sum(validate_mdt(mds, o.mesh, "poly").triangles for o in read_mds(mds, "poly") if o.mesh)
    poly = (tri_count(model_out), tri_count(shadow_out))
    motion_frames = walk_mot(members[mot.casefold()].data, len(model_src), mot)["max_frame"]
    keys = toan_keys(mapping, dc1_keys, motion_frames)
    out_mds, out_smds = ns(dc1_cfg.model), ns(dc1_cfg.shadow_model)
    out_names = {"mot": ns(mot), "bbp": out_mds.split(".", 1)[0] + ".bbp", "wgt": out_mds.split(".", 1)[0] + ".wgt",
                 "sbbp": out_smds.split(".", 1)[0] + ".bbp", "swgt": out_smds.split(".", 1)[0] + ".wgt"}
    if not (sbbp and swgt):
        raise ConvertError("DC1 SHADOW_MOTION names no .bbp/.wgt")
    cfg_text = author_toan_cfg(out_model, ns(img), out_mds, out_smds, out_names["mot"], out_names["bbp"],
                               out_names["wgt"], out_names["sbbp"], out_names["swgt"], deform, poly, scale, mapping, keys)
    body_entries = [(out_mds, model_out), (out_smds, shadow_out), (out_names["mot"], members[mot.casefold()].data),
                    (out_names["bbp"], bbp_out), (out_names["wgt"], members[wgt.casefold()].data),
                    (out_names["sbbp"], members[sbbp.casefold()].data), (out_names["swgt"], members[swgt.casefold()].data),
                    (ns(img), img_out), (f"{out_model}.cfg", cfg_text.encode("cp932"))]
    body_pack = build_pack(body_entries)
    png_files: dict = {}
    sources = [_catalog_source(f"{pack_dir}/{out_model}.chr/{ns(img)}", decode_chr_img(img_out), tim2_gstex1(img_out), png_files)]
    packs = {out_model: body_pack}
    weapon_info = None
    if weapon_pac_path is not None:
        outer = parse_pack(weapon_pac_path.read_bytes())
        wbytes = outer[weapon_member.casefold()].data
        wmembers = parse_pack(wbytes)
        wstem = weapon_member.rsplit(".", 1)[0]
        wcfg = parse_chr_cfg(find_cfg_member(wmembers, wstem).data.decode("cp932"), dc1_comment_names=True)
        w_model = ns(wstem)
        if len(w_model) > MODEL_NAME_MAX:
            raise ConvertError(f"namespaced weapon model {w_model!r} too long")
        wtex = _namespace_textures(wmembers, wcfg.imgs, ns)
        wmds, stats["weapon"] = rewrite_mds(wmembers[wcfg.model.casefold()].data, lambda n: n, wtex, wcfg.model)
        wframes = [o.name for o in read_mds(wmds, "weapon")]
        # Xiao R1: null means a weapon with no melee hit frame (her slingshots have no dcol; the shot is CSHOT's).
        if mapping["weapon_hit_frame"] is not None and mapping["weapon_hit_frame"] not in wframes:
            raise ConvertError(f"weapon lacks the DC1 hit frame {mapping['weapon_hit_frame']!r}")
        missing_points = [n for n in mapping.get("weapon_points", []) if wframes.count(n) != 1]
        if missing_points:
            raise ConvertError(f"weapon lacks the named points {missing_points} the handler reads")
        wimg = wcfg.imgs[0][1]
        wimg_out = rename_img(wmembers[wimg.casefold()].data, wtex)
        wcfg_text = author_part_cfg(w_model, ns(wimg), ns(wcfg.model))
        packs[w_model] = build_pack([(ns(wcfg.model), wmds), (ns(wimg), wimg_out), (f"{w_model}.cfg", wcfg_text.encode("cp932"))])
        sources.append(_catalog_source(f"{pack_dir}/{w_model}.chr/{ns(wimg)}", decode_chr_img(wimg_out), tim2_gstex1(wimg_out), png_files))
        texture_map.update(wtex)
        weapon_info = {"model": w_model, "source_member": weapon_member, "source_sha256": sha256(wbytes),
                       "frames": wframes, "hit_frame": mapping["weapon_hit_frame"],
                       "dropped": ["shadow model " + (wcfg.shadow_model or ""), "SHADOW_VERTEX_ANIME", "empty MOTION/KEY"]}
        if "weapon_points" in mapping:
            weapon_info["points"] = list(mapping["weapon_points"])
        if wcfg.motions and any(m[1] for m in wcfg.motions):
            # c04w01 (Xiao's sling) is skinned and keyed like the body (its band stretches with the draw); the part
            # is carried rigid in its bind pose, so that motion is not.
            weapon_info["dropped"].append("MOTION " + ", ".join(m[1] for m in wcfg.motions if m[1])
                                          + " (part drawn rigid, bind pose)")
    contract = None
    if max_pack_path is not None:
        contract = player_contract(max_pack_path.read_bytes(), max_stb_path.read_bytes() if max_stb_path else None,
                                   mapping["seam_sockets"])
    catalog = {"schema_version": 1, "sources": sources}
    out_root = out_root.resolve()
    out_root.parent.mkdir(parents=True, exist_ok=True)
    if out_root.exists():
        raise ConvertError(f"output {out_root} already exists; choose a new path")
    with tempfile.TemporaryDirectory(prefix=out_root.name + ".tmp-", dir=out_root.parent) as staging_name:
        staging = Path(staging_name)
        for model_name, data in packs.items():
            p = staging / "data" / Path(pack_dir) / f"{model_name}.chr"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        cat_root = staging / "port_data"
        for rel, png in png_files.items():
            p = cat_root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(png)
        (cat_root / "catalog.json").write_text(json.dumps(catalog, indent=1), encoding="utf-8")
        cat_index = {s["source"].lower(): s for s in sources}
        reports = {out_model: validate_chr(body_pack, out_model, None, cat_index, cat_root, pack_dir=pack_dir,
                                           player=contract)}
        if weapon_info:
            reports[weapon_info["model"]] = validate_chr(packs[weapon_info["model"]], weapon_info["model"], None,
                                                         cat_index, cat_root, pack_dir=pack_dir, require_motion=False)
        provenance = {
            "format": "ixion-player-body-pack", "version": 1, "output_model": out_model,
            "outputs": {m: {"path": f"data/{pack_dir}/{m}.chr", "sha256": sha256(d), "bytes": len(d)} for m, d in packs.items()},
            "sources": {"dc1_pack": {"path": dc1_pack_path.name, "sha256": sha256(src_bytes)},
                        "weapon_pac": {"path": weapon_pac_path.name, "sha256": sha256(weapon_pac_path.read_bytes())} if weapon_pac_path else None,
                        "max_pack": {"path": max_pack_path.name, "sha256": sha256(max_pack_path.read_bytes())} if max_pack_path else None,
                        "max_stb": {"path": max_stb_path.name, "sha256": sha256(max_stb_path.read_bytes())} if max_stb_path else None},
            "options": {"prefix": prefix, "scale": scale, "pack_dir": pack_dir, "texture_suffix_reserved": TEXTURE_SUFFIX},
            "copied_unchanged": [mot, wgt, sbbp, swgt] if synth_info or bbp_identity else [mot, bbp, wgt, sbbp, swgt],
            "dropped": {"dc1_cfg_commands": dropped, "shadow_mot": smot,
                        "cloth": [m.name for m in members.values() if m.name.lower().endswith(".clo")]},
            "frame_renames": mapping["frame_renames"], "groups": mapping["groups"], "deform_frames": deform,
            "keys": keys, "dc1_slots": [list(k) for k in dc1_keys], "dc1_cfg_skipped_statements": dc1_cfg.skipped,
            "rewrite_stats": stats, "texture_map": texture_map, "catalog_fragment": "port_data/catalog.json",
            "weapon": weapon_info, "validation": reports,
            "profile": {"name": mapping.get("name"),
                        "path": profile_path.name if profile_path else "toan-c01d.json (default)",
                        "sha256": sha256(profile_path.read_bytes()) if profile_path else
                        sha256((PROFILES_DIR / "toan-c01d.json").read_bytes())},
            "synth_frames": synth_info,
            "vertex_anime": {"dc1": dc1_vertex_anime, "dc2": deform,
                             "why": "DC1 VERTEX_ANIME takes an int; DC2 _VERTEX_ANIME strcpys a string "
                                    "(character.cpp:2443-2455), so the DC2 cfg names the ALLOC_DBUFF skin frames"},
        }
        # Xiao R1 keys appear only when used, so earlier packs' provenance stays byte-identical.
        if deform_dropped:
            provenance["vertex_anime"]["alloc_dbuff_dropped"] = deform_dropped
        if bbp_identity:
            provenance["bbp_zero_rows_identity"] = {
                "frames": bbp_identity,
                "why": "all-zero .bbp rows above the skin owner / synth parents; DC1 starts the chain at the skin "
                       "owner's parent with identity, DC2 chains root-down (AccumulateDc1BindPose)"}
        (staging / "provenance.json").write_text(json.dumps(provenance, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(staging, out_root)
    return provenance


# ---------------------------------------------------------------- DC1 villager -> DC2 townsperson (GEORAMA-R3)

# A DC2 townsperson is loaded by CScene::LoadVillager (scenevillager.cpp:681): LoadFile2("chara/<model>.chr") then
# LoadChara(slot, buffer, "info.cfg", ...), so the cfg member is named info.cfg and the pack lives under chara/.
# Texture names get the slot number appended (name_suffix = "%d" slot, scenevillager.cpp:740), at most three digits.
VILLAGER_TEXTURE_NAME_MAX = 0x20 - 1 - 3
# Motions CScene drives a townsperson with, by name (scenevillager.cpp:43-54): 立ち 歩き 走り 会話 座り, then the
# camera trio and 特別. A DC1 villager has stand / walk / walk / talk (info.cfg KEY 0-3 of p01a), so 走り reuses the
# walk range and the rest are absent (SetCharaMotion falls back to 立ち for a missing 座り, scenevillager.cpp:970).
VILLAGER_MOTIONS = {"motions": [
    {"name": "立ち", "slot": 0, "why": "KEY 0 立ち (stand)"},
    {"name": "歩き", "slot": 1, "why": "KEY 1 歩き (walk)"},
    {"name": "走り", "slot": 2, "why": "KEY 2 is a second 歩き; DC1 villagers never run"},
    {"name": "会話", "slot": 3, "why": "KEY 3 会話 (talk)"},
]}


def convert_villager(dc1_pack_path: Path, out_root: Path, prefix: str = "ix_", scale: float = 1.0,
                     display_name: str | None = None) -> dict:
    """Convert one skinned DC1 villager (gedit/<town>/chara/pNNa.chr) into a DC2 townsperson pack.

    Layout follows convert() for skinned donors (model .bbp rewritten model-space by model_space_bbp, .mot and .wgt
    copied byte for byte, VERTEX_ANIME names the ALLOC_DBUFF frame) but writes data/chara/<model>.chr with an
    ``info.cfg`` member. The skinned shadow (p01s.mds with its own .bbp/.wgt) is dropped: the shadow-skin path is
    not supported by convert(), and a townsperson draws without it. ``scale`` defaults to 1.0 because the Georama
    houses are converted at 1:1 (GEORAMA-R2), so a DC1 villager (BODY_SIZE height 60, like Max) stands at house scale.
    """
    if not math.isfinite(scale) or scale <= 0:
        raise ConvertError("scale must be finite and positive")
    if not re.fullmatch(r"[A-Za-z0-9_]+", prefix):
        raise ConvertError("prefix must be [A-Za-z0-9_]+")
    src_bytes = dc1_pack_path.read_bytes()
    src_model = dc1_pack_path.stem
    out_model = f"{prefix}{src_model}"
    if len(out_model) > MODEL_NAME_MAX:
        raise ConvertError(f"namespaced model {out_model!r} exceeds {MODEL_NAME_MAX} characters")
    members = parse_pack(src_bytes)
    dc1_cfg = parse_chr_cfg(find_cfg_member(members, src_model).data.decode("cp932"), dc1_comment_names=True)
    if not dc1_cfg.model or len(dc1_cfg.motions) != 1:
        raise ConvertError("DC1 cfg must name one MODEL and one MOTION")
    _mid, dc1_mot, dc1_base, dc1_wgt = dc1_cfg.motions[0]
    if not (dc1_base and dc1_wgt):
        raise ConvertError("DC1 villager is expected to be skinned (MOTION names .bbp and .wgt)")
    if dc1_cfg.model.split(".", 1)[0] + ".wgt" != dc1_wgt:
        raise ConvertError(f"weight {dc1_wgt!r} is not <model>.wgt; DC2 _MODEL loads the weight by model basename")
    deform = [str(a) for c, args in dc1_cfg.other if c == "ALLOC_DBUFF" for a in args]
    if not deform:
        raise ConvertError("skinned donor has no ALLOC_DBUFF skin frame")
    dc1_keys = dc1_cfg.keys.get(0, [])
    if len(dc1_keys) < 4:
        raise ConvertError("DC1 villager needs KEY 0-3 (stand, walk, walk, talk)")

    def ns(name: str) -> str:
        new = f"{prefix}{name}"
        if len(new) > PACK_NAME_MAX:
            raise ConvertError(f"namespaced member {new!r} too long")
        return new

    texture_map = _namespace_textures(members, dc1_cfg.imgs, ns)
    for new in texture_map.values():
        if len(new) > VILLAGER_TEXTURE_NAME_MAX:
            raise ConvertError(f"namespaced texture {new!r} exceeds {VILLAGER_TEXTURE_NAME_MAX} characters")
    model_src = members[dc1_cfg.model.casefold()].data
    model_out, stats = rewrite_mds(model_src, lambda n: n, texture_map, dc1_cfg.model)
    src_objs = read_mds(model_src, dc1_cfg.model)
    wstats = validate_wgt(members[dc1_wgt.casefold()].data, src_objs, model_src, deform, dc1_wgt)
    skin_indices = [next(o.index for o in src_objs if o.name == name) for name in deform]
    bbp_out, bbp_stats = model_space_bbp(src_objs, members[dc1_base.casefold()].data, skin_indices, dc1_base)
    if len(dc1_cfg.imgs) != 1:
        raise ConvertError("expected one IMG in the DC1 villager cfg")
    img = dc1_cfg.imgs[0][1]
    img_out = rename_img(members[img.casefold()].data, texture_map)
    triangles = sum(validate_mdt(model_out, o.mesh, "poly").triangles for o in read_mds(model_out, "poly") if o.mesh)
    basename = ns(dc1_cfg.model).split(".", 1)[0]
    out_mds, out_mot, out_bbp, out_wgt = ns(dc1_cfg.model), ns(dc1_mot), f"{basename}.bbp", f"{basename}.wgt"
    frame_names = [o.name for o in read_mds(model_out, "model")]
    groups = [[0, [[frame_names[0], 1.0]]], [1, [[frame_names[0], None]]]]
    motions = resolve_motion_table(VILLAGER_MOTIONS, dc1_keys)
    body = tuple(v * scale for v in (dc1_cfg.body_size or (0.0, 0.0, 0.0)))
    cfg_text = author_cfg(display_name or out_model, [ns(img)], out_mds, None, out_mot, None, body, scale,
                          (triangles, 0), groups, motions, dc1_keys, None, None, deform, out_bbp, out_wgt)
    entries = [(out_mds, model_out), (out_mot, members[dc1_mot.casefold()].data), (out_bbp, bbp_out),
               (out_wgt, members[dc1_wgt.casefold()].data), (ns(img), img_out), ("info.cfg", cfg_text.encode("cp932"))]
    pack = build_pack(entries)
    png_files: dict = {}
    source = _catalog_source(f"chara/{out_model}.chr/{ns(img)}", decode_chr_img(img_out), tim2_gstex1(img_out), png_files)
    catalog = {"schema_version": 1, "sources": [source]}
    out_root = out_root.resolve()
    out_root.parent.mkdir(parents=True, exist_ok=True)
    if out_root.exists():
        raise ConvertError(f"output {out_root} already exists; choose a new path")
    with tempfile.TemporaryDirectory(prefix=out_root.name + ".tmp-", dir=out_root.parent) as staging_name:
        staging = Path(staging_name)
        chr_path = staging / "data" / "chara" / f"{out_model}.chr"
        chr_path.parent.mkdir(parents=True)
        chr_path.write_bytes(pack)
        cat_root = staging / "port_data"
        for rel, png in png_files.items():
            p = cat_root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(png)
        (cat_root / "catalog.json").write_text(json.dumps(catalog, indent=1), encoding="utf-8")
        report = validate_chr(pack, out_model, None, {source["source"].lower(): source}, cat_root,
                              pack_dir="chara", cfg_name="info.cfg")
        provenance = {
            "format": "ixion-villager-pack", "version": 1, "output_model": out_model,
            "output_chr": f"data/chara/{out_model}.chr", "output_chr_sha256": sha256(pack),
            "sources": {"dc1_pack": {"path": dc1_pack_path.name, "sha256": sha256(src_bytes)}},
            "options": {"prefix": prefix, "scale": scale,
                        "scale_why": "Georama houses are converted 1:1; the DC1 villager (BODY_SIZE height 60) is the same height as Max"},
            "motion_table": motions, "dc1_slots": [list(k) for k in dc1_keys], "groups": groups,
            "skin": {"wgt": wstats, "bbp": bbp_stats, "vertex_anime": {"dc1": [a for c, args in dc1_cfg.other
                                                                                if c == "VERTEX_ANIME" for a in args],
                                                                        "dc2": deform}},
            "copied_unchanged": [dc1_mot, dc1_wgt],
            "dropped": {"shadow": [dc1_cfg.shadow_model] + [x for sm in dc1_cfg.shadow_motions for x in sm if x],
                        "dc1_cfg_commands": sorted({c for c, _ in dc1_cfg.other} - {"ALLOC_DBUFF", "MATERIAL_ANIME", "IMG_END"}),
                        "cloth": [m.name for m in members.values() if m.name.lower().endswith(".clo")]},
            "dc1_cfg_skipped_statements": dc1_cfg.skipped, "rewrite_stats": stats, "texture_map": texture_map,
            "catalog_fragment": "port_data/catalog.json", "validation": report,
        }
        (staging / "provenance.json").write_text(json.dumps(provenance, indent=1, ensure_ascii=False), encoding="utf-8")
        replace_with_retry(staging, out_root)
    return provenance


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert")
    c.add_argument("--dc1-pack", type=Path, required=True)
    c.add_argument("--brain-pack", type=Path, help="native DC2 brain pack; omit for a brainless pack")
    c.add_argument("--brain-stb", type=Path)
    c.add_argument("--output", type=Path, required=True)
    c.add_argument("--prefix", default="ix_")
    c.add_argument("--scale", type=float, default=DC1_TO_DC2_SCALE)
    c.add_argument("--mapping", type=Path, help="JSON {motions:[...], groups:[...]} overriding the built-in table")
    c.add_argument("--profile", type=Path, help="brainless JSON {frame_style, aliases:[{name, slot}]} (tools/profiles/)")
    p = sub.add_parser("convert-player", help="skinned DC1 player body -> DC2 player-slot packs (BodyProfile)")
    p.add_argument("--dc1-pack", type=Path, required=True, help="dun/mainchara/c01d.chr (Toan), c06b.chr (Goro), ...")
    p.add_argument("--profile", type=Path, help="BodyProfile JSON (tools/profiles/); default toan-c01d.json")
    p.add_argument("--weapon-pac", type=Path, help="dun/mainchara/c01w.pac")
    p.add_argument("--weapon-member", help="weapon .chr inside the pac (default: the profile's source.weapon_member, "
                                           "else c01w01.chr = Dagger)")
    p.add_argument("--max-pack", type=Path, help="DC2 mainchr/c01_base2.chr: motion/frame contract")
    p.add_argument("--max-stb", type=Path, help="DC2 mainchr/c01.stb")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--prefix", default="ix_")
    p.add_argument("--scale", type=float, default=DC1_TO_DC2_SCALE)
    vl = sub.add_parser("convert-villager", help="skinned DC1 villager (gedit/<town>/chara/pNNa.chr) -> DC2 townsperson pack")
    vl.add_argument("--dc1-pack", type=Path, required=True)
    vl.add_argument("--output", type=Path, required=True)
    vl.add_argument("--prefix", default="ix_")
    vl.add_argument("--scale", type=float, default=1.0)
    vl.add_argument("--name")
    v = sub.add_parser("validate")
    v.add_argument("pack", type=Path)
    v.add_argument("--model", help="model basename (default: pack stem)")
    v.add_argument("--brain-pack", type=Path)
    v.add_argument("--brain-stb", type=Path)
    v.add_argument("--no-textures", action="store_true", help="skip texture provision checks (stripped packs without catalog)")
    v.add_argument("--catalog", type=Path, help="port_data/catalog.json to resolve stripped IMG members")
    v.add_argument("--cfg-name", help="cfg member (default <model>.cfg; DC2 player packs use info.cfg)")
    v.add_argument("--pack-dir", default="dungeon/monster", help="catalog source directory (mainchr for player packs)")
    v.add_argument("--part", action="store_true", help="attached part (weapon): no MOTION required")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "convert":
            mapping = json.loads(args.mapping.read_text(encoding="utf-8")) if args.mapping else None
            profile = json.loads(args.profile.read_text(encoding="utf-8")) if args.profile else None
            result = convert(args.dc1_pack, args.brain_pack, args.brain_stb, args.output, args.prefix, args.scale, mapping,
                             profile=profile)
            result = {k: result[k] for k in ("output_model", "output_chr_sha256", "validation")}
        elif args.cmd == "convert-player":
            profile = load_body_profile(args.profile) if args.profile else TOAN_C01D
            member = args.weapon_member or profile.get("source", {}).get("weapon_member", "c01w01.chr")
            result = convert_player_body(args.dc1_pack, args.output, args.weapon_pac, member,
                                         args.max_pack, args.max_stb, args.prefix, args.scale, args.profile)
            result = {k: result[k] for k in ("output_model", "outputs", "validation")}
        elif args.cmd == "convert-villager":
            result = convert_villager(args.dc1_pack, args.output, args.prefix, args.scale, args.name)
            result = {k: result[k] for k in ("output_model", "output_chr_sha256", "validation")}
        else:
            contract = None
            if args.brain_pack:
                contract, _ = brain_contract(args.brain_pack.read_bytes(), args.brain_pack.stem,
                                             args.brain_stb.read_bytes() if args.brain_stb else None)
            catalog = root = None
            if args.catalog:
                doc = json.loads(args.catalog.read_text(encoding="utf-8"))
                catalog = {s["source"].lower(): s for s in doc["sources"]}
                root = args.catalog.parent
            result = validate_chr(args.pack.read_bytes(), args.model or args.pack.stem, contract, catalog, root,
                                  require_textures=not args.no_textures, pack_dir=args.pack_dir,
                                  cfg_name=args.cfg_name, require_motion=not args.part)
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(result, indent=1, ensure_ascii=False))
        return 0
    except (OSError, ConvertError, struct.error, UnicodeError, KeyError, ValueError) as exc:
        ap.exit(2, f"monster-converter: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
