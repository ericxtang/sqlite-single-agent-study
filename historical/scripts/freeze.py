#!/usr/bin/env python3
"""Seal inputs once; verify all measured launches against that seal."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SEAL = ROOT / 'records/freeze-v1.json'
RECORDS = ['documentation-manifest.json', 'corpus-manifest.json', 'runtime-image.json', 'utility-Cargo.lock', 'astra-mcp-only-catalog.json', 'astra-model-catalog.json', 'isolation-audit.json', 'continuation-audit.json', 'reference-validation-summary.json', 'evaluator-integration.json', 'secondary-validation.json', 'pilot-audit.json', 'historical-baseline.json', 'validation-tests.json']


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def files():
    found = set(ROOT.glob('*.md')) | {ROOT / 'study.json'}
    for directory in ('inputs', 'scripts', 'evaluator', 'runtime'):
        found.update(p for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    found.update(ROOT / 'records' / name for name in RECORDS)
    found.update((ROOT / 'private/corpus/checkout/test').rglob('*.test'))
    return sorted(found)


def verify():
    frozen = json.loads(SEAL.read_text())
    expected = frozen['files']
    actual_names = {str(path.relative_to(ROOT)) for path in files()}
    if actual_names != set(expected):
        raise RuntimeError('Frozen file inventory changed')
    for name, sha in expected.items():
        if digest(ROOT / name) != sha:
            raise RuntimeError('Frozen input changed: ' + name)
    cli = Path(shutil.which('codex')).resolve()
    if str(cli) != frozen['codex']['path'] or digest(cli) != frozen['codex']['sha256']:
        raise RuntimeError('Codex executable changed')
    if subprocess.check_output(['codex', '--version'], text=True).strip() != frozen['codex']['version']:
        raise RuntimeError('Codex version changed')
    image = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', frozen['image']], text=True).strip()
    if image != frozen['image']:
        raise RuntimeError('Pinned worker image unavailable')
    return digest(SEAL)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--create', action='store_true')
    args = parser.parse_args()
    if args.create:
        if SEAL.exists():
            raise SystemExit('Freeze already exists; refusing to overwrite')
        config = json.loads((ROOT / 'study.json').read_text())
        if not all(config.get(k) for k in ('protocol_frozen', 'measured_runs_enabled', 'runner_validated', 'evaluator_validated', 'isolation_validated')):
            raise SystemExit('Validation/launch gates not complete')
        if list((ROOT / 'runs').glob('measured-*')):
            raise SystemExit('Cannot freeze after a measured run exists')
        cli = Path(shutil.which('codex')).resolve()
        result = {'version': '1.0', 'created_at': datetime.now(timezone.utc).isoformat(), 'files': {str(path.relative_to(ROOT)): digest(path) for path in files()}, 'codex': {'path': str(cli), 'sha256': digest(cli), 'version': subprocess.check_output(['codex', '--version'], text=True).strip()}, 'image': json.loads((ROOT / 'records/runtime-image.json').read_text())['id']}
        SEAL.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'verified': True, 'freeze_sha256': verify()}))


if __name__ == '__main__':
    main()
