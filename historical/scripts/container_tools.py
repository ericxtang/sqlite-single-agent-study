#!/usr/bin/env python3
"""Minimal stdio MCP server. All model-controlled code runs in one fixed container."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOL = {
    'name': 'exec',
    'description': 'Execute a bash command inside your offline Linux development workspace at /work. Use this tool for all file reads, edits, searches, compilation, and tests. Documentation is read-only at /docs. General-purpose Python 3, Rust, cargo, git, and rg are available. Commands time out after at most 55 seconds; output is truncated to 30000 characters. Longer tasks can write logs and run in the background, then be checked in a later call. No network access is available.',
    'inputSchema': {
        'type': 'object',
        'properties': {'command': {'type': 'string'}, 'timeout_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 55}},
        'required': ['command'],
        'additionalProperties': False,
    },
}


def execute(container, command, seconds):
    # The executable/container/working directory are fixed outside model input.
    args = ['docker', 'exec', '--user', '1000:1000', '--workdir', '/work', container,
            'timeout', '--signal=TERM', '--kill-after=2s', str(seconds), 'bash', '-c', command]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=seconds + 8)
        result = {'exit_code': r.returncode, 'stdout': r.stdout[-30000:], 'stderr': r.stderr[-6000:]}
    except subprocess.TimeoutExpired:
        result = {'exit_code': 124, 'stdout': '', 'stderr': 'Tool deadline reached.'}
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--container', required=True)
    p.add_argument('--audit-log', required=True)
    args = p.parse_args()
    if not args.container.startswith('astra-sqlite-'):
        raise SystemExit('Refusing a container outside this study namespace.')
    audit = Path(args.audit_log)
    audit.parent.mkdir(parents=True, exist_ok=True)
    for line in sys.stdin:
        try:
            req = json.loads(line)
            method = req.get('method')
            ident = req.get('id')
            with audit.open('a') as f:
                f.write(json.dumps({'protocol_method': method, 'at': datetime.now(timezone.utc).isoformat()}) + '\n')
            if method == 'initialize':
                result = {'protocolVersion': req.get('params', {}).get('protocolVersion', '2024-11-05'), 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'offline-workspace', 'version': '0.1.0'}}
            elif method == 'tools/list':
                result = {'tools': [TOOL]}
            elif method == 'tools/call':
                params = req.get('params', {})
                if params.get('name') != 'exec':
                    raise ValueError('Unknown tool')
                arguments = params.get('arguments', {})
                command = arguments.get('command')
                seconds = arguments.get('timeout_seconds', 55)
                if not isinstance(command, str) or len(command) > 262144:
                    raise ValueError('Invalid command')
                if type(seconds) is not int or not 1 <= seconds <= 55:
                    raise ValueError('Invalid timeout')
                start = datetime.now(timezone.utc).isoformat()
                output = execute(args.container, command, seconds)
                with audit.open('a') as f:
                    f.write(json.dumps({'started_at': start, 'ended_at': datetime.now(timezone.utc).isoformat(), 'command': command, 'result': output}) + '\n')
                result = {'content': [{'type': 'text', 'text': json.dumps(output)}], 'isError': False}
            elif method == 'ping':
                result = {}
            elif ident is None:
                continue
            else:
                print(json.dumps({'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': 'Unsupported method'}}), flush=True)
                continue
            if ident is not None:
                print(json.dumps({'jsonrpc': '2.0', 'id': ident, 'result': result}), flush=True)
        except Exception as exc:
            print(json.dumps({'jsonrpc': '2.0', 'id': locals().get('ident'), 'error': {'code': -32603, 'message': str(exc)}}), flush=True)


if __name__ == '__main__':
    main()
