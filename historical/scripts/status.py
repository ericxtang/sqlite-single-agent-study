#!/usr/bin/env python3
"""Compact study status without exposing agent source or hidden examples."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_status(run):
    manifest = json.loads((run / 'manifest.json').read_text())
    latest_usage = None
    contexts = []
    compactions = 0
    for path in sorted((run / 'runtime/sessions').rglob('*.jsonl')):
        for line in path.open():
            try:
                item = json.loads(line)
            except ValueError:
                continue
            payload = item.get('payload', {})
            if item.get('type') == 'turn_context':
                contexts.append({'model': payload.get('model'), 'effort': payload.get('effort')})
            if payload.get('type') == 'token_count' and payload.get('info'):
                latest_usage = payload['info'].get('total_token_usage')
            if item.get('type') == 'compacted' or payload.get('type') == 'context_compacted':
                compactions += 1
    tool_calls = 0
    if (run / 'tools.jsonl').exists():
        for line in (run / 'tools.jsonl').open():
            try:
                tool_calls += 'result' in json.loads(line)
            except ValueError:
                pass
    started = manifest.get('started_at')
    elapsed = manifest.get('actual_elapsed_seconds')
    if elapsed is None and started:
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds()
    return {'run_id': manifest['run_id'], 'mode': manifest['mode'], 'state': manifest['state'], 'started_at': started, 'elapsed_seconds': elapsed, 'duration_seconds': manifest['duration_seconds'], 'thread_id': manifest['thread_id'], 'effective_contexts': contexts, 'completed_tool_calls': tool_calls, 'last_completed_usage': latest_usage, 'usage_note': 'Cumulative recorded usage; an in-flight request may not yet be included. Reasoning output is a subset of output, not an extra amount.', 'compaction_events': compactions, 'checkpoints': [p.name for p in sorted((run / 'checkpoints').glob('*.tar.gz'))]}


def main():
    output = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'runs': [run_status(p.parent) for p in sorted((ROOT / 'runs').glob('*/manifest.json'))]}
    validation = ROOT / 'records/reference-validation.jsonl'
    if validation.exists():
        rows = []
        for line in validation.open():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
        output['reference_validation'] = {'files_checked': len(rows), 'queries_passed': sum(r['queries_passed'] for r in rows), 'queries_failed': sum(r['queries_failed'] for r in rows), 'statements_failed': sum(r['statements_failed'] for r in rows)}
    (ROOT / 'records/status.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
