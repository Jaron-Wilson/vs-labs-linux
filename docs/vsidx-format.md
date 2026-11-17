# .vsidx (FileContentIndex) notes

Location: `.vs/<sln>.slnx/FileContentIndex/<guid>.vsidx`. Samples decoded: the
reference lab (53543 bytes, 24 files) and a second VS 18 lab (48057 bytes, 22 files).
All integers are little endian.

## Layout

| Offset | Size | Meaning |
|---|---|---|
| 0 | 4 | magic `43 44 47 12` ("CDG", 0x12) |
| 4 | 3 | zero |
| 7 | 8 | u64 offset of the footer (file size - 36) |
| 15 | 8+L0 | section 0, file table (u64 length L0, then payload) |
| s1 | 8+L1 | section 1, posting items |
| s2 | 8+L2 | section 2, per-trigram (start,count) ranges |
| s3 | 8+L3 | section 3, sorted trigram dictionary |
| s3+8+L3 | 8 | zero (8 bytes) |
| footer | 36 | u32 `4`, then 4 x u64 section offsets `15, s1, s2, s3` |

Section payloads:

- Section 0: u32 R (record size = longest Windows path length + 8; 108 in the reference),
  then one R-byte record per file: path as ASCII (`C:\Users\<user>\source\repos\<sln folder>\<proj>\<file>`),
  NUL padded to R-8 bytes, then u64 FILETIME (100 ns since 1601, UTC) of the file's last write time.
  Rows are sorted by path, ordinal ignore case (`Aide.cpp, Aide.h, aides.txt, CaseManager.cpp, ...`).
  Reference: s1 = 2619 = 15+8+4+24*108.
- Section 1: u32 `3` (item size), then 3-byte items `(file row u8, 0x00, line mask u8)`.
  Reference: 7345 items.
- Section 2: u32 `8` (entry size), then one `(start u32, count u32)` per trigram: slice of
  section 1 items (start counts items, not bytes).
- Section 3: u32 `3` (key size), then trigrams in ascending byte order, 3 ASCII bytes each.
  Reference: 2619 trigrams.

## What is indexed (decoded and verified)

- Files: the project items of the .vcxproj (ClCompile, ClInclude, Text in the labs). Files in the
  folder but not in the project (JaronWilson.txt, .vcxproj, .filters, .user, build output) are absent.
- Text: split on whitespace (`\s+`), upper-cased, every 3-gram inside a token (tokens shorter than 3
  produce nothing; punctuation is part of the trigram, e.g. `!(I`, `");`, `W(1`). Trigrams never
  span whitespace or lines.
- Line mask (3rd item byte): bit `k` set for every occurrence on a line whose index k is
  `(number of non-empty lines before it) mod 8`. A line is empty only if it has length 0 after
  splitting on `\n`; in CRLF files the lone `\r` makes a blank line count as non-empty (confirmed on
  Date.cpp and Date.h). Items of one trigram are merged per file (one item per file).
- 2nd item byte (would be a next-char mask) is always 0 in 7345+ items.

## GUID file name

Random v4 GUID (`7230b51b-f61d-4ef6-bbe8-...`, `815a19e0-87ca-4819-8e44-...`; version and variant
bits are valid v4). I searched every file of the reference lab (including .suo, Solution.VC.db,
DocumentLayout.json, in raw, little endian, text and UTF-16 forms): the GUID is not stored anywhere
else. The generator uses `uuid.uuid4()` unless `--guid` is given.

## Exact vs approximate

Exact (regenerating the reference lab with its recorded timestamps: header, file table, range table,
dictionary are byte identical; all 7345 items agree as a set per trigram):

- magic, header, footer, section framing, record size rule, path format, dictionary, ranges,
  trigram and mask rules.

Approximate:

- Order of files inside each trigram's posting list. VS lists files in indexing order, not row order.
  Ascending last-write time reproduces 97% of multi-file lists on the second sample (a fresh index)
  but only 46% on the reference (index updated incrementally while the student edited; the order is
  not even a consistent total order there). Section 1 therefore differs in order only; sizes and all
  other sections are unaffected.
- Which item types are indexed beyond ClCompile/ClInclude/Text (guess: ResourceCompile, None, Midl,
  CustomBuild, Xml, Image, Manifest).
- Non-ASCII text (not present in samples): trigrams containing non-ASCII are dropped; real VS
  behaviour unknown. Item byte for file row is assumed u8 (more than 256 files untested).
- Sorting of exotic file names (ordinal ignore-case assumed).
- Timestamps come from `st_mtime_ns` of the files on disk (no faking); they will naturally differ
  from the reference.

## Validation

`python3 gen_vsidx.py <sol dir> --user jaron --mtimes-from <real .vsidx> --out /tmp/x.vsidx`
(`--mtimes-from` is for validation only) then `python3 compare.py /tmp/x.vsidx <real .vsidx>`:

- reference lab: same size 53543, 89.78% bytes equal at the same offset; header+files, ranges and
  dictionary identical; only posting order differs.
- second lab (/tmp/opencode/labinherit, 22 files): same size 48057, 99.77% bytes equal.
