#!/usr/bin/env python3
"""Build a Visual Studio FileContentIndex .vsidx for a solution folder.

Layout (all integers little endian), see NOTES.md:
  0   4  magic "CDG" + 0x12
  4   3  zero bytes
  7   8  u64 footer offset
  15  8  u64 length of section 0   | section 0 = file table
  ..     u32 record size R (= longest path + 8), then R-byte records:
         path (ASCII, NUL padded to R-8) + u64 FILETIME (last write, UTC)
  ..     section 1 = posting items:  u64 length, u32 3, then 3-byte items
         (file index u8, always 0, line mask u8); files of one trigram are in
  indexing order (approx: ascending mtime)
  ..     section 2 = trigram -> (start u32, count u32) into section 1:
         u64 length, u32 8, then 8-byte entries
  ..     section 3 = sorted trigram dictionary: u64 length, u32 3, 3-byte keys
  ..     8 zero bytes
  footer u32 4, then 4 x u64 section offsets (15, s1, s2, s3)

Exact (verified byte-for-byte against two VS 18 files, see NOTES.md):
  everything except the file-set rule for non-C++ item types, non-ASCII text
  handling and sort order on exotic names (marked APPROX below).
"""
import argparse, os, re, struct, sys, uuid, xml.etree.ElementTree as ET

MAGIC = b"CDG\x12"
FILETIME_EPOCH_NS = 11644473600 * 10**9

# APPROX: item types VS indexes. ClCompile/ClInclude/Text are confirmed;
# the rest are a guess (none appear in the reference labs).
ITEM_TYPES = ("ClCompile", "ClInclude", "Text", "ResourceCompile", "None",
              "Midl", "CustomBuild", "Xml", "Image", "Manifest")


def filetime(ns):
    return (ns + FILETIME_EPOCH_NS) // 100


def find_files(sol_dir):
    """Return absolute Linux paths of indexed files (project items)."""
    out = []
    for root, dirs, files in os.walk(sol_dir):
        dirs[:] = [d for d in dirs if d != ".vs"]
        for f in files:
            if f.endswith(".vcxproj"):
                pdir = root
                tree = ET.parse(os.path.join(root, f))
                for el in tree.iter():
                    tag = el.tag.split("}")[-1]
                    inc = el.get("Include")
                    if tag in ITEM_TYPES and inc and "*" not in inc:
                        p = os.path.normpath(os.path.join(pdir, inc.replace("\\", "/")))
                        if os.path.isfile(p):
                            out.append(p)
    return sorted(set(out))


def tokens_trigrams(text):
    """Whitespace-delimited tokens, upper-cased, all 3-grams inside a token.
    APPROX for non-ASCII: trigrams containing non-ASCII are dropped."""
    for tok in re.split(r"\s+", text.upper()):
        for i in range(len(tok) - 2):
            g = tok[i:i + 3]
            if g.isascii():
                yield g


def line_masks(text):
    """Return per-line bit index: number of non-empty lines before it, mod 8.
    A line is empty only if it has length 0 after splitting on \\n (a lone
    \\r in CRLF files counts as non-empty, confirmed on Date.cpp/Date.h)."""
    idx, c = [], 0
    for ln in text.split("\n"):
        idx.append(c % 8)
        if ln:
            c += 1
    return idx


def build(files, win_paths, mtimes_ns):
    maxlen = max(len(p) for p in win_paths)
    rec = maxlen + 8
    # section 0
    s0 = struct.pack("<I", rec)
    for wp, ns in zip(win_paths, mtimes_ns):
        s0 += wp.encode("ascii").ljust(maxlen, b"\0") + struct.pack("<Q", filetime(ns))
    # postings
    post = {}  # trigram -> {fileidx: mask}  (dict keeps insertion order)
    # APPROX: VS lists the files of a trigram in the order they were indexed,
    # which best matches ascending last-write time (97% of lists exact on a
    # fresh index, 46% on an index that was updated while editing).
    proc = sorted(range(len(files)), key=lambda i: (mtimes_ns[i], i))
    for fi in proc:
        p = files[fi]
        raw = open(p, "rb").read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        lidx = line_masks(text)
        pos = 0
        for ln_i, ln in enumerate(text.split("\n")):
            bit = 1 << lidx[ln_i]
            for g in tokens_trigrams(ln):
                d = post.setdefault(g, {})
                d[fi] = d.get(fi, 0) | bit
        # (per-line processing is equivalent: tokens never span lines)
    keys = sorted(post)  # ordinal order of upper-case ASCII
    s1 = struct.pack("<I", 3)
    s2 = struct.pack("<I", 8)
    s3 = struct.pack("<I", 3)
    start = 0
    for k in keys:
        ents = list(post[k].items())
        for fi, m in ents:
            s1 += bytes((fi, 0, m))
        s2 += struct.pack("<II", start, len(ents))
        start += len(ents)
        s3 += k.encode("ascii")
    secs = [s0, s1, s2, s3]
    body = b""
    offs = []
    pos = 15
    for s in secs:
        offs.append(pos)
        body += struct.pack("<Q", len(s)) + s
        pos += 8 + len(s)
    footer_off = pos + 8
    footer = struct.pack("<I", 4) + b"".join(struct.pack("<Q", o) for o in offs)
    head = MAGIC + b"\0\0\0" + struct.pack("<Q", footer_off)
    return head + body + b"\0" * 8 + footer


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("solution_dir", help="folder holding <name>.slnx and the project folder")
    ap.add_argument("--win-root", default=None,
                    help=r"Windows path of the solution folder, e.g. C:\Users\me\source\repos\Foo_sol "
                         "(default C:\\Users\\<USER>\\source\\repos\\<folder>)")
    ap.add_argument("--user", default=os.environ.get("USER", "student"))
    ap.add_argument("--guid", default=None, help="file name GUID (default random uuid4, as VS does)")
    ap.add_argument("--out", default=None, help="output file (default .vs/<sln>/FileContentIndex/<guid>.vsidx)")
    ap.add_argument("--mtimes-from", default=None,
                    help="validation only: copy FILETIMEs from an existing .vsidx instead of stat()")
    a = ap.parse_args()
    sol_dir = os.path.abspath(a.solution_dir)
    slns = [f for f in os.listdir(sol_dir) if f.endswith((".slnx", ".sln"))]
    if not slns:
        sys.exit("no .slnx/.sln in " + sol_dir)
    sln = slns[0]
    files = find_files(sol_dir)
    win_root = (a.win_root or r"C:\Users\%s\source\repos\%s" % (a.user, os.path.basename(sol_dir))).rstrip("\\")
    wins = [win_root + "\\" + os.path.relpath(p, sol_dir).replace("/", "\\") for p in files]
    order = sorted(range(len(files)), key=lambda i: wins[i].upper())  # ordinal ignore case
    files = [files[i] for i in order]
    wins = [wins[i] for i in order]
    if a.mtimes_from:
        old = open(a.mtimes_from, "rb").read()
        rec = struct.unpack_from("<I", old, 23)[0]
        n = (struct.unpack_from("<Q", old, 15)[0] - 4) // rec
        ts = {}
        for i in range(n):
            o = 27 + rec * i
            ts[old[o:o + rec - 8].rstrip(b"\0").decode()] = struct.unpack_from("<Q", old, o + rec - 8)[0]
        mt = [ts[w] * 100 - FILETIME_EPOCH_NS for w in wins]
    else:
        mt = [os.stat(p).st_mtime_ns for p in files]
    data = build(files, wins, mt)
    g = a.guid or str(uuid.uuid4())
    out = a.out or os.path.join(sol_dir, ".vs", sln, "FileContentIndex", g + ".vsidx")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "wb").write(data)
    print("wrote %s (%d bytes, %d files)" % (out, len(data), len(files)))


if __name__ == "__main__":
    main()
