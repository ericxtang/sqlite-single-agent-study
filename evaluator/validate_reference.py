#!/usr/bin/env python3
"""Run the frozen corpus against controller-side reference SQLite, with resumable logs."""
import argparse
import json
from pathlib import Path
import sqlite3
import time

from slt import Reference, Normalizer, score_file

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--limit-files', type=int)
    args = p.parse_args()
    output = ROOT / 'records/reference-validation.jsonl'
    already = set()
    if output.exists():
        for line in output.read_text().splitlines():
            already.add(json.loads(line)['path'])
    manifest = json.loads((ROOT / 'records/corpus-manifest.json').read_text())
    n = 0
    for entry in manifest['files']:
        if entry['path'] in already:
            continue
        engine = Reference()
        result = score_file(ROOT / 'private/corpus/checkout/test' / entry['path'], engine)
        engine.request({'op': 'close'})
        row = {'path': entry['path'], 'sqlite_version': sqlite3.sqlite_version, **result}
        with output.open('a') as f:
            f.write(json.dumps(row) + '\n')
        n += 1
        if result['queries_failed'] or result['statements_failed']:
            print(json.dumps(row), flush=True)
        elif n % 10 == 0:
            print(json.dumps({'validated_files_this_invocation': n, 'latest': entry['path']}), flush=True)
        if args.limit_files is not None and n >= args.limit_files:
            break
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    summary = {'sqlite_version': sqlite3.sqlite_version, 'files_validated': len(rows), 'files_total': len(manifest['files']), 'queries_passed': sum(r['queries_passed'] for r in rows), 'queries_failed': sum(r['queries_failed'] for r in rows), 'statements_failed': sum(r['statements_failed'] for r in rows), 'complete': len(rows) == len(manifest['files'])}
    summary['passed'] = summary['complete'] and summary['queries_failed'] == 0 and summary['statements_failed'] == 0
    (ROOT / 'records/reference-validation-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
