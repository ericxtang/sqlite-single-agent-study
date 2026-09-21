# Manually try the SQLite implementations

The consoles below run the saved Rust programs in local Docker containers. They make **no model/API calls**. Each run has its own persistent data volume. Source archives, official grades and hidden tests remain untouched.

## 1. Open a console

Docker must be running. Paste this into a terminal:

```sh
cd sqlite-single-agent-study
python3 manual/lab.py console 001
```

Replace `001` with `002` or `004` to try the other completed four-hour artifacts. The first launch builds the selected source archive in Docker. The `001>` prompt accepts **one SQL statement per line**. A semicolon is optional. This is a small console around the study's JSON interface, not the stock `sqlite3` shell.

Run `003` is different: its interrupted terminal artifact fails to compile (five Rust errors). `python3 manual/lab.py console 003` shows the saved build-log location. For an explicitly **older, 30-minute checkpoint**, use `python3 manual/lab.py console 003-30min`. That is not run 003's terminal result or a four-hour replacement.

## 2. Try SQL and a transaction

Paste these lines into the SQL console:

```sql
.open :memory:
SELECT 2 + 3 AS five, NULL IS NULL AS null_test;
CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, qty INTEGER);
INSERT INTO items VALUES (1,'apricot',2),(2,'bread',5),(3,'coffee',1);
SELECT name, qty FROM items ORDER BY qty DESC, name;
SELECT count(*) AS products, sum(qty) AS total_quantity FROM items;
BEGIN;
UPDATE items SET qty=99 WHERE id=2;
SELECT qty FROM items WHERE id=2;
ROLLBACK;
SELECT qty FROM items WHERE id=2;
INSERT INTO items VALUES (2,'duplicate',9);
SELECT count(*) AS still_three FROM items;
```

Expected: `5, 1`; bread/apricot/coffee with quantities `5, 2, 1`; then `3` products and total quantity `8`. Inside the transaction bread becomes `99`; rollback restores `5`. The duplicate primary key should return an error, after which the process should still answer with count `3`.

For broader SQL behavior:

```sql
WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<5) SELECT sum(x) AS fifteen FROM n;
SELECT name, row_number() OVER (ORDER BY qty DESC, name) AS rank FROM items ORDER BY qty DESC, name;
SELECT json_extract('{"answer":42}', '$.answer') AS answer;
.raw on
SELECT NULL AS n, 42 AS i, 3.5 AS r, 'hello' AS t, X'00abff' AS b;
.raw off
```

Expect `15`, ranks `1/2/3`, and `42`. Raw mode exposes the actual typed JSON cells. The blob may be `00ABFF` or `00abff`: those represent the same bytes. This is relevant to the report's strict secondary-comparison caveat.

## 3. Test saved data and inspect its format

This example resets only the `notes` table in this run's dedicated `manual-demo.db`:

```sql
.open /work/manual-demo.db
DROP TABLE IF EXISTS notes;
CREATE TABLE notes(id INTEGER PRIMARY KEY, note TEXT, payload BLOB);
INSERT INTO notes VALUES(1,'saved across restart',X'00abff');
.restart
SELECT id, note, hex(payload) AS hex_bytes FROM notes;
.header
```

Expect `1`, `saved across restart`, `00ABFF` after the engine process restarts. `.header` reads the first 16 file bytes. Run 002 shows `SQLite format 3\x00`; 001 starts `RustSQLite snaps`; 004 starts a JSON object. The older 003 checkpoint starts `RustSQLite`. A recognizable header alone does not establish full file compatibility.

Use `.quit` to close the console. Reopen the same run later and use `.open /work/manual-demo.db` to revisit its data. Opening `:memory:` starts a fresh empty database. `.help` lists console commands; standard sqlite3 commands such as `.tables` are not implemented.

## 4. Logs, shortcuts and stopping

The [ready-to-paste examples](../manual/examples.txt) contain the entire walkthrough. To replay them from a normal terminal:

```sh
python3 manual/lab.py console 002 < manual/examples.txt
python3 manual/lab.py status
python3 manual/lab.py stop
```

`stop` affects only these manual consoles and retains their data. Containers have no network or host-directory mounts; the code volume is read-only at runtime. A query without a response for 30 seconds ends that console and preserves its logs. This manual timeout is not a benchmark setting.

Build logs, console stderr and timestamped raw requests/responses are in manual/logs (retained in the private audit; not bundled). Snapshot hashes and volume names are in manual/instances (retained in the private audit; not bundled). Logs include SQL and values you enter, so use sample data.

The walkthrough was checked on September 21: all 11 result-producing queries matched the stated values on 001, 002, 004 and the explicitly older 003 checkpoint; the duplicate-key error and restart also behaved as described. See diagnostic results (retained in the private audit; not bundled). These small examples illustrate behavior; they are not new grades or a claim of full SQLite compatibility.
