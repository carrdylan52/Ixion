#!/usr/bin/env python3
"""Bounded offline converter for fixed DC1 dungeon rooms."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MAX_PACK = 64 * 1024 * 1024
MAX_ROOM_JSON = 64 * 1024 * 1024
MAX_MEMBERS = 4096
MAX_OBJECTS = 4096
MAX_VERTICES = 2_000_000
MAX_TRIANGLES = 2_000_000
MAX_PACK_TEXTURES = 128
MAX_PACK_VISUALS = 100_000
MAX_PACK_COLLISION = 1_000_000


class ConvertError(ValueError):
    pass


def checked_span(data: bytes, offset: int, size: int, label: str) -> memoryview:
    if offset < 0 or size < 0 or offset > len(data) or size > len(data) - offset:
        raise ConvertError(f"truncated or out-of-range {label}")
    return memoryview(data)[offset:offset + size]


def checked_resource_span(data: bytes, base: int, extent: int, offset: int, size: int, label: str) -> memoryview:
    """Check an offset/size pair relative to one declared MDT, never its parent MDS."""
    if offset < 64 or size < 0 or offset > extent or size > extent - offset:
        raise ConvertError(f"{label} escapes declared MDT resource")
    return checked_span(data, base + offset, size, label)


def native_mds_matrix_to_standard(raw: tuple[float, ...], name: str) -> tuple[float, ...]:
    """Transpose libvu0's four stored column vectors at the raw MDS boundary."""
    matrix=tuple(raw[c*4+r] for r in range(4) for c in range(4))
    if any(abs(v)>1e-5 for v in matrix[12:15]) or abs(matrix[15]-1.0)>1e-5:
        raise ConvertError(f"unsupported non-affine MDS transform in {name}")
    a,b,c=matrix[0:3],matrix[4:7],matrix[8:11]
    det=(a[0]*(b[1]*c[2]-b[2]*c[1])-
         a[1]*(b[0]*c[2]-b[2]*c[0])+
         a[2]*(b[0]*c[1]-b[1]*c[0]))
    if not math.isfinite(det) or abs(det)<1e-10:
        raise ConvertError(f"singular MDS transform in {name}")
    return matrix


@dataclass(frozen=True)
class Member:
    name: str
    data: bytes


def parse_pack(data: bytes) -> dict[str, Member]:
    if len(data) > MAX_PACK:
        raise ConvertError("pack exceeds 64 MiB limit")
    result: dict[str, Member] = {}
    physical_members = 0
    pos = 0
    while True:
        header = checked_span(data, pos, 80, "pack entry header")
        raw_name = bytes(header[:64]).split(b"\0", 1)[0]
        if not raw_name:
            break
        try:
            name = raw_name.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ConvertError("non-ASCII pack member name") from exc
        key = name.casefold()
        if key in result or "/" in name or "\\" in name or name in {".", ".."}:
            raise ConvertError(f"duplicate or unsafe member name: {name!r}")
        offset, size, step = struct.unpack_from("<iii", header, 64)
        if step < 80 or step % 16 or pos + step <= pos:
            raise ConvertError(f"invalid next-entry stride for {name!r}")
        if offset < 80 or size < 0 or offset > step or size > step - offset:
            raise ConvertError(f"invalid member range for {name!r}")
        payload = bytes(checked_span(data, pos + offset, size, f"member {name}"))
        result[key] = Member(name, payload)
        physical_members += 1
        if physical_members > MAX_MEMBERS:
            raise ConvertError("pack exceeds member-count limit")
        pos += step
        if pos == len(data):
            raise ConvertError("pack has no terminating empty entry")
        if pos > len(data):
            raise ConvertError("next-entry stride leaves pack")
    if not result:
        raise ConvertError("empty pack")
    return result


def parse_mds(data: bytes) -> list[dict]:
    if len(data) < 16 or data[:4] != b"MDS\0":
        raise ConvertError("unsupported MDS signature")
    version, count, records = struct.unpack_from("<III", data, 4)
    if version != 1 or records != 16 or not 0 < count <= MAX_OBJECTS:
        raise ConvertError("unsupported MDS header")
    checked_span(data, records, count * 112, "MDS object table")
    objects = []
    for i in range(count):
        at = records + i * 112
        name_b = data[at + 8:at + 40].split(b"\0", 1)[0]
        try:
            name = name_b.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ConvertError("non-ASCII MDS object name") from exc
        mesh, parent = struct.unpack_from("<ii", data, at + 40)
        raw_matrix = struct.unpack_from("<16f", data, at + 48)
        if not all(math.isfinite(v) for v in raw_matrix):
            raise ConvertError(f"non-finite MDS transform in {name}")
        matrix = native_mds_matrix_to_standard(raw_matrix, name)
        if parent < -1 or parent >= count or parent == i:
            raise ConvertError(f"invalid parent index in {name}")
        if parent >= 0 and parent > i:
            raise ConvertError(f"forward parent index is unsupported in {name}")
        if mesh:
            if mesh < records + count * 112 or mesh > len(data) - 64:
                raise ConvertError(f"invalid MDT offset in {name}")
            if data[mesh:mesh + 4] != b"MDT\0":
                raise ConvertError(f"unsupported MDT signature in {name}")
            declared = struct.unpack_from("<I", data, mesh + 8)[0]
            checked_span(data, mesh, declared, f"MDT {name}")
            if declared < 64:
                raise ConvertError(f"invalid MDT size in {name}")
        objects.append({"name": name, "mesh": mesh, "parent": parent, "matrix": matrix})
    for i in range(count):
        seen = set()
        cur = i
        while cur >= 0:
            if cur in seen:
                raise ConvertError("cyclic MDS parent graph")
            seen.add(cur)
            cur = objects[cur]["parent"]
    return objects


@dataclass(frozen=True)
class PartFrame:
    """One PT_BASE record: itemdata.cpp stores x/y/z*10 as frame_offset, field 6 as frame_turn,
    and field 2 only as direction_offset (a minimap tile index, dungeonmap.cpp:666-668)."""
    name: str
    direction_offset: int
    offset: tuple[float, float, float]
    turn: int
    line: int


@dataclass(frozen=True)
class PartMarker:
    name: str
    radius: float
    script: int
    line: int


@dataclass(frozen=True)
class RoomPart:
    index: int
    frames: tuple[PartFrame, ...]
    collision: tuple[str, int] | None
    markers: tuple[PartMarker, ...]
    line: int


@dataclass(frozen=True)
class RoomCfg:
    set_path: str
    ground_images: tuple[str, ...]
    parts: tuple[RoomPart, ...]


_CFG_NUM = r"(-?(?:\d+(?:\.\d*)?|\.\d+))"


def parse_room_cfg(cfg: bytes) -> RoomCfg:
    """Parse the fixed-floor subset of a DC1 dungeon cfg as itemdata.cpp reads it.

    DEF_PATS opens a part and DEF_ENDS closes it (nowPartsCnt); each part holds up to six
    PT_BASE frames, at most one PT_COLS collision, and PT_MARKER records that are looked up in
    that collision model (itemdata.cpp:1254). Source cfgs are Shift-JIS.
    """
    text = cfg.decode("cp932", errors="replace")
    set_path = None; images = []; parts = []
    base = re.compile(r'^\s*PT_BASE\s+"([^"\\]+)"\s*,\s*' + r'\s*,\s*'.join([_CFG_NUM]*5) + r'\s*$', re.I)
    cols = re.compile(r'^\s*PT_COLS\s+"([^"\\]+)"\s*,\s*' + _CFG_NUM + r'\s*$', re.I)
    marker = re.compile(r'^\s*PT_MARKER\s+"([^"\\]+)"\s*,\s*' + _CFG_NUM + r'\s*,\s*' + _CFG_NUM + r'\s*(?:,.*)?$', re.I)
    grd = re.compile(r'^\s*GRD_IMG\s+"([^"\\]+)"\s*(?:,.*)?$', re.I)
    path = re.compile(r'^\s*SET_PATH\s+"(dun/[^"]+/)"\s*$', re.I)
    current = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("//", 1)[0]
        if not line.strip():
            continue
        keyword = line.split()[0].upper()
        if keyword == "SET_PATH":
            m = path.match(line)
            if not m: raise ConvertError(f"cfg line {number}: malformed SET_PATH")
            set_path = m.group(1)
        elif keyword == "GRD_IMG":
            m = grd.match(line)
            if not m: raise ConvertError(f"cfg line {number}: malformed GRD_IMG")
            images.append(PurePosixPath(m.group(1)).name)
        elif keyword == "DEF_PATS":
            if current is not None: raise ConvertError(f"cfg line {number}: nested DEF_PATS")
            current = {"frames": [], "collision": None, "markers": [], "line": number}
        elif keyword == "DEF_ENDS":
            if current is None: raise ConvertError(f"cfg line {number}: DEF_ENDS without DEF_PATS")
            if not current["frames"]:
                # CDungeonMap iterates parts until frame[0] is NULL, so an empty part ends the room.
                raise ConvertError(f"cfg line {number}: part without PT_BASE is unsupported")
            parts.append(RoomPart(len(parts), tuple(current["frames"]), current["collision"],
                                  tuple(current["markers"]), current["line"]))
            current = None
        elif keyword in ("PT_BASE", "PT_COLS", "PT_MARKER"):
            if current is None: raise ConvertError(f"cfg line {number}: {keyword} outside DEF_PATS")
            if keyword == "PT_BASE":
                m = base.match(line)
                if not m: raise ConvertError(f"cfg line {number}: malformed PT_BASE")
                if len(current["frames"]) >= 6: raise ConvertError(f"cfg line {number}: more than six PT_BASE frames")
                current["frames"].append(PartFrame(PurePosixPath(m.group(1)).name, int(float(m.group(2))),
                                                   tuple(float(m.group(j))*10.0 for j in (3,4,5)),
                                                   int(float(m.group(6))), number))
            elif keyword == "PT_COLS":
                m = cols.match(line)
                if not m: raise ConvertError(f"cfg line {number}: malformed PT_COLS")
                if current["collision"] is not None: raise ConvertError(f"cfg line {number}: second PT_COLS in one part")
                current["collision"] = (PurePosixPath(m.group(1)).name, int(float(m.group(2))))
            else:
                m = marker.match(line)
                if not m: raise ConvertError(f"cfg line {number}: malformed PT_MARKER")
                current["markers"].append(PartMarker(m.group(1), float(m.group(2)), int(float(m.group(3))), number))
    if current is not None: raise ConvertError("cfg ends inside DEF_PATS")
    if set_path is None: raise ConvertError("room config lacks a dungeon SET_PATH")
    if not parts: raise ConvertError("room config defines no parts")
    return RoomCfg(set_path, tuple(images), tuple(parts))


def dc1_turn(k: int) -> int:
    """Quarter-turn count as CDungeonParts::Draw and the fixed-floor collision setup normalise it.

    DC1 subtracts 3, not 4, when the sum passes 3, then maps 3 to -1 (dungeonparts.cpp:2119-2124,
    2255-2262). The angle is -90 degrees times the result. Retail quirk kept on purpose: 4 -> 1.
    """
    if k > 3: k -= 3
    if k == 3: k = -1
    return k


def part_collision_turn(part: RoomPart) -> int:
    """Fixed floors turn collision by frame_turn[0] + PT_COLS turn (dungeonparts.cpp:2115-2117, 2341)."""
    if part.collision is None: raise ConvertError("part has no collision")
    return dc1_turn(part.frames[0].turn + part.collision[1])


def frame_visual_turn(frame: PartFrame) -> int:
    """Fixed floors force cell direction 0 (dungeonmap.cpp:288), so the visual turn is frame_turn."""
    return dc1_turn(0 + frame.turn)


def parse_cfg_placement(cfg: bytes, visual_name: str, collision_name: str) -> tuple[tuple[float,...], int, int]:
    """Placement of the one part whose PT_BASE is visual_name: (offset, visual turn, collision turn)."""
    part = select_part(parse_room_cfg(cfg), visual_name, collision_name)
    frame = next(f for f in part.frames if f.name.casefold() == visual_name.casefold())
    return frame.offset, frame_visual_turn(frame), part_collision_turn(part)


def select_part(room: RoomCfg, visual_name: str, collision_name: str) -> RoomPart:
    matches = [p for p in room.parts if any(f.name.casefold() == visual_name.casefold() for f in p.frames)]
    if len(matches) != 1 or matches[0].collision is None or matches[0].collision[0].casefold() != collision_name.casefold():
        raise ConvertError("room must have one unambiguous PT_BASE and PT_COLS placement")
    return matches[0]


def mat_mul(a: tuple[float,...], b: tuple[float,...]) -> tuple[float,...]:
    # Standard row-major representation of libvu0's parent_world * local composition.
    return tuple(sum(a[r*4+k]*b[k*4+c] for k in range(4)) for r in range(4) for c in range(4))


_IDENTITY = (1.0,0.0,0.0,0.0, 0.0,1.0,0.0,0.0, 0.0,0.0,1.0,0.0, 0.0,0.0,0.0,1.0)

# cos/sin of -90*k degrees for k mod 4, exact so quarter turns carry no rounding noise.
_QUARTER_TURN = {0: (1.0, 0.0), 1: (0.0, -1.0), 2: (-1.0, 0.0), 3: (0.0, 1.0)}


def world_matrices(objects: list[dict], offset: tuple[float,...], y_turn: int = 0) -> list[tuple[float,...]]:
    """Place an MDS as CFrame::GetLWMatrix does after SetRotation(0, -90*k deg, 0) and SetPosition.

    rot_type 1 gives local' = RotMatrixY(angle) * local, then translation += position
    (frame.cpp:489-514); libvu0 RotMatrixY's columns are (c,0,-s), (0,1,0), (s,0,c), which is the
    standard Ry(angle). y_turn is a DC1 quarter-turn count (already normalised by dc1_turn).
    Only frame 0 is the CFrame the cfg loader keeps, so other root frames would stay unplaced.
    """
    c,s=_QUARTER_TURN[y_turn % 4]
    if (y_turn % 4 or any(offset)) and any(obj["parent"] < 0 for obj in objects[1:]):
        raise ConvertError("cannot place an MDS with more than one root frame")
    place=(c,0,s,offset[0], 0,1,0,offset[1], -s,0,c,offset[2], 0,0,0,1)
    out=[]
    for i,obj in enumerate(objects):
        local=obj["matrix"]
        parent=obj["parent"]
        out.append(mat_mul(place,local) if parent < 0 else mat_mul(out[parent],local))
    return out


def transform_point(m: tuple[float,...], p: tuple[float,float,float]) -> tuple[float,float,float]:
    x,y,z=p
    return (m[0]*x+m[1]*y+m[2]*z+m[3], m[4]*x+m[5]*y+m[6]*z+m[7], m[8]*x+m[9]*y+m[10]*z+m[11])


def transform_normal(m: tuple[float,...], n: tuple[float,float,float]) -> tuple[float,float,float]:
    # A normal transforms by inverse-transpose, including nonuniform object scale.
    a,b,c=m[0:3],m[4:7],m[8:11]
    det=(a[0]*(b[1]*c[2]-b[2]*c[1])-
         a[1]*(b[0]*c[2]-b[2]*c[0])+
         a[2]*(b[0]*c[1]-b[1]*c[0]))
    if not math.isfinite(det) or abs(det)<1e-10:
        raise ConvertError("singular world transform cannot transform normal")
    inv=(
        (b[1]*c[2]-b[2]*c[1])/det, (a[2]*c[1]-a[1]*c[2])/det, (a[1]*b[2]-a[2]*b[1])/det,
        (b[2]*c[0]-b[0]*c[2])/det, (a[0]*c[2]-a[2]*c[0])/det, (a[2]*b[0]-a[0]*b[2])/det,
        (b[0]*c[1]-b[1]*c[0])/det, (a[1]*c[0]-a[0]*c[1])/det, (a[0]*b[1]-a[1]*b[0])/det,
    )
    x,y,z=(inv[0]*n[0]+inv[3]*n[1]+inv[6]*n[2], inv[1]*n[0]+inv[4]*n[1]+inv[7]*n[2], inv[2]*n[0]+inv[5]*n[1]+inv[8]*n[2])
    length=math.sqrt(x*x+y*y+z*z)
    return (x/length,y/length,z/length) if length else (0.0,1.0,0.0)


def parse_collision_mds(data: bytes, placed: tuple[float,...], turn: int) -> list[list[list[float]]]:
    return [tri for _,tri,_ in collision_records(data,placed,turn,attributes=False)]


def collision_records(data: bytes, placed: tuple[float,...], turn: int, attributes: bool=True) -> list[tuple[str,list,tuple|None]]:
    """(object name, placed triangle, attribute) per collision triangle. The attribute is the 16-byte
    record MDT_CPOLY.info_index selects in the info table at MDT +56 (CreateCollisionMDT,
    dataset.cpp:806-816), read as CCPoly::attr (ground_kind, foot_sound, area_kind, ignore_mask;
    collision.hpp:52-58), or None where the triangle has none (the native zero-fills it)."""
    objects=parse_mds(data); matrices=world_matrices(objects,placed,turn); records=[]
    for i,obj in enumerate(objects):
        mesh=obj["mesh"]
        if not mesh: continue
        size=struct.unpack_from("<I",data,mesh+8)[0]
        vertex_count,vertex_ofs=struct.unpack_from("<ii",data,mesh+12)
        mesh_ofs=struct.unpack_from("<i",data,mesh+40)[0]
        info_ofs=struct.unpack_from("<i",data,mesh+56)[0]
        if vertex_count <= 0 or vertex_count > MAX_VERTICES or vertex_ofs < 64 or mesh_ofs < 64:
            raise ConvertError(f"invalid collision MDT sections in {obj['name']}")
        checked_resource_span(data,mesh,size,vertex_ofs,vertex_count*16,f"collision vertices {obj['name']}")
        checked_resource_span(data,mesh,size,mesh_ofs,24,f"collision index set {obj['name']}")
        num=struct.unpack_from("<I",data,mesh+mesh_ofs+20)[0]
        if num > MAX_TRIANGLES or 24+num*20 > size-mesh_ofs:
            raise ConvertError(f"invalid collision triangle count in {obj['name']}")
        matrix=matrices[i]
        for j in range(num):
            at=mesh+mesh_ofs+24+j*20
            ids=struct.unpack_from("<3i",data,at)
            if any(k<0 or k>=vertex_count for k in ids):
                raise ConvertError(f"collision vertex index out of range in {obj['name']}")
            tri=[]
            for k in ids:
                p=struct.unpack_from("<3f",data,mesh+vertex_ofs+k*16)
                if not all(math.isfinite(v) for v in p): raise ConvertError("non-finite collision vertex")
                tri.append(list(transform_point(matrix,p)))
            info=struct.unpack_from("<i",data,at+12)[0]; attr=None
            if attributes and info_ofs>0 and info>=0:
                attr=struct.unpack_from("<4h",checked_resource_span(data,mesh,size,info_ofs+info*16,16,f"collision attribute {obj['name']}"))
            records.append((obj["name"],tri,attr))
            if len(records)>MAX_TRIANGLES: raise ConvertError("room exceeds triangle limit")
    if not records: raise ConvertError("collision MDS contains no triangles")
    return records


def png_rgba(width: int, height: int, rgba: bytes) -> bytes:
    if width <= 0 or height <= 0 or width*height > 16_777_216 or len(rgba)!=width*height*4:
        raise ConvertError("invalid decoded texture dimensions")
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I",len(payload))+kind+payload+struct.pack(">I",zlib.crc32(kind+payload)&0xffffffff)
    rows=b"".join(b"\0"+rgba[y*width*4:(y+1)*width*4] for y in range(height))
    return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,6,0,0,0))+chunk(b"IDAT",zlib.compress(rows,9))+chunk(b"IEND",b"")


def validate_png(data: bytes) -> None:
    signature=b"\x89PNG\r\n\x1a\n"
    if not data.startswith(signature): raise ConvertError("texture is not PNG")
    pos=len(signature); width=height=None; saw_end=False; compressed=bytearray()
    while pos<len(data):
        if pos+12>len(data): raise ConvertError("truncated PNG chunk")
        size=struct.unpack_from(">I",data,pos)[0]; kind=data[pos+4:pos+8]
        if size>len(data)-pos-12: raise ConvertError("PNG chunk exceeds file")
        body=data[pos+8:pos+8+size]; crc=struct.unpack_from(">I",data,pos+8+size)[0]
        if zlib.crc32(kind+body)&0xffffffff!=crc: raise ConvertError("PNG CRC mismatch")
        if kind==b"IHDR":
            if width is not None or size!=13: raise ConvertError("invalid PNG IHDR")
            width,height,depth,color,compression,filter_method,interlace=struct.unpack(">IIBBBBB",body)
            if depth!=8 or color!=6 or compression or filter_method or interlace or width<=0 or height<=0 or width>16384 or height>16384 or width*height>16_777_216:
                raise ConvertError("unsupported PNG encoding")
        elif kind==b"IDAT": compressed.extend(body)
        elif kind==b"IEND":
            if size!=0 or pos+12!=len(data): raise ConvertError("invalid PNG IEND")
            saw_end=True; break
        pos+=12+size
    if width is None or not saw_end: raise ConvertError("incomplete PNG")
    try: raw=zlib.decompress(compressed)
    except zlib.error as exc: raise ConvertError("invalid PNG image stream") from exc
    row=width*4+1
    if len(raw)!=row*height or any(raw[y*row] > 4 for y in range(height)):
        raise ConvertError("invalid PNG scanline data")


def decode_img(img: bytes, rgba32: bool=False) -> dict[str, tuple[bytes,int,int]]:
    return {name:(png_rgba(w,h,rgba),w,h) for name,(rgba,w,h) in decode_img_rgba(img,rgba32).items()}


def decode_img_rgba(img: bytes, rgba32: bool=False) -> dict[str, tuple[bytes,int,int]]:
    """Raw RGBA (alpha already doubled from the GS 0..128 range) per IMG entry. Room images are 8-bit
    CLUT only; rgba32=True also accepts TIM2 type-3 (32-bit) entries such as fire.img's lightling."""
    if len(img)<16 or img[:4] not in (b"IM2\0",b"IMG\0"):
        raise ConvertError("unsupported IMG signature")
    count=struct.unpack_from("<I",img,4)[0]
    if count>1024 or 16+count*48>len(img): raise ConvertError("invalid IMG entry table")
    out={}
    for i in range(count):
        at=16+i*48
        try: name=img[at:at+32].split(b"\0",1)[0].decode("ascii","strict")
        except UnicodeDecodeError as exc: raise ConvertError("non-ASCII IMG texture name") from exc
        off=struct.unpack_from("<I",img,at+32)[0]
        h=checked_span(img,off,80,"TIM2 picture header")
        if h[:4]!=b"TIM2": raise ConvertError(f"unsupported TIM2 payload for {name}")
        typ=h[35]; width,height=struct.unpack_from("<HH",h,36)
        ph=checked_span(img,off+16,64,"TIM2 picture metadata")
        image_size=struct.unpack_from("<I",ph,8)[0]
        header_size,colors=struct.unpack_from("<HH",ph,12)
        mip_count=ph[17]; psm=ph[19]
        clut_type=ph[18]
        if rgba32 and typ==3 and psm==3 and mip_count>=1 and header_size>=48:
            if not 0<width*height<=MAX_VERTICES or image_size<width*height*4:
                raise ConvertError(f"invalid 32-bit texture dimensions for {name}")
            raw=bytes(checked_span(img,off+16+header_size,width*height*4,f"pixels for {name}"))
            # PSMCT32 is the GS's own page format, so a 32-bit IM2 entry is stored linearly.
            out[name]=(bytes(b if j%4!=3 else min(b*2,255) for j,b in enumerate(raw)),width,height)
            continue
        if typ!=5 or psm!=5 or mip_count<1 or header_size<48:
            raise ConvertError(f"unsupported texture layout {name}: TIM2 type={typ}, psm={psm}")
        if (clut_type&0x3f)==1 or colors!=256:
            raise ConvertError(f"unsupported palette layout for {name}")
        pixels=off+16+header_size
        raw=bytes(checked_span(img,pixels,image_size,f"pixels for {name}"))
        palette_at=pixels+image_size
        palette=bytes(checked_span(img,palette_at,colors*4,f"palette for {name}"))
        if width*height>MAX_VERTICES or image_size < width*height or colors<1:
            raise ConvertError(f"invalid indexed texture dimensions for {name}")
        # DC1 IM2 stores GS PSMT8 pages. Tile decoding is implemented from the port's
        # inverse of PageConv8to32/BlockConv8to32 mapping.
        indices=unswizzle_psmt8(raw,width,height)
        rgba=bytearray(width*height*4)
        csm1=(clut_type&0xc0)==0
        for j,index in enumerate(indices):
            if index>=colors: raise ConvertError(f"palette index out of range in {name}")
            slot=((index&~0x18)|((index&0x08)<<1)|((index&0x10)>>1)) if csm1 else index
            r,g,b,a=palette[slot*4:slot*4+4]
            rgba[j*4:j*4+4]=bytes((r,g,b,min(a*2,255)))
        out[name]=(bytes(rgba),width,height)
    return out


def unswizzle_psmt8(raw: bytes, width: int, height: int) -> bytes:
    if len(raw)<width*height: raise ConvertError("truncated PSMT8 pixels")
    out=bytearray(width*height)
    if width%16 or height%16:
        out[:]=raw[:width*height]
        return bytes(out)
    # PSMT8 addresses are tiled within each 16x16 block and the GS interleaves
    # those blocks in 32-block pages. This is the byte-address form of the donor
    # runtime's indexed-texture sampling layout.
    for y in range(height):
        for x in range(width):
            block=(y&~0x0f)*width+(x&~0x0f)*2
            swap=(((y+2)>>2)&1)*4
            pos_y=(((y&~3)>>1)+(y&1))&7
            column=pos_y*width*2+((x+swap)&7)*4
            byte_num=((y>>1)&1)+((x>>2)&2)
            address=block+column+byte_num
            if address>=len(raw): raise ConvertError("PSMT8 swizzle address out of range")
            out[y*width+x]=raw[address]
    return bytes(out)


def colour_factor(value: float) -> float:
    """Per-vertex colour as a modulation factor: visualvu1.cpp ColourByte stores value*128 rounded
    and saturated to a GS byte, and the mesh shader multiplies by byte/0x80 (gfx README)."""
    scaled=value*128.0
    byte=0 if scaled<=0.0 else 255 if scaled>=255.0 else int(scaled+0.5)
    return byte/128.0


def parse_visual_mds(data: bytes, placements: tuple[float,...], turn: int, textures: dict[str, tuple[bytes,int,int]],
                     local: bool=False) -> tuple[list, int]:
    """Visual triangle groups of an MDS. With local=True every vertex stays in its own object's frame
    (no placement) and each group also records its object index and MDT material slot, for models
    whose objects a motion moves (the Dran field tiles)."""
    texture_indices={name.casefold():i for i,name in enumerate(sorted(textures,key=str.casefold))}
    objects=parse_mds(data); visuals=[]; tri_count=0
    matrices=[_IDENTITY]*len(objects) if local else world_matrices(objects,placements,turn)
    for i,obj in enumerate(objects):
        mesh=obj["mesh"]
        if not mesh: continue
        size,vertex_count,vertex_ofs=struct.unpack_from("<Iii",data,mesh+8)
        normal_count,normal_ofs=struct.unpack_from("<ii",data,mesh+20)
        face_size,face_ofs=struct.unpack_from("<ii",data,mesh+36)
        uv_count,uv_ofs=struct.unpack_from("<ii",data,mesh+44)
        material_count=struct.unpack_from("<i",data,mesh+52)[0]
        info_ofs=struct.unpack_from("<i",data,mesh+56)[0]
        color_count,color_ofs=struct.unpack_from("<ii",data,mesh+28)
        if not 0<vertex_count<=MAX_VERTICES or not 0<normal_count<=MAX_VERTICES or not 0<uv_count<=MAX_VERTICES or face_ofs<64 or face_size<16 or material_count<0 or material_count>1024:
            raise ConvertError(f"invalid visual MDT layout in {obj['name']}")
        # visualvu1.cpp View(): colours exist iff colour_ofs > 0, and then every strip entry is
        # {v, n, uv, colour} (stride 4 words) instead of {v, n, uv}.
        has_colour=color_ofs>0
        if color_count < 0 or (has_colour and color_count == 0) or (color_count and not has_colour):
            raise ConvertError("invalid per-index color section")
        if has_colour:
            checked_resource_span(data,mesh,size,color_ofs,color_count*16,"visual color array")
        checked_resource_span(data,mesh,size,vertex_ofs,vertex_count*16,"visual vertex array")
        checked_resource_span(data,mesh,size,normal_ofs,normal_count*16,"visual normal array")
        checked_resource_span(data,mesh,size,uv_ofs,uv_count*16,"visual UV array")
        checked_resource_span(data,mesh,size,face_ofs,face_size,"visual face section")
        mats=[]
        if material_count:
            if info_ofs<64: raise ConvertError("invalid material offset")
            checked_resource_span(data,mesh,size,info_ofs,material_count*96,"material table")
            for m in range(material_count):
                at=mesh+info_ofs+m*96
                diffuse=struct.unpack_from("<4f",data,at)
                if not all(math.isfinite(x) for x in diffuse): raise ConvertError("non-finite material diffuse color")
                try: tex=data[at+52:at+96].split(b"\0",1)[0].decode("ascii","strict")
                except UnicodeDecodeError as exc: raise ConvertError("non-ASCII MDT material texture name") from exc
                tex_id=next((n for n in textures if n.casefold()==tex.casefold()),None) if tex else None
                if tex and tex_id is None: raise ConvertError(f"material texture {tex!r} is absent from room IMG")
                mats.append((diffuse,texture_indices[tex_id.casefold()] if tex_id else -1))
        face=mesh+face_ofs
        if face_size < 16 or struct.unpack_from("<I",data,face+4)[0]!=16: raise ConvertError("unsupported MDT face header")
        prims=struct.unpack_from("<I",data,face+8)[0]
        if prims>MAX_TRIANGLES: raise ConvertError("too many visual primitives")
        cur=face+16; end=face+face_size
        for _ in range(prims):
            if cur > end or end-cur < 12:
                raise ConvertError("primitive header escapes MDT face section")
            checked_resource_span(data,mesh,size,cur-mesh,12,"primitive header")
            code, count, material=struct.unpack_from("<III",data,cur)
            style=code&0xff
            stride=16 if has_colour else 12
            if count<3 or material< -1 or material>=max(material_count,1): raise ConvertError("unsupported primitive index/material")
            cur+=12
            if cur > end or count > (end-cur)//stride:
                raise ConvertError("primitive indices escape MDT face section")
            checked_resource_span(data,mesh,size,cur-mesh,count*stride,"primitive indices")
            indices=[]
            for k in range(count):
                vals=struct.unpack_from("<"+"i"*(stride//4),data,cur+k*stride)
                vi,ni,ui=vals[:3]
                if vi>=vertex_count or vi<0 or ni>=normal_count or ni<0 or ui>=uv_count or ui<0:
                    raise ConvertError("visual index out of range")
                p=struct.unpack_from("<3f",data,mesh+vertex_ofs+vi*16)
                n=struct.unpack_from("<3f",data,mesh+normal_ofs+ni*16)
                uv=struct.unpack_from("<2f",data,mesh+uv_ofs+ui*16)
                if not all(math.isfinite(x) for x in (*p,*n,*uv)): raise ConvertError("non-finite visual vertex")
                if has_colour:
                    ci=vals[3]
                    if ci<0 or ci>=color_count: raise ConvertError("visual color index out of range")
                    vc=struct.unpack_from("<4f",data,mesh+color_ofs+ci*16)
                    if not all(math.isfinite(x) for x in vc): raise ConvertError("non-finite visual color")
                    diffuse=mats[material][0] if mats and material>=0 else (1.0,1.0,1.0,1.0)
                    color=tuple(max(0.0,min(1.0,d*colour_factor(v))) for d,v in zip(diffuse,vc))
                else:
                    color=tuple(max(0.0,min(1.0,x)) for x in mats[material][0]) if mats and material>=0 else (1.0,1.0,1.0,1.0)
                indices.append({"position":transform_point(matrices[i],p),"normal":transform_normal(matrices[i],n),"uv":uv,"color":color})
            cur+=count*stride
            if cur>end: raise ConvertError("primitive escapes MDT face section")
            # GL_TRIANGLE_STRIP/list/fan are the styles used by the real DC1 room; reject lines.
            if style not in (3,4): raise ConvertError(f"unsupported triangle primitive style 0x{style:02x}")
            if style == 3:
                if count%3: raise ConvertError("triangle-list primitive has trailing indices")
                tri_indices=[(k,k+1,k+2) for k in range(0,count-count%3,3)]
            else:
                tri_indices=[(k,k+1,k+2) if k%2==0 else (k+1,k,k+2) for k in range(count-2)]
            verts=[]
            for tri in tri_indices:
                for k in tri: verts.append(indices[k])
            if verts:
                texture_index=mats[material][1] if mats and material>=0 else -1
                visuals.append({"material":texture_index,"vertices":[{"position":list(v["position"]),"normal":list(v["normal"]),"uv":list(v["uv"]),"color":list(v["color"])} for v in verts]})
                if local: visuals[-1].update({"object":i,"mdt_material":material})
                tri_count+=len(verts)//3
                if tri_count>MAX_TRIANGLES: raise ConvertError("room exceeds visual triangle limit")
        if cur>end: raise ConvertError("face section overrun")
    if not visuals: raise ConvertError("visual MDS contains no triangles")
    return visuals,tri_count


def validate_pack(root: Path) -> dict:
    try:
        json_path=root/"room.json"
        if json_path.stat().st_size==0 or json_path.stat().st_size>MAX_ROOM_JSON:
            raise ConvertError("room.json is empty or exceeds native size limit")
        payload=json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError,UnicodeError,json.JSONDecodeError,RecursionError) as exc: raise ConvertError("cannot read room.json") from exc
    if not isinstance(payload,dict): raise ConvertError("room.json root must be an object")
    if payload.get("format")!="ixion-room" or type(payload.get("version")) is not int or payload["version"]!=1: raise ConvertError("unsupported room pack version")
    def object_value(value, label: str) -> dict:
        if not isinstance(value,dict): raise ConvertError(f"{label} must be an object")
        return value
    def number(value, label: str) -> float:
        if isinstance(value,bool) or not isinstance(value,(int,float)):
            raise ConvertError(f"invalid {label}")
        try: numeric=float(value)
        except (OverflowError,ValueError) as exc: raise ConvertError(f"invalid {label}") from exc
        if not math.isfinite(numeric) or abs(numeric)>1.0e7: raise ConvertError(f"invalid {label}")
        as_float=struct.unpack("<f",struct.pack("<f",numeric))[0]
        if not math.isfinite(as_float): raise ConvertError(f"invalid {label}")
        return as_float
    def finite_vec(value, size: int, label: str) -> list[float]:
        # The native consumer converts every coordinate to float32 before any
        # comparison, so all dependent checks below use these converted values.
        if not isinstance(value,list) or len(value)!=size:
            raise ConvertError(f"invalid {label}")
        return [number(component,label) for component in value]
    def f32(value: float) -> float:
        # One float32 rounding, as the native C++ float arithmetic performs.
        return struct.unpack("<f",struct.pack("<f",value))[0]
    donor=object_value(payload.get("donor"),"donor")
    if donor.get("game")!="dc1" or not isinstance(donor.get("room"),str) or not donor["room"] or len(donor["room"])>64:
        raise ConvertError("invalid donor identity")
    sources=donor.get("sources")
    if not isinstance(sources,list) or not sources or len(sources)>4096: raise ConvertError("donor sources are required")
    for source in sources:
        source=object_value(source,"donor source record")
        path=source.get("path",""); digest=source.get("sha256","")
        rel=PurePosixPath(path) if isinstance(path,str) else PurePosixPath("")
        if not isinstance(path,str) or len(path)>240 or "\0" in path or rel.is_absolute() or ".." in rel.parts or "." in rel.parts or "\\" in path or ":" in path or not path: raise ConvertError("unsafe donor source path")
        if not isinstance(digest,str) or not re.fullmatch(r"[0-9a-fA-F]{64}",digest): raise ConvertError("invalid donor source digest")
    units=object_value(payload.get("units"),"units")
    scale=number(units.get("scale"),"unit scale")
    if scale<=0 or scale>1000: raise ConvertError("invalid unit scale")
    markers={key:finite_vec(payload.get(key),3,key) for key in ("spawn","enemy_spawn","exit")}
    bounds=object_value(payload.get("bounds"),"bounds")
    bmin=finite_vec(bounds.get("min"),3,"bounds.min"); bmax=finite_vec(bounds.get("max"),3,"bounds.max")
    if any(not (bmin[i]<bmax[i]) or f32(bmax[i]-bmin[i])>200000.0 for i in range(3)): raise ConvertError("invalid room bounds")
    lo=[f32(bmin[i]-f32(0.01)) for i in range(3)]; hi=[f32(bmax[i]+f32(0.01)) for i in range(3)]
    for key in ("spawn","enemy_spawn","exit"):
        if any(markers[key][i]<bmin[i] or markers[key][i]>bmax[i] for i in range(3)):
            raise ConvertError(f"{key} marker outside declared room bounds")
    textures=payload.get("textures")
    if not isinstance(textures,list) or len(textures)>MAX_PACK_TEXTURES: raise ConvertError("invalid room texture count")
    for tex in textures:
        tex=object_value(tex,"texture record")
        if not isinstance(tex.get("name"),str) or not tex["name"] or len(tex["name"])>64: raise ConvertError("invalid texture record")
        filename=tex.get("file","")
        rel=PurePosixPath(filename) if isinstance(filename,str) else PurePosixPath("")
        if not isinstance(filename,str) or not filename or len(filename)>240 or "\0" in filename or rel.is_absolute() or ".." in rel.parts or "." in rel.parts or "\\" in filename or ":" in filename: raise ConvertError("unsafe texture path")
        try: path=(root/Path(*rel.parts)).resolve(); base=root.resolve()
        except (OSError,RuntimeError,ValueError) as exc: raise ConvertError("cannot resolve room texture path") from exc
        if base not in path.parents or path==base: raise ConvertError("texture escapes room root")
        try: b=path.read_bytes()
        except OSError as exc: raise ConvertError("cannot read room texture") from exc
        if not b or len(b)>32*1024*1024: raise ConvertError("texture is empty or exceeds native PNG limit")
        validate_png(b)
    visuals=payload.get("visuals")
    if not isinstance(visuals,list) or not visuals: raise ConvertError("room has no visual triangles")
    if len(visuals)>MAX_PACK_VISUALS: raise ConvertError("too many visual groups")
    total_visual_vertices=0
    for visual in visuals:
        visual=object_value(visual,"visual record")
        mat=visual.get("material"); verts=visual.get("vertices")
        if type(mat) is not int or mat < -1 or mat>=len(textures): raise ConvertError("visual material index out of range")
        if not isinstance(verts,list) or not verts or len(verts)%3 or len(verts)>MAX_VERTICES*3: raise ConvertError("visual vertices must be nonempty triangle lists")
        total_visual_vertices+=len(verts)
        if total_visual_vertices>MAX_VERTICES: raise ConvertError("room exceeds total visual vertex limit")
        for v in verts:
            v=object_value(v,"visual vertex")
            converted={key:finite_vec(v.get(key),size,label) for key,size,label in (("position",3,"vertex position"),("normal",3,"vertex normal"),("uv",2,"vertex UV"),("color",4,"vertex color"))}
            if any(c<0 or c>1 for c in converted["color"]): raise ConvertError("vertex color outside 0..1")
            if any(converted["position"][i]<lo[i] or converted["position"][i]>hi[i] for i in range(3)):
                raise ConvertError("visual vertex outside declared room bounds")
    collision=payload.get("collision")
    if not isinstance(collision,list) or not collision or len(collision)>MAX_PACK_COLLISION: raise ConvertError("invalid collision triangle list")
    for tri in collision:
        if not isinstance(tri,list) or len(tri)!=3: raise ConvertError("collision entry must be a triangle")
        points=[finite_vec(p,3,"collision vertex") for p in tri]
        for p in points:
            if any(p[i]<lo[i] or p[i]>hi[i] for i in range(3)):
                raise ConvertError("collision vertex outside declared room bounds")
        # Mirror the native float32 degeneracy test operation by operation.
        a=[f32(points[1][i]-points[0][i]) for i in range(3)]; b=[f32(points[2][i]-points[0][i]) for i in range(3)]
        cross=(f32(f32(a[1]*b[2])-f32(a[2]*b[1])),f32(f32(a[2]*b[0])-f32(a[0]*b[2])),f32(f32(a[0]*b[1])-f32(a[1]*b[0])))
        length2=f32(f32(f32(cross[0]*cross[0])+f32(cross[1]*cross[1]))+f32(cross[2]*cross[2]))
        if not length2>f32(1.0e-12): raise ConvertError("degenerate collision triangle")
    return payload


WALKABLE_NY = 0.65  # same walkable-normal threshold as the R3 marker/route qualification


def ground_heights(collision: list, x: float, z: float) -> list[float]:
    """Heights of walkable collision surfaces under (x, z), by barycentric projection."""
    out=[]
    for tri in collision:
        (x1,y1,z1),(x2,y2,z2),(x3,y3,z3)=tri
        if x<min(x1,x2,x3)-1e-6 or x>max(x1,x2,x3)+1e-6 or z<min(z1,z2,z3)-1e-6 or z>max(z1,z2,z3)+1e-6: continue
        den=(z2-z3)*(x1-x3)+(x3-x2)*(z1-z3)
        if abs(den)<1e-8: continue
        a=((z2-z3)*(x-x3)+(x3-x2)*(z-z3))/den
        b=((z3-z1)*(x-x3)+(x1-x3)*(z-z3))/den
        c=1-a-b
        if min(a,b,c)<-1e-6: continue
        nx=(y2-y1)*(z3-z1)-(z2-z1)*(y3-y1)
        ny=(z2-z1)*(x3-x1)-(x2-x1)*(z3-z1)
        nz=(x2-x1)*(y3-y1)-(y2-y1)*(x3-x1)
        length=math.sqrt(nx*nx+ny*ny+nz*nz)
        if length and abs(ny)/length>=WALKABLE_NY: out.append(a*y1+b*y2+c*y3)
    return out


def ground_under(collision: list, point: tuple[float,float,float], rise: float, drop: float) -> float | None:
    """Highest walkable surface at most `rise` above and `drop` below the point, or None."""
    candidates=[y for y in ground_heights(collision,point[0],point[2]) if point[1]-drop<=y<=point[1]+rise]
    return max(candidates) if candidates else None


def route_support(collision: list, points: list, step: float, rise: float, drop: float) -> tuple[int,int]:
    """Samples along the marker polyline (every `step`) with walkable ground near the
    interpolated marker height. Reported, not enforced: real routes need not be straight."""
    ok=total=0
    for a,b in zip(points,points[1:]):
        length=math.dist((a[0],a[2]),(b[0],b[2])); n=max(1,int(math.ceil(length/step)))
        for i in range(n+1):
            t=i/n; q=tuple(a[j]+(b[j]-a[j])*t for j in range(3))
            total+=1; ok+=ground_under(collision,q,rise,drop) is not None
    return ok,total


def frame_origins(data: bytes, placed: tuple[float,...], turn: int) -> dict[str, list[tuple[float,float,float]]]:
    objects=parse_mds(data); matrices=world_matrices(objects,placed,turn); out={}
    for i,obj in enumerate(objects):
        out.setdefault(obj["name"].casefold(),[]).append(transform_point(matrices[i],(0.0,0.0,0.0)))
    return out


def resolve_markers(spec: dict, parts: list, members: dict, collision: list) -> dict:
    """Resolve authored markers in donor units, then put each on walkable ground.

    {"frame": name[, "part": first PT_BASE name]} uses DC1 PT_MARKER semantics: the named frame
    of the part's PT_COLS model, placed and turned with that collision (itemdata.cpp:1254,
    dungeonparts.cpp:2115-2132). {"donor": [x,y,z]} is an authored donor-unit position.
    """
    if not isinstance(spec,dict): raise ConvertError("marker file must be a JSON object")
    resolved={}
    for key in ("spawn","enemy_spawn","exit"):
        entry=spec.get(key)
        if not isinstance(entry,dict): raise ConvertError(f"marker file lacks {key}")
        if "frame" in entry:
            name=str(entry["frame"]).casefold(); want=entry.get("part")
            hits=[]
            for part in parts:
                if part.collision is None: continue
                if want is not None and part.frames[0].name.casefold()!=str(want).casefold(): continue
                origins=frame_origins(members[part.collision[0].casefold()].data,part.frames[0].offset,part_collision_turn(part))
                hits.extend(origins.get(name,[]))
            if len(hits)!=1: raise ConvertError(f"{key} marker frame {entry['frame']!r} matches {len(hits)} collision frames")
            point=hits[0]; source=f"frame:{entry['frame']}"
        elif "donor" in entry:
            v=entry["donor"]
            if not isinstance(v,list) or len(v)!=3 or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in v):
                raise ConvertError(f"{key} donor position must be three finite numbers")
            point=tuple(float(x) for x in v); source="donor"
        else: raise ConvertError(f"{key} marker needs frame or donor")
        rise=float(entry.get("rise",2.0)); drop=float(entry.get("drop",20.0))
        ground=ground_under(collision,point,rise,drop)
        if ground is None: raise ConvertError(f"{key} marker at {point} has no supported ground")
        resolved[key]={"source":source,"donor":list(point),"ground":[point[0],ground,point[2]]}
    return resolved


def convert(pack_path: Path, cfg_path: Path, output: Path, room: str, visual_name: str, collision_name: str,
            spawn: tuple[float,float,float], enemy: tuple[float,float,float], exit_at: tuple[float,float,float], scale: float,
            all_parts: bool=False, markers: dict | None=None) -> dict:
    if scale<=0 or not math.isfinite(scale): raise ConvertError("scale must be finite and positive")
    pack_bytes=pack_path.read_bytes(); cfg_bytes=cfg_path.read_bytes()
    members=parse_pack(pack_bytes)
    room_cfg=parse_room_cfg(cfg_bytes)
    parts=list(room_cfg.parts) if all_parts else [select_part(room_cfg,visual_name,collision_name)]
    if not room_cfg.ground_images: raise ConvertError("room config lacks GRD_IMG")
    needed=[f.name for p in parts for f in p.frames]+[p.collision[0] for p in parts if p.collision]+list(room_cfg.ground_images)
    if any(members.get(n.casefold()) is None for n in needed): raise ConvertError("required visual, collision, or room IMG member is missing")
    # GRD_IMG names the room's texture image (itemdata.cpp:621-640); no file name is assumed.
    textures={}
    for name in room_cfg.ground_images:
        for tex,value in decode_img(members[name.casefold()].data).items():
            if any(t.casefold()==tex.casefold() for t in textures): raise ConvertError(f"texture {tex!r} appears in two GRD_IMG files")
            textures[tex]=value
    visuals=[]; visual_count=0; collisions=[]; part_stats=[]
    for part in parts:
        part_visuals=0
        for frame in part.frames:
            got,count=parse_visual_mds(members[frame.name.casefold()].data,frame.offset,frame_visual_turn(frame),textures)
            visuals.extend(got); visual_count+=count; part_visuals+=count
        part_collision=[]
        if part.collision is not None:
            # Parts without PT_COLS have no collision model at all: the fixed-floor collision loop
            # skips parts whose collision is NULL (dungeonparts.cpp:2104-2113).
            part_collision=parse_collision_mds(members[part.collision[0].casefold()].data,part.frames[0].offset,part_collision_turn(part))
            collisions.extend(part_collision)
        part_stats.append({"part":part.index,"frames":[f.name for f in part.frames],"visual_turns":[frame_visual_turn(f) for f in part.frames],
                           "collision":part.collision[0] if part.collision else None,
                           "collision_turn":part_collision_turn(part) if part.collision else None,
                           "visual_triangles":part_visuals,"collision_triangles":len(part_collision)})
    if not collisions: raise ConvertError("room has no collision")
    marker_report=None
    if markers is not None:
        marker_report=resolve_markers(markers,parts,members,collisions)
        spawn,enemy,exit_at=(tuple(x*scale for x in marker_report[k]["ground"]) for k in ("spawn","enemy_spawn","exit"))
        route=[marker_report[k]["ground"] for k in ("spawn","enemy_spawn","exit")]
        ok,total=route_support(collisions,route,5.0/scale,2.0,2.0)
        marker_report["straight_route_support"]=[ok,total]
    else:
        for key,point in (("spawn",spawn),("enemy_spawn",enemy),("exit",exit_at)):
            donor=tuple(x/scale for x in point)
            if ground_under(collisions,donor,0.1/scale,0.1/scale) is None:
                raise ConvertError(f"{key} marker has no supported ground")
    output=output.resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists(): raise ConvertError("output already exists; choose a new path")
    tex_records=[]
    pts=[p["position"] for group in visuals for p in group["vertices"]]
    pts.extend(point for triangle in collisions for point in triangle)
    bounds={"min":[min(p[a] for p in pts)*scale for a in range(3)],"max":[max(p[a] for p in pts)*scale for a in range(3)]}
    src=[{"path":pack_path.name,"sha256":hashlib.sha256(pack_bytes).hexdigest()},
         {"path":cfg_path.name,"sha256":hashlib.sha256(cfg_bytes).hexdigest()}]
    # The frozen v1 contract carries room-relative geometry; actor measurements choose scale.
    for group in visuals:
        for v in group["vertices"]: v["position"]=[x*scale for x in v["position"]]
    collisions=[[[x*scale for x in p] for p in tri] for tri in collisions]
    doc={"format":"ixion-room","version":1,"donor":{"game":"dc1","room":room,"sources":src},
         "units":{"scale":scale},"spawn":list(spawn),"enemy_spawn":list(enemy),
         "exit":list(exit_at),"bounds":bounds,"textures":tex_records,"visuals":visuals,"collision":collisions}
    with tempfile.TemporaryDirectory(prefix=output.name+".tmp-",dir=output.parent) as staging_name:
        staging=Path(staging_name)
        for i,(name,(png,w,h)) in enumerate(sorted(textures.items(),key=lambda item:item[0].casefold())):
            filename=f"textures/{i:02d}-{re.sub(r'[^A-Za-z0-9_.-]','_',name)}.png"
            target=staging/filename; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(png)
            tex_records.append({"name":name,"file":filename})
        doc["textures"]=tex_records
        (staging/"room.json").write_text(json.dumps(doc,separators=(",",":"),allow_nan=False),encoding="utf-8")
        validate_pack(staging)
        os.replace(staging,output)
    result={"members":len(members),"visual_groups":len(visuals),"visual_triangles":visual_count,
            "collision_triangles":len(collisions),"textures":len(tex_records),"texture_names":[x["name"] for x in tex_records],"bounds":bounds,
            "parts":part_stats,"markers_output":{"spawn":list(spawn),"enemy_spawn":list(enemy),"exit":list(exit_at)}}
    if marker_report is not None: result["markers_donor"]=marker_report
    return result


# --- Placed DC1 objects (props.json sidecar; room.json v1 stays frozen) ---------------------------

MAX_STB = 16 * 1024 * 1024
MAX_STB_OPS = 4096
# DC1 btsysscript.cpp ext numbers (table at btsysscript.cpp:1117-1125).
EXT_SET_DUNGEON_MAP = 1051  # _SET_DUNGEON_MAP(file, map_type): last call names the floor's map
EXT_SET_ATRA = 1058         # _SET_ATRA(x, y, z, atla_no) -> NowDngMap->SetAtraBoll
EXT_SET_IBOX = 1059         # _SET_IBOX(x, y, z, item) -> NowDngMap->SetTreasureBox(.., TREASURE_BOX_SMALL, 0)
# DC1 items whose role the consumer maps to its own native item (crosswalk-items-world.md:95).
DC1_ITEM_ROLES = {195: "gate_key"}


@dataclass(frozen=True)
class StbExtCall:
    program: int
    offset: int         # byte offset of the EXT instruction from the program start
    number: int | None  # ext number, None when it was not a constant
    args: tuple         # symbolic operands: ("i", v), ("f", v), ("s", text) or ("x", ...)


def _fold_unary(op: int, value):
    if value is None or value[0] not in ("i", "f"):
        return ("x", op, value)
    if op == 0x0B: return (value[0], -value[1])            # NEG
    if op == 0x0C: return ("f", float(value[1]))           # TOFLOAT
    if op == 0x0D: return ("i", int(value[1]))             # TOINT
    return ("x", op, value)


def decode_stb_ext_calls(blob: bytes) -> list[StbExtCall]:
    """Linear walk of every DC1 .stb program, recording EXT calls with constant-folded operands.

    Layout per DarkCloud-Toolkit DC_STB_FORMAT.md: header {magic "STB\\0", main, code_base, id_table,
    id_count, msg}; id table of {program_id, funcdata}; funcdata {code_off, _, frame, argc}; 12-byte
    instructions {op, a, b}. Branches are not followed: a program is read from its start to its
    first RET/END, so calls are reported in code order, not in executed order.
    """
    if len(blob) > MAX_STB: raise ConvertError("event.stb exceeds 16 MiB limit")
    header=checked_span(blob,0,24,"STB header")
    if bytes(header[:4])!=b"STB\0": raise ConvertError("unsupported STB signature")
    _magic,_main,code_base,id_off,id_count,_msg=struct.unpack_from("<6I",blob,0)
    if id_count>4096: raise ConvertError("STB program count exceeds limit")
    checked_span(blob,id_off,id_count*8,"STB program table")
    calls=[]
    for k in range(id_count):
        program,fd_off=struct.unpack_from("<2I",blob,id_off+8*k)
        checked_span(blob,fd_off,16,"STB funcdata")
        code_off=struct.unpack_from("<I",blob,fd_off)[0]
        start=code_base+code_off
        checked_span(blob,start,12,f"STB program {program} code")
        stack=[]; pc=start
        for _ in range(MAX_STB_OPS):
            if pc+12>len(blob): break
            op,a,b=struct.unpack_from("<3I",blob,pc)
            if op==0x03:  # PUSHCONST: a is the constant's type
                if a==1: stack.append(("i",b-0x100000000 if b>=0x80000000 else b))
                elif a==2: stack.append(("f",struct.unpack("<f",struct.pack("<I",b))[0]))
                elif a==3:
                    at=code_base+b
                    if at>=len(blob): raise ConvertError("STB string constant out of range")
                    end=blob.find(b"\0",at,min(len(blob),at+256))
                    if end<0: raise ConvertError("unterminated STB string constant")
                    stack.append(("s",blob[at:end].decode("latin-1")))
                else: stack.append(("x","const",a,b))
            elif op in (0x01,0x02):  # PUSHVAR/PUSHADDR; indexed forms pop the index
                if (b&7) in (2,4) and stack: stack.pop()
                stack.append(("x","var",a,b&0x3F))
            elif op==0x04:
                if stack: stack.pop()
            elif op==0x05:
                del stack[max(0,len(stack)-2):]
            elif op==0x15:  # EXT: a = items consumed, ext number first
                items=stack[len(stack)-a:] if a<=len(stack) else stack[:]
                del stack[len(stack)-len(items):]
                number=items[0][1] if items and items[0][0]=="i" else None
                calls.append(StbExtCall(program,pc-start,number,tuple(items[1:])))
            elif op in (0x0F,0x1B): break  # RET / END
            elif op in (0x06,0x07,0x08,0x09,0x0A,0x0E,0x18,0x19):
                r=stack.pop() if stack else None; l=stack.pop() if stack else None
                stack.append(("x","bin",op,l,r))
            elif op in (0x0B,0x0C,0x0D,0x1A,0x1D,0x1E):
                stack.append(_fold_unary(op,stack.pop() if stack else None))
            elif op in (0x11,0x12):
                if stack: stack.pop()
            elif op==0x13: stack=[]
            elif op==0x14:
                del stack[max(0,len(stack)-a):]
            pc+=12
    return calls


def _const(value, kinds: str):
    return value[1] if value is not None and value[0] in kinds else None


def room_placements_from_stb(calls: list[StbExtCall], room: str) -> list[dict]:
    """SET_IBOX/SET_ATRA calls that follow SET_DUNGEON_MAP(room, ...) in the same program, up to the
    next SET_DUNGEON_MAP. _SET_DUNGEON_MAP only latches the file name (btsysscript.cpp:623-629), and
    the boxes go to NowDngMap, so this is a code-order association; branches are not evaluated."""
    out=[]; seen=set()
    for program in sorted({c.program for c in calls}):
        current=None
        for call in (c for c in calls if c.program==program):
            if call.number==EXT_SET_DUNGEON_MAP:
                current=_const(call.args[0],"s") if call.args else None
                continue
            if current is None or current.casefold()!=room.casefold(): continue
            if call.number not in (EXT_SET_IBOX,EXT_SET_ATRA): continue
            if len(call.args)!=4: raise ConvertError(f"program {program} +0x{call.offset:x}: expected 4 operands")
            pos=[_const(v,"if") for v in call.args[:3]]; value=_const(call.args[3],"i")
            if any(p is None for p in pos) or value is None:
                raise ConvertError(f"program {program} +0x{call.offset:x}: non-constant placement")
            key=(call.number,tuple(float(p) for p in pos),value)
            if key in seen: continue
            seen.add(key)
            out.append({"op":"SET_IBOX" if call.number==EXT_SET_IBOX else "SET_ATRA","program":program,
                        "offset":call.offset,"position":[float(p) for p in pos],"value":value})
    return out


def cfg_deferred_objects(cfg: bytes) -> list[dict]:
    """PT_FIRE torches and gate markers, recorded raw for phase 2 (frame and units unverified)."""
    text=cfg.decode("cp932",errors="replace"); out=[]; part=None
    fire=re.compile(r'^\s*PT_FIRE\s+'+r'\s*,\s*'.join([_CFG_NUM]*3)+r'\s*$',re.I)
    base=re.compile(r'^\s*PT_BASE\s+"([^"\\]+)"',re.I)
    mark=re.compile(r'^\s*PT_MARKER\s+"((?:out|gatekey)[^"\\]*)"\s*,\s*'+_CFG_NUM+r'\s*,\s*'+_CFG_NUM,re.I)
    for number,raw in enumerate(text.splitlines(),1):
        line=raw.split("//",1)[0]
        if not line.strip(): continue
        keyword=line.split()[0].upper()
        if keyword=="DEF_PATS": part=None
        elif keyword=="PT_BASE" and part is None:
            m=base.match(line); part=PurePosixPath(m.group(1)).name if m else None
        elif keyword=="PT_FIRE":
            m=fire.match(line)
            if not m: raise ConvertError(f"cfg line {number}: malformed PT_FIRE")
            out.append({"kind":"torch","part":part,"cfg_line":number,"raw":[float(m.group(j)) for j in (1,2,3)]})
        elif keyword=="PT_MARKER":
            m=mark.match(line)
            if m: out.append({"kind":"gate_marker","part":part,"cfg_line":number,"frame":m.group(1),"script":int(float(m.group(3)))})
    return out


def build_props(room_pack: Path, stb_path: Path, cfg_path: Path | None=None) -> dict:
    """props.json for an existing v1 pack: DC1 chests and Atla in DC2 output units, each dropped
    onto the pack's own walkable collision (same rise/drop rule as the room markers)."""
    room=validate_pack(room_pack)
    name=room["donor"]["room"]; scale=float(room["units"]["scale"])
    stb=stb_path.read_bytes()
    placements=room_placements_from_stb(decode_stb_ext_calls(stb),name)
    if not any(p["op"]=="SET_IBOX" for p in placements): raise ConvertError(f"no SET_IBOX placement for room {name}")
    props=[]; counts={"treasure_box":0,"atla":0}
    for p in placements:
        kind="treasure_box" if p["op"]=="SET_IBOX" else "atla"
        point=tuple(x*scale for x in p["position"])
        ground=ground_under(room["collision"],point,2.0*scale,20.0*scale)
        if ground is None: raise ConvertError(f"{kind} at donor {p['position']} has no supported ground in the pack")
        if any(not (room["bounds"]["min"][i]<=v<=room["bounds"]["max"][i]) for i,v in enumerate((point[0],ground,point[2]))):
            raise ConvertError(f"{kind} at donor {p['position']} is outside the pack bounds")
        entry={"id":f"{kind}-{counts[kind]}","kind":kind,"position":[point[0],ground,point[2]],"rotation_y":0.0,
               "donor":{"op":p["op"],"program":p["program"],"offset":p["offset"],"position":p["position"]}}
        if kind=="treasure_box":
            entry["contents"]={"dc1_item":p["value"],"role":DC1_ITEM_ROLES.get(p["value"],"item"),"count":1}
            entry["donor"]["box"]="small"
        else:
            entry["donor"]["atla"]=p["value"]
        counts[kind]+=1; props.append(entry)
    room_bytes=(room_pack/"room.json").read_bytes()
    doc={"format":"ixion-room-props","version":1,"room":name,
         "room_json_sha256":hashlib.sha256(room_bytes).hexdigest(),"units":{"scale":scale},
         "sources":[{"path":stb_path.name,"sha256":hashlib.sha256(stb).hexdigest()}],"props":props,
         "deferred":cfg_deferred_objects(cfg_path.read_bytes()) if cfg_path is not None else []}
    if cfg_path is not None:
        doc["sources"].append({"path":cfg_path.name,"sha256":hashlib.sha256(cfg_path.read_bytes()).hexdigest()})
    return doc


def write_props(room_pack: Path, doc: dict) -> Path:
    target=room_pack/"props.json"
    if target.exists(): raise ConvertError("props.json already exists; remove it or choose another pack")
    staging=room_pack/"props.json.tmp"
    staging.write_text(json.dumps(doc,indent=1,allow_nan=False),encoding="utf-8")
    os.replace(staging,target)
    return target


# --- Dran arena (arena.json sidecar; room.json v1 stays frozen) ----------------------------------

ARENA_FORMAT = "ixion-room-arena"
DRAN_FIELD_SLOTS = 12        # DRAN_MAP_FIELD_SET field[12]/collision[12]/state[12] (dranmapfield.hpp:95-100)
DRAN_FIELD_DONE_AT = 59.0    # Step: state 1 -> 0 once GetNowTime() >= 59 (dranmapfield.cpp:99-104)
MAX_PART_FIRES = 6           # PT_FIRE beyond six per part are dropped (itemdata.cpp:1404)
FIRE_PARAM = 3               # every PT_FIRE gets fire_param 3 (itemdata.cpp:1408) = DrawFire layers 1|2
MOT_ROTATION, MOT_SCALE, MOT_TRANSLATION, MOT_MATERIAL_ALPHA = 0, 1, 2, 40  # MotionKeyType, gameutil.hpp:32-46
MAX_MOT_FRAME = 100_000


@dataclass(frozen=True)
class ArenaMarker:
    """PT_MARKER with every field itemdata.cpp:1233-1269 stores: radius, script_no, hold (item use),
    fade (auto start), switch_on and ext_mem (cfg comment at d01boss.cfg:97 names them)."""
    name: str
    radius: float
    script: int
    item_use: int | None
    auto_start: int | None
    switch_on: int | None
    ext_mem: int | None
    line: int


@dataclass(frozen=True)
class ArenaPart:
    index: int
    cameras: tuple[tuple[str, int, int], ...]                       # (PT_CAM model, turn, cfg line)
    fires: tuple[tuple[tuple[float, float, float], int], ...]       # (raw x,y,z, cfg line)
    dropped_fires: tuple[int, ...]                                  # cfg lines past the six-fire limit
    markers: tuple[ArenaMarker, ...]


@dataclass(frozen=True)
class ArenaCfg:
    fire_img: tuple[str, int] | None
    field_models: tuple[tuple[str, int], ...]       # DRANS_PARTS, in load (= slot) order
    field_collisions: tuple[tuple[str, int], ...]   # DRANS_COLS, in load (= slot) order
    parts: tuple[ArenaPart, ...]


def _cfg_flag(token: str) -> int:
    t = token.strip().upper()
    if t == "ON": return 1
    if t == "OFF": return 0
    try: return int(float(t))
    except ValueError as exc: raise ConvertError(f"bad cfg flag {token!r}") from exc


def parse_arena_cfg(cfg: bytes) -> ArenaCfg:
    """The cfg records parse_room_cfg leaves out, read as TEIGIMdsLoad/TEIGIAnalyz read them.

    DRANS_PARTS/DRANS_COLS are loaded in file order into the next free CDranMapField slot
    (itemdata.cpp:879-898, dranmapfield.cpp:13-57), so the i-th of each forms slot i. PT_CAM,
    PT_FIRE and PT_MARKER belong to the open DEF_PATS part (nowPartsCnt)."""
    text = cfg.decode("cp932", errors="replace")
    quoted = re.compile(r'^\s*\w+\s+"([^"\\]+)"\s*(?:,(.*))?$')
    fire = re.compile(r'^\s*PT_FIRE\s+' + r'\s*,\s*'.join([_CFG_NUM]*3) + r'\s*$', re.I)
    fire_img = None; models = []; collisions = []; parts = []; current = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("//", 1)[0]
        if not line.strip(): continue
        keyword = line.split()[0].upper()
        if keyword == "DEF_PATS":
            if current is not None: raise ConvertError(f"cfg line {number}: nested DEF_PATS")
            current = {"cameras": [], "fires": [], "dropped": [], "markers": []}
        elif keyword == "DEF_ENDS":
            if current is None: raise ConvertError(f"cfg line {number}: DEF_ENDS without DEF_PATS")
            parts.append(ArenaPart(len(parts), tuple(current["cameras"]), tuple(current["fires"]),
                                   tuple(current["dropped"]), tuple(current["markers"])))
            current = None
        elif keyword in ("FIRE_IMG", "DRANS_PARTS", "DRANS_COLS", "PT_CAM", "PT_MARKER"):
            m = quoted.match(line)
            if not m: raise ConvertError(f"cfg line {number}: malformed {keyword}")
            name = PurePosixPath(m.group(1)).name
            args = [a.strip() for a in (m.group(2) or "").split(",") if a.strip()]
            if keyword == "FIRE_IMG": fire_img = (name, number)
            elif keyword == "DRANS_PARTS": models.append((name, number))
            elif keyword == "DRANS_COLS": collisions.append((name, number))
            elif current is None: raise ConvertError(f"cfg line {number}: {keyword} outside DEF_PATS")
            elif keyword == "PT_CAM":
                if len(args) != 1: raise ConvertError(f"cfg line {number}: PT_CAM needs a turn")
                current["cameras"].append((name, int(float(args[0])), number))
            else:
                if len(args) < 2: raise ConvertError(f"cfg line {number}: PT_MARKER needs radius and script")
                try: radius = float(args[0]); script = int(float(args[1]))
                except ValueError as exc: raise ConvertError(f"cfg line {number}: malformed PT_MARKER") from exc
                flags = [_cfg_flag(a) for a in args[2:6]] + [None]*(4 - len(args[2:6]))
                current["markers"].append(ArenaMarker(name, radius, script, *flags, number))
        elif keyword == "PT_FIRE":
            m = fire.match(line)
            if not m: raise ConvertError(f"cfg line {number}: malformed PT_FIRE")
            if current is None: raise ConvertError(f"cfg line {number}: PT_FIRE outside DEF_PATS")
            if len(current["fires"]) < MAX_PART_FIRES:
                current["fires"].append((tuple(float(m.group(j)) for j in (1, 2, 3)), number))
            else:
                current["dropped"].append(number)
    if current is not None: raise ConvertError("cfg ends inside DEF_PATS")
    if len(models) > DRAN_FIELD_SLOTS or len(collisions) > DRAN_FIELD_SLOTS:
        raise ConvertError("more than twelve DRANS_PARTS or DRANS_COLS (CDranMapField has twelve slots)")
    return ArenaCfg(fire_img, tuple(models), tuple(collisions), tuple(parts))


@dataclass(frozen=True)
class MotDriver:
    frame: int      # MDS object the keys drive
    target: int     # material index for MOT_MATERIAL_ALPHA
    kind: int
    keys: tuple[tuple[int, tuple[float, float, float, float]], ...]


def parse_dc1_motion(data: bytes, object_count: int) -> list[MotDriver]:
    """Mot_File_List records (32-byte header, then key_count 32-byte Mot_Key; gameutil.hpp:222-262)
    chained while `more` is set, as CreateAnimeDataEX walks them."""
    pos = 0; out = []
    while True:
        head = checked_span(data, pos, 32, "motion record header")
        frame, target, kind, _unk, count, more = struct.unpack_from("<iiiIII", head, 0)
        if count > (len(data) - pos - 32) // 32: raise ConvertError("motion keys escape file")
        if kind in (MOT_ROTATION, MOT_SCALE, MOT_TRANSLATION, MOT_MATERIAL_ALPHA) and not 0 <= frame < object_count:
            raise ConvertError(f"motion drives object {frame} of {object_count}")
        keys = []; last = -1
        for k in range(count):
            at = pos + 32 + k*32
            kf = struct.unpack_from("<I", data, at)[0]; value = struct.unpack_from("<4f", data, at + 16)
            if kf < last or kf > MAX_MOT_FRAME: raise ConvertError("motion key frames not ascending")
            if not all(math.isfinite(v) for v in value): raise ConvertError("non-finite motion key")
            last = kf; keys.append((kf, value))
        if not keys: raise ConvertError("motion driver without keys")
        out.append(MotDriver(frame, target, kind, tuple(keys)))
        pos += 32 + count*32
        if not more: break
        if len(out) > MAX_OBJECTS*64: raise ConvertError("too many motion drivers")
    return out


def _mot_span(driver: MotDriver, time: float) -> tuple[int, int, float]:
    """(key, next key, t) as MotionProc picks them: SearchMotKey finds the last key at or before the
    whole frame and t runs linearly to the next key (gameutil.cpp:160-205). Before the first key the
    first key holds; after the last one the last key holds (MotionProc then leaves the frame as is)."""
    keys = driver.keys
    key = max((i for i, (kf, _) in enumerate(keys) if kf <= int(time)), default=0)
    if key + 1 >= len(keys) or time < keys[0][0]: return key, key, 0.0
    a, b = keys[key][0], keys[key + 1][0]
    return key, key + 1, (time - a)/(b - a)


def dc1_quaternion(value: tuple[float, ...]) -> tuple[float, float, float, float]:
    """A rotation key as the (w, x, y, z) unit quaternion QuatToMat turns into the frame's rotation:
    MotionProc negates element 0 first (gameutil.cpp:222-235) and QuatToMat reads it as w with
    elements 1..3 as x, y, z (frame.cpp:212-255). The matrix is the standard one, R*v for column v."""
    return (-value[0], value[1], value[2], value[3])


def quat_slerp(a: tuple[float, ...], b: tuple[float, ...], t: float) -> tuple[float, float, float, float]:
    """QuatSlerp (gameutil.cpp:115-155): shortest arc, linear when the arc is under ~2.6 degrees."""
    cosine = sum(x*y for x, y in zip(a, b))
    if cosine < 0.0: cosine = -cosine; b = tuple(-x for x in b)
    if 1.0 - cosine > 0.001:
        angle = math.acos(min(1.0, cosine)); inv = 1.0/math.sin(angle)
        fa = inv*math.sin((1.0 - t)*angle); fb = inv*math.sin(t*angle)
    else:
        fa = 1.0 - t; fb = t
    return tuple(fa*x + fb*y for x, y in zip(a, b))


def quat_matrix(q: tuple[float, ...]) -> tuple[float, ...]:
    w, x, y, z = q
    return (1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y), 0.0,
            2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x), 0.0,
            2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y), 0.0,
            0.0, 0.0, 0.0, 1.0)


def matrix_quat(m: tuple[float, ...]) -> tuple[float, float, float, float]:
    """Unit quaternion (w >= 0) of an orthonormal rotation block; rejects scale or shear."""
    cols = [(m[0], m[4], m[8]), (m[1], m[5], m[9]), (m[2], m[6], m[10])]
    for i in range(3):
        for j in range(3):
            d = sum(cols[i][k]*cols[j][k] for k in range(3))
            if abs(d - (1.0 if i == j else 0.0)) > 1e-3: raise ConvertError("animated frame is not a pure rotation")
    tr = m[0] + m[5] + m[10]
    if tr > 0:
        s = math.sqrt(tr + 1.0)*2; q = (0.25*s, (m[9]-m[6])/s, (m[2]-m[8])/s, (m[4]-m[1])/s)
    elif m[0] > m[5] and m[0] > m[10]:
        s = math.sqrt(1.0 + m[0] - m[5] - m[10])*2; q = ((m[9]-m[6])/s, 0.25*s, (m[1]+m[4])/s, (m[2]+m[8])/s)
    elif m[5] > m[10]:
        s = math.sqrt(1.0 + m[5] - m[0] - m[10])*2; q = ((m[2]-m[8])/s, (m[1]+m[4])/s, 0.25*s, (m[6]+m[9])/s)
    else:
        s = math.sqrt(1.0 + m[10] - m[0] - m[5])*2; q = ((m[4]-m[1])/s, (m[2]+m[8])/s, (m[6]+m[9])/s, 0.25*s)
    n = math.sqrt(sum(v*v for v in q)); q = tuple(v/n for v in q)
    return q if q[0] >= 0 else tuple(-v for v in q)


def pose_motion(objects: list[dict], drivers: list[MotDriver], time: float) -> tuple[list[tuple[float, ...]], dict]:
    """World matrices of every MDS object at a motion time, plus material alphas {(object, material): a}.

    Rotation keys replace the local rotation and keep its translation (CFrame::SetTransMatrix(float*),
    frame.cpp:557-564); translation keys replace local[3] (gameutil.cpp:256-272); material-alpha keys
    set diffuse alpha to 1 - value (gameutil.cpp:356-365). Undriven frames keep their MDS matrix."""
    local = [list(o["matrix"]) for o in objects]; alphas = {}
    for d in drivers:
        key, nxt, t = _mot_span(d, time)
        a = d.keys[key][1]; b = d.keys[nxt][1]
        if d.kind == MOT_ROTATION:
            qa, qb = dc1_quaternion(a), dc1_quaternion(b)
            q = quat_slerp(qa, qb, t) if 0.0001 < t < 0.9999 else (qb if t >= 0.9999 else qa)
            r = quat_matrix(q); m = local[d.frame]
            for row in range(3):
                for col in range(3): m[row*4 + col] = r[row*4 + col]
        elif d.kind == MOT_TRANSLATION:
            v = [a[i] + (b[i] - a[i])*t for i in range(3)] if 0.0001 < t < 0.9999 else (b if t >= 0.9999 else a)
            m = local[d.frame]; m[3], m[7], m[11] = v[0], v[1], v[2]
        elif d.kind == MOT_MATERIAL_ALPHA:
            alphas[(d.frame, d.target)] = 1.0 - ((1.0 - t)*a[0] + t*b[0])
        elif d.kind == MOT_SCALE:
            if any(abs(v - 1.0) > 1e-6 for _, k in d.keys for v in k[:3]): raise ConvertError("scale keys are not supported")
        else:
            raise ConvertError(f"unsupported motion key type {d.kind} for a field tile")
    world = []
    for i, o in enumerate(objects):
        m = tuple(local[i])
        world.append(m if o["parent"] < 0 else mat_mul(world[o["parent"]], m))
    return world, alphas


def parse_chr_info(text: str) -> dict:
    """The character info.cfg fields a field tile uses: MODEL, MOTION 0 files and its KEY list
    (KEY start, end, speed; chararead.cpp:399-413)."""
    model = re.search(r'^\s*MODEL\s+"([^"\\]+)"', text, re.M | re.I)
    motion = re.search(r'^\s*MOTION\s+0\s*,\s*"([^"\\]+)"', text, re.M | re.I)
    keys = [(int(a), int(b), float(c)) for a, b, c in
            re.findall(r'^\s*KEY\s+(\d+)\s*,\s*(\d+)\s*,\s*' + _CFG_NUM, text, re.M | re.I)]
    if not model or not motion or not keys: raise ConvertError("field tile info.cfg lacks MODEL, MOTION 0 or KEY")
    return {"model": PurePosixPath(model.group(1)).name, "motion": PurePosixPath(motion.group(1)).name, "keys": keys}


def _r(v: float) -> float:
    return round(v, 6) + 0.0


def build_field_tile(slot: int, chr_member: Member, col_member: Member, room_textures: list[str], scale: float) -> dict:
    """One CDranMapField slot: its model's objects in object-local units, the collapse motion baked per
    whole motion frame, and its collision (placed at the origin unturned, dranmapfield.cpp:13-57)."""
    chr_pack = parse_pack(chr_member.data)
    info = parse_chr_info(chr_pack["info.cfg"].data.decode("cp932", errors="replace")) if "info.cfg" in chr_pack else None
    if info is None: raise ConvertError(f"{chr_member.name} lacks info.cfg")
    if info["model"].casefold() not in chr_pack or info["motion"].casefold() not in chr_pack:
        raise ConvertError(f"{chr_member.name} lacks its model or motion")
    mds = chr_pack[info["model"].casefold()].data
    objects = parse_mds(mds)
    drivers = parse_dc1_motion(chr_pack[info["motion"].casefold()].data, len(objects))
    start, end, speed = info["keys"][0]
    if not 0 <= start < end <= MAX_MOT_FRAME or not (speed > 0 and math.isfinite(speed)):
        raise ConvertError(f"{chr_member.name}: invalid KEY {start},{end},{speed}")
    names = sorted(room_textures, key=str.casefold)
    groups, _ = parse_visual_mds(mds, (0.0, 0.0, 0.0), 0, {n: None for n in room_textures}, local=True)
    by_object = {}
    for g in groups:
        tex = names[g["material"]] if g["material"] >= 0 else None
        by_object.setdefault(g["object"], []).append({
            "texture": room_textures.index(tex) if tex is not None else -1, "mdt_material": g["mdt_material"],
            "vertices": [{"position": [_r(x*scale) for x in v["position"]], "normal": [_r(x) for x in v["normal"]],
                          "uv": [_r(x) for x in v["uv"]], "color": [_r(x) for x in v["color"]]} for v in g["vertices"]]})
    frames = list(range(start, end + 1))
    poses = [pose_motion(objects, drivers, float(f)) for f in frames]
    rest, _ = pose_motion(objects, [], 0.0)
    out_objects = []
    for i, o in enumerate(objects):
        if i not in by_object: continue
        mats = sorted({g["mdt_material"] for g in by_object[i]})
        out_objects.append({
            "index": i, "name": o["name"],
            "rest": {"t": [_r(rest[i][k]*scale) for k in (3, 7, 11)], "q": [_r(v) for v in matrix_quat(rest[i])]},
            "groups": by_object[i],
            "track": {"t": [[_r(w[i][k]*scale) for k in (3, 7, 11)] for w, _ in poses],
                      "q": [[_r(v) for v in matrix_quat(w[i])] for w, _ in poses],
                      "alpha": {str(m): [_r(a.get((i, m), 1.0)) for _, a in poses] for m in mats}}})
    records = collision_records(col_member.data, (0.0, 0.0, 0.0), 0)
    kinds = sorted({(attr or (0,))[0] for _, _, attr in records})
    return {"slot": slot, "ground_kind": kinds[0] if len(kinds) == 1 else kinds, "model": chr_member.name,
            "collision_model": col_member.name, "objects": out_objects,
            "collision": [[[_r(x*scale) for x in p] for p in tri] for _, tri, _ in records],
            "motion": {"frames": [start, end], "speed": speed, "done_at": DRAN_FIELD_DONE_AT,
                       "keys": [list(k) for k in info["keys"]], "drivers": len(drivers)}}


def fire_donor_position(part_offset: tuple[float, float, float], frame_turn: int, raw: tuple[float, float, float]) -> tuple[float, float, float]:
    """DrawFireFreeStyle's placement (dungeonmap.cpp:885-911): raw cfg units turn with the part's raw
    frame_turn[0] by 90*(4-turn) degrees, then join the part offset; DC1 draws at ten times that."""
    x, y, z = raw
    if frame_turn != 0:
        a = math.pi*(90.0*(4.0 - frame_turn))/180.0
        rot_x = -((-z*math.sin(a)) - x*math.cos(a)); rot_z = (-x*math.sin(a)) + z*math.cos(a)
    else:
        rot_x, rot_z = x, z
    return (10.0*(part_offset[0]/10.0 + rot_x), 10.0*(y + part_offset[1]/10.0), 10.0*(part_offset[2]/10.0 + rot_z))


FIRE_CELL_STEP = 0.4      # CFireOmni::FireStep: cell_phase -= 0.4, wraps to 14.8 at <= 0 (fireomni.cpp:27-41)
FIRE_CELL_WRAP = 14.8


def fire_flipbook(textures: dict[str, tuple[bytes, int, int]]) -> tuple[bytes, int, int, int]:
    """Bake CFireOmni::FireCreate's 'blender' flame for one cell cycle (37 steps of 0.4) into a
    128x128-per-frame atlas, 8 frames per row. Per step: the d01e03 strip at rows flame_phase..+64
    stretched to 128x128, then the d01e02 cell int(cell_phase) (4x4 grid of 64x64, bpp 1 branch)
    stretched over it with GS alpha (Cd*As + Cs) (fireomni.cpp:43-60, runeffect.cpp:24-80).
    Approximate: the second strip pass inherits mgAlpha, which is not traced; source-over assumed."""
    if "d01e02" not in textures or "d01e03" not in textures: raise ConvertError("fire.img lacks d01e02/d01e03")
    cells, cw, ch = textures["d01e02"]; noise, nw, nh = textures["d01e03"]
    if (cw, ch) != (256, 256) or nw != 128 or nh < 128 + 64: raise ConvertError("unexpected fire sheet sizes")
    steps = int(round(FIRE_CELL_WRAP/FIRE_CELL_STEP))
    cols = 8; rows = (steps + cols - 1)//cols; W = 128*cols; H = 128*rows
    out = bytearray(W*H*4)
    for k in range(steps):
        phase = FIRE_CELL_WRAP - FIRE_CELL_STEP*k; cell = int(phase + 1e-9); flame = k % 128
        cx, cy = (cell % 4)*64, (cell//4)*64; ox, oy = (k % cols)*128, (k//cols)*128
        for y in range(128):
            ny = flame + y//2
            for x in range(128):
                n = (ny*nw + x)*4; c = ((cy + y//2)*cw + cx + x//2)*4
                ca = cells[c + 3]/255.0
                px = ((oy + y)*W + ox + x)*4
                out[px:px+4] = bytes((min(255, int(cells[c] + noise[n]*ca + 0.5)), min(255, int(cells[c+1] + noise[n+1]*ca + 0.5)),
                                      min(255, int(cells[c+2] + noise[n+2]*ca + 0.5)), cells[c + 3]))
    return png_rgba(W, H, bytes(out)), W, H, steps


def _safe_stem(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]', '_', name)


def build_arena(room_pack: Path, pack_path: Path, cfg_path: Path) -> tuple[dict, dict[str, bytes]]:
    """arena.json for an existing v1 pack of a DC1 room with Dran field tiles, PT_FIRE, PT_CAM and full
    PT_MARKER records, in the pack's output units; returns (doc, {relative path: file bytes})."""
    room = validate_pack(room_pack)
    scale = float(room["units"]["scale"]); name = room["donor"]["room"]
    pack_bytes = pack_path.read_bytes(); cfg_bytes = cfg_path.read_bytes()
    members = parse_pack(pack_bytes); room_cfg = parse_room_cfg(cfg_bytes); arena = parse_arena_cfg(cfg_bytes)
    if len(arena.parts) != len(room_cfg.parts): raise ConvertError("part count disagrees between cfg readers")
    if len(arena.field_models) != len(arena.field_collisions):
        raise ConvertError("DRANS_PARTS and DRANS_COLS counts differ")
    room_textures = [t["name"] for t in room["textures"]]
    files: dict[str, bytes] = {}
    tiles = []
    for slot, ((model, mline), (col, cline)) in enumerate(zip(arena.field_models, arena.field_collisions)):
        if model.casefold() not in members or col.casefold() not in members:
            raise ConvertError(f"field slot {slot}: {model} or {col} is missing from the pack")
        tile = build_field_tile(slot, members[model.casefold()], members[col.casefold()], room_textures, scale)
        tile["cfg_lines"] = [mline, cline]
        if tile["ground_kind"] != slot + 1:
            raise ConvertError(f"field slot {slot}: collision ground_kind {tile['ground_kind']} is not {slot + 1}")
        tiles.append(tile)
    # Fires: one record per PT_FIRE, in part order (DrawFireFreeStyle walks parts, then fires).
    fires = []
    for part in arena.parts:
        frame = room_cfg.parts[part.index].frames[0]
        for j, (raw, line) in enumerate(part.fires):
            donor = fire_donor_position(frame.offset, frame.turn, raw)
            fires.append({"id": f"fire-{len(fires)}", "part": part.index, "part_frame": frame.name, "cfg_line": line,
                          "raw": list(raw), "donor": [_r(v) for v in donor], "position": [_r(v*scale) for v in donor],
                          "param": FIRE_PARAM})
    fire_doc = None
    if arena.fire_img is not None:
        img_name = arena.fire_img[0]
        img = members.get(img_name.casefold()) or members.get("fire.img")
        if img is None: raise ConvertError("FIRE_IMG is missing from the pack")
        raw_tex = decode_img_rgba(img.data, rgba32=True)
        tex_files = {}
        for tex, (rgba, w, h) in sorted(raw_tex.items(), key=lambda kv: kv[0].casefold()):
            rel = f"arena/fire/{_safe_stem(tex)}.png"; files[rel] = png_rgba(w, h, rgba); tex_files[tex] = rel
        book, bw, bh, steps = fire_flipbook(raw_tex)
        files["arena/fire/flame_flipbook.png"] = book
        fire_doc = {"image": img.name, "cfg_line": arena.fire_img[1], "textures": tex_files,
                    "flipbook": {"file": "arena/fire/flame_flipbook.png", "frame_size": [128, 128], "columns": 8,
                                 "frames": steps, "steps_per_frame": 1, "approximate": True},
                    "draw": {"offset_y": _r(4.6*scale), "blend": "additive (Cs*As + Cd)", "depth_test": True, "depth_write": False,
                             "layers": [{"layer": 1, "textures": ["lightling", "flame"], "size": [_r(18.0*scale), _r(9.0*scale)]},
                                        {"layer": 2, "textures": ["lightling"], "size": [_r(45.0*scale), _r(22.5*scale)],
                                         "flicker": {"every_steps": 5, "scale_max": 1.1}, "depth_bias_toward_camera": _r(15.0*scale)}],
                             "sound": {"se": "SE_AMBIENT_CAVE_DRIPS", "nearest_within": _r(300.0*scale)}}}
    # Camera collision (PT_CAM): placed like the part, turned by frame_turn[0] + PT_CAM turn
    # (gameloop.cpp:8506-8536).
    cameras = []
    for part in arena.parts:
        frame = room_cfg.parts[part.index].frames[0]
        for model, turn, line in part.cameras:
            if model.casefold() not in members: raise ConvertError(f"PT_CAM model {model} is missing")
            k = dc1_turn(frame.turn + turn)
            records = collision_records(members[model.casefold()].data, frame.offset, k)
            by_obj = {}
            for obj, tri, _ in records: by_obj.setdefault(obj, []).append([[_r(x*scale) for x in p] for p in tri])
            cameras.append({"part": part.index, "model": model, "cfg_line": line, "turn": k,
                            "objects": [{"name": o, "triangles": t} for o, t in by_obj.items()]})
    # Markers with their full DC1 record; positions from the part's placed, turned PT_COLS frame.
    markers = []
    for part in arena.parts:
        rpart = room_cfg.parts[part.index]
        if not part.markers: continue
        if rpart.collision is None: raise ConvertError(f"part {part.index} has PT_MARKER without PT_COLS")
        data = members[rpart.collision[0].casefold()].data
        k = part_collision_turn(rpart)
        objs = parse_mds(data); mats = world_matrices(objs, rpart.frames[0].offset, k)
        for mk in part.markers:
            hits = [m for o, m in zip(objs, mats) if o["name"].casefold() == mk.name.casefold()]
            if len(hits) != 1: raise ConvertError(f"marker {mk.name} matches {len(hits)} collision frames")
            m = hits[0]; donor = (m[3], m[7], m[11])
            ground = ground_under(room["collision"], tuple(v*scale for v in donor), 2.0*scale, 20.0*scale)
            markers.append({"name": mk.name, "part": part.index, "cfg_line": mk.line, "script": mk.script,
                            "radius": mk.radius, "item_use": mk.item_use, "auto_start": mk.auto_start,
                            "switch_on": mk.switch_on, "ext_mem": mk.ext_mem,
                            "donor": [_r(v) for v in donor], "position": [_r(v*scale) for v in donor],
                            "ground_y": None if ground is None else _r(ground),
                            "facing_y": _r(math.atan2(m[2], m[10])),
                            "trigger": {"horizontal_radius": _r((mk.radius + 10.0)*scale), "height_window": _r(40.0*scale)}})
    # Floor support on the straight spawn -> enemy -> exit line, as convert reports it (5 output units
    # per sample, +-2 donor units), without and with the intact tiles.
    route = [room[k] for k in ("spawn", "enemy_spawn", "exit")]
    tile_collision = [tri for t in tiles for tri in t["collision"]]
    before = route_support(room["collision"], route, 5.0, 2.0*scale, 2.0*scale)
    after = route_support(room["collision"] + tile_collision, route, 5.0, 2.0*scale, 2.0*scale)
    room_bytes = (room_pack/"room.json").read_bytes()
    doc = {"format": ARENA_FORMAT, "version": 1, "room": name,
           "room_json_sha256": hashlib.sha256(room_bytes).hexdigest(), "units": {"scale": scale},
           "sources": [{"path": pack_path.name, "sha256": hashlib.sha256(pack_bytes).hexdigest()},
                       {"path": cfg_path.name, "sha256": hashlib.sha256(cfg_bytes).hexdigest()}],
           "field_tiles": {
               "rule": {"slots": DRAN_FIELD_SLOTS, "initial_state": 3, "reset": "every floor load",
                        "states": [{"state": 3, "draw": True, "collision": True, "on_hit": 2},
                                   {"state": 2, "draw": True, "collision": True, "on_step": 1, "sound": "SE_DRAN_FIELD_START"},
                                   {"state": 1, "draw": True, "collision": False, "motion": "play", "to_state_0_when_time_ge": DRAN_FIELD_DONE_AT},
                                   {"state": 0, "draw": False, "collision": False}],
                        "hit": {"by": "projectile map hit (checkCollision)", "ground_kind_to_slot": "slot = ground_kind - 1",
                                "decrement_when_state_ge": 2},
                        "fall": {"below_y": _r(-30.0*scale), "life": -40, "script": 5}},
               "tiles": tiles},
           "fires": {"emitters": fires, "dropped_cfg_lines": [l for p in arena.parts for l in p.dropped_fires], **(fire_doc or {})},
           "camera_collision": cameras, "markers": markers,
           "floor_support": {"route": "spawn->enemy_spawn->exit", "step": 5.0, "room_only": list(before), "with_tiles": list(after)}}
    return doc, files


def validate_arena(room_pack: Path) -> dict:
    """Structural checks of arena.json against the room it was built for."""
    room = validate_pack(room_pack)
    try: doc = json.loads((room_pack/"arena.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc: raise ConvertError("cannot read arena.json") from exc
    if not isinstance(doc, dict) or doc.get("format") != ARENA_FORMAT or doc.get("version") != 1: raise ConvertError("unsupported arena sidecar")
    if doc.get("room") != room["donor"]["room"]: raise ConvertError("arena.json is for another room")
    if doc.get("room_json_sha256") != hashlib.sha256((room_pack/"room.json").read_bytes()).hexdigest():
        raise ConvertError("arena.json was built against a different room.json")
    def vec(v, n, label):
        if not isinstance(v, list) or len(v) != n or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v):
            raise ConvertError(f"invalid {label}")
        return v
    def safe_file(rel):
        p = PurePosixPath(rel) if isinstance(rel, str) else PurePosixPath("")
        if not isinstance(rel, str) or not rel or p.is_absolute() or ".." in p.parts or "\\" in rel or ":" in rel: raise ConvertError("unsafe arena file path")
        f = room_pack/Path(*p.parts)
        if not f.is_file(): raise ConvertError(f"arena file {rel} is missing")
        validate_png(f.read_bytes())
    tiles = doc.get("field_tiles", {}).get("tiles")
    if not isinstance(tiles, list) or len(tiles) > DRAN_FIELD_SLOTS: raise ConvertError("invalid field tile list")
    ntex = len(room["textures"])
    for i, t in enumerate(tiles):
        if t.get("slot") != i or t.get("ground_kind") != i + 1: raise ConvertError("field tiles must be slots 0.. with ground_kind slot+1")
        frames = t["motion"]["frames"]; n = frames[1] - frames[0] + 1
        if not t.get("objects") or not t.get("collision"): raise ConvertError("field tile without objects or collision")
        for o in t["objects"]:
            vec(o["rest"]["t"], 3, "rest translation"); vec(o["rest"]["q"], 4, "rest rotation")
            if len(o["track"]["t"]) != n or len(o["track"]["q"]) != n: raise ConvertError("track length differs from motion frames")
            for q in o["track"]["q"]:
                if abs(math.sqrt(sum(x*x for x in vec(q, 4, "track rotation"))) - 1.0) > 1e-4: raise ConvertError("track rotation is not unit")
            for t3 in o["track"]["t"]: vec(t3, 3, "track translation")
            for a in o["track"]["alpha"].values():
                if len(a) != n or any(not 0.0 <= x <= 1.0 for x in a): raise ConvertError("invalid alpha track")
            for g in o["groups"]:
                if type(g["texture"]) is not int or not -1 <= g["texture"] < ntex: raise ConvertError("tile texture index out of range")
                if not g["vertices"] or len(g["vertices"]) % 3: raise ConvertError("tile vertices must be triangle lists")
                if str(g["mdt_material"]) not in o["track"]["alpha"]: raise ConvertError("group material has no alpha track")
                for v in g["vertices"]:
                    vec(v["position"], 3, "tile position"); vec(v["normal"], 3, "tile normal"); vec(v["uv"], 2, "tile uv")
                    if any(not 0.0 <= c <= 1.0 for c in vec(v["color"], 4, "tile colour")): raise ConvertError("tile colour outside 0..1")
        for tri in t["collision"]:
            if not isinstance(tri, list) or len(tri) != 3: raise ConvertError("tile collision entry must be a triangle")
            for p in tri: vec(p, 3, "tile collision vertex")
    fires = doc.get("fires", {})
    for f in fires.get("emitters", []): vec(f["position"], 3, "fire position")
    for rel in list(fires.get("textures", {}).values()) + ([fires["flipbook"]["file"]] if "flipbook" in fires else []): safe_file(rel)
    for c in doc.get("camera_collision", []):
        for o in c["objects"]:
            for tri in o["triangles"]:
                for p in tri: vec(p, 3, "camera collision vertex")
    for m in doc.get("markers", []): vec(m["position"], 3, "marker position")
    return doc


def write_arena(room_pack: Path, doc: dict, files: dict[str, bytes]) -> Path:
    target = room_pack/"arena.json"
    if target.exists() or (room_pack/"arena").exists(): raise ConvertError("arena.json or arena/ already exists; choose another pack")
    for rel, data in files.items():
        p = room_pack/Path(*PurePosixPath(rel).parts); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    staging = room_pack/"arena.json.tmp"
    staging.write_text(json.dumps(doc, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    os.replace(staging, target)
    validate_arena(room_pack)
    return target


# ---------------------------------------------------------------------------------------------
# Random floors ("floor" mode)
#
# DC1's random dungeon floors are one 20x20 grid of kit parts (CDungeonMap::cells). Cell (col, row)
# is drawn and collided at (160*col, 0, 160*row) (dungeonmap.cpp:316-320, dungeonparts.cpp:2337).
# The grid itself is produced by the real generator and dumped by the port's randfloor_dump tool
# (format "ixion-dc1-randfloor", see docs/room-converter.md); this mode only places kit parts.
# ---------------------------------------------------------------------------------------------

FLOOR_FORMAT = "ixion-dc1-randfloor"
FLOOR_CELL = 160.0
FLOOR_PLAYABLE = 16
FLOOR_PARTS_NONE = -1
PART_STAIR_DOWN = 30    # "Stair that the player comes in by" (dungeonparts.hpp:66)
PART_STAIR_UP = 31      # "Stair that the player leaves by" (dungeonparts.hpp:67)
PART_URA_ROAD = 44
# BuildCellFlag, ps2/src/dungeonmap.cpp:38-49.
BUILD_ROOM, BUILD_CORRIDOR, BUILD_DOOR, BUILD_HEAL_SPRING = 0x001, 0x002, 0x004, 0x008
BUILD_DIVIDING_WALL, BUILD_DIVIDING_DOOR, BUILD_PILLAR = 0x010, 0x020, 0x040
BUILD_STAIR_DOWN, BUILD_STAIR_UP, BUILD_URA_ENTRANCE, BUILD_ROOM_LINK = 0x080, 0x100, 0x200, 0x400


def load_floor_dump(source) -> dict:
    """Read and validate a randfloor_dump JSON (a path or an already parsed object)."""
    if isinstance(source,(str,Path)):
        try: dump=json.loads(Path(source).read_text(encoding="utf-8"))
        except (OSError,UnicodeError,json.JSONDecodeError) as exc: raise ConvertError("cannot read floor dump") from exc
    else: dump=source
    if not isinstance(dump,dict) or dump.get("format")!=FLOOR_FORMAT or dump.get("version")!=1:
        raise ConvertError("not an ixion-dc1-randfloor v1 dump")
    grid=dump.get("grid")
    if not isinstance(grid,dict) or (grid.get("width"),grid.get("height"),grid.get("cell_size"))!=(20,20,160):
        raise ConvertError("unsupported floor grid")
    for key,lo,hi in (("parts_no",-1,255),("direction",0,3),("content",0,0xFFFF),("room_links",0,0xFFFF)):
        values=dump.get(key)
        if not isinstance(values,list) or len(values)!=400 or any(type(v) is not int or v<lo or v>hi for v in values):
            raise ConvertError(f"floor dump {key} must be 400 integers in {lo}..{hi}")
    if not isinstance(dump.get("map_seed"),int) or not isinstance(dump.get("floor"),int):
        raise ConvertError("floor dump lacks map_seed or floor")
    for key,part in (("stair_down",PART_STAIR_DOWN),("stair_up",PART_STAIR_UP)):
        at=dump.get(key)
        if (not isinstance(at,dict) or type(at.get("col")) is not int or type(at.get("row")) is not int
                or not 0<=at["col"]<20 or not 0<=at["row"]<20):
            raise ConvertError(f"floor dump lacks a valid {key}")
        if dump["parts_no"][at["row"]*20+at["col"]]!=part:
            raise ConvertError(f"floor dump {key} cell does not hold part {part}")
    block=dump.get("monsters")
    if block is not None:
        if not isinstance(block,dict) or not isinstance(block.get("available"),bool): raise ConvertError("floor dump monsters must be an object with available")
        if block["available"]:
            lst=block.get("list")
            if not isinstance(lst,list) or not isinstance(block.get("model_nos"),list) or type(block.get("requested")) is not int or not isinstance(block.get("source"),str):
                raise ConvertError("floor dump monsters lacks list, model_nos, requested or source")
            seen=set()
            for m in lst:
                ints=("slot","monster_no","drops_items","holds_gate_key")
                if (not isinstance(m,dict) or any(type(m.get(k)) is not int for k in ints) or not isinstance(m.get("model"),str)
                        or any(not isinstance(m.get(k),(int,float)) or isinstance(m.get(k),bool) or not math.isfinite(m[k]) for k in ("x","y","z","lift"))):
                    raise ConvertError("floor dump monster entry is malformed")
                if not 0<=m["slot"]<16 or m["slot"] in seen: raise ConvertError("floor dump monster slot is out of range or repeated")
                if not (0<=m["x"]<=FLOOR_CELL*FLOOR_PLAYABLE and 0<=m["z"]<=FLOOR_CELL*FLOOR_PLAYABLE): raise ConvertError("floor dump monster lies outside the playable grid")
                seen.add(m["slot"])
            holders=[m for m in lst if m["holds_gate_key"]]
            gate=dump.get("gate_key")
            if len(holders)>1 or (holders and (not isinstance(gate,dict) or gate.get("holder_slot")!=holders[0]["slot"])):
                raise ConvertError("floor dump gate key holder does not match the monster list")
    return dump


def floor_placements(dump: dict, part_count: int, include_under_road: bool=False) -> list[dict]:
    """Occupied cells in row-major order. The 16x16 playable area only, unless asked otherwise:
    column 19 holds the back floor's road (CDungeonMap::SetUnderLoad, dungeonmap.cpp:3049-3054)."""
    out=[]
    for row in range(20):
        for col in range(20):
            part=dump["parts_no"][row*20+col]
            if part==FLOOR_PARTS_NONE: continue
            if not include_under_road and (col>=FLOOR_PLAYABLE or row>=FLOOR_PLAYABLE): continue
            if part>=part_count: raise ConvertError(f"cell ({col},{row}) uses part {part} but the kit has {part_count}")
            out.append({"col":col,"row":row,"parts_no":part,"direction":dump["direction"][row*20+col],
                        "content":dump["content"][row*20+col]})
    return out


def floor_grid_path(dump: dict, start: tuple[int,int], goal: tuple[int,int]) -> list[tuple[int,int]] | None:
    """Shortest cell path from start to goal over the generator's own build flags.

    A cell is open if it holds a part and no dividing wall. A room cell and a corridor or stair
    cell join only through a door cell: mapPartsFilter walls a corridor off from a bare room cell
    (dungeonmap.cpp:1424-1460), and a door is a cell flagged BUILD_DOOR."""
    content=dump["content"]; parts=dump["parts_no"]
    def open_cell(col,row):
        if not (0<=col<FLOOR_PLAYABLE and 0<=row<FLOOR_PLAYABLE): return False
        i=row*20+col
        return parts[i]!=FLOOR_PARTS_NONE and not (content[i]&BUILD_DIVIDING_WALL)
    def bare_room(i): return (content[i]&(BUILD_ROOM|BUILD_DOOR))==BUILD_ROOM
    def joins(a,b):
        # a room cell and a non-room cell are separated by a wall unless the non-room one is a door.
        ra,rb=bare_room(a),bare_room(b)
        return not (ra!=rb and not ((content[a]|content[b])&(BUILD_DOOR|BUILD_URA_ENTRANCE)))
    if not open_cell(*start) or not open_cell(*goal): return None
    came={start:None}; queue=[start]
    for cur in queue:
        if cur==goal: break
        for dc,dr in ((0,1),(1,0),(0,-1),(-1,0)):
            nxt=(cur[0]+dc,cur[1]+dr)
            if nxt in came or not open_cell(*nxt): continue
            if not joins(cur[1]*20+cur[0],nxt[1]*20+nxt[0]): continue
            came[nxt]=cur; queue.append(nxt)
    if goal not in came: return None
    path=[]; cur=goal
    while cur is not None: path.append(cur); cur=came[cur]
    return path[::-1]


_ASCII_CLASS=([(range(0,5),"+"),(range(5,9),"#"),(range(9,13),"D"),(range(13,17),"#"),(range(17,18),"."),
               (range(18,22),"w"),(range(22,26),"d"),(range(26,30),"w"),(range(30,31),"S"),(range(31,32),"X"),
               (range(32,36),"H"),(range(36,40),"G"),(range(40,44),"U"),(range(44,45)," "),(range(45,47),"o"),
               (range(47,53),"D"),(range(53,70),"K")])


def floor_ascii(dump: dict, path: list[tuple[int,int]] | None=None) -> str:
    """Top-down text render of the 16x16 playable grid (north = top, east = right).

    + corridor, # room wall or corner, . room floor, D door, G room gate, w/d divider wall/door,
    S stair in (entrance), X stair out (exit), U back-floor entrance, H heal spring, o pillar,
    K key part, * path cell. Blank = no part."""
    on_path=set(path or ())
    rows=[]
    for row in range(FLOOR_PLAYABLE):
        line=[]
        for col in range(FLOOR_PLAYABLE):
            part=dump["parts_no"][row*20+col]
            ch=" " if part==FLOOR_PARTS_NONE else next((c for r,c in _ASCII_CLASS if part in r),"?")
            if (col,row) in on_path and ch in "+.D": ch="*"
            line.append(ch)
        rows.append("".join(line).rstrip())
    return "\n".join(rows)


class GroundIndex:
    """Walkable collision triangles (|normal.y| >= WALKABLE_NY) bucketed on the xz plane."""
    def __init__(self, collision: list, bucket: float=40.0):
        self.bucket=bucket; self.cells={}
        for tri in collision:
            (x1,y1,z1),(x2,y2,z2),(x3,y3,z3)=tri
            nx=(y2-y1)*(z3-z1)-(z2-z1)*(y3-y1); ny=(z2-z1)*(x3-x1)-(x2-x1)*(z3-z1); nz=(x2-x1)*(y3-y1)-(y2-y1)*(x3-x1)
            length=math.sqrt(nx*nx+ny*ny+nz*nz)
            if not length or abs(ny)/length<WALKABLE_NY: continue
            xs=(x1,x2,x3); zs=(z1,z2,z3)
            for ix in range(int(math.floor(min(xs)/bucket)),int(math.floor(max(xs)/bucket))+1):
                for iz in range(int(math.floor(min(zs)/bucket)),int(math.floor(max(zs)/bucket))+1):
                    self.cells.setdefault((ix,iz),[]).append(tri)

    def heights(self, x: float, z: float) -> list[float]:
        return ground_heights(self.cells.get((int(math.floor(x/self.bucket)),int(math.floor(z/self.bucket))),()),x,z)

    def ground(self, point: tuple[float,float,float], rise: float, drop: float) -> float | None:
        c=[y for y in self.heights(point[0],point[2]) if point[1]-drop<=y<=point[1]+rise]
        return max(c) if c else None


def walk_support(index: GroundIndex, polyline: list[tuple[float,float,float]], step: float, rise: float, drop: float) -> dict:
    """Walk a polyline in xz every `step` units, following the ground as a body would: at each
    sample take the walkable surface nearest the previous height within +rise/-drop. A sample with
    none is void (height is held). Returns sample and void counts and the first void position."""
    y=polyline[0][1]; samples=void=0; first=None; longest=run=0; track=[]
    for a,b in zip(polyline,polyline[1:]):
        n=max(1,int(math.ceil(math.dist((a[0],a[2]),(b[0],b[2]))/step)))
        for i in range(1 if samples else 0,n+1):
            t=i/n; x=a[0]+(b[0]-a[0])*t; z=a[2]+(b[2]-a[2])*t
            c=[h for h in index.heights(x,z) if y-drop<=h<=y+rise]
            samples+=1
            if c:
                y=min(c,key=lambda h:abs(h-y)); run=0
            else:
                void+=1; run+=1; longest=max(longest,run)
                if first is None: first=[x,y,z]
            track.append((x,y,z))
    return {"samples":samples,"void":void,"longest_void_run":longest,"first_void":first,"track":track}


class WallIndex:
    """Steep collision triangles (|normal.y| < WALKABLE_NY: walls and posts), bucketed on xz."""
    def __init__(self, collision: list, bucket: float=40.0):
        self.bucket=bucket; self.cells={}
        for tri in collision:
            (x1,y1,z1),(x2,y2,z2),(x3,y3,z3)=tri
            nx=(y2-y1)*(z3-z1)-(z2-z1)*(y3-y1); ny=(z2-z1)*(x3-x1)-(x2-x1)*(z3-z1); nz=(x2-x1)*(y3-y1)-(y2-y1)*(x3-x1)
            length=math.sqrt(nx*nx+ny*ny+nz*nz)
            if not length or abs(ny)/length>=WALKABLE_NY: continue
            xs=(x1,x2,x3); zs=(z1,z2,z3)
            for ix in range(int(math.floor(min(xs)/bucket)),int(math.floor(max(xs)/bucket))+1):
                for iz in range(int(math.floor(min(zs)/bucket)),int(math.floor(max(zs)/bucket))+1):
                    self.cells.setdefault((ix,iz),[]).append(tri)

    def crosses(self, a: tuple[float,float,float], b: tuple[float,float,float]) -> int:
        """Steep triangles that the segment a-b passes through (Moller-Trumbore, 3D)."""
        d=(b[0]-a[0],b[1]-a[1],b[2]-a[2]); seen=set(); hits=0; k=self.bucket
        for ix in range(int(math.floor(min(a[0],b[0])/k)),int(math.floor(max(a[0],b[0])/k))+1):
            for iz in range(int(math.floor(min(a[2],b[2])/k)),int(math.floor(max(a[2],b[2])/k))+1):
                for tri in self.cells.get((ix,iz),()):
                    if id(tri) in seen: continue
                    seen.add(id(tri))
                    p0,p1,p2=tri
                    e1=(p1[0]-p0[0],p1[1]-p0[1],p1[2]-p0[2]); e2=(p2[0]-p0[0],p2[1]-p0[1],p2[2]-p0[2])
                    h=(d[1]*e2[2]-d[2]*e2[1],d[2]*e2[0]-d[0]*e2[2],d[0]*e2[1]-d[1]*e2[0])
                    det=e1[0]*h[0]+e1[1]*h[1]+e1[2]*h[2]
                    if abs(det)<1e-9: continue
                    s=(a[0]-p0[0],a[1]-p0[1],a[2]-p0[2]); u=(s[0]*h[0]+s[1]*h[1]+s[2]*h[2])/det
                    if u<0 or u>1: continue
                    q=(s[1]*e1[2]-s[2]*e1[1],s[2]*e1[0]-s[0]*e1[2],s[0]*e1[1]-s[1]*e1[0])
                    v=(d[0]*q[0]+d[1]*q[1]+d[2]*q[2])/det
                    if v<0 or u+v>1: continue
                    t=(e2[0]*q[0]+e2[1]*q[1]+e2[2]*q[2])/det
                    if 0<=t<=1: hits+=1
        return hits


def wall_crossings(walls: WallIndex, track: list[tuple[float,float,float]], lifts: tuple[float,...]=(8.0,24.0)) -> dict:
    """Steep triangles crossed by the walked track at body heights (ground + each lift)."""
    hits=0; first=None
    for a,b in zip(track,track[1:]):
        for lift in lifts:
            n=walls.crosses((a[0],a[1]+lift,a[2]),(b[0],b[1]+lift,b[2]))
            if n and first is None: first=[a[0],a[1]+lift,a[2]]
            hits+=n
    return {"wall_crossings":hits,"first_wall_crossing":first,"lifts":list(lifts)}


def _rounded(groups: list) -> list:
    """Floor packs repeat each kit mesh once per cell, so attributes are written to fixed decimals
    (normals and UVs to 5 places, colours to 4) to keep room.json small."""
    return [{"material":g["material"],"vertices":[{"position":v["position"],"normal":[round(c,5) for c in v["normal"]],
                                                   "uv":[round(c,5) for c in v["uv"]],"color":[round(c,4) for c in v["color"]]}
                                                  for v in g["vertices"]]} for g in groups]


def _translated(groups: list, dx: float, dz: float, scale: float) -> list:
    return [{"material":g["material"],"vertices":[{"position":[round((v["position"][0]+dx)*scale,4),round(v["position"][1]*scale,4),round((v["position"][2]+dz)*scale,4)],
                                                   "normal":v["normal"],"uv":v["uv"],"color":v["color"]} for v in g["vertices"]]} for g in groups]



# ---- RANDFLOOR-R2: chests, DC1's own monster arrangement, the gate key rule ---------------------
# DC1 monster models that have a converted donor in the roster overlay (ROSTER-R1.md section 3:
# packs/roster-<id>, DC2_IXION_ROOM_DONOR_MONSTER accepts these). Anything else in a floor's
# arrangement (the Cave Bat e60a, Statue Dog e103a) is kept in floor.json but not requested.
ROSTER_DONOR_IDS = ("e03a","e06a","e35a","e05a","e59a","e01a","e101a","e77a")
ROSTER_MAX_KINDS = 8
# DC1 chest item -> DC2 item. DC2 item numbers are rows of menu/cfg7/comdat.cfg, names from
# comdatmes1.cfg (PAL). "equivalent" = the same thing by name and role. "stand-in" = nearest role.
# 195 is the floor's gate key; the DC2 adapter's own table maps it to the native gate key (337), so
# the entry only documents it.
CHEST_ITEMS = {
    195: (337,"built-in","Dran's Crest","Key Handle"),
    233: (305,"equivalent","Map","Map"),
    234: (306,"equivalent","Magical Crystal","Magic Crystal"),
    145: (425,"stand-in","Regular Water","Tasty Water"),
    146: (425,"equivalent","Tasty Water","Tasty Water"),
    147: (425,"stand-in","Premium Water","Tasty Water"),
    148: (268,"equivalent","Bread","Bread"),
    149: (270,"equivalent","Premium Chicken","Premium Chicken"),
    150: (274,"equivalent","Stamina Drink","Stamina Drink"),
    151: (275,"equivalent","Antidote Drink","Antidote Drink"),
    152: (276,"equivalent","Holy Water","Holy Water"),
    155: (269,"equivalent","Cheese","Cheese"),
    166: (287,"equivalent","Throbbing Cherry","Heart-Throb Cherry"),
    167: (289,"equivalent","Gooey Peach","Gooey Peach"),
    169: (291,"equivalent","Poisonous Apple","Poison Apple"),
    170: (292,"equivalent","Mellow Banana","Mellow Banana"),
}
CHEST_FALLBACK = (268,"stand-in",None,"Bread")
DC2_ITEM_MAX = 428


def chest_mapping(dc1_item: int) -> dict:
    """The DC2 item a DC1 chest item becomes, how it was chosen, and both names where known."""
    dc2,relation,dc1_name,dc2_name=CHEST_ITEMS.get(dc1_item,CHEST_FALLBACK)
    return {"dc1_item":dc1_item,"dc2_item":dc2,"relation":relation if dc1_item in CHEST_ITEMS else "stand-in (fallback: item has no authored mapping)",
            "dc1_name":dc1_name,"dc2_name":dc2_name}


def floor_monsters(dump: dict, index: "GroundIndex", scale: float) -> dict | None:
    """DC1's ArrangementPos result for the floor (the dump's `monsters`), grounded on the pack's
    collision and in output units. None when the dump carries none (an R1 dump)."""
    block=dump.get("monsters")
    if not isinstance(block,dict) or not block.get("available"): return None
    records=[]
    for m in block["list"]:
        x=m["x"]; z=m["z"]; h=index.heights(x,z)
        records.append({"slot":m["slot"],"monster_no":m["monster_no"],"model":m["model"],
                        "col":int(round(x/FLOOR_CELL)),"row":int(round(z/FLOOR_CELL)),"lift":m["lift"],
                        "donor":[x,m["y"],z],"output":[x*scale,(floor_height(h) if h else 0.0)*scale,z*scale],
                        "grounded":bool(h),"drops_items":m["drops_items"],"holds_gate_key":bool(m["holds_gate_key"]),
                        "roster_donor":m["model"] in ROSTER_DONOR_IDS})
    models=[]
    for r in records:
        if r["roster_donor"] and r["model"] not in models: models.append(r["model"])
    return {"source":block["source"],"requested":block["requested"],"placed":len(records),"model_nos":block["model_nos"],
            "list":records,
            "roster":{"supported":models[:ROSTER_MAX_KINDS],"donor_list":",".join(models[:ROSTER_MAX_KINDS]),
                      "unsupported_models":sorted({r["model"] for r in records if not r["roster_donor"]}),
                      "note":"DC2_IXION_ROOM_DONOR_MONSTER takes donor_list; props.json monster_spawn entries place each listed kind at its DC1 cell"}}


def floor_gate_key(dump: dict, monsters: dict | None) -> dict:
    """DC1's gate key rule as data (CMonstorUnit::SetKey, monstorunit.cpp:454-537): one random live
    monster that can drop items holds the key from the moment of arrangement. DC2's own rule (the key
    drops on any death, monster.cpp:2860-2870) is not selected here: that requires an explicit runtime policy."""
    key={"item_no":dump.get("gate_key_no"),"rule":"dc1: one arranged monster holds the key, chosen at arrangement",
         "runtime_use":"none: runtime policy required (DC1 rule vs DC2 drop-on-any-death)"}
    block=dump.get("gate_key")
    if isinstance(block,dict) and monsters is not None:
        holder=next((r for r in monsters["list"] if r["slot"]==block.get("holder_slot")),None)
        key["holder_slot"]=block.get("holder_slot"); key["holder"]=holder
        key["holder_roster_donor"]=bool(holder and holder["roster_donor"])
    return key


def floor_props(name: str, room_sha256: str, scale: float, sources: list, chests: list, monsters: dict | None,
                spawn: tuple[float,float,float] | None=None) -> dict:
    """The props.json sidecar of a floor pack (format ixion-room-props v1, read by the DC2 adapter):
    DC1's chests at their cells with mapped DC2 items, and DC1's monster arrangement. DC2's floor has
    only a few free monster slots, so the monster entries are ordered nearest the player's entrance
    first (ties by DC1 slot): that order is the adapter's spawn priority and the first listed model of
    a roster kind is the primary donor."""
    props=[]; deferred=[]
    for i,box in enumerate(chests):
        if not box["grounded"]: deferred.append({"kind":"treasure_box","index":i,"reason":"no walkable ground under the chest"}); continue
        m=box["dc2"]
        props.append({"id":f"treasure_box-{i}","kind":"treasure_box","position":[round(c,3) for c in box["output"]],"rotation_y":0.0,
                      "donor":{"op":"CDungeonMap::buildEventData SetTreasureBox","position":[box["x"],box["y"],box["z"]],
                               "box":"small" if box["kind"]==1 else "large","trap_no":box["trap_no"]},
                      "contents":{"dc1_item":box["item_no"],"count":1,"dc2_item":m["dc2_item"],"mapping":m["relation"],
                                  "dc1_name":m["dc1_name"],"dc2_name":m["dc2_name"]}})
    ordered=list(monsters["list"]) if monsters else []
    if spawn is not None:
        ordered.sort(key=lambda r:(math.hypot(r["output"][0]-spawn[0],r["output"][2]-spawn[2]),r["slot"]))
    for r in ordered:
        if not r["grounded"]: deferred.append({"kind":"monster_spawn","slot":r["slot"],"reason":"no walkable ground under the monster"}); continue
        props.append({"id":f"monster-{r['slot']}","kind":"monster_spawn","position":[round(c,3) for c in r["output"]],"rotation_y":0.0,
                      "donor":{"op":"CMonstorUnit::ArrangementPos","model":r["model"],"monster_no":r["monster_no"],"slot":r["slot"],
                               "position":r["donor"],"holds_gate_key":r["holds_gate_key"]}})
    # A floor pack spans most of the DC2 floor, so native treasure boxes always lie inside its bounds:
    # ask the adapter to park them for the visit instead of refusing the installation.
    return {"format":"ixion-room-props","version":1,"room":name,"room_json_sha256":room_sha256,"units":{"scale":scale},
            "native_boxes":"park","sources":sources,"props":props,"deferred":deferred}


def floor_height(heights: list[float]) -> float:
    """The walkable surface nearest y=0, which is where every random-floor cell is placed. Kit
    parts also carry roof collision 45-65 units overhead that ground_heights cannot tell apart
    from floor, so the floor is the surface closest to the cell plane."""
    return min(heights,key=abs)


def convert_floor(pack_path: Path, cfg_path: Path, dump_path: Path, output: Path, scale: float,
                  room: str | None=None, include_under_road: bool=False) -> dict:
    """One real seeded random floor as one room.json v1 pack plus a floor.json sidecar.

    Each occupied cell places its kit part's frames at (160*col + frame offset, frame offset y,
    160*row + frame offset z) turned by dc1_turn(cell direction + frame_turn) (CDungeonParts::Draw,
    dungeonparts.cpp:2245-2275), and its PT_COLS model at (160*col, 0, 160*row) turned by
    dc1_turn(cell direction + PT_COLS turn) with no frame offset (dungeonparts.cpp:2156-2175,
    2324-2338). Spawn is the stair-in cell, exit the stair-out cell, both on the walkable collision
    under the cell centre; enemy_spawn is a bare room cell on the grid path between them (if any).
    """
    if scale<=0 or not math.isfinite(scale): raise ConvertError("scale must be finite and positive")
    pack_bytes=pack_path.read_bytes(); cfg_bytes=cfg_path.read_bytes(); dump_bytes=Path(dump_path).read_bytes()
    dump=load_floor_dump(json.loads(dump_bytes.decode("utf-8")))
    members=parse_pack(pack_bytes); room_cfg=parse_room_cfg(cfg_bytes)
    if not room_cfg.ground_images: raise ConvertError("room config lacks GRD_IMG")
    cells=floor_placements(dump,len(room_cfg.parts),include_under_road)
    if not cells: raise ConvertError("floor has no cells")
    used={cell["parts_no"] for cell in cells}
    needed=[f.name for i in used for f in room_cfg.parts[i].frames]+[room_cfg.parts[i].collision[0] for i in used if room_cfg.parts[i].collision]+list(room_cfg.ground_images)
    if any(members.get(n.casefold()) is None for n in needed): raise ConvertError("required kit mesh or IMG member is missing")
    textures={}
    for name in room_cfg.ground_images:
        for tex,value in decode_img(members[name.casefold()].data).items():
            if any(t.casefold()==tex.casefold() for t in textures): raise ConvertError(f"texture {tex!r} appears in two GRD_IMG files")
            textures[tex]=value
    visual_cache={}; collision_cache={}; visuals=[]; collision_donor=[]; visual_count=0; per_cell_collision={}
    for cell in cells:
        part=room_cfg.parts[cell["parts_no"]]; dx=FLOOR_CELL*cell["col"]; dz=FLOOR_CELL*cell["row"]
        for frame in part.frames:
            turn=dc1_turn(cell["direction"]+frame.turn)
            key=(frame.name.casefold(),frame.offset,turn)
            if key not in visual_cache:
                got,cnt=parse_visual_mds(members[frame.name.casefold()].data,frame.offset,turn,textures)
                visual_cache[key]=(_rounded(got),cnt)
            groups,count=visual_cache[key]
            visuals.extend(_translated(groups,dx,dz,scale)); visual_count+=count
        if part.collision is not None:
            turn=dc1_turn(cell["direction"]+part.collision[1])
            key=(part.collision[0].casefold(),turn)
            if key not in collision_cache:
                collision_cache[key]=parse_collision_mds(members[part.collision[0].casefold()].data,(0.0,0.0,0.0),turn)
            tris=[[[round(p[0]+dx,4),round(p[1],4),round(p[2]+dz,4)] for p in tri] for tri in collision_cache[key]]
            collision_donor.extend(tris); per_cell_collision[(cell["col"],cell["row"])]=len(tris)
    if not collision_donor: raise ConvertError("floor has no collision")
    if len(visuals)>MAX_PACK_VISUALS or len(collision_donor)>MAX_PACK_COLLISION: raise ConvertError("floor exceeds pack limits")
    index=GroundIndex(collision_donor)

    # Markers. The stair cells are the generator's own entrance and exit (dungeonmap.cpp:2113-2190).
    # A stair part's closed end holds a gate wall a few units from the cell centre (the entrance
    # stair of the d01main_a kit has one at +7 from the centre, with an end wall at -3), so a
    # marker on the centre sits in a sealed pocket. Markers are placed STAIR_FRONT units from the
    # centre toward the neighbouring cell on the grid path, in front of that wall.
    STAIR_FRONT=40.0
    def anchor(col: int, row: int, label: str, toward: tuple[int,int] | None=None) -> tuple[float,float,float]:
        x=FLOOR_CELL*col; z=FLOOR_CELL*row
        if toward is not None:
            x+=STAIR_FRONT*(toward[0]-col); z+=STAIR_FRONT*(toward[1]-row)
        heights=index.heights(x,z)
        if not heights: raise ConvertError(f"{label} cell ({col},{row}) has no walkable ground at its marker")
        return (x,floor_height(heights),z)
    entrance=(dump["stair_down"]["col"],dump["stair_down"]["row"]); exit_cell=(dump["stair_up"]["col"],dump["stair_up"]["row"])
    path=floor_grid_path(dump,entrance,exit_cell)
    if path is None or len(path)<3: raise ConvertError("no grid path from the entrance stair to the exit stair")
    spawn=anchor(*entrance,"entrance",path[1]); exit_at=anchor(*exit_cell,"exit",path[-2])
    middle=[c for c in path[len(path)//4:len(path)*3//4+1] if (dump["content"][c[1]*20+c[0]]&~BUILD_ROOM)==0 and dump["content"][c[1]*20+c[0]]]
    enemy_cell=middle[len(middle)//2] if middle else path[len(path)//2]
    enemy=anchor(*enemy_cell,"enemy")
    route=[spawn]+[(FLOOR_CELL*c,0.0,FLOOR_CELL*r) for c,r in path[1:-1]]+[exit_at]
    walk=walk_support(index,route,4.0,6.0,12.0)
    walk.update(wall_crossings(WallIndex(collision_donor),walk["track"]))
    walk.pop("track")

    pts=[v["position"] for g in visuals for v in g["vertices"]]
    collision=[[[x*scale for x in p] for p in tri] for tri in collision_donor]
    pts.extend(p for tri in collision for p in tri)
    bounds={"min":[min(p[a] for p in pts) for a in range(3)],"max":[max(p[a] for p in pts) for a in range(3)]}
    spawn_o,enemy_o,exit_o=(tuple(x*scale for x in p) for p in (spawn,enemy,exit_at))
    output=output.resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists(): raise ConvertError("output already exists; choose a new path")
    name=room or f"d01main_a-seed{dump['map_seed']}-floor{dump['floor']}"
    src=[{"path":pack_path.name,"sha256":hashlib.sha256(pack_bytes).hexdigest()},
         {"path":cfg_path.name,"sha256":hashlib.sha256(cfg_bytes).hexdigest()},
         {"path":Path(dump_path).name,"sha256":hashlib.sha256(dump_bytes).hexdigest()}]
    tex_records=[]
    doc={"format":"ixion-room","version":1,"donor":{"game":"dc1","room":name,"sources":src},"units":{"scale":scale},
         "spawn":list(spawn_o),"enemy_spawn":list(enemy_o),"exit":list(exit_o),"bounds":bounds,"textures":tex_records,
         "visuals":visuals,"collision":collision}

    def cell_record(col: int, row: int) -> dict:
        x=FLOOR_CELL*col; z=FLOOR_CELL*row; h=index.heights(x,z)
        return {"col":col,"row":row,"parts_no":dump["parts_no"][row*20+col],"direction":dump["direction"][row*20+col],
                "center":[x*scale,(floor_height(h) if h else 0.0)*scale,z*scale],"grounded":bool(h)}
    def free_cell(c: int, r: int) -> bool: return dump["content"][r*20+c]==BUILD_ROOM and dump["parts_no"][r*20+c]==17
    rooms=[]
    for i,r in enumerate(dump.get("rooms") or []):
        interior=[cell_record(c,rr) for rr in range(r["y"],r["y"]+r["height"]) for c in range(r["x"],r["x"]+r["width"]) if 0<=c<FLOOR_PLAYABLE and 0<=rr<FLOOR_PLAYABLE and free_cell(c,rr)]
        rooms.append({"index":i,"x":r["x"],"y":r["y"],"width":r["width"],"height":r["height"],"free_floor_cells":interior})
    corridor=[cell_record(c,r) for r in range(FLOOR_PLAYABLE) for c in range(FLOOR_PLAYABLE) if dump["content"][r*20+c]&BUILD_CORRIDOR and dump["parts_no"][r*20+c]<5]
    chests=[]
    for box in dump.get("chests") or []:
        col=int(round(box["x"]/FLOOR_CELL)); row=int(round(box["z"]/FLOOR_CELL)); h=index.heights(box["x"],box["z"])
        chests.append({**box,"col":col,"row":row,"output":[box["x"]*scale,(floor_height(h) if h else box["y"])*scale,box["z"]*scale],"grounded":bool(h),
                       "dc2":chest_mapping(box["item_no"])})
    monsters=floor_monsters(dump,index,scale); gate_key=floor_gate_key(dump,monsters)
    ura=dump.get("ura_entrance")
    sidecar={"format":"ixion-randfloor-meta","version":1,"map_seed":dump["map_seed"],"floor":dump["floor"],"dungeon":dump.get("dungeon"),
             "units":{"scale":scale,"cell_size":FLOOR_CELL*scale,"note":"cell (col,row) is centred at (col*cell_size, y, row*cell_size)"},
             "entrance":{**cell_record(*entrance),"role":"stair in (kit part 30), the player's way in"},
             "exit":{**cell_record(*exit_cell),"role":"stair out (kit part 31), opened by the gate key"},
             "back_floor_entrance":cell_record(ura["col"],ura["row"]) if ura else None,
             "gate_key_no":dump.get("gate_key_no"),"gate_key":gate_key,"monsters":monsters,"path_cells":[list(c) for c in path],
             "rooms":rooms,"corridor_cells":corridor,"chests":chests,"atla":dump.get("atla") or [],"trap_circles":dump.get("trap_circles") or [],
             "monster_candidates":{"note":"cells where retail may place monsters are not decoded; these are free room floor cells and corridor cells",
                                   "room_cells":[c for r in rooms for c in r["free_floor_cells"]],"corridor_cells":corridor},
             "walk":walk,"dump_sha256":hashlib.sha256(dump_bytes).hexdigest()}
    with tempfile.TemporaryDirectory(prefix=output.name+".tmp-",dir=output.parent) as staging_name:
        staging=Path(staging_name)
        for i,(tname,(png,w,h)) in enumerate(sorted(textures.items(),key=lambda item:item[0].casefold())):
            filename=f"textures/{i:02d}-{re.sub(r'[^A-Za-z0-9_.-]','_',tname)}.png"
            target=staging/filename; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(png)
            tex_records.append({"name":tname,"file":filename})
        room_text=json.dumps(doc,separators=(",",":"),allow_nan=False)
        (staging/"room.json").write_text(room_text,encoding="utf-8")
        (staging/"floor.json").write_text(json.dumps(sidecar,separators=(",",":"),allow_nan=False),encoding="utf-8")
        props=floor_props(name,hashlib.sha256(room_text.encode("utf-8")).hexdigest(),scale,src,chests,monsters,spawn_o)
        (staging/"props.json").write_text(json.dumps(props,separators=(",",":"),allow_nan=False),encoding="utf-8")
        validate_pack(staging)
        size=(staging/"room.json").stat().st_size
        os.replace(staging,output)
    return {"cells":len(cells),"parts_used":sorted(used),"visual_groups":len(visuals),"visual_triangles":visual_count,
            "collision_triangles":len(collision),"textures":len(tex_records),"room_json_bytes":size,"bounds":bounds,
            "markers_output":{"spawn":list(spawn_o),"enemy_spawn":list(enemy_o),"exit":list(exit_o)},
            "entrance_cell":list(entrance),"exit_cell":list(exit_cell),"enemy_cell":list(enemy_cell),
            "path_cells":len(path),"walk":walk,"chests_in_sidecar":len(chests),"props":len(props["props"]),
            "monsters":(monsters["placed"] if monsters else 0),"donor_list":(monsters["roster"]["donor_list"] if monsters else "")}


def vector_arg(value: str) -> tuple[float,float,float]:
    try: parts=tuple(float(x) for x in value.split(","))
    except ValueError as exc: raise argparse.ArgumentTypeError("expected x,y,z") from exc
    if len(parts)!=3 or not all(math.isfinite(x) for x in parts): raise argparse.ArgumentTypeError("expected finite x,y,z")
    return parts


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="cmd",required=True)
    c=sub.add_parser("convert"); c.add_argument("--pack",type=Path,required=True); c.add_argument("--cfg",type=Path,required=True); c.add_argument("--output",type=Path,required=True); c.add_argument("--room",default="d01inter"); c.add_argument("--visual",default="d01i01_0.mds"); c.add_argument("--collision",default="d01i01_a.mds"); c.add_argument("--all-parts",action="store_true",help="convert every DEF_PATS part of the cfg into one v1 pack"); c.add_argument("--markers",type=Path,help="JSON marker file (frame or donor positions); overrides --spawn/--enemy-spawn/--exit"); c.add_argument("--spawn",type=vector_arg,default=(0,0,0)); c.add_argument("--enemy-spawn",type=vector_arg,default=(12,0,0)); c.add_argument("--exit",type=vector_arg,default=(24,0,0)); c.add_argument("--scale",type=float,default=1.0)
    f=sub.add_parser("floor",help="one seeded random floor (a randfloor_dump JSON) as one v1 pack plus floor.json"); f.add_argument("--pack",type=Path,required=True); f.add_argument("--cfg",type=Path,required=True); f.add_argument("--dump",type=Path,required=True); f.add_argument("--output",type=Path,required=True); f.add_argument("--scale",type=float,required=True); f.add_argument("--room",default=None); f.add_argument("--include-under-road",action="store_true",help="also place the back floor road column (col 19)")
    a=sub.add_parser("floor-ascii",help="print the playable grid of a randfloor_dump as text"); a.add_argument("dump",type=Path)
    v=sub.add_parser("validate"); v.add_argument("pack",type=Path)
    p=sub.add_parser("props",help="write a props.json sidecar (DC1 chests, Atla) next to an existing room.json")
    p.add_argument("--room-pack",type=Path,required=True); p.add_argument("--stb",type=Path,required=True); p.add_argument("--cfg",type=Path)
    a=sub.add_parser("arena",help="write an arena.json sidecar (Dran field tiles, PT_FIRE, PT_CAM, full PT_MARKER) next to an existing room.json")
    a.add_argument("--room-pack",type=Path,required=True); a.add_argument("--pack",type=Path,required=True); a.add_argument("--cfg",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        if args.cmd=="convert":
            markers=json.loads(args.markers.read_text(encoding="utf-8")) if args.markers else None
            result=convert(args.pack,args.cfg,args.output,args.room,args.visual,args.collision,args.spawn,args.enemy_spawn,args.exit,args.scale,args.all_parts,markers)
        elif args.cmd=="props":
            doc=build_props(args.room_pack,args.stb,args.cfg)
            result={"written":str(write_props(args.room_pack,doc)),"props":doc["props"],"deferred":len(doc["deferred"])}
        elif args.cmd=="arena":
            doc,files=build_arena(args.room_pack,args.pack,args.cfg)
            result={"written":str(write_arena(args.room_pack,doc,files)),"files":sorted(files),
                    "tiles":[{"slot":t["slot"],"objects":len(t["objects"]),"collision":len(t["collision"])} for t in doc["field_tiles"]["tiles"]],
                    "fires":len(doc["fires"]["emitters"]),"camera_collision":[sum(len(o["triangles"]) for o in c["objects"]) for c in doc["camera_collision"]],
                    "markers":[(m["name"],m["script"]) for m in doc["markers"]],"floor_support":doc["floor_support"]}


        elif args.cmd=="floor":
            result=convert_floor(args.pack,args.cfg,args.dump,args.output,args.scale,args.room,args.include_under_road)
        elif args.cmd=="floor-ascii":
            dump=load_floor_dump(args.dump)
            path=floor_grid_path(dump,(dump["stair_down"]["col"],dump["stair_down"]["row"]),(dump["stair_up"]["col"],dump["stair_up"]["row"]))
            print(floor_ascii(dump,path)); return 0
        else: result={"format":validate_pack(args.pack).get("format"),"version":1}
        print(json.dumps(result,indent=2)); return 0
    except (OSError,ConvertError,struct.error,UnicodeError,json.JSONDecodeError) as exc:
        parser.exit(2,f"room-converter: {exc}\n")


if __name__=="__main__": raise SystemExit(main())
