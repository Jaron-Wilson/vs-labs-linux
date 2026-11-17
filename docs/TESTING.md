# End to end test on a real lab (2026-11-17)

Lab: LabDynamicMemory_WilsonJ_sol (VS 18 Community, toolset v145, MSVC 14.51.36231, SDK 10.0.26100.0, x64 Debug).
Host: Ubuntu 24.04, user-space Wine 9.0, MSVC 14.51.36231 + SDK 10.0.26100.0 from Microsoft via msvc-wine.
Build: `vslab build` (cl/link under Wine, same switches as the real tlogs), 13 s.

## Program output

Same input script (`7`, Enter, `6`, Enter, `9`, Enter) fed to the Visual Studio built exe on Windows and to the Wine built exe on Linux, working
folder = project folder, stdout redirected to a file: 4942 bytes (Windows) vs 4936 bytes (Linux). The only difference is 6 form feed
bytes (0x0c): the program calls `cls`, which Windows writes as a form feed into a redirected stream and Wine's cmd does not. On a terminal
both clear the screen.

## `vslab check` against the real zip (83 MB, 99 entries), all generators on, round 2 (2026-11-17)

summary: 51 identical, 29 same-format, 0 different-format, 0 missing, 0 extra (of 80 reference files). Zip metadata identical.
The file set is now complete: every file, including the 15 IDE scan files and all four `.ipch`, exists in the Linux made zip.

| Result | Count | Files |
| --- | --- | --- |
| Identical (byte for byte) | 51 | sources and data, `.slnx`, `.vcxproj`, `.filters`, `.user`, `<project>.log`, `.exe.recipe`, `link.command`, `link.write`, `link.secondary`, `Cl.items` tlogs, all 15 `*.dt.*` scan files |
| Same format, different bytes | 29 | `.exe`, 9 `.obj`, 2 `.pdb`, `.ilk`, `vc145.pdb`, `vc145.idb` (toolchain revision, timestamps, GUIDs), `CL.command`, `CL.read`, `CL.write`, `link.read` tlogs (the reference's tlogs record five incremental compile passes; a clean build has one), `.lastbuildstate` (compiler servicing 36263 vs 36257), `.suo` (valid OLE file, 22,016 vs 40,448 B), both DocumentLayout files (same size, same structure, different `WhenOpened` times and view state), `Browse.VC.db` (same schema, project symbols from libclang), `Solution.VC.db` (same size), 4 `.ipch` (same sizes, exact head, memory image is zeros), the `.vsidx` (random GUID name, same size) |
| Different format | 0 | |
| Missing / Extra | 0 / 0 | |

## Clean build comparison with the real Visual Studio MSBuild (same lab, same Windows path)

The reference zip's tlogs reflect a lab that was built many times, so a second reference was made: a copy of the lab built once, from scratch,
on the PC with the real Visual Studio 18 MSBuild (`winpc build`, also `MSBuild /p:Platform=x86` and Release), and the same copy built on Linux with
`VSLAB_WINREPOS` set to the same Windows folder so that every path in the files is the same.

| Configuration | tlog files identical | Only difference |
| --- | --- | --- |
| Debug x64 | 8 of 9 | `.lastbuildstate` (compiler servicing number) |
| Release x64 | 8 of 9 | same |
| Debug Win32 | 8 of 9 | same |
| Release Win32 | 8 of 9 | same |

`.exe` Debug x64: identical section table and size; 432 differing bytes, all in the DOS/Rich header (compiler build number), the build
timestamp and PDB GUID/path, and 11 import hint bytes (the SDK import libraries of the two installs are different refreshes: `kernel32.lib` has
the same size but a different hash). `.obj`: same size, 70 differing bytes in `Aide.obj` (timestamp, `.debug$T` signature, compiler stamp, checksums of one
header); `Main.obj` differs in `.chks64` too because the SDK headers of the Linux install were rewritten by msvc-wine's fix-up step (see README, "Toolchain
revision"). Every other MSVC header read by the lab matches the PC's byte for byte once CRLF line ends are restored (`vslab repair-headers`, 104 of 105
checked files; the other, `sal.h`, had one lower-cased `#include`).

Known remaining gaps: exact servicing build of the compiler and SDK (the installer channel serves the newest one), the lower-cased `#include` lines in an
install made before `install.sh` stopped running the fix-up step, the memory image of `.ipch`, rows of Microsoft header symbols in `Browse.VC.db` without a
seed, the IDE's own state in `.suo`. MSBuild itself does not run (no .NET in Wine).
