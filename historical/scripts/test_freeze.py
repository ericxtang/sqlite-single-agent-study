"""Critical seal checks use temporary fixtures, never real experiment inputs."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import freeze


class FreezeTests(unittest.TestCase):
    def test_verify_rejects_mutated_and_added_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / 'input.txt'
            source.write_text('frozen')
            cli = root / 'codex'
            cli.write_text('binary')
            seal = root / 'seal.json'
            seal.write_text(json.dumps({'files': {'input.txt': freeze.digest(source)}, 'codex': {'path': str(cli), 'sha256': freeze.digest(cli), 'version': 'codex-cli 0.153.0'}, 'image': 'sha256:test'}))
            def command(argv, **kwargs):
                return 'codex-cli 0.153.0' if argv[0] == 'codex' else 'sha256:test'
            with patch.object(freeze, 'ROOT', root), patch.object(freeze, 'SEAL', seal), patch.object(freeze, 'files', return_value=[source]), patch.object(freeze.shutil, 'which', return_value=str(cli)), patch.object(freeze.subprocess, 'check_output', side_effect=command):
                self.assertEqual(freeze.verify(), freeze.digest(seal))
                source.write_text('changed')
                with self.assertRaisesRegex(RuntimeError, 'Frozen input changed'):
                    freeze.verify()
                source.write_text('frozen')
                with patch.object(freeze, 'files', return_value=[source, cli]):
                    with self.assertRaisesRegex(RuntimeError, 'inventory changed'):
                        freeze.verify()


if __name__ == '__main__':
    unittest.main()
