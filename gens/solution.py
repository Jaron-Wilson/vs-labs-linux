"""Solution.VC.db: schema copied from Visual Studio plus its two property rows (byte size identical to the real file)."""
import os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def generate(lab, dest):
    import re
    here = os.path.dirname(os.path.abspath(__file__))
    for suf in ("", "-wal", "-shm"):
        if os.path.exists(str(dest) + suf):
            os.remove(str(dest) + suf)
    sc = sqlite3.connect(str(dest))
    sc.execute("pragma page_size=4096")
    sc.execute("pragma journal_mode=wal")
    stmts = [s.strip("\n") for s in open(os.path.join(here, "Solution.schema.sql"), encoding="utf-8").read().split("\n;;\n") if s.strip()]
    for sql in stmts:
        if re.match(r"CREATE TABLE '\w+_(?:data|idx|docsize|config)'", sql):
            continue
        sc.execute(sql)
    path = lab.win_sol + "\\.vs\\" + lab.sol_name + ".slnx\\v18\\Solution.VC.db"
    sc.execute("insert into property(name,value) values('version','18.0001')")
    sc.execute("insert into property(name,value) values('path',?)", (path.upper(),))
    sc.commit()
    sc.execute("pragma wal_checkpoint(truncate)")
    sc.close()
