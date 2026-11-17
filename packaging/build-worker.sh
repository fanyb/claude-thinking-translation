#!/bin/bash
set -euo pipefail
python=$1
source=$2
output=$3
bridging="$(/usr/bin/xcode-select -p)/usr/include/swift"
flags=()
# CLT 26.0 declares SwiftBridging twice. Hide the duplicate for this compile only.
if [[ -f "$bridging/bridging.modulemap" && -f "$bridging/module.modulemap" ]] &&
   /usr/bin/grep -q 'module SwiftBridging' "$bridging/bridging.modulemap" &&
   /usr/bin/grep -q 'module SwiftBridging' "$bridging/module.modulemap"; then
    temp=$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/ctt-swift.XXXXXX")
    trap '/bin/rm -rf -- "$temp"' EXIT
    : > "$temp/empty.modulemap"
    "$python" - "$bridging/module.modulemap" "$temp" <<'PY'
import json
from pathlib import Path
import sys

temp = Path(sys.argv[2])
(temp / 'overlay.json').write_text(json.dumps({
    'version': 0, 'use-external-names': False,
    'roots': [{'type': 'file', 'name': sys.argv[1], 'external-contents': str(temp / 'empty.modulemap')}],
}))
PY
    flags=(-vfsoverlay "$temp/overlay.json")
fi
/usr/bin/xcrun swiftc -target arm64-apple-macos26.0 -O ${flags[@]+"${flags[@]}"} "$source" -o "$output"
