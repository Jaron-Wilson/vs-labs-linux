"""AutoPCH .ipch generator: exact directory hash and exact head, memory image body written as sparse zeros
(see docs/ipch-format.md)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ipch_core as core


def generate_all(lab, root, sources):
    """write root/<hash>/<STEM>.ipch for each source file name; returns list of paths"""
    ref = core.load_ref()
    model = core.SysModel(ref)
    sln_win = lab.win_sol
    proj_win = lab.win_proj
    out = []
    for s in sources:
        s_abs = str(lab.proj_dir / s)
        if not os.path.isfile(s_abs):
            continue
        h, head, size = core.build_ipch(s_abs, proj_win + "\\" + s, proj_win, sln_win, lab.sol_name + ".slnx",
                                        str(lab.proj_dir), "Debug", "x64", ref, model, None)
        d = os.path.join(root, h)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, os.path.splitext(s)[0].upper() + ".ipch")
        core.write_sparse(p, head, size)
        out.append(p)
    return out
