#!/usr/bin/env python3
"""Generate Visual Studio 18 IntelliSense AutoPCH files (.vs/<sln>/v18/ipch/AutoPCH/<hash>/<STEM>.ipch).

Usage:
  gen_ipch.py SOLUTION_DIR [--win-root C:\\Users\\me\\source\\repos] [--config Debug] [--platform x64]
              [--sources Main.cpp Visit.cpp ...] [--size-mb N] [--dry-run]

What is exact and what is approximate is documented in NOTES.md.
Timestamps stored inside the file are the real st_mtime of your project headers; nothing is faked.
The file body (the EDG memory image) cannot be produced without the compiler: it is written as a
sparse zero region of a plausible size, or truncated to --size-mb.
"""
import argparse, json, os, re, struct, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
M64 = (1 << 64) - 1
BANNER = b'EDG C/C++ version 6.8 (Aug 27 2026 10:05:40)\n\0'   # exact, offset 0x00, 0x2c bytes
SYS_MTIME_MSVC = 0x6aa2ff9f      # mtime seen on MSVC 14.51.36231 headers in the reference install
SYS_MTIME_UCRT = 0x69dfab9c      # mtime seen on Windows SDK 10.0.26100.0 ucrt headers


def fnv1a64(b):
    h = 0xcbf29ce484222325
    for c in b:
        h = ((h ^ c) * 0x100000001b3) & M64
    return h


def dir_hash(win_source_path):
    """AutoPCH directory name: lowercase hex (no zero padding) of FNV-1a 64 over the UPPERCASED
    Windows source path, UTF-8, no terminator. Verified on 4/4 reference files."""
    return '%x' % fnv1a64(win_source_path.upper().encode('utf-8'))


def load_ref():
    return json.load(open(os.path.join(HERE, 'refdata.json')))


# ---------------------------------------------------------------- include parsing
INC = re.compile(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]')


def read_lines(p):
    try:
        return open(p, encoding='utf-8-sig', errors='replace').read().split('\n')
    except OSError:
        return []


def leading_includes(path):
    """The leading include block of a .cpp: (text-as-written, 1-based line). Comments and blank lines
    are skipped; the block ends at the first other line."""
    out = []; in_block = False
    for n, ln in enumerate(read_lines(path), 1):
        s = ln.strip().rstrip('\r')
        if in_block:
            if '*/' in s: in_block = False
            continue
        if s.startswith('/*'):
            if '*/' not in s: in_block = True
            continue
        if not s or s.startswith('//'): continue
        m = INC.match(s)
        if not m: break
        out.append((m.group(1) + m.group(2) + (m.group(1) == '<' and '>' or '"'), n))
    return out


def all_includes(path):
    res = []
    for ln in read_lines(path):
        m = INC.match(ln.rstrip('\r'))
        if m: res.append((m.group(1), m.group(2)))
    return res


# ---------------------------------------------------------------- system header closure model (approximate)
class SysModel:
    """Std header contribution model (approximate).

    Each reference file table is cut into segments at project headers and at the top-level std
    includes of that translation unit.  A segment keyed ('std', H) is "the system files first read
    when <H> is included".  The first public header after a project header is also registered under its
    own name (e.g. <iostream> from Date.h in DATE.cpp).  Generation concatenates segments in include
    order, de-duplicating, so the closure is right when contexts match the reference and plausible
    otherwise."""

    def __init__(self, ref):
        self.ref = ref
        self.mtime = {}
        self.seg = {}     # header -> list of (refname, [paths], context)
        for rn, r in ref['refs'].items():
            order = [n for n, _ in r['names']]
            ents = r['ents']
            # boundary index of each top-level include, scanning forward in source order
            pos = []; i = 0
            for n in order:
                bare = n[1:-1]
                while i < len(ents):
                    p = ents[i][0]
                    hit = (n[0] == '"' and p.upper().startswith('C:\\USERS\\') and p.endswith('\\' + bare)) or \
                          (n[0] == '<' and p.endswith('\\include\\' + bare))
                    i += 1
                    if hit: pos.append(i - 1); break
            pos.append(len(ents))
            for k, n in enumerate(order):
                if k >= len(pos) - 1: break
                raw = [p for p, t in ents[pos[k]:pos[k+1]]]
                if n[0] == '"':      # alias segment: stop at the next project header after the first system file
                    cut = []; started = False
                    for p in raw:
                        usr = p.upper().startswith('C:\\USERS\\')
                        if not usr: started = True
                        elif started: break
                        cut.append(p)
                    raw = cut
                seg = [p for p in raw if not p.upper().startswith('C:\\USERS\\')]
                for p, t in ents:
                    if not p.upper().startswith('C:\\USERS\\'): self.mtime[p] = t
                ctx = [x[1:-1] for x in order[:k] if x[0] == '<']
                if n[0] == '<':
                    self.seg.setdefault(n[1:-1], []).append((rn, seg, ctx))
                elif seg:
                    b0 = seg[0].split('\\include\\')[-1]
                    if '.' not in b0:
                        self.seg.setdefault(b0, []).append((rn, seg, ctx))

    def files_for(self, header, prev_tops):
        c = self.seg.get(header)
        if not c: return None
        return max(c, key=lambda x: (-len(set(x[2]) ^ set(prev_tops)), len(x[1])))[1]


def sys_path_guess(h, ref):
    return r'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\include' + '\\' + h


def build_file_table(src, proj_dir, proj_up, model, ref):
    """Ordered (path, mtime) list of every file the PCH prefix read. DFS over the includes."""
    seen = set(); out = []; prev_tops = []
    def add(p, t):
        if p not in seen:
            seen.add(p); out.append((p, t))
    def visit_header(fpath, depth=0):
        for kind, name in all_includes(fpath):
            if kind == '"':
                cand = os.path.join(os.path.dirname(fpath), name.replace('\\', '/'))
                if os.path.isfile(cand):
                    key = proj_up + '\\' + name.replace('/', '\\')
                    if key in seen: continue
                    add(key, int(os.stat(cand).st_mtime))
                    visit_header(cand, depth + 1)
                    continue
            h = name
            if sys_path_guess(h, ref) in seen:      # include guard: file already read, nothing new
                continue
            if h in prev_tops and depth == 0: continue
            prev_tops.append(h)
            fl = model.files_for(h, prev_tops[:-1])
            if fl is None: fl = [sys_path_guess(h, ref)]
            for p in fl: add(p, model.mtime.get(p, SYS_MTIME_MSVC))
    visit_header(src)
    return out


# ---------------------------------------------------------------- file assembly
def u32(x): return struct.pack('<I', x)


def front_matter(ref, subst, config):
    """Same as front_matter but writes the length field *inside* the preceding literal's tail correctly:
    in the stored format the u32 length precedes the string, and the literal tokens we saved stop right
    before that field, so the field is emitted here."""
    toks = ref['refs']['DATE']['toks']
    b = bytearray(); pend = False
    for t in toks:
        if t[0] == 'L':
            b += bytes.fromhex(t[1])
        else:
            s = t[1]
            if s.startswith('{') or '{' in s:
                s = (s.replace('{PROJ}', subst['PROJ']).replace('{PROJUP}', subst['PROJUP'])
                      .replace('{IPCH}', subst['IPCH']).replace('{OUTDIR}', subst['OUTDIR']))
            if config.lower() == 'release' and s == '_DEBUG': s = 'NDEBUG'
            b += u32(len(s) + 1) + s.encode() + b'\0'
    return b


def estimate_size(ref, nfiles):
    pts = sorted((len(r['ents']), r['size']) for r in ref['refs'].values())
    for n, s in pts:
        if n == nfiles: return s
    if nfiles <= pts[0][0]:
        n0, s0 = pts[0]; n1, s1 = pts[1]
    elif nfiles >= pts[-1][0]:
        n0, s0 = pts[-2]; n1, s1 = pts[-1]
    else:
        for (n0, s0), (n1, s1) in zip(pts, pts[1:]):
            if n0 <= nfiles <= n1: break
    est = s0 + (s1 - s0) * (nfiles - n0) / (n1 - n0)
    est = max(est, 40 << 20)
    return int(round(est / 65536.0)) * 65536


def estimate_tail(ref, nfiles):
    pts = sorted((len(r['ents']), r['n1'], r['n2'], r['prog']) for r in ref['refs'].values())
    for n, a, b, c in pts:
        if n == nfiles: return a, b, c
    n1 = 1000 if nfiles >= 140 else 500
    (na, _, nb, _), (nc, _, nd, _) = pts[0], pts[-1]
    n2 = int(round(nb + (nd - nb) * (nfiles - na) / float(nc - na)))
    prog = 59 if nfiles < 130 else (76 if nfiles < 140 else 87)
    return n1, max(n2, 100), prog


def build_ipch(src_abs, win_src, proj_dir_win, sln_dir_win, slnfile, proj_dir_local, config, platform, ref, model, size_override):
    h = dir_hash(win_src)
    proj_up = proj_dir_win.upper()
    ipchdir = sln_dir_win + '\\.vs\\' + slnfile + '\\v18\\ipch\\AutoPCH\\' + h
    # the stored strings already carry their own trailing backslashes (two for the mixed-case one, one for the upper-case one)
    subst = dict(PROJ=proj_dir_win, PROJUP=proj_up, IPCH=ipchdir, OUTDIR=platform + '\\' + config + '\\\\')
    b = bytearray(BANNER[:-1])           # the banner's NUL is the first byte of the stored front-matter literal
    b += front_matter(ref, subst, config)
    names = leading_includes(src_abs)
    for nm, line in names:
        b += u32(2) + u32(8) + u32(len(nm) + 1) + nm.encode() + b'\0' + u32(line) + u32(1)
    # last u32(1) written above belongs to the record trailer; terminator word and file table follow
    b += u32(0)
    ents = build_file_table(src_abs, proj_dir_local, proj_up, model, ref)
    for p, t in ents:
        b += u32(len(p) + 1) + p.encode() + b'\0' + u32(t & 0xffffffff) + u32(0)
    n1, n2, prog = estimate_tail(ref, len(ents))
    b += u32(0) + u32(0) + u32(n1) + u32(n2) + b'\0\0'
    for k in range(prog):
        b += u32(0x8401 + 4 * k) + u32(4)
    size = size_override or estimate_size(ref, len(ents))
    return h, bytes(b), size


def write_sparse(path, head, size):
    with open(path, 'wb') as f:
        f.write(head)
        f.truncate(max(size, len(head)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('solution_dir')
    ap.add_argument('--win-root', default=r'C:\Users\student\source\repos')
    ap.add_argument('--config', default='Debug')
    ap.add_argument('--platform', default='x64')
    ap.add_argument('--project-dir', help='project folder name inside the solution (default: auto)')
    ap.add_argument('--sources', nargs='*', help='which .cpp files get an ipch (default: files in DocumentLayout.json, else all .cpp)')
    ap.add_argument('--size-mb', type=float, help='force every ipch to this size instead of the estimate')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    sln_dir = os.path.abspath(a.solution_dir)
    sln_name = os.path.basename(sln_dir)
    slnfiles = glob.glob(sln_dir + '/*.slnx') + glob.glob(sln_dir + '/*.sln')
    if not slnfiles: sys.exit('no .slnx/.sln in ' + sln_dir)
    slnfile = os.path.basename(slnfiles[0])
    projs = [d for d in sorted(os.listdir(sln_dir)) if glob.glob(os.path.join(sln_dir, d, '*.vcxproj'))]
    proj = a.project_dir or projs[0]
    proj_local = os.path.join(sln_dir, proj)
    sln_win = a.win_root.rstrip('\\') + '\\' + sln_name
    proj_win = sln_win + '\\' + proj
    ref = load_ref(); model = SysModel(ref)
    if a.sources:
        srcs = a.sources
    else:
        srcs = []
        dl = os.path.join(sln_dir, '.vs', slnfile, 'v18', 'DocumentLayout.json')
        if os.path.isfile(dl):
            for m in re.finditer(r'"DocumentMoniker": "[^"]*\\\\([^"\\]+\.cpp)"', open(dl).read()):
                if m.group(1) not in srcs: srcs.append(m.group(1))
        if not srcs:
            srcs = sorted(f for f in os.listdir(proj_local) if f.lower().endswith('.cpp'))
    root = os.path.join(sln_dir, '.vs', slnfile, 'v18', 'ipch', 'AutoPCH')
    for s in srcs:
        s_abs = os.path.join(proj_local, s)
        if not os.path.isfile(s_abs):
            print('skip (missing):', s); continue
        win_src = proj_win + '\\' + s
        size = int(a.size_mb * 1048576) if a.size_mb else None
        h, head, sz = build_ipch(s_abs, win_src, proj_win, sln_win, slnfile, proj_local, a.config, a.platform, ref, model, size)
        stem = os.path.splitext(s)[0].upper()
        out = os.path.join(root, h, stem + '.ipch')
        print('%s/%s.ipch  head=%d bytes  size=%d' % (h, stem, len(head), sz))
        if a.dry_run: continue
        os.makedirs(os.path.dirname(out), exist_ok=True)
        write_sparse(out, head, sz)


if __name__ == '__main__':
    main()
