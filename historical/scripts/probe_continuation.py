#!/usr/bin/env python3
"""Verify failed-turn resumption preserves one trajectory, with zero real inference."""
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading

from probe_tool_surface import Capture
from runtime_config import ROOT, config_text


def main():
    Capture.captured = []
    server = http.server.HTTPServer(('127.0.0.1', 0), Capture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix='codex-resume-check-') as temporary:
        root = Path(temporary).resolve()
        runtime = root / 'runtime'
        runtime.mkdir()
        driver = root / 'driver'
        driver.mkdir()
        config = 'model_provider = "probe"\n' + config_text(runtime, 'astra-sqlite-probe', ROOT / 'records/continuation-probe-tools.jsonl')
        config += '\n[model_providers.probe]\nname = "Local non-inference probe"\nwire_api = "responses"\nrequires_openai_auth = false\nbase_url = "http://127.0.0.1:%d/v1"\nrequest_max_retries = 0\nstream_max_retries = 0\n' % server.server_port
        (runtime / 'config.toml').write_text(config)
        environment = {'PATH': os.environ['PATH'], 'HOME': str(root), 'CODEX_HOME': str(runtime), 'TMPDIR': str(root)}
        base = ['codex', 'exec', '--strict-config', '--json', '--skip-git-repo-check']
        first = subprocess.run(base + ['-C', str(driver), 'Initial trajectory sentinel.'], cwd=driver, env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=45)
        first_events = [json.loads(line) for line in first.stdout.splitlines() if line.startswith('{')]
        ident = next(e['thread_id'] for e in first_events if e['type'] == 'thread.started')
        resumed = subprocess.run(base + ['resume', ident, 'Continuation sentinel.'], cwd=driver, env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=45)
        resumed_events = [json.loads(line) for line in resumed.stdout.splitlines() if line.startswith('{')]
        resumed_id = next(e['thread_id'] for e in resumed_events if e['type'] == 'thread.started')
        assert ident == resumed_id
        assert len(Capture.captured) == 3
        last = Capture.captured[-1]
        assert 'Initial trajectory sentinel.' in json.dumps(last)
        assert 'Continuation sentinel.' in json.dumps(last)
        assert 'bridge-ok' in json.dumps(last)
        assert last['model'] == 'gpt-6-astra'
        assert last['reasoning']['effort'] == 'xhigh'
        report = {'passed': True, 'inference': False, 'thread_id_preserved': True, 'prior_tool_result_preserved': True, 'model': last['model'], 'effort': last['reasoning']['effort'], 'scenario': 'Resume the same trajectory after a failed model request, using a local synthetic provider.'}
        (ROOT / 'records/continuation-audit.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    server.shutdown()


if __name__ == '__main__':
    main()
