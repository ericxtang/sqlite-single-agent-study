#!/usr/bin/env python3
"""Fetch the official versioned documentation archive and verify its published hash."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://www.sqlite.org/2026/sqlite-doc-3530400.zip'
EXPECTED = '7ccf86a52e7dd1fb9b31e63edcebe3b553f18f89cd26eef59c7f191a5111836e'


def main():
    dest = ROOT / 'downloads' / 'sqlite-doc-3530400.zip'
    dest.parent.mkdir(exist_ok=True)
    if not dest.exists():
        data = urllib.request.urlopen(URL, timeout=90).read()
    else:
        data = dest.read_bytes()
    actual = hashlib.sha3_256(data).hexdigest()
    if actual != EXPECTED:
        raise SystemExit('Official documentation archive checksum mismatch; refusing to use it.')
    dest.write_bytes(data)
    with zipfile.ZipFile(dest) as archive:
        names = archive.namelist()
    report = {'url': URL, 'version': '3.53.4', 'sha3_256': actual, 'bytes': len(data), 'files': names}
    (ROOT / 'records/docs-archive.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'url': URL, 'verified': True, 'bytes': len(data), 'files': len(names)}, indent=2))


if __name__ == '__main__':
    main()
