#!/usr/bin/env python3
"""Ad-hoc SQL console for immutable checkpoints. Never runs the study evaluator."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import queue
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'manual'
STATE = HERE / 'instances'
LABEL = 'sqlite-replication-manual=1'
IMAGE = json.loads((ROOT / 'records/runtime-image.json').read_text())['id']
ISOLATION = ['--network', 'none', '--read-only', '--cap-drop', 'ALL',
             '--security-opt', 'no-new-privileges', '--cpus', '2', '--memory', '4g',
             '--pids-limit', '128', '--tmpfs', '/tmp:rw,nosuid,size=512m']
CHOICES = ['001', '002', '003', '003-30min', '004']

def now():
    return datetime.now(timezone.utc).isoformat()

def docker(*args, **kw):
    return subprocess.run(['docker', *args], check=True, **kw)

def archive_for(run):
    name = '01800.tar.gz' if run == '003-30min' else ('interrupted-recovered.tar.gz' if run == '003' else 'final.tar.gz')
    return ROOT / 'results' / ('measured-' + run[:3]) / 'checkpoints' / name

def prepare(run):
    STATE.mkdir(parents=True, exist_ok=True)
    archive = archive_for(run)
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    meta = json.loads(archive.with_suffix('.gz.json').read_text())
    assert sha == meta['sha256'], 'Archive hash mismatch'
    statefile = STATE / (run + '.json')
    if statefile.exists():
        state = json.loads(statefile.read_text())
        assert state['archive_sha256'] == sha and state['image'] == IMAGE
        docker('volume', 'inspect', state['code_volume'], stdout=subprocess.DEVNULL)
        return state
    tag = 'sqlite-replica-manual-' + run + '-' + uuid.uuid4().hex[:8]
    code, data, build = tag + '-code', tag + '-data', tag + '-build'
    logdir = HERE / 'logs' / tag
    logdir.mkdir(parents=True)
    state = dict(run=run, archive=str(archive.relative_to(ROOT)), archive_sha256=sha,
                 checkpoint_seconds=meta['elapsed_seconds'], image=IMAGE, code_volume=code,
                 data_volume=data, build_log=str((logdir / 'build.log').relative_to(ROOT)),
                 prepared_at=now(), build_ok=False)
    print(f'Building {run} from {archive.name}; log: {ROOT / state["build_log"]}', flush=True)
    docker('volume', 'create', '--label', LABEL, code, stdout=subprocess.DEVNULL)
    docker('volume', 'create', '--label', LABEL, data, stdout=subprocess.DEVNULL)
    started = time.monotonic()
    try:
        docker('run', '-d', '--name', build, '--label', LABEL, *ISOLATION,
               '--mount', f'type=volume,source={code},target=/work', IMAGE,
               stdout=subprocess.DEVNULL)
        with archive.open('rb') as src:
            docker('exec', '-i', build, 'tar', 'xzf', '-', '-C', '/work', '--no-same-owner',
                   stdin=src, stdout=subprocess.DEVNULL)
        with (ROOT / state['build_log']).open('wb') as log:
            result = subprocess.run(['docker', 'exec', build, 'timeout', '--kill-after=2s',
                '300', 'cargo', 'build', '--release', '--offline', '--bin', 'sqlite-agent'],
                stdout=log, stderr=subprocess.STDOUT, timeout=310)
        state['build_exit_code'] = result.returncode
        state['build_ok'] = result.returncode == 0
    finally:
        subprocess.run(['docker', 'rm', '-f', build], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        state['build_elapsed_seconds'] = time.monotonic() - started
        statefile.write_text(json.dumps(state, indent=2) + '\n')
    print(f'{run}: ' + ('ready' if state['build_ok'] else 'BUILD FAILED (source preserved)'), flush=True)
    return state

class Engine:
    def __init__(self, state):
        self.state = state
        self.name = 'sqlite-replica-manual-console-' + state['run'] + '-' + uuid.uuid4().hex[:8]
        logs = HERE / 'logs'
        logs.mkdir(exist_ok=True)
        self.transcript = (logs / (self.name + '.jsonl')).open('a')
        self.stderr = (logs / (self.name + '.stderr.log')).open('a')
        self.proc = subprocess.Popen(['docker', 'run', '--rm', '-i', '--name', self.name,
            '--label', LABEL, *ISOLATION, '--workdir', '/work',
            '--mount', f'type=volume,source={state["code_volume"]},target=/code,readonly',
            '--mount', f'type=volume,source={state["data_volume"]},target=/work',
            IMAGE, '/code/target/release/sqlite-agent'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=self.stderr, text=True, bufsize=1)
        self.queue = queue.Queue()
        def read():
            for line in self.proc.stdout:
                self.queue.put(line)
            self.queue.put(None)
        threading.Thread(target=read, daemon=True).start()

    def request(self, request):
        self.transcript.write(json.dumps({'at': now(), 'request': request}) + '\n')
        self.transcript.flush()
        self.proc.stdin.write(json.dumps(request) + '\n')
        self.proc.stdin.flush()
        try:
            line = self.queue.get(timeout=30)
        except queue.Empty:
            raise RuntimeError('No response within 30 seconds; this console will shut down. Logs preserved.')
        if line is None:
            raise RuntimeError('Engine exited; see stderr log.')
        result = json.loads(line)
        self.transcript.write(json.dumps({'at': now(), 'response': result}) + '\n')
        self.transcript.flush()
        return result

    def stop(self):
        if self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=2)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                subprocess.run(['docker', 'stop', '--time', '2', self.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['docker', 'rm', '-f', self.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
        self.stderr.close()
        self.transcript.close()

def show(response, raw):
    if raw:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    elif not response.get('ok'):
        print('ERROR:', response.get('error', response))
    elif response.get('columns'):
        print(' | '.join(response['columns']))
        for row in response['rows']:
            print(' | '.join('NULL' if c['type'] == 'null' else
                ("X'" + c['value'] + "'" if c['type'] == 'blob' else json.dumps(c['value'], ensure_ascii=False) if c['type'] == 'text' else c['value'])
                for c in row))
        print(f'({len(response["rows"])} rows)')
    else:
        print('OK')

HELP = '''Enter one SQL statement per line (semicolon optional).
.open :memory:           fresh in-memory database
.open /work/demo.db      create/reopen this run's persistent database
.restart                restart the engine, reopen the same path
.raw on / .raw off       show typed JSON / readable rows
.header                 show current database's first 16 bytes
.help                   this help
.quit                   close engine; keep persistent files
No .shell/.read, multi-line SQL or sqlite3 CLI dot commands are supported.'''

def console(run):
    state = prepare(run)
    if not state['build_ok']:
        print(f'{run} is unavailable: original artifact does not build. See {ROOT / state["build_log"]}')
        if run == '003':
            print('For an explicitly older, 30-minute artifact: python3 manual/lab.py console 003-30min')
        return 1
    eng = Engine(state)
    path, raw = ':memory:', False
    print(f'Run {run} | checkpoint {state["checkpoint_seconds"]/60:.2f} minutes | SHA256 {state["archive_sha256"][:16]}')
    if run == '003-30min':
        print('HISTORICAL 30-MINUTE CHECKPOINT: not the interrupted terminal artifact or a four-hour result.')
    print('Isolated local sandbox. No model calls. Logs: ' + str(HERE / 'logs'))
    print(HELP)
    try:
        show(eng.request({'op': 'open', 'path': path}), raw)
        while True:
            try:
                line = input(f'{run}> ').strip()
            except EOFError:
                break
            if not line:
                continue
            if line == '.quit':
                show(eng.request({'op': 'close'}), raw)
                break
            if line == '.help':
                print(HELP)
            elif line.startswith('.raw '):
                if line not in ('.raw on', '.raw off'):
                    print('Use .raw on or .raw off')
                else:
                    raw = line == '.raw on'
            elif line.startswith('.open '):
                candidate = line[6:].strip()
                p = PurePosixPath(candidate)
                if candidate != ':memory:' and (not candidate.startswith('/work/') or '..' in p.parts):
                    print('Use :memory: or a file under /work/, for example /work/demo.db')
                    continue
                response = eng.request({'op': 'open', 'path': candidate})
                if response.get('ok'):
                    path = candidate
                show(response, raw)
            elif line == '.restart':
                show(eng.request({'op': 'close'}), raw)
                eng.stop()
                eng = Engine(state)
                show(eng.request({'op': 'open', 'path': path}), raw)
            elif line == '.header':
                if path == ':memory:':
                    print('Open a persistent file first.')
                else:
                    result = docker('exec', eng.name, 'head', '-c', '16', path, capture_output=True)
                    print(repr(result.stdout))
            elif line.startswith('.'):
                print('Unknown console command. Use .help')
            else:
                show(eng.request({'op': 'execute', 'sql': line}), raw)
    finally:
        eng.stop()
    return 0

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sp = ap.add_subparsers(dest='command', required=True)
    sp.add_parser('prepare').add_argument('run', choices=CHOICES + ['all'])
    sp.add_parser('console').add_argument('run', choices=CHOICES)
    sp.add_parser('status')
    sp.add_parser('stop', help='Stop only manual console containers; retain all data')
    a = ap.parse_args()
    if a.command == 'prepare':
        for run in CHOICES if a.run == 'all' else [a.run]:
            prepare(run)
    elif a.command == 'console':
        return console(a.run)
    elif a.command == 'status':
        for p in sorted(STATE.glob('*.json')):
            s = json.loads(p.read_text())
            print(s['run'], 'ready' if s['build_ok'] else 'BUILD FAILED', s['archive'], s['data_volume'])
        docker('ps', '--filter', 'label=' + LABEL, '--format', '{{.Names}}\t{{.Status}}')
    elif a.command == 'stop':
        ids = docker('ps', '-q', '--filter', 'label=' + LABEL, '--filter', 'name=sqlite-replica-manual-console-', capture_output=True, text=True).stdout.split()
        if ids:
            docker('stop', '--time', '3', *ids)
        print('Manual consoles stopped. Their database volumes and logs are retained.')
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\nConsole closed; persistent data retained.')
        sys.exit(130)
