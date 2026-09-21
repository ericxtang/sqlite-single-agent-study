"""One implementation or grading controller per replication checkout."""
import fcntl
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def acquire(path=None):
    path=Path(path) if path is not None else ROOT/'records/execution.lock'
    handle=path.open('a')
    try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close();raise RuntimeError('Another implementation/grading controller owns this checkout')
    return handle  # caller keeps the descriptor live until all children stop
