"""Visual Studio .suo (OLE compound file) generator, see docs/suo-layout-format.md."""
import datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_layout as L
import gen_suo as S


def generate(lab, dest):
    p = L.discover(str(lab.sol_dir), lab.win_repos, lab.tabs()[0])
    streams = S.build_streams(p, "Debug|x64")
    S.write_cfb(str(dest), streams, S.filetime(datetime.datetime.now(datetime.timezone.utc)))
