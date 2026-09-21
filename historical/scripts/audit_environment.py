#!/usr/bin/env python3
"""No-model checks for offline tool access and exported model-visible capabilities."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    probe = json.loads((ROOT / 'records/tool-surface-probe.json').read_text())
    if len(probe['requests']) != 2:
        raise SystemExit('Tool probe incomplete')
    request = probe['requests'][0]
    assert request['model'] == 'gpt-6-astra'
    assert request['reasoning']['effort'] == 'xhigh'
    assert '<skills_instructions>' not in json.dumps(request)
    outputs = [item for item in probe['requests'][1]['input'] if item.get('type') == 'custom_tool_call_output']
    assert len(outputs) == 1
    content = outputs[0]['output']
    names = json.loads(content[1]['text'])
    assert set(names) == {'clock__curr_time', 'list_mcp_resource_templates', 'list_mcp_resources', 'mcp__workspace__exec', 'read_mcp_resource'}
    assert 'bridge-ok' in json.dumps(content[2])
    assert 'requires approval' not in json.dumps(content)
    details = json.loads(subprocess.check_output(['docker', 'inspect', 'astra-sqlite-probe'], text=True))[0]
    assert details['HostConfig']['NetworkMode'] == 'none'
    assert details['HostConfig']['ReadonlyRootfs']
    assert details['Config']['User'] == 'agent'
    assert details['HostConfig']['CapDrop'] == ['ALL']
    assert all(m['Destination'] in ('/work', '/docs') for m in details['Mounts'])
    shell = r'''python3 - <<'PY'
import ctypes, pathlib, socket, subprocess
assert not pathlib.Path('/Users').exists()
assert not pathlib.Path('/var/run/docker.sock').exists()
try:
 assert not pathlib.Path('/root/.codex/auth.json').exists()
except PermissionError:
 pass
try:
 import _sqlite3
 raise AssertionError('SQLite Python binding available')
except ImportError:
 pass
try:
 ctypes.CDLL('libsqlite3.so.0')
 raise AssertionError('SQLite shared library available')
except OSError:
 pass
s=socket.socket();s.settimeout(1)
assert s.connect_ex(('1.1.1.1',443)) != 0
assert not subprocess.run(['bash','-c','command -v sqlite3'],capture_output=True).stdout
assert pathlib.Path('/docs/INDEX.md').exists()
print('offline-boundaries-ok')
PY'''
    result = subprocess.run(['docker', 'exec', 'astra-sqlite-probe', 'bash', '-c', shell], text=True, capture_output=True, check=True)
    image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', 'astra-sqlite-tools:pilot-v1'], text=True))[0]
    image_record = {'id': image['Id'], 'architecture': image['Architecture'], 'os': image['Os'], 'tag_used_for_build': 'astra-sqlite-tools:pilot-v1', 'dockerfile_sha256': hashlib.sha256((ROOT / 'runtime/Dockerfile').read_bytes()).hexdigest()}
    (ROOT / 'records/runtime-image.json').write_text(json.dumps(image_record, indent=2) + '\n')
    subprocess.run(['docker', 'cp', 'astra-sqlite-probe:/opt/utility-vendor/Cargo.lock', str(ROOT / 'records/utility-Cargo.lock')], check=True)
    record = {'passed': True, 'real_inference_used': False, 'model': request['model'], 'effort': request['reasoning']['effort'], 'callable_tools': names, 'builtin_skills_injected': False, 'container_boundaries': result.stdout.strip(), 'image_id': image['Id'], 'catalog_override': 'Only apply_patch_tool_type changed to null. Native file editing is unavailable; all source edits use the offline container tool.', 'remaining_pilot_checks': ['real subscription inference', 'live usage events', 'same-trajectory continuation', 'deadline behavior under inference', 'compaction if naturally encountered']}
    (ROOT / 'records/isolation-audit.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
