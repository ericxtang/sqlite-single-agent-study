#!/usr/bin/env python3
"""Run isolated graders on saved checkpoints; never start an implementation/model."""
import argparse,concurrent.futures,hashlib,json,os,signal,subprocess,sys,threading
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
active=set();lock=threading.Lock();stopped=threading.Event()
def terminate(*_):
    stopped.set()
    with lock:
        for p in active:
            if p.poll() is None:
                try:p.send_signal(signal.SIGTERM)
                except ProcessLookupError:pass
def jobs_for(preset):
    rows=json.loads((ROOT/'reports/data/comparison-data.json').read_text())['jobs']
    return [dict(archive=ROOT/row['archive'].replace('runs/','results/',1),suite=row['suite']) for row in rows if preset=='all' or row['kind'] in ('four_hour_endpoint','interrupted_terminal_diagnostic','terminal_secondary')]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--preset',choices=['endpoints','all']);group.add_argument('--archive',type=Path)
    p.add_argument('--legacy-v1',action='store_true',help='Explicitly reproduce known-defective historical scoring; use evaluator_v2/grade.py for corrected grading')
    p.add_argument('--suite',choices=['primary','secondary'],default='primary')
    p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=1)
    p.add_argument('--limit-files',type=int,help='Diagnostic primary subset; never a full score')
    a=p.parse_args()
    if not a.legacy_v1:p.error('v1 has known scoring defects (issue #1). Use evaluator_v2/grade.py, or explicitly opt into --legacy-v1 for historical reproduction.')
    from execution_lock import acquire
    execution_guard=acquire()
    if not 1<=a.workers<=7:p.error('workers must be between 1 and 7')
    if a.limit_files is not None and (not a.archive or a.suite!='primary' or a.limit_files<=0):p.error('--limit-files needs one primary archive and a positive count')
    if subprocess.check_output(['docker','ps','-q','--filter','label=study=sqlite-single-agent'],text=True).strip():p.error('Implementation worker live; grade only after all implementations stop')
    from integrity import release_verify
    release_verify()
    from manage import verify_corpus
    verify_corpus()
    jobs=jobs_for(a.preset) if a.preset else [dict(archive=a.archive.resolve(),suite=a.suite)]
    if not jobs:raise RuntimeError('No jobs selected')
    output=a.output.resolve();output.mkdir(parents=True,exist_ok=False)
    # Catch accidental ordering/filter edits before dispatch.
    if a.preset and len(jobs)!=(59 if a.preset=='all' else 8):raise RuntimeError('Unexpected logical queue size')
    for index,j in enumerate(jobs):
        j['output']=output/(f'{index:03d}-'+j['archive'].parent.parent.name+'-'+j['archive'].name.replace('.tar.gz','')+'-'+j['suite'])
    def serializable(j):return {k:str(v) for k,v in j.items()}
    (output/'plan.json').write_text(json.dumps({'workers':a.workers,'jobs':[serializable(j) for j in jobs]},indent=2)+'\n')
    signal.signal(signal.SIGINT,terminate);signal.signal(signal.SIGTERM,terminate)
    def run(j):
        if stopped.is_set():return dict(**serializable(j),state='not_started')
        args=[sys.executable,str(ROOT/'replication/evaluate.py'),'--archive',str(j['archive']),'--output',str(j['output']),'--suite',j['suite']]
        if a.limit_files:args+=['--limit-files',str(a.limit_files)]
        with j['output'].with_suffix('.log').open('w') as log:
            with lock:
                if stopped.is_set():return dict(**serializable(j),state='not_started')
                proc=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);active.add(proc)
            code=proc.wait()
            with lock:active.remove(proc)
        summary=j['output']/'summary.json'
        d=json.loads(summary.read_text()) if summary.exists() else {}
        complete=code==0 and d.get('evaluation_complete',False)
        if not complete:terminate()
        result=dict(**serializable(j),state='complete' if complete else 'incomplete_needs_review',returncode=code,score=d.get('score'),build_ok=d.get('build_ok'))
        print(json.dumps(result),flush=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        results=list(pool.map(run,jobs))
    (output/'state.json').write_text(json.dumps({'finished_at':datetime.now(timezone.utc).isoformat(),'complete':all(x['state']=='complete' for x in results),'jobs':results},indent=2)+'\n')
    if not all(x['state']=='complete' for x in results):raise SystemExit('Grading incomplete; partial outputs preserved. Review before making an explicit new retry plan.')
if __name__=='__main__':main()
