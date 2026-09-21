#!/usr/bin/env python3
"""Read-only trajectory/checkpoint audit; no feedback to implementation agents."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

from runtime_config import ROOT
from status import run_status


def audit(run):
    status = run_status(run)
    manifest = json.loads((run / 'manifest.json').read_text())
    user_prompts = []
    usage = []
    calls = Counter()
    for path in sorted((run / 'runtime/sessions').rglob('*.jsonl')):
        for line in path.open():
            item = json.loads(line)
            payload = item.get('payload', {})
            if item['type'] == 'token_usage_record':
                usage.append({'timestamp': item['timestamp'], **payload})
            if payload.get('type') in ('custom_tool_call', 'function_call'):
                calls[payload.get('name')] += 1
            if item['type'] == 'response_item' and payload.get('type') == 'message' and payload.get('role') == 'user':
                user_prompts.append('\n'.join(c.get('text', '') for c in payload.get('content', [])))
    task = (ROOT / 'inputs/TASK.md').read_text()
    continuation = (ROOT / 'inputs/CONTINUE.md').read_text()
    prompt_ok = all(p.strip() in (task.strip(), continuation.strip()) or p.startswith('<environment_context>') for p in user_prompts)
    checkpoints = []
    for path in sorted((run / 'checkpoints').glob('*.tar.gz')):
        meta = json.loads(path.with_suffix('.gz.json').read_text())
        with tarfile.open(path) as archive:
            count = len(archive.getmembers())
        checkpoints.append({'name': path.name, 'hash_matches': hashlib.sha256(path.read_bytes()).hexdigest() == meta['sha256'], 'members': count, 'capture_seconds': meta['capture_seconds'], 'elapsed_seconds': meta['elapsed_seconds']})
    state = json.loads(subprocess.check_output(['docker', 'inspect', '--format', '{{json .State}}', manifest['container']], text=True))
    with tarfile.open(run / 'checkpoints/00000.tar.gz') as initial:
        fresh_workspace = set(initial.getnames()) == {'.', 'IO_CONTRACT.md'} and initial.extractfile('IO_CONTRACT.md').read() == (ROOT / 'inputs/IO_CONTRACT.md').read_bytes()
    single_identity = len({u['thread_id'] for u in usage}) == 1 and all(u['thread_id'] == manifest['thread_id'] for u in usage)
    allowed_calls = {'exec', 'functions.exec', 'clock__curr_time', 'clock.sleep', 'sleep', 'request_user_input', 'mcp__workspace__exec', 'list_mcp_resources', 'list_mcp_resource_templates', 'read_mcp_resource'}
    checks = {'completed': status['state'] == 'completed', 'correct_model_effort': bool(status['effective_contexts']) and all(c == {'model': 'gpt-6-astra', 'effort': 'xhigh'} for c in status['effective_contexts']), 'one_trajectory_in_usage': single_identity, 'prompts_not_coached': prompt_ok, 'tool_calls_within_surface': not (set(calls) - allowed_calls), 'checkpoint_hashes_match': bool(checkpoints) and all(c['hash_matches'] for c in checkpoints), 'worker_stopped': not state['Running'], 'deadline_within_one_second': status['elapsed_seconds'] is not None and manifest['duration_seconds'] <= status['elapsed_seconds'] <= manifest['duration_seconds'] + 1}
    checks['fresh_initial_workspace'] = fresh_workspace
    # Preserve independent request and cumulative telemetry without folding setup usage in.
    (run / 'usage.jsonl').write_text(''.join(json.dumps(record) + '\n' for record in usage))
    return {'recorded_at': datetime.now(timezone.utc).isoformat(), 'passed': all(checks.values()), 'checks': checks, 'status': status, 'tool_call_names': dict(calls), 'checkpoints': checkpoints, 'usage_records': len(usage), 'limitations': ['Usage can omit a request active at cutoff.', 'No natural compaction observed; compaction behavior remains untested.' if not status['compaction_events'] else 'Normal compaction events retained in raw session logs.', 'Same-trajectory continuation validated synthetically; check effective contexts for live occurrence.']}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('run_id')
    p.add_argument('--output')
    args = p.parse_args()
    result = audit(ROOT / 'runs' / args.run_id)
    destination = Path(args.output) if args.output else ROOT / 'runs' / args.run_id / 'audit.json'
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
