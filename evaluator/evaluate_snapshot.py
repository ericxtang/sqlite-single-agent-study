#!/usr/bin/env python3
"""Build and grade a checkpoint without exposing corpus or answers to generated code."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from process import JsonProcess
from slt import Normalizer, score_file

ROOT = Path(__file__).resolve().parents[1]


def docker_cleanup(name):
    subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--archive', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--limit-files', type=int, help='Diagnostic subset only; never a primary result')
    p.add_argument('--suite', choices=['primary', 'secondary'], default='primary')
    args = p.parse_args()
    if args.limit_files is not None and (args.limit_files <= 0 or args.suite != 'primary'):
        p.error('--limit-files must be positive and used only with the primary suite')
    archive = Path(args.archive).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    checkpoint = json.loads(archive.with_suffix(archive.suffix + '.json').read_text())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != checkpoint['sha256']:
        raise SystemExit('Checkpoint hash mismatch')
    manifest = json.loads((ROOT / 'records/corpus-manifest.json').read_text())
    image = json.loads((ROOT / 'records/runtime-image.json').read_text())['id']
    unique = uuid.uuid4().hex[:12]
    build_name = 'astra-sqlite-eval-build-' + unique
    volume = build_name + '-work'
    engine_name = 'astra-sqlite-eval-engine-' + unique
    common = ['--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--cpus', '4', '--memory', '4g', '--pids-limit', '128', '--tmpfs', '/tmp:rw,nosuid,size=512m']
    start = time.monotonic()
    totals = {'queries': manifest['totals']['queries'], 'queries_passed': 0, 'statements': manifest['totals']['statements'], 'statements_passed': 0}
    summary = {'suite': args.suite, 'checkpoint_sha256': checkpoint['sha256'], 'checkpoint_elapsed_seconds': checkpoint['elapsed_seconds'], 'diagnostic_subset': args.limit_files is not None, 'files_scored': 0, 'image': image, 'build_ok': False, 'evaluation_complete': False}
    selected = manifest['files'][:args.limit_files] if args.limit_files else manifest['files']
    if args.limit_files:
        totals['queries'] = sum(f['queries'] for f in selected)
        totals['statements'] = sum(f['statements'] for f in selected)
    if args.suite == 'secondary':
        from secondary import CASE_NAMES
        summary['secondary'] = {'cases': [{'case': name, 'passed': False, 'reason': 'Build unavailable'} for name in CASE_NAMES], 'passed': 0, 'total': len(CASE_NAMES)}
    try:
        subprocess.run(['docker', 'run', '-d', '--name', build_name, *common, '--mount', f'type=volume,source={volume},target=/work', image], check=True, stdout=subprocess.DEVNULL)
        # Extraction occurs inside the isolated build container, never on the host.
        with archive.open('rb') as source:
            subprocess.run(['docker', 'exec', '-i', build_name, 'tar', 'xzf', '-', '-C', '/work', '--no-same-owner'], stdin=source, check=True, capture_output=True)
        with (output / 'build.log').open('wb') as log:
            result = subprocess.run(['docker', 'exec', build_name, 'timeout', '--kill-after=2s', '300', 'cargo', 'build', '--release', '--offline', '--bin', 'sqlite-agent'], stdout=log, stderr=subprocess.STDOUT, timeout=310)
        summary['build_ok'] = result.returncode == 0
        if not summary['build_ok']:
            summary['build_exit_code'] = result.returncode
            summary['evaluation_complete'] = True
        elif args.suite == 'secondary':
            from secondary import run_suite
            from secondary_docker import DockerLab
            lab = DockerLab(image, volume, engine_name, common)
            try:
                summary['secondary'] = run_suite(lab)
            finally:
                lab.close()
            summary['evaluation_complete'] = True
        else:
            normalizer = Normalizer()
            for entry in selected:
                path = ROOT / 'private/corpus/checkout/test' / entry['path']
                if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                    raise RuntimeError('Corpus hash changed: ' + entry['path'])
                # A fresh container per file has no reference data, test files, or writable source.
                engine = JsonProcess(['docker', 'run', '--rm', '-i', '--name', engine_name, *common, '--workdir', '/tmp', '--mount', f'type=volume,source={volume},target=/code,readonly', image, 'timeout', '--kill-after=2s', '300', '/code/target/release/sqlite-agent'])
                try:
                    result = score_file(path, engine, normalizer)
                finally:
                    engine.close()
                    docker_cleanup(engine_name)
                totals['queries_passed'] += result['queries_passed']
                totals['statements_passed'] += result['statements_passed']
                summary['files_scored'] += 1
                with (output / 'files.jsonl').open('a') as f:
                    f.write(json.dumps({'path': entry['path'], **result}) + '\n')
                if summary['files_scored'] % 10 == 0:
                    print(json.dumps({'files_scored': summary['files_scored'], **totals}), flush=True)
            summary['evaluation_complete'] = True
    except subprocess.TimeoutExpired:
        summary['evaluation_error'] = 'Build deadline reached'
        summary['evaluation_complete'] = True
    except Exception as exc:
        summary['evaluation_error'] = str(exc)
        raise
    finally:
        docker_cleanup(engine_name)
        docker_cleanup(build_name)
        subprocess.run(['docker', 'volume', 'rm', volume], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if args.suite == 'primary':
            summary.update(totals)
            summary['queries_failed'] = totals['queries'] - totals['queries_passed']
            summary['score'] = totals['queries_passed'] / totals['queries'] if totals['queries'] and summary['evaluation_complete'] else None
        summary['evaluation_elapsed_seconds'] = time.monotonic() - start
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
