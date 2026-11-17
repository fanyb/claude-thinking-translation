"""Exercise a fresh Argos install and both gateway paths with a synthetic provider."""
from contextlib import closing
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
from threading import Thread
from urllib.parse import urlencode

from gateway import PORT, LOCAL_URL, serialize


ORIGINAL = {'type': 'thinking', 'thinking': 'The violet squirrel crossed the bridge.', 'signature': 'synthetic-signature'}
TOOL = {'type': 'tool_use', 'id': 'synthetic-tool', 'name': 'Bash', 'input': {}}
STREAM = [
    {'type': 'message_start', 'message': {'model': 'deepseek-v4-1-flash-261017'}},
    {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'thinking', 'thinking': ''}},
    {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'thinking_delta', 'thinking': ORIGINAL['thinking']}},
    {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'signature_delta', 'signature': ORIGINAL['signature']}},
    {'type': 'content_block_stop', 'index': 0},
    {'type': 'content_block_start', 'index': 1, 'content_block': TOOL},
    {'type': 'content_block_stop', 'index': 1},
    {'type': 'message_delta', 'delta': {'stop_reason': 'tool_use'}},
    {'type': 'message_stop'},
]
TOKEN = 'synthetic-test-key'
AUTH = {'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'}
SOURCE = Path(__file__).resolve().parent


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, mime, raw, status=200):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        assert self.path == '/claude-desktop/v1/models' and self.headers['Authorization'] == AUTH['Authorization']
        self.respond('application/json', b'{"data":[]}')

    def do_POST(self):
        assert self.path in ('/v1/messages', '/claude-desktop/v1/messages')
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if data.get('messages'):
            correct = data['messages'][0]['content'] == [ORIGINAL, TOOL]
            self.respond('text/event-stream', serialize(STREAM[-1]), 200 if correct else 400)
        else:
            self.respond('text/event-stream', b''.join(map(serialize, STREAM)))


def run_tests(home, upstream):
    local_data = home / 'Local Data'
    roaming_data = home / 'Roaming Data'
    data = home / 'XDG Data'
    config = home / 'XDG Config'
    env = {**os.environ, 'HOME': str(home), 'USERPROFILE': str(home), 'LOCALAPPDATA': str(local_data),
           'APPDATA': str(roaming_data), 'XDG_DATA_HOME': str(data), 'XDG_CONFIG_HOME': str(config)}

    def run(*args, check=True, output=False):
        return subprocess.run([sys.executable, '-X', 'utf8', str(SOURCE / 'install.py'), *args], env=env,
                              check=check, stdout=subprocess.PIPE if output else None, text=True, encoding='utf-8')

    def post(endpoint, body=None):
        with closing(HTTPConnection('127.0.0.1', PORT, timeout=20)) as connection:
            connection.request('POST', endpoint, body=json.dumps(body or {}), headers=AUTH)
            response = connection.getresponse()
            assert response.status == 200, response.read()
            return [json.loads(line[6:]) for line in response if line.startswith(b'data: ')]

    def panel(action=None, origin=f'http://127.0.0.1:{PORT}', token=None, **headers):
        with closing(HTTPConnection('127.0.0.1', PORT, timeout=20)) as connection:
            if action is None:
                connection.request('GET', '/_panel', headers=headers)
            else:
                connection.request('POST', '/_panel', urlencode({'csrf': token or csrf, 'action': action}),
                                   {'Origin': origin, 'Content-Type': 'application/x-www-form-urlencoded', **headers})
            response = connection.getresponse()
            return response.status, response.read().decode('utf-8')

    library = (local_data if os.name == 'nt' else config) / 'Claude-3p/configLibrary'
    library.mkdir(parents=True)
    profile_id = 'aa322685-7146-4094-84a0-8742a2cc02ab'
    (library / '_meta.json').write_text(json.dumps({'appliedId': profile_id}), encoding='utf-8')
    path = library / f'{profile_id}.json'
    previous = {'inferenceProvider': 'gateway', 'inferenceGatewayBaseUrl': f'{upstream}/claude-desktop', 'unrelated': True}
    path.write_text(json.dumps(previous), encoding='utf-8')
    cc = home / '.cc-switch'
    cc.mkdir()
    with sqlite3.connect(cc / 'cc-switch.db') as db:
        db.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)')
        db.execute('INSERT INTO settings VALUES (?, ?)', ('claude_desktop_gateway_token', TOKEN))
    db.close()
    db_before = (cc / 'cc-switch.db').read_bytes()
    runtime = (local_data if os.name == 'nt' else data) / 'claude-thinking-translation'
    python = runtime / ('venv/Scripts/python.exe' if os.name == 'nt' else 'venv/bin/python')

    run('install', '--no-open')
    try:
        run('check')
        assert json.loads(path.read_text(encoding='utf-8')) == previous
        assert not (runtime / 'cli.json').exists()
        if os.name == 'nt':
            assert list(roaming_data.glob('**/Claude 思考翻译.lnk'))
        else:
            shortcut = data / 'applications/claude-thinking-translation.desktop'
            assert 'install.py" panel' in shortcut.read_text(encoding='utf-8')
        status, html = panel()
        assert status == 200 and '直连 CC Switch' in html and '直连当前供应商' in html
        csrf = re.search(r'name="csrf" value="([^"]+)"', html)[1]
        assert panel(Host='untrusted.example')[0] == 403
        assert panel('desktop-on', origin='https://untrusted.example')[0] == 403
        assert panel('desktop-on', token='wrong')[0] == 403
        assert panel('uninstall')[0] == 400
        assert json.loads(path.read_text(encoding='utf-8')) == previous
        with closing(HTTPConnection('127.0.0.1', PORT, timeout=5)) as connection:
            connection.request('POST', '/_shutdown')
            response = connection.getresponse()
            assert response.status == 403
            response.read()

        status, html = panel('desktop-on')
        assert status == 200 and '已连接离线翻译' in html
        assert json.loads(path.read_text(encoding='utf-8'))['inferenceGatewayBaseUrl'] == LOCAL_URL
        assert run('uninstall', check=False).returncode != 0
        assert panel('cli-on')[0] == 200
        code = '''import sys, json, gateway
gateway.os.execv = lambda exe, args: print(json.loads(args[2])['env']['ANTHROPIC_BASE_URL'].split('/cli/')[1])
def fake_call(args):
    gateway.os.execv(None, args)
    return 0
gateway.subprocess.call = fake_call
gateway.launch_cli(['--model', 'deepseek-v4-1-flash-261017'])
'''
        binary = home / '.local/bin' / ('claude.exe' if os.name == 'nt' else 'claude')
        binary.parent.mkdir(parents=True)
        binary.touch()
        settings = home / '.claude/settings.json'
        settings.parent.mkdir()
        settings.write_text(json.dumps({'env': {'ANTHROPIC_BASE_URL': upstream, 'ANTHROPIC_AUTH_TOKEN': TOKEN,
                                                 'ANTHROPIC_MODEL': 'deepseek-v4-1-flash-261017'}}), encoding='utf-8')
        ticket = subprocess.check_output([python, '-X', 'utf8', '-c', code], cwd=runtime, env=env, text=True).strip()

        for prefix, mode in (('/claude-desktop', 'desktop'), ('/cli/' + ticket, 'cli')):
            endpoint = prefix + '/v1/messages'
            events = post(endpoint)
            translated = ''.join(e['delta']['thinking'] for e in events if e.get('delta', {}).get('type') == 'thinking_delta')
            assert re.search(r'[\u3400-\u9fff]', translated)
            assert TOOL in [e.get('content_block') for e in events]
            assert any(e.get('delta', {}).get('signature') == ORIGINAL['signature'] for e in events) == (mode == 'cli')
            replay = {'messages': [{'role': 'assistant', 'content': [{**ORIGINAL, 'thinking': translated}, TOOL]}]}
            assert post(endpoint, replay) == STREAM[-1:]
            assert panel(mode + '-off')[0] == 200
            assert post(endpoint) == STREAM
            assert post(endpoint, replay) == STREAM[-1:]
            assert panel(mode + '-direct')[0] == 200

        assert json.loads(path.read_text(encoding='utf-8')) == previous
        assert (cc / 'cc-switch.db').read_bytes() == db_before
    finally:
        run('desktop-direct', check=False)
        run('uninstall')
    assert not runtime.exists()
    assert not list(home.glob('**/claude-thinking-translation.desktop'))
    assert not list(home.glob('**/claude-thinking-translation.lnk'))
    assert not list(home.glob('**/Claude 思考翻译.lnk'))
    print('Fresh install, offline translation, Desktop and CLI tool replay, restore, and uninstall passed.')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='ctt-test-') as temp, ThreadingHTTPServer(('127.0.0.1', 0), Upstream) as provider:
        Thread(target=provider.serve_forever, daemon=True).start()
        try:
            run_tests(Path(temp), f'http://127.0.0.1:{provider.server_port}')
        finally:
            provider.shutdown()
