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

Options: `--root DIR` (where everything lives), `--msvc-version 14.50`, `--no-msbuild`, `--userspace`, `--no-msvc`.
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
| `*.tlog` (CL/link command, read, write, items, secondary), `*.lastbuildstate`, `*.exe.recipe`, `<project>.log` | **Regenerated** by vslab from the real commands that ran. Command lines, outputs, and format are the real ones. The `read` logs list the headers the compiler reported via `/showIncludes`, which is the same file set MSBuild's file tracker records. If you run with `--msbuild` and a working .NET in Wine, these are written by the real MSBuild instead (experimental, see below). |
| `.vs/<Sln>/v18/DocumentLayout.json` and `.backup.json` | **Regenerated with equivalent content**: same JSON schema, same field order, CRLF, Windows-style paths (`C:\Users\<you>\source\repos\...`). Lists the open file(s); window state is approximate. |
| `.vs/<Sln>/v18/Browse.VC.db`, `Solution.VC.db` | **Approximate.** SQLite files with the exact table schema copied from a real Visual Studio 18 database, written by vslab. Row content is minimal unless a symbol generator is installed under `gens/`. Visual Studio rebuilds these when it opens the solution. |
| `.vs/<Sln>/v18/.suo` | **Approximate.** Same name; not a byte-for-byte Visual Studio file unless a generator is installed under `gens/`. Visual Studio ignores an unreadable `.suo` and writes a new one. |
| `.vs/<Sln>/FileContentIndex/*.vsidx` | **Regenerated with equivalent content.** The format (a trigram index of the project files, with their modification times) was decoded from a real Visual Studio 18 file (`docs/vsidx-format.md`). On the reference lab the size, header, file table, ranges and dictionary are byte identical and about 90 percent of all bytes match; the rest is the order of index entries, which depends on edit history. The file name is a random GUID, as in Visual Studio. Rewritten on `vslab build` and `vslab zip`. |
| `.vs/<Sln>/v18/ipch/AutoPCH/<hash>/<SOURCE>.ipch` | **Names exact, head exact, body not reproduced.** The folder name is the exact hash Visual Studio uses (decoded: FNV-1a 64 over the upper-cased Windows source path; so it depends on the Windows user name in `C:\Users\<you>\source\repos`). The file head (EDG front end banner, option records, include table, file table with real modification times) follows the real format and matched byte for byte on 3 of 4 reference files. The 30 to 40 MB IntelliSense memory image after it cannot be reproduced and is written as sparse zeros (the file has the right size class, so it takes little disk). Visual Studio rebuilds it by itself. Details in `docs/ipch-format.md`. |
| Timestamps | **Real.** vslab never changes file times. Files have the Linux build time, in the zip (local time plus the Unix time field). |
| The zip file | Same structure as the reference: folder entries, entry order (case-insensitive name order, folder before content), deflate, Unix attributes `0666`/`0777`, `UT` and `ux` extra fields, data descriptors. One known difference: folder entries also carry the data-descriptor flag bit. |

Why the `.vs` folder exists at all: Visual Studio makes it as a cache. It is not needed to build or grade the lab.

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
