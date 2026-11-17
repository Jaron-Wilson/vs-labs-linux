# Real IntelliSense engine route (item 8): status

Goal: get genuine `.ipch` files (and the symbol rows of `Browse.VC.db`) by running Visual Studio's own C++ language service instead of
approximating them.

What is known (from the public Visual Studio 18 channel manifest, read only, nothing downloaded):

| Package | Size | Role |
| --- | --- | --- |
| Microsoft.VisualStudio.VC.Ide.LanguageService | 15.7 MB | the C++ language service (IntelliSense engine, EDG front end, `vcpkgsrv`) |
| Microsoft.VisualStudio.VC.Ide.Core, .Base, .Common, .ProjectSystem, .VCPkgDatabase, .LanguageService.Dependencies | 0.7 to 5 MB each | project system and shared libraries it depends on |

About 25 MB of payloads in total. They are installed by `vsdownload` as ordinary packages, and need the same license acceptance as the compiler: the
`vsdownload` tool shows the license prompt for every run, so I did not run it. `scripts/fetch-intellisense.sh` does it with the user's own "yes".

What is not known yet, and is the actual research: (a) whether the engine runs outside the Visual Studio shell (it is a native service that Visual Studio
starts and talks to over a pipe, and part of it is .NET); (b) whether it runs under Wine without .NET Framework; (c) what request makes it write an `.ipch`
(the files are written when a translation unit is parsed for the editor); (d) the engine in the 18.12 channel is newer than the 18.10 that wrote the reference
files, so even a working run would stamp a different EDG build date in the `.ipch` head and probably a different memory image.
Disk needed: about 100 MB. Network: the vsix files only.
