"""Worker recovery without a model download or a live provider."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gateway


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
