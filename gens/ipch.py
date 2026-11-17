"""AutoPCH .ipch generator: exact directory hash and exact head (see docs/ipch-format.md); the memory image after the head
is not reproducible and is written as sparse zeros.

The list of files in the head comes from the real compiler (cl /showIncludes, same include order as Visual Studio's IntelliSense
front end read in the reference), and the modification times are the real times of the files on this machine."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ipch_core as core


def generate_all(lab, root, sources, closure=None, mtime=None):
    """closure(src) -> ordered list of Windows paths of every header read; mtime(winpath) -> unix seconds or None"""
    ref = core.load_ref()
    model = core.SysModel(ref)
    proj_win = lab.win_proj
    proj_up = proj_win.upper()
    out = []
    for s in sources:
        s_abs = str(lab.proj_dir / s)
        if not os.path.isfile(s_abs):
            continue
        if closure:
            ents = []
            for p in closure(s):
                if p.upper().startswith(proj_up + "\\"):
                    local = lab.proj_dir / p[len(proj_win) + 1:].replace("\\", "/")
                    ents.append((proj_up + "\\" + p[len(proj_win) + 1:], int(os.stat(local).st_mtime)))
                else:
                    t = mtime(p) if mtime else None
                    ents.append((p, int(t) if t is not None else core.SYS_MTIME_MSVC))
            core.build_file_table = lambda src, pd, pu, mdl, rf, _e=ents: _e
        h, head, size = core.build_ipch(s_abs, proj_win + "\\" + s, proj_win, lab.win_sol, lab.sol_name + ".slnx",
                                        str(lab.proj_dir), "Debug", "x64", ref, model, None)
        d = os.path.join(root, h)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, os.path.splitext(s)[0].upper() + ".ipch")
        core.write_sparse(p, head, size)
        out.append(p)
    return out
