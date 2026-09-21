# Rust SQLite implementation state

## Operating rules and build

Continue useful implementation until the controller ends the work period. Work
only through the offline workspace tool, in /work, using supplied /docs. No
reference engine/parser, external code/tests, network, other agents or models.
No human advice is needed. Cargo deps: serde 1.0.228 and serde_json 1.0.145 only.

`cargo build --release --offline --bin sqlite-agent` produces
`target/release/sqlite-agent`. `tests/run.sh` runs all integrated suites. JSON-line
open/execute/close protocol, typed cells and flushing follow IO_CONTRACT.md.
README.md has invocation examples. No git repo; cargo-fmt unavailable.

## Architecture

- lexer/parser/ast: recursive descent + Pratt expressions, serialized schema AST.
- value: storage classes, affinities/collations, arithmetic, lossless real snapshots.
- engine/validate/memo/cte/compound: relational execution and separate static binding,
  aggregates, joins, compounds, subqueries, lazy aliases and CTE dependencies.
- mutate/schema/upsert/foreign/sequence/trigger/attach: constraints, DML/DDL,
  schema rewrites, foreign actions, system sequences, triggers and routing.
- window: partitions/peers/frames/exclusions, grouped windows, expression substitution.
- functions/formatting/datetime/json/json_value/jsonb: scalar and JSON functions.
- storage/snapshot/journal/maintenance/pragma: durability, locks, recovery, metadata, maintenance.

The DB format is versioned JSON snapshots, NOT SQLite page format. JSONB also uses
an implementation-specific binary encoding. Indexes enforce constraints and are
validated/recomputed on writes; execution primarily scans rows. Native SQLite
files/WAL/JSONB, virtual table extensions (FTS/RTREE), and a real planner are absent.

## Durability and transactions

Snapshots preserve integer/blob/text/real data, including IEEE infinities. Explicit
transactions/savepoints hold DB snapshots; close rolls back unfinished writes.
Persistent paths are canonicalized under /work. Readers refresh committed state;
transactions retain read snapshots and stale writer upgrades fail. std File locks
(Rust 1.95) on stable .agent-lock inodes prevent concurrent lost updates. These
sidecars intentionally remain; the OS releases locks after process death.

Attached writes and TEMP-trigger writes are coordinated with the root statement.
ABORT/FAIL/ROLLBACK and deferred-FK COMMIT/outer RELEASE checks propagate across
attachments. Failed BEGIN unwinds locks; failed COMMIT/RELEASE stays retryable.
Temp-only writes avoid locking/persisting the main file; unchanged snapshots skip
publication. data_version changes for other connections' commits.

Multi-file commit stages/fsyncs all new snapshots, writes durable before-image
journals and a super-journal, publishes new snapshots, then unlinks/fsyncs the
super-journal as commit point. Recovery takes writer locks; live readers see
before-images while the master exists. A short shared/exclusive publication gate
protects attached readers against mixed commits. This gate serializes unrelated
DB publication too. Single-file writes use fsynced atomic rename. VACUUM INTO takes
the target writer lock and uses the same publication gate.

Power-loss/fsync faults are simulated, not physically exercised. A directory fsync
failure after a rename/commit-point unlink can report an error after visibility.
Repeated recovery I/O failures, leftover staging files after kill, and exact
EXCLUSIVE/rollback-reader locking warrant further review.

## Implemented SQL behavior

CRUD/RETURNING, views/INSTEAD OF triggers, TEMP and attached schemas, transactions,
savepoints, strict/generated columns, affinities, CHECK/NOT NULL/UNIQUE/PK/FK,
conflict algorithms, UPSERT, ALTER rename/drop/add/set/drop-not-null, recursive and
ordinary CTEs, joins including RIGHT/FULL, grouping and window functions, scalar,
math/date/time/formatting/JSON5/JSONB functions and JSON table functions.

Static binding checks empty inputs and lazy branches without executing expressions.
Tuple widths/assignments, LIMIT domains, window bounds, aggregate/window nesting,
index definitions and UPSERT targets validate before mutation. Rightmost duplicate
assignment wins; tuple subqueries evaluate once per row. CASE/BETWEEN evaluate
base once. Aggregate ordering/partitioning/grouping obey collations.

CTEs support forward references and skip unused definitions; dependency analysis
respects nested WITH scopes and rejects cycles. Recursive queue execution supports
UNION dedup, ordering, multiple terms, LIMIT/OFFSET; recursive terms disallow
multiple/nested recursive sources and aggregate/window functions. DML materializes
each required CTE once. Runtime Query IDs cache uncorrelated scalar/IN/EXISTS
subqueries; actual outer references are detected by binding scope markers. Trigger
and statement evaluation scopes prevent leakage between invocations.

UPSERT resolves actual unique indexes, including expressions, partial predicates,
collations and reordered composite terms. Targets/tuple assignments survive schema
serialization and renames. sqlite_sequence keeps editable typed rows and rowids,
including duplicate/arbitrary names, with compatibility fallback from old counters.

Foreign actions keep stable row identities and refresh live child tables after
cascades/triggers. This handles self-trees, converging cascades, multiple child
keys and REPLACE deletion. DML preflights relevant FK definitions on empty inputs;
parent keys require complete unique indexes with declared collations. Pre-existing
legacy violations are separated from new violations. DROP's implicit deletes
suppress dropped-table triggers and preserve deferred commit failures. Immediate
FK failures override OR FAIL and abort all changes from that statement.

WHERE filters no longer eagerly evaluate output aliases. Direct aliases expand
into expressions; aliases reached from nested WHERE subqueries evaluate lazily in
their defining environment, honoring inner-name shadowing. ORDER BY sees computed
outputs. Bare min/max columns use a qualifying extreme row even when wrapped,
filtered, repeated or present in HAVING/ORDER BY. JOIN USING compares both operand
affinities; table-function joins apply USING/NATURAL and independent RIGHT/FULL
joins. Documented alternative JOIN keyword orders work; contradictory/NATURAL+ON
forms fail. Correlated functions on RIGHT/FULL currently error.

View metadata binds without running view expressions and carries declared source
column types. table_list includes filtered main/temp/attached tables, views and
catalogs. Schema arguments work on table-valued pragmas and in views over them.
Unknown pragma assignments are ignored. Connection settings ignore schema names;
per-database synchronous/cache settings remain isolated. TEMP synchronous is OFF.
temp_store normalizes modes, resets temporary objects on changes, and rejects
changes in transactions. Actual temp storage stays in memory (like TEMP_STORE=3).

Date/time uses one statement timestamp, ISO weeks, checked ranges, strict ASCII
clock parsing, calendar overflow/floor/ceiling and modifier placement. Formatting
handles dynamic width/precision, SQL quotes, Unicode widths, integer bases/signs,
commas, scientific/general notation and output limits. NUMERIC casts distinguish
real-looking text from existing REAL values; numeric whitespace is ASCII. unhex
requires adjacent digit pairs. Substring arithmetic uses wide intermediates.
NOCASE handles embedded NUL comparison boundaries.

## Verification

Last full release suite passed: 51 smoke, 1223 regression, 536 properties, and both
storage suites. Four GROUP BY assertions and three nested-compound properties
have since been added; next complete run should total 1817 SQL/property checks.

Properties cover arithmetic, NULL, conflicts, malformed/resource inputs, 150
Python Gregorian/ISO checks, 100 timediff round trips and deep valid queries.
Persistence tests cover multiprocess isolation, stale writers, busy timeouts,
kill/reopen, temp privacy, exact types, attached transactions, VACUUM locking,
path/symlink confinement and eight malformed snapshot variants. Journal tests
simulate interrupted commit points, live before-images, injected I/O failures and
retry, and attached reads across 40 concurrent paired commits. Six writers doing
180 increments preserve all updates. Tests derive solely from docs and independent
general-purpose properties.

Metadata binds reuse compound input schemas and skip cloning table rows. This
avoids exponential work: 40 nested scalar subqueries take ~10ms; 32 nested compound
sources take ~2ms in this workspace. Runtime result fields retain collation source
information. Compound ORDER BY matches aliases/expressions across all terms and
validates empty inputs; duplicate comparison uses the first defined collation and
no affinity. Signed/COLLATE ordinal ORDER/GROUP terms work; VALUES disallows trailing
ORDER BY/LIMIT. Snapshot validation checks row shapes/ids, index/trigger references,
NaN storage, query shapes and empty column references before execution. Internal
lock/journal opens reject symlinks (Linux no-follow flag and explicit checks).

## Known gaps and next work

- Run the complete suite after signed/COLLATE GROUP BY handling, then review
  compound/window expression matching and recursive ORDER BY validation.
- Exact physical journal modes are approximations of the durable custom protocol;
  WAL setting is not persisted. Page/cache metadata is approximate.
- Native storage/planner/virtual extensions remain major compatibility gaps.
- Main journal formats and incomplete read locks differ from SQLite concurrency.
- FK baseline accounting versus DROP of externally indexed parent keys in deferred
  transactions needs review; autocommit DROP exception is handled.
- Alias aggregates/windows reached through nested HAVING scopes need further work;
  only non-aggregate aliases are lazy. Recursive steps use separate subquery caches.
- Deep/correlated schema dependency rewriting and exact schema text updates,
  sqlite_sequence empty insertion/trigger edge cases, and unusual row-value
  collation cases still warrant review.
- Date localtime/utc remain UTC no-ops. Floating formatter high precision/rounding
  differs from SQLite's custom conversion. Invalid UTF-8 TEXT uses replacement
  characters; protocol strings and internal strings are valid UTF-8.
- Parser/expression nesting ~100, function args1000, compound terms500, result
  columns2000, joins64, JSON path depth1000. Snapshot JSON nesting guard1024.
