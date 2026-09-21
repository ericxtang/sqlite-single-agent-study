#!/usr/bin/env python3
"""Run a bounded single-agent trajectory with offline tools and external checkpoints."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from checkpoint import capture
from runtime_config import ROOT, config_text
from integrity import verify


def now():
    return datetime.now(timezone.utc).isoformat()


def command(args):
    return subprocess.check_output(args, text=True).strip()


def stop_process(process):
    if process is None or process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['pilot', 'measured'], required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--seconds', type=int)
    p.add_argument('--allow-inference', action='store_true')
    args = p.parse_args()
    if not args.allow_inference:
        p.error('--allow-inference is required; this consumes your own Codex allowance')
    if not args.run_id.startswith('replicate-'):
        raise SystemExit('Fresh replication IDs must start with replicate-')
    from execution_lock import acquire
    execution_guard = acquire()
    verify()
    if not all(c.isalnum() or c in '-_' for c in args.run_id):
        raise SystemExit('Invalid run ID')
    config = json.loads((ROOT / 'study.json').read_text())
    if config['billing_mode'] != 'codex_subscription':
        raise SystemExit('This runner is for the authorized subscription mode only')
    if not config['isolation_validated'] or not config['runner_validated']:
        raise SystemExit('Isolation and infrastructure validation have not passed')
    if args.mode == 'measured' and not (config['protocol_frozen'] and config['measured_runs_enabled'] and config['evaluator_validated']):
        raise SystemExit('Measured-run gate is closed')
    freeze_sha256 = verify() if args.mode == 'measured' else None
    if command(['docker', 'ps', '-q', '--filter', 'label=study=sqlite-single-agent']):
        raise SystemExit('Another implementation worker is running; serial execution required')
    container = 'astra-sqlite-replication-' + args.run_id
    for inspect in (['docker', 'container', 'inspect', container], ['docker', 'volume', 'inspect', container + '-work']):
        if subprocess.run(inspect, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            raise SystemExit('Run container/volume already exists; a fresh workspace is required')
    seconds = config['pilot_approved_seconds'] if args.mode == 'pilot' else config['primary_endpoint_seconds']
    if args.seconds is not None:
        if args.mode == 'measured' or args.seconds > seconds or args.seconds <= 0:
            raise SystemExit('Duration override may only shorten an operational pilot')
        seconds = args.seconds
    run = ROOT / 'runs' / args.run_id
    run.mkdir(parents=True, exist_ok=False)
    os.chmod(run, 0o700)
    runtime = run / 'runtime'
    runtime.mkdir(mode=0o700)
    auth_root = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).resolve()
    auth = auth_root / 'auth.json'
    if not auth.is_file():
        raise SystemExit('Subscription credential file unavailable; no billing fallback is permitted')
    (runtime / 'auth.json').symlink_to(auth)
    driver = Path(tempfile.mkdtemp(prefix='offline-rust-work-')).resolve()
    audit = run / 'tools.jsonl'
    (runtime / 'config.toml').write_text(config_text(runtime, container, audit))
    image = json.loads((ROOT / 'records/runtime-image.json').read_text())['id']
    manifest = {'mode': args.mode, 'run_id': args.run_id, 'created_at': now(), 'duration_seconds': seconds, 'model': config['model'], 'reasoning_effort': config['reasoning_effort'], 'billing_mode': config['billing_mode'], 'service_tier': 'default', 'image': image, 'container': container, 'state': 'preparing', 'thread_id': None, 'independent_implementation_agents': 1, 'cpu_limit': 4, 'memory_limit_bytes': 4 * 1024**3, 'files': {}}
    for rel in ['study.json', 'PROTOCOL.md', 'SCORING.md', 'inputs/TASK.md', 'inputs/CONTINUE.md', 'inputs/IO_CONTRACT.md', 'records/documentation-manifest.json', 'records/corpus-manifest.json', 'records/astra-mcp-only-catalog.json', 'replication/run.py', 'replication/runtime_config.py', 'replication/container_tools.py', 'replication/checkpoint.py']:
        manifest['files'][rel] = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    manifest['runtime_config_sha256'] = hashlib.sha256((runtime / 'config.toml').read_bytes()).hexdigest()
    manifest['freeze_sha256'] = freeze_sha256
    manifest['actual_controller_path'] = str(Path(__file__).relative_to(ROOT))
    manifest['actual_controller_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest['controller_basis'] = 'amendment-001 with documented portability changes'
    manifest['original_study_run'] = False
    (run / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    def terminate(signum, frame):
        raise KeyboardInterrupt('Controller received stop signal')
    signal.signal(signal.SIGTERM, terminate)
    try:
        subprocess.run(['docker', 'run', '-d', '--name', container, '--label', 'study=sqlite-single-agent', '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--cpus', '4', '--memory', '4g', '--pids-limit', '256', '--tmpfs', '/tmp:rw,nosuid,size=512m', '--mount', f'type=volume,source={container}-work,target=/work', '--mount', f'type=bind,source={ROOT / "inputs/manual"},target=/docs,readonly', image], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['docker', 'exec', '-i', '--user', '1000:1000', container, 'bash', '-c', 'cat > /work/IO_CONTRACT.md'], input=(ROOT / 'inputs/IO_CONTRACT.md').read_bytes(), check=True)
        capture(container, run / 'checkpoints/00000.tar.gz', 0)
    except BaseException as exc:
        subprocess.run(['docker', 'kill', '--signal', 'KILL', container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        manifest.update(state='preparation_failed', error=str(exc))
        (run / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        raise
    clean_env = {'PATH': os.environ['PATH'], 'HOME': str(runtime), 'CODEX_HOME': str(runtime), 'TMPDIR': str(driver), 'LANG': 'en_US.UTF-8', 'TZ': 'America/New_York'}
    process = None
    stderr_file = (run / 'runner-stderr.log').open('a')
    events = (run / 'events.jsonl').open('a', buffering=1)
    q = queue.Queue()
    thread_id = None
    turn = 0
    consecutive_failures = 0
    first = True
    interrupted = False
    def terminate(signum, frame):
        raise KeyboardInterrupt('Controller received stop signal')
    signal.signal(signal.SIGTERM, terminate)
    t0 = time.monotonic()
    deadline = t0 + seconds
    next_checkpoint = t0 + (min(300, seconds) if args.mode == 'pilot' else 900)
    manifest.update(state='running', started_at=now(), controller_pid=os.getpid())
    (run / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'event': 'started', 'run_id': args.run_id, 'duration_seconds': seconds, 'at': now()}), flush=True)

    def consume(stream):
        for line in stream:
            q.put(line)

    def log_event(line):
        nonlocal thread_id
        try:
            data = json.loads(line)
        except ValueError:
            data = {'unparsed': line.rstrip()}
        events.write(json.dumps({'at': now(), 'elapsed_seconds': time.monotonic() - t0, 'turn': turn, 'event': data}) + '\n')
        if data.get('type') == 'thread.started':
            candidate = data['thread_id']
            if thread_id and candidate != thread_id:
                raise RuntimeError('Resume changed the implementation trajectory')
            thread_id = candidate
            manifest['thread_id'] = candidate
            (run / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        if data.get('type') in ('error', 'turn.failed') and re.search(r'usage.?limit|insufficient.?quota|quota.?exceeded|rate.?limit|authentication|unauthorized|refresh.?token', json.dumps(data), re.I):
            raise RuntimeError('Account/authentication/rate-limit failure; no reset or billing fallback permitted')

    try:
        while time.monotonic() < deadline:
            if (ROOT / 'records/STOP').exists():
                raise KeyboardInterrupt('STOP file observed')
            if process is None:
                turn += 1
                prompt = (ROOT / ('inputs/TASK.md' if first else 'inputs/CONTINUE.md')).read_text()
                argv = ['codex', 'exec', '--strict-config', '--json', '--skip-git-repo-check']
                if first:
                    argv += ['-C', str(driver), prompt]
                else:
                    if thread_id is None:
                        raise RuntimeError('No trajectory ID to resume')
                    argv += ['resume', thread_id, prompt]
                process = subprocess.Popen(argv, cwd=driver, env=clean_env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=stderr_file, text=True, start_new_session=True, bufsize=1)
                threading.Thread(target=consume, args=(process.stdout,), daemon=True).start()
                first = False
            try:
                log_event(q.get(timeout=min(0.25, max(0.01, deadline - time.monotonic()))))
            except queue.Empty:
                pass
            if time.monotonic() >= deadline:
                break
            if time.monotonic() >= next_checkpoint:
                elapsed = time.monotonic() - t0
                checkpoint = capture(container, run / f'checkpoints/{int(elapsed):05d}.tar.gz', elapsed)
                print(json.dumps({'event': 'checkpoint', 'elapsed_seconds': elapsed, 'capture_seconds': checkpoint['capture_seconds']}), flush=True)
                next_checkpoint = t0 + ((int(elapsed) // 900) + 1) * 900
            if process.poll() is not None:
                time.sleep(0.05)
                while not q.empty():
                    log_event(q.get_nowait())
                code = process.returncode
                events.write(json.dumps({'at': now(), 'elapsed_seconds': time.monotonic() - t0, 'controller': 'turn_exit', 'returncode': code}) + '\n')
                consecutive_failures = consecutive_failures + 1 if code else 0
                if consecutive_failures >= 3:
                    raise RuntimeError('Three consecutive runner failures; preserving interrupted run')
                if code:
                    time.sleep(min(15 * 2**(consecutive_failures - 1), max(0, deadline - time.monotonic())))
                process = None
    except (KeyboardInterrupt, Exception) as exc:
        interrupted = True
        manifest['error'] = str(exc)
        print(json.dumps({'event': 'interrupted', 'reason': str(exc)}), flush=True)
    finally:
        # Preserve the paused artifact even when duplicate failure events arrive.
        cleanup_errors = []
        paused = False
        final_captured = False
        try:
            subprocess.run(['docker', 'pause', container], check=True, stdout=subprocess.DEVNULL)
            paused = True
        except Exception as exc:
            cleanup_errors.append('pause: ' + str(exc))
        stopped_at = time.monotonic()
        stopped_timestamp = now()
        try:
            stop_process(process)
        except Exception as exc:
            cleanup_errors.append('stop model process: ' + str(exc))
        while not q.empty():
            try:
                log_event(q.get_nowait())
            except Exception as exc:
                cleanup_errors.append('drained event: ' + str(exc))
        try:
            if not paused:
                raise RuntimeError('Worker pause failed; no valid endpoint can be captured')
            capture(container, run / 'checkpoints/final.tar.gz', stopped_at - t0, keep_paused=True)
            final_captured = True
        except Exception as exc:
            cleanup_errors.append('capture: ' + str(exc))
        finally:
            # KILL also works on a paused worker; no source writes resume after capture.
            try:
                subprocess.run(['docker', 'kill', '--signal', 'KILL', container], check=True, stdout=subprocess.DEVNULL)
            except Exception as exc:
                cleanup_errors.append('kill worker: ' + str(exc))
        interrupted = interrupted or bool(cleanup_errors)
        manifest.update(state='interrupted' if interrupted else 'completed', stopped_at=stopped_timestamp,
                        actual_elapsed_seconds=stopped_at - t0, turns=turn,
                        final_checkpoint_captured=final_captured, cleanup_errors=cleanup_errors)
        (run / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        events.close()
        stderr_file.close()
        print(json.dumps({'event': manifest['state'], 'run_id': args.run_id, 'elapsed_seconds': manifest['actual_elapsed_seconds']}), flush=True)

    if interrupted:
        raise SystemExit('Run interrupted; audit preserved artifacts before another launch')
    if stopped_at - t0 > seconds + 1:
        raise SystemExit('Endpoint exceeded one-second overshoot threshold; requires recorded audit review')


if __name__ == '__main__':
    main()
