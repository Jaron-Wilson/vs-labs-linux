#!/usr/bin/env python3
"""Tests for the Browse.VC.db schema layouts, named seed reading and venv/seed detection. Standard library only, no Microsoft files:
the seeds are built here from the repo's own DDL.   python3 tests/test_vcdb.py"""
import os, sqlite3, stat, sys, tempfile, unittest

GENS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gens")
sys.path.insert(0, GENS)
import _vcdb_schema as vs
import _vcdb_core as core


def have_fts5_delete():
    try:
        sqlite3.connect(":memory:").execute("create virtual table t using fts5(a, content='', contentless_delete=1)")
        return True
    except sqlite3.Error:
        return False


needs_sqlite = unittest.skipUnless(have_fts5_delete(), "this SQLite has no FTS5 contentless_delete")


def make_seed(path, layout):
    con = vs.create_browse_db(path, layout)
    con.execute("insert into shared_data(id,hash,value) values(6,0,'C:\\VS\\INCLUDE')")
    con.execute("insert into files(id,timestamp,parsetime,addtime,difftime,name,leaf_name,extension,attributes,parser_guid) "
                "values(1030,0,0,0,0,'C:\\VS\\INCLUDE\\A.H','A.H','.H',0,'G')")
    for i in (1, 2):
        con.execute("insert into symbols(id,moniker_hash,name,declaration,kind,semantic_token_kind,symbol_kind,flags) values(?,0,?,null,0,0,0,0)", (i, "s%d" % i))
    con.execute("insert into symbol_refs(symbol_id,file_id,config_id,decl_defn_refs,usage_refs) values(1,1030,1025,5,null)")
    if layout == vs.NEW:
        con.execute("insert into template_args(symbol_id,config_id,nesting_level,file_id,offset,args) values(1,1025,0,1030,10,77)")
        con.execute("insert into template_args(symbol_id,config_id,nesting_level,file_id,offset,args) values(1,1025,1,1030,10,78)")
        con.execute("insert into symbol_rels_owned values(1,2,1025,0,1030)")
        con.execute("insert into symbol_rels_free values(1,2,1025,4)")
    else:
        con.execute("insert into template_args(symbol_id,config_id,file_id,offset,args) values(1,1025,1030,10,77)")
        con.execute("insert into symbol_relations values(1,2,1025,0)")
        con.execute("insert into symbol_relations values(1,2,1025,4)")
    con.commit()
    con.close()


class Schema(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)

    def objs(self, layout):
        p = os.path.join(self.d.name, layout + ".db")
        vs.create_browse_db(p, layout).close()
        con = sqlite3.connect(p)
        return {n: t for t, n in con.execute("select type,name from sqlite_master where name not like 'sqlite_%'")}

    @needs_sqlite
    def test_old_layout(self):
        o = self.objs(vs.OLD)
        self.assertEqual(o["symbol_relations"], "table")
        self.assertNotIn("symbol_rels_free", o)
        con = sqlite3.connect(os.path.join(self.d.name, "v18_0.db"))
        cols = [r[1] for r in con.execute("pragma table_info(template_args)")]
        self.assertNotIn("nesting_level", cols)

    @needs_sqlite
    def test_new_layout(self):
        o = self.objs(vs.NEW)
        self.assertEqual(o["symbol_relations"], "view")
        for t in ("symbol_rels_free", "symbol_rels_owned", "code_items_fts", "identifiers_fts"):
            self.assertEqual(o[t], "table", t)
        for v in ("configs_ex", "config_files_ex", "project_refs_ex", "symbol_refs_ex", "symbol_refs_decl_defn_ex", "config_files_debug",
                  "configs_debug", "files_debug", "symbol_definition_ranges_debug", "symbol_refs_debug", "symbol_relations_debug", "symbols_debug"):
            self.assertEqual(o[v], "view", v)
        for i in ("ix_symbol_rels_free_target_symbol_id", "ix_symbol_rels_free_config_id", "ix_symbol_rels_owned_config_id_file_id",
                  "ix_symbol_rels_owned_target_symbol_id"):
            self.assertEqual(o[i], "index", i)
        con = sqlite3.connect(os.path.join(self.d.name, "v18_12.db"))
        self.assertEqual([r[1] for r in con.execute("pragma table_info(template_args)")],
                         ["symbol_id", "config_id", "nesting_level", "file_id", "offset", "args"])
        self.assertEqual(con.execute("pragma page_size").fetchone()[0], 8192)
        self.assertEqual(con.execute("pragma journal_mode").fetchone()[0], "wal")

    @needs_sqlite
    def test_schema_matches_ddl_file_in_order(self):
        for lay in (vs.OLD, vs.NEW):
            p = os.path.join(self.d.name, lay + ".db")
            vs.create_browse_db(p, lay).close()
            got = [r[0] for r in sqlite3.connect(p).execute("select sql from sqlite_master where sql is not null order by rowid")]
            self.assertEqual(got, vs.statements(vs.SCHEMA_FILES[lay]), lay)

    def test_layout_choice(self):
        self.assertEqual(vs.layout_for_vs((18, 12)), vs.NEW)
        self.assertEqual(vs.layout_for_vs((18, 13)), vs.NEW)
        self.assertEqual(vs.layout_for_vs((18, 10)), vs.OLD)
        self.assertEqual(vs.layout_for_vs((18, 0)), vs.OLD)
        self.assertEqual(vs.layout_for_vs(None), vs.NEW)

    @needs_sqlite
    def test_seed_decides_over_version(self):
        for lay in (vs.OLD, vs.NEW):
            p = os.path.join(self.d.name, "seed_" + lay + ".db")
            make_seed(p, lay)
            self.assertEqual(vs.seed_layout(p), lay)
            self.assertEqual(vs.pick_layout(p, (18, 0)), lay)
            self.assertEqual(vs.pick_layout(p, (18, 12)), lay)
        self.assertEqual(vs.pick_layout(os.path.join(self.d.name, "none.db"), (18, 10)), vs.OLD)
        self.assertEqual(vs.pick_layout(None, (18, 12)), vs.NEW)

    def test_unreadable_seed(self):
        p = os.path.join(self.d.name, "junk.db")
        with open(p, "wb") as f:
            f.write(b"not sqlite at all" * 100)
        self.assertIsNone(vs.seed_layout(p))
        self.assertEqual(vs.pick_layout(p, (18, 10)), vs.OLD)


@needs_sqlite
class NamedReading(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)

    def seed(self, layout):
        p = os.path.join(self.d.name, layout + ".db")
        make_seed(p, layout)
        return core.Ref(p)

    def test_template_args_by_name(self):
        """The reported crash: positional r[2] is nesting_level in the new layout, file_id in the old one."""
        new, old = self.seed(vs.NEW), self.seed(vs.OLD)
        n = new.rows("template_args", "file_id=1030")
        self.assertEqual(sorted(r["nesting_level"] for r in n), [0, 1])
        self.assertTrue(all(r["file_id"] == 1030 for r in n))
        self.assertEqual(new.q("select * from template_args")[0][2], 0)       # what the positional code saw: not a file id
        o = old.rows("template_args")
        self.assertEqual(o[0]["file_id"], 1030)
        self.assertNotIn("nesting_level", o[0])

    def test_rows_survive_permuted_columns(self):
        p = os.path.join(self.d.name, "perm.db")
        con = vs.create_browse_db(p, vs.NEW)
        con.execute("drop view symbol_refs_debug")        # views that name template_args columns are irrelevant for this test
        con.execute("drop table template_args")
        con.execute("create table template_args(args bigint, offset integer, file_id bigint, nesting_level integer, config_id bigint, symbol_id bigint)")
        con.execute("insert into template_args values(77,10,1030,0,1025,1)")
        con.execute("insert into shared_data(id,hash,value) values(6,0,'X')")
        con.commit(); con.close()
        r = core.Ref(p).rows("template_args")[0]
        self.assertEqual((r["symbol_id"], r["config_id"], r["file_id"], r["offset"], r["args"]), (1, 1025, 1030, 10, 77))

    def test_put_old_seed_row_into_new_layout(self):
        old = self.seed(vs.OLD)
        dest = os.path.join(self.d.name, "out.db")
        con = vs.create_browse_db(dest, vs.NEW)
        core.put(con, "template_args", old.rows("template_args")[0], default={"nesting_level": 0})
        self.assertEqual(con.execute("select symbol_id,config_id,nesting_level,file_id,offset,args from template_args").fetchall(),
                         [(1, 1025, 0, 1030, 10, 77)])

    def test_put_new_seed_row_into_old_layout(self):
        new = self.seed(vs.NEW)
        con = vs.create_browse_db(os.path.join(self.d.name, "out.db"), vs.OLD)
        core.put(con, "template_args", new.rows("template_args")[0])      # nesting_level has no column there: dropped
        self.assertEqual(con.execute("select symbol_id,file_id,args from template_args").fetchall(), [(1, 1030, 77)])

    def relations(self, seed_layout, out_layout):
        ref = self.seed(seed_layout)
        con = vs.create_browse_db(os.path.join(self.d.name, "o_%s_%s.db" % (seed_layout, out_layout)), out_layout)
        syms = {r["id"]: r for r in ref.rows("symbols")}
        core.copy_relations(con, ref, syms, ref.rows("symbol_refs"), {1030: 2000}, out_layout == vs.NEW)
        return con

    def test_relations_split_new_to_new(self):
        con = self.relations(vs.NEW, vs.NEW)
        self.assertEqual(con.execute("select * from symbol_rels_owned").fetchall(), [(1, 2, 1025, 0, 2000)])
        self.assertEqual(con.execute("select * from symbol_rels_free").fetchall(), [(1, 2, 1025, 4)])
        self.assertEqual(len(con.execute("select * from symbol_relations").fetchall()), 2)       # the view

    def test_relations_split_old_to_new(self):
        con = self.relations(vs.OLD, vs.NEW)
        self.assertEqual(con.execute("select * from symbol_rels_owned").fetchall(), [(1, 2, 1025, 0, 2000)])
        self.assertEqual(con.execute("select * from symbol_rels_free").fetchall(), [(1, 2, 1025, 4)])

    def test_relations_merge_new_to_old(self):
        con = self.relations(vs.NEW, vs.OLD)
        self.assertEqual(sorted(con.execute("select kind from symbol_relations").fetchall()), [(0,), (4,)])


class VenvAndSeed(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.root = self.d.name

    def fake_python(self, code):
        p = os.path.join(self.root, "venv", "bin")
        os.makedirs(p, exist_ok=True)
        f = os.path.join(p, "python")
        with open(f, "w") as fh:
            fh.write("#!/bin/sh\nexit %d\n" % code)
        os.chmod(f, os.stat(f).st_mode | stat.S_IXUSR)

    def test_no_venv(self):
        ok, why = vs.venv_status(self.root)
        self.assertFalse(ok)
        self.assertIn("no venv", why)
        self.assertNotIn("\n", why)

    def test_venv_without_libclang(self):
        self.fake_python(1)
        ok, why = vs.venv_status(self.root)
        self.assertFalse(ok)
        self.assertIn("libclang", why)

    def test_venv_with_libclang(self):
        self.fake_python(0)
        self.assertTrue(vs.venv_status(self.root)[0])

    def test_seed_status_and_problem(self):
        self.assertFalse(vs.seed_status(self.root)[0])
        self.assertIn("no venv", vs.generator_problem(self.root))
        self.fake_python(0)
        self.assertIn("no seed", vs.generator_problem(self.root))
        if have_fts5_delete():
            os.makedirs(os.path.join(self.root, "reference"))
            make_seed(vs.seed_path(self.root), vs.NEW)
            ok, why = vs.seed_status(self.root)
            self.assertTrue(ok)
            self.assertIn(vs.NEW, why)
            self.assertIsNone(vs.generator_problem(self.root))


if __name__ == "__main__":
    unittest.main()
