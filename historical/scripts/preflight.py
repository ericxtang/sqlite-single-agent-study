#!/usr/bin/env python3
"""Read-only prerequisite inventory. No inference, credential reads, or container starts."""
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def probe(argv):
    if shutil.which(argv[0]) is None:
        return {"available": False, "error": "executable not found"}
    try:
        result = subprocess.run(argv, text=True, capture_output=True, timeout=15)
        return {
            "available": result.returncode == 0,
            "returncode": result.returncode,
            "output": result.stdout.strip()[:2000],
            "status_message": result.stderr.strip()[:1000] or None,
            "error": result.stderr.strip()[:1000] if result.returncode else None,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": str(exc)}


def main():
    config = json.loads((ROOT / "study.json").read_text())
    optional = {'pilot_spend_cap_usd', 'total_spend_cap_usd'} if config.get('spending_cap_policy') == 'no_cap_requested_by_user' else set()
    pending = [key for key, value in config.items() if value is None and key not in optional]
    report = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "host": {"system": platform.system(), "machine": platform.machine()},
        "tools": {
            "docker": probe(["docker", "info", "--format", "{{json .ServerVersion}}"]),
            "codex": probe(["codex", "--version"]),
            "codex_auth_status": probe(["codex", "login", "status"]),
            "rustc": probe(["rustc", "--version"]),
            "cargo": probe(["cargo", "--version"]),
            "python": {"available": True, "version": platform.python_version()},
        },
        "pending_fields": pending,
        "study_ready": False,
        "reason": "Prerequisite inventory only; runner, evaluator, isolation, protocol freeze and usage caps require separate validation.",
        "inference_started": False,
    }
    output = ROOT / "records" / "preflight.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
