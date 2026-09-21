"""Verify additive protocol seal without changing original frozen inputs."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from freeze import verify

DIRECTORY = Path(__file__).resolve().parent


def verify_amendment():
    seal_path = DIRECTORY / 'seal.json'
    seal = json.loads(seal_path.read_text())
    if verify() != seal['base_seal_sha256']:
        raise RuntimeError('Base seal mismatch')
    for name, expected in seal['files'].items():
        if hashlib.sha256((DIRECTORY / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Amendment file changed: ' + name)
    decision = json.loads((DIRECTORY / 'decision.json').read_text())
    if decision['status'] != 'approved' or decision['authorized_run_id'] != 'measured-004':
        raise RuntimeError('Replacement authorization mismatch')
    return hashlib.sha256(seal_path.read_bytes()).hexdigest()


if __name__ == '__main__':
    print(json.dumps({'verified': True, 'amendment_sha256': verify_amendment()}))
