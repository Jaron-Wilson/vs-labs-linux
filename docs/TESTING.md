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
`Browse.VC.db` without a seed, the IDE's own state in `.suo`. MSBuild itself does not run (no .NET in Wine). The real IntelliSense engine route was investigated and is a dead end for now (see `intellisense-engine.md`).

## Round 4: after the PC moved to Visual Studio 18.12 (2026-11-17)

The PC now reports VS 18.12.0. Its C++ toolset folders are 14.44.35207 and 14.52.37025 (compiler 19.52.37029); 14.51 is gone.
A clean MSBuild of a scratch copy of the lab on the PC (all four configurations) shows `VCToolsVersion=14.52.37025`,
`VCServicingVersion{ATL,CrtHeaders,Compilers}=14.52.37029`, SDK 10.0.26100.0, and every `CL.read` path under `...\MSVC\14.52.37025\`.
So VS 18.12 builds with 14.52, not 14.51.

The server has the full 14.51.36231 toolset only. Its `14.52.37025` folder is a stub (crt, lib and Auxiliary, 348 KB, no `bin` and no `include`), so there is no 14.52 compiler to
run yet. Getting it needs the Microsoft license step, which only the owner runs: `install.sh --msvc-version 14.52` (it asks for the yes again). Because of that, the exe/obj/pdb byte comparison with the same compiler on both sides was NOT redone.
Same-input comparison against the new PC build using the 14.51 toolset (tlog paths normalised from 14.51 to 14.52 for the comparison only):

| Configuration | tlog files identical (of 9) | Differences |
| --- | --- | --- |
| Debug x64 | 7 | `CL.read` (position of `<cctype>`/`ctype.h` in the include order, a 14.52 header change), `.lastbuildstate` (toolset and servicing numbers) |
| Release x64 | 7 | same |
| Debug x86 | 7 | same |
| Release x86 | 6 | same, plus `link.read`: see below |

New in 18.12 and now reproduced: `CL.write` lists the `.obj` files with a `\\?\` prefix (18.10 did not). vslab emits it when the 14.52 toolset (or `VSLAB_VS=18.12`) is selected; verified, `CL.write` is then identical.
The `link.read` difference on Release x86 is build session state, not a format change: the first link after no `mspdbsrv.exe` is running records it, later ones in the same session do not (measured twice on the PC: 1 line, then 0).
The vslab output corresponds to the fresh start, which is what a first build in a new session produces.

`.exe` sizes, PC 14.52 vs Linux 14.51 (different compilers, so only a sanity check): Debug x64 1,276,416 vs 1,161,728; Release x64 125,952 vs 136,192; Debug x86 927,744 vs 858,112; Release x86 125,952 vs 125,440.

`vslab check` of the Linux zip against the real reference zip (made by VS 18.10) is unchanged: 51 identical, 29 same-format, 0 different-format, 0 missing, 0 extra (80 reference files).
That reference was written by 18.10, so its tlogs correctly keep the 18.10 style (no `\\?\`); vslab with the default 14.51 fallback reproduces it. Note that the 15 IDE `*.dt.*` files and four `.ipch` files appear
only when the same files are open as in the reference (`vslab tabs open Date.cpp Date.h Employee.cpp Visit.cpp`); with only the default tab the check reports them missing.

Still to do after the 14.52 toolset is installed: re-run the PC against Linux comparison of `.exe`, `.obj`, `.pdb`, `.ilk` and the tlogs (expect `.lastbuildstate` and `CL.read` to match, and the `.obj` code and debug sections to match).

## Round 5: same compiler on both sides (toolset 14.52.37025, VS 18.12 on the PC) (2026-11-17)

Setup: the PC built a scratch copy of the lab (`C:\Users\jaron\opencode-work\r4`) with the real MSBuild of VS 18.12, all four configurations, plus a
second Debug x64 build to measure how much the PC differs from itself. Linux built the same sources with `vslab` (14.52.37025, full compiler now installed), with
`VSLAB_WINREPOS` set to the same Windows folder so every path in every record is the same. 141 of 141 headers read by the compiler are SHA-256 identical to the PC's.

### What the comparison found and fixed

The first comparison showed the `.obj` files differing in thousands of bytes (every `.debug$S` section had a type or string index 4 off), which in the previous
round I had blamed on the compiler build. It was not: the compiler stores its own command line, the include lists and the tool path in the build info of every `.obj`/`.pdb`
(an `S_BUILDINFO` record whose strings live in the PDB), and vslab ran cl differently from MSBuild. Now vslab runs the real compile exactly as MSBuild does:
same switch order (`... /FC /errorReport:queue`), project-relative source names, no extra switches (the old `/showIncludes` was moved to a separate compile-less
`/Zs` pass that only feeds `CL.read`), the same `INCLUDE` and `EXTERNAL_INCLUDE` lists (9 folders, in VS's order, including the `NETFXSDK` and `Auxiliary\VS\include` entries), and the tool path
spelled `...\bin\HostX64\x64\CL.exe` (Wine reports a program's path in its on-disk case, so `vslab` adds two symlinks inside the toolset, `HostX64` and `CL.exe`; no file is copied or changed).
Result: IPI stream of `vc145.pdb` byte-identical to the PC's, the project `.pdb` the same size, every x64 `.obj` identical except 20 to 26 bytes.

### Results against the PC's VS 18.12 build

| Item | Debug x64 | Release x64 | Debug x86 | Release x86 |
| --- | --- | --- | --- | --- |
| tlog files identical (of 9, incl. `.lastbuildstate`) | 9 | 9 | 9 | 7 (note 1) |
| `.exe.recipe` | identical | identical | identical | identical |
| `.obj` (9 files) | same size, 26 B differ | same size, 20 B differ | same size, 133 to 5,573 B differ (note 2) | same size, 22 B differ |
| `.exe` | same size, 22 B differ | same size, 25 B differ | same size, 20,477 B differ (note 2) | same size, 26 B differ |
| `vc145.pdb` | same size, 1,858 B differ (note 3) | same size, 1,737 B | same size, 1,858 B | same size, 1,701 B |
| project `.pdb` | same size, 3.0 MB differ | same size | size differs (note 2) | size differs |
| `.ilk` | 88 B smaller (note 3) | none | 665 KB smaller | none |

The PC against itself (two clean builds of the same project, same path, same session type): `.obj` 26 B, `.exe` 22 B, `vc145.pdb` 36 B, project `.pdb` 1.4 MB (same size), `.ilk` 5,299 B, `vc145.idb` 354 B.
So the 20 to 26 `.obj` bytes and 22 `.exe` bytes are exactly what Visual Studio itself changes on every build: the object time stamp, the 16 byte PDB type server GUID in `.debug$T`, the 8 byte `.chks64` value that
covers it, and the `.exe` time stamp and PDB GUID. Those cannot be identical between any two builds, even on one Windows PC.

Notes:
1. Release x86 `CL.read` and `link.read`: `vctip.exe` and `mspdbsrv.exe` appear only for the first build of a session (measured on the PC: a fresh Debug x86 build lists both, a following one does not). vslab writes the fresh-session form.
2. x86 builds: VS runs the 32-bit `Hostx86\x86\CL.exe`; this install has no 32-bit host tools and Wine here has no 32-bit support, so vslab runs the x64-hosted x86 cross compiler. In Debug x86 the generated code differs slightly
(stack frames of 24 bytes in some functions, so unwind programs in `.debug$S` and call offsets in `.text`); Release x86 is not affected beyond the stamps. This is a real difference for Debug x86 and is caused by the compiler host binary, not by anything vslab sends.
3. Local class names in some Microsoft headers carry a hash: for example `std::basic_string<...>::append::__l2::<lambda_1>@...@@`0556da7a` in the PC's `vc145.pdb` versus `` `56833cde`` here. 152 type records of `vc145.pdb` differ only in that 8 character hash. The hash depends on the
canonical path of the source (it is stable across file times, file identity, spelling, a recreated folder, and from build to build on the PC) but is different under Wine for the same path (shown with a small test; the PC's `5780f7dd` for
`C:\Users\jaron\opencode-work\lam` against Wine's `55afda29`). I could not find what Windows feeds into it (not the volume serial, which I tried to set), so it stays as a documented difference. It changes `vc145.pdb` by 1.8 KB, the `.ilk` size by 88 bytes, and the project `.pdb` contents. The code and data of the objects are not affected.

### Project and `.vs` files against the PC

The `.vs` folder, the `*.dt.*` scan files and the `.ipch` files are written by the VS IDE, which only the owner can run; the only IDE state on the PC is from 18.10 (2026-11-06). A MSBuild run does not create them, so there is no 18.12 reference for those files.
`vslab check` against that real VS 18.10 zip (the lab built with 14.52): 40 identical, 40 same-format, 0 different-format, 0 missing, 0 extra (of 80 reference files). The 15 `dt` files now differ from the 18.10 ones only in the toolset version in their paths
(same size, they come from the real `cl /scanDependencies` of 14.52). Project files (`.slnx`, `.vcxproj`, `.filters`, `.user`, sources), `<project>.log` and the recipe are identical.
