"""Frozen single-agent tool configuration shared by probes and runs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def config_text(runtime, container, audit_log):
    runtime = Path(runtime).resolve()
    text = '''model = "gpt-6-astra"
model_reasoning_effort = "xhigh"
approval_policy = "never"
web_search = "disabled"
check_for_update_on_startup = false
suppress_unstable_features_warning = true
'''
    text += 'model_catalog_json = ' + json.dumps(str(ROOT / 'records/astra-mcp-only-catalog.json')) + '\n'
    text += '''
[agents]
enabled = false
[features]
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
view_image = false
shell_snapshot = false
skill_search = false
skill_mcp_dependency_install = false
skip_host_skill_discovery = true
workspace_dependencies = false
enable_request_compression = false
'''
    for skill in ('imagegen', 'openai-docs', 'plugin-creator', 'skill-creator', 'skill-installer'):
        text += '\n[[skills.config]]\npath = ' + json.dumps(str(runtime / 'skills/.system' / skill / 'SKILL.md')) + '\nenabled = false\n'
    text += '\n[mcp_servers.workspace]\ncommand = "/usr/bin/python3"\nargs = ' + json.dumps([str(ROOT / 'scripts/container_tools.py'), '--container', container, '--audit-log', str(audit_log)]) + '\nrequired = true\nenabled = true\nenabled_tools = ["exec"]\ndefault_tools_approval_mode = "approve"\ntool_timeout_sec = 75\n'
    return text
