#!/usr/bin/env python3
"""Capture a Codex request against a local non-inference server to audit its tools."""
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from runtime_config import config_text

ROOT = Path(__file__).resolve().parents[1]


class Capture(http.server.BaseHTTPRequestHandler):
    captured = []

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        try:
            Capture.captured.append(json.loads(raw))
        except (ValueError, UnicodeError):
            Capture.captured.append({'unparsed_bytes': len(raw), 'encoding': self.headers.get('Content-Encoding')})
        if len(Capture.captured) == 1:
            item = {'type': 'custom_tool_call', 'id': 'ctc_probe', 'call_id': 'call_probe', 'namespace': 'functions', 'name': 'exec', 'input': 'text(ALL_TOOLS.map(t => t.name)); text(await tools.mcp__workspace__exec({command: "printf bridge-ok"}));'}
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            response = {'id': 'resp_probe', 'object': 'response', 'status': 'completed', 'model': 'gpt-6-astra', 'output': [item], 'usage': {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}}
            for event in [{'type': 'response.created', 'response': dict(response, status='in_progress', output=[])}, {'type': 'response.output_item.added', 'output_index': 0, 'item': item}, {'type': 'response.output_item.done', 'output_index': 0, 'item': item}, {'type': 'response.completed', 'response': response}]:
                self.wfile.write(('data: ' + json.dumps(event) + '\n\n').encode())
            self.wfile.flush()
            return
        self.send_response(400)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"error":{"message":"Intentional local tool-surface probe. No inference.","type":"invalid_request_error"}}')

    def log_message(self, *args):
        pass


def main():
    server = http.server.HTTPServer(('127.0.0.1', 0), Capture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with tempfile.TemporaryDirectory(prefix='codex-surface-') as tmp:
        root = Path(tmp).resolve()
        driver = root / 'driver'
        driver.mkdir()
        runtime = root / 'runtime'
        runtime.mkdir()
        cfg = '''model = "gpt-6-astra"
model_reasoning_effort = "xhigh"
model_provider = "probe"
approval_policy = "never"
web_search = "disabled"
check_for_update_on_startup = false
[agents]
enabled = false
[features]
view_image = false
shell_tool = false
unified_exec = false
multi_agent = false
apps = false
plugins = false
remote_plugin = false
hooks = false
memories = false
goals = false
browser_use = false
computer_use = false
image_generation = false
shell_snapshot = false
skill_search = false
tool_search_always_defer_mcp_tools = false
skill_mcp_dependency_install = false
skip_host_skill_discovery = true
workspace_dependencies = false
enable_request_compression = false
'''
        for skill in ('imagegen', 'openai-docs', 'plugin-creator', 'skill-creator', 'skill-installer'):
            cfg += '\n[[skills.config]]\npath = ' + json.dumps(str(runtime / 'skills/.system' / skill / 'SKILL.md')) + '\nenabled = false\n'
        cfg += '\n[model_providers.probe]\nname = "Local non-inference probe"\nwire_api = "responses"\nrequires_openai_auth = false\nbase_url = "http://127.0.0.1:%d/v1"\nrequest_max_retries = 0\nstream_max_retries = 0\n' % server.server_port
        cfg += '\n[mcp_servers.workspace]\ncommand = "/usr/bin/python3"\nargs = ' + json.dumps([str(ROOT / 'scripts/container_tools.py'), '--container', 'astra-sqlite-probe', '--audit-log', str(ROOT / 'records/probe-tools.jsonl')]) + '\nrequired = true\nenabled = true\nenabled_tools = ["exec"]\ndefault_tools_approval_mode = "approve"\n'
        # Audit the same configuration builder used by the real runner.
        cfg = 'model_provider = "probe"\n' + config_text(runtime, 'astra-sqlite-probe', ROOT / 'records/probe-tools.jsonl')
        cfg += '\n[model_providers.probe]\nname = "Local non-inference probe"\nwire_api = "responses"\nrequires_openai_auth = false\nbase_url = "http://127.0.0.1:%d/v1"\nrequest_max_retries = 0\nstream_max_retries = 0\n' % server.server_port
        (runtime / 'config.toml').write_text(cfg)
        env = {'PATH': os.environ['PATH'], 'HOME': tmp, 'CODEX_HOME': str(runtime), 'TMPDIR': tmp}
        listing = subprocess.run(['codex', 'mcp', 'list', '--json'], env=env, capture_output=True, text=True, timeout=15)
        print('MCP configuration:', listing.stdout)
        catalog = json.loads((ROOT / 'records/astra-model-catalog.json').read_text())
        catalog['models'][0]['apply_patch_tool_type'] = None
        catalog_path = ROOT / 'records/astra-mcp-only-catalog.json'
        catalog_path.write_text(json.dumps(catalog, indent=2) + '\n')
        args = ['codex', 'exec', '--strict-config', '--json', '--skip-git-repo-check', '-C', str(driver), '-c', 'model_catalog_json=' + json.dumps(str(catalog_path)), 'Readiness probe. Do not act.']
        try:
            result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=45)
        finally:
            server.shutdown()
        report = {'inference': False, 'returncode': result.returncode, 'stderr': result.stderr[-5000:], 'events': result.stdout[-5000:], 'requests': Capture.captured}
        (ROOT / 'records/tool-surface-probe.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'returncode': result.returncode, 'stderr': result.stderr[-3000:], 'requests': len(Capture.captured)}, indent=2))
        for request in Capture.captured:
            import re
            names = []
            for item in request.get('input', []):
                if item.get('type') == 'additional_tools':
                    for namespace in item.get('tools', []):
                        names.append(namespace.get('name'))
                        for tool in namespace.get('tools', []):
                            names.append(namespace.get('name', '') + '.' + tool.get('name', ''))
                            names.extend(re.findall(r'^###? (.+)', tool.get('description', ''), re.M))
            print(json.dumps({'model': request.get('model'), 'reasoning': request.get('reasoning'), 'tools': names}, indent=2))


if __name__ == '__main__':
    main()
