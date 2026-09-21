"""Bounded JSON-lines protocol client for isolated generated programs."""
import json
import os
import queue
import signal
import subprocess
import threading


class JsonProcess:
    def __init__(self, argv, timeout=10, max_bytes=16 * 1024**2):
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.queue = queue.Queue(maxsize=2)
        self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        self.stopped = threading.Event()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while not self.stopped.is_set():
                line = self.process.stdout.readline(self.max_bytes + 1)
                if not line:
                    item = EOFError('Engine stdout closed')
                elif len(line) > self.max_bytes:
                    item = ValueError('Engine response exceeds byte limit')
                else:
                    item = line
                while not self.stopped.is_set():
                    try:
                        self.queue.put(item, timeout=0.1)
                        break
                    except queue.Full:
                        continue
                if isinstance(item, Exception):
                    return
        except (OSError, ValueError) as exc:
            try:
                self.queue.put(exc, timeout=0.1)
            except queue.Full:
                pass

    def request(self, request):
        try:
            self.process.stdin.write((json.dumps(request, ensure_ascii=True) + '\n').encode())
            self.process.stdin.flush()
        except (OSError, ValueError) as exc:
            raise OSError('Engine input closed') from exc
        try:
            line = self.queue.get(timeout=self.timeout)
        except queue.Empty as exc:
            raise TimeoutError('Engine request deadline reached') from exc
        if isinstance(line, Exception):
            raise OSError(str(line))
        try:
            reply = json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise ValueError('Engine emitted invalid JSON') from exc
        if not isinstance(reply, dict):
            raise ValueError('Engine response must be an object')
        return reply

    def close(self):
        self.stopped.set()
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGKILL)
        self.process.wait(timeout=5)
        for stream in (self.process.stdin, self.process.stdout):
            try:
                stream.close()
            except (OSError, ValueError):
                pass
