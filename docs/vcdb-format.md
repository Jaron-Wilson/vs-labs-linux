# Browse.VC.db and Solution.VC.db (VS 18 C++ IntelliSense databases)

Files: `.vs/<sln>.slnx/v18/Browse.VC.db` and `Solution.VC.db`. Both are SQLite 3 files in WAL mode,
UTF-8, user_version 0, application_id 0, auto_vacuum 0. Page size: Browse 8192, Solution 4096.
Reference: `reference/LabDynamicMemory_WilsonJ_sol/.vs/LabDynamicMemory_WilsonJ_sol.slnx/v18/`.
VS rewrites or validates both on open (it compares file timestamps), so a mismatch costs a reparse, not an error.

Tools in this folder:

- `gen_vcdb.py` builds both DBs for a project (needs `python3 -m venv .venv && .venv/bin/pip install libclang`; `gcc` is used to find the builtin clang headers).
- `validate.py` compares a generated Browse.VC.db against the reference (output saved in `validation.txt`).
- `Browse.schema.sql`, `Solution.schema.sql`: DDL dumped verbatim from the reference `sqlite_master` (tables, indexes, views, FTS5 virtual tables), statements separated by `\n;;\n`. `gen_vcdb.py` executes them as is, so the schema is byte identical (checked: `sqlite_master` rows equal for both DBs).

Example:

    .venv/bin/python gen_vcdb.py --project-dir /path/Sol/Proj --win-root 'C:\Users\Student\source\repos\Sol' \
        --out-dir /path/Sol/.vs/Sol.slnx/v18

`--win-root` is the Windows path of the solution folder on the machine that will open the lab. Runtime on the reference lab: about 15 s.

## Solution.VC.db

85 schema objects (project, config, item_type, project_item_file, filter, config_property, command_line, reference, ... tables plus `property`).
In the reference every table is empty except `property`, which has two rows:
`version = 18.0001` and `path = <UPPERCASE Windows path of Solution.VC.db>`. The file is 434176 bytes only because of the empty schema.
`gen_vcdb.py` reproduces this exactly (same size, 434176).

## Browse.VC.db: tables

Paths are stored upper cased and with backslashes (case insensitive key), for example
`C:\PROGRAM FILES\MICROSOFT VISUAL STUDIO\18\COMMUNITY\VC\TOOLS\MSVC\14.51.36231\INCLUDE\STRING`. Only `properties.path` and the
config option strings keep real case.

| Table | Meaning |
|---|---|
| properties | 12 key/value rows: `version 18.0017`, `client_version 18.0`, `path` (real case), `symbols_version 1.40`, `code_items_cnt`, `code_items_mod`, flags |
| parsers, code_item_kinds | fixed: C/C++, IDL, Metadata, null parsers; 64 item kinds (1 class, 2 struct, 4 enum, 6 member_function, 7 member, 8 enumerator, 9 parameter, 10 template, 12 template_type_parameter, 17 base_class, 21 typedef, 27 function, 28 variable, 37 macro_define, 39 pound_include, 53 scope ...) |
| projects, configs | 1 project (id 1025; name = UPPERCASE .vcxproj path, directory, GUID without braces) and its config `Debug|x64` (id 1025). Config columns are ids into `shared_data` (include path, options, ...) |
| files | every file: id, `timestamp` (file mtime, unix seconds), `parsetime/addtime/difftime` (seconds spent by VS parsing, adding, diffing), upper cased path, leaf, extension, `attributes` (64 = not parsed, e.g. .txt/.filters; 16 module interface; 2 managed), parser guid |
| config_files | file x config: `attributes` (4 compiled .cpp, 0 project header, 1 implicit system header, 524 library module), `parse_timestamp` |
| code_items | syntactic outline of each parsed file, one row per declaration/include/macro. Tree via `parent_id` (1024 = file scope root). 1-based line and column, end column inclusive. `attributes` is a bit set (see below). `type` uses `\x01` as name placeholder and `\x02` as parameter list placeholder (`float \x01\x02`) and the type text as written (`vector<Patient>& \x01`, otherwise normalized `const char * \x01`). `lower_name_hint` = first 4 chars lower case |
| assoc_text, assoc_spans | kind 1 text: macro bodies (system), kind 2 text: default initializers (`= nullptr`, enumerator `= 1`). spans kind 1: qualifier range of out of class member definitions (`Nurse::`) |
| file_map | pound_include item -> file it resolved to (config scoped). This is the include graph |
| base_class_parents | base_class item (kind 17) -> derived class item |
| file_tu_map | (header, translation unit .cpp, config): which headers each TU really pulled in |
| shared_data | dedup store for long values: config strings and symbol reference lists. `hash` = signed 64 bit FNV-1a of the value bytes (verified on all sampled rows). Reference lists are SQLite JSONB blobs (`jsonb('[[kind,offset,length,attrs],...]')`) |
| symbols | semantic symbols (IntelliSense engine): `moniker_hash` (algorithm unknown), name, kind (= code item kind), `semantic_token_kind`, `symbol_kind`, `flags` (1 = local variable or parameter). `declaration` is always NULL for C++ |
| symbol_refs | (symbol, file, config) -> `decl_defn_refs` and `usage_refs` ids in shared_data. Each entry `[kind, byte offset, length, attrs]`. kind bits: 1 declaration, 2 definition, 4 reference, 8 read use, 16 modification, 2048 initialization (so 3 decl+def, 12 read, 20 write, 28 read+write, 2052 init in member init list). attrs bits: 4 destructor, 16 implicit instantiation, 32 parent is class template, 48 member of template instantiation, 64 secondary position |
| symbol_relations | kind 0 derived_of, 1 base_override_of, 2 override_of, 3 direct_override_of, 4 overload_of, 5 instantiation_of, 6 special_function_of, 7 injected_of, 8 specialization_of |
| template_args, symbol_definition_ranges | template argument strings per symbol use; ranges table is empty in the reference |
| hint_files | `cpp.hint` from the VS install |
| project_refs | empty here |
| code_items_fts, identifiers_fts (+ _data/_idx/_docsize/_config) | contentless FTS5 indexes, rowid = file id. `code_items_fts` uses the trigram tokenizer over item names, `identifiers_fts` unicode61 over identifiers |
| views | `configs_ex`, `config_files_debug`, `symbols_debug`, `symbol_refs_debug`, ... decode the bit sets (copied with the DDL) |

code_items attribute bits seen: 1 declared, 2 defined, 4 public, 8 protected, 16 private, 0x20 `virtual` written,
0x200 default constructor `= default` in class, 0x800 template, 0x10000 friend, 0x40000 const method, 0x80000 scoped enum,
0x1000000 operator, 0x4000000 `= default`, 0x8000000 `= delete`, 0x10000000 override. Include items: 2 quoted,
0x40002 angle (system). Class/enum/macro: 3.

### Project rows versus system header rows

For the reference lab: 193 files = 25 project files (ids 1027..1051, under `C:\USERS\...`), 2 module files
(`MODULES\STD.IXX`, `STD.COMPAT.IXX`, ids 1025/1026), 129 MSVC STL / VC include files and 39 Windows SDK UCRT files.
`code_items`: 741 rows from project files, 117,498 total, so more than 99 percent of rows are system header outline
(MSVC 14.51.36231 STL and Windows Kits 10.0.26100.0 ucrt). Symbols: ids below 43987 come from system headers, 43987 and up were
created while parsing the project TUs (project symbols, template instantiations, locals). File ids and timestamps of system
files (1789067167 = install time of that VS on the source machine) are real values from that install.

## What gen_vcdb.py does

1. Reads the `.vcxproj` (files, GUID, `PreprocessorDefinitions`, `LanguageStandard`).
2. Parses every `.cpp` with libclang (`-std=` from the project, `-D` from the project, project dir as `-I`) using Linux libstdc++ headers, walks only cursors located in project files and emits code items, symbols and references in the VS layout.
3. Resolves each include: quoted ones to project files, angle ones to the reference's system files (searching the reference include path list), then takes the transitive closure over the reference `file_map` graph. For those system files it copies from the reference: `files`, `config_files`, `code_items` (same ids), `assoc_*`, `file_map`, `base_class_parents`, `symbols`, `symbol_refs`, `symbol_relations`, `template_args` and the referenced `shared_data` rows. File ids are renumbered because project file ids come first.
4. Maps libclang references to system symbols (for example `std::string`) onto reference symbol ids by (name, kind), choosing the candidate the reference project itself used most. Project symbols get new ids.
5. Writes `files.timestamp` and `config_files.parse_timestamp` of project files from the real mtime of the file on disk, `parsetime` from the measured libclang parse time. Nothing is invented: system file times come from the real install the reference was taken from.

## What matches the reference row for row (reference lab regenerated from its own sources)

Measured with `validate.py` (see `validation.txt`):

| Item | Result |
|---|---|
| Schema (all tables, indexes, views, FTS definitions), pragmas | identical |
| Solution.VC.db | identical content and size |
| files, config_files, code_item_kinds, parsers, projects, hint_files, properties (12 rows), configs (1 row) | same row counts; file names 193/193 identical |
| code_items total | 117,498 = 117,498 |
| System header code_items (84,717) | 100.0 percent identical (copied) |
| Project code_items (741) | 741/741 same (file, kind, name, line, column); end position 100 percent, attributes 100 percent, type 100 percent, name columns 100 percent, default values 99.7 percent |
| assoc_text, base_class_parents, code_items_fts rows | 11084 = 11084, 968 = 968, 183 = 183 |
| shared_data hash column | same algorithm, rows byte identical for copied rows |
| Symbols referenced from project files (name, kind, symbol_kind) | 96.0 percent of reference present, 99.0 percent of ours exist in reference |
| Project symbol reference occurrences (file, offset, name) | 98.3 percent of reference found, 99.2 percent of ours correct |
| decl/def reference entries including kind flags | 94.3 percent; usage entries 94.4 percent |
| file_tu_map | all 1165 reference pairs present, 12 extra |

## What is approximate

- `symbols.moniker_hash`, `configs.hash`: VS algorithm not recovered (FNV-1a of plain names did not match). Ours are stable unique FNV-1a values of our own key strings; VS treats them as opaque ids. Project symbol ids differ from VS and symbol rows for system headers copied from the reference keep their original ids.
- `properties.code_items_mod` is set equal to `code_items_cnt` (VS keeps a larger running modification counter).
- Reference kind details guessed from libclang: read/write classification of variable uses (class typed locals sometimes 12 in VS and 4 here), `Employee` injected class name typedef versus class, implicit constructor calls (attr 8 entries), `operator new/delete`, `[]` with attr 112, template type parameter uses inside out of class template member definitions, prototype instantiation refs (8196). These account for the missing 1.7 percent of occurrences.
- Class template members: `template_items` are parsed from tokens; pure virtual (`= 0`), `static` members, `using` aliases in classes and `#pragma once` rows use guessed attribute bits (no sample in the reference lab).
- FTS5 content (`code_items_fts`, `identifiers_fts`): VS tokenization input is not recoverable from a contentless index. Row set matches (183 and 185) but the indexed text is ours (item names, identifiers). Page level tables (`*_data`, `*_idx`) therefore differ in size.
- `parsetime`, `addtime` are our own measured seconds, not VS's.
- Only system headers present in the reference can be mapped. Includes missing from it (for example `<map>`, `<fstream>` if the reference did not use them) get no system rows; the generator prints them. Cure: add a second reference lab that includes those headers or merge several references (not done).
- Windows paths of project files are built from `--win-root`; if the lab is opened from another folder VS drops and rebuilds the DBs.
- Symbol and reference rows exist only for project files plus the system symbols used by the reference; system symbols the new project uses but the reference never touched are skipped.
- symbol_relations: only the system relation rows copied from the reference; no derived_of/override rows are written for project classes yet (reference has about 25 for the lab).
- Everything assumes MSVC 14.51.36231 and Windows SDK 10.0.26100.0; config option strings copy the reference with `/D`, `/std:` and `/BCD` path substituted.
