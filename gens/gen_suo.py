#!/usr/bin/env python3
"""Generate .vs/<sln>/v18/.suo (OLE2 compound file) like Visual Studio 18 writes it.

Usage:
  gen_suo.py SOLUTION_DIR [--win-repos-root 'C:\\Users\\me\\source\\repos']
             [--docs Main.cpp Employee.cpp ...] [--config Debug|x64]

Pure python, no dependencies (writes its own CFB v3 container).  Stream by
stream fidelity is documented in NOTES.md.
"""
import argparse, datetime, hashlib, os, struct, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_layout as L
from suo_consts import CONST

FREE, EOC, FATSEC = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD


def u16(s): return s.encode("utf-16le")
def u32(n): return struct.pack("<I", n)
def guid_le(g): return uuid.UUID(g).bytes_le
def nstr(s): return u16(s + "\0")          # nul terminated utf16


def gstr(g): return "{%s}" % g


def pstr7(s):
    """.NET BinaryWriter style string: 7-bit varint byte length + utf8."""
    b = s.encode("utf-8"); n = len(b); out = bytearray()
    while True:
        c = n & 0x7F; n >>= 7
        out.append(c | (0x80 if n else 0))
        if not n: break
    return bytes(out) + b


# ---------------------------------------------------------------- streams
def s_solution_configuration(p, active):
    gid = gstr(p["guid"])
    items = []
    def d(k, v): items.append((k, 3, v))
    def s(k, v): items.append((k, 8, v))
    d("MultiStartupProj", 0)
    s(gid, p["proj_rel"])
    s("Path." + p["proj_rel"], gid)
    d(gid + ".dwStartupOpt", 0)
    s("StartupProject", gid)
    cfgs = sorted(p["configs"], key=lambda c: c[0], reverse=True)   # Release before Debug, as VS wrote it
    for c, pl in cfgs:
        d("%s.%s|%s.fBatchBld" % (gid, c, pl), 0)
    s("ActiveCfg", active)
    out = u32(1) + u16("#") + u16("=") + struct.pack("<H", 3) + u32(len(items))
    for k, t, v in items:
        out += u16(";") + u32(len(k)) + u16(k) + u16("=") + struct.pack("<H", t)
        out += u32(v) if t == 3 else u32(len(v)) + u16(v)
    out += u16(";")
    return out


def to_mru_path(p, absn):
    prof = "C:\\Users\\"
    parts = absn.split("\\")
    if absn.lower().startswith(prof.lower()) and len(parts) > 3:
        return "%UserProfile%\\" + "\\".join(parts[3:])
    return absn


def s_mru(p, mru):           # mru: list of (name, line, col) in stored order
    ents = b""
    for name, line, col in mru:
        t = "%s|{00000000-0000-0000-0000-000000000000}|%d,%d|False" % (to_mru_path(p, L.win_doc(p, name)[0]), line, col)
        ents += u32(len(t)) + t.encode("ascii")
    body = u32(15) + struct.pack("<HH", len(mru) - 1, len(mru)) + ents
    return u32(len(body) + 4) + body


def s_outlining(p, names, ids, hashes):
    """returns (dir_stream, {OutliningStateV<id+1670>: bytes})"""
    streams = {}
    dirb = u32(max(ids) + 1)
    for name, i in zip(names, ids):
        path = L.win_doc(p, name)[0]
        pb = nstr(path)
        dirb += struct.pack("<H", len(pb)) + pb + u32(i)
        raw = u16(path)
        streams["OutliningStateV167%d" % i] = (bytes([len(raw)]) + b"\x01" + raw + hashes[name]
                                                      + u32(0) + b"\xff" * 16)
    return dirb + b"\0\0", streams


def s_proj_explorer(p, selected_name, item_id=0x55):
    pn = u16(p["proj_name"])
    seg1 = b"\x01\x00\x00\x01\x00" + bytes([len(pn)]) + pn + struct.pack("<H", 1 + len(p["filters"]))
    seg1 += bytes([len(pn)]) + pn
    for f in p["filters"]:
        t = u16("%s;%s" % (f, p["proj_name"]))
        seg1 += bytes([len(t)]) + t
    vp = u16(p["win_sol_dir"] + (p["proj_dir_rel"] + "\\" if p["proj_dir_rel"] else "") + p["proj_name"] + ".vcxproj")
    dp = u16(L.win_doc(p, selected_name)[0])
    z = u16("00000000-0000-0000-0000-000000000000")
    tag = lambda b: struct.pack("<H", len(b) | 0x100) + b
    seg2 = (u32(1) + u32(1) + tag(vp) + u32(1) + tag(dp) + u32(item_id) + u32(1)
            + bytes([len(z)]) + z + u32(0))
    first = 8 + len(seg1)
    return u32(first) + u32(0x10) + seg1 + u32(len(vp) + len(dp) + 20) + seg2


def s_document_window_positions(p, docs, tabs, selected, views, group_guid="390681dd-a380-4d0b-93eb-11411b5a3cdb"):
    """docs: names in DocumentIndex order; tabs: indices in tab order; selected: DocumentIndex."""
    gid = gstr(p["guid"])
    pre = "D:0:0:%s|%s|" % (gid, p["proj_rel"])
    def monikers(name):
        a, r = L.win_doc(p, name)
        fac = L.doc_kind(name)[0]
        return (pstr7("%s%s||%s" % (pre, a, fac)), pstr7("%ssolutionrelative:%s||%s" % (pre, r, fac)))
    body = pstr7(group_guid) + struct.pack("<H", len(docs))
    for n in docs:
        body += b"".join(monikers(n))
    body += b"\x01\x00\x00\x01\x01\x00" + struct.pack("<d", 200.0)
    body += b"".join(monikers(docs[selected]))
    body += struct.pack("<H", len(tabs))
    for i in tabs:
        n = docs[i]; a, r = L.win_doc(p, n)
        body += b"\x44" + b"".join(monikers(n)) + pstr7(n)
        body += b"\x01" + pstr7(a) + pstr7(r) + b"\x01" + pstr7(a) + pstr7(r)
        icon = L.doc_kind(n)[1] if L.doc_kind(n)[0] == L.CPP_DOC_TYPE else "00000000-0000-0000-0000-000000000000.000000|"
        body += pstr7(icon) + b"\0" * 16
        body += struct.pack("<H", 28) + L.viewstate_bytes(views.get(n, (0, 0, 0)))
    body += u32(12) + u32(3) + u32(0)
    return u32(len(body) + 8) + u32(0x14) + body


def s_when_opened(rec):      # rec: list of (4 byte tag, datetime)
    out = u32(0) + u32(1) + u32(len(rec))
    for tag, dt in rec:
        ms = (dt - datetime.datetime(2019, 1, 1, tzinfo=datetime.timezone.utc)) / datetime.timedelta(milliseconds=1)
        out += tag + struct.pack("<d", ms)
    out += u32(0)
    return struct.pack("<I", len(out)) + out[4:]


def s_breakpoints(p):
    pb = nstr(p["win_sol_dir"])
    return u32(1) + u32(len(pb)) + pb + u32(0)




def build_streams(p, active="Debug|x64", docs=None, tabs=None, selected=0, views=None, when=None,
                  mru=None, outline_ids=None, load_count=1, tags=None, projinfo=None,
                  explorer_sel=None, group_guid=None):
    """Return an ordered dict {stream name: bytes}.  docs = DocumentIndex order."""
    docs = docs if docs is not None else p["docs"]
    tabs = tabs if tabs is not None else list(range(len(docs)))
    views = views or {}
    now = datetime.datetime.now(datetime.timezone.utc)
    when = when or [now - datetime.timedelta(seconds=len(docs) - i) for i in range(len(docs))]
    gb = guid_le(p["guid"])
    ids = outline_ids or list(range(1, len(docs) + 1))
    hashes = {n: hashlib.sha256(open(os.path.join(p["proj_dir"], n), "rb").read()).digest() for n in docs}
    odir, ostreams = s_outlining(p, docs, ids, hashes)
    mru = mru if mru is not None else [(n, views.get(n, (0, 0, 0))[1], views.get(n, (0, 0, 0))[2]) for n in docs]
    tags = tags or [hashlib.sha1(L.win_doc(p, n)[0].encode()).digest()[:4] for n in docs]
    S = dict(CONST)
    S["ProjInfoEx"] = projinfo or hashlib.md5((p["win_sol_dir"] + p["sol_file"]).encode("utf-16le")).digest()
    S["ProjectTrustInformation"] = gb + u32(load_count)
    S["VC Project Package 15.0"] = gb
    S["SccProvider.Solution.LoadCount"] = u32(load_count) + u32(0)
    S["SolutionConfiguration"] = s_solution_configuration(p, active)
    S["MRU Solution Files"] = s_mru(p, mru)
    S["DebuggerBreakpoints"] = s_breakpoints(p)
    S["OutliningStateDir"] = odir
    S.update(ostreams)
    S["ProjExplorerState"] = s_proj_explorer(p, explorer_sel or docs[selected])
    group_guid = group_guid or str(uuid.uuid4())      # VS uses a fresh random GUID per solution
    S["DocumentWindowPositions"] = s_document_window_positions(p, docs, tabs, selected, views, group_guid)
    S["WindowManager.WhenOpened"] = s_when_opened([(tags[i], when[i]) for i in range(len(docs))])
    return S


# ---------------------------------------------------------------- CFB v3 writer
def _key(name): return (len(name), name.upper())


def _tree(names):
    """balanced binary tree over sorted names; returns {name: (left,right,color)} (values are names)."""
    order = sorted(names, key=_key)
    info = {}
    def build(lo, hi, depth):
        if lo > hi: return None
        mid = (lo + hi + 1) // 2
        n = order[mid]
        l = build(lo, mid - 1, depth + 1); r = build(mid + 1, hi, depth + 1)
        info[n] = [l, r, depth]
        return n
    root = build(0, len(order) - 1, 0)
    maxd = max(v[2] for v in info.values()) if info else 0
    # complete levels black, deepest (possibly incomplete) level red when tree is not perfect
    full = (1 << (maxd + 1)) - 1 == len(order)
    for n, v in info.items():
        v[2] = 1 if (v[2] == maxd and not full and maxd > 0) else 0   # 1 = red
    return root, info


def write_cfb(path, streams, root_mtime=None):
    SS, MS, CUT = 512, 64, 4096
    names = list(streams)
    big = {n for n in names if len(streams[n]) >= CUT}
    sectors = []                     # list of 512 byte blocks, appended in order
    fat = []
    def alloc_chain(data, ss):
        n = max(1, -(-len(data) // ss)) if data else 0
        return n
    # mini stream
    mini, minifat, mstart = bytearray(), [], {}
    for n in names:
        d = streams[n]
        if n in big or not d: continue
        mstart[n] = len(mini) // MS
        k = -(-len(d) // MS)
        mini += d + b"\0" * (k * MS - len(d))
        base = mstart[n]
        minifat += [base + i + 1 for i in range(k - 1)] + [EOC]
    def chain_sectors(data):
        k = -(-len(data) // SS)
        start = len(fat)
        for b in range(k):
            sectors.append(data[b * SS:(b + 1) * SS].ljust(SS, b"\0"))
            fat.append(start + b + 1 if b < k - 1 else EOC)
        return start
    start = {}
    for n in names:
        if n in big:
            start[n] = chain_sectors(streams[n])
    root_start = chain_sectors(bytes(mini)) if mini else EOC
    mf = b"".join(struct.pack("<I", x) for x in minifat)
    mf_start = chain_sectors(mf) if mf else EOC
    nmf = -(-len(mf) // SS) if mf else 0
    # directory
    rootn, info = _tree(names)
    idx = {n: i + 1 for i, n in enumerate(names)}
    def ent(name, typ, color, l, r, c, st, size, mtime=0):
        nb = (name + "\0").encode("utf-16le") if name else b""
        e = nb.ljust(64, b"\0") + struct.pack("<HBB", len(nb), typ, color)
        e += struct.pack("<III", l, r, c) + b"\0" * 16 + struct.pack("<I", 0)
        e += struct.pack("<QQ", 0, mtime) + struct.pack("<IQ", st, size)
        return e
    nof = lambda n: idx[n] if n else FREE
    ents = [ent("Root Entry", 5, 0, FREE, FREE, nof(rootn), root_start, len(mini), root_mtime or 0)]
    for n in names:
        l, r, red = info[n]
        d = streams[n]
        if n in big: st = start[n]
        elif d: st = mstart[n]
        else: st = EOC
        ents.append(ent(n, 2, 0 if not red else 0, nof(l), nof(r), FREE, st, len(d)))
    # colours: red=0 black=1 in CFB; build properly
    ents2 = [ents[0]]
    for n, e in zip(names, ents[1:]):
        red = info[n][2]
        e = bytearray(e); e[67] = 0 if red else 1
        ents2.append(bytes(e))
    ents = ents2
    while len(ents) % 4: ents.append(ent("", 0, 0, FREE, FREE, FREE, 0, 0))
    dir_start = chain_sectors(b"".join(ents))
    # fat sectors
    nfat = 1
    while True:
        total = len(fat) + nfat
        if nfat * 128 >= total: break
        nfat += 1
    fat_start = len(fat)
    fat += [FATSEC] * nfat
    fat += [FREE] * (nfat * 128 - len(fat))
    for b in range(nfat):
        sectors.append(b"".join(struct.pack("<I", x) for x in fat[b * 128:(b + 1) * 128]))
    assert nfat <= 109
    hdr = bytearray(512)
    hdr[0:8] = bytes.fromhex("d0cf11e0a1b11ae1")
    struct.pack_into("<HHHHH", hdr, 24, 0x3e, 3, 0xFFFE, 9, 6)
    struct.pack_into("<IIIIIIIII", hdr, 40, 0, nfat, dir_start, 0, CUT, mf_start if mf else EOC, nmf, EOC, 0)
    for i in range(109):
        struct.pack_into("<I", hdr, 76 + 4 * i, fat_start + i if i < nfat else FREE)
    open(path, "wb").write(bytes(hdr) + b"".join(sectors))


def filetime(dt):
    return int((dt - datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)) / datetime.timedelta(microseconds=1) * 10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sol_dir")
    ap.add_argument("--win-repos-root")
    ap.add_argument("--docs", nargs="*")
    ap.add_argument("--config", default="Debug|x64")
    a = ap.parse_args()
    p = L.discover(a.sol_dir, a.win_repos_root, a.docs)
    S = build_streams(p, a.config)
    out = L.vs_dir(p); os.makedirs(out, exist_ok=True)
    write_cfb(os.path.join(out, ".suo"), S, filetime(datetime.datetime.now(datetime.timezone.utc)))
    print("wrote .suo with %d streams" % len(S))


if __name__ == "__main__":
    main()
