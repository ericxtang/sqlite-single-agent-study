import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluator'))
sys.path.insert(0, str(ROOT / 'evaluator_v2'))
from container import Container, InfrastructureError
from secondary import execute, run_suite, ReferenceLab
from slt import score_file
from evaluate import evaluate

class Engine:
    def __init__(self, cell): self.cell = cell
    def request(self, request): return {'ok': True, 'columns': ['x'], 'rows': [[self.cell]]}

class V2Tests(unittest.TestCase):
    def test_blob_equivalent_spelling(self):
        for text in ('00ff', '00FF', '00fF'):
            execute(Engine({'type': 'blob', 'value': text}), "SELECT x'00ff'", [(b'\x00\xff',)])
        execute(Engine({'type': 'blob', 'value': ''}), "SELECT x''", [(b'',)])

    def test_blob_unequal_malformed_or_wrong_type_rejected(self):
        cells = [{'type': 'blob', 'value': value} for value in ('00FE', '0', 'xx', '00 ff', None, 123)]
        cells += [{'type': 'text', 'value': '00ff'}, {'type': 'blob'}, {'type': 'blob', 'value': '00ff', 'unexpected': 1}]
        for cell in cells:
            with self.subTest(cell=cell), self.assertRaises(ValueError):
                execute(Engine(cell), "SELECT x'00ff'", [(b'\x00\xff',)])

    def test_reference_all_twelve(self):
        lab = ReferenceLab()
        try: self.assertEqual(run_suite(lab)['passed'], 12)
        finally: lab.close()

    def test_infrastructure_bypasses_scorer(self):
        class BrokenLauncher:
            def request(self, request): raise InfrastructureError('Launch failed')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'one.test'
            path.write_text('query I\nSELECT 1\n----\n1\n\n')
            with self.assertRaises(InfrastructureError): score_file(path, BrokenLauncher())

    def test_real_implementation_failure_stays_zero(self):
        class Crashed:
            def request(self, request): raise OSError('Engine stdout closed')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'one.test'
            path.write_text('query I\nSELECT 1\n----\n1\n\n')
            result = score_file(path, Crashed())
            self.assertEqual(result['queries_failed'], 1)
            self.assertTrue(result['tainted'])

    def test_launch_evidence_not_exit_code(self):
        for state in ({'StartedAt': '0001-01-01', 'Error': ''}, {'StartedAt': '2026-01-01', 'Error': 'runtime failure'}):
            with self.assertRaises(InfrastructureError): Container.require_started(state)
        Container.require_started({'StartedAt': '2026-01-01', 'Error': '', 'ExitCode': 125})

    def test_infrastructure_evaluation_incomplete_not_zero(self):
        archive = next((ROOT / 'results/measured-001/checkpoints').glob('final.tar.gz'))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'evaluation'
            with patch('evaluate.checked', side_effect=InfrastructureError('Docker unavailable')):
                with self.assertRaises(InfrastructureError): evaluate(archive, output, 'sha256:test', limit_files=1)
            result = json.loads((output / 'summary.json').read_text())
            self.assertIsNone(result['score'])
            self.assertFalse(result['evaluation_complete'])
            self.assertIsNone(result['queries_failed'])

if __name__ == '__main__': unittest.main()
