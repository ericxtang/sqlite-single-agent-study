#!/usr/bin/env python3
"""Grade all endpoints before progress checkpoints; preserve incomplete evaluations."""
from datetime import datetime, timezone
import fcntl
import json
import os
import subprocess
import sys

from freeze import ROOT, verify


def main():
    lock = (ROOT / 'records/grading.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    frozen = verify()
    count = json.loads((ROOT / 'study.json').read_text())['measured_repetitions']
    runs = [ROOT / 'runs' / f'measured-{i:03d}' for i in range(1, count + 1)]
    for run in runs:
        manifest = json.loads((run / 'manifest.json').read_text())
        if manifest['state'] != 'completed':
            raise SystemExit('All measured runs must finish before automatic grading')
        if not json.loads((run / 'audit.json').read_text())['passed']:
            raise SystemExit('Run audit not passed')
    jobs = [(run, run / 'checkpoints/final.tar.gz', 'primary') for run in runs]
    jobs += [(run, run / 'checkpoints/final.tar.gz', 'secondary') for run in runs]
    jobs += [(run, archive, 'primary') for run in runs for archive in sorted((run / 'checkpoints').glob('*.tar.gz')) if archive.name != 'final.tar.gz']
    state = {'pid': os.getpid(), 'started_at': datetime.now(timezone.utc).isoformat(), 'state': 'running', 'freeze_sha256': frozen, 'jobs_total': len(jobs), 'jobs_complete': 0}
    def save():
        temp = ROOT / 'records/grading-state.partial'
        temp.write_text(json.dumps(state, indent=2) + '\n')
        temp.replace(ROOT / 'records/grading-state.json')
    try:
        for run, archive, suite in jobs:
            output = run / 'evaluation' / (archive.name.removesuffix('.tar.gz') + '-' + suite)
            state['active_job'] = str(output.relative_to(ROOT))
            save()
            if output.exists():
                summary_path = output / 'summary.json'
                if not summary_path.exists():
                    raise RuntimeError('Incomplete evaluation exists; inspect before any rerun: ' + str(output))
                summary = json.loads(summary_path.read_text())
                checkpoint = json.loads(archive.with_suffix('.gz.json').read_text())
                if not summary['evaluation_complete'] or summary['checkpoint_sha256'] != checkpoint['sha256'] or summary['suite'] != suite or summary['diagnostic_subset']:
                    raise RuntimeError('Existing evaluation not complete/matching: ' + str(output))
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.with_suffix('.log').open('x') as log:
                    code = subprocess.call([sys.executable, str(ROOT / 'evaluator/evaluate_snapshot.py'), '--archive', str(archive), '--output', str(output), '--suite', suite], stdout=log, stderr=subprocess.STDOUT)
                if code or not json.loads((output / 'summary.json').read_text())['evaluation_complete']:
                    raise RuntimeError('Evaluator failed; preserve logs: ' + str(output))
            state['jobs_complete'] += 1
            save()
        state.update(state='complete', active_job=None, finished_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        state.update(state='needs_attention', error=str(exc))
    finally:
        save()
        print(json.dumps(state, indent=2))
        lock.close()


if __name__ == '__main__':
    main()
