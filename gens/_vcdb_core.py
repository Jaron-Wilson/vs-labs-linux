#!/usr/bin/env python3
"""Generate Browse.VC.db and Solution.VC.db like Visual Studio 18 (2026) writes
them into  .vs/<sln>.slnx/v18/ .

Usage:
  .venv/bin/python gen_vcdb.py --project-dir DIR_WITH_VCXPROJ \
      --win-root 'C:\\Users\\Student\\source\\repos\\MySolution' \
      --out-dir OUT/.vs/MySolution.slnx/v18 [--reference REF_Browse.VC.db]

  --project-dir : folder holding <proj>.vcxproj (sources next to it)
  --win-root    : Windows path of the SOLUTION folder (parent of the project
                  folder) as it will exist on the machine that opens the lab
  --reference   : a Browse.VC.db written by a real VS 18 (same MSVC/SDK) used
                  as the source of system header rows
Needs: python3 -m venv .venv && .venv/bin/pip install libclang
See NOTES.md for what is exact and what is approximate.
"""
import argparse, os, re, sqlite3, sys, time, glob, subprocess, collections
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REF = os.path.join(os.environ.get("VSLAB_ROOT", os.path.expanduser("~/.local/share/vslab")), "reference", "Browse.VC.db")
_UNUSED_REF = (
    "~/vs-labs-linux-research/reference/LabDynamicMemory_WilsonJ_sol/.vs/"
    "LabDynamicMemory_WilsonJ_sol.slnx/v18/Browse.VC.db")
ROOT_PARENT = 1024           # parent_id of file scope code items
CONFIG_ID = 1025             # VS used 1025 for the first project / config
PROJECT_ID = 1025
CPP_PARSER = "B5E9BD326D3E4B5D925E8A43B79820B4"
M64 = (1 << 64) - 1
ROOT = {"children": [], "id": ROOT_PARENT, "root": True}

# ---------------------------------------------------------------- helpers

def fnv1a_signed(b):
    """shared_data.hash is the signed 64 bit FNV-1a of the stored value bytes
    (UTF-8 for text values, JSONB for blobs). Verified on the reference DB."""
    if isinstance(b, str):
        b = b.encode("utf-8")
    h = 14695981039346656037
    for x in b:
        h = ((h ^ x) * 1099511628211) & M64
    return h - (1 << 64) if h >= (1 << 63) else h


def to_win(path_posix, proj_dir, win_proj_dir):
    rel = os.path.relpath(os.path.realpath(path_posix), os.path.realpath(proj_dir))
    return win_proj_dir.rstrip("\\") + "\\" + rel.replace("/", "\\")


def create_schema(con, ddl_file):
    """DDL copied verbatim from the reference DBs (sqlite_master order)."""
    with open(os.path.join(HERE, ddl_file), encoding="utf-8") as f:
        stmts = [s.strip("\n") for s in f.read().split("\n;;\n") if s.strip()]
    for sql in stmts:
        if re.match(r"CREATE TABLE '\w+_(?:data|idx|docsize|config)'", sql):
            continue            # FTS5 shadow tables come with CREATE VIRTUAL TABLE
        con.execute(sql)


# ------------------------------------------------------------ vcxproj model

class Project:
    def __init__(self, vcxproj, config="Debug|x64"):
        self.vcxproj = os.path.abspath(vcxproj)
        self.dir = os.path.dirname(self.vcxproj)
        self.name = os.path.splitext(os.path.basename(vcxproj))[0]
        self.config = config
        ns = {"m": "http://schemas.microsoft.com/developer/msbuild/2003"}
        root = ET.parse(vcxproj).getroot()
        g = root.find(".//m:ProjectGuid", ns)
        guid = g.text if g is not None else "{00000000-0000-0000-0000-000000000000}"
        self.guid = guid.strip("{}").replace("-", "").upper()
        self.compile, self.include, self.other = [], [], []
        for tag, lst in (("ClCompile", self.compile), ("ClInclude", self.include),
                         ("Text", self.other), ("None", self.other),
                         ("ResourceCompile", self.other)):
            for e in root.findall(".//m:ItemGroup/m:%s" % tag, ns):
                if e.get("Include"):
                    lst.append(e.get("Include").replace("\\", "/"))
        self.defs, self.std = ["_DEBUG", "_CONSOLE"], "stdcpp20"
        cond = "'$(Configuration)|$(Platform)'=='%s'" % config
        for grp in root.findall("m:ItemDefinitionGroup", ns):
            if grp.get("Condition", "").replace(" ", "") != cond.replace(" ", ""):
                continue
            pd = grp.find("m:ClCompile/m:PreprocessorDefinitions", ns)
            if pd is not None:
                self.defs = [d for d in pd.text.split(";") if d and not d.startswith("%")]
            ls = grp.find("m:ClCompile/m:LanguageStandard", ns)
            if ls is not None:
                self.std = ls.text
        self.std_flag = {"stdcpp14": "c++14", "stdcpp17": "c++17", "stdcpp20": "c++20",
                         "stdcpplatest": "c++latest", "stdcpp23": "c++23"}.get(self.std, "c++14")
        filt = self.vcxproj + ".filters"
        self.filters = filt if os.path.exists(filt) else None

    def files(self):
        return list(self.compile) + list(self.include) + list(self.other)


# ---------------------------------------------------------- reference access

class Ref:
    """Read only view of a VS written Browse.VC.db."""
    def __init__(self, path):
        self.con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
        self.q = lambda s, a=(): self.con.execute(s, a).fetchall()
        self.files = {r[0]: r for r in self.q("select id,name,attributes from files")}
        self.sys_ids = sorted(i for i, r in self.files.items()
                              if "\\MICROSOFT VISUAL STUDIO\\" in r[1] or "\\WINDOWS KITS\\" in r[1])
        self.sys_set = set(self.sys_ids)
        # include graph: pound_include item -> resolved file (file_map)
        self.edges = collections.defaultdict(set)
        for src, tgt in self.q("select i.file_id, m.file_id from file_map m "
                               "join code_items i on i.id=m.code_item_id"):
            self.edges[src].add(tgt)
        inc = self.q("select value from shared_data where id=6")[0][0].upper().split(";")
        self.by_rel = {}
        for root in [p for p in inc if p]:
            r = root.rstrip("\\") + "\\"
            for i in self.sys_ids:
                n = self.files[i][1]
                if n.startswith(r):
                    self.by_rel.setdefault(n[len(r):], i)
        # which system headers each reference translation unit really pulled in (conditional
        # includes make this smaller than the plain include closure) and its direct includes
        self.tu_sets = collections.defaultdict(set)
        for f, tu in self.q("select file_id, tu_file_id from file_tu_map"):
            if f in self.sys_set:
                self.tu_sets[tu].add(f)
        self.tu_direct = {}
        for tu in self.tu_sets:
            seen, todo, direct = set(), [tu], set()
            while todo:
                x = todo.pop()
                if x in seen:
                    continue
                seen.add(x)
                for t in self.edges.get(x, ()):
                    (direct.add(t) if t in self.sys_set else todo.append(t))
            self.tu_direct[tu] = direct
        # how often the reference project itself used a symbol (disambiguation)
        self.popular = collections.Counter()
        excl = ",".join(str(i) for i in self.sys_ids + [1025, 1026])
        for (sid,) in self.q("select symbol_id from symbol_refs where file_id not in (%s)" % excl):
            self.popular[sid] += 1
        self.sym_by_name = collections.defaultdict(list)
        for sid, name, kind, sk in self.q("select id,name,kind,symbol_kind from symbols"):
            self.sym_by_name[name].append((sid, kind, sk))

    def resolve_angle(self, name):
        return self.by_rel.get(name.upper().replace("/", "\\"))

    def tu_system_files(self, direct):
        """system headers a TU with these direct includes pulls in, learned from the
        reference TUs that included the same headers directly"""
        everything = set().union(*self.tu_sets.values()) if self.tu_sets else set()
        out = set()
        for d in direct:
            seen_in = [self.tu_sets[t] for t, ds in self.tu_direct.items() if d in ds]
            allowed = set().union(*seen_in) if seen_in else everything
            out |= self.closure([d]) & allowed
        return out & self.sys_set

    def closure(self, seeds):
        seen, todo = set(), list(seeds)
        while todo:
            f = todo.pop()
            if f in seen:
                continue
            seen.add(f)
            todo.extend(self.edges.get(f, ()))
        return seen


# ------------------------------------------------------------- libclang part

def gcc_include():
    try:
        return subprocess.check_output(["gcc", "-print-file-name=include"], text=True).strip()
    except Exception:
        return ""


SKIP_SPEC = {"virtual", "static", "inline", "explicit", "friend", "extern", "constexpr",
             "consteval", "constinit", "typedef", "mutable", "_NODISCARD"}


class Extractor:
    """Walks libclang ASTs of every translation unit of a project and builds
    code item trees plus symbol / reference data for the project files."""

    def __init__(self, ci, proj, ref):
        self.ci, self.proj, self.ref = ci, proj, ref
        self.pfiles = {os.path.realpath(os.path.join(proj.dir, f)): f for f in proj.files()}
        self.src, self.lines = {}, {}
        self.items = collections.defaultdict(list)   # path -> top level items
        self.seen_items = set()
        self.scopes = {}
        self.syms, self.sym_order = {}, []
        self.refs = collections.defaultdict(list)    # (symkey, path) -> [(kind, off, len, attr)]
        self.includes = collections.defaultdict(set)
        self.times = {}
        self.tu_list = []
        self.sysref = {}

    def text(self, path):
        if path not in self.src:
            self.src[path] = open(path, "rb").read()
            self.lines[path] = self.src[path].split(b"\n")
        return self.src[path]

    def pf(self, f):
        if f is None:
            return None
        p = os.path.realpath(f.name)
        return p if p in self.pfiles else None

    def parse_all(self):
        ci = self.ci
        idx = ci.Index.create()
        args = ["-x", "c++", "-std=" + self.proj.std_flag, "-I" + self.proj.dir, "-Wno-everything",
                "-D_UNICODE", "-DUNICODE", "-fsyntax-only"]
        args += ["-D" + d for d in self.proj.defs]
        g = gcc_include()
        if g:
            args += ["-isystem", g]
        for cpp in self.proj.compile:
            path = os.path.realpath(os.path.join(self.proj.dir, cpp))
            t0 = time.time()
            tu = idx.parse(path, args=args, options=ci.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
            self.times[path] = time.time() - t0
            self.tu_list.append(path)
            for c in tu.cursor.get_children():
                if self.pf(c.location.file):
                    self.visit(c, ROOT)

    # ------------------------------------------------------------ geometry
    def span(self, cur):
        e = cur.extent
        return (e.start.line, e.start.column, e.end.line, e.end.column - 1,
                e.start.offset, e.end.offset)

    def name_span(self, cur, name=None):
        loc = cur.location
        n = name if name is not None else cur.spelling
        if n.startswith("operator"):
            rest = n[8:]
            n = n if (rest[:1].isalpha() or rest[:1] == "_") is False else n
        return (loc.line, loc.column, loc.line, loc.column + len(n) - 1)

    def semi(self, path, sp):
        src = self.src[path]
        if sp[5] < len(src) and src[sp[5]:sp[5] + 1] == b";":
            return (sp[0], sp[1], sp[2], sp[3] + 1, sp[4], sp[5] + 1)
        return sp

    def to_semi(self, path, sp):
        src = self.src[path]
        i = sp[5]
        while i < len(src) and src[i:i + 1] in (b" ", b"\t", b"=") or src[i:i + 1].isalpha():
            i += 1
        if src[i:i + 1] == b";":
            return (sp[0], sp[1], sp[2], sp[3] + (i + 1 - sp[5]), sp[4], i + 1)
        return sp

    def friend_access(self, cur):
        """access label in force at a friend declaration (libclang reports none)"""
        CK = self.ci.CursorKind
        parent = cur.lexical_parent
        acc = 4 if parent is not None and parent.kind == CK.STRUCT_DECL else 0x10
        for t in parent.get_tokens():
            if t.extent.start.offset >= cur.extent.start.offset:
                break
            pass
        toks = list(parent.get_tokens())
        for i, t in enumerate(toks[:-1]):
            if t.extent.start.offset >= cur.extent.start.offset:
                break
            if t.spelling in ("public", "private", "protected") and toks[i + 1].spelling == ":":
                acc = {"public": 4, "protected": 8, "private": 0x10}[t.spelling]
        return acc

    def norm_type(self, toks):
        toks = [t for t in toks if t not in SKIP_SPEC]
        if not toks:
            return ""
        if "<" in toks:
            s = ""
            for t in toks:
                if not s or t in ("::", "<", ">", ",", "&", "*", "&&") or s.endswith(("::", "<")):
                    s += t
                else:
                    s += " " + t
            return re.sub(r",(?=\S)", ", ", s)
        out = ""
        for t in toks:
            if not out:
                out = t
            elif t == "::" or out.endswith("::"):
                out += t
            elif set(t) <= set("*&") and set(out.split(" ")[-1]) <= set("*&"):
                out += t
            else:
                out += " " + t
        return out

    def skip_template_header(self, toks):
        i = 0
        if toks and toks[0].spelling == "template":
            depth = 0
            for i, t in enumerate(toks):
                if t.spelling == "<":
                    depth += 1
                elif t.spelling == ">":
                    depth -= 1
                    if depth == 0:
                        return i + 1
        return 0

    def type_before_name(self, cur):
        toks = list(cur.get_tokens())
        i = self.skip_template_header(toks)
        loc = (cur.location.line, cur.location.column)
        out = []
        for t in toks[i:]:
            if (t.location.line, t.location.column) >= loc:
                break
            out.append(t.spelling)
        while out and out[-1] == "::":
            out.pop()
            if out and out[-1] == ">":
                depth = 0
                while out:
                    t = out.pop()
                    depth += (t == ">") - (t == "<")
                    if depth == 0:
                        break
            if out:
                out.pop()
        return out

    def access_bits(self, cur):
        a = cur.access_specifier
        return {"PUBLIC": 4, "PROTECTED": 8, "PRIVATE": 0x10}.get(a.name if a else "", 0)

    # --------------------------------------------------------------- items
    def mk(self, kind, attrs, name, typ, sp, nsp, parent, default=None, dsp=None, pnum=None):
        return dict(kind=kind, attrs=attrs, name=name, type=typ, sl=sp[0], sc=sp[1], el=sp[2], ec=sp[3],
                    nsl=nsp[0], nsc=nsp[1], nel=nsp[2], nec=nsp[3], default=default, dsp=dsp,
                    pnum=pnum, parent=parent, children=[], lower=name)

    def place(self, path, parent, it):
        it["file"] = path
        if parent is ROOT:
            self.items[path].append(it)
        else:
            parent["children"].append(it)

    def fresh(self, path, kind, name, sl, sc):
        key = (path, kind, name, sl, sc)
        if key in self.seen_items:
            return False
        self.seen_items.add(key)
        return True

    def param_items(self, cur, parent_item, path, acc):
        n = 0
        for a in cur.get_children():
            if a.kind != self.ci.CursorKind.PARM_DECL:
                continue
            n += 1
            sp = self.span(a)
            toks = list(a.get_tokens())
            name = a.spelling
            nsp = self.name_span(a) if name else (0, 0, 0, 0)
            tt = []
            for t in toks:
                if t.spelling == "=":
                    break
                if name and (t.location.line, t.location.column) >= (a.location.line, a.location.column):
                    break
                tt.append(t.spelling)
            ts = self.norm_type(tt)
            typ = (ts + " \x01") if name else ts
            if name and "(" in tt:           # e.g. char (&date)[20] -> 'char(& \x01)[20]'
                raw = self.src[path][sp[4]:sp[5]].decode("utf-8", "replace")
                raw = re.split(r"\s*=", raw)[0]
                typ = re.sub(r"\s+\(", "(", raw).replace(name, " \x01", 1)
            dflt, dsp = "", None
            for k, t in enumerate(toks):
                if t.spelling == "=" and k > 0:
                    last = toks[-1]
                    seg = self.src[path][t.extent.start.offset:last.extent.end.offset].decode("utf-8", "replace")
                    dflt = re.sub(r"\s+", " ", seg)
                    dsp = (t.location.column, t.location.line, last.extent.end.column - 1,
                           last.extent.end.line)
                    break
            it = self.mk(9, 1 | acc, name, typ, sp, nsp, parent_item, dflt, dsp, n)
            it["file"] = path
            parent_item["children"].append(it)

    def template_items(self, cur, parent_item, path):
        toks = list(cur.get_tokens())
        if not toks or toks[0].spelling != "template":
            return
        depth, params, endtok, curp = 0, [], None, []
        for t in toks[1:]:
            s = t.spelling
            if s == "<":
                depth += 1
                if depth == 1:
                    continue
            if s == ">":
                depth -= 1
                if depth == 0:
                    endtok = t
                    if curp:
                        params.append(curp)
                    break
            if s == "," and depth == 1:
                params.append(curp)
                curp = []
                continue
            curp.append(t)
        if endtok is None or not params:
            return
        first = toks[0]
        hs = (first.location.line, first.location.column, endtok.location.line, endtok.location.column, 0, 0)
        t10 = self.mk(10, 0, "", None, hs, (hs[0], 1, hs[2], hs[3]), parent_item)
        t10["file"] = path
        parent_item["children"].append(t10)
        for n, pt in enumerate(params, 1):
            nm_tok = pt[-1]
            kw = pt[0].spelling
            sp = (pt[0].location.line, pt[0].location.column, nm_tok.location.line,
                  nm_tok.extent.end.column - 1, 0, 0)
            nsp = (nm_tok.location.line, nm_tok.location.column, nm_tok.location.line,
                   nm_tok.extent.end.column - 1)
            it = self.mk(12, 0, nm_tok.spelling, kw + " \x01", sp, nsp, t10, "", None, n)
            it["file"] = path
            t10["children"].append(it)

    def func_attrs(self, cur, in_class, toks):
        CK = self.ci.CursorKind
        is_def = cur.is_definition()
        if in_class:
            a = 1 | self.access_bits(cur) | (2 if is_def else 0)
        else:
            a = 2 if is_def else 1
        if cur.is_const_method():
            a |= 0x40000
        if "virtual" in toks[:toks.index(cur.spelling) if cur.spelling in toks else 6]:
            a |= 0x20
        if "override" in toks:
            a |= 0x10000000
        nm = cur.spelling
        if nm.startswith("operator") and not (nm[8:9].isalnum() or nm[8:9] == "_"):
            a |= 0x1000000
        for i, t in enumerate(toks[:-1]):
            if t == "=" and toks[i + 1] == "delete":
                a |= 0x8000000
            elif t == "=" and toks[i + 1] == "default":
                a |= 0x4000000 | 2
                if in_class and cur.kind == CK.CONSTRUCTOR and not any(
                        c.kind == CK.PARM_DECL for c in cur.get_children()):
                    a |= 0x200
        if cur.kind == CK.FUNCTION_TEMPLATE:
            a |= 0x800
        return a

    def func_item(self, cur, path, parent):
        CK = self.ci.CursorKind
        CLS = (CK.CLASS_DECL, CK.STRUCT_DECL, CK.CLASS_TEMPLATE, CK.UNION_DECL)
        lex, sem = cur.lexical_parent, cur.semantic_parent
        in_class = lex is not None and lex.kind in CLS
        toks = [t.spelling for t in cur.get_tokens()]
        is_friend = in_class and "friend" in toks[:6]
        name = re.sub(r"<.*>$", "", cur.spelling) if not cur.spelling.startswith("operator") else cur.spelling
        sp = self.span(cur)
        if not cur.is_definition():
            sp = self.semi(path, sp)
        elif toks[-1:] != ["}"]:          # = default / = delete: VS ends the item at the ';'
            sp = self.to_semi(path, sp)
        nsp = self.name_span(cur, name)
        mt = re.match(rb"\s*=\s*(default|delete)\b", self.src[path][self.span(cur)[5]:self.span(cur)[5] + 40])
        if mt and not ("=" in toks[-3:]):
            toks = toks + ["=", mt.group(1).decode()]
        attrs = self.func_attrs(cur, in_class, toks)
        facc = self.friend_access(cur) if is_friend else 0
        if is_friend:
            attrs = 0x10000 | facc | 1 | (attrs & 0x1000000) | (attrs & 0x40000)
        ret = self.norm_type(self.type_before_name(cur))
        ctype = (ret + " " if ret else "") + "\x01\x02"
        kind = 6 if in_class and not is_friend else 27
        if not self.fresh(path, kind, name, sp[0], sp[1]):
            return
        par = ROOT if is_friend else parent
        if not in_class and sem is not None and sem.kind in CLS and not is_friend:
            key = (path, sem.spelling)
            scope = self.scopes.get(key)
            if scope is None:
                ln = self.lines[path][cur.location.line - 1].decode("utf-8", "replace")
                pre = ln[:cur.location.column - 1]
                mm = re.search(r"(\w+)(?:<[^>]*>)?::$", pre)
                scol = mm.start(1) + 1 if mm else cur.location.column
                qn = sem.spelling
                ssp = (cur.location.line, scol, cur.location.line, scol + len(qn) - 1, 0, 0)
                tm = sem.kind == CK.CLASS_TEMPLATE
                scope = self.mk(53, 0x800 if tm else 0, qn, None, ssp, ssp[:4], par)
                self.scopes[key] = scope
                self.place(path, par, scope)
                if tm:
                    seg = ln[scol - 1 + len(qn):]
                    ma = re.match(r"<([^>]*)>", seg)
                    if ma:
                        c0 = scol + len(qn) + 1
                        for a in ma.group(1).split(","):
                            a2 = a.strip()
                            col = c0 + (len(a) - len(a.lstrip()))
                            asp = (cur.location.line, col, cur.location.line, col + len(a2) - 1, 0, 0)
                            ai = self.mk(11, 0, a2, None, asp, asp[:4], scope)
                            ai["file"] = path
                            scope["children"].append(ai)
                            c0 += len(a) + 1
            par = scope
        it = self.mk(kind, attrs, name, ctype, sp, nsp, par)
        self.place(path, par, it)
        self.param_items(cur, it, path, facc if is_friend else (self.access_bits(cur) if in_class else 0))
        self.template_items(cur, it, path)
        return it

    def visit(self, cur, parent):
        CK = self.ci.CursorKind
        k = cur.kind
        path = self.pf(cur.location.file)
        if path is None:
            return
        self.text(path)
        sp = self.span(cur)
        if k == CK.INCLUSION_DIRECTIVE:
            line = self.lines[path][sp[0] - 1].decode("utf-8", "replace").rstrip("\r")
            angle = "<" in line and ">" in line and line.index("<") < line.rindex(">")
            nm = cur.spelling
            inc = cur.get_included_file()
            info = ("angle" if angle else "quote", nm, os.path.realpath(inc.name) if inc else None)
            self.includes[path].add(info)
            if self.fresh(path, 39, nm, sp[0], sp[1]):
                it = self.mk(39, 0x40002 if angle else 2, nm, None,
                             (sp[0], sp[1], sp[0], len(line), 0, 0), (0, 0, 0, 0), ROOT)
                it["include"] = info
                self.place(path, ROOT, it)
            return
        if k == CK.MACRO_DEFINITION:
            line = self.lines[path][sp[0] - 1].decode("utf-8", "replace").rstrip("\r")
            m = re.match(r"\s*#\s*define\s+", line)
            if not m:
                return
            nsp = self.name_span(cur)
            if self.fresh(path, 37, cur.spelling, sp[0], m.start() + 1):
                it = self.mk(37, 3, cur.spelling, None,
                             (sp[0], m.start() + 1, sp[0], len(line) + 1, 0, 0), nsp, ROOT)
                self.place(path, ROOT, it)
                self.sym_decl(cur, path, 3)
            return
        if k in (CK.CLASS_DECL, CK.STRUCT_DECL, CK.UNION_DECL, CK.CLASS_TEMPLATE):
            if cur.spelling == "":
                for c in cur.get_children():
                    self.visit(c, parent)
                return
            tmpl = k == CK.CLASS_TEMPLATE
            kind = {CK.CLASS_DECL: 1, CK.STRUCT_DECL: 2, CK.UNION_DECL: 3}.get(k)
            if tmpl:
                toks = [t.spelling for t in cur.get_tokens()]
                kind = 2 if "struct" in toks[:toks.index(cur.spelling) if cur.spelling in toks else 0] else 1
            isdef = cur.is_definition()
            a = (3 if isdef else 1) | (0x800 if tmpl else 0)
            lex = cur.lexical_parent
            if lex is not None and lex.kind in (CK.CLASS_DECL, CK.STRUCT_DECL, CK.CLASS_TEMPLATE):
                a |= self.access_bits(cur)
            nsp = self.name_span(cur)
            if not self.fresh(path, kind, cur.spelling, sp[0], sp[1]):
                return
            it = self.mk(kind, a, cur.spelling, None, sp if isdef else self.semi(path, sp), nsp, parent)
            self.place(path, parent, it)
            self.sym_decl(cur, path, 3 if isdef else 1)
            if isdef:
                for c in cur.get_children():
                    if c.kind == CK.CXX_BASE_SPECIFIER:
                        self.base_item(c, it, path)
                    else:
                        self.visit(c, it)
                if tmpl:
                    self.template_items(cur, it, path)
                    for c in cur.get_children():
                        if c.kind == CK.TEMPLATE_TYPE_PARAMETER and c.spelling:
                            self.sym_decl(c, path, 3)
            return
        if k in (CK.CONSTRUCTOR, CK.DESTRUCTOR, CK.CXX_METHOD, CK.FUNCTION_DECL,
                 CK.FUNCTION_TEMPLATE, CK.CONVERSION_FUNCTION):
            self.func_item(cur, path, parent)
            self.sym_decl(cur, path, 3 if cur.is_definition() else 1)
            for c in cur.get_children():
                if c.kind == CK.PARM_DECL and cur.is_definition():
                    self.sym_decl(c, path, 2051 if cur.kind == CK.CONSTRUCTOR else 3)
                elif c.kind == CK.TEMPLATE_TYPE_PARAMETER and c.spelling:
                    self.sym_decl(c, path, 3)
            self.collect_refs(cur, path)
            return
        if k == CK.FIELD_DECL:
            nsp = self.name_span(cur)
            if self.fresh(path, 7, cur.spelling, sp[0], sp[1]):
                ts = self.norm_type(self.type_before_name(cur))
                it = self.mk(7, 3 | self.access_bits(cur), cur.spelling, ts + " \x01",
                             self.semi(path, sp), nsp, parent)
                self.place(path, parent, it)
                toks = list(cur.get_tokens())
                for j, t in enumerate(toks):
                    if t.spelling == "=" and j > 0:
                        seg = self.src[path][t.extent.start.offset:toks[-1].extent.end.offset]
                        it["assoc_text"] = (2, re.sub(r"\s+", " ", seg.decode("utf-8", "replace")).strip())
                        break
                self.sym_decl(cur, path, 3)
            self.collect_refs(cur, path)
            return
        if k in (CK.TYPEDEF_DECL, CK.TYPE_ALIAS_DECL):
            kind = 21 if k == CK.TYPEDEF_DECL else 20
            a = 3
            lex = cur.lexical_parent
            if lex is not None and lex.kind in (CK.CLASS_DECL, CK.STRUCT_DECL):
                a |= self.access_bits(cur)
            if self.fresh(path, kind, cur.spelling, sp[0], sp[1]):
                it = self.mk(kind, a, cur.spelling, self.norm_type(self.type_before_name(cur)) + " \x01",
                             self.semi(path, sp), self.name_span(cur), parent)
                self.place(path, parent, it)
                self.sym_decl(cur, path, 3)
            return
        if k == CK.ENUM_DECL:
            toks = [t.spelling for t in cur.get_tokens()][:3]
            a = 3 | (0x80000 if ("class" in toks or "struct" in toks) else 0)
            lex = cur.lexical_parent
            if lex is not None and lex.kind in (CK.CLASS_DECL, CK.STRUCT_DECL):
                a |= self.access_bits(cur)
            if not self.fresh(path, 4, cur.spelling, sp[0], sp[1]):
                return
            it = self.mk(4, a, cur.spelling, None, sp, self.name_span(cur), parent)
            self.place(path, parent, it)
            self.sym_decl(cur, path, 3)
            for c in cur.get_children():
                if c.kind == CK.ENUM_CONSTANT_DECL:
                    e = self.mk(8, 3, c.spelling, None, self.span(c), self.name_span(c), it)
                    e["file"] = path
                    ts = list(c.get_tokens())
                    for j, t in enumerate(ts):
                        if t.spelling == "=":
                            e["assoc_text"] = (2, "= " + " ".join(x.spelling for x in ts[j + 1:]))
                    it["children"].append(e)
                    self.sym_decl(c, path, 3)
            return
        if k == CK.VAR_DECL and parent is ROOT:
            toks = [t.spelling for t in cur.get_tokens()]
            if self.fresh(path, 28, cur.spelling, sp[0], sp[1]):
                it = self.mk(28, 1 if "extern" in toks else 3, cur.spelling,
                             self.norm_type(self.type_before_name(cur)) + " \x01",
                             self.semi(path, sp), self.name_span(cur), ROOT)
                self.place(path, ROOT, it)
                self.sym_decl(cur, path, 3)
            self.collect_refs(cur, path)
            return
        if k == CK.NAMESPACE:
            if self.fresh(path, 18, cur.spelling, sp[0], sp[1]):
                it = self.mk(18, 3, cur.spelling, None, sp, self.name_span(cur), parent)
                self.place(path, parent, it)
                self.sym_decl(cur, path, 3)
                for c in cur.get_children():
                    self.visit(c, it)
            return
        for c in cur.get_children():
            self.visit(c, parent)

    def base_item(self, c, cls_item, path):
        sp = self.span(c)
        tr = [x for x in c.get_children() if x.kind == self.ci.CursorKind.TYPE_REF]
        name = c.spelling.replace("class ", "").replace("struct ", "").split("::")[-1]
        a = 1 | {"PUBLIC": 4, "PROTECTED": 8, "PRIVATE": 0x10}.get(c.access_specifier.name, 4)
        ns = self.name_span(tr[0], name) if tr else self.name_span(c, name)
        it = self.mk(17, a, name, None, sp, ns, cls_item)
        it["base_of"] = cls_item
        it["file"] = path
        cls_item["children"].append(it)
        for x in c.get_children():
            self.record_ref(x, path, None)

    # --------------------------------------------------- symbols and refs
    def sym_info(self, cur):
        """(code item kind, semantic_token_kind, symbol_kind, flags) as VS stores them."""
        CK = self.ci.CursorKind
        k, n = cur.kind, cur.spelling
        isop = n.startswith("operator") and not (n[8:9].isalnum() or n[8:9] == "_")
        CLS = (CK.CLASS_DECL, CK.STRUCT_DECL, CK.CLASS_TEMPLATE)
        if k == CK.CLASS_DECL:
            return 1, 7, 4, 0
        if k == CK.CLASS_TEMPLATE:
            return 1, 17, 4, 0
        if k == CK.STRUCT_DECL:
            return 2, 7, 4, 0
        if k == CK.UNION_DECL:
            return 3, 7, 5, 0
        if k == CK.ENUM_DECL:
            return 4, 7, 6, 0
        if k == CK.ENUM_CONSTANT_DECL:
            return 8, 3, 2, 0
        if k in (CK.CONSTRUCTOR, CK.DESTRUCTOR, CK.CXX_METHOD, CK.CONVERSION_FUNCTION):
            if k == CK.CXX_METHOD and cur.is_static_method():
                return 6, 13, 10, 0
            return 6, (26 if isop else 11), 10, 0
        if k == CK.FUNCTION_TEMPLATE:
            if cur.semantic_parent is not None and cur.semantic_parent.kind in CLS:
                return 6, 11, 20, 0
            return 27, 19, 20, 0
        if k == CK.FUNCTION_DECL:
            return 27, (25 if isop else 10), 11, 0
        if k == CK.FIELD_DECL:
            return 7, 12, 8, 0
        if k == CK.PARM_DECL:
            return 28, 6, 7, 1
        if k == CK.VAR_DECL:
            sp = cur.semantic_parent
            if sp is not None and sp.kind in CLS:
                return 7, 14, 9, 0
            if sp is not None and sp.kind in (CK.FUNCTION_DECL, CK.CXX_METHOD, CK.CONSTRUCTOR,
                                              CK.DESTRUCTOR, CK.FUNCTION_TEMPLATE):
                return 28, 5, 7, 1
            return 28, 4, 7, 0
        if k in (CK.TYPEDEF_DECL, CK.TYPE_ALIAS_DECL):
            return 21, 7, 3, 0
        if k == CK.NAMESPACE:
            return 18, 20, 23, 0
        if k == CK.TEMPLATE_TYPE_PARAMETER:
            return 21, 7, 3, 0
        if k == CK.MACRO_DEFINITION:
            return 37, 2, 1, 0
        return None

    def get_sym(self, cur):
        info = self.sym_info(cur)
        if info is None or cur.spelling.startswith(("__begin", "__end", "__range")):
            return None
        f = cur.location.file
        if cur.kind == self.ci.CursorKind.MACRO_DEFINITION:
            key = "macro:%s:%s" % (f.name if f else "", cur.spelling)
        else:
            key = cur.get_usr() or "%s:%d:%d:%s" % (f.name if f else "", cur.location.line,
                                                    cur.location.column, cur.spelling)
        s = self.syms.get(key)
        if s is not None:
            return s
        in_proj = self.pf(f) is not None
        s = dict(key=key, name=cur.spelling, info=info, ref_id=None, in_proj=in_proj)
        if not in_proj:
            s["ref_id"] = self.map_system_symbol(cur.spelling, info)
            if s["ref_id"] is None:
                self.syms[key] = None
                return None
        self.syms[key] = s
        self.sym_order.append(key)
        return s

    def map_system_symbol(self, name, info):
        ck = (name, info[0], info[2])
        if ck in self.sysref:
            return self.sysref[ck]
        cands = self.ref.sym_by_name.get(name, [])
        good = [c for c in cands if c[1] == info[0] and c[2] == info[2]] or \
               [c for c in cands if c[1] == info[0]]
        if not good:
            self.sysref[ck] = None
            return None
        good.sort(key=lambda c: (-self.ref.popular.get(c[0], 0), c[0]))
        self.sysref[ck] = good[0][0]
        return good[0][0]

    def add_ref(self, s, path, kind, off, ln, attr):
        lst = self.refs[(s["key"], path)]
        t = (kind, off, ln, attr)
        if t not in lst:
            lst.append(t)

    def sym_decl(self, cur, path, kind):
        s = self.get_sym(cur)
        if s is None:
            return
        n = cur.spelling
        ln = len(n)
        attr = 4 if cur.kind == self.ci.CursorKind.DESTRUCTOR else 0
        if cur.kind == self.ci.CursorKind.VAR_DECL and s["info"][3] == 1:
            kind = 2051
        if n.startswith("operator") and not (n[8:9].isalnum() or n[8:9] == "_"):
            ln = len(n) - 8 if False else len(n)
        self.add_ref(s, path, kind, cur.location.offset, ln, attr)

    def record_ref(self, c, path, ctx):
        CK = self.ci.CursorKind
        k, ref = c.kind, c.referenced
        if ref is None:
            return
        if k in (CK.TYPE_REF, CK.TEMPLATE_REF, CK.NAMESPACE_REF):
            s = self.get_sym(ref)
            if s is not None:
                e = c.extent
                self.add_ref(s, path, 4, e.start.offset, e.end.offset - e.start.offset,
                             16 if k == CK.TEMPLATE_REF and ref.kind == CK.CLASS_TEMPLATE else 0)
            return
        if k not in (CK.DECL_REF_EXPR, CK.MEMBER_REF_EXPR, CK.MEMBER_REF):
            return
        s = self.get_sym(ref)
        if s is None:
            return
        e = c.extent
        kind, attr = 4, 0
        nm = ref.spelling
        isop = nm.startswith("operator") and not (nm[8:9].isalnum() or nm[8:9] == "_")
        ln = (e.end.offset - e.start.offset) if isop else len(nm)
        if k == CK.MEMBER_REF and False:
            pass
        attr |= self.template_attr(ref)
        if k == CK.MEMBER_REF:
            kind = 2052
        elif ref.kind in (CK.VAR_DECL, CK.PARM_DECL, CK.FIELD_DECL):
            t = ref.type.get_canonical()
            scalar = t.kind.name not in ("RECORD", "CONSTANTARRAY", "INCOMPLETEARRAY", "UNEXPOSED", "ELABORATED")
            pk = ctx[0] if ctx and ctx[1] else None
            if pk == "assign":
                kind = 20 if scalar else 28
            elif pk in ("compound", "incdec", "opassign"):
                kind = 28
            else:
                kind = 12 if scalar else 4
        self.add_ref(s, path, kind, c.location.offset, ln, attr)

    def template_attr(self, ref):
        """symbol_refs attribute bits: 16 implicit instantiation, 32 parent is a class template"""
        CK = self.ci.CursorKind
        par = ref.semantic_parent
        in_tpl = par is not None and (par.kind == CK.CLASS_TEMPLATE or
                                      (par.kind in (CK.CLASS_DECL, CK.STRUCT_DECL) and
                                       par.get_num_template_arguments() > 0))
        a = 0
        if in_tpl:
            a |= 32
            if ref.kind in (CK.CXX_METHOD, CK.CONSTRUCTOR, CK.DESTRUCTOR, CK.FUNCTION_TEMPLATE):
                a |= 16
        elif ref.kind in (CK.FUNCTION_DECL, CK.FUNCTION_TEMPLATE) and (
                ref.kind == CK.FUNCTION_TEMPLATE or ref.get_num_template_arguments() > 0):
            a |= 16
        elif ref.spelling.startswith("operator") and ref.kind == CK.FUNCTION_DECL and \
                self.pf(ref.location.file) is None and ref.semantic_parent is not None and \
                ref.semantic_parent.kind == CK.NAMESPACE:
            a |= 16 if ref.type.spelling.count("basic_") else 0
        return a

    def collect_refs(self, cur, path):
        for c in cur.get_children():
            self.walk_refs(c, path, None)

    def walk_refs(self, c, path, ctx):
        CK = self.ci.CursorKind
        f = c.location.file
        if f is not None and self.pf(f) is None:
            return
        k = c.kind
        newctx = None
        if k == CK.BINARY_OPERATOR:
            kids = list(c.get_children())
            op = None
            if len(kids) == 2:
                lend = kids[0].extent.end.offset
                for t in c.get_tokens():
                    if t.extent.start.offset >= lend:
                        op = t.spelling
                        break
            if op == "=":
                newctx = "assign"
            elif op and op.endswith("=") and op not in ("==", "!=", "<=", ">="):
                newctx = "compound"
        elif k == CK.COMPOUND_ASSIGNMENT_OPERATOR:
            newctx = "compound"
        elif k == CK.UNARY_OPERATOR:
            ts = [t.spelling for t in c.get_tokens()]
            if "++" in ts or "--" in ts:
                newctx = "incdec"
        elif k == CK.CALL_EXPR and c.spelling == "operator=":
            newctx = "opassign"
        if k in (CK.DECL_REF_EXPR, CK.MEMBER_REF_EXPR, CK.MEMBER_REF, CK.TYPE_REF, CK.TEMPLATE_REF,
                 CK.NAMESPACE_REF):
            self.record_ref(c, path, ctx)
        elif k == CK.VAR_DECL:
            self.sym_decl(c, path, 3)
        for i, ch in enumerate(c.get_children()):
            self.walk_refs(ch, path, (newctx, i == 0) if newctx else None)


# --------------------------------------------------------------- DB writing

class SharedData:
    def __init__(self, con, first_free):
        self.con, self.next, self.by = con, first_free, {}

    def add(self, value, fixed_id=None):
        if fixed_id is None and value in self.by:
            return self.by[value]
        i = fixed_id if fixed_id is not None else self.next
        if fixed_id is None:
            self.next += 1
        self.con.execute("insert into shared_data(id,hash,value) values(?,?,?)",
                         (i, fnv1a_signed(value), value))
        self.by.setdefault(value, i)
        return i


def refs_json(lst):
    lst = sorted(lst, key=lambda t: (t[1], t[0]))
    return "[" + ",".join("[%d,%d,%d,%d]" % t for t in lst) + "]"


def build(args):
    t_start = time.time()
    vcx = glob.glob(os.path.join(args.project_dir, "*.vcxproj"))
    if not vcx:
        sys.exit("no .vcxproj in " + args.project_dir)
    proj = Project(vcx[0], args.config)
    win_sol = args.win_root.rstrip("\\")
    proj_win = win_sol + "\\" + proj.name
    ref = Ref(args.reference)
    rq = ref.q
    from clang import cindex as ci
    ex = Extractor(ci, proj, ref)
    for p in ex.pfiles:
        if os.path.exists(p):
            ex.text(p)
    ex.parse_all()

    out = args.out_dir
    os.makedirs(out, exist_ok=True)
    bpath, spath = os.path.join(out, "Browse.VC.db"), os.path.join(out, "Solution.VC.db")
    for pth in (bpath, spath):
        for suf in ("", "-wal", "-shm"):
            if os.path.exists(pth + suf):
                os.remove(pth + suf)
    sln = args.sln_name or os.path.basename(os.path.dirname(os.path.abspath(out)))
    browse_win = win_sol + "\\.vs\\" + sln + "\\v18\\"

    # ---- Solution.VC.db: schema plus the two property rows (VS leaves it nearly empty)
    sc = sqlite3.connect(spath)
    sc.execute("pragma page_size=4096")
    sc.execute("pragma journal_mode=wal")
    create_schema(sc, "Solution.schema.sql")
    sc.execute("insert into property(name,value) values('version','18.0001')")
    sc.execute("insert into property(name,value) values('path',?)", ((browse_win + "Solution.VC.db").upper(),))
    sc.commit()
    sc.execute("pragma wal_checkpoint(truncate)")
    sc.close()

    con = sqlite3.connect(bpath)
    con.execute("pragma page_size=8192")      # Browse.VC.db uses 8192, Solution.VC.db 4096
    con.execute("pragma journal_mode=wal")
    create_schema(con, "Browse.schema.sql")
    for t in ("parsers", "code_item_kinds"):
        rows = rq("select * from %s" % t)
        con.executemany("insert into %s values(%s)" % (t, ",".join("?" * len(rows[0]))), rows)
    props = dict(rq("select name,value from properties"))

    # ---- file ids: modules 1025/1026, project files, then system headers
    project_files = sorted(proj.files() + ([os.path.basename(proj.filters)] if proj.filters else []),
                           key=lambda f: to_win(os.path.join(proj.dir, f), proj.dir, proj_win).upper())
    next_file = 1027
    fid = {}
    for f in project_files:
        fid[os.path.realpath(os.path.join(proj.dir, f))] = next_file
        next_file += 1
    # ---- include graph and system closure
    seeds, missing = set(), set()
    proj_edges = collections.defaultdict(set)
    for path in ex.pfiles:
        for kind, nm, resolved in ex.includes.get(path, ()):
            if resolved and resolved in ex.pfiles:
                proj_edges[path].add(resolved)
            else:
                rid = ref.resolve_angle(nm)
                if rid is None:
                    missing.add(nm)
                else:
                    proj_edges[path].add(("S", rid))
                    seeds.add(rid)
    def tu_walk(tu):
        seen_p, direct, todo = set(), set(), [tu]
        while todo:
            x = todo.pop()
            if x in seen_p:
                continue
            seen_p.add(x)
            for e in proj_edges.get(x, ()):
                if isinstance(e, tuple):
                    direct.add(e[1])
                else:
                    todo.append(e)
        return seen_p, direct
    tu_info = {}
    for tu in ex.tu_list:
        pset, direct = tu_walk(tu)
        tu_info[tu] = (pset, ref.tu_system_files(direct))
    # files VS lists (files/config_files) = full include closure; the TU map is the narrower
    # set of headers that were really parsed
    sys_sel = {i for i in ref.closure(seeds) if i in ref.sys_set}
    ref_to_new = {1025: 1025, 1026: 1026}
    for i in ref.sys_ids:
        if i in sys_sel:
            ref_to_new[i] = next_file
            next_file += 1
    sys_new = {o: n for o, n in ref_to_new.items() if o in sys_sel}

    # ---- files and config_files
    frows, cfrows = [], []
    for f in project_files:
        p = os.path.realpath(os.path.join(proj.dir, f))
        w = to_win(p, proj.dir, proj_win).upper()
        leaf, ext = w.rsplit("\\", 1)[1], os.path.splitext(w)[1]
        is_cpp, is_h = f in proj.compile, f in proj.include
        if is_cpp or is_h:
            t = int(os.path.getmtime(p))
            pt = ex.times.get(p, 0.0004)
            frows.append((fid[p], t, round(pt, 7), round(pt / 8, 7), 0.0, w, leaf, ext, 0, CPP_PARSER))
            cfrows.append((CONFIG_ID, fid[p], 4 if is_cpp else 0, t, None, None, None))
        else:
            frows.append((fid[p], 0, 0.0, 0.0, 0.0, w, leaf, ext, 64, "0" * 32))
            cfrows.append((CONFIG_ID, fid[p], 0, 0, None, None, None))
    for i in (1025, 1026):
        frows.append(rq("select * from files where id=?", (i,))[0])
        cfrows.append(rq("select * from config_files where file_id=?", (i,))[0])
    for old, new in sys_new.items():
        r = list(rq("select * from files where id=?", (old,))[0]); r[0] = new
        frows.append(tuple(r))
        c = list(rq("select * from config_files where file_id=?", (old,))[0]); c[1] = new
        cfrows.append(tuple(c))
    con.executemany("insert into files values(?,?,?,?,?,?,?,?,?,?)", frows)

    # ---- config + shared strings (ids 1..7)
    sd = SharedData(con, 8)
    cfg = {r[0]: r[1] for r in rq("select id,value from shared_data where id<=7")}
    refwin = "C:\\Users\\jaron\\source\\repos\\LabDynamicMemory_WilsonJ_sol\\LabDynamicMemory_WilsonJ\\"
    ndef = " ".join("/D %s" % d for d in proj.defs + ["_UNICODE", "UNICODE"])
    for i in range(1, 8):
        v = cfg[i]
        if i == 5:
            v = ("/c /W3 /WX- %s /EHsc /MDd /fp:precise /Zc:wchar_t /Zc:forScope /std:%s /permissive- "
                 "/Fo\"x64\\Debug\\\\\" /external:W3 /Gd /TP /errorReport:prompt" % (ndef, proj.std_flag))
        elif i in (1, 2):
            v = re.sub(r"/std:\S+", "/std:" + proj.std_flag, v)
        elif i == 7:
            v = v.replace(refwin, proj_win + "\\")
        sd.add(v, fixed_id=i)
    cfg_row = list(rq("select * from configs")[0])
    cfg_row[1] = fnv1a_signed("%s|%s" % (proj_win.upper(), proj.config))
    con.execute("insert into projects values(?,?,?,?,?)",
                (PROJECT_ID, (proj_win + "\\" + proj.name + ".vcxproj").upper(), proj_win.upper(), proj.guid, 0))
    con.execute("insert into configs values(%s)" % ",".join("?" * len(cfg_row)), cfg_row)
    con.executemany("insert into config_files values(?,?,?,?,?,?,?)", cfrows)
    for r in rq("select * from hint_files"):
        con.execute("insert into hint_files values(?,?,?)", r)

    # ---- code items: system rows copied (file ids remapped), project rows built
    ci_rows = rq("select * from code_items where file_id in (%s)" %
                 ",".join(map(str, set(sys_new) | {1025, 1026})))
    keep_items, max_item = set(), ROOT_PARENT
    for r in ci_rows:
        r = list(r); r[1] = ref_to_new[r[1]]
        keep_items.add(r[0]); max_item = max(max_item, r[0])
        con.execute("insert into code_items values(%s)" % ",".join("?" * 22), r)
    next_item = max_item + 1
    emitted = []

    def emit(it, parent_id):
        nonlocal next_item
        it["id"] = next_item
        next_item += 1
        d = it["default"]
        dsp = it["dsp"] or (None,) * 4
        con.execute("insert into code_items values(%s)" % ",".join("?" * 22), (
            it["id"], fid[it["file"]], parent_id, it["kind"], it["attrs"], it["name"], it["type"],
            it["sc"], it["sl"], it["ec"], it["el"], it["nsc"], it["nsl"], it["nec"], it["nel"],
            d, dsp[0], dsp[1], dsp[2], dsp[3], it["pnum"], it["lower"][:4].lower()))
        emitted.append(it)
        for ch in it["children"]:
            emit(ch, it["id"])

    for p in sorted(ex.items, key=lambda x: fid[x]):
        for it in ex.items[p]:
            emit(it, ROOT_PARENT)
    for it in emitted:
        if it.get("assoc_text"):
            con.execute("insert into assoc_text values(?,?,?)", (it["id"],) + it["assoc_text"])
        if it.get("base_of"):
            con.execute("insert into base_class_parents values(?,?)", (it["id"], it["base_of"]["id"]))
        par = it["parent"]
        if it["kind"] == 27 and par.get("kind") == 53:     # qualifier range of out of class definitions
            line = ex.lines[it["file"]][it["nsl"] - 1].decode("utf-8", "replace")
            m = re.search(r"(\w+)(?:<[^>]*>)?::$", line[:it["nsc"] - 1])
            if m:
                con.execute("insert or ignore into assoc_spans values(?,?,?,?,?,?)",
                            (it["id"], 1, m.start(1) + 1, it["nsl"], it["nsc"] - 1, it["nsl"]))
    if keep_items:
        ks = ",".join(map(str, keep_items))
        for t in ("assoc_text", "assoc_spans"):
            rows = [r for r in rq("select * from %s" % t) if r[0] in keep_items]
            if rows:
                con.executemany("insert into %s values(%s)" % (t, ",".join("?" * len(rows[0]))), rows)
        con.executemany("insert into base_class_parents values(?,?)",
                        [r for r in rq("select * from base_class_parents")
                         if r[0] in keep_items and r[1] in keep_items])
        for cid, cfgid, ff in rq("select * from file_map"):
            if cid in keep_items and ff in ref_to_new:
                con.execute("insert into file_map values(?,?,?)", (cid, cfgid, ref_to_new[ff]))
    for it in emitted:
        if it["kind"] == 39:
            kind, nm, resolved = it["include"]
            tgt = fid.get(resolved) if resolved else None
            if tgt is None:
                rid = ref.resolve_angle(nm)
                tgt = ref_to_new.get(rid)
            if tgt:
                con.execute("insert or ignore into file_map values(?,?,?)", (it["id"], CONFIG_ID, tgt))

    # ---- file_tu_map
    tu_rows = set()
    for tu, (pset, sset) in tu_info.items():
        tu_rows |= {(fid[p], fid[tu], CONFIG_ID) for p in pset}
        tu_rows |= {(ref_to_new[x], fid[tu], CONFIG_ID) for x in sset if x in ref_to_new}
    con.executemany("insert into file_tu_map values(?,?,?)", sorted(tu_rows))

    # ---- symbols
    sel = ",".join(map(str, set(sys_new) | {1025, 1026}))
    sref_rows = rq("select * from symbol_refs where file_id in (%s)" % sel)
    used = {r[0] for r in sref_rows}
    for k in ex.sym_order:
        if ex.syms[k]["ref_id"] is not None:
            used.add(ex.syms[k]["ref_id"])
    sym_rows = {r[0]: r for r in rq("select * from symbols where id in (%s)" % ",".join(map(str, used or {0})))}
    for r in sym_rows.values():
        con.execute("insert into symbols values(?,?,?,?,?,?,?,?)", r)
    tmpl_rows = [r for r in rq("select * from template_args where file_id in (%s)" % sel) if r[0] in sym_rows]
    need = {v for r in sref_rows for v in (r[3], r[4]) if v} | {r[4] for r in tmpl_rows}
    maxid = 7
    for i, h, v in rq("select id,hash,value from shared_data where id in (%s)" % ",".join(map(str, need or {0}))):
        con.execute("insert into shared_data values(?,?,?)", (i, h, v))
        maxid = max(maxid, i)
        sd.by.setdefault(v, i)
    sd.next = maxid + 1
    for r in sref_rows:
        con.execute("insert into symbol_refs values(?,?,?,?,?)", (r[0], ref_to_new[r[1]], r[2], r[3], r[4]))
    for r in rq("select * from symbol_relations"):
        if r[0] in sym_rows and r[1] in sym_rows:
            con.execute("insert into symbol_relations values(?,?,?,?)", r)
    for r in tmpl_rows:
        con.execute("insert into template_args values(?,?,?,?,?)", (r[0], r[1], ref_to_new[r[2]], r[3], r[4]))
    next_sym = (max(sym_rows) if sym_rows else 0) + 1
    new_sym = {}
    for k in ex.sym_order:
        s = ex.syms[k]
        if s["ref_id"] is not None:
            new_sym[k] = s["ref_id"]
            continue
        new_sym[k] = next_sym
        kind, sem, sk, fl = s["info"]
        con.execute("insert into symbols values(?,?,?,?,?,?,?,?)",
                    (next_sym, fnv1a_signed("%s|%s" % (proj.name, k)), s["name"], None, kind, sem, sk, fl))
        next_sym += 1
    by_sf = {}
    for (k, path), lst in ex.refs.items():
        if k in new_sym and path in fid:
            cur = by_sf.setdefault((new_sym[k], fid[path]), [])
            cur.extend(t for t in lst if t not in cur)
    for (sid, f), lst in sorted(by_sf.items(), key=lambda x: (x[0][1], x[0][0])):
        dd = [t for t in lst if t[0] & 3]
        uu = [t for t in lst if not t[0] & 3]
        a = sd.add(con.execute("select jsonb(?)", (refs_json(dd),)).fetchone()[0]) if dd else None
        b = sd.add(con.execute("select jsonb(?)", (refs_json(uu),)).fetchone()[0]) if uu else None
        con.execute("insert or ignore into symbol_refs values(?,?,?,?,?)", (sid, f, CONFIG_ID, a, b))
    # relations for project classes: derived_of / special_function_of
    sym_of_item = {}
    for it in emitted:
        pass

    # ---- FTS (content is approximate, see NOTES.md)
    FK = {1, 2, 3, 4, 6, 7, 8, 17, 18, 20, 21, 26, 27, 28, 10, 16, 37, 38}
    per_file = collections.defaultdict(list)
    for it in emitted:
        per_file[fid[it["file"]]].append((it["kind"], it["name"], it["type"]))
    for r in ci_rows:
        per_file[ref_to_new[r[1]]].append((r[3], r[5], r[6]))
    for f in sorted(per_file):
        items = per_file[f]
        names = list(dict.fromkeys(n for k, n, t in items if k in FK and n))
        if names:
            con.execute("insert into code_items_fts(rowid,names) values(?,?)", (f, "\n".join(names)))
        ids = []
        for n, t in ((n, t) for k, n, t in items):
            for w in re.findall(r"[A-Za-z_]\w*", (n or "") + " " + (t or "")):
                if w not in ids:
                    ids.append(w)
        con.execute("insert into identifiers_fts(rowid,identifiers) values(?,?)", (f, "\n".join(ids)))

    n_items = con.execute("select count(*) from code_items").fetchone()[0]
    for n, v in (("version", props["version"]), ("client_version", "18.0"),
                 ("path", browse_win + "Browse.VC.db"), ("enhanced_fts", "false"),
                 ("comment_tokens", props["comment_tokens"]), ("symbols_version", props["symbols_version"]),
                 ("symbols_locals", "true"), ("symbols_all_externals", "false"),
                 ("indexes_ready", "true"), ("safe_to_open", "true"),
                 ("code_items_cnt", str(n_items)), ("code_items_mod", str(n_items))):
        con.execute("insert into properties values(?,?)", (n, v))
    con.commit()
    con.execute("pragma wal_checkpoint(truncate)")
    con.close()
    print("wrote %s and %s in %.1fs" % (bpath, spath, time.time() - t_start))
    if missing:
        print("includes not found in the reference (rows missing):", ", ".join(sorted(missing)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--win-root", required=True,
                    help="Windows path of the solution folder, e.g. C:\\Users\\me\\source\\repos\\Sol")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--reference", default=DEFAULT_REF)
    ap.add_argument("--config", default="Debug|x64")
    ap.add_argument("--sln-name", default=None,
                    help="name of the .vs subfolder, e.g. Sol.slnx (default: parent folder of out-dir)")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
