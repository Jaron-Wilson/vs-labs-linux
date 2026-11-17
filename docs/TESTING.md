# End to end test on a real lab (2026-11-17)

Lab: LabDynamicMemory_WilsonJ_sol (VS 18 Community, toolset v145, MSVC 14.51.36231, SDK 10.0.26100.0, x64 Debug).
Host: Ubuntu 24.04, user-space Wine 9.0, MSVC 14.51.36231 + SDK 10.0.26100.0 from Microsoft via msvc-wine.
Build: `vslab build` (cl/link under Wine, same switches as the real tlogs), 13 s.

## Program output

Same input script (`7`, Enter, `6`, Enter, `9`, Enter) fed to the Visual Studio built exe on Windows and to the Wine built exe on Linux, working
folder = project folder, stdout redirected to a file: 4942 bytes (Windows) vs 4936 bytes (Linux). The only difference is 6 form feed
bytes (0x0c): the program calls `cls`, which Windows writes as a form feed into a redirected stream and Wine's cmd does not. On a terminal
both clear the screen.

## `vslab check` against the real zip (83 MB, 99 entries)

| Result | Count | Files |
| --- | --- | --- |
| Identical (byte for byte) | 35 | all source, data, .slnx, .vcxproj, .filters, .user, `*.log`, `.exe.recipe`, `link.command.1.tlog`, `link.write.1.tlog`, `Cl.items.tlog`, `link.secondary.1.tlog`, DocumentLayout (before the layout generator was added; it is generated from the same inputs now) |
| Same format, different bytes | 24 | 9 `.obj` (same sizes as the Visual Studio ones), `.exe` (1,161,728 vs 1,162,240 B), 2 `.pdb`, `.ilk`, `vc145.pdb`, `vc145.idb`, `CL.command.1.tlog` (same size, history differs), `CL.read`, `CL.write`, `link.read`, `.lastbuildstate` (same size; the installed compiler servicing number is 36263 here, 36257 on the PC), Browse.VC.db and Solution.VC.db (same schema, no rows / different rows), MAIN.ipch (same size, head exact, body zeros), DocumentLayout when different tabs are open |
| Different format | 0 after the .suo generator (was 1: empty .suo) | |
| Missing | 23 | VISIT/EMPLOYEE/DATE `.ipch` (only the file open in the editor gets one), `*.dt.*.json` and `*.command` files (Visual Studio IDE IntelliSense scans, not build output), `WilsonJaronLab.docx` (the student's own file in the reference zip, not in the test copy), the empty `_MD.tlog` and `microsoft/STL` folders are created by the build |
| Extra | 1 | the `.vsidx` has a different random GUID name (as it is in Visual Studio) |
| Zip metadata | same | create system 3, modes 0666/0777, flags 8, UT + ux extra fields |

Known gaps: the incremental history of the reference build (its tlogs record five compile passes) cannot be reproduced by a clean build;
MSBuild itself does not run (needs .NET in the Wine prefix).
