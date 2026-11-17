# .suo, DocumentLayout.json, .vcxproj.user: fidelity notes

Scripts: `gen_layout.py` (DocumentLayout.json, DocumentLayout.backup.json, .vcxproj.user, shared
helpers), `gen_suo.py` (.suo, pure python CFB v3 writer, imports `suo_consts.py`),
`validate_suo.py` / `validate_layout.py` (regenerate from the parameters of a real VS 18 solution and
compare byte for byte). Run: `python3 gen_layout.py SOL_DIR [--win-repos-root 'C:\Users\x\source\repos']`
then `python3 gen_suo.py SOL_DIR [same options] [--config Debug|x64]`.
Defaults: Debug|x64, startup project = the (first) project, open documents = its .cpp files (Main.cpp first),
Windows paths = `C:\Users\<linux user>\source\repos\<solution dir>` unless `--win-repos-root` is given.
Two real VS 18 samples were used: the lab reference (A) and a second real solution found in
/tmp/opencode/labinherit (B, 15 tabs incl. .h and .txt, 59 streams).

## Files in the reference that a plain Linux build lacks
`.vs/<sln>/v18/.suo`, `DocumentLayout.json`, `DocumentLayout.backup.json` (these two are identical),
`Solution.VC.db`, `Browse.VC.db` (+ -shm/-wal, empty wal), `ipch/AutoPCH/*/*.ipch`,
`.vs/<sln>/FileContentIndex/<guid>.vsidx` (the db/ipch/vsidx are other agents' formats), and
`<project>/<project>.vcxproj.user`. `.slnx`, `.vcxproj`, `.vcxproj.filters` come from the sources (the
.filters is a fixed template, LF line endings, no BOM). Nothing else small is missing.

## DocumentLayout.json / backup: EXACT
Byte identical to the reference when given the reference parameters (2 space indent, CRLF, no BOM, no
trailing newline). Fields: Version 1, WorkspaceRootPath (solution dir + `\`), Documents (Absolute and
Relative monikers `D:0:0:{projguid}|proj.vcxproj|path||{editor factory}`), group (DockedWidth 200,
SelectedChildIndex), per tab Title/monikers/ToolTips/ViewState (28 byte caret state, see below)/Icon/
WhenOpened. Editor factory: C++ `{D0E1A5C6-B359-4E41-9B60-3365922C2A22}` for .cpp and .h, plain text
`{8B382828-6202-11D1-8870-0000F87579D2}` for .txt (seen in sample B). Icons `...000677|` cpp, `...000680|` h,
`...003109|` txt. WhenOpened is the real generation time (one second apart per tab), ISO UTC with trailing
zero ms trimmed like JS. Approximate only in values that are user state: tab order, selected tab, scroll/caret.
ViewState bytes: `02 02 00 00`, u32@4 = first visible line, u32@16 = caret line, u32@20 = caret column.
DocumentIndex = position in the Documents list; tab order is separate (kept equal by default).

## .vcxproj.user: EXACT
UTF-8 BOM + CRLF, `<PropertyGroup />`, no trailing newline; identical in both samples. Not overwritten if present.

## .suo (OLE2/CFB v3, 512 byte sectors, mini cutoff 4096)
Container: valid per two independent readers (olefile, compoundfiles). Header values copied (0x3e/3, mini
sector 64). Directory is a balanced tree (the reference tree shape is VS internal and differs), sector
order differs, root CLSID zero, root mtime = real generation time. Stream NAMES: all 48 base streams
identical to the reference; extra `OutliningStateV167<id>` per open document (reference has them for
files opened earlier and closed, e.g. Date.h; unknowable).
Streams byte-identical to the real files when fed their parameters (verified on A and B):
BookmarkState, ClassViewContents, DNLPDialogOpened, DebuggerBreakpointGroups, DebuggerBreakpoints,
DebuggerExceptions, DebuggerExtendedExceptions, DebuggerFindSource, DebuggerFindSymbol,
DebuggerMemoryWindows, DebuggerWatches, DebuggerWinstoreAppMonitor, DiagToolWindow.v4,
ExternalFilesProjectContents, HiddenSlnFolders, MemoryToolSolutionOptions, ObjMgrContentsV8,
SccProvider.Solution.LastBranch, SccProvider.Solution.LoadCount (= 1 + times the solution was opened),
SelectedLaunchProfileName, SolutionControlOptions, TaskListShortcuts, TipPersistenceDev10+,
UnloadedProjects/Dev14/Ex/One, VC Project Package 15.0 (project GUID little endian),
VCPkg_* (3), WindowManager.CustomGroupNames/CustomTooltips/PinnedFrames/VertTabListWidths (256.0 px),
ProjectTrustInformation (project GUID LE + u32 load count), SolutionConfiguration (startup project,
Path.<proj>, dwStartupOpt, per config|platform fBatchBld, ActiveCfg=`Debug|x64`; configs ordered Release
before Debug as VS wrote them), ProjExplorerState, MRU Solution Files, DocumentWindowPositions,
OutliningStateDir, OutliningStateV167<id>.
Per stream:
- DebuggerFindSource: constant, holds `C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\...`
  include/crt/atlmfc paths; exact only for that VS 18 Community + MSVC 14.51.36231 install (the reference's).
- DebuggerBreakpoints: u32 1, byte length, solution dir `C:\...\<sol>\` utf16 nul, u32 0. Exact. No breakpoints
  are stored (the reference had none), so no breakpoint entries are generated.
- DiagToolWindow.v4 / DebuggerMemoryWindows etc: fixed blobs captured from the reference (tool window GUIDs).
- SolutionConfiguration: exact grammar (`;`+len+key `=` type value), derived from slnx/vcxproj.
- OutliningStateDir: next id + (path, id) entries. Exact content; entry ORDER in VS follows an internal hash
  order, ours is ascending id (stream size equal, bytes differ in order only).
- OutliningStateV167<id>: len byte, 0x01, utf16 path, SHA-256 of the file contents, u32 0, 16x 0xFF.
  EXACT (SHA-256 of the file as it is on disk; recomputed at generation).
- MRU Solution Files: `%UserProfile%\...|{0}|line,col|False` entries, size header, u16 count-1, u16 count.
  Exact format; ORDER is VS recency (not derivable), ours = open order. Line/col are caret state (0 default).
- ProjExplorerState: filter nodes + selected item. Exact format; filter order differs per solution in VS
  (A: Header, Resource, Source; B: Source, Header, Resource, not derivable), we use alphabetical. Selected
  item defaults to the first open document; item id constant 0x55 in both samples. Length field
  formula (path bytes + 20) derived from the two samples.
- DocumentWindowPositions: exact structure (documents list, 14 byte group header with DockedWidth 200.0,
  selected moniker, tab count, per tab 0x44 + monikers + title + tooltips + icon string + view state, 12 byte
  tail with constant 3). The leading document group GUID is random per solution in VS; we generate a fresh
  random GUID. Icon string in the tab record: VS wrote real icon ids in B and zeros in A for cpp tabs; we write
  the real id (JSON Icon) for code files and zeros for .txt.
- WindowManager.WhenOpened: per document 4 bytes + float64 milliseconds since 2019-01-01 UTC (real time of
  generation, sub ms precision). The 4 byte prefix is unexplained (looks random/hash); we use the first 4
  bytes of SHA-1 of the document path. APPROXIMATE (cosmetic).
- ProjInfoEx (16 bytes): unexplained hash, not md5/sha of paths/GUIDs/files (tried many). We emit md5 of the
  solution path. APPROXIMATE.
- `[Editor] Last Edit Location` (only in B, 48 bytes: size, 0x0f, name length, project relative path,
  u16 line, u16 col): only present after an edit; not generated.
Not stored in the .suo of either sample: breakpoints, watches, startup arguments, bookmarks (all empty), so
"debugger settings" are the constant empty-state blobs above.
Risk assessment: VS ignores/rebuilds unknown or stale .suo state; the file only affects restored tabs,
solution explorer selection and outlining. Windows paths inside refer to the `--win-repos-root` location.
