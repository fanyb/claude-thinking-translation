"""Worker recovery and managed launchers without a live provider."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import gateway


class ModelTranslation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.replay = patch.object(gateway, 'REPLAY', Path(self.temp.name) / 'replay.sqlite3')
        self.replay.start()
        self.assertTrue(gateway.replay_ready())

    def tearDown(self):
        self.replay.stop()
        self.temp.cleanup()

    def test_visible_thinking_does_not_depend_on_model_names(self):
        for cli in (False, True):
            for model in ('glm-5.4', 'glm-5.3-flash', 'deepseek-v4-1-flash-261017',
                          'doubao-seed-2-1-pro', 'kimi-k3.1-pro', 'gpt-5.6', 'o3',
                          'claude-sonnet-5', 'auto', 'future-unknown-model', None):
                with self.subTest(cli=cli, model=model):
                    payload = json.dumps({'model': model, 'content': [
                        {'type': 'thinking', 'thinking': 'Check the result.'}]}).encode()
                    result = json.loads(gateway.translate_response(payload, lambda _: '检查结果。', cli))
                    self.assertEqual(result['content'][0]['thinking'], '检查结果。')

    def test_glm54_stream_translates_before_tool_and_preserves_replay(self):
        original = {'type': 'thinking', 'thinking': '', 'signature': ''}
        tool = {'type': 'tool_use', 'id': 'tool-test', 'name': 'Bash', 'input': {'command': 'pwd'}}
        events = [
            {'type': 'message_start', 'message': {'model': 'glm-5.4'}},
            {'type': 'content_block_start', 'index': 0, 'content_block': original},
            gateway.content_delta(0, 'Check the current directory. '),
            {'type': 'content_block_delta', 'index': 0,
             'delta': {'type': 'signature_delta', 'signature': 'original-signature'}},
            {'type': 'content_block_stop', 'index': 0},
            {'type': 'content_block_start', 'index': 1, 'content_block': tool},
            {'type': 'content_block_stop', 'index': 1},
            {'type': 'message_delta', 'delta': {'stop_reason': 'tool_use'}},
        ]
        for cli in (False, True):
            saved = []
            with patch.object(gateway, 'save_signature') as signature:
                rows = list(gateway.translated_events([(b'original', e) for e in events],
                            lambda text: '检查当前目录。 ', lambda *args: saved.append(args), cli))
            translated = [e for _, e in rows if e.get('delta', {}).get('type') == 'thinking_delta']
            self.assertEqual(translated[0]['delta']['thinking'], '检查当前目录。 ')
            self.assertLess([e for _, e in rows].index(translated[0]),
                            next(i for i, (_, e) in enumerate(rows) if e.get('content_block') == tool))
            self.assertEqual(saved, [(['tool-test'], [(0, {'type': 'thinking',
                             'thinking': 'Check the current directory. ', 'signature': 'original-signature'})])])
            self.assertEqual(signature.call_count, 1)

    def test_json_preserves_signature_and_restores_original_without_tool(self):
        for cli in (False, True):
            for model in ('glm-5.4', 'claude-sonnet-5', 'gpt-5.6'):
                original = {'type': 'thinking', 'thinking': 'Check the result.', 'signature': 'sig',
                            'encrypted_content': 'opaque-context'}
                payload = json.dumps({'model': model, 'content': [
                    original,
                    {'type': 'text', 'text': 'Answer stays unchanged.'}]}).encode()
                result = json.loads(gateway.translate_response(payload, lambda text: '检查结果。', cli))
                self.assertEqual(result['content'][0], {**original, 'thinking': '检查结果。'})
                self.assertEqual(result['content'][1]['text'], 'Answer stays unchanged.')
                body = {'messages': [{'role': 'assistant', 'content': result['content']}]}
                self.assertEqual(gateway.restore_signatures(body), 1)
                self.assertEqual(body['messages'][0]['content'][0], original)

    def test_reused_signatures_do_not_mix_different_thinking(self):
        for source, translated in [('First original.', '第一段。'), ('Second original.', '第二段。')]:
            gateway.save_signature({'type': 'thinking', 'thinking': source, 'signature': 'shared'}, translated)
        for source, translated in [('First original.', '第一段。'), ('Second original.', '第二段。')]:
            body = {'messages': [{'role': 'assistant', 'content': [
                {'type': 'thinking', 'thinking': translated, 'signature': 'shared'}]}]}
            self.assertEqual(gateway.restore_signatures(body), 1)
            self.assertEqual(body['messages'][0]['content'][0]['thinking'], source)

    def test_old_signature_cache_still_restores_existing_histories(self):
        original = {'type': 'thinking', 'thinking': 'Old source.', 'signature': 'old-sig'}
        with closing(sqlite3.connect(gateway.REPLAY)) as db, db:
            db.execute('INSERT INTO replay VALUES (?, ?)',
                       (gateway.signature_key('old-sig'), json.dumps(original)))
        body = {'messages': [{'role': 'assistant', 'content': [{**original, 'thinking': '旧译文。'}]}]}
        self.assertEqual(gateway.restore_signatures(body), 1)
        self.assertEqual(body['messages'][0]['content'], [original])

    def test_opaque_and_text_only_responses_are_not_translated(self):
        for blocks in ([{'type': 'thinking', 'thinking': '', 'signature': 'ccswitch-openai-reasoning-v1:opaque'}],
                       [{'type': 'redacted_thinking', 'data': 'encrypted-context'}],
                       [{'type': 'text', 'text': 'English final answer.'}]):
            payload = json.dumps({'model': 'unknown', 'content': blocks}).encode()
            with patch.object(gateway.ENGINE, 'translate') as translate:
                result = json.loads(gateway.translate_response(payload, gateway.Translator().translate))
                translate.assert_not_called()
            self.assertEqual(result['content'], blocks)

    def test_text_only_stream_is_passed_through_byte_for_byte(self):
        events = [{'type': 'message_start', 'message': {'model': 'unknown'}},
                  {'type': 'content_block_start', 'index': 0,
                   'content_block': {'type': 'text', 'text': 'English answer.'}},
                  {'type': 'message_stop'}]
        frames = [(gateway.serialize(e), e) for e in events]
        self.assertEqual(list(gateway.translated_events(frames, lambda _: self.fail('translated text'),
                                                       lambda *_: self.fail('cached text'))), frames)


class OrcaLauncher(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'ORCA_STRUCTURED_SESSION': '1', 'ORCA_AGENT_SESSION_ID': 'test-session'})
        self.env.start()
        self.args = ['--output-format', 'stream-json', '--setting-sources=user,project,local',
                     '--settings', '{"fastMode":false}', '--resume=test-session']

    def tearDown(self):
        self.env.stop()

    def test_preserves_orca_settings_and_session_flags(self):
        self.assertEqual(gateway.orca_launch_settings(self.args),
                         ({'fastMode': False}, self.args[:3] + self.args[5:]))

    def test_explicit_overrides_and_bad_settings_are_untouched(self):
        for value in ('{"env":{"ANTHROPIC_BASE_URL":"https://override.example"}}',
                      '{"fastMode":"false"}', '[]', 'not-json'):
            with self.subTest(value=value):
                self.assertIsNone(gateway.orca_launch_settings(self.args[:4] + [value]))
        for args in (self.args + ['--bare'], self.args + ['--settings', '{}'],
                     ['--setting-sources=project,local', *self.args[3:]], self.args[:4]):
            with self.subTest(args=args):
                self.assertIsNone(gateway.orca_launch_settings(args))

    def test_only_orca_structured_sessions_are_recognized(self):
        with patch.dict(os.environ, ORCA_STRUCTURED_SESSION='0'):
            self.assertIsNone(gateway.orca_launch_settings(self.args))

    def test_launcher_routes_orca_and_preserves_native_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            settings = home / 'settings.json'
            settings.write_text(json.dumps({'env': {'ANTHROPIC_BASE_URL': 'https://provider.example',
                                                    'ANTHROPIC_AUTH_TOKEN': 'test-auth',
                                                    'ANTHROPIC_MODEL': 'unknown-default'}}), encoding='utf-8')
            native = home / '.local/bin' / ('claude.exe' if os.name == 'nt' else 'claude')
            native.parent.mkdir(parents=True)
            native.touch()
            with patch.object(Path, 'home', return_value=home), \
                 patch.dict(os.environ, CLAUDE_CONFIG_DIR=directory), \
                 patch.object(gateway, 'cli_mode', return_value='on'), \
                 patch.object(gateway, 'cli_ticket', return_value='test-ticket'), \
                 patch.object(gateway, 'probe', return_value=(True, '{"cli":true}')), \
                 patch.object(gateway.os, 'execv') as execute, \
                 patch.object(gateway.subprocess, 'call', return_value=0) as call:
                if os.name == 'nt':
                    with self.assertRaises(SystemExit):
                        gateway.launch_cli([*self.args, '--model=glm-5.4[1m]'])
                    forwarded = call.call_args.args[0]
                else:
                    gateway.launch_cli([*self.args, '--model=glm-5.4[1m]'])
                    forwarded = execute.call_args.args[1]
                self.assertEqual(forwarded.count('--settings'), 1)
                options = json.loads(forwarded[2])
                self.assertIs(options['fastMode'], False)
                self.assertIs(options['showThinkingSummaries'], True)
                self.assertEqual(forwarded[forwarded.index('--thinking-display') + 1], 'summarized')
                self.assertIn('--model=glm-5.4[1m]', forwarded)
                self.assertEqual(options['env']['ANTHROPIC_BASE_URL'],
                                 f'http://127.0.0.1:{gateway.PORT}/cli/test-ticket')
                self.assertIn('--setting-sources=user,project,local', forwarded)
                self.assertIn('--resume=test-session', forwarded)


class WorkerRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.engine = gateway.TranslationEngine()
        self.root_patch = patch.object(gateway, 'ROOT', self.root)
        self.root_patch.start()

    def tearDown(self):
        self.engine.close()
        self.root_patch.stop()
        self.temp.cleanup()

    def worker(self, first):
        (self.root / 'argos_worker.py').write_text(
            'import json, pathlib, sys\n'
            'p = pathlib.Path(__file__).with_name("starts")\n'
            'n = int(p.read_text()) + 1 if p.exists() else 1\n'
            'p.write_text(str(n))\n'
            'for line in sys.stdin:\n'
            ' text = json.loads(line)\n'
            f' if n == 1:\n  {first}\n'
            ' print(json.dumps("翻译成功。"), flush=True)\n', encoding='utf-8')

    def starts(self):
        return int((self.root / 'starts').read_text())

    def test_english_output_rebuilds_and_retries_current_segment(self):
        self.worker('print(json.dumps(text), flush=True); continue')
        self.assertEqual(self.engine.translate('Check the result'), ('翻译成功。', ''))
        self.assertEqual(self.starts(), 2)
        self.assertEqual(self.engine.translate('Continue the task.'), ('翻译成功。', ''))
        self.assertEqual(self.starts(), 2)

    def test_crashed_worker_retries_current_segment(self):
        self.worker('sys.exit(1)')
        self.assertEqual(self.engine.translate('Check the result.'), ('翻译成功。', ''))
        self.assertEqual(self.starts(), 2)

    def test_malformed_output_retries_current_segment(self):
        self.worker('print("broken-json", flush=True); continue')
        self.assertEqual(self.engine.translate('Check the result.'), ('翻译成功。', ''))
        self.assertEqual(self.starts(), 2)

    def test_timeout_rebuilds_worker(self):
        self.worker('pass')
        with patch.object(self.engine, 'ask', side_effect=[gateway.Empty(), '翻译成功。']):
            self.assertEqual(self.engine.translate('Check the result.'), ('翻译成功。', ''))
        self.assertIsNotNone(self.engine.worker)

    def test_persistent_failure_is_bounded_and_keeps_source(self):
        self.worker('print(json.dumps(text), flush=True); continue')
        worker = self.root / 'argos_worker.py'
        worker.write_text(worker.read_text(encoding='utf-8').replace('if n == 1:', 'if True:'), encoding='utf-8')
        with patch.object(gateway, 'ENGINE', self.engine):
            translator = gateway.Translator()
            self.assertEqual(translator.translate('Check the result.'), 'Check the result.')
            self.assertEqual(translator.fallback, {'model kept English': 1})
        self.assertEqual(self.starts(), 2)
        self.assertIsNone(self.engine.worker)


if __name__ == '__main__':
    unittest.main()
