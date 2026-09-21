#!/usr/bin/env python3
"""Capture consistent source state outside a paused worker. Does not call a model."""
import argparse
import hashlib
import json
import subprocess
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


def capture(container, destination, elapsed_seconds, keep_paused=False):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError('Checkpoint exists; refusing to replace it')
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    state = json.loads(subprocess.check_output(['docker', 'inspect', '--format', '{{json .State}}', container], text=True))
    was_paused = state['Paused']
    if not state['Running']:
        raise ValueError('Checkpoint requires a running container')
    if not was_paused:
        subprocess.run(['docker', 'pause', container], check=True, stdout=subprocess.DEVNULL)
    files = []
    temporary = destination.with_suffix(destination.suffix + '.partial')
    try:
        process = subprocess.Popen(['docker', 'cp', container + ':/work/.', '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with tarfile.open(fileobj=process.stdout, mode='r|') as source, tarfile.open(temporary, mode='w:gz') as target:
            for member in source:
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('Unsafe archive path')
                parts = tuple(x for x in path.parts if x != '.')
                if parts and parts[0] == 'target':
                    continue
                # Never follow links into host files when later reconstructing a snapshot.
                if not (member.isfile() or member.isdir() or member.issym()):
                    raise ValueError('Unsupported special file in source checkpoint')
                member.name = '/'.join(parts) or '.'
                if member.issym():
                    link = PurePosixPath(member.linkname)
                    if link.is_absolute() or '..' in link.parts:
                        raise ValueError('External symlink in source checkpoint')
                data = source.extractfile(member) if member.isfile() else None
                target.addfile(member, data)
                files.append({'path': member.name, 'bytes': member.size, 'type': member.type.decode('ascii')})
        error = process.stderr.read().decode()
        if process.wait() != 0:
            raise RuntimeError('Docker checkpoint copy failed: ' + error)
        temporary.rename(destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        report = {'container': container, 'elapsed_seconds': elapsed_seconds, 'started_at': started, 'capture_seconds': time.monotonic() - t0, 'sha256': digest, 'archive': destination.name, 'excluded_top_level': ['target'], 'files': files}
        destination.with_suffix(destination.suffix + '.json').write_text(json.dumps(report, indent=2) + '\n')
        return report
    finally:
        if not was_paused and not keep_paused:
            subprocess.run(['docker', 'unpause', container], check=True, stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--container', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    print(json.dumps(capture(args.container, args.output, 0), indent=2))
