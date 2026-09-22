#!/usr/bin/env python3
"""Run a grading controller while rejecting host clock/suspend discontinuities."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time


class ClockDiscontinuity(RuntimeError):
    """Host suspension or a clock correction makes deadline attribution uncertain."""


class AwakeClock:
    def __init__(self, tolerance=2.0):
        self.tolerance = tolerance
        self.previous = None

    def observe(self, wall=None, monotonic=None):
        """Compare wall and monotonic elapsed time; monotonic excludes host sleep."""
        wall = time.time() if wall is None else wall
        monotonic = time.monotonic() if monotonic is None else monotonic
        if self.previous is not None:
            old_wall, old_monotonic = self.previous
            gap = (wall-old_wall) - (monotonic-old_monotonic)
            if abs(gap) > self.tolerance:
                raise ClockDiscontinuity(f'Wall/monotonic elapsed time diverged by {gap:.3f} seconds')
        self.previous = (wall, monotonic)


def save(path, record):
    """Sync a new state file, atomically replace it, then sync its directory."""
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as handle:
        json.dump(record, handle, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def run(argv, path, clock=None, interval=1):
    """Launch once; stop and preserve on clock gaps, signals or child failure."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x'):
        pass
    clock = clock or AwakeClock()
    record = {'status':'starting', 'started_at':datetime.now(timezone.utc).isoformat(),
              'pid':os.getpid(), 'command':argv,
              'guard_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'acceptance':'Both guard and grading queue must complete; guard failure invalidates this attempt even if a child summary says complete.'}
    save(path, record)
    proc = None
    previous_handlers = {}
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
        record['stop_signal'] = signum
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[sig] = signal.signal(sig, stop)
        clock.observe()
        proc = subprocess.Popen(argv, start_new_session=True)
        record.update(status='running', child_pid=proc.pid)
        save(path, record)
        while True:
            # Check before accepting even a successful child exit after a sleep.
            clock.observe()
            if stopping:
                record['status'] = 'stopped'
                break
            code = proc.poll()
            if code is not None:
                record['status'] = 'complete' if code == 0 else 'child_failed'
                break
            time.sleep(interval)
    except ClockDiscontinuity as exc:
        record.update(status='infrastructure_interruption', error=str(exc))
    except BaseException as exc:
        record.update(status='guard_failed', error=repr(exc))
    finally:
        if proc:
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                record.update(status='cleanup_needs_review', error='Grader did not exit after SIGTERM; inspect its evaluator/container before retrying')
            record['child_returncode'] = proc.poll()
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
        save(path, record)
    return 0 if record['status'] == 'complete' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', required=True, type=Path)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('Supply a grader command after --')
    raise SystemExit(run(command, args.record))

if __name__ == '__main__': main()
