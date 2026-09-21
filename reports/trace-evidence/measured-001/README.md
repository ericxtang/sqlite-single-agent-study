# Rust SQL database agent

Build the offline executable:

```sh
cargo build --release --offline --bin sqlite-agent
```

Run `target/release/sqlite-agent` and send one JSON object per line. Responses are
flushed JSON lines. A connection must be opened before executing SQL:

```json
{"op":"open","path":":memory:"}
{"op":"execute","sql":"CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)"}
{"op":"execute","sql":"INSERT INTO t(name) VALUES('example') RETURNING id,name"}
{"op":"execute","sql":"SELECT * FROM t"}
{"op":"close"}
```

Use a file path under `/work` for persistence. The response and typed-cell format
is specified in `IO_CONTRACT.md`. Run `tests/run.sh` for the integrated verification
suite. Architecture, implementation coverage, and remaining limitations are in
`NOTES.md`.

This implementation uses custom database snapshots and opaque JSONB encodings;
it does not read native SQLite database files or native SQLite JSONB blobs.
