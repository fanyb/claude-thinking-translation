"""Local Claude Desktop and Claude Code relay for CC Switch."""
import base64
import copy
import hashlib
import hmac
import http.client
from contextlib import closing
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from queue import Empty, Queue
import re
import secrets
import shlex
import shutil
import sqlite3
import stat
from string import Template
import subprocess
import sys
import tempfile
from threading import Lock, Thread
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parent
ROUTE = ROOT / 'route.json'
CLI_MODE = ROOT / 'cli.json'
CLI_KEY = ROOT / 'cli.key'
REPLAY = ROOT / 'replay.sqlite3'
CC_DB = Path.home() / '.cc-switch/cc-switch.db'
SERVICE_KEY = ROOT / 'service.key'
PORT = 15722
ORIGIN = f'http://127.0.0.1:{PORT}'
LOCAL_URL = f'{ORIGIN}/claude-desktop'
PANEL = ROOT / 'panel.html'
PANEL_CSRF = secrets.token_urlsafe(32)
PANEL_LOCK = Lock()
HOP = {'connection', 'keep-alive', 'transfer-encoding', 'te', 'trailer', 'upgrade',
       'proxy-authorization', 'proxy-authenticate', 'content-length', 'host', 'accept-encoding'}
THOUGHT = {'thinking', 'redacted_thinking'}
HAN = re.compile(r'[\u3400-\u9fff]')
WORDS = re.compile(r'\b[A-Za-z]{2,}\b')
SENTENCE = re.compile(r'(?<!\d)[.!?。！？]["”)]?(?:\s+|$)|\n+')
DEEPSEEK = re.compile(r'deepseek-v4[.-]1-flash(?:[-\d]*)', re.IGNORECASE)
CLI_THINKING = re.compile(r'(?:deepseek-v4[.-]1-flash|glm-5\.3(?:-flash)?)(?:[-\d]*)', re.IGNORECASE)
CLI_HEADERS = {'authorization': 'ANTHROPIC_AUTH_TOKEN', 'x-api-key': 'ANTHROPIC_API_KEY'}


def load(path):
    return json.loads(path.read_bytes())


def atomic_json(path, data, mode=0o600):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temp = Path(file.name)
        if os.name != 'nt':
            os.fchmod(file.fileno(), mode)
        file.write((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())
        file.flush()
        os.fsync(file.fileno())
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def route_settings():
    return load(ROUTE) if ROUTE.exists() else {}


def local_upstream(url):
    if not isinstance(url, str):
        raise ValueError('找不到原来的 CC Switch 网关地址。')
    parts = urlsplit(url)
    if (parts.scheme != 'http' or parts.hostname not in ('localhost', '127.0.0.1')
            or parts.port in (None, PORT) or parts.netloc != f'{parts.hostname}:{parts.port}'
            or parts.path.rstrip('/') != '/claude-desktop' or parts.query or parts.fragment):
        raise ValueError('当前配置不是 CC Switch 的本地 Claude Desktop 网关。')
    return parts.port


def desktop_library():
    home = Path.home()
    if sys.platform == 'darwin':
        directory = home / 'Library/Application Support'
    elif os.name == 'nt':
        directory = Path(os.environ.get('LOCALAPPDATA') or home / 'AppData/Local')
        exact = directory / 'Claude-3p'
        if not exact.exists():
            candidates = sorted(p for p in directory.glob('Claude*-3p*') if p.is_dir())
            if candidates:
                return candidates[0] / 'configLibrary'
    else:
        config = Path(os.environ.get('XDG_CONFIG_HOME', ''))
        directory = config if config.is_absolute() else home / '.config'
    return directory / 'Claude-3p/configLibrary'


def active_profile():
    library = desktop_library()
    if not (library / '_meta.json').is_file():
        raise ValueError('Claude Desktop 没有可用的 CC Switch Gateway 配置。')
    profile_id = load(library / '_meta.json').get('appliedId', '')
    if not isinstance(profile_id, str) or not re.fullmatch('[a-f0-9-]{36}', profile_id):
        raise ValueError('Claude Desktop 没有正在使用的 Gateway 配置。')
    path = library / (profile_id + '.json')
    record = load(path)
    if record.get('inferenceProvider') != 'gateway':
        raise ValueError('Claude Desktop 当前没有使用 Gateway。')
    return path, record


def check_detached():
    for path in desktop_library().glob('*.json'):
        if path.name.startswith('_'):
            continue
        url = load(path).get('inferenceGatewayBaseUrl')
        if isinstance(url, str) and url.rstrip('/') == LOCAL_URL:
            raise ValueError('有 Claude Desktop 配置还在使用翻译。请先恢复直连，或在 CC Switch 重新应用该配置。')


def cc_key():
    with closing(sqlite3.connect(CC_DB.as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
        row = db.execute("SELECT value FROM settings WHERE key='claude_desktop_gateway_token'").fetchone()
    return row[0].strip() if row else ''


def probe(port, path, headers=None):
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=4)
    try:
        conn.request('GET', path, headers=headers or {})
        response = conn.getresponse()
        return response.status == 200, response.read()
    finally:
        conn.close()


def cli_mode():
    return load(CLI_MODE).get('mode', 'direct') if CLI_MODE.exists() else 'direct'


def set_cli_mode(command):
    state = cli_mode()
    if command == 'status':
        return {'on': '离线翻译已开启', 'english': '已恢复英文', 'direct': '直连当前供应商'}[state]
    if command == 'on':
        healthy, service = probe(PORT, '/_health')
        if not healthy or json.loads(service).get('cli') is not True or not replay_ready():
            raise ValueError('CLI 翻译服务暂时不可用。')
        if not CLI_KEY.exists():
            with CLI_KEY.open('xb') as file:
                file.write(secrets.token_bytes(32))
    state = 'english' if command == 'off' else command
    atomic_json(CLI_MODE, {'mode': state})
    launcher = 'python install.py claude' if (ROOT / 'argos_worker.py').is_file() else 'claude-zh'
    return {
        'on': f'翻译已开启。在终端运行 {launcher} 进入翻译会话。',
        'english': '已恢复英文。已接入的会话从下一次请求生效。',
        'direct': f'新开的 {launcher} 会直接连接当前供应商。已接入的会话先退出再重开。',
    }[state]


def cli_upstream(base):
    url = urlsplit(base)
    if not url.hostname or url.username is not None or url.query or url.fragment:
        raise ValueError('CLI 网关地址格式不受支持。')
    if url.scheme != 'https' and (url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost')
                                  or url.port in (None, PORT)):
        raise ValueError('CLI 网关须使用 HTTPS 或 CC Switch 本地 HTTP 地址。')
    return url


def cli_digest(value):
    return hmac.new(CLI_KEY.read_bytes(), value, hashlib.sha256).hexdigest()


def cli_ticket(base, headers):
    cli_upstream(base)
    auth = {key: cli_digest(value.encode()) for key, value in headers.items() if value}
    data = base64.urlsafe_b64encode(json.dumps([base, auth], separators=(',', ':')).encode()).rstrip(b'=')
    return data.decode() + '.' + cli_digest(data)


def cli_target(ticket, headers):
    data, claimed = ticket.encode().rsplit(b'.', 1)
    if not hmac.compare_digest(cli_digest(data).encode(), claimed):
        raise PermissionError('无效的 CLI 翻译入口。请重新打开 claude。')
    base, auth = json.loads(base64.urlsafe_b64decode(data + b'=' * (-len(data) % 4)))
    actual = {key: cli_digest(headers[key].encode()) for key in CLI_HEADERS if headers.get(key)}
    if actual != auth:
        raise PermissionError('CLI 网关凭据已更新。请重新打开 claude 以使用当前供应商。')
    return cli_upstream(base)


def launch_cli(args):
    forwarded = args
    # Leave explicit session configuration and native maintenance commands with Claude Code.
    bypass = {'update', 'upgrade', 'install', 'doctor', 'setup-token', 'auth', '--version', '-v', '--help', '-h'}
    overrides = any(a.split('=', 1)[0] in ('--settings', '--setting-sources', '--bare') for a in args)
    state = cli_mode()
    if state != 'direct' and not (set(args[:1]) & bypass or overrides):
        settings = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude') / 'settings.json'
        env = load(settings).get('env', {}) if settings.exists() else {}
        base = env.get('ANTHROPIC_BASE_URL')
        auth = {header: env.get(key) for header, key in CLI_HEADERS.items()}
        if base and any(auth.values()):
            if auth['authorization']:
                auth['authorization'] = 'Bearer ' + auth['authorization']
            ticket = cli_ticket(base, auth)
            healthy, health = probe(PORT, '/_health')
            if not healthy or json.loads(health).get('cli') is not True:
                raise ValueError('CLI 翻译服务暂时不可用。可运行普通 claude 暂时恢复直连。')
            options = {'env': {'ANTHROPIC_BASE_URL': f'http://127.0.0.1:{PORT}/cli/{ticket}'}}
            model = (env.get('ANTHROPIC_MODEL') or '').partition('[')[0]
            display = []
            if CLI_THINKING.fullmatch(model) or model == 'ark-code-latest':
                options['showThinkingSummaries'] = True
                if sys.stdin.isatty() and sys.stdout.isatty() and '-p' not in args and '--print' not in args:
                    options['verbose'] = True
                if not any(a.split('=', 1)[0] == '--thinking-display' for a in args):
                    display = ['--thinking-display', 'summarized']
            forwarded = ['--settings', json.dumps(options), *display]
            forwarded += args
    command = 'claude.exe' if os.name == 'nt' else 'claude'
    native = Path.home() / '.local/bin' / command
    claude = str(native) if native.is_file() else shutil.which(command)
    if not claude:
        raise ValueError('找不到 Claude Code。请先安装原生 CLI，并确认 claude 可以运行。')
    if os.name == 'nt':
        raise SystemExit(subprocess.call([claude, *forwarded]))
    os.execv(claude, [claude, *forwarded])


def set_mode(command):
    path, profile = active_profile()
    previous = profile.get('inferenceGatewayBaseUrl')
    route = route_settings()
    attached = previous == LOCAL_URL
    try:
        healthy, service = probe(PORT, '/_health')
        healthy = healthy and json.loads(service).get('service') == 'claude-offline-translation'
    except (OSError, ValueError, AttributeError):
        healthy = False
    if command == 'status':
        if not attached:
            return '直连 CC Switch'
        if not healthy:
            return '翻译服务未连接'
        return '离线翻译已开启' if route.get('enabled') else '已恢复英文'
    if command == 'direct':
        if not attached:
            return '已经在直连 CC Switch。'
        original = route.get('original')
        local_upstream(original)
        profile['inferenceGatewayBaseUrl'] = original
        write_profile(path, previous, profile['inferenceGatewayBaseUrl'])
        return '已恢复直连设置。退出并重新打开 Claude 后生效。'
    if command == 'off':
        if attached:
            atomic_json(ROUTE, {**route, 'enabled': False})
        return '已恢复英文。发送下一条消息时生效。'
    original = route.get('original') if attached else previous
    upstream_port = local_upstream(original)
    if not healthy:
        raise ValueError('本地翻译服务未启动，Claude 的配置保持原样。')
    ok, _ = probe(upstream_port, '/claude-desktop/v1/models', {'Authorization': 'Bearer ' + cc_key()})
    if not ok:
        raise ValueError('CC Switch 网关没有通过健康检查，Claude 的配置保持原样。')
    if not replay_ready():
        raise ValueError('本机工具回传记录不可写，Claude 的配置保持原样。')
    check_translation()
    atomic_json(ROUTE, {'original': original, 'enabled': True})
    if not attached:
        write_profile(path, previous, LOCAL_URL)
        return '已连接离线翻译。退出并重新打开 Claude 后生效。'
    return '已开启离线翻译。发送下一条消息时生效。'


def write_profile(path, expected, new_url):
    current_path, current = active_profile()
    if current_path != path or current.get('inferenceGatewayBaseUrl') != expected:
        raise ValueError('CC Switch 刚刚更新了配置，请再点一次开关。')
    current['inferenceGatewayBaseUrl'] = new_url
    atomic_json(path, current, stat.S_IMODE(path.stat().st_mode) & 0o600)


def replay_ready():
    try:
        with closing(sqlite3.connect(REPLAY, timeout=3)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS replay (key TEXT PRIMARY KEY, blocks TEXT NOT NULL)')
            db.execute('BEGIN IMMEDIATE')
            db.rollback()
        return True
    except sqlite3.Error:
        return False


def replay_key(ids):
    return hashlib.sha256(json.dumps(sorted(ids), ensure_ascii=False).encode()).hexdigest()


def save_originals(ids, originals):
    with closing(sqlite3.connect(REPLAY, timeout=5)) as db, db:
        db.execute('INSERT OR REPLACE INTO replay VALUES (?, ?)',
                   (replay_key(ids), json.dumps(originals, ensure_ascii=False)))


def restore_originals(body):
    if not REPLAY.exists() or not isinstance(body.get('messages'), list):
        return 0
    restored = 0
    with closing(sqlite3.connect(REPLAY, timeout=5)) as db:
        for message in body['messages']:
            content = message.get('content') if isinstance(message, dict) else None
            if not isinstance(content, list) or message.get('role') != 'assistant':
                continue
            ids = [p['id'] for p in content if isinstance(p, dict) and p.get('type') == 'tool_use'
                   and isinstance(p.get('id'), str)]
            if not ids:
                continue
            row = db.execute('SELECT blocks FROM replay WHERE key=?', (replay_key(ids),)).fetchone()
            if row is None:
                continue
            rebuilt = [p for p in content if not isinstance(p, dict) or p.get('type') not in THOUGHT]
            for index, original in json.loads(row[0]):
                rebuilt.insert(index, original)
                restored += 1
            message['content'] = rebuilt
    return restored


def signature_key(signature):
    return 'signature:' + hashlib.sha256(signature.encode()).hexdigest()


def save_signature(block):
    key = signature_key(block['signature'])
    with closing(sqlite3.connect(REPLAY, timeout=5)) as db, db:
        db.execute('INSERT OR IGNORE INTO replay VALUES (?, ?)', (key, json.dumps(block, ensure_ascii=False)))


def restore_signatures(body):
    if not REPLAY.exists() or not isinstance(body.get('messages'), list):
        return 0
    restored = 0
    with closing(sqlite3.connect(REPLAY, timeout=5)) as db:
        for message in body['messages']:
            if not isinstance(message, dict) or message.get('role') != 'assistant':
                continue
            content = message.get('content')
            if not isinstance(content, list):
                continue
            for index, block in enumerate(content):
                signature = block.get('signature') if isinstance(block, dict) and block.get('type') == 'thinking' else None
                if not isinstance(signature, str) or not signature:
                    continue
                row = db.execute('SELECT blocks FROM replay WHERE key=?', (signature_key(signature),)).fetchone()
                if row:
                    original = json.loads(row[0])
                    if block.get('thinking') != original.get('thinking'):
                        content[index] = original
                        restored += 1
    return restored


def english(text):
    words = WORDS.findall(text)
    # Source text can mix code identifiers with Chinese and English prose.
    return len(words) >= 2 and (not HAN.search(text) or len(words) >= 4)


class TranslationEngine:
    def __init__(self):
        self.worker = None
        self.lock = Lock()

    def translate(self, plain):
        with self.lock:
            try:
                if self.worker is None or self.worker.poll() is not None:
                    self.close()
                    argos = ROOT / 'argos_worker.py'
                    command = [sys.executable, '-X', 'utf8', str(argos)] if argos.is_file() else [ROOT / 'translation-worker']
                    self.worker = subprocess.Popen(command, stdin=subprocess.PIPE,
                                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    self.lines = Queue()
                    Thread(target=self.read, args=(self.worker.stdout, self.lines), daemon=True).start()
                result = self.ask(plain)
                if not isinstance(result, str) or not HAN.search(result):
                    # Terminal punctuation helps the offline model translate fragments.
                    retry = plain if plain[-1:] in '.!?' else plain + '.'
                    result = self.ask(retry)
                return result, 'model kept English'
            except (OSError, ValueError, Empty):
                self.close()
                return None, 'worker unavailable'

    def ask(self, text):
        self.worker.stdin.write((json.dumps(text) + '\n').encode())
        self.worker.stdin.flush()
        return json.loads(self.lines.get(timeout=4))

    @staticmethod
    def read(stdout, lines):
        try:
            for line in stdout:
                lines.put(line)
        except (OSError, ValueError):
            pass
        finally:
            lines.put(b'')

    def close(self):
        if self.worker is not None:
            if self.worker.poll() is None:
                self.worker.kill()
            self.worker.wait()
            self.worker.stdin.close()
            self.worker.stdout.close()
            self.worker = None


ENGINE = TranslationEngine()


def check_translation():
    result, _ = ENGINE.translate('The offline translation is ready.')
    if not isinstance(result, str) or not HAN.search(result):
        raise ValueError('本机离线英译简中暂时不可用。')


class Translator:
    def __init__(self):
        self.count = 0
        self.fallback = {}

    def translate(self, text):
        if not english(text):
            return text
        prefix = text[:len(text) - len(text.lstrip())]
        suffix = text[len(text.rstrip()):]
        result, reason = ENGINE.translate(text.strip())
        if isinstance(result, str) and HAN.search(result):
            self.count += 1
            return prefix + result + suffix
        self.fallback[reason] = self.fallback.get(reason, 0) + 1
        return text


def content_delta(index, text):
    return {'type': 'content_block_delta', 'index': index,
            'delta': {'type': 'thinking_delta', 'thinking': text}}


def split_sentence(text):
    sentence = SENTENCE.search(text)
    if sentence:
        end = sentence.end()
    elif len(text) >= 240:
        end = text.rfind(' ', 135, 240)
        end = end + 1 if end != -1 else 240
    else:
        return '', text
    return text[:end], text[end:]


def supported_model(model, cli, requested):
    if not isinstance(model, str):
        return False
    if cli and model == 'auto' and requested == 'ark-code-latest':
        return True
    return bool((CLI_THINKING if cli else DEEPSEEK).fullmatch(model))


def translated_events(frames, translate, save, cli=False, requested=None):
    originals, tool_ids = [], []
    pending, active = '', None
    supported = False
    for raw, event in frames:
        kind, index = event.get('type'), event.get('index')
        if kind == 'message_start':
            model = event.get('message', {}).get('model', '')
            supported = supported_model(model, cli, requested)
        if not supported:
            yield raw, event
            continue
        if kind == 'content_block_start':
            block = event['content_block']
            if block['type'] == 'thinking':
                originals.append((index, copy.deepcopy(block)))
                active, pending = index, block.get('thinking', '')
                start = {'type': 'thinking', 'thinking': ''}
                if cli:
                    start['signature'] = ''
                yield None, {**event, 'content_block': start}
                continue
            if block['type'] == 'redacted_thinking':
                originals.append((index, copy.deepcopy(block)))
            if block['type'] == 'tool_use':
                tool_ids.append(block['id'])
        if active is not None and index == active:
            original = originals[-1][1]
            if kind == 'content_block_delta':
                delta = event['delta']
                if delta['type'] == 'signature_delta':
                    original['signature'] = original.get('signature', '') + delta['signature']
                    continue
                if delta['type'] == 'thinking_delta':
                    original['thinking'] = original.get('thinking', '') + delta['thinking']
                    pending += delta['thinking']
                    while True:
                        sentence, pending = split_sentence(pending)
                        if not sentence:
                            break
                        yield None, content_delta(index, translate(sentence))
                    continue
            if kind == 'content_block_stop':
                if pending:
                    yield None, content_delta(index, translate(pending))
                if cli and original.get('signature'):
                    # CLI histories may retain thinking even in an assistant turn without a tool.
                    save_signature(original)
                    yield None, {'type': 'content_block_delta', 'index': index, 'delta': {
                        'type': 'signature_delta', 'signature': original['signature']}}
                pending, active = '', None
        if kind in ('message_delta', 'message_stop') and tool_ids and originals and active is None:
            save(tool_ids, originals)
            originals = []
        yield raw, event


def upstream_frames(response):
    lines = []
    for line in response:
        if line.strip():
            lines.append(line)
            continue
        yield parse_frame(lines + [line])
        lines = []
    if lines:
        yield parse_frame(lines)


def parse_frame(lines):
    data = b'\n'.join(line[5:].lstrip(b' ').rstrip(b'\r\n') for line in lines if line.startswith(b'data:'))
    try:
        event = json.loads(data) if data else {}
        return b''.join(lines), event if isinstance(event, dict) else {}
    except ValueError:
        return b''.join(lines), {}


def serialize(event):
    return (f'event: {event["type"]}\ndata: ' + json.dumps(event, ensure_ascii=False) + '\n\n').encode()


def translate_response(payload, translate, cli=False, requested=None):
    message = json.loads(payload)
    if not isinstance(message, dict) or not supported_model(message.get('model'), cli, requested):
        return payload
    blocks = message.get('content')
    if not isinstance(blocks, list):
        return payload
    all_originals = [(i, copy.deepcopy(p)) for i, p in enumerate(blocks) if p.get('type') in THOUGHT]
    thought = [(i, p) for i, p in enumerate(blocks) if p.get('type') == 'thinking']
    ids = [p['id'] for p in blocks if p.get('type') == 'tool_use']
    if not thought:
        return payload
    for index, block in thought:
        blocks[index] = {'type': 'thinking', 'thinking': translate(block.get('thinking', ''))}
        if cli and block.get('signature'):
            save_signature(block)
            blocks[index]['signature'] = block['signature']
    if ids:
        save_originals(ids, all_originals)
    return json.dumps(message, ensure_ascii=False).encode()


class Relay(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def direct_reply(self, status, body):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def gateway_error(self, status, message):
        self.direct_reply(status, json.dumps({'type': 'error', 'error': {
            'type': 'api_error', 'message': message}}, ensure_ascii=False).encode())

    def do_GET(self):
        if self.path == '/_panel' and PANEL.is_file():
            self.show_panel()
            return
        if self.path == '/_health':
            credential = self.headers.get('X-Translation-Service-Key')
            if credential is not None and not self.is_manager(credential):
                self.gateway_error(403, 'Forbidden')
                return
            self.direct_reply(200, b'{"service":"claude-offline-translation","cli":true}')
            return
        self.forward()

    def do_POST(self):
        if self.path == '/_panel' and PANEL.is_file():
            self.change_panel()
            return
        if self.path == '/_shutdown':
            if not self.is_manager(self.headers.get('X-Translation-Service-Key', '')):
                self.gateway_error(403, 'Forbidden')
                return
            self.direct_reply(200, b'{}')
            self.server.shutdown()
            return
        self.forward()

    def show_panel(self, notice='', status=200):
        if self.headers.get('Host') != f'127.0.0.1:{PORT}':
            self.gateway_error(403, 'Forbidden')
            return
        try:
            desktop_status = set_mode('status')
        except (OSError, ValueError, AttributeError):
            desktop_status = '未找到可用的 Desktop Gateway 配置'
        try:
            cli_status = set_cli_mode('status')
        except (OSError, ValueError, KeyError):
            cli_status = '无法读取 CLI 状态'
        args = [sys.executable, str(ROOT / 'install.py'), 'claude']
        launch = '& ' + ' '.join("'" + arg.replace("'", "''") + "'" for arg in args) if os.name == 'nt' else shlex.join(args)
        page = Template(PANEL.read_text(encoding='utf-8')).substitute(
            desktop_status=escape(desktop_status), cli_status=escape(cli_status),
            notice=escape(notice), csrf=PANEL_CSRF, launch_command=escape(launch),
        ).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(page)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(page)

    def change_panel(self):
        if (self.headers.get('Host') != f'127.0.0.1:{PORT}' or self.headers.get('Origin') != ORIGIN
                or self.headers.get_content_type() != 'application/x-www-form-urlencoded'
                or self.headers.get('Transfer-Encoding')):
            self.gateway_error(403, 'Forbidden')
            return
        length = self.headers.get('Content-Length', '')
        if not re.fullmatch(r'[0-9]{1,3}', length):
            self.gateway_error(400, 'Invalid form')
            return
        self.connection.settimeout(5)
        try:
            fields = parse_qs(self.rfile.read(int(length)).decode('ascii'), strict_parsing=True, max_num_fields=2)
        except (ValueError, TimeoutError):
            self.gateway_error(400, 'Invalid form')
            return
        csrf, = fields['csrf'] if len(fields.get('csrf', [])) == 1 else ('',)
        if not hmac.compare_digest(csrf.encode(), PANEL_CSRF.encode()):
            self.gateway_error(403, 'Forbidden')
            return
        actions = fields.get('action', [])
        if len(actions) != 1 or not re.fullmatch(r'(desktop|cli)-(on|off|direct)', actions[0]):
            self.gateway_error(400, 'Invalid operation')
            return
        target, command = actions[0].split('-')
        with PANEL_LOCK:
            try:
                notice = (set_mode if target == 'desktop' else set_cli_mode)(command)
            except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError, AttributeError, KeyError) as error:
                self.show_panel(str(error), 409)
                return
            self.show_panel(notice)

    def is_manager(self, credential):
        return SERVICE_KEY.is_file() and hmac.compare_digest(credential.encode(), SERVICE_KEY.read_bytes())

    def forward(self):
        path = urlsplit(self.path)
        cli = path.path.startswith('/cli/')
        if path.scheme or path.netloc or not (cli or path.path.startswith('/claude-desktop/v1/')):
            self.gateway_error(404, 'Gateway endpoint not found.')
            return
        outgoing = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        body = requested = None
        try:
            if cli:
                _, _, ticket, endpoint = path.path.split('/', 3)
                if any(part in ('.', '..') for part in unquote(endpoint).split('/')) or '\\' in unquote(endpoint):
                    raise ValueError('无效的 CLI 网关路径。')
                target = cli_target(ticket, self.headers)
                upstream_path = target.path.rstrip('/') + '/' + endpoint
                if path.query:
                    upstream_path += '?' + path.query
                messages = self.command == 'POST' and endpoint == 'v1/messages'
                valid = messages
                enabled = cli_mode() == 'on'
            else:
                route = route_settings()
                port = local_upstream(route.get('original'))
                target = urlsplit(f'http://127.0.0.1:{port}')
                upstream_path = self.path
                messages = self.command == 'POST' and path.path == '/claude-desktop/v1/messages'
                token = self.headers.get('Authorization', '').strip()
                token = re.sub('^Bearer ', '', token, flags=re.I) if token else self.headers.get('x-api-key', '').strip()
                expected = cc_key() if token and messages else ''
                valid = bool(expected and hmac.compare_digest(token.encode(), expected.encode()))
                enabled = bool(route.get('enabled'))
            length = int(self.headers.get('Content-Length', '0'))
            if self.headers.get('Transfer-Encoding') or not 0 <= length <= 200 * 1024 * 1024:
                self.gateway_error(400, 'Invalid gateway request length.')
                return
            self.connection.settimeout(180)
            if length:
                body = self.rfile.read(length)
            if valid and body and not self.headers.get('Content-Encoding'):
                data = json.loads(body)
                requested = data.get('model')
                restored = restore_originals(data)
                if cli:
                    restored += restore_signatures(data)
                if restored:
                    body = json.dumps(data, ensure_ascii=False).encode()
                    print(f'{"CLI " if cli else ""}Tool replay: restored {restored} original blocks.', flush=True)
            translation = valid and enabled and not self.headers.get('Content-Encoding') and replay_ready()
        except PermissionError as error:
            self.gateway_error(401, str(error))
            return
        except (OSError, ValueError, sqlite3.Error):
            self.gateway_error(502, '本地网关暂时不可用。请检查 CC Switch 或打开翻译工具恢复直连。')
            return
        connection = http.client.HTTPSConnection if target.scheme == 'https' else http.client.HTTPConnection
        conn = connection(target.hostname, target.port, timeout=180)
        translator = Translator()
        headers_sent = False
        try:
            conn.request(self.command, upstream_path, body, outgoing)
            response = conn.getresponse()
            mime = response.getheader('Content-Type', '')
            change = response.status == 200 and translation and not response.getheader('Content-Encoding')
            streaming = 'text/event-stream' in mime
            payload = None
            if change and not streaming and 'json' in mime:
                payload = translate_response(response.read(), translator.translate, cli, requested)
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in HOP and not (change and key.lower() in ('etag', 'content-md5')):
                    self.send_header(key, value)
            if payload is not None:
                self.send_header('Content-Length', str(len(payload)))
            elif not (streaming and change) and response.length is not None:
                self.send_header('Content-Length', str(response.length))
            self.end_headers()
            headers_sent = True
            if payload is not None:
                self.wfile.write(payload)
            elif streaming and change:
                frames = upstream_frames(response)
                for raw, event in translated_events(frames, translator.translate, save_originals, cli, requested):
                    self.wfile.write(raw if raw is not None else serialize(event))
                    self.wfile.flush()
            else:
                while True:
                    data = response.read1(65536)
                    if not data:
                        break
                    self.wfile.write(data)
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (OSError, http.client.HTTPException, ValueError, sqlite3.Error):
            if not headers_sent:
                self.gateway_error(502, '接不到 CLI 当前供应商。' if cli else '接不到 CC Switch。请确认 CC Switch 的本地网关已启动。')
            elif streaming and change:
                self.wfile.write(serialize({'type': 'error', 'error': {
                    'type': 'api_error', 'message': '本地翻译连接中断。可在翻译工具中恢复英文后重试。'}}))
        finally:
            if translator.count or translator.fallback:
                print(f'{"CLI " if cli else ""}Thinking segments: {translator.count} translated. Fallbacks: {translator.fallback}.', flush=True)
            conn.close()


def self_test():
    global REPLAY, CLI_KEY
    with tempfile.TemporaryDirectory() as directory:
        REPLAY = Path(directory) / 'private.sqlite3'
        assert replay_ready()
        def wire(e):
            return serialize(e), e
        original = {'type': 'thinking', 'thinking': 'First sentence. Second sentence.', 'signature': 'originalsignature'}
        tool = {'type': 'tool_use', 'id': 'example', 'name': 'echo', 'input': {}}
        events = [
            {'type': 'message_start', 'message': {'model': 'deepseek-v4-1-flash-261017'}},
            {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'thinking', 'thinking': ''}},
            content_delta(0, 'First sentence. Sec'), content_delta(0, 'ond sentence.'),
            {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'signature_delta', 'signature': 'originalsignature'}},
            {'type': 'content_block_stop', 'index': 0},
            {'type': 'content_block_start', 'index': 1, 'content_block': tool},
            {'type': 'content_block_stop', 'index': 1},
            {'type': 'message_delta', 'delta': {'stop_reason': 'tool_use'}},
            {'type': 'message_stop'},
        ]
        rows = list(translated_events(map(wire, events), lambda _: '中文。', save_originals))
        thoughts = [e['delta']['thinking'] for _, e in rows if e.get('delta', {}).get('type') == 'thinking_delta']
        assert thoughts == ['中文。', '中文。']
        assert not any(e.get('delta', {}).get('type') == 'signature_delta' for _, e in rows)
        assert (serialize(events[6]), events[6]) in rows
        body = {'messages': [{'role': 'assistant', 'content': [{'type': 'redacted_thinking', 'data': 'ignored'}, tool]}]}
        assert restore_originals(body) == 1 and body['messages'][0]['content'] == [original, tool]
        assert restore_originals(body) == 1 and body['messages'][0]['content'] == [original, tool]
        events[0]['message']['model'] = 'another-provider'
        assert list(translated_events(map(wire, events), lambda _: '中文。', save_originals)) == list(map(wire, events))
        payload = b': ping\r\nevent: ping\r\ndata: {"type":"ping"}\r\n\r\n'
        assert parse_frame(payload.splitlines(keepends=True)) == (payload, {'type': 'ping'})
        if os.name != 'nt':
            assert REPLAY.stat().st_mode & 0o077 == 0
        CLI_KEY = Path(directory) / 'key'
        CLI_KEY.write_bytes(secrets.token_bytes(32))
        headers = {'authorization': 'Bearer test-auth'}
        ticket = cli_ticket('https://service.example/prefix', headers)
        assert cli_target(ticket, headers).path == '/prefix'
        for bad_ticket, bad_headers in ((ticket + 'x', headers), (ticket, {})):
            try:
                cli_target(bad_ticket, bad_headers)
            except PermissionError:
                pass
            else:
                raise AssertionError('accepted a wrong CLI route or credential')
        events[0]['message']['model'] = 'glm-5.3-flash'
        rows = list(translated_events(map(wire, events[:6] + events[-2:]), lambda _: '中文。', save_originals, cli=True))
        assert any(e.get('delta', {}).get('signature') == original['signature'] for _, e in rows)
        body = {'messages': [{'role': 'assistant', 'content': [{**original, 'thinking': '中文。'}]}]}
        assert restore_signatures(body) == 1 and body['messages'][0]['content'] == [original]
        assert supported_model('auto', True, 'ark-code-latest') and not supported_model('auto', False, 'ark-code-latest')
        assert not supported_model('auto', True, 'unknown-model')
    print('SSE, passthrough, signed CLI routing and tool replay passed.')


if __name__ == '__main__':
    os.umask(0o077)
    try:
        command = sys.argv[1]
        if command == 'serve':
            if not replay_ready():
                raise ValueError('无法初始化工具回传记录。')
            ENGINE.translate('The local offline translation service is ready.')
            try:
                with ThreadingHTTPServer(('127.0.0.1', PORT), Relay) as server:
                    server.serve_forever()
            finally:
                ENGINE.close()
        elif command == 'self-test':
            self_test()
        elif command == 'check-translation':
            try:
                check_translation()
                print('离线英译简中自检通过。')
            finally:
                ENGINE.close()
        elif command == 'check-detached':
            check_detached()
        elif command in ('status', 'on', 'off', 'direct'):
            print(set_mode(command))
        elif command in ('cli-status', 'cli-on', 'cli-off', 'cli-direct'):
            print(set_cli_mode(command[4:]))
        elif command == 'cli-launch':
            launch_cli(sys.argv[2:])
        else:
            raise ValueError('未知操作。')
    except (OSError, ValueError, subprocess.SubprocessError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
