# Real IntelliSense engine route: investigated, dead end for now (2026-11-17)

Goal: get genuine `.ipch` files and the symbol rows of `Browse.VC.db` by running Visual Studio's own C++ language service under Wine instead of
approximating them.

## What was fetched

The VC.Ide packages (`LanguageService`, `Core`, `Base`, `Common`, `ProjectSystem`, `VCPkgDatabase`, `LanguageService.Dependencies`) were installed with
`vsdownload` by the owner, after his own license "yes". The manifest lists about 25 MB for those seven packages, but `vsdownload` resolved 141 packages
(MinShell, the .NET 8 and 10 runtimes as zips, VC.Llvm.Base and others): about **400 MB download and 476 MB on disk**, not 100 MB.

## What was found (static analysis and runs under Wine 9.0)

| Component | Finding |
| --- | --- |
| `VC/vcpackages/VCPkgSrv.exe` ("Visual C++ Language Service (Server)", 2.9 MB, native x64) | Runs under Wine. Its usage line is `VCPkgSrv [{-s GUID -p OwnerPID -i ID [-c]}\|-k] [-d\|-b] [-q[x\|m]] [-z[i ID]] [-r path] [-f name ...]`. It embeds SQLite, uses named pipes (`\\.\pipe\...`) and a keep-alive sweep. Started with `-s GUID -p 4 -i 1` and no client it exits at once without error: it is a server that waits for its client. |
| `VC/vcpackages/vcpkg.dll` (11 MB) | The client side, loaded inside `devenv.exe`. Its messages say it "sends instantiation arguments" to `vcpkgsrv.exe` and "establishes a connection"; it also contains the strings `AutoPCH`, `Browse.VC.db`, `languages.cpp.intelliSense.enableAutoPch`. It uses libuv named pipes (`\\.\pipe\%08x.%08x`) and a ChaCha20 constant. The wire protocol is undocumented. |
| `VC/vcpackages/cpfe.dll` (11 MB, EDG front end with Microsoft's `edge` layer) | Loads natively under Wine. 1100 mangled C++ exports (`edge::translation_unit`, `file_buffer`, `scoped_query_manager::check_and_compile`, `query_action_data::get_pch_file_name`, ...) plus the C exports `InvokeCompilerPassW` and `AbortCompilerPass`. It understands EDG options such as `--create_pch` and `--use_pch`. There is no headers or documentation for the C++ API, so a host that creates translation units and runs the preparse that writes an AutoPCH would have to be reverse engineered. |
| `VC/vcpackages/isense_model_extractor.exe` (EDGE IntelliCode model extractor) | The only small standalone host of `cpfe.dll`. Usage `isense_model_extractor [<compiler options>] <file name>`. Under Wine it prints the usage text for every argument combination tried (the argument handler returns failure before any file is opened; cause not found). It extracts an IntelliCode model, not an `.ipch`, so even working it would not write the files we want. |

## Why it is a dead end for byte-identical output

1. The only supported driver of the engine is `devenv.exe`: `vcpkg.dll` needs the Visual Studio shell (MinShell, MEF, VCProjectEngine, a .NET host).
   That stack is not installable under Wine here (the Wine prefix has no .NET), and there is no documented way to host `vcpkg.dll` or speak the
   `VCPkgSrv` pipe protocol directly.
2. The reference `.ipch` files were written by 18.10 (EDG "Aug 27 2026" build); the engine available from the channel is 18.12. A working run would stamp a
   different build date and likely a different internal image.
3. Per the earlier format study, 74 percent of an `.ipch` is a memory image of the EDG process with absolute addresses; only 75 of 22788 non-zero pages matched between two real files
   with the same header closure. Even Visual Studio does not reproduce it byte for byte between runs, so a "genuine" file would still not be identical to the reference.

Nothing in `vslab` depends on these components, so the downloaded tree (`~/msvc-linux/vside`, 476 MB) was deleted and the fetch script removed.
If this is ever resumed: reverse the `VCPkgSrv` pipe handshake (start with the `vcpkg.dll` code that builds the "instantiation arguments"), or reverse the
`edge::translation_unit` API in `cpfe.dll` and the AutoPCH preparse path (`mark_preparse_done`, `get_pch_file_name`).
