#!/usr/bin/env bash
# EXPERIMENTAL: fetch Visual Studio's own C++ IntelliSense components (about 25 MB of vsix payloads) so that the real IntelliSense engine
# (vcpkgsrv / EDG front end) could be driven under Wine to write genuine .ipch and Browse.VC.db files. Untested: see docs/intellisense-engine.md.
# Shows Microsoft's license and requires the user's own "yes", like install.sh. Needs VSLAB_ROOT with msvc-wine cloned (run install.sh first).
set -euo pipefail
ROOT=${VSLAB_ROOT:-$HOME/.local/share/vslab}
[ -d "$ROOT/msvc-wine" ] || { echo "run install.sh first"; exit 1; }
echo "These components belong to Microsoft and are covered by the Visual Studio license: https://go.microsoft.com/fwlink/?LinkId=2327714"
[ -r /dev/tty ] || { echo "run in an interactive terminal"; exit 1; }
read -r -p 'Type yes to accept the license and download: ' ans </dev/tty
[ "$ans" = yes ] || { echo "not accepted"; exit 1; }
printf 'Visual Studio license accepted by user %s on %s by typing "yes" in fetch-intellisense.sh\n' "$(id -un)" "$(date -Is)" >> "$ROOT/LICENSE-ACCEPTED.txt"
. "$ROOT/env.sh"
cd "$ROOT/msvc-wine"
python3 vsdownload.py --dest "$ROOT/vside" --cache "$ROOT/cache" --accept-license --only-unpack --skip-recommended \
  Microsoft.VisualStudio.VC.Ide.LanguageService Microsoft.VisualStudio.VC.Ide.Core Microsoft.VisualStudio.VC.Ide.Base \
  Microsoft.VisualStudio.VC.Ide.Common Microsoft.VisualStudio.VC.Ide.ProjectSystem Microsoft.VisualStudio.VC.Ide.VCPkgDatabase \
  Microsoft.VisualStudio.VC.Ide.LanguageService.Dependencies
rm -rf "$ROOT/cache"
du -sh "$ROOT/vside"; find "$ROOT/vside" -iname 'vcpkgsrv*' -o -iname '*edg*' | head
