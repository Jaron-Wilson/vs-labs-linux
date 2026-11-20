#!/usr/bin/env python3
"""Tests for the vslab zip path length check, --clean and --flat. Standard library only.   python3 tests/test_zip.py"""
import importlib.machinery, importlib.util, os, subprocess, sys, tempfile, unittest, zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
VSLAB = os.path.join(ROOT, "bin", "vslab")
loader = importlib.machinery.SourceFileLoader("vslab_mod", VSLAB)
spec = importlib.util.spec_from_loader("vslab_mod", loader)
vl = importlib.util.module_from_spec(spec)
loader.exec_module(vl)

NAME = "LabPolyMorphOp_WilsonJ"
GUID = "{AF636384-1111-2222-3333-444455556666}"
SOL = NAME + "_sol"


def make_lab(base):
    """a real new lab (vslab new, no Wine needed) plus fake build output and editor cache folders"""
    subprocess.run([sys.executable, VSLAB, "new", NAME, "--dir", base], check=True, capture_output=True)
    sol = os.path.join(base, SOL)
    proj = os.path.join(sol, NAME)
    os.makedirs(os.path.join(proj, "x64", "Debug", "LabPolyM.af636384.tlog"), exist_ok=True)
    os.makedirs(os.path.join(sol, "x64", "Debug"), exist_ok=True)
    os.makedirs(os.path.join(sol, ".vs", "v18"), exist_ok=True)
    for p in (os.path.join(proj, "x64", "Debug", "main.obj"), os.path.join(sol, "x64", "Debug", NAME + ".exe")):
        with open(p, "w") as f:
            f.write("x")
    return sol


def run_zip(sol, *args):
    out = os.path.join(os.path.dirname(sol), "out.zip")
    r = subprocess.run([sys.executable, VSLAB, "zip", "-o", out, *args], cwd=sol, capture_output=True, text=True)
    return r, out


class PathLength(unittest.TestCase):
    def test_tlog_name(self):
        self.assertEqual(vl.tlog_dir_name(NAME, GUID), "LabPolyM.af636384.tlog")
        self.assertEqual(vl.tlog_dir_name("Short", GUID), "Short.tlog")

    def test_example_is_264(self):
        pre = SOL + "/" + NAME + "/"
        created = vl.build_created_entries(NAME, GUID, pre)
        n, longest = vl.longest_extracted_path([], SOL, created, base_len=116)
        self.assertEqual(n, 264)
        self.assertTrue(longest.endswith("LabPolyM.af636384.tlog\\" + NAME + ".lastbuildstate"))
        self.assertIn(SOL + "\\" + SOL + "\\", longest)
        self.assertIn("MAX_PATH", vl.path_length_warning(n, longest, 116))

    def test_flat_clean_is_short(self):
        created = vl.build_created_entries(NAME, GUID, NAME + "/")
        n, _ = vl.longest_extracted_path([], SOL, created, base_len=116)
        self.assertEqual(n, 116 + 1 + 26 + 1 + 22 + 1 + 10 + 23 + 37)
        self.assertLess(n, 260)
        self.assertIsNone(vl.path_length_warning(237, "x"))

    def test_close_note(self):
        w = vl.path_length_warning(250, "x")
        self.assertIn("close to", w)
        self.assertIn("--clean --flat", w)
        self.assertIsNone(vl.path_length_warning(240, "x"))


class ZipCommand(unittest.TestCase):
    def names(self, out):
        with zipfile.ZipFile(out) as z:
            return z.namelist()

    def test_default_keeps_everything_and_warns(self):
        with tempfile.TemporaryDirectory() as t:
            sol = make_lab(t)
            r, out = run_zip(sol, "--base-len", "116")
            self.assertEqual(r.returncode, 0, r.stderr)
            n = self.names(out)
            self.assertIn(SOL + "/.vs/", n)
            self.assertIn(SOL + "/x64/Debug/" + NAME + ".exe", n)
            self.assertTrue(all("\\" not in x for x in n))
            self.assertIn("WARNING", r.stderr)

    def test_clean_excludes_build_folders(self):
        with tempfile.TemporaryDirectory() as t:
            sol = make_lab(t)
            r, out = run_zip(sol, "--clean")
            n = self.names(out)
            self.assertFalse([x for x in n if "/.vs" in x or "/x64" in x or "/Debug" in x])
            self.assertIn(SOL + "/" + NAME + "/" + NAME + ".vcxproj.user", n)
            self.assertIn(SOL + "/" + NAME + "/" + NAME + ".cpp", n)

    def test_flat_has_slnx_at_root_and_clean_flat_quiet(self):
        with tempfile.TemporaryDirectory() as t:
            sol = make_lab(t)
            r, out = run_zip(sol, "--clean", "--flat", "--base-len", "116")
            n = self.names(out)
            self.assertIn(SOL + ".slnx", n)
            self.assertIn(NAME + "/" + NAME + ".cpp", n)
            self.assertFalse([x for x in n if x.startswith(SOL + "/")])
            self.assertNotIn("WARNING", r.stderr)


if __name__ == "__main__":
    unittest.main()
