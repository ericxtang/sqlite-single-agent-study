"""Explicit no-inference Docker regression checks; use the pinned study image."""
import argparse
import gzip
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(1, str(Path(__file__).resolve().parents[1] / 'evaluator'))
from container import Container, InfrastructureError, checked
from process import JsonProcess
from slt import score_file


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--image', required=True)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    owner = Container(a.image, [], ['sleep', 'infinity'], a.output / 'collision-owner')
    owner.start_keeper()
    try:
        try:
            JsonProcess(a.image, [], ['sh', '-c', 'exit 0'], a.output / 'collision-attempt', name=owner.name)
        except InfrastructureError:
            pass
        else:
            raise AssertionError('Name collision accepted')
        assert json.loads(checked(['inspect', owner.id]))[0]['State']['Running'], 'Collision removed another container'
    finally:
        owner.close()
    path = a.output / 'one.test'
    path.write_text('query I\nSELECT 1\n----\n1\n\n')
    # Exit 125 is a valid implementation crash when Docker confirms launch.
    crash = JsonProcess(a.image, [], ['sh', '-c', 'echo genuine-program-exit >&2; exit 125'], a.output / 'actual-exit-125')
    try:
        result = score_file(path, crash)
        assert result['queries_failed'] == 1 and result['tainted'], result
    finally:
        crash.close()
    assert b'genuine-program-exit' in (a.output / 'actual-exit-125/stderr.log').read_bytes()
    # Request timeout remains an implementation failure after confirmed launch.
    stalled = JsonProcess(a.image, [], ['sleep', '30'], a.output / 'stalled', timeout=.1)
    try:
        result = score_file(path, stalled)
        assert result['queries_failed'] == 1 and 'deadline' in result['abort_reason'], result
    finally:
        stalled.close()
    valid = JsonProcess(a.image, [], ['python3', '-u', '-c', 'import sys,json\nfor line in sys.stdin:\n print(json.dumps({"ok":True,"columns":["x"],"rows":[[{"type":"integer","value":"1"}]]}),flush=True)'], a.output / 'valid')
    try:
        result = score_file(path, valid)
        assert result['queries_passed'] == 1 and not result['tainted'], result
    finally:
        valid.close()
    raw = gzip.decompress((a.output / 'valid/protocol.bin.gz').read_bytes())
    assert b'SELECT 1' in raw and b'"value": "1"' in raw
    for evidence in a.output.glob('*/container.json'):
        d = json.loads(evidence.read_text())
        if d['container_id']: assert d['cleanup_confirmed'], evidence
    (a.output / 'validation.json').write_text(json.dumps({'passed': True, 'checks': ['name collision is infrastructure', 'collision owner preserved', 'program exit125 is implementation failure', 'request timeout is implementation failure', 'valid query passes', 'raw protocol and stderr retained', 'all owned containers removed']}, indent=2)+'\n')
    print('PASS: Docker v2 launch, crash, timeout, wire capture and cleanup checks')

if __name__ == '__main__': main()
