"""Install or control the per-user Claude thinking translator."""
import argparse
import hashlib
from http.client import HTTPConnection
import os
from pathlib import Path
import platform
import plistlib
import secrets
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen
import venv
import webbrowser
from zipfile import ZipFile

import gateway


SOURCE = Path(__file__).resolve().parent
HOME = Path.home()
WINDOWS = os.name == 'nt'
MAC = sys.platform == 'darwin'
SERVICE = 'claude-thinking-translation'
APPLE = HOME / 'Library/Application Support/Claude Offline Translation'
MAC_LABEL = 'local.claude-thinking-translation.argos'
MODEL = 'translate-en_zh-1_9'
MODEL_URL = f'https://argos-net.com/v1/{MODEL}.argosmodel'
MODEL_SHA256 = '433e7c4f034d87fbe2353161e05f18646d7999452f801a4e1f0378522b9850ab'
MODEL_FILES = ('sentencepiece.model', 'model/config.json', 'model/model.bin', 'model/shared_vocabulary.json')
BUNDLED = (SOURCE / 'model').is_dir() and (SOURCE / 'venv').is_dir()


def xdg(name, default):
    path = Path(os.environ.get(name, ''))
    return path if path.is_absolute() else HOME / default


if WINDOWS:
    RUNTIME = Path(os.environ.get('LOCALAPPDATA') or HOME / 'AppData/Local') / SERVICE
    programs = Path(os.environ.get('APPDATA') or HOME / 'AppData/Roaming') / 'Microsoft/Windows/Start Menu/Programs'
    AUTOSTART = programs / 'Startup' / f'{SERVICE}.lnk'
    SHORTCUT = programs / 'Claude Thinking Translation.lnk'
    bundle = RUNTIME / 'venv/python.exe'
    PYTHON = bundle if bundle.is_file() or (SOURCE / 'venv/python.exe').is_file() else RUNTIME / 'venv/Scripts/python.exe'
elif MAC:
    RUNTIME = HOME / 'Library/Application Support' / SERVICE
    AUTOSTART = HOME / 'Library/LaunchAgents' / f'{MAC_LABEL}.plist'
    SHORTCUT = HOME / 'Applications/Claude 思考翻译.webloc'
    PYTHON = RUNTIME / 'venv/bin/python'
else:
    RUNTIME = xdg('XDG_DATA_HOME', '.local/share') / SERVICE
    AUTOSTART = xdg('XDG_CONFIG_HOME', '.config') / 'autostart' / f'{SERVICE}.desktop'
    SHORTCUT = RUNTIME.parent / 'applications' / f'{SERVICE}.desktop'
    PYTHON = RUNTIME / 'venv/bin/python'

MANAGER = RUNTIME / 'install.py'
KEY = RUNTIME / 'service.key'
LOG = RUNTIME / 'status.log'
PANEL_URL = f'{gateway.ORIGIN}/_panel'
APPLE_APP = HOME / 'Applications/Claude 思考翻译.app'


def call_gateway(*args, root=RUNTIME, python=PYTHON):
    return subprocess.call([str(python), '-X', 'utf8', str(root / 'gateway.py'), *args])


def service_request(method, endpoint):
    connection = HTTPConnection('127.0.0.1', gateway.PORT, timeout=1)
    try:
        connection.request(method, endpoint, headers={'X-Translation-Service-Key': KEY.read_text(encoding='ascii')})
        response = connection.getresponse()
        try:
            return response.status == 200
        finally:
            response.read()
    except OSError:
        return False
    finally:
        connection.close()


def running():
    return service_request('GET', '/_health')


def start():
    if running():
        return
    if port_in_use():
        raise ValueError(f'端口 {gateway.PORT} 已被其他服务占用。')
    detach = {'creationflags': subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {'start_new_session': True}
    with LOG.open('ab') as log:
        child = subprocess.Popen([str(PYTHON), '-X', 'utf8', str(RUNTIME / 'gateway.py'), 'serve'],
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **detach)
    for _ in range(80):
        if running():
            return
        if child.poll() is not None:
            break
        time.sleep(0.25)
    if child.poll() is None:
        child.kill()
        child.wait()
    raise ValueError(f'翻译服务启动失败。日志位置 {LOG}')


def stop():
    if running():
        if not service_request('POST', '/_shutdown'):
            raise ValueError('翻译服务未确认退出。')
        for _ in range(50):
            if not port_in_use():
                return
            time.sleep(0.1)
        raise ValueError('翻译服务仍在退出，请关闭经过翻译的会话再试。')


def remove_runtime():
    for _ in range(20 if WINDOWS else 0):
        try:
            shutil.rmtree(RUNTIME)
            return
        except PermissionError:
            time.sleep(0.15)
    shutil.rmtree(RUNTIME)


def port_in_use():
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(('127.0.0.1', gateway.PORT)) == 0


def write_entry(path, operation):
    path.parent.mkdir(parents=True, exist_ok=True)
    if WINDOWS:
        command = "$ErrorActionPreference='Stop'; $shortcut=(New-Object -ComObject WScript.Shell).CreateShortcut($env:CTT_SHORTCUT); " \
                  "$shortcut.TargetPath=$env:CTT_PYTHON; $shortcut.Arguments=$env:CTT_ARGS; $shortcut.Save()"
        env = {**os.environ, 'CTT_SHORTCUT': str(path), 'CTT_PYTHON': str(PYTHON.with_name('pythonw.exe')),
               'CTT_ARGS': subprocess.list2cmdline(['-X', 'utf8', str(MANAGER), operation])}
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command], env=env, check=True)
    elif MAC:
        entry = {'Label': MAC_LABEL, 'RunAtLoad': True, 'ProgramArguments':
                 [str(PYTHON), '-X', 'utf8', str(MANAGER), operation]} if operation == 'start' else {'URL': PANEL_URL}
        path.write_bytes(plistlib.dumps(entry))
    else:
        def escape(path):
            text = str(path).replace('%', '%%')
            return '"' + ''.join(('\\' if char in '"`$\\' else '') + char for char in text).replace('\\', '\\\\') + '"'

        path.write_text('[Desktop Entry]\nType=Application\nName=Claude 思考翻译\nTerminal=false\n'
                        f'Exec={escape(PYTHON)} -X utf8 {escape(MANAGER)} {operation}\n', encoding='utf-8')


def open_panel(portable):
    if not portable:
        if subprocess.call(['/usr/bin/open', str(APPLE_APP)]):
            print(f'可从 Finder 打开 {APPLE_APP}')
        return
    if not (RUNTIME / 'panel.html').is_file():
        raise ValueError('当前安装早于图形面板版。请先恢复直连并卸载旧版，再安装这一版。')
    start()
    has_desktop = WINDOWS or MAC or os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')
    if has_desktop:
        try:
            if webbrowser.open(PANEL_URL):
                return
        except (OSError, webbrowser.Error):
            pass
    print(f'图形面板地址 {PANEL_URL}')


def download_model():
    archive = RUNTIME / f'{MODEL}.zip'
    checksum = hashlib.sha256()
    request = Request(MODEL_URL, headers={'User-Agent': 'Claude-Thinking-Translation/1.0'})
    with urlopen(request, timeout=60) as response, archive.open('wb') as file:
        for chunk in iter(lambda: response.read(1 << 20), b''):
            checksum.update(chunk)
            file.write(chunk)
            if file.tell() > 100 * (1 << 20):
                raise ValueError('Argos 模型下载大小超过预期。')
    if checksum.hexdigest() != MODEL_SHA256:
        raise ValueError('Argos 模型 SHA-256 校验失败。')
    extract_model(archive, RUNTIME / 'model')
    archive.unlink()


def extract_model(archive, destination):
    with ZipFile(archive) as model:
        for name in MODEL_FILES:
            output = destination / name
            output.parent.mkdir(parents=True, exist_ok=True)
            with model.open(f'{MODEL}/{name}') as source, output.open('wb') as target:
                shutil.copyfileobj(source, target)


def install_portable():
    if sys.version_info < (3, 10):
        raise ValueError('Argos 安装需要 Python 3.10 或以上，推荐 3.12。')
    if MAC and (APPLE / 'gateway.py').exists():
        raise ValueError('已存在 macOS 离线版。可继续使用，或恢复直连并卸载后再安装 Argos。')
    if any(path.exists() or path.is_symlink() for path in (RUNTIME, AUTOSTART, SHORTCUT)) or port_in_use():
        raise ValueError(f'已有安装或端口占用。请先运行 status 检查。安装目录 {RUNTIME}')
    RUNTIME.mkdir(mode=0o700, parents=True)
    try:
        for file in ('gateway.py', 'argos_worker.py', 'install.py', 'panel.html'):
            shutil.copyfile(SOURCE / file, RUNTIME / file)
        if BUNDLED:
            for directory in ('venv', 'model'):
                shutil.copytree(SOURCE / directory, RUNTIME / directory, symlinks=True)
            for name in ('LICENSE', 'NOTICES.md'):
                shutil.copyfile(SOURCE / name, RUNTIME / name)
        else:
            venv.EnvBuilder(with_pip=True).create(RUNTIME / 'venv')
            subprocess.run([str(PYTHON), '-m', 'pip', 'install', '--only-binary=:all:',
                            'ctranslate2==4.9.0', 'sentencepiece==0.2.1', 'numpy<3'], check=True)
            print('正在下载并校验 Argos 英译简中模型（约 67 MB）。', flush=True)
            download_model()
        if call_gateway('self-test') or call_gateway('check-translation'):
            raise ValueError('翻译组件自检失败。')
        KEY.write_text(secrets.token_hex(32), encoding='ascii')
        start()
        write_entry(AUTOSTART, 'start')
        write_entry(SHORTCUT, 'panel')
        if BUNDLED:
            (RUNTIME / '.installed-by-package').touch()
    except (Exception, KeyboardInterrupt):
        if KEY.exists():
            stop()
        AUTOSTART.unlink(missing_ok=True)
        SHORTCUT.unlink(missing_ok=True)
        remove_runtime()
        raise
    print('Argos 离线翻译已安装。可在「Claude 思考翻译」面板按需开启。')


def use_apple():
    return MAC and platform.machine() == 'arm64' and int(platform.mac_ver()[0].split('.')[0]) >= 26


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    setup = commands.add_parser('install')
    setup.add_argument('--engine', choices=('auto', 'apple', 'argos'), default='auto')
    setup.add_argument('--no-open', action='store_true')
    for name in ('status', 'start', 'panel', 'check', 'uninstall', 'desktop-on', 'desktop-off', 'desktop-direct',
                 'cli-on', 'cli-off', 'cli-direct'):
        commands.add_parser(name)
    commands.add_parser('claude').add_argument('args', nargs=argparse.REMAINDER)
    if WINDOWS:
        commands.add_parser('prepare-uninstall')
    if sys.argv[1:2] == ['claude']:
        return operate('claude', sys.argv[2:])
    args = parser.parse_args()
    if args.operation == 'install':
        if not (MAC or WINDOWS or sys.platform.startswith('linux')):
            raise ValueError('当前系统不在安装范围。')
        if not WINDOWS and os.getuid() == 0:
            raise ValueError('请用当前用户安装，无需 sudo。')
        apple = args.engine == 'apple' or (args.engine == 'auto' and use_apple())
        if apple:
            if not use_apple():
                raise ValueError('系统离线翻译安装需要 Apple 芯片和 macOS 26 或以上。可改用 --engine argos。')
            result = subprocess.call(['/bin/bash', str(SOURCE / 'install.command')])
            if result:
                return result
        else:
            install_portable()
        if not args.no_open:
            open_panel(not apple)
        return 0
    return operate(args.operation)


def operate(operation, args=()):
    portable = KEY.is_file()
    if not portable and not (MAC and (APPLE / 'gateway.py').is_file()):
        raise ValueError('尚未安装。请先运行 install。')
    root = RUNTIME if portable else APPLE
    apple_python = APPLE / 'venv/bin/python3'
    python = PYTHON if portable else apple_python if apple_python.is_file() else Path('/usr/bin/python3')

    def gateway_command(*params):
        return call_gateway(*params, root=root, python=python)

    if operation in ('uninstall', 'prepare-uninstall'):
        if operation == 'prepare-uninstall' and not (RUNTIME / '.installed-by-package').is_file():
            raise ValueError('没有通过 Windows 安装包装好的版本。')
        if not portable:
            return subprocess.call(['/bin/bash', str(SOURCE / 'install.command'), '--uninstall'])
        if SOURCE == RUNTIME and WINDOWS and operation == 'uninstall':
            raise ValueError('请从 GitHub 检出的目录运行卸载。')
        if gateway_command('check-detached'):
            return 1
        stop()
        AUTOSTART.unlink(missing_ok=True)
        SHORTCUT.unlink(missing_ok=True)
        if operation == 'prepare-uninstall':
            return 0
        remove_runtime()
        print('已卸载本地翻译。')
        return 0
    if operation == 'status':
        print(f"引擎 {'Argos 离线' if portable else 'macOS 离线'}", flush=True)
        if portable:
            print(f"本地服务 {'运行中' if running() else '未运行'}", flush=True)
        gateway_command('status')
        return gateway_command('cli-status')
    if operation == 'check':
        if portable:
            start()
        return gateway_command('self-test') or gateway_command('check-translation')
    if operation == 'start':
        if portable:
            start()
        return 0
    if operation == 'panel':
        open_panel(portable)
        return 0
    if operation == 'claude':
        mode = RUNTIME / 'cli.json'
        if portable and mode.is_file() and gateway.load(mode).get('mode') != 'direct':
            start()
        return gateway_command('cli-launch', *args)
    if portable and operation in ('desktop-on', 'cli-on'):
        start()
    return gateway_command(operation.removeprefix('desktop-'))


if __name__ == '__main__':
    os.umask(0o077)
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
