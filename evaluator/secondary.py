"""Frozen, hidden compatibility probes; not a SQLite conformance suite."""
import json
from pathlib import Path
import sqlite3
import tempfile

from slt import Reference, typed


def call(engine, op, **args):
    answer = engine.request(dict(op=op, **args))
    if not isinstance(answer, dict) or type(answer.get('ok')) is not bool:
        raise ValueError('Malformed protocol response')
    return answer


def execute(engine, sql, expected=None, ok=True):
    answer = call(engine, 'execute', sql=sql)
    if answer['ok'] != ok:
        raise ValueError('Unexpected SQL success/error')
    if expected is not None:
        wanted = [[typed(value) for value in row] for row in expected]
        if answer.get('rows') != wanted or len(answer.get('columns', [])) != len(expected[0]):
            raise ValueError('Typed result mismatch')


SQL_CASES = [
    ('typed_values', [
        ("SELECT 42, -7, 1.5, 'héllo', NULL, x'00ff'", [(42, -7, 1.5, 'héllo', None, b'\x00\xff')], True),
    ]),
    ('transaction_rollback', [
        ('CREATE TABLE t(x INTEGER)', None, True),
        ('INSERT INTO t VALUES(1)', None, True),
        ('BEGIN', None, True),
        ('INSERT INTO t VALUES(2)', None, True),
        ('ROLLBACK', None, True),
        ('SELECT x FROM t ORDER BY x', [(1,)], True),
    ]),
    ('nested_savepoint', [
        ('CREATE TABLE t(x INTEGER)', None, True),
        ('BEGIN', None, True),
        ('INSERT INTO t VALUES(1)', None, True),
        ('SAVEPOINT s', None, True),
        ('INSERT INTO t VALUES(2)', None, True),
        ('ROLLBACK TO s', None, True),
        ('RELEASE s', None, True),
        ('COMMIT', None, True),
        ('SELECT x FROM t ORDER BY x', [(1,)], True),
    ]),
    ('constraints_and_statement_atomicity', [
        ('CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT NOT NULL UNIQUE, n INTEGER CHECK(n>0))', None, True),
        ("INSERT INTO t VALUES(1,'a',2)", None, True),
        ("INSERT INTO t VALUES(2,'a',3)", None, False),
        ("INSERT INTO t VALUES(2,'b',0)", None, False),
        ("INSERT INTO t VALUES(2,NULL,2)", None, False),
        ("INSERT INTO t VALUES(2,'b',2),(3,'a',3)", None, False),
        ('SELECT id,v,n FROM t ORDER BY id', [(1, 'a', 2)], True),
    ]),
    ('foreign_key_cascade', [
        ('PRAGMA foreign_keys=ON', None, True),
        ('CREATE TABLE p(id INTEGER PRIMARY KEY)', None, True),
        ('CREATE TABLE c(id INTEGER REFERENCES p(id) ON DELETE CASCADE)', None, True),
        ('INSERT INTO p VALUES(1)', None, True),
        ('INSERT INTO c VALUES(1)', None, True),
        ('INSERT INTO c VALUES(2)', None, False),
        ('DELETE FROM p WHERE id=1', None, True),
        ('SELECT count(*) FROM c', [(0,)], True),
    ]),
    ('recursive_cte', [
        ('WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<5) SELECT sum(x) FROM n', [(15,)], True),
    ]),
    ('window_function', [
        ('CREATE TABLE t(x INTEGER)', None, True),
        ('INSERT INTO t VALUES(3),(1),(2)', None, True),
        ('SELECT x,sum(x) OVER (ORDER BY x ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) FROM t ORDER BY x', [(1, 1), (2, 3), (3, 6)], True),
    ]),
    ('json_extract', [
        ('''SELECT json_extract('{"a":[1,7]}','$.a[1]')''', [(7,)], True),
    ]),
]
CASE_NAMES = [c[0] for c in SQL_CASES] + ['close_reopen', 'process_restart', 'sqlite_reads_generated_file', 'generated_reads_sqlite_file']
CREATE = 'CREATE TABLE items(id INTEGER PRIMARY KEY, label TEXT, payload BLOB)'
INSERT = "INSERT INTO items VALUES(1,'alpha',x'00ff'),(9,'βeta',x'1020')"
SELECT = 'SELECT id,label,payload FROM items ORDER BY id'
ROWS = [(1, 'alpha', b'\x00\xff'), (9, 'βeta', b'\x10\x20')]


class ReferenceLab:
    """Also supplies trusted file seed/read operations to the isolated lab."""
    def __init__(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sqlite-secondary-reference-')
        self.root = Path(self.temporary.name)
        self.engines = []

    def path(self, case):
        return str(self.root / (case + '.db'))

    def start(self, case):
        engine = Reference()
        self.engines.append(engine)
        return engine

    def stop(self, engine):
        call(engine, 'close')

    def seed(self, case):
        with sqlite3.connect(self.path(case)) as connection:
            connection.execute(CREATE)
            connection.execute(INSERT)

    def verify_file(self, case):
        # mode=ro cannot create a missing database or repair the generated file.
        with sqlite3.connect(Path(self.path(case)).as_uri() + '?mode=ro', uri=True) as connection:
            if connection.execute(SELECT).fetchall() != ROWS:
                raise ValueError('Reference SQLite readback mismatch')
            if connection.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise ValueError('Reference SQLite quick_check failed')

    def close(self):
        for engine in self.engines:
            self.stop(engine)
        self.temporary.cleanup()


def run_suite(lab):
    results = []
    for name in CASE_NAMES:
        engine = None
        result = {'case': name, 'passed': False}
        try:
            if name == 'generated_reads_sqlite_file':
                lab.seed(name)
            engine = lab.start(name)
            path = ':memory:' if name in dict((c[0], c[1]) for c in SQL_CASES) else lab.path(name)
            if not call(engine, 'open', path=path)['ok']:
                raise ValueError('Open failed')
            if name in dict((c[0], c[1]) for c in SQL_CASES):
                for sql, expected, ok in dict((c[0], c[1]) for c in SQL_CASES)[name]:
                    execute(engine, sql, expected, ok)
            elif name == 'generated_reads_sqlite_file':
                execute(engine, SELECT, ROWS)
            else:
                execute(engine, CREATE)
                execute(engine, 'BEGIN')
                execute(engine, INSERT)
                execute(engine, 'COMMIT')
                if not call(engine, 'close')['ok']:
                    raise ValueError('Close failed')
                if name == 'sqlite_reads_generated_file':
                    lab.verify_file(name)
                else:
                    if name == 'process_restart':
                        lab.stop(engine)
                        engine = None
                        engine = lab.start(name)
                    if not call(engine, 'open', path=path)['ok']:
                        raise ValueError('Reopen failed')
                    execute(engine, SELECT, ROWS)
            result['passed'] = True
        except (ValueError, TypeError, KeyError, OSError, TimeoutError, sqlite3.Error) as exc:
            result['reason'] = str(exc)
        finally:
            if engine is not None:
                lab.stop(engine)
        results.append(result)
    return {'cases': results, 'passed': sum(r['passed'] for r in results), 'total': len(CASE_NAMES), 'not_assessed': ['power_loss_recovery', 'concurrency', 'performance', 'comprehensive_documentation_coverage']}


if __name__ == '__main__':
    lab = ReferenceLab()
    try:
        result = run_suite(lab)
    finally:
        lab.close()
    assert result['passed'] == result['total'], result
    print(json.dumps({'sqlite_version': sqlite3.sqlite_version, **result}, indent=2))
