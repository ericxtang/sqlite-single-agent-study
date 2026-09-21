import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from awake_guard import AwakeClock, ClockDiscontinuity, run

class AwakeGuardTests(unittest.TestCase):
    def test_normal_elapsed_time_including_scheduler_delay(self):
        clock = AwakeClock()
        clock.observe(100, 10)
        clock.observe(400, 310)

    def test_suspend_and_backward_clock_steps_rejected(self):
        for wall in (500, 50):
            clock = AwakeClock()
            clock.observe(100, 10)
            with self.assertRaises(ClockDiscontinuity): clock.observe(wall, 11)

    def test_small_clock_drift_allowed(self):
        clock = AwakeClock()
        clock.observe(100, 10)
        clock.observe(101.2, 11)

    def test_real_child_success_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            for code in (0, 7):
                path = Path(tmp)/f'{code}.json'
                result = run([sys.executable, '-c', f'raise SystemExit({code})'], path, interval=.01)
                record = json.loads(path.read_text())
                self.assertEqual(result, int(code != 0))
                self.assertEqual(record['child_returncode'], code)
                self.assertEqual(record['status'], 'complete' if code == 0 else 'child_failed')

    def test_gap_stops_owned_child_and_withholds_acceptance(self):
        class Gap:
            def __init__(self): self.calls=0
            def observe(self):
                self.calls+=1
                if self.calls>1: raise ClockDiscontinuity('simulated sleep')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'
            code=run([sys.executable,'-c','import time; time.sleep(60)'],path,clock=Gap(),interval=.01)
            record=json.loads(path.read_text())
            self.assertEqual(code,1)
            self.assertEqual(record['status'],'infrastructure_interruption')
            self.assertIsNotNone(record['child_returncode'])
            with self.assertRaises(ProcessLookupError): os.kill(record['child_pid'],0)

    def test_existing_attempt_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json';path.write_text('preserve')
            with self.assertRaises(FileExistsError): run([sys.executable,'-c','pass'],path)
            self.assertEqual(path.read_text(),'preserve')

if __name__ == '__main__': unittest.main()
