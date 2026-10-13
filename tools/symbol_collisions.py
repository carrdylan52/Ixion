#!/usr/bin/env python3
"""Quantify symbol collisions between two Ixion source builds.

Each input is a CMake build tree for one game port (Chronicle or ChronicleTwo).
The analysis reads COFF symbols with llvm-nm (defined and undefined global
names) and llvm-readobj (COMDAT selection, section lengths, weak externals).

Scope ("linked" mode, the default): the merged set is the object and archive
inputs of the game executable's link edge in build.ninja, so the analysis
matches what the linker actually sees. Test and tool executables, unlinked
cargo rlibs and unlinked helper objects are counted but not analysed. Use
--mode tree to analyse every object in the tree instead (heuristic scope).

Attribution: each defined name is attributed to a component (game, port,
host, host-copy, sce, rust, rust-kazarov, test, tool, implib, other) using
compile_commands.json when present and the object path otherwise.

Link effect per cross-build name (what a single merged link would do):
  - hard-link-error: strong definition in a plain object on both sides
    (NoDuplicates COMDATs count as strong; lld reports duplicates);
  - silent-strong-wins: one side strong, the other weak (Any-selection COMDAT
    or weak external): the weak copy is dropped silently;
  - silent-first-wins: both sides weak;
  - archive-pull-dependent: at least one strong definition comes only from
    an archive member; it conflicts only if the member is pulled in.

Classes (owners of constructors, destructors, vtables or typeinfo, from
llvm-cxxfilt demangling) defined by both builds are compared by method
surface, vtable section length and COMDAT code length. This is inference:
symbols cannot prove that the data layout of two same-named classes matches.

Standard library only. Read-only: it never writes into the build trees.
Example:
  python3 symbol_collisions.py --build-a DIR_A --build-b DIR_B \
      --nm /path/to/llvm-nm --label-a dc1 --label-b dc2 \
      --receipts DIR_WITH_SYMS --json out.json
"""

import argparse
import collections
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

OBJECT_SUFFIXES = ('.obj', '.o', '.a', '.lib', '.rlib')
ARCHIVE_SUFFIXES = ('.a', '.lib', '.rlib')
# Categories that are separate executables or not game code.
EXCLUDED_CATS = ('test', 'tool', 'implib')
PORT_HOST_DIRS = ('platform', 'audio', 'gfx')
EXE_NAME_SKIP = re.compile(r'test|data|bridge', re.I)

# Linker-generated names that are not real symbols for this analysis.
ARTIFACT_PREFIXES = (
    '.refptr.', '.idata', '.rdata', '.text', '.data', '.bss', '.xdata',
    '.pdata', '.rodata', '.debug', '.eh_frame', '.ctors', '.dtors', '.tls',
    '.CRT', '.gcc_except', '__imp_', '$R',
)
CRT_PREFIXES = (
    '__mingw', '_MINGW', '__CTOR_LIST__', '__DTOR_LIST__',
    '__RUNTIME_PSEUDO_RELOC', '__ImageBase', '_tls', '__tls', '__dyn_tls',
    '_fltused', '__xl_', '__xc_', 'mainCRTStartup', 'WinMain', 'DllMain',
    '__gxx_personality', '__cxa_', '_Unwind_', '__gcc_', '__emutls',
    '_GLOBAL_OFFSET', 'atexit',
)
LIBCXX_DEM = (
    'std::', 'typeinfo for std::', 'typeinfo name for std::',
    'vtable for std::', 'guard variable for std::',
    'non-virtual thunk to std::', 'construction vtable for std::',
    'covariant return thunk to std::',
)
LIBCXX_MANGLED = re.compile(
    r'^_Z(?:T[VISH]|GV)?(?:N?K?St|NSt|NKSt|St)|St3__1|^_Zn|^_Zd|B9nqe\d+')
RUST_HASH = re.compile(r'17h[0-9a-f]{16}E$')
# Unresolved-import classes, by name shape (heuristic, for the report only).
SDK_PATTERNS = (
    ('sdk:sdl', re.compile(r'^SDL_')),
    ('sdk:vulkan', re.compile(r'^vk[A-Z]')),
    ('sdk:ffmpeg', re.compile(r'^(av[a-z]*_|sws_|swr_)')),
    ('sdk:win32-likely', re.compile(r'^[A-Z][A-Za-z0-9]*[WA]?$')),
)

# COMDAT selections that let the linker keep one of several copies silently.
# NoDuplicates is not in the list: lld reports a duplicate symbol for two
# NoDuplicates definitions (checked with a probe link outside the build trees),
# so it behaves as a strong definition for this analysis.
WEAK_SELECTIONS = ('Any', 'Largest', 'SameSize', 'ExactMatch', 'Associative')
CODE_LETTERS = ('T', 't', 'W', 'w')

Def = collections.namedtuple('Def', 'oid cat weak length sel arch letter')
EMPTY_INFO = {'comdat': set(), 'secof': {}, 'seclen': {}, 'weakext': set(), 'secsel': {}}


# ---------------------------------------------------------------- helpers

def run(cmd, stdin_text=None):
    kwargs = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}
    if stdin_text is None:
        kwargs['stdin'] = subprocess.DEVNULL
    else:
        kwargs['input'] = stdin_text.encode('utf-8')
    proc = subprocess.run(cmd, **kwargs)
    return proc.returncode, proc.stdout.decode('utf-8', 'replace')


def norm(path):
    return os.path.normcase(os.path.abspath(path))


def sibling(tool_path, name):
    folder, base = os.path.split(tool_path)
    ext = os.path.splitext(base)[1]
    return os.path.join(folder, name + ext)


def is_artifact(name):
    # Dot-prefixed names are section, string-literal (.str.N) and linker labels.
    return name.startswith(ARTIFACT_PREFIXES) or name.startswith(('$', '.'))


def classify_source(src):
    low = src.replace('\\', '/').lower()
    if '/ps2_src/' in low:
        return 'game'
    if '/tools/kazarov/' in low or '/kazarov/' in low:
        return 'host'
    if '/tests/' in low or 'googletest' in low or 'gtest' in low or '/_deps/' in low:
        return 'test'
    if '/tools/' in low:
        return 'tool'
    if '/port/src/' in low:
        if '/stubs/' in low or '/sce/' in low:
            return 'sce'
        if any('/port/src/%s/' % d in low for d in PORT_HOST_DIRS):
            return 'host-copy'
        return 'port'
    if '/cargo/' in low or '/corrosion/' in low or low.endswith('.rlib'):
        return 'rust'
    return 'other'


def classify_object_path(path):
    """Fallback when compile_commands.json has no entry for the object."""
    low = path.replace('\\', '/').lower()
    base = low.rsplit('/', 1)[-1]
    if low.endswith('.dll.a'):
        return 'implib'
    if 'gtest' in low or 'googletest' in low or '/tests/' in low:
        return 'test'
    if base.startswith('libkazarov_'):
        # Kazarov Rust core and cxx bridge archives (both linked into the game exe).
        return 'rust-kazarov'
    if '/cargo/' in low or '/corrosion/' in low or low.endswith('.rlib'):
        return 'rust-kazarov' if 'kazarov' in base else 'rust'
    if 'ps2_src' in low:
        return 'game'
    if 'ct_host.dir' in low or 'kazarov' in low:
        return 'host'
    if 'dc_host.dir' in low:
        return 'host-copy'
    if 'ct_port.dir' in low or 'dc_port.dir' in low:
        return 'port'
    if '/tools/' in low:
        return 'tool'
    return 'other'


def load_compile_map(root):
    """Map normalized object path -> source path from compile_commands.json."""
    path = os.path.join(root, 'compile_commands.json')
    mapping = {}
    if not os.path.exists(path):
        return mapping
    with open(path, encoding='utf-8') as fh:
        entries = json.load(fh)
    for entry in entries:
        out = entry.get('output')
        if not out:
            continue
        base = entry.get('directory', root)
        mapping[norm(os.path.join(base, out))] = entry.get('file', '').replace('\\', '/')
    return mapping


def discover(root):
    found = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(OBJECT_SUFFIXES):
                found.append(os.path.join(dirpath, name))
    found.sort()
    return found


# ---------------------------------------------------------------- link edges

def ninja_statements(path):
    """Yield build.ninja statements with '$' line continuations joined."""
    cur = ''
    with open(path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            line = raw.rstrip('\n')
            cur = (cur + ' ' + line.lstrip()) if cur else line
            if cur.endswith('$'):
                cur = cur[:-1]
                continue
            yield cur
            cur = ''


def ninja_path(root, token):
    # Ninja writes 'C$:' for a drive colon and '$ ' for a space.
    tok = token.replace('$:', ':').replace('$ ', ' ')
    if re.match(r'^[A-Za-z]:', tok):
        return norm(tok)
    return norm(os.path.join(root, tok))


def find_link_edges(root):
    """Return {exe_name: (object_set, archive_set)} for executable link edges."""
    path = os.path.join(root, 'build.ninja')
    edges = {}
    if not os.path.exists(path):
        return edges
    for st in ninja_statements(path):
        if not st.startswith('build ') or ':' not in st:
            continue
        head, _, body = st[len('build '):].partition(':')
        exe = head.strip()
        if not exe.endswith('.exe') or 'LINKER' not in body:
            continue
        explicit, _, rest = body.partition(' | ')
        implicit = rest.partition(' || ')[0]
        objs = {ninja_path(root, t) for t in explicit.split()
                if t.lower().endswith(('.obj', '.o'))}
        archives = set()
        for t in implicit.split():
            if t.lower().endswith('.a') and not t.lower().endswith('.dll.a'):
                archives.add(ninja_path(root, t))
        edges[exe] = (objs, archives)
    return edges


def pick_exe(edges, wanted):
    if wanted:
        if wanted not in edges:
            raise SystemExit('exe %s not found in build.ninja (have %s)' % (wanted, sorted(edges)))
        return wanted
    cands = [(len(o), e) for e, (o, _a) in edges.items() if not EXE_NAME_SKIP.search(e)]
    if not cands:
        return None
    return max(cands)[1]


# ---------------------------------------------------------------- readers

def parse_nm(text):
    """Yield (member, name, letter) for each symbol line of llvm-nm posix output."""
    member = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.endswith(':') and ' ' not in line:
            member = line[:-1]
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        yield member, parts[0], parts[1]


def _parse_readobj_one(text):
    """COMDAT, section and weak-external facts for one COFF object."""
    comdat, secof, seclen, weakext, secsel = set(), {}, {}, set(), {}

    def finish(sym):
        name = sym.get('Name', '')
        section = sym.get('Section', '').split(' (')[0]
        storage = sym.get('StorageClass', '').split(' (')[0]
        aux = sym.get('aux', {})
        length = int(aux['Length']) if aux.get('Length', '').isdigit() else None
        if storage == 'Static' and name == section:
            if length is not None:
                seclen[name] = length
            if 'Selection' in aux:
                secsel[name] = aux['Selection'].split(' (')[0]
        if storage == 'External':
            secof[name] = section
            if '$' in section and section.split('$', 1)[1] == name:
                comdat.add(name)
        if storage == 'WeakExternal':
            weakext.add(name)

    cur, aux = None, None
    for raw in text.splitlines():
        line = raw.strip()
        if line == 'Symbol {':
            cur, aux = {}, None
        elif cur is None:
            continue
        elif line == 'AuxSectionDef {':
            aux = {}
        elif line == '}':
            if aux is not None:
                cur['aux'] = aux
                aux = None
            else:
                finish(cur)
                cur = None
        else:
            key, _sep, val = line.partition(': ')
            if aux is not None:
                aux[key] = val
            else:
                cur[key] = val
    return {'comdat': comdat, 'secof': secof, 'seclen': seclen,
            'weakext': weakext, 'secsel': secsel}


def parse_readobj(text):
    """Split llvm-readobj --symbols output by member (archives) or single object.

    Returns {member_basename_or_None: info}. Archive output starts each member
    with a 'File: <archive>(<member>)' line; a plain object has no such line.
    """
    chunks, member, buf = {}, None, []
    for line in text.splitlines():
        if line.startswith('File: '):
            if buf:
                chunks[member] = _parse_readobj_one('\n'.join(buf))
            buf = []
            inner = line[len('File: '):]
            if inner.endswith(')') and '(' in inner:
                member = inner[inner.rfind('(') + 1:-1]
            else:
                member = None
        else:
            buf.append(line)
    if buf or not chunks:
        chunks[member] = _parse_readobj_one('\n'.join(buf))
    return chunks


def scan_member(job):
    """Read one object or archive. Runs in a worker thread."""
    path, rel, cat_hint, nm, readobj = job
    rc, dtext = run([nm, '--format=posix', '-g', '--defined-only', path])
    rc2, utext = run([nm, '--format=posix', '-g', '--undefined-only', path])
    errors = int(rc != 0) + int(rc2 != 0)
    infos = {}
    if readobj and cat_hint != 'implib':
        rc3, rtext = run([readobj, '--symbols', path])
        if rc3 == 0:
            infos = parse_readobj(rtext)
        else:
            errors += 1

    def info_for(member):
        return infos.get(member, EMPTY_INFO)

    implib = cat_hint == 'implib'
    defs, implib_names, letters = [], set(), collections.Counter()
    for member, name, letter in parse_nm(dtext):
        if implib:
            if name.startswith('__imp_'):
                implib_names.add(name[len('__imp_'):])
            continue
        if is_artifact(name):
            continue
        info = info_for(member)
        is_comdat = name in info['comdat']
        sec = info['secof'].get(name, '')
        sel = info['secsel'].get(sec) if is_comdat else None
        weak = (sel in WEAK_SELECTIONS or name in info['weakext']
                or letter in ('W', 'V', 'w', 'v'))
        length = info['seclen'].get(sec) if is_comdat else None
        oid = rel if member is None else '%s(%s)' % (rel, member)
        defs.append((name, oid, weak, length, sel, member is not None, letter))
        letters[letter] += 1

    undefs = set()
    for _member, name, _letter in parse_nm(utext):
        if not is_artifact(name):
            undefs.add(name)

    return {
        'rel': rel,
        'cat': cat_hint,
        'implib': implib,
        'defs': defs,
        'undefs': undefs,
        'implib_names': implib_names,
        'letters': letters,
        'errors': errors,
        'ncomdat': sum(len(i['comdat']) for i in infos.values()),
    }


# ---------------------------------------------------------------- scanning

class Scan:
    def __init__(self, label):
        self.label = label
        self.objects = []
        self.defs = collections.defaultdict(list)   # name -> [Def]
        self.undefs = collections.defaultdict(set)  # name -> {cat}
        self.implib_names = set()
        self.dem = {}
        self.linked = None         # None in tree mode, else the link-edge object set
        self.unlinked = collections.Counter()
        self.exe = None
        self.letters = collections.Counter()

    def merged_defs(self):
        out = {}
        for name, entries in self.defs.items():
            keep = [e for e in entries if e.cat not in EXCLUDED_CATS]
            if keep:
                out[name] = keep
        return out


def scan_build(label, root, nm, readobj, jobs, cxxfilt, mode, exe_wanted):
    cmap = load_compile_map(root)
    scan = Scan(label)
    edges = find_link_edges(root) if mode == 'linked' else {}
    exe = pick_exe(edges, exe_wanted) if mode == 'linked' else None
    if mode == 'linked' and exe is None:
        print('note: %s: no executable link edge found, using tree mode' % label, file=sys.stderr)
    link_objs, link_archives = edges[exe] if exe else (None, None)
    scan.exe = exe
    scan.linked = link_objs

    jobs_list = []
    for path in discover(root):
        rel = os.path.relpath(path, root).replace('\\', '/')
        key = norm(path)
        cat = classify_source(cmap[key]) if key in cmap else classify_object_path(path)
        if path.lower().endswith('.dll.a'):
            cat = 'implib'
        if exe is not None:
            if key not in link_objs and key not in link_archives:
                scan.unlinked[cat] += 1
                continue
            if cat == 'implib':
                continue
        jobs_list.append((path, rel, cat, nm, readobj))

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for res in pool.map(scan_member, jobs_list):
            scan.objects.append({
                'id': res['rel'], 'cat': res['cat'], 'defined': len(res['defs']),
                'undefined': len(res['undefs']), 'comdat': res['ncomdat'],
                'errors': res['errors'],
            })
            scan.letters.update(res['letters'])
            scan.implib_names |= res['implib_names']
            if res['implib']:
                continue
            for name, oid, weak, length, sel, arch, letter in res['defs']:
                scan.defs[name].append(Def(oid, res['cat'], weak, length, sel, arch, letter))
            for name in res['undefs']:
                scan.undefs[name].add(res['cat'])

    if cxxfilt:
        names = sorted(set(scan.defs) | set(scan.undefs))
        rc, out = run([cxxfilt], stdin_text='\n'.join(names) + '\n')
        dem_lines = out.split('\n')
        if rc == 0 and len(dem_lines) >= len(names):
            scan.dem = dict(zip(names, dem_lines))
    return scan


# ---------------------------------------------------------------- demangled parsing

def strip_templates(s):
    out, depth = [], 0
    for c in s:
        if c == '<':
            depth += 1
        elif c == '>' and depth:
            depth -= 1
        elif depth == 0:
            out.append(c)
    return ''.join(out)


def last_scope_index(s):
    """Index of the last '::' at template/paren depth zero, or -1."""
    depth, found, i = 0, -1, 0
    while i < len(s):
        c = s[i]
        if c in '<([{':
            depth += 1
        elif c in '>)]}':
            depth -= 1
        elif depth == 0 and s.startswith('::', i):
            found = i
            i += 2
            continue
        i += 1
    return found


def head_of(s):
    depth = 0
    for i, c in enumerate(s):
        if c == '<':
            depth += 1
        elif c == '>' and depth:
            depth -= 1
        elif c == '(' and depth == 0:
            return s[:i]
    return s


def parse_dem(dem):
    """Return (kind, owner, signature) for class-level symbols, else None."""
    dem = dem.replace('(anonymous namespace)', '{anon}')
    for prefix, kind in (('vtable for ', 'vtable'),
                         ('typeinfo name for ', 'typeinfo-name'),
                         ('typeinfo for ', 'typeinfo')):
        if dem.startswith(prefix):
            return kind, dem[len(prefix):], None
    head = head_of(dem)
    idx = last_scope_index(head)
    if idx < 0:
        return None
    owner, member = head[:idx], head[idx + 2:]
    base = strip_templates(owner)
    bidx = last_scope_index(base)
    last = base[bidx + 2:] if bidx >= 0 else base
    mbase = strip_templates(member)
    kind = 'ctor' if (mbase.startswith('~') or mbase == last) else 'method'
    return kind, owner, dem


def name_kind(name, dem):
    """Third-party or special name classes, or None."""
    if dem and (dem.startswith('operator new') or dem.startswith('operator delete')):
        return 'global:operator-new-delete'
    if dem:
        if dem.startswith(LIBCXX_DEM):
            return 'third-party:libc++'
    elif LIBCXX_MANGLED.search(name):
        return 'third-party:libc++'
    if name.startswith(CRT_PREFIXES):
        return 'third-party:crt'
    if RUST_HASH.search(name):
        return 'third-party:rust'
    return None


def sdk_kind(name):
    for label, pat in SDK_PATTERNS:
        if pat.search(name):
            return label
    return 'sdk:other'


def pair_group(cats_a, cats_b):
    allc = cats_a | cats_b
    if allc & {'host', 'host-copy', 'rust-kazarov'}:
        return 'host-layer'
    if 'sce' in allc:
        return 'sce-shim'
    if 'rust' in allc:
        return 'third-party:rust'
    if 'game' in allc and 'port' in allc:
        return 'game-vs-port'
    if allc == {'game'}:
        return 'game-vs-game'
    if allc == {'port'}:
        return 'port-vs-port'
    return 'other'


def side_state(entries):
    if any(not e.weak and not e.arch for e in entries):
        return 'plain'
    if any(not e.weak for e in entries):
        return 'archive'
    return 'weak'


def link_effect(sa, sb):
    states = {sa, sb}
    if sa == 'plain' and sb == 'plain':
        return 'hard-link-error'
    if states == {'weak'}:
        return 'silent-first-wins'
    if 'plain' in states and 'weak' in states:
        return 'silent-strong-wins'
    return 'archive-pull-dependent'


def pair_label(cats):
    return '+'.join(sorted(cats))


# ---------------------------------------------------------------- analysis

def build_summary(scan):
    merged = scan.merged_defs()
    cat_names = collections.Counter()
    strong_names = weak_only = multi_strong = archive_only_strong = 0
    game_port_overlap = collections.Counter()
    selections = collections.Counter()
    for name, entries in merged.items():
        cats = {e.cat for e in entries}
        for c in cats:
            cat_names[c] += 1
        for e in entries:
            if e.weak and e.sel:
                selections[e.sel] += 1
        strong = [e for e in entries if not e.weak]
        if strong:
            strong_names += 1
            if all(e.arch for e in strong):
                archive_only_strong += 1
        else:
            weak_only += 1
        # Strong duplicates inside plain (non-archive) objects of one build.
        plain_strong = [e for e in strong if not e.arch and e.cat not in ('rust', 'rust-kazarov')]
        if len(plain_strong) > 1:
            multi_strong += 1
        if 'game' in cats and cats & {'port', 'host', 'host-copy', 'sce'}:
            game_port_overlap['strong' if plain_strong else 'weak-only'] += 1
    resolved = set(scan.defs) | scan.implib_names
    unresolved = [n for n in scan.undefs if n not in resolved]
    unres_kind = collections.Counter(
        (name_kind(n, scan.dem.get(n)) or sdk_kind(n)) for n in unresolved)
    obj_cats = collections.Counter(o['cat'] for o in scan.objects if o['cat'] != 'implib')
    undef_cats = collections.Counter(c for cats in scan.undefs.values() for c in cats)
    return {
        'undefined_names_by_category': dict(sorted(undef_cats.items())),
        'mode': 'linked' if scan.linked is not None else 'tree',
        'exe': scan.exe,
        'analysed_objects_by_category': dict(sorted(obj_cats.items())),
        'unlinked_objects_by_category': dict(sorted(scan.unlinked.items())),
        'implib_objects': sum(1 for o in scan.objects if o['cat'] == 'implib'),
        'read_errors': sum(o['errors'] for o in scan.objects),
        'comdat_external_symbols': sum(o['comdat'] for o in scan.objects),
        'comdat_selection_on_defs': dict(selections),
        'letters': dict(scan.letters.most_common()),
        'defined_unique_merged': len(merged),
        'defined_unique_by_category': dict(sorted(cat_names.items())),
        'defined_strong_names': strong_names,
        'defined_weak_only_names': weak_only,
        'defined_archive_only_strong_names': archive_only_strong,
        'names_strong_in_2plus_plain_objects': multi_strong,
        'game_port_overlap_within_build': dict(game_port_overlap),
        'undefined_unique': len(scan.undefs),
        'undefined_unresolved_in_tree': len(unresolved),
        'undefined_unresolved_kinds': dict(unres_kind),
        'unresolved_names': sorted(unresolved),
        'implib_names': len(scan.implib_names),
    }


def cross_collisions(a, b):
    ma, mb = a.merged_defs(), b.merged_defs()
    records = []
    for name in set(ma) & set(mb):
        ea, eb = ma[name], mb[name]
        cats_a = {e.cat for e in ea}
        cats_b = {e.cat for e in eb}
        dem = a.dem.get(name) or b.dem.get(name)
        if 'rust-kazarov' in cats_a | cats_b:
            group = pair_group(cats_a, cats_b)
        else:
            group = name_kind(name, dem) or pair_group(cats_a, cats_b)
        sa, sb = side_state(ea), side_state(eb)
        kinds = {'code' if e.letter in CODE_LETTERS else 'data' for e in ea + eb}
        records.append({
            'name': name,
            'demangled': dem if dem and dem != name else None,
            'group': group,
            'effect': link_effect(sa, sb),
            'kind': kinds.pop() if len(kinds) == 1 else 'mixed',
            'pair': '%s / %s' % (pair_label(cats_a), pair_label(cats_b)),
            'a_state': sa,
            'b_state': sb,
        })
    return records


def undef_crosses(a, b):
    """Names one build references, leaves unresolved, and only the other defines."""
    out = {}
    for x, y in ((a, b), (b, a)):
        ymerged = y.merged_defs()
        resolved = set(x.defs) | x.implib_names
        hits = sorted(n for n in x.undefs if n not in resolved and n in ymerged)
        out['%s_needs_from_%s' % (x.label, y.label)] = hits
    return out


def class_model(scan):
    merged = scan.merged_defs()
    owners = {}
    for name, entries in merged.items():
        dem = scan.dem.get(name)
        if not dem:
            continue
        parsed = parse_dem(dem)
        if parsed is None:
            continue
        kind, owner, sig = parsed
        if kind in ('typeinfo', 'typeinfo-name'):
            rec = owners.setdefault(owner, _new_owner())
            rec['typeinfo'] = True
            continue
        rec = owners.setdefault(owner, _new_owner())
        length = next((e.length for e in entries if e.length is not None), None)
        if kind == 'vtable':
            rec['vtable_len'] = length
            rec['has_vtable'] = True
        else:
            if kind == 'ctor':
                rec['ctor'] = True
            rec['methods'][sig] = length
    return {o: r for o, r in owners.items() if r['ctor'] or r['has_vtable'] or r['typeinfo']}


def _new_owner():
    return {'vtable_len': None, 'has_vtable': False, 'typeinfo': False,
            'ctor': False, 'methods': {}}


def is_libcxx_owner(owner):
    return owner.startswith('std::') or '__1::' in owner or owner.startswith('std')


def compare_classes(ca, cb):
    common = sorted(set(ca) & set(cb))
    states = collections.Counter()
    rows = []
    for owner in common:
        if is_libcxx_owner(owner):
            states['libc++ (skipped)'] += 1
            continue
        a, b = ca[owner], cb[owner]
        va, vb = a['vtable_len'], b['vtable_len']
        if a['has_vtable'] and b['has_vtable']:
            if va is None or vb is None:
                vt = 'vtable-length-unknown'
            else:
                vt = 'vtable-same-length' if va == vb else 'vtable-length-differs'
        elif a['has_vtable'] or b['has_vtable']:
            vt = 'vtable-one-side'
        else:
            vt = 'no-vtable'
        sa, sb = set(a['methods']), set(b['methods'])
        only_a, only_b, both = sa - sb, sb - sa, sa & sb
        code_diff = 0
        for sig in both:
            la, lb = a['methods'][sig], b['methods'][sig]
            if la is not None and lb is not None and la != lb:
                code_diff += 1
        if only_a or only_b or vt in ('vtable-length-differs', 'vtable-one-side'):
            state = 'surface-or-vtable-differs'
        elif code_diff:
            state = 'same-surface-code-length-differs'
        else:
            state = 'same-surface'
        states[state] += 1
        rows.append({'owner': owner, 'state': state, 'vtable': vt,
                     'methods_a': len(sa), 'methods_b': len(sb),
                     'only_a': len(only_a), 'only_b': len(only_b),
                     'code_length_differs': code_diff})
    rows.sort(key=lambda r: -(r['only_a'] + r['only_b'] + r['code_length_differs']))
    return states, rows, len(common)


def read_receipts(folder, labels):
    out = {}
    for name in list(labels) + ['common']:
        path = os.path.join(folder, name + '.syms')
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8', errors='replace') as fh:
            names = set(line.strip() for line in fh if line.strip())
        out[name] = names
    return out


def receipt_summary(rec, la, lb, a=None, b=None):
    if la not in rec or lb not in rec:
        return None
    sa, sb = rec[la], rec[lb]
    inter = sa & sb
    artifacts = {n for n in inter if is_artifact(n)}
    summary = {
        '%s_names' % la: len(sa), '%s_names' % lb: len(sb),
        'intersection': len(inter),
        'intersection_artifacts': len(artifacts),
        'intersection_real': len(inter) - len(artifacts),
        'intersection_mangled': sum(1 for n in inter if n.startswith('_Z')),
    }
    if a is not None and b is not None:
        ma, mb = a.merged_defs(), b.merged_defs()
        breakdown = collections.Counter()
        for n in inter:
            if is_artifact(n):
                breakdown['linker artifact'] += 1
            elif n in ma and n in mb:
                breakdown['defined in both merged sets (cross collision)'] += 1
            elif n in ma or n in mb:
                breakdown['defined in one merged set, other side imports or uses'] += 1
            elif n in a.undefs and n in b.undefs:
                kind = name_kind(n, a.dem.get(n) or b.dem.get(n)) or sdk_kind(n)
                breakdown['undefined on both sides, ' + kind] += 1
            else:
                breakdown['other (supplied by a library on one side)'] += 1
        summary['intersection_breakdown'] = dict(sorted(breakdown.items()))
    if 'common' in rec:
        summary['common_file_equals_intersection'] = rec['common'] == inter
    return summary


# ---------------------------------------------------------------- report

EFFECT_RANK = {'hard-link-error': 0, 'silent-strong-wins': 1,
               'archive-pull-dependent': 2, 'silent-first-wins': 3}


def md_table(rows, headers):
    lines = ['| ' + ' | '.join(headers) + ' |', '|' + '|'.join('---' for _ in headers) + '|']
    for row in rows:
        lines.append('| ' + ' | '.join(str(x) for x in row) + ' |')
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--build-a', required=True, help='build tree for build A')
    ap.add_argument('--build-b', required=True, help='build tree for build B')
    ap.add_argument('--nm', required=True, help='path to llvm-nm (or llvm-nm.exe)')
    ap.add_argument('--readobj', help='llvm-readobj (default: sibling of --nm)')
    ap.add_argument('--cxxfilt', help='llvm-cxxfilt (default: sibling of --nm)')
    ap.add_argument('--label-a', default='a')
    ap.add_argument('--label-b', default='b')
    ap.add_argument('--mode', choices=('linked', 'tree'), default='linked',
                    help='linked: game exe link-edge inputs from build.ninja (default); '
                         'tree: every object in the tree minus test/tool')
    ap.add_argument('--exe-a', help='executable link edge for build A (default: largest)')
    ap.add_argument('--exe-b', help='executable link edge for build B (default: largest)')
    ap.add_argument('--receipts', help='folder holding <label>.syms and common.syms')
    ap.add_argument('--json', help='write full detail (names, classes) to this file')
    ap.add_argument('--examples', type=int, default=12, help='examples per group')
    ap.add_argument('--jobs', type=int, default=8)
    args = ap.parse_args(argv)

    readobj = args.readobj or sibling(args.nm, 'llvm-readobj')
    if not os.path.exists(readobj):
        print('note: llvm-readobj not found; COMDAT detection disabled', file=sys.stderr)
        readobj = None
    cxxfilt = args.cxxfilt or sibling(args.nm, 'llvm-cxxfilt')
    if not os.path.exists(cxxfilt):
        print('note: llvm-cxxfilt not found; class and libc++ analysis disabled', file=sys.stderr)
        cxxfilt = None

    a = scan_build(args.label_a, args.build_a, args.nm, readobj, args.jobs, cxxfilt,
                   args.mode, args.exe_a)
    b = scan_build(args.label_b, args.build_b, args.nm, readobj, args.jobs, cxxfilt,
                   args.mode, args.exe_b)

    sa, sb = build_summary(a), build_summary(b)
    records = cross_collisions(a, b)
    groups = collections.Counter(r['group'] for r in records)
    group_effect = collections.Counter((r['group'], r['effect']) for r in records)
    pairs = collections.Counter((r['group'], r['pair']) for r in records)
    kinds = collections.Counter((r['kind'], r['effect']) for r in records)
    unders = undef_crosses(a, b)

    ca, cb = class_model(a), class_model(b)
    class_states, class_rows, class_common = compare_classes(ca, cb)

    rec = read_receipts(args.receipts, [args.label_a, args.label_b]) if args.receipts else {}
    rsum = receipt_summary(rec, args.label_a, args.label_b, a, b)

    la, lb = args.label_a, args.label_b
    print('# Symbol collisions: %s vs %s\n' % (la, lb))
    print('Scope: %s; executables: %s = %s, %s = %s\n' % (
        args.mode, la, a.exe or '(tree)', lb, b.exe or '(tree)'))
    print('## Build inventory\n')
    rows = []
    for label, s in ((la, sa), (lb, sb)):
        rows.append([label, s['defined_unique_merged'], s['defined_strong_names'],
                     s['defined_weak_only_names'], s['defined_archive_only_strong_names'],
                     s['names_strong_in_2plus_plain_objects'], s['undefined_unique'],
                     s['undefined_unresolved_in_tree'], s['read_errors'],
                     s['comdat_external_symbols']])
    print(md_table(rows, ['build', 'defined names (merged)', 'with strong def', 'weak-only',
                          'archive-only strong', 'strong in 2+ plain objects', 'undefined names',
                          'unresolved in tree', 'read errors', 'COMDAT-flagged externals']))
    print()
    for label, s in ((la, sa), (lb, sb)):
        print('%s analysed objects by category: %s' % (label, s['analysed_objects_by_category']))
        print('%s unlinked objects by category: %s' % (label, s['unlinked_objects_by_category']))
        print('%s defined names by category: %s' % (label, s['defined_unique_by_category']))
        print('%s symbol letters: %s' % (label, s['letters']))
        print('%s COMDAT selections on weak defs: %s' % (label, s['comdat_selection_on_defs']))
        print('%s game/port overlap inside build: %s' % (label, s['game_port_overlap_within_build']))
        print('%s unresolved kinds: %s' % (label, s['undefined_unresolved_kinds']))
        print('%s undefined names referenced by category: %s\n' % (label, s['undefined_names_by_category']))

    print('## Cross-build collisions (names defined by both merged sets)\n')
    print('Total: %d' % len(records))
    rows = []
    for (g, e), n in sorted(group_effect.items(), key=lambda x: (x[0][0], EFFECT_RANK[x[0][1]])):
        rows.append([g, e, n])
    print(md_table(rows, ['group', 'link effect if merged', 'names']))
    print()
    rows = [[g, p, n] for (g, p), n in sorted(pairs.items(), key=lambda x: (x[0][0], -x[1]))]
    print(md_table(rows, ['group', 'pair (%s / %s)' % (la, lb), 'names']))
    print()
    rows = [[k, e, n] for (k, e), n in sorted(kinds.items(), key=lambda x: (x[0][0], EFFECT_RANK[x[0][1]]))]
    print(md_table(rows, ['kind (code or data)', 'link effect', 'names']))
    print()

    print('## Examples per group (most severe first)\n')
    by_group = collections.defaultdict(list)
    for r in records:
        by_group[r['group']].append(r)
    for g in sorted(by_group):
        print('### %s' % g)
        ordered = sorted(by_group[g], key=lambda x: (EFFECT_RANK[x['effect']], x['name']))
        for r in ordered[:args.examples]:
            dem = r['demangled'] or r['name']
            print('- `%s` (%s, %s)' % (dem[:160], r['pair'], r['effect']))
        print()

    print('## Classes (owners of ctor, dtor, vtable or typeinfo)\n')
    print('Classes per build: %s=%d, %s=%d; defined by both (excluding libc++): %d' % (
        la, len(ca), lb, len(cb), class_common))
    rows = [[k, v] for k, v in sorted(class_states.items())]
    print(md_table(rows, ['class state', 'classes']))
    print()
    print('Top divergent classes:')
    for r in class_rows[:args.examples]:
        if r['state'] == 'same-surface':
            continue
        print('- `%s`: %s; methods %s/%s, only-%s %d, only-%s %d, code-length diffs %d, %s' % (
            r['owner'][:120], r['state'], r['methods_a'], r['methods_b'],
            la, r['only_a'], lb, r['only_b'], r['code_length_differs'], r['vtable']))
    print()

    print('## Undefined-name crosses\n')
    for k, v in unders.items():
        print('- %s: %d (examples: %s)' % (k, len(v), ', '.join(v[:5]) or 'none'))
    print()

    if rsum:
        print('## Executable-level receipts\n')
        for k, v in rsum.items():
            print('- %s: %s' % (k, v))
        print()

    if args.json:
        detail = {
            'labels': [la, lb],
            'mode': args.mode,
            'exes': {la: a.exe, lb: b.exe},
            'builds': {la: {k: v for k, v in sa.items() if k != 'unresolved_names'},
                       lb: {k: v for k, v in sb.items() if k != 'unresolved_names'}},
            'cross_groups': {'%s|%s' % k: v for k, v in group_effect.items()},
            'cross_pairs': {'%s|%s' % k: v for k, v in pairs.items()},
            'cross_records': records,
            'cross_kinds': {'%s|%s' % k: v for k, v in kinds.items()},
            'class_states': dict(class_states),
            'class_rows': class_rows,
            'undefined_crosses': unders,
            'unresolved_names': {la: sa['unresolved_names'], lb: sb['unresolved_names']},
            'receipts': rsum,
        }
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump(detail, fh, indent=1, sort_keys=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
