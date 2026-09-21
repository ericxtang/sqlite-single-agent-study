# sqlite-agent

An independent Rust SQL database implementation based only on the supplied SQLite reference documentation. It uses no database engine or SQL parser dependency.

Build and run:

```
cargo build --release --offline --bin sqlite-agent
./target/release/sqlite-agent
```

The executable follows `IO_CONTRACT.md`: one JSON request and response per line, typed result cells, persistent connections, and errors that leave the process usable. Paths must stay under `/work`.

Implementation modules:

- `lex.rs`, `parser.rs`, `ast.rs`: SQL scanning, parsing, and syntax trees.
- `value.rs`, `query.rs`, `rowvalue.rs`, `windowdef.rs`, `subquery.rs`: dynamic values, affinities, SQL expressions, relational queries, aggregates, CTEs, and windows.
- `db.rs`, `schema.rs`, `schema_edit.rs`, `introspect.rs`: schemas, constraints, DML, triggers, attached databases, transactions, and savepoints.
- `storage.rs`: SQLite 3 headers, record encodings, B-trees, overflow chains, freelists, and UTF-8/UTF-16 records.
- `locking.rs`, `journal.rs`, `persistence.rs`, `vacuum.rs`, `settings.rs`, `reindex.rs`, `pagelimit.rs`: advisory locks and durable commit manifests coordinating this implementation's processes and attached files.
- `func.rs`, `date.rs`, `jsonfunc.rs`: scalar functions, UTC date arithmetic, JSON/JSON5, and JSON table functions.

Tests use documentation-derived expectations and this implementation only:

```
cargo test --offline
python3 tests/semantics.py
python3 tests/edgecases.py
python3 tests/windows.py
python3 tests/triggers.py
python3 tests/attach.py
python3 tests/isolation.py
python3 tests/storage.py
python3 tests/recovery.py
python3 tests/foreignkeys.py
python3 tests/names.py
python3 tests/ctes.py
python3 tests/robustness.py
python3 tests/alter.py
python3 tests/indexes.py
python3 tests/corruption.py
python3 tests/busy.py
python3 tests/patterns.py
python3 tests/metadata.py
python3 tests/bulk.py
python3 tests/scopes.py
python3 tests/introspection.py
python3 tests/filemeta.py
python3 tests/vacuum.py
python3 tests/encoding.py
python3 tests/rowvalues.py
python3 tests/pragmas.py
python3 tests/index_integrity.py
python3 tests/lazy_limits.py
python3 tests/subqueries.py
python3 tests/page_limits.py
```

Set `SQLITE_AGENT_BIN=/work/target/release/sqlite-agent` to run process tests against the release binary.

This is a substantial implementation in progress, not complete SQLite compatibility. Commits write full database images with fsync and atomic rename. WAL mode provides snapshot behavior through this mechanism; native WAL files and rollback journals are not implemented. OS locks coordinate this implementation, not other SQLite libraries. Multi-file commits have application-level crash recovery through durable backup manifests. Virtual-table extensions, complete planner/opcode output, JSONB, and some schema/name-resolution details remain incomplete. Parser/expression nesting is limited to 128 and JSON nesting to 200 to keep errors recoverable. See `NOTES.md` for the current work state.

ANALYZE and sqlite_stat1 support persisted table/index statistics, schema scopes, transactions and schema maintenance. PRAGMA optimize supports diagnostic masks and stale/missing statistics; analysis_limit bounds prefix sampling after index records are materialized. Queries still use the scan executor. Validate with `python3 tests/analyze.py` and `python3 tests/optimize.py`.

CTEs evaluate reachable dependencies with nested WITH scopes; stored views isolate caller CTE/column scopes. SQL formatting supports dynamic widths/precision, quoted Unicode strings and numeric flags. Validate with `python3 tests/cte_liveness.py` and `python3 tests/formatting.py`.

Additional validations: `python3 tests/numeric_literals.py` checks numeric grammar and likelihood constants; `python3 tests/replace_actions.py` checks REPLACE deletions, FK/trigger actions, change counts and generated defaults.

`python3 tests/dml_limits.py` covers UPDATE/DELETE LIMIT/OFFSET, collations, view/UPDATE FROM targets, zero-limit binding, and rightmost duplicate assignments.
