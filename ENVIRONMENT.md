# Environment v1.0

## Observed local prerequisites (2026-09-18)

- macOS host; Docker daemon responds, server version 29.6.1.
- Codex CLI 0.153.0 installed; `codex login status` reports ChatGPT sign-in.
- Rust/cargo and Python 3 available on host.
- The authenticated driver uses a private reference to the existing Codex credential file. Credentials are not mounted in or passed to the worker. Live subscription inference began during pilot-002.

## Frozen topology

Controller/runner (auth, budget enforcement, logs)
  -> model endpoint (inference only)
  -> constrained tool bridge -> offline implementation container

Controller snapshots -> separate evaluation environment -> private reports

The implementation container has no network, Docker socket, host home mounts, reference SQLite binary/library/source, existing SQL parser, or test corpus. Only implementation workspace, audited docs, and an allowed toolchain are mounted. The tool bridge must cover all filesystem and shell access; default host tools must not remain exposed as an alternate route.

The runner can reach inference while tools cannot. Simply placing the entire authenticated Codex process and a network-enabled shell in one container is insufficient to establish offline-tool isolation. The selected implementation uses the validated Codex tool bridge with subscription access. There is no API-billing fallback.

Existing Docker images belong to other projects and will not be modified or treated as clean benchmark environments. The dedicated pinned image is recorded in records/runtime-image.json. Each implementation has four CPUs and 4 GiB RAM; service tier is the Codex default.

The evaluation process must also isolate untrusted generated programs from the test files and expected answers. Send only SQL input through the interface, normalize responses outside the generated process, and mount source/binaries separately from expected results. Building generated code also requires an isolated environment.

## Implementation status

- Implemented: model runner, clean private runtime configuration, and tool bridge.
- Built and pinned: Rust 1.95.0 worker image and locked serde/serde_json utility inventory. SQLite shared library and Python native binding removed.
- Prepared: 416 reference text extracts and index, with per-file provenance/hashes; no bundled databases, JavaScript, or test-suite documentation.
- Acquired and pinned: official sqllogictest corpus, revision and file manifest.
- Implemented: parser/scorer, bounded process adapter, and offline snapshot build/evaluation path. Fifteen focused evaluator tests pass. All 5,728,833 eligible queries in all 622 files pass against reference SQLite 3.51.0, with zero statement failures. A deliberately incorrect Rust fixture fails as expected through the complete isolated build/protocol/scoring path.
- Implemented: deadline controller, private JSONL tool/session logs, and consistent external snapshots. Pilot-002 operational audit passed. No experiment spending cap per Eric's choice.

The non-inference tool audit proves the accessible code-mode tools are the fixed offline workspace bridge, clock, and MCP resource discovery/read helpers (the bridge offers no resources). Host shell, native file editing, skills, browser, connectors, image tools, and subagents are absent. The current model catalog is preserved except `apply_patch_tool_type = null`, which prevents a host filesystem editing route. This is a custom isolated Codex harness, not an assertion of identical tooling to Cursor.

The readiness script inventories prerequisites; it does not certify isolation or authorize a run.


## Operational limitations

Pilot-002 stopped after 1,800.089 seconds; all four snapshots verified and the worker is stopped. Ordinary same-trajectory CLI continuation was tested with a synthetic provider, not triggered live in the pilot. No compaction was observed, so compaction remains untested before the measured runs; preserve and audit any actual compaction logs. A backend model identifier is pinned, but the hosted weights/service cannot be cryptographically frozen.

The 272,000-token default comes from the pinned Codex model catalog; the 872,000-token maximum is not selected. Normal compaction defaults remain enabled. The CLI is 0.153.0, with executable hash/path recorded in the freeze. Host OS scheduling, shared subscription load, and the inference service remain uncontrolled. Caffeinate prevents idle system sleep while the supervisor is alive, but does not protect against power loss, forced sleep, daemon restart, or network failure.

Worker image: sha256:c379c6128e193682c40015eb8b126e2916b18c3985f0fb72cf1c642a1a3039f5 (Linux arm64). Docker server at setup: 29.6.1, ten available CPUs, approximately 8 GiB total Docker memory. The worker process limit is 256; evaluator process limit is 128. Root filesystem is read-only, all capabilities dropped, no-new-privileges enabled, UID 1000, /tmp is a 512-MiB tmpfs. Evaluation containers receive no docs or hidden corpus mounts.
