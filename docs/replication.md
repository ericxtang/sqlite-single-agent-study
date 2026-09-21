# Run a fresh single-agent experiment

Use a **new clone** for an independent experiment. The historical runs in `results/` are read-only inputs; new runs go under ignored `runs/replicate-*`. Setup, doctor and seal do not make real model calls. Only the final `run.py` command does.

## Prerequisites

- Python 3.9+, Git, Docker running Linux containers. The image defaults to Linux arm64, matching the original; x86 emulation changes timing. Four CPUs and 4 GiB per implementation worker, plus host overhead. Do not grade alongside an implementation.
- The original experiment used Codex CLI **0.153.0**. Install that exact version with `npm install -g @openai/codex@0.153.0` in an appropriate local environment. The harness intentionally rejects a different version. If this distribution is unavailable, port and revalidate the tool surface as a new protocol instead of silently replacing it.
- Your own signed-in Codex subscription with access to `gpt-6-astra` at `xhigh`. Access is account-dependent and not guaranteed by this repository. See [official CLI setup](https://learn.chatgpt.com/docs/codex/cli). There is no API-key billing fallback.
- Your locally supplied model catalog must contain the original 272,000-token Astra context configuration. We do not distribute platform-supplied model instructions. The `catalog` step copies your model metadata locally and disables native host-file editing; it does not prove hosted weights are unchanged.

## Prepare and validate

```sh
python3 replication/manage.py verify
python3 replication/manage.py setup
python3 replication/manage.py fetch-corpus
codex login
python3 replication/manage.py catalog --from-file "$HOME/.codex/models_cache.json"
python3 replication/manage.py doctor
python3 -m unittest discover -s evaluator -p 'test_*.py'
python3 -m unittest discover -s replication -p 'test_*.py'
python3 replication/manage.py seal
```

If your CLI stores its catalog elsewhere, provide that JSON file explicitly; do not substitute a hand-written permissive model config. The doctor sends requests only to a localhost mock provider, verifies the exact callable tool allowlist and an offline non-root container, and keeps platform instructions out of its saved audit. A tool-surface mismatch stops preparation.

The reference SQLite is supplied by the host Python. Its version is recorded in the local seal; the original used **3.51.0**, while the supplied documentation targets **3.53.4**. A different host reference version is a reported deviation, especially for secondary file/probe behavior. For a full reference validation, before implementation:

```sh
python3 evaluator/validate_reference.py
```

This can take substantial time. Inspect `records/reference-validation-summary.json`; require `passed: true` for a protocol-matched measurement. A short pilot should also check your actual account availability, cutoff behavior and same-trajectory continuation. Compaction may not occur in a pilot. No preflight can guarantee hosted-service behavior.

## Explicitly start a pilot or a measured run

```sh
# Optional operational pilot: 30 minutes; discarded, never pooled with measured runs.
python3 replication/run.py --mode pilot --run-id replicate-pilot-001 --allow-inference

# Fresh four-hour measurement. Do not reuse the pilot ID or workspace.
python3 replication/run.py --mode measured --run-id replicate-001 --allow-inference
```

The command is foreground and sequential; **no scheduled task is needed**. Keep the host awake. On macOS you may prefix it with `caffeinate -i`. Repeat with `replicate-002` and `replicate-003` only after checking the previous manifest, artifact hash, stopped container and timing. No automatic batch replaces failed runs. A normal successful turn continues in the same trajectory using the fixed continuation prompt; account/rate-limit errors stop immediately. Deadline includes inference, tools, retries, compaction and snapshot pauses. Measured time cannot be extended with `--seconds`.

The model has one fixed Docker workspace tool and read-only docs. Host credentials are referenced only by its private driver runtime; they never enter Docker. No historical code, hidden tests, model reviewers or feedback is sent to it.

## Stop and inspect

Press Ctrl-C in the runner terminal, or create `records/STOP`. The runner checks STOP during its main loop, pauses writes, terminates inference, captures the stopped artifact and kills its implementation container. For immediate stop from another terminal, SIGTERM the controller PID recorded in `runs/replicate-001/manifest.json`; verify container shutdown afterward. Preserve all logs and partial artifacts. Provisioning failures also attempt worker shutdown and are recorded; inspect the manifest's exact container name to verify it stopped.

Useful files:

- `runs/replicate-001/manifest.json`: state, duration, PID, image and thread identity.
- `runs/replicate-001/events.jsonl`, `tools.jsonl`, `runner-stderr.log`: local diagnostics; treat as private.
- `runs/replicate-001/runtime/sessions/`: original local telemetry, possibly private reasoning. Do not publish wholesale.
- `runs/replicate-001/checkpoints/`: immutable start, 15-minute and final source snapshots plus hashes.

After stopping all implementations, follow [grading](grading.md). Report every attempt, interrupted durations, endpoint median/range with actual n, progress regressions, threshold intervals/censoring, and all twelve secondary outcomes. Check timing overshoot against the original one-second audit threshold; never silently relabel a failed audit a valid four-hour result.

For usage, deduplicate per-response records and reconcile all token fields to the final raw cumulative thread usage. Compact CLI turn totals can undercount or reset on continuation. Reasoning is a subset of output; cached reads and cache writes are separate input categories. Record cutoff limitations. The historical [usage ledger](../historical/records/usage-accounting.json) shows the required reporting shape; it is not a promise of your run's cost.
