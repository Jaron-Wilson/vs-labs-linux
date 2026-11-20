# Changelog

## Unreleased

- `vslab zip` now checks the zip as if it were extracted with Windows Extract All into a folder of the same name (the doubled
  `X_sol\X_sol` case), and warns if any path would pass the 260 character Windows limit. This includes the files a build creates
  (the `.tlog` folder and `FileListAbsolute.txt`), even when they are not in the zip. New options: `--clean` (leave out `.vs`, `x64`,
  `Debug`, `Release`, `ARM64`), `--flat` (no top folder, the `.slnx` at the root) and `--base-len N` (assumed extraction folder length,
  default 150). The default zip is unchanged.
