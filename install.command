#!/bin/bash
set -euo pipefail
umask 077

fail() { printf '%s\n' "$*" >&2; exit 1; }
source_dir=$(cd -- "$(dirname -- "$0")" && pwd -P)
runtime="$HOME/Library/Application Support/Claude Offline Translation"
app="$HOME/Applications/Claude 思考翻译.app"
launcher="$HOME/.local/bin/claude-zh"
label=local.codex.claude-offline-translation
plist="$HOME/Library/LaunchAgents/$label.plist"
domain="gui/$(/usr/bin/id -u)"
service="$domain/$label"
marker="$runtime/.installed-by-distribution"
health_url=http://127.0.0.1:15722/_health
python=/usr/bin/python3

[[ $# -le 1 && ( $# -eq 0 || ${1:-} == --uninstall ) ]] || fail '运行 install.command 安装，添加 --uninstall 卸载。'
[[ $(/usr/bin/id -u) != 0 ]] || fail '请在自己的 macOS 用户中运行，安装无需 sudo。'
developer=$(/usr/bin/xcode-select -p 2>/dev/null) || fail '请先运行 xcode-select --install。安装完成后再重试。'
"$python" -c 'import sys; sys.exit(sys.version_info < (3, 9))' || fail '需要 Apple 命令行工具提供的 Python 3.9 或以上。'

if [[ ${1:-} == --uninstall ]]; then
    [[ -f "$marker" ]] || fail '找不到通过这个安装包装好的版本。'
    "$python" - "$health_url" <<'PY'
import json
from pathlib import Path
import sys

relay = sys.argv[1].removesuffix('/_health') + '/claude-desktop'
library = Path.home() / 'Library/Application Support/Claude-3p/configLibrary'
try:
    for path in library.glob('*.json'):
        if path.name.startswith('_'):
            continue
        url = json.loads(path.read_bytes()).get('inferenceGatewayBaseUrl')
        if isinstance(url, str) and url.rstrip('/') == relay:
            sys.exit('有 Claude Desktop 配置还在使用翻译。请在 CC Switch 中重新应用该配置，或把它设为当前 Gateway 后点「恢复直连」，再重试。')
except (OSError, ValueError, AttributeError):
    sys.exit('无法核对 Claude Desktop 的 Gateway 配置。请修复该配置后重试。')
PY
    if /bin/launchctl print "$service" >/dev/null 2>&1; then
        /bin/launchctl bootout "$service"
    fi
    /bin/rm -f -- "$plist"
    if /usr/bin/cmp -s "$launcher" "$source_dir/claude-zh"; then
        /bin/rm -f -- "$launcher"
    fi
    /bin/rm -rf -- "$runtime" "$app"
    printf '%s\n' '已卸载 Claude 思考翻译。请重新打开 Claude Desktop 和 CLI 会话。'
    exit 0
fi

[[ $(/usr/bin/uname -m) == arm64 ]] || fail '此安装包面向 Apple 芯片 Mac。请在原生终端中运行。'
macos=$(/usr/bin/sw_vers -productVersion)
(( ${macos%%.*} >= 26 )) || fail '需要 macOS 26 或以上版本。'
for path in "$runtime" "$app" "$launcher" "$plist"; do
    [[ ! -e "$path" && ! -L "$path" ]] || fail "安装位置已有文件，请保留现有版本：$path"
done
if /bin/launchctl print "$service" >/dev/null 2>&1 || /usr/sbin/lsof -nP -iTCP:15722 -sTCP:LISTEN -t >/dev/null 2>&1; then
    fail '本地翻译服务已存在，或端口 15722 已被使用。'
fi

temp=$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/claude-reasoning.XXXXXX")
owns_runtime=0
owns_app=0
owns_launcher=0
owns_plist=0
loaded=0
complete=0
cleanup() {
    /bin/rm -rf -- "$temp"
    if (( ! complete )); then
        if (( loaded )); then /bin/launchctl bootout "$service" || true; fi
        if (( owns_plist )); then /bin/rm -f -- "$plist"; fi
        if (( owns_launcher )); then /bin/rm -f -- "$launcher"; fi
        if (( owns_app )); then /bin/rm -rf -- "$app"; fi
        if (( owns_runtime )); then /bin/rm -rf -- "$runtime"; fi
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf '%s\n' '正在本机编译翻译组件和控制面板。第一次编译可能需要几分钟。'
swift_flags=()
bridging="$developer/usr/include/swift"
# CLT 26.0 can declare SwiftBridging twice. Hide the duplicate only for this compile.
if [[ -f "$bridging/bridging.modulemap" && -f "$bridging/module.modulemap" ]] &&
   /usr/bin/grep -q 'module SwiftBridging' "$bridging/bridging.modulemap" &&
   /usr/bin/grep -q 'module SwiftBridging' "$bridging/module.modulemap"; then
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
    swift_flags=(-vfsoverlay "$temp/overlay.json")
fi
/usr/bin/xcrun swiftc -target arm64-apple-macos26.0 -O ${swift_flags[@]+"${swift_flags[@]}"} \
    "$source_dir/TranslationWorker.swift" -o "$temp/translation-worker"
if ! printf '%s\n' '"The offline translation is ready."' | "$temp/translation-worker" | \
        "$python" -c 'import json, re, sys; sys.exit(not re.search(r"[\u3400-\u9fff]", json.load(sys.stdin) or ""))' 2>/dev/null; then
    fail '离线英译简中暂不可用。请到「系统设置 → 通用 → 语言与地区 → 翻译语言」下载英语（美国）和简体中文后重试。'
fi
staged_app="$temp/Claude 思考翻译.app"
/bin/mkdir -p -- "$staged_app/Contents/MacOS"
/usr/bin/install -m 644 "$source_dir/Info.plist" "$staged_app/Contents/Info.plist"
/usr/bin/xcrun clang -fobjc-arc -framework AppKit -mmacosx-version-min=26.0 \
    "$source_dir/Controls.m" -o "$staged_app/Contents/MacOS/ClaudeOfflineTranslation"
/usr/bin/codesign --force --sign - "$staged_app"
/usr/bin/codesign --verify --strict "$staged_app"
"$python" "$source_dir/gateway.py" self-test

/bin/mkdir -p -- "$(dirname -- "$runtime")" "$(dirname -- "$app")" "$(dirname -- "$launcher")" "$(dirname -- "$plist")"
/bin/mkdir -m 700 -- "$runtime"
owns_runtime=1
/usr/bin/install -m 600 "$source_dir/gateway.py" "$runtime/gateway.py"
/usr/bin/install -m 700 "$temp/translation-worker" "$runtime/translation-worker"
"$python" - "$runtime" "$label" > "$temp/agent.plist" <<'PY'
from pathlib import Path
import plistlib
import sys

runtime = Path(sys.argv[1])
log = str(runtime / 'status.log')
plistlib.dump({
    'Label': sys.argv[2], 'ProgramArguments': ['/usr/bin/python3', str(runtime / 'gateway.py'), 'serve'],
    'WorkingDirectory': str(runtime), 'EnvironmentVariables': {'HOME': str(Path.home())},
    'KeepAlive': True, 'ThrottleInterval': 3, 'StandardOutPath': log, 'StandardErrorPath': log,
}, sys.stdout.buffer)
PY
/bin/mkdir -- "$app"
owns_app=1
/bin/mv -- "$staged_app/Contents" "$app/Contents"
(set -C; : > "$launcher")
owns_launcher=1
/usr/bin/install -m 700 "$source_dir/claude-zh" "$launcher"
(set -C; /bin/cat "$temp/agent.plist" > "$plist")
owns_plist=1
: > "$runtime/status.log"
/bin/launchctl bootstrap "$domain" "$plist"
loaded=1
for ((attempt = 0; attempt < 24; attempt++)); do
    if /usr/bin/curl -fsS --noproxy '*' --max-time 1 "$health_url" 2>/dev/null | \
        "$python" -c 'import json, sys; sys.exit(json.load(sys.stdin) != {"service":"claude-offline-translation", "cli":True})' 2>/dev/null; then
        : > "$marker"
        complete=1
        printf '%s\n' '安装成功。打开 ~/Applications 中的「Claude 思考翻译」，按需开启 Desktop 或 CLI 翻译。'
        exit 0
    fi
    /bin/sleep 0.5
done
/usr/bin/tail -n 10 "$runtime/status.log" >&2
fail '翻译服务未通过启动检查，本次安装将回滚。'
