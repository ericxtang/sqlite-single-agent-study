#!/usr/bin/env python3
"""Serial fixed-budget runs. Never replace a failed attempt or launch model helpers."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

from audit_run import audit
from freeze import ROOT, verify


def main():
    lock = (ROOT / 'records/batch.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    config = json.loads((ROOT / 'study.json').read_text())
    runs = [f'measured-{i:03d}' for i in range(1, config['measured_repetitions'] + 1)]
    if any((ROOT / 'runs' / name).exists() for name in runs):
        raise SystemExit('A measured attempt already exists. Refusing to restart or replace it.')
    state = {'pid': os.getpid(), 'started_at': datetime.now(timezone.utc).isoformat(), 'state': 'starting', 'runs': runs, 'completed': [], 'freeze_sha256': verify()}
    child = None
    def save():
        temporary = ROOT / 'records/batch-state.partial'
        temporary.write_text(json.dumps(state, indent=2) + '\n')
        temporary.replace(ROOT / 'records/batch-state.json')
    def stop(signum, frame):
        if child is not None and child.poll() is None:
            child.terminate()
        raise KeyboardInterrupt('Batch received stop signal')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    save()
    try:
        for name in runs:
            if (ROOT / 'records/STOP').exists():
                raise RuntimeError('Operator STOP file present')
            verify()
            state.update(state='running', active_run=name)
            save()
            with (ROOT / 'records' / (name + '-controller.log')).open('x') as log:
                child = subprocess.Popen([sys.executable, str(ROOT / 'scripts/run.py'), '--mode', 'measured', '--run-id', name], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                state['controller_pid'] = child.pid
                save()
                code = child.wait()
            manifest_path = ROOT / 'runs' / name / 'manifest.json'
            if code or not manifest_path.exists():
                raise RuntimeError(f'{name}: controller exit {code}; preserve attempt and inspect logs')
            manifest = json.loads(manifest_path.read_text())
            if manifest['state'] != 'completed':
                raise RuntimeError(f'{name}: {manifest["state"]}; preserve attempt, do not rerun')
            result = audit(ROOT / 'runs' / name)
            (ROOT / 'runs' / name / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
            if not result['passed']:
                raise RuntimeError(f'{name}: post-run audit requires review; later runs not launched')
            state['completed'].append(name)
            save()
        state.update(state='implementation_complete', active_run=None, finished_at=datetime.now(timezone.utc).isoformat())
    except (Exception, KeyboardInterrupt) as exc:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                state['stop_warning'] = 'Controller has not yet finished stop handling; inspect worker state.'
        state.update(state='needs_attention', error=str(exc), stopped_at=datetime.now(timezone.utc).isoformat())
    finally:
        save()
        print(json.dumps(state, indent=2), flush=True)
        lock.close()


if __name__ == '__main__':
    main()
