# sqlite-agent

An independent Rust implementation of SQLite-style SQL, built from the supplied offline documentation. It uses only Rust's standard library, serde, and serde_json. It does not invoke or embed SQLite or an existing SQL parser.

Build and run:

```sh
cargo build --release --offline --bin sqlite-agent
target/release/sqlite-agent
```

The process accepts JSON objects, one per line, and flushes one JSON response per request. See `IO_CONTRACT.md` for the complete interface. Example input:

```json
{"op":"open","path":":memory:"}
{"op":"execute","sql":"CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT)"}
{"op":"execute","sql":"INSERT INTO items(name) VALUES ('example') RETURNING *"}
{"op":"execute","sql":"SELECT name FROM items"}
{"op":"close"}
```

State remains on the open connection. Filesystem databases are confined to `/work`. Commits write a synced snapshot and atomically replace the previous file. Writer locks and transaction snapshots protect concurrent connections. Multi-file commits use a durable decision journal that is recovered when an affected database is reopened. Uncommitted changes are discarded on close or process exit. Persistent files use this implementation's internal format, not SQLite's native binary format.

Implemented features include expressions and dynamic types; joins, aggregates, subqueries, CTEs, compounds and window functions; tables, views, indexes and triggers; constraints, generated columns, foreign keys and conflict handling; DML with RETURNING and UPSERT; transactions and savepoints; scalar, date, math and JSON functions; JSON table functions; and common introspection PRAGMAs. Compatibility is partial: see `NOTES.md` for specific limitations and ongoing work.

Run the documentation-derived regression suite:

```sh
python3 tests/run_all.py
```
