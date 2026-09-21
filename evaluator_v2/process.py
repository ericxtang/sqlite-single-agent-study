"""Frozen JSON protocol semantics with retained wire bytes and launch checks."""
import gzip
import importlib.util
import json
import queue
import subprocess
import threading
from pathlib import Path
from container import Container, InfrastructureError

_spec = importlib.util.spec_from_file_location('v1_process', Path(__file__).resolve().parents[1] / 'evaluator/process.py')
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

class JsonProcess(_module.JsonProcess):
    def __init__(self, image, options, argv, evidence, name=None, timeout=10, max_bytes=16 * 1024**2):
        self.container = Container(image, options, argv, evidence, name=name)
        self.timeout, self.max_bytes = timeout, max_bytes
        self.queue = queue.Queue(maxsize=2)
        self.stopped = threading.Event()
        self.closed = False
        self.wire_lock = threading.Lock()
        self.wire = self.stderr = None
        try:
            self.wire = gzip.open(Path(evidence) / 'protocol.bin.gz', 'wb', compresslevel=1)
            self.stderr = (Path(evidence) / 'stderr.log').open('wb')
            self.process = subprocess.Popen(['docker', 'start', '-a', '-i', self.container.id], stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=self.stderr, start_new_session=True)
            self.reader = threading.Thread(target=self._read_logged, daemon=True)
            self.reader.start()
            self.container.await_started(self.process)
        except BaseException:
            self.close()
            raise

    def record_bytes(self, direction, data):
        # Lossless framing, including invalid UTF-8/JSON; gzip only compresses.
        try:
            with self.wire_lock:
                self.wire.write(direction + str(len(data)).encode() + b'\n' + data)
        except OSError as exc:
            raise InfrastructureError('Could not retain raw protocol evidence') from exc

    def _read_logged(self):
        try:
            while not self.stopped.is_set():
                line = self.process.stdout.readline(self.max_bytes + 1)
                self.record_bytes(b'<', line)
                item = EOFError('Engine stdout closed') if not line else ValueError('Engine response exceeds byte limit') if len(line) > self.max_bytes else line
                while not self.stopped.is_set():
                    try:
                        self.queue.put(item, timeout=.1)
                        break
                    except queue.Full:
                        pass
                if isinstance(item, Exception):
                    return
        except Exception as exc:
            while not self.stopped.is_set():
                try:
                    self.queue.put(InfrastructureError('Protocol reader failed: ' + repr(exc)), timeout=.1)
                    return
                except queue.Full:
                    pass

    def request(self, request):
        data = (json.dumps(request, ensure_ascii=True) + '\n').encode()
        self.record_bytes(b'>', data)
        try:
            try:
                self.process.stdin.write(data)
                self.process.stdin.flush()
            except (OSError, ValueError) as exc:
                raise OSError('Engine input closed') from exc
            try:
                line = self.queue.get(timeout=self.timeout)
            except queue.Empty as exc:
                raise TimeoutError('Engine request deadline reached') from exc
            if isinstance(line, InfrastructureError):
                raise line
            if isinstance(line, Exception):
                raise OSError(str(line))
            try:
                reply = json.loads(line)
            except (ValueError, UnicodeError) as exc:
                raise ValueError('Engine emitted invalid JSON') from exc
            if not isinstance(reply, dict):
                raise ValueError('Engine response must be an object')
            return reply
        except (OSError, TimeoutError, ValueError):
            self.container.check_runtime(self.process, 'request_failure')
            raise

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.stopped.set()
        errors = []
        proc = getattr(self, 'process', None)
        try:
            if proc:
                self.container.check_runtime(proc, 'before_cleanup')
        except Exception as exc:
            errors.append(exc)
        try:
            self.container.close()
        except Exception as exc:
            errors.append(exc)
        if proc:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            self.container.record['launcher_exit_code_after_cleanup'] = proc.returncode
            self.container.save()
            for stream in (proc.stdin, proc.stdout):
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass
        if hasattr(self, 'reader'):
            self.reader.join(timeout=5)
            if self.reader.is_alive():
                errors.append(InfrastructureError('Protocol reader cleanup not confirmed'))
        if self.stderr:
            self.stderr.close()
        with self.wire_lock:
            if self.wire:
                self.wire.close()
        if errors:
            raise InfrastructureError('; '.join(map(str, errors)))
