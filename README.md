# vs-labs-linux

Do your Visual Studio C++ labs on Linux and still hand in a normal Visual Studio solution zip.

You write code in VS Code (or any editor). `vslab` builds it with Microsoft's real compiler (MSVC `cl` and `link`,
run under Wine), writes the same project files and build files Visual Studio writes, and zips the solution folder
the same way. No dual boot, no Windows VM.

Status: Ubuntu 24.04 is the target. See the "What is exact" table for what is genuine and what is approximate.

## What you need

- Ubuntu 24.04, about 6 GB free disk (the Microsoft download is about 2 to 3 GB, about 3 GB when installed)
- sudo once, for `apt` (or no sudo at all: the installer can unpack the packages in your home folder)
- Your agreement to Microsoft's Visual Studio license (the installer shows it and asks you to type `yes`)

## Install

```bash
git clone https://github.com/Jaron-Wilson/vs-labs-linux ~/vs-labs-linux
cd ~/vs-labs-linux
./install.sh
```

1. It checks for `wine64`, `msitools`, `python3`, `unzip`, `git`. If something is missing it prints the one command to run, for example
   `sudo apt update && sudo apt install -y wine64 libwine wine msitools python3 unzip git curl ca-certificates`.
   Without sudo it downloads the `.deb` files and unpacks them under `~/.local/share/vslab/root`.
2. It clones [msvc-wine](https://github.com/mstorsjo/msvc-wine), an open source downloader.
3. **License.** It prints the Visual Studio license link <https://go.microsoft.com/fwlink/?LinkId=2327714> and waits for you to
   type `yes`. Any other answer stops the installer before anything is downloaded. Your acceptance (user name and date)
   is written to `~/.local/share/vslab/LICENSE-ACCEPTED.txt`.
4. It downloads MSVC, the Windows SDK, MSBuild and the C++ MSBuild targets straight from Microsoft to your disk.
   This repository contains no Microsoft binary and never redistributes one.

Options: `--root DIR` (where everything lives), `--msvc-version 14.52` (also fetches that toolset next to an older one, after your yes), `--no-msbuild`, `--userspace`, `--no-msvc`.
Check with `vslab doctor`.

## Everyday use

```bash
vslab new LabPointers_WilsonJ     # creates LabPointers_WilsonJ_sol/ exactly like File > New > Project (Console App)
cd LabPointers_WilsonJ_sol
vslab sync                        # after you add .cpp/.h files (like Add Existing Item); --all also adds .txt
vslab build                       # Debug|x64 with the real cl/link, writes x64\Debug, .tlog, .log, .recipe, .vs
vslab run                         # runs the exe like Ctrl+F5 (working folder = project folder, "Press any key")
vslab zip                         # LabPointers_WilsonJ_sol.zip next to the folder, same layout as Visual Studio's zip
vslab check REF.zip MY.zip        # compare with a reference zip, file by file
vslab seed REAL.zip              # optional, once: use a Visual Studio made zip to fill Browse.VC.db rows for Microsoft headers
vslab vscode                      # VS Code tasks, F5 debug with g++, extension list (left out of the zip)
```

`vslab run --debug-style` prints the F5 message (`... exited with code 0 (0x0).`) instead of the Ctrl+F5 one.

Compiler messages show real Linux paths, so they are clickable in the terminal and in VS Code.

### VS Code

`vslab vscode` writes `.vscode/` with: build task (Ctrl+Shift+B runs `vslab build`, errors land in the Problems panel),
run task, zip task, and a launch configuration that builds a **native g++ debug binary** and starts `gdb` so you can set
breakpoints and step through the code (install the "C/C++" extension by Microsoft). The native binary is only for
stepping through logic; the graded program is the MSVC build. Behaviour differences between g++ and MSVC are possible
(for example `#include "date.h"` for a file named `Date.h` works on Windows and Wine but fails with g++).

### Zip checking

`vslab check` sorts every reference file into: identical (byte equal), same format but different bytes, different
format, missing, extra. It also compares the zip headers (create system, modes, flags, extra fields).

## What is exact and what is not

Read this, and show it to your teacher. Nothing below is hidden: the point is that the folder contains the same files with
the same names and formats, and a teacher can tell which parts of it a person cannot tell apart from Visual Studio's.

| Item | Status |
| --- | --- |
| `*.cpp`, `*.h`, data files | Your files, untouched. |
| `x64/Debug/*.exe`, `*.pdb`, `*.obj`, `*.ilk`, `vc145.pdb`, `vc145.idb`, `.lib` | **Genuine Microsoft output**: Microsoft's `cl.exe` and `link.exe` with the same switches Visual Studio 18 (toolset v145) uses, taken from the real `CL.command.1.tlog` and `link.command.1.tlog`. Bytes still differ from a Windows build (timestamps and GUIDs in the PE/PDB, tool version, and the path of the build host) but they are real compiler output. The exe runs the same. |
| `*.sln`/`*.slnx`, `*.vcxproj`, `*.vcxproj.filters`, `*.vcxproj.user` | **Regenerated with equivalent content** from templates copied from a real Visual Studio 18 project (same text, same line endings). Only the names and the project GUID change. `vslab sync` produces the same item groups as Visual Studio, tested to round trip a real project byte for byte. |
| `*.tlog` (CL/link command, read, write, items, secondary), `*.lastbuildstate`, `*.exe.recipe`, `<project>.log`, `microsoft/STL`, `_MD.tlog` | **Regenerated, byte-identical to a clean Visual Studio build.** Verified against a clean build of the same lab made on a Windows PC by the real Visual Studio MSBuild, for Debug and Release, x64 and x86: all tlog files are byte-identical, only `.lastbuildstate` differs because it records the compiler servicing number of the installed toolchain (see "Toolchain revision"). The command logs are from the commands that really ran; the read logs from `/showIncludes` plus `/VERBOSE:LIB`. For Win32 the records name the 32-bit host tools Visual Studio uses; the build itself runs the x64-hosted x86 cross compiler because Wine here cannot run 32-bit programs. `vslab build` is always a clean build ("Rebuild"). |
| `.vs/<Sln>/v18/DocumentLayout.json` and `.backup.json`, `*.vcxproj.user` | **Regenerated, same bytes for the same inputs.** Byte-identical to Visual Studio's file when given the same open files, times and caret state (verified on a real solution). Which tabs are open (default: the main `.cpp`, which is what a new project shows; `vslab tabs` records what you really have open), the tab order, the caret positions and the `WhenOpened` times are editor state that vslab cannot know, so they are defaults and the real generation time. |
| `x64/Debug/*.obj.dt.d.json`, `*.dt.module.json`, `*.dt.module.json.command` | **Genuine compiler output, same bytes for the same inputs.** Visual Studio's IDE runs `cl /scanDependencies` for each file you have opened; vslab runs the same real command under Wine for the same files (`vslab tabs`). The 15 reference files were reproduced byte for byte. |
| `.vs/<Sln>/v18/Browse.VC.db` | **Regenerated with equivalent content (needs a seed), otherwise schema only.** SQLite file with the exact table schema copied from Visual Studio. The symbols and code items of your own project files are produced by libclang (installed in a venv by `install.sh`) and matched Visual Studio's count exactly on the reference lab (741 of 741 code items); the other tables match in kind but not in every row (parse times, symbol ids, reference lists). The rows for Microsoft's own headers (`<iostream>`, `<vector>`, ...) cannot be produced without Microsoft's indexer, so they are copied from a database written by a real Visual Studio: run `vslab seed REAL.zip` once with any zip made by Visual Studio that contains a `Browse.VC.db` (yours from Windows, or your teacher's). That data is not in this repository. Without a seed, or for a header the seed lacks, those rows are simply missing. Visual Studio reparses on open. |
| `.vs/<Sln>/v18/Solution.VC.db` | **Regenerated, same bytes.** Schema plus the two `property` rows Visual Studio writes (434,176 bytes, like the real file). |
| `.vs/<Sln>/v18/.suo` | **Approximate (valid file).** A valid OLE compound file with the same stream names and most streams byte-identical to a real one (solution configuration, project info, document window state, outlining). Not byte-identical as a whole: sector layout and directory tree shape are Visual Studio internals, some per-document streams and the project-info hash are approximated. Visual Studio itself rewrites the file when you close the solution. Details in `docs/suo-layout-format.md`. |
| `.vs/<Sln>/FileContentIndex/*.vsidx` | **Regenerated with equivalent content.** The format (a trigram index of the project files, with their modification times) was decoded from a real Visual Studio 18 file (`docs/vsidx-format.md`). On the reference lab the size, header, file table, ranges and dictionary are byte identical and about 90 percent of all bytes match; the rest is the order of index entries, which depends on edit history. The file name is a random GUID, as in Visual Studio. Rewritten on `vslab build` and `vslab zip`. |
| `.vs/<Sln>/v18/ipch/AutoPCH/<hash>/<SOURCE>.ipch` | **Names exact, head exact, body not reproduced.** The folder name is the exact hash Visual Studio uses (decoded: FNV-1a 64 over the upper-cased Windows source path; so it depends on the Windows user name in `C:\Users\<you>\source\repos`). The file head (EDG front end banner, option records, include table, file table) is exact for all four reference files: the list and order of headers now comes from the real compiler (`cl /showIncludes`), and the modification times are the real times of the files on this machine, not copied from another PC. The 30 to 40 MB IntelliSense memory image after it cannot be reproduced and is written as sparse zeros (the file has the right size class, so it takes little disk). Visual Studio rebuilds it by itself. Details in `docs/ipch-format.md`. |
| Timestamps | **Real.** vslab never changes file times. Files have the Linux build time, in the zip (local time plus the Unix time field). |
| The zip file | Same structure as the reference: folder entries, entry order (case-insensitive name order, folder before content), deflate, Unix attributes `0666`/`0777`, `UT` and `ux` extra fields, data descriptors. One known difference: folder entries also carry the data-descriptor flag bit. |

Why the `.vs` folder exists at all: Visual Studio makes it as a cache. It is not needed to build or grade the lab.

## Toolchain revision (why `.exe`, `.obj`, `.pdb` are not byte-identical)

A same-input comparison with a clean Visual Studio build of the same lab (Debug x64, same Windows paths) shows: all MSVC and SDK headers the lab reads are
byte-identical to the PC's; `.text` and the other code and data sections of every `.obj` are identical; the `.exe` has the same section layout and size.
What differs is only: build timestamps, the PDB GUID (new on every build, even between two Linux builds), and the effect of the compiler build number: the Rich
header, CodeView type indices that are shifted by 4 between the compiler builds (so about 70 percent of per-function `.debug$S` sections and their `.chks64` checksums differ
in `Main.obj`), and a few import hints from the SDK libraries (a different refresh). That measurement was made against VS 18.10 (toolset 14.51.36231, compiler 19.51.36257) with
14.51 on Linux.

Which toolset matches: **Visual Studio 18.12 builds with toolset 14.52.37025** (compiler 19.52.37029, confirmed by a real MSBuild run:
`VCToolsVersion=14.52.37025` in `.lastbuildstate`). `vslab` therefore prefers a 14.52 toolset and falls back to the newest complete one with a
warning (`VSLAB_MSVC=14.51` selects the older toolset on purpose). When the 14.52 toolset is used, the records also follow the 18.12 MSBuild: the object files in `CL.write`
carry a `\\?\` prefix (`VSLAB_VS=18.10` or `18.12` overrides that guess). Get the toolset with `install.sh --msvc-version 14.52`.
A 14.52 download that only contains headers/lib stubs (as the first reinstall produced) is not enough; the compiler package must be there. `install.sh` does not run msvc-wine's fix-up step (it lower-cases `#include` text and converts line ends in Microsoft's headers); older installs can run
`vslab repair-headers` for the CRLF part, but a reinstall is the only complete fix.

## MSBuild (optional, experimental)

`install.sh` also downloads MSBuild and the Microsoft.Cpp targets (`--with-msbuild`). MSBuild is a .NET Framework program, so it
needs .NET in the Wine prefix (for example `winetricks dotnet48`, a large download that is not done for you).
Then `vslab build --msbuild` runs the real MSBuild on the real `.vcxproj` and writes genuine `.tlog` files.
Without it, the default `vslab build` runs `cl`/`link` directly with the same flags.

## Fedora (untested)

Not tested. Expected steps: `sudo dnf install wine msitools python3 unzip git curl`, then `./install.sh`. The user-space fallback (`--userspace`) is apt based and does not work on Fedora. Report what breaks.

## Troubleshooting

- `vslab doctor` shows what is found.
- Wine messages are hidden (`WINEDEBUG=-all`). Run `WINEDEBUG=err+all vslab build` to see them.
- Disk: everything lives under `~/.local/share/vslab` (or `--root`). Delete that folder to uninstall.
- The program prints garbage characters: set `LANG=C.UTF-8` in the terminal.

## Honesty about the toolchain

The compiler version is whatever Microsoft's installer channel offers (`vslab doctor` shows it). Visual Studio on your
PC may have a newer patch version. The generated files say which MSVC and SDK built them (in `.lastbuildstate`).
