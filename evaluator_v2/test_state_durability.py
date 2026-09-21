"""Exercise the real controller save function without dispatching a grading job."""
import ast
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch


def save_function(output, state):
    """Load only the nested save function, excluding controller startup/imports."""
    source = ast.parse(Path(__file__).with_name('grade.py').read_text())
    main = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    save = next(node for node in main.body if isinstance(node, ast.FunctionDef) and node.name == 'save')
    module = ast.fix_missing_locations(ast.Module(body=[save], type_ignores=[]))
    namespace = {'output': output, 'state': state, 'os': os, 'json': json}
    exec(compile(module, '<controller-save>', 'exec'), namespace)
    return namespace['save']


class StateDurabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.destination = self.output / 'state.json'
        self.old = {'completed': 0}
        self.new = {'completed': 1}
        self.destination.write_text(json.dumps(self.old))
        self.save = save_function(self.output, self.new)

    def test_contents_synced_before_replace_directory_after(self):
        calls = []
        def synced(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                calls.append('directory')
                self.assertEqual(json.loads(self.destination.read_text()), self.new)
                self.assertFalse((self.output/'state.json.tmp').exists())
            else:
                calls.append('file')
                self.assertEqual(json.loads((self.output/'state.json.tmp').read_text()), self.new)
                self.assertEqual(json.loads(self.destination.read_text()), self.old)
        with patch('os.fsync', side_effect=synced):
            self.save()
        self.assertEqual(calls, ['file', 'directory'])

    def test_file_sync_failure_preserves_previous_state(self):
        with patch('os.fsync', side_effect=OSError('disk sync failed')):
            with self.assertRaises(OSError): self.save()
        self.assertEqual(json.loads(self.destination.read_text()), self.old)

    def test_directory_descriptor_closed_on_sync_failure(self):
        captured = []
        def synced(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                captured.append(fd)
                raise OSError('directory sync failed')
        with patch('os.fsync', side_effect=synced):
            with self.assertRaises(OSError): self.save()
        self.assertEqual(len(captured), 1)
        with self.assertRaises(OSError): os.fstat(captured[0])
        self.assertEqual(json.loads(self.destination.read_text()), self.new)

    def test_real_filesystem_roundtrip(self):
        self.save()
        self.assertEqual(json.loads(self.destination.read_text()), self.new)
        self.assertFalse((self.output/'state.json.tmp').exists())

if __name__ == '__main__': unittest.main()
