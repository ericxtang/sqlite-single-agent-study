"""Exercise the actual runner shutdown AST with recorded duplicate quota errors; no inference."""
import ast
from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import queue
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]


def cleanup_body(path):
    tree = ast.parse(path.read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    body = next(n.finalbody for n in main.body if isinstance(n, ast.Try) and n.finalbody)
    return compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(path), 'exec')


def exercise(path, *, duplicate=False, fail_capture=False, fail_pause=False, fail_kill=False):
    calls = []
    error_events = [json.dumps(json.loads(line)['event']) for line in (ROOT / 'runs/measured-003/events.jsonl').read_text().splitlines() if json.loads(line).get('event', {}).get('type') in ('error', 'turn.failed')]
    q = queue.Queue()
    for event in error_events if duplicate else []:
        q.put(event)
    def log_event(line):
        calls.append('event')
        assert json.loads(line)['type'] in ('error', 'turn.failed')
        raise RuntimeError('Account/authentication/rate-limit failure; no reset or billing fallback permitted')
    def docker(argv, **kwargs):
        calls.append(argv[1])
        if (argv[1] == 'pause' and fail_pause) or (argv[1] == 'kill' and fail_kill):
            raise subprocess.CalledProcessError(1, argv)
    def capture(*args, **kwargs):
        calls.append('capture')
        assert kwargs['keep_paused'] is True
        if fail_capture:
            raise OSError('injected checkpoint failure')
    with tempfile.TemporaryDirectory() as td:
        run = Path(td)
        scope = dict(subprocess=SimpleNamespace(run=docker, DEVNULL=-3), container='test',
                     time=SimpleNamespace(monotonic=lambda: 14400.1), stop_process=lambda p: calls.append('stop_model'),
                     process=None, q=q, log_event=log_event, capture=capture, run=run, t0=0,
                     manifest={'error':'subscription limit'} if duplicate else {}, interrupted=duplicate,
                     now=lambda:'test-stop-time', turn=1, json=json, events=io.StringIO(), stderr_file=io.StringIO(),
                     args=SimpleNamespace(run_id='test'))
        error = None
        try:
            with redirect_stdout(io.StringIO()):
                exec(cleanup_body(path), scope)
        except Exception as exc:
            error = exc
        saved = json.loads((run/'manifest.json').read_text()) if (run/'manifest.json').exists() else None
        return calls, saved, error


class CleanupRegression(unittest.TestCase):
    def test_original_reproduces_duplicate_failure_bug(self):
        calls, saved, error = exercise(ROOT/'scripts/run.py', duplicate=True)
        self.assertIsInstance(error, RuntimeError)
        self.assertIsNone(saved)
        self.assertNotIn('capture', calls)
    def test_duplicate_failure_preserves_artifact_and_stops_worker(self):
        calls, saved, error = exercise(ROOT/'records/amendment-001/run.py', duplicate=True)
        self.assertIsNone(error)
        self.assertEqual(calls, ['pause','stop_model','event','event','capture','kill'])
        self.assertEqual(saved['state'], 'interrupted')
        self.assertTrue(saved['final_checkpoint_captured'])
        self.assertEqual(len(saved['cleanup_errors']),2)
    def test_normal_deadline_preserved(self):
        calls,saved,error=exercise(ROOT/'records/amendment-001/run.py')
        self.assertIsNone(error)
        self.assertEqual(saved['state'],'completed')
        self.assertEqual(saved['actual_elapsed_seconds'],14400.1)
        self.assertEqual(calls,['pause','stop_model','capture','kill'])
    def test_capture_failure_still_stops_and_records(self):
        calls,saved,error=exercise(ROOT/'records/amendment-001/run.py',fail_capture=True)
        self.assertIsNone(error)
        self.assertIn('kill',calls)
        self.assertEqual(saved['state'],'interrupted')
        self.assertFalse(saved['final_checkpoint_captured'])
    def test_pause_failure_does_not_claim_endpoint(self):
        calls,saved,error=exercise(ROOT/'records/amendment-001/run.py',fail_pause=True)
        self.assertIsNone(error)
        self.assertNotIn('capture',calls)
        self.assertIn('kill',calls)
        self.assertEqual(saved['state'],'interrupted')
    def test_kill_failure_cannot_report_completion(self):
        calls,saved,error=exercise(ROOT/'records/amendment-001/run.py',fail_kill=True)
        self.assertIsNone(error)
        self.assertEqual(saved['state'],'interrupted')
        self.assertIn('kill worker',saved['cleanup_errors'][0])

if __name__ == '__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CleanupRegression))
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'tests_run':result.testsRun,'passed':result.wasSuccessful(),'model_calls':0,'scope':'Actual runner cleanup AST under mocked Docker/process calls, with recorded quota error events; original failure reproduced.'}
    (Path(__file__).parent/'cleanup-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
