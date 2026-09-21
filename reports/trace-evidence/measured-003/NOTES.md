# Independent Rust database implementation

Build: `cargo build --release --offline --bin sqlite-agent`
Test: `python3 tests/smoke.py` (documentation-derived assertions only).

Architecture: handwritten tokenizer and Pratt/recursive descent parser; serializable SQL AST; typed scalar values with affinity/collation; scan-based relational evaluation; rowid tables and logical indexes; statement snapshots and nested transaction/savepoint snapshots. Persistent commits atomically replace a synced private-format file within /work. No external database/parser code or reference engine used.

Implemented: JSON-line process lifecycle; literals/operators/CASE/CAST/IN/subqueries; SELECT joins/grouping/aggregates/compounds/CTEs/recursive CTEs/windows; DDL/tables/views/indexes; INSERT/UPDATE/DELETE with RETURNING; basic upsert; constraints, generated columns, STRICT, rowids; foreign keys with delete actions; transactions/savepoints; introspection pragmas; scalar/date/JSON functions.

Current caveats: not SQLite binary-file compatible; no triggers/attached schemas yet; some window frame details, JSON subtype propagation, collation/affinity corner cases, constraint conflict policies, update foreign-key actions, and advanced ALTER dependency rewriting incomplete. Query planning uses scans, no physical index optimization. Docs accessible /docs. rustfmt component unavailable offline.

Next: strengthen semantic tests, default/conflict behavior and statement rollback, implement triggers; then improve storage and remaining SQL coverage. Keep executable integrated throughout.
