"""Browse.VC.db with real symbols for the project (libclang), see docs/vcdb-format.md.

Needs (a) the libclang venv that install.sh makes in $VSLAB_ROOT/venv and (b) a seed: a Browse.VC.db written by a real Visual Studio 18
($VSLAB_ROOT/reference/Browse.VC.db, made by `vslab seed <real-vs-zip>`). The seed supplies the rows for Microsoft's own headers.
Without either, the caller falls back to a schema-only database."""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def available(root):
    return os.path.exists(os.path.join(root, "venv/bin/python")) and os.path.exists(os.path.join(root, "reference/Browse.VC.db"))


def generate(lab, dest):
    root = os.environ.get("VSLAB_ROOT", os.path.expanduser("~/.local/share/vslab"))
    if not available(root):
        raise FileNotFoundError("no libclang venv or seed database")
    out = os.path.dirname(str(dest))
    cmd = [os.path.join(root, "venv/bin/python"), os.path.join(HERE, "_vcdb_core.py"), "--project-dir", str(lab.proj_dir),
           "--win-root", lab.win_sol, "--out-dir", out, "--reference", os.path.join(root, "reference/Browse.VC.db"),
           "--sln-name", lab.sol_name + ".slnx"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:])
    for line in r.stdout.splitlines():
        if line.startswith("includes not found"):
            print("vslab:", line)
