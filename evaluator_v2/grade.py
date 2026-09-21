#!/usr/bin/env python3
"""Sequential v2 queue with durable progress, immutable inputs and no retries."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'replication'))
from execution_lock import acquire
from integrity import release_verify
from manage import verify_corpus
from grade import jobs_for


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preset', choices=['endpoints', 'all'], default='endpoints')
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    guard = acquire()
    if (ROOT / 'records/STOP').exists(): raise RuntimeError('STOP exists')
    release_hash = release_verify()
    verify_corpus()
    if subprocess.check_output(['docker', 'ps', '-q', '--filter', 'label=study=sqlite-single-agent'], text=True).strip():
        raise RuntimeError('An implementation worker is live')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = [*sorted((ROOT / 'evaluator_v2').glob('*.py')), ROOT/'evaluator/slt.py', ROOT/'evaluator/secondary.py', ROOT/'evaluator/process.py', ROOT/'records/corpus-manifest.json']
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in sources}
    jobs = jobs_for(args.preset)
    # Completed endpoints first, interrupted terminal next, then all secondary;
    # remaining progress checkpoints (if requested) follow in frozen queue order.
    # Use the known endpoint list, since terminal archive names are protocol-specific.
    endpoints = jobs_for('endpoints')
    keys = {(str(j['archive']), j['suite']) for j in endpoints}
    jobs = sorted(endpoints, key=lambda j: (j['suite'] != 'primary', 'measured-003' in str(j['archive']), str(j['archive']))) + [j for j in jobs if (str(j['archive']), j['suite']) not in keys]
    serial = []
    for i, job in enumerate(jobs):
        serial.append({'archive':str(job['archive']), 'archive_sha256':digest(job['archive']), 'suite':job['suite'],
                       'output':str(output / f'{i:03d}-{job["archive"].parent.parent.name}-{job["suite"]}')})
    plan = {'version':2, 'created_at':now(), 'workers':1, 'image':args.image, 'publication_manifest_sha256':release_hash,
            'sources':hashes, 'jobs':serial, 'raw_protocol':'gzip frames: direction byte > or <, ASCII byte length, LF, exact bytes'}
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    (output/'plan.sha256').write_text(digest(output/'plan.json')+'\n')
    state={'started_at':now(),'pid':os.getpid(),'status':'running','completed':0,'jobs':[], 'active':None}
    proc=None
    stopped=False
    def save():
        tmp=output/'state.json.tmp'
        tmp.write_text(json.dumps(state,indent=2)+'\n')
        tmp.replace(output/'state.json')
    def stop(*_):
        nonlocal stopped
        stopped=True
        if proc is not None and proc.poll() is None: proc.send_signal(signal.SIGTERM)
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    save()
    try:
        for job in serial:
            if stopped or (ROOT/'records/STOP').exists():
                state['status']='stopped';break
            if any(digest(ROOT/path)!=sha for path,sha in hashes.items()) or digest(job['archive'])!=job['archive_sha256']:
                raise RuntimeError('Sealed grading source or artifact changed; refusing dispatch')
            cmd=[sys.executable,str(ROOT/'evaluator_v2/evaluate.py'),'--archive',job['archive'],'--output',job['output'],'--suite',job['suite'],'--image',args.image]
            with Path(job['output']+'.log').open('xb') as log:
                proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                state['active']={**job,'pid':proc.pid,'started_at':now()};save()
                while proc.poll() is None:
                    if (ROOT/'records/STOP').exists() and not stopped:stop()
                    time.sleep(1)
                code=proc.returncode
                proc=None
            path=Path(job['output'])/'summary.json'
            summary=json.loads(path.read_text()) if path.exists() else {}
            complete=code==0 and summary.get('evaluation_complete',False)
            result={**job,'returncode':code,'status':'complete' if complete else 'incomplete_needs_review','finished_at':now(),'summary_sha256':digest(path) if path.exists() else None}
            state['jobs'].append(result)
            state['active']=None
            state['completed']+=int(complete)
            save()
            print(json.dumps(result),flush=True)
            if not complete:
                state['status']='incomplete_needs_review';break
        else:
            state['status']='complete'
    except BaseException as exc:
        stop()
        if proc:proc.wait(timeout=60)
        state['status']='incomplete_needs_review'
        state['error']=repr(exc)
        raise
    finally:
        state['finished_at']=now();save()
    if state['status']!='complete':raise SystemExit('Incomplete queue preserved; review before a new, explicit retry plan')

if __name__=='__main__':main()
