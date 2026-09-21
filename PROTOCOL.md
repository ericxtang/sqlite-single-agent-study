# Protocol v1.0

This is the measured protocol. The controlling byte seal is `records/freeze-v1.json`; `scripts/freeze.py` must verify it before each measured launch. The seal is created only after the documented validation gates pass. All choices and their provenance are in DECISIONS.md.

## Question

Measure what one Astra agent at Extra High implements in four hours, using a fixed SQLite manual and offline Rust tools. Compare descriptively with Cursor's historical swarm results. Model, harness, documentation selection, scoring adapter, corpus revision, hardware, and date differ; this is a practical conceptual reproduction, not a causal estimate of agent-count effects. Withheld tests may still have appeared in model training.

## Frozen implementation

- GPT-6 Astra (`gpt-6-astra`), `xhigh`, standard 272,000-token context from the frozen Codex catalog, default service tier, Codex CLI 0.153.0. Normal compaction and persistent notes are allowed and recorded.
- One trajectory per run, no subagents, model reviewers, extra inference from scripts, human coding, or adaptive instructions. Ordinary turn completion resumes the same trajectory with exactly `inputs/CONTINUE.md`. Self-review, agent-authored tests, compilation and parallel non-AI commands are allowed.
- Fresh named Docker volume and trajectory for each run. Initial content is only `inputs/IO_CONTRACT.md`; the model receives exactly `inputs/TASK.md`, with normal Codex system/environment instructions. No pilot code, notes, trajectory, benchmark names, historical outputs, or research-controller files carry into measured runs.
- Documentation: 416 selected text extracts from the official SQLite 3.53.4 archive plus an index; all bytes and provenance recorded. This differs from Cursor's 835-page manual. Standard Rust plus serde 1.0.228, serde_json 1.0.145 and locked transitive utilities; no SQL parser or database engine dependency.
- Four CPUs, 4 GiB RAM, offline non-root tools, pinned image, read-only root, no host home, Docker socket, credentials, reference SQLite or external tests. Only the fixed container bridge provides filesystem and shell access. See ENVIRONMENT.md for full boundaries and validation.

## Timing and run schedule

Discarded operational pilot: 30 minutes, with a five-minute diagnostic checkpoint. Pilot-001 failed preparation before inference; pilot-002 completed and passed the operational audit. The measured attempts are `measured-001`, `measured-002`, `measured-003`, run serially with no heavy grading alongside them.

Each measured run stops at 14,400 seconds. The clock starts immediately before first CLI dispatch, after provisioning and initial snapshot. Thinking, tools, compaction, automatic continuation, transient retries, and snapshot pauses count. The controller pauses the worker at deadline before terminating inference and capturing the endpoint. Actual pause latency is recorded; more than one second beyond the target causes an audit flag and stops automatic launch of later runs. There are no extensions or adjusted primary times. Provisioning and evaluation are separate.

The CLI's built-in retries remain its frozen defaults. If a CLI turn exits unsuccessfully for a transient non-account reason, resume the same trajectory after 15 seconds, then 30 seconds; a third consecutive unsuccessful exit interrupts the run. Successful ordinary turns reset this counter. All time counts. Explicit account/rate-limit/authentication failures stop immediately when reported in error events. Never change billing, consume reset credits, choose another model, restart a trajectory, or silently replace a failed attempt. Controller failure, isolation failure, operator stop, and unmatched freeze all require recorded review. The batch stops before later runs on any failed attempt/audit. Record the failure and identify a concrete next step for Eric.

## Checkpoints and isolation

Capture start, every 15 minutes, and final source state into external hashed tar archives, including uncommitted files and notes, excluding only top-level build output `target/`. Freeze filesystem writes briefly with Docker pause. Record actual capture time/overhead and source members. Unsafe paths, external symlinks, or unsupported special files cause a recorded infrastructure failure; do not quietly omit source. A missing or unbuildable checkpoint is not replaced with a later success.

The implementation receives no evaluation results, failing examples, coaching, new source, or test hints. Evaluators compile copies in separate offline containers and transmit SQL through the frozen JSON-lines interface. Corpus files and expected answers remain outside generated-code containers. Secondary file interoperability deliberately passes only its database input files into post-run evaluators.

## Evaluation

Primary denominator: all 5,728,833 eligible query records in all 622 `.test` files at sqllogictest revision `db57eba95d7c412bb413da5480c8be24109a8faf`. Statements (210,713 eligible) are reported separately. Predeclared SQLite dialect conditions skip 1,466,249 queries and 14,583 statements. Skips never depend on implementation capabilities. Unexpected setup-statement outcomes, crash, malformed responses, and timeout taint the rest of the file; unreached queries remain failures. Ordinary wrong SELECT outputs do not taint later queries. SCORING.md fixes normalization, labels, hashes and sorting.

Limits: 300-second build, 10 seconds per request, 16-MiB response line, 300 seconds per primary file. Build failures/timeouts score zero. Infrastructure errors leave evaluation incomplete and require review. Primary endpoints are graded first, then 12 separate secondary compatibility probes, then every retained progress checkpoint on the full corpus. No post-run repair of submitted source is permitted.

Secondary probes cover typed values, transactions/savepoints, constraints, foreign keys, selected advanced SQL, close/reopen and process restart, and bidirectional SQLite file interoperability. They are a small compatibility sample, not a full-conformance metric. Power-loss durability, concurrency, performance, and comprehensive documentation coverage are explicitly untested. All primary cases and secondary probes pass against reference SQLite 3.51.0, which differs from the 3.53.4 documentation target. Deliberately wrong fixtures and isolated file-transfer checks also pass validation.

## Usage and reporting

Use Eric's Codex subscription without an experiment spending cap; account limits still apply. Retain raw session/tool events and per-response plus cumulative usage. Report input, cached input, cache-write input, output, and reasoning tokens, with reasoning treated as a subset of output. A request active at cutoff may be absent from recorded usage, so totals are recorded completed-request usage rather than a guaranteed complete invoice. Keep pilot/setup/supervision usage separate from measured implementations; do not add this controller task's usage to any run.

Report all attempts, completion/interruption status, endpoint score, median/range across the three independent completed runs if available, elapsed time, build availability, tokens, compaction, continuation, checkpoints, secondary results, and deviations. Do not claim millions of correlated queries provide millions of independent experimental replications. Progress thresholds are 50%, 75%, 90%, and 100%; first crossing is only known within adjacent observed checkpoints, and an unobserved threshold is censored at four hours. Include regressions rather than fitting a monotonic curve.

Subscription access does not yield a marginal dollar invoice. Do not equate the subscription fee to implementation cost. API-equivalent estimates are optional and require a verified dated rate card and sufficiently detailed telemetry; label assumptions and omit unsupported estimates. Record local compute/evaluation durations separately. Cursor's four-hour scores and later full-suite completion/cost results must not be conflated.

## Gate evidence and amendments

Required evidence: `records/isolation-audit.json`, `records/continuation-audit.json`, `records/reference-validation-summary.json`, `records/evaluator-integration.json`, `records/secondary-validation.json`, `records/pilot-audit.json`, evaluator unit tests, freeze-verification test. Pilot SQL quality is not a gate. Compaction did not occur during the pilot and remains explicitly untested before the measured runs; synthetic same-trajectory continuation passed. No pilot extension is used to force these events.

The complete seal includes inputs/manual, model metadata, image identity, dependencies, source for controller/evaluator/tests, policy documents and corpus files. Verify before every run; any material amendment requires a new version and an explicit record of affected attempts. Keep mutable status, usage, audit and grading outputs under `records/`, `runs/`, or `reports/`, outside frozen inputs. Do not edit the seal or silently repair measurements after launch.

Sources: [Cursor study](https://prod.cursor.com/blog/agent-swarm-model-economics), [sqllogictest](https://www.sqlite.org/sqllogictest/doc/trunk/about.wiki), [SQLite distributions](https://www.sqlite.org/download.html). Published comparison values and their limits are recorded in `records/historical-baseline.json`.
