#!/usr/bin/env python3
"""Recompute published aggregates from the 59 retained logical results, without inference."""
import argparse,csv,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def csvwrite(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--plots',action='store_true');a=p.parse_args()
    from integrity import release_verify
    release_verify()
    a.output.mkdir(parents=True,exist_ok=False)
    data=json.loads((ROOT/'reports/data/comparison-data.json').read_text());primary=[];secondary=[]
    for job in data['jobs']:
        s=json.loads((ROOT/job['output'].replace('runs/','results/',1)/'summary.json').read_text())
        if job['suite']=='primary':
            primary.append(dict(run=job['run_id'],kind=job['kind'],seconds=s['checkpoint_elapsed_seconds'],build_ok=s['build_ok'],passed=s['queries_passed'],queries=s['queries'],score=s['score']))
        else:
            for row in s['secondary']['cases']:secondary.append(dict(run=job['run_id'],case=row['case'],passed=row['passed'],reason=row.get('reason','')))
    endpoints=[r for r in primary if r['kind']=='four_hour_endpoint']
    scores=[r['score'] for r in endpoints]
    assert len(endpoints)==3 and len(primary)==55 and len(secondary)==48
    usage=[]
    for r in json.loads((ROOT/'historical/records/usage-accounting.json').read_text())['runs']:
        t=r['deduplicated_response_usage_sum'];cost=((t['input_tokens']-t['cached_input_tokens']-t['cache_write_input_tokens'])*10+t['cached_input_tokens']+t['cache_write_input_tokens']*12.5+t['output_tokens']*50)/1e6
        usage.append(dict(run=r['run_id'],category=r['category'],**t,recorded_category_standard_api_valuation_usd=cost,no_cache_api_valuation_usd=(t['input_tokens']*10+t['output_tokens']*50)/1e6))
    for name,rows in [('primary-checkpoints',primary),('four-hour-endpoints',endpoints),('secondary',secondary),('usage-valuations',usage)]:csvwrite(a.output/(name+'.csv'),rows)
    summary={'n':len(endpoints),'median':statistics.median(scores),'min':min(scores),'max':max(scores),'primary_checkpoints':55,'secondary_outcomes':48,'cost_caveat':'Historical September 21 2026 hypothetical API valuations; not subscription invoices. See reports/data/cost-audit.json.'}
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if a.plots:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(9,4.5))
        for run in sorted({r['run'] for r in primary}):
            rows=sorted((r for r in primary if r['run']==run),key=lambda r:r['seconds'])
            ax.plot([r['seconds']/60 for r in rows],[r['score']*100 for r in rows],marker='o',label=run+(' (interrupted)' if run.endswith('003') else ''))
        ax.set(xlabel='Implementation elapsed time (minutes)',ylabel='Eligible queries passed (%)',ylim=(0,100),xlim=(0,245),title='All retained primary checkpoints; build failures remain zero')
        ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(a.output/'progress.png',dpi=180);fig.savefig(a.output/'progress.svg');plt.close(fig)
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
