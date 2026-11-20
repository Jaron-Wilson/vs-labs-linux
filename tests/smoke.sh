#!/usr/bin/env bash
# Tests that need no Microsoft toolchain: new, sync, cache, zip, check.
set -euo pipefail
V=$(cd "$(dirname "$0")/.." && pwd)/bin/vslab
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cd "$T"
"$V" new LabSmoke_Test >/dev/null
cd LabSmoke_Test_sol
printf 'int helper(){return 1;}\n' > LabSmoke_Test/Helper.cpp
"$V" sync
grep -q 'Include="Helper.cpp"' LabSmoke_Test/LabSmoke_Test.vcxproj
grep -q 'Source Files' LabSmoke_Test/LabSmoke_Test.vcxproj.filters
"$V" cache
test -f .vs/LabSmoke_Test_sol.slnx/v18/DocumentLayout.json
python3 - <<'P'
import sqlite3,json,glob
json.loads(open(glob.glob('.vs/*/v18/DocumentLayout.json')[0],encoding='utf-8').read())
for d in ('Browse','Solution'):
    c=sqlite3.connect(glob.glob(f'.vs/*/v18/{d}.VC.db')[0]); assert c.execute("select count(*) from sqlite_master").fetchone()[0]>20
P
mkdir .vscode; echo '{}' > .vscode/tasks.json
"$V" zip -o ../a.zip
unzip -l ../a.zip | grep -q '\.vs/' && ! unzip -l ../a.zip | grep -q vscode
"$V" check ../a.zip ../a.zip | tail -1 | grep -q '0 missing'
python3 "$(dirname "$V")/../tests/test_vcdb.py" >/dev/null 2>&1 || { echo "test_vcdb.py failed" >&2; exit 1; }
echo "smoke OK"
