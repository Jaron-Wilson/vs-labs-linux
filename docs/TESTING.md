# End to end test on a real lab (2026-11-17)

Lab: LabDynamicMemory_WilsonJ_sol (VS 18 Community, toolset v145, MSVC 14.51.36231, SDK 10.0.26100.0, x64 Debug).
Host: Ubuntu 24.04, user-space Wine 9.0, MSVC 14.51.36231 + SDK 10.0.26100.0 from Microsoft via msvc-wine.
Build: `vslab build` (cl/link under Wine, same switches as the real tlogs), 13 s.

## Program output

Same input script (`7`, Enter, `6`, Enter, `9`, Enter) fed to the Visual Studio built exe on Windows and to the Wine built exe on Linux, working
folder = project folder, stdout redirected to a file: 4942 bytes (Windows) vs 4936 bytes (Linux). The only difference is 6 form feed
bytes (0x0c): the program calls `cls`, which Windows writes as a form feed into a redirected stream and Wine's cmd does not. On a terminal
both clear the screen.

## `vslab check` against the real zip (83 MB, 99 entries), all generators on

summary: 35 identical, 25 same-format, 0 different-format, 23 missing, 1 extra (of 83 reference files). Zip metadata identical.

| Result | Count | Files |
| --- | --- | --- |
| Identical (byte for byte) | 35 | sources and data files, `.slnx`, `.vcxproj`, `.filters`, `.user`, `<project>.log`, `.exe.recipe`, `link.command`, `link.write`, `Cl.items`, `link.secondary` tlogs, `.dt.*` is not among them (see missing) |
| Same format, different bytes | 25 | `.suo` (valid OLE file, 33,792 vs 40,448 B), `Browse.VC.db` (same schema, project symbols from libclang, 22,806,528 vs 22,773,760 B), `Solution.VC.db` (same size, differs only in content that depends on paths and WAL state), both DocumentLayout files (we list every .cpp as open, the real one 3 tabs), `MAIN.ipch` (same size, exact head), 9 `.obj`, `.exe` (1,161,728 vs 1,162,240 B), 2 `.pdb`, `.ilk`, `vc145.pdb`, `vc145.idb`, `CL.command` (same size), `CL.read`, `CL.write`, `link.read`, `.lastbuildstate` (compiler servicing number 36263 here, 36257 on the PC) |
| Different format | 0 | |
| Missing | 23 | 3 `.ipch` (only files open in the editor get one), 15 IDE IntelliSense scan files `*.dt.*` (not build output, not generated), `.vsidx` name (random GUID, ours differs), `WilsonJaronLab.docx` (the student's own document) and 3 empty folders |
| Extra | 1 | the `.vsidx` under its own random GUID |

Browse.VC.db needs a "seed" (a Browse.VC.db written by a real Visual Studio, `vslab seed REAL.zip`) for the rows of Microsoft's own headers; without it the
file has the exact schema but no rows. Headers that are not in the seed get no rows (`<map>` was missing in one test).
Known gaps: the incremental history of the reference build (its tlogs record five compile passes) cannot be reproduced by a clean build;
MSBuild itself does not run (needs .NET in the Wine prefix).
