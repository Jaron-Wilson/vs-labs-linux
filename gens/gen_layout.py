#!/usr/bin/env python3
"""Generate .vs/<sln>/v18/DocumentLayout.json (+ DocumentLayout.backup.json),
the per-project .vcxproj.user, and shared solution discovery helpers used by
gen_suo.py.

Usage:
  gen_layout.py SOLUTION_DIR [--win-repos-root 'C:\\Users\\me\\source\\repos']
                [--docs Main.cpp Employee.cpp ...] [--no-user-file]

Defaults: open documents = the project's .cpp files (Main.cpp first),
Debug|x64, the solution's only project is the startup project.  Timestamps
(WhenOpened) are the real time the script runs, never invented.
"""
import argparse, base64, datetime, getpass, json, os, re, struct, sys
import xml.etree.ElementTree as ET

CPP_DOC_TYPE = "{D0E1A5C6-B359-4E41-9B60-3365922C2A22}"   # C++ editor factory
CPP_ICON = "ae27a6b0-e345-4288-96df-5eaf394ee369.000677|"
TEXT_DOC_TYPE = "{8B382828-6202-11D1-8870-0000F87579D2}"   # plain text editor (txt files)


def doc_kind(name):
    """(editor factory guid, icon) as seen in real VS 18 layouts."""
    e = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if e in ("cpp", "cc", "cxx", "c"):
        return CPP_DOC_TYPE, CPP_ICON
    if e in ("h", "hpp", "hh", "hxx"):
        return CPP_DOC_TYPE, "ae27a6b0-e345-4288-96df-5eaf394ee369.000680|"
    return TEXT_DOC_TYPE, "ae27a6b0-e345-4288-96df-5eaf394ee369.003109|"
VCXPROJ_USER = ('\ufeff<?xml version="1.0" encoding="utf-8"?>\r\n'
                '<Project ToolsVersion="Current" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">\r\n'
                '  <PropertyGroup />\r\n</Project>')


def find_solution(sol_dir):
    for ext in (".slnx", ".sln"):
        for f in sorted(os.listdir(sol_dir)):
            if f.endswith(ext):
                return f
    raise SystemExit("no .slnx/.sln in " + sol_dir)


def discover(sol_dir, win_repos_root=None, docs=None):
    """Return a params dict describing the solution (all paths Windows style)."""
    sol_dir = os.path.abspath(sol_dir)
    sol_file = find_solution(sol_dir)
    sol_name = sol_file.rsplit(".", 1)[0]
    ext = sol_file.rsplit(".", 1)[1]
    projects = []
    if ext == "slnx":
        root = ET.parse(os.path.join(sol_dir, sol_file)).getroot()
        for p in root.iter("Project"):
            projects.append((p.get("Path"), (p.get("Id") or "").upper()))
    else:
        txt = open(os.path.join(sol_dir, sol_file), encoding="utf-8-sig").read()
        for m in re.finditer(r'Project\("\{[^}]+\}"\) = "[^"]*", "([^"]+\.vcxproj)", "(\{[^}]+\})"', txt):
            projects.append((m.group(1).replace("\\", "/"), m.group(2).strip("{}").upper()))
    if not projects:
        raise SystemExit("no project in solution")
    proj_path, guid = projects[0]
    vcx_abs = os.path.join(sol_dir, proj_path)
    vtxt = open(vcx_abs, encoding="utf-8-sig").read()
    if not guid:
        guid = re.search(r"<ProjectGuid>\{([^}]+)\}", vtxt).group(1).upper()
    configs = re.findall(r'<ProjectConfiguration Include="([^"|]+)\|([^"]+)"', vtxt) or [("Debug", "x64")]
    proj_dir_rel = os.path.dirname(proj_path).replace("/", "\\")
    proj_name = os.path.basename(proj_path).rsplit(".", 1)[0]
    proj_dir = os.path.dirname(vcx_abs)
    if docs is None:
        cpps = sorted(f for f in os.listdir(proj_dir) if f.lower().endswith(".cpp"))
        cpps.sort(key=lambda f: (f.lower() != "main.cpp", f.lower()))   # Main.cpp first
        docs = cpps
    user = getpass.getuser()
    repos = win_repos_root or ("C:\\Users\\%s\\source\\repos" % user)
    repos = repos.rstrip("\\")
    filters = []
    fpath = vcx_abs + ".filters"
    if os.path.exists(fpath):
        filters = re.findall(r'<Filter Include="([^"]+)"', open(fpath, encoding="utf-8-sig").read())
    return dict(sol_dir=sol_dir, sol_file=sol_file, sol_name=sol_name, sol_ext=ext,
                proj_rel=proj_path.replace("/", "\\"), proj_dir_rel=proj_dir_rel, proj_name=proj_name,
                proj_dir=proj_dir, guid=guid, configs=configs, docs=docs,
                win_repos=repos, win_sol_dir="%s\\%s\\" % (repos, os.path.basename(sol_dir)),
                filters=sorted(filters))


def win_doc(p, name):
    base = p["win_sol_dir"] + (p["proj_dir_rel"] + "\\" if p["proj_dir_rel"] else "")
    return base + name, (p["proj_dir_rel"] + "\\" if p["proj_dir_rel"] else "") + name


def viewstate_bytes(v=(0, 0, 0)):
    """28 byte editor view state: u8 2, u8 2, u16 0, then u32 at offset 4 = first visible
    line, offset 16 = caret line, offset 20 = caret column (0 based lines)."""
    top, caret, col = (tuple(v) + (0, 0))[:3]
    b = bytearray(28); b[0] = 2; b[1] = 2
    struct.pack_into("<I", b, 4, top); struct.pack_into("<I", b, 16, caret); struct.pack_into("<I", b, 20, col)
    return bytes(b)


def viewstate(v=(0, 0)):
    return base64.b64encode(viewstate_bytes(v)).decode()


def iso(dt):
    """JS style: milliseconds with trailing zeros trimmed, none when zero (as VS writes)."""
    ms = ("%03d" % (dt.microsecond // 1000)).rstrip("0")
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + ("." + ms if ms else "") + "Z"


def build_layout(p, when=None, tab_order=None, selected=0, views=None):
    """p from discover().  when: list of datetimes (UTC) per doc; views: {name:(top,caret) or 6 tuple}."""
    now = datetime.datetime.now(datetime.timezone.utc)
    docs = p["docs"]
    when = when or [now - datetime.timedelta(seconds=len(docs) - i) for i in range(len(docs))]
    views = views or {}
    gid = "{%s}" % p["guid"]
    pre = "D:0:0:%s|%s|" % (gid, p["proj_rel"])
    documents, children = [], {}
    for i, name in enumerate(docs):
        absn, reln = win_doc(p, name)
        fac, icon = doc_kind(name)
        documents.append(dict(
            AbsoluteMoniker="%s%s||%s" % (pre, absn, fac),
            RelativeMoniker="%ssolutionrelative:%s||%s" % (pre, reln, fac)))
        children[i] = {"$type": "Document", "DocumentIndex": i, "Title": name,
                       "DocumentMoniker": absn, "RelativeDocumentMoniker": reln,
                       "ToolTip": absn, "RelativeToolTip": reln,
                       "ViewState": viewstate(views.get(name, (0, 0))), "Icon": icon,
                       "WhenOpened": iso(when[i]), "EditorCaption": ""}
    order = tab_order if tab_order is not None else list(range(len(docs)))
    layout = {"Version": 1, "WorkspaceRootPath": p["win_sol_dir"], "Documents": documents,
              "DocumentGroupContainers": [{"Orientation": 0, "VerticalTabListWidth": 256,
                  "DocumentGroups": [{"DockedWidth": 200, "SelectedChildIndex": selected,
                                      "Children": [children[i] for i in order]}]}]}
    return layout


def dump_layout(layout):
    # VS writes 2-space indent, CRLF, no BOM, no trailing newline
    return json.dumps(layout, indent=2, ensure_ascii=False).replace("\n", "\r\n").encode("utf-8")


def vs_dir(p):
    return os.path.join(p["sol_dir"], ".vs", p["sol_file"], "v18")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sol_dir")
    ap.add_argument("--win-repos-root")
    ap.add_argument("--docs", nargs="*")
    ap.add_argument("--no-user-file", action="store_true")
    a = ap.parse_args()
    p = discover(a.sol_dir, a.win_repos_root, a.docs)
    out = vs_dir(p); os.makedirs(out, exist_ok=True)
    data = dump_layout(build_layout(p))
    for n in ("DocumentLayout.json", "DocumentLayout.backup.json"):
        open(os.path.join(out, n), "wb").write(data)
    if not a.no_user_file:
        up = os.path.join(p["proj_dir"], p["proj_name"] + ".vcxproj.user")
        if not os.path.exists(up):
            open(up, "wb").write(VCXPROJ_USER.encode("utf-8"))
    print("wrote layout for", p["sol_name"], "docs:", ", ".join(p["docs"]))


if __name__ == "__main__":
    main()
