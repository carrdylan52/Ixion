"""Offline PAL DC2 Ridepod -> private DC1 visual pack. No retail assets in git.

DC1 reads MDT/MDS/MOT; arm01 uses a private donor skin adapter.
SetupRobo links arm to leg.body1 and body to arm.spine. Punch and machine-gun
arms are included; sounds, seat and native equipment menus are excluded.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import struct
import sys
import zlib
from pathlib import Path, PurePosixPath
# Explicit local imports also work under Python -I, without the current directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.monster_converter import (ConvertError, parse_pack, DC1_TO_DC2_SCALE, build_pack, parse_chr_cfg,
    read_mds, validate_mdt, mdt_header, walk_mot)

SCALE = 1 / DC1_TO_DC2_SCALE
LOGIC_HZ = 25
KEY_NAMES = ('立ち-足', '歩き-足', '走り-足')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def png_rgba(data: bytes) -> tuple[bytes, int, int]:
    """Bounded non-interlaced 8-bit RGBA PNG reader for the native catalog."""
    if data[:8] != b'\x89PNG\r\n\x1a\n': raise ConvertError('bad PNG signature')
    pos, compressed, dimensions = 8, bytearray(), None
    while pos < len(data):
        if len(data) - pos < 12: raise ConvertError('truncated PNG chunk')
        n = struct.unpack_from('>I', data, pos)[0]
        if n > len(data) - pos - 12: raise ConvertError('PNG chunk escapes file')
        tag = data[pos+4:pos+8]
        chunk = data[pos+8:pos+8+n]
        if zlib.crc32(tag+chunk) != struct.unpack_from('>I', data, pos+8+n)[0]:
            raise ConvertError('PNG CRC mismatch')
        if tag == b'IHDR':
            if dimensions or n != 13: raise ConvertError('invalid PNG IHDR')
            w,h,depth,color,compression,filtering,interlace = struct.unpack('>IIBBBBB',chunk)
            if not (0 < w <= 2048 and 0 < h <= 2048) or (depth,color,compression,filtering,interlace) != (8,6,0,0,0):
                raise ConvertError('expected bounded RGBA8 non-interlaced PNG')
            dimensions = (w,h)
        elif tag == b'IDAT': compressed.extend(chunk)
        elif tag == b'IEND': break
        pos += n+12
    if dimensions is None: raise ConvertError('missing PNG IHDR')
    w,h = dimensions
    stride = w*4
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, (stride+1)*h+1)
    if len(raw) != (stride+1)*h or not decoder.eof or decoder.unused_data:
        raise ConvertError('invalid PNG scanline extent')
    out = bytearray()
    previous = bytes(stride)
    for row in range(h):
        at = row*(stride+1)
        kind, scan = raw[at], bytearray(raw[at+1:at+1+stride])
        if kind > 4: raise ConvertError('unknown PNG filter')
        for i in range(stride):
            a = scan[i-4] if i >= 4 else 0
            b = previous[i]
            c = previous[i-4] if i >= 4 else 0
            predictor = 0
            if kind == 1: predictor = a
            elif kind == 2: predictor = b
            elif kind == 3: predictor = (a+b)//2
            elif kind == 4:
                p = a+b-c
                distances = (abs(p-a),abs(p-b),abs(p-c))
                predictor = (a,b,c)[distances.index(min(distances))]
            scan[i] = (scan[i]+predictor)&255
        out.extend(scan)
        previous = scan
    return bytes(out),w,h


def gs_rgba(rgba: bytes) -> bytes:
    out = bytearray(rgba)
    for i in range(3,len(out),4): out[i] = (out[i]*128+127)//255
    return bytes(out)


def safe_file(root: Path, name: str) -> Path:
    p = PurePosixPath(name)
    if p.is_absolute() or any(s in ('..','.') for s in p.parts) or '\\' in name or ':' in name:
        raise ConvertError('unsafe catalog path')
    resolved = (root/p).resolve()
    if not resolved.is_relative_to(root.resolve()): raise ConvertError('catalog path escapes root')
    return resolved


def rigid_mds(data: bytes, label: str, textures: dict[str,str], mount: bool = False) -> tuple[bytes,dict]:
    objects = read_mds(data,label)
    out = bytearray(data[:16+112*len(objects)] if mount else data)
    stats = {'objects':len(objects),'meshes':0,'triangles':0,'material_names':0,'face_types':{}}
    for obj in objects:
        if mount:
            struct.pack_into('<i',out,16+112*obj.index+40,0)
            continue
        if not obj.mesh: continue
        info = validate_mdt(data,obj.mesh,f'{label}:{obj.name}')
        # DC1's existing renderer consumes exactly vertex/normal/UV triplets.
        if set(info.face_types) - {3,4}: raise ConvertError('DC1 visual requires triplet triangle lists/strips')
        h = mdt_header(data,obj.mesh)
        if h['colour_num'] or h['colour_ofs'] > 0: raise ConvertError('unexpected donor vertex colours')
        stats['meshes'] += 1
        stats['triangles'] += info.triangles
        for kind,count in info.face_types.items():
            stats['face_types'][str(kind)] = stats['face_types'].get(str(kind),0)+count
        for i,name in enumerate(info.materials):
            if name not in textures: raise ConvertError(f'missing texture {name}')
            new = textures[name].encode('ascii')
            if len(new) > 31: raise ConvertError('texture name too long')
            at = obj.mesh+h['material_ofs']+96*i+52
            # DC1 material texture is char[44]; zero DC2's extra 12 bytes.
            out[at:at+44] = new.ljust(44,b'\0')
            stats['material_names'] += 1
    return bytes(out),stats


def dc1_cfg(model: str, motion: str | None, keys: list[dict], skin: bool = False) -> bytes:
    lines = (['VERTEX_ANIME 1'] if skin else []) + [f'MODEL "{model}"', 'BODY_SIZE 20.0, 8.0, 80.0']
    if motion:
        stem = model.removesuffix('.mds')
        bones, weights = (f'{stem}.bbp', f'{stem}.wgt') if skin else ('','')
        lines += [f'MOTION 0, "{motion}", "{bones}", "{weights}"','KEY_START 0']
        for key in keys: lines.append(f'KEY {key["start"]}, {key["end"]}, {key["step"]:.8f}')
        lines.append('MOTION_END')
    return ('\n'.join(lines)+'\n').encode('ascii')


def validate_skin(mds: bytes, bbp: bytes, wgt: bytes) -> dict:
    objects = read_mds(mds,'arm skin')
    if len(bbp) != len(objects)*64: raise ConvertError('skin bind matrix extent mismatch')
    if not all(math.isfinite(v) for v in struct.unpack(f'<{len(bbp)//4}f',bbp)):
        raise ConvertError('skin bind matrix nonfinite')
    at,lists,keys = 0,0,0
    while True:
        if at+32 > len(wgt): raise ConvertError('skin weight header truncated')
        frame,target,kind = struct.unpack_from('<3I',wgt,at)
        count,more = struct.unpack_from('<2I',wgt,at+16)
        if frame >= len(objects) or target >= len(objects) or kind != 20 or count > 3000:
            raise ConvertError('unsupported skin frame/weight type')
        if not objects[frame].mesh: raise ConvertError('skin target has no mesh')
        vertices = mdt_header(mds,objects[frame].mesh)['vertex_num']
        if vertices > 3000 or at+32+count*32 > len(wgt): raise ConvertError('skin weight extent invalid')
        at += 32
        for i in range(count):
            vertex = struct.unpack_from('<I',wgt,at)[0]
            weight = struct.unpack_from('<f',wgt,at+16)[0]
            if vertex >= vertices or not math.isfinite(weight) or not 0 <= weight <= 100:
                raise ConvertError('skin weight or vertex invalid')
            at += 32
        lists += 1; keys += count
        if not more: break
    if at != len(wgt): raise ConvertError('skin trailing bytes')
    return {'lists':lists,'weights':keys,'bbp_sha256':digest(bbp),'wgt_sha256':digest(wgt)}


def convert(data_root: Path, catalog_file: Path, output: Path) -> dict:
    if output.exists(): raise ConvertError('output exists; refusing to overwrite')
    catalog = json.loads(catalog_file.read_text(encoding='utf-8'))
    sources = {s['source']:s for s in catalog['sources']}
    files, provenance, tex_table, texture_map = {}, {}, [], {}
    for part in ('leg01','body01','arm01','arm04'):
        source = sources[f'dungeon/robo/{part}.chr/{part}.img']
        for entry in source['entries']:
            if entry.get('no_image') or entry['format'] != 'rgba8': raise ConvertError('unsupported catalog texture')
            name = entry['name']
            texture_map[name] = 'ixrp_'+name
            level = entry['variants'][0]['levels'][0]
            png = safe_file(catalog_file.parent,level).read_bytes()
            rgba,w,h = png_rgba(png)
            if (w,h) != (entry['width'],entry['height']): raise ConvertError('catalog dimensions disagree')
            filename = 'ixrp_'+name+'.rgba'
            pixels = gs_rgba(rgba)
            files[filename] = pixels
            tex_table.append({'name':texture_map[name],'file':filename,'width':w,'height':h,
                'tex1':entry['tex1'],'sha256':digest(pixels),'source_png':level,'source_sha256':digest(png)})
    keys = []
    for part in ('leg01','body01','arm01','arm04'):
        src_path = data_root/f'dungeon/robo/{part}.chr'
        raw = src_path.read_bytes()
        members = parse_pack(raw)
        cfg = parse_chr_cfg(members['info.cfg'].data.decode('cp932'))
        mds = members[f'{part}.mds'].data
        rewritten,stats = rigid_mds(mds,part,texture_map)
        if part == 'arm01':
            stats['skin'] = validate_skin(mds,members['arm01.bbp'].data,members['arm01.wgt'].data)
        if part == 'body01':
            out=bytearray(rewritten)
            light=next(o for o in read_mds(mds,part) if o.name.startswith('light--'))
            struct.pack_into('<i',out,16+112*light.index+40,0)
            rewritten=bytes(out)
            stats['effect_omitted']='DC2 additive headlight cone is unsupported by DC1 material flags'
        name = part
        entries = [(f'{name}.mds',rewritten)]
        selected = []
        if part != 'body01':
            # Both source cfgs share the real foot motions. No procedural cycle.
            names = KEY_NAMES + (('右手攻撃','左手攻撃','両手攻撃') if part == 'arm01' else
                                 ('攻撃１',) if part == 'arm04' else ())
            for key_name in names:
                key = next((k for k in cfg.keys.get(0,[]) if k[0] == key_name),None)
                if key is None: raise ConvertError(f'missing donor motion {key_name}')
                selected.append({'name':key_name,'start':key[1],'end':key[2],
                    'donor_step':key[3],'step':key[3]*1.2*LOGIC_HZ/60})
            mot = members[f'{part}.mot'].data
            motion_info = walk_mot(mot,stats['objects'],part)
            if any(k['end'] > motion_info['max_frame'] for k in selected): raise ConvertError('motion range escapes MOT')
            entries.append((f'{name}.mot',mot))
            if part=='arm01':
                entries.extend((f'{name}.{suffix}',members[f'{name}.{suffix}'].data) for suffix in ('bbp','wgt'))
            if part == 'leg01': keys = selected
        entries.append(('info.cfg',dc1_cfg(f'{name}.mds',f'{name}.mot' if selected else None,selected,part=='arm01')))
        packed = build_pack(entries)
        files[f'{name}.chr'] = packed
        provenance[part] = {'source':str(src_path),'sha256':digest(raw),'mds_sha256':digest(mds),
            'output_mds_sha256':digest(rewritten),'output_sha256':digest(packed),'stats':stats,
            'motion_sha256':digest(mot) if selected else None,'keys':selected}
    # RB_PARTS is extracted into the private pack, never committed as retail data.
    import re
    stat_path = data_root/'menu/cfg7/robodat.cfg'
    stat_text = stat_path.read_text(encoding='cp932')
    stats = {}
    for label,item in (('arm',145),('gun',150)):
        match = re.search(rf'RB_PARTS\s+{item},([^;]+);',stat_text)
        if not match: raise ConvertError('missing donor weapon stats')
        fields = match[1].split(',')
        stats[label] = {'item':item,'attack':int(fields[4]),'durability':int(fields[3]),
                        'donor_durable':int(fields[5]),'attack_type':int(fields[14])}
    manifest = {'format':'ixion-ridepod-dc1','version':2,'world_scale':SCALE,'donor_logic_hz':LOGIC_HZ,
        'animation_rate_note':'DC2 NormalDrive step * 1.2 * 25 / 60; runtime adjusts for host Hz',
        'assembly':{'leg_joint':'body1','body_joint':'spine','mount_source':'arm01 skinned punch / arm04 machine gun; headlight cone omitted'},
        'rider':'hidden; no verified Toan seat/pose','textures':tex_table,'provenance':provenance,'keys':keys,
        'weapons':stats,'stats_source_sha256':digest(stat_path.read_bytes())}
    files['ridepod.json'] = (json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode('utf-8')
    output.mkdir(parents=True)
    for name,payload in files.items(): (output/name).write_bytes(payload)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--catalog',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    try:
        result = convert(args.data,args.catalog,args.output)
        print(json.dumps(result,indent=2,ensure_ascii=True))
        return 0
    except (ConvertError,KeyError,ValueError,OSError) as error:
        parser.exit(1,f'conversion refused: {error}\n')

if __name__ == '__main__': raise SystemExit(main())
