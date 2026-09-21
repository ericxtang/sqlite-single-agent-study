# Process interface

Provide a Rust Cargo project at `/work`. `cargo build --release --offline --bin sqlite-agent` must produce `target/release/sqlite-agent`.

The executable reads one JSON object per line from stdin and writes exactly one JSON response line per request to stdout, flushing each response. Send diagnostics to stderr. Remain alive between requests. Preserve database state across requests on the same open connection.

Requests:

- `{"op":"open","path":":memory:"}` opens a new, empty in-memory database. A filesystem path opens or creates a persistent database. Close any existing connection first.
- `{"op":"execute","sql":"SQL text"}` executes one statement on the current connection.
- `{"op":"close"}` closes the connection. Persistent data must survive reopening.

Responses:

- Open/close/non-row-producing success: `{"ok":true,"columns":[],"rows":[]}`.
- Row-producing success: `{"ok":true,"columns":["column name"],"rows":[[{"type":"integer","value":"1"}]]}`.
- SQL or operational error: `{"ok":false,"error":"description"}`. Keep the process alive after ordinary SQL errors.

Each cell is an object with a `type`: `null`, `integer`, `real`, `text`, or `blob`. NULL cells are `{"type":"null"}`. Integers use base-10 string values to avoid JSON precision loss. Reals use decimal string values. Text uses a JSON string value. Blobs use an even-length hexadecimal string value. Column names and row widths must agree. Return an empty row list with the correct columns for empty SELECT results.

Each process starts without an open connection. Database files and temporary files must be confined to the provided writable workspace. You may build a Rust library behind this interface. The interface does not constrain internal architecture.

General-purpose dependencies available offline: `serde = 1.0.228` (derive enabled), `serde_json = 1.0.145`, and their vendored transitive dependencies. Rust standard library is available. Do not use any existing database engine or SQL parser implementation. Implement database functionality in Rust yourself.
