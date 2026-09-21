"""Run only the newly authored manual examples; preserve raw diagnostic transcripts."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXPECTED = [
    [['5','1']],
    [['bread','5'],['apricot','2'],['coffee','1']],
    [['3','8']], [['99']], [['5']], [['3']], [['15']],
    [['bread','1'],['apricot','2'],['coffee','3']], [['42']],
    [[None,'42','3.5','hello','00abff']],
    [['1','saved across restart','00ABFF']],
]

def main():
    outputs=[]
    for run in ['001','002','004','003-30min']:
        before = set((HERE/'logs').glob('*.jsonl'))
        result = subprocess.run([sys.executable,str(HERE/'lab.py'),'console',run],
            input=(HERE/'examples.txt').read_text(), text=True, capture_output=True, timeout=180)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        output=HERE/'logs'/f'examples-{run}-{stamp}.txt'
        output.write_text(result.stdout+'\n'+result.stderr)
        transcripts = sorted(set((HERE/'logs').glob('*.jsonl'))-before)
        events=[]
        for path in transcripts:
            events.extend(json.loads(line) for line in path.read_text().splitlines())
        events.sort(key=lambda x:x['at'])
        selects=[]; errors=[]; all_responses=[]
        pending=None
        for event in events:
            if 'request' in event:
                pending=event['request']
            else:
                response=event['response'];all_responses.append(response)
                if not response.get('ok'):
                    errors.append({'request':pending,'response':response})
                if pending and pending.get('op')=='execute' and pending['sql'].startswith(('SELECT','WITH')):
                    selects.append([[None if c['type']=='null' else c.get('value','').lower() if c['type']=='blob' else c.get('value') for c in row] for row in response.get('rows',[])])
        passed=(result.returncode==0 and selects==EXPECTED and len(errors)==1 and
                errors[0]['request']['sql']=="INSERT INTO items VALUES (2,'duplicate',9);")
        entry=dict(run=run,passed=passed,select_values=selects,expected_select_values=EXPECTED,
                   errors=errors,process_exit_code=result.returncode,
                   transcript_files=[str(p.relative_to(HERE.parent)) for p in transcripts],
                   console_output=str(output.relative_to(HERE.parent)))
        outputs.append(entry)
        print(run, 'PASS' if passed else 'DIFFERENCE', output, flush=True)
    report=dict(recorded_at=datetime.now(timezone.utc).isoformat(),
                scope='Post-study manual examples only; no hidden corpus, no evaluator rerun, no score revision.',
                runs=outputs)
    (HERE/'example-validation.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
