# Scoring policy v1.0

Corpus: official SQLite sqllogictest Fossil checkout `db57eba95d7c412bb413da5480c8be24109a8faf` (2026-04-15). Freeze every file under `test/` ending `.test`; do not sample files based on performance.

Primary unit: eligible query record. Apply `skipif`/`onlyif` for the `SQLite` engine label using case-insensitive comparisons. Honor corpus `halt` records. Exclusions are fixed during parsing, before any implementation is scored. Report eligible and excluded query and statement counts. Statements are scored separately, never added to the query denominator.

An unexpected setup-statement failure, unexpected statement success, process crash, malformed response, or timeout taints the remainder of that file: all remaining eligible queries fail and remain in the denominator. Ordinary incorrect SELECT output does not taint later queries. Each file begins with a new empty in-memory connection. The full corpus, not the subset actually executed, determines the denominator.

Normalize values according to the corpus type string and original SQLite sqllogictest adapter: NULL -> `NULL`; I -> SQLite conversion then signed 32-bit output; R -> SQLite `%.3f`; T -> SQLite text conversion, empty string -> `(empty)`, each non-printable/non-ASCII byte -> `@`, and NUL termination as in the original C adapter. Apply `nosort`, `rowsort`, or `valuesort` before comparison. Hash results as MD5 of each normalized value followed by a newline. Verify both count and digest. Preserve labeled-result consistency within each file.

Fixed limits: build 300 seconds; each SQL request 10 seconds; response line 16 MiB; each file 300 seconds. Timeouts are failures, not exclusions. Reference timeout/inconsistency is a harness validation problem; resolve it before freezing rather than silently dropping the case. Evaluation time is outside agent wall clock and is reported separately. A build failure scores zero for that checkpoint.

All generated code is compiled and executed in an offline container. Corpus files, expected outputs, reference SQLite, and controller files are not mounted in that container. Only SQL inputs cross the process interface. Reference SQLite is available to the controller/evaluator only.

This policy is not claimed to match Cursor's unpublished scoring details. Validate parser, normalizer, error handling, fixed denominators, and reference results before freezing it.


Secondary assessment: `evaluator/secondary.py` defines 12 independent binary probes: typed values, rollback, nested savepoints, constraints/statement atomicity, foreign-key cascade, recursive CTE, window function, JSON extraction, close/reopen, process restart after explicit close, SQLite reading a generated file (including quick_check), and the generated program reading a SQLite file. Report every probe separately; their count is not a conformance percentage and is never mixed into the primary score. Exact typed values are compared. Each case receives a fresh database; restart retains only that case's database volume. Requests have the same 10-second/16-MiB limits; each generated secondary process has a 180-second cap. Seed/reference files enter only post-run evaluation containers, never implementation containers. The trusted reference-file reader has a 10-second deadline.

Power-loss recovery, concurrent access, performance, and comprehensive documentation coverage are not tested. Persistence probes demonstrate their specified close/restart sequences only. Reference SQLite is Python's SQLite 3.51.0, while documentation targets 3.53.4. The entire primary corpus and all secondary probes pass on that reference. No expected result is changed to match an implementation.

The primary diagnostic pilot subset consists of the first two lexically sorted corpus files (45 queries); it only exercises the artifact path and is not a full-corpus estimate. Measured endpoints and progress snapshots use all 622 files. All endpoint primary evaluations precede secondary endpoint checks and progress grading. Evaluation infrastructure errors produce an incomplete result requiring review; they are not silently assigned a valid zero. Build failure/timeout is a declared valid zero. Every evaluation retains its build log and per-file outcome log.
