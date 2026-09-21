#!/usr/bin/env python3
"""Additive v2 evaluator; never overwrites an evaluation or modifies a checkpoint."""
import argparse
import hashlib
import json
import signal
import sqlite3
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Frozen scoring semantics; v2's process/secondary modules take precedence.
sys.path.insert(1, str(ROOT / 'evaluator'))
from slt import Normalizer, score_file
from container import Container, InfrastructureError, checked, volume_create, volume_remove
from process import JsonProcess
REVISION = 'launch-evidence-blob-bytes-v2'


def evaluate(archive, output, image, suite='primary', limit_files=None):
    archive, output = Path(archive).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    checkpoint = json.loads(archive.with_suffix(archive.suffix + '.json').read_text())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != checkpoint['sha256']:
        raise InfrastructureError('Checkpoint hash mismatch')
    manifest = json.loads((ROOT / 'records/corpus-manifest.json').read_text())
    selected = manifest['files'][:limit_files] if limit_files else manifest['files']
    start = time.monotonic()
    summary = {'evaluator_revision': REVISION, 'suite': suite, 'checkpoint_sha256': checkpoint['sha256'],
               'checkpoint_elapsed_seconds': checkpoint['elapsed_seconds'], 'diagnostic_subset': limit_files is not None,
               'files_scored': 0, 'image': image, 'reference_sqlite_version': sqlite3.sqlite_version,
               'build_ok': False, 'evaluation_complete': False}
    totals = {'queries': sum(f['queries'] for f in selected), 'queries_passed': 0,
              'statements': sum(f['statements'] for f in selected), 'statements_passed': 0}
    resources = []
    volume = None
    evidence = output / 'evidence'
    evidence.mkdir()
    def save():
        summary['evaluation_elapsed_seconds'] = time.monotonic() - start
        if suite == 'primary':
            summary.update(totals)
            summary['queries_failed'] = totals['queries'] - totals['queries_passed'] if summary['evaluation_complete'] else None
            summary['score'] = totals['queries_passed'] / totals['queries'] if totals['queries'] and summary['evaluation_complete'] else None
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    save()
    try:
        inspected = json.loads(checked(['image', 'inspect', image]))[0]
        if inspected['Id'] != image:
            raise InfrastructureError('Use an immutable image SHA256, not a mutable tag')
        summary['image_architecture'] = inspected['Architecture']
        volume = volume_create('sqlite-eval-v2-code-' + uuid.uuid4().hex)
        options = ['--mount', f'type=volume,source={volume},target=/work']
        keeper = Container(image, options, ['sleep', 'infinity'], evidence / 'source-extraction')
        resources.append(keeper)
        keeper.start_keeper()
        with archive.open('rb') as source:
            checked(['exec', '-i', keeper.id, 'tar', 'xzf', '-', '-C', '/work', '--no-same-owner'], stdin=source)
        compiler = Container(image, options, ['timeout', '--kill-after=2s', '300', 'cargo', 'build', '--release', '--offline', '--bin', 'sqlite-agent'], evidence / 'build')
        resources.append(compiler)
        code = compiler.run(output / 'build.log')
        summary['build_exit_code'] = code
        summary['build_ok'] = code == 0
        compiler.close()
        if not summary['build_ok']:
            if suite == 'secondary':
                from secondary import CASE_NAMES
                summary['secondary'] = {'cases': [{'case': n, 'passed': False, 'reason': 'Build unavailable'} for n in CASE_NAMES], 'passed': 0, 'total': len(CASE_NAMES)}
            summary['evaluation_complete'] = True
        elif suite == 'secondary':
            from secondary import run_suite
            from secondary_docker import DockerLab
            lab = DockerLab(image, volume, evidence)
            resources.append(lab)
            summary['secondary'] = run_suite(lab)
            lab.close()
            resources.remove(lab)
            summary['evaluation_complete'] = True
        else:
            normalizer = Normalizer()
            for index, entry in enumerate(selected):
                path = ROOT / 'private/corpus/checkout/test' / entry['path']
                if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                    raise InfrastructureError('Corpus hash changed: ' + entry['path'])
                directory = evidence / f'file-{index:04d}'
                engine = JsonProcess(image, ['--workdir', '/tmp', '--mount', f'type=volume,source={volume},target=/code,readonly'],
                                     ['timeout', '--kill-after=2s', '300', '/code/target/release/sqlite-agent'], directory)
                try:
                    result = score_file(path, engine, normalizer)
                finally:
                    engine.close()
                # Only append accepted per-file results AFTER checked cleanup.
                totals['queries_passed'] += result['queries_passed']
                totals['statements_passed'] += result['statements_passed']
                summary['files_scored'] += 1
                with (output / 'files.jsonl').open('a') as log:
                    log.write(json.dumps({'path': entry['path'], 'evidence': str(directory.relative_to(output)), **result}) + '\n')
                save()
                if summary['files_scored'] % 10 == 0:
                    print(json.dumps({'files_scored': summary['files_scored'], **totals}), flush=True)
            summary['evaluation_complete'] = True
    except BaseException as exc:
        summary['evaluation_complete'] = False
        summary['evaluation_error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        errors = []
        for resource in reversed(resources):
            try: resource.close()
            except Exception as exc: errors.append(str(exc))
        if volume:
            try: volume_remove(volume)
            except Exception as exc: errors.append(str(exc))
        if errors:
            summary['evaluation_complete'] = False
            summary['cleanup_errors'] = errors
        save()
        print(json.dumps(summary), flush=True)
    if not summary['evaluation_complete']:
        raise InfrastructureError('Evaluation incomplete; preserved for review')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--suite', choices=['primary', 'secondary'], default='primary')
    parser.add_argument('--limit-files', type=int)
    args = parser.parse_args()
    if args.limit_files is not None and (args.limit_files <= 0 or args.suite != 'primary'):
        parser.error('--limit-files must be positive and primary only')
    def stop(*_):
        raise KeyboardInterrupt('Evaluation stopped; preserving incomplete evidence')
    signal.signal(signal.SIGTERM, stop)
    evaluate(args.archive, args.output, args.image, args.suite, args.limit_files)

if __name__ == '__main__':
    main()
