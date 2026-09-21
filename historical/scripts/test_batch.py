import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import batch


class BatchTests(unittest.TestCase):
    def exercise(self, first_state):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'records').mkdir()
            (root / 'runs').mkdir()
            (root / 'study.json').write_text(json.dumps({'measured_repetitions': 3}))
            launched = []
            class Child:
                pid = 123
                def __init__(self, argv, **kwargs):
                    self.name = argv[-1]
                    launched.append(self.name)
                def wait(self, **kwargs):
                    path = root / 'runs' / self.name
                    path.mkdir()
                    state = first_state if self.name == 'measured-001' else 'completed'
                    (path / 'manifest.json').write_text(json.dumps({'state': state}))
                    return 0
                def poll(self):
                    return 0
            with patch.object(batch, 'ROOT', root), patch.object(batch, 'verify', return_value='frozen'), patch.object(batch, 'audit', return_value={'passed': True}), patch.object(batch.subprocess, 'Popen', Child), patch.object(batch.signal, 'signal'), patch('builtins.print'):
                batch.main()
            return launched, json.loads((root / 'records/batch-state.json').read_text())

    def test_three_serial_fresh_attempts(self):
        launched, state = self.exercise('completed')
        self.assertEqual(launched, ['measured-001', 'measured-002', 'measured-003'])
        self.assertEqual(state['state'], 'implementation_complete')
        self.assertEqual(len(state['completed']), 3)

    def test_failed_attempt_stops_before_later_runs(self):
        launched, state = self.exercise('interrupted')
        self.assertEqual(launched, ['measured-001'])
        self.assertEqual(state['state'], 'needs_attention')
        self.assertEqual(state['completed'], [])
