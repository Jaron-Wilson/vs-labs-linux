# IntelliSense AutoPCH (.ipch) format notes

Reference: LabDynamicMemory_WilsonJ_sol, VS 18 (2026), MSVC 14.51.36231, SDK 10.0.26100.0.
Files: `.vs/<sln>.slnx/v18/ipch/AutoPCH/<hash>/<STEM>.ipch` for MAIN, EMPLOYEE, VISIT, DATE
(94 to 134 MB each; 74% of every file is zero bytes; the four files are 70 MB of the 83 MB submission zip).

## 1. Directory name hash (solved, exact)

`dirname = '%x' % FNV1a_64( upper(windows_source_path).encode('utf-8') )`

- 64-bit FNV-1a (offset 0xcbf29ce484222325, prime 0x100000001b3), no terminator, no UTF-16.
- Input is the full Windows path of the .cpp, UPPERCASED, backslashes:
  `C:\USERS\JARON\SOURCE\REPOS\LABDYNAMICMEMORY_WILSONJ_SOL\LABDYNAMICMEMORY_WILSONJ\MAIN.CPP`.
- Printed as lowercase hex WITHOUT zero padding (that is why `bfebc658a38a61a` has 15 digits).
- Verified 4/4 (MAIN 4c19baa34752e78b, VISIT 6693d7871cfaf697, EMPLOYEE bfebc658a38a61a,
  DATE d5ea47fa35cf3222). Found by brute force over ~15 hash functions and ~14k input variants
  (work/hunt.py, work/run1.py).
- Consequence: the hash depends on where the project lived on the Windows machine. To match the
  teacher's machine style pass `--win-root C:\Users\<name>\source\repos`.

## 2. Which source gets an ipch, and the name

One AutoPCH per .cpp that the IDE parsed, named `<UPPERCASE STEM>.ipch` (Main.cpp -> MAIN.ipch). The
reference has 4 of 9 .cpp files: Visit, Main, Employee (the three open tabs in DocumentLayout.json)
plus Date (opened earlier). The generator uses the .cpp files named in `.vs/.../DocumentLayout.json`,
else all .cpp, or `--sources`.

## 3. File structure (offsets from DATE.ipch, other files shift by name/table sizes)

The file is a raw EDG front end (6.8) precompiled-header image: a small structured head followed by
a memory dump. Not compressed. Integers little endian.

| Offset | Content | Status in generator |
|---|---|---|
| 0x00 | ASCII `EDG C/C++ version 6.8 (Aug 27 2026 10:05:40)\n` | exact |
| 0x2d | NUL, then option records (below) | exact |
| ... | option records, see below | exact for Debug x64 |
| after options | include-name table | exact |
| after names | file table | exact if closure model hits, else approximate |
| after file table | `00000000 00000000 N1 N2 0000` then progression | N1/N2/progression approximate |
| ~0x4200 to end | EDG memory image (IL of the PCH prefix) | NOT generated (zeros) |

File size is always a multiple of 64 KiB (the image is mmapped in 64 KiB units).

### 3.1 Option records (0x2d to include-name table, about 0xbe8 bytes)
Each record: `[pad 8 zero][u32 1][u32 option id][u8 1][u32 len][string, NUL]`. Observed ids:
0x1c include dir (`...\MSVC\14.51.36231\include`, `atlmfc\include`, `Auxiliary\VS\include`, SDK ucrt, um,
shared, winrt, cppwinrt, `NETFXSDK\4.8\Include\um`), 0x21 -D macro (`_MSC_EXTENSIONS`, `_MSC_VER=1951`,
`_MSC_FULL_VER=195136257`, `_MSC_BUILD=0`, `_M_AMD64=100`, `_M_X64=100`, `_WIN64`, `_WIN32`,
`_EDG_COMPILER`, `_USE_DECLSPECS_FOR_SAL=1`, `_DEBUG`, `_CONSOLE`, `_UNICODE`, `UNICODE`, `_CPPUNWIND`,
`_MT`, `_DLL`, `_M_FP_PRECISE`), 0xbf lib dir (`...\lib\x64` list, 8 entries), a few numeric ones
(0x43/0x46/0x44/0x54 hold `1951`, `16`; 0x5a, 0x19, 0x1a, 0x53, 0x67, 0x4b, 0xc4, 0x79 `x64\Debug\\`),
0x98 `no_ms_nonreal_base_classes`, 0x102 the project dir again, 0x3a the AutoPCH dir itself.
Project specific strings (identical layout in all four files):
- `C:\Users\jaron\source\repos\<sln>\<proj>\\` (mixed case, TWO trailing backslashes), twice
- `C:\USERS\JARON\...\<PROJ>\` (uppercase, one trailing backslash) near the start
- `<sln dir>\.vs\<sln>.slnx\v18\ipch\AutoPCH\<hash>` (the file embeds its own directory)
- `x64\Debug\\`
The ids are copied as opaque literals from the reference; their meaning is only partly known.

### 3.2 Include-name table
Written as: `fe 00 00 00 | 01 00 00 00 | 16 zero bytes`, then per leading `#include` of the .cpp
(comments and blank lines skipped, block ends at first other line):
`[u32 2][u32 8][u32 len+1]["Name.h" or <name>, NUL][u32 source line number][u32 1]`.
After the last name the trailing `[u32 1]` is followed by `u32 0`, then the file table.
(The u32 after each name is the 1-based source line of that include: verified on all 4 files.)

### 3.3 File table
Every file read while building the prefix, in first-read order (a DFS of the include graph):
`[u32 len+1][path, NUL][u32 mtime][u32 0]`, terminated by `u32 0`.
- Project headers: path = UPPERCASED project dir + `\` + filename in original case; mtime = the
  file's st_mtime (unix seconds, low 32 bits). The generator reads the real mtime from disk. Nothing
  is invented.
- System headers: real path under VS/SDK; mtime = install time of that file on the reference machine
  (0x6aa2ff9f for MSVC include files, 0x69dfab9c or 0x69dfabb0 for ucrt). Copied from the
  reference table for known files; the MSVC value is used for unknown ones.
- 126 entries for DATE, 129 EMPLOYEE, 137 VISIT, 147 MAIN.

### 3.4 After the file table
`[u32 0][u32 0][u32 N1][u32 N2][u16 0]` then pairs `[u32 0x8401+4k][u32 4]` for k = 0..prog-1
(prog 59, 59, 76, 87 for DATE, VISIT, EMPLOYEE, MAIN), then irregular pairs and the memory image.
N1 = 500 (DATE, VISIT, EMPLOYEE) or 1000 (MAIN); N2 = 362, 412, 383, 510. Meaning unknown (EDG
internal table sizes); generator uses the reference values when the file count matches, otherwise a
linear guess.

## 4. What the generator does and how close it is

Check against the reference lab (generator run with the same Windows path and with the project
headers' mtimes set to the values stored in the reference ipch):
- Directory names: 4/4 identical to the reference.
- Header, option records, include-name table, file table, N1/N2 and the progression are byte
  identical to the reference for MAIN (0x4e44 bytes), EMPLOYEE (0x447f) and DATE (0x4217).
  For VISIT the file table model misses 3 STL files and misorders a few, so VISIT differs from offset
  0x42f5 on (it is the only one of four that is not exact in the structured head).
- Everything after that point (about 26% of every file, the EDG memory image, 30 to 40 MB of
  nonzero data per file) is not reproducible without the real EDG front end: the image holds absolute
  addresses and compiler-internal state, and only 75 of 22788 non-zero 4 KiB pages match between
  DATE and VISIT even though both contain the same `<string>` closure.
- The files are written sparse (holes), so on disk they cost almost nothing and zip to a few KB.
  Real ones deflate 84% (about 16 to 22 MB each). Use `--size-mb` for a smaller file.
- Byte-for-byte equality over the whole files at the same size is about 74% for each file, but that
  is the zero bytes agreeing with zero bytes; the genuinely informative part (the head, 17 to 20 KB per
  file) is 100% exact for 3 of 4 files. Do not claim more than that.

## 5. Approximate or unverified parts

- File size: exact only when the file-table length equals a reference one; otherwise interpolated
  by number of table entries, rounded to 64 KiB (VISIT comes out 104.8 MB vs 107.4 MB real).
- Std closure order for header sets not seen in the reference (any new std header) is a model:
  each reference table is cut at the top-level includes; closures are concatenated and de-duplicated.
  Unknown std headers get a single guessed path. Different include sets give a plausible set of
  files, maybe off by a few entries and some ordering.
- Release or x86 builds: the macro list is not known for them. `--config Release` only swaps
  `_DEBUG` for `NDEBUG`; x86 is not modelled. Treat as approximate.
- System header mtimes are those from the reference machine's installation; a different VS patch
  level would have different values (they are install times, not related to the student's files).
- The `.ipch` of a header-only open file, or a .cpp that starts with code before the includes, was
  not observed.
