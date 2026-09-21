"""Owned Docker containers with launch evidence and checked cleanup (v2)."""
import json
import re
import subprocess
import time
import uuid
from pathlib import Path

COMMON = ['--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt',
          'no-new-privileges', '--cpus', '4', '--memory', '4g', '--pids-limit', '128',
          '--tmpfs', '/tmp:rw,nosuid,size=512m']

class InfrastructureError(RuntimeError):
    """Must bypass the frozen scorer's implementation-failure exception handlers."""


def command(args, **kwargs):
    try:
        return subprocess.run(['docker', *args], capture_output=True, timeout=30, **kwargs)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InfrastructureError('Docker control command failed: ' + repr(args)) from exc


def checked(args, **kwargs):
    result = command(args, **kwargs)
    if result.returncode:
        raise InfrastructureError('Docker control command failed: ' + repr(args) + ': ' + result.stderr.decode(errors='replace'))
    return result.stdout.decode().strip()


class Container:
    def __init__(self, image, options, argv, evidence, name=None):
        self.evidence = Path(evidence)
        self.evidence.mkdir(parents=True, exist_ok=False)
        self.name = name or 'sqlite-eval-v2-' + uuid.uuid4().hex
        self.id = None
        self.closed = False
        args = ['create', '-i', '--name', self.name, '--label', 'sqlite-evaluator=v2', *COMMON, *options, image, *argv]
        self.record = {'name': self.name, 'image': image, 'create_argv': ['docker', *args], 'events': []}
        result = command(args)
        (self.evidence / 'create.stderr').write_bytes(result.stderr)
        self.record['create_exit_code'] = result.returncode
        candidate = result.stdout.decode().strip()
        if result.returncode == 0 and re.fullmatch('[a-f0-9]{64}', candidate):
            self.id = candidate
        self.record['container_id'] = self.id
        self.save()
        if not self.id:
            # In particular, never remove a pre-existing name collision.
            raise InfrastructureError('Container creation failed; inspect ' + str(self.evidence))

    def save(self):
        try:
            (self.evidence / 'container.json').write_text(json.dumps(self.record, indent=2) + '\n')
        except OSError as exc:
            raise InfrastructureError('Could not retain container evidence') from exc

    def inspect(self, phase):
        try:
            value = json.loads(checked(['inspect', self.id]))[0]
            state = value['State']
            if not isinstance(state, dict) or 'Running' not in state or 'StartedAt' not in state:
                raise ValueError('Missing container state')
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise InfrastructureError('Malformed Docker inspection response') from exc
        entry = {'phase': phase, 'monotonic': time.monotonic(), 'state': value['State']}
        self.record['events'].append(entry)
        self.save()
        return value['State']

    @staticmethod
    def require_started(state):
        if state.get('Error') or not state.get('StartedAt') or state['StartedAt'].startswith('0001-'):
            raise InfrastructureError('No successful container launch: ' + repr(state))

    def await_started(self, process):
        deadline = time.monotonic() + 15
        while True:
            state = self.inspect('launch')
            if state.get('Error'):
                self.require_started(state)
            if state.get('StartedAt') and not state['StartedAt'].startswith('0001-'):
                self.require_started(state)
                return
            if process.poll() is not None or time.monotonic() >= deadline:
                raise InfrastructureError('Docker start/attach failed before confirmed launch')
            time.sleep(.05)

    def check_runtime(self, process, phase):
        state = self.inspect(phase)
        self.require_started(state)
        # A nonzero host launcher exit while the container is still running is
        # a broken attachment, not evidence that the generated program failed.
        code = process.poll()
        if state.get('Running') and code not in (None, 0):
            raise InfrastructureError('Docker attachment exited while container remained live')
        self.record['launcher_exit_code_before_cleanup'] = code
        self.save()
        return state

    def run(self, logfile, timeout=310):
        with Path(logfile).open('wb') as log:
            proc = subprocess.Popen(['docker', 'start', '-a', self.id], stdout=log, stderr=subprocess.STDOUT)
            try:
                self.await_started(proc)
                proc.wait(timeout=timeout)
                state = self.check_runtime(proc, 'command_exit')
                if state['Running'] or state['ExitCode'] != proc.returncode:
                    raise InfrastructureError('Container and launcher completion disagree')
                return state['ExitCode']
            except subprocess.TimeoutExpired as exc:
                # The in-container timeout is authoritative. A host/daemon hang
                # does not establish a compiler timeout or a valid build zero.
                raise InfrastructureError('Host Docker wait timed out') from exc
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=5)

    def start_keeper(self):
        checked(['start', self.id])
        state = self.inspect('keeper_started')
        self.require_started(state)
        if not state['Running']:
            raise InfrastructureError('Keeper exited unexpectedly')

    def close(self):
        if self.closed or not self.id:
            return
        # Only the full ID returned by OUR successful create may be removed.
        result = command(['rm', '-f', self.id])
        self.record['remove_exit_code'] = result.returncode
        self.record['remove_stderr'] = result.stderr.decode(errors='replace')
        remaining = checked(['container', 'ls', '--all', '--no-trunc', '--filter', 'id=' + self.id, '--format', '{{.ID}}'])
        self.record['cleanup_confirmed'] = not remaining.strip()
        self.save()
        if remaining.strip():
            raise InfrastructureError('Container cleanup not confirmed: ' + self.id)
        self.closed = True


def volume_create(name):
    checked(['volume', 'create', name])
    return name


def volume_remove(name):
    checked(['volume', 'rm', name])
    if name in checked(['volume', 'ls', '--format', '{{.Name}}']).splitlines():
        raise InfrastructureError('Volume cleanup not confirmed: ' + name)
