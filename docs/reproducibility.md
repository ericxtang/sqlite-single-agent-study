# Reproducibility and publication boundaries

This is a public replication package for a completed September 18–21, 2026 study. It supports re-executing the saved source artifacts and conducting a fresh conceptual replication. It does not promise identical output from a hosted model or an exact match to Cursor's experiments.

## What is byte-identical

`historical/bundled-originals.json` records original paths and SHA256 hashes of unchanged bundled files. These include implementation task/continuation/I/O prompts, selected manual bytes, scoring source, corpus manifest, source checkpoint archives, and raw per-file/summary/build evaluation outputs. `historical/records/freeze-v1.json` retains the original seal as provenance. It covers more private/local files than this public repo includes; it is **not** a complete public replay seal.

The original four-hour implementations have not been resumed, patched or replaced. Run 003's recovered interrupted artifact is published with its failing build. Its 30-minute checkpoint is a separate diagnostic. Later grading attempts and incomplete evidence remain distinct. A new `publication-manifest.json` verifies the public release; a locally generated `records/replication-seal.json` identifies each replication environment.

## Portable adaptations

- New repository layout, relative links and local state paths; original controllers under `historical/` are reference code, not the supported entry points.
- New `replication/` commands use the amendment-001 deadline/cleanup controller with fresh `replicate-*` IDs, a local seal, explicit inference opt-in, STOP-file polling, exclusive controller locks, provisioning cleanup, nonzero exit on interruption/overshoot, current Python executable and a localhost capability probe. Original study IDs and private authorizations cannot launch through this entry point.
- Runtime rebuild uses the original Cargo.lock, preventing transitive-dependency drift. Rust version/arm64 target are fixed, but base-image OS packages are not a byte-for-byte reproduction of the original local Docker image. Rebuilt image identity is recorded. Network is used for installation only; execution containers are offline.
- Grading keeps frozen scoring unchanged and applies the reviewed cleanup-only adapter. A general fresh-output queue replaces machine-specific original PID/state/retry plans. SIGTERM invokes cleanup and preserves partial outputs.
- Model catalog and provider-supplied instructions come from the replicator's own local CLI, remain ignored, and are hashed locally. Model availability, service revision, latency, OS scheduling, subscription contention and compaction cannot be frozen by publishing this repo.
- Reports have portable links and removed local user/session identifiers. Links to private raw evidence are explicitly labeled as unbundled. Published aggregate data are an export, not a complete replacement for the retained private audit. The full private usage reconciliation is described; outsiders can recompute aggregate cost arithmetic, but cannot independently reproduce private response-level reconciliation from this export alone.

## Agent formation and measurement

Astra's one-agent formation was enforced: no child agents, forks, model reviewers or external model calls. Multiple non-AI shell processes and parallel evaluation workers are not extra implementation agents. Cursor describes recursive delegation and different planner/worker model combinations. This package is a descriptive comparison across those different setups, not an agent-count ablation.

Our measurement uses the public sqllogictest corpus but a separately frozen revision, filtering, typed-JSON adapter and timeout/taint policy. Cursor does not publish enough detail in the two cited posts to establish identical tests and grading. Our 416 selected extracts also differ from its reported 835-page manual. Compare the reported four-hour values separately from Cursor's later completion and token/dollar totals.

## Data handling and licensing

The public bundle deliberately excludes credentials, runtime auth links, raw session/rollout files, private reasoning text, complete platform-supplied prompts, personal automation state and unrelated projects. Source archives include agent-authored code, tests and workspace notes, not the model's private reasoning stream. Observable progress messages/command summaries in the report are self-reports, with independent grading distinguished.

Fresh runs create sensitive local logs under ignored paths. Review and export a deliberate allowlist before sharing your own results. Gitignore is convenience, not a credential scanner.

Project-authored harness, reports and generated implementations are MIT licensed. Upstream documentation/corpus/dependencies retain their own terms; see [third-party notices](../THIRD_PARTY_NOTICES.md). No model weights or proprietary hosted service are distributed.
