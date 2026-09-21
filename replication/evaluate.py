"""Explicit cleanup-only adapter around the byte-unchanged frozen evaluator."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'cleanup-recovery-001'
sys.path.insert(0, str(ROOT / 'evaluator'))
from process import JsonProcess as FrozenJsonProcess


class CleanupError(RuntimeError):
    """Infrastructure error, deliberately NOT TimeoutExpired (a frozen build zero)."""


def event(**fields):
    print(json.dumps({'recorded_at': datetime.now(timezone.utc).isoformat(),
                      'event': 'cleanup_fallback', 'revision': REVISION, **fields}),
          file=sys.stderr, flush=True)


def docker_cleanup(name):
    if not re.fullmatch(r'astra-sqlite-eval-(engine|build)-[0-9a-f]{12}', name):
        raise CleanupError('Refusing cleanup of an unexpected container name')
    deadline = time.monotonic() + 30
    try:
        removed = subprocess.run(['docker', 'rm', '-f', name], capture_output=True,
                                 text=True, timeout=30)
        # --rm can race our explicit rm. "Removal already in progress" needs a
        # bounded absence check, not an immediate success or immediate failure.
        while True:
            remaining = subprocess.run(['docker', 'container', 'ls', '--all',
                                        '--filter', 'name=^/' + name + '$', '--format', '{{.ID}}'],
                                       capture_output=True, text=True,
                                       timeout=max(.01, deadline - time.monotonic()))
            if remaining.returncode:
                raise CleanupError('Container absence query failed: ' + name + ': ' + remaining.stderr.strip())
            if not remaining.stdout.strip():
                return
            if time.monotonic() >= deadline:
                raise CleanupError('Container cleanup not confirmed: ' + name + ': ' + removed.stderr.strip())
            time.sleep(min(.1, max(0, deadline - time.monotonic())))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CleanupError('Could not confirm container cleanup: ' + name) from exc


class JsonProcess(FrozenJsonProcess):
    # __init__, reader, serialization, request deadline and response limit remain inherited.
    def close(self):
        self.stopped.set()
        try:
            if self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except (PermissionError, ProcessLookupError) as exc:
                    # poll->killpg can race with exit. If still live, target only our
                    # unreaped Popen child; never another PID/group or elevated privileges.
                    exited = self.process.poll() is not None
                    event(pid=self.process.pid, error=repr(exc), already_exited=exited,
                          action='reap' if exited else 'kill_owned_child')
                    if not exited:
                        try:
                            self.process.kill()
                        except ProcessLookupError:
                            pass
            self.process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CleanupError('Host child cleanup not confirmed: ' + str(self.process.pid)) from exc
        # The frozen evaluator next calls checked docker_cleanup for its unique container.
        # If this close raises, its outer finally still attempts that container cleanup.
        for stream in (self.process.stdin, self.process.stdout):
            try:
                stream.close()
            except (OSError, ValueError):
                pass


def load_evaluator():
    spec = importlib.util.spec_from_file_location('frozen_evaluate_snapshot', ROOT / 'evaluator/evaluate_snapshot.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.JsonProcess = JsonProcess
    module.docker_cleanup = docker_cleanup
    return module


def main():
    # Original module retains its real __file__ and ROOT. Only the two cleanup hooks differ.
    def terminate(signum, frame):
        raise KeyboardInterrupt("Evaluator stopped; preserving partial output")
    signal.signal(signal.SIGTERM, terminate)
    module = load_evaluator()
    output = Path(sys.argv[sys.argv.index('--output') + 1])
    if output.exists():
        raise RuntimeError('Existing output must be preserved')
    try:
        module.main()
    finally:
        summary_path = output / 'summary.json'
        if summary_path.exists():
            summary = json.loads(summary_path.read_text())
            summary['evaluator_revision'] = REVISION
            summary['frozen_evaluator_path'] = 'evaluator/evaluate_snapshot.py'
            summary_path.write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
