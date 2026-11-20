"""Browse.VC.db schema layouts and the status checks for the libclang venv and the seed.

Two layouts exist. "v18_0" is the one older Visual Studio 18 builds write (symbol_relations is a table, template_args has no
nesting_level). "v18_12" is what Visual Studio 18.12 (toolset 14.52) writes: symbol_rels_free and symbol_rels_owned tables with
symbol_relations as a view over them, nesting_level in template_args, and the *_ex / *_debug views. The DDL files are statements
copied verbatim from a real database's sqlite_master, separated by a line holding two semicolons.

Only the standard library is used here, so bin/vslab and the tests can import it without the libclang venv."""
import os, re, sqlite3, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OLD, NEW = "v18_0", "v18_12"
SCHEMA_FILES = {OLD: "Browse.schema.sql", NEW: "Browse.schema.v18_12.sql"}
SOLUTION_SCHEMA = "Solution.schema.sql"
PAGE_SIZE = 8192
_SHADOW = re.compile(r"CREATE TABLE '\w+_(?:data|idx|docsize|config)'")


def statements(ddl_file):
    with open(os.path.join(HERE, ddl_file), encoding="utf-8") as f:
        return [s.strip("\n") for s in f.read().split("\n;;\n") if s.strip()]


def create_schema(con, ddl_file):
    """Run the DDL. FTS5 shadow tables come with CREATE VIRTUAL TABLE, so their own statements are skipped."""
    for sql in statements(ddl_file):
        if _SHADOW.match(sql):
            continue
        con.execute(sql)


def seed_layout(path):
    """Layout of a Browse.VC.db written by a real Visual Studio, read from its schema. None if it cannot be read."""
    try:
        con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
        try:
            names = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        finally:
            con.close()
    except sqlite3.Error:
        return None
    return NEW if "symbol_rels_free" in names else OLD


def layout_for_vs(version):
    """version: (major, minor) of Visual Studio or None when unknown. Unknown means the current release, the one the README targets."""
    if version is None:
        return NEW
    return NEW if tuple(version[:2]) >= (18, 12) else OLD


def pick_layout(seed_path=None, vs_version=None):
    """The seed's own schema wins (the output has to match the rows it supplies); without a seed, the Visual Studio version decides."""
    if seed_path and os.path.exists(seed_path):
        lay = seed_layout(seed_path)
        if lay:
            return lay
    return layout_for_vs(vs_version)


def create_browse_db(path, layout):
    """Empty Browse.VC.db with the exact schema of the layout (8192 byte pages, WAL like Visual Studio's)."""
    con = sqlite3.connect(path)
    con.execute("pragma page_size=%d" % PAGE_SIZE)
    con.execute("pragma journal_mode=wal")
    create_schema(con, SCHEMA_FILES[layout])
    con.commit()
    return con


# ------------------------------------------------------------------ venv and seed status

def venv_python(root):
    return os.path.join(str(root), "venv", "bin", "python")


def venv_status(root, run=True):
    """(ok, one line reason). ok means the venv exists and can import clang.cindex."""
    py = venv_python(root)
    if not os.path.exists(py):
        return False, "no venv at %s (run install.sh, or: python3 -m venv %s/venv && %s/venv/bin/pip install libclang)" % (
            os.path.join(str(root), "venv"), root, root)
    if not run:
        return True, "venv present"
    try:
        r = subprocess.run([py, "-c", "import clang.cindex"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return False, "venv python does not run: %s" % e
    if r.returncode != 0:
        return False, "libclang is not installed in the venv (%s/venv/bin/pip install libclang)" % root
    return True, "venv with libclang"


def seed_path(root):
    return os.path.join(str(root), "reference", "Browse.VC.db")


def seed_status(root):
    """(ok, one line reason)."""
    p = seed_path(root)
    if not os.path.exists(p):
        return False, "no seed at %s (run: vslab seed REAL_VS_ZIP)" % p
    lay = seed_layout(p)
    if lay is None:
        return False, "seed at %s is not a readable SQLite database" % p
    return True, "seed present, layout %s (%d KiB)" % (lay, os.path.getsize(p) // 1024)


def generator_problem(root):
    """One line reason why the full Browse generator cannot run, or None."""
    ok, why = venv_status(root)
    if not ok:
        return why
    ok, why = seed_status(root)
    if not ok:
        return why
    return None
