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

## Clean build comparison with the real Visual Studio MSBuild (round 3, fresh install with untouched headers)

A copy of the lab was built once, from scratch, on the PC with the real Visual Studio 18 MSBuild (`winpc build`), and the same copy on Linux with
`VSLAB_WINREPOS` set to the same Windows folder so that every path is the same. The PC is on VS 18.10.0 (compiler 19.51.36257); the Linux install is
the installer channel's current build (compiler 19.51.36263).

| Configuration | tlog files identical | Only difference |
| --- | --- | --- |
| Debug x64 | 8 of 9 | `.lastbuildstate` (compiler servicing number) |
| Release x64, Debug Win32, Release Win32 | 8 of 9 each | same (measured in round 2) |

Headers: all 139 MSVC and SDK header files the lab reads are now byte-identical to the PC's (SHA-256 checked), after the reinstall without msvc-wine's fix-up step.
(Before: 104 of 105 only after `vslab repair-headers`.)

`.exe` Debug x64: identical section table and size, `.text`, `.rdata` and `.pdata` data identical; 432 differing bytes, all in the DOS/Rich header (compiler build
number), the build timestamp, the PDB GUID, and 11 import-hint bytes (the SDK import libraries of the two installs are different refreshes).
`.obj` (all nine): same size, and `.text`, `.xdata`, `.pdata`, `.rdata` identical. What differs: the timestamp, a 16 byte type stream signature (this changes on every build, also between two Linux builds
of the same file) and the debug symbol sections: in `Main.obj` 609 of 856 `.debug$S` sections differ by about one byte each, and each of those bytes is a CodeView type index that is 4 lower in the
Linux build than in the Windows one, the signature of a small change in the compiler's type numbering between the two compiler builds. The `.chks64` checksums of those sections differ because
their content differs. The headers are not the reason (they are identical), so the remaining `.obj`, `.pdb`, `.ilk` and `.idb` differences are attributable to the compiler build number. Once the PC runs the
same compiler (it was asked to update), the clean build comparison should be re-run.

## Reference zip check, round 3

summary: 51 identical, 29 same-format, 0 different-format, 0 missing, 0 extra (of 80 reference files), same as round 2 (the `.suo` and the other IDE state were not touched by the header change).

Known remaining gaps: exact servicing build of the compiler and SDK libraries (the installer channel serves the newest one), the memory image of `.ipch`, rows of Microsoft header symbols in
`Browse.VC.db` without a seed, the IDE's own state in `.suo`. MSBuild itself does not run (no .NET in Wine). The real IntelliSense engine route is analysed in `intellisense-engine.md` and needs
the owner's license step before anything can be tried.
