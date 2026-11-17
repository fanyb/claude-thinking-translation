"""Build a distributable installer on its target operating system and architecture."""
import hashlib
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
DIST = SOURCE / 'dist'
sys.path.insert(0, str(SOURCE))
from install import MODEL_SHA256, MODEL_URL, extract_model


PYTHON_RELEASE = '20261110'
PYTHON_VERSION = '3.12.16'
RUNTIMES = {
    ('Darwin', 'arm64'): ('aarch64-apple-darwin', '2f11b8aa3726bdbd87dd9eb76568412faddf4f47e26913fa45d6a2e424972acd'),
    ('Windows', 'AMD64'): ('x86_64-pc-windows-msvc', '355ee61b8207b91574491b1c6dc9b0ebb4408fc56bfafe498f3ef439314b52dc'),
    ('Linux', 'x86_64'): ('x86_64-unknown-linux-gnu', '6a9e62dad033790aef722dbd370e0ce76ce17b73627ba3ae679f537049350b39'),
    ('Linux', 'aarch64'): ('aarch64-unknown-linux-gnu', 'b6a41defec4975d94b4ff1950236e7383e5c02ba40ea48c9ec33c66087a35aab'),
}


def run(*args):
    subprocess.run(args, check=True)


def download(url, target, checksum):
    if not target.is_file():
        request = Request(url, headers={'User-Agent': 'Claude-Thinking-Translation/1.0'})
        with urlopen(request, timeout=90) as response, target.open('wb') as file:
            shutil.copyfileobj(response, file)
    with target.open('rb') as file:
        if hashlib.file_digest(file, 'sha256').hexdigest() != checksum:
            raise ValueError(f'SHA-256 mismatch for {target.name}')


def runtime(payload, downloads):
    triple, checksum = RUNTIMES[(platform.system(), platform.machine())]
    name = f'cpython-{PYTHON_VERSION}+{PYTHON_RELEASE}-{triple}-install_only_stripped.tar.gz'
    archive = downloads / name
    download(f'https://github.com/astral-sh/python-build-standalone/releases/download/{PYTHON_RELEASE}/{name}', archive, checksum)
    run('tar', '-xzf', archive, '-C', payload)
    python = payload / 'venv'
    (payload / 'python').rename(python)
    interpreters = (python / 'python.exe', python / 'pythonw.exe') if sys.platform == 'win32' else (python / 'bin/python3',)
    for exe in interpreters:
        if not exe.is_file():
            raise ValueError(f'Missing bundled interpreter {exe}')
    if sys.platform != 'win32' and not (python / 'bin/python').exists():
        (python / 'bin/python').symlink_to('python3')
    run(interpreters[0], '-E', '-s', '-c', 'import sqlite3, ssl, sys; print(sys.version)')
    return python


def build_mac(root, downloads):
    app = root / '安装 Claude 思考翻译.app'
    contents = app / 'Contents'
    payload = contents / 'Resources/Payload'
    installer_bin = contents / 'MacOS'
    dashboard = payload / 'Claude 思考翻译.app'
    dashboard_bin = dashboard / 'Contents/MacOS'
    installer_bin.mkdir(parents=True)
    dashboard_bin.mkdir(parents=True)
    runtime(payload, downloads)
    for name in ('install.command', 'gateway.py', 'claude-zh', 'LICENSE'):
        shutil.copy2(SOURCE / name, payload / name)
    shutil.copy2(SOURCE / 'Info.plist', dashboard / 'Contents')
    shutil.copy2(HERE / 'Installer.plist', contents / 'Info.plist')
    run('/bin/bash', HERE / 'build-worker.sh', sys.executable, SOURCE / 'TranslationWorker.swift', payload / 'translation-worker')
    for source, output in ((SOURCE / 'Controls.m', dashboard_bin / 'ClaudeOfflineTranslation'),
                           (HERE / 'Installer.m', installer_bin / 'Installer')):
        run('xcrun', 'clang', '-fobjc-arc', '-framework', 'AppKit', '-mmacosx-version-min=26.0', source, '-o', output)
    for bundle in (dashboard, app):
        run('codesign', '--force', '--sign', '-', bundle)
        run('codesign', '--verify', '--strict', bundle)
    run('hdiutil', 'create', '-fs', 'HFS+', '-format', 'UDZO', '-volname', 'Claude Thinking Translation',
        '-srcfolder', root, DIST / 'Claude-Thinking-Translation-macOS-Apple-Silicon.dmg')


def build_portable(root, downloads, version):
    windows = sys.platform == 'win32'
    payload = root / 'payload'
    payload.mkdir()
    python = runtime(payload, downloads)
    model = downloads / 'translate-en_zh-1_9.argosmodel'
    download(MODEL_URL, model, MODEL_SHA256)
    extract_model(model, payload / 'model')
    for name in ('gateway.py', 'argos_worker.py', 'install.py', 'panel.html', 'LICENSE'):
        shutil.copy2(SOURCE / name, payload)
    shutil.copy2(HERE / 'NOTICES.md', payload)
    site_packages = python / ('Lib/site-packages' if windows else 'lib/python3.12/site-packages')
    run(sys.executable, '-m', 'pip', 'install', '--ignore-installed', '--only-binary=:all:', '--target', site_packages,
        'ctranslate2==4.9.0', 'sentencepiece==0.2.1', 'numpy<3')
    exe = python / ('python.exe' if windows else 'bin/python3')
    run(exe, '-E', '-s', '-X', 'utf8', payload / 'gateway.py', 'check-translation')
    if windows:
        compiler = Path(r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe')
        # UTF-8 with BOM lets ISCC read the Chinese messages without a locale override.
        script = root / 'windows.iss'
        script.write_text((HERE / 'windows.iss').read_text(encoding='utf-8'), encoding='utf-8-sig')
        run(compiler, f'/DVersion={version}', f'/O{DIST}', script)
    else:
        entry = root / '安装 Claude 思考翻译'
        shutil.copy2(HERE / 'install-linux', entry)
        entry.chmod(0o755)
        name = f'Claude-Thinking-Translation-Linux-{platform.machine()}'
        destination = root.with_name(name)
        archive = DIST / f'{name}.tar.gz'
        root.rename(destination)
        run('tar', '-czf', archive, '-C', destination.parent, name)


if __name__ == '__main__':
    DIST.mkdir(exist_ok=True)
    # An optional cache holds the checksum-verified upstream downloads only.
    with tempfile.TemporaryDirectory(prefix='ctt-build-') as temp:
        temp = Path(temp)
        downloads = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else temp / 'downloads'
        downloads.mkdir(exist_ok=True)
        root = temp / 'package'
        root.mkdir()
        if sys.platform == 'darwin':
            build_mac(root, downloads)
        else:
            build_portable(root, downloads, sys.argv[1])
