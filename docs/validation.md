# Publication validation — September 21, 2026

The portable package was checked without launching a new live implementation trajectory:

- All 55 bundled source archives match their original SHA256 metadata; archive member paths were inspected without extracting generated code onto the host.
- All 59 logical result summaries match recorded hashes; all 66 evaluation attempts remain available, including seven incomplete attempts.
- The Docker runtime rebuilt from the documented recipe and pinned Cargo.lock on Linux arm64.
- The official upstream Fossil corpus was freshly cloned; all 622 test files matched the frozen corpus manifest.
- The Codex 0.153.0 localhost mock-provider doctor passed, including exact callable tool allowlist, no host editing/subagents, and offline non-root container checks. It made zero live model calls.
- 15 frozen evaluator tests and 10 replication/cleanup tests passed. Cleanup tests cover normal cutoff, duplicate account errors, failed pause/capture/shutdown and exclusive controller locks.
- All manual examples passed for 001, 002, 004 and the explicitly older 003-30min checkpoint. Interrupted 003's terminal artifact failed to build as expected.
- The primary smoke replay built 001 in isolation and passed 45/45 queries in the first two files. It is explicitly a diagnostic subset, not a new full-suite score.
- A 001 secondary replay matched all twelve original outcomes (7/12 passed), including the unchanged blob-case limitation.
- Recomputed completed-endpoint statistics matched the report: n=3, median 96.4636078587%, range 96.4275272119–96.7380092944%. Historical API valuation arithmetic matched the audited ledger.
- Tracked files and archive contents were scanned for common credential patterns; auth/runtime/session directories were excluded. Public README/report/guide links were checked.

The new controller was not tested with a paid/live four-hour model run during publication. The original run evidence, local mock-provider check and shutdown regression tests support its documented behavior, but replicators should run and audit their own operational pilot. A hosted model and its access cannot be guaranteed by this repo.

GitHub Actions reruns the no-inference unit, integrity, archive and link checks. It does not run full Docker grading or consume a model allowance.

## Evaluator v2 correction (September 21, 2026)

The 25 original unit tests plus seven v2 tests pass. Explicit Docker regression checks verify a real name collision is infrastructure failure without removing the existing container; a confirmed generated-process exit 125 and a request timeout remain implementation failures; a valid query passes; raw protocol/stderr are retained; owned containers are removed. These checks make no model calls.

An unchanged run 001 archive passed the 45-query/two-file v2 primary smoke diagnostic and 10/12 corrected secondary probes under the original image. These are validation diagnostics, not a completed full terminal regrade. [Machine-readable validation](../reports/data/v2-validation.json). [Erratum and pending full regrade](ERRATUM-001.md).

The subsequent PR review identified missing file/directory synchronization in queue-state updates. Four additional tests exercise the actual controller save function: file sync precedes replacement, directory sync follows it, a failed file sync preserves the previous state, the directory descriptor closes on failure, and a real filesystem round trip succeeds. Total current unit tests: **36**. This controller bookkeeping correction was developed in a separate checkout; the already-running terminal queue retains its sealed source version and is not restarted or silently patched.
