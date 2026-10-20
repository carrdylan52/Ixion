"""Offline rigid Vanguard conversion. Retail bytes remain in a private output directory."""
from __future__ import annotations
import argparse
import json
import struct
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.ridepod_dc1_converter import (ConvertError, parse_pack, parse_chr_cfg,
    rigid_mds, read_mds, build_pack, dc1_cfg, png_rgba, gs_rgba, safe_file, digest, SCALE)


def validate_script(data: bytes) -> dict:
    """Walk every program and reachable CALL/JMP; reject DC2 globals before DC1 sees them."""
    if len(data) < 32 or data[:4] != b'SB2\0': raise ConvertError('expected SB2')
    main, code, table, count = struct.unpack_from('<4i', data, 4)
    def extent(at, n):
        if at < 0 or at+n > len(data): raise ConvertError('script offset escapes file')
    extent(table, count*8)
    if not 0 < count <= 32: raise ConvertError('invalid program count')
    programs = {}
    for i in range(count):
        number, function_offset = struct.unpack_from('<2i', data, table+8*i)
        if number in programs: raise ConvertError(f'duplicate program number {number}')
        programs[number] = function_offset
    required = {100,200,500,1000}
    if not required <= programs.keys(): raise ConvertError('missing Vanguard programs')
    work, seen, functions = [], set(), set()
    def function(fd):
        extent(fd, 16)
        if fd in functions: return
        functions.add(fd)
        addr, name, local, arg = struct.unpack_from('<4i', data, fd)
        if not 0 <= arg <= local <= 128: raise ConvertError('unsupported function stack')
        work.append(addr)
    for fd in [main, *programs.values()]: function(fd)
    while work:
        at = work.pop()
        if at in seen: continue
        seen.add(at)
        extent(code+at,12)
        op,a,b = struct.unpack_from('<3i',data,code+at)
        if not 1 <= op <= 30: raise ConvertError(f'unknown opcode {op}')
        if op in (1,2) and b not in (1,2,4,8,16,32):
            raise ConvertError(f'unsupported address mode {b:#x}')
        if op == 19: function(code+b)
        if op in (16,17,18): work.append(a)
        if op not in (15,16,27): work.append(at+12)
    return {'programs': sorted(programs), 'reachable_instructions':len(seen),
            'functions':len(functions), 'globals_referenced':False, 'sha256':digest(data)}


def convert(data_root: Path, catalog_file: Path, output: Path) -> dict:
    if output.exists(): raise ConvertError('output exists; refusing overwrite')
    raw = (data_root/'dungeon/monster/e202a.chr').read_bytes()
    stb = (data_root/'dungeon/monster/e202a.stb').read_bytes()
    script = validate_script(stb)
    members = parse_pack(raw)
    if any(name.endswith('.wgt') for name in members): raise ConvertError('rigid monster required')
    cfg_text = members['e202a.cfg'].data.decode('cp932')
    cfg = parse_chr_cfg(cfg_text)
    catalog = json.loads(catalog_file.read_text(encoding='utf-8'))
    source = next(s for s in catalog['sources'] if s['source']=='dungeon/monster/e202a.chr/e202a01.img')
    files, textures, mapping = {}, [], {}
    for entry in source['entries']:
        if entry.get('no_image') or entry['format'] != 'rgba8': raise ConvertError('unsupported texture')
        name = 'ixvg_'+entry['name']
        path = entry['variants'][0]['levels'][0]
        png = safe_file(catalog_file.parent,path).read_bytes()
        rgba,w,h = png_rgba(png)
        if (w,h)!=(entry['width'],entry['height']): raise ConvertError('texture dimensions disagree')
        pixels = gs_rgba(rgba)
        files[name+'.rgba'] = pixels
        textures.append({'name':name,'file':name+'.rgba','width':w,'height':h,
                         'tex1':entry['tex1'],'sha256':digest(pixels)})
        mapping[entry['name']] = name
    keys = [{'name':k[0], 'sjis_hex':k[0].encode('cp932').hex(), 'start':k[1],
             'end':k[2], 'donor_step':k[3], 'step':k[3]*1.2*25/60}
            for k in cfg.keys[0]]
    mds,stats = rigid_mds(members['e202a.mds'].data,'e202a',mapping)
    files['e202a.chr'] = build_pack([('e202a.mds',mds),('e202a.mot',members['e202a.mot'].data),
                                    ('info.cfg',dc1_cfg('e202a.mds','e202a.mot',keys))])
    files['e202a.stb'] = stb  # no bytecode rewriting; DC1 invocation is mapped by its adapter
    objects = read_mds(mds,'e202a')
    # Keep donor cfg entry order: _SET_DMG2 ids refer to group-3 indices, not frame suffixes.
    manifest = {'format':'ixion-dc2-monster-dc1','version':1,'donor':'e202a',
        'world_scale':SCALE,'logic_hz':25,'keys':keys,'textures':textures,
        'source_sha256':digest(raw),'model_sha256':digest(files['e202a.chr']), 'script':script,
        'stats':stats, 'frames':[o.name for o in objects]}
    # Record cfg commands without interpreting native collision semantics offline.
    from tools.monster_converter import spi_statements
    manifest['collision_commands'] = [[cmd,args] for cmd,args in spi_statements(cfg_text)
                                      if cmd == 'OBJECT_NAME2']
    files['monster.json'] = (json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode('utf-8')
    output.mkdir(parents=True)
    for name,payload in files.items(): (output/name).write_bytes(payload)
    return manifest


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,required=True)
    ap.add_argument('--catalog',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    try: print(json.dumps(convert(args.data,args.catalog,args.output),indent=2,ensure_ascii=True))
    except (ConvertError,KeyError,ValueError,OSError,StopIteration) as error: ap.exit(1,f'conversion refused: {error}\n')
