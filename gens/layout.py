"""DocumentLayout.json / .backup.json / .vcxproj.user (byte exact for the reference parameters, see docs/suo-layout-format.md)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_layout as L


def generate(lab, v18_dir):
    p = L.discover(str(lab.sol_dir), lab.win_repos, None)
    data = L.dump_layout(L.build_layout(p))
    for n in ("DocumentLayout.json", "DocumentLayout.backup.json"):
        open(os.path.join(str(v18_dir), n), "wb").write(data)
    up = os.path.join(p["proj_dir"], p["proj_name"] + ".vcxproj.user")
    if not os.path.exists(up):
        open(up, "wb").write(L.VCXPROJ_USER.encode("utf-8"))
