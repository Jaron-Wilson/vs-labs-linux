"""FileContentIndex/*.vsidx generator (format decoded from a real Visual Studio 18 file, see docs/vsidx-format.md)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vsidx_core as core


def generate(lab, dest):
    files = core.find_files(str(lab.sol_dir))
    wins = [lab.win_sol + "\\" + os.path.relpath(p, lab.sol_dir).replace("/", "\\") for p in files]
    order = sorted(range(len(files)), key=lambda i: wins[i].upper())
    files = [files[i] for i in order]
    wins = [wins[i] for i in order]
    data = core.build(files, wins, [os.stat(p).st_mtime_ns for p in files])
    dest.write_bytes(data)
